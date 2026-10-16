"""M1: logística binaria por eje con variables de la lista blanca principal (Fase 3, entregable 4).

Especificación congelada A PRIORI en `docs/models/m1_spec.md` y `config/harness/m1_logit_axis_v1.yaml`
(hipótesis H-M1-001 en `research/hypotheses.yaml`), escrita y commiteada ANTES de correr nada con la etiqueta.

Por eje a ∈ {G, I} y en cada corte del walk-forward:

    P(eje alto) = Λ(c + b · logit(clip(pers_axis, eps)) + Σ_j β_j · (x_j − μ_j) / σ_j)

- `pers_axis` = P(eje alto) de la persistencia PIT (la misma entrada que M0, `base.CalibratedPersistence`);
- x_j = variables del eje (nombres explícitos de la matriz PIT v0.3), estandarizadas con la media y la desviación
  de las filas de entrenamiento del corte (ventana expansiva → estandarización expansiva);
- objetivo blando del eje (p_g_high / p_i_high de la etiqueta recalculada con datos ≤ T) y pesos de madurez;
- L2 (escala de suma) = `l2_pers` · b² + `l2` · Σ β_j²; la constante c no se penaliza.
  Con l2_pers = 1,0 y eps = 1e-3 (los de M0), M1 anida exactamente a M0 cuando β = 0: M1 − M0 = valor de las variables.
"""
from __future__ import annotations

from functools import partial

import numpy as np
from scipy.optimize import minimize

from src.models import base as B

M1_G = ("growth_rt", "unrate_sahm", "baa_spread", "eq_ret_6m", "curve_10y3m")
M1_I_CORE = ("core_cpi_6m_ann",)
M1_I_HEADLINE = ("headline_cpi_6m_ann",)
EXPECTED_SIGN = {"growth_rt": +1, "unrate_sahm": -1, "baa_spread": -1, "eq_ret_6m": +1, "curve_10y3m": +1,
                 "core_cpi_6m_ann": +1, "headline_cpi_6m_ann": +1, "pers": +1}
WEAK_SIGN = ("curve_10y3m",)          # signo débil: se informa, no decide (Estratega)
L2_FEATURES = 6.0                     # fijada a priori (m1_spec.md §3): k / (2 τ²) con k = 12, τ = 1
L2_PERS = 1.0                         # la de M0
EPS = 1e-3                            # la de M0


def fit_binary_logit_pen(Z: np.ndarray, t: np.ndarray, w: np.ndarray, pen: np.ndarray) -> np.ndarray:
    """Logística binaria con objetivo BLANDO t ∈ [0, 1], pesos w y L2 por coeficiente: Σ pen_j · β_j² (escala de
    suma; la constante no se penaliza). Devuelve [constante, β...]. Con pen constante coincide con
    `base.fit_binary_logit`."""
    Z, t, w, pen = (np.asarray(a, float) for a in (Z, t, w, pen))
    Xb = np.hstack([np.ones((len(Z), 1)), Z])
    P_ = np.concatenate([[0.0], pen])

    def f(b):
        s = Xb @ b
        loss = (w * (np.logaddexp(0, s) - t * s)).sum() + (P_ * b ** 2).sum()
        p = 1 / (1 + np.exp(-s))
        return loss, Xb.T @ (w * (p - t)) + 2 * P_ * b

    return minimize(f, np.zeros(Xb.shape[1]), jac=True, method="L-BFGS-B").x


class LogitAxis(B.AxisModel):
    """M1 (y sus variantes preregistradas): logística por eje = logit de la persistencia del eje + variables."""
    uses_persistence = True

    def __init__(self, name: str = "m1_logit_axis", G: tuple = M1_G, I: tuple = M1_I_CORE,
                 l2: float = L2_FEATURES, l2_pers: float = L2_PERS, eps: float = EPS):
        self.name = name
        self.axis_features = {"G": tuple(G), "I": tuple(I)}
        self.params = {"l2": l2, "l2_pers": l2_pers, "eps": eps, "G": list(G), "I": list(I)}
        self.coef_: dict[str, dict] = {}
        self._std: dict[str, tuple] = {}

    def _design(self, axis, X):
        feats = list(self.axis_features[axis])
        zp = B.logit(X[B.PERS_AXIS[axis]].to_numpy(float), self.params["eps"])[:, None]
        if not feats:
            return zp
        mu, sd = self._std[axis]
        return np.hstack([zp, (X[feats].to_numpy(float) - mu) / sd])

    def fit_axis(self, axis, X, t, w, info):
        feats = list(self.axis_features[axis])
        if feats:
            F = X[feats].to_numpy(float)
            sd = F.std(axis=0)
            self._std[axis] = (F.mean(axis=0), np.where(sd > 0, sd, 1.0))
        pen = np.array([self.params["l2_pers"]] + [self.params["l2"]] * len(feats))
        b = fit_binary_logit_pen(self._design(axis, X), t, w, pen)
        self.coef_[axis] = {"const": float(b[0]), "pers": float(b[1]),
                            **{f: float(v) for f, v in zip(feats, b[2:])}}

    def predict_axis(self, axis, X, info):
        c = self.coef_[axis]
        b = np.array([c["const"], c["pers"], *[c[f] for f in self.axis_features[axis]]])
        s = b[0] + self._design(axis, X) @ b[1:]
        return 1 / (1 + np.exp(-s))

    def coefficients(self) -> dict:
        return {f"{ax}_{k}": v for ax, d in self.coef_.items() for k, v in d.items()}


def _m1(name, I, **kw):
    return LogitAxis(name=name, I=I, **kw)


# Nombres preregistrados (m1_spec.md §2 y §6). Las variantes de L2 son SENSIBILIDADES: se publican, no eligen.
REGISTRY = {
    "m1_logit_axis": partial(_m1, "m1_logit_axis", M1_I_CORE),                  # M1 (principal; P-EVAL-BASE)
    "m1_logit_axis_hl": partial(_m1, "m1_logit_axis_hl", M1_I_HEADLINE),        # época previa al subyacente
    "m1_logit_axis_l2lo": partial(_m1, "m1_logit_axis_l2lo", M1_I_CORE),        # sensibilidad L2 (l2 en la config)
    "m1_logit_axis_l2hi": partial(_m1, "m1_logit_axis_l2hi", M1_I_CORE),
    "m1_logit_axis_hl_l2lo": partial(_m1, "m1_logit_axis_hl_l2lo", M1_I_HEADLINE),
    "m1_logit_axis_hl_l2hi": partial(_m1, "m1_logit_axis_hl_l2hi", M1_I_HEADLINE),
}
