"""Validador: potencia de las pruebas (c) placebo y (d) señal plantada. Solo datos sintéticos (mismo generador que
tests/test_pit_leaks.py::_synthetic), sin datos reales ni etiqueta. Ejecutar con .venv/bin/python."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pit_helpers import wf_skill, persistence_onehot

def gen(seed):
    rng = np.random.default_rng(seed)
    months = pd.date_range("1950-01-01", "2004-12-01", freq="MS")
    P_ = np.full((4, 4), 0.07 / 3) + np.eye(4) * (0.93 - 0.07 / 3)
    y = [0]
    for _ in range(len(months) - 1): y.append(rng.choice(4, p=P_[y[-1]]))
    y = np.array(y); mu = np.array([1.5, 0.5, -0.5, -1.5])
    x = mu[y] + rng.normal(0, 0.5, len(y)); first = x + rng.normal(0, 0.3, len(y))
    return months, y, x, first, rng.normal(0, 1, len(y))

def sk(months, y, f):
    ok = slice(2, None)
    return wf_skill(persistence_onehot(y)[ok], f[ok, None], y[ok], months[ok], first_test_year=1965)

rows = []
for seed in range(20):
    m, y, x, first, noise = gen(seed)
    lag1 = np.r_[np.nan, first[:-1]]; lag2 = np.r_[np.nan, np.nan, first[:-2]]
    lag1, lag2 = np.nan_to_num(lag1), np.nan_to_num(lag2)
    # placebo con variable con FUGA (dato del propio mes t, revisado) y etiqueta barajada en bloques de 24
    rng = np.random.default_rng(100 + seed); nb = int(np.ceil(len(y) / 24))
    ys = np.concatenate([y[i * 24:(i + 1) * 24] for i in rng.permutation(nb)])[:len(y)]
    rows.append(dict(seed=seed, correcto_t1=sk(m, y, lag1), conservador_t2=sk(m, y, lag2),
                     fuga_t=sk(m, y, x), ruido=sk(m, y, noise), placebo_con_fuga=sk(m, ys, x)))
D = pd.DataFrame(rows)
print(D.round(3).to_string()); print(D.describe().round(3).to_string())
