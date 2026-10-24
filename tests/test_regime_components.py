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


def test_skeletons_not_runnable_nor_registered():
    from src.models import harness as H
    reg = H.model_registry()
    for name in ("m2_struct_g", "m3_tvtp_g", "m3_ctp_g", "pool_g"):
        assert name not in reg
    assert C.REGISTRY == {}
    assert C.TVTPG(constant_transitions=True).name == "m3_ctp_g"
    with pytest.raises(NotImplementedError):
        C.StructuralG().predict_axis_continuous("G", None, {})
    with pytest.raises(NotImplementedError):
        C.TVTPG().fit_axis("G", None, None, None, {})
    with pytest.raises(NotImplementedError):
        C.PoolG().predict_axis("G", None, {})
