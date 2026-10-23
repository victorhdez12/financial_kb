"""Matriz de variables point-in-time para el nowcast de régimen EE. UU. (docs/models/pit_base.md, v0.4).

Para cada fecha de decisión t (último día hábil del mes, calendario federal de EE. UU.; ficha de la etiqueta §9)
devuelve el valor de cada variable de la LISTA BLANCA (research/pit_whitelist.yaml) usando solo lo publicado
hasta t, según el calendario (research/pit_calendar.yaml, src/features/calendar.py).

Dos modos (Validador M-4; decisión B del usuario: `vintage` es el principal, `latest_truncated` la sensibilidad):
- `vintage`: donde hay vintages (ALFRED/RTDSM/features/raw/alfred), la serie tal como se publicó en t; fuera del
  archivo, o en variables declaradas `latest_truncated`, el modo siguiente. El linaje marca el modo de cada celda.
- `latest_truncated`: última vintage truncada por la fecha de publicación de cada observación.

La matriz OFICIAL se construye solo desde la instantánea congelada de entradas (FROZEN, read_snapshot), nunca desde el
warehouse vivo. Barreras: lista blanca, `pit_role = observed`, sin raíces prohibidas y `assert_no_forbidden` al final.

Salida (no va al warehouse), en <FIN_DATA_ROOT>/features/: pit_us_v<versión>_<modo>.parquet (+ variante
vintage_filadelfia_prudente), linaje, baseline_persistence_v<versión>_<modo>.parquet (misma muestra en los dos modos)
y pit_us_v<versión>.meta.json.

    .venv/bin/python -m src.features.pit --freeze   # warehouse vivo + raw → instantánea (no toca una versión congelada)
    .venv/bin/python -m src.features.pit            # matriz oficial desde la instantánea
    .venv/bin/python -m src.features.pit --live     # seguimiento desde el warehouse vivo (*_live)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import yaml
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessMonthEnd

import duckdb

from src.features.calendar import (CAL_PATH, NEVER, CalEntry, VintageSet, availability, load_calendar,
                                   load_vintage_set)
from src.labels import regime_us as R
from src.regime.asof import infer_freq, period_end
from src.regime.features import regularize, sahm
from src.warehouse import db
from src.warehouse.build import VIEWS_SQL

REPO = Path(__file__).resolve().parents[2]
WL_PATH = REPO / "research" / "pit_whitelist.yaml"
VERSION = "0.4"                # v0.4 CANDIDATA (2026-10-23); la v0.3 sigue congelada (FROZEN) para M1 v1
MODES = ("vintage", "latest_truncated")
GRID_START = "1950-01-01"
# un valor deja de valer (NaN) si su periodo de referencia terminó hace más de estos días (series cortadas)
STALE_DAYS = {"D": 45, "W": 45, "M": 130, "Q": 280, "A": 600}
VINTAGE_LOOKBACK = pd.DateOffset(years=6)   # historia de la vintage necesaria para cualquier transformación


def out_dir() -> Path:
    return db.DATA_ROOT / "features"


# ------------------------------------------------------------------ transformaciones (índice de observación)
def _ppy(s: pd.Series) -> int:
    return {"D": 252, "W": 52, "M": 12, "Q": 4, "A": 1}[infer_freq(s.index)]


def t_level(s, **_):
    return s


def t_log_diff(s, k: int, **_):
    return 100 * np.log(s / s.shift(k))


def t_log_diff_ann(s, k: int, **_):
    return 100 * np.log(s / s.shift(k)) * (_ppy(s) / k)


def t_pct_ann(s, k: int, **_):
    return ((s / s.shift(k)) ** (_ppy(s) / k) - 1) * 100


def t_diff(s, k: int, **_):
    return s - s.shift(k)


def t_sahm(s, **_):
    return sahm(s)


def t_rolling_mean(s, n: int, **_):
    return s.rolling(n, min_periods=n).mean()


def t_rolling_log_yoy(s, n: int, **_):
    m = s.rolling(n, min_periods=n).mean()
    return 100 * np.log(m / m.shift(_ppy(s)))


TRANSFORMS: dict[str, Callable] = {
    "level": t_level, "log_diff": t_log_diff, "log_diff_ann": t_log_diff_ann, "pct_ann": t_pct_ann,
    "diff": t_diff, "sahm": t_sahm, "rolling_mean": t_rolling_mean, "rolling_log_yoy": t_rolling_log_yoy,
}


# ------------------------------------------------------------------ derivadas (columnas en la rejilla mensual)
def zexp(x: pd.Series, zmin: int) -> pd.Series:
    """z-score expansivo: solo valores de la trayectoria PIT hasta t."""
    m = x.expanding(min_periods=zmin).mean()
    s = x.expanding(min_periods=zmin).std()
    return (x - m) / s


def d_zmean(df, cols, wl, spec):
    z = pd.concat([zexp(df[c], wl["zscore_min_meses"]) for c in cols], axis=1)
    return z.mean(axis=1).where(z.notna().sum(axis=1) >= spec.get("min_entradas", len(cols)))


def _rolling_prev(x: pd.Series, n: int, how: str) -> pd.Series:
    """Estadístico de los n valores PIT ANTERIORES a t (t−n … t−1); exige el 90 % de la ventana."""
    r = x.shift(1).rolling(n, min_periods=int(0.9 * n))
    return r.median() if how == "median" else r.mean()


def d_trend_zmean(df, cols, wl, spec):
    """Versión unilateral de G (ficha §3): para cada entrada, (g − mediana de los 120 meses hasta t) / (1,4826 · MAD
    expansiva de esa desviación); media de las disponibles."""
    n, mmin = wl["tendencia_meses"], wl["mad_min_meses"]
    zs = []
    for c in cols:
        g = df[c]
        dev = g - g.rolling(n, min_periods=int(0.9 * n)).median()
        mad = dev.expanding(min_periods=mmin).apply(lambda a: np.nanmedian(np.abs(a - np.nanmedian(a))), raw=True)
        zs.append(dev / (1.4826 * mad))
    z = pd.concat(zs, axis=1)
    return z.mean(axis=1).where(z.notna().sum(axis=1) >= spec.get("min_entradas", len(cols)))


def d_hysteresis_state(df, cols, wl, spec):
    """+1 / −1 cuando growth_rt pasa de ±k·σ (σ expansiva de growth_rt) durante `confirmación` meses seguidos;
    −1 inmediato si Sahm ≥ 0,5; si no, se mantiene el estado (0 hasta el primer cambio)."""
    g, sh = df[cols[0]], df[cols[1]]
    band = wl["histeresis_sigma"] * g.expanding(min_periods=60).std()
    conf = wl["histeresis_confirmacion"]
    state, up, down, out = 0.0, 0, 0, []
    for gv, bv, sv in zip(g.to_numpy(), band.to_numpy(), sh.to_numpy()):
        if np.isnan(gv) or np.isnan(bv):
            out.append(np.nan)
            up = down = 0
            continue
        up = up + 1 if gv > bv else 0
        down = down + 1 if gv < -bv else 0
        if not np.isnan(sv) and sv >= 0.5:
            state = -1.0
        elif up >= conf:
            state = 1.0
        elif down >= conf:
            state = -1.0
        out.append(state)
    return pd.Series(out, index=df.index)


def d_core_pressure(df, cols, wl, spec):
    parts = pd.concat([df[cols[0]], df[cols[1]], df[cols[2]] - wl["salario_productividad_pp"]], axis=1)
    return parts.mean(axis=1).where(parts.notna().sum(axis=1) >= spec.get("min_entradas", 3))


def d_curve_regime(df, cols, wl, spec):
    """Curva en 4 estados (Δ3m): sin cambio si |Δ(10a − 3m)| < umbral; si no, steepening/flattening por el signo de
    Δcurva y bear/bull por el signo del tramo que más se mueve. Devuelve el indicador del estado `regimen`."""
    d10, d3 = df[cols[0]].diff(3), df[cols[1]].diff(3)
    dc = d10 - d3
    thr = wl["curva_umbral_pb"] / 100
    leg = d10.where(d10.abs() >= d3.abs(), d3)
    states = {"bear_steep": (dc > thr) & (leg > 0), "bull_steep": (dc > thr) & (leg <= 0),
              "bear_flat": (dc < -thr) & (leg > 0), "bull_flat": (dc < -thr) & (leg <= 0)}
    return _flag(states[spec["regimen"]], d10, d3)


def _flag(cond, *xs):
    ok = pd.concat(xs, axis=1).notna().all(axis=1)
    return cond.astype(float).where(ok)


DERIVED: dict[str, Callable] = {
    "zmean": d_zmean,
    "trend_zmean": d_trend_zmean,
    "hysteresis_state": d_hysteresis_state,
    "core_pressure": d_core_pressure,
    "curve_regime": d_curve_regime,
    "gap_median_prev": lambda df, c, wl, sp: df[c[0]] - _rolling_prev(df[c[0]], wl["tendencia_meses"], "median"),
    "gap_mean_prev": lambda df, c, wl, sp: df[c[0]] - _rolling_prev(df[c[0]], wl["tendencia_meses"], "mean"),
    "log_ratio_x100": lambda df, c, wl, sp: 100 * np.log(df[c[0]] / df[c[1]]),
    "curve": lambda df, c, wl, sp: df[c[0]].combine_first(df[c[1]] - df[c[2]]),
    "diff3": lambda df, c, wl, sp: df[c[0]] - df[c[0]].shift(3),
    "diff6": lambda df, c, wl, sp: df[c[0]] - df[c[0]].shift(6),
    "diff12": lambda df, c, wl, sp: df[c[0]] - df[c[0]].shift(12),
    # v0.4: mínimo de los n valores PIT hasta t (t − n + 1 … t), con los n presentes (curve_min12)
    "rolling_min": lambda df, c, wl, sp: df[c[0]].rolling(int(sp["n"]), min_periods=int(sp["n"])).min(),
    "level_d3m": lambda df, c, wl, sp: ((df[c[0]] + df[c[1]]) / 2).diff(3),
    "diff_ab": lambda df, c, wl, sp: df[c[0]] - df[c[1]],
    "baa_spread": lambda df, c, wl, sp: df[c[0]].combine_first(df[c[1]] - df[c[2]]),
    "ratio_log_diff6": lambda df, c, wl, sp: 100 * (np.log(df[c[0]] / df[c[1]])
                                                   - np.log(df[c[0]] / df[c[1]]).shift(6)),
    "net_liq_yoy": lambda df, c, wl, sp: _yoy(df[c[0]] - df[c[1]] - df[c[2]].fillna(0)),
    "global_cb_usd_yoy": lambda df, c, wl, sp: _yoy(df[c[0]] + df[c[1]] * df[c[2]] + df[c[3]] * 100 / df[c[4]]),
}


def _yoy(level: pd.Series) -> pd.Series:
    return 100 * np.log(level / level.shift(12))


# ------------------------------------------------------------------ lista blanca
def load_whitelist(path: Path = WL_PATH) -> dict:
    wl = yaml.safe_load(Path(path).read_text())
    names = [v["nombre"] for v in wl["variables"]]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        raise ValueError(f"nombres repetidos en la lista blanca: {dup}")
    return wl


def whitelist_series(wl: dict) -> list[str]:
    return sorted({s for v in wl["variables"] if v["tipo"] == "serie" for s in v["series"]})


def needed_series(wl: dict, cal: dict[str, CalEntry]) -> list[str]:
    """Todas las series que lee el constructor: las de la lista blanca y sus proxies/vintages."""
    sids = set(whitelist_series(wl))
    for s in list(sids):
        sids |= set(cal[s].proxies) | set(cal[s].vintages)
    return sorted(sids)


def effective_principal_desde(wl: dict) -> dict[str, str | None]:
    """Regla general (Validador v0.2, I-1): una variable entra en el modelo principal desde el `principal_desde` MÁS
    TARDÍO entre el suyo y el de todas sus entradas, recorriendo el grafo de dependencias de las derivadas. Fechas en
    ISO (AAAA-MM-DD); None = sin restricción."""
    specs = {v["nombre"]: v for v in wl["variables"]}
    memo: dict[str, str | None] = {}

    def eff(name: str, stack: tuple = ()) -> str | None:
        if name in stack:
            raise ValueError(f"dependencia circular en la lista blanca: {' → '.join(stack + (name,))}")
        if name not in memo:
            v = specs[name]
            dates = [str(v["principal_desde"])] if v.get("principal_desde") else []
            dates += [d for e in (v.get("entradas") or []) if (d := eff(e, stack + (name,)))]
            memo[name] = max(dates) if dates else None
        return memo[name]

    return {n: eff(n) for n in specs}


def public_columns(wl: dict) -> list[str]:
    return [v["nombre"] for v in wl["variables"] if not v["nombre"].startswith("_")]


# ------------------------------------------------------------------ rejilla de decisión
def decision_grid(start: str = GRID_START, today: date | None = None) -> pd.DataFrame:
    """Último día hábil (calendario federal de EE. UU.) de cada mes; solo fechas ya pasadas (≤ hoy)."""
    today = pd.Timestamp(today or date.today()).normalize()
    off = CustomBusinessMonthEnd(calendar=USFederalHolidayCalendar())
    d = pd.date_range(start, today + pd.offsets.MonthEnd(1), freq=off)
    d = d[d <= today]
    return pd.DataFrame({"decision_date": d, "month": d.to_period("M").to_timestamp()})


# ------------------------------------------------------------------ acceso al warehouse
class Warehouse:
    """Lecturas del warehouse con caché. Necesita `obs_latest`, `vintages` y `catalog`."""

    def __init__(self, con, raw: bool = True):
        self.con = con
        self.raw = raw          # vintages de features/raw/alfred si no están en el warehouse (nunca con la instantánea)
        self._latest: dict[str, pd.Series] = {}
        self._vint: dict[str, VintageSet | None] = {}

    def latest(self, sid: str) -> pd.Series:
        if sid not in self._latest:
            self._latest[sid] = db.series(self.con, sid)
        return self._latest[sid]

    def vint(self, sid: str) -> VintageSet | None:
        if sid not in self._vint:
            self._vint[sid] = load_vintage_set(self.con, sid, raw=self.raw)
        return self._vint[sid]

    def catalog(self, sid: str) -> dict:
        r = self.con.execute("select pit_role, units from catalog where series_id = ?", [sid]).fetchone()
        return {"pit_role": r[0], "units": r[1]} if r else {"pit_role": None, "units": None}


def check_sources(wh: Warehouse, wl: dict, cal: dict[str, CalEntry], forbidden: list[str]) -> None:
    """Primera barrera: cada serie está en el calendario, es `observed` y no tiene raíz prohibida."""
    forb = sorted(set(R.FORBIDDEN_FEATURES) | set(forbidden), key=len, reverse=True)
    for v in wl["variables"]:
        if v["tipo"] != "serie":
            continue
        for sid in v["series"]:
            if sid not in cal:
                raise KeyError(f"{v['nombre']}: la serie {sid} no está en el calendario de publicación")
            if R.forbidden_root(sid, forb):
                raise AssertionError(f"{v['nombre']}: la serie {sid} es prohibida")
            role = wh.catalog(sid)["pit_role"]
            if role != "observed":
                raise AssertionError(f"{v['nombre']}: {sid} tiene pit_role={role} (solo 'observed')")
            exp = (v.get("unidades") or {}).get(sid)
            if exp:
                units = str(wh.catalog(sid)["units"] or "").lower()
                if exp.lower() not in units:
                    raise AssertionError(f"{sid}: unidades '{units}' ≠ esperadas '{exp}'")


# ------------------------------------------------------------------ una variable de tipo serie
def _not_before_period_end(entry: CalEntry, idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    if entry.anchor == "fin_periodo" and entry.freq in ("M", "Q", "A") and min(d for _, d in entry.lags) >= 0:
        return entry.anchor_dates(idx) + pd.Timedelta(days=1)
    return pd.DatetimeIndex(idx)


def _stale(entry: CalEntry, obs: pd.Series, t: pd.Series) -> pd.Series:
    ok = obs.notna()
    pe = pd.Series(pd.NaT, index=obs.index, dtype="datetime64[ns]")
    if ok.any():
        pe[ok] = period_end(pd.DatetimeIndex(obs[ok]), entry.freq) if entry.freq not in ("D", "W") else obs[ok]
    return (t - pe).dt.days > STALE_DAYS[entry.freq]


def latest_truncated(wh: Warehouse, entry: CalEntry, fn: Callable, factor: float,
                     grid: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """(valor, fecha de la observación más reciente usada) en cada t con la última vintage."""
    t = grid["decision_date"]
    s = regularize(wh.latest(entry.sid) * factor)
    nan = pd.Series(np.nan, index=t.values), pd.Series(pd.NaT, index=t.values, dtype="datetime64[ns]")
    if s.dropna().empty:
        return nan
    x = fn(s).dropna()
    if x.empty:
        return nan
    av = availability(entry, s.dropna().index, [wh.vint(p) for p in entry.proxies])
    avx = av.reindex(x.index).ffill()
    obs = pd.DataFrame({"av": avx.values, "value": x.values, "obs": x.index})
    obs = obs[obs["av"] < NEVER].sort_values(["av", "obs"])
    m = pd.merge_asof(pd.DataFrame({"t": t.values}), obs, left_on="t", right_on="av")
    m.index = t.values
    st = _stale(entry, m["obs"], m["t"])
    return m["value"].where(~st), m["obs"].where(~st)


def vintage_value(vs: VintageSet, entry: CalEntry, fn: Callable, factor: float,
                  t: pd.Timestamp) -> tuple[float, pd.Timestamp | None]:
    snap = vs.snapshot(t, since=t - VINTAGE_LOOKBACK) * factor
    snap = snap[_not_before_period_end(entry, snap.index) <= t]
    if snap.empty:
        return np.nan, None
    x = fn(regularize(snap)).dropna()
    if x.empty:
        return np.nan, None
    d = x.index[-1]
    pe = period_end(pd.DatetimeIndex([d]), entry.freq)[0] if entry.freq not in ("D", "W") else d
    if (t - pe).days > STALE_DAYS[entry.freq]:
        return np.nan, None
    return float(x.iloc[-1]), d


def series_variable(wh: Warehouse, cal: dict[str, CalEntry], spec: dict, grid: pd.DataFrame,
                    mode: str) -> tuple[pd.Series, pd.DataFrame]:
    """Valores en la rejilla y linaje (t, series_id, obs_date, modo efectivo) de una variable de tipo serie.
    Varias series = empalme por prioridad: en cada t gana la primera que tiene valor."""
    tr = dict(spec["transformacion"])
    fname = tr.pop("fn")
    fn = lambda s: TRANSFORMS[fname](s, **tr)  # noqa: E731
    factor = float(spec.get("factor", 1.0))
    idx = grid["decision_date"].values
    vals = pd.Series(np.nan, index=idx)
    lin = pd.DataFrame({"series_id": pd.Series(None, index=idx, dtype=object),
                        "obs_date": pd.Series(pd.NaT, index=idx, dtype="datetime64[ns]"),
                        "mode": pd.Series(None, index=idx, dtype=object)})
    use_v = mode == "vintage" and spec.get("modo") == "vintage"
    for sid in spec["series"]:
        entry = cal[sid]
        lv, lo = latest_truncated(wh, entry, fn, factor, grid)
        cv, co = lv.copy(), lo.copy()
        cm = pd.Series("latest_truncated", index=idx, dtype=object)
        if use_v:
            sources = [vs for v in entry.vintages if (vs := wh.vint(v)) is not None]
            for i, t in enumerate(grid["decision_date"]):
                vs = next((v for v in sources if v.start <= t), None)
                if vs is None:
                    continue
                cv.iloc[i], d = vintage_value(vs, entry, fn, factor, t)
                co.iloc[i] = d if d is not None else pd.NaT
                cm.iloc[i] = f"vintage:{vs.sid}"
        fill = vals.isna() & cv.notna()
        vals[fill] = cv[fill]
        lin.loc[fill, "series_id"] = sid
        lin.loc[fill, "obs_date"] = co[fill]
        lin.loc[fill, "mode"] = cm[fill]
    return vals, lin


# ------------------------------------------------------------------ matriz
def build_matrix(con, mode: str, grid: pd.DataFrame | None = None, wl: dict | None = None,
                 cal: dict[str, CalEntry] | None = None, forbidden: list[str] | None = None,
                 check_forbidden: bool = True, raw: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Matriz (índice = fecha de decisión) con las columnas públicas de la lista blanca, linaje largo y
    descripción por columna. `forbidden` = series forecast/lookahead (por defecto, las del meta.json oficial).
    `raw=False` con la instantánea congelada (todo lo que se lee está dentro de ella)."""
    if mode not in MODES:
        raise ValueError(f"modo desconocido: {mode}")
    wl = wl or load_whitelist()
    cal = cal or load_calendar()
    grid = decision_grid() if grid is None else grid
    if forbidden is None:
        meta = json.loads(R.out_path().with_suffix(".meta.json").read_text())
        forbidden = meta["forbidden_features"]["series"]
    wh = Warehouse(con, raw=raw)
    check_sources(wh, wl, cal, forbidden)

    idx = grid["decision_date"].values
    cols: dict[str, pd.Series] = {}
    lineage: dict[str, pd.DataFrame] = {}
    info: dict[str, dict] = {}
    # primero las series; después las derivadas en el orden de la lista (pueden usar derivadas anteriores)
    ordered = ([s for s in wl["variables"] if s["tipo"] == "serie"]
               + [s for s in wl["variables"] if s["tipo"] != "serie"])
    for spec in ordered:
        name = spec["nombre"]
        if spec["tipo"] == "serie":
            v, lin = series_variable(wh, cal, spec, grid, mode)
            cols[name], lineage[name] = v, lin.assign(column=name, decision_date=idx)
        elif spec["tipo"] == "derivada":
            missing = [c for c in spec["entradas"] if c not in cols]
            if missing:
                raise KeyError(f"{name}: entradas no definidas antes en la lista blanca: {missing}")
            df = pd.DataFrame({c: cols[c] for c in spec["entradas"]}, index=idx)
            v = DERIVED[spec["funcion"]](df, spec["entradas"], wl, spec)
            cols[name] = v.replace([np.inf, -np.inf], np.nan)
            parts = [lineage[c].assign(column=name) for c in spec["entradas"]]
            lineage[name] = pd.concat(parts, ignore_index=True)
        else:
            raise ValueError(f"{name}: tipo desconocido {spec['tipo']}")
        if spec.get("desde"):   # sin mecanismo o sin datos fiables antes de esta fecha (regla 4)
            before = pd.DatetimeIndex(idx) < pd.Timestamp(str(spec["desde"]))
            cols[name] = cols[name].where(~before)
            lineage[name] = lineage[name][lineage[name]["decision_date"] >= pd.Timestamp(str(spec["desde"]))]
        info[name] = {k: (str(spec[k]) if k in ("desde", "principal_desde") and spec.get(k) else spec.get(k))
                      for k in ("bloque", "tipo", "series", "entradas", "modo", "estado", "desde",
                                "principal_desde")}

    pub = public_columns(wl)
    eff = effective_principal_desde(wl)
    for c in pub:
        info[c]["principal_desde_efectivo"] = eff[c]
        info[c]["principal_desde_heredado"] = bool(eff[c]) and eff[c] != info[c].get("principal_desde")
    X = pd.DataFrame({c: cols[c] for c in pub}, index=pd.DatetimeIndex(idx, name="decision_date"))
    if check_forbidden:
        R.assert_no_forbidden(X.columns, extra=forbidden)   # segunda barrera
    lin = pd.concat([lineage[c] for c in pub], ignore_index=True)
    lin = lin[lin["series_id"].notna() & lin["obs_date"].notna()]
    lin = lin[["decision_date", "column", "series_id", "obs_date", "mode"]].reset_index(drop=True)
    for c in pub:
        s = X[c].dropna()
        lc = lin[lin["column"] == c]
        vin = lc[lc["mode"].str.startswith("vintage")]
        info[c].update(primer_dato=f"{s.index.min():%Y-%m}" if len(s) else None,
                       hasta=f"{s.index.max():%Y-%m}" if len(s) else None, n=int(len(s)),
                       vintage_desde=f"{vin['decision_date'].min():%Y-%m}" if len(vin) else None,
                       celdas_vintage=int(vin["decision_date"].nunique()))
    return X, lin, {c: info[c] for c in pub}


