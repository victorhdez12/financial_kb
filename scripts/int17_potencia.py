"""INT-17 (borrador v0): beneficios NIPA → entrada en recesión NBER a 12 meses, incremental sobre E1. POTENCIA antes de
construir (docs/int/INT17_beneficios_prerregistro_v0.md). Datos reales solo ≤ 2004; NADA ≥ 2005 se lee.

Qué usa (y nada más), en partes que NUNCA se juntan:
  (i)   DATOS (sin la etiqueta): cobertura de CPATAX/GDPDEF/GDP y de las 4 variables de E1 para EE. UU.; retraso real de
        la primera publicación de CPATAX en ALFRED (1981-2004); tamaño de las revisiones del interanual real (primera
        publicación frente a la última añada); persistencia de `prof_yoy` (trimestral) y del índice E1 (mensual), cada
        uno por separado. Ningún rasgo se cruza con USREC.
  (ii)  ESTRUCTURA DE EVENTOS (solo la etiqueta USREC ≤ 2004): entradas, filas en riesgo, positivos, calendario del
        walk-forward (primer año de evaluación por regla).
  (iii) POTENCIA: estructura REAL de (ii) y rasgos SIMULADOS: x1 = índice E1 (a·y + u, u AR(1) mensual), x2 = beneficios
        (b_e·y + λ·x1 + w; w AR(1) trimestral mantenido 3 meses; λ = colinealidad con E1 sin información nueva;
        b_e = b + τ·N(0,1) por entrada). Walk-forward IGUAL que el diseño (§5): logit re-estimado cada enero, ventana
        creciente, embargo 24 m (12 del horizonte + 12 del anuncio NBER). Estadístico D = LL(L) − LL(A) (nats/fila).
        Valor crítico = cuantil de la nula simulada (b = 0) al 5 % y 2,5 % (Holm-2); aparte, bootstrap por bloques.

Uso: .venv/bin/python -m scripts.int17_potencia            (con puerta: árbol limpio; escribe el JSON)
     .venv/bin/python -m scripts.int17_potencia --prueba   (sin puerta; no escribe nada; pocas réplicas)
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research" / "int" / "int17_potencia.json"
CORTE = pd.Timestamp("2004-12-31")
H = 12                                  # horizonte (meses)
EMBARGO = 24                            # 12 del horizonte + 12 del anuncio NBER (prudente)
FIT_DESDE = pd.Period("1955-08", "M")   # primer mes con las 4 variables de E1 para EE. UU.
ULTIMO_ORIGEN = pd.Period("2003-12", "M")
MIN_ENTRADAS_AJUSTE = 2
ALFRED_DESDE = pd.Timestamp("1981-01-31")   # primer fin de mes con añada ALFRED de CPATAX (1980-12-23)
MESES_RETRASO_PRE1981 = 4               # trimestre usable desde el fin del 4.º mes tras su fin (regla §3)
BLOQUE = 24
RECORTE = 0.01
SEMILLA = 20261118
E1_SHA = "227ffa8c903cd19fa3c66f998b67e45dce78e8d93581fa22a4e52d1b4ede532e"


def _r(x, k=4):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), k)


# ================================================================ rasgos "as of" (para la corrida y la descripción)
def disponible_regla(trimestres: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Fin del 4.º mes tras el fin del trimestre (T1 1960 → 1960-07-31)."""
    return trimestres + pd.offsets.QuarterEnd(0) + pd.offsets.MonthEnd(MESES_RETRASO_PRE1981)


def _yoy_real(prof: pd.Series, defl: pd.Series) -> pd.Series:
    x = np.log(prof / defl.reindex(prof.index))
    return x - x.shift(4)


def prof_yoy_ultima(prof: pd.Series, defl: pd.Series, rej: pd.DatetimeIndex) -> pd.Series:
    """`prof_yoy` con la última añada y la regla del retraso (antes de ALFRED): valor del último trimestre usable."""
    q = _yoy_real(prof, defl).dropna()
    obs = pd.DataFrame({"disp": disponible_regla(q.index), "v": q.values}).sort_values("disp")
    m = pd.merge_asof(pd.DataFrame({"t": rej}), obs, left_on="t", right_on="disp")
    return pd.Series(m["v"].values, index=rej)


