"""Tests sintéticos de la potencia de INT-17 (sin datos reales): etiqueta, calendario con embargo, rasgos "as of",
y que la tubería recupera una señal plantada y no la inventa sin señal (P4)."""
import numpy as np
import pandas as pd
from scipy.stats import norm

from scripts import int17_potencia as S


def _usrec(picos, desde="1950-01", hasta="2004-12", dur=8):
    idx = pd.period_range(desde, hasta, freq="M")
    u = pd.Series(0.0, index=idx)
    for p in picos:
        e = pd.Period(p, "M")
        u[e:e + dur - 1] = 1.0
    return pd.Series(u.values, index=idx.to_timestamp())


def test_entradas_y_filas_objetivo():
    u = _usrec(["1960-05", "1970-01"])
    df, ent = S.filas_objetivo(u, pd.Period("1959-01", "M"), pd.Period("1971-06", "M"))
    assert [str(e) for e in ent] == ["1960-05", "1970-01"]
    pos = list(df[df.y == 1].mes.astype(str))
    assert pos[0] == "1959-05" and "1960-04" in pos and "1960-05" not in pos     # (M, M + 12]
    assert not df.set_index(df.mes.astype(str)).loc["1960-06", "en_riesgo"]      # en recesión: fuera del riesgo


def test_calendario_respeta_embargo_y_minimo_de_entradas():
    u = _usrec(["1957-09", "1960-05", "1970-01", "1980-02", "1990-08", "2001-04"])
    df, ent = S.filas_objetivo(u)
    cal = S.calendario(df)
    d = df[df.en_riesgo].reset_index(drop=True)
    t = np.array([(m - S.FIT_DESDE).n for m in d.mes])
    for anio, fit, pred in cal:
        p0 = (pd.Period(f"{anio}-01", "M") - S.FIT_DESDE).n
        assert (t[fit] + S.EMBARGO <= p0).all()
        assert {m.year for m in d.mes.iloc[pred]} == {anio}
    a0, fit0, _ = cal[0]
    assert len(set(d.ent.values[fit0][d.y.values[fit0] == 1])) >= 2
    assert a0 == 1962


def test_prof_yoy_regla_de_retraso_no_usa_el_trimestre_antes_de_tiempo():
    q = pd.date_range("1958-01-01", "1962-10-01", freq="QS")
    prof = pd.Series(np.exp(np.arange(len(q)) ** 1.5 * 0.01), index=q)
    defl = pd.Series(1.0, index=q)
    rej = pd.date_range("1960-01-31", "1960-12-31", freq="ME")
    x = S.prof_yoy_ultima(prof, defl, rej)
    yoy = np.log(prof) - np.log(prof).shift(4)
    # 1960T1 (fin 31-mar) se usa desde el fin de julio; en junio sigue el de 1959T4
    assert np.isclose(x.loc["1960-07-31"], yoy.loc["1960-01-01"])
    assert np.isclose(x.loc["1960-06-30"], yoy.loc["1959-10-01"])
    assert (S.disponible_regla(pd.DatetimeIndex(["1960-10-01"])) == pd.DatetimeIndex(["1961-04-30"])).all()


def test_prof_yoy_alfred_usa_la_anada_vigente():
    q = pd.date_range("1980-01-01", "1981-04-01", freq="QS")      # 1980T1 … 1981T2
    v1 = pd.DataFrame({"date": q[:-1], "value": 100.0, "realtime_start": pd.Timestamp("1981-03-01"),
                       "realtime_end": pd.Timestamp("1981-05-31")})
    v1.loc[v1.index[-1], "value"] = 110.0                         # 1981T1 = 110 en la 1.ª añada (sin 1981T2)
    v2 = pd.DataFrame({"date": q, "value": 100.0, "realtime_start": pd.Timestamp("1981-06-01"),
                       "realtime_end": pd.NaT})
    v2.loc[v2.index[-1], "value"] = 120.0                         # 1981T2 = 120 en la 2.ª añada
    vint = pd.concat([v1, v2], ignore_index=True)
    defl = pd.Series(1.0, index=q)
    assert np.isclose(S.prof_yoy_alfred(vint, defl, pd.Timestamp("1981-04-30")), np.log(1.10))
    assert np.isclose(S.prof_yoy_alfred(vint, defl, pd.Timestamp("1981-06-30")), np.log(1.20))
    assert np.isnan(S.prof_yoy_alfred(vint, defl, pd.Timestamp("1981-02-28")))   # antes de la 1.ª añada: nada


def test_margen_caida8_no_positiva():
    q = pd.date_range("1950-01-01", periods=40, freq="QS")
    rng = np.random.default_rng(0)
    prof = pd.Series(np.exp(rng.standard_normal(40) * 0.1), index=q)
    gdp = pd.Series(10.0, index=q)
    m = S.margen_caida8(prof, gdp).dropna()
    assert len(m) == 33 and (m <= 1e-12).all() and (m == 0).any()


def test_delta_poblacional_y_su_inversa():
    a = np.sqrt(2) * norm.ppf(0.8)
    assert abs(S.delta_poblacional(a, 0.0)) < 1e-12
    for d in (0.02, 0.04, 0.08):
        assert abs(S.delta_poblacional(a, S.b_para_delta(a, d)) - d) < 1e-6


def test_bootstrap_por_bloques():
    rng = np.random.default_rng(0)
    assert S.boot_inferior(np.full(200, 0.3), rng, 100) > 0
    assert S.boot_inferior(rng.standard_normal(200) - 1.0, rng, 100) < 0


def _est_sintetica():
    picos = [f"{y}-06" for y in range(1958, 2003, 4)]           # 12 recesiones: más información que la real
    df, _ = S.filas_objetivo(_usrec(picos, dur=6))
    return S.Estructura(df)


def test_recupera_senal_plantada_y_no_la_inventa():
    est = _est_sintetica()
    a = np.sqrt(2) * norm.ppf(0.75)
    rng = np.random.default_rng(1)
    nula = np.array([est.evaluar(*est.simular(rng, a, 0.0, 0.0, 0.3, 0.9, 0.75))["D"] for _ in range(60)])
    senal = np.array([est.evaluar(*est.simular(rng, a, 3.0, 0.0, 0.3, 0.9, 0.75))["D"] for _ in range(30)])
    c = np.quantile(nula, 0.95)
    assert np.median(nula) <= 0.01                                   # sin señal no aparece mejora
    assert (senal > c).mean() >= 0.85 and np.median(senal) > 0.05    # señal fuerte: se recupera


def test_escenario_estructura_de_salida_y_potencia_monotona():
    est = _est_sintetica()
    out = S.escenario(est, 0.75, 0.0, 0.0, 0.9, 0.75, [0.04, 0.08, 0.20], 40, 7, 0)
    assert out["nula"]["critico_5"] is not None and len(out["filas"]) == 3
    pot = [f["potencia_5"] for f in out["filas"]]
    assert pot[-1] > pot[0] and pot[-1] >= 0.6                      # más señal, más potencia
