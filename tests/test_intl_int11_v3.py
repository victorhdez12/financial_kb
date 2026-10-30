"""Tests SINTÉTICOS de INT-11 v3 (docs/int/INT11_v3_diseno.md). Ningún dato real."""
from __future__ import annotations

import numpy as np
import pytest

from src.intl import escenarios as E
from tests.sint_int11 import panel


@pytest.fixture(scope="module")
def filas():
    return E.preparar_filas(panel(), covariables=("termo",))


# ------------------------------------------------------------------ v1 y v2 intactos
def test_config_v2_reproduce_v2_bit_a_bit(filas):
    """Valores calculados con src/intl/escenarios.py de main (v2 congelado, 3995fd4) con la misma semilla."""
    g = E.Generador(E.Config.v2()).ajustar(filas)
    e = g.simular("P01", "sobrecalentamiento", horizonte=4, n_lotes=10, por_lote=50, semilla=3)
    assert float(np.nansum(e.rent)) == 66.33919133266853
    assert float(np.nansum(e.inflacion)) == 114.18559230076
    assert int(e.regimen.sum()) == 1727
    assert float(np.nansum(g.simular("ZZZ", 2, horizonte=2, n_lotes=10, por_lote=50, semilla=5).rent)) == \
        -95.36156658718585
    gt = E.Generador(E.Config.v2(modo="t")).ajustar(filas)
    assert float(np.nansum(gt.simular("P01", 2, horizonte=3, n_lotes=10, por_lote=50, semilla=4).rent)) == \
        -122.43641674248751
    assert g.escala_resumen["curtosis"] == [0.32, -0.23, 0.0, 0.1, 0.12]


def _panel_hetero(factor=2.5, semilla=0, n_paises=8):
    """El país P00 con dispersión propia de la bolsa `factor` veces mayor (choques normales: curtosis verdadera 0)."""
    df = panel(n_paises=n_paises, semilla=semilla)
    m = df["pais"] == "P00"
    media_año = df.groupby("año")["bolsa"].transform("mean")
    df.loc[m, "bolsa"] = media_año[m] + factor * (df.loc[m, "bolsa"] - media_año[m])
    return df


def test_config_v3_valores():
    c = E.Config.v3()
    assert c.es_v2 and c.escala_pais and c.curtosis_escala == "pais" and c.k_mezcla == 0.0
    assert c.c_suavizado == E.C_SUAVIZADO_V3 == 5.25
    assert c.semivida_epoca == E.SEMIVIDA_V3 and c.sigma_infl == E.SIGMA_INFL_V3 and c.sigma_brecha == E.SIGMA_BRECHA_V3
    assert c.eventos == () and not c.evento_condiciona
    for campo in ("curtosis_escala", "semivida_epoca", "sigma_infl", "sigma_brecha", "eventos"):
        assert getattr(E.Config(), campo) == getattr(E.Config.v2(), campo)          # v1/v2 sin piezas v3


# ------------------------------------------------------------------ curtosis por país
def test_curtosis_por_pais_no_se_infla_con_la_heterogeneidad():
    f = E.preparar_filas(_panel_hetero(2.5))
    g2 = E.Generador(E.Config.v2()).ajustar(f)
    g3 = E.Generador(E.Config.v3()).ajustar(f)
    k2 = g2.escala_resumen["curtosis"][0]
    k3 = g3.escala_resumen["curtosis"][0]
    assert k2 > 3.0 and abs(k3) < 0.8                     # agrupada inflada (3,8); estandarizada por país ≈ 0,5
    assert all(v[0] < 2.0 < k2 for v in g3.escala_resumen["curtosis_pais"].values())     # ruido muestral ≈ ±0,5
    bruto = 2.5 / np.sqrt((2.5 ** 2 + 7) / 8)             # factor verdadero de P00 relativo al rms del panel
    f2, f3 = g2.escala_resumen["factor_pais"]["P00"][0], g3.escala_resumen["factor_pais"]["P00"][0]
    assert abs(np.log(f3 / bruto)) < abs(np.log(f2 / bruto))                    # menos encogimiento de más
    assert g3.escala_resumen["B"]["P00"][0] > 0.5