def prof_yoy_alfred(vint: pd.DataFrame, defl: pd.Series, t: pd.Timestamp) -> float:
    """`prof_yoy` con la añada vigente en t (CPATAX de ALFRED; deflactor de la última añada, §3)."""
    m = (vint["realtime_start"] <= t) & (vint["realtime_end"].isna() | (vint["realtime_end"] >= t))
    s = (vint.loc[m].sort_values(["date", "realtime_start"]).drop_duplicates("date", keep="last")
         .set_index("date")["value"].dropna().sort_index())
    if len(s) < 5:
        return float("nan")
    q = _yoy_real(s, defl).dropna()
    return float(q.iloc[-1]) if len(q) else float("nan")


def prof_yoy_asof(prof: pd.Series, defl: pd.Series, vint: pd.DataFrame, rej: pd.DatetimeIndex) -> pd.Series:
    """Principal: ALFRED desde 1981-01; antes, última añada con la regla. Nada posterior al fin de cada mes."""
    out = prof_yoy_ultima(prof, defl, rej)
    for t in rej[rej >= ALFRED_DESDE]:
        out.loc[t] = prof_yoy_alfred(vint, defl, t)
    return out


def margen_caida8(prof: pd.Series, gdp: pd.Series) -> pd.Series:
    """S1 (trimestral, por fecha de observación): log(margen) − máximo de los últimos 8 trimestres (≤ 0)."""
    m = np.log(prof / gdp.reindex(prof.index))
    return m - m.rolling(8, min_periods=8).max()


