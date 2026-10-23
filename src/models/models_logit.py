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
                 "core_cpi_6m_ann": +1, "headline_cpi_6m_ann": +1, "pers": +1,
                 # M1 v2 (docs/models/m1_v2_spec.md §2; base PIT v0.4)
                 "claims_4w_yoy": -1, "curve_min12": +1, "baa_gap10y": -1, "baa_d6m": -1, "sahm_d3m": -1}
WEAK_SIGN = ("curve_10y3m",)          # signo débil: se informa, no decide (Estratega)
L2_FEATURES = 6.0                     # fijada a priori (m1_spec.md §3): k / (2 τ²) con k = 12, τ = 1
L2_PERS = 1.0                         # la de M0
EPS = 1e-3                            # la de M0


def fit_binary_logit_pen(Z: np.ndarray, t: np.ndarray, w: np.ndarray, pen: np.ndarray,
                         offset: np.ndarray | None = None) -> np.ndarray:
    """Logística binaria con objetivo BLANDO t ∈ [0, 1], pesos w y L2 por coeficiente: Σ pen_j · β_j² (escala de
    suma; la constante no se penaliza). `offset` (M1 v2, eje I estructural): término FIJO del predictor lineal, no se
    estima. Devuelve [constante, β...]. Con pen constante y sin offset coincide con `base.fit_binary_logit`."""
    Z, t, w, pen = (np.asarray(a, float) for a in (Z, t, w, pen))
    Xb = np.hstack([np.ones((len(Z), 1)), Z])
    P_ = np.concatenate([[0.0], pen])
    off = None if offset is None else np.asarray(offset, float)

    def f(b):
        s = Xb @ b if off is None else Xb @ b + off
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


# ------------------------------------------------------------------ M1 v2 (H-M1-002, docs/models/m1_v2_spec.md)
# Especificación a priori, commiteada ANTES de correr nada con la etiqueta. Hipótesis nueva DECLARADA CONTAMINADA por
# los resultados de desarrollo de M1 v1 (revisión del Estratega de M1, §4-ii). Tres cambios, cada uno con mecanismo:
#   1. sin la Sahm en nivel; entra su Δ3m (`sahm_d3m`, signo −);
#   2. eje I ESTRUCTURAL: offset fijo 1,7 · (core_cpi_6m_ann − 2,9) / s, s = 0,75 pp (sensibilidades 0,5 y 1,0);
#      solo la constante y el logit de la persistencia del eje se estiman (como M0);
#   3. variables de riesgo de giro de la base PIT v0.4 en el eje G (sustituyen a `curve_10y3m` y `baa_spread` en nivel).
M2_G = ("growth_rt", "claims_4w_yoy", "curve_min12", "baa_gap10y", "baa_d6m", "eq_ret_6m", "sahm_d3m")
M2_I = ("core_cpi_6m_ann",)
I_SLOPE = 1.7          # probit → logit
I_CENTER = 2.9         # κ = 2,5 % en PCE subyacente ≈ 2,9 % en IPC subyacente (ficha de la etiqueta §4)
I_SCALE = 0.75         # pp: ruido de revisión del eje (s_I = 0,31) + meses que faltan de la ventana de la etiqueta


class LogitAxisV2(LogitAxis):
    """M1 v2: eje G = logística con el logit de la persistencia + variables (como M1 v1, L2 = 6); eje I con un OFFSET
    estructural de pendiente fija (`structural`): logit P(I alta) = c + b · logit(pers_i) + slope · (x − center) / scale.
    La variable del offset se declara en `axis_features` (el arnés le aplica la misma ventana, mínimos, dropna y
    cobertura), pero su coeficiente NO se estima."""

    def __init__(self, name: str = "m1v2_logit_axis", G: tuple = M2_G, I: tuple = M2_I, l2: float = L2_FEATURES,
                 l2_pers: float = L2_PERS, eps: float = EPS, i_structural: bool = True, i_slope: float = I_SLOPE,
                 i_center: float = I_CENTER, i_scale: float = I_SCALE):
        super().__init__(name=name, G=G, I=I, l2=l2, l2_pers=l2_pers, eps=eps)
        self.structural = {"I": (tuple(I)[0], i_slope, i_center, i_scale)} if i_structural else {}
        self.params.update({"i_structural": i_structural, "i_slope": i_slope, "i_center": i_center,
                            "i_scale": i_scale})

    def _free(self, axis) -> list:
        fixed = self.structural.get(axis, (None,))[0]
        return [f for f in self.axis_features[axis] if f != fixed]

    def _offset(self, axis, X):
        if axis not in self.structural:
            return None
        f, slope, center, scale = self.structural[axis]
        return slope * (X[f].to_numpy(float) - center) / scale

    def _design(self, axis, X):
        feats = self._free(axis)
        zp = B.logit(X[B.PERS_AXIS[axis]].to_numpy(float), self.params["eps"])[:, None]
        if not feats:
            return zp
        mu, sd = self._std[axis]
        return np.hstack([zp, (X[feats].to_numpy(float) - mu) / sd])

    def fit_axis(self, axis, X, t, w, info):
        feats = self._free(axis)
        if feats:
            F = X[feats].to_numpy(float)
            sd = F.std(axis=0)
            self._std[axis] = (F.mean(axis=0), np.where(sd > 0, sd, 1.0))
        pen = np.array([self.params["l2_pers"]] + [self.params["l2"]] * len(feats))
        b = fit_binary_logit_pen(self._design(axis, X), t, w, pen, offset=self._offset(axis, X))
        self.coef_[axis] = {"const": float(b[0]), "pers": float(b[1]), **{f: float(v) for f, v in zip(feats, b[2:])}}
        if axis in self.structural:
            f, slope, _, scale = self.structural[axis]
            self.coef_[axis][f] = slope / scale          # FIJO (no estimado): se publica para leerlo junto a los demás

    def predict_axis(self, axis, X, info):
        c = self.coef_[axis]
        b = np.array([c["const"], c["pers"], *[c[f] for f in self._free(axis)]])
        s = b[0] + self._design(axis, X) @ b[1:]
        off = self._offset(axis, X)
        return 1 / (1 + np.exp(-(s if off is None else s + off)))


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
    # M1 v2 (m1_v2_spec.md §2-§6). Las variantes de s son SENSIBILIDADES preregistradas: se publican, no eligen
    "m1v2_logit_axis": partial(LogitAxisV2, "m1v2_logit_axis"),                       # M1 v2 (principal)
    "m1v2_logit_axis_s050": partial(LogitAxisV2, "m1v2_logit_axis_s050", i_scale=0.5),
    "m1v2_logit_axis_s100": partial(LogitAxisV2, "m1v2_logit_axis_s100", i_scale=1.0),
    # eje G de M1 v2 con el eje I de M0 (sin variables): para la ventana larga (G elegible desde 1978-07)
    "m1v2_g": partial(LogitAxisV2, "m1v2_g", I=(), i_structural=False),
}
