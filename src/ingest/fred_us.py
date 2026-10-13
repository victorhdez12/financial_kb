"""US macro/credit/liquidity extension from FRED -> curated/fred_us (docs/DATA_CONTRACT.md).

    .venv/bin/python -m src.ingest.fred_us            # incremental (reuse raw < 20h old)
    .venv/bin/python -m src.ingest.fred_us --refresh  # force re-download

Complements curated/fred (src/ingest/fred_extended.py) WITHOUT duplicating it: every series
already present in curated/fred/_catalog.csv is skipped, so series_id stays globally unique.

Two kinds of universe:
* EXPLICIT: hand-picked ids (labour market, Z.1 debt by sector, H.4.1, fiscal, profits, housing,
  inflation detail, Kim-Wright, money). Missing ids are logged and reported, not substituted.
* RELEASES: whole FRED releases (or filtered subsets) discovered with fred/release/series:
  H.15 (all non-annual), G.19, SLOOS, charge-off/delinquency, H.8 weekly SA all commercial
  banks, JOLTS national + industry rates, PMMS, Monthly Treasury Statement, OBFR, market value
  of US government debt, household debt service ratios.

Raw API responses go to $FIN_DATA_ROOT/raw/fred_us/ (<id>.series.json, <id>.observations.json).
Rate limit: <= 2 requests/second (Fred client from fred_extended). Key never logged.
"""
from __future__ import annotations

import argparse
import json
import logging
import re

import pandas as pd

from src.ingest.fred_extended import (CATALOG_COLS, Fred, FredError, catalog_row, data_root,
                                      fetch_series, obs_to_frame, write_parquet)

SOURCE = "fred_us"
log = logging.getLogger("fred_us")