# ================================================================ (i) datos (sin la etiqueta)
def describir_datos(con) -> dict:
    from src.intl import e1 as E1
    from src.intl.data import load_dev
    out = {"cobertura": {}}
    for s in ("CPATAX", "GDPDEF", "GDP", "oecd_irlt_usa", "bis_cbpol_us", "oecd_ip_usa", "oecd_bci_usa", "USREC"):
        x = load_dev(con, s)
        out["cobertura"][s] = {"desde": str(x.index.min().date()), "hasta": str(x.index.max().date()), "n_le_2004": len(x)}
    prof, defl, gdp = load_dev(con, "CPATAX"), load_dev(con, "GDPDEF"), load_dev(con, "GDP")

    # ALFRED: retraso de la primera publicación y revisiones (solo trimestres ≤ 2004, añadas ≤ 2004 para el retraso)
    from src.ingest.alfred_vintages import load_vintages
    v = load_vintages("CPATAX")
    v = v[v["date"] <= CORTE]
    primera = v.dropna(subset=["value"]).groupby("date")["realtime_start"].min()
    primera = primera[primera > pd.Timestamp("1980-12-23")]              # antes de la 1.ª añada no hay fecha real
    lag = pd.Series((primera.values - (primera.index + pd.offsets.QuarterEnd(0))).days, index=primera.index)
    out["retraso_alfred"] = {
        "primera_anada": str(v["realtime_start"].min().date()), "n_anadas_le_2004": int(v.loc[v["realtime_start"] <= CORTE, "realtime_start"].nunique()),
        "trimestres": int(len(lag)), "dias_min": int(lag.min()), "dias_mediana": float(lag.median()),
        "dias_p90": float(lag.quantile(0.9)), "dias_max": int(lag.max()),
        "por_trimestre": {f"T{k}": {"mediana": float(g.median()), "max": int(g.max())}
                          for k, g in lag.groupby(lag.index.quarter)},
        "cubre_regla_4_meses": bool((lag <= 120).all()),
        "regla_dias_aprox": "T1 → 122, T2 → 123, T3 → 123, T4 → 120 días",
    }
    # revisión del interanual real: primera publicación del trimestre q frente a la última añada (≤ 2004)
    rev = []
    for q in primera.index:
        if q < pd.Timestamp("1982-01-01"):
            continue
        t = primera.loc[q]
        m = (v["realtime_start"] <= t) & (v["realtime_end"].isna() | (v["realtime_end"] >= t))
        s = v.loc[m].sort_values(["date", "realtime_start"]).drop_duplicates("date", keep="last").set_index("date")["value"]
        if q in s.index and (q - pd.DateOffset(months=12)) in s.index:
            q4 = q - pd.DateOffset(months=12)
            y0 = np.log(s[q] / defl[q]) - np.log(s[q4] / defl[q4])
            y1 = np.log(prof[q] / defl[q]) - np.log(prof[q4] / defl[q4])
            rev.append((y0, y1))
    rev = np.array(rev)
    yl = _yoy_real(prof, defl).dropna()
    out["revisiones_prof_yoy_1982_2004"] = {
        "n": int(len(rev)), "sd_primera": _r(rev[:, 0].std(ddof=1)), "sd_ultima": _r(rev[:, 1].std(ddof=1)),
        "sd_revision": _r((rev[:, 1] - rev[:, 0]).std(ddof=1)), "corr_primera_ultima": _r(np.corrcoef(rev.T)[0, 1]),
        "nota": "interanual real (log), deflactor de la última añada en los dos; revisión = última − primera"}
    # persistencia de cada rasgo POR SEPARADO (sin la etiqueta)
    def ar1(x):
        x = np.asarray(x, float)
        x = x[np.isfinite(x)]
        return _r(np.corrcoef(x[1:], x[:-1])[0, 1])
    yq = yl[yl.index >= "1948-01-01"]
    mc = margen_caida8(prof, gdp).dropna()
    out["persistencia"] = {"prof_yoy_trimestral_ar1": ar1(yq.values), "prof_yoy_sd": _r(yq.std()),
                           "margen_caida8_trimestral_ar1": ar1(mc.values), "margen_caida8_media": _r(mc.mean())}
    # índice E1 para EE. UU. (coeficientes congelados; sin la etiqueta)
    mod = json.loads((REPO / "research" / "int" / "e1_modelos.json").read_text())
    if mod["modelos_sha256"] != E1_SHA or E1.sha(mod["modelos"]) != E1_SHA:
        raise SystemExit("e1_modelos.json no coincide con el sha256 congelado")
    rej = pd.date_range("1950-01-31", CORTE, freq="ME")
    r = E1.rasgos(lambda sid: load_dev(con, sid), rej, paises=["USA"])
    a = mod["modelos"]["A"]
    ok = r[a["cols"]].notna().all(axis=1)
    X = (r.loc[ok, a["cols"]].to_numpy(float) - np.array(a["media"])) / np.array(a["dt"])
    s = pd.Series(a["b"][0] + X @ np.array(a["b"][1:]), index=r.loc[ok, "fecha"].values)
    out["indice_E1_usa"] = {"desde": str(pd.Timestamp(s.index.min()).date()), "hasta": str(pd.Timestamp(s.index.max()).date()),
                            "meses": int(len(s)), "ar1_mensual": ar1(s.values), "sd": _r(s.std())}
    # cobertura de prof_yoy "as of" en la rejilla de la muestra
    rj = pd.date_range(FIT_DESDE.to_timestamp(how="end").normalize(), ULTIMO_ORIGEN.to_timestamp(how="end").normalize(),
                       freq="ME")
    pa = prof_yoy_asof(prof, defl, v, rj)
    pu = prof_yoy_ultima(prof, defl, rj)
    m81 = rj >= ALFRED_DESDE
    out["prof_yoy_asof"] = {"meses": int(len(rj)), "con_dato": int(pa.notna().sum()),
                            "meses_alfred": int(m81.sum()),
                            "corr_alfred_vs_ultima_1981_2003": _r(np.corrcoef(pa[m81], pu[m81])[0, 1]),
                            "nota": "comparación de dos versiones del MISMO rasgo; ninguna etiqueta"}
    return out


# ================================================================ (ii) estructura de eventos (solo USREC)
def entradas_nber(usrec: pd.Series) -> list[pd.Period]:
    u = usrec.copy()
    u.index = u.index.to_period("M")
    u = u.astype(int)
    return [m for m, prev, cur in zip(u.index[1:], u.values[:-1], u.values[1:]) if prev == 0 and cur == 1]


def filas_objetivo(usrec: pd.Series, desde=FIT_DESDE, hasta=ULTIMO_ORIGEN) -> pd.DataFrame:
    """Una fila por mes M en [desde, hasta]: en_riesgo = USREC(M) = 0; y = 1 si hay entrada en (M, M + 12];
    ent = índice de la entrada de la ventana (−1 si no)."""
    u = usrec.copy()
    u.index = u.index.to_period("M")
    ent = entradas_nber(usrec)
    filas = []
    for m in pd.period_range(desde, hasta, freq="M"):
        k = [i for i, e in enumerate(ent) if m < e <= m + H]
        filas.append({"mes": m, "en_riesgo": int(u.loc[m]) == 0, "y": int(bool(k)), "ent": k[0] if k else -1})
    return pd.DataFrame(filas), ent


