"""ECB Data Portal (SDMX REST, no key): policy rates, €STR/EONIA, Euribor, yield curves,
10y convergence yields by country, monetary aggregates, bank loans, MIR, BLS, Eurosystem
balance sheet, CISS, exchange rates and HICP (headline, core and components).

Run: .venv/bin/python -m src.ingest.ecb
Raw:     $FIN_DATA_ROOT/raw/ecb/<FLOW>.<KEY>.csv   (one SDMX csvdata file per series, untouched)
Curated: $FIN_DATA_ROOT/curated/ecb/ecb_*.parquet + _catalog.csv
"""
from __future__ import annotations

import io

import pandas as pd

from src.ingest._europe_common import CatalogWriter, add_series, cached_get, log, raw_dir, spliced, to_period_start

SOURCE = "ecb"
API = "https://data-api.ecb.europa.eu/service/data/{flow}/{key}?format=csvdata"
PORTAL = "https://data.ecb.europa.eu/data/datasets/{flow}/{flow}.{key}"
LICENSE = "ECB statistics: free re-use with source attribution (ECB Data Portal terms)"

U2 = "Euro area, changing composition (EA11 1999 -> EA21 2026, Bulgaria joined 2026-01)"
COUNTRIES_10Y = ["DE", "ES", "IT", "FR", "PT", "GR", "NL", "IE", "BE", "AT", "FI"]

# (series_id, flow, key, name, category, freq, units, country, positive, notes)
S = []


def add(*a):
    S.append(a)


# --- Policy rates (daily calendar, step functions) -------------------------------------------
add("ecb_dfr_d", "FM", "D.U2.EUR.4F.KR.DFR.LEV", "ECB deposit facility rate", "rates", "D", "% p.a.", "EA", False,
    "Daily calendar step series (value in force each day).")
add("ecb_mro_fixed_d", "FM", "D.U2.EUR.4F.KR.MRR_FR.LEV", "ECB main refinancing operations, fixed rate tenders", "rates", "D", "% p.a.", "EA", False,
    "Only defined while MROs were fixed-rate tenders (1999-01 to 2000-06 and since 2008-10-15).")
add("ecb_mro_minbid_d", "FM", "D.U2.EUR.4F.KR.MRR_MBR.LEV", "ECB main refinancing operations, variable rate tenders (minimum bid rate)", "rates", "D", "% p.a.", "EA", False,
    "Only 2000-06-28 to 2008-10-14 (variable rate tender regime).")
add("ecb_mlf_d", "FM", "D.U2.EUR.4F.KR.MLFR.LEV", "ECB marginal lending facility rate", "rates", "D", "% p.a.", "EA", False, "")
# --- Overnight / money market ------------------------------------------------------------------
add("ecb_estr_d", "EST", "B.EU000A2X2A25.WT", "Euro short-term rate (€STR), volume-weighted trimmed mean", "rates", "D", "% p.a.", "EA", False,
    "Business days, published since 2019-10-01.")
add("ecb_eonia_d", "EON", "D.EONIA_TO.RATE", "EONIA overnight rate (discontinued 2021-12-31)", "rates", "D", "% p.a.", "EA", False,
    "From 2019-10-02 EONIA was computed as €STR + 8.5 bp.")
add("ecb_eonia_m", "FM", "M.U2.EUR.4F.MM.EONIA.HSTA", "EONIA, monthly average", "rates", "M", "% p.a.", "EA", False, "Ends 2021-12.")
for t, lab in [("1MD_", "1m"), ("3MD_", "3m"), ("6MD_", "6m"), ("1YD_", "12m")]:
    add(f"ecb_euribor_{lab}_m", "FM", f"M.U2.EUR.RT.MM.EURIBOR{t}.HSTA", f"Euribor {lab}, monthly average", "rates", "M", "% p.a.", "EA", False,
        "Monthly average of daily fixings; pre-1999 national rates are not included (see bundesbank_fibor_*).")
# --- Yield curves (daily, spot rates, Svensson) ------------------------------------------------
for curve, cname in [("G_N_A", "AAA-rated euro area central government bonds"), ("G_N_C", "all euro area central government bonds")]:
    tag = "aaa" if curve == "G_N_A" else "all"
    for m in ["3M", "1Y", "2Y", "5Y", "10Y", "20Y", "30Y"]:
        add(f"ecb_yc_{tag}_spot_{m.lower()}_d", "YC", f"B.U2.EUR.4F.{curve}.SV_C_YM.SR_{m}",
            f"ECB yield curve, {cname}, spot rate {m}", "rates", "D", "% p.a.", "EA", False,
            "Svensson-fitted zero-coupon curve, business days, since 2004-09-06.")
