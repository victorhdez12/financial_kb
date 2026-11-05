"""INT-11, registro en vivo: rentabilidad REALIZADA de la bolsa por país (fuente D9; docs/int/INT11_fuente_bolsa_vivo.md).

Qué exige el registro (docs/int/INT11_registro_vivo.md §3): para cada uno de los 14 países del núcleo, la rentabilidad
REAL de 12 meses, en MONEDA LOCAL, de un índice de RENTABILIDAD TOTAL (con dividendos), en la ventana de la emisión
(12 meses desde el mes siguiente), deflactada con el IPC OCDE. El motor se estimó con JST `eq_tr` (anual, fin de año a
fin de año, local, con dividendos) deflactado con la inflación de la MEDIA ANUAL del IPC.

Fuente propuesta (pendiente de aprobación):
  principal = AQR "MKT" por país (exceso mensual en USD sobre la letra de EE. UU.) + letra AQR → rentabilidad total en
              USD → moneda local con el tipo de cambio de FIN DE MES (FRED H.10);
  respaldo  = índice de cotizaciones OCDE (precio, MEDIA mensual) + rentabilidad por dividendo congelada por país
              (FRA ya es de rentabilidad total en la OCDE: no se suma nada).

Funciones PURAS (series de pandas → series/dict); solo `leer_obs` toca el warehouse y `fx_fred` la red.
Convención de fechas: series mensuales fechadas el día 1 del mes (como el warehouse); el valor de un mes es la
rentabilidad DURANTE ese mes (AQR) o el nivel de ese mes (índices, IPC, tipo de cambio de fin de mes).
"""
from __future__ import annotations

import io
import urllib.request

import numpy as np
import pandas as pd

NUCLEO = ["BEL", "DEU", "DNK", "ESP", "FIN", "FRA", "GBR", "ITA", "JPN", "NLD", "NOR", "PRT", "SWE", "USA"]
EURO = {"BEL", "DEU", "ESP", "FIN", "FRA", "ITA", "NLD", "PRT"}
# FRED H.10 (Reserva Federal, diario, dominio público): (serie, True si cotiza USD por unidad local → se invierte)
FX_FRED = {"GBR": ("DEXUSUK", True), "JPN": ("DEXJPUS", False), "DNK": ("DEXDNUS", False),
           "NOR": ("DEXNOUS", False), "SWE": ("DEXSDUS", False), **{c: ("DEXUSEU", True) for c in EURO}}
OCDE_YA_TR = {"FRA"}                 # src/intl/panel.py: el índice OCDE de FRA ya incluye dividendos
OCDE_ROTA = {"DNK", "JPN"}           # src/intl/panel.py: rupturas antes de 2005 (solo afecta a la comparación ≤ 2004)


# ----------------------------------------------------------------------------------------------- utilidades de fechas
def _mes(s: pd.Series) -> pd.Series:
    """Índice a inicio de mes, ordenado; error si hay dos datos en el mismo mes."""
    s = s.dropna().astype(float)
    i = pd.DatetimeIndex(s.index).to_period("M")
    if i.duplicated().any():
        raise ValueError(f"{s.name}: dos datos en el mismo mes")
    return pd.Series(s.values, index=i.to_timestamp(how="start"), name=s.name).sort_index()


def fin_de_mes(diaria: pd.Series) -> pd.Series:
    """Serie diaria → último dato disponible de cada mes (fechado el día 1 de ese mes)."""
    d = diaria.dropna().astype(float).sort_index()
    u = d.groupby(pd.DatetimeIndex(d.index).to_period("M")).last()
    return pd.Series(u.values, index=u.index.to_timestamp(how="start"), name=diaria.name)


def meses_ventana(desde, hasta) -> pd.DatetimeIndex:
    """Meses (día 1) de la ventana [desde, hasta]; `ventana_objetivo` da desde = día 1, hasta = último día."""
    return pd.period_range(pd.Timestamp(desde), pd.Timestamp(hasta), freq="M").to_timestamp(how="start")


# ------------------------------------------------------------------------------------------ rentabilidad nominal local
def local_por_usd(fx: pd.Series, invertir: bool) -> pd.Series:
    """Tipo de cambio en unidades locales por USD (FRED cotiza EUR y GBP como USD por unidad local)."""
    return 1.0 / fx if invertir else fx


