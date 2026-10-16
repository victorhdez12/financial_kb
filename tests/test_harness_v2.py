"""Tests del arnés v2 (docs/models/harness.md §9). Solo meses ≤ 2004 de la etiqueta oficial.

A-1: cada ataque del Validador v1 (docs/validation/2026-10-16_harness_v1.md §4) reproducido y ahora FALLANDO. Todas
las pruebas de desbloqueo usan un REPOSITORIO GIT TEMPORAL (hypotheses.yaml y registro de consumo propios) y una
ETIQUETA SINTÉTICA 1990-2012; `R.out_path` se redirige a la sintética para que ninguna vía llegue a la oficial.
M-1 (PITLabeler, score_training), M-2 (ventanas por eje, mínimos), M-3 (ventana fija), M-4 (pesos de madurez),
M-6 y cortes (métricas por eje, Holm, signo, detección, episodios), M0 y hash redondeado.
"""
from __future__ import annotations

import json
import subprocess

import numpy as np
import pandas as pd
import pytest
import yaml

from src.features import pit as P
from src.labels import regime_us as R
from src.models import base as B
from src.models import harness as H
from src.models import metrics as M
from src.models import vault as V
from src.models.metrics import P_COLS

HOLDOUT = pd.Timestamp(R.PARAMS.holdout_start)


@pytest.fixture(scope="module", autouse=True)
def trial_dirs(tmp_path_factory):
    d = tmp_path_factory.mktemp("trials_v2")
    (d / "trial_log.md").write_text("| cabecera |\n")
    mp = pytest.MonkeyPatch()
    mp.setenv("FKB_TRIALS_DIR", str(d / "trials"))
    mp.setenv("FKB_RUNS_DIR", str(d / "runs"))
    mp.setenv("FKB_TRIAL_LOG", str(d / "trial_log.md"))
    mp.delenv(V.UNLOCK_ENV, raising=False)
    yield d
    mp.undo()


@pytest.fixture(scope="module")
def vint():
    return H.PITData("vintage")


def C(**kw):
    return H.HarnessConfig(**{"min_train_months": 12, "min_train_recessions": 0, "min_train_g_changes": 0, **kw})


# ================================================================== A-1: repositorio temporal + etiqueta sintética
def _git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True).stdout


def _fake_label(path, start="1990-01-01", end="2012-12-01"):
    idx = pd.date_range(start, end, freq="MS")
    pd.DataFrame({"date": idx, **{c: 0.25 for c in P_COLS}, "label_hard": "expansion", "weight": 1.0,
                  "provisional": False, "usrec": 0}).to_parquet(path, index=False)
    return path


HYP = [
    {"id": "P-EVAL-TEST", "tipo": "evaluacion_holdout", "estado": "preregistrada (sintética)", "incluye": ["H-TEST-1"],
     "config_arnes": "config/eval_test.yaml"},
    {"id": "P-EVAL-OTRO", "tipo": "evaluacion_holdout", "estado": "preregistrada (sintética)", "incluye": ["H-TEST-1"]},
    {"id": "P-EVAL-SOLO", "tipo": "evaluacion_holdout", "estado": "preregistrada (sintética)"},
    {"id": "P-EVAL-NOTIPO", "estado": "preregistrada (sintética)"},
    {"id": "P-EVAL-BORRADOR", "tipo": "evaluacion_holdout", "estado": "borrador"},
    {"id": "H-TEST-1", "estado": "preregistrada (sintética)"},
]