def test_curtosis_por_pais_encoge_hacia_el_panel():
    f = E.preparar_filas(_panel_hetero(2.5))
    g = E.Generador(E.Config.v3(n0_curtosis=1e9)).ajustar(f)
    ks = [v[0] for v in g.escala_resumen["curtosis_pais"].values()]
    assert np.allclose(ks, g.escala_resumen["curtosis"][0], atol=1e-6)          # n0 enorme → todos = panel
    with pytest.raises(ValueError):
        E.Generador(E.Config.v3(curtosis_escala="otra")).ajustar(f)


# ------------------------------------------------------------------ pertenencia suave
def test_pesos_estado():
    w = E.pesos_estado(0.031, 0.02, 0.0, 0.0)
    assert np.array_equal(w, np.eye(4)[1])
    for infl, br in ((0.01, 0.05), (0.06, 0.05), (0.06, -0.05), (0.01, -0.05)):
        assert np.argmax(E.pesos_estado(infl, br, 0.0, 0.0)) == E.codigo_regimen([infl], [br])[0]
    w = E.pesos_estado(0.03, 0.0, 0.005, 0.01)
    assert np.allclose(w, 0.25) and w.sum() == pytest.approx(1)
    w = E.pesos_estado(0.0325, 0.5, 0.005, 0.01)                          # +0,25 pp: ≈ 69 % alta, brecha lejos
    assert w[1] == pytest.approx(0.6915, abs=1e-3) and w[2] + w[3] < 1e-12
    with pytest.raises(ValueError):
        E.pesos_estado(np.nan, 0.0, 0.005, 0.01)


def test_simular_con_pesos_puros_es_identico_al_duro(filas):
    g = E.Generador(E.Config.v3()).ajustar(filas)
    a = g.simular("P01", 1, horizonte=2, n_lotes=5, por_lote=40, semilla=9)
    b = g.simular("P01", np.eye(4)[1], horizonte=2, n_lotes=5, por_lote=40, semilla=9)
    assert np.array_equal(np.nan_to_num(a.rent), np.nan_to_num(b.rent)) and np.array_equal(a.regimen, b.regimen)
    assert (b.inicio == 1).all() and a.inicio is None


def test_simular_suave_mezcla_los_estados(filas):
    g = E.Generador(E.Config.v3()).ajustar(filas)
    br = 0.05                                                            # brecha holgada: solo el eje de inflación
    e = g.simular_suave("P01", 0.03, br, horizonte=1, n_lotes=20, por_lote=50, semilla=2)
    assert np.bincount(e.inicio, minlength=4).tolist() == [500, 500, 0, 0]
    p_suave = e.prob_inflacion(0.05)["p"]
    p0 = g.simular("P01", 0, horizonte=1, n_lotes=20, por_lote=50, semilla=2).prob_inflacion(0.05)["p"]
    p1 = g.simular("P01", 1, horizonte=1, n_lotes=20, por_lote=50, semilla=2).prob_inflacion(0.05)["p"]
    assert min(p0, p1) - 0.03 < p_suave < max(p0, p1) + 0.03 and p1 > p0
    assert e.meta["estado_observado"]["sigma_infl"] == E.SIGMA_INFL_V3
    assert "regimen_inicial" in e.a_tabla()
    lejos = g.simular_suave("P01", 0.08, br, horizonte=1, n_lotes=4, por_lote=50, semilla=2)
    assert (lejos.inicio == 1).all()                                     # 5 pp por encima: pertenencia ≈ 1


def test_preparar_filas_estado_previo(filas):
    f = E.preparar_filas(panel(), estado_previo=True)
    assert {"infl_prev", "brecha_prev"} <= set(f.columns)
    d = E.estados_operables(panel()).set_index(["pais", "año"])
    r = f.iloc[10]
    assert r["infl_prev"] == pytest.approx(d.loc[(r["pais"], r["año"] - 1), "inflacion"])
    assert E.codigo_regimen([r["infl_prev"]], [r["brecha_prev"]])[0] == r["s_prev"]
    assert "infl_prev" not in filas                                      # opcional: v1/v2 sin cambios


