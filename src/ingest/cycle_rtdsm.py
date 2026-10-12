"""Philadelphia Fed Real-Time Data Set for Macroeconomists (RTDSM): full vintage matrices
from 1964/65 (complements ALFRED, whose vintages mostly start in 1991).

source_id = rtdsm. Output follows the ALFRED layout (long format, only changes kept):
  date, value, realtime_start, realtime_end, series_id, source
realtime_start: RTDSM vintages describe data available in the MIDDLE of the vintage period:
  monthly vintage YYMn -> 15th of that month; quarterly vintage YYQn -> 15th of the middle
  month of the quarter (Philly Fed convention). realtime_end = day before the next change
  (NULL = still current).
Also writes first/second/third/most-recent release series (ordinary time series).

Run: .venv/bin/python -m src.ingest.cycle_rtdsm [--refresh]
"""
from __future__ import annotations

import re
import sys
import warnings

import numpy as np
import pandas as pd

from ._extlong_common import CATALOG_COLS, curated_dir, download, log, raw_dir

warnings.filterwarnings("ignore", category=UserWarning)

SRC = "rtdsm"
BASE = "https://www.philadelphiafed.org/-/media/FRBP/Assets/Surveys-And-Data/real-time-data/data-files/xlsx"
PAGE = "https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/real-time-data-set-for-macroeconomists"
LIC = "Federal Reserve Bank of Philadelphia RTDSM, public data; cite Croushore & Stark (2001)"

# file -> (series_id, name, category, freq, units)
VINTAGES = {
    "routputMvQd.xlsx": ("rtdsm_routput", "Real GNP/GDP, all monthly vintages", "growth", "Q",
                         "billions of real $ (base year of each vintage)"),
    "pMvQd.xlsx": ("rtdsm_p", "GNP/GDP price index, all monthly vintages", "inflation", "Q",
                   "index (base year of each vintage)"),
    "rucQvMd.xlsx": ("rtdsm_ruc", "Civilian unemployment rate, quarterly vintages of monthly data",
                     "employment", "M", "percent"),
    "employMvMd.xlsx": ("rtdsm_employ", "Nonfarm payroll employment, all monthly vintages", "employment",
                        "M", "thousands"),
}
RELEASES = {
    "routput_first_second_third.xlsx": ("rtdsm_routput", "Real GDP growth", "growth", "Q",
                                        "% q/q annualized"),
    "p_first_second_third.xlsx": ("rtdsm_p", "GDP price index inflation", "inflation", "Q",
                                  "% q/q annualized"),
    "employ_level_first_second_third.xlsx": ("rtdsm_employ_chg", "Nonfarm payroll change", "employment",
                                             "M", "thousands m/m change"),
}
EXTRA_RAW = ["ROUTPUTQvQd.xlsx", "PQvQd.xlsx"]


def _vintage_date(col: str) -> pd.Timestamp:
    m = re.search(r"(\d{2})([MQ])(\d{1,2})$", col)
    yy, kind, n = int(m.group(1)), m.group(2), int(m.group(3))
    year = 1900 + yy if yy >= 60 else 2000 + yy
    month = n if kind == "M" else 3 * (n - 1) + 2
    return pd.Timestamp(year, month, 15)


def _obs_date(s: str) -> pd.Timestamp:
    s = str(s).strip()
    if ":Q" in s:
        y, q = s.split(":Q")
        return pd.Timestamp(int(y), 3 * (int(q) - 1) + 1, 1)
    y, m = s.split(":")
    return pd.Timestamp(int(y), int(m), 1)


