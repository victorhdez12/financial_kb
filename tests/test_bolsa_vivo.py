"""Lectura de la bolsa realizada para el registro en vivo de INT-11 (src/report/bolsa_vivo.py) y modo ensayo del registro
(src/report/registro_vivo.py). Sintéticos, sin red ni warehouse."""
import duckdb
import numpy as np
import pandas as pd
import pytest

from src.report import bolsa_vivo as B
from src.report import registro_vivo as RV

MS = lambda a, b: pd.date_range(a, b, freq="MS")  # noqa: E731


def test_tr_local_usa_y_conversion_divisa():
    m = MS("2020-01-01", "2020-03-01")
    ex, rf = pd.Series([1.0, -2.0, 3.0], m), pd.Series([0.1, 0.1, 0.1], m)
    usa = B.tr_local_desde_usd(ex, rf, None)
    assert np.allclose(usa.values, [0.011, -0.019, 0.031])
    # divisa: 100 → 110 unidades locales por USD en feb (el USD se aprecia 10 %): el inversor local gana 10 % más
    fx = pd.Series([100.0, 100.0, 110.0, 110.0], MS("2019-12-01", "2020-03-01"))
    loc = B.tr_local_desde_usd(ex, rf, fx)
    assert np.isclose(loc["2020-02-01"], (1 - 0.019) * 1.1 - 1)
    assert np.isclose(loc["2020-01-01"], 0.011) and np.isclose(loc["2020-03-01"], 0.031)


def test_fin_de_mes_y_local_por_usd():
    d = pd.Series([1.10, 1.20, 1.25, 1.30], pd.to_datetime(["2024-01-02", "2024-01-31", "2024-02-01", "2024-02-29"]))
    f = B.fin_de_mes(d)
    assert list(f.index) == list(MS("2024-01-01", "2024-02-01")) and list(f.values) == [1.20, 1.30]
    assert np.allclose(B.local_por_usd(f, True).values, [1 / 1.2, 1 / 1.3])


def test_rent_ventana_tr_exige_los_12_meses():
    r = pd.Series(0.01, MS("2025-01-01", "2026-12-01"))
    v = B.rent_ventana_tr(r, "2025-12-01", "2026-11-30")
    assert v["completo"] and np.isclose(v["nominal"], 1.01 ** 12 - 1)
    v2 = B.rent_ventana_tr(r.drop(pd.Timestamp("2026-03-01")), "2025-12-01", "2026-11-30")
    assert not v2["completo"] and v2["faltan"] == ["2026-03"] and v2["nominal"] is None


def test_rent_ventana_precio_con_dividendo():
    p = pd.Series(np.linspace(100, 123, 24), MS("2025-01-01", "2026-12-01"))
    v = B.rent_ventana_precio(p, "2026-01-01", "2026-12-31", rend_div=0.02)
    assert np.isclose(v["nominal"], p["2026-12-01"] / p["2025-12-01"] * 1.02 - 1)


def test_inflacion_media_y_punta():
    ipc = pd.Series(100 * 1.002 ** np.arange(36), MS("2024-01-01", "2026-12-01"))
    med = B.inflacion_ventana(ipc, "2026-01-01", "2026-12-31", "media")
    pun = B.inflacion_ventana(ipc, "2026-01-01", "2026-12-31", "punta")
    assert np.isclose(med, 1.002 ** 12 - 1) and np.isclose(pun, 1.002 ** 12 - 1)
    assert B.inflacion_ventana(ipc.drop(pd.Timestamp("2025-06-01")), "2026-01-01", "2026-12-31") is None
    assert B.real(0.10, 0.05) == pytest.approx(1.10 / 1.05 - 1)
    assert B.real(None, 0.05) is None


def test_ipc_con_huecos_rellena_solo_huecos_cortos():
    ipc = pd.Series(100 * 1.01 ** np.arange(12), MS("2025-01-01", "2025-12-01"))
    s, rell = B.ipc_con_huecos(ipc.drop([pd.Timestamp("2025-10-01")]))
    assert rell == ["2025-10"] and np.isclose(s["2025-10-01"], ipc["2025-10-01"])
    s2, rell2 = B.ipc_con_huecos(ipc.drop([pd.Timestamp("2025-05-01"), pd.Timestamp("2025-06-01")]))
    assert rell2 == [] and pd.Timestamp("2025-05-01") not in s2.index


def test_realizado_pais_principal_y_respaldo():
    m = MS("2014-01-01", "2026-12-01")
    ex = pd.Series(0.5, m)
    rf = pd.Series(0.0, m)
    ipc = pd.Series(100.0, m)
    precio = pd.Series(100 * 1.005 ** np.arange(len(m)), m)
    r = B.realizado_pais("2026-01-01", "2026-12-31", ipc, exceso_pct=ex, rf_pct=rf, es_usa=True,
                         precio_medio=precio, rend_div=0.0)
    assert r["usada"] == "principal" and np.isclose(r["principal"]["real"], 1.005 ** 12 - 1)
    assert np.isclose(r["respaldo"]["real"], 1.005 ** 12 - 1)
    # sin el último mes de la principal → respaldo
    r2 = B.realizado_pais("2026-01-01", "2026-12-31", ipc, exceso_pct=ex.iloc[:-1], rf_pct=rf, es_usa=True,
                          precio_medio=precio, rend_div=0.0)
    assert r2["usada"] == "respaldo"
    # sin divisa para un país no-EE. UU. → no hay principal
    r3 = B.realizado_pais("2026-01-01", "2026-12-31", ipc, exceso_pct=ex, rf_pct=rf, precio_medio=precio, rend_div=0.0)
    assert "principal" not in r3 and r3["usada"] == "respaldo"


