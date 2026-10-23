"""Caja fuerte de la etiqueta oficial: periodo bloqueado 2005-01 → INTOCABLE (docs/models/harness.md §4).

Es una barrera **anti-accidente, no anti-intención**: Python no tiene atributos privados y los ficheros completos
(etiqueta, matrices, baselines) siguen en disco sin cifrar (harness.md §4, "vías restantes").

- Modo `development` (todo salvo la evaluación única): la etiqueta oficial v1.1 se lee con un filtro de pyarrow
  `date < holdout_start`, de modo que las filas ≥ 2005-01 **nunca se decodifican**. `limit` es de solo lectura.
  Cualquier petición de meses ≥ 2005-01 lanza `HoldoutLocked` (y queda en el registro de accesos).
- Modo `holdout_evaluation`: SOLO a través de `src.models.harness.evaluate_holdout(prereg_id)` (que antes exige el
  ENSAYO EN SECO del preregistro, harness.md §4e). Antes de leer nada exige, en este orden (`_unlock`):
    1. un identificador de evaluación explícito: prefijo `P-EVAL-`, `tipo: evaluacion_holdout`, estado
       "preregistrada…" en `research/hypotheses.yaml` (no vale cualquier hipótesis preregistrada);
    2. `FKB_HOLDOUT_UNLOCK = "EVALUACION-UNICA <prereg_id>"` (confirmación explícita del usuario);
    3. git disponible, `REPO` = raíz del repositorio, una RAMA (no HEAD suelto) y árbol limpio: incluidos los no
       rastreados y los IGNORADOS relevantes (en src/, config/, tests/, research/; salvo `__pycache__`/`*.pyc`, el
       registros `research/trials/` (salidas del arnés, no entradas) y las salidas `research/holdout/runs/`; N6). Git **falla cerrado**;
    4b. PROTECCIÓN DE RAMA (Validador A3-1): la rama de evaluación de `origin` en GitHub prohíbe push forzado y borrado
       e incluye a los administradores (`check_branch_protection`, vía `gh api`); si no se puede comprobar, aborta;
    4. ANCLA EXTERNA (decisión del usuario 16-oct): remoto `origin` configurado con URL de GitHub; con el CERROJO
       exclusivo ya tomado (fcntl en `<git-dir>/fkb-holdout.lock`; un segundo proceso falla, N8): `git fetch origin`,
       la rama local contiene `origin/<rama>`, y se empuja HEAD (el preregistro queda en el remoto antes de gastar);
    5. el registro de consumo `research/holdout/evaluations.jsonl` (ruta FIJA relativa al código; ninguna variable
       de entorno la cambia) rastreado por git, sin cambios, y sin perder ninguna línea vista en CUALQUIER versión del
       fichero en TODAS las refs (ramas, etiquetas, remotas tras el fetch) y en el REFLOG (N2/N2b): un consumo visto
       en cualquier sitio cuenta como gastado;
    6. que ni el id ni ninguno de los que incluye (`incluye:`) se hayan consumido antes (también como parte de otro);
    7. una sola apertura por proceso; si ya hay evaluaciones, el preregistro declara `amplia:` (B2-1) y su ventana de
       evaluación no se solapa con ninguna ya evaluada (N9).
  El consumo se ANOTA, se COMMITEA (solo ese fichero), se comprueba que el registro tiene UNA línea del id, se EMPUJA a
  `origin` y se comprueba que el commit de consumo está en el remoto (`git ls-remote` y `git branch -r --contains`),
  todo ANTES de leer y con el cerrojo tomado. Si el commit, el push o la comprobación fallan, la caja no se abre y el
  id queda gastado (falla cerrado).
- Solo las cajas creadas aquí y desbloqueadas por `_unlock` están en `_ISSUED`; `PITData` y `PITLabeler` comprueban
  identidad y tipo exacto (no duck typing). Tras la corrida, `close()` la inutiliza.
- Registro de accesos: cada intento (concedido, denegado o servido desde la caché) añade una línea a
  `research/trials/full/label_access.jsonl` (ruta fija, fuera de git) y los accesos que leen el fichero también a
  `<trials>/label_access.jsonl` (el registro versionado; los tests lo redirigen con FKB_TRIALS_DIR).

La integridad se comprueba con el SHA-256 del fichero (bytes, sin decodificar filas) y con el hash de contenido de
las filas ≤ 2004 (fijados en git, abajo).
"""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import inspect
import json
import os
import re
import subprocess
import weakref
from pathlib import Path

