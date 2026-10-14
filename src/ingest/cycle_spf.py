"""Philadelphia Fed Survey of Professional Forecasters (SPF), 1968Q4 -> today.

source_id = spf. Medians (level + growth), cross-sectional dispersion (IQR), mean
probability of decline in real GDP (RECESS1..5) and the Anxious Index.

Date convention: `date` = first day of the SURVEY quarter (e.g. 2026Q3 -> 2026-07-01).
The survey is released ~mid second month of the quarter (deadline ~day 10-20), so for
point-in-time use treat the value as known from date + 45 days.
Horizon suffixes (Philadelphia Fed naming): 1 = previous quarter (nowcast of last
published quarter), 2 = current quarter, 3..6 = 1..4 quarters ahead; A/B/C/D = annual
averages for current year, next year, +2, +3.

Run: .venv/bin/python -m src.ingest.cycle_spf [--refresh]
"""
from __future__ import annotations

import re
import sys
import warnings

import pandas as pd

from ._extlong_common import CatalogWriter, download, log, raw_dir

warnings.filterwarnings("ignore", category=UserWarning)

SRC = "spf"
BASE = "https://www.philadelphiafed.org/-/media/FRBP/Assets/Surveys-And-Data/survey-of-professional-forecasters"
FILES = {
    "medianLevel.xlsx": f"{BASE}/historical-data/medianLevel.xlsx",
    "medianGrowth.xlsx": f"{BASE}/historical-data/medianGrowth.xlsx",
    "meanLevel.xlsx": f"{BASE}/historical-data/meanLevel.xlsx",
    "Dispersion_1.xlsx": f"{BASE}/historical-data/Dispersion_1.xlsx",
    "Dispersion_2.xlsx": f"{BASE}/historical-data/Dispersion_2.xlsx",
    "Dispersion_3.xlsx": f"{BASE}/historical-data/Dispersion_3.xlsx",
    "prob.xlsx": f"{BASE}/historical-data/prob.xlsx",
    "anxious_index_chart.xlsx": f"{BASE}/anxious-index/anxious_index_chart.xlsx",
}
PAGE = "https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/survey-of-professional-forecasters"
LIC = "Federal Reserve Bank of Philadelphia, public data; cite 'Survey of Professional Forecasters'"

# variable -> (description, category, units for level file)
VARS = {
    "RGDP": ("Real GDP", "growth", "billions chained $ (level) / % q/q saar (growth)"),
    "NGDP": ("Nominal GDP", "growth", "billions $ / % q/q saar"),
    "PGDP": ("GDP price index", "inflation", "index / % q/q saar"),
    "CPROF": ("Corporate profits after tax", "growth", "billions $ / % q/q saar"),
    "UNEMP": ("Civilian unemployment rate", "employment", "%"),
    "EMP": ("Nonfarm payroll employment", "employment", "thousands / % q/q saar"),
    "INDPROD": ("Industrial production index", "growth", "index / % q/q saar"),
    "HOUSING": ("Housing starts", "housing", "millions saar / % q/q saar"),
    "RCONSUM": ("Real personal consumption", "growth", "billions chained $ / % q/q saar"),
    "RNRESIN": ("Real nonresidential fixed investment", "growth", "billions chained $ / % q/q saar"),
    "RRESINV": ("Real residential fixed investment", "housing", "billions chained $ / % q/q saar"),
    "TBILL": ("3-month Treasury bill rate", "rates", "%"),
    "TBOND": ("10-year Treasury bond yield", "rates", "%"),
    "BOND": ("Moody's AAA corporate bond yield", "rates", "%"),
    "BAABOND": ("Moody's BAA corporate bond yield", "credit", "%"),
    "CPI": ("CPI inflation (headline)", "inflation", "% q/q saar (annual: % q4/q4)"),
    "CORECPI": ("Core CPI inflation", "inflation", "% q/q saar"),
    "PCE": ("PCE price inflation", "inflation", "% q/q saar"),
    "COREPCE": ("Core PCE inflation", "inflation", "% q/q saar"),
    "CPI5YR": ("CPI inflation, next 5 years", "inflation", "% per year"),
    "CPI10": ("CPI inflation, next 10 years", "inflation", "% per year"),
    "PCE10": ("PCE inflation, next 10 years", "inflation", "% per year"),
    "RGDP10": ("Real GDP growth, next 10 years", "growth", "% per year"),
    "PROD10": ("Productivity growth, next 10 years", "growth", "% per year"),
    "STOCK10": ("S&P 500 total return, next 10 years", "markets", "% per year"),
    "BOND10": ("10y Treasury return, next 10 years", "rates", "% per year"),
    "BILL10": ("3m T-bill return, next 10 years", "rates", "% per year"),
    "UBAR": ("Natural rate of unemployment (long-run)", "employment", "%"),
    "SPR_TBOND_TBILL": ("Spread 10y Treasury - 3m bill", "rates", "pp"),
    "SPR_BAA_TBOND": ("Spread BAA - 10y Treasury", "credit", "pp"),
}
HORIZON_TXT = {"1": "previous quarter", "2": "current quarter", "3": "1q ahead", "4": "2q ahead",
               "5": "3q ahead", "6": "4q ahead", "A": "current year (annual)", "B": "next year (annual)",
               "C": "year+2 (annual)", "D": "year+3 (annual)"}


def _qdate(year, q) -> pd.Timestamp:
    return pd.Timestamp(int(year), 3 * (int(q) - 1) + 1, 1)


