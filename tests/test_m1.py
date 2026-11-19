"""M1 «Claude gestor macro» (spec M1 v1.1): sombra teórica (regla del borrador 0.1 y valoración), guardia con citas,
paquete, ciclo con un `claude` FALSO, registro (exige M1_ACTIVO) y piezas de automatización. Sin red, sin claves y sin
tocar los registros reales."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.broker import alpaca as A
from src.broker import c1_guardia as G
from src.broker import m1_guardia as MG
from src.paper import agente as AG
from src.paper import c1_paquete as CP
from src.paper import m1 as M
from src.paper import m1_paquete as P
from src.paper import m1_sombra as S
from tests.agente_falso import archivo_y_repo, claude_falso

REPO = M.REPO
REALES = [REPO / "research" / "paper" / x for x in ("decisiones_m1.jsonl", "decisiones_m1_sombra.jsonl", "M1_PARADA")]
SIGNAL = {"asof": "2026-11-17", "regime": {"quadrant": "Goldilocks", "G_state": "up", "I_state": "down"},
          "credit": {"light": "verde", "reds": 0}, "liquidity": {"state": "escasa"},
          "debt_cycle": {"phase": "expansión temprana"}, "long_cycle": {"stage": "tardío"},
          "escenarios": {"emision": "2026-11-17", "paises": {"USA": {"abanicos": {"bolsa": {"p_neg": 0.364}}}}}}
TODOS = list(MG.MODELOS)


@pytest.fixture(autouse=True)
def aislado(tmp_path, monkeypatch):
    for k in list(os.environ):
        if k.startswith(("ALPACA_", "APCA_")):
            monkeypatch.delenv(k)
    monkeypatch.setenv("FIN_ALPACA_ENV", str(tmp_path / "alpaca.env"))
    monkeypatch.setenv("FIN_ALPACA_DIR", str(tmp_path / "alpaca"))
    monkeypatch.setenv("FIN_M1_DIR", str(tmp_path / "m1"))
    a, r = archivo_y_repo(tmp_path)
    monkeypatch.setenv("FIN_DATA_ROOT", str(a))
    monkeypatch.setenv("FIN_AGENTE_REPO", str(r))
    monkeypatch.setattr(A, "_transporte_requests", lambda *a, **k: (_ for _ in ()).throw(AssertionError("red real")))
    monkeypatch.setattr(CP, "cierres_warehouse", lambda X=None: {"fuente": "test", "activos": {}})
    monkeypatch.setattr(CP, "alertas", lambda hoy: [{"ticker": "UNH", "frase": "volumen anormal"}])
    monkeypatch.setattr(CP, "resumen_panel", lambda s: ["EE. UU. en Goldilocks"])
    monkeypatch.setattr(CP, "diagnosticos", lambda hoy, carpeta=None: [])
    monkeypatch.setattr(CP, "ultimo_signal", lambda: (SIGNAL, "x_signal.json"))
    monkeypatch.setattr(S, "E1_VIVO", tmp_path / "e1_vivo.jsonl")
    monkeypatch.setattr(P, "K1_VIVO", tmp_path / "k1_vivo.jsonl")
    monkeypatch.setattr(S, "ARCHIVO_PRECIOS", tmp_path / "no_existe.parquet")
    monkeypatch.setattr(S, "LOG", tmp_path / "sombra.jsonl")
    monkeypatch.setattr(MG, "PARADA", tmp_path / "M1_PARADA")
    monkeypatch.setattr(AG, "ruta_diario", lambda cartera, fecha, repo=None: tmp_path / "obsidian" / cartera / f"{fecha}.md")
    monkeypatch.setattr(S, "cierres_yahoo", lambda simbolos, desde: precios_falsos(simbolos))
    antes = [x.read_bytes() if x.exists() else None for x in REALES]
    yield
    assert [x.read_bytes() if x.exists() else None for x in REALES] == antes, "un test tocó un registro real de M1"


def precios_falsos(simbolos, dias=8, fin="2026-11-18") -> pd.DataFrame:
    idx = pd.bdate_range(end=fin, periods=dias)
    return pd.DataFrame({s: 100.0 * (1.001 ** np.arange(dias)) for s in simbolos}, index=idx)


def entradas(**kw) -> dict:
    x = {"cuadrante": "Goldilocks", "G": "up", "I": "down", "credito": "verde", "liquidez": "neutral",
         "int11_p_perdida_bolsa": 0.40, "e1_p_recesion": None}
    x.update(kw)
    return x


# ------------------------------------------------------------------ sombra: regla del borrador 0.1
def test_bolsa_base_ajustes_y_limites():
    assert S.bolsa(entradas(G=None))[0] == 0.60
    assert S.bolsa(entradas())[0] == 0.70                                              # G↑ +10
    b, aj = S.bolsa(entradas(credito="rojo", e1_p_recesion=0.55, liquidez="escasa", int11_p_perdida_bolsa=0.7,
                             G="down"))
    assert b == 0.20 and any("acotado" in x for x in aj)                              # suelo 20 %
    assert S.bolsa(entradas(liquidez="abundante", int11_p_perdida_bolsa=0.30))[0] == 0.75   # techo 75 %
    assert S.bolsa(entradas(G=None, e1_p_recesion=0.35))[0] == 0.45                   # > 30 % → −15
    assert S.bolsa(entradas(G=None, e1_p_recesion=0.60))[0] == 0.30                   # > 50 % → −30 (no se suman)
    assert S.bolsa(entradas(G=None, credito="ámbar"))[0] == 0.50
    assert not any("acotado" in x for x in S.bolsa(entradas(liquidez="escasa"))[1])   # 0,65 exacto, sin redondeos


def test_objetivo_goldilocks_pesos_y_suma():
    o = S.objetivo(entradas())
    w = o["pesos"]
    assert abs(sum(w.values()) - 1) < 1e-6 and abs(w["efectivo"] - S.COLCHON) < 1e-5
    b = 0.70 * (1 - S.COLCHON)
    assert abs(w["VTI"] - b * 0.5) < 1e-6
    assert all(abs(w[t] - b * 0.3 / 4) < 1e-6 for t in ("XLK", "XLY", "XRT", "XLF"))
    assert len(o["acciones"]) == 8 and all(abs(w[t] - b * 0.2 / 8) < 1e-6 for t in o["acciones"])
    resto = 0.30 * (1 - S.COLCHON)
    assert abs(w["TLT"] - resto * 0.4) < 1e-6 and abs(w["SHY"] - resto * 0.1) < 1e-6 and "UUP" not in w


def test_objetivo_inflacion_alta_y_uup_sale_de_shy_e_ief():
    o = S.objetivo(entradas(cuadrante="Estanflación", G="down", I="up", credito="rojo"))
    w = o["pesos"]
    assert {"GLD", "DBC", "TIP"} <= set(w) and "TLT" not in w and o["uup"]
    assert abs(w["UUP"] - 0.10 * (1 - S.COLCHON)) < 1e-6 and abs(sum(w.values()) - 1) < 1e-6
    assert set(o["sectores"]) == {"Enrgy", "Utils", "NoDur", "Hlth"}
    o2 = S.objetivo(entradas(I="down", e1_p_recesion=0.6, G=None))                  # I↓: SHY 10 % no basta → IEF
    assert abs(o2["pesos"]["UUP"] - 0.10 * (1 - S.COLCHON)) < 1e-6 and "SHY" not in o2["pesos"]


def test_sin_cuadrante_no_hay_objetivo_y_e1_ausente_es_neutral():
    assert S.objetivo(entradas(cuadrante=None))["pesos"] is None
    x = S.entradas(SIGNAL, S.e1_usa(Path("/no/existe.jsonl")))
    assert x["e1_p_recesion"] is None and x["int11_p_perdida_bolsa"] == 0.364 and x["G"] == "up"


def test_e1_usa_ultimo_origen(tmp_path):
    p = tmp_path / "e1.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in [{"origen": "2026-11-30", "pais": "USA", "p_A": 0.2, "p_L": 0.1},
                                                     {"origen": "2026-12-31", "pais": "USA", "p_A": 0.4, "p_L": 0.1},
                                                     {"origen": "2026-12-31", "pais": "DEU", "p_A": 0.9}]))
    e = S.e1_usa(p)
    assert e["disponible"] and e["p"] == 0.4 and e["origen"] == "2026-12-31"


# ------------------------------------------------------------------ sombra: valoración teórica
def test_valorar_reequilibra_por_cambio_o_deriva_y_cobra_5pb():
    idx = pd.bdate_range("2026-12-01", periods=6)
    px = pd.DataFrame({"A": [100, 110, 125, 125, 125, 125], "B": [100, 100, 100, 100, 100, 100]}, index=idx, dtype=float)
    w = {"A": 0.5, "B": 0.5, "efectivo": 0.0}
    lineas = [{"fecha": str(d.date()), "objetivo": {"pesos": w}} for d in idx]
    v = S.valorar(lineas, px)
    assert v["rebalanceos"] == 2                     # compra inicial + reequilibrio cuando A deriva ≥ 5 pp (día 3)
    assert abs(v["costes"] - 0.0005 * (1.0 + 2 * (0.625 / 1.125 - 0.5))) < 1e-6
    # sin ninguna deriva ni cambio: solo la compra inicial
    px2 = pd.DataFrame({"A": [100.0] * 4, "B": [100.0] * 4}, index=idx[:4])
    v2 = S.valorar(lineas[:4], px2)
    assert v2["rebalanceos"] == 1 and abs(v2["valor"] - 100_000 * (1 - 0.0005)) < 0.01
    # cambio de objetivo: reequilibra aunque no haya deriva
    l3 = lineas[:2] + [{"fecha": str(idx[2].date()), "objetivo": {"pesos": {"A": 0.2, "B": 0.8, "efectivo": 0.0}}}]
    v3 = S.valorar(l3, px2.iloc[:3])
    assert v3["rebalanceos"] == 2 and abs(v3["costes"] - 0.0005 * (1 + 0.6)) < 1e-6


def test_valorar_sin_cierre_de_un_activo_lo_deja_quieto_y_lo_anota():
    idx = pd.bdate_range("2026-12-01", periods=3)
    px = pd.DataFrame({"A": [100.0, np.nan, 100.0], "B": [100.0, 110.0, 110.0]}, index=idx)
    v = S.valorar([{"fecha": "2026-12-01", "objetivo": {"pesos": {"A": 0.5, "B": 0.5, "efectivo": 0.0}}}], px)
    assert "A" in v["sin_cierre"] and v["valor"] > 100_000


def test_linea_del_dia_y_registro_una_por_dia(tmp_path):
    px = precios_falsos(S.universo())
    ln = S.linea_del_dia("2026-11-19", SIGNAL, {"disponible": False}, [], px, "test")
    assert ln["version"] == S.VERSION and ln["objetivo"]["bolsa"] == 0.65
    assert ln["valoracion"]["hasta"] is None                                          # se ejecuta al cierre de hoy
    r = tmp_path / "s.jsonl"
    S.registrar(ln, r)
    with pytest.raises(ValueError):
        S.registrar(ln, r)
    ln2 = S.linea_del_dia("2026-11-20", SIGNAL, {"disponible": False}, [ln], precios_falsos(S.universo(), fin="2026-11-19"),
                          "test")
    assert ln2["valoracion"]["hasta"] == "2026-11-19" and ln2["valoracion"]["rebalanceos"] == 1


def test_acciones_lista_fija_versionada_y_universo():
    a = json.loads(S.ACCIONES.read_text())
    assert a["version"].startswith("m1-acciones-1") and all(len(v) == 2 for v in a["acciones"].values())
    todas = [t for v in a["acciones"].values() for t in v]
    assert len(todas) == len(set(todas)) == 22
    u = S.universo()
    assert {"VTI", "UUP", "DBC", "XRT", "BRK.B"} <= set(u)


# ------------------------------------------------------------------ guardia con citas
def declaracion(caso="si", sin=()):
    return [{"modelo": m, "caso": caso if m in ("cuadrante", "credito") else "no_disponible" if m == "e1" else "no",
             "por_que": "x"} for m in TODOS if m not in sin]


def salida(ordenes=None, **kw) -> str:
    d = {"version_mandato": "m1-v1", "fecha": "2026-11-19", "resumen": "r", "ordenes": ordenes or [],
         "citas_no_operar": [{"modelo": "credito", "dice": "verde"}], "declaracion_modelos": declaracion(),
         "desviacion_sombra": "sigo la sombra", "nota_diario": "n", "diario_md": "## d"}
    d.update(kw)
    return json.dumps(d, ensure_ascii=False)


def orden(simbolo="SPY", citas=None, **kw):
    o = {"simbolo": simbolo, "clase": "accion", "lado": "compra", "tipo": "mercado", "importe_usd": 1000,
         "razon": "r", "cambiaria_de_opinion": "c"}
    if citas is not None:
        o["citas"] = citas
    o.update(kw)
    return o


def estado():
    return G.EstadoCuenta(efectivo=10_000, activos={s: {"simbolo": s, "clase": "accion", "negociable": True,
                                                        "fraccionable": True} for s in ("SPY", "TLT", "GLD", "VTI")},
                          precios={"SPY": 600, "TLT": 80, "GLD": 250, "VTI": 300})


DISP = {"cuadrante", "credito", "liquidez", "ciclo_deuda", "int11", "alertas"}


def test_guardia_rechaza_ordenes_sin_cita_valida_y_deja_pasar_las_demas():
    ords = [orden("SPY", [{"modelo": "cuadrante", "dice": "Goldilocks, G↑ (signal 2026-11-17)"}]),
            orden("TLT"),                                                                  # sin citas
            orden("GLD", [{"modelo": "e1", "dice": "P(recesión) 40 %"}]),                  # E1 sin salida hoy
            orden("VTI", [{"modelo": "astrologia", "dice": "x"}]),                         # modelo inexistente
            orden("SPY", [{"modelo": "credito", "dice": ""}]),                             # no dice nada
            orden("SPY", [{"modelo": "credito", "dice": "verde"}, {"modelo": "e1", "dice": "x"}])]   # una mala
    v = MG.validar(salida(ords), estado(), DISP, parada=False)
    assert v.opera and [n["indice"] for n in v.validas] == [0]
    mot = {r["indice"]: r["motivo"] for r in v.rechazadas}
    assert "sin cita" in mot[1] and "no tiene salida" in mot[2] and "no está en la lista" in mot[3]
    assert "sin decir" in mot[4] and "no tiene salida" in mot[5]


def test_guardia_m1_sigue_aplicando_las_reglas_de_c1():
    ok = [{"modelo": "credito", "dice": "verde"}]
    ords = [orden("SPY", ok, importe_usd=9000), orden("GLD", ok, importe_usd=5000),          # supera el efectivo
            orden("TLT", ok, lado="venta", importe_usd=None, cantidad=3)]                    # corto
    v = MG.validar(salida(ords), estado(), DISP, parada=False)
    assert [n["simbolo"] for n in v.validas] == ["SPY"]
    assert {r["indice"] for r in v.rechazadas} == {1, 2}


@pytest.mark.parametrize("cambio, texto", [
    ({"citas_no_operar": []}, "citas_no_operar"),
    ({"citas_no_operar": [{"modelo": "e1", "dice": "x"}]}, "citas_no_operar"),
    ({"declaracion_modelos": declaracion(sin=("xbrl",))}, "faltan ['xbrl']"),
    ({"declaracion_modelos": declaracion() + [{"modelo": "credito", "caso": "si", "por_que": "x"}]}, "repetidos"),
    ({"declaracion_modelos": [dict(x, caso="si") if x["modelo"] == "e1" else x for x in declaracion()]},
     "no tiene salida"),
    ({"declaracion_modelos": [dict(x, caso="quizá") if x["modelo"] == "alertas" else x for x in declaracion()]},
     "caso"),
    ({"desviacion_sombra": ""}, "desviacion_sombra"),
    ({"diario_md": " "}, "diario_md"),
    ({"version_mandato": "c1-v2"}, "m1-v1"),
])
def test_salida_que_incumple_el_mandato_no_opera(cambio, texto):
    v = MG.validar(salida(**cambio), estado(), DISP, parada=False)
    assert not v.opera and texto in v.motivo


def test_no_operar_con_cita_valida_es_valido_y_parada_m1():
    v = MG.validar(salida(), estado(), DISP, parada=False)
    assert v.opera and not v.validas and not v.rechazadas
    assert not MG.validar(salida(), estado(), DISP, parada=True).opera
    assert MG.PARADA.name == "M1_PARADA"


def test_mandato_m1_coincide_con_la_guardia():
    t = M.MANDATO.read_text()
    assert "version: m1-v1" in t and f'"version_mandato": "{MG.VERSION_MANDATO}"' in t and "−35 %" in t
    for m in MG.MODELOS:
        assert f"`{m}`" in t
    assert "citas_no_operar" in t and "declaracion_modelos" in t and "desviacion_sombra" in t


# ------------------------------------------------------------------ paquete
def test_paquete_m1_modelos_disponibles_y_sombra(tmp_path):
    p = P.recoger(None, dt.date(2026, 11, 19), registro=[], sombra_previas=[])
    assert p["mandato"] == "m1-v1" and p["version"] == "m1-paquete-1" and p["cuenta"]["simulada"]
    assert set(p["modelos_disponibles"]) == {"cuadrante", "credito", "liquidez", "ciclo_deuda", "int11", "alertas"}
    assert "error" in p["modelos"]["e1"] and "error" in p["modelos"]["xbrl"] and "error" in p["modelos"]["diagnosticos"]
    assert p["modelos"]["cuadrante"]["fecha_publicacion"] == "2026-11-17"
    assert p["sombra"]["objetivo"]["bolsa"] == 0.65 and p["sha256"] == CP.hash_paquete(p)
    assert "VTI" in p["cierres_simulacion"]["activos"]
    assert all(v["fecha"] <= "2026-11-18" for v in p["cierres_simulacion"]["activos"].values())   # solo sesiones completas


def test_xbrl_resumen_ultimos_trimestres(tmp_path):
    f = tmp_path / "hechos.json"
    hs = [{"start": f"2026-0{q}-01", "end": f"2026-0{q + 2}-30", "val": q, "form": "10-Q", "filed": "2026-11-01",
           "frame": f"CY2026Q{q}"} for q in (1, 2, 3)] + [{"end": "2026-09-30", "val": 9, "frame": "CY2026"}]
    f.write_text(json.dumps({"actualizado_utc": "2026-11-18", "empresas": {"GOOGL": {"nombre": "Alphabet", "conceptos": {
        "us-gaap:Revenues": {"hechos": hs}}}}}))
    x = P.xbrl(f)
    assert [h["valor"] for h in x["empresas"]["GOOGL"]["ingresos"]] == [1, 2, 3]


# ------------------------------------------------------------------ ciclo con claude falso
def test_ciclo_m1_ensayo_registra_uso_de_modelos_y_rechaza_sin_cita(tmp_path, monkeypatch):
    ok = [{"modelo": "cuadrante", "dice": "Goldilocks"}]
    ords = [orden("VTI", ok, importe_usd=30_000), orden("XLK", None, importe_usd=5_000)]
    f = claude_falso(tmp_path, salida(ords))
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(f))
    linea = M.ciclo(None, hoy=dt.date(2026, 11, 19), registro=[])
    assert linea["perfil"] == "M1" and linea["modo"] == "agente" and linea["mandato"]["version"] == "m1-v1"
    assert [n["simbolo"] for n in linea["guardia"]["validas"]] == ["VTI"]
    assert "sin cita" in linea["rechazadas"][0]["motivo"]
    u = linea["uso_modelos"]
    assert u["declaracion"]["cuadrante"] == "si" and u["citas_ordenes"][0]["modelos"] == ["cuadrante"]
    assert Path(linea["diario"]).name == "diario.md"                                   # ensayo: fuera de Obsidian
    s = M.sombra_de(linea)
    assert s["objetivo"]["bolsa"] == 0.65
    stdin = (f.parent / "stdin.txt").read_text()
    assert "M1" in stdin and "modelos_disponibles" in stdin


def test_ciclo_m1_con_parada_no_llama_a_claude(tmp_path, monkeypatch):
    f = claude_falso(tmp_path, salida())
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(f))
    (tmp_path / "M1_PARADA").write_text("supervisor")
    linea = M.ciclo(None, hoy=dt.date(2026, 11, 19), registro=[])
    assert not linea["opera"] and "M1_PARADA" in linea["motivo_no_opera"] and not (f.parent / "args.txt").exists()


def test_main_m1_exige_activo_arbol_limpio_y_claves(tmp_path, monkeypatch):
    f = claude_falso(tmp_path, salida())
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(f))
    monkeypatch.setattr(M, "ACTIVO", tmp_path / "M1_ACTIVO")
    assert M.main(["--auto"]) == 0 and not (f.parent / "args.txt").exists()
    assert M.main(["--registrar"]) == 6
    (tmp_path / "M1_ACTIVO").write_text("")
    monkeypatch.setattr(M, "git", lambda *a: " M algo" if a[0] == "status" else "")
    assert M.main(["--registrar"]) == 5
    monkeypatch.setattr(M, "git", lambda *a: "")
    assert M.main(["--registrar"]) == 7
    assert not (f.parent / "args.txt").exists()


def test_main_m1_registra_decision_y_sombra_y_commitea_las_dos(tmp_path, monkeypatch):
    from tests.test_c1 import Falso
    ok = [{"modelo": "credito", "dice": "verde"}]
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(claude_falso(tmp_path, salida([orden("SPY", ok, importe_usd=500)]))))
    monkeypatch.setattr(M, "ACTIVO", tmp_path / "M1_ACTIVO")
    (tmp_path / "M1_ACTIVO").write_text("")
    reg = tmp_path / "decisiones_m1.jsonl"
    monkeypatch.setattr(M, "LOG", reg)
    monkeypatch.setattr(P, "LOG", reg)
    llamadas = []
    monkeypatch.setattr(M, "git", lambda *a: llamadas.append(a) or ("abc123" if a[0] == "rev-parse" else ""))
    from src.paper import c1 as C
    monkeypatch.setattr(C, "ESPERA_EJECUCION_S", 0)
    t = Falso()
    cl = A.Cliente(A.Credenciales(key_id="PKM1TEST", secret="SECRETM1TEST", perfil="M1"), transporte=t)
    monkeypatch.setattr(A, "cliente", lambda perfil=None, **kw: cl if perfil == "M1" else None)
    monkeypatch.setattr(S, "cierres_alpaca", lambda c, simbolos, desde, hasta: precios_falsos(simbolos))
    assert M.main(["--registrar"]) == 0
    linea = json.loads(reg.read_text())
    assert linea["perfil"] == "M1" and len(linea["enviadas"]) == 1
    assert linea["enviadas"][0]["client_order_id"].startswith("m1-")
    sombra = S.leer_registro()
    assert len(sombra) == 1 and sombra[0]["fecha"] == linea["fecha"] and sombra[0]["git_head"] == "abc123"
    add = next(a for a in llamadas if a[0] == "add")
    assert str(reg) in add and str(S.LOG) in add
    assert llamadas[-1] == ("push", "-q", "origin", "main") and "Co-Authored-By" in next(a for a in llamadas if a[0] == "commit")[-1]
    assert (tmp_path / "obsidian" / "M1" / f"{linea['fecha']}.md").exists()
    assert "SECRETM1TEST" not in reg.read_text() and "PKM1TEST" not in reg.read_text()


# ------------------------------------------------------------------ automatización (no instalada)
def test_plist_m1_lun_vie_2045_y_no_instalado():
    import plistlib
    p = plistlib.loads((REPO / "scripts" / "launchd" / "com.financialkb.m1.plist").read_bytes())
    assert p["Label"] == "com.financialkb.m1" and p["ProgramArguments"][-1].endswith("scripts/m1_gestor.sh")
    assert sorted(d["Weekday"] for d in p["StartCalendarInterval"]) == [1, 2, 3, 4, 5]
    assert all((d["Hour"], d["Minute"]) == (20, 45) for d in p["StartCalendarInterval"]) and not p["RunAtLoad"]
    assert not (Path.home() / "Library" / "LaunchAgents" / "com.financialkb.m1.plist").exists()


def test_script_m1_sin_activo_no_hace_nada(tmp_path):
    import subprocess
    repo = tmp_path / "repo2"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "m1_gestor.sh").write_text((REPO / "scripts" / "m1_gestor.sh").read_text())
    r = subprocess.run(["/bin/bash", str(repo / "scripts" / "m1_gestor.sh")], capture_output=True, text=True,
                       env={**os.environ, "FIN_REPO": str(repo), "FIN_LOGDIR": str(tmp_path / "logs"),
                            "FIN_SIN_AVISOS": "1"})
    assert r.returncode == 0 and "no activado" in next((tmp_path / "logs").glob("*_m1.log")).read_text()
