"""Bank of England - "A millennium of macroeconomic data for the UK" (v3.1, frozen 2016/17).

Selected key UK series only (headline annual sheet A1 and monthly headline sheet M1).
Run: .venv/bin/python -m src.ingest.boe_millennium_uk
Raw:     $FIN_DATA_ROOT/raw/boe_millennium_uk/a-millennium-of-macroeconomic-data-for-the-uk.xlsx
Curated: $FIN_DATA_ROOT/curated/boe_millennium_uk/boe_uk_*.parquet
"""
from __future__ import annotations

import re

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, log, raw_dir

SOURCE = "boe_millennium_uk"
URL = ("https://www.bankofengland.co.uk/-/media/boe/files/statistics/research-datasets/"
       "a-millennium-of-macroeconomic-data-for-the-uk.xlsx")
PAGE = "https://www.bankofengland.co.uk/statistics/research-datasets"
LICENSE = "Bank of England research dataset; free re-use with attribution (BoE terms; Open Government Licence style)"

MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
                                      "Nov", "Dec"], start=1)}

# (series_id, desc regex, units regex, category)
ANNUAL = [
    ("boe_uk_real_gdp_a", r"^Real UK GDP at market prices", r"Chained Volume", "growth"),
    ("boe_uk_real_gdp_growth_a", r"^Real UK GDP at market prices", r"^growth rate", "growth"),
    ("boe_uk_nominal_gdp_a", r"^Nominal UK GDP at market prices", r"^£mn", "growth"),
    ("boe_uk_population_a", r"^Population \(GB\+NI\)", r"000s", "growth"),
    ("boe_uk_unemployment_a", r"^Unemployment rate", r"%", "employment"),
    ("boe_uk_gdp_deflator_a", r"^GDP deflator", r"2013=100", "inflation"),
    ("boe_uk_cpi_a", r"^Consumer price index", r"2015=100", "inflation"),
    ("boe_uk_cpi_inflation_a", r"^Consumer price inflation", r"%", "inflation"),
    ("boe_uk_wpi_a", r"^Wholesale/producer price", r"2010=100", "inflation"),
    ("boe_uk_earnings_a", r"^Earnings per head", r"weekly earnings", "employment"),
    ("boe_uk_real_wages_a", r"^Real consumption wages", r"1900=100", "employment"),
    ("boe_uk_oil_price_usd_a", r"Oil prices", r"barrel", "commodities"),
    ("boe_uk_bank_rate_eop_a", r"^Bank Rate", r"end period", "rates"),
    ("boe_uk_bank_rate_avg_a", r"^Bank Rate", r"calendar year average", "rates"),
    ("boe_uk_gov10y_yield_a", r"^10 year/medium-term government bond", r"", "rates"),
    ("boe_uk_consol_yield_a", r"^Consols", r"", "rates"),
    ("boe_uk_mortgage_rate_a", r"^Mortgage rates", r"", "rates"),
    ("boe_uk_corp_bond_yield_a", r"^Corporate bond yields", r"", "credit"),
    ("boe_uk_share_prices_a", r"^Share prices", r"", "markets"),
    ("boe_uk_usd_gbp_a", r"^\$/£ exchange rate", r"", "fx"),
    ("boe_uk_house_prices_a", r"^House price index", r"", "housing"),
    ("boe_uk_credit_a", r"^Credit", r"£mn", "credit"),
    ("boe_uk_monetary_base_a", r"^Monetary base", r"£mn", "money"),
    ("boe_uk_broad_money_a", r"^Broad Money", r"£mn", "money"),
    ("boe_uk_boe_balance_sheet_gdp_a", r"^Bank of England Balance sheet", r"% of nominal GDP", "liquidity"),
    ("boe_uk_ps_net_lending_gdp_a", r"^Public Sector Net Lending", r"% of nominal GDP", "fiscal"),
    ("boe_uk_public_debt_gdp_a", r"^UK Public sector debt", r"measure 1", "fiscal"),
    ("boe_uk_public_debt_a", r"^UK Public sector debt", r"nominal par value", "fiscal"),
    ("boe_uk_current_account_gdp_a", r"^Current account\s*$", r"% of nominal GDP", "growth"),
]
MONTHLY = [
    ("boe_uk_ip_m", r"^Index of Industrial Production", r"", "growth"),
    ("boe_uk_unemployment_m", r"^Monthly unemployment rate", r"", "employment"),
    ("boe_uk_wpi_m", r"^Spliced wholesale/producer", r"", "inflation"),
    ("boe_uk_cpi_m", r"^Spliced monthly Consumer Price", r"", "inflation"),
    ("boe_uk_rpi_m", r"^Spliced monthly Retail Price", r"", "inflation"),
    ("boe_uk_bank_rate_m", r"^Bank Rate", r"", "rates"),
    ("boe_uk_discount_rate_m", r"^Spliced series for discount rate", r"", "rates"),
    ("boe_uk_tbill_rate_m", r"^Spliced series for Treasury bill", r"", "rates"),
    ("boe_uk_gov10y_yield_m", r"^Medium-term/10 year bond yield", r"", "rates"),
    ("boe_uk_consol_yield_m", r"^Long-term consols yield", r"", "rates"),
    ("boe_uk_share_prices_m", r"^Spliced monthly share price index", r"", "markets"),
    ("boe_uk_corp_bond_yield_m", r"^Monthly corporate bond yields", r"", "credit"),
    ("boe_uk_corp_bond_spread_m", r"^Monthly corporate bonds spreads", r"", "credit"),
    ("boe_uk_usd_gbp_m", r"^\$/£ exchange rate", r"", "fx"),
    ("boe_uk_monetary_base_m", r"^Monetary base M0", r"", "money"),
    ("boe_uk_credit_m", r"^Aggregate Credit", r"", "credit"),
]


