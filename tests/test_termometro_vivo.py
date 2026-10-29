"""Termómetro informativo en vivo (src/report/termometro_vivo.py). Sintéticos sin red (warehouse en memoria) y, si existe
el warehouse real, reproducción del desarrollo con fecha de corte 2004-12."""
import json

import duckdb
import numpy as np
import pandas as pd
import pytest

from src.intl import data as D
from src.report import termometro_vivo as V
from src.warehouse import db

EN_RECESION = {"ESP", "DNK", "AUS"}      # núcleo con T2, núcleo sin bolsa, prueba


def _obs(sid, fechas, valores):
    return pd.DataFrame({"series_id": sid, "date": pd.to_datetime(fechas).date, "value": np.asarray(valores, float)})


def _warehouse(hasta_m="2026-09-01", hasta_q="2026-04-01", choque=0.0):
    """obs_latest sintético para los 18 países desde 1985. `choque` altera todo lo posterior a 2026-03 (para comprobar
    que no se mira el futuro)."""
    rng = np.random.default_rng(0)
    fm = pd.date_range("1985-01-01", hasta_m, freq="MS")
    fq = pd.date_range("1985-01-01", hasta_q, freq="QS")
    tm, tq = np.arange(len(fm)), np.arange(len(fq))
    pos_m, pos_q = fm > pd.Timestamp("2026-03-01"), fq > pd.Timestamp("2026-03-01")
    partes = []
    for i, c in enumerate(V.TODOS):
        lc, i2 = c.lower(), D.ISO2[c]
        ir3 = 3 + 2 * np.cos(tm / 30 + i) + choque * pos_m
        partes += [_obs(f"oecd_irlt_{lc}", fm, 5 + np.sin(tm / 40 + i) + choque * pos_m),
                   _obs(f"oecd_ir3m_{lc}", fm, ir3),
                   _obs(f"oecd_cpi_{lc}_idx", fm, 100 * np.exp(0.002 * tm + 0.002 * rng.normal(size=len(tm)))),
                   _obs(f"oecd_share_{lc}", fm, 100 * np.exp(0.005 * tm + 0.05 * np.sin(tm / 9 + i)) * (1 + choque * pos_m)),
                   _obs(f"bis_creditgap_{i2}_ratio", fq, 100 + 10 * np.sin(tq / 15 + i) + choque * pos_q)]
        g = 100 * np.exp(0.005 * tq)
        caida = (fq >= pd.Timestamp(f"{1991 + i % 4}-01-01")) & (fq < pd.Timestamp(f"{1992 + i % 4}-07-01"))
        g = g * 0.98 ** np.cumsum(caida)     # recesión histórica (≤ 2004): da la media de referencia de T2
        if c in EN_RECESION:                 # cae un 3 % por trimestre desde 2025T3 → entra en 2025T4
            g = g * np.where(fq >= pd.Timestamp("2025-07-01"), 0.97 ** (np.cumsum(fq >= pd.Timestamp("2025-07-01"))), 1)
        partes.append(_obs(f"oecd_gdpq_{lc}", fq, g * (1 + choque * pos_q)))
    partes.append(_obs("jst_usa_cpi", ["2010-01-01"], [1.0]))
    con = duckdb.connect(":memory:")
    df = pd.concat(partes, ignore_index=True)  # noqa: F841
    con.execute("create table obs_latest as select series_id, date, value from df")
    return con


@pytest.fixture(scope="module")
def vivo():
    con = _warehouse()
    res = V.termometro(con, "2026-10-29")
    con.close()
    return res


def test_estado_y_probabilidad_solo_en_recesion(vivo):
    assert vivo["fecha_calculo"] == "2026-09-30"
    assert set(vivo["en_recesion"]) == EN_RECESION
    p = vivo["paises"]
    assert p["ESP"]["estado"]["ultimo_trimestre_pib"] == "2026Q2"
    s = p["ESP"]["salida_12m"]
    assert 0 < s["probabilidad"] < 1 and s["banda"] in {"bajo", "medio", "alto", "muy alto"}
    assert s["aviso"] == V.AVISO_NIVEL and s["empuja_mas"]["variable"] in V.VARS_T2
    assert "sin bolsa" in p["DNK"]["salida_12m"]["motivo"] and "probabilidad" not in p["DNK"]["salida_12m"]
    assert "prueba" in p["AUS"]["salida_12m"]["motivo"]
    assert all(p[c]["salida_12m"] is None for c in V.TODOS if c not in EN_RECESION)
    assert p["DNK"]["indicadores"]["C6"]["valor"] is None                      # sin bolsa mensual
    for c in V.TODOS:
        assert set(p[c]["indicadores"]) == {k for k, *_ in V.INDICADORES}


