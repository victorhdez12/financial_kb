"""Modo agente de solo lectura (src/paper/agente.py) y C1 en modo agente (c1-v2). Con un `claude` FALSO, sin red, sin
claves y sin tocar los registros reales. La prueba de aislamiento REAL (con `claude` de verdad y un señuelo) se
documenta en el informe del Constructor; aquí se comprueba por construcción qué carpetas y reglas recibe."""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from src.broker import alpaca as A
from src.broker import c1_guardia as G
from src.paper import agente as AG
from src.paper import c1 as C
from src.paper import c1_paquete as P
from tests.agente_falso import archivo_y_repo, args, claude_falso

REPO = C.REPO
REG_REAL = REPO / "research" / "paper" / "decisiones_c1.jsonl"


@pytest.fixture(autouse=True)
def aislado(tmp_path, monkeypatch):
    for k in list(os.environ):
        if k.startswith(("ALPACA_", "APCA_")):
            monkeypatch.delenv(k)
    monkeypatch.setenv("FIN_ALPACA_ENV", str(tmp_path / "alpaca.env"))
    monkeypatch.setenv("FIN_ALPACA_DIR", str(tmp_path / "alpaca"))
    monkeypatch.setenv("FIN_C1_DIR", str(tmp_path / "c1"))
    a, r = archivo_y_repo(tmp_path)
    monkeypatch.setenv("FIN_DATA_ROOT", str(a))
    monkeypatch.setenv("FIN_AGENTE_REPO", str(r))
    monkeypatch.setattr(A, "_transporte_requests", lambda *a, **k: (_ for _ in ()).throw(AssertionError("red real")))
    monkeypatch.setattr(P, "cierres_warehouse", lambda X=None: {"fuente": "test", "activos": {
        "SPY": {"fecha": "2026-11-18", "cierre": 600.0}, "GLD": {"fecha": "2026-11-18", "cierre": 250.0}}})
    monkeypatch.setattr(P, "alertas", lambda hoy: [{"ticker": "UNH", "frase": "volumen anormal"}])
    monkeypatch.setattr(P, "resumen_panel", lambda s: ["EE. UU. en Goldilocks"])
    monkeypatch.setattr(P, "ultimo_signal", lambda: ({"asof": "2026-11-17", "regime": {"quadrant": "Goldilocks"}},
                                                     "x_signal.json"))
    monkeypatch.setattr(G, "PARADA", tmp_path / "C1_PARADA")
    monkeypatch.setattr(AG, "ruta_diario", lambda cartera, fecha, repo=None: tmp_path / "obsidian" / cartera / f"{fecha}.md")
    antes = REG_REAL.read_bytes() if REG_REAL.exists() else None
    yield
    assert (REG_REAL.read_bytes() if REG_REAL.exists() else None) == antes, "un test tocó el registro real de C1"


def propuesta_v2(ordenes=None, **kw) -> str:
    d = {"version_mandato": "c1-v2", "fecha": "2026-11-19", "resumen": "Mercado tranquilo.",
         "ordenes": ordenes if ordenes is not None else [], "nota_diario": "Sin cambios.",
         "diario_md": "## Hoy\nLeí el paquete y el panel; no veo motivo para operar."}
    d.update(kw)
    return json.dumps(d, ensure_ascii=False)


# ------------------------------------------------------------------ carpetas y reglas (por construcción)
def test_directorios_enumerados_sin_raiz_ni_config(tmp_path):
    a, r = Path(os.environ["FIN_DATA_ROOT"]), Path(os.environ["FIN_AGENTE_REPO"])
    ds = AG.directorios("C1")
    assert a.resolve() not in ds and (a / "config").resolve() not in ds
    assert all(not str(d).startswith(str((a / "config").resolve())) for d in ds)
    assert (a / "panel").resolve() in ds and (a / "macro").resolve() in ds
    assert (a / ".venv").resolve() not in ds and (a / "raw").resolve() not in ds and (a / "logs").resolve() not in ds
    assert (r / "data").resolve() not in ds and (r / "research" / "paper").resolve() not in ds
    assert (r / "research" / "int").resolve() in ds and (r / "obsidian").resolve() in ds
    sup = AG.directorios("supervisor")
    assert (r / "research" / "paper").resolve() in sup and (a / "logs").resolve() in sup
    assert a.resolve() not in sup and (a / "config").resolve() not in sup


