"""Validador (A POSTERIORI, declarado; no cambia el veredicto de P-DEV-INT4-ML v1.0): comprobaciones de fugas y
sensibilidades baratas sobre las mismas filas, pliegues y métricas que scripts/int4ml_corrida.py.
  0. reproducción de ΔAUC estratificada de la corrida oficial (determinista);
  1. fugas: año máximo de filas y de datos de indicadores usados; estandarización por pliegue; dejar un país fuera;
  2. signos del logit de INT-4 (muestra completa y por pliegue) frente a las restricciones de monotonía de M-GB;
  3. M-GB sin restricciones de monotonía; M-GB con el signo del Δ tipo real (C5/S2) invertido al del logit; M-GB con el
     Δ tipo real sin restricción (las tres con placebo z, 124 desplazamientos, reajustando ML y logit);
  4. M-L2 sin interacciones (sólo encogimiento L2) y M-L2 con interacciones y C = 100 (casi sin penalizar).
Salida: research/int/int4ml_validador.json. Uso: .venv/bin/python -m scripts.int4ml_validador
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.linear_model import LogisticRegression

from scripts.int4_corrida import COLS, NUCLEO, REPO, TODOS, _r, materias_primas
from scripts.int4_sensibilidad_liston import auc_estrat, boot
from src.intl import data as D
from src.intl import int4 as M
from src.intl import int4ml as ML
from src.intl import panel as P
from src.intl.procedencia import procedencia
from src.warehouse import db


class GBLibre(ML.GB):
    def __init__(self, n: int):
        super().__init__([0] * n)


class L2Sin:
    def fit(self, X, y):
        self.mu, self.sd = X.mean(0), X.std(0)
        self.sd[self.sd == 0] = 1.0
        self.m = LogisticRegression(C=1.0, max_iter=10000).fit((X - self.mu) / self.sd, y)
        return self

    def predict(self, X):
        return self.m.predict_proba((X - self.mu) / self.sd)[:, 1]


class L2C100(ML.L2Inter):
    def fit(self, X, y):
        self.m = LogisticRegression(C=100.0, max_iter=10000).fit(self._diseño(X, True), y)
        return self


def variantes(giro, nb, cols):
    cst = [ML.MONOTONIA[giro][c] for c in cols]
    real = "C5" if giro == "T1" else "S2"           # Δ tipo real: el signo del prerregistro va contra el logit
    flip = [-s if c == real else s for c, s in zip(cols, cst)]
    libre = [0 if c == real else s for c, s in zip(cols, cst)]
    return {"M-GB_sin_monotonia": lambda: GBLibre(nb + len(cols)),
            "M-GB_signo_real_del_logit": lambda: ML.GB([0] * nb + flip),
            "M-GB_real_sin_restriccion": lambda: ML.GB([0] * nb + libre),
            "M-L2_sin_interacciones": L2Sin, "M-L2_C100": lambda: L2C100(nb)}


def placebo_k(k, f_all, B1_all, pan, cols, fab):
    Xk = M.matriz(f_all, pan, cols, k)
    ok = np.isfinite(B1_all).all(axis=1) & np.isfinite(Xk).all(axis=1)
    y, g = f_all.y.to_numpy(float)[ok], f_all.pais.to_numpy()[ok]
    if y.sum() < 10 or (1 - y).sum() < 10:
        return None
    X = np.column_stack([B1_all[ok], Xk[ok]])
    return auc_estrat(y, ML.loco(fab, X, y, g), g) - auc_estrat(y, ML.loco(ML.Logit, X, y, g), g)


def main() -> None:
    proc = procedencia(exigir_limpio=False)
    con = D.connect()
    a = P.anual(con)
    extra = {}
    for v in ("hpnom", "money", "wage"):
        s = {c: D.load_dev(con, f"jst_{c.lower()}_{v}") for c in D.PAISES}
        s = pd.concat({c: x.set_axis(x.index.year) for c, x in s.items() if not x.empty})
        s.index.names = ["pais", "año"]
        extra[v] = s
    con.close()
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    años_pais = {c: set(a.xs(c, level=0)["rgdpmad"].dropna().index.astype(int)) for c in TODOS}
    primer = {c: min(v) for c, v in años_pais.items()}
    pan = M.paneles(a, pd.DataFrame(extra), NUCLEO, TODOS, materias_primas())
    oficial = json.load(open(REPO / "research" / "int" / "int4ml_resultado.json"))["contrastes"]
    res = {"procedencia": proc, "declarado": "a posteriori; no cambia el veredicto", "giros": {}}
    for giro in ("T1", "T2"):
        cols = COLS[giro]
        f_all = (M.obj_entrada(rec, años_pais, NUCLEO, 1, 1871, True) if giro == "T1"
                 else M.obj_salida(rec, años_pais, NUCLEO, 1, 1871, True))
        B1_all, X_all = M.liston(f_all, giro, rec, primer, pan), M.matriz(f_all, pan, cols)
        ok = np.isfinite(B1_all).all(axis=1) & np.isfinite(X_all).all(axis=1)
        f = f_all[ok].reset_index(drop=True)
        X = np.column_stack([B1_all[ok], X_all[ok]])
        y, g, t = f.y.to_numpy(float), f.pais.to_numpy(), f.t.to_numpy()
        nb = B1_all.shape[1]
        R = {}
        # 1. fugas
        años_dato = np.concatenate([f.t.to_numpy()] + ([f.pico.to_numpy()] if "S5" in cols else []))
        R["fugas"] = {"t_max": int(t.max()), "t_mas_h_max": int(t.max() + 1), "año_max_dato_indicador": int(años_dato.max()),
                      "panel_años_max": {c: int(pan["C2" if c == "S5" else {"S1": "C1", "S2": "C5", "S3": "C6"}.get(c, c)]
                                                .dropna(how="all").index.max()) for c in cols}}
        if "pico" in f:
            R["fugas"]["pico_mayor_que_t"] = int((f.pico > f.t).sum())
        c0 = np.unique(g)[0]
        m = ML.L2Inter(nb).fit(X[g != c0], y[g != c0])
        R["fugas"]["L2_mu_es_del_pliegue"] = bool(np.allclose(m.mu, X[g != c0].mean(0)) and
                                                   not np.allclose(m.mu, X.mean(0)))
        # 0. reproducción
        p_log = ML.loco(ML.Logit, X, y, g)
        a_log = auc_estrat(y, p_log, g)
        R["reproduccion"] = {}
        for c in ("M-L2", "M-GB"):
            p = ML.loco(ML.fabrica(c, giro, nb, cols), X, y, g)
            R["reproduccion"][c] = {"d_auc": auc_estrat(y, p, g) - a_log, "oficial": oficial[f"{c}|{giro}"]["estratificada"]["d_auc"]}
        # 2. signos del logit
        b = M.logit_fit(X, y)[1 + nb:]
        cst = [ML.MONOTONIA[giro][c] for c in cols]
        por = np.array([M.logit_fit(X[g != c], y[g != c])[1 + nb:] for c in np.unique(g)])
        R["signos"] = {c: {"restriccion": cst[i], "coef_logit_completo": float(b[i]),
                           "coincide": bool(np.sign(b[i]) == cst[i]),
                           "pliegues_con_signo_de_la_restriccion": int((np.sign(por[:, i]) == cst[i]).sum())}
                       for i, c in enumerate(cols)}
        # 3-4. variantes
        R["variantes"] = {}
        for nom, fab in variantes(giro, nb, cols).items():
            p = ML.loco(fab, X, y, g)
            e = boot(y, p, p_log, t, g, auc_estrat)
            R["variantes"][nom] = {"estratificada": e, "d_logloss": M.logloss(y, p) - M.logloss(y, p_log),
                                   "pendiente": M.calibracion(y, p)["pendiente"]}
            if nom.startswith("M-GB"):
                ds = Parallel(n_jobs=-1)(delayed(placebo_k)(k, f_all, B1_all, pan, cols, fab) for k in M.KS)
                R["variantes"][nom]["placebo"] = ML.z_placebo(e["d_auc"], np.array([d for d in ds if d is not None]))
            print(giro, nom, round(e["d_auc"], 4), e["ic95"], flush=True)
        res["giros"][giro] = R
    out = REPO / "research" / "int" / "int4ml_validador.json"
    out.write_text(json.dumps(_r(res), indent=1, ensure_ascii=False))
    print(json.dumps(_r({k: {"fugas": v["fugas"], "reproduccion": v["reproduccion"], "signos": v["signos"]}
                         for k, v in res["giros"].items()}), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
