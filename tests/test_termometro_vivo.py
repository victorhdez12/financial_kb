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


def _warehouse(hasta_m="2026-09-01", hasta_q="2026-04-01", choque=0.0, cortes=None):
    """obs_latest sintético para los 18 países desde 1985. `choque` altera todo lo posterior a 2026-03 (para comprobar
    que no se mira el futuro); `cortes` = {series_id: última fecha} corta esas series."""
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
    df = pd.concat(partes, ignore_index=True)
    for sid, hasta in (cortes or {}).items():
        df = df[(df.series_id != sid) | (pd.to_datetime(df.date) <= pd.Timestamp(hasta))]
    con.execute("create table obs_latest as select series_id, date, value from df")
    return con


def _refs(con, fecha="2026-10-29"):
    """Referencias ≤ 2004 del warehouse sintético (las congeladas son las del real)."""
    from src.intl import termometro as T
    par = V.parametros()
    pm, bis, pib, _ = V.cargar(con, fecha)
    mens = T.mensuales(pm, bis, pib, V.NUCLEO, V.TODOS)
    return V.referencias(mens, T.traducir(mens, par["rectas"], V.TODOS), pib, par)


def _termometro(con, fecha):
    return V.termometro(con, fecha, refs=_refs(con, fecha))


@pytest.fixture(scope="module")
def vivo():
    con = _warehouse()
    res = _termometro(con, "2026-10-29")
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
    """b0 + b·centro + Σ contribuciones = logit sin recalibrar del mes (recalculado aparte), y su recalibración da la
    probabilidad publicada; «lo que más pesa» es la contribución mayor en valor absoluto (Validador, diff 4 a)."""
    from src.intl import termometro as T
    s = vivo["paises"]["ESP"]["salida_12m"]
    c = s["contribuciones_logit"]
    assert max(c.values(), key=abs) == pytest.approx(s["empuja_mas"]["contribucion_logit"])
    con = _warehouse()
    par, refs = V.parametros(), _refs(con)
    pm, bis, pib, _ = V.cargar(con, "2026-10-29")
    mens = T.mensuales(pm, bis, pib, V.NUCLEO, V.TODOS)
    _, _, Z2 = V._estados(T.traducir(mens, par["rectas"], V.TODOS), pib, mens["C1"].index, par)
    b, z, centro = par["b_T2"], Z2["ESP"][-1], np.array(refs["centro_T2"])
    lg = b[0] + b[1:] @ z
    assert b[0] + b[1:] @ centro + sum(c.values()) == pytest.approx(lg, abs=6 * 5e-4)    # contribuciones a 3 decimales
    assert [c[v] for v in V.VARS_T2] == pytest.approx(list(b[1:] * (z - centro)), abs=5e-4)
    assert T.aplicar_cal(np.array([1 / (1 + np.exp(-lg))]), par["cal_T2"])[0] == pytest.approx(s["probabilidad"],
                                                                                                abs=5e-4)


def test_markdown(vivo):
    md = V.markdown(vivo)
    assert V.AVISO in md and V.AVISO_T2 in md and "**EE. UU.**" in md and "- ESP: **" in md and V.AVISO_NIVEL in md
    assert "- DNK" not in md                                                   # sin probabilidad
    assert md.count("| USA |") == 1


