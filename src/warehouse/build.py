"""Build data/warehouse.duckdb from the legacy CSVs and the curated parquet layer.

Idempotent: the database file is rebuilt from scratch on every run. Whatever exists under
$FIN_DATA_ROOT/curated/*/*.parquet and $FIN_DATA_ROOT/events/*.parquet at run time is loaded
(glob), so new sources written by the ingest scripts are picked up automatically.

Tables
  observations(date, value, series_id, source, realtime_start)   all rows, incl. ALFRED vintages
  catalog(series_id, source, name, category, frequency, units, country, start, "end", ...)
  events(event_id, name, type, country, start_date, end_date, severity, source, url, notes, dataset)
Views
  obs_latest   one value per (series_id, date), vintages excluded; curated sources win over legacy
  monthly      last observation of each calendar month per series (long format; PIVOT-able)
  vintages     ALFRED rows only (realtime_start not null)
  series_summary  coverage per series

Run: .venv/bin/python -m src.warehouse.build
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import duckdb
import pandas as pd

from src.warehouse.db import DATA_ROOT, WAREHOUSE

OBS_COLS = ["date", "value", "series_id", "source", "realtime_start"]
CATALOG_COLS = ["series_id", "source", "name", "category", "frequency", "units", "country",
                "start", "end", "transform_notes", "url", "license"]
EVENT_COLS = ["event_id", "name", "type", "country", "start_date", "end_date", "severity",
              "source", "url", "notes"]


# ---------------------------------------------------------------- legacy CSVs
def load_legacy_csv(path: Path, source: str, prefix: str = "") -> pd.DataFrame:
    df = pd.read_csv(path, usecols=lambda c: c in {"date", "value", "series_id"})
    df["series_id"] = prefix + df.get("series_id", pd.Series(path.stem, index=df.index)).astype(str)
    df["source"] = source
    df["realtime_start"] = pd.NaT
    return df


def legacy_catalog_row(meta_path: Path, csv_path: Path, category: str | None) -> dict:
    row = {"series_id": csv_path.stem, "source": "fred_legacy", "category": category,
           "country": "USA", "license": "FRED terms of use",
           "url": f"https://fred.stlouisfed.org/series/{csv_path.stem}"}
    if meta_path.exists():
        s = json.loads(meta_path.read_text())["seriess"][0]
        row.update(name=s.get("title"), frequency=s.get("frequency_short"), units=s.get("units"),
                   start=s.get("observation_start"), end=s.get("observation_end"))
    return row


def legacy_frames() -> tuple[list[pd.DataFrame], list[dict]]:
    frames, cat = [], []
    for p in sorted((DATA_ROOT / "macro" / "fred").glob("*.csv")):
        df = load_legacy_csv(p, "fred_legacy")
        frames.append(df)
        category = pd.read_csv(p, nrows=1).get("category", pd.Series([None])).iloc[0]
        cat.append(legacy_catalog_row(p.with_suffix(".metadata.json"), p, category))
    for p in sorted((DATA_ROOT / "macro" / "bls").glob("*.csv")):
        frames.append(load_legacy_csv(p, "bls_legacy", prefix="bls_"))
        desc = pd.read_csv(p, nrows=1).get("description", pd.Series([None])).iloc[0]
        cat.append({"series_id": "bls_" + p.stem, "source": "bls_legacy", "name": desc,
                    "frequency": "M", "country": "USA", "license": "BLS public domain"})
    return frames, cat


# ---------------------------------------------------------------- curated parquet
def normalize_curated(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    out = pd.DataFrame({"date": pd.to_datetime(df["date"], errors="coerce"),
                        "value": pd.to_numeric(df["value"], errors="coerce")})
    out["series_id"] = df["series_id"].astype(str) if "series_id" in df else path.stem
    out["source"] = df["source"].astype(str) if "source" in df else path.parent.name
    out["realtime_start"] = (pd.to_datetime(df["realtime_start"], errors="coerce")
                             if "realtime_start" in df else pd.NaT)
    return out.dropna(subset=["date"])


def curated_frames() -> tuple[list[pd.DataFrame], list[pd.DataFrame], list[str]]:
    frames, cats, errors = [], [], []
    root = DATA_ROOT / "curated"
    for p in sorted(root.glob("*/*.parquet")):
        if p.name.startswith("_"):
            continue
        try:
            df = pd.read_parquet(p)
            if {"date", "value"} <= set(df.columns):
                frames.append(normalize_curated(df, p))
            else:
                errors.append(f"{p}: missing date/value columns")
        except Exception as exc:  # a half-written file from a concurrent ingest must not break the build
            errors.append(f"{p}: {exc}")
    for c in sorted(root.glob("*/_catalog.csv")):
        try:
            cdf = pd.read_csv(c)
            cdf = cdf.reindex(columns=CATALOG_COLS)
            cdf["source"] = cdf["source"].fillna(c.parent.name)
            cats.append(cdf)
        except Exception as exc:
            errors.append(f"{c}: {exc}")
    return frames, cats, errors


def event_frames() -> tuple[list[pd.DataFrame], list[str]]:
    frames, errors = [], []
    for p in sorted((DATA_ROOT / "events").glob("*.parquet")):
        try:
            df = pd.read_parquet(p).reindex(columns=EVENT_COLS)
            df["dataset"] = p.stem
            for c in ("start_date", "end_date"):
                df[c] = pd.to_datetime(df[c], errors="coerce")
            for c in ("event_id", "name", "type", "country", "severity", "source", "url", "notes"):
                df[c] = df[c].astype("string")
            frames.append(df)
        except Exception as exc:
            errors.append(f"{p}: {exc}")
    return frames, errors


# ---------------------------------------------------------------- build
VIEWS_SQL = """
create or replace view obs_latest as
select date, value, series_id, source from (
  select *, row_number() over (
     partition by series_id, date
     order by case when source like '%legacy' then 2 else 1 end, source) as rk
  from observations where realtime_start is null
) where rk = 1;

