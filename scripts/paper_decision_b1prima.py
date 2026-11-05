"""Decisión mensual de B1′ EN PARALELO a B1 (docs/factors/B1prima_spec.md §4, docs/factors/B1prima_implementacion.md).
Uso: .venv/bin/python -m scripts.paper_decision_b1prima [--cierre AAAA-MM-DD | --auto] [--registrar]
- Sin --registrar es un ensayo: imprime la decisión (y la de B1 del mismo cierre, si está registrada) y no escribe nada.
- --auto: el cierre es SIEMPRE el último fin de mes pasado; nunca otro.
- Con --registrar exige, además de las reglas de B1 (scripts/paper_decision.validar: último fin de mes pasado, una vez
  por mes, sin saltos) y el árbol limpio: que exista research/paper/ACTIVO (como B1) y que el cierre sea ≥ 2026-11-30
  (primer cierre después de la aprobación del 5-nov-2026; sin historia retroactiva). Añade la línea a
  research/paper/decisiones_b1prima.jsonl (fichero propio, inmutable), commitea y sube.
Códigos de salida: 0 hecho (o ya registrado con --auto), 3 ya registrado, 4 mes no válido, 5 árbol sucio,
6 sin research/paper/ACTIVO, 1 otros.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import asdict

import pandas as pd

from scripts.paper_decision import MesNoValido, YaRegistrado, cierre_objetivo, git, validar
from src.paper import b1prima as B

PRIMER_CIERRE = pd.Timestamp("2026-11-30")


def registrados() -> list[str]:
    if not B.LOG.exists():
        return []
    return [json.loads(x)["cierre"] for x in B.LOG.read_text().splitlines() if x.strip()]


def validar_b1p(cierre: pd.Timestamp, hoy: pd.Timestamp, previos: list[str]) -> None:
    validar(cierre, hoy, previos)
    if cierre < PRIMER_CIERRE:
        raise MesNoValido(f"B1′ arranca en el cierre {PRIMER_CIERRE.date()} (sin historia retroactiva), no {cierre.date()}")


def b1_del_mes(cierre: pd.Timestamp) -> dict | None:
    from src.paper import live as L
    if not L.LOG.exists():
        return None
    for x in L.LOG.read_text().splitlines():
        if x.strip() and json.loads(x)["cierre"] == str(cierre.date()):
            d = json.loads(x)
            return {"sigma_hat": d["sigma_hat"], "rv_b1_bruta": d["rv_b1_bruta"], "b1": d["b1"]}
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--cierre", help="fin de mes de la decisión (por defecto, el último fin de mes pasado)")
    g.add_argument("--auto", action="store_true")
    ap.add_argument("--registrar", action="store_true")
    a = ap.parse_args(argv)
    hoy = pd.Timestamp(dt.date.today())
    cierre = cierre_objetivo(hoy) if (a.auto or not a.cierre) else pd.Timestamp(a.cierre)
    if a.registrar:
        try:
            validar_b1p(cierre, hoy, registrados())
        except YaRegistrado as e:
            print(e)
            return 0 if a.auto else 3
        except MesNoValido as e:
            print(e)
            return 4
        if not B.ACTIVO.exists():
            print("no existe research/paper/ACTIVO: B1′ solo ensaya (como B1)")
            return 6
        if git("status", "--porcelain"):
            print("árbol de git sucio: commitea antes de registrar")
            return 5
    d = B.decidir(cierre)
    print(json.dumps(asdict(d), indent=1, ensure_ascii=False))
    if not a.registrar:
        print(json.dumps({"B1_registrada_mismo_cierre": b1_del_mes(cierre)}, indent=1, ensure_ascii=False))
        return 0
    B.registrar(d, {"registrado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                    "git_head": git("rev-parse", "HEAD")})
    git("add", str(B.LOG.relative_to(B.REPO)))
    git("commit", "-q", "-m", f"Paper trading B1prime: decision for {cierre.date()} (RV {d.b1prima['rv']})\n\n"
                              "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    git("push", "-q", "origin", "main")
    print("registrada y subida")
    return 0


if __name__ == "__main__":
    sys.exit(main())
