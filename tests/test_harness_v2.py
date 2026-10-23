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
    {"id": "P-EVAL-AMPL", "tipo": "evaluacion_holdout", "estado": "preregistrada (sintética)", "amplia": "P-EVAL-TEST"},
    {"id": "H-TEST-1", "estado": "preregistrada (sintética)"},
]
REMOTE_RE_REAL = V.REMOTE_URL_RE


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
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    remote = tmp_path / "remote.git"                     # "GitHub" simulado: un repositorio bare local
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    _git(repo, "remote", "add", "origin", str(remote))
    fake = _fake_label(tmp_path / "fake_label.parquet")
    # la comprobación de URL de GitHub se relaja SOLO aquí, por inyección explícita (nunca por variable de entorno)
    monkeypatch.setattr(V, "REMOTE_URL_RE", __import__("re").compile("^" + __import__("re").escape(str(remote)) + "$"))
    # protección de rama (A3-1): el remoto bare local no es GitHub; se simula una protección correcta, también por
    # inyección explícita (los tests de A3-1 la sustituyen por respuestas simuladas de `gh api`)
    monkeypatch.setattr(V, "check_branch_protection", lambda branch=None: {"ok": True, "simulada": True})
    monkeypatch.setattr(V, "REPO", repo)
    monkeypatch.setattr(H, "REPO", repo)
    monkeypatch.setattr(R, "out_path", lambda *a, **k: fake)     # ninguna vía llega a la etiqueta oficial
    monkeypatch.setitem(V._PROCESS, "opened", None)
    monkeypatch.setitem(H._EVAL, "vault", None)
    monkeypatch.setenv("FKB_TRIALS_DIR", str(repo / "research" / "trials"))
    monkeypatch.setenv(V.UNLOCK_ENV, "EVALUACION-UNICA P-EVAL-TEST")
    return {"repo": repo, "fake": fake, "remote": remote}


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
        seen.append(_git(repo, "status", "--porcelain").strip())   # …commiteado…
        seen.append(_git(evalrepo["remote"], "log", "-1", "--format=%H %s", "main").strip())   # …y en el remoto
        return real(path, *a, **k)

    monkeypatch.setattr(V.pd, "read_parquet", spy)
    v = _open()
    df = v.load()
    assert df.index.max() == pd.Timestamp("2012-12-01")
    assert seen[0][0]["prereg_id"] == "P-EVAL-TEST" and seen[0][0]["n"] == 1 and seen[1] == ""
    head = _git(repo, "rev-parse", "HEAD").strip()
    assert seen[2] == f"{head} Holdout evaluation consumed: P-EVAL-TEST"
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
        def __init__(self, mode, variant, phase, prereg_id, policy, vault=None, pit_version=None):
            assert V.is_open_holdout_vault(vault, "P-EVAL-TEST") and H._EVAL["vault"] is vault
            assert _registry(evalrepo["repo"])[0]["prereg_id"] == "P-EVAL-TEST"
            assert V._FIXED["on"] and V.trials_dir() == evalrepo["repo"] / "research" / "trials"   # N7
            built.append(vault)
            raise Stop

    monkeypatch.setattr(H, "PITData", FakeData)
    monkeypatch.setattr(H, "_preflight", lambda *a: {"ok": True})        # el ensayo en seco se prueba aparte
    with pytest.raises(TypeError):
        H.evaluate_holdout("P-EVAL-TEST", datas={})                     # no acepta datos externos
    with pytest.raises(Stop):
        H.evaluate_holdout("P-EVAL-TEST")
    v = built[0]
    assert not v.unlocked and H._EVAL["vault"] is None and not V._FIXED["on"]
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
    # v2.1: retraso hasta la CONFIRMACIÓN (3.er mes seguido del lado nuevo): cambio en 28 → confirmado en 30 → 6
    assert d["n_giros"] == 1 and d["giros"][0]["retraso"] == 6 and d["giros"][0]["detectado"]
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
    # B2-5: las rachas que tocan el borde de la muestra se marcan truncadas (no entran en la prueba de signo)
    assert [e["truncado"] for e in rachas] == [True, False, True]
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


# ================================================================== v2.1: M2-3 detección de giros
def _glab(g, start="1990-01-01"):
    idx = pd.date_range(start, periods=len(g), freq="MS")
    g = np.asarray(g, float)
    return pd.DataFrame({"p_g_high": g, "label_hard": np.where(g > 0.5, "expansion", "low_growth_disinfl"),
                         "usrec": 0}, index=idx)


