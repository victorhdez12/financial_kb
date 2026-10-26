"""INT-3d, sensibilidad DECLARADA A POSTERIORI (Validador, 27-oct): la del §8 del prerregistro que no se calculó en la
corrida única ("inflación absoluta del 3 % para E-I"). La etiqueta abs3 se construye igual que en INT-3 e INT-4
(src.intl.regimes.etiqueta con umbral 3 % y relativa=False sobre log PIB real pc e inflación de JST): no hacía falta
otro parquet. No cambia el prerregistro, la familia ni la clasificación; C5 sigue siendo descriptivo.
Uso: .venv/bin/python -m scripts.int3d_sensibilidad_abs3
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts import int3d_corrida as R
from src.intl import data as D
from src.intl import int3d as M
from src.intl import panel as P
from src.intl import regimes as G
from src.intl.procedencia import procedencia

REPO = Path(__file__).resolve().parents[1]


def etiqueta_abs3(anual: pd.DataFrame, paises: list[str]) -> pd.DataFrame:
    out = []
    for c in paises:
        a = anual.loc[c]
        e = G.etiqueta(np.log(a["rgdpmad"]), a["inflacion"], G.VENTANA_ANUAL, umbral_i=G.UMBRAL_I_ABSOLUTO, relativa=False)
        out.append(e[["cuadrante", "frontera", "truncada"]].assign(pais=c).reset_index(names="año"))
    return pd.concat(out, ignore_index=True)


def main() -> None:
    proc = procedencia()
    con = D.connect()
    anual = P.anual(con)
    con.close()
    x = M.panel_log(anual, R.NUC)
    ev = M.dic_t(M.eventos_transicion(etiqueta_abs3(anual, R.NUC), R.NUC, R.INFL_ALTA))
    vf = M.valfun_nombre("C5_espera_inflac")
    res = {"procedencia": proc, "nota": "a posteriori; C5 descriptivo; no decide",
           "C5_espera_inflac_abs3": {m: M.evaluar(vf, x["bond_x"], M.submuestra("C5_espera_inflac", ev, m))
                                     for m in ("principal", "sin_guerras", "1950_2004")}}
    (REPO / "research" / "int" / "int3d_sensibilidad_abs3.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps({m: {k: round(v[k], 4) for k in ("efecto", "p", "p_rangos")} | {"eventos": v["eventos"]}
                      for m, v in res["C5_espera_inflac_abs3"].items()}, indent=1))


if __name__ == "__main__":
    main()