def calendario(df: pd.DataFrame) -> list[tuple[int, np.ndarray, np.ndarray]]:
    """[(año, filas de ajuste, filas a predecir)] desde el primer enero con ≥ MIN_ENTRADAS_AJUSTE entradas distintas en
    las filas de ajuste (fila M usable en el enero del año Y si M + EMBARGO ≤ Y-01)."""
    d = df[df.en_riesgo].reset_index(drop=True)
    t = np.array([(m - FIT_DESDE).n for m in d.mes])
    out = []
    for anio in range(FIT_DESDE.year + 1, ULTIMO_ORIGEN.year + 1):
        p0 = (pd.Period(f"{anio}-01", "M") - FIT_DESDE).n
        fit = np.where(t + EMBARGO <= p0)[0]
        if len(set(d.ent.values[fit][d.y.values[fit] == 1])) < MIN_ENTRADAS_AJUSTE and not out:
            continue
        pred = np.where((t >= p0) & (t < p0 + 12))[0]
        if len(pred):
            out.append((anio, fit, pred))
    return out


def resumen_eventos(df: pd.DataFrame, ent: list) -> dict:
    cal = calendario(df)
    d = df[df.en_riesgo].reset_index(drop=True)
    ev = np.concatenate([c[2] for c in cal])
    ent_ev = sorted({int(e) for e in d.ent.values[ev] if e >= 0})
    return {"entradas_nber_1955_2004": [str(e) for e in ent if FIT_DESDE < e <= pd.Period("2004-12", "M")],
            "muestra": {"meses": int(len(df)), "en_riesgo": int(len(d)), "positivos": int(d.y.sum())},
            "evaluacion": {"primer_anio": cal[0][0], "filas": int(len(ev)), "positivos": int(d.y.values[ev].sum()),
                           "tasa": _r(d.y.values[ev].mean()), "entradas": [str(ent[i]) for i in ent_ev],
                           "n_entradas": len(ent_ev)},
            "embargo_meses": EMBARGO}


