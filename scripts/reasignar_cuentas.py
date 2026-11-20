"""Reasignación DECLARADA de cuentas Alpaca PAPER (decisión del usuario 20-nov-2026; mismo mecanismo que el 19-nov:
B0→D1 en …X9F9). Añade filas `reasignacion` a ~/financial_archive/alpaca/espejo.jsonl (FIN_ALPACA_DIR), fuera de git:
- …4JGR: B1 → C1 (B1 sigue solo en papel);
- …X9F9: D1 → A1 (D1 sigue decidiendo y registrando en papel cada día, sin cuenta).
Efecto: src/broker/espejo.puede_ejecutar deja de enviar órdenes de B1/D1 a esas cuentas, y src/paper/c1.comprobar_cuenta
deja operar a C1/A1 ignorando las órdenes del espejo ANTERIORES a la reasignación (las heredan).
La huella de cada cuenta se toma de las filas ya existentes del espejo (no hacen falta claves ni red).

Por defecto EN SECO (dice qué escribiría). `--escribir` añade las filas (idempotente: si la última reasignación de esa
cuenta ya es a esa cartera, no hace nada). Hacerlo DESPUÉS de cambiar el plist de D1 (sin `--ejecutar`): una orden del
espejo de D1 posterior a la reasignación volvería a bloquear A1.
Uso: .venv/bin/python -m scripts.reasignar_cuentas [--escribir]
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

from src.broker import espejo as E

REASIGNACIONES = [
    {"cuenta": "…4JGR", "de": "B1", "a": "C1",
     "motivo": "decisión del usuario 20-nov: B1 sigue solo en papel; la cuenta pasa a C1 (gestor libre)"},
    {"cuenta": "…X9F9", "de": "D1", "a": "A1",
     "motivo": "decisión del usuario 20-nov: D1 sigue solo en papel; la cuenta pasa a A1 (selección de acciones)"},
]


def plan(registro: list[dict], reasignaciones: list[dict] | None = None) -> list[dict]:
    """Filas a añadir (pura). Lanza LookupError si una cuenta no aparece en el espejo (no se puede saber su huella)."""
    out = []
    for x in reasignaciones or REASIGNACIONES:
        huellas = {r.get("cuenta_huella") for r in registro if r.get("cuenta") == x["cuenta"] and r.get("cuenta_huella")}
        if len(huellas) != 1:
            raise LookupError(f"cuenta {x['cuenta']}: {len(huellas)} huellas en espejo.jsonl (hace falta exactamente 1)")
        h = huellas.pop()
        ult = [r for r in registro if r.get("tipo") == "reasignacion" and r.get("cuenta_huella") == h]
        if ult and ult[-1].get("a") == x["a"]:
            continue
        out.append({"tipo": "reasignacion", "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                    "cuenta_huella": h, "cuenta": x["cuenta"], "de": x["de"], "a": x["a"], "motivo": x["motivo"]})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Reasignación declarada de cuentas paper (en seco por defecto)")
    ap.add_argument("--escribir", action="store_true", help="añade las filas a espejo.jsonl")
    a = ap.parse_args(argv)
    try:
        filas = plan(E.leer_registro())
    except LookupError as e:
        print(f"ERROR: {e}")
        return 1
    if not filas:
        print("nada que hacer: las reasignaciones ya están declaradas")
        return 0
    for f in filas:
        print(f"{'ESCRIBE' if a.escribir else 'EN SECO'}: {f['cuenta']} {f['de']} → {f['a']} (huella {f['cuenta_huella']})")
        if a.escribir:
            E.apunta(f)
    if not a.escribir:
        print("en seco: nada escrito (usa --escribir)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