# ------------------------------------------------------------------ persistencia point-in-time (baseline)
PRED_COLS = [f"pers_{q}" for q in R.QUADRANTS]
# Hash del meta.json de la etiqueta v1.1 (fuera de git). Los parámetros NO se leen de él: s_G y s_I salen de R.PARAMS
# (código en git) y el empalme se recalcula desde la instantánea congelada de la etiqueta (hash en R.FROZEN). El meta
# solo se usa para comprobar que coinciden; si su hash cambia, falla (Validador v0.2, M-1).
LABEL_META_SHA256 = {"1.1": "240a10cd405faed561b446f5922292e288df5b256ea3140b839f924363f9677c"}


def label_params(inputs: dict | None = None) -> dict:
    """s_G, s_I (fijos en R.PARAMS) y empalme IPC→PCE (recalculado desde la instantánea de la etiqueta), comprobados
    contra el meta.json congelado de la etiqueta."""
    p = R.PARAMS
    if inputs is None:
        inputs, _ = R.read_snapshot()            # verifica el hash de la instantánea (R.FROZEN)
    splice = R.inflation_axis(inputs["levels"], p).attrs["splice"]["adj_pp"]
    mp = R.out_path().with_suffix(".meta.json")
    if file_sha(mp) != LABEL_META_SHA256[p.version]:
        raise RuntimeError(f"{mp.name} no coincide con el hash registrado en LABEL_META_SHA256")
    meta = json.loads(mp.read_text())
    if (meta["s_G"], meta["s_I"]) != (p.s_G_fixed, p.s_I_fixed) or \
            abs(meta["splice_cpi_core"]["adj_pp"] - splice) > 1e-12:
        raise RuntimeError("los parámetros de la etiqueta no coinciden con su meta congelado")
    return {"s_G": p.s_G_fixed, "s_I": p.s_I_fixed, "splice": splice, "label_lag": meta["label_lag"]["label_lag"]}


