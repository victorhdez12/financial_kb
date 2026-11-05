"""P-E1 (docs/int/E1_prerregistro_v1.md, v1.0): ajuste ÚNICO de L y A con datos ≤ 2004 y congelación con sha256.
No evalúa nada (la evaluación es en vivo, §11). No lee nada ≥ 2005.

Uso: .venv/bin/python -m scripts.e1_corrida --sintetico   (P4: señal plantada; no escribe nada)
     .venv/bin/python -m scripts.e1_corrida               (puerta: árbol limpio, sha256 del prerregistro; una vez)
     .venv/bin/python -m scripts.e1_corrida --seis        (P-E1b, 6 meses; misma puerta)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scripts import int13_corrida as C
from src.intl import e1 as E
from src.intl import int13 as M

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs/int/E1_prerregistro_v1.md"
DOC_SHA = "62fb1b57b67b454a79adc1e493060ab033dc62dc45772c37bc9dd5182efb5437"
SALIDA = REPO / "research/int/e1_modelos.json"
# P-E1b (6 meses): docs/int/E1b_6m_prerregistro_v1.md
OBJ6 = {"doc": REPO / "docs/int/E1b_6m_prerregistro_v1.md",
        "sha": "a02e10abcc4cbcf78b3f5d470e67dcb0610cb55731774a846b897deb9a728e90",
        "salida": REPO / "research/int/e1_6_modelos.json", "obj": "E1_6", "documento": "P-E1b v1.0 (6 meses)"}


def sintetico() -> None:
    """P4: con la señal plantada en la confianza, A gana a L fuera de muestra; sin señal, ΔAUC ≈ 0."""
    df = M.construir(C.cargar_sintetico())
    rng = np.random.default_rng(1)
    res = {}
    for nom, k in (("sin_senal", 0.0), ("senal", 1.5)):
        d = df.copy()
        d["confianza_emp"] = d["confianza_emp"] + k * 50 * (d[E.Y].fillna(0) - 0.5) * -1 + rng.normal(0, 30, len(d))
        aj, ev = d[d.fecha <= M.CORTE_TEMPORAL], d[d.fecha >= M.PRUEBA_DESDE + pd.offsets.MonthEnd(12)]
        mod = E.ajustar(E.filas(aj))
        r = E.evaluar(mod, ev, sin_2020=False)
        res[nom] = {"dauc": round(r["principal"]["dauc"], 3), "p1": round(r["p1"]["p"], 3),
                    "p2": round(r["p2_dauc"], 3), "p3": round(r["p3_dauc"], 3)}
    print("[P4 sintético]", res)
    assert res["senal"]["dauc"] > 0.05 and res["senal"]["p1"] < 0.05, "no recupera la señal plantada"
    assert abs(res["sin_senal"]["dauc"]) < 0.05, "ΔAUC sin señal lejos de 0"
    print("P4 superado")


def main() -> None:
    if "--sintetico" in sys.argv:
        return sintetico()
    from src.intl.procedencia import procedencia
    seis = "--seis" in sys.argv
    doc, sha_doc, salida, obj = ((OBJ6["doc"], OBJ6["sha"], OBJ6["salida"], OBJ6["obj"]) if seis
                                 else (DOC, DOC_SHA, SALIDA, E.OBJ))
    if salida.exists():
        raise SystemExit(f"{salida} ya existe: el ajuste es único")
    if hashlib.sha256(doc.read_bytes()).hexdigest() != sha_doc:
        raise SystemExit("el prerregistro no coincide con el congelado")
    proc = procedencia(exigir_limpio=True)
    df = M.construir(C.cargar_real())
    yc = f"y_{obj}"
    d = E.filas(M.muestra(df, obj), yc)
    n, ev = len(d), int(d[yc].sum())
    if not seis and (n, ev) != E.ESPERADO_DEV:
        raise SystemExit(f"P5: filas/eventos {n}/{ev} ≠ INT-13 {E.ESPERADO_DEV}")
    if d.fecha.max() + pd.offsets.MonthEnd(M.OBJETIVOS[obj]) > M.FIN_DEV:
        raise SystemExit("P5: objetivo posterior a 2004")
    mod = E.ajustar(d, yc)
    sg = E.signos_ok(mod)
    out = {"documento": OBJ6["documento"] if seis else "P-E1 v1.0", "doc_sha256": sha_doc, "procedencia": proc, "filas": n, "eventos": ev,
           "desde": str(d.fecha.min().date()), "hasta": str(d.fecha.max().date()), "modelos": mod,
           "modelos_sha256": E.sha(mod), "signos_ok": sg,
           "estado": "congelado" if all(sg.values()) else "PARADO: signo de la actividad al revés (§4)",
           "nota": "solo ajuste ≤ 2004; ninguna métrica de desarrollo cuenta (M1); evaluación en vivo (§11)"}
    salida.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({k: out[k] for k in ("filas", "eventos", "signos_ok", "estado", "modelos_sha256")}, indent=1))


if __name__ == "__main__":
    main()
