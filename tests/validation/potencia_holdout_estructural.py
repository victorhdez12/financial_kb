"""Potencia de P-EVAL-BASE v4 — capa 2, estructural con el pool de `pool_spec.md` §3 (solo sintético).

Para cada réplica:
1. G latente mensual (régimen de Markov expansión/G bajo + AR(1)), objetivo blando t = Φ(G/0,4) (s_G de la ficha) y
   etiqueta dura de G = 1{t ≥ 0,5}. 312 meses de historia fuera de muestra (≈ 1978-10 → 2004-12) + n meses de
   bloqueado.
2. Componentes (P(G alto)):
   - M0: persistencia calibrada, Λ(a + b·logit(t_{s−5})), (a, b) por logit ponderado en la historia;
   - M2: Ĝ = q·G_s + (1 − q)·G_{s−5} + e_s (e AR(1), ρ 0,5, desviación 0,45), P = Φ(Ĝ/√(σ̂² + 0,4²)), σ̂² = varianza
     del error en la historia (calibrada, como V_conj). q = 0: M2 no sabe nada que no sepa M0 (hipótesis nula honesta);
   - M3: Ĝ₃ = ½·Ĝ + ½·G_{s−5} + η (η desviación 0,3), misma conversión.
3. Pool exactamente como `pool_spec.md` §3 (BLP de Ranjan-Gneiting estimado de una vez, previa de Dirichlet moda
   (½, ¼, ¼) κ = 20, ln a, ln b ~ N(0; 0,5²), L-BFGS-B, arranque en la moda, embargo 6, ventana expansiva, recorte
   1e-6) con UNA simplificación declarada: se reestima cada 12 meses en el bloqueado (la spec dice cada mes; con
   > 300 meses de muestra expansiva los pesos apenas se mueven en un año) y los pesos de madurez valen 1.
4. d del pool y d de M2 frente a M0 con la log-loss binaria del arnés (recorte 1e-4), marca de giro de 4 cuadrantes
   (giros de G + Poisson(2) cambios del eje I, 5 meses por cambio) y los mismos diseños que la capa 1.

    PYTHONPATH=. python tests/validation/potencia_holdout_estructural.py research/validation/potencia_holdout/estructural.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy import optimize, special, stats

from src.models import metrics as M
from tests.validation import potencia_holdout_comun as K
from tests.validation.potencia_holdout_reducida import SPLIT

SEED = 20261026
R = 2000
N_DEV, N_HOLD = 312, 202
QS = (0.0, 0.15, 0.3, 0.45, 0.6, 0.8, 1.0)
if os.environ.get("QS"):                    # rejilla alternativa, p. ej. la calibrada para Δ ≈ 0 / 0,03 / 0,05 / 0,07 / 0,10
    QS = tuple(float(x) for x in os.environ["QS"].split(","))
S_G = 0.40
KAPPA, MODE, SD_AB = 20.0, np.array([0.5, 0.25, 0.25]), 0.5
EMBARGO, N_MIN, REFIT = 6, 60, 12


def latente(rng, n):
    s = np.zeros(n, int)
    for t in range(1, n):
        s[t] = (rng.random() < 1 / 70) if s[t - 1] == 0 else (rng.random() >= 1 / 12)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = 0.85 * x[t - 1] + 0.2 * rng.standard_normal()
    return np.where(s == 1, -1.0, 0.5) + x


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def fit_m0(z, t):
    """Logit ponderado de t (blando) sobre z = logit(t_{s−5}), L2 = 1 sobre b (M0 del arnés)."""
    def nll(b):
        p = special.expit(b[0] + b[1] * z)
        p = np.clip(p, 1e-9, 1 - 1e-9)
        return -(t * np.log(p) + (1 - t) * np.log(1 - p)).sum() + 0.5 * b[1] ** 2
    return optimize.minimize(nll, np.array([0.0, 1.0]), method="L-BFGS-B").x


def blp(p, w, a, b):
    return np.clip(special.betainc(a, b, np.clip(p @ w, 1e-6, 1 - 1e-6)), 1e-6, 1 - 1e-6)


def fit_pool(Pk, t):
    """MAP de `pool_spec.md` §3: max Σ[t ln P + (1−t) ln(1−P)] + κ Σ m_k ln w_k − ((ln a)² + (ln b)²)/(2·0,5²)."""
    def f(th):
        w = special.softmax(np.r_[0.0, th[:2]])
        a, b = np.exp(th[2]), np.exp(th[3])
        P = blp(Pk, w, a, b)
        ll = (t * np.log(P) + (1 - t) * np.log(1 - P)).sum()
        return -(ll + KAPPA * (MODE * np.log(w)).sum() - (th[2] ** 2 + th[3] ** 2) / (2 * SD_AB ** 2))
    x0 = np.r_[np.log(MODE[1:] / MODE[0]), 0.0, 0.0]
    r = optimize.minimize(f, x0, method="L-BFGS-B", options={"maxiter": 500, "gtol": 1e-8})
    return special.softmax(np.r_[0.0, r.x[:2]]), np.exp(r.x[2]), np.exp(r.x[3])


def replica(args):
    q, seed, n_hold = args
    rng = np.random.default_rng(seed)
    n = N_DEV + n_hold + 5
    G = latente(rng, n + 60)[60:]
    t = stats.norm.cdf(G / S_G)
    lag = np.r_[np.full(5, np.nan), G[:-5]]
    tl = np.r_[np.full(5, np.nan), t[:-5]]
    e = np.zeros(n)
    for i in range(1, n):
        e[i] = 0.5 * e[i - 1] + np.sqrt(1 - 0.25) * 0.45 * rng.standard_normal()
    g2 = q * G + (1 - q) * lag + e
    g3 = 0.5 * g2 + 0.5 * lag + 0.3 * rng.standard_normal(n)
    sl = slice(5, None)                                  # meses con t_{s−5}
    G, t, tl, g2, g3 = G[sl], t[sl], tl[sl], g2[sl], g3[sl]
    dev = slice(0, N_DEV)
    s2 = np.sqrt(np.mean((g2[dev] - G[dev]) ** 2) + S_G ** 2)
    s3 = np.sqrt(np.mean((g3[dev] - G[dev]) ** 2) + S_G ** 2)
    b0 = fit_m0(logit(tl[dev]), t[dev])
    p0 = special.expit(b0[0] + b0[1] * logit(tl))
    Pk = np.column_stack([p0, stats.norm.cdf(g2 / s2), stats.norm.cdf(g3 / s3)])
    Pk = np.clip(Pk, 1e-6, 1 - 1e-6)
    pool = np.empty(n_hold)
    ws = []
    for j in range(0, n_hold, REFIT):
        m0 = N_DEV + j
        est = slice(0, m0 - EMBARGO + 1)
        w, a, b = fit_pool(Pk[est], t[est]) if m0 - EMBARGO + 1 >= N_MIN else (np.array([1.0, 0, 0]), 1.0, 1.0)
        ws.append([*w, a, b])
        hs = slice(m0, min(m0 + REFIT, N_DEV + n_hold))
        pool[j:j + (hs.stop - hs.start)] = blp(Pk[hs], w, a, b)
    h = slice(N_DEV, N_DEV + n_hold)
    th = t[h]
    ll0, ll2 = M.binary_logloss(Pk[h, 0], th), M.binary_logloss(Pk[h, 1], th)
    llp = M.binary_logloss(pool, th)
    hard = (th >= 0.5).astype(int)
    prev = np.r_[(t[N_DEV - 5:N_DEV] >= 0.5).astype(int), hard[:-5]]
    giro = hard != prev
    for c in rng.integers(0, n_hold, size=rng.poisson(2.0)):
        giro[c:c + 5] = True
    return ll0 - llp, ll0 - ll2, giro, np.array(ws[-1])


def evalua(X, G, C12, C24):
    b = K.boot_stats(X, C12)
    b24 = K.boot_stats(X, C24)
    s = K.secondary(X, G, SPLIT)
    c1 = (b["mean"] >= 0.05) & (b["lo"] > 0)
    c1u = (b["mean"] >= 0.05) & (b["lo_uni"] > 0)
    c7 = b["p_h0"] < 0.05
    sec = s["c2"] & s["c3"] & s["c4"] & s["c6"]
    out = {"v4_tal_cual": c1 & sec & c7, "v4_solo_criterio1": c1, "v4_c1_unilateral": c1u & sec & c7,
           "unilateral_bb12": b["lo_uni"] > 0, "unilateral_bb12_no_dano": (b["lo_uni"] > 0) & s["c4"],
           "unilateral_bb24": b24["lo_uni"] > 0, "dm_newey_west_hln": K.dm_nw(X) < 0.05,
           "ewc_llsw": K.ewc(X) < 0.05, "estimacion_ic95_lo_mayor_0": b["lo"] > 0,
           "recomendado_sin_suelo": (b["lo"] > 0) & sec & c7,
           "v43_final": (b["lo"] > 0) & sec & c7}            # P-EVAL-BASE v4.3: criterios 1-4, 6 y 7 (el 8 no decide)
    res = {k: float(v.mean()) for k, v in out.items()}
    res["marginales"] = {"c1": float(c1.mean()), "c3": float(s["c3"].mean()), "c4": float(s["c4"].mean()),
                         "c6": float(s["c6"].mean()), "c7": float(c7.mean())}
    xb = X.mean(axis=1)
    res["delta_verdadero_aprox"] = float(xb.mean())           # media sobre 2.000 réplicas (EE ≈ sd/√2000)
    res["sd_media_entre_replicas"] = float(xb.std())
    res["sd_mensual_media"] = float(X.std(axis=1, ddof=1).mean())
    acf = np.array([K._autocov(X, 6)[:, k] / K._autocov(X, 6)[:, 0] for k in range(1, 7)]).mean(axis=1)
    res["acf_1_6_media"] = [float(a) for a in acf]
    res["ic95_cobertura_delta"] = float(((b["lo"] <= xb.mean()) & (xb.mean() <= b["hi"])).mean())
    return res


def main(dest: str) -> None:
    t0 = time.time()
    C12, C24 = K.boot_counts(N_HOLD, 12), K.boot_counts(N_HOLD, 24)
    out = {"semilla": SEED, "replicas_por_celda": R, "qs": QS, "n_dev": N_DEV, "n_bloqueado": N_HOLD,
           "simplificaciones": ["pool reestimado cada 12 meses en el bloqueado (spec: cada mes)",
                                "pesos de madurez = 1 y objetivo de entrenamiento = etiqueta final",
                                "M0 calibrado una vez con la historia (el arnés lo reajusta cada mes)",
                                "eje I idéntico en todos: d de 4 cuadrantes = d binaria del eje G"],
           "celdas": {}}
    with Pool(int(os.environ.get("NPROC", os.cpu_count() or 1))) as pool:
        for qi, q in enumerate(QS):
            seeds = [(q, int(s), N_HOLD) for s in np.random.SeedSequence([SEED, qi]).generate_state(R)]
            res = pool.map(replica, seeds, chunksize=20)
            Dp = np.array([r[0] for r in res])
            D2 = np.array([r[1] for r in res])
            Gm = np.array([r[2] for r in res])
            W = np.array([r[3] for r in res])
            corr = float(np.mean([np.corrcoef(Dp[i], D2[i])[0, 1] for i in range(R)]))
            out["celdas"][f"{q:.2f}"] = {
                "pool": evalua(Dp, Gm, C12, C24), "m2_solo": evalua(D2, Gm, C12, C24),
                "corr_d_pool_d_m2": corr, "frac_giro_media": float(Gm.mean()),
                "pesos_finales_medios": {"w_m0": float(W[:, 0].mean()), "w_m2": float(W[:, 1].mean()),
                                         "w_m3": float(W[:, 2].mean()), "a": float(W[:, 3].mean()),
                                         "b": float(W[:, 4].mean())}}
            c = out["celdas"][f"{q:.2f}"]
            print(q, f"{time.time() - t0:.0f}s", "Δpool", round(c["pool"]["delta_verdadero_aprox"], 4),
                  "ΔM2", round(c["m2_solo"]["delta_verdadero_aprox"], 4), "v4 pool", c["pool"]["v4_tal_cual"],
                  "v4 M2", c["m2_solo"]["v4_tal_cual"], flush=True)
    out["segundos"] = round(time.time() - t0, 1)
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_text(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1])
