"""Barrera del periodo bloqueado, v3 (auditoría del Validador, 25-oct; solo sintético, sin datos ni etiqueta):

(1) las cachés compartidas de M2/M3 (`models_struct.FactorEngine`) no pueden saltarse la cota de fecha del arnés: una
    entrada cacheada (por un corte posterior, otra corrida del mismo proceso o una evaluación única anterior) no se
    sirve a una llamada cuya cota es anterior;
(2) el arnés pasa la cota (`pit_bound`) en la info v2.4;
(3) la identidad de datos de `PITData` incluye la fase: desarrollo y evaluación única no comparten cachés;
(4) ningún módulo de src/ lee la etiqueta oficial con `read_parquet` fuera de la caja fuerte, salvo los declarados.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from src.models import harness as H
from src.models import models_struct as MS
from src.models.vault import HoldoutLocked

REPO = Path(__file__).resolve().parents[1]


def _info(bound_month: str, calendar_from="1990-01"):
    months = pd.date_range(calendar_from + "-01", bound_month + "-01", freq="MS")
    cal = pd.Series(months + pd.offsets.MonthEnd(0), index=months)
    calls = []

    def pit_levels(date):
        calls.append(pd.Timestamp(date))
        return {"levels": {}, "from_vintage": {}}
    return {"pit_levels": pit_levels, "decision_calendar": cal, "pit_bound": cal.iloc[-1],
            "data_key": "sintetico", "pit_mode": "vintage", "features_history": pd.DataFrame()}, calls


def test_engine_levels_cache_does_not_bypass_the_bound():
    eng = MS.FactorEngine(MS.StructCfg())
    late, _ = _info("2004-12")
    d = pd.Timestamp("2004-12-31")
    eng.levels_at(late, d)                                   # queda en la caché con una cota posterior
    early, calls = _info("2000-06")
    with pytest.raises(HoldoutLocked):
        eng.levels_at(early, d)                              # misma fecha, cota anterior: no se sirve de la caché
    assert calls == []
    eng.levels_at(early, pd.Timestamp("2000-06-30"))         # dentro de la cota: normal
    assert calls == [pd.Timestamp("2000-06-30")]


def test_engine_nowcast_and_version_caches_check_the_calendar_first():
    eng = MS.FactorEngine(MS.StructCfg())
    v = MS.FactorVersion(T=pd.Timestamp("2000-01-01"), params=np.array([]), d={}, mean={}, sd={}, converged=True,
                         kept_previous=False, fit_info={})
    m = pd.Timestamp("2004-12-01")
    eng.nowcasts[(v.id, v.from_T, m)] = {"G": 1.0}           # como si lo hubiera calculado una corrida con cota 2004-12
    eng.versions[(m, None)] = v
    early, _ = _info("2000-06")
    with pytest.raises(HoldoutLocked):
        eng.nowcast_base(v, m, early)
    with pytest.raises(HoldoutLocked):
        eng.version(m, early, None)


@pytest.mark.usefixtures("synthetic_label_meta")
def test_harness_v24_info_carries_the_bound():
    idx = pd.date_range("1990-01-01", "1999-12-01", freq="MS")
    data = SimpleNamespace(decision=pd.Series(idx + pd.offsets.MonthEnd(0), index=idx),
                           X=pd.DataFrame({"x": np.zeros(len(idx))}, index=idx), data_key="k", mode="vintage",
                           pit_levels=lambda d: {"levels": {}, "from_vintage": {}})
    model = SimpleNamespace(uses_pit_levels=True, name="espia")
    info = H._v24_info(model, data, ["x"], None, pd.Timestamp("1995-06-01"), None)
    assert info["pit_bound"] == pd.Timestamp("1995-06-30")
    assert info["decision_calendar"].index.max() == pd.Timestamp("1995-06-01")


def test_pitdata_data_key_separates_development_from_evaluation():
    key = H.PITData.data_key.fget
    a = SimpleNamespace(pit_version="0.4", matrix_name="m.parquet", mode="vintage", phase="development")
    b = SimpleNamespace(**{**vars(a), "phase": "holdout_evaluation"})
    assert key(a) != key(b)


# Módulos que nombran la etiqueta oficial (R.out_path() o "regime_us_v…") Y leen parquet: DECLARADOS. Es una red
# heurística (un módulo nuevo que lea la etiqueta tiene que pasar por aquí y justificarse), no una prueba formal:
#  - src/labels/regime_us.py, src/labels/checks.py: la construyen, la escriben y la comprueban (muestra completa);
#  - src/features/pit.py: la lee con filtro date < 2005 (persistencia PIT, `pit.py` ~l. 547);
#  - src/models/vault.py: la caja fuerte; src/models/harness.py: solo el meta.json de la etiqueta y las matrices;
#  - src/report/fase3/make_figures.py: figuras de la Fase 3 con la etiqueta 1950 → 2026 (EXPOSICIÓN YA OCURRIDA,
#    a declarar en P-EVAL-BASE A2; no se vuelve a ejecutar sin filtrar < 2005);
#  - src/report/fase3/make_figures_pit.py: la lee con una aserción < 2005.
LABEL_READERS_DECLARED = {"src/labels/regime_us.py", "src/labels/checks.py", "src/features/pit.py",
                          "src/models/vault.py", "src/models/harness.py", "src/report/fase3/make_figures.py",
                          "src/report/fase3/make_figures_pit.py"}
NAMES_LABEL = re.compile(r"out_path\(\)|regime_us_v")


def test_no_new_direct_label_reader_outside_the_vault():
    found = set()
    for f in (REPO / "src").rglob("*.py"):
        txt = f.read_text(encoding="utf-8")
        if "read_parquet" in txt and NAMES_LABEL.search(txt):
            found.add(f.relative_to(REPO).as_posix())
    new = found - LABEL_READERS_DECLARED
    assert not new, f"posible lectura directa de la etiqueta oficial fuera de la caja fuerte: {sorted(new)}"
