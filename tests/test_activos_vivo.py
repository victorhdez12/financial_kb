"""Realizado en vivo de bonos, letras, vivienda y oro y semáforo (src/report/activos_vivo.py;
docs/int/INT11_vivo_realizado_v0.md). Solo datos SINTÉTICOS, sin red y sin el warehouse real."""
import duckdb
import numpy as np
import pandas as pd
import pytest

from src.report import activos_vivo as V

MESES = pd.date_range("2000-01-01", "2030-12-01", freq="MS")
TRIM = pd.date_range("2000-01-01", "2030-10-01", freq="QS")


def test_bono_tipo_constante_rinde_el_cupon():
    y = pd.Series(4.0, index=MESES)
    r = V.rent_bono_ventana(y, "2027-01-01", "2027-12-31")
    assert r["completo"] and abs(r["nominal"] - ((1 + 0.04 / 12) ** 12 - 1)) < 1e-12


def test_bono_subida_de_tipos_pierde_por_duracion():
    y = pd.Series(4.0, index=MESES)
    y[y.index >= "2027-06-01"] = 5.0
    r = V.rent_bono_ventana(y, "2027-01-01", "2027-12-31")
    assert r["nominal"] < 0.04 - 0.06          # ≈ cupón − duración (≈ 8) × 1 pp


def test_bono_falta_un_mes_o_el_previo():
    y = pd.Series(4.0, index=MESES).drop(pd.Timestamp("2026-12-01"))
    r = V.rent_bono_ventana(y, "2027-01-01", "2027-12-31")
    assert not r["completo"] and r["faltan"] == ["2026-12"] and r["nominal"] is None


def test_letras_media_y_encadenada():
    y = pd.Series(np.where(MESES < pd.Timestamp("2027-07-01"), 2.0, 4.0), index=MESES)
    m = V.rent_letra_ventana(y, "2027-01-01", "2027-12-31", "media")
    assert abs(m["nominal"] - 0.03) < 1e-12
    e = V.rent_letra_ventana(y, "2027-01-01", "2027-12-31", "encadenada")       # usa dic-2026 … nov-2027
    assert abs(e["nominal"] - ((1 + 0.02 / 12) ** 7 * (1 + 0.04 / 12) ** 5 - 1)) < 1e-12
    with pytest.raises(ValueError):
        V.rent_letra_ventana(y, "2027-01-01", "2027-12-31", "otra")


def test_empalme_3m_gbr_sin_ajuste():
    base = pd.Series(3.0, index=MESES[MESES <= "2026-02-01"])
    sust = pd.Series(3.01, index=MESES[MESES >= "2016-01-01"])
    s, info = V.empalmar_3m(base, sust)
    assert info is not None and info["ajuste_pp"] == 0.0 and s.index.max() == MESES.max()
    assert V.empalmar_3m(base, None) == (base, None)


def test_vivienda_media_y_t4_con_alquiler():
    p = pd.Series(100 * 1.01 ** np.arange(len(TRIM)), index=TRIM)        # +1 % por trimestre
    r = pd.Series(100.0, index=TRIM)                                      # alquiler plano
    sp = V.rent_vivienda_ventana(p, "2027-01-01", "2027-12-31")
    assert sp["metodo"] == "solo_precio" and abs(sp["nominal"] - (1.01 ** 4 - 1)) < 1e-12
    q4 = V.rent_vivienda_ventana(p, "2027-01-01", "2027-12-31", modo="q4")
    assert abs(q4["plusvalia"] - (1.01 ** 4 - 1)) < 1e-12
    fijo = V.rent_vivienda_ventana(p, "2027-01-01", "2027-12-31", yd_ancla=0.04)
    assert fijo["metodo"] == "alquiler_fijo" and abs(fijo["alquiler"] - 0.04 * 1.01 ** 4) < 1e-12
    ind = V.rent_vivienda_ventana(p, "2027-01-01", "2027-12-31", yd_ancla=0.04, alquiler_q=r)
    # 23 años de precios +4 %/año con alquiler plano: el rent_yd cae en 1,01^(4·23)
    assert ind["metodo"] == "indice_alquiler" and abs(ind["rent_yd"] - 0.04 / 1.01 ** 92) < 1e-9
    assert abs(ind["nominal"] - (ind["plusvalia"] + ind["rent_yd"] * (1 + ind["plusvalia"]))) < 1e-12


def test_vivienda_falta_trimestre():
    p = pd.Series(100.0, index=TRIM).drop(pd.Timestamp("2027-10-01"))
    r = V.rent_vivienda_ventana(p, "2027-01-01", "2027-12-31")
    assert not r["completo"] and "2027-10" in r["faltan"]


