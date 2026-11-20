"""C1 «Claude gestor» (spec C1 v1.0): paquete, explicador con un `claude` FALSO, ciclo completo en ensayo y con una
cuenta PAPER simulada (transporte falso), registro. Sin red, sin claves, sin tocar los registros reales."""
from __future__ import annotations

import datetime as dt
import json
import os
import stat
import subprocess
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

from src.broker import alpaca as A
from src.broker import c1_guardia as G
from src.paper import c1 as C
from src.paper import c1_paquete as P

REPO = C.REPO
REG_REAL = REPO / "research" / "paper" / "decisiones_c1.jsonl"
OPC = "SPY261218C00600000"


@pytest.fixture(autouse=True)
def aislado(tmp_path, monkeypatch):
    for k in list(os.environ):
        if k.startswith(("ALPACA_", "APCA_")):
            monkeypatch.delenv(k)
    # estos tests son los del explicador c1-v1 (modo «paquete», validado el 19-nov); el modo agente c1-v2 se prueba
    # en tests/test_agente.py
    monkeypatch.setattr(C, "MODO_DEFECTO", "paquete")
    monkeypatch.setattr(C.AG, "ruta_diario", lambda cartera, fecha, repo=None: tmp_path / "diarios" / cartera / f"{fecha}.md")
    monkeypatch.setenv("FIN_ALPACA_ENV", str(tmp_path / "alpaca.env"))
    monkeypatch.setenv("FIN_ALPACA_DIR", str(tmp_path / "alpaca"))
    monkeypatch.setenv("FIN_C1_DIR", str(tmp_path / "c1"))
    monkeypatch.setattr(A, "_transporte_requests", lambda *a, **k: (_ for _ in ()).throw(AssertionError("red real")))
    # partes lentas o que leen el archivo real: datos fijos
    monkeypatch.setattr(P, "cierres_warehouse", lambda X=None: {"fuente": "test", "activos": {
        "SPY": {"fecha": "2026-11-18", "cierre": 600.0}, "GLD": {"fecha": "2026-11-18", "cierre": 250.0},
        "BAYN.DE": {"fecha": "2026-11-18", "cierre": 30.0}}})
    monkeypatch.setattr(P, "alertas", lambda hoy: [{"ticker": "UNH", "frase": "volumen anormal"}])
    monkeypatch.setattr(P, "resumen_panel", lambda s: ["EE. UU. en Goldilocks"])
    monkeypatch.setattr(P, "ultimo_signal", lambda: ({"asof": "2026-11-17", "regime": {"quadrant": "Goldilocks"},
                                                      "credit": {"light": "verde", "indicators": [1, 2]}}, "x_signal.json"))
    monkeypatch.setattr(G, "PARADA", tmp_path / "C1_PARADA")
    antes = REG_REAL.read_bytes() if REG_REAL.exists() else None
    yield
    assert (REG_REAL.read_bytes() if REG_REAL.exists() else None) == antes, "un test tocó el registro real de C1"


def propuesta(ordenes=None, **kw) -> str:
    d = {"version_mandato": "c1-v1", "fecha": "2026-11-19", "resumen": "Mercado tranquilo.",
         "ordenes": ordenes if ordenes is not None else [], "nota_diario": "Sin cambios."}
    d.update(kw)
    return json.dumps(d, ensure_ascii=False)


def claude_falso(tmp_path: Path, resultado: str | None = None, *, dormir: int = 0, codigo: int = 0,
                 envoltorio: dict | None = None) -> Path:
    """Binario `claude` falso: apunta argumentos, entorno, carpeta y entrada; responde como --output-format json."""
    d = tmp_path / "falso"
    d.mkdir(exist_ok=True)
    env = envoltorio or {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 4321,
                         "result": resultado if resultado is not None else propuesta(), "total_cost_usd": 0.42,
                         "modelUsage": {"claude-opus-5-5": {"inputTokens": 1}}}
    (d / "respuesta.json").write_text(json.dumps(env))
    s = d / "claude"
    s.write_text(f"""#!/bin/bash
printf '%s\\n' "$@" > {d}/args.txt
env > {d}/env.txt
pwd > {d}/pwd.txt
cat > {d}/stdin.txt
sleep {dormir}
cat {d}/respuesta.json
exit {codigo}
""")
    s.chmod(s.stat().st_mode | stat.S_IEXEC)
    return s


