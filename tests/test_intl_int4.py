"""Tests sintéticos del motor de INT-4 (sin datos reales salvo el de equivalencia, que solo compara FILAS de objetivos)."""
import numpy as np
import pandas as pd
import pytest

from src.intl import int4 as M


def _datos(n=1500, b=(-1.5, 1.0, 0.0), semilla=0, paises=8):
    rng = np.random.default_rng(semilla)
    X = rng.normal(size=(n, 2))
    p = 1 / (1 + np.exp(-(b[0] + X @ np.array(b[1:]))))
    y = (rng.random(n) < p).astype(float)
    pais = np.array([f"P{i % paises}" for i in range(n)])
    t = 1871 + (np.arange(n) // paises) % 134
    return X, y, pais, t


def test_logit_recupera_coeficientes():
    X, y, _, _ = _datos(n=20000, b=(-1.0, 0.8, -0.5))
    b = M.logit_fit(X, y)
    assert np.allclose(b, [-1.0, 0.8, -0.5], atol=0.07)


def test_auc_con_empates():
    y = np.array([0, 0, 1, 1])
    assert M.auc(y, np.array([0.1, 0.4, 0.35, 0.8])) == 0.75
    assert M.auc(y, np.array([0.5, 0.5, 0.5, 0.5])) == 0.5


def test_comparar_detecta_indicador_util_y_no_el_inutil():
    X, y, pais, t = _datos(n=2000, b=(-1.5, 0.3, 1.0), semilla=1)
    f = pd.DataFrame({"pais": pais, "t": t, "y": y})
    util = M.comparar(f, X[:, :1], X[:, 1:2])
    ruido = M.comparar(f, X[:, :1], np.random.default_rng(9).normal(size=(2000, 1)))
    assert util["d_auc"] > 0.1 and util["d_auc_ic95"][0] > 0 and util["d_logloss"] < 0 and util["p_bloques"] < 0.01
    assert abs(ruido["d_auc"]) < 0.03 and (ruido["d_auc"] < 0 or ruido["p_bloques"] > 0.05)   # ruido: no mejora
    assert 0.7 < util["calibracion"]["pendiente"] < 1.3


def test_desplazar_panel_circular():
    p = pd.DataFrame({"A": np.arange(M.L, dtype=float)}, index=range(M.A0, M.A1 + 1))
    q = M.desplazar_panel(p, 6)
    assert q.loc[M.A0 + 6, "A"] == 0 and q.loc[M.A0, "A"] == M.L - 6


def test_placebo_y_matriz():
    años = range(M.A0, M.A1 + 1)
    rng = np.random.default_rng(3)
    pan = {"C1": pd.DataFrame(rng.normal(size=(M.L, 3)), index=años, columns=["A", "B", "C"])}
    filas = pd.DataFrame([(c, t) for c in "ABC" for t in range(1880, 2000)], columns=["pais", "t"])
    x = M.matriz(filas, pan, ["C1"])[:, 0]
    filas["y"] = (x + rng.normal(0, 0.5, len(x)) > 1).astype(float)
    B1 = rng.normal(size=(len(filas), 1))
    r = M.comparar(filas, B1, M.matriz(filas, pan, ["C1"]), temporal_ok=False)
    pl = M.placebo(filas, B1, pan, ["C1"], r["d_auc"])
    assert pl["desplazamientos"] == len(M.KS) and pl["p_placebo"] == pytest.approx(1 / (1 + len(M.KS)))


def test_temporal_solo_usa_pasado():
    X, y, pais, t = _datos(n=3000, semilla=4)
    p = M.temporal(X, y, t, 1)
    assert np.isnan(p[t < 1950]).all() and np.isfinite(p[t >= 1950]).all()


def test_objetivos_iguales_que_los_de_la_potencia():
    from scripts import int4_potencia as A
    from scripts import int4b_potencia as Bb
    rec = pd.DataFrame({"pais": ["USA", "USA", "GBR"], "pico": [1900, 1920, 1910], "valle": [1901, 1922, 1911],
                        "tipo": ["normal", "financiera", "normal"]})
    años = {c: set(range(1870, 2005)) for c in A.NUCLEO}
    for h in (1, 2):
        a = A.objetivo_recesion_anual(rec, años, h, 1871, True)
        b = M.obj_entrada(rec, años, A.NUCLEO, h, 1871, True)
        assert a[["pais", "t", "y"]].reset_index(drop=True).equals(b[["pais", "t", "y"]].reset_index(drop=True))
        a = Bb.objetivo_salida_recesion(rec, años, h, 1871, True)
        b = M.obj_salida(rec, años, A.NUCLEO, h, 1871, True)
        assert a[["pais", "t", "y"]].reset_index(drop=True).equals(b[["pais", "t", "y"]].reset_index(drop=True))
    rng = np.random.default_rng(0)
    pi = pd.DataFrame([{"pais": c, "año": y, "p_i_alta": rng.random(), "truncada": False}
                       for c in A.NUCLEO for y in range(1870, 2005)])
    for sube in (True, False):
        a = Bb.objetivo_inflacion(pi, 1, 1871, True, sube)
        b = M.obj_inflacion(pi, A.NUCLEO, 1, 1871, True, sube)
        assert a[["pais", "t", "y"]].reset_index(drop=True).equals(b[["pais", "t", "y"]].reset_index(drop=True))
