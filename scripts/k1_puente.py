"""P-K1v §2: puente JST (tloans/gdp) → BIS (bis_tc_XX_pb_m) del Δ5 del crédito bancario, solo ≤ 2004 y sin crisis.
Descriptivo: correlación y pendiente por país. Uso: .venv/bin/python -m scripts.k1_puente"""
import numpy as np
import pandas as pd

from scripts.int6_corrida import NUCLEO
from src.intl import data as D
from src.warehouse import db


def main() -> None:
    con, w = D.connect(), db.connect(read_only=True)
    rows = []
    for c in NUCLEO:
        j = D.load_dev(con, f"jst_{c.lower()}_tloans") / D.load_dev(con, f"jst_{c.lower()}_gdp") * 100
        j.index = j.index.year
        q = w.execute("select date, value from obs_latest where series_id = ? and date <= '2004-12-31' order by date",
                      [f"bis_tc_{D.ISO2[c]}_pb_m"]).df()
        s = pd.Series(q.value.values, index=pd.to_datetime(q.date))
        s = s[s.index.month == 10]
        s.index = s.index.year
        z = pd.concat([j.diff(5), s.diff(5)], axis=1, keys=["jst", "bis"]).dropna()
        rows.append({"pais": c, "n": len(z), "desde": int(z.index.min()), "corr": round(z.corr().iloc[0, 1], 2),
                     "pendiente": round(float(np.polyfit(z.bis, z.jst, 1)[0]), 2)})
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