def test_M23_turns_skip_blinks_and_alternate():
    """Giros tras parpadeos (regla a priori): una racha < 6 m toma el valor de la última racha larga; los giros alternan
    y el mes del giro es el inicio de la racha larga nueva. Caso del Validador: G↑, parpadeo ↓, G↑ → UN solo giro."""
    g = [0] * 12 + [1] * 8 + [0] * 3 + [1] * 10 + [0] * 4 + [1] * 2 + [0] * 12
    lab = _glab(g)
    t = M.g_turns(lab)
    assert [(x["mes"], x["nuevo"]) for x in t] == [(lab.index[12], 1), (lab.index[39], 0)]
    assert all(a["nuevo"] != b["nuevo"] for a, b in zip(t, t[1:]))
    w = M.turn_windows([{"mes": pd.Timestamp("2000-01-01")}, {"mes": pd.Timestamp("2000-07-01")}])
    assert w[0][1] < w[1][0] and w[1][0] == pd.Timestamp("2000-04-01")      # sin solape; el 2.º conserva sus −3 m


def test_M23_detection_confirmation_censoring_anticipation():
    lab = _glab([1] * 24 + [0] * 24)
    turn = lab.index[24]
    late = pd.Series(np.r_[np.full(28, 0.8), np.full(20, 0.2)], index=lab.index)
    early = pd.Series(np.r_[np.full(22, 0.8), np.full(26, 0.2)], index=lab.index)      # cambia 2 m ANTES del giro
    never = pd.Series(np.full(48, 0.8), index=lab.index)
    dl, de, dn = (M.detection(x, lab) for x in (late, early, never))
    assert dl["giros"][0]["retraso"] == 6 and dl["giros"][0]["confirmacion"] == f"{turn + pd.DateOffset(months=6):%Y-%m}"
    assert de["giros"][0]["retraso"] == 0                                  # confirmado en el mes del giro: no se acota
    early2 = pd.Series(np.r_[np.full(21, 0.8), np.full(27, 0.2)], index=lab.index)
    assert M.detection(early2, lab)["giros"][0]["retraso"] == -1           # anticipación: retraso negativo
    assert dn["censurados"] == 1 and dn["detectados"] == 0 and np.isnan(dn["retraso_medio"])   # censura aparte
    v = M.detection_vs(de, dl)
    assert v["n_pares"] == 1 and v["retraso_pareado_medio"] == -6
    v2 = M.detection_vs(dn, dl)
    assert v2["n_pares"] == 0 and v2["censurados_modelo"] == 1 and v2["censurados_comparador"] == 0


# ================================================================== v2.1: M2-4 signos, sign_stability y Holm por familia
def test_M24_coefficient_signs_and_stability(vint):
    months = pd.date_range("1990-01-01", "2004-12-01", freq="MS")
    diags = {"vintage": [{"model": "m", "refit_month": m,
                          "coef": {"I:core_cpi_6m_ann": 0.5 if m < pd.Timestamp("1996-12-01") else -0.2,
                                   "G:growth_rt": 0.3, "G:curve_10y3m": -0.1}} for m in months]}
    cfg = C(name="t", models=("m",), baseline="m", modes=("vintage",), test_start="1990-01", test_end="2004-12",
            eval_window=("1998-01", "2004-12"),
            expected_signs={"m": {"I:core_cpi_6m_ann": "+", "G:growth_rt": "+",
                                  "G:curve_10y3m": {"signo": "+", "decide": False}}})
    out = H.coefficient_signs(diags, {"vintage": vint}, cfg)["vintage/m"]
    assert out["signos"]["G:growth_rt"]["coincide"] and not out["signos"]["I:core_cpi_6m_ann"]["coincide"]
    assert out["signos"]["G:curve_10y3m"]["decide"] is False
    st = {r["variable"]: r for r in out["sign_stability"]}
    assert st["I:core_cpi_6m_ann"]["salto"] == "1996-12" and not st["I:core_cpi_6m_ann"]["mismo_signo"]
    assert out["criterio_signos_cumple"] is False
    diags["vintage"] = [{**d, "coef": {**d["coef"], "I:core_cpi_6m_ann": 0.4}} for d in diags["vintage"]]
    assert H.coefficient_signs(diags, {"vintage": vint}, cfg)["vintage/m"]["criterio_signos_cumple"] is True


