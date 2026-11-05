"""INT-11, registro en vivo: rentabilidad REALIZADA de bonos, letras, vivienda y oro por país, y semáforo de cobertura
(docs/int/INT11_vivo_realizado_v0.md, BORRADOR pendiente de aprobación).

Qué exige el registro (docs/int/INT11_registro_vivo.md §3): por país del núcleo, la rentabilidad REAL de 12 meses, en
MONEDA LOCAL, de cada activo en la ventana de la emisión, lo más parecida posible a la variable JST con la que aprendió
el motor (src/intl/activos3b.py, scripts/int11_corrida.COL):
  bonos    JST `bond_tr` (bono del Estado a ≈ 10 años, rentabilidad total)  → OCDE `oecd_irlt_<p>` (media mensual del
           rendimiento a 10 años) con la fórmula de duración y convexidad de `src/intl/returns.bono_tr_mensual`,
           encadenada en los 12 meses de la ventana;
  letras   JST `bill_rate` (= tipo corto MEDIO del año, `stir`/100)           → OCDE `oecd_ir3m_<p>`, media de los 12
           meses de la ventana (GBR: empalme con el OIS a 3 m del BoE, docs/int/GBR_3m_sustituto.md);
  vivienda JST `housing_tr` = plusvalía + alquiler (`rent_rtn` = rent_yd · (1 + plusvalía)), con precios MEDIOS anuales →
           precio BIS (`bis_spp_<iso2>_n`, trimestral; media de los 4 trimestres de la ventana / media de los 4
           anteriores) + rentabilidad por alquiler encadenada desde el rent_yd JST de 2004 con el índice de alquileres
           y el de precios de la OCDE (Analytical house prices: RPI y HPI); sin índice de alquileres, el rent_yd queda
           fijo en el ancla (respaldo declarado);
  oro      motor = oro en USD (media de diciembre, Banco Mundial) × tipo de cambio JST de fin de año → `gold_wb_usd_m`
           (media mensual del último mes de la ventana / la del mes anterior a la ventana) × tipo de cambio de FIN DE
           MES FRED H.10 (el mismo que la bolsa).
Deflactor: el de la bolsa (IPC OCDE, media de los 12 meses de la ventana / media de los 12 anteriores).

Funciones PURAS (series de pandas → números/dict) salvo `leer_realizado_activos`, que lee el warehouse (nunca JST ≥ 2005:
el único dato JST es el rent_yd de 2004, con `src.intl.data.load_dev`). Convención de fechas: series mensuales
fechadas el día 1 del mes; trimestrales fechadas el día 1 del primer mes del trimestre (como el warehouse).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from src.intl.returns import bono_tr_mensual
from src.report import bolsa_vivo as B

NUCLEO = B.NUCLEO
ACTIVOS_NUEVOS = ("bonos", "letras", "vivienda", "oro")
ISO2 = {"BEL": "be", "DEU": "de", "DNK": "dk", "ESP": "es", "FIN": "fi", "FRA": "fr", "GBR": "gb", "ITA": "it",
        "JPN": "jp", "NLD": "nl", "NOR": "no", "PRT": "pt", "SWE": "se", "USA": "us"}
SERIES = {"bonos": "oecd_irlt_{p}", "letras": "oecd_ir3m_{p}", "vivienda_precio": "bis_spp_{i2}_n",
          "vivienda_alquiler": "oecd_rpi_{p}_q", "vivienda_precio_ocde": "oecd_hpi_{p}_q", "oro": "gold_wb_usd_m"}
SUSTITUTO_3M = {"GBR": "boe_ois3m_m"}
# V4 (aprobada 5-nov-2026): el RPI OCDE de USA está parado desde 2024-T4; si no cubre la ventana se usa el IPC de
# alquileres de FRED (mensual → media trimestral, fechada a inicio de trimestre). Declarado en la nota del realizado.
SUSTITUTO_ALQUILER = {"USA": "CUSR0000SEHA"}      # docs/int/GBR_3m_sustituto.md (empalme de termometro_vivo)
AÑO_ANCLA_ALQUILER = 2004                  # último rent_yd JST permitido (≤ 2004)
# Meses tras el fin de la ventana en que se lee cada activo (UNA vez; medidos el 2026-11-05, §2 del documento):
# OCDE tipos y Banco Mundial ≈ 1-2 meses; BIS trimestral ≈ 4 meses (JPN ≈ 10, BEL ≈ 7) → 12 para tener los 14.
RETRASO_MESES = {"bolsa": 3, "bonos": 3, "letras": 3, "oro": 3, "vivienda": 12}
FUENTE = {
    "bonos": "OCDE irlt (media mensual, 10 años) → bono a la par 10 años: y_{m−1}/12 − D·Δy + ½·C·Δy², encadenado",
    "letras": "OCDE ir3m, media de los 12 meses de la ventana (como JST bill_rate = stir medio); GBR + OIS 3 m BoE",
    "vivienda": "BIS precio nominal (media de los 4 trimestres de la ventana / media de los 4 anteriores) + alquiler: rent_yd JST "
                "2004 × (RPI/RPI_2004)/(P/P_2004) OCDE; sin RPI, rent_yd fijo en 2004 (respaldo, declarado)",
    "oro": "Banco Mundial (media mensual, USD): último mes de la ventana / mes previo × FX FRED H.10 de fin de mes",
    "deflactor": "IPC OCDE, media de los 12 meses de la ventana / media de los 12 anteriores (como la bolsa)",
    "estado": "APROBADO por el usuario el 5-nov-2026 (docs/int/INT11_vivo_realizado_v0.md §7, V1-V8)"}


def alquiler_trimestral(m: pd.Series) -> pd.Series:
    """Índice mensual → media trimestral (solo trimestres completos), fechada a inicio de trimestre (como el RPI OCDE)."""
    if not len(m):
        return m
    q = m.groupby(m.index.to_period("Q"))
    out = q.mean()[q.count() == 3]
    return pd.Series(out.values, index=out.index.to_timestamp(how="start"))


# ------------------------------------------------------------------------------------------------- bonos y letras
def rent_bono_ventana(y_pct: pd.Series, desde, hasta, n: int = 10) -> dict:
    """Rentabilidad total nominal de la ventana del bono a la par a `n` años con el rendimiento MEDIO mensual (%):
    se encadena `bono_tr_mensual` en los meses de la ventana (hace falta también el mes anterior a la ventana)."""
    m = B.meses_ventana(desde, hasta)
    meses = m.insert(0, m[0] - pd.offsets.MonthBegin(1))
    y = B._mes(y_pct).reindex(meses)
    faltan = [str(x.date())[:7] for x in y.index[y.isna()]]
    if faltan:
        return {"nominal": None, "completo": False, "faltan": faltan}
    r = bono_tr_mensual(y, n).reindex(m)
    return {"nominal": float(np.prod(1 + r.values) - 1), "completo": True, "faltan": []}


def rent_letra_ventana(y_pct: pd.Series, desde, hasta, metodo: str = "media") -> dict:
    """Letras con el tipo a 3 meses mensual (%).
    "media" (principal; como JST bill_rate = media del tipo corto del año): media de los 12 meses de la ventana / 100.
    "encadenada" (descriptiva; src/intl/returns.letra_tr_mensual): Π(1 + y_{m−1}/1200) − 1."""
    m = B.meses_ventana(desde, hasta)
    y = B._mes(y_pct)
    if metodo == "media":
        v = y.reindex(m)
    elif metodo == "encadenada":
        v = y.reindex(m - pd.offsets.MonthBegin(1))
    else:
        raise ValueError(metodo)
    faltan = [str(x.date())[:7] for x in v.index[v.isna()]]
    if faltan:
        return {"nominal": None, "completo": False, "faltan": faltan}
    nom = float(v.mean() / 100) if metodo == "media" else float(np.prod(1 + v.values / 1200) - 1)
    return {"nominal": nom, "completo": True, "faltan": []}


def empalmar_3m(base: pd.Series, sustituto: pd.Series | None) -> tuple[pd.Series, dict | None]:
    """El empalme del termómetro en vivo (docs/int/GBR_3m_sustituto.md): `base` y, desde el mes siguiente a su último
    dato, el sustituto con la diferencia de nivel de los 24 últimos meses de solape si |media| ≥ 0,05 pp."""
    if sustituto is None or sustituto.empty:
        return base, None
    from src.report.termometro_vivo import empalmar
    return empalmar(B._mes(base), B._mes(sustituto))


# ------------------------------------------------------------------------------------------------------- vivienda
def _trimestre(fecha) -> pd.Timestamp:
    """Día 1 del primer mes del trimestre que contiene `fecha`."""
    return pd.Timestamp(fecha).to_period("Q").to_timestamp(how="start")


def _q(s: pd.Series) -> pd.Series:
    s = s.dropna().astype(float)
    i = pd.DatetimeIndex(s.index).to_period("Q")
    if i.duplicated().any():
        raise ValueError(f"{s.name}: dos datos en el mismo trimestre")
    return pd.Series(s.values, index=i.to_timestamp(how="start"), name=s.name).sort_index()


def _trimestres_ventana(desde, hasta) -> tuple[pd.DatetimeIndex, pd.DatetimeIndex]:
    """Los 4 trimestres que terminan en el de `hasta` y los 4 anteriores (en una ventana enero-diciembre: los del año
    y los del año anterior; en otra ventana, aproximación declarada al trimestre)."""
    qf = pd.Timestamp(hasta).to_period("Q")
    v = pd.period_range(qf - 3, qf, freq="Q").to_timestamp(how="start")
    a = pd.period_range(qf - 7, qf - 4, freq="Q").to_timestamp(how="start")
    return v, a


def rent_vivienda_ventana(precio_q: pd.Series, desde, hasta, *, yd_ancla: float | None = None,
                          año_ancla: int = AÑO_ANCLA_ALQUILER, alquiler_q: pd.Series | None = None,
                          modo: str = "media") -> dict:
    """Vivienda con un índice de precios trimestral.
    plusvalía "media" (principal; como JST, cuyo `hpnom` es una MEDIA ANUAL: §3.3 del documento) = media de los 4
    trimestres de la ventana / media de los 4 anteriores − 1; "q4" (descriptiva) = P(trimestre de `hasta`) / P(trimestre
    del mes anterior a `desde`) − 1.
    alquiler (como JST: rent_rtn = rent_yd · (1 + plusvalía)), con rent_yd de la ventana =
        yd_ancla · [R̄(ventana) / R̄(año_ancla)] / [P̄(ventana) / P̄(año_ancla)]          ("indice_alquiler")
    (R̄, P̄ = medias de los trimestres; el rent_yd JST es alquiler del año / precio medio del año); sin índice de
    alquiler, rent_yd = yd_ancla ("alquiler_fijo", respaldo). Sin yd_ancla: solo la plusvalía ("solo_precio",
    declarado: sesgo ≈ −rent_yd)."""
    p = _q(precio_q)
    qv, qa = _trimestres_ventana(desde, hasta)
    if modo == "media":
        falt = [str(x.date())[:7] for x in qv.append(qa) if x not in p.index]
        if not falt:
            pv, cap = float(p[qv].mean()), float(p[qv].mean() / p[qa].mean() - 1)
    elif modo == "q4":
        qf, qi = _trimestre(hasta), _trimestre(pd.Timestamp(desde) - pd.offsets.MonthBegin(1))
        falt = [str(x.date())[:7] for x in (qi, qf) if x not in p.index]
        if not falt:
            pv, cap = float(p[qf]), float(p[qf] / p[qi] - 1)
    else:
        raise ValueError(modo)
    if falt:
        return {"nominal": None, "completo": False, "faltan": falt, "metodo": None, "modo": modo}
    out = {"plusvalia": cap, "completo": True, "faltan": [], "modo": modo}
    if yd_ancla is None:
        return {**out, "nominal": cap, "rent_yd": None, "alquiler": None, "metodo": "solo_precio"}
    yd, metodo = float(yd_ancla), "alquiler_fijo"
    if alquiler_q is not None and not alquiler_q.dropna().empty:
        r = _q(alquiler_q)
        qs_a = pd.period_range(f"{año_ancla}-01-01", f"{año_ancla}-12-31", freq="Q").to_timestamp(how="start")
        if all(q in r.index for q in qv) and all(q in r.index for q in qs_a) and all(q in p.index for q in qs_a):
            yd = float(yd_ancla * (r[qv].mean() / r[qs_a].mean()) / (pv / p[qs_a].mean()))
            metodo = "indice_alquiler"
    alq = yd * (1 + cap)
    return {**out, "nominal": cap + alq, "rent_yd": yd, "alquiler": alq, "metodo": metodo}


# ------------------------------------------------------------------------------------------------------------ oro
def rent_oro_ventana(oro_usd_medio: pd.Series, fx_lpu: pd.Series | None, desde, hasta) -> dict:
    """Oro en moneda local: G(último mes) / G(mes anterior a la ventana) con G la media mensual en USD (Banco Mundial),
    × X(último mes) / X(mes anterior) con X el tipo de cambio de FIN DE MES en unidades locales por USD (None = USA).
    En una ventana enero-diciembre es exactamente la construcción del motor (media de diciembre × FX de fin de año)."""
    m = B.meses_ventana(desde, hasta)
    ini, fin = m[0] - pd.offsets.MonthBegin(1), m[-1]
    g = B._mes(oro_usd_medio)
    falt = [str(x.date())[:7] for x in (ini, fin) if x not in g.index]
    rx = 1.0
    if fx_lpu is not None:
        x = B._mes(fx_lpu)
        falt += [f"fx {str(t.date())[:7]}" for t in (ini, fin) if t not in x.index]
        if not falt:
            rx = float(x[fin] / x[ini])
    if falt:
        return {"nominal": None, "completo": False, "faltan": falt}
    return {"nominal": float(g[fin] / g[ini] * rx - 1), "completo": True, "faltan": []}


# ------------------------------------------------------------------------------------------------------ cabecera
def realizado_activos_pais(desde, hasta, ipc: pd.Series, *, irlt: pd.Series | None = None,
                           ir3m: pd.Series | None = None, precio_viv: pd.Series | None = None,
                           alquiler_viv: pd.Series | None = None, yd_ancla: float | None = None,
                           oro_usd: pd.Series | None = None, fx_lpu: pd.Series | None = None, es_usa: bool = False,
                           metodo_ipc: str = "media") -> dict:
    """Realizado nominal y real de bonos, letras, vivienda y oro de un país en la ventana. Pura: todo ya leído.
    Un activo sin serie o con algún mes que falta → real None (no se rellena ni se mezcla con otra fuente)."""
    infl = B.inflacion_ventana(ipc, desde, hasta, metodo_ipc)
    out = {"ventana": {"desde": str(pd.Timestamp(desde).date()), "hasta": str(pd.Timestamp(hasta).date())},
           "metodo_ipc": metodo_ipc, "inflacion": infl}
    piezas = {
        "bonos": (lambda: rent_bono_ventana(irlt, desde, hasta)) if irlt is not None else None,
        "letras": (lambda: {**rent_letra_ventana(ir3m, desde, hasta, "media"),
                            "descriptiva_encadenada": rent_letra_ventana(ir3m, desde, hasta, "encadenada")["nominal"]})
        if ir3m is not None else None,
        "vivienda": (lambda: rent_vivienda_ventana(precio_viv, desde, hasta, yd_ancla=yd_ancla, alquiler_q=alquiler_viv))
        if precio_viv is not None else None,
        "oro": (lambda: rent_oro_ventana(oro_usd, None if es_usa else fx_lpu, desde, hasta))
        if oro_usd is not None and (es_usa or fx_lpu is not None) else None,
    }
    for a, f in piezas.items():
        if f is None:
            out[a] = {"nominal": None, "real": None, "completo": False, "faltan": ["sin serie"]}
            continue
        r = f()
        out[a] = {**r, "real": B.real(r["nominal"], infl) if r.get("completo") else None}
    return out


# ------------------------------------------------------------------------------------------------- lectura (impura)
def yd_ancla_jst(con, pais: str, año: int = AÑO_ANCLA_ALQUILER) -> float | None:
    """rent_yd JST del año del ancla (≤ 2004, con `load_dev`: el único dato JST que usa el realizado)."""
    from src.intl import data as D
    s = D.load_dev(con, f"jst_{pais.lower()}_housing_rent_yd")
    s = s[s.index.year == año]
    return float(s.iloc[0]) if len(s) else None


def leer_realizado_activos(con, fx_diarias: dict[str, pd.Series], desde, hasta, paises=NUCLEO,
                           metodo_ipc: str = "media", activos=ACTIVOS_NUEVOS) -> dict:
    """Realizado de los activos `activos` por país, leído del warehouse (sin JST salvo el ancla de 2004). Sin escribir.
    Devuelve también qué serie de alquiler se usó (la de la OCDE aún no está ingerida: decisión V3 del documento)."""
    ini = pd.Timestamp(desde)
    lee = ini - pd.DateOffset(years=2)
    oro = B.leer_obs(con, SERIES["oro"], desde=lee) if "oro" in activos else None
    out = {}
    for c in paises:
        lc, i2 = c.lower(), ISO2[c]
        ipc, rell = B.ipc_con_huecos(B.leer_obs(con, f"oecd_cpi_{lc}_idx", desde=lee))
        kw: dict = {"ipc": ipc, "es_usa": c == "USA", "metodo_ipc": metodo_ipc}
        notas = {}
        if "bonos" in activos:
            kw["irlt"] = B.leer_obs(con, SERIES["bonos"].format(p=lc), desde=lee)
        if "letras" in activos:
            b = B.leer_obs(con, SERIES["letras"].format(p=lc), desde=lee - pd.DateOffset(years=2))
            if c in SUSTITUTO_3M:
                b, e = empalmar_3m(b, B.leer_obs(con, SUSTITUTO_3M[c], desde=lee - pd.DateOffset(years=2)))
                if e is not None:
                    notas["letras_empalme"] = {k: (str(v) if isinstance(v, pd.Timestamp) else v) for k, v in e.items()}
            kw["ir3m"] = b
        if "vivienda" in activos:
            kw["precio_viv"] = B.leer_obs(con, SERIES["vivienda_precio"].format(i2=i2))
            alq = B.leer_obs(con, SERIES["vivienda_alquiler"].format(p=lc))
            if c in SUSTITUTO_ALQUILER and (not len(alq) or alq.index.max() < pd.Timestamp(hasta) - pd.DateOffset(months=3)):
                alq = alquiler_trimestral(B.leer_obs(con, SUSTITUTO_ALQUILER[c]))
                notas["vivienda_alquiler_sustituto"] = SUSTITUTO_ALQUILER[c]
            kw["alquiler_viv"] = alq if len(alq) else None
            kw["yd_ancla"] = yd_ancla_jst(con, c)
            notas["vivienda_alquiler_serie"] = SERIES["vivienda_alquiler"].format(p=lc) if len(alq) else None
        if "oro" in activos:
            kw["oro_usd"] = oro
            kw["fx_lpu"] = B.fx_lpu_pais(c, fx_diarias)
        r = realizado_activos_pais(desde, hasta, **kw)
        for a in ACTIVOS_NUEVOS:
            if a not in activos:
                r.pop(a, None)
        r["ipc_interpolados"] = [m for m in rell if pd.Timestamp(m) >= ini - pd.DateOffset(months=12)]
        r["notas"] = notas
        out[c] = r
    return out


def series_leidas(paises=NUCLEO, activos=ACTIVOS_NUEVOS) -> list[str]:
    """Series del warehouse que lee `leer_realizado_activos` (para la huella sha256)."""
    s = []
    for c in paises:
        lc, i2 = c.lower(), ISO2[c]
        if "bonos" in activos:
            s.append(SERIES["bonos"].format(p=lc))
        if "letras" in activos:
            s += [SERIES["letras"].format(p=lc)] + ([SUSTITUTO_3M[c]] if c in SUSTITUTO_3M else [])
        if "vivienda" in activos:
            s += [SERIES["vivienda_precio"].format(i2=i2), SERIES["vivienda_alquiler"].format(p=lc)]
            s += [SUSTITUTO_ALQUILER[c]] if c in SUSTITUTO_ALQUILER else []
    return s + ([SERIES["oro"]] if "oro" in activos else [])


# ======================================================================================== semáforo y contraste
def banda_binomial(n_eff: float, p0: float = 0.90, colas=(0.025, 0.10, 0.90, 0.975)) -> list[float]:
    """Cuantiles de la cobertura observada bajo H0 (cobertura real p0) con una binomial de tamaño efectivo n_eff
    (= filas / efecto de diseño). Con n_eff no entero se interpola entre los dos enteros vecinos."""
    lo, hi = int(np.floor(n_eff)), int(np.ceil(n_eff))
    lo = max(lo, 1)
    hi = max(hi, 1)

    def q(n):
        return np.array([stats.binom.ppf(c, n, p0) / n for c in colas])
    w = n_eff - lo if hi > lo else 0.0
    return [float(v) for v in (1 - w) * q(lo) + w * q(hi)]


def semaforo(cobertura: float | None, banda: dict) -> str:
    """banda = {"p2_5", "p10", "p90", "p97_5"} de la cobertura bajo H0 para ese nº de años.
    verde: dentro del 80 % central; ámbar: en el 95 % central pero fuera del 80 %; rojo: fuera del 95 %."""
    if cobertura is None or not np.isfinite(cobertura):
        return "sin datos"
    if banda["p10"] <= cobertura <= banda["p90"]:
        return "verde"
    if banda["p2_5"] <= cobertura <= banda["p97_5"]:
        return "ámbar"
    return "rojo"


def _t_multi(n: int, R: np.ndarray, nu: float, rng) -> np.ndarray:
    z = rng.standard_normal((n, len(R))) @ np.linalg.cholesky(R).T
    return z * np.sqrt((nu - 2) / rng.chisquare(nu, size=(n, 1))) if np.isfinite(nu) else z


def simular_dentro(años: int, sd_comun, sd_propio, R, nu: float, nsim: int, rng, escala=1.0, n_paises: int = 14,
                   umbral=None) -> np.ndarray:
    """(nsim, años, n_paises, A) booleano "dentro del p5-p95" de un abanico CALIBRADO para la distribución marginal
    (choque común del año + propio, t multivariante entre activos) cuando el realizado se escala por `escala` (1 =
    calibrado; > 1 = abanico demasiado estrecho). `umbral` (A,) = p95 de |z| marginal (simétrico); si None, se estima."""
    sc, sp = np.asarray(sd_comun, float), np.asarray(sd_propio, float)
    sd = np.sqrt(sc ** 2 + sp ** 2)
    A = len(sc)
    if umbral is None:
        umbral = umbral_marginal(sd_comun, sd_propio, R, nu, rng)
    u = _t_multi(nsim * años, R, nu, rng).reshape(nsim, años, 1, A) * sc
    e = _t_multi(nsim * años * n_paises, R, nu, rng).reshape(nsim, años, n_paises, A) * sp
    z = (u + e) / sd * np.asarray(escala, float)
    return np.abs(z) <= umbral


def umbral_marginal(sd_comun, sd_propio, R, nu: float, rng, n: int = 400_000) -> np.ndarray:
    """p90 de |z| de la marginal estandarizada (= los límites p5 y p95, simétrica) por activo."""
    sc, sp = np.asarray(sd_comun, float), np.asarray(sd_propio, float)
    sd = np.sqrt(sc ** 2 + sp ** 2)
    z = (_t_multi(n, R, nu, rng) * sc + _t_multi(n, R, nu, rng) * sp) / sd
    return np.quantile(np.abs(z), 0.90, axis=0)


def escala_para(cobertura_objetivo: float, sd_comun, sd_propio, R, nu: float, umbral, rng, n: int = 400_000):
    """(A,) factor por el que hay que escalar el realizado para que el p5-p95 calibrado cubra `cobertura_objetivo`."""
    sc, sp = np.asarray(sd_comun, float), np.asarray(sd_propio, float)
    sd = np.sqrt(sc ** 2 + sp ** 2)
    z = np.abs((_t_multi(n, R, nu, rng) * sc + _t_multi(n, R, nu, rng) * sp) / sd)
    return np.array([float(umbral[a] / np.quantile(z[:, a], cobertura_objetivo)) for a in range(len(sc))])
