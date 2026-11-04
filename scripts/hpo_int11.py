"""HPO EXPLORATORIO del motor de escenarios INT-11 v3 (docs/int/HPO_INT11_exploratorio.md). Config "v3-hpo".

NO toca Config.v3 (congelada, va a la confirmación), ni research/int/int11_v3_resultado.json, ni la salida "hoy".
Solo ≤ 2004 (cargar_real_v3 → load_dev). Todo lo que sale de aquí CONTAMINA el desarrollo (≤ 2004): cualquier "v4"
que salga necesita prerregistro propio y su evidencia solo puede venir del periodo bloqueado.

Diseño (declarado antes de correr; §2 del doc):
- Candidatos: θ0 = Config.v3() exacta + N_ALEAT configuraciones aleatorias (semilla SEMILLA_ESPACIO) del espacio ESPACIO.
- Predictiva H = 1 con pertenencia suave (como int11v3.evaluar_suave): mezcla de los 4 regímenes de partida con
  pesos_estado(π_{t−1}, brecha_{t−1}, σπ, σb) de la configuración. N_LOTES × POR_LOTE sorteos por régimen.
- Ajustes: 14 LOCO simples (fuera c → predice c) + 91 pares (fuera {c, d} → predice c y d). Números aleatorios
  comunes entre configuraciones (misma semilla por pliegue, país y régimen).
- Puntuaciones por fila y activo: CRPS de la mezcla ponderada, log-score (núcleo gaussiano por régimen, Silverman),
  PIT = F(y) de la mezcla, dentro del p5-p95 (cuantil de la CDF de la mezcla, int11v3._cuantiles_filas), anchura.
- Anidado (analiza): para cada país externo c, el interno = LOCO sobre los otros 13 con los ajustes de pares
  (fuera {c, d} → d). Regla de elección (fijada antes): admisibles = |S5_int − 0,90| ≤ 0,01 y todo activo
  |S_a,int − 0,90| ≤ 0,03; entre ellos, menor CRPS relativo a v3 (media por activo de ΣCRPS_θ / ΣCRPS_v3, mismas filas);
  si ninguno, v3. El externo evalúa c con la θ elegida (ajuste LOCO simple, fuera c).
- Comparación con v3 en las mismas filas: diferencias con IC 90 % por bloques móviles de años (5 años, B = 2000).
- Variación Monte Carlo: todo se repite con SEMILLAS_MC[1]; v3(semilla A) frente a v3(semilla B) da el ruido MC.

Uso: .venv/bin/python -m scripts.hpo_int11 corre --semilla 0   (índice en SEMILLAS_MC; árbol limpio)
     .venv/bin/python -m scripts.hpo_int11 analiza              (lee las dos corridas; árbol limpio)
     .venv/bin/python -m scripts.hpo_int11 prueba               (2 configuraciones, pocos sorteos; no escribe)
"""
from __future__ import annotations

import itertools
import json
import pickle
import sys
import time
import warnings
from dataclasses import asdict
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy import stats

from scripts.int11_corrida import NUCLEO
from scripts.int11_v3_corrida import cargar_real_v3
from src.intl import data as D
from src.intl import escenarios as E
from src.intl import int11v3 as V
from src.intl.procedencia import procedencia

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/hpo_int11"
N_ALEAT = 80
SEMILLA_ESPACIO = 20261105
SEMILLAS_MC = (20261104, 20261204)
N_LOTES, POR_LOTE = 50, 100
TOL_S5, TOL_ACT = 0.01, 0.03
BLOQUE_AÑOS, B_BOOT = 5, 2000
ACTS = list(E.ACTIVOS)
N_TRAB = 8
A = len(ACTS)

# espacio (declarado antes de correr). κ: "eb" = rejilla de Bayes empírico de v3 (log10 κ ∈ [0, 6]); si no, log10 κ fijo
ESPACIO = {
    "c_suavizado": ("uniforme", 1.0, 10.0),
    "nu_suavizado": ("elige", (3.0, 4.0, 5.0, 7.0, 10.0, 30.0)),
    "sigma_infl": ("uniforme", 0.0, 0.0125),
    "sigma_brecha": ("uniforme", 0.0, 0.025),
    "n0_curtosis": ("logunif", 5.0, 1000.0),
    "semivida_epoca": ("elige", (0.0, 25.0, 35.0, 50.0, 75.0, 100.0, 150.0)),
    "n_min_celda": ("elige", (15, 20, 25, 30, 40, 50)),
    "log10_kappa": ("eb_o_uniforme", 0.0, 4.0),
}


