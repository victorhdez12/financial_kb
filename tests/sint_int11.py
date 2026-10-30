"""Panel SINTÉTICO para los tests de INT-11 (ningún dato real)."""
from __future__ import annotations

import numpy as np
import pandas as pd

EFECTO_EST = -0.15


def panel(n_paises=6, a0=1870, a1=2000, semilla=0, ar_bolsa=0.0, desfase_propio=None):
    rng = np.random.default_rng(semilla)
    filas = []
    paises = [f"P{i:02d}" for i in range(n_paises)]
    comun_inf = np.zeros(a1 - a0 + 1)
    for t in range(1, len(comun_inf)):
        comun_inf[t] = 0.85 * comun_inf[t - 1] + 0.012 * rng.standard_normal()
    comun_r = 0.10 * rng.standard_normal(len(comun_inf))
    for c in paises:
        infl = np.zeros(len(comun_inf))
        lg = np.zeros(len(comun_inf))
        lg[0] = 8.0
        g = 0.02
        for t in range(1, len(infl)):
            infl[t] = 0.03 + comun_inf[t] + 0.5 * (infl[t - 1] - 0.03) + 0.01 * rng.standard_normal()
            g = 0.02 + 0.5 * (g - 0.02) + 0.025 * rng.standard_normal()
            lg[t] = lg[t - 1] + g
        d = pd.DataFrame({"pais": c, "año": np.arange(a0, a1 + 1), "inflacion": infl, "rgdpmad": np.exp(lg)})
        filas.append(d)
    df = pd.concat(filas, ignore_index=True)
    from src.intl import escenarios as E
    df = E.estados_operables(df)
    prev = df.groupby("pais")["regimen"].shift(1)
    año_i = df["año"] - a0
    e = rng.standard_normal(len(df))
    bolsa = 0.06 + EFECTO_EST * (prev == 2) + comun_r[año_i] + 0.12 * e
    if desfase_propio:
        bolsa = bolsa + np.where(df["pais"] == paises[0], desfase_propio, 0.0)
    if ar_bolsa:
        bolsa = bolsa + ar_bolsa * df.groupby("pais")["inflacion"].shift(1).fillna(0) * 0  # sin efecto (marcador)
    df["bolsa"] = bolsa
    df["bonos"] = 0.02 - 0.06 * (prev.isin([1, 2])) + 0.06 * rng.standard_normal(len(df))
    df["letras"] = 0.01 - 0.04 * (prev.isin([1, 2])) + 0.02 * rng.standard_normal(len(df))
    df["vivienda"] = 0.05 + 0.08 * rng.standard_normal(len(df))
    df["oro"] = np.where(df["año"] >= 1972, 0.01 + 0.2 * rng.standard_normal(len(df)), np.nan)
    df["termo"] = rng.standard_normal(len(df))
    return df.drop(columns=["brecha", "regimen"])
