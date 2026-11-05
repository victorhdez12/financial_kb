"""Sección descriptiva 5e del reporte semanal (src/report/liquidez_vivo.py): datos de ejemplo sin red (warehouse en
memoria), unidades, descomposición del 10 años, divergencias fijas, avisos de dato viejo y sección en el Markdown."""
import duckdb
import numpy as np
import pandas as pd
import pytest

from src.report import liquidez_vivo as L
from src.report import weekly as W

HOY = pd.Timestamp("2026-11-05")


def _obs(sid, fechas, valores):
    return pd.DataFrame({"series_id": sid, "date": pd.to_datetime(fechas).date, "value": np.asarray(valores, float)})


def _warehouse(units=None, hasta=pd.Timestamp("2026-11-04"), hy_sube=True, sp_sube=True):
    """obs_latest y catalog de ejemplo. Liquidez con unidades de FRED: WALCL/WTREGEN/WRESBAL en millones, RRP en miles
    de millones. Valores constantes salvo donde el test necesita un cambio conocido."""
    d = pd.bdate_range("2023-10-02", hasta)                      # diarias
    w = pd.date_range("2002-12-18", hasta, freq="W-WED")        # semanales (miércoles)
    m = pd.date_range("2000-01-01", "2026-09-01", freq="MS")     # mensual
    nw, nd = len(w), len(d)
    partes = [
        # balance 7 000 000 M (7 000 mm) que baja 1 000 M por semana; TGA 800 000 M; RRP 50 mm
        _obs("WALCL", w, 7_000_000 + 1000 * np.arange(nw)[::-1]),
        _obs("WTREGEN", w, np.full(nw, 800_000.0)),
        _obs("RRPONTSYD", d, np.full(nd, 50.0)),
        _obs("WRESBAL", w, np.full(nw, 3_000_000.0)),
        _obs("M2SL", m, 20_000 * 1.004 ** np.arange(len(m))),
        _obs("BAA10Y", d, np.linspace(2.0, 1.5, nd)),
        _obs("AAA10Y", d, np.linspace(1.5, 1.0, nd)),
        _obs("BAMLH0A0HYM2", d, np.linspace(3, 4, nd) if hy_sube else np.linspace(4, 3, nd)),
        _obs("BAMLH0A3HYC", d, np.linspace(8, 12, nd)),
        _obs("VIXCLS", d, np.full(nd, 15.0)),
        _obs("SP500", d, np.linspace(4000, 6000, nd) if sp_sube else np.linspace(6000, 4000, nd)),
        # 10 años: real sube 1 pb/día hábil, implícita constante; nominal = suma
        _obs("DFII10", d, 2 + 0.01 * np.arange(nd)), _obs("T10YIE", d, np.full(nd, 2.3)),
        _obs("DGS10", d, 4.3 + 0.01 * np.arange(nd)),
        _obs("nyfed_acm_tp10_d", d, 0.5 + 0.002 * np.arange(nd)),
        _obs("nyfed_acm_rny10_d", d, np.full(nd, 4.0)),
        _obs("nyfed_acm_y10_d", d, 4.5 + 0.002 * np.arange(nd)),
    ]
    con = duckdb.connect(":memory:")
    obs = pd.concat(partes, ignore_index=True)
    con.register("obs_df", obs)
    con.execute("create table obs_latest as select * from obs_df")
    cat = pd.DataFrame(list((units or {"WALCL": "Millions of U.S. Dollars", "WTREGEN": "Millions of U.S. Dollars",
                                       "WRESBAL": "Millions of U.S. Dollars", "RRPONTSYD": "Billions of US Dollars",
                                       "M2SL": "Billions of Dollars"}).items()), columns=["series_id", "units"])
    con.register("cat_df", cat)
    con.execute("create table catalog as select * from cat_df")
    return con


def test_unidades_y_liquidez_neta():
    con = _warehouse()
    r = L.liquidez_credito(con, HOY.date())
    n = r["liquidez"]["neta"]
    # 7 000 mm − 800 − 50 en la última semana; WALCL baja 1 mm por semana → flujo −4 y −13
    assert n["valor"] == pytest.approx(7000 - 800 - 50, abs=0.05)
    assert n["flujo_4s"] == pytest.approx(-4.0, abs=0.05)
    assert n["flujo_13s"] == pytest.approx(-13.0, abs=0.05)
    assert r["liquidez"]["reservas"]["valor"] == pytest.approx(3000.0)
    assert r["liquidez"]["componentes"]["rrp"]["valor"] == pytest.approx(50.0)
    assert r["liquidez"]["m2"]["a_a_pct"] == pytest.approx((1.004 ** 12 - 1) * 100, abs=0.05)


