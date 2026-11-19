"""Tabla «Competición» del panel (src/report/panel_competicion.py; spec C1 v1.0 §4). Sin red: el panel en tests no
llama a Alpaca (FIN_PANEL_SIN_ALPACA=1, tests/conftest.py); las series de las cuentas se inyectan."""
from __future__ import annotations

import json
import math

import pandas as pd
import pytest

from src.report import panel as PN
from src.report import panel_competicion as PC

VAL = {"b0": {"desde": "2026-11", "hasta": "2027-04", "meses": 6, "rent_acumulada": 0.06, "vol_anual": 0.10,
              "caida_max": -0.03, "rotacion": 0.05, "costes": 0.0001},
       "b1": {"desde": "2026-11", "hasta": "2027-04", "meses": 6, "rent_acumulada": 0.04, "vol_anual": 0.08,
              "caida_max": -0.02, "rotacion": 0.20, "costes": 0.0003},
       "b1p": {"nota": "sin decisiones registradas"}}


def test_metricas_serie():
    v = pd.Series([100, 110, 99, 120], index=pd.date_range("2027-01-01", periods=4))
    m = PC.metricas_serie(v)
    r = v.pct_change().dropna()
    assert m["rent"] == pytest.approx(0.2) and m["caida"] == pytest.approx(99 / 110 - 1)
    assert m["vol"] == pytest.approx(r.std() * math.sqrt(252))
    assert m["sharpe"] == pytest.approx(r.mean() / r.std() * math.sqrt(252))
    assert PC.metricas_serie(pd.Series([100.0]))["rent"] is None


def test_fila_teorica_sharpe_anualizado():
    f = PC.fila_teorica(VAL["b0"])
    assert f["sharpe"] == pytest.approx(((1.06) ** 2 - 1) / 0.10) and f["operaciones"] is None
    assert PC.fila_teorica(VAL["b1p"]) is None and PC.fila_teorica(None) is None


def test_sin_registros_todo_sin_datos(tmp_path):
    d = PC.recoger({}, con_alpaca=False, log_c1=tmp_path / "no", log_d1=tmp_path / "no2", espejo=[])
    assert all(v is None for v in d["teoricos"].values()) and all(v is None for v in d["cuentas"].values())
    h = PC.html_competicion(d)
    assert "Competición" in h and "habilidad de suerte" in h and h.count("sin datos") >= 8 * 8
    for nombre in ("B0", "B1", "B1′", "D1", "C1"):
        assert nombre in h


def test_cuentas_desde_el_inicio_comun_con_operaciones_y_coste_claude(tmp_path):
    dias = pd.date_range("2027-01-04", periods=30, freq="B")
    series = {"B1": pd.Series(range(100_000, 100_030), index=dias, dtype=float),
              "C1": pd.Series([100_000 + 50 * (i % 3) for i in range(20)], index=dias[10:], dtype=float)}
    espejo = [{"tipo": "ejecucion", "cartera": "B1", "ts": "2027-01-04T15:00:00+00:00", "qty_ejecutada": 10,
               "precio_medio": 100, "deslizamiento_pb_vs_ref": 5},
              {"tipo": "ejecucion", "cartera": "B1", "ts": "2027-02-01T15:00:00+00:00", "qty_ejecutada": 100,
               "precio_medio": 100, "deslizamiento_pb_vs_ref": 10}]
    c1 = tmp_path / "c1.jsonl"
    c1.write_text("\n".join(json.dumps(x) for x in [
        {"fecha": str(dias[10].date()), "claude": {"coste_usd": 0.5},
         "ejecuciones": [{"orden_id": "a", "qty_ejecutada": 1, "precio_medio": 500, "valor_usd": 500, "estado": "new"}]},
        {"fecha": str(dias[11].date()), "claude": {"coste_usd": 0.25}, "ejecuciones": [],
         "seguimiento_previo": [{"orden_id": "a", "qty_ejecutada": 2, "precio_medio": 500, "valor_usd": 1000,
                                 "estado": "filled"}]},
        {"fecha": "2027-01-01", "ensayo": True}]) + "\n")
    d = PC.recoger({"paper": {"valoracion": VAL}}, con_alpaca=True, log_c1=c1, log_d1=tmp_path / "no",
                   espejo=espejo, series=series)
    assert d["inicio_cuentas"] == str(dias[10].date())
    b1, c = d["cuentas"]["B1"], d["cuentas"]["C1"]
    assert b1["desde"] == c["desde"] == str(dias[10].date())                       # inicio común
    assert b1["operaciones"] == 1                                                  # la de enero queda fuera
    assert b1["costes"] == pytest.approx(10_000 * 10 / 1e4 / series["B1"][dias[10]:].mean())
    assert c["operaciones"] == 1 and c["rotacion"] == pytest.approx(1000 / series["C1"].mean())  # orden contada una vez
    assert c["coste_claude_usd"] == pytest.approx(0.75)
    assert d["cuentas"]["D1"] is None and d["cuentas"]["B0"] is None
    assert d["teoricos"]["b0"]["rent"] == 0.06 and d["teoricos"]["b1p"] is None
    h = PC.html_competicion(d)
    assert "0,75 $" in h and "inicio común" in h


def test_panel_engancha_la_competicion_en_mi_cartera_sin_alpaca(monkeypatch):
    def prohibido(*a, **k):
        raise AssertionError("el panel en tests no llama a Alpaca")
    monkeypatch.setattr(PC, "clientes_por_cartera", prohibido)
    h = PN.construir({"asof": "2026-11-17", "paper": {"valoracion": VAL}})
    cartera = h[h.index('<section id="cartera"'):h.index('<section id="estado"')]
    assert 'id="competicion"' in cartera and "habilidad de suerte" in cartera
    assert "FIN_PANEL_SIN_ALPACA=1" in cartera
