"""Datos SINTÉTICOS generados con el modelo de M2 (m2_structural_spec.md §3) para los tests y los controles de M2/M3.
No lee la etiqueta ni datos reales."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.models import models_struct as MS

TRUE = {"lam": {"INDPRO": 0.8, "PAYEMS": 0.9, "W875RX1": 0.5, "CMRMTSPL": 0.6, "claims_4w_yoy": -0.5,
                "philly_neworders": 0.7},
        "phi": (1.1, -0.3),
        "rho": {"INDPRO": 0.2, "PAYEMS": 0.6, "W875RX1": -0.3, "CMRMTSPL": -0.2, "claims_4w_yoy": 0.7,
                "philly_neworders": 0.4},
        "q": {"INDPRO": 0.4, "PAYEMS": 0.15, "W875RX1": 0.6, "CMRMTSPL": 0.7, "claims_4w_yoy": 0.3,
              "philly_neworders": 0.5}}
STARTS = {"INDPRO": "1919-01", "PAYEMS": "1939-01", "W875RX1": "1959-01", "CMRMTSPL": "1967-01"}
LAGS = {"INDPRO": 1, "PAYEMS": 1, "W875RX1": 1, "CMRMTSPL": 2}     # meses de retraso de publicación
TAU = {"INDPRO": 0.25, "PAYEMS": 0.15, "W875RX1": 0.25, "CMRMTSPL": 0.25}
SCALE = {"INDPRO": 0.9, "PAYEMS": 0.25, "W875RX1": 0.5, "CMRMTSPL": 0.9}


class Synth:
    def __init__(self, seed: int = 0, end: str = "2004-12", true: dict = TRUE, phi=None):
        rng = np.random.default_rng(seed)
        self.idx = pd.date_range("1919-01-01", end + "-01", freq="MS")
        n = len(self.idx)
        phi = true["phi"] if phi is None else phi
        f = np.zeros(n + 50)
        for t in range(2, n + 50):
            f[t] = phi[0] * f[t - 1] + (phi[1] if len(phi) > 1 else 0) * f[t - 2] + rng.standard_normal()
        f = f[50:]
        self.f = pd.Series(f, index=self.idx)
        cols = list(true["lam"])
        u = {}
        for c in cols:
            x = np.zeros(n)
            for t in range(1, n):
                x[t] = true["rho"][c] * x[t - 1] + np.sqrt(true["q"][c]) * rng.standard_normal()
            u[c] = x
        self.r = {}
        self.levels = {}
        for c in MS.COINC:
            r = TAU[c] + SCALE[c] * (true["lam"][c] * f + u[c])
            s = pd.Series(r, index=self.idx)
            s = s[s.index >= STARTS[c] + "-01"]
            self.r[c] = s
            self.levels[c] = pd.Series(100 * np.exp(np.cumsum(s.to_numpy()) / 100), index=s.index)
        fl = pd.Series(f, index=self.idx)
        claims = 2.0 + 10 * (true["lam"]["claims_4w_yoy"] * (fl - fl.shift(12)) + u["claims_4w_yoy"])
        philly = 5.0 + 12 * (true["lam"]["philly_neworders"] * fl + u["philly_neworders"])
        self.X = pd.DataFrame({"claims_4w_yoy": claims, "philly_neworders": philly}, index=self.idx)
        self.X = self.X[self.X.index >= "1968-02-01"]
        self.X.loc[self.X.index < "1968-05-01", "philly_neworders"] = np.nan
        self.decision = pd.Series(self.idx + pd.offsets.MonthEnd(0), index=self.idx)

    def pit_levels(self, date, tamper_after: bool = False):
        mt = pd.Timestamp(date).to_period("M").to_timestamp()
        out = {}
        for c, lv in self.levels.items():
            k = lv[lv.index <= mt - pd.DateOffset(months=LAGS[c])]
            out[c] = k
        return {"levels": out, "from_vintage": {c: False for c in out}}

    def info(self, m0, rows=None, bound=None, data_key="synth", mode="latest_truncated", **kw):
        m0 = pd.Timestamp(m0)
        bound = pd.Timestamp(bound) if bound is not None else m0
        X = self.X[self.X.index <= bound]
        return {"refit_month": m0, "decision_date": self.decision[m0], "mode": mode, "data_key": data_key,
                "pit_mode": mode,
                "pit_levels": self.pit_levels, "features_history": X,
                "decision_calendar": self.decision[self.decision.index <= bound],
                "axis_scale": (0.0, 0.40), **kw}

    def true_G(self) -> pd.Series:
        return MS.label_G(self.levels)["G"]


def target_from_G(G: pd.Series, seed: int = 0, p_i: float = 0.3) -> pd.DataFrame:
    """Etiqueta SINTÉTICA de 4 cuadrantes a partir de un G sintético (p_g = Φ(G/0,40)), eje I constante, recesiones
    sintéticas cuando G < −1 (solo para los mínimos de entrenamiento del arnés)."""
    from scipy.stats import norm
    from src.models.metrics import P_COLS, QUADS
    G = G.dropna()
    pg = norm.cdf(G / 0.40)
    P = np.column_stack([pg * (1 - p_i), pg * p_i, (1 - pg) * p_i, (1 - pg) * (1 - p_i)])
    t = pd.DataFrame(P, index=G.index, columns=P_COLS)
    t["label_hard"] = [QUADS[i] for i in P.argmax(axis=1)]
    t["usrec"] = (G < -1.0).astype(float)
    t["weight"], t["provisional"], t["G"] = 1.0, False, G
    return t


def array_data(s: "Synth", extra_X: pd.DataFrame | None = None, target: pd.DataFrame | None = None,
               start: str = "1955-01", end: str = "2004-12"):
    """ArrayData del arnés con los datos sintéticos (niveles PIT sintéticos vía `levels_fn`)."""
    from src.models import harness as H
    tgt = target if target is not None else target_from_G(s.true_G())
    tgt = tgt[(tgt.index >= start) & (tgt.index <= end + "-01")]
    X = s.X.reindex(tgt.index)
    if extra_X is not None:
        X = X.join(extra_X.reindex(tgt.index))
    colinfo = {c: {"estado": "principal", "start": X[c].first_valid_index()} for c in X.columns}
    return H.ArrayData(X, tgt, colinfo, kind="synthetic", mode="synthetic", levels_fn=s.pit_levels,
                       decision=s.decision, data_key=f"synth|{id(s)}")