# --- 10y government bond yields by country (convergence criterion, monthly avg) ----------------
for c in COUNTRIES_10Y:
    add(f"ecb_gov10y_{c.lower()}_m", "IRS", f"M.{c}.L.L40.CI.0000.EUR.N.Z",
        f"Long-term (10y) government bond yield for convergence purposes, {c}", "rates", "M", "% p.a.", c, False,
        "Maastricht convergence yield, monthly average of secondary-market yields on ~10y benchmark.")
# --- Money and credit (BSI) ---------------------------------------------------------------------
for agg in ["M1", "M2", "M3"]:
    n = agg[1]
    add(f"ecb_{agg.lower()}_stock_m", "BSI", f"M.U2.Y.V.M{n}0.X.1.U2.2300.Z01.E", f"Euro area monetary aggregate {agg}, outstanding amounts (SA)",
        "money", "M", "EUR millions", "EA", True, "Seasonally and calendar adjusted, end of month stock.")
    add(f"ecb_{agg.lower()}_yoy_m", "BSI", f"M.U2.Y.V.M{n}0.X.I.U2.2300.Z01.A", f"Euro area monetary aggregate {agg}, annual growth rate",
        "money", "M", "% y/y", "EA", False, "Growth computed by the ECB from flows (excludes reclassifications).")
add("ecb_loans_hh_adj_yoy_m", "BSI", "M.U2.Y.U.A20T.A.I.U2.2250.Z01.A", "MFI loans to euro area households, adjusted for sales and securitisation, annual growth",
    "credit", "M", "% y/y", "EA", False, "")
add("ecb_loans_nfc_adj_yoy_m", "BSI", "M.U2.Y.U.A20T.A.I.U2.2240.Z01.A", "MFI loans to euro area non-financial corporations, adjusted for sales and securitisation, annual growth",
    "credit", "M", "% y/y", "EA", False, "")
# --- Bank lending rates (MIR, composite cost of borrowing, new business) ----------------------
for area, cty in [("U2", "EA"), ("ES", "ES"), ("DE", "DE"), ("IT", "IT"), ("FR", "FR")]:
    add(f"ecb_mir_nfc_cost_{cty.lower()}_m", "MIR", f"M.{area}.B.A2I.AM.R.A.2240.EUR.N", f"Composite cost of borrowing for non-financial corporations, {cty}",
        "credit", "M", "% p.a.", cty, False, "New business, composite indicator, since 2003-01.")
    add(f"ecb_mir_hh_house_cost_{cty.lower()}_m", "MIR", f"M.{area}.B.A2C.AM.R.A.2250.EUR.N", f"Composite cost of borrowing for households for house purchase, {cty}",
        "credit", "M", "% p.a.", cty, False, "New business, composite indicator, since 2003-01.")
# --- Bank Lending Survey --------------------------------------------------------------------------
add("ecb_bls_nfc_standards_ea_q", "BLS", "Q.U2.ALL.O.E.Z.B3.ST.S.WFNET", "BLS: credit standards on loans to enterprises, past 3 months (weighted net %)",
    "credit", "Q", "net % of banks (tightening +)", "EA", False, "Positive = tightening.")
add("ecb_bls_hh_house_standards_ea_q", "BLS", "Q.U2.ALL.Z.H.H.B3.ST.S.WFNET", "BLS: credit standards on loans to households for house purchase (weighted net %)",
    "credit", "Q", "net % of banks (tightening +)", "EA", False, "Positive = tightening.")
add("ecb_bls_hh_consumer_standards_ea_q", "BLS", "Q.U2.ALL.Z.H.C.B3.ST.S.WFNET", "BLS: credit standards on consumer credit to households (weighted net %)",
    "credit", "Q", "net % of banks (tightening +)", "EA", False, "Positive = tightening.")
add("ecb_bls_nfc_demand_ea_q", "BLS", "Q.U2.ALL.O.E.Z.B3.ZZ.D.WFNET", "BLS: demand for loans by enterprises (weighted net %)",
    "credit", "Q", "net % of banks (increase +)", "EA", False, "")
add("ecb_bls_hh_house_demand_ea_q", "BLS", "Q.U2.ALL.Z.H.H.B3.ZZ.D.WFNET", "BLS: demand for housing loans by households (weighted net %)",
    "credit", "Q", "net % of banks (increase +)", "EA", False, "")
