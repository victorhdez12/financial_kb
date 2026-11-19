"""S1 en vivo: decisión mensual (src/paper/s1.py, scripts/paper_decision_s1.py) y espejo Alpaca PAPER de S1
(src/broker/espejo.py + config/alpaca_etfs_s1.json). Sin red (transporte simulado de tests/test_alpaca.py), sin
claves reales y sin tocar ningún registro real (research/paper/decisiones*.jsonl)."""
from __future__ import annotations

import json

import duckdb
import pandas as pd
import pytest

from scripts import paper_decision_s1 as P
from src.broker import alpaca as A
from src.broker import espejo as E
from src.factors import s1 as M
from src.paper import s1 as S
from tests.test_alpaca import KEY, SECRET, Falso, aislado, cred, env_file, logs_tmp  # noqa: F401 (aislado = fixture)

C = pd.Timestamp("2026-11-30")
PRECIOS = {"VTI": 300.0, "XLK": 250.0, "XLY": 200.0, "XRT": 80.0, "XLF": 50.0, "XLE": 90.0, "XLB": 88.0,
           "XLI": 140.0, "XLU": 80.0, "XLP": 80.0, "XLV": 150.0, "XLC": 100.0}


@pytest.fixture(autouse=True)
def registros_reales_intactos():
    rutas = [E.LOG_B1, E.LOG_B1P, E.LOG_S1, S.LOG, S.ACTIVO_S1]
    antes = {p: (p.read_bytes() if p.exists() else None) for p in rutas}
    yield
    assert {p: (p.read_bytes() if p.exists() else None) for p in rutas} == antes


def diaria(q="Goldilocks"):
    return {"quadrant": q, "G": 0.1, "G_state": "up", "I_state": "down", "vintage_mode": "alfred",
            "cutoff": str(C.date())}


# --------------------------------------------------------------------------- decisión (pura)
def test_arranque_cambio_y_sin_cambio():
    d0 = S.decidir(C, diaria("Goldilocks"), [])
    assert d0.opera and d0.motivo == "arranque" and d0.s1 == {"mkt": 0.5, "BusEq": 0.125, "Durbl": 0.125,
                                                                 "Shops": 0.125, "Money": 0.125}
    prev = [json.loads(json.dumps(d0.__dict__))]
    d1 = S.decidir(C + pd.offsets.MonthEnd(1), diaria("Goldilocks"), prev)
    assert not d1.opera and d1.s1 == d0.s1 and d1.vigente == "Goldilocks"
    d2 = S.decidir(C + pd.offsets.MonthEnd(1), diaria("Estanflación"), prev)
    assert d2.opera and set(d2.s1) == {"mkt", "Enrgy", "Utils", "NoDur", "Hlth"} and "→" in d2.motivo
    for q in M.SECTORES:                                   # mismos pesos que el desarrollo
        assert S.pesos(q) == {k: v for k, v in M.objetivo(q).items() if v > 0}


def test_sin_cuadrante():
    with pytest.raises(S.SinCuadrante):
        S.decidir(C, diaria(None), [])
    prev = [{"vigente": "Reflación", "s1": S.pesos("Reflación")}]
    d = S.decidir(C, diaria(None), prev)
    assert not d.opera and d.vigente == "Reflación" and d.s1 == S.pesos("Reflación")
    with pytest.raises(ValueError):
        S.decidir(C, diaria("Other"), [])


def _con(cutoff):
    con = duckdb.connect(":memory:")
    con.execute("create table regime_monthly (date date, quadrant varchar, G double, G_state varchar, "
                "I_state varchar, vintage_mode varchar, cutoff timestamp)")
    con.execute("insert into regime_monthly values (?, 'Reflación', 0.3, 'up', 'up', 'alfred', ?)", [C.date(), cutoff])
    con.execute("create table regime_meta as select '{}' as meta_json, current_timestamp as built_at")
    return con


def test_fila_diaria_exige_corte_del_cierre():
    assert S.fila_diaria(_con(C), C)["quadrant"] == "Reflación"
    with pytest.raises(S.SinCuadrante):
        S.fila_diaria(_con(pd.Timestamp("2026-11-20")), C)       # diaria anterior al cierre
    with pytest.raises(S.SinCuadrante):
        S.fila_diaria(_con(C), C + pd.offsets.MonthEnd(1))


def test_registrar_valida_pesos(tmp_path):
    ruta = tmp_path / "decisiones_s1.jsonl"
    d = S.decidir(C, diaria("Goldilocks"), [])
    S.registrar(d, {"registrado": "x"}, ruta)
    (fila,) = S.leer_registro(ruta)
    assert fila["opera"] and fila["vigente"] == "Goldilocks" and fila["registrado"] == "x"
    d.s1 = {"mkt": 0.6, "BusEq": 0.4}
    with pytest.raises(ValueError):
        S.registrar(d, {}, ruta)


# --------------------------------------------------------------------------- script
def test_script_ensayo_no_escribe(capsys):
    assert P.main(["--cierre", str(C.date())], con=_con(C)) == 0
    assert '"vigente": "Reflación"' in capsys.readouterr().out


def test_script_registrar_exige_s1_activo(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "LOG", tmp_path / "decisiones_s1.jsonl")
    monkeypatch.setattr(S, "ACTIVO_S1", tmp_path / "S1_ACTIVO")
    monkeypatch.setattr(P, "validar_s1", lambda *a: None)
    assert P.main(["--registrar"], con=_con(C)) == 6
    assert not (tmp_path / "decisiones_s1.jsonl").exists()


