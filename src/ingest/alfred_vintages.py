"""ALFRED vintages (real-time history) -> curated/alfred (docs/DATA_CONTRACT.md).

    .venv/bin/python -m src.ingest.alfred_vintages            # download/refresh all
    .venv/bin/python -m src.ingest.alfred_vintages --refresh

Uses fred/series/observations with realtime_start=1776-07-04, realtime_end=9999-12-31
(output_type=1, "observations by real-time period"): each row is a (date, value) pair valid
over [realtime_start, realtime_end]. Results are paginated (limit 100000 + offset).

Long format parquet: date, value, realtime_start, realtime_end, series_id, source='alfred'.
realtime_end is NULL for the currently valid value (API returns 9999-12-31).

Helper:
    from src.ingest.alfred_vintages import as_of
    as_of("GDPC1", "2008-10-15")   # GDPC1 as it was known on 2008-10-15
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import date
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.ingest.fred_extended import LICENSE, Fred, data_root

SOURCE = "alfred"
SERIES = ["GDPC1", "PAYEMS", "CPIAUCSL", "INDPRO", "UNRATE", "PCEPILFE", "CPILFESL"]
CATEGORY = {"GDPC1": "growth", "INDPRO": "growth", "PAYEMS": "employment",
            "UNRATE": "employment", "CPIAUCSL": "inflation", "PCEPILFE": "inflation",
            "CPILFESL": "inflation"}
SCHEMA = pa.schema([("date", pa.date32()), ("value", pa.float64()),
                    ("realtime_start", pa.date32()), ("realtime_end", pa.date32()),
                    ("series_id", pa.string()), ("source", pa.string())])
CATALOG_COLS = ["series_id", "source", "name", "category", "frequency", "units", "country",
                "start", "end", "transform_notes", "url", "license",
                "n_rows", "n_vintages", "first_vintage", "last_vintage"]

log = logging.getLogger("alfred_vintages")


def curated_dir() -> Path:
    return data_root() / "curated" / SOURCE


def download(fred: Fred, sid: str, raw: Path, refresh: bool) -> tuple[dict, list[dict]]:
    p_obs, p_meta = raw / f"{sid}.vintages.json", raw / f"{sid}.series.json"
    if p_obs.exists() and p_meta.exists() and not refresh and \
            time.time() - p_obs.stat().st_mtime < 20 * 3600:
        return json.loads(p_meta.read_text())["seriess"][0], json.loads(p_obs.read_text())["observations"]
    meta = fred.get("series", series_id=sid)
    obs, offset, count = [], 0, None
    while count is None or offset < count:
        j = fred.get("series/observations", series_id=sid, realtime_start="1776-07-04",
                     realtime_end="9999-12-31", limit=100000, offset=offset)
        count = int(j["count"])
        if not j["observations"]:
            break
        obs += j["observations"]
        offset = len(obs)
        log.info("%s: %d / %d rows", sid, offset, count)
    p_meta.write_text(json.dumps(meta))
    p_obs.write_text(json.dumps({"count": count, "observations": obs}))
    return meta["seriess"][0], obs


def normalise(obs: list[dict], sid: str) -> pd.DataFrame:
    df = pd.DataFrame(obs)
    out = pd.DataFrame({
        "date": pd.to_datetime(df["date"]).dt.date,
        "value": pd.to_numeric(df["value"].replace(".", None), errors="coerce").astype("float64"),
        "realtime_start": pd.to_datetime(df["realtime_start"]).dt.date,
        "realtime_end": [None if e.startswith("9999") else date.fromisoformat(e)
                         for e in df["realtime_end"]],
        "series_id": sid, "source": SOURCE,
    })
    return out.sort_values(["date", "realtime_start"]).reset_index(drop=True)


def run(refresh: bool = False) -> pd.DataFrame:
    raw = data_root() / "raw" / SOURCE
    out = curated_dir()
    raw.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    fred = Fred()
    rows = []
    for sid in SERIES:
        meta, obs = download(fred, sid, raw, refresh)
        df = normalise(obs, sid)
        tbl = pa.Table.from_pandas(df, schema=SCHEMA, preserve_index=False)
        pq.write_table(tbl, out / f"{sid}.parquet")
        v = df.dropna(subset=["value"])
        rows.append({
            "series_id": sid, "source": SOURCE, "name": meta["title"] + " (all vintages)",
            "category": CATEGORY[sid], "frequency": meta["frequency_short"][:1],
            "units": meta["units"], "country": "US",
            "start": str(v["date"].min()), "end": str(v["date"].max()),
            "transform_notes": ("ALFRED output_type=1, realtime 1776-07-04..9999-12-31; long format;"
                                " realtime_end NULL = still current; '.' -> NaN; use as_of()"),
            "url": f"https://alfred.stlouisfed.org/series?seid={sid}", "license": LICENSE,
            "n_rows": len(df), "n_vintages": df["realtime_start"].nunique(),
            "first_vintage": str(df["realtime_start"].min()),
            "last_vintage": str(df["realtime_start"].max()),
        })
        log.info("%s: %d rows, %d vintages, %s..%s", sid, len(df), rows[-1]["n_vintages"],
                 rows[-1]["first_vintage"], rows[-1]["last_vintage"])
    cat = pd.DataFrame(rows, columns=CATALOG_COLS)
    cat.to_csv(out / "_catalog.csv", index=False)
    return cat


# --------------------------------------------------------------------------------------
_CACHE: dict[str, pd.DataFrame] = {}


def load_vintages(series_id: str) -> pd.DataFrame:
    if series_id not in _CACHE:
        df = pd.read_parquet(curated_dir() / f"{series_id}.parquet")
        for c in ("date", "realtime_start", "realtime_end"):
            df[c] = pd.to_datetime(df[c])
        _CACHE[series_id] = df
    return _CACHE[series_id]


def as_of(series_id: str, asof_date) -> pd.Series:
    """Series as it was known on `asof_date` (point-in-time).

    Keeps rows with realtime_start <= asof < realtime_end (NULL end = still valid) and returns
    a float Series indexed by observation date. Observations not yet published at asof_date
    are absent. Before the first available vintage the result is empty.
    """
    df = load_vintages(series_id)
    t = pd.Timestamp(asof_date)
    m = (df["realtime_start"] <= t) & (df["realtime_end"].isna() | (df["realtime_end"] >= t))
    # realtime_end is inclusive in ALFRED (last day the value was valid)
    s = df.loc[m].sort_values(["date", "realtime_start"]).drop_duplicates("date", keep="last")
    return s.set_index("date")["value"].rename(series_id).dropna()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    run(refresh=ap.parse_args().refresh)


if __name__ == "__main__":
    main()
