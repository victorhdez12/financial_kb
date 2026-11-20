"""A1 «selección de acciones» (spec A1 v1.0): candidatas XBRL, filtro macro, sombra, guardia (cita doble, solo
acciones, 10 % por valor, 35 % por sector, 30 valores, techo de bolsa), paquete, ciclo con un `claude` FALSO, registro
(exige A1_ACTIVO), reasignación de cuentas, configuración de cuentas y automatización. Sin red, sin claves y sin tocar
los registros reales."""
from __future__ import annotations

import datetime as dt
import json
import os
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.broker import a1_guardia as AGd
from src.broker import alpaca as A
from src.broker import c1_guardia as G
from src.broker import espejo as E
from src.paper import a1 as M
from src.paper import a1_candidatas as K
from src.paper import a1_paquete as P
from src.paper import a1_sombra as SA
from src.paper import agente as AG
from src.paper import c1 as C
from src.paper import c1_paquete as CP
from src.paper import m1_paquete as MP
from src.paper import m1_sombra as S
from tests.agente_falso import archivo_y_repo, claude_falso

REPO = M.REPO
REALES = [REPO / "research" / "paper" / x for x in ("decisiones_a1.jsonl", "decisiones_a1_sombra.jsonl", "A1_PARADA",
                                                     "A1_ACTIVO")]
SIGNAL = {"asof": "2026-11-17", "regime": {"quadrant": "Goldilocks", "G_state": "up", "I_state": "down"},
          "credit": {"light": "verde", "reds": 0}, "liquidity": {"state": "escasa"},
          "debt_cycle": {"phase": "expansión temprana"}, "long_cycle": {"stage": "tardío"},
          "escenarios": {"emision": "2026-11-17", "paises": {"USA": {"abanicos": {"bolsa": {"p_neg": 0.364}}}}}}
SECTORES = {"AAA": "Tecnología", "BBB": "Tecnología", "CCC": "Salud", "DDD": "Financiero", "EEE": "Energía",
            "MSFT": "Tecnología"}


def candidatas_falsas() -> dict:
    emp = {}
    for i, (t, s) in enumerate(SECTORES.items()):
        emp[t] = {"cik": i + 1, "nombre": t, "sector": s, "anio_fiscal": 2025, "calidad": round(0.9 - 0.1 * i, 2),
                  "rango": i + 1, "metricas": {"roa": 0.1, "margen_operativo": 0.2, "crec_ingresos": 0.1,
                                               "apalancamiento": 0.4}, "valores": {}}
    emp["ZZZ"] = {"cik": 99, "nombre": "sin datos", "sector": None, "anio_fiscal": None, "calidad": None,
                  "metricas": {k: None for k in ("roa", "margen_operativo", "crec_ingresos", "apalancamiento")}}
    return {"version": K.VERSION, "fecha_datos": "2026-10-07", "fuente": "test", "reglas": "test",
            "universo": sorted(emp), "empresas": emp, "sin_datos": []}


@pytest.fixture(autouse=True)
def aislado(tmp_path, monkeypatch):
    for k in list(os.environ):
        if k.startswith(("ALPACA_", "APCA_")):
            monkeypatch.delenv(k)
    monkeypatch.setenv("FIN_ALPACA_ENV", str(tmp_path / "alpaca.env"))
    monkeypatch.setenv("FIN_ALPACA_DIR", str(tmp_path / "alpaca"))
    monkeypatch.setenv("FIN_A1_DIR", str(tmp_path / "a1"))
    a, r = archivo_y_repo(tmp_path)
    monkeypatch.setenv("FIN_DATA_ROOT", str(a))
    monkeypatch.setenv("FIN_AGENTE_REPO", str(r))
    monkeypatch.setattr(A, "_transporte_requests", lambda *a, **k: (_ for _ in ()).throw(AssertionError("red real")))
    monkeypatch.setattr(CP, "cierres_warehouse", lambda X=None: {"fuente": "test", "activos": {}})
    monkeypatch.setattr(CP, "alertas", lambda hoy: [{"ticker": "MSFT", "frase": "volumen anormal"}])
    monkeypatch.setattr(CP, "resumen_panel", lambda s: ["EE. UU. en Goldilocks"])
    monkeypatch.setattr(CP, "diagnosticos", lambda hoy, carpeta=None: [])
    monkeypatch.setattr(CP, "ultimo_signal", lambda: (SIGNAL, "x_signal.json"))
    monkeypatch.setattr(S, "E1_VIVO", tmp_path / "e1_vivo.jsonl")
    monkeypatch.setattr(MP, "K1_VIVO", tmp_path / "k1_vivo.jsonl")
    monkeypatch.setattr(S, "ARCHIVO_PRECIOS", tmp_path / "no_existe.parquet")
    monkeypatch.setattr(SA, "LOG", tmp_path / "sombra_a1.jsonl")
    monkeypatch.setattr(AGd, "PARADA", tmp_path / "A1_PARADA")
    monkeypatch.setattr(P, "mis_activos", lambda: ["MSFT"])
    monkeypatch.setattr(AG, "ruta_diario", lambda cartera, fecha, repo=None: tmp_path / "obsidian" / cartera / f"{fecha}.md")
    monkeypatch.setattr(S, "cierres_yahoo", lambda simbolos, desde: precios_falsos(simbolos))
    antes = [x.read_bytes() if x.exists() else None for x in REALES]
    yield
    assert [x.read_bytes() if x.exists() else None for x in REALES] == antes, "un test tocó un registro real de A1"


