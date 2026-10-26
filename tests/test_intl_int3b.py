"""INT-3b/3c: construcción de activos (sintético) y corte de la capa curada."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.intl import activos3b as A
from src.intl import data as D


def test_familias_nuevas_y_ajenas():
    for sid in ("aqr_clr_ew_xret_m", "damodaran_baa_corp_tr", "boe_uk_corp_bond_yield_a", "gold_wb_usd_m", "BAA"):
        assert D.permitida(sid), sid
    for sid in ("CPIAUCSL", "aqr_clr_x", "damodaran_sp500_tr", "VIXCLS"):
        assert not D.permitida(sid), sid


def test_curado_corta_en_2004(tmp_path, monkeypatch):
    monkeypatch.setattr(D.db, "DATA_ROOT", tmp_path)
    p = tmp_path / "curated" / "aqr_clr"
    p.mkdir(parents=True)
    pd.DataFrame({"date": pd.to_datetime(["2004-12-01", "2005-01-01"]).date, "value": [1.0, 2.0]}).to_parquet(
        p / "aqr_clr_ew_xret_m.parquet")
    s = D.load_dev_curado("aqr_clr_ew_xret_m")
    assert s.index.max() == pd.Timestamp("2004-12-01") and len(s) == 1
    with pytest.raises(D.FactorCutoffError):
        D.load_dev_curado("CPIAUCSL")


def test_compuesto_y_suma_anual():
    idx = pd.date_range("2000-01-01", periods=24, freq="MS")
    s = pd.Series(1.0, index=idx)
    assert A.compuesto_anual(s).round(6).tolist() == [round(1.01 ** 12 - 1, 6)] * 2
    assert A.suma_anual(s).round(6).tolist() == [0.12, 0.12]
    assert A.compuesto_anual(s.iloc[:-1]).isna().tolist() == [False, True]


def test_tr_desde_rendimiento_sin_cambio_es_el_cupon():
    y = pd.Series([5.0, 5.0, 5.0], index=[2000, 2001, 2002])
    r = A.tr_desde_rendimiento(y)
    assert np.isnan(r.iloc[0]) and np.allclose(r.iloc[1:], 0.05)
    r2 = A.tr_desde_rendimiento(pd.Series([5.0, 6.0], index=[2000, 2001]))
    assert r2.iloc[1] < 0                                     # sube el tipo → pérdida de capital
