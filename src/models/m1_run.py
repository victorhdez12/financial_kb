"""Corridas del entregable 4 (M1 y clasificador de reglas) sobre el arnés v2, SOLO desarrollo ≤ 2004.

Especificación y orden congelados en `docs/models/m1_spec.md` (commit previo a cualquier resultado):

    .venv/bin/python -m src.models.m1_run placebo research/trials/m1_v1/placebo_m1_v1.json   # 1.º (antes de mirar M1)
    .venv/bin/python -m src.models.m1_run run --config config/harness/m1_logit_axis_v1.yaml --official
    .venv/bin/python -m src.models.m1_run run --config config/harness/m1_logit_axis_v1_long.yaml --official
    .venv/bin/python -m src.models.m1_run epocas <run_id_long> <run_id_core> <salida.json>
    .venv/bin/python -m src.models.m1_run analyze <run_id> <salida.json>

No modifica el núcleo del arnés: usa `harness.run(cfg, registry=...)` con los modelos de `models_logit` y
`models_rules`, y las funciones públicas del arnés (`placebo_data`, `report`, `sign_stability`, `vintage_breaks`).
"""
from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from src.models import base as B
from src.models import harness as H
from src.models import metrics as M
from src.models import models_logit as L
from src.models import models_rules as RU
from src.models import trials
from src.models import vault as V

REGISTRY = {**B.REGISTRY, **L.REGISTRY, **RU.REGISTRY}

# ------------------------------------------------------------------ placebo de M1 (m1_spec.md §5; fijado a priori)
PLACEBO_SEEDS = tuple(range(1, 21))
PLACEBO_TOL = 0.02                     # regla del arnés (§9b): fuga si la media pareada > 0,02 nats
SIGN_P, T_MAX = 0.01, 3.0              # regla complementaria del Validador (M2-5): aviso si signo p < 0,01 o t > 3
PLACEBO_SPECS = {                      # (I del eje, inicio de la ventana del placebo: tras el primer corte elegible)
    "m1_logit_axis": (L.M1_I_CORE, "1989-01"),
    "m1_logit_axis_hl": (L.M1_I_HEADLINE, "1976-01"),
}
CAND = ("cand_a", "cand_b", "cand_c")


def _placebo_cfg(name, models, mode, start):
    return H.HarnessConfig(name=name, models=tuple(models), modes=(mode,), test_start=start, test_end="2004-12",
                           refit_every=12, min_train_months=120, min_train_recessions=0, min_train_g_changes=0,
                           provisional_weighting="uno", baseline="m0_calibrated_persistence", reference=None,
                           epochs=(), who="Constructor (M1, placebo)")


def placebo_seed(pit, seed: int, spec: str, leak=None) -> dict:
    """Una permutación (etiqueta ≤ 2004 barajada en bloques de 24). Sin `leak`: Δ = ll(M0) − ll(M1) (el contraste
    pareado de M1: con frente a sin SUS variables, con su L2). Con `leak`: Δ_C = ll(M1) − ll(M1 + C) (potencia de la
    regla con la L2 de M1; C en los dos ejes)."""
    I, start = PLACEBO_SPECS[spec]
    data = H.placebo_data(pit, seed, leak=leak)
    reg = {"m0_calibrated_persistence": B.CalibratedPersistence, spec: lambda: L.LogitAxis(name=spec, I=I)}
    if leak is not None:
        data.X[list(CAND)] = data.X[list(CAND)].fillna(0.0)
        for c in CAND:
            data.colinfo[c] = {"estado": "principal", "start": data.X.index.min()}
        reg["m1_plus_c"] = lambda: L.LogitAxis(name="m1_plus_c", G=L.M1_G + CAND, I=I + CAND)
    r = H.run(_placebo_cfg(f"placebo_{spec}", reg, data.mode, start), registry=reg, datas={data.mode: data},
              record=False)
    m, k = r["report"]["modelos"], data.mode
    out = {"seed": seed, "n": r["report"]["muestra"]["n"]}
    if leak is None:
        a, b = m[f"{k}/m0_calibrated_persistence"], m[f"{k}/{spec}"]
    else:
        a, b = m[f"{k}/{spec}"], m[f"{k}/m1_plus_c"]
    out.update({"delta": a["logloss"] - b["logloss"], "delta_g": a["ll_g"] - b["ll_g"],
                "delta_i": a["ll_i"] - b["ll_i"]})
    return out


