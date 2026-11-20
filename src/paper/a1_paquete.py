"""Paquete del día de A1 «selección de acciones» (docs/factors/A1_seleccion_acciones_spec.md v1.0 §3). SIN IA.

= el paquete de C1 (src/paper/c1_paquete.py: cuenta del perfil A1 o simulada, precios, régimen, alertas,
diagnósticos, panel, diario de A1) MÁS:
- `macro`: la salida de cada modelo macro citable (src/broker/a1_guardia.MACRO) con su fecha (las mismas que recibe M1)
  y `filtro_macro` (techo de bolsa del día, src/paper/a1_sombra.filtro_macro); `macro_disponibles`;
- `candidatas`: calidad XBRL y métricas del universo (S&P 500 actual + «Mis activos» + posiciones;
  src/paper/a1_candidatas.py); el detalle de las `N_DETALLE` mejores y, de todas, una fila compacta;
- `mis_activos`: por cada valor de «Mis activos», XBRL de los últimos trimestres, Form 4 (12 meses), 13F (último
  trimestre frente al anterior), 13D/13G y alertas;
- `empresa_disponible` (símbolo → fuentes de empresa con datos hoy), `universo_compra` y `sectores` (los usa la guardia);
- `sombra` (línea del día de la sombra teórica) y `cierres_simulacion` (para validar en los ensayos sin cuenta).
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import pandas as pd

from src.broker import a1_guardia as AGd
from src.broker import alpaca as A
from src.paper import a1_candidatas as K
from src.paper import a1_sombra as SA
from src.paper import c1_paquete as P
from src.paper import m1_paquete as MP
from src.paper import m1_sombra as S

REPO = A.REPO
LOG = REPO / "research" / "paper" / "decisiones_a1.jsonl"
VERSION = "a1-paquete-1"
N_DETALLE = 60
DIAS_FORM4 = 365


def leer_registro(ruta: Path | None = None) -> list[dict]:
    return P.leer_registro(ruta or LOG)


def raiz() -> Path:
    return Path(os.path.expanduser(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")))


def mis_activos() -> list[str]:
    from src.ingest.sec_insiders import tickers_mis_activos
    return tickers_mis_activos()


# --------------------------------------------------------------------------- «Mis activos»: Form 4, 13F, 13D/13G
def form4(tickers: list[str], hoy: dt.date, ruta: Path | None = None) -> dict:
    ruta = ruta or raiz() / "sec_form4" / "operaciones.parquet"
    if not ruta.exists():
        return {}
    d = pd.read_parquet(ruta)
    d = d[pd.to_datetime(d["trans_date"]) >= pd.Timestamp(hoy - dt.timedelta(days=DIAS_FORM4))]
    out = {}
    for t in tickers:
        x = d[d["ticker"] == t]
        if x.empty:
            continue
        imp = pd.to_numeric(x["shares"], errors="coerce").fillna(0) * pd.to_numeric(x["price"], errors="coerce").fillna(0)
        compras = x[x["code"] == "P"]
        ventas = x[(x["code"] == "S") & ~x["plan_10b5_1"].fillna(False).astype(bool)]
        out[t] = {"desde": str(hoy - dt.timedelta(days=DIAS_FORM4)), "operaciones": int(len(x)),
                  "compras_mercado_abierto": int(len(compras)), "compras_usd": round(float(imp[compras.index].sum()), 0),
                  "ventas_sin_plan": int(len(ventas)), "ventas_sin_plan_usd": round(float(imp[ventas.index].sum()), 0),
                  "ultima": str(pd.to_datetime(x["filing_date"]).max().date())}
    return out


def f13(tickers: list[str], ruta: Path | None = None) -> dict:
    ruta = ruta or raiz() / "sec_13f" / "posiciones.parquet"
    if not ruta.exists():
        return {}
    d = pd.read_parquet(ruta, columns=["ticker", "period", "gestor", "shares", "value"])
    out = {}
    for t in tickers:
        x = d[d["ticker"] == t]
        if x.empty:
            continue
        per = sorted(x["period"].unique())
        ult = x[x["period"] == per[-1]]
        ant = x[x["period"] == per[-2]] if len(per) > 1 else None
        fila = {"trimestre": str(pd.Timestamp(per[-1]).date()), "gestores": int(ult["gestor"].nunique()),
                "acciones": float(ult["shares"].sum())}
        if ant is not None and float(ant["shares"].sum()) > 0:
            fila["cambio_acciones_vs_trimestre_anterior"] = round(float(ult["shares"].sum()) / float(ant["shares"].sum()) - 1, 4)
        out[t] = fila
    return out


def flujos(tickers: list[str], ruta: Path | None = None) -> dict:
    ruta = ruta or raiz() / "sec_flujos" / "participaciones.parquet"
    if not ruta.exists():
        return {}
    d = pd.read_parquet(ruta)
    out = {}
    for t in tickers:
        x = d[d["ticker"] == t].sort_values("filing_date")
        if x.empty:
            continue
        out[t] = [{"presentado": str(pd.Timestamp(r["filing_date"]).date()), "form": r["form"], "quien": r["filer"],
                   "pct": r.get("pct")} for _, r in x.tail(5).iterrows()]
    return out


def _seguro(fn, *a):
    try:
        return fn(*a)
    except Exception as e:  # noqa: BLE001 — una fuente que falla no tumba el paquete
        return P._error(e)


def _ok(x) -> bool:
    return isinstance(x, dict) and "error" not in x


# --------------------------------------------------------------------------- todo junto
def compacta(f: dict) -> dict:
    m = f.get("metricas") or {}
    return {"calidad": f.get("calidad"), "rango": f.get("rango"), "sector": f.get("sector"),
            "anio_fiscal": f.get("anio_fiscal"), **{k: m.get(k) for k in ("roa", "margen_operativo", "crec_ingresos",
                                                                          "apalancamiento")}}


def disponibilidad(cand: dict, mis: list[str], xb: dict, f4: dict, f13_: dict, fl: dict,
                   alertas_: list) -> tuple[dict, list[str], dict]:
    """(empresa_disponible, universo_compra, sectores) — puras."""
    emp: dict[str, set] = {}
    for t, f in (cand.get("empresas") or {}).items():
        if f.get("calidad") is not None or any(v for v in (f.get("metricas") or {}).values()):
            emp.setdefault(t, set()).add("xbrl")
    if _ok(xb):
        for t in xb.get("empresas") or {}:
            emp.setdefault(t, set()).add("xbrl")
    for fuente, d in (("form4", f4), ("13f", f13_), ("flujos", fl)):
        if _ok(d):
            for t in d:
                emp.setdefault(t, set()).add(fuente)
    for a in alertas_ or []:
        if isinstance(a, dict) and a.get("ticker") and "error" not in a:
            emp.setdefault(a["ticker"], set()).add("alertas")
    for t in mis:
        emp.setdefault(t, set()).add("ficha")
    sectores = {t: f.get("sector") for t, f in (cand.get("empresas") or {}).items() if f.get("sector")}
    universo = sorted(t for t, f in (cand.get("empresas") or {}).items()
                      if f.get("calidad") is not None and f.get("sector") and t not in AGd.COLCHON)
    return {t: sorted(v) for t, v in sorted(emp.items())}, universo, sectores


def recoger(c: A.Cliente | None, hoy: dt.date | None = None, *, registro: list[dict] | None = None,
            sombra_previas: list[dict] | None = None, yahoo: bool = True, candidatas: dict | None = None) -> dict:
    hoy = hoy or dt.date.today()
    registro = leer_registro() if registro is None else registro
    base = P.recoger(c, hoy, registro=registro)
    if base["cuenta"].get("simulada"):
        base["cuenta"]["aviso"] = "ENSAYO sin claves de A1: cuenta ficticia, no es la cuenta paper"
    try:
        s, nombre = P.ultimo_signal()
    except Exception:  # noqa: BLE001
        s, nombre = None, None
    m = _seguro(MP.modelos, s, nombre, base)
    m = m if isinstance(m, dict) else {"error": "sin modelos"}
    x = S.entradas(s, S.e1_usa())
    fm = SA.filtro_macro(x)
    macro = {k: m.get(k) for k in AGd.MACRO if k != "filtro_macro"}
    macro["filtro_macro"] = {"fecha_publicacion": x.get("signal_asof"), **fm}
    macro_disp = [k for k in MP.disponibles(macro) if k in AGd.MACRO]
    if "filtro_macro" not in macro_disp and fm.get("techo_bolsa") is not None:
        macro_disp.append("filtro_macro")
    try:
        mis = mis_activos()
    except Exception:  # noqa: BLE001
        mis = []
    pos = [p["simbolo"] for p in base["cuenta"].get("posiciones") or [] if p.get("clase") == "accion"]
    cand = candidatas if candidatas is not None else _seguro(lambda: K.calcular(sorted(set(mis) | set(pos)), hoy=hoy))
    xb = m.get("xbrl") if isinstance(m.get("xbrl"), dict) else {"error": "sin XBRL de «Mis activos»"}
    f4, f13_, fl = _seguro(form4, mis, hoy), _seguro(f13, mis), _seguro(flujos, mis)
    alertas_ = [a for a in base.get("alertas") or [] if isinstance(a, dict)]
    emp, universo, sectores = disponibilidad(cand if _ok(cand) else {}, mis, xb, f4, f13_, fl, alertas_)
    emps = (cand.get("empresas") or {}) if _ok(cand) else {}
    mejores = K.mejores(cand, N_DETALLE) if _ok(cand) else []
    previas = SA.leer_registro() if sombra_previas is None else sombra_previas
    try:
        sombra = SA.sombra_del_dia(c, hoy, x, cand if _ok(cand) else {}, previas, yahoo=yahoo)
    except Exception as e:  # noqa: BLE001
        sombra = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
    # cierres para validar en los ensayos sin cuenta: detalle + colchón + «Mis activos» + posiciones
    sim = sorted(set(mejores) | AGd.COLCHON | set(mis) | set(pos))
    try:
        px, fuente = S.cierres(sim, hoy - dt.timedelta(days=10), hoy - dt.timedelta(days=1), c, yahoo=yahoo)
        cierres = {"fuente": fuente, "activos": {t: {"fecha": str(px[t].dropna().index[-1].date()),
                                                     "cierre": round(float(px[t].dropna().iloc[-1]), 4)}
                                                 for t in px.columns if len(px[t].dropna())}}
    except Exception as e:  # noqa: BLE001
        cierres = {"error": f"{type(e).__name__}: {str(e)[:200]}", "activos": {}}
    p = {k: v for k, v in base.items() if k != "sha256"}
    p.update(version=VERSION, mandato=AGd.VERSION_MANDATO, macro=macro, macro_disponibles=sorted(macro_disp),
             macro_lista=AGd.MACRO, filtro_macro=macro["filtro_macro"], fuentes_empresa_lista=AGd.FUENTES_EMPRESA,
             candidatas={"version": cand.get("version") if _ok(cand) else None,
                         "fecha_datos": cand.get("fecha_datos") if _ok(cand) else None,
                         "fuente": cand.get("fuente") if _ok(cand) else None,
                         "reglas": cand.get("reglas") if _ok(cand) else None,
                         "error": None if _ok(cand) else (cand or {}).get("error"),
                         "detalle_mejores": {t: {**compacta(emps[t]), "nombre": emps[t].get("nombre"),
                                                 "valores": emps[t].get("valores")} for t in mejores},
                         "todas": {t: compacta(f) for t, f in sorted(emps.items())}},
             mis_activos={"tickers": mis, "xbrl": xb, "form4": f4, "13f": f13_, "flujos": fl},
             empresa_disponible=emp, universo_compra=universo, sectores=sectores,
             colchon=sorted(AGd.COLCHON),
             limites_a1={"max_por_valor": AGd.MAX_POR_VALOR, "max_por_sector": AGd.MAX_POR_SECTOR,
                         "max_valores": AGd.MAX_VALORES, "min_valores_objetivo": AGd.MIN_VALORES,
                         "caida_max_tolerable": AGd.CAIDA_MAX, "techo_bolsa_hoy": fm.get("techo_bolsa")},
             sombra=sombra, cierres_simulacion=cierres)
    p["sha256"] = P.hash_paquete(p)
    return p
