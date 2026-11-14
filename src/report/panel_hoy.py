"""Pestaña «Hoy» del panel web: lo que hay que mirar cada mañana (uso personal; informativo, no es asesoramiento).

Tres bloques, de arriba abajo:
1. «En rojo»: lo que está en rojo o ámbar hoy en la franja de indicadores y en los avisos del reporte semanal.
2. Franja de indicadores clave (EE. UU. y zona euro): valor, fecha del dato, cambio frente al dato anterior,
   percentil en su historia, semáforo y mini-sparkline (24 meses). Los semáforos reutilizan reglas que ya existen
   en el código (monitor de fractura de crédito `src/regime/credit.py`, reglas de `pulso_paises.py`); los que no
   existían son umbrales REDONDOS rotulados «regla fija, no validada».
3. «Datos nuevos publicados»: series cuya última observación cambió en los últimos 7 días, con el valor nuevo frente
   al anterior y si el anterior se revisó. Fuentes de la detección, sin servicios externos:
   - series con vintages ALFRED (`vintages`): la última vintage ≤ hoy dice cuándo se publicó y qué se revisó;
   - el resto: un JSON de estado `hoy_estado.json` junto al panel (fuera de git) con la última fecha/valor visto
     de cada serie no diaria; si no hay estado aún, se siembra con `last_updated` de los catálogos de FRED.

Lee solo del warehouse (obs_latest, vintages, catalog). Todo cálculo es una regla fija, sin LLM ni optimización.
"""
from __future__ import annotations

import html
import json
import math
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from src.regime.credit import THRESHOLDS
from src.report import liquidez_vivo as LV
from src.report import pulso_paises as PUL
from src.warehouse import db

ESTADO_DIR: Path | None = None   # lo fija panel.generar (carpeta de salida); None = no se guarda estado
ESTADO_FICHERO = "hoy_estado.json"
DIAS_NUEVO = 7
FIJA = "regla fija, no validada"
ND = '<span class="nd">no disponible</span>'
AVISO = ("Informativo y de uso personal; no es asesoramiento ni una recomendación de compra o venta. Los semáforos son "
         "reglas fijas de lectura (no predicciones); los marcados «regla fija, no validada» son umbrales redondos "
         "elegidos a mano, sin ninguna validación.")

# series que se ordenan primero en «Datos nuevos» (por importancia)
CLAVE = ["M2SL", "WM2NS", "CPIAUCSL", "CPILFESL", "PCEPILFE", "PCEPI", "UNRATE", "PAYEMS", "ICSA", "GDPC1", "GDP",
         "A191RL1Q225SBEA", "WALCL", "WTREGEN", "WRESBAL", "NFCI", "STLFSI4", "INDPRO", "TCU", "RSAFS", "UMCSENT",
         "PPIACO", "CFNAI", "JTSJOL", "M2REAL", "ecb_hicp_headline_yoy_ea_m", "ecb_hicp_core_yoy_ea_m",
         "ecb_m3_yoy_m", "eurostat_unemp_ea_m"]


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def fnum(v, dec: int = 1, signo: bool = False) -> str:
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "—"
    t = f"{v:+,.{dec}f}" if signo else f"{v:,.{dec}f}"
    return t.replace(",", " ").replace(".", ",").replace("-", "−")


# ----------------------------------------------------------------------------------------------- cálculo puro
def percentil(x: pd.Series, min_obs: int = 24) -> float | None:
    """Percentil (0-100) del último valor en toda su historia (proporción de valores ≤ el último)."""
    x = x.dropna()
    if len(x) < min_obs:
        return None
    return round(float((x <= x.iloc[-1]).mean() * 100), 0)


def en(x: pd.Series, t: pd.Timestamp) -> float | None:
    x = x[x.index <= t].dropna()
    return None if x.empty else float(x.iloc[-1])


def delta(x: pd.Series, desfase: pd.DateOffset) -> float | None:
    x = x.dropna()
    if x.empty:
        return None
    a = en(x, x.index[-1] - desfase)
    return None if a is None else float(x.iloc[-1]) - a


def yoy(x: pd.Series) -> pd.Series:
    """Variación a/a (%) frente al MISMO mes del año anterior (por calendario, no por posición).

    Un único mes ausente en el interior (p. ej. el IPC de EE. UU. de oct-2025, cierre del Gobierno) se rellena por
    interpolación log-lineal SOLO como base de comparación (como `bolsa_vivo.ipc_con_huecos`); el mes ausente no
    tiene a/a propio. Antes se desplazaba por posición tras quitar el hueco y de nov-2025 en adelante se comparaba
    con 13 meses antes (IPC oct-2026 4,1 % en vez de 3,9 %)."""
    x = x.dropna()
    if x.empty:
        return x
    m = x.resample("MS").last()
    base = m
    falta = m.isna()
    suelto = falta & ~falta.shift(1, fill_value=False) & ~falta.shift(-1, fill_value=False)
    if suelto.any() and m.dropna().gt(0).all():
        rell = np.exp(np.log(m).interpolate(limit_area="inside"))
        base = m.where(~suelto, rell)
    y = 100 * (m / base.shift(12) - 1)
    return y[m.notna()].dropna()


