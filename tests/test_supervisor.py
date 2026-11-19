"""Supervisor de carteras (spec supervisor v1.0): límites duros en código, paradas (C1/M1) y avisos, paquete, agente
con un `claude` FALSO, informe. Sin red, sin claves, sin tocar los registros ni las paradas reales."""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import pytest

from src.broker import alpaca as A
from src.broker import c1_guardia as G
from src.broker import m1_guardia as MG
from src.paper import agente as AG
from src.paper import c1 as C
from src.paper import supervisor as SUP
from tests.agente_falso import archivo_y_repo, args, claude_falso

REPO = SUP.REPO
HOY = dt.date(2026, 11, 20)
REALES = [REPO / "research" / "paper" / x for x in ("C1_PARADA", "M1_PARADA", "D1_PARADA")]


@pytest.fixture(autouse=True)
def aislado(tmp_path, monkeypatch):
    for k in list(os.environ):
        if k.startswith(("ALPACA_", "APCA_")):
            monkeypatch.delenv(k)
    monkeypatch.setenv("FIN_ALPACA_ENV", str(tmp_path / "alpaca.env"))
    monkeypatch.setenv("FIN_ALPACA_DIR", str(tmp_path / "alpaca"))
    monkeypatch.setenv("FIN_SUPERVISOR_DIR", str(tmp_path / "sup"))
    monkeypatch.setenv("FIN_SIN_AVISOS", "1")
    a, r = archivo_y_repo(tmp_path)
    monkeypatch.setenv("FIN_DATA_ROOT", str(a))
    monkeypatch.setenv("FIN_AGENTE_REPO", str(r))
    monkeypatch.setattr(A, "_transporte_requests", lambda *a, **k: (_ for _ in ()).throw(AssertionError("red real")))
    paper = tmp_path / "paper"
    paper.mkdir()
    monkeypatch.setattr(SUP, "PAPER", paper)
    monkeypatch.setattr(SUP, "REGISTROS", {k: paper / v.name for k, v in SUP.REGISTROS.items()})
    monkeypatch.setattr(SUP, "ACTIVOS", {k: paper / v.name for k, v in SUP.ACTIVOS.items()})
    monkeypatch.setattr(G, "PARADA", paper / "C1_PARADA")
    monkeypatch.setattr(MG, "PARADA", paper / "M1_PARADA")
    nota = tmp_path / "Actualizaciones.md"
    nota.write_text("# Actualizaciones\n<!-- entradas -->\n")
    monkeypatch.setattr(SUP, "NOTA", nota)
    monkeypatch.setattr(AG, "ruta_diario", lambda cartera, fecha, repo=None: tmp_path / "obsidian" / cartera / f"{fecha}.md")
    antes = [x.exists() for x in REALES]
    yield
    assert [x.exists() for x in REALES] == antes, "un test creó o borró una parada real"


def salida_sup(**kw) -> str:
    d = {"version_mandato": "supervisor-v1", "fecha": HOY.isoformat(),
         "carteras": {k: {"estado": "ok", "hallazgos": []} for k in SUP.CARTERAS},
         "paradas": [], "para_el_usuario": ["nada"], "informe_md": "## Informe\nTodo en orden."}
    d.update(kw)
    return json.dumps(d, ensure_ascii=False)


def cuenta(**kw):
    c = {"efectivo": 1000.0, "valor": 100_000.0, "maximo_valor": 100_000.0, "caida_desde_maximo": 0.0,
         "posiciones": [{"simbolo": "SPY", "clase": "us_equity", "cantidad": 10, "lado": "long", "valor": 6000}],
         "ordenes_abiertas": []}
    c.update(kw)
    return c


# ------------------------------------------------------------------ límites duros (código)
def test_limites_caida_corto_opcion_vendida_apalancamiento_y_errores():
    cuentas = {"B0": cuenta(caida_desde_maximo=-0.36),
               "D1": cuenta(posiciones=[{"simbolo": "DBC", "clase": "us_equity", "cantidad": -5, "lado": "short"}]),
               "C1": cuenta(posiciones=[{"simbolo": "SPY261218P00550000", "clase": "us_option", "cantidad": -1,
                                         "lado": "short"}]),
               "M1": cuenta(efectivo=-50.0), "B1": cuenta(caida_desde_maximo=-0.35), "B1P": {"sin_cuenta": "x"}}
    err = {"claude": {"ok": False}}
    regs = {k: [] for k in SUP.CARTERAS}
    regs["M1"] = [{"claude": {"ok": True}}] + [err] * 4
    regs["C1"] = [err] * 3                                              # 3 no es > 3
    lim = SUP.limites_duros(cuentas, regs)
    por = {(x["cartera"], x["limite"]) for x in lim}
    assert ("B0", "caida_maxima") in por and ("B1", "caida_maxima") in por        # ≤ −35 % incluye −35 %
    assert ("D1", "fuera_de_mandato") in por and ("C1", "fuera_de_mandato") in por
    assert any("opción vendida" in x["detalle"] for x in lim if x["cartera"] == "C1")
    assert ("M1", "fuera_de_mandato") in por and ("M1", "errores_seguidos") in por
    assert ("C1", "errores_seguidos") not in por
    assert all(x["parada"] == (x["cartera"] in ("C1", "M1")) for x in lim)


