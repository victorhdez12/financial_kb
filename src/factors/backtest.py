"""Motor del backtest de desarrollo de P-DEV-FACT v0.1 (docs/factors/prerreg_desarrollo_v0.md). Funciones puras sobre
series mensuales (PeriodIndex); los datos los carga src/factors/data.py.

Cronología (§4): los objetivos se fijan al cierre de t y rigen el rendimiento de t + 1; las órdenes de oro se ejecutan un
mes más tarde (cierre de t + 1), con la renta fija absorbiendo la diferencia mientras tanto.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm

ACTIVOS = ("rv", "rf", "oro")
ESTRATEGICO = {"rv": 0.80, "rf": 0.10, "oro": 0.10}
DEFENSIVO = {"rv": 0.65, "rf": 0.25, "oro": 0.10}
COSTE = {"rv": 0.0010, "rf": 0.0010, "oro": 0.0020}          # por lado
TER = {"rv": 0.0020, "rf": 0.0015, "oro": 0.0015}            # anual
BANDA = 0.05
EPISODIOS = {"1980": ("1980-01", "1980-07"), "1981-82": ("1981-07", "1982-11"), "1990-91": ("1990-07", "1991-03"),
             "2001": ("2001-03", "2001-11")}
EPISODIOS_1963 = {"1969-70": ("1969-12", "1970-11"), "1973-75": ("1973-11", "1975-03"), **EPISODIOS}


@dataclass
class Resultado:
    neto: pd.Series           # rendimiento mensual neto de la cartera
    pesos: pd.DataFrame       # pesos al inicio de cada mes
    rotacion: pd.Series       # Σ|Δw| / 2 por mes
    costes: pd.Series         # coste de transacción por mes (fracción de la cartera)


def simular(r: pd.DataFrame, objetivo: pd.DataFrame, coste_mult: float = 1.0, retraso_oro: int = 1,
            pesos_base: dict | None = None) -> Resultado:
    """r: rendimientos mensuales por activo (columnas ACTIVOS) en el periodo puntuado. objetivo: pesos objetivo fijados al
    cierre de cada mes t (mismo índice), que rigen desde t + 1. Rebalanceo: si cambia el objetivo, si algún peso se separa
    más de BANDA del objetivo, o en diciembre. El oro se ejecuta `retraso_oro` meses después."""
    base = pesos_base or ESTRATEGICO
    idx = r.index
    w = pd.Series(base, dtype=float)[list(ACTIVOS)]
    obj_prev = w.copy()
    oro_pend: list[tuple[int, float]] = []
    neto, pesos, rot, cst = [], [], [], []
    ter_m = pd.Series(TER)[list(ACTIVOS)] / 12
    for i, t in enumerate(idx):
        pesos.append(w.copy())
        ra = r.loc[t, list(ACTIVOS)] - ter_m
        g = float((w * (1 + ra)).sum())
        w = w * (1 + ra) / g
        # órdenes de oro pendientes que vencen al cierre de t
        c_t, rot_t = 0.0, 0.0
        venc = [o for o in oro_pend if o[0] == i]
        oro_pend = [o for o in oro_pend if o[0] != i]
        for _, obj_oro in venc:
            d = obj_oro - w["oro"]
            w["oro"] += d; w["rf"] -= d
            c_t += abs(d) * COSTE["oro"] * coste_mult + abs(d) * COSTE["rf"] * coste_mult
            rot_t += abs(d)
        obj = objetivo.loc[t, list(ACTIVOS)].astype(float)
        cambia = not np.allclose(obj.values, obj_prev.values)
        fuera = (w - obj).abs().max() > BANDA
        if cambia or fuera or t.month == 12:
            d = obj - w
            d_oro = d["oro"]
            if retraso_oro and abs(d_oro) > 1e-12:
                oro_pend.append((i + retraso_oro, obj["oro"]))
                d["rf"] += d_oro; d["oro"] = 0.0          # la RF absorbe hasta que se ejecute el oro
            w = w + d
            c_t += float((d.abs() * pd.Series(COSTE)[list(ACTIVOS)]).sum()) * coste_mult
            rot_t += float(d.abs().sum())
        obj_prev = obj
        neto.append((g - 1) - c_t)
        rot.append(rot_t / 2); cst.append(c_t)
    return Resultado(pd.Series(neto, index=idx), pd.DataFrame(pesos, index=idx), pd.Series(rot, index=idx),
                     pd.Series(cst, index=idx))


def objetivo_fijo(idx, pesos=ESTRATEGICO) -> pd.DataFrame:
    return pd.DataFrame([pesos] * len(idx), index=idx)[list(ACTIVOS)]


def objetivo_estado(defensivo: pd.Series, normal=ESTRATEGICO, defens=DEFENSIVO) -> pd.DataFrame:
    return pd.DataFrame([defens if d else normal for d in defensivo], index=defensivo.index)[list(ACTIVOS)]


def objetivo_vol(rv_hist: pd.Series, idx, ventana: int = 12, normal=ESTRATEGICO, minimo: float = 0.65,
                 umbral: float = 0.025) -> pd.DataFrame:
    """B1: RV = 80 % × min(1, σ*/σ̂_t) acotada en [minimo, 80 %]; σ̂ = vol. realizada de `ventana` meses hasta t;
    σ* = mediana expansiva de σ̂ desde el inicio de `rv_hist`; cambio solo si mueve ≥ `umbral`. El resto va a RF."""
    sig = rv_hist.rolling(ventana).std() * np.sqrt(12)
    sig_star = sig.expanding().median()
    rv_obj = (normal["rv"] * np.minimum(1.0, sig_star / sig)).clip(minimo, normal["rv"])
    filas, cur = [], normal["rv"]
    for t in idx:
        x = rv_obj.get(t, np.nan)
        if not np.isnan(x) and abs(x - cur) >= umbral - 1e-12:
            cur = float(x)
        filas.append({"rv": cur, "rf": 1 - normal["oro"] - cur, "oro": normal["oro"]})
    return pd.DataFrame(filas, index=idx)[list(ACTIVOS)]


def estado(g: pd.Series, theta: float, k: int) -> pd.Series:
    """True = DEFENSIVO; cambia tras k meses seguidos al otro lado de θ (idéntico a scripts/factors_variantes.py)."""
    out, cur, rb, ra = [], False, 0, 0
    for v in g:
        if np.isnan(v):
            out.append(cur); continue
        rb, ra = (rb + 1, 0) if v < theta else (0, ra + 1)
        if not cur and rb >= k:
            cur = True
        elif cur and ra >= k:
            cur = False
        out.append(cur)
    return pd.Series(out, index=g.index)


def desuavizar(r: pd.Series, rho: float) -> pd.Series:
    """Corrección del efecto Working (§5.6): r*_t = (r_t − ρ r_{t−1}) / (1 − ρ)."""
    return ((r - rho * r.shift(1)) / (1 - rho)).fillna(r)


# ---------------------------------------------------------------- métricas
def caida_max(r: pd.Series) -> float:
    w = (1 + r).cumprod()
    return float((w / w.cummax() - 1).min())


def caidas_episodio(r: pd.Series, episodios=EPISODIOS) -> dict:
    out = {}
    for nom, (pico, valle) in episodios.items():
        a, b = pd.Period(pico, "M") - 6, pd.Period(valle, "M") + 12
        sub = r[(r.index >= a) & (r.index <= b)]
        if len(sub):
            out[nom] = caida_max(sub)
    return out


def metricas(res: Resultado, efectivo: pd.Series, episodios=EPISODIOS) -> dict:
    r = res.neto
    ex = r - efectivo.reindex(r.index)
    q = r.quantile(0.05)
    return {"vol_anual": float(r.std(ddof=1) * np.sqrt(12)), "caida_max": caida_max(r),
            "caidas_episodio": caidas_episodio(r, episodios), "cvar5_mensual": float(r[r <= q].mean()),
            "rent_anual": float((1 + r).prod() ** (12 / len(r)) - 1),
            "sharpe_anual": float(ex.mean() / ex.std(ddof=1) * np.sqrt(12)),
            "rotacion_anual": float(res.rotacion.sum() / (len(r) / 12)),
            "costes_anual": float(res.costes.sum() / (len(r) / 12)),
            "meses_defensivo_o_recortado": int((res.pesos["rv"] < 0.80 - 1e-9).sum())}


def bootstrap_dif_vol(a: pd.Series, b: pd.Series, bloque: int = 12, n: int = 2000, semilla: int = 20261026) -> dict:
    """IC 95 % de σ(a) − σ(b) (anualizadas) por bootstrap de bloques móviles, pareado."""
    rng = np.random.default_rng(semilla)
    x, y, T = a.to_numpy(), b.to_numpy(), len(a)
    nb = int(np.ceil(T / bloque))
    difs = np.empty(n)
    for j in range(n):
        st = rng.integers(0, T - bloque + 1, nb)
        ii = (st[:, None] + np.arange(bloque)).ravel()[:T]
        difs[j] = (x[ii].std(ddof=1) - y[ii].std(ddof=1)) * np.sqrt(12)
    obs = (x.std(ddof=1) - y.std(ddof=1)) * np.sqrt(12)
    lo, hi = np.quantile(difs, [0.025, 0.975])
    p = float(min(1.0, 2 * min((difs >= 0).mean(), (difs <= 0).mean())))
    return {"dif": float(obs), "lo": float(lo), "hi": float(hi), "p": p}


def barajar_bloques(s: pd.Series, bloque: int, rng) -> pd.Series:
    v = s.to_numpy()
    trozos = [v[i:i + bloque] for i in range(0, len(v), bloque)]
    orden = rng.permutation(len(trozos))
    return pd.Series(np.concatenate([trozos[o] for o in orden]), index=s.index)


def dsr(r_ex: pd.Series, sr_todas: list[float], n: int) -> float:
    """Deflated Sharpe (Bailey y López de Prado 2014) con Sharpe mensuales."""
    sr = r_ex.mean() / r_ex.std(ddof=1)
    T, g3, g4 = len(r_ex), float(r_ex.skew()), float(r_ex.kurt() + 3)
    v = float(np.var(sr_todas, ddof=1))
    em = 0.5772156649
    sr0 = np.sqrt(v) * ((1 - em) * norm.ppf(1 - 1 / n) + em * norm.ppf(1 - 1 / (n * np.e)))
    return float(norm.cdf((sr - sr0) * np.sqrt(T - 1) / np.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2)))


def holm(ps: dict, alfa: float = 0.05) -> dict:
    orden = sorted(ps, key=ps.get)
    out, m, sigue = {}, len(ps), True
    for i, k in enumerate(orden):
        sigue = sigue and ps[k] <= alfa / (m - i)
        out[k] = sigue
    return out
