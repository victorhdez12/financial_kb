"""OECD Analytical house prices (SDMX, DF_HOUSE_PRICES): índices trimestrales de precio (HPI) y de ALQUILER (RPI) por
país, para la medida realizada en vivo de la vivienda de INT-11 (docs/int/INT11_vivo_realizado_v0.md, V3 aprobada
5-nov-2026). series_id = oecd_hpi_<iso3>_q / oecd_rpi_<iso3>_q, trimestral fechado a inicio de trimestre.
Raw: $FIN_DATA_ROOT/raw/oecd_vivienda/house_prices.csv (+ archivo fechado, src/ingest/_archivo_raw.py).
Run: .venv/bin/python -m src.ingest.oecd_vivienda [--refresh]
"""
from __future__ import annotations

import sys
import time

import pandas as pd

from ._archivo_raw import archivar
from ._extlong_common import CatalogWriter, http_get, log, raw_dir

SRC = "oecd_vivienda"
PAGE = "https://data-explorer.oecd.org/"
LIC = "OECD data, CC BY 4.0 (OECD terms and conditions)"
AREAS = ["AUS", "BEL", "CAN", "CHE", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "IRL", "ITA", "JPN", "NLD", "NOR", "PRT",
         "SWE", "USA"]
URL = ("https://sdmx.oecd.org/public/rest/data/OECD.ECO.MPD,DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES,1.0/all?"
       "dimensionAtObservation=AllDimensions&format=csvfilewithlabels")
MEDIDAS = {"HPI": "nominal house price index", "RPI": "rent price index"}


def main() -> None:
    dest = raw_dir(SRC) / "house_prices.csv"
    fresh = dest.exists() and (time.time() - dest.stat().st_mtime) / 3600 < 20
    if "--refresh" in sys.argv or not fresh:
        try:
            r = http_get(URL, timeout=300)
            dest.write_bytes(r.content)
            archivar(raw_dir(SRC), "house_prices", r.content)
        except Exception as e:  # noqa: BLE001
            if not dest.exists():
                raise
            log.warning("descarga fallida (%s); se usa la caché", e)
    d = pd.read_csv(dest, usecols=["REF_AREA", "FREQ", "MEASURE", "TIME_PERIOD", "OBS_VALUE"])
    d = d[(d.FREQ == "Q") & d.MEASURE.isin(list(MEDIDAS)) & d.REF_AREA.isin(AREAS)]
    cw = CatalogWriter(SRC, url=PAGE, license=LIC)
    for (m, c), g in d.groupby(["MEASURE", "REF_AREA"]):
        idx = pd.PeriodIndex(g.TIME_PERIOD.str.replace("-Q", "Q"), freq="Q").to_timestamp(how="start")
        s = pd.Series(g.OBS_VALUE.astype(float).values, index=idx).sort_index()
        cw.add(f"oecd_{m.lower()}_{c.lower()}_q", s, name=f"OECD Analytical house prices {c}: {MEDIDAS[m]}",
               category="housing", frequency="Q", units="index", country=c,
               transform_notes="DF_HOUSE_PRICES (OECD.ECO.MPD); quarterly, dated at quarter start; latest release",
               url=URL)
    cat = cw.close()
    print(cat[["series_id", "start", "end"]].to_string(index=False))


if __name__ == "__main__":
    main()