def persistence(con, mode: str, grid: pd.DataFrame | None = None, start: str = "1955-01-01",
                cal: dict[str, CalEntry] | None = None, raw: bool = True) -> pd.DataFrame:
    """Baseline de persistencia point-in-time (ficha §12) con el MISMO modo que las variables (M-4): en cada t,
    la etiqueta se recalcula desde la instantánea congelada con los niveles conocidos en t (vintage: tal como se
    publicaron; latest_truncated: última vintage truncada por fecha de publicación) y se toma la última
    calculable (normalmente la de t − label_lag). Devuelve predicciones (prefijo `pers_`), NO variables."""
    grid = decision_grid() if grid is None else grid
    grid = grid[grid["decision_date"] >= pd.Timestamp(start)]
    inputs, _ = R.read_snapshot()
    lp = label_params()
    cal = cal or load_calendar()
    wh = Warehouse(con, raw=raw)
    snapv = {sid: VintageSet(v, sid) for sid, (v, _) in inputs["vintages"].items() if len(v)}

    def vset(sid):
        return snapv.get(sid) or wh.vint(sid)

    levels = {sid: s.dropna() for sid, s in inputs["levels"].items()}
    av = {sid: availability(cal[sid], s.index, [vset(p) for p in cal[sid].proxies]) for sid, s in levels.items()}
    rows = []
    for t, month in zip(grid["decision_date"], grid["month"]):
        lv = {}
        for sid, s in levels.items():
            vs = snapv.get(sid) if mode == "vintage" else None
            if vs is not None and vs.start <= t:
                snap = vs.snapshot(t)
                snap = snap[_not_before_period_end(cal[sid], snap.index) <= t]
                lv[sid] = R._cal(snap)
            else:
                lv[sid] = R._cal(s[av[sid].reindex(s.index).to_numpy() <= np.datetime64(t)])
        lab, _ = R.make_label({"levels": lv, "usrec": inputs["usrec"]}, R.PARAMS, lp["s_G"], lp["s_I"],
                              splice=lp["splice"])
        if lab.empty:
            continue
        last = lab.iloc[-1]
        rows.append({"decision_date": t, "month": month, "label_month": last["date"],
                     **{f"pers_{q}": float(last[f"p_{q}"]) for q in R.QUADRANTS},
                     "pers_hard": last["label_hard"]})
    out = pd.DataFrame(rows).set_index("decision_date")
    out["lag_months"] = ((out["month"].dt.year - out["label_month"].dt.year) * 12
                         + out["month"].dt.month - out["label_month"].dt.month)
    return out


