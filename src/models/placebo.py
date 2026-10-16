"""Placebo PAREADO del arnés y tabla de potencia frente a fugas débiles (docs/models/harness.md §9b; Validador v1 M-5).

Diseño (fijado el 2026-10-16 ANTES de correrlo):
- Etiqueta oficial ≤ 2004 BARAJADA en bloques de 24 meses (`harness.placebo_data`); variables PIT reales (las 8 a
  priori del placebo de la base PIT); refit anual 1975-2004, embargo 6, L2 = 0,05, min_train 60.
- Base del placebo RICA: persistencia blanda (pers_*) **y dura** (one-hot pers_hard_*), para que una transformación
  legítima de la persistencia (control t−5) no cuente como fuga (especificidad).
- Columna sospechosa C (3 columnas). Incremento PAREADO (principal; diseño del Validador v1, M-5):
      pareado = log-loss(base + vars) − log-loss(base + vars + C), con la MISMA permutación del objetivo.
  Diagnóstico secundario: frente a un NULO de la misma dimensión (C barajada en bloques de 24 con otra permutación),
      pareado_nulo = log-loss(base + vars + C_nulo) − log-loss(base + vars + C).
  AJUSTE POST HOC (2026-10-16, anotado en el trial log): el diseño se fijó primero con `pareado_nulo` como principal;
  con UNA semilla (antes de correr la tabla) el control t−5 dio +0,13: un nulo de la misma dimensión sobreajusta y una
  columna redundante no, así que ese contraste no es específico. Se pasó a `pareado` (el del Validador) como regla.
  SEGUNDO AJUSTE POST HOC (misma semilla, antes de la tabla): con `pareado` el control t−5 seguía en +0,09 porque la
  L2 de la v1 (0,05·‖W‖² frente a la log-loss MEDIA) también encogía la persistencia de la base, y duplicarla relajaba
  la penalización. Ahora la L2 solo penaliza las variables añadidas; la persistencia (blanda y dura) de la base va
  sin penalizar (`fit_logit_masked`).
- Se publica también el placebo absoluto de la v1 (base + vars frente a base).
- REGLA COMPLEMENTARIA (preregistrada el 2026-10-16 ANTES de correr ningún placebo de un aspirante; propuesta del
  Validador v2, M2-5): **aviso de fuga** si, sobre las 20 semillas, la prueba de signo unilateral da p < 0,01 (≥ 15 de
  20 positivas) **o** t = media / (sd/√20) > 3. El aviso obliga a investigar la columna; no falla automáticamente.
  La regla principal (media > 0,02) no cambia.
- PLACEBO DE UN ASPIRANTE (`model_placebo`): con la especificación y la L2 DEL PROPIO modelo (no la L2 = 0,05 de esta
  tabla, que solo mide la potencia de ESTE regularizador): incremento pareado = log-loss(modelo sin las variables
  sospechosas) − log-loss(modelo con ellas), con la etiqueta barajada y las mismas permutaciones.

    .venv/bin/python -m src.models.placebo <salida.json>     # tabla de potencia completa (~minutos)
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

from scipy.optimize import minimize

from src.features.placebo import block_shuffle, predict_logit
from src.models import base as B
from src.models import harness as H
from src.models import metrics as M
from src.models.metrics import P_COLS, QUADS

PAIRED_TOL = 0.02
N_SEEDS = 20
WARN_SIGN_P = 0.01          # regla complementaria (M2-5): prueba de signo unilateral sobre las semillas…
WARN_T = 3.0                # …o t de la media > 3 → AVISO de fuga (investigar; no falla automáticamente)
PLACEBO_VARS = ("curve_10y3m", "payems_3m_ann", "indpro_3m_ann", "unrate_sahm", "headline_cpi_6m_ann", "ppi_yoy",
                "baa_spread", "ff_d12m")   # las 8 variables a priori del placebo de la base PIT
CAND = ("cand_a", "cand_b", "cand_c")
NULL = ("null_a", "null_b", "null_c")


def fit_logit_masked(X: np.ndarray, y: np.ndarray, k: int, lam: float, n_free: int) -> np.ndarray:
    """Logística multinomial con L2 = lam·‖W‖² (frente a la log-loss media) SOLO sobre las columnas ≥ n_free."""
    n, p = X.shape
    Xb = np.hstack([np.ones((n, 1)), X])
    Y = np.eye(k)[y]
    pen = np.zeros((p + 1, 1))
    pen[1 + n_free:] = lam

    def f(w):
        W = w.reshape(p + 1, k)
        Z = Xb @ W
        Z -= Z.max(axis=1, keepdims=True)
        lse = np.log(np.exp(Z).sum(axis=1))
        ll = -(Y * (Z - lse[:, None])).sum() / n
        P_ = np.exp(Z - lse[:, None])
        g = Xb.T @ (P_ - Y) / n + 2 * pen * W
        return ll + (pen * W ** 2).sum(), g.ravel()

    return minimize(f, np.zeros((p + 1) * k), jac=True, method="L-BFGS-B").x.reshape(p + 1, k)


class PlaceboLogit(B.Model):
    """Logística multinomial con base = persistencia blanda + dura SIN penalizar; L2 = 0,05 en el resto. Solo placebo."""
    uses_persistence = True

    def __init__(self, name, features=(), lam=0.05):
        self.name, self.features, self.lam = name, features, lam

    def _design(self, X):
        Z = X[B.PERS_COLS[1:] + B.PERS_HARD_COLS[1:]].to_numpy(float)
        if self.cols:
            Z = np.hstack([Z, (X[self.cols].to_numpy(float) - self.mu) / self.sd])
        return Z

    def fit(self, X, Y, y, info, sample_weight=None):
        self.cols = [c for c in X.columns if c not in B.PERS_COLS + B.PERS_HARD_COLS]
        F = X[self.cols].to_numpy(float)
        self.mu, self.sd = F.mean(axis=0), F.std(axis=0) + 1e-9
        self.W = fit_logit_masked(self._design(X), np.array([QUADS.index(v) for v in y]), 4, self.lam,
                                  n_free=len(B.PERS_COLS) - 1 + len(B.PERS_HARD_COLS) - 1)

    def predict_proba(self, X, info):
        return predict_logit(self.W, self._design(X))


# ------------------------------------------------------------------ columnas sospechosas (desde el objetivo barajado)
def leak_future(sd: float, k: int = 1):
    """Objetivo blando de t + k (k = 0: contemporáneo) + ruido N(0, sd)."""
    def f(tgt, rng):
        x = tgt[P_COLS[1:]].shift(-k)
        return pd.DataFrame(x.to_numpy() + rng.normal(0, sd, x.shape), index=x.index, columns=list(CAND))
    return f


def leak_lag(k: int):
    """Etiqueta dura de t − k en one-hot (k ≤ 4: fuga de calendario; k = 5: control SIN fuga = la persistencia)."""
    def f(tgt, rng):
        oh = pd.get_dummies(tgt["label_hard"]).reindex(columns=list(QUADS), fill_value=0).astype(float)
        x = oh[list(QUADS[1:])].shift(k)
        return pd.DataFrame(x.to_numpy(), index=x.index, columns=list(CAND))
    return f


def noise():
    """Sin fuga: ruido puro."""
    def f(tgt, rng):
        return pd.DataFrame(rng.normal(0, 1, (len(tgt), 3)), index=tgt.index, columns=list(CAND))
    return f


def _with_null(leak):
    def f(tgt, rng):
        C = leak(tgt, rng)
        order = block_shuffle(np.arange(len(C)), 24, rng)
        N = pd.DataFrame(C.to_numpy()[order], index=C.index, columns=list(NULL))
        return C.join(N)
    return f


def paired_skill(pit, seed: int, leak, record: bool = False) -> dict:
    """Una permutación: placebo absoluto (vars frente a base) e incremento pareado (C frente a C_nulo)."""
    data = H.placebo_data(pit, seed, leak=_with_null(leak))
    # las columnas con NaN (desplazamientos) no deben hacer de reloj: se rellenan con 0 en los dos brazos
    data.X[list(CAND + NULL)] = data.X[list(CAND + NULL)].fillna(0.0)
    for c in CAND + NULL:
        data.colinfo[c] = {"estado": "principal", "start": data.X.index.min()}
    reg = {"base": lambda: PlaceboLogit("base"), "vars": lambda: PlaceboLogit("vars", PLACEBO_VARS),
           "vars_null": lambda: PlaceboLogit("vars_null", PLACEBO_VARS + NULL),
           "vars_cand": lambda: PlaceboLogit("vars_cand", PLACEBO_VARS + CAND)}
    cfg = H.HarnessConfig(name="placebo_pareado", models=tuple(reg), modes=(data.mode,), test_start="1975-01",
                          refit_every=12, min_train_months=60, min_train_recessions=0, min_train_g_changes=0,
                          provisional_weighting="uno", baseline="vars", reference="base", epochs=())
    r = H.run(cfg, registry=reg, datas={data.mode: data}, record=record)
    m = r["report"]["modelos"]
    k = data.mode
    return {"seed": seed, "absoluto": m[f"{k}/base"]["logloss"] - m[f"{k}/vars"]["logloss"],
            "pareado": m[f"{k}/vars"]["logloss"] - m[f"{k}/vars_cand"]["logloss"],
            "pareado_nulo": m[f"{k}/vars_null"]["logloss"] - m[f"{k}/vars_cand"]["logloss"]}


def leak_rules(p) -> dict:
    """Regla principal (media > 0,02) y regla complementaria (aviso: signo unilateral p < 0,01 o t > 3)."""
    p = np.asarray(p, float)
    n = len(p)
    sd = p.std(ddof=1) if n > 1 else float("nan")
    t = float(p.mean() / (sd / np.sqrt(n))) if n > 1 and sd > 0 else float("nan")
    sp = M.sign_test_greater(int((p > 0).sum()), n)
    return {"fuga_detectada": bool(p.mean() > PAIRED_TOL), "signo_p_unilateral": sp, "t": t,
            "aviso_fuga": bool(sp < WARN_SIGN_P or (t == t and t > WARN_T))}


def evaluate(pit, leak, seeds=tuple(range(1, N_SEEDS + 1))) -> dict:
    rows = [paired_skill(pit, s, leak) for s in seeds]
    a, p = np.array([r["absoluto"] for r in rows]), np.array([r["pareado"] for r in rows])
    pn = np.array([r["pareado_nulo"] for r in rows])
    return {"n_semillas": len(rows), "pareado_media": float(p.mean()), "pareado_sd": float(p.std(ddof=1)),
            "pareado_frac_>0": float((p > 0).mean()), **leak_rules(p),
            "pareado_nulo_media": float(pn.mean()), "absoluto_media": float(a.mean()), "absoluto_regla_v1_falla": bool(a.mean() > PAIRED_TOL),
            "pareado": [round(float(x), 5) for x in p]}


def _named(model: B.Model, name: str) -> B.Model:
    model.name = name
    return model


def model_placebo(pit, make_without, make_with, seeds=tuple(range(1, N_SEEDS + 1)), test_start: str = "1975-01",
                  refit_every: int = 12, min_train_months: int = 60, record: bool = False) -> dict:
    """Placebo pareado de un ASPIRANTE con SU especificación y SU regularizador (M2-5). `make_without()` / `make_with()`
    devuelven el modelo sin y con las variables sospechosas (p. ej. M0 y M1, o M1 − v y M1). Etiqueta oficial ≤ 2004
    barajada en bloques de 24 meses, mismas permutaciones para los dos; reglas: `leak_rules`."""
    rows = []
    for seed in seeds:
        data = H.placebo_data(pit, seed)
        reg = {"sin": lambda: _named(make_without(), "sin"), "con": lambda: _named(make_with(), "con")}
        cfg = H.HarnessConfig(name="placebo_aspirante", models=("sin", "con"), modes=(data.mode,),
                              test_start=test_start, refit_every=refit_every, min_train_months=min_train_months,
                              min_train_recessions=0, min_train_g_changes=0, baseline="sin", epochs=())
        m = H.run(cfg, registry=reg, datas={data.mode: data}, record=record)["report"]["modelos"]
        rows.append(m[f"{data.mode}/sin"]["logloss"] - m[f"{data.mode}/con"]["logloss"])
    p = np.array(rows)
    return {"n_semillas": len(p), "pareado_media": float(p.mean()), "pareado_frac_>0": float((p > 0).mean()),
            **leak_rules(p), "pareado": [round(float(x), 5) for x in p]}


CASES = {"sin_fuga_ruido": noise(),
         "control_t-5_sin_fuga": leak_lag(5),
         "futura_t+1_sd1": leak_future(1.0), "futura_t+1_sd2": leak_future(2.0),
         "contemporanea_t_sd1": leak_future(1.0, 0), "contemporanea_t_sd2": leak_future(2.0, 0),
         "contemporanea_t_sd4": leak_future(4.0, 0),
         "calendario_t-4": leak_lag(4), "calendario_t-1": leak_lag(1)}


def main() -> None:
    dest = sys.argv[1]
    os.environ.setdefault("FKB_TRIALS_DIR", os.path.join(os.path.dirname(os.path.abspath(dest)), "trials_tmp"))
    pit = H.PITData("vintage")
    out = {"regla": {"PAIRED_TOL": PAIRED_TOL, "N_SEEDS": N_SEEDS}}
    for name, lk in CASES.items():
        t = time.time()
        out[name] = evaluate(pit, lk)
        out[name]["seg"] = round(time.time() - t, 1)
        print(name, {k: v for k, v in out[name].items() if k != "pareado"}, flush=True)
        with open(dest, "w") as fh:
            json.dump(out, fh, indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