def test_M24_holm_family_with_preregistered_p():
    """P-EVAL-MOD: cada módulo frente a M1 en SU eje, Holm con `frac_rep_le0` (no p_h0 ni frente al baseline)."""
    rng = np.random.default_rng(3)
    n = 120
    base = pd.DataFrame({"logloss": 1.0, "ll_g": 0.6 + rng.normal(0, .1, n), "ll_i": 0.3 + rng.normal(0, .1, n)})
    by = {"m1": base, "mod_g": base.assign(ll_g=base["ll_g"] - 0.05), "mod_i": base.assign(ll_i=base["ll_i"] + 0.0)}
    f = {"nombre": "P-EVAL-MOD", "comparador": "m1", "modelos": ["mod_g", "mod_i"],
         "metrica": {"mod_g": "ll_g", "mod_i": "ll_i"}, "p": "frac_rep_le0"}
    out = H.holm_family(f, by)
    assert out["p"] == "frac_rep_le0" and out["sin_corregir"]["mod_g"] == 0.0
    assert out["sin_corregir"]["mod_i"] == 1.0 and out["detalle"]["mod_g"]["metrica"] == "ll_g"
    assert out["ajustado"] == M.holm(out["sin_corregir"])


# ================================================================== v2.1: M2-5 regla complementaria del placebo
def test_M25_placebo_complementary_rule_on_power_table():
    from src.models import placebo as PL
    tab = json.loads((V.REPO / "research" / "trials" / "placebo_power_v2.json").read_text())
    warn = {k: PL.leak_rules(v["pareado"])["aviso_fuga"] for k, v in tab.items() if k != "regla"}
    assert not warn["sin_fuga_ruido"] and not warn["control_t-5_sin_fuga"] and not warn["contemporanea_t_sd4"]
    assert warn["futura_t+1_sd2"] and warn["contemporanea_t_sd2"]        # σ = 2: la regla del 0,02 no las ve
    assert not PL.leak_rules(tab["futura_t+1_sd2"]["pareado"])["fuga_detectada"]


def test_M25_model_placebo_uses_the_models_own_spec(vint):
    """Mecánica: el placebo de un aspirante usa SUS modelos (aquí M0 frente a la sonda, que no usa variables: el
    incremento pareado es exactamente 0 y no hay ni fuga ni aviso)."""
    from src.models import placebo as PL
    from src.models.probes import AxisWindowProbe
    r = PL.model_placebo(vint, lambda: B.CalibratedPersistence(),
                         lambda: AxisWindowProbe({"G": ["unrate_sahm"], "I": ["headline_cpi_6m_ann"]}),
                         seeds=(1, 2), test_start="1990-01", refit_every=60)
    assert r["n_semillas"] == 2 and abs(r["pareado_media"]) < 1e-9 and not r["fuga_detectada"] and not r["aviso_fuga"]


# ================================================================== v2.1: N4 levels_at
def test_N4_levels_at_blocks_holdout(vint):
    with pytest.raises(V.HoldoutLocked, match="levels_at"):
        vint.labeler.levels_at(pd.Timestamp("2006-03-31"))
    assert vint.labeler.levels_at(pd.Timestamp("2004-12-31"))


# ================================================================== v2.1: M2-1 ancla externa, refs, reflog y cerrojo
def test_anchor_requires_github_origin(evalrepo, monkeypatch):
    repo = evalrepo["repo"]
    _git(repo, "remote", "remove", "origin")
    with pytest.raises(V.HoldoutLocked, match="sin remoto 'origin'"):
        _open()
    _git(repo, "remote", "add", "origin", str(evalrepo["remote"]))
    monkeypatch.setattr(V, "REMOTE_URL_RE", REMOTE_RE_REAL)              # la comprobación real: solo GitHub
    with pytest.raises(V.HoldoutLocked, match="no es una URL de GitHub"):
        _open()
    assert _registry(repo) == []
    for url in ("https://github.com/usuario/financial_kb.git", "git@github.com:usuario/financial_kb.git"):
        assert REMOTE_RE_REAL.match(url)
    assert not REMOTE_RE_REAL.match("https://gitlab.com/u/r.git") and not REMOTE_RE_REAL.match(str(evalrepo["remote"]))