def precios_falsos(simbolos, dias=8, fin="2026-11-19") -> pd.DataFrame:
    idx = pd.bdate_range(end=fin, periods=dias)
    return pd.DataFrame({s: 100.0 * (1.001 ** np.arange(dias)) for s in simbolos}, index=idx)


# ------------------------------------------------------------------ candidatas XBRL
def hecho(val, frame, end, filed="2026-02-01"):
    return {"val": val, "frame": frame, "end": end, "filed": filed, "form": "10-K"}


def companyfacts(ing=(100, 120), ni=12, op=30, act=100, pas=40, viejo_revenues=False):
    g = {"RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            hecho(ing[0], "CY2024", "2024-12-31"), hecho(ing[1], "CY2025", "2025-12-31")]}},
         "NetIncomeLoss": {"units": {"USD": [hecho(ni, "CY2025", "2025-12-31")]}},
         "OperatingIncomeLoss": {"units": {"USD": [hecho(op, "CY2025", "2025-12-31")]}},
         "Assets": {"units": {"USD": [hecho(act, "CY2025Q4I", "2025-12-31")]}},
         "Liabilities": {"units": {"USD": [hecho(pas, "CY2025Q4I", "2025-12-31")]}}}
    if viejo_revenues:   # concepto abandonado con años viejos: no debe mezclarse con el nuevo
        g["Revenues"] = {"units": {"USD": [hecho(5, "CY2016", "2016-12-31")]}}
    return {"entityName": "X", "facts": {"us-gaap": g}}


def test_extraer_y_metricas_usan_el_concepto_mas_reciente():
    x = K.extraer(companyfacts(viejo_revenues=True))
    assert x["ingresos"]["anio"] == 2025 and x["ingresos"]["valor"] == 120 and x["ingresos"]["anterior"] == 100
    m = K.metricas(x)
    assert m == {"roa": 0.12, "margen_operativo": 0.25, "crec_ingresos": 0.2, "apalancamiento": 0.4}


def test_puntuar_percentiles_minimo_de_metricas_y_anio_reciente():
    filas = {"A": {"anio_fiscal": 2025, "metricas": {"roa": 0.3, "margen_operativo": 0.3, "crec_ingresos": 0.3,
                                                     "apalancamiento": 0.1}},
             "B": {"anio_fiscal": 2025, "metricas": {"roa": 0.1, "margen_operativo": 0.1, "crec_ingresos": 0.1,
                                                     "apalancamiento": 0.9}},
             "C": {"anio_fiscal": 2025, "metricas": {"roa": 0.2, "margen_operativo": None, "crec_ingresos": None,
                                                     "apalancamiento": 0.5}},
             "D": {"anio_fiscal": 2021, "metricas": {"roa": 0.9, "margen_operativo": 0.9, "crec_ingresos": 0.9,
                                                     "apalancamiento": 0.0}}}
    K.puntuar(filas, 2026)
    assert filas["A"]["calidad"] == 1.0 and filas["B"]["calidad"] == 0.0 and filas["A"]["rango"] == 1
    assert filas["C"]["calidad"] is None and "2 de 4" in filas["C"]["motivo_sin_calidad"]
    assert filas["D"]["calidad"] is None and "reciente" in filas["D"]["motivo_sin_calidad"]


def test_sector_sic_y_mejores_con_tope_por_sector():
    assert K.sector_sic("3571") == "Tecnología" and K.sector_sic("6022") == "Financiero"
    assert K.sector_sic("2834") == "Salud" and K.sector_sic(None) is None
    c = candidatas_falsas()
    assert K.mejores(c, 3) == ["AAA", "BBB", "CCC"]
    assert K.mejores(c, 3, max_por_sector=1) == ["AAA", "CCC", "DDD"]


