"""HPO-ML-RECESIÓN: ajuste de hiperparámetros EXPLORATORIO del ML de recesión (docs/int/HPO_ML_recesion_exploratorio.md).
NO reabre la línea ML (INT-4-ML cerrada; INT-10 sin potencia): comprueba si una búsqueda seria de hiperparámetros con
validación cruzada ANIDADA cambia la conclusión. Solo datos ≤ 2004 (mismas filas que INT-4 / INT-4-ML: núcleo 14 países,
1871-2004 sin guerras, h = 1, casos completos; T1 entrada en recesión, T2 salida).

Esquema (fijado en el documento antes de correr):
- Externo: dejar un país fuera (14 pliegues), como INT-4. Interno: dejar un país fuera sobre los 13 países de ajuste
  (13 pliegues). El ajuste interno sin {c, d} es el mismo para el pliegue externo c y para el d: se ajusta una vez por
  par (91 pares) y se predice c y d. Criterio interno: AUC estratificada por país de las predicciones internas juntas.
- Candidatos (presupuesto igual: 20 configuraciones por candidato, muestreo aleatorio con semilla fija del espacio
  declarado; la lista exacta está en research/int/hpo_ml_recesion/espacio.json, generada antes de ver ningún dato):
  GB (HistGradientBoosting), RF (bosque aleatorio, 100 árboles), EN (logit regularizado L1/L2/elastic net, con o sin
  interacciones). Selector global TODOS: el interno elige entre las 60.
- Listón: logit de INT-4 (B1 + indicadores, sin penalizar) en los mismos pliegues externos; métrica principal AUC
  estratificada por país (arreglo del sesgo LOCO del intercepto). Secundaria Δlog-loss.
- IC: bootstrap por bloques de año (2.000). Placebo: objetivo permutado por bloques dentro de cada país (bloques de 5
  filas en T1, 3 en T2), 30 réplicas, TODO el procedimiento anidado repetido (incl. el logit). Holm-8 (4 selectores × 2).
Uso: .venv/bin/python -m scripts.hpo_ml_recesion [--espacio] [--prueba]
  --espacio  solo escribe espacio.json (sin datos).
  --prueba   presupuesto mínimo, salida ENMASCARADA (solo tiempos y tamaños) en el directorio temporal; sin puerta.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "1"     # máquina compartida: un hilo por proceso (no cambia el resultado)

import datetime as dt  # noqa: E402
import itertools  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
import warnings  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import sklearn  # noqa: E402
from joblib import Parallel, delayed  # noqa: E402
from scipy.stats import loguniform, norm  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier  # noqa: E402
from sklearn.exceptions import ConvergenceWarning  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.model_selection import ParameterSampler  # noqa: E402

from scripts.int4_corrida import COLS, NUCLEO, REPO, TODOS, _r, materias_primas  # noqa: E402
from scripts.int4_sensibilidad_liston import auc_estrat, boot  # noqa: E402
from scripts.int4ml_corrida import boot_ll  # noqa: E402
from src.intl import data as D  # noqa: E402
from src.intl import int3 as I3  # noqa: E402
from src.intl import int4 as M  # noqa: E402
from src.intl import int4ml as ML  # noqa: E402
from src.intl import panel as P  # noqa: E402
from src.intl.procedencia import procedencia  # noqa: E402
from src.warehouse import db  # noqa: E402

PRUEBA = "--prueba" in sys.argv
SALIDA = REPO / "research" / "int" / "hpo_ml_recesion"
GIROS = ["T1", "T2"]
PRESUPUESTO = 20                      # configuraciones por candidato (igual para todos)
N_PLACEBO = 30                        # réplicas del placebo (objetivo permutado por bloques dentro de país)
BLOQUE = {"T1": 5, "T2": 3}           # longitud de bloque del placebo (filas consecutivas del país)
B_BOOT = 2000
N_JOBS = 5                            # procesos en paralelo (máquina compartida; no cambia el resultado)
MDE = {"T1": (0.05, 0.07), "T2": (0.05, 0.07)}   # INT-4-ML §4 (r 0,8-0,9, Holm-4); INT-10: T1 0,040 (un contraste)
ESPACIO = {
    "GB": {"max_depth": [1, 2, 3, 4], "learning_rate": loguniform(0.01, 0.2), "max_iter": [50, 100, 200, 400],
           "min_samples_leaf": [10, 20, 40, 80], "l2_regularization": [0.0, 0.1, 1.0, 10.0], "monotonia": [True, False]},
    "RF": {"max_depth": [2, 3, 4, 6, None], "min_samples_leaf": [5, 10, 20, 40, 80], "max_features": ["sqrt", 0.5, 1.0],
           "max_samples": [None, 0.5]},
    "EN": {"C": loguniform(1e-3, 10.0), "l1_ratio": [0.0, 0.25, 0.5, 0.75, 1.0], "interacciones": [False, True]},
}
CANDIDATOS = list(ESPACIO)
SELECTORES = CANDIDATOS + ["TODOS"]


def configuraciones(presupuesto: int = PRESUPUESTO) -> list[dict]:
    out = []
    for i, c in enumerate(CANDIDATOS):
        for j, p in enumerate(ParameterSampler(ESPACIO[c], presupuesto, random_state=i)):
            p = {k: (round(float(v), 6) if isinstance(v, (float, np.floating)) else v) for k, v in p.items()}
            out.append({"id": f"{c}{j:02d}", "candidato": c, "params": p})
    return out


# ---------------------------------------------------------------- modelos
class EN:
    def __init__(self, n_b1, C, l1_ratio, interacciones):
        self.n_b1, self.C, self.l1, self.inter = n_b1, C, l1_ratio, interacciones

    def _d(self, X, fit):
        if fit:
            self.mu, self.sd = X.mean(0), X.std(0)
            self.sd[self.sd == 0] = 1.0
        Z = (X - self.mu) / self.sd
        if not self.inter:
            return Z
        ind = Z[:, self.n_b1:]
        I = np.column_stack([ind[:, i] * ind[:, j] for i, j in itertools.combinations(range(ind.shape[1]), 2)])
        if fit:
            self.mi, self.si = I.mean(0), I.std(0)
            self.si[self.si == 0] = 1.0
        return np.column_stack([Z, (I - self.mi) / self.si])

    def fit(self, X, y):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            self.m = LogisticRegression(penalty="elasticnet", solver="saga", C=self.C, l1_ratio=self.l1, max_iter=5000,
                                        tol=1e-4, random_state=0).fit(self._d(X, True), y)
        return self

    def predict(self, X):
        return self.m.predict_proba(self._d(X, False))[:, 1]


class SK:
    def __init__(self, m):
        self.m = m

    def fit(self, X, y):
        self.m.fit(X, y)
        return self

    def predict(self, X):
        return self.m.predict_proba(X)[:, 1]


def modelo(cfg: dict, giro: str, n_b1: int, cols: list[str]):
    p = dict(cfg["params"])
    if cfg["candidato"] == "GB":
        mono = p.pop("monotonia")
        cst = [0] * n_b1 + ([ML.MONOTONIA[giro][c] for c in cols] if mono else [0] * len(cols))
        return SK(HistGradientBoostingClassifier(monotonic_cst=cst, early_stopping=False, random_state=0, **p))
    if cfg["candidato"] == "RF":
        return SK(RandomForestClassifier(n_estimators=100, n_jobs=1, random_state=0, **p))
    return EN(n_b1, **p)


# ---------------------------------------------------------------- procedimiento anidado (una réplica)
def una_config(X, y, g, cfg, giro, n_b1, cols) -> tuple[np.ndarray, np.ndarray]:
    """Para UNA configuración: predicción LOCO externa (= reajuste final si el interno la elige) y su puntuación interna
    (AUC estratificada de las predicciones internas juntas) en cada pliegue externo. q[c][d] = predicción sobre d del
    modelo ajustado sin {c, d} (el mismo ajuste sirve al pliegue externo c y al d)."""
    paises = list(np.unique(g))
    fil = {c: g == c for c in paises}
    p_ext = np.full(len(y), np.nan)
    q = {c: {} for c in paises}
    for c in paises:
        p_ext[fil[c]] = modelo(cfg, giro, n_b1, cols).fit(X[~fil[c]], y[~fil[c]]).predict(X[fil[c]])
    for c, d in itertools.combinations(paises, 2):
        tr = ~(fil[c] | fil[d])
        m = modelo(cfg, giro, n_b1, cols).fit(X[tr], y[tr])
        q[c][d] = m.predict(X[fil[d]])
        q[d][c] = m.predict(X[fil[c]])
    S = np.full(len(paises), np.nan)
    for i, c in enumerate(paises):
        resto = [d for d in paises if d != c]
        S[i] = auc_estrat(np.concatenate([y[fil[d]] for d in resto]), np.concatenate([q[c][d] for d in resto]),
                          np.concatenate([g[fil[d]] for d in resto]))
    return p_ext, S


def seleccionar(P_ext, S, cfgs, y, g) -> tuple[dict, dict]:
    """El interno elige, en cada pliegue externo, la configuración con mayor puntuación interna (empate: la primera)."""
    paises = list(np.unique(g))
    cand = np.array([c["candidato"] for c in cfgs])
    sel, elig = {}, {}
    for s in SELECTORES:
        idx = np.arange(len(cfgs)) if s == "TODOS" else np.flatnonzero(cand == s)
        p = np.full(len(y), np.nan)
        e = {}
        for i, c in enumerate(paises):
            kb = idx[int(np.argmax(S[i, idx]))]
            p[g == c] = P_ext[kb, g == c]
            e[c] = cfgs[kb]["id"]
        sel[s], elig[s] = p, e
    return sel, elig


def permutar(y, g, t, L, semilla) -> np.ndarray:
    rng = np.random.default_rng(semilla)
    yp = y.copy()
    for c in np.unique(g):
        idx = np.flatnonzero(g == c)
        idx = idx[np.argsort(t[idx], kind="stable")]
        bl = [idx[i:i + L] for i in range(0, len(idx), L)]
        orden = rng.permutation(len(bl))
        yp[idx] = y[np.concatenate([bl[o] for o in orden])]
    return yp


def placebo_rep(r, X, y, g, t, cfgs, giro, n_b1, cols) -> dict:
    yp = permutar(y, g, t, BLOQUE[giro], 10_000 + r)
    partes = [una_config(X, yp, g, c, giro, n_b1, cols) for c in cfgs]
    P_ext, S = np.vstack([a for a, _ in partes]), np.column_stack([b for _, b in partes])
    sel, _ = seleccionar(P_ext, S, cfgs, yp, g)
    a0 = auc_estrat(yp, ML.loco(ML.Logit, X, yp, g), g)
    return {"d": {s: auc_estrat(yp, sel[s], g) - a0 for s in SELECTORES},
            "d_max_no_anidado": float(max(auc_estrat(yp, P_ext[k], g) for k in range(len(cfgs))) - a0)}


# ---------------------------------------------------------------- datos (idénticos a INT-4-ML)
def datos() -> dict:
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
    out = {}
    for giro in GIROS:
        cols = COLS[giro]
        f = (M.obj_entrada if giro == "T1" else M.obj_salida)(rec, años_pais, NUCLEO, 1, 1871, True)
        B1, Xc = M.liston(f, giro, rec, primer, pan), M.matriz(f, pan, cols)
        ok = np.isfinite(B1).all(axis=1) & np.isfinite(Xc).all(axis=1)
        f = f[ok].reset_index(drop=True)
        assert int(f.t.max()) + 1 <= 2004, "regla: solo datos ≤ 2004"
        out[giro] = {"X": np.column_stack([B1[ok], Xc[ok]]), "y": f.y.to_numpy(float), "g": f.pais.to_numpy(),
                     "t": f.t.to_numpy(), "n_b1": B1.shape[1], "cols": cols}
    return out


def main() -> None:
    cfgs_all = configuraciones()
    if "--espacio" in sys.argv:
        SALIDA.mkdir(parents=True, exist_ok=True)
        (SALIDA / "espacio.json").write_text(json.dumps(
            {"presupuesto_por_candidato": PRESUPUESTO, "n_placebo": N_PLACEBO, "bloque_placebo": BLOQUE,
             "espacio": {c: {k: (v if isinstance(v, list) else f"loguniform{v.args}") for k, v in e.items()}
                         for c, e in ESPACIO.items()},
             "rf_fijo": {"n_estimators": 100, "random_state": 0}, "gb_fijo": {"early_stopping": False, "random_state": 0},
             "en_fijo": {"solver": "saga", "max_iter": 5000, "tol": 1e-4, "estandarizacion": "pliegue de ajuste"},
             "configuraciones": cfgs_all}, indent=1, ensure_ascii=False))
        return
    proc = procedencia(exigir_limpio=not PRUEBA)
    cfgs = configuraciones(2) if PRUEBA else cfgs_all
    if not PRUEBA:
        congelado = json.loads((SALIDA / "espacio.json").read_text())["configuraciones"]
        assert congelado == json.loads(json.dumps(cfgs)), "las configuraciones no coinciden con espacio.json congelado"
    n_pl = 2 if PRUEBA else N_PLACEBO
    Dd = datos()
    res = {"procedencia": proc, "documento": "docs/int/HPO_ML_recesion_exploratorio.md", "exploratorio": True,
           "versiones": {"scikit-learn": sklearn.__version__, "numpy": np.__version__},
           "presupuesto_por_candidato": len(cfgs) // len(CANDIDATOS), "n_placebo": n_pl, "giros": {}}
    for giro in GIROS:
        d = Dd[giro]
        X, y, g, t, nb, cols = d["X"], d["y"], d["g"], d["t"], d["n_b1"], d["cols"]
        t0 = time.time()
        # observado: paraleliza por configuración (cada tarea hace el anidado de UNA configuración)
        partes = Parallel(n_jobs=N_JOBS)(delayed(una_config)(X, y, g, c, giro, nb, cols) for c in cfgs)
        p_ext, S = np.vstack([a for a, _ in partes]), np.column_stack([b for _, b in partes])
        p_log = ML.loco(ML.Logit, X, y, g)
        sel, elig = seleccionar(p_ext, S, cfgs, y, g)
        t_obs = time.time() - t0
        t0 = time.time()
        pl = Parallel(n_jobs=N_JOBS)(delayed(placebo_rep)(r, X, y, g, t, cfgs, giro, nb, cols) for r in range(n_pl))
        t_pl = time.time() - t0
        a_log = auc_estrat(y, p_log, g)
        G = {"filas": int(len(y)), "eventos": int(y.sum()), "indicadores": cols, "auc_estrat_logit": a_log,
             "logloss_logit": M.logloss(y, p_log), "segundos": {"observado": t_obs, "placebo": t_pl}, "selectores": {},
             "registro_configuraciones": []}
        for k, c in enumerate(cfgs):    # registro de TODAS las pruebas: puntuación interna media y LOCO no anidado
            G["registro_configuraciones"].append(
                {"id": c["id"], "candidato": c["candidato"], "params": c["params"],
                 "interna_media": float(np.mean(S[:, k])), "interna_min": float(np.min(S[:, k])),
                 "interna_max": float(np.max(S[:, k])), "loco_no_anidado_auc_estrat": auc_estrat(y, p_ext[k], g),
                 "loco_no_anidado_d": auc_estrat(y, p_ext[k], g) - a_log,
                 "loco_no_anidado_logloss": M.logloss(y, p_ext[k]), "veces_elegida": {
                     s: sum(v == c["id"] for v in elig[s].values()) for s in SELECTORES}})
        d_max = max(r["loco_no_anidado_d"] for r in G["registro_configuraciones"])
        G["optimismo_no_anidado"] = {"d_max_no_anidado": d_max,
                                     "placebo_d_max_no_anidado": [x["d_max_no_anidado"] for x in pl]}
        for s in SELECTORES:
            p = sel[s]
            obs = auc_estrat(y, p, g) - a_log
            ds = np.array([x["d"][s] for x in pl])
            G["selectores"][s] = {
                "estratificada": boot(y, p, p_log, t, g, auc_estrat, B=B_BOOT),
                "logloss": boot_ll(y, p, p_log, t, B=B_BOOT), "calibracion": M.calibracion(y, p),
                "placebo": ML.z_placebo(obs, ds), "placebo_cuantiles": {q: float(np.quantile(ds, q)) for q in
                                                                        (0.05, 0.5, 0.95)},
                "elecciones": elig[s]}
        res["giros"][giro] = G
        if PRUEBA:
            print(giro, "filas", len(y), "configs", len(cfgs), "s observado", round(t_obs, 1), "s placebo", round(t_pl, 1),
                  flush=True)
        else:
            print(giro, {s: round(v["estratificada"]["d_auc"], 4) for s, v in G["selectores"].items()}, flush=True)
    if PRUEBA:
        out = Path(tempfile.mkdtemp(prefix="hpo_prueba_"))
        (out / "tiempos.json").write_text(json.dumps({g: v["segundos"] for g, v in res["giros"].items()}))
        print("prueba (enmascarada) en", out)
        return
    claves = [(gi, s) for gi in GIROS for s in SELECTORES]
    h_i = I3.holm({f"{gi}|{s}": res["giros"][gi]["selectores"][s]["estratificada"]["p_bloques"] for gi, s in claves})
    h_ii = I3.holm({f"{gi}|{s}": res["giros"][gi]["selectores"][s]["placebo"]["p_z"] for gi, s in claves})
    ver = {}
    for gi, s in claves:
        v, k = res["giros"][gi]["selectores"][s], f"{gi}|{s}"
        dd = v["estratificada"]["d_auc"]
        crit = {"a_ic_holm": bool(dd > 0 and h_i[k]), "b_placebo_holm": bool(h_ii[k]),
                "c_dlogloss_neg": bool(v["logloss"]["d_logloss"] < 0), "d_supera_mde_0.05": bool(dd >= MDE[gi][0])}
        ver[k] = {"criterios": crit, "candidata_a_prerregistro": all(crit.values())}
    res["veredicto"] = ver
    res["hora_fin_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    R = _r(res)
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "resultado.json").write_text(json.dumps(R, indent=1, ensure_ascii=False))
    (SALIDA / "resultado.md").write_text(informe(R))
    linea = (f"| {res['hora_fin_utc']} | Constructor (HPO-ML-RECESIÓN, EXPLORATORIO declarado; no reabre INT-4-ML) | "
             f"{proc['commit'][:7]} | Validación cruzada anidada (externo e interno dejar un país fuera), GB/RF/EN × "
             f"{PRESUPUESTO} configuraciones + selector global (60), T1 y T2, frente al logit de INT-4, AUC estratificada; "
             f"placebo objetivo permutado por bloques ({N_PLACEBO}); Holm-8. Candidatas a prerregistro: "
             f"{[k for k, v in ver.items() if v['candidata_a_prerregistro']]}. 60 × 2 configuraciones registradas. "
             f"Nada ≥ 2005 | research/int/hpo_ml_recesion/resultado.{{json,md}} |\n")
    with open(REPO / "research" / "trial_log.md", "a") as fh:
        fh.write(linea)
    print(json.dumps(_r(ver), indent=1, ensure_ascii=False))


def _f(v, k=3):
    return "–" if v is None else f"{v:+.{k}f}"


def informe(r: dict) -> str:
    p = r["procedencia"]
    L = ["# HPO-ML-RECESIÓN (exploratorio): resultado anidado", "",
         f"Procedencia: commit `{p['commit'][:7]}`, árbol limpio {p['arbol_limpio']}, {p['hora_utc']} → {r['hora_fin_utc']}. "
         f"scikit-learn {r['versiones']['scikit-learn']}. Presupuesto {r['presupuesto_por_candidato']} configuraciones por "
         f"candidato; placebo {r['n_placebo']} réplicas. Listón: logit de INT-4. Métrica: AUC estratificada por país.", ""]
    for gi, G in r["giros"].items():
        L += [f"## {gi} ({G['filas']} filas / {G['eventos']} eventos; AUC estrat. logit {G['auc_estrat_logit']:.3f})", "",
              "| selector | AUC estrat. | ΔAUC anidada | IC 95 % bloques | p bloques | placebo media [p5; p95] | z (p) | "
              "Δlog-loss [IC] | pendiente | ¿candidata? |", "|---|---|---|---|---|---|---|---|---|---|"]
        for s, v in G["selectores"].items():
            e, pl, ll, q = v["estratificada"], v["placebo"], v["logloss"], v["placebo_cuantiles"]
            L.append(f"| {s} | {e['auc_modelo']:.3f} | {_f(e['d_auc'])} | [{_f(e['ic95'][0])}; {_f(e['ic95'][1])}] | "
                     f"{e['p_bloques']:.3f} | {_f(pl['media'])} [{_f(q['0.05'])}; {_f(q['0.95'])}] | {pl['z']:+.2f} "
                     f"({pl['p_z']:.3f}) | {_f(ll['d_logloss'], 4)} [{_f(ll['ic95'][0], 4)}; {_f(ll['ic95'][1], 4)}] | "
                     f"{v['calibracion']['pendiente']:.2f} | {'sí' if r['veredicto'][f'{gi}|{s}']['candidata_a_prerregistro'] else 'no'} |")
        o = G["optimismo_no_anidado"]
        pm = np.array(o["placebo_d_max_no_anidado"])
        L += ["", f"Optimismo de elegir SIN anidar: la mejor de las 60 configuraciones medida en el propio LOCO externo da "
              f"ΔAUC {_f(o['d_max_no_anidado'])} (placebo: media {_f(float(pm.mean()))}, p95 {_f(float(np.quantile(pm, 0.95)))}).",
              "", "Mejores 5 configuraciones por puntuación interna media (registro completo en resultado.json):", "",
              "| id | params | interna media | LOCO no anidado ΔAUC |", "|---|---|---|---|"]
        for c in sorted(G["registro_configuraciones"], key=lambda c: -c["interna_media"])[:5]:
            L.append(f"| {c['id']} | `{json.dumps(c['params'])}` | {c['interna_media']:.3f} | {_f(c['loco_no_anidado_d'])} |")
        L.append("")
    L += ["Criterios (todos para 'candidata a prerregistro'): " + "; ".join(
        f"{k}: {v['criterios']}" for k, v in r["veredicto"].items()), ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
