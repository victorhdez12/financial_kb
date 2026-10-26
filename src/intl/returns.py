"""Rentabilidad total mensual de bonos y letras por país a partir de tipos (INT-0, tarea 2).

Bono: bono a la par a 10 años con cupón = y_{t-1}; rentabilidad del mes ≈ y_{t-1}/12 − D·Δy + ½·C·Δy², con D y C la
duración modificada y la convexidad de un bono a la par de 10 años a tipo y_{t-1}. Letras: y3m_{t-1}/12.
Limitación declarada: los tipos de la OCDE son MEDIAS mensuales (no cierre), así que Δy está suavizado (efecto Working):
la volatilidad mensual del bono sale algo baja. En anual (lo que se contrasta con JST) el efecto es pequeño.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def duracion_convexidad(y: pd.Series | np.ndarray, n: int = 10, f: int = 2) -> tuple[np.ndarray, np.ndarray]:
    """Duración modificada y convexidad de un bono a la par (cupón = y) con n años y f pagos al año; y en fracción."""
    y = np.asarray(y, dtype=float)
    i = np.maximum(y / f, 1e-9)
    t = np.arange(1, n * f + 1)[:, None]
    cf = np.full((n * f, y.size), 1.0) * i[None, :]
    cf[-1] += 1.0
    df = (1 + i[None, :]) ** (-t)
    precio = (cf * df).sum(0)
    dmac = (t * cf * df).sum(0) / precio / f
    dmod = dmac / (1 + i)
    conv = (t * (t + 1) * cf * df).sum(0) / precio / (f ** 2) / (1 + i) ** 2
    return dmod, conv


def bono_tr_mensual(y_pct: pd.Series, n: int = 10) -> pd.Series:
    y = y_pct / 100
    d, c = duracion_convexidad(y.shift(1).to_numpy(), n)
    dy = y.diff()
    r = y.shift(1) / 12 - d * dy + 0.5 * c * dy ** 2
    return r.rename("bono_tr")


def letra_tr_mensual(y3m_pct: pd.Series) -> pd.Series:
    return (y3m_pct.shift(1) / 100 / 12).rename("letra_tr")
