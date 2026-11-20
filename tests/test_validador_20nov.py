"""Pruebas adversas del Validador (20-nov-2026) sobre la rama de C1/M1/A1: guardias (C1 + `post_validar` de A1),
reasignación de cuentas y comprobación de la cuenta de cada cartera. Sin red, sin claves, sin tocar registros reales."""
from __future__ import annotations

import json
import os
import random

import pytest

from src.broker import a1_guardia as AGd
from src.broker import alpaca as A
from src.broker import c1_guardia as G
from src.broker import espejo as E
from src.paper import a1 as M
from src.paper import c1 as C


@pytest.fixture(autouse=True)
def aislado(tmp_path, monkeypatch):
    for k in list(os.environ):
        if k.startswith(("ALPACA_", "APCA_")):
            monkeypatch.delenv(k)
    monkeypatch.setenv("FIN_ALPACA_ENV", str(tmp_path / "alpaca.env"))
    monkeypatch.setenv("FIN_ALPACA_DIR", str(tmp_path / "alpaca"))
    monkeypatch.setattr(A, "_transporte_requests", lambda *a, **k: (_ for _ in ()).throw(AssertionError("red real")))
    monkeypatch.setattr(AGd, "PARADA", tmp_path / "A1_PARADA")
    monkeypatch.setattr(G, "PARADA", tmp_path / "C1_PARADA")


CM = [{"modelo": "credito", "dice": "verde"}]
CE = [{"fuente": "xbrl", "dice": "calidad alta"}]
SECT = {"AAA": "Tecnología", "BBB": "Tecnología", "CCC": "Salud", "DDD": "Financiero", "EEE": "Energía"}
SIMS = ("AAA", "BBB", "CCC", "DDD", "EEE", "SGOV", "URTH", "GLD")


def ctx(**kw) -> AGd.Contexto:
    base = dict(macro={"credito", "filtro_macro"}, empresa={s: {"xbrl"} for s in SECT},
                universo_compra=set(SECT), sectores=dict(SECT), techo_bolsa=0.9, valor=100_000.0,
                posiciones={}, precios_pos={})
    base.update(kw)
    return AGd.Contexto(**base)


def estado(efectivo=100_000.0, posiciones=None, extra=None) -> G.EstadoCuenta:
    act = {s: {"simbolo": s, "clase": "accion", "negociable": True, "fraccionable": True} for s in SIMS}
    act.update(extra or {})
    return G.EstadoCuenta(efectivo=efectivo, posiciones=posiciones or {}, activos=act,
                          precios={s: 100.0 for s in act})


def salida_a1(ordenes) -> str:
    return json.dumps({"version_mandato": "a1-v1", "fecha": "2026-11-20", "resumen": "r", "lectura_macro": "m",
                       "ordenes": ordenes, "citas_no_operar": CM, "nota_diario": "n", "diario_md": "d"})


def o(simbolo, lado="compra", **kw):
    x = {"simbolo": simbolo, "clase": "accion", "lado": lado, "tipo": "mercado", "razon": "r",
         "cambiaria_de_opinion": "c", "citas_macro": CM, "citas_empresa": CE}
    if lado == "compra" and "cantidad" not in kw:
        x["importe_usd"] = 5_000
    x.update(kw)
    return {k: v for k, v in x.items() if v is not None}


def compras(v: G.Veredicto) -> float:
    return sum(n["coste_estimado_usd"] for n in v.validas if n["lado"] == "compra")


# ------------------------------------------------------------------ post_validar (A1) tras el presupuesto de C1
def test_compra_rechazada_por_a1_devuelve_su_coste_y_el_total_no_pasa_del_efectivo():
    # efectivo 10 000: C1 reparte AAA 9 000 (válida para C1) y BBB 5 000 (sin efectivo); A1 rechaza AAA (10 %: ya
    # tiene 6 000). BBB queda rechazada aunque ya habría sitio: conservador (nunca deja el total por encima del efectivo)
    c = ctx(posiciones={"AAA": 6_000.0})
    v = AGd.validar(salida_a1([o("AAA", importe_usd=9_000), o("BBB")]), estado(efectivo=10_000.0), c, parada=False)
    assert v.validas == []
    mot = {r["indice"]: r["motivo"] for r in v.rechazadas}
    assert "máx. 10 %" in mot[0] and "supera el efectivo" in mot[1]
    assert v.compras_estimadas_usd == 0.0 <= 10_000