def test_rend_div_implicito_recupera_el_diferencial_sin_mirar_la_ventana():
    m = MS("2010-01-01", "2026-12-01")
    precio = pd.Series(100 * 1.004 ** np.arange(len(m)), m)
    tr = pd.Series((1.004 * 1.03 ** (1 / 12)) - 1, m)        # TR = precio + 3 % anual de dividendo
    tr.loc["2026-01-01":] = 0.5                               # la ventana evaluada (2026) no debe influir
    d = B.rend_div_implicito(tr, precio, "2025-12-31")
    assert d == pytest.approx(0.03, abs=1e-9)


def test_anual_y_comparar():
    r = pd.Series(0.01, MS("2000-01-01", "2002-06-01"))
    a = B.anual(r)
    assert list(a.index) == [2000, 2001] and np.isclose(a[2000], 1.01 ** 12 - 1)
    p = pd.Series(np.arange(1, 37, dtype=float), MS("2000-01-01", "2002-12-01"))
    ap = B.anual_precio(p)
    assert list(ap.index) == [2001, 2002] and np.isclose(ap[2001], 24 / 12 - 1)
    x = pd.Series([0.1, 0.2, -0.1, 0.05], [1, 2, 3, 4])
    c = B.comparar(x + 0.01, x)
    assert c["n"] == 4 and c["corr"] == pytest.approx(1.0) and c["sesgo_pp"] == pytest.approx(1.0)


def test_french_parser():
    txt = """
     Value-Weight Dollar Returns      All 4 Data Items Not Reqd
          Mkt   High    Low
202001   9.00   1.00   1.00

     Value-Weight Local  Returns      All 4 Data Items Not Reqd
          Mkt   High    Low
202001   1.50   1.00   1.00
202002 -99.99   1.00   1.00
202003  -2.00   1.00   1.00

     Value-Weight Local  Returns      All 4 Data Items Required
          Mkt   High    Low
202001   7.00   1.00   1.00
"""
    s = B.french_pais_local(txt)
    assert list(s.index) == list(MS("2020-01-01", "2020-03-01"))
    assert s.iloc[0] == 1.5 and np.isnan(s.iloc[1]) and s.iloc[2] == -2.0


def test_leer_obs_no_lee_jst():
    con = duckdb.connect(":memory:")
    with pytest.raises(ValueError):
        B.leer_obs(con, "jst_usa_eq_tr")


def test_leer_realizado_warehouse_sintetico():
    con = duckdb.connect(":memory:")
    m = MS("2010-01-01", "2026-12-01")
    filas = []
    for sid, v in [("aqr_rf_risk_free_rate_m", 0.1), ("aqr_mkt_usa_m", 0.4), ("aqr_mkt_deu_m", 0.4)]:
        filas.append(pd.DataFrame({"series_id": sid, "date": m.date, "value": v}))
    for c in ("usa", "deu"):
        filas.append(pd.DataFrame({"series_id": f"oecd_share_{c}", "date": m.date, "value": 100 * 1.004 ** np.arange(len(m))}))
        filas.append(pd.DataFrame({"series_id": f"oecd_cpi_{c}_idx", "date": m.date, "value": 100 * 1.002 ** np.arange(len(m))}))
    df = pd.concat(filas)  # noqa: F841
    con.execute("create table obs_latest as select series_id, cast(date as date) as date, value from df")
    d = pd.date_range("2009-12-01", "2026-12-31", freq="D")
    fx = {"DEXUSEU": pd.Series(1.0, d)}
    r = B.leer_realizado(con, fx, "2026-01-01", "2026-12-31", paises=["USA", "DEU"])
    for c in ("USA", "DEU"):
        assert r[c]["usada"] == "principal"
        assert r[c]["principal"]["real"] == pytest.approx(1.005 ** 12 / 1.002 ** 12 - 1)
        assert r[c]["respaldo"]["completo"] and r[c]["ipc_interpolados"] == []


def test_plan_evaluacion():
    p = B.plan_evaluacion({"desde": "2026-12-01", "hasta": "2027-11-30", "meses": 12})
    assert p["evaluable_desde"]["principal"] == "2028-02-29" and "PROPUESTA" in p["fuente"]["estado"]


def test_comprobaciones_ensayo_anota_sin_abortar(tmp_path):
    carpeta = RV.REPO / "research/int/int11_vivo_test_inexistente"
    ch = RV.comprobaciones_ensayo("2026-01-01", carpeta, hoy="2026-03-01", sucios=["src/x.py"])
    assert not ch["fecha_ok"] and not ch["arbol_ok"] and ch["mes_libre"] and len(ch["abortaria"]) == 2
    ok = RV.comprobaciones_ensayo("2026-03-01", carpeta, hoy="2026-03-02", sucios=[])
    assert ok["fecha_ok"] and ok["arbol_ok"] and ok["abortaria"] == []
    assert not carpeta.exists()          # el ensayo no crea nada


def test_resumen_ensayo_no_escribe(tmp_path):
    o = {"emision": "2026-11-20", "ventana_objetivo": {"desde": "2026-12-01", "hasta": "2027-11-30", "meses": 12},
         "paises": {"USA": {"cuantiles_1_99": {}}, "JPN": {"aviso": "sin datos suficientes"}},
         "entradas": {"sha256": "abc"}, "ensayo": {"abortaria": []}}
    r = RV.resumen_ensayo(o, tmp_path, {"x": 1})
    assert r["archivo_que_se_escribiria"].endswith("2026-11.json") and r["paises"] == {"USA": "ok", "JPN": "sin datos suficientes"}
    assert list(tmp_path.iterdir()) == []
