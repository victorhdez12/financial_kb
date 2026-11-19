"""scripts/paper_mensual.sh (launchd com.financialkb.paper) en un repo de juguete
(ensayo del cierre de nov-2026, docs/int/ENSAYO_cierre_nov2026.md). Los .py de E1/K1/B1′/B1 se sustituyen por un
`.venv/bin/python` falso que imita sus guardas (árbol limpio, «ya registrado») y su escritura/commit/push.
Nada toca el repo ni los registros reales."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SH = REPO / "scripts/paper_mensual.sh"
F = {"e1": "research/int/e1_vivo.jsonl", "b1p": "research/paper/decisiones_b1prima.jsonl",
     "b1": "research/paper/decisiones.jsonl"}

PY_FALSO = r"""#!/bin/bash
echo "$*" >> "$FIN_LLAMADAS"
case "$2" in
  scripts.e1_vivo) f=research/int/e1_vivo.jsonl; k=e1; ok="registrado y subido" ;;
  scripts.k1_vivo) echo "no se registra: t = [2025]"; exit 0 ;;
  scripts.paper_decision_b1prima) f=research/paper/decisiones_b1prima.jsonl; k=b1p; ok="registrada y subida" ;;
  scripts.paper_decision) f=research/paper/decisiones.jsonl; k=b1; ok="registrada y subida" ;;
  *) exit 9 ;;
