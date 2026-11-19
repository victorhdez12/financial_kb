"""Motor de D1 (src/factors/d1.py) con datos sintéticos: ninguna rentabilidad real."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.factors import d1 as M

DIAS = pd.bdate_range("1990-01-01", periods=400)


def _r(**cols) -> pd.DataFrame:
    return pd.DataFrame({k: np.full(len(DIAS), v) if np.isscalar(v) else v for k, v in cols.items()}, index=DIAS)


def test_tendencia_toma_valores_de_tercios_y_espera_252_dias():
    rng = np.random.default_rng(0)
    r = _r(sube=0.001 + rng.normal(0, 1e-4, len(DIAS)), baja=-0.001 + rng.normal(0, 1e-4, len(DIAS)))
    s = M.tendencia(r)
    assert s.iloc[:251].isna().all().all() and s.iloc[251:].notna().all().all()
    assert (s["sube"].iloc[251:] == 1).all() and (s["baja"].iloc[251:] == 0).all()
    # tendencia corta negativa, larga positiva → ⅔ (21 d < 0, 63 y 252 > 0)
    x = np.full(len(DIAS), 0.002)
    x[-21:] = -0.003
    s2 = M.tendencia(_r(a=x))["a"].iloc[-1]
    assert s2 == pytest.approx(2 / 3)
    assert set(np.round(M.tendencia(_r(a=rng.normal(0, 0.01, len(DIAS))))["a"].dropna() * 3)) <= {0, 1, 2, 3}


def test_cero_exacto_no_es_positivo():
    assert (M.tendencia(_r(a=0.0))["a"].dropna() == 0).all()


def test_objetivo_vol_tope_y_suma():
    s = pd.Series({"a": 1.0, "b": 1.0, "c": 0.0})
    sig = pd.Series({"a": 0.10, "b": 0.20, "c": 0.15})
    w = M.objetivo(s, sig)
    assert w["a"] == pytest.approx(0.10 / 3 / 0.10) and w["b"] == pytest.approx(0.10 / 3 / 0.20) and w["c"] == 0
    # σ muy baja → tope del 40 %
    w2 = M.objetivo(pd.Series({"a": 1.0, "b": 1.0}), pd.Series({"a": 0.01, "b": 0.20}))
    assert w2["a"] == pytest.approx(0.40) and w2["b"] == pytest.approx(0.25)
    # suma > 100 % → se escala a 100 %
    w3 = M.objetivo(pd.Series({k: 1.0 for k in "abc"}), pd.Series({k: 0.02 for k in "abc"}))
    assert w3.sum() == pytest.approx(1.0) and (w3 <= M.TOPE + 1e-12).all()
    # activo sin historia: peso 0 y no cuenta en N
    w4 = M.objetivo(pd.Series({"a": 1.0, "b": np.nan}), pd.Series({"a": 0.50, "b": 0.10}))
    assert w4["a"] == pytest.approx(0.20) and w4["b"] == 0


def test_banda_de_3_pp_y_sin_apalancamiento():
    obj, act = np.array([0.30, 0.20, 0.10]), np.array([0.28, 0.25, 0.10])
    assert np.allclose(M.aplica_banda(obj, act), [0.28, 0.20, 0.10])          # 2 pp no opera, 5 pp sí
    assert np.allclose(M.aplica_banda(np.array([0.33, 0.0]), np.array([0.30, 0.0])), [0.33, 0.0])  # 3 pp justos
    # si mantener lo que no se mueve llevara la suma > 100 %, se va al objetivo entero
    assert np.allclose(M.aplica_banda(np.array([0.40, 0.58]), np.array([0.42, 0.50])), [0.42, 0.58])
    assert np.allclose(M.aplica_banda(np.array([0.40, 0.59]), np.array([0.42, 0.50])), [0.40, 0.59])
    assert np.allclose(M.aplica_banda(np.array([0.38, 0.62]), np.array([0.40, 0.50])), [0.38, 0.62])


def test_simular_cronologia_costes_y_efectivo():
    r = _r(us=0.0, bonos=0.0)
    r.iloc[10, 0] = 0.10                                    # solo el día 10 sube la bolsa
    rf = pd.Series(0.0001, index=DIAS)
    obj = pd.DataFrame(0.0, index=DIAS, columns=["us", "bonos"])
    obj.loc[DIAS[10]:, "us"] = 0.5                         # la señal del cierre del día 10 no ve su propio día
    res = M.simular(r.iloc[1:], rf, obj)
    assert res.pesos.loc[DIAS[10], "us"] == 0 and res.bruto.loc[DIAS[10]] == pytest.approx(0.0001)
    assert res.pesos.loc[DIAS[11], "us"] == 0.5
    assert res.costes.loc[DIAS[11]] == pytest.approx(0.5 * 0.0005)
    assert res.rotacion.loc[DIAS[11]] == pytest.approx(0.5)
    assert res.bruto.loc[DIAS[11]] == pytest.approx(0.5 * 0.0001)                 # mitad en efectivo
    assert res.neto.loc[DIAS[11]] == pytest.approx((1 - 0.00025) * (1 + 0.00005) - 1)
    assert res.costes.loc[DIAS[12]:].eq(0).all()          # sin cambios del objetivo: no opera


def test_deriva_y_banda_en_la_simulacion():
    r = _r(us=0.0, mp=0.0)
    r.loc[DIAS[5], "us"] = 0.05
    obj = pd.DataFrame({"us": 0.5, "mp": 0.2}, index=DIAS)
    res = M.simular(r.iloc[1:], pd.Series(0.0, index=DIAS), obj)
    assert res.costes.loc[DIAS[1]] == pytest.approx(0.5 * 0.0005 + 0.2 * 0.0010)   # 10 pb en materias primas
    # tras +5 % la bolsa deriva a 0,525/1,025 ≈ 51,2 % (< 3 pp de 50 %): no opera
    assert res.pesos.loc[DIAS[6], "us"] == pytest.approx(0.525 / 1.025)
    assert res.costes.loc[DIAS[6]:].eq(0).all()


def test_simular_falla_cerrado():
    obj = pd.DataFrame({"us": 0.5}, index=DIAS)
    r = _r(us=0.0)
    with pytest.raises(ValueError):
        M.simular(r, pd.Series(0.0, index=DIAS), obj)                   # sin objetivo del día anterior al primero
    r2 = r.iloc[1:].copy()
    r2.iloc[3, 0] = np.nan
    with pytest.raises(ValueError):
        M.simular(r2, pd.Series(0.0, index=DIAS), obj)


def test_l1_rebalanceo_anual():
    dias = pd.bdate_range("1990-12-20", "1992-01-10")
    o, reb = M.l1_objetivos(dias, ["us", "bonos", "oro"])
    assert reb.sum() == 2 and reb[pd.Timestamp("1990-12-31")] and reb[pd.Timestamp("1991-12-31")]
    r = pd.DataFrame({"us": 0.01, "bonos": 0.0, "oro": 0.0}, index=dias)
    res = M.simular(r.iloc[1:], pd.Series(0.0, index=dias), o, rebalanceo=reb, coste_lado={k: 0 for k in "x"} | {
        "us": 0, "bonos": 0, "oro": 0})
    assert res.pesos.iloc[0]["us"] == pytest.approx(0.70)
    assert res.pesos.loc["1991-06-03", "us"] > 0.75                     # deriva entre rebalanceos
    assert res.pesos.loc["1992-01-01", "us"] == pytest.approx(0.70)    # vuelve a 70 % tras el cierre de año


def test_metricas_y_mitades():
    r = pd.Series([0.01, -0.02, 0.03, 0.0], index=DIAS[:4])
    assert M.caida_maxima(r) == pytest.approx(-0.02)
    a, b = M.mitades(pd.DatetimeIndex(DIAS[:5]))
    assert len(a) == 3 and len(b) == 2
    m = M.metricas(r, pd.Series(0.0, index=DIAS[:4]), pd.Series(0.1, index=DIAS[:4]))
    assert m["rotacion_anual"] == pytest.approx(25.2) and m["dias"] == 4


def test_barajar_bloques_conserva_los_dias():
    rng = np.random.default_rng(1)
    o = M.barajar_bloques(200, 63, rng)
    assert sorted(o) == list(range(200))
    assert all(o[i + 1] == o[i] + 1 for i in range(len(o) - 1) if o[i] % 63 != 62 and o[i] != 199)


def test_placebos_reproducibles_y_percentil():
    rng = np.random.default_rng(2)
    r = pd.DataFrame(rng.normal(0.0003, 0.01, (400, 2)), index=DIAS, columns=["us", "bonos"])
    rf = pd.Series(0.0001, index=DIAS)
    s, sig = M.tendencia(r), M.volatilidad(r)
    p1 = M.placebos(r.iloc[260:], rf, s, sig, n=5, semilla=7)
    p2 = M.placebos(r.iloc[260:], rf, s, sig, n=5, semilla=7)
    assert p1.equals(p2) and len(p1) == 5
    pc = M.percentil_placebo(1.0, pd.Series([0.0, 0.5, 1.0, 2.0]))
    assert pc["p"] == pytest.approx(3 / 5) and pc["mejor_que"] == pytest.approx(0.5)


def test_criterios():
    m = lambda sh, dd: {"sharpe": sh, "caida_max": dd}   # noqa: E731
    ok = M.criterios(m(0.6, -0.20), m(0.5, -0.30), m(0.55, -0.25), {"p": 0.05}, [(0.5, 0.4), (0.7, 0.7)])
    assert ok["pasa"]
    no = M.criterios(m(0.6, -0.35), m(0.5, -0.30), m(0.65, -0.25), {"p": 0.11}, [(0.5, 0.6), (0.7, 0.7)])
    assert not any(no[k] for k in "abcd")
