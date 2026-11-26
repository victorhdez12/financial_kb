"""scripts/recupera_gestores.sh y el cerrojo de los gestores (ciclos C1/M1/A1 perdidos: Mac apagado o sin red)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOY = "2026-11-25"


def repo_falso(tmp_path, activos=("C1", "M1", "A1"), cerrado=False):
    """Repo con gestores FALSOS que solo apuntan que se lanzaron (y si FIN_RECUPERADA llega)."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "research" / "paper").mkdir(parents=True)
    (repo / "scripts" / "recupera_gestores.sh").write_text((REPO / "scripts" / "recupera_gestores.sh").read_text())
    logs = tmp_path / "logs"
    logs.mkdir()
    for g in ("c1", "m1", "a1"):
        msg = "mercado cerrado (abre mañana): sin registro" if cerrado else "registrada y subida"
        (repo / "scripts" / f"{g}_gestor.sh").write_text(
            f'echo "{g} ${{FIN_RECUPERADA:-}}" >> "{tmp_path}/lanzados.txt"\n'
            f'echo "{msg}" > "{logs}/$(date +%H%M%S)_${{RANDOM}}_{g}.log"\n')
    for p in activos:
        (repo / "research" / "paper" / f"{p}_ACTIVO").write_text("")
    return repo, logs


def corre(tmp_path, repo, logs, ahora, dow=3):
    env = {**os.environ, "FIN_REPO": str(repo), "FIN_LOGDIR": str(logs), "FIN_AHORA": ahora,
           "FIN_DOW": str(dow), "FIN_HOY": HOY}
    r = subprocess.run(["/bin/bash", str(repo / "scripts" / "recupera_gestores.sh")], capture_output=True,
                       text=True, env=env)
    assert r.returncode == 0, r.stderr
    f = tmp_path / "lanzados.txt"
    return f.read_text().splitlines() if f.exists() else []


def test_lanza_solo_los_que_ya_tocaban_y_marca_recuperado(tmp_path):
    repo, logs = repo_falso(tmp_path)
    assert corre(tmp_path, repo, logs, "1605") == ["c1 1", "m1 1"]          # A1 (16:15) aún no toca


def test_nada_en_fin_de_semana_antes_de_hora_o_de_noche(tmp_path):
    repo, logs = repo_falso(tmp_path)
    assert corre(tmp_path, repo, logs, "1700", dow=6) == []
    assert corre(tmp_path, repo, logs, "1544") == []
    assert corre(tmp_path, repo, logs, "2231") == []
    assert corre(tmp_path, repo, logs, "0930") == []                         # 10#: «0930» no es octal


def test_no_relanza_si_ya_hay_decision_de_hoy_ni_sin_activo_ni_con_ciclo_en_marcha(tmp_path):
    repo, logs = repo_falso(tmp_path, activos=("C1", "M1"))
    (repo / "research" / "paper" / "decisiones_c1.jsonl").write_text(
        '{"fecha": "2026-11-24"}\n{"fecha": "%s", "opera": false}\n' % HOY)
    (logs / ".gestor_m1.lock").mkdir()
    assert corre(tmp_path, repo, logs, "1800") == []


def test_decision_de_ayer_no_cuenta_como_hoy(tmp_path):
    repo, logs = repo_falso(tmp_path, activos=("C1",))
    (repo / "research" / "paper" / "decisiones_c1.jsonl").write_text('{"fecha": "2026-11-24"}\n')
    assert corre(tmp_path, repo, logs, "1800") == ["c1 1"]


def test_mercado_cerrado_no_se_reintenta_hoy(tmp_path):
    repo, logs = repo_falso(tmp_path, cerrado=True)
    assert corre(tmp_path, repo, logs, "1800") == ["c1 1"]                   # para tras el primero
    assert (logs / ".mercado_cerrado").read_text().strip() == HOY
    assert corre(tmp_path, repo, logs, "1900") == ["c1 1"]                   # la hora siguiente: nada nuevo


def test_gestor_real_con_cerrojo_no_lanza_un_segundo_ciclo(tmp_path):
    for g in ("c1", "m1", "a1"):
        repo = tmp_path / g / "repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "research" / "paper").mkdir(parents=True)
        (repo / "research" / "paper" / f"{g.upper()}_ACTIVO").write_text("")
        (repo / "scripts" / f"{g}_gestor.sh").write_text((REPO / "scripts" / f"{g}_gestor.sh").read_text())
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        logs = tmp_path / g / "logs"
        (logs / f".gestor_{g}.lock").mkdir(parents=True)
        r = subprocess.run(["/bin/bash", str(repo / "scripts" / f"{g}_gestor.sh")], capture_output=True, text=True,
                           env={**os.environ, "FIN_REPO": str(repo), "FIN_LOGDIR": str(logs),
                                "FIN_SIN_AVISOS": "1", "FIN_SIN_ESPERA_RED": "1"})
        assert r.returncode == 0
        assert "ya hay un ciclo" in next(logs.glob(f"*_{g}.log")).read_text()
        assert (logs / f".gestor_{g}.lock").is_dir()                         # el cerrojo ajeno no se borra


