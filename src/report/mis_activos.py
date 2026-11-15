"""«Mis activos»: acciones, ETF y materias primas que sigue el usuario (lista en src/ingest/yahoo_precios.py).

DESCRIPTIVO y NO VALIDADO. Nada de esto ha pasado una prueba fuera de muestra (las acciones individuales tienen poca
historia y un solo camino; ver INT-2/INT-8/INT-10: falta de episodios). No es una recomendación de compra o venta.

Por activo:
1. Situación: último precio y fecha, rentabilidad 1 m / 3 m / en el año / 12 m (por fecha de calendario), volatilidad
   anualizada de 1 año (diaria, 252), caída desde el máximo de 52 semanas, beta y correlación con el S&P 500 (SPY,
   semanal, 3 años).
2. Comportamiento por cuadrante mensual de EE. UU. (regime_monthly, point-in-time): rentabilidad mensual media
   anualizada (×12) y % de meses positivos, con el número de meses. Pocos meses → poco fiable (se marca).
3. Dos simulaciones a 12 meses (rentabilidad NOMINAL en la moneda del activo), con semilla fija:
   A «historia propia»: bootstrap estacionario de bloques (media 6 meses) de sus rentabilidades mensuales desde que
     cotiza. Arrastra la tendencia pasada: un activo que subió mucho «hereda» esa subida (sesgo optimista declarado).
   B «enlazada al motor» (solo activos en USD): modelo de mercado sin alfa,
     r = rf + β·(r_mercado − rf) + ε, con r_mercado = escenarios de la bolsa de EE. UU. del motor INT-11 (real, se le
     suma la inflación prevista por el FMI para el año siguiente), rf = letra a 3 meses (DTB3) y ε = suma de 12
     residuos mensuales remuestreados de los últimos 10 años. Sin alfa: no supone que lo que batió al mercado lo siga
     haciendo.
   Ambas dan p5 / p25 / p50 / p75 / p95, P(pérdida) y P(caída ≥ 20 %).
Petróleo (BZ=F, CL=F): precio del futuro de 1.er vencimiento encadenado (no invertible tal cual; los cambios de
contrato meten saltos) y se usan solo cierres de mes positivos (el WTI cerró en negativo el 20-abr-2020).
Historia corta (menos de MIN_DIAS sesiones, p. ej. VYLR, que cotiza desde el 1-oct-2026): solo precio y las rentabilidades
cuya fecha de partida existe; sin volatilidad de 1 año, caída desde máximo de 52 semanas, beta, cuadrantes ni
simulaciones (se muestra «historia insuficiente (desde …)»). No se inventa historia anterior. Con menos de
MIN_DIAS_PRECIO sesiones no se muestra nada.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

SEMILLA = 20261112
N_SIM = 20000
BLOQUE = 6
MIN_MESES = 60
MIN_DIAS = 260        # ~1 año de sesiones: por debajo, «historia corta» (sin volatilidad 1 a, beta, cuadrantes ni sims)
MIN_DIAS_PRECIO = 5   # por debajo ni siquiera se enseña el precio
NOTAS = {
    "CTVA": "Corteva escindió su negocio de semillas (Vylor, VYLR) el 1-oct-2026, 1 acción VYLR por cada CTVA; "
            "desde entonces CTVA es solo protección de cultivos. Yahoo lo ajustó como «split» 6,665:1, que reescala "
            "toda su historia: las rentabilidades anteriores a oct-2026 son de la empresa entera, no de la actual. "
            "La caída del 12-nov no es la escisión. CTVA + VYLR (1 por acción) = la Corteva anterior a la escisión "
            "(el panel no construye la serie combinada).",
    "VYLR": "Vylor: negocio de semillas escindido de Corteva (CTVA) el 1-oct-2026, 1 VYLR por cada CTVA. Cotiza desde "
            "entonces: sin historia propia anterior (no se reconstruye). Quien tenía CTVA antes de la escisión tiene ahora "
            "CTVA + VYLR, que juntas equivalen a la Corteva anterior.",
    "BZ=F": "Futuro de 1.er vencimiento encadenado: no es invertible tal cual (los cambios de contrato meten saltos).",
    "CL=F": "Futuro de 1.er vencimiento encadenado: no es invertible tal cual; cerró en negativo el 20-abr-2020.",
    "BAYN.DE": "Cotiza en euros: sin simulación enlazada al motor (que es de la bolsa de EE. UU. en dólares).",
}
DIR = Path(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")).expanduser() / "mercados"


def _hasta(s: pd.Series, f: pd.Timestamp):
    x = s[s.index <= f]
    return float(x.iloc[-1]) if len(x) else None


def _ret(s: pd.Series, f0: pd.Timestamp):
    a, b = _hasta(s, f0), float(s.iloc[-1])
    return None if a is None or a <= 0 else 100 * (b / a - 1)


def _mensual(s: pd.Series) -> pd.Series:
    m = s.resample("ME").last().dropna()
    m = m[m > 0]
    return np.log(m).diff().dropna()


def _bootstrap(r: np.ndarray, n: int, h: int, rng) -> np.ndarray:
    """Bootstrap estacionario (Politis-Romano) de longitud h; devuelve la suma de log-rentabilidades (n,)."""
    T = len(r)
    out = np.zeros(n)
    pos = rng.integers(0, T, n)
    for k in range(h):
        nuevo = rng.random(n) < 1 / BLOQUE
        pos = np.where(nuevo, rng.integers(0, T, n), (pos + 1) % T)
        out += r[pos]
    return out


def _resumen(ret_simple: np.ndarray) -> dict:
    q = np.percentile(ret_simple, [5, 25, 50, 75, 95])
    return {"p5": q[0], "p25": q[1], "p50": q[2], "p75": q[3], "p95": q[4],
            "p_perdida": float((ret_simple < 0).mean()), "p_caida20": float((ret_simple <= -0.20).mean())}


def _mercado_motor(escenarios: dict | None, infl_fmi: float | None, n: int, rng):
    """Muestras de la rentabilidad NOMINAL de la bolsa de EE. UU. a 12 m a partir de la rejilla 1..99 del motor."""
    try:
        q = escenarios["paises"]["USA"]["cuantiles_1_99"]["bolsa"]
    except (KeyError, TypeError):
        return None
    q = np.asarray(q, float)
    u = rng.uniform(0.01, 0.99, n)
    real = np.interp(u, np.arange(1, 100) / 100, q)
    return (1 + real) * (1 + (infl_fmi or 0) / 100) - 1


def _corta(t: str, s: pd.Series, m: dict, f: pd.Timestamp) -> dict:
    """Activo con menos de ~1 año de historia: precio y rentabilidades con base real; nada estadístico."""
    txt = f"historia insuficiente (desde {s.index[0].date()})"
    avisos = [f"{txt}: {len(s)} sesiones. Sin volatilidad de 1 año, beta, cuadrantes ni simulaciones."]
    if t in NOTAS:
        avisos.append(NOTAS[t])
    return {**m, "precio": float(s.iloc[-1]), "fecha": str(f.date()),
            "r_1m": _ret(s, f - pd.DateOffset(months=1)), "r_3m": _ret(s, f - pd.DateOffset(months=3)),
            "r_ytd": _ret(s, pd.Timestamp(f.year - 1, 12, 31)), "r_12m": _ret(s, f - pd.DateOffset(years=1)),
            "r_3a_anual": None, "vol_1a": None, "caida_max52": None, "historia_insuficiente": txt,
            "sesiones": int(len(s)), "avisos": avisos}


def analizar(con=None, hoy: date | None = None, escenarios: dict | None = None, infl_usa: float | None = None,
             rf: float | None = None) -> dict:
    pp = DIR / "precios_diarios.parquet"
    if not pp.exists():
        return {"error": "sin precios (src/ingest/yahoo_precios.py no se ha ejecutado)"}
    P = pd.read_parquet(pp)
    meta = json.loads((DIR / "activos.json").read_text())
    hoy_ts = pd.Timestamp(hoy or date.today())
    reg = None
    if con is not None:
        try:
            reg = con.execute("select date, quadrant from regime_monthly order by date").fetchdf()
            reg = reg.set_index(pd.DatetimeIndex(reg["date"]).to_period("M"))["quadrant"]
        except Exception:  # noqa: BLE001
            reg = None
    spy = P["SPY"].dropna() if "SPY" in P else None
    spy_m = _mensual(spy) if spy is not None else None
    rng = np.random.default_rng(SEMILLA)
    mkt = _mercado_motor(escenarios, infl_usa, N_SIM, rng)
    rf = rf if rf is not None else 0.0
    out = {}
    for t, m in meta["activos"].items():
        s = P[t].dropna() if t in P else pd.Series(dtype=float)
        s = s[s > 0]
        if len(s) < MIN_DIAS_PRECIO:
            desde = f" (desde {s.index[0].date()})" if len(s) else ""
            out[t] = {**m, "error": f"historia insuficiente{desde}"}
            continue
        f = s.index[-1]
        if len(s) < MIN_DIAS:
            out[t] = _corta(t, s, m, f)
            continue
        d = np.log(s).diff().dropna()
        ult1a = d[d.index > f - pd.DateOffset(years=1)]
        r = {**m, "precio": float(s.iloc[-1]), "fecha": str(f.date()),
             "r_1m": _ret(s, f - pd.DateOffset(months=1)), "r_3m": _ret(s, f - pd.DateOffset(months=3)),
             "r_ytd": _ret(s, pd.Timestamp(f.year - 1, 12, 31)), "r_12m": _ret(s, f - pd.DateOffset(years=1)),
             "r_3a_anual": None, "vol_1a": float(ult1a.std() * np.sqrt(252) * 100),
             "caida_max52": 100 * (float(s.iloc[-1]) / float(s[s.index > f - pd.DateOffset(weeks=52)].max()) - 1)}
        avisos = []
        ult5 = d[d.index > f - pd.DateOffset(days=10)]
        if len(ult5) and float(ult5.abs().max()) > 0.15:
            dia = ult5.abs().idxmax()
            avisos.append(f"movimiento de {100 * np.expm1(float(ult5[dia])):+.0f} % el {dia.date()}: comprobar si es un "
                          "evento corporativo (escisión, ampliación…) antes de leer las rentabilidades recientes")
        if t in NOTAS:
            avisos.append(NOTAS[t])
        r["avisos"] = avisos
        r3 = _ret(s, f - pd.DateOffset(years=3))
        r["r_3a_anual"] = None if r3 is None else 100 * ((1 + r3 / 100) ** (1 / 3) - 1)
        # beta y correlación semanal 3 años frente a SPY
        if spy is not None and t != "SPY":
            w = pd.concat([s, spy], axis=1, keys=["a", "m"]).dropna()
            w = w[w.index > f - pd.DateOffset(years=3)].resample("W-FRI").last().dropna()
            lw = np.log(w).diff().dropna()
            if len(lw) > 100:
                c = np.cov(lw["a"], lw["m"])
                r["beta_3a"] = float(c[0, 1] / c[1, 1])
                r["corr_3a"] = float(np.corrcoef(lw["a"], lw["m"])[0, 1])
        # por cuadrante
        mm = _mensual(s)
        if reg is not None and len(mm):
            j = pd.DataFrame({"r": mm.values}, index=mm.index.to_period("M")).join(reg, how="inner")
            por = {}
            for q, g in j.groupby("quadrant"):
                por[q] = {"anual": float(g["r"].mean() * 12 * 100), "positivos": float((g["r"] > 0).mean() * 100),
                          "meses": int(len(g))}
            r["por_cuadrante"] = por
        # simulación A (historia propia)
        if len(mm) >= MIN_MESES:
            la = _bootstrap(mm.values, N_SIM, 12, rng)
            r["sim_historia"] = {**_resumen(np.expm1(la)), "meses_historia": int(len(mm)),
                                 "desde": str(mm.index[0].date())[:7]}
        # simulación B (enlazada al motor), solo USD y con SPY
        if mkt is not None and m.get("moneda") == "USD" and spy_m is not None and t != "SPY":
            j = pd.concat([mm, spy_m], axis=1, keys=["a", "m"]).dropna()
            j = j[j.index > f - pd.DateOffset(years=10)]
            if len(j) >= MIN_MESES:
                b = float(np.cov(j["a"], j["m"])[0, 1] / np.var(j["m"], ddof=1))
                res = (j["a"] - j["a"].mean()) - b * (j["m"] - j["m"].mean())
                eps = res.values[rng.integers(0, len(res), (N_SIM, 12))].sum(axis=1)
                lr = np.log1p(rf / 100) + b * (np.log1p(mkt) - np.log1p(rf / 100)) + eps
                r["sim_motor"] = {**_resumen(np.expm1(lr)), "beta_10a": b, "meses": int(len(j)),
                                  "vol_idio_anual": float(res.std(ddof=1) * np.sqrt(12) * 100)}
        out[t] = r
    return {"fecha": str(hoy_ts.date()), "descarga": meta.get("descarga"), "fuente": meta.get("fuente"),
            "activos": out, "supuestos": {"rf_3m": rf, "inflacion_usa_fmi": infl_usa, "n_sim": N_SIM, "semilla": SEMILLA,
                                          "bloque_meses": BLOQUE},
            "aviso": "Descriptivo y no validado; no es una recomendación de compra o venta."}
