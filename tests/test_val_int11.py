"""Tests del VALIDADOR para INT-11 (docs/validation/2026-10-30_int11.md). Sintéticos: ningún dato real.

Comprueban: (1) sin fuga en "dejar un país fuera" (los datos del país excluido no cambian su predictiva ni el pool);
(2) el régimen de partida s_prev de la fila t solo usa información hasta t − 1; (3) el arreglo de `Generador.ajustar`
(sucesor) es necesario: sin recalcular, un subconjunto encadena bloques con filas de otro país; (4) el estado en vivo
retrocede un año entero si falta un solo mes de IPC (caso EE. UU. en int11_hoy: estado 2024 → año objetivo 2025).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.intl import escenarios as E
from src.report import escenarios_vivo as V
from tests.sint_int11 import panel


def _filas():
    return E.preparar_filas(panel(n_paises=5, semilla=3))


def test_loco_sin_fuga_del_pais_excluido():
    f = _filas()
    fuera = "P02"
    tr = f["pais"].to_numpy() != fuera
    g1 = E.Generador(E.Config()).ajustar(f[tr])
    f2 = f.copy()
    m = f2["pais"] == fuera
    f2.loc[m, list(E.ACTIVOS)] = f2.loc[m, list(E.ACTIVOS)] * 5 + 1      # datos del excluido destrozados
    f2.loc[m, ["s", "s_prev"]] = 2
    g2 = E.Generador(E.Config()).ajustar(f2[tr])
    assert fuera not in g1.paises and not (g1.pais == fuera).any()
    assert g1.kappa == g2.kappa and np.array_equal(g1.n_pais, g2.n_pais)
    e1 = g1.simular(fuera, 1, horizonte=3, n_lotes=10, por_lote=50, semilla=4)
    e2 = g2.simular(fuera, 1, horizonte=3, n_lotes=10, por_lote=50, semilla=4)
    assert np.array_equal(np.nan_to_num(e1.rent, nan=-9), np.nan_to_num(e2.rent, nan=-9))
    # credibilidad propia 0 → panel puro: transición = κ · p_panel normalizada
    a = g1.posterior_transicion(fuera)
    assert np.allclose(a, g1.kappa * g1.p_panel)


def test_regimen_de_partida_solo_usa_t_menos_1():
    df = panel(n_paises=3, semilla=5)
    base = E.preparar_filas(df)
    c, t = "P01", 1950
    d2 = df.copy()
    m = (d2["pais"] == c) & (d2["año"] == t)
    d2.loc[m, "inflacion"] = 0.40                                     # año t: inflación y PIB extremos
    d2.loc[m, "rgdpmad"] = d2.loc[m, "rgdpmad"] * 0.5
    pert = E.preparar_filas(d2)
    k = ["pais", "año"]
    a = base.set_index(k).loc[(c, t)]
    b = pert.set_index(k).loc[(c, t)]
    assert a["s_prev"] == b["s_prev"]                                 # lo conocido al empezar el año no cambia
    assert b["s"] == 2                                                # el régimen del propio año sí
    # y las filas de años anteriores del país no se mueven
    pa = base[(base.pais == c) & (base.año < t)]["s_prev"].to_numpy()
    pb = pert[(pert.pais == c) & (pert.año < t)]["s_prev"].to_numpy()
    assert np.array_equal(pa, pb)


def test_sin_recalcular_el_sucesor_cruza_paises():
    """Documenta el error que corrigió 9cf53df: con el índice reiniciado y el `sucesor` original, un subconjunto
    LOCO (sin el primer país) apunta a filas de otro país/año; con el arreglo, siempre (mismo país, año + 1)."""
    f = _filas()
    sub = f[f["pais"] != "P00"]
    viejo = sub.reset_index(drop=True)
    s = viejo["sucesor"].to_numpy()
    i = np.flatnonzero((s >= 0) & (s < len(viejo)))
    mal = (viejo["pais"].to_numpy()[s[i]] != viejo["pais"].to_numpy()[i]) | \
          (viejo["año"].to_numpy()[s[i]] != viejo["año"].to_numpy()[i] + 1)
    assert mal.mean() > 0.9
    g = E.Generador(E.Config()).ajustar(sub)
    j = np.flatnonzero(g.suc >= 0)
    assert (g.pais[g.suc[j]] == g.pais[j]).all() and (g.anio[g.suc[j]] == g.anio[j] + 1).all()


def test_estado_vivo_retrocede_si_falta_un_mes():
    m = pd.date_range("2005-01-01", "2026-09-01", freq="MS")
    cpi = pd.Series(100 * np.exp(0.02 * np.arange(len(m)) / 12), index=m)
    cpi = cpi.drop(pd.Timestamp("2025-10-01"))                         # un mes perdido (como el IPC de EE. UU.)
    q = pd.date_range("2005-01-01", "2026-04-01", freq="QS")
    pib = pd.Series(np.exp(0.005 * np.arange(len(q))), index=q)
    e = V.estado_pais(cpi, pib)
    assert e["año"] == 2024     # el abanico "a 1 año" describe entonces 2025, un año ya terminado