def score_training(pred: pd.DataFrame, end: str = "2004-12-01") -> dict:
    """Métricas del baseline SOLO en el periodo de entrenamiento (≤ 2004-12; nunca el bloqueado)."""
    hold = pd.Timestamp(R.PARAMS.holdout_start)
    lab = pd.read_parquet(R.out_path(), filters=[("date", "<", hold.to_datetime64())]).set_index("date")
    lab = lab[(lab["weight"] > 0) & ~lab["provisional"] & (lab.index <= pd.Timestamp(end))]
    p = pred.set_index("month")
    common = lab.index.intersection(p.index)
    assert pd.Timestamp(end) < hold and common.max() < hold, "no se puntúa el periodo bloqueado"
    P = np.clip(p.loc[common, PRED_COLS].to_numpy(float), 1e-4, 1)   # mismo recorte que labels/checks.py
    P = P / P.sum(axis=1, keepdims=True)
    T = lab.loc[common, [f"p_{q}" for q in R.QUADRANTS]].to_numpy(float)
    hard = p.loc[common, "pers_hard"].to_numpy() == lab.loc[common, "label_hard"].to_numpy()
    return {"n": int(len(common)), "desde": f"{common.min():%Y-%m}", "hasta": f"{common.max():%Y-%m}",
            "acierto": float(hard.mean()), "logloss_blanda": float(-(T * np.log(P)).sum(axis=1).mean()),
            "lag_meses_mediana": float(p.loc[common, "lag_months"].median())}


