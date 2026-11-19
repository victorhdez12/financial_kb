"""S1 (docs/factors/S1_rotacion_sectorial_spec.md §1): las 12 industrias de Ken French solo ≤ 2004 (fallo cerrado)."""
from __future__ import annotations

import zipfile

import duckdb
import pandas as pd
import pytest

from src.factors import data as F
from src.warehouse import db


@pytest.fixture
def con_ind12():
    con = duckdb.connect(":memory:")
    con.execute("create table obs_latest (series_id varchar, date date, value double)")
    for n in F.INDUSTRIAS12:
        sid = f"ff_ind12_{n.lower()}_vw_m"
        con.execute("insert into obs_latest values (?, '2004-11-01', 1.0), (?, '2004-12-01', 2.0), "
                    "(?, '2005-01-01', 3.0)", [sid, sid, sid])
    con.execute("insert into obs_latest values ('ff_ind12_buseq_ew_m', '2004-12-01', 1.0)")
    yield con
    con.close()


def test_industrias12_cortan_en_2004(con_ind12):
    df = F.industrias12_dev(con_ind12)
    assert list(df.columns) == list(F.INDUSTRIAS12)
    assert df.index.max() == pd.Timestamp("2004-12-01") and len(df) == 2
    assert df.loc["2004-12-01", "BusEq"] == pytest.approx(0.02)      # % → fracción


def test_solo_value_weighted(con_ind12):
    assert F.permitida("ff_ind12_buseq_vw_m")
    for sid in ("ff_ind12_buseq_ew_m", "ff_ind12_buseq_vw_a", "ff_ind12_inventada_vw_m"):
        assert not F.permitida(sid)
    with pytest.raises(F.FactorCutoffError):
        F.load_dev(con_ind12, "ff_ind12_buseq_ew_m")


def test_huecos_fallan(con_ind12):
    con_ind12.execute("delete from obs_latest where series_id = 'ff_ind12_telcm_vw_m' and date = '2004-11-01'")
    with pytest.raises(ValueError):
        F.industrias12_dev(con_ind12)


def _zip(tmp_path, filas: list[str]):
    cab = ",".join(F.INDUSTRIAS12)
    texto = "\n".join(["cabecera", "", "  Average Value Weighted Returns -- Monthly", f",{cab}", *filas, "",
                       "  Average Equal Weighted Returns -- Monthly", f",{cab}"])
    ruta = tmp_path / "12_Industry_Portfolios_CSV.zip"
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("12_Industry_Portfolios.csv", texto)
    return ruta


def test_zip_descarta_2005_sin_convertirlo(tmp_path):
    ok = ",".join(["1.00"] * 12)
    # la fila de 2005 lleva basura: si se convirtiera, float() fallaría
    ruta = _zip(tmp_path, [f"200411,{ok}", f"200412,{ok}", "200501," + ",".join(["xx"] * 12)])
    df = F.industrias12_zip_dev(ruta)
    assert df.index.max() == pd.Timestamp("2004-12-01") and len(df) == 2
    assert (df == 0.01).all().all()


@pytest.mark.skipif(not db.WAREHOUSE.exists() or not F.ZIP_IND12.exists(), reason="sin warehouse o zip reales")
def test_reales_cuadran_con_el_zip_y_terminan_en_2004():
    con = db.connect(read_only=True)
    try:
        w = F.industrias12_dev(con)
        mkt, rf = F.mercado_dev(con)
    finally:
        con.close()
    z = F.industrias12_zip_dev()
    assert w.index.max() == F.DEV_END.replace(day=1) and mkt.index.max() <= F.DEV_END
    assert (w - z.reindex(w.index)).abs().max().max() < 1e-9
    assert w.index.min() == pd.Timestamp("1926-07-01") and len(mkt) == len(w)
