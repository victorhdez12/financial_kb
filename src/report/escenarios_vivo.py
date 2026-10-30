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


def _poblacion(con, lc: str, corte) -> pd.Series | None:
    """Población anual de Maddison (solo demografía, para el PIB per cápita del ESTADO; no es un resultado)."""
    df = con.execute("select date, value from obs_latest where series_id = ? and value is not null and date <= ? "
                     "order by date", [f"maddison_{lc}_pop", pd.Timestamp(corte).date()]).df()
    if len(df) < 2:
        return None
    return pd.Series(df["value"].astype(float).values, index=pd.to_datetime(df["date"]).dt.year)


def estado_actual_movil(con, fecha, per_capita: bool = True) -> dict:
    """v2 (docs/int/INT11_v2_diseno.md §4): estado con ventanas MÓVILES de 12 meses hasta el último dato publicado y
    horizonte del abanico = los 12 meses siguientes al corte (no el año natural). Per cápita con la población de
    Maddison (anual, termina antes que el PIB: se extrapola con su crecimiento de los últimos 10 años; declarado)."""
    corte = TV.fin_de_mes(fecha)
    out = {}
    for c in NUCLEO:
        lc = c.lower()
        pob = _poblacion(con, lc, corte) if per_capita else None
        out[c] = E.estado_movil(TV._serie(con, f"oecd_cpi_{lc}_idx", corte), TV._serie(con, f"oecd_gdpq_{lc}", corte),
                                pob)
    # el abanico empieza el mes SIGUIENTE a la fecha de emisión (no al corte de datos): sin solapar meses ya vividos
    return {"corte": str(corte.date()), "emision": str(pd.Timestamp(fecha).date()),
            "ventana_objetivo": E.ventana_objetivo(fecha), "paises": out}