# ------------------------------------------------------------------ escritura
def file_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frame_sha(df: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(df.reset_index(), index=False).values.tobytes()).hexdigest()


# ------------------------------------------------------------------ instantánea congelada de entradas
# Igual que la etiqueta (src/labels/regime_us.py): la matriz OFICIAL se construye solo desde la instantánea de entradas
# (observaciones y vintages que lee el constructor + calendario + lista blanca). Sus hashes están aquí, en git;
# `read_snapshot` se niega a usar una instantánea distinta y `write_snapshot` no toca una versión congelada.
FROZEN: dict[str, dict] = {
    # v0.2 candidata (2026-10-15): instantánea de entradas desde el warehouse built_at 2026-10-15 ~12:50 + raw ALFRED
    "0.2": {
        "data_sha256_file": "db06b89c63d7c89c896c76a13127739237c67e6594224a4d7375a5bf5c4a6261",
        "data_sha256_content": "069b9d5cece116c8771c4d84c6f26ecc21d599f942f27f29b79bfbac9ded6b64",
        "whitelist_sha256": "6e321ebe4068ba69c181affbd3b8c4b80b012e75fe5dfba3a28f558416a172b0",
        "calendar_sha256": "9142290c086af0c8a3250a7a9184417f8e570777561052b0c6a3895efd6c566b",
        "info_sha256": "8a01d6f0296bd6b16d2164fba87ab2dfd7f16801ee93809b701d84c5168c38f3",
        "grid_end": "2026-09-30",
    },
    # v0.3 congelada el 2026-10-16 tras el ✅ del Validador y la aprobación del usuario (procedimiento B-5):
    # copia de los hashes de CANDIDATE["0.3"]
    "0.3": {
        "data_sha256_file": "db06b89c63d7c89c896c76a13127739237c67e6594224a4d7375a5bf5c4a6261",
        "data_sha256_content": "069b9d5cece116c8771c4d84c6f26ecc21d599f942f27f29b79bfbac9ded6b64",
        "whitelist_sha256": "55fb431466c721880ddf76f2407d3f88f498866a9865f12a2a8850020712324b",
        "calendar_sha256": "373ced7b907e08728464935a64d523b0aa0150e899f44735c6613870c4cbc421",
        "info_sha256": "7c1b141976f548cdabc60f874d9f2114734f036ee2698c27f169e2fc57684081",
        "grid_end": "2026-09-30",
        "veredicto": "docs/validation/2026-10-16_pit_base_v0.3.md",
    },
}