def candidatos() -> list[dict]:
    rng = np.random.default_rng(SEMILLA_ESPACIO)
    out = [{"id": 0, "nombre": "v3", "params": {}}]
    for i in range(1, N_ALEAT + 1):
        p = {}
        for k, d in ESPACIO.items():
            if d[0] == "uniforme":
                p[k] = round(float(rng.uniform(d[1], d[2])), 5)
            elif d[0] == "logunif":
                p[k] = round(float(np.exp(rng.uniform(np.log(d[1]), np.log(d[2])))), 2)
            elif d[0] == "elige":
                p[k] = d[1][int(rng.integers(len(d[1])))]
            elif d[0] == "eb_o_uniforme":
                p[k] = "eb" if rng.random() < 0.5 else round(float(rng.uniform(d[1], d[2])), 3)
        out.append({"id": i, "nombre": f"hpo{i:03d}", "params": p})
    return out


def config(params: dict) -> E.Config:
    p = dict(params)
    lk = p.pop("log10_kappa", "eb")
    if "n_min_celda" in p:
        p["n_min_celda"] = int(p["n_min_celda"])
    if lk != "eb":
        p["rejilla_kappa"] = (float(lk), float(lk), 1)
    return E.Config.v3(**p)


# ============================================================================ puntuación de la mezcla ponderada
def puntuar(ms: list[np.ndarray], W: np.ndarray, y: np.ndarray) -> dict:
    """ms: K muestras (vacías si peso 0); W (m, K) pesos de la mezcla; y (m,). CRPS, log-score, PIT, dentro90, ancho."""
    K = len(ms)
    x = np.concatenate(ms)
    lab = np.concatenate([np.full(len(m), k) for k, m in enumerate(ms)])
    n = np.array([max(len(m), 1) for m in ms], float)
    o = np.argsort(x, kind="stable")
    x, lab = x[o], lab[o]
    w = (W / n[None, :])[:, lab]                                       # (m, N)
    w /= w.sum(1, keepdims=True)
    C = np.cumsum(w, 1)
    e_xy = np.sum(w * np.abs(x[None, :] - y[:, None]), 1)
    e_xx = 2 * np.sum(w * x[None, :] * ((C - w) - (1 - C)), 1)
    crps = e_xy - 0.5 * e_xx
    pit = np.sum(w * (x[None, :] <= y[:, None]), 1)
    dens = np.zeros(len(y))
    for k, m in enumerate(ms):
        if len(m) < 2 or not (W[:, k] > 0).any():
            continue
        s = np.std(m, ddof=1)
        iq = stats.iqr(m) / 1.349
        s = min(s, iq) if iq > 0 else s
        bw = 0.9 * s * len(m) ** (-0.2)
        dk = stats.norm.pdf((y[:, None] - m[None, :]) / bw).mean(1) / bw
        dens += W[:, k] / W.sum(1) * dk
    ls = -np.log(np.maximum(dens, 1e-300))
    q = V._cuantiles_filas(ms, W, (0.05, 0.95))
    return {"crps": crps, "ls": ls, "pit": pit, "dentro": ((y >= q[0]) & (y <= q[1])).astype(float),
            "ancho": q[1] - q[0]}


# ============================================================================ corrida de una configuración
_F = None


def _init():
    global _F
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    _F = cargar_real_v3(D.connect())


