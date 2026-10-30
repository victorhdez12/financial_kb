"""Tests sintéticos del script de potencia de INT-8 (sin datos reales)."""
import numpy as np
import pandas as pd

from scripts import int8_potencia as S


def test_auc_e_influencia_coinciden_con_mann_whitney():
    rng = np.random.default_rng(0)
    y = (rng.random(300) < 0.2).astype(int)
    s = rng.standard_normal(300) + y
    a, infl = S.influencia_auc(s, y)
    pos, neg = s[y == 1], s[y == 0]
    ref = np.mean([(p > n) + 0.5 * (p == n) for p in pos for n in neg])
    assert np.isclose(a, ref)
    assert abs(infl.sum()) < 1e-12


def test_episodios_agrupan_entradas_cercanas():
    f = [pd.Period(x, "M") for x in ("1974-04", "1974-07", "1975-01", "1980-07", "1980-10", "1990-01")]
    e = S.episodios(f, 6)
    assert [len(x) for x in e] == [3, 2, 1]


def test_recesion_tecnica_dos_caidas():
    q = pd.date_range("1960-01-01", periods=12, freq="QS")
    pib = pd.Series([100, 101, 102, 101, 100, 101, 102, 103, 102, 103, 104, 105], index=q, dtype=float)
    est, ent = S.fechado_pib_t(pib)
    assert [str(x) for x in ent] == ["1960Q4"]          # caen 1960Q4 y 1961Q1; la caída aislada de 1962Q1 no entra
    assert est["en_rec"].loc[pd.Period("1961Q1")] and not est["en_rec"].loc[pd.Period("1961Q2")]


def test_filas_en_riesgo_marca_las_h_previas():
    meses = pd.period_range("1960-01", "1961-12", freq="M")
    est = pd.Series(0.0, index=meses)
    est[pd.Period("1960-10", "M"):pd.Period("1961-03", "M")] = 1.0
    df = S.filas_en_riesgo(est, {pd.Period("1960-10", "M")}, 3, None, "X")
    pos = list(df[df.y == 1].m.astype(str))
    assert pos == ["1960-07", "1960-08", "1960-09"]
    assert "1960-10" not in set(df.m.astype(str))       # en recesión: fuera del riesgo
