"""Validador (re-auditoría de las specs a priori v1.1 del pool y de P-EVAL-BASE v4.1, 24-oct: commit d1bde77).
SOLO datos SINTÉTICOS y texto de los documentos: no lee la etiqueta, la base PIT, los scores de desarrollo ni nada
≥ 2005. No ajusta ni corre ningún modelo.

Comprueba:
  1. Peticiones de paro (M2 v1.1): λ·(f_m − f_{m−12}) = λ·Σ ΔF; al inicio de una recuperación la forma de flujo da
     el signo observado (tasa interanual negativa con λ < 0) y la de stock (v1.0) el contrario.
  2. Criterio 8 (`gamma_fraction_criterion`): estricto, faltantes = fallo; pero si el llamador pasa como denominador
     los cortes CON coeficientes (como hace hoy `harness.coefficient_signs`), un corte sin ajuste deja de contar como
     fallo → el arnés v2.4 debe usar los cortes de `eval_window`.
  3. `harness.coefficient_signs` con todos los `expected_signs` en `decide: false` → `criterio_signos_cumple` = True
     de forma vacía (por eso A3-8 no puede usar esa clave).
  4. Regla de S-PIT-001 (`s_pit_001_triggered`): M0 se cancela (Δ_S = media ll(M2pr) − ll(M2fp)); con un NaN en d la
     función devuelve "no dispara" en silencio.
  5. Las predicciones P1-P11 de `pool_spec.md` §5b son copia literal del §4.2 del Estratega.

Ejecutar: .venv/bin/python tests/validation/specs_pool_v4_reaudit.py <salida.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.models import regime_components as C  # noqa: E402
from src.models import harness as H  # noqa: E402

OUT: dict = {}

# 1. flujo frente a stock -----------------------------------------------------------------------------------------
lam = -0.8
f = np.r_[-np.ones(12) * 1.5, np.ones(3) * 1.0]          # 12 meses de recesión y 3 de recuperación
m = len(f) - 1
lags = f[m - np.arange(13)]
flow = C.claims_factor_loading(lam) @ lags
stock = lam * f[m - np.arange(12)].mean()
rng = np.random.default_rng(0)
g = np.cumsum(rng.standard_normal(80))
eq = all(np.isclose(C.claims_factor_loading(lam) @ g[k - np.arange(13)], lam * np.diff(g)[k - 12:k].sum())
         for k in range(13, 80))
OUT["1_claims"] = {"flujo_inicio_recuperacion": float(flow), "stock_inicio_recuperacion": float(stock),
                   "flujo_negativo_stock_positivo": bool(flow < 0 < stock), "equivale_suma_de_cambios": bool(eq),
                   "state_dim": C.STRUCT.state_dim}

# 2. denominador del criterio 8 -----------------------------------------------------------------------------------
cuts = pd.period_range("2005-01", "2021-10", freq="M").to_timestamp()
gam = pd.DataFrame({k: 0.3 for k in C.TVTP.sign_coefs}, index=cuts)
gam.loc[cuts[:110], "G:gamma3"] = 0.0                    # 110/202 = 54 % pegado a 0 → debe fallar
gam_fit = gam.iloc[::2].copy()                           # la mitad de los cortes sin ajuste (sin coeficientes)
gam_fit.loc[gam_fit.index[:20], "G:gamma3"] = 0.0
gam_fit.loc[gam_fit.index[20:], "G:gamma3"] = 0.3
r_win = C.gamma_fraction_criterion(gam_fit, cuts)
r_own = C.gamma_fraction_criterion(gam_fit, gam_fit.index)
r_full = C.gamma_fraction_criterion(gam, cuts)
r_badidx = C.gamma_fraction_criterion(gam.set_axis(cuts.to_period("M")), cuts)
OUT["2_criterio8"] = {
    "completo_gamma3_frac": r_full["fraccion_umbral"]["G:gamma3"]["frac"], "completo_cumple": r_full["criterio_fraccion_cumple"],
    "denominador_eval_window_cumple": r_win["criterio_fraccion_cumple"],
    "denominador_eval_window_frac_gamma1": r_win["fraccion_umbral"]["G:gamma1"]["frac"],
    "denominador_cortes_ajustados_cumple": r_own["criterio_fraccion_cumple"],
    "denominador_cortes_ajustados_frac_gamma3": r_own["fraccion_umbral"]["G:gamma3"]["frac"],
    "indice_de_otro_tipo_cumple": r_badidx["criterio_fraccion_cumple"],
}

# 3. criterio_signos_cumple vacío con decide: false -----------------------------------------------------------------
cfg = SimpleNamespace(window=("2005-01-01", "2021-10-01"),
                      expected_signs={"m3_tvtp_g": {k: {"signo": "+", "decide": False} for k in C.TVTP.sign_coefs}})
diags = {"vintage": [{"refit_month": c, "model": "m3_tvtp_g",
                      "coef": {"gamma1": 0.0, "gamma2": 0.0, "gamma3": 0.0, "gamma4": 0.0}} for c in cuts]}
try:
    cs = H.coefficient_signs(diags, {"vintage": SimpleNamespace(kind="")}, cfg)
    v = cs.get("vintage/m3_tvtp_g", {})
    OUT["3_signos_vacio"] = {"criterio_signos_cumple_con_todos_gamma_0": v.get("criterio_signos_cumple"),
                             "error": v.get("error")}
except Exception as e:  # noqa: BLE001
    OUT["3_signos_vacio"] = {"excepcion": repr(e)}

# 4. S-PIT-001 ----------------------------------------------------------------------------------------------------
n = 300
ll0 = rng.gamma(2, 0.4, n)
ll2 = ll0 - rng.normal(0.03, 0.3, n)
ll2fp = ll2 + rng.normal(0.0, 0.05, n)
d_pr, d_fp = ll0 - ll2, ll0 - ll2fp
r4 = C.s_pit_001_triggered(d_pr, d_fp, -0.02, 0.08)
d_fp_nan = d_fp.copy(); d_fp_nan[5] = np.nan
d_big = d_fp_nan - 1.0                                    # diferencia enorme, pero con un NaN
r_nan = C.s_pit_001_triggered(d_pr, d_big, -0.02, 0.08)
OUT["4_spit"] = {"m0_se_cancela": bool(np.isclose(r4["delta"], np.mean(ll2 - ll2fp))),
                 "nan_con_delta_enorme_dispara": r_nan["dispara"], "nan_delta": r_nan["delta"]}

# 5. cita literal -------------------------------------------------------------------------------------------------
src = (ROOT / "docs/reviews/2026-10-24_estratega_macro_specs_pool.md").read_text().splitlines()
i = next(k for k, l in enumerate(src) if l.startswith("### 4.2"))
j = next(k for k, l in enumerate(src) if l.startswith("## 5."))
a = [l for l in src[i + 1:j]]
while a and not a[0].strip():
    a.pop(0)
while a and not a[-1].strip():
    a.pop()
pool = (ROOT / "docs/models/pool_spec.md").read_text()
blk = pool[pool.index("### 5b"):pool.index("**Controles antes de la etiqueta real:**", pool.index("### 5b"))]
b = [l[2:] if l.startswith("> ") else l[1:] for l in blk.splitlines() if l.startswith(">")]
OUT["5_cita_literal"] = {"lineas_estratega": len(a), "lineas_cita": len(b), "identica": a == b}

out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
txt = json.dumps(OUT, indent=2, ensure_ascii=False, default=str)
print(txt)
if out:
    out.write_text(txt)
