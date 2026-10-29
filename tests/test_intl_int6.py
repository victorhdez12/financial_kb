"""Tests sintéticos del motor de INT-6 (src/intl/int6.py). Sin datos reales de resultado."""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.int4_sensibilidad_liston import auc_estrat as auc_estrat_int4
from src.intl import data as D
from src.intl import int4 as M
from src.intl import int6 as S

PAISES = [f"P{i}" for i in range(8)]


def test_familia_diferencial_uk_permitida():
    assert D.permitida("boe_uk_corp_bond_spread_m")
    assert not D.permitida("fed_ebp_m") and not D.permitida("boe_uk_corp_bond_spread_x")


def test_auc_estrat_igual_que_int4():
    rng = np.random.default_rng(0)
    y = (rng.random(600) < 0.2).astype(float)
    p = rng.random(600) + 0.3 * y
    g = np.array(PAISES * 75)
    assert np.isclose(S.auc_estrat(y, p, g), auc_estrat_int4(y, p, g))


def test_hiper_fuera_t_y_t_mas_1():
    s = pd.Series({("A", 1922): 0.8, ("A", 1923): 0.1, ("B", 1950): 0.6, ("B", 1951): np.nan})
    assert S.hiper_fuera(s) == {("A", 1922), ("A", 1921), ("B", 1950), ("B", 1949)}


def _crisis(paises, años, semilla=0):
    rng = np.random.default_rng(semilla)
    return {c: pd.Series((rng.random(len(años)) < 0.05).astype(float), index=list(años)) for c in paises}


def test_objetivo_crisis_igual_que_la_potencia():
    import scripts.int6_potencia as POT
    años = range(1870, 2005)
    cr = _crisis(POT.NUCLEO, años)
    a = pd.concat({c: pd.DataFrame({"crisisjst": s}) for c, s in cr.items()})
    a.index.names = ["pais", "año"]
    años_pais = {c: set(años) for c in POT.NUCLEO}
    ref = POT.objetivo_crisis(a, años_pais, 1, 1871, True)
    nuevo = S.objetivo_crisis(cr, años_pais, POT.NUCLEO, 1, 1871, True)
    pd.testing.assert_frame_equal(ref.reset_index(drop=True), nuevo.reset_index(drop=True), check_dtype=False)
    fuera = {(POT.NUCLEO[0], 1900)}
    assert len(S.objetivo_crisis(cr, años_pais, POT.NUCLEO, 1, 1871, True, fuera=fuera)) == len(nuevo) - int(
        ((nuevo.pais == POT.NUCLEO[0]) & (nuevo.t == 1900)).sum())


def test_objetivo_crisis_excluye_tras_inicio_y_guerras():
    cr = {"A": pd.Series(0.0, index=range(1870, 2005))}
    cr["A"][1900] = 1.0
    f = S.objetivo_crisis(cr, {"A": set(range(1870, 2005))}, ["A"], 1, 1871, True)
    assert f.loc[f.t == 1899, "y"].item() == 1
    assert not set(range(1900, 1905)) & set(f.t)          # sin inicio en t − 4 … t
    assert 1905 in set(f.t)
    assert not set(range(1913, 1919)) & set(f.t)          # ventana t … t + 1 toca 1914-1918
    f3 = S.objetivo_crisis(cr, {"A": set(range(1870, 2005))}, ["A"], 1, 1871, True, excluir_tras=2)
    assert 1903 in set(f3.t) and 1902 not in set(f3.t)


def test_liston_crisis_censura():
    cr = {"A": pd.Series([0.0, 1.0, 0.0], index=[1880, 1890, 1900])}
    f = pd.DataFrame({"pais": ["A", "A", "A"], "t": [1885, 1890, 1899]})
    b = S.liston_crisis(f, cr, {"A": 1875}).ravel()
    assert np.allclose(b, np.log1p([10, 0, 9]))


def test_ts_mensual_detecta_negativo_y_calibra():
    rng = np.random.default_rng(1)
    x = rng.normal(size=384)
    y = -0.3 * x + rng.normal(size=384)
    r = S.ts_mensual(y, x)
    assert r["efecto"] < 0 and r["placebo"]["p_cal"] < 0.001 and r["placebo"]["supera_p95"]
    assert r["placebo"]["placebos"] == 384 - 2 * 12 + 1 and r["lags"] == 6
    assert np.isclose(r["r_estandarizada"], np.corrcoef(x, y)[0, 1], atol=1e-9)
    nulo = S.ts_mensual(rng.normal(size=384), x)
    assert nulo["placebo"]["phi"] >= 1.0


def _panel(b=0.03, semilla=2, n_años=100):
    rng = np.random.default_rng(semilla)
    filas = []
    choque = rng.normal(size=n_años) * 0.15                 # choque común por año
    for c in PAISES:
        x = rng.normal(size=n_años)
        y = b * x + choque + rng.normal(size=n_años) * 0.1
        filas.append(pd.DataFrame({"pais": c, "año": np.arange(1900, 1900 + n_años), "x": x, "y": y}))
    return pd.concat(filas, ignore_index=True)


