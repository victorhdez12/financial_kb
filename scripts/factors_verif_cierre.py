"""Verificación (P-DEV-FACT §10.2): ¿las series mensuales del BIS (EUR por USD) y de la Bundesbank (Bund cupón cero)
son cierre o media del mes? Solo niveles, 1999-01 → 2004-12 (≤ 2004). Compara con el cierre y la media mensual de la
serie diaria equivalente: gana la de menor error absoluto medio.
Uso: .venv/bin/python -m scripts.factors_verif_cierre
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.warehouse import db

OUT = Path(__file__).resolve().parents[1] / "research" / "factors" / "verif_cierre.json"
PARES = {"bis_xru_xm_eur_m": ("ecb_eurusd_d", lambda x: 1 / x),           # BIS EUR por USD; BCE USD por EUR
         "bundesbank_bund_zero_5y_m": ("bundesbank_bund_zero_5y_d", lambda x: x),
         "bundesbank_bund_zero_1y_m": ("bundesbank_bund_zero_1y_d", lambda x: x)}


def serie(con, sid):
    df = con.execute("select date, value from obs_latest where series_id = ? and value is not null and date >= '1999-01-01'"
                     " and date <= '2004-12-31' order by date", [sid]).df()
    return pd.Series(df["value"].values, index=pd.to_datetime(df["date"]))


def main() -> None:
    con = db.connect(read_only=True)
    res = {}
    for m, (d, f) in PARES.items():
        sm, sd = serie(con, m), f(serie(con, d))
        sm.index = sm.index.to_period("M")
        g = sd.groupby(sd.index.to_period("M"))
        cmp = pd.DataFrame({"m": sm, "cierre": g.last(), "media": g.mean()}).dropna()
        e_c, e_m = (cmp["m"] - cmp["cierre"]).abs().mean(), (cmp["m"] - cmp["media"]).abs().mean()
        res[m] = {"meses": len(cmp), "error_frente_cierre": round(float(e_c), 5), "error_frente_media": round(float(e_m), 5),
                  "veredicto": "cierre" if e_c < e_m else "media"}
        print(m, res[m])
    con.close()
    OUT.write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
