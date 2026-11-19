"""Alpaca PAPER y espejo de ejecución: todo con respuestas simuladas (sin red)."""
from __future__ import annotations

import json
import logging
import os
from urllib.parse import urlparse

import pytest

from src.broker import alpaca as A
from src.broker import espejo as E
from src.report import panel_alpaca as PA

KEY, SECRET = "PKTESTKEYID1234567890", "sEcReTsEcReTsEcReTsEcReT0987654321"
MAPEO = A.cargar_mapeo()
ABIERTO = {"abierto": True, "minutos_al_cierre": 120.0}
CERRADO = {"abierto": False, "minutos_al_cierre": None}


@pytest.fixture(autouse=True)
def aislado(tmp_path, monkeypatch):
    """Sin claves reales ni registro real: entorno limpio, alpaca.env y espejo.jsonl en tmp."""
    for k in list(os.environ):
        if k.startswith(("ALPACA_", "APCA_")) or k == "FIN_ALPACA_EJECUTAR":
            monkeypatch.delenv(k)
    monkeypatch.setenv("FIN_ALPACA_ENV", str(tmp_path / "alpaca.env"))
    monkeypatch.setenv("FIN_ALPACA_DIR", str(tmp_path / "alpaca"))
    A._avisados.clear()

    def sin_red(*a, **k):
        raise AssertionError("intento de red real en un test")
    monkeypatch.setattr(A, "_transporte_requests", sin_red)


def env_file(tmp_path, texto: str, modo: int = 0o600):
    p = tmp_path / "alpaca.env"
    p.write_text(texto)
    p.chmod(modo)
    return p


def cred(**kw) -> A.Credenciales:
    return A.Credenciales(key_id=KEY, secret=SECRET, **kw)


class Falso:
    """Transporte simulado: responde por (método, ruta) y guarda cada llamada."""

    def __init__(self, cuenta=None, posiciones=None, reloj=None, precios=None, fraccionable=True, abiertas=None):
        self.llamadas: list[tuple] = []
        self.cuenta = cuenta or {"id": "acc-uuid-1", "account_number": "PA12345678", "status": "ACTIVE",
                                 "currency": "USD", "equity": "100000", "cash": "100000", "buying_power": "200000"}
        self.pos = posiciones or []
        self.reloj = reloj or {"timestamp": "2026-11-18T10:00:00-05:00", "is_open": True,
                               "next_open": "2026-11-19T09:30:00-05:00", "next_close": "2026-11-18T16:00:00-05:00"}
        self.precios = precios or {"URTH": 160.0, "IEI": 118.0, "GLD": 250.0}
        self.frac = fraccionable
        self.abiertas = abiertas or []
        self.ordenes: dict[str, dict] = {}

    def __call__(self, metodo, url, cab, params, cuerpo, plazo):
        u = urlparse(url)
        self.llamadas.append((metodo, u.hostname, u.path, params, cuerpo, dict(cab)))
        r = u.path
        if r == "/v2/clock":
            return 200, self.reloj
        if r == "/v2/account":
            return 200, self.cuenta
        if r == "/v2/positions":
            return 200, self.pos
        if r.startswith("/v2/assets/"):
            return 200, {"symbol": r.rsplit("/", 1)[1], "tradable": True, "fractionable": self.frac}
        if r == "/v2/orders" and metodo == "GET":
            return 200, self.abiertas
        if r == "/v2/orders" and metodo == "POST":
            oid = f"o{len(self.ordenes) + 1}"
            p = self.precios[cuerpo["symbol"]]
            self.ordenes[oid] = {"id": oid, "status": "filled", "filled_qty": cuerpo["qty"],
                                 "filled_avg_price": str(p * (1.001 if cuerpo["side"] == "buy" else 0.999)),
                                 "filled_at": "2026-11-18T15:01:00Z"}
            return 200, {"id": oid, "status": "accepted"}
        if r.startswith("/v2/orders/"):
            return 200, self.ordenes[r.rsplit("/", 1)[1]]
        if r == "/v2/stocks/snapshots":
            return 200, {s: {"latestTrade": {"p": p, "t": "2026-11-18T15:00:00Z"},
                             "latestQuote": {"bp": p - 0.01, "ap": p + 0.01},
                             "prevDailyBar": {"c": p * 0.99}} for s, p in self.precios.items()}
        if r == "/v2/stocks/bars/latest":
            return 200, {"bars": {s: {"c": p, "t": "2026-11-18T14:59:00Z"} for s, p in self.precios.items()}}
        if r == "/v2/stocks/bars":
            return 200, {"bars": {s: [{"t": "2026-10-30T04:00:00Z", "c": p * 0.98},
                                      {"t": "2026-11-02T05:00:00Z", "c": p * 0.97}] for s, p in self.precios.items()}}
        return 404, {"message": f"ruta no simulada {r}"}