def _std_sheet(path, sheet) -> pd.DataFrame:
    d = pd.read_excel(path, sheet_name=sheet)
    d = d.dropna(subset=["YEAR", "QUARTER"])
    d.index = [_qdate(y, q) for y, q in zip(d["YEAR"], d["QUARTER"])]
    return d.drop(columns=["YEAR", "QUARTER"])


def _disp_sheet(path, sheet) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    hdr = raw.index[raw[0].astype(str).str.startswith("Survey_Date")][0]
    d = raw.iloc[hdr + 1:].copy()
    d.columns = raw.iloc[hdr].astype(str)
    d = d[d.iloc[:, 0].astype(str).str.match(r"^\d{4}Q\d$")]
    d.index = [pd.Period(s, "Q").start_time for s in d.iloc[:, 0].astype(str)]
    return d.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")


def main(refresh: bool = False) -> None:
    rd = raw_dir(SRC)
    for name, url in FILES.items():
        download(url, rd / name, "xlsx", min_age_hours=0 if refresh else 20)
    cw = CatalogWriter(SRC, url=PAGE, license=LIC)
    note = "date = survey quarter start; known ~date+45d; horizon per Philly Fed suffix"

    # 1) median & mean levels
    for fname, stat in (("medianLevel.xlsx", "med"), ("meanLevel.xlsx", "mean")):
        xl = pd.ExcelFile(rd / fname)
        for var, (desc, cat, units) in VARS.items():
            if var not in xl.sheet_names:
                continue
            if stat == "mean" and var not in ("RGDP", "UNEMP", "CPI", "CORECPI", "TBILL", "TBOND", "CPI10"):
                continue
            d = _std_sheet(xl, var)
            for col in d.columns:
                m = re.match(rf"^{var}(\w)$", col, re.I)
                if not m:
                    continue
                h = m.group(1).upper()
                cw.add(f"spf_{stat}_{var.lower()}_{h.lower()}", d[col],
                       name=f"SPF {stat} forecast: {desc}, {HORIZON_TXT.get(h, h)}", category=cat,
                       frequency="Q", units=units.split(" / ")[0], country="US",
                       transform_notes=f"{fname} sheet {var} col {col}; {note}")

    # 2) median growth (q/q saar, annual-average growth)
    xl = pd.ExcelFile(rd / "medianGrowth.xlsx")
    for sheet in xl.sheet_names:
        var = sheet.split("_")[0]
        desc, cat, _ = VARS.get(var, (sheet, "growth", ""))
        d = _std_sheet(xl, sheet)
        for col in d.columns:
            m = re.match(r"^d\w+?(\d|[a-d])$", col)
            if not m:
                continue
            h = m.group(1).upper()
            suffix = sheet.lower().replace("_", "")
            cw.add(f"spf_medg_{suffix}_{h.lower()}", d[col],
                   name=f"SPF median growth forecast: {desc} ({sheet}), {HORIZON_TXT.get(h, h)}",
                   category=cat, frequency="Q", units="% q/q annualized (annual cols: % year avg/year avg)",
                   country="US", transform_notes=f"medianGrowth.xlsx sheet {sheet} col {col}; {note}")

    # 3) dispersion (75th - 25th percentile), all three files
    for fname in ("Dispersion_1.xlsx", "Dispersion_2.xlsx", "Dispersion_3.xlsx"):
        dnum = fname[-6]
        xl = pd.ExcelFile(rd / fname)
        for sheet in xl.sheet_names:
            var = sheet.upper()
            if var not in VARS:
                continue
            desc, cat, _ = VARS[var]
            d = _disp_sheet(xl, sheet)
            for col in d.columns:
                m = re.match(rf"^{re.escape(sheet)}_D\d\(T(\+\d)?\)$", col, re.I)
                if not m:
                    continue
                k = (m.group(1) or "+0")[1:]
                kind = {"1": "level", "2": "q/q growth", "3": "annual-avg growth"}[dnum]
                cw.add(f"spf_disp{dnum}_{var.lower()}_t{k}", d[col],
                       name=f"SPF dispersion (IQR, {kind}): {desc}, horizon T+{k}", category=cat,
                       frequency="Q", units="pp (75th - 25th percentile)", country="US",
                       transform_notes=f"{fname} sheet {sheet} col {col}; D{dnum}=P75-P25 of {kind}; {note}")

    # 4) probability of decline in real GDP (mean across forecasters)
    d = _std_sheet(rd / "prob.xlsx", "RECESS")
    for i in range(1, 6):
        cw.add(f"spf_recess{i}", d[f"RECESS{i}"],
               name=f"SPF mean probability of decline in real GDP in {HORIZON_TXT[str(i)]}",
               category="growth", frequency="Q", units="percent", country="US",
               transform_notes=f"prob.xlsx RECESS{i}; RECESS2 = Anxious Index; {note}")

    # 5) anxious index (official file)
    raw = pd.read_excel(rd / "anxious_index_chart.xlsx", sheet_name="Data", header=None)
    hdr = raw.index[raw[0].astype(str).str.contains("Obs Year", na=False)][0]
    a = raw.iloc[hdr + 1:, :3].dropna()
    a.index = [_qdate(y, q) for y, q in zip(a[0], a[1])]
    cw.add("spf_anxious_index", a[2], name="SPF Anxious Index (prob. of GDP decline next quarter)",
           category="growth", frequency="Q", units="percent", country="US",
           transform_notes="anxious_index_chart.xlsx; date = TARGET quarter (survey quarter + 1): equals spf_recess2 shifted +1q; survey known ~45d after survey-quarter start")
    cat = cw.close()
    log.info("spf: %d series", len(cat))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
