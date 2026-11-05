"""P-K1v §3: registro prospectivo en vivo, ANUAL. Para el último año t con el 4.º trimestre del crédito BIS publicado,
P(inicio de crisis bancaria en t + 1) por país con los modelos congelados L (B1) y K (B1 + Δ5 crédito/PIB). No se muestra
en el reporte.

Uso: .venv/bin/python -m scripts.k1_vivo [--registrar]   (registra solo t ≥ 2026, una vez por año; commitea y sube)
Lee crisisjst (JST, hasta 2020) SOLO para B1, declarado en el prerregistro §2.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.k1_corrida import SALIDA as MODELOS, sha
from src.intl import data as D
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
LOG = REPO / "research/int/k1_vivo.jsonl"
PRIMER_T = 2026
INICIOS_DESDE_2021: dict[str, list[int]] = {}   # §2: ninguno declarado hasta 2025
# Último año para el que se han revisado (y declarado arriba) los inicios de crisis desde 2021. B1 y "en riesgo" de t
# dependen de los inicios ≤ t: no se registra t > INICIOS_REVISADOS_HASTA sin declararlo antes (Validador 2026-11-05).
INICIOS_REVISADOS_HASTA = 2025


def puede_registrar(ts, revisado_hasta: int = INICIOS_REVISADOS_HASTA) -> tuple[int, str]:
    """(código, motivo): 0 = sí; 10 = aún no toca (t mezclados o t < PRIMER_T); 6 = inicios de t sin revisar."""
    ts = sorted({int(x) for x in ts if x == x})
    if len(ts) != 1 or ts[0] < PRIMER_T:
        return 10, f"t = {ts} (se exige un único t ≥ {PRIMER_T})"
    if ts[0] > revisado_hasta:
        return 6, (f"t = {ts[0]}: inicios de crisis revisados solo hasta {revisado_hasta}; declara los de "
                   f"{revisado_hasta + 1}-{ts[0]} en INICIOS_DESDE_2021 y sube INICIOS_REVISADOS_HASTA")
    return 0, ""


def git(*a) -> str:
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True, check=True).stdout.strip()


def q(con, sid: str) -> pd.Series:
    d = con.execute("select date, value from obs_latest where series_id = ? and value is not null order by date",
                    [sid]).df()
    return pd.Series(d.value.astype(float).values, index=pd.to_datetime(d.date))


def calcular(con, paises: list[str]) -> pd.DataFrame:
    filas = []
    for c in paises:
        cr = q(con, f"jst_{c.lower()}_crisisjst")
        ini = sorted({*cr[cr == 1].index.year.tolist(), *INICIOS_DESDE_2021.get(c, [])})
        s = q(con, f"bis_tc_{D.ISO2[c]}_pb_m")
        s4 = s[s.index.month == 10]
        s4.index = s4.index.year
        if s4.empty:
            filas.append({"pais": c, "sin_dato": True})
            continue
        t = int(s4.index.max())
        x = s4.get(t) - s4.get(t - 5) if (t - 5) in s4.index else np.nan
        prev = [a for a in ini if a <= t]
        en_riesgo = not any(t - k in ini for k in range(0, 5))
        filas.append({"pais": c, "t": t, "x": float(x), "ultimo_inicio": prev[-1] if prev else None,
                      "B1": float(np.log1p(t - prev[-1])) if prev else np.nan, "en_riesgo": en_riesgo})
    return pd.DataFrame(filas)


def main() -> int:
    from scripts.int6_corrida import NUCLEO
    j = json.loads(MODELOS.read_text())
    mod = j["modelos"]
    if sha(mod) != j["modelos_sha256"]:
        print("modelos alterados")
        return 1
    con = db.connect(read_only=True)
    try:
        d = calcular(con, NUCLEO)
    finally:
        con.close()
    bL, bK = np.array(mod["L"]["b"]), np.array(mod["K"]["b"])
    sig = lambda z: 1 / (1 + np.exp(-z))  # noqa: E731
    d["p_L"] = sig(bL[0] + bL[1] * d.B1)
    d["p_K"] = sig(bK[0] + bK[1] * d.B1 + bK[2] * d.x)
    print("K1v (registro, no es señal ni se muestra): P(inicio de crisis bancaria en t + 1)")
    print(d.round(3).to_string(index=False))
    if "--registrar" not in sys.argv:
        return 0
    rc, motivo = puede_registrar(d.t)
    if rc:
        print(f"no se registra: {motivo}")
        return 0 if rc == 10 else rc
    t = int(d.t.min())
    hechos = {(r["pais"], r["t"]) for r in map(json.loads, LOG.read_text().splitlines())} if LOG.exists() else set()
    if any((p, t) in hechos for p in d.pais):
        print(f"t = {t} ya registrado")
        return 0
    if git("status", "--porcelain"):
        print("árbol de git sucio")
        return 5
    ahora, head = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), git("rev-parse", "HEAD")
    with LOG.open("a") as f:
        for r in d.to_dict("records"):
            f.write(json.dumps({**{k: (None if isinstance(v, float) and not np.isfinite(v) else v)
                                   for k, v in r.items()}, "modelos_sha256": j["modelos_sha256"],
                                "registrado": ahora, "git_head": head}, default=str) + "\n")
    git("add", str(LOG.relative_to(REPO)))
    git("commit", "-q", "-m", f"K1v live registry: t = {t}\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    git("push", "-q", "origin", "main")
    print("registrado y subido")
    return 0


if __name__ == "__main__":
    sys.exit(main())
