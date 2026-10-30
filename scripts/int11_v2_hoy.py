"""INT-11 v2 "hoy" (DESCRIPTIVO; docs/int/INT11_prerregistro_v2.md §7) y registro mensual en vivo (§8;
docs/int/INT11_registro_vivo.md).

Motor Config.v2 estimado con TODAS las filas ≤ 2004; estado actual con ventanas MÓVILES de 12 meses (OCDE en vivo, PIB per
cápita con población Maddison); abanico de los 12 meses que siguen a la emisión. Cada abanico lleva el ACIERTO MEDIDO en
la fase D (cobertura LOCO ≤ 2004 del activo, del régimen de partida y del país), no el nominal.

Uso: .venv/bin/python -m scripts.int11_v2_hoy [AAAA-MM-DD]              → research/int/int11_v2_hoy.{json,md}
     .venv/bin/python -m scripts.int11_v2_hoy [AAAA-MM-DD] --registro   → SOLO research/int/int11_vivo/AAAA-MM.json
                                                                           (+ índice con sha256; nunca sobrescribe)
     ... --registro --vintage                                            → fecha atrasada: solo países con vintages
Registro (v0.2, arreglos de la validación v2, hallazgo 3; src/report/registro_vivo.py): con --registro NO se reescribe
la salida "hoy" (la 2.ª emisión ya no aborta por árbol sucio), el árbol puede tener cambios solo dentro de
research/int/int11_vivo, la fecha debe ser hoy ± 3 días (o --vintage) y se guarda la huella de las entradas.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.int11_corrida import NUCLEO, cargar_real
from src.intl import data as D
from src.intl import escenarios as E
from src.intl.procedencia import procedencia
from src.report import escenarios_vivo as V
from src.report import registro_vivo as RV

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/int11_v2_hoy.json"
RESULTADO = REPO / "research/int/int11_v2_resultado.json"
VIVO = REPO / "research/int/int11_vivo"
SEED = 20261101
REJILLA_Q = tuple(range(1, 100))                    # percentiles 1..99 guardados en el registro (PIT y coberturas)


def _p(x):
    return f"{100 * x:.0f} %"


def acierto_medido(res: dict) -> dict:
    """Coberturas p5-p95 MEDIDAS en la fase D (LOCO ≤ 2004): por activo, por régimen de partida × activo, por país."""
    return {"activo": res["loco"]["S_activo"], "regimen": res["cobertura_por_regimen_loco"],
            "pais": res["cobertura_por_pais_loco"], "global": res["loco"]["S5"], "puerta_D": res["puerta_D"]["pasa"]}


def pais_escenario(gen: E.Generador, c: str, e: dict, semilla: int) -> dict:
    esc = gen.simular(c, e["codigo"], horizonte=1, n_lotes=200, por_lote=100, semilla=semilla)
    R = esc.rent[:, 0, :]
    q = {a: np.nanpercentile(R[:, j], REJILLA_Q).round(5).tolist() for j, a in enumerate(esc.activos)}
    return {"cuantiles_1_99": q, "p_caida_bolsa_20": esc.prob_caida("bolsa", -0.20, h=1),
            "p_inflacion_5": esc.prob_inflacion(0.05, h=1), "factor_dispersion": gen.escala_resumen["factor_pais"].get(c)}


def emitir(fecha: str, registro: bool = False, vintage: bool = False) -> dict:
    if registro:
        RV.comprobar_fecha(fecha, vintage=vintage)
    proc = RV.procedencia_registro(VIVO) if registro else procedencia()
    if not RESULTADO.exists():
        raise SystemExit("falta research/int/int11_v2_resultado.json (fase D): la salida v2 se etiqueta con su acierto")
    ac = acierto_medido(json.loads(RESULTADO.read_text()))
    con = D.connect()
    filas = cargar_real(con)
    if filas["año"].max() > 2004:
        raise D.FactorCutoffError("filas > 2004")
    gen = E.Generador(E.Config.v2()).ajustar(filas)
    est = V.estado_actual_movil(con, fecha, vintage=vintage, entradas=registro)
    entradas = RV.huella_entradas(est.pop("_series")) if registro else None
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
            **({"entradas": entradas, "vintage": vintage} if registro else {}),
            "aviso": "DESCRIPTIVO. Motor v2 estimado SOLO con ≤ 2004 (JST, 14 países); estado OCDE en vivo (12 meses móviles,"
                     " PIB per cápita con población Maddison extrapolada). Calibración comprobada solo en desarrollo "
                     "(contaminado); NO confirmada fuera de muestra. Rentabilidades reales en moneda local. No es una "
                     "recomendación."}


def _q(r: dict, a: str, p: int) -> float:
    return r["cuantiles_1_99"][a][p - 1]


def markdown(o: dict) -> str:
    ac = o["acierto_medido_fase_D"]
    v = o["ventana_objetivo"]
    filas = []
    for c, r in o["paises"].items():
        if "cuantiles_1_99" not in r:
            filas.append(f"| {c} | — | — | — | — | — | — |")
            continue
        e = r["estado"]
        reg = e["regimen"]
        acb = ac["regimen"].get(reg, {}).get("bolsa")
        pc, pi = r["p_caida_bolsa_20"], r["p_inflacion_5"]
        filas.append(
            f"| {c} | {reg} (IPC a {e['mes_ipc'][:7]}: {100 * e['inflacion']:.1f} %; brecha pc {100 * e['brecha']:+.1f} %) | "
            f"{_p(_q(r, 'bolsa', 5))} … {_p(_q(r, 'bolsa', 50))} … {_p(_q(r, 'bolsa', 95))} "
            f"(acertó {_p(ac['pais'][c]['bolsa'])} país / {_p(acb) if acb is not None else '—'} régimen) | "
            f"{_p(_q(r, 'bonos', 5))} … {_p(_q(r, 'bonos', 95))} | {_p(_q(r, 'vivienda', 5))} … {_p(_q(r, 'vivienda', 95))} | "
            f"{_p(pc['p'])} [{_p(max(pc['ic90'][0], 0))}-{_p(pc['ic90'][1])}] | "
            f"{_p(pi['p'])} [{_p(max(pi['ic90'][0], 0))}-{_p(min(pi['ic90'][1], 1))}] |")
    act = ", ".join(f"{a} {_p(x)}" for a, x in ac["activo"].items())
    return f"""---
