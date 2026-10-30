"""Validador INT-11 v2 (30-oct; SOLO SINTÉTICO; propuesta de DISEÑO para v3, nada se cambia en v2): pertenencia SUAVE
al régimen en la emisión. En vez de s_{t−1} = 1{inflación > 3 %}, la predictiva es la mezcla
    (1 − w) · predictiva(lado ≤ 3 %) + w · predictiva(lado > 3 %),   w = Φ((π_{t−1} − 3 %) / σ),
con el mismo lado de la brecha. El motor (Config.v2) se estima igual (régimen duro en el entrenamiento).

Proceso: el nulo heterogéneo congelado de P-INT11 v2 (`panel_v2`, factores medidos, inflación continua lineal en el
latente), estructura de huecos del panel real (solo disponibilidad). Variante "ruido": la inflación OBSERVADA de la
emisión lleva un error N(0, 0,25 pp) (definición/revisión del IPC); el régimen del motor se calcula con la observada.
LOCO, 20 lotes × 100. Métricas: S5, S_raros, cobertura de las filas cerca del umbral (|π − 3 %| < 0,5 pp), Brier y
fiabilidad de P(inflación > 5 %) (global y cerca del umbral).
Uso: .venv/bin/python -m scripts.val_int11v2_suave [R]
"""
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
from scipy import stats

warnings.filterwarnings("ignore")
from scripts.int11_corrida import NUCLEO, cargar_real, estructura          # noqa: E402
from scripts.int11_v2_potencia import panel_v2                              # noqa: E402
from src.intl import data as D                                              # noqa: E402
from src.intl import escenarios as E                                        # noqa: E402
from src.intl import int11 as Q                                             # noqa: E402
from src.intl.procedencia import procedencia                                # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "research/int/val_int11v2"
SIGMAS = (0.0, 0.0025, 0.005)          # 0 = duro (v2); 0,25 pp; 0,5 pp
CERCA = 0.005


def cuantiles_mezcla(xa, xb, w, qs=(0.05, 0.95)):
    """Cuantiles de (1 − w)·F_a + w·F_b con muestras xa, xb."""
    x = np.concatenate([xa, xb])
    p = np.concatenate([np.full(len(xa), (1 - w) / len(xa)), np.full(len(xb), w / len(xb))])
    o = np.argsort(x)
    cw = np.cumsum(p[o])
    return [x[o][min(np.searchsorted(cw, q), len(x) - 1)] for q in qs]


def una_replica(fs, infl_prev_obs, semilla):
    f = fs.reset_index(drop=True)
    V = f[list(E.ACTIVOS)].to_numpy(float)
    infl_t = np.expm1(f["inflacion"].to_numpy(float))
    paises = sorted(f.pais.unique())
    m = len(f)
    res = {s: {"d90": np.full((m, 5), np.nan), "p5": np.full(m, np.nan)} for s in SIGMAS}
    for k, c in enumerate(paises):
        tr, te = f.pais.values != c, f.pais.values == c
        gen = E.Generador(E.Config.v2()).ajustar(f[tr])
        sims = {}
        for s0 in range(4):
            esc = gen.simular(c, s0, horizonte=1, n_lotes=20, por_lote=100, semilla=semilla + 100 * k + s0)
            sims[s0] = (esc.rent[:, 0, :], float(np.mean(np.expm1(esc.inflacion[:, 0]) > 0.05)))
        for i in np.flatnonzero(te):
            sp = int(f.s_prev.values[i])
            baja = sp in (2, 3)
            a, b = (3, 2) if baja else (0, 1)                     # lado ≤ 3 % y lado > 3 % con la misma brecha
            for sg in SIGMAS:
                if sg == 0:
                    w = float(sp in (1, 2))
                else:
                    w = float(stats.norm.cdf((infl_prev_obs[i] - 0.03) / sg))
                res[sg]["p5"][i] = (1 - w) * sims[a][1] + w * sims[b][1]
                for j in range(5):
                    y = V[i, j]
                    if not np.isfinite(y):
                        continue
                    xa, xb = sims[a][0][:, j], sims[b][0][:, j]
                    xa, xb = xa[np.isfinite(xa)], xb[np.isfinite(xb)]
                    if w <= 0 or w >= 1:
                        x = xb if w >= 1 else xa
                        q = np.quantile(x, [.05, .95])
                    else:
                        q = cuantiles_mezcla(xa, xb, w)
                    res[sg]["d90"][i, j] = q[0] <= y <= q[1]
    cerca = np.abs(infl_prev_obs - 0.03) < CERCA
    raro = np.isin(f.s_prev.values, (2, 3))
    ev = (infl_t > 0.05).astype(float)
    out = {}
    for sg, r in res.items():
        d = r["d90"]
        fila = np.isfinite(d).any(1)
        out[sg] = {"S5": float(np.mean(np.nanmean(d[fila], 1))), "S_raros": float(np.nanmean(d[raro])),
                   "S5_cerca": float(np.nanmean(d[cerca])), "brier": float(np.mean((r["p5"] - ev) ** 2)),
                   "brier_cerca": float(np.mean((r["p5"][cerca] - ev[cerca]) ** 2)),
                   "p_media_cerca": float(np.mean(r["p5"][cerca])), "freq_cerca": float(np.mean(ev[cerca])),
                   "n_cerca": int(cerca.sum())}
    return out


