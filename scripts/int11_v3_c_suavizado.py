"""INT-11 v3: experimento SINTÉTICO que fija la constante de ensanchamiento `c_suavizado` (docs/int/INT11_v3_diseno.md §2.3).

Regla (fijada antes de correrlo; src/intl/int11v3.py): c* = menor c de la rejilla 0-12 (paso 0,25) con cobertura del
p5-p95 ≥ 0,90 en n = 20 Y n = 34, t con ν = 4,5, 20.000 réplicas por n (error MC ± 0,002). Sensibilidades (informativas,
no cambian c*): ν = 3,5 / 6 / normal y la cobertura de c* en n = 65 y 150. Ningún dato real.

Uso: .venv/bin/python -m scripts.int11_v3_c_suavizado   (árbol limpio; escribe research/int/int11_v3_c_suavizado.json)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from src.intl import int11v3 as V
from src.intl.procedencia import procedencia

SALIDA = Path(__file__).resolve().parents[1] / "research/int/int11_v3_c_suavizado.json"


def main() -> None:
    prueba = "--prueba" in sys.argv
    proc = {"prueba": True} if prueba else procedencia()
    R = 1000 if prueba else 20000
    t0 = time.time()
    base = V.derivar_c(R=R)
    print("c* =", base["c"], flush=True)
    sens = {}
    cs = [0.0, 4.0, base["c"] or 12.0, 6.0, 8.0]
    for nu in (3.5, 6.0, np.inf):
        sens[f"nu={nu}"] = {str(n): dict(zip(map(str, cs), np.round(V.cobertura_iid(n, cs, nu, R // 2, 7 + n), 4)
                                             .tolist())) for n in V.N_C}
        print(nu, sens[f"nu={nu}"], flush=True)
    grandes = {str(n): dict(zip(map(str, cs), np.round(V.cobertura_iid(n, cs, V.NU_C, R // 4, 9 + n), 4).tolist()))
               for n in (65, 150)}
    out = {"procedencia": proc, "regla": "menor c con cobertura p5-p95 ≥ 0,90 en n = 20 y n = 34 (t ν = 4,5)",
           "base": base, "sensibilidad_nu": sens, "n_grandes": grandes, "segundos": round(time.time() - t0)}
    if not prueba:
        SALIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float))
    print(json.dumps({k: v for k, v in out.items() if k != "base"}, ensure_ascii=False, default=float))
    print(base)


if __name__ == "__main__":
    main()
