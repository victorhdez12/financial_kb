"""INT-7 (borrador): potencia de las preguntas "valoración → rentabilidad" ANTES de prerregistrar y sin cruzar ningún
indicador de valoración con ninguna rentabilidad. Solo datos ≤ 2004 (corte de src/factors/data.DEV_END).

Qué usa (y nada más):
  (i)   estadísticos INCONDICIONALES de cada serie POR SEPARADO: dt, AR(1), correlación media entre países, tamaño de
        la muestra; de los indicadores (log D/P de JST; log CAPE de Shiller) y de los resultados (bolsa real de JST y de
        Shiller, a 1, 5 y 10 años) — nunca juntos;
  (ii)  DISPONIBILIDAD (si hay dato en el país-año, nunca su valor) para contar filas;
  (iii) RECUENTOS de país-años en estanflación (etiquetas de INT-1) con disponibilidad, para la pregunta de interacción.
Qué NO hace nunca: una regresión, correlación o media condicionada que junte un indicador de valoración con una
rentabilidad, ni una rentabilidad con un estado. En particular, la correlación entre las innovaciones del indicador y
la rentabilidad (δ, la que genera el sesgo de Stambaugh) NO se mide: se SUPONE en una rejilla tomada de la literatura
(Stambaugh 1999; Lewellen 2004; Campbell-Yogo 2006: δ ≈ −0,7 a −0,95 para D/P en EE. UU.).

Dos MDE (80 % de potencia, bilateral):
  - analítico (como INT-6): MDE = z · dt_y / √N_ef, N_ef = N / [1 + (m* − 1)·ρx·ρy] · (1 − φx·φy)/(1 + φx·φy).
    Ignora el sesgo de Stambaugh y el solape de horizontes: es solo la referencia.
  - simulado: panel sintético con la persistencia (φx), la correlación entre países (ρx, ρy), las dt y la
    DISPONIBILIDAD reales de cada serie, innovaciones correlacionadas δ (supuesta) entre indicador y rentabilidad, y el
    contraste del prerregistro: MCO con efectos fijos de país (y de año en V2), errores Driscoll-Kraay (Newey-West con
    una sola unidad) y valor crítico CALIBRADO con la distribución nula simulada con el mismo δ (lo que hará en la
    corrida el bootstrap nulo que respeta el sesgo de Stambaugh). Publica además el tamaño real del contraste ingenuo
    (t de Student sin calibrar) y el sesgo medio bajo la nula, en pp por dt.
  La rentabilidad es lineal en b: y = b·X + E, con lo que b̂, el residuo y la varianza DK son funciones cerradas de b
  por réplica (números aleatorios comunes para toda la rejilla de b).

z: un contraste y Holm con m = 2, 3, 4 (la familia de INT-7 tendrá como mucho 4 confirmatorias).

Uso: .venv/bin/python -m scripts.int7_potencia            (con puerta: árbol limpio; escribe el JSON)
     .venv/bin/python -m scripts.int7_potencia --prueba   (sin puerta; no escribe nada)
"""
from __future__ import annotations

import itertools
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.intl import data as D
from src.intl import panel as P
from src.intl.procedencia import procedencia
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
NUCLEO = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
HIPER = 0.50
MS = (1, 2, 3, 4)
Z = {f"m{m}": float(stats.norm.ppf(1 - 0.05 / (2 * m)) + stats.norm.ppf(0.80)) for m in MS}
DELTAS = (-0.5, -0.7, -0.9)          # SUPUESTAS (literatura), nunca medidas
NSIM = 3000
SEED = 20261029
# series de Shiller: aún NO están en las familias permitidas de src/intl/data.py (decisión del usuario, §9 del
# borrador). Para la potencia se leen aquí con el mismo corte y la misma comprobación que load_dev, una por una.
SHILLER = ("shiller_cape", "shiller_real_stock_tr_ret_m")


def _r(x, k=3):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), k)


def leer_no_permitida(con, sid: str) -> pd.Series:
    if sid not in SHILLER:
        raise D.FactorCutoffError(f"{sid}: solo se admiten {SHILLER} fuera de las familias")
    df = con.execute("select date, value from obs_latest where series_id = ? and value is not null and date <= ? "
                     "order by date", [sid, D.DEV_END.date()]).df()
    s = pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["date"]), name=sid)
    if s.index.duplicated().any():
        raise D.FactorCutoffError(f"{sid}: fechas repetidas")
    D.check(s)
    return s