def tr_local_desde_usd(exceso_pct: pd.Series, rf_pct: pd.Series, fx_lpu: pd.Series | None) -> pd.Series:
    """Rentabilidad total MENSUAL en moneda local (fracción) a partir del exceso en USD (AQR MKT, %), la letra USD (%) y
    el tipo de cambio de fin de mes en unidades locales por USD (None = el país es EE. UU.).
        1 + r_local(m) = (1 + exceso(m) + rf(m)) · X(m) / X(m − 1)
    Solo meses con los tres datos (y el tipo de cambio del mes anterior)."""
    e, r = _mes(exceso_pct) / 100, _mes(rf_pct) / 100
    usd = (e + r).dropna()
    if fx_lpu is None:
        return usd.rename("tr_local")
    x = _mes(fx_lpu)
    rx = (x / x.shift(1, freq="MS")).reindex(usd.index)
    return ((1 + usd) * rx - 1).dropna().rename("tr_local")


def indice(rent_m: pd.Series, base: float = 100.0) -> pd.Series:
    """Índice de fin de mes a partir de rentabilidades mensuales (el nivel del mes m es el de su cierre). Un hueco corta
    el índice (no se encadena por encima de meses que faltan)."""
    r = _mes(rent_m)
    seguidos = r.index.to_series().diff().dt.days.fillna(31).le(31)
    if not seguidos.all():
        r = r[r.index >= r.index[~seguidos.values][-1]]
    return (base * (1 + r).cumprod()).rename("indice")


def rent_ventana_tr(rent_m: pd.Series, desde, hasta) -> dict:
    """Rentabilidad total nominal de la ventana encadenando los meses (todos deben estar)."""
    m = meses_ventana(desde, hasta)
    r = _mes(rent_m).reindex(m)
    faltan = [str(x.date())[:7] for x in r.index[r.isna()]]
    if faltan:
        return {"nominal": None, "completo": False, "faltan": faltan}
    return {"nominal": float(np.prod(1 + r.values) - 1), "completo": True, "faltan": []}


def rent_ventana_precio(nivel_medio: pd.Series, desde, hasta, rend_div: float = 0.0) -> dict:
    """Respaldo con un índice de precios de MEDIA mensual (OCDE): media del último mes de la ventana / media del mes
    anterior a la ventana, más la rentabilidad por dividendo anual `rend_div` (fracción) compuesta:
        1 + r = (P̄(hasta) / P̄(desde − 1)) · (1 + rend_div)
    Declarado: con medias mensuales el cambio de 12 meses está desplazado ≈ medio mes y algo suavizado."""
    m = meses_ventana(desde, hasta)
    p = _mes(nivel_medio)
    ini, fin = m[0] - pd.offsets.MonthBegin(1), m[-1]
    if ini not in p.index or fin not in p.index:
        return {"nominal": None, "completo": False, "faltan": [str(x.date())[:7] for x in (ini, fin) if x not in p.index]}
    return {"nominal": float(p[fin] / p[ini] * (1 + rend_div) - 1), "completo": True, "faltan": []}


# --------------------------------------------------------------------------------------------------------- deflactar
def ipc_con_huecos(ipc: pd.Series, max_hueco: int = 1) -> tuple[pd.Series, list[str]]:
    """Rellena huecos INTERIORES de hasta `max_hueco` meses por interpolación log-lineal (p. ej. el IPC de EE. UU. de
    2025-10, no publicado por el cierre del Gobierno). Devuelve la serie y los meses rellenados (se declaran)."""
    p = _mes(ipc)
    if p.empty:
        return p, []
    r = p.reindex(pd.date_range(p.index.min(), p.index.max(), freq="MS"))
    falta = r.isna()
    grupo = (falta != falta.shift()).cumsum()
    largo = falta.groupby(grupo).transform("sum")
    rellenar = falta & (largo <= max_hueco)
    out = np.exp(np.log(r).interpolate(limit_area="inside"))
    out = out.where(~falta | rellenar)
    return out.dropna().rename(ipc.name), [str(x.date())[:7] for x in r.index[rellenar]]


