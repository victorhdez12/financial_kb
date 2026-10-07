"""Point-in-time machinery: publication lags, as-of sampling on a month-end grid, ALFRED vintages.

Anti look-ahead rules implemented here (each is a deliberate decision):
1. Every observation gets an `available` date = end of its reference period + publication lag
   (table PUB_LAG). A value is used at decision date t only if available <= t.
   e.g. CPI for March (dated 03-01) -> period end 03-31 + 15d -> usable from mid-April.
2. Lags are conservative (rounded up) when the real calendar varies; unknown series get a
   frequency default (DEFAULT_LAG) that is at least as long as typical US release lags.
3. Transforms that need history (yoy, 6m annualised, Sahm) are computed on the observation
   index and then shifted to availability as a whole, so the transformed value at t only uses
   observations that were themselves available at t.
4. With ALFRED vintages, the value at t is computed from the vintage in force at t
   (realtime_start <= t < realtime_end), i.e. the data exactly as it was published then.
   Without vintages we use the latest revised data (`vintage_mode='latest'`): timing is
   honest but levels include later revisions — a known, documented bias.
"""
from __future__ import annotations

from datetime import date
from typing import Callable

import numpy as np
import pandas as pd

# days after the END of the reference period until the first release
PUB_LAG: dict[str, int] = {
    # prices (BLS CPI ~ 2nd week of next month, PPI similar; BEA PCE ~ end of next month)
    "CPIAUCSL": 15, "CPILFESL": 15, "bls_CUSR0000SA0": 15, "bls_CUUR0000SA0": 15,
    "PPIACO": 15, "PCEPI": 31, "PCEPILFE": 31, "PCE": 31,
    # labour (Employment Situation: first Friday of next month)
    "PAYEMS": 8, "UNRATE": 8, "bls_CES0000000001": 8, "bls_LNS14000000": 8,
    "ICSA": 5, "CCSA": 12,
    # activity
    "INDPRO": 17, "TCU": 17, "CFNAI": 24, "RSAFS": 16,
    # national accounts (advance estimate ~30 days after quarter end; NIPA detail later)
    "GDPC1": 30, "GDP": 30, "A191RL1Q225SBEA": 30,
    "A091RC1Q027SBEA": 60, "W006RC1Q027SBEA": 60, "TDSP": 90,
    # money / fiscal / balance sheets
    "M2SL": 28, "M1SL": 28, "GFDEGDQ188S": 90, "GFDEBTN": 45, "FYFSGDA188S": 120,
    "TCMDO": 75, "QUSPAM770A": 150, "QUSHAM770A": 150, "QUSNAM770A": 150,
    # monthly averages of market rates are known on the 1st of the next month
    "FEDFUNDS": 1, "TB3MS": 1, "GS10": 1, "BAA": 1, "AAA": 1,
    # weekly releases (FRED dates weekly series by week-end/Wed/Fri)
    "NFCI": 5, "ANFCI": 5, "NFCICREDIT": 5, "NFCILEVERAGE": 5, "NFCIRISK": 5, "NFCINONFINLEVERAGE": 5,
    "STLFSI4": 7, "STLFSI3": 7, "STLFSI2": 7, "WALCL": 1, "WTREGEN": 1, "WRESBAL": 1,
    # bank surveys / delinquencies (quarterly)
    "DRTSCILM": 45, "DRTSCIS": 45, "DRALACBN": 60, "DRALACBS": 60, "DRCCLACBS": 60, "DRBLACBS": 60,
}
DEFAULT_LAG = {"D": 1, "W": 6, "M": 31, "Q": 60, "A": 120}
# series whose FRED date is the survey START rather than a period to be completed
START_ANCHORED = {"DRTSCILM", "DRTSCIS"}


def infer_freq(idx: pd.DatetimeIndex) -> str:
    if len(idx) < 3:
        return "M"
    d = np.median(np.diff(idx.values).astype("timedelta64[D]").astype(int))
    if d <= 4:
        return "D"
    if d <= 10:
        return "W"
    if d <= 45:
        return "M"
    if d <= 120:
        return "Q"
    return "A"


def period_end(idx: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    if freq in ("D", "W"):
        return idx
    if freq == "M":
        return idx + pd.offsets.MonthEnd(0)
    if freq == "Q":
        return idx + pd.offsets.QuarterEnd(0)
    return idx + pd.offsets.YearEnd(0)


def available_dates(s: pd.Series, sid: str) -> pd.DatetimeIndex:
    freq = infer_freq(s.index)
    lag = PUB_LAG.get(sid, DEFAULT_LAG[freq])
    base = s.index if sid in START_ANCHORED else period_end(s.index, freq)
    return base + pd.Timedelta(days=lag)


def month_grid(start: str = "1947-01-31", today: date | None = None) -> pd.DataFrame:
    """Month-end decision dates; the current month's cutoff is today (not the future month end)."""
    today = pd.Timestamp(today or date.today())
    ends = pd.date_range(start, today + pd.offsets.MonthEnd(0), freq="ME")
    cutoff = ends.where(ends <= today, today)
    return pd.DataFrame({"date": ends, "cutoff": cutoff})


def asof_on_grid(s: pd.Series, sid: str, grid: pd.DataFrame, tag_obs: bool = False):
    """Value known at each grid cutoff (last observation whose release date <= cutoff)."""
    s = s.dropna()
    if s.empty:
        out = pd.Series(np.nan, index=grid["date"])
        return (out, pd.Series(pd.NaT, index=grid["date"])) if tag_obs else out
    obs = pd.DataFrame({"available": available_dates(s, sid), "value": s.values, "obs_date": s.index})
    obs = obs.sort_values("available")
    m = pd.merge_asof(grid.sort_values("cutoff"), obs, left_on="cutoff", right_on="available")
    vals = pd.Series(m["value"].values, index=grid["date"].values)
    if tag_obs:
        return vals, pd.Series(m["obs_date"].values, index=grid["date"].values)
    return vals


# ---------------------------------------------------------------- ALFRED vintages
def add_realtime_end(v: pd.DataFrame) -> pd.DataFrame:
    v = v.sort_values(["date", "realtime_start"]).copy()
    v["realtime_end"] = v.groupby("date")["realtime_start"].shift(-1).fillna(pd.Timestamp.max)
    return v


def vintage_asof(v: pd.DataFrame, grid: pd.DataFrame, fn: Callable[[pd.Series], float]) -> pd.Series:
    """For each cutoff t, rebuild the series exactly as published at t and apply `fn` to it.

    Returns NaN for cutoffs before the first vintage (caller falls back to latest data)."""
    out = pd.Series(np.nan, index=grid["date"].values)
    if v is None or v.empty:
        return out
    v = add_realtime_end(v)
    rs, re_ = v["realtime_start"].values, v["realtime_end"].values
    dates, vals = v["date"].values, v["value"].values
    first = v["realtime_start"].min()
    for d, t in zip(grid["date"], grid["cutoff"]):
        if t < first:
            continue
        mask = (rs <= np.datetime64(t)) & (re_ > np.datetime64(t))
        snap = pd.Series(vals[mask], index=pd.DatetimeIndex(dates[mask])).sort_index().dropna()
        if len(snap) < 13:
            continue
        try:
            out[d] = fn(snap)
        except Exception:
            pass
    return out
