"""Deriva de revisión (src/report/revisiones.py): el warehouse de hoy ≤ 2004 frente a la instantánea con la que se
congelaron las referencias de INT-8b y del termómetro. Umbrales por familia, aviso y fallo (revisiones.UMBRALES_FAMILIA,
UMBRAL_PERCENTIL; docs/int/OCDE_deriva_umbrales.md): AVISA siempre con las magnitudes y solo FALLA con «fallo»."""
import json
import warnings

import duckdb
import numpy as np
import pandas as pd
import pytest

from src.intl import data as D
from src.report import revisiones as RV
from src.warehouse import db


def _obs(sid, fechas, valores):
    return pd.DataFrame({"series_id": sid, "date": pd.to_datetime(fechas), "value": np.asarray(valores, float)})


def _con(df):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    con = duckdb.connect(":memory:")
    con.execute("create table obs_latest as select * from df")
    return con


def test_familias_y_metricas():
    f = {s: (RV.umbral_de(s).familia, RV.umbral_de(s).metrica) for s in (
        "oecd_irlt_bel", "bis_cbpol_be", "oecd_ir3m_ita", "oecd_unemp_ita", "oecd_ip_gbr", "oecd_retail_dnk",
        "oecd_cpi_gbr_idx", "oecd_cpicore_gbr_idx", "oecd_share_gbr", "oecd_cli_usa", "oecd_bci_deu", "oecd_gdpq_gbr",
        "bis_creditgap_be_ratio", "aqr_mkt_usa_m", "jst_usa_eq_dp", "USREC")}
    assert f["oecd_irlt_bel"] == f["bis_cbpol_be"] == f["oecd_ir3m_ita"] == ("tipos", "nivel")
    assert f["oecd_unemp_ita"] == ("paro", "nivel")
    assert f["oecd_ip_gbr"] == ("ip", "interanual") and f["oecd_retail_dnk"] == ("ventas", "interanual")
    assert f["oecd_cpi_gbr_idx"] == f["oecd_cpicore_gbr_idx"] == ("ipc", "interanual")
    assert f["oecd_share_gbr"] == ("bolsa", "interanual")
    assert f["oecd_cli_usa"] == ("cli", "nivel") and f["oecd_bci_deu"] == ("confianza", "nivel")   # se usan en nivel
    assert f["oecd_gdpq_gbr"] == ("pib_trimestral", "interanual_t")
    assert f["bis_creditgap_be_ratio"][0] == "credito_pib" and f["USREC"][0] == "usrec"
    assert RV.umbral_de("jst_usa_cpi") is None                                           # sin umbral: solo informa
    assert all(u.aviso <= u.fallo for u in RV.UMBRALES_FAMILIA)


def test_cubre_toda_la_instantanea():
    """Cada serie de la cobertura de la instantánea tiene familia con umbral (no hay series que solo se informen)."""
    cob = json.loads(D.INSTANTANEA.read_text())["cobertura"]
    assert [s for s in cob if RV.umbral_de(s) is None] == []


