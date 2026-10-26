"""Paper trading de la opción 3 (docs/factors/paper_trading.md): cada cierre de mes fija los pesos objetivo de B0
(estática 70/15/15) y B1 (ajuste por volatilidad) con datos EN VIVO. Separado de src/factors/ a propósito: el corte
técnico de desarrollo (≤ 2004) sigue intacto allí; aquí solo se leen los últimos 13 cierres de mes.

Cartera de referencia 70/15/15 (decisión del usuario del 26-oct, tomada DESPUÉS de ver la caída de −42 % de la 80/10/10
en desarrollo; declarado). B1: RV = 70 % × min(1, σ*/σ̂_t), acotada en [55 %, 70 %] (− 15 pp), umbral 2,5 pp.
- σ̂_t = volatilidad realizada de 12 rendimientos mensuales de la RV en EUR: S&P 500 (FRED `SP500`, precio) convertido
  con el EUR/USD del BCE, ambos a cierre de mes;
- σ* = 0,1702 CONGELADA, en la MISMA medida (precio y divisa a cierre de mes): mediana de σ̂ 1963-07 → 2004-12 con el
  mercado de EE. UU. de French (cierre de mes) y el fixing DEM/USD de Frankfurt (≤ 1998) / BCE (≥ 1999)
  (`scripts/paper_sigma_star.py`, `research/paper/sigma_star.json`). Antes 0,1548 (divisa media del BIS). Alternativa
  declarada, no usada: solo tipos flotantes 1973-2004 = 0,1872.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.warehouse import db

REPO = Path(__file__).resolve().parents[2]
LOG = REPO / "research" / "paper" / "decisiones.jsonl"
SIGMA_STAR = 0.1702
ESTRATEGICO = {"rv": 0.70, "rf": 0.15, "oro": 0.15}
RV_MIN, UMBRAL = 0.55, 0.025
MAX_DIAS_SIN_DATO = 5


@dataclass
class Decision:
    cierre: str
    sigma_hat: float
    rv_b1_bruta: float
    b0: dict
    b1: dict
    cambio_b1: bool
    datos: dict


def cierres(con, sid: str, hasta: pd.Timestamp, n: int = 14) -> pd.Series:
    df = con.execute("select date, value from obs_latest where series_id = ? and value is not null and date <= ? "
                     "order by date", [sid, hasta.date()]).df()
    s = pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["date"]))
    if s.empty or (hasta - s.index.max()).days > MAX_DIAS_SIN_DATO:
        raise RuntimeError(f"{sid}: sin dato reciente para el cierre {hasta.date()} (último {s.index.max() if len(s) else None})")
    return s.groupby(s.index.to_period("M")).last().iloc[-n:]


def rv_eur_mensual(sp: pd.Series, eurusd: pd.Series) -> pd.Series:
    """Rendimiento mensual en EUR de un activo en USD: (P_t / E_t) / (P_{t-1} / E_{t-1}) − 1 (E = USD por EUR)."""
    v = (sp / eurusd.reindex(sp.index)).dropna()
    return v.pct_change().dropna()


def rv_b1(sigma_hat: float, previo: float) -> tuple[float, float, bool]:
    bruta = float(np.clip(ESTRATEGICO["rv"] * min(1.0, SIGMA_STAR / sigma_hat), RV_MIN, ESTRATEGICO["rv"]))
    if abs(bruta - previo) >= UMBRAL - 1e-12:
        return bruta, bruta, True
    return bruta, previo, False


def ultimo_b1() -> float:
    if not LOG.exists():
        return ESTRATEGICO["rv"]
    lineas = [json.loads(x) for x in LOG.read_text().splitlines() if x.strip()]
    return float(lineas[-1]["b1"]["rv"]) if lineas else ESTRATEGICO["rv"]


def decidir(cierre: pd.Timestamp, con=None) -> Decision:
    propia = con is None
    con = con or db.connect(read_only=True)
    try:
        sp, fx = cierres(con, "SP500", cierre), cierres(con, "ecb_eurusd_d", cierre)
    finally:
        if propia:
            con.close()
    r = rv_eur_mensual(sp, fx).iloc[-12:]
    if len(r) < 12:
        raise RuntimeError(f"solo {len(r)} rendimientos mensuales para σ̂")
    sig = float(r.std(ddof=1) * np.sqrt(12))
    bruta, rv, cambio = rv_b1(sig, ultimo_b1())
    b1 = {"rv": round(rv, 4), "rf": round(1 - ESTRATEGICO["oro"] - rv, 4), "oro": ESTRATEGICO["oro"]}
    return Decision(str(cierre.date()), round(sig, 5), round(bruta, 4), dict(ESTRATEGICO), b1, cambio,
                    {"sp500_ultimo": str(sp.index[-1]), "eurusd_ultimo": str(fx.index[-1]),
                     "meses_sigma": [str(p) for p in r.index]})


def registrar(d: Decision, extra: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as fh:
        fh.write(json.dumps({**asdict(d), **extra}, ensure_ascii=False) + "\n")
