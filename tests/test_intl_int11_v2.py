"""Tests SINTÉTICOS de INT-11 v2 (docs/int/INT11_v2_diseno.md). Ningún dato real."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.intl import escenarios as E
from src.intl import int11 as Q
from tests.sint_int11 import panel


@pytest.fixture(scope="module")
def filas():
    return E.preparar_filas(panel(), covariables=("termo",))


def _ancho(esc, j=0, h=0):
    x = esc.rent[:, h, j]
    q = np.nanpercentile(x, [5, 95])
    return q[1] - q[0]


def _panel_hetero(factor=2.5, semilla=0, n_paises=8):
    """Panel sintético en el que el país P00 tiene una dispersión propia `factor` veces mayor en la bolsa."""
    df = panel(n_paises=n_paises, semilla=semilla)
    rng = np.random.default_rng(semilla + 100)
    m = df["pais"] == "P00"
    media_año = df.groupby("año")["bolsa"].transform("mean")
    df.loc[m, "bolsa"] = media_año[m] + factor * (df.loc[m, "bolsa"] - media_año[m]) + 0.0 * rng.standard_normal(m.sum())
    return df


# ------------------------------------------------------------------ v1 intacto
def test_config_por_defecto_reproduce_v1_bit_a_bit(filas):
    """Valores calculados con src/intl/escenarios.py de main (v1, 2c0afce) con la misma semilla."""
    g = E.Generador(E.Config()).ajustar(filas)
    e = g.simular("P01", "sobrecalentamiento", horizonte=4, n_lotes=10, por_lote=50, semilla=3)
    assert float(np.nansum(e.rent)) == 38.93651313623553
    assert float(np.nansum(e.inflacion)) == 109.85046103444627
    assert int(e.regimen.sum()) == 1697
    gt = E.Generador(E.Config(modo="t")).ajustar(filas)
    assert float(np.nansum(gt.simular("P01", 2, horizonte=3, n_lotes=10, por_lote=50, semilla=4).rent)) == \
        -153.52264336836217
    assert not E.Config().es_v2 and E.Config.v2().es_v2


def test_config_v2_valores():
    c = E.Config.v2()
    assert c.escala_pais and c.k_mezcla == E.K_MEZCLA_V2 and c.c_suavizado == E.C_SUAVIZADO_V2
    assert c.rejilla_kappa == E.REJILLA_KAPPA_V2
    assert E.Config.v2(k_mezcla=0.0).k_mezcla == 0.0


# ------------------------------------------------------------------ κ
def test_rejilla_kappa_ampliada_y_aviso_de_borde(filas):
    g1 = E.Generador(E.Config()).ajustar(filas)
    g2 = E.Generador(E.Config.v2()).ajustar(filas)
    assert g1.kappa_en_borde and g1.kappa == pytest.approx(10 ** 3.5)          # panel homogéneo: v1 en el borde
    assert g2.kappa > g1.kappa                                                  # v2 puede ir más allá
    e = g2.simular("P01", 0, horizonte=1, n_lotes=5, por_lote=20, semilla=1)
    assert "kappa_en_borde" in e.meta


# ------------------------------------------------------------------ escala por país
def test_escala_pais_recupera_el_factor_y_ensancha_al_pais_volatil():
    f = E.preparar_filas(_panel_hetero(2.5))
    g = E.Generador(E.Config.v2()).ajustar(f)
    fac = g.escala_resumen["factor_pais"]
    otros = [fac[c][0] for c in fac if c != "P00"]
    assert fac["P00"][0] / np.median(otros) > 1.6 and max(otros) < 1.1          # relativo al panel (P00 incluido)
    a0 = _ancho(g.simular("P00", 0, horizonte=1, n_lotes=40, por_lote=100, semilla=1))
    a1 = _ancho(g.simular("P01", 0, horizonte=1, n_lotes=40, por_lote=100, semilla=1))
    assert a0 > 1.5 * a1
    g1 = E.Generador(E.Config()).ajustar(f)                                     # v1: el pool domina (k_pais = 40)
    b0 = _ancho(g1.simular("P00", 0, horizonte=1, n_lotes=40, por_lote=100, semilla=1))
    assert a0 > b0


def test_escala_pais_sin_heterogeneidad_no_cambia_nada_relevante(filas):
    g = E.Generador(E.Config(escala_pais=True)).ajustar(filas)
    tau = np.array(g.escala_resumen["tau"])
    assert tau[0] < 0.12                                                         # bolsa homogénea en el panel sintético
    a = _ancho(g.simular("P01", 0, horizonte=1, n_lotes=40, por_lote=100, semilla=2))
    b = _ancho(E.Generador(E.Config()).ajustar(filas).simular("P01", 0, horizonte=1, n_lotes=40, por_lote=100,
                                                               semilla=2))
    assert abs(a / b - 1) < 0.10


def test_pais_fuera_del_pool_recibe_la_predictiva_del_panel():
    f = E.preparar_filas(_panel_hetero(2.5))
    g = E.Generador(E.Config.v2()).ajustar(f[f["pais"] != "P03"])
    m, tau2 = g.escala_pred
    assert tau2[0] > 0                                                          # hay heterogeneidad (P00)
    rng = np.random.default_rng(0)
    gs = np.array([g._factor_lote("P03", rng)[0] for _ in range(400)])
    assert np.std(np.log(gs)) == pytest.approx(np.sqrt(tau2[0]), rel=0.15)
    assert np.mean(np.log(gs)) == pytest.approx(m[0], abs=0.05)


def test_sin_incertidumbre_factor_fijo():
    f = E.preparar_filas(_panel_hetero(2.0))
    g = E.Generador(E.Config.v2(incertidumbre=False)).ajustar(f)
    rng = np.random.default_rng(0)
    assert np.allclose(g._factor_lote("P00", rng), g._factor_lote("P00", rng))


# ------------------------------------------------------------------ suavizado y mezcla
def test_suavizado_ensancha_mas_las_celdas_pequenas(filas):
    g1 = E.Generador(E.Config()).ajustar(filas)
    g2 = E.Generador(E.Config(c_suavizado=4.0)).ajustar(filas)
    n = {c: len(i) for c, i in g1.celdas.items()}
    pequeña = min((c for c in n if c[0] == c[1]), key=n.get)
    grande = max((c for c in n if c[0] == c[1]), key=n.get)
    r = {}
    for c in (pequeña, grande):
        a1 = _ancho(g1.simular("P01", c[0], horizonte=1, n_lotes=40, por_lote=100, semilla=5))
        a2 = _ancho(g2.simular("P01", c[0], horizonte=1, n_lotes=40, por_lote=100, semilla=5))
        r[c] = a2 / a1
    assert r[pequeña] > r[grande] and r[grande] < 1.05


def test_suavizado_no_toca_la_inflacion(filas):
    g = E.Generador(E.Config.v2()).ajustar(filas)
    e = g.simular("P01", "sobrecalentamiento", horizonte=3, n_lotes=20, por_lote=50, semilla=2)
    alta = np.isin(e.regimen, (1, 2))
    # coherencia régimen-inflación como en v1 (solo el respaldo (s_prev, ·) de celdas raras la rompe, ≈ 0,4 %)
    assert np.mean((e.inflacion > E.UMBRAL_INFL) == alta) > 0.99
    assert set(np.unique(e.inflacion)).issubset(set(g.V[:, len(g.vars) - 2]))     # valores históricos, sin ruido


def test_mezcla_acerca_la_celda_al_incondicional(filas):
    """Con k_mezcla enorme la bolsa en estanflación conocida (efecto plantado −15 %) se acerca a la del mismo lado de
    la inflación sin condicionar al régimen de partida."""
    base = E.Generador(E.Config()).ajustar(filas)
    mez = E.Generador(E.Config(k_mezcla=1e6)).ajustar(filas)
    m0 = np.nanmean(base.simular("P01", 2, horizonte=1, n_lotes=20, por_lote=200, semilla=7).rent[:, 0, 0])
    m1 = np.nanmean(mez.simular("P01", 2, horizonte=1, n_lotes=20, por_lote=200, semilla=7).rent[:, 0, 0])
    assert m1 > m0 + 0.05


def test_v2_formas_reproducible_y_sin_nan(filas):
    g = E.Generador(E.Config.v2()).ajustar(filas)
    a = g.simular("P02", "expansion", horizonte=5, n_lotes=10, por_lote=30, semilla=9)
    b = g.simular("P02", "expansion", horizonte=5, n_lotes=10, por_lote=30, semilla=9)
    assert a.rent.shape == (300, 5, 5) and np.array_equal(a.rent, b.rent, equal_nan=True)
    assert np.isfinite(a.rent[:, :, :4]).all()
    assert np.isfinite(a.rent[:, :, 4]).all()                                   # oro imputado por donante
    assert g.tabla_regimenes("P02", n_lotes=5, por_lote=20).shape[0] == 4 * 5
    gt = E.Generador(E.Config.v2(modo="t")).ajustar(filas)
    assert np.isfinite(gt.simular("P02", 2, horizonte=2, n_lotes=5, por_lote=20, semilla=1).rent[:, :, :4]).all()


def test_v2_mejora_la_cobertura_dejando_fuera_un_pais_volatil():
    """Proceso conocido con un país 2,5 veces más volátil: dejándolo fuera, v1 infracubre su bolsa; v2 menos."""
    f = E.preparar_filas(_panel_hetero(2.5, semilla=3, n_paises=8))
    ev1 = Q.evaluar_motor(f, "loco", 20, 100, 1, H=1, cfg=E.Config())
    ev2 = Q.evaluar_motor(f, "loco", 20, 100, 1, H=1, cfg=E.Config.v2())
    p0 = ev1["pais"] == "P00"
    c1, c2 = np.nanmean(ev1["dentro90"][p0, 0]), np.nanmean(ev2["dentro90"][p0, 0])
    assert c2 > c1 + 0.03


# ------------------------------------------------------------------ horizonte móvil (estado mensual)
def _series(n_meses_fin="2025-12-01", trim_fin="2025-10-01", infl=0.02, semilla=0):
    rng = np.random.default_rng(semilla)
    m = pd.date_range("2005-01-01", n_meses_fin, freq="MS")
    cpi = pd.Series(100 * np.exp(np.cumsum(infl / 12 + 0.002 * rng.standard_normal(len(m)))), index=m)
    q = pd.date_range("2005-01-01", trim_fin, freq="QS")
    pib = pd.Series(np.exp(np.cumsum(0.005 + 0.01 * rng.standard_normal(len(q)))), index=q)
    return cpi, pib


def test_estado_movil_en_diciembre_es_el_estado_anual():
    from src.report import escenarios_vivo as V
    cpi, pib = _series()
    a, b = V.estado_pais(cpi, pib), E.estado_movil(cpi, pib)
    assert b["inflacion"] == pytest.approx(a["inflacion"], abs=1e-12)
    assert b["brecha"] == pytest.approx(a["brecha_pib_total"], abs=1e-12)
    assert b["regimen"] == a["regimen"] and b["mes_ipc"] == "2025-12-01" and not b["per_capita"]


def test_estado_movil_usa_el_ultimo_mes_y_no_retrocede_un_año():
    cpi, pib = _series("2026-09-01", "2026-04-01")
    b = E.estado_movil(cpi, pib)
    assert b["mes_ipc"] == "2026-09-01" and b["trimestre_pib"] == "2026-04-01"
    sin = cpi.drop(pd.Timestamp("2025-10-01"))                                   # un mes perdido (caso EE. UU.)
    c = E.estado_movil(sin, pib)
    assert c["mes_ipc"] == "2026-09-01" and c["huecos_ipc_interpolados"] == 1
    assert c["inflacion"] == pytest.approx(b["inflacion"], abs=0.002)
    dos = cpi.drop([pd.Timestamp("2025-10-01"), pd.Timestamp("2025-11-01")])     # dos huecos → retrocede
    assert E.estado_movil(dos, pib)["mes_ipc"] < "2025-10-01"


def test_estado_movil_per_capita():
    cpi, pib = _series()
    plano = pd.Series(1e6, index=range(1990, 2023))
    assert E.estado_movil(cpi, pib, plano)["brecha"] == pytest.approx(E.estado_movil(cpi, pib)["brecha"], abs=1e-9)
    crece = pd.Series(1e6 * np.exp(0.01 * np.arange(33)), index=range(1990, 2023))   # termina en 2022: extrapola
    b = E.estado_movil(cpi, pib, crece)
    assert b["per_capita"]
    assert b["brecha"] == pytest.approx(E.estado_movil(cpi, pib)["brecha"] - 0.01 * 5.5, abs=0.003)


def test_estado_movil_sin_datos():
    cpi, pib = _series()
    assert E.estado_movil(cpi.iloc[:10], pib)["regimen"] is None
    assert E.estado_movil(cpi, pib.iloc[:20])["regimen"] is None


def test_ventana_objetivo():
    v = E.ventana_objetivo("2026-10-30")
    assert v == {"desde": "2026-11-01", "hasta": "2027-10-31", "meses": 12}
    assert E.ventana_objetivo("2026-12-31")["desde"] == "2027-01-01"


# ------------------------------------------------------------------ proceso sintético v2 (potencia)
def test_inflacion_desde_latente_frecuencias_y_coherencia():
    rng = np.random.default_rng(0)
    z = rng.standard_normal(200_000)
    x = Q.inflacion_desde_latente(z, 0.41, 0.27)
    assert np.mean(x > 0.03) == pytest.approx(0.41, abs=0.005) and np.mean(x > 0.05) == pytest.approx(0.27, abs=0.005)
    assert np.mean(Q.inflacion_desde_latente(z, 0.41, 0.27, desplaz=0.81) > 0.03) == pytest.approx(0.15, abs=0.01)


def test_dgp_rent_factor_pais_y_raros():
    rng = np.random.default_rng(1)
    reg = np.zeros((4, 3000), int)
    reg[:, 1::7] = 2
    fac = np.array([[1.0] * 5, [2.0] * 5, [1.0] * 5, [1.0] * 5])
    sdp = np.full(5, 0.1)
    Y = Q.dgp_rent(reg, np.zeros((5, 4)), np.zeros(5), np.zeros(5), sdp, np.eye(5), np.inf, rng, fac_pais=fac,
                   fac_raro=3.0)
    sd = np.nanstd(Y[:, :, 0], 1)
    assert sd[1] / sd[0] == pytest.approx(2.0, rel=0.08)
    raro = np.zeros(3000, bool)
    raro[2::7] = True                                                           # s_{t−1} = 2
    assert np.nanstd(Y[0, raro, 0]) / np.nanstd(Y[0, ~raro, 0]) == pytest.approx(3.0, rel=0.15)


def test_filas_sinteticas_inflacion_continua_y_k_anchura():
    rng = np.random.default_rng(2)
    lat = {"q_i": 0.41, "a_i": 0.79, "rho_i": 0.69, "q_g": 0.06, "a_g": 0.89, "rho_g": 0.36}
    reg, zi, _ = Q.dgp_regimenes(8, 90, lat, rng, latentes=True)
    infl = Q.inflacion_desde_latente(zi, 0.41, 0.27)
    Y = Q.dgp_rent(reg, Q.EFECTOS_REF, np.full(5, 0.03), np.full(5, 0.05), np.full(5, 0.1), np.eye(5), 5.0, rng)
    f = Q.filas_sinteticas(reg, Y, [f"C{i}" for i in range(8)], np.arange(1900, 1990), infl=infl)
    assert np.all((np.expm1(f["inflacion"]) > 0.03) == np.isin(f["s"], (1, 2)))
    ev = Q.evaluar_motor(f, "loco", 10, 100, 1, H=1, cfg=E.Config.v2(), k_anchura=(1.0, 0.8))
    assert np.array_equal(np.isnan(ev["dentro_k"][:, :, 0]), np.isnan(ev["dentro90"]))
    assert np.nanmean(ev["dentro_k"][:, :, 0]) == pytest.approx(np.nanmean(ev["dentro90"]), abs=0.01)
    assert np.nanmean(ev["dentro_k"][:, :, 1]) < np.nanmean(ev["dentro_k"][:, :, 0]) - 0.03


def test_potencia_v2_tuberia_estadisticos():
    from scripts import int11_v2_potencia as PV
    rng = np.random.default_rng(3)
    lat = {"q_i": 0.41, "a_i": 0.79, "rho_i": 0.69, "q_g": 0.06, "a_g": 0.89, "rho_g": 0.36}
    reg, zi, _ = Q.dgp_regimenes(14, 80, lat, rng, latentes=True)
    infl = Q.inflacion_desde_latente(zi, 0.41, 0.27)
    Y = Q.dgp_rent(reg, Q.EFECTOS_REF, np.full(5, 0.03), np.full(5, 0.05), np.full(5, 0.1), np.eye(5), 5.0, rng)
    f = PV.a_filas(reg, Y, infl, np.arange(1925, 2005))
    ev = Q.evaluar_motor(f, "loco", 10, 100, 1, H=1, cfg=E.Config.v2(), k_anchura=PV.K_ANCHO)
    st = PV.estadisticos(ev)
    assert 0.8 < st["S5"] < 1 and st["S5_k"][2] < st["S5_k"][0]
    assert st["infl5"]["bss"] > 0 and 0 <= st["infl5"]["p"] <= 1
    o = PV.potencia_puerta([st, PV.estadisticos(ev, ev["año"] >= 1960), st])
    assert o["R"] == 3 and len(o["banda_nula_S5"]) == 2


# ------------------------------------------------------------------ corrida v2 (fase D)
def test_corrida_v2_se_niega_a_repetir(tmp_path, monkeypatch):
    from scripts import int11_v2_corrida as C
    falso = tmp_path / "int11_v2_resultado.json"
    falso.write_text("{}")
    monkeypatch.setattr(C, "SALIDA", falso)
    monkeypatch.setattr("sys.argv", ["int11_v2_corrida"])
    with pytest.raises(SystemExit):
        C.main()


def test_puerta_d_criterios():
    from scripts import int11_v2_corrida as C
    banda = {"S_raros": {"banda_2.5_97.5": [0.86, 0.95]}}
    L = {"S5": 0.905, "S_activo": {"bolsa": 0.90, "bonos": 0.875, "oro": np.nan}}
    assert C.puerta_d(L, 0.87, banda)["pasa"]
    assert not C.puerta_d(L, 0.85, banda)["pasa"]
    assert not C.puerta_d({**L, "S5": 0.884}, 0.87, banda)["pasa"]
    assert not C.puerta_d({**L, "S_activo": {"bolsa": 0.869}}, 0.87, banda)["pasa"]


def test_corrida_v2_estadisticos_auxiliares():
    from scripts import int11_v2_corrida as C
    ev = {"s_prev": np.array([0, 2, 3, 1]), "pais": np.array(["A", "A", "B", "B"]),
          "dentro90": np.array([[1, 1, 1, 1, np.nan], [0, 1, 1, 1, 1], [1, 0, 1, 1, np.nan], [1, 1, 1, 1, 1.0]])}
    assert C.s_raros(ev) == pytest.approx(7 / 9)
    pp = C.por_pais(ev)
    assert pp["A"]["filas"] == 2 and pp["B"]["bolsa"] == 1.0
    assert C.por_regimen_activo(ev)["estanflacion"]["bolsa"] == 0.0