# ------------------------------------------------------------------ explicit universe
EXPLICIT: dict[str, list[str]] = {
    "employment": [
        # alternative unemployment measures (U-1..U-5; U6RATE already in curated/fred)
        "U1RATE", "U2RATE", "U4RATE", "U5RATE", "U1RATENSA", "U2RATENSA", "U4RATENSA",
        "U5RATENSA", "U6RATENSA",
        # duration of unemployment
        "UEMPMEAN", "UEMPMED", "UEMPLT5", "UEMP5TO14", "UEMP15OV", "UEMP15T26", "UEMP27OV",
        "LNS13025703", "LNS13008636",
        # levels / participation / prime age
        "UNEMPLOY", "CLF16OV", "CE16OV", "LNS12300060", "LNS11300060", "LNS14000060",
        "LNS12032194", "LNS13023621", "LNS13023705",
        # payrolls by sector (CES, 1939+)
        "USPRIV", "USGOOD", "SRVPRD", "MANEMP", "DMANEMP", "NDMANEMP", "USCONS", "USMINE",
        "USTPU", "USTRADE", "USWTRADE", "USINFO", "USFIRE", "USPBS", "USEHS", "USLAH",
        "USSERV", "USGOVT", "CES9091000001", "CES9092000001", "CES9093000001", "TEMPHELPS",
        "PAYNSA",
        # hours & wages & labour cost
        "AHETPI", "AWHAETP", "AWHNONAG", "AWHAEMAN", "CES0500000011", "CES0500000008",
        "ECIALLCIV", "ECIWAG", "ECIBEN", "COMPNFB", "COMPRNFB", "OPHNFB", "ULCNFB", "PRS85006112",
        "FRBATLWGT3MMAUMHWGO", "FRBATLWGT12MMUMHGO",
        # claims
        "ICNSA", "IC4WSA", "CCNSA",
    ],
    "rates": [
        "EFFR", "IORB", "IOER", "IORR", "SOFR30DAYAVG", "SOFR90DAYAVG", "SOFR180DAYAVG",
        "SOFRINDEX", "RPONTSYD", "DPRIME", "PRIME",
        "DAAA", "DBAA",
        # Kim-Wright three-factor model (Fed Board), yields & term premia 1-10y
        *[f"THREEFYTP{i}" for i in range(1, 11)], *[f"THREEFY{i}" for i in range(1, 11)],
        *[f"THREEFF{i}" for i in (1, 2, 5, 10)],
        # breakevens / inflation compensation
        "T5YIFR", "T7YIEM", "T20YIEM", "T30YIEM", "T10YIEM", "T5YIEM",
    ],
    "credit": [
        # H.8 monthly long history (1947+)
        "LOANS", "REALLN", "INVEST", "USGSEC", "LOANINV", "OTHSEC",
        # Z.1 debt by sector (D.3), levels 1945+
        "TODNS", "CMDEBT", "TCMILBSHNO", "HHMSDODNS", "HCCSDODNS", "TBSDODNS", "BCNSDODNS",
        "TCMILBSNNCB", "TCMILBSNNB", "FGSDODNS", "FGTCMDODNS", "SLGSDODNS", "DODFS",
        "TCMDODFS", "DODFFSWCMI", "BOGZ1FL364104005Q", "GSETCMDODFS", "FICTCMDODFS",
        "MDOAH", "NCBCMDPMVCE", "BOGZ1FL104104006Q",
        # leverage ratios / debt-to-income
        "HDTGPDUSQ163N", "HNONWPDPI", "TNWBSHNO", "OEHRENWBSHNO", "BOGZ1FL192090005Q",
        "BOGZ1LM152090005Q",
        # margin debt / security credit (Z.1)
        "BOGZ1FL663067003Q",
    ],
    "liquidity": [
        # H.4.1 detail (2002+) and historical weekly (1914+)
        "WSHOSHO", "WSHOTSL", "WSHOMCB", "WSHOBL", "WSHONBNL", "WLRRAL", "WLRRAFOIAL",
        "WLRRAOL", "WCURCIR", "WORAL", "SWPT", "WLCFLPCL", "WDTGAL", "WLODLL", "WLFN",
        "LNCFRNC", "RAGGCTGFR", "LDGUST",
        "TOTRESNS", "BORROW", "RESBALNS", "EXCSRESNS", "NONBORRES",
    ],
    "money": ["M2REAL", "M2V", "M1V", "MBCURRCIR", "CURRCIR", "CURRSL", "DEMDEPSL", "SAVINGSL",
              "WM2NS", "WM1NS", "MMMFFAQ027S", "RMFSL"],
    "fiscal": [
        "FYFR", "FYONET", "FYFSD", "FYOINT", "GFDGDPA188S", "FYGFGDQ188S", "FDHBFIN", "FDHBFRBN",
        "FGRECPT", "FGEXPND", "FGDEF", "MTSDS133FMS", "FYFRGDA188S", "A091RC1A027NBEA",
        "GFDEBTN", "FGCCSAQ027S",
    ],
    "growth": [
        # potential output & income / consumption / production
        "GDPPOT", "NGDPPOT", "GDPDEF", "A939RX0Q048SBEA", "GDI", "A261RX1Q020SBEA",
        "PI", "DSPIC96", "PSAVERT", "W875RX1", "PCEC96", "CMRMTSPL", "RRSFS", "RSXFS",
        "IPMAN", "IPFINAL", "DGORDER", "NEWORDER", "AMTMNO", "BUSINV", "ISRATIO", "TOTALSA",
        "USSLIND", "GNP", "A191RP1Q027SBEA",
        # NIPA corporate profits
        "CP", "CPATAX", "A446RC1Q027SBEA", "A053RC1Q027SBEA", "NFCPATAX", "A464RC1Q027SBEA",
        "W273RE1A156NBEA", "A053RC1A027NBEA", "A055RC1A027NBEA", "DIVIDEND", "A466RD3Q052SBEA",
    ],
    "inflation": [
        "STICKCPIM157SFRBATL", "CORESTICKM159SFRBATL", "MEDCPIM158SFRBCLE",
        "TRMMEANCPIM158SFRBCLE", "PCETRIM12M159SFRBDAL", "CUSR0000SAH1", "CUSR0000SASLE",
        "CUSR0000SACL1E", "CPIENGSL", "CPIUFDSL", "CPILFENS", "PPIFIS", "WPSFD49207",
        "WPSFD4131", "EXPINF1YR", "EXPINF10YR", "MICH", "IR", "IQ", "DPCCRV1Q225SBEA",
        "CPIAUCSL",  # skipped automatically if already in curated/fred
    ],
    "housing": [
        "MSPUS", "ASPUS", "CSUSHPINSA", "USSTHPI", "HPIPONM226S", "HSN1F", "MSACSR", "HOUST1F",
        "COMPUTSA", "UNDCONTSA", "EXHOSLUSM495S", "RHORUSQ156N", "RRVRUSQ156N",
        "RHVRUSQ156N", "MORTGAGE15US", "MORTGAGE5US", "OBMMIJUMBO30YF", "OBMMIC30YF",
        "QUSR628BIS",
    ],
    "financial_conditions": ["STLFSI3", "DRSDCILM", "CPFF", "DCPF3M", "DCPN3M", "COMPOUT",
                              "RIFSPPFAAD90NB", "RIFSPPNAAD90NB"],
}

