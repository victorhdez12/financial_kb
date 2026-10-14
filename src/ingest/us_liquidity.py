"""US Treasury cash / issuance / Fed-liquidity extras -> curated/us_liquidity (docs/DATA_CONTRACT.md).

    .venv/bin/python -m src.ingest.us_liquidity

FiscalData API (no key, public domain), all amounts converted to USD millions:
* v1/accounting/dts/operating_cash_balance          daily TGA closing balance, 2005-10+ (the DTS in this API
                                                    starts 2005-10-03; older DTS PDFs/text are not in the API)
* v1/accounting/dts/deposits_withdrawals_operating_cash  daily deposits/withdrawals of the TGA
* v1/accounting/dts/public_debt_transactions        daily cash issues/redemptions by security type (Table IIIA)
* v1/accounting/od/auctions_query                   Treasury Securities Auctions Data, 1979+
* v1/accounting/od/buybacks_operations              Treasury buybacks, 2000-2002 and 2024+
FRED extras (H.4.1 detail not in fred/fred_us, plus pre-2002 Fed/monetary base proxies).

TGA definition (stitched, see transform_notes): "Federal Reserve Account" close (-2021-09-30), "Treasury General
Account (TGA)" close (2021-10-01..2022-04-15), "TGA Closing Balance" (2022-04-18+).
Raw: $FIN_DATA_ROOT/raw/us_liquidity/<endpoint>.json.
"""
from __future__ import annotations

import json
import re
import time

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, http_get, log, raw_dir
from src.ingest.fred_extended import Fred
from src.ingest.us_treasury import API

SOURCE = "us_liquidity"
PAGE = "https://fiscaldata.treasury.gov/datasets/"
LICENSE = "US Treasury Fiscal Data - US government work, public domain"
DTS = "v1/accounting/dts/"


class Writer(CatalogWriter):
    """Drops the current (incomplete) month from flow aggregates built from daily/auction data."""

    def add(self, series_id, s, **kw):
        if kw.get("frequency") == "M" and series_id.startswith(("usliq_dts_", "usliq_auc_", "usliq_buyback_")):
            s = s[pd.to_datetime(s.index) < pd.Timestamp.today().to_period("M").to_timestamp()]
            kw["transform_notes"] = kw.get("transform_notes", "") + "; current incomplete month dropped"
        return super().add(series_id, s, **kw)


def fetch(endpoint: str, fields: str | None = None, hours: float = 20, sort: str = "record_date") -> list[dict]:
    name = endpoint.strip("/").split("/")[-1]
    p = raw_dir(SOURCE) / f"{name}.json"
    if p.exists() and (time.time() - p.stat().st_mtime) / 3600 < hours:
        return json.loads(p.read_text())["data"]
    rows, page = [], 1
    while True:
        url = f"{API}{endpoint}?page%5Bsize%5D=10000&page%5Bnumber%5D={page}&sort={sort}"
        if fields:
            url += f"&fields={fields}"
        j = http_get(url, timeout=180).json()
        rows += j["data"]
        if page >= int(j["meta"].get("total-pages", 1)):
            break
        page += 1
        time.sleep(0.3)
    p.write_text(json.dumps({"endpoint": endpoint, "data": rows}))
    log.info("%s: %d rows", endpoint, len(rows))
    return rows


def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.replace("null", None), errors="coerce")


def mstart(d) -> pd.DatetimeIndex:
    return pd.to_datetime(d).dt.to_period("M").dt.to_timestamp()


def add_daily(cw, sid, s, name, notes, url, units="USD millions"):
    cw.add(sid, s, name=name, category="liquidity", frequency="D", units=units, country="US",
           transform_notes=notes, url=url, license=LICENSE)