def paquete_min(**kw) -> dict:
    return P.armar(fecha="2026-11-19", mercado=None, cuenta=P.cuenta_simulada(), precios={}, regimen_={},
                   alertas_=[], diagnosticos_=[], panel_=[], diario_=[], **kw)


# ------------------------------------------------------------------ paquete
def test_paquete_tiene_hash_estable_y_cambia_con_el_contenido():
    p = paquete_min()
    assert p["sha256"] == P.hash_paquete(p) and len(p["sha256"]) == 64
    q = dict(p, cuenta={**p["cuenta"], "efectivo": 1.0})
    assert P.hash_paquete(q) != p["sha256"]


def test_paquete_simulado_sin_claves_y_partes_tolerantes(monkeypatch):
    def rompe(hoy):
        raise RuntimeError("sin datos")
    monkeypatch.setattr(P, "diagnosticos", rompe)
    p = P.recoger(None, dt.date(2026, 11, 19), registro=[])
    assert p["cuenta"]["simulada"] and p["cuenta"]["efectivo"] == 100_000
    assert p["regimen"]["regimen"]["quadrant"] == "Goldilocks" and "indicators" not in p["regimen"]["credito"]
    assert p["diagnosticos"][0]["error"].startswith("RuntimeError")      # una parte falla, el resto sale
    assert p["panel"] == ["EE. UU. en Goldilocks"] and p["mandato"] == "c1-v1"
    assert "KEY" not in json.dumps(p).upper().replace("KEYS", "")


def test_diagnosticos_recientes_si_existe_la_carpeta(tmp_path):
    assert P.diagnosticos(dt.date(2026, 11, 19), tmp_path / "no_existe") == []
    (tmp_path / "2026-11-18_oro.md").write_text("x" * 5000)
    (tmp_path / "2026-11-01_viejo.md").write_text("viejo")
    (tmp_path / "notas.md").write_text("sin fecha")
    d = P.diagnosticos(dt.date(2026, 11, 19), tmp_path)
    assert [x["fichero"] for x in d] == ["2026-11-18_oro.md"] and d[0]["recortado"] and len(d[0]["texto"]) == 4000


def test_diario_resume_las_decisiones_anteriores():
    reg = [{"fecha": "2026-11-18", "opera": True, "propuesta": json.loads(propuesta(
        [{"simbolo": "SPY", "lado": "compra", "importe_usd": 10, "razon": "r", "cambiaria_de_opinion": "c"}])),
        "rechazadas": [{"orden": {"simbolo": "GLD"}, "motivo": "m"}],
        "ejecuciones": [{"simbolo": "SPY", "lado": "compra", "estado": "filled", "qty_ejecutada": 0.1,
                         "precio_medio": 600}], "paquete": {"valor_cuenta": 100000}}]
    d = P.diario(reg)
    assert d[0]["nota_diario"] == "Sin cambios." and d[0]["ordenes"][0]["razon"] == "r"
    assert d[0]["rechazadas"] == [{"simbolo": "GLD", "motivo": "m"}] and d[0]["valor_cuenta"] == 100000


# ------------------------------------------------------------------ explicador (scripts/c1_gestor.sh explicar)
def test_explicador_sin_herramientas_sin_claves_y_en_carpeta_aislada(tmp_path, monkeypatch):
    f = claude_falso(tmp_path)
    monkeypatch.setenv("FIN_C1_CLAUDE", str(f))
    monkeypatch.setenv("ALPACA_API_KEY_ID_C1", "PKSECRETOQUENODEBEPASAR")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "otrosecreto")
    r = C.explicar(paquete_min(), tmp_path / "trabajo")
    assert r["ok"] and r["modelo"] == ["claude-opus-5-5"] and r["coste_usd"] == 0.42 and r["duracion_claude_s"] == 4.3
    args = (f.parent / "args.txt").read_text().splitlines()
    assert args[0] == "-p" and "--restricted" in args and "--strict-mcp-config" in args
    assert args[args.index("--tools") + 1] == "" and args[args.index("--output-format") + 1] == "json"
    for t in ("Bash", "Read", "WebFetch"):
        assert t in args[args.index("--disallowedTools"):]
    sp = args[args.index("--system-prompt") + 1:]
    assert any("Formato de salida (OBLIGATORIO)" in x for x in sp)          # el mandato va como system prompt
    env = (f.parent / "env.txt").read_text()
    assert "PKSECRETOQUENODEBEPASAR" not in env and "otrosecreto" not in env and "ALPACA" not in env
    assert Path((f.parent / "pwd.txt").read_text().strip()).resolve() == (tmp_path / "trabajo").resolve()
    stdin = (f.parent / "stdin.txt").read_text()
    assert "PAQUETE DEL DÍA" in stdin and '"mandato": "c1-v1"' in stdin
    assert (tmp_path / "trabajo" / "salida_claude.json").exists()


