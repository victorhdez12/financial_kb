"""Registro de verificación a corto plazo (método v1, docs/verif/metodo_v1.md). Idempotente; segundos.

    .venv/bin/python scripts/verif_registrar.py               # diario: descarga vintages recientes, emite lo que toque,
                                                              # puntúa y escribe ~/financial_archive/verif/resumen_v1.json
    .venv/bin/python scripts/verif_registrar.py --retro       # rehace el retrospectivo (backtest 2015-hoy, NO en vivo)
    .venv/bin/python scripts/verif_registrar.py --sin-descarga  # sin red: solo puntúa (no emite)

Sin descarga del día no se emite nada: sin ella no se sabe si el dato ya ha salido.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.verif import datos as D  # noqa: E402
from src.verif import registro as R  # noqa: E402


def main(argv=None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--retro", action="store_true", help="rehacer el retrospectivo")
    ap.add_argument("--sin-descarga", action="store_true")
    a = ap.parse_args(argv)
    if not a.sin_descarga:
        try:
            D.refrescar()
        except (Exception, SystemExit) as e:  # noqa: BLE001
            print(f"AVISO verif: sin descarga de FRED ({type(e).__name__}); no se emite hoy")
    V = D.Vintages()
    if a.retro or not R.RUTA_RETRO.exists():
        regs = R.backtest(V)
        R.guardar_retro(regs)
        print(f"verif: retrospectivo -> {R.RUTA_RETRO} ({len(regs)} predicciones, {R.ETIQ_RETRO})")
    estados = []
    if D.cache_de_hoy():
        estados = R.emitir_vivo(V)
        for e in estados:
            print(f"verif: {e['variable']:8s} {e.get('periodo', '')[:7]:8s} {e['estado']}"
                  + (f" -> {e['punto']} [{e['inf80']}; {e['sup80']}]" if e["estado"] == "EMITIDA" else "")
                  + (f" (desde {e['emision_prevista']})" if e["estado"].startswith("esperando") else ""))
    else:
        # sin emitir, al menos las fechas previstas
        estados = [{"variable": v, "estado": "sin descarga hoy"} for v in R.M.VARIABLES]
    res = R.escribir_resumen(V, estados)
    pv = sum(f.get("n", 0) for f in res["vivo"]["resumen"])
    print(f"verif: resumen -> {R.RUTA_RESUMEN} (vivo puntuadas {pv}, retro {len(res['retro']['registros'])})")
    _commit_registro()
    return 0


def _commit_registro() -> None:
    """Commitea solo research/verif/*.jsonl si cambiaron (registro append-only), para que el árbol quede limpio
    (la emisión de INT-11 aborta con árbol sucio). Solo en main y solo en el repo real (no con FIN_VERIF_REGISTRO)."""
    import os
    import subprocess
    if os.environ.get("FIN_VERIF_REGISTRO"):
        return
    repo = str(R.db.REPO)
    git = lambda *a: subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True)  # noqa: E731
    if git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "main":
        return
    rutas = [str(x.relative_to(R.db.REPO)) for x in (R.RUTA_VIVO, R.RUTA_RETRO) if x.exists()]
    if not rutas or not git("status", "--porcelain", "--", *rutas).stdout.strip():
        return
    git("add", "--", *rutas)
    c = git("commit", "-m", "verif: registro a corto plazo (automático)", "--", *rutas)
    if c.returncode == 0:
        git("push", "-q", "origin", "main")
        print("verif: registro commiteado")
    else:
        print(f"AVISO verif: commit fallido: {c.stderr.strip()[:200]}")


if __name__ == "__main__":
    raise SystemExit(main())
