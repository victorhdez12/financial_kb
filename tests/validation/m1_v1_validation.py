"""Validador (auditoría de M1, entregable 4; commits bf7049d → 9b64c5c). Solo ≤ 2004.

Usa las corridas reproducidas por el Validador desde `git archive 1f9c52b` (directorio de artefactos en argv[2]) y
la corrida de los baselines v2 reproducida desde `git archive 2159d53` (argv[3]).
Ejecutar: .venv/bin/python tests/validation/m1_v1_validation.py <salida.json> <runs_m1> <runs_baselines_v2>
"""
from __future__ import annotations

import glob
import json
import os
import sys
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="fkb_val_m1_"))
os.environ["FKB_TRIALS_DIR"] = str(TMP / "trials")
os.environ["FKB_RUNS_DIR"] = str(TMP / "runs")
os.environ["FKB_TRIAL_LOG"] = str(TMP / "tl.md")
(TMP / "tl.md").write_text("|h|\n")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.models import harness as H  # noqa: E402
from src.models import metrics as M  # noqa: E402

OUT: dict = {}
dest, runs_m1, runs_b2 = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])


def load(pattern, root):
    d = Path(glob.glob(str(root / pattern))[0])
    return json.loads((d / "report.json").read_text()), pd.read_parquet(d / "scores.parquet"), \
        pd.read_parquet(d / "predictions.parquet")


jm, Sm, Pm = load("*_m1_logit_axis_v1_3f435b7b", runs_m1)
jl, Sl, Pl = load("*_m1_logit_axis_v1_long_0e55b60b", runs_m1)
jb, Sb, Pb = load("*_baselines_v2_1a6d6df8", runs_b2)


def cmp(rep, key):
    c = rep["report"]["frente_al_baseline"][key]
    return {k: [round(c[k]["mean"], 4), round(c[k]["lo"], 4), round(c[k]["hi"], 4)]
            for k in ("mejora_logloss", "mejora_ll_g", "mejora_ll_i")} | \
        {"giro": round(c["cortes"]["giro"]["mean"], 4), "estable": round(c["cortes"]["estable"]["mean"], 4)}


OUT["principal"] = {k: cmp(jm, k) for k in ("vintage/m1_logit_axis", "latest_truncated/m1_logit_axis",
                                              "vintage/m1_logit_axis_hl", "vintage/rules_v1")}
OUT["larga"] = {k: cmp(jl, k) for k in ("vintage/m1_logit_axis_hl", "latest_truncated/m1_logit_axis_hl",
                                          "vintage/rules_v1_hl")}

# M0 y persistencia de las corridas M1 = baselines v2 (mismos cortes)
ident = {}
for name, P_ in (("principal", Pm), ("larga", Pl)):
    for model in ("m0_calibrated_persistence", "persistence_pit"):
        a = P_[P_["model"] == model].set_index(["mode", "month"])[M.P_COLS]
        b = Pb[Pb["model"] == model].set_index(["mode", "month"])[M.P_COLS]
        common = a.index.intersection(b.index)
        ident[f"{name}/{model}"] = {"filas_comunes": len(common),
                                    "dif_max": float(np.abs(a.loc[common].to_numpy() - b.loc[common].to_numpy()).max())}
OUT["m0_identico_a_baselines_v2"] = ident

# empalme por épocas, recalculado a mano: M1-general < 1989-10 (larga) + M1 ≥ 1989-10 (principal) frente a M0
SW = pd.Timestamp("1989-10-01")
res = {}
for mode in ("vintage", "latest_truncated"):
    m0 = Sl[(Sl["mode"] == mode) & (Sl["model"] == "m0_calibrated_persistence")].set_index("month")
    a = Sl[(Sl["mode"] == mode) & (Sl["model"] == "m1_logit_axis_hl") & (Sl["month"] < SW)].set_index("month")
    b = Sm[(Sm["mode"] == mode) & (Sm["model"] == "m1_logit_axis") & (Sm["month"] >= SW)].set_index("month")
    ep = pd.concat([a, b]).sort_index()
    d = m0.loc[ep.index, "logloss"] - ep["logloss"]
    bm = M.boot_mean(d.to_numpy())
    res[mode] = {"n": len(d), "mejora": [round(bm["mean"], 4), round(bm["lo"], 4), round(bm["hi"], 4)],
                 "m0_principal_en_larga_igual": bool(np.allclose(
                     m0.loc[b.index, "logloss"],
                     Sm[(Sm["mode"] == mode) & (Sm["model"] == "m0_calibrated_persistence")].set_index("month")
                     .loc[b.index, "logloss"]))}
    # sensibilidad: si el cambio de época fuera 1988-06 (el a priori), ¿qué meses faltan? (M1-subyacente no los cubre)
