"""INE (Instituto Nacional de Estadística) - Tempus3 JSON API (no key).

CPI (annual rate since 1962, index and core since 2002), EPA unemployment rate (base 2021,
from 2002), quarterly national accounts GDP (chain-linked volume index, SCA, from 1995) and
the housing price index IPV (from 2007).

Extensions (europe_gaps, 2026-10-13), additive only:
  * EPA 1976Q3-2001Q4 (INE "series76_01.xls": official re-weighted retrospective series, old
    pre-2002 unemployment definition) for active/employed/unemployed (thousands), activity and
    unemployment rates, both sexes / men / women, plus the same post-2002 aggregates from Tempus and
    a spliced "_linked_q" series (level splice, break in 2002 noted in transform_notes).
  * CPI: monthly change from 1961 (Tempus IPC290752) and a linked general index since 1961-01
    (INE index base 2021 from 2002 + BdE/INE linked index rescaled before; Tempus only serves the
    index from 2002).

Run: .venv/bin/python -m src.ingest.ine
Raw:     $FIN_DATA_ROOT/raw/ine/<COD>.json
Curated: $FIN_DATA_ROOT/curated/ine/ine_*.parquet + _catalog.csv
"""
from __future__ import annotations

import json
import re

import pandas as pd

from src.ingest._europe_common import CatalogWriter, add_series, cached_get, log, raw_dir
from src.ingest._extlong_common import curated_dir

SOURCE = "ine"
API = "https://servicios.ine.es/wstempus/js/ES/DATOS_SERIE/{cod}?nult=5000"
SERIE_URL = "https://www.ine.es/consul/serie.do?s={cod}"
LICENSE = "INE: free re-use with attribution (Aviso legal INE, CC BY 4.0-compatible)"

