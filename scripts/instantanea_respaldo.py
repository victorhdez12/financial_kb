"""Respaldo de la instantánea ≤ 2004 (research/int/instantanea_dev_2004.json; docs/int/OCDE_deriva_umbrales.md, §3).

Dos copias con el mismo sha256 (el del manifiesto):
- archivo: $FIN_DATA_ROOT/intl/snapshots/dev_le2004_20261026.parquet (solo lectura; la que se lee normalmente);
- respaldo: research/int/snapshots/dev_le2004_20261026.parquet.xz (en git, y por tanto en origin).
La instantánea NO se puede regenerar (se reconstruyó invirtiendo una caché del 26-oct frente al warehouse del 4-nov);
por eso el respaldo vive en el repo.

Run:
  .venv/bin/python scripts/instantanea_respaldo.py verificar    # estado de las dos copias (sale con 1 si alguna falla)
  .venv/bin/python scripts/instantanea_respaldo.py restaurar    # reescribe el archivo desde el respaldo si falta/corrupto
  .venv/bin/python scripts/instantanea_respaldo.py respaldar    # crea el respaldo desde el archivo válido (una vez)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.intl import data as D  # noqa: E402


def main(argv: list[str]) -> int:
    orden = argv[1] if len(argv) > 1 else "verificar"
    if orden == "verificar":
        est = D.verificar_instantanea()
        for k, (ok, det) in est.items():
            print(f"{k:9s} {'OK ' if ok else 'MAL'} {det}")
        return 0 if all(ok for ok, _ in est.values()) else 1
    if orden == "restaurar":
        print(D.restaurar_instantanea())
        return 0
    if orden == "respaldar":
        print(D.respaldar_instantanea())
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