def caida_desde_max(x: pd.Series, dias: int = 365) -> pd.Series:
    x = x.dropna()
    return (100 * (x / x.rolling(f"{dias}D").max() - 1)).dropna()


def _umbral(v, ambar, rojo, mayor=True):
    if v is None:
        return "gris", "sin dato"
    if (v >= rojo) if mayor else (v <= rojo):
        return "rojo", "alto" if mayor else "bajo"
    if (v >= ambar) if mayor else (v <= ambar):
        return "ambar", "elevado" if mayor else "flojo"
    return "verde", "normal"


def regla_vix(x):
    return _umbral(_ult(x), 20, 30)


def regla_hy(x):
    v, d3 = _ult(x), delta(x, pd.DateOffset(months=3))
    if v is None:
        return "gris", "sin dato"
    if v >= 6.0 or (d3 is not None and d3 >= 1.5):
        return "rojo", "tensión de crédito"
    if v >= 4.5 or (d3 is not None and d3 >= 0.75):
        return "ambar", "se ensancha"
    return "verde", "tranquilo"


def regla_ig(x):
    return _umbral(_ult(x), 1.5, 2.5)


def regla_curva(x):
    """Regla del monitor de crédito (rejilla mensual): invertida → ámbar; re-empinamiento tras inversión → rojo."""
    m = x.dropna().resample("MS").last().dropna()
    if m.empty:
        return "gris", "sin dato"
    v = float(m.iloc[-1])
    inv12 = bool((m.iloc[-12:] < 0).any())
    d3 = float(m.iloc[-1] - m.iloc[-4]) if len(m) >= 4 else None
    if inv12 and v > 0 and d3 is not None and d3 >= 0.5:
        return "rojo", "re-empina tras invertirse"
    if v < 0:
        return "ambar", "invertida"
    return "verde", "positiva"


def regla_infl(x):
    return PUL._color_infl(_ult(x))


def regla_implicita(x):
    v = _ult(x)
    if v is None:
        return "gris", "sin dato"
    if v > 3:
        return "rojo", "expectativas altas"
    if v > 2.5 or v < 1.5:
        return "ambar", "lejos del 2 %"
    return "verde", "ancladas"


def regla_paro(x):
    return PUL._color_paro(delta(x, pd.DateOffset(months=12)))


def regla_m2(x):
    v = _ult(x)
    if v is None:
        return "gris", "sin dato"
    if v < 0:
        return "rojo", "se contrae"
    if v < 2 or v > 10:
        return "ambar", "crece poco" if v < 2 else "crece mucho"
    return "verde", "normal"


def regla_m2_real(x):
    return _umbral(_ult(x), 0, -2, mayor=False)


def regla_liq(x):
    x = x.dropna()
    if len(x) < 14:
        return "gris", "sin dato"
    a = en(x, x.index[-1] - pd.DateOffset(weeks=13))
    c = None if not a else 100 * (float(x.iloc[-1]) / a - 1)
    if c is None:
        return "gris", "sin dato"
    if c <= -10:
        return "rojo", f"cae {fnum(c, 1)} % en 13 sem."
    if c <= -5:
        return "ambar", f"cae {fnum(c, 1)} % en 13 sem."
    return "verde", f"{fnum(c, 1, True)} % en 13 sem."


def regla_nfci(x):
    v, d3 = _ult(x), delta(x, pd.DateOffset(months=3))
    if v is None:
        return "gris", "sin dato"
    if v > 0:
        return "rojo", "condiciones tensas"
    if v > -0.25 or (d3 is not None and d3 >= 0.2):
        return "ambar", "se endurecen"
    return "verde", "holgadas"


def regla_stlfsi(x):
    v = _ult(x)
    if v is None:
        return "gris", "sin dato"
    return ("rojo", "estrés alto") if v > 1 else ("ambar", "estrés sobre la media") if v > 0 else ("verde", "bajo")


def _var12(x):
    x = x.dropna()
    if x.empty:
        return None
    a = en(x, x.index[-1] - pd.DateOffset(months=12))
    return None if not a else 100 * (float(x.iloc[-1]) / a - 1)


def regla_dolar(x):
    c = _var12(x)
    if c is None:
        return "gris", "sin dato"
    col, _ = _umbral(c, 10, 15)
    return col, f"{fnum(c, 1, True)} % en 12 meses"


def regla_petroleo(x):
    c = _var12(x)
    if c is None:
        return "gris", "sin dato"
    col, _ = _umbral(c, 50, 100)
    return col, f"{fnum(c, 0, True)} % en 12 meses"


def regla_bolsa(x):
    return PUL._color_bolsa(_ult(x))


def regla_ciss(x):
    return _umbral(_ult(x), 0.2, 0.4)