def test_estados_sinteticos():
    fm = pd.date_range("1990-01-01", "2004-12-01", freq="MS")
    t = np.arange(len(fm))
    fq = pd.date_range("1990-01-01", "2004-10-01", freq="QS")
    ind = 100 * np.exp(0.002 * t)
    inst = pd.concat([
        _obs("oecd_irlt_bel", fm, 5 + 0 * t),            # retoque 0,02 pp → ok
        _obs("oecd_ir3m_bel", fm, 5 + 0 * t),            # 0,10 pp → aviso
        _obs("oecd_ir3m_ita", fm, 5 + 0 * t),            # 0,30 pp → fallo
        _obs("oecd_unemp_ita", fm, 8 + 0 * t),           # 0,1 pp = un dígito → ok
        _obs("oecd_unemp_irl", fm, 8 + 0 * t),           # pierde fechas → fallo (rotura)
        _obs("oecd_ip_gbr", fm, ind),                    # +0,76 % desde 2003 → aviso
        _obs("oecd_ip_esp", fm, ind),                    # +2 % desde 2003 → fallo
        _obs("oecd_cpi_gbr_idx", fm, ind),               # cambio de base puro ×1,05 → aviso (interanual intacta)
        _obs("oecd_bci_deu", fm, 100 + np.sin(t / 7)),   # cambio de base +0,5 puntos → fallo (se usa en nivel)
        _obs("oecd_gdpq_gbr", fq, 1000 * np.exp(0.006 * np.arange(len(fq)))),
        _obs("USREC", fm, 0 * t),
    ], ignore_index=True)
    hoy = inst.copy()
    s, d = hoy.series_id, hoy.date

    def mod(sid, cond, f):
        m = (s == sid) & cond
        hoy.loc[m, "value"] = f(hoy.loc[m, "value"])
    mod("oecd_irlt_bel", d == "2000-01-01", lambda v: v + 0.02)
    mod("oecd_ir3m_bel", d == "2000-01-01", lambda v: v + 0.10)
    mod("oecd_ir3m_ita", d == "2000-01-01", lambda v: v + 0.30)
    mod("oecd_unemp_ita", d == "2001-01-01", lambda v: v + 0.1)
    mod("oecd_ip_gbr", d >= "2003-01-01", lambda v: v * np.exp(0.0076))
    mod("oecd_ip_esp", d >= "2003-01-01", lambda v: v * 1.02)
    mod("oecd_cpi_gbr_idx", d == d, lambda v: v * 1.05)
    mod("oecd_bci_deu", d == d, lambda v: v + 0.5)
    mod("oecd_gdpq_gbr", d == "2002-04-01", lambda v: v * 1.003)   # +0,3 pp interanual → aviso
    hoy = hoy[~((s == "oecd_unemp_irl") & (d < "1991-01-01"))]
    r = RV.deriva_datos(_con(hoy), inst).set_index("series_id")
    e = r.estado.to_dict()
    assert e == {"oecd_irlt_bel": "ok", "oecd_ir3m_bel": "aviso", "oecd_ir3m_ita": "fallo", "oecd_unemp_ita": "ok",
                 "oecd_unemp_irl": "fallo", "oecd_ip_gbr": "aviso", "oecd_ip_esp": "fallo",
                 "oecd_cpi_gbr_idx": "aviso", "oecd_bci_deu": "fallo", "oecd_gdpq_gbr": "aviso", "USREC": "ok"}
    assert r.loc["oecd_ip_gbr", "dif_max"] == pytest.approx(0.76) and r.loc["oecd_ip_gbr", "cambiados"] == 12
    assert r.loc["oecd_cpi_gbr_idx", "dif_max"] == pytest.approx(0, abs=1e-9)
    assert r.loc["oecd_cpi_gbr_idx", "cambio_base_pct"] == pytest.approx(100 * np.log(1.05), abs=1e-3)
    assert "rotura" in r.loc["oecd_unemp_irl", "motivo"] and r.loc["oecd_unemp_irl", "faltan_hoy"] == 12
    assert r.loc["oecd_gdpq_gbr", "cambiados"] == 2                  # el trimestre y el de un año después
    assert r.grande.equals(r.estado == "fallo")
    fam = RV.resumen_familias(r.reset_index()).set_index("familia")
    assert fam.loc["tipos", "n_aviso"] == 1 and fam.loc["tipos", "n_fallo"] == 1


def test_usrec_cualquier_cambio_falla():
    fm = pd.date_range("2000-01-01", "2002-12-01", freq="MS")
    inst = _obs("USREC", fm, np.zeros(len(fm)))
    hoy = inst.copy()
    hoy.loc[hoy.date == "2001-04-01", "value"] = 1
    assert RV.deriva_datos(_con(hoy), inst).estado.iloc[0] == "fallo"


@pytest.mark.parametrize("dmax,nulos,esperado", [(0, 0, "ok"), (1, 0, "aviso"), (2, 0, "aviso"), (3, 0, "fallo"),
                                                 (0, 1, "fallo")])
def test_estado_percentiles(dmax, nulos, esperado):
    assert RV.estado_percentiles({"dif_max": dmax, "nulos_distintos": nulos}) == esperado


@pytest.mark.skipif(not db.WAREHOUSE.exists() or not D.instantanea_disponible(),
                    reason="sin warehouse real o sin la instantánea ≤ 2004")
def test_deriva_de_revision_del_warehouse():
    """Aviso con las magnitudes de la revisión en origen (siempre) y fallo solo con estado «fallo» (umbrales por
    familia + percentiles). Medido el 5-nov: 12 series revisadas, 1 en aviso (IP GBR 0,76 pp interanual), 0 en fallo;
    0 de 217 percentiles cambiarían."""
    con = db.connect(read_only=True)
    try:
        inf = RV.informe(con, pd.Timestamp.today().normalize())
    finally:
        con.close()
    warnings.warn(RV.texto(inf), UserWarning, stacklevel=1)
    assert inf["estado"] != "fallo", RV.texto(inf)


@pytest.mark.skipif(not D.instantanea_disponible(), reason="sin la instantánea ≤ 2004")
def test_instantanea_inmutable_y_cubierta():
    """sha256 del manifiesto, nada posterior a 2004, solo lectura, y `load_dev` falla con una serie no cubierta."""
    man = json.loads(D.INSTANTANEA.read_text())
    p = D.ruta_instantanea()
    if p.exists():
        assert D.sha256(p) == man["sha256"]
        assert not p.stat().st_mode & 0o222                                                  # solo lectura
    con = D.connect(fuente="instantanea")
    try:
        assert D.load_dev(con, "oecd_irlt_bel").index.max() <= D.DEV_END
        with pytest.raises(D.FactorCutoffError, match="no está en la instantánea"):
            D.load_dev(con, "oecd_cli_aut")
    finally:
        con.close()
    assert not D.load_dev_curado("oecd_gdpq_gbr", fuente="instantanea").empty