def tga_block(cw: CatalogWriter) -> None:
    oc = pd.DataFrame(fetch(DTS + "operating_cash_balance",
                            "record_date,account_type,close_today_bal,open_today_bal"))
    oc["d"] = pd.to_datetime(oc["record_date"])
    oc["c"], oc["o"] = num(oc["close_today_bal"]), num(oc["open_today_bal"])
    at = oc["account_type"]
    fed = oc[at == "Federal Reserve Account"].set_index("d")["c"]
    tga2 = oc[at == "Treasury General Account (TGA)"].set_index("d")["c"]
    tga3 = oc[at == "Treasury General Account (TGA) Closing Balance"].set_index("d")["o"]
    tga = pd.concat([fed, tga2, tga3]).sort_index()
    tga = tga[~tga.index.duplicated(keep="last")]
    url = PAGE + "daily-treasury-statement-dts/"
    add_daily(cw, "usliq_tga_close_d", tga, "Treasury General Account (Fed) closing balance, daily",
              ("Stitched: 'Federal Reserve Account' close_today_bal (2005-10-03..2021-09-30), 'Treasury General "
               "Account (TGA)' close_today_bal (2021-10-01..2022-04-15), 'TGA Closing Balance' (2022-04-18+; value "
               "is in the open_today_bal column of that row). Excludes Tax & Loan (commercial-bank) balances and "
               "the Supplementary Financing Program account. Business days only"), url)
    sfp = oc[at.str.startswith("Supplementary Financing Prog") | at.str.startswith("Account Supplementary")]
    sfp = sfp.set_index("d")["c"]
    sfp = sfp[~sfp.index.duplicated(keep="last")]
    add_daily(cw, "usliq_sfp_close_d", sfp, "Supplementary Financing Program account at the Fed, closing balance",
              "union of label variants ('Supplementary Financing Prog(ram)(s)(Account)'); 2008-09..2022-04; Treasury "
              "cash held at the Fed outside the TGA line (drains reserves like the TGA)", url)
    tl = oc[at.str.contains("Tax and Loan")].set_index("d")["c"]
    tl = tl[~tl.index.duplicated(keep="last")]
    add_daily(cw, "usliq_tl_close_d", tl, "Tax and Loan Note Accounts (commercial banks), closing balance",
              "Treasury cash at depository institutions (not at the Fed); 2005-10..2012-09; label variants merged", url)

    d = pd.DataFrame(fetch(DTS + "deposits_withdrawals_operating_cash",
                           "record_date,account_type,transaction_type,transaction_catg,transaction_today_amt"))
    d["d"] = pd.to_datetime(d["record_date"])
    d["amt"] = num(d["transaction_today_amt"])
    d = d[d["account_type"].isin(["Federal Reserve Account", "Treasury General Account (TGA)"])]
    d = d[~d["transaction_catg"].str.contains("Sub-Total", na=False)]
    debt = d["transaction_catg"].str.startswith("Public Debt Cash")
    transfer = d["transaction_catg"].str.match(r"^(Transfers|ShTransfers)", na=False)
    dep, wd = d["transaction_type"] == "Deposits", d["transaction_type"] == "Withdrawals"
    nm = "daily deposits/withdrawals of the Fed account (TGA), all categories"
    base = ("sum of transaction_today_amt over table II lines for the Federal Reserve Account/TGA, excluding "
            "'Sub-Total' lines; includes Table V transfers from/to Tax&Loan accounts in 2005-2012 so that "
            "close(t)-close(t-1)=deposits-withdrawals (identity holds within +-5 on ~97% of days)")
    for sid, mask, nme, extra in [
        ("usliq_tga_deposits_d", dep, "TGA total deposits", ""),
        ("usliq_tga_withdrawals_d", wd, "TGA total withdrawals", ""),
        ("usliq_tga_deposits_exdebt_d", dep & ~debt & ~transfer, "TGA deposits excluding public-debt cash issues and transfers",
         "; excludes 'Public Debt Cash Issues' and 'Transfers ...' lines (tax/other receipts)"),
        ("usliq_tga_withdrawals_exdebt_d", wd & ~debt & ~transfer,
         "TGA withdrawals excluding public-debt redemptions and transfers",
         "; excludes 'Public Debt Cash Redemp.' and 'Transfers ...' lines (government spending proxy)"),
        ("usliq_tga_debt_issues_d", dep & debt, "TGA public-debt cash issues (deposits)", "; only 'Public Debt Cash Issues'"),
        ("usliq_tga_debt_redemptions_d", wd & debt, "TGA public-debt cash redemptions (withdrawals)",
         "; only 'Public Debt Cash Redemp.'"),
    ]:
        s = d[mask].groupby("d")["amt"].sum(min_count=1)
        add_daily(cw, sid, s, f"{nme}, daily", base + extra, PAGE + "daily-treasury-statement-dts/")


