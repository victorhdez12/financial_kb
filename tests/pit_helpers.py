"""Utilidades de los tests de fugas de la base point-in-time (tests/test_pit_leaks.py).

- `truncated_warehouse`: copia en memoria del warehouse con solo lo que se sabía en t.
- `synthetic_warehouse`: warehouse en memoria con series inventadas (señal plantada).
- `wf_skill`: logística multinomial con L2 en walk-forward con embargo; habilidad = log-loss del modelo de
  solo persistencia − log-loss del modelo con variables (en nats; > 0 = las variables aportan).
No es el arnés de backtest (entregable 3): solo comprueba que la tubería no fabrica ni esconde habilidad.
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
from scipy.optimize import minimize

from src.warehouse.build import VIEWS_SQL


def _finish(mem, built_at) -> duckdb.DuckDBPyConnection:
    mem.execute(f"create table build_log as select timestamp '{pd.Timestamp(built_at):%Y-%m-%d %H:%M:%S}' as built_at")
    mem.execute(VIEWS_SQL)
    return mem


def truncated_warehouse(con, t: pd.Timestamp, sids: list[str]) -> duckdb.DuckDBPyConnection:
    """Observaciones con fecha ≤ t (última vintage) y vintages con realtime_start ≤ t (realtime_end abierto si
    era posterior a t): el warehouse tal como habría estado en t, salvo revisiones posteriores de la última
    vintage, que el modo latest_truncated usa a propósito."""
    obs = con.execute(
        """select date, value, series_id, source, realtime_start,
                  case when realtime_end > ? then null else realtime_end end as realtime_end
           from observations where series_id in (select unnest(?))
             and ((realtime_start is null and date <= ?) or (realtime_start is not null and realtime_start <= ?))""",
        [t, sids, t, t]).df()
    cat = con.execute("select * from catalog where series_id in (select unnest(?))", [sids]).df()
    mem = duckdb.connect(":memory:")
    mem.register("o", obs)
    mem.execute("""create table observations as select cast(date as date) as date, value, series_id, source,
                   cast(realtime_start as date) as realtime_start, cast(realtime_end as date) as realtime_end
                   from o""")
    mem.register("c", cat)
    mem.execute("create table catalog as select * from c")
    return _finish(mem, t)


def synthetic_warehouse(obs: pd.DataFrame, catalog: pd.DataFrame, built_at) -> duckdb.DuckDBPyConnection:
    mem = duckdb.connect(":memory:")
    obs = obs.reindex(columns=["date", "value", "series_id", "source", "realtime_start", "realtime_end"])
    for c in ("date", "realtime_start", "realtime_end"):
        obs[c] = pd.to_datetime(obs[c])
    mem.register("o", obs)
    mem.execute("""create table observations as select cast(date as date) as date, cast(value as double) as value,
                   series_id, source, cast(realtime_start as date) as realtime_start,
                   cast(realtime_end as date) as realtime_end from o""")
    mem.register("c", catalog)
    mem.execute("create table catalog as select * from c")
    return _finish(mem, built_at)


# ------------------------------------------------------------------ logística multinomial
def fit_logit(X: np.ndarray, y: np.ndarray, k: int, lam: float = 1.0) -> np.ndarray:
    n, p = X.shape
    Xb = np.hstack([np.ones((n, 1)), X])
    Y = np.eye(k)[y]

    def f(w):
        W = w.reshape(p + 1, k)
        Z = Xb @ W
        Z -= Z.max(axis=1, keepdims=True)
        lse = np.log(np.exp(Z).sum(axis=1))
        ll = -(Y * (Z - lse[:, None])).sum() / n
        P = np.exp(Z - lse[:, None])
        g = Xb.T @ (P - Y) / n
        reg = lam / n * (W[1:] ** 2).sum()
        g[1:] += 2 * lam / n * W[1:]
        return ll + reg, g.ravel()

    return minimize(f, np.zeros((p + 1) * k), jac=True, method="L-BFGS-B").x.reshape(p + 1, k)


def predict_logit(W: np.ndarray, X: np.ndarray) -> np.ndarray:
    Z = np.hstack([np.ones((len(X), 1)), X]) @ W
    Z -= Z.max(axis=1, keepdims=True)
    P = np.exp(Z)
    return P / P.sum(axis=1, keepdims=True)


def wf_skill(base: np.ndarray, feats: np.ndarray, y: np.ndarray, months: pd.DatetimeIndex,
             first_test_year: int, embargo: int = 6, k: int = 4) -> float:
    """Walk-forward anual con ventana expansiva y embargo de `embargo` meses. Devuelve la mejora media de
    log-loss (nats) del modelo base + variables frente al modelo solo base, fuera de muestra."""
    ll_b, ll_f = [], []
    for year in range(first_test_year, months.year.max() + 1):
        test = months.year == year
        train = months < pd.Timestamp(f"{year}-01-01") - pd.DateOffset(months=embargo)
        if train.sum() < 60 or test.sum() == 0:
            continue
        mu, sd = feats[train].mean(axis=0), feats[train].std(axis=0) + 1e-9
        F = (feats - mu) / sd
        Xb, Xf = base, np.hstack([base, F])
        wb, wf = fit_logit(Xb[train], y[train], k), fit_logit(Xf[train], y[train], k)
        pb, pf = predict_logit(wb, Xb[test]), predict_logit(wf, Xf[test])
        idx = np.arange(test.sum())
        ll_b += list(-np.log(np.clip(pb[idx, y[test]], 1e-4, 1)))
        ll_f += list(-np.log(np.clip(pf[idx, y[test]], 1e-4, 1)))
    return float(np.mean(ll_b) - np.mean(ll_f))


def persistence_onehot(y: np.ndarray, lag: int = 5, k: int = 4) -> np.ndarray:
    """Etiqueta de t − lag en one-hot (k − 1 columnas). Las primeras `lag` filas quedan a cero."""
    out = np.zeros((len(y), k - 1))
    for i in range(lag, len(y)):
        if y[i - lag] > 0:
            out[i, y[i - lag] - 1] = 1.0
    return out