def test_script_auto_antes_del_arranque(monkeypatch):
    monkeypatch.setattr(P, "PRIMER_CIERRE", pd.Timestamp("2100-01-31"))
    assert P.main(["--auto", "--registrar"], con=_con(C)) == 0
    with pytest.raises(P.MesNoValido):
        P.validar_s1(pd.Timestamp("2026-10-31"), pd.Timestamp("2026-11-03"), [])


def test_no_enganchado_a_launchd():
    from pathlib import Path
    sh = (Path(P.__file__).parent / "paper_mensual.sh").read_text()
    assert "paper_decision_s1" not in sh


# --------------------------------------------------------------------------- espejo
def logs_s1(tmp_path, opera=True, q="Goldilocks") -> dict:
    L = logs_tmp(tmp_path)
    s1 = tmp_path / "decisiones_s1.jsonl"
    s1.write_text(json.dumps({"cierre": "2026-11-30", "vigente": q, "opera": opera, "s1": S.pesos(q)}) + "\n")
    return {**L, "S1": (s1, "s1")}


def test_mapeo_s1_es_el_de_la_spec():
    m = E.mapeo_de("S1")
    assert m["version"].startswith("s1-") and m != A.cargar_mapeo()
    assert A.simbolos_mapeo(m) == {"mkt": "VTI", "BusEq": "XLK", "Durbl": "XLY", "Shops": "XRT", "Money": "XLF",
                                   "Enrgy": "XLE", "Chems": "XLB", "Manuf": "XLI", "Utils": "XLU", "NoDur": "XLP",
                                   "Hlth": "XLV", "Telcm": "XLC"}
    assert set(A.simbolos_mapeo(m)) == set(M.ACTIVOS) - {"Other"}
    for c in ("B0", "B1", "B1P", "B1′"):                     # B0/B1/B1′ siguen con su mapeo
        assert E.mapeo_de(c) == A.cargar_mapeo()


def test_decision_s1_lleva_opera_y_b1_no(tmp_path):
    L = logs_s1(tmp_path, opera=False)
    d = E.decision("S1", logs=L)
    assert d["opera"] is False and d["pesos"]["mkt"] == 0.5
    assert "opera" not in E.decision("B1", logs=L)


def test_plan_s1_arranque_compra_los_etf(tmp_path):
    f = Falso(precios=PRECIOS)
    c = A.Cliente(cred(perfil="S1"), transporte=f)
    p = E.plan(c, "S1", logs=logs_s1(tmp_path))
    assert p["mapeo_version"].startswith("s1-")
    compras = {o.simbolo: o for o in p["ordenes"]}
    assert set(compras) == {"VTI", "XLK", "XLY", "XRT", "XLF"} and all(o.lado == "buy" for o in compras.values())
    assert compras["VTI"].valor_estimado == pytest.approx(0.5 * 99_500, rel=1e-3)
    assert compras["XLK"].valor_estimado == pytest.approx(0.125 * 99_500, rel=1e-3)


def test_plan_s1_sin_cambio_no_opera_salvo_cuenta_vacia(tmp_path):
    pos = [{"symbol": "VTI", "qty": "170"}, {"symbol": "XLK", "qty": "40"}]
    f = Falso(precios=PRECIOS, posiciones=pos)
    c = A.Cliente(cred(perfil="S1"), transporte=f)
    p = E.plan(c, "S1", logs=logs_s1(tmp_path, opera=False))
    assert p["ordenes"] == [] and "sin cambio" in p["resumen"]["sin_operar"]
    # cuenta vacía (arranque del espejo): construye aunque el mes no opere
    c2 = A.Cliente(cred(perfil="S1"), transporte=Falso(precios=PRECIOS))
    assert E.plan(c2, "S1", logs=logs_s1(tmp_path, opera=False))["ordenes"]
    # cambio de cuadrante con posiciones: vende lo que sale, compra lo que entra
    p3 = E.plan(A.Cliente(cred(perfil="S1"), transporte=Falso(precios=PRECIOS, posiciones=pos)), "S1",
                logs=logs_s1(tmp_path, opera=True, q="Deflación/recesión"))
    lados = {o.simbolo: o.lado for o in p3["ordenes"]}
    assert lados["XLK"] == "sell" and lados["XLC"] == "buy" and lados["XLP"] == "buy"


def test_dry_run_s1_no_envia(tmp_path, monkeypatch, capsys):
    env_file(tmp_path, f"ALPACA_API_KEY_ID_S1={KEY}\nALPACA_API_SECRET_KEY_S1={SECRET}\n")
    f = Falso(precios=PRECIOS)
    monkeypatch.setattr(A, "_transporte_requests", f)
    monkeypatch.setattr(E, "CARTERAS", logs_s1(tmp_path))
    assert E.main(["--cartera", "S1", "--dry-run"]) == 0
    assert not [x for x in f.llamadas if x[0] == "POST"]
    (plan,) = E.leer_registro()
    assert plan["cartera"] == "S1" and plan["dry_run"] and plan["mapeo_version"].startswith("s1-")
    out = capsys.readouterr().out
    assert KEY not in out and SECRET not in out


def test_una_cuenta_una_cartera_s1():
    assert E.puede_ejecutar(cred(perfil="S1"), "S1", "h", []) is None
    assert "es de la cartera S1" in E.puede_ejecutar(cred(perfil="S1"), "B1", "h", [])
    assert "ya se usó" in E.puede_ejecutar(cred(perfil="S1"), "S1", "h",
                                           [{"tipo": "orden", "cartera": "B1", "cuenta_huella": "h"}])