def test_oro_local_con_fx_de_fin_de_mes():
    g = pd.Series(np.where(MESES < pd.Timestamp("2027-12-01"), 2000.0, 2200.0), index=MESES)
    x = pd.Series(np.where(MESES < pd.Timestamp("2027-12-01"), 0.90, 0.99), index=MESES)
    r = V.rent_oro_ventana(g, x, "2027-01-01", "2027-12-31")
    assert abs(r["nominal"] - (1.1 * 1.1 - 1)) < 1e-12
    assert abs(V.rent_oro_ventana(g, None, "2027-01-01", "2027-12-31")["nominal"] - 0.1) < 1e-12
    assert not V.rent_oro_ventana(g, x.drop(pd.Timestamp("2027-12-01")), "2027-01-01", "2027-12-31")["completo"]


def test_cabecera_real_y_sin_serie():
    ipc = pd.Series(100 * 1.002 ** np.arange(len(MESES)), index=MESES)
    y = pd.Series(3.0, index=MESES)
    r = V.realizado_activos_pais("2027-01-01", "2027-12-31", ipc, irlt=y, ir3m=y)
    infl = 1.002 ** 12 - 1
    assert abs(r["letras"]["real"] - (1.03 / (1 + infl) - 1)) < 1e-12
    assert r["vivienda"]["real"] is None and r["oro"]["faltan"] == ["sin serie"]


def test_lectura_con_warehouse_sintetico(monkeypatch):
    con = duckdb.connect(":memory:")
    con.execute("create table obs_latest (series_id varchar, date date, value double)")
    f = [("gold_wb_usd_m", d, 2000.0 * 1.01 ** i) for i, d in enumerate(MESES)]
    for c in ("usa", "gbr"):
        f += [(f"oecd_cpi_{c}_idx", d, 100 * 1.002 ** i) for i, d in enumerate(MESES)]
        f += [(f"oecd_irlt_{c}", d, 4.0) for d in MESES]
    f += [("oecd_ir3m_usa", d, 3.0) for d in MESES]
    f += [("oecd_ir3m_gbr", d, 3.0) for d in MESES if d <= pd.Timestamp("2026-02-01")]
    f += [("boe_ois3m_m", d, 3.0) for d in MESES if d >= pd.Timestamp("2016-01-01")]
    f += [(f"bis_spp_{i2}_n", d, 100.0 * 1.01 ** i) for i2 in ("us", "gb") for i, d in enumerate(TRIM)]
    con.executemany("insert into obs_latest values (?, ?, ?)", f)
    monkeypatch.setattr(V, "yd_ancla_jst", lambda con, pais, año=2004: 0.04)
    fx = {"DEXUSUK": pd.Series(1.25, index=pd.date_range("2000-01-03", "2030-12-31", freq="B"))}
    r = V.leer_realizado_activos(con, fx, "2027-01-01", "2027-12-31", paises=["USA", "GBR"])
    assert r["GBR"]["letras"]["completo"] and "letras_empalme" in r["GBR"]["notas"]
    assert r["USA"]["vivienda"]["metodo"] == "alquiler_fijo"           # sin RPI en el warehouse → respaldo declarado
    assert abs(r["USA"]["oro"]["nominal"] - (1.01 ** 12 - 1)) < 1e-9
    assert all(r[c][a]["real"] is not None for c in ("USA", "GBR") for a in V.ACTIVOS_NUEVOS)
    assert "oecd_rpi_usa_q" in V.series_leidas(["USA"])


def test_semaforo_y_banda_binomial():
    b = {"p2_5": 0.80, "p10": 0.85, "p90": 0.95, "p97_5": 0.97}
    assert V.semaforo(0.90, b) == "verde" and V.semaforo(0.82, b) == "ámbar" and V.semaforo(0.70, b) == "rojo"
    assert V.semaforo(None, b) == "sin datos"
    lo, p10, p90, hi = V.banda_binomial(140)
    assert lo < p10 < 0.9 < p90 < hi and V.banda_binomial(1e6)[0] > 0.899


def test_simulacion_calibrada_cubre_90_y_escala_baja_a_80():
    rng = np.random.default_rng(0)
    sc, sp, R = [0.1, 0.02], [0.1, 0.08], np.eye(2)
    u = V.umbral_marginal(sc, sp, R, 6.0, rng, n=100_000)
    d = V.simular_dentro(10, sc, sp, R, 6.0, 300, rng, umbral=u)
    assert abs(d.mean() - 0.90) < 0.01
    e = V.escala_para(0.80, sc, sp, R, 6.0, u, rng, n=100_000)
    assert abs(V.simular_dentro(10, sc, sp, R, 6.0, 300, rng, escala=e, umbral=u).mean() - 0.80) < 0.01
    # con choque común, la cobertura de un año varía más que una binomial de 14 filas (efecto de diseño > 1)
    años = d[:, :, :, 0].mean(axis=2).ravel()
    assert años.var() > 0.09 / 14 * 1.5