def meta_rows(d: pd.DataFrame) -> dict[str, int]:
    out = {}
    for i, v in d[0].items():
        if isinstance(v, str) and v.strip() in ("Section", "Description", "Worksheet", "Units", "Seasonality",
                                                "Notes", "Documentation"):
            out.setdefault(v.strip(), i)
        if i > 15:
            break
    return out


def columns_meta(d: pd.DataFrame, first_col: int) -> pd.DataFrame:
    mr = meta_rows(d)
    desc = d.loc[mr["Description"], first_col:].ffill()  # blank description = continuation
    units = d.loc[mr["Units"], first_col:]
    notes = d.loc[mr.get("Notes", mr.get("Documentation")), first_col:]
    ws = d.loc[mr["Worksheet"], first_col:].ffill()
    return pd.DataFrame({"desc": desc.fillna("").astype(str).str.strip(), "units": units.fillna("").astype(str).str.strip(),
                         "notes": notes.fillna("").astype(str), "worksheet": ws.fillna("").astype(str).str.strip()})


def pick(meta: pd.DataFrame, desc_re: str, units_re: str) -> int | None:
    m = meta[meta.desc.str.contains(desc_re, regex=True) & meta.units.str.contains(units_re, regex=True)]
    return m.index[0] if len(m) else None


def main() -> None:
    dest = raw_dir(SOURCE) / "a-millennium-of-macroeconomic-data-for-the-uk.xlsx"
    if not dest.exists():  # 27 MB, frozen dataset (v3.1): download once
        download(URL, dest, "xlsx")
    cw = CatalogWriter(SOURCE, url=URL, license=LICENSE)

    a = pd.read_excel(dest, sheet_name="A1. Headline series", header=None)
    meta = columns_meta(a, 1)
    yrs = pd.to_numeric(a[0], errors="coerce")
    rows = a[yrs.notna() & yrs.between(1000, 2100)]
    idx = pd.to_datetime(rows[0].astype(int).astype(str) + "-01-01", format="%Y-%m-%d")
    for sid, dre, ure, cat in ANNUAL:
        c = pick(meta, dre, ure)
        if c is None:
            log.warning("not found: %s (%s / %s)", sid, dre, ure)
            continue
        cw.add(sid, pd.Series(pd.to_numeric(rows[c], errors="coerce").values, index=idx),
               name=f"UK: {meta.desc[c][:120]}", category=cat, frequency="A", units=meta.units[c],
               country="GBR", transform_notes=f"BoE millennium v3.1 sheet A1 <- {meta.worksheet[c]}; "
                                              f"{meta.notes[c][:200]}")

    m = pd.read_excel(dest, sheet_name="M1. Mthly headline series", header=None)
    meta = columns_meta(m, 2)
    yrs = pd.to_numeric(m[0], errors="coerce")
    ok = yrs.notna() & m[1].isin(MONTHS.keys())
    rows = m[ok]
    idx = pd.to_datetime(dict(year=rows[0].astype(int), month=rows[1].map(MONTHS), day=1))
    for sid, dre, ure, cat in MONTHLY:
        c = pick(meta, dre, ure)
        if c is None:
            log.warning("not found: %s (%s)", sid, dre)
            continue
        cw.add(sid, pd.Series(pd.to_numeric(rows[c], errors="coerce").values, index=idx.values),
               name=f"UK: {meta.desc[c][:120]}", category=cat, frequency="M", units=meta.units[c],
               country="GBR", transform_notes=f"BoE millennium v3.1 sheet M1 <- {meta.worksheet[c]}; "
                                              f"{meta.notes[c][:200]}")
    cat = cw.close()
    print(cat[["series_id", "units", "start", "end"]].to_string(index=False))


if __name__ == "__main__":
    main()
