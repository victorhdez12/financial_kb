"""P-DEV-INT14 — corrección DECLARADA del placebo del panel (research/int/int14_resultado.md §0).

Defecto de implementación detectado tras la corrida única: `placebo_panel` exigía un año falso por CADA evento
verdadero, también por los que no entran en la estimación por falta de rentabilidad (CAN 1907 en JST; oro antes de
1969). Eso es imposible → 0 placebos válidos → p = 1 por construcción (no por los datos). La corrección hace lo que
dice el prerregistro v1.0 §4 ("para cada crisis verdadera" que entra en el efecto): `solo_con_dato=True`. Mismos
eventos, mismas semillas, mismas réplicas (2.000 en H1, H2, H4; 300 en lo descriptivo). No se recalculan ni efectos ni
IC (ya están en int14_resultado.json); solo los valores p de placebo de las capas anuales, y Holm.

Con puerta: árbol limpio y se niega a correr si research/int/int14_placebo_corregido.json existe.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.int14_corrida import PRINCIPALES, SEMILLA, mundial_anual, panel
from scripts.int14_potencia import GUERRAS, Datos, construir_eventos
from src.intl import eventos as E

REPO = Path(__file__).resolve().parents[1]
ORIGEN = REPO / "research" / "int" / "int14_resultado.json"
SALIDA = REPO / "research" / "int" / "int14_placebo_corregido.json"


def main():
    if SALIDA.exists():
        raise SystemExit(f"{SALIDA} ya existe (corrección única)")
    from src.intl.procedencia import procedencia
    from src.warehouse import db
    t0 = time.time()
    orig = json.loads(ORIGEN.read_text())
    res = {"procedencia": procedencia(exigir_limpio=True), "origen": str(ORIGEN.relative_to(REPO)),
           "motivo": __doc__.strip().split("\n\n")[1]}
    con = db.connect(read_only=True)
    D = Datos(con, db)
    B = construir_eventos(D)
    P, M = panel(D), mundial_anual(D)
    con.close()
    ev = B["ev"]
    f = lambda k: list(ev[k]["fecha"])                                         # noqa: E731
    c = B["crisis"]
    c_sg = c[~c["año"].isin(list(GUERRAS))].reset_index(drop=True)
    cg = E.conglomerados_globales(c["año"].values)
    años_ev = lambda k: pd.DataFrame({"año": sorted({p.year for p in f(k)} - GUERRAS)})   # noqa: E731
    conj = {"panel": (P, {"crisis": (c_sg, False, 5),
                          "crisis_1946_2004": (c_sg[c_sg.año >= 1946].reset_index(drop=True), False, 5),
                          "petroleo_global": (años_ev("petroleo"), True, 2), "vol_global": (años_ev("vol"), True, 2),
                          "dolar_global": (años_ev("dolar"), True, 2)}),
            "mundial": (M, {"crisis_episodios": (pd.DataFrame({"año": sorted(set(cg.inicio.astype(int)) - GUERRAS)}),
                                                 True, 2),
                            "petroleo": (años_ev("petroleo"), True, 2), "vol": (años_ev("vol"), True, 2),
                            "dolar": (años_ev("dolar"), True, 2)})}
    ppal = {(v[1], v[2], v[3]) for v in PRINCIPALES.values() if v[0] == "panel"}
    out = {}
    for capa, (datos, conjuntos) in conj.items():
        out[capa] = {}
        for evn, (eventos, comun, sep) in conjuntos.items():
            out[capa][evn] = {}
            for a, r in datos.items():
                out[capa][evn][a] = {}
                for nombre, H, desde in [("H0_año_t", 1, 0)] + [(f"H{H}", H, 1) for H in (1, 2, 3)]:
                    o = orig[capa][evn][a][nombre]
                    if o.get("nota"):
                        out[capa][evn][a][nombre] = {"nota": o["nota"]}
                        continue
                    es_ppal = (evn, a, nombre) in ppal
                    pl = E.placebo_panel(r, eventos, H, comun, sep, n_rep=2000 if es_ppal else 300, semilla=SEMILLA,
                                         excluir_años=frozenset(GUERRAS), desde=desde, solo_con_dato=True)
                    v = int(np.isfinite(pl).sum())
                    out[capa][evn][a][nombre] = {
                        "p_placebo_v1_0": o.get("p_placebo"), "placebos_validos_v1_0": o.get("placebos_validos"),
                        "p_placebo_corregido": round(E.p_placebo(o["efecto_log"], pl), 4) if v else None,
                        "placebos_validos": v}
            print(capa, evn, flush=True)
    res["capas"] = out
    prin = {}
    for k, (capa, evn, a, h) in PRINCIPALES.items():
        if capa == "mensual":
            p = orig["principales"][k]["p_placebo"]
        else:
            p = out["panel"][evn][a][h]["p_placebo_corregido"]
        prin[k] = {**orig["principales"][k], "p_placebo": p}
    ph = E.holm({k: v["p_placebo"] for k, v in prin.items()})
    for k, v in prin.items():
        v["p_holm"] = round(ph[k], 4)
        ic = v["ic90_pp"]
        v["veredicto"] = "establecido" if ph[k] < 0.05 and ic and (ic[0] > 0 or ic[1] < 0) else "no establecido"
    res["principales_corregidos"] = prin
    res["segundos"] = round(time.time() - t0)
    SALIDA.write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    print(json.dumps(prin, ensure_ascii=False), res["segundos"], "s")


if __name__ == "__main__":
    main()
