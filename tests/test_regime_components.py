"""Esqueleto de M2/M3/pool (src/models/regime_components.py): solo datos SINTÉTICOS. Ningún test lee la etiqueta,
la base PIT ni datos reales."""
import numpy as np
import pandas as pd
import pytest

from src.labels import regime_us as R
from src.models import regime_components as C


def _levels(n=200, seed=0):
    rng = np.random.default_rng(seed)
    r = 0.002 + 0.004 * rng.standard_normal(n)              # tasas log mensuales sintéticas
    idx = pd.date_range("1990-01-01", periods=n, freq="MS")
    return pd.Series(100 * np.exp(np.cumsum(r)), index=idx)


def test_label_pace_weights_match_label_params():
    p = R.PARAMS
    assert len(C.LABEL_PACE_WEIGHTS) == p.pace_lead + p.pace_lag + 2   # t−3 … t+4
    assert sum(C.LABEL_PACE_WEIGHTS) == 18
    # anualización: (2/3)·18 = 12 ⇒ una tasa mensual constante de x % da g = 12·x
    assert np.isclose(C.pace_rate_coeffs(1.0, 1).sum(), 12.0)


def test_linearized_pace_matches_label_code():
    """∂g_t/∂r_m del código de la etiqueta (R.pace) ≈ (2/3)·w (m2_structural_spec.md §4, V_filtro). Tolerancia 1 %:
    la media de 3 meses es de niveles, no de logaritmos (no linealidad declarada en la spec)."""
    lv = _levels()
    t = lv.index[100]
    g0 = R.pace(lv)[t]
    d = 0.01                                                 # perturbación de r en puntos porcentuales
    for k, off in enumerate(C.LABEL_PACE_OFFSETS):
        m = lv.index.get_loc(t) + off
        lv2 = lv.copy()
        lv2.iloc[m:] *= np.exp(d / 100)                      # sube r_m en d (y todos los niveles posteriores)
        dg = R.pace(lv2)[t] - g0
        assert np.isclose(dg / d, (2 / 3) * C.LABEL_PACE_WEIGHTS[k], rtol=1e-2), (off, dg / d)
    lv3 = lv.copy()
    lv3.iloc[lv.index.get_loc(t) + 5:] *= 1.1                # fuera de la ventana (t+5): no cambia g_t
    assert np.isclose(R.pace(lv3)[t], g0)


def test_blp_transform_identity_and_sharpening():
    p = np.linspace(0.01, 0.99, 50)
    assert np.allclose(C.blp_transform(p, 1.0, 1.0), p)
    q = C.blp_transform(p, 2.0, 2.0)                         # a = b > 1: más nítida (aleja de 0,5), simétrica
    assert np.all(np.diff(q) > 0)
    assert np.isclose(C.blp_transform(0.5, 2.0, 2.0), 0.5)
    assert C.blp_transform(0.7, 2.0, 2.0) > 0.7 and C.blp_transform(0.3, 2.0, 2.0) < 0.3
    assert C.blp_transform(0.0, 1.0, 1.0) >= C.POOL.clip and C.blp_transform(1.0, 1.0, 1.0) <= 1 - C.POOL.clip


def test_declared_turns_8020():
    p = [0.9, 0.9, 0.15, 0.1, 0.3, 0.1, 0.1, 0.1, 0.5, 0.85, 0.9, 0.95, 0.95]
    state, turns = C.declared_turns_8020(p)
    assert turns == [(7, 0), (11, 1)]                         # el 0,3 corta la racha; 3 meses ≤ 0,2 → bajo en 7
    assert list(state[:7]) == [1] * 7 and list(state[7:11]) == [0] * 4 and state[11] == 1
    s2, t2 = C.declared_turns_8020([0.4, 0.85, 0.85, 0.85])  # empieza bajo (< 0,5) y confirma alto en el 3.er mes
    assert t2 == [(3, 1)] and s2[0] == 0
    assert C.declared_turns_8020([])[1] == []