# ---------------------------------------------------------------- estadísticos de UNA variable
def ancho(s: pd.Series) -> pd.DataFrame:
    """(pais, año) → matriz año × país, con todos los años intermedios."""
    w = s.unstack(0)
    return w.reindex(range(int(w.index.min()), int(w.index.max()) + 1))


def st_panel(s: pd.Series) -> dict:
    w = ancho(s.dropna())
    pares = [w[[i, j]].dropna().corr().iloc[0, 1] for i, j in itertools.combinations(w.columns, 2)
             if w[[i, j]].dropna().shape[0] >= 20]
    ar1 = {c: float(w[c].autocorr(1)) for c in w.columns if w[c].notna().sum() > 20}
    return {"n": int(s.notna().sum()), "sd": float(s.std()), "rho_paises": float(np.nanmean(pares)) if pares else 0.0,
            "ar1": float(np.nanmean(list(ar1.values()))) if ar1 else 0.0, "ar1_por_pais": {k: _r(v, 2) for k, v in ar1.items()},
            "ar1_min": _r(min(ar1.values()), 2) if ar1 else None, "ar1_max": _r(max(ar1.values()), 2) if ar1 else None}


def dos_vias(s: pd.Series, it: int = 50) -> pd.Series:
    """Quita efecto de país y de año (proyecciones alternadas, panel desequilibrado). Una sola variable."""
    s = s.dropna().copy()
    for _ in range(it):
        s = s - s.groupby(level=0).transform("mean")
        s = s - s.groupby(level=1).transform("mean")
    return s


def m_kish(años) -> float:
    c = pd.Series(np.asarray(años)).value_counts()
    return float(c.mean() * (1 + (c.std(ddof=0) / c.mean()) ** 2))


def mde_analitico(filas: pd.Index, sx: dict, sy: dict, rho_override: float | None = None) -> dict:
    n, mk = len(filas), m_kish(filas.get_level_values(1))
    ar = (1 - sx["ar1"] * sy["ar1"]) / (1 + sx["ar1"] * sy["ar1"])
    out = {"filas": int(n), "m_kish": _r(mk, 2)}
    for nom, rho in (("central", sx["rho_paises"] * sy["rho_paises"] if rho_override is None else rho_override),
                     ("prudente", sy["rho_paises"] if rho_override is None else rho_override)):
        n_ef = n / (1 + (mk - 1) * max(rho, 0.0)) * ar
        out[nom] = {"n_ef": _r(n_ef, 1), **{f"mde_pp_por_dt_z{k}": _r(100 * z * sy["sd"] / np.sqrt(n_ef), 2)
                                            for k, z in Z.items()}}
    return out


def sesgo_kendall(phi: float, T: float, delta: float, sd_y: float) -> float:
    """Sesgo de Stambaugh aproximado de la pendiente MCO (pp por 1 dt de x), con media estimada (Kendall 1954):
    E[b̂ − b] ≈ δ·(σ_e/σ_v)·E[φ̂ − φ], E[φ̂ − φ] ≈ −(1 + 3φ)/T, σ_v = dt_x·√(1 − φ²). Por 1 dt de x: × dt_x."""
    return 100 * delta * sd_y / np.sqrt(1 - phi ** 2) * (-(1 + 3 * phi) / T)


# ---------------------------------------------------------------- simulación del contraste del prerregistro
def dk_t(xt: np.ndarray, r1: np.ndarray, r2: np.ndarray, beta_e: float, cxx: float, k1: float, L: int, T: int,
         bgrid: np.ndarray) -> np.ndarray:
    """t de Driscoll-Kraay para cada b de la rejilla. Matrices año × unidad ya desmediadas (NaN = sin fila).
    ỹ = b·X̃ + Ẽ ⇒ b̂ = b·k1 + beta_e; residuo = b·r1 + r2; puntuaciones por año h_t = b·s1 + s2."""
    m = ~np.isnan(xt)
    x0 = np.where(m, xt, 0.0)
    s1, s2 = (x0 * np.where(m, r1, 0.0)).sum(1), (x0 * np.where(m, r2, 0.0)).sum(1)

    def lrv(a, b):
        S = a @ b
        for l in range(1, L + 1):
            S += (1 - l / (L + 1)) * (a[l:] @ b[:-l] + b[l:] @ a[:-l])
        return S
    S11, S12, S22 = lrv(s1, s1), lrv(s1, s2), lrv(s2, s2)
    var = (bgrid ** 2 * S11 + 2 * bgrid * S12 + S22) / cxx ** 2 * T / (T - 1)
    return (bgrid * k1 + beta_e) / np.sqrt(np.maximum(var, 1e-300))


