"""Tests sintéticos del script de potencia de INT-7 (sin datos reales)."""
import numpy as np
import pandas as pd

from scripts import int7_potencia as S
from src.intl import int3


def test_dk_t_coincide_con_driscoll_kraay():
    rng = np.random.default_rng(0)
    Tn, N = 60, 5
    x = rng.standard_normal((Tn, N))
    y = 0.3 * x + rng.standard_normal((Tn, N))
    m = np.ones((Tn, N), bool)
    m[:10, 0] = False
    xt, yt = S.desmediar(x, m, False), S.desmediar(y, m, False)
    cxx = np.nansum(xt * xt)
    b = np.nansum(xt * yt) / cxx
    t = S.dk_t(xt, np.zeros_like(xt), yt - b * xt, b, cxx, 0.0, 3, Tn, np.array([0.0]))[0]
    filas = [(i, t_, y[t_, i], x[t_, i]) for t_ in range(Tn) for i in range(N) if m[t_, i]]
    f = pd.DataFrame(filas, columns=["pais", "anio", "y", "x"])
    ref = int3.driscoll_kraay(f.y, f.x, f.pais.astype(str), f.anio, lags=3)
    assert np.isclose(t, ref["t"], rtol=1e-6)


def test_nula_sin_stambaugh_calibra_cerca_de_196():
    rng = np.random.default_rng(1)
    m = np.ones((120, 1), bool)
    sim = S.simular(m, 0.0, 0.0, 0.0, 1.0, 0.0, 1, False, np.array([0.0, 0.2]), 1500, rng)
    c = np.quantile(sim["t"][:, 0], 0.975)
    assert 1.75 < c < 2.2
    assert abs(np.mean(sim["bias0"])) < 0.02


def test_stambaugh_sesga_hacia_arriba_con_delta_negativo():
    rng = np.random.default_rng(2)
    m = np.ones((100, 1), bool)
    sim = S.simular(m, 0.9, 0.0, 0.0, 1.0, -0.9, 1, False, np.array([0.0]), 800, rng)
    assert np.mean(sim["bias0"]) > 0.01
