"""Banco de España - Boletín Estadístico (full CSV bundle be.zip, no key).

Selection of Spanish (and a few international) series: interest rates (MIBOR, Letras,
bonos/obligaciones, IRPH, new-business loan rates), bank credit and doubtful loans (NPL),
household debt and wealth, public debt and deficit, balance of payments, Madrid/IBEX equity
indices, housing prices, registered unemployment (since 1933), and long CPI series for
ES/DE/FR/IT (since 1954-55).

Run: .venv/bin/python -m src.ingest.bde
Raw:     $FIN_DATA_ROOT/raw/bde/be.zip   (the original bundle, ~650 CSV files, latin-1)
Curated: $FIN_DATA_ROOT/curated/bde/bde_*.parquet + _catalog.csv
"""
from __future__ import annotations

import csv
import io
import zipfile

import pandas as pd

from src.ingest._europe_common import CatalogWriter, add_series, cached_get, log, raw_dir, to_period_start

SOURCE = "bde"
ZIP_URL = "https://www.bde.es/webbe/es/estadisticas/compartido/datos/zip/be.zip"
CSV_URL = "https://www.bde.es/webbe/es/estadisticas/compartido/datos/csv/{f}"
LICENSE = "Banco de España: free re-use with attribution (Aviso legal BdE)"

