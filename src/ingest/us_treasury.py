"""US Treasury FiscalData API -> curated/us_treasury (docs/DATA_CONTRACT.md).

    .venv/bin/python -m src.ingest.us_treasury

Datasets (https://fiscaldata.treasury.gov/api-documentation/, no key, public domain):
* v2/accounting/od/debt_outstanding   Historical Debt Outstanding, annual 1790+
* v2/accounting/od/debt_to_penny      Debt to the Penny, daily 1993+
* v1/debt/mspd/mspd_table_1           Monthly Statement of the Public Debt summary, 2001+
* v2/accounting/od/avg_interest_rates Average interest rates on Treasury securities, 2001+
* v2/accounting/od/interest_expense   Interest expense on the public debt, monthly 2010+

Raw: $FIN_DATA_ROOT/raw/us_treasury/<dataset>.json (full API pages concatenated, untouched rows).
MTS receipts/outlays/deficit come from FRED (release 363) in curated/fred_us.
"""
from __future__ import annotations

import json
import time

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, http_get, log, raw_dir

SOURCE = "us_treasury"
API = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
PAGE = "https://fiscaldata.treasury.gov/datasets/"
LICENSE = "US Treasury Fiscal Data - US government work, public domain"


def fetch(endpoint: str) -> list[dict]:
    rows, page = [], 1
    while True:
        url = f"{API}{endpoint}?page%5Bsize%5D=10000&page%5Bnumber%5D={page}&sort=record_date"
        j = http_get(url, timeout=120).json()
        rows += j["data"]
        total_pages = int(j["meta"].get("total-pages", 1))
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.5)
    name = endpoint.strip("/").split("/")[-1]
    (raw_dir(SOURCE) / f"{name}.json").write_text(json.dumps({"endpoint": endpoint, "data": rows}))
    log.info("%s: %d rows", endpoint, len(rows))
    return rows


def month_start(d: pd.Series) -> pd.DatetimeIndex:
    return pd.to_datetime(d).dt.to_period("M").dt.to_timestamp()


