"""Tests sintéticos del motor de INT-4-ML (sin datos reales)."""
import numpy as np

from src.intl import int4ml as ML
from scripts.int4_sensibilidad_liston import auc_estrat


def _datos(n=1500, inter=0.0, semilla=0):
    rng = np.random.default_rng(semilla)
    X = rng.normal(size=(n, 3))                       # col 0 = "B1", cols 1-2 = indicadores
    eta = -1.2 + 0.4 * X[:, 0] + 0.8 * X[:, 1] - 0.6 * X[:, 2] + inter * X[:, 1] * X[:, 2]
    y = (rng.random(n) < 1 / (1 + np.exp(-eta))).astype(float)
    g = np.array([f"P{i % 6}" for i in range(n)])
    t = 1871 + (np.arange(n) // 6) % 134
    return X, y, g, t


def test_l2_estandariza_en_el_pliegue_y_crea_interacciones():
    X, y, _, _ = _datos()
    m = ML.L2Inter(1).fit(X, y)
    D = m._diseño(X, False)
    assert D.shape[1] == 3 + 1 and np.allclose(D.mean(0), 0, atol=1e-9)


def test_l2_capta_la_interaccion():
    X, y, g, _ = _datos(n=4000, inter=1.5, semilla=1)
    p0 = ML.loco(ML.Logit, X, y, g)
    p1 = ML.loco(lambda: ML.L2Inter(1), X, y, g)
    assert auc_estrat(y, p1, g) - auc_estrat(y, p0, g) > 0.02


def test_gb_respeta_la_monotonia():
    X, y, _, _ = _datos(n=3000, semilla=2)
    m = ML.GB([0, +1, -1]).fit(X, y)
    rej = np.linspace(-3, 3, 50)
    Z = np.zeros((50, 3))
    Z[:, 1] = rej
    assert np.all(np.diff(m.predict(Z)) >= -1e-12)
    Z = np.zeros((50, 3))
    Z[:, 2] = rej
    assert np.all(np.diff(m.predict(Z)) <= 1e-12)


def test_fabrica_monotonia_del_prerregistro():
    gb = ML.fabrica("M-GB", "T2", 1, ["S1", "S2", "S3", "S4", "S5"])()
    assert gb.cst == [0, 1, -1, 1, -1, -1]
    gb = ML.fabrica("M-GB", "T1", 2, ["C1", "C2", "C4", "C5", "C6"])()
    assert gb.cst == [0, 0, -1, 1, 1, 1, -1]


def test_z_placebo():
    r = ML.z_placebo(0.3, np.array([0.0, 0.1, -0.1, 0.05, -0.05]))
    assert r["z"] > 3 and r["p_z"] < 0.01 and r["p_rangos"] == 1 / 6


def test_temporal_sin_futuro():
    X, y, _, t = _datos(n=2000, semilla=3)
    p = ML.temporal(ML.Logit, X, y, t)
    assert np.isnan(p[t < 1950]).all() and np.isfinite(p[t >= 1950]).all()
