"""Cleveland Fed inflation-expectations model (Haubrich-Pennacchi-Ritchken) -> curated/clev_inflexp.

    .venv/bin/python -m src.ingest.clev_inflexp

Source: www.clevelandfed.org .../inflation-expectations.xlsx (public, no key). Monthly, 1982+.
Model combines Treasury yields, inflation data, inflation swaps and survey forecasts.
Kept: expected inflation at 2,3,5,7,20,30 years (1y and 10y already in fred_us as EXPINF1YR /
EXPINF10YR, not duplicated), 5y5y forward expected inflation (derived), 10y real and inflation
risk premia, real rates 1m/1y/10y. All in percent (the 'Expected Inflation' and 'Real Interest
Rate' sheets are fractions -> x100).
date = model output month (first of month). Point-in-time: published around the middle of that
same month (after the CPI release; 2026-10 value already out on 2026-10-14) -> use date + ~15 d.
"""
from __future__ import annotations

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, find_link, log, raw_dir

SOURCE = "clev_inflexp"
PAGE = "https://www.clevelandfed.org/indicators-and-data/inflation-expectations"
FALLBACK = ("https://www.clevelandfed.org/-/media/files/webcharts/inflationexpectations/"
            "inflation-expectations.xlsx?sc_lang=en")
LICENSE = "Federal Reserve Bank of Cleveland public data; free use with attribution"
NOTE = ("Cleveland Fed model output (Haubrich, Pennacchi & Ritchken 2012); monthly, date = model "
        "output month; published ~mid-month of the same month (PIT: date + 15 d)")


def _sheet(path, name: str) -> pd.DataFrame:
    d = pd.read_excel(path, sheet_name=name)
    d.columns = [str(c).strip() for c in d.columns]
    d = d.set_index(pd.to_datetime(d.iloc[:, 0], errors="coerce")).iloc[:, 1:]
    return d[d.index.notna()].apply(pd.to_numeric, errors="coerce")


def run() -> pd.DataFrame:
    url = find_link(PAGE, r"inflation-expectations\.xlsx") or FALLBACK
    p = download(url, raw_dir(SOURCE) / "inflation-expectations.xlsx", "xlsx", min_age_hours=20)
    cw = CatalogWriter(SOURCE, url=PAGE, license=LICENSE)
    ei = _sheet(p, "Expected Inflation") * 100
    for y in (2, 3, 5, 7, 20, 30):
        cw.add(f"clev_expinf_{y}y", ei[f"{y} year Expected Inflation"],
               name=f"Cleveland Fed {y}-year expected inflation (annual average)", category="inflation",
               frequency="M", units="% p.a.", country="US", transform_notes=NOTE + "; fraction x100")
    fwd = (10 * ei["10 year Expected Inflation"] - 5 * ei["5 year Expected Inflation"]) / 5
    cw.add("clev_expinf_5y5y", fwd, name="Cleveland Fed 5y5y forward expected inflation (derived)",
           category="inflation", frequency="M", units="% p.a.", country="US",
           transform_notes=NOTE + "; derived (10*E10 - 5*E5)/5 from the expected-inflation curve")
    tt = _sheet(p, "Ten-year Expected Chart")
    for col, sid, nm in [("Real Risk Premium", "clev_real_rp_10y", "10-year real risk premium"),
                         ("Inflation Risk Premium", "clev_infl_rp_10y", "10-year inflation risk premium")]:
        cw.add(sid, tt[col], name=f"Cleveland Fed {nm}", category="inflation" if "infl" in sid else "rates",
               frequency="M", units="% p.a.", country="US", transform_notes=NOTE)
    rr = _sheet(p, "Real Interest Rate") * 100
    for col, tag in [("Real Rate 1-month", "1m"), ("Real Rate 1-year", "1y"), ("Real Rate 10-year", "10y")]:
        cw.add(f"clev_real_rate_{tag}", rr[col], name=f"Cleveland Fed real interest rate, {tag}",
               category="rates", frequency="M", units="% p.a.", country="US",
               transform_notes=NOTE + "; fraction x100")
    log.info("clev_inflexp: last model date %s", ei.index.max().date())
    return cw.close()


if __name__ == "__main__":
    run()
