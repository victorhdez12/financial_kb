"""Motor de S1 (src/factors/s1.py) con datos sintéticos: pesos de §3, cronología, deriva, costes, placebos, criterios."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.factors import s1 as S


def _r(n=24, val=0.0, desde="2000-01"):
    idx = pd.period_range(desde, periods=n, freq="M")
    return pd.DataFrame(val, index=idx, columns=list(S.ACTIVOS))


def test_pesos_por_cuadrante_spec():
    assert S.SECTORES["Goldilocks"] == ("BusEq", "Durbl", "Shops", "Money")
    assert S.SECTORES["Reflación"] == ("Enrgy", "Chems", "Manuf", "Money")
    assert S.SECTORES["Estanflación"] == ("Enrgy", "Utils", "NoDur", "Hlth")
    assert S.SECTORES["Deflación/recesión"] == ("NoDur", "Hlth", "Utils", "Telcm")
    for q in S.SECTORES:
        w = S.objetivo(q)
        assert w.sum() == pytest.approx(1) and (w >= 0).all() and w["mkt"] == 0.5 and w["Other"] == 0
        assert sorted(w[w > 0].drop("mkt").round(6).unique()) == [0.125]
    with pytest.raises(ValueError):
        S.objetivo("Other")


def test_cronologia_cuadrante_de_t_rige_t_mas_1():
    r = _r(3)
    r.loc[pd.Period("2000-02", "M"), "BusEq"] = 0.10       # solo BusEq se mueve en febrero
    senal = pd.Series(["Deflación/recesión", "Goldilocks", "Goldilocks"],
                      index=pd.period_range("1999-12", periods=3, freq="M"), dtype=object)
    res = S.simular(r, senal, coste_lado=0)
    # el Goldilocks de 2000-01 rige febrero: 12,5 % en BusEq → +1,25 %
    assert res.bruto[pd.Period("2000-02", "M")] == pytest.approx(0.0125)
    assert res.cuadrante[pd.Period("2000-01", "M")] == "Deflación/recesión"


def test_sin_cambio_no_opera_y_los_pesos_derivan():
    r = _r(3)
    r["Enrgy"] = 0.10
    senal = pd.Series("Estanflación", index=pd.period_range("1999-12", periods=3, freq="M"), dtype=object)
    res = S.simular(r, senal)
    assert (res.rotacion.iloc[1:] == 0).all() and (res.costes.iloc[1:] == 0).all()
    assert res.pesos["Enrgy"].iloc[1] > 0.125                 # deriva: no se rebalancea
    assert res.pesos.sum(axis=1).round(12).eq(1).all()


def test_costes_10pb_por_lado_y_primera_inclinacion():
    r = _r(3)
    senal = pd.Series(["Goldilocks", "Goldilocks", "Reflación"],
                      index=pd.period_range("1999-12", periods=3, freq="M"), dtype=object)
    res = S.simular(r, senal)
    # de L0 (100 % mercado) a 50/50: Σ|Δw| = 1,0 → rotación 0,5, coste 10 pb
    assert res.rotacion.iloc[0] == pytest.approx(0.5) and res.costes.iloc[0] == pytest.approx(0.0010)
    # Goldilocks → Reflación (sin deriva): vende 3×12,5 %, compra 3×12,5 % (Money se queda) → Σ|Δw| = 0,75
    assert res.rotacion.iloc[2] == pytest.approx(0.375) and res.costes.iloc[2] == pytest.approx(0.00075)
    assert res.neto.iloc[2] == pytest.approx(-0.00075)


def test_sin_cuadrante_mantiene_pesos():
    r = _r(3)
    senal = pd.Series(["Goldilocks", None, np.nan], index=pd.period_range("1999-12", periods=3, freq="M"),
                      dtype=object)
    res = S.simular(r, senal)
    assert list(res.cuadrante) == ["Goldilocks"] * 3 and (res.rotacion.iloc[1:] == 0).all()


def test_falla_con_huecos_o_meses_salteados():
    r = _r(3)
    r.iloc[1, 2] = np.nan
    with pytest.raises(ValueError):
        S.simular(r, pd.Series(dtype=object))
    r = _r(3).drop(pd.Period("2000-02", "M"))
    with pytest.raises(ValueError):
        S.simular(r, pd.Series(dtype=object))


def test_barajar_bloques_conserva_frecuencias():
    v = np.array(list("AAAABBBBCCCCDD"), dtype=object)
    out = S.barajar_bloques(v, 4, np.random.default_rng(1))
    assert sorted(out) == sorted(v) and len(out) == len(v)
    texto = "".join(out)
    assert all(b in texto for b in ("AAAA", "BBBB", "CCCC", "DD"))          # los bloques viajan enteros
    # reproducible con la semilla
    assert (S.barajar_bloques(v, 4, np.random.default_rng(1)) == out).all()


def test_placebos_reproducibles_y_metricas():
    rng = np.random.default_rng(0)
    r = _r(60)
    r[:] = rng.normal(0.01, 0.04, size=r.shape)
    q = list(S.SECTORES)
    senal = pd.Series([q[(i // 7) % 4] for i in range(61)], index=pd.period_range("1999-12", periods=61, freq="M"),
                      dtype=object)
    p1 = S.placebos(r, senal, r["mkt"], 20, 12, 7)
    p2 = S.placebos(r, senal, r["mkt"], 20, 12, 7)
    pd.testing.assert_frame_equal(p1, p2)
    pc = S.percentil_placebo(10.0, p1["activa_arit"])
    assert pc["p"] == pytest.approx(1 / 21) and pc["mejor_que"] == 1.0
    a, b = S.mitades(r.index)
    assert len(a) == 30 and len(b) == 30 and a[-1] + 1 == b[0]
    assert S.caida_maxima(pd.Series([0.1, -0.5, 0.2])) == pytest.approx(-0.5)


def test_criterios():
    act = {"activa_arit": 0.01, "activa_geo": 0.005, "ir": 0.25}
    mit = [{"activa_arit": 0.0, "activa_geo": 0.001}, {"activa_arit": 0.02, "activa_geo": 0.01}]
    ok = S.criterios(act, {"p": 0.05}, mit, -0.50, -0.46)
    assert ok == {"a": True, "b": True, "c": True, "d": True, "pasa": True}
    assert not S.criterios({**act, "ir": 0.19}, {"p": 0.05}, mit, -0.5, -0.46)["a"]
    assert not S.criterios({**act, "activa_geo": -0.001}, {"p": 0.05}, mit, -0.5, -0.46)["a"]
    assert not S.criterios(act, {"p": 0.11}, mit, -0.5, -0.46)["b"]
    assert not S.criterios(act, {"p": 0.05}, [mit[0], {"activa_arit": -1e-4, "activa_geo": 0.0}], -0.5, -0.46)["c"]
    assert not S.criterios(act, {"p": 0.05}, mit, -0.52, -0.46)["d"]