def main(R):
    med = json.loads((REPO / "research/int/int11_potencia.json").read_text())["medicion"]
    med2 = json.loads((REPO / "research/int/int11_v2_potencia.json").read_text())["medicion_v2"]
    años, existe, ok = estructura(cargar_real(D.connect()))          # solo la estructura de huecos
    fac = np.array([med2["factor_pais"][c] for c in NUCLEO])
    rng = np.random.default_rng(31337)
    acc = {v: {s: [] for s in SIGMAS} for v in ("sin_ruido", "ruido_0.25pp")}
    for r in range(R):
        reg, Y, infl = panel_v2(med, med2, len(años), rng, fac=fac, fac_raro=1.0)
        for var in acc:
            ruido = 0.0025 if var.startswith("ruido") else 0.0
            infl_obs = infl + ruido * rng.standard_normal(infl.shape)
            # el régimen OBSERVADO (el que ve el motor) usa la inflación observada; la rentabilidad depende del verdadero
            alta_obs = infl_obs > 0.03
            baja = np.isin(reg, (2, 3))
            reg_obs = np.where(baja, np.where(alta_obs, 2, 3), np.where(alta_obs, 1, 0))
            fs = Q.filas_sinteticas(reg_obs, Y, NUCLEO, años, existe, ok, infl)
            ci = {c: i for i, c in enumerate(NUCLEO)}
            ii = fs.pais.map(ci).to_numpy()
            tt = (fs["año"] - años[0]).to_numpy()
            prev = infl_obs[ii, tt - 1]
            o = una_replica(fs, prev, 20261101 + 7 * r)
            for s in SIGMAS:
                acc[var][s].append(o[s])
        print(r + 1, {v: {s: round(x[s][-1]["S5"], 4) for s in SIGMAS} for v, x in acc.items()}, flush=True)
    resumen = {}
    for var, x in acc.items():
        resumen[var] = {}
        for s, lst in x.items():
            d = {k: float(np.mean([z[k] for z in lst])) for k in lst[0]}
            d["S5_banda"] = np.percentile([z["S5"] for z in lst], [2.5, 97.5]).round(4).tolist()
            resumen[var][f"sigma={100 * s:.2f}pp"] = {k: (round(v, 4) if isinstance(v, float) else v)
                                                      for k, v in d.items()}
    return resumen


if __name__ == "__main__":
    t0 = time.time()
    R = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    OUT.mkdir(parents=True, exist_ok=True)
    o = {"procedencia": procedencia(), "R": R, "res": main(R)}
    o["segundos"] = round(time.time() - t0)
    (OUT / "suave.json").write_text(json.dumps(o, ensure_ascii=False, indent=1, default=float))
    print(json.dumps(o, ensure_ascii=False, indent=1, default=float))