def test_ensayo_no_crea_paradas_ni_avisa():
    lim = SUP.limites_duros({"M1": cuenta(caida_desde_maximo=-0.4)}, {k: [] for k in SUP.CARTERAS})
    acc = SUP.aplicar_paradas(lim, ensayo=True, fecha=HOY.isoformat())
    assert acc[0]["accion"].startswith("ENSAYO") and not MG.PARADA.exists()
    assert "Supervisor" not in SUP.NOTA.read_text()


def test_registro_crea_parada_de_c1_y_m1_y_solo_avisa_en_d1():
    lim = SUP.limites_duros({"M1": cuenta(caida_desde_maximo=-0.4), "C1": cuenta(efectivo=-1.0),
                             "D1": cuenta(caida_desde_maximo=-0.5)}, {k: [] for k in SUP.CARTERAS})
    acc = {a["cartera"]: a for a in SUP.aplicar_paradas(lim, ensayo=False, fecha=HOY.isoformat())}
    assert MG.PARADA.exists() and G.PARADA.exists() and not (SUP.PAPER / "D1_PARADA").exists()
    assert acc["M1"]["accion"] == "parada creada" and "solo aviso" in acc["D1"]["accion"]
    assert "caída" in MG.PARADA.read_text() and "borrar este fichero" in MG.PARADA.read_text()
    n = SUP.NOTA.read_text()
    assert "🛑 PARADA: M1" in n and "🛑 PARADA: C1" in n and "⚠️ D1" in n
    acc2 = SUP.aplicar_paradas(lim, ensayo=False, fecha=HOY.isoformat())
    assert {a["accion"] for a in acc2 if a["cartera"] in ("C1", "M1")} == {"la parada ya existía"}


def test_la_parada_del_supervisor_es_la_que_miran_los_ciclos(tmp_path, monkeypatch):
    assert SUP.parada("C1") == G.PARADA and SUP.parada("M1") == MG.PARADA
    G.PARADA.write_text("x")
    f = claude_falso(tmp_path, "{}")
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(f))
    linea = C.ciclo(None, hoy=HOY, registro=[])
    assert not linea["opera"] and "C1_PARADA" in linea["motivo_no_opera"] and not (f.parent / "args.txt").exists()
    from src.paper import m1 as M
    MG.PARADA.write_text("x")
    linea = M.ciclo(None, hoy=HOY, registro=[])
    assert not linea["opera"] and "M1_PARADA" in linea["motivo_no_opera"]


# ------------------------------------------------------------------ paquete y salud
def test_paquete_con_cuentas_simuladas_registros_y_salud(tmp_path):
    (SUP.PAPER / "ACTIVO").write_text("")
    SUP.REGISTROS["C1"].write_text("\n".join(json.dumps({"fecha": f"2026-11-1{i}", "claude": {"ok": False}})
                                             for i in range(5)) + "\n")
    p = SUP.recoger(HOY, cuentas=SUP.cuentas_simuladas(HOY), ensayo=True)
    assert p["cuentas_simuladas"] and p["sha256"] == SUP.hash_paquete(p)
    assert p["salud"]["B0"]["activo"] and not p["salud"]["M1"]["registro_existe"]
    assert p["salud"]["C1"]["errores_seguidos"] == 5
    sup = {(x["cartera"], x["limite"]) for x in p["limites_duros"]["superados"]}
    assert ("M1", "caida_maxima") in sup and ("D1", "fuera_de_mandato") in sup and ("C1", "errores_seguidos") in sup
    assert all(a["accion"].startswith("ENSAYO") for a in p["limites_duros"]["acciones"])
    assert not MG.PARADA.exists() and not G.PARADA.exists()
    assert "KEY" not in json.dumps(p).upper().replace("KEYS", "")