@pytest.fixture
def evalrepo(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / "research" / "holdout").mkdir(parents=True)
    (repo / "config").mkdir()
    (repo / "research" / "hypotheses.yaml").write_text(yaml.safe_dump(HYP, allow_unicode=True))
    (repo / V.REGISTRY_REL).write_text("")
    (repo / "config" / "eval_test.yaml").write_text(yaml.safe_dump(
        {"name": "eval_test", "phase": "holdout_evaluation", "prereg_id": "P-EVAL-TEST", "test_end": "2012-12"}))
    (repo / ".gitignore").write_text("research/trials/\n")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    fake = _fake_label(tmp_path / "fake_label.parquet")
    monkeypatch.setattr(V, "REPO", repo)
    monkeypatch.setattr(H, "REPO", repo)
    monkeypatch.setattr(R, "out_path", lambda *a, **k: fake)     # ninguna vía llega a la etiqueta oficial
    monkeypatch.setitem(V._PROCESS, "opened", None)
    monkeypatch.setitem(H._EVAL, "vault", None)
    monkeypatch.setenv("FKB_TRIALS_DIR", str(repo / "research" / "trials"))
    monkeypatch.setenv(V.UNLOCK_ENV, "EVALUACION-UNICA P-EVAL-TEST")
    return {"repo": repo, "fake": fake}


def _open(pid="P-EVAL-TEST", **kw):
    return V.LabelVault(mode="holdout_evaluation", prereg_id=pid, **kw)


def _registry(repo):
    return [json.loads(x) for x in (repo / V.REGISTRY_REL).read_text().splitlines() if x.strip()]


def test_unlock_consumes_and_commits_before_read(evalrepo, monkeypatch):
    repo = evalrepo["repo"]
    seen = []
    real = V.pd.read_parquet

    def spy(path, *a, **k):
        seen.append(_registry(repo))           # en el momento de leer, el consumo ya está escrito…
        seen.append(_git(repo, "status", "--porcelain").strip())   # …y commiteado
        return real(path, *a, **k)

    monkeypatch.setattr(V.pd, "read_parquet", spy)
    v = _open()
    df = v.load()
    assert df.index.max() == pd.Timestamp("2012-12-01")
    assert seen[0][0]["prereg_id"] == "P-EVAL-TEST" and seen[0][0]["n"] == 1 and seen[1] == ""
    assert "Holdout evaluation consumed: P-EVAL-TEST" in _git(repo, "log", "--format=%s")
    monkeypatch.setitem(V._PROCESS, "opened", None)
    with pytest.raises(V.HoldoutLocked, match="ya evaluado"):
        _open()


def test_failed_read_still_spends_the_evaluation(evalrepo, monkeypatch):
    def boom(*a, **k):
        raise OSError("disco")

    v = _open()
    monkeypatch.setattr(V.pd, "read_parquet", boom)
    with pytest.raises(OSError):
        v.load()
    assert [r["prereg_id"] for r in _registry(evalrepo["repo"])] == ["P-EVAL-TEST"]


def test_D2_trials_dir_redirect_does_not_reopen(evalrepo, monkeypatch, tmp_path):
    """D2: redirigir FKB_TRIALS_DIR ya no reabre: el registro de consumo tiene ruta fija."""
    _open()
    for i in range(3):
        monkeypatch.setenv("FKB_TRIALS_DIR", str(tmp_path / f"redir_{i}"))
        monkeypatch.setitem(V._PROCESS, "opened", None)
        with pytest.raises(V.HoldoutLocked, match="ya evaluado"):
            _open()
    assert len(_registry(evalrepo["repo"])) == 1
    assert V.registry_path() == evalrepo["repo"] / "research" / "holdout" / "evaluations.jsonl"


def test_registry_tampering_fails_closed(evalrepo, monkeypatch):
    repo = evalrepo["repo"]
    _open()
    reg = repo / V.REGISTRY_REL
    # (a) borrar la línea sin commitear → árbol sucio
    reg.write_text("")
    monkeypatch.setitem(V._PROCESS, "opened", None)
    with pytest.raises(V.HoldoutLocked, match="sucio"):
        _open()
    # (b) borrar la línea y commitear → el historial de git la conserva
    _git(repo, "commit", "-q", "-am", "borra el consumo")
    with pytest.raises(V.HoldoutLocked, match="perdió"):
        _open()
    # (c) dejar de rastrear el registro
    _git(repo, "rm", "-q", "--cached", V.REGISTRY_REL)
    _git(repo, "commit", "-q", "-m", "untrack")
    (repo / ".gitignore").write_text("research/trials/\nresearch/holdout/\n")
    _git(repo, "commit", "-q", "-am", "ignore")
    with pytest.raises(V.HoldoutLocked):
        _open()