# ------------------------------------------------------------------ época (no estacionariedad)
def test_semivida_pesa_mas_lo_reciente_y_ensancha_si_lo_reciente_es_mas_volatil():
    df = panel(n_paises=6, semilla=3)
    m = df["año"] >= 1950
    df.loc[m, "bolsa"] = 0.06 + 2.0 * (df.loc[m, "bolsa"] - 0.06)        # bolsa reciente el doble de dispersa
    f = E.preparar_filas(df)
    g0 = E.Generador(E.Config.v3(semivida_epoca=0.0)).ajustar(f)
    g1 = E.Generador(E.Config.v3()).ajustar(f)
    assert g0.peso_epoca is None and g1.peso_epoca.max() == 1.0
    assert g1.peso_epoca[g1.anio == g1.anio.max() - 50].min() == pytest.approx(0.5)
    sd0, n0 = g0.sd_celda[(0, 0)]
    sd1, n1 = g1.sd_celda[(0, 0)]
    assert n1[0] < n0[0] and sd1[0] > sd0[0]                             # n de Kish menor, dt ponderada mayor

    def ancho(g):
        x = g.simular("P01", 0, horizonte=1, n_lotes=40, por_lote=100, semilla=1).rent[:, 0, 0]
        return np.diff(np.nanpercentile(x, [5, 95]))[0]
    assert ancho(g1) > 1.1 * ancho(g0)


def test_semivida_con_año_de_referencia_fijo():
    f = E.preparar_filas(panel(n_paises=4))
    g = E.Generador(E.Config.v3(anio_ref_epoca=1950)).ajustar(f)
    assert g.peso_epoca[g.anio == 1950].max() == pytest.approx(1.0) and g.peso_epoca.max() > 1.0


# ------------------------------------------------------------------ eventos como estados opcionales
def _panel_eventos(semilla=0):
    df = panel(n_paises=6, semilla=semilla)
    rng = np.random.default_rng(semilla + 50)
    años = np.sort(df["año"].unique())
    glob = dict(zip(años, rng.random(len(años)) < 0.15))
    df["ev_petroleo"] = df["año"].map(glob).astype(float)
    df["ev_crisis"] = (rng.random(len(df)) < 0.08).astype(float)
    df.loc[df["ev_crisis"] == 1, "bolsa"] -= 0.30                         # efecto plantado SOLO para el test
    return df, glob


def test_eventos_recuentos_global_y_por_pais():
    df, glob = _panel_eventos()
    f = E.preparar_filas(df, eventos=("petroleo", "crisis"))
    g = E.Generador(E.Config.v3(eventos=("petroleo", "crisis"))).ajustar(f)
    rp, rc = g.recuento_evento["petroleo"], g.recuento_evento["crisis"]
    assert rp["tipo"].startswith("global") and rp["n"] == f["año"].nunique()
    assert rp["eventos"] == sum(bool(glob[a]) for a in f["año"].unique())
    assert rc["tipo"] == "país-año" and rc["n"] == len(f) and rc["eventos"] == int(f["ev_crisis"].sum())
    g2 = E.Generador(E.Config.v3(eventos=("petroleo",), recuentos_evento={"petroleo": (12, 100)})).ajustar(f)
    assert g2.recuento_evento["petroleo"]["beta"] == (12.5, 88.5)
    with pytest.raises(ValueError):
        E.Generador(E.Config.v3(eventos=("dolar",))).ajustar(f)
    with pytest.raises(ValueError):
        E.Generador(E.Config.v3(modo="t", eventos=("crisis",), evento_condiciona=True)).ajustar(f)


def test_eventos_frecuencia_simulada_y_salidas():
    df, _ = _panel_eventos()
    f = E.preparar_filas(df, eventos=("petroleo", "crisis"))
    g = E.Generador(E.Config.v3(eventos=("petroleo", "crisis"))).ajustar(f)
    e = g.simular("P01", 0, horizonte=5, n_lotes=40, por_lote=100, semilla=4)
    for k in ("petroleo", "crisis"):
        a, b = g.recuento_evento[k]["beta"]
        assert e.eventos[k].mean() == pytest.approx(a / (a + b), abs=0.02)
    p5 = e.prob_evento("petroleo", h=5)["p"]
    assert p5 == pytest.approx(np.mean(e.eventos["petroleo"].any(1)))
    t = e.a_tabla()
    assert {"ev_petroleo", "ev_crisis"} <= set(t.columns) and len(t) == 4000 * 5
    assert "eventos" in e.meta and "SIN efecto" in e.meta["eventos"]["aviso"]


def test_eventos_sin_condicionar_no_tocan_las_rentabilidades():
    df, _ = _panel_eventos()
    f = E.preparar_filas(df, eventos=("crisis",))
    g = E.Generador(E.Config.v3(eventos=("crisis",))).ajustar(f)
    e = g.simular("P01", 0, horizonte=3, n_lotes=40, por_lote=100, semilla=6)
    x, ev = e.rent[:, :, 0].ravel(), e.eventos["crisis"].ravel()
    assert abs(np.nanmean(x[ev]) - np.nanmean(x[~ev])) < 0.04