def inflacion_ventana(ipc: pd.Series, desde, hasta, metodo: str = "media") -> float | None:
    """Inflación de la ventana con el IPC OCDE mensual.
    "media" (como JST y como K2 del registro): media del IPC de los 12 meses de la ventana / media de los 12 anteriores.
    "punta": IPC del último mes de la ventana / IPC del mes anterior a la ventana.
    Un mes que falta → None (los huecos se rellenan, declarados, con `ipc_con_huecos` antes de llamar)."""
    m = meses_ventana(desde, hasta)
    p = _mes(ipc)
    if metodo == "media":
        prev = m - pd.DateOffset(months=len(m))
        a, b = p.reindex(m), p.reindex(prev)
        if a.isna().any() or b.isna().any():
            return None
        return float(a.mean() / b.mean() - 1)
    if metodo == "punta":
        ini = m[0] - pd.offsets.MonthBegin(1)
        if ini not in p.index or m[-1] not in p.index:
            return None
        return float(p[m[-1]] / p[ini] - 1)
    raise ValueError(metodo)


def real(nominal: float | None, inflacion: float | None) -> float | None:
    """(1 + nominal) / (1 + inflación) − 1, como `jst_*_eq_tr_real`."""
    if nominal is None or inflacion is None:
        return None
    return (1 + nominal) / (1 + inflacion) - 1


# ------------------------------------------------------------------------------------------------------ cabecera
def realizado_pais(desde, hasta, ipc: pd.Series, *, exceso_pct: pd.Series | None = None, rf_pct: pd.Series | None = None,
                   fx_lpu: pd.Series | None = None, es_usa: bool = False, precio_medio: pd.Series | None = None,
                   rend_div: float | None = None, metodo_ipc: str = "media") -> dict:
    """Rentabilidad realizada de la bolsa de un país en la ventana: principal (AQR + FX) y, si se da, respaldo (OCDE +
    dividendo). Devuelve las dos con su inflación; `usada` = la principal si está completa, si no el respaldo, si no
    None. Pura: todas las series se pasan ya leídas."""
    infl = inflacion_ventana(ipc, desde, hasta, metodo_ipc)
    out = {"ventana": {"desde": str(pd.Timestamp(desde).date()), "hasta": str(pd.Timestamp(hasta).date())},
           "metodo_ipc": metodo_ipc, "inflacion": infl}
    if exceso_pct is not None and rf_pct is not None and (es_usa or fx_lpu is not None):
        p = rent_ventana_tr(tr_local_desde_usd(exceso_pct, rf_pct, None if es_usa else fx_lpu), desde, hasta)
        out["principal"] = {**p, "real": real(p["nominal"], infl), "fuente": "aqr_mkt+rf+fx_fin_de_mes"}
    if precio_medio is not None and rend_div is not None:
        r = rent_ventana_precio(precio_medio, desde, hasta, rend_div)
        out["respaldo"] = {**r, "real": real(r["nominal"], infl), "fuente": "oecd_share(media)+div", "rend_div": rend_div}
    for k in ("principal", "respaldo"):
        if out.get(k, {}).get("completo") and out[k]["real"] is not None:
            out["usada"] = k
            break
    else:
        out["usada"] = None
    return out


