"""Etiqueta de régimen recalculada point-in-time (docs/models/harness.md §3; ficha de la etiqueta §12).

En cada fecha de decisión T, `PITLabeler.at(T)` devuelve la etiqueta v1.1 COMPLETA recalculada solo con los niveles
conocidos en T, desde las instantáneas congeladas de la etiqueta (R.FROZEN) y de la base PIT (P.FROZEN):

- `vintage`: las series tal como se publicaron en T (vintages de la instantánea de la etiqueta); fuera del archivo
  de vintages, la última vintage truncada por fecha de publicación (calendario congelado de la base PIT);
- `latest_truncated`: la última vintage truncada por fecha de publicación.

Es exactamente el cálculo de `src.features.pit.persistence` (mismo bucle, mismas entradas y parámetros), pero
devolviendo la etiqueta entera en lugar de su última fila: la última fila es la persistencia PIT (lo comprueba
`tests/test_harness.py` bit a bit frente a los baselines congelados) y el resto son las ETIQUETAS DE ENTRENAMIENTO del
corte T (prohibido entrenar con la etiqueta final precalculada).

Barrera (Validador v1, M-1/D4): `at(T)` con T ≥ 2005-01 recalcularía la etiqueta del periodo bloqueado desde la
instantánea (que llega a 2026). Solo se permite con una caja fuerte de evaluación desbloqueada (identidad, no duck
typing); si no, se registra y lanza `HoldoutLocked`.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from src.features import pit as P
from src.features.calendar import VintageSet, availability, load_calendar
from src.labels import regime_us as R
from src.models import vault as V

KEEP = ["date", "G", "I", "p_g_high", "p_i_high", *[f"p_{q}" for q in R.QUADRANTS], "label_hard", "weight",
        "provisional"]


def _sha(paths) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(Path(p).read_bytes())
    return h.hexdigest()


class PITLabeler:
    """Etiqueta recalculada con los datos conocidos en cada fecha de decisión (un modo)."""

    def __init__(self, mode: str, pit_version: str = "0.3", vault=None):   # la congelada (la v0.4 da lo mismo)
        if mode not in P.MODES:
            raise ValueError(f"modo desconocido: {mode}")
        self.mode, self.vault = mode, vault
        con, self.wl, cal_path, _info = P.read_snapshot(pit_version)  # verifica hashes (P.FROZEN)
        self.inputs, _ = R.read_snapshot()                           # verifica hashes (R.FROZEN)
        self.lp = P.label_params(self.inputs)                        # s_G, s_I, empalme (hash del meta fijado)
        self.cal = load_calendar(cal_path)
        wh = P.Warehouse(con, raw=False)
        self.snapv = {sid: VintageSet(v, sid) for sid, (v, _) in self.inputs["vintages"].items() if len(v)}

        def vset(sid):
            return self.snapv.get(sid) or wh.vint(sid)

        self.levels = {sid: s.dropna() for sid, s in self.inputs["levels"].items()}
        self.av = {sid: availability(self.cal[sid], s.index, [vset(p) for p in self.cal[sid].proxies])
                   for sid, s in self.levels.items()}
        con.close()
        self._cache: dict[pd.Timestamp, pd.DataFrame] = {}

    def _guard(self, t: pd.Timestamp, what: str) -> None:
        if t >= V.HOLDOUT_START and not V.is_open_holdout_vault(self.vault):
            why = f"PITLabeler.{what}({t:%Y-%m-%d}): etiqueta recalculada del periodo bloqueado sin evaluación única"
            V.log_access({"mode": "pit_labeler", "granted": False, "why": why, "labeler_mode": self.mode})
            raise V.HoldoutLocked(why)

    def levels_at(self, t: pd.Timestamp) -> dict[str, pd.Series]:
        """Niveles conocidos en t. Barrera (Validador v2, N4/B2-1): t ≥ 2005-01 solo con la caja de la evaluación."""
        t = pd.Timestamp(t)
        self._guard(t, "levels_at")
        lv = {}
        for sid, s in self.levels.items():
            vs = self.snapv.get(sid) if self.mode == "vintage" else None
            if vs is not None and vs.start <= t:
                snap = vs.snapshot(t)
                snap = snap[P._not_before_period_end(self.cal[sid], snap.index) <= t]
                lv[sid] = R._cal(snap)
            else:
                lv[sid] = R._cal(s[self.av[sid].reindex(s.index).to_numpy() <= np.datetime64(t)])
        return lv

    def from_vintage(self, t) -> dict[str, bool]:
        """Por serie, si `levels_at(t)` la toma de una vintage de la instantánea (misma regla que `levels_at`; v2.4)."""
        t = pd.Timestamp(t)
        self._guard(t, "from_vintage")
        out = {}
        for sid in self.levels:
            vs = self.snapv.get(sid) if self.mode == "vintage" else None
            out[sid] = bool(vs is not None and vs.start <= t)
        return out

    def at(self, t) -> pd.DataFrame:
        """Etiqueta completa calculable en la fecha de decisión t (columnas KEEP; vacía si no hay ninguna)."""
        t = pd.Timestamp(t)
        self._guard(t, "at")
        if t not in self._cache:
            lab, _ = R.make_label({"levels": self.levels_at(t), "usrec": self.inputs["usrec"]}, R.PARAMS,
                                  self.lp["s_G"], self.lp["s_I"], splice=self.lp["splice"])
            self._cache[t] = lab[KEEP].reset_index(drop=True) if len(lab) else pd.DataFrame(columns=KEEP)
        return self._cache[t]

    def persistence(self, t) -> dict | None:
        """Persistencia PIT en t: la última fila de la etiqueta calculable en t (= src.features.pit.persistence)."""
        lab = self.at(t)
        if lab.empty:
            return None
        last = lab.iloc[-1]
        return {"label_month": last["date"], **{f"pers_{q}": float(last[f"p_{q}"]) for q in R.QUADRANTS},
                "pers_hard": last["label_hard"]}


def code_sha() -> str:
    """Hash del código que define la etiqueta PIT (este módulo + etiqueta + base PIT + calendario)."""
    src = Path(__file__).resolve().parents[1]
    return _sha([Path(__file__), src / "labels" / "regime_us.py", src / "features" / "pit.py",
                 src / "features" / "calendar.py"])
