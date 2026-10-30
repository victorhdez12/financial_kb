"""Tests sintéticos de INT-14 (src/intl/eventos.py). Sin datos reales."""
import inspect

import numpy as np
import pandas as pd
import pytest

from src.intl import eventos as E
from src.intl.data import FactorCutoffError


def _m(vals, inicio="1980-01"):
    return pd.Series(np.asarray(vals, float), index=pd.period_range(inicio, periods=len(vals), freq="M"))


def test_modulo_no_lee_datos():
    src = inspect.getsource(E)
    for prohibido in ("db.connect", "read_parquet", "load_dev(", "read_csv"):
        assert prohibido not in src


def test_corte_2005_bloqueado():
    s = _m(np.ones(40), "2002-01")
    with pytest.raises(FactorCutoffError):
        E.eventos_petroleo(s)
    with pytest.raises(FactorCutoffError):
        E.eventos_crisis(pd.DataFrame({"USA": [0, 1]}, index=[2004, 2005]))


def test_episodios_cruce_y_separacion():
    m = pd.Series([0, 1, 1, 0, 1, 0, 0, 0, 0, 1, 1], dtype=bool)
    ini = E.episodios(m, separacion=4)
    assert list(np.flatnonzero(ini)) == [1, 9]            # el cruce en 4 está a < 4 del inicio en 1
    assert list(np.flatnonzero(E.episodios(m, separacion=3))) == [1, 4, 9]
    ini2 = E.episodios(m, separacion=3, modo="racha")
    assert list(np.flatnonzero(ini2)) == [1, 9]
    # racha larga: "cruce" permite un segundo episodio tras un hueco; "racha" lo encadena
    m2 = pd.Series([1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1, 0, 1], dtype=bool)
    assert np.flatnonzero(E.episodios(m2, 6)).tolist() == [0, 7]
    assert np.flatnonzero(E.episodios(m2, 2, modo="racha")).tolist() == [0]


def test_nopi_hamilton():
    p = _m([10, 10, 10, 12, 11, 13])
    n = E.nopi(p, ventana=3)
    assert np.isnan(n.iloc[2])
    assert n.iloc[3] == pytest.approx(np.log(12 / 10))
    assert n.iloc[4] == 0                                # por debajo del máximo previo
    assert n.iloc[5] == pytest.approx(np.log(13 / 12))


def test_evento_petroleo_acumula_maximos_sucesivos():
    base = [20.0] * 48
    subida = list(20 * np.exp(0.03 * np.arange(1, 13)))   # +3 %/mes: NOPI 0,03 cada mes; Σ12 = 0,36
    p = _m(base + subida + [subida[-1]] * 20)
    ev = E.eventos_petroleo(p, umbral=0.20)
    assert len(ev) == 1
    # Σ NOPI ≥ 0,20 a partir del 7.º mes de subida (0,21)
    assert ev.fecha.iloc[0] == p.index[48 + 6]
    assert ev.intensidad.iloc[0] == pytest.approx(0.21)


def test_empalme_no_mezcla_tramos():
    a = _m([10.0] * 50, "1950-01")
    b = _m([100.0] * 50, "1954-03")                       # cambio de base x10 en el empalme
    o = E.mensual_petroleo_encadenado([a, b])
    ev = E.eventos_petroleo(o, umbral=0.05)
    assert len(ev) == 0                                   # sin hueco, el cambio de base daría un "shock" falso


def test_dolar_y_vol_asof():
    x = _m(list(np.full(24, 100.0)) + list(100 * np.exp(np.linspace(0.01, 0.15, 12))) + [116.0] * 12)
    ev = E.eventos_dolar(x, umbral=0.10)
    assert len(ev) == 1 and ev.subida_log.iloc[0] >= 0.10
    # volatilidad: el umbral solo usa meses anteriores (un pico no sube su propio umbral)
    v = _m(list(10 + np.random.default_rng(0).random(80)) + [40.0] + [10.0] * 30)
    u = E.umbral_expansivo(v, 0.9, 60)
    assert u.iloc[80] <= 11.0
    ev = E.eventos_vol(v)
    assert v.index[80] in set(ev.fecha)
    assert (ev.umbral < 11.0).all()


def test_vol_realizada_mensual():
    idx = pd.bdate_range("1990-01-01", "1990-02-28")
    r = pd.Series(0.01, index=idx)
    rv = E.vol_realizada_mensual(r)
    assert rv.iloc[0] == pytest.approx(0.01 * np.sqrt(252))


def test_crisis_y_conglomerados():
    c = pd.DataFrame({"A": [0, 1, 0, 0, 1, 0, 0, 0, 0, 0], "B": [0, 0, 1, 0, 0, 0, 0, 0, 0, 1]},
                     index=range(1900, 1910))
    ev = E.eventos_crisis(c, separacion=5)
    ok = ev[ev.año > 0]
    assert sorted(ok.año.tolist()) == [1901, 1902, 1909]   # 1904 de A: a < 5 años de 1901 → continuación
    g = E.conglomerados_globales(ok.año.values, hueco=1)
    assert g.n.tolist() == [2, 1]
    assert E.n_efectivo(np.array([2, 1]), icc=0.0) == pytest.approx(3)
    assert E.n_efectivo(np.array([2, 1]), icc=1.0) < 2


