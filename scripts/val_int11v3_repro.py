"""Validador INT-11 v3 (31-oct, local). Reproduce la fase D (≤ 2004) con el código ACTUAL (tras 77b3bd1, cambio posterior
a la congelación) y las semillas congeladas, y compara la puerta D con research/int/int11_v3_resultado.json.
No es una segunda corrida: mismas semillas, mismo panel; solo comprueba que el cambio no toca la predictiva.
Uso: .venv/bin/python -m scripts.val_int11v3_repro
"""
import json
import time
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
from scripts import int11_v3_corrida as C                                    # noqa: E402
from scripts.int11_corrida import estructura                                 # noqa: E402
from src.intl import data as D                                               # noqa: E402
from src.intl import escenarios as E                                         # noqa: E402
from src.intl.procedencia import procedencia                                 # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "research/int/val_int11v3/repro.json"


def main() -> None:
    proc = procedencia()                                                     # árbol limpio ANTES de correr
    t0 = time.time()
    oficial = json.loads(C.SALIDA.read_text())
    med = json.loads(C.POT1.read_text())["medicion"]
    med2 = json.loads(C.POT2.read_text())["medicion_v2"]
    sd_b = json.loads(C.POT3.read_text())["medicion_brecha"]["sd_robusta"]
    f = C.cargar_real_v3(D.connect())
    años, existe, ok = estructura(f)
    if f["año"].max() > 2004:
        raise D.FactorCutoffError("filas > 2004")
    ev = {d: C.V.evaluar_suave(f, d, E.Config.v3(), 200, 100, C.SEED, corte=C.CORTE) for d in ("loco", "temporal")}
    st = {d: C.V.estadisticos(v) for d, v in ev.items()}
    nb = C.nulo(med, med2, sd_b, años, existe, ok, C.R_NULO, np.random.default_rng(C.SEED))
    g = C.puerta_d(st["loco"], nb["loco"])
    rt = lambda x: json.loads(json.dumps(x, default=float))                  # noqa: E731
    iguales = {"loco": rt(st["loco"]) == oficial["loco"], "temporal": rt(st["temporal"]) == oficial["temporal"],
               "puerta_D": rt(g) == oficial["puerta_D"]}
    o = {"procedencia": proc, "iguales": iguales, "puerta_D": g, "puerta_D_oficial": oficial["puerta_D"],
         "segundos": round(time.time() - t0)}
    OUT.write_text(json.dumps(o, ensure_ascii=False, indent=1, default=float))
    print(json.dumps({"iguales": iguales, "segundos": o["segundos"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
