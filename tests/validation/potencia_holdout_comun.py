"""Piezas comunes del estudio de potencia de P-EVAL-BASE v4 (solo sintético; no lee datos ni la etiqueta).

- Réplica EXACTA y vectorizada de `metrics.boot_mean`: el arnés usa la misma semilla (20261015) para los índices del
  bootstrap circular por bloques, así que, para una longitud n dada, la matriz de índices es siempre la misma. La media
  de cada réplica es entonces C·x/n, con C la matriz de recuentos (n_rep × n) de esos índices. Se comprueba contra
  `metrics.boot_mean` en `check_boot_replica`.
- Contrastes alternativos: Diebold-Mariano con HAC de Newey-West (Bartlett) y corrección de Harvey-Leybourne-Newbold,
  y HAC EWC (coseno de pesos iguales, Lazarus-Lewis-Stock-Watson 2018) con valores críticos t_ν.
- Criterios de A3 de P-EVAL-BASE v4 que se pueden calcular solo con d_t, la marca de giro y los subperiodos.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.models import metrics as M


def boot_counts(n: int, block: int = 12, n_rep: int = M.BOOT["n"], seed: int = M.BOOT["seed"]) -> np.ndarray:
    idx = M.block_indices(n, block, n_rep, seed)
    C = np.zeros((n_rep, n))
    np.add.at(C, (np.repeat(np.arange(n_rep), n), idx.ravel()), 1.0)
    return C


def boot_stats(X: np.ndarray, C: np.ndarray, level: float = 0.95) -> dict:
    """Para cada fila de X (réplica × meses): media, IC percentil bilateral `level`, límite inferior unilateral del
    mismo nivel (percentil 1 − level) y `p_h0` exactamente como `metrics.boot_mean`."""
    n = X.shape[1]
    m = X @ C.T / n
    xb = X.mean(axis=1)
    a = (1 - level) / 2
    lo, hi = np.quantile(m, [a, 1 - a], axis=1)
    lo1 = np.quantile(m, 1 - level, axis=1)
    p = ((m - xb[:, None]) >= xb[:, None]).mean(axis=1)
    return {"mean": xb, "lo": lo, "hi": hi, "lo_uni": lo1, "p_h0": p}


def check_boot_replica(n: int = 202, block: int = 12, seed: int = 0) -> float:
    """Diferencia máxima entre esta réplica y `metrics.boot_mean` en 5 series al azar (debe ser ~1e-15)."""
    rng = np.random.default_rng(seed)
    X = rng.standard_t(4, size=(5, n)) * 0.3
    C = boot_counts(n, block)
    b = boot_stats(X, C)
    err = 0.0
    boot = {**M.BOOT, "block": block}
    for i in range(5):
        r = M.boot_mean(X[i], boot)
        err = max(err, abs(r["lo"] - b["lo"][i]), abs(r["hi"] - b["hi"][i]), abs(r["p_h0"] - b["p_h0"][i]))
    return err


def _autocov(X: np.ndarray, L: int) -> np.ndarray:
    Xc = X - X.mean(axis=1, keepdims=True)
    n = X.shape[1]
    return np.stack([(Xc[:, k:] * Xc[:, :n - k]).sum(axis=1) / n for k in range(L + 1)], axis=1)


def dm_nw(X: np.ndarray, lag: int = 12) -> np.ndarray:
    """p unilateral (H1: media > 0) del Diebold-Mariano con HAC Newey-West (Bartlett, `lag`) y la corrección de
    Harvey-Leybourne-Newbold (1997) con h = lag + 1, comparado con t_{n−1}."""
    n = X.shape[1]
    g = _autocov(X, lag)
    w = 1 - np.arange(1, lag + 1) / (lag + 1)
    lrv = g[:, 0] + 2 * (g[:, 1:] * w).sum(axis=1)
    lrv = np.maximum(lrv, 1e-12)
    t = X.mean(axis=1) / np.sqrt(lrv / n)
    h = lag + 1
    t *= np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    return stats.t.sf(t, n - 1)


def ewc(X: np.ndarray, nu: int | None = None) -> np.ndarray:
    """p unilateral del contraste de la media con HAC EWC (Lazarus, Lewis, Stock y Watson 2018): ν = ⌊0,4·n^{2/3}⌋
    proyecciones coseno, estadístico t con ν grados de libertad (valores críticos de rango fijo)."""
    n = X.shape[1]
    nu = nu or int(np.floor(0.4 * n ** (2 / 3)))
    s = (np.arange(1, n + 1) - 0.5) / n
    Phi = np.sqrt(2 / n) * np.cos(np.pi * np.outer(np.arange(1, nu + 1), s))     # ν × n
    Xc = X - X.mean(axis=1, keepdims=True)
    lam = Xc @ Phi.T                                                              # R × ν
    lrv = np.maximum((lam ** 2).mean(axis=1), 1e-12)
    t = X.mean(axis=1) / np.sqrt(lrv / n)
    return stats.t.sf(t, nu)


def secondary(X: np.ndarray, giro: np.ndarray, split: int) -> dict:
    """Criterios 2, 3, 4 y 6 de A3 (2: eje G > 0; con el eje I = M0, d del eje G = d de 4 cuadrantes)."""
    gm = np.where(giro, X, np.nan)
    sm = np.where(~giro, X, np.nan)
    with np.errstate(invalid="ignore"):
        c3 = np.nanmean(gm, axis=1) >= 0
        c4 = np.nanmean(sm, axis=1) >= -0.05
    c3 = np.where(giro.any(axis=1), c3, False)
    s1, s2 = X[:, :split].mean(axis=1), X[:, split:].mean(axis=1)
    c6 = np.sign(s1) == np.sign(s2)
    return {"c2": X.mean(axis=1) > 0, "c3": c3, "c4": c4, "c6": c6}