def _ult(x: pd.Series) -> float | None:
    x = x.dropna()
    return None if x.empty else float(x.iloc[-1])


CRED = "monitor de fractura de crédito (src/regime/credit.py)"
PULSO = "reglas de «Países» (pulso_paises.py)"
# (clave, etiqueta, zona, unidad, decimales, regla, texto de la regla, origen de la regla, series de origen)
INDICADORES = [
    ("m2_aa", "M2 a/a", "EE. UU.", "%", 1, regla_m2, "< 0 % rojo; < 2 % o > 10 % ámbar", FIJA, ["M2SL"]),
    ("m2_real", "M2 real a/a (M2 / IPC)", "EE. UU.", "%", 1, regla_m2_real, "< −2 % rojo; < 0 % ámbar", FIJA,
     ["M2SL", "CPIAUCSL"]),
    ("vix", "VIX", "EE. UU.", "", 1, regla_vix, "≥ 30 rojo; ≥ 20 ámbar", FIJA, ["VIXCLS"]),
    ("hy", "Crédito HY (OAS)", "EE. UU.", "pp", 2, regla_hy, f"ámbar {THRESHOLDS['hy_oas'][0]}; rojo {THRESHOLDS['hy_oas'][1]}",
     CRED, ["BAMLH0A0HYM2"]),
    ("ig", "Crédito IG (OAS)", "EE. UU.", "pp", 2, regla_ig, "≥ 2,5 pp rojo; ≥ 1,5 pp ámbar", FIJA, ["BAMLC0A0CM"]),
    ("c10_3m", "Curva 10a − 3m", "EE. UU.", "pp", 2, regla_curva, f"ámbar {THRESHOLDS['curve'][0]}; rojo {THRESHOLDS['curve'][1]}",
     CRED, ["T10Y3M"]),
    ("c10_2a", "Curva 10a − 2a", "EE. UU.", "pp", 2, regla_curva, "la misma regla que la curva 10a−3m del monitor",
     CRED + ", aplicada a 10a−2a", ["T10Y2Y"]),
    ("ipc", "IPC general a/a", "EE. UU.", "%", 1, regla_infl, "> 5 % rojo; 3-5 % o < 1 % ámbar", PULSO, ["CPIAUCSL"]),
    ("ipc_sub", "IPC subyacente a/a", "EE. UU.", "%", 1, regla_infl, "> 5 % rojo; 3-5 % o < 1 % ámbar", PULSO,
     ["CPILFESL"]),
    ("t5yie", "Inflación implícita 5a", "EE. UU.", "%", 2, regla_implicita, "> 3 % rojo; > 2,5 % o < 1,5 % ámbar", FIJA,
     ["T5YIE"]),
    ("paro", "Paro", "EE. UU.", "%", 1, regla_paro, "sube ≥ 0,5 pp en 12 meses rojo; ≥ 0,2 pp ámbar", PULSO, ["UNRATE"]),
    ("liq", "Liquidez neta Fed (WALCL − TGA − RRP)", "EE. UU.", "mm USD", 0, regla_liq,
     "cae ≥ 10 % en 13 semanas rojo; ≥ 5 % ámbar", FIJA, ["WALCL", "WTREGEN", "RRPONTSYD"]),
    ("nfci", "NFCI (Chicago Fed)", "EE. UU.", "", 2, regla_nfci, f"ámbar {THRESHOLDS['nfci'][0]}; rojo {THRESHOLDS['nfci'][1]}",
     CRED, ["NFCI"]),
    ("stlfsi", "STLFSI (St. Louis Fed)", "EE. UU.", "", 2, regla_stlfsi,
     f"ámbar {THRESHOLDS['stlfsi'][0]}; rojo {THRESHOLDS['stlfsi'][1]}", CRED, ["STLFSI4"]),
    ("dolar", "Dólar (índice amplio)", "EE. UU.", "", 1, regla_dolar, "sube ≥ 15 % en 12 meses rojo; ≥ 10 % ámbar", FIJA,
     ["DTWEXBGS"]),
    ("wti", "Petróleo WTI", "EE. UU.", "USD", 1, regla_petroleo, "sube ≥ 100 % en 12 meses rojo; ≥ 50 % ámbar", FIJA,
     ["DCOILWTICO"]),
    ("sp500", "S&P 500: caída desde su máximo de 12 meses", "EE. UU.", "%", 1, regla_bolsa,
     "caída ≥ 20 % rojo; ≥ 10 % ámbar", PULSO, ["SP500"]),
    ("ea_ipc", "IPCA general a/a", "Zona euro", "%", 1, regla_infl, "> 5 % rojo; 3-5 % o < 1 % ámbar", PULSO,
     ["ecb_hicp_headline_yoy_ea_m"]),
    ("ea_sub", "IPCA subyacente a/a", "Zona euro", "%", 1, regla_infl, "> 5 % rojo; 3-5 % o < 1 % ámbar", PULSO,
     ["ecb_hicp_core_yoy_ea_m"]),
    ("ea_m3", "M3 a/a", "Zona euro", "%", 1, regla_m2, "< 0 % rojo; < 2 % o > 10 % ámbar", FIJA, ["ecb_m3_yoy_m"]),
    ("ea_paro", "Paro", "Zona euro", "%", 1, regla_paro, "sube ≥ 0,5 pp en 12 meses rojo; ≥ 0,2 pp ámbar", PULSO,
     ["eurostat_unemp_ea_m"]),
    ("ea_ciss", "Estrés financiero CISS (BCE)", "Zona euro", "", 2, regla_ciss, "≥ 0,4 rojo; ≥ 0,2 ámbar", FIJA,
     ["ecb_ciss_new_ea_d"]),
]


