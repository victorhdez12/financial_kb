"""Paper trading de la opción 3 (docs/factors/paper_trading.md): cada cierre de mes fija los pesos objetivo de B0
(estática 80/10/10) y B1 (ajuste por volatilidad) con datos EN VIVO. Separado de src/factors/ a propósito: el corte
técnico de desarrollo (≤ 2004) sigue intacto allí; aquí solo se leen los últimos 13 cierres de mes.

B1 en vivo (misma regla que P-DEV-FACT §4, con dos sustituciones declaradas):
- σ̂_t = volatilidad realizada de 12 rendimientos mensuales de la RV en EUR: S&P 500 (FRED `SP500`, precio) convertido
  con el EUR/USD diario del BCE al cierre de mes (en desarrollo: EE. UU. con dividendos y divisa media del BIS);
- σ* = 0,1548 CONGELADA (mediana expansiva de σ̂ 1963-07 → 2004-12, datos de desarrollo), en vez de la mediana
  expansiva hasta t: así no se lee la historia 2005-2025.
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
SIGMA_STAR = 0.1548
ESTRATEGICO = {"rv": 0.80, "rf": 0.10, "oro": 0.10}
RV_MIN, UMBRAL = 0.65, 0.025
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