def test_spec_constants():
    assert np.isclose(sum(C.POOL.prior_mode), 1.0) and C.POOL.prior_mode[0] == 0.5
    assert C.POOL.n_min == 60 and C.POOL.kappa == 20 and C.POOL.embargo == 6
    assert C.POOL.components[0] == "m0_calibrated_persistence"
    assert C.TVTP.temper == pytest.approx(1 / 3) and C.TVTP.gamma_prior_sd == 0.5
    assert {v for v, _ in C.TVTP.exit_high + C.TVTP.exit_low} == {"curve_min12", "baa_d6m", "eq_ret_6m"}
    assert "baa_gap10y" not in str(C.TVTP) and "sahm_d3m" not in str(C.TVTP)
    s = C.STRUCT
    assert s.coincident == tuple(R.PARAMS.growth_ids)          # las 4 series de la etiqueta
    assert 6 * 1 + s.factor_order + 6 + 6 == s.n_params        # λ, φ, ρ, q


def test_skeletons_not_runnable_but_implementations_registered():
    """v2.4: el esqueleto de regime_components sigue sin ser ejecutable; las implementaciones están en
    models_struct.py, models_tvtp.py y models_pool.py y son las que registra el arnés."""
    from src.models import harness as H
    from src.models import models_pool, models_struct, models_tvtp
    reg = H.model_registry()
    assert reg["m2_struct_g"] is models_struct.StructuralG
    assert reg["m3_tvtp_g"] is models_tvtp.REGISTRY["m3_tvtp_g"] and reg["pool_g"] is models_pool.REGISTRY["pool_g"]
    for name in ("m3_ctp_g", "pool_g_eq", "pool_g_lin", "pool_g_kull", "pool_g_unif", "m2_struct_g_platt",
                 "m2_struct_g_norev", "m2_struct_g_revpit", "m2_struct_g_coinc", "m2_struct_g_ar1",
                 "m3_tvtp_g_l16", "m3_tvtp_g_l12", "m3_tvtp_g_fac", "m3_tvtp_g_nocal"):
        assert name in reg
    assert C.REGISTRY == {}
    assert C.TVTPG(constant_transitions=True).name == "m3_ctp_g"
    with pytest.raises(NotImplementedError):
        C.StructuralG().predict_axis_continuous("G", None, {})
    with pytest.raises(NotImplementedError):
        C.TVTPG().fit_axis("G", None, None, None, {})
    with pytest.raises(NotImplementedError):
        C.PoolG().predict_axis("G", None, {})


# --- v1.1 (2026-10-24): Estratega (peticiones de paro = flujo), Validador M-1, M-2, M-4, B-2, B-5 -------------------

def test_m2_v11_claims_loading_is_flow_and_state_dim_47():
    """x_c,m = λ_c·(f_m − f_{m−12}) = λ_c·Σ_{k=0..11} Δf_{m−k} (m2_structural_spec.md v1.1 §3); estado 47."""
    s = C.STRUCT
    assert s.claims_diff_lag == 12 and not hasattr(s, "claims_sum_months")
    assert s.state_dim == 13 + 4 * 8 + 2 == 47
    v = C.claims_factor_loading(-0.7)
    assert v.shape == (13,) and v[0] == -0.7 and v[12] == 0.7 and np.count_nonzero(v) == 2
    rng = np.random.default_rng(3)
    f = np.cumsum(rng.standard_normal(60))
    m = 40
    lags = f[m - np.arange(13)]                               # f_m, f_{m−1}, …, f_{m−12}
    assert np.isclose(v @ lags, -0.7 * np.diff(f)[m - 12:m].sum())
    # flujo frente a stock: al empezar una caída (f_m < 0 con f_{m−12} > 0) la tasa interanual de las peticiones es
    # claramente positiva con λ_c < 0; la media de 12 meses de la forma v1.0 seguiría ≈ positiva-pequeña.
    f2 = np.r_[np.ones(13), -np.ones(2)]
    assert C.claims_factor_loading(-1.0) @ f2[::-1][:13] > 1.5
    assert s.implementation.startswith("statsmodels") and s.warm_start is False
    assert s.rev_principal_is_pit is False and s.rev_var_sample == ("1968-06", "2004-12")


