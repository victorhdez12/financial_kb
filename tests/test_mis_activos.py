"""Simulación B de «Mis activos» (src/report/mis_activos.py): trayectorias conjuntas del motor (bolsa real + inflación),
coherencia real/nominal por trayectoria, colas completas y betas sin fuga temporal. Datos SINTÉTICOS salvo el último
test (reproducción de la emisión publicada), que se salta sin warehouse."""
import json

import duckdb
import numpy as np
import pandas as pd
import pytest

from src.report import mis_activos as MA


def _motor(n=20000, semilla=1):
    rng = np.random.default_rng(semilla)
    pi = rng.normal(0.035, 0.04, n)
    b = np.expm1(rng.normal(0.06, 0.18, n) - 0.8 * (pi - 0.035))
    return {"bolsa_real": b, "inflacion_log": pi, "emision": "2026-11-12", "corte": "2026-10-31",
            "ventana": {"desde": "2026-12-01", "hasta": "2027-11-30"}, "estado": {}, "comprobacion": None}


def _mensuales(semilla=2, desde="2005-01-31", hasta="2026-10-31"):
    idx = pd.date_range(desde, hasta, freq="ME")
    rng = np.random.default_rng(semilla)
    m = pd.Series(rng.normal(0.007, 0.045, len(idx)), index=idx)
    pi = pd.Series(rng.normal(0.0025, 0.003, len(idx)), index=idx)
    a = 0.001 + 1.2 * m + 2.0 * pi + rng.normal(0, 0.05, len(idx))
    return pd.Series(a, index=idx), m, pi


def test_real_es_nominal_menos_inflacion_de_la_misma_trayectoria():
    mo = _motor()
    mk = MA.mercado_motor(mo)
    assert np.allclose(mk["l_nom"], np.log1p(mo["bolsa_real"]) + mo["inflacion_log"], atol=0, rtol=0)
    a, m, pi = _mensuales()
    bt = MA.betas(a, m, pd.Timestamp("2026-10-31"), pi)
    for ci in (False, True):
        x = MA.sim_motor(bt, mk, 4.0, np.random.default_rng(0), con_inflacion=ci)
        assert x["l_nom"].shape == mo["inflacion_log"].shape          # una muestra por trayectoria del motor
        assert np.array_equal(x["l_real"], x["l_nom"] - mk["pi"])     # misma π, trayectoria a trayectoria
    # activo idéntico al mercado (β = 1, sin residuo, rf = 0) → real del activo = bolsa real del motor
    bt1 = {"beta": 1.0, "res": np.zeros(120)}
    x = MA.sim_motor(bt1, mk, 0.0, np.random.default_rng(0))
    assert np.allclose(np.expm1(x["l_real"]), mo["bolsa_real"])


def test_sin_recorte_de_colas_p1_p99():
    mo = _motor()
    mo["bolsa_real"][:3] = [-0.95, 3.0, -0.90]                        # colas extremas, fuera de p1-p99
    mk = MA.mercado_motor(mo)
    assert mk["recortadas"] == 0
    bt1 = {"beta": 1.0, "res": np.zeros(120)}
    x = MA.sim_motor(bt1, mk, 0.0, np.random.default_rng(0))
    r = MA._resumen(np.expm1(x["l_real"]))
    assert r["min"] == pytest.approx(-0.95) and r["max"] == pytest.approx(3.0)
    assert r["min"] < r["p1"] < r["p5"] < r["p50"] < r["p95"] < r["p99"] < r["max"]
    assert r["n"] == len(mo["bolsa_real"])
    # una bolsa real ≤ −100 % rompe el log: se acota y se CUENTA (rótulo en el panel)
    mo["bolsa_real"][0] = -1.0
    assert MA.mercado_motor(mo)["recortadas"] == 1