def test_ventas_salen_primero_y_el_orden_de_envio_no_cambia_tras_post_validar():
    c = ctx(posiciones={"CCC": 4_000.0})
    v = AGd.validar(salida_a1([o("AAA"), o("CCC", lado="venta", cantidad=10, citas_empresa=CE), o("DDD")]),
                    estado(posiciones={"CCC": 40.0}), c, parada=False)
    assert [n["indice"] for n in v.validas] == [1, 0, 2]          # orden de la guardia de C1: ventas primero
    orden_envio = [n["indice"] for n in sorted(v.validas, key=lambda n: (n["lado"] != "venta", n["indice"]))]
    assert orden_envio == [1, 0, 2]


@pytest.mark.parametrize("semilla", range(300))
def test_propiedad_a1_nunca_apalanca_corta_ni_rompe_limites(semilla):
    rnd = random.Random(semilla)
    V = 100_000.0
    pos_val = {s: rnd.choice([0.0, 0.0, 2_000.0, 6_000.0, 9_500.0]) for s in SECT}
    pos_val.update({"URTH": rnd.choice([0.0, 40_000.0, 70_000.0]), "GLD": rnd.choice([0.0, 15_000.0])})
    pos_qty = {s: v / 100.0 for s, v in pos_val.items() if v}
    efectivo = rnd.choice([0.0, 500.0, 5_000.0, 20_000.0, 60_000.0])
    techo = rnd.choice([0.3, 0.6, 0.9, 1.0])
    ords = []
    for _ in range(rnd.randint(1, 12)):
        s = rnd.choice(list(SIMS) + ["QQQ", "SPY261218C00600000", "BTC/USD"])
        lado = rnd.choice(["compra", "venta"])
        clase = "opcion" if s.startswith("SPY2") else ("cripto" if "/" in s else "accion")
        if lado == "compra":
            ords.append(o(s, clase=clase, importe_usd=rnd.choice([100, 3_000, 8_000, 15_000]),
                          citas_empresa=None if s in AGd.COLCHON else CE))
        else:
            ords.append(o(s, lado="venta", clase=clase, cantidad=rnd.choice([1, 10, 100, 10_000]),
                          citas_empresa=CE if s in SECT else None))
    c = ctx(techo_bolsa=techo, posiciones=dict(pos_val), precios_pos={s: 100.0 for s in pos_val})
    v = AGd.validar(salida_a1(ords), estado(efectivo=efectivo, posiciones=pos_qty), c, parada=False)
    assert compras(v) <= efectivo + 0.01
    assert abs(v.compras_estimadas_usd - compras(v)) < 0.05
    assert all(n["clase"] == "accion" for n in v.validas)
    vendido: dict[str, float] = {}
    for n in v.validas:
        if n["lado"] == "venta":
            vendido[n["simbolo"]] = vendido.get(n["simbolo"], 0) + n["cantidad"]
    assert all(q <= pos_qty.get(s, 0) + 1e-9 for s, q in vendido.items())
    # límites tras el día (ventas a precio de referencia, compras a su coste)
    val = dict(pos_val)
    for s, q in vendido.items():
        val[s] = max(0.0, val.get(s, 0) - q * 100.0)
    for n in v.validas:
        if n["lado"] == "compra":
            val[n["simbolo"]] = val.get(n["simbolo"], 0) + n["coste_estimado_usd"]
            if n["simbolo"] not in AGd.COLCHON:
                assert n["simbolo"] in SECT
    nuevas = {n["simbolo"] for n in v.validas if n["lado"] == "compra" and n["simbolo"] not in AGd.COLCHON}
    for s in nuevas:
        assert val[s] <= 0.10 * V + 1e-6
        assert sum(x for k, x in val.items() if SECT.get(k) == SECT[s]) <= 0.35 * V + 1e-6
    if nuevas:
        assert sum(x for k, x in val.items() if k not in AGd.COLCHON) <= techo * V + 1e-6


