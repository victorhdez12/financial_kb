"""HPO-INT12 (EXPLORATORIO): ajuste de hiperparámetros del ML de volatilidad de INT-12 con validación cruzada ANIDADA
walk-forward con embargo. Presupuesto, espacio y reglas declarados en docs/int/HPO_INT12_exploratorio.md §1-§3 ANTES
de correr (mismo commit que este código).

- Datos: los de P-DEV-INT12 (scripts/int12_corrida.cargar_real / tabla), SOLO ≤ 2004. Horizonte 1 mes, QLIKE.
- Externo: orígenes 1950-01 … 2004-11 (como INT-12), ventana creciente desde 1934-02, embargo (fin del objetivo ≤ origen
  de la re-estimación), re-estimación cada enero. La configuración se elige al inicio de cada bloque de 5 años
  (1950, 1955, …, 2000) con el bucle INTERNO, que solo usa filas cuyo objetivo acaba ≤ origen de ese enero.
- Interno: validación walk-forward sobre los 10 años anteriores al bloque (5 pliegues de 2 años, re-estimación al inicio
  de cada pliegue con la misma regla de embargo). Se elige la configuración de menor QLIKE medio interno.
- Presupuesto: 60 configuraciones (la 0 = GB de INT-12; 1-59 al azar, semilla 20261104), iguales en todos los bloques.
- Placebo: R = 50 réplicas con (rv, n_dias) barajados por bloques de 12 meses (semillas 20261104 + r) y el
  procedimiento anidado ENTERO repetido; nula de la "ganancia" de la búsqueda frente a HAR.
- Contraste: ganancia QLIKE (HPO-GB frente a HAR), DM-NW (6 retardos) e IC 95 % por bootstrap de bloques estacionario
  (bloque medio 12, 2000 réplicas).

Uso: .venv/bin/python -m scripts.hpo_int12              (árbol limpio; se niega si ya existe la salida)
     .venv/bin/python -m scripts.hpo_int12 --sintetico  (datos sintéticos y presupuesto mínimo; no escribe nada)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import int12 as M

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/hpo_int12"
SEMILLA = 20261104
N_CONFIG = 60
R_PLACEBO = 50
BLOQUE_PLACEBO = 12
BOOT_REPS = 2000
EVAL_DESDE = pd.Period("1950-01", "M")
ENTRENO_DESDE = pd.Period("1934-02", "M")
MITAD = pd.Period("1977-07", "M")
BLOQUES = list(range(1950, 2001, 5))
INTERNO_AÑOS, INTERNO_PLIEGUE = 10, 2
N_JOBS = 12


# ============================================================================ espacio de búsqueda
def configuraciones(n: int = N_CONFIG, seed: int = SEMILLA) -> list[dict]:
    rng = np.random.default_rng(seed)
    cfgs = [dict(rasgos="har+x", modo="directo", learning_rate=0.05, max_iter=300, max_depth=3, min_samples_leaf=20,
                 l2_regularization=1.0, max_features=1.0)]                       # 0 = GB de INT-12
    lu = lambda a, b: float(np.exp(rng.uniform(np.log(a), np.log(b))))         # noqa: E731
    for _ in range(n - 1):
        cfgs.append(dict(rasgos=str(rng.choice(["har", "har+x"])), modo=str(rng.choice(["directo", "residuo"])),
                         learning_rate=round(lu(0.005, 0.2), 5), max_iter=int(round(lu(20, 500))),
                         max_depth=int(rng.integers(1, 6)), min_samples_leaf=int(round(lu(5, 200))),
                         l2_regularization=round(lu(1e-3, 100), 5), max_features=round(float(rng.uniform(0.3, 1.0)), 3)))
    for i, c in enumerate(cfgs):
        c["id"] = i
    return cfgs


def _gb(cfg):
    from sklearn.ensemble import HistGradientBoostingRegressor
    p = {k: cfg[k] for k in ("learning_rate", "max_iter", "max_depth", "min_samples_leaf", "l2_regularization",
                             "max_features")}
    return HistGradientBoostingRegressor(loss="squared_error", early_stopping=False, random_state=SEMILLA, **p)


def ajustar_prever(cfg, Ztr_har, Ztr, y, Zte_har, Zte, n_te) -> np.ndarray:
    """cfg None = HAR (MCO). 'residuo': GB sobre el residuo del HAR lineal. Corrección de Duan como en INT-12."""
    A = np.column_stack([np.ones(len(Ztr_har)), Ztr_har])
    beta = np.linalg.lstsq(A, y, rcond=None)[0]
    base_tr, base_te = A @ beta, np.column_stack([np.ones(len(Zte_har)), Zte_har]) @ beta
    if cfg is None:
        p_tr, p_te = base_tr, base_te
    elif cfg["modo"] == "residuo":
        m = _gb(cfg).fit(Ztr, y - base_tr)
        p_tr, p_te = base_tr + m.predict(Ztr), base_te + m.predict(Zte)
    else:
        m = _gb(cfg).fit(Ztr, y)
        p_tr, p_te = m.predict(Ztr), m.predict(Zte)
    return n_te * np.exp(p_te) * float(np.mean(np.exp(y - p_tr)))


# ============================================================================ walk-forward con embargo
class Datos:
    def __init__(self, T: pd.DataFrame):
        self.T = T
        self.idx = T.index
        self.pos = {m: i for i, m in enumerate(T.index)}
        self.origen = T["origen"].values
        self.fin = T["fin"].values
        ok = T[M.HAR + M.X].notna().all(axis=1).values & (T.index >= ENTRENO_DESDE)
        self.ok = ok
        self.har = T[M.HAR].values.astype(float)
        self.hx = T[M.HAR + M.X].values.astype(float)
        self.rv = T["rv"].values.astype(float)
        self.n = T["n_dias"].values.astype(float)

    def entreno(self, m) -> np.ndarray:
        """Filas de entreno en la re-estimación del mes m (regla de INT-12)."""
        i = self.pos[m]
        msk = self.ok.copy()
        msk[i:] = False
        return np.where(msk & (self.fin <= self.origen[i]))[0]

    def correr(self, cfg, meses: list, refits: set) -> np.ndarray:
        """Previsiones de cfg en `meses`, re-estimando en los meses de `refits` (y en el primero)."""
        out = np.empty(len(meses))
        seg = []
        for j, m in enumerate(meses):
            if j == 0 or m in refits:
                seg.append([m, []])
            seg[-1][1].append(j)
        for m0, js in seg:
            tr = self.entreno(m0)
            te = np.array([self.pos[meses[j]] for j in js])
            Z, Zt = (self.har, self.har) if cfg is None or cfg["rasgos"] == "har" else (self.hx, self.hx)
            y = np.log(self.rv[tr] / self.n[tr])
            out[js] = ajustar_prever(cfg, self.har[tr], Z[tr], y, self.har[te], Zt[te], self.n[te])
        return out


def meses_entre(a: pd.Period, b: pd.Period, idx) -> list:
    return [m for m in idx if a <= m <= b]


def anidado(D: Datos, cfgs: list, eval_hasta: pd.Period, con_todas: bool = False) -> dict:
    """Procedimiento anidado completo. Devuelve previsiones externas HPO y HAR, selección por bloque, tabla interna y
    (con_todas) las previsiones externas de TODAS las configuraciones (solo descriptivo; no se usan para elegir)."""
    internas, sel = [], {}
    ext_meses = meses_entre(EVAL_DESDE, eval_hasta, D.idx)
    f_hpo = np.empty(len(ext_meses))
    for B in BLOQUES:
        v0, v1 = pd.Period(f"{B - INTERNO_AÑOS}-01", "M"), pd.Period(f"{B - 1}-12", "M")
        vm = meses_entre(v0, v1, D.idx)
        refits = {pd.Period(f"{a}-01", "M") for a in range(B - INTERNO_AÑOS, B, INTERNO_PLIEGUE)}
        # embargo del bucle interno respecto al externo: todo objetivo interno acaba ≤ origen de enero de B
        assert max(D.fin[D.pos[m]] for m in vm) <= D.origen[D.pos[pd.Period(f"{B}-01", "M")]]
        te = np.array([D.pos[m] for m in vm])
        q_har = M.qlike(D.correr(None, vm, refits), D.rv[te]).mean()
        mejor = None
        for c in cfgs:
            q = float(M.qlike(D.correr(c, vm, refits), D.rv[te]).mean())
            internas.append({"bloque": B, "config": c["id"], "qlike_interno": q, "qlike_har_interno": float(q_har),
                             "ganancia_interna_vs_har": float(1 - q / q_har)})
            if mejor is None or q < mejor[1]:
                mejor = (c, q)
        sel[B] = {"config": mejor[0]["id"], "qlike_interno": mejor[1], "ganancia_interna_vs_har": float(1 - mejor[1] / q_har)}
        bm = [m for m in ext_meses if B <= m.year <= B + 4]
        js = [ext_meses.index(m) for m in bm]
        f_hpo[js] = D.correr(mejor[0], bm, {m for m in bm if m.month == 1})
    ref_ext = {m for m in ext_meses if m.month == 1}
    out = {"meses": ext_meses, "f_hpo": f_hpo, "f_har": D.correr(None, ext_meses, ref_ext), "seleccion": sel,
           "internas": internas, "rv": D.rv[[D.pos[m] for m in ext_meses]]}
    if con_todas:
        out["f_todas"] = {c["id"]: D.correr(c, ext_meses, ref_ext) for c in cfgs}
    return out


# ============================================================================ contrastes
def boot_indices(n: int, reps: int, bloque: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    idx = np.empty((reps, n), int)
    idx[:, 0] = rng.integers(n, size=reps)
    nuevos = rng.random((reps, n)) < 1 / bloque
    saltos = rng.integers(n, size=(reps, n))
    for i in range(1, n):
        idx[:, i] = np.where(nuevos[:, i], saltos[:, i], (idx[:, i - 1] + 1) % n)
    return idx


def contraste(l_base: np.ndarray, l_ret: np.ndarray, meses: list, seed: int = SEMILLA) -> dict:
    d = l_base - l_ret
    r = M.dm(d, M.lags_nw(len(d), 1))
    ix = boot_indices(len(d), BOOT_REPS, 12, seed)
    gan_b = 1 - l_ret[ix].mean(1) / l_base[ix].mean(1)
    d_b = d[ix].mean(1)
    a = np.array([m < MITAD for m in meses])
    return {"ganancia": float(1 - l_ret.mean() / l_base.mean()), "qlike_liston": float(l_base.mean()),
            "qlike_retador": float(l_ret.mean()), "t_nw": r["t"], "p_nw": r["p"], "ic95_nw_media_d": r["ic95"],
            "ic95_boot_ganancia": [float(np.quantile(gan_b, .025)), float(np.quantile(gan_b, .975))],
            "ic95_boot_media_d": [float(np.quantile(d_b, .025)), float(np.quantile(d_b, .975))],
            "p_boot_unilateral": float((1 + np.sum(d_b - d.mean() >= d.mean())) / (BOOT_REPS + 1)),
            "ganancia_mitad1": float(1 - l_ret[a].mean() / l_base[a].mean()),
            "ganancia_mitad2": float(1 - l_ret[~a].mean() / l_base[~a].mean())}


def resumen(o: dict) -> dict:
    lh, lp = M.qlike(o["f_har"], o["rv"]), M.qlike(o["f_hpo"], o["rv"])
    gi = np.mean([v["ganancia_interna_vs_har"] for v in o["seleccion"].values()])
    return {"ganancia_externa": float(1 - lp.mean() / lh.mean()), "ganancia_interna_media_mejor": float(gi),
            "qlike_har": float(lh.mean()), "qlike_hpo": float(lp.mean())}


# ============================================================================ placebo
def barajar(T: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(T)
    bl = [np.arange(i, min(i + BLOQUE_PLACEBO, n)) for i in range(0, n, BLOQUE_PLACEBO)]
    perm = np.concatenate([bl[k] for k in rng.permutation(len(bl))])
    T2 = T.copy()
    T2["rv"] = T["rv"].values[perm]
    T2["n_dias"] = T["n_dias"].values[perm]
    return T2


def _una_placebo(T, cfgs, eval_hasta, r):
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1):
        o = anidado(Datos(barajar(T, SEMILLA + r)), cfgs, eval_hasta)
    s = resumen(o)
    s.update({"replica": r, "semilla": SEMILLA + r, "seleccion": {str(k): v["config"] for k, v in o["seleccion"].items()}})
    return s


# ============================================================================ principal
def _pc(x):
    return f"{100 * x:+.1f} %".replace(".", ",")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    sint = "--sintetico" in argv
    t0 = time.time()
    from scripts import int12_corrida as C
    if sint:
        d, proc = C.cargar_sintetico(), {"sintetico": True}
        n_cfg, r_pl = 4, 2
    else:
        if SALIDA.exists():
            raise SystemExit(f"{SALIDA} ya existe: corrida única; no se repite")
        from src.intl.procedencia import procedencia
        proc = procedencia()
        d = C.cargar_real()
        n_cfg, r_pl = N_CONFIG, R_PLACEBO
    T = C.tabla(d, 1)
    eval_hasta = T.index[T.index >= EVAL_DESDE].max()
    cfgs = configuraciones(n_cfg)
    from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: F401
    from threadpoolctl import threadpool_limits
    with threadpool_limits(limits=1):
        real = anidado(Datos(T), cfgs, eval_hasta, con_todas=True)
    meses = real["meses"]
    lh, lp = M.qlike(real["f_har"], real["rv"]), M.qlike(real["f_hpo"], real["rv"])
    principal = contraste(lh, lp, meses)
    principal.update(resumen(real))
    todas = []
    for c in cfgs:
        lc = M.qlike(real["f_todas"][c["id"]], real["rv"])
        todas.append({**c, "qlike_externo": float(lc.mean()), "ganancia_externa_vs_har": float(1 - lc.mean() / lh.mean()),
                      "qlike_interno_medio": float(np.mean([x["qlike_interno"] for x in real["internas"]
                                                            if x["config"] == c["id"]]))})
    t1 = time.time()
    from joblib import Parallel, delayed
    pl = Parallel(n_jobs=N_JOBS)(delayed(_una_placebo)(T, cfgs, eval_hasta, r) for r in range(r_pl))
    g_pl = np.array([p["ganancia_externa"] for p in pl])
    gi_pl = np.array([p["ganancia_interna_media_mejor"] for p in pl])
    placebo = {"R": r_pl, "bloque_meses": BLOQUE_PLACEBO,
               "ganancia_externa": {"media": float(g_pl.mean()), "p50": float(np.median(g_pl)),
                                    "p95": float(np.quantile(g_pl, .95)), "max": float(g_pl.max())},
               "ganancia_interna_mejor": {"media": float(gi_pl.mean()), "p95": float(np.quantile(gi_pl, .95))},
               "p_real_vs_placebo": float((1 + np.sum(g_pl >= principal["ganancia_externa"])) / (r_pl + 1)),
               "replicas": pl}
    import sklearn
    o = {"procedencia": proc, "documento": "docs/int/HPO_INT12_exploratorio.md", "semilla": SEMILLA,
         "sklearn": sklearn.__version__, "n_config": n_cfg, "bloques": BLOQUES,
         "interno": {"años": INTERNO_AÑOS, "pliegue_años": INTERNO_PLIEGUE}, "n_eval": len(meses),
         "eval": [str(meses[0]), str(meses[-1])], "principal_hpo_vs_har": principal,
         "seleccion_por_bloque": {str(k): v for k, v in real["seleccion"].items()},
         "configuraciones": cfgs, "placebo": placebo,
         "segundos": {"real": round(t1 - t0), "placebo": round(time.time() - t1)}}
    s = principal
    txt = (f"HPO-GB frente a HAR (anidado, N = {len(meses)}): ganancia {_pc(s['ganancia'])} "
           f"IC95 boot [{_pc(s['ic95_boot_ganancia'][0])}, {_pc(s['ic95_boot_ganancia'][1])}], t {s['t_nw']:.2f}, "
           f"p {s['p_nw']:.4f}; mitades {_pc(s['ganancia_mitad1'])} / {_pc(s['ganancia_mitad2'])}; "
           f"interna media del elegido {_pc(s['ganancia_interna_media_mejor'])}\n"
           f"QLIKE HAR {s['qlike_har']:.4f} (INT-12: 0.2742) · HPO {s['qlike_hpo']:.4f}\n"
           f"placebo: media {_pc(placebo['ganancia_externa']['media'])}, p95 {_pc(placebo['ganancia_externa']['p95'])}, "
           f"p(real ≤ placebo) {placebo['p_real_vs_placebo']:.3f}\n"
           f"selección: {o['seleccion_por_bloque']}")
    print(txt)
    if sint:
        return o
    SALIDA.mkdir(parents=True)
    (SALIDA / "resultado.json").write_text(json.dumps(o, ensure_ascii=False, indent=1, default=str))
    pd.DataFrame(real["internas"]).to_csv(SALIDA / "pruebas_internas.csv", index=False)
    pd.DataFrame(todas).to_csv(SALIDA / "pruebas_externas_todas.csv", index=False)
    pd.DataFrame([{k: v for k, v in p.items() if k != "seleccion"} | {"seleccion": json.dumps(p["seleccion"])}
                  for p in pl]).to_csv(SALIDA / "placebo.csv", index=False)
    pd.DataFrame({"mes": [str(m) for m in meses], "rv": real["rv"], "f_har": real["f_har"], "f_hpo": real["f_hpo"]}
                 ).to_csv(SALIDA / "previsiones.csv", index=False)
    (SALIDA / "resumen.txt").write_text(txt + "\n")
    return o


if __name__ == "__main__":
    main()
