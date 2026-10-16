"""Validador (re-auditoría del arnés v2.1: commits 2fd94e0, b626919, cd6d68a, 6902ad3). Ataques a la evaluación
única en REPOSITORIOS GIT TEMPORALES con un REMOTO BARE local (la URL de GitHub se relaja inyectando
`V.REMOTE_URL_RE`, como hacen los tests) y una ETIQUETA SINTÉTICA 1990-2012. La confirmación de desbloqueo se define
solo dentro de este proceso o sus hijos y solo para los repositorios temporales. Nunca toca el repo real.

Ejecutar: .venv/bin/python tests/validation/harness_v2_1_validation.py <salida.json>
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="fkb_val_v21_"))
os.environ["FKB_TRIALS_DIR"] = str(TMP / "trials")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from src.labels import regime_us as R  # noqa: E402
from src.models import harness as H  # noqa: E402
from src.models import metrics as M  # noqa: E402
from src.models import vault as V  # noqa: E402

OUT: dict = {"tmp": str(TMP)}
REAL_OUT = R.out_path
HYP = [{"id": "P-EVAL-TEST", "tipo": "evaluacion_holdout", "estado": "preregistrada (sintética)", "incluye": []}]


def git(repo, *a, check=True):
    r = subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {a}: {r.stderr}")
    return r.stdout


def fake_label(path):
    idx = pd.date_range("1990-01-01", "2012-12-01", freq="MS")
    pd.DataFrame({"date": idx, **{c: 0.25 for c in M.P_COLS}, "label_hard": "expansion", "weight": 1.0,
                  "provisional": False, "usrec": 0}).to_parquet(path, index=False)
    return path


def setup(name, extra_ignore=""):
    base = TMP / name
    repo, bare = base / "repo", base / "remote.git"
    (repo / "research" / "holdout").mkdir(parents=True)
    (repo / "research" / "hypotheses.yaml").write_text(yaml.safe_dump(HYP, allow_unicode=True))
    (repo / V.REGISTRY_REL).write_text("")
    (repo / ".gitignore").write_text("research/trials/\n__pycache__/\n*.pyc\n.env\n" + extra_ignore)
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    git(repo.parent, "init", "-q", "-b", "main", str(repo))
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    git(repo, "remote", "add", "origin", str(bare))
    git(repo, "push", "-q", "-u", "origin", "main")
    return {"repo": repo, "bare": bare, "fake": fake_label(base / "fake.parquet")}


def point(repo, fake):
    V.REPO = repo
    H.REPO = repo
    R.out_path = lambda *a, **k: fake
    V.REMOTE_URL_RE = re.compile(r".*")          # inyección explícita (los tests hacen lo mismo)
    V._PROCESS["opened"] = None
    H._EVAL["vault"] = None
    os.environ["FKB_TRIALS_DIR"] = str(repo / "research" / "trials")
    os.environ[V.UNLOCK_ENV] = "EVALUACION-UNICA P-EVAL-TEST"


def restore():
    V.REPO = ROOT
    H.REPO = ROOT
    R.out_path = REAL_OUT
    V._PROCESS["opened"] = None
    H._EVAL["vault"] = None
    os.environ.pop(V.UNLOCK_ENV, None)
    os.environ["FKB_TRIALS_DIR"] = str(TMP / "trials")


def try_open(window=("2005-01", "2012-12")):
    V._PROCESS["opened"] = None
    try:
        v = V.LabelVault(mode="holdout_evaluation", prereg_id="P-EVAL-TEST", window=window)
        return {"abierta": True, "max": f"{v.load().index.max():%Y-%m}"}
    except V.HoldoutLocked as e:
        return {"abierta": False, "motivo": str(e)[:180]}


def main(dest):
    # T1 apertura normal y reapertura
    e = setup("t1")
    point(e["repo"], e["fake"])
    OUT["T1_primera"] = try_open()
    OUT["T1_segunda"] = try_open()
    # T2 reset --hard local (sin tocar el remoto)
    git(e["repo"], "reset", "-q", "--hard", "HEAD~1")
    OUT["T2_reset_local"] = try_open()
    # T3b reset + push forzado del remoto, SIN expirar el reflog
    git(e["repo"], "push", "-q", "-f", "origin", "HEAD:main")
    OUT["T3b_push_forzado_con_reflog"] = try_open()
    # T3 además: expirar el reflog y gc (local) → ¿reabre?
    git(e["repo"], "reflog", "expire", "--expire=now", "--all")
    git(e["repo"], "gc", "-q", "--prune=now")
    subprocess.run(["git", "-C", str(e["bare"]), "gc", "-q", "--prune=now"], check=False)
    OUT["T3_push_forzado_reflog_expirado_gc"] = try_open()
    OUT["T3_registro_tras_reapertura"] = (e["repo"] / V.REGISTRY_REL).read_text().count("P-EVAL-TEST")
    restore()

    # T4 clon nuevo tras reescribir el remoto
    e = setup("t4")
    point(e["repo"], e["fake"])
    OUT["T4_primera"] = try_open()
    git(e["repo"], "reset", "-q", "--hard", "HEAD~1")
    git(e["repo"], "push", "-q", "-f", "origin", "HEAD:main")
    clone = TMP / "t4" / "clone"
    subprocess.run(["git", "clone", "-q", str(e["bare"]), str(clone)], check=True)
    git(clone, "config", "user.email", "t@t")
    git(clone, "config", "user.name", "t")
    point(clone, e["fake"])
    OUT["T4_clon_tras_reescritura_remota"] = try_open()
    restore()

    # T5 dos clones a la vez: el remoto hace de CAS (push no fast-forward)
    e = setup("t5")
    cl = []
    for k in ("A", "B"):
        c = TMP / "t5" / f"clone{k}"
        subprocess.run(["git", "clone", "-q", str(e["bare"]), str(c)], check=True)
        git(c, "config", "user.email", "t@t")
        git(c, "config", "user.name", "t")
        cl.append(c)
    child = TMP / "child.py"
    child.write_text(CHILD)
    env = {k: v for k, v in os.environ.items() if k != V.UNLOCK_ENV}
    pa = subprocess.Popen([sys.executable, str(child), str(ROOT), str(cl[0]), str(e["fake"]), "0"],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    pb = subprocess.Popen([sys.executable, str(child), str(ROOT), str(cl[1]), str(e["fake"]), "8"],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    oa, ea = pa.communicate(timeout=300)
    ob, eb = pb.communicate(timeout=300)
    OUT["T5_dos_clones"] = {"A": oa.strip()[-250:] or ea[-250:], "B": ob.strip()[-250:] or eb[-250:],
                            "remoto": git(e["bare"], "log", "--format=%s", "main").strip().splitlines()}

    # T6 worktree del mismo repo: ¿mismo cerrojo?
    e = setup("t6")
    wt = TMP / "t6" / "wt"
    git(e["repo"], "worktree", "add", "-q", "-b", "otra", str(wt))
    OUT["T6_cerrojos"] = {"repo": git(e["repo"], "rev-parse", "--absolute-git-dir").strip(),
                          "worktree": git(wt, "rev-parse", "--absolute-git-dir").strip()}

    # T7 N6: ficheros ignorados
    e = setup("t7", extra_ignore="config/local.yaml\n")
    (e["repo"] / ".env").write_text("FKB_TRIALS_DIR=/tmp/otro\n")
    (e["repo"] / "research" / "trials").mkdir(parents=True, exist_ok=True)
    (e["repo"] / "research" / "trials" / "cualquier.py").write_text("x = 1\n")
    point(e["repo"], e["fake"])
    OUT["T7_env_y_research_trials_ignorados"] = try_open()
    restore()
    e = setup("t7b", extra_ignore="config/local.yaml\n")
    (e["repo"] / "config").mkdir()
    (e["repo"] / "config" / "local.yaml").write_text("x: 1\n")
    point(e["repo"], e["fake"])
    OUT["T7b_config_ignorado"] = try_open()
    restore()
    Path(dest).write_text(json.dumps(OUT, indent=1, ensure_ascii=False))
    print(json.dumps(OUT, indent=1, ensure_ascii=False))


CHILD = r"""
import os, sys, re, time, json
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from src.labels import regime_us as R
from src.models import vault as V, harness as H
repo, fake, delay = Path(sys.argv[2]), Path(sys.argv[3]), float(sys.argv[4])
V.REPO = repo; H.REPO = repo; R.out_path = lambda *a, **k: fake
V.REMOTE_URL_RE = re.compile(r".*")
os.environ["FKB_TRIALS_DIR"] = str(repo / "research" / "trials")
os.environ[V.UNLOCK_ENV] = "EVALUACION-UNICA P-EVAL-TEST"
real = V._push_and_verify
state = {"n": 0}
def slow(branch, sha):
    if state["n"] == 0:
        time.sleep(delay)        # B: pasa fetch y merge-base, y espera a que A consuma y empuje
    state["n"] += 1
    return real(branch, sha)
V._push_and_verify = slow
try:
    v = V.LabelVault(mode="holdout_evaluation", prereg_id="P-EVAL-TEST", window=("2005-01", "2012-12"))
    print(json.dumps({"abierta": True}))
except V.HoldoutLocked as e:
    print(json.dumps({"abierta": False, "motivo": str(e)[:200]}))
"""

if __name__ == "__main__":
    try:
        main(sys.argv[1])
    finally:
        restore()
