"""Corridas de M1 v2 (H-M1-002) sobre el arnés v2.1 con la base PIT v0.4 candidata, SOLO desarrollo ≤ 2004.

Especificación y orden congelados en `docs/models/m1_v2_spec.md` (commit previo a cualquier corrida con la etiqueta).
UNA sola pasada; no se itera mirando sus resultados:

    .venv/bin/python -m src.models.m1v2_run placebo research/trials/m1_v2/placebo_m1_v2.json   # 1.º (antes de M1 v2)
    .venv/bin/python -m src.models.m1v2_run run --config config/harness/m1v2_principal.yaml --official
    .venv/bin/python -m src.models.m1v2_run run --config config/harness/m1v2_long.yaml --official
    .venv/bin/python -m src.models.m1v2_run run --config config/harness/m1v2_sens.yaml --official
    .venv/bin/python -m src.models.m1v2_run analyze <run_id> <salida.json>                  # coeficientes y signos
    .venv/bin/python -m src.models.m1v2_run compare <run_id> <modelo_a> <modelo_b> <salida.json>   # a − b pareado

No modifica el núcleo del arnés: reutiliza `m1_run` (reglas del placebo, coeficientes) y `harness`.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np

from src.models import base as B
from src.models import harness as H
from src.models import m1_run as M1R
from src.models import metrics as M
from src.models import models_logit as L

PIT_VERSION = "0.4"
REGISTRY = M1R.REGISTRY            # incluye los modelos de M1 v2 (models_logit.REGISTRY)
PLACEBO_SEEDS = M1R.PLACEBO_SEEDS  # 1…20, bloque 24, refit 12; reglas: media > 0,02 (fuga), signo p < 0,01 o t > 3 (aviso)
PLACEBO_SPECS = {                  # (factoría, inicio de la ventana del placebo: tras el primer corte elegible)
    "m1v2_logit_axis": (lambda **kw: L.LogitAxisV2(name="m1v2_logit_axis", **kw), "1990-01"),
    "m1v2_g": (lambda **kw: L.LogitAxisV2(name="m1v2_g", I=(), i_structural=False, **kw), "1979-01"),
}
CAND = M1R.CAND


def placebo_seed(pit, seed: int, spec: str, leak=None) -> dict:
    """Δ = ll(M0) − ll(M1 v2) con la etiqueta ≤ 2004 barajada en bloques de 24 (sin `leak`); con `leak`,
    Δ_C = ll(M1 v2) − ll(M1 v2 + C) con C en los dos ejes (potencia con la L2 de M1 v2)."""
    make, start = PLACEBO_SPECS[spec]
    data = H.placebo_data(pit, seed, leak=leak)
    reg = {"m0_calibrated_persistence": B.CalibratedPersistence, spec: lambda: make()}
    if leak is not None:
        data.X[list(CAND)] = data.X[list(CAND)].fillna(0.0)
        for c in CAND:
            data.colinfo[c] = {"estado": "principal", "start": data.X.index.min()}
        base = make()
        G, I = base.axis_features["G"], base.axis_features["I"]
        reg["m1_plus_c"] = lambda: L.LogitAxisV2(name="m1_plus_c", G=G + CAND, I=I + CAND,
                                                 i_structural=bool(base.structural))
    cfg = M1R._placebo_cfg(f"placebo_{spec}", reg, data.mode, start)
    r = H.run(cfg, registry=reg, datas={data.mode: data}, record=False)
    m, k = r["report"]["modelos"], data.mode
    a, b = (m[f"{k}/m0_calibrated_persistence"], m[f"{k}/{spec}"]) if leak is None else \
        (m[f"{k}/{spec}"], m[f"{k}/m1_plus_c"])
    return {"seed": seed, "n": r["report"]["muestra"]["n"], "delta": a["logloss"] - b["logloss"],
            "delta_g": a["ll_g"] - b["ll_g"], "delta_i": a["ll_i"] - b["ll_i"]}


def run_placebo(dest: str) -> dict:
    from src.models import placebo as PL
    pit = H.PITData("vintage", pit_version=PIT_VERSION)
    out = {"diseño": {"semillas": list(PLACEBO_SEEDS), "bloque": 24, "refit_every": 12, "tol": M1R.PLACEBO_TOL,
                      "signo_p": M1R.SIGN_P, "t_max": M1R.T_MAX, "l2": L.L2_FEATURES, "l2_pers": L.L2_PERS,
                      "pit_version": PIT_VERSION}}
    cases = {"principal": None, "potencia_ruido": PL.noise(), "potencia_control_t-5": PL.leak_lag(5),
             "potencia_t+1_sd1": PL.leak_future(1.0), "potencia_t+1_sd2": PL.leak_future(2.0),
             "potencia_t_sd2": PL.leak_future(2.0, 0), "potencia_calendario_t-4": PL.leak_lag(4)}
    for spec in PLACEBO_SPECS:
        for case, leak in cases.items():
            if case != "principal" and spec != "m1v2_g":
                continue                  # la tabla de potencia, solo con la especificación larga (más meses)
            rows = [placebo_seed(pit, s, spec, leak) for s in PLACEBO_SEEDS]
            res = {k: M1R.placebo_rule(np.array([r[k] for r in rows])) for k in ("delta", "delta_g", "delta_i")}
            res["por_semilla"] = [{k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()} for r in rows]
            out[f"{spec}/{case}"] = res
            print(spec, case, {k: res["delta"][k] for k in ("media", "frac_>0", "signo_p_unilateral", "t",
                                                           "fuga_regla_0.02", "aviso_signo_o_t")}, flush=True)
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


def compare(run_id: str, a: str, b: str, dest: str) -> dict:
    """Contraste PAREADO a − b (mejora de b sobre a, positivo = b mejor) en la misma corrida y los mismos meses, con el
    bootstrap por bloques del arnés: total, ejes, giro/estable y detección (v2.1)."""
    j, S = M1R._load_run(run_id)
    cfg = M1R._cfg_from(j["config"])
    out = {"run_id": run_id, "a": a, "b": b}
    for mode in sorted(S["mode"].unique()):
        sa = S[(S["mode"] == mode) & (S["model"] == a)].set_index("month").sort_index()
        sb = S[(S["mode"] == mode) & (S["model"] == b)].set_index("month").sort_index().loc[sa.index]
        lab = H.PITData(mode, pit_version=cfg.pit_version).score_labels(cfg.test_end)
        cuts = M.month_cuts(lab.loc[lab.index <= sa.index.max()]).loc[sa.index]
        g = cuts["giro"].to_numpy()
        d = (sa["logloss"] - sb["logloss"]).to_numpy()
        out[mode] = {"n": int(len(d)), "mejora_logloss": M.boot_mean(d),
                     "mejora_ll_g": M.boot_mean((sa["ll_g"] - sb["ll_g"]).to_numpy()),
                     "mejora_ll_i": M.boot_mean((sa["ll_i"] - sb["ll_i"]).to_numpy()),
                     "giro": M.boot_mean(d[g]), "estable": M.boot_mean(d[~g]),
                     "deteccion_b_frente_a_a": M.detection_vs(j["report"]["deteccion_giros_g"][f"{mode}/{b}"],
                                                              j["report"]["deteccion_giros_g"][f"{mode}/{a}"])}
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_text(json.dumps(H._round(out, 10), indent=1, ensure_ascii=False, default=str))
    return out


def analyze(run_id: str, dest: str) -> dict:
    """Coeficientes por corte, fracción con el signo preregistrado y estabilidad en los saltos de vintage (como M1 v1)."""
    j, _ = M1R._load_run(run_id)
    out = {"run_id": run_id}
    models = [m for m in j["config"]["models"] if m.startswith("m1")]
    for mode in j["diag"]:
        br = H.vintage_breaks(H.PITData(mode, pit_version=j["config"].get("pit_version", "0.3")))
        for model in models:
            C = M1R.coef_table(j["diag"], mode, model)
            if len(C):
                out[f"{mode}/{model}"] = {ax: M1R.coef_summary(C[[c for c in C.columns if c.startswith(ax + "_")]], br)
                                          for ax in ("G", "I")}
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_text(json.dumps(H._round(out, 10), indent=1, ensure_ascii=False, default=str))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="M1 v2: solo desarrollo ≤ 2004")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("placebo")
    p.add_argument("dest")
    r = sp.add_parser("run")
    r.add_argument("--config", required=True)
    r.add_argument("--official", action="store_true")
    a = sp.add_parser("analyze")
    a.add_argument("run_id")
    a.add_argument("dest")
    c = sp.add_parser("compare")
    c.add_argument("run_id")
    c.add_argument("a")
    c.add_argument("b")
    c.add_argument("dest")
    x = ap.parse_args()
    if x.cmd == "placebo":
        os.environ.setdefault("FKB_TRIALS_DIR", str(Path(x.dest).resolve().parent / "trials_tmp"))
        run_placebo(x.dest)
    elif x.cmd == "run":
        M1R.run_config(x.config, x.official)
    elif x.cmd == "analyze":
        analyze(x.run_id, x.dest)
    else:
        compare(x.run_id, x.a, x.b, x.dest)


if __name__ == "__main__":
    main()