def test_panel_continuo_recupera_pendiente_y_criterios():
    f = _panel()
    r = S.panel_continuo(f, "y", "x")
    assert abs(r["efecto"] - 0.03) < 0.01 and r["efecto_efectos_de_año"] > 0 and r["efecto_1950_2004"] > 0
    assert r["placebo"]["p_cal"] < 0.01
    c = S.criterios_panel(r, +1, holm_ok=True)
    assert c["ESTABLECIDO"]
    c = S.criterios_panel(r, -1, holm_ok=True)
    assert not c["ESTABLECIDO"] and not c["1_signo"]


def test_panel_continuo_nulo_no_establece():
    r = S.panel_continuo(_panel(b=0.0, semilla=3), "y", "x")
    assert r["placebo"]["p_cal"] > 0.01


def test_winsor_solo_mira_el_indicador():
    x = pd.Series(np.r_[np.arange(98, dtype=float), -1e6, 1e6])
    w = S.winsor(x)
    assert w.min() > -1e6 and w.max() < 1e6 and (w.iloc[10:90] == x.iloc[10:90]).all()


def _giro(señal=1.5, semilla=4):
    rng = np.random.default_rng(semilla)
    años = list(range(M.A0, M.A1 + 1))
    pan = pd.DataFrame(rng.normal(size=(len(años), len(PAISES))), index=años, columns=PAISES)
    filas = []
    for c in PAISES:
        for t in años[1:-1]:
            eta = -2.5 + señal * pan.at[t, c]
            filas.append({"pais": c, "t": t, "y": int(rng.random() < 1 / (1 + np.exp(-eta)))})
    f = pd.DataFrame(filas)
    base = rng.normal(size=(len(f), 1))
    return f, base, pan


def test_evaluar_con_señal_y_sin_señal():
    f, base, pan = _giro()
    r = S.evaluar(f, base, [pan], periodos={"a": (1871, 1913), "b": (1919, 2004)}, B_=200)
    assert r["d_auc"] > 0.1 and r["d_auc_ic95"][0] > 0 and r["placebo"]["z"] > 3
    assert r["placebo"]["desplazamientos"] == len(M.KS)
    assert r["periodo_a"]["d_auc"] > 0 and r["temporal_1950_2004"]["d_auc"] > 0
    c = S.criterios_auc(r, True, True, True, "x")
    assert set(c) >= {"i_dauc_estrat_ic_holm6", "ii_z_placebo_holm6", "iii_dlogloss_neg", "iv_x", "ESTABLECIDO"}
    f0, base0, pan0 = _giro(señal=0.0, semilla=5)
    r0 = S.evaluar(f0, base0, [pan0], placebo=False, temporal=False, B_=200)
    assert abs(r0["d_auc"]) < 0.1


def test_mirar_desplaza_en_circulo_igual_en_todos():
    años = list(range(M.A0, M.A1 + 1))
    pan = pd.DataFrame({c: np.arange(len(años), dtype=float) + i * 1000 for i, c in enumerate(PAISES[:2])}, index=años)
    f = pd.DataFrame({"pais": ["P0", "P1"], "t": [1880, 1880]})
    v = S.mirar(f, [pan], k=6).ravel()
    assert v[0] == 1880 - 6 - M.A0 and v[1] == 1000 + 1880 - 6 - M.A0


def test_delta_diciembre_y_empalme_no_mezclan_niveles():
    idx_uk = pd.date_range("1915-01-01", "1920-12-01", freq="MS")
    uk = pd.Series(np.where(idx_uk.month == 12, idx_uk.year - 1900.0, np.nan), index=idx_uk)   # Δ = 1 cada año
    idx_us = pd.date_range("1919-01-01", "1922-12-01", freq="MS")
    us = pd.Series(np.where(idx_us.month == 12, 100 + 3.0 * (idx_us.year - 1919), np.nan), index=idx_us)  # Δ = 3
    x = S.empalme(S.delta_diciembre(uk), S.delta_diciembre(us))
    assert x.loc[1916] == 1 and x.loc[1918] == 1
    assert 1919 not in x.index or np.isnan(x.loc[1919])        # sin Δ de EE. UU. en 1919
    assert x.loc[1920] == 3 and x.loc[1922] == 3


def test_nivel_mediana10():
    idx = pd.date_range("1900-01-01", "1915-12-01", freq="MS")
    s = pd.Series(np.where(idx.month == 12, idx.year - 1900.0, np.nan), index=idx)
    n = S.nivel_mediana10(s)
    assert n.index.min() == 1909 and np.isclose(n.loc[1909], 9 - 4.5)


def test_cuota_otros_minimo_y_pesos():
    años = list(range(M.A0, M.A1 + 1))
    cae = pd.DataFrame(0.0, index=años, columns=PAISES)
    cae.loc[1900, PAISES[1:4]] = 1.0
    cae.loc[1901, PAISES[1:]] = np.nan                       # solo P0 con dato: < 5
    r = S.cuota_otros(cae, PAISES, PAISES)
    assert np.isclose(r.at[1900, "P0"], 3 / 7) and np.isnan(r.at[1901, "P5"])
    pesos = pd.DataFrame(1.0, index=años, columns=PAISES)
    pesos["P1"] = 4.0
    rp = S.cuota_otros(cae, PAISES, PAISES, pesos)
    assert np.isclose(rp.at[1900, "P0"], 6 / 10)