def evaluar_config(args) -> dict:
    cand, semilla, n_lotes, por_lote = args
    f = E.recalcular_sucesor(_F)
    cfg = config(cand["params"])
    V_ = f[ACTS].to_numpy(float)
    pais = f["pais"].to_numpy()
    paises = sorted(set(pais))
    sp, sb = cfg.sigma_infl, cfg.sigma_brecha
    if sp > 0 or sb > 0:
        W = np.array([E.pesos_estado(a, b, sp, sb) for a, b in zip(f["infl_prev"], f["brecha_prev"])])
    else:
        W = np.eye(E.K)[f["s_prev"].to_numpy(int)]
    m = len(f)
    met = ("crps", "ls", "pit", "dentro", "ancho")
    simple = {k: np.full((m, A), np.nan) for k in met}
    par = {k: np.full((len(paises), m, A), np.nan) for k in met}       # par[k][i_c, fila de d, a]: fuera {c, d}
    t0 = time.time()

    def predice(gen, c, fold, destino):
        idx = np.flatnonzero(pais == c)
        Wc = W[idx]
        usa = np.flatnonzero(Wc.max(0) > 0)
        R = {}
        for s0 in usa:
            esc = gen.simular(c, int(s0), horizonte=1, n_lotes=n_lotes, por_lote=por_lote,
                              semilla=semilla + 1000 * fold + 10 * paises.index(c) + int(s0))
            R[s0] = esc.rent[:, 0, :]
        for j in range(A):
            ms = [R[s][np.isfinite(R[s][:, j]), j] if s in R else np.zeros(0) for s in range(E.K)]
            if min(len(ms[s]) for s in usa) < 30:
                continue
            y = V_[idx, j]
            ok = np.isfinite(y)
            if not ok.any():
                continue
            sc = puntuar(ms, Wc[ok], y[ok])
            for k in met:
                destino[k][idx[ok], j] = sc[k]

    for k, c in enumerate(paises):
        gen = E.Generador(cfg).ajustar(E.recalcular_sucesor(f[pais != c]))
        predice(gen, c, k, simple)
    for p_i, (c, d) in enumerate(itertools.combinations(paises, 2)):
        gen = E.Generador(cfg).ajustar(E.recalcular_sucesor(f[(pais != c) & (pais != d)]))
        ic, id_ = paises.index(c), paises.index(d)
        predice(gen, d, 100 + p_i, {k: par[k][ic] for k in met})
        predice(gen, c, 100 + p_i, {k: par[k][id_] for k in met})
    return {"id": cand["id"], "simple": simple, "par": par, "segundos": time.time() - t0,
            "config": asdict(cfg)}


def corre(i_sem: int, prueba: bool = False) -> None:
    semilla = SEMILLAS_MC[i_sem]
    proc = {"prueba": True} if prueba else procedencia()
    cands = candidatos()[:2] if prueba else candidatos()
    n_lotes, por_lote = (5, 100) if prueba else (N_LOTES, POR_LOTE)
    t0 = time.time()
    # caché por configuración (reanudable: un trabajador muerto dejaba colgado imap; 4-nov). Mismo resultado: cada
    # configuración es determinista dada la semilla.
    cache = SALIDA / f"cache_s{i_sem}"
    cache.mkdir(parents=True, exist_ok=True)
    res = []
    for c in cands:
        p = cache / f"cfg{c['id']:03d}.pkl"
        if not prueba and p.exists():
            res.append(pickle.loads(p.read_bytes()))
    hechos = {r["id"] for r in res}
    pend = [(c, semilla, n_lotes, por_lote) for c in cands if c["id"] not in hechos]
    with Pool(N_TRAB if not prueba else 2, initializer=_init, maxtasksperchild=4) as pool:
        for r in pool.imap_unordered(evaluar_config, pend):
            r["procedencia"] = proc
            if not prueba:
                (cache / f"cfg{r['id']:03d}.pkl").write_bytes(pickle.dumps(r))
            res.append(r)
            print("config", r["id"], round(r["segundos"]), "s", len(res), "/", len(cands), flush=True)
    res.sort(key=lambda r: r["id"])
    if prueba:
        for r in res:
            print(r["id"], {k: np.nanmean(r["simple"][k], 0).round(4).tolist() for k in ("crps", "dentro")})
        return
    SALIDA.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(SALIDA / f"corrida_s{i_sem}.npz",
                        **{f"{k}_simple": np.stack([r["simple"][k] for r in res]) for k in res[0]["simple"]},
                        **{f"{k}_par": np.stack([r["par"][k] for r in res]).astype(np.float32) for k in res[0]["par"]})
    f = cargar_real_v3(D.connect())
    meta = {"procedencia": proc, "semilla": semilla, "n_lotes": n_lotes, "por_lote": por_lote,
            "candidatos": cands, "procedencia_por_config": {r["id"]: r.get("procedencia") for r in res}, "config_completa": {r["id"]: r["config"] for r in res},
            "segundos": round(time.time() - t0), "filas": int(len(f)),
            "años": [int(f["año"].min()), int(f["año"].max())]}
    (SALIDA / f"corrida_s{i_sem}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1, default=str))
    print("segundos", meta["segundos"])


if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    if sys.argv[1] == "corre":
        corre(int(sys.argv[sys.argv.index("--semilla") + 1]))
    elif sys.argv[1] == "prueba":
        corre(0, prueba=True)
    elif sys.argv[1] == "analiza":
        from scripts.hpo_int11_analiza import main
        main()
