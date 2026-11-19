"""Espejo de ejecución en Alpaca PAPER de las carteras del paper trading (B0, B1, B1′, S1 y D1). SOLO cuenta simulada.

Qué hace: lee la decisión registrada (research/paper/decisiones.jsonl para B0/B1, decisiones_b1prima.jsonl para B1′;
SOLO LECTURA, nunca los modifica ni los sustituye), traduce los pesos por tramo (rv/rf/oro) a ETFs de EE. UU. con
`config/alpaca_etfs.json` y calcula las órdenes que llevan la cuenta paper a esos pesos. Es una comprobación de ejecución
realista (deslizamiento, fracciones, redondeos, costes) frente al paper teórico, que valora con cierres de mes.

S1 (docs/factors/S1_rotacion_sectorial_spec.md §6): pesos por ETF (núcleo `mkt` + industrias French) desde
research/paper/decisiones_s1.jsonl con su propio mapeo versionado `config/alpaca_etfs_s1.json`. Solo opera cuando la
decisión dice `opera` (cambió el cuadrante) o la cuenta aún no tiene ninguna posición de S1 (arranque); si no, deja que
los pesos deriven, como la regla. B0/B1/B1′ no cambian (sus decisiones no llevan `opera`: siempre se rebalancean).

D1 (docs/factors/D1_tendencia_diaria_spec.md §6): decisión DIARIA en research/paper/decisiones_d1.jsonl, pesos por ETF
(SPY/VEA/TLT/GLD/DBC) con `config/alpaca_etfs_d1.json`. Los pesos suman ≤ 100 % (el resto, efectivo en la cuenta:
`permite_efectivo`). Misma lógica de `opera` que S1 y, además, la banda de no operar del mapeo (`banda_no_operar`,
3 pp): no se envía la orden de un ETF cuyo peso real en la cuenta ya está a menos de la banda del objetivo.

Reglas:
- `--dry-run` por defecto: calcula, imprime y apunta el plan; no envía nada. `--ejecutar` envía órdenes a la cuenta
  PAPER. Con `--auto` (lo que llamaría scripts/paper_mensual.sh) solo se ejecuta si además FIN_ALPACA_EJECUTAR=1.
- Una cuenta paper = una cartera: el perfil declara su cartera (`ALPACA_CARTERA[_PERFIL]` o el nombre del perfil
  B0/B1/B1P). Sin declaración no se ejecuta; si la cuenta ya se usó para otra cartera, tampoco.
- Mercado abierto y a ≥ N minutos del cierre: órdenes de mercado (day). Si no: limit con margen (± 0,5 %) que espera a
  la apertura. Ventas antes que compras; las compras se recortan al efectivo disponible (con el margen).
- Fracciones si el activo es `fractionable` (a 4 decimales, hacia abajo); si no, acciones enteras. Órdenes de menos de
  `min_orden_usd` no se envían. Colchón de efectivo del 0,5 % (B0/B1/B1′ no tienen tramo de liquidez).
- No envía si hay órdenes abiertas en la cuenta (evita duplicar). `client_order_id` determinista: Alpaca rechaza un
  duplicado.
- Registro propio, fuera de git: ~/financial_archive/alpaca/espejo.jsonl (FIN_ALPACA_DIR), con plan, órdenes,
  ejecuciones, precios de referencia y deslizamiento frente al precio en el momento de la orden y frente al cierre de
  la sesión del cierre de mes (el precio al que «opera» el paper teórico). Nunca claves.

Uso:  python -m src.broker.espejo --cartera B1 [--dry-run | --ejecutar] [--cierre AAAA-MM-DD] [--perfil P]
      python -m src.broker.espejo --seguimiento [--perfil P]      (actualiza ejecuciones pendientes)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from src.broker import alpaca as A

REPO = A.REPO
LOG_B1 = REPO / "research" / "paper" / "decisiones.jsonl"
LOG_B1P = REPO / "research" / "paper" / "decisiones_b1prima.jsonl"
LOG_S1 = REPO / "research" / "paper" / "decisiones_s1.jsonl"
LOG_D1 = REPO / "research" / "paper" / "decisiones_d1.jsonl"
CARTERAS = {"B0": (LOG_B1, "b0"), "B1": (LOG_B1, "b1"), "B1P": (LOG_B1P, "b1prima"), "S1": (LOG_S1, "s1"),
            "D1": (LOG_D1, "d1")}
MAPEOS = {"S1": REPO / "config" / "alpaca_etfs_s1.json",
          "D1": REPO / "config" / "alpaca_etfs_d1.json"}       # el resto: config/alpaca_etfs.json
COSTE_TEORICO_PB = {"rv": 10.0, "rf": 10.0, "oro": 20.0,   # docs/factors/paper_trading.md §4 (por lado)
                    # D1 (spec §2.5): 5 pb en ETFs de bolsa, bonos y oro; 10 pb en materias primas
                    "us": 5.0, "xus": 5.0, "bonos": 5.0, "mp": 10.0}
ESTADOS_FINALES = {"filled", "canceled", "expired", "rejected", "done_for_day", "replaced"}


def dir_registro() -> Path:
    return Path(os.path.expanduser(os.environ.get("FIN_ALPACA_DIR", "~/financial_archive/alpaca")))


def ruta_registro() -> Path:
    return dir_registro() / "espejo.jsonl"


# --------------------------------------------------------------------------- decisiones (solo lectura)
def _jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def mapeo_de(cartera: str) -> dict:
    """Mapeo tramo → ETF de la cartera (S1 tiene el suyo; B0/B1/B1′ comparten config/alpaca_etfs.json)."""
    ruta = MAPEOS.get(A.normaliza_perfil(cartera))
    return A.cargar_mapeo(ruta) if ruta else A.cargar_mapeo()


def decision(cartera: str, cierre: str | None = None, *, logs: dict | None = None) -> dict | None:
    """{'cierre', 'pesos': {tramo: peso}, 'registrado'} de la última decisión (o la del cierre pedido); con 'opera' si
    el registro lo lleva (S1)."""
    cartera = A.normaliza_perfil(cartera)
    if cartera not in (logs or CARTERAS):
        raise ValueError(f"cartera desconocida {cartera!r}: B0, B1, B1P (B1′), S1 o D1")
    ruta, clave = (logs or CARTERAS)[cartera]
    filas = [d for d in _jsonl(Path(ruta)) if clave in d]
    if cierre:
        filas = [d for d in filas if d["cierre"] == cierre]
    if not filas:
        return None
    d = filas[-1]
    out = {"cierre": d["cierre"], "pesos": {k: float(v) for k, v in d[clave].items()},
           "registrado": d.get("registrado")}
    if "opera" in d:
        out["opera"] = bool(d["opera"])
    return out


# --------------------------------------------------------------------------- cálculo de órdenes (puro)
@dataclass
class Orden:
    simbolo: str
    tramo: str | None
    lado: str                 # buy / sell
    qty: float
    tipo_orden: str           # market / limit
    limit_price: float | None
    precio_ref: float
    valor_estimado: float     # qty × precio_ref
    peso_objetivo: float
    peso_actual: float
    client_order_id: str = ""

    def cuerpo(self) -> dict:
        d = {"symbol": self.simbolo, "qty": _fmt_qty(self.qty), "side": self.lado, "type": self.tipo_orden,
             "time_in_force": "day", "client_order_id": self.client_order_id}
        if self.tipo_orden == "limit":
            d["limit_price"] = f"{self.limit_price:.4f}".rstrip("0").rstrip(".")
        return d


def _fmt_qty(q: float) -> str:
    return (f"{q:.9f}".rstrip("0").rstrip(".")) or "0"


def redondea_qty(q: float, fraccionable: bool, decimales: int) -> float:
    """Hacia abajo (nunca más de lo calculado): a `decimales` si es fraccionable, si no a acciones enteras."""
    if q <= 0:
        return 0.0
    if not fraccionable:
        return float(math.floor(q + 1e-9))
    f = 10 ** decimales
    return math.floor(q * f + 1e-9) / f


def precio_limit(ref: float, lado: str, margen: float) -> float:
    """Comprar hasta ref·(1+margen), vender desde ref·(1−margen); céntimos (≥ 1 $) o 4 decimales (< 1 $)."""
    p = ref * (1 + margen) if lado == "buy" else ref * (1 - margen)
    dec = 2 if p >= 1 else 4
    f = 10 ** dec
    return (math.floor(p * f + 1e-6) if lado == "buy" else math.ceil(p * f - 1e-6)) / f   # sin pasar del margen


def tipo_orden(mercado: dict, cfg: dict) -> str:
    """market solo con el mercado abierto y a ≥ N minutos del cierre; si no, limit."""
    m = mercado.get("minutos_al_cierre")
    if mercado.get("abierto") and m is not None and m >= cfg.get("minutos_antes_cierre_sin_mercado", 15):
        return "market"
    return "limit"


def pesos_etf(pesos: dict[str, float], mapeo: dict) -> dict[str, tuple[str, float]]:
    """Con `permite_efectivo` (D1) los pesos pueden sumar menos de 1 (el resto queda en efectivo); nunca más de 1."""
    suma = sum(pesos.values())
    mal = suma > 1 + 1e-6 if mapeo.get("permite_efectivo") else abs(suma - 1) > 1e-6
    if any(w < 0 for w in pesos.values()) or mal:
        raise ValueError(f"pesos no válidos (negativos o no suman 1): {pesos}")
    out: dict[str, tuple[str, float]] = {}
    for tramo, w in pesos.items():
        if tramo not in mapeo["tramos"]:
            raise ValueError(f"tramo {tramo!r} sin ETF en config/alpaca_etfs.json")
        s = mapeo["tramos"][tramo]["etf"]
        out[s] = (tramo, out.get(s, (tramo, 0.0))[1] + w)
    return out


def calcular_ordenes(pesos: dict[str, float], mapeo: dict, *, equity: float, efectivo: float,
                     posiciones: dict[str, float], precios: dict[str, float], fraccionable: dict[str, bool],
                     mercado: dict) -> tuple[list[Orden], dict]:
    """Órdenes para llevar la cuenta a `pesos` (por tramo). Falla cerrado si falta un precio.
    Devuelve (órdenes: ventas primero, resumen)."""
    cfg = {**mapeo.get("ordenes", {})}
    colchon = float(mapeo.get("liquidez", {}).get("colchon", 0.0))
    dec, minimo, margen = int(cfg.get("decimales_fraccion", 4)), float(cfg.get("min_orden_usd", 10)), \
        float(cfg.get("margen_limit", 0.005))
    banda = float(cfg.get("banda_no_operar", 0.0))           # D1: 3 pp; el resto de carteras, 0 (sin efecto)
    objetivo = pesos_etf(pesos, mapeo)
    simbolos = sorted(set(objetivo) | {s for s, q in posiciones.items() if abs(q) > 0})
    faltan = [s for s in simbolos if not precios.get(s) or precios[s] <= 0]
    if faltan:
        raise ValueError(f"sin precio para {faltan}: no se calcula nada (falla cerrado)")
    if equity <= 0:
        raise ValueError(f"valor de la cuenta no positivo ({equity})")
    tipo = tipo_orden(mercado, cfg)
    invertible = equity * (1 - colchon)
    ventas, compras, omitidas = [], [], []
    for s in simbolos:
        tramo, w = objetivo.get(s, (None, 0.0))
        p, q = precios[s], float(posiciones.get(s, 0.0))
        actual = q * p
        delta = w * invertible - actual
        frac = bool(fraccionable.get(s, False))
        if banda > 0 and abs(delta) < banda * equity - 1e-9:
            if abs(delta) >= minimo:
                omitidas.append(Orden(s, tramo, "sell" if delta < 0 else "buy", 0.0, tipo, None, p, 0.0, w,
                                      actual / equity))
            continue
        if delta < 0:
            qv = q if w == 0 else min(q, redondea_qty(-delta / p, frac, dec))
            o = Orden(s, tramo, "sell", qv, tipo, precio_limit(p, "sell", margen) if tipo == "limit" else None,
                      p, round(qv * p, 2), w, actual / equity)
            (ventas if qv > 0 and (qv * p >= minimo or w == 0) else omitidas).append(o)
        elif delta > 0:
            qc = redondea_qty(delta / p, frac, dec)
            o = Orden(s, tramo, "buy", qc, tipo, precio_limit(p, "buy", margen) if tipo == "limit" else None,
                      p, round(qc * p, 2), w, actual / equity)
            (compras if qc > 0 and qc * p >= minimo else omitidas).append(o)
    # presupuesto de compras: efectivo + ventas (limit: a su precio límite; mercado: al de referencia). Coste: limit a
    # su precio límite, mercado al de referencia. El colchón (≥ margen) absorbe el deslizamiento de las de mercado.
    presupuesto = efectivo + sum(o.qty * (o.limit_price or o.precio_ref) for o in ventas)
    peor = lambda o: o.qty * (o.limit_price or o.precio_ref)   # noqa: E731
    coste = sum(peor(o) for o in compras)
    escala = 1.0
    if coste > presupuesto and coste > 0:
        escala = max(presupuesto, 0.0) / coste
        for o in compras:
            o.qty = redondea_qty(o.qty * escala, bool(fraccionable.get(o.simbolo)), dec)
            o.valor_estimado = round(o.qty * o.precio_ref, 2)
        omitidas += [o for o in compras if o.qty * o.precio_ref < minimo]
        compras = [o for o in compras if o.qty * o.precio_ref >= minimo]
    ordenes = ventas + compras
    coste_teo = sum(o.valor_estimado * COSTE_TEORICO_PB.get(o.tramo or "rv", 10.0) / 1e4 for o in ordenes)
    resumen = {"tipo_orden": tipo, "equity": equity, "efectivo": efectivo, "invertible": round(invertible, 2),
               "escala_compras": round(escala, 6), "rotacion": round(sum(o.valor_estimado for o in ordenes)
                                                                      / (2 * equity), 6),
               "coste_teorico_usd": round(coste_teo, 2),
               "omitidas": [{"simbolo": o.simbolo, "lado": o.lado, "qty": o.qty, "valor": o.valor_estimado}
                            for o in omitidas],
               "pesos_objetivo_etf": {s: round(w, 6) for s, (_, w) in objetivo.items()}}
    return ordenes, resumen


def sin_operar(pesos: dict[str, float], mapeo: dict, equity: float, efectivo: float) -> dict:
    """Resumen de un periodo sin operaciones (S1 sin cambio de cuadrante; D1 sin activos que crucen la banda): los
    pesos derivan, como en la regla."""
    objetivo = pesos_etf(pesos, mapeo)
    colchon = float(mapeo.get("liquidez", {}).get("colchon", 0.0))
    return {"tipo_orden": "ninguna", "equity": equity, "efectivo": efectivo, "invertible": round(equity * (1 - colchon), 2),
            "escala_compras": 1.0, "rotacion": 0.0, "coste_teorico_usd": 0.0, "omitidas": [],
            "pesos_objetivo_etf": {s: round(w, 6) for s, (_, w) in objetivo.items()},
            "sin_operar": "la decisión no opera (S1: sin cambio de cuadrante; D1: nada cruza la banda): se mantienen "
                          "las posiciones (los pesos derivan)"}


def deslizamiento_pb(lado: str, precio: float | None, ref: float | None) -> float | None:
    """Positivo = peor que la referencia (comprar más caro o vender más barato)."""
    if not precio or not ref:
        return None
    signo = 1 if lado == "buy" else -1
    return round(signo * (precio / ref - 1) * 1e4, 2)


# --------------------------------------------------------------------------- registro
def apunta(fila: dict, ruta: Path | None = None) -> None:
    ruta = ruta or ruta_registro()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(fila, ensure_ascii=False, default=str) + "\n")


def leer_registro(ruta: Path | None = None) -> list[dict]:
    return _jsonl(ruta or ruta_registro())


def huella_cuenta(cuenta: dict) -> str:
    return hashlib.sha256(str(cuenta.get("id") or cuenta.get("account_number") or "").encode()).hexdigest()[:12]


def cartera_de(cred: A.Credenciales) -> str | None:
    return cred.cartera or (cred.perfil if cred.perfil in CARTERAS else None)


# --------------------------------------------------------------------------- flujo con la API
def _cierre_sesion(c: A.Cliente, simbolos: list[str], cierre: str) -> dict[str, float | None]:
    """Cierre (feed IEX) de la última sesión ≤ fecha del cierre de mes: el precio del paper teórico."""
    f = dt.date.fromisoformat(cierre)
    try:
        barras = c.barras_diarias(simbolos, f - dt.timedelta(days=10), f)
    except A.AlpacaError:
        return {s: None for s in simbolos}
    out = {}
    for s in simbolos:
        b = [x for x in barras.get(s) or [] if str(x.get("t", ""))[:10] <= cierre]
        out[s] = float(b[-1]["c"]) if b else None
    return out


def plan(c: A.Cliente, cartera: str, cierre: str | None = None, *, mapeo: dict | None = None,
         logs: dict | None = None) -> dict:
    mapeo = mapeo or mapeo_de(cartera)
    d = decision(cartera, cierre, logs=logs)
    if d is None:
        raise LookupError(f"sin decisión registrada para {cartera}" + (f" en {cierre}" if cierre else ""))
    mercado = A.estado_mercado(c.reloj())
    cu = c.cuenta()
    pos = {p["symbol"]: float(p["qty"]) for p in c.posiciones()}
    simbolos = sorted(set(A.simbolos_mapeo(mapeo).values()) | set(pos))
    inst = c.instantaneas(simbolos)
    precios = {s: A.precio_de(inst.get(s) or {}) for s in simbolos}
    frac = {}
    for s in simbolos:
        a = c.activo(s)
        if not a.get("tradable", False):
            raise ValueError(f"{s} no es negociable en Alpaca")
        frac[s] = bool(a.get("fractionable"))
    propias = set(A.simbolos_mapeo(mapeo).values())
    if d.get("opera", True) or not any(abs(q) > 0 for s, q in pos.items() if s in propias):
        ordenes, res = calcular_ordenes(d["pesos"], mapeo, equity=float(cu["equity"]), efectivo=float(cu["cash"]),
                                        posiciones=pos, precios=precios, fraccionable=frac, mercado=mercado)
    else:
        ordenes, res = [], sin_operar(d["pesos"], mapeo, float(cu["equity"]), float(cu["cash"]))
    cierres = _cierre_sesion(c, simbolos, d["cierre"])
    return {"cartera": cartera, "decision": d, "mercado": mercado, "cuenta": A.enmascara_cuenta(cu.get("account_number")),
            "cuenta_huella": huella_cuenta(cu), "mapeo_version": mapeo.get("version"), "precios": precios,
            "fraccionable": frac, "cierre_sesion": cierres, "posiciones": pos, "resumen": res, "ordenes": ordenes}


def _base(p: dict, cred: A.Credenciales) -> dict:
    return {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "cartera": p["cartera"],
            "cierre": p["decision"]["cierre"], "perfil": cred.perfil or "defecto", "cuenta": p["cuenta"],
            "cuenta_huella": p["cuenta_huella"], "mapeo_version": p["mapeo_version"]}


def puede_ejecutar(cred: A.Credenciales, cartera: str, huella: str, registro: list[dict]) -> str | None:
    """None si se puede ejecutar; si no, el motivo."""
    propia = cartera_de(cred)
    if propia is None:
        return (f"el perfil '{cred.perfil or 'defecto'}' no declara su cartera: añade "
                f"ALPACA_CARTERA{'_' + cred.perfil if cred.perfil else ''}={cartera} en alpaca.env")
    if propia != cartera:
        return f"el perfil '{cred.perfil or 'defecto'}' es de la cartera {propia}, no de {cartera} (una cuenta = una cartera)"
    otras = {r["cartera"] for r in registro if r.get("cuenta_huella") == huella and r.get("tipo") == "orden"} - {cartera}
    if otras:
        return f"esta cuenta paper ya se usó para {sorted(otras)}: una cuenta = una cartera"
    return None


def ejecutar(c: A.Cliente, p: dict, *, espera_s: float | None = None, dormir=time.sleep) -> list[dict]:
    """Envía las órdenes del plan (ventas, pausa, compras) y espera ejecuciones hasta `espera_s`."""
    if c.ordenes_abiertas():
        raise A.AlpacaError("hay órdenes abiertas en la cuenta paper: no se envía nada (espera o cancélalas)")
    base = _base(p, c.cred)
    previas = sum(1 for r in leer_registro() if r.get("tipo") == "orden" and r.get("cartera") == p["cartera"]
                  and r.get("cierre") == p["decision"]["cierre"] and r.get("cuenta_huella") == p["cuenta_huella"])
    intento = previas + 1
    enviadas = []
    espera_s = float(espera_s if espera_s is not None else 60)
    for lado in ("sell", "buy"):
        for o in [o for o in p["ordenes"] if o.lado == lado]:
            o.client_order_id = f"espejo-{p['cartera']}-{p['decision']['cierre']}-{o.simbolo}-{lado}-{intento}"
            try:
                r = c.enviar_orden(o.cuerpo())
                fila = {**base, "tipo": "orden", **asdict(o), "orden_id": r.get("id"), "estado": r.get("status"),
                        "cierre_sesion": p["cierre_sesion"].get(o.simbolo)}
            except A.AlpacaError as e:
                fila = {**base, "tipo": "orden_rechazada", **asdict(o), "error": c.cred.enmascarar(str(e))}
            apunta(fila)
            enviadas.append(fila)
        if lado == "sell" and any(f["tipo"] == "orden" for f in enviadas):
            _espera(c, [f for f in enviadas if f["tipo"] == "orden"], espera_s, dormir)
    return _espera(c, [f for f in enviadas if f["tipo"] == "orden"], espera_s, dormir, apuntar=True)


def fila_ejecucion(base: dict, orden_fila: dict, r: dict) -> dict:
    precio = float(r["filled_avg_price"]) if r.get("filled_avg_price") else None
    return {**base, "tipo": "ejecucion", "orden_id": orden_fila.get("orden_id"), "simbolo": orden_fila["simbolo"],
            "lado": orden_fila["lado"], "tramo": orden_fila.get("tramo"), "estado": r.get("status"),
            "qty_pedida": orden_fila.get("qty"), "qty_ejecutada": float(r.get("filled_qty") or 0),
            "precio_medio": precio, "precio_ref": orden_fila.get("precio_ref"),
            "cierre_sesion": orden_fila.get("cierre_sesion"), "hora_ejecucion": r.get("filled_at"),
            "deslizamiento_pb_vs_ref": deslizamiento_pb(orden_fila["lado"], precio, orden_fila.get("precio_ref")),
            "deslizamiento_pb_vs_cierre": deslizamiento_pb(orden_fila["lado"], precio, orden_fila.get("cierre_sesion")),
            "coste_teorico_pb": COSTE_TEORICO_PB.get(orden_fila.get("tramo") or "rv", 10.0)}


def _espera(c: A.Cliente, filas: list[dict], espera_s: float, dormir, apuntar: bool = False) -> list[dict]:
    pendientes = {f["orden_id"]: f for f in filas if f.get("orden_id")}
    estados: dict[str, dict] = {}
    t0 = time.monotonic()
    while pendientes:
        for oid in list(pendientes):
            try:
                r = c.orden(oid)
            except A.AlpacaError:
                continue
            estados[oid] = r
            if r.get("status") in ESTADOS_FINALES:
                pendientes.pop(oid)
        if not pendientes or time.monotonic() - t0 >= espera_s:
            break
        dormir(2)
    if not apuntar:
        return []
    out = []
    for f in filas:
        r = estados.get(f.get("orden_id"))
        if r and r.get("status") in ESTADOS_FINALES:
            fila = fila_ejecucion({k: f[k] for k in ("cartera", "cierre", "perfil", "cuenta", "cuenta_huella",
                                                       "mapeo_version")} |
                                  {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}, f, r)
            apunta(fila)
            out.append(fila)
    return out


def seguimiento(c: A.Cliente) -> list[dict]:
    """Apunta la ejecución de las órdenes del registro que aún no tienen estado final apuntado."""
    reg = leer_registro()
    hechas = {r.get("orden_id") for r in reg if r.get("tipo") == "ejecucion"}
    filas = [r for r in reg if r.get("tipo") == "orden" and r.get("orden_id") not in hechas
             and r.get("perfil") == (c.cred.perfil or "defecto")]
    return _espera(c, filas, 0, lambda s: None, apuntar=True)


def resumen_ejecucion(registro: list[dict], cartera: str | None = None) -> dict:
    """Deslizamiento medio ponderado por valor (vs ref y vs cierre) frente al coste teórico, por cartera."""
    ej = [r for r in registro if r.get("tipo") == "ejecucion" and r.get("qty_ejecutada")
          and (cartera is None or r.get("cartera") == cartera)]
    def media(campo):
        xs = [(r[campo], r["qty_ejecutada"] * (r["precio_medio"] or 0)) for r in ej if r.get(campo) is not None]
        v = sum(w for _, w in xs)
        return round(sum(x * w for x, w in xs) / v, 2) if v else None
    v = sum(r["qty_ejecutada"] * (r["precio_medio"] or 0) for r in ej)
    teo = sum(r["qty_ejecutada"] * (r["precio_medio"] or 0) * r.get("coste_teorico_pb", 10) for r in ej)
    return {"ejecuciones": len(ej), "valor_usd": round(v, 2), "desliz_pb_vs_ref": media("deslizamiento_pb_vs_ref"),
            "desliz_pb_vs_cierre": media("deslizamiento_pb_vs_cierre"),
            "coste_teorico_pb": round(teo / v, 2) if v else None}


# --------------------------------------------------------------------------- comando
def _imprime(p: dict) -> None:
    d, m, r = p["decision"], p["mercado"], p["resumen"]
    print(f"Espejo {p['cartera']} · decisión del cierre {d['cierre']} · pesos {d['pesos']} · cuenta {p['cuenta']}")
    print(f"mercado {'ABIERTO' if m['abierto'] else 'cerrado'} → órdenes {r['tipo_orden']} · valor {r['equity']:.2f} $"
          f" · efectivo {r['efectivo']:.2f} $ · rotación {r['rotacion']:.2%} · coste teórico {r['coste_teorico_usd']} $")
    for o in p["ordenes"]:
        lim = f" limit {o.limit_price}" if o.limit_price else ""
        print(f"  {o.lado:4s} {o.simbolo:5s} {_fmt_qty(o.qty):>12s} @≈{o.precio_ref}{lim} = {o.valor_estimado:.2f} $"
              f"  (peso {o.peso_actual:.1%} → {o.peso_objetivo:.1%})")
    if r.get("sin_operar"):
        print(f"  sin órdenes: {r['sin_operar']}")
    elif not p["ordenes"]:
        print("  sin órdenes: la cuenta ya está en los pesos (o las diferencias son menores que el mínimo)")
    for o in r["omitidas"]:
        print(f"  omitida (menor que el mínimo o sin presupuesto): {o}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Espejo de ejecución en Alpaca PAPER de B0/B1/B1′/S1/D1 (solo simulado)")
    ap.add_argument("--cartera", help="B0, B1, B1P (B1′), S1 o D1")
    ap.add_argument("--cierre", help="AAAA-MM-DD; por defecto la última decisión registrada")
    ap.add_argument("--perfil", default=None, help="perfil de alpaca.env; por defecto el de la cartera o el general")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True, help="(por defecto) calcula sin enviar")
    g.add_argument("--ejecutar", action="store_true", help="envía las órdenes a la cuenta PAPER")
    ap.add_argument("--auto", action="store_true", help="modo launchd: sale 0 si no hay nada que hacer; "
                                                         "--ejecutar solo con FIN_ALPACA_EJECUTAR=1")
    ap.add_argument("--seguimiento", action="store_true", help="apunta ejecuciones pendientes")
    ap.add_argument("--espera", type=float, default=None, help="segundos de espera por ejecuciones")
    a = ap.parse_args(argv)
    if not a.seguimiento and not a.cartera:
        ap.error("--cartera es obligatoria (salvo con --seguimiento)")
    cartera = A.normaliza_perfil(a.cartera) if a.cartera else None
    ejecuta = a.ejecutar and (not a.auto or os.environ.get("FIN_ALPACA_EJECUTAR") == "1")
    if a.ejecutar and not ejecuta:
        print("--auto sin FIN_ALPACA_EJECUTAR=1: solo dry-run")
    try:
        cred = None
        if a.perfil is not None:
            cred = A.cargar_credenciales(a.perfil)
        else:
            cred = A.cargar_credenciales(cartera) if cartera else None
            cred = cred or A.cargar_credenciales(None)
    except A.EndpointNoPermitido as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    if cred is None:
        print(f"Alpaca no configurado (sin claves en el entorno ni en {A.ruta_env()}): espejo omitido")
        return 0
    c = A.Cliente(cred)
    try:
        if a.seguimiento:
            filas = seguimiento(c)
            print(f"{len(filas)} ejecuciones apuntadas en {ruta_registro()}")
            return 0
        reg = leer_registro()
        if a.auto and ejecuta:
            d = decision(cartera, a.cierre)
            if d and any(r.get("tipo") == "plan" and r.get("ejecutado") and r.get("cartera") == cartera
                         and r.get("cierre") == d["cierre"] and r.get("perfil") == (cred.perfil or "defecto")
                         for r in reg):
                print(f"espejo {cartera} del cierre {d['cierre']} ya ejecutado: nada que hacer")
                return 0
        p = plan(c, cartera, a.cierre)
    except LookupError as e:
        print(str(e))
        return 0 if a.auto else 3
    except (A.AlpacaError, ValueError) as e:
        print(f"ERROR: {cred.enmascarar(str(e))}", file=sys.stderr)
        return 1
    _imprime(p)
    if ejecuta:
        motivo = puede_ejecutar(cred, cartera, p["cuenta_huella"], reg)
        if motivo:
            print(f"NO se ejecuta: {motivo}", file=sys.stderr)
            ejecuta = False
    fila_plan = {**_base(p, cred), "tipo": "plan", "dry_run": not ejecuta, "ejecutado": False,
                 "pesos_decision": p["decision"]["pesos"], "mercado": p["mercado"], "precios": p["precios"],
                 "cierre_sesion": p["cierre_sesion"], "posiciones_antes": p["posiciones"], "resumen": p["resumen"],
                 "ordenes": [asdict(o) for o in p["ordenes"]]}
    if not ejecuta:
        apunta(fila_plan)
        print(f"dry-run: nada enviado (plan apuntado en {ruta_registro()})")
        return 0 if not a.ejecutar or a.auto else 7
    fila_plan["ejecutado"] = True
    apunta(fila_plan)
    try:
        ej = ejecutar(c, p, espera_s=a.espera if a.espera is not None
                      else mapeo_de(cartera).get("ordenes", {}).get("espera_ejecucion_s", 60))
    except A.AlpacaError as e:
        print(f"ERROR: {cred.enmascarar(str(e))}", file=sys.stderr)
        return 1
    for f in ej:
        print(f"  {f['estado']:9s} {f['lado']:4s} {f['simbolo']:5s} {f['qty_ejecutada']} @ {f['precio_medio']} · "
              f"desliz. {f['deslizamiento_pb_vs_ref']} pb vs ref, {f['deslizamiento_pb_vs_cierre']} pb vs cierre")
    pend = len([o for o in p["ordenes"]]) - len(ej)
    if pend:
        print(f"{pend} órdenes sin estado final todavía: `python -m src.broker.espejo --seguimiento` más tarde")
    return 0


if __name__ == "__main__":
    sys.exit(main())