def test_explicador_mas_de_plazo_no_opera_y_mata_el_proceso(tmp_path, monkeypatch):
    monkeypatch.setenv("FIN_C1_CLAUDE", str(claude_falso(tmp_path, dormir=30)))
    t0 = time.monotonic()
    r = C.explicar(paquete_min(), tmp_path / "t", plazo=1)
    assert not r["ok"] and "tardó" in r["error"] and time.monotonic() - t0 < 10
    out = subprocess.run(["pgrep", "-f", str(tmp_path / "falso")], capture_output=True, text=True).stdout
    assert out.strip() == ""


@pytest.mark.parametrize("kw", [{"codigo": 1}, {"envoltorio": {"is_error": True, "subtype": "error_max_turns"}}])
def test_explicador_que_falla_se_anota(tmp_path, monkeypatch, kw):
    monkeypatch.setenv("FIN_C1_CLAUDE", str(claude_falso(tmp_path, **kw)))
    r = C.explicar(paquete_min(), tmp_path / "t")
    assert not r["ok"] and r["error"]


def test_explicador_salida_no_json(tmp_path, monkeypatch):
    f = claude_falso(tmp_path)
    (f.parent / "respuesta.json").write_text("esto no es json")
    monkeypatch.setenv("FIN_C1_CLAUDE", str(f))
    r = C.explicar(paquete_min(), tmp_path / "t")
    assert not r["ok"] and "no es JSON" in r["error"]


# ------------------------------------------------------------------ ciclo en ensayo (dry-run) con claude falso
def test_ciclo_ensayo_completo_sin_claves(tmp_path, monkeypatch):
    ordenes = [
        {"simbolo": "SPY", "clase": "accion", "lado": "compra", "tipo": "mercado", "importe_usd": 30000,
         "razon": "Núcleo de bolsa.", "cambiaria_de_opinion": "Recesión."},
        {"simbolo": "GLD", "clase": "accion", "lado": "compra", "tipo": "mercado", "importe_usd": 90000,
         "razon": "Oro.", "cambiaria_de_opinion": "Tipos reales al alza."},                 # supera el efectivo
        {"simbolo": "BTC/USD", "clase": "cripto", "lado": "compra", "tipo": "mercado", "importe_usd": 1000,
         "razon": "Cripto.", "cambiaria_de_opinion": "x"},                                  # no verificable sin Alpaca
        {"simbolo": "TLT", "clase": "accion", "lado": "venta", "tipo": "mercado", "cantidad": 3,
         "razon": "x", "cambiaria_de_opinion": "x"}]                                        # no se tiene (y desconocido)
    monkeypatch.setenv("FIN_C1_CLAUDE", str(claude_falso(tmp_path, propuesta(ordenes))))
    linea = C.ciclo(None, hoy=dt.date(2026, 11, 19), registro=[], enviar=False)
    assert linea["ensayo"] and linea["opera"] and linea["modelo"] == ["claude-opus-5-5"]
    assert [n["simbolo"] for n in linea["guardia"]["validas"]] == ["SPY"]
    assert {r["indice"] for r in linea["rechazadas"]} == {1, 2, 3}
    assert linea["enviadas"] == [] and linea["ejecuciones"] == []
    assert linea["paquete"]["simulada"] and len(linea["paquete"]["sha256"]) == 64
    assert linea["mandato"]["sha256"] == C.sha256_fichero(C.MANDATO)
    assert (tmp_path / "c1" / "ensayos").is_dir()
    with pytest.raises(ValueError):
        C.registrar(linea, tmp_path / "reg.jsonl")                 # un ensayo nunca se registra


def test_ciclo_con_json_invalido_no_opera(tmp_path, monkeypatch):
    monkeypatch.setenv("FIN_C1_CLAUDE", str(claude_falso(tmp_path, "Hoy compraría SPY")))
    linea = C.ciclo(None, hoy=dt.date(2026, 11, 19), registro=[])
    assert not linea["opera"] and "inválida" in linea["motivo_no_opera"] and linea["propuesta"] is None
    assert linea["salida_no_valida"] == "Hoy compraría SPY"


