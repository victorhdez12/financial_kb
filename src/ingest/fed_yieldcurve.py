"""Federal Reserve Board staff yield curves -> curated/fed_yieldcurve (docs/DATA_CONTRACT.md).

    .venv/bin/python -m src.ingest.fed_yieldcurve

* Gurkaynak-Sack-Wright (2007) nominal Treasury curve, daily 1961-06+ (feds200628.csv):
  zero-coupon yields SVENY01..SVENY30, 1-year forwards SVEN1F01/04/09, instantaneous forwards
  SVENF01..SVENF30 are NOT kept (derivable from the parameters / zeros).
* Gurkaynak-Sack-Wright (2010) TIPS real curve, daily 1999-01+ (feds200805.csv): real zero
  yields TIPSY02..TIPSY20 and breakevens BKEVEN02..BKEVEN20, BKEVEN1F4, BKEVEN1F9, BKEVEN5F5.
Kim-Wright term premia are in curated/fred_us (THREEFYTP*), ACM in curated/nyfed.
Raw CSVs kept untouched in $FIN_DATA_ROOT/raw/fed_yieldcurve/.
"""
from __future__ import annotations

import io
import re

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, log, raw_dir

SOURCE = "fed_yieldcurve"
BASE = "https://www.federalreserve.gov/data/yield-curve-tables/"
LICENSE = "Federal Reserve Board staff research data (public); cite Gurkaynak, Sack & Wright (2007, 2010)"
FILES = {
    "feds200628.csv": ("nominal", re.compile(r"^(SVENY\d\d|SVEN1F0[149])$")),
    "feds200805.csv": ("tips", re.compile(r"^(TIPSY\d\d|BKEVEN\d\d|BKEVEN1F[49]|BKEVEN5F5)$")),
}


def read_gsw(path) -> pd.DataFrame:
    lines = path.read_text(errors="replace").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("Date,"))
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])), na_values=["NA", "-999.99", ""])
    df["Date"] = pd.to_datetime(df["Date"])
    return df.set_index("Date").sort_index()


def describe(col: str) -> tuple[str, str]:
    m = re.match(r"SVENY(\d\d)", col)
    if m:
        return f"GSW nominal zero-coupon Treasury yield, {int(m[1])}y", "rates"
    m = re.match(r"SVEN1F0(\d)", col)
    if m:
        return f"GSW nominal 1-year forward rate starting in {m[1]}y", "rates"
    m = re.match(r"TIPSY(\d\d)", col)
    if m:
        return f"GSW TIPS real zero-coupon yield, {int(m[1])}y", "rates"
    m = re.match(r"BKEVEN(\d\d)$", col)
    if m:
        return f"GSW zero-coupon breakeven inflation, {int(m[1])}y", "inflation"
    m = re.match(r"BKEVEN1F(\d)", col)
    if m:
        return f"GSW 1-year forward breakeven inflation starting in {m[1]}y", "inflation"
    return "GSW 5-year forward breakeven inflation starting in 5y (5y5y)", "inflation"


def main() -> None:
    cw = CatalogWriter(SOURCE, url=BASE, license=LICENSE)
    rd = raw_dir(SOURCE)
    for fname, (kind, pat) in FILES.items():
        p = download(BASE + fname, rd / fname, "csv", min_age_hours=20)
        df = read_gsw(p)
        cols = [c for c in df.columns if pat.match(c)]
        log.info("%s: %d rows %s..%s, %d series", fname, len(df), df.index.min().date(),
                 df.index.max().date(), len(cols))
        for c in cols:
            name, cat = describe(c)
            cw.add(f"gsw_{c.lower()}", df[c], name=name, category=cat, frequency="D",
                   units="Percent, continuously compounded", country="US",
                   transform_notes=f"{fname} column {c}; NA/-999.99 -> dropped (business days only)",
                   url=BASE + fname)
    cat = cw.close()
    print(cat[["series_id", "start", "end"]].to_string(index=False))


if __name__ == "__main__":
    main()
