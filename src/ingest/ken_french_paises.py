"""Kenneth R. French Data Library: International Countries (rentabilidad mensual en MONEDA LOCAL por país, con y sin
dividendos). Contraste anual de la bolsa en vivo de INT-11 (docs/int/INT11_fuente_bolsa_vivo.md, A2/A5 aprobadas
5-nov-2026). Parser: src/report/bolsa_vivo.french_pais_local (el mismo que midió las fuentes).
Run: .venv/bin/python -m src.ingest.ken_french_paises
Curated: ffc_<iso3>_<tr|precio>_m  (percent per month, local currency). No se redistribuye (licencia de French).
"""
from __future__ import annotations

import zipfile

from src.ingest._extlong_common import CatalogWriter, download, log, raw_dir
from src.ingest.ken_french_intl import LIB, LICENSE
from src.report.bolsa_vivo import FRENCH_PAIS, french_pais_local

SOURCE = "ken_french_paises"
URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_International_Countries{}.zip"


def main() -> None:
    cw = CatalogWriter(SOURCE, url=LIB, license=LICENSE)
    for k, suf in (("tr", ""), ("precio", "_Wout_Div")):
        dest = raw_dir(SOURCE) / f"F-F_International_Countries{suf}.zip"
        try:
            download(URL.format(suf), dest, "zip")
        except Exception as e:  # noqa: BLE001
            if not dest.exists():
                log.error("skip %s: %s", k, e)
                continue
            log.warning("%s download failed (%s); cached", k, e)
        with zipfile.ZipFile(dest) as z:
            for c, n in FRENCH_PAIS.items():
                s = french_pais_local(z.read(f"{n}.Dat").decode("latin-1"))
                cw.add(f"ffc_{c.lower()}_{k}_m", s,
                       name=f"Fama-French International Countries {n}: {'total return' if k == 'tr' else 'price'} "
                            "local currency, monthly",
                       category="equity_returns", frequency="M", units="percent per period", country=c,
                       transform_notes=f"F-F_International_Countries{suf}.zip/{n}.Dat; local currency; percent",
                       url=URL.format(suf))
    cat = cw.close()
    print(cat[["series_id", "frequency", "start", "end"]].to_string(index=False))


if __name__ == "__main__":
    main()