# (series_id, file, code, short English name, category, positive, country, notes)
SEL = [
    # --- interest rates ---
    ("bde_es_mibor_1y_m", "be1901.csv", "D_1E723706.EUR", "MIBOR 1-year (official mortgage reference; Euribor 12m since 1999)", "rates", False, "ES",
     "Official mortgage reference rate: interbank MIBOR 1y until 1998, then the BdE publishes Euribor 12m under the same code (implicit splice at 1999-01)."),
    ("bde_es_irph_m", "be1901.csv", "D_1T9H0000", "IRPH: average mortgage rate (>3y) for free-market housing, all credit institutions", "rates", False, "ES", ""),
    ("bde_es_letras_1y_secondary_m", "be0210.csv", "D_1TES00U7", "Spanish Treasury bills (Letras) 1y, secondary market yield", "rates", False, "ES", ""),
    ("bde_es_bono_3y_secondary_m", "be0210.csv", "D_G2B1F0ZN", "Spanish government bonds 3y, secondary market yield", "rates", False, "ES", ""),
    ("bde_es_gov10y_secondary_m", "be0210.csv", "D_G2B1I0ZP", "Spanish government bonds 10y (convergence criterion), secondary market", "rates", False, "ES", ""),
    ("bde_es_gov_long_yield_m", "be2636.csv", "D_1NBBO320", "Spain long-term government bond yield (international comparison table)", "rates", False, "ES",
     "Long-term benchmark; maturity definition changed over time (not strictly 10y before 1991)."),
    ("bde_de_gov10y_m", "be2636.csv", "D_1NBBO308", "Germany 10y government bond yield (BdE international table)", "rates", False, "DE", ""),
    ("bde_fr_gov10y_m", "be2636.csv", "D_1NBBO303", "France 10y government bond yield (BdE international table)", "rates", False, "FR", ""),
    ("bde_it_gov10y_m", "be2636.csv", "D_1NBBO309", "Italy 10y government bond yield (BdE international table)", "rates", False, "IT", ""),
    ("bde_es_obligaciones_10y_auction_m", "be2127.csv", "D_1G1ABIK0", "Spanish 10y bonds (Obligaciones), auction weighted average yield", "rates", False, "ES",
     "Only months with an auction have a value."),
    ("bde_es_letras_12m_auction_m", "be2127.csv", "D_1TED0G0E", "Spanish 12m Treasury bills, auction weighted average yield", "rates", False, "ES",
     "Only months with an auction have a value."),
    ("bde_es_loan_rate_hh_new_m", "be0210.csv", "D_1TI2THITA", "New-business lending rate to households (synthetic, NDER)", "credit", False, "ES", ""),
    ("bde_es_loan_rate_nfc_new_m", "be0210.csv", "D_1TI2TSOTA", "New-business lending rate to non-financial corporations (synthetic, NDER)", "credit", False, "ES", ""),
    ("bde_es_deposit_rate_hh_new_m", "be0210.csv", "D_1TI2THITP", "New-business deposit rate, households (synthetic)", "rates", False, "ES", ""),
    ("bde_es_prime_rate_banks_m", "be1902.csv", "D_1T2AP326", "Prime rate, banks (discontinued 2012)", "rates", False, "ES", ""),
    ("bde_es_legal_interest_rate_m", "be1901.csv", "D_1T9L0001", "Legal interest rate (interés legal del dinero)", "rates", False, "ES", ""),
    # --- credit / banks ---
    ("bde_es_credit_osr_m", "be0403.csv", "D_BEEA1000", "Credit institutions + EFC: loans to other resident sectors (private sector), stock", "credit", True, "ES",
     "EFC (establecimientos financieros de crédito) excluded from 2014-01 (break)."),
    ("bde_es_doubtful_loans_osr_m", "be0403.csv", "D_BEEA1600", "Credit institutions + EFC: doubtful loans to other resident sectors, stock", "credit", True, "ES", ""),
    ("bde_es_npl_ratio_m", "be0403.csv", "D_BEEA2020", "Doubtful loans ratio (morosidad), other resident sectors", "credit", True, "ES",
     "Official BdE ratio (% of credit), monthly since 1980-12."),
    ("bde_es_hh_debt_rdi_q", "be1608.csv", "DMZ10E000H0.Q", "Households & NPISH total liabilities, % of gross disposable income", "credit", True, "ES", "Financial accounts (CFEE), 4Q rolling income."),
    ("bde_es_hh_loans_rdi_q", "be1608.csv", "DMZ10E800H0.Q", "Households & NPISH loans, % of gross disposable income", "credit", True, "ES", ""),
    ("bde_es_hh_loans_stock_q", "be1608.csv", "DMZ10S800H0.Q", "Households & NPISH loans outstanding (all lenders)", "credit", True, "ES", ""),
    ("bde_es_hh_housing_loans_stock_q", "be1608.csv", "DMZ10S80VHK.Q", "Households housing loans from MFIs, outstanding", "credit", True, "ES", ""),
    ("bde_es_nfc_loans_stock_q", "be0205.csv", "DMZ10S800N0.Q", "Non-financial corporations: loans outstanding (all lenders)", "credit", True, "ES", "Financial accounts (CFEE)."),
    ("bde_es_nfc_debt_securities_stock_q", "be0205.csv", "DMZ10S400N0.Q", "Non-financial corporations: debt securities outstanding", "credit", True, "ES", "Financial accounts (CFEE)."),
    ("bde_es_hh_net_wealth_q", "be1606.csv", "DMZ10SP000H.Q", "Households & NPISH net wealth", "housing", True, "ES", ""),
    ("bde_es_hh_housing_wealth_q", "be1606.csv", "D_TKB070C0_ESTI", "Households residential real-estate wealth (BdE estimate)", "housing", True, "ES", ""),
    # --- fiscal / external ---
    ("bde_es_gov_debt_gdp_q", "be1107.csv", "DTNPDE2010_P0000P_PS_APU", "General government debt (EDP), % of GDP, quarterly", "fiscal", True, "ES", ""),
    ("bde_es_gov_balance_gdp_a", "be0209.csv", "DANPDE2010_S0000P_APU", "General government net lending/borrowing (EDP), % of GDP", "fiscal", False, "ES", ""),
    ("bde_es_ca_balance_q", "be0206.csv", "DEEQ.N.ES.W1.S1.S1.T.B.CA._Z._Z._Z.EUR._T._X.N.ALL", "Current account balance (BPM6)", "growth", False, "ES", ""),
    ("bde_es_niip_q", "be0206.csv", "DEEQ.N.ES.W1.S1.S1.LE.N.FA._T.F._Z.EUR._T._X.N.ALL", "Net international investment position", "growth", False, "ES", "End of quarter stock."),
    # --- markets ---
    ("bde_es_ibex35_m", "be2225.csv", "D_1TGC000A", "IBEX 35 index", "markets", True, "ES", "Price index (no dividends)."),
    ("bde_es_madrid_general_index_m", "be2225.csv", "D_$G500JA0", "Madrid Stock Exchange general index (IGBM)", "markets", True, "ES", "Price index (no dividends), base 1985=100."),
    ("bde_es_madrid_market_cap_m", "be2223.csv", "D_$G500900", "Madrid Stock Exchange market capitalisation, resident companies", "markets", True, "ES",
     "Annual (December) observations early on, monthly later; pesetas converted to euros by BdE."),
    ("bde_es_per_m", "be2226.csv", "D_1G500S01", "Madrid Stock Exchange price/earnings ratio", "valuation", True, "ES", ""),
    ("bde_eurostoxx_broad_m", "be2227.csv", "D_1NCHE072", "Dow Jones STOXX broad index (EU)", "markets", True, "EA", ""),
    ("bde_es_house_price_m2_q", "be2507.csv", "DHIVTNOAPLPMMUVT_RLI.T", "Average appraised price per m2 of free-market housing (MIVAU)", "housing", True, "ES", ""),
    # --- labour / activity ---
    ("bde_es_registered_unemployed_m", "be2415.csv", "D_1JA0D000", "Registered unemployment (paro registrado, SEPE)", "employment", True, "ES",
     "Methodological breaks (1985 and 2005 SISPE); not comparable with EPA."),
    ("bde_es_ss_affiliates_m", "be2419.csv", "DEPSEGS1AF_XRTODS.M", "Social Security affiliates, end of month", "employment", True, "ES", ""),
    ("bde_es_unemp_rate_epa_q", "be1602.csv", "DEPA202140_TSPA.T", "Unemployment rate (EPA, base 2021)", "employment", True, "ES", ""),
    ("bde_es_unemp_rate_sa_m", "be2611.csv", "D_2NECF120", "Spain unemployment rate, SA (international comparison table)", "employment", True, "ES", ""),
    ("bde_es_ip_m", "be2622.csv", "D_1NEAB820", "Spain industrial production index (excl. construction)", "growth", True, "ES", ""),
    ("bde_de_ip_m", "be2622.csv", "D_1NEAB808", "Germany industrial production index (excl. construction)", "growth", True, "DE", ""),
    ("bde_es_real_gdp_q", "be2602.csv", "D_UNFKB020", "Spain real GDP, SA", "growth", True, "ES", ""),
    ("bde_fr_real_gdp_q", "be2602.csv", "D_UNFKB003", "France real GDP, SA (since 1950)", "growth", True, "FR", ""),
    # --- prices ---
    ("bde_es_cpi_m", "be2621.csv", "D_1NEACJ20", "Spain CPI (long series)", "inflation", True, "ES", "Rebased by BdE to 2015=100, chained across INE bases."),
    ("bde_de_cpi_m", "be2621.csv", "D_1NEACJ08", "Germany CPI (long series)", "inflation", True, "DE", "West Germany before 1991 (as compiled by the BdE)."),
    ("bde_fr_cpi_m", "be2621.csv", "D_1NEACJ03", "France CPI (long series)", "inflation", True, "FR", ""),
    ("bde_it_cpi_m", "be2621.csv", "D_1NEACJ09", "Italy CPI (long series)", "inflation", True, "IT", ""),
    ("bde_es_hicp_yoy_long_m", "be0208.csv", "D_1NEAC020", "Spain HICP/CPI annual rate, long series (discontinued 2021-06)", "inflation", False, "ES",
     "Back-extended by the BdE with CPI before 1996; discontinued in 2021-06."),
    ("bde_es_ppi_m", "be2503.csv", "DCIIPR2021IND.M", "Spain industrial producer prices, domestic market (IPRI)", "inflation", True, "ES", ""),
    # --- fx ---
    ("bde_usd_per_eur_ecu_m", "be0116.csv", "D_1PFJ1001", "USD per EUR (ECU before 1999), chained series, monthly average", "fx", True, "EA",
     "SPLICE by BdE: ECU 1979-1998 -> EUR 1999 (1 EUR = 1 ECU)."),
]