def desmediar(a: np.ndarray, m: np.ndarray, anio: bool, it: int = 30) -> np.ndarray:
    a = np.where(m, a, np.nan)
    for _ in range(it if anio else 1):
        a = a - np.nanmean(a, axis=0, keepdims=True)
        if anio:
            a = a - np.nanmean(a, axis=1, keepdims=True)
    return np.where(m, a, np.nan)


def simular(mask: np.ndarray, phi: float, rho_x: float, rho_y: float, sd_y: float, delta: float, h: int,
            efectos_año: bool, bgrid: np.ndarray, nsim: int, rng: np.random.Generator) -> dict:
    """mask: años × unidades, True si la fila (x_t, y_{t+1..t+h}) existe. x estandarizado (dt 1); y_{t+1} = b·x_t + e,
    e con dt = dt_y, corr(e_{t+1}, v_{t+1}) = δ dentro de cada componente (común y propio). Devuelve las t por réplica."""
    Tn, N = mask.shape
    T_obs = int(mask.any(1).sum())
    L = max(int(np.floor(4 * (T_obs / 100) ** (2 / 9))), h)
    burn = 50
    tt = np.empty((nsim, len(bgrid)))
    bias0 = np.empty(nsim)
    sdv = np.sqrt(1 - phi ** 2)
    for s in range(nsim):
        n_t = Tn + h + burn
        f = rng.standard_normal(n_t)
        g = rng.standard_normal((n_t, N))
        hh = delta * f + np.sqrt(1 - delta ** 2) * rng.standard_normal(n_t)
        k = delta * g + np.sqrt(1 - delta ** 2) * rng.standard_normal((n_t, N))
        v = np.sqrt(rho_x) * f[:, None] + np.sqrt(1 - rho_x) * g
        e = sd_y * (np.sqrt(rho_y) * hh[:, None] + np.sqrt(1 - rho_y) * k)
        x = np.empty((n_t, N))
        x[0] = rng.standard_normal(N)
        for t in range(1, n_t):
            x[t] = phi * x[t - 1] + sdv * v[t]
        x, e = x[burn:], e[burn:]
        # filas t = 0..Tn−1: x_t; resultado acumulado de t+1..t+h
        X = x[:Tn]
        E = sum(e[1 + j: 1 + j + Tn] for j in range(h))
        Xh = sum(x[j: j + Tn] for j in range(h))          # b·Σ_{j<h} x_{t+j}
        xt = desmediar(X, mask, efectos_año)
        Et, Xht = desmediar(E, mask, efectos_año), desmediar(Xh, mask, efectos_año)
        cxx = np.nansum(xt * xt)
        k1, beta_e = np.nansum(xt * Xht) / cxx, np.nansum(xt * Et) / cxx
        r1, r2 = Xht - k1 * xt, Et - beta_e * xt
        tt[s] = dk_t(xt, r1, r2, beta_e, cxx, k1, L, T_obs, bgrid)
        bias0[s] = beta_e
    return {"t": tt, "bias0": bias0, "T": T_obs, "L": L}


