"""INT-1, SEGUNDO INTENTO del fechado mensual (declarado; el primero, solo IP, dio 6/8 = 75 % < 80 %, `d1d6d49`).
Regla fijada ANTES de correr (decisión del Constructor con el visto bueno del usuario, 27-oct):
- Indicador coincidente compuesto = IP + paro invertido (src/intl/regimes.indice_coincidente), paro OCDE donde sea
  válido (el interpolado de 9 países, solo desde 1998-01, como en el panel). Mismo Bry-Boschan y mismos parámetros.
- MISMA puerta: picos de EE. UU. frente al NBER 1955-2004, ± 6 meses, ≥ 80 %. Informativo: euro frente a CEPR (± 9 m).
- Si no pasa, el fechado mensual queda solo como informativo y el forecast de riesgo (INT-4) usará las recesiones
  anuales de JST y, para EE. UU., las fechas del NBER como objetivo. No hay tercer intento.
Uso: .venv/bin/python -m scripts.int1_mensual_v2
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import data as D
from src.intl import panel as P
from src.intl import regimes as G
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
EURO = ["BEL", "DEU", "ESP", "FRA", "ITA", "NLD"]
CEPR_PICOS = [pd.Timestamp(x) for x in ("1974-08-01", "1980-02-01", "1992-02-01")]


def main() -> None:
    con = D.connect()
    usrec = P._mensual_completa(D.load_dev(con, "USREC"))
    res, giros = {"paises": {}}, []
    for c in D.PAISES:
        ip = P._mensual_completa(D.load_dev(con, f"oecd_ip_{c.lower()}"))
        if len(ip.dropna()) < 240:
            continue
        paro = P._mensual_completa(D.load_dev(con, f"oecd_unemp_{c.lower()}"))
        if c in P.PARO_INTERPOLADO and len(paro):
            paro = paro[paro.index >= P.PARO_DESDE]
        idx = ip.index
        ind = G.indice_coincidente(np.log(ip), paro.reindex(idx) if len(paro) else None)
        bb = G.bry_boschan(ind[ind.index >= "1955-01-01"])
        giros.append(bb.assign(pais=c))
        r = {"picos": int((bb.tipo == "pico").sum()), "con_paro_desde": str(paro.dropna().index.min().date()) if len(paro.dropna()) else None}
        if c in EURO:
            r["vs_cepr"] = G.concordancia(list(bb[bb.tipo == "pico"].fecha), CEPR_PICOS, 9)
        res["paises"][c] = r
    con.close()
    u = usrec[usrec.index >= "1955-01-01"]
    nber = [u.index[i - 1] for i in range(1, len(u)) if u.iloc[i] == 1 and u.iloc[i - 1] == 0]
    g = pd.concat(giros)
    bbu = g[(g.pais == "USA") & (g.tipo == "pico")]
    pu = G.concordancia(list(bbu.fecha), nber, 6)
    pu["falsos_picos"] = len(bbu) - pu["detectados"]
    pu["picos_propios"] = [str(d.date()) for d in bbu.fecha]
    res["puerta_usa_nber"] = {**pu, "cumple_80": bool(pu["pct"] >= 0.80)}
    ea = [res["paises"][c]["vs_cepr"]["pct"] for c in EURO if c in res["paises"]]
    res["euro_vs_cepr_media"] = round(float(np.mean(ea)), 3)
    g.to_parquet(db.DATA_ROOT / "intl" / "giros_mensuales_v2_dev.parquet")
    (REPO / "research" / "int" / "int1_mensual_v2.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps({k: res[k] for k in ("puerta_usa_nber", "euro_vs_cepr_media")}, indent=1, ensure_ascii=False))
    print({c: v.get("vs_cepr") for c, v in res["paises"].items() if c in EURO})


if __name__ == "__main__":
    main()