# ------------------------------------------------------------------ Validador 26-nov
class _Alpaca:
    """Transporte FALSO: mercado abierto, sin órdenes abiertas, cada POST se apunta y se ejecuta."""
    def __init__(self):
        self.posts = []

    def __call__(self, metodo, url, cab, params, cuerpo, plazo):
        if url.endswith("/v2/orders") and metodo == "GET":
            return 200, []
        if url.endswith("/v2/clock"):
            return 200, {"timestamp": "2026-11-25T11:00:00-05:00", "is_open": True,
                         "next_close": "2026-11-25T16:00:00-05:00", "next_open": "2026-11-27T09:30:00-05:00"}
        if metodo == "POST":
            self.posts.append(cuerpo)
            return 200, {"id": f"o{len(self.posts)}", "status": "new"}
        return 200, {"status": "filled", "filled_qty": "1", "filled_avg_price": "100"}


def test_un_ciclo_relanzado_no_reenvia_ordenes_ya_enviadas_hoy(tmp_path, monkeypatch):
    """Ciclo 1 envía y muere antes de dejar la línea en git (o `restaura` la deshace); la recuperación relanza el
    ciclo el mismo día: NO debe volver a enviar (aunque el agente decida otra cosa, con otros índices)."""
    from src.broker import alpaca as A
    from src.broker import c1_guardia as G
    from src.paper import c1 as C
    monkeypatch.setattr(A, "_transporte_requests", lambda *a, **k: (_ for _ in ()).throw(AssertionError("red real")))
    base = tmp_path / "c1"
    t = _Alpaca()
    c = A.Cliente(A.Credenciales(key_id="K", secret="S", perfil="C1"), transporte=t)
    n = {"indice": 1, "simbolo": "AAA", "clase": "accion", "lado": "compra", "tipo": "mercado", "cantidad": None,
         "importe_usd": 100.0, "precio_limite": None}
    out = C.ejecutar(c, G.Veredicto(True, None, validas=[n]), HOY, espera_s=0, dormir=lambda s: None, base=base)
    assert len(t.posts) == 1 and out["enviadas"]
    otra = {**n, "indice": 2, "simbolo": "BBB"}
    out = C.ejecutar(c, G.Veredicto(True, None, validas=[otra]), HOY, espera_s=0, dormir=lambda s: None, base=base)
    assert len(t.posts) == 1 and out["enviadas"] == []
    assert "ya se enviaron 1 órdenes hoy" in out["rechazadas_alpaca"][0]["motivo"]
    assert out["enviadas_previas"][0]["simbolo"] == "AAA"
    out = C.ejecutar(c, G.Veredicto(True, None, validas=[otra]), "2026-11-27", espera_s=0, dormir=lambda s: None,
                     base=base)
    assert len(t.posts) == 2                                                # otro día sí envía


def test_rechazos_de_alpaca_previos_no_bloquean_el_envio(tmp_path):
    from src.paper import c1 as C
    base = tmp_path / "c1"
    (base / "ordenes").mkdir(parents=True)
    (base / "ordenes" / f"{HOY}.jsonl").write_text('{"indice": 1, "simbolo": "AAA", "motivo": "422"}\nbasura\n')
    assert C._enviadas_hoy(HOY, base) == []


def test_mercado_cerrado_solo_por_el_aviso_de_main_y_sin_linea_de_hoy(tmp_path):
    """El resumen/diario del agente (impreso en el log) puede decir «mercado cerrado» (p. ej. «mañana mercado
    cerrado por Acción de Gracias»): eso no es el aviso de main() y no debe parar la recuperación de M1/A1."""
    repo, logs = repo_falso(tmp_path)
    for g in ("c1", "m1", "a1"):
        (repo / "scripts" / f"{g}_gestor.sh").write_text(
            f'echo "{g} ${{FIN_RECUPERADA:-}}" >> "{tmp_path}/lanzados.txt"\n'
            f'echo "resumen: mañana mercado cerrado (abre el viernes) por Acción de Gracias" '
            f'> "{logs}/$(date +%H%M%S)_${{RANDOM}}_{g}.log"\n'
            f'echo \'{{"fecha": "{HOY}"}}\' >> research/paper/decisiones_{g}.jsonl\n')
    assert corre(tmp_path, repo, logs, "1800") == ["c1 1", "m1 1", "a1 1"]
    assert not (logs / ".mercado_cerrado").exists()


def test_fecha_de_hoy_anidada_en_una_linea_de_ayer_no_cuenta(tmp_path):
    repo, logs = repo_falso(tmp_path, activos=("C1",))
    (repo / "research" / "paper" / "decisiones_c1.jsonl").write_text(
        '{"fecha": "2026-11-24", "propuesta": {"fecha": "%s"}}\n' % HOY)
    assert corre(tmp_path, repo, logs, "1800") == ["c1 1"]
