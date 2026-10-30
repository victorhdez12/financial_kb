"""Tests SINTÉTICOS de INT-13 (src/intl/int13.py, scripts/int13_corrida.py). Ningún dato real."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.intl import int13 as M

pytest.importorskip("xgboost")


def _rej(desde="1990-01-31", hasta="1995-12-31"):
    return pd.date_range(desde, hasta, freq="ME")


# ---------------------------------------------------------------- objetivos
def test_objetivo_e2_e3_definicion():
    rej = _rej()
    pi = pd.DataFrame({"A": np.r_[np.full(12, 0.02), np.full(len(rej) - 12, 0.05)]}, index=rej)
    y = M.objetivo_e2(pi)["A"]
    assert y.iloc[0] == 1.0                      # 0,02 → 0,05 en 12 meses: +3 pp > 2 pp
    assert y.iloc[12] == 0.0
    assert y.iloc[-12:].isna().all()             # sin futuro observado → NaN
    c = pd.DataFrame({"A": np.r_[np.full(12, 3.0), np.full(len(rej) - 12, 4.0)]}, index=rej)
    y3 = M.objetivo_e3(c)["A"]
    assert y3.iloc[0] == 1.0                     # exactamente +100 pb cuenta
    assert y3.iloc[1] == 1.0 and y3.iloc[12] == 0.0
    assert M.objetivo_e3(c - 0.01 * (c > 3.5))["A"].iloc[0] == 0.0   # +99 pb no cuenta


def test_inflacion_ref_suma_12():
    rej = _rej()
    im = pd.DataFrame({"A": np.full(len(rej), 0.001)}, index=rej)
    pi = M.inflacion_ref(im)["A"]
    assert pi.iloc[:11].isna().all() and np.isclose(pi.iloc[11], 0.012)


def test_e1_entrada_y_conjunto_en_riesgo():
    q = pd.period_range("1980Q1", "1995Q4", freq="Q")
    g = np.full(len(q), 0.01)
    g[40:44] = -0.02                              # caída 1990Q1-1990Q4
    pib = pd.Series(100 * np.exp(np.cumsum(g)), index=q.to_timestamp(how="start"))
    en, ent = M.entradas_recesion(pib)
    meses_ent = ent[ent == 1].index
    assert len(meses_ent) == 1
    m_ent = meses_ent[0]
    assert m_ent.month in (3, 6, 9, 12)           # último mes del trimestre de entrada
    y6 = M.objetivo_e1(en, ent, 6)
    assert y6.loc[m_ent - pd.offsets.MonthEnd(3)] == 1.0
    assert y6.loc[m_ent - pd.offsets.MonthEnd(7)] == 0.0   # entrada fuera de (M, M + 6]
    assert np.isnan(y6.loc[m_ent])                # en recesión: fuera del conjunto en riesgo
    assert y6.iloc[-6:].isna().all()


# ---------------------------------------------------------------- rasgos "as of": sin futuro
def _crudo():
    from scripts.int13_corrida import cargar_sintetico
    return cargar_sintetico(seed=3, n_paises=8)


def _cortar(crudo: dict, X: pd.Timestamp, ruido: float = 7.0) -> dict:
    """Mismo crudo, pero con TODO lo posterior a X cambiado."""
    rng = np.random.default_rng(0)
    out = {"w": {}}
    for k, v in crudo["w"].items():
        v = v.copy()
        v.loc[v.index > X] = rng.standard_normal(v.loc[v.index > X].shape) * ruido
        out["w"][k] = v
    c = crudo["corto_ref"].copy()
    c.loc[c.index > X] += 5.0
    out["corto_ref"] = c
    sx = lambda s: s.where(s.index + pd.offsets.QuarterEnd(0) <= X, s * 3)  # noqa: E731
    out["bis"] = {k: sx(s) for k, s in crudo["bis"].items()}
    out["pib"] = {k: sx(s) for k, s in crudo["pib"].items()}
    mp = crudo["mp"].copy()
    mp[mp.index + pd.offsets.MonthEnd(0) > X] = 50.0
    out["mp"] = mp
    j = crudo["jst_cred"].copy()
    j.loc[j.index >= X.year] = 9.0
    out["jst_cred"] = j
    s = crudo["sahm"].copy()
    s.loc[s.index > X] = 9.0
    out["sahm"] = s
    return out


def test_rasgos_no_usan_el_futuro():
    crudo = _crudo()
    X = pd.Timestamp("1985-06-30")
    a, b = M.construir(crudo), M.construir(_cortar(crudo, X))
    feats = sorted({c for v in M.PAQUETES.values() for c in v})
    ka, kb = a[a.fecha <= X].set_index(["pais", "fecha"]), b[b.fecha <= X].set_index(["pais", "fecha"])
    pd.testing.assert_frame_equal(ka[feats], kb[feats])
    # control: los objetivos SÍ cambian (miran el futuro) → el test tiene potencia
    assert not ka["y_E3"].equals(kb["y_E3"])


def test_tabla_acaba_en_2004_y_muestra_respeta_h():
    df = M.construir(_crudo())
    assert df.fecha.max() <= M.FIN_DEV
    for o, h in M.OBJETIVOS.items():
        S = M.muestra(df, o)
        assert ((S.fecha + pd.offsets.MonthEnd(h)) <= M.FIN_DEV).all()
        assert S[M.BASE[o]].notna().all().all()


# ---------------------------------------------------------------- modelo
def _plantado(n=6000, seed=1):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n)
    z = rng.standard_normal(n)
    ruido = rng.standard_normal((n, 3))
    eta = -1.5 + 0.8 * x + 2.0 * (z > 1.0)        # efecto umbral que el logit de la base no ve
    y = (rng.random(n) < 1 / (1 + np.exp(-eta))).astype(float)
    fechas = pd.date_range("1960-01-31", periods=n // 6, freq="ME").repeat(6)
    paises = np.tile(list("ABCDEF"), n // 6)
    return pd.DataFrame({"fecha": fechas, "pais": paises, "x": x, "z": z, "r1": ruido[:, 0], "r2": ruido[:, 1],
                         "r3": ruido[:, 2], "y_T": y})


def test_xgb_corrige_la_base_con_señal_plantada_y_no_con_ruido(monkeypatch):
    monkeypatch.setattr(M, "BASE", {"T": ["x"]})
    monkeypatch.setattr(M, "PAQUETES", {"senal": ["z"], "ruido": ["r1", "r2", "r3"]})
    monkeypatch.setattr(M, "MONOTONIA", {"T": {}})
    monkeypatch.setattr(M, "OBJETIVOS", {"T": 1})
    df = _plantado()
    P = M.loco(df, "T")
    y = P["y"].to_numpy()
    ll = {k: M.ll_filas(y, P[f"p_{k}"].to_numpy()).mean() for k in ("clima", "base", "senal", "ruido", M.COMBO)}
    assert ll["base"] < ll["clima"]
    assert ll["senal"] < ll["base"] - 0.02
    assert abs(ll["ruido"] - ll["base"]) < 0.01
    assert ll[M.COMBO] < ll["base"]


def test_combinacion_es_media_de_correcciones(monkeypatch):
    monkeypatch.setattr(M, "BASE", {"T": ["x"]})
    monkeypatch.setattr(M, "PAQUETES", {"a": ["z"], "b": ["r1"]})
    monkeypatch.setattr(M, "MONOTONIA", {"T": {}})
    df = _plantado(1200)
    tr, te = df.iloc[:900], df.iloc[900:]
    p = M.ajustar_predecir(tr, te, "T", n_arboles=20)
    lg = M._logit
    esperado = M._sig(lg(p["base"]) + ((lg(p["a"]) - lg(p["base"])) + (lg(p["b"]) - lg(p["base"]))) / 2)
    assert np.allclose(p[M.COMBO], esperado, atol=1e-6)


def test_restriccion_monotona_se_respeta():
    rng = np.random.default_rng(2)
    n = 3000
    x = rng.standard_normal((n, 2))
    y = (rng.random(n) < 1 / (1 + np.exp(-(np.sin(3 * x[:, 0]) + x[:, 1])))).astype(float)
    bst = M.xgb_fit(x, y, np.zeros(n), [1, 0], n_arboles=100)
    g = np.linspace(-3, 3, 200)
    for v in (-1.0, 0.0, 1.0):
        X = np.column_stack([g, np.full_like(g, v)])
        z = M.xgb_margen(bst, X, np.zeros(len(g)))
        assert np.all(np.diff(z) >= -1e-9)


def test_temporal_con_embargo(monkeypatch):
    visto = {}

    def falso(tr, te, obj, n_arboles=0):
        visto["tr"], visto["te"] = tr, te
        return {"clima": np.full(len(te), 0.5)}
    monkeypatch.setattr(M, "ajustar_predecir", falso)
    monkeypatch.setattr(M, "OBJETIVOS", {"T": 12})
    df = pd.DataFrame({"fecha": pd.date_range("1960-01-31", "2003-12-31", freq="ME"), "pais": "A", "y_T": 0.0})
    M.temporal(df, "T")
    assert (visto["tr"].fecha + pd.offsets.MonthEnd(12)).max() <= M.CORTE_TEMPORAL
    assert visto["tr"].fecha.max() == pd.Timestamp("1988-12-31")
    assert visto["te"].fecha.min() == M.PRUEBA_DESDE


def test_loco_no_entrena_con_el_pais_de_prueba(monkeypatch):
    visto = []

    def falso(tr, te, obj, n_arboles=0):
        visto.append((set(tr.pais), set(te.pais)))
        return {"clima": np.full(len(te), 0.5)}
    monkeypatch.setattr(M, "ajustar_predecir", falso)
    df = _plantado(600)
    M.loco(df, "T")
    assert len(visto) == 6 and all(not (a & b) for a, b in visto)


# ---------------------------------------------------------------- incertidumbre y multiplicidad
def test_bloques_mantienen_los_meses_juntos():
    fechas = pd.Series(pd.date_range("1960-01-31", periods=100, freq="ME").repeat(3))
    bs = M.bloques_meses(fechas, bloque=24, reps=5)
    for ix in bs:
        assert len(ix) == len(fechas)
        f = fechas.iloc[ix]
        assert (f.value_counts() % 3 == 0).all()


def test_comparar_detecta_mejora_y_holm():
    rng = np.random.default_rng(4)
    n = 3000
    y = (rng.random(n) < 0.2).astype(float)
    P = pd.DataFrame({"fecha": pd.date_range("1960-01-31", periods=n // 5, freq="ME").repeat(5), "y": y,
                      "p_malo": np.full(n, 0.2), "p_bueno": np.where(y == 1, 0.5, 0.12)})
    boot = M.bloques_meses(P.fecha, reps=200)
    c = M.comparar(P, "bueno", "malo", boot)
    assert c["dlogloss"]["est"] < 0 and c["dlogloss"]["ic95"][1] < 0 and c["dlogloss"]["p_mejora"] < 0.01
    assert c["dauc"]["est"] > 0.3
    h = M.holm({"a": 0.001, "b": 0.02, "c": 0.06})
    assert h["a"]["rechaza"] and not h["c"]["rechaza"] and np.isclose(h["b"]["p_holm"], 0.04)


def test_potencia_y_calibracion():
    assert M.potencia(-0.01, 0.002) > M.potencia(-0.005, 0.002) > M.potencia(-0.001, 0.002)
    assert M.potencia(-0.01, 0.002, años_nuevo=45) > M.potencia(-0.01, 0.002, años_nuevo=20)
    rng = np.random.default_rng(5)
    p = rng.uniform(0.05, 0.6, 20000)
    y = (rng.random(len(p)) < p).astype(float)
    c = M.calibracion(y, p)
    assert 0.9 < c["pendiente"] < 1.1 and abs(c["intercepto"]) < 0.1
    assert all(abs(f["p_media"] - f["frecuencia"]) < 0.05 for f in c["fiabilidad"])


def test_tuberia_sintetica_completa():
    from scripts import int13_corrida as S
    out = S.correr(S.cargar_sintetico(seed=5, n_paises=8), reps=20, n_arboles=20)
    d = out["decision"]
    assert d["n_pruebas"] == 4 * (2 + len(M.PAQUETES))
    out["procedencia"] = {"sintetico": True}
    md = S.informe(S._limpio(out))
    assert "exploratorio: cualquier hallazgo necesita prerregistro y confirmación en vivo o en el bloqueado" in md.lower()
