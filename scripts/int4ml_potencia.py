"""P-DEV-INT4-ML: potencia ANTES de construir nada. ¿Qué mejora de AUC de un modelo de ML frente al logit de INT-4 se
podría detectar? Solo usa recuentos de eventos (research/int/int4_potencia.json, int4b_potencia.json) y las AUC del logit
YA medidas en la corrida única de INT-4 (AUC estratificada por país: T1 0,732, T2 0,770). Ningún modelo de ML se ajusta.
La correlación entre las AUC de dos modelos sobre los mismos datos con los mismos indicadores es alta y desconocida:
rejilla r = 0,5 / 0,7 / 0,8 / 0,9. Familia: 2 candidatos × 2 giros = 4 contrastes (Holm-4, z ≈ 3,30).
Uso: .venv/bin/python -m scripts.int4ml_potencia [--prueba]
"""
from __future__ import annotations

import json
import sys

from scipy.stats import norm

from scripts.int4_potencia import REPO, Z1, mde_auc
from src.intl.procedencia import procedencia

Z4 = norm.ppf(1 - 0.05 / 8) + norm.ppf(0.80)
RS = (0.5, 0.7, 0.8, 0.9)


def efectivos(filas, eventos, años, de):
    """Positivos efectivos = el mayor de eventos/DE y años distintos (como INT-4); negativos = no eventos / DE."""
    return max(eventos / de, años), (filas - eventos) / de


def main() -> None:
    proc = procedencia(exigir_limpio="--prueba" not in sys.argv)
    p4 = json.loads((REPO / "research/int/int4_potencia.json").read_text())
    p4b = json.loads((REPO / "research/int/int4b_potencia.json").read_text())
    t1 = p4["anual_con_datos"]["1871_2004_sin_guerras"]["5_sin_vivienda"]["recesion_h1"]
    t2 = p4b["objetivos"]["1871_2004_sin_guerras"]["salida_recesion_h1"]
    giros = {"T1": (t1, 0.732), "T2": (t2, 0.770)}
    res = {"procedencia": proc, "z_1": round(Z1, 3), "z_holm4": round(Z4, 3), "giros": {}}
    for g, (v, a0) in giros.items():
        n1, n0 = efectivos(v["filas_en_riesgo"], v["eventos"], v["años_distintos_con_evento"], v["efecto_diseño"])
        res["giros"][g] = {"auc_logit": a0, "pos_ef": round(n1, 1), "neg_ef": round(n0, 1),
                           "mde": {f"r={r}": {"1_contraste": _r(mde_auc(a0, n1, n0, Z1, r)),
                                              "holm_4": _r(mde_auc(a0, n1, n0, Z4, r))} for r in RS}}
    if "--prueba" not in sys.argv:
        (REPO / "research/int/int4ml_potencia.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res["giros"], indent=1))


def _r(x):
    return None if x is None else round(x, 3)


if __name__ == "__main__":
    main()
