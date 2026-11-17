"""Validador independiente (17-nov-2026): cambios del panel fusionados el 15-nov sin validar.

1. Percentiles unificados (src/report/_percentil.py): definición recalculada a mano (numpy, sin _percentil), bordes
   (empates, NaN, base corta, ventanas), sin fuga de datos posteriores al corte, HY OAS igual en las tres tablas.
2. VYLR en «Mis activos»: guarda de historia corta (< 260 sesiones).
3. Simulación B: trayectorias conjuntas bolsa+inflación, colas sin recortar, reproducibilidad.

Los tests marcados `xfail(strict=True)` documentan HALLAZGOS (comportamiento actual incorrecto o frágil); si alguien
los arregla, pasarán y pytest avisará (XPASS → fallo) para quitar la marca.
Los tests con datos reales se saltan si no hay warehouse o precios (data/warehouse.duckdb, ~/financial_archive/mercados).
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.report import _percentil as PC
from src.report import mis_activos as MA


def _manual(a, v=None):
    a = np.asarray(pd.Series(a, dtype=float).dropna().values, float)
    v = a[-1] if v is None else v
    return 100.0 * np.sum(a <= v) / len(a)


def _d(vals, start="2000-01-03", freq="B"):
    return pd.Series(vals, index=pd.date_range(start, periods=len(vals), freq=freq), dtype=float)


# ------------------------------------------------------------------------------------------- 1. percentiles
@pytest.mark.parametrize("semilla", range(10))
def test_definicion_igual_a_recalculo_manual(semilla):
    rng = np.random.default_rng(semilla)
    x = np.round(rng.normal(size=500), 1)                     # redondeo → muchos empates
    x[rng.integers(0, 500, 20)] = np.nan
    s = _d(x)
    assert PC.percentil(s, dec=None) == pytest.approx(_manual(x))
    v = float(rng.normal())
    assert PC.percentil(s, v, dec=None) == pytest.approx(_manual(x, v))


def test_empates_cuentan_como_menor_o_igual():
    assert PC.percentil(_d([2.0] * 30)) == 100
    assert PC.percentil(_d([1.0] * 15 + [2.0] * 15), 1.0) == 50


def test_nan_al_final_se_descarta_y_el_actual_es_el_ultimo_valido():
    s = _d(list(range(1, 31)) + [np.nan])
    assert PC.percentil(s) == 100


def test_base_corta_sin_percentil():
    assert PC.percentil(_d(range(23))) is None
    assert PC.percentil(_d(range(24))) == 100
    assert PC.calcular(_d([np.nan] * 40)).valor is None


def test_ventana_dateoffset_y_ultimas_n():
    s = _d(range(1, 1001))
    p = PC.calcular(s, ventana=pd.DateOffset(years=1))
    b = s[s.index > s.index[-1] - pd.DateOffset(years=1)]
    assert p.n == len(b) and p.valor == pytest.approx(100.0)
    assert PC.calcular(s, 500.0, ventana=156).valor == pytest.approx(0.0)
    assert PC.etiqueta(p.valor, p.desde, p.ventana) == "p100 · 1 año"
    assert PC.etiqueta(34, "1950-01", frecuencia="mensual") == "p34 · mensual desde 1950-01"


def test_sin_fuga_datos_posteriores_al_corte():
    s = _d(range(1, 101))
    futuro = pd.concat([s, pd.Series([-1e9, 1e9], index=pd.to_datetime(["2100-01-01", "2100-01-02"]))])
    corte = s.index[-1]
    assert PC.percentil(futuro, hasta=corte, dec=None) == PC.percentil(s, dec=None)
    assert PC.base(futuro, hasta=corte).index.max() == corte


def test_frecuencia_mensual_ultimo_de_cada_mes():
    s = _d(np.arange(300.0))
    m = PC.base(s, frecuencia="M")
    assert len(m) == s.index.to_period("M").nunique()
    assert m.iloc[-1] == s.iloc[-1]


@pytest.mark.xfail(strict=True, reason="HALLAZGO: valor NaN da 0 en vez de None (insiders: act['amplitud'] NaN)")
def test_valor_nan_no_da_cero():
    assert PC.percentil(_d(range(1, 31)), float("nan")) is None


@pytest.mark.xfail(strict=True, reason="HALLAZGO menor: ventana=0 (int) devuelve TODA la historia (iloc[-0:])")
def test_ventana_cero_no_es_toda_la_historia():
    assert PC.calcular(_d(range(1, 31)), ventana=0, min_obs=1).n == 0


# ------------------------------------------------------------------------------- datos reales (si los hay)
def _con():
    from src.warehouse import db
    if not db.WAREHOUSE.exists():
        pytest.skip("sin warehouse")
    return db.connect(read_only=True)


def test_hy_oas_igual_en_las_tres_tablas_mismo_corte():
    from src.report import liquidez_vivo as LV
    from src.report import panel_hoy as PH
    from src.report import weekly as W
    con = _con()
    try:
        from src.warehouse import db
        hy = db.series(con, "BAMLH0A0HYM2")
        rm, meta = W.load()
        corte = pd.Timestamp(rm["cutoff"].iloc[-1])
        fila = next(r for r in W.indicator_rows(rm, meta, W.series_nativas(con, meta)) if r["indicador"] == "HY OAS")
        series, _ = LV.cargar(con, corte)
        liq = LV.credito(series, corte)["hy"]["percentil"]
        hoy = PH.ficha("hy", PH.serie_indicador("hy", {"BAMLH0A0HYM2": hy[hy.index <= corte]}))["percentil"]
    finally:
        con.close()
    esperado = round(_manual(hy[hy.index <= corte]))
    assert fila["percentil_base"] == "nativa"
    assert fila["percentil_hist"] == liq == hoy == esperado


def _precios():
    pp = MA.DIR / "precios_diarios.parquet"
    if not pp.exists():
        pytest.skip("sin precios")
    return pd.read_parquet(pp)


def _motor_sintetico(n=50000, semilla=7):
    rng = np.random.default_rng(semilla)
    pi = rng.normal(0.03, 0.03, n)
    b = np.expm1(rng.normal(0.06, 0.17, n) - 1.5 * (pi - 0.03))   # correlación negativa bolsa-inflación
    return {"bolsa_real": b, "inflacion_log": pi}


# -------------------------------------------------------------------------------------- 2. VYLR (datos reales)
def test_vylr_guarda_historia_corta_y_no_rompe_otras_filas():
    P = _precios()
    if "VYLR" not in P or P["VYLR"].dropna().size >= MA.MIN_DIAS:
        pytest.skip("VYLR no está o ya tiene ≥ 260 sesiones")
    con = _con()
    try:
        d = MA.analizar(con, date(2026, 11, 17), _motor_sintetico(), 4.0)
    finally:
        con.close()
    v = d["activos"]["VYLR"]
    assert v["historia_insuficiente"].startswith("historia insuficiente (desde 2026-10-01")
    for k in ("vol_1a", "caida_max52", "beta_3a", "por_cuadrante", "sim_historia", "sim_motor", "sim_motor_infl"):
        assert v.get(k) is None, k
    assert v["r_ytd"] is None and v["r_12m"] is None and v["r_3m"] is None      # sin base anterior a oct-2026
    for t in ("CTVA", "SPY", "MSFT", "TLT"):
        r = d["activos"][t]
        assert "sim_historia" in r and "sim_motor" in r and r.get("vol_1a") is not None, t


def test_ctva_escision_ajustada_sin_salto_de_6x():
    P = _precios()
    c = P["CTVA"].dropna()
    salto = float(np.log(c["2026-10-01"] / c[:"2026-09-30"].iloc[-1]))
    assert abs(salto) < 0.15                       # sin el ajuste sería log(1/6,665) ≈ −1,9


# ------------------------------------------------------------------------------------- 3. simulación B
def _bt():
    rng = np.random.default_rng(3)
    return {"beta": 0.8, "res": rng.normal(0, 0.05, 120)}


def test_b_usa_la_inflacion_de_la_misma_trayectoria():
    mo = _motor_sintetico()
    mk = MA.mercado_motor(mo)
    assert np.allclose(mk["l_nom"], np.log1p(mo["bolsa_real"]) + mo["inflacion_log"])
    x = MA.sim_motor(_bt(), mk, 4.0, np.random.default_rng(1))
    assert np.allclose(x["l_real"], x["l_nom"] - mo["inflacion_log"])
    # si se remezclara la inflación (independiente de la bolsa), la real cambiaría: el emparejamiento importa
    mk2 = dict(mk, pi=np.random.default_rng(9).permutation(mk["pi"]))
    x2 = MA.sim_motor(_bt(), mk2, 4.0, np.random.default_rng(1))
    c1 = np.corrcoef(x["l_real"], mo["inflacion_log"])[0, 1]
    c2 = np.corrcoef(x2["l_real"], mo["inflacion_log"])[0, 1]
    assert abs(c1 - c2) > 0.05


def test_b_colas_completas_y_reproducible():
    mo = _motor_sintetico()
    mk = MA.mercado_motor(mo)
    x = MA.sim_motor(_bt(), mk, 4.0, np.random.default_rng([MA.SEMILLA, 2]))
    r = MA._resumen(np.expm1(x["l_nom"]))
    assert r["n"] == len(mo["bolsa_real"])
    assert r["min"] == pytest.approx(float(np.expm1(x["l_nom"]).min()))
    assert r["max"] == pytest.approx(float(np.expm1(x["l_nom"]).max()))
    assert r["min"] < r["p1"] < r["p5"] and r["p95"] < r["p99"] < r["max"]
    y = MA.sim_motor(_bt(), mk, 4.0, np.random.default_rng([MA.SEMILLA, 2]))
    assert np.array_equal(x["l_nom"], y["l_nom"])
    assert mk["recortadas"] == 0


def test_b_beta_uno_sin_residuo_reproduce_la_bolsa_del_motor():
    mo = _motor_sintetico()
    mk = MA.mercado_motor(mo)
    x = MA.sim_motor({"beta": 1.0, "res": np.zeros(60)}, mk, 4.0, np.random.default_rng(0))
    assert np.allclose(np.expm1(x["l_real"]), mo["bolsa_real"])
