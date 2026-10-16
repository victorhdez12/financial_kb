"""Clasificador de reglas de la Fase 1 como `Model` del arnés (Fase 3, entregable 4; secundario, fuera del criterio de
éxito). Traducción a la matriz PIT v0.3 CONGELADA antes de correrlo (`docs/models/m1_spec.md` §4).

Reglas (de `src/regime/classify.py`, sin tocar umbrales; traducción del Estratega, revisión del arnés §3e):
- G alto ("up") ⇔ growth_rt(t) > 0  y  growth_rt(t) − growth_rt(t−6) > 0  y  unrate_sahm(t) < 0,5.
  (`classify.growth`: G compuesto > 0 y ΔG(6m) > 0 y Sahm < 0,5; `growth_rt` es el análogo PIT de G de la v0.3.)
  Si el modelo no tiene la fila de t−6 (solo en los ≤ 5 primeros meses tras su primer corte elegible), la condición
  de Δ6m se omite (signo de growth_rt y Sahm).
- I alta ("up"): la histéresis de `classify.inflation_state` (≥ 2,5 % y acelerando → up; < 2,0 % o desacelerando
  > 0,5 pp → down; si no, mantiene), con aceleración = x(t) − x(t−3) (`classify.inflation`; NaN → 0) sobre
  x = `core_cpi_6m_ann` cuando el arnés lo admite (época del subyacente: 120 meses desde 1978-01) y
  `headline_cpi_6m_ann` antes. Se llama a la función congelada `inflation_state`, no a una copia.
- Calibración: tabla 4 × 4 dentro del walk-forward. Estado de las reglas (G up/down × I up/down) → distribución de la
  etiqueta recalculada con datos ≤ T (objetivo blando, pesos de madurez), Dirichlet α = 1 (12 parámetros libres).

Aviso a priori (Estratega): la regla de I mide ACELERACIÓN y la etiqueta, NIVEL. No se corrige.

Historia: las reglas necesitan t−3 y t−6. El arnés solo pasa al modelo las filas de entrenamiento (≤ corte − 6) y las
del mes que predice. Cada fila de la matriz PIT es la información publicada en SU fecha de decisión, así que el modelo
memoriza las filas que ha recibido (entrenamiento y predicción, siempre ≤ t) y calcula los estados con ellas.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.models import base as B
from src.models.metrics import QUADS
from src.regime.classify import inflation_state

G_VAR, SAHM_VAR = "growth_rt", "unrate_sahm"
I_CORE, I_HEADLINE = "core_cpi_6m_ann", "headline_cpi_6m_ann"
STATES = (("up", "down"), ("up", "up"), ("down", "up"), ("down", "down"))   # en el orden de QUADS (G, I)
SAHM_TRIGGER = 0.5


def rule_states(H: pd.DataFrame, ivar: str) -> pd.DataFrame:
    """Estados de las reglas mes a mes sobre una historia mensual (índice = mes; huecos = NaN)."""
    idx = pd.date_range(H.index.min(), H.index.max(), freq="MS")
    H = H.reindex(idx)
    for c in (G_VAR, SAHM_VAR):          # antes de que el arnés admita growth_rt (época): sin estado de G
        if c not in H:
            H[c] = np.nan
    g = H[G_VAR]
    gd6 = g - g.shift(6)
    up = (g > 0) & ((gd6 > 0) | gd6.isna()) & ~(H[SAHM_VAR] >= SAHM_TRIGGER)
    gstate = pd.Series(np.where(g.isna(), None, np.where(up, "up", "down")), index=idx, dtype=object)
    x = H[ivar] if ivar in H else pd.Series(np.nan, index=idx)
    accel = x - x.shift(3)
    istate = inflation_state(x.astype(float), accel.astype(float))
    return pd.DataFrame({"G": gstate, "I": istate}, index=idx)


def state_index(st: pd.DataFrame) -> np.ndarray:
    """0-3 en el orden de QUADS; −1 si falta algún eje."""
    out = np.full(len(st), -1)
    for k, (gs, is_) in enumerate(STATES):
        out[((st["G"] == gs) & (st["I"] == is_)).to_numpy()] = k
    return out


class RulesClassifier(B.Model):
    """Reglas de la Fase 1 (congeladas) + calibración 4 × 4 de Dirichlet en cada corte."""
    name = "rules_v1"
    features = (G_VAR, SAHM_VAR, I_HEADLINE, I_CORE)   # el subyacente entra cuando el arnés lo admite (época)
    uses_persistence = False

    def __init__(self, alpha: float = 1.0):
        self.params = {"alpha": alpha}
        self._hist = pd.DataFrame()
        self.table_ = None
        self.ivar_ = None

    def _remember(self, X: pd.DataFrame) -> None:
        X = X[[c for c in X.columns if c in self.features]]
        self._hist = X.combine_first(self._hist) if len(self._hist) else X.copy()
        self._hist = self._hist.sort_index()

    def _states(self, months) -> np.ndarray:
        st = rule_states(self._hist[self._hist.index <= max(months)], self.ivar_)
        return state_index(st.reindex(months))

    def fit(self, X, Y, y, info, sample_weight=None):
        self.ivar_ = I_CORE if I_CORE in X.columns else I_HEADLINE
        self._remember(X)
        s = self._states(X.index)
        w = np.ones(len(Y)) if sample_weight is None else np.asarray(sample_weight, float)
        Y = np.asarray(Y, float)
        a = self.params["alpha"]
        T = np.zeros((len(QUADS), len(QUADS)))
        for k in range(len(QUADS)):
            m = s == k
            T[k] = (w[m] @ Y[m] + a) / (w[m].sum() + a * len(QUADS))
        clim = (w @ Y + a) / (w.sum() + a * len(QUADS))
        self.table_, self.clim_ = T, clim
        self.counts_ = {QUADS[k]: float(w[s == k].sum()) for k in range(len(QUADS))}

    def predict_proba(self, X, info):
        self._remember(X)
        s = self._states(X.index)
        return np.vstack([self.table_[k] if k >= 0 else self.clim_ for k in s])

    def coefficients(self) -> dict:
        return {"ivar": self.ivar_, "peso_por_estado": self.counts_,
                **{f"{QUADS[k]}→{QUADS[j]}": float(self.table_[k, j]) for k in range(4) for j in range(4)}}


REGISTRY = {"rules_v1": RulesClassifier}
