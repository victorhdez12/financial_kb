"""INT-12 fase 1 (borrador): modelo de RIESGO DE MERCADO a 1-3 meses. Inventario + POTENCIA antes de construir nada
(docs/int/INT12_diseno_v0.md). Datos reales solo ≤ 2004; nada ≥ 2005.

Pregunta de potencia: ¿se puede DEMOSTRAR (Diebold-Mariano con HAC, un contraste, 80 %) que un modelo de ML mejora a un
listón HAR / EWMA / σ̂ de 12 meses (el de B1) en QLIKE (volatilidad), pinball y FZ0 (VaR / ES 5 %) y Brier (P de caída
≥ 10 % en 3 meses), con las muestras que hay ≤ 2004?

Qué usa (y nada más), en partes que NUNCA se juntan:
  (i)   INVENTARIO: cobertura de cada serie candidata (fechas, observaciones ≤ 2004, frecuencia). Ningún valor cruzado.
  (ii)  OBJETIVOS (solo la serie de rentabilidad diaria de EE. UU., AQR MKT USA, CRSP, 1926-2004): recuentos y momentos
        MARGINALES (nivel medio de la volatilidad, dispersión de log RV, curtosis diaria, frecuencia de caídas ≥ 10 % y
        episodios) y la correlación CONTEMPORÁNEA de log RV entre países (AQR, 1991-2004). Nunca una relación
        pasado → futuro: ni autocorrelación de RV, ni HAR ajustado, ni ningún predictor frente al objetivo.
  (iii) POTENCIA: proceso SIMULADO de volatilidad estocástica de 3 componentes (persistencias de la literatura, NO
        estimadas aquí) con colas gruesas y apalancamiento; nivel y dispersión ajustados a los momentos marginales de (ii).
        En cada réplica se ajustan de verdad HAR (log, ventana creciente, embargo), EWMA (λ = 0,94) y la σ̂ de 12 meses
        de B1; el "ML" se representa como una mezcla en logaritmos del listón con el ORÁCULO (que conoce el estado
        latente) más ruido de estimación: log f_ML = (1 − w) log f_listón + w log f_oráculo + ν. w fija la ganancia.
        DM unilateral con HAC (Newey-West) y valor crítico de la nula simulada (dos previsiones igual de buenas).

Uso: .venv/bin/python -m scripts.int12_potencia            (con puerta: árbol limpio; escribe el JSON)
     .venv/bin/python -m scripts.int12_potencia --prueba   (sin puerta; no escribe nada; pocas réplicas)
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
CORTE = pd.Timestamp("2004-12-31")
DIAS_MES = 21
UMBRAL_CAIDA = -0.10
ALFA = 0.05

# (i) inventario: series candidatas (rol → ids). Solo cobertura.
CANDIDATAS = {
    "rentabilidad_diaria_EEUU": ["aqr_mkt_usa_d"],
    "rentabilidad_diaria_otros": ["aqr_mkt_global_d", "aqr_mkt_europe_d", "ffx_dev_mkt_rf_d", "NASDAQCOM"],
    "rentabilidad_mensual_larga": ["shiller_nominal_stock_tr_ret_m", "shiller_sp_price", "ff_mkt_rf_m"],
    "volatilidad_implicita": ["VIXCLS", "VXDCLS", "VXNCLS", "cboe_skew", "cboe_vx_f1"],
    "credito": ["BAA", "AAA", "DBAA", "DAAA", "BAA10Y", "TEDRATE", "CPFF", "NFCI", "STLFSI4"],
    "tipos_curva": ["TB3MS", "GS10", "GS1", "FEDFUNDS", "DTB3", "DGS10", "T10Y3M", "T10Y2Y"],
    "estres_incertidumbre": ["ecb_ciss_new_ea_d", "USEPUINDXD"],
    "macro_mensual_vintages": ["INDPRO", "PAYEMS", "CPIAUCSL", "UNRATE", "ICSA", "UMCSENT", "USREC"],
    "divisa_B1": ["bundesbank_usd_dem_d", "ecb_eurusd_d", "SP500"],
}

# (iii) proceso simulado (literatura: volatilidad estocástica multifactor, p. ej. Chernov-Gallant-Ghysels-Tauchen 2003;
# vida media ≈ 460 / 23 / 2,4 días). NO se estiman con los datos: solo el nivel (mu) y la escala de las desviaciones.
PHI = (0.9985, 0.97, 0.75)
SD_ESTACIONARIA = (0.45, 0.45, 0.35)           # en log-varianza diaria; se re-escalan con la dispersión real de log RV
RHO_APALANCAMIENTO = (0.0, -0.45, -0.45)        # correlación del choque de cada componente con la rentabilidad del día
NU_T = 6.0                                      # colas: mezcla de escala inversa-gamma (t de 6 g. l.)
W_REJILLA = (0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.45, 0.6, 0.8, 1.0)
SD_NU, PHI_NU = 0.05, 0.5                       # ruido de estimación del ML (log), AR(1) mensual
SD_NULA, PHI_NULA = 0.10, 0.5                   # nula: dos versiones del listón con ruido independiente
REALISTAS_QLIKE = (0.02, 0.05, 0.10)            # literatura: ML frente a HAR 2-10 % en QLIKE (más en 1 día que en 1 mes)


@dataclass
class Proceso:
    phi: tuple = PHI
    sd: tuple = SD_ESTACIONARIA
    rho: tuple = RHO_APALANCAMIENTO
    nu: float = NU_T
    vol_anual: float = 0.17                     # se sustituye por el nivel real ≤ 2004 (momento marginal)
    deriva_diaria: float = 0.0003
    escala_sd: float = 1.0                      # se ajusta para casar la dispersión de log RV 1 m real

    def mu(self) -> float:
        s2 = sum((self.escala_sd * s) ** 2 for s in self.sd)
        return float(np.log(self.vol_anual ** 2 / 252) - 0.5 * s2)


def _r(x, k=4):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), k)


# ================================================================ (ii) objetivos sobre datos reales (solo marginales)
def objetivos_mensuales(r: pd.Series, h_meses: int, umbral: float = UMBRAL_CAIDA) -> pd.DataFrame:
    """Orígenes = último día hábil de cada mes. Para cada origen: RV de los h meses siguientes (suma de r², rentabilidad
    diaria en decimales), rentabilidad acumulada y si la trayectoria cae ≥ |umbral| desde el origen. Solo filas cuyos h
    meses estén completos (el último mes de la serie se descarta)."""
    r = r.dropna().sort_index()
    mes = r.index.to_period("M")
    meses = mes.unique()
    grupos = {m: r.values[mes == m] for m in meses}
    filas = []
    for i, m in enumerate(meses[:-h_meses] if h_meses else meses):
        fut = np.concatenate([grupos[meses[i + k]] for k in range(1, h_meses + 1)])
        camino = np.cumprod(1 + fut)
        filas.append({"origen": m, "rv": float(np.sum(fut ** 2)), "ret": float(camino[-1] - 1),
                      "caida": int(camino.min() <= 1 + umbral), "n_dias": len(fut)})
    return pd.DataFrame(filas)


def episodios(orig: list, gap: int) -> int:
    """Agrupa orígenes (Period mensuales) con evento separados por ≤ gap meses en un mismo episodio."""
    n, prev = 0, None
    for f in sorted(orig):
        if prev is None or (f - prev).n > gap:
            n += 1
        prev = f
    return n


def marginales(r: pd.Series, desde: str, hasta: pd.Timestamp = CORTE) -> dict:
    """Momentos MARGINALES de los objetivos (nada de pasado → futuro)."""
    r = r[(r.index >= desde) & (r.index <= hasta)]
    o1, o3 = objetivos_mensuales(r, 1), objetivos_mensuales(r, 3)
    lrv = np.log(o1.rv[o1.rv > 0])
    ev = list(o3.origen[o3.caida == 1])
    x = r.values
    curt = float(np.mean((x - x.mean()) ** 4) / np.var(x) ** 2)
    return {"desde": desde, "dias": int(len(r)), "origenes_1m": int(len(o1)), "origenes_3m": int(len(o3)),
            "vol_anual_media_sqrt_media_rv": _r(np.sqrt(o1.rv.mean() * 12)), "sd_log_rv1m": _r(lrv.std(ddof=1)),
            "curtosis_diaria": _r(curt, 2), "deriva_diaria": _r(x.mean(), 6),
            "caidas10_3m": {"origenes": int(len(o3)), "eventos": int(o3.caida.sum()), "tasa": _r(o3.caida.mean()),
                            "episodios_gap3": episodios(ev, 3), "años_distintos": len({p.year for p in ev})},
            "meses_rv_top10pct": int((o1.rv >= o1.rv.quantile(0.9)).sum()),
            "episodios_rv_top10pct_gap3": episodios(list(o1.origen[o1.rv >= o1.rv.quantile(0.9)]), 3)}


def corr_panel(rs: dict[str, pd.Series], desde: str = "1991-01-01", hasta: pd.Timestamp = CORTE) -> dict:
    """Correlación CONTEMPORÁNEA media de log RV mensual entre países (como el ICC / efecto de diseño de INT-10)."""
    lrv = {}
    for k, s in rs.items():
        s = s[(s.index >= desde) & (s.index <= hasta)].dropna()
        if len(s) < 200:
            continue
        g = (s ** 2).groupby(s.index.to_period("M")).sum()
        lrv[k] = np.log(g[g > 0])
    df = pd.DataFrame(lrv).dropna()
    c = df.corr().values
    k = c.shape[0]
    media = float((c.sum() - k) / (k * (k - 1))) if k > 1 else float("nan")
    return {"paises": sorted(lrv), "k": k, "meses": int(len(df)), "corr_media_log_rv1m": _r(media),
            "k_efectivo": _r(k / (1 + (k - 1) * media)) if k > 1 else None}


# ================================================================ (iii) simulación
def simular_camino(n_dias: int, p: Proceso, rng, comun=None) -> tuple[np.ndarray, np.ndarray]:
    """Rentabilidades diarias y componentes latentes C[d] (estado que da la varianza del día d + 1).
    var_d = exp(mu + Σ C[d − 1]); r_d = deriva + sqrt(var_d · λ_d) z_d; C[d] = φ C[d − 1] + sd·(ρ z_d + √(1−ρ²) ε).
    `comun` (opcional): (z_común, ε_común, peso) para paneles de países con choques compartidos."""
    phi = np.array(p.phi)
    sd = np.array(p.sd) * p.escala_sd
    sdi = sd * np.sqrt(1 - phi ** 2)
    rho = np.array(p.rho)
    z = rng.standard_normal(n_dias)
    eps = rng.standard_normal((n_dias, len(phi)))
    if comun is not None:
        zc, ec, a = comun
        z = np.sqrt(a) * zc + np.sqrt(1 - a) * z
        eps = np.sqrt(a) * ec + np.sqrt(1 - a) * eps
    lam = (p.nu - 2) / rng.chisquare(p.nu, n_dias)
    choque = sdi * (rho * z[:, None] + np.sqrt(1 - rho ** 2) * eps)
    C = np.empty((n_dias, len(phi)))
    c = rng.standard_normal(len(phi)) * sd
    mu = p.mu()
    r = np.empty(n_dias)
    for d in range(n_dias):                    # bucle simple: n_dias ≈ 2·10⁴, coste despreciable frente al resto
        r[d] = p.deriva_diaria + np.exp(0.5 * (mu + c.sum())) * np.sqrt(lam[d]) * z[d]
        c = phi * c + choque[d]
        C[d] = c
    return r, C


def oraculo(C_origen: np.ndarray, p: Proceso, H: int) -> np.ndarray:
    """E[Σ_{k=1..H} var_{d+k} | C[d]] exacto (choques gaussianos)."""
    phi = np.array(p.phi)
    sd = np.array(p.sd) * p.escala_sd
    k = np.arange(H)                                          # var_{d+1+k} depende de C[d+k] = φ^k C[d] + ruido
    pk = phi[None, :] ** k[:, None]                           # H × J
    v = 0.5 * (sd ** 2 * (1 - phi[None, :] ** (2 * k[:, None]))).sum(1)
    return np.exp(p.mu() + C_origen @ pk.T + v[None, :]).sum(1)


def _media_movil(x: np.ndarray, n: int) -> np.ndarray:
    c = np.concatenate([[0.0], np.cumsum(x)])
    out = np.full(len(x), np.nan)
    out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def har_rasgos(r: np.ndarray) -> np.ndarray:
    """Rasgos HAR con rentabilidades diarias (sin intradía): log de la media de r² en 5, 21 y 63 días."""
    r2 = r ** 2
    return np.column_stack([np.log(_media_movil(r2, n) + 1e-12) for n in (5, 21, 63)])


def suma_futura(x: np.ndarray, H: int) -> np.ndarray:
    """S[d] = Σ x[d+1 … d+H] (NaN si no cabe)."""
    c = np.concatenate([[0.0], np.cumsum(x)])
    out = np.full(len(x), np.nan)
    d = np.arange(len(x) - H)
    out[d] = c[d + H + 1] - c[d + 1]
    return out


def prevision_har(r: np.ndarray, origenes: np.ndarray, H: int, primer_entreno: int, cada: int = 252) -> np.ndarray:
    """log-HAR por MCO con ventana creciente: se re-estima cada `cada` días con todas las filas diarias d' cuyo objetivo
    acaba antes del origen (embargo: d' + H ≤ origen). Corrección de Duan (media de exp(residuo))."""
    X = har_rasgos(r)
    y = np.log(suma_futura(r ** 2, H) / H + 1e-12)
    f = np.full(len(origenes), np.nan)
    beta, smear, ultimo = None, None, -10 ** 9
    for i, o in enumerate(origenes):
        if o - ultimo >= cada or beta is None:
            fin = o - H + 1
            idx = np.arange(primer_entreno, max(fin, primer_entreno))
            idx = idx[np.isfinite(X[idx]).all(1) & np.isfinite(y[idx])]
            A = np.column_stack([np.ones(len(idx)), X[idx]])
            beta = np.linalg.lstsq(A, y[idx], rcond=None)[0]
            smear = float(np.mean(np.exp(y[idx] - A @ beta)))
            ultimo = o
        f[i] = H * np.exp(beta[0] + X[o] @ beta[1:]) * smear
    return f


def prevision_ewma(r: np.ndarray, origenes: np.ndarray, H: int, lam: float = 0.94) -> np.ndarray:
    """RiskMetrics: σ²_{d+1} = λ σ²_d + (1 − λ) r_d²; previsión plana H · σ²_{d+1}."""
    s2 = np.empty(len(r))
    s2[0] = r[:63].var()
    for d in range(1, len(r)):
        s2[d] = lam * s2[d - 1] + (1 - lam) * r[d - 1] ** 2
    nxt = lam * s2 + (1 - lam) * r ** 2                       # σ²_{d+1} conocido al cierre de d
    return H * nxt[origenes]


def prevision_b1(r: np.ndarray, origenes: np.ndarray, H: int) -> np.ndarray:
    """σ̂ de B1: varianza muestral (ddof = 1) de los 12 últimos rendimientos MENSUALES; previsión (H/21) · σ̂²_mes."""
    f = np.full(len(origenes), np.nan)
    for i, o in enumerate(origenes):
        ini = o + 1 - 12 * DIAS_MES
        if ini < 0:
            continue
        m = np.prod(1 + r[ini:o + 1].reshape(12, DIAS_MES), axis=1) - 1
        f[i] = (H / DIAS_MES) * m.var(ddof=1)
    return f


# ---------------------------------------------------------------- funciones de pérdida
def qlike(f: np.ndarray, y: np.ndarray) -> np.ndarray:
    """QLIKE (Patton 2011): y/f − log(y/f) − 1 ≥ 0; robusta al ruido del proxy y libre de escala."""
    q = y / f
    return q - np.log(q) - 1


def pinball(q: np.ndarray, y: np.ndarray, a: float = ALFA) -> np.ndarray:
    return (a - (y <= q)) * (y - q)


def fz0(v: np.ndarray, e: np.ndarray, y: np.ndarray, a: float = ALFA) -> np.ndarray:
    """Pérdida FZ0 de Patton-Ziegel-Chen (2019) para (VaR, ES) conjuntos, v ≥ e, ambos < 0."""
    ind = (y <= v).astype(float)
    return -ind * (v - y) / (a * e) + v / e + np.log(-e) - 1


def escala_cuantil(y: np.ndarray, f: np.ndarray, a: float = ALFA) -> tuple[float, float]:
    """VaR = −kv·√f y ES = −ke·√f con kv, ke de la propia muestra (igual para todos los modelos: calibración de la
    ESCALA por oráculo; mide solo la capacidad de ordenar riesgo)."""
    s = y / np.sqrt(f)
    kv = -np.quantile(s, a)
    ke = -s[s <= -kv].mean()
    return float(kv), float(ke)


def logit_ajuste(x: np.ndarray, y: np.ndarray, it: int = 25) -> np.ndarray:
    """Logística P(y) = 1/(1 + exp(−(a + b x))) por Newton (2 parámetros)."""
    A = np.column_stack([np.ones(len(x)), x])
    b = np.zeros(2)
    for _ in range(it):
        p = 1 / (1 + np.exp(-np.clip(A @ b, -30, 30)))
        W = p * (1 - p) + 1e-9
        b = b + np.linalg.solve(A.T @ (A * W[:, None]) + 1e-8 * np.eye(2), A.T @ (y - p))
    return 1 / (1 + np.exp(-np.clip(A @ b, -30, 30)))


# ---------------------------------------------------------------- contraste
def nw_t(d: np.ndarray, lags: int) -> float:
    """t de Diebold-Mariano con varianza HAC de Newey-West (Bartlett). d > 0 ⇒ el retador pierde menos."""
    d = np.asarray(d, float)
    n = len(d)
    u = d - d.mean()
    s = u @ u / n
    for k in range(1, lags + 1):
        s += 2 * (1 - k / (lags + 1)) * (u[k:] @ u[:-k]) / n
    return float(d.mean() / np.sqrt(max(s, 1e-300) / n))


def lags_hac(n: int, h_meses: int) -> int:
    return (h_meses - 1) + int(np.floor(4 * (n / 100) ** (2 / 9)))


def n_efectivo(d: np.ndarray, kmax: int = 12) -> float:
    u = d - d.mean()
    v = u @ u
    rho = [(u[k:] @ u[:-k]) / v for k in range(1, kmax + 1)]
    return float(len(d) / max(1 + 2 * sum(rho), 1e-9))


def _ar1(n: int, phi: float, sd: float, rng) -> np.ndarray:
    e = rng.standard_normal(n) * sd * np.sqrt(1 - phi ** 2)
    x = np.empty(n)
    x[0] = rng.standard_normal() * sd
    for t in range(1, n):
        x[t] = phi * x[t - 1] + e[t]
    return x


# ---------------------------------------------------------------- una réplica
@dataclass
class Escenario:
    nombre: str
    n_oos: int                       # meses fuera de muestra (orígenes mensuales)
    meses_entreno: int = 288         # 24 años antes del primer origen (como 1926-07 → 1950)
    k_paises: int = 1
    corr_comun: float = 0.0          # peso del choque común entre países (panel)
    hs: tuple = (1, 3)
    extra: dict = field(default_factory=dict)


def replica(esc: Escenario, p: Proceso, rng, ws=W_REJILLA) -> dict:
    """Devuelve, por horizonte, las pérdidas por origen (promediadas entre países si hay panel) de cada modelo."""
    H3 = max(esc.hs) * DIAS_MES
    n_meses = esc.meses_entreno + esc.n_oos + max(esc.hs) + 1
    n_dias = n_meses * DIAS_MES
    comun = None
    if esc.k_paises > 1:
        comun = (rng.standard_normal(n_dias), rng.standard_normal((n_dias, len(p.phi))), esc.corr_comun)
    origenes = (np.arange(esc.meses_entreno, esc.meses_entreno + esc.n_oos) + 1) * DIAS_MES - 1
    out = {h: {} for h in esc.hs}
    for _ in range(esc.k_paises):
        r, C = simular_camino(n_dias, p, rng, comun)
        for h in esc.hs:
            H = h * DIAS_MES
            y = suma_futura(r ** 2, H)[origenes]
            ret = suma_futura(r, H)[origenes]                        # log-aprox. de la rentabilidad del periodo
            cam = np.cumsum(r)
            caida = np.array([(cam[o + 1:o + 1 + H] - cam[o]).min() <= np.log(1 + UMBRAL_CAIDA) for o in origenes])
            incond = H * np.exp(p.mu() + 0.5 * sum((p.escala_sd * x) ** 2 for x in p.sd))
            prev = {"oraculo": oraculo(C[origenes], p, H), "constante": np.full(len(origenes), incond),
                    "har": prevision_har(r, origenes, H, primer_entreno=63),
                    "ewma": prevision_ewma(r, origenes, H),
                    "b1_12m": prevision_b1(r, origenes, H)}
            nu = _ar1(len(origenes), PHI_NU, esc.extra.get("sd_nu", SD_NU), rng)
            for w in ws:
                prev[f"ml_w{w}"] = np.exp((1 - w) * np.log(prev["har"]) + w * np.log(prev["oraculo"]) + nu)
            na = _ar1(len(origenes), PHI_NULA, SD_NULA, rng)
            nb = _ar1(len(origenes), PHI_NULA, SD_NULA, rng)
            prev["nula_a"], prev["nula_b"] = prev["har"] * np.exp(na), prev["har"] * np.exp(nb)
            for k, f in prev.items():
                L = {"qlike": qlike(f, y)}
                kv, ke = escala_cuantil(ret, f)
                v, e = -kv * np.sqrt(f), -ke * np.sqrt(f)
                L["pinball"] = pinball(v, ret)
                L["fz0"] = fz0(v, e, ret)
                L["brier"] = (logit_ajuste(np.log(f), caida.astype(float)) - caida) ** 2
                for m, x in L.items():
                    out[h].setdefault(k, {}).setdefault(m, []).append(x)
            out[h].setdefault("_tasa_caida", []).append(caida.mean())
            out[h].setdefault("_sd_log_rv", []).append(np.log(y).std())
            x = r[esc.meses_entreno * DIAS_MES:]
            out[h].setdefault("_curtosis", []).append(np.mean((x - x.mean()) ** 4) / np.var(x) ** 2)
    res = {}
    for h in esc.hs:
        res[h] = {k: ({m: np.mean(v, axis=0) for m, v in d.items()} if isinstance(d, dict) else float(np.mean(d)))
                  for k, d in out[h].items()}
    return res


PERDIDAS = ("qlike", "pinball", "fz0", "brier")


def potencia(esc: Escenario, p: Proceso, reps: int, rng, ws=W_REJILLA) -> dict:
    """Potencia del DM unilateral (5 %, valor crítico de la nula simulada) para cada contraste y pérdida."""
    contrastes = {"har_vs_b1_12m": ("b1_12m", "har"), "har_vs_ewma": ("ewma", "har"),
                  "oraculo_vs_har_(techo)": ("har", "oraculo")}
    contrastes.update({f"ml_w{w}_vs_har": ("har", f"ml_w{w}") for w in ws})
    T = {h: {c: {m: [] for m in PERDIDAS} for c in list(contrastes) + ["nula"]} for h in esc.hs}
    G = {h: {c: {m: [] for m in PERDIDAS} for c in contrastes} for h in esc.hs}
    NEF = {h: [] for h in esc.hs}
    aux = {h: {"tasa_caida": [], "sd_log_rv": [], "curtosis": []} for h in esc.hs}
    REF = {h: {m: [] for m in PERDIDAS} for h in esc.hs}
    for _ in range(reps):
        rr = replica(esc, p, rng, ws)
        for h in esc.hs:
            L = rr[h]
            lg = lags_hac(esc.n_oos, h)
            for m in PERDIDAS:
                T[h]["nula"][m].append(nw_t(L["nula_a"][m] - L["nula_b"][m], lg))
                for c, (base, ret) in contrastes.items():
                    d = L[base][m] - L[ret][m]
                    T[h][c][m].append(nw_t(d, lg))
                    G[h][c][m].append((L[base][m].mean(), L[ret][m].mean()))
            NEF[h].append(n_efectivo(L["har"]["qlike"] - L["ml_w0.3"]["qlike"]) if "ml_w0.3" in L else np.nan)
            aux[h]["tasa_caida"].append(L["_tasa_caida"])
            aux[h]["sd_log_rv"].append(L["_sd_log_rv"])
            aux[h]["curtosis"].append(L["_curtosis"])
            for m in PERDIDAS:
                REF[h][m].append((L["constante"][m].mean(), L["oraculo"][m].mean()))
    res = {}
    for h in esc.hs:
        crit = {m: float(np.quantile(T[h]["nula"][m], 0.95)) for m in PERDIDAS}
        tam = {m: float(np.mean(np.array(T[h]["nula"][m]) > 1.645)) for m in PERDIDAS}
        filas = {}
        for c in contrastes:
            filas[c] = {}
            for m in PERDIDAS:
                g = np.array(G[h][c][m])
                ref = np.array(REF[h][m])
                ganancia = 1 - g[:, 1].mean() / g[:, 0].mean()        # reducción relativa (solo pérdidas ≥ 0)
                recorrido = (g[:, 0].mean() - g[:, 1].mean()) / (ref[:, 0].mean() - ref[:, 1].mean())
                filas[c][m] = {"ganancia_rel": _r(ganancia) if m != "fz0" else None,
                               "fraccion_recorrido_constante_oraculo": _r(recorrido), "potencia": _r(np.mean(np.array(T[h][c][m]) > crit[m]), 3),
                               "potencia_crit_normal": _r(np.mean(np.array(T[h][c][m]) > 1.645), 3)}
        res[f"h{h}"] = {"critico_nula_95": {m: _r(v, 3) for m, v in crit.items()},
                        "tamaño_real_con_1.645": {m: _r(v, 3) for m, v in tam.items()},
                        "n_efectivo_dif_qlike_(w=0.3)": _r(np.nanmean(NEF[h]), 1),
                        "tasa_caida10_sim": _r(np.mean(aux[h]["tasa_caida"])),
                        "sd_log_rv_sim": _r(np.mean(aux[h]["sd_log_rv"])),
                        "curtosis_diaria_sim": _r(np.mean(aux[h]["curtosis"]), 2),
                        "contrastes": filas,
                        "mde": {m: mde(filas, m, ws) for m in PERDIDAS}}
    return res


def mde(filas: dict, m: str, ws=W_REJILLA, objetivo: float = 0.8) -> dict:
    """Ganancia mínima detectable EXPRESADA EN QLIKE (el mismo ML, misma w): para cada pérdida m, la reducción relativa
    de QLIKE frente a HAR a partir de la cual el contraste en m alcanza el 80 % (interpolación lineal en la rejilla).
    Así VaR/ES/Brier se leen en la misma escala que la volatilidad."""
    g = np.array([filas[f"ml_w{w}_vs_har"]["qlike"]["ganancia_rel"] for w in ws], float)
    pw = np.array([filas[f"ml_w{w}_vs_har"][m]["potencia"] for w in ws], float)
    propia = [filas[f"ml_w{w}_vs_har"][m]["fraccion_recorrido_constante_oraculo"] for w in ws]
    out = {"ganancia_qlike_en_w": [_r(x) for x in g], "potencia_en_w": [_r(x, 3) for x in pw],
           "fraccion_recorrido_propia_en_w": propia}
    idx = np.where(pw >= objetivo)[0]
    if len(idx) == 0:
        out["mde_ganancia_qlike"] = None
        out["nota"] = f"ni el oráculo alcanza {objetivo:.0%}"
        return out
    i = idx[0]
    if i == 0:
        out["mde_ganancia_qlike"] = _r(g[0])
    else:
        t = (objetivo - pw[i - 1]) / max(pw[i] - pw[i - 1], 1e-9)
        out["mde_ganancia_qlike"] = _r(g[i - 1] + t * (g[i] - g[i - 1]))
    for x in REALISTAS_QLIKE:
        out[f"potencia_si_ganancia_{x}"] = _r(float(np.interp(x, g, pw)), 3) if g.max() >= x else None
    return out


# ================================================================ principal
def escala_para_sd(p: Proceso, objetivo_sd: float, rng, n_meses: int = 3000) -> float:
    """Busca la escala de las desviaciones del proceso que reproduce la sd marginal de log RV 1 m (momento marginal)."""
    lo, hi = 0.3, 2.0
    for _ in range(14):
        mid = 0.5 * (lo + hi)
        q = Proceso(**{**asdict(p), "escala_sd": mid})
        r, _ = simular_camino(n_meses * DIAS_MES, q, np.random.default_rng(rng.integers(1 << 31)))
        sd = np.log((r.reshape(n_meses, DIAS_MES) ** 2).sum(1)).std()
        lo, hi = (mid, hi) if sd < objetivo_sd else (lo, mid)
    return 0.5 * (lo + hi)


def inventario(con) -> dict:
    out = {}
    for rol, ids in CANDIDATAS.items():
        out[rol] = {}
        for s in ids:
            q = ("select min(date), max(date) filter (where date <= ?), count(*) filter (where date <= ?), "
                 "count(*) filter (where date > ?) from obs_latest where series_id = ? and value is not null")
            d0, d1, n, npost = con.execute(q, [CORTE.date(), CORTE.date(), CORTE.date(), s]).fetchone()
            fr = con.execute("select frequency, source from catalog where series_id = ?", [s]).fetchone()
            nv = con.execute("select count(distinct realtime_start) from observations where series_id = ? "
                             "and realtime_start is not null", [s]).fetchone()[0]
            out[rol][s] = {"frecuencia": fr[0] if fr else None, "fuente": fr[1] if fr else None,
                           "desde": str(d0) if d0 else None, "ultimo_le_2004": str(d1) if d1 else None,
                           "obs_le_2004": int(n), "obs_post_2004": int(npost), "vintages_distintas": int(nv)}
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    borrador = "--prueba" in argv
    reps = 12 if borrador else 300
    reps_panel = 4 if borrador else 100
    rng = np.random.default_rng(20261030)
    from src.intl.procedencia import procedencia
    from src.warehouse import db
    res = {"procedencia": procedencia(exigir_limpio=not borrador), "borrador": borrador, "reps": reps,
           "reps_panel": reps_panel}
    t0 = time.time()

    con = db.connect()
    res["inventario"] = inventario(con)
    r_us = db.series(con, "aqr_mkt_usa_d") / 100
    r_us = r_us[r_us.index <= CORTE]
    paises = [s for s in db.all_series_ids(con) if s.startswith("aqr_mkt_") and s.endswith("_d")
              and s.count("_") == 3 and s not in ("aqr_mkt_usa_d", "aqr_mkt_europe_d", "aqr_mkt_global_d",
                                                   "aqr_mkt_pacific_d")]
    rs = {}
    for s in paises:
        x = db.series(con, s) / 100
        x = x[x.index <= CORTE]
        if len(x) and x.index.min() <= pd.Timestamp("1990-12-31"):
            rs[s] = x
    rs["aqr_mkt_usa_d"] = r_us
    con.close()

    # (ii) objetivos: solo marginales
    marg = {k: marginales(r_us, k) for k in ("1926-07-01", "1950-01-01", "1960-01-01", "1990-01-01")}
    res["objetivos_marginales_EEUU"] = marg
    res["panel_corr_contemporanea"] = corr_panel(rs)
    print(json.dumps(marg, ensure_ascii=False), json.dumps(res["panel_corr_contemporanea"]), flush=True)

    # (iii) proceso: nivel, deriva y dispersión marginales de 1950-2004
    m0 = marg["1950-01-01"]                     # periodo de evaluación principal (A)
    p = Proceso(vol_anual=m0["vol_anual_media_sqrt_media_rv"], deriva_diaria=m0["deriva_diaria"])
    p.escala_sd = escala_para_sd(p, m0["sd_log_rv1m"], rng, 600 if borrador else 3000)
    res["proceso"] = {**asdict(p), "mu": p.mu(), "nota": "persistencias de la literatura; nivel/dispersión marginales"}
    print("proceso", res["proceso"], flush=True)

    escenarios = [
        Escenario("A_EEUU_1950-2004", 660),
        Escenario("B_EEUU_1960-2004", 540),
        Escenario("C_EEUU_1975-2004", 360),
        Escenario("D_con_VIX_1995-2004", 120, meses_entreno=288),
        Escenario("E_panel16_1991-2004", 168, meses_entreno=288, k_paises=16,
                  corr_comun=float(res["panel_corr_contemporanea"]["corr_media_log_rv1m"] or 0.6)),
        Escenario("S1_A_ruido_ML_0.10", 660, extra={"sd_nu": 0.10}),
        Escenario("S2_A_dispersion_baja", 660, extra={"sd_log_rv_objetivo": 0.70}),
    ]
    p_baja = Proceso(**{**asdict(p), "escala_sd": escala_para_sd(p, 0.70, rng, 600 if borrador else 3000)})
    res["proceso_sensibilidad_dispersion_baja"] = {**asdict(p_baja), "mu": p_baja.mu()}
    sim = {}
    for e in escenarios:
        pe = p_baja if "sd_log_rv_objetivo" in e.extra else p
        sim[e.nombre] = potencia(e, pe, reps_panel if e.k_paises > 1 else reps, rng)
        for h, v in sim[e.nombre].items():
            print(e.nombre, h, {m: v["mde"][m].get("mde_ganancia_qlike") for m in PERDIDAS},
                  {c: v["contrastes"][c]["qlike"] for c in ("har_vs_b1_12m", "har_vs_ewma", "oraculo_vs_har_(techo)")},
                  "tam", v["tamaño_real_con_1.645"], "neff", v["n_efectivo_dif_qlike_(w=0.3)"],
                  f"{time.time() - t0:.0f}s", flush=True)
    res["simulacion"] = sim
    res["supuestos"] = {"w_rejilla": list(W_REJILLA), "sd_nu": SD_NU, "phi_nu": PHI_NU, "sd_nula": SD_NULA,
                        "phi_nula": PHI_NULA, "realistas_qlike": list(REALISTAS_QLIKE), "alfa_var": ALFA,
                        "umbral_caida": UMBRAL_CAIDA, "dias_mes": DIAS_MES, "contraste": "DM unilateral 5 %, HAC NW",
                        "escalas_var_es_brier": "calibradas en la propia muestra para todos los modelos (oráculo)"}
    res["segundos"] = round(time.time() - t0)
    if not borrador:
        (REPO / "research" / "int" / "int12_potencia.json").write_text(
            json.dumps(res, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