# --------------------------------------------------------------------------- endpoint real: siempre se niega
@pytest.mark.parametrize("url", ["https://api.alpaca.markets", "https://api.alpaca.markets/v2/orders",
                                 "https://API.alpaca.markets", "https://broker-api.alpaca.markets",
                                 "http://paper-api.alpaca.markets", "https://paper-api.alpaca.markets.evil.com",
                                 "https://paper-api.alpaca.markets:8443", "https://user:pw@paper-api.alpaca.markets",
                                 "https://example.com"])
def test_rechaza_endpoints_no_paper(url):
    with pytest.raises(A.EndpointNoPermitido):
        A.comprobar_url(url)


def test_acepta_solo_paper_y_datos():
    assert A.comprobar_url("https://paper-api.alpaca.markets/") == A.PAPER_TRADING
    assert A.comprobar_url("https://data.alpaca.markets/v2/stocks/snapshots")
    with pytest.raises(A.EndpointNoPermitido):   # datos no sirve como base de trading
        A.comprobar_url(A.DATOS, solo_trading=True)


@pytest.mark.parametrize("linea", ["ALPACA_BASE_URL=https://api.alpaca.markets",
                                   "APCA_API_BASE_URL=https://api.alpaca.markets",
                                   "ALPACA_BASE_URL_B1=https://api.alpaca.markets"])
def test_endpoint_real_configurado_en_fichero_se_niega(tmp_path, linea):
    env_file(tmp_path, f"ALPACA_API_KEY_ID={KEY}\nALPACA_API_SECRET_KEY={SECRET}\n"
                       f"ALPACA_API_KEY_ID_B1={KEY}\nALPACA_API_SECRET_KEY_B1={SECRET}\n{linea}\n")
    with pytest.raises(A.EndpointNoPermitido):
        A.cargar_credenciales("B1")


def test_endpoint_real_en_entorno_se_niega_y_cli_sale_con_error(monkeypatch, capsys):
    monkeypatch.setenv("ALPACA_API_KEY_ID", KEY)
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", SECRET)
    monkeypatch.setenv("APCA_API_BASE_URL", "https://api.alpaca.markets")
    with pytest.raises(A.EndpointNoPermitido):
        A.cargar_credenciales()
    assert A.main(["estado"]) == 2
    assert E.main(["--cartera", "B1", "--ejecutar"]) == 2
    out = capsys.readouterr()
    assert SECRET not in out.out + out.err and KEY not in out.out + out.err


def test_cliente_no_se_construye_con_endpoint_real():
    with pytest.raises(A.EndpointNoPermitido):
        A.Cliente(cred(base_url="https://api.alpaca.markets"), transporte=Falso())


def test_todas_las_llamadas_van_a_paper_o_datos(tmp_path):
    f = Falso()
    c = A.Cliente(cred(perfil="B1"), transporte=f)
    A.resumen(c)
    p = E.plan(c, "B1", logs=logs_tmp(tmp_path))
    E.ejecutar(c, p, espera_s=0, dormir=lambda s: None)
    hosts = {h for _, h, *_ in f.llamadas}
    assert hosts <= {A.HOST_PAPER, A.HOST_DATOS} and A.HOST_REAL not in hosts
    assert all(h == A.HOST_PAPER for m, h, *_ in f.llamadas if m == "POST")
    assert all(p_.get("feed") == "iex" for _, h, _, p_, *_ in f.llamadas if h == A.HOST_DATOS)


# --------------------------------------------------------------------------- claves
def test_sin_claves_todo_se_salta(capsys):
    assert A.cargar_credenciales() is None
    assert A.main(["estado"]) == 0
    assert E.main(["--cartera", "B1"]) == 0
    assert E.main(["--cartera", "B1", "--ejecutar", "--auto"]) == 0
    assert "Alpaca no configurado" in capsys.readouterr().out
    assert "Alpaca no configurado" in PA.seccion_alpaca()
    assert not (E.ruta_registro()).exists()


