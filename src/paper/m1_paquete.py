"""Paquete del día de M1 «Claude gestor macro» (docs/factors/M1_cartera_macro_spec.md v1.1 §3). SIN IA.

= el paquete de C1 (src/paper/c1_paquete.py: cuenta del perfil M1 o simulada, precios, régimen, alertas,
diagnósticos, panel, diario de M1) MÁS:
- `modelos`: la salida completa de cada modelo citable (src/broker/m1_guardia.MODELOS) con su fecha de publicación:
  cuadrante y G/I, crédito, liquidez, ciclo de deuda (corto y largo) del último signal semanal; E1 (último origen de
  research/int/e1_vivo.jsonl, todos los países); INT-11 (signal.escenarios: abanicos por país y activo, acierto medido);
  diagnósticos y alertas (los del paquete de C1); fundamentales XBRL resumidos (~/financial_archive/sec_fundamentales);
  y, como contexto no citable, K1v si hay emisión (research/int/k1_vivo.jsonl);
- `modelos_disponibles`: los identificadores con salida hoy (la guardia rechaza las citas a los demás);
- `sombra`: la línea del día de la sombra teórica (src/paper/m1_sombra.py: entradas, pesos objetivo, valoración);
- `cierres_simulacion`: últimos cierres del universo de la sombra (para validar en los ensayos sin cuenta).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path

from src.broker import alpaca as A
from src.broker import m1_guardia as MG
from src.paper import c1_paquete as P
from src.paper import m1_sombra as S

REPO = A.REPO
LOG = REPO / "research" / "paper" / "decisiones_m1.jsonl"
K1_VIVO = REPO / "research" / "int" / "k1_vivo.jsonl"
VERSION = "m1-paquete-1"
CONCEPTOS_XBRL = {"ingresos": ("us-gaap:Revenues", "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"),
                  "beneficio_neto": ("us-gaap:NetIncomeLoss",),
                  "resultado_operativo": ("us-gaap:OperatingIncomeLoss",),
                  "bpa_diluido": ("us-gaap:EarningsPerShareDiluted",)}
RE_TRIM = re.compile(r"^CY\d{4}Q\d$")


def leer_registro(ruta: Path | None = None) -> list[dict]:
    return P.leer_registro(ruta or LOG)


def _jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


# --------------------------------------------------------------------------- salidas de los modelos
def e1_todos(ruta: Path = S.E1_VIVO) -> dict:
    filas = _jsonl(ruta)
    if not filas:
        return {"error": "sin registros de E1 todavía (primer origen 2026-11-30, ≈ 3-dic)"}
    ult = max(str(f.get("origen")) for f in filas)
    return {"fecha_publicacion": ult, "fuente": "research/int/e1_vivo.jsonl",
            "nota": "p_A = modelo A (curva + actividad), p_L = listón (curva); 12 m y 6 m (p_A6, p_L6). Registro "
                    "prospectivo SIN veredicto todavía: no validado fuera de muestra.",
            "paises": {f["pais"]: {k: f.get(k) for k in ("p_A", "p_L", "p_A6", "p_L6")} for f in filas
                       if str(f.get("origen")) == ult}}


def k1v(ruta: Path = K1_VIVO) -> dict:
    filas = _jsonl(ruta)
    if not filas:
        return {"error": "sin emisión de K1v (anual; primera con t = 2026)"}
    return {"filas": filas[-20:], "fuente": "research/int/k1_vivo.jsonl", "citable": False}


def int11(s: dict) -> dict:
    e = (s or {}).get("escenarios") or {}
    if not e.get("paises"):
        return {"error": "sin escenarios de INT-11 en el signal"}
    return {"fecha_publicacion": e.get("emision"), "motor": e.get("motor"), "aviso": e.get("aviso"),
            "acierto_medido_fase_D_por_activo": (e.get("acierto_medido_fase_D") or {}).get("activo"),
            "paises": {p: {k: v.get(k) for k in ("regimen_dominante", "pesos_regimen", "p_caida_bolsa_20",
                                                 "p_inflacion_5", "abanicos", "cerca_umbral")}
                       for p, v in e["paises"].items()}}


def xbrl(ruta: Path | None = None, simbolos: list[str] | None = None) -> dict:
    """Últimos 4 trimestres (marco CYAAAAQn) de ingresos, beneficio neto, resultado operativo y BPA por empresa."""
    raiz = Path(os.path.expanduser(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")))
    ruta = ruta or raiz / "sec_fundamentales" / "hechos.json"
    if not ruta.exists():
        return {"error": "sin fundamentales XBRL (sec_fundamentales/hechos.json)"}
    d = json.loads(ruta.read_text(encoding="utf-8"))
    out = {}
    for t, e in (d.get("empresas") or {}).items():
        if simbolos and t not in simbolos:
            continue
        fila = {"nombre": e.get("nombre")}
        for nombre, conceptos in CONCEPTOS_XBRL.items():
            for c in conceptos:
                hs = [h for h in ((e.get("conceptos") or {}).get(c) or {}).get("hechos") or []
                      if RE_TRIM.match(str(h.get("frame") or ""))]
                if hs:
                    hs = sorted(hs, key=lambda h: h["end"])[-4:]
                    fila[nombre] = [{"fin": h["end"], "valor": h["val"], "presentado": h.get("filed"),
                                     "form": h.get("form")} for h in hs]
                    break
        out[t] = fila
    return {"fecha_publicacion": d.get("actualizado_utc"), "fuente": "SEC data.sec.gov (XBRL), «Mis activos»",
            "empresas": out}


def modelos(s: dict | None, nombre_signal: str | None, base: dict) -> dict:
    s = s or {}
    asof = s.get("asof")
    reg = s.get("regime") or {}
    out = {
        "cuadrante": ({"fecha_publicacion": asof, "signal": nombre_signal, **reg,
                       "cambios": s.get("changes")} if reg else {"error": "sin régimen en el signal"}),
        "credito": ({"fecha_publicacion": asof, **(s.get("credit") or {})} if s.get("credit")
                    else {"error": "sin crédito en el signal"}),
        "liquidez": ({"fecha_publicacion": asof, **(s.get("liquidity") or {})} if s.get("liquidity")
                     else {"error": "sin liquidez en el signal"}),
        "ciclo_deuda": ({"fecha_publicacion": asof, "corto": s.get("debt_cycle"), "largo": s.get("long_cycle")}
                        if s.get("debt_cycle") else {"error": "sin ciclo de deuda en el signal"}),
        "e1": e1_todos(),
        "int11": int11(s),
        "diagnosticos": base.get("diagnosticos") if base.get("diagnosticos") else {"error": "sin diagnósticos esta semana"},
        "alertas": base.get("alertas") if base.get("alertas") else {"error": "sin alertas recientes"},
        "xbrl": xbrl(),
    }
    out = {k: (P._error(v) if isinstance(v, Exception) else v) for k, v in out.items()}
    out["_contexto_no_citable"] = {"k1v": k1v(), "termometro": (s.get("termometro") or {}).get("aviso"),
                                   "nowcast": ((s.get("nowcast") or {}).get("agregado"))}
    return out


def disponibles(m: dict) -> list[str]:
    def tiene(v) -> bool:
        if isinstance(v, dict):
            return bool(v) and "error" not in v
        if isinstance(v, list):
            return bool(v) and not all(isinstance(x, dict) and "error" in x for x in v)
        return v is not None
    return [k for k in MG.MODELOS if tiene(m.get(k))]


def _seguro(fn, *a):
    try:
        return fn(*a)
    except Exception as e:  # noqa: BLE001
        return P._error(e)


# --------------------------------------------------------------------------- sombra
def sombra_del_dia(c: A.Cliente | None, hoy: dt.date, s: dict | None, previas: list[dict], *,
                   yahoo: bool = True) -> tuple[dict, dict]:
    """(línea de la sombra del día, cierres_simulacion). Pide cierres desde la primera decisión registrada."""
    desde = min([dt.date.fromisoformat(r["fecha"]) for r in previas] + [hoy - dt.timedelta(days=10)])
    # solo sesiones COMPLETAS (antes de hoy): el ciclo corre con el mercado abierto y la decisión de hoy se ejecuta,
    # en teoría, al cierre de hoy, que se valora mañana
    px, fuente = S.cierres(S.universo(), desde, hoy - dt.timedelta(days=1), c, yahoo=yahoo)
    linea = S.linea_del_dia(hoy.isoformat(), s, S.e1_usa(), previas, px, fuente)
    ult = {}
    if not px.empty:
        for t in px.columns:
            x = px[t].dropna()
            if len(x):
                ult[t] = {"fecha": str(x.index[-1].date()), "cierre": round(float(x.iloc[-1]), 4)}
    return linea, {"fuente": fuente, "activos": ult}


def recoger(c: A.Cliente | None, hoy: dt.date | None = None, *, registro: list[dict] | None = None,
            sombra_previas: list[dict] | None = None, yahoo: bool = True) -> dict:
    hoy = hoy or dt.date.today()
    registro = leer_registro() if registro is None else registro
    base = P.recoger(c, hoy, registro=registro)
    if base["cuenta"].get("simulada"):
        base["cuenta"]["aviso"] = "ENSAYO sin claves de M1: cuenta ficticia, no es la cuenta paper"
    try:
        s, nombre = P.ultimo_signal()
    except Exception:  # noqa: BLE001
        s, nombre = None, None
    m = _seguro(modelos, s, nombre, base)
    previas = S.leer_registro() if sombra_previas is None else sombra_previas
    try:
        sombra, cierres = sombra_del_dia(c, hoy, s, previas, yahoo=yahoo)
    except Exception as e:  # noqa: BLE001
        sombra, cierres = {"error": f"{type(e).__name__}: {str(e)[:200]}"}, {"activos": {}}
    p = {k: v for k, v in base.items() if k != "sha256"}
    p.update(version=VERSION, mandato=MG.VERSION_MANDATO, modelos=m,
             modelos_disponibles=disponibles(m) if isinstance(m, dict) and "error" not in m else [],
             modelos_lista=MG.MODELOS, sombra=sombra, cierres_simulacion=cierres)
    p["sha256"] = P.hash_paquete(p)
    return p