def test_no_mira_el_futuro():
    a = _termometro(_warehouse(), "2026-03-31")
    b = _termometro(_warehouse(choque=1.0), "2026-03-31")    # todo lo posterior a 2026-03 cambia
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_aviso_serie_cortada(vivo):
    """Series cortadas o viejas (como GBR real, tipo a 3 meses hasta 2026-02, aquí sin la serie del BoE para empalmar):
    el indicador sale «—» con aviso por país;
    un país sin PIB trimestral sale "sin dato" y el resto del termómetro sigue (Validador, diff 2)."""
    con = _warehouse(cortes={"oecd_ir3m_gbr": "2026-02-01", "bis_creditgap_de_ratio": "2025-01-01",
                             "oecd_gdpq_fra": "2025-07-01", "oecd_gdpq_bel": "1900-01-01",
                             "oecd_ir3m_esp": "2026-02-01"})
    res = _termometro(con, "2026-10-29")
    p = res["paises"]
    assert p["GBR"]["indicadores"]["C1"]["valor"] is None
    assert p["GBR"]["indicadores"]["C1"]["sin_dato"] == ["sin tipo a 3 meses desde 2026-02 (último dato)"]
    assert p["GBR"]["avisos_datos"] == ["Curva 10a−3m (media 12 m): sin tipo a 3 meses desde 2026-02 (último dato)"]
    assert p["DEU"]["avisos_datos"] == ["Δ5 años crédito/PIB (BIS): sin crédito/PIB (BIS) desde 2025Q1 (último dato)"]
    assert p["FRA"]["estado"]["en_recesion"] is None
    assert p["FRA"]["avisos_datos"] == ["estado de recesión: sin PIB trimestral desde 2025Q3 (último dato)"]
    assert p["BEL"]["estado"] == {"en_recesion": None, "ultimo_trimestre_pib": None, "meses_desde_entrada": None}
    assert p["BEL"]["avisos_datos"] == ["estado de recesión: sin PIB trimestral (sin serie)"]
    # ESP en recesión sin tipo a 3 meses: sin probabilidad, y se dice qué variables faltan
    assert p["ESP"]["estado"]["en_recesion"] is True
    assert p["ESP"]["salida_12m"] == {"motivo": "falta algún indicador de T2 este mes (S1 curva, S2 Δ tipo real corto)"}
    assert p["ESP"]["avisos_datos"] == ["Curva 10a−3m (media 12 m): sin tipo a 3 meses desde 2026-02 (último dato)"]
    assert all(not p[c]["avisos_datos"] for c in V.TODOS if c not in {"GBR", "DEU", "FRA", "BEL", "ESP"})
    assert set(res["en_recesion"]) == EN_RECESION and p["USA"]["indicadores"]["C1"]["valor"] is not None
    assert all(not vivo["paises"][c]["avisos_datos"] for c in V.TODOS)              # sin cortes: sin avisos
    md = V.markdown(res)
    assert "> - GBR: Curva 10a−3m (media 12 m): sin tipo a 3 meses desde 2026-02 (último dato)." in md
    assert "> - BEL: estado de recesión: sin PIB trimestral (sin serie)." in md
    assert "Datos que faltan" not in V.markdown(vivo)


def test_no_mira_el_futuro_estricto():
    """Con fecha 2026-03-31, datos con fecha ≤ corte que aún no se conocían ese día (retrasos as of) no cambian nada:
    tipos y bolsa de marzo, IPC de febrero y marzo, PIB 2026T1, BIS 2025T4. Un dato ya conocido (tipo a 10 años de
    febrero) sí cambia el resultado (Validador, diff 4 b)."""
    def alterado(sql):
        con = _warehouse()
        con.execute(sql)
        return _termometro(con, "2026-03-31")
    a = _termometro(_warehouse(), "2026-03-31")
    b = alterado("update obs_latest set value = value * case when series_id like 'oecd_gdpq_%' then 0.5 else 3 end "
                 "where (date = '2026-03-01' and regexp_matches(series_id, '^oecd_(irlt|ir3m|share)_')) "
                 "or (date in ('2026-02-01', '2026-03-01') and regexp_matches(series_id, '^oecd_cpi_.*_idx$')) "
                 "or (date = '2026-01-01' and series_id like 'oecd_gdpq_%') "
                 "or (date = '2025-10-01' and series_id like 'bis_creditgap_%')")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    c = alterado("update obs_latest set value = value * 3 where date = '2026-02-01' and series_id = 'oecd_irlt_usa'")
    assert c["paises"]["USA"]["indicadores"]["C1"]["valor"] != a["paises"]["USA"]["indicadores"]["C1"]["valor"]


def test_nunca_jst():
    con = _warehouse()
    with pytest.raises(D.FactorCutoffError):
        V._serie(con, "jst_usa_cpi", pd.Timestamp("2026-01-31"))
    with pytest.raises(D.FactorCutoffError):
        V._serie(con, "CPIAUCSL", pd.Timestamp("2026-01-31"))


def test_percentil_empates():
    """Rango medio: S4 = 0 con el 60 % de los meses en 0 y ninguno por debajo → p30 (con «≤» salía p60)."""
    h = np.r_[np.zeros(60), np.linspace(0.1, 1, 40)]
    assert V._pct(h, 0.0) == (30, 100)
    assert V._pct(h, 1.0) == (100, 100) and V._pct(h, -1.0) == (0, 100)
    assert V._pct(np.arange(100.0), 49.0) == (50, 100)          # sin empates: casi igual que antes (49,5 → 50)
    assert V._pct(h[:59], 0.0) == (None, 59)                    # historia corta


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
    # parámetros sin redondear: faltan, o no redondean a los publicados
    with pytest.raises(V.ParametrosIncompletos, match="sin redondear"):
        V.parametros(sin_redondeo=tmp_path / "no_existe.json")
    r = json.loads(V.REFERENCIAS.read_text())
    r["final_sin_redondeo"]["cal"]["T2"][1] += 1e-3
    p.write_text(json.dumps(r))
    with pytest.raises(V.ParametrosIncompletos, match="no redondean"):
        V.parametros(sin_redondeo=p)
    par = V.parametros()
    assert par["cal_T2"] != tuple(json.loads(V.CONGELADO.read_text())["final"]["cal"]["T2"])     # sin redondear