def test_ciclo_con_parada_no_llama_a_claude(tmp_path, monkeypatch):
    f = claude_falso(tmp_path)
    monkeypatch.setenv("FIN_C1_CLAUDE", str(f))
    linea = C.ciclo(None, hoy=dt.date(2026, 11, 19), registro=[], parada=True)
    assert not linea["opera"] and "parada" in linea["motivo_no_opera"] and not (f.parent / "args.txt").exists()


def test_cambio_de_modelo_se_anota(tmp_path, monkeypatch):
    monkeypatch.setenv("FIN_C1_CLAUDE", str(claude_falso(tmp_path)))
    linea = C.ciclo(None, hoy=dt.date(2026, 11, 20), registro=[{"fecha": "2026-11-19", "modelo": ["claude-opus-5-0"]}])
    assert linea["cambio_modelo"] is True


# ------------------------------------------------------------------ cuenta PAPER simulada (transporte falso)
class Falso:
    def __init__(self, efectivo="10000", posiciones=None, abiertas=None, estado_final="filled"):
        self.llamadas: list[tuple] = []
        self.cuenta = {"id": "acc-c1", "account_number": "PA99998888", "status": "ACTIVE", "currency": "USD",
                       "equity": "16000", "cash": efectivo, "buying_power": "32000"}
        self.pos = posiciones if posiciones is not None else [
            {"symbol": "SPY", "qty": "10", "asset_class": "us_equity", "market_value": "6000", "current_price": "600"}]
        self.abiertas = abiertas or []
        self.ordenes: dict[str, dict] = {}
        self.estado_final = estado_final

    def __call__(self, metodo, url, cab, params, cuerpo, plazo):
        u = urlparse(url)
        r = unquote(u.path)
        self.llamadas.append((metodo, u.hostname, r, params, cuerpo))
        if r == "/v2/clock":
            return 200, {"timestamp": "2026-11-19T14:30:00-05:00", "is_open": True,
                         "next_open": "2026-11-20T09:30:00-05:00", "next_close": "2026-11-19T16:00:00-05:00"}
        if r == "/v2/account":
            return 200, self.cuenta
        if r == "/v2/positions":
            return 200, self.pos
        if r == "/v2/account/portfolio/history":
            return 200, {"timestamp": [1763337600, 1763424000], "equity": [17000.0, 16000.0]}
        if r.startswith("/v2/options/contracts/"):
            return 200, {"symbol": r.rsplit("/", 1)[1], "tradable": True, "status": "active"}
        if r.startswith("/v2/assets/"):
            s = r.rsplit("/", 1)[1]
            if s == "BTCUSD":
                return 200, {"symbol": "BTC/USD", "class": "crypto", "tradable": True, "fractionable": True}
            if s == "ZZZZ":
                return 404, {"message": "asset not found"}
            return 200, {"symbol": s, "class": "us_equity", "tradable": s != "NOPE", "fractionable": True,
                         "status": "active"}
        if r == "/v2/orders" and metodo == "GET":
            return 200, self.abiertas
        if r == "/v2/orders" and metodo == "POST":
            oid = f"o{len(self.ordenes) + 1}"
            self.ordenes[oid] = {"id": oid, "status": self.estado_final, "filled_qty": cuerpo.get("qty") or "1",
                                 "filled_avg_price": "100", "filled_at": "2026-11-19T19:31:00Z"}
            return 200, {"id": oid, "status": "accepted"}
        if r.startswith("/v2/orders/"):
            return 200, self.ordenes[r.rsplit("/", 1)[1]]
        if r == "/v2/stocks/snapshots":
            return 200, {s: {"latestTrade": {"p": 100.0}} for s in params["symbols"].split(",")}
        if r == "/v1beta3/crypto/us/snapshots":
            return 200, {"snapshots": {s: {"latestTrade": {"p": 90000.0}} for s in params["symbols"].split(",")}}
        if r == "/v1beta1/options/snapshots":
            return 200, {"snapshots": {s: {"latestQuote": {"ap": 5.0, "bp": 4.8}} for s in params["symbols"].split(",")}}
        return 404, {"message": f"ruta no simulada {r}"}


