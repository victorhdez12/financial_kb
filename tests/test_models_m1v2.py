"""Tests de M1 v2 (docs/models/m1_v2_spec.md; H-M1-002). SOLO datos sintéticos: ningún test corre M1 v2 con la etiqueta
real (la especificación se commitea antes de cualquier corrida con la etiqueta).

- el eje I estructural no estima la pendiente (offset fijo 1,7·(x − 2,9)/s) y solo ajusta constante y persistencia;
- con la pendiente correcta y sin señal en la persistencia, recupera constante ≈ 0 y b ≈ 0;
- `m1v2_g` tiene el eje I de M0 exactamente; el eje G anida a M0 (sin variables = M0);
- sin offset y con pen constante, `fit_binary_logit_pen` sigue igual (M1 v1 bit a bit);
- nombres, variables, signos y parámetros preregistrados; configuraciones válidas, en desarrollo y sobre la v0.4;
- una base PIT candidata no sirve para la evaluación única (la v0.4 está congelada desde el 23-oct).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models import base as B
from src.models import harness as H
from src.models import models_logit as L
from src.models import vault as V
from tests.real_data import requires_real_data


def _frame(n=400, seed=0):
    rng = np.random.default_rng(seed)
    X = pd.DataFrame({"pers_axis_infl": rng.uniform(0.05, 0.95, n), "pers_axis_growth": rng.uniform(0.05, 0.95, n),
                      "core_cpi_6m_ann": rng.normal(3.0, 1.5, n), **{c: rng.normal(size=n) for c in L.M2_G}})
    return X, rng


def test_registry_and_spec():
    reg = H.model_registry()
    for k in ("m1v2_logit_axis", "m1v2_logit_axis_s050", "m1v2_logit_axis_s100", "m1v2_g"):
        assert k in reg
    m = reg["m1v2_logit_axis"]()
    assert m.axis_features == {"G": L.M2_G, "I": ("core_cpi_6m_ann",)}
    assert m.structural == {"I": ("core_cpi_6m_ann", 1.7, 2.9, 0.75)}
    assert "unrate_sahm" not in L.M2_G and "curve_10y3m" not in L.M2_G and "baa_spread" not in L.M2_G
    assert reg["m1v2_logit_axis_s050"]().structural["I"][3] == 0.5
    assert reg["m1v2_logit_axis_s100"]().structural["I"][3] == 1.0
    g = reg["m1v2_g"]()
    assert g.axis_features["I"] == () and g.structural == {}
    signs = {"growth_rt": 1, "claims_4w_yoy": -1, "curve_min12": 1, "baa_gap10y": -1, "baa_d6m": -1, "eq_ret_6m": 1,
             "sahm_d3m": -1}
    assert {k: L.EXPECTED_SIGN[k] for k in signs} == signs
    assert (L.L2_FEATURES, L.L2_PERS, L.EPS) == (6.0, 1.0, 1e-3)


def test_structural_I_offset_fixed_and_identified():
    X, rng = _frame()
    off = 1.7 * (X["core_cpi_6m_ann"] - 2.9) / 0.75
    t = 1 / (1 + np.exp(-off))                      # objetivo blando generado SOLO por el offset
    m = L.LogitAxisV2()
    m.fit_axis("I", X, t.to_numpy(), np.ones(len(X)), {})
    c = m.coef_["I"]
    assert set(c) == {"const", "pers", "core_cpi_6m_ann"}
    assert abs(c["const"]) < 0.05 and abs(c["pers"]) < 0.05
    assert c["core_cpi_6m_ann"] == pytest.approx(1.7 / 0.75)          # publicado, no estimado
    np.testing.assert_allclose(m.predict_axis("I", X, {}), t, atol=0.02)
    # la pendiente NO se mueve aunque el objetivo pida otra (solo se ajustan const y pers)
    t2 = 1 / (1 + np.exp(-3 * off))
    m.fit_axis("I", X, t2.to_numpy(), np.ones(len(X)), {})
    assert m.coef_["I"]["core_cpi_6m_ann"] == pytest.approx(1.7 / 0.75)


def test_offset_none_keeps_v1_fit_bit_identical():
    X, rng = _frame()
    Z = X[["pers_axis_growth", "growth_rt"]].to_numpy()
    t = rng.uniform(size=len(X))
    w = rng.uniform(0.5, 1, len(X))
    pen = np.array([1.0, 6.0])
    np.testing.assert_array_equal(L.fit_binary_logit_pen(Z, t, w, pen), L.fit_binary_logit_pen(Z, t, w, pen, None))
    np.testing.assert_allclose(L.fit_binary_logit_pen(Z, t, w, np.array([2.0, 2.0])),
                               B.fit_binary_logit(Z, t, w, 2.0), atol=1e-6)


def test_m1v2_g_axis_I_equals_M0():
    X, rng = _frame()
    t = rng.uniform(size=len(X))
    w = np.ones(len(X))
    g, m0 = L.REGISTRY["m1v2_g"](), B.CalibratedPersistence()
    g.fit_axis("I", X, t, w, {})
    m0.fit_axis("I", X, t, w, {})
    np.testing.assert_allclose(g.predict_axis("I", X, {}), m0.predict_axis("I", X, {}), atol=1e-6)
    # eje G sin variables = M0 (anida)
    g0 = L.LogitAxisV2(name="x", G=(), I=(), i_structural=False)
    g0.fit_axis("G", X, t, w, {})
    m0.fit_axis("G", X, t, w, {})
    np.testing.assert_allclose(g0.predict_axis("G", X, {}), m0.predict_axis("G", X, {}), atol=1e-6)


def test_G_axis_recovers_planted_signs():
    X, rng = _frame(n=2000, seed=3)
    true = {"growth_rt": 1.0, "claims_4w_yoy": -0.8, "curve_min12": 0.6, "baa_gap10y": -0.6, "baa_d6m": -0.5,
            "eq_ret_6m": 0.4, "sahm_d3m": -0.7}
    s = sum(v * X[k] for k, v in true.items())
    t = (rng.uniform(size=len(X)) < 1 / (1 + np.exp(-s))).astype(float)
    m = L.LogitAxisV2()
    m.fit_axis("G", X, t, np.ones(len(X)), {})
    assert all(np.sign(m.coef_["G"][k]) == np.sign(v) for k, v in true.items())


@pytest.mark.parametrize("name", ["m1v2_principal", "m1v2_long", "m1v2_sens"])
def test_configs_valid_dev_only_on_v04(name):
    cfg = H.HarnessConfig.from_yaml(H.REPO / "config" / "harness" / f"{name}.yaml")
    cfg.validate()
    assert cfg.pit_version == "0.4" and cfg.phase == "development" and not cfg.allow_shrink
    assert cfg.baseline == "m0_calibrated_persistence"
    assert H._month(cfg.window[1]) < V.HOLDOUT_START
    models = H.build_models(cfg)
    assert any(m.name.startswith("m1v2") for m in models)


def test_candidate_pit_not_allowed_in_holdout(monkeypatch):
    """Una base PIT candidata (aquí una versión ficticia 9.4; la v0.4 se congeló el 23-oct) no sirve para la evaluación."""
    assert "0.4" in H.P.FROZEN
    monkeypatch.setitem(H.MATRIX_SHA256_BY_VERSION, "9.4", dict(H.MATRIX_SHA256_BY_VERSION["0.4"]))
    with pytest.raises(V.HoldoutLocked, match="congelada"):
        H.HarnessConfig(name="x", phase="holdout_evaluation", pit_version="9.4", test_end="2021-10",
                        prereg_id="P-EVAL-X").validate()
    with pytest.raises(V.HoldoutLocked, match="congelada"):
        H.PITData("vintage", phase="holdout_evaluation", prereg_id="P-EVAL-X", pit_version="9.4")
    with pytest.raises(ValueError, match="desconocida"):
        H.HarnessConfig(name="x", pit_version="9.9").validate()


@requires_real_data
def test_dry_run_flags_candidate_pit_before_spending(tmp_path, monkeypatch):
    """Una configuración de evaluación con una base PIT candidata la rechaza el ensayo en seco (que `_preflight` repite
    ANTES de abrir la caja): nunca llega a `_run` con el preregistro ya consumido. La v0.4 congelada ya no se rechaza."""
    import yaml
    monkeypatch.setitem(H.MATRIX_SHA256_BY_VERSION, "9.4", dict(H.MATRIX_SHA256_BY_VERSION["0.4"]))
    d = {"name": "x", "prereg_id": "P-EVAL-X", "phase": "holdout_evaluation", "pit_version": "9.4",
         "principal": "m1v2_logit_axis", "models": ["m1v2_logit_axis", "m0_calibrated_persistence"],
         "modes": ["vintage"], "test_start": "1978-07", "test_end": "2021-10", "eval_window": ["2005-01", "2021-10"],
         "baseline": "m0_calibrated_persistence", "dry_run_window": ["1995-01", "2004-12"]}
    cfg = H.HarnessConfig(**{**d, "models": tuple(d["models"]), "modes": tuple(d["modes"]),
                             "eval_window": tuple(d["eval_window"]), "dry_run_window": tuple(d["dry_run_window"])})
    errs = H._check_eval_config(cfg, "P-EVAL-X", None)
    assert any("no está congelada" in e for e in errs)
    for ok_version in ("0.3", "0.4"):
        assert not any("no está congelada" in e for e in H._check_eval_config(
            H.HarnessConfig(**{**cfg.__dict__, "pit_version": ok_version}), "P-EVAL-X", None))
