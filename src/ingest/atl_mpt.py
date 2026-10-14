"""Atlanta Fed Market Probability Tracker (3M SOFR options) -> curated/atl_mpt.

    .venv/bin/python -m src.ingest.atl_mpt

Source: atlantafed.org .../market-probability-tracker/mpt_histdata.xlsx (public, no key; "use
permitted for personal and educational purposes only"; CME data used under permission).
Long format: (date, reference_start of a 3-month SOFR window, FOMC target range on date, field,
value in bps or %). Daily, 2023-03-29+.

The reference windows are fixed calendar quarters (IMM dates), so their horizon shrinks every
day. Constant-horizon series are built per date by linear interpolation in calendar days between
date and reference_start (no extrapolation: NaN outside the available windows):
  atl_mpt_sofr_mean_{3,6,12,24}m   mean of the implied distribution of 3M average SOFR (%)
  atl_mpt_chg_{6,12}m              mean minus midpoint of the current FOMC target range (pp;
                                   < 0 = market prices cuts)
  atl_mpt_iqr_12m                  p75 - p25 at 12 months (pp; rate uncertainty)
  atl_mpt_prob_cut_{6,12}m / prob_hike_{6,12}m   P(avg SOFR below / above current target range)
Point-in-time: date = observation (market close); file updated next morning (t+1 business day).
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, find_link, log, raw_dir

SOURCE = "atl_mpt"
PAGE = "https://www.atlantafed.org/research-and-data/data/market-probability-tracker"
FALLBACK = ("https://www.atlantafed.org/-/media/Project/Atlanta/FRBA/Documents/research-and-data/"
            "data/market-probability-tracker/mpt_histdata.xlsx")
LICENSE = ("Federal Reserve Bank of Atlanta; use permitted for personal and educational purposes "
           "only; CME Group market data used under permission (non-commercial)")
NOTE = ("Atlanta Fed MPT (CME 3M SOFR options); constant horizon by linear interpolation in "
        "calendar days to reference_start across the quarterly windows, no extrapolation; "
        "PIT: market close at date, published t+1")
FIELDS = {"Rate: mean": "mean", "Rate: 25th percentile": "p25", "Rate: 75th percentile": "p75",
          "Prob: cut": "cut", "Prob: hike": "hike"}
DAYS = {3: 91, 6: 182, 12: 365, 24: 730}


def _mid(rng: str) -> float:
    m = re.findall(r"(\d+)\s*bps", str(rng))
    return np.mean([float(x) for x in m]) / 100 if len(m) == 2 else np.nan


def run() -> pd.DataFrame:
    url = find_link(PAGE, r"mpt_histdata\.xlsx") or FALLBACK
    p = download(url, raw_dir(SOURCE) / "mpt_histdata.xlsx", "xlsx", min_age_hours=20)
    d = pd.read_excel(p, sheet_name="DATA")
    d = d[d["field"].isin(FIELDS)].copy()
    d["date"] = pd.to_datetime(d["date"])
    d["h"] = (pd.to_datetime(d["reference_start"]) - d["date"]).dt.days
    d["f"] = d["field"].map(FIELDS)
    d["value"] = pd.to_numeric(d["value"], errors="coerce")
    w = d.pivot_table(index=["date", "h"], columns="f", values="value").reset_index()
    tgt = d.groupby("date")["target_range"].first().map(_mid)
    log.info("MPT: %d dates %s -> %s", w["date"].nunique(), w["date"].min().date(), w["date"].max().date())

    def interp(col: str, days: int) -> pd.Series:
        out = {}
        for dt, g in w[["date", "h", col]].dropna().groupby("date"):
            g = g.sort_values("h")
            x, y = g["h"].to_numpy(float), g[col].to_numpy(float)
            out[dt] = np.interp(days, x, y) if x[0] <= days <= x[-1] else np.nan
        return pd.Series(out, dtype=float)

    cw = CatalogWriter(SOURCE, url=PAGE, license=LICENSE)
    mean = {m: interp("mean", dd) / 100 for m, dd in DAYS.items()}
    for m, s in mean.items():
        cw.add(f"atl_mpt_sofr_mean_{m}m", s, name=f"Market-implied mean 3M SOFR, {m} months ahead (Atlanta Fed MPT)",
               category="rates", frequency="D", units="% p.a.", country="US", transform_notes=NOTE + "; bps/100")
    for m in (6, 12):
        cw.add(f"atl_mpt_chg_{m}m", (mean[m] - tgt.reindex(mean[m].index)),
               name=f"Market-implied change in policy rate over {m} months (mean SOFR - target midpoint)",
               category="rates", frequency="D", units="pp", country="US",
               transform_notes=NOTE + "; minus midpoint of the FOMC target range on date (SOFR-IORB "
                                      "basis of a few bp included)")
        for f, lab in (("cut", "below (cut)"), ("hike", "above (hike)")):
            cw.add(f"atl_mpt_prob_{f}_{m}m", interp(f, DAYS[m]),
                   name=f"Probability avg 3M SOFR {m} months ahead is {lab} the current target range",
                   category="rates", frequency="D", units="%", country="US", transform_notes=NOTE)
    cw.add("atl_mpt_iqr_12m", (interp("p75", 365) - interp("p25", 365)) / 100,
           name="Market-implied interquartile range of 3M SOFR 12 months ahead", category="rates",
           frequency="D", units="pp", country="US", transform_notes=NOTE + "; (p75 - p25)/100")
    return cw.close()


if __name__ == "__main__":
    run()
