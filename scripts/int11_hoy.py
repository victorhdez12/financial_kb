"""INT-11 "hoy" (DESCRIPTIVO; docs/int/INT11_prerregistro_v1.md §8): motor estimado con TODAS las filas ≤ 2004 y estado
actual de cada país con datos OCDE en vivo (src/report/escenarios_vivo). Abanicos a 1 año por activo, P(bolsa ≤ −20 %),
P(inflación > 5 %), con IC de parámetros. No evalúa nada: no hay resultados futuros.

Uso: .venv/bin/python -m scripts.int11_hoy [AAAA-MM-DD]   → research/int/int11_hoy.{json,md}
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.int11_corrida import NUCLEO, SEED, cargar_real
from src.intl import data as D
from src.intl import escenarios as E
from src.intl.procedencia import procedencia
from src.report import escenarios_vivo as V

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/int11_hoy.json"


def _p(x):
    return f"{100 * x:.0f} %"


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    fecha = sys.argv[1] if len(sys.argv) > 1 else str(pd.Timestamp.today().date())
    proc = procedencia()
    con = D.connect()
    filas = cargar_real(con)
    gen = E.Generador(E.Config()).ajustar(filas)
    est = V.estado_actual(con, fecha)
    res = {}
    for i, c in enumerate(NUCLEO):
        e = est["paises"][c]
        if e["regimen"] is None:
            res[c] = {"estado": e, "aviso": "sin datos suficientes"}
            continue
        esc = gen.simular(c, e["codigo"], horizonte=1, n_lotes=200, por_lote=100, semilla=SEED + i)
        ab = esc.abanico(percentiles=(5, 10, 50, 90, 95), medida="anual")
        res[c] = {"estado": e, "abanico_1a": {r["activo"]: {k: round(float(r[k]), 4) for k in ("p5", "p10", "p50",
                                                                                                "p90", "p95")}
                                               for _, r in ab.iterrows()},
                  "p_caida_bolsa_20": esc.prob_caida("bolsa", -0.20, h=1),
                  "p_inflacion_5": esc.prob_inflacion(0.05, h=1)}
    o = {"procedencia": proc, "fecha": fecha, "corte_datos_vivo": est["corte"], "aviso":
         "DESCRIPTIVO. Motor estimado SOLO con datos ≤ 2004 (JST, 14 países); el estado actual sale de datos OCDE en "
         "vivo (PIB total en lugar de per cápita). Rentabilidades reales en moneda local. No es una recomendación.",
         "kappa": gen.kappa, "paises": res}
    SALIDA.write_text(json.dumps(o, ensure_ascii=False, indent=1, default=float))
    filas_md = []
    for c, r in res.items():
        if "abanico_1a" not in r:
            filas_md.append(f"| {c} | — | — | — | — | — | — |")
            continue
        e, ab = r["estado"], r["abanico_1a"]
        b = ab["bolsa"]
        pc, pi = r["p_caida_bolsa_20"], r["p_inflacion_5"]
        filas_md.append(
            f"| {c} | {e['regimen']} ({e['año']}; infl. {100 * e['inflacion']:.1f} %, brecha "
            f"{100 * e['brecha_pib_total']:+.1f} %) | {_p(b['p5'])} … {_p(b['p50'])} … {_p(b['p95'])} | "
            f"{_p(ab['bonos']['p5'])} … {_p(ab['bonos']['p95'])} | {_p(ab['vivienda']['p5'])} … "
            f"{_p(ab['vivienda']['p95'])} | {_p(pc['p'])} [{_p(max(pc['ic90'][0], 0))}-{_p(pc['ic90'][1])}] | "
            f"{_p(pi['p'])} [{_p(max(pi['ic90'][0], 0))}-{_p(min(pi['ic90'][1], 1))}] |")
    md = f"""---
documento: INT-11 "hoy" — escenarios a 1 año por país (DESCRIPTIVO)
procedencia: {proc}
fecha: {fecha} (datos en vivo hasta {est['corte']})
aviso: {o['aviso']}
---

# Escenarios a 1 año desde el estado actual (estimado con datos ≤ 2004)

| país | estado operable (año; inflación, brecha) | bolsa real: p5 … p50 … p95 | bonos p5 … p95 | vivienda p5 … p95 | P(bolsa ≤ −20 %) [IC 90 % parámetros] | P(inflación > 5 %) [IC] |
|---|---|---|---|---|---|---|
{chr(10).join(filas_md)}

Cómo leerlo: "p5 … p95" es el abanico del 90 %: en 9 de cada 10 escenarios la rentabilidad real del próximo año cae
dentro. El IC entre corchetes es solo la duda sobre los parámetros (no la mala suerte, que ya está en la probabilidad).
Letras y oro en research/int/int11_hoy.json.
"""
    SALIDA.with_suffix(".md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
