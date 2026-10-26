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


def connect():
    return db.connect(read_only=True)