def cliente(t: Falso, perfil: str = "C1") -> A.Cliente:
    return A.Cliente(A.Credenciales(key_id="PKC1TEST", secret="SECRETC1TEST", perfil=perfil), transporte=t)


ORDENES_REALES = [
    {"simbolo": "QQQ", "clase": "accion", "lado": "compra", "tipo": "mercado", "importe_usd": 2000,
     "razon": "Tecnología.", "cambiaria_de_opinion": "Beneficios a la baja."},
    {"simbolo": "SPY", "clase": "accion", "lado": "venta", "tipo": "mercado", "cantidad": 4,
     "razon": "Reducir.", "cambiaria_de_opinion": "x"},
    {"simbolo": OPC, "clase": "opcion", "lado": "compra", "tipo": "limite", "cantidad": 2, "precio_limite": 5.0,
     "razon": "Cobertura alcista barata.", "cambiaria_de_opinion": "x"},
    {"simbolo": "BTC/USD", "clase": "cripto", "lado": "compra", "tipo": "mercado", "importe_usd": 500,
     "razon": "Cripto.", "cambiaria_de_opinion": "x"},
    {"simbolo": "GLD", "clase": "accion", "lado": "compra", "tipo": "mercado", "importe_usd": 9000,
     "razon": "Oro.", "cambiaria_de_opinion": "x"},                       # 2000 + 1000 + 500 + 9000 > 10 000: fuera
    {"simbolo": "SPY", "clase": "accion", "lado": "venta", "tipo": "mercado", "cantidad": 20,
     "razon": "x", "cambiaria_de_opinion": "x"},                          # más de lo que queda: corto, fuera
    {"simbolo": OPC, "clase": "opcion", "lado": "venta", "tipo": "mercado", "cantidad": 1,
     "razon": "x", "cambiaria_de_opinion": "x"},                          # opción sin tener: al descubierto, fuera
    {"simbolo": "NOPE", "clase": "accion", "lado": "compra", "tipo": "mercado", "importe_usd": 10,
     "razon": "x", "cambiaria_de_opinion": "x"},                          # no negociable
    {"simbolo": "ZZZZ", "clase": "accion", "lado": "compra", "tipo": "mercado", "importe_usd": 10,
     "razon": "x", "cambiaria_de_opinion": "x"}]                          # desconocido (404)


def test_ciclo_envia_solo_lo_valido_a_la_cuenta_paper(tmp_path, monkeypatch):
    monkeypatch.setenv("FIN_C1_CLAUDE", str(claude_falso(tmp_path, propuesta(ORDENES_REALES))))
    t = Falso()
    linea = C.ciclo(cliente(t), hoy=dt.date(2026, 11, 19), registro=[], enviar=True, dormir=lambda s: None)
    assert not linea["ensayo"] and linea["opera"]
    posts = [x[4] for x in t.llamadas if x[0] == "POST"]
    assert [p["symbol"] for p in posts] == ["SPY", "QQQ", OPC, "BTC/USD"]                  # ventas primero
    assert posts[0] == {"symbol": "SPY", "side": "sell", "type": "market", "time_in_force": "day",
                        "client_order_id": "c1-2026-11-19-01", "qty": "4"}
    assert posts[2]["position_intent"] == "buy_to_open" and posts[2]["limit_price"] == "5.00"
    assert posts[3]["time_in_force"] == "gtc" and posts[3]["notional"] == "500.00"
    assert {r["indice"] for r in linea["rechazadas"]} == {4, 5, 6, 7, 8}
    assert linea["guardia"]["compras_estimadas_usd"] <= float(t.cuenta["cash"])
    assert len(linea["ejecuciones"]) == 4 and all(e["estado"] == "filled" for e in linea["ejecuciones"])
    assert linea["ejecuciones"][2]["valor_usd"] == 2 * 100 * 100                              # opción × 100
    assert {h for _, h, *_ in t.llamadas} <= {A.HOST_PAPER, A.HOST_DATOS}
    assert all(h == A.HOST_PAPER for m, h, *_ in t.llamadas if m == "POST")
    assert "SECRETC1TEST" not in json.dumps(linea) and "PKC1TEST" not in json.dumps(linea)
    assert linea["paquete"]["valor_cuenta"] == 16000 and not linea["paquete"]["simulada"]
    assert (tmp_path / "c1" / "ordenes" / "2026-11-19.jsonl").exists()                    # diario fuera de git
    p = json.loads(Path(linea["paquete"]["fichero"]).read_text())
    assert p["sha256"] == linea["paquete"]["sha256"] == P.hash_paquete(p)
    assert p["cuenta"]["caida_desde_maximo"] == round(16000 / 17000 - 1, 4)


