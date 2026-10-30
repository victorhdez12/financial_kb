"""Tests sintéticos de P-DEV-INT12 (src/intl/int12.py y la puerta de scripts/int12_corrida.py). Sin datos reales."""
import numpy as np
import pandas as pd
import pytest

from src.intl import data as D
from src.intl import int12 as M


def _r(n=3000, seed=0, inicio="1990-01-01"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(inicio, periods=n)
    vol = np.exp(np.cumsum(rng.standard_normal(n) * 0.02) * 0.5) * 0.01
    return pd.Series(rng.standard_normal(n) * vol, index=idx)


def test_familia_int12_permitida_y_solo_esas():
    for s in ("aqr_mkt_usa_d", "TB3MS", "shiller_gs10"):
        assert D.permitida(s), s
    for s in ("aqr_mkt_usa_m_x", "TB6MS", "shiller_gs10x", "VIXCLS"):
        assert not D.permitida(s), s


def test_tabla_objetivos_usa_solo_meses_siguientes():
    r = _r(300)
    T = M.tabla_objetivos(r, 1)
    m = T.index[3]
    sig = r[r.index.to_period("M") == m + 1]
    assert np.isclose(T.loc[m, "rv"], (sig ** 2).sum()) and T.loc[m, "n_dias"] == len(sig)
    assert T.loc[m, "fin"] == sig.index.max() and T.loc[m, "origen"] < sig.index.min()
    assert T.index.max() < r.index.to_period("M").max()
    T3 = M.tabla_objetivos(r, 3)
    assert T3.index.max() == r.index.to_period("M").max() - 3


def test_rasgos_diarios_b1_es_varianza_de_12_meses():
    r = _r(800)
    F = M.rasgos_diarios(r)
    mens = (1 + r).groupby(r.index.to_period("M")).prod() - 1
    m = F.index[20]
    assert np.isclose(F.loc[m, "b1_var"], mens.loc[:m].iloc[-12:].var(ddof=1))
    dias = r[r.index.to_period("M") <= m]
    assert np.isclose(F.loc[m, "lrv21"], np.log((dias.iloc[-21:] ** 2).mean() + 1e-12))


def test_rasgos_x_retraso_un_mes_y_regimen_abril():
    meses = pd.period_range("2000-01", "2001-06", freq="M")
    idx = pd.date_range("1999-01-01", "2001-12-01", freq="MS")
    s = pd.Series(np.arange(len(idx), dtype=float), index=idx)
    reg = pd.DataFrame({"reg_infl": [0.0, 1.0, 0.0], "reg_brecha": [0.0, 0.0, 1.0]}, index=[1998, 1999, 2000])
    X = M.rasgos_x(meses, s + 1, s, s * 2, s, reg)
    assert X.loc[pd.Period("2000-05", "M"), "corto"] == s[pd.Timestamp("2000-04-01")]   # valor del mes anterior
    assert X.loc[pd.Period("2000-05", "M"), "credito"] == 1
    assert X.loc[pd.Period("2000-03", "M"), "reg_infl"] == 0.0     # marzo 2000 → año 1998
    assert X.loc[pd.Period("2000-04", "M"), "reg_infl"] == 1.0     # abril 2000 → año 1999
    assert X.loc[pd.Period("2001-04", "M"), "reg_brecha"] == 1.0   # abril 2001 → año 2000


def _tabla_sint(h=1, n=6000):
    r = _r(n, seed=3, inicio="1975-01-01")
    T = M.tabla_objetivos(r, h).join(M.rasgos_diarios(r))
    rng = np.random.default_rng(1)
    for c in M.X:
        T[c] = rng.standard_normal(len(T))
    return T


def test_ventana_creciente_embargo_y_reajuste_en_enero():
    T = _tabla_sint(h=3)
    ev = T.index[T.index >= pd.Period("1990-01", "M")]
    P, info = M.ventana_creciente(T, ev, T.index[3], 3, ("har", "harx", "b1_12m"))
    assert info["reajustes"] == len({m.year for m in ev})
    # embargo: alterar los objetivos de los 3 meses anteriores al primer origen no cambia su previsión
    T2 = T.copy()
    m0 = ev[0]
    for k in (1, 2):
        T2.loc[m0 - k, "rv"] *= 50
    P2, _ = M.ventana_creciente(T2, ev[:1], T.index[3], 3, ("har",))
    assert np.isclose(P.loc[m0, "f_har"], P2.loc[m0, "f_har"])
    T2.loc[m0 - 3, "rv"] *= 50                                  # este sí acaba antes del origen → sí entra
    P3, _ = M.ventana_creciente(T2, ev[:1], T.index[3], 3, ("har",))
    assert not np.isclose(P.loc[m0, "f_har"], P3.loc[m0, "f_har"])


def test_ventana_no_mira_el_futuro():
    T = _tabla_sint()
    ev = T.index[T.index >= pd.Period("1990-01", "M")]
    P, _ = M.ventana_creciente(T, ev[:12], T.index[3], 1, ("har", "gb"))
    T2 = T.copy()
    T2.loc[ev[12]:, "rv"] *= 100
    P2, _ = M.ventana_creciente(T2, ev[:12], T.index[3], 1, ("har", "gb"))
    assert np.allclose(P[["f_har", "f_gb"]], P2[["f_har", "f_gb"]])


def test_har_recupera_coeficientes_conocidos():
    rng = np.random.default_rng(5)
    F = pd.DataFrame(rng.standard_normal((4000, 3)), columns=M.HAR)
    y = 0.1 + F.values @ np.array([0.2, 0.3, 0.4]) + rng.standard_normal(4000) * 0.3
    m = M.Modelo("har").ajustar(F, y)
    assert np.allclose(m.beta, [0.1, 0.2, 0.3, 0.4], atol=0.03)
    assert np.isclose(m.smear, np.exp(0.5 * 0.09), atol=0.01)


def test_dm_holm_kupiec():
    rng = np.random.default_rng(2)
    assert M.dm(rng.standard_normal(600) + 0.3, 6)["p"] < 1e-4
    assert M.dm(rng.standard_normal(600) - 0.3, 6)["p"] > 0.99
    h = M.holm({"a": 0.01, "b": 0.03, "c": 0.04})
    assert h["a"]["p_holm"] == pytest.approx(0.03) and h["b"]["p_holm"] == pytest.approx(0.06)
    assert h["a"]["rechaza"] and not h["b"]["rechaza"] and h["c"]["p_holm"] == pytest.approx(0.06)
    k = M.kupiec(np.r_[np.ones(5), np.zeros(95)])
    assert k["p"] > 0.9 and M.kupiec(np.r_[np.ones(20), np.zeros(80)])["p"] < 0.001


def test_bootstrap_estacionario_detecta_media():
    rng = np.random.default_rng(4)
    assert M.bootstrap_estacionario_p(rng.standard_normal(300) + 0.4, reps=300) < 0.01
    assert M.bootstrap_estacionario_p(rng.standard_normal(300) - 0.4, reps=300) > 0.9


def test_contraste_mitades():
    idx = pd.period_range("1950-01", periods=100, freq="M")
    P = pd.DataFrame({"rv": np.ones(100), "f_a": np.full(100, 2.0), "f_b": np.ones(100)}, index=idx)
    c = M.contraste(P, "a", "b", 1, idx[50])
    assert c["ganancia"] == pytest.approx(1.0) and c["ganancia_mitad1"] == c["ganancia_mitad2"] == pytest.approx(1.0)


def test_corrida_se_niega_si_existe_salida(tmp_path, monkeypatch):
    from scripts import int12_corrida as C
    f = tmp_path / "int12_resultado.json"
    f.write_text("{}")
    monkeypatch.setattr(C, "SALIDA", f)
    with pytest.raises(SystemExit, match="ya existe"):
        C.main([])
