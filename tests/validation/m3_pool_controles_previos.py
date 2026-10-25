"""Controles SINTÉTICOS previos a las corridas de desarrollo de M3 y del pool (Validador, 25-oct; sin datos ni etiqueta).

1. Repite con el código ACTUAL (M2 v1.3) los controles sintéticos de M3 (señal plantada y ruido, m3_tvtp_spec.md §5) y
   del pool ((i)-(iii), pool_spec.md §5), que se corrieron el 24-oct con el código de 0bd606b. Mismas funciones
   (`src/models/pool_controls.py`), sin escribir en research/trials ni en el trial log.
2. PILA COMPLETA en el arnés (nunca probada antes de extremo a extremo): M0 + m2_struct_g (v1.3) + m3_tvtp_g +
   m3_ctp_g + pool_g sobre el panel sintético de `tests/m2_synth.py`, refit 1, con bastantes cortes para que el pool
   salga del arranque (N_min = 60). Comprueba: predicciones finitas y en (0, 1); el arnés verifica que cada p_{k,s}
   viene de su corte (stack_frame); pool = M0 bit a bit antes de N_min; después, pool activo con pesos en el simplex;
   eje I idéntico a M0 en todos; la marca philly_pre1990_nan heredada = false.

    PYTHONPATH=. python tests/validation/m3_pool_controles_previos.py research/validation/m3_pool_controles_previos/resultado.json
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np
import pandas as pd

from src.labels import regime_us as R
from src.models import base as B
from src.models import harness as H
from src.models import metrics as M
from src.models import models_pool as MP
from src.models import models_struct as MS
from src.models import models_tvtp as MT
from src.models import pool_controls as PC
from src.models import regime_components as C
from tests.m2_synth import Synth, array_data

SEED_SYNTH, SEED_Z = 4, 0
TEST_START, TEST_END = "1985-01", "1993-12"      # 108 cortes: el pool supera N_min = 60 hacia 1991


@contextlib.contextmanager
def meta_sintetico():
    """Como la fixture `synthetic_label_meta` de tests/conftest.py: si no existe el meta.json oficial de la etiqueta
    (sin datos), `assert_no_forbidden` usa uno sintético (columnas de la etiqueta y USREC prohibidas por código). Si
    existe, no hace nada."""
    meta = R.out_path().with_suffix(".meta.json")
    if meta.exists():
        yield
        return
    orig = R.out_path
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / meta.name).write_text(json.dumps(
            {"forbidden_features": {"label_columns": sorted(R.FORBIDDEN_FEATURES), "series": []}}))
        R.out_path = lambda p=R.PARAMS: Path(d) / f"regime_us_v{p.version}.parquet"
        try:
            yield
        finally:
            R.out_path = orig


def pila() -> dict:
    s = Synth(SEED_SYNTH)
    rng = np.random.default_rng(SEED_Z)
    ex = pd.DataFrame(rng.standard_normal((len(s.idx), 3)), index=s.idx, columns=list(MT.TRANS))
    data = array_data(s, extra_X=ex)
    reg = {"m0_calibrated_persistence": B.CalibratedPersistence, "m2_struct_g": MS.StructuralG,
           "m3_tvtp_g": MT.REGISTRY["m3_tvtp_g"], "m3_ctp_g": MT.REGISTRY["m3_ctp_g"], "pool_g": MP.REGISTRY["pool_g"]}
    cfg = H.HarnessConfig(name="pila_sintetica", models=tuple(reg), modes=("synthetic",), test_start=TEST_START,
                          test_end=TEST_END, refit_every=1, baseline="m0_calibrated_persistence", epochs=(),
                          min_train_recessions=0, min_train_g_changes=0,
                          model_params={"m2_struct_g": {"philly_pre1990_nan": False}})
    MS.clear_engines()
    with meta_sintetico():
        r = H.run(cfg, registry=reg, datas={"synthetic": data}, record=False)
    p = r["preds"]
    out = {"cortes": int(p["month"].nunique()), "modelos": sorted(p["model"].unique())}
    pc = p[M.P_COLS].to_numpy()
    out["finitas_y_en_0_1"] = bool(np.isfinite(pc).all() and (pc > 0).all() and (pc < 1).all())
    wide = {m: g.set_index("month")[M.P_COLS] for m, g in p.groupby("model")}
    i_axis = {m: (w.to_numpy() @ M.I_HIGH) for m, w in wide.items()}
    out["eje_I_igual_a_M0"] = bool(all(np.allclose(v, i_axis["m0_calibrated_persistence"], atol=1e-12)
                                      for v in i_axis.values()))
    hist = [x for x in r["diag"]["synthetic"] if x["model"] == "pool_g" and x.get("diag_modelo")]
    coefs = [x for x in r["diag"]["synthetic"] if x["model"] == "pool_g" and x.get("coef")]
    g_pool = wide["pool_g"].to_numpy() @ M.G_HIGH
    g_m0 = wide["m0_calibrated_persistence"].to_numpy() @ M.G_HIGH
    n_est = np.array([c["coef"].get("G:n_est", np.nan) for c in coefs], float)
    pre = n_est < C.POOL.n_min
    out["meses_pool_igual_M0_antes_de_Nmin"] = int(pre.sum())
    out["pool_bit_a_bit_M0_antes_de_Nmin"] = bool(np.array_equal(g_pool[: pre.sum()], g_m0[: pre.sum()]))
    out["meses_pool_activo"] = int((~pre).sum())
    if (~pre).any():
        last = coefs[-1]["coef"]
        w = np.array([last["G:w_m0"], last["G:w_m2"], last["G:w_m3"]])
        out["pesos_finales"] = {"w_m0": w[0], "w_m2": w[1], "w_m3": w[2], "a": last["G:blp_a"], "b": last["G:blp_b"]}
        out["pesos_en_simplex"] = bool(np.all(w > 0) and abs(w.sum() - 1) < 1e-9)
        out["pool_distinto_de_M0_tras_activar"] = bool(not np.allclose(g_pool[pre.sum():], g_m0[pre.sum():]))
    out["diag_pool"] = hist[-1]["diag_modelo"] if hist else None
    rep = r["report"]["frente_al_baseline"]
    out["mejora_logloss_sintetica"] = {k: rep[k]["mejora_logloss"]["mean"] for k in rep}
    out["marca_heredada"] = {m.name: m.params.get("philly_pre1990_nan") for m in H.build_models(cfg, reg)
                             if "philly_pre1990_nan" in getattr(m, "params", {})}
    return out


def main(dest: str) -> None:
    t0 = time.time()
    res = {"m3": PC.m3_controls(), "pool": PC.pool_controls()}
    res["m3"]["ruido"]["criterio_<=0.005"] = res["m3"]["ruido"].pop("cumple_<=0.005")
    w = res["pool"]["(i)_oraculo_w"]
    res["pool"]["(i)_cumple_oraculo_domina"] = bool(w[1] > max(w[0], w[2]))
    w0 = res["pool"]["(ii)_sin_info_w"]
    res["pool"]["(ii)_cumple_previa"] = bool(np.allclose(w0, C.POOL.prior_mode, atol=0.02))
    res["pool"]["(iii)_cumple_a_b_mayor_1"] = bool(min(res["pool"]["(iii)_infradispersado_a_b"]) > 1)
    res["pila"] = pila()
    res["segundos"] = round(time.time() - t0, 1)
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float))
    print(json.dumps(res, indent=1, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main(sys.argv[1])
