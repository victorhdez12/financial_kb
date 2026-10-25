"""ESQUELETO de los componentes del pool (M2 estructural, M3 TVTP) y del pool, con las constantes de sus specs a priori.

Specs (v1.1, congeladas antes de cualquier contacto con la etiqueta para M2/M3/pool, 2026-10-24; v1.0 = 1a5f1f9):
- docs/models/m2_structural_spec.md   (H-M2-001, `m2_struct_g`)
- docs/models/m3_tvtp_spec.md         (H-M3-001, `m3_tvtp_g`, referencia `m3_ctp_g`)
- docs/models/pool_spec.md            (H-POOL-001, `pool_g`)

Aquí NO hay ningún ajuste: solo constantes fijadas en las specs, funciones definitorias (pesos de la etiqueta, carga
de las peticiones de paro, transformación beta del pool, regla 3 m × 80/20, criterio 8 de signos de M3 y regla
operativa de S-PIT-001) y clases sin implementar. El módulo NO se llama `models_*.py` a
propósito: el registro de modelos del arnés (`harness.model_registry`) no lo carga, así que ninguna configuración puede
usar estos esqueletos por accidente. La implementación irá en `models_struct.py`, `models_tvtp.py` y `models_pool.py`
con las extensiones del arnés v2.4 (specs, §8/§6).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.models import base as B

# Pesos de las tasas mensuales r_{t−3} … r_{t+4} en el ritmo g_t de la etiqueta (ficha §3; R.pace): media de 3 meses
# centrada del nivel y variación log anualizada t−3 → t+3 ⇒ g_t ≈ (2/3)·Σ w_k·r_{t−3+k}, con r = 100·Δln(nivel).
LABEL_PACE_WEIGHTS = (1, 2, 3, 3, 3, 3, 2, 1)
LABEL_PACE_OFFSETS = tuple(range(-3, 5))          # meses t−3 … t+4


@dataclass(frozen=True)
class StructSpec:                                  # m2_structural_spec.md §2-§4
    coincident: tuple[str, ...] = ("INDPRO", "PAYEMS", "W875RX1", "CMRMTSPL")
    extra_features: tuple[str, ...] = ("claims_4w_yoy", "philly_neworders")
    data_start: str = "1968-06"
    trend_months: int = 120                        # τʳ: mediana de los 120 meses previos …
    trend_min_obs: int = 90                        # … con ≥ 90 presentes
    factor_order: int = 2
    idio_order: int = 1
    claims_diff_lag: int = 12                      # v1.1: la tasa interanual (flujo) carga en f_m − f_{m−12}
    n_coincident_lags: int = 8                     # u_i: retardos 0…7 (t−3 … t+4) en el estado aumentado
    implementation: str = "statsmodels.MLEModel 0.15.0"   # única (v1.1, B-2)
    warm_start: bool = False                       # v1.1: arranque determinista fijo en cada reestimación
    balanced_min_months: int = 60                  # panel balanceado del arranque: si < 60 meses, el de las 4 coincidentes
    meas_var: float = 1e-4                         # regularización numérica fija
    rho_max: float = 0.99
    maxiter: int = 1000
    gtol: float = 1e-6
    reestimate_month: int = 1                      # parámetros: primer corte y cada enero
    horizon_after: int = 4                         # se prevé hasta t+4
    rev_age_buckets: tuple[str, ...] = ("1", "2", "3", "4", "5", "6", "7-12", ">=13")
    trend_err_start: str = "1965-01"               # V_tend: meses s de 1965-01 a T−65
    trend_err_lag: int = 65
    rev_var_sample: tuple[str, str] = ("1968-06", "2004-12")   # Var(r_i): última vintage (v1.1, M-2)
    rev_principal_is_pit: bool = False             # V_rev frente a la última vintage: declarado NO PIT
    rev_pit_min_lag: int = 24                      # sensibilidad m2_struct_g_revpit: fechas s ≤ T − 24
    rev_pit_min_pairs: int = 30
    n_params: int = 20

    @property
    def state_dim(self) -> int:
        """Estado aumentado (§3): retardos 0…12 de f + 0…7 de u_i (4 coincidentes) + u_c + u_p = 47 (46 en v1.0)."""
        return (self.claims_diff_lag + 1) + len(self.coincident) * self.n_coincident_lags + len(self.extra_features)


@dataclass(frozen=True)
class TVTPSpec:                                    # m3_tvtp_spec.md §2-§3
    exit_high: tuple[tuple[str, int], ...] = (("curve_min12", -1), ("baa_d6m", +1))   # signo en el logit de A → B
    exit_low: tuple[tuple[str, int], ...] = (("baa_d6m", -1), ("eq_ret_6m", +1))      # signo en el logit de B → A
    gamma_prior_sd: float = 0.5                    # N(0; 0,5²) sobre cada γ ⇒ penalización 2·γ² (escala de suma)
    temper: float = 1 / 3                          # λ
    temper_sens: tuple[float, ...] = (1 / 6, 1 / 2)
    pers_eps: float = 1e-3
    cal_l2: float = 1.0
    opt_maxiter: int = 500                         # logísticas y calibración (v1.1, B-5)
    opt_gtol: float = 1e-8
    sign_threshold: float = 0.01                   # criterio 8: γ_j > 0,01 (estricto) …
    sign_min_frac: float = 0.5                     # … en ≥ 50 % de los cortes, cada γ por separado
    sign_window: tuple[str, str] = ("2005-01", "2021-10")
    sign_coefs: tuple[str, ...] = ("G:gamma1", "G:gamma2", "G:gamma3", "G:gamma4")
    n_params: int = 11


@dataclass(frozen=True)
class PoolSpec:                                    # pool_spec.md §2-§3
    components: tuple[str, ...] = ("m0_calibrated_persistence", "m2_struct_g", "m3_tvtp_g")
    prior_mode: tuple[float, ...] = (0.5, 0.25, 0.25)
    kappa: float = 20.0                            # Dirichlet α_k = 1 + κ·m_k
    beta_log_sd: float = 0.5                       # ln a, ln b ~ N(0; 0,5²)
    n_min: int = 60
    embargo: int = 6
    clip: float = 1e-6
    maxiter: int = 500
    gtol: float = 1e-8


STRUCT, TVTP, POOL = StructSpec(), TVTPSpec(), PoolSpec()


def pace_rate_coeffs(sigma: float, n_ind: int) -> np.ndarray:
    """∂G_t/∂r_{i,m} para m = t−3 … t+4 (m2_structural_spec.md §4, V_filtro y V_rev): (1/n)·(2/3)·w/σ_i."""
    return (2.0 / 3.0) * np.asarray(LABEL_PACE_WEIGHTS, float) / (float(sigma) * int(n_ind))


def claims_factor_loading(lam: float = 1.0, lag: int = STRUCT.claims_diff_lag) -> np.ndarray:
    """Carga de `claims_4w_yoy` sobre los retardos 0…lag de f (m2_structural_spec.md v1.1 §3): λ·(f_m − f_{m−12})."""
    v = np.zeros(lag + 1)
    v[0], v[lag] = lam, -lam
    return v


def gamma_fraction_criterion(coefs: pd.DataFrame, cut_months, threshold: float = TVTP.sign_threshold,
                             min_frac: float = TVTP.sign_min_frac, keys=TVTP.sign_coefs) -> dict:
    """Criterio 8 de P-EVAL-BASE v4 (m3_tvtp_spec.md v1.1 §5): para cada γ por separado, fracción de cortes con
    γ > threshold (estricto) ≥ min_frac. `coefs`: coeficientes por corte (índice = mes del corte); `cut_months`: los
    cortes de la ventana en que el modelo debía ajustarse (denominador). Un corte sin coeficiente cuenta como no
    cumplido. Referencia para la clave `fraccion_umbral` del arnés v2.4."""
    cuts = pd.Index(cut_months)
    out = {}
    for k in keys:
        x = coefs[k].reindex(cuts) if k in coefs else pd.Series(np.nan, index=cuts)
        ok = (x > threshold).fillna(False)
        out[k] = {"umbral": threshold, "n_cortes": int(len(cuts)), "n_sin_coef": int(x.isna().sum()),
                  "frac": float(ok.mean()) if len(cuts) else float("nan")}
    cumple = bool(len(cuts)) and all(v["frac"] >= min_frac for v in out.values())
    return {"fraccion_umbral": out, "criterio_fraccion_cumple": cumple}


def s_pit_001_triggered(d_principal, d_prudente, ci_lo: float, ci_hi: float) -> dict:
    """Regla operativa de S-PIT-001 para M2 (m2_structural_spec.md v1.2 §2): d = ll(M0) − ll(M2) en los MISMOS meses
    con la matriz principal y la prudente; se dispara si |media(d_prudente) − media(d_principal)| > (hi − lo)/2 del
    IC 95 % de mejora_logloss de M2 frente a M0 (matriz principal).
    v1.2 (Validador N-2): las dos series tienen que ser FINITAS en todos los meses, con la misma longitud y, si son
    pd.Series, con el MISMO índice (mismos meses, mismo orden). Si no: ValueError y se para (nunca intersección)."""
    if isinstance(d_principal, pd.Series) or isinstance(d_prudente, pd.Series):
        if not (isinstance(d_principal, pd.Series) and isinstance(d_prudente, pd.Series)):
            raise ValueError("S-PIT-001: las dos series deben venir con su índice de meses (pd.Series)")
        if not d_principal.index.equals(d_prudente.index):
            raise ValueError("S-PIT-001: las dos series no están alineadas por mes (índices distintos)")
    a, b = np.asarray(d_principal, float), np.asarray(d_prudente, float)
    if a.ndim != 1 or a.shape != b.shape or not len(a):
        raise ValueError("S-PIT-001: las dos series deben cubrir los mismos meses")
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        raise ValueError("S-PIT-001: d no finita en algún mes (NaN/inf): la regla no se puede aplicar")
    if not (np.isfinite(ci_lo) and np.isfinite(ci_hi)) or ci_hi < ci_lo:
        raise ValueError("S-PIT-001: IC no válido")
    delta, h = float(b.mean() - a.mean()), (float(ci_hi) - float(ci_lo)) / 2
    return {"delta": delta, "semiamplitud": h, "dispara": bool(abs(delta) > h), "n_meses": int(len(a))}


def s_pit_001_enmienda(d_principal: pd.Series, d_prudente: pd.Series, m0_principal: pd.Series,
                       m0_prudente: pd.Series, max_iniciales: int = 3) -> dict:
    """Enmienda 2026-10-25 de S-PIT-001 (m2_structural_spec.md §2): la corrida prudente puede no cubrir como mucho
    `max_iniciales` meses INICIALES consecutivos de `m2_long`. Entonces d^pr = d de `m2_long` restringida a los meses de
    la prudente y h = (hi − lo)/2 de `metrics.boot_mean(d^pr)` (mismo bootstrap que `mejora_logloss` del arnés). Antes,
    comprueba que el M0 de las dos corridas da las MISMAS pérdidas en los meses comunes (M0 no usa Filadelfia). En
    cualquier otro caso: ValueError y se para. Dentro de esos meses siguen las exigencias N-2 (`s_pit_001_triggered`)."""
    from src.models import metrics as M
    ss = (d_principal, d_prudente, m0_principal, m0_prudente)
    if not all(isinstance(s, pd.Series) for s in ss):
        raise ValueError("S-PIT-001 (enmienda): las cuatro series deben ser pd.Series indexadas por mes")
    if not all(s.index.is_monotonic_increasing and s.index.is_unique for s in ss):
        raise ValueError("S-PIT-001 (enmienda): índices no ordenados o con meses repetidos")
    if not (d_principal.index.equals(m0_principal.index) and d_prudente.index.equals(m0_prudente.index)):
        raise ValueError("S-PIT-001 (enmienda): d y M0 de una misma corrida con índices distintos")
    full, sub = d_principal.index, d_prudente.index
    if len(sub.difference(full)):
        raise ValueError("S-PIT-001 (enmienda): la corrida prudente puntúa meses que no están en m2_long")
    falta = full.difference(sub)
    k = len(falta)
    if k > max_iniciales or not falta.equals(full[:k]):
        raise ValueError(f"S-PIT-001 (enmienda): faltan {k} meses y no son los {max_iniciales} iniciales como mucho: "
                         f"{[f'{m:%Y-%m}' for m in falta]}")
    if not np.array_equal(m0_principal.loc[sub].to_numpy(float), m0_prudente.to_numpy(float)):
        raise ValueError("S-PIT-001 (enmienda): las pérdidas de M0 difieren entre m2_long y s_pit_001")
    dpr = d_principal.loc[sub]
    b = M.boot_mean(dpr.to_numpy(float))
    res = s_pit_001_triggered(dpr, d_prudente, b["lo"], b["hi"])
    return {**res, "meses_excluidos": [f"{m:%Y-%m}" for m in falta], "ic95_d_pr_restringida": [b["lo"], b["hi"]]}


def blp_transform(p, a: float, b: float, clip: float = POOL.clip) -> np.ndarray:
    """Recalibración beta del pool lineal (Ranjan-Gneiting 2010): P = B_{a,b}(p), función de distribución beta
    regularizada. a = b = 1 es la identidad. Recorte a [clip, 1 − clip] (pool_spec.md §3)."""
    from scipy.stats import beta
    p = np.clip(np.asarray(p, float), clip, 1 - clip)
    return np.clip(beta.cdf(p, a, b), clip, 1 - clip)


def declared_turns_8020(p, lo: float = 0.20, hi: float = 0.80, k: int = 3) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Regla de confirmación 3 m × 80/20 (m3_tvtp_spec.md §6; SOLO métrica secundaria). Estado declarado inicial = lado
    de p[0] (≥ 0,5 → 1 = G alto). Se declara G bajo en el k-ésimo mes seguido con p ≤ lo estando declarado alto, y G
    alto en el k-ésimo seguido con p ≥ hi estando declarado bajo. Devuelve (estado declarado por mes, [(índice, nuevo
    estado)])."""
    p = np.asarray(p, float)
    state = np.empty(len(p), int)
    if not len(p):
        return state, []
    cur, run, turns = int(p[0] >= 0.5), 0, []
    for i, x in enumerate(p):
        against = (x <= lo) if cur == 1 else (x >= hi)
        run = run + 1 if against else 0
        if run >= k:
            cur, run = 1 - cur, 0
            turns.append((i, cur))
        state[i] = cur
    return state, turns


