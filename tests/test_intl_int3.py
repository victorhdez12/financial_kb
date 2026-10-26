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


def _panel_persistente(semilla, n_pais=12, años=120, phi=0.6):
    """Estado en rachas (persistente, común a todos los países como un régimen global) y choque común AR(1) (épocas de
    inflación o de tipos compartidas por todos los países, como en bonos y letras), más ruido de país."""
    rng = np.random.default_rng(semilla)
    estado, choque = np.zeros(años), np.zeros(años)
    for t in range(1, años):
        estado[t] = estado[t - 1] if rng.random() < 0.8 else 1 - estado[t - 1]
        choque[t] = phi * choque[t - 1] + rng.normal(0, 0.05)
    filas = []
    for c in range(n_pais):
        filas.append(pd.DataFrame({"pais": f"P{c}", "anio": np.arange(1880, 1880 + años), "d": estado,
                                   "y": choque + rng.normal(0, 0.1, años)}))
    return pd.concat(filas, ignore_index=True)


def test_driscoll_kraay_corrige_la_autocorrelacion():
    fp_cr2, fp_dk = [], []
    for s in range(80):
        df = _panel_persistente(s)
        fp_cr2.append(I.contraste(df.y, df.d, df.pais, df.anio)["p"] < 0.05)
        fp_dk.append(I.driscoll_kraay(df.y, df.d, df.pais, df.anio, lags=6)["p"] < 0.05)
    assert np.mean(fp_cr2) > 0.10 and np.mean(fp_dk) < np.mean(fp_cr2)   # CR2 por año no ve la autocorrelación común


def test_p_placebo():
    df = _panel_persistente(1, años=60)
    r = I.p_placebo(df.y, df.d, df.pais, df.anio)
    assert 0 < r["p_empirico"] <= 1 and r["desplazamientos"] == 60 - 2 * I.DESFASE_MIN + 1


def test_driscoll_kraay_igual_efecto_que_contraste():
    df = _panel(efecto=-0.05)
    a, b = I.contraste(df.y, df.d, df.pais, df.anio), I.driscoll_kraay(df.y, df.d, df.pais, df.anio)
    assert a["efecto"] == pytest.approx(b["efecto"])


def test_efectos_pais_sin_año_quita_el_choque_comun():
    df = _panel(efecto=-0.08, choque_año=0.3)
    ef0, ef1 = I.efectos_pais(df.y, df.d, df.pais), I.efectos_pais_sin_año(df.y, df.d, df.pais, df.anio)
    assert ef1["var"].mean() < ef0["var"].mean()