@pytest.mark.parametrize("semilla", range(200))
def test_propiedad_c1_compras_le_efectivo_sin_cortos_opciones_solo_compradas(semilla):
    rnd = random.Random(1000 + semilla)
    opc = "SPY261218C00600000"
    extra = {opc: {"simbolo": opc, "clase": "opcion", "negociable": True, "fraccionable": False},
             "BTCUSD": {"simbolo": "BTC/USD", "clase": "cripto", "negociable": True, "fraccionable": True}}
    pos = {k: rnd.choice([0, 0, 2, 50]) for k in ("AAA", opc, "BTCUSD")}
    pos = {k: float(q) for k, q in pos.items() if q}
    efectivo = rnd.choice([0.0, 300.0, 5_000.0, 50_000.0])
    ords = []
    for _ in range(rnd.randint(1, 15)):
        s, clase = rnd.choice([("AAA", "accion"), (opc, "opcion"), ("BTC/USD", "cripto"), ("BBB", "accion")])
        lado = rnd.choice(["compra", "venta"])
        x = {"simbolo": s, "clase": clase, "lado": lado, "razon": "r", "cambiaria_de_opinion": "c"}
        if rnd.random() < 0.5:
            x.update(tipo="limite", cantidad=rnd.choice([1, 3, 60]), precio_limite=rnd.choice([0.5, 5.0, 150.0]))
        elif lado == "compra" and clase != "opcion" and rnd.random() < 0.5:
            x.update(tipo="mercado", importe_usd=rnd.choice([50, 2_000, 30_000]))
        else:
            x.update(tipo="mercado", cantidad=rnd.choice([1, 3, 60]))
        ords.append(x)
    texto = json.dumps({"version_mandato": "c1-v1", "fecha": "2026-11-20", "ordenes": ords, "nota_diario": "n",
                        "resumen": "r"})
    v = G.validar(texto, estado(efectivo=efectivo, posiciones=pos, extra=extra), parada=False)
    assert compras(v) <= efectivo + 0.01 and v.prima_opciones_usd <= efectivo + 0.01
    vend: dict[str, float] = {}
    for n in v.validas:
        if n["lado"] == "venta":
            k = G.clave(n["simbolo"])
            vend[k] = vend.get(k, 0) + n["cantidad"]
        cuerpo = G.cuerpo_alpaca(n, "x")
        if n["clase"] == "opcion":
            assert cuerpo["position_intent"] == ("buy_to_open" if n["lado"] == "compra" else "sell_to_close")
        if n["tipo"] == "limite" and n["lado"] == "compra":
            # lo que se envía nunca cuesta más de lo que estimó la guardia
            mult = 100 if n["clase"] == "opcion" else 1
            assert float(cuerpo["qty"]) * float(cuerpo["limit_price"]) * mult <= n["coste_estimado_usd"] + 0.01
    assert all(q <= pos.get(k, 0) + 1e-9 for k, q in vend.items())


def test_post_validar_de_la_cartera_a1_es_la_guardia_de_a1():
    k = M.cartera(yahoo=False, candidatas={})
    assert k.post_validar is not None and k.campos_orden == AGd.CAMPOS_ORDEN
    paq = {"cuenta": {"valor": 100_000.0, "posiciones": [{"simbolo": "AAA", "valor": 9_000.0, "cantidad": 90}]},
           "filtro_macro": {"techo_bolsa": 0.9}, "macro_disponibles": ["credito"],
           "empresa_disponible": {"AAA": ["xbrl"]}, "universo_compra": ["AAA"], "sectores": {"AAA": "Tecnología"}}
    est = estado()
    ver = G.validar(salida_a1([o("AAA", importe_usd=2_000)]), est, parada=False, leer=AGd.lector(AGd.contexto(paq)),
                    campos_orden=k.campos_orden, extra_orden=k.extra_orden(paq), ruta_parada=AGd.PARADA)
    assert len(ver.validas) == 1                      # la guardia de C1 la acepta …
    ver = k.post_validar(ver, paq, est)
    assert ver.validas == [] and "10 %" in ver.rechazadas[0]["motivo"]   # … y A1 la rechaza (9 000 + 2 000 > 10 %)


