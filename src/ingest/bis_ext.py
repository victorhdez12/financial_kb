"""BIS bulk data, extension of `bis` (cycle_bis.py) with datasets it does not cover:
effective exchange rates (WS_EER), global liquidity indicators (WS_GLI), long consumer price
series (WS_LONG_CPI, back to the 19th century for several countries) and US dollar exchange
rates (WS_XRU).

Kept as a separate source_id (`bis_ext`) so that cycle_bis.py (which deletes stale parquet in
curated/bis) and this script never step on each other. Credit, credit gaps, DSR, total credit
(incl. bank credit and government debt) and property prices stay in `bis`.

series_id = bis_<dataset>_<cty>_<codes>, cty = BIS 2-letter code lower case (xm = euro area).
Country column = ISO3 when it is a country, BIS code otherwise (aggregates).
Curation criterion: G20 + euro area + Spain/Netherlands/Switzerland (FOCUS) for EER, CPI and XRU;
all GLI series (they are global aggregates). Raw zips are kept complete.

Run: .venv/bin/python -m src.ingest.bis_ext [--refresh]
"""
from __future__ import annotations

import sys
import zipfile

import pandas as pd

from ._extlong_common import CatalogWriter, download, log, raw_dir

SRC = "bis_ext"
BULK = "https://data.bis.org/static/bulk/{}_csv_flat.zip"
LIC = "BIS statistics, free reuse with attribution (BIS terms of use)"
DATASETS = ["WS_EER", "WS_GLI", "WS_LONG_CPI", "WS_XRU"]

ISO3 = {"US": "USA", "XM": "EA", "DE": "DEU", "FR": "FRA", "IT": "ITA", "ES": "ESP", "NL": "NLD",
        "GB": "GBR", "JP": "JPN", "CN": "CHN", "CA": "CAN", "CH": "CHE", "AU": "AUS", "KR": "KOR",
        "IN": "IND", "BR": "BRA", "MX": "MEX", "RU": "RUS", "ZA": "ZAF", "TR": "TUR", "ID": "IDN",
        "SA": "SAU", "AR": "ARG", "SE": "SWE", "NO": "NOR", "5C": "EA"}
FOCUS = [k for k in ISO3 if k not in ("SE", "NO", "5C")]


def _code(x) -> str:
    return str(x).split(":")[0].strip()


def _label(x) -> str:
    s = str(x)
    return s.split(":", 1)[1].strip() if ":" in s else s


def _date(tp: pd.Series) -> pd.DatetimeIndex:
    tp = tp.astype(str)
    if tp.str.contains("-Q").any():
        return pd.PeriodIndex(tp.str.replace("-Q", "Q"), freq="Q").start_time
    if tp.str.len().max() == 7:
        return pd.PeriodIndex(tp, freq="M").start_time
    if tp.str.len().max() == 4:
        return pd.PeriodIndex(tp, freq="Y").start_time
    return pd.to_datetime(tp)


def _read(rd, ds, filt=None) -> pd.DataFrame:
    z = zipfile.ZipFile(rd / f"{ds}_csv_flat.zip")
    parts = []
    for ch in pd.read_csv(z.open(z.namelist()[0]), chunksize=500_000, low_memory=False):
        if filt is not None:
            ch = ch[filt(ch)]
        parts.append(ch)
    d = pd.concat(parts)
    d.columns = [c.split(":")[0] for c in d.columns]
    return d.dropna(subset=["TIME_PERIOD"])


def _first(col: str):
    return lambda ch: ch[[c for c in ch.columns if c.startswith(col + ":")][0]].astype(str).str.split(":").str[0]


def _country(cty: str) -> str:
    return ISO3.get(cty, cty)


def _emit(cw, d, keys, make_id, make_meta, cty_key):
    n = 0
    for k, g in d.groupby(keys):
        k = k if isinstance(k, tuple) else (k,)
        codes = [_code(x) for x in k]
        s = pd.Series(pd.to_numeric(g["OBS_VALUE"], errors="coerce").values, index=_date(g["TIME_PERIOD"]))
        name, cat, units, freq = make_meta(g.iloc[0], *codes)
        n += cw.add(make_id(*codes), s, name=name, category=cat, frequency=freq, units=units,
                    country=_country(_code(g.iloc[0][cty_key])),
                    transform_notes=f"BIS bulk {keys}={tuple(codes)}; quarterly/monthly dated at period start") > 0
    return n


