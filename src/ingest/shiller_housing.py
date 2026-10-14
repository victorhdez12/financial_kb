"""Shiller US home prices 1890+ (Irrational Exuberance Fig. 3.1 data) -> curated/shiller_housing.

    .venv/bin/python -m src.ingest.shiller_housing

Source: Fig3-1.xls linked from https://shillerdata.com/ (updated by R. Shiller). The sheet holds
several (date, value) column pairs:
  cols 0-1  real home price index (1890=100): annual 1890-1952, monthly from 1953-01
  cols 7-8  nominal home price index: idem (Grebler/Case-Shiller/S&P CoreLogic splice by Shiller)
  cols 2-6  annual: real building cost index, US population (millions), long rate (Jan, Homer
            "History of Interest Rates" before GS10)
  cols 10-11 annual nominal building cost index; cols 17-18 annual CPI
Annual and monthly parts are split into separate series (_a / _m) so frequencies are not mixed.
Monthly fractional dates (YYYY + (m-0.5)/12) are mapped to the first day of month m.
"""
from __future__ import annotations

import math

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, find_link, log, raw_dir

SOURCE = "shiller_housing"
PAGE = "https://shillerdata.com/"
LICENSE = "Robert J. Shiller public data (Irrational Exuberance, 3rd ed., updated); cite source"


def split(d: pd.DataFrame, dc: int, vc: int) -> tuple[pd.Series, pd.Series]:
    s = d[[dc, vc]].copy()
    s[dc] = pd.to_numeric(s[dc], errors="coerce")
    s[vc] = pd.to_numeric(s[vc], errors="coerce")
    s = s.dropna(subset=[dc])
    ann, mon = {}, {}
    for t, v in zip(s[dc], s[vc]):
        if abs(t - round(t)) < 1e-6:
            ann[pd.Timestamp(int(round(t)), 1, 1)] = v
        else:
            y = math.floor(t)
            m = min(12, int((t - y) * 12) + 1)
            mon[pd.Timestamp(y, m, 1)] = v
    return pd.Series(ann, dtype=float), pd.Series(mon, dtype=float)


def main() -> None:
    url = find_link(PAGE, r"Fig3-1.*\.xls")
    if not url:
        raise SystemExit("Fig3-1.xls link not found on shillerdata.com")
    p = download(url, raw_dir(SOURCE) / "Fig3-1.xls", "xls", min_age_hours=20)
    d = pd.read_excel(p, header=None).iloc[7:]
    cw = CatalogWriter(SOURCE, url=url, license=LICENSE)
    base = "Fig3-1.xls; "
    for dc, vc, sid, name, units, cat in [
        (0, 1, "shillerh_hpi_real", "Shiller real US home price index", "Index 1890=100", "housing"),
        (7, 8, "shillerh_hpi_nominal", "Shiller nominal US home price index (spliced)",
         "Index (Case-Shiller scale)", "housing"),
    ]:
        a, m = split(d, dc, vc)
        cw.add(f"{sid}_a", a[a.index.year < 1953], name=name + " (annual, 1890-1952)", category=cat,
               frequency="A", units=units, country="US",
               transform_notes=base + f"cols {dc}-{vc}; annual rows only (source switches to monthly in 1953)")
        cw.add(f"{sid}_m", m, name=name + " (monthly, 1953+)", category=cat, frequency="M", units=units,
               country="US", transform_notes=base + f"cols {dc}-{vc}; fractional year -> month start")
    for dc, vc, sid, name, units, cat in [
        (2, 3, "shillerh_build_cost_real_a", "Real building cost index", "Index", "housing"),
        (10, 11, "shillerh_build_cost_nominal_a", "Nominal building cost index", "Index", "housing"),
        (2, 4, "shillerh_population_a", "US population", "Millions", "growth"),
        (2, 5, "shillerh_long_rate_a", "US long-term interest rate, January (Homer before GS10)",
         "Percent", "rates"),
        (17, 18, "shillerh_cpi_a", "US CPI, annual (Warren&Pearson / BLS)", "Index", "inflation"),
    ]:
        a, _ = split(d, dc, vc)
        cw.add(sid, a, name=name, category=cat, frequency="A", units=units, country="US",
               transform_notes=base + f"cols {dc}-{vc}; sources per row in adjacent source column")
    cat = cw.close()
    log.info("\n%s", cat[["series_id", "start", "end"]].to_string(index=False))


if __name__ == "__main__":
    main()