# (series_id, INE code, name, category, freq, units, positive, notes)
SEL = [
    ("ine_ipc_yoy_m", "IPC290750", "Spain CPI (IPC), general index, annual rate", "inflation", "M", "% y/y", False,
     "Official annual rate published since 1962 (computed on the successive INE bases)."),
    ("ine_ipc_index_m", "IPC290751", "Spain CPI (IPC), general index", "inflation", "M", "index (base 2021=100)", True,
     "Tempus only serves the index from 2002; for 1954+ use bde_es_cpi_m."),
    ("ine_ipc_core_yoy_m", "IPC292510", "Spain core CPI (excl. unprocessed food and energy), annual rate", "inflation", "M", "% y/y", False, ""),
    ("ine_ipc_core_index_m", "IPC292511", "Spain core CPI (excl. unprocessed food and energy), index", "inflation", "M", "index (base 2021=100)", True, ""),
    ("ine_epa_unemp_rate_q", "EPA423474", "EPA unemployment rate, total, both sexes (base 2021)", "employment", "Q", "% of active population", True,
     "Base-2021 EPA series, back-calculated to 2002. Pre-2002 EPA (from 1976) is not served by Tempus (see docs gap)."),
    ("ine_epa_unemp_rate_16_19_q", "EPA423476", "EPA unemployment rate, ages 16-19", "employment", "Q", "% of active population", True, ""),
    ("ine_epa_unemp_rate_20_24_q", "EPA423477", "EPA unemployment rate, ages 20-24", "employment", "Q", "% of active population", True, ""),
    ("ine_gdp_volume_index_q", "CNTR6652", "Spain GDP at market prices, chain-linked volume index, SCA", "growth", "Q", "index (2020=100)", True,
     "Quarterly National Accounts (CNTR), seasonally and calendar adjusted."),
    ("ine_gdp_qoq_q", "CNTR6653", "Spain real GDP growth, q/q, SCA", "growth", "Q", "% q/q", False, ""),
    ("ine_gdp_yoy_q", "CNTR6654", "Spain real GDP growth, y/y, SCA", "growth", "Q", "% y/y", False, ""),
    ("ine_ipv_index_q", "IPV1209", "Spain housing price index (IPV), general", "housing", "Q", "index (2025=100)", True, "Transaction-based, from 2007."),
    ("ine_ipv_yoy_q", "IPV1376", "Spain housing price index (IPV), annual rate", "housing", "Q", "% y/y", False, ""),
    ("ine_ipv_new_index_q", "IPV1613", "Spain housing price index (IPV), new dwellings", "housing", "Q", "index (2025=100)", True, ""),
    ("ine_ipv_used_index_q", "IPV1618", "Spain housing price index (IPV), second-hand dwellings", "housing", "Q", "index (2025=100)", True, "Base 2025=100 (units fixed 2026-10-13: earlier catalog said 2015)."),
    ("ine_ipv_used_yoy_q", "IPV1620", "Spain housing price index (IPV), second-hand dwellings, annual rate", "housing", "Q", "% y/y", False, ""),
    ("ine_ipv_new_yoy_q", "IPV1615", "Spain housing price index (IPV), new dwellings, annual rate", "housing", "Q", "% y/y", False, ""),
    ("ine_ipv_qoq_q", "IPV1522", "Spain housing price index (IPV), general, quarterly change", "housing", "Q", "% q/q", False, ""),
    ("ine_etdp_sales_dwellings_m", "ETDP1510", "Property transfers (ETDP): home sales (compraventa de viviendas), total", "housing", "M", "number", True,
     "Registry-based, monthly from 2007-01 (INE ETDP)."),
    ("ine_etdp_sales_new_m", "ETDP1825", "Property transfers (ETDP): new-dwelling sales", "housing", "M", "number", True, ""),
    ("ine_etdp_sales_used_m", "ETDP1824", "Property transfers (ETDP): second-hand dwelling sales", "housing", "M", "number", True, ""),
    ("ine_etdp_sales_protected_m", "ETDP1822", "Property transfers (ETDP): protected-dwelling sales", "housing", "M", "number", True, ""),
    ("ine_hpt_mortgages_n_new_m", "HPT34618", "Mortgages on dwellings (INE H), number, new base (2003-01+)", "credit", "M", "number", True, "Base nueva."),
    ("ine_hpt_mortgages_amt_new_m", "HPT34565", "Mortgages on dwellings (INE H), amount, new base (2003-01+)", "credit", "M", "EUR thousand", True, "Base nueva."),
    ("ine_hpt_mortgages_n_old_m", "HPT8268", "Mortgages on dwellings (INE H), number, old base (1994-2003)", "credit", "M", "number", True, "Base antigua, ends 2003-12."),
    ("ine_hpt_mortgages_amt_old_m", "HPT8215", "Mortgages on dwellings (INE H), amount, old base (1994-2003)", "credit", "M", "EUR thousand", True, "Base antigua, ends 2003-12."),
    ("ine_ipi_sca_index_m", "IPI15360", "Spain industrial production index, total industry, SCA", "growth", "M", "index (2021=100)", True, "Seasonally and calendar adjusted, from 1992."),
    ("ine_ipi_sca_yoy_m", "IPI15374", "Spain industrial production, total industry, annual rate, SCA", "growth", "M", "% y/y", False, ""),
    ("ine_ipi_sca_mom_m", "IPI15381", "Spain industrial production, total industry, monthly change, SCA", "growth", "M", "% m/m", False, ""),
    ("ine_ipi_cal_index_m", "IPI14404", "Spain industrial production index, total industry, calendar adjusted", "growth", "M", "index (2021=100)", True, "Calendar adjusted, from 1992."),
    ("ine_ipi_cal_yoy_m", "IPI14424", "Spain industrial production, total industry, annual rate, calendar adjusted", "growth", "M", "% y/y", False, ""),
    ("ine_ipi_nsa_index_m", "IPI13491", "Spain industrial production index, total industry, unadjusted", "growth", "M", "index (2021=100)", True, "Raw index from 1975."),
    ("ine_ipi_nsa_yoy_m", "IPI13868", "Spain industrial production, total industry, annual rate, unadjusted", "growth", "M", "% y/y", False, ""),
]


def period_start(anyo: int, per: int) -> pd.Timestamp | None:
    if 1 <= per <= 12:
        return pd.Timestamp(anyo, per, 1)
    if 19 <= per <= 22:
        return pd.Timestamp(anyo, 3 * (per - 18) - 2, 1)
    if per == 28:
        return pd.Timestamp(anyo, 1, 1)
    return None


def fetch(cod: str) -> tuple[pd.Series, str]:
    content = cached_get(API.format(cod=cod), raw_dir(SOURCE) / f"{cod}.json", min_bytes=100)
    d = json.loads(content)
    idx, vals = [], []
    for x in d.get("Data", []):
        t = period_start(int(x["Anyo"]), int(x["FK_Periodo"]))
        if t is None:
            continue
        idx.append(t)
        v = x.get("Valor")
        vals.append(float("nan") if v is None or x.get("Secreto") else float(v))
    return pd.Series(vals, index=pd.DatetimeIndex(idx)).sort_index(), d.get("Nombre", "")


