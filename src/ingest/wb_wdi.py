"""World Bank World Development Indicators (API v2, api.worldbank.org): key annual macro
indicators for the major economies.

source_id = wb_wdi. series_id = wdi_<iso3>_<indicator code lower, dots -> _>.
Raw: one JSON per indicator (API response for all COUNTRIES). Annual obs dated Jan-1.
Curation criterion: G20 members + euro area members ES/NL + CH + aggregates (EMU, WLD, OED,
LMY); INDICATORS below. The whole WDI (1,400 indicators x 266 economies) is not mirrored.

Run: .venv/bin/python -m src.ingest.wb_wdi [--refresh]
"""
from __future__ import annotations

import json
import sys
import time

import pandas as pd

from ._extlong_common import CatalogWriter, http_get, log, raw_dir

SRC = "wb_wdi"
API = "https://api.worldbank.org/v2/country/{c}/indicator/{i}?format=json&per_page=20000"
LIC = "CC BY 4.0 (World Bank)"
PAGE = "https://databank.worldbank.org/source/world-development-indicators"
COUNTRIES = ["USA", "EMU", "DEU", "FRA", "ITA", "ESP", "NLD", "GBR", "JPN", "CHN", "CAN", "CHE", "AUS", "KOR",
             "IND", "BRA", "MEX", "RUS", "ZAF", "TUR", "IDN", "SAU", "ARG", "WLD", "OED", "LMY"]
ISO_OUT = {"EMU": "EA", "OED": "OECD"}
INDICATORS = {  # code -> (category, units)
    "NY.GDP.MKTP.KD.ZG": ("growth", "% y/y, constant prices"),
    "NY.GDP.MKTP.CD": ("growth", "current USD"),
    "NY.GDP.PCAP.PP.KD": ("growth", "constant 2021 international $ (PPP) per capita"),
    "SP.POP.TOTL": ("growth", "persons"),
    "FP.CPI.TOTL.ZG": ("inflation", "% y/y, annual average CPI"),
    "NY.GDP.DEFL.KD.ZG": ("inflation", "% y/y, GDP deflator"),
    "SL.UEM.TOTL.ZS": ("employment", "% of labour force (ILO modelled estimate)"),
    "FS.AST.DOMS.GD.ZS": ("credit", "% of GDP"),
    "FS.AST.PRVT.GD.ZS": ("credit", "% of GDP"),
    "FD.AST.PRVT.GD.ZS": ("credit", "% of GDP"),
    "FR.INR.RINR": ("rates", "% (lending rate deflated by GDP deflator)"),
    "BN.CAB.XOKA.GD.ZS": ("growth", "% of GDP"),
    "NE.TRD.GNFS.ZS": ("growth", "% of GDP"),
    "FI.RES.TOTL.CD": ("fx", "current USD"),
    "FI.RES.TOTL.MO": ("fx", "months of imports"),
    "GC.DOD.TOTL.GD.ZS": ("fiscal", "% of GDP"),
}


def fetch(ind: str, refresh: bool) -> list:
    dest = raw_dir(SRC) / f"{ind}.json"
    fresh = dest.exists() and (time.time() - dest.stat().st_mtime) / 3600 < 20
    if refresh or not fresh:
        try:
            r = http_get(API.format(c=";".join(COUNTRIES), i=ind), timeout=180)
            js = r.json()
            if not isinstance(js, list) or len(js) < 2 or js[1] is None:
                raise ValueError(str(js)[:200])
            if js[0].get("pages", 1) > 1:
                raise ValueError("paged response, raise per_page")
            dest.write_bytes(r.content)
            log.info("downloaded wdi %s (%d rows)", ind, len(js[1]))
        except Exception as e:  # noqa: BLE001
            if not dest.exists():
                raise
            log.warning("wdi %s failed (%s); using cached raw", ind, e)
    return json.loads(dest.read_text())


def main(refresh: bool = False) -> None:
    cw = CatalogWriter(SRC, url=PAGE, license=LIC)
    for ind, (cat, units) in INDICATORS.items():
        meta, rows = fetch(ind, refresh)
        d = pd.DataFrame([{"iso": r["countryiso3code"] or r["country"]["id"], "cty": r["country"]["value"], "ind": r["indicator"]["value"],
                           "year": int(r["date"]), "value": r["value"]} for r in rows])
        for iso, g in d.groupby("iso"):
            iso_o = ISO_OUT.get(iso, iso)
            s = pd.Series(pd.to_numeric(g["value"], errors="coerce").values,
                          index=pd.to_datetime(g["year"].astype(str) + "-01-01"))
            cw.add(f"wdi_{iso_o.lower()}_{ind.lower().replace('.', '_')}", s,
                   name=f"WB WDI {g['ind'].iloc[0]}, {g['cty'].iloc[0]}", category=cat, frequency="A", units=units,
                   country=iso_o, transform_notes=f"WDI {ind}; last updated {meta.get('lastupdated', '?')}")
        time.sleep(1)
    out = cw.close()
    log.info("wb_wdi: %d series", len(out))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
