"""Robert Shiller - U.S. stock market data (ie_data.xls), monthly 1871-present.

Run: .venv/bin/python -m src.ingest.shiller
Raw:     $FIN_DATA_ROOT/raw/shiller/ie_data.xls
Curated: $FIN_DATA_ROOT/curated/shiller/shiller_*.parquet
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, find_link, log, raw_dir

SOURCE = "shiller"
PAGE = "https://shillerdata.com/"
FALLBACK_URLS = [
    "https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/downloads/ie_data.xls",
    "http://www.econ.yale.edu/~shiller/data/ie_data.xls",
]
LICENSE = "Public data by Robert J. Shiller (Irrational Exuberance); free for research, cite source"

# column position -> (series suffix, name, category, units)
COLS = {
    1: ("sp_price", "S&P Composite price (monthly avg of daily closes)", "markets", "index"),
    2: ("sp_dividend", "S&P Composite dividends (12m trailing, interpolated)", "valuation", "USD per index unit"),
    3: ("sp_earnings", "S&P Composite earnings (12m trailing, interpolated)", "valuation", "USD per index unit"),
    4: ("cpi", "Consumer Price Index (Shiller/BLS splice)", "inflation", "index"),
    6: ("gs10", "Long interest rate (GS10 from 1953, splice before)", "rates", "percent"),
    7: ("real_price", "Real S&P price (current-month dollars)", "markets", "index (real)"),
    8: ("real_dividend", "Real dividend", "valuation", "USD real"),
    9: ("real_tr_price", "Real total return price index (dividends reinvested)", "equity_returns", "index (real)"),
    10: ("real_earnings", "Real earnings", "valuation", "USD real"),
    11: ("real_tr_scaled_earnings", "Real TR scaled earnings", "valuation", "USD real"),
    12: ("cape", "Cyclically adjusted P/E (P/E10, CAPE)", "valuation", "ratio"),
    14: ("tr_cape", "Total return CAPE", "valuation", "ratio"),
    16: ("excess_cape_yield", "Excess CAPE yield (1/TR-CAPE minus real 10y yield)", "valuation", "ratio"),
    17: ("bond_tr_monthly", "Monthly total bond return (10y, gross, nominal)", "bond_returns", "gross return (1+r)"),
    18: ("real_bond_tr_index", "Real total bond return index", "bond_returns", "index (real)"),
    19: ("fwd10y_real_stock_ret", "Forward 10y annualized real stock return", "equity_returns", "fraction p.a."),
    20: ("fwd10y_real_bond_ret", "Forward 10y annualized real bond return", "bond_returns", "fraction p.a."),
    21: ("fwd10y_excess_ret", "Forward 10y annualized real excess return (stocks - bonds)", "equity_returns", "fraction p.a."),
}


# (series suffix, date) -> (wrong value in Shiller's file, corrected value, reason); only applied while the file still has the wrong value
KNOWN_FIXES = {
    ("gs10", "2019-07-01"): (1.63, 2.06, "Shiller repeats the Aug-2019 value; FRED GS10 Jul-2019 = 2.06 (audit 2026-10-12)"),
}


def fetch() -> tuple[str, "Path"]:
    dest = raw_dir(SOURCE) / "ie_data.xls"
    urls = []
    link = find_link(PAGE, r"ie_data\.xls")
    if link:
        urls.append(link)
    urls += FALLBACK_URLS
    for u in urls:
        try:
            download(u, dest, "xls")
            return u, dest
        except Exception as e:  # noqa: BLE001
            log.warning("shiller download failed from %s: %s", u, e)
    if dest.exists():
        log.warning("using previously downloaded %s", dest)
        return urls[0], dest
    raise RuntimeError("could not download Shiller ie_data.xls")


def parse(path) -> pd.DataFrame:
    d = pd.read_excel(path, sheet_name="Data", header=None)
    d = d.iloc[8:].copy()
    d = d[pd.to_numeric(d[0], errors="coerce").notna()]
    x = pd.to_numeric(d[0]).astype(float)
    year = np.floor(x).astype(int)
    month = np.rint((x - year) * 100).astype(int)
    assert month.between(1, 12).all(), "bad Shiller month decoding"
    d.index = pd.to_datetime(dict(year=year, month=month, day=1))
    return d


def main() -> None:
    url, path = fetch()
    d = parse(path)
    cw = CatalogWriter(SOURCE, url=url, license=LICENSE)
    for col, (suf, name, cat, units) in COLS.items():
        notes = "Date decoded from YYYY.MM; last month is provisional (partial-month price/CPI estimate per Shiller footnote)"
        if suf.startswith("fwd10y"):
            notes += "; FORWARD-LOOKING (look-ahead): value at t uses returns t..t+120m - never use as a predictor"
        series = d[col]
        for (fsuf, fdate), (bad, good, why) in KNOWN_FIXES.items():
            ts = pd.Timestamp(fdate)
            if fsuf == suf and ts in series.index and abs(pd.to_numeric(series[ts]) - bad) < 1e-9:
                series = series.copy()
                series[ts] = good
                notes += f"; FIX {fdate}: {bad} -> {good} ({why})"
        cw.add(f"shiller_{suf}", series, name=name, category=cat, frequency="M", units=units,
               country="USA", transform_notes=notes)
    # derived monthly returns
    rtr = pd.to_numeric(d[9], errors="coerce")
    cpi = pd.to_numeric(d[4], errors="coerce")
    real_ret = rtr.pct_change(fill_method=None)
    nominal_tr = rtr * cpi / cpi.iloc[-1]
    cw.add("shiller_real_stock_tr_ret_m", real_ret, name="Monthly real total return S&P (from real TR price)",
           category="equity_returns", frequency="M", units="fraction", country="USA",
           transform_notes="pct_change of Shiller real total return price")
    cw.add("shiller_nominal_stock_tr_ret_m", nominal_tr.pct_change(fill_method=None),
           name="Monthly nominal total return S&P", category="equity_returns", frequency="M",
           units="fraction", country="USA", transform_notes="real TR price x CPI, pct_change")
    cw.add("shiller_nominal_bond_tr_ret_m", pd.to_numeric(d[17], errors="coerce") - 1,
           name="Monthly nominal 10y bond total return", category="bond_returns", frequency="M",
           units="fraction", country="USA", transform_notes="Shiller gross bond return minus 1")
    cat = cw.close()
    print(cat[["series_id", "start", "end"]].to_string(index=False))


if __name__ == "__main__":
    main()