# ================================================================ (iii) potencia
def auc(s: np.ndarray, y: np.ndarray) -> float:
    n1 = y.sum()
    n0 = len(y) - n1
    rk = rankdata(s)
    return float((rk[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def logit(X: np.ndarray, y: np.ndarray, b0: np.ndarray | None = None) -> np.ndarray:
    """El ajuste del diseño (§5): `src/intl/int4.logit_fit` (Newton con búsqueda lineal, sin penalizar). `b0` se ignora
    (se mantiene la firma)."""
    from src.intl.int4 import logit_fit
    return logit_fit(X, y)


def _p(b, X):
    return 1 / (1 + np.exp(-np.clip(b[0] + X @ b[1:], -30, 30)))


def ll_filas(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def ar1(rng, n: int, phi: float) -> np.ndarray:
    e = rng.standard_normal(n) * np.sqrt(1 - phi ** 2)
    x = np.empty(n)
    x[0] = rng.standard_normal()
    for t in range(1, n):
        x[t] = phi * x[t - 1] + e[t]
    return x


def boot_inferior(d: np.ndarray, rng, B: int = 300, bloque: int = BLOQUE, q: float = 0.05) -> float:
    """Cuantil q de la media de d por bootstrap de bloques móviles (bloques de `bloque` filas consecutivas)."""
    n = len(d)
    nb = int(np.ceil(n / bloque))
    ini = rng.integers(0, n - bloque + 1, size=(B, nb))
    idx = (ini[:, :, None] + np.arange(bloque)[None, None, :]).reshape(B, -1)[:, :n]
    return float(np.quantile(d[idx].mean(1), q))


class Estructura:
    """Filas en riesgo reales y calendario walk-forward del diseño (§5)."""

    def __init__(self, df: pd.DataFrame):
        d = df[df.en_riesgo].reset_index(drop=True)
        self.t = np.array([(m - FIT_DESDE).n for m in d.mes])
        self.nt = int(self.t.max()) + 1
        self.y = d.y.values.astype(float)
        self.ent = d.ent.values
        self.n_ent = int(max(self.ent.max() + 1, 1))
        self.bloques = [(f, p) for _, f, p in calendario(df)]
        self.ev = np.concatenate([b[1] for b in self.bloques])
        self.anio_ev = np.concatenate([np.full(len(p), a) for a, _, p in calendario(df)])

    def simular(self, rng, a: float, b: float, tau: float, lam: float, phi_u: float, phi_q: float):
        u = ar1(rng, self.nt, phi_u)[self.t]
        wq = ar1(rng, self.nt // 3 + 2, phi_q)
        w = wq[self.t // 3]
        be = b + tau * rng.standard_normal(self.n_ent)
        x1 = a * self.y + u
        x2 = np.where(self.y == 1, be[np.maximum(self.ent, 0)], 0.0) + lam * x1 + w
        return x1, x2

    def evaluar(self, x1: np.ndarray, x2: np.ndarray, rng=None, boot: int = 0) -> dict:
        n = len(self.y)
        pL, pA, p0, iA = (np.full(n, np.nan) for _ in range(4))
        bl = ba = None
        for fit, pred in self.bloques:
            yf = self.y[fit]
            X1, X2 = np.column_stack([x1]), np.column_stack([x1, x2])
            bl = logit(X1[fit], yf, bl)
            ba = logit(X2[fit], yf, ba)
            pL[pred], pA[pred] = _p(bl, X1[pred]), _p(ba, X2[pred])
            p0[pred] = max(yf.mean(), 1e-4)
            iA[pred] = x1[pred] + (ba[2] / ba[1]) * x2[pred] if ba[1] > 1e-6 else ba[1] * x1[pred] + ba[2] * x2[pred]
        e = self.ev
        y = self.y[e]
        lL, lA, l0 = ll_filas(pL[e], y), ll_filas(pA[e], y), ll_filas(p0[e], y)
        d = lL - lA
        out = {"D": float(d.mean()), "dBrier": float(((pA[e] - y) ** 2 - (pL[e] - y) ** 2).mean()),
               "dAUC_indice": auc(iA[e], y) - auc(x1[e], y), "D_L_vs_P0": float((l0 - lL).mean()),
               "auc_L": auc(x1[e], y)}
        # sensibilidad declarada (no es el principal): probabilidades recortadas a [0,01; 0,99] (la simulación muestra
        # que, con 2-3 entradas en el ajuste de los primeros años, el logit sin penalizar da probabilidades extremas)
        r = lambda p: np.clip(p, RECORTE, 1 - RECORTE)  # noqa: E731
        out["D_rec"] = float((ll_filas(r(pL[e]), y) - ll_filas(r(pA[e]), y)).mean())
        h1 = self.anio_ev < 1980
        out["D_mitad1"], out["D_mitad2"] = float(d[h1].mean()), float(d[~h1].mean())
        if boot and rng is not None:
            out["boot_inf5"] = boot_inferior(d, rng, boot, q=0.05)
            out["boot_inf2_5"] = boot_inferior(d, rng, boot, q=0.025)
        return out


def delta_poblacional(a: float, b: float) -> float:
    """ΔAUC del oráculo: binormal, la parte nueva de x2 (b·y + w) independiente de x1 y de varianza 1."""
    return float(norm.cdf(np.sqrt(a ** 2 + b ** 2) / np.sqrt(2)) - norm.cdf(a / np.sqrt(2)))


def b_para_delta(a: float, d: float) -> float:
    lo, hi = 0.0, 6.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if delta_poblacional(a, mid) < d else (lo, mid)
    return (lo + hi) / 2


def lam_para_corr(a: float, pi: float, rho: float) -> float:
    """λ tal que corr(x1, λ·x1 + w) = rho sin señal (var x1 = 1 + a²·π(1 − π), var w = 1)."""
    if rho <= 0:
        return 0.0
    sd1 = np.sqrt(1 + a ** 2 * pi * (1 - pi))
    return float(rho / (np.sqrt(1 - rho ** 2) * sd1))


def mde(filas: list, clave: str, x: str = "delta_poblacional", objetivo: float = 0.8):
    xs, ps = [f[x] for f in filas], [f[clave] for f in filas]
    if ps[0] >= objetivo:
        return _r(xs[0])
    for i in range(1, len(xs)):
        if ps[i - 1] < objetivo <= ps[i]:
            return _r(xs[i - 1] + (objetivo - ps[i - 1]) * (xs[i] - xs[i - 1]) / (ps[i] - ps[i - 1]))
    return None


def _reps(args) -> np.ndarray:
    est, seed, reps, a, b, tau, lam, phi_u, phi_q, boot = args
    rng = np.random.default_rng(seed)
    claves = ["D", "dBrier", "dAUC_indice", "D_L_vs_P0", "auc_L", "D_mitad1", "D_mitad2", "boot_inf5", "boot_inf2_5",
              "D_rec"]
    res = []
    for _ in range(reps):
        x1, x2 = est.simular(rng, a, b, tau, lam, phi_u, phi_q)
        o = est.evaluar(x1, x2, rng, boot)
        res.append([o.get(k, np.nan) for k in claves])
    return np.array(res)


COLS = {"D": 0, "dBrier": 1, "dAUC_indice": 2, "D_L_vs_P0": 3, "auc_L": 4, "D_mitad1": 5, "D_mitad2": 6,
        "boot_inf5": 7, "boot_inf2_5": 8, "D_rec": 9}


def escenario(est: Estructura, auc_l: float, tau: float, rho: float, phi_u: float, phi_q: float, deltas, reps: int,
              seed: int, boot: int, pool=None) -> dict:
    a = np.sqrt(2) * norm.ppf(auc_l)
    deltas = [d for d in deltas if auc_l + d < 0.995]            # el oráculo no puede pasar de AUC 1
    lam = lam_para_corr(a, est.y.mean(), rho)
    bs = [0.0] + [b_para_delta(a, d) for d in deltas]
    trozos = 4
    tareas = [(est, seed + 1000 * i + j, reps // trozos, a, b, tau if b > 0 else 0.0, lam, phi_u, phi_q, boot)
              for i, b in enumerate(bs) for j in range(trozos)]
    sal = list(pool.map(_reps, tareas)) if pool else [_reps(t) for t in tareas]
    sims = [np.vstack(sal[i * trozos:(i + 1) * trozos]) for i in range(len(bs))]
    nula = sims[0]
    c05, c025 = np.quantile(nula[:, 0], 0.95), np.quantile(nula[:, 0], 0.975)
    cr05, ci05 = np.quantile(nula[:, 9], 0.95), np.quantile(nula[:, 2], 0.95)
    filas = []
    for d, b, s in zip(deltas, bs[1:], sims[1:]):
        D = s[:, 0]
        filas.append({
            "delta_poblacional": d, "b": _r(b), "D_medio_nats": _r(D.mean(), 5), "sd_D": _r(D.std(ddof=1), 5),
            "dBrier_medio": _r(s[:, 1].mean(), 5), "dAUC_indice_medio": _r(s[:, 2].mean()),
            "potencia_5": _r((D > c05).mean(), 3), "potencia_2_5": _r((D > c025).mean(), 3),
            "potencia_boot_5": _r((s[:, 7] > 0).mean(), 3), "potencia_boot_2_5": _r((s[:, 8] > 0).mean(), 3),
            "p_D_pos": _r((D > 0).mean(), 3), "D_rec_medio": _r(s[:, 9].mean(), 5),
            "potencia_rec_5": _r((s[:, 9] > cr05).mean(), 3), "potencia_dAUC_indice_5": _r((s[:, 2] > ci05).mean(), 3),
            "p_paquete_establecido_5": _r(((D > c05) & (s[:, 1] < 0) & (s[:, 5] > 0) & (s[:, 6] > 0)).mean(), 3),
        })
    return {"auc_liston": auc_l, "a": _r(a), "tau": tau, "rho_e1": rho, "lambda": _r(lam), "phi_u": phi_u,
            "phi_q": phi_q, "reps": int(len(nula)),
            "nula": {"D_medio": _r(nula[:, 0].mean(), 5), "sd_D": _r(nula[:, 0].std(ddof=1), 5),
                     "critico_5": _r(c05, 5), "critico_2_5": _r(c025, 5), "p_D_pos": _r((nula[:, 0] > 0).mean(), 3),
                     "tam_boot_5": _r((nula[:, 7] > 0).mean(), 3), "tam_boot_2_5": _r((nula[:, 8] > 0).mean(), 3),
                     "auc_L_realizado": _r(nula[:, 4].mean()), "D_L_vs_P0_medio": _r(nula[:, 3].mean(), 5),
                     "p_L_peor_que_P0": _r((nula[:, 3] < 0).mean(), 3), "D_rec_medio": _r(nula[:, 9].mean(), 5),
                     "critico_rec_5": _r(cr05, 5), "dAUC_indice_medio": _r(nula[:, 2].mean()), "critico_dAUC_5": _r(ci05)},
            "filas": filas, "mde_80_5": mde(filas, "potencia_5"), "mde_80_2_5": mde(filas, "potencia_2_5"),
            "mde_80_boot_5": mde(filas, "potencia_boot_5"), "mde_80_rec_5": mde(filas, "potencia_rec_5"),
            "mde_80_dAUC_indice_5": mde(filas, "potencia_dAUC_indice_5"),
            "potencia_realista_0_04": next(f["potencia_5"] for f in filas if f["delta_poblacional"] == 0.04),
            "potencia_realista_0_04_holm": next(f["potencia_2_5"] for f in filas if f["delta_poblacional"] == 0.04),
            "potencia_optimista_0_08": next(f["potencia_5"] for f in filas if f["delta_poblacional"] == 0.08)}


# ================================================================ main
def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    prueba = "--prueba" in argv
    reps = 40 if prueba else 800
    boot = 100 if prueba else 300
    from src.intl.data import connect, load_dev
    from src.intl.procedencia import procedencia
    if not prueba and SALIDA.exists():
        raise SystemExit(f"{SALIDA} ya existe: no se sobrescribe")
    res = {"procedencia": procedencia(exigir_limpio=not prueba), "prueba": prueba, "reps": reps, "boot": boot,
           "semilla": SEMILLA, "documento": "docs/int/INT17_beneficios_prerregistro_v0.md"}
    t0 = time.time()
    con = connect("warehouse")
    res["datos"] = describir_datos(con)
    print(json.dumps(res["datos"], ensure_ascii=False, default=str), flush=True)
    usrec = load_dev(con, "USREC")
    con.close()
    df, ent = filas_objetivo(usrec)
    res["eventos"] = resumen_eventos(df, ent)
    print(json.dumps(res["eventos"], ensure_ascii=False), flush=True)

    est = Estructura(df)
    phi_q = res["datos"]["persistencia"]["prof_yoy_trimestral_ar1"]
    phi_u = 0.95
    deltas = [0.01, 0.02, 0.04, 0.06, 0.08, 0.10, 0.13, 0.16, 0.20]
    esc = {"central": (0.80, 0.25, 0.3), "tau0": (0.80, 0.0, 0.3), "tau0.5": (0.80, 0.5, 0.3),
           "rho0": (0.80, 0.25, 0.0), "rho0.6": (0.80, 0.25, 0.6), "aucL0.70": (0.70, 0.25, 0.3),
           "aucL0.90": (0.90, 0.25, 0.3)}
    if prueba:
        esc = {"central": esc["central"]}
    out = {}
    with ProcessPoolExecutor(max_workers=12) as pool:
        for i, (k, (al, tau, rho)) in enumerate(esc.items()):
            out[k] = escenario(est, al, tau, rho, phi_u, phi_q, deltas, reps, SEMILLA + 100000 * i, boot, pool)
            v = out[k]
            print(k, v["nula"], v["mde_80_5"], v["mde_80_2_5"], v["mde_80_boot_5"], v["mde_80_rec_5"],
                  v["mde_80_dAUC_indice_5"],
                  [(f["delta_poblacional"], f["potencia_5"], f["potencia_rec_5"], f["potencia_dAUC_indice_5"],
                    f["D_medio_nats"]) for f in v["filas"]],
                  round(time.time() - t0), flush=True)
    res["potencia"] = out
    res["supuestos"] = {
        "x1": "índice E1 simulado a·y + u, u AR(1) mensual φ 0,95 (como E1); AUC poblacional del listón 0,80 central",
        "x2": "beneficios simulados b_e·y + λ·x1 + w; w AR(1) TRIMESTRAL con φ medido en prof_yoy ≤ 2004, mantenido 3 "
              "meses; λ = colinealidad con E1 (corr sin señal rho); b_e = b + τ·N(0,1) por entrada NBER",
        "walk_forward": "logit re-estimado cada enero, ventana creciente desde 1955-08, embargo 24 m; primer año por regla",
        "efecto": {"realista": 0.04, "optimista": 0.08, "unidad": "ΔAUC poblacional del oráculo; D en nats en las filas"},
        "umbral_potencia": 0.8,
        "no_modelado": "ruido de revisión (el efecto se define sobre el rasgo publicado), retraso (ya en el rasgo real)",
    }
    res["segundos"] = round(time.time() - t0)
    if prueba:
        print("prueba: no se escribe nada")
        return
    SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    print("escrito", SALIDA)


if __name__ == "__main__":
    main()
