"""Caja fuerte de la etiqueta oficial: periodo bloqueado 2005-01 → INTOCABLE (docs/models/harness.md §4).

Es una barrera **anti-accidente, no anti-intención**: Python no tiene atributos privados y los ficheros completos
(etiqueta, matrices, baselines) siguen en disco sin cifrar (harness.md §4, "vías restantes").

- Modo `development` (todo salvo la evaluación única): la etiqueta oficial v1.1 se lee con un filtro de pyarrow
  `date < holdout_start`, de modo que las filas ≥ 2005-01 **nunca se decodifican**. `limit` es de solo lectura.
  Cualquier petición de meses ≥ 2005-01 lanza `HoldoutLocked` (y queda en el registro de accesos).
- Modo `holdout_evaluation`: SOLO a través de `src.models.harness.evaluate_holdout(prereg_id)`. Antes de leer nada
  exige, en este orden (`_unlock`):
    1. un identificador de evaluación explícito: prefijo `P-EVAL-`, `tipo: evaluacion_holdout`, estado
       "preregistrada…" en `research/hypotheses.yaml` (no vale cualquier hipótesis preregistrada);
    2. `FKB_HOLDOUT_UNLOCK = "EVALUACION-UNICA <prereg_id>"` (confirmación explícita del usuario);
    3. git disponible, `REPO` = raíz del repositorio y árbol limpio (incluidos los no rastreados). Git **falla
       cerrado**: cualquier error de git = no hay evaluación;
    4. el registro de consumo `research/holdout/evaluations.jsonl` (ruta FIJA relativa al código; ninguna variable
       de entorno la cambia) rastreado por git, sin cambios respecto a HEAD y sin ninguna línea borrada respecto a su
       historial de git (un id consumido no puede desaparecer);
    5. que ni el id ni ninguno de los que incluye (`incluye:`) se hayan consumido antes (también como parte de otro);
    6. una sola apertura por proceso.
  El consumo se ANOTA y se COMMITEA (solo ese fichero) ANTES de leer: un fallo posterior también gasta la evaluación,
  y si el commit falla la caja no se abre (la línea queda escrita: el id queda gastado igualmente).
- Solo las cajas creadas aquí y desbloqueadas por `_unlock` están en `_ISSUED`; `PITData` y `PITLabeler` comprueban
  identidad y tipo exacto (no duck typing). Tras la corrida, `close()` la inutiliza.
- Registro de accesos: cada intento (concedido, denegado o servido desde la caché) añade una línea a
  `research/trials/full/label_access.jsonl` (ruta fija, fuera de git) y los accesos que leen el fichero también a
  `<trials>/label_access.jsonl` (el registro versionado; los tests lo redirigen con FKB_TRIALS_DIR).

La integridad se comprueba con el SHA-256 del fichero (bytes, sin decodificar filas) y con el hash de contenido de
las filas ≤ 2004 (fijados en git, abajo).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import inspect
import json
import os
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

_OFFICIAL_LABEL = R.out_path()          # ruta de la etiqueta oficial, fijada al importar (los tests redirigen R.out_path)
_ISSUED: "weakref.WeakSet[LabelVault]" = weakref.WeakSet()   # cajas desbloqueadas por _unlock (identidad)
_PROCESS = {"opened": None}                                   # una sola apertura del bloqueado por proceso


class HoldoutLocked(PermissionError):
    """Acceso al periodo bloqueado sin la evaluación única preregistrada."""


def trials_dir() -> Path:
    """Directorio del registro de pruebas versionado (los tests lo redirigen con FKB_TRIALS_DIR).
    NO contiene el registro de consumo del bloqueado (ruta fija: `registry_path()`)."""
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
        r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, timeout=60)
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
    if versioned:
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
    """El registro está rastreado, sin cambios y sin líneas borradas respecto a TODO su historial de git."""
    rel = REGISTRY_REL
    _git_strict("ls-files", "--error-unmatch", rel)
    cur = registry_path().read_text()
    cur_lines = set(x for x in cur.splitlines() if x.strip())
    for c in _git_strict("log", "--format=%H", "--", rel).split():
        old = _git_strict("show", f"{c}:{rel}")
        missing = [x for x in old.splitlines() if x.strip() and x not in cur_lines]
        if missing:
            raise HoldoutLocked(f"el registro de consumo perdió {len(missing)} línea(s) respecto al commit {c[:8]}: "
                                "un id consumido no puede desaparecer")
    return _read_registry_text(cur)


# ------------------------------------------------------------------ caja fuerte
class LabelVault:
    """Única puerta de acceso del arnés a la etiqueta OFICIAL (solo para puntuar)."""

    def __init__(self, mode: str = "development", prereg_id: str | None = None, path: Path | None = None,
                 version: str = R.PARAMS.version):
        self.mode, self.prereg_id, self.version = mode, prereg_id, version
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
            dirty = _git_strict("status", "--porcelain", "--untracked-files=all").strip()
            if dirty:
                raise HoldoutLocked("árbol de git sucio: la evaluación única exige todo commiteado\n" + dirty[:500])
            reg = _check_registry_history()                                         # 4
            used = consumed_ids()                                                   # 5
            inc = list(h.get("incluye") or [])
            clash = sorted(({pid, *inc}) & used)
            if clash:
                raise HoldoutLocked(f"ya evaluado en el periodo bloqueado (evaluación ÚNICA): {clash}")
            if _PROCESS["opened"] is not None:                                      # 6
                raise HoldoutLocked(f"este proceso ya abrió el bloqueado ({_PROCESS['opened']})")
        except HoldoutLocked as e:
            self._deny(str(e))
        head = _git_strict("rev-parse", "HEAD").strip()
        rec = {"n": len(reg) + 1, "ts": dt.datetime.now().isoformat(timespec="seconds"), "prereg_id": pid,
               "incluye": inc, "git_head": head, "path": str(self.path), "official": self.official}
        _PROCESS["opened"] = pid
        _append(registry_path(), rec)              # se consume ANTES de leer nada…
        try:                                       # …y se commitea (solo ese fichero) antes de abrir
            _git_strict("add", "--", REGISTRY_REL)
            _git_strict("commit", "-q", "-m", f"Holdout evaluation consumed: {pid}", "--", REGISTRY_REL)
        except HoldoutLocked as e:
            self._deny(f"consumo de {pid} anotado pero NO commiteado ({e}); el id queda gastado")
        log_access({"mode": self.mode, "prereg_id": pid, "granted": True, "event": "unlock", "n": rec["n"],
                    "path": str(self.path)})
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
