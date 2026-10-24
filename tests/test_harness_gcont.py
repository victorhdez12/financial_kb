"""Tests del eje G CONTINUO en el arnés (docs/models/harness.md §5c y §11 v2.3). Solo datos SINTÉTICOS (ArrayData):
ninguna etiqueta real, ningún modelo especificado (los modelos de aquí son de juguete y viven solo en este fichero).

- la transformación gaussiana: P(G alto) = Φ(μ/√(σ² + s_G²)) = E[Φ(G/s_G)] con G ~ N(μ, σ²) (Monte Carlo);
- CRPS gaussiano en forma cerrada frente a Monte Carlo;
- un modelo continuo corre en el arnés, sus probabilidades son exactamente la transformación de su (μ, σ), se combina
  con el eje I y se puntúa como M0 (log-loss, giros, falsas alarmas, retraso) + `report["g_continuo"]` (CRPS/RMSE);
- señal plantada: con G = f(x) + ruido, el modelo continuo bate a M0 y su RMSE es el del ruido; un oráculo de G con
  σ → 0 da CRPS ≈ 0 y la log-loss binaria mínima (la entropía del objetivo blando);
- sin señal (x = ruido) no inventa nada frente a M0;
- el objetivo continuo respeta el embargo (el modelo nunca ve G de meses > corte − 6) y es el de la etiqueta de
  entrenamiento (no el oficial);
- errores: sin columna G, σ ≤ 0, formas incorrectas;
- sin modelos continuos, las predicciones no tienen columnas nuevas y el informe no tiene `g_continuo` (por eso los
  hashes de las corridas previas no cambian; la reproducción bit a bit real está en la Bitácora del 23-oct).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from src.labels import regime_us as R
from src.models import base as B
from src.models import harness as H
from src.models import metrics as M
from src.models.metrics import P_COLS, QUADS

S_G = R.PARAMS.s_G_fixed


@pytest.fixture(autouse=True)
def trial_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("FKB_TRIALS_DIR", str(tmp_path / "trials"))
    monkeypatch.setenv("FKB_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("FKB_TRIAL_LOG", str(tmp_path / "trial_log.md"))


# ------------------------------------------------------------------ modelos de juguete (solo tests)
class ToyOLSG(B.ContinuousAxisModel):
    """G: MCO ponderado de G sobre x, σ = desviación residual; I: la calibración de M0."""
    name = "toy_ols_g"
    uses_persistence = True
    axis_features = {"G": ("x",), "I": ()}

    def __init__(self):
        self.m0 = B.CalibratedPersistence()
        self.seen = []

    def fit_axis_continuous(self, axis, X, g, t, w, info):
        self.seen.append((info["refit_month"], X.index.max(), np.asarray(g).copy(), X.index))
        Z = np.column_stack([np.ones(len(X)), X["x"].to_numpy(float)])
        W = np.asarray(w, float)
        self.b = np.linalg.solve(Z.T @ (Z * W[:, None]), Z.T @ (W * g))
        r = g - Z @ self.b
        self.sd = float(np.sqrt((W * r ** 2).sum() / W.sum()))

    def predict_axis_continuous(self, axis, X, info):
        mu = self.b[0] + self.b[1] * X["x"].to_numpy(float)
        return mu, np.full(len(X), self.sd)

    def fit_axis(self, axis, X, t, w, info):
        self.m0.fit_axis(axis, X, t, w, info)

    def predict_axis(self, axis, X, info):
        return self.m0.predict_axis(axis, X, info)


class Oracle(ToyOLSG):
    """Lee el G verdadero del mes (columna 'z_oraculo' de X, solo en tests) con σ casi 0."""
    name = "oracle_g"
    axis_features = {"G": ("z_oraculo",), "I": ()}

    def fit_axis_continuous(self, axis, X, g, t, w, info):
        pass

    def predict_axis_continuous(self, axis, X, info):
        return X["z_oraculo"].to_numpy(float), np.full(len(X), 1e-6)


class Bad(ToyOLSG):
    name = "bad_g"

    def __init__(self, how):
        super().__init__()
        self.how = how

    def predict_axis_continuous(self, axis, X, info):
        mu, sd = super().predict_axis_continuous(axis, X, info)
        if self.how == "sd0":
            return mu, sd * 0
        if self.how == "shape":
            return mu[:-1], sd
        return mu * np.nan, sd


REG = {**B.REGISTRY, "toy_ols_g": ToyOLSG, "oracle_g": Oracle}


def _synthetic(signal: bool = True, n_years: int = 40, seed: int = 3, with_g: bool = True) -> H.ArrayData:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1955-01-01", periods=12 * n_years, freq="MS")
    x = rng.normal(size=len(idx))
    base = np.sin(np.arange(len(idx)) / 9.0)                   # ciclo persistente (lo recoge la persistencia)
    g = 0.8 * base + (0.9 * x if signal else 0.0) + rng.normal(0, 0.3, len(idx))
    i = np.sin(np.arange(len(idx)) / 40.0 + 1)
    pg, pi = norm.cdf(g / S_G), norm.cdf((i - R.PARAMS.kappa) / R.PARAMS.s_I_fixed)
    T = M.combine_axes(pg, pi)
    tgt = pd.DataFrame(T, index=idx, columns=P_COLS)
    tgt["label_hard"] = np.array(QUADS)[T.argmax(1)]
    tgt["weight"], tgt["provisional"] = 1.0, False
    tgt["usrec"] = ((g < -0.5) & (np.roll(g, 1) >= -0.5)).astype(int)
    if with_g:
        tgt["G"], tgt["I"] = g, i
    X = pd.DataFrame({"x": x if signal else rng.normal(size=len(idx)), "z_oraculo": g}, index=idx)
    info = {c: {"estado": "principal", "start": idx[0]} for c in X.columns}
    return H.ArrayData(X, tgt, info, kind="synthetic")


def _cfg(models, **kw):
    return H.HarnessConfig(**{"name": "t", "models": models, "modes": ("synthetic",), "test_start": "1970-01",
                              "test_end": "1994-12", "refit_every": 12, "min_train_months": 120,
                              "min_train_recessions": 0, "min_train_g_changes": 0,
                              "baseline": "m0_calibrated_persistence", "reference": None, "epochs": (), **kw})


# ------------------------------------------------------------------ fórmulas
def test_gaussian_axis_prob_is_expected_soft_label():
    rng = np.random.default_rng(0)
    for mu, sd in ((0.3, 0.5), (-1.2, 0.2), (0.0, 1.0), (0.05, 1e-6)):
        gs = rng.normal(mu, sd, 400_000)
        assert B.gaussian_axis_prob(mu, sd, S_G) == pytest.approx(norm.cdf(gs / S_G).mean(), abs=2e-3)
    # con σ → 0 es exactamente la etiqueta blanda p_g_high = Φ(G/s_G); con centro (eje I) se desplaza
    assert B.gaussian_axis_prob(0.7, 0.0, S_G) == pytest.approx(norm.cdf(0.7 / S_G))
    assert B.gaussian_axis_prob(3.1, 0.0, 0.31, center=2.9) == pytest.approx(norm.cdf(0.2 / 0.31))


def test_gaussian_crps_closed_form_vs_monte_carlo():
    rng = np.random.default_rng(1)
    for mu, sd, y in ((0.0, 1.0, 0.5), (1.0, 0.3, -0.2), (-0.5, 2.0, -0.5)):
        a, b = rng.normal(mu, sd, 300_000), rng.normal(mu, sd, 300_000)
        mc = np.abs(a - y).mean() - 0.5 * np.abs(a - b).mean()
        assert B.gaussian_crps(mu, sd, y) == pytest.approx(mc, abs=5e-3)
    assert B.gaussian_crps(0.4, 1e-9, 0.4) == pytest.approx(0.0, abs=1e-8)


# ------------------------------------------------------------------ en el arnés
@pytest.fixture(scope="module")
def planted():
    import os
    import tempfile
    with tempfile.TemporaryDirectory() as d, pytest.MonkeyPatch().context() as mp:
        mp.setenv("FKB_TRIALS_DIR", os.path.join(d, "trials"))
        data = _synthetic(signal=True)
        r = H.run(_cfg(("m0_calibrated_persistence", "toy_ols_g", "oracle_g")), registry=REG,
                  datas={"synthetic": data}, record=False)
        yield data, r


def test_continuous_probs_are_transformation_of_mu_sd(planted):
    data, r = planted
    p = r["preds"]
    toy = p[p["model"] == "toy_ols_g"]
    assert {"g_mu", "g_sd"} <= set(p.columns)
    assert p.loc[p["model"] == "m0_calibrated_persistence", "g_mu"].isna().all()
    pg = toy[P_COLS].to_numpy() @ M.G_HIGH
    assert np.allclose(pg, B.gaussian_axis_prob(toy["g_mu"], toy["g_sd"], S_G), atol=1e-12)
    # el eje I del modelo continuo es el de M0 (producto de ejes): mismas P(I alta)
    m0 = p[p["model"] == "m0_calibrated_persistence"].set_index("month")
    t = toy.set_index("month")
    assert np.allclose(t[P_COLS].to_numpy() @ M.I_HIGH, m0.loc[t.index, P_COLS].to_numpy() @ M.I_HIGH)


def test_continuous_model_scored_like_m0_and_reports_crps(planted):
    data, r = planted
    rep = r["report"]
    key = "synthetic/toy_ols_g"
    for k in ("modelos", "frente_al_baseline", "deteccion_giros_g", "cortes_modelo", "calibracion"):
        assert key in rep[k], k
    c = rep["frente_al_baseline"][key]
    assert {"mejora_logloss", "mejora_ll_g", "cortes", "deteccion_frente_al_comparador"} <= set(c)
    assert "falsas_alarmas_por_año" in rep["deteccion_giros_g"][key]
    assert c["mejora_logloss"]["mean"] > 0.05 and c["mejora_logloss"]["lo"] > 0     # señal plantada: bate a M0
    gc = rep["g_continuo"]
    toy, orc = gc["G:synthetic/toy_ols_g"], gc["G:synthetic/oracle_g"]
    assert toy["n"] == rep["muestra"]["n"]                                          # mismos meses que la log-loss
    assert 0.55 < toy["rmse"] < 0.75     # el juguete solo usa x: residuo = √(0,8²·½ + 0,3²) ≈ 0,64
    assert 0.6 < toy["cobertura_80"] <= 0.95
    assert orc["crps"] < 1e-5 and orc["rmse"] < 1e-9
    assert "G:synthetic/toy_ols_g_frente_a_oracle_g" in gc
    assert "synthetic/m0_calibrated_persistence" not in {k.split(":", 1)[1] for k in gc}


def test_oracle_reaches_entropy_of_soft_target(planted):
    data, r = planted
    S = r["scores"]
    o = S[S["model"] == "oracle_g"].set_index("month")
    tg = data.target.loc[o.index, P_COLS].to_numpy() @ M.G_HIGH
    inner = (tg > 0.01) & (tg < 0.99)          # fuera, el recorte de 1e-4 de las métricas mueve la cola
    assert inner.mean() > 0.5
    assert np.allclose(o["ll_g"][inner], M.binary_logloss(tg, tg)[inner], atol=1e-6)


def test_continuous_target_respects_embargo_and_uses_training_label(planted):
    data, r = planted
    toy = ToyOLSG()
    cfg = _cfg(("m0_calibrated_persistence", "toy_ols_g"))
    H.walk_forward(_synthetic(signal=True), [toy], cfg)
    assert toy.seen
    for m0, last, g, months in toy.seen:
        assert last <= H._add(m0, -cfg.embargo_months)
        assert np.allclose(g, data.target.loc[months, "G"].to_numpy())   # G de la etiqueta de entrenamiento


def test_no_signal_no_skill():
    data = _synthetic(signal=False, seed=11)
    r = H.run(_cfg(("m0_calibrated_persistence", "toy_ols_g")), registry=REG, datas={"synthetic": data},
              record=False)
    c = r["report"]["frente_al_baseline"]["synthetic/toy_ols_g"]["mejora_logloss"]
    assert c["lo"] < 0 < c["hi"] or c["mean"] < 0.02


@pytest.mark.parametrize("how,match", [("sd0", "≤ 0"), ("shape", "devolvió"), ("nan", "no finito")])
def test_bad_continuous_predictions_rejected(how, match):
    reg = {**REG, "bad_g": lambda: Bad(how)}
    with pytest.raises(ValueError, match=match):
        H.run(_cfg(("m0_calibrated_persistence", "bad_g")), registry=reg, datas={"synthetic": _synthetic()}, record=False)


def test_missing_continuous_target_rejected():
    with pytest.raises(ValueError, match="no trae 'G'"):
        H.run(_cfg(("m0_calibrated_persistence", "toy_ols_g")), registry=REG, datas={"synthetic": _synthetic(with_g=False)}, record=False)


def test_without_continuous_models_nothing_changes():
    """Sin modelos continuos: ni columnas nuevas en las predicciones ni clave nueva en el informe; el hash es el de la
    misma corrida con los datos sin las columnas G/I de la etiqueta (que el arnés no lee si nadie las pide)."""
    cfg = _cfg(("m0_calibrated_persistence", "persistence_pit"))
    r1 = H.run(cfg, datas={"synthetic": _synthetic()}, record=False)
    r2 = H.run(cfg, datas={"synthetic": _synthetic(with_g=False)}, record=False)
    assert not {"g_mu", "g_sd", "i_mu", "i_sd"} & set(r1["preds"].columns)
    assert "g_continuo" not in r1["report"]
    assert r1["results_sha256"] == r2["results_sha256"]


def test_pitdata_axis_scale_matches_label_params():
    """La escala que usa el arnés con datos reales es la de la etiqueta congelada (sin leer la etiqueta)."""
    from src.features import pit as P
    lp = P.label_params()
    assert lp["s_G"] == pytest.approx(S_G)
    ad = _synthetic()
    assert ad.axis_scale("G") == (0.0, S_G)
    assert ad.axis_scale("I") == (R.PARAMS.kappa, R.PARAMS.s_I_fixed)
