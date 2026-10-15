"""Re-auditoría de cierre de la etiqueta v1.1 (commit ebccae1). Solo lee: trabaja en copias temporales.

    .venv/bin/python -m tests.validation.label_v1_1_closure [commit]      # ~2 min

Bloques:
  1. Reproducción desde `git archive <commit>` + copia de la instantánea, sin warehouse (db.connect bloqueado).
  2. Mutaciones (en copias del árbol y de los datos): ¿qué tests de tests/test_labels.py fallan?
  3. Lista negra: casos adversarios y falsos positivos sobre el catálogo del warehouse (solo lectura).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = str(REPO / ".venv" / "bin" / "python")
DATA = Path("~/financial_archive/labels").expanduser()
FILES = ["regime_us_v1.1.parquet", "regime_us_v1.1.meta.json", "regime_us_v1.0.parquet", "revision_study.json"]
SNAP = "inputs/regime_us_v1.1_inputs.parquet"

WRAP = """
_orig_bfi = build_from_inputs
def build_from_inputs(*a, **k):
    df, info = _orig_bfi(*a, **k)
    df = df.copy(); MUT(df); return df, info
"""
PARAM = """
import dataclasses as _dc
_orig_bfi = build_from_inputs
def build_from_inputs(inputs, p=PARAMS, snap_info=None):
    return _orig_bfi(inputs, _dc.replace(p, {kw}), snap_info)
"""
ROW = WRAP + "def MUT(df):\n    i = df.index[df.date == '{d}'][0]; df.loc[i, '{c}'] = {expr}\n"
CODE_MUTANTS = {
    "kappa 2.5→2.4": PARAM.format(kw="kappa=2.4"),
    "splice_months 24→69 (solo ventana 1957-59)": PARAM.format(kw="splice_months=69"),
    "I 1980-01 +1e-3 (fila madura)": ROW.format(d="1980-01-01", c="I", expr="df.loc[i, 'I'] + 1e-3"),
    "I 1980-01 +1e-6 (fila madura)": ROW.format(d="1980-01-01", c="I", expr="df.loc[i, 'I'] + 1e-6"),
    "G ×1.000005 en maduras": WRAP + "def MUT(df):\n    m = ~df.provisional; df.loc[m, 'G'] *= 1.000005\n",
    "I 1958-01 +0.3 (dentro de la ventana)": ROW.format(d="1958-01-01", c="I", expr="df.loc[i, 'I'] + 0.3"),
    "read_snapshot sin comprobación": """
def read_snapshot(p=PARAMS):
    path = snapshot_path(p); df = pd.read_parquet(path)
    return frame_to_inputs(df), {"path": str(path), "sha256_file": file_sha(path),
                                 "sha256_content": content_hash(df), "rows": len(df)}
