"""Matriz de variables point-in-time para el nowcast de régimen EE. UU. (docs/models/pit_base.md).

Para cada fecha de decisión t (último día hábil del mes, calendario federal de EE. UU.; ficha de la etiqueta §9)
devuelve el valor de cada variable de la LISTA BLANCA (research/pit_whitelist.yaml) usando solo lo publicado
hasta t, según el calendario (research/pit_calendar.yaml, src/features/calendar.py).

Dos modos (Validador M-4: el baseline de persistencia y las variables se construyen con el mismo modo):
- `vintage`: donde hay vintages (ALFRED/RTDSM), la serie tal como se publicó en t; fuera del archivo de vintages,
  o para variables declaradas `latest_truncated`, se usa el modo siguiente. Cada celda indica su modo efectivo
  (linaje).
- `latest_truncated`: última vintage (datos revisados) truncada por la fecha de publicación de cada observación.

Barreras: solo series de la lista blanca, con `pit_role = observed` en el catálogo y sin raíces prohibidas; al
final, `src.labels.regime_us.assert_no_forbidden` sobre las columnas (segunda barrera, P-4 del Validador).

Salida (no va al warehouse): <FIN_DATA_ROOT>/features/pit_us_v<versión>_<modo>.parquet, su linaje
(`..._lineage.parquet`), la persistencia point-in-time (`baseline_persistence_v<versión>_<modo>.parquet`) y
`pit_us_v<versión>.meta.json` con hashes.

    .venv/bin/python -m src.features.pit            # construye los dos modos + baseline y escribe
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

from src.features.calendar import (CAL_PATH, NEVER, CalEntry, VintageSet, availability, load_calendar)
from src.labels import regime_us as R
from src.regime.asof import infer_freq, period_end
from src.regime.features import regularize, sahm
from src.warehouse import db

REPO = Path(__file__).resolve().parents[2]
WL_PATH = REPO / "research" / "pit_whitelist.yaml"
VERSION = "0.1"
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


def d_hysteresis_state(df, cols, wl, spec):
    g, sh = df[cols[0]], df[cols[1]]
    band, state, out = wl["histeresis_banda"], 0.0, []
    for gv, sv in zip(g.to_numpy(), sh.to_numpy()):
        if np.isnan(gv):
            out.append(np.nan)
            continue
        if gv < -band or (not np.isnan(sv) and sv >= 0.5):
            state = -1.0
        elif gv > band:
            state = 1.0
        out.append(state)
    return pd.Series(out, index=df.index)


def _flag(cond, *xs):
    ok = pd.concat(xs, axis=1).notna().all(axis=1)
    return cond.astype(float).where(ok)


DERIVED: dict[str, Callable] = {
    "zmean": d_zmean,
    "hysteresis_state": d_hysteresis_state,
    "log_ratio_x100": lambda df, c, wl, sp: 100 * np.log(df[c[0]] / df[c[1]]),
    "curve": lambda df, c, wl, sp: df[c[0]].combine_first(df[c[1]] - df[c[2]]),
    "diff3": lambda df, c, wl, sp: df[c[0]] - df[c[0]].shift(3),
    "diff12": lambda df, c, wl, sp: df[c[0]] - df[c[0]].shift(12),
    "level_d3m": lambda df, c, wl, sp: ((df[c[0]] + df[c[1]]) / 2).diff(3),
    "bear_steepening": lambda df, c, wl, sp: _flag((df[c[0]] > 0) & (df[c[1]] > 0), df[c[0]], df[c[1]]),
    "bull_steepening": lambda df, c, wl, sp: _flag((df[c[0]] > 0) & (df[c[1]] < 0), df[c[0]], df[c[1]]),
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

    def __init__(self, con):
        self.con = con
        self._latest: dict[str, pd.Series] = {}
        self._vint: dict[str, VintageSet | None] = {}

    def latest(self, sid: str) -> pd.Series:
        if sid not in self._latest:
            self._latest[sid] = db.series(self.con, sid)
        return self._latest[sid]

    def vint(self, sid: str) -> VintageSet | None:
        if sid not in self._vint:
            df = self.con.execute("select date, value, realtime_start from vintages where series_id = ?",
                                  [sid]).df()
            self._vint[sid] = VintageSet(df, sid) if len(df) else None
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
                 check_forbidden: bool = True) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Matriz (índice = fecha de decisión) con las columnas públicas de la lista blanca, linaje largo y
    descripción por columna. `forbidden` = series forecast/lookahead (por defecto, las del meta.json oficial)."""
    if mode not in MODES:
        raise ValueError(f"modo desconocido: {mode}")
    wl = wl or load_whitelist()
    cal = cal or load_calendar()
    grid = decision_grid() if grid is None else grid
    if forbidden is None:
        meta = json.loads(R.out_path().with_suffix(".meta.json").read_text())
        forbidden = meta["forbidden_features"]["series"]
    wh = Warehouse(con)
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
        info[name] = {k: spec.get(k) for k in ("bloque", "tipo", "series", "entradas", "modo", "estado")}

    pub = public_columns(wl)
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
        info[c].update(desde=f"{s.index.min():%Y-%m}" if len(s) else None,
                       hasta=f"{s.index.max():%Y-%m}" if len(s) else None, n=int(len(s)),
                       vintage_desde=f"{vin['decision_date'].min():%Y-%m}" if len(vin) else None,
                       celdas_vintage=int(vin["decision_date"].nunique()))
    return X, lin, {c: info[c] for c in pub}


