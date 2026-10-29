"""Termómetro informativo (src/intl/termometro.py): fechado trimestral, "as of" trimestral, rectas y puerta (sintético)."""
import numpy as np
import pandas as pd

from src.intl import termometro as T


def _pib(valores, desde="1990-01-01"):
    return pd.Series(valores, index=pd.date_range(desde, periods=len(valores), freq="QS"), dtype=float)


def test_fechado_dos_trimestres():
    # sube 8 trimestres, cae 4 (interanual negativa tras ≥ 2), sube después
    v = [100 + i for i in range(8)] + [100, 99, 98, 97, 98, 100, 103, 106, 109, 112, 115, 118]
    f = T.fechado_trimestral(_pib(v))
    ent = f["entrada"].dropna().unique()
    assert len(ent) == 1 and str(ent[0]) == "1992Q2"      # 2.ª caída interanual seguida
    sal = f["salida"].dropna().unique()
    assert len(sal) == 1 and sal[0] > ent[0]
    assert f.loc[pd.Period("1992Q1"), "en_rec"] == 0      # una sola caída no basta


def test_asof_trimestral_respeta_retraso():
    s = pd.Series([1.0, 2.0], index=pd.PeriodIndex(["2000Q1", "2000Q2"], freq="Q"))
    rej = pd.date_range("2000-04-30", "2000-12-31", freq="ME")
    a = T.asof_q(s, 75, rej)
    assert np.isnan(a["2000-05-31"]) and a["2000-06-30"] == 1.0   # 31-mar + 75 días = 14-jun
    assert a["2000-09-30"] == 2.0                                  # 30-jun + 75 = 13-sep


def test_rectas_propia_y_agrupada():
    años = list(range(1950, 2004))
    idx = pd.to_datetime([f"{a + 1}-04-30" for a in años])
    rng = np.random.default_rng(0)
    xm = pd.DataFrame({"A": rng.normal(size=len(años)), "B": rng.normal(size=len(años))}, index=idx)
    xa = pd.DataFrame({"A": 1 + 2 * xm["A"].to_numpy(), "B": 1 + 2 * xm["B"].to_numpy()}, index=años)
    xa.loc[:1985, "B"] = np.nan                                       # B con pocos años → agrupada
    pan = {k: xa for k in T.LINEALES}
    mens = {k: xm for k in T.LINEALES}
    r = T.rectas(pan, mens, ["A", "B"], ["A", "B"])["C1"]
    assert r["A"]["tipo"] == "propia" and abs(r["A"]["b"] - 2) < 1e-9
    assert r["B"]["tipo"] == "agrupada" and abs(r["B"]["a"] - 1) < 1e-9


def test_puerta():
    p = np.linspace(0.05, 0.6, 40)
    assert T.puerta(p, p)["pasa"]
    assert not T.puerta(p, p * 2)["pasa"]                             # pendiente 0,5
    assert not T.puerta(p, np.random.default_rng(1).permutation(p))["pasa"]


def test_recalibracion_corrige_escala():
    rng = np.random.default_rng(2)
    z = rng.normal(size=200)
    pa = 1 / (1 + np.exp(-(-2 + 0.6 * z)))
    pm = 1 / (1 + np.exp(-(-2.5 + z)))          # mensual con más dispersión
    cal = T.calibrar(pa, pm)
    assert abs(cal[1] - 0.6) < 1e-6
    assert np.allclose(T.aplicar_cal(pm, cal), pa)
