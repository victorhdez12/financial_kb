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
    series = {"A1": pd.Series(range(100_000, 100_030), index=dias, dtype=float),
              "C1": pd.Series([100_000 + 50 * (i % 3) for i in range(20)], index=dias[10:], dtype=float)}
    a1 = tmp_path / "a1.jsonl"
    a1.write_text("\n".join(json.dumps(x) for x in [
        {"fecha": str(dias[0].date()), "claude": {"coste_usd": 1.0},
         "ejecuciones": [{"orden_id": "x", "qty_ejecutada": 10, "precio_medio": 100, "valor_usd": 1000,
                          "estado": "filled"}]},
        {"fecha": str(dias[15].date()), "claude": {"coste_usd": 1.0},
         "ejecuciones": [{"orden_id": "y", "qty_ejecutada": 100, "precio_medio": 100, "valor_usd": 10_000,
                          "estado": "filled"}]}]) + "\n")
    c1 = tmp_path / "c1.jsonl"
    c1.write_text("\n".join(json.dumps(x) for x in [
        {"fecha": str(dias[10].date()), "claude": {"coste_usd": 0.5},
         "ejecuciones": [{"orden_id": "a", "qty_ejecutada": 1, "precio_medio": 500, "valor_usd": 500, "estado": "new"}]},
        {"fecha": str(dias[11].date()), "claude": {"coste_usd": 0.25}, "ejecuciones": [],
         "seguimiento_previo": [{"orden_id": "a", "qty_ejecutada": 2, "precio_medio": 500, "valor_usd": 1000,
                                 "estado": "filled"}]},
        {"fecha": "2027-01-01", "ensayo": True}]) + "\n")
    d = PC.recoger({"paper": {"valoracion": VAL}}, con_alpaca=True, log_c1=c1, log_d1=tmp_path / "no",
                   espejo=[], series=series, log_a1=a1, log_m1=tmp_path / "no3", log_a1_sombra=tmp_path / "no4")
    assert d["inicio_cuentas"] == str(dias[10].date())
    a, c = d["cuentas"]["A1"], d["cuentas"]["C1"]
    assert a["desde"] == c["desde"] == str(dias[10].date())                        # inicio común
    assert a["operaciones"] == 1 and a["coste_claude_usd"] == pytest.approx(2.0)   # la del primer día queda fuera
    assert c["operaciones"] == 1 and c["rotacion"] == pytest.approx(1000 / series["C1"].mean())  # orden contada una vez
    assert c["coste_claude_usd"] == pytest.approx(0.75)
    assert d["cuentas"]["M1"] is None and d["cuentas"]["D1T"] is None
    assert set(d["cuentas"]) == {"C1", "M1", "A1", "M1S", "A1S", "D1T"}           # sin filas de espejo B0/B1/B1′/D1
    assert d["teoricos"]["b0"]["rent"] == 0.06 and d["teoricos"]["b1p"] is None
    h = PC.html_competicion(d)
    assert "0,75 $" in h and "inicio común" in h and "A1 · Claude selección de acciones" in h


def test_d1_teorico_solo_papel_con_cierres(tmp_path):
    idx = pd.bdate_range("2026-11-20", periods=6)
    px = pd.DataFrame({s: [100.0 * (1.01 if s == "SPY" else 1.0) ** i for i in range(6)]
                       for s in ("SPY", "VEA", "TLT", "GLD", "DBC")}, index=idx)
    reg = [{"cierre": str(idx[0].date()), "d1": {"us": 0.5, "xus": 0.0, "bonos": 0.5, "oro": 0.0, "mp": 0.0}}]
    f = PC.fila_d1_teorica(reg, None, px)
    assert f["operaciones"] == 1 and f["rent"] > 0 and f["desde"] == str(idx[0].date())
    assert PC.fila_d1_teorica([], None, px) is None


def test_clientes_solo_de_las_carteras_gestionadas(monkeypatch):
    from src.broker import alpaca as A
    hechos = {}
    for p in ("", "D1", "C1", "A1", "M1"):
        hechos[p] = A.Cliente(A.Credenciales(key_id=f"PK{p}X", secret="S", perfil=p or None))
    monkeypatch.setattr(A, "perfiles", lambda: list(hechos))
    monkeypatch.setattr(A, "cliente", lambda p=None, **k: hechos.get(p or ""))
    assert set(PC.clientes_por_cartera()) == {"C1", "A1", "M1"}


def test_panel_engancha_la_competicion_en_mi_cartera_sin_alpaca(monkeypatch):
    def prohibido(*a, **k):
        raise AssertionError("el panel en tests no llama a Alpaca")
    monkeypatch.setattr(PC, "clientes_por_cartera", prohibido)
    h = PN.construir({"asof": "2026-11-17", "paper": {"valoracion": VAL}})
    cartera = h[h.index('<section id="cartera"'):h.index('<section id="estado"')]
    assert 'id="competicion"' in cartera and "habilidad de suerte" in cartera
    assert "FIN_PANEL_SIN_ALPACA=1" in cartera


def test_m1_sombra_y_uso_de_modelos(tmp_path):
    dias = pd.date_range("2027-01-04", periods=10, freq="B")
    series = {"M1": pd.Series([100_000 * (1 + 0.01 * (i % 2)) for i in range(10)], index=dias, dtype=float)}
    m1 = tmp_path / "m1.jsonl"
    dec = lambda caso_e1: {"cuadrante": "si", "credito": "parcial", "e1": caso_e1}  # noqa: E731
    m1.write_text("\n".join(json.dumps(x) for x in [
        {"fecha": str(dias[0].date()), "claude": {"coste_usd": 1.0},
         "uso_modelos": {"declaracion": dec("no"), "citas_ordenes": [{"modelos": ["cuadrante", "credito"]}]}},
        {"fecha": str(dias[1].date()), "claude": {"coste_usd": 2.0},
         "uso_modelos": {"declaracion": dec("si"), "citas_ordenes": []}},
        {"fecha": "2027-01-01", "ensayo": True, "uso_modelos": {"declaracion": dec("si")}}]) + "\n")
    sombra = tmp_path / "s.jsonl"
    sombra.write_text("\n".join(json.dumps({"fecha": str(d.date()), "valoracion": {
        "hasta": str(d.date()), "valor": 100_000 + 100 * i, "rotacion": 0.5, "costes": 0.0005, "rebalanceos": 1}})
        for i, d in enumerate(dias)) + "\n")
    d = PC.recoger({}, con_alpaca=True, log_c1=tmp_path / "no", log_d1=tmp_path / "no2", espejo=[], series=series,
                   log_m1=m1, log_m1_sombra=sombra)
    assert d["cuentas"]["M1"]["coste_claude_usd"] == pytest.approx(3.0)
    s = d["cuentas"]["M1S"]
    assert s["rent"] == pytest.approx(900 / 100_000) and s["operaciones"] == 1 and s["coste_claude_usd"] is None
    u = {f["modelo"]: f for f in d["uso_modelos"]}
    assert u["cuadrante"]["dias"] == 2 and u["cuadrante"]["pct_caso"] == 1.0 and u["e1"]["pct_caso"] == 0.5
    assert u["cuadrante"]["ordenes"] == 1 and u["xbrl"]["ordenes"] == 0
    assert u["cuadrante"]["rent_sesion_siguiente"] == pytest.approx(0.01)
    h = PC.html_competicion(d)
    assert "M1 · Claude gestor macro" in h and "sombra teórica" in h and "uso de modelos" in h
