"""INT-3b/3c: construcción de activos (sintético) y corte de la capa curada."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.intl import activos3b as A
from src.intl import data as D


def test_familias_nuevas_y_ajenas():
    for sid in ("aqr_clr_ew_xret_m", "damodaran_baa_corp_tr", "boe_uk_corp_bond_yield_a", "gold_wb_usd_m", "BAA",
                "oecd_gdpq_deu", "bis_creditgap_de_ratio"):
        assert D.permitida(sid), sid
    for sid in ("CPIAUCSL", "aqr_clr_x", "damodaran_sp500_tr", "VIXCLS", "bis_creditgap_de_gap", "oecd_gdpq_ea20x"):
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


# ---------------------------------------------------------------- inferencia de la corrida (src/intl/int3b.py)
from src.intl import int3b as B  # noqa: E402


def test_nw_igual_a_statsmodels():
    import statsmodels.api as sm
    r = np.random.default_rng(1)
    x = (r.random(120) < .3).astype(float)
    y = r.standard_normal(120) + .3 * x
    f = sm.OLS(y, sm.add_constant(x)).fit(cov_type="HAC", cov_kwds={"maxlags": 4, "use_correction": True})
    o = B.nw(y, x, 4)
    assert np.isclose(o["t"], f.tvalues[1]) and np.isclose(o["efecto"], f.params[1])


def test_ts_contraste_detecta_y_calibra():
    r = np.random.default_rng(2)
    años = np.arange(1878, 2000)
    x = pd.Series(np.clip(np.convolve(r.random(len(años) + 4), np.ones(5) / 5, "valid")[:len(años)], 0, 1), index=años)
    y0 = pd.Series(r.standard_normal(len(años)) * 0.2, index=años)
    nulo = B.ts_contraste(y0, x)
    assert nulo["placebo"]["placebos"] == len(años) - 11 and nulo["placebo"]["phi"] >= 1
    fuerte = B.ts_contraste(y0 + 2.0 * (x - x.mean()) / x.std() * 0.2, x)
    assert fuerte["placebo"]["p_cal"] < 0.001 and fuerte["placebo"]["supera_p95"]
    assert fuerte["efecto_1878_1949"] > 0 and fuerte["efecto_1950_1999"] > 0


def _panel(efecto: float, seed: int = 3) -> pd.DataFrame:
    r = np.random.default_rng(seed)
    filas = []
    for p in ["A", "B", "C", "D", "E", "F"]:
        d = (r.random(100) < 0.3).astype(float)
        choque = 0.0
        for i, a in enumerate(range(1900, 2000)):
            filas.append({"pais": p, "año": a, "d": d[i], "y": efecto * d[i] + r.standard_normal() * 0.1})
    f = pd.DataFrame(filas)
    comun = pd.Series(r.standard_normal(100) * 0.1, index=range(1900, 2000))
    f["y"] += f["año"].map(comun)
    return f


def test_panel_contraste_y_criterios():
    nulo = B.panel_contraste(_panel(0.0), "y", "d")
    assert set(nulo["por_pais_sin_encoger"]) == set("ABCDEF") and nulo["placebo"]["placebos"] > 50
    s = B.panel_contraste(_panel(-0.1), "y", "d")
    c = B.criterios(s, -1, holm_ok=s["placebo"]["p_cal"] < 0.0125, mundial=False)
    assert c["ESTABLECIDO"], c
    c2 = B.criterios(s, +1, holm_ok=True, mundial=False)
    assert not c2["ESTABLECIDO"] and not c2["1_signo"]


def test_descomposicion_lineal_suma_al_total():
    f = _panel(-0.05)
    f["p1"] = f.y * 0.3 + 0.01
    f["p2"] = f.y - f.p1
    tot = B.panel_contraste(f, "y", "d", placebo=False, paises=False)["efecto"]
    partes = sum(B.panel_contraste(f, c, "d", placebo=False, paises=False)["efecto"] for c in ("p1", "p2"))
    assert np.isclose(tot, partes)
