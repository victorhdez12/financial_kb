"""Credit-fracture monitor: traffic light from spreads, financial conditions, lending standards,
delinquencies and the curve. Every threshold is listed in THRESHOLDS (documented in the report).

Per-indicator status: 2 = rojo, 1 = ámbar, 0 = verde, NaN = sin dato.
Overall: ROJO if >= 2 reds, or 1 red + >= 2 ambers; ÁMBAR if >= 1 red or >= 2 ambers; else VERDE.
Percentiles are expanding (only history up to t). Changes are over 3 months on the grid.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.regime.classify import pct_rank

# indicator -> (amber rule text, red rule text) — the text is reproduced in the weekly report
THRESHOLDS = {
    "baa_spread": ("≥ 2,5 pp, Δ3m ≥ +0,35 pp o percentil ≥ 80", "≥ 3,0 pp o Δ3m ≥ +0,75 pp"),
    "hy_oas": ("≥ 4,5 pp o Δ3m ≥ +0,75 pp", "≥ 6,0 pp o Δ3m ≥ +1,5 pp"),
    "nfci": ("> −0,25 o Δ3m ≥ +0,20", "> 0 (condiciones más tensas que la media)"),
    "anfci": ("> 0", "> 0,5"),
    "nfci_credit": ("> 0", "> 0,5"),
    "stlfsi": ("> 0", "> 1"),
    "sloos_ci": ("> 10 % neto endureciendo", "> 30 % neto endureciendo"),
    "delinq_all": ("Δ12m ≥ +0,3 pp", "Δ12m ≥ +0,75 pp"),
    "ted": ("> 0,5 pp", "> 1,0 pp"),
    "curve": ("curva invertida (10y−3m < 0)", "re-empinamiento tras inversión: invertida en los últimos 12m, "
                                              "ahora > 0 y Δ3m ≥ +0,5 pp"),
}


def _status(amber: pd.Series, red: pd.Series, avail: pd.Series) -> pd.Series:
    s = np.where(red, 2, np.where(amber, 1, 0)).astype(float)
    return pd.Series(np.where(avail, s, np.nan), index=avail.index)


def indicator_status(p: pd.DataFrame) -> pd.DataFrame:
    d3 = lambda c: p[c] - p[c].shift(3)  # noqa: E731
    st = pd.DataFrame(index=p.index)
    b = p["baa_spread"]
    st["baa_spread"] = _status((b >= 2.5) | (d3("baa_spread") >= 0.35) | (pct_rank(b) >= 80),
                               (b >= 3.0) | (d3("baa_spread") >= 0.75), b.notna())
    h = p["hy_oas"]
    st["hy_oas"] = _status((h >= 4.5) | (d3("hy_oas") >= 0.75), (h >= 6.0) | (d3("hy_oas") >= 1.5), h.notna())
    st["nfci"] = _status((p["nfci"] > -0.25) | (d3("nfci") >= 0.2), p["nfci"] > 0, p["nfci"].notna())
    for c in ("anfci", "nfci_credit"):
        st[c] = _status(p[c] > 0, p[c] > 0.5, p[c].notna())
    st["stlfsi"] = _status(p["stlfsi"] > 0, p["stlfsi"] > 1, p["stlfsi"].notna())
    st["sloos_ci"] = _status(p["sloos_ci"] > 10, p["sloos_ci"] > 30, p["sloos_ci"].notna())
    dl = p["delinq_all"] - p["delinq_all"].shift(12)
    st["delinq_all"] = _status(dl >= 0.3, dl >= 0.75, dl.notna())
    st["ted"] = _status(p["ted"] > 0.5, p["ted"] > 1.0, p["ted"].notna())
    c = p["curve"]
    was_inv = (c < 0).astype(float).rolling(12, min_periods=1).max() > 0
    st["curve"] = _status(c < 0, was_inv & (c > 0) & (d3("curve") >= 0.5), c.notna())
    return st


def overall(st: pd.DataFrame) -> pd.DataFrame:
    reds = (st == 2).sum(axis=1)
    ambers = (st == 1).sum(axis=1)
    n = st.notna().sum(axis=1)
    light = np.select([(reds >= 2) | ((reds >= 1) & (ambers >= 2)), (reds >= 1) | (ambers >= 2)],
                      ["rojo", "ámbar"], "verde")
    return pd.DataFrame({"credit_light": np.where(n > 0, light, None), "credit_reds": reds,
                         "credit_ambers": ambers, "credit_n": n}, index=st.index)


def credit_monitor(p: pd.DataFrame) -> pd.DataFrame:
    st = indicator_status(p)
    out = overall(st)
    out["baa_spread_pct"] = pct_rank(p["baa_spread"])
    out["hy_oas_pct"] = pct_rank(p["hy_oas"], min_periods=12)
    out["baa_spread_d3"] = p["baa_spread"] - p["baa_spread"].shift(3)
    out["hy_oas_d3"] = p["hy_oas"] - p["hy_oas"].shift(3)
    return pd.concat([out, st.add_prefix("cs_")], axis=1)
