"""INE (Instituto Nacional de Estadística) - Tempus3 JSON API (no key).

CPI (annual rate since 1962, index and core since 2002), EPA unemployment rate (base 2021,
from 2002), quarterly national accounts GDP (chain-linked volume index, SCA, from 1995) and
the housing price index IPV (from 2007).

Run: .venv/bin/python -m src.ingest.ine
Raw:     $FIN_DATA_ROOT/raw/ine/<COD>.json
Curated: $FIN_DATA_ROOT/curated/ine/ine_*.parquet + _catalog.csv
"""
from __future__ import annotations

import json

import pandas as pd

from src.ingest._europe_common import CatalogWriter, add_series, cached_get, log, raw_dir

SOURCE = "ine"
API = "https://servicios.ine.es/wstempus/js/ES/DATOS_SERIE/{cod}?nult=5000"
SERIE_URL = "https://www.ine.es/consul/serie.do?s={cod}"
LICENSE = "INE: free re-use with attribution (Aviso legal INE, CC BY 4.0-compatible)"

# (series_id, INE code, name, category, freq, units, positive, notes)
SEL = [
    ("ine_ipc_yoy_m", "IPC290750", "Spain CPI (IPC), general index, annual rate", "inflation", "M", "% y/y", False,
     "Official annual rate published since 1962 (computed on the successive INE bases)."),
    ("ine_ipc_index_m", "IPC290751", "Spain CPI (IPC), general index", "inflation", "M", "index (base 2021=100)", True,
     "Tempus only serves the index from 2002; for 1954+ use bde_es_cpi_m."),
    ("ine_ipc_core_yoy_m", "IPC292510", "Spain core CPI (excl. unprocessed food and energy), annual rate", "inflation", "M", "% y/y", False, ""),
    ("ine_ipc_core_index_m", "IPC292511", "Spain core CPI (excl. unprocessed food and energy), index", "inflation", "M", "index (base 2021=100)", True, ""),
    ("ine_epa_unemp_rate_q", "EPA423474", "EPA unemployment rate, total, both sexes (base 2021)", "employment", "Q", "% of active population", True,
     "Base-2021 EPA series, back-calculated to 2002. Pre-2002 EPA (from 1976) is not served by Tempus (see docs gap)."),
    ("ine_epa_unemp_rate_16_19_q", "EPA423476", "EPA unemployment rate, ages 16-19", "employment", "Q", "% of active population", True, ""),
    ("ine_epa_unemp_rate_20_24_q", "EPA423477", "EPA unemployment rate, ages 20-24", "employment", "Q", "% of active population", True, ""),
    ("ine_gdp_volume_index_q", "CNTR6652", "Spain GDP at market prices, chain-linked volume index, SCA", "growth", "Q", "index (2020=100)", True,
     "Quarterly National Accounts (CNTR), seasonally and calendar adjusted."),
    ("ine_gdp_qoq_q", "CNTR6653", "Spain real GDP growth, q/q, SCA", "growth", "Q", "% q/q", False, ""),
    ("ine_gdp_yoy_q", "CNTR6654", "Spain real GDP growth, y/y, SCA", "growth", "Q", "% y/y", False, ""),
    ("ine_ipv_index_q", "IPV1209", "Spain housing price index (IPV), general", "housing", "Q", "index (2015=100)", True, "Transaction-based, from 2007."),
    ("ine_ipv_yoy_q", "IPV1376", "Spain housing price index (IPV), annual rate", "housing", "Q", "% y/y", False, ""),
    ("ine_ipv_new_index_q", "IPV1613", "Spain housing price index (IPV), new dwellings", "housing", "Q", "index (2015=100)", True, ""),
]


def period_start(anyo: int, per: int) -> pd.Timestamp | None:
    if 1 <= per <= 12:
        return pd.Timestamp(anyo, per, 1)
    if 19 <= per <= 22:
        return pd.Timestamp(anyo, 3 * (per - 18) - 2, 1)
    if per == 28:
        return pd.Timestamp(anyo, 1, 1)
    return None


def fetch(cod: str) -> tuple[pd.Series, str]:
    content = cached_get(API.format(cod=cod), raw_dir(SOURCE) / f"{cod}.json", min_bytes=100)
    d = json.loads(content)
    idx, vals = [], []
    for x in d.get("Data", []):
        t = period_start(int(x["Anyo"]), int(x["FK_Periodo"]))
        if t is None:
            continue
        idx.append(t)
        v = x.get("Valor")
        vals.append(float("nan") if v is None or x.get("Secreto") else float(v))
    return pd.Series(vals, index=pd.DatetimeIndex(idx)).sort_index(), d.get("Nombre", "")


def main() -> pd.DataFrame:
    cw = CatalogWriter(SOURCE, url="https://www.ine.es/dyngs/DataLab/manual.html?cid=45", license=LICENSE)
    for sid, cod, name, cat, freq, units, pos, notes in SEL:
        try:
            s, nombre = fetch(cod)
        except Exception as e:  # noqa: BLE001
            log.warning("%s (%s) failed: %s", sid, cod, e)
            continue
        n = add_series(cw, sid, s, positive=pos, name=name, category=cat, frequency=freq, units=units, country="ES",
                       transform_notes=f"INE Tempus series {cod}: {nombre.strip()} {notes}".strip(), url=SERIE_URL.format(cod=cod))
        log.info("%-30s %5d obs", sid, n)
    return cw.close()


if __name__ == "__main__":
    main()