def test_calcular_con_ficheros_sec_y_cache(tmp_path):
    raiz = tmp_path / "arch"
    r = K.rutas(raiz)
    for p in r.values():
        p.parent.mkdir(parents=True, exist_ok=True)
    r["sp500"].write_text("ticker,start_date,end_date\nAAA,2000-01-01,\nOLD,2000-01-01,2010-01-01\nBRK.B,2000-01-01,\n")
    r["tickers"].write_text(json.dumps({"0": {"cik_str": 1, "ticker": "AAA"}, "1": {"cik_str": 2, "ticker": "BRK-B"},
                                        "2": {"cik_str": 3, "ticker": "MSFT"}}))
    with zipfile.ZipFile(r["hechos"], "w") as z:
        z.writestr("CIK0000000001.json", json.dumps(companyfacts()))
        z.writestr("CIK0000000002.json", json.dumps(companyfacts(ni=2)))
    with zipfile.ZipFile(r["envios"], "w") as z:
        z.writestr("CIK0000000001.json", json.dumps({"sic": "3571"}))
        z.writestr("CIK0000000002.json", json.dumps({"sic": "6331"}))
    c = K.calcular(["MSFT"], raiz=raiz, hoy=dt.date(2026, 11, 20))
    assert c["universo"] == ["AAA", "BRK.B", "MSFT"] and set(c["empresas"]) == {"AAA", "BRK.B"}
    assert c["empresas"]["AAA"]["sector"] == "Tecnología" and c["empresas"]["BRK.B"]["sector"] == "Financiero"
    assert c["sin_datos"] == [{"ticker": "MSFT", "motivo": "sin XBRL en companyfacts.zip"}]
    assert list((tmp_path / "a1" / "candidatas").glob("*.json"))
    assert K.calcular(["MSFT"], raiz=raiz, hoy=dt.date(2026, 11, 20)) == c      # caché
    assert "error" in K.calcular([], raiz=tmp_path / "vacio")


# ------------------------------------------------------------------ filtro macro y sombra
def entradas(**kw) -> dict:
    x = {"cuadrante": "Goldilocks", "G": None, "I": "down", "credito": "verde", "liquidez": "neutral",
         "int11_p_perdida_bolsa": 0.40, "e1_p_recesion": None}
    x.update(kw)
    return x


def test_filtro_macro_base_90_suelo_30_techo_100_y_m1_sin_cambios():
    assert SA.filtro_macro(entradas())["techo_bolsa"] == 0.90
    assert SA.filtro_macro(entradas(G="up", liquidez="abundante"))["techo_bolsa"] == 1.0
    f = SA.filtro_macro(entradas(credito="rojo", e1_p_recesion=0.6, G="down", int11_p_perdida_bolsa=0.7))
    assert f["techo_bolsa"] == 0.30 and any("acotado" in a for a in f["ajustes"])
    assert SA.filtro_macro(entradas(credito="ámbar"))["techo_bolsa"] == 0.80
    assert S.bolsa(entradas(G=None))[0] == 0.60                                  # M1 intacta


def test_sombra_cesta_mensual_pesos_y_valoracion():
    c = candidatas_falsas()
    ln = SA.linea_del_dia("2026-11-20", entradas(), c, [], None, "test")
    w = ln["objetivo"]["pesos"]
    assert ln["objetivo"]["cesta"] == ["AAA", "BBB", "CCC", "DDD", "EEE", "MSFT"]
    assert abs(sum(w.values()) - 1) < 1e-6 and abs(w["SGOV"] - 0.10 * (1 - SA.COLCHON)) < 1e-6
    assert abs(w["AAA"] - 0.90 * (1 - SA.COLCHON) / 6) < 1e-6
    # mismo mes: la cesta no cambia aunque cambien las candidatas; mes nuevo: se recalcula
    c2 = candidatas_falsas()
    c2["empresas"]["AAA"]["calidad"] = None
    ln2 = SA.linea_del_dia("2026-11-23", entradas(), c2, [ln], precios_falsos(["AAA", "BBB", "CCC", "DDD", "EEE", "MSFT",
                                                                               "SGOV"], fin="2026-11-20"), "test")
    assert ln2["objetivo"]["cesta"] == ln["objetivo"]["cesta"] and ln2["cesta_fijada"] == "2026-11-20"
    assert ln2["valoracion"]["hasta"] == "2026-11-20" and ln2["valoracion"]["rebalanceos"] == 1
    ln3 = SA.linea_del_dia("2026-12-01", entradas(), c2, [ln, ln2], None, "test")
    assert "AAA" not in ln3["objetivo"]["cesta"] and ln3["cesta_fijada"] == "2026-12-01"
    r = Path(os.environ["FIN_A1_DIR"]) / "s.jsonl"
    SA.registrar(ln, r)
    with pytest.raises(ValueError):
        SA.registrar(ln, r)


