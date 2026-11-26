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
