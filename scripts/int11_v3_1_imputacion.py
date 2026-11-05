"""INT-11 v3.1: efecto MEDIDO de la imputación condicionada (PMM) frente a la independiente de v3
(docs/int/INT11_v3_1_imputacion.md). Cambio de ingeniería declarado (decisión V2 de docs/int/INT11_v4_correlaciones_v0.md
§6): NO es una puerta y NO se usa para elegir nada (los parámetros de la PMM están fijados a priori en escenarios.py).

Partes (todo ≤ 2004, load_dev; nada ≥ 2005 leído):
  A. Correlación (log) de los sorteos a 1 año del motor v3 y v3.1, mismos países, regímenes de partida y semillas que
     `D_motor_v3` de research/int/int11_v4_potencia.json (comprueba además que v3 reproduce aquellas cifras), frente a
     las filas crudas con los dos datos.
  B. Cómo se emparejan los huecos en los datos reales (nivel del donante: celda / mismo s_prev / todas / independiente).
  C. INFORMATIVO, declarado: la fase D de v3 (LOCO + temporal, predictiva suave, semillas congeladas) recalculada con
     v3.1, junto a la oficial de v3 (research/int/int11_v3_resultado.json) y v3 recalculada con el código actual (debe
     salir idéntica: v3 sigue bit a bit). La "puerta" con la banda nula OFICIAL de v3 se muestra solo como referencia: no
     es una puerta nueva (los datos ≤ 2004 ya están usados para desarrollar).

Uso: .venv/bin/python -m scripts.int11_v3_1_imputacion          (árbol limpio; escribe research/int/int11_v3_1_imputacion.json)
     .venv/bin/python -m scripts.int11_v3_1_imputacion --rapido (sin la parte C; no escribe)
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

from scripts import int11_v3_corrida as C
from scripts.int11_corrida import cargar_real
from src.intl import data as D
from src.intl import escenarios as E
from src.intl import int11v3 as V
from src.intl.procedencia import procedencia

REPO = Path(__file__).resolve().parents[1]
SALIDA = REPO / "research/int/int11_v3_1_imputacion.json"
POT4 = REPO / "research/int/int11_v4_potencia.json"
SEED_D = 20261105                       # = scripts/int11_v4_potencia.SEED (parte D_motor_v3)
PARES = (("bolsa", "bonos"), ("bolsa", "vivienda"), ("bonos", "oro"), ("bolsa", "oro"), ("bonos", "vivienda"))
PAISES_D = ("USA", "DEU", "GBR", "ESP")


def _corr(x, y) -> float:
    return float(np.corrcoef(x, y)[0, 1]) if len(x) >= 5 else float("nan")


def corr_sorteos(gen: E.Generador, R: np.ndarray) -> dict:
    """Correlación (log) de cada par de PARES en una matriz de sorteos R (P, A) de rentabilidades simples."""
    acts = list(gen.cfg.activos)
    L = np.log1p(R)
    out = {}
    for a, b in PARES:
        ia, ib = acts.index(a), acts.index(b)
        ok = np.isfinite(L[:, ia]) & np.isfinite(L[:, ib])
        out[f"{a}-{b}"] = round(_corr(L[ok, ia], L[ok, ib]), 3)
    return out


def correlacion_motor(f14) -> dict:
    out = {}
    for nombre, cfg in (("v3", E.Config.v3()), ("v3_1", E.Config.v3_1()),
                        ("v3_1_sin_suavizado", E.Config.v3_1(c_suavizado=0.0))):
        gen = E.Generador(cfg).ajustar(f14)
        res = {}
        for c in PAISES_D:
            for s0 in (0, 1):
                esc = gen.simular(c, s0, horizonte=1, n_lotes=100, por_lote=100, semilla=SEED_D + s0)
                res[f"{c}|{E.REGIMENES[s0]}"] = corr_sorteos(gen, esc.rent[:, 0, :])
        out[nombre] = res
    cel = {}
    for s0 in (0, 1):
        d = {}
        for a, b in PARES:
            h = f14[(f14["s_prev"] == s0)][[a, b]].dropna()
            d[f"{a}-{b}"] = {"rho": round(_corr(np.log1p(h[a]), np.log1p(h[b])), 3), "n": int(len(h))}
        cel[E.REGIMENES[s0]] = d
    out["filas_por_s_prev_crudas"] = cel
    ref = json.loads(POT4.read_text())["D_motor_v3"]["v3"]
    out["v3_reproduce_D_motor_v3"] = out["v3"] == ref
    return out


def niveles_pmm(f14) -> dict:
    gen = E.Generador(E.Config.v3_1()).ajustar(f14)
    out = {}
    for v, nombre in enumerate(gen.vars):
        tot = [gen.pmm_nivel[(c, v)] for c in gen.celdas if (c, v) in gen.pmm_nivel]
        if not tot:
            continue
        s = np.sum(tot, 0)
        out[nombre] = {"filas_sin_dato": int((~np.isfinite(gen.V[:, v])).sum()),
                       **dict(zip(("celda", "mismo_s_prev", "todas", "independiente"),
                                  np.round(s / max(s.sum(), 1), 4).tolist()))}
    return out


def fase_d_informativa(f) -> dict:
    oficial = json.loads(C.SALIDA.read_text())
    out = {"aviso": "INFORMATIVO, no es una puerta: ≤ 2004 ya usado para desarrollar (contaminado); misma semilla y "
                    "pliegues que la fase D de v3; banda nula = la OFICIAL de v3 (no recalculada)."}
    for nombre, cfg in (("v3_recalculada", E.Config.v3()), ("v3_1", E.Config.v3_1())):
        ev = {d: V.evaluar_suave(f, d, cfg, 200, 100, C.SEED, corte=C.CORTE) for d in ("loco", "temporal")}
        st = {d: V.estadisticos(e) for d, e in ev.items()}
        rt = json.loads(json.dumps(st, default=float))
        out[nombre] = {"loco": rt["loco"], "temporal": rt["temporal"],
                       "cobertura_por_regimen_loco": C.por_regimen(ev["loco"]),
                       "cobertura_por_pais_loco": C.por_pais(ev["loco"]),
                       "puerta_D_referencia": C.puerta_d(st["loco"], oficial["nulo"]["loco"])}
        print(nombre, round(st["loco"]["S5"], 4), flush=True)
    out["v3_identica_a_la_oficial"] = (out["v3_recalculada"]["loco"] == oficial["loco"]
                                       and out["v3_recalculada"]["temporal"] == oficial["temporal"])
    return out


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    rapido = "--rapido" in sys.argv
    proc = {"rapido": True} if rapido else procedencia()
    t0 = time.time()
    con = D.connect()
    try:
        f14 = cargar_real(con)
        f3 = C.cargar_real_v3(con)
    finally:
        con.close()
    if max(f14["año"].max(), f3["año"].max()) > 2004:
        raise D.FactorCutoffError("filas > 2004")
    o = {"procedencia": proc, "documento": "docs/int/INT11_v3_1_imputacion.md", "config_v3_1": str(E.Config.v3_1()),
         "aviso": "Medición de un cambio de ingeniería declarado; ≤ 2004; no es puerta ni confirmación.",
         "frac_filas_sin_dato": {a: round(float(f14[a].isna().mean()), 3) for a in E.ACTIVOS}}
    o["A_correlacion_motor"] = correlacion_motor(f14)
    o["B_niveles_pmm"] = niveles_pmm(f14)
    print(json.dumps({k: o[k] for k in ("B_niveles_pmm",)}, ensure_ascii=False), flush=True)
    if not rapido:
        o["C_fase_D_informativa"] = fase_d_informativa(f3)
    o["segundos"] = round(time.time() - t0)
    txt = json.dumps(o, ensure_ascii=False, indent=1, default=float)
    if rapido:
        print(txt[:6000])
        return
    SALIDA.write_text(txt)
    print("escrito", SALIDA, o["segundos"], "s")


if __name__ == "__main__":
    main()