def test_included_ids_are_consumed_too(evalrepo, monkeypatch):
    _open()                                                      # P-EVAL-TEST incluye H-TEST-1
    monkeypatch.setitem(V._PROCESS, "opened", None)
    monkeypatch.setenv(V.UNLOCK_ENV, "EVALUACION-UNICA P-EVAL-OTRO")
    with pytest.raises(V.HoldoutLocked, match="H-TEST-1"):
        _open("P-EVAL-OTRO")


def test_D9_only_explicit_evaluation_ids(evalrepo, monkeypatch):
    for pid in ("H-TEST-1", "P-EVAL-NOTIPO", "P-EVAL-BORRADOR", "P-EVAL-NOEXISTE", None):
        monkeypatch.setenv(V.UNLOCK_ENV, f"EVALUACION-UNICA {pid}")
        with pytest.raises(V.HoldoutLocked):
            _open(pid)
    assert _registry(evalrepo["repo"]) == []


def test_D9_no_real_hypothesis_can_open_today():
    """En el repositorio real ninguna de las 13 hipótesis "preregistradas" abre el bloqueado (ninguna es de tipo
    evaluacion_holdout; P-EVAL-BASE es solo un borrador fuera de hypotheses.yaml)."""
    hyp = yaml.safe_load((V.REPO / "research" / "hypotheses.yaml").read_text())
    pre = [h["id"] for h in hyp if str(h.get("estado", "")).startswith("preregistrada")]
    assert len(pre) >= 13
    for pid in pre:
        with pytest.raises(V.HoldoutLocked):
            V.eval_entry(pid)


def test_unlock_needs_explicit_confirmation(evalrepo, monkeypatch):
    monkeypatch.delenv(V.UNLOCK_ENV)
    with pytest.raises(V.HoldoutLocked, match=V.UNLOCK_ENV):
        _open()
    monkeypatch.setenv(V.UNLOCK_ENV, "EVALUACION-UNICA P-EVAL-SOLO")       # confirmación de otro id
    with pytest.raises(V.HoldoutLocked, match=V.UNLOCK_ENV):
        _open()


def test_D6_git_fails_closed(evalrepo, monkeypatch, tmp_path):
    repo = evalrepo["repo"]
    # (a) árbol sucio por un fichero no rastreado
    (repo / "nuevo.py").write_text("x = 1\n")
    with pytest.raises(V.HoldoutLocked, match="sucio"):
        _open()
    (repo / "nuevo.py").unlink()
    # (b) sin git (el binario falla)
    real = subprocess.run

    def nogit(cmd, *a, **k):
        if cmd and cmd[0] == "git":
            raise FileNotFoundError("git")
        return real(cmd, *a, **k)

    monkeypatch.setattr(V.subprocess, "run", nogit)
    with pytest.raises(V.HoldoutLocked, match="git"):
        _open()
    monkeypatch.setattr(V.subprocess, "run", real)
    # (c) fuera de un repositorio (p. ej. un `git archive`)
    norepo = tmp_path / "archive"
    (norepo / "research" / "holdout").mkdir(parents=True)
    (norepo / "research" / "hypotheses.yaml").write_text(yaml.safe_dump(HYP))
    (norepo / V.REGISTRY_REL).write_text("")
    monkeypatch.setattr(V, "REPO", norepo)
    with pytest.raises(V.HoldoutLocked):
        _open()
    assert not (norepo / V.REGISTRY_REL).read_text()


def test_single_opening_per_process(evalrepo, monkeypatch):
    _open()
    monkeypatch.setenv(V.UNLOCK_ENV, "EVALUACION-UNICA P-EVAL-SOLO")
    with pytest.raises(V.HoldoutLocked, match="este proceso"):
        _open("P-EVAL-SOLO")


def test_D1_limit_is_read_only_and_dev_filter_fixed(evalrepo):
    v = V.LabelVault(path=evalrepo["fake"])
    with pytest.raises(AttributeError):
        v.limit = None
    assert v.load().index.max() < HOLDOUT
    with pytest.raises(V.HoldoutLocked):
        v.load(end="2008-01")