def pdt_block(cw: CatalogWriter) -> None:
    p = pd.DataFrame(fetch(DTS + "public_debt_transactions",
                           "record_date,transaction_type,security_market,security_type,security_type_desc,transaction_today_amt"))
    p["d"] = pd.to_datetime(p["record_date"])
    p["amt"] = num(p["transaction_today_amt"])
    p = p[p["security_market"] == "Marketable"]
    url = PAGE + "daily-treasury-statement-dts/"
    daily = {}
    for typ, key in [("Bills", "bills"), ("Notes", "notes"), ("Bonds", "bonds")]:
        for tt, lab in [("Issues", "issues"), ("Redemptions", "redemptions")]:
            m = (p["security_type"] == typ) & (p["transaction_type"] == tt)
            s = p[m].groupby("d")["amt"].sum(min_count=1)
            daily[(key, lab)] = s
            add_daily(cw, f"usliq_dts_{key}_{lab}_d", s, f"DTS marketable {typ.lower()} cash {lab}, daily",
                      "DTS Table III-A; face value of cash issues/redemptions; 'Notes' include TIPS/FRN; "
                      "'Bills' regular + cash management series; excludes inflation increments", url)
    for key, parts in [("bills", ["bills"]), ("coupons", ["notes", "bonds"]), ("marketable", ["bills", "notes", "bonds"])]:
        iss = sum(daily[(k, "issues")].resample("MS").sum(min_count=1) for k in parts)
        red = sum(daily[(k, "redemptions")].resample("MS").sum(min_count=1) for k in parts)
        for sid, s, nm in [(f"usliq_dts_{key}_gross_m", iss, f"gross cash issuance of marketable {key}"),
                           (f"usliq_dts_{key}_redeem_m", red, f"cash redemptions of marketable {key} (incl. buybacks)"),
                           (f"usliq_dts_{key}_net_m", iss - red, f"NET cash issuance of marketable {key} (issues - redemptions)")]:
            cw.add(sid, s, name=f"DTS monthly: {nm}", category="liquidity", frequency="M", units="USD millions",
                   country="US", transform_notes="monthly sum of DTS Table III-A daily amounts; month-start date; "
                   "coupons = Notes + Bonds (TIPS and FRN are inside Notes); a month with partial data is not flagged",
                   url=url, license=LICENSE)