esac
case " $* " in *" --registrar "*) ;; *) echo ensayo; exit 0 ;; esac
grep -q "\"$FIN_CIERRE\"" "$f" 2>/dev/null && { echo "ya registrado"; exit 0; }
[ -n "$(git status --porcelain)" ] && { echo "árbol de git sucio: commitea antes de registrar"; exit 5; }
mkdir -p "$(dirname "$f")"; echo "{\"cierre\": \"$FIN_CIERRE\"}" >> "$f"
git add "$f"
[ "${FIN_FALLA:-}" = "$k:commit" ] && { echo "Traceback: commit fallido"; exit 1; }
git commit -q -m "registro $k" || exit 1
git push -q origin main || { echo "CalledProcessError: push"; exit 1; }
echo "$ok"
"""


def _git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def juguete(tmp_path):
    remoto, repo, logs = tmp_path / "remoto.git", tmp_path / "repo", tmp_path / "logs"
    _git(tmp_path, "init", "-q", "--bare", str(remoto))
    repo.mkdir()
    logs.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    py = repo / ".venv/bin/python"
    py.parent.mkdir(parents=True)
    py.write_text(PY_FALSO)
    py.chmod(0o755)
    (repo / ".gitignore").write_text(".venv/\n")
    (repo / "research/paper").mkdir(parents=True)
    (repo / "research/paper/ACTIVO").write_text("ok\n")
    (repo / F["b1"]).write_text('{"cierre": "2026-10-31"}\n')
    (repo / "obsidian/Reports").mkdir(parents=True)
    (repo / "obsidian/Reports/2026-11-22_semanal.md").write_text("viejo\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "remote", "add", "origin", str(remoto))
    _git(repo, "push", "-q", "-u", "origin", "main")
    (logs / "nota.md").write_text("# nota\n\n<!-- entradas -->\n")
    return repo, logs, remoto, tmp_path / "llamadas.txt"


def _corre(juguete, hoy="2026-12-03", ahora="1000", diaria_hecha=True, **env):
    repo, logs, _, llamadas = juguete
    if diaria_hecha:
        (logs / ".hecho_diario").write_text(hoy + "\n")
    e = {**os.environ, "FIN_REPO": str(repo), "FIN_LOGDIR": str(logs), "FIN_NOTA": str(logs / "nota.md"),
         "FIN_HOY": hoy, "FIN_AHORA": ahora, "FIN_CIERRE": "2026-11-30", "FIN_ESPERA_RED": "0",
         "FIN_ESPERA_DIARIO_MIN": "0", "FIN_ESPERA_LOCK_MIN": "0", "FIN_SIN_AVISOS": "1",
         "FIN_LLAMADAS": str(llamadas), **env}
    subprocess.run(["bash", str(SH)], env=e, capture_output=True, text=True, timeout=60)
    return (llamadas.read_text() if llamadas.exists() else ""), (logs / "nota.md").read_text()


def test_dias_1_y_2_no_hacen_nada(juguete):
    for hoy in ("2026-12-01", "2026-12-02"):
        assert _corre(juguete, hoy=hoy)[0] == ""


def test_al_encender_antes_de_las_730_espera_a_la_diaria(juguete):
    # jueves 3-dic, 7:05, diaria de hoy sin hacer: no lanza nada (lo hará la cita de las 10:00, tras la diaria)
    assert _corre(juguete, ahora="0705", diaria_hecha=False)[0] == ""
    # domingo: no hay diaria que esperar
    assert "scripts.e1_vivo" in _corre(juguete, hoy="2026-12-06", ahora="0705", diaria_hecha=False)[0]


def test_con_actualizacion_en_marcha_no_registra(juguete):
    (juguete[1] / ".actualizar.lock").mkdir()
    assert _corre(juguete)[0] == ""


def test_fuera_de_main_no_registra(juguete):
    _git(juguete[0], "checkout", "-q", "-b", "otra")
    llamadas, nota = _corre(juguete)
    assert llamadas == "" and "no está en main" in nota


def test_dia_3_registra_e1_b1prima_y_b1_cada_uno_solo_su_fichero(juguete):
    repo, logs, remoto, _ = juguete
    llamadas, nota = _corre(juguete)
    for m in ("scripts.e1_vivo", "scripts.k1_vivo", "scripts.paper_decision_b1prima", "scripts.paper_decision "):
        assert m in llamadas
    for k in ("e1", "b1p", "paper"):
        assert (logs / f".{k}_hecho_2026-12").exists()
    assert "✅ B1′" in nota and "✅ decisión registrada" in nota
    commits = _git(remoto, "log", "--name-only", "--format=format:@@", "main").split("@@")
    assert [c.split() for c in commits[1:4]] == [[F["b1"]], [F["b1p"]], [F["e1"]]]
    assert _git(repo, "status", "--porcelain") == ""
    antes = Path(juguete[3]).read_text()
    _corre(juguete, hoy="2026-12-04")                    # marcas del mes: solo K1 (anual) vuelve a mirar
    nuevas = Path(juguete[3]).read_text()[len(antes):]
    assert "scripts.k1_vivo" in nuevas and "e1_vivo" not in nuevas and "paper_decision" not in nuevas


@pytest.mark.parametrize("k", ["e1", "b1p"])
def test_commit_fallido_no_deja_el_arbol_sucio(juguete, k):
    # Antes: E1 dejaba su fichero añadido al índice (y B1′ lo borraba sin sacarlo del índice): árbol sucio →
    # E1, B1′ y B1 abortaban todos los días.
    repo, logs, _, _ = juguete
    _corre(juguete, FIN_FALLA=f"{k}:commit")
    assert _git(repo, "status", "--porcelain") == ""
    assert not (repo / F[k]).exists()
    otros = {"e1": ("b1p", "paper"), "b1p": ("e1", "paper")}[k]
    assert all((logs / f".{o}_hecho_2026-12").exists() for o in otros)   # los demás registros no se bloquean
    _corre(juguete, hoy="2026-12-04")                                     # el fallido se reintenta y sale
    assert (repo / F[k]).exists() and _git(repo, "status", "--porcelain") == ""


def test_push_fallido_se_sube_al_dia_siguiente(juguete):
    repo, logs, remoto, _ = juguete
    _git(repo, "remote", "set-url", "origin", str(remoto) + "_no_existe")
    _corre(juguete)
    assert _git(repo, "rev-list", "--count", "origin/main..main").strip() == "3"
    _git(repo, "remote", "set-url", "origin", str(remoto))
    _, nota = _corre(juguete, hoy="2026-12-04")
    assert "subidos commits de registro pendientes" in nota
    assert _git(remoto, "rev-parse", "main") == _git(repo, "rev-parse", "main")


def _espejo(llamadas: str) -> list[str]:
    return [l.strip() for l in llamadas.splitlines() if "src.broker.espejo" in l]


def test_espejo_alpaca_tras_cada_registro_en_dry_run_antes_de_2026_12(juguete):
    # el python falso sale con 9 para src.broker.espejo (como un fallo): el registro no se entera
    # docs/broker/alpaca.md §7: B1′ tras su registro, B1 y B0 tras el de B1; el cierre de nov (registrado en dic) en dry-run
    llamadas, _ = _corre(juguete, hoy="2026-11-03")
    esp = _espejo(llamadas)
    assert len(esp) == 3 and all("--dry-run" in l and "--auto" in l for l in esp)
    assert [l.split("--cartera ")[1].split()[0] for l in esp] == ["B1P", "B1", "B0"]
    assert _git(juguete[0], "status", "--porcelain") == ""


def test_espejo_alpaca_ejecuta_desde_2026_12_y_el_entorno_manda(juguete):
    llamadas, _ = _corre(juguete, hoy="2026-12-03")
    assert all("--ejecutar" in l for l in _espejo(llamadas)) and len(_espejo(llamadas)) == 3


def test_espejo_alpaca_no_ejecuta_si_el_entorno_lo_prohibe(juguete):
    llamadas, _ = _corre(juguete, hoy="2027-01-04", FIN_ALPACA_EJECUTAR="0")
    assert _espejo(llamadas) and all("--dry-run" in l for l in _espejo(llamadas))


def test_espejo_alpaca_fallido_no_cambia_nada(juguete):
    repo, logs, _, _ = juguete
    llamadas, nota = _corre(juguete)                      # el python falso sale con 9 en el espejo
    assert _espejo(llamadas)
    assert (logs / ".paper_hecho_2026-12").exists() and "✅ decisión registrada" in nota
    assert _git(repo, "status", "--porcelain") == ""
