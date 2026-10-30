"""INT-11, parte en vivo: estado ACTUAL de cada país para el motor de escenarios (docs/int/INT11_prerregistro_v1.md §8).

Vive en src/report/ porque lee datos ≥ 2005 (como termometro_vivo): OCDE del warehouse (`obs_latest`, sin vintages),
NUNCA JST. Solo se usa para el ESTADO de partida; el motor se estima con filas ≤ 2004 (src/intl/escenarios).

Estado operable (eje P3, Atlas §8) del último año completo publicado:
  inflación = Δlog de la media anual del IPC (12 meses en cada año);
  brecha ≈ log PIB real TOTAL anual (suma de 4 trimestres) − media de los 10 años anteriores. Aproximación declarada:
  en el desarrollo es PIB per cápita (JST); sin población en vivo se usa el total (con población creciendo ≈ 0,3-0,5 %
  al año la brecha sale ≈ 2 pp más alta, es decir, algo menos propensa a marcar "crecimiento bajo").
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.intl import escenarios as E
from src.report import termometro_vivo as TV

NUCLEO = TV.NUCLEO


def anual_completo(s: pd.Series, n: int) -> pd.Series:
    """Media (n = 12, mensual) o suma (n = 4, trimestral) por año natural, solo años con n observaciones."""
    s = s.dropna()
    g = s.groupby(s.index.year)
    ok = g.count() == n
    v = g.mean() if n == 12 else g.sum()
    return v[ok]


def estado_pais(cpi_m: pd.Series, pib_q: pd.Series) -> dict:
    ipc = anual_completo(cpi_m, 12)
    pib = np.log(anual_completo(pib_q, 4))
    años = [a for a in ipc.index if a in pib.index and a - 1 in ipc.index
            and all(a - k in pib.index for k in range(1, E.VENTANA_BRECHA + 1))]
    if not años:
        return {"año": None, "regimen": None}
    a = max(años)
    infl = float(np.log(ipc[a] / ipc[a - 1]))
    brecha = float(pib[a] - np.mean([pib[a - k] for k in range(1, E.VENTANA_BRECHA + 1)]))
    r = int(E.codigo_regimen([infl], [brecha])[0])
    return {"año": int(a), "inflacion": infl, "brecha_pib_total": brecha, "regimen": E.REGIMENES[r], "codigo": r}


def estado_actual(con, fecha) -> dict:
    corte = TV.fin_de_mes(fecha)
    out = {}
    for c in NUCLEO:
        lc = c.lower()
        out[c] = estado_pais(TV._serie(con, f"oecd_cpi_{lc}_idx", corte), TV._serie(con, f"oecd_gdpq_{lc}", corte))
    return {"corte": str(corte.date()), "paises": out}