def main(refresh: bool = False) -> None:
    rd = raw_dir(SRC)
    for ds in DATASETS:
        download(BULK.format(ds), rd / f"{ds}_csv_flat.zip", "zip", min_age_hours=0 if refresh else 20)
    cw = CatalogWriter(SRC, url="https://data.bis.org/", license=LIC)

    # Effective exchange rates: monthly averages, broad (64 economies, 1994-) and narrow (27, 1964-) baskets
    f = lambda ch: (_first("FREQ")(ch) == "M") & _first("EER_BASKET")(ch).isin(["B", "N"]) & _first("REF_AREA")(ch).isin(FOCUS)  # noqa: E731
    d = _read(rd, "WS_EER", filt=f)
    n = _emit(cw, d, ["REF_AREA", "EER_TYPE", "EER_BASKET"],
              lambda c, t, b: f"bis_eer_{c.lower()}_{'neer' if t == 'N' else 'reer'}{'' if b == 'B' else '_narrow'}_m",
              lambda r, c, t, b: (f"BIS {'nominal' if t == 'N' else 'real (CPI-based)'} effective exchange rate, "
                               f"{'broad basket (64 economies, from 1994)' if b == 'B' else 'narrow basket (27 economies, long history)'}, {_label(r['REF_AREA'])}", "fx",
                               "index 2020=100, monthly average; up = appreciation", "M"), "REF_AREA")
    log.info("eer series: %d", n)

    # Global liquidity indicators: all series (global / regional aggregates + major EMs)
    d = _read(rd, "WS_GLI")
    keys = ["CURR_DENOM", "BORROWERS_CTY", "BORROWERS_SECTOR", "LENDERS_SECTOR", "L_POS_TYPE", "L_INSTR", "UNIT_MEASURE"]
    um = {"771": "yoy", "770": "gdp", "USD": "usd", "EUR": "eur", "JPY": "jpy"}
    n = _emit(cw, d, keys,
              lambda cur, cty, bs, ls, pt, ins, u: f"bis_gli_{cur.lower()}_{cty.lower()}_{bs.lower()}{ls.lower()}{pt.lower()}{ins.lower()}_{um.get(u, u.lower())}",
              lambda r, cur, cty, bs, ls, pt, ins, u: (
                  f"BIS global liquidity: {_label(r['TITLE'])} [{_label(r['CURR_DENOM'])}; {_label(r['L_INSTR'])}; "
                  f"{_label(r['L_POS_TYPE'])}; lenders {_label(r['LENDERS_SECTOR'])}]", "liquidity",
                  _label(r["UNIT_MEASURE"]) + (" (millions)" if u in ("USD", "EUR", "JPY") else ""), "Q"),
              "BORROWERS_CTY")
    log.info("gli series: %d", n)

    # Long CPI: monthly index 2010=100 and annual y/y
    f = lambda ch: _first("REF_AREA")(ch).isin(FOCUS)  # noqa: E731
    d = _read(rd, "WS_LONG_CPI", filt=f)
    d = d[((d["FREQ"].astype(str).str[0] == "M") & (d["UNIT_MEASURE"].astype(str).str[:3] == "628")) |
          ((d["FREQ"].astype(str).str[0] == "A") & (d["UNIT_MEASURE"].astype(str).str[:3] == "771"))]
    n = _emit(cw, d, ["REF_AREA", "FREQ"],
              lambda c, fq: f"bis_cpi_{c.lower()}_{'idx_m' if fq == 'M' else 'yoy_a'}",
              lambda r, c, fq: (f"BIS long consumer price {'index (monthly)' if fq == 'M' else 'inflation (annual, y/y)'}, "
                                f"{_label(r['REF_AREA'])}", "inflation",
                                "index 2010=100" if fq == "M" else "% y/y", fq), "REF_AREA")
    log.info("long cpi series: %d", n)

    # USD exchange rates: monthly average, national currency per USD
    f = lambda ch: (_first("FREQ")(ch) == "M") & (_first("COLLECTION")(ch) == "A") & _first("REF_AREA")(ch).isin([c for c in FOCUS if c != "US"])  # noqa: E731
    d = _read(rd, "WS_XRU", filt=f)
    n = _emit(cw, d, ["REF_AREA", "CURRENCY"],
              lambda c, cur: f"bis_xru_{c.lower()}_{cur.lower()}_m",
              lambda r, c, cur: (f"BIS exchange rate {cur} per USD (monthly average), {_label(r['REF_AREA'])}", "fx",
                                 f"{cur} per USD", "M"), "REF_AREA")
    log.info("xru series: %d", n)
    cat = cw.close()
    log.info("bis_ext: %d series", len(cat))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