add("ecb_bls_nfc_standards_es_q", "BLS", "Q.ES.ALL.O.E.Z.B3.ST.S.FNET", "BLS Spain: credit standards on loans to enterprises (net %)",
    "credit", "Q", "net % of banks (tightening +)", "ES", False, "Spanish banks sample (Banco de España), unweighted net percentage.")
add("ecb_bls_hh_house_standards_es_q", "BLS", "Q.ES.ALL.Z.H.H.B3.ST.S.FNET", "BLS Spain: credit standards on housing loans (net %)",
    "credit", "Q", "net % of banks (tightening +)", "ES", False, "Spanish banks sample, unweighted net percentage.")
# --- Eurosystem balance sheet ------------------------------------------------------------------
add("ecb_eurosystem_total_assets_w", "ILM", "W.U2.C.T000000.Z5.Z01", "Eurosystem consolidated weekly financial statement, total assets",
    "liquidity", "W", "EUR millions", "EA", True, "Weekly financial statement; date = Monday of the ISO reference week.")
# --- Systemic stress -------------------------------------------------------------------------------
add("ecb_ciss_new_ea_d", "CISS", "D.U2.Z0Z.4F.EC.SS_CIN.IDX", "New CISS (composite indicator of systemic stress), euro area", "financial_conditions", "D", "index 0-1", "EA", False, "")
add("ecb_ciss_ea_w", "CISS", "D.U2.Z0Z.4F.EC.SS_CI.IDX", "CISS (original methodology), euro area, weekly", "financial_conditions", "W", "index 0-1", "EA", False,
    "Original Hollo-Kremer-Lo Duca CISS (weekly, 1999-2025-05, discontinued); superseded by the new CISS. "
    "Source dates are Fridays (week end); shifted -4 days to the Monday of the week (period start).")
for c in ["DE", "ES", "FR", "IT", "PT", "NL", "IE"]:
    add(f"ecb_ciss_new_{c.lower()}_d", "CISS", f"D.{c}.Z0Z.4F.EC.SS_CIN.IDX", f"New CISS, {c}", "financial_conditions", "D", "index 0-1", c, False, "")
add("ecb_sovciss_ea_m", "CISS", "M.U2.Z0Z.4F.EC.SOV_GDPW.IDX", "SovCISS, euro area (GDP-weighted)", "financial_conditions", "M", "index 0-1", "EA", False, "")
# --- Exchange rates ---------------------------------------------------------------------------------
for cur in ["USD", "GBP", "JPY", "CHF", "CNY"]:
    add(f"ecb_eur{cur.lower()}_d", "EXR", f"D.{cur}.EUR.SP00.A", f"ECB reference rate, {cur} per EUR", "fx", "D", f"{cur} per EUR", "EA", True, "")
add("ecb_eer41_nominal_m", "EXR", "M.E03.EUR.EN00.A", "Euro nominal effective exchange rate, broad group (EER-41)", "fx", "M", "index 1999Q1=100", "EA", True, "")
add("ecb_eer41_real_cpi_m", "EXR", "M.E03.EUR.ERC0.A", "Euro real effective exchange rate (CPI-deflated), broad group (EER-41)", "fx", "M", "index 1999Q1=100", "EA", True, "")
# --- HICP (new HICP dataflow, ECOICOP 2) ------------------------------------------------------------
HICP_NOTE = ("ECB HICP dataflow (ECOICOP ver.2, from 2026 releases). The legacy ICP dataflow is frozen at 2025-12; "
             "this one carries the back data. U2 = changing composition.")
add("ecb_hicp_index_ea_m", "HICP", "M.U2.N.000000.4D0.INX", "HICP overall index, euro area", "inflation", "M", "index (2025=100)", "EA", True, HICP_NOTE)
for item, lab, nm in [("000000", "headline", "overall index"), ("XEF000", "core", "excluding energy, food, alcohol & tobacco"),
                      ("SERV00", "services", "services"), ("IGXE00", "neig", "non-energy industrial goods"),
                      ("NRGY00", "energy", "energy"), ("FOOD00", "food", "food incl. alcohol and tobacco"),
                      ("FOODUN", "food_unprocessed", "unprocessed food"), ("XE0000", "ex_energy", "excluding energy")]:
    add(f"ecb_hicp_{lab}_yoy_ea_m", "HICP", f"M.U2.N.{item}.4D0.ANR", f"HICP {nm}, annual rate, euro area", "inflation", "M", "% y/y", "EA", False, HICP_NOTE)