import pandas as pd
import yaml

from src.labels import regime_us as R

REPO = Path(__file__).resolve().parents[2]
HOLDOUT_START = pd.Timestamp(R.PARAMS.holdout_start)
UNLOCK_ENV = "FKB_HOLDOUT_UNLOCK"
EVAL_PREFIX = "P-EVAL-"
EVAL_TIPO = "evaluacion_holdout"
REGISTRY_REL = "research/holdout/evaluations.jsonl"      # registro de consumo: ruta fija, versionada en git
FULL_LOG_REL = "research/trials/full"                     # registro completo de accesos (fuera de git)
# Etiqueta oficial v1.1: SHA-256 del fichero y hash de contenido (R.content_hash) de las filas con date < 2005-01.
LABEL_FILE_SHA256 = {"1.1": "7ffa68ce2f1c7b9577425daa5daf20b1089f39ed2a83814410426b6b4f89ac52"}
LABEL_DEV_CONTENT_SHA256 = {"1.1": "a0997d08a5a0dfacf2c5d6d08839909d32695ae6ee38b3306411fe6ac1dafc64"}

REMOTE_NAME = "origin"                                    # ancla externa: nombre FIJO
# URL de GitHub (https o ssh). Los tests la relajan por inyección explícita (monkeypatch de este objeto), nunca por
# variable de entorno.
REMOTE_URL_RE = re.compile(r"^(https://github\.com/|git@github\.com:|ssh://git@github\.com/)[\w.-]+/[\w.-]+?(\.git)?/?$")
LOCK_NAME = "fkb-holdout.lock"                            # cerrojo, dentro del directorio .git (no ensucia el árbol)
RELEVANT_IGNORED = ("src", "config", "tests", "research")  # N6: ficheros ignorados que cuentan como sucio…
IGNORED_OK = ("research/trials/", "research/holdout/runs/")   # …salvo registros/salidas (y __pycache__, *.pyc)

_OFFICIAL_LABEL = R.out_path()          # ruta de la etiqueta oficial, fijada al importar (los tests redirigen R.out_path)
_ISSUED: "weakref.WeakSet[LabelVault]" = weakref.WeakSet()   # cajas desbloqueadas por _unlock (identidad)
_PROCESS = {"opened": None}                                   # una sola apertura del bloqueado por proceso
_QUIET = {"on": False}       # ensayo previo dentro de evaluate_holdout: sin tocar el registro versionado (árbol limpio)
_FIXED = {"on": False}       # N7: durante la evaluación única, registros y salidas en rutas FIJAS (sin FKB_*_DIR)


class HoldoutLocked(PermissionError):
    """Acceso al periodo bloqueado sin la evaluación única preregistrada."""


def trials_dir() -> Path:
    """Directorio del registro de pruebas versionado (los tests lo redirigen con FKB_TRIALS_DIR).
    NO contiene el registro de consumo del bloqueado (ruta fija: `registry_path()`)."""
    if _FIXED["on"]:
        return REPO / "research" / "trials"
    return Path(os.environ.get("FKB_TRIALS_DIR", REPO / "research" / "trials"))


def registry_path() -> Path:
    return REPO / REGISTRY_REL


def full_log_dir() -> Path:
    return REPO / FULL_LOG_REL


def _git(*args) -> str:
    """git tolerante (solo para anotar el commit en los registros; NUNCA para decidir una apertura)."""
    try:
        return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _git_strict(*args) -> str:
    """git que FALLA CERRADO: sin git, fuera de un repo o con cualquier error → HoldoutLocked."""
    try:
        r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, timeout=120,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except Exception as e:  # noqa: BLE001
        raise HoldoutLocked(f"git no disponible ({e!r}): sin git no hay evaluación única") from e
    if r.returncode != 0:
        raise HoldoutLocked(f"git {' '.join(args)} falló ({r.returncode}): {r.stderr.strip()[:200]}")
    return r.stdout


