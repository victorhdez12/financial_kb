"""IMF Monetary and Financial Statistics (MFS), Monetary Aggregates: dinero amplio (broad money, definición nacional,
moneda nacional, mensual) de los países del panel internacional FUERA del euro y de EE. UU. (que ya tienen M3 del BCE
y M2 de FRED), vía la API SDMX 3.0 del FMI (dataflow IMF.STA/MFS_MA, indicador BM_MAI).

Ojo: «dinero amplio» es la definición nacional de cada país (M2/M3/M4), no comparable en nivel entre países; se usa
solo su variación interanual. La cobertura del FMI va con retraso desigual (algunos países con 6-12 meses).
Curado: imf_mfs_<iso>_broad_money_m (nivel, moneda nacional).

Run: .venv/bin/python -m src.ingest.imf_mfs [--refresh]
"""
from __future__ import annotations

import sys

from ._extlong_common import CatalogWriter, log, raw_dir
from .imf_weo import API, LIC, fetch_imf, parse_sdmx_json

SRC = "imf_mfs"
PAGE = "https://data.imf.org/en/datasets/IMF.STA:MFS_MA"
PAISES = ["GBR", "JPN", "CAN", "AUS", "SWE", "NOR", "DNK", "CHE"]


def main(refresh: bool = False) -> None:
    rd = raw_dir(SRC)
    js = fetch_imf(API + f"data/dataflow/IMF.STA/MFS_MA/+/{'+'.join(PAISES)}.BM_MAI.XDC.M"
                         "?dimensionAtObservation=TIME_PERIOD&attributes=series&measures=all",
                   rd / "mfs_ma_bm.json", refresh, min_age_hours=24)
    cw = CatalogWriter(SRC, url=PAGE, license=LIC)
    for dims, attrs, s in parse_sdmx_json(js):
        c = dims["COUNTRY"]
        s = s.dropna()
        if s.empty or c not in PAISES:
            continue
        cw.add(f"imf_mfs_{c.lower()}_broad_money_m", s, name=f"IMF MFS broad money (national definition), {c}",
               category="money", frequency="M", units="national currency", country=c,
               transform_notes="MFS_MA BM_MAI, XDC, monthly; national definition (not comparable across countries); "
                               "use y/y growth only")
    cat = cw.close()
    log.info("imf_mfs: %d series", len(cat))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