""",
    "FROZEN vaciado": "FROZEN.clear()\n",
}


def sh(cmd, cwd, env=None, check=True):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, check=check, shell=isinstance(cmd, str))


def make_data(root: Path) -> Path:
    d = root / "labels"
    (d / "inputs").mkdir(parents=True)
    for f in FILES:
        shutil.copy2(DATA / f, d / f)
    shutil.copy2(DATA / SNAP, d / SNAP)
    return root


def pytest_failures(tree: Path, data: Path) -> str:
    import os
    env = dict(os.environ, FIN_DATA_ROOT=str(data))
    r = sh([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_labels.py"], tree, env, check=False)
    fails = [l.split(" - ")[0].split("::")[-1] for l in r.stdout.splitlines() if l.startswith(("FAILED", "ERROR"))]
    return f"{r.stdout.strip().splitlines()[-1]} | {sorted(set(fails))}"


def main(commit: str = "ebccae1") -> None:
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        base = tmp / "src"
        base.mkdir()
        sh(f"git -C {REPO} archive {commit} | tar -x -C {base}", REPO)
        data = make_data(tmp / "data")
        # 1. reproducción
        code = ("from src.warehouse import db\n"
                "def _b(*a, **k): raise RuntimeError('warehouse bloqueado')\n"
                "db.connect = _b\n"
                "from src.labels import regime_us as R\nimport pandas as pd, json\n"
                "df, info = R.build(source='snapshot')\n"
                f"off = pd.read_parquet('{DATA / 'regime_us_v1.1.parquet'}')\n"
                "m = info['meta']\n"
                "print(json.dumps({'hash': R.content_hash(df), 'equals_official': bool(df.equals(off)),"
                " 'sha256_code': m['code']['sha256_code'], 'snap': m['inputs_snapshot']['sha256_file']}))\n")
        import os
        env = dict(os.environ, FIN_DATA_ROOT=str(data))
        out["reproduccion"] = json.loads(sh([PY, "-c", code], base, env).stdout)
        out["tests_arbol_limpio"] = pytest_failures(base, data)
        # 2. mutaciones de código
        mut = {}
        for name, patch in CODE_MUTANTS.items():
            tree = tmp / "mut"
            shutil.rmtree(tree, ignore_errors=True)
            shutil.copytree(base, tree)
            with open(tree / "src/labels/regime_us.py", "a") as fh:
                fh.write("\n" + patch)
            mut[name] = pytest_failures(tree, data)
        # mutaciones de datos
        for name, edit in {
            "instantánea recomprimida (mismo contenido)":
                (SNAP, "df.to_parquet(p, index=False, compression='gzip')"),
            "parquet oficial: p_expansion fila 400 +0.01":
                ("regime_us_v1.1.parquet", "df.loc[400, 'p_expansion'] += 0.01; df.to_parquet(p, index=False)"),
        }.items():
            d2 = make_data(tmp / f"d{len(mut)}")
            p = d2 / "labels" / edit[0]
            sh([PY, "-c", f"import pandas as pd; p='{p}'; df=pd.read_parquet(p); {edit[1]}"], base)
            mut[name] = pytest_failures(base, d2)
        out["mutaciones"] = mut
        # 3. lista negra (en el árbol limpio)
        code = ("import json\nfrom src.labels import regime_us as R\n"
                "cases = ['usrec_lag1','G_lag5','p_expansion_lag5','GDPPOT_yoy','LABEL_HARD','G.l5','max_prob-12m',"
                "'lag5_G','d_usrec','L5.usrec','yoy_GDPPOT','gap_GDPPOT','usrec1','Gl5','x_label_hard','lbl_hard_l5',"
                "'usrec:lag1','  usrec','INDPRO','fed_ebp','g_indpro','i_core']\n"
                "res = {}\n"
                "for c in cases + [('lag1', 'usrec')]:\n"
                "    try: R.assert_no_forbidden([c]); res[str(c)] = 'pasa'\n"
                "    except AssertionError: res[str(c)] = 'bloqueada'\n"
                "print(json.dumps(res))\n")
        env["FIN_DATA_ROOT"] = str(data)
        out["lista_negra"] = json.loads(sh([PY, "-c", code], base, env).stdout)
    # falsos positivos sobre el catálogo (warehouse real, solo lectura)
    code = ("import json\nfrom src.warehouse import db\nfrom src.labels import regime_us as R\n"
            "con = db.connect(read_only=True)\n"
            "cat = con.sql('select series_id, pit_role from catalog').df()\n"
            "m = json.load(open(R.out_path().with_suffix('.meta.json')))\n"
            "ser = set(m['forbidden_features']['series'])\n"
            "fl = sorted(set(R.FORBIDDEN_FEATURES) | ser, key=len, reverse=True)\n"
            "fp = [s for s in cat.series_id if R.forbidden_root(s, fl) and s not in ser]\n"
            "exp = set(cat.series_id[cat.pit_role.isin(['forecast', 'lookahead'])])\n"
            "print(json.dumps({'series': len(cat), 'bloqueadas_no_listadas': fp, 'meta_igual_catalogo': exp == ser}))\n")
    try:
        out["falsos_positivos"] = json.loads(sh([PY, "-c", code], REPO).stdout)
    except subprocess.CalledProcessError as e:
        out["falsos_positivos"] = {"error": e.stderr[-300:]}
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:])
