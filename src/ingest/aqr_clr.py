"""AQR "Commodities for the Long Run: Index Level Data, Monthly" (Levine, Ooi, Richardson & Sasseville, FAJ 2018).
Equal-weight and long/short commodity futures portfolios since 1877-02, with the split of the excess return into
excess spot return + interest-rate-adjusted carry (roll). Added for INT-3b/INT-3c (docs/int/INT3b_prerregistro_v0.md).

Run: .venv/bin/python -m src.ingest.aqr_clr
Raw:     $FIN_DATA_ROOT/raw/aqr_clr/Commodities-for-the-Long-Run-Index-Level-Data-Monthly.xlsx (intact)
         $FIN_DATA_ROOT/raw/aqr_clr/provenance.json (url, sha256, bytes, UTC download time)
Curated: $FIN_DATA_ROOT/curated/aqr_clr/aqr_clr_<col>_m.parquet

Units: AQR publishes decimal monthly returns; stored in PERCENT (x100), as src/ingest/aqr.py. Month-end -> first of month.
The text columns 'State of backwardation/contango' and 'State of inflation' are NOT ingested: the second is AQR's own
inflation regime (it would be a foreign regime label next to ours); the numeric 'Aggregate backwardation/contango' is kept
as an indicator.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json

import openpyxl
import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, log, raw_dir

SOURCE = "aqr_clr"
STEM = "Commodities-for-the-Long-Run-Index-Level-Data-Monthly"
PAGE = "https://www.aqr.com/Insights/Datasets/Commodities-for-the-Long-Run-Index-Level-Data-Monthly"
URL = "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/" + STEM + ".xlsx"
LICENSE = ("AQR Data Sets: free download, no registration. No explicit data licence; AQR Terms of Use forbid "
           "reproducing/distributing/reselling site content without written consent; hypothetical, illustrative. "
           "Use: personal/internal research only; cite Levine-Ooi-Richardson-Sasseville (FAJ 2018); do not redistribute.")
TEXTO = {"State of backwardation/contango", "State of inflation"}
CORTO = {
    "Excess return of equal-weight commodities portfolio": "ew_xret",
    "Excess spot return of equal-weight commodities portfolio": "ew_xspot",
    "Interest rate adjusted carry of equal-weight commodities portfolio": "ew_carry_adj",
    "Spot return of equal-weight commodities portfolio": "ew_spot",
    "Carry of equal-weight commodities portfolio": "ew_carry",
    "Excess return of long/short commodities portfolio": "ls_xret",
    "Excess spot return of long/short commodities portfolio": "ls_xspot",
    "Interest rate adjusted carry of long/short commodities portfolio": "ls_carry_adj",
    "Aggregate backwardation/contango": "agg_backwardation",
}


def _fecha(v):
    if isinstance(v, (dt.datetime, dt.date)):
        return pd.Timestamp(v)
    if isinstance(v, str):
        try:
            return pd.Timestamp(v.strip())
        except ValueError:
            return None
    return None


def leer(path) -> pd.DataFrame:
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    i0 = next(i for i, r in enumerate(rows) if _fecha(r[0]) is not None)
    hdr = rows[i0 - 1]
    data = [r for r in rows[i0:] if _fecha(r[0]) is not None]
    cols = {j: str(h).strip() for j, h in enumerate(hdr) if j > 0 and h not in (None, "")}
    df = pd.DataFrame({h: [r[j] for r in data] for j, h in cols.items() if h not in TEXTO},
                      index=pd.DatetimeIndex([_fecha(r[0]) for r in data]))
    faltan = set(cols.values()) - TEXTO - set(CORTO)
    if faltan:
        raise ValueError(f"columnas nuevas en el fichero de AQR: {faltan}")
    return df.apply(pd.to_numeric, errors="coerce")


def main() -> None:
    dest = raw_dir(SOURCE) / f"{STEM}.xlsx"
    download(URL, dest, "xlsx", min_age_hours=12)
    b = dest.read_bytes()
    (raw_dir(SOURCE) / "provenance.json").write_text(json.dumps({
        "url": URL, "page": PAGE, "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b),
        "file_mtime_utc": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).isoformat(timespec="seconds"),
        "paper": "Levine, Ooi, Richardson & Sasseville (2018), Commodities for the Long Run, FAJ 74(2): 55-68",
    }, indent=1))
    df = leer(dest)
    df.index = df.index.to_period("M").to_timestamp()
    cw = CatalogWriter(SOURCE, url=PAGE, license=LICENSE)
    for col, k in CORTO.items():
        unidades = "index level (AQR aggregate backwardation measure)" if k == "agg_backwardation" else "percent per month"
        escala = 1 if k == "agg_backwardation" else 100
        cw.add(f"aqr_clr_{k}_m", df[col] * escala, name=f"AQR Commodities for the Long Run: {col}, monthly",
               category="commodity_returns", frequency="M", units=unidades, country="WLD",
               transform_notes=(f"{STEM}.xlsx first sheet; decimal x100 -> percent (except backwardation); month-end -> "
                                "first of month; excess return = excess spot + interest-rate-adjusted carry (AQR identity); "
                                "AQR rebuilds full history each update"), url=PAGE)
    cat = cw.close()
    log.info("aqr_clr: %d series, %s .. %s", len(cat), cat.start.min(), cat.end.max())


if __name__ == "__main__":
    main()
