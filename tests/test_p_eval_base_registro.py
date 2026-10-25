"""Registro de P-EVAL-BASE (borrador v4.3, §A8-A9): la configuración definitiva es byte a byte el bloque YAML de A8, es
ejecutable (modelos registrados, apilados con sus componentes, familia principal_k1 de un miembro) y la entrada para
research/hypotheses.yaml está preparada pero NO activada. Sin datos.
"""
from __future__ import annotations

import re

import yaml

from src.models import harness as H

DRAFT = H.REPO / "docs" / "models" / "p_eval_base_v4_draft.md"
CFG = H.REPO / "config" / "harness" / "p_eval_base.yaml"
CHECKLIST = H.REPO / "docs" / "models" / "p_eval_base_registro.md"


def _a8_block() -> str:
    s = DRAFT.read_text(encoding="utf-8")
    i = s.index("```yaml\nname: p_eval_base")
    return s[i + len("```yaml\n"):s.index("```", i + 7)]


def test_config_is_exactly_the_a8_block():
    assert CFG.read_text(encoding="utf-8") == _a8_block()


def test_config_is_executable_and_holm_principal_has_one_member():
    cfg = H.HarnessConfig.from_yaml(CFG)
    assert (cfg.name, cfg.prereg_id, cfg.phase, cfg.principal) == ("p_eval_base", "P-EVAL-BASE",
                                                                 "holdout_evaluation", "pool_g")
    assert cfg.eval_window == ("2005-01", "2021-10") and not cfg.allow_shrink
    reg = H.model_registry()
    allm = set(cfg.models) | {m for s in cfg.sensitivities for m in s.get("models", [])}
    assert all(m in reg for m in allm)
    fam = {f["nombre"]: f for f in cfg.holm_families}
    assert [m["modelo"] for m in fam["principal_k1"]["miembros"]] == ["pool_g"]
    models = {m.name: m for m in H.build_models(cfg)}
    assert set(models["pool_g"].components) <= set(models)
    assert all(m.params.get("philly_pre1990_nan") is False for m in models.values()
               if "philly_pre1990_nan" in getattr(m, "params", {}))
    assert [s.name for s in H.suite(cfg)][0] == "p_eval_base"


def test_hypotheses_entry_is_prepared_but_not_active():
    hyp = yaml.safe_load((H.REPO / "research" / "hypotheses.yaml").read_text(encoding="utf-8"))
    assert "P-EVAL-BASE" not in {h.get("id") for h in hyp}
    block = re.search(r"```yaml\n(- id: P-EVAL-BASE.*?)```", CHECKLIST.read_text(encoding="utf-8"), re.S).group(1)
    e = yaml.safe_load(block)[0]
    assert e["tipo"] == "evaluacion_holdout" and str(e["estado"]).startswith("preregistrada")
    assert e["config_arnes"] == "config/harness/p_eval_base.yaml" and e["incluye"] == []
    assert e["ventana"] == ["2005-01", "2021-10"]
