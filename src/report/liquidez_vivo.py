"""Liquidez y crédito (EE. UU.): sección DESCRIPTIVA del reporte semanal (5e).

Informativa: sin señal, sin probabilidades, sin umbrales optimizados y NO validada (no hay historia suficiente: el
balance de la Fed semanal empieza en 2002-12, el repo inverso solo es relevante desde 2013 y el HY/CCC del warehouse
empieza en 2023). Todo sale de `obs_latest` (última publicación, sin vintages), con las observaciones ≤ la fecha pedida.

Contenido:
(a) liquidez neta = WALCL − TGA (WTREGEN) − RRP (RRPONTSYD), en miles de millones de USD, y su flujo a 4 y 13 semanas;
    reservas (WRESBAL) y M2 (M2SL). Unidades del catálogo (WALCL, WTREGEN, WRESBAL en millones; RRPONTSYD y M2SL en
    miles de millones); si el catálogo no las tiene se usan las conocidas de FRED (UNIDADES_FRED) y si dice algo distinto
    de lo esperado se falla (no se mezclan escalas en silencio).
(b) crédito y volatilidad: nivel, Δ1 mes, Δ3 meses y percentil en su historia disponible (desde la primera observación).
(c) descomposición del movimiento del 10 años a 4 y 13 semanas: tipo real (DFII10) + inflación implícita (T10YIE)
    frente a DGS10, y prima por plazo (ACM tp10) + expectativas (ACM rny10) frente al rendimiento ACM y10.
(d) divergencias descriptivas de una lista fija (DIVERGENCIAS): solo el signo de cada cambio, sin umbrales.
Cada dato lleva la fecha de su último valor y aviso si está viejo (EDAD_MAX_DIAS por frecuencia).
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from src.warehouse import db

TITULO = "## 5e. Liquidez y crédito (EE. UU., descriptivo)"
AVISO = ("Descriptivo e informativo: no es una señal ni da probabilidades, y NO está validado. No hay historia "
         "suficiente para validarlo: el balance semanal de la Fed empieza en 2002, el repo inverso solo es relevante "
         "desde 2013 y el HY/CCC disponible empieza en 2023. Las divergencias son una lista fija definida en el código "
         "(solo el signo de los cambios), sin umbrales optimizados ni historial de aciertos.")

# unidades esperadas (FRED, 2026); el catálogo manda pero debe coincidir
UNIDADES_FRED = {"WALCL": "millions", "WTREGEN": "millions", "WRESBAL": "millions", "RRPONTSYD": "billions",
                 "M2SL": "billions"}
SERIES = ["WALCL", "WTREGEN", "RRPONTSYD", "WRESBAL", "M2SL", "BAA10Y", "AAA10Y", "BAMLH0A0HYM2", "BAMLH0A3HYC",
          "VIXCLS", "DFII10", "T10YIE", "DGS10", "nyfed_acm_y10_d", "nyfed_acm_tp10_d", "nyfed_acm_rny10_d", "SP500"]
# frecuencia de publicación → días máximos desde el último dato antes de avisar (mensual: la fecha es el día 1 del mes
# y M2 sale ≈ 4 semanas después de cerrar el mes)
FRECUENCIA = {"WALCL": "semanal", "WTREGEN": "semanal", "WRESBAL": "semanal", "M2SL": "mensual"}
EDAD_MAX_DIAS = {"diaria": 7, "semanal": 14, "mensual": 75}

# (clave, etiqueta, series_id o None si es derivado, unidad, nota)
CREDITO = [("baa10y", "Baa − 10a", "BAA10Y", "pp", ""),
           ("aaa10y", "Aaa − 10a", "AAA10Y", "pp", ""),
           ("baa_aaa", "Baa − Aaa", None, "pp", "derivado"),
           ("hy", "HY OAS (ICE BofA)", "BAMLH0A0HYM2", "pp", "historia corta (desde 2023)"),
           ("ccc", "CCC OAS (ICE BofA)", "BAMLH0A3HYC", "pp", "historia corta (desde 2023)"),
           ("vix", "VIX", "VIXCLS", "índice", "")]

# divergencias fijas: (texto, [(clave de cambio, signo esperado)]); se cumple si todos los signos coinciden
DIVERGENCIAS = [
    ("Bolsa sube a 1 mes y el HY se ensancha a 1 mes", [("sp500_1m", +1), ("hy_1m", +1)]),
    ("Bolsa sube a 1 mes y el VIX sube a 1 mes", [("sp500_1m", +1), ("vix_1m", +1)]),
    ("HY se estrecha a 1 mes y el CCC se ensancha a 1 mes", [("hy_1m", -1), ("ccc_1m", +1)]),
    ("Bolsa sube a 3 meses y Baa − Aaa se ensancha a 3 meses", [("sp500_3m", +1), ("baa_aaa_3m", +1)]),
    ("Bolsa sube a 3 meses y la liquidez neta cae a 13 semanas", [("sp500_3m", +1), ("liq_13s", -1)]),
    ("Bolsa sube a 3 meses y el tipo real 10a sube a 13 semanas", [("sp500_3m", +1), ("dfii10_13s", +1)]),
]


class UnidadesInesperadas(RuntimeError):
    """El catálogo declara unidades distintas de las esperadas: no se mezclan escalas."""


# ---------------------------------------------------------------- carga
def _unidades(con, sid: str) -> str:
    try:
        row = con.execute("select units from catalog where series_id = ? and units is not null limit 1",
                          [sid]).fetchone()
    except Exception:  # noqa: BLE001  (warehouse sin catálogo, p. ej. en tests)
        row = None
    return (row[0] if row else UNIDADES_FRED.get(sid, "")).lower()


def cargar(con, fecha) -> tuple[dict, dict]:
    """Series de `obs_latest` con fecha ≤ `fecha` y las unidades de las de liquidez."""
    corte = pd.Timestamp(fecha)
    series = {}
    for sid in SERIES:
        s = db.series(con, sid)
        if s.empty:
            s = pd.Series(dtype=float, index=pd.DatetimeIndex([]), name=sid)
        series[sid] = s[s.index <= corte]
    return series, {sid: _unidades(con, sid) for sid in UNIDADES_FRED}


def a_miles_de_millones(s: pd.Series, unidades: str, sid: str) -> pd.Series:
    esperado = UNIDADES_FRED[sid]
    if esperado not in unidades:
        raise UnidadesInesperadas(f"{sid}: el catálogo dice «{unidades}», se esperaba «{esperado}»")
    return s / 1000 if esperado == "millions" else s


# ---------------------------------------------------------------- utilidades
def _r(v, n=2):
    return None if v is None or not np.isfinite(v) else round(float(v), n)


def _en(s: pd.Series, t: pd.Timestamp) -> float | None:
    """Último valor ≤ t (as of)."""
    s = s[s.index <= t]
    return None if s.empty else float(s.iloc[-1])


def _frecuencia(sid: str) -> str:
    return FRECUENCIA.get(sid, "diaria")


def _frescura(sid: str, s: pd.Series, hoy: pd.Timestamp) -> dict:
    if s.empty:
        return {"fecha": None, "edad_dias": None, "viejo": True}
    ult = s.index[-1]
    edad = int((hoy - ult).days)
    return {"fecha": str(ult.date()), "edad_dias": edad, "viejo": edad > EDAD_MAX_DIAS[_frecuencia(sid)]}


def _cambio(s: pd.Series, desfase: pd.DateOffset) -> float | None:
    if s.empty:
        return None
    a = _en(s, s.index[-1] - desfase)
    return None if a is None else float(s.iloc[-1]) - a


def _percentil(s: pd.Series) -> float | None:
    s = s.dropna()
    if len(s) < 24:
        return None
    return round(float((s <= s.iloc[-1]).mean() * 100), 0)


S4, S13 = pd.DateOffset(weeks=4), pd.DateOffset(weeks=13)
M1, M3 = pd.DateOffset(months=1), pd.DateOffset(months=3)


# ---------------------------------------------------------------- cálculo
def liquidez(series: dict, unidades: dict, hoy: pd.Timestamp) -> dict:
    walcl = a_miles_de_millones(series["WALCL"], unidades["WALCL"], "WALCL")
    tga = a_miles_de_millones(series["WTREGEN"], unidades["WTREGEN"], "WTREGEN")
    rrp = a_miles_de_millones(series["RRPONTSYD"], unidades["RRPONTSYD"], "RRPONTSYD")
    res = a_miles_de_millones(series["WRESBAL"], unidades["WRESBAL"], "WRESBAL")
    m2 = a_miles_de_millones(series["M2SL"], unidades["M2SL"], "M2SL")
    # rejilla: los miércoles del balance con TGA; el RRP (diario) se toma as of ese día
    fechas = walcl.index.intersection(tga.index)
    neta = pd.Series([walcl[d] - tga[d] - (_en(rrp, d) or 0.0) for d in fechas], index=fechas, dtype=float)
    out = {"unidad": "mm USD (miles de millones)",
           "componentes": {k: {"valor": _r(_en(s, fechas[-1]) if len(fechas) else None, 1),
                               **_frescura(sid, series[sid], hoy)}
                           for k, s, sid in (("walcl", walcl, "WALCL"), ("tga", tga, "WTREGEN"),
                                             ("rrp", rrp, "RRPONTSYD"))}}
    # el RRP es diario: en la liquidez neta entra el del miércoles del balance; se enseña también el último
    out["componentes"]["rrp"]["ultimo"] = _r(_en(rrp, hoy), 1)
    if len(fechas):
        out["neta"] = {"valor": _r(neta.iloc[-1], 1), "fecha": str(fechas[-1].date()),
                       "flujo_4s": _r(_cambio(neta, S4), 1), "flujo_13s": _r(_cambio(neta, S13), 1),
                       "viejo": out["componentes"]["walcl"]["viejo"] or out["componentes"]["tga"]["viejo"]}
    else:
        out["neta"] = {"valor": None, "fecha": None, "flujo_4s": None, "flujo_13s": None, "viejo": True}
    out["reservas"] = {"valor": _r(_en(res, hoy), 1), "cambio_4s": _r(_cambio(res, S4), 1),
                       "cambio_13s": _r(_cambio(res, S13), 1), **_frescura("WRESBAL", series["WRESBAL"], hoy)}
    m2_yoy = None
    if len(m2):
        a = _en(m2, m2.index[-1] - pd.DateOffset(months=12))
        m2_yoy = None if not a else (float(m2.iloc[-1]) / a - 1) * 100
    out["m2"] = {"valor": _r(_en(m2, hoy), 1), "cambio_3m": _r(_cambio(m2, M3), 1), "a_a_pct": _r(m2_yoy, 1),
                 **_frescura("M2SL", series["M2SL"], hoy)}
    out["_neta_serie"] = neta
    return out


def credito(series: dict, hoy: pd.Timestamp) -> dict:
    baa, aaa = series["BAA10Y"], series["AAA10Y"]
    comun = baa.index.intersection(aaa.index)
    derivada = (baa[comun] - aaa[comun]).rename("BAA-AAA")
    out = {}
    for k, lab, sid, uni, nota in CREDITO:
        s = derivada if sid is None else series[sid]
        fr = _frescura(sid or "BAA10Y", s, hoy)
        out[k] = {"etiqueta": lab, "serie": sid or "BAA10Y − AAA10Y", "unidad": uni, "nota": nota,
                  "valor": _r(s.iloc[-1]) if len(s) else None, "cambio_1m": _r(_cambio(s, M1)),
                  "cambio_3m": _r(_cambio(s, M3)), "percentil": _percentil(s),
                  "desde": f"{s.index[0]:%Y-%m}" if len(s) else None, **fr}
    return out


def _descomp(partes: dict, total_sid: str, series: dict, desfase) -> dict:
    """Δ del total y de cada parte entre la última fecha común de las partes y la misma fecha − desfase."""
    idx = None
    for sid in partes.values():
        idx = series[sid].index if idx is None else idx.intersection(series[sid].index)
    if idx is None or not len(idx):
        return {"fecha": None}
    t = idx[-1]
    d = {k: _r(_en(series[sid], t) - _en(series[sid], t - desfase))
         if _en(series[sid], t - desfase) is not None else None for k, sid in partes.items()}
    tot = series[total_sid]
    t0, t1 = _en(tot, t - desfase), _en(tot, t)
    d["total"] = _r(t1 - t0) if t0 is not None and t1 is not None else None
    d["residuo"] = (_r(d["total"] - sum(d[k] for k in partes)) if d["total"] is not None
                    and all(d[k] is not None for k in partes) else None)
    d["fecha"] = str(t.date())
    return d


def diez_anos(series: dict, hoy: pd.Timestamp) -> dict:
    out = {}
    for nom, desf in (("4s", S4), ("13s", S13)):
        out[nom] = {"real_vs_inflacion": _descomp({"tipo_real": "DFII10", "inflacion_implicita": "T10YIE"}, "DGS10",
                                                  series, desf),
                    "prima_vs_expectativas": _descomp({"prima_plazo": "nyfed_acm_tp10_d",
                                                       "expectativas": "nyfed_acm_rny10_d"}, "nyfed_acm_y10_d",
                                                      series, desf)}
    out["frescura"] = {sid: _frescura(sid, series[sid], hoy)
                       for sid in ("DGS10", "DFII10", "T10YIE", "nyfed_acm_tp10_d", "nyfed_acm_rny10_d")}
    out["niveles"] = {sid: _r(series[sid].iloc[-1]) if len(series[sid]) else None
                      for sid in ("DGS10", "DFII10", "T10YIE", "nyfed_acm_tp10_d", "nyfed_acm_rny10_d")}
    return out


def _signo(v):
    return None if v is None else (1 if v > 0 else (-1 if v < 0 else 0))


def divergencias(cambios: dict) -> list[dict]:
    out = []
    for texto, conds in DIVERGENCIAS:
        vals = {k: cambios.get(k) for k, _ in conds}
        if any(v is None for v in vals.values()):
            estado = None
        else:
            estado = all(_signo(vals[k]) == sg for k, sg in conds)
        out.append({"divergencia": texto, "se_da": estado, "valores": vals})
    return out


def calcular(series: dict, unidades: dict, fecha) -> dict:
    hoy = pd.Timestamp(fecha)
    liq = liquidez(series, unidades, hoy)
    neta = liq.pop("_neta_serie")
    cred = credito(series, hoy)
    dz = diez_anos(series, hoy)
    sp = series["SP500"]
    sp_pct = {n: (None if not len(sp) or not _en(sp, sp.index[-1] - d)
                  else _r((float(sp.iloc[-1]) / _en(sp, sp.index[-1] - d) - 1) * 100))
              for n, d in (("1m", M1), ("3m", M3))}
    dfii = series["DFII10"]
    cambios = {"sp500_1m": sp_pct["1m"], "sp500_3m": sp_pct["3m"],
               "hy_1m": cred["hy"]["cambio_1m"], "ccc_1m": cred["ccc"]["cambio_1m"],
               "vix_1m": cred["vix"]["cambio_1m"], "baa_aaa_3m": cred["baa_aaa"]["cambio_3m"],
               "liq_13s": _r(_cambio(neta, S13), 1), "dfii10_13s": _r(_cambio(dfii, S13))}
    return {"fecha_calculo": str(hoy.date()), "aviso": AVISO, "liquidez": liq, "credito": cred, "diez_anos": dz,
            "bolsa": {"serie": "SP500", "cambio_1m_pct": sp_pct["1m"], "cambio_3m_pct": sp_pct["3m"],
                      **_frescura("SP500", sp, hoy)},
            "divergencias": divergencias(cambios)}


def liquidez_credito(con, fecha: date) -> dict:
    series, unidades = cargar(con, fecha)
    return calcular(series, unidades, fecha)


# ---------------------------------------------------------------- Markdown
def _f(v, suf="", signo=False):
    if v is None:
        return "—"
    return (f"{v:+,}" if signo else f"{v:,}").replace(",", " ") + suf


def _fecha(d: dict) -> str:
    if d.get("fecha") is None:
        return "sin dato"
    return d["fecha"] + (f" ⚠️ viejo ({d['edad_dias']} días)" if d.get("viejo") else "")


def markdown(res: dict, titulo: str = TITULO) -> str:
    L, C, Z = res["liquidez"], res["credito"], res["diez_anos"]
    n, rs, m2, comp = L["neta"], L["reservas"], L["m2"], L["componentes"]
    out = [f"{titulo} — {res['fecha_calculo']}", "",
           "> [!note] Descriptivo, sin señal y no validado", f"> {res['aviso']}", "",
           "### Liquidez (miles de millones de USD)", "",
           "| dato | valor | Δ 4 semanas | Δ 13 semanas | fecha del dato |", "|---|---|---|---|---|",
           f"| Liquidez neta = balance Fed − TGA − repo inverso | {_f(n['valor'])} | {_f(n['flujo_4s'], signo=True)} | "
           f"{_f(n['flujo_13s'], signo=True)} | {_fecha({**n, 'edad_dias': comp['walcl']['edad_dias']})} |",
           f"| Balance de la Fed (WALCL) | {_f(comp['walcl']['valor'])} | | | {_fecha(comp['walcl'])} |",
           f"| Cuenta del Tesoro, TGA (WTREGEN) | {_f(comp['tga']['valor'])} | | | {_fecha(comp['tga'])} |",
           f"| Repo inverso (RRPONTSYD) del día del balance ({n['fecha'] or '—'}) | {_f(comp['rrp']['valor'])} | | | "
           f"último: {_f(comp['rrp']['ultimo'])} el {_fecha(comp['rrp'])} |",
           f"| Reservas bancarias (WRESBAL) | {_f(rs['valor'])} | {_f(rs['cambio_4s'], signo=True)} | "
           f"{_f(rs['cambio_13s'], signo=True)} | {_fecha(rs)} |",
           f"| M2 (M2SL; Δ a 3 meses, a/a {_f(m2['a_a_pct'], ' %')}) | {_f(m2['valor'])} | | "
           f"{_f(m2['cambio_3m'], signo=True)} (3 m) | {_fecha(m2)} |", "",
           "WALCL, WTREGEN y WRESBAL vienen en millones y se pasan a miles de millones; RRPONTSYD y M2SL ya están en "
           "miles de millones. Flujo = cambio del stock frente al último dato ≤ 4 o 13 semanas antes.", "",
           "### Crédito y volatilidad", "",
           "| indicador | valor | Δ 1 mes | Δ 3 meses | percentil (historia disponible) | desde | fecha del dato |",
           "|---|---|---|---|---|---|---|"]
    for v in C.values():
        nota = f" — {v['nota']}" if v["nota"] and v["nota"] != "derivado" else ""
        out.append(f"| {v['etiqueta']}{nota} | {_f(v['valor'])} {v['unidad']} | {_f(v['cambio_1m'], signo=True)} | "
                   f"{_f(v['cambio_3m'], signo=True)} | {_f(None if v['percentil'] is None else int(v['percentil']))} | {v['desde'] or '—'} | {_fecha(v)} |")
    out += ["", "Percentil: posición del último valor entre todas las observaciones diarias desde «desde»; con HY/CCC "
            "(desde 2023) no dice nada del ciclo largo.", "",
            "### Movimiento del 10 años (pp)", "",
            "| ventana | Δ 10a nominal (DGS10) | tipo real (DFII10) | inflación implícita (T10YIE) | residuo | "
            "Δ 10a ACM | prima por plazo | expectativas | fechas |", "|---|---|---|---|---|---|---|---|---|"]
    for w, lab in (("4s", "4 semanas"), ("13s", "13 semanas")):
        a, b = Z[w]["real_vs_inflacion"], Z[w]["prima_vs_expectativas"]
        out.append(f"| {lab} | {_f(a.get('total'), signo=True)} | {_f(a.get('tipo_real'), signo=True)} | "
                   f"{_f(a.get('inflacion_implicita'), signo=True)} | {_f(a.get('residuo'), signo=True)} | "
                   f"{_f(b.get('total'), signo=True)} | {_f(b.get('prima_plazo'), signo=True)} | "
                   f"{_f(b.get('expectativas'), signo=True)} | {a.get('fecha') or '—'} / {b.get('fecha') or '—'} |")
    nv, fr = Z["niveles"], Z["frescura"]
    viejos = [f"{k} ({v['fecha']})" for k, v in fr.items() if v["viejo"]]
    out += ["", f"Niveles: 10a {_f(nv['DGS10'])} %, real {_f(nv['DFII10'])} %, implícita {_f(nv['T10YIE'])} %, "
            f"prima por plazo ACM {_f(nv['nyfed_acm_tp10_d'])} pp, expectativas ACM {_f(nv['nyfed_acm_rny10_d'])} %. "
            "Cada descomposición usa la última fecha común de sus partes (la de ACM puede ir unos días por detrás); "
            "la de ACM es la del modelo de Adrian-Crump-Moench (NY Fed), no la del DGS10."
            + (f" ⚠️ Datos viejos: {', '.join(viejos)}." if viejos else ""), "",
            "### Divergencias (lista fija, solo signos)", "",
            "| divergencia | ¿se da? | valores |", "|---|---|---|"]
    for d in res["divergencias"]:
        st = {True: "**sí**", False: "no", None: "sin dato"}[d["se_da"]]
        vals = ", ".join(f"{k} {_f(v, signo=True)}" for k, v in d["valores"].items())
        out.append(f"| {d['divergencia']} | {st} | {vals} |")
    b = res["bolsa"]
    out += ["", f"Bolsa: S&P 500 (SP500) {_f(b['cambio_1m_pct'], ' %', True)} a 1 mes, "
            f"{_f(b['cambio_3m_pct'], ' %', True)} a 3 meses (dato {_fecha(b)}). Spreads y VIX en pp/puntos; "
            "liquidez en miles de millones; tipo real en pp. Una divergencia «sí» es una descripción, no un aviso."]
    return "\n".join(out) + "\n"
