"""Corte técnico de la fase de factores (src/factors/data.py): nada ≥ 2005-01 en desarrollo."""
from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from src.factors import data as F
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
# una serie por familia (las que necesita la fase)
MUESTRA = ["ff_mkt_rf_m", "ff_mom_m", "ff5_rmw_m", "aqr_qmj_usa_m", "aqr_bab_usa_m", "gsw_sveny10", "GS10",
           "TB3MS", "bis_xru_de_eur_m", "DEXUSEU", "ecb_eurusd_d",
           "gold_wb_usd_m"]


@pytest.fixture
def con_sintetica():
    """Warehouse mínimo en memoria con datos a ambos lados del corte."""
    con = duckdb.connect(":memory:")
    con.execute("create table obs_latest (series_id varchar, date date, value double)")
    con.execute("insert into obs_latest values ('ff_mkt_rf_m', '2004-12-01', 1.0), ('ff_mkt_rf_m', '2005-01-01', 2.0),"
                " ('ff_mkt_rf_m', '2026-08-01', 3.0), ('CPIAUCSL', '2004-12-01', 1.0)")
    yield con
    con.close()


def test_filtra_en_sql(con_sintetica):
    s = F.load_dev(con_sintetica, "ff_mkt_rf_m")
    assert s.index.max() == pd.Timestamp("2004-12-01") and len(s) == 1


def test_serie_fuera_de_familias(con_sintetica):
    with pytest.raises(F.FactorCutoffError):
        F.load_dev(con_sintetica, "CPIAUCSL")


def test_check_falla_si_se_cuela_2005():
    idx = pd.to_datetime(["2004-12-31", "2005-01-03"])
    with pytest.raises(F.FactorCutoffError):
        F.check(pd.Series([1.0, 2.0], index=idx))
    F.check(pd.Series([1.0], index=idx[:1]))


def test_solo_data_py_lee_el_warehouse():
    """Ningún otro módulo de src/factors/ lee series directamente (todo pasa por load_dev)."""
    rx = re.compile(r"obs_latest|obs_all_latest|observations|db\.series\(|first_available\(|\bmonthly\b")
    malos = [p.name for p in (REPO / "src" / "factors").glob("*.py") if p.name != "data.py" and rx.search(p.read_text())]
    assert not malos, malos


@pytest.mark.skipif(not db.WAREHOUSE.exists(), reason="sin warehouse real")
def test_series_reales_terminan_antes_de_2005():
    con = db.connect(read_only=True)
    try:
        for sid in MUESTRA:
            s = F.load_dev(con, sid)
            assert len(s), sid
            assert s.index.max() <= F.DEV_END, sid
            # y la serie completa sí tiene datos posteriores: el corte está actuando
            assert db.series(con, sid).index.max() > F.DEV_END, sid
    finally:
        con.close()


@pytest.mark.skipif(not db.WAREHOUSE.exists(), reason="sin warehouse real")
def test_oro_en_eur_antes_de_2005():
    con = db.connect(read_only=True)
    try:
        g = F.gold_eur_dev(con)
    finally:
        con.close()
    assert g.index.max() <= F.DEV_END and g.index.min() <= pd.Timestamp("1975-01-01")
    assert 300 < g.loc["2004-12-01"] < 400    # ~ 440 USD/oz × ~0,75 EUR/USD (comprobación de orden de magnitud)
