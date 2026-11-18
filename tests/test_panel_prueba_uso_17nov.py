"""Arreglos de la prueba de uso del panel (docs/validation/2026-11-17_panel_prueba_uso.md, «Arreglos (17-nov)»)."""
from __future__ import annotations

from datetime import date

import duckdb
import pandas as pd

from src.ingest import cftc_cot as CF
from src.report import _ui as UI
from src.report import panel_hoy as PH
from src.report import panel_paises as PP
from src.report import pulso_paises as PUL
from src.verif import panel_verif as PV


def _con(series: dict[str, pd.Series]):
    con = duckdb.connect()
    filas = [(d.date(), float(v), sid) for sid, s in series.items() for d, v in s.items()]
    con.execute("create table obs_latest(date date, value double, series_id varchar)")
    con.executemany("insert into obs_latest values (?, ?, ?)", filas)
    return con


# M1: la inflación de EE. UU. de «Países» es la misma (BLS) que la de «Hoy» cuando es más reciente que la de la OCDE
def test_ipc_usa_mismo_dato_que_hoy():
    idx = pd.date_range("2024-01-01", "2026-10-01", freq="MS")
    cpi = pd.Series([300 * 1.003 ** i for i in range(len(idx))], index=idx).drop(pd.Timestamp("2025-10-01"))
    con = _con({"CPIAUCSL": cpi})
    v, f = PUL.ipc_bls_usa(con, pd.Timestamp("2026-11-17"))
    hoy = PH.yoy(cpi)
    assert f == pd.Timestamp("2026-10-01") and abs(v - float(hoy.iloc[-1])) < 1e-12


# M2: aviso de mercados atrasados con el dato de SPY de «Mis activos»
def test_nota_mercados_atrasados():
    assert PH.ultimo_habil(date(2026, 11, 17)) == date(2026, 11, 16)
    assert PH.ultimo_habil(date(2026, 11, 16)) == date(2026, 11, 13)   # lunes → viernes
    fichas = [{"clave": "vix", "fecha": "2026-11-13"}, {"clave": "ipc", "fecha": "2026-10-01"}]
    t = PH.nota_mercados(fichas, date(2026, 11, 17), (-5.02, "2026-11-16"))
    assert "2026-11-13" in t and "2026-11-16" in t and "−5,0 %" in t
    assert PH.nota_mercados([{"clave": "vix", "fecha": "2026-11-16"}], date(2026, 11, 17)) == ""


# M3 y B1: CSS/JS de móvil y de saltos a fichas
def test_css_movil_y_scroll_margin():
    assert "scroll-margin-top" in UI.CSS and "--navh" in UI.JS
    assert ".badge,.chip{white-space:normal" in UI.CSS
    assert "tw-auto" in UI.CSS and "tw-auto" in UI.JS


# M4: la caché del zip del año en curso de la CFTC es corta (la publicación se retrasa a un lunes por festivo)
def test_cftc_cache_corta_del_año_en_curso():
    assert CF.max_age_hours("fut_fin_txt_2026", 2026) <= 6
    assert CF.max_age_hours("fut_fin_txt_2025", 2026) > 24 * 300


# B7: una serie que sale por vintages ALFRED no se repite desde los eventos guardados
def test_novedades_sin_duplicar_serie_de_vintages():
    ult = pd.DataFrame({"series_id": ["PPIACO"], "d1": ["2026-10-01"], "v1": [293.9], "d2": ["2026-09-01"],
                        "v2": [294.5], "nombre": ["PPI"], "freq": ["M"]})
    est = {"series": {"PPIACO": ["2026-10-01", 293.9]},
           "eventos": [{"series_id": "PPIACO", "fecha": "2026-10-01", "detectado": "2026-11-14",
                        "via": "fecha de actualización de FRED"}]}
    ev, _ = PH.novedades_estado(ult, est, date(2026, 11, 17), excluir={"PPIACO"})
    assert ev == []


# B8: sin «−0,0» y separador de miles «.»
def test_formatos_sin_cero_negativo_y_miles():
    assert PH.fnum(-0.001, 2, True) == "+0,00" and PH.fnum(-0.001, 2) == "0,00"
    assert PH.fnum(5844.2, 0) == "5.844"
    assert "−" not in PP.n(-0.04, 1) and "−" not in PUL._fmt(-0.04, 1) and "−" not in PV._n(-0.001, 2)
    assert PP.n(-0.06, 1) == "−0,1 %"


# B4: «en recesión» (termómetro) sale en rojo en «Hoy», como en «Países»
def test_recesion_en_rojo_en_hoy():
    s = {"termometro": {"paises": {"IRL": {"estado": {"en_recesion": True}}}}}
    assert ("rojo", "Termómetro: en recesión según el fechado trimestral: Irlanda.") in PH.avisos_reporte(s)
    assert PP._banda_recesion(s, "IRL")[0] == "rojo"


# B2: filas estructurales ocultas y huecos de la fuente rotulados
def test_sd_estructurales_ocultos_y_rotulados():
    assert PP._sin_dato("NLD", ('<abbr>CLI</abbr> OCDE', '<span class="nd">s/d</span>', ""))[2].startswith("la OCDE no publica")
    assert PP._sin_dato("ESP", ("CLI OCDE", "1,0", "oct-2026"))[2] == "oct-2026"
    assert {"BEL", "FIN"} <= set(PUL.BCE)


def test_tipo_3m_gbr_empalme_y_jpn_mes_comun():
    meses = pd.date_range("2023-01-01", "2026-10-01", freq="MS")
    r10 = pd.Series(4.0, index=meses)
    ois = pd.Series(3.9, index=meses)
    gbr3 = pd.Series(3.9, index=meses[meses <= "2026-02-01"])
    con = _con({"oecd_ir3m_gbr": gbr3, "boe_ois3m_m": ois})
    s, fuente = PUL.tipo_3m(con, "GBR", gbr3, pd.Timestamp("2026-11-17"))
    assert s.index.max() == pd.Timestamp("2026-10-01") and "SONIA" in fuente
    s2, f2 = PUL.tipo_3m(con, "JPN", gbr3, pd.Timestamp("2026-11-17"))
    assert f2 is None and s2.equals(gbr3)
    assert r10.index.max() == pd.Timestamp("2026-10-01")
