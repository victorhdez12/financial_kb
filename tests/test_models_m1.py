"""Tests del entregable 4: M1 (logística por eje) y clasificador de reglas como `Model` (docs/models/m1_spec.md).

Solo mecánica: ningún test puntúa M1 ni las reglas contra la etiqueta oficial (los datos reales solo se usan con
`walk_forward`, que no puntúa; el resto es sintético).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models import base as B
from src.models import harness as H
from src.models import m1_run as MR
from src.models import models_logit as L
from src.models import models_rules as RU
from src.models.metrics import P_COLS, QUADS
from src.regime.classify import inflation_state


@pytest.fixture(scope="module", autouse=True)
def trial_dirs(tmp_path_factory):
    d = tmp_path_factory.mktemp("trials_m1")
    (d / "trial_log.md").write_text("| cabecera |\n")
    mp = pytest.MonkeyPatch()
    mp.setenv("FKB_TRIALS_DIR", str(d / "trials"))
    mp.setenv("FKB_RUNS_DIR", str(d / "runs"))
    mp.setenv("FKB_TRIAL_LOG", str(d / "trial_log.md"))
    yield d
    mp.undo()


# ------------------------------------------------------------------ logística penalizada
def test_penalized_logit_matches_base_with_constant_penalty():
    rng = np.random.default_rng(0)
    Z = rng.normal(size=(300, 3))
    t = 1 / (1 + np.exp(-(0.3 + Z @ [1.0, -0.5, 0.0])))
    w = rng.uniform(0.8, 1.0, 300)
    np.testing.assert_allclose(L.fit_binary_logit_pen(Z, t, w, np.full(3, 2.0)), B.fit_binary_logit(Z, t, w, 2.0),
                               atol=1e-5)


def _axis_frame(n=400, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1960-01-01", periods=n, freq="MS")
    X = pd.DataFrame(rng.normal(size=(n, 5)) * [1, 0.5, 2, 10, 1] + [0, 0.2, 2, 1, 1], index=idx, columns=list(L.M1_G))
    X[B.PERS_AXIS["G"]] = rng.uniform(0.05, 0.95, n)
    s = 0.5 * B.logit(X[B.PERS_AXIS["G"]].to_numpy(), 1e-3) + 1.0 * (X["growth_rt"] - 0) - 0.8 * (X["unrate_sahm"] - 0.2) / 0.5
    t = 1 / (1 + np.exp(-s.to_numpy()))
    return X, t


def test_m1_recovers_signs_and_nests_m0():
    X, t = _axis_frame()
    w = np.ones(len(X))
    m1 = L.LogitAxis(I=())
    m1.fit_axis("G", X, t, w, {})
    c = m1.coef_["G"]
    assert c["growth_rt"] > 0.5 and c["unrate_sahm"] < -0.5 and c["pers"] > 0
    big = L.LogitAxis(I=(), l2=1e6)               # variables anuladas por la L2 → M1 = M0 (mismo eps y L2 de b)
    big.fit_axis("G", X, t, w, {})
    m0 = B.CalibratedPersistence()
    m0.fit_axis("G", X, t, w, {})
    np.testing.assert_allclose(big.predict_axis("G", X, {}), m0.predict_axis("G", X, {}), atol=2e-4)


def test_m1_standardizes_with_training_rows_only():
    X, t = _axis_frame()
    m1 = L.LogitAxis(I=())
    m1.fit_axis("G", X.iloc[:200], t[:200], np.ones(200), {})
    mu, sd = m1._std["G"]
    np.testing.assert_allclose(mu, X.iloc[:200][list(L.M1_G)].mean().to_numpy())
    np.testing.assert_allclose(sd, X.iloc[:200][list(L.M1_G)].std(ddof=0).to_numpy())


def test_registry_names_and_spec():
    for name, f in MR.REGISTRY.items():
        assert f().name == name
    m1 = MR.REGISTRY["m1_logit_axis"]()
    assert m1.axis_features == {"G": L.M1_G, "I": ("core_cpi_6m_ann",)} and m1.params["l2"] == 6.0
    assert m1.params["l2_pers"] == 1.0 and m1.params["eps"] == 1e-3
    assert MR.REGISTRY["m1_logit_axis_hl"]().axis_features["I"] == ("headline_cpi_6m_ann",)


@pytest.mark.parametrize("path", ["config/harness/m1_logit_axis_v1.yaml", "config/harness/m1_logit_axis_v1_long.yaml",
                                  "config/harness/m1_logit_axis_v1_sens.yaml",
                                  "config/harness/m1_logit_axis_v1_long_sens.yaml",
                                  "config/harness/m1_logit_axis_v1_w_uno.yaml",
                                  "config/harness/m1_logit_axis_v1_w_excluir.yaml"])
def test_configs_load_and_are_development(path):
    cfg = H.HarnessConfig.from_yaml(H.REPO / path)
    cfg.validate()
    assert cfg.phase == "development" and cfg.test_end <= "2004-12"
    assert cfg.allow_shrink == path.endswith("w_excluir.yaml")
    assert cfg.baseline == "m0_calibrated_persistence" and all(m in MR.REGISTRY for m in cfg.models)
    assert cfg.eval_window[0] in ("1975-06", "1989-10")
    for m in H.build_models(cfg, MR.REGISTRY):
        assert m.name in cfg.models


# ------------------------------------------------------------------ reglas
def test_rules_inflation_uses_frozen_hysteresis():
    idx = pd.date_range("1980-01-01", periods=40, freq="MS")
    x = pd.Series(np.r_[np.linspace(1, 4, 20), np.linspace(4, 1.5, 20)], index=idx)
    H_ = pd.DataFrame({"growth_rt": 0.5, "unrate_sahm": 0.0, "headline_cpi_6m_ann": x}, index=idx)
    st = RU.rule_states(H_, "headline_cpi_6m_ann")
    exp = inflation_state(x, x - x.shift(3))
    assert list(st["I"]) == list(exp)


def test_rules_growth_translation():
    idx = pd.date_range("1980-01-01", periods=12, freq="MS")
    g = pd.Series([-1, -1, -1, -1, -1, -1, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5], index=idx, dtype=float)
    sahm = pd.Series(0.0, index=idx)
    sahm.iloc[-1] = 0.6
    H_ = pd.DataFrame({"growth_rt": g, "unrate_sahm": sahm, "headline_cpi_6m_ann": 3.0}, index=idx)
    st = RU.rule_states(H_, "headline_cpi_6m_ann")["G"]
    assert list(st.iloc[:6]) == ["down"] * 6                 # g < 0
    assert list(st.iloc[6:11]) == ["up"] * 5                 # g > 0 y Δ6 > 0 (los 6 primeros sin t−6: solo el signo)
    assert st.iloc[-1] == "down"                             # Sahm ≥ 0,5 manda


def test_rules_table_is_dirichlet_and_uses_memory():
    idx = pd.date_range("1970-01-01", periods=60, freq="MS")
    rng = np.random.default_rng(3)
    X = pd.DataFrame({"growth_rt": rng.normal(size=60), "unrate_sahm": 0.0,
                      "headline_cpi_6m_ann": rng.uniform(0, 6, 60)}, index=idx)
    Y = rng.dirichlet(np.ones(4), 60)
    r = RU.RulesClassifier()
    r.fit(X.iloc[:50], Y[:50], None, {})
    assert np.allclose(r.table_.sum(axis=1), 1) and (r.table_ > 0).all()
    s = RU.state_index(RU.rule_states(X.iloc[:50], "headline_cpi_6m_ann"))
    k = s[-1]
    np.testing.assert_allclose(r.table_[k], (Y[:50][s == k].sum(0) + 1) / ((s == k).sum() + 4))
    P = r.predict_proba(X.iloc[[55]], {})                  # 55: t−6 = 49 y t−3 = 52 (no visto) en la memoria
    full = RU.state_index(RU.rule_states(pd.concat([X.iloc[:50], X.iloc[[55]]]), "headline_cpi_6m_ann"))[-1]
    np.testing.assert_allclose(P[0], r.table_[full])


# ------------------------------------------------------------------ dentro del arnés
def _synthetic(n_years=40, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1955-01-01", periods=12 * n_years, freq="MS")
    g = np.sign(np.sin(np.arange(len(idx)) / 9.0))
    i = np.sign(np.sin(np.arange(len(idx)) / 40.0 + 1))
    pg, pi = 1 / (1 + np.exp(-2 * g)), 1 / (1 + np.exp(-2 * i))
    T = np.column_stack([pg * (1 - pi), pg * pi, (1 - pg) * pi, (1 - pg) * (1 - pi)])
    tgt = pd.DataFrame(T, index=idx, columns=P_COLS)
    tgt["label_hard"] = np.array(QUADS)[T.argmax(1)]
    tgt["weight"], tgt["provisional"] = 1.0, False
    tgt["usrec"] = ((g < 0) & (np.roll(g, 1) > 0)).astype(int)
    cols = {c: rng.normal(size=len(idx)) for c in L.M1_G + ("core_cpi_6m_ann", "headline_cpi_6m_ann")}
    cols["growth_rt"] = np.roll(g, -2) + rng.normal(0, 0.5, len(idx))
    X = pd.DataFrame(cols, index=idx)
    info = {c: {"estado": "principal", "start": idx[0]} for c in X.columns}
    return H.ArrayData(X, tgt, info, kind="synthetic")


def test_m1_and_rules_run_in_harness_without_leaks():
    data = _synthetic()
    seen = []

    def spy(model, info, X, Y):
        seen.append((model.name, info, list(X.columns)))

    cfg = H.HarnessConfig(name="t", models=("persistence_pit", "m0_calibrated_persistence", "m1_logit_axis",
                                            "rules_v1"),
                          modes=("synthetic",), test_start="1970-01", test_end="1994-12", refit_every=12,
                          min_train_months=120, min_train_recessions=0, min_train_g_changes=0,
                          baseline="m0_calibrated_persistence", reference="persistence_pit", epochs=())
    r = H.run(cfg, registry=MR.REGISTRY, datas={"synthetic": data}, record=False, spy=spy)
    for name, info, cols in seen:
        if len(info["train_months"]):
            assert info["train_months"].max() <= info["refit_month"] - pd.DateOffset(months=6)
        H.R.assert_no_forbidden(cols)
        if name == "m1_logit_axis":
            ax = info["axis"]
            assert cols == [*MR.REGISTRY[name]().axis_features[ax], B.PERS_AXIS[ax]]
        if name == "rules_v1":
            assert set(cols) == set(RU.RulesClassifier.features)
    rep = r["report"]
    assert rep["modelos"]["synthetic/m1_logit_axis"]["logloss"] < rep["modelos"]["synthetic/m0_calibrated_persistence"]["logloss"]
    p = r["preds"]
    assert np.allclose(p[P_COLS].sum(axis=1), 1)


def test_real_pit_columns_and_windows_spy_only():
    """Datos reales SIN puntuar (solo walk_forward): columnas, ventanas por eje y época del subyacente en las reglas."""
    pit = H.PITData("vintage")
    seen = []

    def spy(model, info, X, Y):
        seen.append((model.name, info.get("axis"), info["refit_month"], X.index.min(), list(X.columns)))

    cfg = H.HarnessConfig(name="t", models=("m0_calibrated_persistence", "m1_logit_axis", "m1_logit_axis_hl",
                                            "rules_v1"), modes=("vintage",), test_start="1986-06",
                          test_end="1990-06", refit_every=24, baseline="m0_calibrated_persistence", allow_shrink=True)
    H.walk_forward(pit, H.build_models(cfg, MR.REGISTRY), cfg, spy=spy)
    d = {(n, a, m): (s, c) for n, a, m, s, c in seen}
    t86, t88 = pd.Timestamp("1986-06-01"), pd.Timestamp("1988-06-01")
    assert ("m1_logit_axis", "I", t86) not in d and ("m1_logit_axis", "I", t88) in d   # subyacente: elegible en 1988-06
    assert d[("m1_logit_axis", "I", t88)][0] == pd.Timestamp("1978-01-01")
    assert d[("m1_logit_axis", "G", t86)][0] == pd.Timestamp("1963-11-01")
    assert "core_cpi_6m_ann" not in d[("rules_v1", None, t86)][1]
    assert "core_cpi_6m_ann" in d[("rules_v1", None, t88)][1] and d[("rules_v1", None, t88)][0] == pd.Timestamp("1978-01-01")


def test_rules_without_growth_rt_fall_back_to_climatology():
    """Corrección técnica post hoc (m1_spec.md §9): antes de que el arnés admita growth_rt, sin estado → climatología."""
    idx = pd.date_range("1960-01-01", periods=30, freq="MS")
    X = pd.DataFrame({"unrate_sahm": 0.0, "headline_cpi_6m_ann": 3.0}, index=idx)
    Y = np.tile([0.4, 0.3, 0.2, 0.1], (30, 1))
    r = RU.RulesClassifier()
    r.fit(X, Y, None, {})
    np.testing.assert_allclose(r.predict_proba(X.iloc[[-1]], {})[0], r.clim_)
