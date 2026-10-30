"""Tests SINTÉTICOS de INT-11 (src/intl/escenarios.py, src/intl/int11.py). Ningún dato real."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.intl import escenarios as E
from src.intl import int11 as Q
from src.intl.data import FactorCutoffError
from tests.sint_int11 import EFECTO_EST, panel


@pytest.fixture(scope="module")
def filas():
    return E.preparar_filas(panel(), covariables=("termo",))


@pytest.fixture(scope="module")
def gen(filas):
    return E.Generador(E.Config()).ajustar(filas)


def test_modulos_no_leen_datos():
    for m in (E, Q):
        src = Path(m.__file__).read_text()
        assert "load_dev" not in src and "connect(" not in src and "read_parquet" not in src


def test_codigo_regimen():
    c = E.codigo_regimen([0.01, 0.05, 0.05, 0.01, np.nan], [0.1, 0.1, -0.1, -0.1, 0.1])
    assert c.tolist() == [0, 1, 2, 3, -1]


def test_eje_tendencia_mas_frecuente():
    df = panel(n_paises=3)
    p3 = E.estados_operables(df, "p3")
    td = E.estados_operables(df, "tendencia")
    assert (td["brecha"] < 0).mean() > (p3["brecha"] < 0).mean()
    with pytest.raises(ValueError):
        E.estados_operables(df, "otro")


def test_corte_2004():
    df = panel(n_paises=2, a1=2006)
    with pytest.raises(FactorCutoffError):
        E.preparar_filas(df)
    with pytest.raises(FactorCutoffError):
        E.preparar_filas(panel(n_paises=2), anio_max=2010)
    f = E.preparar_filas(panel(n_paises=2))
    with pytest.raises(FactorCutoffError):
        E.Generador(E.Config(anio_max=2020)).ajustar(f)


def test_filas_estructura(filas):
    assert {"s_prev", "s", "w", "sucesor", "z_termo"} <= set(filas.columns)
    assert filas["s"].between(0, 3).all() and filas["s_prev"].between(0, 3).all()
    # sucesor: misma fila del país al año siguiente y s_prev del sucesor = s propio
    i = filas.index[filas["sucesor"] >= 0]
    j = filas.loc[i, "sucesor"].to_numpy()
    assert (filas.loc[j, "año"].to_numpy() == filas.loc[i, "año"].to_numpy() + 1).all()
    assert (filas.loc[j, "s_prev"].to_numpy() == filas.loc[i, "s"].to_numpy()).all()
    # excluir años
    f2 = E.preparar_filas(panel(), excluir=E.GUERRAS)
    assert not f2["año"].isin(E.GUERRAS).any()


def test_kappa_eb_homogeneo_frente_a_heterogeneo():
    rng = np.random.default_rng(0)
    p = np.array([[0.8, 0.2], [0.3, 0.7]])
    hom = np.stack([np.stack([rng.multinomial(200, p[i]) for i in range(2)]) for _ in range(10)])
    het = np.stack([np.stack([rng.multinomial(200, rng.dirichlet(2 * p[i])) for i in range(2)]) for _ in range(10)])
    k_hom = E.kappa_eb(hom, hom.sum(0) / hom.sum(0).sum(-1, keepdims=True))
    k_het = E.kappa_eb(het, het.sum(0) / het.sum(0).sum(-1, keepdims=True))
    assert k_hom > 10 * k_het


def test_markov_recupera_transiciones():
    rng = np.random.default_rng(1)
    P = np.array([[0.8, 0.1, 0.05, 0.05], [0.2, 0.7, 0.05, 0.05], [0.3, 0.2, 0.4, 0.1], [0.4, 0.1, 0.1, 0.4]])
    filas = []
    for c in range(8):
        s = 0
        for t in range(1, 400):
            s2 = rng.choice(4, p=P[s])
            filas.append({"pais": f"C{c}", "año": 1600 + t, "s_prev": s, "s": s2, "w": 0})
            s = s2
    f = pd.DataFrame(filas)
    n = E.recuentos(f, sorted(f.pais.unique()), False)
    phat = n.sum(0) / n.sum(0).sum(-1, keepdims=True)
    assert np.abs(phat - P).max() < 0.06


def test_simular_formas_y_reproducible(gen):
    a = gen.simular("P01", "estanflacion", horizonte=4, n_lotes=20, por_lote=50, semilla=3)
    b = gen.simular("P01", "estanflacion", horizonte=4, n_lotes=20, por_lote=50, semilla=3)
    assert a.rent.shape == (1000, 4, 5) and a.regimen.shape == (1000, 4)
    assert np.isfinite(a.rent).all() and np.isfinite(a.inflacion).all()
    assert np.array_equal(a.rent, b.rent)
    assert a.regimen.min() >= 0 and a.regimen.max() <= 3
    assert a.meta["estado_inicial"] == "estanflacion" and a.meta["config"]["modo"] == "bootstrap"


def test_condiciona_al_regimen_conocido(gen):
    est = gen.simular("P01", 2, horizonte=1, n_lotes=40, por_lote=100, semilla=4).rent[:, 0, 0].mean()
    exp = gen.simular("P01", 0, horizonte=1, n_lotes=40, por_lote=100, semilla=5).rent[:, 0, 0].mean()
    assert est - exp < 0.6 * EFECTO_EST          # efecto plantado −0,15: se recupera al menos el 60 %


def test_coherencia_inflacion_regimen(gen):
    e = gen.simular("P02", 0, horizonte=3, n_lotes=20, por_lote=100, semilla=6)
    alta = np.isin(e.regimen, (1, 2))
    # con celdas de nivel ≤ 1 la inflación sorteada respeta el lado del umbral del régimen simulado
    assert (e.inflacion[alta] > E.UMBRAL_INFL).mean() > 0.9
    assert (e.inflacion[~alta] <= E.UMBRAL_INFL).mean() > 0.9


def test_credibilidad_pais():
    df = panel(desfase_propio=0.20, semilla=7)
    f = E.preparar_filas(df)
    solo = E.Generador(E.Config(k_pais=1e-9)).ajustar(f).simular("P00", 0, 1, 20, 100, semilla=1).rent[:, 0, 0].mean()
    panel_ = E.Generador(E.Config(k_pais=1e9)).ajustar(f).simular("P00", 0, 1, 20, 100, semilla=1).rent[:, 0, 0].mean()
    otro = E.Generador(E.Config(k_pais=1e-9)).ajustar(f).simular("P01", 0, 1, 20, 100, semilla=1).rent[:, 0, 0].mean()
    assert solo - otro > 0.12 and abs(panel_ - otro) < 0.08
    # país fuera del pool (dejar un país fuera): panel puro, sin error
    fuera = E.Generador(E.Config()).ajustar(f[f.pais != "P00"]).simular("P00", 0, 1, 5, 50)
    assert np.isfinite(fuera.rent).all()


def test_bloques_conservan_autocorrelacion():
    """Serie con autocorrelación fuerte (mismo régimen siempre): bloques largos la conservan, bloque 1 no."""
    rng = np.random.default_rng(8)
    filas = []
    for c in range(5):
        x = 0.0
        for t in range(1880, 2001):
            x = 0.9 * x + 0.05 * rng.standard_normal()
            filas.append({"pais": f"C{c}", "año": t, "s_prev": 0, "s": 0, "w_prev": 0, "w": 0, "bolsa": x,
                          "bonos": 0.0, "letras": 0.0, "vivienda": 0.0, "oro": 0.0, "inflacion": 0.01,
                          "crecimiento": 0.02})
    f = pd.DataFrame(filas)
    sig = f.groupby("pais")["año"].shift(-1)
    f["sucesor"] = np.where(sig == f["año"] + 1, f.index + 1, -1)

    def ac(L):
        e = E.Generador(E.Config(bloque_medio=L, incertidumbre=False)).ajustar(f).simular("C0", 0, 6, 10, 200, 2)
        r = e.rent[:, :, 0]
        return np.corrcoef(r[:, :-1].ravel(), r[:, 1:].ravel())[0, 1]
    assert ac(20.0) > 0.6 and abs(ac(1.0)) < 0.1


def test_incertidumbre_de_parametros_ensancha_ic(filas):
    con = E.Generador(E.Config(incertidumbre=True)).ajustar(filas).simular("P01", 2, 1, 60, 200, semilla=9)
    sin = E.Generador(E.Config(incertidumbre=False)).ajustar(filas).simular("P01", 2, 1, 60, 200, semilla=9)
    w = lambda e: np.diff(e.prob_caida("bolsa", -0.2, 1)["ic90"])[0]  # noqa: E731
    assert w(con) > w(sin)


def test_salidas(gen, tmp_path):
    e = gen.simular("P03", "expansion", horizonte=3, n_lotes=10, por_lote=50, semilla=10)
    ab = e.abanico()
    q = ab[[c for c in ab.columns if c.startswith("p")]].to_numpy()
    assert (np.diff(q, axis=1) >= -1e-12).all()
    assert len(ab) == 5 * 3
    p = e.prob_caida("bolsa", -0.2, h=2)
    assert 0 <= p["p"] <= 1 and p["ic90"][0] <= p["p"] <= p["ic90"][1]
    assert e.prob_caida("bolsa", -0.2, h=3, desde_maximo=True)["p"] >= e.prob_caida("bolsa", -0.2, h=3)["p"]
    assert np.isclose(e.prob_regimen(1)["p"].sum(), 1)
    t = e.a_tabla()
    assert len(t) == 500 * 3 and {"trayectoria", "lote", "h", "regimen", "inflacion", "bolsa", "oro"} <= set(t.columns)
    e.guardar(tmp_path / "esc")
    assert pd.read_parquet(tmp_path / "esc.parquet").shape == t.shape
    assert (tmp_path / "esc.json").exists()
    acu = e.acumulada()
    assert np.allclose(acu[:, 0], e.rent[:, 0])


def test_tabla_regimenes(gen):
    t = gen.tabla_regimenes("P01", n_lotes=10, por_lote=100)
    assert len(t) == 4 * 5
    s = t.groupby("regimen")["p_mejor"].sum()
    assert np.allclose(s, 1, atol=1e-9)
    b = t.set_index(["regimen", "activo"])["media"]
    assert b["estanflacion", "bolsa"] < b["expansion", "bolsa"]


def test_modo_t_y_contagio(filas):
    g = E.Generador(E.Config(modo="t", contagio=True)).ajustar(filas)
    e = g.simular("P01", 2, horizonte=3, n_lotes=10, por_lote=100, semilla=11, mundo=1)
    assert e.mundo is not None and e.mundo.shape == (1000, 3)
    assert np.isfinite(e.rent).all()
    assert g.posterior_transicion("P01").shape == (4, 4, 4)
    # colas: la t (ν = 5) da más curtosis que una normal
    z = (e.rent[:, 0, 2] - e.rent[:, 0, 2].mean()) / e.rent[:, 0, 2].std()
    assert (z ** 4).mean() > 3.2


def test_imputa_oro(gen):
    e = gen.simular("P01", 2, horizonte=2, n_lotes=5, por_lote=100, semilla=12)
    assert np.isfinite(e.rent[:, :, 4]).all()


def test_inclinacion_cambia_solo_el_primer_año():
    rng = np.random.default_rng(13)
    df = panel(semilla=13)
    df["termo"] = rng.standard_normal(len(df))
    # la bolsa del año t depende del termómetro de t − 1
    df["bolsa"] = df["bolsa"] + 0.10 * df.groupby("pais")["termo"].shift(1).fillna(0)
    f = E.preparar_filas(df, covariables=("termo",))
    g = E.Generador(E.Config()).ajustar(f)
    alto = g.simular("P01", 0, 2, 30, 100, semilla=1, inclinacion={"termo": (1.5, 0.5)})
    base = g.simular("P01", 0, 2, 30, 100, semilla=1)
    assert alto.rent[:, 0, 0].mean() - base.rent[:, 0, 0].mean() > 0.06
    assert abs(alto.rent[:, 1, 0].mean() - base.rent[:, 1, 0].mean()) < 0.04


# ============================================================================ puntuación
def test_crps_muestra_contra_fuerza_bruta():
    rng = np.random.default_rng(14)
    x, y = rng.standard_normal(200), rng.standard_normal(7)
    bruto = np.abs(x[:, None] - y[None]).mean(0) - 0.5 * np.abs(x[:, None] - x[None]).mean()
    assert np.allclose(E.crps_muestra(x, y), bruto)
    xl = rng.standard_normal(40000)
    assert np.allclose(E.crps_muestra(xl, [0.3, -1.0]), E.crps_normal(0, 1, np.array([0.3, -1.0])), atol=0.01)


def test_pit_uniforme_y_cobertura():
    rng = np.random.default_rng(15)
    x, y = rng.standard_normal(5000), rng.standard_normal(4000)
    u = E.pit(x, y, rng)
    assert abs(u.mean() - 0.5) < 0.02 and abs((u < 0.1).mean() - 0.1) < 0.02
    assert abs(E.cobertura(x, y, 0.05, 0.95).mean() - 0.9) < 0.02
    ls_bueno = E.log_score(x, y).mean()
    ls_malo = E.log_score(3 * x, y).mean()
    assert ls_bueno < ls_malo


def test_dm_conglomerado_tamaño_con_choque_comun():
    """Bajo H0 con choque común de año, el t por años mantiene el tamaño (≈ 5 %); el t ingenuo se dispara."""
    rng = np.random.default_rng(16)
    rech, rech_ing = [], []
    from scipy import stats
    for _ in range(300):
        anio = np.repeat(np.arange(60), 14)
        d = np.repeat(rng.standard_normal(60), 14) + rng.standard_normal(60 * 14)
        rech.append(E.dm_conglomerado(d, anio, lags=0)["p_unilateral"] < 0.05)
        t_ing = d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))
        rech_ing.append(stats.norm.sf(t_ing) < 0.05)
    assert np.mean(rech) < 0.09 and np.mean(rech_ing) > 0.15


def test_cobertura_contraste():
    rng = np.random.default_rng(17)
    anio = np.repeat(np.arange(80), 10)
    r = E.cobertura_contraste(rng.random(800) < 0.8, anio, 0.9)
    assert r["p_bilateral"] < 0.01 and abs(r["cobertura"] - 0.8) < 0.05


# ============================================================================ potencia (proceso sintético)
def test_dgp_regimenes_frecuencias_y_persistencia():
    rng = np.random.default_rng(18)
    par = {"q_i": 0.4, "q_g": 0.1, "a_i": 0.8, "rho_i": 0.6, "a_g": 0.9, "rho_g": 0.3}
    reg = Q.dgp_regimenes(14, 600, par, rng)
    alta = np.isin(reg, (1, 2))
    assert abs(alta.mean() - 0.4) < 0.06 and abs(np.isin(reg, (2, 3)).mean() - 0.1) < 0.04
    pr = Q.indicador_props(alta)
    assert pr["persistencia"] > 0.7 and pr["concordancia"] > 0.2


def test_calibrar_latente_recupera():
    rng = np.random.default_rng(19)
    z = Q.latente(14, 400, 0.85, 0.5, rng) > 0
    pr = Q.indicador_props(z)
    c = Q.calibrar_latente(0.5, pr["persistencia"], pr["concordancia"], T=300)
    assert abs(c["a"] - 0.85) < 0.08 and abs(c["rho"] - 0.5) < 0.15


def _sim(delta, rng, T=130):
    par = {"q_i": 0.4, "q_g": 0.1, "a_i": 0.8, "rho_i": 0.6, "a_g": 0.9, "rho_g": 0.3}
    reg = Q.dgp_regimenes(14, T, par, rng)
    mu = np.array([0.05, 0.03, 0.02, 0.07, 0.01])
    Y = Q.dgp_rent(reg, delta * Q.EFECTOS_REF, mu, np.array([0.12, 0.065, 0.033, 0.022, 0.2]),
                   np.array([0.17, 0.075, 0.046, 0.087, 0.06]), np.eye(5), 5.0, rng)
    return reg, Y


def test_dgp_rent_planta_el_efecto():
    rng = np.random.default_rng(20)
    reg, Y = _sim(1.0, rng, T=400)
    prev = reg[:, :-1]
    y = Y[:, 1:, 2]
    dif = y[np.isin(prev, (1, 2))].mean() - y[~np.isin(prev, (1, 2))].mean()
    assert abs(dif - (-0.05)) < 0.015


def test_evaluar_mejora_con_efecto_y_no_sin_el():
    rng = np.random.default_rng(21)
    reg, Y = _sim(1.5, rng)
    r = Q.evaluar(Y, reg, "loco")
    assert r["crpss"][2] > 0.05 and E.dm_conglomerado(r["d"], r["año"])["p_unilateral"] < 0.05
    reg, Y = _sim(0.0, rng)
    r0 = Q.evaluar(Y, reg, "temporal", corte=70)
    assert r0["crpss_medio"] < 0.01
    r5 = Q.evaluar(Y, reg, "loco", h=5)
    assert len(r5["d"]) <= 14 * 26


def test_cobertura_sim_k():
    rng = np.random.default_rng(22)
    reg, Y = _sim(1.0, rng, T=200)
    ancho = np.nanmean(Q.cobertura_sim(Y, reg, 1.0, 0.05, 0.95, corte=120, prueba=(120, 200))["dentro"])
    estrecho = np.nanmean(Q.cobertura_sim(Y, reg, 0.6, 0.05, 0.95, corte=120, prueba=(120, 200))["dentro"])
    assert 0.83 < ancho < 0.95 and estrecho < ancho - 0.1


# ============================================================================ corrida de desarrollo (sintética)
def test_recalcular_sucesor_tras_subconjunto(filas):
    sub = filas[filas["pais"] != "P00"]
    g = E.Generador(E.Config()).ajustar(sub)
    f = g.filas
    i = np.flatnonzero(f["sucesor"].to_numpy() >= 0)
    j = f["sucesor"].to_numpy()[i]
    assert (f["pais"].to_numpy()[j] == f["pais"].to_numpy()[i]).all()
    assert (f["año"].to_numpy()[j] == f["año"].to_numpy()[i] + 1).all()


def test_filas_sinteticas_y_huecos():
    rng = np.random.default_rng(30)
    reg, Y = _sim(1.0, rng, T=60)
    existe = np.ones((14, 60), bool)
    existe[0, 30] = False
    ok = np.ones((14, 60, 5), bool)
    ok[:, :40, 4] = False
    f = Q.filas_sinteticas(reg, Y, [f"C{i:02d}" for i in range(14)], np.arange(1900, 1960), existe, ok)
    assert len(f) == 14 * 59 - 1
    assert f.loc[f["año"] < 1940, "oro"].isna().all() and f.loc[f["año"] >= 1940, "oro"].notna().all()
    c0 = f[f.pais == "C00"]
    assert (c0.loc[c0["año"] == 1929, "sucesor"] == -1).all()
    assert set(np.unique(f["inflacion"])) <= {0.01, 0.05}


def test_evaluar_motor_calibrado_en_proceso_conocido():
    rng = np.random.default_rng(31)
    reg, Y = _sim(1.0, rng, T=130)
    f = Q.filas_sinteticas(reg, Y, [f"C{i:02d}" for i in range(14)], np.arange(1875, 2005))
    ev = Q.evaluar_motor(f, "loco", 20, 100, 1, H=5)
    r = Q.resumen_motor(ev)
    assert abs(r["S5"] - 0.90) < 0.03 and abs(r["Sb"] - 0.90) < 0.04
    assert r["crpss_%"]["letras"] > 2 and r["dm"]["p_unilateral"] < 0.05
    assert np.isfinite(ev["crps1_5"]).sum() > 100
    et = Q.evaluar_motor(f, "temporal", 20, 100, 1, H=1, corte=1950)
    assert et["año"].min() >= 1950
    with pytest.raises(ValueError):
        Q.evaluar_motor(f, "otro", 2, 10, 1)


def test_corrida_se_niega_a_repetir(tmp_path, monkeypatch):
    from scripts import int11_corrida as C
    falso = tmp_path / "int11_resultado.json"
    falso.write_text("{}")
    monkeypatch.setattr(C, "SALIDA", falso)
    monkeypatch.setattr("sys.argv", ["int11_corrida"])
    with pytest.raises(SystemExit):
        C.main()


def test_puerta_criterios():
    from scripts import int11_corrida as C
    banda = {"S5": {"banda_2.5_97.5": [0.88, 0.92]}, "Sb": {"banda_2.5_97.5": [0.87, 0.93]}}
    res = {"S5": 0.90, "Sb": 0.90, "S_activo": {"bolsa": 0.9, "bonos": 0.86, "oro": np.nan}}
    assert C.puerta(res, banda)["pasa"]
    res["S_activo"]["bonos"] = 0.84
    assert not C.puerta(res, banda)["pasa"]
