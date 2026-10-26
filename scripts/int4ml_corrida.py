"""Corrida ÚNICA de P-DEV-INT4-ML v1.0 (docs/int/INT4ML_prerregistro_v0.md, congelado en e1f67a6).
Familia Holm-4: {M-L2, M-GB} × {T1 entrada, T2 salida}, frente al logit de INT-4 (B1 + indicadores), núcleo 14 países,
1871-2004 sin guerras, h = 1, dejar un país fuera, mismas filas que INT-4. Placebo: indicadores desplazados k = 6 … 129
(los 124, todos), reajustando el logit y los dos ML en los 14 pliegues (en paralelo por k; mismo resultado). Concreciones
en el docstring de src/intl/int4ml.py. Países de prueba AUS y CHE con los modelos congelados en el núcleo (informativo).
Exige el árbol limpio. Salida: research/int/int4ml_resultado.json y .md, y una línea en research/trial_log.md.
Uso: .venv/bin/python -m scripts.int4ml_corrida
"""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd
import sklearn
from joblib import Parallel, delayed

from scripts.int4_corrida import COLS, NUCLEO, PRUEBA_TODO, REPO, TODOS, _r, materias_primas
from scripts.int4_sensibilidad_liston import auc_estrat, boot
from src.intl import data as D
from src.intl import int3 as I3
from src.intl import int4 as M
from src.intl import int4ml as ML
from src.intl import panel as P
from src.intl.procedencia import procedencia
from src.warehouse import db

GIROS = ["T1", "T2"]
CAND = ["M-L2", "M-GB"]
agr = lambda y, p, g: M.auc(y, p)  # noqa: E731


def boot_ll(y, p1, p0, t, B=2000, semilla=0) -> dict:
    años = np.unique(t)
    idx = {a: np.flatnonzero(t == a) for a in años}
    rng = np.random.default_rng(semilla)
    d = []
    for _ in range(B):
        s = np.concatenate([idx[a] for a in rng.choice(años, len(años), replace=True)])
        d.append(M.logloss(y[s], p1[s]) - M.logloss(y[s], p0[s]))
    return {"d_logloss": M.logloss(y, p1) - M.logloss(y, p0),
            "ic95": [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))],
            "d_brier": M.brier(y, p1) - M.brier(y, p0)}


def placebo_k(k, f_all, B1_all, pan, cols, giro):
    Xk = M.matriz(f_all, pan, cols, k)
    ok = np.isfinite(B1_all).all(axis=1) & np.isfinite(Xk).all(axis=1)
    y, g = f_all.y.to_numpy(float)[ok], f_all.pais.to_numpy()[ok]
    if y.sum() < 10 or (1 - y).sum() < 10:
        return None
    X = np.column_stack([B1_all[ok], Xk[ok]])
    p0 = ML.loco(ML.Logit, X, y, g)
    a0 = auc_estrat(y, p0, g)
    out = {}
    for c in CAND:
        p1 = ML.loco(ML.fabrica(c, giro, B1_all.shape[1], cols), X, y, g)
        out[c] = auc_estrat(y, p1, g) - a0
    return out


