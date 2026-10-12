"""IMF Historical Public Debt Database (HPDD, Abbas et al. 2010): general government gross debt,
% of (fiscal-year) GDP, annual 1800-2015, via the IMF SDMX 3.0 API (dataflow IMF.FAD/HPD).

Raw: complete dataset (191 countries) as SDMX-JSON. Curated: imf_hpdd_<iso>_debt_gdp for the
major economies (imf_weo.COUNTRIES) plus every country whose series starts before 1914
(long-history criterion). Annual obs dated Jan-1. The database is frozen at 2015 (for later years
use imf_weo_*_ggxwdg_ngdp or imf_gdd_*).

Run: .venv/bin/python -m src.ingest.imf_hpdd [--refresh]
"""
from __future__ import annotations

import sys

from ._extlong_common import CatalogWriter, log, raw_dir
from .imf_weo import API, COUNTRIES, ISO_OUT, LIC, codelist_names, fetch_imf, parse_sdmx_json

SRC = "imf_hpdd"
PAGE = "https://data.imf.org/en/datasets/IMF.FAD:HPD"


def main(refresh: bool = False) -> None:
    rd = raw_dir(SRC)
    js = fetch_imf(API + "data/dataflow/IMF.FAD/HPD/+/*?dimensionAtObservation=TIME_PERIOD&attributes=series&measures=all",
                   rd / "hpd_all.json", refresh, min_age_hours=24 * 7)
    stc = fetch_imf(API + "structure/dataflow/IMF.FAD/HPD/+?references=descendants", rd / "hpd_structure.json",
                    refresh, min_age_hours=24 * 30, accept="application/json")
    cty = codelist_names(stc).get("CL_COUNTRY", {})
    cw = CatalogWriter(SRC, url=PAGE, license=LIC + "; cite Abbas, Belhocine, El-Ganainy & Horton (2010)")
    for dims, attrs, s in parse_sdmx_json(js):
        c = dims["COUNTRY"]
        s = s.dropna()
        if s.empty or (c not in COUNTRIES and s.index.min().year >= 1914):
            continue
        cw.add(f"imf_hpdd_{ISO_OUT.get(c, c).lower()}_debt_gdp", s, name=f"IMF HPDD general government gross debt, {cty.get(c, c)}",
               category="fiscal", frequency="A", units="% of fiscal-year GDP", country=ISO_OUT.get(c, c),
               transform_notes=f"HPD {dims['INDICATOR']}; methodology={attrs.get('METHODOLOGY', '')}; "
                               "coverage may switch central/general government over time (see IMF HPDD notes)")
    cat = cw.close()
    log.info("imf_hpdd: %d series", len(cat))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
