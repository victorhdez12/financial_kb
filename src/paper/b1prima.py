"""B1′ (docs/factors/B1prima_spec.md v1.0, congelada el 30-oct; implementación: docs/factors/B1prima_implementacion.md).
La misma regla que B1 (src/paper/live.py) con otra σ̂: σ̂′_t = √(12 · f_t), f_t la previsión log-HAR a 1 mes de la
varianza de la RV de EE. UU. EN EUR con datos diarios. EN PARALELO a B1: B1, su registro y su σ* no se tocan.

- Rendimiento diario en EUR: r = (1 + r_USD) · (X_t / X_{t−1}) − 1, con X = EUR por USD (= 1 / EURUSD del BCE; antes de
  1999, DEM por USD del fixing de Frankfurt / 1,95583). X se lleva al último fixing conocido en cada sesión de EE. UU.
- Rasgos (como P-DEV-INT12): log de la media de r² de las últimas 5, 21 y 63 sesiones hasta el cierre (incluido).
- log-HAR: MCO de log(RV_{M+1} / n_{M+1}) sobre [1, lrv5, lrv21, lrv63]; f = n_{M+1} · exp(β·x) · Duan. Coeficientes
  estimados UNA vez (1963-07 … 2004-11, datos ≤ 2004; scripts/b1prima_congelar.py) y CONGELADOS con sha256 en
  research/paper/b1prima_congelado.json; aquí solo se leen (y se comprueba su sha256: si no cuadra, no se decide).
- n_{M+1} en vivo: sesiones de la NYSE del mes siguiente (`sesiones_nyse`, reglas del calendario de la NYSE).
- σ*′: mediana de σ̂′ en 1963-07 … 2004-12 (misma medida, coeficientes congelados, dentro de muestra; declarado).
Separado de src/factors/ como live.py: el corte ≤ 2004 sigue allí; aquí solo se leen las últimas ~70 sesiones.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from dateutil.easter import easter

REPO = Path(__file__).resolve().parents[2]
LOG = REPO / "research" / "paper" / "decisiones_b1prima.jsonl"
CONGELADO = REPO / "research" / "paper" / "b1prima_congelado.json"
ACTIVO = REPO / "research" / "paper" / "ACTIVO"
# mismas reglas que B1 (tests/test_b1prima.py comprueba que coinciden con src/paper/live.py)
ESTRATEGICO = {"rv": 0.70, "rf": 0.15, "oro": 0.15}
RV_MIN, UMBRAL = 0.55, 0.025
MAX_DIAS_SIN_DATO = 5
VENTANAS = (5, 21, 63)
HAR = [f"lrv{n}" for n in VENTANAS]
EUR_DEM = 1.95583
DECIMALES = 12                      # redondeo de los parámetros congelados antes del sha256


# ============================================================================ calendario de la NYSE
# Cierres extraordinarios ya anunciados/ocurridos (≥ 2005). Uno futuro no anunciado no se puede prever (declarado).
CIERRES_ESPECIALES = {pd.Timestamp(x) for x in ("2007-01-02", "2012-10-29", "2012-10-30", "2018-12-05", "2025-01-09")}


def _observado(d: pd.Timestamp, sabado_a_viernes: bool = True) -> pd.Timestamp | None:
    if d.weekday() == 5:
        return d - pd.Timedelta(days=1) if sabado_a_viernes else None
    if d.weekday() == 6:
        return d + pd.Timedelta(days=1)
    return d


def _n_esimo(año: int, mes: int, dia_semana: int, n: int) -> pd.Timestamp:
    """n-ésimo `dia_semana` (0 = lunes) del mes; n = −1 → el último."""
    dias = pd.date_range(f"{año}-{mes:02d}-01", periods=pd.Period(f"{año}-{mes:02d}").days_in_month)
    dias = dias[dias.weekday == dia_semana]
    return dias[n if n < 0 else n - 1]


def festivos_nyse(año: int) -> set[pd.Timestamp]:
    """Festivos de la NYSE (regla 7.2) para años ≥ 2005. Año Nuevo en sábado no se adelanta al viernes (regla NYSE)."""
    if año < 2005:
        raise ValueError("calendario de reglas solo para años ≥ 2005 (antes se usan las sesiones observadas)")
    T = pd.Timestamp
    f = {_observado(T(f"{año}-01-01"), sabado_a_viernes=False),
         _n_esimo(año, 1, 0, 3), _n_esimo(año, 2, 0, 3),                    # Martin Luther King, Presidents
         T(easter(año)) - pd.Timedelta(days=2),                             # Viernes Santo
         _n_esimo(año, 5, 0, -1),                                           # Memorial
         _observado(T(f"{año}-07-04")), _n_esimo(año, 9, 0, 1),             # Independencia, Labor
         _n_esimo(año, 11, 3, 4), _observado(T(f"{año}-12-25"))}            # Acción de Gracias, Navidad
    if año >= 2022:
        f.add(_observado(T(f"{año}-06-19")))                                # Juneteenth
    return {d for d in f if d is not None} | {d for d in CIERRES_ESPECIALES if d.year == año}


def sesiones_nyse(mes: pd.Period) -> int:
    dias = pd.bdate_range(mes.start_time, mes.end_time.normalize())
    fest = festivos_nyse(mes.year)
    return int(sum(d not in fest for d in dias))


# ============================================================================ medida: RV de EE. UU. en EUR, diaria
def r_eur_diario(r_usd: pd.Series, eur_por_usd: pd.Series) -> pd.Series:
    """r_usd: rendimiento diario en USD (decimal) por sesión de EE. UU.; eur_por_usd: fixing diario. El fixing se lleva
    al último conocido en cada sesión (los movimientos de la divisa en días sin sesión entran en la sesión siguiente).
    Las sesiones anteriores al primer fixing se descartan."""
    r_usd = r_usd.dropna().sort_index()
    x = eur_por_usd.dropna().sort_index()
    x = x[~x.index.duplicated(keep="last")]
    xs = x.reindex(x.index.union(r_usd.index)).ffill().reindex(r_usd.index)
    out = ((1 + r_usd) * (xs / xs.shift(1)) - 1).dropna()
    return out.rename("r_eur")


def precio_a_rendimiento(p: pd.Series) -> pd.Series:
    p = p.dropna().sort_index()
    return p.pct_change().dropna()


def rasgos_har(r: pd.Series) -> pd.DataFrame:
    """Por mes (Period): log(media de r² de las últimas 5/21/63 sesiones + 1e-12) en la última sesión del mes, y la
    fecha de esa sesión. Idéntico a src/intl/int12.rasgos_diarios (columnas HAR; un test lo comprueba)."""
    r = r.dropna().sort_index()
    r2 = r ** 2
    f = pd.DataFrame({f"lrv{n}": np.log(r2.rolling(n, min_periods=n).mean() + 1e-12) for n in VENTANAS})
    f["sesion"] = r.index
    return f.groupby(r.index.to_period("M")).last()


# ============================================================================ estimación (una vez) y congelación
def estimar(r_eur: pd.Series, desde: str = "1963-07", hasta: str = "2004-11") -> dict:
    """log-HAR con los orígenes M ∈ [desde, hasta] (objetivo: RV de M + 1, n = sesiones observadas de M + 1).
    Usa src/intl/int12 (tabla_objetivos, Modelo("har")) tal cual: la misma estimación que P-DEV-INT12."""
    from src.intl import int12 as M
    T = M.tabla_objetivos(r_eur, 1).join(rasgos_har(r_eur)[HAR], how="left")
    T = T[(T.index >= pd.Period(desde, "M")) & (T.index <= pd.Period(hasta, "M"))]
    if T[HAR].isna().any().any():
        raise RuntimeError("rasgos HAR incompletos en la muestra de estimación")
    y = np.log(T["rv"].values / T["n_dias"].values)
    mod = M.Modelo("har").ajustar(T, y)
    return {"beta": [float(b) for b in mod.beta], "duan": float(mod.smear), "n_meses": int(len(T)),
            "desde": str(T.index.min()), "hasta": str(T.index.max()), "fin_objetivo": str(T["fin"].max().date()),
            "_tabla": T}


def prevision(x: np.ndarray, n_dias, beta, duan) -> np.ndarray:
    """f = n · exp(β₀ + β·x) · Duan (varianza del mes siguiente)."""
    x = np.atleast_2d(np.asarray(x, float))
    return np.asarray(n_dias, float) * np.exp(beta[0] + x @ np.asarray(beta[1:], float)) * duan


def sigma_prima(f) -> np.ndarray:
    return np.sqrt(12 * np.asarray(f, float))


def parametros_canonicos(p: dict) -> dict:
    return {"beta": [round(float(b), DECIMALES) for b in p["beta"]], "duan": round(float(p["duan"]), DECIMALES),
            "sigma_star_prima": round(float(p["sigma_star_prima"]), DECIMALES)}


def sha256_parametros(p: dict) -> str:
    txt = json.dumps(parametros_canonicos(p), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(txt.encode()).hexdigest()


def sha256_serie(s: pd.Series) -> str:
    """Huella de los datos de entrada (fechas y valores redondeados a 1e-12): detecta revisiones de la fuente."""
    txt = "\n".join(f"{d.date()},{v:.12e}" for d, v in s.items())
    return hashlib.sha256(txt.encode()).hexdigest()


def cargar_congelado(ruta: Path = CONGELADO) -> dict:
    """Parámetros congelados; falla cerrado si falta el fichero o el sha256 no cuadra."""
    if not ruta.exists():
        raise RuntimeError(f"{ruta}: faltan los coeficientes congelados de B1′ (scripts/b1prima_congelar.py)")
    c = json.loads(ruta.read_text())
    p = c["parametros"]
    if sha256_parametros(p) != c["sha256_parametros"]:
        raise RuntimeError(f"{ruta}: el sha256 de los parámetros no cuadra (¿editado a mano?): no se decide")
    return p


# ============================================================================ decisión en vivo
@dataclass
class DecisionB1p:
    cierre: str
    sigma_hat_prima: float
    f_varianza_mes: float
    n_sesiones_mes_siguiente: int
    rasgos: dict
    rv_b1p_bruta: float
    b0: dict
    b1prima: dict
    cambio_b1prima: bool
    sigma_star_prima: float
    sha256_parametros: str
    datos: dict


def rv_regla(sigma_hat: float, previo: float, sigma_star: float) -> tuple[float, float, bool]:
    """La regla de B1 con σ*′ y σ̂′ (src/paper/live.rv_b1)."""
    bruta = float(np.clip(ESTRATEGICO["rv"] * min(1.0, sigma_star / sigma_hat), RV_MIN, ESTRATEGICO["rv"]))
    if abs(bruta - previo) >= UMBRAL - 1e-12:
        return bruta, bruta, True
    return bruta, previo, False


def ultimo_b1p(log: Path | None = None) -> float:
    log = log or LOG
    if not log.exists():
        return ESTRATEGICO["rv"]
    lineas = [json.loads(x) for x in log.read_text().splitlines() if x.strip()]
    return float(lineas[-1]["b1prima"]["rv"]) if lineas else ESTRATEGICO["rv"]


def _diaria(con, sid: str, hasta: pd.Timestamp, desde: pd.Timestamp) -> pd.Series:
    df = con.execute("select date, value from obs_latest where series_id = ? and value is not null and date <= ? "
                     "and date >= ? order by date", [sid, hasta.date(), desde.date()]).df()
    s = pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["date"]))
    s = s[~s.index.duplicated(keep="last")]
    if s.empty or (hasta - s.index.max()).days > MAX_DIAS_SIN_DATO:
        raise RuntimeError(f"{sid}: sin dato reciente para el cierre {hasta.date()} (último {s.index.max() if len(s) else None})")
    return s


def comprobar_sesiones(sp: pd.Series, meses: list[pd.Period]) -> None:
    """Falla cerrado si en algún mes de la ventana faltan sesiones respecto al calendario de la NYSE (dato que falta)."""
    for m in meses:
        n_obs = int((sp.index.to_period("M") == m).sum())
        n_cal = sesiones_nyse(m)
        if n_obs < n_cal:
            raise RuntimeError(f"SP500: {n_obs} sesiones en {m}, el calendario de la NYSE dice {n_cal}: faltan datos")


def decidir(cierre: pd.Timestamp, con=None, congelado: Path = CONGELADO, log: Path | None = None) -> DecisionB1p:
    p = cargar_congelado(congelado)
    propia = con is None
    if propia:
        from src.warehouse import db
        con = db.connect(read_only=True)
    try:
        desde = cierre - pd.Timedelta(days=150)
        sp, fx = _diaria(con, "SP500", cierre, desde), _diaria(con, "ecb_eurusd_d", cierre, desde - pd.Timedelta(days=10))
    finally:
        if propia:
            con.close()
    ultimo_mes = cierre.to_period("M")
    r = r_eur_diario(precio_a_rendimiento(sp), 1 / fx)
    if len(r) < max(VENTANAS):
        raise RuntimeError(f"solo {len(r)} rendimientos diarios (hacen falta {max(VENTANAS)})")
    ventana = r.iloc[-max(VENTANAS):]
    meses = sorted(set(ventana.index.to_period("M")) | {ultimo_mes})
    comprobar_sesiones(sp, [m for m in meses if m > ventana.index[0].to_period("M")])   # el primero puede ser parcial
    F = rasgos_har(r)
    if F.index[-1] != ultimo_mes:
        raise RuntimeError(f"sin sesiones en {ultimo_mes}")
    x = F.loc[ultimo_mes, HAR].values.astype(float)
    n = sesiones_nyse(ultimo_mes + 1)
    f = float(prevision(x, n, p["beta"], p["duan"])[0])
    sig = float(sigma_prima(f))
    bruta, rv, cambio = rv_regla(sig, ultimo_b1p(log), p["sigma_star_prima"])
    b1p = {"rv": round(rv, 4), "rf": round(1 - ESTRATEGICO["oro"] - rv, 4), "oro": ESTRATEGICO["oro"]}
    return DecisionB1p(str(cierre.date()), round(sig, 5), f, n, {k: round(float(v), 6) for k, v in zip(HAR, x)},
                       round(bruta, 4), dict(ESTRATEGICO), b1p, cambio, p["sigma_star_prima"], sha256_parametros(p),
                       {"sp500_ultimo": str(sp.index[-1].date()), "eurusd_ultimo": str(fx.index[-1].date()),
                        "primera_sesion_63": str(ventana.index[0].date()), "ultima_sesion": str(ventana.index[-1].date())})


def registrar(d: DecisionB1p, extra: dict, log: Path | None = None) -> None:
    log = log or LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a") as fh:
        fh.write(json.dumps({**asdict(d), **extra}, ensure_ascii=False) + "\n")