def test_acumulada_futura_no_usa_el_pasado():
    r = _m([0.5, 0, 0, 0.1, 0.1, 0])
    acc = E.acumulada_futura(r, h=2, retraso=1)
    # origen 0: periodos 2 y 3 (salta el 1 por el retraso)
    assert acc.iloc[0] == pytest.approx(np.log(1.0) + np.log(1.1))
    assert np.isnan(acc.iloc[-1])


def test_estudio_eventos_recupera_efecto_y_placebo():
    rng = np.random.default_rng(1)
    n = 600
    r = _m(rng.normal(0.005, 0.04, n), "1950-01")
    fechas = list(r.index[30:560:40])
    lr = np.log1p(r.to_numpy())
    for f in fechas:                                     # +3 % por mes en los 6 meses siguientes
        i = r.index.get_loc(f)
        lr[i + 1:i + 7] += 0.03
    r = pd.Series(np.expm1(lr), index=r.index)
    ef = E.efecto_eventos(r, fechas, h=6)
    assert ef.efecto == pytest.approx(0.18, abs=0.06)
    lo, hi = E.ic_bloques(ef, bloque=60, n_boot=500)
    assert lo < 0.18 < hi and lo > 0
    pl = E.placebo(r, len(fechas), 6, 0, separacion=24, n_rep=200, excluir=fechas)
    assert E.p_placebo(ef.efecto, pl) < 0.02
    # sin efecto: p grande la mayoría de las veces
    r0 = _m(rng.normal(0.005, 0.04, n), "1950-01")
    ef0 = E.efecto_eventos(r0, fechas, h=6)
    assert E.p_placebo(ef0.efecto, E.placebo(r0, len(fechas), 6, 0, 24, n_rep=200, excluir=fechas)) > 0.01


def test_efecto_panel_y_holm():
    años = range(1900, 1960)
    rng = np.random.default_rng(2)
    r = pd.DataFrame(rng.normal(0.05, 0.02, (60, 3)), index=años, columns=list("ABC"))
    ev = pd.DataFrame({"pais": ["A", "B"], "año": [1910, 1930]})
    for c, a in zip(ev.pais, ev.año):
        r.loc[a + 1:a + 2, c] -= 0.20
    out = E.efecto_panel(r, ev, H=2)
    assert out["n"] == 2 and out["efecto"] < -0.35
    d = out["detalle"]
    assert E.ic_panel(d, n_boot=200)[1] < 0
    h = E.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert h["a"] == pytest.approx(0.03) and h["c"] == pytest.approx(0.06) and h["b"] == pytest.approx(0.06)


def test_potencia_clasificacion_monotona():
    p0 = E.potencia_clasificacion(30, 100, 0.8, 0.0, n_rep=60, n_boot=99, semilla=3)
    p1 = E.potencia_clasificacion(30, 100, 0.8, 1.5, n_rep=60, n_boot=99, semilla=3)
    assert p0["potencia_auc"] <= 0.15
    assert p1["potencia_auc"] > p0["potencia_auc"] and p1["delta_auc_medio"] > 0.05
    assert E.mde_media(1.0, 25) == pytest.approx((1.959964 + 0.841621) / 5, rel=1e-4)


def test_placebo_panel_y_rapido_coinciden_con_lento():
    rng = np.random.default_rng(5)
    r = _m(rng.normal(0.005, 0.04, 300), "1950-01")
    fechas = list(r.index[[20, 80, 150, 220]])
    ef = E.efecto_eventos(r, fechas, h=6)
    a = E.acumulada_futura(r, 6).to_numpy()
    assert E._efecto_idx(a, r.index.get_indexer(fechas), 6) == pytest.approx(ef.efecto)
    años = range(1900, 1960)
    p = pd.DataFrame(rng.normal(0.03, 0.1, (60, 4)), index=años, columns=list("ABCD"))
    ev = pd.DataFrame({"pais": ["A", "B", "A"], "año": [1910, 1930, 1940]})
    pl = E.placebo_panel(p, ev, 2, comun=False, separacion=5, n_rep=50)
    assert np.isfinite(pl).mean() > 0.9 and abs(np.nanmean(pl)) < 0.1
    pg = E.placebo_panel(p, pd.DataFrame({"año": [1910, 1930]}), 1, comun=True, separacion=2, n_rep=50,
                         excluir_años=frozenset(range(1914, 1919)))
    assert np.isfinite(pg).all()
    h0 = E.efecto_panel(p, ev, 1, desde=0)
    assert h0["detalle"]["abs"].iloc[0] == pytest.approx(np.log1p(p.loc[1910, "A"]))
