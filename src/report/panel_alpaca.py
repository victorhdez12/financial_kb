"""Sección «Alpaca paper» del panel, al final de la pestaña «Mi cartera» (src/report/panel.py `_alpaca`).
Desde el 20-nov-2026: solo los perfiles de las cuentas gestionadas (C1, M1, A1), sin espejo.

Muestra, por cada perfil configurado: estado del mercado, valor de la cuenta PAPER (simulada), posiciones con su peso
frente al peso objetivo de la cartera que espeja, y el resumen del espejo (deslizamiento real vs coste teórico).
Nunca muestra claves ni el número de cuenta completo. Sin claves: un aviso breve «Alpaca no configurado». Cualquier fallo
de Alpaca queda dentro de la sección (no tumba el panel).
"""
from __future__ import annotations

import html

from src.broker import alpaca as A
from src.broker import espejo as E


def _e(x) -> str:
    return html.escape("" if x is None else str(x))


def _num(x, dec: int = 2) -> str:
    try:
        return f"{float(x):,.{dec}f}".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


GESTIONADAS = {"C1": "Claude gestor libre (docs/factors/C1_claude_gestor_spec.md)",
               "M1": "Claude gestor macro (docs/factors/M1_cartera_macro_spec.md)",
               "A1": "Claude selección de acciones (docs/factors/A1_seleccion_acciones_spec.md)"}


def _bloque_perfil(c: A.Cliente, registro: list[dict]) -> str:
    gestionada = c.cred.perfil in GESTIONADAS
    cartera = c.cred.perfil if gestionada else E.cartera_de(c.cred)
    partes = [f"<h4>Cuenta paper · perfil {_e(c.cred.perfil or 'defecto')} · cartera "
              f"{_e(cartera or 'sin declarar')}</h4>"]
    try:
        m = A.estado_mercado(c.reloj())
        cu = c.cuenta()
        pos = c.posiciones()
    except A.AlpacaError as e:
        return "".join(partes) + f"<p class='nota'>Alpaca no responde: {_e(c.cred.enmascarar(str(e)))[:200]}</p>"
    estado = ("abierto" + (f", cierra en {m['minutos_al_cierre']:.0f} min" if m["minutos_al_cierre"] is not None else "")
              if m["abierto"] else f"cerrado (abre {_e(m['proxima_apertura'])})")
    equity = float(cu.get("equity") or 0)
    partes.append(f"<p>Mercado de EE. UU.: <b>{estado}</b>. Valor de la cuenta (simulada) "
                  f"<b>{_num(equity)} {_e(cu.get('currency', 'USD'))}</b>, efectivo {_num(cu.get('cash'))} · "
                  f"cuenta {_e(A.enmascara_cuenta(cu.get('account_number')))}</p>")
    objetivo: dict[str, float] = {}
    if gestionada:
        partes.append(f"<p>Gestionada por el agente cada día: {_e(GESTIONADAS[cartera])}. Sus decisiones, en "
                      f"research/paper/decisiones_{cartera.lower()}.jsonl y obsidian/Carteras/{cartera}/.</p>")
    elif cartera:
        try:
            d = E.decision(cartera)
            if d:
                objetivo = {s: w for s, (_, w) in E.pesos_etf(d["pesos"], E.mapeo_de(cartera)).items()}
                partes.append(f"<p>Decisión espejada: cierre {_e(d['cierre'])}, pesos {_e(d['pesos'])}</p>")
        except (ValueError, OSError):
            pass
    filas = []
    simbolos = sorted({p["symbol"] for p in pos} | set(objetivo))
    por = {p["symbol"]: p for p in pos}
    for s in simbolos:
        p = por.get(s, {})
        mv = float(p.get("market_value") or 0)
        obj = f"{objetivo[s]:.1%}" if s in objetivo else "—"
        filas.append(f"<tr><td>{_e(s)}</td><td>{_e(p.get('qty', '0'))}</td><td>{_num(p.get('current_price'))}</td>"
                     f"<td>{_num(mv)}</td><td>{(mv / equity if equity else 0):.1%}</td><td>{obj}</td></tr>")
    if filas:
        partes.append("<table><thead><tr><th>ETF</th><th>participaciones</th><th>precio</th><th>valor</th>"
                      "<th>peso</th><th>objetivo</th></tr></thead><tbody>" + "".join(filas) + "</tbody></table>")
    else:
        partes.append("<p>Sin posiciones.</p>")
    r = E.resumen_ejecucion(registro, cartera)
    if gestionada:
        pass                                       # sin espejo: las ejecuciones van en el registro del gestor
    elif r["ejecuciones"]:
        partes.append(f"<p>Espejo vs teórico: {r['ejecuciones']} ejecuciones por {_num(r['valor_usd'])} $ · "
                      f"deslizamiento medio {_e(r['desliz_pb_vs_ref'])} pb frente al precio al enviar y "
                      f"{_e(r['desliz_pb_vs_cierre'])} pb frente al cierre del mes (el precio del paper teórico) · "
                      f"coste teórico supuesto {_e(r['coste_teorico_pb'])} pb por lado.</p>")
    else:
        partes.append("<p>Espejo vs teórico: aún sin ejecuciones apuntadas.</p>")
    return "".join(partes)


def seccion_alpaca(clientes: list[A.Cliente] | None = None, registro: list[dict] | None = None) -> str:
    """HTML de la sección. `clientes` y `registro` se inyectan en los tests; por defecto, todos los perfiles."""
    cab = ("<section id='alpaca'><h3>Alpaca paper (cuenta SIMULADA)</h3>"
           "<p class='nota'>Las 3 cuentas paper las gestiona el agente desde el 20-nov-2026 (C1 libre, M1 macro, A1 "
           "selección de acciones); B0/B1/B1′/D1 siguen solo en papel. Datos IEX (no todo el volumen). "
           "Nunca dinero real.</p>")
    try:
        if clientes is None:
            clientes = [c for c in (A.cliente(p) for p in A.perfiles() if p in GESTIONADAS) if c is not None]
            vistos, unicos = set(), []
            for c in clientes:
                if c.cred.perfil not in vistos:
                    vistos.add(c.cred.perfil)
                    unicos.append(c)
            clientes = unicos
        registro = E.leer_registro() if registro is None else registro
    except A.EndpointNoPermitido as e:
        return cab + f"<p class='nota'>{_e(str(e))}</p></section>"
    except Exception as e:   # la sección nunca tumba el panel
        return cab + f"<p class='nota'>Alpaca: error al leer la configuración ({_e(type(e).__name__)})</p></section>"
    if not clientes:
        return cab + "<p>Alpaca no configurado.</p></section>"
    cuerpo = []
    for c in clientes:
        try:
            cuerpo.append(_bloque_perfil(c, registro))
        except Exception as e:
            cuerpo.append(f"<p class='nota'>Alpaca ({_e(c.cred.perfil or 'defecto')}): "
                          f"{_e(c.cred.enmascarar(f'{type(e).__name__}: {e}'))[:200]}</p>")
    return cab + "".join(cuerpo) + "</section>"
