"""Gilchrist-Zakrajsek credit spread and Excess Bond Premium (Fed Board) -> curated/fed_ebp.

    .venv/bin/python -m src.ingest.fed_ebp

Source: https://www.federalreserve.gov/econres/notes/feds-notes/ebp_csv.csv
(columns date, gz_spread, ebp, est_prob; monthly, 1973-01 onward). Dates are already month starts.
Updated by the Fed roughly monthly; the last value can be revised. Raw kept in raw/fed_ebp/.
est_prob = estimated probability of a US recession implied by the EBP (Favara et al. 2016).
"""
from __future__ import annotations

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, raw_dir

SOURCE = "fed_ebp"
URL = "https://www.federalreserve.gov/econres/notes/feds-notes/ebp_csv.csv"
LICENSE = "Federal Reserve Board public data; cite Gilchrist & Zakrajsek (2012) and Favara et al. (2016)"


def run() -> pd.DataFrame:
    p = download(URL, raw_dir(SOURCE) / "ebp_csv.csv", "csv", min_age_hours=20)
    d = pd.read_csv(p, parse_dates=["date"]).set_index("date")
    d.index = d.index.to_period("M").to_timestamp()
    cw = CatalogWriter(SOURCE, url=URL, license=LICENSE)
    meta = {
        "gz_spread": ("fed_ebp_gz_spread", "Gilchrist-Zakrajsek credit spread (corporate bond yield minus Treasury)",
                      "percentage points", "credit"),
        "ebp": ("fed_ebp_ebp", "Excess Bond Premium (GZ spread component not explained by default risk)",
                "percentage points", "financial_conditions"),
        "est_prob": ("fed_ebp_recession_prob", "Recession probability implied by the EBP (12-month ahead, Favara et al.)",
                     "probability (0-1)", "financial_conditions"),
    }
    for col, (sid, name, units, cat) in meta.items():
        cw.add(sid, d[col], name=name, category=cat, frequency="M", units=units, country="US",
               transform_notes="monthly, dated month start. Estimated with full-sample parameters "
               "(not strictly real time); last values may be revised.")
    return cw.close()


if __name__ == "__main__":
    run()
