"""Validador INT-11 v3 (31-oct): por qué el IC 90 % de P(inflación > 5 %) sale de anchura 0 en DEU y FIN tras 77b3bd1.
Descompone var(medias de lote) frente al ruido MC estratificado y el no estratificado. Nada ≥ 2005 en el ajuste.
Uso: .venv/bin/python -m scripts.val_int11v3_ic
"""
import json
from pathlib import Path

import numpy as np

from scripts import int11_v3_hoy as H
from scripts.int11_v3_corrida import cargar_real_v3
from src.intl import data as D
from src.intl import escenarios as E
from src.intl.procedencia import procedencia
from src.report import escenarios_vivo as V

OUT = Path(__file__).resolve().parents[1] / "research/int/val_int11v3/ic.json"


def descomp(x, lote, estrato):
    ids = np.unique(lote)
    med = np.array([x[lote == b].mean() for b in ids])
    mc_e = []
    for b in ids:
        xb, sb = x[lote == b], estrato[lote == b]
        mc_e.append(sum((len(xb[sb == s]) / len(xb)) ** 2 * xb[sb == s].var(ddof=1) / len(xb[sb == s])
                        for s in np.unique(sb) if (sb == s).sum() > 1))
    mc_simple = np.mean([x[lote == b].var(ddof=1) / (lote == b).sum() for b in ids])
    return {"p": float(x.mean()), "var_medias": float(np.var(med, ddof=1)), "mc_estratificado": float(np.mean(mc_e)),
            "mc_simple": float(mc_simple), "estratos": {int(s): int((estrato == s).sum()) for s in np.unique(estrato)}}


def main() -> None:
    proc = procedencia()
    con = D.connect()
    filas = cargar_real_v3(con)
    assert filas["año"].max() <= 2004
    gen = E.Generador(E.Config.v3()).ajustar(filas)
    est = V.estado_actual_movil(con, "2026-10-30")
    o = {"procedencia": proc}
    for i, c in enumerate(H.NUCLEO):
        e = est["paises"][c]
        if e.get("regimen") is None:
            continue
        esc = gen.simular_suave(c, e["inflacion"], e["brecha"], horizonte=1, n_lotes=200, por_lote=100, semilla=H.SEED + i)
        ev = (np.expm1(esc.inflacion[:, 0]) > 0.05).astype(float)
        o[c] = {"infl_5": descomp(ev, esc.lote, esc.inicio),
                "bolsa_20": descomp((esc.rent[:, 0, list(esc.activos).index("bolsa")] <= -0.20).astype(float),
                                    esc.lote, esc.inicio)}
    OUT.write_text(json.dumps(o, indent=1))
    for c, d in o.items():
        if c == "procedencia":
            continue
        r = d["infl_5"]
        print(c, f"p={r['p']:.3f} var_med={r['var_medias']:.2e} mcE={r['mc_estratificado']:.2e} mcS={r['mc_simple']:.2e}",
              r["estratos"])


if __name__ == "__main__":
    main()
