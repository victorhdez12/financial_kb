"""IMF International Financial Statistics (IFS) by country, via the IMF SDMX 3.0 API (api.imf.org).

The classic IFS database (dataservices.imf.org) was dismantled; its content now lives in thematic
IMF.STA dataflows. IFS-equivalent series are pulled from:
  CPI      consumer prices (headline + core index and yoy), monthly, from the 1950s
  ER       exchange rates, domestic currency per USD (period average and end of period)
  MFS_IR   interest rates (policy, discount, money market, T-bill, government bond, deposit, lending...)
  MFS_MA   monetary aggregates, national definitions (base money / M1 / narrow money, history from 1959)
  MFS_DC   broad money, depository corporations (standardised report forms, from 2001-12)
  MFS_CBS  monetary base, central bank survey (from 2001-12)
  IL       international reserves and gold (from 1945/1950)
Countries: G20 members (excluding the EU as such) + Spain, Switzerland, Netherlands.

Raw: one CSV per (dataflow, country), intact, in raw/imf_ifs/. Curated: imf_ifs_<iso3>_<short>.parquet.
OBS_VALUE comes in full units (the SCALE attribute is display metadata only; verified: US reserves 1950 = 24,076,419,999 USD); amounts are stored in millions (USD or domestic currency).

Run: .venv/bin/python -m src.ingest.imf_ifs [--refresh]
"""
from __future__ import annotations

import io
import sys

import pandas as pd

from src.ingest._europe_common import CatalogWriter, add_series, cached_get, log, raw_dir

SRC = "imf_ifs"
API = "https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/{flow}/+/{key}?attributes=dsd&measures=all"
ACCEPT = {"Accept": "application/vnd.sdmx.data+csv;version=2.0.0"}
LIC = "IMF data, free reuse with attribution (IMF copyright and usage terms); IFS-derived"
PAGE = "https://data.imf.org/en/Data-Explorer"

COUNTRIES = {
    "USA": "United States", "ESP": "Spain", "DEU": "Germany", "FRA": "France", "ITA": "Italy", "NLD": "Netherlands",
    "GBR": "United Kingdom", "JPN": "Japan", "CHN": "China", "CAN": "Canada", "CHE": "Switzerland", "AUS": "Australia",
    "KOR": "Korea", "IND": "India", "BRA": "Brazil", "MEX": "Mexico", "RUS": "Russia", "ZAF": "South Africa",
    "TUR": "Turkey", "IDN": "Indonesia", "SAU": "Saudi Arabia", "ARG": "Argentina",
}

# (flow, key template, [(indicator filter, extra-dim filter, short, name, category, units, positive)])
RATE_IND = {  # MFS_IR indicator -> (short, name)
    "MFS166_RT_PT_A_PT": ("rate_policy", "Monetary policy-related rate"),
    "DISR_RT_PT_A_PT": ("rate_discount", "Discount rate"),
    "MFS171_RT_PT_A_PT": ("rate_refi", "Refinancing rate"),
    "MFS161_RT_PT_A_PT": ("rate_keyrepo", "Key repurchase agreement rate"),
    "MFS141_RT_PT_A_PT": ("rate_depfac", "Deposit facility rate"),
    "MMRT_RT_PT_A_PT": ("rate_moneymkt", "Money market rate"),
    "IBRT_S3M_RT_PT_A_PT": ("rate_interbank3m", "Interbank rate, 3 months"),
    "IRTBILL_RT_PT_A_PT": ("rate_tbill", "Treasury bill rate"),
    "GSTBILY_RT_PT_A_PT": ("rate_tbill_yield", "Treasury bill yield"),
    "S13BOND_RT_PT_A_PT": ("rate_govbond", "Government bond yield"),
    "S13BONDSML_RT_PT_A_PT": ("rate_govbond_ml", "Government bond yield, medium and long term"),
    "MFS135_RT_PT_A_PT": ("rate_deposit", "Deposit rate"),
    "MFS162_RT_PT_A_PT": ("rate_lending", "Lending rate"),
}
MA_IND = {
    "NDMBM_MAI": ("money_base_nd", "Base money, national definition (IFS/MFS_MA)"),
    "NDMNM_MAI": ("money_narrow_nd", "Narrow money, national definition (IFS/MFS_MA)"),
    "NDMM1_MAI": ("money_m1_nd", "M1, national definition (IFS/MFS_MA)"),
    "BM_MAI": ("money_broad_ma", "Broad money (IFS/MFS_MA)"),
}
IL_IND = {
    "TRGMV_REVS": ("res_total_gold_mv", "Total reserves incl. gold at market value", "USD"),
    "RXF11_REVS": ("res_ex_gold", "Total reserves excluding gold", "USD"),
    "RGOLDNV_REVS": ("res_gold_nv", "Gold reserves at national valuation", "USD"),
    "RGV_REVS": ("res_gold_oz", "Gold reserves, volume (million fine troy ounces)", "FTO"),
}