def serie_indicador(clave: str, raw: dict[str, pd.Series], liq: pd.Series | None = None) -> pd.Series:
    """Serie que muestra cada indicador (transformada) a partir de las series en bruto."""
    g = lambda s: raw.get(s, pd.Series(dtype=float))  # noqa: E731
    if clave == "m2_aa":
        return yoy(g("M2SL"))
    if clave == "m2_real":
        m, p = yoy(g("M2SL")), yoy(g("CPIAUCSL"))
        j = pd.concat([m, p], axis=1, join="inner").dropna()
        return (100 * ((1 + j.iloc[:, 0] / 100) / (1 + j.iloc[:, 1] / 100) - 1)) if len(j) else pd.Series(dtype=float)
    if clave in ("ipc", "ipc_sub"):
        return yoy(g("CPIAUCSL" if clave == "ipc" else "CPILFESL"))
    if clave == "liq":
        return liq if liq is not None else pd.Series(dtype=float)
    if clave == "sp500":
        return caida_desde_max(g("SP500"))
    sid = next(i for i in INDICADORES if i[0] == clave)[8][0]
    return g(sid).dropna()


def sparkline(x: pd.Series, meses: int = 24, w: int = 120, h: int = 28) -> str:
    x = x.dropna()
    if x.empty:
        return ""
    x = x[x.index >= x.index[-1] - pd.DateOffset(months=meses)]
    if len(x) > 120:
        x = x.resample("W").last().dropna()
    if len(x) < 2:
        return ""
    lo, hi = float(x.min()), float(x.max())
    rng = (hi - lo) or 1.0
    n = len(x) - 1
    pts = [(2 + (w - 4) * i / n, 2 + (h - 4) * (1 - (float(v) - lo) / rng)) for i, v in enumerate(x.values)]
    path = " ".join(f"{a:.1f},{b:.1f}" for a, b in pts)
    cero = ""
    if lo < 0 < hi:
        y0 = 2 + (h - 4) * (1 - (0 - lo) / rng)
        cero = f'<line x1="0" x2="{w}" y1="{y0:.1f}" y2="{y0:.1f}" class="hz0"/>'
    xa, ya = pts[-1]
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true">{cero}'
            f'<polyline points="{path}"/><circle cx="{xa:.1f}" cy="{ya:.1f}" r="2.2"/></svg>')


def ficha(clave: str, x: pd.Series) -> dict:
    """Valor, fecha, cambio, percentil y semáforo de un indicador (sin HTML)."""
    meta = next(i for i in INDICADORES if i[0] == clave)
    x = x.dropna()
    color, texto = meta[5](x)
    d = {"clave": clave, "etiqueta": meta[1], "zona": meta[2], "unidad": meta[3], "dec": meta[4], "color": color,
         "estado": texto, "regla": meta[6], "origen": meta[7], "fija": meta[7] == FIJA, "series": meta[8],
         "valor": None, "fecha": None, "anterior": None, "cambio": None, "percentil": None, "desde": None}
    if x.empty:
        return d
    d.update(valor=float(x.iloc[-1]), fecha=x.index[-1].date().isoformat(), percentil=percentil(x),
             desde=f"{x.index[0]:%Y}")
    if len(x) >= 2:
        d["anterior"] = float(x.iloc[-2])
        d["cambio"] = d["valor"] - d["anterior"]
    return d


