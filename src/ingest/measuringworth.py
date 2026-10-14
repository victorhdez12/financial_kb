"""MeasuringWorth (Officer & Williamson): long annual US/UK interest rates and consumer prices.

- interestrates: UK (1729-) and US (1798-) short-term (ordinary / surplus funds) and long-term
  rates, each as "contemporary" and "consistent" series (see MW methodology).
- uscpi: US consumer price index 1774- (1982-84=100).
- ukearncpi: UK retail price index (1209-, 2010=100) and average nominal earnings (UK prices also in
  boe_millennium_uk, which stops in 2016). The form rejects the current year, so it asks up to Y-1.

source_id = measuringworth; series_id = mw_<cty>_<var>_a. Annual, dated Jan-1.
Raw: the HTML result pages returned by the MW forms (POST), kept intact.
Gold prices from MW are in `gold` (gold.py), not here.

Run: .venv/bin/python -m src.ingest.measuringworth [--refresh]
"""
from __future__ import annotations

import re
import sys
import time
from datetime import date

import pandas as pd
import requests

from ._extlong_common import UA, CatalogWriter, log, raw_dir

SRC = "measuringworth"
LIC = ("MeasuringWorth (Officer & Williamson); free for non-profit educational/research use with citation; "
       "contact MW before publishing >5 consecutive years")
Y = str(date.today().year)
FORMS = {
    "interestrates": ("https://www.measuringworth.com/datasets/interestrates/result.php",
                      {**{f"data{i}": "on" for i in range(1, 13)}, "year_source": "1700", "year_result": Y}),
    "uscpi": ("https://www.measuringworth.com/datasets/uscpi/result.php", {"year_source": "1774", "year_result": Y}),
    "ukearncpi": ("https://www.measuringworth.com/datasets/ukearncpi/result2.php",
                  {"use[]": ["CPI", "WAGE"], "year_source": "1209", "year_result": str(int(Y) - 1)}),
}


def fetch(name: str, refresh: bool) -> str:
    url, form = FORMS[name]
    dest = raw_dir(SRC) / f"{name}.html"
    fresh = dest.exists() and (time.time() - dest.stat().st_mtime) / 3600 < 24 * 7
    if refresh or not fresh:
        try:
            r = requests.post(url, data=form, headers={"User-Agent": UA}, timeout=120)
            r.raise_for_status()
            if r.text.count("<tr>") < 100:
                raise ValueError("no data table in MW response")
            dest.write_text(r.text, encoding="utf-8")
            log.info("downloaded MW %s (%d bytes)", name, len(r.content))
        except Exception as e:  # noqa: BLE001
            if not dest.exists():
                raise
            log.warning("MW %s failed (%s); using cached html", name, e)
    return dest.read_text(encoding="utf-8")


def _clean(x: str) -> str:
    x = re.sub(r"<br\s*/?>", " ", x)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>|&nbsp;|&pound;|&#36;|\*", " ", x)).strip()


def tables(html: str) -> list[pd.DataFrame]:
    """Each data table whose first header cell is 'Year' -> DataFrame indexed by year."""
    out = []
    for t in re.split(r"<table", html)[1:]:
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", t, flags=re.S)
        if not rows:
            continue
        hdr = [_clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", rows[0], flags=re.S)]
        if not hdr or hdr[0] != "Year":
            continue
        recs = []
        for r in rows[1:]:
            cells = [_clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", r, flags=re.S)]
            if cells and re.fullmatch(r"\d{4}", cells[0]) and len(cells) == len(hdr):
                recs.append(cells)
        if recs:
            df = pd.DataFrame(recs, columns=hdr).set_index("Year")
            df = df.apply(lambda c: pd.to_numeric(c.str.replace(",", ""), errors="coerce"))
            df.index = pd.to_datetime(df.index + "-01-01")
            out.append(df)
    return out


def _slug(col: str) -> str:
    c = col.lower()
    cty = "uk" if c.startswith("uk") else "us"
    term = "long" if "long-term" in c else ("short_ordinary" if "ordinary" in c else "short_surplus")
    kind = "consistent" if "consistent" in c else "contemporary"
    return f"mw_{cty}_rate_{term}_{kind}_a"


def main(refresh: bool = False) -> None:
    cw = CatalogWriter(SRC, url="https://www.measuringworth.com/", license=LIC)
    for df in tables(fetch("interestrates", refresh)):
        for col in df.columns:
            cw.add(_slug(col), df[col], name=f"MeasuringWorth {col}", category="rates", frequency="A",
                   units="% per year, annual average", country="GBR" if col.upper().startswith("UK") else "USA",
                   transform_notes="MW interest rates; 'consistent' = adjusted to a homogeneous concept across "
                                   "sources, 'contemporary' = as quoted at the time; short rates: ordinary vs surplus funds",
                   url="https://www.measuringworth.com/datasets/interestrates/")
    t = tables(fetch("uscpi", refresh))[0]
    cw.add("mw_us_cpi_a", t.iloc[:, 0], name="MeasuringWorth U.S. consumer price index", category="inflation",
           frequency="A", units="index 1982-84=100, annual average", country="USA",
           transform_notes="MW US CPI (David-Solar to 1912, BLS CPI-U after)",
           url="https://www.measuringworth.com/datasets/uscpi/")
    cw.add("mw_us_cpi_inflation_a", t.iloc[:, 0].pct_change(fill_method=None) * 100,
           name="MeasuringWorth U.S. CPI inflation (derived)", category="inflation", frequency="A", units="% y/y",
           country="USA", transform_notes="derived: pct change of mw_us_cpi_a",
           url="https://www.measuringworth.com/datasets/uscpi/")
    for df in tables(fetch("ukearncpi", refresh)):
        for col in df.columns:
            lc = col.lower()
            if "price" in lc or "cpi" in lc:
                sid, cat, units = "mw_uk_rpi_a", "inflation", "index 2010=100, annual average"
            elif "earn" in lc or "wage" in lc:
                sid, cat, units = "mw_uk_avg_earnings_a", "employment", "GBP per year (nominal average earnings)"
            else:
                continue
            cw.add(sid, df[col], name=f"MeasuringWorth UK {col}", category=cat, frequency="A", units=units,
                   country="GBR", transform_notes="MW UK earnings & CPI (Officer & Williamson)",
                   url="https://www.measuringworth.com/datasets/ukearncpi/")
    cat = cw.close()
    log.info("measuringworth: %d series", len(cat))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
