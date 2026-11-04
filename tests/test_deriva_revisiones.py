"""Deriva de revisión (src/report/revisiones.py): el warehouse de hoy ≤ 2004 frente a la instantánea con la que se
congelaron las referencias de INT-8b y del termómetro. Informa de las magnitudes (aviso) y solo FALLA con diferencias
grandes (umbrales declarados en revisiones.UMBRALES; docs/int/INT8b_nowcast.md, «Revisiones de datos»)."""
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


def test_tipos_de_serie():
    assert RV.tipo_serie("oecd_irlt_bel") == "pp" and RV.tipo_serie("oecd_unemp_ita") == "pp"
    assert RV.tipo_serie("bis_cbpol_be") == "pp" and RV.tipo_serie("bis_creditgap_be_ratio") == "pp_pib"
    assert RV.tipo_serie("oecd_ip_gbr") == "pp_interanual" and RV.tipo_serie("oecd_cpi_gbr_idx") == "pp_interanual"
    assert RV.tipo_serie("oecd_gdpq_gbr") == "pp_interanual"
    assert RV.tipo_serie("jst_usa_eq_dp") is None and RV.tipo_serie("USREC") is None


def test_deriva_datos_umbral_sintetico():
    fm = pd.date_range("1990-01-01", "2004-12-01", freq="MS")
    t = np.arange(len(fm))
    inst = pd.concat([_obs("oecd_irlt_bel", fm, 5 + 0 * t), _obs("oecd_unemp_ita", fm, 8 + 0 * t),
                      _obs("oecd_ip_gbr", fm, 100 * np.exp(0.002 * t))], ignore_index=True)
    hoy = inst.copy()
    hoy.loc[(hoy.series_id == "oecd_irlt_bel") & (hoy.date == "2000-01-01"), "value"] += 0.02     # retoque: no grande
    hoy.loc[(hoy.series_id == "oecd_unemp_ita") & (hoy.date == "2001-01-01"), "value"] += 0.1     # = umbral: no grande
    hoy.loc[(hoy.series_id == "oecd_ip_gbr") & (hoy.date >= "2003-01-01"), "value"] *= 1.02      # +2 pp interanual
    hoy["date"] = hoy["date"].dt.date
    con = duckdb.connect(":memory:")
    con.execute("create table obs_latest as select * from hoy")
    d = RV.deriva_datos(con, inst).set_index("series_id")
    assert d.loc["oecd_irlt_bel", "dif_max"] == pytest.approx(0.02) and not d.loc["oecd_irlt_bel", "grande"]
    assert d.loc["oecd_unemp_ita", "cambiados"] == 1 and not d.loc["oecd_unemp_ita", "grande"]
    assert d.loc["oecd_ip_gbr", "grande"] and d.loc["oecd_ip_gbr", "dif_max"] == pytest.approx(100 * np.log(1.02))
    assert d.loc["oecd_ip_gbr", "cambiados"] == 12                  # solo el escalón de 2003 (luego la interanual vuelve)


@pytest.mark.skipif(not db.WAREHOUSE.exists() or not D.instantanea_disponible(),
                    reason="sin warehouse real o sin la instantánea ≤ 2004 (fuera del repo)")
def test_deriva_de_revision_del_warehouse():
    """Aviso con las magnitudes de la revisión en origen (siempre) y fallo solo si es grande: |Δ| > 0,10 pp en tipos o
    paro, > 1 pp en la interanual de un índice o en crédito/PIB, o algún percentil entero publicado hoy (nowcast o
    termómetro) que cambiaría si se recalcularan las referencias con los datos de hoy. Medido el 4-nov: 12 series
    revisadas (máx. IP GBR 0,76 pp interanual; BEL 10 años 0,02 pp; paro IRL/ITA 0,1 pp) y 0 percentiles cambiados."""
    con = db.connect(read_only=True)
    try:
        inf = RV.informe(con, pd.Timestamp.today().normalize())
    finally:
        con.close()
    warnings.warn(RV.texto(inf), UserWarning, stacklevel=1)
    assert not inf["grande"], RV.texto(inf)


@pytest.mark.skipif(not D.instantanea_disponible(), reason="sin la instantánea ≤ 2004 (fuera del repo)")
def test_instantanea_inmutable_y_cubierta():
    """sha256 del manifiesto, nada posterior a 2004, solo lectura, y `load_dev` falla con una serie no cubierta."""
    man = D.INSTANTANEA
    assert D.sha256(D.ruta_instantanea(man)) == __import__("json").loads(man.read_text())["sha256"]
    assert not D.ruta_instantanea(man).stat().st_mode & 0o222                                 # solo lectura
    con = D.connect(fuente="instantanea")
    try:
        assert D.load_dev(con, "oecd_irlt_bel").index.max() <= D.DEV_END
        with pytest.raises(D.FactorCutoffError, match="no está en la instantánea"):
            D.load_dev(con, "oecd_cli_aut")
    finally:
        con.close()
    assert not D.load_dev_curado("oecd_gdpq_gbr", fuente="instantanea").empty