# ------------------------------------------------------------------ guardia
CM = [{"modelo": "credito", "dice": "verde (signal 2026-11-17)"}]
CE = [{"fuente": "xbrl", "dice": "calidad 0,9, ROA 10 %"}]


def ctx(**kw) -> AGd.Contexto:
    base = dict(macro={"cuadrante", "credito", "filtro_macro"},
                empresa={"AAA": {"xbrl"}, "BBB": {"xbrl"}, "CCC": {"xbrl"}, "DDD": {"xbrl"},
                         "MSFT": {"xbrl", "form4", "ficha"}},
                universo_compra={"AAA", "BBB", "CCC", "DDD", "MSFT"}, sectores=dict(SECTORES),
                techo_bolsa=0.90, valor=100_000.0, posiciones={}, precios_pos={})
    base.update(kw)
    return AGd.Contexto(**base)


def estado(efectivo=100_000.0, posiciones=None) -> G.EstadoCuenta:
    sim = ("AAA", "BBB", "CCC", "DDD", "MSFT", "SGOV", "URTH", "GLD", "QQQ")
    return G.EstadoCuenta(efectivo=efectivo, posiciones=posiciones or {},
                          activos={s: {"simbolo": s, "clase": "accion", "negociable": True, "fraccionable": True}
                                   for s in sim},
                          precios={s: 100.0 for s in sim})


def salida(ordenes=None, **kw) -> str:
    d = {"version_mandato": "a1-v1", "fecha": "2026-11-20", "resumen": "r", "lectura_macro": "techo 90 %",
         "ordenes": ordenes or [], "citas_no_operar": CM, "nota_diario": "n", "diario_md": "## d"}
    d.update(kw)
    return json.dumps(d, ensure_ascii=False)


def orden(simbolo="AAA", ce=CE, cm=CM, **kw):
    o = {"simbolo": simbolo, "clase": "accion", "lado": "compra", "tipo": "mercado", "importe_usd": 5000,
         "razon": "r", "cambiaria_de_opinion": "c"}
    if ce is not None:
        o["citas_empresa"] = ce
    if cm is not None:
        o["citas_macro"] = cm
    o.update(kw)
    return o


def test_guardia_a1_cita_doble_solo_acciones_y_universo():
    ords = [orden("AAA"),                                                          # 0 válida
            orden("BBB", ce=None),                                                 # 1 sin cita de empresa
            orden("CCC", cm=None),                                                 # 2 sin cita macro
            orden("DDD", ce=[{"fuente": "form4", "dice": "compras"}]),             # 3 fuente sin datos para DDD
            orden("AAA", cm=[{"modelo": "e1", "dice": "x"}]),                       # 4 macro sin salida hoy
            orden("SPY261218C00600000", clase="opcion", cantidad=1, importe_usd=None, tipo="limite",
                  precio_limite=5.0),                                              # 5 opción
            orden("BTC/USD", clase="cripto"),                                      # 6 cripto
            orden("QQQ"),                                                          # 7 fuera del universo
            orden("SGOV", ce=None),                                                # 8 colchón: basta macro
            orden("MSFT", ce=[{"fuente": "form4", "dice": "1 compra de directivo"}])]   # 9 válida (form4 de MSFT)
    v = AGd.validar(salida(ords), estado(), ctx(), parada=False)
    assert v.opera and [n["indice"] for n in v.validas] == [0, 8, 9]
    mot = {r["indice"]: r["motivo"] for r in v.rechazadas}
    assert "citas_empresa" in mot[1] and "citas_macro" in mot[2] and "hoy no tiene datos" in mot[3]
    assert "hoy no tiene datos" in mot[4] and "sin opciones" in mot[5] and "sin opciones ni cripto" in mot[6]
    assert "fuera del universo" in mot[7]


