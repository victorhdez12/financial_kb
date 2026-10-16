import os, sys, json
S = sys.argv[1]
os.environ["FKB_TRIALS_DIR"] = S + "/trials_sens"; os.environ["FKB_RUNS_DIR"] = S + "/runs_sens"; os.environ["FKB_TRIAL_LOG"] = S + "/tl_sens.md"
open(S + "/tl_sens.md", "w").write("|h|\n")
sys.path.insert(0, "/Users/victorhdez12/Proyectos/financial_kb")
from src.models import harness as H
d = {"vintage": H.PITData("vintage")}
out = {}
for eps, l2 in ((1e-3, 1.0), (1e-4, 1.0), (1e-2, 1.0), (1e-3, 0.1), (1e-3, 10.0)):
    cfg = H.HarnessConfig(name="val_m0_sens", models=("persistence_pit", "m0_calibrated_persistence"),
                          model_params={"m0_calibrated_persistence": {"eps": eps, "l2": l2}}, modes=("vintage",),
                          test_start="1956-10", test_end="2004-12", eval_window=("1975-01", "2004-12"),
                          baseline="m0_calibrated_persistence", reference="persistence_pit")
    r = H.run(cfg, datas=d, record=False)["report"]
    m = r["modelos"]["vintage/m0_calibrated_persistence"]
    out[f"eps={eps},l2={l2}"] = {"logloss": round(m["logloss"], 4), "ll_g": round(m["ll_g"], 4), "ll_i": round(m["ll_i"], 4)}
    print(out, flush=True)
json.dump(out, open(S + "/m0_sens.json", "w"), indent=1)