# ------------------------------------------------------------------ persistencia point-in-time (baseline)
PRED_COLS = [f"pers_{q}" for q in R.QUADRANTS]


def persistence(con, mode: str, grid: pd.DataFrame | None = None,
                start: str = "1955-01-01") -> pd.DataFrame:
    """Baseline de persistencia point-in-time (ficha §12) con el MISMO modo que las variables (M-4): en cada t,
    la etiqueta se recalcula desde la instantánea congelada con los niveles conocidos en t (vintage: tal como se
    publicaron; latest_truncated: última vintage truncada por fecha de publicación) y se toma la última
    calculable (normalmente la de t − label_lag). Devuelve predicciones (prefijo `pers_`), NO variables."""
    grid = decision_grid() if grid is None else grid
    grid = grid[grid["decision_date"] >= pd.Timestamp(start)]
    inputs, _ = R.read_snapshot()
    meta = json.loads(R.out_path().with_suffix(".meta.json").read_text())
    cal = load_calendar()
    wh = Warehouse(con)
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
        lab, _ = R.make_label({"levels": lv, "usrec": inputs["usrec"]}, R.PARAMS, meta["s_G"], meta["s_I"],
                              splice=meta["splice_cpi_core"]["adj_pp"])
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
    lab = pd.read_parquet(R.out_path()).set_index("date")
    lab = lab[(lab["weight"] > 0) & ~lab["provisional"] & (lab.index <= pd.Timestamp(end))]
    p = pred.set_index("month")
    common = lab.index.intersection(p.index)
    assert common.max() <= pd.Timestamp(R.PARAMS.holdout_start), "no se puntúa el periodo bloqueado"
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


def write(results: dict, baselines: dict, grid: pd.DataFrame, con) -> Path:
    od = out_dir()
    od.mkdir(parents=True, exist_ok=True)
    meta = {"version": VERSION, "creado": pd.Timestamp.now().isoformat(timespec="seconds"),
            "fecha_decision": "último día hábil del mes (calendario federal EE. UU.)",
            "grid": [f"{grid['decision_date'].min():%Y-%m-%d}", f"{grid['decision_date'].max():%Y-%m-%d}"],
            "warehouse_built_at": str(con.execute("select built_at from build_log").fetchone()[0]),
            "whitelist_sha256": file_sha(WL_PATH), "calendar_sha256": file_sha(CAL_PATH),
            "code_sha256": {p.name: file_sha(p) for p in sorted((REPO / "src" / "features").glob("*.py"))},
            "label_snapshot": R.FROZEN.get(R.PARAMS.version), "files": {}, "columns": {}, "baseline": {}}
    for mode, (X, lin, info) in results.items():
        f = od / f"pit_us_v{VERSION}_{mode}.parquet"
        X.reset_index().to_parquet(f, index=False)
        fl = od / f"pit_us_v{VERSION}_{mode}_lineage.parquet"
        lin.to_parquet(fl, index=False)
        meta["files"][f.name] = {"sha256_file": file_sha(f), "sha256_content": frame_sha(X), "rows": len(X)}
        meta["files"][fl.name] = {"sha256_file": file_sha(fl), "rows": len(lin)}
        meta["columns"][mode] = info
    for mode, (B, sc) in baselines.items():
        f = od / f"baseline_persistence_v{VERSION}_{mode}.parquet"
        B.reset_index().to_parquet(f, index=False)
        meta["files"][f.name] = {"sha256_file": file_sha(f), "rows": len(B)}
        meta["baseline"][mode] = {"entrenamiento_hasta_2004": sc}
    mp = od / f"pit_us_v{VERSION}.meta.json"
    mp.write_text(json.dumps(meta, indent=1, ensure_ascii=False, default=str))
    return mp


def main() -> None:
    ap = argparse.ArgumentParser(description="Construye la matriz point-in-time y el baseline de persistencia")
    ap.add_argument("--no-baseline", action="store_true")
    a = ap.parse_args()
    con = db.connect()
    grid = decision_grid()
    results, baselines = {}, {}
    for mode in MODES:
        results[mode] = build_matrix(con, mode, grid)
        X = results[mode][0]
        print(f"{mode}: {X.shape[1]} columnas, {len(X)} fechas ({grid['decision_date'].min():%Y-%m} → "
              f"{grid['decision_date'].max():%Y-%m})")
        if not a.no_baseline:
            B = persistence(con, mode, grid)
            baselines[mode] = (B, score_training(B))
            print(f"  persistencia PIT ≤2004: {baselines[mode][1]}")
    print("→", write(results, baselines, grid, con))


if __name__ == "__main__":
    main()