@pytest.mark.parametrize("destino", ["raiz", "config"])
def test_una_subcarpeta_que_apunta_a_config_o_a_la_raiz_aborta(tmp_path, destino):
    a = Path(os.environ["FIN_DATA_ROOT"])
    (a / "macro").rmdir()
    (a / "macro").symlink_to(a if destino == "raiz" else a / "config")
    with pytest.raises(AG.AislamientoRoto):
        AG.directorios("M1")


def test_ajustes_niegan_config_paper_data_env_y_el_diario_del_otro(tmp_path):
    a, r = Path(os.environ["FIN_DATA_ROOT"]), Path(os.environ["FIN_AGENTE_REPO"])
    ds = AG.directorios("C1")
    aj = AG.ajustes("C1", ds, tmp_path / "t")
    deny, allow = aj["permissions"]["deny"], aj["permissions"]["allow"]
    assert f"Read(/{a.resolve()}/config/**)" in deny and "Read(~/financial_archive/config/**)" in deny
    assert f"Read(/{r.resolve()}/research/paper/**)" in deny and f"Read(/{r.resolve()}/data/**)" in deny
    assert "Read(**/.env)" in deny and "Read(**/*.env)" in deny
    assert f"Read(/{r.resolve()}/obsidian/Carteras/M1/**)" in deny
    assert {"Bash", "Write", "Edit", "WebFetch", "WebSearch"} <= set(deny)
    assert aj["permissions"]["defaultMode"] == "dontAsk" and aj["disableAllHooks"] is True
    assert all(x.startswith("Read(//") and x.endswith("/**)") for x in allow)
    assert not any("config/**" in x and str(a) in x for x in allow)
    sup = AG.ajustes("supervisor", AG.directorios("supervisor"), tmp_path / "t")["permissions"]["deny"]
    assert f"Read(/{r.resolve()}/research/paper/**)" not in sup and f"Read(/{a.resolve()}/config/**)" in sup


def test_comando_solo_lectura_sin_allowedtools_ni_mcp(tmp_path):
    ds = AG.directorios("C1")
    cmd = AG.comando("MANDATO", ds, tmp_path / "ajustes.json")
    assert cmd[1] == "-p" and "--restricted" in cmd and "--strict-mcp-config" in cmd
    assert cmd[cmd.index("--tools") + 1] == "Read,Grep,Glob" and "--allowedTools" not in cmd
    assert cmd[cmd.index("--permission-mode") + 1] == "dontAsk"
    assert cmd[cmd.index("--settings") + 1] == str(tmp_path / "ajustes.json")
    i = cmd.index("--add-dir")
    assert cmd[i + 1:i + 1 + len(ds)] == [str(d) for d in ds] and cmd[i + 1 + len(ds)] == "--system-prompt"
    assert not any("/config" in x and "financial_archive" in x for x in cmd)
    a = Path(os.environ["FIN_DATA_ROOT"])
    assert str(a.resolve()) not in cmd and str((a / "config").resolve()) not in cmd


# ------------------------------------------------------------------ ejecución con claude falso
def test_ejecutar_sin_claves_en_su_carpeta_y_con_su_registro(tmp_path, monkeypatch):
    f = claude_falso(tmp_path, propuesta_v2())
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(f))
    monkeypatch.setenv("ALPACA_API_KEY_ID_C1", "PKSECRETOQUENODEBEPASAR")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "otrosecreto")
    reg = tmp_path / "reg.jsonl"
    reg.write_text('{"fecha": "2026-11-18"}\n')
    r = AG.ejecutar("C1", tmp_path / "t", sistema_txt="MANDATO X", prompt_txt="hola", copias={"mi_registro.jsonl": reg})
    assert r["ok"] and r["modelo"] == ["claude-opus-5-5"] and r["coste_usd"] == 0.42 and r["turnos"] == 7
    env = (f.parent / "env.txt").read_text()
    assert "PKSECRETOQUENODEBEPASAR" not in env and "otrosecreto" not in env and "ALPACA" not in env
    assert Path((f.parent / "pwd.txt").read_text().strip()).resolve() == (tmp_path / "t").resolve()
    assert (tmp_path / "t" / "mi_registro.jsonl").read_text() == reg.read_text()
    assert (f.parent / "stdin.txt").read_text() == "hola"
    aj = json.loads((tmp_path / "t" / "ajustes.json").read_text())
    assert any("config/**" in x for x in aj["permissions"]["deny"])


