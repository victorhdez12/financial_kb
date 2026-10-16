"""Modelos SONDA para el ensayo en seco de un preregistro (docs/models/harness.md §4e). NO son aspirantes.

`AxisWindowProbe` declara por eje las MISMAS variables que el modelo que sustituye (así el arnés le aplica las mismas
ventanas, mínimos de entrenamiento, `dropna`, cobertura y diagnósticos), pero **no usa ninguna variable macro**: por
eje ajusta la persistencia calibrada (como M0) y devuelve coeficiente 0 para cada variable declarada. Sirve para
demostrar que una configuración de evaluación es ejecutable de principio a fin sin entrenar nada con variables reales.
"""
from __future__ import annotations

import numpy as np

from src.models import base as B


class AxisWindowProbe(B.AxisModel):
    name = "axis_window_probe"
    uses_persistence = True

    def __init__(self, axis_features: dict | None = None, eps: float = 1e-3, l2: float = 1.0):
        self.axis_features = {ax: tuple((axis_features or {}).get(ax, ())) for ax in ("G", "I")}
        self.params = {"axis_features": self.axis_features, "eps": eps, "l2": l2}
        self.coef_: dict[str, np.ndarray] = {}

    def _z(self, axis, X):
        return B.logit(X[B.PERS_AXIS[axis]].to_numpy(float), self.params["eps"])[:, None]

    def fit_axis(self, axis, X, t, w, info):
        self.coef_[axis] = B.fit_binary_logit(self._z(axis, X), t, w, self.params["l2"])

    def predict_axis(self, axis, X, info):
        b = self.coef_[axis]
        return 1 / (1 + np.exp(-(b[0] + self._z(axis, X)[:, 0] * b[1])))

    def coefficients(self) -> dict:
        """Convención de claves del arnés para los signos (M2-4): "<eje>:<variable>" y "<eje>:pers"."""
        out = {}
        for ax, b in self.coef_.items():
            out[f"{ax}:pers"] = float(b[1])
            out.update({f"{ax}:{c}": 0.0 for c in self.axis_features[ax]})
        return out


B.REGISTRY.setdefault(AxisWindowProbe.name, AxisWindowProbe)
