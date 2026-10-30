"""Tests del validador independiente de P-DEV-INT12 (docs/validation/2026-10-30_int12.md). Sintéticos, sin datos reales."""
import numpy as np
import pandas as pd
import pytest

from src.intl import int12 as M


def test_qlike_escala_correcta_y_propia():
    rng = np.random.default_rng(0)
    y = rng.chisquare(5, 20000) / 5 * 0.002          # "RV" positiva
    f = np.full_like(y, 0.0015)
    assert np.allclose(M.qlike(y, y), 0.0)
    # invariante a la escala común (unidades: decimales², %², mensual/anual)
    assert np.allclose(M.qlike(f * 1e4, y * 1e4), M.qlike(f, y))
    # propia: la previsión constante que minimiza la QLIKE media es la media de la RV
    grid = np.linspace(0.5, 1.5, 201) * y.mean()
    best = grid[np.argmin([M.qlike(np.full_like(y, g), y).mean() for g in grid])]
    assert best == pytest.approx(y.mean(), rel=0.01)
    # asimétrica: infra-prever cuesta más que sobre-prever en la misma proporción
    assert M.qlike(0.5, 1.0) > M.qlike(2.0, 1.0)


def test_retardos_nw_del_prerregistro():
    assert M.lags_nw(659, 1) == 6
    assert M.lags_nw(657, 3) == 8


def test_dm_sin_retardos_es_t_de_la_media():
    rng = np.random.default_rng(1)
    d = rng.standard_normal(500) + 0.1
    r = M.dm(d, 0)
    assert r["t"] == pytest.approx(d.mean() / (d.std(ddof=0) / np.sqrt(len(d))))
    # con autocorrelación positiva, la varianza HAC crece y el t baja
    e = np.convolve(rng.standard_normal(600), np.ones(6) / 6, mode="valid")[:500] + 0.05
    assert M.dm(e, 6)["ee"] > M.dm(e, 0)["ee"]


def test_harx_invariante_a_reescalar_x():
    """Descarta que el signo de C2 venga del escalado de los rasgos: MCO no depende de la unidad de X."""
    rng = np.random.default_rng(2)
    n = 400
    F = pd.DataFrame(rng.standard_normal((n, len(M.HAR + M.X))), columns=M.HAR + M.X)
    y = -9 + F[M.HAR].values @ np.array([0.2, 0.3, 0.4]) + rng.standard_normal(n) * 0.5
    F2 = F.copy()
    F2[M.X] = F2[M.X] * 100 + 7
    nd = np.full(n, 21)
    a = M.Modelo("harx").ajustar(F, y).prever(F, nd)
    b = M.Modelo("harx").ajustar(F2, y).prever(F2, nd)
    assert np.allclose(a, b, rtol=1e-8)


def test_rasgos_diarios_solo_usan_datos_hasta_el_origen():
    rng = np.random.default_rng(3)
    idx = pd.bdate_range("1990-01-01", periods=600)
    r = pd.Series(rng.standard_normal(600) * 0.01, index=idx)
    F = M.rasgos_diarios(r)
    m = pd.Period("1991-03", "M")
    r2 = r.copy()
    r2[r2.index > r.index[r.index.to_period("M") == m].max()] *= 20     # todo lo posterior al origen de m
    F2 = M.rasgos_diarios(r2)
    assert np.allclose(F.loc[m], F2.loc[m])
    assert not np.allclose(F.loc[m + 1, "lrv5"], F2.loc[m + 1, "lrv5"])