create or replace view vintages as
select * from observations where realtime_start is not null;

create or replace view monthly as
select series_id,
       date_trunc('month', date)::date as month,
       arg_max(value, date) as value,
       max(date) as last_obs_date
from obs_latest where value is not null
group by series_id, date_trunc('month', date);

create or replace view series_summary as
select series_id, any_value(source) as source, count(*) as n_obs,
       min(date) as first_date, max(date) as last_date,
       arg_max(value, date) as last_value
from obs_latest group by series_id;
"""


def write_tables(con, obs: pd.DataFrame, catalog: pd.DataFrame, events: pd.DataFrame) -> None:
    con.register("obs_df", obs)
    con.execute("""create table observations as
                   select cast(date as date) as date, cast(value as double) as value,
                          cast(series_id as varchar) as series_id, cast(source as varchar) as source,
                          cast(realtime_start as date) as realtime_start from obs_df""")
    con.register("cat_df", catalog)
    con.execute("create table catalog as select * from cat_df")
    if events.empty:
        con.execute("""create table events (event_id varchar, name varchar, type varchar, country varchar,
                       start_date date, end_date date, severity varchar, source varchar, url varchar,
                       notes varchar, dataset varchar)""")
    else:
        con.register("ev_df", events)
        con.execute("""create table events as select event_id, name, type, country,
                       cast(start_date as date) as start_date, cast(end_date as date) as end_date,
                       severity, source, url, notes, dataset from ev_df""")
    con.execute(VIEWS_SQL)
    con.execute("create table build_log as select current_timestamp as built_at")


def build() -> None:
    t0 = time.time()
    leg, leg_cat = legacy_frames()
    cur, cur_cat, errors = curated_frames()
    evs, ev_err = event_frames()
    errors += ev_err

    obs = pd.concat([f[OBS_COLS] for f in leg + cur], ignore_index=True)
    catalog = pd.concat([pd.DataFrame(leg_cat).reindex(columns=CATALOG_COLS)] + cur_cat, ignore_index=True)
    catalog = catalog.astype("string")
    events = pd.concat(evs, ignore_index=True) if evs else pd.DataFrame()

    WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    tmp = WAREHOUSE.with_suffix(".tmp.duckdb")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    write_tables(con, obs, catalog, events)
    n_series = con.execute("select count(distinct series_id) from observations").fetchone()[0]
    n_vint = con.execute("select count(*) from vintages").fetchone()[0]
    con.close()
    tmp.replace(WAREHOUSE)  # atomic swap: readers never see a half-built DB

    print(f"warehouse: {len(obs):,} rows, {n_series} series ({len(cur)} curated files), "
          f"{n_vint:,} vintage rows, {len(events)} events -> {WAREHOUSE} [{time.time()-t0:.1f}s]")
    for e in errors:
        print("  WARN", e)


if __name__ == "__main__":
    build()
