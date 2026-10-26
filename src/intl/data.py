"""Corte técnico del panel internacional (INT-0): en desarrollo, ningún dato con fecha ≥ 2005-01, para ningún país.
Mismo límite y misma comprobación que src/factors/data.py (DEV_END, check). `load_dev` es la única entrada de datos del
warehouse en src/intl/ (un test lo comprueba) y falla cerrado con series fuera de las familias permitidas.
"""
from __future__ import annotations

import re

import pandas as pd

from src.factors.data import DEV_END, FactorCutoffError, check  # noqa: F401  (mismo corte para todo el proyecto)
from src.warehouse import db

PAISES = ["AUS", "BEL", "CAN", "CHE", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "IRL", "ITA", "JPN", "NLD", "NOR", "PRT",
          "SWE", "USA"]
ISO2 = {"AUS": "au", "BEL": "be", "CAN": "ca", "CHE": "ch", "DEU": "de", "DNK": "dk", "ESP": "es", "FIN": "fi", "FRA": "fr",
        "GBR": "gb", "IRL": "ie", "ITA": "it", "JPN": "jp", "NLD": "nl", "NOR": "no", "PRT": "pt", "SWE": "se", "USA": "us"}

FAMILIAS: dict[str, str] = {
    r"jst_[a-z]{3}_\w+": "JST Macrohistory R6 (anual, revisado, CC BY-NC-SA)",
    r"oecd_(ip|retail|unemp|irlt|ir3m|ircall|share|cli|bci|cci)_[a-z]{3}": "OCDE mensual (CC BY 4.0)",
    r"oecd_(cpi|cpicore)_[a-z]{3}_(idx|yoy)": "OCDE IPC mensual (CC BY 4.0)",
    r"bis_cbpol_[a-z]{2}": "BIS tipo oficial mensual",
    r"imf_ifs_[a-z]{3}_\w+": "FMI IFS mensual",
    r"aqr_mkt_[a-z]{3}_m": "AQR mercado por país, mensual, USD (sin redistribución)",
    r"USREC": "NBER: recesiones de EE. UU. (solo como contraste externo del fechado, nunca como variable)",
    # INT-3b/INT-3c (docs/int/INT3b_prerregistro_v0.md): activos y componentes de precio mundial o de EE. UU./R. U.
    r"aqr_clr_\w+_m": "AQR Commodities for the Long Run, mensual 1877- (sin redistribución; curado, ver load_dev_curado)",
    r"aqr_cfp_commodities_market_m": "AQR Century of Factor Premia, materias primas largo, mensual 1926- (sin redistribución)",
    r"damodaran_(baa_corp_tr|tbond_10y_tr|tbill_3m|gold_ret|inflation)": "Damodaran histretSP, anual 1928-",
    r"gold_mw_newyork_usd_a|gold_wb_usd_m": "Oro en USD: MeasuringWorth (media anual) y Banco Mundial (media mensual)",
    r"boe_uk_(corp_bond_yield_a|consol_yield_a|oil_price_usd_a|cpi_a)": "BoE A Millennium of Macroeconomic Data (UK), anual",
    r"BAA|AAA|GS10": "FRED: Moody's Baa/Aaa y Tesoro 10 años, mensual",
}
_RX = [re.compile(f"^(?:{p})$") for p in FAMILIAS]


def permitida(sid: str) -> bool:
    return any(rx.match(sid) for rx in _RX)


def load_dev(con, sid: str) -> pd.Series:
    """Serie `sid` con fechas ≤ DEV_END; vacía si no existe. Error si no es de una familia permitida o si se cuela algo
    posterior (filtro SQL + comprobación)."""
    if not permitida(sid):
        raise FactorCutoffError(f"{sid}: no está en las familias del panel internacional (src/intl/data.py)")
    df = con.execute("select date, value from obs_latest where series_id = ? and value is not null and date <= ? "
                     "order by date", [sid, DEV_END.date()]).df()
    s = pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["date"]), name=sid)
    if s.index.duplicated().any():
        raise FactorCutoffError(f"{sid}: fechas repetidas en obs_latest (no se elige una en silencio)")
    check(s)
    return s


def load_dev_curado(sid: str) -> pd.Series:
    """Como `load_dev`, pero desde la capa curada ($FIN_DATA_ROOT/curated/<fuente>/<sid>.parquet) para series ya
    descargadas que todavía no están en el warehouse (se cargarán en la próxima reconstrucción). Mismo corte y mismas
    familias permitidas."""
    if not permitida(sid):
        raise FactorCutoffError(f"{sid}: no está en las familias del panel internacional (src/intl/data.py)")
    fuente = "aqr_clr" if sid.startswith("aqr_clr_") else None
    if fuente is None:
        raise FactorCutoffError(f"{sid}: sin carpeta curada conocida; usa load_dev")
    df = pd.read_parquet(db.DATA_ROOT / "curated" / fuente / f"{sid}.parquet")
    df = df[pd.to_datetime(df["date"]) <= DEV_END]
    s = pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["date"]), name=sid).sort_index()
    if s.index.duplicated().any():
        raise FactorCutoffError(f"{sid}: fechas repetidas en la capa curada")
    check(s)
    return s


def connect():
    return db.connect(read_only=True)
