"""Tests sintéticos de INT-9 fase 1 (src/intl/int9.py). Sin datos reales."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import int3
from src.intl import int9 as K


def _panel(T=150, N=40, r=2, ruido=1.0, huecos=0.2, semilla=0):
    rng = np.random.default_rng(semilla)
    F = rng.standard_normal((T, r))
    L = rng.standard_normal((N, r))
    X = F @ L.T + ruido * rng.standard_normal((T, N))
    X[rng.random((T, N)) < huecos] = np.nan
    return X, F, L


def test_modulo_no_lee_datos():
    src = Path(K.__file__).read_text()
    assert "load_dev" not in src and "connect(" not in src and "read_parquet" not in src


def test_em_pca_recupera_factor_con_huecos():
    X, F, _ = _panel(r=1, huecos=0.3)
    e = K.em_pca(X, 1)
    assert abs(np.corrcoef(e["F"][:, 0], F[:, 0])[0, 1]) > 0.95
    assert np.allclose(e["F"].T @ e["F"] / len(X), np.eye(1), atol=1e-6)


def test_bai_ng_elige_dos():
    X, _, _ = _panel(r=2, N=60, T=150, ruido=1.0, huecos=0.1, semilla=1)
    assert K.bai_ng(X, 6)["IC_p2"] == 2


def test_paralelo_uno_y_ruido():
    rng = np.random.default_rng(2)
    X, _, _ = _panel(r=1, N=20, T=120, ruido=1.5, huecos=0.1, semilla=3)
    assert K.paralelo(X, 30, rng)["retenidos"] == 1
    Xn = rng.standard_normal((120, 20))
    assert K.paralelo(Xn, 30, rng)["retenidos"] == 0


def test_congruencia_y_alinear():
    rng = np.random.default_rng(4)
    L = rng.standard_normal((30, 3))
    L2 = L[:, [2, 0, 1]] * np.array([-1, 1, -1])
    out, cg = K.alinear(L, L2)
    assert np.allclose(out, L) and np.allclose(cg, 1)
    assert np.isclose(K.congruencia(L[:, 0], -L[:, 0]), -1)


def test_ari():
    a = [1, 1, 2, 2, 3, 3]
    assert K.ari(a, a) == 1.0
    assert np.isclose(K.ari(a, [7, 7, 5, 5, 9, 9]), 1.0)
    rng = np.random.default_rng(5)
    v = [K.ari(rng.integers(0, 4, 200), rng.integers(0, 4, 200)) for _ in range(30)]
    assert abs(np.mean(v)) < 0.02


def test_jerarquico_separa_dos_bloques():
    rng = np.random.default_rng(6)
    f1, f2 = rng.standard_normal(200), rng.standard_normal(200)
    X = np.column_stack([f1 + 0.5 * rng.standard_normal(200) for _ in range(4)]
                        + [f2 + 0.5 * rng.standard_normal(200) for _ in range(4)])
    et = K.jerarquico(K.corr_pares(X), 2)["etiquetas"]
    assert len(set(et[:4])) == 1 and len(set(et[4:])) == 1 and et[0] != et[4]


def test_bloques_y_coasignacion():
    rng = np.random.default_rng(7)
    ix = K.bloques(123, 10, rng)
    assert len(ix) == 123 and ix.min() >= 0 and ix.max() <= 122
    assert np.all(np.diff(ix[:10]) == 1)
    co = K.coasignacion(np.array([[1, 1, 2], [1, 2, 2]]))
    assert np.allclose(co, [[1, .5, 0], [.5, 1, .5], [0, .5, 1]])


def test_cubo_guerras_fuera_y_winsor():
    p = pd.DataFrame({"A": np.arange(100, dtype=float), "B": np.arange(100, dtype=float)}, index=range(1900, 2000))
    c = K.cubo({"x": p}, {("A", 1950)}, True)["x"]
    assert c.loc[1916].isna().all() and c.loc[1940].isna().all() and np.isnan(c.loc[1950, "A"])
    assert c.max().max() < 99


def test_apilar_filas_estandariza_dentro_de_pais():
    p = pd.DataFrame({"A": np.arange(30.0), "B": 10 + 5 * np.arange(30.0)}, index=range(1950, 1980))
    f = K.apilar_filas({"x": p}, ["A", "B"])
    assert np.allclose(f.groupby(level=0).x.mean(), 0) and np.allclose(f.groupby(level=0).x.std(), 1)


def test_dk_t_coincide_con_int3():
    rng = np.random.default_rng(8)
    T, N = 60, 6
    x = rng.standard_normal((T, N))
    y = 0.3 * x + rng.standard_normal((T, N))
    f = pd.DataFrame([(f"P{i}", t, y[t, i], x[t, i]) for t in range(T) for i in range(N)],
                     columns=["pais", "anio", "y", "x"])
    gi = pd.factorize(f.pais)[0]
    dm = lambda v: v - (np.bincount(gi, v) / np.bincount(gi))[gi]  # noqa: E731
    t = K.dk_t(dm(f.x.to_numpy()), dm(f.y.to_numpy()), f.anio.to_numpy(), 3)
    ref = int3.driscoll_kraay(f.y, f.x, f.pais, f.anio, lags=3)
    assert np.isclose(t, ref["t"], rtol=1e-6)


def test_pot_logit_tamano_y_potencia():
    rng = np.random.default_rng(9)
    n_p, n_t = 10, 80
    g = np.repeat([f"P{i}" for i in range(n_p)], n_t)
    anio = np.tile(np.arange(n_t), n_p)
    F = np.tile(rng.standard_normal(n_t), n_p)
    r = K.pot_logit(F, g, anio, 0.15, 0.3, [0.0, 1.2], 60, 0.05, rng)
    assert r["rejilla"][0]["potencia"] < 0.2
    assert r["rejilla"][1]["potencia"] > 0.8


def test_pot_mco_tamano_y_potencia():
    rng = np.random.default_rng(10)
    n_p, n_t = 10, 100
    g = np.repeat([f"P{i}" for i in range(n_p)], n_t)
    anio = np.tile(np.arange(n_t), n_p)
    F = np.tile(rng.standard_normal(n_t), n_p)
    r = K.pot_mco(F, g, anio, 0.1, 0.2, [0.0, 0.1], 200, 0.05, 3, rng)
    assert r["rejilla"][0]["potencia"] < 0.1
    assert r["rejilla"][1]["potencia"] > 0.8


def test_sobredispersion_uno_sin_agrupamiento():
    rng = np.random.default_rng(11)
    anio = np.repeat(np.arange(200), 14)
    y = (rng.random(len(anio)) < 0.15).astype(float)
    assert 0.7 < K.sobredispersion(y, anio) < 1.3
    y2 = K.sim_eventos(np.full(len(anio), -1.7), anio, 1.5, rng)
    assert K.sobredispersion(y2, anio) > 2