def test_referencias_incompletas(tmp_path):
    with pytest.raises(V.ParametrosIncompletos, match="sin referencias"):
        V.referencias_congeladas(tmp_path / "no_existe.json")
    r = json.loads(V.REFERENCIAS.read_text())
    del r["referencias"]["indicadores"]["C2"]["GBR"]
    r["referencias"]["centro_T2"] = r["referencias"]["centro_T2"][:5]
    p = tmp_path / "x.json"
    p.write_text(json.dumps(r))
    with pytest.raises(V.ParametrosIncompletos, match="distribución C2 GBR.*centro"):
        V.referencias_congeladas(p)


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
    for q in (50, 80, 95):      # parámetros sin redondear: reproduce los percentiles exactos (antes, error ≤ 5e-4)
        assert np.quantile(v, q / 100) == pytest.approx(par["pct_T2"][f"p{q}"], abs=1e-12)
        assert round(float(np.quantile(v, q / 100)), 4) == ref[f"p{q}"]


@pytest.mark.skipif(not db.WAREHOUSE.exists(), reason="sin warehouse real")
@pytest.mark.parametrize("fecha", ["2004-12-31", "2026-10-29"])
def test_referencias_congeladas_igual_a_recalculadas(fecha):
    """Las referencias ≤ 2004 congeladas (scripts/termometro_referencias.py, datos load_dev) = las que se recalculaban
    en cada ejecución con los datos en vivo, con corte 2004-12 y con corte de hoy (as of: los meses ≤ 2004 no cambian)."""
    from src.intl import termometro as T
    con = db.connect(read_only=True)
    try:
        pm, bis, pib, _ = V.cargar(con, fecha)
    finally:
        con.close()
    par = V.parametros()
    mens = T.mensuales(pm, bis, pib, V.NUCLEO, V.TODOS)
    rec = V.referencias(mens, T.traducir(mens, par["rectas"], V.TODOS), pib, par)
    cong = V.referencias_congeladas()
    assert rec["meses_centro"] == cong["meses_centro"] == 295
    assert np.allclose(rec["centro_T2"], cong["centro_T2"], rtol=0, atol=1e-12)
    for k, *_ in V.INDICADORES:
        for c in V.TODOS:
            a, b = rec["indicadores"][k][c], cong["indicadores"][k][c]
            assert len(a) == len(b) and np.allclose(a, b, rtol=0, atol=1e-12), (k, c)


# ---------------------------------------------------------------- empalme del tipo a 3 meses (GBR: OCDE → BoE)
def _m(desde, hasta, valores):
    idx = pd.date_range(desde, hasta, freq="MS")
    return pd.Series(np.broadcast_to(np.asarray(valores, float), len(idx)).copy(), index=idx)


def test_empalmar_sin_ajuste_si_la_diferencia_es_pequena():
    base, sust = _m("2023-01-01", "2026-02-01", 4.0), _m("2016-01-01", "2026-09-01", 3.98)
    s, e = V.empalmar(base, sust)
    assert e["desde"] == "2026-03-01" and e["solape_meses"] == 24 and e["solape"] == "2024-03/2026-02"
    assert e["dif_media_pp"] == pytest.approx(0.02) and e["ajuste_pp"] == 0.0
    assert s.index.max() == pd.Timestamp("2026-09-01") and (s.loc["2026-03-01":] == 3.98).all()
    assert (s.loc[:"2026-02-01"] == base).all()                                     # la parte OCDE no se toca


def test_empalmar_ajusta_con_la_media_de_los_ultimos_24_meses():
    base = _m("2020-01-01", "2026-02-01", 4.0)
    sust = _m("2016-01-01", "2026-09-01", 3.5)
    sust.loc[:"2024-02-01"] = 0.0                    # solape viejo muy distinto: no cuenta (solo los últimos 24)
    s, e = V.empalmar(base, sust)
    assert e["ajuste_pp"] == pytest.approx(0.5) and e["solape_meses"] == 24
    assert np.allclose(s.loc["2026-03-01":], 4.0)
    assert "nivel ajustado +0.50 pp" in V._texto_empalme("BoE OIS (SONIA) 3 m", e)


def test_empalmar_no_empalma_sin_cola_o_con_poco_solape():
    base = _m("2020-01-01", "2026-02-01", 4.0)
    assert V.empalmar(base, _m("2016-01-01", "2026-02-01", 3.9))[1] is None        # sin meses nuevos
    s, e = V.empalmar(base, _m("2025-06-01", "2026-09-01", 3.9))                   # 9 meses de solape < 12
    assert e is None and s.index.max() == pd.Timestamp("2026-02-01")
    assert V.empalmar(pd.Series(dtype=float), _m("2016-01-01", "2026-09-01", 3.9))[1] is None


