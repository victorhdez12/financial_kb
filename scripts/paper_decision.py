"""Decisión mensual del paper trading (docs/factors/paper_trading.md).
Uso: .venv/bin/python -m scripts.paper_decision [--cierre AAAA-MM-DD] [--registrar]
Sin --registrar es un ensayo: imprime la decisión y no escribe nada. Con --registrar exige el árbol limpio, añade la
línea a research/paper/decisiones.jsonl, commitea y sube (la hora del commit en el remoto fecha la decisión).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from dataclasses import asdict

import pandas as pd

from src.paper import live as L

REPO = L.REPO


def git(*a) -> str:
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True, check=True).stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cierre", help="fin de mes de la decisión (por defecto, el último fin de mes pasado)")
    ap.add_argument("--registrar", action="store_true")
    a = ap.parse_args()
    hoy = pd.Timestamp(dt.date.today())
    cierre = pd.Timestamp(a.cierre) if a.cierre else (hoy - pd.offsets.MonthBegin(1)) - pd.Timedelta(days=1)
    cierre = cierre + pd.offsets.MonthEnd(0)
    if cierre >= hoy:
        raise SystemExit(f"el cierre {cierre.date()} aún no ha pasado")
    if a.registrar and git("status", "--porcelain"):
        raise SystemExit("árbol de git sucio: commitea antes de registrar")
    if a.registrar and L.LOG.exists() and any(json.loads(x)["cierre"] == str(cierre.date())
                                               for x in L.LOG.read_text().splitlines() if x.strip()):
        raise SystemExit(f"ya hay una decisión registrada para {cierre.date()} (una por mes, inmutable)")
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


if __name__ == "__main__":
    main()