# BdE metadata units that are wrong in the CSV header
UNITS_OVERRIDE = {"D_BEEA2020": "%"}


def parse_bde_csv(raw: bytes) -> tuple[list[str], dict[str, list[str]], list[list[str]]]:
    rows = list(csv.reader(io.StringIO(raw.decode("latin-1"))))
    codes = rows[0]
    meta = {}
    for r in rows[1:6]:
        if r:
            meta[r[0].upper()] = r
    data = [r for r in rows[6:] if r and to_period_start(r[0]) is not None]
    return codes, meta, data


def series_from(codes, meta, data, code: str) -> tuple[pd.Series, str, str, str]:
    j = codes.index(code)
    get = lambda k: next((v[j] for kk, v in meta.items() if kk.startswith(k) and j < len(v)), "")  # noqa: E731
    desc, units, freq = get("DESCRIPCIÓN DE LA SERIE"), get("DESCRIPCIÓN DE LAS UNIDADES"), get("FRECUENCIA").upper()
    idx, vals = [], []
    for r in data:
        if j >= len(r):
            continue
        d = to_period_start(r[0])
        if freq.startswith("TRIM") and len(r[0].split()) == 2:
            d = d - pd.DateOffset(months=2)  # 'MAR 1995' = Q1 -> 1995-01-01
        idx.append(d)
        v = r[j].strip()
        try:
            vals.append(float(v))
        except ValueError:  # '_', '...', '' = not available
            vals.append(float("nan"))
    return pd.Series(vals, index=pd.DatetimeIndex(idx)), desc, units, freq


