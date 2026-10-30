"""INT-11 v3 "hoy" (DESCRIPTIVO; docs/int/INT11_prerregistro_v3.md §8).

Motor Config.v3 estimado con TODAS las filas ≤ 2004; estado actual con ventanas MÓVILES de 12 meses (OCDE en vivo, PIB
per cápita con población Maddison) y PERTENENCIA SUAVE al régimen (σ 0,5 pp en la inflación, 1 pp en la brecha); abanico
de los 12 meses que siguen a la emisión. Cada abanico lleva el ACIERTO MEDIDO en la fase D de v3 (cobertura LOCO ≤ 2004
del país, del activo y del régimen de partida dominante), no el nominal. Aviso del umbral con TODOS los países a < 0,5 pp
del 3 % (o a < 1 pp de brecha 0). El registro en vivo NO se activa aquí (falta fijar la fuente de bolsa).

Uso: .venv/bin/python -m scripts.int11_v3_hoy [AAAA-MM-DD]   → research/int/int11_v3_hoy.{json,md}
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.int11_corrida import NUCLEO
from scripts.int11_v3_corrida import cargar_real_v3
from src.intl import data as D
from src.intl import escenarios as E
from src.intl.procedencia import procedencia
from src.report import escenarios_vivo as V

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/int11_v3_hoy.json"
RESULTADO = REPO / "research/int/int11_v3_resultado.json"
SEED = 20261105
REJILLA_Q = tuple(range(1, 100))
CERCA_INFL, CERCA_BRECHA = 0.005, 0.01


def _p(x):
    return f"{100 * x:.0f} %"


def acierto_medido(res: dict) -> dict:
    return {"activo": dict(zip(E.ACTIVOS, res["loco"]["S_activo"])), "regimen": res["cobertura_por_regimen_loco"],
            "pais": res["cobertura_por_pais_loco"], "global": res["loco"]["S5"], "puerta_D": res["puerta_D"]["pasa"],
            "cerca_umbral": res["loco"]["S5_cerca"]}


def pais_escenario(gen: E.Generador, c: str, e: dict, semilla: int) -> dict:
    w = E.pesos_estado(e["inflacion"], e["brecha"], gen.cfg.sigma_infl, gen.cfg.sigma_brecha)
    esc = gen.simular_suave(c, e["inflacion"], e["brecha"], horizonte=1, n_lotes=200, por_lote=100, semilla=semilla)
    R = esc.rent[:, 0, :]
    duro = gen.simular(c, e["codigo"], horizonte=1, n_lotes=200, por_lote=100, semilla=semilla)
    return {"pesos_regimen": dict(zip(E.REGIMENES, np.round(w, 4).tolist())),
            "regimen_dominante": E.REGIMENES[int(np.argmax(w))],
            "cuantiles_1_99": {a: np.nanpercentile(R[:, j], REJILLA_Q).round(5).tolist() for j, a in enumerate(esc.activos)},
            "p_caida_bolsa_20": esc.prob_caida("bolsa", -0.20, h=1), "p_inflacion_5": esc.prob_inflacion(0.05, h=1),
            "p_inflacion_5_regimen_duro": duro.prob_inflacion(0.05, h=1)["p"],
            "factor_dispersion": gen.escala_resumen["factor_pais"].get(c),
            "distancia_umbral_pp": round(100 * (e["inflacion"] - E.UMBRAL_INFL), 2),
            "cerca_umbral": bool(abs(e["inflacion"] - E.UMBRAL_INFL) < CERCA_INFL or abs(e["brecha"]) < CERCA_BRECHA)}


def emitir(fecha: str) -> dict:
    proc = procedencia()
    if not RESULTADO.exists():
        raise SystemExit("falta research/int/int11_v3_resultado.json (fase D): la salida v3 se etiqueta con su acierto")
    ac = acierto_medido(json.loads(RESULTADO.read_text()))
    con = D.connect()
    filas = cargar_real_v3(con)
    if filas["año"].max() > 2004:
        raise D.FactorCutoffError("filas > 2004")
    gen = E.Generador(E.Config.v3()).ajustar(filas)
    est = V.estado_actual_movil(con, fecha)
    paises = {}
    for i, c in enumerate(NUCLEO):
        e = est["paises"][c]
        if e.get("regimen") is None:
            paises[c] = {"estado": e, "aviso": "sin datos suficientes"}
            continue
        paises[c] = {"estado": e, **pais_escenario(gen, c, e, SEED + i)}
    return {"procedencia": proc, "version_motor": E.VERSION, "config": str(gen.cfg), "emision": est["emision"],
            "corte_datos": est["corte"], "ventana_objetivo": est["ventana_objetivo"], "kappa": gen.kappa,
            "kappa_en_borde": gen.kappa_en_borde, "acierto_medido_fase_D": ac, "paises": paises,
            "aviso": "DESCRIPTIVO. Motor v3 estimado SOLO con ≤ 2004 (JST, 14 países); estado OCDE en vivo (12 meses móviles,"
                     " PIB per cápita con población Maddison extrapolada) con pertenencia suave al régimen. Calibración "
                     "comprobada solo en desarrollo (contaminado); NO confirmada fuera de muestra. Rentabilidades reales en "
                     "moneda local. No es una recomendación."}


def _q(r: dict, a: str, p: int) -> float:
    return r["cuantiles_1_99"][a][p - 1]


def markdown(o: dict) -> str:
    ac = o["acierto_medido_fase_D"]
    v = o["ventana_objetivo"]
    filas, cerca = [], []
    for c, r in o["paises"].items():
        if "cuantiles_1_99" not in r:
            filas.append(f"| {c} | — | — | — | — | — | — |")
            continue
        e = r["estado"]
        dom = r["regimen_dominante"]
        acb = ac["regimen"].get(dom, {}).get("bolsa")
        pc, pi = r["p_caida_bolsa_20"], r["p_inflacion_5"]
        pesos = ", ".join(f"{k[:5]} {_p(x)}" for k, x in r["pesos_regimen"].items() if x >= 0.005)
        filas.append(
            f"| {c} | {pesos} (IPC a {e['mes_ipc'][:7]}: {100 * e['inflacion']:.2f} %; brecha pc {100 * e['brecha']:+.1f} %) | "
            f"{_p(_q(r, 'bolsa', 5))} … {_p(_q(r, 'bolsa', 50))} … {_p(_q(r, 'bolsa', 95))} "
            f"(acertó {_p(ac['pais'][c]['bolsa'])} país / {_p(acb) if acb is not None else '—'} régimen) | "
            f"{_p(_q(r, 'bonos', 5))} … {_p(_q(r, 'bonos', 95))} | {_p(_q(r, 'vivienda', 5))} … {_p(_q(r, 'vivienda', 95))} | "
            f"{_p(pc['p'])} [{_p(max(pc['ic90'][0], 0))}-{_p(pc['ic90'][1])}] | "
            f"{_p(pi['p'])} [{_p(max(pi['ic90'][0], 0))}-{_p(min(pi['ic90'][1], 1))}] |")
        if r["cerca_umbral"]:
            cerca.append(f"{c} (inflación {r['distancia_umbral_pp']:+.2f} pp del 3 %, brecha {100 * e['brecha']:+.1f} %: "
                         f"P(inflación > 5 %) {_p(pi['p'])} suave frente a {_p(r['p_inflacion_5_regimen_duro'])} con la "
                         f"regla dura)")
    act = ", ".join(f"{a} {_p(x)}" for a, x in ac["activo"].items())
    aviso_umbral = ("; ".join(cerca) if cerca else "ninguno")
    return f"""---