def test_venta_de_heredadas_sin_datos_de_empresa_basta_la_macro_y_sin_cortos():
    c = ctx(posiciones={"URTH": 70_000.0, "GLD": 15_000.0}, precios_pos={"URTH": 200.0, "GLD": 250.0})
    ords = [orden("URTH", ce=None, lado="venta", importe_usd=None, cantidad=10),
            orden("GLD", ce=None, cm=None, lado="venta", importe_usd=None, cantidad=5),   # sin macro
            orden("AAA", ce=None, lado="venta", importe_usd=None, cantidad=1),            # con datos: exige empresa
            orden("URTH", ce=None, lado="venta", importe_usd=None, cantidad=10_000)]      # más de lo que hay
    v = AGd.validar(salida(ords), estado(posiciones={"URTH": 350.0, "GLD": 60.0}), c, parada=False)
    assert [n["indice"] for n in v.validas] == [0]
    mot = {r["indice"]: r["motivo"] for r in v.rechazadas}
    assert "citas_macro" in mot[1] and "citas_empresa" in mot[2] and "sin cortos" in mot[3]


def test_limites_10_por_valor_35_por_sector_y_techo_de_bolsa():
    # 10 %: AAA ya tiene 6 000 $; comprar 5 000 la deja en 11 %
    v = AGd.validar(salida([orden("AAA")]), estado(), ctx(posiciones={"AAA": 6_000.0}), parada=False)
    assert not v.validas and "máx. 10 % por valor" in v.rechazadas[0]["motivo"] and v.compras_estimadas_usd == 0
    # 35 % por sector: Tecnología ya tiene 30 000 (MSFT); BBB 5 000 → 35 % justo, AAA 5 000 más → 40 %
    c = ctx(posiciones={"MSFT": 10_000.0, "ZZ1": 0.0}, sectores={**SECTORES, "XT1": "Tecnología", "XT2": "Tecnología"})
    c.posiciones.update({"XT1": 10_000.0, "XT2": 10_000.0})
    v = AGd.validar(salida([orden("BBB"), orden("AAA")]), estado(), c, parada=False)
    assert [n["simbolo"] for n in v.validas] == ["BBB"] and "máx. 35 % por sector" in v.rechazadas[0]["motivo"]
    # las ventas válidas del día liberan sitio en el sector
    v = AGd.validar(salida([orden("MSFT", lado="venta", importe_usd=None, cantidad=50), orden("BBB"), orden("AAA")]),
                    estado(posiciones={"MSFT": 100.0}), c, parada=False)
    assert [n["simbolo"] for n in v.validas] == ["MSFT", "BBB", "AAA"]
    # techo de bolsa 30 %: con 28 000 $ en heredadas, una compra de 5 000 lo rompe; el colchón no cuenta
    c = ctx(techo_bolsa=0.30, posiciones={"URTH": 28_000.0, "IEI": 50_000.0})
    v = AGd.validar(salida([orden("AAA"), orden("SGOV", ce=None)]), estado(), c, parada=False)
    assert [n["simbolo"] for n in v.validas] == ["SGOV"] and "filtro macro" in v.rechazadas[0]["motivo"]
    # sin techo (sin filtro macro): no compra acciones
    v = AGd.validar(salida([orden("AAA")]), estado(), ctx(techo_bolsa=None), parada=False)
    assert not v.validas and "sin filtro macro" in v.rechazadas[0]["motivo"]


def test_limite_de_30_valores_y_sin_sector():
    pos = {f"X{i:02d}": 3_000.0 for i in range(30)}
    sec = {**SECTORES, **{f"X{i:02d}": ["Salud", "Industria", "Energía", "Materiales"][i % 4] for i in range(30)}}
    v = AGd.validar(salida([orden("AAA", importe_usd=1000)]), estado(), ctx(posiciones=pos, sectores=sec, techo_bolsa=1.0),
                    parada=False)
    assert not v.validas and "máx. 30 valores" in v.rechazadas[0]["motivo"]
    v = AGd.validar(salida([orden("AAA")]), estado(), ctx(sectores={}), parada=False)
    assert "sin sector" in v.rechazadas[0]["motivo"]


@pytest.mark.parametrize("cambio, texto", [
    ({"citas_no_operar": []}, "citas_no_operar"),
    ({"citas_no_operar": [{"modelo": "e1", "dice": "x"}]}, "citas_no_operar"),
    ({"lectura_macro": ""}, "lectura_macro"),
    ({"diario_md": " "}, "diario_md"),
    ({"version_mandato": "m1-v1"}, "a1-v1"),
    ({"declaracion_modelos": []}, "campos no previstos"),
])
def test_salida_que_incumple_el_mandato_no_opera(cambio, texto):
    v = AGd.validar(salida(**cambio), estado(), ctx(), parada=False)
    assert not v.opera and texto in v.motivo


