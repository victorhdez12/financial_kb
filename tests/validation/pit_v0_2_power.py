"""Validador (re-auditoría v0.2): potencia de (c) placebo y (d) señal plantada con el CONSTRUCTOR REAL.

(d) 20 semillas del generador de tests/test_pit_leaks.py::_synthetic, pasando por P.build_matrix:
    correcto (vintage, publicación a 20 d), fuga (−10 d: dato de t en t), retardo demasiado corto (el calendario dice
    20 d pero la serie se publica a 50 d y no hay vintages que lo delaten), y demasiado conservador (calendario 50 d).
(c) placebo sobre la matriz oficial (etiqueta ≤ 2004 BARAJADA en bloques de 24; nunca 2005→): barrido de la fuerza
    de la fuga (ruido de la variable con fuga) y fugas "de calendario" de la etiqueta (y de t−4, t−3, t−1 en lugar
    de t−5).
Ejecutar: .venv/bin/python tests/validation/pit_v0_2_power.py [d|c]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))
from pit_helpers import persistence_onehot, synthetic_warehouse, wf_skill  # noqa: E402
from src.features import pit as P  # noqa: E402
from src.features import placebo as PL  # noqa: E402
from src.features.calendar import CalEntry  # noqa: E402
from src.labels import regime_us as R  # noqa: E402

ONE = lambda d: ((pd.Timestamp("1900-01-01"), d),)  # noqa: E731


def synth(seed, variant):
    rng = np.random.default_rng(seed)
    months = pd.date_range("1950-01-01", "2004-12-01", freq="MS")
    T = np.full((4, 4), 0.07 / 3) + np.eye(4) * (0.93 - 0.07 / 3)
    y = [0]
    for _ in range(len(months) - 1):
        y.append(rng.choice(4, p=T[y[-1]]))
    y = np.array(y)
    x = np.array([1.5, 0.5, -0.5, -1.5])[y] + rng.normal(0, 0.5, len(y))
    first = x + rng.normal(0, 0.3, len(y))
    noise = rng.normal(0, 1, len(y))
    pe = months + pd.offsets.MonthEnd(0)
    true_lag = 50 if variant == "corto" else 20
    rows = [pd.DataFrame({"date": months, "value": x, "series_id": "SYN_SIGNAL", "source": "syn"}),
            pd.DataFrame({"date": months, "value": noise, "series_id": "SYN_NOISE", "source": "syn"})]
    if variant == "correcto":
        rows += [pd.DataFrame({"date": months, "value": first, "series_id": "SYN_SIGNAL", "source": "syn",
                               "realtime_start": pe + pd.Timedelta(days=true_lag)}),
                 pd.DataFrame({"date": months, "value": x, "series_id": "SYN_SIGNAL", "source": "syn",
                               "realtime_start": pe + pd.Timedelta(days=110)})]
    cat = pd.DataFrame({"series_id": ["SYN_SIGNAL", "SYN_NOISE"], "source": "syn", "units": "x",
                        "pit_role": "observed"})
    mem = synthetic_warehouse(pd.concat(rows, ignore_index=True), cat, "2005-03-01")
    lag = {"correcto": 20, "fuga": -10, "corto": 20, "conservador": 50}[variant]
    if variant == "correcto":
        sig = CalEntry("SYN_SIGNAL", "M", "fin_periodo", ONE(20), ("SYN_SIGNAL",), ("SYN_SIGNAL",), False, "", "")
        modo = "vintage"
    else:   # sin vintages: el calendario manda (y no hay nada que lo contradiga)
        sig = CalEntry("SYN_SIGNAL", "M", "fin_periodo", ONE(lag), (), (), True, "", "")
        modo = "latest_truncated"
    cal = {"SYN_SIGNAL": sig, "SYN_NOISE": CalEntry("SYN_NOISE", "M", "fin_periodo", ONE(20), (), (), True, "", "")}
    wl = {"zscore_min_meses": 120, "variables": [
        {"nombre": "syn_signal", "tipo": "serie", "series": ["SYN_SIGNAL"], "transformacion": {"fn": "level"},
         "modo": modo},
        {"nombre": "syn_noise", "tipo": "serie", "series": ["SYN_NOISE"], "transformacion": {"fn": "level"},
         "modo": "latest_truncated"}]}
    grid = P.decision_grid(today=pd.Timestamp("2005-01-15"))
    grid = grid[grid["month"] <= months.max()]
    X, lin, _ = P.build_matrix(mem, "vintage", grid, wl=wl, cal=cal, forbidden=[])
    mem.close()
    mv = X.set_index(X.index.to_period("M").to_timestamp())
    yy = pd.Series(y, index=months).reindex(mv.index).to_numpy()
    ok = slice(2, None)
    base = persistence_onehot(yy)[ok]
    f = mv["syn_signal"].to_numpy()[ok, None]
    f = np.nan_to_num(f)
    return (wf_skill(base, f, yy[ok], mv.index[ok], first_test_year=1965),
            wf_skill(base, mv["syn_noise"].to_numpy()[ok, None], yy[ok], mv.index[ok], first_test_year=1965))


def run_d(seeds=range(20)):
    rows = []
    for s in seeds:
        r = {"seed": s}
        for v in ("correcto", "fuga", "corto", "conservador"):
            r[v], nz = synth(s, v)
            if v == "correcto":
                r["ruido"] = nz
        rows.append(r)
        print(r, flush=True)
    D = pd.DataFrame(rows)
    print(D.describe().round(3).to_string())
    print("correcto en [0,20; 0,40]:", D["correcto"].between(0.20, 0.40).mean(),
          "| fuga > 0,42:", (D["fuga"] > 0.42).mean(), "| corto en [0,20;0,40]:", D["corto"].between(0.2, 0.4).mean())
    return D


def run_c(n_perm=8):
    snap = P.read_snapshot()
    con, wl, cal_path, info = snap
    X = pd.read_parquet(P.out_dir() / "pit_us_v0.2_vintage.parquet").set_index("decision_date")
    X = X.set_index(X.index.to_period("M").to_timestamp())[
        ["curve_10y3m", "payems_3m_ann", "indpro_3m_ann", "unrate_sahm", "headline_cpi_6m_ann", "ppi_yoy",
         "baa_spread", "ff_d12m"]]
    lab = pd.read_parquet(R.out_path())
    lab = lab[(lab["weight"] > 0) & ~lab["provisional"] & (lab["date"] < pd.Timestamp(R.PARAMS.holdout_start))]
    lab = lab.set_index("date")
    assert lab.index.max() < pd.Timestamp("2005-01-01")
    common = lab.index.intersection(X.dropna().index)
    common = common[common >= pd.Timestamp("1962-01-01")]
    y = np.array([R.QUADRANTS.index(q) for q in lab.loc[common, "label_hard"]])
    F = X.loc[common].to_numpy(float)

    def noisy(sd):
        return lambda ys, rng: np.eye(4)[ys][:, 1:] + rng.normal(0, sd, (len(ys), 3))

    def early(k):   # la etiqueta de t−k en lugar de t−5 (fuga de calendario de 5−k meses)
        def f(ys, rng):
            out = np.zeros((len(ys), 3))
            for i in range(k, len(ys)):
                if ys[i - k] > 0:
                    out[i, ys[i - k] - 1] = 1.0
            return out
        return f

    cases = {"sin_fuga": None, **{f"ruido_{sd}": noisy(sd) for sd in (0.5, 1.0, 1.5, 2.0, 3.0)},
             **{f"etiqueta_t-{k}": early(k) for k in (4, 3, 1)}}
    rows = []
    for name, leak in cases.items():
        sk = PL.placebo_skills(F, y, common, n_perm=n_perm, leak=leak)
        rows.append({"caso": name, "media": sk.mean(), "min": sk.min(), "max": sk.max(),
                     "falla_placebo": not PL.placebo_check(sk), "detecta_todas": bool((sk > PL.PLACEBO_TOL).all())})
        print(rows[-1], flush=True)
    print(pd.DataFrame(rows).round(3).to_string())


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "dc"
    if "d" in what:
        run_d()
    if "c" in what:
        run_c()
