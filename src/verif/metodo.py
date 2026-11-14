"""Método de predicción v1 — CONGELADO (docs/verif/metodo_v1.md lleva el sha256 de este fichero).

No editar: cualquier cambio de reglas, ventanas o variables es un método v2 en otro fichero y otro registro.
Cada predicción guarda el sha256 de este fichero; los tests comprueban que coincide con el del documento.

Reglas comunes
- Datos: solo lo publicado hasta el día anterior a la emisión (as_of(emisión − 1 día)), vintages ALFRED.
- Emisión: el primer día en que se cumple la regla de `fecha_emision`; si para entonces el dato ya se ha publicado,
  no hay predicción (no se recupera a posteriori).
- Ventana de estimación: 120 meses o 80 trimestres que acaban en el periodo anterior al objetivo,
  quitando 2020-03..2021-06 (2020T1..2021T2) por la covid.
- Intervalo del 80 %: punto ± 1,2816·σ, σ = desviación típica de los residuos (o de los errores de la regla) en la ventana.
- Benchmarks ingenuos: «último» = último valor publicado de la variable; «media 12 m» = media de los 12 últimos meses
  (4 trimestres en el PIB).
- Dato real: primera publicación (vintage del día de publicación del periodo objetivo).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

VERSION = "v1"
Z80 = 1.2815515655446004
VENTANA_M, VENTANA_T = 120, 80
COVID_M = (pd.Timestamp("2020-03-01"), pd.Timestamp("2021-06-01"))
COVID_T = (pd.Timestamp("2020-01-01"), pd.Timestamp("2021-04-01"))

VARIABLES = {
    "ipc": {"nombre": "IPC general m/m", "unidad": "%", "serie": "CPIAUCSL", "freq": "M",
            "metodo": "puente: AR(1) del IPC m/m + variación del petróleo WTI en el mes (MCO, 120 m)"},
    "ipc_sub": {"nombre": "IPC subyacente m/m", "unidad": "%", "serie": "CPILFESL", "freq": "M",
                "metodo": "AR(1) del IPC subyacente m/m (MCO, 120 m)"},
    "nominas": {"nombre": "Nóminas no agrícolas (variación)", "unidad": "miles", "serie": "PAYEMS", "freq": "M",
                "metodo": "media de las 3 últimas variaciones mensuales"},
    "paro": {"nombre": "Tasa de paro", "unidad": "%", "serie": "UNRATE", "freq": "M",
             "metodo": "último valor + MCO del cambio sobre la variación de las peticiones de subsidio (ICSA) del mes"},
    "pib": {"nombre": "PIB real, avance (t/t anualizado)", "unidad": "%", "serie": "GDPC1", "freq": "Q",
            "metodo": "puente: MCO del PIB t/t anualizado sobre nóminas e industria (medias trimestrales), 80 trimestres"},
}


# ------------------------------------------------------------------------------------------------ transformaciones
def _mensual(s: pd.Series) -> pd.Series:
    s = s.copy()
    s.index = pd.DatetimeIndex(s.index).to_period("M").to_timestamp()
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="MS")) if len(s) else s


def _trimestral(s: pd.Series) -> pd.Series:
    s = s.copy()
    s.index = pd.DatetimeIndex(s.index).to_period("Q").to_timestamp()
    s = s[~s.index.duplicated(keep="last")]
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="QS")) if len(s) else s


def transformar(var: str, nivel: pd.Series) -> pd.Series:
    """Nivel publicado -> variable que se predice (los huecos, p. ej. oct-2025 sin IPC, quedan en NaN)."""
    if var in ("ipc", "ipc_sub"):
        s = _mensual(nivel)
        return 100 * (s / s.shift(1) - 1)
    if var == "nominas":
        s = _mensual(nivel)
        return s - s.shift(1)
    if var == "paro":
        return _mensual(nivel)
    if var == "pib":
        s = _trimestral(nivel)
        return 100 * ((s / s.shift(1)) ** 4 - 1)
    raise KeyError(var)


def periodo_fin(var: str, periodo: pd.Timestamp) -> pd.Timestamp:
    p = pd.Timestamp(periodo)
    return (p + (pd.offsets.QuarterEnd(0) if VARIABLES[var]["freq"] == "Q" else pd.offsets.MonthEnd(0))).normalize()


def periodo_anterior(var: str, periodo) -> pd.Timestamp:
    return pd.Timestamp(periodo) - (pd.DateOffset(months=3) if VARIABLES[var]["freq"] == "Q" else pd.DateOffset(months=1))


def fecha_emision(var: str, periodo, V) -> pd.Timestamp | None:
    """Primer día en que la regla permite emitir. None si aún no se puede saber (faltan entradas)."""
    p = pd.Timestamp(periodo)
    d = periodo_fin(var, p) + pd.Timedelta(days=1)
    serie = VARIABLES[var]["serie"]
    pa = V.publicacion(serie, periodo_anterior(var, p))
    if pa is None:
        return None
    d = max(d, pa + pd.Timedelta(days=1))
    if var == "pib":   # hacen falta los 3 meses del trimestre de nóminas e industria
        m3 = p + pd.DateOffset(months=2)
        for sid in ("PAYEMS", "INDPRO"):
            r = V.publicacion(sid, m3)
            if r is None:
                return None
            d = max(d, r + pd.Timedelta(days=1))
    return d


def dato_real(var: str, periodo, V) -> tuple[float | None, pd.Timestamp | None]:
    """Primera publicación del periodo objetivo y su fecha."""
    serie = VARIABLES[var]["serie"]
    r = V.publicacion(serie, periodo)
    if r is None:
        return None, None
    y = transformar(var, V.as_of(serie, r))
    v = y.get(pd.Timestamp(periodo))
    return (None if v is None or pd.isna(v) else float(v)), r


# ------------------------------------------------------------------------------------------------ estimación
def _ventana(df: pd.DataFrame, fin: pd.Timestamp, n: int, covid) -> pd.DataFrame:
    df = df[df.index <= fin].dropna().tail(n + 16)
    df = df[(df.index < covid[0]) | (df.index > covid[1])]
    return df.tail(n)


def _mco(df: pd.DataFrame, y: str, xs: list[str]) -> tuple[np.ndarray, float, int]:
    X = np.column_stack([np.ones(len(df))] + [df[x].to_numpy() for x in xs])
    b, *_ = np.linalg.lstsq(X, df[y].to_numpy(), rcond=None)
    e = df[y].to_numpy() - X @ b
    return b, float(np.sqrt(e @ e / (len(df) - X.shape[1]))), len(df)


def _wti_mes(V, hasta: pd.Timestamp) -> pd.Series:
    w = V.diaria("DCOILWTICO", hasta)
    w = w[w > 0]
    m = w.groupby(w.index.to_period("M")).mean()
    m.index = m.index.to_timestamp()
    return 100 * np.log(m / m.shift(1))


def predecir(var: str, periodo, V, emision) -> dict | None:
    """Predicción puntual + intervalo 80 % + benchmarks con datos publicados hasta emisión − 1 día."""
    p = pd.Timestamp(periodo)
    corte = pd.Timestamp(emision) - pd.Timedelta(days=1)
    meta = VARIABLES[var]
    y = transformar(var, V.as_of(meta["serie"], corte))
    ant = periodo_anterior(var, p)
    if ant not in y.index or pd.isna(y.get(ant)) or p in y.dropna().index:
        return None
    hist = y[y.index <= ant].dropna()
    n_bench = 4 if meta["freq"] == "Q" else 12
    out = {"bench_ultimo": float(y[ant]), "bench_media12": float(hist.tail(n_bench).mean())}
    entradas: dict = {}
    if var in ("ipc", "ipc_sub"):
        df = pd.DataFrame({"y": y, "y1": y.shift(1)})
        xs = ["y1"]
        if var == "ipc":
            wti = _wti_mes(V, corte)
            df["wti"] = wti.reindex(df.index)
            xs = ["y1", "wti"]
            if p not in wti.index or pd.isna(wti.get(p)):
                return None
            entradas["wti_mes_pct_log"] = round(float(wti[p]), 3)
        tr = _ventana(df, ant, VENTANA_M, COVID_M)
        b, sigma, n = _mco(tr, "y", xs)
        x = [1.0, float(y[ant])] + ([float(wti[p])] if var == "ipc" else [])
        punto = float(np.dot(b, x))
        entradas["coef"] = [round(float(c), 4) for c in b]
    elif var == "nominas":
        regla = y.rolling(3).mean().shift(1)
        df = pd.DataFrame({"y": y, "r": regla})
        tr = _ventana(df, ant, VENTANA_M, COVID_M)
        e = tr["y"] - tr["r"]
        sigma, n = float(np.sqrt((e ** 2).mean())), len(tr)
        punto = float(hist.tail(3).mean())
    elif var == "paro":
        ic = V.as_of("ICSA", corte)
        icm = ic.groupby(pd.DatetimeIndex(ic.index).to_period("M")).mean()
        icm.index = icm.index.to_timestamp()
        dcl = 100 * np.log(icm / icm.shift(1))
        if p not in dcl.index or pd.isna(dcl.get(p)):
            return None
        df = pd.DataFrame({"du": y - y.shift(1), "dcl": dcl.reindex(y.index)})
        tr = _ventana(df, ant, VENTANA_M, COVID_M)
        b, sigma, n = _mco(tr, "du", ["dcl"])
        punto = float(y[ant] + b[0] + b[1] * float(dcl[p]))
        entradas.update({"icsa_mes_pct_log": round(float(dcl[p]), 3), "coef": [round(float(c), 4) for c in b]})
    elif var == "pib":
        def q(sid):
            s = _mensual(V.as_of(sid, corte))
            qa = s.groupby(s.index.to_period("Q")).agg(["mean", "count"])
            qa.index = qa.index.to_timestamp()
            return 400 * np.log(qa["mean"] / qa["mean"].shift(1)), qa["count"]
        pay, npay = q("PAYEMS")
        ip, nip = q("INDPRO")
        if npay.get(p, 0) < 3 or nip.get(p, 0) < 3:
            return None
        df = pd.DataFrame({"y": y, "pay": pay.reindex(y.index), "ip": ip.reindex(y.index)})
        tr = _ventana(df, ant, VENTANA_T, COVID_T)
        b, sigma, n = _mco(tr, "y", ["pay", "ip"])
        punto = float(b[0] + b[1] * pay[p] + b[2] * ip[p])
        entradas.update({"nominas_t_anualiz": round(float(pay[p]), 3), "industria_t_anualiz": round(float(ip[p]), 3),
                         "coef": [round(float(c), 4) for c in b]})
    else:
        raise KeyError(var)
    out.update({"punto": punto, "inf80": punto - Z80 * sigma, "sup80": punto + Z80 * sigma, "sigma": sigma,
                "n_entreno": int(n), "corte_datos": corte.date().isoformat(), "entradas": entradas})
    return out
