"""Extended FRED universe -> curated/fred (docs/DATA_CONTRACT.md).

    .venv/bin/python -m src.ingest.fred_extended            # incremental (reuse raw < 20h old)
    .venv/bin/python -m src.ingest.fred_extended --refresh  # force re-download

* Legacy series in $FIN_DATA_ROOT/macro/fred/*.csv (+ .metadata.json) are re-normalised,
  not re-downloaded (legacy files are read-only).
* New series are downloaded from the FRED API to $FIN_DATA_ROOT/raw/fred_extended/
  (<id>.observations.json + <id>.series.json, untouched API responses) and normalised to
  $FIN_DATA_ROOT/curated/fred/<series_id>.parquet + _catalog.csv.
* Every ID is verified with fred/series; missing IDs fall back to the listed substitutes.
* All ICE BofA (BAML*) series are discovered via fred/series/search.
* Rate limit: <= 2 requests/second. The API key is never logged.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

API = "https://api.stlouisfed.org/fred"
SOURCE = "fred"
RAW_SOURCE = "fred_extended"
LICENSE = ("FRED/ALFRED terms of use: personal/research use; some series carry third-party "
           "copyright (ICE BofA, S&P/Dow Jones, NASDAQ, OECD, BIS, IMF)")
CATALOG_COLS = ["series_id", "source", "name", "category", "frequency", "units", "country",
                "start", "end", "transform_notes", "url", "license",
                # extras (metadata requested by the plan)
                "requested_id", "n_obs", "observation_start", "observation_end",
                "seasonal_adjustment", "last_updated", "notes"]
SCHEMA = pa.schema([("date", pa.date32()), ("value", pa.float64()),
                    ("series_id", pa.string()), ("source", pa.string())])

log = logging.getLogger("fred_extended")


def data_root() -> Path:
    return Path(os.path.expanduser(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")))


# --------------------------------------------------------------------------------------
# Universe: id -> (category, country, [substitute ids], note)
# --------------------------------------------------------------------------------------
def _u(cat, country="US", subs=(), note=""):
    return (cat, country, list(subs), note)


UNIVERSE: dict[str, tuple] = {
    # --- employment ---
    "UNRATE": _u("employment"), "UNRATENSA": _u("employment"),
    "M0892AUSM156SNBR": _u("employment", note="NBER macrohistory unemployment 1929-1942"),
    "M0892BUSM156SNBR": _u("employment", note="NBER macrohistory unemployment 1940-1946"),
    "M0892CUSM156NNBR": _u("employment", note="NBER macrohistory unemployment 1947-1966"),
    "NROU": _u("employment"), "CCSA": _u("employment"), "ICSA": _u("employment"),
    "JTSJOL": _u("employment"), "AWHMAN": _u("employment"), "CFNAI": _u("growth"),
    "SAHMREALTIME": _u("growth"),
    # --- rates / bond history ---
    "GS1": _u("rates"), "GS2": _u("rates"), "GS3": _u("rates"), "GS5": _u("rates"),
    "GS7": _u("rates"), "GS10": _u("rates"), "GS20": _u("rates"), "GS30": _u("rates"),
    "TB3MS": _u("rates"), "TB6MS": _u("rates"), "DTB3": _u("rates"),
    "AAA": _u("rates"), "BAA": _u("rates"),
    "M13009USM156NNBR": _u("rates", note="NBER: discount rate FRB New York 1914-1969"),
    "M1333AUSM156NNBR": _u("rates", note="NBER: yield on long-term US bonds 1919-1944"),
    "M13002US35620M156NNBR": _u("rates", note="NBER: commercial paper rates NY 1857-1971"),
    "M13001USM156NNBR": _u("rates", note="NBER: call money rates, mixed collateral 1857-1970"),
    "M13019USM156NNBR": _u("rates", note="NBER: American railroad bond yields high grade 1857-1937"),
    "M13026USM156NNBR": _u("rates", note="NBER: yield high-grade industrial bonds Aaa 1900-1972"),
    "M13021USM156NNBR": _u("rates", note="NBER: index of yields high-grade corp+muni 1900-1967"),
    "DFII5": _u("rates"), "DFII10": _u("rates"), "DFII30": _u("rates"),
    "THREEFYTP10": _u("rates"), "THREEFY10": _u("rates"),
    "MORTGAGE30US": _u("housing"), "FEDFUNDS": _u("rates"), "INTDSRUSM193N": _u("rates"),
    # --- credit & fractures ---
    "BAA10Y": _u("credit"), "AAA10Y": _u("credit"), "TEDRATE": _u("credit"),
    "DRTSCILM": _u("credit"), "DRTSCIS": _u("credit"), "DRSFRMACBS": _u("credit"),
    "DRCCLACBS": _u("credit"), "DRALACBS": _u("credit"), "DRBLACBS": _u("credit"),
    "TOTLL": _u("credit"), "BUSLOANS": _u("credit"), "CONSUMER": _u("credit"),
    "TDSP": _u("credit"), "NCBDBIQ027S": _u("credit"),
    "TCMDO": _u("credit", note="All sectors debt securities and loans (Z.1)"),
    "TCMDODNS": _u("credit", note="Domestic nonfinancial sectors debt (Z.1)"),
    "QUSPAM770A": _u("credit"), "QUSCAM770A": _u("credit"), "QUSHAM770A": _u("credit"),
    "QUSNAM770A": _u("credit"),
    "STLFSI4": _u("financial_conditions"), "KCFSI": _u("financial_conditions"),
    "NFCI": _u("financial_conditions"), "ANFCI": _u("financial_conditions"),
    "NFCICREDIT": _u("financial_conditions"), "NFCILEVERAGE": _u("financial_conditions"),
    "NFCIRISK": _u("financial_conditions"),
    "WTREGEN": _u("liquidity"), "RRPONTSYD": _u("liquidity"), "WRESBAL": _u("liquidity"),
    "WALCL": _u("liquidity"), "BOGMBASE": _u("money"),
    # --- inflation & commodities ---
    "PPIACO": _u("inflation"), "WPU0561": _u("commodities"), "CPIAUCNS": _u("inflation"),
    "PCOPPUSDM": _u("commodities", "WLD"), "PWHEAMTUSDM": _u("commodities", "WLD"),
    "POILBREUSDM": _u("commodities", "WLD"), "MCOILWTICO": _u("commodities"),
    "PNGASUSUSDM": _u("commodities"), "PALLFNFINDEXM": _u("commodities", "WLD"),
    "PNRGINDEXM": _u("commodities", "WLD"), "PFOODINDEXM": _u("commodities", "WLD"),
    "PMETAINDEXM": _u("commodities", "WLD"),
    "M04051USM324NNBR": _u("inflation", note="NBER: index of general price level 1860-1939"),
    "IR14270": _u("gold", note="PROXY: import price index nonmonetary gold (no live gold price in FRED)"),
    "M1476BUSM027NNBR": _u("gold", note="NBER: monetary gold stock US 1914-1946"),
    # --- fiscal ---
    "GFDEGDQ188S": _u("fiscal"), "FYFSGDA188S": _u("fiscal"),
    "A091RC1Q027SBEA": _u("fiscal"), "W006RC1Q027SBEA": _u("fiscal"), "FYGFDPUN": _u("fiscal"),
    "FYONGDA188S": _u("fiscal"), "FYOIGDA188S": _u("fiscal"),
    # --- fx ---
    "DTWEXBGS": _u("fx"), "TWEXBMTH": _u("fx"), "TWEXB": _u("fx"), "TWEXMMTH": _u("fx"),
    "RTWEXBGS": _u("fx"), "DEXUSEU": _u("fx"), "DEXJPUS": _u("fx"), "DEXUSUK": _u("fx"),
    "DEXCHUS": _u("fx"), "DEXSZUS": _u("fx"),
    # --- markets ---
    "SP500": _u("markets"), "NASDAQCOM": _u("markets"), "VIXCLS": _u("markets"),
    "DJIA": _u("markets"),
    "WILL5000INDFC": _u("markets", subs=["BOGZ1FL073164003Q"],
                        note="Wilshire indices removed from FRED"),
    "NCBEILQ027S": _u("valuation", note="Nonfin. corporate equities market value (Buffett ratio numerator)"),
    "M1109BUSM293NNBR": _u("markets", note="NBER: Dow-Jones industrial index 1914-1968"),
    "M1109AUSM293NNBR": _u("markets", note="NBER: Dow-Jones industrial index 1897-1916"),
    "M1125AUSM343NNBR": _u("markets", note="NBER: Cowles/S&P all common stocks 1871-1956"),
    "M1346BUSM156NNBR": _u("valuation", note="NBER: NYSE dividend yield 1926-1969"),
    # --- international ---
    "IRLTLT01DEM156N": _u("rates", "DE"), "IRLTLT01GBM156N": _u("rates", "GB"),
    "IRLTLT01JPM156N": _u("rates", "JP"), "IRLTLT01ITM156N": _u("rates", "IT"),
    "IRLTLT01ESM156N": _u("rates", "ES"), "IRLTLT01FRM156N": _u("rates", "FR"),
    "CP0000EZ19M086NEST": _u("inflation", "EA"), "CP00MI15EA20M086NEST": _u("inflation", "EA"),
    "LRHUTTTTEZM156S": _u("employment", "EA", note="OECD MEI; discontinued 2023-01"),
    "USALOLITOAASTSAM": _u("growth", "US"), "DEULOLITOAASTSAM": _u("growth", "DE"),
    "GBRLOLITOAASTSAM": _u("growth", "GB"), "JPNLOLITOAASTSAM": _u("growth", "JP"),
    "CHNLOLITOAASTSAM": _u("growth", "CN"), "G7LOLITOAASTSAM": _u("growth", "G7"),
    "EA19LOLITOAASTSAM": _u("growth", "EA", note="discontinued 2022-11"),
}

LEGACY_CAT = {
    "business_cycle": "growth", "consumer_sentiment": "growth", "consumption": "growth",
    "interest_rates": "rates", "yield_curve": "rates", "housing_rates": "housing",
    "inflation_expectations": "inflation", "wages": "employment",
}
FREQ = {"D": "D", "W": "W", "BW": "W", "M": "M", "Q": "Q", "SA": "Q", "A": "A"}


# --------------------------------------------------------------------------------------
class Fred:
    def __init__(self, min_interval: float = 0.55):
        self.key = os.environ.get("FRED_API_KEY")
        if not self.key:
            raise SystemExit("FRED_API_KEY missing in .env")
        self.min_interval = min_interval
        self._last = 0.0
        self.s = requests.Session()
        self.n_requests = 0

    def get(self, endpoint: str, **params) -> dict:
        params.update(api_key=self.key, file_type="json")
        for attempt in range(5):
            wait = self.min_interval - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()
            self.n_requests += 1
            try:
                r = self.s.get(f"{API}/{endpoint}", params=params, timeout=60)
            except requests.RequestException as e:  # never log the URL (contains key)
                log.warning("%s network error (%s), retry %d", endpoint, type(e).__name__, attempt)
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code == 429 or r.status_code >= 500:
                log.warning("%s HTTP %d, retry %d", endpoint, r.status_code, attempt)
                time.sleep(5 * (attempt + 1))
                continue
            j = r.json()
            if r.status_code != 200:
                raise FredError(j.get("error_message", f"HTTP {r.status_code}"))
            return j
        raise FredError(f"{endpoint}: retries exhausted")


class FredError(Exception):
    pass


# --------------------------------------------------------------------------------------
def _clean(text: str | None, n: int = 400) -> str:
    return re.sub(r"\s+", " ", text or "").strip()[:n]


def write_parquet(path: Path, df: pd.DataFrame, schema: pa.Schema = SCHEMA) -> None:
    tbl = pa.Table.from_pandas(df, schema=schema, preserve_index=False)
    tmp = path.with_suffix(".parquet.part")
    pq.write_table(tbl, tmp)
    tmp.replace(path)


def obs_to_frame(obs: list[dict], sid: str) -> pd.DataFrame:
    df = pd.DataFrame(obs)[["date", "value"]]
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["value"] = pd.to_numeric(df["value"].replace(".", None), errors="coerce").astype("float64")
    df["series_id"] = sid
    df["source"] = SOURCE
    return df.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)


def catalog_row(sid, meta, df, cat, country, requested, note, origin) -> dict:
    v = df.dropna(subset=["value"])
    fs = meta.get("frequency_short", "")
    freq = FREQ.get(fs, FREQ.get(fs[:1], fs))
    tn = [origin, "value '.' -> NaN; date = FRED observation date (period start for M/Q/A;"
          " week-ending/day for D/W)"]
    if fs == "SA":
        tn.append("semiannual mapped to Q")
    if note:
        tn.append(note)
    if requested != sid:
        tn.append(f"substitute for requested {requested}")
    if "DISCONTINUED" in meta.get("title", "").upper():
        tn.append("DISCONTINUED in FRED")
    return {
        "series_id": sid, "source": SOURCE, "name": meta.get("title", sid), "category": cat,
        "frequency": freq, "units": meta.get("units", ""), "country": country,
        "start": str(v["date"].min()) if len(v) else "", "end": str(v["date"].max()) if len(v) else "",
        "transform_notes": "; ".join(tn), "url": f"https://fred.stlouisfed.org/series/{sid}",
        "license": LICENSE, "requested_id": requested, "n_obs": int(len(v)),
        "observation_start": meta.get("observation_start", ""),
        "observation_end": meta.get("observation_end", ""),
        "seasonal_adjustment": meta.get("seasonal_adjustment_short", ""),
        "last_updated": meta.get("last_updated", ""), "notes": _clean(meta.get("notes")),
    }


# --------------------------------------------------------------------------------------
# Known data problems found by the data audit (docs/data/audit_2026-10-12_tarde.md).
# sid -> list of (first date, last date, factor, reason): values in the range are multiplied by factor.
KNOWN_FIXES: dict[str, list[tuple[str, str, float, str]]] = {
    "BOGZ1FL073164003Q": [("1945-01-01", "1951-12-31", 10.0,
                           "pre-1952 annual (Q4) observations are one decimal place off the quarterly "
                           "series that starts in 1952 (1.277 in 1951-Q4 vs 12.910 in 1952-Q1)")],
}
# sid -> catalog fields to override, plus an extra transform note.
CATALOG_OVERRIDES: dict[str, dict[str, str]] = {
    "BOGZ1FL073164003Q": {"units": "Index (FRED metadata says 'Percent': wrong)",
                          "note": "Z.1 corporate equities market value index; used only as a Wilshire substitute"},
    "M1SL": {"note": "DEFINITION BREAK 2020-05: savings deposits reclassified into M1 (Fed H.6, Feb-2021); "
                     "levels jump ~+11 tn USD; do not use y/y changes across 2020-05..2021-04"},
}


def apply_fixes(sid: str, df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    notes = []
    for lo, hi, factor, why in KNOWN_FIXES.get(sid, []):
        d = pd.to_datetime(df["date"])
        m = (d >= pd.Timestamp(lo)) & (d <= pd.Timestamp(hi)) & df["value"].notna()
        if m.any():
            df = df.copy()
            df.loc[m, "value"] = df.loc[m, "value"] * factor
            notes.append(f"FIX {lo}..{hi} x{factor:g}: {why}")
    if CATALOG_OVERRIDES.get(sid, {}).get("note"):
        notes.append(CATALOG_OVERRIDES[sid]["note"])
    return df, "; ".join(notes)


def override_row(sid: str, row: dict) -> dict:
    if "units" in CATALOG_OVERRIDES.get(sid, {}):
        row["units"] = CATALOG_OVERRIDES[sid]["units"]
    return row


def load_legacy(legacy_dir: Path, out: Path) -> dict[str, dict]:
    rows = {}
    for csv in sorted(legacy_dir.glob("*.csv")):
        sid = csv.stem
        meta_p = legacy_dir / f"{sid}.metadata.json"
        meta = json.loads(meta_p.read_text())["seriess"][0] if meta_p.exists() else {}
        raw = pd.read_csv(csv)
        legacy_cat = str(raw["category"].iloc[0]) if "category" in raw and len(raw) else ""
        cat = LEGACY_CAT.get(legacy_cat, legacy_cat) or UNIVERSE.get(sid, ("growth",))[0]
        if sid in UNIVERSE:
            cat = UNIVERSE[sid][0]
        df = obs_to_frame(raw[["date", "value"]].astype({"value": "string"}).to_dict("records"), sid)
        df, fix_note = apply_fixes(sid, df)
        write_parquet(out / f"{sid}.parquet", df)
        rows[sid] = override_row(sid, catalog_row(sid, meta, df, cat, "US", sid, fix_note,
                                "origin: legacy macro/fred CSV (re-normalised, not re-downloaded)"))
    log.info("legacy: %d series re-normalised", len(rows))
    return rows


def fetch_series(fred: Fred, sid: str, raw: Path, refresh: bool, meta: dict | None = None):
    """Return (meta, observations) for sid, using raw cache if fresh."""
    p_obs, p_meta = raw / f"{sid}.observations.json", raw / f"{sid}.series.json"
    fresh = p_obs.exists() and p_meta.exists() and (time.time() - p_obs.stat().st_mtime) < 20 * 3600
    if fresh and not refresh:
        return json.loads(p_meta.read_text())["seriess"][0], json.loads(p_obs.read_text())["observations"]
    if meta is None:
        mj = fred.get("series", series_id=sid)
    else:
        mj = {"seriess": [meta]}
    obs_all, offset = [], 0
    while True:
        j = fred.get("series/observations", series_id=sid, limit=100000, offset=offset)
        obs_all += j["observations"]
        if len(obs_all) >= int(j.get("count", 0)) or not j["observations"]:
            break
        offset = len(obs_all)
    j["observations"], j["offset"] = obs_all, 0
    p_meta.write_text(json.dumps(mj))
    p_obs.write_text(json.dumps(j))
    return mj["seriess"][0], obs_all


def discover_baml(fred: Fred) -> dict[str, dict]:
    found, offset = {}, 0
    while True:
        j = fred.get("series/search", search_text="ICE BofA", limit=1000, offset=offset)
        for s in j.get("seriess", []):
            if s["id"].startswith("BAML"):
                found[s["id"]] = s
        offset += 1000
        if offset >= int(j.get("count", 0)):
            break
    log.info("BAML discovery: %d series", len(found))
    return found


def run(refresh: bool = False) -> pd.DataFrame:
    root = data_root()
    raw = root / "raw" / RAW_SOURCE
    out = root / "curated" / SOURCE
    raw.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    rows = load_legacy(root / "macro" / "fred", out)

    fred = Fred()
    failures, substitutions = [], []
    todo: list[tuple[str, tuple, dict | None]] = [(k, v, None) for k, v in UNIVERSE.items()]
    for sid, meta in discover_baml(fred).items():
        if sid not in UNIVERSE:
            t = meta.get("title", "")
            ctry = "EA" if "Euro" in t else "EM" if "Emerging" in t else "US"
            todo.append((sid, _u("credit", ctry), meta))

    for requested, (cat, country, subs, note), meta in todo:
        if requested in rows:
            continue
        got = None
        for sid in [requested, *subs]:
            if sid in rows:
                got = sid
                break
            try:
                m, obs = fetch_series(fred, sid, raw, refresh, meta if sid == requested else None)
            except FredError as e:
                log.warning("%s: %s", sid, e)
                continue
            if not obs:
                log.warning("%s: no observations", sid)
                continue
            df = obs_to_frame(obs, sid)
            df, fix_note = apply_fixes(sid, df)
            write_parquet(out / f"{sid}.parquet", df)
            rows[sid] = override_row(sid, catalog_row(sid, m, df, cat, country, requested,
                                                      "; ".join(x for x in (note, fix_note) if x),
                                                      "origin: FRED API (raw/fred_extended)"))
            got = sid
            break
        if got is None:
            failures.append(requested)
        elif got != requested:
            substitutions.append((requested, got))
            log.info("substituted %s -> %s", requested, got)

    cat_df = pd.DataFrame(list(rows.values()), columns=CATALOG_COLS).sort_values("series_id")
    cat_df.to_csv(out / "_catalog.csv", index=False)
    (raw / "_run_summary.json").write_text(json.dumps({
        "run_utc": pd.Timestamp.now("UTC").isoformat(), "n_series": len(cat_df),
        "failures": failures, "substitutions": substitutions, "requests": fred.n_requests,
    }, indent=2))
    log.info("curated/fred: %d series; %d failures %s; substitutions %s; %d API requests",
             len(cat_df), len(failures), failures, substitutions, fred.n_requests)
    return cat_df


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="ignore raw cache")
    run(refresh=ap.parse_args().refresh)


if __name__ == "__main__":
    main()