def test_cuentas_alpaca_usa_el_cliente_y_enmascara(monkeypatch):
    from tests.test_c1 import Falso
    from src.report import panel_competicion as PC
    t = Falso()
    cl = A.Cliente(A.Credenciales(key_id="PKSUPTEST", secret="SECRETSUPTEST", perfil="M1"), transporte=t)
    monkeypatch.setattr(PC, "clientes_por_cartera", lambda: {"M1": cl})
    cs = SUP.cuentas_alpaca()
    assert cs["M1"]["valor"] == float(t.cuenta["equity"]) and "sin_cuenta" in cs["B0"]
    assert "SECRETSUPTEST" not in json.dumps(cs) and {m for m, *_ in t.llamadas} == {"GET"}


# ------------------------------------------------------------------ agente y salida
def test_ciclo_ensayo_con_claude_falso_escribe_el_informe_en_la_carpeta_de_trabajo(tmp_path, monkeypatch):
    f = claude_falso(tmp_path, salida_sup(paradas=[{"cartera": "M1", "explicacion": "caída −37 %"}]))
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(f))
    out = SUP.ciclo(HOY, cuentas=SUP.cuentas_simuladas(HOY))
    assert out["ensayo"] and out["claude"]["ok"] and out["informe"]["carteras"]["B0"]["estado"] == "ok"
    inf = Path(out["informe_fichero"])
    assert inf.name == "informe.md" and "Todo en orden" in inf.read_text() and "ENSAYO: se crearía" in inf.read_text()
    a = args(f)
    assert a[a.index("--tools") + 1] == "Read,Grep,Glob"
    i = a.index("--add-dir")
    dirs = a[i + 1:a.index("--system-prompt")]
    assert any(d.endswith("research/paper") for d in dirs)                         # el supervisor lee los registros
    assert not any(d.endswith("/config") and "archivo" in d for d in dirs)
    assert "supervisor-v1" in "\n".join(a[a.index("--system-prompt") + 1:]) and "SIMULADAS" in (f.parent / "stdin.txt").read_text()
    assert not MG.PARADA.exists()


def test_registrar_escribe_el_informe_en_obsidian_y_crea_la_parada(tmp_path, monkeypatch):
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(claude_falso(tmp_path, salida_sup())))
    monkeypatch.setattr(SUP, "cuentas_alpaca", lambda: {"M1": cuenta(caida_desde_maximo=-0.4)})
    out = SUP.ciclo(HOY, registrar=True)
    assert Path(out["informe_fichero"]) == tmp_path / "obsidian" / "Supervisor" / f"{HOY}.md"
    assert MG.PARADA.exists() and "parada creada" in Path(out["informe_fichero"]).read_text()


@pytest.mark.parametrize("cambio", [{"carteras": {"B0": {"estado": "ok"}}}, {"version_mandato": "x"},
                                    {"informe_md": ""}, {"extra": 1},
                                    {"carteras": {k: {"estado": "regular"} for k in SUP.CARTERAS}}])
def test_salida_del_supervisor_invalida(cambio):
    with pytest.raises(G.SalidaInvalida):
        SUP.leer_salida(salida_sup(**cambio))


def test_agente_que_falla_deja_informe_minimo(tmp_path, monkeypatch):
    env = {"type": "result", "subtype": "success", "is_error": True, "result": "usage limit reached"}
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(claude_falso(tmp_path, envoltorio=env)))
    out = SUP.ciclo(HOY, cuentas={})
    assert not out["claude"]["ok"] and out["claude"]["cupo_agotado"]
    assert "no produjo informe" in Path(out["informe_fichero"]).read_text()
    assert SUP.main(["--registrar", "--simulada"]) == 1


def test_plist_supervisor_8_00_diario_y_no_instalado():
    import plistlib
    p = plistlib.loads((REPO / "scripts" / "launchd" / "com.financialkb.supervisor.plist").read_bytes())
    assert p["Label"] == "com.financialkb.supervisor" and p["ProgramArguments"][-1].endswith("scripts/supervisor.sh")
    assert p["StartCalendarInterval"] == {"Hour": 8, "Minute": 0} and not p["RunAtLoad"]
    assert not (Path.home() / "Library" / "LaunchAgents" / "com.financialkb.supervisor.plist").exists()
    t = SUP.MANDATO.read_text()
    assert "version: supervisor-v1" in t and '"version_mandato": "supervisor-v1"' in t and "Nunca operas" in t
