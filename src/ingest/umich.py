"""University of Michigan Surveys of Consumers (fuente directa) -> curated/umich.

    .venv/bin/python -m src.ingest.umich

Fuente: https://www.sca.isr.umich.edu/files/ (CSV públicos, sin clave). FRED publica estas series con ~1 mes de
retraso por licencia; la fuente directa tiene el dato final del mes t a finales de t.
- tbmics.csv     Index of Consumer Sentiment (ICS_ALL): trimestral/irregular 1952-1977, mensual desde 1978-01.
- tbmpx1px5.csv  Expectativa de inflación a 1 año (PX_MD, mediana) desde 1978-01 y a 5-10 años (PX5_MD) desde 1990.
date = mes de la encuesta (día 1). Point-in-time: el dato final se publica a finales del mismo mes (el preliminar a
mediados); retardo prudente en research/pit_calendar.yaml (20 días tras el fin de mes). Nota: la encuesta pasó a web
en 2024 (salto de nivel documentado por la Universidad).
"""
from __future__ import annotations

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, log, raw_dir

SOURCE = "umich"
BASE = "https://www.sca.isr.umich.edu/files/"
PAGE = "https://www.sca.isr.umich.edu/tables.html"
LICENSE = "University of Michigan Surveys of Consumers; public tables, free use with attribution"
NOTE = ("date = survey month (day 1); final release at the end of the same month (preliminary mid-month); "
        "web survey from 2024 (level break)")
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"], start=1)}


def _read(path) -> pd.DataFrame:
    d = pd.read_csv(path)
    d.columns = [c.strip() for c in d.columns]
    d = d[d["Month"].astype(str).str.strip().isin(MONTHS)]
    idx = pd.to_datetime({"year": d["YYYY"].astype(int), "month": d["Month"].str.strip().map(MONTHS), "day": 1})
    return d.set_index(pd.DatetimeIndex(idx)).drop(columns=["Month", "YYYY"])


def run() -> pd.DataFrame:
    cw = CatalogWriter(SOURCE, url=PAGE, license=LICENSE)
    ics = _read(download(BASE + "tbmics.csv", raw_dir(SOURCE) / "tbmics.csv", "csv", min_age_hours=20))
    cw.add("umich_ics", ics["ICS_ALL"], name="Michigan Index of Consumer Sentiment", category="growth",
           frequency="M", units="index 1966Q1=100", country="US",
           transform_notes=NOTE + "; quarterly/irregular before 1978-01", url=BASE + "tbmics.csv")
    px = _read(download(BASE + "tbmpx1px5.csv", raw_dir(SOURCE) / "tbmpx1px5.csv", "csv", min_age_hours=20))
    cw.add("umich_px1_md", px["PX_MD"], name="Michigan expected inflation, next 12 months (median)",
           category="inflation", frequency="M", units="%", country="US", transform_notes=NOTE,
           url=BASE + "tbmpx1px5.csv")
    cw.add("umich_px5_md", px["PX5_MD"], name="Michigan expected inflation, next 5-10 years (median)",
           category="inflation", frequency="M", units="%", country="US", transform_notes=NOTE,
           url=BASE + "tbmpx1px5.csv")
    log.info("umich: last month %s", ics.index.max().date())
    return cw.close()


if __name__ == "__main__":
    run()