class _HoldoutArray(H.ArrayData):
    """El atacante D3 del Validador: ArrayData que dice estar en holdout y no consulta ninguna caja fuerte."""
    phase = "holdout_evaluation"

    def check_cut(self, m0):
        return None

    def score_labels(self, end):
        return self.target[self.target.index <= pd.Timestamp(end)]


def test_D3_run_and_walk_forward_refuse_holdout(evalrepo):
    tgt = pd.read_parquet(evalrepo["fake"]).set_index("date")
    ad = _HoldoutArray(pd.DataFrame({"x": 0.0}, index=tgt.index), tgt, {"x": {"estado": "principal", "start": None}},
                       kind="synthetic")
    cfg = H.HarnessConfig(name="ataque", models=("persistence_pit", "climatology"), modes=("synthetic",),
                          test_start="2000-01", test_end="2012-12", phase="holdout_evaluation", prereg_id="NO-EXISTE")
    for _ in range(3):
        with pytest.raises(V.HoldoutLocked):
            H.run(cfg, datas={"synthetic": ad}, record=False)
    with pytest.raises(V.HoldoutLocked):
        H.walk_forward(ad, H.build_models(cfg), cfg)
    with pytest.raises(V.HoldoutLocked):
        H._run(cfg, {"synthetic": ad}, None, record=False)
    assert _registry(evalrepo["repo"]) == []


def test_D3b_pitdata_rejects_fake_vaults_before_reading(evalrepo, monkeypatch):
    read = []
    monkeypatch.setattr(H.pd, "read_parquet", lambda *a, **k: read.append(a) or pd.DataFrame())

    class Duck:
        mode, prereg_id, unlocked = "holdout_evaluation", "P-EVAL-TEST", True

    class SubVault(V.LabelVault):
        pass

    sub = SubVault.__new__(SubVault)
    sub.mode, sub.prereg_id = "holdout_evaluation", "P-EVAL-TEST"
    real_dev = V.LabelVault(path=evalrepo["fake"])
    for fake in (Duck(), sub, real_dev, None):
        with pytest.raises((V.HoldoutLocked, TypeError)):
            H.PITData("vintage", phase="holdout_evaluation", prereg_id="P-EVAL-TEST", vault=fake)
    # incluso una caja realmente desbloqueada, fuera de evaluate_holdout, no sirve
    v = _open()
    with pytest.raises(V.HoldoutLocked):
        H.PITData("vintage", phase="holdout_evaluation", prereg_id="P-EVAL-TEST", vault=v)
    assert read == []


def test_evaluate_holdout_single_entry_and_closes_vault(evalrepo, monkeypatch):
    """Punto de entrada único: crea él mismo caja y datos (no acepta `datas`), consume antes de construir nada y cierra
    la caja al terminar (una caja usada no sirve para otra corrida). Con dobles: no se lee ningún dato."""
    built = []

    class Stop(Exception):
        pass

    class FakeData:
        def __init__(self, mode, variant, phase, prereg_id, policy, vault=None):
            assert V.is_open_holdout_vault(vault, "P-EVAL-TEST") and H._EVAL["vault"] is vault
            assert _registry(evalrepo["repo"])[0]["prereg_id"] == "P-EVAL-TEST"
            built.append(vault)
            raise Stop

    monkeypatch.setattr(H, "PITData", FakeData)
    with pytest.raises(TypeError):
        H.evaluate_holdout("P-EVAL-TEST", datas={})                     # no acepta datos externos
    with pytest.raises(Stop):
        H.evaluate_holdout("P-EVAL-TEST")
    v = built[0]
    assert not v.unlocked and H._EVAL["vault"] is None
    with pytest.raises(V.HoldoutLocked, match="cerrada"):
        v.load()
    monkeypatch.setitem(V._PROCESS, "opened", None)
    with pytest.raises(V.HoldoutLocked, match="ya evaluado"):
        H.evaluate_holdout("P-EVAL-TEST")
    monkeypatch.setenv(V.UNLOCK_ENV, "EVALUACION-UNICA P-EVAL-SOLO")
    with pytest.raises(V.HoldoutLocked, match="config_arnes"):
        H.evaluate_holdout("P-EVAL-SOLO")                               # sin configuración congelada: no


