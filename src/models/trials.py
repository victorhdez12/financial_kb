"""Registro automático de pruebas del arnés (docs/models/harness.md §7).

Cada corrida añade:
- una línea a `<trials>/harness_runs.jsonl` (config, hash del código, hashes de datos, hash de resultados, métricas,
  `kind` = pit | placebo | synthetic, fase);
- una fila a la tabla de `research/trial_log.md` (resumen legible);
- sus predicciones, puntuaciones e informe en `<runs>/<run_id>/` (fuera de git: `FIN_DATA_ROOT/models/runs`).

`<trials>` = research/trials (FKB_TRIALS_DIR en los tests); el trial log = research/trial_log.md (FKB_TRIAL_LOG).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path

from src.models import pit_labels
from src.models.vault import REPO, _git, trials_dir
from src.warehouse import db


def runs_dir() -> Path:
    return Path(os.environ.get("FKB_RUNS_DIR", db.DATA_ROOT / "models" / "runs"))


def trial_log_path() -> Path:
    return Path(os.environ.get("FKB_TRIAL_LOG", REPO / "research" / "trial_log.md"))


def code_sha() -> dict:
    files = sorted((REPO / "src" / "models").glob("*.py"))
    h = hashlib.sha256()
    for f in files:
        h.update(f.read_bytes())
    return {"src_models": h.hexdigest(), "pit_labels_deps": pit_labels.code_sha(),
            "git_head": _git("rev-parse", "HEAD"),
            "git_dirty": bool(_git("status", "--porcelain", "--", "src", "config"))}


def _fmt(x: float, pct: bool = False) -> str:
    return (f"{100 * x:.2f} %" if pct else f"{x:.4f}").replace(".", ",")


def record(res: dict) -> dict:
    cfg, rep = res["config"], res["report"]
    now = dt.datetime.now()
    run_id = f"{now:%Y%m%d-%H%M%S}_{cfg['name']}_{res['results_sha256'][:8]}"
    d = runs_dir() / run_id
    d.mkdir(parents=True, exist_ok=True)
    res["preds"].to_parquet(d / "predictions.parquet", index=False)
    res["scores"].to_parquet(d / "scores.parquet", index=False)
    (d / "report.json").write_text(json.dumps({"config": cfg, "report": rep, "diag": res["diag"]}, indent=1,
                                              ensure_ascii=False, default=str))
    entry = {"run_id": run_id, "ts": now.isoformat(timespec="seconds"), "who": cfg["who"], "phase": cfg["phase"],
             "kind": res["kind"], "config": cfg, "code": code_sha(), "data": res["data_hashes"],
             "results_sha256": res["results_sha256"], "muestra": rep["muestra"], "modelos": rep["modelos"],
             "frente_al_baseline": {k: {"mejora_logloss": v["mejora_logloss"], "bss": v["bss"]}
                                    for k, v in rep["frente_al_baseline"].items()},
             "persistencia_muestra_completa": rep.get("persistencia_muestra_completa"),
             "artefactos": str(d)}
    td = trials_dir()
    td.mkdir(parents=True, exist_ok=True)
    with open(td / "harness_runs.jsonl", "a") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    mods = "; ".join(f"{k} {_fmt(v['acierto'], True)} / {_fmt(v['logloss'])}" for k, v in rep["modelos"].items())
    row = (f"| {now:%Y-%m-%d} | {cfg['who']} (arnés, automático) | Corrida `{run_id}` ({', '.join(res['kind'])}, "
           f"fase {cfg['phase']}): {', '.join(cfg['models'])}; modos {', '.join(cfg['modes'])}; acierto / log-loss "
           f"blanda: {mods} | {rep['muestra']['desde']} → {rep['muestra']['hasta']} ({rep['muestra']['n']} meses "
           f"comunes) | refit {cfg['refit_every']} m, embargo {cfg['embargo_months']} m, política "
           f"{cfg['feature_policy']} | Registro automático; detalle en `research/trials/harness_runs.jsonl`. "
           f"{cfg.get('nota') or ''} |\n")
    tl = trial_log_path()
    with open(tl, "a") as fh:
        fh.write(row)
    return entry
