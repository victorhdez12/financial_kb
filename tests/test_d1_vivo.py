"""D1 en vivo: decisión diaria (src/paper/d1.py, scripts/paper_decision_d1.py) y espejo Alpaca PAPER de D1
(src/broker/espejo.py + config/alpaca_etfs_d1.json). Precios sintéticos, sin red (transporte simulado de
tests/test_alpaca.py), sin claves reales y sin tocar ningún registro real."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts import paper_decision_d1 as P
from src.broker import alpaca as A
from src.broker import espejo as E
from src.factors import d1 as M
from src.paper import d1 as D
from tests.test_alpaca import KEY, SECRET, Falso, aislado, cred, env_file, logs_tmp  # noqa: F401 (aislado = fixture)

DIAS = pd.bdate_range(end="2026-11-20", periods=300)
C = DIAS[-1]
PRECIOS = {"SPY": 600.0, "VEA": 55.0, "TLT": 90.0, "GLD": 250.0, "DBC": 22.0}


@pytest.fixture(autouse=True)
def registros_reales_intactos():
    rutas = [E.LOG_B1, E.LOG_B1P, E.LOG_S1, E.LOG_D1, D.LOG, D.ACTIVO_D1]
    antes = {p: (p.read_bytes() if p.exists() else None) for p in rutas}
    yield
    assert {p: (p.read_bytes() if p.exists() else None) for p in rutas} == antes


def precios(tend=(0.0008, 0.0004, -0.0006, 0.0005, -0.0010), semilla=0) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    r = rng.normal(0, 0.01, (len(DIAS), 5)) + np.array(tend)
    return pd.DataFrame(100 * np.cumprod(1 + r, axis=0), index=DIAS, columns=list(D.TRAMOS))


# --------------------------------------------------------------------------- decisión (pura)
def test_arranque_usa_la_misma_regla_que_el_desarrollo():
    p = precios()
    d = D.decidir(C, p, [], "test")
    r = p.pct_change().iloc[1:]
    obj = M.objetivo(M.tendencia(r).iloc[-1], M.volatilidad(r).iloc[-1])
    assert d.opera and d.motivo == "arranque"
    assert d.objetivo == pytest.approx({k: round(v, 6) for k, v in obj.items()})
    assert d.d1 == d.objetivo and sum(d.d1.values()) <= 1 + 1e-9 and max(d.d1.values()) <= M.TOPE + 1e-9
    assert set(d.s.values()) <= {0.0, round(1 / 3, 6), round(2 / 3, 6), 1.0}


def test_segunda_sesion_deriva_y_banda():
    p = precios()
    d0 = D.decidir(DIAS[-2], p, [], "test")
    prev = [json.loads(json.dumps(d0.__dict__))]
    d1 = D.decidir(C, p, prev, "test")
    assert d1.ultimo_cierre_previo == str(DIAS[-2].date())
    assert d1.actual == pytest.approx(D.deriva(d0.d1, p.dropna(), d0.cierre, C), abs=1e-6)
    for k in D.TRAMOS:                                  # cada activo: o cruza la banda (va al objetivo) o se queda
        cruza = abs(d1.objetivo[k] - d1.actual[k]) >= M.BANDA - 1e-12
        assert d1.d1[k] == pytest.approx(d1.objetivo[k] if cruza else d1.actual[k], abs=1e-6) or \
            sum(d1.d1.values()) == pytest.approx(sum(d1.objetivo.values()), abs=1e-6)
    with pytest.raises(ValueError):
        D.decidir(DIAS[-2], p, [json.loads(json.dumps(d1.__dict__))], "test")      # nunca hacia atrás


def test_deriva_con_efectivo_a_cero():
    p = pd.DataFrame({"a": [100.0, 110.0], "b": [50.0, 50.0]}, index=DIAS[:2])
    w = D.deriva({"a": 0.5, "b": 0.2}, p, str(DIAS[0].date()), DIAS[1])
    assert w["a"] == pytest.approx(0.55 / 1.05) and w["b"] == pytest.approx(0.2 / 1.05)


def test_sin_datos_falla_cerrado():
    p = precios()
    with pytest.raises(D.SinDatos):
        D.decidir(C + pd.Timedelta(days=3), p, [], "test")           # la última barra no es la del cierre
    with pytest.raises(D.SinDatos):
        D.decidir(C, p.iloc[-200:], [], "test")                      # historia corta
    q = p.copy()
    q.loc[C, "oro"] = np.nan
    with pytest.raises(D.SinDatos):
        D.decidir(C, q, [], "test")


def test_registrar_valida_pesos(tmp_path):
    ruta = tmp_path / "decisiones_d1.jsonl"
    d = D.decidir(C, precios(), [], "test")
    D.registrar(d, {"registrado": "x"}, ruta)
    (fila,) = D.leer_registro(ruta)
    assert fila["cierre"] == str(C.date()) and fila["registrado"] == "x"
    d.d1 = {k: 0.3 for k in D.TRAMOS}
    with pytest.raises(ValueError):
        D.registrar(d, {}, ruta)


def test_cierres_alpaca_pide_ajustado_y_pagina():
    class Cli:
        llamadas = []

        def _pide(self, metodo, base, ruta, params):
            self.llamadas.append(params)
            if "page_token" not in params:
                return {"bars": {"SPY": [{"t": "2026-11-19T05:00:00Z", "c": 1.0}]}, "next_page_token": "t2"}
            return {"bars": {s: [{"t": "2026-11-20T05:00:00Z", "c": 2.0}] for s in PRECIOS}, "next_page_token": None}
    c = Cli()
    df = D.cierres_alpaca(c, pd.Timestamp("2026-01-01").date(), C.date())
    assert all(x["adjustment"] == "all" and x["feed"] == "iex" for x in c.llamadas) and len(c.llamadas) == 2
    assert list(df.columns) == list(D.TRAMOS) and df.loc["2026-11-19", "us"] == 1.0 and np.isnan(df.loc["2026-11-19", "oro"])


# --------------------------------------------------------------------------- script
def test_ultima_sesion_cerrada():
    cal = [{"date": "2026-11-19", "close": "16:00"}, {"date": "2026-11-20", "close": "16:00"}]
    abierto = {"timestamp": "2026-11-20T11:00:00-05:00", "is_open": True}
    tarde = {"timestamp": "2026-11-20T16:30:00-05:00", "is_open": False}
    temprano = {"timestamp": "2026-11-20T08:00:00-05:00", "is_open": False}
    assert P.ultima_sesion_cerrada(abierto, cal) == pd.Timestamp("2026-11-19")
    assert P.ultima_sesion_cerrada(tarde, cal) == pd.Timestamp("2026-11-20")
    assert P.ultima_sesion_cerrada(temprano, cal) == pd.Timestamp("2026-11-19")
    sab = {"timestamp": "2026-11-21T16:30:00-05:00", "is_open": False}
    assert P.ultima_sesion_cerrada(sab, cal) == pd.Timestamp("2026-11-20")


def test_validar_d1():
    P.validar_d1(C, C, [])
    with pytest.raises(P.MesNoValido):
        P.validar_d1(C, C + pd.Timedelta(days=3), [])
    with pytest.raises(P.YaRegistrado):
        P.validar_d1(C, C, [str(C.date())])
    with pytest.raises(P.MesNoValido):
        P.validar_d1(pd.Timestamp("2026-11-19"), pd.Timestamp("2026-11-19"), [])     # antes del arranque


class CliFalso:
    def reloj(self):
        return {"timestamp": "2026-11-20T16:30:00-05:00", "is_open": False}

    def calendario(self, desde, hasta):
        return [{"date": "2026-11-19", "close": "16:00"}, {"date": "2026-11-20", "close": "16:00"}]


def test_script_ensayo_no_escribe(capsys):
    assert P.main([], cliente=CliFalso(), precios=precios()) == 0
    assert f'"cierre": "{C.date()}"' in capsys.readouterr().out


def test_script_registrar_exige_d1_activo(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "LOG", tmp_path / "decisiones_d1.jsonl")
    monkeypatch.setattr(D, "ACTIVO_D1", tmp_path / "D1_ACTIVO")
    assert P.main(["--registrar"], cliente=CliFalso(), precios=precios()) == 6
    assert not (tmp_path / "decisiones_d1.jsonl").exists()
    assert P.main(["--registrar", "--fuente", "archivo"], precios=precios()) == 4


def test_script_registrar_exige_arbol_limpio(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "LOG", tmp_path / "decisiones_d1.jsonl")
    monkeypatch.setattr(D, "ACTIVO_D1", tmp_path / "D1_ACTIVO")
    (tmp_path / "D1_ACTIVO").write_text("")
    monkeypatch.setattr(P, "git", lambda *a: " M algo")
    assert P.main(["--registrar"], cliente=CliFalso(), precios=precios()) == 5
    assert not (tmp_path / "decisiones_d1.jsonl").exists()


def test_plist_no_instalado_y_horario():
    pl = Path(P.__file__).parent / "launchd" / "com.financialkb.d1.plist"
    t = pl.read_text()
    assert "paper_decision_d1 --auto --registrar" in t and "<integer>22</integer>" in t and "<integer>30</integer>" in t
    # 20-nov-2026: D1 solo en papel — el plist ya no lanza el espejo ni pide ejecución (el instalado lo cambia el usuario)
    assert "src.broker.espejo" not in t and "--ejecutar" not in t and "FIN_ALPACA_EJECUTAR" not in t


# --------------------------------------------------------------------------- espejo
def logs_d1(tmp_path, opera=True, d1=None) -> dict:
    L = logs_tmp(tmp_path)
    f = tmp_path / "decisiones_d1.jsonl"
    w = d1 or {"us": 0.30, "xus": 0.10, "bonos": 0.20, "oro": 0.15, "mp": 0.0}
    f.write_text(json.dumps({"cierre": str(C.date()), "opera": opera, "d1": w}) + "\n")
    return {**L, "D1": (f, "d1")}


def test_mapeo_d1_es_el_de_la_spec():
    m = E.mapeo_de("D1")
    assert m["version"].startswith("d1-") and m["permite_efectivo"] is True
    assert A.simbolos_mapeo(m) == {"us": "SPY", "xus": "VEA", "bonos": "TLT", "oro": "GLD", "mp": "DBC"}
    assert set(A.simbolos_mapeo(m)) == set(D.TRAMOS) and m["ordenes"]["banda_no_operar"] == M.BANDA
    for c in ("B0", "B1", "B1P"):
        assert E.mapeo_de(c) == A.cargar_mapeo()
        assert "permite_efectivo" not in E.mapeo_de(c)


def test_pesos_menores_que_uno_solo_con_permite_efectivo():
    m = E.mapeo_de("D1")
    assert E.pesos_etf({"us": 0.3, "bonos": 0.2}, m)["SPY"] == ("us", 0.3)
    with pytest.raises(ValueError):
        E.pesos_etf({"us": 0.7, "bonos": 0.4}, m)
    with pytest.raises(ValueError):
        E.pesos_etf({"rv": 0.6, "rf": 0.2}, A.cargar_mapeo())             # B0/B1 siguen exigiendo 100 %


def test_plan_d1_arranque_deja_efectivo(tmp_path):
    c = A.Cliente(cred(perfil="D1"), transporte=Falso(precios=PRECIOS))
    p = E.plan(c, "D1", logs=logs_d1(tmp_path))
    compras = {o.simbolo: o for o in p["ordenes"]}
    assert set(compras) == {"SPY", "VEA", "TLT", "GLD"} and all(o.lado == "buy" for o in compras.values())
    assert compras["SPY"].valor_estimado == pytest.approx(0.30 * 99_500, rel=1e-3)
    assert sum(o.valor_estimado for o in compras.values()) < 0.76 * 100_000


def test_plan_d1_banda_y_sin_operar(tmp_path):
    # SPY al 29 % real frente al 30 %: dentro de la banda, no se toca; TLT del 10 % al 20 %: se compra
    pos = [{"symbol": "SPY", "qty": str(29_000 / 600)}, {"symbol": "TLT", "qty": str(10_000 / 90)}]
    f = Falso(precios=PRECIOS, posiciones=pos, cuenta={"id": "x", "account_number": "PA1", "status": "ACTIVE",
                                                          "currency": "USD", "equity": "100000", "cash": "61000"})
    p = E.plan(A.Cliente(cred(perfil="D1"), transporte=f), "D1", logs=logs_d1(tmp_path))
    lados = {o.simbolo: o.lado for o in p["ordenes"]}
    assert "SPY" not in lados and lados["TLT"] == "buy" and lados["VEA"] == "buy"
    assert any(o["simbolo"] == "SPY" for o in p["resumen"]["omitidas"])
    p2 = E.plan(A.Cliente(cred(perfil="D1"), transporte=f), "D1", logs=logs_d1(tmp_path, opera=False))
    assert p2["ordenes"] == [] and "no opera" in p2["resumen"]["sin_operar"]


def test_b1_sin_banda_sigue_igual(tmp_path):
    pos = [{"symbol": "URTH", "qty": str(59_000 / 160)}]
    f = Falso(posiciones=pos, cuenta={"id": "x", "account_number": "PA1", "status": "ACTIVE", "currency": "USD",
                                      "equity": "100000", "cash": "41000"})
    p = E.plan(A.Cliente(cred(perfil="B1"), transporte=f), "B1", logs=logs_tmp(tmp_path))
    assert any(o.simbolo == "URTH" for o in p["ordenes"])        # 1 pp de diferencia: B1 sí rebalancea


def test_dry_run_d1_no_envia(tmp_path, monkeypatch, capsys):
    env_file(tmp_path, f"ALPACA_API_KEY_ID_D1={KEY}\nALPACA_API_SECRET_KEY_D1={SECRET}\n")
    f = Falso(precios=PRECIOS)
    monkeypatch.setattr(A, "_transporte_requests", f)
    monkeypatch.setattr(E, "CARTERAS", logs_d1(tmp_path))
    assert E.main(["--cartera", "D1", "--dry-run"]) == 0
    assert not [x for x in f.llamadas if x[0] == "POST"]
    (plan,) = E.leer_registro()
    assert plan["cartera"] == "D1" and plan["dry_run"] and plan["mapeo_version"].startswith("d1-")
    out = capsys.readouterr().out
    assert KEY not in out and SECRET not in out


def test_una_cuenta_una_cartera_d1():
    assert E.puede_ejecutar(cred(perfil="D1"), "D1", "h", []) is None
    assert "es de la cartera D1" in E.puede_ejecutar(cred(perfil="D1"), "S1", "h", [])
