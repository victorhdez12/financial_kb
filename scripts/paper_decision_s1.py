"""Decisión mensual de S1 «rotación de sectores por régimen» (docs/factors/S1_rotacion_sectorial_spec.md §6; src/paper/s1.py).
Uso: .venv/bin/python -m scripts.paper_decision_s1 [--cierre AAAA-MM-DD | --auto] [--registrar]
- Sin --registrar es un ensayo: imprime la decisión y no escribe nada.
- --auto: el cierre es SIEMPRE el último fin de mes pasado; nunca otro.
- Con --registrar exige las reglas de B1 (scripts/paper_decision.validar: último fin de mes pasado, una vez por mes,
  sin saltos), el árbol limpio, que el cierre sea ≥ PRIMER_CIERRE (sin historia retroactiva) y que exista
  research/paper/S1_ACTIVO (S1 NO pasó el desarrollo: lo crea el usuario solo si decide llevarla como observación).
  Añade la línea a research/paper/decisiones_s1.jsonl (propio, inmutable), commitea y sube, como B1′.
- NO está enganchado a launchd (scripts/paper_mensual.sh no lo llama).
Códigos de salida: 0 hecho (o ya registrado / anterior al arranque con --auto), 3 ya registrado, 4 mes no válido,
5 árbol sucio, 6 sin research/paper/S1_ACTIVO, 8 sin cuadrante de la diaria del cierre, 1 otros.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import asdict

import pandas as pd

from scripts.paper_decision import MesNoValido, YaRegistrado, cierre_objetivo, git, validar
from src.paper import s1 as S

PRIMER_CIERRE = pd.Timestamp("2026-11-30")     # primer cierre tras la spec congelada (19-nov-2026)


def registrados() -> list[str]:
    return [d["cierre"] for d in S.leer_registro()]


def validar_s1(cierre: pd.Timestamp, hoy: pd.Timestamp, previos: list[str]) -> None:
    validar(cierre, hoy, previos)
    if cierre < PRIMER_CIERRE:
        raise MesNoValido(f"S1 arranca en el cierre {PRIMER_CIERRE.date()} (sin historia retroactiva), no {cierre.date()}")


def main(argv=None, *, con=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--cierre", help="fin de mes de la decisión (por defecto, el último fin de mes pasado)")
    g.add_argument("--auto", action="store_true")
    ap.add_argument("--registrar", action="store_true")
    a = ap.parse_args(argv)
    hoy = pd.Timestamp(dt.date.today())
    cierre = cierre_objetivo(hoy) if (a.auto or not a.cierre) else pd.Timestamp(a.cierre)
    if a.registrar:
        if a.auto and cierre < PRIMER_CIERRE:
            print(f"S1 aún no arranca: primer cierre registrable {PRIMER_CIERRE.date()} (nada que hacer)")
            return 0
        try:
            validar_s1(cierre, hoy, registrados())
        except YaRegistrado as e:
            print(e)
            return 0 if a.auto else 3
        except MesNoValido as e:
            print(e)
            return 4
        if not S.ACTIVO_S1.exists():
            print("no existe research/paper/S1_ACTIVO: S1 solo ensaya (no pasó el desarrollo; decide el usuario)")
            return 6
        if git("status", "--porcelain"):
            print("árbol de git sucio: commitea antes de registrar")
            return 5
    propia = con is None
    if propia:
        from src.warehouse import db
        con = db.connect(read_only=True)
    try:
        d = S.decidir(cierre, S.fila_diaria(con, cierre), S.leer_registro())
    except S.SinCuadrante as e:
        print(f"S1: {e}")
        return 8
    finally:
        if propia:
            con.close()
    print(json.dumps(asdict(d), indent=1, ensure_ascii=False))
    if not a.registrar:
        return 0
    S.registrar(d, {"registrado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                    "git_head": git("rev-parse", "HEAD")})
    git("add", str(S.LOG.relative_to(S.REPO)))
    git("commit", "-q", "-m", f"Paper trading S1: decision for {cierre.date()} ({d.vigente}, opera={d.opera})\n\n"
                              "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    git("push", "-q", "origin", "main")
    print("registrada y subida")
    return 0


if __name__ == "__main__":
    sys.exit(main())