def test_parada_y_mandato_coincide_con_la_guardia():
    assert not AGd.validar(salida(), estado(), ctx(), parada=True).opera
    t = M.MANDATO.read_text()
    assert "version: a1-v1" in t and f'"version_mandato": "{AGd.VERSION_MANDATO}"' in t and "−35 %" in t
    for m in AGd.MACRO:
        assert f"`{m}`" in t
    for f in AGd.FUENTES_EMPRESA:
        assert f"`{f}`" in t
    assert "10 %" in t and "35 %" in t and "30 valores" in t and "Previo escéptico" in t


# ------------------------------------------------------------------ paquete
def test_paquete_a1_contexto_de_la_guardia(tmp_path):
    p = P.recoger(None, dt.date(2026, 11, 20), registro=[], sombra_previas=[], candidatas=candidatas_falsas())
    assert p["mandato"] == "a1-v1" and p["version"] == "a1-paquete-1" and p["cuenta"]["simulada"]
    assert set(p["macro_disponibles"]) == {"cuadrante", "credito", "liquidez", "ciclo_deuda", "int11", "filtro_macro"}
    assert p["filtro_macro"]["techo_bolsa"] == 0.95                               # escasa −5, G↑ +10
    assert p["universo_compra"] == ["AAA", "BBB", "CCC", "DDD", "EEE", "MSFT"]    # ZZZ sin calidad: fuera
    assert p["empresa_disponible"]["MSFT"] == ["alertas", "ficha", "xbrl"] and "ZZZ" not in p["empresa_disponible"]
    assert p["sectores"]["CCC"] == "Salud" and p["sha256"] == CP.hash_paquete(p)
    assert p["sombra"]["objetivo"]["techo_bolsa"] == 0.95 and "AAA" in p["cierres_simulacion"]["activos"]
    c = AGd.contexto(p)
    assert c.techo_bolsa == 0.95 and "filtro_macro" in c.macro and c.valor == 100_000.0


# ------------------------------------------------------------------ ciclo con claude falso
def test_ciclo_a1_ensayo_valida_rechaza_y_anota_citas(tmp_path, monkeypatch):
    ords = [orden("AAA", importe_usd=8_000), orden("BBB", importe_usd=20_000), orden("CCC", ce=None)]
    f = claude_falso(tmp_path, salida(ords))
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(f))
    linea = M.ciclo(None, hoy=dt.date(2026, 11, 20), registro=[], candidatas=candidatas_falsas())
    assert linea["perfil"] == "A1" and linea["modo"] == "agente" and linea["mandato"]["version"] == "a1-v1"
    assert [n["simbolo"] for n in linea["guardia"]["validas"]] == ["AAA"]
    mot = {r["indice"]: r["motivo"] for r in linea["rechazadas"]}
    assert "máx. 10 %" in mot[1] and "citas_empresa" in mot[2]
    u = linea["uso_citas"]["ordenes"][0]
    assert u["macro"] == ["credito"] and u["empresa"] == ["xbrl"]
    assert Path(linea["diario"]).name == "diario.md"
    assert M.sombra_de(linea)["filtro"]["techo_bolsa"] == 0.95
    stdin = (f.parent / "stdin.txt").read_text()
    assert "A1" in stdin and "universo_compra" in stdin
    aj = json.loads((Path(linea["paquete"]["fichero"]).parent / "ajustes.json").read_text())
    deny = " ".join(aj["permissions"]["deny"])
    assert "Carteras/C1" in deny and "Carteras/M1" in deny and "Carteras/A1" not in deny   # no lee los de C1/M1


def test_ciclo_a1_con_parada_no_llama_a_claude(tmp_path, monkeypatch):
    f = claude_falso(tmp_path, salida())
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(f))
    (tmp_path / "A1_PARADA").write_text("supervisor")
    linea = M.ciclo(None, hoy=dt.date(2026, 11, 20), registro=[], candidatas=candidatas_falsas())
    assert not linea["opera"] and "A1_PARADA" in linea["motivo_no_opera"] and not (f.parent / "args.txt").exists()


def test_main_a1_exige_activo_arbol_limpio_y_claves(tmp_path, monkeypatch):
    f = claude_falso(tmp_path, salida())
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(f))
    monkeypatch.setattr(M, "ACTIVO", tmp_path / "A1_ACTIVO")
    assert M.main(["--auto"]) == 0 and not (f.parent / "args.txt").exists()
    assert M.main(["--registrar"]) == 6
    (tmp_path / "A1_ACTIVO").write_text("")
    monkeypatch.setattr(M, "git", lambda *a: " M algo" if a[0] == "status" else "")
    assert M.main(["--registrar"]) == 5
    monkeypatch.setattr(M, "git", lambda *a: "")
    assert M.main(["--registrar"]) == 7
    assert not (f.parent / "args.txt").exists()