def test_push_failure_spends_but_never_opens(evalrepo, monkeypatch):
    remote = evalrepo["remote"]
    hook = remote / "hooks" / "pre-receive"
    hook.write_text('#!/bin/sh\nwhile read old new ref; do git log -1 --format=%s "$new" | grep -q consumed && exit 1; '
                    'done\nexit 0\n')
    hook.chmod(0o755)
    with pytest.raises(V.HoldoutLocked, match="NO commiteado/anclado"):
        _open()
    assert [r["prereg_id"] for r in _registry(evalrepo["repo"])] == ["P-EVAL-TEST"]     # gastado…
    assert not any(V.is_open_holdout_vault(v) for v in list(V._ISSUED))                 # …y sin abrir
    hook.unlink()
    monkeypatch.setitem(V._PROCESS, "opened", None)
    with pytest.raises(V.HoldoutLocked, match="ya evaluado"):
        _open()


def test_N2_history_rewrite_does_not_reopen(evalrepo, monkeypatch):
    repo = evalrepo["repo"]
    _open()
    init = _git(repo, "rev-list", "--max-parents=0", "HEAD").strip()
    # (a) reset --hard: el remoto conserva el consumo (la rama local ya no lo contiene)
    _git(repo, "reset", "-q", "--hard", init)
    monkeypatch.setitem(V._PROCESS, "opened", None)
    with pytest.raises(V.HoldoutLocked, match="no contiene origin/main"):
        _open()
    # (b) además, push forzado que borra el consumo del remoto: el reflog lo conserva
    _git(repo, "push", "-q", "-f", "origin", "HEAD:main")
    with pytest.raises(V.HoldoutLocked, match="perdió"):
        _open()
    # (c) N2b: rama creada antes del consumo
    _git(repo, "checkout", "-q", "-b", "limpia", init)
    with pytest.raises(V.HoldoutLocked, match="perdió"):
        _open()
    assert len([r for r in _registry(repo)]) == 0                    # en el árbol actual no está…
    assert "consumed" in _git(repo, "log", "-g", "--all", "--format=%s")   # …pero el reflog lo guarda


def test_remote_consumption_missing_locally_is_seen(evalrepo, monkeypatch, tmp_path):
    repo, remote = evalrepo["repo"], evalrepo["remote"]
    _git(repo, "push", "-q", "origin", "main")
    other = tmp_path / "otra_maquina"
    subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
    _git(other, "config", "user.email", "o@o")
    _git(other, "config", "user.name", "o")
    with open(other / V.REGISTRY_REL, "a") as fh:
        fh.write(json.dumps({"n": 1, "prereg_id": "P-EVAL-TEST", "incluye": ["H-TEST-1"]}) + "\n")
    _git(other, "commit", "-q", "-am", "Holdout evaluation consumed: P-EVAL-TEST")
    _git(other, "push", "-q", "origin", "main")
    with pytest.raises(V.HoldoutLocked, match="no contiene origin/main"):
        _open()
    _git(repo, "checkout", "-q", "-b", "otra")                        # desde otra rama: el remoto lo delata igual
    with pytest.raises(V.HoldoutLocked, match="perdió"):
        _open()
    assert _registry(repo) == []


def test_lock_blocks_concurrent_unlock(evalrepo):
    with V.holdout_lock():
        with pytest.raises(V.HoldoutLocked, match="cerrojo"):
            _open()
    assert _registry(evalrepo["repo"]) == []


_RACE = """
import re, sys, time
sys.path.insert(0, sys.argv[4])
from pathlib import Path
from src.labels import regime_us as R
from src.models import vault as V
V.REPO = Path(sys.argv[1])
R.out_path = lambda *a, **k: Path(sys.argv[2])
V.REMOTE_URL_RE = re.compile(".*")
V.check_branch_protection = lambda *a, **k: {"ok": True}
orig = V._check_registry_history
def slow():
    r = orig(); time.sleep(float(sys.argv[3])); return r
V._check_registry_history = slow
try:
    V.LabelVault(mode="holdout_evaluation", prereg_id="P-EVAL-TEST")
    print("OPENED")
except V.HoldoutLocked as e:
    print("DENIED", str(e).splitlines()[0])
"""