# ----------------------------------------------------------------------------------------------- datos nuevos
def novedades_estado(ultimas: pd.DataFrame, estado: dict, hoy: date, publicado: dict | None = None,
                     excluir: set | None = None) -> tuple[list[dict], dict]:
    """Compara la última observación de cada serie con el estado guardado.

    `ultimas`: columnas series_id, d1, v1, d2, v2 (última y penúltima observación), nombre, freq.
    `estado`: {"series": {sid: [fecha, valor]}, "eventos": [...]} (vacío la primera vez).
    `publicado`: {sid: date} (p. ej. last_updated de FRED) para sembrar eventos cuando no hay estado.
    Devuelve (eventos de los últimos DIAS_NUEVO días, estado nuevo).
    """
    excluir = excluir or set()
    prev = (estado or {}).get("series") or {}
    eventos = [e for e in (estado or {}).get("eventos") or []
               if (hoy - date.fromisoformat(e["detectado"])).days <= DIAS_NUEVO]
    nuevo = {}
    sembrar = not prev
    for r in ultimas.itertuples(index=False):
        sid = r.series_id
        d1 = str(r.d1)[:10]
        v1 = None if pd.isna(r.v1) else float(r.v1)
        nuevo[sid] = [d1, v1]
        if sid in excluir:
            continue
        base = {"series_id": sid, "nombre": getattr(r, "nombre", None) or sid, "freq": getattr(r, "freq", None),
                "fecha": d1, "valor": v1, "detectado": hoy.isoformat(), "via": "estado"}
        d2 = None if pd.isna(r.d2) else str(r.d2)[:10]
        v2 = None if pd.isna(r.v2) else float(r.v2)
        if sid in prev:
            pf, pv = prev[sid]
            if d1 > pf:
                rev = None
                if d2 == pf and pv is not None and v2 is not None:
                    rev = not math.isclose(v2, pv, rel_tol=1e-9, abs_tol=1e-12)
                eventos.append({**base, "fecha_ant": d2, "valor_ant": v2, "revisado": rev,
                                "valor_ant_antes": pv if rev else None})
            elif d1 == pf and v1 is not None and pv is not None and not math.isclose(v1, pv, rel_tol=1e-9, abs_tol=1e-12):
                eventos.append({**base, "fecha_ant": d1, "valor_ant": pv, "revisado": True, "valor_ant_antes": pv,
                                "solo_revision": True})
        elif sembrar and publicado and sid in publicado and (hoy - publicado[sid]).days <= DIAS_NUEVO:
            eventos.append({**base, "fecha_ant": d2, "valor_ant": v2, "revisado": None,
                            "detectado": publicado[sid].isoformat(), "via": "fecha de actualización de FRED"})
    # una entrada por serie (la más reciente)
    unicos = {}
    for e in eventos:
        k = e["series_id"]
        if k not in unicos or (e["detectado"], e["fecha"]) >= (unicos[k]["detectado"], unicos[k]["fecha"]):
            unicos[k] = e
    ev = list(unicos.values())
    return ev, {"actualizado": hoy.isoformat(), "series": nuevo, "eventos": ev}


def novedades_vintages(v: pd.DataFrame, hoy: date) -> list[dict]:
    """Novedades desde vintages ALFRED: la última vintage ≤ hoy en los últimos DIAS_NUEVO días.

    `v`: columnas series_id, date, value, realtime_start. Revisado = el dato anterior al último nuevo tenía otro
    valor en la vintage previa."""
    out = []
    if v is None or v.empty:
        return out
    v = v.copy()
    v["date"] = pd.to_datetime(v["date"])
    v["realtime_start"] = pd.to_datetime(v["realtime_start"])
    v = v[v["realtime_start"] <= pd.Timestamp(hoy)]
    for sid, g in v.groupby("series_id"):
        V = g["realtime_start"].max()
        if (pd.Timestamp(hoy) - V).days > DIAS_NUEVO:
            continue
        ahora = g.sort_values("realtime_start").drop_duplicates("date", keep="last").set_index("date")["value"].sort_index()
        antes = (g[g["realtime_start"] < V].sort_values("realtime_start").drop_duplicates("date", keep="last")
                 .set_index("date")["value"].sort_index())
        nuevas = ahora.index.difference(antes.index)
        if len(nuevas) == 0:  # solo revisiones
            rev = [d for d in ahora.index if d in antes.index and not math.isclose(ahora[d], antes[d], rel_tol=1e-9)]
            if not rev:
                continue
            d = rev[-1]
            out.append({"series_id": sid, "fecha": f"{d:%Y-%m-%d}", "valor": float(ahora[d]), "fecha_ant": f"{d:%Y-%m-%d}",
                        "valor_ant": float(antes[d]), "revisado": True, "valor_ant_antes": float(antes[d]),
                        "solo_revision": True, "detectado": f"{V:%Y-%m-%d}", "via": "vintage ALFRED"})
            continue
        d1 = nuevas.max()
        prev_idx = ahora.index[ahora.index < d1]
        d2 = prev_idx.max() if len(prev_idx) else None
        e = {"series_id": sid, "fecha": f"{d1:%Y-%m-%d}", "valor": float(ahora[d1]), "detectado": f"{V:%Y-%m-%d}",
             "via": "vintage ALFRED", "fecha_ant": None, "valor_ant": None, "revisado": None, "valor_ant_antes": None}
        if d2 is not None:
            e.update(fecha_ant=f"{d2:%Y-%m-%d}", valor_ant=float(ahora[d2]))
            if d2 in antes.index:
                e["revisado"] = not math.isclose(float(ahora[d2]), float(antes[d2]), rel_tol=1e-9)
                e["valor_ant_antes"] = float(antes[d2]) if e["revisado"] else None
        out.append(e)
    return out