# ---------------------------------------------------------------------------------------------
# Extensions: EPA 1976-2001 retrospective + post-2002 aggregates + linked series; CPI linked index
# ---------------------------------------------------------------------------------------------
RETRO_URL = "https://ine.es/epa02/series76_01.xls"
RETRO_PAGE = "https://ine.es/epa02/repercusion_nacio7601.htm"
SEXES = [("t", "Ambos sexos", "both sexes", 0), ("m", "Varones", "men", 6), ("f", "Mujeres", "women", 12)]
# variable -> (xls sheet, tempus codes by sex, name, units, category)
EPA_VARS = {
    "unemp_rate": ("TasaParo", {"t": "EPA423474", "m": "EPA423488", "f": "EPA423501"}, "unemployment rate", "% of active population"),
    "act_rate": ("TasaAct", {"t": "EPA388079", "m": "EPA388093", "f": "EPA388106"}, "activity rate", "% of population 16+"),
    "activos": ("Activos", {"t": "EPA387794", "m": "EPA387879", "f": "EPA387959"}, "active population", "thousand persons"),
    "ocupados": ("Ocupados", {"t": "EPA387796", "m": "EPA387880", "f": "EPA387960"}, "employed", "thousand persons"),
    "parados": ("Parados", {"t": "EPA387800", "m": "EPA387882", "f": "EPA387962"}, "unemployed", "thousand persons"),
}
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4}


def read_retro_sheet(path, sheet: str) -> dict[str, tuple[pd.Series, pd.Series]]:
    """Return {sex_key: (reponderado, publicado)} quarterly series from one sheet of series76_01.xls."""
    import xlrd

    ws = xlrd.open_workbook(str(path)).sheet_by_name(sheet)
    year = None
    idx, rows = [], []
    for r in range(7, ws.nrows):
        row = ws.row_values(r)
        lab = str(row[0]).strip()
        m = re.match(r"^(IV|III|II|I)\s*(\d{4})?\s*$", lab)
        if not m:
            continue
        if m.group(2):
            year = int(m.group(2))
        if year is None or not isinstance(row[2], float):
            continue
        idx.append(pd.Timestamp(year, 3 * _ROMAN[m.group(1)] - 2, 1))
        rows.append(row)
    ix = pd.DatetimeIndex(idx)
    out = {}
    for key, _, _, c0 in SEXES:
        pub = pd.Series([r[2 + c0] if isinstance(r[2 + c0], float) else float("nan") for r in rows], index=ix)
        rew = pd.Series([r[4 + c0] if isinstance(r[4 + c0], float) else float("nan") for r in rows], index=ix)
        out[key] = (rew, pub)
    return out


def epa_retro(cw) -> int:
    n = 0
    path = raw_dir(SOURCE) / "series76_01.xls"
    try:
        cached_get(RETRO_URL, path, min_bytes=5000, max_age_hours=24 * 30)
    except Exception as e:  # noqa: BLE001
        log.warning("EPA 1976-2001 retrospective not available: %s", e)
        return 0
    note_pre = ("INE retrospective EPA series 1976Q3-2001Q4 (series76_01.xls), 'datos reponderados' = re-weighted with the "
                "post-2001 population projections; OLD pre-2002 definition of unemployment (not the EPA-2002 definition). "
                "Quarterly, not seasonally adjusted. ")
    for var, (sheet, codes, vname, units) in EPA_VARS.items():
        retro = read_retro_sheet(path, sheet)
        for key, esp, eng, _ in SEXES:
            rew, pub = retro[key]
            cat = "employment"
            base = f"ine_epa76_{var}_{key}_q"
            n += add_series(cw, base, rew, positive=False, name=f"EPA {vname}, {eng}, 1976Q3-2001Q4 (re-weighted, old definition)",
                            category=cat, frequency="Q", units=units, country="ES",
                            transform_notes=note_pre + f"Sheet '{sheet}', block '{esp}'.", url=RETRO_PAGE)
            if var == "unemp_rate" and key == "t":
                n += add_series(cw, "ine_epa76_unemp_rate_published_t_q", pub, positive=False,
                                name="EPA unemployment rate, both sexes, 1976Q3-2001Q4 (as originally published)", category=cat,
                                frequency="Q", units=units, country="ES",
                                transform_notes=note_pre.replace("'datos reponderados' = re-weighted with the post-2001 population projections",
                                                                 "'datos publicados' = as published at the time (pre-reweighting)") + f"Sheet '{sheet}'.",
                                url=RETRO_PAGE)
            # post-2002 aggregate from Tempus
            cod = codes[key]
            try:
                post, nombre = fetch(cod)
            except Exception as e:  # noqa: BLE001
                log.warning("EPA %s (%s) failed: %s", base, cod, e)
                continue
            post_id = "ine_epa_unemp_rate_q" if (var, key) == ("unemp_rate", "t") else f"ine_epa_{var}_{key}_q"
            if post_id != "ine_epa_unemp_rate_q":
                n += add_series(cw, post_id, post, positive=False, name=f"EPA {vname}, {eng} (base 2021, from 2002)", category=cat,
                                frequency="Q", units=units, country="ES",
                                transform_notes=f"INE Tempus series {cod}: {nombre.strip()}", url=SERIE_URL.format(cod=cod))
            post = post.dropna()
            linked = pd.concat([rew[rew.index < pd.Timestamp(2002, 1, 1)], post[post.index >= pd.Timestamp(2002, 1, 1)]]).sort_index()
            q4, q1 = rew.dropna().iloc[-1], post.iloc[0]
            n += add_series(cw, f"ine_epa_{var}_{key}_linked_q", linked, positive=False,
                            name=f"EPA {vname}, {eng}, 1976Q3-present (spliced)", category=cat, frequency="Q", units=units,
                            country="ES",
                            transform_notes=(f"SPLICE: 1976Q3-2001Q4 = ine_epa76_{var}_{key}_q (old unemployment definition, re-weighted) + "
                                             f"2002Q1+ = Tempus {cod} (EPA-2002 definition, base 2021). Plain level splice, NO adjustment: "
                                             f"definition break at 2002Q1 (last old {q4:.2f} -> first new {q1:.2f}; for rates the new definition "
                                             f"reads lower). See INE working paper 'Enlace de las series de paro 1976-2000' (Aug 2005)."),
                            url=RETRO_PAGE)
    return n