def test_con_ordenes_abiertas_no_se_envia_nada(tmp_path, monkeypatch):
    monkeypatch.setenv("FIN_C1_CLAUDE", str(claude_falso(tmp_path, propuesta(ORDENES_REALES[:1]))))
    t = Falso(abiertas=[{"id": "x"}])
    linea = C.ciclo(cliente(t), hoy=dt.date(2026, 11, 19), registro=[], enviar=True, dormir=lambda s: None)
    assert not [x for x in t.llamadas if x[0] == "POST"] and linea["rechazadas_alpaca"]


def test_ensayo_con_cuenta_real_no_envia(tmp_path, monkeypatch):
    monkeypatch.setenv("FIN_C1_CLAUDE", str(claude_falso(tmp_path, propuesta(ORDENES_REALES))))
    t = Falso()
    linea = C.ciclo(cliente(t), hoy=dt.date(2026, 11, 19), registro=[], enviar=False)
    assert not [x for x in t.llamadas if x[0] == "POST"] and linea["guardia"]["validas"]


def test_seguimiento_de_ordenes_pendientes_del_dia_anterior():
    t = Falso()
    t.ordenes["o9"] = {"id": "o9", "status": "filled", "filled_qty": "3", "filled_avg_price": "50"}
    reg = [{"fecha": "2026-11-18", "ejecuciones": [{"orden_id": "o9", "simbolo": "IWM", "lado": "compra",
                                                     "estado": "new"}]}]
    s = C.seguimiento(cliente(t), reg)
    assert s == [{"fecha_orden": "2026-11-18", "orden_id": "o9", "client_order_id": None, "simbolo": "IWM",
                  "clase": None, "lado": "compra", "estado": "filled", "qty_ejecutada": 3.0, "precio_medio": 50.0,
                  "valor_usd": 150.0, "hora_ejecucion": None}]


def test_cuenta_de_otra_cartera_o_perfil_no_opera(tmp_path, monkeypatch):
    t = Falso()
    assert C.comprobar_cuenta(cliente(t), t.cuenta) is None
    assert "perfil" in C.comprobar_cuenta(cliente(t, "B1"), t.cuenta)
    c = A.Cliente(A.Credenciales(key_id="K", secret="S", perfil="C1", cartera="B0"), transporte=t)
    assert "cartera B0" in C.comprobar_cuenta(c, t.cuenta)
    from src.broker import espejo as E
    E.apunta({"tipo": "orden", "cartera": "B1", "cuenta_huella": E.huella_cuenta(t.cuenta)})
    assert "B1" in C.comprobar_cuenta(cliente(t), t.cuenta)


# ------------------------------------------------------------------ registro y comando
def test_registro_una_linea_por_dia(tmp_path):
    r = tmp_path / "reg.jsonl"
    C.registrar({"fecha": "2026-11-19", "ensayo": False, "opera": False}, r)
    with pytest.raises(ValueError):
        C.registrar({"fecha": "2026-11-19", "ensayo": False}, r)
    assert len(r.read_text().splitlines()) == 1


def test_main_exige_activo_arbol_limpio_y_claves(tmp_path, monkeypatch):
    f = claude_falso(tmp_path)
    monkeypatch.setenv("FIN_C1_CLAUDE", str(f))
    monkeypatch.setattr(C, "ACTIVO", tmp_path / "C1_ACTIVO")
    assert C.main(["--auto"]) == 0 and not (f.parent / "args.txt").exists()     # no activado: ni llama a Claude
    assert C.main(["--registrar"]) == 6
    (tmp_path / "C1_ACTIVO").write_text("")
    monkeypatch.setattr(C, "git", lambda *a: " M algo" if a[0] == "status" else "")
    assert C.main(["--registrar"]) == 5
    monkeypatch.setattr(C, "git", lambda *a: "")
    assert C.main(["--registrar"]) == 7                                             # sin claves C1
    monkeypatch.setattr(P, "leer_registro", lambda ruta=P.LOG: [{"fecha": dt.date.today().isoformat()}])
    assert C.main(["--registrar"]) == 3 and C.main(["--auto"]) == 0
    assert not (f.parent / "args.txt").exists()


