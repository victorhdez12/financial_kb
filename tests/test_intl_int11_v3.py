"""Tests SINTÉTICOS de INT-11 v3 (docs/int/INT11_v3_diseno.md). Ningún dato real."""
from __future__ import annotations

import numpy as np
import pytest

from src.intl import escenarios as E
from tests.sint_int11 import panel


@pytest.fixture(scope="module")
def filas():
    return E.preparar_filas(panel(), covariables=("termo",))


# ------------------------------------------------------------------ v1 y v2 intactos
def test_config_v2_reproduce_v2_bit_a_bit(filas):
    """Valores calculados con src/intl/escenarios.py de main (v2 congelado, 3995fd4) con la misma semilla."""
    g = E.Generador(E.Config.v2()).ajustar(filas)
    e = g.simular("P01", "sobrecalentamiento", horizonte=4, n_lotes=10, por_lote=50, semilla=3)
    assert float(np.nansum(e.rent)) == 66.33919133266853
    assert float(np.nansum(e.inflacion)) == 114.18559230076
    assert int(e.regimen.sum()) == 1727
    assert float(np.nansum(g.simular("ZZZ", 2, horizonte=2, n_lotes=10, por_lote=50, semilla=5).rent)) == \
        -95.36156658718585
    gt = E.Generador(E.Config.v2(modo="t")).ajustar(filas)
    assert float(np.nansum(gt.simular("P01", 2, horizonte=3, n_lotes=10, por_lote=50, semilla=4).rent)) == \
        -122.43641674248751
    assert g.escala_resumen["curtosis"] == [0.32, -0.23, 0.0, 0.1, 0.12]
