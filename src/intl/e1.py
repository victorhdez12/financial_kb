"""P-E1 (docs/int/E1_prerregistro_v1.md, congelado v1.0): logit de CURVA (L) frente a CURVA + ACTIVIDAD (A) para la
entrada en recesión a 12 meses. Funciones puras: ajuste congelado, predicción, evaluación (ΔAUC, Δlog-loss, placebo P1
de desplazamiento circular, P2 países permutados, P3 actividad retrasada 24 m, M4 anticipación pura).
Los datos entran ya construidos por `src/intl/int13.construir` (misma tabla larga que INT-13)."""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from src.intl import int4 as M4

OBJ = "E1_12"
Y = f"y_{OBJ}"
COLS = {"L": ["curva", "d12_corto"], "A": ["curva", "d12_corto", "ip_yoy", "confianza_emp"]}
ACTIVIDAD = ["ip_yoy", "confianza_emp"]
SIGNOS = {"curva": -1, "d12_corto": 1, "ip_yoy": -1, "confianza_emp": -1}
ESPERADO_DEV = (3306, 240)            # filas / eventos de E1-12 con las 4 columnas en INT-13 (P5)
SIN_2020 = (pd.Timestamp("2019-01-31"), pd.Timestamp("2021-06-30"))


def filas(df: pd.DataFrame) -> pd.DataFrame:
    """Casos completos: objetivo + las 4 columnas (mismas filas para L y A)."""
    ok = df[Y].notna() & df[COLS["A"]].notna().all(axis=1)
    return df[ok].reset_index(drop=True)


def ajustar(d: pd.DataFrame) -> dict:
    y = d[Y].to_numpy(float)
    out = {}
    for m, cols in COLS.items():
        X = d[cols].to_numpy(float)
        mu, sd = X.mean(0), X.std(0, ddof=0)
        b = M4.logit_fit((X - mu) / sd, y)
        out[m] = {"cols": cols, "media": mu.tolist(), "dt": sd.tolist(), "b": b.tolist()}
    return out


def signos_ok(mod: dict) -> dict:
    a = mod["A"]
    return {c: bool(np.sign(a["b"][1 + i]) == SIGNOS[c]) for i, c in enumerate(a["cols"])}


def sha(mod: dict) -> str:
    return hashlib.sha256(json.dumps(mod, sort_keys=True).encode()).hexdigest()


def predecir(mod: dict, d: pd.DataFrame, m: str) -> np.ndarray:
    p = mod[m]
    X = (d[p["cols"]].to_numpy(float) - np.array(p["media"])) / np.array(p["dt"])
    return M4.logit_pred(np.array(p["b"]), X)


def _delta(mod, d) -> dict:
    y = d[Y].to_numpy(float)
    pa, pl = predecir(mod, d, "A"), predecir(mod, d, "L")
    return {"dauc": M4.auc(y, pa) - M4.auc(y, pl), "dlogloss": M4.logloss(y, pa) - M4.logloss(y, pl),
            "dbrier": M4.brier(y, pa) - M4.brier(y, pl), "auc_A": M4.auc(y, pa), "auc_L": M4.auc(y, pl),
            "calib_A": M4.calibracion(y, pa), "n": int(len(y)), "eventos": int(y.sum())}


def _mover_actividad(df: pd.DataFrame, f) -> pd.DataFrame:
    """Aplica f a cada panel ancho (fecha × país) de las columnas de actividad."""
    out = df.copy()
    for c in ACTIVIDAD:
        w = df.pivot(index="fecha", columns="pais", values=c)
        w2 = f(w).rename_axis(index="fecha", columns="pais").stack(future_stack=True).rename(c)
        out = out.drop(columns=c).merge(w2.reset_index(), on=["fecha", "pais"], how="left")
    return out


def p1_circular(mod, df: pd.DataFrame) -> dict:
    """Placebo P1: desplazamiento circular k ∈ [24, T − 24] de la actividad (misma k para todos los países)."""
    fechas = np.sort(df.fecha.unique())
    T = len(fechas)
    obs = _delta(mod, filas(df))["dauc"]
    nulos = []
    for k in range(24, T - 23):
        g = lambda w: pd.DataFrame(np.roll(w.reindex(fechas).to_numpy(), k, axis=0), index=fechas,  # noqa: E731
                                   columns=w.columns)
        d = filas(_mover_actividad(df, g))
        if d[Y].sum() > 0 and d[Y].sum() < len(d):
            nulos.append(_delta(mod, d)["dauc"])
    nulos = np.array(nulos)
    return {"dauc_obs": obs, "k": int(len(nulos)), "p": float((1 + (nulos >= obs).sum()) / (1 + len(nulos)))}


def p2_paises(mod, df) -> float:
    paises = sorted(df.pais.unique())
    rot = dict(zip(paises, paises[1:] + paises[:1]))
    g = lambda w: w.rename(columns={v: k for k, v in rot.items()})  # noqa: E731  (cada país recibe la del siguiente)
    return _delta(mod, filas(_mover_actividad(df, g)))["dauc"]


def p3_retraso(mod, df) -> float:
    return _delta(mod, filas(_mover_actividad(df, lambda w: w.shift(24))))["dauc"]


def m4_anticipacion(mod, df, entrada_6m: pd.Series) -> dict:
    """Quita las filas con entrada en (M, M + 6] (y = 1 solo si la entrada cae en (M + 6, M + 12])."""
    d = filas(df.assign(_e6=entrada_6m.values))
    return _delta(mod, d[d._e6 != 1])


def evaluar(mod, df: pd.DataFrame, sin_2020: bool = True) -> dict:
    """Principal (§5) y secundarios sobre la muestra de evaluación `df` (ya "as of", objetivo cerrado)."""
    base = df
    if sin_2020:
        base = df[~df.fecha.between(*SIN_2020)]
    out = {"principal": _delta(mod, filas(base)), "p1": p1_circular(mod, base), "p2_dauc": p2_paises(mod, base),
           "p3_dauc": p3_retraso(mod, base)}
    if "y_E1_6" in base:
        out["m4"] = m4_anticipacion(mod, base, base["y_E1_6"])
    return out
