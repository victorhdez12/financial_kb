"""INT-4 (termómetro de riesgo ampliado): motor de la corrida única de P-DEV-INT4 v1.0 (docs/int/INT4_prerregistro_v0.md,
congelado en fa6d4c9). Objetivos e indicadores con las MISMAS definiciones que scripts/int4_potencia.py y
scripts/int4b_potencia.py (aquí con la lista de países como parámetro, para los países de prueba; un test comprueba que
con el núcleo dan las mismas filas). Todo con datos ≤ 2004 y "as of" (origen 30-abr de t + 1, datos JST del año t).

Concreciones de la implementación (fijadas antes de correr; no cambian el prerregistro):
- Listón B1 de T1: si un país no tiene valle previo, "años desde el último valle" = años desde su primer año con PIB, y
  "primer año tras un valle" = 0. log(años) con años ≥ 1.
- Casos completos: cada comparación (modelo frente a B1) usa las MISMAS filas, las que tienen B1 y todos los indicadores
  del modelo. Los secundarios (un indicador + B1) usan las filas completas para ese indicador.
- Logit sin penalización por Newton-Raphson (con intercepto); AUC de Mann-Whitney con empates promediados.
- Bootstrap por bloques de año: 2.000 réplicas, se remuestrean años t (con todas sus filas) sobre las predicciones fuera
  de muestra ya hechas (no se reajusta). p bootstrap bilateral = 2·(1 + #{Δ ≤ 0}) / (1 + B) (para Δ > 0; simétrico), y
  el criterio (i) es ese p con Holm (equivale al IC por bloques que excluye 0 tras Holm).
- Placebo: los paneles país × año de los indicadores candidatos (no los del listón) se desplazan k años en círculo dentro
  de 1870-2004, la misma k en todos los países, k = 6 … 129 (124, todas las posibles con k ≥ 6); se rehacen las filas
  completas, los dos modelos y el dejar un país fuera. p = (1 + #{ΔAUC_k ≥ ΔAUC}) / (1 + K), unilateral (mejora).
- Temporal: décadas 1950 … 2000 (la última 2000-2004); ajuste con filas cuyo año objetivo t + h < inicio de la década.
- Calibración: pendiente e intercepto de logit(y) sobre logit(p) de las predicciones fuera de muestra del modelo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import rankdata

from src.intl import regimes as G

A0, A1 = 1870, 2004
L = A1 - A0 + 1
GUERRAS = set(range(1914, 1919)) | set(range(1939, 1946))
DESFASE_MIN = 6
KS = list(range(DESFASE_MIN, L - DESFASE_MIN + 1))
UMBRAL_P = 0.5


# ---------------------------------------------------------------- objetivos (como int4_potencia / int4b_potencia)
def _filtro(t: int, h: int, desde: int, sg: bool, años: set) -> bool:
    if t < desde or t + h > A1 or any(t + k not in años for k in range(1, h + 1)):
        return False
    return not (sg and any(y in GUERRAS for y in range(t, t + h + 1)))


def obj_entrada(rec, años_pais, paises, h, desde, sg) -> pd.DataFrame:
    filas = []
    for c in paises:
        r = rec[rec.pais == c]
        en_rec = {y for _, x in r.iterrows() for y in range(int(x.pico) + 1, int(x.valle) + 1)}
        entradas = {int(x.pico) + 1: x.tipo for _, x in r.iterrows()}
        for t in sorted(años_pais[c]):
            if t < desde or t + h > A1 or t in en_rec or any(t + k not in años_pais[c] for k in range(1, h + 1)):
                continue
            if sg and any(y in GUERRAS for y in range(t, t + h + 1)):
                continue
            E = [y for y in range(t + 1, t + h + 1) if y in entradas]
            filas.append({"pais": c, "t": t, "y": int(bool(E)), "tipo": entradas[E[0]] if E else None})
    return pd.DataFrame(filas)


def obj_salida(rec, años_pais, paises, h, desde, sg) -> pd.DataFrame:
    filas = []
    for c in paises:
        for _, x in rec[rec.pais == c].iterrows():
            X = int(x.valle) + 1
            for t in range(int(x.pico) + 1, int(x.valle) + 1):
                if not _filtro(t, h, desde, sg, años_pais[c]):
                    continue
                filas.append({"pais": c, "t": t, "y": int(t + 1 <= X <= t + h), "tipo": x.tipo, "pico": int(x.pico)})
    return pd.DataFrame(filas)


def obj_inflacion(p_i: pd.DataFrame, paises, h, desde, sg, sube: bool, sin_truncadas: bool = False) -> pd.DataFrame:
    filas = []
    for c in paises:
        d = p_i.loc[p_i.pais == c].set_index("año")
        s = d["p_i_alta"].dropna()
        alta = s >= UMBRAL_P
        años = set(s.index.astype(int))
        cambio = {int(t) for t in alta.index[1:] if alta[t] != alta.get(t - 1, alta[t]) and alta[t] == sube}
        for t in sorted(años):
            if alta[t] == sube or not _filtro(t, h, desde, sg, años):
                continue
            if sin_truncadas and bool(d["truncada"].get(t + 1, True)):
                continue
            E = [y for y in range(t + 1, t + h + 1) if y in cambio]
            filas.append({"pais": c, "t": t, "y": int(bool(E)), "tipo": None})
    return pd.DataFrame(filas)


def etiquetas_inflacion(a: pd.DataFrame, paises) -> dict:
    out = {"principal": [], "abs3": []}
    for c in paises:
        x = a.loc[c]
        for nom, kw in (("principal", {}), ("abs3", {"umbral_i": G.UMBRAL_I_ABSOLUTO, "relativa": False})):
            e = G.etiqueta(np.log(x["rgdpmad"]), x["inflacion"], G.VENTANA_ANUAL, **kw)
            out[nom].append(e[["p_i_alta", "truncada"]].assign(pais=c).reset_index(names="año"))
    return {k: pd.concat(v, ignore_index=True) for k, v in out.items()}


# ---------------------------------------------------------------- indicadores: paneles país × año (1870-2004)
def paneles(a: pd.DataFrame, extra: pd.DataFrame, nucleo: list[str], paises: list[str], mp: pd.Series | None) -> dict:
    """Paneles (DataFrame años × países) de los indicadores candidatos, con las fórmulas de int4_potencia
    (cobertura_anual) e int4b_potencia (candidatos_nuevos). `extra` trae hpnom, money, wage."""
    años = range(A0, A1 + 1)
    w = lambda s: s.unstack(0).reindex(index=años, columns=paises)  # noqa: E731
    x = a.join(extra, how="left")
    g = x.groupby(level=0)
    curva = x["ltrate"] - x["stir"]
    out = {"C1": w(curva), "C2": w(g["credito_pib"].diff(5)),
           "C3": w(g.apply(lambda d: np.log(d["hpnom"] / d["cpi"]).diff(3)).reset_index(level=0, drop=True)),
           "C5": w((x["stir"] / 100 - x["inflacion"]).groupby(level=0).diff(1)), "C6": w(x["eq_tr_real"])}
    inv = (curva < 0).astype(float).where(curva.notna()).unstack(0).reindex(index=años)
    caida = (x["pib_real_g"] < 0).astype(float).where(x["pib_real_g"].notna()).unstack(0).reindex(index=años)
    c4, s4 = {}, {}
    for c in paises:
        otros = [k for k in nucleo if k != c and k in inv.columns]
        c4[c] = inv[otros].mean(axis=1).where(inv[otros].notna().sum(axis=1) >= 5)
        otros = [k for k in nucleo if k != c and k in caida.columns]
        s4[c] = caida[otros].mean(axis=1).where(caida[otros].notna().sum(axis=1) >= 5)
    out["C4"], out["S4"] = pd.DataFrame(c4), pd.DataFrame(s4)
    out["P1"] = w(g["money"].transform(lambda s: np.log(s).diff()))
    out["P2"] = w(g["wage"].transform(lambda s: np.log(s).diff()))
    lp = np.log(x["rgdpmad"])
    out["P3"] = w(lp - lp.groupby(level=0).transform(lambda s: s.shift(1).rolling(10, min_periods=10).mean()))
    out["P5"] = w(x["stir"] / 100 - x["inflacion"])
    if mp is not None:
        out["P4"] = pd.DataFrame({c: mp.reindex(años) for c in paises})
    # listones (no se desplazan nunca)
    out["_infl"] = w(x["inflacion"])
    return {k: v.replace([np.inf, -np.inf], np.nan) for k, v in out.items()}


def desplazar_panel(p: pd.DataFrame, k: int) -> pd.DataFrame:
    """Valor del año y pasa al año A0 + (y − A0 + k) mod L, en todos los países a la vez."""
    v = p.to_numpy()
    return pd.DataFrame(np.roll(v, k, axis=0), index=p.index, columns=p.columns)


def _mira(panel: pd.DataFrame, paises, años) -> np.ndarray:
    ci = panel.columns.get_indexer(paises)
    yi = np.asarray(años) - A0
    ok = (yi >= 0) & (yi < L) & (ci >= 0)
    out = np.full(len(yi), np.nan)
    out[ok] = panel.to_numpy()[yi[ok], ci[ok]]
    return out


def matriz(filas: pd.DataFrame, pan: dict, cols: list[str], k: int = 0) -> np.ndarray:
    """Valores de los indicadores en las filas (país, t). S5 = C2 en el año del pico (solo filas de T2); S1 = C1,
    S2 = C5, S3 = C6. Con k ≠ 0, los paneles candidatos se desplazan k años (placebo)."""
    alias = {"S1": "C1", "S2": "C5", "S3": "C6"}
    out = []
    for c in cols:
        base = "C2" if c == "S5" else alias.get(c, c)
        p = pan[base] if k == 0 else desplazar_panel(pan[base], k)
        años = filas["pico"].to_numpy() if c == "S5" else filas["t"].to_numpy()
        out.append(_mira(p, filas["pais"].to_numpy(), años))
    return np.column_stack(out) if out else np.empty((len(filas), 0))


def liston(filas: pd.DataFrame, giro: str, rec: pd.DataFrame, primer_año: dict, pan: dict) -> np.ndarray:
    """B1 (solo información conocida en el origen)."""
    if giro == "T1":
        a, b = [], []
        for c, t in zip(filas.pais, filas.t):
            vs = [int(v) for v in rec.loc[rec.pais == c, "valle"] if int(v) < t]
            ref = max(vs) if vs else primer_año[c]
            a.append(float(bool(vs) and t == max(vs) + 1))
            b.append(np.log(max(t - ref, 1)))
        return np.column_stack([a, b])
    if giro == "T2":
        return np.log(np.maximum(filas.t.to_numpy() - filas.pico.to_numpy(), 1)).reshape(-1, 1).astype(float)
    p = pan["_infl"]
    return np.column_stack([_mira(p, filas.pais.to_numpy(), filas.t.to_numpy()),
                            _mira(p, filas.pais.to_numpy(), filas.t.to_numpy() - 1)])


# ---------------------------------------------------------------- logit, métricas
def logit_fit(X: np.ndarray, y: np.ndarray, it: int = 100) -> np.ndarray:
    Xc = np.column_stack([np.ones(len(X)), X])
    b = np.zeros(Xc.shape[1])
    b[0] = np.log(max(y.mean(), 1e-6) / max(1 - y.mean(), 1e-6))
    ll_prev = -np.inf
    for _ in range(it):
        eta = np.clip(Xc @ b, -30, 30)
        p = 1 / (1 + np.exp(-eta))
        g = Xc.T @ (y - p)
        H = (Xc * (p * (1 - p))[:, None]).T @ Xc
        paso = np.linalg.lstsq(H, g, rcond=None)[0]
        t = 1.0
        while t > 1e-4:
            bn = b + t * paso
            en = np.clip(Xc @ bn, -30, 30)
            ll = float(np.sum(y * en - np.log1p(np.exp(en))))
            if ll >= ll_prev - 1e-10:
                break
            t /= 2
        b, ll_old, ll_prev = bn, ll_prev, ll
        if abs(ll - ll_old) < 1e-9:
            break
    return b


def logit_pred(b: np.ndarray, X: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(b[0] + X @ b[1:], -30, 30)))


def auc(y: np.ndarray, p: np.ndarray) -> float:
    y = y.astype(bool)
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return np.nan
    r = rankdata(p)
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def logloss(y, p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier(y, p):
    return float(np.mean((p - y) ** 2))


def calibracion(y, p) -> dict:
    lp = np.log(np.clip(p, 1e-12, 1 - 1e-12) / np.clip(1 - p, 1e-12, 1))
    b = logit_fit(lp.reshape(-1, 1), y)
    return {"intercepto": float(b[0]), "pendiente": float(b[1])}


def loco(X: np.ndarray, y: np.ndarray, pais: np.ndarray) -> np.ndarray:
    """Dejar un país fuera: predicción de cada país con el modelo ajustado en los demás."""
    p = np.full(len(y), np.nan)
    for c in np.unique(pais):
        f = pais == c
        b = logit_fit(X[~f], y[~f])
        p[f] = logit_pred(b, X[f])
    return p


def temporal(X: np.ndarray, y: np.ndarray, t: np.ndarray, h: int, pais: np.ndarray | None = None) -> np.ndarray:
    """Ventana creciente por décadas 1950 … 2000: ajuste con t + h < inicio; predicción de [inicio, inicio + 9]."""
    if pais is not None:          # sensibilidad con efectos fijos de país
        D = (pais[:, None] == np.unique(pais)[None, 1:]).astype(float)
        X = np.column_stack([X, D])
    p = np.full(len(y), np.nan)
    for d in range(1950, 2001, 10):
        tr, te = t + h < d, (t >= d) & (t <= d + 9)
        if te.any() and tr.sum() > 20 and 0 < y[tr].sum() < tr.sum():
            p[te] = logit_pred(logit_fit(X[tr], y[tr]), X[te])
    return p


def bloques(y, p1, p0, t, B: int = 2000, semilla: int = 0) -> dict:
    """Bootstrap por bloques de año sobre predicciones fijas: Δ = modelo − listón (AUC, log-loss, Brier)."""
    ok = np.isfinite(p1) & np.isfinite(p0)
    y, p1, p0, t = y[ok], p1[ok], p0[ok], t[ok]
    años = np.unique(t)
    idx = {a: np.flatnonzero(t == a) for a in años}
    rng = np.random.default_rng(semilla)
    d = np.empty((B, 3))
    for b in range(B):
        sel = np.concatenate([idx[a] for a in rng.choice(años, len(años), replace=True)])
        yy = y[sel]
        d[b] = (auc(yy, p1[sel]) - auc(yy, p0[sel]), logloss(yy, p1[sel]) - logloss(yy, p0[sel]),
                brier(yy, p1[sel]) - brier(yy, p0[sel]))
    obs = (auc(y, p1) - auc(y, p0), logloss(y, p1) - logloss(y, p0), brier(y, p1) - brier(y, p0))
    da = d[:, 0][np.isfinite(d[:, 0])]
    lado = (da <= 0).sum() if obs[0] > 0 else (da >= 0).sum()
    return {"d_auc": obs[0], "d_auc_ic95": [float(np.quantile(da, 0.025)), float(np.quantile(da, 0.975))],
            "p_bloques": float(min(1.0, 2 * (1 + lado) / (1 + len(da)))),
            "d_logloss": obs[1], "d_logloss_ic95": [float(np.quantile(d[:, 1], 0.025)), float(np.quantile(d[:, 1], 0.975))],
            "d_brier": obs[2], "d_brier_ic95": [float(np.quantile(d[:, 2], 0.025)), float(np.quantile(d[:, 2], 0.975))],
            "años": int(len(años))}


# ---------------------------------------------------------------- una comparación completa
def comparar(filas: pd.DataFrame, B1: np.ndarray, Xc: np.ndarray, h: int = 1, temporal_ok: bool = True) -> dict:
    """Modelo (B1 + Xc) frente a B1 en las filas completas: dejar un país fuera, bootstrap, temporal, calibración."""
    y = filas.y.to_numpy(float)
    ok = np.isfinite(B1).all(axis=1) & np.isfinite(Xc).all(axis=1)
    f, B1, Xc, y = filas[ok].reset_index(drop=True), B1[ok], Xc[ok], y[ok]
    pais, t = f.pais.to_numpy(), f.t.to_numpy()
    X1 = np.column_stack([B1, Xc])
    p1, p0 = loco(X1, y, pais), loco(B1, y, pais)
    out = {"filas": int(len(y)), "eventos": int(y.sum()), "paises": int(np.unique(pais).size),
           "auc_modelo": auc(y, p1), "auc_liston": auc(y, p0), "logloss_modelo": logloss(y, p1),
           "logloss_liston": logloss(y, p0), **bloques(y, p1, p0, t), "calibracion": calibracion(y, p1)}
    m50 = t >= 1950
    out["loco_1950_2004_d_auc"] = auc(y[m50], p1[m50]) - auc(y[m50], p0[m50])
    if temporal_ok:
        q1, q0 = temporal(X1, y, t, h), temporal(B1, y, t, h)
        v = np.isfinite(q1) & np.isfinite(q0)
        out["temporal_1950_2004"] = {"filas": int(v.sum()), "eventos": int(y[v].sum()),
                                     "d_auc": auc(y[v], q1[v]) - auc(y[v], q0[v])}
        r1, r0 = temporal(X1, y, t, h, pais), temporal(B1, y, t, h, pais)
        v = np.isfinite(r1) & np.isfinite(r0)
        out["temporal_1950_2004_efectos_fijos"] = {"d_auc": auc(y[v], r1[v]) - auc(y[v], r0[v])}
    out["_pred"] = (f, p1, p0)
    return out


def placebo(filas: pd.DataFrame, B1: np.ndarray, pan: dict, cols: list[str], d_obs: float) -> dict:
    """ΔAUC (dejar un país fuera) con los indicadores candidatos desplazados k años (k = 6 … 129)."""
    y_all = filas.y.to_numpy(float)
    ds = []
    for k in KS:
        Xk = matriz(filas, pan, cols, k)
        ok = np.isfinite(B1).all(axis=1) & np.isfinite(Xk).all(axis=1)
        y, pais = y_all[ok], filas.pais.to_numpy()[ok]
        if y.sum() < 10 or (1 - y).sum() < 10:
            continue
        p1 = loco(np.column_stack([B1[ok], Xk[ok]]), y, pais)
        p0 = loco(B1[ok], y, pais)
        ds.append(auc(y, p1) - auc(y, p0))
    ds = np.array(ds)
    return {"desplazamientos": int(len(ds)), "p_placebo": float((1 + (ds >= d_obs).sum()) / (1 + len(ds))),
            "d_auc_placebo_media": float(ds.mean()), "d_auc_placebo_p95": float(np.quantile(ds, 0.95))}


def congelado(filas_n, B1n, Xn, filas_p, B1p, Xp) -> dict:
    """Países de prueba: modelo y listón ajustados UNA vez con todo el núcleo; predicción de los países de prueba."""
    yn = filas_n.y.to_numpy(float)
    okn = np.isfinite(B1n).all(axis=1) & np.isfinite(Xn).all(axis=1)
    b1 = logit_fit(np.column_stack([B1n, Xn])[okn], yn[okn])
    b0 = logit_fit(B1n[okn], yn[okn])
    yp = filas_p.y.to_numpy(float)
    okp = np.isfinite(B1p).all(axis=1) & np.isfinite(Xp).all(axis=1)
    if okp.sum() == 0 or yp[okp].sum() == 0:
        return {"filas": int(okp.sum()), "eventos": 0}
    yy, pais, t = yp[okp], filas_p.pais.to_numpy()[okp], filas_p.t.to_numpy()[okp]
    p1 = logit_pred(b1, np.column_stack([B1p, Xp])[okp])
    p0 = logit_pred(b0, B1p[okp])
    out = {"filas": int(okp.sum()), "eventos": int(yy.sum()), **bloques(yy, p1, p0, t)}
    out["por_pais"] = {c: {"filas": int((pais == c).sum()), "eventos": int(yy[pais == c].sum()),
                           "d_auc": auc(yy[pais == c], p1[pais == c]) - auc(yy[pais == c], p0[pais == c])}
                       for c in np.unique(pais)}
    return out
