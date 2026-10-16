"""Validador (re-auditoría del arnés v2: commits e58a054 y 2159d53). Solo ≤ 2004; nunca el periodo bloqueado.

Todos los ataques a la caja fuerte se hacen en un REPOSITORIO GIT TEMPORAL con su hypotheses.yaml y su registro de
consumo, y con una ETIQUETA SINTÉTICA 1990-2012 (`R.out_path` redirigido). La confirmación de desbloqueo solo se
define DENTRO de este proceso (o de sus hijos) y solo para el repositorio temporal; nunca en el repo real.

Ejecutar: .venv/bin/python tests/validation/harness_v2_validation.py <salida.json> [secciones...]
secciones: attacks race m0 weights recessions placebo_rules
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="fkb_val_v2_"))
os.environ["FKB_TRIALS_DIR"] = str(TMP / "trials")
os.environ["FKB_RUNS_DIR"] = str(TMP / "runs")
os.environ["FKB_TRIAL_LOG"] = str(TMP / "trial_log.md")
(TMP / "trial_log.md").write_text("| cabecera |\n")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from src.labels import regime_us as R  # noqa: E402
from src.models import base as B  # noqa: E402
from src.models import harness as H  # noqa: E402
from src.models import metrics as M  # noqa: E402
from src.models import vault as V  # noqa: E402

OUT: dict = {"tmp": str(TMP)}
REAL_OUT_PATH = R.out_path
HYP = [
    {"id": "P-EVAL-TEST", "tipo": "evaluacion_holdout", "estado": "preregistrada (sintética)", "incluye": ["H-TEST-1"],
     "config_arnes": "config/eval_test.yaml"},
    {"id": "H-TEST-1", "estado": "preregistrada (sintética)"},
]


def git(repo, *a, check=True):
    return subprocess.run(["git", "-C", str(repo), *a], check=check, capture_output=True, text=True).stdout


def make_repo(name: str, extra_ignore: str = "") -> dict:
    """Repositorio temporal + etiqueta sintética; redirige V/H/R y define la confirmación SOLO en este proceso."""
    repo = TMP / name / "repo"
    (repo / "research" / "holdout").mkdir(parents=True)
    (repo / "config").mkdir()
    (repo / "research" / "hypotheses.yaml").write_text(yaml.safe_dump(HYP, allow_unicode=True))
    (repo / V.REGISTRY_REL).write_text("")
    (repo / "config" / "eval_test.yaml").write_text(yaml.safe_dump(
        {"name": "eval_test", "phase": "holdout_evaluation", "prereg_id": "P-EVAL-TEST", "test_end": "2012-12"}))
    (repo / ".gitignore").write_text("research/trials/\n" + extra_ignore)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    idx = pd.date_range("1990-01-01", "2012-12-01", freq="MS")
    fake = TMP / name / "fake_label.parquet"
    pd.DataFrame({"date": idx, **{c: 0.25 for c in M.P_COLS}, "label_hard": "expansion", "weight": 1.0,
                  "provisional": False, "usrec": 0}).to_parquet(fake, index=False)
    V.REPO = repo
    H.REPO = repo
    R.out_path = lambda *a, **k: fake
    V._PROCESS["opened"] = None
    H._EVAL["vault"] = None
    os.environ["FKB_TRIALS_DIR"] = str(repo / "research" / "trials")
    os.environ[V.UNLOCK_ENV] = "EVALUACION-UNICA P-EVAL-TEST"     # solo en este proceso y para el repo temporal
    return {"repo": repo, "fake": fake}


def restore():
    V.REPO = ROOT
    H.REPO = ROOT
    R.out_path = REAL_OUT_PATH
    V._PROCESS["opened"] = None
    H._EVAL["vault"] = None
    os.environ.pop(V.UNLOCK_ENV, None)
    os.environ["FKB_TRIALS_DIR"] = str(TMP / "trials")


def try_open(pid="P-EVAL-TEST"):
    try:
        v = V.LabelVault(mode="holdout_evaluation", prereg_id=pid)
        df = v.load()
        return {"abierta": True, "max": f"{df.index.max():%Y-%m}"}
    except V.HoldoutLocked as e:
        return {"abierta": False, "motivo": str(e)[:160]}


def registry_lines(repo):
    return [json.loads(x) for x in (repo / V.REGISTRY_REL).read_text().splitlines() if x.strip()]


# ------------------------------------------------------------------ ataques A-1 / M-1
def sec_attacks():
    out = {}
    # D1: limit de solo lectura; y forja de los atributos con nombre "privado"
    e = make_repo("d1")
    v = V.LabelVault()
    try:
        v.limit = None
        out["D1_limit_None"] = "asignado (FALLO)"
    except AttributeError:
        out["D1_limit_None"] = "AttributeError (barrera)"
    v = V.LabelVault()
    v._LabelVault__unlocked = True
    v.mode = "holdout_evaluation"
    V._ISSUED.add(v)
    df = v.load()
    out["N1_forja_dentro_del_proceso_(__unlocked + _ISSUED)"] = {
        "lee_hasta": f"{df.index.max():%Y-%m}", "is_open_holdout_vault": V.is_open_holdout_vault(v),
        "consumo_en_registro": len(registry_lines(e["repo"]))}
    # …y con _EVAL forjado, PITData en holdout llega a leer la matriz SIN filtro (interceptado antes de decodificar)
    H._EVAL["vault"] = v
    seen = {}
    real = H.pd.read_parquet

    class Stop(Exception):
        pass

    def spy_read(path, *a, **k):
        seen["path"], seen["filters"] = Path(path).name, k.get("filters")
        raise Stop

    H.pd.read_parquet = spy_read
    try:
        H.PITData("vintage", phase="holdout_evaluation", prereg_id=None, vault=v)
        seen["resultado"] = "sin excepción"
    except Stop:
        seen["resultado"] = "llegó a read_parquet"
    except Exception as ex:  # noqa: BLE001
        seen["resultado"] = repr(ex)[:160]
    finally:
        H.pd.read_parquet = real
    out["N1b_PITData_con__EVAL_forjado"] = seen
    restore()

    # D2: FKB_TRIALS_DIR ya no reabre
    e = make_repo("d2")
    r1 = try_open()
    V._PROCESS["opened"] = None
    os.environ["FKB_TRIALS_DIR"] = str(TMP / "otro_dir")
    r2 = try_open()
    out["D2_redirigir_FKB_TRIALS_DIR"] = {"primera": r1, "segunda_otro_dir": r2}
    # N2: reescribir el historial (reset --hard al commit anterior al consumo) → ¿reabre?
    log_before = git(e["repo"], "log", "--oneline")
    git(e["repo"], "reset", "-q", "--hard", "HEAD~1")
    V._PROCESS["opened"] = None
    r3 = try_open()
    reflog = git(e["repo"], "reflog", "--format=%gs")
    out["N2_historial_reescrito_(reset --hard HEAD~1)"] = {"log_antes": log_before.strip().splitlines(),
                                                            "tercera_apertura": r3,
                                                            "rastro_en_reflog": "consumed" in reflog}
    # N2b: rama creada antes del consumo
    restore()
    e = make_repo("d2b")
    base_commit = git(e["repo"], "rev-parse", "HEAD").strip()
    try_open()
    git(e["repo"], "checkout", "-q", "-b", "limpia", base_commit)
    V._PROCESS["opened"] = None
    out["N2b_rama_anterior_al_consumo"] = try_open()
    restore()

    # D3: run() en holdout con ArrayData → debe negarse
    e = make_repo("d3")
    idx = pd.date_range("1990-01-01", "2012-12-01", freq="MS")
    tgt = pd.read_parquet(e["fake"]).set_index("date")
    ad = H.ArrayData(pd.DataFrame({"x": 0.0}, index=idx), tgt, {"x": {"estado": "principal", "start": None}},
                     kind="synthetic")
    try:
        object.__setattr__(ad, "phase", "holdout_evaluation")
        out["D3_ArrayData_phase_asignable"] = True
    except Exception as ex:  # noqa: BLE001
        out["D3_ArrayData_phase_asignable"] = repr(ex)[:120]
    try:
        cfg = H.HarnessConfig(name="x", models=("persistence_pit",), modes=("synthetic",), test_start="2000-01",
                              test_end="2012-12", phase="holdout_evaluation", prereg_id="P-EVAL-TEST",
                              min_train_months=12, min_train_recessions=0, min_train_g_changes=0)
        H.run(cfg, datas={"synthetic": ad}, record=False)
        out["D3_run_holdout"] = "ejecutada (FALLO)"
    except V.HoldoutLocked as ex:
        out["D3_run_holdout"] = f"HoldoutLocked: {str(ex)[:100]}"
    # D3b: caja falsa por duck typing
    class Duck:
        mode = "holdout_evaluation"
    try:
        H.PITData("vintage", phase="holdout_evaluation", prereg_id="P-EVAL-TEST", vault=Duck())
        out["D3b_duck"] = "aceptada (FALLO)"
    except (V.HoldoutLocked, TypeError) as ex:
        out["D3b_duck"] = f"{type(ex).__name__}"
    restore()

    # D4: PITLabeler.at(2010) y levels_at(2010)
    from src.models.pit_labels import PITLabeler
    lb = PITLabeler("latest_truncated")
    try:
        lb.at("2010-06-30")
        out["D4_at_2010"] = "devuelta (FALLO)"
    except V.HoldoutLocked:
        out["D4_at_2010"] = "HoldoutLocked (barrera)"
    lb.levels = {sid: s[s.index < V.HOLDOUT_START] for sid, s in lb.levels.items()}   # sin datos del bloqueado
    try:
        lv = lb.levels_at(pd.Timestamp("2010-06-30"))
        out["N4_levels_at_2010_sin_barrera"] = {"series": len(lv), "excepcion": None}
    except Exception as ex:  # noqa: BLE001
        out["N4_levels_at_2010_sin_barrera"] = {"excepcion": repr(ex)[:120]}

    # D5: score_training(end=2005-01) con etiqueta sintética
    from src.features import pit as P
    fake = make_repo("d5")["fake"]
    pred = pd.DataFrame({"month": pd.date_range("2000-01-01", "2005-01-01", freq="MS")})
    for c in P.PRED_COLS:
        pred[c] = 0.25
    pred["pers_hard"], pred["lag_months"] = "expansion", 5
    try:
        P.score_training(pred, end="2005-01-01")
        out["D5_score_training_2005_01"] = "puntuado (FALLO)"
    except AssertionError:
        out["D5_score_training_2005_01"] = "AssertionError (barrera)"
    restore()

    # D6: fuera de un repo
    e = make_repo("d6")
    import shutil
    norepo = TMP / "d6" / "norepo"
    shutil.copytree(e["repo"], norepo, ignore=shutil.ignore_patterns(".git"))
    V.REPO = norepo
    out["D6_fuera_de_repo"] = try_open()
    restore()

    # D9 / incluye / ids nuevos: un id nuevo cuesta un commit
    e = make_repo("d9")
    out["d9_primera"] = try_open()
    hyp = HYP + [{"id": "P-EVAL-TEST2", "tipo": "evaluacion_holdout", "estado": "preregistrada (sintética)",
                  "incluye": ["H-TEST-1"]},
                 {"id": "P-EVAL-TEST3", "tipo": "evaluacion_holdout", "estado": "preregistrada (sintética)"}]
    (e["repo"] / "research" / "hypotheses.yaml").write_text(yaml.safe_dump(hyp, allow_unicode=True))
    git(e["repo"], "commit", "-q", "-am", "nuevo preregistro")
    for pid in ("P-EVAL-TEST2", "P-EVAL-TEST3"):
        V._PROCESS["opened"] = None
        os.environ[V.UNLOCK_ENV] = f"EVALUACION-UNICA {pid}"
        out[f"N9_{pid}"] = try_open(pid)
    out["N9_registro_n"] = [r["n"] for r in registry_lines(e["repo"])]
    restore()

    # N6: ficheros ignorados por git no cuentan como "árbol sucio"
    e = make_repo("n6", extra_ignore="*.pyc\n__pycache__/\n.env\n")
    (e["repo"] / "src").mkdir()
    (e["repo"] / "src" / "__pycache__").mkdir()
    (e["repo"] / "src" / "__pycache__" / "harness.cpython-311.pyc").write_bytes(b"x")
    (e["repo"] / ".env").write_text("FIN_DATA_ROOT=/otro\n")
    out["N6_ignorados_presentes"] = try_open()
    restore()

    # N7: el registro de RESULTADOS de la evaluación única sigue siendo redirigible (FKB_TRIALS_DIR/FKB_RUNS_DIR)
    import inspect
    from src.models import trials as T
    out["N7_trials_record_rutas"] = {"trials_dir_usa_env": "FKB_TRIALS_DIR" in inspect.getsource(V.trials_dir),
                                     "runs_dir_usa_env": "FKB_RUNS_DIR" in inspect.getsource(T.runs_dir),
                                     "evaluate_holdout_fija_rutas": "FKB_TRIALS_DIR" in inspect.getsource(
                                         H.evaluate_holdout)}
    OUT["attacks"] = out


# ------------------------------------------------------------------ carrera entre dos procesos
CHILD = r"""
import os, sys, time, json
sys.path.insert(0, sys.argv[1])
from pathlib import Path
import pandas as pd
from src.labels import regime_us as R
from src.models import vault as V, harness as H
repo, fake, delay = Path(sys.argv[2]), Path(sys.argv[3]), float(sys.argv[4])
V.REPO = repo; H.REPO = repo; R.out_path = lambda *a, **k: fake
os.environ["FKB_TRIALS_DIR"] = str(repo / "research" / "trials")
os.environ[V.UNLOCK_ENV] = "EVALUACION-UNICA P-EVAL-TEST"
real = V.consumed_ids
def slow():
    r = real(); time.sleep(delay); return r     # ventana entre leer el registro (paso 5) y anotar el consumo