def rend_div_implicito(tr_m: pd.Series, precio_medio: pd.Series, hasta, años: int = 10) -> float | None:
    """Rentabilidad por dividendo implícita para el respaldo: media, en los `años` anteriores a `hasta` (incluido), de
    (1 + TR 12 m) / (1 + precio 12 m) − 1 tomando años naturales (dic → dic). Se fija ANTES de usarla (sin mirar la
    ventana evaluada)."""
    h = pd.Timestamp(hasta).year
    v = []
    for a in range(h - años + 1, h + 1):
        t = rent_ventana_tr(tr_m, f"{a}-01-01", f"{a}-12-31")
        p = rent_ventana_precio(precio_medio, f"{a}-01-01", f"{a}-12-31")
        if t["completo"] and p["completo"]:
            v.append((1 + t["nominal"]) / (1 + p["nominal"]) - 1)
    return float(np.mean(v)) if len(v) >= max(3, años // 2) else None


def anual(rent_m: pd.Series) -> pd.Series:
    """Rentabilidad de cada año natural completo (12 meses) encadenando la mensual."""
    r = _mes(rent_m)
    g = r.groupby(r.index.year)
    ok = g.count() == 12
    return (g.apply(lambda x: float(np.prod(1 + x.values) - 1)))[ok]


def anual_precio(nivel: pd.Series, mes: int = 12) -> pd.Series:
    """Cambio anual de un nivel mensual tomando el mes `mes` de cada año (dic → dic)."""
    p = _mes(nivel)
    p = pd.Series(p[p.index.month == mes].values, index=p.index[p.index.month == mes].year)
    return (p / p.shift(1) - 1)[p.index.to_series().diff() == 1].astype(float)


def comparar(a: pd.Series, b: pd.Series) -> dict:
    """Solapamiento de dos series anuales: n, correlación, sesgo medio (a − b), dt de la diferencia, RMSE."""
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    if len(j) < 3:
        return {"n": int(len(j))}
    d = j.iloc[:, 0] - j.iloc[:, 1]
    return {"n": int(len(j)), "desde": int(j.index.min()), "hasta": int(j.index.max()),
            "corr": round(float(j.corr().iloc[0, 1]), 4), "sesgo_pp": round(100 * float(d.mean()), 2),
            "dt_dif_pp": round(100 * float(d.std(ddof=1)), 2), "rmse_pp": round(100 * float(np.sqrt((d ** 2).mean())), 2)}


# Ken French, "International Research Returns" por país (F-F_International_Countries[_Wout_Div].zip): archivo por país
FRENCH_PAIS = {"BEL": "Belgium", "DEU": "Germany", "DNK": "Denmark", "ESP": "Spain", "FIN": "Finland", "FRA": "France",
               "GBR": "UK", "ITA": "Italy", "JPN": "Japan", "NLD": "Nethrlnd", "NOR": "Norway", "SWE": "Sweden"}


def french_pais_local(texto: str) -> pd.Series:
    """Columna `Mkt` del bloque MENSUAL "Value-Weight Local Returns / All 4 Data Items Not Reqd" de un archivo .Dat de
    French (rentabilidad en moneda local, %, fechada el día 1 del mes). Con el archivo "_Wout_Div" sale el precio."""
    filas, dentro = [], False
    for ln in texto.splitlines():
        if "Value-Weight" in ln:
            dentro = "Local" in ln and "Not Reqd" in ln and not filas
            continue
        p = ln.split()
        if dentro and p and len(p[0]) == 6 and p[0].isdigit():
            filas.append((pd.Timestamp(f"{p[0][:4]}-{p[0][4:]}-01"), float(p[1])))
        elif dentro and filas and not p:
            break
    s = pd.Series(dict(filas), name="french_local_pct").sort_index()
    return s.mask(s <= -99.99)


# ------------------------------------------------------------------------------------------------- lectura (impura)
def leer_obs(con, sid: str, hasta=None, desde=None) -> pd.Series:
    """Serie del warehouse (`obs_latest`), con corte opcional. Lee datos ≥ 2005: vive en src/report/ (como
    escenarios_vivo); NUNCA se usa para JST ≥ 2005 (la comparación histórica usa `src.intl.data.load_dev`)."""
    if sid.startswith("jst_"):
        raise ValueError("bolsa_vivo no lee JST (usa src.intl.data.load_dev, ≤ 2004)")
    q, a = "select date, value from obs_latest where series_id = ? and value is not null", [sid]
    if desde is not None:
        q, a = q + " and date >= ?", a + [pd.Timestamp(desde).date()]
    if hasta is not None:
        q, a = q + " and date <= ?", a + [pd.Timestamp(hasta).date()]
    df = con.execute(q + " order by date", a).df()
    return pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["date"]), name=sid)