def ordenar_novedades(ev: list[dict]) -> list[dict]:
    rank = {s: i for i, s in enumerate(CLAVE)}
    return sorted(ev, key=lambda e: (rank.get(e["series_id"], len(CLAVE)),
                                     -(date.fromisoformat(e["detectado"]).toordinal() if e.get("detectado") else 0),
                                     e["series_id"]))


# ----------------------------------------------------------------------------------------------- lectura warehouse
def _ultimas(con) -> pd.DataFrame:
    q = """with r as (select series_id, date, value,
                 row_number() over (partition by series_id order by date desc) rn
               from obs_latest where value is not null)
           select r.series_id, max(case when rn = 1 then date end) d1, max(case when rn = 1 then value end) v1,
                  max(case when rn = 2 then date end) d2, max(case when rn = 2 then value end) v2,
                  any_value(c.name) nombre, any_value(c.frequency) freq
           from r left join catalog c using (series_id) where rn <= 2 group by r.series_id"""
    df = con.execute(q).df()
    # las series diarias no son «publicaciones»: salen en la franja con su fecha
    return df[df["freq"].fillna("").str[:1] != "D"].reset_index(drop=True)


def _publicado_fred() -> dict:
    out = {}
    for src in ("fred", "fred_us"):
        p = db.DATA_ROOT / "curated" / src / "_catalog.csv"
        if not p.exists():
            continue
        try:
            c = pd.read_csv(p, usecols=["series_id", "last_updated"]).dropna()
        except Exception:  # noqa: BLE001
            continue
        for sid, lu in zip(c["series_id"], c["last_updated"]):
            try:
                out[sid] = date.fromisoformat(str(lu)[:10])
            except ValueError:
                pass
    return out


def _leer_estado(d: Path | None) -> dict:
    if d is None:
        return {}
    p = Path(d) / ESTADO_FICHERO
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return {}


def _guardar_estado(d: Path | None, est: dict) -> None:
    if d is None:
        return
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    tmp = p / (ESTADO_FICHERO + ".tmp")
    tmp.write_text(json.dumps(est, ensure_ascii=False, separators=(",", ":")))
    tmp.replace(p / ESTADO_FICHERO)


def calcular(con, hoy: date, estado_dir: Path | None) -> dict:
    sids = sorted({s for i in INDICADORES for s in i[8]})
    raw = {s: db.series(con, s) for s in sids}
    raw = {s: x[x.index <= pd.Timestamp(hoy)] for s, x in raw.items()}
    liq = None
    try:
        series, unidades = LV.cargar(con, hoy)
        liq = LV.liquidez(series, unidades, pd.Timestamp(hoy))["_neta_serie"]
    except Exception:  # noqa: BLE001
        liq = None
    fichas, sparks = [], {}
    for i in INDICADORES:
        x = serie_indicador(i[0], raw, liq)
        fichas.append(ficha(i[0], x))
        sparks[i[0]] = sparkline(x)
    # novedades
    try:
        v = con.execute("select series_id, date, value, realtime_start from vintages "
                        "where realtime_start >= ? and series_id in (select distinct series_id from vintages "
                        "where realtime_start between ? and ?)",
                        [hoy - timedelta(days=400), hoy - timedelta(days=DIAS_NUEVO), hoy]).df()
    except Exception:  # noqa: BLE001
        v = pd.DataFrame()
    ev_v = novedades_vintages(v, hoy)
    ult = _ultimas(con)
    nombres = dict(zip(ult["series_id"], ult["nombre"]))
    ev_e, est = novedades_estado(ult, _leer_estado(estado_dir), hoy, _publicado_fred(),
                                 excluir={e["series_id"] for e in ev_v})
    for e in ev_v:
        e["nombre"] = nombres.get(e["series_id"]) or e["series_id"]
    _guardar_estado(estado_dir, est)
    return {"fichas": fichas, "sparks": sparks, "novedades": ordenar_novedades(ev_v + ev_e)}


# ----------------------------------------------------------------------------------------------- avisos del reporte
DIMS = {"inflacion": "inflación", "crecimiento": "crecimiento", "empleo": "empleo", "bonos": "bonos",
        "fiscal": "fiscal", "bolsa": "bolsa", "confianza": "confianza"}


