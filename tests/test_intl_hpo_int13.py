"""Tests SINTÉTICOS de HPO-INT13 (src/intl/hpo_int13.py). Ningún dato real."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.intl import hpo_int13 as H
from src.intl import int13 as M

pytest.importorskip("xgboost")


def _panel(n_paises=6, seed=0):
    rng = np.random.default_rng(seed)
    fechas = pd.date_range("1960-01-31", "2004-12-31", freq="ME")
    filas = []
    for c in [f"P{i}" for i in range(n_paises)]:
        x = rng.standard_normal((len(fechas), 8))
        y = (rng.random(len(fechas)) < 1 / (1 + np.exp(-(-1.5 + 1.2 * x[:, 0])))).astype(float)
        d = pd.DataFrame({"pais": c, "fecha": fechas, "y_E3": y})
        for j, col in enumerate(["ipc_yoy", "tipo_real", "ip_yoy"]):
            d[col] = x[:, j]
        todas = [c for cols in M.PAQUETES.values() for c in cols]
        for j, col in enumerate(dict.fromkeys(todas)):
            if col not in d:
                d[col] = x[:, (j % 5) + 3] if col in M.PAQUETES["P3_actividad"] else rng.standard_normal(len(fechas))
        filas.append(d)
    return pd.concat(filas, ignore_index=True)


def test_configs_deterministas_y_la_0_es_int13():
    a, b = H.muestrear_configs(), H.muestrear_configs()
    assert a == b and len(a) == H.N_CONFIGS
    assert a[0] == H.DEFAULT
    assert a[0]["eta"] == M.XGB_PARAMS["eta"] and a[0]["max_depth"] == M.XGB_PARAMS["max_depth"]
    for c in a[1:]:
        assert 0.02 <= c["eta"] <= 0.3 and c["max_depth"] in (1, 2, 3, 4, 6) and 1 <= c["min_child_weight"] <= 100
        assert 0.5 <= c["subsample"] <= 1 and 0.1 <= c["lambda"] <= 100 and (c["alpha"] == 0 or c["alpha"] >= 0.01)


def test_pliegues_internos_loco_no_tocan_el_pais_externo():
    S = _panel()
    tr = S[S.pais != "P0"].reset_index(drop=True)
    pl = H.pliegues_internos_loco(tr)
    assert len(pl) == H.K_INTERNO
    val = np.concatenate([b for _, b in pl])
    assert sorted(val) == list(range(len(tr)))                 # cada fila valida exactamente una vez
    for a, b in pl:
        assert set(tr.pais.iloc[a]).isdisjoint(set(tr.pais.iloc[b]))
    assert "P0" not in set(tr.pais)


def test_pliegues_internos_temporales_con_embargo():
    S = _panel()
    h = 12
    tr = S[(S.fecha + pd.offsets.MonthEnd(h)) <= M.CORTE_TEMPORAL].reset_index(drop=True)
    for (corte, desde), (a, b) in zip(H.CORTES_V2_INTERNOS, H.pliegues_internos_temporal(tr, h)):
        assert ((tr.fecha.iloc[a] + pd.offsets.MonthEnd(h)) <= pd.Timestamp(corte)).all()
        assert (tr.fecha.iloc[b] >= pd.Timestamp(desde)).all()
        assert tr.fecha.iloc[a].max() < tr.fecha.iloc[b].min()
        assert (tr.fecha.iloc[b] + pd.offsets.MonthEnd(h) <= M.CORTE_TEMPORAL).all()   # nunca toca la prueba V2


def test_default_reproduce_int13_y_elegir():
    S = _panel()
    tr, te = S[S.pais != "P0"], S[S.pais == "P0"]
    cfgs = H.muestrear_configs(3)
    r = H.tarea(tr, te, "E3", "P3_actividad", cfgs, "loco", max_rondas=120)
    p13 = M.ajustar_predecir(tr.reset_index(drop=True), te, "E3")["P3_actividad"]
    assert np.allclose(M._sig(r["z_def"]), p13)
    assert H.MIN_RONDAS <= r["sel"]["rondas"] <= 120 and 0 <= r["sel"]["cfg"] < 3
    assert r["sel"]["ll_interna"] <= min(x["ll_interna"] for x in r["sel"]["por_config"]) + 1e-12


def test_elegir_minimo_y_min_rondas():
    S = np.array([[5.0, 1.0, 3.0, 4.0], [2.0, 2.0, 2.0, 0.5]]) * 10
    e = H.elegir(S, 10, min_rondas=2)
    assert (e["cfg"], e["rondas"]) == (1, 4) and np.isclose(e["ll_interna"], 0.5)
    e = H.elegir(np.array([[0.1, 9.0], [9.0, 9.0]]), 1, min_rondas=2)
    assert e["rondas"] == 2                                    # ronda 1 prohibida


def test_permutar_bloques_conserva_eventos_por_pais_y_rompe_la_senal():
    S = _panel()
    P = H.permutar_bloques(S, "E3", seed=1)
    assert (P.groupby("pais").y_E3.sum() == S.groupby("pais").y_E3.sum()).all()
    assert (P[["pais", "fecha", "ip_yoy"]].to_numpy() == S[["pais", "fecha", "ip_yoy"]].to_numpy()).all()
    assert not np.array_equal(P.y_E3.to_numpy(), S.y_E3.to_numpy())
    c_real = np.corrcoef(S.ipc_yoy, S.y_E3)[0, 1]
    c_perm = np.corrcoef(P.ipc_yoy, P.y_E3)[0, 1]
    assert c_real > 0.2 and abs(c_perm) < 0.08
    assert np.array_equal(H.permutar_bloques(S, "E3", seed=1).y_E3, P.y_E3)


def test_logit_paquete_maneja_nan():
    S = _panel()
    S.loc[S.sample(frac=0.2, random_state=0).index, "sahm"] = np.nan
    tr, te = S[S.pais != "P0"], S[S.pais == "P0"]
    z = H.logit_paquete(tr, te, "E3", M.PAQUETES["P3_actividad"])
    assert np.isfinite(z).all() and len(z) == len(te)