def test_eventos_condicionados_sortean_filas_con_el_mismo_evento():
    df, _ = _panel_eventos()
    f = E.preparar_filas(df, eventos=("crisis",))
    g = E.Generador(E.Config.v3(eventos=("crisis",), evento_condiciona=True)).ajustar(f)
    e = g.simular("P01", 0, horizonte=3, n_lotes=40, por_lote=100, semilla=6)
    x, ev = e.rent[:, :, 0].ravel(), e.eventos["crisis"].ravel()
    assert np.nanmean(x[ev]) - np.nanmean(x[~ev]) < -0.20                # el efecto plantado (−30 pp) aparece
    assert ev.mean() == pytest.approx(f["ev_crisis"].mean(), abs=0.02)


# ------------------------------------------------------------------ piezas sintéticas (src/intl/int11v3)
def test_cobertura_iid_monotona_y_cerca_de_la_teoria():
    from src.intl import int11v3 as V
    c = V.cobertura_iid(20, [0.0, 5.25, 10.0], R=1500, semilla=1)
    assert c[0] == pytest.approx(19 / 21 * 0.95 - 0.01, abs=0.03)        # ≈ estadísticos de orden (0,85)
    assert c[0] < c[1] < c[2]


def test_brecha_y_epoca_sinteticas():
    from src.intl import int11v3 as V
    rng = np.random.default_rng(0)
    zg = rng.standard_normal((5, 400))
    b = V.brecha_desde_latente(zg, 0.06, 0.04)
    assert np.array_equal(b < 0, zg < -1.5547735945968535) and np.std(b) == pytest.approx(0.04, rel=0.05)
    reg = rng.integers(0, 4, (5, 400))
    Y = rng.standard_normal((5, 400, 5))
    ef = np.zeros((5, 4))
    Z = V.escalar_epoca(Y, reg, ef, np.zeros(5), 200, 2.0)
    assert np.allclose(Z[:, :200], Y[:, :200]) and np.allclose(Z[:, 200:], 2 * Y[:, 200:])


def test_evaluar_suave_con_sigma_cero_es_el_duro():
    from src.intl import int11v3 as V
    f = E.preparar_filas(panel(n_paises=4, a0=1900), estado_previo=True)
    cfg = E.Config.v3()
    duro = V.evaluar_suave(f, "loco", cfg, 4, 50, 1, sigmas=(0.0, 0.0), k_anchura=(1.0, 0.8))
    suave = V.evaluar_suave(f, "loco", cfg, 4, 50, 1, sigmas=(0.005, 0.0), k_anchura=(1.0, 0.8))
    for ev in (duro, suave):
        st = V.estadisticos(ev)
        assert 0.6 < st["S5"] <= 1 and st["S5_k"][1] <= st["S5_k"][0] + 1e-12
        assert np.isfinite(st["infl5"]["brier"])
    lejos = np.abs(duro["infl_prev"] - 0.03) > 0.03
    assert np.allclose(duro["p_infl_m1"][lejos], suave["p_infl_m1"][lejos], atol=0.02)
    assert not np.allclose(duro["p_infl_m1"], suave["p_infl_m1"])


# ------------------------------------------------------------------ registro en vivo (arreglos de la validación v2)
def test_registro_rechaza_fechas_atrasadas_y_futuras():
    from src.report import registro_vivo as RV
    RV.comprobar_fecha("2026-10-20", hoy="2026-10-22")
    with pytest.raises(SystemExit):
        RV.comprobar_fecha("2026-06-20", hoy="2026-10-30")                       # atrasada: fuga
    RV.comprobar_fecha("2026-06-20", hoy="2026-10-30", vintage=True)             # permitida solo con vintages
    with pytest.raises(SystemExit):
        RV.comprobar_fecha("2026-11-20", hoy="2026-10-30")


def test_registro_tolera_solo_cambios_en_su_carpeta():
    from src.report import registro_vivo as RV
    carpeta = RV.REPO / "research/int/int11_vivo"
    p = RV.procedencia_registro(carpeta, sucios=["research/int/int11_vivo/2026-10.json",
                                                 "research/int/int11_vivo/indice.csv"])
    assert not p["arbol_limpio"] and len(p["pendientes_en_registro"]) == 2
    with pytest.raises(SystemExit):
        RV.procedencia_registro(carpeta, sucios=["research/int/int11_v2_hoy.json"])
    with pytest.raises(SystemExit):
        RV.procedencia_registro(carpeta, sucios=["research/int/int11_vivo_otro/x.json"])
    assert RV.procedencia_registro(carpeta, sucios=[])["arbol_limpio"]


