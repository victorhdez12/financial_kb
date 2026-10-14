"""AQR Capital Management data sets (https://www.aqr.com/Insights/Datasets).

Run: .venv/bin/python -m src.ingest.aqr
Raw:     $FIN_DATA_ROOT/raw/aqr/*.xlsx   (intact)
Curated: $FIN_DATA_ROOT/curated/aqr/aqr_<set>_<col>_<m|d>.parquet

Units: AQR publishes decimal excess returns (0.01 = 1 %). They are stored in PERCENT
(x100) to be coherent with ken_french / ken_french_intl.
Dates: monthly files use month-end -> stored as first day of month; daily keep the trading day.
Long/short factors are self-financing excess returns; Mkt/SMB/HML/UMD tabs are AQR's own
country factors (not Fama-French's), RF is AQR's risk-free input.
"""
from __future__ import annotations

import datetime as dt
import re

import openpyxl
import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, log, raw_dir

SOURCE = "aqr"
PAGE = "https://www.aqr.com/Insights/Datasets"
BASE = "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/"
LICENSE = ("AQR Data Sets: free download, no registration. No explicit data licence; AQR Terms of Use "
           "(aqr.com/Terms-of-Use) forbid reproducing/distributing/reselling site content without written "
           "consent; data is 'for illustrative purposes only', not investment advice, hypothetical. "
           "Use: personal/internal research only; cite the paper named in each file; do not redistribute.")

# (file stem, set id, label, citation, frequency, main-sheet prefix, extra sheets)
EXTRA = {"MKT": "mkt", "SMB": "smb", "HML FF": "hmlff", "UMD": "umd", "RF": "rf"}
FILES = [
    ("Quality-Minus-Junk-Factors-Monthly", "qmj", "Quality Minus Junk (Asness-Frazzini-Pedersen 2014)", "M", True),
    ("Quality-Minus-Junk-Factors-Daily", "qmj", "Quality Minus Junk (Asness-Frazzini-Pedersen 2014)", "D", True),
    ("Betting-Against-Beta-Equity-Factors-Monthly", "bab", "Betting Against Beta equity factor (Frazzini-Pedersen 2014)", "M", False),
    ("Betting-Against-Beta-Equity-Factors-Daily", "bab", "Betting Against Beta equity factor (Frazzini-Pedersen 2014)", "D", False),
    ("The-Devil-in-HMLs-Details-Factors-Monthly", "hmldevil", "HML Devil value factor (Asness-Frazzini 2013)", "M", False),
    ("The-Devil-in-HMLs-Details-Factors-Daily", "hmldevil", "HML Devil value factor (Asness-Frazzini 2013)", "D", False),
    ("Value-and-Momentum-Everywhere-Factors-Monthly", "vme", "Value and Momentum Everywhere (Asness-Moskowitz-Pedersen 2013)", "M", False),
    ("Time-Series-Momentum-Factors-Monthly", "tsmom", "Time Series Momentum (Moskowitz-Ooi-Pedersen 2012)", "M", False),
    ("Century-of-Factor-Premia-Monthly", "cfp", "Century of Factor Premia (Ilmanen et al. 2021)", "M", False),
]
COUNTRY = {  # ISO3 -> kept as given; aggregates mapped
    "global": "WLD", "global_ex_usa": "WLDXUS", "europe": "EUR", "north_america": "NAMER", "pacific": "PAC",
}


def slug(x) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(x).lower()).strip("_")


def parse_date(v):
    if isinstance(v, (dt.datetime, dt.date)):
        return pd.Timestamp(v)
    if isinstance(v, str) and re.match(r"^\d{2}/\d{2}/\d{4}$", v.strip()):
        return pd.to_datetime(v.strip(), format="%m/%d/%Y")
    return None


def read_sheet(ws) -> pd.DataFrame:
    """Return DataFrame indexed by date; header = row just above the first date row."""
    rows = [r for r in ws.iter_rows(values_only=True)]
    first = next(i for i, r in enumerate(rows) if parse_date(r[0]) is not None)
    hdr = rows[first - 1]
    data = [r for r in rows[first:] if parse_date(r[0]) is not None]
    idx = [parse_date(r[0]) for r in data]
    cols = {j: str(h).strip() for j, h in enumerate(hdr) if j > 0 and h not in (None, "")}
    df = pd.DataFrame({h: [r[j] if j < len(r) else None for r in data] for j, h in cols.items()}, index=idx)
    return df.apply(pd.to_numeric, errors="coerce")


def main() -> None:
    cw = CatalogWriter(SOURCE, url=PAGE, license=LICENSE)
    for stem, sid0, label, freq, extras in FILES:
        dest = raw_dir(SOURCE) / f"{stem}.xlsx"
        try:
            download(BASE + stem + ".xlsx", dest, "xlsx", min_age_hours=12)
        except Exception as e:  # noqa: BLE001
            if not dest.exists():
                log.error("skip %s: %s", stem, e)
                continue
            log.warning("%s download failed (%s); cached", stem, e)
        wb = openpyxl.load_workbook(dest, read_only=True, data_only=True)
        sheets = [(wb.worksheets[0].title, sid0, label)]
        if extras:
            sheets += [(s, f"aqr{k}", f"AQR country {s} factor") for s, k in EXTRA.items() if s in wb.sheetnames]
        for sheet, setid, lab in sheets:
            df = read_sheet(wb[sheet])
            if freq == "M":
                df.index = df.index.to_period("M").to_timestamp()
            for col in df.columns:
                k = slug(col)
                ccode = COUNTRY.get(k, k.upper() if re.fullmatch(r"[a-z]{3}", k) and setid in ("qmj", "bab", "hmldevil") or setid.startswith("aqr") and re.fullmatch(r"[a-z]{3}", k) and k != "rf" else "")
                if not ccode:  # multi-asset / cross-country sets
                    ccode = "USA" if (setid == "aqrrf" or k.startswith("us_") or "_us90" in k) else "WLD"
                sid = f"aqr_{setid}_{k}_{freq.lower()}"
                if setid.startswith("aqr"):
                    sid = f"aqr_{setid[3:]}_{k}_{freq.lower()}"
                    cat = "rates" if setid == "aqrrf" else "equity_returns"
                else:
                    cat = "equity_returns"
                cw.add(sid, df[col] * 100, name=f"AQR {lab}: {col}, {'monthly' if freq == 'M' else 'daily'}",
                       category=cat, frequency=freq, units="percent per period (excess return)" if setid != "aqrrf"
                       else "percent per period", country=ccode,
                       transform_notes=(f"{stem}.xlsx sheet '{sheet}'; decimal x100 -> percent; "
                                        "month-end date -> first of month; AQR rebuilds full history each update; "
                                        "self-financing long/short excess returns"),
                       url=PAGE)
    cat = cw.close()
    print(cat.groupby(["frequency"]).size())
    print(cat.groupby(cat.series_id.str.split("_").str[1]).agg(n=("series_id", "size"), start=("start", "min"), end=("end", "max")))


if __name__ == "__main__":
    main()