def placebo_rule(x: np.ndarray) -> dict:
    n, pos = len(x), int((x > 0).sum())
    p_sign = sum(math.comb(n, j) for j in range(pos, n + 1)) / 2 ** n        # unilateral, H0: P(>0) = 1/2
    t = float(x.mean() / (x.std(ddof=1) / math.sqrt(n))) if x.std(ddof=1) > 0 else float("nan")
    return {"media": float(x.mean()), "sd": float(x.std(ddof=1)), "frac_>0": pos / n, "signo_p_unilateral": p_sign,
            "t": t, "fuga_regla_0.02": bool(x.mean() > PLACEBO_TOL),
            "aviso_signo_o_t": bool(p_sign < SIGN_P or t > T_MAX)}


def run_placebo(dest: str) -> dict:
    from src.models import placebo as PL
    pit = H.PITData("vintage")
    out = {"diseño": {"semillas": list(PLACEBO_SEEDS), "bloque": 24, "refit_every": 12, "tol": PLACEBO_TOL,
                      "signo_p": SIGN_P, "t_max": T_MAX, "l2": L.L2_FEATURES, "l2_pers": L.L2_PERS}}
    cases = {"principal": None, "potencia_ruido": PL.noise(), "potencia_control_t-5": PL.leak_lag(5),
             "potencia_t+1_sd1": PL.leak_future(1.0), "potencia_t+1_sd2": PL.leak_future(2.0),
             "potencia_t_sd2": PL.leak_future(2.0, 0), "potencia_calendario_t-4": PL.leak_lag(4)}
    for spec in PLACEBO_SPECS:
        for case, leak in cases.items():
            if case != "principal" and spec != "m1_logit_axis_hl":
                continue                  # la tabla de potencia, solo con la especificación larga (más meses)
            rows = [placebo_seed(pit, s, spec, leak) for s in PLACEBO_SEEDS]
            res = {k: placebo_rule(np.array([r[k] for r in rows])) for k in ("delta", "delta_g", "delta_i")}
            res["por_semilla"] = [{k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()} for r in rows]
            out[f"{spec}/{case}"] = res
            print(spec, case, {k: res["delta"][k] for k in ("media", "frac_>0", "signo_p_unilateral", "t",
                                                           "fuga_regla_0.02", "aviso_signo_o_t")}, flush=True)
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


# ------------------------------------------------------------------ corridas oficiales
def run_config(path: str, official: bool) -> dict:
    if official:
        dirty = V._git_strict("status", "--porcelain", "--", "src", "config", "tests").strip()
        if dirty:
            raise SystemExit(f"--official con código sin commitear:\n{dirty}")
    cfg = H.HarnessConfig.from_yaml(path)
    res = H.run(cfg, registry=REGISTRY)
    rep = res["report"]
    print(json.dumps({"run_id": res["entry"]["run_id"], "muestra": rep["muestra"], "avisos": rep["avisos"],
                      "results_sha256": res["results_sha256"], "results_sha256_r10": res["results_sha256_r10"]},
                     indent=1, ensure_ascii=False))
    return res


def _load_run(run_id: str) -> tuple[dict, pd.DataFrame]:
    d = trials.runs_dir() / run_id
    return json.loads((d / "report.json").read_text()), pd.read_parquet(d / "scores.parquet")


def _cfg_from(conf: dict, **kw) -> H.HarnessConfig:
    c = {**conf, **kw}
    for k in ("models", "modes", "eval_window"):
        if c.get(k) is not None:
            c[k] = tuple(c[k])
    for k in ("epochs", "subperiods"):
        c[k] = tuple(tuple(x) for x in c.get(k, ()))
    return H.HarnessConfig(**c)


# ------------------------------------------------------------------ M1 por épocas (m1_spec.md §2b)
SWITCH = pd.Timestamp("1989-10-01")     # desde aquí el eje I con el subyacente es elegible en TODOS los cortes (§9)


