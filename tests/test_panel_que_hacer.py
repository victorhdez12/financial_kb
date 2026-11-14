"""Funciones de cálculo de la pestaña «Qué hacer» (src/report/panel_que_hacer.py). Sin base de datos."""
import math

import numpy as np
import pandas as pd

from src.report import panel_que_hacer as Q

ATLAS = {"regimenes": [
    {"id": "inflacion_alta", "nombre": "Inflación alta", "filas": [
        {"activo": "Bonos", "lado": "sufre", "efecto": "−10,1", "ic": "", "estado": "establecido", "nota": "", "fuente": ""},
        {"activo": "Bonos, con lo que se sabe a tiempo", "lado": "sufre", "efecto": "−6,2", "ic": "", "estado": "descriptivo", "nota": "", "fuente": ""},
        {"activo": "Oro (moneda local)", "lado": "no se sabe", "efecto": "−6,0", "ic": "", "estado": "no establecido", "nota": "", "fuente": ""}]},
    {"id": "otro", "nombre": "Otro", "filas": [
        {"activo": "Letras, a tiempo", "lado": "sufre", "efecto": "−5", "ic": "", "estado": "establecido", "nota": "", "fuente": ""}]},
]}


def _rec(sigma=0.107, rv=0.70):
    return Q.recomendacion({"sigma_hat": sigma, "rv": rv, "cierre": "2026-10-31"},
                           {"sigma_hat": 0.110, "rv": 0.70, "cierre": "2026-09-30"},
                           {"sigma_hat": 0.147, "rv": 0.70, "cierre": "2026-10-31"}, 0.1702, 0.16674)


def test_umbral_recorte():
    assert math.isclose(Q.umbral_recorte(0.1702), 0.70 * 0.1702 / 0.675)
    # justo en el umbral, la regla de B1 recorta exactamente 2,5 pp
    s = Q.umbral_recorte(0.1702)
    assert math.isclose(0.70 * 0.1702 / s, 0.675)


def test_nivel_evidencia():
    assert Q.nivel_evidencia("establecido") == "establecido"
    assert Q.nivel_evidencia("establecido (frágil)") == "frágil"
    assert Q.nivel_evidencia("probable") == "frágil"
    assert Q.nivel_evidencia("descriptivo") == "no validado"
    assert Q.nivel_evidencia("no establecido") == "no validado"
    assert Q.nivel_evidencia(None) == "no validado"


def test_recomendacion_sin_recorte_y_con_recorte():
    r = _rec()
    assert r["ok"] and not r["recorta"] and r["delta_base"] == 0 and r["delta_mes"] == 0
    assert math.isclose(r["rf"], 0.15) and "Mantén" in r["frase"] and "10,7 %" in r["frase"]
    r2 = _rec(0.20, 0.5957)
    assert r2["recorta"] and r2["delta_base"] < 0 and math.isclose(r2["delta_mes"], 0.5957 - 0.70)
    assert not Q.recomendacion(None, None, None, 0.17, 0.16)["ok"]


def test_inclinaciones_reglas_fijas():
    ab = {"bolsa": {"p_neg": 0.36, "p50": 0.07}, "bonos": {"p_neg": 0.39, "p50": 0.02}}
    inc = {d["activo"]: d for d in Q.inclinaciones(_rec(), ab, ATLAS, ["inflacion_alta"])}
    assert inc["bolsa"]["flecha"] == "►" and inc["bolsa"]["evidencia"] == "establecido"
    # bonos: ex post establecido y «a tiempo» solo descriptivo → neutral, con dirección no validada ▼
    assert inc["bonos"]["flecha"] == "►" and inc["bonos"].get("direccion_no_validada") == "▼"
    assert inc["oro"]["flecha"] == "►"
    # sin filas del régimen → neutral sin evidencia
    assert inc["vivienda"]["flecha"] == "►" and inc["vivienda"]["evidencia"] == "no validado"
    # una fila «a tiempo» establecida SÍ mueve la flecha
    inc2 = {d["activo"]: d for d in Q.inclinaciones(_rec(), {}, ATLAS, ["otro"])}
    assert inc2["letras"]["flecha"] == "▼" and inc2["letras"]["accion"] == "infraponderar"
    # B1 recortando → bolsa ▼; nunca ▲
    inc3 = {d["activo"]: d for d in Q.inclinaciones(_rec(0.20, 0.5957), {}, ATLAS, [])}
    assert inc3["bolsa"]["flecha"] == "▼"


def test_p_cola_normal():
    assert math.isclose(Q.p_cola_normal(5.0, 1.0), 0.5)
    assert math.isclose(Q.p_cola_normal(3.0, 1.0), 0.02275, abs_tol=1e-4)


def test_error_previsiones_respeta_corte():
    idx = pd.date_range("1990-01-01", "2010-12-01", freq="MS")
    ipc = pd.Series(100 * 1.03 ** (np.arange(len(idx)) / 12), index=idx)   # inflación constante 3 %
    prev = pd.Series(2.0, index=idx)                                         # previsión 2 % → error +1
    e = Q.error_previsiones(prev, ipc)
    assert e["hasta"] <= "2003-12" and math.isclose(e["sesgo"], 1.0, abs_tol=1e-6) and math.isclose(e["rmse"], 1.0, abs_tol=1e-6)
    assert Q.error_previsiones(prev.iloc[:10], ipc) is None


def test_svgs():
    a = {"p5": -0.2, "p25": 0.0, "p50": 0.07, "p75": 0.15, "p95": 0.3, "p_neg": 0.36}
    s = Q.svg_abanico(a, "Bolsa", -0.3, 0.4)
    assert s.startswith("<svg") and s.count("<polygon") == 2 and "p50 7 %" in s
    m = {"p5": -1.8, "p25": 2.0, "p50": 3.6, "p75": 5.5, "p95": 14.4}
    t = Q.svg_inflacion(m, [{"nombre": "Cleveland", "valor": 3.04}], {"valor": 3.7, "mes": "2026-09"})
    assert "umbral 5 %" in t and t.count('class="qh-pt"') == 2


def test_cuantiles():
    q = Q.cuantiles(np.arange(101.0))
    assert q["p50"] == 50 and q["p5"] == 5
