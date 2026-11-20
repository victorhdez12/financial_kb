"""Utilidades de test para el modo agente: un `claude` FALSO que apunta argumentos, entorno, carpeta y entrada, y
responde como `claude -p --output-format json`. Sin red."""
from __future__ import annotations

import json
import stat
from pathlib import Path


def claude_falso(tmp_path: Path, resultado: str | None = None, *, dormir: int = 0, codigo: int = 0,
                 envoltorio: dict | None = None, nombre: str = "falso") -> Path:
    d = tmp_path / nombre
    d.mkdir(exist_ok=True)
    env = envoltorio or {"type": "result", "subtype": "success", "is_error": False, "duration_ms": 61_000,
                         "num_turns": 7, "result": resultado if resultado is not None else "{}",
                         "total_cost_usd": 0.42, "modelUsage": {"claude-opus-5-5": {"inputTokens": 1}}}
    (d / "respuesta.json").write_text(json.dumps(env))
    s = d / "claude"
    s.write_text(f"""#!/bin/bash
printf '%s\\n' "$@" > {d}/args.txt
env > {d}/env.txt
pwd > {d}/pwd.txt
cat > {d}/stdin.txt
sleep {dormir}
cat {d}/respuesta.json
exit {codigo}
""")
    s.chmod(s.stat().st_mode | stat.S_IEXEC)
    return s


def args(falso: Path) -> list[str]:
    return (falso.parent / "args.txt").read_text().splitlines()


def archivo_y_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Archivo y repo FALSOS con la forma de los reales (config/ con un señuelo, data/archive enlazado al archivo)."""
    a, r = tmp_path / "archivo", tmp_path / "repo"
    for d in ("config", "panel", "macro", "mercados", "logs", "alpaca", ".venv", "raw"):
        (a / d).mkdir(parents=True)
    (a / "config" / "alpaca.env").write_text("ALPACA_API_KEY_ID_C1=SENUELO_TEST_0001\n")
    for d in ("config", "docs", "obsidian/Carteras/C1", "obsidian/Carteras/M1", "src", "scripts", "research/int",
              "research/paper", "data"):
        (r / d).mkdir(parents=True)
    (r / "data" / "archive").symlink_to(a)
    (r / ".env").write_text("SENUELO_TEST_0002\n")
    return a, r
