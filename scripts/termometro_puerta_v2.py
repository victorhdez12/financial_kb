"""Segundo y ÚLTIMO intento de la puerta del termómetro (docs/int/TERMOMETRO_diseno_v1.md §9, v1.3 `a94ac09`):
recalibración logit de la probabilidad mensual y validación cruzada en dos mitades (pares ↔ impares), mismos umbrales.
Si pasa: rectas y recalibración finales con todos los años ≤ 2004 y percentiles de referencia recalibrados.
Exige el árbol limpio. Salida: research/int/termometro_puerta_v2.{json,md} y una línea en research/trial_log.md.
Uso: .venv/bin/python -m scripts.termometro_puerta_v2 [--correccion]
--correccion (29-oct, Validador): S4 según §8 d y lista de países sin DNK/JPN; salida termometro_puerta_v2_corr.*
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from scripts.int4_corrida import NUCLEO, _r
from scripts.termometro_puerta import GIROS, REPO, TODOS, cargar
from src.intl import int4 as M
from src.intl import termometro as T
from src.intl.procedencia import procedencia
from src.warehouse import db

PAR = lambda t: t % 2 == 0  # noqa: E731
IMPAR = lambda t: t % 2 == 1  # noqa: E731
TODO = lambda t: True  # noqa: E731


def probs(f, B1, Xa, b, tr, cols):
    pa = M.logit_pred(b, np.column_stack([B1, Xa]))
    pm = M.logit_pred(b, np.column_stack([B1, T.matriz_mensual(f, tr, cols)]))
    ok = np.isfinite(pa) & np.isfinite(pm) & (f.t.to_numpy() <= 2003)
    return pa, pm, ok


def referencia_cal(tr, pib, fq, b, cal, rej) -> dict:
    """Como termometro_puerta.referencia, con la probabilidad recalibrada."""
    ps = {"T1": [], "T2": []}
    for c in NUCLEO:
        est = T.estado_mensual(fq[c], rej, pib[c].index.min())
        x = {k: tr[k][c].reindex(rej) for k in ("C1", "C2", "C4", "C5", "C6", "S4")}
        fuera = (est["en_rec"] == 0).to_numpy()
        X = np.column_stack([x[k] for k in ("C1", "C2", "C4", "C5", "C6")])
        p1 = T.aplicar_cal(M.logit_pred(b["T1"], np.column_stack([T.b1_vivo(est, "T1"), X])), cal["T1"])
        ps["T1"].append(p1[fuera & np.isfinite(p1)])
        dentro = (est["en_rec"] == 1).to_numpy()
        inicio = dentro & ~np.r_[False, dentro[:-1]]
        s5 = pd.Series(np.where(inicio, x["C2"].to_numpy(), np.nan), index=rej).ffill().where(dentro)
        X2 = np.column_stack([x["C1"], x["C5"], x["C6"], x["S4"], s5])
        p2 = T.aplicar_cal(M.logit_pred(b["T2"], np.column_stack([T.b1_vivo(est, "T2"), X2])), cal["T2"])
        ps["T2"].append(p2[dentro & np.isfinite(p2)])
    return {g: {"meses": int(len(v := np.concatenate(x))),
                **{f"p{q}": float(np.quantile(v, q / 100)) for q in (50, 80, 95)}} for g, x in ps.items()}


def main() -> None:
    proc = procedencia()
    a, extra, pm_, bis, pib = cargar()
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    años_pais = {c: set(a.xs(c, level=0)["rgdpmad"].dropna().index.astype(int)) for c in TODOS}
    primer = {c: min(v) for c, v in años_pais.items()}
    pan = M.paneles(a, extra, NUCLEO, TODOS, None)
    mens = T.mensuales(pm_, bis, pib, NUCLEO, TODOS)
    rej = mens["C1"].index
    res = {"procedencia": proc, "diseno": "docs/int/TERMOMETRO_diseno_v1.md §9 (v1.3, a94ac09)", "puerta": {},
           "sin_recalibrar_cruzada": {}, "final": {}}
    base, b = {}, {}
    for giro, cols in GIROS.items():
        f = (M.obj_entrada if giro == "T1" else M.obj_salida)(rec, años_pais, NUCLEO, 1, 1871, True)
        B1 = M.liston(f, giro, rec, primer, pan)
        Xa = M.matriz(f, pan, cols)
        b[giro] = T.congelar(B1, Xa, f.y.to_numpy(float))
        base[giro] = (f, B1, Xa)

    pa_all = {g: np.full(len(base[g][0]), np.nan) for g in GIROS}
    pc_all, pm_all = {g: pa_all[g].copy() for g in GIROS}, {g: pa_all[g].copy() for g in GIROS}
    for fit, gate, nom in ((PAR, IMPAR, "pares→impares"), (IMPAR, PAR, "impares→pares")):
        tr = T.traducir(mens, T.rectas(pan, mens, NUCLEO, TODOS, fit, gate), TODOS)
        for giro, cols in GIROS.items():
            f, B1, Xa = base[giro]
            pa, pm, ok = probs(f, B1, Xa, b[giro], tr, cols)
            t = f.t.to_numpy()
            mf, mg = ok & np.array([fit(x) for x in t]), ok & np.array([gate(x) for x in t])
            cal = T.calibrar(pa[mf], pm[mf])
            pa_all[giro][mg], pm_all[giro][mg] = pa[mg], pm[mg]
            pc_all[giro][mg] = T.aplicar_cal(pm[mg], cal)
            res.setdefault("pliegues", {}).setdefault(giro, {})[nom] = {"cal": cal, "filas_ajuste": int(mf.sum()),
                                                                       "filas_puerta": int(mg.sum())}
    for giro in GIROS:
        f = base[giro][0]
        pa, pc = pa_all[giro], pc_all[giro]
        g = {"agregado": T.puerta(pa, pc), "por_pais": {}}
        for c in NUCLEO:
            k = (f.pais.to_numpy() == c) & np.isfinite(pc)
            v = T.puerta(pa[k], pc[k]) if k.sum() >= T.MIN_FILAS_PUERTA else {"filas": int(k.sum()), "pasa": None}
            v["muestra"] = "propia" if k.sum() >= T.MIN_FILAS_PUERTA else "sin puerta propia"
            g["por_pais"][c] = v
        res["puerta"][giro] = g
        res["sin_recalibrar_cruzada"][giro] = T.puerta(pa, pm_all[giro])
        print(giro, _r(g["agregado"]), "sin recalibrar:", _r(res["sin_recalibrar_cruzada"][giro]), flush=True)

    pasa = {g: bool(res["puerta"][g]["agregado"]["pasa"]) for g in GIROS}
    res["veredicto"] = {"pasa_agregado": pasa, "paises_con_probabilidad": {
        g: [c for c, v in res["puerta"][g]["por_pais"].items() if pasa[g] and v["pasa"] is not False and v["filas"] > 0 and c not in T.SIN_BOLSA] for g in GIROS}}
    if any(pasa.values()):     # final: todos los años ≤ 2004
        rl = T.rectas(pan, mens, NUCLEO, TODOS, TODO, TODO)
        tr = T.traducir(mens, rl, TODOS)
        cal = {}
        for giro, cols in GIROS.items():
            f, B1, Xa = base[giro]
            pa, pm, ok = probs(f, B1, Xa, b[giro], tr, cols)
            cal[giro] = T.calibrar(pa[ok], pm[ok])
        fq = {c: T.fechado_trimestral(pib[c]) for c in TODOS}
        res["final"] = {"modelo": {g: [float(x) for x in b[g]] for g in GIROS}, "cal": cal, "rectas": rl,
                        "percentiles_referencia": referencia_cal(tr, pib, fq, b, cal, rej)}

    out = REPO / "research" / "int"
    suf = "_corr" if "--correccion" in sys.argv else ""
    (out / f"termometro_puerta_v2{suf}.json").write_text(json.dumps(_r(res), indent=1, ensure_ascii=False))
    fm = lambda v: "—" if v is None else f"{v:.3f}"  # noqa: E731
    md = ["# Termómetro: puerta, 2.º y último intento (recalibración + validación cruzada)", "",
          f"Diseño v1.3 §9 (`a94ac09`); commit {proc['commit'][:7]}, árbol limpio {proc['arbol_limpio']}, "
          f"{proc['hora_utc']}.", "", "| giro | filas | r | pendiente | pasa | sin recalibrar r / pend |",
          "|---|---|---|---|---|---|"]
    for g in GIROS:
        p, q = res["puerta"][g]["agregado"], res["sin_recalibrar_cruzada"][g]
        md.append(f"| {g} | {p['filas']} | {fm(p['r'])} | {fm(p['pendiente'])} | {p['pasa']} | "
                  f"{fm(q['r'])} / {fm(q['pendiente'])} |")
    md += ["", "Por país: " + "; ".join(f"{g} {c} {v['filas']} f, {fm(v.get('r'))} / {fm(v.get('pendiente'))}"
                                        f" {v['pasa']}" for g in GIROS for c, v in res["puerta"][g]["por_pais"].items()
                                        if v["muestra"] == "propia"),
           "", f"Veredicto: {res['veredicto']}"]
    if res["final"]:
        md += ["", f"Percentiles de referencia (recalibrados, todos los años ≤ 2004): "
                   f"{_r(res['final']['percentiles_referencia'])}"]
    (out / f"termometro_puerta_v2{suf}.md").write_text("\n".join(md) + "\n")
    with open(REPO / "research" / "trial_log.md", "a") as fh:
        fh.write(f"| {proc['hora_utc']} | termometro_puerta_v2{suf} (2.º y último intento{' — corrección de error del Validador' if suf else ''}) | {proc['commit'][:7]} | "
                 f"puerta T1 {pasa['T1']} T2 {pasa['T2']} | recalibración logit + validación cruzada 2 mitades |\n")
    print(res["veredicto"])


if __name__ == "__main__":
    main()
