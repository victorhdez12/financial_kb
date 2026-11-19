"""Guardia de C1 (src/broker/c1_guardia.py; spec C1 v1.0 §3): reglas en código, sin red ni claves."""
from __future__ import annotations

import json

import pytest

from src.broker import alpaca as A
from src.broker import c1_guardia as G


def orden(**kw) -> dict:
    o = {"simbolo": "SPY", "clase": "accion", "lado": "compra", "tipo": "mercado", "importe_usd": 1000.0,
         "razon": "Diversificar.", "cambiaria_de_opinion": "Una recesión."}
    o.update(kw)
    return {k: v for k, v in o.items() if v is not None}


def salida(ordenes, **kw) -> str:
    d = {"version_mandato": "c1-v1", "fecha": "2026-11-19", "resumen": "r", "ordenes": ordenes, "nota_diario": "n"}
    d.update(kw)
    return json.dumps(d)


ACT = {"SPY": {"simbolo": "SPY", "clase": "accion", "negociable": True, "fraccionable": True},
       "BRK.A": {"simbolo": "BRK.A", "clase": "accion", "negociable": True, "fraccionable": False},
       "NOPE": {"simbolo": "NOPE", "clase": "accion", "negociable": False, "fraccionable": True},
       "BTCUSD": {"simbolo": "BTC/USD", "clase": "cripto", "negociable": True, "fraccionable": True},
       "SPY261218C00600000": {"simbolo": "SPY261218C00600000", "clase": "opcion", "negociable": True,
                              "fraccionable": False},
       "SPY261218P00500000": {"simbolo": "SPY261218P00500000", "clase": "opcion", "negociable": True,
                              "fraccionable": False}}
PRE = {"SPY": 600.0, "BRK.A": 700000.0, "BTCUSD": 90000.0, "SPY261218C00600000": 20.0, "SPY261218P00500000": 5.0}


def estado(efectivo=10_000.0, posiciones=None, **kw) -> G.EstadoCuenta:
    return G.EstadoCuenta(efectivo=efectivo, posiciones=posiciones or {}, activos=dict(ACT), precios=dict(PRE), **kw)


def val(ordenes, est=None, **kw) -> G.Veredicto:
    return G.validar(salida(ordenes, **kw), est or estado(), parada=False)


# ------------------------------------------------------------------ salida inválida → no opera
@pytest.mark.parametrize("texto", [None, "", "   ", "no es json", "[1, 2]", '{"ordenes": []}',
                                   salida([], version_mandato="c1-v2"), salida([], nota_diario=""),
                                   salida("SPY"), json.dumps({"version_mandato": "c1-v1", "ordenes": []}),
                                   salida([], extra="x"), "Aquí va mi JSON: " + salida([]),
                                   salida([]) + "\n¿Algo más?"])
def test_salida_invalida_no_opera(texto):
    v = G.validar(texto, estado(), parada=False)
    assert not v.opera and v.validas == [] and "inválida" in v.motivo


def test_salida_en_bloque_json_se_admite_y_lista_vacia_es_no_operar_valido():
    v = G.validar("```json\n" + salida([]) + "\n```", estado(), parada=False)
    assert v.opera and v.validas == [] and v.rechazadas == []


def test_parada_no_opera_aunque_la_salida_sea_valida(tmp_path, monkeypatch):
    assert not G.validar(salida([orden()]), estado(), parada=True).opera
    monkeypatch.setattr(G, "PARADA", G.REPO / "research" / "paper" / "C1_PARADA_test_inexistente")
    assert G.validar(salida([orden()]), estado()).opera   # por defecto mira el fichero; no existe
    f = G.REPO / "research" / "paper" / "C1_PARADA_test_inexistente"
    try:
        f.write_text("")
        v = G.validar(salida([orden()]), estado())
        assert not v.opera and "parada" in v.motivo
    finally:
        f.unlink()


def test_sin_estado_de_cuenta_no_opera():
    assert not G.validar(salida([orden()]), None, parada=False).opera


def test_mas_de_20_ordenes_no_opera_nada():
    v = val([orden(importe_usd=10.0)] * 21)
    assert not v.opera and "20" in v.motivo
    assert val([orden(importe_usd=10.0)] * 20).opera
    v = G.validar(salida([orden(importe_usd=10.0)] * 5), estado(ordenes_hoy=16), parada=False)
    assert not v.opera


# ------------------------------------------------------------------ sin apalancamiento
def test_compras_no_superan_el_efectivo_ignorando_poder_de_compra():
    v = val([orden(importe_usd=6000.0), orden(importe_usd=5000.0)])
    assert v.opera and len(v.validas) == 1 and len(v.rechazadas) == 1
    assert "apalancamiento" in v.rechazadas[0]["motivo"]
    assert v.compras_estimadas_usd == 6000.0 <= v.efectivo