def _caller() -> str:
    return next((f"{Path(f.filename).name}:{f.lineno}" for f in inspect.stack()[2:]
                 if not f.filename.endswith(("vault.py", "pit_labels.py"))), "?")


def _append(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def log_access(event: dict, versioned: bool = True) -> None:
    """Registro de accesos. Siempre en la ruta fija completa; `versioned` además en `<trials>/label_access.jsonl`."""
    rec = {"ts": dt.datetime.now().isoformat(timespec="seconds"), "git_head": _git("rev-parse", "HEAD"),
           "caller": _caller(), "pid": os.getpid(), "pytest": os.environ.get("PYTEST_CURRENT_TEST"),
           "trials_dir": str(trials_dir()), **event}
    _append(full_log_dir() / "label_access.jsonl", rec)
    if versioned and not _QUIET["on"]:
        _append(trials_dir() / "label_access.jsonl", rec)


def log_unrecorded_run(entry: dict) -> None:
    """Línea mínima de una corrida con `record=False` (B-3): ruta fija, fuera de git."""
    _append(full_log_dir() / "harness_runs_unrecorded.jsonl",
            {"ts": dt.datetime.now().isoformat(timespec="seconds"), "git_head": _git("rev-parse", "HEAD"),
             "caller": _caller(), "pytest": os.environ.get("PYTEST_CURRENT_TEST"), **entry})


# ------------------------------------------------------------------ preregistros de evaluación
def _hypotheses() -> list[dict]:
    return yaml.safe_load((REPO / "research" / "hypotheses.yaml").read_text()) or []


def eval_entry(prereg_id: str | None) -> dict:
    """Entrada de `research/hypotheses.yaml` que puede abrir el bloqueado, o HoldoutLocked (D9)."""
    if not prereg_id or not str(prereg_id).startswith(EVAL_PREFIX):
        raise HoldoutLocked(f"{prereg_id!r} no es un identificador de evaluación ({EVAL_PREFIX}…)")
    h = next((h for h in _hypotheses() if h.get("id") == prereg_id), None)
    if h is None:
        raise HoldoutLocked(f"{prereg_id} no está en research/hypotheses.yaml")
    if h.get("tipo") != EVAL_TIPO:
        raise HoldoutLocked(f"{prereg_id}: tipo {h.get('tipo')!r} ≠ {EVAL_TIPO!r} (solo una evaluación explícita "
                            "abre el periodo bloqueado)")
    if not str(h.get("estado", "")).startswith("preregistrada"):
        raise HoldoutLocked(f"{prereg_id}: estado {h.get('estado')!r} (no preregistrada)")
    return h


def _read_registry_text(text: str) -> list[dict]:
    return [json.loads(x) for x in text.splitlines() if x.strip()]


def consumed_ids() -> set[str]:
    """Ids gastados según el registro fijo (incluidos los que cubría cada evaluación)."""
    p = registry_path()
    out: set[str] = set()
    if p.exists():
        for r in _read_registry_text(p.read_text()):
            out.add(r["prereg_id"])
            out.update(r.get("incluye") or [])
    return out


def _check_registry_history() -> list[dict]:
    """El registro está rastreado y no ha perdido ninguna línea vista en CUALQUIER versión del fichero alcanzable desde
    TODAS las refs (ramas, etiquetas, refs remotas tras el fetch, stash) o desde el REFLOG (M2-1: un `reset --hard`, una
    rama creada antes del consumo o un push forzado no lo esconden). Un commit en el que el fichero no existe (borrado)
    también falla cerrado."""
    rel = REGISTRY_REL
    _git_strict("ls-files", "--error-unmatch", rel)
    cur = registry_path().read_text()
    cur_lines = set(x for x in cur.splitlines() if x.strip())
    commits = set(_git_strict("rev-list", "--all", "--reflog", "--", rel).split())
    commits |= set(_git_strict("log", "--format=%H", "--", rel).split())
    for c in sorted(commits):
        old = _git_strict("show", f"{c}:{rel}")
        missing = [x for x in old.splitlines() if x.strip() and x not in cur_lines]
        if missing:
            raise HoldoutLocked(f"el registro de consumo perdió {len(missing)} línea(s) respecto al commit {c[:8]} "
                                "(alguna ref, el remoto o el reflog lo conservan): un id consumido no puede desaparecer")
    return _read_registry_text(cur)


def _ignored_relevant() -> list[str]:
    """N6: ficheros IGNORADOS por git en src/, config/, tests/ y research/ que pueden cambiar lo que se ejecuta o se lee
    (salvo `__pycache__`/`*.pyc`, que genera Python, y las rutas de IGNORED_OK). `.env` (raíz) NO cuenta: guarda las
    credenciales de las fuentes; durante la evaluación las rutas de registro son fijas (N7) y los datos se comprueban
    por SHA-256, así que nada de `.env` puede redirigir la evaluación."""
    out = _git_strict("ls-files", "--others", "--ignored", "--exclude-standard", "--", *RELEVANT_IGNORED)
    return [p for p in out.splitlines() if p.strip() and not p.startswith(IGNORED_OK)
            and "__pycache__/" not in p and not p.endswith(".pyc")]


def _branch() -> str:
    try:
        return _git_strict("symbolic-ref", "--short", "-q", "HEAD").strip()
    except HoldoutLocked as e:
        raise HoldoutLocked("HEAD suelto: la evaluación única se hace desde una rama (la que se empuja al remoto)") from e


def check_remote() -> str:
    """Ancla externa: remoto `origin` configurado y con URL de GitHub. Devuelve la URL."""
    try:
        url = _git_strict("remote", "get-url", REMOTE_NAME).strip()
    except HoldoutLocked as e:
        raise HoldoutLocked(f"sin remoto '{REMOTE_NAME}': la evaluación única exige un ancla externa (repositorio "
                            "privado en GitHub; docs/models/harness.md §4b)") from e
    if not REMOTE_URL_RE.match(url):
        raise HoldoutLocked(f"el remoto '{REMOTE_NAME}' ({url}) no es una URL de GitHub")
    return url


# ------------------------------------------------------------------ protección de rama en GitHub (Validador A3-1)
# La unicidad de la evaluación solo cae si se REESCRIBE el remoto (push forzado o borrado de la rama; Validador v2.1
# T3/T4). Lo impide la protección de rama de GitHub; el código la COMPRUEBA antes de abrir la caja (y en el ensayo en
# seco registrado, paso previo a registrar un P-EVAL-…): si falta, no es la esperada o no se puede consultar → aborta.
GITHUB_SLUG_RE = re.compile(r"github\.com[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$")
PROTECTION_REQUIRED = {"allow_force_pushes": False, "allow_deletions": False, "enforce_admins": True}


def github_slug(url: str) -> tuple[str, str]:
    """(propietario, repositorio) de una URL de GitHub (https o ssh); si no lo es → HoldoutLocked."""
    m = GITHUB_SLUG_RE.search(url.strip())
    if not m:
        raise HoldoutLocked(f"no se puede leer propietario/repositorio de GitHub en {url!r}")
    return m.group(1), m.group(2)


def _gh_api(path: str) -> dict:
    """`gh api <path>` (JSON). Falla CERRADO: sin `gh`, sin sesión, 404/403 o salida no JSON → HoldoutLocked."""
    try:
        r = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=60,
                           env={**os.environ, "GH_PROMPT_DISABLED": "1"})
    except Exception as e:  # noqa: BLE001
        raise HoldoutLocked(f"gh no disponible ({e!r}): no se puede comprobar la protección de rama") from e
    if r.returncode != 0:
        raise HoldoutLocked(f"gh api {path} falló ({r.returncode}): {(r.stderr or r.stdout).strip()[:200]}")
    try:
        out = json.loads(r.stdout)
    except ValueError as e:
        raise HoldoutLocked(f"gh api {path}: respuesta no JSON") from e
    if not isinstance(out, dict):
        raise HoldoutLocked(f"gh api {path}: respuesta inesperada")
    return out


