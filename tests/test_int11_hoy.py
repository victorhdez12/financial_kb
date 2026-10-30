"""Tests sintéticos del estado en vivo de INT-11 (src/report/escenarios_vivo.py)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.report import escenarios_vivo as V


def _series(infl_anual=0.02, caida_final=0.0):
    m = pd.date_range("2005-01-01", "2025-12-01", freq="MS")
    cpi = pd.Series(100 * np.exp(infl_anual * (np.arange(len(m)) / 12)), index=m)
    q = pd.date_range("2005-01-01", "2026-04-01", freq="QS")
    pib = pd.Series(np.exp(0.005 * np.arange(len(q))), index=q)
    pib[q.year >= 2025] *= (1 - caida_final)
    return cpi, pib


def test_estado_expansion_y_ultimo_año_completo():
    cpi, pib = _series(0.02)
    e = V.estado_pais(cpi, pib)
    assert e["año"] == 2025                       # 2026 no tiene 12 meses de IPC ni 4 trimestres
    assert abs(e["inflacion"] - 0.02) < 1e-6 and e["brecha_pib_total"] > 0 and e["regimen"] == "expansion"


def test_estado_estanflacion():
    cpi, pib = _series(0.06, caida_final=0.25)
    e = V.estado_pais(cpi, pib)
    assert e["regimen"] == "estanflacion"


def test_sin_datos():
    cpi, pib = _series()
    assert V.estado_pais(cpi[cpi.index.year < 2007], pib)["regimen"] is None


def test_anual_completo():
    cpi, _ = _series()
    a = V.anual_completo(cpi.iloc[:-1], 12)
    assert 2025 not in a.index and 2024 in a.index
