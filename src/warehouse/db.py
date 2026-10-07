"""Shared paths and read helpers for the DuckDB warehouse."""
from __future__ import annotations

import os
import re
from pathlib import Path

import duckdb
import pandas as pd
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
load_dotenv(REPO / ".env")

DATA_ROOT = Path(os.path.expanduser(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")))
WAREHOUSE = REPO / "data" / "warehouse.duckdb"


def connect(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(WAREHOUSE), read_only=read_only)


def has_table(con, name: str) -> bool:
    q = "select count(*) from information_schema.tables where table_name = ?"
    return con.execute(q, [name]).fetchone()[0] > 0


def series(con, series_id: str) -> pd.Series:
    """Latest-vintage observations of one series (deduplicated by `obs_latest`), indexed by date."""
    df = con.execute(
        "select date, value from obs_latest where series_id = ? and value is not null order by date",
        [series_id],
    ).df()
    if df.empty:
        return pd.Series(dtype=float, name=series_id)
    s = pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["date"]), name=series_id)
    return s[~s.index.duplicated(keep="last")]


def first_available(con, candidates: list[str]) -> tuple[str | None, pd.Series]:
    """Return the first candidate series id that has data."""
    for sid in candidates:
        s = series(con, sid)
        if not s.empty:
            return sid, s
    return None, pd.Series(dtype=float)


def all_series_ids(con) -> list[str]:
    return [r[0] for r in con.execute("select distinct series_id from obs_latest").fetchall()]


def find_series(con, patterns: list[str]) -> str | None:
    """First series id matching any regex (case-insensitive), in pattern priority order."""
    ids = sorted(all_series_ids(con))
    for pat in patterns:
        rx = re.compile(pat, re.I)
        hits = [i for i in ids if rx.search(i)]
        if hits:
            return hits[0]
    return None


def vintages(con, base_id: str) -> pd.DataFrame:
    """ALFRED vintage rows for `base_id` (any series_id containing it as a token), or empty.

    NaN rows are kept on purpose: in ALFRED a NaN vintage means the observation was dropped from
    the series at that release (e.g. rebasing); it must close the previous value's validity."""
    if not has_table(con, "observations"):
        return pd.DataFrame()
    df = con.execute(
        """select series_id, date, value, realtime_start from observations
           where realtime_start is not null
             and regexp_matches(upper(series_id), ?)""",
        [rf"(^|_){base_id.upper()}($|_)"],
    ).df()
    if df.empty:
        return df
    # if several ids match (e.g. GDPC1 and alfred_GDPC1) keep the one with most rows
    best = df["series_id"].value_counts().idxmax()
    df = df[df["series_id"] == best].copy()
    df["date"] = pd.to_datetime(df["date"])
    df["realtime_start"] = pd.to_datetime(df["realtime_start"])
    return df[["date", "value", "realtime_start"]]
