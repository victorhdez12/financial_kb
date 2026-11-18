"""Tests SINTÉTICOS de la regla del BORRADOR de B2 «compra en caídas» (scripts/b2_borrador.py; spec en
docs/factors/B2_spec_borrador.md). Sin warehouse ni red."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts import b2_borrador as B2


def _s(vals, desde="2000-01"):
    return pd.Series(vals, index=pd.period_range(desde, periods=len(vals), freq="M"), dtype=float)


def test_pesos_suman_uno_y_oro_fijo():
    assert B2.NORMAL == {"rv": 0.70, "rf": 0.15, "oro": 0.15}
    assert B2.COMPRA == {"rv": 0.80, "rf": 0.05, "oro": 0.15}
    for e in (True, False):
        w = B2.pesos_b2(e)
        assert sum(w.values()) == pytest.approx(1.0) and w["oro"] == 0.15 and min(w.values()) >= 0


def test_caida_desde_maximo_12_cierres():
    nivel = _s([100] * 11 + [120, 90] + [100] * 12)
    dd = B2.caida_desde_maximo(nivel)
    assert dd.iloc[:11].isna().all()                       # hacen falta 12 cierres
    assert dd.iloc[11] == pytest.approx(0.0)               # nuevo máximo
    assert dd.iloc[12] == pytest.approx(90 / 120 - 1)      # −25 %
    assert dd.iloc[22] == pytest.approx(100 / 120 - 1)     # el máximo de 120 (t = 11) sigue en la ventana t−11 … t
    assert dd.iloc[23] == pytest.approx(0.0)               # sale de la ventana: el «máximo de 12 m» se olvida
    assert (dd.dropna() <= 1e-12).all()


def test_entrada_salida_con_histeresis():
    x = 0.15
    dd = _s([0, -0.10, -0.15, -0.20, -0.10, -0.08, -0.07, -0.16, 0.0])
    e = B2.estado_compra(dd, x).tolist()
    #        0      −10    −15(entra) −20   −10(sigue) −8(sigue) −7,5≥? −7 sale  −16 entra  0 sale
    assert e == [False, False, True, True, True, True, False, True, False]


def test_sin_histeresis_y_nan_mantiene():
    dd = _s([-0.2, np.nan, -0.149, -0.16])
    assert B2.estado_compra(dd, 0.15, salida_frac=1.0).tolist() == [True, True, False, True]


def test_calibrar_umbral_percentil_y_redondeo():
    dd = _s(list(-np.arange(100) / 1000))                  # 0, −0,1 %, … −9,9 %
    x = B2.calibrar_umbral(dd, 0.20)
    assert x == pytest.approx(round(-np.quantile(dd, 0.20), 3)) and x > 0
    with pytest.raises(ValueError):
        B2.calibrar_umbral(_s([0.0] * 30), 0.20)           # sin caídas no hay umbral


def test_decision_un_cierre_y_falla_cerrado():
    niv = _s([100] * 11 + [80])
    d = B2.decision_b2(niv, 0.147, previo=False)
    assert d["compra"] and d["cambio"] and d["pesos"]["rv"] == 0.80 and d["dd_12m"] == pytest.approx(-0.2)
    d2 = B2.decision_b2(_s([100] * 11 + [95]), 0.147, previo=True)       # −5 % ≥ −7,35 %: vuelve a NORMAL
    assert not d2["compra"] and d2["cambio"] and d2["pesos"]["rv"] == 0.70
    d3 = B2.decision_b2(_s([100] * 11 + [90]), 0.147, previo=True)       # −10 %: entre −X y −X/2, mantiene
    assert d3["compra"] and not d3["cambio"]
    with pytest.raises(RuntimeError):
        B2.decision_b2(_s([100] * 11), 0.147, previo=False)


def test_objetivo_b1_vivo_coincide_con_live():
    from src.paper import live as L
    assert (B2.SIGMA_STAR_B1, B2.RV_MIN_B1, B2.UMBRAL_B1) == (L.SIGMA_STAR, L.RV_MIN, L.UMBRAL)
    alt = np.tile([1.0, -1.0], 12)
    r = _s(np.r_[0.01 * alt, 0.09 * alt], "1990-01")      # σ̂ ≈ 3,6 % y luego ≈ 32 %
    o = B2.objetivo_b1_vivo(r, r.index)
    assert o["rv"].iloc[12] == pytest.approx(0.70)
    assert 0.55 - 1e-9 <= o["rv"].iloc[-1] < 0.55 + 0.025     # cerca del suelo; el umbral de 2,5 pp frena el último paso
    assert np.allclose(o.sum(axis=1), 1.0)


def test_potencia_analitica_y_bootstrap():
    assert B2.anios_para_distinguir(0.01, 0.03) == pytest.approx(((1.645 + 0.8416) * 3) ** 2)
    assert B2.anios_para_distinguir(0.0, 0.03) == float("inf")
    rng = np.random.default_rng(2)
    d = pd.Series(rng.normal(0, 0.01, 360))
    assert B2.potencia_bootstrap(d, 5, n=500, mu_objetivo=0.0) < 0.15          # tamaño ≈ 5 %
    assert B2.potencia_bootstrap(d, 30, n=500, mu_objetivo=0.05) > 0.9         # efecto grande: se detecta
