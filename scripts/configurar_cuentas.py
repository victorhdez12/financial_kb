"""Configuración de las cuentas Alpaca PAPER según el mandato de cada cartera (20-nov-2026), vía
`PATCH /v2/account/configurations` (solo paper: el cliente de src/broker/alpaca.py se niega al endpoint real).

| perfil | cuenta | no_shorting | max_margin_multiplier | max_options_trading_level |
|---|---|---|---|---|
| C1 | …4JGR | true | 1 | 2 (opciones compradas; la guardia de C1 impide venderlas para abrir) |
| A1 | …X9F9 | true | 1 | 0 (desactivadas: A1 es selección de acciones pura) |
| M1 | …ZFJX | — ya configurada el 19-nov (sin margen, sin cortos, nivel 2): no se toca |

Por defecto EN SECO y SIN RED: imprime lo que enviaría. `--leer` consulta (GET) la configuración actual de cada
cuenta y la diferencia; `--aplicar` envía el PATCH. Antes de tocar nada comprueba que el número de cuenta del perfil
acaba como se espera (las claves se renombran a mano: un perfil mal puesto configuraría la cuenta equivocada).
Nunca envía órdenes. Uso: .venv/bin/python -m scripts.configurar_cuentas [--leer | --aplicar] [--perfil C1|A1]
"""
from __future__ import annotations

import argparse
import sys

from src.broker import alpaca as A
from src.broker import c1_guardia as G

RUTA = "/v2/account/configurations"
OBJETIVO = {
    "C1": {"cuenta": "4JGR", "config": {"no_shorting": True, "max_margin_multiplier": "1",
                                        "max_options_trading_level": 2}},
    "A1": {"cuenta": "X9F9", "config": {"no_shorting": True, "max_margin_multiplier": "1",
                                        "max_options_trading_level": 0}},
}


def diferencias(actual: dict, objetivo: dict) -> dict:
    return {k: v for k, v in objetivo.items() if str(actual.get(k)).lower() != str(v).lower()}


def comprobar_cuenta(c: A.Cliente, esperada: str) -> str | None:
    n = str(c.cuenta().get("account_number") or "")
    if not n.endswith(esperada):
        return f"el perfil {c.cred.perfil} es la cuenta {A.enmascara_cuenta(n)}, no …{esperada}: no se toca"
    return None


def configurar(c: A.Cliente, perfil: str, *, aplicar: bool) -> dict:
    G.comprobar_cliente(c)              # solo paper-api
    o = OBJETIVO[perfil]
    motivo = comprobar_cuenta(c, o["cuenta"])
    if motivo:
        return {"perfil": perfil, "error": motivo}
    actual = c._pide("GET", c.base, RUTA)
    dif = diferencias(actual, o["config"])
    out = {"perfil": perfil, "actual": {k: actual.get(k) for k in o["config"]}, "cambios": dif}
    if aplicar and dif:
        nuevo = c._pide("PATCH", c.base, RUTA, cuerpo=dif)
        out["despues"] = {k: nuevo.get(k) for k in o["config"]}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Configura las cuentas paper de C1 y A1 (en seco por defecto)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--leer", action="store_true", help="GET de la configuración actual (sin cambiar nada)")
    g.add_argument("--aplicar", action="store_true", help="envía el PATCH a la cuenta PAPER")
    ap.add_argument("--perfil", choices=sorted(OBJETIVO), action="append")
    a = ap.parse_args(argv)
    perfiles = a.perfil or sorted(OBJETIVO)
    if not (a.leer or a.aplicar):
        for p in perfiles:
            print(f"EN SECO {p} (…{OBJETIVO[p]['cuenta']}): PATCH {RUTA} {OBJETIVO[p]['config']}")
        print("nada enviado (sin red). --leer para ver la configuración actual, --aplicar para cambiarla")
        return 0
    rc = 0
    for p in perfiles:
        try:
            c = A.cliente(p)
        except A.EndpointNoPermitido as e:
            print(f"ERROR: {e}")
            return 1
        if c is None:
            print(f"{p}: sin claves ALPACA_API_KEY_ID_{p} (renómbralas primero)")
            rc = 7
            continue
        try:
            r = configurar(c, p, aplicar=a.aplicar)
        except A.AlpacaError as e:
            print(f"{p}: ERROR Alpaca: {c.cred.enmascarar(str(e))}")
            rc = 1
            continue
        if r.get("error"):
            print(f"{p}: {r['error']}")
            rc = 9
            continue
        print(f"{p}: actual {r['actual']} · cambios {r['cambios'] or 'ninguno'}"
              + (f" · después {r['despues']}" if "despues" in r else ""))
    return rc


if __name__ == "__main__":
    sys.exit(main())