def _cliente_a1():
    from tests.test_c1 import Falso
    t = Falso(efectivo="10000", posiciones=[
        {"symbol": "URTH", "qty": "50", "asset_class": "us_equity", "market_value": "10000", "current_price": "200"}])
    t.cuenta["equity"] = "100000"
    return A.Cliente(A.Credenciales(key_id="PKA1TEST", secret="SECRETA1TEST", perfil="A1"), transporte=t), t


def test_main_a1_registra_decision_y_sombra(tmp_path, monkeypatch):
    ords = [orden("AAA", importe_usd=500), orden("URTH", ce=None, lado="venta", importe_usd=None, cantidad=5)]
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(claude_falso(tmp_path, salida(ords))))
    monkeypatch.setattr(M, "ACTIVO", tmp_path / "A1_ACTIVO")
    (tmp_path / "A1_ACTIVO").write_text("")
    reg = tmp_path / "decisiones_a1.jsonl"
    monkeypatch.setattr(M, "LOG", reg)
    monkeypatch.setattr(P, "LOG", reg)
    llamadas = []
    monkeypatch.setattr(M, "git", lambda *a: llamadas.append(a) or ("abc123" if a[0] == "rev-parse" else ""))
    monkeypatch.setattr(C, "ESPERA_EJECUCION_S", 0)
    cl, t = _cliente_a1()
    monkeypatch.setattr(A, "cliente", lambda perfil=None, **kw: cl if perfil == "A1" else None)
    monkeypatch.setattr(S, "cierres_alpaca", lambda c, simbolos, desde, hasta: precios_falsos(simbolos))
    real = P.recoger
    monkeypatch.setattr(P, "recoger", lambda *a, **k: real(*a, **{**k, "candidatas": candidatas_falsas()}))
    assert M.main(["--registrar"]) == 0
    linea = json.loads(reg.read_text())
    assert linea["perfil"] == "A1" and len(linea["enviadas"]) == 2
    assert all(e["client_order_id"].startswith("a1-") for e in linea["enviadas"])
    assert linea["enviadas"][0]["lado"] == "venta"                                 # ventas primero
    sombra = SA.leer_registro()
    assert len(sombra) == 1 and sombra[0]["git_head"] == "abc123"
    add = next(a for a in llamadas if a[0] == "add")
    assert str(reg) in add and str(SA.LOG) in add and llamadas[-1] == ("push", "-q", "origin", "main")
    assert "SECRETA1TEST" not in reg.read_text() and "PKA1TEST" not in reg.read_text()


def test_main_a1_no_opera_en_cuenta_con_ordenes_del_espejo_sin_reasignacion(tmp_path, monkeypatch):
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(claude_falso(tmp_path, salida())))
    monkeypatch.setattr(M, "ACTIVO", tmp_path / "A1_ACTIVO")
    (tmp_path / "A1_ACTIVO").write_text("")
    monkeypatch.setattr(M, "git", lambda *a: "")
    cl, t = _cliente_a1()
    monkeypatch.setattr(A, "cliente", lambda perfil=None, **kw: cl if perfil == "A1" else None)
    h = E.huella_cuenta(t.cuenta)
    E.apunta({"tipo": "orden", "cartera": "D1", "cuenta_huella": h, "cuenta": "…8888"})
    assert M.main(["--registrar"]) == 9
    # reasignación declarada D1 → A1: las órdenes anteriores ya no cuentan
    E.apunta({"tipo": "reasignacion", "cuenta_huella": h, "cuenta": "…8888", "de": "D1", "a": "A1"})
    assert C.comprobar_cuenta(cl, t.cuenta, "A1") is None
    # pero una orden del espejo posterior vuelve a bloquear, y el espejo de D1 ya no opera en esa cuenta
    assert "reasignó a A1" in E.puede_ejecutar(A.Credenciales(key_id="k", secret="s", perfil="D1"), "D1", h,
                                                E.leer_registro())
    E.apunta({"tipo": "orden", "cartera": "D1", "cuenta_huella": h, "cuenta": "…8888"})
    assert "después de su reasignación" in C.comprobar_cuenta(cl, t.cuenta, "A1")