# ------------------------------------------------------------------ cuenta de cada cartera (reasignación)
class _T:
    def __init__(self, cuenta):
        self.cuenta = cuenta

    def __call__(self, metodo, url, cab, params, cuerpo, plazo):
        return 200, self.cuenta


def _cli(perfil, cuenta):
    return A.Cliente(A.Credenciales(key_id="K", secret="S", perfil=perfil), transporte=_T(cuenta))


CTA = {"C1": {"id": "id-4jgr", "account_number": "PA1114JGR"}, "A1": {"id": "id-x9f9", "account_number": "PA111X9F9"},
       "M1": {"id": "id-zfjx", "account_number": "PA111ZFJX"}}


def _espejo_real():
    """Historia como la del espejo real del 20-nov tras `reasignar_cuentas --escribir`."""
    h = {k: E.huella_cuenta(v) for k, v in CTA.items()}
    E.apunta({"tipo": "orden", "cartera": "B1", "cuenta_huella": h["C1"], "cuenta": "…4JGR"})
    E.apunta({"tipo": "orden", "cartera": "B0", "cuenta_huella": h["A1"], "cuenta": "…X9F9"})
    E.apunta({"tipo": "reasignacion", "cuenta_huella": h["A1"], "cuenta": "…X9F9", "de": "B0", "a": "D1"})
    E.apunta({"tipo": "reasignacion", "cuenta_huella": h["C1"], "cuenta": "…4JGR", "de": "B1", "a": "C1"})
    E.apunta({"tipo": "reasignacion", "cuenta_huella": h["A1"], "cuenta": "…X9F9", "de": "D1", "a": "A1"})
    return h


def test_cada_cartera_solo_opera_en_su_cuenta():
    _espejo_real()
    for perfil in ("C1", "M1", "A1"):
        for dueno, cu in CTA.items():
            m = C.comprobar_cuenta(_cli(perfil, cu), cu, perfil)
            assert (m is None) == (perfil == dueno), (perfil, dueno, m)


def test_carteras_antiguas_no_operan_en_las_cuentas_nuevas():
    h = _espejo_real()
    reg = E.leer_registro()
    for cartera in ("B0", "B1", "B1P", "D1"):
        for k in ("C1", "A1"):
            cred = A.Credenciales(key_id="K", secret="S", perfil=cartera)
            assert E.puede_ejecutar(cred, cartera, h[k], reg) is not None, (cartera, k)


def test_reasignar_no_tapa_ordenes_del_espejo_posteriores(capsys):
    from scripts import reasignar_cuentas as R
    h = _espejo_real()
    assert R.plan(E.leer_registro()) == []                               # idempotente
    E.apunta({"tipo": "orden", "cartera": "D1", "cuenta_huella": h["A1"], "cuenta": "…X9F9"})   # plist antiguo de D1
    with pytest.raises(LookupError, match="DESPUÉS"):
        R.plan(E.leer_registro())
    assert R.main([]) == 1 and "DESPUÉS" in capsys.readouterr().out
    assert "después de su reasignación" in C.comprobar_cuenta(_cli("A1", CTA["A1"]), CTA["A1"], "A1")


def test_importe_se_redondea_a_centimos_hacia_abajo_y_el_notional_no_supera_el_efectivo():
    t = json.dumps({"version_mandato": "c1-v1", "fecha": "x", "nota_diario": "n", "ordenes": [
        {"simbolo": "AAA", "clase": "accion", "lado": "compra", "importe_usd": 99.995, "razon": "r",
         "cambiaria_de_opinion": "c"}]})
    v = G.validar(t, estado(efectivo=99.995), parada=False)
    n = v.validas[0]
    assert float(G.cuerpo_alpaca(n, "x")["notional"]) == n["coste_estimado_usd"] == 99.99 <= 99.995
