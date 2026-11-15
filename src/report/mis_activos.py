"""«Mis activos»: acciones, ETF y materias primas que sigue el usuario (lista en src/ingest/yahoo_precios.py).

DESCRIPTIVO y NO VALIDADO. Nada de esto ha pasado una prueba fuera de muestra (las acciones individuales tienen poca
historia y un solo camino; ver INT-2/INT-8/INT-10: falta de episodios). No es una recomendación de compra o venta.

Por activo:
1. Situación: último precio y fecha, rentabilidad 1 m / 3 m / en el año / 12 m (por fecha de calendario), volatilidad
   anualizada de 1 año (diaria, 252), caída desde el máximo de 52 semanas, beta y correlación con el S&P 500 (SPY,
   semanal, 3 años).
2. Comportamiento por cuadrante mensual de EE. UU. (regime_monthly, point-in-time): rentabilidad mensual media
   anualizada (×12) y % de meses positivos, con el número de meses. Pocos meses → poco fiable (se marca).
3. Dos simulaciones a 12 meses con semilla fija (cada una con su propio generador aleatorio):
   A «historia propia» (rentabilidad NOMINAL en la moneda del activo): bootstrap estacionario de bloques (media
     6 meses) de sus rentabilidades mensuales desde que cotiza. Arrastra la tendencia pasada: un activo que subió mucho
     «hereda» esa subida (sesgo optimista declarado).
   B «enlazada al motor» (solo activos en USD): modelo de mercado sin alfa sobre CADA TRAYECTORIA del motor INT-11
     v3.1 de EE. UU. (bolsa real e inflación conjuntas; la emisión del signal se reproduce en solo lectura con la misma
     llamada, semilla y estado que scripts/int11_v3_hoy.py y se comprueba contra los cuantiles publicados):
       log(1 + mercado nominal) = log(1 + bolsa real) + π   (π = inflación de ESA trayectoria, Δlog del IPC medio)
       log(1 + activo nominal) = rf + β·(mercado nominal − rf) + ε
       log(1 + activo real)    = log(1 + activo nominal) − π   (misma π: real y nominal son coherentes por trayectoria)
     rf = letra a 3 meses (DTB3), β y ε (suma de 12 residuos mensuales remuestreados) de los últimos 10 años hasta el
     último precio. Sin alfa: no supone que lo que batió al mercado lo siga haciendo. Se usan TODAS las trayectorias
     del motor (sin rejilla p1-p99 ni recorte de colas); si alguna bolsa real ≤ −100 % hubiera que acotarla para el
     logaritmo, se cuenta y se rotula.
     B′ (informativa): igual, con una segunda beta a la inflación mensual del IPC de EE. UU. (CPIAUCSL), estimada
     con los meses cuyo IPC ya estaba publicado en la fecha del último precio (mes + 1 mes + 15 días ≤ fecha).
     Rentabilidad real = nominal − π de la misma trayectoria. Beta mensual aplicada a la inflación anual del motor
     (aproximación declarada); su error típico va en la ficha.
   Todas dan p5 / p25 / p50 / p75 / p95 (y mínimo, p1, p99, máximo informativos), P(pérdida) y P(caída ≥ 20 %).
   Supuestos que quedan (declarados): la inflación del motor es la del IPC medio de la ventana del motor (12 meses
   desde el mes siguiente a su emisión), no la de diciembre a diciembre del activo; residuos i. i. d. (sin bloques);
   β con rentabilidades brutas (no en exceso).
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
    """Distribución COMPLETA (sin recortar colas): p5…p95 y, informativos, mínimo, p1, p99 y máximo."""
    x = np.asarray(ret_simple, float)
    q = np.percentile(x, [1, 5, 25, 50, 75, 95, 99])
    return {"p5": q[1], "p25": q[2], "p50": q[3], "p75": q[4], "p95": q[5],
            "min": float(x.min()), "p1": q[0], "p99": q[6], "max": float(x.max()),
            "p_perdida": float((x < 0).mean()), "p_caida20": float((x <= -0.20).mean()), "n": int(len(x))}


# ---------------------------------------------------------------- trayectorias del motor INT-11 v3.1 (solo lectura)
def trayectorias_motor(emision: str, con=None, ref: dict | None = None, pais: str = "USA", tol: float = 1e-3) -> dict:
    """Reproduce en SOLO LECTURA la emisión `emision` del motor INT-11 v3.1 para `pais` con la misma llamada que
    `scripts.int11_v3_hoy.pais_escenario` (Config.v3_1 ajustado con las filas ≤ 2004, estado móvil de esa fecha,
    pertenencia suave, 200 lotes × POR_LOTE, semilla SEED + índice del país) y devuelve sus trayectorias CONJUNTAS:
    bolsa real simple e inflación (Δlog del IPC medio) de la ventana de 12 meses. No escribe nada ni toca el motor.

    `ref` = {percentil: valor} de la bolsa real publicada (signal o research/int/int11_v3_hoy.json): se comprueba que
    la reproducción coincide (máx. |dif| ≤ tol); si no, se devuelve igualmente y se rotula."""
    from scripts import int11_v3_hoy as H
    from scripts.int11_corrida import NUCLEO
    from scripts.int11_v3_corrida import cargar_real_v3
    from src.intl import data as D
    from src.intl import escenarios as E
    from src.report import escenarios_vivo as V
    cerrar = con is None
    con = con or D.connect()
    try:
        filas = cargar_real_v3(con)
        if filas["año"].max() > 2004:
            raise D.FactorCutoffError("filas > 2004")
        gen = E.Generador(E.Config.v3_1()).ajustar(filas)
        est = V.estado_actual_movil(con, emision)
    finally:
        if cerrar:
            con.close()
    e = est["paises"][pais]
    if e.get("regimen") is None:
        raise ValueError(f"motor: {pais} sin estado")
    esc = gen.simular_suave(pais, e["inflacion"], e["brecha"], horizonte=1, n_lotes=200, por_lote=H.POR_LOTE,
                            semilla=H.SEED + list(NUCLEO).index(pais))
    b = esc.rent[:, 0, list(esc.activos).index("bolsa")]
    pi = esc.inflacion[:, 0]
    ok = np.isfinite(b) & np.isfinite(pi)
    comp = None
    if ref:
        ps = sorted(int(k) for k in ref)
        dif = float(np.max(np.abs(np.percentile(b[ok], ps) - np.array([ref[k] if k in ref else ref[str(k)]
                                                                         for k in ps], float))))
        comp = {"max_dif": dif, "coincide": dif <= tol, "percentiles": len(ps)}
    return {"bolsa_real": b[ok], "inflacion_log": pi[ok], "emision": est["emision"], "corte": est["corte"],
            "ventana": est["ventana_objetivo"], "estado": {k: e.get(k) for k in ("mes_ipc", "inflacion", "brecha")},
            "descartadas": int((~ok).sum()), "comprobacion": comp}


def _cpi_mensual(con) -> pd.Series | None:
    """Inflación mensual Δlog del IPC de EE. UU. (CPIAUCSL), solo entre meses CONSECUTIVOS (el hueco de oct-2025 no
    genera un Δ de dos meses). Índice: fin de mes."""
    if con is None:
        return None
    try:
        df = con.execute("select date, value from obs_latest where series_id = 'CPIAUCSL' and value is not null "
                         "order by date").fetchdf()
    except Exception:  # noqa: BLE001
        return None
    if df.empty:
        return None
    c = pd.Series(df["value"].astype(float).values, index=pd.DatetimeIndex(df["date"]).to_period("M"))
    o = np.array([p.ordinal for p in c.index])
    d = np.log(c).diff()[np.r_[False, np.diff(o) == 1]]
    d.index = d.index.to_timestamp(how="end").normalize()
    return d.dropna()


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


def ipc_publicado(pi_m: pd.Series, f: pd.Timestamp) -> pd.Series:
    """Meses de IPC ya publicados en la fecha f (regla conservadora: el IPC del mes m sale antes del día 15 de m + 1)."""
    pub = (pi_m.index.to_period("M") + 1).to_timestamp() + pd.Timedelta(days=14)
    return pi_m[pub <= f]


def betas(a_m: pd.Series, m_m: pd.Series, f: pd.Timestamp, pi_m: pd.Series | None = None, anos: int = 10) -> dict | None:
    """β de mercado (y, si hay `pi_m`, β a la inflación en una regresión con las dos) con rentabilidades mensuales
    log de la ventana (f − anos, f]. SIN FUGA: nada posterior a f; el IPC solo con los meses publicados en f."""
    j = pd.concat([a_m, m_m], axis=1, keys=["a", "m"]).dropna()
    j = j[(j.index > f - pd.DateOffset(years=anos)) & (j.index <= f + pd.offsets.MonthEnd(0))]
    if len(j) < MIN_MESES:
        return None
    b = float(np.cov(j["a"], j["m"])[0, 1] / np.var(j["m"], ddof=1))
    res = (j["a"] - j["a"].mean()) - b * (j["m"] - j["m"].mean())
    out = {"beta": b, "res": res.values, "meses": int(len(j)), "hasta": str(j.index.max().date())}
    if pi_m is not None:
        k = j.join(ipc_publicado(pi_m, f).rename("pi"), how="inner")
        if len(k) >= MIN_MESES:
            X = np.column_stack([np.ones(len(k)), k["m"], k["pi"]])
            coef, *_ = np.linalg.lstsq(X, k["a"].values, rcond=None)
            e = k["a"].values - X @ coef
            s2 = float(e @ e) / (len(k) - 3)
            se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
            out["inflacion"] = {"beta_m": float(coef[1]), "beta_pi": float(coef[2]), "se_pi": float(se[2]),
                                "res": e - e.mean(), "pi_media_anual": float(k["pi"].mean() * 12),
                                "meses": int(len(k)), "ipc_hasta": str(k.index.max().date())[:7]}
    return out


def mercado_motor(motor: dict) -> dict:
    """log(1 + bolsa nominal) por trayectoria = log(1 + bolsa real) + π de la misma trayectoria. Si alguna bolsa real
    fuera ≤ −100 % (log indefinido) se acota a −99,9 % y se CUENTA (rótulo «recorte por estabilidad numérica»)."""
    b = np.asarray(motor["bolsa_real"], float)
    pi = np.asarray(motor["inflacion_log"], float)
    malas = b <= -0.999
    lb = np.log1p(np.where(malas, -0.999, b))
    return {"l_real": lb, "pi": pi, "l_nom": lb + pi, "recortadas": int(malas.sum())}


def sim_motor(bt: dict, mk: dict, rf: float, rng, con_inflacion: bool = False) -> dict:
    """Devuelve los LOG de la rentabilidad a 12 m del activo por trayectoria del motor: nominal y real (= nominal − π de
    esa misma trayectoria). rf en % anual."""
    lrf = np.log1p(rf / 100)
    n_ = len(mk["l_nom"])
    if con_inflacion:
        x = bt["inflacion"]
        eps = x["res"][rng.integers(0, len(x["res"]), (n_, 12))].sum(axis=1)
        l_nom = lrf + x["beta_m"] * (mk["l_nom"] - lrf) + x["beta_pi"] * (mk["pi"] - x["pi_media_anual"]) + eps
    else:
        eps = bt["res"][rng.integers(0, len(bt["res"]), (n_, 12))].sum(axis=1)
        l_nom = lrf + bt["beta"] * (mk["l_nom"] - lrf) + eps
    return {"l_nom": l_nom, "l_real": l_nom - mk["pi"]}


def analizar(con=None, hoy: date | None = None, motor: dict | None = None, rf: float | None = None) -> dict:
    """`motor`: salida de `trayectorias_motor` (o un dict con bolsa_real / inflacion_log); None → sin simulación B."""
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
    pi_m = _cpi_mensual(con)
    spy = P["SPY"].dropna() if "SPY" in P else None
    spy_m = _mensual(spy) if spy is not None else None
    rng = np.random.default_rng(SEMILLA)                 # A
    rng_b = np.random.default_rng([SEMILLA, 2])          # B y B′ (independiente: B no altera la semilla de A)
    mk = mercado_motor(motor) if motor is not None else None
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
        # simulación B (enlazada al motor, trayectoria a trayectoria), solo USD
        if mk is not None and m.get("moneda") == "USD" and spy_m is not None:
            bt = betas(mm, spy_m, f, pi_m)
            if bt is not None:
                x = sim_motor(bt, mk, rf, rng_b)
                r["sim_motor"] = {**_resumen(np.expm1(x["l_nom"])), "real": _resumen(np.expm1(x["l_real"])),
                                  "beta_10a": bt["beta"], "meses": bt["meses"], "hasta": bt["hasta"],
                                  "vol_idio_anual": float(bt["res"].std(ddof=1) * np.sqrt(12) * 100),
                                  "recortadas": mk["recortadas"]}
                if "inflacion" in bt:
                    xi = sim_motor(bt, mk, rf, rng_b, con_inflacion=True)
                    bi = bt["inflacion"]
                    r["sim_motor_infl"] = {**_resumen(np.expm1(xi["l_nom"])), "real": _resumen(np.expm1(xi["l_real"])),
                                           **{k: bi[k] for k in ("beta_m", "beta_pi", "se_pi", "pi_media_anual",
                                                                 "meses", "ipc_hasta")}}
        out[t] = r
    sup = {"rf_3m": rf, "n_sim": N_SIM, "semilla": SEMILLA, "bloque_meses": BLOQUE}
    if motor is not None:
        sup["motor"] = {"emision": motor.get("emision"), "corte": motor.get("corte"), "ventana": motor.get("ventana"),
                        "estado": motor.get("estado"), "comprobacion": motor.get("comprobacion"),
                        "trayectorias": int(len(mk["l_nom"])), "recortadas": mk["recortadas"],
                        "inflacion": _resumen(np.expm1(mk["pi"])), "bolsa_real": _resumen(np.expm1(mk["l_real"])),
                        "bolsa_nominal": _resumen(np.expm1(mk["l_nom"])),
                        "corr_bolsa_inflacion": float(np.corrcoef(mk["l_real"], mk["pi"])[0, 1])}
    return {"fecha": str(hoy_ts.date()), "descarga": meta.get("descarga"), "fuente": meta.get("fuente"),
            "activos": out, "supuestos": sup,
            "aviso": "Descriptivo y no validado; no es una recomendación de compra o venta."}