def test_access_log_complete_fixed_path(evalrepo, monkeypatch, tmp_path):
    """B-3: el registro completo (ruta fija) recoge también la caché y las corridas con record=False."""
    full = V.full_log_dir() / "label_access.jsonl"
    v = V.LabelVault(path=evalrepo["fake"])
    v.load()
    v.load(end="2001-01")
    lines = [json.loads(x) for x in full.read_text().splitlines()]
    assert any(x.get("cache") for x in lines) and all(x["pytest"] for x in lines)


# ================================================================== M-1
def test_M1_pitlabeler_blocks_holdout(vint, trial_dirs):
    lb = vint.labeler
    for t in ("2005-01-31", "2010-06-30"):
        with pytest.raises(V.HoldoutLocked):
            lb.at(t)
    assert len(lb.at("2004-12-31"))
    log = [json.loads(x) for x in (trial_dirs / "trials" / "label_access.jsonl").read_text().splitlines()]
    assert any(x.get("mode") == "pit_labeler" and not x["granted"] for x in log)


def test_M1_score_training_strict_and_unchanged():
    pred = pd.DataFrame({"month": pd.date_range("2000-01-01", "2005-01-01", freq="MS")})
    with pytest.raises(AssertionError):
        P.score_training(pred, end="2005-01-01")
    meta = json.loads((P.out_dir() / f"pit_us_v{H.PIT_VERSION}.meta.json").read_text())["baseline"]
    for mode in P.MODES:
        f = P.out_dir() / f"baseline_persistence_v{H.PIT_VERSION}_{mode}.parquet"
        Bm = pd.read_parquet(f, filters=[("decision_date", "<", HOLDOUT.to_datetime64())])
        assert P.score_training(Bm) == meta[mode]["entrenamiento_hasta_2004"]    # mismo resultado congelado


# ================================================================== M-3: ventana fija
def test_M3_eval_window_fixed_or_warned(vint):
    cfg = H.HarnessConfig(name="t", models=("persistence_pit", "climatology"), modes=("vintage",),
                          test_start="1960-01", test_end="1972-12")      # la climatología empieza en ~1965
    with pytest.raises(ValueError, match="ventana de evaluación"):
        H.run(cfg, datas={"vintage": vint}, record=False)
    from dataclasses import replace
    with pytest.warns(UserWarning, match="REDUCIDA"):
        r = H.run(replace(cfg, allow_shrink=True), datas={"vintage": vint}, record=False)
    assert r["report"]["ventana_evaluacion"]["reducida"] and r["report"]["avisos"]
    ok = H.run(replace(cfg, eval_window=("1970-01", "1972-12")), datas={"vintage": vint}, record=False)
    assert ok["report"]["muestra"] == {"n": 36, "desde": "1970-01", "hasta": "1972-12"} and not ok["report"]["avisos"]


# ================================================================== M-4: pesos de madurez
def test_M4_maturity_weight_function_fixed():
    w = H.maturity_weight
    assert w(4) == pytest.approx(83.2 / 97) and w(12) == w(4)
    assert w(13) == pytest.approx(87.0 / 97) and w(42) == pytest.approx(87.0 / 97)
    assert w(48) == pytest.approx(90.0 / 97) and w(54) == pytest.approx(94.0 / 97)
    assert w(55) == pytest.approx(95.0 / 97) and w(56) == 1.0 and w(200) == 1.0
    ks = range(4, 120)
    assert all(w(a) <= w(b) for a, b in zip(ks, ks[1:]))          # monótona