class StructuralG(B.ContinuousAxisModel):
    """M2 `m2_struct_g` (ESQUELETO; m2_structural_spec.md). Eje G continuo: factor dinámico de 1 factor con ragged
    edge + composición exacta de Ĝ con el código de la etiqueta; σ̂² = V_filtro + V_rev + V_tend. Eje I = M0."""
    name = "m2_struct_g"
    continuous_axes = ("G",)
    axis_features = {"G": STRUCT.extra_features, "I": ()}
    uses_persistence = True
    uses_pit_levels = True
    spec = STRUCT

    def fit_axis_continuous(self, axis, X, g, t, w, info):
        raise NotImplementedError("m2_struct_g: esqueleto (m2_structural_spec.md v1.1); falta el arnés v2.4")

    def predict_axis_continuous(self, axis, X, info):
        raise NotImplementedError("m2_struct_g: esqueleto")

    def fit_axis(self, axis, X, t, w, info):
        raise NotImplementedError("m2_struct_g: esqueleto (eje I = M0)")

    def predict_axis(self, axis, X, info):
        raise NotImplementedError("m2_struct_g: esqueleto")


class TVTPG(B.AxisModel):
    """M3 `m3_tvtp_g` (ESQUELETO; m3_tvtp_spec.md). Markov de 2 estados del eje G definidos por la etiqueta, anclado en
    la persistencia PIT, emisión Ĝ en tiempo real de M2 templada (λ = 1/3), transiciones con γ ≥ 0, calibración Platt.
    `constant_transitions=True` da la referencia `m3_ctp_g`. Eje I = M0."""
    name = "m3_tvtp_g"
    axis_features = {"G": ("curve_min12", "baa_d6m", "eq_ret_6m", *STRUCT.extra_features), "I": ()}
    uses_persistence = True
    uses_pit_levels = True
    spec = TVTP

    def __init__(self, constant_transitions: bool = False):
        self.params = {"constant_transitions": constant_transitions}
        if constant_transitions:
            self.name = "m3_ctp_g"

    def fit_axis(self, axis, X, t, w, info):
        raise NotImplementedError(f"{self.name}: esqueleto (m3_tvtp_spec.md v1.1); falta el arnés v2.4")

    def predict_axis(self, axis, X, info):
        raise NotImplementedError(f"{self.name}: esqueleto")


class PoolG(B.AxisModel):
    """Pool `pool_g` (ESQUELETO; pool_spec.md). P = B_{a,b}(Σ w_k p_k) sobre las predicciones FUERA DE MUESTRA del eje G
    de M0, M2 y M3; MAP conjunto con previa de Dirichlet (moda ½, ¼, ¼; κ = 20) y lognormal en a, b; pool = M0 hasta
    N_min = 60 meses. Eje I = M0."""
    name = "pool_g"
    components = POOL.components
    axis_features = {"G": (), "I": ()}
    uses_persistence = True
    spec = POOL

    def fit_axis(self, axis, X, t, w, info):
        raise NotImplementedError("pool_g: esqueleto (pool_spec.md v1.1); falta el modelo apilado del arnés v2.4")

    def predict_axis(self, axis, X, info):
        raise NotImplementedError("pool_g: esqueleto")


REGISTRY: dict = {}      # vacío a propósito: nada de esto es ejecutable por el arnés todavía
