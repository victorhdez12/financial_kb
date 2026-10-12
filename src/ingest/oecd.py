"""OECD Data Explorer (SDMX REST, sdmx.oecd.org): composite leading indicators, business and
consumer confidence (all areas available), harmonised unemployment, short/long interest rates,
share prices and CPI (major economies).

source_id = oecd. series_id = oecd_<measure>_<area>[_<variant>], area = OECD code lower case
(ISO3 for countries; ea20, oecd, g7, g20... for aggregates).
Monthly obs dated at month start. Raw = one CSV per query (the full API response, with labels).

Curation criterion:
- CLI (LI, amplitude adjusted), BCI and CCI: every area published (~50).
- Unemployment, rates, share prices, CPI: AREAS (G20-ish + euro area + Spain/NL/CH + aggregates).
The OECD API is rate limited (~20 queries/hour): only 5 queries, cached for 20 h.

Run: .venv/bin/python -m src.ingest.oecd [--refresh]
"""
from __future__ import annotations

import sys
import time

import pandas as pd

from ._extlong_common import CatalogWriter, http_get, log, raw_dir

SRC = "oecd"
BASE = "https://sdmx.oecd.org/public/rest/data/"
LIC = "OECD data, CC BY 4.0 (OECD terms and conditions)"
PAGE = "https://data-explorer.oecd.org/"
AREAS = ["USA", "EA20", "DEU", "FRA", "ITA", "ESP", "NLD", "GBR", "JPN", "CHN", "CAN", "CHE", "AUS",
         "KOR", "IND", "BRA", "MEX", "ZAF", "TUR", "IDN", "SWE", "OECD", "G7"]
A = "+".join(AREAS)

QUERIES = {
    # REF_AREA.FREQ.MEASURE.UNIT_MEASURE.ACTIVITY.ADJUSTMENT.TRANSFORMATION.TIME_HORIZ.METHODOLOGY
    "cli": "OECD.SDD.STES,DSD_STES@DF_CLI,4.1/.M.LI+BCICP+CCICP.IX._Z.AA.IX._Z.H",
    # REF_AREA.MEASURE.UNIT_MEASURE.TRANSFORMATION.ADJUSTMENT.SEX.AGE.ACTIVITY.FREQ
    "unemp": f"OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0/{A}.UNE_LF_M.PT_LF_SUB._Z.Y._T.Y_GE15._Z.M",
    # REF_AREA.FREQ.MEASURE.UNIT_MEASURE.ACTIVITY.ADJUSTMENT.TRANSFORMATION.TIME_HORIZ.METHODOLOGY
    "finmark": f"OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0/{A}.M.IR3TIB+IRLT+IRSTCI+SHARE.......",
    # REF_AREA.FREQ.METHODOLOGY.MEASURE.UNIT_MEASURE.EXPENDITURE.ADJUSTMENT.TRANSFORMATION
    "cpi": f"OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/{A}.M.N.CPI.IX+PA._T+_TXCP01_NRG.N.",
}

META = {  # measure code -> (slug, name, category, units)
    "LI": ("cli", "OECD composite leading indicator (amplitude adjusted)", "growth", "index, long-term average=100"),
    "BCICP": ("bci", "OECD composite business confidence indicator (amplitude adjusted)", "growth", "index, long-term average=100"),
    "CCICP": ("cci", "OECD composite consumer confidence indicator (amplitude adjusted)", "growth", "index, long-term average=100"),
    "UNE_LF_M": ("unemp", "OECD harmonised unemployment rate, total 15+, SA", "employment", "% of labour force"),
    "IR3TIB": ("ir3m", "OECD short-term interest rate (3-month interbank/T-bill)", "rates", "% per annum, monthly average"),
    "IRLT": ("irlt", "OECD long-term interest rate (10-year government bond)", "rates", "% per annum, monthly average"),
    "IRSTCI": ("ircall", "OECD immediate interest rate (call money / interbank overnight)", "rates", "% per annum, monthly average"),
    "SHARE": ("share", "OECD share price index", "markets", "index 2015=100"),
}


def fetch(name: str, q: str, refresh: bool) -> pd.DataFrame:
    dest = raw_dir(SRC) / f"{name}.csv"
    fresh = dest.exists() and (time.time() - dest.stat().st_mtime) / 3600 < 20
    if refresh or not fresh:
        try:
            r = http_get(BASE + q + "?format=csvfilewithlabels", timeout=300)
            if b"TIME_PERIOD" not in r.content[:3000]:
                raise ValueError(r.text[:200])
            dest.write_bytes(r.content)
            log.info("downloaded oecd %s (%d bytes)", name, len(r.content))
            time.sleep(5)
        except Exception as e:  # noqa: BLE001
            if not dest.exists():
                raise
            log.warning("oecd %s failed (%s); using cached raw", name, e)
    return pd.read_csv(dest, low_memory=False)


def _series(g: pd.DataFrame, zero_is_missing: bool = False) -> pd.Series:
    """`zero_is_missing` for price/share indices: OECD fills unpublished months with 0
    (e.g. Brazil share prices, 105 zeros) — an index level of 0 is impossible."""
    idx = pd.PeriodIndex(g["TIME_PERIOD"].astype(str), freq="M").start_time
    s = pd.Series(pd.to_numeric(g["OBS_VALUE"], errors="coerce").values, index=idx)
    return s.mask(s == 0) if zero_is_missing else s


def main(refresh: bool = False) -> None:
    cw = CatalogWriter(SRC, url=PAGE, license=LIC)
    n = {}
    for name in ("cli", "unemp", "finmark"):
        d = fetch(name, QUERIES[name], refresh)
        keys = ["REF_AREA", "MEASURE"] + (["UNIT_MEASURE"] if name == "finmark" else [])
        for k, g in d.groupby(keys):
            area, meas = k[0], k[1]
            if name == "finmark" and meas == "SHARE" and k[2] != "IX":
                continue
            slug, nm, cat, units = META[meas]
            n[name] = n.get(name, 0) + (cw.add(
                f"oecd_{slug}_{area.lower()}", _series(g, zero_is_missing=units.startswith("index")), name=f"{nm}, {g['Reference area'].iloc[0]}",
                category=cat, frequency="M", units=units, country=area,
                transform_notes=f"OECD SDMX {QUERIES[name].split('/')[0]} key {'.'.join(map(str, k))}; "
                                "monthly, dated at month start", url=PAGE) > 0)
    d = fetch("cpi", QUERIES["cpi"], refresh)
    for (area, um, exp, tr), g in d.groupby(["REF_AREA", "UNIT_MEASURE", "EXPENDITURE", "TRANSFORMATION"]):
        core = exp != "_T"
        if um == "IX" and tr == "_Z":
            sid, units, what = "idx", "index 2015=100", "index"
        elif um == "PA" and tr == "GY":
            sid, units, what = "yoy", "% y/y", "y/y inflation"
        else:
            continue
        sid = f"oecd_cpi{'core' if core else ''}_{area.lower()}_{sid}"
        nm = f"OECD CPI {'ex food & energy' if core else 'all items'} {what} (NSA), {g['Reference area'].iloc[0]}"
        n["cpi"] = n.get("cpi", 0) + (cw.add(sid, _series(g, zero_is_missing=um == "IX"), name=nm, category="inflation", frequency="M",
                                             units=units, country=area,
                                             transform_notes=f"OECD DF_PRICES_ALL {area}.{um}.{exp}.{tr}; national methodology") > 0)
    cat = cw.close()
    log.info("oecd: %s -> %d series", n, len(cat))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
