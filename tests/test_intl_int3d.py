"""Tests sintéticos del motor de INT-3d (sin datos reales)."""
import numpy as np
import pandas as pd

from scripts import int3d_potencia as S
from src.intl import int3d as M

PA = ["A", "B", "C", "D", "E", "F"]


def _ruido(semilla=0, sd=0.1):
    return np.random.default_rng(semilla).normal(0, sd, (len(PA), S.L))


def _eventos(semilla=0, n=40):
    rng = np.random.default_rng(semilla)
    P = rng.integers(1875, 1995, n)
    D = rng.integers(1, 3, n)
    return {"ci": rng.integers(0, len(PA), n), "P": P, "V": P + D, "fin": rng.integers(0, 2, n)}


def test_efecto_inyectado_se_detecta_y_ruido_no():
    x, ev = _ruido(1), _eventos(1)
    vf = M.valfun_nombre("C1_espera_salida")
    nulo = M.evaluar(vf, x, ev)
    x2 = x.copy()
    for c, v in zip(ev["ci"], ev["V"]):
        if v + 1 <= S.A1:
            x2[c, v + 1 - S.A0] += 0.3
    efe = M.evaluar(vf, x2, ev)
    assert abs(nulo["z"]) < 3.5 and efe["z"] > 4 and efe["p_rangos"] <= 1 / 50
    assert efe["placebos"] == len(M.KS) or efe["placebos"] > 100


def test_efecto_es_T_menos_media_placebo():
    x, ev = _ruido(2), _eventos(2)
    r = M.evaluar(M.valfun_nombre("C3_bonos_recesion"), x, ev)
    assert np.isclose(r["efecto"], r["T_bruto"] - r["media_placebo"])
    assert np.isclose(r["ic95"][1] - r["ic95"][0], 2 * 1.96 * r["sd_placebo"])


def test_submuestra_sin_guerras():
    ev = {"ci": np.array([0, 1]), "P": np.array([1913, 1960]), "V": np.array([1914, 1961]), "fin": np.array([0, 0])}
    s = M.submuestra("C1_espera_salida", ev, "sin_guerras")
    assert list(s["P"]) == [1960]
    assert list(M.submuestra("C1_espera_salida", ev, "1950_2004")["P"]) == [1960]


def test_año_influyente():
    x, ev = _ruido(3), _eventos(3, n=30)
    ev["P"][:5] = 1929
    ev["V"][:5] = 1931
    for c in ev["ci"][:5]:
        x[c, 1932 - S.A0] += 2.0
    r = M.sin_año_influyente(M.valfun_nombre("C1_espera_salida"), x, ev)
    assert r["año"] == 1931


def test_transicion_con_racha_previa():
    filas = [{"pais": "A", "año": y, "cuadrante": q, "truncada": False, "frontera": False}
             for y, q in zip(range(1900, 1908), ["expansion", "expansion", "estanflacion", "expansion",
                                                 "estanflacion", "estanflacion", "expansion", "expansion"])]
    e = M.eventos_transicion(pd.DataFrame(filas), PA, {"estanflacion", "sobrecalentamiento"})
    assert list(e.t) == [1902]                      # 1904 no: en 1903 sí, pero en 1902 era alta


def test_vf_ventana_fracciones():
    x = np.full((len(PA), S.L), 0.06)
    ac = S.Acum(x)
    v, g = M.vf_ventana("V", [(1, 1.0), (2, 4 / 12)])(ac, {"ci": np.array([0]), "V": np.array([1900])})
    assert np.isclose(v[0], 0.08) and g[0] == 1900


def test_eeuu_evento():
    meses = pd.period_range("1960-01", "1990-12", freq="M")
    m = pd.DataFrame({"r_bolsa_tr": 0.01, "r_bono": 0.005, "r_letra": 0.002, "inflacion_mes": 0.0},
                     index=meses.to_timestamp(how="end"))
    m.loc[m.index[(meses >= pd.Period("1975-01", "M")) & (meses <= pd.Period("1975-03", "M"))], "r_bolsa_tr"] = -0.2
    u = M.eeuu_series(m)
    r = M.eeuu_evento(u, pd.Period("1975-03", "M"), pd.Period("1975-06", "M"))
    assert r["fondo_bolsa_meses"] == 0 and r["espera_nber_meses"] == 3 and r["espera_regla_9m_meses"] == 9
    assert np.isclose(r["espera_nber_bolsa_x"], 3 * (0.01 - np.log1p(0.002)))
