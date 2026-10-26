"""INT-4-ML: motor de la corrida única de P-DEV-INT4-ML v1.0 (docs/int/INT4ML_prerregistro_v0.md, congelado en e1f67a6).
Listón = logit de INT-4 (B1 + indicadores del giro, src/intl/int4.logit_fit). Candidatos fijados en el §2 (sin búsqueda):
  M-L2: LogisticRegression(penalty="l2", C=1, lbfgs) sobre B1 + indicadores + todas las interacciones de 2.º orden entre
        indicadores (sin cuadrados). Estandarización con media y desviación del pliegue de ajuste: primero las variables
        base; las interacciones se forman con los indicadores ya estandarizados y después se estandarizan también (con el
        mismo pliegue).
  M-GB: HistGradientBoostingClassifier(max_depth=2, max_iter=200, learning_rate=0.05, min_samples_leaf=20,
        l2_regularization=1.0, early_stopping=False, random_state=0), monotonía del §2 en los indicadores, B1 libre.
Concreciones (fijadas antes de correr): métrica principal AUC estratificada por país (scripts/int4_sensibilidad_liston.
auc_estrat); el signo temporal (criterio iv) se mide también con la AUC estratificada; p del placebo = 1 − Φ(z), z =
(ΔAUC − media placebos) / dt placebos, unilateral (mejora), con Holm-4; p por rangos informativa.
Versiones: scikit-learn 1.5.2 (instalada para esta corrida), numpy del .venv.
"""
from __future__ import annotations

import itertools

import numpy as np
from scipy.stats import norm
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from src.intl import int4 as M

MONOTONIA = {"T1": {"C1": -1, "C2": +1, "C4": +1, "C5": +1, "C6": -1},
             "T2": {"S1": +1, "S2": -1, "S3": +1, "S4": -1, "S5": -1}}
GB_PARAMS = dict(max_depth=2, max_iter=200, learning_rate=0.05, min_samples_leaf=20, l2_regularization=1.0,
                 early_stopping=False, random_state=0)


class Logit:
    """Listón: el logit de INT-4 (sin penalización)."""

    def fit(self, X, y):
        self.b = M.logit_fit(X, y)
        return self

    def predict(self, X):
        return M.logit_pred(self.b, X)


class L2Inter:
    def __init__(self, n_b1: int):
        self.n_b1 = n_b1

    def _diseño(self, X, fit: bool):
        if fit:
            self.mu, self.sd = X.mean(0), X.std(0)
            self.sd[self.sd == 0] = 1.0
        Z = (X - self.mu) / self.sd
        ind = Z[:, self.n_b1:]
        pares = list(itertools.combinations(range(ind.shape[1]), 2))
        inter = np.column_stack([ind[:, i] * ind[:, j] for i, j in pares]) if pares else np.empty((len(Z), 0))
        if fit:
            self.mi, self.si = inter.mean(0), inter.std(0)
            self.si[self.si == 0] = 1.0
        return np.column_stack([Z, (inter - self.mi) / self.si])

    def fit(self, X, y):
        self.m = LogisticRegression(penalty="l2", C=1.0, solver="lbfgs", max_iter=10000).fit(self._diseño(X, True), y)
        return self

    def predict(self, X):
        return self.m.predict_proba(self._diseño(X, False))[:, 1]


class GB:
    def __init__(self, cst: list[int]):
        self.cst = cst

    def fit(self, X, y):
        self.m = HistGradientBoostingClassifier(monotonic_cst=self.cst, **GB_PARAMS).fit(X, y)
        return self

    def predict(self, X):
        return self.m.predict_proba(X)[:, 1]


def fabrica(nombre: str, giro: str, n_b1: int, cols: list[str]):
    if nombre == "logit":
        return Logit
    if nombre == "M-L2":
        return lambda: L2Inter(n_b1)
    cst = [0] * n_b1 + [MONOTONIA[giro][c] for c in cols]
    return lambda: GB(cst)


def loco(fab, X, y, pais) -> np.ndarray:
    p = np.full(len(y), np.nan)
    for c in np.unique(pais):
        f = pais == c
        p[f] = fab().fit(X[~f], y[~f]).predict(X[f])
    return p


def temporal(fab, X, y, t, h: int = 1) -> np.ndarray:
    p = np.full(len(y), np.nan)
    for d in range(1950, 2001, 10):
        tr, te = t + h < d, (t >= d) & (t <= d + 9)
        if te.any() and tr.sum() > 20 and 0 < y[tr].sum() < tr.sum():
            p[te] = fab().fit(X[tr], y[tr]).predict(X[te])
    return p


def z_placebo(obs: float, ds: np.ndarray) -> dict:
    ds = ds[np.isfinite(ds)]
    mu, sd = float(ds.mean()), float(ds.std(ddof=1))
    z = (obs - mu) / sd if sd > 0 else np.nan
    return {"desplazamientos": int(len(ds)), "media": mu, "dt": sd, "z": z, "p_z": float(norm.sf(z)),
            "p_rangos": float((1 + (ds >= obs).sum()) / (1 + len(ds)))}