# Candidatas: hashes calculados, pendientes del veredicto del Validador. Pasan a FROZEN solo tras él (I-4). La v0.2 entró
# en FROZEN antes del veredicto por un error de orden; queda congelada como registro, pero está SUSTITUIDA por la v0.3.
# PROCEDIMIENTO DE CONGELACIÓN (Validador v0.3, B-5), solo tras el ✅ del Validador y la aprobación del usuario:
#   1. Se CONSERVA la entrada de CANDIDATE tal cual (el meta.json la publica en "candidata" y el test de reproducción
#      la compara) y se añade a FROZEN una copia idéntica de sus hashes más la clave
#      "veredicto": "docs/validation/<fecha>_pit_base_v<versión>.md" (el fichero debe existir; lo comprueba un test).
#   2. Opcional: regenerar el meta (`python -m src.features.pit`) para que su "estado" diga "congelada". Las matrices,
#      los linajes y los baselines no cambian (mismos sha256); el test de reproducción sigue pasando.
#   3. Tag git `pit-v<versión>`. Nunca `--freeze` ni `--candidate` sobre una versión en FROZEN (se niegan).
CANDIDATE: dict[str, dict] = {
    # v0.3 (2026-10-15; lista blanca rehecha el 2026-10-16 tras la re-auditoría: tcu_gap condicional < 1984, H-1):
    # lista blanca y calendario nuevos sobre la instantánea de datos de la v0.2 (mismo hash)
    "0.3": {
        "data_sha256_file": "db06b89c63d7c89c896c76a13127739237c67e6594224a4d7375a5bf5c4a6261",
        "data_sha256_content": "069b9d5cece116c8771c4d84c6f26ecc21d599f942f27f29b79bfbac9ded6b64",
        "whitelist_sha256": "55fb431466c721880ddf76f2407d3f88f498866a9865f12a2a8850020712324b",
        "calendar_sha256": "373ced7b907e08728464935a64d523b0aa0150e899f44735c6613870c4cbc421",
        "info_sha256": "7c1b141976f548cdabc60f874d9f2114734f036ee2698c27f169e2fc57684081",
        "grid_end": "2026-09-30",
    },
    # v0.4 (2026-10-23): 4 derivadas de riesgo de giro (curve_min12, baa_gap10y, baa_d6m, sahm_d3m; Estratega, revisión
    # de M1 §5) sobre la instantánea de datos de la v0.2 (mismo hash) y el calendario de la v0.3 (mismo hash). FUERA de
    # FROZEN hasta el ✅ del Validador y la aprobación del usuario (procedimiento B-5)
    "0.4": {
        "data_sha256_file": "db06b89c63d7c89c896c76a13127739237c67e6594224a4d7375a5bf5c4a6261",
        "data_sha256_content": "069b9d5cece116c8771c4d84c6f26ecc21d599f942f27f29b79bfbac9ded6b64",
        "whitelist_sha256": "0df63c84c2431434fa7c3fb7d9a735eb31319b421ef8f5bcf4000c740b45e561",
        "calendar_sha256": "373ced7b907e08728464935a64d523b0aa0150e899f44735c6613870c4cbc421",
        "info_sha256": "90515a5f8b11dbdd37ee4005359cdcbeb39b0cc0084beb7c0fb591225c10f01c",
        "grid_end": "2026-09-30",
    },
}
# versión → versión de la instantánea de DATOS que usa (la v0.3 reutiliza la de la v0.2, sin releer el warehouse)
DATA_VERSION = {"0.2": "0.2", "0.3": "0.2", "0.4": "0.2"}
SUPERSEDED = {"0.2": "0.3"}


def inputs_dir() -> Path:
    return out_dir() / "inputs"


def snapshot_paths(version: str = VERSION) -> dict[str, Path]:
    d = inputs_dir()
    return {"data": d / f"pit_us_v{DATA_VERSION.get(version, version)}_inputs.parquet",
            "whitelist": d / f"pit_us_v{version}_whitelist.yaml",
            "calendar": d / f"pit_us_v{version}_calendar.yaml", "info": d / f"pit_us_v{version}_inputs.json"}


SNAP_COLS = ["kind", "series_id", "date", "value", "realtime_start", "source", "pit_role", "units"]


def collect_inputs(con, wl: dict, cal: dict[str, CalEntry]) -> pd.DataFrame:
    """Todo lo que lee el constructor (y la persistencia, para sus proxies) desde el warehouse vivo y
    features/raw/alfred: última vintage (`latest`), vintages (`vintage`) y catálogo (`catalog`)."""
    wh = Warehouse(con, raw=True)
    parts = []
    for sid in needed_series(wl, cal):
        s = wh.latest(sid)
        parts.append(pd.DataFrame({"kind": "latest", "series_id": sid, "date": s.index, "value": s.values}))
        vs = wh.vint(sid)
        if vs is not None:
            parts.append(vs.v.assign(kind="vintage", series_id=sid))
        r = con.execute("select source, pit_role, units from catalog where series_id = ?", [sid]).fetchone()
        parts.append(pd.DataFrame([{"kind": "catalog", "series_id": sid, "source": r[0] if r else None,
                                    "pit_role": r[1] if r else None, "units": r[2] if r else None}]))
    df = pd.concat(parts, ignore_index=True).reindex(columns=SNAP_COLS)
    for c in ("date", "realtime_start"):
        df[c] = pd.to_datetime(df[c]).astype("datetime64[ns]")
    df["value"] = df["value"].astype(float)
    for c in ("kind", "series_id", "source", "pit_role", "units"):
        df[c] = df[c].astype(object).where(df[c].notna(), None)
    return df.sort_values(["kind", "series_id", "date", "realtime_start"], na_position="first").reset_index(drop=True)


