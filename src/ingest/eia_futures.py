"""EIA NYMEX futures (WTI crude oil, Henry Hub natural gas; contracts 1-4) -> curated/eia_futures.

    .venv/bin/python -m src.ingest.eia_futures

Source: EIA historical xls (public, no key) www.eia.gov/dnav/{pet,ng}/hist_xls/<KEY>d.xls.
EIA STOPPED publishing NYMEX futures on 2024-04-05 (licensing); the files are frozen there and
there is no free official continuation (see docs/data/futures_derivatives_2026-10-14.md).
Contract n = n-th nearby NYMEX contract as defined by EIA (rolls at each expiry; no back-
adjustment). Derived curve slopes:
  *_spread_c2_c1   C2 - C1 (USD; > 0 = contango)
  *_slope_c4_c1    C4 / C1 - 1 (%; > 0 = contango, < 0 = backwardation). NaN when C1 <= 0
                   (WTI 2020-04-20, C1 = -37.63 USD).
Point-in-time: NYMEX settlement on the date (~14:30 ET); EIA posted it with ~1 business day lag.
Raw xls files are kept intact in $FIN_DATA_ROOT/raw/eia_futures/.
"""
from __future__ import annotations

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, log, raw_dir

SOURCE = "eia_futures"
URL = "https://www.eia.gov/dnav/{}/hist_xls/{}d.xls"
LICENSE = "EIA data, US government work (public domain); NYMEX futures prices as published by EIA"
PRODUCTS = {  # prefix -> (dnav area, key stem, label, units)
    "wti": ("pet", "RCLC", "WTI crude oil (Cushing, OK) NYMEX futures", "USD/barrel"),
    "ng": ("ng", "RNGC", "Henry Hub natural gas NYMEX futures", "USD/MMBtu"),
}
NOTE = ("EIA daily NYMEX futures, contract {n} (n-th nearby, rolled at expiry by EIA, no back-"
        "adjustment); EIA discontinued the series on 2024-04-05; settlement at t, ~1 business day "
        "publication lag")


def _read(path) -> pd.Series:
    d = pd.read_excel(path, sheet_name="Data 1", header=2)
    s = pd.Series(pd.to_numeric(d.iloc[:, 1], errors="coerce").values,
                  index=pd.to_datetime(d.iloc[:, 0], errors="coerce"))
    return s[s.index.notna()].dropna()


def run() -> pd.DataFrame:
    raw = raw_dir(SOURCE)
    cw = CatalogWriter(SOURCE, url="https://www.eia.gov/dnav/pet/pet_pri_fut_s1_d.htm", license=LICENSE)
    for pre, (area, key, label, units) in PRODUCTS.items():
        c = {}
        for n in range(1, 5):
            url = URL.format(area, f"{key}{n}")
            try:
                # frozen since 2024-04 -> refresh only monthly in case EIA resumes
                p = download(url, raw / f"{key}{n}d.xls", "xls", min_age_hours=24 * 30)
            except Exception as e:  # noqa: BLE001
                log.warning("%s unavailable: %s", url, e)
                continue
            c[n] = _read(p)
            cw.add(f"eia_{pre}_fut_c{n}", c[n], name=f"{label}, contract {n} settle",
                   category="commodities", frequency="D", units=units, country="US",
                   transform_notes=NOTE.format(n=n), url=url)
        if 1 in c and 2 in c:
            cw.add(f"eia_{pre}_fut_spread_c2_c1", (c[2] - c[1]).dropna(),
                   name=f"{label}: curve spread C2 - C1 (>0 contango)", category="commodities",
                   frequency="D", units=units, country="US",
                   transform_notes="C2 - C1 on common dates; " + NOTE.format(n="1-2"))
        if 1 in c and 4 in c:
            c1 = c[1].where(c[1] > 0)
            cw.add(f"eia_{pre}_fut_slope_c4_c1", ((c[4] / c1 - 1) * 100).dropna(),
                   name=f"{label}: curve slope C4/C1 - 1 (>0 contango, <0 backwardation)",
                   category="commodities", frequency="D", units="%", country="US",
                   transform_notes="C4/C1 - 1 on common dates, NaN if C1 <= 0 (WTI 2020-04-20); "
                                   + NOTE.format(n="1,4"))
    return cw.close()


if __name__ == "__main__":
    run()
