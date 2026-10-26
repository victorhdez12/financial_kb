"""Tests SINTÉTICOS de src/intl/regimes.py."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.intl import regimes as G


def test_cuadrante_y_frontera():
    out = G.cuadrante(pd.Series([0.9, 0.5]), pd.Series([0.1, 0.5]))
    assert out["cuadrante"].iloc[0] == "expansion" and not out["frontera"].iloc[0]
    assert out["frontera"].iloc[1]
    con_hueco = G.cuadrante(pd.Series([np.nan, 0.9]), pd.Series([0.2, 0.2]))
    assert pd.isna(con_hueco["cuadrante"].iloc[0]) and con_hueco["cuadrante"].iloc[1] == "expansion"


def test_etiqueta_relativa_y_truncada():
    idx = pd.RangeIndex(1950, 2005)
    crec = pd.Series(np.where(np.arange(len(idx)) % 10 < 5, 0.04, 0.0), index=idx)
    infl = pd.Series(0.05, index=idx)
    e = G.etiqueta(crec, infl, G.VENTANA_ANUAL)
    assert e["truncada"].iloc[-1] and e["truncada"].iloc[0] and not e["truncada"].iloc[20]
    assert set(e["cuadrante"].dropna()) <= set(G.CUADRANTES.values())


def test_recesiones_anuales():
    pib = pd.Series([1, 2, 3, 2.5, 2.4, 3, 4, 3.9, 5], index=range(1900, 1909), dtype=float)
    crisis = pd.Series(0, index=range(1895, 1915)); crisis[1906] = 1
    r = G.recesiones_anuales(pib, crisis)
    assert r[["pico", "valle"]].values.tolist() == [[1902, 1904], [1906, 1907]]
    assert r["tipo"].tolist() == ["normal", "financiera"]


def test_bry_boschan_ciclo_sinusoidal():
    t = np.arange(240)
    s = pd.Series(np.sin(2 * np.pi * t / 60) + 0.002 * t, index=pd.date_range("1960-01-01", periods=240, freq="MS"))
    bb = G.bry_boschan(s)
    picos = bb[bb.tipo == "pico"]
    assert 3 <= len(picos) <= 4                                   # periodo de 60 meses en 20 años
    assert all(bb.tipo.iloc[i] != bb.tipo.iloc[i + 1] for i in range(len(bb) - 1))


def test_bry_boschan_ignora_baches_cortos():
    s = pd.Series(np.linspace(0, 1, 120), index=pd.date_range("1960-01-01", periods=120, freq="MS"))
    s.iloc[60:63] -= 0.05                                         # bache de 3 meses: no es un ciclo
    assert len(G.bry_boschan(s)) == 0


def test_concordancia():
    T = pd.Timestamp
    c = G.concordancia([T("1980-03-01"), T("1990-08-01")], [T("1980-01-01"), T("1990-07-01"), T("2001-03-01")], 6)
    assert c["detectados"] == 2 and c["pct"] == round(2 / 3, 3) and c["desfase_medio_meses"] == 1.5