def fx_fred(serie: str, timeout: int = 60) -> pd.Series:
    """Serie diaria FRED H.10 (CSV público fredgraph, sin clave)."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={serie}"
    with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (URL fija de FRED)
        df = pd.read_csv(io.BytesIO(r.read()), na_values=["."])
    df.columns = ["date", "value"]
    return pd.Series(pd.to_numeric(df["value"], errors="coerce").values, index=pd.to_datetime(df["date"]),
                     name=serie).dropna()


def leer_realizado(con, fx_diarias: dict[str, pd.Series], desde, hasta, paises=NUCLEO, metodo_ipc: str = "media") -> dict:
    """Rentabilidad realizada de la bolsa (principal AQR + FX; respaldo OCDE + dividendo implícito de los 10 años
    naturales ANTERIORES a la ventana) de cada país, con la huella de lo leído. No escribe nada."""
    ini = pd.Timestamp(desde)
    lee = ini - pd.DateOffset(years=12)
    rf = leer_obs(con, "aqr_rf_risk_free_rate_m", desde=lee)
    out = {}
    for c in paises:
        lc = c.lower()
        ex = leer_obs(con, f"aqr_mkt_{lc}_m", desde=lee)
        x = fx_lpu_pais(c, fx_diarias)
        pr = leer_obs(con, f"oecd_share_{lc}", desde=lee)
        ipc, ipc_rellenos = ipc_con_huecos(leer_obs(con, f"oecd_cpi_{lc}_idx", desde=lee))
        tr = tr_local_desde_usd(ex, rf, x)
        dv = rend_div_implicito(tr[tr.index < ini], pr[pr.index < ini], ini - pd.DateOffset(years=1) +
                                pd.offsets.YearEnd(0))
        r = realizado_pais(desde, hasta, ipc, exceso_pct=ex, rf_pct=rf, fx_lpu=x, es_usa=c == "USA",
                           precio_medio=pr, rend_div=dv, metodo_ipc=metodo_ipc)
        r["ultimo_dato"] = {"aqr": str(ex.index.max().date()) if len(ex) else None,
                            "oecd_share": str(pr.index.max().date()) if len(pr) else None,
                            "ipc": str(ipc.index.max().date()) if len(ipc) else None}
        r["ipc_interpolados"] = [m for m in ipc_rellenos if pd.Timestamp(m) >= ini - pd.DateOffset(months=12)]
        if r.get("respaldo") is None and dv is None:
            r["respaldo"] = {"completo": False, "motivo": "sin dividendo implícito (faltan años previos)"}
        out[c] = r
    return out


# retrasos de publicación medidos el 2026-11-05 (docs/int/INT11_fuente_bolsa_vivo.md §2), en meses tras el fin de mes
RETRASO_MESES = {"principal": 3, "respaldo_ocde": 2, "contraste_french": 14}
FUENTE_D9 = {"principal": "AQR MKT por país (exceso USD) + letra AQR + FX fin de mes FRED H.10 → TR local",
             "respaldo": "OCDE share price (media mensual) × (1 + dividendo implícito de los 10 años naturales previos)",
             "contraste": "Ken French International Countries, local, con dividendos (12 de 14; anual)",
             "deflactor": "IPC OCDE, media de los 12 meses de la ventana / media de los 12 anteriores (como JST y K2)",
             "estado": "PROPUESTA (pendiente de aprobación del usuario)"}


def plan_evaluacion(ventana: dict) -> dict:
    """Cuándo y con qué se evaluará la bolsa de una emisión (no lee datos)."""
    fin = pd.Timestamp(ventana["hasta"])
    return {"fuente": FUENTE_D9, "ventana": ventana,
            "evaluable_desde": {k: str((fin + pd.offsets.MonthEnd(m)).date()) for k, m in RETRASO_MESES.items()},
            "regla": "principal si están los 12 meses; si no, respaldo; nunca se mezclan dentro de una ventana; el "
                     "valor leído, la fuente usada y la fecha de lectura se guardan con su sha256 al evaluar"}


def fx_lpu_pais(c: str, diarias: dict[str, pd.Series]) -> pd.Series | None:
    """Tipo de cambio de fin de mes, unidades locales por USD, para el país `c` (None para EE. UU.)."""
    if c == "USA":
        return None
    sid, inv = FX_FRED[c]
    return local_por_usd(fin_de_mes(diarias[sid]), inv)