documento: INT-11 v2 "hoy" — abanicos de los próximos 12 meses por país (DESCRIPTIVO)
procedencia: {o['procedencia']}
emision: {o['emision']} (datos en vivo hasta {o['corte_datos']})
ventana: {v['desde']} → {v['hasta']}
aviso: {o['aviso']}
---

# Escenarios para {v['desde'][:7]} … {v['hasta'][:7]} (motor v2 estimado con ≤ 2004)

**Cuánto acertaron estos abanicos en el pasado** (fase D, cada país predicho sin sus propios datos, 1876-2004): el
abanico "del 90 %" contuvo lo realizado el **{_p(ac['global'])}** de las veces ({act}). Puerta de desarrollo:
{'pasó' if ac['puerta_D'] else 'NO pasó'}. Fuera de muestra todavía **no está comprobado** (confirmación futura K1).

| país | estado (12 meses móviles) | bolsa real: p5 … p50 … p95 (acierto medido del p5-p95) | bonos p5 … p95 | vivienda p5 … p95 | P(bolsa ≤ −20 %) [IC 90 % parámetros] | P(inflación > 5 %) [IC] |
|---|---|---|---|---|---|---|
{chr(10).join(filas)}

Cómo leerlo: "p5 … p95" es el abanico nominal del 90 % de la rentabilidad real de los 12 meses de la ventana; entre
paréntesis, con qué frecuencia un abanico así contuvo lo realizado en el pasado para ese país y para ese régimen de
partida (si es < 90 %, el abanico es más estrecho de lo que dice). El IC entre corchetes es solo la duda sobre los
parámetros. κ = {o['kappa']:.3g} (en el borde: {o['kappa_en_borde']}). Letras, oro y la rejilla completa de percentiles en
research/int/int11_v2_hoy.json.
"""


def registrar(o: dict, carpeta: Path = VIVO) -> Path:
    """Guarda la emisión del mes (inmutable): carpeta/AAAA-MM.json + línea en indice.csv (src/report/registro_vivo)."""
    return RV.registrar(o, carpeta)


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fecha = args[0] if args else str(pd.Timestamp.today().date())
    registro = "--registro" in sys.argv
    o = emitir(fecha, registro=registro, vintage="--vintage" in sys.argv)
    md = markdown(o)
    if registro:                     # solo el registro: no ensucia el árbol con la salida "hoy"
        print("registro:", registrar(o))
    else:
        SALIDA.write_text(json.dumps(o, ensure_ascii=False, indent=1, default=float))
        SALIDA.with_suffix(".md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
