"""INT-4: sensibilidad DECLARADA A POSTERIORI (tras ver la corrida única e4cceb5) sobre el listón B1.
No cambia el prerregistro ni la clasificación oficial de la corrida única.

Motivo: con dejar un país fuera, el listón B1 da AUC < 0,5 en T1 y T2 (0,546 y 0,446). Hipótesis: sesgo conocido de la
validación dejando un grupo fuera con un predictor débil: el intercepto ajustado sin el país c se mueve en contra de la
tasa base de c, así que las predicciones agrupadas ordenan los países al revés. Ese sesgo castiga más al listón (casi solo
intercepto) que al modelo, e infla ΔAUC. Dos comprobaciones:
  (a) AUC ESTRATIFICADA por país: solo pares (positivo, negativo) del MISMO país; anula el efecto del intercepto por país;
  (b) listón B1 ajustado DENTRO de muestra (sin dejar fuera; 1-2 parámetros), frente al modelo dejando un país fuera:
      favorece al listón (conservador).
Inferencia: bootstrap por bloques de año (2.000 réplicas, semilla 0), como la corrida.
Uso: .venv/bin/python -m scripts.int4_sensibilidad_liston [--prueba]
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from scripts.int4_corrida import COLS, NUCLEO, REPO, TODOS, materias_primas
from src.intl import data as D
from src.intl import int4 as M
from src.intl import panel as P
from src.intl.procedencia import procedencia
from src.warehouse import db


def auc_estrat(y, p, g) -> float:
    num = den = 0.0
    for c in np.unique(g):
        f = g == c
        yy, pp = y[f].astype(bool), p[f]
        n1, n0 = yy.sum(), (~yy).sum()
        if n1 == 0 or n0 == 0:
            continue
        r = rankdata(pp)
        num += r[yy].sum() - n1 * (n1 + 1) / 2
        den += n1 * n0
    return num / den if den else np.nan


def boot(y, p1, p0, t, g, f_auc, B=2000, semilla=0) -> dict:
    años = np.unique(t)
    idx = {a: np.flatnonzero(t == a) for a in años}
    rng = np.random.default_rng(semilla)
    d = []
    for _ in range(B):
        s = np.concatenate([idx[a] for a in rng.choice(años, len(años), replace=True)])
        d.append(f_auc(y[s], p1[s], g[s]) - f_auc(y[s], p0[s], g[s]))
    d = np.array(d)
    d = d[np.isfinite(d)]
    obs = f_auc(y, p1, g) - f_auc(y, p0, g)
    lado = (d <= 0).sum() if obs > 0 else (d >= 0).sum()
    return {"auc_modelo": f_auc(y, p1, g), "auc_liston": f_auc(y, p0, g), "d_auc": obs,
            "ic95": [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))],
            "p_bloques": float(min(1.0, 2 * (1 + lado) / (1 + len(d))))}


def main() -> None:
    proc = procedencia(exigir_limpio="--prueba" not in sys.argv)
    con = D.connect()
    a = P.anual(con)
    extra = {}
    for v in ("hpnom", "money", "wage"):
        s = {c: D.load_dev(con, f"jst_{c.lower()}_{v}") for c in D.PAISES}
        s = pd.concat({c: x.set_axis(x.index.year) for c, x in s.items() if not x.empty})
        s.index.names = ["pais", "año"]
        extra[v] = s
    con.close()
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    años_pais = {c: set(a.xs(c, level=0)["rgdpmad"].dropna().index.astype(int)) for c in TODOS}
    primer = {c: min(v) for c, v in años_pais.items()}
    pan = M.paneles(a, pd.DataFrame(extra), NUCLEO, TODOS, materias_primas())
    et = M.etiquetas_inflacion(a, TODOS)
    agr = lambda y, p, g: M.auc(y, p)
    res = {"procedencia": proc, "declarado": "a posteriori; no cambia la clasificación de la corrida única", "giros": {}}
    for giro, cols in COLS.items():
        if giro == "T1":
            f = M.obj_entrada(rec, años_pais, NUCLEO, 1, 1871, True)
        elif giro == "T2":
            f = M.obj_salida(rec, años_pais, NUCLEO, 1, 1871, True)
        else:
            f = M.obj_inflacion(et["principal"], NUCLEO, 1, 1871, True, sube=(giro == "T3"))
        B1, Xc = M.liston(f, giro, rec, primer, pan), M.matriz(f, pan, cols)
        ok = np.isfinite(B1).all(axis=1) & np.isfinite(Xc).all(axis=1)
        f, B1, Xc = f[ok].reset_index(drop=True), B1[ok], Xc[ok]
        y, g, t = f.y.to_numpy(float), f.pais.to_numpy(), f.t.to_numpy()
        X1 = np.column_stack([B1, Xc])
        p1, p0 = M.loco(X1, y, g), M.loco(B1, y, g)
        p0_in = M.logit_pred(M.logit_fit(B1, y), B1)
        tasa = pd.Series(y).groupby(g).mean()
        res["giros"][giro] = {
            "filas": int(len(y)),
            "agrupada_loco_reproduce_corrida": boot(y, p1, p0, t, g, agr),
            "a_estratificada_loco": boot(y, p1, p0, t, g, auc_estrat),
            "b_liston_dentro_de_muestra": boot(y, p1, p0_in, t, g, agr),
            "b_estratificada_liston_dentro": boot(y, p1, p0_in, t, g, auc_estrat),
            "corr_tasa_pais_vs_pred_media_liston_loco": float(np.corrcoef(
                tasa.to_numpy(), pd.Series(p0).groupby(g).mean().reindex(tasa.index).to_numpy())[0, 1])}
        r = res["giros"][giro]
        print(giro, {k: (round(v["auc_liston"], 3), round(v["auc_modelo"], 3), round(v["d_auc"], 3),
                         [round(x, 3) for x in v["ic95"]], round(v["p_bloques"], 3))
                     for k, v in r.items() if isinstance(v, dict)}, "corr", round(r["corr_tasa_pais_vs_pred_media_liston_loco"], 2))
    if "--prueba" not in sys.argv:
        (REPO / "research" / "int" / "int4_sensibilidad_liston.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
