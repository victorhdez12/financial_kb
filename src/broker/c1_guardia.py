"""Guardia de C1 «Claude gestor» (docs/factors/C1_claude_gestor_spec.md v1.0 §3): reglas en código que NO dependen del
modelo. Funciones puras: reciben la salida de Claude (texto) y el estado de la cuenta, y devuelven qué órdenes son
válidas y cuáles se rechazan, con su motivo. No habla con Alpaca (eso es src/paper/c1.py).

Reglas:
- Solo `paper-api` (`comprobar_cliente`; el endpoint real se rechaza siempre, como en src/broker/alpaca.py).
- Sin apalancamiento: la suma de las compras (estimadas al precio límite, o al precio de referencia + 1 % de colchón si
  son de mercado) no supera el EFECTIVO de la cuenta (`cash`); se ignora el poder de compra 2× de Alpaca. Las ventas del
  mismo día no cuentan como efectivo (pueden no ejecutarse a tiempo).
- Sin cortos: no se vende más de lo que hay en cartera (sumando las ventas del mismo día); nada se vende si no se tiene.
- Opciones: solo comprar para abrir (`buy_to_open`) y vender para cerrar (`sell_to_close`) contratos que se tienen
  comprados; nunca vender al descubierto. Prima total (precio × 100 × contratos) ≤ efectivo.
- Máximo 20 órdenes al día (más = salida inválida: ese día no opera). Símbolo desconocido, no negociable o de otra
  clase que la declarada: fuera.
- Salida que no es un JSON con el formato del mandato (config/c1_mandato_v1.md), o de otra versión del mandato: ese día
  no opera. Botón de parada `research/paper/C1_PARADA`: si existe, no opera.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.broker import alpaca as A

REPO = A.REPO
PARADA = REPO / "research" / "paper" / "C1_PARADA"
VERSION_MANDATO = "c1-v1"
MAX_ORDENES = 20
COLCHON_MERCADO = 0.01          # las compras de mercado se estiman al precio de referencia + 1 %
MULTIPLICADOR_OPCION = 100      # acciones por contrato
IMPORTE_MINIMO = 1.0            # Alpaca no admite órdenes de menos de 1 $
MAX_TEXTO = 800
CLASES = {"accion": "us_equity", "opcion": "us_option", "cripto": "crypto"}
LADOS = {"compra": "buy", "venta": "sell"}
TIPOS = {"mercado": "market", "limite": "limit"}
CAMPOS_ORDEN = {"simbolo", "clase", "lado", "tipo", "cantidad", "importe_usd", "precio_limite", "razon",
                "cambiaria_de_opinion"}
CAMPOS_SALIDA = {"version_mandato", "fecha", "ordenes", "nota_diario", "resumen"}
RE_SIMBOLO = re.compile(r"^[A-Z0-9][A-Z0-9./]{0,31}$")


class SalidaInvalida(ValueError):
    """La salida de Claude no es un JSON con el formato del mandato: ese día no se opera."""


def clave(simbolo: str) -> str:
    """Símbolo normalizado para comparar (Alpaca escribe la cripto como BTC/USD en órdenes y BTCUSD en posiciones)."""
    return str(simbolo).strip().upper().replace("/", "")


def comprobar_cliente(c: A.Cliente) -> None:
    """El cliente tiene que hablar con el paper de Alpaca y con nada más (lanza A.EndpointNoPermitido)."""
    if A.comprobar_url(c.base, solo_trading=True) != A.PAPER_TRADING:
        raise A.EndpointNoPermitido(f"C1 solo opera en {A.PAPER_TRADING}")


# --------------------------------------------------------------------------- lectura de la salida
def bloque_final(t: str) -> str | None:
    """Contenido del ÚLTIMO bloque ```json …``` si el texto TERMINA en él (modo agente: el último mensaje de un agente
    con herramientas suele llevar una frase antes del JSON; ensayos reales del 19-nov). Si no, None."""
    m = re.search(r"```json[ \t]*\n((?:(?!```).)*)\n```\s*\Z", t, flags=re.S)
    return m.group(1).strip() if m else None


def leer_salida(texto: str | None, *, version: str = VERSION_MANDATO, campos: set[str] | None = None,
                prosa_previa: bool = False) -> dict:
    """JSON de la salida de Claude. Admite el JSON solo o envuelto en UN bloque ```json …```; nada más.
    `version` y `campos`: los del mandato (c1-v1 por defecto; el modo agente c1-v2 y M1 m1-v1 pasan los suyos).
    `prosa_previa` (modo agente): admite además texto ANTES de un único bloque ```json final; nada después."""
    campos = CAMPOS_SALIDA if campos is None else campos
    if texto is None or not str(texto).strip():
        raise SalidaInvalida("salida vacía")
    t = str(texto).strip()
    m = re.fullmatch(r"```(?:json)?\s*\n(.*)\n```", t, flags=re.S)
    if m:
        t = m.group(1).strip()
    elif prosa_previa and bloque_final(t) is not None:
        t = bloque_final(t)
    try:
        d = json.loads(t)
    except json.JSONDecodeError as e:
        raise SalidaInvalida(f"no es JSON válido ({e.msg}, posición {e.pos})") from None
    if not isinstance(d, dict):
        raise SalidaInvalida("el JSON no es un objeto")
    extra = set(d) - campos
    if extra:
        raise SalidaInvalida(f"campos no previstos en el mandato: {sorted(extra)}")
    if d.get("version_mandato") != version:
        raise SalidaInvalida(f"version_mandato {d.get('version_mandato')!r} ≠ {version!r}")
    if not isinstance(d.get("ordenes"), list):
        raise SalidaInvalida("falta la lista 'ordenes' (puede ser [] si no opera)")
    if not isinstance(d.get("nota_diario"), str) or not d["nota_diario"].strip():
        raise SalidaInvalida("falta 'nota_diario' (texto)")
    if len(d["ordenes"]) > MAX_ORDENES:
        raise SalidaInvalida(f"{len(d['ordenes'])} órdenes: el máximo es {MAX_ORDENES} al día")
    return d


# --------------------------------------------------------------------------- estado y veredicto
@dataclass
class EstadoCuenta:
    """Lo que la guardia necesita saber de la cuenta y de los activos propuestos (lo arma src/paper/c1.py)."""
    efectivo: float                                   # `cash` de la cuenta (NO `buying_power`)
    posiciones: dict[str, float] = field(default_factory=dict)      # clave(símbolo) → cantidad (opciones: contratos)
    activos: dict[str, dict] = field(default_factory=dict)          # clave → {simbolo, clase, negociable, fraccionable}
    precios: dict[str, float] = field(default_factory=dict)         # clave → precio de compra estimado por unidad
    ordenes_hoy: int = 0                                            # órdenes ya enviadas hoy (reintentos)


@dataclass
class Veredicto:
    opera: bool
    motivo: str | None
    validas: list[dict] = field(default_factory=list)
    rechazadas: list[dict] = field(default_factory=list)
    efectivo: float | None = None
    compras_estimadas_usd: float = 0.0
    prima_opciones_usd: float = 0.0

    def a_dict(self) -> dict:
        return asdict(self)


def no_opera(motivo: str, efectivo: float | None = None) -> Veredicto:
    return Veredicto(False, motivo, efectivo=efectivo)


def _num(x) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    x = float(x)
    return x if math.isfinite(x) else None


def _forma(o, campos: set[str] | None = None) -> tuple[dict | None, str | None]:
    """Comprueba la forma de una orden (sin mirar la cuenta). Devuelve (orden normalizada, None) o (None, motivo)."""
    if not isinstance(o, dict):
        return None, "la orden no es un objeto"
    extra = set(o) - (CAMPOS_ORDEN if campos is None else campos)
    if extra:
        return None, f"campos no previstos: {sorted(extra)}"
    s = str(o.get("simbolo") or "").strip().upper()
    if not RE_SIMBOLO.match(s):
        return None, f"símbolo no válido {o.get('simbolo')!r}"
    if o.get("clase") not in CLASES:
        return None, f"clase {o.get('clase')!r} no válida (accion, opcion, cripto)"
    if o.get("lado") not in LADOS:
        return None, f"lado {o.get('lado')!r} no válido (compra, venta)"
    tipo = o.get("tipo", "mercado")
    if tipo not in TIPOS:
        return None, f"tipo {tipo!r} no válido (mercado, limite)"
    for k in ("razon", "cambiaria_de_opinion"):
        v = o.get(k)
        if not isinstance(v, str) or not v.strip():
            return None, f"falta '{k}' (el mandato exige explicar cada orden)"
        if len(v) > MAX_TEXTO:
            return None, f"'{k}' demasiado largo ({len(v)} > {MAX_TEXTO} caracteres)"
    cant, imp, lim = o.get("cantidad"), o.get("importe_usd"), o.get("precio_limite")
    cant = None if cant is None else _num(cant)
    imp = None if imp is None else _num(imp)
    if (o.get("cantidad") is not None and cant is None) or (o.get("importe_usd") is not None and imp is None):
        return None, "cantidad o importe no numéricos"
    if (cant is None) == (imp is None):
        return None, "hay que dar exactamente uno de 'cantidad' o 'importe_usd'"
    if cant is not None and cant <= 0 or imp is not None and imp <= 0:
        return None, "cantidad o importe ≤ 0"
    if cant is not None and math.floor(cant * 1e9 + 1e-6) <= 0:
        return None, "cantidad < 1e-9 (se truncaría a 0)"
    if imp is not None:
        if o["lado"] != "compra" or o["clase"] == "opcion" or tipo != "mercado":
            return None, "'importe_usd' solo en compras de mercado de acciones o cripto (las ventas van por cantidad)"
        imp = math.floor(imp * 100 + 1e-6) / 100   # céntimos hacia abajo: el `notional` enviado = el coste estimado
        if imp < IMPORTE_MINIMO:
            return None, f"importe < {IMPORTE_MINIMO} $"
    if o["clase"] == "opcion" and (cant is None or cant != int(cant)):
        return None, "las opciones van en contratos enteros"
    if tipo == "limite":
        lim = _num(lim)
        if lim is None or lim <= 0:
            return None, "orden límite sin 'precio_limite' > 0"
        lim = precio_tick(lim, o["lado"])          # el coste se acota con el precio que de verdad se envía
        if lim <= 0:
            return None, "precio_limite demasiado pequeño (redondeado a 0)"
    elif o.get("precio_limite") is not None:
        return None, "'precio_limite' solo en órdenes límite"
    else:
        lim = None
    return {"simbolo": s, "clase": o["clase"], "lado": o["lado"], "tipo": tipo, "cantidad": cant, "importe_usd": imp,
            "precio_limite": lim, "razon": o["razon"].strip(), "cambiaria_de_opinion": o["cambiaria_de_opinion"].strip()}, None


def validar(texto: str | None, estado: EstadoCuenta | None, *, parada: bool | None = None,
            version: str = VERSION_MANDATO, campos_salida: set[str] | None = None,
            campos_orden: set[str] | None = None, leer=None, extra_orden=None,
            ruta_parada: Path | None = None) -> Veredicto:
    """Veredicto de la guardia para la salida `texto` de Claude. `estado` None = sin datos de la cuenta → no opera.

    Ampliaciones (modo agente c1-v2 y M1; las reglas de la cuenta son las mismas): `version`, `campos_salida` y
    `campos_orden` del mandato; `leer(texto) -> dict` sustituye a `leer_salida` (M1 comprueba además su declaración
    modelo por modelo); `extra_orden(orden) -> motivo | None` rechaza una orden antes de mirar la cuenta (M1: sin cita
    válida); `ruta_parada`: el botón de parada de esa cartera (por defecto el de C1)."""
    ruta_parada = PARADA if ruta_parada is None else ruta_parada
    parada = ruta_parada.exists() if parada is None else parada
    if parada:
        return no_opera(f"botón de parada: existe research/paper/{ruta_parada.name}")
    try:
        d = leer(texto) if leer is not None else leer_salida(texto, version=version, campos=campos_salida)
    except SalidaInvalida as e:
        return no_opera(f"salida de Claude inválida: {e}", estado.efectivo if estado else None)
    if estado is None:
        return no_opera("sin estado de la cuenta")
    efectivo = _num(estado.efectivo)
    if efectivo is None:
        return no_opera("efectivo de la cuenta no numérico")
    if estado.ordenes_hoy + len(d["ordenes"]) > MAX_ORDENES:
        return no_opera(f"{estado.ordenes_hoy} órdenes ya enviadas hoy + {len(d['ordenes'])} propuestas > {MAX_ORDENES}",
                        efectivo)
    v = Veredicto(True, None, efectivo=round(efectivo, 2))
    formadas = []
    for i, o in enumerate(d["ordenes"]):
        motivo = extra_orden(o) if extra_orden is not None and isinstance(o, dict) else None
        n, motivo = (None, motivo) if motivo else _forma(o, campos_orden)
        if motivo:
            v.rechazadas.append({"indice": i, "orden": o, "motivo": motivo})
        else:
            formadas.append((i, n))
    vendido: dict[str, float] = {}
    disponible = max(0.0, efectivo)
    # ventas primero (no generan efectivo utilizable el mismo día), luego compras en el orden propuesto
    for i, n in sorted(formadas, key=lambda x: (x[1]["lado"] != "venta", x[0])):
        k = clave(n["simbolo"])
        a = estado.activos.get(k)
        motivo = None
        if a is None:
            motivo = "activo desconocido o no verificado en Alpaca"
        elif not a.get("negociable"):
            motivo = "Alpaca lo marca como no negociable"
        elif a.get("clase") != n["clase"]:
            motivo = f"clase declarada {n['clase']} ≠ clase en Alpaca {a.get('clase')}"
        elif n["clase"] == "accion" and n["cantidad"] is not None and n["cantidad"] != int(n["cantidad"]) \
                and not a.get("fraccionable"):
            motivo = "fracciones en un activo no fraccionable"
        elif n["clase"] == "accion" and n["importe_usd"] is not None and not a.get("fraccionable"):
            motivo = "importe en $ (fracciones) en un activo no fraccionable"
        if motivo is None and n["lado"] == "venta":
            tengo = float(estado.posiciones.get(k, 0.0)) - vendido.get(k, 0.0)
            if float(estado.posiciones.get(k, 0.0)) < 0:
                motivo = "hay una posición corta en la cuenta: no se opera ese símbolo"
            elif tengo <= 0:
                motivo = "venta sin posición (sin cortos" + ("; opciones: solo vender para cerrar)" if n["clase"] == "opcion" else ")")
            elif n["cantidad"] > tengo + 1e-9:
                motivo = f"vende {n['cantidad']:g} y solo hay {tengo:g} (sin cortos)"
            else:
                vendido[k] = vendido.get(k, 0.0) + n["cantidad"]
        elif motivo is None:
            mult = MULTIPLICADOR_OPCION if n["clase"] == "opcion" else 1
            if n["importe_usd"] is not None:
                coste = n["importe_usd"]
            elif n["precio_limite"] is not None:
                coste = n["cantidad"] * n["precio_limite"] * mult
            elif estado.precios.get(k):
                coste = n["cantidad"] * float(estado.precios[k]) * (1 + COLCHON_MERCADO) * mult
            else:
                coste = None
                motivo = "compra de mercado sin precio de referencia: no se puede acotar el coste"
            if coste is not None:
                if coste > disponible + 1e-6:
                    motivo = (f"compra de ≈ {coste:,.2f} $ supera el efectivo que queda ({disponible:,.2f} $): "
                              "sin apalancamiento")
                else:
                    disponible -= coste
                    v.compras_estimadas_usd = round(v.compras_estimadas_usd + coste, 2)
                    if n["clase"] == "opcion":
                        v.prima_opciones_usd = round(v.prima_opciones_usd + coste, 2)
                    n["coste_estimado_usd"] = round(coste, 2)
        if motivo:
            v.rechazadas.append({"indice": i, "orden": n, "motivo": motivo})
        else:
            n["indice"] = i
            n["simbolo_alpaca"] = a.get("simbolo") or n["simbolo"]
            v.validas.append(n)
    assert v.compras_estimadas_usd <= max(0.0, efectivo) + 0.01 and v.prima_opciones_usd <= max(0.0, efectivo) + 0.01
    v.rechazadas.sort(key=lambda r: r["indice"])
    return v


# --------------------------------------------------------------------------- cuerpo de la orden para Alpaca
def _decimales_precio(p: float) -> int:
    return 2 if p >= 1 else 4


def precio_tick(p: float, lado: str) -> float:
    """Precio límite al decimal que se envía a Alpaca (2 decimales desde 1 $, 4 por debajo). Las compras se redondean
    HACIA ABAJO: así el coste estimado por la guardia nunca es menor que el máximo que puede costar la orden enviada
    (antes se estimaba con el precio sin redondear y el texto enviado podía redondear al alza)."""
    k = 10 ** _decimales_precio(p)
    return (math.floor(p * k + 1e-9) if lado == "compra" else round(p * k)) / k


def texto_precio(p: float) -> str:
    return f"{p:.{_decimales_precio(p)}f}"


def texto_qty(q: float) -> str:
    """Cantidad truncada a 9 decimales, sin ceros ni punto finales («10.» o «0.» no son cantidades válidas)."""
    t = f"{math.floor(q * 1e9 + 1e-6) / 1e9:.9f}".rstrip("0").rstrip(".")
    if float(t) <= 0:
        raise ValueError(f"cantidad {q!r} se trunca a 0")
    return t


def cuerpo_alpaca(n: dict, client_order_id: str) -> dict:
    """Cuerpo de POST /v2/orders para una orden VÁLIDA de la guardia. Opciones: siempre buy_to_open / sell_to_close."""
    c: dict = {"symbol": n.get("simbolo_alpaca") or n["simbolo"], "side": LADOS[n["lado"]], "type": TIPOS[n["tipo"]],
               "time_in_force": "gtc" if n["clase"] == "cripto" else "day", "client_order_id": client_order_id}
    if n["importe_usd"] is not None:
        c["notional"] = f"{n['importe_usd']:.2f}"
    else:
        q = n["cantidad"]
        c["qty"] = texto_qty(q)
    if n["tipo"] == "limite":
        c["limit_price"] = texto_precio(n["precio_limite"])
    if n["clase"] == "opcion":
        c["position_intent"] = "buy_to_open" if n["lado"] == "compra" else "sell_to_close"
    return c


def ruta_parada() -> Path:
    return PARADA
