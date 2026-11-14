"""Monitor de correlaciones entre activos de EE. UU. (solo descriptivo; NO toca el motor INT-11).

Rentabilidades mensuales nominales (tabla `monthly` del warehouse):
- bolsa: shiller_nominal_stock_tr_ret_m (S&P compuesto con dividendos; Shiller usa medias mensuales de precio);
- bonos: shiller_nominal_bond_tr_ret_m (bono a 10 años, rentabilidad total);
- oro: variación de gold_usd_monthly;
- dólar: variación del índice amplio DTWEXBGS (desde 2006).
Correlación de Pearson móvil a 36 y 12 meses. Referencia del motor: `dependencia_hoy` de EE. UU. en
research/int/int11_v3_hoy.json (lo que enseña la pestaña de escenarios): correlación (log) de rentabilidades REALES a
12 meses heredada de las filas ≤ 2004. Horizonte y deflactor distintos: la comparación útil es el SIGNO.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.warehouse import db

INT11_HOY = db.REPO / "research/int/int11_v3_hoy.json"
SERIES = {"bolsa": ("shiller_nominal_stock_tr_ret_m", "ret"), "bonos": ("shiller_nominal_bond_tr_ret_m", "ret"),
          "oro": ("gold_usd_monthly", "nivel"), "dolar": ("DTWEXBGS", "nivel")}
PARES = [("bolsa", "bonos"), ("bolsa", "oro"), ("bonos", "oro"), ("bolsa", "dolar")]
UMBRAL_DIF = 0.3   # aviso secundario: |ρ36 − ρmotor| ≥ 0,3 aunque coincida el signo
NOMBRE = {"bolsa": "bolsa", "bonos": "bonos", "oro": "oro", "dolar": "dólar"}


def rentabilidades(con=None) -> pd.DataFrame:
    cerrar = con is None
    con = con or db.connect()
    try:
        cols = {}
        for k, (sid, tipo) in SERIES.items():
            df = con.execute("select month, value from monthly where series_id = ? and value is not null order by month",
                             [sid]).df()
            s = pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["month"]))
            cols[k] = s if tipo == "ret" else s.pct_change()
        return pd.DataFrame(cols)
    finally:
        if cerrar:
            con.close()


def motor(ruta: Path = INT11_HOY) -> dict:
    try:
        h = json.loads(Path(ruta).read_text())
    except Exception:  # noqa: BLE001
        return {}
    dh = ((h.get("paises") or {}).get("USA") or {}).get("dependencia_hoy") or {}
    return {"emision": h.get("emision"), "valores": dh}


def monitor(r: pd.DataFrame, ref: dict, desde: str = "2000-01-01") -> dict:
    out = {"pares": [], "series": {}, "nota": __doc__.split("\n\n")[1].strip()}
    for a, b in PARES:
        par = f"{a}-{b}"
        d = r[[a, b]].dropna()
        c36 = d[a].rolling(36).corr(d[b])
        c12 = d[a].rolling(12).corr(d[b])
        m = (ref.get("valores") or {}).get(par)
        u36 = c36.dropna()
        v36 = float(u36.iloc[-1]) if len(u36) else None
        v12 = float(c12.dropna().iloc[-1]) if c12.notna().any() else None
        signo = None if m is None or v36 is None else (np.sign(v36) != np.sign(m))
        out["pares"].append({"par": par, "nombre": f"{NOMBRE[a]}-{NOMBRE[b]}",
                             "ultimo_mes": u36.index.max().strftime("%Y-%m") if len(u36) else None,
                             "c36": None if v36 is None else round(v36, 3), "c12": None if v12 is None else round(v12, 3),
                             "c_10a": round(float(d[a].tail(120).corr(d[b].tail(120))), 3) if len(d) >= 120 else None,
                             "motor": m, "difiere_signo": bool(signo) if signo is not None else None,
                             "difiere_mucho": None if m is None or v36 is None else bool(abs(v36 - m) >= UMBRAL_DIF)})
        s = c36[c36.index >= desde].dropna()
        s12 = c12[c12.index >= desde].dropna()
        out["series"][par] = {"c36": [[i.strftime("%Y-%m"), round(float(v), 3)] for i, v in s.items()],
                              "c12": [[i.strftime("%Y-%m"), round(float(v), 3)] for i, v in s12.items()]}
    out["motor_emision"] = ref.get("emision")
    return out


def calcular() -> dict:
    return monitor(rentabilidades(), motor())
