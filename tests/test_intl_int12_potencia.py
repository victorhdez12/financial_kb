"""Tests sintéticos del script de potencia de INT-12 (sin datos reales)."""
import numpy as np
import pandas as pd

from scripts import int12_potencia as S


def _diaria(vals, inicio="2000-01-03"):
    idx = pd.bdate_range(inicio, periods=len(vals))
    return pd.Series(vals, index=idx, dtype=float)


def test_objetivos_mensuales_rv_y_caida_usan_solo_meses_siguientes():
    # enero: 0,0 ; febrero: −5 % cada día los 3 primeros días → caída ≥ 10 % en 1 mes desde el origen de enero
    r = _diaria(np.zeros(70))
    feb = r.index[r.index.month == 2]
    r[feb[:3]] = -0.05
    o = S.objetivos_mensuales(r, 1)
    ene = o[o.origen == pd.Period("2000-01", "M")].iloc[0]
    assert ene.caida == 1 and np.isclose(ene.rv, 3 * 0.05 ** 2)
    fe = o[o.origen == pd.Period("2000-02", "M")].iloc[0]
    assert fe.caida == 0 and fe.rv == 0           # marzo sin movimiento: el origen de febrero no ve febrero
    assert o.origen.max() < r.index.to_period("M").max()     # el último mes no tiene objetivo completo


def test_episodios_agrupa_meses_cercanos():
    ms = [pd.Period(x, "M") for x in ("1987-10", "1987-11", "1988-01", "1990-08")]
    assert S.episodios(ms, 3) == 2
    assert S.episodios(ms, 1) == 3


def test_qlike_minima_en_la_verdad_y_no_negativa():
    y = np.array([1.0, 2.0, 0.5])
    assert np.allclose(S.qlike(y, y), 0)
    assert (S.qlike(y * 1.3, y) > 0).all() and (S.qlike(y * 0.7, y) > 0).all()


def test_pinball_y_fz0_premian_el_cuantil_correcto():
    rng = np.random.default_rng(0)
    y = rng.standard_normal(200_000)
    q5, es5 = -1.6449, -2.0627
    assert S.pinball(np.full_like(y, q5), y).mean() < S.pinball(np.full_like(y, -1.2), y).mean()
    bien = S.fz0(np.full_like(y, q5), np.full_like(y, es5), y).mean()
    mal = S.fz0(np.full_like(y, -1.2), np.full_like(y, -1.6), y).mean()
    assert bien < mal


def test_nw_t_y_lags():
    rng = np.random.default_rng(1)
    d = rng.standard_normal(500) + 0.3
    assert S.nw_t(d, 3) > 4
    assert S.lags_hac(660, 3) == 2 + int(np.floor(4 * 6.6 ** (2 / 9)))


def test_oraculo_cuadra_con_montecarlo():
    p = S.Proceso(rho=(0.0, 0.0, 0.0), nu=1e6, vol_anual=0.16, deriva_diaria=0.0)
    rng = np.random.default_rng(2)
    r, C = S.simular_camino(400_000, p, rng)
    H = 21
    orig = np.arange(1000, 400_000 - H - 1, 50)
    f = S.oraculo(C[orig], p, H)
    y = S.suma_futura(r ** 2, H)[orig]
    assert abs(y.mean() / f.mean() - 1) < 0.05            # insesgado en media
    assert abs(np.sqrt(252 * (r ** 2).mean()) - 0.16) < 0.02  # nivel de volatilidad del proceso


def test_suma_futura_excluye_el_dia_de_origen():
    x = np.arange(10, dtype=float)
    s = S.suma_futura(x, 3)
    assert s[0] == 1 + 2 + 3 and np.isnan(s[-1]) and s[6] == 7 + 8 + 9


def test_har_respeta_embargo():
    """El HAR del origen o solo puede usar filas d' con d' + H ≤ o: si se alteran los rendimientos posteriores al
    origen, la previsión en el origen no cambia."""
    rng = np.random.default_rng(3)
    r = rng.standard_normal(3000) * 0.01
    H, o = 21, np.array([2500])
    f1 = S.prevision_har(r, o, H, primer_entreno=63)
    r2 = r.copy()
    r2[2501:] *= 5
    f2 = S.prevision_har(r2, o, H, primer_entreno=63)
    assert np.isclose(f1, f2).all()


def test_b1_es_varianza_de_12_meses():
    r = np.zeros(20 * S.DIAS_MES)
    for m in range(20):
        r[m * S.DIAS_MES] = 0.01 * (m % 3)
    o = np.array([12 * S.DIAS_MES - 1])
    m = np.array([0.01 * (k % 3) for k in range(12)])
    assert np.isclose(S.prevision_b1(r, o, S.DIAS_MES)[0], m.var(ddof=1))


def test_potencia_y_ganancia_suben_con_w():
    rng = np.random.default_rng(4)
    p = S.Proceso()
    esc = S.Escenario("t", 240, meses_entreno=120, hs=(1,))
    res = S.potencia(esc, p, 8, rng, ws=(0.0, 0.5, 1.0))["h1"]
    g = [res["contrastes"][f"ml_w{w}_vs_har"]["qlike"]["ganancia_rel"] for w in (0.0, 0.5, 1.0)]
    assert g[0] < g[1] < g[2]
    pw = [res["contrastes"][f"ml_w{w}_vs_har"]["qlike"]["potencia"] for w in (0.0, 0.5, 1.0)]
    assert pw[2] >= pw[0]
    assert res["contrastes"]["har_vs_b1_12m"]["qlike"]["ganancia_rel"] > 0


def test_mde_interpola():
    filas = {f"ml_w{w}_vs_har": {"qlike": {"ganancia_rel": g, "potencia": p, "fraccion_recorrido_constante_oraculo": g}}
             for w, g, p in ((0.0, 0.0, 0.05), (0.5, 0.04, 0.6), (1.0, 0.08, 1.0))}
    out = S.mde(filas, "qlike", ws=(0.0, 0.5, 1.0))
    assert np.isclose(out["mde_ganancia_qlike"], 0.04 + 0.5 * 0.04)
    assert out["potencia_si_ganancia_0.02"] == round(float(np.interp(0.02, [0, .04, .08], [.05, .6, 1])), 3)