def avisos_reporte(s: dict) -> list[tuple[str, str]]:
    """(color, texto) de lo que ya marca el reporte semanal en rojo/ámbar."""
    out = []
    cr = (s or {}).get("credit") or {}
    if cr.get("light") in ("rojo", "ámbar"):
        out.append(("rojo" if cr["light"] == "rojo" else "ambar",
                    f"Monitor de fractura de crédito en {cr['light']} ({cr.get('reds')} rojos, {cr.get('ambers')} ámbar)."))
    for k, d in (cr.get("indicators") or {}).items():
        if isinstance(d, dict) and d.get("status") in ("rojo", "ámbar"):
            out.append(("rojo" if d["status"] == "rojo" else "ambar",
                        f"Monitor de crédito: {k} en {d['status']} (valor {fnum(d.get('value'), 2)})."))
    r = (s or {}).get("regime") or {}
    if r.get("sahm_trigger"):
        out.append(("rojo", f"Regla de Sahm disparada ({fnum(r.get('sahm'), 2)} pp)."))
    tv = ((s or {}).get("termometro") or {}).get("paises") or {}
    rec = [c for c, p in tv.items() if (p.get("estado") or {}).get("en_recesion")]
    if rec:
        out.append(("ambar", "Termómetro: en recesión según el fechado trimestral: " + ", ".join(
            PUL.NOMBRE.get(c, c) for c in rec) + "."))
    ag = (((s or {}).get("nowcast") or {}).get("agregado") or {})
    if ag.get("paises_alto"):
        out.append(("ambar", "Nowcast de recesión en banda alta: " + ", ".join(
            PUL.NOMBRE.get(c, c) for c in ag["paises_alto"]) + "."))
    pp = (((s or {}).get("pulso_paises") or {}).get("paises") or {})
    rojos = []
    for c, p in (pp.items() if isinstance(pp, dict) else []):
        for dim, col in (p.get("colores") or {}).items():
            if (col or {}).get("color") == "rojo":
                rojos.append(f"{p.get('nombre') or c} ({DIMS.get(dim, dim)})")
    if rojos:
        out.append(("rojo", f"Países en rojo en alguna dimensión ({len(rojos)}): " + ", ".join(rojos) + "."))
    return out


# ----------------------------------------------------------------------------------------------- HTML
CSS = """<style>
.spark{display:block;margin-top:4px;overflow:visible}.spark polyline{fill:none;stroke:var(--s1);stroke-width:1.5}
.spark circle{fill:var(--s1)}.spark .hz0{stroke:var(--axis);stroke-width:1;stroke-dasharray:2 2}
.tile.t-rojo{box-shadow:inset 4px 0 0 var(--crit)}.tile.t-ambar{box-shadow:inset 4px 0 0 var(--warn)}
.tile.t-verde{box-shadow:inset 4px 0 0 var(--good)}.tile .tl{font-size:13px;color:var(--ink2);font-weight:600}
.tile strong.v{font-size:22px}.enrojo li{margin:5px 0}.zona-h{margin:14px 0 2px;font-size:14px;color:var(--ink2)}
</style>"""
SIMB = {"rojo": "●", "ambar": "●", "verde": "●", "gris": "○"}
NCOL = {"rojo": "rojo", "ambar": "ámbar", "verde": "verde", "gris": "sin dato"}


def chip(color: str, texto: str) -> str:
    return f'<span class="chip c-{color}"><span aria-hidden="true">{SIMB.get(color, "○")}</span>{esc(texto)}</span>'


def _fmt_val(f: dict, v=None) -> str:
    v = f["valor"] if v is None else v
    u = f["unidad"]
    t = fnum(v, f["dec"])
    return t + ("" if not u else (" %" if u == "%" else f" {u}"))


def tile(f: dict, spark: str) -> str:
    if f["valor"] is None:
        return (f'<div class="tile"><span class="tl">{esc(f["etiqueta"])}</span>{ND}'
                f'<span class="muted">serie {esc(", ".join(f["series"]))}</span></div>')
    unid = "pp" if f["unidad"] in ("%", "pp") else f["unidad"]
    cambio = fnum(f["cambio"], f["dec"], True) + (f" {unid}" if unid else "") if f["cambio"] is not None else "—"
    pc = f"p{int(f['percentil'])}" if f["percentil"] is not None else "p—"
    tip = (f"{f['etiqueta']}: {NCOL[f['color']]} ({f['estado']}). Regla: {f['regla']} — {f['origen']}. "
           f"Percentil {pc} en su historia desde {f['desde']}. Series: {', '.join(f['series'])}.")
    fija = ' <span class="muted">· regla fija, no validada</span>' if f["fija"] else ""
    return (f'<div class="tile t-{f["color"]}" tabindex="0" data-tip="{esc(tip)}"><span class="tl">{esc(f["etiqueta"])}</span>'
            f'<span>{chip(f["color"], NCOL[f["color"]] + " · " + f["estado"])}{fija}</span>'
            f'<strong class="v">{esc(_fmt_val(f))}</strong>'
            f'<span class="small">dato del {esc(f["fecha"])} · Δ {esc(cambio)} vs anterior · {pc} (desde {esc(f["desde"])})</span>'
            f'{spark}</div>')


