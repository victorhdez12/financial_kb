"""Panel internacional (src/intl/): corte en 2004, retrasos, bonos (sintético) y una comprobación con datos reales."""
from __future__ import annotations

import re
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from src.intl import data as D
from src.intl import lags as Lg
from src.intl import returns as R
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]


def test_corte_y_familias():
    con = duckdb.connect(":memory:")
    con.execute("create table obs_latest (series_id varchar, date date, value double)")
    con.execute("insert into obs_latest values ('oecd_ip_deu','2004-12-01',1),('oecd_ip_deu','2005-01-01',2),('CPIAUCSL','2000-01-01',1)")
    assert D.load_dev(con, "oecd_ip_deu").index.max() == pd.Timestamp("2004-12-01")
    with pytest.raises(D.FactorCutoffError):
        D.load_dev(con, "CPIAUCSL")


def test_solo_data_py_lee_el_warehouse():
    rx = re.compile(r"obs_latest|obs_all_latest|observations|db\.series\(|first_available\(")
    malos = [p.name for p in (REPO / "src" / "intl").glob("*.py") if p.name != "data.py" and rx.search(p.read_text())]
    assert not malos, malos


def test_retrasos_y_asof():
    for sid in ("oecd_ip_deu", "oecd_cpi_deu_idx", "oecd_unemp_fra", "oecd_irlt_ita", "bis_cbpol_de", "jst_usa_cpi"):
        assert Lg.medida(sid) in Lg.RETRASO_DIAS, sid
    s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2004-01-01", "2004-02-01"]))
    rej = pd.date_range("2004-01-31", "2004-05-31", freq="ME")
    a = Lg.asof(s, "oecd_ip_deu", rej)          # enero disponible 31-ene + 60 d = 31-mar
    assert np.isnan(a.iloc[0]) and np.isnan(a.iloc[1]) and a.iloc[2] == 1.0 and a.iloc[3] == 2.0


def test_bono_tr():
    d, c = R.duracion_convexidad(np.array([0.05]))
    assert 7.5 < d[0] < 8.0 and c[0] > 50                        # bono a la par 10 años al 5 %: D ≈ 7,8
    y = pd.Series([5.0, 5.0, 6.0])
    r = R.bono_tr_mensual(y)
    assert r.iloc[1] == pytest.approx(0.05 / 12)                  # sin cambio de tipo: solo el cupón
    assert r.iloc[2] < -0.07                                      # +100 pb: ≈ −7,8 % + cupón + convexidad


@pytest.mark.skipif(not db.WAREHOUSE.exists(), reason="sin warehouse real")
def test_panel_real_antes_de_2005():
    from src.intl import panel as P
    con = db.connect(read_only=True)
    try:
        m = P.mensual(con, desde="2000-01-31")
        a = P.anual(con)
    finally:
        con.close()
    assert m.index.get_level_values("fecha").max() <= D.DEV_END
    assert a.index.get_level_values("año").max() <= 2004
    assert set(m.index.get_level_values("pais")) == set(D.PAISES)
