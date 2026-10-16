"""Interfaz de modelo del arnés y baselines mínimos (docs/models/harness.md §5).

Un modelo declara qué necesita y el arnés le da SOLO eso, ya filtrado (lista blanca, estados, épocas, embargo):

    class MiModelo(Model):
        name = "logit_v1"
        features = ("curve_10y3m", "unrate_sahm")   # () = sin variables; "principal" = todas las admitidas
        uses_persistence = True                      # añade pers_* (persistencia PIT de cada mes) a X
        def fit(self, X, Y, y, info): ...            # X: variables del entrenamiento; Y: probabilidades blandas
                                                     # (n × 4, etiqueta RECALCULADA con datos ≤ T); y: etiqueta dura
        def predict_proba(self, X, info): ...        # → n × 4, columnas en el orden de QUADS

`info` lleva el corte (`refit_month`, `decision_date`), el modo y los meses de entrenamiento. El modelo nunca ve la
etiqueta oficial ni meses posteriores al corte menos el embargo. Para enchufar logística, Markov, GBM o calibración
basta con una subclase registrada en `REGISTRY`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.metrics import QUADS

PERS_COLS = [f"pers_{q}" for q in QUADS]


class Model:
    name = "base"
    features: tuple[str, ...] | str = ()
    uses_persistence = False
    needs_training = True

    def fit(self, X: pd.DataFrame, Y: np.ndarray, y: np.ndarray, info: dict) -> None:  # pragma: no cover
        raise NotImplementedError

    def predict_proba(self, X: pd.DataFrame, info: dict) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    def describe(self) -> dict:
        return {"name": self.name, "class": type(self).__name__, "features": self.features,
                "uses_persistence": self.uses_persistence, "params": getattr(self, "params", {})}


class PersistencePIT(Model):
    """Listón: la última etiqueta conocida en t (la de t − 5), recalculada con los datos publicados en t, en el mismo
    modo que las variables (ficha §12). No entrena."""
    name = "persistence_pit"
    uses_persistence = True
    needs_training = False

    def fit(self, X, Y, y, info):
        return None

    def predict_proba(self, X, info):
        return X[PERS_COLS].to_numpy(float)


class Climatology(Model):
    """Frecuencias marginales expansivas: media de las probabilidades blandas de la etiqueta de entrenamiento
    (recalculada con datos ≤ T) con un prior de Dirichlet uniforme (alpha por clase)."""
    name = "climatology"

    def __init__(self, alpha: float = 1.0):
        self.params = {"alpha": alpha}
        self.p_ = None

    def fit(self, X, Y, y, info):
        a = self.params["alpha"]
        self.p_ = (np.asarray(Y, float).sum(axis=0) + a) / (len(Y) + a * len(QUADS))

    def predict_proba(self, X, info):
        return np.tile(self.p_, (len(X), 1))


REGISTRY = {"persistence_pit": PersistencePIT, "climatology": Climatology}


def make(name: str, **kw) -> Model:
    return REGISTRY[name](**kw)