def main() -> None:
    proc = procedencia()
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

    def filas(giro, paises):
        if giro == "T1":
            return M.obj_entrada(rec, años_pais, paises, 1, 1871, True)
        return M.obj_salida(rec, años_pais, paises, 1, 1871, True)

    res = {"procedencia": proc, "prerregistro": "docs/int/INT4ML_prerregistro_v0.md (v1.0, e1f67a6)",
           "versiones": {"scikit-learn": sklearn.__version__, "numpy": np.__version__}, "contrastes": {},
           "paises_prueba": {}}
    for giro in GIROS:
        cols = COLS[giro]
        f_all = filas(giro, NUCLEO)
        B1_all, X_all = M.liston(f_all, giro, rec, primer, pan), M.matriz(f_all, pan, cols)
        ok = np.isfinite(B1_all).all(axis=1) & np.isfinite(X_all).all(axis=1)
        f = f_all[ok].reset_index(drop=True)
        X = np.column_stack([B1_all[ok], X_all[ok]])
        y, g, t = f.y.to_numpy(float), f.pais.to_numpy(), f.t.to_numpy()
        nb = B1_all.shape[1]
        p_log = ML.loco(ML.Logit, X, y, g)
        q_log = ML.temporal(ML.Logit, X, y, t)
        pl = Parallel(n_jobs=-1)(delayed(placebo_k)(k, f_all, B1_all, pan, cols, giro) for k in M.KS)
        pl = [x for x in pl if x is not None]
        for c in CAND:
            fab = ML.fabrica(c, giro, nb, cols)
            p = ML.loco(fab, X, y, g)
            q = ML.temporal(fab, X, y, t)
            v = np.isfinite(q) & np.isfinite(q_log)
            r = {"filas": int(len(y)), "eventos": int(y.sum()), "indicadores": cols,
                 "estratificada": boot(y, p, p_log, t, g, auc_estrat), "agrupada": boot(y, p, p_log, t, g, agr),
                 "logloss": boot_ll(y, p, p_log, t), "calibracion": M.calibracion(y, p),
                 "calibracion_logit": M.calibracion(y, p_log),
                 "temporal_1950_2004": {"filas": int(v.sum()),
                                        "d_auc_estratificada": auc_estrat(y[v], q[v], g[v]) - auc_estrat(y[v], q_log[v], g[v]),
                                        "d_auc_agrupada": M.auc(y[v], q[v]) - M.auc(y[v], q_log[v])},
                 "placebo": ML.z_placebo(auc_estrat(y, p, g) - auc_estrat(y, p_log, g), np.array([x[c] for x in pl]))}
            res["contrastes"][f"{c}|{giro}"] = r
            print(c, giro, round(r["estratificada"]["d_auc"], 4), r["estratificada"]["ic95"], round(r["placebo"]["z"], 2),
                  flush=True)
        # países de prueba: modelos congelados (ajustados una vez con todo el núcleo)
        fp = filas(giro, PRUEBA_TODO)
        B1p, Xp = M.liston(fp, giro, rec, primer, pan), M.matriz(fp, pan, cols)
        okp = np.isfinite(B1p).all(axis=1) & np.isfinite(Xp).all(axis=1)
        fp = fp[okp].reset_index(drop=True)
        Xpp = np.column_stack([B1p[okp], Xp[okp]])
        yp, gp, tp = fp.y.to_numpy(float), fp.pais.to_numpy(), fp.t.to_numpy()
        pp_log = ML.Logit().fit(X, y).predict(Xpp)
        d = {}
        for c in CAND:
            pp = ML.fabrica(c, giro, nb, cols)().fit(X, y).predict(Xpp)
            d[c] = {"filas": int(len(yp)), "eventos": int(yp.sum()), "estratificada": boot(yp, pp, pp_log, tp, gp, auc_estrat),
                    "agrupada": boot(yp, pp, pp_log, tp, gp, agr),
                    "d_logloss": M.logloss(yp, pp) - M.logloss(yp, pp_log)}
        res["paises_prueba"][giro] = d

    C = res["contrastes"]
    h_i = I3.holm({k: v["estratificada"]["p_bloques"] for k, v in C.items()})
    h_ii = I3.holm({k: v["placebo"]["p_z"] for k, v in C.items()})
    ver = {}
    for k, v in C.items():
        crit = {"i_ic_estratificada_holm": bool(v["estratificada"]["d_auc"] > 0 and h_i[k]),
                "ii_z_placebo_holm": bool(h_ii[k]), "iii_dlogloss_neg": bool(v["logloss"]["d_logloss"] < 0),
                "iv_temporal_pos": bool(v["temporal_1950_2004"]["d_auc_estratificada"] > 0),
                "v_pendiente_0.5_1.5": bool(0.5 <= v["calibracion"]["pendiente"] <= 1.5)}
        ver[k] = {"criterios": crit, "establecido": all(crit.values())}
    res["veredicto"] = ver
    res["regla_cierre"] = ("si ninguno queda establecido, la línea de ML queda cerrada con estos datos (§7): no se prueban "
                           "otros modelos ni hiperparámetros sobre ≤ 2004")
    res["hora_fin_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    R = _r(res)
    out = REPO / "research" / "int"
    (out / "int4ml_resultado.json").write_text(json.dumps(R, indent=1, ensure_ascii=False))
    (out / "int4ml_resultado.md").write_text(informe(R))
    est = {k: v["establecido"] for k, v in ver.items()}
    linea = (f"| {dt.date.today().isoformat()} | Constructor (P-DEV-INT4-ML v1.0, corrida única) | commit {proc['commit'][:7]}; "
             f"M-L2 y M-GB frente al logit de INT-4, T1 y T2, dejar un país fuera, AUC estratificada, Holm-4; establecidos "
             f"{json.dumps(est, ensure_ascii=False)}; scikit-learn {sklearn.__version__}; research/int/int4ml_resultado.json |\n")
    with open(REPO / "research" / "trial_log.md", "a") as fh:
        fh.write(linea)
    print(json.dumps(_r(ver), indent=1, ensure_ascii=False))


def _f(v, k=3):
    return "–" if v is None else f"{v:+.{k}f}"


def informe(r: dict) -> str:
    p = r["procedencia"]
    L = ["# INT-4-ML: resultado de la corrida única", "",
         f"Procedencia: commit `{p['commit'][:7]}`, árbol limpio {p['arbol_limpio']}, {p['hora_utc']}. Prerregistro v1.0 "
         f"(e1f67a6). scikit-learn {r['versiones']['scikit-learn']}. Listón = logit de INT-4 (B1 + indicadores). Núcleo 14 "
         "países, 1871-2004 sin guerras, h = 1, dejar un país fuera. Métrica principal: AUC estratificada por país.", "",
         "| candidato · giro | filas / eventos | AUC estrat. logit → ML | ΔAUC estrat. | IC 95 % | p bloques | z placebo (p) | "
         "p rangos | ΔAUC agrupada | Δlog-loss [IC] | temporal | pendiente | ESTABLECIDO |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in r["contrastes"].items():
        e, pl, ll = v["estratificada"], v["placebo"], v["logloss"]
        L.append(f"| {k} | {v['filas']} / {v['eventos']} | {e['auc_liston']:.3f} → {e['auc_modelo']:.3f} | {_f(e['d_auc'])} | "
                 f"[{_f(e['ic95'][0])}; {_f(e['ic95'][1])}] | {e['p_bloques']:.4f} | {pl['z']:+.2f} ({pl['p_z']:.4f}) | "
                 f"{pl['p_rangos']:.3f} | {_f(v['agrupada']['d_auc'])} | {_f(ll['d_logloss'], 4)} "
                 f"[{_f(ll['ic95'][0], 4)}; {_f(ll['ic95'][1], 4)}] | {_f(v['temporal_1950_2004']['d_auc_estratificada'])} | "
                 f"{v['calibracion']['pendiente']:.2f} | **{'sí' if r['veredicto'][k]['establecido'] else 'no'}** |")
    L += ["", "Criterios: " + "; ".join(f"{k}: {v['criterios']}" for k, v in r["veredicto"].items()), "",
          f"Regla de cierre: {r['regla_cierre']}.", "", "## Países de prueba (AUS, CHE; modelos congelados; informativo)", "",
          "| giro · candidato | filas / eventos | ΔAUC estrat. [IC] | ΔAUC agrupada | Δlog-loss |", "|---|---|---|---|---|"]
    for giro, d in r["paises_prueba"].items():
        for c, v in d.items():
            e = v["estratificada"]
            L.append(f"| {giro} · {c} | {v['filas']} / {v['eventos']} | {_f(e['d_auc'])} [{_f(e['ic95'][0])}; "
                     f"{_f(e['ic95'][1])}] | {_f(v['agrupada']['d_auc'])} | {_f(v['d_logloss'], 4)} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
