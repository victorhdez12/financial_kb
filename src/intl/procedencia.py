"""Procedencia de cada ejecución con puerta (Validador INT-1/INT-2, 27-oct): commit, árbol limpio y hora UTC en la salida,
para que el orden "fijar y después correr" se pueda comprobar. Con `exigir_limpio`, se niega a correr con cambios sin
commitear."""
from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def procedencia(exigir_limpio: bool = True) -> dict:
    git = lambda *a: subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True, check=True).stdout.strip()  # noqa: E731
    sucio = git("status", "--porcelain")
    if exigir_limpio and sucio:
        raise SystemExit("árbol de git sucio: commitea el código antes de una ejecución con puerta\n" + sucio)
    return {"commit": git("rev-parse", "HEAD"), "arbol_limpio": not sucio,
            "hora_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