def test_M4_sample_weight_reaches_fit(vint):
    calls = {}
    for how in H.WEIGHTING:
        spy = _Spy4()
        cfg = H.HarnessConfig(name="t", models=("persistence_pit",), modes=("vintage",), test_start="1990-01",
                              test_end="1990-01", provisional_weighting=how)
        H.walk_forward(vint, [spy], cfg)
        calls[how] = spy.calls[0]
    m0 = pd.Timestamp("1990-01-01")
    lab = vint.train_targets(m0)
    lab = lab[(lab.index <= m0 - pd.DateOffset(months=6)) & (lab["weight"] > 0)]
    prov = lab["provisional"].astype(bool)
    k = (m0.year - lab.index.year) * 12 + (m0.month - lab.index.month) - 1
    exp = np.where(prov, [H.maturity_weight(x) for x in k], 1.0)
    np.testing.assert_allclose(calls["madurez"]["w"], exp)
    assert prov.sum() > 40 and (calls["uno"]["w"] == 1).all()
    assert len(calls["excluir"]["months"]) == (~prov).sum() and (calls["excluir"]["w"] == 1).all()


class _Spy4(B.Model):
    name = "spy4"

    def __init__(self):
        self.calls = []

    def fit(self, X, Y, y, info, sample_weight=None):
        self.calls.append({"months": X.index, "w": np.asarray(sample_weight), "Y": Y})

    def predict_proba(self, X, info):
        return np.full((len(X), 4), 0.25)


# ================================================================== M-2: ventanas por eje + mínimos
class _AxisSpy(B.AxisModel):
    name = "axis_spy"
    uses_persistence = True
    axis_features = {"G": ("growth_rt",), "I": ("core_cpi_6m_ann",)}

    def __init__(self):
        self.calls = []

    def fit_axis(self, axis, X, t, w, info):
        self.calls.append({"axis": axis, "m0": info["refit_month"], "months": X.index, "cols": list(X.columns),
                           "t": t})

    def predict_axis(self, axis, X, info):
        return np.full(len(X), 0.5)


def test_M2_axis_windows_independent_and_minimums(vint):
    spy = _AxisSpy()
    cfg = H.HarnessConfig(name="t", models=("persistence_pit", "axis_spy"), modes=("vintage",),
                          test_start="1975-01", test_end="2004-12", refit_every=60, allow_shrink=True)
    _, diag = H.walk_forward(vint, [B.PersistencePIT(), spy], cfg)
    g_start, i_start = vint.colinfo["growth_rt"]["start"], vint.colinfo["core_cpi_6m_ann"]["start"]
    assert g_start < pd.Timestamp("1965-01-01") and i_start >= pd.Timestamp("1978-01-01")
    for c in spy.calls:
        st = g_start if c["axis"] == "G" else i_start
        assert c["months"].min() >= st and c["cols"] == [*_AxisSpy.axis_features[c["axis"]], B.PERS_AXIS[c["axis"]]]
    g80 = next(c for c in spy.calls if c["axis"] == "G" and c["m0"] == pd.Timestamp("1980-01-01"))
    assert g80["months"].min() < pd.Timestamp("1966-01-01")       # el eje G conserva 1964-77
    d = {x["refit_month"]: x for x in diag if x["model"] == "axis_spy"}
    e75 = d[pd.Timestamp("1975-01-01")]["ejes"]
    assert e75["G"].get("skipped") and e75["G"]["n_recesiones"] == 1   # 1963-11 → 1974-07: solo el pico de 1969-12
    e80 = d[pd.Timestamp("1980-01-01")]["ejes"]
    assert e80["I"].get("skipped") and not e80["G"].get("skipped")   # I: < 120 meses desde 1978 → no predice
    assert e80["G"]["ventana_desde"] == f"{g_start:%Y-%m}" and e80["I"]["ventana_desde"] == f"{i_start:%Y-%m}"
    e95 = d[pd.Timestamp("1995-01-01")]["ejes"]
    for ax in ("G", "I"):
        assert e95[ax]["n_train"] >= 120 and e95[ax]["n_recesiones"] >= 2 and e95[ax]["n_cambios_g"] >= 8


