"""Pasos previos a la corrida de desarrollo de M2/M3/pool (specs v1.2: m2_structural_spec.md §6, m3_tvtp_spec.md §5,
pool_spec.md §5, §7). SOLO desarrollo ≤ 2004. Ninguno corre M2, M3 ni el pool con la etiqueta REAL:

    .venv/bin/python -m src.models.pool_dev revtable            # 3. tabla v(edad) de M2, SIN etiqueta
    .venv/bin/python -m src.models.pool_dev probe               # 4. sonda de elegibilidad: solo recuentos (W_G, pool)
    .venv/bin/python -m src.models.pool_dev placebo <cuál>      # 5. placebos (etiqueta ≤ 2004 BARAJADA): m2 | m3 | pool
    .venv/bin/python -m src.models.pool_dev controls            # señal plantada y controles SINTÉTICOS

Salidas en research/trials/m2/ (tabla, sonda, placebos, controles) y una fila en el trial log por paso.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.models import base as B
from src.models import harness as H
from src.models import models_pool as MP
from src.models import models_struct as MS
from src.models import models_tvtp as MT
from src.models import vault as V

PIT_VERSION = "0.4"
OUT = H.REPO / "research" / "trials" / "m2"
SEEDS = tuple(range(1, 21))
TOL, SIGN_P, T_MAX = 0.02, 0.01, 3.0
M2_FEATS = tuple(MS.S.extra_features)
M3_FEATS = tuple(MT.TVTPG.axis_features["G"])


def _trial_log(quien: str, que: str, datos: str, n: str, res: str) -> None:
    from src.models import trials
    with open(trials.trial_log_path(), "a") as fh:
        fh.write(f"| {pd.Timestamp.now():%Y-%m-%d} | {quien} | {que} | {datos} | {n} | {res} |\n")


def _dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(H._round(obj, 10), indent=1, ensure_ascii=False, default=str))


# ------------------------------------------------------------------ 3. tabla v(edad)
def revtable(dest: Path = MS.REVISION_TABLE) -> dict:
    """Tabla v(edad) principal (m2_structural_spec.md §4): vintages ≤ 2004 de INDPRO y PAYEMS, SIN etiqueta."""
    d = H.PITData("vintage", pit_version=PIT_VERSION)
    tab = MS.build_revision_table(d.labeler, d.decision)
    tab["generado"] = pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")
    _dump(dest, tab)
    _trial_log("Constructor (M2)", "**Tabla v(edad) de M2** (spec §4; antes de cualquier carga de la etiqueta para "
               "M2): vintages ALFRED de INDPRO/PAYEMS de la instantánea congelada, fechas de decisión y meses ≤ 2004-12; "
               "Var(r) en la última vintage 1968-06 → 2004-12. Declarada NO PIT", "≤ 2004 (niveles; sin etiqueta)",
               "1 tabla", f"`{dest.relative_to(H.REPO)}`")
    return tab


# ------------------------------------------------------------------ 4. sonda de elegibilidad
def _axis_elig(data, cfg, tr, feats):
    start = H.axis_window_start(list(feats), data)
    sub = tr if start is None else tr[tr.index >= start]
    Xtr = data.X.loc[sub.index, list(feats)].dropna()
    Y = sub.loc[Xtr.index, H.P_COLS].to_numpy(float)
    n_rec = H.count_recessions(data.usrec, Xtr.index.min(), Xtr.index.max()) if len(Xtr) else 0
    n_g = H.count_g_changes(Y)
    return H._eligible(cfg, len(Xtr), n_rec, n_g), len(Xtr), n_rec, n_g, Xtr.index


def probe(dest: Path = OUT / "elegibilidad.json") -> dict:
    """Sonda (m2_structural_spec.md §6 paso 4; pool_spec.md §5): SOLO RECUENTOS, no puntúa nada ni corre ningún
    modelo. Por corte (1956-10 → 2004-12, refit 1, embargo 6, madurez) y modo: elegibilidad de los ejes G de M2 y de
    M3 con los mínimos del arnés (lee la etiqueta RECALCULADA ≤ T para contar cambios de G, como el arnés).
    W_G = primer corte desde el que M2 y M3 son elegibles en todos los cortes siguientes de los dos modos.
    Activación del pool = primer corte ≥ W_G con |S| ≥ 60 (S = meses de entrenamiento del eje G del pool ≥ W_G, que es
    cuando M2 y M3 empiezan a predecir); ventana principal del pool = primer enero ≥ activación. Se informa también la
    activación con `excluir`."""
    cfg = H.HarnessConfig(name="sonda_pool", models=("m0_calibrated_persistence",), modes=("vintage", "latest_truncated"),
                          test_start="1956-10", test_end="2004-12", pit_version=PIT_VERSION,
                          baseline="m0_calibrated_persistence")
    V.log_access({"mode": "development", "granted": True, "event": "sonda de elegibilidad M2/M3/pool (solo recuentos "
                  "de la etiqueta RECALCULADA ≤ T; sin puntuar)", "hasta": "2004-12"})
    rows, act = [], {}
    for mode in cfg.modes:
        data = H.PITData(mode, pit_version=PIT_VERSION)
        months = data.X.index
        test = months[(months >= H._month(cfg.test_start)) & (months <= H._month(cfg.test_end))]
        for m0 in test:
            lab = data.train_targets(m0)
            cut = H._add(m0, -cfg.embargo_months)
            tr0 = lab[(lab.index <= cut) & (lab["weight"] > 0)]
            tr0 = tr0[tr0.index.isin(months)]
            r = {"modo": mode, "corte": f"{m0:%Y-%m}"}
            for how in ("madurez", "excluir"):
                w = H.train_weights(tr0, m0, how)
                tr = tr0[w > 0]
                if how == "madurez":
                    for nm, feats in (("m2_G", M2_FEATS), ("m3_G", M3_FEATS), ("I", ())):
                        ok, n, nr, ng, _ = _axis_elig(data, cfg, tr, feats)
                        r.update({f"{nm}_elegible": bool(ok), f"{nm}_n": n, f"{nm}_rec": nr, f"{nm}_cambios_g": ng})
                ok, n, nr, ng, idx = _axis_elig(data, cfg, tr, ())
                r[f"pool_meses_{how}"] = [f"{x:%Y-%m}" for x in idx]
            rows.append(r)
    df = pd.DataFrame(rows)
    ok = df.groupby("corte")[["m2_G_elegible", "m3_G_elegible", "I_elegible"]].all().all(axis=1).sort_index()
    bad = ok[~ok]
    cand = ok.index[ok.index > bad.index.max()] if len(bad) else ok.index
    WG = pd.Timestamp(cand.min() + "-01")
    out = {"W_G": f"{WG:%Y-%m}", "regla": probe.__doc__}
    for how in ("madurez", "excluir"):
        a = None
        for mode in cfg.modes:
            sub = df[df["modo"] == mode]
            for _, r in sub.iterrows():
                m0 = pd.Timestamp(r["corte"] + "-01")
                if m0 < WG:
                    continue
                if sum(pd.Timestamp(x + "-01") >= WG for x in r[f"pool_meses_{how}"]) >= MP.PS.n_min:
                    a = m0 if a is None else max(a, m0)
                    break
        act[how] = a
        jan = pd.Timestamp(f"{a.year + (a.month > 1)}-01-01") if a is not None else None
        out[f"activacion_pool_{how}"] = f"{a:%Y-%m}" if a is not None else None
        out[f"ventana_pool_{how}"] = [f"{jan:%Y-%m}", "2004-12"] if jan is not None else None
    df = df.drop(columns=[c for c in df.columns if c.startswith("pool_meses_")])
    out["por_corte"] = df.to_dict("records")
    first = {}
    for mode in cfg.modes:
        s = df[df["modo"] == mode]
        for nm in ("m2_G", "m3_G", "I"):
            e = s[s[f"{nm}_elegible"]]
            first[f"{mode}/{nm}"] = e["corte"].min() if len(e) else None
    out["primer_corte_elegible"] = first
    _dump(dest, out)
    _trial_log("Constructor (M2/M3/pool)", "**Sonda de elegibilidad** (solo recuentos de meses, recesiones y cambios de "
               "G de la etiqueta recalculada ≤ T; ningún modelo, ninguna puntuación)", "≤ 2004", f"{len(df)} cortes",
               f"W_G = {out['W_G']}; pool: activación {out['activacion_pool_madurez']} → ventana "
               f"{out['ventana_pool_madurez']}; con excluir {out['activacion_pool_excluir']}. "
               f"`{dest.relative_to(H.REPO)}`")
    return out


# ------------------------------------------------------------------ 5. placebos
def placebo_rule(x) -> dict:
    x = np.asarray(x, float)
    n, pos = len(x), int((x > 0).sum())
    p_sign = sum(math.comb(n, j) for j in range(pos, n + 1)) / 2 ** n
    sd = x.std(ddof=1)
    t = float(x.mean() / (sd / math.sqrt(n))) if sd > 0 else float("nan")
    return {"media": float(x.mean()), "sd": float(sd), "frac_>0": pos / n, "signo_p_unilateral": p_sign, "t": t,
            "fuga_regla_0.02": bool(x.mean() > TOL), "aviso_signo_o_t": bool(p_sign < SIGN_P or (t == t and t > T_MAX))}


def _placebo_cfg(name, models, mode, start, eval_window=None):
    return H.HarnessConfig(name=name, models=tuple(models), modes=(mode,), test_start=start, test_end="2004-12",
                           eval_window=eval_window, refit_every=12, min_train_months=120, min_train_recessions=0,
                           min_train_g_changes=0, provisional_weighting="uno", baseline="m0_calibrated_persistence",
                           reference=None, epochs=(), pit_version=PIT_VERSION, who="Constructor (placebo M2/M3/pool)")


PLACEBO = {   # modelo → (modelos de la corrida, modelo contrastado)
    "m2": (("m0_calibrated_persistence", "m2_struct_g"), "m2_struct_g"),
    "m3": (("m0_calibrated_persistence", "m3_tvtp_g"), "m3_tvtp_g"),
    "pool": (("m0_calibrated_persistence", "m2_struct_g", "m3_tvtp_g", "pool_g"), "pool_g"),
}


def placebo(which: str, dest: Path | None = None, seeds=SEEDS) -> dict:
    """Placebo pareado (arnés §9b; specs M2 §6, M3 §5, pool §5): etiqueta oficial ≤ 2004 BARAJADA en bloques de 24,
    semillas 1…20, refit cada 12; variables y niveles PIT reales. Δ = ll(M0) − ll(modelo). Fuga si la media > 0,02;
    aviso si signo p < 0,01 o t > 3. Ventanas por regla desde la sonda: M2/M3 desde el primer enero ≥ W_G; el pool,
    con la misma historia, puntúa desde el primer enero ≥ su activación (antes es M0 por construcción). M2 no usa la
    etiqueta (sus predicciones son las mismas en todas las semillas: caché compartida); M0, M3 y el pool se reajustan
    con la etiqueta barajada."""
    el = json.loads((OUT / "elegibilidad.json").read_text())
    WG = pd.Timestamp(el["W_G"] + "-01")
    start = f"{WG.year + (WG.month > 1)}-01"
    models, target = PLACEBO[which]
    ew = None
    if which == "pool":
        # activación del placebo (refit 12): primer enero con ≥ 60 meses de las tres predicciones (≥ start) hasta m0 − 6
        j = pd.Timestamp(start + "-01")
        while len(pd.date_range(start + "-01", H._add(j, -6), freq="MS")) < MP.PS.n_min:
            j = H._add(j, 12)
        ew = (f"{j:%Y-%m}", "2004-12")
    pit = H.PITData("vintage", pit_version=PIT_VERSION)
    reg = H.model_registry()
    rows = []
    t0 = time.time()
    for s in seeds:
        data = H.placebo_data(pit, s, pit_levels=True)
        cfg = _placebo_cfg(f"placebo_{which}", models, data.mode, start, ew)
        r = H.run(cfg, registry=reg, datas={data.mode: data}, record=False)
        m, k = r["report"]["modelos"], data.mode
        a, b = m[f"{k}/m0_calibrated_persistence"], m[f"{k}/{target}"]
        row = {"seed": s, "n": r["report"]["muestra"]["n"], "desde": r["report"]["muestra"]["desde"],
               "delta": a["logloss"] - b["logloss"], "delta_g": a["ll_g"] - b["ll_g"], "delta_i": a["ll_i"] - b["ll_i"]}
        if which == "pool":
            co = [x["coef"] for x in r["diag"][k] if x["model"] == "pool_g" and x.get("coef")]
            row["pesos_2004"] = {c: co[-1][c] for c in ("G:w_m0", "G:w_m2", "G:w_m3", "G:blp_a", "G:blp_b")}
        rows.append(row)
        print(which, s, {kk: (round(v, 5) if isinstance(v, float) else v) for kk, v in row.items()},
              f"{time.time() - t0:.0f}s", flush=True)
    out = {"diseño": {"semillas": list(seeds), "bloque": 24, "refit_every": 12, "tol": TOL, "signo_p": SIGN_P,
                      "t_max": T_MAX, "pit_version": PIT_VERSION, "modelos": list(models), "test_start": start,
                      "eval_window": list(ew) if ew else None, "W_G": el["W_G"]},
           "delta": placebo_rule([r["delta"] for r in rows]), "delta_g": placebo_rule([r["delta_g"] for r in rows]),
           "delta_i": placebo_rule([r["delta_i"] for r in rows]), "por_semilla": rows,
           "segundos": round(time.time() - t0, 1)}
    dest = dest or OUT / f"placebo_{which}.json"
    _dump(dest, out)
    d = out["delta"]
    _trial_log(f"Constructor ({which.upper()})", f"**Placebo pareado de {target}** ANTES de la etiqueta real (etiqueta "
               f"oficial ≤ 2004 barajada en bloques de 24, 20 semillas, refit 12, base v{PIT_VERSION}, "
               f"desde {start}{'; puntúa ' + ew[0] + ' → ' + ew[1] if ew else ''})", "≤ 2004 (etiqueta barajada)",
               "20 semillas (corridas `record=False`)",
               f"Δ = ll(M0) − ll({target}) = {d['media']:+.4f} ({d['frac_>0']:.0%} > 0, signo p {d['signo_p_unilateral']:.3g}, "
               f"t {d['t']:.2f}): fuga {'SÍ' if d['fuga_regla_0.02'] else 'no'}, aviso "
               f"{'SÍ' if d['aviso_signo_o_t'] else 'no'}. `{dest.relative_to(H.REPO)}`")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="M2/M3/pool: pasos previos (solo ≤ 2004; nunca la etiqueta real)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("revtable")
    sp.add_parser("probe")
    p = sp.add_parser("placebo")
    p.add_argument("which", choices=sorted(PLACEBO) + ["all"])
    sp.add_parser("controls")
    a = ap.parse_args()
    if a.cmd == "revtable":
        revtable()
    elif a.cmd == "probe":
        print(json.dumps({k: v for k, v in probe().items() if k != "por_corte"}, indent=1, ensure_ascii=False))
    elif a.cmd == "placebo":
        for w in (("m2", "m3", "pool") if a.which == "all" else (a.which,)):   # un proceso: cachés compartidas
            print(json.dumps({k: v for k, v in placebo(w).items() if k != "por_semilla"}, indent=1,
                             ensure_ascii=False), flush=True)
    else:
        from src.models import pool_controls
        pool_controls.main()


if __name__ == "__main__":
    main()