def _con_boe(con, desplaza=0.0, choque_desde=None):
    """Añade boe_ois3m_m (= tipo a 3 meses sintético de GBR − 0,02 pp; `desplaza` lo mueve todo y `choque_desde` solo
    lo posterior a esa fecha)."""
    s = con.execute("select date, value from obs_latest where series_id = 'oecd_ir3m_gbr' order by date").df()
    fm = pd.date_range("2016-01-01", "2026-09-01", freq="MS")
    i = 3 + 2 * np.cos(np.arange(len(pd.date_range("1985-01-01", "2026-09-01", freq="MS"))) / 30 + V.TODOS.index("GBR"))
    v = i[-len(fm):] - 0.02 + desplaza
    if choque_desde:
        v = v + 5.0 * (fm > pd.Timestamp(choque_desde))
    df = _obs("boe_ois3m_m", fm, v)
    con.execute("insert into obs_latest select series_id, date, value from df")
    assert len(s)
    return con


def test_empalme_gbr_en_vivo():
    con = _con_boe(_warehouse(cortes={"oecd_ir3m_gbr": "2026-02-01"}))
    res = _termometro(con, "2026-10-29")
    g = res["paises"]["GBR"]
    assert g["indicadores"]["C1"]["valor"] is not None and "sin_dato" not in g["indicadores"]["C1"]
    assert g["avisos_datos"] == []                                       # desaparece "sin tipo a 3 meses"
    assert g["empalmes"] == ["tipo a 3 m: BoE OIS (SONIA) 3 m desde 2026-03 (empalme; sin ajuste de nivel: diferencia "
                             "media OCDE − BoE +0.02 pp en 24 meses de solape 2024-03/2026-02, < 0.05 pp)"]
    assert all(res["paises"][c]["empalmes"] == [] for c in V.TODOS if c != "GBR")
    # sin corte, la curva empalmada casi coincide con la de la serie OCDE completa (0,02 pp de diferencia)
    completo = _termometro(_warehouse(), "2026-10-29")["paises"]["GBR"]["indicadores"]["C1"]["valor"]
    assert g["indicadores"]["C1"]["valor"] == pytest.approx(completo, abs=0.03)
    md = V.markdown(res)
    assert "> - GBR: tipo a 3 m: BoE OIS (SONIA) 3 m desde 2026-03 (empalme;" in md and "Datos que faltan" not in md


def test_empalme_gbr_con_ajuste_y_sin_mirar_el_futuro():
    con = _con_boe(_warehouse(cortes={"oecd_ir3m_gbr": "2026-02-01"}), desplaza=-0.48)     # BoE 0,50 pp por debajo
    g = _termometro(con, "2026-10-29")["paises"]["GBR"]
    assert "nivel ajustado +0.50 pp (diferencia media OCDE − BoE de 24 meses de solape 2024-03/2026-02)" in g["empalmes"][0]
    completo = _termometro(_warehouse(), "2026-10-29")["paises"]["GBR"]["indicadores"]["C1"]["valor"]
    assert g["indicadores"]["C1"]["valor"] == pytest.approx(completo, abs=0.01)
    # con corte 2026-05-31: lo del BoE posterior al corte no cambia nada
    a = _termometro(_con_boe(_warehouse(cortes={"oecd_ir3m_gbr": "2026-02-01"})), "2026-05-31")
    b = _termometro(_con_boe(_warehouse(cortes={"oecd_ir3m_gbr": "2026-02-01"}), choque_desde="2026-05-01"), "2026-05-31")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a["paises"]["GBR"]["empalmes"][0].startswith("tipo a 3 m: BoE OIS (SONIA) 3 m desde 2026-03")


def test_empalme_no_actua_si_la_ocde_sigue_ni_en_desarrollo():
    con = _con_boe(_warehouse())                                 # OCDE hasta 2026-09 como el BoE: sin cola
    res = _termometro(con, "2026-10-29")
    assert res["paises"]["GBR"]["empalmes"] == []
    con = _con_boe(_warehouse(cortes={"oecd_ir3m_gbr": "2026-02-01"}))
    assert _termometro(con, "2026-01-31")["paises"]["GBR"]["empalmes"] == []    # as of: la OCDE aún tenía el dato
    assert not D.permitida("boe_ois3m_m")                        # desarrollo (load_dev) no puede leerla
    with pytest.raises(D.FactorCutoffError):
        D.load_dev(con, "boe_ois3m_m")