def test_M2_minimums_reject_short_or_quiet_windows():
    idx = pd.date_range("1960-01-01", "1990-12-01", freq="MS")
    tgt = pd.DataFrame({"p_expansion": 0.7, "p_late_cycle": 0.1, "p_stagflation": 0.1, "p_low_growth_disinfl": 0.1,
                        "label_hard": "expansion", "weight": 1.0, "provisional": False, "usrec": 0}, index=idx)
    ad = H.ArrayData(pd.DataFrame({"x": 0.0}, index=idx), tgt, {"x": {"estado": "principal", "start": None}},
                     kind="synthetic")
    cfg = H.HarnessConfig(name="t", models=("persistence_pit", "climatology"), modes=("synthetic",),
                          test_start="1985-01", test_end="1985-12", allow_shrink=True)
    _, diag = H.walk_forward(ad, H.build_models(cfg), cfg)
    cl = [x for x in diag if x["model"] == "climatology"]
    assert cl and all(x.get("skipped") and x["n_recesiones"] == 0 and x["n_cambios_g"] == 0 for x in cl)


def test_count_recessions_pit():
    u = pd.Series(0, index=pd.date_range("1950-01-01", "1990-12-01", freq="MS"))
    u["1957-09-01":"1958-04-01"] = 1
    u["1960-05-01":"1961-02-01"] = 1
    u["1969-12-01":"1970-11-01"] = 1
    assert H.count_recessions(u, pd.Timestamp("1955-01-01"), pd.Timestamp("1970-06-01")) == 2   # 1969-12: < 12 m
    assert H.count_recessions(u, pd.Timestamp("1955-01-01"), pd.Timestamp("1970-12-01")) == 3
    assert H.count_recessions(u, pd.Timestamp("1959-01-01"), pd.Timestamp("1970-12-01")) == 2


# ================================================================== M0
def test_M0_calibrated_persistence_walk_forward(vint):
    """M0 no usa ninguna variable macro: solo P(eje alto) de la persistencia PIT; entrena con datos ≤ corte − 6."""
    seen = []

    def spy(model, info, X, Y):
        if model.name == "m0_calibrated_persistence":
            seen.append((info, list(X.columns)))

    cfg = H.HarnessConfig(name="t", models=("persistence_pit", "m0_calibrated_persistence"), modes=("vintage",),
                          test_start="1985-01", test_end="1986-12", refit_every=12,
                          baseline="m0_calibrated_persistence", reference="persistence_pit")
    r = H.run(cfg, datas={"vintage": vint}, record=False, spy=spy)
    assert {tuple(c) for _, c in seen} == {(B.PERS_AXIS["G"],), (B.PERS_AXIS["I"],)}
    for info, _ in seen:
        assert info["train_months"].max() <= info["refit_month"] - pd.DateOffset(months=6)
    p = r["preds"][r["preds"]["model"] == "m0_calibrated_persistence"]
    pg, pi = M.axis_probs(p[P_COLS].to_numpy())
    np.testing.assert_allclose(p[P_COLS].to_numpy(), M.combine_axes(pg, pi), atol=1e-12)   # producto de ejes
    assert "frente_a_referencia" in r["report"] and r["report"]["frente_al_baseline"]


# ================================================================== M-6, cortes y episodios
def test_axis_logloss_decomposes_for_product():
    rng = np.random.default_rng(0)
    pg, pi, tg, ti = rng.uniform(0.05, 0.95, (4, 50))
    sc = M.monthly_scores(M.combine_axes(pg, pi), M.combine_axes(tg, ti), np.array(["expansion"] * 50))
    np.testing.assert_allclose(sc["logloss"], sc["ll_g"] + sc["ll_i"], atol=1e-10)


def test_holm_and_sign_test_and_p_h0():
    adj = M.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj == pytest.approx({"a": 0.03, "c": 0.06, "b": 0.06})
    assert M.sign_test(10, 10) == pytest.approx(2 / 1024) and M.sign_test(5, 10) == 1.0
    x = np.random.default_rng(1).normal(0.0, 1.0, 240)
    x -= x.mean()
    b = M.boot_mean(x)
    assert 0.05 < b["p_h0"] < 0.95 and "frac_rep_le0" in b and "p_le0" not in b
    assert M.boot_mean(x + 1)["p_h0"] < 0.01