def test_betas_sin_fuga_temporal():
    a, m, pi = _mensuales(hasta="2030-12-31")
    f = pd.Timestamp("2026-06-15")
    b = MA.betas(a, m, f, pi)
    # cambiar TODO lo posterior a f (precios e IPC) no mueve nada
    fut = a.index > f + pd.offsets.MonthEnd(0)
    a2, m2, pi2 = a.copy(), m.copy(), pi.copy()
    a2[fut], m2[fut], pi2[pi.index > pd.Timestamp("2026-05-31")] = 9.0, -9.0, 5.0   # IPC de jun-2026 en adelante: aún no publicado en f
    b2 = MA.betas(a2, m2, f, pi2)
    assert b["beta"] == b2["beta"] and np.array_equal(b["res"], b2["res"])
    assert b["inflacion"]["beta_pi"] == b2["inflacion"]["beta_pi"]
    assert b["hasta"] <= "2026-06-30"
    # IPC solo de meses ya publicados en f: el de mayo-2026 sale ~mediados de junio (regla: día 15 de m + 1)
    assert b["inflacion"]["ipc_hasta"] == "2026-05"
    assert MA.betas(a, m, pd.Timestamp("2026-06-14"), pi)["inflacion"]["ipc_hasta"] == "2026-04"
    # la β a la inflación recupera la verdadera (2,0) con datos sintéticos
    assert abs(MA.betas(a, m, pd.Timestamp("2030-12-31"), pi, anos=25)["inflacion"]["beta_pi"] - 2.0) < 1.0


def test_ipc_mensual_no_salta_huecos():
    con = duckdb.connect(":memory:")
    fechas = pd.date_range("2025-01-01", "2026-03-01", freq="MS")
    v = 300 * np.exp(0.003 * np.arange(len(fechas)))
    df = pd.DataFrame({"series_id": "CPIAUCSL", "date": fechas.date, "value": v})
    df.loc[df["date"] == pd.Timestamp("2025-10-01").date(), "value"] = None
    con.execute("create table obs_latest as select * from df")
    p = MA._cpi_mensual(con)
    assert pd.Timestamp("2025-10-31") not in p.index and pd.Timestamp("2025-11-30") not in p.index  # sin Δ de 2 meses
    assert np.allclose(p.values, 0.003)


def test_analizar_end_to_end_sintetico(tmp_path, monkeypatch):
    dias = pd.bdate_range("2012-01-02", "2026-11-13")
    rng = np.random.default_rng(3)
    spy = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.011, len(dias))))
    act = 50 * np.exp(np.cumsum(0.8 * np.log(np.r_[1, spy[1:] / spy[:-1]]) + rng.normal(0, 0.01, len(dias))))
    pd.DataFrame({"SPY": spy, "ACT": act}, index=dias).to_parquet(tmp_path / "precios_diarios.parquet")
    (tmp_path / "activos.json").write_text(json.dumps({"activos": {
        "SPY": {"nombre": "S&P 500", "grupo": "Referencias", "moneda": "USD"},
        "ACT": {"nombre": "Activo", "grupo": "Acciones", "moneda": "USD"},
        "EUR": {"nombre": "Euro", "grupo": "Acciones", "moneda": "EUR"}}}))
    monkeypatch.setattr(MA, "DIR", tmp_path)
    d = MA.analizar(None, None, _motor(), 4.0)
    for t in ("SPY", "ACT"):
        b = d["activos"][t]["sim_motor"]
        assert {"min", "p1", "p99", "max"} <= set(b) and {"p5", "p50", "p95"} <= set(b["real"])
        assert b["real"]["p50"] < b["p50"]                       # inflación media del motor > 0
        assert "sim_motor_infl" not in d["activos"][t]           # sin con → sin IPC → sin B′
    assert abs(d["activos"]["SPY"]["sim_motor"]["beta_10a"] - 1) < 1e-12
    assert "inflacion" in d["supuestos"]["motor"]
    # A no depende de B: la misma con y sin motor
    d0 = MA.analizar(None, None, None, 4.0)
    assert d0["activos"]["ACT"]["sim_historia"] == d["activos"]["ACT"]["sim_historia"]
    assert "sim_motor" not in d0["activos"]["ACT"]


def _warehouse():
    from src.warehouse import db
    return db.WAREHOUSE.exists()


@pytest.mark.skipif(not _warehouse(), reason="necesita el warehouse real (data/warehouse.duckdb)")
def test_trayectorias_reproducen_la_emision_publicada():
    from src.report import panel as P
    sp = P.ultimo_signal()
    if sp is None:
        pytest.skip("sin signal")
    es = json.loads(sp.read_text()).get("escenarios") or {}
    try:
        ab = es["paises"]["USA"]["abanicos"]["bolsa"]
    except (KeyError, TypeError):
        pytest.skip("signal sin abanicos")
    mo = MA.trayectorias_motor(es["emision"], ref={p: ab[f"p{p}"] for p in (5, 25, 50, 75, 95)})
    if not mo["comprobacion"]["coincide"]:
        pytest.skip(f"datos del warehouse cambiaron desde la emisión (dif {mo['comprobacion']['max_dif']:.4f})")
    assert len(mo["bolsa_real"]) == len(mo["inflacion_log"]) == 200 * 1000
