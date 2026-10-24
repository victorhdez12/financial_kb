"""Validador (revisión de las specs a priori del pool, 24-oct: commits 1a5f1f9 y 34554c6). SOLO datos SINTÉTICOS:
no lee la etiqueta, la base PIT, los scores de desarrollo ni nada ≥ 2005. No ajusta ni corre ningún modelo.

Comprueba:
  1. `power.harness_test` reproduce `metrics.boot_mean` (lo, p_h0) exactamente.
  2. Tamaño del contraste del arnés (bloques de 12) con efecto 0: (a) serie estacionaria persistente "real" frente a
     (b) el proceso generador de `power.py` (bootstrap por bloques ALINEADOS de 12 de una serie fuente). (b) corta la
     dependencia en 12 meses y, con dependencia larga, infraestima el tamaño real.
  3. `coefficient_signs`/`frac_signo_esperado` cuenta γ = 0 como "no positivo" y γ = 1e-12 como positivo: el criterio
     "γ > 0 en ≥ 50 % de los cortes" necesita una tolerancia explícita.
  4. d_t del pool: la diferencia de log-loss de 4 cuadrantes = la del eje G cuando el eje I es común, salvo cuando el
     recorte de `metrics.prep` (CLIP = 1e-4 por cuadrante) actúa (P(G) extrema).

Ejecutar: .venv/bin/python tests/validation/specs_pool_v4_validation.py <salida.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.models import metrics as M  # noqa: E402
from src.models import power as P  # noqa: E402

OUT: dict = {}
rng = np.random.default_rng(20261024)


# 1 ------------------------------------------------------------------------------------------------------------
X = rng.standard_normal((5, 202)) * 0.3 + 0.02
t = P.harness_test(X)
ok = True
for i in range(len(X)):
    b = M.boot_mean(X[i])
    ok &= abs(b["lo"] - t["lo"][i]) < 1e-12 and b["p_h0"] == t["p_h0"][i]   # igual salvo redondeo (1e-17)
OUT["1_harness_test_igual_a_boot_mean"] = bool(ok)
assert ok


# 2 ------------------------------------------------------------------------------------------------------------
def ar(nn: int, phi: float) -> np.ndarray:
    e = rng.standard_t(4, size=nn + 300)
    x = np.zeros(nn + 300)
    for i in range(1, nn + 300):
        x[i] = phi * x[i - 1] + e[i]
    return x[300:]


def size(X: np.ndarray) -> dict:
    t = P.harness_test(X)
    return {"lo_gt_0": float((t["lo"] > 0).mean()), "p_h0_lt_0025": float((t["p_h0"] < 0.025).mean()),
            "p_h0_lt_005": float((t["p_h0"] < 0.05).mean())}


n, nsim, res = P.HOLDOUT_N, 800, {}
for phi in (0.0, 0.6, 0.85, 0.95):
    Xa = np.stack([ar(n, phi) for _ in range(nsim)])                     # media verdadera 0
    src = ar(318, phi)
    src = src - src.mean()                                               # como power.simulate (centrada)
    nb = int(np.ceil(n / 12))
    starts = rng.integers(0, len(src), size=(nsim, nb))
    idx = ((starts[:, :, None] + np.arange(12)[None, None, :]) % len(src)).reshape(nsim, -1)[:, :n]
    res[f"phi={phi}"] = {"serie_real": size(Xa), "dgp_power_py": size(src[idx])}
OUT["2_tamano_efecto_0_nominal_lo_0025"] = res


# 3 ------------------------------------------------------------------------------------------------------------
g = np.array([0.0, 0.0, 1e-12, 1e-9, 0.3])
OUT["3_frac_signo_positivo_como_el_arnes"] = float((np.sign(g) == 1).mean())          # 0,6: 1e-12 cuenta como > 0
OUT["3_frac_con_tolerancia_1e-6"] = float((g > 1e-6).mean())                           # 0,2


# 4 ------------------------------------------------------------------------------------------------------------
def d4_vs_dg(pg_pool, pg_m0, pi, tq):
    S0 = M.monthly_scores(M.combine_axes(pg_m0, pi), tq, np.array(["expansion"] * len(pi)))
    S1 = M.monthly_scores(M.combine_axes(pg_pool, pi), tq, np.array(["expansion"] * len(pi)))
    return float(np.max(np.abs((S0["logloss"] - S1["logloss"]) - (S0["ll_g"] - S1["ll_g"]))))


m = 400
tq = rng.dirichlet(np.ones(4), size=m)                                   # objetivo blando NO producto
pi = rng.uniform(0.05, 0.95, m)
pg0 = rng.uniform(0.01, 0.99, m)
OUT["4_dif_max_interior"] = d4_vs_dg(rng.uniform(1e-3, 1 - 1e-3, m), pg0, pi, tq)
OUT["4_dif_max_pool_extremo_1e-5"] = d4_vs_dg(np.full(m, 1e-5), pg0, pi, tq)
assert OUT["4_dif_max_interior"] < 1e-9

print(json.dumps(OUT, indent=1))
if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(json.dumps(OUT, indent=1))
