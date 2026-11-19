"""D1 (docs/factors/D1_tendencia_diaria_spec.md §1): series diarias ≤ 2004 (fallo cerrado), con datos sintéticos."""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
import pytest

from src.factors import data as F


def _con(filas: list[tuple[str, str, float]]):
    con = duckdb.connect(":memory:")
    con.execute("create table obs_latest (series_id varchar, date date, value double)")
    con.executemany("insert into obs_latest values (?, ?, ?)", filas)
    return con


def test_familias_d1():
    for sid in ("DGS10", "DGS20", "ffx_us_mkt_rf_d", "ffx_us_rf_d", "ffx_devxus_mkt_rf_d"):
        assert F.permitida(sid)
    for sid in ("DGS30", "DGS1", "DCOILWTICO", "SP500"):
        assert not F.permitida(sid)


def test_bonos_formula_empalme_y_corte():
    dias = pd.DatetimeIndex(["2004-12-28", "2004-12-29", "2004-12-30", "2004-12-31"])
    filas = [("DGS20", "2004-12-28", 5.00), ("DGS20", "2004-12-29", 5.10),
             # 30-dic sin 20 a (ni arrastre posible si falta el día previo) → usa el 10 a
             ("DGS10", "2004-12-28", 4.00), ("DGS10", "2004-12-29", 4.00), ("DGS10", "2004-12-30", 3.90),
             ("DGS10", "2004-12-31", 3.95), ("DGS20", "2004-12-31", 5.00), ("DGS20", "2005-01-03", 9.99)]
    con = _con(filas)
    b = F.d1_bonos_dev(con, dias)
    assert np.isnan(b.iloc[0])
    assert b.iloc[1] == pytest.approx(0.05 / 252 - 17 * 0.001)            # 20 a: +10 pb
    # 30-dic: el 20 a se arrastra (festivo de bonos) → Δy = 0, solo devengo
    assert b.iloc[2] == pytest.approx(0.051 / 252)
    assert b.iloc[3] == pytest.approx(0.051 / 252 - 17 * (0.050 - 0.051))
    assert b.index.max() <= F.DEV_END


def test_bonos_hueco_largo_del_20_usa_el_10():
    dias = pd.bdate_range("1990-01-01", periods=10)
    filas = [("DGS10", str(d.date()), 8.0 + 0.01 * i) for i, d in enumerate(dias)]
    filas += [("DGS20", str(dias[0].date()), 8.5)]                       # el 20 a desaparece tras el día 0
    b = F.d1_bonos_dev(_con(filas), dias)
    assert b.iloc[8] == pytest.approx(0.0807 / 252 - 17 * 0.0001)          # más allá del arrastre: 10 a


def test_d1_dev_columnas_calendario_y_corte():
    us = pd.bdate_range("2004-12-27", "2004-12-31")
    filas = []
    for d in us:
        filas += [("ffx_us_mkt_rf_d", str(d.date()), 1.0), ("ffx_us_rf_d", str(d.date()), 0.01),
                  ("DGS20", str(d.date()), 5.0), ("DGS10", str(d.date()), 4.0)]
    # internacional: un día que la bolsa EE. UU. no tiene (sábado ficticio) se compone con el siguiente
    filas += [("ffx_devxus_mkt_rf_d", "2004-12-27", 1.0), ("ffx_devxus_rf_d", "2004-12-27", 0.0),
              ("ffx_devxus_mkt_rf_d", "2004-12-28", 1.0), ("ffx_devxus_rf_d", "2004-12-28", 0.0),
              ("ffx_devxus_mkt_rf_d", "2004-12-29", 2.0), ("ffx_devxus_rf_d", "2004-12-29", 0.0),
              ("ffx_devxus_mkt_rf_d", "2005-01-01", 2.0), ("ffx_devxus_rf_d", "2005-01-01", 0.0),
              ("ffx_us_mkt_rf_d", "2005-01-03", 50.0), ("ffx_us_rf_d", "2005-01-03", 0.01)]
    con = _con(filas)
    con.execute("delete from obs_latest where series_id like 'ffx_devxus%' and date = '2004-12-28'")
    con.execute("insert into obs_latest values ('ffx_devxus_mkt_rf_d', '2004-12-25', 1.0), "
                "('ffx_devxus_rf_d', '2004-12-25', 0.0)")
    df, rf = F.d1_dev(con, ruta_oro=None)
    assert list(df.columns) == ["us", "xus", "bonos"] and df.index.max() == pd.Timestamp("2004-12-31")
    assert df.loc["2004-12-28", "us"] == pytest.approx(0.0101) and rf.iloc[0] == pytest.approx(0.0001)
    assert np.isnan(df.loc["2004-12-27", "xus"])                              # primer día del calendario
    assert df.loc["2004-12-28", "xus"] == 0                                   # festivo fuera: no hay rentabilidad
    assert df.loc["2004-12-29", "xus"] == pytest.approx(0.02)


def test_al_calendario_compone():
    r = pd.Series([0.01, 0.02, 0.03], index=pd.DatetimeIndex(["2000-01-03", "2000-01-04", "2000-01-05"]))
    cal = pd.DatetimeIndex(["1999-12-31", "2000-01-03", "2000-01-05"])
    out = F._al_calendario(r, cal)
    assert np.isnan(out.iloc[0])
    assert out.iloc[1] == pytest.approx(0.01)
    assert out.iloc[2] == pytest.approx(1.02 * 1.03 - 1)


def _oro(tmp_path, filas):
    ruta = tmp_path / "oro.txt"
    ruta.write_bytes(("Title: x\r\nDATE          VALUE\r\n" + "".join(f"{f}\r\n" for f in filas)).encode())
    return ruta


def test_oro_corta_en_2004_sin_convertir_y_salta_festivos(tmp_path):
    ruta = _oro(tmp_path, ["2004-12-29    440.000", "2004-12-30         .", "2004-12-31    438.000",
                           "2005-01-03    basura"])                 # si se convirtiera, float() fallaría
    s = F.oro_diario_dev(ruta, sha256=None)
    assert list(s) == [440.0, 438.0] and s.index.max() == pd.Timestamp("2004-12-31")
    with pytest.raises(ValueError):
        F.oro_diario_dev(ruta)                                        # sha256 distinto del registrado


def test_oro_al_calendario_festivos_y_hueco_largo():
    p = pd.Series([100.0, 110.0, 121.0], index=pd.DatetimeIndex(["2000-01-03", "2000-01-05", "2000-01-06"]))
    cal = pd.DatetimeIndex(["2000-01-03", "2000-01-04", "2000-01-05", "2000-01-06"])
    r = F.oro_al_calendario(p, cal)
    assert np.isnan(r.iloc[0]) and r.iloc[1] == 0 and r.iloc[2] == pytest.approx(0.10) and r.iloc[3] == pytest.approx(0.10)
    p2 = pd.Series([100.0, 120.0], index=pd.DatetimeIndex(["2000-01-03", "2000-01-20"]))
    r2 = F.oro_al_calendario(p2, pd.bdate_range("2000-01-03", "2000-01-20"))
    assert r2.iloc[1:6].eq(0).all() and r2.iloc[6:].isna().all()     # más de 5 días sin fixing → NaN


@pytest.mark.skipif(not F.RUTA_ORO_D.exists(), reason="sin el fichero real del oro")
def test_oro_real_cuadra_sha_y_corte():
    s = F.oro_diario_dev()
    assert s.index.min() == pd.Timestamp("1968-04-01") and s.index.max() <= F.DEV_END
