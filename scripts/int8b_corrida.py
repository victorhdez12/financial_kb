"""INT-8b (docs/int/INT8b_regla_v1.md, regla congelada en `88ae9be`): congela las referencias 1960-2004 del nowcast
descriptivo y dibuja la ilustración 1960-2004 (CONTAMINADA, solo para ver qué mide). Solo datos ≤ 2004 (`load_dev`,
`load_dev_curado`). No calcula ninguna métrica de acierto (ni AUC, ni tasas): no es una prueba.

Salidas: research/int/int8b_referencias.json y research/int/graficas/int8b_ilustracion.png. Exige el árbol limpio.
Uso: .venv/bin/python -m scripts.int8b_corrida
"""
from __future__ import annotations

import json
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.intl import data as D  # noqa: E402
from src.intl import int8b as K  # noqa: E402
from src.intl import panel as P  # noqa: E402
from src.intl import termometro as T  # noqa: E402
from src.intl.procedencia import REPO, procedencia  # noqa: E402
from src.report import nowcast_vivo as NV  # noqa: E402

SALIDA = REPO / "research" / "int" / "int8b_referencias.json"
FIGURA = REPO / "research" / "int" / "graficas" / "int8b_ilustracion.png"
UMBRAL_SOMBRA = 1 / 3       # ilustración: se sombrea si ≥ 1/3 del núcleo con dato está en recesión (fechado)


def cargar_dev():
    con = D.connect()
    try:
        pm = P.mensual(con)
        bis = {c: s for c in NV.TODOS if not (s := D.load_dev(con, f"bis_creditgap_{D.ISO2[c]}_ratio")).empty}
        paro = {c: s for c in NV.TODOS if not (s := D.load_dev(con, f"oecd_unemp_{c.lower()}")).empty}
        usrec = D.load_dev(con, "USREC")
    finally:
        con.close()
    pib = {c: D.load_dev_curado(f"oecd_gdpq_{c.lower()}") for c in NV.TODOS}
    return pm, bis, pib, paro, usrec


def _tramos(mask: pd.Series):
    """(inicio, fin) de los tramos seguidos con mask True."""
    out, ini = [], None
    for t, v in mask.items():
        if v and ini is None:
            ini = t
        if not v and ini is not None:
            out.append((ini, t))
            ini = None
    if ini is not None:
        out.append((ini, mask.index[-1]))
    return out


def figura(res: dict, pib: dict, usrec: pd.Series) -> None:
    rej = res["A"].index
    sel = (rej >= K.REF_DESDE) & (rej <= K.REF_HASTA)
    est = pd.DataFrame({c: T.estado_mensual(T.fechado_trimestral(pib[c].dropna()), rej, pib[c].dropna().index.min())
                        ["en_rec"] for c in NV.NUCLEO})
    frac = est.mean(axis=1, skipna=True)
    usr = usrec.set_axis(usrec.index + pd.offsets.MonthEnd(0)).reindex(rej).fillna(0) > 0
    tinta, sec, serie, sombra = "#1f2328", "#59636e", "#2a6fdb", "#d0d7de"
    fig, ax = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True)
    paneles = [(res["A"], frac >= UMBRAL_SOMBRA, "Agregado del núcleo (14 países)",
                "sombra: ≥ 1/3 del núcleo en recesión según el fechado trimestral del PIB"),
               (res["N"]["USA"], usr, "EE. UU.", "sombra: recesiones NBER (USREC, solo contraste externo)")]
    for a, (y, m, tit, nota) in zip(ax, paneles):
        for i, f in _tramos(m[sel]):
            a.axvspan(i, f, color=sombra, lw=0)
        a.plot(y.index[sel], y[sel], color=serie, lw=1.6)
        a.set_ylim(0, 100)
        a.set_ylabel("índice 0-100", color=sec)
        a.set_title(f"{tit} — {nota}", loc="left", fontsize=10, color=tinta)
        a.grid(axis="y", color="#eaeef2", lw=0.8)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
        a.tick_params(colors=sec)
    fig.suptitle("INT-8b nowcast descriptivo 1960-2004 — ILUSTRACIÓN CONTAMINADA (indicadores elegidos sabiendo qué "
                 "funcionó en estos episodios); no es una prueba", fontsize=10.5, color=tinta, x=0.01, ha="left")
    fig.tight_layout()
    FIGURA.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURA, dpi=130)
    plt.close(fig)


def _json(v):
    if isinstance(v, dict):
        return {a: _json(x) for a, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_json(x) for x in v]
    if isinstance(v, (float, np.floating)):
        return None if not np.isfinite(v) else float(v)
    return v


def main() -> None:
    proc = procedencia()
    pm, bis, pib, paro, usrec = cargar_dev()
    comp = K.componentes(pm, bis, pib, paro, NV.NUCLEO, NV.TODOS)
    refs = K.referencias(comp, NV.NUCLEO, NV.TODOS)
    res = K.calcular(comp, refs, NV.NUCLEO, NV.TODOS)
    figura(res, pib, usrec)
    meses = {"indicadores": {k: {c: len(refs["indicadores"][k][c]) for c in NV.TODOS} for k in K.CLAVES},
             "indice": {c: len(refs["indice"][c]) for c in NV.TODOS}, "agregado": len(refs["agregado"])}
    out = {"procedencia": proc, "regla": "docs/int/INT8b_regla_v1.md (commit 88ae9be)",
           "descripcion": "Distribuciones 1960-2004 de los 6 indicadores, del índice por país y del agregado del núcleo "
                          "(scripts/int8b_corrida.py). Solo datos ≤ 2004. Sin ninguna métrica de acierto.",
           "meses": meses, "figura": str(FIGURA.relative_to(REPO)), "referencias": _json(refs)}
    txt = json.dumps(out, indent=1, ensure_ascii=False)
    txt = re.sub(r"\[\s*([-+0-9.eE,\s]+?)\s*\]", lambda m: "[" + ", ".join(x.strip() for x in m.group(1).split(",")) + "]",
                 txt)
    SALIDA.write_text(txt + "\n")
    print(json.dumps(meses, ensure_ascii=False))
    print(f"-> {SALIDA}\n-> {FIGURA}")


if __name__ == "__main__":
    main()