def test_ejecutar_plazo_vencido_mata_el_proceso(tmp_path, monkeypatch):
    f = claude_falso(tmp_path, dormir=30)
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(f))
    t0 = time.monotonic()
    r = AG.ejecutar("M1", tmp_path / "t", sistema_txt="x", prompt_txt="x", plazo=1)
    assert not r["ok"] and "tardó" in r["error"] and time.monotonic() - t0 < 10
    assert subprocess.run(["pgrep", "-f", str(f.parent)], capture_output=True, text=True).stdout.strip() == ""


def test_cupo_de_la_suscripcion_agotado_se_anota(tmp_path, monkeypatch):
    env = {"type": "result", "subtype": "success", "is_error": True,
           "result": "Claude AI usage limit reached|1763600000", "modelUsage": {}}
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(claude_falso(tmp_path, envoltorio=env)))
    r = AG.ejecutar("C1", tmp_path / "t", sistema_txt="x", prompt_txt="x")
    assert not r["ok"] and r["cupo_agotado"] and "cupo" in r["error"]
    assert AG.interpreta("", 1, "API Error: 529 overloaded")["cupo_agotado"] is False


def test_sistema_lleva_mandato_y_conocimiento():
    s = AG.sistema(C.MANDATO_AGENTE)
    assert "c1-v2" in s and "DOCUMENTO DE CONOCIMIENTO" in s and "contango" in s
    assert AG.CONOCIMIENTO.exists() and len(AG.CONOCIMIENTO.read_text().split()) < 3500   # ≤ ~6 páginas


# ------------------------------------------------------------------ C1 en modo agente (c1-v2)
def test_c1_agente_ensayo_valida_y_escribe_el_diario_en_la_carpeta_de_trabajo(tmp_path, monkeypatch):
    ordenes = [{"simbolo": "SPY", "clase": "accion", "lado": "compra", "tipo": "mercado", "importe_usd": 30000,
                "razon": "Núcleo.", "cambiaria_de_opinion": "Recesión."},
               {"simbolo": "GLD", "clase": "accion", "lado": "compra", "tipo": "mercado", "importe_usd": 90000,
                "razon": "Oro.", "cambiaria_de_opinion": "x"}]                       # supera el efectivo
    f = claude_falso(tmp_path, propuesta_v2(ordenes))
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(f))
    linea = C.ciclo(None, hoy=dt.date(2026, 11, 19), registro=[{"fecha": "2026-11-18", "opera": False}])
    assert linea["modo"] == "agente" and linea["mandato"]["version"] == "c1-v2"
    assert linea["mandato"]["sha256"] == C.sha256_fichero(C.MANDATO_AGENTE)
    assert linea["mandato"]["conocimiento"]["sha256"] == C.sha256_fichero(AG.CONOCIMIENTO)
    assert [n["simbolo"] for n in linea["guardia"]["validas"]] == ["SPY"] and linea["rechazadas"][0]["indice"] == 1
    d = Path(linea["diario"])
    assert d.parent == Path(linea["paquete"]["fichero"]).parent and d.name == "diario.md"   # ensayo: no en Obsidian
    t = d.read_text()
    assert "Leí el paquete" in t and "Guardia ❌ #1 GLD" in t and "ENSAYO" in t
    a = args(f)
    assert a[a.index("--tools") + 1] == "Read,Grep,Glob"
    trabajo = Path(linea["paquete"]["fichero"]).parent
    assert json.loads((trabajo / "paquete.json").read_text())["sha256"] == linea["paquete"]["sha256"]
    assert "paquete.json" in (f.parent / "stdin.txt").read_text()                 # el prompt apunta al paquete
    assert (trabajo / "mi_registro.jsonl").exists()


def test_c1_agente_sin_diario_es_salida_invalida(tmp_path, monkeypatch):
    d = json.loads(propuesta_v2())
    del d["diario_md"]
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(claude_falso(tmp_path, json.dumps(d))))
    linea = C.ciclo(None, hoy=dt.date(2026, 11, 19), registro=[])
    assert not linea["opera"] and "diario_md" in linea["motivo_no_opera"]
    assert "salida no válida" in Path(linea["diario"]).read_text()


