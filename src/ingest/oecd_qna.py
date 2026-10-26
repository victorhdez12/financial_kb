"""OECD Quarterly National Accounts (SDMX, sdmx.oecd.org, DF_QNA 1.1): real GDP volume by quarter for the 18 JST
countries, for the live recession dating of the informative recession thermometer (docs/int/TERMOMETRO_diseno_v1.md §3).

series_id = oecd_gdpq_<iso3 lower>. Key Q.Y.<area>.S1.S1.B1GQ._Z._Z._Z.XDC.LR.LA.T0102: calendar and seasonally adjusted,
national currency, chain-linked volume (rebased), annual levels. Quarterly obs dated at quarter start.
Latest release only (no vintages in this flow; declared in the design: "si no, la última"). Back-cast history (estimated
observations before the national benchmark) is kept as published; OBS_STATUS counts go to the catalog notes.
Raw: $FIN_DATA_ROOT/raw/oecd_qna/gdpq.csv (full API response) + provenance.json (url, sha256, UTC time).

Run: .venv/bin/python -m src.ingest.oecd_qna [--refresh]
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import time

import pandas as pd

from ._extlong_common import CatalogWriter, http_get, log, raw_dir

SRC = "oecd_qna"
PAGE = "https://data-explorer.oecd.org/"
LIC = "OECD data, CC BY 4.0 (OECD terms and conditions)"
AREAS = ["AUS", "BEL", "CAN", "CHE", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "IRL", "ITA", "JPN", "NLD", "NOR", "PRT",
         "SWE", "USA"]
URL = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA,1.1/Q.Y." + "+".join(AREAS) +
       ".S1.S1.B1GQ._Z._Z._Z.XDC.LR.LA.T0102?format=csvfilewithlabels")


def fetch(refresh: bool) -> pd.DataFrame:
    dest = raw_dir(SRC) / "gdpq.csv"
    fresh = dest.exists() and (time.time() - dest.stat().st_mtime) / 3600 < 20
    if refresh or not fresh:
        try:
            r = http_get(URL, timeout=300)
            if b"TIME_PERIOD" not in r.content[:3000]:
                raise ValueError(r.text[:200])
            dest.write_bytes(r.content)
            (raw_dir(SRC) / "provenance.json").write_text(json.dumps({
                "url": URL, "sha256": hashlib.sha256(r.content).hexdigest(), "bytes": len(r.content),
                "downloaded_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}, indent=1))
            log.info("downloaded oecd_qna gdpq (%d bytes)", len(r.content))
        except Exception as e:  # noqa: BLE001
            if not dest.exists():
                raise
            log.warning("oecd_qna failed (%s); using cached raw", e)
    return pd.read_csv(dest, low_memory=False)


def main(refresh: bool = False) -> None:
    d = fetch(refresh)
    cw = CatalogWriter(SRC, url=PAGE, license=LIC)
    for area, g in d.groupby("REF_AREA"):
        if g["TIME_PERIOD"].duplicated().any():
            raise ValueError(f"oecd_qna {area}: varias series por trimestre")
        idx = pd.PeriodIndex(g["TIME_PERIOD"].astype(str).str.replace("-Q", "Q"), freq="Q").start_time
        s = pd.Series(pd.to_numeric(g["OBS_VALUE"], errors="coerce").values, index=idx)
        st = g["OBS_STATUS"].value_counts().to_dict() if "OBS_STATUS" in g else {}
        cw.add(f"oecd_gdpq_{area.lower()}", s, name=f"OECD real GDP, chain-linked volume, SA, quarterly, "
               f"{g['Reference area'].iloc[0]}", category="growth", frequency="Q",
               units=f"national currency, chain-linked volume (ref. year {g['REF_YEAR_PRICE'].iloc[0]}), annual levels",
               country=area, transform_notes=(f"OECD SDMX DF_QNA 1.1 key Q.Y.{area}.S1.S1.B1GQ._Z._Z._Z.XDC.LR.LA.T0102; "
                                              f"quarter start; latest release (no vintages); OBS_STATUS {st}"),
               url=PAGE)
    cat = cw.close()
    log.info("oecd_qna: %d series, %s .. %s", len(cat), cat.start.min(), cat.end.max())


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
