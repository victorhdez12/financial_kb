"""New York Fed: ACM term-structure decomposition (Adrian-Crump-Moench, 1961 ->) and the
yield-curve recession-probability model (Estrella-Mishkin, 1959 ->).

source_id = nyfed.
- nyfed_acm_{y,tp,rny}NN_m : monthly (month-end obs, dated 1st of month) fitted yield, term premium,
  risk-neutral yield for maturities 1..10y.
- nyfed_acm_{y,tp,rny}{02,05,10}_d : daily.
- nyfed_recprob_target : P(recession) as published, dated at the TARGET month (12m ahead).
- nyfed_recprob_12m    : same values dated at the month of the spread used (target - 12m) ->
  point-in-time usable signal.
- nyfed_spread_10y3m_m : 10y - 3m (bond-equivalent) spread used by the model.

Run: .venv/bin/python -m src.ingest.cycle_nyfed [--refresh]
"""
from __future__ import annotations

import sys
import warnings

import pandas as pd

from ._extlong_common import CatalogWriter, download, log, raw_dir

warnings.filterwarnings("ignore")
SRC = "nyfed"
ACM_URL = "https://www.newyorkfed.org/medialibrary/media/research/data_indicators/ACMTermPremium.xls"
REC_URL = "https://www.newyorkfed.org/medialibrary/media/research/capital_markets/allmonth.xls"
LIC = "Federal Reserve Bank of New York, public research data; cite Adrian, Crump & Moench (2013)"


def main(refresh: bool = False) -> None:
    rd = raw_dir(SRC)
    age = 0 if refresh else 20
    download(ACM_URL, rd / "ACMTermPremium.xls", "xls", min_age_hours=age)
    download(REC_URL, rd / "allmonth.xls", "xls", min_age_hours=age)
    cw = CatalogWriter(SRC, url="https://www.newyorkfed.org/research/data_indicators/term-premia-tabs",
                       license=LIC)
    kinds = {"ACMY": ("y", "ACM fitted zero-coupon Treasury yield"),
             "ACMTP": ("tp", "ACM term premium"),
             "ACMRNY": ("rny", "ACM risk-neutral (expected short rate) yield")}
    m = pd.read_excel(rd / "ACMTermPremium.xls", sheet_name="ACM Monthly")
    m.index = pd.to_datetime(m["DATE"], format="%d-%b-%Y").dt.to_period("M").dt.start_time
    d = pd.read_excel(rd / "ACMTermPremium.xls", sheet_name="ACM Daily")
    d.index = pd.to_datetime(d["DATE"], format="%d-%b-%Y")
    for pref, (k, desc) in kinds.items():
        for n in range(1, 11):
            col = f"{pref}{n:02d}"
            cw.add(f"nyfed_acm_{k}{n:02d}_m", m[col], name=f"{desc}, {n}y (monthly)", category="rates",
                   frequency="M", units="percent", country="US",
                   transform_notes=f"sheet 'ACM Monthly' {col}; month-end obs dated 1st of month",
                   url=ACM_URL)
            if n in (2, 5, 10):
                cw.add(f"nyfed_acm_{k}{n:02d}_d", d[col], name=f"{desc}, {n}y (daily)", category="rates",
                       frequency="D", units="percent", country="US",
                       transform_notes=f"sheet 'ACM Daily' {col}", url=ACM_URL)
    r = pd.read_excel(rd / "allmonth.xls", sheet_name="rec_prob")
    r.index = pd.to_datetime(r["Date"]).dt.to_period("M").dt.start_time
    cw.add("nyfed_recprob_target", r["Rec_prob"] * 100, name="NY Fed yield-curve P(recession) at target month",
           category="growth", frequency="M", units="percent", country="US",
           transform_notes="allmonth.xls Rec_prob x100; dated at TARGET month (12m after the spread)",
           url=REC_URL)
    sig = r["Rec_prob"].copy() * 100
    sig.index = sig.index - pd.DateOffset(months=12)
    cw.add("nyfed_recprob_12m", sig, name="NY Fed P(recession in 12m), dated at signal month",
           category="growth", frequency="M", units="percent", country="US",
           transform_notes="Rec_prob x100 shifted -12m so date = month of the 10y-3m spread (point-in-time)",
           url=REC_URL)
    cw.add("nyfed_spread_10y3m_m", r["Spread"], name="10y - 3m Treasury spread (bond-equivalent), monthly avg",
           category="rates", frequency="M", units="pp", country="US",
           transform_notes="allmonth.xls Spread", url=REC_URL)
    cat = cw.close()
    log.info("nyfed: %d series", len(cat))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
