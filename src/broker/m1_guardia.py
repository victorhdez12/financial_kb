"""Guardia de M1 «Claude gestor macro» (docs/factors/M1_cartera_macro_spec.md v1.1 §1-§2): la guardia de C1
(src/broker/c1_guardia.py: sin apalancamiento, sin cortos, opciones solo compradas, ≤ 20 órdenes, solo paper) MÁS la
obligación de base del mandato m1-v1 (config/m1_mandato_v1.md):

- cada orden lleva `citas`: lista no vacía de {modelo, dice}; `modelo` es uno de MODELOS y tiene salida en el paquete
  del día (`modelos_disponibles`); `dice` es texto (lo que el modelo dice). Una orden sin cita válida, o con alguna cita
  a un modelo que no existe o no tiene datos hoy, se RECHAZA (las demás siguen su camino);
- si no opera (`ordenes` vacía): `citas_no_operar` con al menos una cita válida; si no → salida inválida (no opera, y
  queda anotado como incumplimiento del mandato);
- `declaracion_modelos`: una entrada por cada modelo de MODELOS, exactamente una vez, con `caso` ∈ CASOS y `por_que`;
  si falta o sobra alguno → salida inválida;
- `desviacion_sombra` (texto) y `diario_md` (texto) obligatorios.
La guardia NO comprueba que lo citado sea verdad (eso lo revisa el supervisor, supervisor_carteras_spec.md §1.1).
Funciones puras.
"""
from __future__ import annotations

from pathlib import Path

from src.broker import c1_guardia as G

REPO = G.REPO
PARADA = REPO / "research" / "paper" / "M1_PARADA"
VERSION_MANDATO = "m1-v1"
MODELOS = {
    "cuadrante": "cuadrante y G/I del clasificador en vivo (signal.regime)",
    "credito": "semáforo de crédito (signal.credit)",
    "liquidez": "liquidez (signal.liquidity)",
    "ciclo_deuda": "ciclo de deuda corto y largo (signal.debt_cycle, signal.long_cycle)",
    "e1": "P(recesión a 12 m) de E1 (research/int/e1_vivo.jsonl)",
    "int11": "escenarios de INT-11 por activo (signal.escenarios)",
    "diagnosticos": "diagnósticos de la semana (obsidian/Diagnosticos)",
    "alertas": "alertas de flujos (src/report/alertas.py)",
    "xbrl": "fundamentales XBRL de las acciones (sec_fundamentales/hechos.json)",
}
CASOS = {"si", "no", "parcial", "no_disponible"}
CAMPOS_SALIDA = G.CAMPOS_SALIDA | {"citas_no_operar", "declaracion_modelos", "desviacion_sombra", "diario_md"}
CAMPOS_ORDEN = G.CAMPOS_ORDEN | {"citas"}
MAX_CITAS = 9
MAX_DICE = 400
MAX_DIARIO = 20_000


def _motivo_citas(citas, disponibles: set[str]) -> str | None:
    if not isinstance(citas, list) or not citas:
        return "sin cita de los modelos (el mandato m1-v1 exige citar qué salidas de los modelos la justifican)"
    if len(citas) > MAX_CITAS:
        return f"demasiadas citas ({len(citas)} > {MAX_CITAS})"
    for c in citas:
        if not isinstance(c, dict) or set(c) - {"modelo", "dice"}:
            return "cita mal formada (cada cita es {modelo, dice})"
        m = c.get("modelo")
        if m not in MODELOS:
            return f"cita a un modelo que no está en la lista del mandato: {m!r}"
        if m not in disponibles:
            return f"cita al modelo {m!r}, que hoy no tiene salida en el paquete"
        d = c.get("dice")
        if not isinstance(d, str) or not d.strip():
            return f"cita a {m!r} sin decir qué dice el modelo"
        if len(d) > MAX_DICE:
            return f"cita a {m!r} demasiado larga ({len(d)} > {MAX_DICE})"
    return None


def lector(disponibles: set[str]):
    """Función `leer(texto) -> dict` para G.validar (lanza G.SalidaInvalida si incumple el mandato m1-v1)."""
    def leer(texto: str | None) -> dict:
        d = G.leer_salida(texto, version=VERSION_MANDATO, campos=CAMPOS_SALIDA, prosa_previa=True)
        dec = d.get("declaracion_modelos")
        if not isinstance(dec, list):
            raise G.SalidaInvalida("falta 'declaracion_modelos' (una línea por modelo: le hace caso o no y por qué)")
        vistos = []
        for x in dec:
            if not isinstance(x, dict) or set(x) - {"modelo", "caso", "por_que"}:
                raise G.SalidaInvalida("cada entrada de 'declaracion_modelos' es {modelo, caso, por_que}")
            if x.get("modelo") not in MODELOS:
                raise G.SalidaInvalida(f"declaracion_modelos: modelo desconocido {x.get('modelo')!r}")
            if x.get("caso") not in CASOS:
                raise G.SalidaInvalida(f"declaracion_modelos: caso {x.get('caso')!r} no válido {sorted(CASOS)}")
            if not isinstance(x.get("por_que"), str) or not x["por_que"].strip():
                raise G.SalidaInvalida(f"declaracion_modelos: falta 'por_que' en {x['modelo']}")
            if x["caso"] in ("si", "parcial") and x["modelo"] not in disponibles:
                raise G.SalidaInvalida(f"declaracion_modelos: dice hacer caso a {x['modelo']!r}, que hoy no tiene salida")
            vistos.append(x["modelo"])
        if sorted(vistos) != sorted(MODELOS):
            faltan, repes = sorted(set(MODELOS) - set(vistos)), sorted({m for m in vistos if vistos.count(m) > 1})
            raise G.SalidaInvalida(f"declaracion_modelos debe tener cada modelo una vez (faltan {faltan}, repetidos {repes})")
        for k in ("desviacion_sombra", "diario_md"):
            if not isinstance(d.get(k), str) or not d[k].strip():
                raise G.SalidaInvalida(f"falta '{k}' (texto)")
        if len(d["diario_md"]) > MAX_DIARIO:
            raise G.SalidaInvalida(f"'diario_md' demasiado largo ({len(d['diario_md'])} > {MAX_DIARIO})")
        if not d["ordenes"]:
            m = _motivo_citas(d.get("citas_no_operar"), disponibles)
            if m:
                raise G.SalidaInvalida(f"no opera sin citar modelos válidos en 'citas_no_operar': {m}")
        return d
    return leer


def comprobar_orden(disponibles: set[str]):
    """Función `extra_orden(orden) -> motivo | None` para G.validar: rechaza la orden sin cita válida."""
    return lambda o: _motivo_citas(o.get("citas"), disponibles)


def validar(texto: str | None, estado: G.EstadoCuenta | None, disponibles: set[str], *,
            parada: bool | None = None) -> G.Veredicto:
    return G.validar(texto, estado, parada=parada, leer=lector(disponibles), campos_orden=CAMPOS_ORDEN,
                     extra_orden=comprobar_orden(disponibles), ruta_parada=PARADA)


def ruta_parada() -> Path:
    return PARADA
