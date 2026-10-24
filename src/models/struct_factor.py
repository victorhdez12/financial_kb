"""Núcleo del factor coincidente de M2 (m2_structural_spec.md v1.2 §3): modelo de estado en statsmodels `MLEModel`
(implementación ÚNICA, v1.1 B-2), con la representación mínima (estimación) y la aumentada de dimensión 47 (previsión
conjunta de las tasas que faltan de t−3 … t+4). Sin datos ni etiqueta: solo álgebra del modelo y su ajuste.

    x_i,m = λ_i·f_m + u_i,m + ε            (4 coincidentes y Filadelfia)
    x_c,m = λ_c·(f_m − f_{m−12}) + u_c,m + ε   (peticiones de paro: flujo, v1.1)
    f_m = φ1 f_{m−1} + φ2 f_{m−2} + η,  η ~ N(0, 1);   u_j,m = ρ_j u_j,{m−1} + e_j,  e_j ~ N(0, q_j);   ε ~ N(0, 1e-4)

Estado mínimo: (f_m … f_{m−12}, u_1 … u_J)  → 13 + J.
Estado aumentado: (f_m … f_{m−12}, u_i,m … u_i,{m−7} para cada coincidente, u_c, u_p) → 13 + 8·4 + 2 = 47.
Inicialización estacionaria (verosimilitud exacta). Parámetros: λ (J), φ1, φ2 (φ2 ≡ 0 con AR(1)), ρ (J), q (J).
"""
from __future__ import annotations

import warnings

import numpy as np
from statsmodels.tsa.statespace.mlemodel import MLEModel
from statsmodels.tsa.statespace.tools import constrain_stationary_univariate, unconstrain_stationary_univariate

N_F_LAGS = 13            # retardos 0…12 de f
N_U_LAGS = 8             # retardos 0…7 de u_i (meses t+4 … t−3 vistos desde t+4)
MEAS_VAR = 1e-4
RHO_MAX = 0.99
KINDS = ("coinc", "claims", "philly")