def epocas(run_long: str, run_core: str, dest: str) -> dict:
    """M1 por épocas = M1 con el IPC general (m1_logit_axis_hl) antes de SWITCH y M1 con el subyacente
    (m1_logit_axis) desde SWITCH. El eje G es idéntico en las dos. Puntuaciones mes a mes de las dos corridas
    oficiales; el informe se recalcula con `harness.report` en la ventana de la corrida larga."""
    jl, Sl = _load_run(run_long)
    _, Sc = _load_run(run_core)
    a = Sl[(Sl["model"] == "m1_logit_axis_hl") & (Sl["month"] < SWITCH)]
    b = Sc[(Sc["model"] == "m1_logit_axis") & (Sc["month"] >= SWITCH)]
    ep = pd.concat([a, b]).assign(model="m1_epocas")
    S = pd.concat([Sl, ep], ignore_index=True).sort_values(["mode", "model", "month"]).reset_index(drop=True)
    n = S.groupby(["mode", "model"])["month"].nunique()
    assert n.nunique() == 1, f"la serie empalmada no cubre la ventana: {n.to_dict()}"
    cfg = _cfg_from(jl["config"], models=tuple(sorted(S["model"].unique())))
    labels = {m: H.PITData(m).score_labels(cfg.test_end) for m in sorted(S["mode"].unique())}
    rep = H.report(S, labels, cfg)
    out = {"run_largo": run_long, "run_subyacente": run_core, "switch": f"{SWITCH:%Y-%m}", "report": rep}
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_text(json.dumps(H._round(out, 10), indent=1, ensure_ascii=False, default=str))
    return out


# ------------------------------------------------------------------ signos y estabilidad de coeficientes
def coef_table(conf_diag: dict, mode: str, model: str) -> pd.DataFrame:
    rows = {}
    for d in conf_diag[mode]:
        if d["model"] != model or d.get("skipped") or not d.get("coef"):
            continue
        if any(e.get("skipped") for e in d.get("ejes", {}).values()):
            continue
        rows[pd.Timestamp(d["refit_month"])] = d["coef"]
    return pd.DataFrame.from_dict(rows, orient="index").sort_index()


def coef_summary(C: pd.DataFrame, breaks: dict) -> dict:
    out = {}
    for col in C.columns:
        if col.endswith("_const"):
            continue
        var = col.split("_", 1)[1]
        s = C[col].dropna()
        exp = L.EXPECTED_SIGN.get(var)
        out[col] = {"n_cortes": len(s), "media": float(s.mean()), "min": float(s.min()), "max": float(s.max()),
                    "ultimo": float(s.iloc[-1]), "signo_esperado": exp,
                    "frac_signo_esperado": float((np.sign(s) == exp).mean()) if exp else None,
                    "signo_medio_ok": bool(np.sign(s.mean()) == exp) if exp else None}
    renamed = C[[c for c in C.columns if not c.endswith("_const")]].rename(columns=lambda c: c.split("_", 1)[1])
    renamed = renamed.loc[:, ~renamed.columns.duplicated()]
    ss = H.sign_stability(renamed[[c for c in renamed.columns if c in breaks]], breaks)
    return {"coeficientes": out, "estabilidad_saltos": ss.to_dict(orient="records")}


def analyze(run_id: str, dest: str) -> dict:
    j, _ = _load_run(run_id)
    out = {"run_id": run_id}
    models = [m for m in j["config"]["models"] if m.startswith("m1_")]
    for mode in j["diag"]:
        br = H.vintage_breaks(H.PITData(mode))
        for model in models:
            C = coef_table(j["diag"], mode, model)
            if len(C):
                # los saltos se comprueban por eje: G_x y I_x comparten nombre de variable solo si están en los dos
                out[f"{mode}/{model}"] = {ax: coef_summary(C[[c for c in C.columns if c.startswith(ax + "_")]], br)
                                          for ax in ("G", "I")}
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_text(json.dumps(H._round(out, 10), indent=1, ensure_ascii=False, default=str))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Entregable 4 (M1, reglas): solo desarrollo ≤ 2004")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("placebo")
    p.add_argument("dest")
    r = sp.add_parser("run")
    r.add_argument("--config", required=True)
    r.add_argument("--official", action="store_true")
    e = sp.add_parser("epocas")
    e.add_argument("run_long")
    e.add_argument("run_core")
    e.add_argument("dest")
    a = sp.add_parser("analyze")
    a.add_argument("run_id")
    a.add_argument("dest")
    x = ap.parse_args()
    if x.cmd == "placebo":
        os.environ.setdefault("FKB_TRIALS_DIR", str(Path(x.dest).resolve().parent / "trials_tmp"))
        run_placebo(x.dest)
    elif x.cmd == "run":
        run_config(x.config, x.official)
    elif x.cmd == "epocas":
        epocas(x.run_long, x.run_core, x.dest)
    else:
        analyze(x.run_id, x.dest)


if __name__ == "__main__":
    main()