def _to_long(mat: pd.DataFrame, sid: str) -> pd.DataFrame:
    mat = mat.copy()
    mat.index = [_obs_date(x) for x in mat.iloc[:, 0]]
    mat = mat.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")
    vdates = [_vintage_date(c) for c in mat.columns]
    mat.columns = vdates
    mat = mat.sort_index(axis=1)
    rows = []
    vd = np.array(mat.columns)
    for obs, r in mat.iterrows():
        vals = r.to_numpy(dtype=float)
        started = False
        prev = None
        changes = []
        for j, v in enumerate(vals):
            if not started:
                if np.isnan(v):
                    continue
                started = True
            same = (prev is not None) and ((np.isnan(v) and np.isnan(prev)) or v == prev)
            if not same:
                changes.append((vd[j], v))
            prev = v
        for k, (rs, v) in enumerate(changes):
            re_ = changes[k + 1][0] - pd.Timedelta(days=1) if k + 1 < len(changes) else pd.NaT
            rows.append((obs, v, rs, re_))
    df = pd.DataFrame(rows, columns=["date", "value", "realtime_start", "realtime_end"])
    for c in ("date", "realtime_start", "realtime_end"):
        df[c] = pd.to_datetime(df[c]).dt.date
    df["series_id"] = pd.array([sid] * len(df), dtype="string")
    df["source"] = pd.array([SRC] * len(df), dtype="string")
    return df


def main(refresh: bool = False) -> None:
    rd = raw_dir(SRC)
    out = curated_dir(SRC)
    age = 0 if refresh else 20
    for f in list(VINTAGES) + list(RELEASES) + EXTRA_RAW:
        download(f"{BASE}/{f}", rd / f, "xlsx", min_age_hours=age)
    cat = []
    for f, (sid, name, catg, freq, units) in VINTAGES.items():
        mat = pd.read_excel(rd / f, sheet_name=0)
        df = _to_long(mat, sid)
        df.to_parquet(out / f"{sid}.parquet", index=False)
        cat.append(dict(series_id=sid, source=SRC, name=name, category=catg, frequency=freq, units=units,
                        country="US", start=str(df.date.min()), end=str(df.date.max()),
                        transform_notes=(f"{f}: {mat.shape[1]-1} vintages {mat.columns[1]}..{mat.columns[-1]}; "
                                         "long format, only value changes kept; realtime_start = 15th of vintage "
                                         "month (quarterly vintage: 15th of mid-quarter month); realtime_end NULL = "
                                         "current. Levels are in each vintage's base year: compare growth rates "
                                         "within a vintage, not levels across vintages"),
                        url=PAGE, license=LIC, n_rows=len(df), n_vintages=mat.shape[1] - 1,
                        first_vintage=str(df.realtime_start.min()), last_vintage=str(df.realtime_start.max())))
        log.info("%s: %d rows, %d vintages", sid, len(df), mat.shape[1] - 1)
    for f, (sid, name, catg, freq, units) in RELEASES.items():
        raw = pd.read_excel(rd / f, sheet_name="DATA", header=None)
        hdr = raw.index[raw[0].astype(str).str.strip() == "Date"][0]
        d = raw.iloc[hdr + 1:].dropna(subset=[0])
        d.index = [_obs_date(x) for x in d[0]]
        for j, lab in enumerate(["first", "second", "third", "most_recent"], start=1):
            s = pd.to_numeric(d[j], errors="coerce").dropna()
            s_id = f"{sid}_{lab}"
            pd.DataFrame({"date": s.index.date, "value": s.values.astype(float),
                          "series_id": pd.array([s_id] * len(s), dtype="string"),
                          "source": pd.array([SRC] * len(s), dtype="string")}).to_parquet(
                out / f"{s_id}.parquet", index=False)
            cat.append(dict(series_id=s_id, source=SRC, name=f"{name}, {lab.replace('_', '-')} release",
                            category=catg, frequency=freq, units=units, country="US",
                            start=str(s.index.min().date()), end=str(s.index.max().date()),
                            transform_notes=f"{f} sheet DATA col {lab}; surprise/revision studies",
                            url=PAGE, license=LIC))
    c = pd.DataFrame(cat)
    c = c[CATALOG_COLS + [x for x in c.columns if x not in CATALOG_COLS]].sort_values("series_id")
    keep = set(c.series_id)
    for p in out.glob("*.parquet"):
        if p.stem not in keep:
            p.unlink()
    c.to_csv(out / "_catalog.csv", index=False)
    log.info("rtdsm: %d series", len(c))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
