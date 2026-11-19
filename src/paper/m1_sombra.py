"""Sombra teórica de M1 (docs/factors/M1_cartera_macro_spec.md v1.1 §4): la regla MECÁNICA del borrador 0.1
(git be92b9e, §2), calculada cada día SIN cuenta, valorada con cierres y 5 pb de coste, y registrada en
`research/paper/decisiones_m1_sombra.jsonl` (una línea por día; la escribe src/paper/m1.py junto a la de M1 y con las
mismas exigencias: M1_ACTIVO, árbol limpio, commit y push).

Regla (borrador 0.1, sin cambios salvo lo declarado abajo):
- Paso 1, cuánta bolsa: base 60 %, suelo 20 %, techo 75 %; crédito ámbar −10 pp, rojo −25 pp; P(recesión) E1 > 30 %
  −15 pp, > 50 % −30 pp (la mayor, no se suman); liquidez escasa −5 pp, holgada +5 pp; INT-11 P(pérdida 12 m) de la
  bolsa > 60 % −10 pp, < 35 % +5 pp; cuadrante G↑ +10 pp, G↓ −10 pp.
- Paso 2, qué bolsa: 50 % VTI; 30 % en los 4 sectores del cuadrante (mapa de S1, config/alpaca_etfs_s1.json) a partes
  iguales; 20 % en 8 acciones (las 2 mayores de cada sector favorecido, config/m1_acciones_v1.json) a partes iguales.
- Paso 3, el resto según la inflación: I↑ GLD 30 / DBC 25 / TIP 25 / SHY 20; I↓ TLT 40 / IEF 30 / GLD 20 / SHY 10; si
  crédito rojo o P(recesión) > 50 %: UUP 10 % de la cartera total, sacado de SHY y luego de IEF.
- Colchón 0,5 % en efectivo (todo se escala por 0,995). Opera si cambia el objetivo o si un peso deriva ≥ 5 pp.
Declarado (lo que el borrador no fijaba):
- Entradas: `signal` semanal más reciente (cuadrante = `regime.quadrant`, G = `regime.G_state`, I = `regime.I_state`,
  crédito = `credit.light`, liquidez = `liquidity.state`, INT-11 = `escenarios.paises.USA.abanicos.bolsa.p_neg`, que
  es la P(rentabilidad real < 0 a 12 m) de la bolsa de EE. UU.) y E1 = `p_A` de EE. UU. del último origen de
  `research/int/e1_vivo.jsonl` (modelo A, curva + actividad). Sin dato → esa entrada no ajusta (neutral) y se anota.
- Ejecución teórica al CIERRE del día de la decisión (el ciclo corre a las 20:45 con el mercado abierto); cierres
  ajustados (Alpaca `adjustment=all`, o el archivo de precios, o Yahoo); coste 5 pb × Σ|Δw| en cada reequilibrio;
  el efectivo no rinde. Un día sin cierre de algún activo en cartera: ese activo no se mueve ese día (se anota).
Funciones puras salvo `cierres` (lee datos) y `registrar` (escribe el registro).
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from src.factors import s1 as S1

REPO = Path(__file__).resolve().parents[2]
LOG = REPO / "research" / "paper" / "decisiones_m1_sombra.jsonl"
E1_VIVO = REPO / "research" / "int" / "e1_vivo.jsonl"
ACCIONES = REPO / "config" / "m1_acciones_v1.json"
MAPA_S1 = REPO / "config" / "alpaca_etfs_s1.json"
ARCHIVO_PRECIOS = Path("~/financial_archive/mercados/precios_diarios.parquet").expanduser()
VERSION = "m1-sombra-0.1"
SPEC = "docs/factors/M1_cartera_macro_spec.md v1.1 §4 (regla del borrador 0.1, git be92b9e §2)"
BASE, SUELO, TECHO = 0.60, 0.20, 0.75
NUCLEO, SECTORES_PCT, ACCIONES_PCT = 0.50, 0.30, 0.20
RESTO = {"up": {"GLD": 0.30, "DBC": 0.25, "TIP": 0.25, "SHY": 0.20},
         "down": {"TLT": 0.40, "IEF": 0.30, "GLD": 0.20, "SHY": 0.10}}
UUP = 0.10
COLCHON = 0.005
COSTE = 0.0005          # 5 pb por unidad de valor operado
DERIVA = 0.05
VALOR_INICIAL = 100_000.0


# --------------------------------------------------------------------------- entradas
def e1_usa(ruta: Path = E1_VIVO) -> dict:
    """Último origen de E1 para EE. UU. (p_A, modelo curva + actividad). Sin registro: no disponible."""
    if not ruta.exists():
        return {"disponible": False, "nota": "sin registros de E1 todavía (primer origen 2026-11-30)"}
    filas = [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]
    us = [f for f in filas if f.get("pais") in ("USA", "US", "EEUU")]
    if not us:
        return {"disponible": False, "nota": "E1 sin fila de EE. UU."}
    f = max(us, key=lambda x: str(x.get("origen")))
    return {"disponible": True, "origen": f.get("origen"), "p": f.get("p_A"), "p_L": f.get("p_L"),
            "fuente": "research/int/e1_vivo.jsonl p_A (EE. UU.)"}


def entradas(signal: dict | None, e1: dict | None) -> dict:
    s = signal or {}
    reg = s.get("regime") or {}
    usa = (((s.get("escenarios") or {}).get("paises") or {}).get("USA") or {})
    p_neg = ((usa.get("abanicos") or {}).get("bolsa") or {}).get("p_neg")
    e1 = e1 or {"disponible": False}
    return {"signal_asof": s.get("asof"), "cuadrante": reg.get("quadrant"), "G": reg.get("G_state"),
            "I": reg.get("I_state"), "credito": (s.get("credit") or {}).get("light"),
            "liquidez": (s.get("liquidity") or {}).get("state"),
            "int11_p_perdida_bolsa": p_neg, "int11_emision": (s.get("escenarios") or {}).get("emision"),
            "e1_p_recesion": e1.get("p") if e1.get("disponible") else None, "e1_origen": e1.get("origen")}


# --------------------------------------------------------------------------- regla (pura)
def bolsa(x: dict) -> tuple[float, list[str]]:
    """Paso 1: % de bolsa y los ajustes aplicados (texto)."""
    b, aj = BASE, []
    cr = x.get("credito")
    if cr == "ámbar" or cr == "ambar":
        b -= 0.10
        aj.append("crédito ámbar −10 pp")
    elif cr == "rojo":
        b -= 0.25
        aj.append("crédito rojo −25 pp")
    p = x.get("e1_p_recesion")
    if p is not None and p > 0.50:
        b -= 0.30
        aj.append(f"E1 P(recesión) {p:.0%} > 50 % −30 pp")
    elif p is not None and p > 0.30:
        b -= 0.15
        aj.append(f"E1 P(recesión) {p:.0%} > 30 % −15 pp")
    liq = x.get("liquidez")
    if liq == "escasa":
        b -= 0.05
        aj.append("liquidez escasa −5 pp")
    elif liq in ("holgada", "abundante"):      # el clasificador la llama «abundante»; el borrador, «holgada»
        b += 0.05
        aj.append("liquidez abundante +5 pp")
    q = x.get("int11_p_perdida_bolsa")
    if q is not None and q > 0.60:
        b -= 0.10
        aj.append(f"INT-11 P(pérdida) {q:.0%} > 60 % −10 pp")
    elif q is not None and q < 0.35:
        b += 0.05
        aj.append(f"INT-11 P(pérdida) {q:.0%} < 35 % +5 pp")
    g = x.get("G")
    if g == "up":
        b += 0.10
        aj.append("G↑ +10 pp")
    elif g == "down":
        b -= 0.10
        aj.append("G↓ −10 pp")
    b = round(b, 10)
    b2 = min(TECHO, max(SUELO, b))
    if round(b2, 10) != round(b, 10):
        aj.append(f"acotado a [{SUELO:.0%}, {TECHO:.0%}]")
    return round(b2, 6), aj


def objetivo(x: dict, acciones: dict | None = None, mapa: dict | None = None) -> dict:
    """Pesos objetivo (suman 1 con 'efectivo') y detalle. Sin cuadrante o sin I: no hay objetivo (None)."""
    acciones = acciones if acciones is not None else json.loads(ACCIONES.read_text(encoding="utf-8"))
    mapa = mapa if mapa is not None else json.loads(MAPA_S1.read_text(encoding="utf-8"))
    cuad, inf = x.get("cuadrante"), x.get("I")
    if cuad not in S1.SECTORES or inf not in RESTO:
        return {"pesos": None, "motivo": f"sin cuadrante válido ({cuad!r}) o sin estado de inflación ({inf!r})"}
    b, aj = bolsa(x)
    w: dict[str, float] = {}

    def suma(t, v):
        w[t] = w.get(t, 0.0) + v
    suma(mapa["tramos"]["mkt"]["etf"], b * NUCLEO)
    secs = S1.SECTORES[cuad]
    for s in secs:
        suma(mapa["tramos"][s]["etf"], b * SECTORES_PCT / len(secs))
    accs = [t for s in secs for t in acciones["acciones"][s]]
    for t in accs:
        suma(t, b * ACCIONES_PCT / len(accs))
    resto = 1 - b
    for t, v in RESTO[inf].items():
        suma(t, resto * v)
    p = x.get("e1_p_recesion")
    uup = x.get("credito") == "rojo" or (p is not None and p > 0.50)
    if uup:
        falta = UUP
        for t in ("SHY", "IEF"):
            q = min(w.get(t, 0.0), falta)
            if q > 0:
                w[t] -= q
                falta -= q
        suma("UUP", UUP - falta)
    w = {t: round(v * (1 - COLCHON), 6) for t, v in w.items() if v > 1e-12}
    w["efectivo"] = round(1 - sum(w.values()), 6)
    return {"pesos": w, "bolsa": b, "ajustes": aj, "sectores": list(secs), "acciones": accs, "uup": uup,
            "acciones_version": acciones.get("version"), "mapa_s1_version": mapa.get("version")}


# --------------------------------------------------------------------------- valoración teórica (pura)
def valorar(lineas: list[dict], precios: pd.DataFrame, *, coste: float = COSTE, deriva: float = DERIVA,
            valor0: float = VALOR_INICIAL) -> dict:
    """Valor teórico de la sombra con los cierres `precios` (índice fecha, columnas símbolo).

    Cada línea {fecha, objetivo: {pesos}} se ejecuta al cierre de su fecha (o del primer día con cierres después):
    se reequilibra si cambia el objetivo o si algún peso derivado se separa ≥ `deriva`; coste = `coste` × Σ|Δw|."""
    decisiones = sorted([ln for ln in lineas if (ln.get("objetivo") or {}).get("pesos")], key=lambda r: r["fecha"])
    out = {"serie": {}, "rebalanceos": 0, "rotacion": 0.0, "costes": 0.0, "sin_cierre": [], "hasta": None}
    if not decisiones or precios is None or precios.empty:
        return out
    px = precios.sort_index()
    px.index = pd.to_datetime(px.index).normalize()
    fechas = px.index[px.index >= pd.Timestamp(decisiones[0]["fecha"])]
    w: dict[str, float] = {}
    previo_obj = None
    v = valor0
    i = 0
    ant = None
    sin = set()
    for t in fechas:
        if ant is not None and w:
            nuevo = {}
            for k, x in w.items():
                if k == "efectivo":
                    nuevo[k] = x
                    continue
                a, b = px.at[ant, k] if k in px.columns else np.nan, px.at[t, k] if k in px.columns else np.nan
                r = (b / a - 1) if (a and b and math.isfinite(a) and math.isfinite(b)) else 0.0
                if not (a and b and math.isfinite(a) and math.isfinite(b)):
                    sin.add(k)
                nuevo[k] = x * (1 + r)
            tot = sum(nuevo.values())
            v *= tot
            w = {k: x / tot for k, x in nuevo.items()}
        obj = None
        while i < len(decisiones) and pd.Timestamp(decisiones[i]["fecha"]) <= t:
            obj = decisiones[i]["objetivo"]["pesos"]
            i += 1
        if obj is not None:
            claves = set(obj) | set(w)
            dif = {k: obj.get(k, 0.0) - w.get(k, 0.0) for k in claves}
            if not w or obj != previo_obj or max(abs(x) for x in dif.values()) >= deriva - 1e-12:
                giro = sum(abs(x) for k, x in dif.items() if k != "efectivo") if w else \
                    sum(x for k, x in obj.items() if k != "efectivo")
                c = coste * giro
                v *= (1 - c)
                out["rebalanceos"] += 1
                out["rotacion"] += giro / 2
                out["costes"] += c
                w = dict(obj)
            previo_obj = obj
        out["serie"][str(t.date())] = round(v, 2)
        ant = t
    out["hasta"] = str(fechas[-1].date()) if len(fechas) else None
    out["valor"] = round(v, 2)
    out["pesos_actuales"] = {k: round(x, 6) for k, x in w.items()}
    out["sin_cierre"] = sorted(sin)
    out["rotacion"] = round(out["rotacion"], 6)
    out["costes"] = round(out["costes"], 6)
    return out


# --------------------------------------------------------------------------- cierres (lectura)
def cierres_alpaca(c, simbolos: list[str], desde: dt.date, hasta: dt.date) -> pd.DataFrame:
    """Cierres ajustados (adjustment=all, feed IEX) con el cliente de src/broker/alpaca.py (solo lectura de datos)."""
    from src.broker import alpaca as A
    barras: dict[str, list] = {}
    token = None
    while True:
        p = {"symbols": ",".join(simbolos), "timeframe": "1Day", "start": desde.isoformat(), "end": hasta.isoformat(),
             "feed": A.FEED, "adjustment": "all", "limit": 10000}
        if token:
            p["page_token"] = token
        d = c._pide("GET", A.DATOS, "/v2/stocks/bars", p)
        for s, xs in (d.get("bars") or {}).items():
            barras.setdefault(s, []).extend(xs)
        token = d.get("next_page_token")
        if not token:
            break
    return pd.DataFrame({s: pd.Series({pd.Timestamp(str(x["t"])[:10]): float(x["c"]) for x in barras.get(s) or []},
                                      dtype=float) for s in simbolos}).sort_index()


def cierres_yahoo(simbolos: list[str], desde: dt.date) -> pd.DataFrame:
    from src.ingest import yahoo_precios as Y
    cols = {}
    for s in simbolos:
        try:
            x, _ = Y.descargar(s.replace(".", "-"))
            cols[s] = x[x.index >= pd.Timestamp(desde)]
        except Exception:  # noqa: BLE001 — un símbolo sin datos no tumba la sombra
            continue
    return pd.DataFrame(cols).sort_index()


def cierres(simbolos: list[str], desde: dt.date, hasta: dt.date, c=None, *, yahoo: bool = True) -> tuple[pd.DataFrame, str]:
    """Cierres ajustados: Alpaca (si hay cliente) → archivo de precios → Yahoo para los que falten."""
    simbolos = sorted(set(simbolos))
    df, fuentes = pd.DataFrame(), []
    if c is not None:
        try:
            df = cierres_alpaca(c, simbolos, desde, hasta)
            fuentes.append("Alpaca (IEX, ajustado)")
        except Exception:  # noqa: BLE001
            df = pd.DataFrame()
    faltan = [s for s in simbolos if s not in df.columns or df[s].dropna().empty]
    if faltan and ARCHIVO_PRECIOS.exists():
        try:
            a = pd.read_parquet(ARCHIVO_PRECIOS)
            a.index = pd.to_datetime(a.index).normalize()
            hay = [s for s in faltan if s in a.columns]
            if hay:
                df = pd.concat([df, a.loc[a.index >= pd.Timestamp(desde), hay]], axis=1)
                fuentes.append(f"archivo ({len(hay)})")
        except Exception:  # noqa: BLE001
            pass
    faltan = [s for s in simbolos if s not in df.columns or df[s].dropna().empty]
    if faltan and yahoo:
        y = cierres_yahoo(faltan, desde)
        if not y.empty:
            df = pd.concat([df, y], axis=1)
            fuentes.append(f"Yahoo ({len(y.columns)})")
    df = df.loc[:, ~df.columns.duplicated()].sort_index() if not df.empty else df
    if not df.empty:
        df = df[df.index <= pd.Timestamp(hasta)]
    return df, " + ".join(fuentes) or "sin cierres"


# --------------------------------------------------------------------------- registro
def leer_registro(ruta: Path | None = None) -> list[dict]:
    ruta = ruta or LOG
    if not ruta.exists():
        return []
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]


def linea_del_dia(fecha: str, signal: dict | None, e1: dict | None, previas: list[dict],
                  precios: pd.DataFrame | None, fuente: str) -> dict:
    x = entradas(signal, e1)
    obj = objetivo(x)
    ln = {"fecha": fecha, "spec": SPEC, "version": VERSION, "entradas": x, "objetivo": obj}
    val = valorar(previas + [ln], precios if precios is not None else pd.DataFrame())
    ln["valoracion"] = {"hasta": val.get("hasta"), "valor": val.get("valor"), "rebalanceos": val["rebalanceos"],
                        "rotacion": val["rotacion"], "costes": val["costes"], "sin_cierre": val["sin_cierre"],
                        "fuente_cierres": fuente, "valor_inicial": VALOR_INICIAL}
    return ln


def registrar(linea: dict, ruta: Path | None = None) -> None:
    ruta = ruta or LOG
    if linea["fecha"] in {r.get("fecha") for r in leer_registro(ruta)}:
        raise ValueError(f"ya hay una línea de la sombra de M1 para {linea['fecha']} (una por día, inmutable)")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(linea, ensure_ascii=False, default=str) + "\n")


def universo(acciones: dict | None = None, mapa: dict | None = None) -> list[str]:
    """Todos los símbolos que la sombra puede tener (para pedir cierres)."""
    acciones = acciones if acciones is not None else json.loads(ACCIONES.read_text(encoding="utf-8"))
    mapa = mapa if mapa is not None else json.loads(MAPA_S1.read_text(encoding="utf-8"))
    xs = {v["etf"] for v in mapa["tramos"].values()} | {t for v in acciones["acciones"].values() for t in v}
    xs |= {t for r in RESTO.values() for t in r} | {"UUP"}
    return sorted(xs)