def protection_problems(prot: dict) -> list[str]:
    """Qué falta en la respuesta de `branches/<rama>/protection` frente a PROTECTION_REQUIRED (vacío = cumple). Una
    clave ausente o mal formada cuenta como incumplida."""
    out = []
    for key, want in PROTECTION_REQUIRED.items():
        v = prot.get(key)
        got = v.get("enabled") if isinstance(v, dict) else None
        if got is not want:
            out.append(f"{key}.enabled = {got!r} (se exige {want})")
    return out


def check_branch_protection(branch: str | None = None) -> dict:
    """Comprueba en GitHub que la rama de evaluación de `origin` está protegida con allow_force_pushes = false,
    allow_deletions = false y enforce_admins = true (`gh api repos/<o>/<r>/branches/<rama>/protection`). Si no se puede
    consultar o no cumple → HoldoutLocked (no se abre ni se gasta nada)."""
    branch = branch or _branch()
    url = check_remote()
    owner, repo = github_slug(url)
    path = f"repos/{owner}/{repo}/branches/{branch}/protection"
    prot = _gh_api(path)
    probs = protection_problems(prot)
    if probs:
        raise HoldoutLocked(f"la rama {branch} de {owner}/{repo} no tiene la protección exigida (A3-1): "
                            + "; ".join(probs))
    return {"repo": f"{owner}/{repo}", "rama": branch, "ok": True,
            **{k: prot[k]["enabled"] for k in PROTECTION_REQUIRED}}