# Market / sentiment extension (2026-10-13, agent "mercado, credito y sentimiento"). None of these
# ids were in curated/fred or fred_us before. Run only these (merging into the existing catalog,
# no deletions) with:  .venv/bin/python -m src.ingest.fred_us --only-ext
EXT: dict[str, list[str]] = {
    "commodities": ["DCOILBRENTEU"],
    "fx": ["DTWEXAFEGS", "DTWEXEMEGS"],
    # CBOE vol indices on FRED (longer than the CBOE VIX3M file: VXV from 2007-12)
    "markets": ["VXVCLS", "VXNCLS", "RVXCLS", "OVXCLS", "GVZCLS", "VXEEMCLS", "VXDCLS"],
    "financial_conditions": ["USEPUINDXD", "USEPUINDXM"],
    "growth": [
        "CFNAIMA3",
        # Empire State (NY) manufacturing survey, SA diffusion indices
        "GACDISA066MSFRBNY", "GAFDISA066MSFRBNY", "NOCDISA066MSFRBNY", "NOFDISA066MSFRBNY",
        "PPCDISA066MSFRBNY", "PRCDISA066MSFRBNY", "NECDISA066MSFRBNY", "SHCDISA066MSFRBNY",
        "UOCDISA066MSFRBNY", "DTCDISA066MSFRBNY", "IVCDISA066MSFRBNY",
        # Philadelphia Fed manufacturing survey (1968+)
        "GACDFSA066MSFRBPHI", "GAFDFSA066MSFRBPHI", "NOCDFSA066MSFRBPHI", "NOFDFSA066MSFRBPHI",
        "PPCDFSA066MSFRBPHI", "PPFDFSA066MSFRBPHI", "PRCDFSA066MSFRBPHI", "NECDFSA066MSFRBPHI",
        "SHCDFSA066MSFRBPHI", "UOCDFSA066MSFRBPHI", "DTCDFSA066MSFRBPHI", "IVCDFSA066MSFRBPHI",
        # Dallas Fed Texas manufacturing (TMOS) and services (TSSOS) outlook surveys
        "BACTSAMFRBDAL", "FBACTSAMFRBDAL", "VNWOSAMFRBDAL", "PRMSAMFRBDAL", "PFGSAMFRBDAL",
        "NEMPSAMFRBDAL", "PRODSAMFRBDAL", "COLKSAMFRBDAL",
        "TSSOSBACTSAMFRBDAL", "TSSOSCOLKSAMFRBDAL", "TSSOSREVSAMFRBDAL",
    ],
    "employment": ["FRBKCLMCILA", "FRBKCLMCIM"],
    # H.6 money-fund assets (ICI-sourced): retail weekly NSA; institutional discontinued 2021-02
    "money": ["WRMFNS", "WIMFNS"],
}

# release_id -> (category, label, filter(meta)->bool)
RELEASES: dict[int, tuple[str, str, object]] = {
    18: ("rates", "H.15 Selected Interest Rates (non-annual)",
         lambda s: s["frequency_short"] != "A"),
    14: ("credit", "G.19 Consumer Credit", lambda s: True),
    191: ("credit", "Senior Loan Officer Opinion Survey (SLOOS)", lambda s: True),
    231: ("credit", "Charge-off and delinquency rates, commercial banks", lambda s: True),
    22: ("credit", "H.8 weekly SA, all commercial banks",
         lambda s: s["frequency_short"] == "W" and s["seasonal_adjustment_short"] == "SA"
         and "All Commercial Banks" in s["title"]),
    192: ("employment", "JOLTS national total + industry openings/quits rates",
          lambda s: s["seasonal_adjustment_short"] == "SA" and (
              re.fullmatch(r"JTS(HI|JO|LD|OS|QU|TS)[LR]", s["id"]) is not None
              or re.fullmatch(r"JTS\d{4,6}(JOR|QUR)", s["id"]) is not None)),
    190: ("housing", "Freddie Mac PMMS", lambda s: True),
    363: ("fiscal", "Monthly Treasury Statement", lambda s: True),
    383: ("fiscal", "Market value of US government debt", lambda s: True),
    375: ("rates", "Overnight Bank Funding Rate", lambda s: True),
    89: ("credit", "Household debt service ratios", lambda s: True),
}


def discover_release(fred: Fred, rid: int) -> list[dict]:
    out, off = [], 0
    while True:
        j = fred.get("release/series", release_id=rid, limit=1000, offset=off)
        out += j["seriess"]
        off += 1000
        if off >= int(j["count"]):
            return out


SENTINELS = (9999.0, -9999.0, 99999.0, -99999.0)


def drop_sentinels(v: pd.Series) -> pd.Series:
    """Some old FRED/Fed series encode 'not available' as 9999 (e.g. H1RIFSPABM03NWF,
    DALLCCACBEP). Treat those as NaN unless the series genuinely lives at that magnitude."""
    hit = v.isin(SENTINELS)
    if hit.any() and v[~hit].abs().median() < 1000:
        return v.mask(hit)
    return v


