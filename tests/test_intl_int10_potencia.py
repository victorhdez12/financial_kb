"""Tests sintéticos del script de potencia de INT-10 (sin datos reales)."""
import numpy as np
import pandas as pd

from scripts import int10_potencia as S


def test_bajista_entra_con_20_y_sale_a_menos_de_10():
    nivel = pd.Series([100, 110, 95, 87, 80, 90, 100, 105, 120, 90], index=range(2000, 2010), dtype=float)
    est, ent = S.bajista_por_nivel(nivel)
    assert ent == {2003, 2009}                       # 87/110 − 1 = −21 %; 90/120 − 1 = −25 %
    assert list(est.loc[2003:2006]) == [1.0, 1.0, 1.0, 0.0]   # 100/110 − 1 = −9 % → sale en 2006


def test_filas_estado_excluye_el_estado_y_marca_h_previos():
    est = pd.Series([0, 0, 0, 1, 1, 0, 0], index=range(2000, 2007), dtype=float)
    df = S.filas_estado(est, {2003}, 2, "X")
    assert list(df.t) == [2000, 2001, 2002]       # 2003-2004 en el estado; 2005 y 2006 sin t + 2
    assert list(df[df.y == 1].t) == [2001, 2002]
    assert set(df.E.dropna()) == {2003}


def test_episodios_agrupa_años_seguidos():
    assert S.episodios([1907, 1908, 1914, 1920, 1921, 1922], 1) == 3
    meses = [pd.Period(x, "M") for x in ("1974-01", "1974-05", "1980-01")]
    assert S.episodios(meses, 6) == 2


def test_codificar_compartir_une_tareas():
    df = pd.DataFrame({"pais": ["A", "B", "A", "B"], "t": [1, 1, 1, 2], "y": [0, 1, 1, 0], "tarea": ["x", "x", "z", "z"]})
    _, _, iu, _ = S.codificar(df)
    _, _, iu_c, _ = S.codificar(df, compartir=True)
    assert len(set(iu)) == 4 and len(set(iu_c)) == 2


def test_simular_tamaño_y_potencia_creciente():
    rng = np.random.default_rng(1)
    filas = []
    for c in range(10):
        for t in range(60):
            filas.append({"pais": str(c), "t": t, "y": int(rng.random() < 0.15)})
    df = pd.DataFrame(filas)
    r = S.simular(df, 0.5, 0.2, 0.9, 60, rng, deltas=[0.0, 0.03, 0.10])
    p = [r["por_delta"][k]["pot_auc"] for k in ("0.00", "0.03", "0.10")]
    assert p[0] <= 0.1 and p[2] > p[0] and p[2] >= 0.8
    assert r["por_delta"]["0.10"]["dlogloss_medio"] < 0     # mejor AUC y bien calibrado → menos log-loss


def test_solape_objetivos_cuenta_coincidencias():
    a = pd.DataFrame({"pais": ["A", "A", "B"], "t": [1, 5, 1], "y": [1, 1, 1], "E": [2, 6, 2]})
    b = pd.DataFrame({"pais": ["A", "B"], "t": [2, 9], "y": [1, 1], "E": [3, 10]})
    r = S.solape_objetivos({"a": a, "b": b}, ventana=1)
    assert r["pares"]["a~b"]["pct_de_A_con_B"] == round(1 / 3, 3)
    assert r["eventos_suma"] == 5 and r["pais_años_union"] == 5