def test_lee_fichero_y_perfiles(tmp_path, monkeypatch):
    env_file(tmp_path, f"# claves paper\nexport ALPACA_API_KEY_ID='{KEY}'\nALPACA_API_SECRET_KEY=\"{SECRET}\"\n"
                       f"ALPACA_CARTERA=B0\nALPACA_API_KEY_ID_B1P=k2\nALPACA_API_SECRET_KEY_B1P=s2\n")
    c = A.cargar_credenciales()
    assert (c.key_id, c.secret, c.cartera, c.base_url) == (KEY, SECRET, "B0", A.PAPER_TRADING)
    c2 = A.cargar_credenciales("B1′")
    assert (c2.key_id, c2.perfil) == ("k2", "B1P") and E.cartera_de(c2) == "B1P"
    assert A.perfiles() == ["", "B1P"]
    monkeypatch.setenv("ALPACA_API_KEY_ID", "del_entorno")
    assert A.cargar_credenciales().key_id == "del_entorno"   # el entorno manda


def test_aviso_si_permisos_no_600(tmp_path, capsys, caplog):
    p = env_file(tmp_path, f"ALPACA_API_KEY_ID={KEY}\nALPACA_API_SECRET_KEY={SECRET}\n", modo=0o644)
    with caplog.at_level(logging.WARNING):
        A.cargar_credenciales()
    assert "600" in capsys.readouterr().err and "600" in caplog.text
    p.chmod(0o600)
    assert A.aviso_permisos(p) is None


def test_claves_no_salen_en_repr_errores_ni_logs(tmp_path, capsys, caplog, monkeypatch):
    c = cred()
    assert SECRET not in repr(c) and KEY not in repr(c) and SECRET not in str(A.Cliente(c, transporte=Falso()))

    def roto(metodo, url, cab, *a):
        raise ConnectionError(f"fallo con cabeceras {cab}")   # un error que (mal) incluyera las claves
    with pytest.raises(A.AlpacaError) as e:
        A.Cliente(c, transporte=roto).cuenta()
    assert SECRET not in str(e.value) and KEY not in str(e.value) and "***" in str(e.value)

    def eco(metodo, url, cab, *a):
        return 403, {"message": f"forbidden for {cab['APCA-API-KEY-ID']}"}
    with pytest.raises(A.AlpacaError) as e:
        A.Cliente(c, transporte=eco).cuenta()
    assert KEY not in str(e.value) and e.value.status == 403

    # CLI de punta a punta con el transporte simulado: ni stdout, ni stderr, ni logs, ni el registro
    env_file(tmp_path, f"ALPACA_API_KEY_ID_B1={KEY}\nALPACA_API_SECRET_KEY_B1={SECRET}\n")
    monkeypatch.setattr(A, "_transporte_requests", Falso())
    monkeypatch.setattr(E, "CARTERAS", {**E.CARTERAS, **{k: v for k, v in logs_tmp(tmp_path).items()}})
    with caplog.at_level(logging.DEBUG):
        assert A.main(["estado", "--perfil", "B1"]) == 0
        assert E.main(["--cartera", "B1", "--ejecutar", "--espera", "0"]) == 0
        monkeypatch.setattr(A, "_transporte_requests", roto)
        assert A.main(["estado", "--perfil", "B1"]) == 1
    out = capsys.readouterr()
    todo = out.out + out.err + caplog.text + E.ruta_registro().read_text()
    assert KEY not in todo and SECRET not in todo
    assert "PA12345678" not in todo and "…5678" in out.out


# --------------------------------------------------------------------------- horario de mercado
def test_estado_mercado_y_tipo_de_orden():
    m = A.estado_mercado({"timestamp": "2026-11-18T15:50:00.123456789-05:00", "is_open": True,
                          "next_close": "2026-11-18T16:00:00-05:00", "next_open": "2026-11-19T09:30:00-05:00"})
    assert m["abierto"] and m["minutos_al_cierre"] == pytest.approx(10, abs=0.1)
    cfg = MAPEO["ordenes"]
    assert E.tipo_orden(m, cfg) == "limit"                     # a 10 min del cierre: limit
    assert E.tipo_orden(ABIERTO, cfg) == "market"
    assert E.tipo_orden(CERRADO, cfg) == "limit"
    c = A.estado_mercado({"timestamp": "2026-11-21T12:00:00Z", "is_open": False,
                          "next_open": "2026-11-23T09:30:00-05:00", "next_close": "2026-11-23T16:00:00-05:00"})
    assert not c["abierto"] and c["minutos_al_cierre"] is None and c["proxima_apertura"].startswith("2026-11-23")


