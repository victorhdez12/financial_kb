"""Utilidades de los tests de fugas de la base point-in-time (tests/test_pit_leaks.py).

- `truncated_warehouse`: copia en memoria del warehouse (o de la instantánea) con solo lo que se sabía en t.
- `synthetic_warehouse`: warehouse en memoria con series inventadas (señal plantada).
- El walk-forward y el placebo están en src/features/placebo.py (reutilizables por el arnés).
"""
from __future__ import annotations

import duckdb
import pandas as pd

from src.features.placebo import fit_logit, persistence_onehot, predict_logit, wf_skill  # noqa: F401
from src.warehouse.build import VIEWS_SQL


def _finish(mem, built_at) -> duckdb.DuckDBPyConnection:
    mem.execute(f"create table build_log as select timestamp '{pd.Timestamp(built_at):%Y-%m-%d %H:%M:%S}' as built_at")
    mem.execute(VIEWS_SQL)
    return mem


def truncated_warehouse(con, t: pd.Timestamp, sids: list[str]) -> duckdb.DuckDBPyConnection:
    """Observaciones con fecha ≤ t (última vintage) y vintages con realtime_start ≤ t."""
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
