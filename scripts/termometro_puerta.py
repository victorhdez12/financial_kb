"""Puerta de la traducción mensual del termómetro informativo (docs/int/TERMOMETRO_diseno_v1.md v1.2, `e9ec71d`).
Ejecución ÚNICA con puerta: rectas de escala con los años pares ≤ 2004, puerta (r ≥ 0,8, pendiente en [0,8; 1,25]) con
los impares, por giro (T1 en sus filas, T2 en las suyas, B1 del fechado anual JST). Informativos: partición temporal
(≤ 1984 / 1985-2004), concordancia del fechado trimestral con JST y percentiles de referencia (p50/p80/p95) de las
probabilidades mensuales 1960-2004 del núcleo. Solo indicadores y fechados: no mira rentabilidades ni el periodo ≥ 2005.
Exige el árbol limpio. Salida: research/int/termometro_puerta.{json,md} y una línea en research/trial_log.md.
Uso: .venv/bin/python -m scripts.termometro_puerta
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.int4_corrida import COLS, NUCLEO, PRUEBA_SIN_BOLSA, PRUEBA_TODO, _r
from src.intl import data as D
from src.intl import int4 as M
from src.intl import panel as P
from src.intl import termometro as T
from src.intl.procedencia import procedencia
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
TODOS = NUCLEO + PRUEBA_TODO + PRUEBA_SIN_BOLSA
GIROS = {"T1": COLS["T1"], "T2": COLS["T2"]}


def cargar():
    con = D.connect()
    a = P.anual(con)
    extra = {}
    for v in ("hpnom", "money", "wage"):
        s = {c: D.load_dev(con, f"jst_{c.lower()}_{v}") for c in D.PAISES}
        s = pd.concat({c: x.set_axis(x.index.year) for c, x in s.items() if not x.empty})
        s.index.names = ["pais", "año"]
        extra[v] = s
    pm = P.mensual(con)
    bis = {c: s for c in TODOS if not (s := D.load_dev(con, f"bis_creditgap_{D.ISO2[c]}_ratio")).empty}
    con.close()
    pib = {c: D.load_dev_curado(f"oecd_gdpq_{c.lower()}") for c in TODOS}
    return a, pd.DataFrame(extra), pm, bis, pib


def puertas(f, B1, Xa, b, tr, cols, sel) -> dict:
    """Probabilidad anual y mensual traducida en las filas `sel`; puerta agregada y por país."""
    Xm = T.matriz_mensual(f, tr, cols)
    pa = M.logit_pred(b, np.column_stack([B1, Xa]))
    pmn = M.logit_pred(b, np.column_stack([B1, Xm]))
    ok = sel & np.isfinite(pa) & np.isfinite(pmn)
    out = {"agregado": T.puerta(pa[ok], pmn[ok]), "por_pais": {}}
    for c in NUCLEO:
        k = ok & (f.pais.to_numpy() == c)
        g = T.puerta(pa[k], pmn[k]) if k.sum() >= T.MIN_FILAS_PUERTA else {"filas": int(k.sum()), "pasa": None}
        g["muestra"] = "propia" if k.sum() >= T.MIN_FILAS_PUERTA else "sin puerta propia"
        out["por_pais"][c] = g
    out["años"] = sorted({int(t) for t in f.t.to_numpy()[ok]})
    return out


def referencia(tr, pib, fq, b, rej) -> dict:
    """Probabilidades mensuales 1960-2004 del núcleo con el B1 del fechado en vivo → percentiles."""
    ps = {"T1": [], "T2": []}
    for c in NUCLEO:
        est = T.estado_mensual(fq[c], rej, pib[c].index.min())
        x = {k: tr[k][c].reindex(rej) for k in ("C1", "C2", "C4", "C5", "C6", "S4")}
        fuera = est["en_rec"] == 0
        X = np.column_stack([x[k] for k in ("C1", "C2", "C4", "C5", "C6")])
        p1 = M.logit_pred(b["T1"], np.column_stack([T.b1_vivo(est, "T1"), X]))
        ps["T1"].append(p1[fuera.to_numpy() & np.isfinite(p1)])
        dentro = (est["en_rec"] == 1).to_numpy()
        inicio = dentro & ~np.r_[False, dentro[:-1]]
        s5 = pd.Series(np.where(inicio, x["C2"].to_numpy(), np.nan), index=rej).ffill().where(dentro)
        X2 = np.column_stack([x["C1"], x["C5"], x["C6"], x["S4"], s5])
        p2 = M.logit_pred(b["T2"], np.column_stack([T.b1_vivo(est, "T2"), X2]))
        ps["T2"].append(p2[dentro & np.isfinite(p2)])
    out = {}
    for g, v in ps.items():
        v = np.concatenate(v)
        out[g] = {"meses": int(len(v)), **({f"p{q}": float(np.quantile(v, q / 100)) for q in (50, 80, 95)} if len(v) else {})}
    return out


def main() -> None:
    proc = procedencia()
    a, extra, pm, bis, pib = cargar()
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    años_pais = {c: set(a.xs(c, level=0)["rgdpmad"].dropna().index.astype(int)) for c in TODOS}
    primer = {c: min(v) for c, v in años_pais.items()}
    pan = M.paneles(a, extra, NUCLEO, TODOS, None)
    mens = T.mensuales(pm, bis, pib, NUCLEO, TODOS)
    rej = mens["C1"].index

    res = {"procedencia": proc, "diseno": "docs/int/TERMOMETRO_diseno_v1.md (v1.2, e9ec71d)", "rectas": {},
           "modelo": {}, "puerta": {}, "informativo_temporal": {}}
    variantes = {"principal": (lambda t: t % 2 == 0, lambda t: t % 2 == 1),
                 "temporal": (lambda t: t <= 1984, lambda t: t >= 1985)}
    b = {}
    for nom, (fit, gate) in variantes.items():
        rl = T.rectas(pan, mens, NUCLEO, TODOS, fit, gate)
        tr = T.traducir(mens, rl, TODOS)
        if nom == "principal":
            res["rectas"], tr_principal = rl, tr
        for giro, cols in GIROS.items():
            f = (M.obj_entrada if giro == "T1" else M.obj_salida)(rec, años_pais, NUCLEO, 1, 1871, True)
            B1 = M.liston(f, giro, rec, primer, pan)
            Xa = M.matriz(f, pan, cols)
            if giro not in b:
                b[giro] = T.congelar(B1, Xa, f.y.to_numpy(float))
                res["modelo"][giro] = {"indicadores": cols, "coef": [float(v) for v in b[giro]],
                                       "filas_ajuste": int((np.isfinite(B1).all(1) & np.isfinite(Xa).all(1)).sum())}
            sel = np.array([gate(int(t)) for t in f.t]) & (f.t.to_numpy() <= 2003)
            g = puertas(f, B1, Xa, b[giro], tr, cols, sel)
            (res["puerta"] if nom == "principal" else res["informativo_temporal"])[giro] = g
            print(nom, giro, _r(g["agregado"]), flush=True)

    fq = {c: T.fechado_trimestral(pib[c]) for c in TODOS}
    res["concordancia_fechado"] = T.concordancia(rec, {c: fq[c] for c in NUCLEO})
    res["percentiles_referencia"] = referencia(tr_principal, pib, fq, b, rej)
    pasa = {g: bool(res["puerta"][g]["agregado"]["pasa"]) for g in GIROS}
    res["veredicto"] = {"pasa_agregado": pasa,
                        "paises_con_probabilidad": {g: [c for c, v in res["puerta"][g]["por_pais"].items()
                                                        if pasa[g] and v["pasa"] is not False and v["filas"] > 0 and c not in T.SIN_BOLSA] for g in GIROS}}

    out = REPO / "research" / "int"
    (out / "termometro_puerta.json").write_text(json.dumps(_r(res), indent=1, ensure_ascii=False))
    md = ["# Termómetro informativo: puerta de la traducción mensual", "",
          f"Diseño v1.2 (`e9ec71d`); commit {proc['commit'][:7]}, árbol limpio {proc['arbol_limpio']}, {proc['hora_utc']}.",
          "", "| giro | filas impares | r | pendiente | pasa | temporal r / pend |", "|---|---|---|---|---|---|"]
    for g in GIROS:
        p, q = res["puerta"][g]["agregado"], res["informativo_temporal"][g]["agregado"]
        fm = lambda v: "—" if v is None else f"{v:.3f}"  # noqa: E731
        md.append(f"| {g} | {p['filas']} | {fm(p['r'])} | {fm(p['pendiente'])} | {p['pasa']} | "
                  f"{fm(q['r'])} / {fm(q['pendiente'])} |")
    md += ["", "Por país (impares): " + "; ".join(
        f"{g} {c} {v['filas']} f, {'—' if v.get('r') is None else round(v['r'], 2)} ({v['muestra']})"
        for g in GIROS for c, v in res["puerta"][g]["por_pais"].items()),
        "", f"Concordancia del fechado trimestral (±1 año, 1961-2003): {res['concordancia_fechado']['total']}",
        "", f"Percentiles de referencia: {_r(res['percentiles_referencia'])}",
        "", f"Veredicto: {res['veredicto']}"]
    (out / "termometro_puerta.md").write_text("\n".join(md) + "\n")
    with open(REPO / "research" / "trial_log.md", "a") as fh:
        fh.write(f"| {proc['hora_utc']} | termometro_puerta | {proc['commit'][:7]} | puerta traducción T1 "
                 f"{pasa['T1']} T2 {pasa['T2']} | ejecución única con puerta (diseño v1.2) |\n")
    print(res["veredicto"])


if __name__ == "__main__":
    main()
