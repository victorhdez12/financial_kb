"""Guardia de A1 «selección de acciones» (docs/factors/A1_seleccion_acciones_spec.md v1.0 §2 y §5): la guardia de C1
(src/broker/c1_guardia.py: solo paper, sin apalancamiento —compras ≤ efectivo—, sin cortos, ≤ 20 órdenes) MÁS las
reglas del mandato a1-v1 (config/a1_mandato_v1.md). Funciones puras; el contexto sale del paquete del día.

Por orden (antes de mirar la cuenta; `comprobar_orden`):
- solo `clase` = `accion` (acciones y ETFs de EE. UU.): opciones y cripto se RECHAZAN;
- cita DOBLE: `citas_macro` (≥ 1 {modelo, dice}, modelo de MACRO con salida hoy) y `citas_empresa` (≥ 1 {fuente, dice},
  fuente de FUENTES_EMPRESA con datos HOY para ESE símbolo en el paquete). Excepciones declaradas: los ETFs de colchón
  (COLCHON) solo necesitan la cita macro; la VENTA de algo que hoy no tiene ningún dato de empresa en el paquete (p. ej.
  los ETFs heredados URTH/GLD) también. Sin cita válida → orden rechazada;
- compras: solo acciones del universo con datos de empresa hoy (`universo_compra`) o ETFs de colchón.
Por cartera (después de la guardia de C1; `limites`): con la cuenta (valor y posiciones) y las órdenes válidas del día
(las ventas válidas se descuentan a su precio de referencia; las compras se suman a su coste estimado):
- máx. 10 % del valor de la cuenta por valor (MAX_POR_VALOR), máx. 35 % por sector (MAX_POR_SECTOR; sector del
  paquete; una acción sin sector no se puede comprar), máx. 30 valores distintos (MAX_VALORES),
- y el FILTRO MACRO: lo invertido fuera del colchón (acciones y ETFs heredados) ≤ `techo_bolsa` × valor (lo calcula el
  paquete con reglas fijas de régimen, crédito, liquidez, E1 e INT-11).
La compra que lo incumple se rechaza (y su coste se devuelve al efectivo disponible); NO se fuerza ninguna venta si la
cartera ya está por encima (por subidas de precio): eso lo vigila el supervisor.
La guardia NO comprueba que lo citado sea verdad (lo revisa el supervisor).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.broker import c1_guardia as G

REPO = G.REPO
PARADA = REPO / "research" / "paper" / "A1_PARADA"
VERSION_MANDATO = "a1-v1"
MACRO = {
    "cuadrante": "cuadrante y G/I del clasificador en vivo (signal.regime)",
    "credito": "semáforo de crédito (signal.credit)",
    "liquidez": "liquidez (signal.liquidity)",
    "ciclo_deuda": "ciclo de deuda corto y largo (signal.debt_cycle, signal.long_cycle)",
    "e1": "P(recesión a 12 m) de E1 (research/int/e1_vivo.jsonl)",
    "int11": "escenarios de INT-11 por activo (signal.escenarios)",
    "diagnosticos": "diagnósticos de la semana (obsidian/Diagnosticos)",
    "filtro_macro": "techo de bolsa del día calculado por el paquete con las reglas fijas del mandato",
}
FUENTES_EMPRESA = {
    "xbrl": "fundamentales XBRL de la SEC (candidatas: calidad y métricas; «Mis activos»: últimos trimestres)",
    "form4": "operaciones de directivos y consejeros (Form 4), últimos 12 meses",
    "13f": "posiciones de gestores institucionales (13F), último trimestre",
    "flujos": "participaciones ≥ 5 % (13D/13G)",
    "alertas": "alertas de flujos (src/report/alertas.py)",
    "ficha": "ficha de «Mis activos» en el panel",
}
COLCHON = {"SGOV", "BIL", "SHV", "SHY", "IEI"}
MAX_POR_VALOR = 0.10
MAX_POR_SECTOR = 0.35
MAX_VALORES = 30
MIN_VALORES = 10            # objetivo del mandato, no lo impone la guardia (lo vigila el supervisor)
CAIDA_MAX = -0.35
TOLERANCIA = 1e-6
CAMPOS_SALIDA = G.CAMPOS_SALIDA | {"citas_no_operar", "lectura_macro", "diario_md"}
CAMPOS_ORDEN = G.CAMPOS_ORDEN | {"citas_macro", "citas_empresa"}
MAX_CITAS = 9
MAX_DICE = 400
MAX_DIARIO = 20_000


@dataclass
class Contexto:
    """Lo que la guardia de A1 necesita del paquete del día (lo arma `contexto`)."""
    macro: set[str] = field(default_factory=set)                       # modelos macro con salida hoy
    empresa: dict[str, set[str]] = field(default_factory=dict)         # símbolo → fuentes de empresa con datos hoy
    universo_compra: set[str] = field(default_factory=set)             # acciones que se pueden comprar hoy
    sectores: dict[str, str] = field(default_factory=dict)             # símbolo → sector
    techo_bolsa: float | None = None                                   # filtro macro (fracción del valor)
    valor: float | None = None                                         # valor de la cuenta
    posiciones: dict[str, float] = field(default_factory=dict)         # símbolo → valor de mercado ($)
    precios_pos: dict[str, float] = field(default_factory=dict)        # símbolo → precio de las posiciones


def _f(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def contexto(paquete: dict) -> Contexto:
    cu = paquete.get("cuenta") or {}
    pos, pre = {}, {}
    for p in cu.get("posiciones") or []:
        s = G.clave(p.get("simbolo") or "")
        v = _f(p.get("valor"))
        if v is None and _f(p.get("precio")) is not None and _f(p.get("cantidad")) is not None:
            v = _f(p["precio"]) * _f(p["cantidad"])
        pos[s] = v or 0.0
        if _f(p.get("precio")):
            pre[s] = _f(p["precio"])
        elif v and _f(p.get("cantidad")):
            pre[s] = v / _f(p["cantidad"])
    fm = paquete.get("filtro_macro") or {}
    return Contexto(macro=set(paquete.get("macro_disponibles") or []),
                    empresa={G.clave(k): set(v) for k, v in (paquete.get("empresa_disponible") or {}).items()},
                    universo_compra={G.clave(x) for x in paquete.get("universo_compra") or []},
                    sectores={G.clave(k): v for k, v in (paquete.get("sectores") or {}).items() if v},
                    techo_bolsa=_f(fm.get("techo_bolsa")), valor=_f(cu.get("valor")), posiciones=pos, precios_pos=pre)


# --------------------------------------------------------------------------- citas
def _citas(citas, clave_id: str, validos: dict, disponibles: set[str], que: str) -> str | None:
    if not isinstance(citas, list) or not citas:
        return f"sin {que}"
    if len(citas) > MAX_CITAS:
        return f"demasiadas citas en {que} ({len(citas)} > {MAX_CITAS})"
    for c in citas:
        if not isinstance(c, dict) or set(c) - {clave_id, "dice"}:
            return f"{que}: cita mal formada (cada cita es {{{clave_id}, dice}})"
        m = c.get(clave_id)
        if m not in validos:
            return f"{que}: {m!r} no está en la lista del mandato"
        if m not in disponibles:
            return f"{que}: {m!r} hoy no tiene datos en el paquete"
        d = c.get("dice")
        if not isinstance(d, str) or not d.strip():
            return f"{que}: cita a {m!r} sin decir qué dice"
        if len(d) > MAX_DICE:
            return f"{que}: cita a {m!r} demasiado larga ({len(d)} > {MAX_DICE})"
    return None


def motivo_citas_macro(citas, ctx: Contexto) -> str | None:
    return _citas(citas, "modelo", MACRO, ctx.macro, "cita macro (citas_macro)")


def motivo_citas_empresa(citas, simbolo: str, ctx: Contexto) -> str | None:
    return _citas(citas, "fuente", FUENTES_EMPRESA, ctx.empresa.get(G.clave(simbolo), set()),
                  f"cita de datos de la empresa {simbolo} (citas_empresa)")


def comprobar_orden(ctx: Contexto):
    """`extra_orden(orden) -> motivo | None` para G.validar (antes de mirar la cuenta)."""
    def comprobar(o: dict) -> str | None:
        if o.get("clase") != "accion":
            return f"clase {o.get('clase')!r}: A1 es selección de acciones pura (sin opciones ni cripto)"
        s = G.clave(str(o.get("simbolo") or "").strip())
        m = motivo_citas_macro(o.get("citas_macro"), ctx)
        if m:
            return m
        colchon = s in COLCHON
        if o.get("lado") == "compra" and not colchon and s not in ctx.universo_compra:
            return f"{s} fuera del universo de compra de hoy (acciones con datos de empresa en el paquete o colchón)"
        if colchon:
            return None
        if o.get("lado") == "venta" and not ctx.empresa.get(s):
            return None     # venta de algo sin datos de empresa hoy (ETF heredado): basta la cita macro
        return motivo_citas_empresa(o.get("citas_empresa"), s, ctx)
    return comprobar


# --------------------------------------------------------------------------- salida
def lector(ctx: Contexto):
    """`leer(texto) -> dict` para G.validar (lanza G.SalidaInvalida si incumple el mandato a1-v1)."""
    def leer(texto: str | None) -> dict:
        d = G.leer_salida(texto, version=VERSION_MANDATO, campos=CAMPOS_SALIDA, prosa_previa=True)
        for k in ("lectura_macro", "diario_md"):
            if not isinstance(d.get(k), str) or not d[k].strip():
                raise G.SalidaInvalida(f"falta '{k}' (texto)")
        if len(d["diario_md"]) > MAX_DIARIO:
            raise G.SalidaInvalida(f"'diario_md' demasiado largo ({len(d['diario_md'])} > {MAX_DIARIO})")
        if not d["ordenes"]:
            m = motivo_citas_macro(d.get("citas_no_operar"), ctx)
            if m:
                raise G.SalidaInvalida(f"no opera sin citar la lectura macro en 'citas_no_operar': {m}")
        return d
    return leer


# --------------------------------------------------------------------------- límites de cartera
def limites(ver: G.Veredicto, ctx: Contexto, estado: G.EstadoCuenta | None = None) -> G.Veredicto:
    """Rechaza (en el orden propuesto) las compras válidas que romperían 10 % por valor, 35 % por sector, 30 valores o
    el techo de bolsa. Modifica y devuelve `ver`."""
    if not ver.opera or not ver.validas:
        return ver
    if not ctx.valor or ctx.valor <= 0:
        for n in [n for n in ver.validas if n["lado"] == "compra"]:
            ver.validas.remove(n)
            ver.rechazadas.append({"indice": n["indice"], "orden": n,
                                   "motivo": "sin valor de la cuenta: no se pueden comprobar los límites de A1"})
        ver.compras_estimadas_usd = 0.0
        ver.rechazadas.sort(key=lambda r: r["indice"])
        return ver
    precios = dict(ctx.precios_pos)
    if estado is not None:
        precios.update({k: v for k, v in estado.precios.items() if v})
    val = dict(ctx.posiciones)
    for n in ver.validas:
        if n["lado"] == "venta":
            k = G.clave(n["simbolo"])
            p = precios.get(k)
            if p:
                val[k] = max(0.0, val.get(k, 0.0) - n["cantidad"] * p)
    V = ctx.valor

    def bolsa() -> float:
        return sum(v for k, v in val.items() if k not in COLCHON)

    def sector(s: str) -> float:
        return sum(v for k, v in val.items() if k not in COLCHON and ctx.sectores.get(k) == s)

    def n_valores() -> int:
        return sum(1 for k, v in val.items() if k not in COLCHON and v > 1.0)

    quedan = []
    for n in ver.validas:
        if n["lado"] != "compra":
            quedan.append(n)
            continue
        k = G.clave(n["simbolo"])
        coste = float(n.get("coste_estimado_usd") or 0.0)
        motivo = None
        if k not in COLCHON:
            sec = ctx.sectores.get(k)
            if (val.get(k, 0.0) + coste) > MAX_POR_VALOR * V + TOLERANCIA:
                motivo = (f"{k} pasaría a {(val.get(k, 0.0) + coste) / V:.1%} del valor de la cuenta "
                          f"(máx. {MAX_POR_VALOR:.0%} por valor)")
            elif sec is None:
                motivo = f"{k} sin sector en el paquete: no se puede comprobar el máximo por sector"
            elif sector(sec) + coste > MAX_POR_SECTOR * V + TOLERANCIA:
                motivo = (f"el sector {sec} pasaría a {(sector(sec) + coste) / V:.1%} (máx. {MAX_POR_SECTOR:.0%} "
                          "por sector)")
            elif val.get(k, 0.0) <= 1.0 and n_valores() + 1 > MAX_VALORES:
                motivo = f"abriría el valor nº {n_valores() + 1} (máx. {MAX_VALORES} valores)"
            elif ctx.techo_bolsa is None:
                motivo = "sin filtro macro (techo de bolsa) en el paquete: A1 no compra acciones hoy"
            elif bolsa() + coste > ctx.techo_bolsa * V + TOLERANCIA:
                motivo = (f"la bolsa pasaría a {(bolsa() + coste) / V:.1%} del valor; el filtro macro de hoy la "
                          f"limita a {ctx.techo_bolsa:.0%}")
        if motivo:
            ver.rechazadas.append({"indice": n["indice"], "orden": n, "motivo": motivo})
            ver.compras_estimadas_usd = round(ver.compras_estimadas_usd - coste, 2)
        else:
            val[k] = val.get(k, 0.0) + coste
            quedan.append(n)
    ver.validas = quedan
    ver.rechazadas.sort(key=lambda r: r["indice"])
    return ver


def validar(texto: str | None, estado: G.EstadoCuenta | None, ctx: Contexto, *,
            parada: bool | None = None) -> G.Veredicto:
    v = G.validar(texto, estado, parada=parada, leer=lector(ctx), campos_orden=CAMPOS_ORDEN,
                  extra_orden=comprobar_orden(ctx), ruta_parada=PARADA)
    return limites(v, ctx, estado)


def ruta_parada() -> Path:
    return PARADA
