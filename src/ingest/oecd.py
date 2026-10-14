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
AREAS2 = AREAS + ["EA", "PRT", "GRC", "BEL", "AUT", "IRL", "FIN", "EU27_2020"]
A2 = "+".join(AREAS2)

QUERIES = {
    # REF_AREA.FREQ.MEASURE.UNIT_MEASURE.ACTIVITY.ADJUSTMENT.TRANSFORMATION.TIME_HORIZ.METHODOLOGY
    "cli": "OECD.SDD.STES,DSD_STES@DF_CLI,4.1/.M.LI+BCICP+CCICP.IX._Z.AA.IX._Z.H",
    # REF_AREA.MEASURE.UNIT_MEASURE.TRANSFORMATION.ADJUSTMENT.SEX.AGE.ACTIVITY.FREQ
    "unemp": f"OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M,1.0/{A}.UNE_LF_M.PT_LF_SUB._Z.Y._T.Y_GE15._Z.M",
    # REF_AREA.FREQ.MEASURE.UNIT_MEASURE.ACTIVITY.ADJUSTMENT.TRANSFORMATION.TIME_HORIZ.METHODOLOGY
    "finmark": f"OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0/{A}.M.IR3TIB+IRLT+IRSTCI+SHARE.......",
    # REF_AREA.FREQ.METHODOLOGY.MEASURE.UNIT_MEASURE.EXPENDITURE.ADJUSTMENT.TRANSFORMATION
    "cpi": f"OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/{A}.M.N.CPI.IX+PA._T+_TXCP01_NRG.N.",
    # COICOP 2018 dataflow: since the 2026 Eurostat ECOICOP-2 switch the OECD moved the euro-area
    # countries (ESP, FRA, ITA, NLD...), the euro area (now 'EA', changing composition) and others
    # here; the legacy DF_PRICES_ALL froze at 2025-12 for them (diagnosed 2026-10-13).
    "cpi2": f"OECD.SDD.TPS,DSD_PRICES_COICOP2018@DF_PRICES_C2018_ALL,1.0/{A2}.M.N.CPI.IX+PA._T+_TXCP01_NRG.N.",
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
    for name in ("cli", "unemp", "finmark"):  # cpi/cpi2 handled below
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
    try:
        d2 = fetch("cpi2", QUERIES["cpi2"], refresh)
    except Exception as e:  # noqa: BLE001
        log.warning("oecd cpi2 (COICOP 2018) unavailable: %s", e)
        d2 = None

    def cpi_key(df):
        out = {}
        for (area, um, exp, tr), g in df.groupby(["REF_AREA", "UNIT_MEASURE", "EXPENDITURE", "TRANSFORMATION"]):
            core = exp != "_T"
            if exp not in ("_T", "_TXCP01_NRG"):
                continue
            if um == "IX" and tr == "_Z":
                kind = "idx"
            elif um == "PA" and tr == "GY":
                kind = "yoy"
            else:
                continue
            out[(area, core, kind)] = g
        return out

    old_d = cpi_key(d)
    new_d = cpi_key(d2) if d2 is not None else {}
    for key in sorted(set(old_d) | set(new_d)):
        area, core, kind = key
        g_old, g_new = old_d.get(key), new_d.get(key)
        sid = f"oecd_cpi{'core' if core else ''}_{area.lower()}_{kind}"
        units, what = ("index 2015=100", "index") if kind == "idx" else ("% y/y", "y/y inflation")
        s_old = _series(g_old, zero_is_missing=kind == "idx") if g_old is not None else pd.Series(dtype=float)
        s_new = _series(g_new, zero_is_missing=kind == "idx") if g_new is not None else pd.Series(dtype=float)
        s_old, s_new = s_old.dropna(), s_new.dropna()
        src_g = g_old if g_old is not None else g_new
        note = f"OECD DF_PRICES_ALL {area}; national methodology"
        s = s_old
        if g_old is None:
            s = s_new
            note = f"OECD DF_PRICES_C2018_ALL (COICOP 2018) {area}; legacy DF_PRICES_ALL has no data for this area"
        elif len(s_new) and (s_old.empty or s_new.index.max() > s_old.index.max()):
            # extend the stale legacy series with the COICOP-2018 flow after its last month
            f = 1.0
            ov = s_old.index.intersection(s_new.index)[-12:]
            if kind == "idx" and len(ov):
                f = float((s_old[ov] / s_new[ov]).mean())
            tail = s_new[s_new.index > s_old.index.max()] * f
            s = pd.concat([s_old, tail])
            note = (f"SPLICE: DF_PRICES_ALL {area} to {s_old.index.max():%Y-%m}, then DF_PRICES_C2018_ALL (COICOP 2018) "
                    f"after (rescale factor {f:.5f} on {len(ov)} overlap months; both base 2015=100). The legacy flow froze at "
                    "2025-12 for the euro-area countries after the 2026 Eurostat ECOICOP-2 switch.")
        nm = f"OECD CPI {'ex food & energy' if core else 'all items'} {what} (NSA), {src_g['Reference area'].iloc[0]}"
        if area == "EA":
            nm += " (changing composition, successor of EA20)"
        n["cpi"] = n.get("cpi", 0) + (cw.add(sid, s, name=nm, category="inflation", frequency="M", units=units, country=area,
                                             transform_notes=note) > 0)
    cat = cw.close()
    log.info("oecd: %s -> %d series", n, len(cat))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
