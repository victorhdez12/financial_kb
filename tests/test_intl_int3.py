"""Tests SINTÉTICOS de src/intl/int3.py."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.intl import int3 as I


def _panel(efecto=0.0, n_pais=10, años=80, semilla=0, choque_año=0.1):
    rng = np.random.default_rng(semilla)
    filas = []
    choque = rng.normal(0, choque_año, años)
    for c in range(n_pais):
        d = (rng.random(años) < 0.3).astype(float)
        y = 0.02 * c + efecto * d + choque + rng.normal(0, 0.1, años)
        filas.append(pd.DataFrame({"pais": f"P{c}", "anio": np.arange(1900, 1900 + años), "d": d, "y": y}))
    return pd.concat(filas, ignore_index=True)


def test_contraste_recupera_efecto_y_cubre():
    df = _panel(efecto=-0.08)
    r = I.contraste(df.y, df.d, df.pais, df.anio)
    assert r["ic95"][0] < -0.08 < r["ic95"][1] and r["p"] < 0.01
    df0 = _panel(efecto=0.0, semilla=3)
    assert I.contraste(df0.y, df0.d, df0.pais, df0.anio)["p"] > 0.01


def test_cobertura_nula_con_choques_de_año():
    """Con choques comunes de año, el error agrupado por año mantiene la tasa de falsos positivos cerca del 5 %."""
    fp = np.mean([I.contraste(*(lambda df: (df.y, df.d, df.pais, df.anio))(_panel(semilla=s)))["p"] < 0.05
                  for s in range(60)])
    assert fp < 0.15


def test_encoger():
    ef = pd.DataFrame({"pais": list("ABCD"), "efecto": [-0.1, -0.08, -0.12, 0.05], "var": [0.001] * 4})
    out, mu, tau2 = I.encoger(ef)
    assert mu < 0 and tau2 > 0
    assert (out["encogido"] - mu).abs().le((out["efecto"] - mu).abs() + 1e-12).all()


def test_holm():
    assert I.holm({"a": 0.001, "b": 0.02, "c": 0.04}) == {"a": True, "b": True, "c": True}
    assert I.holm({"a": 0.001, "b": 0.03, "c": 0.04}) == {"a": True, "b": False, "c": False}


def test_desplazar_conserva_estructura():
    df = _panel(años=30)
    dk = I.desplazar(df.d, df.pais, df.anio, 7)
    assert dk.sum() == df.d.sum() and not dk.equals(df.d)
