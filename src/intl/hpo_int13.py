"""HPO-INT13 (EXPLORATORIO): ajuste de hiperparámetros ANIDADO del XGBoost por paquetes de INT-13.

Plan fijado antes de correr: docs/int/HPO_INT13_exploratorio.md (§1-§6). Reutiliza los rasgos, objetivos, base logit,
monotonías y métricas de src/intl/int13.py (no los cambia).

- Bucle EXTERNO = el de INT-13: V1 dejar un país fuera (18 pliegues) y V2 temporal (objetivo ≤ 1989-12 → 1990-2004).
- Bucle INTERNO (solo con el entreno del pliegue externo): V1 → 3 grupos de países (de los 17 de entreno); V2 → 2
  cortes walk-forward con embargo dentro de ≤ 1989. Elige (configuración, nº de árboles) por log-loss interna apilada.
- Espacio: 20 configuraciones (la 0 = la de INT-13) × 10…300 árboles; mismas configuraciones en todos los pliegues.

Funciones puras (los datos entran ya construidos con int13.construir); la carga y la puerta están en
scripts/hpo_int13_corrida.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.intl import int13 as M

SEMILLA_HPO = 20261104
OBJ_HPO = ["E1_12", "E2", "E3"]           # los tres objetivos a 12 meses (E1-6 no se ajusta)
N_CONFIGS = 20                            # presupuesto: 1 (INT-13) + 19 al azar
MAX_RONDAS, MIN_RONDAS = 300, 10
K_INTERNO = 3                             # grupos de países en el bucle interno de V1
CORTES_V2_INTERNOS = [("1974-12-31", "1975-01-31"), ("1981-12-31", "1982-01-31")]   # (fin objetivo entreno, val desde)
PLACEBO_REPS = 10
BLOQUE_PLACEBO = 24
DEFAULT = {"eta": 0.05, "max_depth": 2, "min_child_weight": 10.0, "subsample": 0.8, "colsample_bytree": 1.0,
           "lambda": 5.0, "alpha": 0.0}
FIJOS = {"objective": "binary:logistic", "tree_method": "hist", "max_bin": 64, "seed": M.SEMILLA, "nthread": 1,
         "verbosity": 0, "eval_metric": "logloss"}
MODELOS = [*M.PAQUETES, M.COMBO]


# ---------------------------------------------------------------- espacio de búsqueda
def muestrear_configs(n: int = N_CONFIGS, seed: int = SEMILLA_HPO) -> list[dict]:
    """Configuración 0 = la de INT-13; el resto, búsqueda al azar en el espacio declarado (§2 del plan)."""
    rng = np.random.default_rng(seed)
    lu = lambda a, b: float(np.exp(rng.uniform(np.log(a), np.log(b))))  # noqa: E731
    out = [dict(DEFAULT)]
    for _ in range(n - 1):
        out.append({"eta": lu(0.02, 0.3), "max_depth": int(rng.choice([1, 2, 3, 4, 6])),
                    "min_child_weight": lu(1.0, 100.0), "subsample": float(rng.uniform(0.5, 1.0)),
                    "colsample_bytree": float(rng.uniform(0.5, 1.0)), "lambda": lu(0.1, 100.0),
                    "alpha": 0.0 if rng.random() < 0.5 else lu(0.01, 10.0)})
    return out


# ---------------------------------------------------------------- pliegues internos
def pliegues_internos_loco(tr: pd.DataFrame, k: int = K_INTERNO, seed: int = SEMILLA_HPO) -> list:
    """k grupos de países del entreno externo (posiciones de fila)."""
    paises = np.array(sorted(tr.pais.unique()))
    rng = np.random.default_rng(seed + len(paises) + sum(ord(c) for c in "".join(paises)))
    grupos = np.array_split(rng.permutation(paises), k)
    p = tr.pais.to_numpy()
    return [(np.flatnonzero(~np.isin(p, g)), np.flatnonzero(np.isin(p, g))) for g in grupos]


def pliegues_internos_temporal(tr: pd.DataFrame, h: int) -> list:
    """Cortes walk-forward con embargo: entreno con objetivo acabado ≤ corte; validación desde el mes siguiente."""
    fin_obj = tr.fecha + pd.offsets.MonthEnd(h)
    out = []
    for corte, desde in CORTES_V2_INTERNOS:
        a = np.flatnonzero((fin_obj <= pd.Timestamp(corte)).to_numpy())
        b = np.flatnonzero((tr.fecha >= pd.Timestamp(desde)).to_numpy())
        out.append((a, b))
    return out


# ---------------------------------------------------------------- búsqueda interna
def _dm(X, y, m):
    import xgboost as xgb
    return xgb.DMatrix(X, label=y, base_margin=m, missing=np.nan)


def _params(cfg: dict, mono: list[int]) -> dict:
    return {**FIJOS, **cfg, "monotone_constraints": "(" + ",".join(str(int(v)) for v in mono) + ")"}


def curvas_internas(tr: pd.DataFrame, obj: str, cols: list[str], pliegues: list, cfgs: list[dict],
                    max_rondas: int = MAX_RONDAS) -> tuple[np.ndarray, int]:
    """Suma de la log-loss de validación (por fila) en cada ronda, apilando pliegues internos: matriz configs × rondas,
    y el nº de filas de validación usadas."""
    import xgboost as xgb
    y = tr[f"y_{obj}"].to_numpy(float)
    Xb, X = tr[M.BASE[obj]].to_numpy(float), tr[cols].to_numpy(float)
    mono = M.mono_de(obj, cols)
    S = np.zeros((len(cfgs), max_rondas))
    n_val = 0
    for a, b in pliegues:
        if len(a) == 0 or len(b) == 0 or np.unique(y[a]).size < 2:
            continue
        mb = M.base_fit(Xb[a], y[a])
        dtr, dva = _dm(X[a], y[a], M.base_margen(mb, Xb[a])), _dm(X[b], y[b], M.base_margen(mb, Xb[b]))
        for i, cfg in enumerate(cfgs):
            ev: dict = {}
            xgb.train(_params(cfg, mono), dtr, num_boost_round=max_rondas, evals=[(dva, "v")], evals_result=ev,
                      verbose_eval=False)
            S[i] += np.asarray(ev["v"]["logloss"]) * len(b)
        n_val += len(b)
    return S, n_val


def elegir(S: np.ndarray, n_val: int, min_rondas: int = MIN_RONDAS) -> dict:
    """Mejor (configuración, nº de árboles) por log-loss interna apilada; también la de INT-13 (config 0, 100 árboles)."""
    if n_val == 0:
        return {"cfg": 0, "rondas": M.N_ARBOLES, "ll_interna": np.nan, "ll_interna_default": np.nan,
                "por_config": []}
    L = S / n_val
    sub = L[:, min_rondas - 1:]
    i, j = np.unravel_index(np.argmin(sub), sub.shape)
    por_cfg = [{"cfg": k, "rondas": int(np.argmin(sub[k]) + min_rondas), "ll_interna": float(sub[k].min())}
               for k in range(len(L))]
    return {"cfg": int(i), "rondas": int(j + min_rondas), "ll_interna": float(sub[i, j]),
            "ll_interna_default": float(L[0, min(M.N_ARBOLES, L.shape[1]) - 1]), "por_config": por_cfg}


def tarea(tr: pd.DataFrame, te: pd.DataFrame, obj: str, pq: str, cfgs: list[dict], tipo: str,
          max_rondas: int = MAX_RONDAS) -> dict:
    """Un pliegue externo × un paquete: búsqueda interna, reajuste con todo el entreno externo y margen en `te` de
    (a) el XGBoost ajustado y (b) el de INT-13 (config fija, 100 árboles)."""
    import xgboost as xgb
    cols = M.PAQUETES[pq]
    tr = tr.reset_index(drop=True)
    pl = pliegues_internos_loco(tr) if tipo == "loco" else pliegues_internos_temporal(tr, M.OBJETIVOS[obj])
    S, n_val = curvas_internas(tr, obj, cols, pl, cfgs, max_rondas)
    sel = elegir(S, n_val)
    y = tr[f"y_{obj}"].to_numpy(float)
    mb = M.base_fit(tr[M.BASE[obj]].to_numpy(float), y)
    m_tr, m_te = M.base_margen(mb, tr[M.BASE[obj]].to_numpy(float)), M.base_margen(mb, te[M.BASE[obj]].to_numpy(float))
    X, Xte = tr[cols].to_numpy(float), te[cols].to_numpy(float)
    mono = M.mono_de(obj, cols)
    bst = xgb.train(_params(cfgs[sel["cfg"]], mono), _dm(X, y, m_tr), num_boost_round=sel["rondas"])
    z_hpo = bst.predict(xgb.DMatrix(Xte, base_margin=m_te, missing=np.nan), output_margin=True)
    z_def = M.xgb_margen(M.xgb_fit(X, y, m_tr, mono), Xte, m_te)       # exactamente el XGBoost de INT-13
    return {"pq": pq, "sel": sel, "z_hpo": z_hpo, "z_def": z_def, "n_val_interno": n_val}


# ---------------------------------------------------------------- logit con los rasgos del paquete (listón extra)
def logit_paquete(tr: pd.DataFrame, te: pd.DataFrame, obj: str, cols: list[str]) -> np.ndarray:
    """Logit sin penalizar con base + rasgos del paquete (estandarizados con el entreno; NaN → media del entreno).
    Devuelve el margen en `te`."""
    vs = list(dict.fromkeys([*M.BASE[obj], *cols]))
    A, B = tr[vs].to_numpy(float), te[vs].to_numpy(float)
    mu = np.nanmean(A, axis=0)
    mu = np.where(np.isfinite(mu), mu, 0.0)
    A, B = np.where(np.isnan(A), mu, A), np.where(np.isnan(B), mu, B)
    sd = A.std(axis=0)
    keep = sd > 0
    m = {"mu": mu[keep], "sd": sd[keep], "b": M.M4.logit_fit((A[:, keep] - mu[keep]) / sd[keep],
                                                             tr[f"y_{obj}"].to_numpy(float))}
    return M.base_margen(m, B[:, keep])


# ---------------------------------------------------------------- un bucle externo completo
def pliegues_externos(S: pd.DataFrame, obj: str, tipo: str) -> list:
    if tipo == "loco":
        out = []
        for c in sorted(S.pais.unique()):
            tr, te = S[S.pais != c], S[S.pais == c]
            if tr[f"y_{obj}"].nunique() >= 2 and not te.empty:
                out.append((c, tr, te))
        return out
    h = M.OBJETIVOS[obj]
    return [("V2", S[(S.fecha + pd.offsets.MonthEnd(h)) <= M.CORTE_TEMPORAL], S[S.fecha >= M.PRUEBA_DESDE])]


def evaluar_externo(S: pd.DataFrame, obj: str, tipo: str, cfgs: list[dict], n_jobs: int = 1,
                    max_rondas: int = MAX_RONDAS) -> tuple[pd.DataFrame, list]:
    """Predicciones fuera de muestra apiladas (columnas p_<modelo>) y el registro de pruebas internas."""
    from joblib import Parallel, delayed
    pl = pliegues_externos(S, obj, tipo)
    jobs = [(k, pq) for k in range(len(pl)) for pq in M.PAQUETES]
    res = Parallel(n_jobs=n_jobs, backend="loky")(
        delayed(tarea)(pl[k][1], pl[k][2], obj, pq, cfgs, tipo, max_rondas) for k, pq in jobs)
    por = {(k, r["pq"]): r for (k, _), r in zip(jobs, res)}
    partes, registro = [], []
    for k, (nombre, tr, te) in enumerate(pl):
        y = tr[f"y_{obj}"].to_numpy(float)
        mb = M.base_fit(tr[M.BASE[obj]].to_numpy(float), y)
        m_te = M.base_margen(mb, te[M.BASE[obj]].to_numpy(float))
        out = {"clima": np.full(len(te), np.clip(y.mean(), 1e-6, 1 - 1e-6)), "base": M._sig(m_te)}
        corr = {"hpo": [], "def": [], "lgt": []}
        for pq, cols in M.PAQUETES.items():
            r = por[(k, pq)]
            z_l = logit_paquete(tr, te, obj, cols)
            for fam, z in (("hpo", r["z_hpo"]), ("def", r["z_def"]), ("lgt", z_l)):
                out[f"{fam}_{pq}"] = M._sig(z)
                corr[fam].append(z - m_te)
            s = r["sel"]
            registro.append({"objetivo": obj, "validacion": tipo, "pliegue": nombre, "paquete": pq,
                             "cfg_elegida": s["cfg"], "rondas_elegidas": s["rondas"], "ll_interna": s["ll_interna"],
                             "ll_interna_default": s["ll_interna_default"], "n_val_interno": r["n_val_interno"],
                             "por_config": s["por_config"]})
        for fam in corr:
            out[f"{fam}_{M.COMBO}"] = M._sig(m_te + np.mean(corr[fam], axis=0))
        partes.append(te[["pais", "fecha", f"y_{obj}"]].assign(**{f"p_{a}": v for a, v in out.items()}))
    P = pd.concat(partes, ignore_index=True).rename(columns={f"y_{obj}": "y"})
    return P, registro


# ---------------------------------------------------------------- comparaciones
def comparaciones() -> dict:
    """nombre → (modelo, listón). F1 = hpo frente a base; F2 = hpo frente a def (ganancia del ajuste)."""
    c = {"base_vs_clima": ("base", "clima")}
    for m in MODELOS:
        c[f"hpo_{m}_vs_base"] = (f"hpo_{m}", "base")
        c[f"hpo_{m}_vs_def"] = (f"hpo_{m}", f"def_{m}")
        c[f"hpo_{m}_vs_lgt"] = (f"hpo_{m}", f"lgt_{m}")
        c[f"def_{m}_vs_base"] = (f"def_{m}", "base")
        c[f"lgt_{m}_vs_base"] = (f"lgt_{m}", "base")
    return c


def dll_puntual(P: pd.DataFrame, mod: str, lis: str) -> float:
    y = P["y"].to_numpy(float)
    return float((M.ll_filas(y, P[f"p_{mod}"].to_numpy()) - M.ll_filas(y, P[f"p_{lis}"].to_numpy())).mean())


# ---------------------------------------------------------------- placebo
def permutar_bloques(S: pd.DataFrame, obj: str, seed: int, bloque: int = BLOQUE_PLACEBO) -> pd.DataFrame:
    """Objetivo permutado por bloques DENTRO de cada país: las filas del país (en orden de fecha) se cortan en bloques
    de `bloque` filas consecutivas y se baraja el orden de los bloques (desplazamiento circular al azar antes de
    cortar). Conserva el nº de eventos y la persistencia por país; rompe la relación rasgo-objetivo."""
    rng = np.random.default_rng(seed)
    S = S.copy()
    col = f"y_{obj}"
    for c in sorted(S.pais.unique()):
        ix = S.index[S.pais == c][np.argsort(S.loc[S.pais == c, "fecha"].to_numpy(), kind="stable")]
        y = np.roll(S.loc[ix, col].to_numpy(), int(rng.integers(0, len(ix))))
        bl = [y[i:i + bloque] for i in range(0, len(y), bloque)]
        S.loc[ix, col] = np.concatenate([bl[i] for i in rng.permutation(len(bl))])
    return S
