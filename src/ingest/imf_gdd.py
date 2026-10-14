"""IMF Global Debt Database (GDD, Mbaye, Moreno-Badia & Chae 2018): private (households, NFC)
and public debt, % of GDP, annual 1950-, via the IMF SDMX 3.0 API (dataflow IMF.FAD/GDD).

Raw: complete dataset (190 countries x 11 indicators) as SDMX-JSON. Curated: all debt-ratio
indicators (GDP levels skipped) for the major economies (imf_weo.COUNTRIES).
series_id = imf_gdd_<iso>_<indicator lower>. Annual obs dated Jan-1.

Run: .venv/bin/python -m src.ingest.imf_gdd [--refresh]
"""
from __future__ import annotations

import sys

from ._extlong_common import CatalogWriter, log, raw_dir
from .imf_weo import API, COUNTRIES, ISO_OUT, LIC, codelist_names, fetch_imf, parse_sdmx_json

SRC = "imf_gdd"
PAGE = "https://data.imf.org/en/datasets/IMF.FAD:GDD"


def main(refresh: bool = False) -> None:
    rd = raw_dir(SRC)
    js = fetch_imf(API + "data/dataflow/IMF.FAD/GDD/+/*?dimensionAtObservation=TIME_PERIOD&attributes=series&measures=all",
                   rd / "gdd_all.json", refresh, min_age_hours=24 * 7)
    stc = fetch_imf(API + "structure/dataflow/IMF.FAD/GDD/+?references=descendants", rd / "gdd_structure.json",
                    refresh, min_age_hours=24 * 30, accept="application/json")
    names = codelist_names(stc)
    ind, cty = names.get("CL_GDD_INDICATOR", {}), names.get("CL_COUNTRY", {})
    cw = CatalogWriter(SRC, url=PAGE, license=LIC + "; cite IMF Global Debt Database (Mbaye et al. 2018)")
    for dims, attrs, s in parse_sdmx_json(js):
        c, i = dims["COUNTRY"], dims["INDICATOR"]
        if c not in COUNTRIES or not i.endswith("POGDP_PT"):
            continue
        cat = "fiscal" if any(k in i for k in ("S13", "S1311", "S11001", "S1ZS")) else "credit"
        cw.add(f"imf_gdd_{ISO_OUT.get(c, c).lower()}_{i.lower()}", s, name=f"IMF GDD {ind.get(i, i)}, {cty.get(c, c)}",
               category=cat, frequency="A", units="% of GDP", country=ISO_OUT.get(c, c),
               transform_notes=f"GDD {i}; data_source={attrs.get('DATA_SOURCE', '')}; "
                               "'Debt instruments' = all instruments, 'Debt securities and loans' = F3+F4 only")
    cat = cw.close()
    log.info("imf_gdd: %d series", len(cat))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