def test_registro_huella_de_entradas_y_segunda_emision(tmp_path):
    import hashlib
    import json
    import pandas as pd
    from src.report import registro_vivo as RV
    s = pd.Series([100.0, 101.0], index=pd.to_datetime(["2026-08-01", "2026-09-01"]))
    h1 = RV.huella_entradas({"USA_ipc": s, "ESP_ipc": s * 2})
    h2 = RV.huella_entradas({"ESP_ipc": s * 2, "USA_ipc": s})
    assert h1 == h2 and h1["series"]["USA_ipc"]["2026-09-01"] == 101.0
    assert RV.huella_entradas({"USA_ipc": s + 1e-6})["sha256"] != h1["sha256"]
    base = {"procedencia": {"commit": "abc"}, "ventana_objetivo": {"desde": "2026-11-01", "hasta": "2027-10-31"},
            "entradas": h1}
    r1 = RV.registrar({**base, "emision": "2026-10-20"}, tmp_path)
    r2 = RV.registrar({**base, "emision": "2026-11-20"}, tmp_path)                # el mes siguiente no aborta
    lin = (tmp_path / "indice.csv").read_text().splitlines()
    assert len(lin) == 3 and lin[0].endswith("sha256_entradas") and lin[2].split(",")[-1] == h1["sha256"]
    assert lin[2].split(",")[2] == hashlib.sha256(r2.read_text().encode()).hexdigest()
    assert json.loads(r1.read_text())["entradas"]["sha256"] == h1["sha256"]
    with pytest.raises(SystemExit):
        RV.registrar({**base, "emision": "2026-11-21"}, tmp_path)


def test_serie_asof_usa_la_vintage_vigente():
    import duckdb
    from src.report import escenarios_vivo as V
    con = duckdb.connect()
    con.execute("create table vintages (date date, value double, series_id varchar, realtime_start date, "
                "realtime_end date)")
    con.execute("insert into vintages values ('2025-01-01', 1.0, 'X', '2025-04-30', '2025-05-28'), "
                "('2025-01-01', 2.0, 'X', '2025-05-29', null), ('2025-04-01', 3.0, 'X', '2025-07-30', null)")
    a = V.serie_asof(con, "X", "2025-05-15")
    assert a.tolist() == [1.0]
    b = V.serie_asof(con, "X", "2025-08-01")
    assert b.tolist() == [2.0, 3.0]


def test_hoy_v2_registro_no_reescribe_la_salida_hoy(monkeypatch, tmp_path):
    from scripts import int11_v2_hoy as H
    llamadas = {}
    monkeypatch.setattr(H, "emitir", lambda fecha, registro, vintage: llamadas.update(r=registro) or {"x": 1})
    monkeypatch.setattr(H, "markdown", lambda o: "md")
    monkeypatch.setattr(H, "registrar", lambda o: tmp_path / "r.json")
    monkeypatch.setattr(H, "SALIDA", tmp_path / "hoy.json")
    monkeypatch.setattr("sys.argv", ["x", "2026-10-30", "--registro"])
    H.main()
    assert llamadas["r"] and not (tmp_path / "hoy.json").exists()


def test_cuantiles_filas_de_la_mezcla():
    from src.intl import int11v3 as V
    rng = np.random.default_rng(0)
    a, b = rng.normal(0, 1, 4000), rng.normal(5, 1, 4000)
    W = np.array([[1.0, 0, 0, 0], [0.5, 0.5, 0, 0], [0, 1.0, 0, 0]])
    q = V._cuantiles_filas([a, b, np.zeros(0), np.zeros(0)], W, (0.05, 0.5, 0.95))
    assert q[1, 0] == pytest.approx(np.quantile(a, 0.5), abs=0.01) and q[1, 2] == pytest.approx(5, abs=0.06)
    assert q[0, 1] == pytest.approx(np.quantile(a, 0.10), abs=0.03)          # p5 de la mezcla = p10 de a
    assert q[2, 1] == pytest.approx(np.quantile(b, 0.90), abs=0.03)
