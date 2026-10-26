"""Corte técnico de la fase de factores: en desarrollo, ningún dato de mercado ≥ 2005-01 (plan de la fase, ajuste 2).

La caja fuerte (`src/models/vault.py`) solo protege la etiqueta. Los rendimientos de factores, las curvas del Tesoro y
el tipo de cambio son públicos, así que el corte se impone aquí:
- `load_dev` es la ÚNICA puerta de entrada de estas series en `src/factors/` (un test lo comprueba estáticamente);
- la consulta ya filtra `date <= DEV_END` en SQL, y después se comprueba la fecha máxima: si se cuela un dato
  ≥ 2005-01, `FactorCutoffError` (falla cerrado, nunca recorta en silencio);
- una serie que no esté en `FAMILIAS` también es un error: nada entra por omisión.
Las series diarias se cortan por fecha de observación; un dato de diciembre de 2004 publicado en enero de 2005 no
existe para estas fuentes (precios y rendimientos de mercado se conocen al cierre).
"""
from __future__ import annotations

import re

import pandas as pd

from src.warehouse import db

DEV_END = pd.Timestamp("2004-12-31")

# familias permitidas en la fase de factores (prefijo o id exacto) → qué son
FAMILIAS: dict[str, str] = {
    r"ff_(mkt_rf|smb|hml|mom|rf)_m": "Ken French EE. UU., mensual (1926-07 →)",
    r"ff5_(mkt_rf|smb|hml|rmw|cma|rf)_m": "Ken French 5 factores EE. UU., mensual (1963-07 →)",
    r"ff_ind10_\w+_m": "Ken French 10 industrias EE. UU., mensual",
    r"ffx_\w+_[md]": "Ken French internacional y diario EE. UU.",
    r"aqr_\w+_[md]": "AQR (QMJ, BAB, HML Devil, VME, TSMOM; sin redistribución)",
    r"jkp_\w+_[md]": "JKP (CC BY-NC: solo no comercial)",
    r"gsw_sveny\d\d": "Curva cupón cero del Tesoro (Gürkaynak-Sack-Wright), diaria (1961-06 →)",
    r"GS(1|2|5|10|30)|TB3MS": "Rendimientos del Tesoro de FRED, mensual",
    r"bis_xru_(de|xm)_eur_m": "BIS: marco alemán (EUR equivalente) y euro por USD, mensual",
    r"DEXUSEU|ecb_eurusd_d": "EUR/USD diario (1999-01 →)",
}
_RX = [re.compile(f"^(?:{p})$") for p in FAMILIAS]


class FactorCutoffError(RuntimeError):
    """Se ha pedido o colado un dato ≥ 2005-01, o una serie fuera de las familias de la fase."""


def permitida(sid: str) -> bool:
    return any(rx.match(sid) for rx in _RX)


def load_dev(con, sid: str) -> pd.Series:
    """Serie `sid` (última vintage) con fechas ≤ DEV_END. Error si no es de una familia permitida o si llega algo
    posterior (doble barrera: filtro SQL + comprobación)."""
    if not permitida(sid):
        raise FactorCutoffError(f"{sid}: no está en las familias de la fase de factores (src/factors/data.py)")
    df = con.execute("select date, value from obs_latest where series_id = ? and value is not null "
                     "and date <= ? order by date", [sid, DEV_END.date()]).df()
    s = pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["date"]), name=sid)
    s = s[~s.index.duplicated(keep="last")]
    check(s)
    return s


def check(x: pd.Series | pd.DataFrame) -> None:
    """Falla si `x` tiene alguna fecha posterior a DEV_END (para cualquier tabla derivada antes de usarla)."""
    if len(x) and pd.Timestamp(x.index.max()) > DEV_END:
        raise FactorCutoffError(f"dato posterior al corte: {pd.Timestamp(x.index.max()).date()} > {DEV_END.date()}")


def connect():
    return db.connect(read_only=True)