def test_N8_race_two_processes_second_fails(evalrepo, tmp_path):
    """N8: dos procesos con el mismo id y la ventana entre leer el registro y anotar el consumo ensanchada (4 s): el
    cerrojo hace que el segundo falle; el registro acaba con UNA línea."""
    import os
    import sys
    script = tmp_path / "race.py"
    script.write_text(_RACE)
    env = {**os.environ, "FKB_TRIALS_DIR": str(tmp_path / "tr"), V.UNLOCK_ENV: "EVALUACION-UNICA P-EVAL-TEST"}
    args = [sys.executable, str(script), str(evalrepo["repo"]), str(evalrepo["fake"]), "4",
            str(V.Path(H.__file__).resolve().parents[2])]
    ps = [subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
          for _ in range(2)]
    outs = [p.communicate(timeout=120) for p in ps]
    res = sorted(o[0].strip() for o in outs)
    assert sum(r.startswith("OPENED") for r in res) == 1, outs
    assert any("cerrojo" in r for r in res), outs
    assert len(_registry(evalrepo["repo"])) == 1


def test_N6_ignored_relevant_files_are_dirty(evalrepo):
    repo = evalrepo["repo"]
    (repo / ".gitignore").write_text("research/trials/\n*.local.yaml\n__pycache__/\n")
    _git(repo, "commit", "-q", "-am", "ignore")
    (repo / "config" / "x.local.yaml").write_text("a: 1\n")
    with pytest.raises(V.HoldoutLocked, match="IGNORADOS"):
        _open()
    (repo / "config" / "x.local.yaml").unlink()
    (repo / "config" / "__pycache__").mkdir()
    (repo / "config" / "__pycache__" / "m.cpython-312.pyc").write_bytes(b"x")    # generado por Python: no cuenta
    assert _open().unlocked


def test_N9_extension_needs_amplia_and_new_months(evalrepo, monkeypatch):
    _open(window=("2005-01", "2010-12"))
    monkeypatch.setitem(V._PROCESS, "opened", None)
    monkeypatch.setenv(V.UNLOCK_ENV, "EVALUACION-UNICA P-EVAL-SOLO")
    with pytest.raises(V.HoldoutLocked, match="amplia"):
        _open("P-EVAL-SOLO", window=("2011-01", "2012-12"))
    monkeypatch.setenv(V.UNLOCK_ENV, "EVALUACION-UNICA P-EVAL-AMPL")
    with pytest.raises(V.HoldoutLocked, match="solapa"):
        _open("P-EVAL-AMPL", window=("2010-06", "2012-12"))
    v = _open("P-EVAL-AMPL", window=("2011-01", "2012-12"))
    assert v.unlocked and _registry(evalrepo["repo"])[-1]["ventana"] == ["2011-01", "2012-12"]


# ================================================================== v2.1: M2-2 ensayo en seco
def test_evaluate_holdout_refuses_before_spending_without_dry_run(evalrepo, monkeypatch):
    with pytest.raises(V.HoldoutLocked, match="ensayo en seco"):
        H.evaluate_holdout("P-EVAL-TEST")
    assert _registry(evalrepo["repo"]) == []
    # un ensayo aprobado con el hash correcto, commiteado, pero que AHORA falla: se niega antes de gastar
    repo = evalrepo["repo"]
    sha = H.prereg_config_sha(repo / "config" / "eval_test.yaml")
    (repo / H.DRY_RUNS_REL).write_text(json.dumps({"prereg_id": "P-EVAL-TEST", "ok": True, "config_sha": sha}) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "dry run")
    monkeypatch.setattr(H, "dry_run_prereg", lambda *a, **k: {"ok": False, "errores": ["no elegible"]})
    with pytest.raises(V.HoldoutLocked, match="FALLA"):
        H.evaluate_holdout("P-EVAL-TEST")
    assert _registry(repo) == []
    # el hash cambia con la configuración: un ensayo de otra configuración no vale
    (repo / "config" / "eval_test.yaml").write_text((repo / "config" / "eval_test.yaml").read_text() + "nota: x\n")
    _git(repo, "commit", "-q", "-am", "cambia config")
    with pytest.raises(V.HoldoutLocked, match="no hay ensayo en seco"):
        H.evaluate_holdout("P-EVAL-TEST")