def resumen_sim(sim: dict, bgrid: np.ndarray, signo: int, sd_y: float, phi: float, h: int) -> dict:
    t = sim["t"] * signo                                    # contraste en la dirección esperada
    t0 = t[:, 0]                                            # bgrid[0] = 0: nula
    T = sim["T"]
    out = {"T_años": T, "lags_DK": sim["L"],
           "sesgo_medio_nula_pp_por_dt_pendiente_h": _r(100 * sd_y * signo * np.mean(sim["bias0"]), 2),
           "tamaño_ingenuo_5pc_bilateral": _r(np.mean(np.abs(sim["t"][:, 0]) > stats.t.ppf(0.975, T - 1)), 3),
           "media_t_nula": _r(np.mean(t0), 2), "dt_t_nula": _r(np.std(t0), 2)}
    for m in MS:
        a = 0.05 / (2 * m)
        c = np.quantile(t0, 1 - a)                          # valor crítico calibrado (cola del signo esperado)
        pot = (t[:, 1:] > c).mean(0)
        b = bgrid[1:]
        i = np.argmax(pot >= 0.8) if (pot >= 0.8).any() else None
        if i is None:
            mde = None
        elif i == 0:
            mde = float(b[0])
        else:                                               # interpolación lineal
            mde = float(b[i - 1] + (0.8 - pot[i - 1]) / (pot[i] - pot[i - 1]) * (b[i] - b[i - 1]))
        out[f"m{m}"] = {"t_critica_calibrada": _r(c, 2),
                        "mde_pp_por_dt_1año": _r(100 * mde * sd_y, 2) if mde is not None else "> rejilla",
                        "mde_R2_1año": _r(mde ** 2 / (1 + mde ** 2), 4) if mde is not None else None,
                        "potencia_en_rejilla": {f"{_r(100 * bb * sd_y, 1)}pp": _r(p, 2) for bb, p in zip(b, pot)}}
        if h > 1 and mde is not None:
            out[f"m{m}"]["pendiente_implicita_h_pp_por_dt"] = _r(100 * mde * sd_y * (1 - phi ** h) / (1 - phi), 1)
    return out


