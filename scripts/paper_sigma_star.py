"""σ* del paper trading en la MISMA medida que la señal en vivo (decisión del usuario, 26-oct): volatilidad de 12
rendimientos mensuales de la RV de EE. UU. en EUR, con precio y divisa A CIERRE DE MES.
- RV: mercado de EE. UU. de French (`ff_mkt_rf_m` + `ff_rf_m`, cierre de mes; incluye dividendos, el S&P 500 de precio
  a cierre de mes no existe antes de 2016 en el warehouse; los dividendos apenas afectan a la volatilidad).
- Divisa: fixing de Frankfurt DEM/USD (Bundesbank) / 1,95583 hasta 1998-12; EUR/USD del BCE desde 1999-01 (último día
  hábil del mes).
σ* = mediana expansiva de σ̂ desde 1963-07 hasta 2004-12, congelada. Además: frecuencia con que B1 (70/15/15, RV en
[55 %, 70 %], umbral 2,5 pp) recortaría en desarrollo con el σ* antiguo (15,48 %) y con el nuevo. Sin rentabilidades de
cartera. Uso: .venv/bin/python -m scripts.paper_sigma_star
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.factors import data as F

OUT = Path(__file__).resolve().parents[1] / "research" / "paper" / "sigma_star.json"
ANTIGUO, RV, RV_MIN, UMBRAL = 0.1548, 0.70, 0.55, 0.025


def fin_de_mes(s: pd.Series) -> pd.Series:
    return s.groupby(s.index.to_period("M")).last()


def main() -> None:
    con = F.connect()
    rv = ((F.load_dev(con, "ff_mkt_rf_m") + F.load_dev(con, "ff_rf_m")) / 100)
    rv.index = rv.index.to_period("M")
    dem = fin_de_mes(F.load_dev(con, "bundesbank_usd_dem_d")) / 1.95583           # EUR por USD (marco en EUR equiv.)
    ecb = 1 / fin_de_mes(F.load_dev(con, "ecb_eurusd_d"))                          # EUR por USD
    con.close()
    fx = pd.concat([dem[dem.index < pd.Period("1999-01", "M")], ecb[ecb.index >= pd.Period("1999-01", "M")]])
    rv_eur = ((1 + rv) * (fx / fx.shift(1)).reindex(rv.index) - 1).dropna()
    sig = (rv_eur.rolling(12).std() * np.sqrt(12))
    sig = sig[sig.index >= pd.Period("1963-07", "M")].dropna()
    nuevo = float(sig.expanding().median().iloc[-1])

    def recortes(sigma_star: float, desde: str) -> dict:
        s = sig[sig.index >= pd.Period(desde, "M")]
        bruta = (RV * np.minimum(1, sigma_star / s)).clip(RV_MIN, RV)
        cur, objs = RV, []
        for x in bruta:
            if abs(x - cur) >= UMBRAL - 1e-12:
                cur = float(x)
            objs.append(cur)
        o = pd.Series(objs, index=s.index)
        return {"pct_meses_recortado": round(float((o < RV - 1e-9).mean()), 3),
                "rv_media_recortado": round(float(o[o < RV - 1e-9].mean()), 3) if (o < RV - 1e-9).any() else None,
                "cambios_al_año": round(float((o != o.shift()).sum() - 1) / (len(o) / 12), 2)}
    res = {"sigma_star_antiguo": ANTIGUO, "sigma_star_nuevo": round(nuevo, 4),
           "medida": "RV EE. UU. (French, cierre de mes) en EUR con DEM/USD Frankfurt ≤ 1998 y BCE ≥ 1999, cierre de mes",
           "recortes": {f"{k}_{d}": recortes(v, d) for k, v in (("antiguo", ANTIGUO), ("nuevo", nuevo))
                        for d in ("1963-07", "1975-01")}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
