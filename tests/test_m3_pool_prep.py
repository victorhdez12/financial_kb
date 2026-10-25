"""Preparación de las corridas de desarrollo de M3 y del pool (Validador, 25-oct; solo sintético, sin datos):

- control (i) del pool (pool_spec.md §5): con un componente oráculo y dos ruidosos, el peso va al oráculo. Hasta hoy
  solo estaba en `pool_controls.pool_controls()` (script); (ii)-(v) ya tienen test en test_harness_v24.py;
- las configuraciones de las corridas pendientes parsean, validan, sus modelos están registrados, los apilados llevan sus
  componentes y todos los que dependen de M2 heredan philly_pre1990_nan = false (S-PIT-001 no se disparó).
"""
from __future__ import annotations

import numpy as np
import pytest

from src.models import harness as H
from src.models import models_pool as MP
from src.models import regime_components as C

RUNS = ("m2_m1cmp", "m2_sens", "m3_long", "m3_m1cmp", "m3_sens", "pool_dev", "pool_m1cmp", "pool_pesos_uno",
        "pool_pesos_excluir")


def test_pool_control_i_oracle_component_gets_the_weight():
    rng = np.random.default_rng(1)
    n = 3000
    tt = rng.uniform(0.02, 0.98, n)
    P = np.column_stack([np.clip(tt + rng.normal(0, .3, n), .01, .99), tt,
                         np.clip(tt + rng.normal(0, .3, n), .01, .99)])
    st, ok = MP.fit_pool(P, tt, np.ones(n))
    assert ok and st["w"][1] > 0.8 and st["w"][1] > max(st["w"][0], st["w"][2])


@pytest.mark.parametrize("run", RUNS)
def test_pending_dev_configs_parse_and_build(run):
    cfg = H.HarnessConfig.from_yaml(H.REPO / "config" / "harness" / f"{run}.yaml")
    cfg.validate()
    assert cfg.phase == "development" and cfg.test_end == "2004-12" and not cfg.allow_shrink
    reg = H.model_registry()
    assert all(m in reg for m in cfg.models)
    models = H.build_models(cfg)
    names = {m.name for m in models}
    for m in models:
        if hasattr(m, "components"):
            assert set(m.components) <= names, f"{m.name}: faltan componentes en la corrida"
        if "philly_pre1990_nan" in getattr(m, "params", {}):
            assert m.params["philly_pre1990_nan"] is False
    assert C.POOL.components == ("m0_calibrated_persistence", "m2_struct_g", "m3_tvtp_g")
