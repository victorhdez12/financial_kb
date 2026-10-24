"""Interfaz de modelo del arnés y baselines (docs/models/harness.md §5).

Un modelo declara qué necesita y el arnés le da SOLO eso, ya filtrado (lista blanca, estados, ventana, embargo):

    class MiModelo(Model):                            # modelo de 4 cuadrantes
        name = "x"
        features = ("curve_10y3m", "unrate_sahm")     # () = sin variables; "principal" = todas las admitidas
        uses_persistence = True                       # añade pers_* y pers_hard_* (persistencia PIT) a X
        def fit(self, X, Y, y, info, sample_weight=None): ...
        def predict_proba(self, X, info): ...         # → n × 4, columnas en el orden de QUADS

    class MiModeloPorEje(AxisModel):                  # un modelo por eje (G, I), combinado como producto
        name = "y"
        axis_features = {"G": ("growth_rt", "baa_spread"), "I": ("core_cpi_6m_ann",)}   # nombres explícitos
        uses_persistence = True                       # añade pers_axis (P(eje alto) de la persistencia PIT)
        def fit_axis(self, axis, X, t, w, info): ...  # t: objetivo blando del eje (p_g_high / p_i_high recalculado)
        def predict_axis(self, axis, X, info): ...    # → n, P(eje alto)

    class MiNowcastG(ContinuousAxisModel):            # eje G CONTINUO (nowcast estructural); el I, como AxisModel
        continuous_axes = ("G",)
        def fit_axis_continuous(self, axis, X, g, t, w, info): ...   # g: valor continuo de G recalculado ≤ T
        def predict_axis_continuous(self, axis, X, info): ...        # → (media, desviación) de G, n y n
        # el arnés convierte: P(G alto) = Φ(media / √(desv² + s_G²)) (= E[p_g_high] si G ~ N(media, desv²)), lo combina
        # con el eje I en 4 cuadrantes y lo puntúa como a cualquier modelo (log-loss, giros, falsas alarmas, retraso);
        # además publica CRPS/RMSE de G (informativos, `report["g_continuo"]`)

`Y` = probabilidades blandas de la etiqueta RECALCULADA con datos ≤ T (n × 4); `y` = etiqueta dura recalculada;
`sample_weight` = peso de madurez de cada mes (harness.md §3b; 1 = maduro). `info` lleva el corte, la fecha de
decisión, el modo, los meses de entrenamiento y las variables. El modelo nunca ve la etiqueta oficial ni meses
posteriores al corte menos el embargo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from src.models.metrics import QUADS

PERS_COLS = [f"pers_{q}" for q in QUADS]
PERS_HARD_COLS = [f"pers_hard_{q}" for q in QUADS]      # persistencia en forma dura (one-hot de pers_hard)
PERS_AXIS = {"G": "pers_axis_growth", "I": "pers_axis_infl"}   # P(eje alto) de la persistencia PIT


class Model:
    name = "base"
    features: tuple[str, ...] | str = ()
    uses_persistence = False
    needs_training = True

    def fit(self, X: pd.DataFrame, Y: np.ndarray, y: np.ndarray, info: dict,
            sample_weight: np.ndarray | None = None) -> None:  # pragma: no cover
        raise NotImplementedError

    def predict_proba(self, X: pd.DataFrame, info: dict) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    def describe(self) -> dict:
        return {"name": self.name, "class": type(self).__name__, "features": self.features,
                "uses_persistence": self.uses_persistence, "params": getattr(self, "params", {})}


class AxisModel(Model):
    """Modelo por eje: el arnés entrena G e I por separado, cada uno con SUS variables y SU ventana (la del inicio más
    tardío de sus propias variables), y combina P(G)·P(I) en 4 cuadrantes (supuesto de independencia condicional:
    harness.md §5b)."""
    axis_features: dict[str, tuple[str, ...]] = {"G": (), "I": ()}

    def fit_axis(self, axis: str, X: pd.DataFrame, t: np.ndarray, w: np.ndarray, info: dict) -> None:  # pragma: no cover
        raise NotImplementedError

    def predict_axis(self, axis: str, X: pd.DataFrame, info: dict) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError


class ContinuousAxisModel(AxisModel):
    """Modelo por eje en el que los ejes de `continuous_axes` se prevén como un VALOR CONTINUO con su incertidumbre
    (p. ej. el nowcast estructural de G). El arnés le pasa el valor continuo del eje de la etiqueta recalculada con
    datos ≤ T (columna "G" o "I" de `PITLabeler.at`, mismos meses, embargo y pesos que el objetivo blando) y convierte
    la previsión gaussiana N(media, desv²) en P(eje alto) con `gaussian_axis_prob`, usando la escala de medida de la
    propia etiqueta (s_G = 0,40; para I, centro κ y s_I). Los ejes que no estén en `continuous_axes` siguen la
    interfaz de AxisModel (`fit_axis`/`predict_axis`)."""
    continuous_axes: tuple[str, ...] = ("G",)

    def fit_axis_continuous(self, axis: str, X: pd.DataFrame, g: np.ndarray, t: np.ndarray, w: np.ndarray,
                            info: dict) -> None:  # pragma: no cover
        raise NotImplementedError

    def predict_axis_continuous(self, axis: str, X: pd.DataFrame, info: dict) -> tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError  # pragma: no cover


class StackedAxisModel(AxisModel):
    """Modelo APILADO (arnés v2.4; pool_spec.md §6): el arnés corre antes, en el mismo corte y modo, los modelos de
    `components` (que tienen que estar en la corrida) y le pasa en `info["stack_preds"]` sus P(G alto) FUERA DE
    MUESTRA de todos los meses ≤ el corte (en `fit`) o ≤ el final del bloque (en `predict`), con el corte que produjo
    cada una (`<comp>@corte`)."""
    components: tuple[str, ...] = ()


def gaussian_axis_prob(mu, sd, s_label: float, center: float = 0.0) -> np.ndarray:
    """P(eje alto) de una previsión gaussiana del valor continuo del eje: la etiqueta define p_alto = Φ((X − c)/s)
    (ficha §5; s_G = 0,40, c = 0 para G); si X ~ N(mu, sd²), E[p_alto] = Φ((mu − c)/√(sd² + s²)). Es la previsión que
    minimiza la log-loss esperada frente al objetivo blando cuando la previsión de X es correcta."""
    from scipy.stats import norm
    mu, sd = np.asarray(mu, float), np.asarray(sd, float)
    return norm.cdf((mu - center) / np.sqrt(sd ** 2 + float(s_label) ** 2))


def gaussian_crps(mu, sd, y) -> np.ndarray:
    """CRPS de N(mu, sd²) frente a y (forma cerrada; Gneiting-Raftery 2007). Mismas unidades que G."""
    from scipy.stats import norm
    mu, sd, y = np.asarray(mu, float), np.asarray(sd, float), np.asarray(y, float)
    z = (y - mu) / sd
    return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))


class PersistencePIT(Model):
    """Persistencia cruda (referencia): la última etiqueta conocida en t (la de t − 5), recalculada con los datos
    publicados en t, en el mismo modo que las variables (ficha §12). No entrena."""
    name = "persistence_pit"
    uses_persistence = True
    needs_training = False

    def fit(self, X, Y, y, info, sample_weight=None):
        return None

    def predict_proba(self, X, info):
        return X[PERS_COLS].to_numpy(float)


class Climatology(Model):
    """Frecuencias marginales expansivas: media PONDERADA de las probabilidades blandas de la etiqueta de entrenamiento
    (recalculada con datos ≤ T) con un prior de Dirichlet uniforme (alpha por clase)."""
    name = "climatology"

    def __init__(self, alpha: float = 1.0):
        self.params = {"alpha": alpha}
        self.p_ = None

    def fit(self, X, Y, y, info, sample_weight=None):
        a = self.params["alpha"]
        w = np.ones(len(Y)) if sample_weight is None else np.asarray(sample_weight, float)
        self.p_ = (w @ np.asarray(Y, float) + a) / (w.sum() + a * len(QUADS))

    def predict_proba(self, X, info):
        return np.tile(self.p_, (len(X), 1))


def fit_binary_logit(Z: np.ndarray, t: np.ndarray, w: np.ndarray, l2: float) -> np.ndarray:
    """Logística binaria con objetivo BLANDO t ∈ [0, 1], pesos w y L2 = l2·‖β‖² (constante sin penalizar; escala de
    suma, no por observación). Devuelve [constante, β...]."""
    Z, t, w = np.asarray(Z, float), np.asarray(t, float), np.asarray(w, float)
    Xb = np.hstack([np.ones((len(Z), 1)), Z])

    def f(b):
        s = Xb @ b
        ls = np.logaddexp(0, s)                  # log(1 + e^s)
        loss = (w * (ls - t * s)).sum() + l2 * (b[1:] ** 2).sum()
        p = 1 / (1 + np.exp(-s))
        g = Xb.T @ (w * (p - t))
        g[1:] += 2 * l2 * b[1:]
        return loss, g

    return minimize(f, np.zeros(Xb.shape[1]), jac=True, method="L-BFGS-B").x


def logit(p: np.ndarray, eps: float) -> np.ndarray:
    p = np.clip(np.asarray(p, float), eps, 1 - eps)
    return np.log(p / (1 - p))


class CalibratedPersistence(AxisModel):
    """M0, persistencia CALIBRADA (listón principal; Estratega E1, decisión del usuario 2026-10-16). Por eje:
        P(eje alto) = Λ(a + b · logit(clip(pers_axis, eps)))
    con pers_axis = P(eje alto) de la persistencia PIT del mes, ajustada en cada corte del walk-forward con la etiqueta
    recalculada con datos ≤ T (objetivo blando p_g_high / p_i_high, pesos de madurez). Sin ninguna variable macro.
    Parámetros fijados A PRIORI (antes de correrlo): eps = 1e-3 (limita el apalancamiento de las probabilidades
    extremas de la persistencia), L2 = 1,0 sobre b (escala de suma; con ≥ 120 meses es casi nula)."""
    name = "m0_calibrated_persistence"
    uses_persistence = True
    axis_features = {"G": (), "I": ()}

    def __init__(self, eps: float = 1e-3, l2: float = 1.0):
        self.params = {"eps": eps, "l2": l2}
        self.coef_: dict[str, np.ndarray] = {}

    def _z(self, axis, X):
        return logit(X[PERS_AXIS[axis]].to_numpy(float), self.params["eps"])[:, None]

    def fit_axis(self, axis, X, t, w, info):
        self.coef_[axis] = fit_binary_logit(self._z(axis, X), t, w, self.params["l2"])

    def predict_axis(self, axis, X, info):
        b = self.coef_[axis]
        return 1 / (1 + np.exp(-(b[0] + self._z(axis, X)[:, 0] * b[1])))

    def coefficients(self) -> dict:
        return {f"{ax}_{k}": float(v[i]) for ax, v in self.coef_.items() for i, k in enumerate(("a", "b"))}


REGISTRY = {"persistence_pit": PersistencePIT, "climatology": Climatology,
            "m0_calibrated_persistence": CalibratedPersistence}


def make(name: str, **kw) -> Model:
    return REGISTRY[name](**kw)