# ------------------------------------------------------------------ reasignación y configuración de cuentas
def test_reasignar_cuentas_en_seco_y_escribir_idempotente(monkeypatch, capsys):
    from scripts import reasignar_cuentas as R
    E.apunta({"tipo": "orden", "cartera": "B1", "cuenta_huella": "h4", "cuenta": "…4JGR"})
    E.apunta({"tipo": "orden", "cartera": "B0", "cuenta_huella": "h9", "cuenta": "…X9F9"})
    E.apunta({"tipo": "reasignacion", "cuenta_huella": "h9", "cuenta": "…X9F9", "de": "B0", "a": "D1"})
    assert R.main([]) == 0 and "en seco" in capsys.readouterr().out
    assert len(E.leer_registro()) == 3
    assert R.main(["--escribir"]) == 0
    reas = [(r["cuenta"], r["de"], r["a"]) for r in E.leer_registro() if r.get("tipo") == "reasignacion"]
    assert reas == [("…X9F9", "B0", "D1"), ("…4JGR", "B1", "C1"), ("…X9F9", "D1", "A1")]
    assert R.main(["--escribir"]) == 0 and len(E.leer_registro()) == 5                # idempotente
    with pytest.raises(LookupError):
        R.plan([])


def test_configurar_cuentas_en_seco_sin_red_y_comprueba_la_cuenta(capsys):
    from scripts import configurar_cuentas as CC
    assert CC.main([]) == 0 and "nada enviado" in capsys.readouterr().out          # la red real lanzaría AssertionError
    assert CC.OBJETIVO["A1"]["config"]["max_options_trading_level"] == 0
    assert CC.OBJETIVO["C1"]["config"]["no_shorting"] is True and "M1" not in CC.OBJETIVO
    llamadas = []

    def t(metodo, url, cab, params, cuerpo, plazo):
        llamadas.append((metodo, url, cuerpo))
        if url.endswith("/v2/account"):
            return 200, {"account_number": "PA3ABCX9F9"}
        return 200, {"no_shorting": False, "max_margin_multiplier": "2", "max_options_trading_level": 2, **(cuerpo or {})}
    c = A.Cliente(A.Credenciales(key_id="k", secret="s", perfil="A1"), transporte=t)
    r = CC.configurar(c, "A1", aplicar=False)
    assert set(r["cambios"]) == {"no_shorting", "max_margin_multiplier", "max_options_trading_level"}
    assert not [x for x in llamadas if x[0] == "PATCH"]
    r = CC.configurar(c, "A1", aplicar=True)
    patch = [x for x in llamadas if x[0] == "PATCH"]
    assert len(patch) == 1 and patch[0][1].startswith("https://paper-api.alpaca.markets/")
    assert r["despues"]["max_options_trading_level"] == 0
    assert "no se toca" in CC.configurar(c, "C1", aplicar=True)["error"]           # …X9F9 no es la de C1


def test_d1_solo_papel_usa_cualquier_perfil_para_datos(monkeypatch):
    from scripts import paper_decision_d1 as D
    hechos = {"C1": "cliente-c1"}
    monkeypatch.setattr(A, "cliente", lambda p=None, **k: hechos.get(p))
    assert D.cliente_datos() == "cliente-c1"
    hechos.clear()
    assert D.cliente_datos() is None


# ------------------------------------------------------------------ automatización (no instalada)
def test_plist_a1_lun_vie_2100_y_no_instalado():
    import plistlib
    p = plistlib.loads((REPO / "scripts" / "launchd" / "com.financialkb.a1.plist").read_bytes())
    assert p["Label"] == "com.financialkb.a1" and p["ProgramArguments"][-1].endswith("scripts/a1_gestor.sh")
    assert sorted(d["Weekday"] for d in p["StartCalendarInterval"]) == [1, 2, 3, 4, 5]
    assert all((d["Hour"], d["Minute"]) == (21, 0) for d in p["StartCalendarInterval"]) and not p["RunAtLoad"]
    assert not (Path.home() / "Library" / "LaunchAgents" / "com.financialkb.a1.plist").exists()


def test_script_a1_sin_activo_no_hace_nada(tmp_path):
    import subprocess
    repo = tmp_path / "repo2"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "a1_gestor.sh").write_text((REPO / "scripts" / "a1_gestor.sh").read_text())
    r = subprocess.run(["/bin/bash", str(repo / "scripts" / "a1_gestor.sh")], capture_output=True, text=True,
                       env={**os.environ, "FIN_REPO": str(repo), "FIN_LOGDIR": str(tmp_path / "logs"),
                            "FIN_SIN_AVISOS": "1"})
    assert r.returncode == 0 and "A1 no activado" in next((tmp_path / "logs").glob("*_a1.log")).read_text()
    t = (REPO / "scripts" / "a1_gestor.sh").read_text()
    assert "src.paper.a1 --auto" in t and "decisiones_a1_sombra.jsonl" in t and "m1" not in t.replace("(c1|m1)", "")