def auctions_block(cw: CatalogWriter) -> None:
    a = pd.DataFrame(fetch("v1/accounting/od/auctions_query",
                           "record_date,security_type,security_term,auction_date,issue_date,offering_amt,"
                           "total_accepted,soma_accepted,floating_rate,inflation_index_security,"
                           "cash_management_bill_cmb,reopening"))
    a["issue"] = pd.to_datetime(a["issue_date"], errors="coerce")
    a = a[a["issue"].notna() & (a["issue"] <= pd.Timestamp.today())].copy()  # no future settlement dates
    for c in ["offering_amt", "total_accepted", "soma_accepted"]:
        a[c] = num(a[c]) / 1e6
    a["public"] = a["total_accepted"] - a["soma_accepted"].fillna(0)
    a = a[a["total_accepted"].notna()]
    a["month"] = a["issue"].dt.to_period("M").dt.to_timestamp()
    frn, tips = a["floating_rate"] == "Yes", a["inflation_index_security"] == "Yes"
    cmb = a["cash_management_bill_cmb"] == "Yes"
    a["grp"] = a["security_type"].str.lower()
    a.loc[frn, "grp"] = "frn"
    a.loc[tips & ~frn, "grp"] = "tips"
    url = PAGE + "treasury-securities-auctions-data/"
    note = ("Treasury Securities Auctions Data grouped by issue_date month; USD millions; 'gross' = total_accepted "
            "minus soma_accepted (SOMA add-ons excluded, i.e. new supply to the public); face value; "
            "TIPS at face (not inflation-adjusted)")
    for g, nm in [("bill", "bills (incl. CMB)"), ("note", "nominal notes"), ("bond", "nominal bonds"),
                  ("tips", "TIPS"), ("frn", "floating-rate notes")]:
        s = a[a["grp"] == g].groupby("month")["public"].sum(min_count=1)
        cw.add(f"usliq_auc_{g}_gross_m", s, name=f"Auction gross issuance: {nm}", category="liquidity",
               frequency="M", units="USD millions", country="US", transform_notes=note, url=url, license=LICENSE)
    cw.add("usliq_auc_cmb_gross_m", a[cmb].groupby("month")["public"].sum(min_count=1),
           name="Auction gross issuance: cash management bills", category="liquidity", frequency="M",
           units="USD millions", country="US", transform_notes=note + "; subset of the bills line", url=url, license=LICENSE)
    coup = a[a["grp"].isin(["note", "bond", "tips", "frn"])].groupby("month")["public"].sum(min_count=1)
    bills = a[a["grp"] == "bill"].groupby("month")["public"].sum(min_count=1)
    cw.add("usliq_auc_coupons_gross_m", coup, name="Auction gross issuance: all coupons (notes+bonds+TIPS+FRN)",
           category="liquidity", frequency="M", units="USD millions", country="US", transform_notes=note, url=url, license=LICENSE)
    tot = (bills.reindex(coup.index.union(bills.index)).fillna(0) + coup.reindex(coup.index.union(bills.index)).fillna(0))
    share = 100 * bills.reindex(tot.index).fillna(0) / tot.where(tot > 0)
    share = share[share.index >= bills.index.min()]
    cw.add("usliq_auc_bill_share_m", share,
           name="Bills as share of gross auction issuance", category="liquidity", frequency="M", units="Percent",
           country="US", transform_notes=note + "; bills / (bills + coupons)", url=url, license=LICENSE)
    cw.add("usliq_auc_soma_addon_m", a.groupby("month")["soma_accepted"].sum(min_count=1),
           name="Auction add-ons accepted for the Fed SOMA (rollovers)", category="liquidity", frequency="M",
           units="USD millions", country="US", transform_notes="sum of soma_accepted by issue month", url=url, license=LICENSE)
    cw.add("usliq_auc_count_m", a.groupby("month").size().astype(float), name="Number of auctions settling in the month",
           category="liquidity", frequency="M", units="Count", country="US", transform_notes="by issue_date", url=url, license=LICENSE)


def buybacks_block(cw: CatalogWriter) -> None:
    b = pd.DataFrame(fetch("v1/accounting/od/buybacks_operations", sort="operation_date"))
    b["settle"] = pd.to_datetime(b["settlement_date"], errors="coerce")
    b = b[b["settle"].notna() & (b["settle"] <= pd.Timestamp.today())].copy()
    b["amt"] = num(b["total_par_amt_accepted"]) / 1e6
    b["month"] = b["settle"].dt.to_period("M").dt.to_timestamp()
    url = PAGE + "buybacks/"
    note = "Treasury buyback operations, par amount accepted by settlement month, USD millions"
    cw.add("usliq_buyback_accepted_m", b.groupby("month")["amt"].sum(min_count=1), name="Treasury buybacks: par accepted",
           category="liquidity", frequency="M", units="USD millions", country="US",
           transform_notes=note + "; two programmes: 2000-03..2002-04 (debt reduction) and 2024-05+", url=url, license=LICENSE)
    for typ, sid in [("Liquidity Support", "usliq_buyback_liqsupport_m"), ("Cash Management", "usliq_buyback_cashmgmt_m")]:
        s = b[b["operation_type"] == typ].groupby("month")["amt"].sum(min_count=1)
        cw.add(sid, s, name=f"Treasury buybacks: {typ.lower()} operations, par accepted", category="liquidity",
               frequency="M", units="USD millions", country="US", transform_notes=note + f"; operation_type={typ}",
               url=url, license=LICENSE)


