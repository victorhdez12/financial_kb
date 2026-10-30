"""Validador INT-14: tests sintéticos de la corrección del placebo del panel (cadcba1) y de la reproducción propia."""
import numpy as np
import pandas as pd
import pytest

from scripts import val_int14_repro as V
from src.intl import eventos as E


def _panel(seed=3, T=80, cols="ABC"):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.normal(0.03, 0.1, (T, len(cols))), index=range(1900, 1900 + T), columns=list(cols))


def test_p_placebo_sin_placebos_es_1_por_construccion():
    """El defecto de v1.0: con 0 placebos válidos, p = (1 + 0)/(1 + 0) = 1 sea cual sea el efecto."""
    assert E.p_placebo(-10.0, np.full(50, np.nan)) == 1.0


def test_solo_con_dato_equivale_a_pasar_solo_los_eventos_usados():
    """La corrección solo filtra eventos sin dato: mismo sorteo que pasar a mano los eventos que entran."""
    p = _panel()
    p.loc[:1925, "C"] = np.nan                       # C sin datos al principio
    ev = pd.DataFrame({"pais": ["A", "B", "C", "C"], "año": [1910, 1930, 1912, 1950]})
    usados = E.efecto_panel(p, ev, 2)["detalle"][["pais", "año"]]
    assert len(usados) == 3
    a = E.placebo_panel(p, ev, 2, False, 5, n_rep=30, semilla=11, solo_con_dato=True)
    b = E.placebo_panel(p, usados, 2, False, 5, n_rep=30, semilla=11)
    np.testing.assert_allclose(a, b)


def test_correccion_no_cambia_el_efecto():
    p = _panel()
    p["C"] = np.nan
    ev = pd.DataFrame({"pais": ["A", "C"], "año": [1910, 1930]})
    r = E.efecto_panel(p, ev, 3)
    assert r["n"] == 1
    assert np.isnan(E.placebo_panel(p, ev, 3, False, 5, n_rep=5)).all()           # v1.0: degenerado
    assert np.isfinite(E.placebo_panel(p, ev, 3, False, 5, n_rep=5, solo_con_dato=True)).all()


@pytest.mark.parametrize("H", [1, 3])
def test_efecto_propio_coincide_con_efecto_panel(H):
    """Implementación independiente del Validador (val_int14_repro) = efecto_panel en datos sintéticos con huecos."""
    p = _panel(T=V.AÑOS.size, cols=V.PAISES[:4]).set_axis(V.AÑOS)
    p.iloc[5:9, 1] = np.nan
    ev = [(V.PAISES[0], 1890), (V.PAISES[0], 1960), (V.PAISES[1], 1876), (V.PAISES[3], 2003)]
    of = E.efecto_panel(p, pd.DataFrame(ev, columns=["pais", "año"]), H)
    mio = V.efecto_pais(V.acum(p.to_numpy(float), H), list(p.columns), ev, H)
    assert len(mio) == of["n"]
    assert np.mean([x[2] for x in mio]) == pytest.approx(of["efecto"], abs=1e-12)


def test_placebo_propio_reproduce_el_oficial_corregido():
    p = _panel(T=V.AÑOS.size, cols=V.PAISES[:3]).set_axis(V.AÑOS)
    ev = [(V.PAISES[0], 1890), (V.PAISES[0], 1960), (V.PAISES[1], 1930), (V.PAISES[2], 1980)]
    of = E.placebo_panel(p, pd.DataFrame(ev, columns=["pais", "año"]), 2, False, 5, n_rep=40, semilla=5, excluir_años=frozenset(V.WAR),
                         solo_con_dato=True)
    usados = {}
    for c, a in ev:
        usados.setdefault(c, []).append(a)
    mio = V.placebo_pais(V.acum(p.to_numpy(float), 2), list(p.columns), {c: len(v) for c, v in usados.items()},
                         usados, 2, 5, 40, 5)
    np.testing.assert_allclose(mio, of, atol=1e-12)
