"""M3 `m3_tvtp_g`: Markov de 2 estados del eje G con transiciones variables (TVTP), anclado en la persistencia PIT, con
emisión desde el nowcast en tiempo real de M2 (docs/models/m3_tvtp_spec.md v1.2, H-M3-001). Referencia anidada
`m3_ctp_g` (γ ≡ 0) y sensibilidades `_l16`, `_l12`, `_fac`, `_nocal`. Eje I = M0.

- Estados S_s ∈ {A = G alto, B = G bajo} = etiqueta dura del eje G recalculada ≤ T (p_g_high ≥ 0,5) en los meses de
  entrenamiento que da el arnés (embargo, purga, pesos de madurez).
- Transiciones: P(A→B) = Λ(α_A − γ1·z(curve_min12) + γ2·z(baa_d6m)), P(B→A) = Λ(α_B − γ3·z(baa_d6m) + γ4·z(eq_ret_6m)),
  γ ≥ 0, previa N(0; 0,5²) (2·γ² en escala de suma), dos logísticas ponderadas (peso del par = peso de madurez de s),
  L-BFGS-B 500 / 1e-8, arranque γ = 0, α = logit de la frecuencia ponderada.
- Emisión: Ĝ^rt_s (media del nowcast de M2 en la fecha de decisión de s, con los parámetros del factor vigentes en el
  corte; motor y caché COMPARTIDOS con M2, `models_struct.engine_for`), N(μ_k, ω²) templada a λ = 1/3.
- Filtro anclado: π_a = clip(pers_axis_growth, 1e-3) en el mes de la persistencia a de la fila; meses a+1 … m.
- Calibración Λ(c + b·logit(clip(p_filtro, 1e-3))), L2 = 1 sobre b, objetivo blando, pesos de madurez, arranque c = 0,
  b = 1, L-BFGS-B 500 / 1e-8 (dentro de muestra, declarado en la spec).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from src.models import base as B
from src.models import models_struct as MS
from src.models import regime_components as C

TV = C.TVTP
TRANS = ("curve_min12", "baa_d6m", "eq_ret_6m")
CLIP_P = 1e-3

IMPLEMENTATION_CHOICES = (
    "estandarización de z: media y desviación (ddof 0) SIN ponderar de las filas de entrenamiento del corte; un z que "
    "falte en un mes del filtro (fuera del entrenamiento) se toma = 0 (la media), como la imputación del arnés",
    "α de arranque: logit de la frecuencia ponderada de salida, recortada a [1e-3, 1 − 1e-3]",
    "gradiente analítico en las logísticas y en la calibración",
    "mes del filtro sin emisión finita (Ĝ NaN): solo predicción, sin actualización",
    "_fac: f̂_{s|s} estandarizado con la media y la desviación (ddof 0) de los meses de entrenamiento (la emisión "
    "gaussiana con μ_k, ω estimadas es invariante a esa transformación)",
)


def _sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def fit_logistic(Z: np.ndarray, y: np.ndarray, w: np.ndarray, free_gamma: bool, prior_sd: float = TV.gamma_prior_sd,
                 maxiter: int = TV.opt_maxiter, gtol: float = TV.opt_gtol) -> tuple[np.ndarray, bool]:
    """Logística ponderada η = α + Z·γ con γ ≥ 0 (cotas) y penalización Σγ²/(2·sd²); `free_gamma=False` → γ ≡ 0.
    Z ya lleva el signo de cada variable. Devuelve ([α, γ…], converged)."""
    Z, y, w = np.asarray(Z, float), np.asarray(y, float), np.asarray(w, float)
    k = Z.shape[1]
    pen = 1.0 / (2.0 * prior_sd ** 2)
    fr = float(np.clip((w * y).sum() / w.sum(), 1e-3, 1 - 1e-3)) if w.sum() > 0 else 0.5
    x0 = np.r_[np.log(fr / (1 - fr)), np.zeros(k)]

    def f(b):
        eta = b[0] + Z @ b[1:]
        loss = (w * (np.logaddexp(0, eta) - y * eta)).sum() + pen * (b[1:] ** 2).sum()
        r = w * (_sig(eta) - y)
        g = np.r_[r.sum(), Z.T @ r + 2 * pen * b[1:]]
        return loss, g

    bounds = [(None, None)] + ([(0.0, None)] * k if free_gamma else [(0.0, 0.0)] * k)
    res = minimize(f, x0, jac=True, method="L-BFGS-B", bounds=bounds, options={"maxiter": maxiter, "gtol": gtol})
    return res.x, bool(res.success)


def fit_calibration(L: np.ndarray, t: np.ndarray, w: np.ndarray, l2: float = TV.cal_l2,
                    maxiter: int = TV.opt_maxiter, gtol: float = TV.opt_gtol) -> tuple[np.ndarray, bool]:
    """Λ(c + b·L) con objetivo blando t, pesos w, L2 = l2·b²; arranque (0, 1)."""
    L, t, w = np.asarray(L, float), np.asarray(t, float), np.asarray(w, float)

    def f(p):
        eta = p[0] + p[1] * L
        loss = (w * (np.logaddexp(0, eta) - t * eta)).sum() + l2 * p[1] ** 2
        r = w * (_sig(eta) - t)
        return loss, np.array([r.sum(), (r * L).sum() + 2 * l2 * p[1]])

    res = minimize(f, np.array([0.0, 1.0]), jac=True, method="L-BFGS-B",
                   options={"maxiter": maxiter, "gtol": gtol})
    return res.x, bool(res.success)


def anchored_filter(pi_a: float, zs: np.ndarray, xs: np.ndarray, par: dict, temper: float) -> float:
    """P(S_m = A | …): parte de π_a en el mes del ancla y filtra los meses a+1 … m (filas de zs/xs, en orden):
    predicción con la matriz de transición de z_s y actualización con la emisión templada de x_s."""
    p = float(np.clip(pi_a, CLIP_P, 1 - CLIP_P))
    lv = np.log(par["omega2"])
    for z, x in zip(zs, xs):
        pab = _sig(par["alpha_A"] - par["gamma1"] * z[0] + par["gamma2"] * z[1])
        pba = _sig(par["alpha_B"] - par["gamma3"] * z[1] + par["gamma4"] * z[2])
        pa = p * (1 - pab) + (1 - p) * pba
        if np.isfinite(x):
            la = -0.5 * temper * ((x - par["mu_A"]) ** 2 / par["omega2"] + lv)
            lb = -0.5 * temper * ((x - par["mu_B"]) ** 2 / par["omega2"] + lv)
            mx = max(la, lb)
            num, den = pa * np.exp(la - mx), pa * np.exp(la - mx) + (1 - pa) * np.exp(lb - mx)
            p = num / den
        else:
            p = pa
    return float(p)


class TVTPG(B.AxisModel):
    """M3 `m3_tvtp_g` (spec v1.2). `constant_transitions=True` → `m3_ctp_g` (γ ≡ 0)."""
    name = "m3_tvtp_g"
    axis_features = {"G": (*TRANS, *C.STRUCT.extra_features), "I": ()}
    uses_persistence = True
    uses_pit_levels = True
    uses_pers_label_month = True
    m2_dependent = True

    def __init__(self, constant_transitions: bool = False, temper: float = TV.temper, emission: str = "ghat",
                 calibrate: bool = True, philly_pre1990_nan: bool = False, name: str | None = None):
        if emission not in ("ghat", "factor"):
            raise ValueError(f"emisión desconocida: {emission}")
        self.params = {"constant_transitions": constant_transitions, "temper": temper, "emission": emission,
                       "calibrate": calibrate, "philly_pre1990_nan": bool(philly_pre1990_nan)}
        self.name = name or ("m3_ctp_g" if constant_transitions else "m3_tvtp_g")
        self.scfg = MS.StructCfg(philly_pre1990_nan=bool(philly_pre1990_nan))
        self._v: MS.FactorVersion | None = None
        self._m0 = B.CalibratedPersistence()
        self.par: dict | None = None
        self._zstd = None
        self._xstd = (0.0, 1.0)
        self._hist: list[dict] = []

    # entradas ------------------------------------------------------------------
    def _ensure_version(self, info):
        MS._check_info(info)
        eng = MS.engine_for(info, self.scfg)
        m0 = pd.Timestamp(info["refit_month"])
        if self._v is None or (m0.month == C.STRUCT.reestimate_month and m0 != self._v.T):
            self._v = eng.version(m0, info, self._v)
        return eng

    def _emission(self, eng, months, info) -> np.ndarray:
        key = "G" if self.params["emission"] == "ghat" else "f"
        x = np.array([eng.nowcast_base(self._v, pd.Timestamp(m), info)[key] for m in months], float)
        return x if key == "G" else (x - self._xstd[0]) / self._xstd[1]

    def _z(self, months, info) -> np.ndarray:
        fh = info["features_history"]
        Z = fh.reindex(pd.DatetimeIndex(months))[list(TRANS)].to_numpy(float)
        Z = (Z - self._zstd[0]) / self._zstd[1]
        return np.where(np.isfinite(Z), Z, 0.0)

    def _pfilter(self, eng, rows: pd.DataFrame, info) -> np.ndarray:
        out = []
        for m, r in rows.iterrows():
            a = pd.Timestamp(r["pers_label_month"])
            seq = pd.date_range(a + pd.DateOffset(months=1), m, freq="MS")
            out.append(anchored_filter(r[B.PERS_AXIS["G"]], self._z(seq, info), self._emission(eng, seq, info),
                                       self.par, self.params["temper"]))
        return np.array(out)

    # interfaz ------------------------------------------------------------------
    def fit_axis(self, axis, X, t, w, info):
        if axis == "I":
            return self._m0.fit_axis(axis, X, t, w, info)
        eng = self._ensure_version(info)
        months = X.index
        Zraw = X[list(TRANS)].to_numpy(float)
        self._zstd = (Zraw.mean(axis=0), Zraw.std(axis=0))
        z = (Zraw - self._zstd[0]) / self._zstd[1]
        Sx = (np.asarray(t, float) >= 0.5).astype(int)          # 1 = A (G alto)
        w = np.asarray(w, float)
        if self.params["emission"] == "factor":
            f = np.array([eng.nowcast_base(self._v, m, info)["f"] for m in months])
            f = f[np.isfinite(f)]
            self._xstd = (float(f.mean()), float(f.std()))
        x = self._emission(eng, months, info)
        # pares de meses consecutivos de entrenamiento
        prev = pd.DatetimeIndex(months) - pd.DateOffset(months=1)
        pos = pd.Index(months).get_indexer(prev)
        ok = pos >= 0
        i1, i0 = np.where(ok)[0], pos[ok]
        free = not self.params["constant_transitions"]
        fromA, fromB = Sx[i0] == 1, Sx[i0] == 0
        ZA = np.column_stack([-z[i1, 0], z[i1, 1]])             # −γ1·z(curve) + γ2·z(baa)
        ZB = np.column_stack([-z[i1, 1], z[i1, 2]])             # −γ3·z(baa)  + γ4·z(eq)
        bA, cA = fit_logistic(ZA[fromA], (Sx[i1][fromA] == 0).astype(float), w[i1][fromA], free)
        bB, cB = fit_logistic(ZB[fromB], (Sx[i1][fromB] == 1).astype(float), w[i1][fromB], free)
        fin = np.isfinite(x)
        wa, wb = w * (Sx == 1) * fin, w * (Sx == 0) * fin
        if wa.sum() <= 0 or wb.sum() <= 0:
            raise ValueError(f"{self.name}: un estado sin meses de entrenamiento con emisión finita")
        xx = np.where(fin, x, 0.0)
        muA, muB = float((wa * xx).sum() / wa.sum()), float((wb * xx).sum() / wb.sum())
        om2 = float(((wa * (xx - muA) ** 2).sum() + (wb * (xx - muB) ** 2).sum()) / (wa.sum() + wb.sum()))
        self.par = {"alpha_A": bA[0], "gamma1": bA[1], "gamma2": bA[2], "alpha_B": bB[0], "gamma3": bB[1],
                    "gamma4": bB[2], "mu_A": muA, "mu_B": muB, "omega2": om2}
        conv = cA and cB
        if self.params["calibrate"]:
            pf = self._pfilter(eng, X, info)
            L = B.logit(pf, CLIP_P)
            cal, cc = fit_calibration(L, t, w)
            self.par.update({"cal_c": float(cal[0]), "cal_b": float(cal[1])})
            conv = conv and cc
        self._hist.append({"T": f"{pd.Timestamp(info['refit_month']):%Y-%m}", "fit_converged": bool(conv),
                           "factor": self._v.id if self._v else None,
                           "factor_converged": bool(self._v.converged) if self._v else True})

    def predict_axis(self, axis, X, info):
        if axis == "I":
            return self._m0.predict_axis(axis, X, info)
        eng = MS.engine_for(info, self.scfg)
        pf = self._pfilter(eng, X, info)
        if not self.params["calibrate"]:
            return pf
        L = B.logit(pf, CLIP_P)
        return _sig(self.par["cal_c"] + self.par["cal_b"] * L)

    def coefficients(self) -> dict:
        out = {f"I:{k[2:]}": v for k, v in self._m0.coefficients().items()}
        if self.par is None:
            return out
        p = self.par
        out.update({"G:alpha_A": p["alpha_A"], "G:alpha_B": p["alpha_B"], **{f"G:gamma{j}": p[f"gamma{j}"]
                                                                             for j in range(1, 5)},
                    "G:mu_A": p["mu_A"], "G:mu_B": p["mu_B"], "G:omega": float(np.sqrt(p["omega2"]))})
        if "cal_c" in p:
            out.update({"G:cal_c": p["cal_c"], "G:cal_b": p["cal_b"]})
        return {k: float(v) for k, v in out.items()}

    def diagnostics(self) -> dict:
        return {"cortes": len(self._hist), "sin_convergencia": int(sum(not h["fit_converged"] for h in self._hist)),
                "factor_sin_convergencia": sorted({h["factor"] for h in self._hist if not h["factor_converged"]})}


def _variant(name, **kw):
    def make(philly_pre1990_nan: bool = False, **extra):
        return TVTPG(philly_pre1990_nan=philly_pre1990_nan, name=name, **{**kw, **extra})
    make.m2_dependent = True
    return make


REGISTRY = {
    "m3_tvtp_g": _variant("m3_tvtp_g"),
    "m3_ctp_g": _variant("m3_ctp_g", constant_transitions=True),
    "m3_tvtp_g_l16": _variant("m3_tvtp_g_l16", temper=TV.temper_sens[0]),
    "m3_tvtp_g_l12": _variant("m3_tvtp_g_l12", temper=TV.temper_sens[1]),
    "m3_tvtp_g_fac": _variant("m3_tvtp_g_fac", emission="factor"),
    "m3_tvtp_g_nocal": _variant("m3_tvtp_g_nocal", calibrate=False),
}
