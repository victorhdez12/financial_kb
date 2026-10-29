"""Termómetro de recesión informativo en vivo (src/report/termometro_vivo.py): imprime la sección Markdown para una fecha
(hoy por defecto) y guarda research/int/termometro_vivo_ultimo.json. No toca el reporte semanal.
Uso: .venv/bin/python -m scripts.termometro_vivo [AAAA-MM-DD]
"""
from __future__ import annotations

import json
import sys
from datetime import date

from src.intl.procedencia import procedencia
from src.report import termometro_vivo as V
from src.warehouse import db

SALIDA = V.REPO / "research" / "int" / "termometro_vivo_ultimo.json"


def main(fecha: str | None = None) -> dict:
    fecha = fecha or date.today().isoformat()
    con = db.connect(read_only=True)
    try:
        res = V.termometro(con, fecha)
    finally:
        con.close()
    res = {"fecha_pedida": fecha, "procedencia": procedencia(exigir_limpio=False), **res}
    SALIDA.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(V.markdown(res))
    print(f"-> {SALIDA}")
    return res


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
