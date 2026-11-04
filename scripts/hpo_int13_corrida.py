"""HPO-INT13 (EXPLORATORIO): ajuste de hiperparámetros anidado del XGBoost por paquetes de INT-13.

Plan: docs/int/HPO_INT13_exploratorio.md (§1-§6 fijados y commiteados ANTES de esta corrida). Datos ≤ 2004; nada ≥ 2005.

Uso: .venv/bin/python -m scripts.hpo_int13_corrida            real (una vez) + placebo (reanudable) + informe
     .venv/bin/python -m scripts.hpo_int13_corrida --sintetico datos SINTÉTICOS, presupuesto mínimo; no escribe nada
Puerta: árbol limpio; la parte real se niega a repetirse si ya existe real.json; cada réplica placebo exige el MISMO
commit que la parte real (si falta alguna réplica tras un corte, se reanuda con semillas fijas, sin cambiar código).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from scripts import int13_corrida as C
from src.intl import hpo_int13 as H
from src.intl import int13 as M

REPO = Path(__file__).resolve().parents[1]
DIR = REPO / "research/int/hpo_int13"
PLAN = "docs/int/HPO_INT13_exploratorio.md"
N_JOBS = int(os.environ.get("HPO_N_JOBS", "12"))
FRASE = "exploratorio: cualquier hallazgo necesita prerregistro y confirmación en vivo o en el bloqueado"
_limpio = C._limpio


def muestras(crudo: dict) -> dict:
    df = M.construir(crudo)
    if df.fecha.max() > M.FIN_DEV:
        raise RuntimeError("filas posteriores a 2004")
    return {o: M.muestra(df, o) for o in H.OBJ_HPO}


# ---------------------------------------------------------------- parte real
def parte_real(Ss: dict, cfgs: list, reps: int, max_rondas: int, guardar: Path | None) -> dict:
    comps = H.comparaciones()
    modelos = ["clima", "base"] + [f"{f}_{m}" for m in H.MODELOS for f in ("hpo", "def", "lgt")]
    res, registro = {}, []
    for obj, S in Ss.items():
        res[obj] = {"filas": int(len(S)), "eventos": int(S[f"y_{obj}"].sum()),
                    "meses_con_evento": int(S.loc[S[f"y_{obj}"] == 1, "fecha"].nunique()),
                    "paises": sorted(S.pais.unique().tolist())}
        for tipo, nom in (("loco", "V1_loco"), ("temporal", "V2_temporal")):
            t = time.time()
            P, reg = H.evaluar_externo(S, obj, tipo, cfgs, N_JOBS, max_rondas)
            registro += reg
            boot = M.bloques_meses(P["fecha"], reps=reps)
            res[obj][nom] = {"filas": int(len(P)), "eventos": int(P.y.sum()),
                             "metricas": {m: M.metricas(P, m, boot) for m in modelos},
                             "comparaciones": {k: M.comparar(P, a, b, boot) for k, (a, b) in comps.items()}}
            if guardar is not None:
                P.to_csv(guardar / f"pred_{obj}_{nom}.csv.gz", index=False)
            print(f"{obj} {nom}: {len(P)} filas, {time.time() - t:.0f} s", flush=True)
    return {"objetivos": res, "registro": registro}


# ---------------------------------------------------------------- placebo
def replica_placebo(S: pd.DataFrame, obj: str, r: int, cfgs: list, max_rondas: int) -> dict:
    k = H.OBJ_HPO.index(obj)
    Sp = H.permutar_bloques(S, obj, seed=H.SEMILLA_HPO + 1000 * (k + 1) + r)
    P, reg = H.evaluar_externo(Sp, obj, "loco", cfgs, N_JOBS, max_rondas)
    d = {nom: H.dll_puntual(P, a, b) for nom, (a, b) in H.comparaciones().items()}
    opt = {pq: float(np.mean([g["ll_interna_default"] - g["ll_interna"] for g in reg if g["paquete"] == pq]))
           for pq in M.PAQUETES}
    cfg = {pq: [g["cfg_elegida"] for g in reg if g["paquete"] == pq] for pq in M.PAQUETES}
    return {"objetivo": obj, "replica": r, "dlogloss_V1": d, "optimismo_interno": opt, "cfg_elegidas": cfg}


def optimismo_real(registro: list, obj: str) -> dict:
    return {pq: float(np.mean([g["ll_interna_default"] - g["ll_interna"] for g in registro
                               if g["paquete"] == pq and g["objetivo"] == obj and g["validacion"] == "loco"]))
            for pq in M.PAQUETES}


# ---------------------------------------------------------------- decisión (reglas del plan §5)
def decidir(real: dict, plac: dict) -> dict:
    from src.intl.int13 import holm
    R = real["objetivos"]
    f1 = {f"{o}|hpo_{m}_vs_base": R[o]["V1_loco"]["comparaciones"][f"hpo_{m}_vs_base"]["dlogloss"]["p_mejora"]
          for o in R for m in H.MODELOS}
    f2 = {f"{o}|hpo_{m}_vs_def": R[o]["V1_loco"]["comparaciones"][f"hpo_{m}_vs_def"]["dlogloss"]["p_mejora"]
          for o in R for m in H.MODELOS}
    h1, h2 = holm(f1), holm(f2)
    filas = []
    for o in R:
        reps = plac.get(o, [])
        for m in H.MODELOS:
            c1 = R[o]["V1_loco"]["comparaciones"]
            c2 = R[o]["V2_temporal"]["comparaciones"]
            pp = {}
            for comp in (f"hpo_{m}_vs_base", f"hpo_{m}_vs_def", f"hpo_{m}_vs_lgt", f"def_{m}_vs_base"):
                real_d = c1[comp]["dlogloss"]["est"]
                nul = np.array([x["dlogloss_V1"][comp] for x in reps], float)
                pp[comp] = {"real": real_d, "p_placebo": float((1 + np.sum(nul <= real_d)) / (len(nul) + 1))
                            if len(nul) else None,
                            "placebo_media": float(nul.mean()) if len(nul) else None,
                            "placebo_p05": float(np.percentile(nul, 5)) if len(nul) else None,
                            "placebo_min": float(nul.min()) if len(nul) else None,
                            "z_placebo": float((real_d - nul.mean()) / nul.std(ddof=1))
                            if len(nul) > 1 and nul.std(ddof=1) > 0 else None}
            pend = R[o]["V1_loco"]["metricas"][f"hpo_{m}"]["calibracion"]["pendiente"]
            regla13 = bool(h1[f"{o}|hpo_{m}_vs_base"]["rechaza"] and c2[f"hpo_{m}_vs_base"]["dlogloss"]["est"] < 0
                           and pend is not None and 0.5 <= pend <= 1.5)
            z = pp[f"hpo_{m}_vs_def"]["z_placebo"]
            ajuste = bool(h2[f"{o}|hpo_{m}_vs_def"]["rechaza"] and z is not None and z <= -1.645
                          and c2[f"hpo_{m}_vs_def"]["dlogloss"]["est"] < 0)
            filas.append({"objetivo": o, "modelo": m,
                          "hpo_vs_base_V1": c1[f"hpo_{m}_vs_base"]["dlogloss"], "p_holm_F1": h1[f"{o}|hpo_{m}_vs_base"]["p_holm"],
                          "hpo_vs_base_V2": c2[f"hpo_{m}_vs_base"]["dlogloss"]["est"],
                          "hpo_vs_def_V1": c1[f"hpo_{m}_vs_def"]["dlogloss"], "p_holm_F2": h2[f"{o}|hpo_{m}_vs_def"]["p_holm"],
                          "hpo_vs_def_V2": c2[f"hpo_{m}_vs_def"]["dlogloss"]["est"],
                          "hpo_vs_lgt_V1": c1[f"hpo_{m}_vs_lgt"]["dlogloss"],
                          "hpo_vs_lgt_V2": c2[f"hpo_{m}_vs_lgt"]["dlogloss"]["est"],
                          "pendiente_cal_V1": pend, "placebo": pp, "regla_int13": regla13,
                          "ajuste_supera_placebo": ajuste, "destaca": bool(regla13 and ajuste)})
    return {"n_pruebas_F1": len(f1), "n_pruebas_F2": len(f2), "tabla": filas,
            "destacan": [(r["objetivo"], r["modelo"]) for r in filas if r["destaca"]]}


def config_final(S: pd.DataFrame, obj: str, cfgs: list, max_rondas: int) -> dict:
    """Solo si algo destaca: búsqueda interna (3 grupos de países) sobre TODA la muestra ≤ 2004, por paquete."""
    from joblib import Parallel, delayed

    def uno(pq):
        S0 = S.reset_index(drop=True)
        Sm, n = H.curvas_internas(S0, obj, M.PAQUETES[pq], H.pliegues_internos_loco(S0), cfgs, max_rondas)
        e = H.elegir(Sm, n)
        return pq, {"cfg": e["cfg"], "params": cfgs[e["cfg"]], "rondas": e["rondas"], "ll_interna": e["ll_interna"]}
    return dict(Parallel(n_jobs=min(N_JOBS, 6), backend="loky")(delayed(uno)(pq) for pq in M.PAQUETES))


# ---------------------------------------------------------------- informe
_f, _ic = C._f, C._ic


def informe(out: dict) -> str:
    d = out["decision"]
    L = ["---", "documento: Resultado HPO-INT13 (EXPLORATORIO): ajuste de hiperparámetros anidado del XGBoost por paquetes",
         f"plan: {PLAN} ({out['plan_commit']})", f"procedencia: {out['procedencia']}",
         f"placebo: {out['placebo_reps']} réplicas por objetivo (V1)", "datos: ≤ 2004. NADA ≥ 2005", "---", "",
         "# HPO-INT13: ¿el ajuste hace que XGBoost bata al logit por encima del ruido de la búsqueda?", "",
         f"> **{FRASE[0].upper() + FRASE[1:]}.** Contaminación adicional: mismos datos ≤ 2004 que INT-13 y que el "
         "desarrollo de E1.", "",
         f"**Pruebas:** F1 = {d['n_pruebas_F1']} (ajustado frente a base, V1, Holm), F2 = {d['n_pruebas_F2']} "
         "(ajustado frente a INT-13 por defecto, V1, Holm); cada una con 20 configuraciones × 10-300 árboles elegidas "
         "en el bucle interno; V2 filtra.", "", "## Muestras", "", "| objetivo | filas | eventos | meses con evento | V2 filas / eventos |",
         "|---|---|---|---|---|"]
    for o, v in out["objetivos"].items():
        L.append(f"| {o} | {v['filas']} | {v['eventos']} | {v['meses_con_evento']} | {v['V2_temporal']['filas']} / "
                 f"{v['V2_temporal']['eventos']} |")
    L += ["", "## Log-loss fuera de muestra (V1 dejar un país fuera; V2 1990-2004) y AUC V1", "",
          "| objetivo | modelo | base | def (INT-13) | hpo (ajustado) | logit paquete | AUC V1 def / hpo / logit | pend. cal. hpo V1 |",
          "|---|---|---|---|---|---|---|---|"]
    for o, v in out["objetivos"].items():
        for m in H.MODELOS:
            r = (v["V1_loco"]["metricas"], v["V2_temporal"]["metricas"])
            g = lambda mod, i: f"{r[i][mod]['logloss']:.4f}"  # noqa: E731
            L.append(f"| {o} | {m} | {g('base', 0)} / {g('base', 1)} | {g('def_' + m, 0)} / {g('def_' + m, 1)} | "
                     f"{g('hpo_' + m, 0)} / {g('hpo_' + m, 1)} | {g('lgt_' + m, 0)} / {g('lgt_' + m, 1)} | "
                     f"{r[0]['def_' + m]['auc']:.3f} / {r[0]['hpo_' + m]['auc']:.3f} / {r[0]['lgt_' + m]['auc']:.3f} | "
                     f"{_f(r[0]['hpo_' + m]['calibracion']['pendiente'], 2)} |")
    L += ["", "(cada celda: V1 / V2)", "", "## Contrastes de log-loss (Δ = modelo − listón; negativo = mejor), IC 95 % por bloques de 24 meses", "",
          "| objetivo | modelo | hpo−base V1 [IC] | Holm F1 | V2 | p placebo | hpo−def V1 [IC] | Holm F2 | V2 | z placebo (p rango) | hpo−logit paq. V1 [IC] | V2 | ¿destaca? |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in d["tabla"]:
        pb, pd_ = r["placebo"][f"hpo_{r['modelo']}_vs_base"], r["placebo"][f"hpo_{r['modelo']}_vs_def"]
        L.append(f"| {r['objetivo']} | {r['modelo']} | {_f(r['hpo_vs_base_V1']['est'])} {_ic(r['hpo_vs_base_V1']['ic95'])} | "
                 f"{_f(r['p_holm_F1'], 3)} | {_f(r['hpo_vs_base_V2'])} | {_f(pb['p_placebo'], 3)} | "
                 f"{_f(r['hpo_vs_def_V1']['est'])} {_ic(r['hpo_vs_def_V1']['ic95'])} | {_f(r['p_holm_F2'], 3)} | "
                 f"{_f(r['hpo_vs_def_V2'])} | {_f(pd_["z_placebo"], 2)} ({_f(pd_["p_placebo"], 3)}) | "
                 f"{_f(r['hpo_vs_lgt_V1']['est'])} {_ic(r['hpo_vs_lgt_V1']['ic95'])} | {_f(r['hpo_vs_lgt_V2'])} | "
                 f"{'**sí**' if r['destaca'] else 'no'} |")
    L += ["", "## Placebo (objetivo permutado por bloques de 24 filas dentro de cada país; V1)", "",
          "| objetivo | modelo | hpo−def real | placebo media [p5; min] | hpo−base real | placebo media [p5; min] | optimismo interno real / placebo |",
          "|---|---|---|---|---|---|---|"]
    for r in d["tabla"]:
        m, o = r["modelo"], r["objetivo"]
        a, b = r["placebo"][f"hpo_{m}_vs_def"], r["placebo"][f"hpo_{m}_vs_base"]
        opr = out["optimismo"][o]["real"].get(m)
        opp = out["optimismo"][o]["placebo"].get(m)
        L.append(f"| {o} | {m} | {_f(a['real'])} | {_f(a['placebo_media'])} [{_f(a['placebo_p05'])}; {_f(a['placebo_min'])}] | "
                 f"{_f(b['real'])} | {_f(b['placebo_media'])} [{_f(b['placebo_p05'])}; {_f(b['placebo_min'])}] | "
                 f"{_f(opr)} / {_f(opp)} |")
    L += ["", "## Configuraciones elegidas en el bucle interno (V1, 18 pliegues): moda y rondas medianas", ""]
    for o, v in out["elegidas"].items():
        L.append(f"- **{o}** — " + "; ".join(f"{pq}: cfg {x['moda']} ({x['n_moda']}/18), {x['rondas_mediana']} árboles"
                                            for pq, x in v.items()))
    L += ["", "## Configuración a prerregistrar", ""]
    if out.get("config_final"):
        for o, v in out["config_final"].items():
            L.append(f"- **{o}**: " + json.dumps(v, ensure_ascii=False))
    else:
        L.append("- Nada destaca según la regla del plan §5: no se propone ninguna configuración.")
    L += ["", f"_{FRASE[0].upper() + FRASE[1:]}._", ""]
    return "\n".join(L)


def resumen_elegidas(registro: list) -> dict:
    out = {}
    for o in H.OBJ_HPO:
        out[o] = {}
        for pq in M.PAQUETES:
            g = [x for x in registro if x["objetivo"] == o and x["paquete"] == pq and x["validacion"] == "loco"]
            if not g:
                continue
            cf = pd.Series([x["cfg_elegida"] for x in g])
            out[o][pq] = {"moda": int(cf.mode().iloc[0]), "n_moda": int((cf == cf.mode().iloc[0]).sum()),
                          "rondas_mediana": float(np.median([x["rondas_elegidas"] for x in g]))}
    return out


# ---------------------------------------------------------------- main
def main() -> None:
    cfgs = H.muestrear_configs()
    if "--sintetico" in sys.argv:
        t = time.time()
        Ss = muestras(C.cargar_sintetico(n_paises=6))
        cf = cfgs[:3]
        real = parte_real(Ss, cf, reps=20, max_rondas=120, guardar=None)
        plac = {o: [replica_placebo(S, o, r, cf, 120) for r in range(2)] for o, S in Ss.items()}
        d = decidir(real, plac)
        out = {**real, "decision": d, "procedencia": {"sintetico": True}, "plan_commit": "-", "placebo_reps": 2,
               "optimismo": {o: {"real": optimismo_real(real["registro"], o),
                                 "placebo": {pq: float(np.mean([x["optimismo_interno"][pq] for x in plac[o]]))
                                             for pq in M.PAQUETES}} for o in Ss},
               "elegidas": resumen_elegidas(real["registro"])}
        informe(_limpio(out))
        print(f"[sintético] {time.time() - t:.0f} s; destacan: {d['destacan']}")
        return
    from src.intl.procedencia import procedencia
    import xgboost
    f_real = DIR / "real.json"
    proc = procedencia(exigir_limpio=not f_real.exists())
    if f_real.exists():           # reanudación: solo se permiten cambios dentro de la carpeta de salida
        import subprocess
        sucio = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=all"],
                               capture_output=True, text=True, check=True).stdout.splitlines()
        ajenos = [x for x in sucio if not x[3:].startswith("research/int/hpo_int13/")]
        if ajenos:
            raise SystemExit("árbol sucio fuera de research/int/hpo_int13/:\n" + "\n".join(ajenos))
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "placebo").mkdir(exist_ok=True)
    Ss = muestras(C.cargar_real())
    if not f_real.exists():
        t = time.time()
        real = parte_real(Ss, cfgs, reps=M.REPS, max_rondas=H.MAX_RONDAS, guardar=DIR)
        real = {"documento": "HPO-INT13 (exploratorio): parte real", "procedencia": proc, "xgboost": xgboost.__version__,
                "configs": cfgs, "segundos": round(time.time() - t), **real}
        with open(DIR / "pruebas_internas.jsonl", "w") as fh:
            for g in real["registro"]:
                fh.write(json.dumps(_limpio(g), ensure_ascii=False) + "\n")
        f_real.write_text(json.dumps(_limpio({k: v for k, v in real.items() if k != "registro"}), ensure_ascii=False,
                                     indent=1))
        print(f"escrito {f_real}", flush=True)
    real = json.loads(f_real.read_text())
    real["registro"] = [json.loads(x) for x in (DIR / "pruebas_internas.jsonl").read_text().splitlines()]
    if real["procedencia"]["commit"] != proc["commit"]:
        raise SystemExit("el commit actual no es el de la parte real: el placebo debe correr con el mismo código")
    plac = {}
    for o, S in Ss.items():
        plac[o] = []
        for r in range(H.PLACEBO_REPS):
            f = DIR / "placebo" / f"{o}_{r:02d}.json"
            if not f.exists():
                t = time.time()
                x = replica_placebo(S, o, r, cfgs, H.MAX_RONDAS)
                x["procedencia"] = procedencia(exigir_limpio=False)
                f.write_text(json.dumps(_limpio(x), ensure_ascii=False))
                print(f"placebo {o} {r}: {time.time() - t:.0f} s", flush=True)
            plac[o].append(json.loads(f.read_text()))
    d = decidir(real, plac)
    out = {"documento": "HPO-INT13 (exploratorio)", "plan_commit": real["procedencia"]["commit"][:7],
           "procedencia": real["procedencia"], "placebo_reps": H.PLACEBO_REPS, "aviso": FRASE,
           "objetivos": real["objetivos"], "decision": d,
           "optimismo": {o: {"real": optimismo_real(real["registro"], o),
                             "placebo": {pq: float(np.mean([x["optimismo_interno"][pq] for x in plac[o]]))
                                         for pq in M.PAQUETES}} for o in Ss},
           "elegidas": resumen_elegidas(real["registro"]),
           "config_final": {o: config_final(Ss[o], o, cfgs, H.MAX_RONDAS) for o in {o for o, _ in d["destacan"]}}}
    (DIR / "resultado.json").write_text(json.dumps(_limpio(out), ensure_ascii=False, indent=1))
    (DIR / "resultado.md").write_text(informe(_limpio(out)))
    print(f"escrito {DIR}/resultado.{{json,md}}; destacan: {d['destacan']}")


if __name__ == "__main__":
    main()
