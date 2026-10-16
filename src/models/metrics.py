"""Métricas del arnés (docs/models/harness.md §6).

- Probabilidades: se recortan a 1e-4 y se renormalizan (mismo recorte que labels/checks.py y pit.score_training,
  para reproducir el listón de la persistencia PIT).
- log-loss BLANDA (principal): −Σ_q T_q · log P_q contra las probabilidades de la etiqueta oficial.
- Brier multiclase blando: Σ_q (P_q − T_q)²; BSS = 1 − Brier_modelo / Brier_persistencia (mismos meses, mismo modo).
- Acierto: argmax P = etiqueta dura oficial (se informa, no decide).
- Intervalos: bootstrap por bloques CIRCULAR de 12 meses, 5.000 réplicas, semilla 20261015, percentil 95 %
  (adenda P-EVAL-MOD de research/hypotheses.yaml). p-valor unilateral = proporción de réplicas con mejora ≤ 0.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

QUADS = ("expansion", "late_cycle", "stagflation", "low_growth_disinfl")
P_COLS = [f"p_{q}" for q in QUADS]
CLIP = 1e-4
BOOT = {"block": 12, "n": 5000, "seed": 20261015, "level": 0.95}


def prep(P: np.ndarray) -> np.ndarray:
    P = np.clip(np.asarray(P, float), CLIP, 1)
    return P / P.sum(axis=1, keepdims=True)


def monthly_scores(P: np.ndarray, T: np.ndarray, hard: np.ndarray) -> pd.DataFrame:
    """Pérdidas mes a mes: log-loss blanda, Brier blando y acierto."""
    P, T = prep(P), np.asarray(T, float)
    return pd.DataFrame({"logloss": -(T * np.log(P)).sum(axis=1),
                         "brier": ((P - T) ** 2).sum(axis=1),
                         "hit": (np.array(QUADS)[P.argmax(axis=1)] == np.asarray(hard)).astype(float)})


def block_indices(n: int, block: int, n_rep: int, seed: int) -> np.ndarray:
    """Índices del bootstrap por bloques circular (n_rep × n)."""
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / block))
    starts = rng.integers(0, n, size=(n_rep, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]) % n
    return idx.reshape(n_rep, -1)[:, :n]


def boot_mean(x: np.ndarray, boot: dict = BOOT) -> dict:
    """Media de una serie mensual con IC por bloques; p unilateral = P(media* ≤ 0)."""
    x = np.asarray(x, float)
    if len(x) == 0:
        return {"mean": np.nan, "lo": np.nan, "hi": np.nan, "p_le0": np.nan, "n": 0}
    idx = block_indices(len(x), boot["block"], boot["n"], boot["seed"])
    m = x[idx].mean(axis=1)
    a = (1 - boot["level"]) / 2
    return {"mean": float(x.mean()), "lo": float(np.quantile(m, a)), "hi": float(np.quantile(m, 1 - a)),
            "p_le0": float((m <= 0).mean()), "n": int(len(x))}


def boot_bss(b_model: np.ndarray, b_ref: np.ndarray, boot: dict = BOOT) -> dict:
    """BSS = 1 − ΣBrier_modelo / ΣBrier_ref, con IC por bloques (mismos índices para los dos)."""
    b_model, b_ref = np.asarray(b_model, float), np.asarray(b_ref, float)
    idx = block_indices(len(b_model), boot["block"], boot["n"], boot["seed"])
    s = 1 - b_model[idx].sum(axis=1) / b_ref[idx].sum(axis=1)
    a = (1 - boot["level"]) / 2
    return {"bss": float(1 - b_model.sum() / b_ref.sum()), "lo": float(np.quantile(s, a)),
            "hi": float(np.quantile(s, 1 - a))}


def summary(sc: pd.DataFrame) -> dict:
    return {"n": int(len(sc)), "logloss": float(sc["logloss"].mean()), "brier": float(sc["brier"].mean()),
            "acierto": float(sc["hit"].mean())}


def episodes(lab: pd.DataFrame, pad: int = 6) -> list[dict]:
    """Episodios fijados a priori: (a) recesiones NBER (usrec de la etiqueta oficial) con ±`pad` meses;
    (b) rachas de la etiqueta dura oficial (cada racha = un episodio de régimen)."""
    out = []
    u = lab["usrec"].fillna(0).astype(int)
    starts = u.index[(u == 1) & (u.shift(1, fill_value=0) == 0)]
    ends = u.index[(u == 1) & (u.shift(-1, fill_value=0) == 0)]
    for s, e in zip(starts, ends):
        out.append({"tipo": "recesion_nber", "id": f"rec {s:%Y-%m}",
                    "desde": s - pd.DateOffset(months=pad), "hasta": e + pd.DateOffset(months=pad)})
    h = lab["label_hard"]
    run = (h != h.shift()).cumsum()
    for _, g in h.groupby(run):
        out.append({"tipo": "racha_regimen", "id": f"{g.iloc[0]} {g.index[0]:%Y-%m}",
                    "desde": g.index[0], "hasta": g.index[-1]})
    return out
