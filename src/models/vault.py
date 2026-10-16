"""Caja fuerte de la etiqueta oficial: periodo bloqueado 2005-01 → INTOCABLE (docs/models/harness.md §4).

- Modo `development` (el único que usa el arnés salvo la evaluación única): la etiqueta oficial v1.1 se lee con un
  filtro de pyarrow `date < holdout_start`, de modo que las filas ≥ 2005-01 **nunca se decodifican**. Cualquier
  petición de meses ≥ 2005-01 lanza `HoldoutLocked` (y queda en el registro de accesos).
- Modo `holdout_evaluation`: solo para la evaluación única preregistrada. Exige (1) un `prereg_id` que exista en
  `research/hypotheses.yaml` con estado "preregistrada", (2) la variable de entorno `FKB_HOLDOUT_UNLOCK` igual a
  `EVALUACION-UNICA <prereg_id>`, (3) el árbol de git limpio (código evaluado = código commiteado) y (4) que ese
  preregistro no se haya evaluado antes (`holdout_evaluations.jsonl`). El consumo se anota ANTES de leer.
- Registro de accesos: cada intento (concedido o denegado) añade una línea a `<trials>/label_access.jsonl`.

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
from pathlib import Path

import pandas as pd
import yaml

from src.labels import regime_us as R

REPO = Path(__file__).resolve().parents[2]
HOLDOUT_START = pd.Timestamp(R.PARAMS.holdout_start)
UNLOCK_ENV = "FKB_HOLDOUT_UNLOCK"
# Etiqueta oficial v1.1: SHA-256 del fichero y hash de contenido (R.content_hash) de las filas con date < 2005-01.
LABEL_FILE_SHA256 = {"1.1": "7ffa68ce2f1c7b9577425daa5daf20b1089f39ed2a83814410426b6b4f89ac52"}
LABEL_DEV_CONTENT_SHA256 = {"1.1": "a0997d08a5a0dfacf2c5d6d08839909d32695ae6ee38b3306411fe6ac1dafc64"}


class HoldoutLocked(PermissionError):
    """Acceso al periodo bloqueado sin la evaluación única preregistrada."""


def trials_dir() -> Path:
    """Directorio del registro de pruebas (los tests lo redirigen con FKB_TRIALS_DIR)."""
    return Path(os.environ.get("FKB_TRIALS_DIR", REPO / "research" / "trials"))


def _git(*args) -> str:
    try:
        return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def log_access(event: dict) -> None:
    d = trials_dir()
    d.mkdir(parents=True, exist_ok=True)
    caller = next((f"{Path(f.filename).name}:{f.lineno}" for f in inspect.stack()[2:]
                   if "vault.py" not in f.filename), "?")
    rec = {"ts": dt.datetime.now().isoformat(timespec="seconds"), "git_head": _git("rev-parse", "HEAD"),
           "caller": caller, **event}
    with open(d / "label_access.jsonl", "a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def _preregistered(prereg_id: str) -> bool:
    hyp = yaml.safe_load((REPO / "research" / "hypotheses.yaml").read_text()) or []
    return any(h.get("id") == prereg_id and str(h.get("estado", "")).startswith("preregistrada") for h in hyp)


class LabelVault:
    """Única puerta de acceso del arnés a la etiqueta OFICIAL (solo para puntuar)."""

    def __init__(self, mode: str = "development", prereg_id: str | None = None, path: Path | None = None,
                 version: str = R.PARAMS.version):
        self.mode, self.prereg_id, self.version = mode, prereg_id, version
        self.path = Path(path) if path is not None else R.out_path()
        self.official = self.path.resolve() == R.out_path().resolve()
        if mode == "development":
            self.limit = HOLDOUT_START
        elif mode == "holdout_evaluation":
            self._unlock()
            self.limit = None
        else:
            raise ValueError(f"modo de la caja fuerte desconocido: {mode}")
        self._df: pd.DataFrame | None = None

    def _deny(self, why: str):
        log_access({"mode": self.mode, "prereg_id": self.prereg_id, "granted": False, "why": why,
                    "path": str(self.path)})
        raise HoldoutLocked(why)

    def _unlock(self) -> None:
        pid = self.prereg_id
        if not pid or not _preregistered(pid):
            self._deny(f"evaluación única sin preregistro válido en research/hypotheses.yaml: {pid!r}")
        if os.environ.get(UNLOCK_ENV) != f"EVALUACION-UNICA {pid}":
            self._deny(f"falta {UNLOCK_ENV}='EVALUACION-UNICA {pid}' (confirmación explícita del usuario)")
        if self.official and _git("status", "--porcelain"):
            self._deny("árbol de git sucio: la evaluación única exige el código commiteado")
        used = trials_dir() / "holdout_evaluations.jsonl"
        if used.exists() and any(json.loads(x).get("prereg_id") == pid for x in used.read_text().splitlines() if x):
            self._deny(f"el preregistro {pid} ya se evaluó en el periodo bloqueado (evaluación ÚNICA)")
        used.parent.mkdir(parents=True, exist_ok=True)
        with open(used, "a") as fh:     # se consume ANTES de leer nada
            fh.write(json.dumps({"ts": dt.datetime.now().isoformat(timespec="seconds"), "prereg_id": pid,
                                 "git_head": _git("rev-parse", "HEAD"), "path": str(self.path)}) + "\n")

    def load(self, end=None) -> pd.DataFrame:
        """Etiqueta oficial hasta `end` (incluido). En desarrollo, `end` ≥ 2005-01 se deniega."""
        end = pd.Timestamp(end) if end is not None else None
        if self.limit is not None and end is not None and end >= self.limit:
            self._deny(f"etiqueta pedida hasta {end:%Y-%m}: periodo bloqueado (≥ {self.limit:%Y-%m})")
        if self._df is None:
            if self.official:
                sha = hashlib.sha256(self.path.read_bytes()).hexdigest()
                if sha != LABEL_FILE_SHA256[self.version]:
                    raise RuntimeError(f"{self.path.name} no coincide con el SHA-256 registrado (etiqueta congelada)")
            filters = [("date", "<", self.limit.to_datetime64())] if self.limit is not None else None
            df = pd.read_parquet(self.path, filters=filters)
            if self.limit is not None:
                assert df["date"].max() < self.limit, "el filtro de lectura no se aplicó"
                if self.official and R.content_hash(df) != LABEL_DEV_CONTENT_SHA256[self.version]:
                    raise RuntimeError("las filas < 2005-01 de la etiqueta oficial no coinciden con su hash")
            self._df = df.set_index("date")
            log_access({"mode": self.mode, "prereg_id": self.prereg_id, "granted": True, "path": str(self.path),
                        "rows": len(df), "hasta": f"{df['date'].max():%Y-%m}"})
        df = self._df
        return df if end is None else df[df.index <= end]
