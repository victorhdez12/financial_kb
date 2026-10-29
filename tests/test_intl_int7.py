"""Tests sintéticos de src/intl/int7.py (INT-7): sin datos reales."""
import numpy as np
import pandas as pd

from src.intl import int3
from src.intl import int3b
from src.intl import int7 as V


def panel_ar1(rng, n, N, phi, delta, b=0.0, rho=0.3, faltan=True):
    """x AR(1) por unidad, y_{t+1} = b·x_t + e_{t+1}, corr(e, v) = δ; componente común ρ. Huecos al principio."""
    f, g = rng.standard_normal(n), rng.standard_normal((n, N))
    v = np.sqrt(rho) * f[:, None] + np.sqrt(1 - rho) * g
    w = delta * v + np.sqrt(1 - delta ** 2) * rng.standard_normal((n, N))
    X = np.empty((n, N))
    X[0] = rng.standard_normal(N) / np.sqrt(1 - phi ** 2)
    for t in range(1, n):
        X[t] = phi * X[t - 1] + v[t]
    Y = np.full((n, N), np.nan)
    Y[1:] = b * X[:-1] + w[1:]
    if faltan:
        X[: n // 5, 0] = np.nan
        Y[: n // 5 + 1, 0] = np.nan
    return X, Y


def filas_1(X, Y):
    f = np.zeros(X.shape, bool)
    f[:-1] = np.isfinite(X[:-1]) & np.isfinite(Y[1:])
    return f


def test_hac_coincide_con_driscoll_kraay_de_int3():
    rng = np.random.default_rng(0)
    X, Y = panel_ar1(rng, 60, 5, 0.5, -0.5, b=0.3)
    f = filas_1(X, Y)
    d = V.Diseno(f, 1, False, np.arange(1900, 1960), np.isfinite(X))
    r = d.ols(X, Y)
    ti, tj = np.nonzero(f)
    ref = int3.driscoll_kraay(pd.Series(Y[ti + 1, tj]), pd.Series(X[ti, tj]), pd.Series(tj.astype(str)),
                              pd.Series(1900 + ti))
    assert np.isclose(r["b"][0], ref["efecto"]) and np.isclose(r["t"][0], ref["t"]) and r["L"] == ref["lags"]


def test_hac_nw_coincide_con_int3b():
    rng = np.random.default_rng(1)
    x, y = rng.standard_normal(80), rng.standard_normal(80)
    r = V.hac(x - x.mean(), y - y.mean(), np.arange(80), 3, corr="nw")
    ref = int3b.nw(y, x, 3)
    assert np.isclose(r["t"][0], ref["t"])


def test_fe_dos_vias_igual_que_ficticias():
    rng = np.random.default_rng(2)
    u, a = np.repeat(np.arange(4), 30), np.tile(np.arange(30), 4)
    keep = rng.random(120) > 0.1
    u, a = u[keep], a[keep]
    x, y = rng.standard_normal(len(u)), rng.standard_normal(len(u))
    fe = V.FE(u, a, True)
    b = (fe(x) @ fe(y)) / (fe(x) @ fe(x))
    D = np.column_stack([x, np.eye(4)[u], np.eye(30)[a][:, 1:]])
    ref = np.linalg.lstsq(D, y, rcond=None)[0][0]
    assert np.isclose(b, ref)


def test_kendall_corrige_el_sesgo_de_phi():
    rng = np.random.default_rng(3)
    ph, pc = [], []
    for _ in range(300):
        X, _ = panel_ar1(rng, 80, 1, 0.9, 0.0, faltan=False)
        ar = V.ar1_kendall(X)
        ph.append(ar["phi"][0])
        pc.append(ar["phi_c"][0])
    assert np.mean(ph) < 0.87 and abs(np.mean(pc) - 0.9) < abs(np.mean(ph) - 0.9)


def test_amihud_hurvich_quita_casi_todo_el_sesgo_de_stambaugh():
    rng = np.random.default_rng(4)
    bo, ba = [], []
    for _ in range(200):
        X, Y = panel_ar1(rng, 60, 3, 0.9, -0.9, b=0.0)
        d = V.Diseno(filas_1(X, Y), 1, False, np.arange(60), np.isfinite(X))
        bo.append(d.ols(X, Y)["b"][0])
        ba.append(d.ah(X, Y)["b"][0])
    assert np.mean(bo) > 0.03                       # sesgo de Stambaugh hacia la predictibilidad
    assert abs(np.mean(ba)) < 0.5 * np.mean(bo)


def test_bootstrap_nulo_tamaño_cerca_del_5pc_con_ar1_persistente_y_delta_fuerte():
    """Bajo H0 (b = 0) con φ = 0,9 y δ = −0,9 el t ingenuo rechaza de más; el p del bootstrap nulo que conserva δ
    rechaza ≈ 5 % de las veces."""
    rng = np.random.default_rng(5)
    rech_boot, rech_ing = [], []
    for _ in range(160):
        X, Y = panel_ar1(rng, 70, 4, 0.9, -0.9, b=0.0)
        d = V.Diseno(filas_1(X, Y), 1, False, np.arange(70), np.isfinite(X))
        r = d.ols(X, Y)
        t0 = float(r["t"][0])
        par = V.residuos_pares(d, X, Y)
        tb = V.bootstrap(par, {"d": d}, 199, rng)["d"]
        rech_boot.append(V.p_bootstrap(t0, tb) <= 0.05)
        rech_ing.append(V.resumen(r)["p_student"] <= 0.05)
    tb_rate, ing_rate = np.mean(rech_boot), np.mean(rech_ing)
    assert 0.01 <= tb_rate <= 0.10, tb_rate
    assert ing_rate > tb_rate


def test_bootstrap_detecta_un_efecto_fuerte():
    rng = np.random.default_rng(6)
    X, Y = panel_ar1(rng, 100, 5, 0.8, -0.7, b=0.4)
    d = V.Diseno(filas_1(X, Y), 1, False, np.arange(100), np.isfinite(X))
    t0 = float(d.ols(X, Y)["t"][0])
    tb = V.bootstrap(V.residuos_pares(d, X, Y), {"d": d}, 199, rng)["d"]
    assert V.p_bootstrap(t0, tb) <= 2 / 200          # suelo con B = 199


def test_generar_respeta_huecos_y_valor_inicial():
    rng = np.random.default_rng(7)
    X, Y = panel_ar1(rng, 50, 3, 0.7, -0.5)
    d = V.Diseno(filas_1(X, Y), 1, False, np.arange(50), np.isfinite(X))
    par = V.residuos_pares(d, X, Y)
    Xs, Ys = V.generar(par, 0.0, rng)
    assert np.isnan(Xs[: 50 // 5, 0]).all() and Xs[50 // 5, 0] == X[50 // 5, 0]
    assert np.isfinite(Xs[:, 1]).all() and Xs[0, 1] == X[0, 1]


def test_p_bootstrap():
    tb = np.arange(-49, 50, dtype=float)              # 99 réplicas simétricas
    assert V.p_bootstrap(0.0, tb) == 1.0
    assert np.isclose(V.p_bootstrap(100.0, tb), 2 / 100)


def test_placebo_y_por_unidad_corren():
    rng = np.random.default_rng(8)
    X, Y = panel_ar1(rng, 60, 4, 0.7, -0.5, b=0.2)
    d = V.Diseno(filas_1(X, Y), 1, True, np.arange(60), np.isfinite(X))
    pl = V.placebo(d, X, Y)
    assert pl["desplazamientos"] == 59 - 2 * 6 + 1 or pl["desplazamientos"] > 40
    pu = V.por_unidad(d, X, Y, ["A", "B", "C", "D"])
    assert set(pu["sin_encoger"]) == {"A", "B", "C", "D"}


def test_hodrick_h1_es_dk_sin_retardos():
    rng = np.random.default_rng(9)
    X, Y = panel_ar1(rng, 60, 3, 0.7, -0.5, b=0.2)
    f = filas_1(X, Y)
    h = V.hodrick_1b(X, Y, f, 1, np.arange(60), False)
    d = V.Diseno(f, 1, False, np.arange(60), np.isfinite(X), L=0)
    assert np.isclose(h["t"], d.ols(X, Y)["t"][0])


def test_oos_sin_senal_da_r2_cercano_o_negativo_y_con_senal_positivo():
    rng = np.random.default_rng(10)
    X, Y = panel_ar1(rng, 120, 4, 0.7, 0.0, b=0.0)
    r0 = V.oos(X, Y, filas_1(X, Y), np.arange(1880, 2000), 1950, False)
    X, Y = panel_ar1(rng, 120, 4, 0.7, 0.0, b=0.6)
    r1 = V.oos(X, Y, filas_1(X, Y), np.arange(1880, 2000), 1950, False)
    assert r0["r2_oos"] < 0.05 and r1["r2_oos"] > 0.1


def test_interaccion_recupera_diferencia():
    rng = np.random.default_rng(11)
    n, N = 150, 4
    X, _ = panel_ar1(rng, n, N, 0.5, 0.0, faltan=False)
    S = (rng.random((n, N)) < 0.3).astype(float)
    Y = np.full((n, N), np.nan)
    Y[1:] = (0.1 + 0.5 * S[:-1]) * X[:-1] + 0.3 * rng.standard_normal((n - 1, N))
    d = V.Diseno(filas_1(X, Y), 1, False, np.arange(n), np.isfinite(X))
    r = V.interaccion(d, X, Y, S)
    assert abs(r["diferencia"]["b"] - 0.5) < 0.15
