"""NY Fed Quarterly Report on Household Debt and Credit -> curated/nyfed_hhdc.

    .venv/bin/python -m src.ingest.nyfed_hhdc

Source workbook: https://www.newyorkfed.org/medialibrary/interactives/householdcredit/data/xls/
HHD_C_Report_<YYYY>Q<q>.xlsx (NY Fed Consumer Credit Panel / Equifax). The script probes the
latest available quarter (walking back from the current one). Raw xlsx kept untouched in
$FIN_DATA_ROOT/raw/nyfed_hhdc/.

Only the national quarterly time-series pages are parsed (balances by product, accounts,
originations by credit score, delinquency status and transitions, foreclosures/bankruptcies,
collections, balances/transitions by age). State snapshot pages are skipped.
"""
from __future__ import annotations

import re

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, log, raw_dir

SOURCE = "nyfed_hhdc"
BASE = "https://www.newyorkfed.org/medialibrary/interactives/householdcredit/data/xls/HHD_C_Report_{q}.xlsx"
PAGE = "https://www.newyorkfed.org/microeconomics/hhdc"
LICENSE = "Federal Reserve Bank of New York / Equifax CCP; public report data, cite the NY Fed"
PAGES = {  # sheet -> (prefix, category)
    "Page 3 Data": ("bal", "credit"), "Page 4 Data": ("accts", "credit"),
    "Page 5 Data": ("inq", "credit"), "Page 6 Data": ("mortorig", "credit"),
    "Page 7 Data": ("mortorig_score", "credit"), "Page 8 Data": ("autoorig", "credit"),
    "Page 11 Data": ("delstat", "credit"), "Page 12 Data": ("dq90", "credit"),
    "Page 13 Data": ("newdq30", "credit"), "Page 14 Data": ("newdq90", "credit"),
    "Page 15 Data": ("trans_cur", "credit"), "Page 16 Data": ("trans_30_60", "credit"),
    "Page 17 Data": ("forecl_bankr", "credit"), "Page 18 Data": ("collections", "credit"),
    "Page 20 Data": ("bal_age", "credit"), "Page 24 Data": ("sdq_age_all", "credit"),
    "Page 25 Data": ("sdq_age_mort", "credit"), "Page 26 Data": ("sdq_age_auto", "credit"),
    "Page 27 Data": ("sdq_age_cc", "credit"), "Page 28 Data": ("sdq_age_student", "credit"),
}
SKIP = {"hhdc_delstat_total"}  # identically 100
UNITS = {"hhdc_collections_average_collection_amount_per_person_with_item": "USD",
         "hhdc_mortorig_score_median": "Equifax Riskscore 3.0",
         "hhdc_mortorig_score_25th_percentile": "Equifax Riskscore 3.0",
         "hhdc_mortorig_score_10th_percentile": "Equifax Riskscore 3.0"}
QRE = re.compile(r"^(\d{2}):Q([1-4])$")


def slug(s: str) -> str:
    s = s.lower().replace("+", "plus").replace("<", "lt").replace("%", "pct")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def to_quarter(x) -> pd.Timestamp | None:
    if isinstance(x, (pd.Timestamp,)) or hasattr(x, "year"):
        return pd.Timestamp(x).to_period("Q").start_time
    m = QRE.match(str(x).strip())
    if m:
        yy = int(m[1])
        return pd.Timestamp(1900 + yy if yy >= 90 else 2000 + yy, 3 * int(m[2]) - 2, 1)
    return None


def latest_workbook():
    rd = raw_dir(SOURCE)
    today = pd.Timestamp.today()
    for k in range(0, 6):
        p = (today - pd.DateOffset(months=3 * k)).to_period("Q")
        q = f"{p.year}Q{p.quarter}"
        dest = rd / f"HHD_C_Report_{q}.xlsx"
        if dest.exists() and dest.stat().st_size > 500_000:
            return dest, q
        try:
            return download(BASE.format(q=q), dest, "xlsx"), q
        except Exception as e:  # noqa: BLE001
            log.info("%s not available (%s)", q, str(e)[:80])
    raise SystemExit("no HHDC workbook found")


def parse_sheet(df: pd.DataFrame):
    title = str(df.iat[0, 0]).strip()
    units = str(df.iat[1, 0]).strip() if not str(df.iat[1, 0]).startswith(("Return", "nan", "*")) else ""
    first = next(i for i in range(len(df)) if to_quarter(df.iat[i, 0]) is not None)
    hdr = df.iloc[first - 1]
    for j in range(1, df.shape[1]):
        h = hdr.iloc[j]
        if pd.isna(h) or str(h).startswith(("Source", "Note", "Return", "*")):
            continue
        rows = df.iloc[first:]
        idx = [to_quarter(v) for v in rows.iloc[:, 0]]
        s = pd.Series(pd.to_numeric(rows.iloc[:, j], errors="coerce").values, index=idx)
        s = s[[i is not None for i in idx]]
        yield str(h).strip(), title, units, s


def main() -> None:
    path, q = latest_workbook()
    log.info("using %s", path.name)
    cw = CatalogWriter(SOURCE, url=PAGE, license=LICENSE)
    x = pd.ExcelFile(path)
    seen = set()
    for sheet, (prefix, cat) in PAGES.items():
        if sheet not in x.sheet_names:
            log.warning("sheet %s missing", sheet)
            continue
        for col, title, units, s in parse_sheet(x.parse(sheet, header=None)):
            sid = f"hhdc_{prefix}_{slug(col)}"
            if sid in seen or sid in SKIP:
                continue
            seen.add(sid)
            cw.add(sid, s, name=f"{title}: {col}", category=cat, frequency="Q",
                   units=UNITS.get(sid, units or "see raw workbook"), country="US",
                   transform_notes=(f"{path.name} sheet '{sheet}' column '{col}'; quarter labels "
                                    "'YY:Qn' / quarter-end dates -> quarter start"),
                   url=BASE.format(q=q))
    cat = cw.close()
    print(cat[["series_id", "start", "end", "units"]].to_string(index=False))


if __name__ == "__main__":
    main()