class FactorSSM(MLEModel):
    """kinds: tipo de cada columna de `endog` ("coinc", "claims", "philly")."""

    def __init__(self, endog, kinds, ar_order: int = 2, augmented: bool = False, meas_var: float = MEAS_VAR):
        kinds = tuple(kinds)
        if any(k not in KINDS for k in kinds):
            raise ValueError(f"tipos de serie desconocidos: {kinds}")
        if ar_order not in (1, 2):
            raise ValueError("ar_order ∈ {1, 2}")
        self.kinds, self.ar_order, self.augmented = kinds, ar_order, augmented
        J = len(kinds)
        self.u_pos, pos = [], N_F_LAGS
        for k in kinds:
            self.u_pos.append(pos)
            pos += N_U_LAGS if (augmented and k == "coinc") else 1
        k_states = pos
        super().__init__(endog, k_states=k_states, k_posdef=1 + J, initialization="stationary")
        self.ssm["obs_cov"] = np.eye(J) * meas_var
        T = np.zeros((k_states, k_states))
        for i in range(1, N_F_LAGS):
            T[i, i - 1] = 1.0
        for j, k in enumerate(kinds):
            p0 = self.u_pos[j]
            if augmented and k == "coinc":
                for i in range(1, N_U_LAGS):
                    T[p0 + i, p0 + i - 1] = 1.0
        self.ssm["transition"] = T
        R = np.zeros((k_states, 1 + J))
        R[0, 0] = 1.0
        for j in range(J):
            R[self.u_pos[j], 1 + j] = 1.0
        self.ssm["selection"] = R
        Z = np.zeros((J, k_states))
        for j in range(J):
            Z[j, self.u_pos[j]] = 1.0
        self.ssm["design"] = Z
        self.ssm["state_cov"] = np.eye(1 + J)
        self.J = J

    # ------------------------------------------------------------------ parámetros
    @property
    def n_params(self) -> int:
        return self.J + self.ar_order + 2 * self.J

    @property
    def param_names(self):
        names = [f"lambda.{j}" for j in range(self.J)] + [f"phi{i + 1}" for i in range(self.ar_order)]
        return names + [f"rho.{j}" for j in range(self.J)] + [f"q.{j}" for j in range(self.J)]

    def split(self, params):
        J, p = self.J, self.ar_order
        lam, phi = params[:J], params[J:J + p]
        rho, q = params[J + p:2 * J + p], params[2 * J + p:]
        return lam, phi, rho, q

    def transform_params(self, unconstrained):
        u = np.asarray(unconstrained)
        lam, phi, rho, q = self.split(u)
        return np.r_[lam, constrain_stationary_univariate(phi), RHO_MAX * np.tanh(rho), np.exp(q)]

    def untransform_params(self, constrained):
        c = np.asarray(constrained, float)
        lam, phi, rho, q = self.split(c)
        return np.r_[lam, unconstrain_stationary_univariate(phi), np.arctanh(np.clip(rho / RHO_MAX, -1 + 1e-12,
                                                                                         1 - 1e-12)), np.log(q)]

    def update(self, params, transformed=True, includes_fixed=False, complex_step=False):
        params = super().update(params, transformed=transformed, includes_fixed=includes_fixed,
                                complex_step=complex_step)
        lam, phi, rho, q = self.split(params)
        for j, k in enumerate(self.kinds):
            self.ssm["design", j, 0] = lam[j]
            if k == "claims":
                self.ssm["design", j, N_F_LAGS - 1] = -lam[j]
            self.ssm["transition", self.u_pos[j], self.u_pos[j]] = rho[j]
            self.ssm["state_cov", 1 + j, 1 + j] = q[j]
        self.ssm["transition", 0, 0] = phi[0]
        if self.ar_order == 2:
            self.ssm["transition", 0, 1] = phi[1]

    # ------------------------------------------------------------------ utilidades
    def f_index(self, lag: int) -> int:
        return lag

    def u_index(self, j: int, lag: int = 0) -> int:
        if lag and not (self.augmented and self.kinds[j] == "coinc"):
            raise ValueError("solo el estado aumentado guarda retardos de u_i")
        return self.u_pos[j] + lag


def fit_ml(endog, kinds, start_params, ar_order: int = 2, maxiter: int = 1000, gtol: float = 1e-6):
    """Máxima verosimilitud con L-BFGS-B (statsmodels; `pgtol` = gtol). Devuelve (params, converged, info). Aplica la
    normalización λ_PAYEMS > 0 (la columna 1 es PAYEMS por convención del llamador: `payems_col`)."""
    mod = FactorSSM(endog, kinds, ar_order=ar_order)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = mod.fit(start_params=np.asarray(start_params, float), method="lbfgs", maxiter=maxiter, pgtol=gtol,
                      disp=False, cov_type="none")
    rv = res.mle_retvals or {}
    conv = bool(rv.get("converged", False)) and int(rv.get("warnflag", 1)) == 0
    return np.asarray(res.params, float), conv, {"llf": float(res.llf), "iter": int(rv.get("iterations", -1)),
                                                 "warnflag": int(rv.get("warnflag", -1))}


def loglike(endog, kinds, params, ar_order: int = 2, augmented: bool = False) -> float:
    mod = FactorSSM(endog, kinds, ar_order=ar_order, augmented=augmented)
    return float(mod.loglike(np.asarray(params, float)))


def filter_last(endog, kinds, params, ar_order: int = 2):
    """Filtro con el estado AUMENTADO: media y covarianza del estado en el último mes de `endog` condicionadas a TODO lo
    observado (los últimos meses de `endog` son NaN: t+1 … t+4)."""
    mod = FactorSSM(endog, kinds, ar_order=ar_order, augmented=True)
    res = mod.filter(np.asarray(params, float), cov_type="none")
    return mod, res.filtered_state[:, -1].copy(), res.filtered_state_cov[:, :, -1].copy()