def main() -> None:
    borrador = "--prueba" in sys.argv
    warnings.filterwarnings("ignore", category=RuntimeWarning)       # nanmean de años sin filas
    proc = procedencia(exigir_limpio=not borrador)
    nsim = 200 if borrador else NSIM                                  # la prueba solo comprueba que corre
    rng = np.random.default_rng(SEED)
    con = D.connect()
    a = P.anual(con)
    a = a[a.index.get_level_values(1) <= 2004]
    nuc = a[a.index.get_level_values(0).isin(NUCLEO)].copy()
    res: dict = {"procedencia": proc, "nucleo": NUCLEO, "z": {k: _r(v) for k, v in Z.items()},
                 "deltas_supuestos": list(DELTAS), "nsim": nsim, "semilla": SEED}

    # ---------- hiperinflación: país-años con inflación > 50 % en t o en t+1 (regla de INT-3b/INT-6; mira solo el IPC)
    inf = nuc["inflacion"].abs()
    hip = (inf > HIPER) | (inf.groupby(level=0).shift(-1) > HIPER)

    # ---------- indicador: log D/P (JST), solo sus estadísticos
    dp = nuc["eq_dp"]
    res["calidad_dp"] = {"filas_con_dato": int(dp.notna().sum()), "filas_dp_no_positivo": int((dp <= 0).sum()),
                         "por_pais_desde_hasta": {c: [int(dp.xs(c).dropna().index.min()), int(dp.xs(c).dropna().index.max())]
                                                  for c in NUCLEO if dp.xs(c).notna().any()}}
    x = np.log(dp.where(dp > 0)).where(~hip)
    sx = st_panel(x)
    x_rel = dos_vias(x)
    sx_rel = st_panel(x_rel)
    res["log_dp_stats"] = {k: (_r(v) if not isinstance(v, dict) else v) for k, v in sx.items()}
    res["log_dp_relativo_stats (sin efectos de país ni de año)"] = {k: (_r(v) if not isinstance(v, dict) else v)
                                                                   for k, v in sx_rel.items()}
    res["log_dp_dt_relativa_sobre_total"] = _r(sx_rel["sd"] / sx["sd"])

    # ---------- resultados: bolsa real en log, 1 y 5 años (solo sus estadísticos)
    y1 = np.log1p(nuc["eq_tr_real"]).where(~hip)
    sy1 = st_panel(y1)
    y1_rel = dos_vias(y1)
    sy1_rel = st_panel(y1_rel)
    w1 = ancho(y1)
    y5 = (w1.shift(-1).rolling(5, min_periods=5).sum().shift(-4)).stack().rename("y5")   # fila t: t+1 … t+5
    y5.index = y5.index.swaplevel().set_names(["pais", "año"])
    y5 = y5.sort_index()
    sy5 = st_panel(y5)
    res["bolsa_real_1a_stats"] = {k: (_r(v) if not isinstance(v, dict) else v) for k, v in sy1.items()}
    res["bolsa_real_1a_relativa_stats"] = {k: (_r(v) if not isinstance(v, dict) else v) for k, v in sy1_rel.items()}
    res["bolsa_real_5a_stats (suma de logs t+1…t+5; solapada)"] = {k: (_r(v) if not isinstance(v, dict) else v)
                                                                   for k, v in sy5.items()}

    # ---------- disponibilidad (filas, nunca valores cruzados)
    y1_adel = ancho(y1).shift(-1).stack()
    y1_adel.index = y1_adel.index.swaplevel().set_names(["pais", "año"])
    disp1 = x.dropna().index.intersection(y1_adel.dropna().index)
    disp5 = x.dropna().index.intersection(y5.dropna().index)
    d50 = disp1[disp1.get_level_values(1) >= 1950]
    guerras = set(range(1914, 1919)) | set(range(1939, 1946))
    sin_g = disp1[[t not in guerras and t + 1 not in guerras for t in disp1.get_level_values(1)]]

    V = {}
    V["V1_dp_bolsa_1a"] = {"analitico_1871_2004": mde_analitico(disp1, sx, sy1),
                           "analitico_1950_2004": mde_analitico(d50, sx, sy1),
                           "analitico_sin_guerras": mde_analitico(sin_g, sx, sy1)}
    V["V2_dp_relativo_bolsa_1a (efectos de año)"] = {
        "analitico_1871_2004 (dt_y relativa; rho ≈ 0 tras quitar el año)": mde_analitico(disp1, sx_rel, sy1_rel,
                                                                                          rho_override=0.0)}
    V["V3_dp_bolsa_5a"] = {"filas": int(len(disp5)), "nota": "el analítico no aplica (solape); ver simulación"}

    # ---------- estanflación: solo recuentos con disponibilidad (V5, interacción)
    et = pd.read_parquet(db.DATA_ROOT / "intl" / "regimen_anual_dev.parquet")
    et = et[et.pais.isin(NUCLEO) & et.cuadrante.notna() & ~et.truncada.fillna(True).astype(bool)]
    est = pd.Series((et.cuadrante == "estanflacion").astype(int).values,
                    index=pd.MultiIndex.from_arrays([et.pais.values, et.año.astype(int).values], names=["pais", "año"]))
    e_disp = est.reindex(disp1).dropna()
    n1, n0 = int((e_disp == 1).sum()), int((e_disp == 0).sum())
    idx1, idx0 = e_disp.index[e_disp == 1], e_disp.index[e_disp == 0]

    def nef(idx):
        mk = m_kish(idx.get_level_values(1))
        return len(idx) / (1 + (mk - 1) * max(sx["rho_paises"] * sy1["rho_paises"], 0)) * \
            (1 - sx["ar1"] * sy1["ar1"]) / (1 + sx["ar1"] * sy1["ar1"])
    # diferencia de pendientes (pp por dt de x) entre estanflación y resto; dt de x dentro de cada grupo ≈ la total
    # (supuesto prudente a favor de la potencia: dentro de un estado la dt de x suele ser menor)
    V["V5_interaccion_estanflacion"] = {
        "pais_años_estanflacion_con_fila": n1, "pais_años_resto": n0, "años_distintos_estanflacion":
            int(idx1.get_level_values(1).nunique()),
        **{f"mde_dif_pendientes_pp_por_dt_z{k}": _r(100 * z * sy1["sd"] * np.sqrt(1 / nef(idx1) + 1 / nef(idx0)), 2)
           for k, z in Z.items()}}

    # ---------- simulación de los paneles (V1, V2, V3) con la disponibilidad real
    def mascara(disp: pd.Index) -> np.ndarray:
        años = range(1870, 2005)
        s = set(disp)
        return np.array([[(c, t) in s for c in NUCLEO] for t in años])

    bgrid = np.r_[0.0, np.linspace(0.02, 0.40, 39)]          # b en dt_y por dt de x (1 año)
    sims = {}
    for nom, disp, h, rel, sxx, syy in (("V1_dp_bolsa_1a", disp1, 1, False, sx, sy1),
                                        ("V2_dp_relativo_bolsa_1a (efectos de año)", disp1, 1, True, sx, sy1),
                                        ("V3_dp_bolsa_5a", disp5, 5, False, sx, sy1)):
        mk = mascara(disp)
        for d in DELTAS:
            sim = simular(mk, sxx["ar1"], max(sxx["rho_paises"], 0), max(syy["rho_paises"], 0), 1.0, d, h, rel, bgrid,
                          nsim, rng)
            r = resumen_sim(sim, bgrid, +1, syy["sd"], sxx["ar1"], h)
            if rel:   # en V2 la pendiente se lee también por 1 dt del D/P RELATIVO
                for m in MS:
                    v = r[f"m{m}"]["mde_pp_por_dt_1año"]
                    if isinstance(v, float):
                        r[f"m{m}"]["mde_pp_por_dt_relativa"] = _r(v * sx_rel["sd"] / sx["sd"], 2)
            r["sesgo_kendall_aprox_pp_por_dt"] = _r(sesgo_kendall(sxx["ar1"], mk.sum(0)[mk.sum(0) > 0].mean(), d,
                                                                  syy["sd"]), 2)
            sims.setdefault(nom, {})[f"delta={d}"] = r
        V[nom]["simulado"] = sims[nom]

    # ---------- EE. UU.: CAPE de Shiller (anual, diciembre) y bolsa real de Shiller; cada serie por separado
    cape = leer_no_permitida(con, "shiller_cape")
    rm = leer_no_permitida(con, "shiller_real_stock_tr_ret_m")
    lc_m = np.log(cape)
    lc = lc_m[lc_m.index.month == 12]
    lc.index = lc.index.year
    yr = np.log1p(rm).groupby(rm.index.year).agg(["sum", "count"])
    yr = yr.loc[yr["count"] == 12, "sum"]                     # año natural completo
    res["usa_cape"] = {"desde": int(lc.index.min()), "hasta": int(lc.index.max()), "dt_log": _r(lc.std()),
                       "ar1_anual": _r(lc.autocorr(1)), "ar1_mensual": _r(lc_m.autocorr(1), 4),
                       "ar1_anual_1950_2004": _r(lc[lc.index >= 1950].autocorr(1))}
    res["usa_bolsa_real_shiller"] = {"desde": int(yr.index.min()), "hasta": int(yr.index.max()), "dt_1a": _r(yr.std()),
                                     "ar1_1a": _r(yr.autocorr(1)),
                                     "dt_10a_solapada": _r(yr.rolling(10).sum().std())}
    dpu = x.xs("USA").dropna()
    res["usa_log_dp_jst"] = {"dt": _r(dpu.std()), "ar1": _r(dpu.autocorr(1)), "años": int(dpu.size)}
    phi_c, sd_yu = float(lc.autocorr(1)), float(yr.std())
    V4 = {}
    for h in (1, 10):
        filas = [t for t in lc.index if all((t + j) in yr.index for j in range(1, h + 1))]
        mk = np.zeros((2005 - 1870, 1), bool)
        for t in filas:
            mk[t - 1870, 0] = True
        V4[f"h{h}"] = {"filas": len(filas), "desde": min(filas), "hasta": max(filas),
                       "observaciones_no_solapadas": len(filas) // h}
        for d in DELTAS:
            sim = simular(mk, phi_c, 0.0, 0.0, 1.0, d, h, False, bgrid, nsim, rng)
            # x = −log CAPE (rendimiento de beneficios en log): signo esperado +, y δ < 0 como en D/P
            r = resumen_sim(sim, bgrid, +1, sd_yu, phi_c, h)
            r["sesgo_kendall_aprox_pp_por_dt"] = _r(sesgo_kendall(phi_c, len(filas), d, sd_yu), 2)
            V4[f"h{h}"][f"delta={d}"] = r
    V["V4_cape_usa"] = V4
    res["preguntas"] = V
    con.close()
    if not borrador:
        (REPO / "research" / "int" / "int7_potencia.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
