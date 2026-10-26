"""Retrasos de publicación del panel internacional (INT-0, tarea 1) y muestreo "as of".

Días desde el FIN del periodo de referencia hasta que el dato se puede usar. Conservadores (redondeados al alza sobre el
calendario habitual de los institutos estadísticos europeos, Japón, Canadá y Australia; los de EE. UU. son menores) y
iguales para todos los países: un solo número por medida evita afinar por país con información posterior. El desarrollo
(≤ 2004) usa datos REVISADOS (no hay vintages internacionales antes de 2008): las fechas son honestas, los niveles no.

Reglas (las mismas que src/regime/asof.py): (1) un valor de m se usa en la fecha t solo si fin(m) + retraso ≤ t;
(2) las transformaciones (interanual, diferencias) se calculan sobre el índice de observación y después se desplazan
enteras a su fecha de disponibilidad; (3) un dato más viejo que MAX_VIEJO días cuenta como ausente.
"""
from __future__ import annotations

import pandas as pd

RETRASO_DIAS: dict[str, int] = {
    # actividad
    "ip": 60,          # producción industrial: 35-45 días en Europa/Japón, 17 en EE. UU.
    "retail": 60,      # ventas minoristas: 30-45 días
    "unemp": 60,       # paro armonizado OCDE: 30-60 días (algunos países trimestrales interpolados)
    # precios
    "cpi": 30,         # IPC: 10-20 días (avance de la zona euro, 0)
    "cpicore": 30,
    # ciclo y encuestas
    "cli": 45,         # CLI de la OCDE: ≈ 40 días (y muy revisado: declarado)
    "bci": 10, "cci": 10,
    # mercado (medias mensuales: se conocen al cierre del mes)
    "irlt": 1, "ir3m": 1, "ircall": 1, "share": 1, "cbpol": 1,
    # anual JST: el dato del año t se da por conocido a finales de abril de t + 1
    "jst": 120,
}
MAX_VIEJO = {"M": 120, "A": 550}


def medida(sid: str) -> str:
    if sid.startswith("jst_"):
        return "jst"
    if sid.startswith("bis_cbpol"):
        return "cbpol"
    partes = sid.split("_")
    return partes[1] if partes[0] == "oecd" else partes[0]


def disponible(idx: pd.DatetimeIndex, sid: str, freq: str = "M") -> pd.DatetimeIndex:
    fin = idx + (pd.offsets.MonthEnd(0) if freq == "M" else pd.offsets.YearEnd(0))
    return fin + pd.to_timedelta(RETRASO_DIAS[medida(sid)], unit="D")


def asof(s: pd.Series, sid: str, rejilla: pd.DatetimeIndex, freq: str = "M") -> pd.Series:
    """Valor conocido en cada fecha de la rejilla (fin de mes) o NaN si no hay o está viejo."""
    s = s.dropna()
    if s.empty:
        return pd.Series(float("nan"), index=rejilla)
    obs = pd.DataFrame({"disp": disponible(s.index, sid, freq), "v": s.values}).sort_values("disp")
    g = pd.DataFrame({"t": rejilla})
    m = pd.merge_asof(g, obs, left_on="t", right_on="disp")
    viejo = (m["t"] - m["disp"]).dt.days > MAX_VIEJO[freq]
    m.loc[viejo, "v"] = float("nan")
    return pd.Series(m["v"].values, index=rejilla)
