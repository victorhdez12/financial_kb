"""P-E1 §11: registro prospectivo en vivo. Cada mes, P(entrada en recesión en 12 meses) por país con los modelos
congelados L (curva) y A (curva + actividad). NO se muestra en el reporte; solo se registra para la evaluación futura
(≥ 12 episodios nuevos).

Uso: .venv/bin/python -m scripts.e1_vivo [--cierre AAAA-MM-DD | --auto] [--registrar]
- Sin --registrar: ensayo (imprime, no escribe).
- --registrar: árbol limpio, cierre = último fin de mes pasado, ≥ 2026-11-30 (posterior a la congelación), no registrado
  antes; añade una línea por país a research/int/e1_vivo.jsonl, commitea y sube.
Salida: 0 hecho / ya registrado / aún no toca (--auto); 3 ya registrado; 4 mes no válido; 5 árbol sucio; 1 otros.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.intl import e1 as E

REPO = Path(__file__).resolve().parents[1]
MODELOS = REPO / "research/int/e1_modelos.json"
LOG = REPO / "research/int/e1_vivo.jsonl"


def git(*a) -> str:
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True, check=True).stdout.strip()


def registrados() -> set:
    if not LOG.exists():
        return set()
    return {json.loads(x)["origen"] for x in LOG.read_text().splitlines() if x.strip()}


def main() -> int:
    from src.report import termometro_vivo as V
    from src.warehouse import db
    ap = argparse.ArgumentParser()
    ap.add_argument("--cierre")
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--registrar", action="store_true")
    a = ap.parse_args()
    hoy = pd.Timestamp(dt.date.today())
    ultimo = V.fin_de_mes(hoy - pd.Timedelta(days=1)) if hoy == V.fin_de_mes(hoy) else V.fin_de_mes(hoy)
    cierre = V.fin_de_mes(a.cierre) if a.cierre else ultimo
    j = json.loads(MODELOS.read_text())
    mod = j["modelos"]
    if E.sha(mod) != j["modelos_sha256"]:
        print("modelos alterados: sha256 no coincide")
        return 1
    if a.registrar:
        if cierre != ultimo or cierre < E.PRIMER_ORIGEN:
            print(f"{cierre.date()}: no se registra (solo el último fin de mes pasado y ≥ {E.PRIMER_ORIGEN.date()})")
            return 0 if a.auto else 4
        if str(cierre.date()) in registrados():
            print(f"{cierre.date()} ya registrado")
            return 0 if a.auto else 3
        if git("status", "--porcelain"):
            print("árbol de git sucio: commitea antes de registrar")
            return 5
    con = db.connect(read_only=True)
    try:
        rej = pd.date_range("1950-01-31", cierre, freq="ME")
        r = E.rasgos(lambda sid: V._serie(con, sid, cierre), rej, euro_bce=True)
    finally:
        con.close()
    d = E.prediccion(mod, r[r.fecha == cierre])
    faltan = sorted(set(E.PAISES) - set(d.pais))
    print(f"E1 cierre {cierre.date()} (registro, no es señal ni se muestra): {len(d)} países; sin dato: {faltan}")
    for x in d.itertuples():
        print(f"  {x.pais}: p_L {x.p_L:.3f}  p_A {x.p_A:.3f}")
    if not a.registrar:
        return 0
    ahora = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    head = git("rev-parse", "HEAD")
    with LOG.open("a") as f:
        for x in d.itertuples():
            f.write(json.dumps({"origen": str(cierre.date()), "pais": x.pais, "p_L": round(x.p_L, 6),
                                "p_A": round(x.p_A, 6), **{c: round(getattr(x, c), 6) for c in E.COLS["A"]},
                                "modelos_sha256": j["modelos_sha256"], "registrado": ahora, "git_head": head}) + "\n")
        for c in faltan:
            f.write(json.dumps({"origen": str(cierre.date()), "pais": c, "sin_dato": True, "registrado": ahora,
                                "git_head": head}) + "\n")
    git("add", str(LOG.relative_to(REPO)))
    git("commit", "-q", "-m", f"E1 live registry: origin {cierre.date()}\n\n"
                              "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    git("push", "-q", "origin", "main")
    print("registrado y subido")
    return 0


if __name__ == "__main__":
    sys.exit(main())