# --------------------------------------------------------------------------- cálculo de órdenes y redondeos
def test_redondeos():
    assert E.redondea_qty(10.987654, True, 4) == 10.9876
    assert E.redondea_qty(10.987654, False, 4) == 10.0
    assert E.redondea_qty(0.00004, True, 4) == 0.0
    assert E.redondea_qty(-1, True, 4) == 0.0
    assert E.precio_limit(100.0, "buy", 0.005) == 100.5
    assert E.precio_limit(100.003, "sell", 0.005) == 99.51        # hacia arriba: no vende por debajo del margen
    assert E.precio_limit(0.5, "buy", 0.005) == 0.5025            # < 1 $: 4 decimales
    assert E.Orden("X", "rv", "buy", 1.23450000, "limit", 100.5, 100, 123.45, .7, 0).cuerpo()["qty"] == "1.2345"


def calcula(pos=None, precios=None, frac=True, mercado=ABIERTO, equity=100_000.0, efectivo=None, pesos=None):
    precios = precios or {"URTH": 160.0, "IEI": 118.0, "GLD": 250.0}
    pos = pos or {}
    if efectivo is None:
        efectivo = equity - sum(q * precios[s] for s, q in pos.items())
    return E.calcular_ordenes(pesos or {"rv": 0.7, "rf": 0.15, "oro": 0.15}, MAPEO, equity=equity, efectivo=efectivo,
                              posiciones=pos, precios=precios, fraccionable={s: frac for s in precios},
                              mercado=mercado)


def test_cuenta_vacia_fracciones():
    ords, res = calcula()
    q = {o.simbolo: o for o in ords}
    assert set(q) == {"URTH", "IEI", "GLD"} and all(o.lado == "buy" and o.tipo_orden == "market" for o in ords)
    inv = 100_000 * (1 - MAPEO["liquidez"]["colchon"])
    assert q["URTH"].qty == E.redondea_qty(0.7 * inv / 160, True, 4) == 435.3125
    assert all(round(o.qty, 4) == o.qty for o in ords)
    assert sum(o.valor_estimado for o in ords) <= inv
    assert res["coste_teorico_usd"] == pytest.approx(0.7 * inv * 10e-4 + 0.15 * inv * 10e-4 + 0.15 * inv * 20e-4, abs=1)


def test_sin_fracciones_acciones_enteras_y_minimo():
    ords, _ = calcula(frac=False, equity=1000.0, precios={"URTH": 160.0, "IEI": 118.0, "GLD": 250.0})
    q = {o.simbolo: o.qty for o in ords}
    assert q == {"URTH": 4.0, "IEI": 1.0}        # GLD: 0,15·995/250 < 1 acción → no se compra
    ords, res = calcula(equity=50.0)              # 15 % de 50 $ = 7,5 $ < mínimo de 10 $
    assert {o.simbolo for o in ords} == {"URTH"} and len(res["omitidas"]) == 2


def test_rebalanceo_ventas_primero_y_limit_fuera_de_horario():
    precios = {"URTH": 160.0, "IEI": 118.0, "GLD": 250.0}
    pos = {"URTH": 500.0, "IEI": 50.0, "GLD": 40.0}            # 80 000 / 5 900 / 10 000 de 100 000
    ords, _ = calcula(pos=pos, mercado=CERRADO, efectivo=4100.0)
    assert [o.lado for o in ords] == ["sell", "buy", "buy"] and ords[0].simbolo == "URTH"
    assert all(o.tipo_orden == "limit" and o.limit_price for o in ords)
    assert ords[0].limit_price < 160 and all(o.limit_price > o.precio_ref for o in ords[1:])
    inv = 100_000 * 0.995
    assert ords[0].qty == E.redondea_qty((80_000 - 0.7 * inv) / 160, True, 4)