def test_compra_por_cantidad_de_mercado_lleva_colchon_y_limite_usa_su_precio():
    # 16 × 600 × 1,01 = 9 696 ≤ 10 000; 17 × 600 × 1,01 = 10 302 > 10 000
    assert len(val([orden(importe_usd=None, cantidad=16)]).validas) == 1
    assert len(val([orden(importe_usd=None, cantidad=17)]).validas) == 0
    assert len(val([orden(importe_usd=None, cantidad=17, tipo="limite", precio_limite=580.0)]).validas) == 1


def test_compra_de_mercado_sin_precio_se_rechaza():
    est = estado()
    est.precios.pop("SPY")
    v = G.validar(salida([orden(importe_usd=None, cantidad=1)]), est, parada=False)
    assert v.validas == [] and "precio" in v.rechazadas[0]["motivo"]


def test_ventas_del_dia_no_liberan_efectivo():
    v = val([orden(lado="venta", importe_usd=None, cantidad=10), orden(importe_usd=9000.0)],
            estado(efectivo=1000.0, posiciones={"SPY": 10}))
    assert [n["lado"] for n in v.validas] == ["venta"]
    assert "apalancamiento" in v.rechazadas[0]["motivo"]


@pytest.mark.parametrize("efectivo", [0.0, -5000.0])
def test_sin_efectivo_o_negativo_no_hay_compras(efectivo):
    v = val([orden(importe_usd=10.0)], estado(efectivo=efectivo))
    assert v.validas == [] and v.compras_estimadas_usd == 0


# ------------------------------------------------------------------ sin cortos
def test_no_se_vende_lo_que_no_se_tiene():
    v = val([orden(lado="venta", importe_usd=None, cantidad=1)])
    assert v.validas == [] and "cortos" in v.rechazadas[0]["motivo"]


def test_no_se_vende_mas_de_lo_que_hay_sumando_ventas_del_dia():
    est = estado(posiciones={"SPY": 10})
    v = G.validar(salida([orden(lado="venta", importe_usd=None, cantidad=6)] * 2), est, parada=False)
    assert len(v.validas) == 1 and "solo hay 4" in v.rechazadas[0]["motivo"]
    v = G.validar(salida([orden(lado="venta", importe_usd=None, cantidad=10)]), est, parada=False)
    assert len(v.validas) == 1


def test_posicion_corta_existente_bloquea_ventas():
    v = val([orden(lado="venta", importe_usd=None, cantidad=1)], estado(posiciones={"SPY": -5}))
    assert v.validas == [] and "corta" in v.rechazadas[0]["motivo"]


def test_venta_por_importe_no_se_admite():
    v = val([orden(lado="venta", importe_usd=100.0)], estado(posiciones={"SPY": 10}))
    assert v.validas == [] and "importe_usd" in v.rechazadas[0]["motivo"]


# ------------------------------------------------------------------ opciones
OPC = "SPY261218C00600000"


def test_opcion_compra_para_abrir_con_prima_hasta_el_efectivo():
    v = val([orden(simbolo=OPC, clase="opcion", importe_usd=None, cantidad=4, tipo="limite", precio_limite=20.0)])
    assert len(v.validas) == 1 and v.prima_opciones_usd == 8000.0
    c = G.cuerpo_alpaca(v.validas[0], "c1-x-00")
    assert c["position_intent"] == "buy_to_open" and c["side"] == "buy" and c["qty"] == "4"
    v = val([orden(simbolo=OPC, clase="opcion", importe_usd=None, cantidad=6, tipo="limite", precio_limite=20.0)])
    assert v.validas == [] and v.prima_opciones_usd == 0   # 12 000 $ de prima > 10 000 $


def test_opcion_venta_solo_para_cerrar_lo_comprado():
    v = val([orden(simbolo=OPC, clase="opcion", lado="venta", importe_usd=None, cantidad=1)])
    assert v.validas == [] and "cerrar" in v.rechazadas[0]["motivo"]      # vender al descubierto: no
    v = val([orden(simbolo=OPC, clase="opcion", lado="venta", importe_usd=None, cantidad=3)],
            estado(posiciones={OPC: 2}))
    assert v.validas == []                                                 # más de lo que se tiene: no
    v = val([orden(simbolo=OPC, clase="opcion", lado="venta", importe_usd=None, cantidad=2)],
            estado(posiciones={OPC: 2}))
    c = G.cuerpo_alpaca(v.validas[0], "c1-x-00")
    assert c["position_intent"] == "sell_to_close" and c["side"] == "sell"


def test_opciones_en_contratos_enteros_y_sin_importe():
    assert val([orden(simbolo=OPC, clase="opcion", importe_usd=None, cantidad=1.5)]).validas == []
    assert val([orden(simbolo=OPC, clase="opcion", importe_usd=100.0)]).validas == []


