"""Validador (re-auditoría final v0.3): potencia de (c) placebo y (d) señal plantada con el constructor de 64186fe.

Reutiliza pit_v0_2_power.py; (c) corre sobre la matriz oficial v0.3 (etiqueta ≤ 2004 BARAJADA en bloques de 24; nunca
2005→) e incluye el control a priori del test (etiqueta de t−4) con la función del propio test (persistence_onehot).
Ejecutar: .venv/bin/python tests/validation/pit_v0_3_power.py [d|c]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pit_v0_2_power as M  # noqa: E402
from pit_v0_2_power import P, PL, R, persistence_onehot  # noqa: E402


def run_c(n_perm=8):
    assert P.VERSION == "0.3"
    X = pd.read_parquet(P.out_dir() / "pit_us_v0.3_vintage.parquet").set_index("decision_date")
    X = X.set_index(X.index.to_period("M").to_timestamp())[
        ["curve_10y3m", "payems_3m_ann", "indpro_3m_ann", "unrate_sahm", "headline_cpi_6m_ann", "ppi_yoy",
         "baa_spread", "ff_d12m"]]
    lab = pd.read_parquet(R.out_path())
    lab = lab[(lab["weight"] > 0) & ~lab["provisional"] & (lab["date"] < pd.Timestamp(R.PARAMS.holdout_start))]
    lab = lab.set_index("date")
    assert lab.index.max() < pd.Timestamp("2005-01-01")
    common = lab.index.intersection(X.dropna().index)
    common = common[common >= pd.Timestamp("1962-01-01")]
    print("muestra placebo:", common.min().date(), "→", common.max().date(), len(common))
    y = np.array([R.QUADRANTS.index(q) for q in lab.loc[common, "label_hard"]])
    F = X.loc[common].to_numpy(float)

    def noisy(sd):
        return lambda ys, rng: np.eye(4)[ys][:, 1:] + rng.normal(0, sd, (len(ys), 3))

    cases = {"sin_fuga": None, **{f"ruido_{sd}": noisy(sd) for sd in (0.5, 1.0, 1.5, 2.0)},
             **{f"etiqueta_t-{k} (persistence_onehot del test)": (lambda k: lambda ys, rng: persistence_onehot(ys, lag=k))(k)
                for k in (4, 3, 1)},
             "etiqueta_t-5 (sin fuga: duplica la persistencia)": lambda ys, rng: persistence_onehot(ys, lag=5)}
    rows = []
    for name, leak in cases.items():
        sk = PL.placebo_skills(F, y, common, n_perm=n_perm, leak=leak)
        rows.append({"caso": name, "media": sk.mean(), "min": sk.min(), "max": sk.max(),
                     "falla_placebo": not PL.placebo_check(sk), "detecta_todas": bool((sk > PL.PLACEBO_TOL).all())})
        print(rows[-1], flush=True)
    print(pd.DataFrame(rows).round(3).to_string())


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "dc"
    if "c" in what:
        run_c()
    if "d" in what:
        M.run_d()