for c in ["ES", "DE", "FR", "IT", "NL", "PT", "GR", "IE"]:
    add(f"ecb_hicp_headline_yoy_{c.lower()}_m", "HICP", f"M.{c}.N.000000.4D0.ANR", f"HICP overall index, annual rate, {c}", "inflation", "M", "% y/y", c, False, HICP_NOTE)
    add(f"ecb_hicp_core_yoy_{c.lower()}_m", "HICP", f"M.{c}.N.XEF000.4D0.ANR", f"HICP excl. energy, food, alcohol & tobacco, annual rate, {c}", "inflation", "M", "% y/y", c, False, HICP_NOTE)

# --- europe_daily_spain extension (2026-10-13), additive: forwards, EUR OIS proxies, benchmark yields ---
for curve, tag, cname in [("G_N_A", "aaa", "AAA-rated euro area central government bonds"), ("G_N_C", "all", "all euro area central government bonds")]:
    for m in ["1Y", "2Y", "5Y", "10Y"]:
        add(f"ecb_yc_{tag}_fwd_{m.lower()}_d", "YC", f"B.U2.EUR.4F.{curve}.SV_C_YM.IF_{m}",
            f"ECB yield curve, {cname}, instantaneous forward rate {m}", "rates", "D", "% p.a.", "EA", False,
            "Svensson-fitted instantaneous forward, business days, since 2004-09-06. The ECB curve is built on government bonds (AAA = mostly DE/NL/FI/LU), not on swaps.")
for code, lab, nm in [("EU000A2QQF16", "1w", "1 week"), ("EU000A2QQF24", "1m", "1 month"), ("EU000A2QQF32", "3m", "3 months"),
                      ("EU000A2QQF40", "6m", "6 months"), ("EU000A2QQF57", "12m", "12 months")]:
    add(f"ecb_estr_comp_{lab}_d", "EST", f"B.{code}.CR", f"Compounded €STR average rate, {nm} tenor (backward-looking)", "rates", "D", "% p.a.", "EA", False,
        "ECB-published backward-looking compounded €STR over the past tenor; a free, official proxy for realised OIS (NOT forward-looking market OIS, which is licensed). Since 2022-09-15 (ECB publication start; ~2019-10 for the 1w tenor).")
add("ecb_bench_yld_ea_2y_m", "FM", "M.U2.EUR.4F.BB.U2_2Y.YLD", "Euro area 2-year government benchmark bond yield, monthly average", "rates", "M", "% p.a.", "EA", False, "ECB/Refinitiv benchmark, changing composition.")
add("ecb_bench_yld_ea_10y_m", "FM", "M.U2.EUR.4F.BB.U2_10Y.YLD", "Euro area 10-year government benchmark bond yield, monthly average", "rates", "M", "% p.a.", "EA", False, "ECB/Refinitiv benchmark, changing composition.")


def fetch(flow: str, key: str) -> tuple[pd.Series, str]:
    dest = raw_dir(SOURCE) / f"{flow}.{key}.csv"
    content = cached_get(API.format(flow=flow, key=key), dest)
    df = pd.read_csv(io.BytesIO(content), dtype=str)
    df = df[df["KEY"] == f"{flow}.{key}"]
    title = df["TITLE"].dropna().iloc[0] if "TITLE" in df and df["TITLE"].notna().any() else ""
    idx = df["TIME_PERIOD"].map(to_period_start)
    s = pd.Series(pd.to_numeric(df["OBS_VALUE"], errors="coerce").values, index=pd.DatetimeIndex(idx))
    s = s[s.index.notna()]
    return s, title