def test_unidades_inesperadas_fallan():
    con = _warehouse(units={"WALCL": "Millions of U.S. Dollars", "WTREGEN": "Billions of Dollars",
                            "WRESBAL": "Millions of U.S. Dollars", "RRPONTSYD": "Billions of US Dollars",
                            "M2SL": "Billions of Dollars"})
    with pytest.raises(L.UnidadesInesperadas):
        L.liquidez_credito(con, HOY.date())


def test_sin_catalogo_usa_unidades_fred():
    con = _warehouse()
    con.execute("drop table catalog")
    r = L.liquidez_credito(con, HOY.date())
    assert r["liquidez"]["neta"]["valor"] == pytest.approx(6150, abs=0.05)


def test_credito_descomposicion_y_divergencias():
    con = _warehouse()
    r = L.liquidez_credito(con, HOY.date())
    c = r["credito"]
    assert c["baa_aaa"]["valor"] == pytest.approx(0.5)
    assert c["baa_aaa"]["cambio_3m"] == pytest.approx(0.0, abs=1e-9)
    assert c["hy"]["cambio_1m"] > 0 and c["hy"]["percentil"] == 100
    assert c["hy"]["desde"] == "2023-10"
    z = r["diez_anos"]["13s"]
    a, b = z["real_vs_inflacion"], z["prima_vs_expectativas"]
    assert a["total"] == pytest.approx(a["tipo_real"] + a["inflacion_implicita"], abs=0.011)
    assert a["inflacion_implicita"] == pytest.approx(0.0) and a["tipo_real"] > 0
    assert b["expectativas"] == pytest.approx(0.0) and b["prima_plazo"] > 0
    div = {d["divergencia"]: d["se_da"] for d in r["divergencias"]}
    assert div["Bolsa sube a 1 mes y el HY se ensancha a 1 mes"] is True
    assert div["Bolsa sube a 1 mes y el VIX sube a 1 mes"] is False         # VIX plano
    assert div["Bolsa sube a 3 meses y la liquidez neta cae a 13 semanas"] is True
    assert div["Bolsa sube a 3 meses y Baa − Aaa se ensancha a 3 meses"] is False
    r2 = L.liquidez_credito(_warehouse(hy_sube=False, sp_sube=False), HOY.date())
    assert {d["divergencia"]: d["se_da"] for d in r2["divergencias"]}[
        "Bolsa sube a 1 mes y el HY se ensancha a 1 mes"] is False
    assert len(r["divergencias"]) == len(L.DIVERGENCIAS)


def test_no_mira_el_futuro_y_avisa_si_viejo():
    con = _warehouse()
    r = L.liquidez_credito(con, "2026-06-30")
    assert r["credito"]["vix"]["fecha"] <= "2026-06-30"
    con = _warehouse(hasta=pd.Timestamp("2026-09-15"))
    r = L.liquidez_credito(con, HOY.date())
    assert r["credito"]["vix"]["viejo"] and r["liquidez"]["neta"]["viejo"]
    assert "viejo" in L.markdown(r)
    r = L.liquidez_credito(_warehouse(), HOY.date())
    assert not r["credito"]["vix"]["viejo"] and not r["liquidez"]["neta"]["viejo"]


def test_serie_ausente_da_sin_dato():
    con = _warehouse()
    con.execute("delete from obs_latest where series_id = 'BAMLH0A3HYC'")
    r = L.liquidez_credito(con, HOY.date())
    assert r["credito"]["ccc"]["valor"] is None
    assert {d["divergencia"]: d["se_da"] for d in r["divergencias"]}[
        "HY se estrecha a 1 mes y el CCC se ensancha a 1 mes"] is None
    assert "sin dato" in L.markdown(r)


def test_seccion_en_el_reporte():
    r = L.liquidez_credito(_warehouse(), HOY.date())
    md = W.md_liquidez_credito({"liquidez_credito": r})
    assert md.startswith(L.TITULO)
    assert "no está validado" in md.lower() or "NO está validado" in md
    assert "probabilidad" not in md.lower().replace("ni da probabilidades", "")
    assert "6 150" in md                                   # liquidez neta en miles de millones
    assert "No disponible" in W.md_liquidez_credito({"liquidez_credito": {"error": "X"}})
    assert "No disponible" in W.md_liquidez_credito({})