def tp_start(t: str) -> pd.Timestamp | None:
    t = str(t)
    try:
        if "-M" in t:
            return pd.Timestamp(int(t[:4]), int(t.split("-M")[1]), 1)
        if "-Q" in t:
            return pd.Timestamp(int(t[:4]), 3 * int(t.split("-Q")[1]) - 2, 1)
        if len(t) == 4:
            return pd.Timestamp(int(t), 1, 1)
    except ValueError:
        return None
    return None


def fetch_csv(flow: str, key: str, iso: str, refresh: bool) -> pd.DataFrame | None:
    dest = raw_dir(SRC) / f"{flow}_{iso}.csv"
    try:
        content = cached_get(API.format(flow=flow, key=key), dest, max_age_hours=0 if refresh else 24 * 7, timeout=600,
                             min_bytes=20, headers=ACCEPT, allow_404=True)
    except Exception as e:  # noqa: BLE001
        log.warning("%s %s failed: %s", flow, iso, e)
        return None
    if not content or len(content) < 200:
        return None
    df = pd.read_csv(io.BytesIO(content), low_memory=False)
    if "OBS_VALUE" not in df.columns:
        return None
    df["date"] = df["TIME_PERIOD"].map(tp_start)
    sc = pd.to_numeric(df.get("SCALE", 0), errors="coerce").fillna(0)
    df["value"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df["scale"] = sc
    return df.dropna(subset=["date"])


def series_of(df: pd.DataFrame, scale_to_millions: bool = False) -> pd.Series:
    s = pd.Series(df["value"].values, index=pd.DatetimeIndex(df["date"]))
    if scale_to_millions:
        s = s / 1e6  # OBS_VALUE is already in full units (SCALE is display metadata only)
    return s[~s.index.duplicated(keep="last")].sort_index()


def main(refresh: bool = False) -> None:
    cw = CatalogWriter(SRC, url=PAGE, license=LIC)
    tot = 0

    def put(sid, s, name, cat, units, iso, flow, pos, note=""):
        nonlocal tot
        n = add_series(cw, sid, s, positive=pos, name=name, category=cat, frequency="M", units=units, country=iso,
                       transform_notes=f"IMF.STA {flow} (IFS successor dataflow), monthly. {note}".strip(),
                       url=f"https://data.imf.org/en/datasets/IMF.STA:{flow}")
        tot += n
        return n

    for iso, cname in COUNTRIES.items():
        # CPI -------------------------------------------------------------------------------
        d = fetch_csv("CPI", f"{iso}.CPI+CCPI._T.IX+YOY_PCH_PA_PT.M", iso, refresh)
        if d is not None:
            for it, tag, nm in (("CPI", "cpi", "CPI"), ("CCPI", "cpi_core", "core CPI")):
                for tr, suf, units, pos in (("IX", "ix", "index (national base)", True), ("YOY_PCH_PA_PT", "yoy", "% y/y", False)):
                    x = d[(d.INDEX_TYPE == it) & (d.TYPE_OF_TRANSFORMATION == tr)]
                    if x.empty:
                        continue
                    put(f"imf_ifs_{iso.lower()}_{tag}_{suf}", series_of(x), f"{cname} {nm}, {'index' if suf == 'ix' else 'annual change'} (IMF)",
                        "inflation", units, iso, "CPI", pos,
                        "Index base year is national (see IMF metadata); use yoy for cross-country comparison." if suf == "ix" else "")
        # Exchange rates ---------------------------------------------------------------------
        if iso != "USA":
            d = fetch_csv("ER", f"{iso}.XDC_USD.PA_RT+EOP_RT.M", iso, refresh)
            if d is not None:
                for tr, suf, nm in (("PA_RT", "avg", "period average"), ("EOP_RT", "eop", "end of period")):
                    x = d[d.TYPE_OF_TRANSFORMATION == tr]
                    if not x.empty:
                        put(f"imf_ifs_{iso.lower()}_fx_usd_{suf}", series_of(x), f"{cname}: domestic currency per USD, {nm} (IMF)",
                            "fx", "domestic currency per USD", iso, "ER", True,
                            "Currency changes (e.g. peso/new peso, euro adoption) are NOT rebased: values are in the currency of the time.")
        # Interest rates ---------------------------------------------------------------------
        d = fetch_csv("MFS_IR", f"{iso}.{'+'.join(RATE_IND)}.M", iso, refresh)
        if d is not None:
            for ind, (short, nm) in RATE_IND.items():
                x = d[d.INDICATOR == ind]
                if not x.empty:
                    put(f"imf_ifs_{iso.lower()}_{short}", series_of(x), f"{cname}: {nm} (IMF)", "rates", "% per annum", iso,
                        "MFS_IR", False, "Rates as reported to the IMF (end of period or period average per country metadata).")
        # Monetary aggregates ----------------------------------------------------------------
        d = fetch_csv("MFS_MA", f"{iso}.{'+'.join(MA_IND)}.*.M", iso, refresh)
        if d is not None:
            for ind, (short, nm) in MA_IND.items():
                x = d[d.INDICATOR == ind]
                if not x.empty:
                    ccy = "USD" if iso == "USA" else "domestic currency"
                    unit_vals = sorted(x["UNIT"].dropna().unique())
                    if len(unit_vals) > 1:
                        x = x[x["UNIT"] == unit_vals[0]]
                    put(f"imf_ifs_{iso.lower()}_{short}", series_of(x, True), f"{cname}: {nm}", "money",
                        f"million {unit_vals[0] if unit_vals else ccy}", iso, "MFS_MA", True,
                        f"Unit as reported ({', '.join(unit_vals)}); values in millions. Sample ends when the country stopped "
                        "reporting this national definition.")
        d = fetch_csv("MFS_DC", f"{iso}.DCORP_L_BM.XDC.M", iso, refresh)
        if d is not None and not d.empty:
            put(f"imf_ifs_{iso.lower()}_money_broad_dc", series_of(d, True), f"{cname}: broad money, depository corporations (SRF)",
                "money", "million domestic currency", iso, "MFS_DC", True, "Standardised report form; starts 2001-12.")
        d = fetch_csv("MFS_CBS", f"{iso}.S121_L_MB_CBS.XDC.M", iso, refresh)
        if d is not None and not d.empty:
            put(f"imf_ifs_{iso.lower()}_monbase_cbs", series_of(d, True), f"{cname}: monetary base, central bank survey (SRF)",
                "money", "million domestic currency", iso, "MFS_CBS", True, "Standardised report form; starts 2001-12.")
        # International reserves --------------------------------------------------------------
        d = fetch_csv("IL", f"{iso}.{'+'.join(IL_IND)}.*.M", iso, refresh)
        if d is not None:
            for ind, (short, nm, unit) in IL_IND.items():
                x = d[(d.INDICATOR == ind) & (d["UNIT"] == unit)]
                if not x.empty:
                    put(f"imf_ifs_{iso.lower()}_{short}", series_of(x, True), f"{cname}: {nm} (IMF)", "liquidity",
                        "million USD" if unit == "USD" else "million fine troy ounces", iso, "IL", True,
                        "Values converted to millions.")
        log.info("%s done (running total %d obs)", iso, tot)
    cat = cw.close()
    log.info("imf_ifs: %d series, %d obs", len(cat), tot)


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