def _probe_cfg(tmp_path, **kw):
    d = {"name": "probe_test", "prereg_id": "P-EVAL-PRUEBA", "phase": "holdout_evaluation",
         "principal": "axis_window_probe", "models": ["axis_window_probe", "m0_calibrated_persistence"],
         "model_params": {"axis_window_probe": {"axis_features": {"G": ["growth_rt", "unrate_sahm"],
                                                                  "I": ["core_cpi_6m_ann"]}}},
         "modes": ["vintage"], "refit_every": 12, "test_start": "1985-01", "test_end": "2021-10",
         "eval_window": ["2005-01", "2021-10"], "epochs": [], "subperiods": [["2005-01", "2014-12"],
                                                                            ["2015-01", "2021-10"]],
         "baseline": "m0_calibrated_persistence", "dry_run_window": ["1995-01", "2004-12"],
         "expected_signs": {"axis_window_probe": {"G:growth_rt": "+", "I:core_cpi_6m_ann": "+"}},
         "holm_families": [{"nombre": "f", "p": "p_h0", "miembros": [
             {"id": "g", "modelo": "axis_window_probe", "metrica": "ll_g", "comparador": "m0_calibrated_persistence"}]}],
         "sensitivities": [{"name": "uno", "provisional_weighting": "uno"}], **kw}
    f = tmp_path / "probe.yaml"
    f.write_text(yaml.safe_dump(d, allow_unicode=True))
    return f


def test_dry_run_executes_the_whole_config_without_opening(vint, tmp_path):
    n0 = len(V.registry_path().read_text().splitlines())
    dr = H.dry_run_prereg(cfg_path=str(_probe_cfg(tmp_path)), record=False, _datas={("vintage", "", "principal"): vint})
    assert dr["ok"], dr["errores"]
    el = {(e["corrida"], e["modelo"], e["eje"]): e for e in dr["elegibilidad"]}
    g = el[("probe_test", "axis_window_probe", "G")]
    assert g["elegible"] and g["primer_corte"] == "2005-01" and g["n_recesiones_cota"] >= 2
    assert ("probe_test__uno", "axis_window_probe", "I") in el and len(dr["ensayos"]) == 2
    assert len(V.registry_path().read_text().splitlines()) == n0           # nada consumido


def test_dry_run_catches_ineligible_models_and_bad_config(vint, tmp_path):
    f = _probe_cfg(tmp_path, allow_shrink=True, eval_window=["2004-06", "2021-12"])
    dr = H.dry_run_prereg(cfg_path=str(f), record=False, _datas={("vintage", "", "principal"): vint})
    e = " | ".join(dr["errores"])
    assert not dr["ok"] and "allow_shrink" in e and "antes del periodo bloqueado" in e and "provisionales" in e
    # A2-1: un módulo H-MOD (dfii10, desde 2003) no está admitido en la política principal ni sería elegible en 2005
    f = _probe_cfg(tmp_path, model_params={"axis_window_probe": {"axis_features": {
        "G": ["growth_rt", "dfii10"], "I": ["core_cpi_6m_ann"]}}})
    dr = H.dry_run_prereg(cfg_path=str(f), record=False, _datas={("vintage", "", "principal"): vint})
    assert not dr["ok"] and any("dfii10" in x for x in dr["errores"])
    # mínimo de entrenamiento inalcanzable en el primer corte de la ventana → NO elegible, antes de gastar nada
    f = _probe_cfg(tmp_path, min_train_months=500)
    dr = H.dry_run_prereg(cfg_path=str(f), record=False, _datas={("vintage", "", "principal"): vint})
    bad = [x for x in dr["elegibilidad"] if not x["elegible"]]
    assert not dr["ok"] and any("NO elegible" in x for x in dr["errores"])
    assert {x["eje"] for x in bad} == {"G", "I"} and all(x["n_train"] < 500 for x in bad)


# ================================================================== A3-1: protección de rama en GitHub comprobada por código
GOOD_PROTECTION = {"url": "https://api.github.com/repos/u/r/branches/main/protection",
                   "allow_force_pushes": {"enabled": False}, "allow_deletions": {"enabled": False},
                   "enforce_admins": {"url": "…", "enabled": True}, "required_linear_history": {"enabled": False}}


def test_A31_protection_problems_on_simulated_responses():
    assert V.protection_problems(GOOD_PROTECTION) == []
    for key, bad in (("allow_force_pushes", True), ("allow_deletions", True), ("enforce_admins", False)):
        r = json.loads(json.dumps(GOOD_PROTECTION))
        r[key]["enabled"] = bad
        assert len(V.protection_problems(r)) == 1 and key in V.protection_problems(r)[0]
    assert len(V.protection_problems({})) == 3                                    # claves ausentes: incumple
    assert len(V.protection_problems({"allow_force_pushes": False, "allow_deletions": None,
                                      "enforce_admins": {"enabled": "true"}})) == 3   # mal formadas: incumple