def html_novedades(ev: list[dict], hoy: date, max_vis: int = 15) -> str:
    if not ev:
        return ('<p>Ninguna serie no diaria cambió su último dato en los últimos 7 días (o es la primera ejecución y '
                'aún no hay estado con el que comparar).</p>')
    filas = []
    for e in ev:
        rev = ("—" if e.get("revisado") is None else
               (f'sí: {fnum(e.get("valor_ant_antes"), 2)} → {fnum(e.get("valor_ant"), 2)}' if e["revisado"] else "no"))
        clave = ' <span class="chip c-verde"><span aria-hidden="true">★</span>clave</span>' if e["series_id"] in CLAVE else ""
        nuevo = ("revisión del último dato" if e.get("solo_revision") else
                 f'{esc(e["fecha"])}: <strong>{fnum(e.get("valor"), 2)}</strong>')
        ant = "—" if e.get("fecha_ant") is None or e.get("solo_revision") else f'{esc(e["fecha_ant"])}: {fnum(e.get("valor_ant"), 2)}'
        filas.append(f'<tr><td>{esc((e.get("nombre") or e["series_id"])[:90])}{clave}<br><span class="muted">{esc(e["series_id"])}</span></td>'
                     f'<td>{nuevo}</td><td>{ant}</td><td>{rev}</td>'
                     f'<td>{esc(e.get("detectado"))}<br><span class="muted">{esc(e.get("via"))}</span></td></tr>')
    cab = ("<thead><tr><th>serie</th><th>dato nuevo</th><th>dato anterior (valor de hoy)</th>"
           "<th>¿se revisó el anterior?</th><th>visto / publicado</th></tr></thead>")
    t1 = f'<div class="tw"><table class="num">{cab}<tbody>{"".join(filas[:max_vis])}</tbody></table></div>'
    resto = filas[max_vis:]
    if resto:
        t1 += (f'<details><summary>Ver {len(resto)} series más</summary><div class="tw"><table class="num">{cab}'
               f'<tbody>{"".join(resto)}</tbody></table></div></details>')
    return t1


def sec_hoy_diario(s: dict, hoy: date | None = None, estado_dir: Path | None = None, con=None) -> str:
    """HTML de la pestaña «Hoy». Abre el warehouse en solo lectura si no se le da conexión."""
    hoy = hoy or date.today()
    estado_dir = estado_dir if estado_dir is not None else ESTADO_DIR
    cerrar = con is None
    con = con or db.connect()
    try:
        r = calcular(con, hoy, estado_dir)
    finally:
        if cerrar:
            con.close()
    fichas = r["fichas"]
    # En rojo
    alerta = [(f["color"], f'{f["zona"]} · {f["etiqueta"]}: {_fmt_val(f)} ({f["estado"]}; dato del {f["fecha"]})'
               + (" — regla fija, no validada" if f["fija"] else ""))
              for f in fichas if f["color"] in ("rojo", "ambar")]
    alerta += avisos_reporte(s)
    alerta.sort(key=lambda a: 0 if a[0] == "rojo" else 1)
    if alerta:
        li = "".join(f"<li>{chip(c, NCOL[c])} {esc(t)}</li>" for c, t in alerta)
        enrojo = f'<ul class="avisos enrojo">{li}</ul>'
    else:
        enrojo = f'<p>{chip("verde", "nada en rojo")} Ningún indicador de la franja ni del reporte está en rojo o ámbar.</p>'
    nr = sum(1 for a in alerta if a[0] == "rojo")
    out = [CSS, f'<p class="disc"><strong>No es asesoramiento.</strong> {esc(AVISO)}</p>',
           f'<div class="card"><h3>En rojo o ámbar hoy <span class="muted">({nr} en rojo, {len(alerta) - nr} en ámbar · '
           f'{esc(hoy.isoformat())})</span></h3>{enrojo}'
           '<p class="note">Incluye la franja de abajo y los avisos del último reporte semanal (monitor de crédito, '
           'Sahm, termómetro, nowcast y colores de «Países»). Los avisos de datos viejos están en «Estado y avisos».</p></div>']
    # franja
    bloques = []
    for zona in ("EE. UU.", "Zona euro"):
        fs = [f for f in fichas if f["zona"] == zona]
        if zona == "Zona euro" and all(f["valor"] is None for f in fs):
            continue
        bloques.append(f'<h4 class="zona-h">{esc(zona)}</h4><div class="tiles">'
                       + "".join(tile(f, r["sparks"][f["clave"]]) for f in fs) + "</div>")
    out.append('<div class="card"><h3>Indicadores clave</h3>'
               '<p class="note">Valor y fecha del último dato, cambio frente al dato anterior, percentil del valor en '
               'toda su historia (p90 = más alto que el 90 % de su historia) y la línea de los últimos 24 meses. '
               'Pasa el ratón o el foco por una ficha para ver la regla del color y su origen. Las series se '
               'actualizan a diario (ingesta diaria) cuando la fuente publica.</p>' + "".join(bloques) + "</div>")
    out.append(f'<div class="card"><h3>Datos nuevos publicados (últimos {DIAS_NUEVO} días)</h3>'
               '<p class="note">Series mensuales, semanales o trimestrales cuyo último dato cambió. Primero las '
               'series clave (★), luego el resto por fecha. «Revisado» compara el dato anterior con su valor en la '
               'publicación previa (vintage ALFRED o lo visto por el panel el día anterior). Las series diarias '
               '(mercados) no se listan: su fecha sale en cada ficha.</p>' + html_novedades(r["novedades"], hoy) + "</div>")
    return "\n".join(out)
