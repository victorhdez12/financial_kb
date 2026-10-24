"""Pool de log-scores `pool_g` del eje G con recalibración beta (BLP) (docs/models/pool_spec.md v1.2, H-POOL-001) y
sus variantes preregistradas (`pool_g_eq`, `pool_g_lin`, `pool_g_kull`, `pool_g_unif`). Eje I = M0.

Modelo APILADO (arnés v2.4, `B.StackedAxisModel`): en cada corte m0 recibe las P(G alto) FUERA DE MUESTRA de M0,
M2 y M3 (`info["stack_preds"]`). Muestra de estimación = meses de entrenamiento del corte (s ≤ m0 − 6, objetivo blando
recalculado ≤ m0, peso de madurez × weight) con las tres predicciones. Con < N_min = 60 meses, pool = M0 exactamente.
Si no, MAP conjunto de (w, a, b): Σ ω_s[t ln P + (1 − t) ln(1 − P)] + κ Σ m_k ln w_k − [(ln a)² + (ln b)²]/(2·0,5²),
P = B_{a,b}(Σ w_k p_k), w = softmax(0, v1, v2), L-BFGS-B 500 / 1e-8, arranque en la moda de la previa.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit

from src.models import base as B
from src.models import regime_components as C

PS = C.POOL

IMPLEMENTATION_CHOICES = (
    "gradiente numérico de scipy (diferencias finitas por defecto) en el MAP del pool: la derivada de la beta "
    "regularizada respecto de a y b no tiene forma cerrada sencilla",
    "en el objetivo, P = B_{a,b}(Σ w p) se recorta a [1e-6, 1 − 1e-6] (el recorte de la predicción)",
    "las variantes (_eq, _lin, _kull, _unif) conservan el arranque: pool = M0 mientras |S| < 60",
    "_kull en dos pasos: pesos del pool lineal MAP (como _lin) y después la beta de Kull sobre su salida, MAP con "
    "c, ln a, ln b ~ N(0; 0,5²), L-BFGS-B 500 / 1e-8, arranque c = 0, a = b = 1",
)


def _softmax(v):
    z = np.r_[0.0, v]
    z = np.exp(z - z.max())
    return z / z.sum()


def _ll(P, t, w):
    P = np.clip(P, PS.clip, 1 - PS.clip)
    return float((w * (t * np.log(P) + (1 - t) * np.log(1 - P))).sum())


def fit_pool(p: np.ndarray, t: np.ndarray, w: np.ndarray, prior_mode=PS.prior_mode, beta: bool = True,
             kappa: float = PS.kappa, maxiter: int = PS.maxiter, gtol: float = PS.gtol) -> tuple[dict, bool]:
    """MAP conjunto de los pesos (Dirichlet con moda `prior_mode`, κ) y, con `beta`, de la beta (ln a, ln b ~ N(0; 0,5²))."""
    from scipy.stats import beta as Bd
    p = np.clip(np.asarray(p, float), PS.clip, 1 - PS.clip)
    t, w, m = np.asarray(t, float), np.asarray(w, float), np.asarray(prior_mode, float)
    sd2 = 2 * PS.beta_log_sd ** 2

    def negpost(x):
        wk = _softmax(x[:2])
        lin = np.clip(p @ wk, PS.clip, 1 - PS.clip)
        if beta:
            la, lb = x[2], x[3]
            P = Bd.cdf(lin, np.exp(la), np.exp(lb))
            pr = -(la ** 2 + lb ** 2) / sd2
        else:
            P, pr = lin, 0.0
        return -(_ll(P, t, w) + kappa * float((m * np.log(wk)).sum()) + pr)

    x0 = np.r_[np.log(m[1:] / m[0]), [0.0, 0.0] if beta else []]
    res = minimize(negpost, x0, method="L-BFGS-B", options={"maxiter": maxiter, "gtol": gtol})
    wk = _softmax(res.x[:2])
    a, b = (float(np.exp(res.x[2])), float(np.exp(res.x[3]))) if beta else (1.0, 1.0)
    return {"w": wk, "a": a, "b": b}, bool(res.success)


def fit_kull(q: np.ndarray, t: np.ndarray, w: np.ndarray, maxiter: int = PS.maxiter,
             gtol: float = PS.gtol) -> tuple[dict, bool]:
    """Beta de Kull et al.: Λ(c + a ln q − b ln(1 − q)), MAP con c, ln a, ln b ~ N(0; 0,5²)."""
    q = np.clip(np.asarray(q, float), PS.clip, 1 - PS.clip)
    lq, l1q = np.log(q), np.log(1 - q)
    sd2 = 2 * PS.beta_log_sd ** 2

    def negpost(x):
        P = expit(x[0] + np.exp(x[1]) * lq - np.exp(x[2]) * l1q)
        return -(_ll(P, t, w) - (x[0] ** 2 + x[1] ** 2 + x[2] ** 2) / sd2)

    res = minimize(negpost, np.zeros(3), method="L-BFGS-B", options={"maxiter": maxiter, "gtol": gtol})
    return {"c": float(res.x[0]), "a": float(np.exp(res.x[1])), "b": float(np.exp(res.x[2]))}, bool(res.success)


class PoolG(B.StackedAxisModel):
    """`pool_g` y variantes. weights: "map" | "equal"; recal: "blp" | "none" | "kull"."""
    name = "pool_g"
    components = PS.components
    axis_features = {"G": (), "I": ()}
    uses_persistence = True
    m2_dependent = True

    def __init__(self, weights: str = "map", recal: str = "blp", prior_mode=PS.prior_mode,
                 philly_pre1990_nan: bool = False, name: str | None = None):
        if weights not in ("map", "equal") or recal not in ("blp", "none", "kull"):
            raise ValueError(f"variante desconocida: {weights}/{recal}")
        self.params = {"weights": weights, "recal": recal, "prior_mode": tuple(prior_mode),
                       "philly_pre1990_nan": bool(philly_pre1990_nan)}
        if name:
            self.name = name
        self._m0 = B.CalibratedPersistence()
        self.state: dict | None = None
        self._hist: list[dict] = []

    def _P(self, sp, months) -> np.ndarray:
        miss = [c for c in self.components if c not in sp]
        if miss:
            raise ValueError(f"{self.name}: faltan predicciones de {miss}")
        return sp.reindex(months)[list(self.components)].to_numpy(float)

    def fit_axis(self, axis, X, t, w, info):
        if axis == "I":
            return self._m0.fit_axis(axis, X, t, w, info)
        sp = info["stack_preds"]
        P = self._P(sp, X.index)
        ok = np.isfinite(P).all(axis=1)
        n = int(ok.sum())
        if n < PS.n_min:
            self.state = {"mode": "m0", "n": n, "w": np.array([1.0, 0.0, 0.0]), "a": 1.0, "b": 1.0}
            return
        p, tt, ww = P[ok], np.asarray(t, float)[ok], np.asarray(w, float)[ok]
        wts, rc = self.params["weights"], self.params["recal"]
        if wts == "equal":
            st, conv = {"w": np.full(3, 1 / 3), "a": 1.0, "b": 1.0}, True
        else:
            st, conv = fit_pool(p, tt, ww, prior_mode=self.params["prior_mode"], beta=(rc == "blp"))
        if rc == "kull":
            k, ck = fit_kull(np.clip(p, PS.clip, 1 - PS.clip) @ st["w"], tt, ww)
            st, conv = {**st, "kull": k}, conv and ck
        self.state = {"mode": "pool", "n": n, **st}
        self._hist.append({"T": f"{info['refit_month']:%Y-%m}", "n": n, "fit_converged": bool(conv)})

    def predict_axis(self, axis, X, info):
        if axis == "I":
            return self._m0.predict_axis(axis, X, info)
        P = self._P(info["stack_preds"], X.index)
        if self.state["mode"] == "m0":
            return P[:, 0]                               # pool = M0, bit a bit
        if not np.isfinite(P).all():
            raise ValueError(f"{self.name}: falta la predicción de un componente en el mes de prueba")
        lin = np.clip(np.clip(P, PS.clip, 1 - PS.clip) @ self.state["w"], PS.clip, 1 - PS.clip)
        if "kull" in self.state:
            k = self.state["kull"]
            out = expit(k["c"] + k["a"] * np.log(lin) - k["b"] * np.log(1 - lin))
            return np.clip(out, PS.clip, 1 - PS.clip)
        return C.blp_transform(lin, self.state["a"], self.state["b"])

    def coefficients(self) -> dict:
        out = {f"I:{k[2:]}": v for k, v in self._m0.coefficients().items()}
        if self.state is None:
            return out
        w = self.state["w"]
        out.update({"G:w_m0": float(w[0]), "G:w_m2": float(w[1]), "G:w_m3": float(w[2]),
                    "G:blp_a": float(self.state["a"]), "G:blp_b": float(self.state["b"]),
                    "G:n_est": float(self.state["n"])})
        if "kull" in self.state:
            out.update({f"G:kull_{k}": float(v) for k, v in self.state["kull"].items()})
        return out

    def diagnostics(self) -> dict:
        return {"cortes_estimados": len(self._hist),
                "sin_convergencia": int(sum(not h["fit_converged"] for h in self._hist))}


def _variant(name, **kw):
    def make(philly_pre1990_nan: bool = False, **extra):
        return PoolG(philly_pre1990_nan=philly_pre1990_nan, name=name, **{**kw, **extra})
    make.m2_dependent = True
    make.components = PS.components
    return make


REGISTRY = {
    "pool_g": _variant("pool_g"),
    "pool_g_eq": _variant("pool_g_eq", weights="equal", recal="none"),
    "pool_g_lin": _variant("pool_g_lin", recal="none"),
    "pool_g_kull": _variant("pool_g_kull", recal="kull"),
    "pool_g_unif": _variant("pool_g_unif", prior_mode=(1 / 3, 1 / 3, 1 / 3)),
}