def test_A31_github_slug():
    assert V.github_slug("https://github.com/victorhdez12/financial_kb.git") == ("victorhdez12", "financial_kb")
    assert V.github_slug("git@github.com:victorhdez12/financial_kb.git") == ("victorhdez12", "financial_kb")
    assert V.github_slug("https://github.com/u/r") == ("u", "r")
    with pytest.raises(V.HoldoutLocked):
        V.github_slug("/tmp/remote.git")


def _gh_check(monkeypatch, response):
    """check_branch_protection REAL (no la simulada del fixture) con `gh api` simulado y un origin de GitHub."""
    calls = []
    monkeypatch.setattr(V, "check_remote", lambda: "https://github.com/u/r.git")

    def fake(path):
        calls.append(path)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(V, "_gh_api", fake)
    return calls


def test_A31_check_branch_protection_ok_and_fails_closed(monkeypatch):
    real = V.check_branch_protection
    calls = _gh_check(monkeypatch, GOOD_PROTECTION)
    out = real("main")
    assert out["ok"] and out["repo"] == "u/r" and calls == ["repos/u/r/branches/main/protection"]
    assert (out["allow_force_pushes"], out["allow_deletions"], out["enforce_admins"]) == (False, False, True)
    bad = {**GOOD_PROTECTION, "allow_force_pushes": {"enabled": True}}
    _gh_check(monkeypatch, bad)
    with pytest.raises(V.HoldoutLocked, match="allow_force_pushes"):
        real("main")
    _gh_check(monkeypatch, V.HoldoutLocked("gh api …: 404 Branch not protected"))
    with pytest.raises(V.HoldoutLocked, match="404"):
        real("main")


def test_A31_gh_api_fails_closed(monkeypatch):
    class Proc:
        def __init__(self, rc, out, err=""):
            self.returncode, self.stdout, self.stderr = rc, out, err

    monkeypatch.setattr(V.subprocess, "run", lambda *a, **k: Proc(1, "", "HTTP 404: Branch not protected"))
    with pytest.raises(V.HoldoutLocked, match="404"):
        V._gh_api("repos/u/r/branches/main/protection")
    monkeypatch.setattr(V.subprocess, "run", lambda *a, **k: Proc(0, "no es json"))
    with pytest.raises(V.HoldoutLocked, match="JSON"):
        V._gh_api("x")
    monkeypatch.setattr(V.subprocess, "run", lambda *a, **k: Proc(0, "[1, 2]"))
    with pytest.raises(V.HoldoutLocked, match="inesperada"):
        V._gh_api("x")

    def boom(*a, **k):
        raise FileNotFoundError("gh")

    monkeypatch.setattr(V.subprocess, "run", boom)
    with pytest.raises(V.HoldoutLocked, match="gh no disponible"):
        V._gh_api("x")
    monkeypatch.setattr(V.subprocess, "run", lambda *a, **k: Proc(0, json.dumps(GOOD_PROTECTION)))
    assert V._gh_api("x") == GOOD_PROTECTION


def test_A31_unlock_aborts_without_protection_and_spends_nothing(evalrepo, monkeypatch):
    def nope(branch=None):
        raise V.HoldoutLocked(f"la rama {branch} no tiene la protección exigida (A3-1)")

    monkeypatch.setattr(V, "check_branch_protection", nope)
    with pytest.raises(V.HoldoutLocked, match="protección exigida"):
        _open()
    assert _registry(evalrepo["repo"]) == []                                   # nada consumido
    assert _git(evalrepo["remote"], "rev-list", "--all").strip() == ""          # nada empujado
    with pytest.raises(V.HoldoutLocked, match="protección exigida"):
        H.evaluate_holdout("P-EVAL-TEST")
    assert _registry(evalrepo["repo"]) == []


def test_A31_registered_dry_run_needs_protection(monkeypatch, tmp_path):
    def nope(branch=None):
        raise V.HoldoutLocked("sin protección (A3-1)")

    monkeypatch.setattr(V, "check_branch_protection", nope)
    seen = []
    monkeypatch.setattr(V, "_append", lambda path, rec: seen.append(path))
    with pytest.raises(V.HoldoutLocked, match="A3-1"):
        H.dry_run_prereg(cfg_path=str(_probe_cfg(tmp_path)), record=True)
    assert seen == []                                                          # no deja ninguna línea "ok"