V.consumed_ids = slow
try:
    v = V.LabelVault(mode="holdout_evaluation", prereg_id="P-EVAL-TEST")
    print(json.dumps({"abierta": True, "max": str(v.load().index.max())}))
except V.HoldoutLocked as e:
    print(json.dumps({"abierta": False, "motivo": str(e)[:200]}))
"""


def sec_race():
    e = make_repo("race")
    child = TMP / "race_child.py"
    child.write_text(CHILD)
    env = {k: v for k, v in os.environ.items() if k != V.UNLOCK_ENV}
    py = sys.executable
    pa = subprocess.Popen([py, str(child), str(ROOT), str(e["repo"]), str(e["fake"]), "2"], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, env=env)
    pb = subprocess.Popen([py, str(child), str(ROOT), str(e["repo"]), str(e["fake"]), "6"], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, env=env)
    oa, ea = pa.communicate(timeout=300)
    ob, eb = pb.communicate(timeout=300)
    OUT["race"] = {"A": oa.strip()[-300:] or ea[-300:], "B": ob.strip()[-300:] or eb[-300:],
                   "registro": registry_lines(e["repo"]),
                   "commits": git(e["repo"], "log", "--format=%s").strip().splitlines()}
    restore()


# ------------------------------------------------------------------ M0: espía + reimplementación independiente
def sec_m0():
    from scipy.optimize import minimize
    d = H.PITData("vintage")
    calls = []
    real_fit = B.CalibratedPersistence.fit_axis

    def spy_fit(self, axis, X, t, w, info):
        calls.append({"m0": info["refit_month"], "T": info["decision_date"], "axis": axis, "X": X.copy(),
                      "t": np.array(t), "w": np.array(w)})
        return real_fit(self, axis, X, t, w, info)

    B.CalibratedPersistence.fit_axis = spy_fit
    try:
        cfg = H.HarnessConfig(name="val_m0", models=("persistence_pit", "m0_calibrated_persistence"),
                              model_params={"m0_calibrated_persistence": {"eps": 1e-3, "l2": 1.0}},
                              modes=("vintage",), test_start="1975-01", test_end="2004-12", refit_every=60,
                              baseline="persistence_pit")
        preds, diag = H.walk_forward(d, H.build_models(cfg), cfg)
    finally:
        B.CalibratedPersistence.fit_axis = real_fit
    viol, tdiff, wdiff, pdiff = 0, 0.0, 0.0, 0.0
    for c in calls:
        m0 = c["m0"]
        viol += int(c["X"].index.max() > m0 - pd.DateOffset(months=6))
        lab = d.labeler.at(c["T"]).set_index("date").loc[c["X"].index]
        tdiff = max(tdiff, float(np.abs(c["t"] - lab[M.P_COLS].to_numpy(float) @ H.AXIS_VEC[c["axis"]]).max()))
        k = H._mdiff(m0, c["X"].index) - 1
        wexp = np.where(lab["provisional"].astype(bool), [H.maturity_weight(x) for x in k], 1.0)
        wdiff = max(wdiff, float(np.abs(c["w"] - wexp).max()))
        pers = d.pers_rows(c["X"].index)[B.PERS_AXIS[c["axis"]]].to_numpy(float)
        pdiff = max(pdiff, float(np.abs(pers - c["X"][B.PERS_AXIS[c["axis"]]].to_numpy(float)).max()))
    # reimplementación independiente (statsmodels-free): logística binaria ponderada, objetivo blando, L2 = 1 en b
    rep = []
    for c in calls:
        z = np.log(np.clip(c["X"][B.PERS_AXIS[c["axis"]]].to_numpy(float), 1e-3, 1 - 1e-3))
        z = z - np.log(1 - np.clip(c["X"][B.PERS_AXIS[c["axis"]]].to_numpy(float), 1e-3, 1 - 1e-3))
        t, w = c["t"], c["w"]

        def nll(b):
            s = b[0] + b[1] * z
            return (w * (np.logaddexp(0, s) - t * s)).sum() + 1.0 * b[1] ** 2

        b = minimize(nll, np.zeros(2), method="Nelder-Mead", options={"xatol": 1e-10, "fatol": 1e-12,
                                                                        "maxiter": 20000}).x
        rep.append({"m0": f"{c['m0']:%Y-%m}", "eje": c["axis"], "n": len(t), "a": round(float(b[0]), 4),
                    "b": round(float(b[1]), 4), "peso_medio": round(float(w.mean()), 4)})
    OUT["m0"] = {"fits": len(calls), "violaciones_embargo": viol, "max_dif_objetivo_vs_at(T)": tdiff,
                 "max_dif_pesos_vs_funcion": wdiff, "max_dif_pers_axis": pdiff, "coeficientes_independientes": rep,
                 "coef_arnes": [x.get("coef") for x in diag if x.get("model") == "m0_calibrated_persistence"]}


# ------------------------------------------------------------------ pesos: convención de k
def sec_weights():
    d = H.PITData("latest_truncated")
    rows = []
    for m0 in pd.date_range("1975-01-01", "2004-01-01", freq="60MS"):
        lab = d.labeler.at(d.decision[m0]).set_index("date")
        prov = lab[lab["provisional"].astype(bool)]
        k = H._mdiff(m0, prov.index) - 1
        rows.append({"m0": f"{m0:%Y-%m}", "ultima_fila_k_estudio": int(H._mdiff(m0, lab.index.max()) - 1),
                     "k_provisionales": [int(k.min()), int(k.max())], "n_prov": len(prov),
                     "w_min_max": [H.maturity_weight(int(k.min())), H.maturity_weight(int(k.max()))]})
    table = {k: round(H.maturity_weight(k), 4) for k in (4, 5, 12, 13, 42, 43, 48, 49, 54, 55, 56, 57, 60)}
    OUT["weights"] = {"cortes": rows, "w(k)": table}


# ------------------------------------------------------------------ recesiones: elegibilidad
def sec_recessions():
    d = H.PITData("vintage")
    u = d.usrec.fillna(0).astype(int)
    peaks = list(u.index[(u == 1) & (u.shift(1, fill_value=0) == 0)])
    peaks = [p for p in peaks if p >= pd.Timestamp("1940-01-01")]
    out = {"picos": [f"{p:%Y-%m}" for p in peaks]}
    for name, st in (("G_growth_rt", d.colinfo["growth_rt"]["start"]),
                     ("I_core_cpi", d.colinfo["core_cpi_6m_ann"]["start"]), ("sin_variables", pd.Timestamp("1955-01-01"))):
        first = None
        for m0 in pd.date_range("1960-01-01", "2004-12-01", freq="MS"):
            last = m0 - pd.DateOffset(months=6)
            n = H.count_recessions(d.usrec, st, last)
            nm = (last.year - st.year) * 12 + last.month - st.month + 1
            if n >= 2 and nm >= 120:
                first = m0
                break
        out[name] = {"inicio_ventana": f"{st:%Y-%m}", "primer_corte_con_120m_y_2_recesiones": f"{first:%Y-%m}"
                     if first is not None else None}
    OUT["recessions"] = out


# ------------------------------------------------------------------ reglas complementarias del placebo
def sec_placebo_rules():
    from math import comb
    res = {}
    for src in (ROOT / "research" / "trials" / "placebo_power_v2.json",
                Path(os.environ.get("FKB_VAL_PLACEBO_REPRO", "/nonexistent"))):
        if not src.exists():
            continue
        d = json.loads(src.read_text())
        tab = {}
        for k, v in d.items():
            if not isinstance(v, dict) or "pareado" not in v:
                continue
            p = np.array(v["pareado"])
            n, w = len(p), int((p > 0).sum())
            p_sign = sum(comb(n, j) for j in range(w, n + 1)) / 2 ** n      # unilateral
            se = p.std(ddof=1) / np.sqrt(n)
            tab[k] = {"media": round(float(p.mean()), 4), "frac_>0": w / n, "p_signo_unilateral": round(p_sign, 5),
                      "t": round(float(p.mean() / se), 2) if se > 0 else None,
                      "regla_0.02": bool(p.mean() > 0.02), "regla_80%": bool(w / n >= 0.8),
                      "regla_signo_p<0.01": bool(p_sign < 0.01), "regla_t>3": bool(se > 0 and p.mean() / se > 3)}
        res[src.name if "research" in str(src) else "reproduccion"] = tab
    OUT["placebo_rules"] = res


SECS = {"attacks": sec_attacks, "race": sec_race, "m0": sec_m0, "weights": sec_weights,
        "recessions": sec_recessions, "placebo_rules": sec_placebo_rules}

if __name__ == "__main__":
    dest = Path(sys.argv[1])
    for s in (sys.argv[2:] or list(SECS)):
        t0 = time.time()
        try:
            SECS[s]()
        finally:
            restore()
        print(f"[{s}] {time.time() - t0:.0f} s", flush=True)
        dest.write_text(json.dumps(OUT, indent=1, ensure_ascii=False, default=str))
    print(json.dumps(OUT, indent=1, ensure_ascii=False, default=str)[:20000])
