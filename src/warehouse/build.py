"""Build data/warehouse.duckdb from the legacy CSVs and the curated parquet layer.

Idempotent: the database file is rebuilt from scratch on every run. Whatever exists under
$FIN_DATA_ROOT/curated/*/*.parquet and $FIN_DATA_ROOT/events/*.parquet at run time is loaded
(glob), so new sources written by the ingest scripts are picked up automatically.

Tables
  observations(date, value, series_id, source, realtime_start, realtime_end)  all rows, incl. ALFRED vintages
  catalog(series_id, source, name, category, frequency, units, country, start, "end", ...,
          country_iso3, pit_role)   one row per series_id (see dedupe_catalog / PIT_RULES)
  events(event_id, name, type, country, start_date, end_date, severity, source, url, notes, dataset)
Views
  obs_latest   one value per (series_id, date), vintages excluded; curated sources win over legacy;
               only pit_role='observed' series and no dates after the build date
  forecasts    pit_role in ('forecast', 'lookahead'): never use as predictors at their own date
  monthly      table: last observation of each calendar month per series (long format; PIVOT-able)
  vintages     ALFRED rows only (realtime_start not null)
  series_summary  coverage per series

Run: .venv/bin/python -m src.warehouse.build
"""
from __future__ import annotations

import json
import re
import time
from functools import lru_cache
from pathlib import Path

import duckdb
import pandas as pd
import pycountry

from src.warehouse.db import DATA_ROOT, WAREHOUSE

OBS_COLS = ["date", "value", "series_id", "source", "realtime_start", "realtime_end"]
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
    df["realtime_end"] = pd.NaT
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
    for c in ("realtime_start", "realtime_end"):
        out[c] = pd.to_datetime(df[c], errors="coerce") if c in df else pd.NaT
    out = out.dropna(subset=["date"])
    return fiscal_year_to_jan1(out)


def fiscal_year_to_jan1(df: pd.DataFrame) -> pd.DataFrame:
    """Annual series dated at a non-January day (e.g. FRED fiscal-year data on 06-30 before 1977
    and 09-30 after) -> January 1st of the same year, as the contract requires. Only touches
    single-series annual frames, and only if that leaves one observation per year."""
    if df.empty or df["series_id"].nunique() != 1 or df["realtime_start"].notna().any():
        return df
    d = df["date"]
    if len(d) < 3 or (d.dt.month.eq(1) & d.dt.day.eq(1)).all():
        return df
    yearly = d.sort_values().diff().dt.days.median() >= 360
    if yearly and d.dt.year.is_unique:
        df = df.copy()
        df["date"] = d.dt.to_period("Y").dt.start_time
    return df


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


# ---------------------------------------------------------------- catalog metadata
# point-in-time role of a series: 'observed' (safe as predictor at its date), 'forecast'
# (projections; future dates), 'lookahead' (value at t uses information after t)
PIT_RULES: list[tuple[str, str]] = [
    (r"_proj$", "forecast"),          # IMF WEO projections
    (r"^NROU$", "forecast"),          # CBO natural rate, projected ~10 years ahead
    (r"^shiller_fwd10y_", "lookahead"),  # realised forward 10y returns
    (r"^nyfed_recprob_target$", "lookahead"),  # dated at the target month, not the forecast date
]
AGGREGATES = {"EA": "EA", "EA19": "EA", "EA20": "EA", "EA21": "EA", "EU": "EU", "EU27": "EU",
              "U2": "EA", "I9": "EA", "EURO AREA": "EA", "WORLD": "WLD", "WLD": "WLD",
              "UK": "GBR", "EL": "GRC", "KOSOVO": "XKX", "KOREA": "KOR",
              # multi-country groups keep a stable code so they can still be filtered
              "G7": "G7", "G20": "G20", "OECD": "OECD", "EM": "EM", "ADV": "ADV", "EMDE": "EMDE",
              # factor regions (ken_french_intl, aqr, jkp); NAMER, not NAM (= Namibia)
              "WLDXUS": "WLDXUS", "DEV": "DEV", "DEVXUS": "DEVXUS", "EUR": "EUR", "NAMER": "NAMER",
              "APXJ": "APXJ", "PAC": "PAC"}


def pit_role(series_id: str, transform_notes: object = None) -> str:
    if isinstance(transform_notes, str) and transform_notes.startswith("FORECAST"):
        return "forecast"
    for rx, role in PIT_RULES:
        if re.search(rx, series_id):
            return role
    return "observed"