def write_snapshot(con, version: str = VERSION, force: bool = False) -> dict:
    import shutil
    paths = snapshot_paths(version)
    if version in FROZEN:
        raise SystemExit(f"la v{version} está congelada (FROZEN): su instantánea no se toca; crea una versión nueva")
    dv = DATA_VERSION.get(version, version)
    if dv != version:   # Validador v0.3, H-2: la instantánea de datos es de otra versión (compartida): nunca se reescribe
        raise SystemExit(f"la v{version} usa la instantánea de datos de la v{dv} ({paths['data'].name}), que no es "
                         f"suya: write_snapshot no la toca ni con --force; crea una versión nueva con datos propios")
    if paths["data"].exists() and not force:
        raise SystemExit(f"{paths['data']} ya existe (usa --force solo para una candidata no congelada)")
    paths["data"].parent.mkdir(parents=True, exist_ok=True)
    for p in paths.values():
        if p.exists():
            p.chmod(0o644)
    df = collect_inputs(con, load_whitelist(), load_calendar())
    df.to_parquet(paths["data"], index=False)
    shutil.copyfile(WL_PATH, paths["whitelist"])
    shutil.copyfile(CAL_PATH, paths["calendar"])
    grid_end = decision_grid()["decision_date"].max()
    info = {"version": version, "creado": pd.Timestamp.now().isoformat(timespec="seconds"),
            "grid_end": f"{grid_end:%Y-%m-%d}",
            "warehouse_built_at": str(con.execute("select built_at from build_log").fetchone()[0]),
            "rows": len(df), "series": int(df.loc[df["kind"] == "catalog", "series_id"].nunique())}
    paths["info"].write_text(json.dumps(info, indent=1))
    frozen = {"data_sha256_file": file_sha(paths["data"]), "data_sha256_content": frame_sha(df),
              "whitelist_sha256": file_sha(paths["whitelist"]), "calendar_sha256": file_sha(paths["calendar"]),
              "info_sha256": file_sha(paths["info"]), "grid_end": info["grid_end"]}
    backup = paths["data"].parent / "backup"
    backup.mkdir(exist_ok=True)
    for p in paths.values():
        b = backup / p.name
        if b.exists():
            b.chmod(0o644)
        shutil.copyfile(p, b)
        b.chmod(0o444)
        p.chmod(0o444)
    return frozen


def write_candidate(version: str = VERSION, force: bool = False) -> dict:
    """Versión nueva de lista blanca/calendario sobre la instantánea de DATOS existente (DATA_VERSION): copia los yaml
    de research/, escribe el info (con el hash de los datos reutilizados) y devuelve los hashes de la candidata. No lee
    el warehouse."""
    import shutil
    if version in FROZEN:
        raise SystemExit(f"la v{version} está congelada (FROZEN)")
    paths = snapshot_paths(version)
    dv = DATA_VERSION[version]
    data_ref = FROZEN.get(dv) or CANDIDATE.get(dv)
    if not data_ref or file_sha(paths["data"]) != data_ref["data_sha256_file"]:
        raise RuntimeError(f"la instantánea de datos v{dv} no coincide con su hash")
    if paths["whitelist"].exists() and not force:
        raise SystemExit(f"{paths['whitelist']} ya existe (usa --force para rehacer una candidata)")
    old = json.loads(snapshot_paths(dv)["info"].read_text())
    info = {**old, "version": version, "datos_de": dv, "creado": pd.Timestamp.now().isoformat(timespec="seconds")}
    for k in ("whitelist", "calendar", "info"):
        if paths[k].exists():
            paths[k].chmod(0o644)
    shutil.copyfile(WL_PATH, paths["whitelist"])
    shutil.copyfile(CAL_PATH, paths["calendar"])
    paths["info"].write_text(json.dumps(info, indent=1))
    backup = inputs_dir() / "backup"
    for k in ("whitelist", "calendar", "info"):
        b = backup / paths[k].name
        if b.exists():
            b.chmod(0o644)
        shutil.copyfile(paths[k], b)
        b.chmod(0o444)
        paths[k].chmod(0o444)
    return {"data_sha256_file": data_ref["data_sha256_file"], "data_sha256_content": data_ref["data_sha256_content"],
            "whitelist_sha256": file_sha(paths["whitelist"]), "calendar_sha256": file_sha(paths["calendar"]),
            "info_sha256": file_sha(paths["info"]), "grid_end": info["grid_end"]}


def snapshot_ref(version: str) -> dict | None:
    return FROZEN.get(version) or CANDIDATE.get(version)


def read_snapshot(version: str = VERSION, paths: dict[str, Path] | None = None):
    """(conexión DuckDB en memoria con observations/catalog/vistas, lista blanca, ruta del calendario, info).
    Falla si algún fichero no coincide con FROZEN o, para una candidata, con CANDIDATE."""
    paths = paths or snapshot_paths(version)
    ref = snapshot_ref(version)
    if ref:
        for key, k in (("data", "data_sha256_file"), ("whitelist", "whitelist_sha256"),
                       ("calendar", "calendar_sha256"), ("info", "info_sha256")):
            if file_sha(paths[key]) != ref[k]:
                raise RuntimeError(f"la instantánea {paths[key].name} no coincide con la registrada de la v{version}")
    df = pd.read_parquet(paths["data"])
    if ref and frame_sha(df) != ref["data_sha256_content"]:
        raise RuntimeError(f"el contenido de la instantánea v{version} no coincide con el registrado")
    info = json.loads(paths["info"].read_text())
    return snapshot_warehouse(df, info["creado"]), load_whitelist(paths["whitelist"]), paths["calendar"], info


