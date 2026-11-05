"""INT-15 (borrador v0): "crédito antes que bolsa". POTENCIA antes de construir (docs/int/INT15_credito_prerregistro_v0.md).
Datos reales solo ≤ 2004 (src/intl/data.load_dev); NADA ≥ 2005 se lee.

Qué usa (y nada más), en partes que NUNCA se juntan:
  (i)   INVENTARIO: cobertura de las series candidatas (primera fecha y nº de observaciones ≤ 2004). Ningún valor de
        crédito se lee: ni BAA, ni AAA, ni GS10, ni BAA10Y/AAA10Y.
  (ii)  ESTRUCTURA DE EVENTOS del objetivo (solo la bolsa: AQR MKT USA diario, exceso CRSP, + letra TB3MS/252 para
        acercarse a la rentabilidad total): entradas en mercado bajista (Lunde-Timmermann, −15 % desde el máximo del
        tramo alcista; nuevo tramo alcista tras +15 % desde el mínimo), orígenes en riesgo, positivos, episodios.
        Variantes declaradas (−20 %, caída ≥ 15 % / 20 % desde el origen en 6 m) solo como recuento.
  (iii) POTENCIA O1 (ΔAUC, entrada en bajista a 6 m): con la estructura REAL de eventos (1926-2004) y rasgos SIMULADOS:
        x1 = "HAR" (listón: a·y + u), x2 = "crédito" (b_e·y + w, b_e = b + τ·N(0,1) por entrada → heterogeneidad entre
        episodios), u y w AR(1) mensuales. Walk-forward IGUAL que el diseño: logit re-estimado cada enero desde 1950 con
        las filas cuyo objetivo ya acabó (embargo 6 m); predicción de ese año; ΔAUC apilado 1950-01 … 2004-06.
        Valor crítico = cuantil de la nula simulada (b = 0), unilateral 5 % y 2,5 % (Holm-2).
  (iv)  POTENCIA O2 (QLIKE, volatilidad realizada a 1 m): proceso mensual SIMULADO de log RV (dos componentes AR de la
        literatura, ruido t5, dispersión marginal real de INT-12) + "crédito" c_t AR(1) correlacionado con los choques de
        volatilidad; listón = HAR mensual, candidato = HAR + c_t; MCO con ventana creciente re-estimado cada enero;
        Duan; DM unilateral HAC (NW 6). Valor crítico nominal (1,645 / 1,96) y empírico de la nula.

Uso: .venv/bin/python -m scripts.int15_potencia            (con puerta: árbol limpio; escribe el JSON)
     .venv/bin/python -m scripts.int15_potencia --prueba   (sin puerta; no escribe nada; pocas réplicas)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, rankdata

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research" / "int" / "int15_potencia.json"
CORTE = pd.Timestamp("2004-12-31")
H = 6                                   # horizonte del objetivo O1 (meses)
EVAL_DESDE = pd.Period("1950-01", "M")  # como INT-12
FIT_DESDE = pd.Period("1926-10", "M")   # primer origen con 63 días de historia diaria (HAR); crédito desde 1919
SEMILLA = 20261105

CANDIDATAS = {
    "credito_mensual": ["BAA", "AAA", "GS10"],
    "credito_diario": ["DBAA", "DAAA", "BAA10Y", "AAA10Y"],
    "tipos": ["TB3MS", "shiller_gs10"],
    "bolsa": ["aqr_mkt_usa_d", "ff_mkt_rf_m", "shiller_nominal_stock_tr_ret_m"],
    "excluidas_por_diseno": ["BAMLH0A0HYM2", "NFCI"],
}


def _r(x, k=4):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), k)


# ================================================================ (i) inventario (solo cobertura)
def inventario(con) -> dict:
    out = {}
    for rol, ids in CANDIDATAS.items():
        out[rol] = {}
        for s in ids:
            d0, n = con.execute("select min(date), count(*) from obs_latest where series_id = ? and value is not null "
                                "and date <= ?", [s, CORTE.date()]).fetchone()
            out[rol][s] = {"desde": str(d0) if d0 else None, "obs_le_2004": int(n)}
    return out


# ================================================================ (ii) estructura de eventos (solo la bolsa)
def indice_bolsa(con) -> pd.Series:
    """Índice de rentabilidad total aproximada: exceso diario AQR (CRSP) + TB3MS/252 del mes (0 antes de 1934)."""
    from src.intl.data import load_dev
    r = load_dev(con, "aqr_mkt_usa_d") / 100
    tb = load_dev(con, "TB3MS")
    rf = (tb / 100 / 252).reindex(r.index.to_period("M").to_timestamp()).fillna(0.0).values
    return pd.Series(np.cumprod(1 + r.values + rf), index=r.index, name="indice")


def lunde_timmermann(p: pd.Series, baja: float, sube: float) -> tuple[list, pd.Series]:
    """Entradas en bajista (día en que el índice cae `baja` desde el máximo del tramo alcista) y estado diario
    (True = alcista). Solo usa precios ≤ el día: el estado en el origen es "as of"."""
    alc, mx, mn, ent, est = True, p.iloc[0], None, [], np.empty(len(p), bool)
    for i, v in enumerate(p.values):
        if alc:
            mx = max(mx, v)
            if v <= mx * (1 - baja):
                alc, mn = False, v
                ent.append(p.index[i])
        else:
            mn = min(mn, v)
            if v >= mn * (1 + sube):
                alc, mx = True, v
        est[i] = alc
    return ent, pd.Series(est, index=p.index)


def filas_o1(p: pd.Series, baja: float = 0.15, sube: float = 0.15) -> pd.DataFrame:
    """Una fila por origen (último día hábil del mes M): en riesgo = estado alcista en el origen; y = 1 si hay una
    entrada en (origen, origen + 6 meses]; `ent` = índice de la primera entrada de la ventana (para τ)."""
    ent, est = lunde_timmermann(p, baja, sube)
    fin = p.groupby(p.index.to_period("M")).apply(lambda s: s.index[-1])
    ent_ix = pd.DatetimeIndex(ent)
    filas = []
    for m, d in fin.items():
        if m < FIT_DESDE:
            continue
        hasta = d + pd.DateOffset(months=H)
        if hasta > CORTE:
            break
        k = np.where((ent_ix > d) & (ent_ix <= hasta))[0]
        filas.append({"mes": m, "en_riesgo": bool(est.loc[d]), "y": int(len(k) > 0), "ent": int(k[0]) if len(k) else -1})
    return pd.DataFrame(filas), ent


def episodios(fechas: list, gap_meses: int = 12) -> int:
    n, prev = 0, None
    for f in sorted(fechas):
        if prev is None or (f.to_period("M") - prev.to_period("M")).n > gap_meses:
            n += 1
        prev = f
    return n


def resumen_o1(df: pd.DataFrame, ent: list) -> dict:
    out = {}
    for nom, desde in (("ajuste_y_evaluacion_1926-2004", FIT_DESDE), ("evaluacion_1950-2004", EVAL_DESDE)):
        d = df[(df.mes >= desde) & df.en_riesgo]
        e = [x for x in ent if x.to_period("M") >= desde]
        out[nom] = {"origenes": int(((df.mes >= desde)).sum()), "en_riesgo": int(len(d)), "positivos": int(d.y.sum()),
                    "tasa": _r(d.y.mean()), "entradas": len(e), "episodios_gap12": episodios(e),
                    "entradas_por_decada": pd.Series([x.year // 10 * 10 for x in e]).value_counts().sort_index()
                    .to_dict() if e else {}}
    out["fechas_entrada"] = [str(x.date()) for x in ent]
    return out


def recuento_desde_origen(p: pd.Series, umbral: float) -> dict:
    """Variante declarada: caída ≥ umbral desde el nivel del origen en algún día de los 6 meses siguientes."""
    fin = p.groupby(p.index.to_period("M")).apply(lambda s: s.index[-1])
    ys, ms = [], []
    for m, d in fin.items():
        if m < EVAL_DESDE:
            continue
        hasta = d + pd.DateOffset(months=H)
        if hasta > CORTE:
            break
        seg = p[(p.index > d) & (p.index <= hasta)]
        ys.append(int(seg.min() / p.loc[d] - 1 <= -umbral))
        ms.append(m)
    y = pd.Series(ys, index=ms)
    pos = [m.to_timestamp() for m in y.index[y == 1]]
    return {"origenes": int(len(y)), "positivos": int(y.sum()), "tasa": _r(y.mean()), "episodios_gap12": episodios(pos)}


# ================================================================ (iii) potencia O1 (ΔAUC)
def auc(s: np.ndarray, y: np.ndarray) -> float:
    n1 = y.sum()
    n0 = len(y) - n1
    rk = rankdata(s)
    return float((rk[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def logit(X: np.ndarray, y: np.ndarray, b0: np.ndarray | None = None, it: int = 25) -> np.ndarray:
    Xc = np.column_stack([np.ones(len(X)), X])
    b = np.zeros(Xc.shape[1]) if b0 is None else b0.copy()
    if b0 is None:
        b[0] = np.log(max(y.mean(), 1e-4) / max(1 - y.mean(), 1e-4))
    for _ in range(it):
        p = 1 / (1 + np.exp(-np.clip(Xc @ b, -30, 30)))
        W = p * (1 - p) + 1e-9
        paso = np.linalg.solve((Xc * W[:, None]).T @ Xc + 1e-8 * np.eye(len(b)), Xc.T @ (y - p))
        b = b + paso
        if np.max(np.abs(paso)) < 1e-7:
            break
    return b


def ar1(rng, n: int, phi: float) -> np.ndarray:
    e = rng.standard_normal(n) * np.sqrt(1 - phi ** 2)
    x = np.empty(n)
    x[0] = rng.standard_normal()
    for t in range(1, n):
        x[t] = phi * x[t - 1] + e[t]
    return x


class O1:
    """Estructura fija de filas en riesgo (1926-10 … 2004-06) y calendario walk-forward del diseño."""

    def __init__(self, df: pd.DataFrame):
        d = df[df.en_riesgo].reset_index(drop=True)
        self.t = np.array([(m - FIT_DESDE).n for m in d.mes])        # índice de mes (para el AR)
        self.nt = int(self.t.max()) + 1
        self.y = d.y.values.astype(float)
        self.ent = d.ent.values
        self.n_ent = int(max(self.ent.max() + 1, 1))
        ev = np.array([m >= EVAL_DESDE for m in d.mes])
        self.bloques = []                                             # (filas de ajuste, filas a predecir) por año
        for anio in range(EVAL_DESDE.year, 2005):
            p0 = (pd.Period(f"{anio}-01", "M") - FIT_DESDE).n
            pred = np.where(ev & (self.t >= p0) & (self.t < p0 + 12))[0]
            if len(pred):
                self.bloques.append((np.where(self.t + H <= p0)[0], pred))
        self.ev = np.concatenate([b[1] for b in self.bloques])

    def una(self, rng, a: float, b: float, tau: float, phi_u: float, phi_w: float) -> tuple:
        """Devuelve (ΔAUC apilado, AUC listón apilado, ΔAUC índice, AUC listón índice).
        - apilado: probabilidades del logit de cada año apiladas (cambian intercepto y pendiente cada enero);
        - índice (métrica propuesta como principal, §5 del borrador): listón = x1 (rango invariante al reajuste),
          candidato = x1 + (β2/β1)·x2 con los coeficientes de ese año → aísla si el crédito AÑADE orden."""
        u, w = ar1(rng, self.nt, phi_u)[self.t], ar1(rng, self.nt, phi_w)[self.t]
        be = b + tau * rng.standard_normal(self.n_ent)
        x1 = a * self.y + u
        x2 = np.where(self.y == 1, be[np.maximum(self.ent, 0)], 0.0) + w
        sL, sA, iA = (np.empty(len(self.y)) for _ in range(3))
        bl, ba = None, None
        for fit, pred in self.bloques:
            bl = logit(x1[fit, None], self.y[fit], bl)
            ba = logit(np.column_stack([x1[fit], x2[fit]]), self.y[fit], ba)
            sL[pred] = bl[0] + bl[1] * x1[pred]
            sA[pred] = ba[0] + ba[1] * x1[pred] + ba[2] * x2[pred]
            iA[pred] = x1[pred] + (ba[2] / ba[1]) * x2[pred] if ba[1] > 1e-6 else ba[1] * x1[pred] + ba[2] * x2[pred]
        y = self.y[self.ev]
        aL, aA = auc(sL[self.ev], y), auc(sA[self.ev], y)
        iL, iAa = auc(x1[self.ev], y), auc(iA[self.ev], y)
        return aA - aL, aL, iAa - iL, iL


def delta_poblacional(a: float, b: float) -> float:
    """ΔAUC del oráculo (sin ruido de estimación, sin τ): binormal con dos rasgos independientes de varianza 1."""
    return float(norm.cdf(np.sqrt(a ** 2 + b ** 2) / np.sqrt(2)) - norm.cdf(a / np.sqrt(2)))


def b_para_delta(a: float, d: float) -> float:
    lo, hi = 0.0, 5.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if delta_poblacional(a, mid) < d else (lo, mid)
    return (lo + hi) / 2


def _bloque_o1(nula: np.ndarray, sims_por_delta: list, deltas, col: int) -> dict:
    c05, c025 = np.quantile(nula[:, col], 0.95), np.quantile(nula[:, col], 0.975)
    filas = []
    for d, (b, sims) in zip(deltas, sims_por_delta):
        dd = sims[:, col]
        filas.append({"delta_poblacional": d, "b": _r(b), "delta_medio_realizado": _r(dd.mean()),
                      "sd_delta": _r(dd.std(ddof=1)), "auc_liston_medio": _r(sims[:, col + 1].mean()),
                      "potencia_5": _r((dd > c05).mean(), 3), "potencia_2_5": _r((dd > c025).mean(), 3),
                      "p_delta_pos": _r((dd > 0).mean(), 3)})
    n = nula[:, col]
    return {"nula": {"media": _r(n.mean()), "sd": _r(n.std(ddof=1)), "critico_5": _r(c05), "critico_2_5": _r(c025),
                     "p_delta_pos": _r((n > 0).mean(), 3), "auc_liston_medio": _r(nula[:, col + 1].mean())},
            "filas": filas, "mde_80_5": mde(filas, "potencia_5"), "mde_80_2_5": mde(filas, "potencia_2_5")}


def potencia_o1(est: O1, auc_l: float, tau: float, deltas, reps: int, rng, phi_u=0.9, phi_w=0.85) -> dict:
    a = np.sqrt(2) * norm.ppf(auc_l)
    nula = np.array([est.una(rng, a, 0.0, 0.0, phi_u, phi_w) for _ in range(reps)])
    sims = []
    for d in deltas:
        b = b_para_delta(a, d)
        sims.append((b, np.array([est.una(rng, a, b, tau, phi_u, phi_w) for _ in range(reps)])))
    return {"auc_liston_rasgo": auc_l, "tau": tau, "phi_u": phi_u, "phi_w": phi_w,
            "indice": _bloque_o1(nula, sims, deltas, 2), "apilado": _bloque_o1(nula, sims, deltas, 0)}


def mde(filas: list, clave: str, x: str = "delta_poblacional", objetivo: float = 0.8):
    """Interpolación lineal del efecto con potencia 80 % (None si no se alcanza en la rejilla)."""
    xs, ps = [f[x] for f in filas], [f[clave] for f in filas]
    for i in range(1, len(xs)):
        if ps[i - 1] < objetivo <= ps[i]:
            return _r(xs[i - 1] + (objetivo - ps[i - 1]) * (xs[i] - xs[i - 1]) / (ps[i] - ps[i - 1]))
    return None if ps[-1] < objetivo else _r(xs[0])


# ================================================================ (iv) potencia O2 (QLIKE, RV 1 m)
def simular_lrv(rng, n: int, sd_obj: float, r2_har: float, rho_c: float, beta: float, phi_c: float = 0.85):
    """log RV mensual = μ + z1 + z2 + β·c_{t−1} + ε, z1 AR(0,98), z2 AR(0,7), ε t5. c AR(φ_c), con correlación
    rho_c con los choques de z2 (el crédito se ensancha cuando sube la volatilidad). Escalas: var(z1 + z2) =
    r2_har·sd_obj², var(ε) = (1 − r2_har)·sd_obj²."""
    vz = r2_har * sd_obj ** 2
    e1, e2 = rng.standard_normal(n), rng.standard_normal(n)
    ec = rho_c * e2 + np.sqrt(1 - rho_c ** 2) * rng.standard_normal(n)
    z1, z2, c = np.zeros(n), np.zeros(n), np.zeros(n)
    for t in range(1, n):
        z1[t] = 0.98 * z1[t - 1] + np.sqrt(1 - 0.98 ** 2) * e1[t]
        z2[t] = 0.7 * z2[t - 1] + np.sqrt(1 - 0.7 ** 2) * e2[t]
        c[t] = phi_c * c[t - 1] + np.sqrt(1 - phi_c ** 2) * ec[t]
    z = np.sqrt(vz / 2) * (z1 + z2)
    eps = rng.standard_t(5, n) / np.sqrt(5 / 3) * np.sqrt((1 - r2_har) * sd_obj ** 2)
    lrv = -6.0 + z + beta * np.r_[0.0, c[:-1]] + eps            # lrv[t] usa c[t − 1] (rasgo "as of" en t − 1)
    return lrv, c


def har_mensual(lrv: np.ndarray) -> np.ndarray:
    s = pd.Series(lrv)
    return np.column_stack([s, s.rolling(3).mean(), s.rolling(12).mean()])


def nw_t(d: np.ndarray, L: int = 6) -> float:
    n, m = len(d), d.mean()
    e = d - m
    v = e @ e / n
    for k in range(1, L + 1):
        v += 2 * (1 - k / (L + 1)) * (e[k:] @ e[:-k]) / n
    return float(m / np.sqrt(v / n))


def ols(X, y):
    Xc = np.column_stack([np.ones(len(X)), X])
    b = np.linalg.lstsq(Xc, y, rcond=None)[0]
    return b, y - Xc @ b


def una_o2(rng, n_fit: int, n_ev: int, sd_obj, r2, rho_c, beta) -> tuple[float, float]:
    n = n_fit + n_ev + 13
    lrv, c = simular_lrv(rng, n, sd_obj, r2, rho_c, beta)
    F = har_mensual(lrv)
    # fila t: rasgos en t (HAR hasta t, crédito c[t]) → objetivo lrv[t + 1]
    t0 = 12
    idx = np.arange(t0, n - 1)
    XL, XA, Y = F[idx], np.column_stack([F[idx], c[idx]]), lrv[idx + 1]
    ini = n_fit
    fL, fA = np.empty(n_ev), np.empty(n_ev)
    for k in range(0, n_ev, 12):
        tr = slice(0, ini + k)                          # filas cuyo objetivo ya se observó
        pr = slice(ini + k, min(ini + k + 12, ini + n_ev))
        bL, eL = ols(XL[tr], Y[tr])
        bA, eA = ols(XA[tr], Y[tr])
        fL[k:k + 12] = np.exp(np.column_stack([np.ones(len(XL[pr])), XL[pr]]) @ bL) * np.mean(np.exp(eL))
        fA[k:k + 12] = np.exp(np.column_stack([np.ones(len(XA[pr])), XA[pr]]) @ bA) * np.mean(np.exp(eA))
    rv = np.exp(Y[ini:ini + n_ev])
    ql = lambda f: rv / f - np.log(rv / f) - 1  # noqa: E731
    qL, qA = ql(fL), ql(fA)
    return float(1 - qA.mean() / qL.mean()), nw_t(qL - qA)


def potencia_o2(sd_obj, r2, rho_c, betas, reps, rng, n_fit=279, n_ev=659) -> dict:
    nula = np.array([una_o2(rng, n_fit, n_ev, sd_obj, r2, rho_c, 0.0) for _ in range(reps)])
    c05, c025 = np.quantile(nula[:, 1], 0.95), np.quantile(nula[:, 1], 0.975)
    filas = []
    for b in betas:
        s = np.array([una_o2(rng, n_fit, n_ev, sd_obj, r2, rho_c, b) for _ in range(reps)])
        g, t = s[:, 0], s[:, 1]
        filas.append({"beta": b, "ganancia_qlike_media": _r(g.mean()), "sd_ganancia": _r(g.std(ddof=1)),
                      "potencia_1645": _r((t > 1.645).mean(), 3), "potencia_196": _r((t > 1.96).mean(), 3),
                      "potencia_crit_nula_5": _r((t > c05).mean(), 3),
                      "potencia_crit_nula_2_5": _r((t > c025).mean(), 3), "p_ganancia_pos": _r((g > 0).mean(), 3)})
    for f in filas:
        f["ganancia"] = f["ganancia_qlike_media"]
    return {"sd_log_rv": sd_obj, "r2_har": r2, "rho_c": rho_c, "n_ajuste_inicial": n_fit, "n_eval": n_ev,
            "nula": {"ganancia_media": _r(nula[:, 0].mean()), "tam_1645": _r((nula[:, 1] > 1.645).mean(), 3),
                     "tam_196": _r((nula[:, 1] > 1.96).mean(), 3), "critico_5": _r(c05), "critico_2_5": _r(c025)},
            "filas": filas, "mde_ganancia_80_1645": mde(filas, "potencia_1645", "ganancia"),
            "mde_ganancia_80_196": mde(filas, "potencia_196", "ganancia"),
            "mde_ganancia_80_crit_nula_5": mde(filas, "potencia_crit_nula_5", "ganancia"),
            "mde_ganancia_80_crit_nula_2_5": mde(filas, "potencia_crit_nula_2_5", "ganancia")}


# ================================================================ main
def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    prueba = "--prueba" in argv
    reps = 40 if prueba else 600
    rng = np.random.default_rng(SEMILLA)
    from src.intl.data import connect
    from src.intl.procedencia import procedencia
    if not prueba and SALIDA.exists():
        raise SystemExit(f"{SALIDA} ya existe: no se sobrescribe")
    res = {"procedencia": procedencia(exigir_limpio=not prueba), "prueba": prueba, "reps": reps, "semilla": SEMILLA}
    t0 = time.time()
    con = connect("warehouse")
    res["inventario"] = inventario(con)
    p = indice_bolsa(con)
    con.close()
    if p.index.max() > CORTE:
        raise SystemExit("dato posterior al corte")

    # (ii) eventos
    df, ent = filas_o1(p, 0.15, 0.15)
    res["eventos_O1_LT15_15"] = resumen_o1(df, ent)
    df20, ent20 = filas_o1(p, 0.20, 0.20)
    res["eventos_variante_LT20_20"] = resumen_o1(df20, ent20)
    res["eventos_variante_desde_origen"] = {f"{int(u * 100)}pct": recuento_desde_origen(p, u) for u in (0.15, 0.20)}
    print(json.dumps({k: v for k, v in res.items() if k.startswith("eventos")}, ensure_ascii=False, default=str),
          flush=True)

    # (iii) O1
    est = O1(df)
    deltas = [0.02, 0.04, 0.06, 0.08, 0.10, 0.13, 0.16, 0.20]
    o1 = {}
    for auc_l, tau, phi in ((0.65, 0.0, 0.9), (0.65, 0.25, 0.9), (0.65, 0.5, 0.9), (0.60, 0.25, 0.9),
                            (0.70, 0.25, 0.9), (0.65, 0.25, 0.97)):
        k = f"aucL{auc_l}_tau{tau}_phi{phi}"
        o1[k] = potencia_o1(est, auc_l, tau, deltas, reps, rng, phi_u=phi, phi_w=min(phi, 0.97))
        for met in ("indice", "apilado"):
            v = o1[k][met]
            print("O1", k, met, v["nula"], v["mde_80_5"], v["mde_80_2_5"],
                  [(f["delta_poblacional"], f["potencia_5"]) for f in v["filas"]], round(time.time() - t0), flush=True)
    res["potencia_O1"] = o1

    # (iv) O2 (sd log RV 1 m 1950-2004 = 0,8856, research/int/int12_potencia.json → objetivos_marginales_EEUU)
    betas = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]
    o2 = {}
    for r2, rho in ((0.55, 0.4), (0.55, 0.0), (0.45, 0.4), (0.65, 0.4)):
        k = f"r2{r2}_rho{rho}"
        o2[k] = potencia_o2(0.8856, r2, rho, betas, reps // 2 if not prueba else reps, rng)
        print("O2", k, o2[k]["nula"], o2[k]["mde_ganancia_80_1645"], o2[k]["mde_ganancia_80_crit_nula_5"],
              [(f["ganancia_qlike_media"], f["potencia_1645"], f["potencia_crit_nula_5"]) for f in o2[k]["filas"]], round(time.time() - t0), flush=True)
    res["potencia_O2"] = o2
    res["supuestos"] = {
        "O1": "rasgos simulados binormales; x1 (HAR) AR(1) φ 0,9, x2 (crédito) AR(1) φ 0,85, independientes entre sí; "
              "señal del crédito b_e por entrada (τ); walk-forward anual con embargo de 6 m; valor crítico de la nula",
        "O2": "log RV mensual = dos AR (0,98; 0,7) + ruido t5; HAR mensual (1, 3, 12 meses) como listón; crédito AR(1) "
              "φ 0,85 correlacionado rho con los choques de volatilidad; MCO walk-forward anual; DM HAC NW 6",
        "deltas_realistas_O1": {"optimista": 0.08, "realista_maldicion_ganador": 0.04},
        "ganancias_realistas_O2": {"optimista": 0.03, "realista": 0.01, "INT12_C2_harx_con_nivel": -0.047},
    }
    res["segundos"] = round(time.time() - t0)
    if prueba:
        print("prueba: no se escribe nada")
        return
    SALIDA.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
    print("escrito", SALIDA)


if __name__ == "__main__":
    main()