documento: INT-11 v3 "hoy" — abanicos de los próximos 12 meses por país (DESCRIPTIVO)
procedencia: {o['procedencia']}
emision: {o['emision']} (datos en vivo hasta {o['corte_datos']})
ventana: {v['desde']} → {v['hasta']}
aviso: {o['aviso']}
---

# Escenarios para {v['desde'][:7]} … {v['hasta'][:7]} (motor v3 estimado con ≤ 2004)

**Cuánto acertaron estos abanicos en el pasado** (fase D de v3, cada país predicho sin sus propios datos, 1876-2004):
el abanico "del 90 %" contuvo lo realizado el **{100 * ac['global']:.1f} %** de las veces ({act}); cerca del umbral del
3 %, el {100 * ac['cerca_umbral']:.1f} %. Puerta de desarrollo: {'pasó' if ac['puerta_D'] else 'NO pasó'}. Fuera de
muestra todavía **no está comprobado** (confirmación futura K1).

**Aviso del umbral (frontera del 3 % y brecha 0).** Países a menos de 0,5 pp del 3 % de inflación o a menos de 1 pp de
brecha 0: {aviso_umbral}. En v3 su abanico es una MEZCLA de los regímenes vecinos (pesos en la columna "estado"), en
lugar de saltar de uno a otro por décimas: por eso su P(inflación > 5 %) queda entre los dos extremos. Aun así, un dato
nuevo de IPC puede mover bastante esas cifras.

| país | estado: pesos de régimen (12 meses móviles) | bolsa real: p5 … p50 … p95 (acierto medido del p5-p95) | bonos p5 … p95 | vivienda p5 … p95 | P(bolsa ≤ −20 %) [IC 90 % parámetros] | P(inflación > 5 %) [IC] |
|---|---|---|---|---|---|---|
{chr(10).join(filas)}

Cómo leerlo: "p5 … p95" es el abanico nominal del 90 % de la rentabilidad real de los 12 meses de la ventana; entre
paréntesis, con qué frecuencia un abanico así contuvo lo realizado en el pasado para ese país y para su régimen de
partida dominante (si es < 90 %, el abanico es más estrecho de lo que dice). El IC entre corchetes es solo la duda
sobre los parámetros. κ = {o['kappa']:.3g} (en el borde: {o['kappa_en_borde']}). Letras, oro y la rejilla completa de
percentiles en research/int/int11_v3_hoy.json.
"""


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fecha = args[0] if args else str(pd.Timestamp.today().date())
    o = emitir(fecha)
    md = markdown(o)
    SALIDA.write_text(json.dumps(o, ensure_ascii=False, indent=1, default=float))
    SALIDA.with_suffix(".md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
