"""Eurostat dissemination API (SDMX 2.1, SDMX-CSV, no key): quarterly real GDP, monthly
unemployment, industrial production, economic sentiment (ESI) and consumer confidence,
government debt and deficit (EDP), and current account balances.

Run: .venv/bin/python -m src.ingest.eurostat
Raw:     $FIN_DATA_ROOT/raw/eurostat/<dataset>__<key>.csv
Curated: $FIN_DATA_ROOT/curated/eurostat/eurostat_*.parquet + _catalog.csv

Euro area aggregate: EA21 (fixed composition incl. Bulgaria, back-calculated) when Eurostat
publishes it, else EA20; the chosen code is written in transform_notes. HICP is taken from
the ECB (src.ingest.ecb): Eurostat's prc_hicp_manr was frozen at the 2026 ECOICOP-2 switch.
"""
from __future__ import annotations

import io

import pandas as pd

from src.ingest._europe_common import CatalogWriter, add_series, cached_get, log, raw_dir, to_period_start

SOURCE = "eurostat"
API = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/{ds}/{key}?format=SDMX-CSV"
PAGE = "https://ec.europa.eu/eurostat/databrowser/view/{ds}/default/table"
LICENSE = "Eurostat: CC BY 4.0 (Commission Decision 2011/833/EU), cite Eurostat"

EA_CODES = ["EA21", "EA20"]
MAIN = ["DE", "ES", "FR", "IT", "NL", "PT"]

# (tag, dataset, key template with {geo}, name, category, freq, units, positive, geos, note)
SPEC = [
    ("gdp_real", "namq_10_gdp", "Q.CLV10_MEUR.SCA.B1GQ.{geo}", "Real GDP (chain-linked volumes 2010, SCA)", "growth", "Q",
     "EUR millions, chain-linked 2010", True, ["EA"] + MAIN + ["GR", "IE", "BE", "AT"], "Seasonally and calendar adjusted."),
    ("gdp_qoq", "namq_10_gdp", "Q.CLV_PCH_PRE.SCA.B1GQ.{geo}", "Real GDP growth, q/q", "growth", "Q", "% q/q", False,
     ["EA"] + MAIN, "SCA, chain-linked volumes."),
    ("gdp_yoy", "namq_10_gdp", "Q.CLV_PCH_SM.SCA.B1GQ.{geo}", "Real GDP growth, y/y (same quarter previous year)", "growth", "Q",
     "% y/y", False, ["EA"] + MAIN, "SCA, chain-linked volumes."),
    ("unemp", "une_rt_m", "M.SA.TOTAL.PC_ACT.T.{geo}", "Unemployment rate, total, SA", "employment", "M", "% of labour force", True,
     ["EA", "EU27_2020"] + MAIN + ["GR", "IE"], "ILO definition, monthly, seasonally adjusted."),
    ("unemp_youth", "une_rt_m", "M.SA.Y_LT25.PC_ACT.T.{geo}", "Youth unemployment rate (<25), SA", "employment", "M",
     "% of labour force", True, ["EA", "ES", "IT", "DE", "FR"], "ILO definition, monthly, seasonally adjusted."),
    ("ip", "sts_inpr_m", "M.PRD.B-D.SCA.I21.{geo}", "Industrial production index (B-D, excl. construction), SCA", "growth", "M",
     "index 2021=100", True, ["EA"] + MAIN, "Volume index, seasonally and calendar adjusted."),
    ("esi", "ei_bssi_m_r2", "M.BS-ESI-I.SA.{geo}", "Economic sentiment indicator (ESI)", "growth", "M",
     "index (long-term avg=100)", True, ["EA", "EU27_2020"] + MAIN, "DG ECFIN business and consumer surveys."),
    ("consconf", "ei_bssi_m_r2", "M.BS-CSMCI-BAL.SA.{geo}", "Consumer confidence indicator", "growth", "M", "balance (pp)", False,
     ["EA"] + MAIN, "DG ECFIN consumer survey, SA balance."),
    ("gov_debt_gdp", "gov_10dd_edpt1", "A.PC_GDP.S13.GD.{geo}", "General government gross debt (EDP/Maastricht)", "fiscal", "A",
     "% of GDP", True, ["EA"] + MAIN + ["GR", "IE", "BE", "AT"], "EDP notification, annual."),
    ("gov_balance_gdp", "gov_10dd_edpt1", "A.PC_GDP.S13.B9.{geo}", "General government net lending (+) / borrowing (-)", "fiscal", "A",
     "% of GDP", False, ["EA"] + MAIN + ["GR", "IE", "BE", "AT"], "EDP notification, annual (negative = deficit)."),
    ("gov_debt_gdp_q", "gov_10q_ggdebt", "Q.GD.S13.PC_GDP.{geo}", "General government gross debt, quarterly", "fiscal", "Q",
     "% of GDP", True, ["EA"] + MAIN + ["GR"], "Quarterly government debt."),
    ("ca_balance", "bop_c6_q", "Q.MIO_EUR.CA.S1.S1.BAL.WRL_REST.{geo}", "Current account balance vs rest of world", "growth", "Q",
     "EUR millions", False, ["DE", "ES", "FR", "IT", "NL", "PT"], "BPM6, not seasonally adjusted."),
]


def fetch(ds: str, key: str) -> pd.Series | None:
    dest = raw_dir(SOURCE) / f"{ds}__{key.replace('+', '_')}.csv"
    content = cached_get(API.format(ds=ds, key=key), dest, allow_404=True, retries=2, min_bytes=100)
    if not content or content.lstrip().startswith(b"<"):
        return None
    df = pd.read_csv(io.BytesIO(content), dtype=str)
    if df.empty or "TIME_PERIOD" not in df:
        return None
    idx = df["TIME_PERIOD"].map(to_period_start)
    s = pd.Series(pd.to_numeric(df["OBS_VALUE"], errors="coerce").values, index=pd.DatetimeIndex(idx))
    return s[s.index.notna()].sort_index()


def main() -> pd.DataFrame:
    cw = CatalogWriter(SOURCE, url="https://ec.europa.eu/eurostat/web/main/data/database", license=LICENSE)
    gaps = []
    for tag, ds, tmpl, name, cat, freq, units, pos, geos, note in SPEC:
        for geo in geos:
            candidates = EA_CODES if geo == "EA" else ["EL" if geo == "GR" else geo]  # Eurostat uses EL for Greece
            s, used = None, None
            for g in candidates:
                try:
                    s = fetch(ds, tmpl.format(geo=g))
                except Exception as e:  # noqa: BLE001
                    log.warning("%s %s: %s", ds, g, e)
                    s = None
                if s is not None and s.notna().any():
                    used = g
                    break
            if used is None:
                gaps.append(f"{tag}:{geo}")
                continue
            cty = "EA" if geo == "EA" else ("EU" if geo.startswith("EU") else geo)
            sid = f"eurostat_{tag}_{cty.lower()}_{freq.lower()}"
            tn = f"Eurostat {ds}, key {tmpl.format(geo=used)}. {note}"
            if geo == "EA":
                tn += f" Euro area code {used} (fixed composition, back-calculated; not the changing-composition EA)."
            n = add_series(cw, sid, s, positive=pos, name=f"{name}, {used}", category=cat, frequency=freq, units=units,
                           country=cty, transform_notes=tn, url=PAGE.format(ds=ds))
            log.info("%-36s %5d obs (%s)", sid, n, used)
    if gaps:
        log.warning("not available: %s", gaps)
    return cw.close()


if __name__ == "__main__":
    main()