FRED = [
    # H.4.1 detail (weekly, Wednesday level, USD millions)
    ("WLCFLL", "Fed loans (discount window + other), total", "liquidity", "H.4.1 Liquidity and credit facilities: loans"),
    ("WLCFLSECL", "Fed seasonal credit", "liquidity", "discount window"),
    ("WLCFLSCL", "Fed secondary credit", "liquidity", "discount window"),
    ("WFCDA", "Fed foreign-currency-denominated assets", "liquidity", ""),
    ("WDFOL", "Fed deposits of foreign official institutions", "liquidity", "liability side"),
    ("WUPSHO", "Fed unamortized premiums on securities held outright", "liquidity", ""),
    ("WSHOBL", "Fed holdings of Treasury bills", "liquidity", ""),
    ("TREAST", "Fed holdings of Treasury securities, all", "liquidity", ""),
    ("WSHONBNL", "Fed holdings of Treasury notes and bonds, nominal", "liquidity", ""),
    ("WSHOFADSL", "Fed holdings of federal agency debt", "liquidity", ""),
    ("H41RESPPALGTRFNWW", "Fed repos with foreign official accounts (FIMA)", "liquidity", ""),
    # pre-2002 proxies for Fed balance sheet / reserves / monetary base
    ("AMBSL", "St. Louis Adjusted Monetary Base (1918-2019, discontinued)", "money", "longest base series, monthly; ends 2019-11"),
    ("BOGAMBSL", "Board of Governors Monetary Base adjusted for reserve requirement changes (1959-2013, discontinued)", "money", ""),
    ("BOGNONBR", "Non-borrowed reserves of depository institutions (1959-2013, discontinued)", "liquidity", ""),
    ("BASE", "St. Louis Adjusted Monetary Base, biweekly (1984-2019, discontinued)", "money", ""),
    ("M14066USM144NNBR", "NBER: bills and securities held by Federal Reserve Banks (1914-1969)", "liquidity", "NBER macrohistory"),
    ("M14062USM027NNBR", "NBER: total gold reserves of Federal Reserve Banks (1914-1949)", "liquidity", "NBER macrohistory"),
    ("M14070USM027NNBR", "NBER: total deposits, Federal Reserve Banks (1914-1949)", "liquidity", "NBER macrohistory"),
]


def fred_block(cw: CatalogWriter) -> None:
    f = Fred()
    for sid, name, cat, note in FRED:
        try:
            meta = f.get("series", series_id=sid)["seriess"][0]
            obs = f.get("series/observations", series_id=sid)["observations"]
        except Exception as e:  # noqa: BLE001
            log.warning("FRED %s failed: %s", sid, e)
            continue
        (raw_dir(SOURCE) / f"fred_{sid}.json").write_text(json.dumps({"series": meta, "observations": obs}))
        s = pd.Series([float(o["value"]) if o["value"] != "." else None for o in obs],
                      index=pd.to_datetime([o["date"] for o in obs]), dtype="float64")
        fq = meta["frequency_short"][:1]
        if fq == "M":
            s.index = s.index.to_period("M").to_timestamp()
        cw.add(f"usliq_fred_{sid.lower()}", s, name=name, category=cat, frequency="W" if fq == "B" else fq,
               units=meta["units"], country="US",
               transform_notes=f"FRED {sid}; {note}".strip("; ") + ("; biweekly" if fq == "B" else ""),
               url=f"https://fred.stlouisfed.org/series/{sid}",
               license="FRED terms of use (underlying: Federal Reserve Board / St. Louis Fed / NBER)")


def main() -> None:
    cw = Writer(SOURCE, url=PAGE, license=LICENSE)
    tga_block(cw)
    pdt_block(cw)
    auctions_block(cw)
    buybacks_block(cw)
    fred_block(cw)
    cat = cw.close()
    print(cat[["series_id", "frequency", "start", "end"]].to_string(index=False))


if __name__ == "__main__":
    main()