def test_main_registra_commitea_y_sube_con_cuenta_falsa(tmp_path, monkeypatch):
    monkeypatch.setenv("FIN_C1_CLAUDE", str(claude_falso(tmp_path, propuesta(ORDENES_REALES[:2]))))
    monkeypatch.setattr(C, "ACTIVO", tmp_path / "C1_ACTIVO")
    (tmp_path / "C1_ACTIVO").write_text("")
    reg = tmp_path / "decisiones_c1.jsonl"
    monkeypatch.setattr(C, "LOG", reg)
    monkeypatch.setattr(P, "LOG", reg)
    llamadas = []
    monkeypatch.setattr(C, "git", lambda *a: llamadas.append(a) or ("abc123" if a[0] == "rev-parse" else ""))
    monkeypatch.setattr(C, "ESPERA_EJECUCION_S", 0)
    t = Falso()
    monkeypatch.setattr(A, "cliente", lambda perfil=None, **kw: cliente(t) if perfil == "C1" else None)
    assert C.main(["--registrar"]) == 0
    linea = json.loads(reg.read_text())
    assert linea["fecha"] == dt.date.today().isoformat() and len(linea["enviadas"]) == 2 and linea["git_head"] == "abc123"
    assert [a[0] for a in llamadas] == ["status", "rev-parse", "add", "commit", "push"]
    assert llamadas[-1] == ("push", "-q", "origin", "main") and "Co-Authored-By" in llamadas[3][-1]


def test_script_ciclo_sin_activo_no_hace_nada(tmp_path):
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "c1_gestor.sh").write_text((REPO / "scripts" / "c1_gestor.sh").read_text())
    r = subprocess.run(["/bin/bash", str(repo / "scripts" / "c1_gestor.sh")], capture_output=True, text=True,
                       env={**os.environ, "FIN_REPO": str(repo), "FIN_LOGDIR": str(tmp_path / "logs"),
                            "FIN_SIN_AVISOS": "1"})
    assert r.returncode == 0
    assert "no activado" in next((tmp_path / "logs").glob("*_c1.log")).read_text()


def test_plist_c1_lun_vie_2030_y_no_instalado():
    import plistlib
    p = plistlib.loads((REPO / "scripts" / "launchd" / "com.financialkb.c1.plist").read_bytes())
    assert p["Label"] == "com.financialkb.c1" and p["ProgramArguments"][-1].endswith("scripts/c1_gestor.sh")
    assert sorted(d["Weekday"] for d in p["StartCalendarInterval"]) == [1, 2, 3, 4, 5]
    assert all((d["Hour"], d["Minute"]) == (20, 30) for d in p["StartCalendarInterval"]) and not p["RunAtLoad"]


def test_mandato_versionado_coincide_con_la_guardia():
    t = C.MANDATO.read_text()
    assert "version: c1-v1" in t and f'"version_mandato": "{G.VERSION_MANDATO}"' in t and "−35 %" in t
    assert "20 órdenes" in t and "poder de compra" in t


# ------------------------------------------------------------------ alpaca.py: métodos nuevos (solo lectura)
def test_metodos_nuevos_de_alpaca_solo_hosts_permitidos():
    t = Falso()
    c = cliente(t)
    c.contrato_opcion(OPC)
    c.historial_cartera(desde=dt.date(2026, 11, 1))
    c.instantaneas_opciones([OPC])
    c.instantaneas_cripto(["BTC/USD"])
    c.activo("BTC/USD")
    rutas = [(m, h, r, p) for m, h, r, p, _ in t.llamadas]
    assert ("GET", A.HOST_PAPER, f"/v2/options/contracts/{OPC}", None) in rutas
    assert ("GET", A.HOST_PAPER, "/v2/account/portfolio/history", {"timeframe": "1D", "start": "2026-11-01"}) in rutas
    assert ("GET", A.HOST_DATOS, "/v1beta1/options/snapshots", {"symbols": OPC, "feed": "indicative"}) in rutas
    assert ("GET", A.HOST_DATOS, "/v1beta3/crypto/us/snapshots", {"symbols": "BTC/USD"}) in rutas
    assert ("GET", A.HOST_PAPER, "/v2/assets/BTCUSD", None) in rutas
    assert all(m == "GET" for m, *_ in rutas)
    with pytest.raises(A.EndpointNoPermitido):
        A.Cliente(A.Credenciales(key_id="K", secret="S", base_url="https://api.alpaca.markets"))
