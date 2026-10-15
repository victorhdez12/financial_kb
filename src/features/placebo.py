"""Walk-forward mínimo y placebo de fugas para la base point-in-time (docs/models/pit_base.md §5).

No es el arnés de backtest (entregable 3), pero el arnés debe reutilizar `placebo_check` sobre sus propias
predicciones: con la etiqueta barajada en bloques no puede haber habilidad, y una variable con fuga (información del
objetivo que en t aún no se conoce) tiene que hacer fallar el placebo. El test (c) comprueba las dos cosas.

Habilidad = log-loss del modelo solo con persistencia − log-loss del modelo con persistencia + variables, fuera de
muestra (walk-forward anual, ventana expansiva, embargo de 6 meses). > 0 = las variables aportan.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def fit_logit(X: np.ndarray, y: np.ndarray, k: int, lam: float = 1.0, per_obs: bool = True) -> np.ndarray:
    """Logística multinomial con L2. per_obs=True: penalización lam/n·‖W‖² (casi nula con n grande; la usa el test de
    señal plantada, calibrado así a priori por el Validador); per_obs=False: lam·‖W‖² (placebo)."""
    n, p = X.shape
    Xb = np.hstack([np.ones((n, 1)), X])
    Y = np.eye(k)[y]
    c = lam / n if per_obs else lam

    def f(w):
        W = w.reshape(p + 1, k)
        Z = Xb @ W
        Z -= Z.max(axis=1, keepdims=True)
        lse = np.log(np.exp(Z).sum(axis=1))
        ll = -(Y * (Z - lse[:, None])).sum() / n
        P = np.exp(Z - lse[:, None])
        g = Xb.T @ (P - Y) / n
        g[1:] += 2 * c * W[1:]
        return ll + c * (W[1:] ** 2).sum(), g.ravel()

    return minimize(f, np.zeros((p + 1) * k), jac=True, method="L-BFGS-B").x.reshape(p + 1, k)


def predict_logit(W: np.ndarray, X: np.ndarray) -> np.ndarray:
    Z = np.hstack([np.ones((len(X), 1)), X]) @ W
    Z -= Z.max(axis=1, keepdims=True)
    P = np.exp(Z)
    return P / P.sum(axis=1, keepdims=True)


def wf_skill(base: np.ndarray, feats: np.ndarray, y: np.ndarray, months: pd.DatetimeIndex, first_test_year: int,
             embargo: int = 6, k: int = 4, lam: float = 1.0, per_obs: bool = True) -> float:
    """Mejora media de log-loss (nats) de base + variables frente a solo base, fuera de muestra."""
    ll_b, ll_f = [], []
    for year in range(first_test_year, months.year.max() + 1):
        test = months.year == year
        train = months < pd.Timestamp(f"{year}-01-01") - pd.DateOffset(months=embargo)
        if train.sum() < 60 or test.sum() == 0:
            continue
        mu, sd = feats[train].mean(axis=0), feats[train].std(axis=0) + 1e-9
        Xf = np.hstack([base, (feats - mu) / sd])
        wb = fit_logit(base[train], y[train], k, lam, per_obs)
        wf = fit_logit(Xf[train], y[train], k, lam, per_obs)
        pb, pf = predict_logit(wb, base[test]), predict_logit(wf, Xf[test])
        i = np.arange(test.sum())
        ll_b += list(-np.log(np.clip(pb[i, y[test]], 1e-4, 1)))
        ll_f += list(-np.log(np.clip(pf[i, y[test]], 1e-4, 1)))
    return float(np.mean(ll_b) - np.mean(ll_f))


def persistence_onehot(y: np.ndarray, lag: int = 5, k: int = 4) -> np.ndarray:
    """Etiqueta de t − lag en one-hot (k − 1 columnas); las primeras `lag` filas a cero."""
    out = np.zeros((len(y), k - 1))
    for i in range(lag, len(y)):
        if y[i - lag] > 0:
            out[i, y[i - lag] - 1] = 1.0
    return out


def block_shuffle(y: np.ndarray, block: int, rng: np.random.Generator) -> np.ndarray:
    nb = int(np.ceil(len(y) / block))
    order = rng.permutation(nb)
    return np.concatenate([y[i * block:(i + 1) * block] for i in order])[:len(y)]


def placebo_skills(F: np.ndarray, y: np.ndarray, months: pd.DatetimeIndex, *, n_perm: int = 10, block: int = 24,
                   seed: int = 20261015, first_test_year: int = 1975, lam: float = 0.05, leak=None) -> np.ndarray:
    """Habilidad con la etiqueta barajada en bloques. `leak(y_barajada, rng) -> columnas` añade una variable con fuga
    construida desde el objetivo barajado (para comprobar que el placebo la detecta)."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n_perm):
        ys = block_shuffle(y, block, rng)
        Fx = F if leak is None else np.hstack([F, leak(ys, rng)])
        out.append(wf_skill(persistence_onehot(ys), Fx, ys, months, first_test_year, lam=lam, per_obs=False))
    return np.array(out)


PLACEBO_TOL = 0.02   # nats: por encima, el placebo falla (habilidad donde no puede haberla)


def placebo_check(skills: np.ndarray, tol: float = PLACEBO_TOL) -> bool:
    """True = pasa (sin habilidad con la etiqueta barajada)."""
    return bool(np.mean(skills) < tol)