def test_posicion_fuera_del_mapeo_se_vende_entera_y_falta_precio_falla():
    ords, _ = calcula(pos={"SPY": 0.5}, precios={"URTH": 160.0, "IEI": 118.0, "GLD": 250.0, "SPY": 10.0},
                      efectivo=99_995.0)
    spy = [o for o in ords if o.simbolo == "SPY"]
    assert spy and spy[0].lado == "sell" and spy[0].qty == 0.5     # aunque valga < mínimo
    with pytest.raises(ValueError, match="sin precio"):
        calcula(precios={"URTH": 160.0, "IEI": 118.0, "GLD": 0})
    with pytest.raises(ValueError, match="no suman 1"):
        calcula(pesos={"rv": 0.7, "rf": 0.2, "oro": 0.15})


def test_compras_se_recortan_al_presupuesto():
    ords, res = calcula(efectivo=50_000.0)    # valor 100 000 pero solo 50 000 de efectivo y nada que vender
    assert res["escala_compras"] < 1
    assert sum(o.qty * o.precio_ref for o in ords) <= 50_000 + 1e-6
    ords, res = calcula(efectivo=50_000.0, mercado=CERRADO)     # limit: a su precio límite
    assert res["escala_compras"] < 1 and sum(o.qty * o.limit_price for o in ords) <= 50_000 + 1e-6


def test_deslizamiento_signo():
    assert E.deslizamiento_pb("buy", 100.1, 100) == 10.0
    assert E.deslizamiento_pb("sell", 99.9, 100) == 10.0
    assert E.deslizamiento_pb("sell", 100.1, 100) == -10.0
    assert E.deslizamiento_pb("buy", None, 100) is None


# --------------------------------------------------------------------------- decisiones y una cuenta = una cartera
def logs_tmp(tmp_path) -> dict:
    b1 = tmp_path / "decisiones.jsonl"
    b1.write_text(json.dumps({"cierre": "2026-10-31", "b0": {"rv": 0.7, "rf": 0.15, "oro": 0.15},
                              "b1": {"rv": 0.6, "rf": 0.25, "oro": 0.15}}) + "\n")
    b1p = tmp_path / "decisiones_b1prima.jsonl"
    b1p.write_text(json.dumps({"cierre": "2026-11-30", "b1prima": {"rv": 0.619, "rf": 0.231, "oro": 0.15}}) + "\n")
    return {"B0": (b1, "b0"), "B1": (b1, "b1"), "B1P": (b1p, "b1prima")}


def test_decisiones_se_leen_sin_tocar_los_registros(tmp_path):
    L = logs_tmp(tmp_path)
    antes = {p: p.read_bytes() for p, _ in L.values()}
    assert E.decision("B1", logs=L)["pesos"] == {"rv": 0.6, "rf": 0.25, "oro": 0.15}
    assert E.decision("B1′", logs=L)["cierre"] == "2026-11-30"
    assert E.decision("B0", "2026-09-30", logs=L) is None
    assert {p: p.read_bytes() for p, _ in L.values()} == antes
    # los registros reales existen y se pueden leer (B0/B1 congelados)
    assert E.decision("B1") is not None


def test_una_cuenta_una_cartera():
    assert "no declara" in E.puede_ejecutar(cred(), "B1", "h", [])
    assert "es de la cartera B0" in E.puede_ejecutar(cred(perfil="B0"), "B1", "h", [])
    assert E.puede_ejecutar(cred(perfil="B1"), "B1", "h", []) is None
    assert E.puede_ejecutar(cred(cartera="B1"), "B1", "h", []) is None
    usado = [{"tipo": "orden", "cartera": "B0", "cuenta_huella": "h"}]
    assert "ya se usó" in E.puede_ejecutar(cred(perfil="B1"), "B1", "h", usado)


# --------------------------------------------------------------------------- flujo completo simulado
def test_dry_run_no_envia_y_apunta_plan(tmp_path, monkeypatch, capsys):
    env_file(tmp_path, f"ALPACA_API_KEY_ID_B1={KEY}\nALPACA_API_SECRET_KEY_B1={SECRET}\n")
    f = Falso()
    monkeypatch.setattr(A, "_transporte_requests", f)
    monkeypatch.setattr(E, "CARTERAS", logs_tmp(tmp_path))
    assert E.main(["--cartera", "B1", "--dry-run"]) == 0
    assert not [x for x in f.llamadas if x[0] == "POST"]
    (plan,) = E.leer_registro()
    assert plan["tipo"] == "plan" and plan["dry_run"] and plan["pesos_decision"]["rv"] == 0.6
    assert "dry-run" in capsys.readouterr().out


