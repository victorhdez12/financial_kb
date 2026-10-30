"""INT-11 v3: piezas SINTÉTICAS (docs/int/INT11_v3_diseno.md). Ningún dato real entra aquí.

1. `cobertura_iid` / `derivar_c`: el experimento que fija la constante de ensanchamiento `c_suavizado` (en v2 se fijó
   en un sintético que no quedó en el repo; validación v2, hallazgo 5). Reproduce el MECANISMO del motor en una celda
   de n filas iid: bootstrap bayesiano por lotes (pesos Dirichlet(1) por fila = por año) + ruido t5 de varianza unidad
   × dt de la celda (ddof = 1) × √(c / n). Se mide la cobertura del p5-p95 de la predictiva para una observación nueva.
   REGLA (fijada antes de correrlo): c* = el menor c de la rejilla con cobertura ≥ 0,90 en n = 20 Y en n = 34 (tamaños
   de las celdas raras; recuentos de v1, contaminación de estructura ya declarada), ν = 4,5 (colas de la rentabilidad
   anual del panel, prerregistro v1). Números aleatorios comunes entre valores de c (la curva es monótona).
2. Proceso sintético v3 (`panel_v3`): el nulo heterogéneo congelado de v2 + inflación y brecha CONTINUAS + error de
   medida de la inflación y de la brecha observadas (el régimen que ve el motor es el observado; la rentabilidad depende
   del verdadero) + no estacionariedad opcional (choques × f desde un año dado; hipotético).
3. Evaluación con pertenencia SUAVE (`evaluar_suave`): por país del pliegue se simulan los 4 estados de partida y la
   predictiva de cada fila es la mezcla ponderada por `E.pesos_estado` (equivalente en distribución a `simular_suave`).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.intl import escenarios as E

NU_C = 4.5
N_C = (20, 34)
REJILLA_C = tuple(np.round(np.arange(0.0, 12.01, 0.25), 2))


# ============================================================================ 1. experimento de c
def cobertura_iid(n: int, cs, nu: float = NU_C, R: int = 20000, semilla: int = 0, n_lotes: int = 20,
                  por_lote: int = 200, lote_rep: int = 500, nivel=(0.05, 0.95)) -> np.ndarray:
    """Cobertura del intervalo p5-p95 de la predictiva del motor (celda de n filas iid t_ν) para cada c de `cs`.
    Dentro ⇔ la fracción de sorteos < y es ≥ 0,05 y la de sorteos ≤ y es ≤ 0,95 (equivale al cuantil empírico salvo
    O(1/sorteos)). ν = inf → normal."""
    rng = np.random.default_rng(semilla)
    cs = np.asarray(cs, float)
    dentro = np.zeros(len(cs))
    S = n_lotes * por_lote
    hechos = 0
    while hechos < R:
        B = min(lote_rep, R - hechos)
        x = rng.standard_normal((B, n + 1)) if not np.isfinite(nu) else rng.standard_t(nu, (B, n + 1))
        s, y = x[:, :n], x[:, n]
        sd = s.std(axis=1, ddof=1)
        v = np.empty((B, S))
        for b in range(n_lotes):
            w = rng.standard_gamma(1.0, (B, n))
            cw = np.cumsum(w, 1)
            u = rng.random((B, por_lote)) * cw[:, -1:]
            idx = (u[:, :, None] > cw[:, None, :]).sum(-1).clip(0, n - 1)
            v[:, b * por_lote:(b + 1) * por_lote] = np.take_along_axis(s, idx, 1)
        ruido = rng.standard_t(5, (B, S)) * np.sqrt(3 / 5)
        for k, c in enumerate(cs):
            z = v + ruido * (sd * np.sqrt(c / n))[:, None]
            bajo = (z < y[:, None]).mean(1)
            hasta = (z <= y[:, None]).mean(1)
            dentro[k] += np.sum((bajo >= nivel[0]) & (hasta <= nivel[1]))
        hechos += B
    return dentro / R


def derivar_c(R: int = 20000, semilla: int = 20261102, rejilla=REJILLA_C, ns=N_C, nu: float = NU_C) -> dict:
    """Regla de §1 del docstring. Devuelve la curva por n y el c* (None si ninguno de la rejilla llega)."""
    curvas = {n: cobertura_iid(n, rejilla, nu, R, semilla + n) for n in ns}
    ok = np.all([curvas[n] >= 0.90 for n in ns], axis=0)
    c = float(np.asarray(rejilla)[np.argmax(ok)]) if ok.any() else None
    return {"c": c, "nu": nu, "R": R, "rejilla": list(map(float, rejilla)),
            "curvas": {str(n): np.round(curvas[n], 4).tolist() for n in ns}}


# ============================================================================ 2. proceso sintético v3
def brecha_desde_latente(zg: np.ndarray, q_baja: float, sd_brecha: float) -> np.ndarray:
    """Brecha continua lineal en el latente (varianza 1): < 0 ⇔ zg < Φ⁻¹(q_baja) (coherente con el régimen), dt =
    sd_brecha; la media resultante es −sd_brecha·Φ⁻¹(q_baja)."""
    return sd_brecha * (zg - stats.norm.ppf(q_baja))


def escalar_epoca(Y: np.ndarray, reg: np.ndarray, efectos: np.ndarray, mu: np.ndarray, desde: int | None,
                  factor) -> np.ndarray:
    """No estacionariedad hipotética: desde el índice de año `desde`, los choques (común + propio) se multiplican por
    `factor` (escalar o (A,)). Se conserva la media y el efecto del régimen."""
    if desde is None:
        return Y
    N, T, A = Y.shape
    prev = np.concatenate([np.full((N, 1), 0), reg[:, :-1]], axis=1)
    centro = mu + efectos.T[prev]
    f = np.ones((T, A))
    f[desde:] = np.broadcast_to(np.asarray(factor, float), (A,))
    return centro + (Y - centro) * f[None]


def observar_regimen(infl_obs: np.ndarray, brecha_obs: np.ndarray) -> np.ndarray:
    return E.codigo_regimen(np.log1p(infl_obs), brecha_obs).reshape(infl_obs.shape)


def filas_v3(reg_obs, Y, infl_true, infl_obs, brecha_obs, paises, años, existe=None, ok=None) -> pd.DataFrame:
    """Filas del motor con el régimen OBSERVADO y columnas del estado previo observado (infl_prev, brecha_prev) para la
    pertenencia suave; la inflación del año (resultado del Brier) es la verdadera."""
    from src.intl import int11 as Q
    f = Q.filas_sinteticas(reg_obs, Y, paises, años, existe, ok, infl_true)
    ci = {c: i for i, c in enumerate(paises)}
    ii = f["pais"].map(ci).to_numpy()
    tt = (f["año"] - años[0]).to_numpy()
    f["infl_prev"] = np.log1p(infl_obs[ii, tt - 1])
    f["brecha_prev"] = brecha_obs[ii, tt - 1]
    return f


# ============================================================================ 3. evaluación con pertenencia suave
def _cuantiles_mezcla(muestras: list[np.ndarray], w: np.ndarray, qs) -> np.ndarray:
    x = np.concatenate(muestras)
    p = np.concatenate([np.full(len(m), wi / max(len(m), 1)) for m, wi in zip(muestras, w)])
    o = np.argsort(x, kind="stable")
    cw = np.cumsum(p[o])
    cw /= cw[-1]
    return np.array([x[o][min(np.searchsorted(cw, q), len(x) - 1)] for q in qs])


def evaluar_suave(filas: pd.DataFrame, diseño: str, cfg: E.Config, n_lotes: int, por_lote: int, semilla: int,
                  corte: int = 1950, sigmas: tuple | None = None, k_anchura: tuple = (), n_min: int = 30) -> dict:
    """Como `int11.evaluar_motor` (H = 1) pero con la predictiva de cada fila = mezcla de los 4 estados de partida con
    pesos `E.pesos_estado(infl_prev, brecha_prev, σπ, σb)` (σ = 0 → régimen duro = s_prev). Devuelve por fila de prueba:
    dentro90 (m, A), dentro_k (m, A, K), p_infl_m1/m0, p_caida_m1/m0, y, infl, año, pais, s_prev, infl_prev, crps0/1."""
    filas = E.recalcular_sucesor(filas)
    acts = list(E.ACTIVOS)
    V = filas[acts].to_numpy(float)
    infl = np.expm1(filas["inflacion"].to_numpy(float))
    paises = sorted(filas["pais"].unique())
    sp, sb = sigmas if sigmas is not None else (cfg.sigma_infl, cfg.sigma_brecha)
    pais = filas["pais"].to_numpy()
    if diseño == "loco":
        pliegues = [(k, pais != c, pais == c) for k, c in enumerate(paises)]
    elif diseño == "temporal":
        a = filas["año"].to_numpy()
        pliegues = [(0, a < corte, a >= corte)]
    else:
        raise ValueError(diseño)
    m, A = len(filas), len(acts)
    out = {k: np.full((m, A), np.nan) for k in ("dentro90", "crps0", "crps1")}
    out.update({k: np.full(m, np.nan) for k in ("p_infl_m1", "p_infl_m0", "p_caida_m1", "p_caida_m0")})
    dk = np.full((m, A, len(k_anchura)), np.nan)
    prueba = np.zeros(m, bool)
    for k, tr, te in pliegues:
        gen = E.Generador(cfg).ajustar(E.recalcular_sucesor(filas[tr]))
        Vtr = V[tr]
        p0 = [Vtr[np.isfinite(Vtr[:, j]), j] for j in range(A)]
        it = infl[tr]
        infl_m0 = float(np.mean(it[np.isfinite(it)] > 0.05))
        caida_m0 = float(np.mean(Vtr[np.isfinite(Vtr[:, 0]), 0] <= -0.20))
        te_idx = np.flatnonzero(te)
        prueba[te_idx] = True
        for c in np.unique(pais[te_idx]):
            idx = te_idx[pais[te_idx] == c]
            sims = []
            for s0 in range(E.K):
                esc = gen.simular(c, s0, horizonte=1, n_lotes=n_lotes, por_lote=por_lote,
                                  semilla=semilla + 1000 * k + 10 * paises.index(c) + s0)
                R1 = esc.rent[:, 0, :]
                sims.append(([R1[np.isfinite(R1[:, j]), j] for j in range(A)],
                             float(np.mean(np.expm1(esc.inflacion[:, 0]) > 0.05)),
                             float(np.mean(R1[np.isfinite(R1[:, 0]), 0] <= -0.20))))
            for i in idx:
                if sp > 0 or sb > 0:
                    w = E.pesos_estado(filas["infl_prev"].iat[i], filas["brecha_prev"].iat[i], sp, sb)
                else:
                    w = np.eye(E.K)[int(filas["s_prev"].iat[i])]
                out["p_infl_m1"][i] = float(np.dot(w, [s[1] for s in sims]))
                out["p_caida_m1"][i] = float(np.dot(w, [s[2] for s in sims]))
                out["p_infl_m0"][i], out["p_caida_m0"][i] = infl_m0, caida_m0
                usa = np.flatnonzero(w > 1e-12)
                for j in range(A):
                    y = V[i, j]
                    if not np.isfinite(y) or len(p0[j]) < n_min:
                        continue
                    ms = [sims[s][0][j] for s in usa]
                    if min(len(x) for x in ms) < n_min:
                        continue
                    q = _cuantiles_mezcla(ms, w[usa], (0.05, 0.5, 0.95))
                    out["dentro90"][i, j] = q[0] <= y <= q[2]
                    out["crps0"][i, j] = E.crps_muestra(p0[j], y)[0]
                    # CRPS de la mezcla: con pesos, aproximado por remuestreo proporcional (4.000 sorteos)
                    x = np.concatenate([np.random.default_rng(i).choice(mm, max(int(round(4000 * ww)), 1))
                                        for mm, ww in zip(ms, w[usa])])
                    out["crps1"][i, j] = E.crps_muestra(x, y)[0]
                    for kk, fk in enumerate(k_anchura):
                        dk[i, j, kk] = (y >= q[1] - fk * (q[1] - q[0])) & (y <= q[1] + fk * (q[2] - q[1]))
    sel = prueba
    res = {k: v[sel] for k, v in out.items()}
    res.update({"pais": pais[sel], "año": filas["año"].to_numpy()[sel], "s_prev": filas["s_prev"].to_numpy()[sel],
                "y": V[sel], "infl": infl[sel],
                "infl_prev": np.expm1(filas["infl_prev"].to_numpy(float))[sel] if "infl_prev" in filas else None})
    if k_anchura:
        res["dentro_k"] = dk[sel]
    return res


def estadisticos(ev: dict, sel: np.ndarray | None = None, cerca_pp: float = 0.5) -> dict:
    """S5, S_raros, cobertura cerca del umbral (|π_{t−1} − 3 %| < cerca_pp), CRPSS, Brier de inflación > 5 % (global y
    cerca), con DM por años; y cobertura de los intervalos escalados (potencia de la puerta)."""
    sel = np.ones(len(ev["año"]), bool) if sel is None else sel
    dn = ev["dentro90"][sel]
    fila = np.isfinite(dn).any(1)
    o = {"S5": float(np.mean(np.nanmean(dn[fila], 1))), "Sb": float(np.nanmean(dn[:, 0])),
         "S_activo": np.nanmean(dn, 0).tolist()}
    raro = np.isin(ev["s_prev"][sel], (2, 3))
    o["S_raros"] = float(np.nanmean(dn[raro])) if raro.any() else np.nan
    cerca = (np.abs(ev["infl_prev"][sel] - 0.03) < cerca_pp / 100) if ev.get("infl_prev") is not None else \
        np.zeros(sel.sum(), bool)
    o["S5_cerca"] = float(np.nanmean(dn[cerca])) if cerca.any() else np.nan
    o["n_cerca"] = int(cerca.sum())
    if "dentro_k" in ev:
        dkk = ev["dentro_k"][sel]
        o["S5_k"] = [float(np.mean(np.nanmean(dkk[fila, :, k], 1))) for k in range(dkk.shape[2])]
    c0, c1 = ev["crps0"][sel], ev["crps1"][sel]
    usa = np.isfinite(c0).any(1)
    o["crpss_medio"] = float(np.nanmean(1 - np.nanmean(c1[usa], 0) / np.nanmean(c0[usa], 0)))
    y = (ev["infl"][sel] > 0.05).astype(float)
    p1, p0 = ev["p_infl_m1"][sel], ev["p_infl_m0"][sel]
    b1, b0 = (p1 - y) ** 2, (p0 - y) ** 2
    dm = E.dm_conglomerado(b0 - b1, ev["año"][sel], lags=2)
    o["infl5"] = {"bss": float(1 - b1.mean() / max(b0.mean(), 1e-12)), "p": dm["p_unilateral"],
                  "brier": float(b1.mean()), "brier_cerca": float(b1[cerca].mean()) if cerca.any() else np.nan,
                  "p_media_cerca": float(p1[cerca].mean()) if cerca.any() else np.nan,
                  "frec_cerca": float(y[cerca].mean()) if cerca.any() else np.nan,
                  "eventos": int(y.sum()), "n": int(len(y))}
    return o