def main() -> None:
    cw = CatalogWriter(SOURCE, url=PAGE, license=LICENSE)

    # 1. Historical debt outstanding (annual, 1790+)
    d = pd.DataFrame(fetch("v2/accounting/od/debt_outstanding"))
    d["date"] = pd.to_datetime(d["record_fiscal_year"] + "-01-01")
    d = d.sort_values("record_date")
    s = pd.Series(pd.to_numeric(d["debt_outstanding_amt"]).values / 1e6, index=d["date"])
    cw.add("ust_debt_outstanding_a", s, name="Historical Debt Outstanding (US federal), end of fiscal year",
           category="fiscal", frequency="A", units="Millions of USD", country="US",
           transform_notes=("date = Jan 1 of fiscal year (record_fiscal_year); value is the level at the "
                            "record_date (Jan 1 until 1842, Jun 30/Jul 1 1843-1976, Sep 30 since 1977); "
                            "1843 has two records (Jan 1 and Jun 30): kept the later; USD -> millions"),
           url=PAGE + "historical-debt-outstanding/")

    # 2. Debt to the penny (daily)
    d = pd.DataFrame(fetch("v2/accounting/od/debt_to_penny"))
    idx = pd.to_datetime(d["record_date"])
    for col, sid, nm in [("tot_pub_debt_out_amt", "ust_dtp_total_d", "Total public debt outstanding"),
                         ("debt_held_public_amt", "ust_dtp_public_d", "Debt held by the public"),
                         ("intragov_hold_amt", "ust_dtp_intragov_d", "Intragovernmental holdings")]:
        s = pd.Series(pd.to_numeric(d[col], errors="coerce").values / 1e6, index=idx)
        cw.add(sid, s, name=f"Debt to the Penny: {nm}", category="fiscal", frequency="D",
               units="Millions of USD", country="US", transform_notes="business-day level; USD -> millions",
               url=PAGE + "debt-to-the-penny/")

    # 3. MSPD summary (monthly)
    d = pd.DataFrame(fetch("v1/debt/mspd/mspd_table_1"))
    d["date"] = month_start(d["record_date"])
    # Jan-Feb 2001 label variant of the grand total
    d["security_type_desc"] = d["security_type_desc"].replace(
        {"Total Treasury Securities Outstanding": "Total Public Debt Outstanding"})
    for label, sid in [("Total Marketable", "ust_mspd_marketable_m"),
                       ("Total Nonmarketable", "ust_mspd_nonmarketable_m"),
                       ("Total Public Debt Outstanding", "ust_mspd_total_m")]:
        sub = d[d["security_type_desc"] == label]
        for col, suf, nm in [("total_mil_amt", "", "total"), ("debt_held_public_mil_amt", "_public",
                                                               "held by the public")]:
            s = pd.Series(pd.to_numeric(sub[col], errors="coerce").values, index=sub["date"])
            cw.add(sid[:-2] + suf + "_m", s, name=f"MSPD: {label}, {nm} (end of month)",
                   category="fiscal", frequency="M", units="Millions of USD", country="US",
                   transform_notes=("end-of-month level dated to month start; Jan-Feb 2001 label 'Total Treasury Securities Outstanding' merged into 'Total Public Debt Outstanding'"),
                   url=PAGE + "monthly-statement-public-debt/")
    for cls, sid in [("Bills", "ust_mspd_bills_m"), ("Notes", "ust_mspd_notes_m"),
                     ("Bonds", "ust_mspd_bonds_m"),
                     ("Treasury Inflation-Protected Securities", "ust_mspd_tips_m"),
                     ("Floating Rate Notes", "ust_mspd_frn_m")]:
        sub = d[(d["security_type_desc"] == "Marketable") & (d["security_class_desc"] == cls)]
        s = pd.Series(pd.to_numeric(sub["total_mil_amt"], errors="coerce").values, index=sub["date"])
        cw.add(sid, s, name=f"MSPD: marketable {cls} outstanding (end of month)", category="fiscal",
               frequency="M", units="Millions of USD", country="US",
               transform_notes="end-of-month level dated to month start",
               url=PAGE + "monthly-statement-public-debt/")

    # 4. Average interest rates
    d = pd.DataFrame(fetch("v2/accounting/od/avg_interest_rates"))
    d["date"] = month_start(d["record_date"])
    d["security_desc"] = d["security_desc"].replace({"TotalMarketable": "Total Marketable"})
    for desc, sid in [("Total Interest-bearing Debt", "ust_avgrate_total_m"),
                      ("Total Marketable", "ust_avgrate_marketable_m"),
                      ("Total Non-marketable", "ust_avgrate_nonmarketable_m"),
                      ("Treasury Bills", "ust_avgrate_bills_m"), ("Treasury Notes", "ust_avgrate_notes_m"),
                      ("Treasury Bonds", "ust_avgrate_bonds_m"),
                      ("Treasury Inflation-Protected Securities (TIPS)", "ust_avgrate_tips_m")]:
        sub = d[d["security_desc"] == desc]
        s = pd.Series(pd.to_numeric(sub["avg_interest_rate_amt"], errors="coerce").values, index=sub["date"])
        cw.add(sid, s, name=f"Average interest rate on {desc}", category="fiscal", frequency="M",
               units="Percent", country="US",
               transform_notes="end-of-month average rate dated to month start; 'TotalMarketable' label "
                               "variant merged into 'Total Marketable'",
               url=PAGE + "average-interest-rates-treasury-securities/")

    # 5. Interest expense (monthly)
    d = pd.DataFrame(fetch("v2/accounting/od/interest_expense"))
    d["date"] = month_start(d["record_date"])
    d["amt"] = pd.to_numeric(d["month_expense_amt"], errors="coerce") / 1e6
    for flt, sid, nm in [(None, "ust_interest_expense_total_m", "total"),
                         ("INTEREST EXPENSE ON PUBLIC ISSUES", "ust_interest_expense_public_m",
                          "public issues"),
                         ("INTEREST EXPENSE ON GOVT ACCOUNT SERIES", "ust_interest_expense_gas_m",
                          "Government Account Series (intragovernmental)")]:
        sub = d if flt is None else d[d["expense_catg_desc"] == flt]
        s = sub.groupby("date")["amt"].sum(min_count=1)
        cw.add(sid, s, name=f"Interest expense on the public debt, {nm} (month)", category="fiscal",
               frequency="M", units="Millions of USD", country="US",
               transform_notes="sum of month_expense_amt over all expense lines (no subtotal rows in source)",
               url=PAGE + "interest-expense-debt-outstanding/")

    cat = cw.close()
    print(cat[["series_id", "frequency", "start", "end"]].to_string(index=False))


if __name__ == "__main__":
    main()