def cpi_extensions(cw) -> int:
    n = 0
    # monthly change since 1961
    try:
        mom, nombre = fetch("IPC290752")
        n += add_series(cw, "ine_ipc_mom_m", mom, positive=False, name="Spain CPI (IPC), general index, monthly change",
                        category="inflation", frequency="M", units="% m/m", country="ES",
                        transform_notes=f"INE Tempus series IPC290752: {nombre.strip()} Official rates, one decimal, from 1961-02.",
                        url=SERIE_URL.format(cod="IPC290752"))
    except Exception as e:  # noqa: BLE001
        log.warning("IPC290752 failed: %s", e)
    # linked index since 1961-01
    try:
        ine, _ = fetch("IPC290751")
        bde = pd.read_parquet(curated_dir("bde") / "bde_es_cpi_m.parquet")
        bde = pd.Series(bde["value"].values, index=pd.to_datetime(bde["date"]))
    except Exception as e:  # noqa: BLE001
        log.warning("linked CPI index not built (need ine IPC290751 and curated bde_es_cpi_m): %s", e)
        return n
    ine = ine.dropna()
    ratio = (ine / bde.reindex(ine.index)).dropna()
    f = float(ratio.mean())
    spread = float(ratio.max() / ratio.min() - 1)
    pre = (bde * f)[(bde.index >= pd.Timestamp(1961, 1, 1)) & (bde.index < ine.index.min())]
    linked = pd.concat([pre, ine]).sort_index()
    n += add_series(cw, "ine_ipc_index_linked_m", linked, positive=True,
                    name="Spain CPI (IPC), general index, linked 1961-present (base 2021=100)", category="inflation",
                    frequency="M", units="index (base 2021=100)", country="ES",
                    transform_notes=(f"SPLICE: 2002-01+ = INE Tempus IPC290751 (base 2021); 1961-01..2001-12 = bde_es_cpi_m (BdE series of the INE "
                                     f"linked index) x {f:.6f}. Over the {len(ratio)}-month overlap the INE/BdE ratio is constant (max/min-1 = "
                                     f"{spread:.1e}), i.e. bde_es_cpi_m is the INE linked index in another base, so the splice is exact "
                                     f"(rebasing only). The yoy computed from this index matches the official ine_ipc_yoy_m within rounding (<=0.1 pp) except Jan-Sep 2002 (up to 1.3 pp, base-change artefact of the 2001/2002 relinking): for 2002 yoy use ine_ipc_yoy_m."),
                    url=SERIE_URL.format(cod="IPC290751"))
    return n


def main() -> pd.DataFrame:
    cw = CatalogWriter(SOURCE, url="https://www.ine.es/dyngs/DataLab/manual.html?cid=45", license=LICENSE)
    for sid, cod, name, cat, freq, units, pos, notes in SEL:
        try:
            s, nombre = fetch(cod)
        except Exception as e:  # noqa: BLE001
            log.warning("%s (%s) failed: %s", sid, cod, e)
            continue
        n = add_series(cw, sid, s, positive=pos, name=name, category=cat, frequency=freq, units=units, country="ES",
                       transform_notes=f"INE Tempus series {cod}: {nombre.strip()} {notes}".strip(), url=SERIE_URL.format(cod=cod))
        log.info("%-30s %5d obs", sid, n)
    log.info("EPA 1976-2001 + linked: %d obs", epa_retro(cw))
    log.info("CPI extensions: %d obs", cpi_extensions(cw))
    return cw.close()


if __name__ == "__main__":
    main()
