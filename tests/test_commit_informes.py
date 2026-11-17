"""scripts/commit_informes.sh (lo llama actualizar.sh al acabar la semanal): commitea solo los informes de la semanal
para que E1/B1′/B1 (día 3) e INT-11 (día 20) no aborten por árbol sucio (docs/int/ENSAYO_cierre_nov2026.md, F1).
Usa el repo de juguete de tests/test_paper_mensual.py."""
from __future__ import annotations

import subprocess

from tests.test_paper_mensual import REPO, _corre, _git, juguete  # noqa: F401  (juguete es el fixture)

INFORMES = REPO / "scripts/commit_informes.sh"


def test_informes_de_la_semanal_sin_commitear_bloquean_y_commit_informes_lo_arregla(juguete):
    repo, logs, remoto, _ = juguete
    (repo / "obsidian/Reports/2026-11-29_semanal.md").write_text("x\n")
    (repo / "obsidian/Reports/2026-11-29_signal.json").write_text("{}\n")
    (repo / "docs/data").mkdir(parents=True)
    (repo / "docs/data/audit_2026-11-29_series.csv").write_text("a\n")
    (repo / "obsidian/Reports/2026-11-22_semanal.md").write_text("reescrito\n")
    _, nota = _corre(juguete)
    assert "árbol de git sucio" in nota and not (logs / ".e1_hecho_2026-12").exists()
    (repo / "ajeno.txt").write_text("no es un informe\n")
    (repo / "a_medias.py").write_text("x\n")
    _git(repo, "add", "a_medias.py")                      # algo en el índice: NO debe entrar en el commit
    r = subprocess.run(["bash", str(INFORMES), str(repo)], capture_output=True, text=True, check=True)
    assert "commiteados 4" in r.stdout
    assert sorted(_git(repo, "show", "--name-only", "--format=", "HEAD").split()) == sorted([
        "docs/data/audit_2026-11-29_series.csv", "obsidian/Reports/2026-11-22_semanal.md",
        "obsidian/Reports/2026-11-29_semanal.md", "obsidian/Reports/2026-11-29_signal.json"])
    assert sorted(_git(repo, "status", "--porcelain").splitlines()) == ["?? ajeno.txt", "A  a_medias.py"]
    assert _git(remoto, "rev-parse", "main") != _git(repo, "rev-parse", "main")   # sin push
    _git(repo, "rm", "-q", "--cached", "a_medias.py")
    (repo / "a_medias.py").unlink()
    (repo / "ajeno.txt").unlink()
    _, nota = _corre(juguete, hoy="2026-12-04")
    assert (logs / ".e1_hecho_2026-12").exists() and (logs / ".paper_hecho_2026-12").exists()
    assert _git(remoto, "rev-parse", "main") == _git(repo, "rev-parse", "main")    # el push del registro lo sube


def test_commit_informes_fuera_de_main_no_hace_nada(juguete):
    repo = juguete[0]
    _git(repo, "checkout", "-q", "-b", "otra")
    (repo / "obsidian/Reports/2026-11-29_semanal.md").write_text("x\n")
    r = subprocess.run(["bash", str(INFORMES), str(repo)], capture_output=True, text=True, check=True)
    assert "no estoy en main" in r.stdout and "??" in _git(repo, "status", "--porcelain")
