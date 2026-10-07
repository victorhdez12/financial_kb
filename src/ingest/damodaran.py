"""Aswath Damodaran - Historical returns on stocks, bonds, bills, real estate, gold (annual, 1928-).

Run: .venv/bin/python -m src.ingest.damodaran
Raw:     $FIN_DATA_ROOT/raw/damodaran/histretSP.xls
Curated: $FIN_DATA_ROOT/curated/damodaran/damodaran_*.parquet  (decimal returns)
"""
from __future__ import annotations

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, log, raw_dir

SOURCE = "damodaran"
URL = "https://pages.stern.nyu.edu/~adamodar/pc/datasets/histretSP.xls"
PAGE = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histret.html"
LICENSE = "Aswath Damodaran, NYU Stern - freely shared for educational/research use, cite source"

# column -> (suffix, name, category)
COLS = {
    1: ("sp500_tr", "S&P 500 total return (incl. dividends), nominal", "equity_returns"),
    2: ("smallcap_tr", "US small cap (bottom decile, French) return, nominal", "equity_returns"),
    3: ("tbill_3m", "3-month T-bill return, nominal", "rates"),
    4: ("tbond_10y_tr", "US 10-year T-bond total return, nominal", "bond_returns"),
    5: ("baa_corp_tr", "Baa corporate bond total return, nominal", "bond_returns"),
    6: ("real_estate_tr", "Real estate (home price) return, nominal", "housing"),
    7: ("gold_ret", "Gold return, nominal", "gold"),
    15: ("erp_stocks_bills", "Annual risk premium: stocks minus bills", "equity_returns"),
    16: ("erp_stocks_bonds", "Annual risk premium: stocks minus T-bonds", "equity_returns"),
    18: ("erp_stocks_baa", "Annual risk premium: stocks minus Baa bonds", "equity_returns"),
    19: ("implied_erp", "Historical implied ERP (Damodaran)", "valuation"),
    20: ("inflation", "US CPI inflation rate", "inflation"),
    21: ("sp500_tr_real", "S&P 500 total return, real", "equity_returns"),
    22: ("smallcap_tr_real", "US small cap return, real", "equity_returns"),
    23: ("tbill_3m_real", "3-month T-bill return, real", "rates"),
    24: ("tbond_10y_tr_real", "10-year T-bond total return, real", "bond_returns"),
    25: ("baa_corp_tr_real", "Baa corporate bond return, real", "bond_returns"),
    26: ("real_estate_tr_real", "Real estate return, real", "housing"),
    27: ("gold_ret_real", "Gold return, real", "gold"),
}


def main() -> None:
    dest = raw_dir(SOURCE) / "histretSP.xls"
    try:
        download(URL, dest, "xls")
    except Exception as e:  # noqa: BLE001
        if not dest.exists():
            raise
        log.warning("download failed (%s); using cached", e)
    d = pd.read_excel(dest, sheet_name="Returns by year", header=None)
    hdr = d.index[d[0].astype(str).str.strip().eq("Year")][0]
    upd = d.iloc[0, 1]
    body = d.iloc[hdr + 1:]
    yr = pd.to_numeric(body[0], errors="coerce")
    body = body[yr.notna() & yr.between(1900, 2100)]
    # stop at first non-year row (summary tables below)
    years = body[0].astype(int)
    idx = pd.to_datetime(years.astype(str) + "-01-01")
    cw = CatalogWriter(SOURCE, url=PAGE, license=LICENSE)
    for col, (suf, name, cat) in COLS.items():
        hdr_txt = str(d.iloc[hdr, col])
        cw.add(f"damodaran_{suf}", pd.Series(pd.to_numeric(body[col], errors="coerce").values, index=idx),
               name=name, category=cat, frequency="A", units="fraction p.a.", country="USA",
               transform_notes=f"sheet 'Returns by year' col '{hdr_txt}'; file updated {upd}; calendar-year return",
               url=URL)
    cat = cw.close()
    print(cat[["series_id", "start", "end"]].to_string(index=False))


if __name__ == "__main__":
    main()
