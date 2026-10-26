"""Tests SINTÉTICOS de src/paper/live.py."""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
import pytest

from src.paper import live as L


def test_regla_b1():
    assert L.rv_b1(0.10, 0.80) == (0.80, 0.80, False)                     # vol baja: sin recorte
    bruta, rv, cambio = L.rv_b1(0.30, 0.80)                               # vol alta: al suelo
    assert bruta == pytest.approx(0.65) and rv == pytest.approx(0.65) and cambio
    bruta, rv, cambio = L.rv_b1(L.SIGMA_STAR / 0.99, 0.80)                # recorte < 2,5 pp: no se mueve
    assert rv == 0.80 and not cambio


def test_rv_eur():
    idx = pd.period_range("2025-01", "2025-03", freq="M")
    sp, fx = pd.Series([100.0, 110.0, 110.0], index=idx), pd.Series([1.0, 1.0, 1.1], index=idx)
    r = L.rv_eur_mensual(sp, fx)
    assert r.iloc[0] == pytest.approx(0.10) and r.iloc[1] == pytest.approx(1 / 1.1 - 1)


def test_decidir_y_dato_viejo(monkeypatch, tmp_path):
    monkeypatch.setattr(L, "LOG", tmp_path / "d.jsonl")
    con = duckdb.connect(":memory:")
    con.execute("create table obs_latest (series_id varchar, date date, value double)")
    dias = pd.bdate_range("2025-09-01", "2026-10-30")
    rng = np.random.default_rng(0)
    sp = 100 * np.exp(np.cumsum(rng.normal(0, 0.03, len(dias))))
    for d, v in zip(dias, sp):
        con.execute("insert into obs_latest values ('SP500', ?, ?), ('ecb_eurusd_d', ?, 1.1)", [d.date(), v, d.date()])
    dec = L.decidir(pd.Timestamp("2026-10-31"), con)                       # vol diaria 3 % → muy alta → suelo
    assert dec.b1["rv"] == pytest.approx(0.65) and dec.cambio_b1 and abs(sum(dec.b1.values()) - 1) < 1e-9
    with pytest.raises(RuntimeError):
        L.decidir(pd.Timestamp("2026-12-31"), con)                         # sin dato reciente
