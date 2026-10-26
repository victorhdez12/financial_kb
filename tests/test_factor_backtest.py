"""Tests SINTÉTICOS del motor de P-DEV-FACT (src/factors/backtest.py): sin datos reales."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.factors import backtest as B

IDX = pd.period_range("1975-01", "1979-12", freq="M")


def _r(rv=0.01, rf=0.004, oro=0.0):
    return pd.DataFrame({"rv": rv, "rf": rf, "oro": oro}, index=IDX)


def test_estatica_sin_costes_ni_ter_es_media_ponderada(monkeypatch):
    monkeypatch.setattr(B, "TER", {"rv": 0, "rf": 0, "oro": 0})
    r = _r()
    res = B.simular(r, B.objetivo_fijo(IDX), coste_mult=0.0)
    assert res.neto.iloc[0] == pytest.approx(0.8 * 0.01 + 0.1 * 0.004)


def test_rebalanceo_en_diciembre_y_por_banda(monkeypatch):
    monkeypatch.setattr(B, "TER", {"rv": 0, "rf": 0, "oro": 0})
    res = B.simular(_r(rv=0.0, rf=0.0), B.objetivo_fijo(IDX))
    assert res.rotacion.sum() == pytest.approx(0.0)           # nada se mueve: no hay órdenes efectivas
    r = _r(rv=0.10, rf=0.0)                                    # la RV se dispara → sale de la banda
    res = B.simular(r, B.objetivo_fijo(IDX))
    assert (res.rotacion > 0).any() and res.pesos["rv"].max() < 0.80 + 0.05 + 0.03


def test_oro_se_ejecuta_un_mes_tarde(monkeypatch):
    monkeypatch.setattr(B, "TER", {"rv": 0, "rf": 0, "oro": 0})
    obj = B.objetivo_fijo(IDX, {"rv": 0.8, "rf": 0.2, "oro": 0.0})
    obj.iloc[3:] = [0.8, 0.1, 0.1]                              # el oro sube al 10 % al cierre del mes 3
    res = B.simular(_r(rf=0.0), obj, coste_mult=0.0, pesos_base={"rv": 0.8, "rf": 0.2, "oro": 0.0})
    assert res.pesos["oro"].iloc[4] == pytest.approx(0.0)       # rige t + 1 sin oro todavía
    assert res.pesos["oro"].iloc[5] > 0.09                      # ejecutado al cierre de t + 1


def test_estado_histeresis():
    g = pd.Series([1, -1, 1, -1, -1, -1, 1, 1, 1], dtype=float)
    assert B.estado(g, 0.0, 1).tolist() == [False, True, False, True, True, True, False, False, False]
    assert B.estado(g, 0.0, 3).tolist() == [False] * 5 + [True, True, True, False]


def test_vol_recorta_y_respeta_limites():
    rng = np.random.default_rng(0)
    idx = pd.period_range("1963-07", "1979-12", freq="M")
    vol = np.where(np.arange(len(idx)) > 150, 0.08, 0.03)
    rv = pd.Series(rng.normal(0, 1, len(idx)) * vol, index=idx)
    obj = B.objetivo_vol(rv, idx)
    assert obj["rv"].min() >= 0.65 - 1e-12 and obj["rv"].max() <= 0.80 + 1e-12
    assert obj["rv"].iloc[-1] < 0.80 and np.allclose(obj.sum(axis=1), 1.0)


def test_desuavizar_recupera_varianza_de_medias():
    rng = np.random.default_rng(1)
    d = rng.normal(0, 0.01, 22 * 3000)
    p = np.cumsum(d)
    medias = p.reshape(-1, 22).mean(axis=1)
    r = pd.Series(np.diff(medias))
    rho = r.autocorr(1)
    assert 0.2 < rho < 0.3                                      # efecto Working
    assert B.desuavizar(r, rho).std() == pytest.approx(0.01 * np.sqrt(22), rel=0.1)


def test_placebo_conserva_proporcion():
    s = pd.Series([True] * 30 + [False] * 70)
    b = B.barajar_bloques(s, 24, np.random.default_rng(2))
    assert b.sum() == 30 and len(b) == 100


def test_holm():
    assert B.holm({"a": 0.01, "b": 0.02, "c": 0.04}) == {"a": True, "b": True, "c": True}
    assert B.holm({"a": 0.01, "b": 0.03, "c": 0.04}) == {"a": True, "b": False, "c": False}