def test_gamma_fraction_criterion_threshold_strict_and_missing_fails():
    cuts = pd.period_range("2005-01", periods=10, freq="M").to_timestamp()
    g = pd.DataFrame({"G:gamma1": [0.3] * 10,
                      "G:gamma2": [0.02] * 5 + [0.0] * 5,                 # exactamente 50 % → cumple
                      "G:gamma3": [1e-10] * 6 + [0.011] * 4,             # residuo numérico no cuenta → 40 %
                      "G:gamma4": [0.01] * 10}, index=cuts)              # 0,01 exacto no cuenta (estricto)
    r = C.gamma_fraction_criterion(g, cuts)
    fu = r["fraccion_umbral"]
    assert fu["G:gamma1"]["frac"] == 1.0 and fu["G:gamma2"]["frac"] == 0.5
    assert fu["G:gamma3"]["frac"] == pytest.approx(0.4) and fu["G:gamma4"]["frac"] == 0.0
    assert r["criterio_fraccion_cumple"] is False
    ok = g.assign(**{"G:gamma3": 0.5, "G:gamma4": 0.5})
    assert C.gamma_fraction_criterion(ok, cuts)["criterio_fraccion_cumple"] is True
    # un corte sin coeficientes cuenta como no cumplido (denominador = cortes de la ventana)
    half = ok.assign(**{"G:gamma2": [0.02] * 5 + [0.0] * 5}).iloc[1:]
    r2 = C.gamma_fraction_criterion(half, cuts)
    assert r2["fraccion_umbral"]["G:gamma2"]["n_sin_coef"] == 1
    assert r2["fraccion_umbral"]["G:gamma2"]["frac"] == pytest.approx(0.4) and r2["criterio_fraccion_cumple"] is False
    # con γ ≥ 0 impuesto, el criterio de expected_signs (signo de la media) se cumpliría aun con 1 corte > 0
    trivial = g.assign(**{"G:gamma3": [0.0] * 9 + [1e-9]})
    assert np.sign(trivial["G:gamma3"].mean()) == 1
    assert C.gamma_fraction_criterion(trivial, cuts)["fraccion_umbral"]["G:gamma3"]["frac"] == 0.0
    assert C.TVTP.sign_window == ("2005-01", "2021-10") and C.TVTP.sign_threshold == 0.01


def test_s_pit_001_rule():
    rng = np.random.default_rng(1)
    d = rng.standard_normal(300) * 0.3
    r = C.s_pit_001_triggered(d, d + 0.01, ci_lo=-0.02, ci_hi=0.06)      # h = 0,04 > 0,01 → no
    assert r["dispara"] is False and np.isclose(r["delta"], 0.01) and np.isclose(r["semiamplitud"], 0.04)
    assert C.s_pit_001_triggered(d, d - 0.05, -0.02, 0.06)["dispara"] is True   # en cualquier sentido
    with pytest.raises(ValueError):
        C.s_pit_001_triggered(d, d[:-1], -0.02, 0.06)


def test_m3_optimizer_constants_fixed():
    assert C.TVTP.opt_maxiter == 500 and C.TVTP.opt_gtol == 1e-8
    assert C.TVTP.sign_coefs == ("G:gamma1", "G:gamma2", "G:gamma3", "G:gamma4")


def test_s_pit_001_requires_finite_aligned_series():
    """Validador N-2: con un NaN la regla no puede "no dispararse" en silencio; índices distintos → error."""
    idx = pd.period_range("1980-01", periods=50, freq="M").to_timestamp()
    d = pd.Series(np.zeros(50), index=idx)
    bad = d - 1.0
    bad.iloc[3] = np.nan                                                  # Δ real = −1 nat con un NaN
    with pytest.raises(ValueError):
        C.s_pit_001_triggered(d, bad, -0.02, 0.06)
    with pytest.raises(ValueError):
        C.s_pit_001_triggered(d.to_numpy(), bad.to_numpy(), -0.02, 0.06)
    with pytest.raises(ValueError):                                       # mismos valores, meses desplazados
        C.s_pit_001_triggered(d, pd.Series(d.to_numpy(), index=idx + pd.DateOffset(months=1)), -0.02, 0.06)
    with pytest.raises(ValueError):
        C.s_pit_001_triggered(d, d.to_numpy(), -0.02, 0.06)
    with pytest.raises(ValueError):
        C.s_pit_001_triggered(d, d, float("nan"), 0.06)
    r = C.s_pit_001_triggered(d, d - 1.0, -0.02, 0.06)
    assert r["dispara"] is True and r["n_meses"] == 50
