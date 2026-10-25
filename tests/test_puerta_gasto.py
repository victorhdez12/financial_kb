"""Puerta de gasto (tests/validation/puerta_gasto.py) con artefactos SINTÉTICOS en el formato real: predicciones
inventadas para todos los modelos de las configuraciones reales (pool_dev, pool_m1cmp, pool_pesos_*, m2_long,
m3_long), puntuadas con `harness.score` y registradas con `trials.record` (report.json, scores.parquet y la línea de
harness_runs.jsonl) en un directorio temporal. Sin datos ni etiqueta reales.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src.models import harness as H
from src.models import metrics as M
from src.models import regime_components as C
from tests.validation import puerta_gasto as PG

LOW_G = [("1980-02", "1980-08"), ("1981-08", "1982-11"), ("1990-08", "1991-04"), ("2001-03", "2001-12")]
IDX = pd.date_range("1956-10-01", "2004-12-01", freq="MS")


def _label():
    tg = pd.Series(0.92, index=IDX)
    for a, b in LOW_G:
        tg[a + "-01":b + "-01"] = 0.08
    ti = pd.Series(0.25, index=IDX)
    P = M.combine_axes(tg.to_numpy(), ti.to_numpy())
    lab = pd.DataFrame(P, index=IDX, columns=M.P_COLS)
    lab["label_hard"] = [M.QUADS[i] for i in P.argmax(axis=1)]
    lab["weight"], lab["provisional"], lab["frontera"] = 1.0, False, False
    lab["usrec"] = (tg < 0.5).astype(float)
    return lab, tg, ti


def _pg(model, tg, rng):
    lag = tg.shift(5).bfill()
    m0 = 0.85 * lag + 0.15 * 0.8
    m2 = (0.75 * tg + 0.25 * m0 + rng.normal(0, 0.04, len(tg))).clip(0.02, 0.98)
    m3 = (0.6 * tg + 0.4 * m0 + rng.normal(0, 0.05, len(tg))).clip(0.02, 0.98)
    base = {"m0_calibrated_persistence": m0, "m2_struct_g": m2, "m3_tvtp_g": m3,
            "m3_ctp_g": (0.9 * m0 + 0.1 * 0.8), "pool_g": 0.4 * m0 + 0.4 * m2 + 0.2 * m3,
            "persistence_pit": lag.clip(0.01, 0.99), "climatology": pd.Series(0.8, index=tg.index)}
    if model in base:
        return pd.Series(np.asarray(base[model], float), index=tg.index)
    return (m0 + rng.normal(0, 0.02, len(tg))).clip(0.02, 0.98)       # variantes, M1…: cerca de M0


def _registrar(name, monkeypatch, tmp_path, seed=0):
    from src.models import trials
    cfg = H.HarnessConfig.from_yaml(H.REPO / "config" / "harness" / f"{name}.yaml")
    lab, tg, ti = _label()
    rng = np.random.default_rng(seed)
    rows = []
    for mode in cfg.modes:
        for model in cfg.models:
            pg = _pg(model, tg, rng)
            P = M.combine_axes(pg.to_numpy(), ti.to_numpy())
            df = pd.DataFrame(P, columns=M.P_COLS)
            df.insert(0, "month", IDX)
            df.insert(0, "refit_month", IDX)
            df.insert(0, "model", model)
            df.insert(0, "mode", mode)
            rows.append(df)
    preds = pd.concat(rows, ignore_index=True)
    labels = {m: lab for m in cfg.modes}
    S, rep = H.score(preds, labels, cfg)
    w0, w1 = cfg.window
    months = pd.date_range(w0, w1, freq="MS")
    diag = {m: [] for m in cfg.modes}
    for mode in cfg.modes:
        for i, m0 in enumerate(months):
            if "pool_g" in cfg.models:
                wm0 = 0.6 - 0.25 * i / len(months)
                diag[mode].append({"model": "pool_g", "refit_month": m0,
                                   "coef": {"G:w_m0": wm0, "G:w_m2": (1 - wm0) * 0.65, "G:w_m3": (1 - wm0) * 0.35,
                                            "G:blp_a": 1.2, "G:blp_b": 1.1, "G:n_est": 60.0 + i}})
            if "m3_tvtp_g" in cfg.models:
                diag[mode].append({"model": "m3_tvtp_g", "refit_month": m0,
                                   "coef": {"G:gamma1": 0.3, "G:gamma2": 0.02 if i % 2 else 0.0,
                                            "G:gamma3": 0.0, "G:gamma4": 0.05}})
    if cfg.sign_fraction:
        coefs = pd.DataFrame({m["refit_month"]: m["coef"] for m in diag["vintage"]
                              if m["model"] == "m3_tvtp_g"}).T
        rep.setdefault("signos_coeficientes", {})["vintage/m3_tvtp_g"] = C.gamma_fraction_criterion(coefs, months)
    from dataclasses import asdict
    res = {"config": asdict(cfg), "preds": preds, "scores": S, "report": rep, "diag": diag,
           "results_sha256": H.results_hash(preds, rep), "results_sha256_r10": H.results_hash(preds, rep, 10),
           "kind": ["synthetic"], "data_hashes": {}}
    return trials.record(res)["run_id"]


@pytest.fixture(scope="module")
def artefactos(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    d = tmp_path_factory.mktemp("puerta")
    mp.setenv("FKB_RUNS_DIR", str(d / "runs"))
    mp.setenv("FKB_TRIALS_DIR", str(d / "trials"))
    mp.setenv("FKB_TRIAL_LOG", str(d / "trial_log.md"))
    ids = {k: _registrar(PG.NAMES[k], mp, d, seed=i) for i, k in enumerate(PG.NAMES)}
    yield ids, d
    mp.undo()


def test_puerta_reads_synthetic_artifacts_in_the_real_format(artefactos, tmp_path):
    ids, d = artefactos
    res = PG.lectura(ids, d / "runs", d / "trials" / "harness_runs.jsonl")
    rs = res["pool_frente_a_M0"]["pool_dev"]
    assert rs["disponible"] and rs["mejora"] > 0 and rs["ic95"][0] <= rs["mejora"] <= rs["ic95"][1]
    assert set(rs["subperiodos"]) == {"1985-01→1994-12", "1995-01→2004-12"}
    sd = res["sd_mensual_d"]["pool_dev"]
    assert {"pool_g", "m2_struct_g", "m3_tvtp_g", "m3_ctp_g", "ratio_pool_m2"} <= set(sd)
    tr = res["trayectoria_pesos"]["pool_dev"]
    assert len(tr) == 240 and tr[-1]["corte"] == "2004-12"
    p = res["predicciones_estratega"]
    assert p["P4"]["pool_g"]["estado"] == "se cumple" and p["P4"]["m2_struct_g"]["entrada"] > 0
    assert p["P1"]["m2_struct_g"]["estado"] != "no evaluable"          # con m2_long y m3_long
    assert p["P11"]["corte"] == "2004-12" and p["P11"]["estado"] == "se cumple"
    assert set(p["P10"]["fracciones"]) == {f"G:gamma{j}" for j in range(1, 5)} and p["P10"]["gamma3_lt_0_5"]
    assert res["puerta_de_gasto"]["lectura"].startswith(("se recomienda NO", "la puerta no desaconseja"))
    md = PG.markdown(res)
    assert "Puerta de gasto" in md and "P8" in md
    json.dumps(res, default=float)


def test_puerta_without_m2_m3_long_marks_1980_as_not_evaluable(artefactos):
    ids, d = artefactos
    sub = {k: v for k, v in ids.items() if k.startswith("pool")}
    res = PG.lectura(sub, d / "runs", d / "trials" / "harness_runs.jsonl")
    assert res["predicciones_estratega"]["P1"]["m2_struct_g"]["estado"] == "no evaluable"
    assert res["predicciones_estratega"]["P2"]["estado"] == "no evaluable"


def test_puerta_stops_on_tampered_or_unregistered_artifacts(artefactos, tmp_path):
    ids, d = artefactos
    hr = d / "trials" / "harness_runs.jsonl"
    with pytest.raises(PG.Integridad):
        PG.lectura({**ids, "pool_dev": "20990101-000000_pool_dev_deadbeef"}, d / "runs", hr)
    with pytest.raises(PG.Integridad):
        PG.lectura({**ids, "pool_dev": ids["pool_uno"]}, d / "runs", hr)      # run de otra configuración
    sp = d / "runs" / ids["pool_m1cmp"] / "scores.parquet"
    S = pd.read_parquet(sp)
    S.loc[S.index[0], "logloss"] += 0.01
    S.to_parquet(sp, index=False)
    with pytest.raises(PG.Integridad):
        PG.lectura(ids, d / "runs", hr)
