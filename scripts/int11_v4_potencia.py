"""INT-11 v4-correlaciones: descriptivos de la dependencia entre activos por régimen (≤ 2004) y POTENCIA de la regla
"las correlaciones dependen del régimen" (docs/int/INT11_v4_correlaciones_v0.md). NO es la puerta de v4: no se evalúa
el motor contra resultados reales; los contrastes de la potencia se hacen con paneles SINTÉTICOS.

Partes:
  A. Descriptivos anuales JST ≤ 2004 (núcleo de 14 países del motor, sin guerras ni hiperinflación; sensibilidad con
     los 18): correlación de las rentabilidades reales (log 1 + r) bolsa-bonos, bolsa-vivienda, bonos-oro, bolsa-oro,
     bonos-vivienda, por régimen de inflación (P3 operable del año, P3 conocido al empezar el año, INT-3 ex post) y de
     crecimiento (INT-3 ex post; el eje P3 de brecha < 0 es raro). Correlación de los choques: cada variable menos la
     media del país dentro del régimen. IC 90 % por bootstrap de AÑOS (todas las filas de un año juntas).
  B. Cambios estructurales (descriptivo): serie anual c_t = media entre países de z_bolsa·z_bono (z por país); sup-F de
     un cambio de media (recorte 15 %, valor crítico de Andrews 1993) con p por bootstrap de bloques de 5 años; lo mismo
     con c_t limpia del régimen de inflación (residuo de c_{i,t} sobre la indicadora de inflación alta).
  C. Descriptivo mensual OCDE ≤ 2004: correlación bolsa (precio OCDE + dividendo JST; media mensual → suavizada) y bono
     (desde el tipo a 10 años, src/intl/returns.py) por inflación interanual "as of" > 3 %; por décadas.
  D. El motor v3 (descriptivo de su SALIDA, sin resultados de prueba): correlación bolsa-bonos en los sorteos a 1 año por
     régimen de partida frente a la de sus celdas; con y sin suavizado (atenuación por ruido independiente).
  E. Potencia por simulación (estructura real ≤ 2004: filas, huecos, régimen observado y su persistencia; medias, dt,
     correlaciones por régimen y parte común del año medidas en A): verdad R_s(λ) = R̄ + λ(R̂_s − R̄); modelos M_fija
     (R̄ del entrenamiento) y M_reg (R̂_s encogida hacia R̄ con n0 = 30); LOCO; predictiva = mezcla sobre el régimen del
     año con P(s_t | s_{t−1}); puntuaciones: energy score (bolsa, bonos), CRPS de la cartera 60/40, log score bivariante
     y cobertura p5-p95 de la 60/40 por régimen; DM unilateral con años como conglomerados (α = 0,05); potencia y MDE.
     Además, diseño "bloqueado" hipotético (entrena ≤ 2004, prueba 16 años × 14 países con una fracción de inflación
     alta SUPUESTA: no se lee nada ≥ 2005).

Uso: .venv/bin/python -m scripts.int11_v4_potencia            (árbol limpio; escribe research/int/int11_v4_potencia.json)
     .venv/bin/python -m scripts.int11_v4_potencia --prueba   (pocas réplicas, sin puerta; no escribe)
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from scripts.int11_corrida import COL, NUCLEO, cargar_real
from src.intl import activos3b as A3
from src.intl import data as D
from src.intl import escenarios as E
from src.intl import int6 as S
from src.intl import panel as P
from src.intl.procedencia import procedencia
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/int11_v4_potencia.json"
SEED = 20261105
PARES = (("bolsa", "bonos"), ("bolsa", "vivienda"), ("bonos", "oro"), ("bolsa", "oro"), ("bonos", "vivienda"))
B_BOOT = 1000
N0_REG = 30.0                    # encogimiento de la correlación por régimen hacia la agrupada (= n0_cov del modo t)
LAMBDAS = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0)
M_SORTEOS = 400
ALFA = 0.05
W6040 = np.array([0.6, 0.4])
CAIDA = -0.15                    # Brier de "cartera 60/40 ≤ −15 % real en el año" (cola conjunta)
PUNT = ("es", "crps", "ls", "brier")


# ============================================================================ datos
def cargar_todos(con) -> pd.DataFrame:
    """Como scripts.int11_corrida.cargar_real pero con los 18 países (sensibilidad descriptiva)."""
    a = P.anual(con)
    df = a.reset_index()[["pais", "año", "inflacion", "rgdpmad", *COL.values()]].rename(
        columns={v: k for k, v in COL.items()})
    oro = A3.oro_panel(con, D.PAISES)
    oro = oro[oro["año"] >= 1972][["pais", "año", "oro_real_local"]].rename(columns={"oro_real_local": "oro"})
    df = df.merge(oro, on=["pais", "año"], how="left")
    fuera = S.hiper_fuera(np.expm1(a["inflacion"]).dropna())
    f = E.preparar_filas(df, excluir=set(E.GUERRAS) | set(fuera))
    if f["año"].max() > 2004:
        raise D.FactorCutoffError("filas > 2004")
    return f


def con_int3(f: pd.DataFrame) -> pd.DataFrame:
    """Añade el cuadrante ex post de INT-1/INT-3 (relativa + 2 %, ventanas centradas; NO es PIT) y dos ejes."""
    et = pd.read_parquet(db.DATA_ROOT / "intl" / "regimen_anual_dev.parquet")
    if et["año"].max() > 2004:
        raise D.FactorCutoffError("etiqueta INT-3 con años > 2004")
    et = et[~et["truncada"].fillna(True).astype(bool)][["pais", "año", "cuadrante"]]
    g = f.merge(et, on=["pais", "año"], how="left")
    g["i3_infl_alta"] = g["cuadrante"].map({"sobrecalentamiento": 1, "estanflacion": 1, "expansion": 0,
                                            "crecimiento_bajo": 0})
    g["i3_crec_alto"] = g["cuadrante"].map({"sobrecalentamiento": 1, "expansion": 1, "estanflacion": 0,
                                            "crecimiento_bajo": 0})
    g["p3_infl_alta"] = np.isin(g["s"], (1, 2)).astype(float)
    g["p3_infl_alta_prev"] = np.isin(g["s_prev"], (1, 2)).astype(float)
    return g


# ============================================================================ A. correlaciones por régimen
def _choques(g: pd.DataFrame, a: str, b: str, estado: str | None) -> pd.DataFrame:
    """Filas con a y b finitos (log 1 + r), menos la media del país dentro del estado; columnas x, y, año, pais, k."""
    h = g[["pais", "año", a, b] + ([estado] if estado else [])].dropna().copy()
    h["k"] = h[estado].astype(int) if estado else 0
    for v in (a, b):
        h[v] = np.log1p(h[v])
    n = h.groupby(["pais", "k"])[a].transform("size")
    h = h[n >= 3].copy()
    for v in (a, b):
        h[v] = h[v] - h.groupby(["pais", "k"])[v].transform("mean")
    return h.rename(columns={a: "x", b: "y"})[["pais", "año", "k", "x", "y"]]


def _corr(x, y) -> float:
    if len(x) < 5:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def corr_regimen(g: pd.DataFrame, a: str, b: str, estado: str | None, rng, B: int = B_BOOT) -> dict:
    h = _choques(g, a, b, estado)
    B = min(B, B_BOOT)
    if len(h) < 20:
        return {"n": int(len(h)), "nota": "sin filas suficientes"}
    ks = sorted(h["k"].unique())
    años = h["año"].to_numpy()
    au, inv = np.unique(años, return_inverse=True)
    por_año = [np.flatnonzero(inv == j) for j in range(len(au))]
    X, Y, K = h["x"].to_numpy(), h["y"].to_numpy(), h["k"].to_numpy()
    est = {k: _corr(X[K == k], Y[K == k]) for k in ks}
    boot = {k: [] for k in ks}
    dif = []
    for _ in range(B):
        idx = np.concatenate([por_año[j] for j in rng.integers(0, len(au), len(au))])
        r = {k: _corr(X[idx][K[idx] == k], Y[idx][K[idx] == k]) for k in ks}
        for k in ks:
            boot[k].append(r[k])
        if len(ks) == 2:
            dif.append(r[1] - r[0])
    out = {"n": {str(k): int((K == k).sum()) for k in ks}, "paises": int(h["pais"].nunique()),
           "años": [int(au.min()), int(au.max())],
           "rho": {str(k): round(est[k], 3) for k in ks},
           "ic90": {str(k): np.round(np.nanpercentile(boot[k], [5, 95]), 3).tolist() for k in ks},
           "spearman": {str(k): round(float(stats.spearmanr(X[K == k], Y[K == k])[0]), 3) for k in ks}}
    if len(ks) == 2:
        d = np.array(dif)
        out["dif_1_menos_0"] = round(est[1] - est[0], 3)
        out["dif_ic90"] = np.round(np.nanpercentile(d, [5, 95]), 3).tolist()
        out["dif_frac_boot_neg"] = round(float(np.nanmean(d < 0)), 3)
        # por país (n ≥ 15 en los dos estados): cuántos con el mismo signo de la diferencia agrupada
        signos = []
        for c, hc in h.groupby("pais"):
            if (hc["k"] == 0).sum() >= 15 and (hc["k"] == 1).sum() >= 15:
                signos.append(_corr(hc.x[hc.k == 1], hc.y[hc.k == 1]) - _corr(hc.x[hc.k == 0], hc.y[hc.k == 0]))
        if signos:
            s = np.sign(out["dif_1_menos_0"])
            out["paises_mismo_signo"] = f"{int(np.sum(np.sign(signos) == s))}/{len(signos)}"
            out["dif_mediana_paises"] = round(float(np.median(signos)), 3)
    return out


def descriptivos_anuales(g14: pd.DataFrame, g18: pd.DataFrame, rng) -> dict:
    estados = {"incondicional": None, "p3_infl_alta": "p3_infl_alta", "p3_infl_alta_prev": "p3_infl_alta_prev",
               "i3_infl_alta": "i3_infl_alta", "i3_crec_alto": "i3_crec_alto"}
    out = {}
    for nombre, g in (("nucleo14", g14), ("todos18", g18)):
        out[nombre] = {}
        for a, b in PARES:
            par = f"{a}-{b}"
            out[nombre][par] = {e: corr_regimen(g, a, b, col, rng, B_BOOT if nombre == "nucleo14" else 300)
                                for e, col in estados.items()}
    # estabilidad: subperiodos y cuadrante INT-3 (4 estados) en el núcleo, solo bolsa-bonos y bolsa-vivienda
    sub = {}
    for etiqueta, m in (("<1950", g14["año"] < 1950), ("1950-2004", g14["año"] >= 1950),
                        ("1950-1997", (g14["año"] >= 1950) & (g14["año"] <= 1997)), ("1998-2004", g14["año"] >= 1998)):
        sub[etiqueta] = {f"{a}-{b}": corr_regimen(g14[m], a, b, "p3_infl_alta", rng, 300)
                         for a, b in PARES[:2] + PARES[2:3]}
    out["subperiodos_nucleo14_p3"] = sub
    q = g14.dropna(subset=["cuadrante"]).copy()
    q["kq"] = q["cuadrante"].map({r: i for i, r in enumerate(E.REGIMENES)})
    out["cuadrante_int3_nucleo14"] = {f"{a}-{b}": {**corr_regimen(q, a, b, "kq", rng, 300),
                                                   "codigos": dict(enumerate(E.REGIMENES))} for a, b in PARES[:2]}
    return out


# ============================================================================ B. cambios estructurales
def _supF(c: np.ndarray, recorte: float = 0.15) -> tuple[float, int]:
    T = len(c)
    lo, hi = int(np.floor(recorte * T)), int(np.ceil((1 - recorte) * T))
    ssr0 = ((c - c.mean()) ** 2).sum()
    best, arg = -np.inf, lo
    for k in range(lo, hi):
        ssr1 = ((c[:k] - c[:k].mean()) ** 2).sum() + ((c[k:] - c[k:].mean()) ** 2).sum()
        F = (ssr0 - ssr1) / (ssr1 / (T - 2))
        if F > best:
            best, arg = F, k
    return float(best), arg


def _supF_boot(c: np.ndarray, rng, B: int = 999, bloque: int = 5) -> float:
    F0, _ = _supF(c)
    T = len(c)
    e = c - c.mean()
    n_b = int(np.ceil(T / bloque))
    cnt = 0
    for _ in range(B):
        ini = rng.integers(0, T - bloque + 1, n_b)
        x = np.concatenate([e[i:i + bloque] for i in ini])[:T]
        cnt += _supF(x)[0] >= F0
    return float((cnt + 1) / (B + 1))


def cambios_estructurales(g: pd.DataFrame, rng, a: str = "bolsa", b: str = "bonos") -> dict:
    h = g[["pais", "año", a, b, "p3_infl_alta"]].dropna().copy()
    for v in (a, b):
        x = np.log1p(h[v])
        h["z_" + v] = (x - x.groupby(h["pais"]).transform("mean")) / x.groupby(h["pais"]).transform("std")
    h["c"] = h["z_" + a] * h["z_" + b]
    # residuo del régimen de inflación (media de c por estado, agrupada)
    h["c_res"] = h["c"] - h.groupby("p3_infl_alta")["c"].transform("mean") + h["c"].mean()
    out = {}
    for col in ("c", "c_res"):
        s = h.groupby("año")[col].mean()
        s = s[h.groupby("año").size() >= 5]
        F, k = _supF(s.to_numpy())
        roll = s.rolling(20, min_periods=15).mean()
        out[col] = {"años": [int(s.index.min()), int(s.index.max())], "T": int(len(s)), "supF": round(F, 2),
                    "año_cambio": int(s.index[k]), "media_antes": round(float(s.iloc[:k].mean()), 3),
                    "media_despues": round(float(s.iloc[k:].mean()), 3),
                    "vc_andrews_5": 8.85, "p_bootstrap_bloques5": round(_supF_boot(s.to_numpy(), rng), 3),
                    "media_movil_20a": {int(y): round(float(v), 3) for y, v in roll.dropna().iloc[::5].items()}}
    # descriptivo por país (año de máximo F en la serie del país; solo signo y medias)
    pp = {}
    for c, hc in h.groupby("pais"):
        s = hc.set_index("año")["c"]
        if len(s) >= 40:
            F, k = _supF(s.to_numpy())
            pp[c] = {"año_cambio": int(s.index[k]), "supF": round(F, 2), "antes": round(float(s.iloc[:k].mean()), 2),
                     "despues": round(float(s.iloc[k:].mean()), 2)}
    out["por_pais_c"] = pp
    out["nota"] = ("c_t = media entre países de z_bolsa·z_bono (z por país, periodo completo): su media es la "
                   "correlación agrupada. Valor crítico asintótico sup-F (q = 1, recorte 15 %) de Andrews (1993) ≈ 8,85; "
                   "p por bootstrap de bloques de 5 años bajo media constante. Descriptivo: no decide nada.")
    return out


# ============================================================================ C. mensual OCDE
def descriptivo_mensual(con, rng) -> dict:
    m = P.mensual(con).reset_index()
    if m["fecha"].max() > D.DEV_END:
        raise D.FactorCutoffError("panel mensual > 2004")
    h = m[["pais", "fecha", "r_bolsa_tr", "r_bono", "ipc_yoy"]].dropna().copy()
    h["k"] = (h["ipc_yoy"] > np.log1p(0.03)).astype(int)
    h["año"] = h["fecha"].dt.year
    n = h.groupby(["pais", "k"])["r_bono"].transform("size")
    h = h[n >= 24].copy()
    for v in ("r_bolsa_tr", "r_bono"):
        h[v] = h[v] - h.groupby(["pais", "k"])[v].transform("mean")
    g = h.rename(columns={"r_bolsa_tr": "bolsa", "r_bono": "bonos"})
    g["bolsa"], g["bonos"] = np.expm1(g["bolsa"]), np.expm1(g["bonos"])   # _choques vuelve a tomar log1p
    out = {"global": corr_regimen(g, "bolsa", "bonos", "k", rng, 500)}
    dec = {}
    for d0 in range(1950, 2001, 10):
        gd = g[(g["año"] >= d0) & (g["año"] < d0 + 10)]
        if len(gd) > 200 and gd["k"].nunique() == 2:
            dec[f"{d0}s"] = corr_regimen(gd, "bolsa", "bonos", "k", rng, 200)
        elif len(gd) > 200:
            dec[f"{d0}s"] = {"n": int(len(gd)), "rho_incondicional": round(_corr(gd.bolsa, gd.bonos), 3)}
    out["decadas"] = dec
    out["nota"] = ("rentabilidades mensuales NOMINALES en moneda local; bolsa = precio OCDE (media mensual: suavizada) "
                   "+ dividendo JST/12, sin DNK ni JPN; bono = rentabilidad aproximada desde el tipo a 10 años; ESP desde "
                   "1992; estado = inflación interanual 'as of' (con retraso de publicación) > 3 %. Bootstrap por años.")
    return out


# ============================================================================ D. salida del motor v3
def correlacion_motor(f14: pd.DataFrame) -> dict:
    """Pares de PARES en los sorteos a 1 año del motor frente a las filas con los dos datos de s_prev = s0 (crudas)."""
    acts = list(E.ACTIVOS)
    out = {}
    for nombre, cfg in (("v3", E.Config.v3()), ("v3_sin_suavizado", E.Config.v3(c_suavizado=0.0))):
        gen = E.Generador(cfg).ajustar(f14)
        res = {}
        for c in ("USA", "DEU", "GBR", "ESP"):
            for s0 in (0, 1):
                esc = gen.simular(c, s0, horizonte=1, n_lotes=100, por_lote=100, semilla=SEED + s0)
                R = np.log1p(esc.rent[:, 0, :])
                d = {}
                for a, b in PARES:
                    ia, ib = acts.index(a), acts.index(b)
                    ok = np.isfinite(R[:, ia]) & np.isfinite(R[:, ib])
                    d[f"{a}-{b}"] = round(_corr(R[ok, ia], R[ok, ib]), 3)
                res[f"{c}|{E.REGIMENES[s0]}"] = d
        out[nombre] = res
    cel = {}
    for s0 in (0, 1):
        d = {}
        for a, b in PARES:
            h = f14[(f14["s_prev"] == s0)][[a, b]].dropna()
            d[f"{a}-{b}"] = {"rho": round(_corr(np.log1p(h[a]), np.log1p(h[b])), 3), "n": int(len(h))}
        cel[E.REGIMENES[s0]] = d
    out["filas_por_s_prev_crudas"] = cel
    out["frac_filas_sin_dato"] = {a: round(float(f14[a].isna().mean()), 3) for a in acts}
    out["nota"] = ("correlación (log) de los sorteos a 1 año del motor ajustado con todas las filas ≤ 2004 "
                   "(descriptivo de la SALIDA; no compara con resultados). Las filas crudas incluyen el efecto país "
                   "y la media del año. Un activo sin dato en la fila sorteada se imputa con un donante INDEPENDIENTE "
                   "de la misma celda (oro antes de 1972, vivienda): eso diluye su correlación con los demás.")
    return out


# ============================================================================ E. potencia
def medir_estructura(g: pd.DataFrame) -> dict:
    """Parámetros de la verdad sintética, medidos ≤ 2004 en el núcleo (régimen = P3 del año, inflación alta/baja)."""
    h = g[["pais", "año", "bolsa", "bonos", "s", "s_prev"]].dropna().copy()
    for v in ("bolsa", "bonos"):
        h[v] = np.log1p(h[v])
    h["k"] = np.isin(h["s"], (1, 2)).astype(int)
    h["kp"] = np.isin(h["s_prev"], (1, 2)).astype(int)
    mu, sd, R = {}, {}, {}
    for k in (0, 1):
        x = h[h.k == k]
        mu[k] = x[["bolsa", "bonos"]].mean().to_numpy()
        sd[k] = x[["bolsa", "bonos"]].std().to_numpy()
    # correlación de choques (menos la media país × estado), como en A
    ch = _choques(g.assign(k_=np.isin(g["s"], (1, 2)).astype(float)), "bolsa", "bonos", "k_")
    for k in (0, 1):
        R[k] = _corr(ch.x[ch.k == k], ch.y[ch.k == k])
    rbar = _corr(ch.x, ch.y)
    # efecto país (dt de las medias por país) y parte común del año (ICC por activo)
    tau = h.groupby("pais")[["bolsa", "bonos"]].mean().std().to_numpy()
    icc = []
    for v in ("bolsa", "bonos"):
        e = h[v] - h.groupby(["pais", "k"])[v].transform("mean")
        ym = e.groupby(h["año"]).transform("mean")
        icc.append(float(np.var(ym) / np.var(e)))
    trans = {kp: float(h[h.kp == kp].k.mean()) for kp in (0, 1)}
    return {"mu": {k: v.round(4).tolist() for k, v in mu.items()}, "sd": {k: v.round(4).tolist() for k, v in sd.items()},
            "rho": {k: round(v, 3) for k, v in R.items()}, "rho_agrupada": round(rbar, 3),
            "tau_pais": tau.round(4).tolist(), "icc_año": np.round(icc, 3).tolist(),
            "p_alta_dado_prev": {k: round(v, 3) for k, v in trans.items()}, "n": int(len(h)),
            "frac_alta": round(float(h.k.mean()), 3)}


def _corrmat(r: float) -> np.ndarray:
    return np.array([[1.0, r], [r, 1.0]])


def simular_verdad(est: pd.DataFrame, med: dict, lam: float, rng, nu: float = 5.0) -> np.ndarray:
    """(n, 2) log-rentabilidades sintéticas para las filas `est` (pais, año, k). Total por estado: corr R_k(λ);
    parte común del año con corr agrupada y peso ICC; parte propia con la corr que cuadra el total; colas t_ν comunes a
    los dos activos de la fila (t multivariante); efecto país N(0, τ)."""
    rbar = med["rho_agrupada"]
    icc = float(np.mean(med["icc_año"]))
    paises = est["pais"].unique()
    ef = {c: rng.standard_normal(2) * np.array(med["tau_pais"]) for c in paises}
    años = np.unique(est["año"])
    F = rng.standard_normal((len(años), 2)) @ np.linalg.cholesky(_corrmat(rbar)).T
    Fi = F[np.searchsorted(años, est["año"].to_numpy())]
    k = est["k"].to_numpy()
    Z = np.empty((len(est), 2))
    for s in (0, 1):
        rt = float(np.clip(rbar + lam * (med["rho"][s] - rbar), -0.95, 0.95))
        re = float(np.clip((rt - icc * rbar) / (1 - icc), -0.99, 0.99))
        m = k == s
        Z[m] = np.sqrt(icc) * Fi[m] + np.sqrt(1 - icc) * (rng.standard_normal((m.sum(), 2)) @
                                                           np.linalg.cholesky(_corrmat(re)).T)
    W = np.sqrt((nu - 2) / rng.chisquare(nu, (len(est), 1)))
    Z *= W
    mu = np.array([med["mu"][s] for s in (0, 1)])[k]
    sd = np.array([med["sd"][s] for s in (0, 1)])[k]
    return mu + np.stack([ef[c] for c in est["pais"]]) + sd * Z


def _ajustar(Y, k, kp, n0: float):
    """Marginales por estado, P(alta | prev) y correlaciones (agrupada y por estado encogida, de choques ≈ desviaciones
    respecto de la media del estado)."""
    p = {}
    for s in (0, 1):
        x = Y[k == s]
        p[("mu", s)], p[("sd", s)] = x.mean(0), x.std(0, ddof=1)
    Zs = np.empty_like(Y)
    for s in (0, 1):
        Zs[k == s] = (Y[k == s] - p[("mu", s)]) / p[("sd", s)]
    rbar = float(np.corrcoef(Zs.T)[0, 1])
    for s in (0, 1):
        m = k == s
        r = float(np.corrcoef(Zs[m].T)[0, 1])
        n = m.sum()
        p[("rfij", s)] = rbar
        p[("rreg", s)] = (n * r + n0 * rbar) / (n + n0)
    p["pa"] = {s: float(np.mean(k[kp == s] == 1)) for s in (0, 1)}
    return p


def _puntuar(Y, kp, p, rng, M: int = M_SORTEOS, k_oraculo=None) -> dict:
    """Puntuaciones por fila de prueba para M_fija y M_reg (números aleatorios comunes). k_oraculo: régimen del año
    conocido (cota superior de la ganancia; el motor real solo conoce s_{t−1})."""
    n = len(Y)
    pa = np.array([p["pa"][int(s)] for s in kp]) if k_oraculo is None else np.asarray(k_oraculo, float)
    S = (rng.random((n, M)) < pa[:, None]).astype(int)                 # régimen del año en cada sorteo
    Z = rng.standard_normal((n, M, 2))
    W = np.sqrt(3 / rng.chisquare(5, (n, M, 1)))                        # predictiva t5 (colas, misma en los dos)
    out = {}
    for mod in ("rfij", "rreg"):
        X = np.empty((n, M, 2))
        for s in (0, 1):
            r = p[(mod, s)]
            L = np.linalg.cholesky(_corrmat(r))
            Xs = p[("mu", s)] + p[("sd", s)] * ((Z @ L.T) * W)
            X = np.where((S == s)[..., None], Xs, X)
        Xp = np.roll(X, 1, axis=1)
        es = np.linalg.norm(X - Y[:, None], axis=2).mean(1) - 0.5 * np.linalg.norm(X - Xp, axis=2).mean(1)
        cart = (np.expm1(X) @ W6040)
        yc = np.expm1(Y) @ W6040
        crps = np.abs(cart - yc[:, None]).mean(1) - 0.5 * np.abs(cart - np.roll(cart, 1, 1)).mean(1)
        lo, hi = np.quantile(cart, [0.05, 0.95], axis=1)
        dentro = (yc >= lo) & (yc <= hi)
        # log score de la mezcla de normales bivariantes (exacto; la verdad es t: puntuación de información)
        dens = np.zeros(n)
        for s in (0, 1):
            w = np.where(s == 1, pa, 1 - pa)
            cov = np.outer(p[("sd", s)], p[("sd", s)]) * _corrmat(p[(mod, s)])
            dens += w * stats.multivariate_normal(p[("mu", s)], cov).pdf(Y)
        brier = ((cart <= CAIDA).mean(1) - (yc <= CAIDA)) ** 2
        out[mod] = {"es": es, "crps": crps, "dentro": dentro, "ls": -np.log(np.maximum(dens, 1e-300)), "brier": brier}
    return out


def una_replica(est: pd.DataFrame, med: dict, lam: float, rng, diseño: str = "loco", prueba_est=None,
                oraculo: bool = False) -> dict:
    """Panel sintético con la estructura `est` (y `prueba_est` en el bloqueado), evaluación y DM por puntuación."""
    Y = simular_verdad(est, med, lam, rng)
    k, kp, pais, año = est["k"].to_numpy(), est["kp"].to_numpy(), est["pais"].to_numpy(), est["año"].to_numpy()
    sc = {m: {s: np.full(len(est) if diseño == "loco" else len(prueba_est), np.nan) for s in PUNT}
          for m in ("rfij", "rreg")}
    dentro = {m: np.zeros(len(est) if diseño == "loco" else len(prueba_est), bool) for m in ("rfij", "rreg")}
    if diseño == "loco":
        kt, años_t = k, año
        for c in np.unique(pais):
            tr, te = pais != c, pais == c
            p = _ajustar(Y[tr], k[tr], kp[tr], N0_REG)
            r = _puntuar(Y[te], kp[te], p, rng, k_oraculo=k[te] if oraculo else None)
            for m in r:
                for s in PUNT:
                    sc[m][s][te] = r[m][s]
                dentro[m][te] = r[m]["dentro"]
    else:
        p = _ajustar(Y, k, kp, N0_REG)
        Yt = simular_verdad(prueba_est, med, lam, rng)
        r = _puntuar(Yt, prueba_est["kp"].to_numpy(), p, rng)
        for m in r:
            for s in PUNT:
                sc[m][s][:] = r[m][s]
            dentro[m][:] = r[m]["dentro"]
        kt, años_t = prueba_est["k"].to_numpy(), prueba_est["año"].to_numpy()
    o = {}
    for s in PUNT:
        d = sc["rfij"][s] - sc["rreg"][s]
        dm = E.dm_conglomerado(d, años_t, lags=2)
        o[s] = {"p": dm["p_unilateral"], "mejora_rel": float(d.mean() / np.mean(sc["rfij"][s]))
                if s != "ls" else float(d.mean())}
    for m in ("rfij", "rreg"):
        o[f"cob_{m}"] = {str(s): float(dentro[m][kt == s].mean()) for s in (0, 1)}
    return o


def potencia(f14: pd.DataFrame, med: dict, R: int, rng) -> dict:
    est = f14[["pais", "año", "bolsa", "bonos", "s", "s_prev"]].dropna().copy()
    est["k"] = np.isin(est["s"], (1, 2)).astype(int)
    est["kp"] = np.isin(est["s_prev"], (1, 2)).astype(int)
    est = est[["pais", "año", "k", "kp"]].reset_index(drop=True)
    res = {"loco": {}, "bloqueado": {}}
    for lam in LAMBDAS:
        reps = [una_replica(est, med, lam, rng) for _ in range(R)]
        res["loco"][str(lam)] = resumir(reps, med, lam)
    res["loco_oraculo"] = {}
    for lam in (0.0, 1.0, 2.0, 3.0):
        reps = [una_replica(est, med, lam, rng, oraculo=True) for _ in range(R)]
        res["loco_oraculo"][str(lam)] = resumir(reps, med, lam)
    # bloqueado hipotético: 16 años × 14 países, fracción de inflación alta SUPUESTA, persistencia como ≤ 2004
    for frac in (0.15, 0.30):
        clave = f"frac_alta_{frac}"
        res["bloqueado"][clave] = {}
        for lam in (0.0, 1.0, 2.0, 3.0):
            reps = []
            for _ in range(R):
                pe = prueba_hipotetica(frac, med, rng)
                reps.append(una_replica(est, med, lam, rng, "bloqueado", pe))
            res["bloqueado"][clave][str(lam)] = resumir(reps, med, lam)
    return res


def prueba_hipotetica(frac: float, med: dict, rng, años=range(2005, 2021), paises=NUCLEO) -> pd.DataFrame:
    """Estados de 2005-2020 SUPUESTOS (no leídos): cadena de Markov por país con la persistencia de ≤ 2004 reescalada
    para que la fracción estacionaria de inflación alta sea `frac`; un factor común del año (mitad de los países
    sigue el estado 'mundo')."""
    p11 = med["p_alta_dado_prev"][1]
    p01 = frac * (1 - p11) / (1 - frac)
    filas = []
    mundo = [rng.random() < frac]
    for _ in range(len(años) - 1):
        mundo.append(rng.random() < (p11 if mundo[-1] else p01))
    for c in paises:
        prev = rng.random() < frac
        for t, a in enumerate(años):
            q = p11 if prev else p01
            q = 0.5 * q + 0.5 * float(mundo[t])
            cur = rng.random() < q
            filas.append((c, a, int(cur), int(prev)))
            prev = cur
    return pd.DataFrame(filas, columns=["pais", "año", "k", "kp"])


def resumir(reps: list[dict], med: dict, lam: float) -> dict:
    rbar = med["rho_agrupada"]
    out = {"rho_verdad": {str(s): round(float(np.clip(rbar + lam * (med["rho"][s] - rbar), -0.95, 0.95)), 3)
                          for s in (0, 1)}}
    out["delta_rho_verdad"] = round(out["rho_verdad"]["1"] - out["rho_verdad"]["0"], 3)
    for s in PUNT:
        ps = np.array([r[s]["p"] for r in reps])
        mj = np.array([r[s]["mejora_rel"] for r in reps])
        out[s] = {"potencia": round(float(np.mean(ps < ALFA)), 3), "mejora_media": float(np.round(mj.mean(), 5)),
                  "mejora_p10_p90": np.round(np.percentile(mj, [10, 90]), 5).tolist()}
    for m in ("rfij", "rreg"):
        out[f"cobertura_6040_{m}"] = {s: round(float(np.mean([r[f"cob_{m}"][s] for r in reps])), 3) for s in ("0", "1")}
    out["R"] = len(reps)
    return out


def mde(res: dict, clave: str = "es") -> dict:
    """λ mínimo de la rejilla con potencia ≥ 0,8 (interpolación lineal) y su Δρ."""
    lam = np.array([float(x) for x in res])
    pw = np.array([res[x][clave]["potencia"] for x in res])
    dr = np.array([res[x]["delta_rho_verdad"] for x in res])
    if (pw >= 0.8).any():
        j = int(np.argmax(pw >= 0.8))
        if j == 0:
            return {"lambda": float(lam[0]), "delta_rho": float(dr[0])}
        t = (0.8 - pw[j - 1]) / max(pw[j] - pw[j - 1], 1e-9)
        return {"lambda": round(float(lam[j - 1] + t * (lam[j] - lam[j - 1])), 2),
                "delta_rho": round(float(dr[j - 1] + t * (dr[j] - dr[j - 1])), 3)}
    return {"lambda": None, "delta_rho": None, "nota": f"potencia < 0,8 en toda la rejilla (máx {pw.max():.2f})"}


# ============================================================================ main
def main() -> None:
    prueba = "--prueba" in sys.argv
    proc = {"prueba": True} if prueba else procedencia()
    if not prueba and SALIDA.exists():
        raise SystemExit(f"{SALIDA} ya existe (una sola corrida)")
    warnings.filterwarnings("ignore")
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    con = D.connect()
    try:
        f14 = cargar_real(con)
        f18 = cargar_todos(con)
        mens = descriptivo_mensual(con, rng)
    finally:
        con.close()
    g14, g18 = con_int3(f14), con_int3(f18)
    global B_BOOT
    if prueba:
        B_BOOT = 50
    out = {"procedencia": proc, "semilla": SEED, "diseño": "docs/int/INT11_v4_correlaciones_v0.md",
           "aviso": "Descriptivos ≤ 2004 y potencia sintética. No es la puerta de v4; nada ≥ 2005 leído.",
           "codigos_estado": {"0": "inflación baja (≤ 3 %) / crecimiento bajo", "1": "inflación alta / crecimiento alto"}}
    out["A_anual"] = descriptivos_anuales(g14, g18, rng)
    print("A", round(time.time() - t0), flush=True)
    out["B_cambios"] = cambios_estructurales(g14, rng)
    out["C_mensual"] = mens
    out["D_motor_v3"] = correlacion_motor(f14)
    print("D", round(time.time() - t0), flush=True)
    med = medir_estructura(f14)
    out["E_medicion"] = med
    R = 4 if prueba else 200
    pot = potencia(f14, med, R, rng)
    out["E_potencia"] = pot
    out["E_mde"] = {s: mde(pot["loco"], s) for s in PUNT}
    out["E_mde_oraculo"] = {s: mde(pot["loco_oraculo"], s) for s in PUNT}
    out["E_mde_bloqueado"] = {f: {s: mde(v, s) for s in PUNT} for f, v in pot["bloqueado"].items()}
    out["segundos"] = round(time.time() - t0)
    txt = json.dumps(out, indent=1, ensure_ascii=False, default=float)
    if prueba:
        destino = next((a[9:] for a in sys.argv if a.startswith("--salida=")), "/dev/stdout")
        Path(destino).write_text(txt)
        return
    SALIDA.write_text(txt)
    print("escrito", SALIDA, out["segundos"], "s")


if __name__ == "__main__":
    main()
