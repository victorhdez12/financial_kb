"""Modo agente de solo lectura para los gestores C1, M1 y A1 y para el supervisor de carteras
(docs/factors/C1_claude_gestor_spec.md §7, docs/factors/M1_cartera_macro_spec.md §7,
docs/factors/A1_seleccion_acciones_spec.md §6,
docs/factors/supervisor_carteras_spec.md §3).

`claude -p` con herramientas SOLO de lectura (Read, Grep, Glob) y acceso a una lista de carpetas ENUMERADA:
- del repo: `config`, `docs`, `obsidian`, `schema`, `scripts`, `src` y las subcarpetas de `research` salvo `paper`
  (nunca `data/`, que es un enlace a todo ~/financial_archive, ni `.env`, ni `research/paper/`). Su propio registro
  (`research/paper/decisiones_<x>.jsonl`) se le copia en su carpeta de trabajo. El supervisor sí lee research/paper
  (revisa los registros de todas las carteras) y además `logs`, `alpaca`, `c1`, `m1`, `a1` y `supervisor` del archivo;
- de ~/financial_archive (`FIN_DATA_ROOT`): solo las subcarpetas de datos listadas en `ARCHIVO_<ROL>`; NUNCA la raíz,
  así `config/` (claves de Alpaca) queda fuera por construcción;
- su carpeta de trabajo (paquete del día, su registro, prompt), fuera del repo.
Además, reglas `deny` (por si un enlace simbólico apuntara fuera): `config/**` del archivo, `research/paper/**`,
`data/**`, `.env`, `*.env`, los diarios de los otros gestores, y todas las herramientas que no son de lectura.
Permisos en modo `dontAsk` con `allow` solo para esas carpetas: lo que no está permitido se deniega sin preguntar.
Sin Bash, sin red, sin MCP, sin ajustes del usuario (`--restricted`), sin sesión guardada, con un entorno mínimo sin
variables ALPACA_*/APCA_*. El agente NO escribe: devuelve un JSON y Python escribe su diario (§7: «escritura solo en
su diario»: no tiene herramienta de escritura; el texto del diario viaja en el JSON).

Plazo por ejecución: 15 min (se mata el grupo de procesos). Si la suscripción no tiene cupo o claude falla: ese día
no opera (o no hay informe) y se anota (`cupo_agotado`).
Pruebas: FIN_AGENTE_CLAUDE (binario; por defecto FIN_C1_CLAUDE o ~/.local/bin/claude), FIN_AGENTE_MODELO (opus),
FIN_AGENTE_REPO (repo que lee el agente; por defecto este), FIN_DATA_ROOT.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLAZO_S = 900
CONOCIMIENTO = REPO / "config" / "gestor_conocimiento_v1.md"
REPO_DIRS = ("config", "docs", "obsidian", "schema", "scripts", "src")
RESEARCH_EXCLUIDOS = {"paper"}
# subcarpetas de ~/financial_archive que puede leer cada rol (enumeradas: la raíz nunca, config nunca)
ARCHIVO_GESTOR = ("panel", "macro", "mercados", "intl", "curated", "features", "events", "diag", "labels",
                  "sec_fundamentales", "sec_flujos", "sec_form4", "sec_13f", "sec_recompras", "finra_short")
ARCHIVO_SUPERVISOR = ARCHIVO_GESTOR + ("alpaca", "c1", "m1", "a1", "supervisor", "logs")
PROHIBIDOS_ARCHIVO = {"config", ".venv", "raw", "neo4j"}
HERRAMIENTAS = ("Read", "Grep", "Glob")
# nombres conocidos: un ajuste inválido haría que `claude -p` ignorase en silencio el fichero de ajustes entero
NEGADAS = ("Bash", "Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch", "Agent")
GESTORES = ("C1", "M1", "A1")
RE_CUPO = re.compile(r"usage limit|limit reached|hit your limit|rate.?limit|quota|out of (extra )?usage|"
                     r"credit balance|cupo", re.I)


class AislamientoRoto(RuntimeError):
    """Una carpeta de lectura incluiría config/ o la raíz del archivo: no se lanza el agente."""


def archivo_raiz() -> Path:
    return Path(os.path.expanduser(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")))


def repo_lectura() -> Path:
    return Path(os.path.expanduser(os.environ.get("FIN_AGENTE_REPO", str(REPO))))


def binario() -> str:
    return os.environ.get("FIN_AGENTE_CLAUDE") or os.environ.get("FIN_C1_CLAUDE") \
        or os.path.expanduser("~/.local/bin/claude")


def modelo() -> str:
    return os.environ.get("FIN_AGENTE_MODELO") or os.environ.get("FIN_C1_MODELO") or "opus"


def _dentro(p: Path, base: Path) -> bool:
    try:
        p.relative_to(base)
        return True
    except ValueError:
        return False


# --------------------------------------------------------------------------- carpetas y permisos
def directorios(rol: str, *, repo: Path | None = None, archivo: Path | None = None) -> list[Path]:
    """Carpetas de lectura del rol ('C1', 'M1', 'A1' o 'supervisor'), ya resueltas. Lanza AislamientoRoto si alguna es la
    raíz del archivo, está dentro de config/ o contiene config/ (p. ej. por un enlace simbólico)."""
    repo = (repo or repo_lectura()).resolve()
    archivo = archivo or archivo_raiz()
    arch = archivo.resolve() if archivo.exists() else archivo
    config = arch / "config"
    out: list[Path] = []
    for d in REPO_DIRS:
        out.append(repo / d)
    inv = repo / "research"
    if inv.is_dir():
        # el supervisor lee los registros de todas las carteras (research/paper); los gestores, no (su registro se les
        # copia a la carpeta de trabajo)
        out += [x for x in sorted(inv.iterdir()) if x.is_dir()
                and (rol == "supervisor" or x.name not in RESEARCH_EXCLUIDOS)]
    subs = ARCHIVO_SUPERVISOR if rol == "supervisor" else ARCHIVO_GESTOR
    for s in subs:
        if s in PROHIBIDOS_ARCHIVO:
            raise AislamientoRoto(f"subcarpeta prohibida en la lista: {s}")
        out.append(archivo / s)
    res = []
    for d in out:
        if not d.exists() or not d.is_dir():
            continue
        r = d.resolve()
        if r == arch or _dentro(r, config) or _dentro(config, r) or r == Path(os.path.expanduser("~")).resolve() \
                or r == Path("/"):
            raise AislamientoRoto(f"{d} → {r}: abriría la raíz del archivo o config/")
        if (rol != "supervisor" and _dentro(r, (repo / "research" / "paper").resolve())) \
                or _dentro(r, (repo / "data").resolve()):
            raise AislamientoRoto(f"{d} → {r}: research/paper o data/ del repo")
        if r not in res:
            res.append(r)
    return res


def _regla(p: Path) -> str:
    """Ruta absoluta en la sintaxis de reglas de permisos de Claude Code (`//ruta`)."""
    return "/" + str(p)


def ajustes(rol: str, dirs: list[Path], trabajo: Path, *, repo: Path | None = None,
            archivo: Path | None = None) -> dict:
    repo = (repo or repo_lectura()).resolve()
    archivo = archivo or archivo_raiz()
    cfg = [archivo / "config", archivo.resolve() / "config" if archivo.exists() else archivo / "config"]
    deny = []
    for c in dict.fromkeys(cfg):
        deny += [f"Read({_regla(c)}/**)", f"Read({_regla(c)})"]
    deny += ["Read(~/financial_archive/config/**)", f"Read({_regla(repo / 'data')}/**)",
             f"Read({_regla(repo / '.env')})", f"Read({_regla(repo / '.git')}/**)", "Read(**/.env)", "Read(**/*.env)",
             "Read(**/alpaca.env)"]
    if rol != "supervisor":
        deny.append(f"Read({_regla(repo / 'research' / 'paper')}/**)")
    if rol in GESTORES:
        for otro in GESTORES:
            if otro != rol:
                deny.append(f"Read({_regla(repo / 'obsidian' / 'Carteras' / otro)}/**)")
    deny += list(NEGADAS)
    allow = [f"Read({_regla(d)}/**)" for d in [trabajo.resolve(), *dirs]]
    return {"permissions": {"allow": allow, "deny": deny, "defaultMode": "dontAsk"},
            "disableAllHooks": True, "enableAllProjectMcpServers": False}


def entorno() -> dict:
    """Entorno mínimo (como scripts/c1_gestor.sh): sin ALPACA_*/APCA_* ni nada más del proceso padre."""
    e = {"HOME": os.path.expanduser("~"), "USER": os.environ.get("USER", ""),
         "LOGNAME": os.environ.get("LOGNAME", os.environ.get("USER", "")), "LANG": os.environ.get("LANG", "es_ES.UTF-8"),
         "TMPDIR": os.environ.get("TMPDIR", "/tmp"), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
    return {k: v for k, v in e.items() if not k.startswith(("ALPACA", "APCA"))}


def comando(sistema: str, dirs: list[Path], ruta_ajustes: Path) -> list[str]:
    return [binario(), "-p", "--model", modelo(), "--output-format", "json", "--no-session-persistence",
            "--restricted", "--strict-mcp-config", "--disable-slash-commands",
            # sin --allowedTools: «Read» a secas permitiría leer en cualquier sitio; lo permitido va en los ajustes,
            # acotado a las carpetas enumeradas
            "--tools", ",".join(HERRAMIENTAS), "--disallowedTools", *NEGADAS,
            "--permission-mode", "dontAsk", "--settings", str(ruta_ajustes),
            "--add-dir", *[str(d) for d in dirs],
            "--system-prompt", sistema]


def sistema(mandato: Path, conocimiento: Path | None = CONOCIMIENTO) -> str:
    """System prompt = mandato + documento de conocimiento (ambos versionados; su sha256 va en el registro)."""
    s = Path(mandato).read_text(encoding="utf-8")
    if conocimiento is not None and Path(conocimiento).exists():
        s += "\n\n---\n\n# DOCUMENTO DE CONOCIMIENTO (config/gestor_conocimiento_v1.md)\n\n" + \
            Path(conocimiento).read_text(encoding="utf-8")
    return s


def interpreta(so: str, rc: int, se: str) -> dict:
    """Salida de `claude -p --output-format json` → {ok, texto, modelo, coste_usd, duracion_claude_s, error, …}."""
    out: dict = {"ok": False, "texto": None, "modelo": [], "coste_usd": None, "error": None, "cupo_agotado": False,
                 "sha256_salida": hashlib.sha256((so or "").encode()).hexdigest(), "turnos": None}
    env = None
    try:
        env = json.loads(so) if so and so.strip() else None
    except json.JSONDecodeError:
        env = None
    if isinstance(env, dict):
        out["modelo"] = sorted((env.get("modelUsage") or {}).keys()) or ([env["model"]] if env.get("model") else [])
        out["coste_usd"] = env.get("total_cost_usd")
        out["turnos"] = env.get("num_turns")
        if env.get("duration_ms"):
            out["duracion_claude_s"] = round(env["duration_ms"] / 1000, 1)
    if rc != 0 or not isinstance(env, dict) or env.get("is_error") or env.get("subtype") not in (None, "success"):
        detalle = (str(env.get("result")) if isinstance(env, dict) else (se or so or "")).strip()[-300:]
        if rc != 0:
            out["error"] = f"claude salió con código {rc}: {detalle or (se or '').strip()[-300:]}"
        elif not isinstance(env, dict):
            out["error"] = "la salida de claude -p --output-format json no es JSON"
        else:
            out["error"] = f"claude devolvió error ({env.get('subtype')}): {detalle}"
        out["cupo_agotado"] = bool(RE_CUPO.search(f"{detalle} {se or ''}"))
        if out["cupo_agotado"]:
            out["error"] = "cupo de la suscripción agotado: no opera hoy · " + out["error"]
        return out
    out.update(ok=True, texto=env.get("result"))
    return out


def ejecutar(rol: str, trabajo: Path, *, sistema_txt: str, prompt_txt: str, plazo: float = PLAZO_S,
             copias: dict[str, Path] | None = None) -> dict:
    """Lanza el agente en `trabajo` (fuera del repo). `copias`: {nombre: ruta} que se copian a `trabajo` (su propio
    registro). Devuelve el dict de `interpreta` + duracion_s, dirs y la ruta de los ajustes."""
    trabajo.mkdir(parents=True, exist_ok=True)
    for nombre, ruta in (copias or {}).items():
        dst = trabajo / nombre
        dst.write_bytes(Path(ruta).read_bytes() if Path(ruta).exists() else b"")
    dirs = directorios(rol)
    aj = ajustes(rol, dirs, trabajo)
    (trabajo / "ajustes.json").write_text(json.dumps(aj, ensure_ascii=False, indent=1), encoding="utf-8")
    (trabajo / "prompt.txt").write_text(prompt_txt, encoding="utf-8")
    (trabajo / "directorios.txt").write_text("\n".join(map(str, dirs)) + "\n", encoding="utf-8")
    cmd = comando(sistema_txt, dirs, trabajo / "ajustes.json")
    t0 = time.monotonic()
    base = {"duracion_s": None, "directorios": [str(d) for d in dirs]}
    with open(trabajo / "prompt.txt", encoding="utf-8") as fin:
        p = subprocess.Popen(cmd, stdin=fin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             cwd=str(trabajo), env=entorno(), start_new_session=True)
        try:
            so, se = p.communicate(timeout=plazo)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.communicate()
            return {"ok": False, "texto": None, "modelo": [], "coste_usd": None, "cupo_agotado": False,
                    "error": f"el agente tardó más de {plazo:.0f} s: no opera", "sha256_salida": None, **base,
                    "duracion_s": round(time.monotonic() - t0, 1)}
    (trabajo / "salida_claude.json").write_text(so or "", encoding="utf-8")
    if se:
        (trabajo / "stderr.txt").write_text(se, encoding="utf-8")
    out = interpreta(so, p.returncode, se)
    out.update(base, duracion_s=round(time.monotonic() - t0, 1))
    return out


# --------------------------------------------------------------------------- diario en Obsidian (lo escribe Python)
def ruta_diario(cartera: str, fecha: str, repo: Path | None = None) -> Path:
    return (repo or REPO) / "obsidian" / "Carteras" / cartera / f"{fecha}.md"


def escribir_diario(ruta: Path, cabecera: dict, cuerpo: str | None, anexo: str = "") -> Path:
    """Diario del día (fuera de git: obsidian/Carteras/ está en .gitignore). Si ya existe (reintento), añade."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fm = "---\n" + "".join(f"{k}: {json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v}\n"
                           for k, v in cabecera.items()) + "---\n\n"
    texto = (cuerpo or "_(el agente no devolvió diario)_").strip() + "\n" + (("\n" + anexo.strip() + "\n") if anexo else "")
    if ruta.exists():
        with open(ruta, "a", encoding="utf-8") as fh:
            fh.write("\n\n---\n\n" + fm + texto)
    else:
        ruta.write_text(fm + texto, encoding="utf-8")
    return ruta