def run_ext(fred, root, raw, out, existing, refresh) -> pd.DataFrame:
    """Fetch only EXT ids and merge them into the existing curated/fred_us catalog."""
    cat_path = out / "_catalog.csv"
    cur = pd.read_csv(cat_path) if cat_path.exists() else pd.DataFrame(columns=CATALOG_COLS)
    rows, failures = {}, []
    for cat, ids in EXT.items():
        for sid in ids:
            if sid in existing:
                log.warning("%s already in curated/fred: skipped", sid)
                continue
            try:
                m, obs = fetch_series(fred, sid, raw, refresh, None)
            except FredError as e:
                log.warning("%s: %s", sid, e)
                failures.append(sid)
                continue
            df = obs_to_frame(obs, sid)
            df["value"] = drop_sentinels(df["value"])
            df["source"] = SOURCE
            if df["value"].notna().sum() == 0:
                failures.append(sid)
                continue
            write_parquet(out / f"{sid}.parquet", df)
            r = catalog_row(sid, m, df, cat, "US", sid, "", "origin: FRED API (market/sentiment extension)")
            r["source"] = SOURCE
            rows[sid] = r
    new = pd.DataFrame(list(rows.values()), columns=CATALOG_COLS)
    cat_df = pd.concat([cur[~cur["series_id"].isin(new["series_id"])], new]).sort_values("series_id")
    cat_df.to_csv(cat_path, index=False)
    log.info("fred_us ext: %d series written/updated; failures %s; catalog now %d", len(new), failures, len(cat_df))
    return cat_df


def run(refresh: bool = False, only_ext: bool = False) -> pd.DataFrame:
    root = data_root()
    raw = root / "raw" / SOURCE
    out = root / "curated" / SOURCE
    raw.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    existing = set()
    p = root / "curated" / "fred" / "_catalog.csv"
    if p.exists():
        existing = set(pd.read_csv(p, usecols=["series_id"])["series_id"])

    fred = Fred()
    todo: dict[str, tuple[str, str, dict | None]] = {}  # sid -> (category, origin note, meta)
    if only_ext:
        return run_ext(fred, root, raw, out, existing, refresh)
    for cat, ids in EXPLICIT.items():
        for sid in ids:
            todo.setdefault(sid, (cat, "explicit list", None))
    for cat, ids in EXT.items():
        for sid in ids:
            todo.setdefault(sid, (cat, "explicit list (market/sentiment extension)", None))
    for rid, (cat, label, filt) in RELEASES.items():
        metas = [m for m in discover_release(fred, rid) if filt(m)]
        log.info("release %d (%s): %d series selected", rid, label, len(metas))
        for m in metas:
            if m["id"] not in todo:
                todo[m["id"]] = (cat, f"FRED release {rid}: {label}", m)

    rows, failures, skipped = {}, [], []
    for i, (sid, (cat, origin, meta)) in enumerate(todo.items()):
        if sid in existing:
            skipped.append(sid)
            continue
        try:
            m, obs = fetch_series(fred, sid, raw, refresh, meta)
        except FredError as e:
            log.warning("%s: %s", sid, e)
            failures.append(sid)
            continue
        if not obs:
            failures.append(sid)
            continue
        df = obs_to_frame(obs, sid)
        df["value"] = drop_sentinels(df["value"])
        df["source"] = SOURCE
        if df["value"].notna().sum() == 0:
            failures.append(sid)
            continue
        write_parquet(out / f"{sid}.parquet", df)
        r = catalog_row(sid, m, df, cat, "US", sid, "", f"origin: FRED API ({origin})")
        r["source"] = SOURCE
        rows[sid] = r
        if i % 100 == 0:
            log.info("%d / %d", i, len(todo))

    cat_df = pd.DataFrame(list(rows.values()), columns=CATALOG_COLS).sort_values("series_id")
    keep = set(cat_df["series_id"])
    for f in out.glob("*.parquet"):
        if f.stem not in keep:
            f.unlink()
    cat_df.to_csv(out / "_catalog.csv", index=False)
    (raw / "_run_summary.json").write_text(json.dumps({
        "run_utc": pd.Timestamp.now("UTC").isoformat(), "n_series": len(cat_df),
        "failures": failures, "skipped_already_in_curated_fred": skipped,
        "requests": fred.n_requests}, indent=2))
    log.info("curated/fred_us: %d series; %d failures %s; %d skipped (in curated/fred)",
             len(cat_df), len(failures), failures, len(skipped))
    return cat_df


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="ignore raw cache")
    ap.add_argument("--only-ext", action="store_true",
                    help="fetch only the market/sentiment extension (EXT) and merge into the catalog")
    a = ap.parse_args()
    run(refresh=a.refresh, only_ext=a.only_ext)


if __name__ == "__main__":
    main()
