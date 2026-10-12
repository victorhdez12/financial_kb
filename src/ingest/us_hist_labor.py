"""Long-run annual US unemployment rate 1890-2010 -> curated/us_hist_labor.

    .venv/bin/python -m src.ingest.us_hist_labor

Source: OpenIntro `unempl` dataset (https://www.openintro.org/data/index.php?data=unempl), which
compiles Romer (1986, "Spurious Volatility in Historical Unemployment Data", JPE) for 1890-1929,
Coen (1973) for 1930-1939 and BLS (annual CPS average) from 1940 (column us_data = 1).
Raw CSV kept untouched in $FIN_DATA_ROOT/raw/us_hist_labor/.

Lebergott (1964) / Weir (1992) / HSUS Ba470-477 are behind the Cambridge HSUS paywall and are
NOT included (pending gap). Monthly 1929-1966 NBER tranches are in curated/fred (M0892*) and
curated/nber_macrohistory (nber_m08292a).
"""
from __future__ import annotations

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, raw_dir

SOURCE = "us_hist_labor"
URL = "https://www.openintro.org/data/csv/unempl.csv"
PAGE = "https://www.openintro.org/data/index.php?data=unempl"
LICENSE = "OpenIntro data (CC BY-SA); underlying: Romer (1986), Coen (1973), BLS (public domain)"


def main() -> None:
    p = download(URL, raw_dir(SOURCE) / "unempl.csv", "csv", min_age_hours=24 * 30)
    df = pd.read_csv(p)
    df.index = pd.to_datetime(df["year"].astype(str) + "-01-01")
    cw = CatalogWriter(SOURCE, url=PAGE, license=LICENSE)
    cw.add("us_unemp_romer_a", df["unemp"],
           name="US unemployment rate, annual 1890-2010 (Romer 1890-1929, Coen 1930-39, BLS 1940+)",
           category="employment", frequency="A", units="Percent of labor force", country="US",
           transform_notes=("splice as published by OpenIntro: Romer (1986) 1890-1929, Coen (1973) 1930-1939 "
                            "(lower than Lebergott, e.g. 1933 19.8 vs 24.9), BLS annual average 1940+ "
                            "(us_data=1); year dated Jan 1"))
    cw.add("us_unemp_romer_flag_a", df["us_data"],
           name="Flag: 1 = official BLS data, 0 = historical estimate (us_unemp_romer_a)",
           category="employment", frequency="A", units="0/1", country="US",
           transform_notes="column us_data of the raw CSV")
    print(cw.close().to_string(index=False))


if __name__ == "__main__":
    main()
