"""Congela las referencias ≤ 2004 del termómetro en vivo (src/report/termometro_vivo.py) y los parámetros finales de la
puerta SIN redondear. Solo datos de desarrollo (≤ 2004: `load_dev`/`load_dev_curado` vía scripts/termometro_puerta.cargar).

- Parámetros finales: mismo código que el bloque `final` de scripts/termometro_puerta_v2.py (modelo con todas las filas,
  rectas con TODO, recalibración con todas las filas ≤ 2003, percentiles recalibrados de los meses 1960-2004). Se
  comprueba que, redondeados a 4 decimales como `_r`, son exactamente los de research/int/termometro_puerta_v2_corr.json;
  si no, no se escribe nada. No se reajusta ni se decide nada nuevo: solo se evita el error de redondeo (≤ 5e-4).
- Referencias: `termometro_vivo.referencias` con esos parámetros (distribución 1960-2004 de cada indicador por país y
  centro de las contribuciones al logit de T2).
Exige el árbol limpio. Salida: research/int/termometro_referencias.json.
Uso: .venv/bin/python -m scripts.termometro_referencias
"""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from scripts.int4_corrida import NUCLEO, _r
from scripts.termometro_puerta import GIROS, REPO, TODOS, cargar
from scripts.termometro_puerta_v2 import TODO, probs, referencia_cal
from src.intl import int4 as M
from src.intl import termometro as T
from src.intl.procedencia import procedencia
from src.report import termometro_vivo as V
from src.warehouse import db

SALIDA = REPO / "research" / "int" / "termometro_referencias.json"


def final_sin_redondeo(a, extra, pm_, bis, pib) -> tuple[dict, dict, dict]:
    """El `final` de termometro_puerta_v2.main, sin `_r`. Devuelve también `mens` y `tr` (traducción final)."""
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    años_pais = {c: set(a.xs(c, level=0)["rgdpmad"].dropna().index.astype(int)) for c in TODOS}
    primer = {c: min(v) for c, v in años_pais.items()}
    pan = M.paneles(a, extra, NUCLEO, TODOS, None)
    mens = T.mensuales(pm_, bis, pib, NUCLEO, TODOS)
    rej = mens["C1"].index
    base, b = {}, {}
    for giro, cols in GIROS.items():
        f = (M.obj_entrada if giro == "T1" else M.obj_salida)(rec, años_pais, NUCLEO, 1, 1871, True)
        B1 = M.liston(f, giro, rec, primer, pan)
        Xa = M.matriz(f, pan, cols)
        b[giro] = T.congelar(B1, Xa, f.y.to_numpy(float))
        base[giro] = (f, B1, Xa)
    rl = T.rectas(pan, mens, NUCLEO, TODOS, TODO, TODO)
    tr = T.traducir(mens, rl, TODOS)
    cal = {}
    for giro, cols in GIROS.items():
        f, B1, Xa = base[giro]
        pa, pm, ok = probs(f, B1, Xa, b[giro], tr, cols)
        cal[giro] = T.calibrar(pa[ok], pm[ok])
    fq = {c: T.fechado_trimestral(pib[c]) for c in TODOS}
    final = {"modelo": {g: [float(x) for x in b[g]] for g in GIROS}, "cal": cal, "rectas": rl,
             "percentiles_referencia": referencia_cal(tr, pib, fq, b, cal, rej)}
    return final, mens, tr


def _json(v):
    """Como `_r` pero sin redondear (NaN → None, tuplas → listas, tipos de numpy → nativos)."""
    if isinstance(v, dict):
        return {a: _json(x) for a, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_json(x) for x in v]
    if isinstance(v, (float, np.floating)):
        return None if not np.isfinite(v) else float(v)
    if isinstance(v, (np.integer, np.bool_)):
        return v.item()
    return v


def main() -> None:
    proc = procedencia()
    a, extra, pm_, bis, pib = cargar()
    final, mens, tr = final_sin_redondeo(a, extra, pm_, bis, pib)
    pub = json.loads(V.CONGELADO.read_text())["final"]
    if json.dumps(_r(final), sort_keys=True) != json.dumps(pub, sort_keys=True):
        raise SystemExit(f"los parámetros recalculados no redondean a los de {V.CONGELADO.name}: no se escribe nada")
    if set(V.TODOS) != set(TODOS) or V.NUCLEO != NUCLEO:
        raise SystemExit("países distintos entre el termómetro en vivo y la puerta")
    ver = json.loads(V.CONGELADO.read_text())["veredicto"]["paises_con_probabilidad"]["T2"]
    par = {"b_T2": np.array(final["modelo"]["T2"], float), "cal_T2": tuple(final["cal"]["T2"]),
           "rectas": final["rectas"], "paises_T2": [c for c in NUCLEO if c in ver and c not in T.SIN_BOLSA]}
    refs = V.referencias(mens, tr, pib, par)
    out = {"procedencia": proc,
           "descripcion": "Referencias ≤ 2004 del termómetro en vivo y parámetros finales de la puerta sin redondear "
                          "(scripts/termometro_referencias.py). Solo datos ≤ 2004 (load_dev, load_dev_curado).",
           "puerta": str(V.CONGELADO.relative_to(REPO)),
           "comprobacion": "final_sin_redondeo redondeado a 4 decimales (_r) = final de la puerta",
           "final_sin_redondeo": _json(final), "referencias": _json(refs)}
    txt = json.dumps(out, indent=1, ensure_ascii=False)
    # listas de números en una sola línea (las distribuciones tienen hasta 540 valores)
    txt = re.sub(r"\[\s*([-+0-9.eE,\s]+?)\s*\]", lambda m: "[" + ", ".join(x.strip() for x in m.group(1).split(",")) + "]",
                 txt)
    SALIDA.write_text(txt + "\n")
    print(f"centro T2 {np.round(refs['centro_T2'], 4)} ({refs['meses_centro']} meses); "
          f"percentiles T2 {final['percentiles_referencia']['T2']}\n-> {SALIDA}")


if __name__ == "__main__":
    main()