def main() -> pd.DataFrame:
    cw = CatalogWriter(SOURCE, url="https://data.ecb.europa.eu/", license=LICENSE)
    got: dict[str, pd.Series] = {}
    failed = []
    for sid, flow, key, name, cat, freq, units, cty, pos, notes in S:
        try:
            s, title = fetch(flow, key)
        except Exception as e:  # noqa: BLE001
            log.warning("%s %s.%s failed: %s", sid, flow, key, e)
            failed.append(sid)
            continue
        if freq == "W" and flow == "CISS":
            s.index = s.index - pd.Timedelta(days=4)  # Friday -> Monday of the same week
        got[sid] = s
        tn = f"ECB key {flow}.{key}. {notes}".strip()
        if cty == "EA":
            tn += f" Area: {U2}."
        n = add_series(cw, sid, s, positive=pos, name=name, category=cat, frequency=freq, units=units,
                       country=cty, transform_notes=tn, url=PORTAL.format(flow=flow, key=key))
        log.info("%-40s %6d obs  %s", sid, n, title[:60])

    # --- derived / spliced --------------------------------------------------------------------
    if "ecb_mro_fixed_d" in got and "ecb_mro_minbid_d" in got:
        mro = got["ecb_mro_minbid_d"].dropna().combine_first(got["ecb_mro_fixed_d"].dropna())
        add_series(cw, "ecb_mro_d", mro, name="ECB main refinancing rate (fixed rate or minimum bid rate)", category="rates",
                   frequency="D", units="% p.a.", country="EA",
                   transform_notes="SPLICE: fixed rate tenders 1999-01-01..2000-06-27 and 2008-10-15..; minimum bid rate of variable "
                                   "rate tenders 2000-06-28..2008-10-14 (FM.D.U2.EUR.4F.KR.MRR_FR/MRR_MBR).")
    if "ecb_eonia_d" in got and "ecb_estr_d" in got:
        on = spliced([(got["ecb_eonia_d"], None, "2019-09-30"), (got["ecb_estr_d"], "2019-10-01", None)])
        add_series(cw, "ecb_overnight_eonia_estr_d", on, name="Euro overnight rate: EONIA to 2019-09-30, €STR from 2019-10-01",
                   category="rates", frequency="D", units="% p.a.", country="EA",
                   transform_notes="SPLICE EONIA->€STR at 2019-10-01, no level adjustment: EONIA traded ~8.5 bp above €STR "
                                   "(official spread 8.5 bp), so there is a ~-8.5 bp step at the splice.")
    if "ecb_gov10y_de_m" in got:
        de = got["ecb_gov10y_de_m"]
        for c in ["es", "it", "fr", "pt", "gr", "nl", "ie", "be"]:
            k = f"ecb_gov10y_{c}_m"
            if k in got:
                sp = (got[k] - de).dropna() * 100
                add_series(cw, f"ecb_spread10y_{c}_de_m", sp, name=f"10y government bond spread {c.upper()} vs DE",
                           category="rates", frequency="M", units="basis points", country=c.upper(),
                           transform_notes=f"Derived: (IRS {c.upper()} - IRS DE) x 100, monthly averages.")
    for tag in ["aaa", "all"]:
        a, b = got.get(f"ecb_yc_{tag}_spot_10y_d"), got.get(f"ecb_yc_{tag}_spot_2y_d")
        if a is not None and b is not None:
            add_series(cw, f"ecb_yc_{tag}_10y2y_slope_d", (a - b).dropna() * 100, name=f"ECB {tag.upper()} yield curve slope 10y-2y",
                       category="rates", frequency="D", units="basis points", country="EA",
                       transform_notes="Derived: spot 10y - spot 2y (Svensson), x100.")
    # europe_daily_spain: derived daily curve metrics
    a, b = got.get("ecb_yc_all_spot_10y_d"), got.get("ecb_yc_aaa_spot_10y_d")
    if a is not None and b is not None:
        add_series(cw, "ecb_yc_all_minus_aaa_10y_d", (a - b).dropna() * 100, name="Euro area 10y spot: all-bonds minus AAA curve (sovereign stress proxy)",
                   category="rates", frequency="D", units="basis points", country="EA",
                   transform_notes="Derived: ecb_yc_all_spot_10y_d - ecb_yc_aaa_spot_10y_d, x100. Widens with periphery spreads (2011-12 peak).")
    for tag in ["aaa", "all"]:
        s1, s2 = got.get(f"ecb_yc_{tag}_spot_1y_d"), got.get(f"ecb_yc_{tag}_spot_2y_d")
        if s1 is not None and s2 is not None:
            f = (((1 + s2 / 100) ** 2 / (1 + s1 / 100)) - 1) * 100
            add_series(cw, f"ecb_yc_{tag}_fwd_1y1y_d", f.dropna(), name=f"ECB {tag.upper()} curve, 1y forward rate 1 year ahead (from spot 1y and 2y)",
                       category="rates", frequency="D", units="% p.a.", country="EA",
                       transform_notes="Derived: ((1+s2)^2/(1+s1))-1 with annual-compounded Svensson spot rates (zero-coupon, government bonds).")
    cat = cw.close()
    if failed:
        log.warning("failed series: %s", failed)
    return cat


if __name__ == "__main__":
    main()
