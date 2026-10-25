"""Tests del arnés walk-forward (docs/models/harness.md §9). Solo meses ≤ 2004 de la etiqueta oficial.

(1) reproducción del listón: la persistencia PIT del arnés = baselines congelados de la base PIT v0.3, bit a bit, y sus
    métricas (vintage 61,14 % / 1,2997; latest_truncated 63,04 % / 1,1824; 579 meses);
(2) fuga de etiqueta: el modelo entrena con la etiqueta RECALCULADA con datos ≤ T (no con la final), nunca recibe meses
    posteriores a T − embargo, y una columna con la etiqueta (o cualquier columna fuera de la matriz congelada) es
    imposible de meter; con datos de placebo, una variable con la etiqueta FUTURA se detecta;
(3) embargo: mínimo 6 meses (menos se rechaza) y aplicado en cada corte;
(4) placebo PAREADO (v2): etiqueta barajada en bloques de 24 meses, 20 permutaciones; control t−5 sin fuga, fuga débil
    de t + 1 detectada;
(5) reproducibilidad: misma config → mismo hash de resultados;
(6) periodo bloqueado ≥ 2005-01: la caja fuerte no decodifica filas ≥ 2005, deniega y registra; la evaluación única
    exige preregistro + confirmación y es de un solo uso;
(7) registro de pruebas automático; política de variables (principal_desde_efectivo, condicionales, épocas).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.features import pit as P
from src.labels import regime_us as R
from src.models import base as B
from src.models import harness as H
from src.models import vault as V
from src.models.metrics import P_COLS
from tests.real_data import requires_real_data

pytestmark = requires_real_data

HOLDOUT = pd.Timestamp(R.PARAMS.holdout_start)
LISTON = {"vintage": (0.6113989637305699, 1.299697368353707),
          "latest_truncated": (0.6303972366148531, 1.1824229051402468)}


@pytest.fixture(scope="module", autouse=True)
def trial_dirs(tmp_path_factory):
    """Registro de pruebas, artefactos y trial log de los tests en un directorio temporal (no ensucian research/)."""
    d = tmp_path_factory.mktemp("trials")
    (d / "trial_log.md").write_text("| cabecera |\n")
    mp = pytest.MonkeyPatch()
    mp.setenv("FKB_TRIALS_DIR", str(d / "trials"))
    mp.setenv("FKB_RUNS_DIR", str(d / "runs"))
    mp.setenv("FKB_TRIAL_LOG", str(d / "trial_log.md"))
    mp.delenv(V.UNLOCK_ENV, raising=False)
    yield d
    mp.undo()


@pytest.fixture(scope="module")
def datas():
    return {m: H.PITData(m) for m in P.MODES}


def C(**kw):
    """Configuración de prueba con los mínimos de entrenamiento de la v1 (12 meses, sin recesiones ni cambios de G),
    para que los tests de mecánica no dependan de la regla de §5 (que tiene sus propios tests)."""
    return H.HarnessConfig(**{"min_train_months": 12, "min_train_recessions": 0, "min_train_g_changes": 0, **kw})


@pytest.fixture(scope="module")
def res(datas):
    """Los baselines de la v1 (persistencia y climatología, min_train 12) sobre la muestra completa 1956-10 → 2004-12."""
    return H.run(C(name="baselines_v1_equiv", models=("persistence_pit", "climatology"),
                   model_params={"climatology": {"alpha": 1.0}}), datas=datas)


# ------------------------------------------------------------------ modelos de prueba (no son aspirantes)
class Spy(B.Model):
    """Registra lo que recibe en cada fit; predice uniforme."""
    name = "spy"

    def __init__(self, features=(), uses_persistence=False):
        self.features, self.uses_persistence, self.calls = features, uses_persistence, []

    def fit(self, X, Y, y, info, sample_weight=None):
        self.calls.append({"m0": info["refit_month"], "T": info["decision_date"], "months": X.index, "Y": Y,
                           "cols": list(X.columns), "w": sample_weight})

    def predict_proba(self, X, info):
        return np.full((len(X), 4), 0.25)


def spy_run(data, cfg, model):
    H.walk_forward(data, [model], cfg)
    return model.calls


# ------------------------------------------------------------------ (1) listón
@pytest.mark.parametrize("mode", P.MODES)
def test_persistence_equals_frozen_baseline(datas, mode):
    """La persistencia del arnés (última fila de la etiqueta recalculada en t) = baseline congelado v0.3, bit a bit."""
    f = P.out_dir() / f"baseline_persistence_v{H.PIT_VERSION}_{mode}.parquet"
    ref = pd.read_parquet(f, filters=[("decision_date", "<", HOLDOUT.to_datetime64())]).set_index("month")
    mine = datas[mode].persistence_frame().loc[ref.index]
    assert len(ref) > 570
    assert (mine["pers_hard"].to_numpy() == ref["pers_hard"].to_numpy()).all()
    assert (mine["label_month"].to_numpy() == ref["label_month"].to_numpy()).all()
    np.testing.assert_array_equal(mine[B.PERS_COLS].to_numpy(), ref[B.PERS_COLS].to_numpy())


def test_liston_reproduced(res):
    rep = res["report"]
    assert rep["muestra"] == {"n": 579, "desde": "1956-10", "hasta": "2004-12"}
    for mode, (acc, ll) in LISTON.items():
        for got in (rep["persistencia_muestra_completa"][mode], rep["modelos"][f"{mode}/persistence_pit"]):
            assert got["n"] == 579
            assert got["acierto"] == pytest.approx(acc, abs=1e-12)
            assert got["logloss"] == pytest.approx(ll, abs=1e-12)


def test_both_modes_scored_on_same_months(res):
    S = res["scores"]
    months = {k: set(g["month"]) for k, g in S.groupby(["mode", "model"])}
    assert len(months) == 4 and len({frozenset(v) for v in months.values()}) == 1
    assert S["month"].max() < HOLDOUT


# ------------------------------------------------------------------ (2) fuga de etiqueta
def test_training_labels_recomputed_with_data_up_to_T(datas):
    """Cada fit recibe la etiqueta recalculada con los datos conocidos en T (no la final) y nada posterior a T − 6."""
    d = datas["vintage"]
    cfg = C(name="t", models=("persistence_pit",), test_start="1978-01", test_end="1985-12", refit_every=12)
    calls = spy_run(d, cfg, Spy())
    official = d.score_labels("2004-12")
    differs = 0
    for c in calls:
        assert c["months"].max() <= c["m0"] - pd.DateOffset(months=6)
        assert c["months"].max() + pd.DateOffset(months=H.LABEL_FORWARD) < c["m0"]
        pit = d.labeler.at(c["T"]).set_index("date").loc[c["months"], P_COLS].to_numpy()
        np.testing.assert_array_equal(c["Y"], pit)
        differs += int(np.abs(c["Y"] - official.loc[c["months"], P_COLS].to_numpy()).max() > 1e-6)
    assert len(calls) == 8 and differs == len(calls)   # la etiqueta final nunca coincide: no es la que se usa


def test_label_columns_cannot_enter(datas):
    d = datas["vintage"]
    cfg = C(name="t", models=("persistence_pit",), test_start="1990-01", test_end="1990-06")
    for cols in (("label_hard",), ("p_expansion",), ("usrec",), ("G",), ("xyz_future",)):
        with pytest.raises(KeyError):
            H.walk_forward(d, [Spy(features=cols)], cfg)
    with pytest.raises(AssertionError):
        R.assert_no_forbidden(["p_expansion_lag5", "usrec_lag1"])
    R.assert_no_forbidden(B.PERS_COLS)        # las predicciones de persistencia no chocan con la lista negra
    with pytest.raises(ValueError):
        H.ArrayData(d.X, d.score_labels("2004-12"), d.colinfo, kind="pit")


def test_tampered_matrix_rejected(tmp_path, monkeypatch):
    """Una matriz con una columna añadida (p. ej. la etiqueta renombrada) no pasa el hash congelado."""
    name = f"pit_us_v{H.PIT_VERSION}_vintage.parquet"
    X = pd.read_parquet(P.out_dir() / name)
    X["rumor"] = 0.0
    X.to_parquet(tmp_path / name, index=False)
    monkeypatch.setattr(P, "out_dir", lambda: tmp_path)
    with pytest.raises(RuntimeError, match="no coincide"):
        H.PITData("vintage")


@pytest.mark.parametrize("case,leak_expected", [("control_t-5_sin_fuga", False), ("futura_t+1_sd1", True)])
def test_placebo_paired_specific_and_powerful(datas, case, leak_expected):
    """(4) Placebo PAREADO (M-5; src/models/placebo.py, regla fijada antes de correr la tabla): etiqueta ≤ 2004 barajada
    en bloques de 24, 20 permutaciones, base con la persistencia blanda y dura. El control t−5 (la persistencia en
    forma dura: SIN fuga) no se marca como fuga; la etiqueta de t + 1 con ruido σ = 1 (fuga débil, que la regla
    absoluta de la v1 dejaba pasar) sí."""
    from src.models import placebo as PL
    r = PL.evaluate(datas["vintage"], PL.CASES[case])
    assert r["n_semillas"] == PL.N_SEEDS == 20
    assert r["fuga_detectada"] is leak_expected, r


# ------------------------------------------------------------------ (3) embargo
def test_embargo_minimum_and_applied(datas):
    with pytest.raises(ValueError, match="embargo"):
        H.HarnessConfig(name="t", embargo_months=3).validate()
    cfg = C(name="t", models=("persistence_pit",), test_start="1990-01", test_end="1991-12",
            refit_every=3, embargo_months=9)
    calls = spy_run(datas["latest_truncated"], cfg, Spy())
    assert len(calls) == 8
    for c in calls:
        assert c["months"].max() == c["m0"] - pd.DateOffset(months=9)


def test_refit_every_and_predictions_use_cut_model(datas):
    cfg = C(name="t", models=("persistence_pit", "climatology"), modes=("vintage",),
            test_start="1990-01", test_end="1991-12", refit_every=6)
    preds, _ = H.walk_forward(datas["vintage"], H.build_models(cfg), cfg)
    c = preds[preds["model"] == "climatology"]
    assert sorted(c["refit_month"].unique()) == list(pd.date_range("1990-01-01", periods=4, freq="6MS"))
    assert ((c["month"] - c["refit_month"]).dt.days < 190).all() and (c["month"] >= c["refit_month"]).all()
    assert c.groupby("refit_month")[P_COLS].nunique().max().max() == 1   # un modelo por corte


# ------------------------------------------------------------------ (7) política de variables
def test_feature_policy_principal_desde_and_conditionals(datas):
    d = datas["vintage"]
    cfg = C(name="t", models=("persistence_pit",), test_start="1975-01", test_end="2004-12", refit_every=60)
    spy = Spy(features="principal")
    calls = spy_run(d, cfg, spy)
    by = {c["m0"].year: c for c in calls}
    cond = {c for c, i in d.colinfo.items() if i["estado"] in ("condicional", "modulo_adicional")}
    for c in calls:
        assert not cond & set(c["cols"])
        for col in c["cols"]:
            st = d.colinfo[col]["start"]
            assert c["months"].min() >= st
            pd_ef = d.colinfo[col]["principal_desde_efectivo"]
            assert pd_ef is None or c["months"].min() >= pd.Timestamp(pd_ef)
    assert "core_cpi_6m_ann" not in by[1975]["cols"] and "infl_energy_pressure" not in by[1975]["cols"]
    assert "core_cpi_6m_ann" in by[1990]["cols"] and "tcu_gap" in by[1990]["cols"]
    assert "vix" not in by[2000]["cols"]
    with pytest.raises(ValueError, match="no admitidas"):
        spy_run(d, cfg, Spy(features=("core_pce_6m_ann",)))
    sens = H.PITData("vintage", policy="sensibilidad")
    c90 = spy_run(sens, C(name="t", models=("persistence_pit",), test_start="1990-01",
                          test_end="1990-01", feature_policy="sensibilidad"),
                  Spy(features=("core_pce_6m_ann",)))
    assert c90[0]["cols"] == ["core_pce_6m_ann"]


def test_sign_stability_utility(datas):
    br = H.vintage_breaks(datas["vintage"])
    assert br["core_cpi_6m_ann"] == [pd.Timestamp("1996-12-01")]
    assert pd.Timestamp("1981-05-01") in br["growth_rt"]
    idx = pd.date_range("1990-01-01", periods=180, freq="MS")
    coefs = pd.DataFrame({"core_cpi_6m_ann": np.where(idx < "1996-12-01", 1.0, -1.0)}, index=idx)
    out = H.sign_stability(coefs, br)
    assert len(out) == 1 and not out["mismo_signo"].iloc[0]


# ------------------------------------------------------------------ (5) reproducibilidad y (7) registro
def test_reproducible_same_config_same_hash():
    cfg = C(name="repro", modes=("vintage",), test_start="1995-01", test_end="1999-12", refit_every=3)
    a = H.run(cfg, datas={"vintage": H.PITData("vintage")}, record=False)
    b = H.run(cfg, datas={"vintage": H.PITData("vintage")}, record=False)
    assert a["results_sha256"] == b["results_sha256"]
    c = H.run(C(name="repro", modes=("vintage",), test_start="1995-01", test_end="1999-12",
                refit_every=6), datas={"vintage": H.PITData("vintage")}, record=False)
    assert c["results_sha256"] != a["results_sha256"]


def test_trial_registry_written(res, trial_dirs):
    lines = [json.loads(x) for x in (trial_dirs / "trials" / "harness_runs.jsonl").read_text().splitlines()]
    e = next(x for x in lines if x["run_id"] == res["entry"]["run_id"])
    assert e["results_sha256"] == res["results_sha256"] and e["kind"] == ["pit"] and e["phase"] == "development"
    assert e["code"]["src_models"] and e["data"]["vintage"]["matrix"]
    assert res["entry"]["run_id"] in (trial_dirs / "trial_log.md").read_text()
    assert (trial_dirs / "runs" / e["run_id"] / "predictions.parquet").exists()


# ------------------------------------------------------------------ (6) periodo bloqueado
def test_vault_development_never_decodes_holdout(monkeypatch, trial_dirs):
    seen = {}
    real = pd.read_parquet

    def spy(path, *a, **k):
        seen["filters"] = k.get("filters")
        return real(path, *a, **k)

    monkeypatch.setattr(V.pd, "read_parquet", spy)
    v = V.LabelVault()
    df = v.load()
    assert seen["filters"] == [("date", "<", HOLDOUT.to_datetime64())]
    assert df.index.max() < HOLDOUT and len(df) == 660
    for end in ("2005-01", "2015-06"):
        with pytest.raises(V.HoldoutLocked):
            v.load(end=end)
    log = [json.loads(x) for x in (trial_dirs / "trials" / "label_access.jsonl").read_text().splitlines()]
    assert any(not x["granted"] and "2015-06" in x["why"] for x in log)
    assert any(x["granted"] and x["hasta"] == "2004-12" for x in log)


def test_harness_refuses_holdout(datas):
    with pytest.raises(V.HoldoutLocked):
        H.HarnessConfig(name="t", test_end="2005-01").validate()
    assert all(d.X.index.max() < HOLDOUT for d in datas.values())   # ni siquiera las variables ≥ 2005
    lab = datas["vintage"].score_labels("2004-12")
    idx = pd.date_range("1990-01-01", "2006-12-01", freq="MS")
    t = pd.DataFrame({**{c: 0.25 for c in P_COLS}, "label_hard": "expansion", "weight": 1.0, "provisional": False,
                      "usrec": 0}, index=idx)
    ad = H.ArrayData(pd.DataFrame({"x": 0.0}, index=idx), t, {"x": {"estado": "principal", "start": None}},
                     kind="synthetic")
    cfg = C(name="t", models=("persistence_pit",), test_start="2004-01", test_end="2004-12", refit_every=1)
    with pytest.raises(V.HoldoutLocked):
        ad.check_cut(pd.Timestamp("2005-01-01"))
    with pytest.raises(V.HoldoutLocked):
        ad.score_labels("2005-03")
    H.walk_forward(ad, [B.PersistencePIT()], cfg)       # hasta 2004-12 sí funciona
    assert len(lab) == 660

# La evaluación única (desbloqueo, consumo, ataques del Validador) se prueba en tests/test_harness_v2.py, sobre un
# repositorio git temporal y una etiqueta sintética.
