"""Potencia de P-EVAL-BASE v4 — capa 1, forma reducida (solo sintético; no lee datos ni la etiqueta).

Se simula directamente d_t = ll(M0)_t − ll(pool)_t en una ventana de n meses (202 = 2005-01 → 2021-10, la del borrador;
250 como sensibilidad) con:
- calendario: k recesiones (cada una, un tramo de G bajo de 8-20 meses, posición al azar) + Poisson(1) desaceleraciones
  cortas (4-8 meses) + Poisson(2) cambios del eje I. La marca de giro del arnés es dura(t) ≠ dura(t−5): 5 meses por
  cambio de la etiqueta dura (G o I). Los meses de giro de G son los de las entradas y salidas de tramos de G bajo;
- ruido: AR(1) con innovaciones t_4, desviación ×2 en los meses de giro de G, más un efecto común por episodio de giro de
  G (u ~ N(0, (τ·σ_giro)²)), escalado para que la desviación marginal de d sea `sd`;
- efecto de media Δ (exacta en cada réplica) con forma `mixto` (mitad del efecto total en los meses de giro de G,
  mitad en el resto), `uniforme` o `giros` (todo en los meses de giro de G).

Diseños (ver DISEÑOS): el v4 tal cual (criterios 1, 2, 3, 4, 6 y 7 de A3; el 5 y el 8 no se pueden simular con d y se
tratan aparte) y alternativas preregistrables. Bootstrap = réplica exacta de `metrics.boot_mean` (bloques 12, 5.000
réplicas, semilla 20261015). 2.000 réplicas por celda, semillas fijas.

    PYTHONPATH=. python tests/validation/potencia_holdout_reducida.py research/validation/potencia_holdout/reducida.json
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np

from tests.validation import potencia_holdout_comun as K

SEED = 20261025
R = 2000
DELTAS = (0.0, 0.03, 0.05, 0.07, 0.10, 0.15)
SPLIT = 120                         # 2005-01 → 2014-12 | 2015-01 → (subperiodos de A6)


@dataclass(frozen=True)
class Esc:
    nombre: str = "base"
    n: int = 202
    k_rec: int = 3
    phi: float = 0.3
    sd: float = 0.22                # desviación marginal de d del pool (0,6 × la de M2 en desarrollo, 0,365)
    ratio_giro: float = 2.0         # desviación en meses de giro de G / resto
    tau: float = 0.5                # efecto de episodio, en unidades de la desviación de giro
    forma: str = "mixto"
    df: float = 4.0


BASE = Esc()
ESCENARIOS = [
    BASE,
    replace(BASE, nombre="k2", k_rec=2), replace(BASE, nombre="k4", k_rec=4),
    replace(BASE, nombre="phi0.6", phi=0.6), replace(BASE, nombre="phi0.85", phi=0.85),
    replace(BASE, nombre="sd0.18", sd=0.18), replace(BASE, nombre="sd0.29", sd=0.29),
    replace(BASE, nombre="sd0.365_ruido_M2", sd=0.365),
    replace(BASE, nombre="tau0", tau=0.0), replace(BASE, nombre="tau1", tau=1.0),
    replace(BASE, nombre="uniforme", forma="uniforme"), replace(BASE, nombre="solo_giros", forma="giros"),
    replace(BASE, nombre="n250", n=250),
    replace(BASE, nombre="colas_x3_df3", ratio_giro=3.0, df=3.0),
    replace(BASE, nombre="adverso", k_rec=2, phi=0.6, sd=0.29, tau=1.0),
]


def calendario(rng, e: Esc):
    """Marca de giro de 4 cuadrantes y marca de giro de G (con identificador de episodio) para una réplica."""
    n = e.n
    giro = np.zeros(n, bool)
    gep = np.full(n, -1)
    spells = [(rng.integers(-6, n), rng.integers(8, 21)) for _ in range(e.k_rec)]
    spells += [(rng.integers(0, n), rng.integers(4, 9)) for _ in range(rng.poisson(1.0))]
    ep = 0
    for s, L in spells:
        for c in (s, s + L):                     # entrada A→B y salida B→A
            w = np.arange(c, c + 5)
            w = w[(w >= 0) & (w < n)]
            if len(w):
                giro[w] = True
                gep[w] = np.where(gep[w] < 0, ep, gep[w])
                ep += 1
    for c in rng.integers(0, n, size=rng.poisson(2.0)):
        giro[c:c + 5] = True
    return giro, gep, ep


def ruido(rng, e: Esc, gep: np.ndarray, n_ep: int) -> np.ndarray:
    n = e.n
    z = rng.standard_t(e.df, size=n + 60) / np.sqrt(e.df / (e.df - 2))
    x = np.empty(n + 60)
    x[0] = z[0]
    for t in range(1, n + 60):
        x[t] = e.phi * x[t - 1] + np.sqrt(1 - e.phi ** 2) * z[t]
    x = x[60:]
    gm = gep >= 0
    s = np.where(gm, e.ratio_giro, 1.0)
    u = rng.normal(0, e.tau * e.ratio_giro, size=max(n_ep, 1))
    return s * x + np.where(gm, u[np.maximum(gep, 0)], 0.0)


def escala(e: Esc) -> float:
    """Factor que lleva la desviación marginal (media sobre 4.000 réplicas piloto, semilla fija) a `e.sd`."""
    rng = np.random.default_rng([SEED, 999])
    v = []
    for _ in range(4000):
        _, gep, n_ep = calendario(rng, e)
        v.append(ruido(rng, e, gep, n_ep))
    return e.sd / float(np.concatenate(v).std())


def media(delta: float, e: Esc, gep: np.ndarray) -> np.ndarray:
    n = e.n
    gm = gep >= 0
    ng = int(gm.sum())
    if e.forma == "uniforme" or ng == 0 or ng == n:
        return np.full(n, delta)
    if e.forma == "giros":
        return np.where(gm, delta * n / ng, 0.0)
    return np.where(gm, 0.5 * delta * n / ng, 0.5 * delta * n / (n - ng))


def simula(e: Esc, delta: float, di: int, ei: int, f: float):
    rng = np.random.default_rng([SEED, ei, di])
    X = np.empty((R, e.n))
    G = np.empty((R, e.n), bool)
    for r in range(R):
        giro, gep, n_ep = calendario(rng, e)
        X[r] = media(delta, e, gep) + f * ruido(rng, e, gep, n_ep)
        G[r] = giro
    return X, G


def evalua(X, G, delta, C12, C24) -> dict:
    b = K.boot_stats(X, C12)
    b24 = K.boot_stats(X, C24)
    s = K.secondary(X, G, SPLIT)
    c1 = (b["mean"] >= 0.05) & (b["lo"] > 0)
    c1u = (b["mean"] >= 0.05) & (b["lo_uni"] > 0)
    c7 = b["p_h0"] < 0.05
    sec = s["c2"] & s["c3"] & s["c4"] & s["c6"]
    p_nw, p_ewc = K.dm_nw(X), K.ewc(X)
    out = {
        "v4_tal_cual": c1 & sec & c7,
        "v4_solo_criterio1": c1,
        "v4_c1_unilateral": c1u & sec & c7,
        "unilateral_bb12": b["lo_uni"] > 0,
        "unilateral_bb12_no_dano": (b["lo_uni"] > 0) & s["c4"],
        "unilateral_bb24": b24["lo_uni"] > 0,
        "dm_newey_west_hln": p_nw < 0.05,
        "ewc_llsw": p_ewc < 0.05,
        "estimacion_ic95_lo_mayor_0": b["lo"] > 0,
    }
    res = {k: float(v.mean()) for k, v in out.items()}
    res["marginales"] = {"c1": float(c1.mean()), "c2": float(s["c2"].mean()), "c3": float(s["c3"].mean()),
                         "c4": float(s["c4"].mean()), "c6": float(s["c6"].mean()), "c7": float(c7.mean())}
    res["ic95_cobertura_delta"] = float(((b["lo"] <= delta) & (delta <= b["hi"])).mean())
    res["ic95_semiamplitud_mediana"] = float(np.median((b["hi"] - b["lo"]) / 2))
    res["sd_media_entre_replicas"] = float(X.mean(axis=1).std())
    res["sd_mensual_media"] = float(X.std(axis=1, ddof=1).mean())
    res["frac_giro_media"] = float(G.mean())
    return res


def main(dest: str) -> None:
    t0 = time.time()
    out = {"semilla": SEED, "replicas_por_celda": R, "deltas": DELTAS, "split_subperiodos": SPLIT,
           "comprobacion_boot_vs_metrics": {"n202_b12": K.check_boot_replica(202, 12),
                                            "n250_b12": K.check_boot_replica(250, 12)},
           "escenarios": {}}
    counts = {}
    for ei, e in enumerate(ESCENARIOS):
        if e.n not in counts:
            counts[e.n] = (K.boot_counts(e.n, 12), K.boot_counts(e.n, 24))
        C12, C24 = counts[e.n]
        f = escala(e)
        cel = {}
        for di, d in enumerate(DELTAS):
            X, G = simula(e, d, di, ei, f)
            cel[f"{d:.2f}"] = evalua(X, G, d, C12, C24)
        out["escenarios"][e.nombre] = {"parametros": asdict(e), "factor_escala": f, "celdas": cel}
        print(e.nombre, f"{time.time() - t0:.0f}s", {k: round(v["v4_tal_cual"], 3) for k, v in cel.items()},
              flush=True)
    out["segundos"] = round(time.time() - t0, 1)
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_text(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
