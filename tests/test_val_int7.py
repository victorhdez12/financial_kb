"""Tests del Validador de INT-7 (sintéticos, sin datos reales).

1. Documenta el hallazgo principal: con un efecto real, el bootstrap nulo del prerregistro (§3.2: ê = y − ȳ_i, años en
   bloques de 5) aplicado con el código OFICIAL (src/intl/int7) da una t nula muy desplazada hacia la t observada; con
   bloques de 1 año (Nelson-Kim), no. Es una propiedad del diseño congelado, no un error del código.
2. El código independiente del Validador (scripts/val_int7.py: MCO con ficticias y DK propio) coincide con el oficial.
"""
import numpy as np

from scripts import val_int7 as W
from src.intl import int7 as V
from tests.test_intl_int7 import filas_1, panel_ar1


def test_bootstrap_bloques5_reintroduce_el_efecto_en_el_nulo():
    rng = np.random.default_rng(0)
    X, Y = panel_ar1(rng, 100, 5, 0.8, -0.8, b=0.3, faltan=False)
    d = V.Diseno(filas_1(X, Y), 1, False, np.arange(100), np.isfinite(X))
    t0 = float(d.ols(X, Y)["t"][0])
    par = V.residuos_pares(d, X, Y)
    m5 = V.bootstrap(par, {"d": d}, 99, np.random.default_rng(9), bloque=5)["d"].mean()
    m1 = V.bootstrap(par, {"d": d}, 99, np.random.default_rng(9), bloque=1)["d"].mean()
    assert t0 > 5
    assert m1 < 1.5                     # bloques de 1 año: solo el sesgo de Stambaugh
    assert m5 > m1 + 2.5                # bloques de 5 años: el "nulo" arrastra parte del efecto real


def test_bootstrap_irrestricto_no_reintroduce_el_efecto():
    """Variante a posteriori del Validador (residuo sin la parte predecible, luego b = 0, bloques de 5): sin desplazamiento."""
    rng = np.random.default_rng(0)
    X, Y = panel_ar1(rng, 100, 5, 0.8, -0.8, b=0.3, faltan=False)
    P = W.pares_sint(X, Y, irrestricto=True)
    tb = np.array([W.replica(P, np.random.default_rng(k), 5) for k in range(99)])
    assert P["t0"] > 5 and tb.mean() < 1.5


def test_dk_independiente_coincide_con_el_oficial_una_y_dos_vias():
    rng = np.random.default_rng(1)
    X, Y = panel_ar1(rng, 80, 5, 0.7, -0.6, b=0.2)
    f = filas_1(X, Y)
    ti, tj = np.nonzero(f)
    for anio in (False, True):
        d = V.Diseno(f, 1, anio, np.arange(1900, 1980), np.isfinite(X))
        r = d.ols(X, Y)
        Dm = np.eye(5)[tj]
        if anio:
            Dm = np.column_stack([Dm, np.eye(80)[ti][:, sorted(set(ti))[1:]]])
        b, t = W.dk(np.column_stack([X[ti, tj], Dm]), Y[ti + 1, tj], 1900 + ti)
        assert np.isclose(b, r["b"][0]) and np.isclose(t, r["t"][0])


def test_tstat_rapido_del_validador_coincide_con_dk_completo():
    rng = np.random.default_rng(2)
    X, Y = panel_ar1(rng, 60, 4, 0.7, -0.6, b=0.2, faltan=False)
    f = filas_1(X, Y)
    ti, tj = np.nonzero(f)
    for anio in (False, True):
        ts = W.TStat(tj, ti, anio)
        Dm = np.eye(4)[tj]
        if anio:
            Dm = np.column_stack([Dm, np.eye(60)[ti][:, sorted(set(ti))[1:]]])
        ref = W.dk(np.column_stack([X[ti, tj], Dm]), Y[ti + 1, tj], ti)
        assert np.allclose(ts(X[ti, tj], Y[ti + 1, tj]), ref)