def test_detection_delay_and_false_alarms():
    idx = pd.date_range("1990-01-01", periods=48, freq="MS")
    pgh = np.r_[np.ones(24), np.zeros(24)]
    lab = pd.DataFrame({"p_g_high": pgh, "label_hard": np.where(pgh > 0.5, "expansion", "low_growth_disinfl"),
                        "usrec": 0}, index=idx)
    pred = pd.Series(np.r_[np.full(24, 0.8), np.full(4, 0.8), np.full(20, 0.2)], index=idx)
    pred.iloc[10] = 0.3                                                        # una falsa alarma en la parte estable
    d = M.detection(pred, lab)
    assert d["n_giros"] == 1 and d["giros"][0]["retraso"] == 4 and d["giros"][0]["detectado"]
    assert d["falsas_alarmas"] == 1


def test_episodes_definition():
    idx = pd.date_range("1990-01-01", periods=40, freq="MS")
    hard = ["expansion"] * 12 + ["late_cycle"] * 2 + ["expansion"] * 10 + ["low_growth_disinfl"] * 16
    pgh = [1.0 if h in ("expansion", "late_cycle") else 0.0 for h in hard]
    u = [0] * 30 + [1] * 4 + [0] * 6
    lab = pd.DataFrame({"label_hard": hard, "p_g_high": pgh, "usrec": u}, index=idx)
    eps = M.episodes(lab)
    rachas = [e for e in eps if e["tipo"] == "racha_regimen"]
    assert len(rachas) == 3                                  # el parpadeo de 2 meses no es episodio
    gi = [e for e in eps if e["tipo"] == "giro_g"]
    assert len(gi) == 1 and gi[0]["desde"] == pd.Timestamp("1991-10-01")    # −3 m del giro 1992-01
    assert sum(e["tipo"] == "recesion_nber" for e in eps) == 1
    cuts = M.month_cuts(lab)
    assert cuts.loc["1991-01-01", "giro"] and not cuts.loc["1990-11-01", "giro"]


def test_report_has_axis_cuts_and_r10_hash(vint):
    cfg = H.HarnessConfig(name="t", models=("persistence_pit", "climatology"), modes=("vintage",),
                          test_start="1980-01", test_end="1989-12", refit_every=12,
                          subperiods=(("1980-01", "1984-12"), ("1985-01", "1989-12")))
    r = H.run(cfg, datas={"vintage": vint}, record=False)
    rep = r["report"]
    c = rep["frente_al_baseline"]["vintage/climatology"]
    for k in ("mejora_ll_g", "mejora_ll_i", "mejora_logloss_b24", "cortes", "por_periodo", "por_episodio",
              "subperiodos_mismo_signo"):
        assert k in c
    assert c["mejora_logloss_b24"]["block"] == 24 and {"giro", "estable"} <= set(c["cortes"])
    assert {"recesion_nber", "racha_regimen", "giro_g"} == set(c["por_episodio"]["resumen"])
    assert rep["calibracion"]["vintage/climatology"]["G"] and rep["deteccion_giros_g"]["vintage/persistence_pit"]
    assert "vintage" in rep["holm"]
    # hash redondeado: estable frente a 1e-13; el bit a bit no
    p2 = r["preds"].copy()
    p2.loc[0, "p_expansion"] += 1e-13
    assert H.results_hash(p2, rep, 10) == r["results_sha256_r10"]
    assert H.results_hash(p2.assign(p_expansion=p2["p_expansion"] + 1e-11), rep) != r["results_sha256"]


def test_unrecorded_run_leaves_a_line(vint):
    f = V.full_log_dir() / "harness_runs_unrecorded.jsonl"
    n0 = len(f.read_text().splitlines()) if f.exists() else 0
    H.run(C(name="unrec", models=("persistence_pit",), modes=("vintage",), test_start="1990-01", test_end="1990-03"),
          datas={"vintage": vint}, record=False)
    assert len(f.read_text().splitlines()) == n0 + 1