def test_opcion_de_mercado_usa_ask_por_100():
    v = val([orden(simbolo=OPC, clase="opcion", importe_usd=None, cantidad=4)])   # 4 × 20 × 1,01 × 100 = 8 080
    assert len(v.validas) == 1 and v.prima_opciones_usd == pytest.approx(8080.0)


def test_ningun_cuerpo_de_opcion_puede_ser_sell_to_open():
    for lado in ("compra", "venta"):
        n = {"simbolo": OPC, "clase": "opcion", "lado": lado, "tipo": "mercado", "cantidad": 1.0, "importe_usd": None,
             "precio_limite": None}
        assert G.cuerpo_alpaca(n, "x")["position_intent"] in ("buy_to_open", "sell_to_close")


# ------------------------------------------------------------------ activos
def test_no_negociable_desconocido_o_clase_equivocada_fuera():
    v = val([orden(simbolo="NOPE"), orden(simbolo="ZZZZ"), orden(simbolo="SPY", clase="cripto"),
             orden(simbolo=OPC, clase="accion", importe_usd=None, cantidad=1)])
    assert v.validas == [] and len(v.rechazadas) == 4
    motivos = " | ".join(r["motivo"] for r in v.rechazadas)
    assert "no negociable" in motivos and "desconocido" in motivos and "clase" in motivos


def test_fracciones_solo_en_fraccionables():
    est = estado(efectivo=2_000_000.0)
    assert G.validar(salida([orden(simbolo="BRK.A", importe_usd=None, cantidad=0.5)]), est, parada=False).validas == []
    assert G.validar(salida([orden(simbolo="BRK.A", importe_usd=1000.0)]), est, parada=False).validas == []
    v = G.validar(salida([orden(simbolo="BRK.A", importe_usd=None, cantidad=1)]), est, parada=False)
    assert len(v.validas) == 1 and v.validas[0]["simbolo_alpaca"] == "BRK.A"


def test_cripto_compra_por_importe_y_venta_de_lo_que_hay():
    v = val([orden(simbolo="BTC/USD", clase="cripto", importe_usd=500.0)])
    c = G.cuerpo_alpaca(v.validas[0], "c1-x-00")
    assert c == {"symbol": "BTC/USD", "side": "buy", "type": "market", "time_in_force": "gtc",
                 "client_order_id": "c1-x-00", "notional": "500.00"}
    v = val([orden(simbolo="BTC/USD", clase="cripto", lado="venta", importe_usd=None, cantidad=0.01)],
            estado(posiciones={"BTCUSD": 0.02}))
    assert len(v.validas) == 1


# ------------------------------------------------------------------ forma de cada orden
@pytest.mark.parametrize("cambio", [
    {"razon": ""}, {"razon": None}, {"cambiaria_de_opinion": "  "}, {"razon": "x" * 801}, {"lado": "corto"},
    {"clase": "futuro"}, {"tipo": "stop"}, {"simbolo": "spy; rm -rf"}, {"simbolo": ""}, {"importe_usd": -5.0},
    {"importe_usd": 0.5}, {"importe_usd": "100"}, {"importe_usd": True}, {"cantidad": 1},
    {"importe_usd": None}, {"tipo": "limite"}, {"precio_limite": 600.0}, {"apalancamiento": 2},
    {"importe_usd": float("nan")}, {"importe_usd": float("inf")},
])
def test_ordenes_mal_formadas_se_rechazan_una_a_una(cambio):
    o = {k: x for k, x in {**orden(), **cambio}.items() if x is not None}
    v = val([o, orden(importe_usd=100.0)])
    assert v.opera and len(v.validas) == 1 and len(v.rechazadas) == 1 and v.rechazadas[0]["indice"] == 0


def test_limite_lleva_precio_y_formato_alpaca():
    v = val([orden(importe_usd=None, cantidad=2.5, tipo="limite", precio_limite=590.123)])
    c = G.cuerpo_alpaca(v.validas[0], "c1-x-00")
    assert c == {"symbol": "SPY", "side": "buy", "type": "limit", "time_in_force": "day", "client_order_id": "c1-x-00",
                 "qty": "2.5", "limit_price": "590.12"}


# ------------------------------------------------------------------ solo paper
def test_comprobar_cliente_solo_paper():
    c = A.Cliente(A.Credenciales(key_id="PKX", secret="S"), transporte=lambda *a: (200, {}))
    G.comprobar_cliente(c)
    with pytest.raises(A.EndpointNoPermitido):
        A.Cliente(A.Credenciales(key_id="PKX", secret="S", base_url="https://api.alpaca.markets"))
    c.base = "https://api.alpaca.markets"   # aunque alguien lo cambie después
    with pytest.raises(A.EndpointNoPermitido):
        G.comprobar_cliente(c)