def _remote_head(branch: str) -> str:
    out = _git_strict("ls-remote", REMOTE_NAME, f"refs/heads/{branch}").split()
    return out[0] if out else ""


def _push_and_verify(branch: str, sha: str) -> None:
    """Empuja `sha` a origin/<rama> y comprueba que el remoto lo tiene (ls-remote + fetch + branch -r --contains)."""
    _git_strict("push", "-q", REMOTE_NAME, f"{sha}:refs/heads/{branch}")
    if _remote_head(branch) != sha:
        raise HoldoutLocked(f"el remoto no tiene {sha[:8]} en refs/heads/{branch} tras el push")
    _git_strict("fetch", "-q", REMOTE_NAME)
    rb = [x.strip() for x in _git_strict("branch", "-r", "--contains", sha).splitlines()]
    if f"{REMOTE_NAME}/{branch}" not in rb:
        raise HoldoutLocked(f"{REMOTE_NAME}/{branch} no contiene {sha[:8]} tras el fetch")


@contextlib.contextmanager
def holdout_lock():
    """Cerrojo EXCLUSIVO y no bloqueante (fcntl.flock) entre leer el registro y dejar el consumo anclado (M2-1, N8). Vive
    en el directorio .git (no ensucia el árbol) y lo libera el sistema si el proceso muere. Un segundo proceso falla."""
    gd = Path(_git_strict("rev-parse", "--absolute-git-dir").strip())
    fd = os.open(gd / LOCK_NAME, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        os.close(fd)
        raise HoldoutLocked(f"cerrojo ocupado ({gd / LOCK_NAME}): otra evaluación única está en curso") from e
    try:
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n".encode())
        yield gd / LOCK_NAME
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _overlap(a, b) -> bool:
    return a is not None and b is not None and pd.Timestamp(a[0]) <= pd.Timestamp(b[1]) \
        and pd.Timestamp(b[0]) <= pd.Timestamp(a[1])


# ------------------------------------------------------------------ caja fuerte
class LabelVault:
    """Única puerta de acceso del arnés a la etiqueta OFICIAL (solo para puntuar)."""

    def __init__(self, mode: str = "development", prereg_id: str | None = None, path: Path | None = None,
                 version: str = R.PARAMS.version, window: tuple | None = None):
        self.mode, self.prereg_id, self.version = mode, prereg_id, version
        self.window = None if window is None else (f"{pd.Timestamp(window[0]):%Y-%m}", f"{pd.Timestamp(window[1]):%Y-%m}")
        self.path = Path(path) if path is not None else R.out_path()
        self.official = self.path.resolve() == _OFFICIAL_LABEL.resolve()
        self.__unlocked = False
        self.__closed = False
        self._df: pd.DataFrame | None = None
        if mode == "holdout_evaluation":
            self._unlock()
        elif mode != "development":
            raise ValueError(f"modo de la caja fuerte desconocido: {mode}")

    @property
    def limit(self) -> pd.Timestamp | None:
        """Límite de lectura (solo lectura: `v.limit = None` lanza AttributeError)."""
        return None if (self.mode == "holdout_evaluation" and self.__unlocked) else HOLDOUT_START

    @property
    def unlocked(self) -> bool:
        return self.__unlocked and not self.__closed and self in _ISSUED

    def close(self) -> None:
        """Inutiliza la caja (al terminar la evaluación única): ninguna lectura más, ni desde la caché."""
        self.__closed = True
        self._df = None

    def _deny(self, why: str):
        log_access({"mode": self.mode, "prereg_id": self.prereg_id, "granted": False, "why": why,
                    "path": str(self.path)})
        raise HoldoutLocked(why)

    def _unlock(self) -> None:
        pid = self.prereg_id
        try:
            h = eval_entry(pid)                                                     # 1
            if os.environ.get(UNLOCK_ENV) != f"EVALUACION-UNICA {pid}":             # 2
                raise HoldoutLocked(f"falta {UNLOCK_ENV}='EVALUACION-UNICA {pid}' (confirmación explícita del usuario)")
            top = _git_strict("rev-parse", "--show-toplevel").strip()               # 3
            if Path(top).resolve() != REPO.resolve():
                raise HoldoutLocked(f"REPO {REPO} no es la raíz del repositorio git ({top})")
            branch = _branch()
            dirty = _git_strict("status", "--porcelain", "--untracked-files=all").strip()
            if dirty:
                raise HoldoutLocked("árbol de git sucio: la evaluación única exige todo commiteado\n" + dirty[:500])
            ign = _ignored_relevant()
            if ign:
                raise HoldoutLocked("árbol de git sucio: ficheros IGNORADOS relevantes (N6): " + ", ".join(ign[:10]))
            check_remote()                                                          # 4
            check_branch_protection(branch)                                         # 4b (A3-1): sin reescritura
        except HoldoutLocked as e:
            self._deny(str(e))
        try:
            with holdout_lock():                                                    # cerrojo: 4 … consumo anclado
                self._unlock_locked(h, pid, branch)
        except HoldoutLocked as e:
            if not self.__unlocked:
                self._deny(str(e))
            raise

    def _unlock_locked(self, h: dict, pid: str, branch: str) -> None:
        inc = list(h.get("incluye") or [])
        _git_strict("fetch", "-q", REMOTE_NAME)                                     # 4 (cont.)
        remote_ref = f"refs/remotes/{REMOTE_NAME}/{branch}"
        has_remote = bool(_git_strict("for-each-ref", "--format=%(objectname)", remote_ref).strip())
        if has_remote:
            r = subprocess.run(["git", "-C", str(REPO), "merge-base", "--is-ancestor", remote_ref, "HEAD"],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise HoldoutLocked(f"la rama local no contiene {REMOTE_NAME}/{branch}: trae el remoto antes "
                                    "(puede tener un consumo que aquí falta)")
        head = _git_strict("rev-parse", "HEAD").strip()
        _push_and_verify(branch, head)                  # el preregistro y su configuración quedan en el remoto
        reg = _check_registry_history()                                         # 5
        used = consumed_ids()                                                   # 6
        clash = sorted(({pid, *inc}) & used)
        if clash:
            raise HoldoutLocked(f"ya evaluado en el periodo bloqueado (evaluación ÚNICA): {clash}")
        if _PROCESS["opened"] is not None:                                      # 7
            raise HoldoutLocked(f"este proceso ya abrió el bloqueado ({_PROCESS['opened']})")
        if reg:
            prev = {r["prereg_id"] for r in reg}
            if h.get("amplia") not in prev:
                raise HoldoutLocked(f"ya hay evaluaciones ({sorted(prev)}): una nueva es una AMPLIACIÓN y debe declarar "
                                    "`amplia: <id de la evaluación anterior>` en su preregistro (B2-1)")
            olap = [r["prereg_id"] for r in reg if _overlap(r.get("ventana"), self.window)]
            if olap:
                raise HoldoutLocked(f"la ventana {self.window} se solapa con meses ya evaluados por {olap} (N9)")
        rec = {"n": len(reg) + 1, "ts": dt.datetime.now().isoformat(timespec="seconds"), "prereg_id": pid,
               "incluye": inc, "ventana": self.window, "amplia": h.get("amplia"), "git_head": head,
               "rama": branch, "remoto": _git_strict("remote", "get-url", REMOTE_NAME).strip(),
               "path": str(self.path), "official": self.official}
        _PROCESS["opened"] = pid
        _append(registry_path(), rec)              # se consume ANTES de leer nada…
        try:                                       # …se commitea (solo ese fichero), se ancla y se comprueba
            _git_strict("add", "--", REGISTRY_REL)
            _git_strict("commit", "-q", "-m", f"Holdout evaluation consumed: {pid}", "--", REGISTRY_REL)
            sha = _git_strict("rev-parse", "HEAD").strip()
            mine = [r for r in _read_registry_text(registry_path().read_text()) if r["prereg_id"] == pid]
            if len(mine) != 1:
                raise HoldoutLocked(f"el registro tiene {len(mine)} líneas de {pid} tras el commit (debe ser 1)")
            _push_and_verify(branch, sha)
        except HoldoutLocked as e:
            raise HoldoutLocked(f"consumo de {pid} anotado pero NO commiteado/anclado en el remoto ({e}); el id queda "
                                "gastado y la caja no se abre") from e
        log_access({"mode": self.mode, "prereg_id": pid, "granted": True, "event": "unlock", "n": rec["n"],
                    "path": str(self.path), "anclado": sha})
        self.__unlocked = True
        _ISSUED.add(self)

    def load(self, end=None) -> pd.DataFrame:
        """Etiqueta oficial hasta `end` (incluido). En desarrollo, `end` ≥ 2005-01 se deniega."""
        if self.__closed:
            self._deny("caja fuerte cerrada (la evaluación única ya se ejecutó)")
        if self.mode == "holdout_evaluation" and not self.unlocked:
            self._deny("caja fuerte de evaluación sin desbloquear")
        end = pd.Timestamp(end) if end is not None else None
        limit = self.limit
        if limit is not None and end is not None and end >= limit:
            self._deny(f"etiqueta pedida hasta {end:%Y-%m}: periodo bloqueado (≥ {limit:%Y-%m})")
        if self._df is None:
            if self.official:
                sha = hashlib.sha256(self.path.read_bytes()).hexdigest()
                if sha != LABEL_FILE_SHA256[self.version]:
                    raise RuntimeError(f"{self.path.name} no coincide con el SHA-256 registrado (etiqueta congelada)")
            filters = [("date", "<", limit.to_datetime64())] if limit is not None else None
            df = pd.read_parquet(self.path, filters=filters)
            if limit is not None:
                assert df["date"].max() < limit, "el filtro de lectura no se aplicó"
                if self.official and R.content_hash(df) != LABEL_DEV_CONTENT_SHA256[self.version]:
                    raise RuntimeError("las filas < 2005-01 de la etiqueta oficial no coinciden con su hash")
            self._df = df.set_index("date")
            log_access({"mode": self.mode, "prereg_id": self.prereg_id, "granted": True, "path": str(self.path),
                        "rows": len(df), "hasta": f"{df['date'].max():%Y-%m}"})
        else:
            log_access({"mode": self.mode, "prereg_id": self.prereg_id, "granted": True, "cache": True,
                        "end": None if end is None else f"{end:%Y-%m}"}, versioned=False)
        df = self._df
        return df if end is None else df[df.index <= end]


def is_open_holdout_vault(v, prereg_id: str | None = None) -> bool:
    """Identidad y tipo EXACTO (no duck typing): una caja desbloqueada por `_unlock`, abierta y del preregistro."""
    return (type(v) is LabelVault and v in _ISSUED and v.mode == "holdout_evaluation" and v.unlocked
            and (prereg_id is None or v.prereg_id == prereg_id))