@lru_cache(maxsize=None)
def to_iso3(country: object) -> object:
    """Normalise mixed country labels (ISO3, ISO2, English names) to ISO3; aggregates to EA/EU/WLD.
    Unknown labels (regions, BIS groups) return None and keep their original `country`."""
    if not isinstance(country, str) or not country.strip():
        return None
    c = country.strip()
    if c.upper() in AGGREGATES:
        return AGGREGATES[c.upper()]
    try:
        if len(c) == 3 and c.isalpha():
            return pycountry.countries.get(alpha_3=c.upper()).alpha_3
        if len(c) == 2 and c.isalpha():
            return pycountry.countries.get(alpha_2=c.upper()).alpha_3
        return pycountry.countries.lookup(c).alpha_3
    except (LookupError, AttributeError):
        pass
    try:
        hits = pycountry.countries.search_fuzzy(c)
        return hits[0].alpha_3 if len(hits) == 1 else None
    except LookupError:
        return None


def dedupe_catalog(catalog: pd.DataFrame) -> pd.DataFrame:
    """One row per series_id: curated source > alfred (vintage-only twin) > legacy CSV."""
    src = catalog["source"].fillna("")
    rank = src.str.endswith("legacy").astype(int) * 2 + src.eq("alfred").astype(int)
    out = catalog.assign(_rk=rank).sort_values(["series_id", "_rk"], kind="stable")
    return out.drop_duplicates("series_id").drop(columns="_rk").reset_index(drop=True)


def enrich_catalog(catalog: pd.DataFrame) -> pd.DataFrame:
    catalog = dedupe_catalog(catalog)
    catalog["country_iso3"] = catalog["country"].map(to_iso3)
    catalog["pit_role"] = [pit_role(s, n) for s, n in zip(catalog["series_id"], catalog["transform_notes"])]
    return catalog


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
create or replace view obs_all_latest as
select date, value, series_id, source from (
  select *, row_number() over (
     partition by series_id, date
     order by case when source like '%legacy' then 2 else 1 end, source) as rk
  from observations where realtime_start is null
) where rk = 1;

create or replace view obs_latest as
select o.* from obs_all_latest o
left join catalog c using (series_id)
where coalesce(c.pit_role, 'observed') = 'observed'
  and o.date <= (select cast(built_at as date) from build_log);

create or replace view forecasts as
select o.*, c.pit_role from obs_all_latest o
join catalog c using (series_id)
where c.pit_role in ('forecast', 'lookahead');

create or replace view vintages as
select * from observations where realtime_start is not null;

create table monthly as
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
                          cast(realtime_start as date) as realtime_start,
                          cast(realtime_end as date) as realtime_end from obs_df""")
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
    con.execute("create table build_log as select current_timestamp as built_at")
    con.execute(VIEWS_SQL)


def build() -> None:
    t0 = time.time()
    leg, leg_cat = legacy_frames()
    cur, cur_cat, errors = curated_frames()
    evs, ev_err = event_frames()
    errors += ev_err

    obs = pd.concat([f[OBS_COLS] for f in leg + cur], ignore_index=True)
    catalog = pd.concat([pd.DataFrame(leg_cat).reindex(columns=CATALOG_COLS)] + cur_cat, ignore_index=True)
    catalog = enrich_catalog(catalog).astype("string")
    events = pd.concat(evs, ignore_index=True) if evs else pd.DataFrame()

    WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    tmp = WAREHOUSE.with_suffix(".tmp.duckdb")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    write_tables(con, obs, catalog, events)
    n_series = con.execute("select count(distinct series_id) from observations").fetchone()[0]
    n_vint = con.execute("select count(*) from vintages").fetchone()[0]
    roles = dict(con.execute("select pit_role, count(*) from catalog group by 1").fetchall())
    con.close()
    tmp.replace(WAREHOUSE)  # atomic swap: readers never see a half-built DB

    print(f"warehouse: {len(obs):,} rows, {n_series} series ({len(cur)} curated files), "
          f"{n_vint:,} vintage rows, {len(events)} events -> {WAREHOUSE} [{time.time()-t0:.1f}s]")
    print(f"  catalog: {len(catalog)} series, pit_role {roles}")
    for e in errors:
        print("  WARN", e)


if __name__ == "__main__":
    build()