def test_auto_ejecutar_exige_variable(tmp_path, monkeypatch):
    env_file(tmp_path, f"ALPACA_API_KEY_ID_B1={KEY}\nALPACA_API_SECRET_KEY_B1={SECRET}\n")
    f = Falso()
    monkeypatch.setattr(A, "_transporte_requests", f)
    monkeypatch.setattr(E, "CARTERAS", logs_tmp(tmp_path))
    assert E.main(["--cartera", "B1", "--ejecutar", "--auto"]) == 0
    assert not [x for x in f.llamadas if x[0] == "POST"]
    monkeypatch.setenv("FIN_ALPACA_EJECUTAR", "1")
    assert E.main(["--cartera", "B1", "--ejecutar", "--auto", "--espera", "0"]) == 0
    assert len([x for x in f.llamadas if x[0] == "POST"]) == 3
    n = len(f.llamadas)
    assert E.main(["--cartera", "B1", "--ejecutar", "--auto"]) == 0      # ya ejecutado este cierre: no repite
    assert not [x for x in f.llamadas[n:] if x[0] == "POST"]


def test_ejecucion_registra_deslizamiento(tmp_path):
    f = Falso()
    c = A.Cliente(cred(perfil="B1"), transporte=f)
    p = E.plan(c, "B1", logs=logs_tmp(tmp_path))
    ej = E.ejecutar(c, p, espera_s=0, dormir=lambda s: None)
    assert len(ej) == 3 and all(x["estado"] == "filled" for x in ej)
    assert all(x["deslizamiento_pb_vs_ref"] == pytest.approx(10, abs=0.5) for x in ej)
    urth = next(x for x in ej if x["simbolo"] == "URTH")
    assert urth["cierre_sesion"] == pytest.approx(160 * 0.98)      # sesión ≤ 2026-10-31, no la de noviembre
    assert urth["deslizamiento_pb_vs_cierre"] == pytest.approx((1.001 / 0.98 - 1) * 1e4, abs=0.1)
    posts = [x[4] for x in f.llamadas if x[0] == "POST"]
    assert all(b["client_order_id"].startswith("espejo-B1-2026-10-31-") and b["time_in_force"] == "day" for b in posts)
    r = E.resumen_ejecucion(E.leer_registro(), "B1")
    assert r["ejecuciones"] == 3 and r["desliz_pb_vs_ref"] == pytest.approx(10, abs=0.5)


def test_no_envia_con_ordenes_abiertas(tmp_path):
    f = Falso(abiertas=[{"id": "x"}])
    c = A.Cliente(cred(perfil="B1"), transporte=f)
    p = E.plan(c, "B1", logs=logs_tmp(tmp_path))
    with pytest.raises(A.AlpacaError, match="órdenes abiertas"):
        E.ejecutar(c, p, espera_s=0)
    assert not [x for x in f.llamadas if x[0] == "POST"]


# --------------------------------------------------------------------------- panel
def test_seccion_panel(tmp_path, monkeypatch):
    f = Falso(posiciones=[{"symbol": "URTH", "qty": "10", "current_price": "160", "market_value": "1600"}])
    monkeypatch.setattr(E, "CARTERAS", logs_tmp(tmp_path))
    h = PA.seccion_alpaca([A.Cliente(cred(perfil="B1"), transporte=f)], registro=[])
    assert "SIMULADA" in h and "URTH" in h and "abierto" in h and "100 000.00" in h and "60.0%" in h
    assert KEY not in h and SECRET not in h and "PA12345678" not in h

    def roto(*a):
        raise ConnectionError("caído")
    h = PA.seccion_alpaca([A.Cliente(cred(perfil="B1"), transporte=roto)], registro=[])
    assert "no responde" in h


def test_panel_engancha_alpaca_en_mi_cartera_y_se_puede_apagar(monkeypatch):
    from src.report import panel as P
    monkeypatch.setattr(P.PAL, "seccion_alpaca", lambda: "<section id='alpaca'>ALPACA-OK</section>")
    assert P._alpaca() == ""                         # conftest: FIN_PANEL_SIN_ALPACA=1
    monkeypatch.delenv("FIN_PANEL_SIN_ALPACA")
    assert "ALPACA-OK" in P._alpaca()
    html = P.construir({})
    cart = html.split('<section id="cartera"')[1].split('<section id="estado"')[0]
    assert "ALPACA-OK" in cart
