"""scripts/int11_vivo_mensual.sh (launchd com.financialkb.int11vivo) en un repo de juguete: el motor se sustituye por un
`.venv/bin/python` falso que solo escribe el JSON del mes. Nada toca el repo ni el registro reales."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SH = REPO / "scripts/int11_vivo_mensual.sh"
CARPETA = "research/int/int11_v3_1_vivo"

PY_FALSO = """#!/bin/bash
echo "$@" >> "$FIN_LLAMADAS"
case " $* " in
  *" --registro "*) mkdir -p research/int/int11_v3_1_vivo; echo '{}' > research/int/int11_v3_1_vivo/${FIN_HOY:0:7}.json ;;
  *" --ensayo "*) echo "ensayo" ;;
esac
exit "${FIN_PY_RC:-0}"
"""


def _git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def juguete(tmp_path):
    remoto, repo, logs = tmp_path / "remoto.git", tmp_path / "repo", tmp_path / "logs"
    _git(tmp_path, "init", "-q", "--bare", str(remoto))
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    py = repo / ".venv/bin/python"
    py.parent.mkdir(parents=True)
    py.write_text(PY_FALSO)
    py.chmod(0o755)
    (repo / ".gitignore").write_text(".venv/\n")
    (repo / "a.txt").write_text("a\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "remote", "add", "origin", str(remoto))
    _git(repo, "push", "-q", "origin", "main")
    return repo, logs, remoto, tmp_path / "llamadas.txt"


def _corre(juguete, hoy="2026-11-20", **env):
    repo, logs, _, llamadas = juguete
    e = {**os.environ, "FIN_REPO": str(repo), "FIN_LOGDIR": str(logs), "FIN_NOTA": str(logs / "nota.md"),
         "FIN_HOY": hoy, "FIN_ESPERA_RED": "0", "FIN_ESPERA_DIARIO_MIN": "0", "FIN_LLAMADAS": str(llamadas), **env}
    subprocess.run(["bash", str(SH)], env=e, check=True, capture_output=True, text=True, timeout=60)
    return (llamadas.read_text() if llamadas.exists() else ""), ((logs / "nota.md").read_text()
                                                                 if (logs / "nota.md").exists() else "")


def test_antes_del_20_no_hace_nada(juguete):
    llamadas, nota = _corre(juguete, hoy="2026-11-19")
    assert llamadas == "" and nota == ""


def test_emite_commitea_solo_el_registro_y_sube(juguete):
    repo, logs, remoto, _ = juguete
    (repo / "otro.txt").write_text("x\n")
    _git(repo, "add", "otro.txt")                      # algo ya en el índice: NO debe entrar en el commit del registro
    llamadas, nota = _corre(juguete)
    assert "--registro" not in llamadas                # árbol sucio fuera del registro: no se lanza el motor
    assert "árbol sucio" in nota
    _git(repo, "reset", "-q", "otro.txt")
    (repo / "otro.txt").unlink()
    llamadas, nota = _corre(juguete)
    assert "--registro" in llamadas and "✅" in nota.splitlines()[-1]
    assert (logs / ".int11_hecho_2026-11").exists()
    assert _git(remoto, "log", "-1", "--name-only", "--format=", "main").split() == [f"{CARPETA}/2026-11.json"]
    assert _corre(juguete)[0] == llamadas              # marca del mes: no se repite


def test_push_fallido_se_reintenta_sin_reemitir(juguete):
    repo, logs, remoto, llamadas = juguete
    _git(repo, "remote", "set-url", "origin", str(remoto) + "_no_existe")
    _, nota = _corre(juguete)
    assert "push falló" in nota and not (logs / ".int11_hecho_2026-11").exists()
    _git(repo, "remote", "set-url", "origin", str(remoto))
    antes = llamadas.read_text().count("--registro")
    _, nota = _corre(juguete)
    assert llamadas.read_text().count("--registro") == antes        # no se re-emite (el registro no se sobrescribe)
    assert "✅" in nota.splitlines()[-1] and (logs / ".int11_hecho_2026-11").exists()
    assert f"{CARPETA}/2026-11.json" in _git(remoto, "log", "-1", "--name-only", "--format=", "main")


def test_fuera_de_main_no_emite(juguete):
    repo = juguete[0]
    _git(repo, "checkout", "-q", "-b", "otra")
    llamadas, nota = _corre(juguete)
    assert "--registro" not in llamadas and "no está en main" in nota


def test_ensayo_no_escribe_ni_commitea(juguete):
    repo, logs, remoto, _ = juguete
    cabeza = _git(remoto, "rev-parse", "main")
    llamadas, nota = _corre(juguete, FIN_INT11_ENSAYO="1")
    assert "--ensayo" in llamadas and "--registro" not in llamadas and "ENSAYO" in nota
    assert not (repo / CARPETA).exists() and not (logs / ".int11_hecho_2026-11").exists()
    assert _git(remoto, "rev-parse", "main") == cabeza and _git(repo, "status", "--porcelain") == ""
