"""INT-0: construye el panel internacional (≤ 2004) y comprueba su coherencia con JST.
Guarda los paneles en $FIN_DATA_ROOT/intl/ (fuera de git, como el resto de datos) y un resumen en research/int/panel.json.
Comprobación de DATOS (no de modelos): rentabilidad anual del bono construido (mensual compuesto, tipos OCDE) frente al
bond_tr de JST, y de la bolsa (precio OCDE + dividendo JST) frente al eq_tr de JST, por país, años comunes 1960-2004.
Uso: .venv/bin/python -m scripts.int0_panel
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import data as D
from src.intl import panel as P
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
DEST = db.DATA_ROOT / "intl"


def main() -> None:
    con = D.connect()
    a, m = P.anual(con), P.mensual(con)
    con.close()
    DEST.mkdir(parents=True, exist_ok=True)
    a.to_parquet(DEST / "panel_anual_dev.parquet")
    m.to_parquet(DEST / "panel_mensual_dev.parquet")
    # coherencia con JST
    coh = {}
    for c in D.PAISES:
        mm = m.loc[c]
        anio = mm.index.year
        bono = (1 + mm["r_bono"]).groupby(anio).prod(min_count=12) - 1
        bolsa_p = np.exp(mm["r_bolsa_precio"].groupby(anio).sum(min_count=12)) - 1
        if c not in a.index.get_level_values(0):
            continue
        j = a.loc[c]
        x = pd.DataFrame({"bono": bono, "jst_bono": j["bond_tr"], "bolsa": bolsa_p + j["eq_dp"], "jst_bolsa": j["eq_tr"]})
        x = x[(x.index >= 1960) & (x.index <= 2004)]
        r = {}
        for k in ("bono", "bolsa"):
            z = x[[k, f"jst_{k}"]].dropna()
            if len(z) >= 10:
                r[k] = {"años": len(z), "correlacion": round(float(z.corr().iloc[0, 1]), 3),
                        "dif_media_pp": round(float((z[k] - z[f"jst_{k}"]).mean() * 100), 2)}
        coh[c] = r
    cobertura = {c: {col: int(m.loc[c][col].notna().sum()) for col in m.columns if col != "pais"} for c in D.PAISES}
    res = {"filas_anual": len(a), "filas_mensual": len(m), "corte": str(D.DEV_END.date()),
           "coherencia_con_jst": coh, "meses_con_dato": cobertura}
    (REPO / "research" / "int").mkdir(parents=True, exist_ok=True)
    (REPO / "research" / "int" / "panel.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(f"anual {a.shape}, mensual {m.shape} → {DEST}")
    for c, r in coh.items():
        print(c, r)


if __name__ == "__main__":
    main()