def test_c1_agente_admite_una_frase_antes_del_bloque_json_final_y_nada_despues():
    # ensayo real 19-nov: el agente escribió «Ya tengo lo que necesito…» antes del ```json
    ok = "Ya tengo lo que necesito.\n\n```json\n" + propuesta_v2() + "\n```"
    assert C.leer_agente_c1(ok)["version_mandato"] == "c1-v2"
    for malo in (ok + "\nY algo después", "texto sin bloque " + propuesta_v2(),
                 "```json\n{}\n```\nmedio\n```json\n" + propuesta_v2() + "\n```x"):
        with pytest.raises(G.SalidaInvalida):
            C.leer_agente_c1(malo)
    with pytest.raises(G.SalidaInvalida):                      # el modo paquete (c1-v1) sigue siendo estricto
        G.leer_salida("Hola\n```json\n" + json.dumps({"version_mandato": "c1-v1", "ordenes": [],
                                                      "nota_diario": "x"}) + "\n```")


def test_c1_agente_respuesta_v1_no_vale_en_modo_agente(tmp_path, monkeypatch):
    v1 = json.dumps({"version_mandato": "c1-v1", "fecha": "2026-11-19", "ordenes": [], "nota_diario": "x"})
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(claude_falso(tmp_path, v1)))
    linea = C.ciclo(None, hoy=dt.date(2026, 11, 19), registro=[])
    assert not linea["opera"] and "c1-v2" in linea["motivo_no_opera"]


def test_c1_agente_con_cupo_agotado_no_opera_y_se_anota(tmp_path, monkeypatch):
    env = {"type": "result", "subtype": "success", "is_error": True, "result": "You've hit your limit"}
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(claude_falso(tmp_path, envoltorio=env)))
    linea = C.ciclo(None, hoy=dt.date(2026, 11, 19), registro=[])
    assert not linea["opera"] and linea["claude"]["cupo_agotado"] and "cupo" in linea["motivo_no_opera"]


def test_c1_agente_con_parada_no_lanza_el_agente(tmp_path, monkeypatch):
    f = claude_falso(tmp_path, propuesta_v2())
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(f))
    (tmp_path / "C1_PARADA").write_text("supervisor")
    linea = C.ciclo(None, hoy=dt.date(2026, 11, 19), registro=[])
    assert not linea["opera"] and "C1_PARADA" in linea["motivo_no_opera"] and not (f.parent / "args.txt").exists()


def test_c1_agente_con_aislamiento_roto_no_lanza_el_agente(tmp_path, monkeypatch):
    f = claude_falso(tmp_path, propuesta_v2())
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(f))
    a = Path(os.environ["FIN_DATA_ROOT"])
    (a / "macro").rmdir()
    (a / "macro").symlink_to(a)
    linea = C.ciclo(None, hoy=dt.date(2026, 11, 19), registro=[])
    assert not linea["opera"] and "aislamiento" in linea["motivo_no_opera"] and not (f.parent / "args.txt").exists()


def test_c1_agente_registrado_escribe_el_diario_en_obsidian(tmp_path, monkeypatch):
    from tests.test_c1 import Falso, cliente
    ordenes = [{"simbolo": "SPY", "clase": "accion", "lado": "compra", "tipo": "mercado", "importe_usd": 500,
                "razon": "x", "cambiaria_de_opinion": "y"}]
    monkeypatch.setenv("FIN_AGENTE_CLAUDE", str(claude_falso(tmp_path, propuesta_v2(ordenes))))
    t = Falso()
    linea = C.ciclo(cliente(t), hoy=dt.date(2026, 11, 19), registro=[], enviar=True, dormir=lambda s: None)
    assert Path(linea["diario"]) == tmp_path / "obsidian" / "C1" / "2026-11-19.md"
    assert "Registro" in Path(linea["diario"]).read_text()
    posts = [x[4] for x in t.llamadas if x[0] == "POST"]
    assert posts and posts[0]["client_order_id"].startswith("c1-2026-11-19-")


def test_plazo_agente_15_min_y_modo_por_defecto():
    assert AG.PLAZO_S == 900 and C.cartera_c1().plazo == 900 and C.cartera_c1("paquete").plazo == 600
    assert C.MODO_DEFECTO == "agente" and C.cartera_c1().version == "c1-v2"


def test_gitignore_deja_fuera_los_diarios_y_las_paradas():
    g = (REPO / ".gitignore").read_text()
    assert "obsidian/Carteras/" in g and "research/paper/*_PARADA" in g
