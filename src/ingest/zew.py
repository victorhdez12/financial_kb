"""ZEW Financial Market Survey: ZEW Indicator of Economic Sentiment (expectations) and current economic
situation for Germany, balances, monthly since 1991-12 (public Excel konjunktur.xls on ftp.zew.de).

Only these two German series are free. Euro-area / country sentiment series, sub-sector indicators and the
micro data are licensed by ZEW (https://www.zew.de/en/publications/zew-expertises-research-reports/research-reports/business-cycle/zew-financial-market-survey) -> gap.
Dates: the Excel holds the survey (release) date; stored at month start.
Run: .venv/bin/python -m src.ingest.zew     Raw: raw/zew/konjunktur.xls   Curated: curated/zew/zew_*.parquet
"""
from __future__ import annotations

import pandas as pd
import xlrd

from src.ingest._europe_common import CatalogWriter, add_series, cached_get, log, raw_dir

SOURCE = "zew"
URL = "https://ftp.zew.de/pub/zew-docs/div/konjunktur.xls"
PAGE = "https://www.zew.de/en/publications/zew-expertises-research-reports/research-reports/business-cycle/zew-financial-market-survey"
LICENSE = "ZEW: free download of the German indicator series on zew.de, cite 'ZEW - Leibniz Centre for European Economic Research'. Other ZEW series are licensed."


def main() -> pd.DataFrame:
    path = raw_dir(SOURCE) / "konjunktur.xls"
    cached_get(URL, path, min_bytes=20000, max_age_hours=24)
    ws = xlrd.open_workbook(str(path)).sheet_by_name("data")
    idx, a, b = [], [], []
    for r in range(1, ws.nrows):
        row = ws.row_values(r)
        if not isinstance(row[0], float):
            continue
        d = pd.Timestamp(xlrd.xldate_as_datetime(row[0], 0)).to_period("M").start_time
        idx.append(d)
        a.append(row[1] if isinstance(row[1], float) else float("nan"))
        b.append(row[2] if isinstance(row[2], float) else float("nan"))
    cw = CatalogWriter(SOURCE, url=PAGE, license=LICENSE)
    note = "ZEW konjunktur.xls sheet 'data'; survey date mapped to month start. Balance of positive minus negative replies (-100..100)."
    add_series(cw, "zew_de_sentiment_m", pd.Series(a, index=idx), name="ZEW Indicator of Economic Sentiment, Germany (expectations, 6 months ahead)",
               category="growth", frequency="M", units="balance (pp)", country="DE", transform_notes=note)
    add_series(cw, "zew_de_situation_m", pd.Series(b, index=idx), name="ZEW current economic situation, Germany",
               category="growth", frequency="M", units="balance (pp)", country="DE", transform_notes=note)
    return cw.close()


if __name__ == "__main__":
    main()
