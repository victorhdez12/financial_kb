"""Tests del VALIDADOR para INT-11 v2 (docs/validation/2026-10-30_int11v2.md). Sintéticos: ningún dato real.

(1) LOCO sin fuga con Config.v2: el país excluido no entra en la escala jerárquica (media del año, factores, m, τ),
    ni en las transiciones, ni en el pool; destrozar sus datos no cambia ni un sorteo.
(2) Hallazgo: la curtosis AGRUPADA que usa el error de medida del factor de país se infla con la propia
    heterogeneidad de escala entre países (con choques normales por país, la agrupada sale > 1 y el factor del país
    volátil se encoge mucho más que con la curtosis estandarizada por país).
(3) Un mes de IPC perdido se interpola en log (media geométrica de los vecinos) y no mueve la inflación móvil.
(4) Mezcla suave (propuesta v3): los cuantiles de la mezcla quedan entre los de las dos componentes y en los
    extremos w = 0 / 1 coinciden con la componente.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.intl import escenarios as E
from tests.sint_int11 import panel


def _filas_hetero(semilla=5, n_paises=8, factor=2.5):
    df = panel(n_paises=n_paises, semilla=semilla)
    rng = np.random.default_rng(semilla + 1)
    sd = np.where(df["pais"].isin([f"P{i:02d}" for i in range(n_paises // 2)]), 0.10 * factor, 0.10)
    comun = df.groupby("año")["bolsa"].transform("mean")
    df["bolsa"] = comun + sd * rng.standard_normal(len(df))            # choque propio NORMAL, escala por país
    return E.preparar_filas(df)


def test_loco_v2_sin_fuga_del_pais_excluido():
    f = _filas_hetero()
    fuera = "P01"
    tr = f["pais"].to_numpy() != fuera
    g1 = E.Generador(E.Config.v2()).ajustar(f[tr])
    f2 = f.copy()
    m = f2["pais"] == fuera
    f2.loc[m, list(E.ACTIVOS)] = f2.loc[m, list(E.ACTIVOS)] * 5 + 1
    f2.loc[m, ["s", "s_prev"]] = 2
    g2 = E.Generador(E.Config.v2()).ajustar(f2[tr])
    assert fuera not in g1.escala_post and fuera not in g1.paises
    assert np.array_equal(g1.escala_pred[0], g2.escala_pred[0]) and np.array_equal(g1.escala_pred[1], g2.escala_pred[1])
    assert np.array_equal(g1.ybar, g2.ybar, equal_nan=True)
    e1 = g1.simular(fuera, 1, horizonte=2, n_lotes=10, por_lote=50, semilla=9)
    e2 = g2.simular(fuera, 1, horizonte=2, n_lotes=10, por_lote=50, semilla=9)
    assert np.array_equal(e1.rent, e2.rent, equal_nan=True) and np.array_equal(e1.inflacion, e2.inflacion,
                                                                                 equal_nan=True)
    assert np.allclose(g1.posterior_transicion(fuera), g1.kappa * g1.p_panel)
    # control: con el país DENTRO del pool sí cambia (el test detectaría una fuga)
    g3 = E.Generador(E.Config.v2()).ajustar(f)
    assert fuera in g3.escala_post


def test_curtosis_agrupada_inflada_por_la_heterogeneidad():
    f = _filas_hetero(factor=2.5)
    g = E.Generador(E.Config.v2()).ajustar(f)
    kurt_motor = g.escala_resumen["curtosis"][0]
    dev = g.L[:, 0] - g.ybar[:, 0]
    zc = np.full_like(dev, np.nan)
    for c in g.paises:
        m = g.pais == c
        zc[m] = dev[m] / np.sqrt(np.nanmean(dev[m] ** 2))
    kurt_pais = np.nanmean(zc ** 4) / np.nanmean(zc ** 2) ** 2 - 3
    assert kurt_motor > 0.8                                            # mezcla de normales de distinta escala
    assert abs(kurt_pais) < 0.6                                        # dentro de cada país, normal
    # el país volátil (factor real 2,5 / media) queda encogido hacia el panel
    bruto = np.exp(np.log(np.sqrt(np.nanmean(dev[g.pais == "P00"] ** 2)) / np.sqrt(np.nanmean(dev ** 2))))
    post = g.escala_resumen["factor_pais"]["P00"][0]
    assert post < bruto


def test_un_mes_perdido_se_interpola_en_log():
    m = pd.date_range("2020-01-01", "2026-09-01", freq="MS")
    cpi = pd.Series(100 * np.exp(0.03 * np.arange(len(m)) / 12 + 0.002 * np.sin(np.arange(len(m)))), index=m)
    sin = cpi.drop(pd.Timestamp("2025-10-01"))
    w = E._mensual_completa(sin, 24)
    v = w[pd.Timestamp("2025-10-01")]
    esperado = np.sqrt(cpi[pd.Timestamp("2025-09-01")] * cpi[pd.Timestamp("2025-11-01")])
    assert v == pytest.approx(esperado, rel=1e-12)
    completo = E._mensual_completa(cpi, 24)
    i1 = np.log(w.iloc[12:].mean() / w.iloc[:12].mean())
    i0 = np.log(completo.iloc[12:].mean() / completo.iloc[:12].mean())
    assert abs(i1 - i0) < 5e-4


def test_mezcla_suave_cuantiles():
    from scripts.val_int11v2_suave import cuantiles_mezcla
    rng = np.random.default_rng(0)
    xa, xb = rng.normal(0, 1, 4000), rng.normal(3, 1, 4000)
    qa, qb = np.quantile(xa, [.05, .95]), np.quantile(xb, [.05, .95])
    q0 = cuantiles_mezcla(xa, xb, 1e-9)
    q1 = cuantiles_mezcla(xa, xb, 1 - 1e-9)
    assert q0[0] == pytest.approx(qa[0], abs=0.01) and q0[1] == pytest.approx(qa[1], abs=0.01)
    assert q1[0] == pytest.approx(qb[0], abs=0.01) and q1[1] == pytest.approx(qb[1], abs=0.01)
    qm = cuantiles_mezcla(xa, xb, 0.5)
    assert qa[0] - 0.01 <= qm[0] <= qb[0] and qa[1] <= qm[1] <= qb[1] + 0.01