def test_contribuciones_suman_al_logit(vivo):
    s = vivo["paises"]["ESP"]["salida_12m"]
    c = s["contribuciones_logit"]
    assert max(c.values(), key=abs) == pytest.approx(s["empuja_mas"]["contribucion_logit"])


def test_markdown(vivo):
    md = V.markdown(vivo)
    assert V.AVISO in md and V.AVISO_T2 in md and "**EE. UU.**" in md and "- ESP: **" in md and V.AVISO_NIVEL in md
    assert "- DNK" not in md                                                   # sin probabilidad
    assert md.count("| USA |") == 1


def test_no_mira_el_futuro():
    a = V.termometro(_warehouse(), "2026-03-31")
    b = V.termometro(_warehouse(choque=1.0), "2026-03-31")    # todo lo posterior a 2026-03 cambia
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_nunca_jst():
    con = _warehouse()
    with pytest.raises(D.FactorCutoffError):
        V._serie(con, "jst_usa_cpi", pd.Timestamp("2026-01-31"))
    with pytest.raises(D.FactorCutoffError):
        V._serie(con, "CPIAUCSL", pd.Timestamp("2026-01-31"))


def test_bandas_y_fin_de_mes():
    pct = {"p50": 0.8, "p80": 0.9, "p95": 0.95}
    assert [V.banda(x, pct) for x in (0.5, 0.8, 0.9, 0.95, 0.99)] == ["bajo", "medio", "alto", "muy alto", "muy alto"]
    assert V.fin_de_mes("2026-10-29") == pd.Timestamp("2026-09-30")
    assert V.fin_de_mes("2026-10-31") == pd.Timestamp("2026-10-31")


def test_parametros_incompletos(tmp_path):
    d = json.loads(V.CONGELADO.read_text())
    assert V.parametros()["paises_T2"] == ["BEL", "DEU", "ESP", "FIN", "FRA", "GBR", "ITA", "NLD", "NOR", "PRT", "SWE",
                                           "USA"]
    d["final"]["rectas"]["C2"]["USA"]["b"] = None
    p = tmp_path / "x.json"
    p.write_text(json.dumps(d))
    with pytest.raises(V.ParametrosIncompletos, match="recta C2 USA"):
        V.parametros(p)
    d = json.loads(V.CONGELADO.read_text())
    d["veredicto"]["pasa_agregado"]["T2"] = False
    p.write_text(json.dumps(d))
    with pytest.raises(V.ParametrosIncompletos, match="T2"):
        V.parametros(p)


def test_fuera_de_src_intl():
    """El acceso en vivo está en src/report: src/intl/ sigue leyendo solo con load_dev (tests/test_intl_panel.py)."""
    assert "intl" not in V.__file__.split("/src/")[1]


@pytest.mark.skipif(not db.WAREHOUSE.exists(), reason="sin warehouse real")
def test_corte_2004_reproduce_desarrollo():
    """Con fecha de corte 2004-12 el bloque mensual es idéntico al de src/intl/panel.mensual (load_dev) y las
    probabilidades traducidas y recalibradas de T2 en los meses en recesión 1960-2004 del núcleo reproducen los
    percentiles de referencia del JSON de la puerta (295 meses). Con los parámetros sin redondear (recalculados con el
    código de la puerta, ≤ 2004) la diferencia máxima por mes es ≈ 5e-4 (medido el 29-oct con el JSON corregido)."""
    from src.intl import panel as P
    from src.intl import termometro as T
    con = db.connect(read_only=True)
    try:
        pm, bis, pib, corte = V.cargar(con, "2004-12-31")
        dev = P.mensual(con)
    finally:
        con.close()
    cols = ["curva", "tipo_3m", "ipc_yoy", "bolsa_12m"]
    assert np.allclose(pm[cols].to_numpy(), dev[cols].reindex(pm.index).to_numpy(), equal_nan=True)
    for c in V.TODOS:
        cur = D.load_dev_curado(f"oecd_gdpq_{c.lower()}")
        assert np.allclose(cur.to_numpy(), pib[c].to_numpy()) and (cur.index == pib[c].index).all(), c
    par = V.parametros()
    mens = T.mensuales(pm, bis, pib, V.NUCLEO, V.TODOS)
    tr = T.traducir(mens, par["rectas"], V.TODOS)
    rej = mens["C1"].index
    ps = []
    for c in V.NUCLEO:
        est = T.estado_mensual(T.fechado_trimestral(pib[c]), rej, pib[c].index.min())
        p, _ = V.prob_salida(tr, est, c, par["b_T2"], par["cal_T2"])
        ps.append(p[np.isfinite(p)])
    v = np.concatenate(ps)
    ref = json.loads(V.CONGELADO.read_text())["final"]["percentiles_referencia"]["T2"]
    assert len(v) == ref["meses"]
    for q in (50, 80, 95):
        assert np.quantile(v, q / 100) == pytest.approx(ref[f"p{q}"], abs=5e-4)