def main() -> pd.DataFrame:
    dest = raw_dir(SOURCE) / "be.zip"
    content = cached_get(ZIP_URL, dest, min_bytes=1_000_000, timeout=600)
    zf = zipfile.ZipFile(io.BytesIO(content))
    cache: dict[str, tuple] = {}
    cw = CatalogWriter(SOURCE, url="https://www.bde.es/webbe/es/estadisticas/recursos/descargas-completas.html", license=LICENSE)
    fmap = {"MENSUAL": "M", "TRIMESTRAL": "Q", "ANUAL": "A", "DIARIA": "D"}
    got = {}
    for sid, f, code, name, cat, pos, cty, notes in SEL:
        if f not in cache:
            try:
                cache[f] = parse_bde_csv(zf.read(f))
            except KeyError:
                log.warning("%s missing in be.zip", f)
                cache[f] = None
        if cache[f] is None or code not in cache[f][0]:
            log.warning("%s: code %s not found in %s", sid, code, f)
            continue
        s, desc, units, freq = series_from(*cache[f], code)
        fq = fmap.get(freq.split()[0] if freq else "", "M")
        got[sid] = s
        n = add_series(cw, sid, s, positive=pos, name=name, category=cat, frequency=fq, units=UNITS_OVERRIDE.get(code, units or ""),
                       country=cty, transform_notes=f"BdE series {code} ({f}): {desc}. {notes}".strip(),
                       url=CSV_URL.format(f=f))
        log.info("%-38s %5d obs  %s", sid, n, units)
    # derived: NPL ratio back to 1962 from stocks
    if "bde_es_doubtful_loans_osr_m" in got and "bde_es_credit_osr_m" in got:
        ratio = (got["bde_es_doubtful_loans_osr_m"] / got["bde_es_credit_osr_m"] * 100).dropna()
        add_series(cw, "bde_es_npl_ratio_computed_m", ratio, positive=True, name="Doubtful loans / loans to other resident sectors (computed)",
                   category="credit", frequency="M", units="%", country="ES",
                   transform_notes="Derived: D_BEEA1600 / D_BEEA1000 x 100; extends the official ratio (bde_es_npl_ratio_m, from 1980-12) back to 1962. "
                                   "Pre-1980 'dudosos' definitions differ (morosos/dudoso cobro); EFC excluded from 2014 in both terms.")
    return cw.close()


if __name__ == "__main__":
    main()