OUT["epocas"] = res

# M1-general frente a M0 en 1988-06…1989-09 (los meses que quitó el cambio post hoc de ventana)
for mode in ("vintage", "latest_truncated"):
    m0 = Sl[(Sl["mode"] == mode) & (Sl["model"] == "m0_calibrated_persistence")].set_index("month")
    hl = Sl[(Sl["mode"] == mode) & (Sl["model"] == "m1_logit_axis_hl")].set_index("month")
    sel = (m0.index >= "1988-06-01") & (m0.index <= "1989-09-01")
    d = m0.loc[sel, "logloss"] - hl.loc[m0.index[sel], "logloss"]
    OUT.setdefault("meses_quitados_1988_06_1989_09", {})[mode] = {
        "n": int(sel.sum()), "m1_general_menos_m0_mejora_media": round(float(d.mean()), 4)}
    # y la principal con M1-general desde 1988-06 frente a desde 1989-10
    for start in ("1988-06-01", "1989-10-01"):
        s2 = m0.index >= start
        dd = m0.loc[s2, "logloss"] - hl.loc[m0.index[s2], "logloss"]
        OUT["meses_quitados_1988_06_1989_09"][mode][f"m1_general_desde_{start[:7]}"] = round(float(dd.mean()), 4)

# signos de coeficientes (diag de las corridas)
signs = {}
for nm, j, model in (("principal", jm, "m1_logit_axis"), ("larga", jl, "m1_logit_axis_hl")):
    for mode, dl in j["diag"].items():
        rows = {x["refit_month"]: x["coef"] for x in dl if x["model"] == model and x.get("coef")
                and not any(e.get("skipped") for e in x.get("ejes", {}).values())}
        C = pd.DataFrame.from_dict(rows, orient="index")
        if "G_unrate_sahm" in C:
            s = C["G_unrate_sahm"].dropna()
            signs[f"{nm}/{mode}"] = {"n": len(s), "frac_negativo": float((s < 0).mean()),
                                     "media": round(float(s.mean()), 3), "min": round(float(s.min()), 3),
                                     "max": round(float(s.max()), 3)}
OUT["sahm"] = signs

# espía de M1: entrenamiento ≤ m0 − 6, columnas declaradas, estandarización con el entrenamiento
from src.models import models_logit as L  # noqa: E402

d = H.PITData("vintage")
calls = []
real = L.LogitAxis.fit_axis


def spy(self, axis, X, t, w, info):
    real(self, axis, X, t, w, info)
    feats = list(self.axis_features[axis])
    mu, sd = self._std.get(axis, (np.array([]), np.array([])))
    calls.append({"m0": info["refit_month"], "axis": axis, "max": X.index.max(), "cols": list(X.columns),
                  "mu_ok": bool(np.allclose(mu, X[feats].mean().to_numpy())) if feats else True,
                  "lab_ok": bool(np.allclose(t, d.labeler.at(info["decision_date"]).set_index("date")
                                             .loc[X.index, M.P_COLS].to_numpy(float) @ H.AXIS_VEC[axis]))})


L.LogitAxis.fit_axis = spy
try:
    cfg = H.HarnessConfig(name="val_m1_spy", models=("m0_calibrated_persistence", "m1_logit_axis"),
                          modes=("vintage",), test_start="1989-10", test_end="2004-12", refit_every=36,
                          baseline="m0_calibrated_persistence")
    H.walk_forward(d, H.build_models(cfg, {**H.B.REGISTRY, **L.REGISTRY}), cfg)
finally:
    L.LogitAxis.fit_axis = real
OUT["espia_m1"] = {"ajustes": len(calls),
                   "violaciones_embargo": sum(c["max"] > c["m0"] - pd.DateOffset(months=6) for c in calls),
                   "columnas": sorted({tuple(c["cols"]) for c in calls}),
                   "estandarizacion_con_entrenamiento": all(c["mu_ok"] for c in calls),
                   "objetivo_=_at(T)": all(c["lab_ok"] for c in calls)}

Path(dest).write_text(json.dumps(OUT, indent=1, ensure_ascii=False, default=str))
print(json.dumps(OUT, indent=1, ensure_ascii=False, default=str))