def snapshot_warehouse(df: pd.DataFrame, built_at) -> duckdb.DuckDBPyConnection:
    obs = df[df["kind"].isin(["latest", "vintage"])][["date", "value", "series_id", "realtime_start"]].copy()
    obs["source"] = "snapshot"
    obs["realtime_end"] = pd.NaT
    cat = df[df["kind"] == "catalog"][["series_id", "source", "pit_role", "units"]].reset_index(drop=True)
    mem = duckdb.connect(":memory:")
    mem.register("o", obs)
    mem.execute("""create table observations as select cast(date as date) as date, cast(value as double) as value,
                   series_id, source, cast(realtime_start as date) as realtime_start,
                   cast(realtime_end as date) as realtime_end from o""")
    mem.register("c", cat)
    mem.execute("create table catalog as select * from c")
    mem.execute(f"create table build_log as select timestamp '{pd.Timestamp(built_at):%Y-%m-%d %H:%M:%S}' as built_at")
    mem.execute(VIEWS_SQL)
    return mem


# ------------------------------------------------------------------ construcción oficial y escritura
def common_sample(baselines: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Los baselines de los dos modos sobre la MISMA muestra de meses (decisión B del usuario)."""
    common = None
    for B in baselines.values():
        common = B.index if common is None else common.intersection(B.index)
    return {m: B.loc[common] for m, B in baselines.items()}


def build_official(version: str = VERSION, with_baseline: bool = True) -> dict:
    con, wl, cal_path, info = read_snapshot(version)
    grid = decision_grid(today=pd.Timestamp(info["grid_end"]))
    cal = load_calendar(cal_path)
    out = {"matrices": {}, "baselines": {}, "grid": grid, "info": info}
    for mode in MODES:
        out["matrices"][mode] = build_matrix(con, mode, grid, wl=wl, cal=cal, raw=False)
    out["matrices"]["vintage_filadelfia_prudente"] = build_matrix(
        con, "vintage", grid, wl=wl, cal=load_calendar(cal_path, variant="prudente"), raw=False)
    if with_baseline:
        full = {m: persistence(con, m, grid, cal=cal, raw=False) for m in MODES}
        out["baselines"] = common_sample(full)
    out["con"] = con
    return out


def write(res: dict, version: str = VERSION, suffix: str = "") -> Path:
    od = out_dir()
    od.mkdir(parents=True, exist_ok=True)
    meta = {"version": version, "creado": pd.Timestamp.now().isoformat(timespec="seconds"),
            "fecha_decision": "último día hábil del mes (calendario federal EE. UU.)",
            "grid": [f"{res['grid']['decision_date'].min():%Y-%m-%d}", f"{res['grid']['decision_date'].max():%Y-%m-%d}"],
            "instantanea_entradas": {"info": res.get("info"), "frozen": FROZEN.get(version),
                                     "candidata": CANDIDATE.get(version),
                                     "estado": ("congelada" if version in FROZEN else
                                                "candidata (pendiente del Validador)" if version in CANDIDATE
                                                else "sin registrar")},
            "sustituye_a": [v for v, n in SUPERSEDED.items() if n == version],
            "label_params": {k: v for k, v in label_params().items()},
            "label_meta_sha256": LABEL_META_SHA256.get(R.PARAMS.version),
            "code_sha256": {p.name: file_sha(p) for p in sorted((REPO / "src" / "features").glob("*.py"))},
            "label_snapshot": R.FROZEN.get(R.PARAMS.version), "files": {}, "columns": {}, "baseline": {},
            "regla_arnes": ("modo principal vintage; latest_truncated como sensibilidad; puntuar en los dos; "
                            "comprobar la estabilidad de cada variable a ambos lados del salto revisado → primera "
                            "publicación; no usar ninguna variable antes de su principal_desde en el modelo principal")}
    for name, (X, lin, info) in res["matrices"].items():
        f = od / f"pit_us_v{version}_{name}{suffix}.parquet"
        X.reset_index().to_parquet(f, index=False)
        fl = od / f"pit_us_v{version}_{name}{suffix}_lineage.parquet"
        lin.to_parquet(fl, index=False)
        meta["files"][f.name] = {"sha256_file": file_sha(f), "sha256_content": frame_sha(X), "rows": len(X)}
        meta["files"][fl.name] = {"sha256_file": file_sha(fl), "rows": len(lin)}
        meta["columns"][name] = info
    for mode, B in res["baselines"].items():
        f = od / f"baseline_persistence_v{version}_{mode}{suffix}.parquet"
        B.reset_index().to_parquet(f, index=False)
        meta["files"][f.name] = {"sha256_file": file_sha(f), "rows": len(B)}
        meta["baseline"][mode] = {"muestra": "meses comunes a los dos modos",
                                  "entrenamiento_hasta_2004": score_training(B)}
    mp = od / f"pit_us_v{version}{suffix}.meta.json"
    mp.write_text(json.dumps(meta, indent=1, ensure_ascii=False, default=str))
    return mp


def main() -> None:
    ap = argparse.ArgumentParser(description="Base point-in-time: instantánea, matriz y baseline de persistencia")
    ap.add_argument("--freeze", action="store_true", help="warehouse vivo + raw → instantánea de entradas")
    ap.add_argument("--candidate", action="store_true",
                    help="lista blanca y calendario nuevos sobre la instantánea de datos existente (sin warehouse)")
    ap.add_argument("--force", action="store_true", help="sobrescribe una instantánea candidata (no congelada)")
    ap.add_argument("--live", action="store_true", help="construye desde el warehouse vivo (*_live, seguimiento)")
    ap.add_argument("--no-baseline", action="store_true")
    a = ap.parse_args()
    if a.freeze:
        frozen = write_snapshot(db.connect(), force=a.force)
        print("Instantánea escrita. Añade sus hashes a CANDIDATE en src/features/pit.py (a FROZEN solo tras el veredicto):")
        print(json.dumps({VERSION: frozen}, indent=1))
        return
    if a.candidate:
        cand = write_candidate(force=a.force)
        print("Candidata escrita. Añade a CANDIDATE en src/features/pit.py (no a FROZEN hasta el veredicto):")
        print(json.dumps({VERSION: cand}, indent=1))
        return
    if a.live:
        con = db.connect()
        grid = decision_grid()
        res = {"grid": grid, "matrices": {m: build_matrix(con, m, grid) for m in MODES}, "baselines": {}}
        print("→", write(res, suffix="_live"))
        return
    res = build_official(with_baseline=not a.no_baseline)
    for name, (X, _, _) in res["matrices"].items():
        print(f"{name}: {X.shape[1]} columnas, {len(X)} fechas")
    for mode, B in res["baselines"].items():
        print(f"  persistencia PIT ≤2004 ({mode}, muestra común): {score_training(B)}")
    print("→", write(res))


if __name__ == "__main__":
    main()
