"""Decisión mensual del paper trading (docs/factors/paper_trading.md).
Uso: .venv/bin/python -m scripts.paper_decision [--cierre AAAA-MM-DD | --auto] [--registrar]
- Sin --registrar es un ensayo: imprime la decisión y no escribe nada.
- --auto (lo usa launchd): el cierre es SIEMPRE el último fin de mes pasado; nunca otro.
- Con --registrar exige: árbol limpio, cierre ya pasado, que sea el último fin de mes pasado, que no esté registrado y
  que el siguiente cierre de la serie sea el inmediatamente posterior al último registrado (sin saltos ni retrocesos).
  Añade la línea a research/paper/decisiones.jsonl, commitea y sube (la hora del commit en el remoto fecha la decisión).
Códigos de salida: 0 hecho (o ya registrado con --auto), 3 ya registrado, 4 mes no válido, 5 árbol sucio, 1 otros.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from dataclasses import asdict

import pandas as pd

from src.paper import live as L

REPO = L.REPO


class MesNoValido(RuntimeError):
    pass


class YaRegistrado(RuntimeError):
    pass


def git(*a) -> str:
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True, check=True).stdout.strip()


def cierre_objetivo(hoy: pd.Timestamp) -> pd.Timestamp:
    """Último fin de mes ya pasado respecto a `hoy` (el 3-nov-2026 → 2026-10-31; el 31-oct-2026 → 2026-09-30)."""
    return (hoy.normalize().replace(day=1) - pd.Timedelta(days=1)).normalize()


def registrados() -> list[str]:
    if not L.LOG.exists():
        return []
    return [json.loads(x)["cierre"] for x in L.LOG.read_text().splitlines() if x.strip()]


def validar(cierre: pd.Timestamp, hoy: pd.Timestamp, previos: list[str]) -> None:
    """Reglas para registrar: nunca el mes equivocado, nunca dos veces el mismo mes."""
    if cierre != cierre + pd.offsets.MonthEnd(0):
        raise MesNoValido(f"{cierre.date()} no es fin de mes")
    if cierre != cierre_objetivo(hoy):
        raise MesNoValido(f"solo se registra el último fin de mes pasado ({cierre_objetivo(hoy).date()}), no {cierre.date()}")
    if str(cierre.date()) in previos:
        raise YaRegistrado(f"ya hay una decisión registrada para {cierre.date()} (una por mes, inmutable)")
    if previos:
        esperado = pd.Timestamp(max(previos)) + pd.offsets.MonthEnd(1)
        if cierre != esperado:
            raise MesNoValido(f"el siguiente cierre registrable es {esperado.date()}, no {cierre.date()} (sin saltos)")


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--cierre", help="fin de mes de la decisión (por defecto, el último fin de mes pasado)")
    g.add_argument("--auto", action="store_true")
    ap.add_argument("--registrar", action="store_true")
    a = ap.parse_args()
    hoy = pd.Timestamp(dt.date.today())
    cierre = cierre_objetivo(hoy) if (a.auto or not a.cierre) else pd.Timestamp(a.cierre)
    if a.registrar:
        try:
            validar(cierre, hoy, registrados())
        except YaRegistrado as e:
            print(e)
            return 0 if a.auto else 3
        except MesNoValido as e:
            print(e)
            return 4
        if git("status", "--porcelain"):
            print("árbol de git sucio: commitea antes de registrar")
            return 5
    d = L.decidir(cierre)
    print(json.dumps(asdict(d), indent=1, ensure_ascii=False))
    if a.registrar:
        L.registrar(d, {"registrado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                        "git_head": git("rev-parse", "HEAD")})
        git("add", str(L.LOG.relative_to(REPO)))
        git("commit", "-q", "-m", f"Paper trading: decision for {cierre.date()} (B1 RV {d.b1['rv']})\n\n"
                                  "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
        git("push", "-q", "origin", "main")
        print("registrada y subida")
    return 0


if __name__ == "__main__":
    sys.exit(main())
