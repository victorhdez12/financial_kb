"""Etiqueta de régimen EE. UU. v1.1 — CONGELADA (ficha: docs/models/label_spec.md).

Ejecutar:
    .venv/bin/python -m src.labels.regime_us --from-snapshot   # etiqueta oficial, solo desde la instantánea
    .venv/bin/python -m src.labels.regime_us --freeze          # warehouse → instantánea de entradas → etiqueta
                                                               # (no sobrescribe una instantánea existente
                                                               #  sin --force)
    .venv/bin/python -m src.labels.regime_us --live            # warehouse de hoy → *_live.parquet (seguimiento;
                                                               #  no es la etiqueta oficial)
    .venv/bin/python -m src.labels.regime_us --fetch-vintages  # descarga vintages ALFRED de W875RX1/CMRMTSPL

La etiqueta es EX POST: usa la última vintage y ventanas CENTRADAS en t (mira meses hacia
delante). Nunca debe entrar como variable de un modelo (FORBIDDEN_FEATURES, assert_no_forbidden).

La etiqueta OFICIAL es la que se reconstruye desde la instantánea de entradas
(<FIN_DATA_ROOT>/labels/inputs/regime_us_v<versión>_inputs.parquet, con su SHA-256 en el meta.json).
Con datos vivos cambian también los meses maduros (σ_i y revisiones de la última vintage).

Salida: <FIN_DATA_ROOT>/labels/regime_us_v1.1.parquet (+ .meta.json). `data/archive` es un enlace a
FIN_DATA_ROOT. Versiones anteriores en git: v0.1 (35a0375), v0.2 (7b378cf), v1.0 (a76a4c0).

Uso: los meses con `provisional = true` (los últimos `provisional_months` = 54) o `weight = 0` no
puntúan ni entrenan. Embargo del backtest: `embargo_months`. Persistencia point-in-time: en la
fecha de decisión t la última etiqueta conocida es la de t − `label_lag`, calculada solo con datos
publicados en t (nunca `label_hard.shift(k)` con k < label_lag sobre la etiqueta final).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from src.warehouse import db


# ------------------------------------------------------------------ parámetros (ficha §11)
@dataclass(frozen=True)
class Params:
    version: str = "1.1"
    start: str = "1950-01-01"                   # inicio de la muestra de la etiqueta
    growth_ids: tuple[str, ...] = ("INDPRO", "PAYEMS", "W875RX1", "CMRMTSPL")
    min_growth_ind: int = 2                     # mínimo de indicadores para G
    smooth_months: int = 3                      # media de 3 m del nivel, centrada en el mes
    pace_lead: int = 3                          # ritmo: nivel suavizado en t+3 ...
    pace_lag: int = 3                           # ... frente a t−3 (6 m, anualizado ×2)
    trend_half_window: int = 60                 # mediana centrada ±60 meses (10 años)
    mad_k: float = 1.4826
    kappa: float = 2.5                          # umbral de inflación (PCE subyacente, %)
    splice_months: int = 24                     # empalme IPC→PCE subyacente: ajuste = media de
                                                # (PCE − IPC) subyacentes en los 24 primeros meses
                                                # en que coexisten (v1.0: −0,4 pp fijo)
    infl_lead: int = 3                          # inflación: índice en t+3 ...
    infl_lag: int = 3                           # ... frente a t−3, anualizada
    frontier: float = 0.55                      # máx. prob. < 0,55 → frontera
    provisional_months: int = 54               # fijado por src/labels/revision_study.py (k* = 55, ver ficha §7)
    embargo_months: int = 6                     # embargo del backtest (la etiqueta usa datos hasta t+4)
    holdout_start: str = "2005-01-01"           # periodo bloqueado: 2005-01 → abierto (decisión del usuario)
    truncated_months: int = 60                  # meses con ventana de tendencia truncada
    zero_weight_until: str = "1954-12-01"       # weight = 0 hasta aquí (IPC general, Corea)
    # escalas FIJAS de la v1.0 (estimadas con ALFRED en la v0.2; ver ficha §11). None = estimarlas
    s_G_fixed: float | None = 0.40              # INDPRO + PAYEMS, 1955-2024 (4 indicadores 2013-24: 0,33)
    s_I_fixed: float | None = 0.31              # PCE subyacente, 2000-2024
    scale_mature_months: int = 24               # fechas maduras para la estimación informativa
    # estimación ALFRED (informativa en la v1.0): suelo y valor de reserva
    scale_floor: float = 0.25
    scale_fallback: float = 0.5
    first_release_max_days: int = 75            # primera vintage ≤ 75 días tras fin de mes
    scale_min_n: int = 60                       # mínimo de fechas para una estimación estable
    scale_half_ratio: float = 2.0               # MAD de cada mitad dentro de ×/÷ 2 del total


PARAMS = Params()
QUADRANTS = ("expansion", "late_cycle", "stagflation", "low_growth_disinfl")
# v0.1 → v0.2: el cuadrante G↓ I↓ se llamaba "slowdown" (desaceleración/recesión). La palabra
# "recesión" queda reservada a la capa `usrec`.
ALIASES = {"slowdown": "low_growth_disinfl", "p_slowdown": "p_low_growth_disinfl"}
EXTRA_VINTAGES = ("W875RX1", "CMRMTSPL")    # no están en el warehouse; se guardan en labels/raw


def out_dir() -> Path:
    return db.DATA_ROOT / "labels"


def out_path(p: Params = PARAMS) -> Path:
    return out_dir() / f"regime_us_v{p.version}.parquet"


def raw_vintage_dir() -> Path:
    return out_dir() / "raw" / "alfred"


# ------------------------------------------------------------------ utilidades
def robust_sd(x, k: float = PARAMS.mad_k) -> float:
    x = pd.Series(x).dropna()
    if x.empty:
        return np.nan
    return float(k * np.median(np.abs(x - np.median(x))))


def monthly(con, sid: str) -> pd.Series:
    """Serie mensual (última vintage) en su calendario completo: los huecos quedan como NaN."""
    s = db.series(con, sid)
    if s.empty:
        return s
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="MS"))


def pace(level: pd.Series, p: Params = PARAMS) -> pd.Series:
    """Ritmo en t: variación log anualizada, en %, entre el nivel suavizado (media de 3 m centrada)
    en t+3 y en t−3. Usa los niveles de t−4 a t+4; equivale a una media triangular (1,2,3,3,3,3,2,1)
    de las tasas mensuales centrada en t."""
    sm = level.rolling(p.smooth_months, center=True, min_periods=p.smooth_months).mean()
    k = p.pace_lead + p.pace_lag
    return 100 * (12 / k) * (np.log(sm.shift(-p.pace_lead)) - np.log(sm.shift(p.pace_lag)))


def ann_change(level: pd.Series, p: Params = PARAMS) -> pd.Series:
    """Inflación en t: variación del índice de t−3 a t+3, anualizada, en %."""
    k = p.infl_lead + p.infl_lag
    return 100 * ((level.shift(-p.infl_lead) / level.shift(p.infl_lag)) ** (12 / k) - 1)


def pace_need(p: Params = PARAMS) -> int:
    """Meses posteriores a t que necesita el ritmo de G."""
    return p.pace_lead + p.smooth_months // 2


def centered_median(g: pd.Series, p: Params = PARAMS) -> pd.Series:
    h = p.trend_half_window
    return g.rolling(2 * h + 1, center=True, min_periods=h + 1).median()


# ------------------------------------------------------------------ eje G
def growth_components(levels: dict, p: Params = PARAMS) -> dict:
    """Para cada indicador: ritmo g, tendencia τ, σ y z (todo con la última vintage).

    La tendencia y σ se calculan sobre la muestra de la etiqueta (desde p.start); por eso la
    ventana está truncada al principio (1950-1954) y al final (últimos 60 meses)."""
    start = pd.Timestamp(p.start)
    out, notes = {}, []
    for sid in p.growth_ids:
        lv = levels.get(sid, pd.Series(dtype=float)).dropna()
        if lv.empty:
            notes.append(f"{sid}: sin datos en obs_latest; se omite")
            continue
        lv = lv.reindex(pd.date_range(lv.index.min(), lv.index.max(), freq="MS"))
        g = pace(lv, p)
        g = g[g.index >= start].dropna()
        tau = centered_median(g, p)
        dev = g - tau
        sigma = robust_sd(dev, p.mad_k)
        out[sid] = {"g": g, "tau": tau, "sigma": sigma, "z": dev / sigma}
    return {"comp": out, "notes": notes}


def growth_axis(comp: dict, p: Params = PARAMS) -> pd.DataFrame:
    z = pd.DataFrame({sid: c["z"] for sid, c in comp.items()})
    n = z.notna().sum(axis=1)
    G = z.mean(axis=1).where(n >= p.min_growth_ind)
    return pd.DataFrame({"G": G, "cobertura_g": n})


# ------------------------------------------------------------------ eje I
def splice_adjustment(pce: pd.Series, cpic_raw: pd.Series, p: Params = PARAMS) -> tuple[float, str, str]:
    """Ajuste del empalme (regla de la ficha §4): media de (PCE − IPC) subyacentes, ya
    transformados en I (6 m centrados, anualizados), en los p.splice_months primeros meses en que
    coexisten. Devuelve (ajuste, desde, hasta)."""
    both = pd.concat([pce, cpic_raw], axis=1, keys=["pce", "cpi"], sort=True).dropna().iloc[:p.splice_months]
    if both.empty:
        return float("nan"), None, None
    return float((both["pce"] - both["cpi"]).mean()), f"{both.index.min():%Y-%m}", f"{both.index.max():%Y-%m}"


def inflation_axis(levels: dict, p: Params = PARAMS, splice: float | None = None) -> pd.DataFrame:
    """PCE subyacente (desde su primer valor centrado, 1959-04); antes IPC subyacente + ajuste de
    empalme medido (desde 1957-04); antes IPC general (`headline`). El ajuste queda en
    `df.attrs['splice']`."""
    pce = ann_change(_cal(levels["PCEPILFE"]), p)
    cpic_raw = ann_change(_cal(levels["CPILFESL"]), p)
    if splice is None:
        adj, s_from, s_to = splice_adjustment(pce, cpic_raw, p)
    else:  # ajuste ya medido con la muestra completa (constante de definición)
        adj, s_from, s_to = splice, "fijo", "fijo"
    cpic = cpic_raw + adj
    head = ann_change(_cal(levels["CPIAUCSL"]), p)
    idx = pd.date_range(p.start, max(s.dropna().index.max() for s in (pce, cpic, head) if s.notna().any()), freq="MS")
    pce, cpic, head = (s.reindex(idx) for s in (pce, cpic, head))
    far = pd.Timestamp("2262-01-01")
    m_pce = idx >= (pce.first_valid_index() or far)
    m_cpic = (idx >= (cpic.first_valid_index() or far)) & ~m_pce
    m_head = ~m_pce & ~m_cpic
    I = pd.Series(np.nan, index=idx)
    src = pd.Series(None, index=idx, dtype=object)
    I[m_pce], src[m_pce] = pce[m_pce], "pce_core"
    I[m_cpic], src[m_cpic] = cpic[m_cpic], "cpi_core_adj"
    I[m_head], src[m_head] = head[m_head], "headline"
    src[I.isna()] = None
    out = pd.DataFrame({"I": I, "fuente_i": src})
    out.attrs["splice"] = {"adj_pp": adj, "from": s_from, "to": s_to}
    return out


# ------------------------------------------------------------------ vintages ALFRED
def fetch_extra_vintages(refresh: bool = False) -> list[str]:
    """Descarga de ALFRED las vintages de las series de G que no están en el warehouse, a
    <FIN_DATA_ROOT>/labels/raw/alfred (no toca src/ingest ni el warehouse; reutiliza su cliente)."""
    from src.ingest.alfred_vintages import download, normalise
    from src.ingest.fred_extended import Fred

    raw = raw_vintage_dir()
    raw.mkdir(parents=True, exist_ok=True)
    fred, msgs = Fred(), []
    for sid in EXTRA_VINTAGES:
        try:
            _, obs = download(fred, sid, raw, refresh)
            df = normalise(obs, sid)
            df.to_parquet(raw / f"{sid}.parquet", index=False)
            msgs.append(f"{sid}: {len(df)} filas, {df['realtime_start'].nunique()} vintages "
                        f"({df['realtime_start'].min()} → {df['realtime_start'].max()})")
        except Exception as e:  # noqa: BLE001 — si ALFRED no la tiene, se anota y se sigue
            msgs.append(f"{sid}: ALFRED no la devuelve ({type(e).__name__})")
    return msgs


def load_vintages(con, sid: str) -> tuple[pd.DataFrame, str]:
    df = con.execute(
        "select date, value, realtime_start, realtime_end from vintages where series_id = ?", [sid]
    ).df()
    origin = "warehouse"
    if df.empty:
        f = raw_vintage_dir() / f"{sid}.parquet"
        if not f.exists():
            return df, "none"
        df = pd.read_parquet(f)[["date", "value", "realtime_start", "realtime_end"]]
        origin = "labels/raw/alfred"
    for c in ("date", "realtime_start", "realtime_end"):
        df[c] = pd.to_datetime(df[c])
    return df, origin


def first_release(v: pd.DataFrame, fn, need: int, p: Params = PARAMS) -> pd.Series:
    """Valor del eje en t tal como se pudo calcular por primera vez: en la primera vintage que
    contiene el último dato que necesita la ventana (t+need). Solo si esa vintage sale
    ≤ p.first_release_max_days tras el fin de ese mes y no es el inicio del archivo ALFRED (en ese
    caso no sería una primera publicación)."""
    if v.empty:
        return pd.Series(dtype=float)
    r0 = v.groupby("date")["realtime_start"].min()
    lag = (r0 - (r0.index + pd.offsets.MonthEnd(0))).dt.days
    r0 = r0[(lag >= 0) & (lag <= p.first_release_max_days) & (r0 > v["realtime_start"].min())]
    rs, re_ = v["realtime_start"].values, v["realtime_end"].fillna(pd.Timestamp("2262-01-01")).values
    dates, vals = v["date"].values, v["value"].values
    out = {}
    for last, r in r0.items():
        t = last - pd.DateOffset(months=need)
        rr = np.datetime64(r)
        m = (rs <= rr) & (re_ >= rr) & (dates <= np.datetime64(last))
        snap = pd.Series(vals[m], index=pd.DatetimeIndex(dates[m])).sort_index()
        snap = snap[~snap.index.duplicated(keep="last")]
        snap = snap.reindex(pd.date_range(t - pd.DateOffset(months=12), last, freq="MS"))
        try:
            out[t] = float(fn(snap).loc[t])
        except Exception:  # noqa: BLE001
            continue
    return pd.Series(out, dtype=float).sort_index()


def _scale_from_errors(err: pd.Series, p: Params) -> dict:
    err = err.dropna()
    n = len(err)
    s = robust_sd(err, p.mad_k)
    halves = [robust_sd(h, p.mad_k) for h in np.array_split(err.values, 2)] if n >= 2 else [np.nan, np.nan]
    stable = (n >= p.scale_min_n and np.isfinite(s) and s > 0
              and all(np.isfinite(h) and s / p.scale_half_ratio <= h <= s * p.scale_half_ratio
                      for h in halves))
    return {"n": n, "mad_sd": s, "half1": halves[0], "half2": halves[1], "stable": bool(stable),
            "from": str(err.index.min().date()) if n else None,
            "to": str(err.index.max().date()) if n else None,
            "mean_err": float(err.mean()) if n else np.nan}


def estimate_scales(inputs: dict, comp: dict, last_mature: pd.Timestamp, p: Params = PARAMS) -> dict:
    """s_G y s_I = MAD×1,4826 del error de revisión (primera publicación − última vintage), en
    las unidades del eje (ventanas centradas); solo fechas maduras (≤ last_mature).

    s_G: error del G compuesto con TODOS los indicadores que tienen vintages, en las fechas en que
    todos tienen primera publicación (con W875RX1 y CMRMTSPL, desde ~2013). Se informa también el
    compuesto INDPRO+PAYEMS de toda la muestra. Suelo p.scale_floor; si no es estable, fallback."""
    notes, detail, origins = [], {}, {}
    infl_err = {}
    for sid in ("PCEPILFE", "CPILFESL"):
        v, origins[sid] = inputs["vintages"].get(sid, (pd.DataFrame(), "none"))
        fr = first_release(v, lambda s: ann_change(s, p), p.infl_lead, p)
        fin = ann_change(_cal(inputs["levels"][sid]), p)
        e = fr - fin.reindex(fr.index)
        infl_err[sid] = e[e.index <= last_mature]
        detail[f"I_{sid}"] = _scale_from_errors(infl_err[sid], p)
    z_err = {}
    for sid in p.growth_ids:
        v, origins[sid] = inputs["vintages"].get(sid, (pd.DataFrame(), "none"))
        if v.empty or sid not in comp:
            notes.append(f"{sid}: sin vintages ALFRED (ni en el warehouse ni en labels/raw); no entra en s_G")
            continue
        fr = first_release(v, lambda s: pace(s, p), pace_need(p), p)
        fin = pace(_cal(inputs["levels"][sid]), p)
        e = (fr - fin.reindex(fr.index)) / comp[sid]["sigma"]
        z_err[sid] = e[(e.index <= last_mature) & (e.index >= pd.Timestamp(p.start))]
        detail[f"G_z_{sid}"] = _scale_from_errors(z_err[sid], p)
    zdf = pd.DataFrame(z_err)
    all_err = zdf.mean(axis=1).where(zdf.notna().all(axis=1))
    detail["G_composite"] = _scale_from_errors(all_err, p)
    two = [c for c in ("INDPRO", "PAYEMS") if c in zdf]
    if len(two) == 2 and zdf.shape[1] > 2:
        two_err = zdf[two].mean(axis=1).where(zdf[two].notna().all(axis=1))
        detail["G_composite_INDPRO_PAYEMS"] = _scale_from_errors(two_err, p)

    def pick(key):
        d = detail[key]
        if not d["stable"]:
            notes.append(f"{key}: estimación no estable (n={d['n']}); se usa {p.scale_fallback}")
            return p.scale_fallback, "fallback"
        if d["mad_sd"] < p.scale_floor:
            return p.scale_floor, "suelo"
        return d["mad_sd"], "alfred"

    s_G, how_G = pick("G_composite")
    s_I, how_I = pick("I_PCEPILFE")
    return {"s_G": float(s_G), "s_I": float(s_I), "how_G": how_G, "how_I": how_I,
            "detail": detail, "notes": notes, "vintage_origin": origins,
            "g_composite_ids": list(zdf.columns),
            "errors": {"I": infl_err, "G": z_err, "G_composite": all_err}}


# ------------------------------------------------------------------ entradas y su instantánea
INFL_IDS = ("PCEPILFE", "CPILFESL", "CPIAUCSL")
VINTAGE_IDS = ("PCEPILFE", "CPILFESL", "INDPRO", "PAYEMS", "W875RX1", "CMRMTSPL")
SNAP_COLS = ["kind", "series_id", "date", "value", "realtime_start", "realtime_end", "origin"]


def _cal(x: pd.Series) -> pd.Series:
    x = x.dropna()
    return x.reindex(pd.date_range(x.index.min(), x.index.max(), freq="MS")) if len(x) else x


def snapshot_path(p: Params = PARAMS) -> Path:
    return out_dir() / "inputs" / f"regime_us_v{p.version}_inputs.parquet"


def forbidden_series(con) -> list[str]:
    """Series del warehouse con pit_role forecast/lookahead (nunca variables)."""
    return [r[0] for r in con.execute(
        "select distinct series_id from catalog where pit_role in ('forecast', 'lookahead') order by 1").fetchall()]


def load_inputs(con, p: Params = PARAMS, with_vintages: bool = True) -> dict:
    """Entradas de la etiqueta desde el warehouse: niveles (última vintage) de las 7 series, USREC,
    vintages ALFRED para las escalas y la lista de series forecast/lookahead."""
    levels = {sid: monthly(con, sid) for sid in (*p.growth_ids, *INFL_IDS)}
    out = {"levels": levels, "usrec": db.series(con, "USREC"), "vintages": {}, "forbidden_series": []}
    if with_vintages:
        out["vintages"] = {sid: load_vintages(con, sid) for sid in VINTAGE_IDS}
        out["forbidden_series"] = forbidden_series(con)
    return out


def inputs_to_frame(inputs: dict) -> pd.DataFrame:
    parts = []
    for sid, s in {**inputs["levels"], "USREC": inputs["usrec"]}.items():
        s = s.dropna()
        parts.append(pd.DataFrame({"kind": "level", "series_id": sid, "date": s.index, "value": s.values}))
    for sid, (v, origin) in inputs["vintages"].items():
        if v.empty:
            continue
        parts.append(v.assign(kind="vintage", series_id=sid, origin=origin))
    parts.append(pd.DataFrame({"kind": "forbidden", "series_id": inputs["forbidden_series"]}))
    df = pd.concat(parts, ignore_index=True).reindex(columns=SNAP_COLS)
    for c in ("date", "realtime_start", "realtime_end"):
        df[c] = pd.to_datetime(df[c]).astype("datetime64[ns]")
    df["value"] = df["value"].astype(float)
    df = df.astype({"kind": str, "series_id": str, "origin": object})
    return df.sort_values(["kind", "series_id", "date", "realtime_start"], na_position="first").reset_index(drop=True)


def frame_to_inputs(df: pd.DataFrame) -> dict:
    lv = df[df["kind"] == "level"]
    levels = {sid: _cal(pd.Series(g["value"].values, index=pd.DatetimeIndex(g["date"]), name=sid))
              for sid, g in lv.groupby("series_id", sort=False)}
    usrec = levels.pop("USREC").dropna()
    vint = {sid: (g[["date", "value", "realtime_start", "realtime_end"]].reset_index(drop=True),
                  str(g["origin"].iloc[0]))
            for sid, g in df[df["kind"] == "vintage"].groupby("series_id", sort=False)}
    forb = sorted(df.loc[df["kind"] == "forbidden", "series_id"].tolist())
    return {"levels": levels, "usrec": usrec, "vintages": vint, "forbidden_series": forb}


def write_snapshot(inputs: dict, p: Params = PARAMS, force: bool = False) -> Path:
    path = snapshot_path(p)
    if path.exists() and not force:
        raise SystemExit(f"{path} ya existe: la instantánea oficial no se sobrescribe (usa --force y crea "
                         "una versión nueva de la etiqueta)")
    path.parent.mkdir(parents=True, exist_ok=True)
    inputs_to_frame(inputs).to_parquet(path, index=False)
    return path


def read_snapshot(p: Params = PARAMS) -> tuple[dict, dict]:
    path = snapshot_path(p)
    df = pd.read_parquet(path)
    return frame_to_inputs(df), {"path": str(path), "sha256_file": file_sha(path),
                                 "sha256_content": content_hash(df), "rows": len(df)}


def file_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------ uso: columnas prohibidas y retardos
LABEL_COLUMNS = ("G", "I", "p_g_high", "p_i_high", "p_expansion", "p_late_cycle", "p_stagflation",
                 "p_low_growth_disinfl", "p_slowdown", "label_hard", "max_prob", "frontera", "provisional",
                 "tendencia_truncada", "cobertura_g", "fuente_i", "usrec", "weight")
# Nunca pueden ser variables de un modelo: columnas de la etiqueta (incl. alias de la v0.1), USREC
# (fechas NBER, ex post) y, además, las series del warehouse con pit_role forecast/lookahead (lista
# completa en el meta.json, `forbidden_features.series`).
FORBIDDEN_FEATURES = frozenset(LABEL_COLUMNS) | {"USREC"}


def assert_no_forbidden(columns, extra=None) -> None:
    """Falla si alguna columna de la matriz de variables es una columna prohibida. El arnés debe
    llamarla con la lista de variables y, en `extra`, `meta['forbidden_features']['series']`."""
    forb = set(FORBIDDEN_FEATURES) | set(extra or ())
    low = {f.lower() for f in forb if len(f) > 1}
    bad = [c for c in columns if c in forb or (len(str(c)) > 1 and str(c).lower() in low)
           or str(c).startswith("label_")]
    if bad:
        raise AssertionError(f"columnas prohibidas como variables: {sorted(map(str, bad))}")


def months_back(sid: str) -> int:
    """Meses de retraso del último dato publicado de `sid` al cierre (último día hábil) del mes t,
    con el calendario de publicación de src/regime/asof.py (días tras el fin del mes de referencia):
    1 si sale en < 28 días, 2 si tarda más."""
    from src.regime.asof import DEFAULT_LAG, PUB_LAG
    return 1 + int(PUB_LAG.get(sid, DEFAULT_LAG["M"]) // 28)


def label_lag(p: Params = PARAMS) -> dict:
    """Regla de la ficha: la etiqueta de s necesita G(s) (niveles hasta s+4 de ≥ 2 indicadores) e
    I(s) (índice hasta s+3). En la fecha de decisión t, la última etiqueta calculable es la de
    t − label_lag."""
    mb = {sid: months_back(sid) for sid in (*p.growth_ids, "PCEPILFE")}
    g = sorted(mb[s] for s in p.growth_ids)[p.min_growth_ind - 1] + pace_need(p)
    i = mb["PCEPILFE"] + p.infl_lead
    return {"label_lag": max(g, i), "lag_G": g, "lag_I": i, "months_back": mb}


# ------------------------------------------------------------------ construcción
def make_label(inputs: dict, p: Params, s_G: float, s_I: float,
               cutoff: pd.Timestamp | dict | None = None, splice: float | None = None) -> tuple[pd.DataFrame, dict]:
    """Etiqueta completa a partir de los niveles. Con `cutoff` (fecha, o dict serie → fecha), solo usa
    datos con fecha ≤ cutoff (estudio de revisión, persistencia point-in-time)."""
    levels = inputs["levels"]
    if cutoff is not None:
        cut = cutoff if isinstance(cutoff, dict) else {k: cutoff for k in levels}
        levels = {k: (v[v.index <= cut[k]] if k in cut else v) for k, v in levels.items()}
    gc = growth_components(levels, p)
    g = growth_axis(gc["comp"], p)
    i = inflation_axis(levels, p, splice)
    df = g.join(i, how="outer")
    df = df[df.index >= pd.Timestamp(p.start)]
    ok = df["G"].notna() & df["I"].notna()
    df = df[ok]  # con datos completos no hay huecos; con cortes por serie puede haberlos

    p_g = pd.Series(norm.cdf(df["G"] / s_G), index=df.index).where(df["G"].notna())
    p_i = pd.Series(norm.cdf((df["I"] - p.kappa) / s_I), index=df.index).where(df["I"].notna())
    probs = pd.DataFrame({
        "p_expansion": p_g * (1 - p_i),
        "p_late_cycle": p_g * p_i,
        "p_stagflation": (1 - p_g) * p_i,
        "p_low_growth_disinfl": (1 - p_g) * (1 - p_i),
    })
    n = len(df)
    pos = np.arange(n)
    out = pd.DataFrame(index=df.index)
    out["G"], out["I"] = df["G"], df["I"]
    out["p_g_high"], out["p_i_high"] = p_g, p_i
    out = out.join(probs)
    pc = list(probs.columns)
    out["label_hard"] = probs[pc].idxmax(axis=1).str.replace("p_", "", regex=False)
    out["max_prob"] = probs[pc].max(axis=1)
    out["frontera"] = out["max_prob"] < p.frontier
    out["provisional"] = pos >= n - p.provisional_months
    out["tendencia_truncada"] = (pos < p.truncated_months) | (pos >= n - p.truncated_months)
    out["cobertura_g"] = df["cobertura_g"].astype("int64")
    out["fuente_i"] = df["fuente_i"].astype(str)
    out["usrec"] = inputs["usrec"].reindex(out.index).astype("Int64")
    out["weight"] = np.where(out.index <= pd.Timestamp(p.zero_weight_until), 0.0, 1.0)
    out.index.name = "date"
    gc["splice"] = i.attrs.get("splice")
    return out.reset_index(), gc


def code_sha() -> dict:
    """SHA-256 del código que genera la etiqueta (y el commit de git, si se puede leer)."""
    here = Path(__file__).resolve()
    files = [here, here.parent / "__init__.py"]
    h = hashlib.sha256()
    for f in files:
        h.update(f.read_bytes())
    out = {"sha256_code": h.hexdigest(), "files": [str(f.relative_to(db.REPO)) for f in files]}
    try:
        import subprocess
        out["git_head"] = subprocess.run(["git", "-C", str(db.REPO), "rev-parse", "HEAD"], capture_output=True,
                                         text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(db.REPO), "status", "--porcelain", "--", *out["files"]],
                               capture_output=True, text=True, check=True).stdout.strip()
        out["git_dirty"] = bool(dirty)
    except Exception:  # noqa: BLE001
        pass
    return out


def build_from_inputs(inputs: dict, p: Params = PARAMS, snap_info: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """Construye la etiqueta y su meta solo a partir de `inputs` (sin tocar el warehouse)."""
    gc_full = growth_components(inputs["levels"], p)
    g_full = growth_axis(gc_full["comp"], p)
    i_full = inflation_axis(inputs["levels"], p)
    ok = g_full["G"].notna() & i_full["I"].reindex(g_full.index).notna()
    last = g_full.index[ok].max()
    last_mature = last - pd.DateOffset(months=p.scale_mature_months)
    sc = estimate_scales(inputs, gc_full["comp"], last_mature, p)
    data_end = {sid: str(inputs["levels"][sid].dropna().index.max().date()) for sid in (*p.growth_ids, "PCEPILFE")}
    s_G = p.s_G_fixed if p.s_G_fixed is not None else sc["s_G"]
    s_I = p.s_I_fixed if p.s_I_fixed is not None else sc["s_I"]
    how_G = "fija (ficha §11)" if p.s_G_fixed is not None else sc["how_G"]
    how_I = "fija (ficha §11)" if p.s_I_fixed is not None else sc["how_I"]
    out, gc = make_label(inputs, p, s_G, s_I)
    ll = label_lag(p)
    meta = {
        "version": p.version, "status": "CONGELADA" if p.version.startswith("1.") else "borrador",
        "params": asdict(p), "s_G": float(s_G), "s_I": float(s_I), "how_G": how_G, "how_I": how_I,
        "splice_cpi_core": gc["splice"],
        "alfred_estimates": {"s_G_4ind": sc["detail"]["G_composite"]["mad_sd"],
                             "s_G_indpro_payems": sc["detail"].get("G_composite_INDPRO_PAYEMS", {}).get("mad_sd"),
                             "s_I_pce": sc["detail"]["I_PCEPILFE"]["mad_sd"],
                             "I_first_release_bias_pp": sc["detail"]["I_PCEPILFE"]["mean_err"]},
        "scale_detail": sc["detail"],
        "g_composite_ids": sc["g_composite_ids"], "vintage_origin": sc["vintage_origin"],
        "notes": gc["notes"] + sc["notes"], "aliases_v0_1": ALIASES,
        "usage": {"embargo_months": p.embargo_months,
                  "score_and_train_mask": "weight > 0 and not provisional",
                  "holdout_start": p.holdout_start,
                  "label_lag": ll["label_lag"],
                  "persistence_pit": (f"en la fecha de decisión t, la última etiqueta conocida es la de "
                                      f"t − {ll['label_lag']}, calculada solo con los datos publicados en t "
                                      "(make_label con cutoff por serie); nunca label_hard.shift(k) con "
                                      f"k < {ll['label_lag']} sobre la etiqueta final"),
                  "note": ("la etiqueta de t usa datos hasta t+4, la tendencia hasta t+60 y σ_i toda la muestra; "
                           "nunca es variable (forbidden_features)")},
        "forbidden_features": {"label_columns": sorted(FORBIDDEN_FEATURES),
                               "series": inputs.get("forbidden_series", []),
                               "rule": "ninguna puede ser variable; el arnés llama a assert_no_forbidden"},
        "label_lag": ll, "holdout_start": p.holdout_start,
        "embargo_months": p.embargo_months, "provisional_months": p.provisional_months,
        "sigma_i": {k: v["sigma"] for k, v in gc["comp"].items()},
        "first": str(out["date"].min().date()), "last": str(out["date"].max().date()),
        "data_end": data_end, "last_mature_for_scales": str(last_mature.date()),
        "inputs_snapshot": snap_info,
        "code": code_sha(),
    }
    return out, {"meta": meta, "scales": sc, "components": gc["comp"], "inputs": inputs}


def build(con=None, p: Params = PARAMS, source: str = "snapshot") -> tuple[pd.DataFrame, dict]:
    """source='snapshot': solo desde la instantánea oficial. source='live': desde el warehouse."""
    if source == "snapshot":
        inputs, info = read_snapshot(p)
        return build_from_inputs(inputs, p, info)
    own = con is None
    con = con or db.connect()
    try:
        inputs = load_inputs(con, p)
    finally:
        if own:
            con.close()
    return build_from_inputs(inputs, p, None)


def freeze(p: Params = PARAMS, force: bool = False) -> Path:
    con = db.connect()
    try:
        inputs = load_inputs(con, p)
    finally:
        con.close()
    return write_snapshot(inputs, p, force)


def content_hash(df: pd.DataFrame) -> str:
    num = df.select_dtypes("float").columns
    h = pd.util.hash_pandas_object(df.assign(**{c: df[c].round(12) for c in num}), index=False).values
    return hashlib.sha256(h.tobytes()).hexdigest()


def write(df: pd.DataFrame, meta: dict, p: Params = PARAMS, live: bool = False) -> Path:
    path = out_path(p)
    if live:
        path = path.with_name(path.stem + "_live.parquet")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    meta = dict(meta, sha256_content=content_hash(df), rows=len(df))
    path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=str))
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch-vintages", action="store_true",
                    help="descarga de ALFRED las vintages de W875RX1 y CMRMTSPL a labels/raw/alfred")
    ap.add_argument("--freeze", action="store_true", help="warehouse → instantánea de entradas → etiqueta oficial")
    ap.add_argument("--force", action="store_true", help="con --freeze: sobrescribe la instantánea")
    ap.add_argument("--from-snapshot", action="store_true", help="etiqueta oficial solo desde la instantánea")
    ap.add_argument("--live", action="store_true", help="warehouse de hoy → *_live.parquet (no oficial)")
    args = ap.parse_args()
    if args.fetch_vintages:
        for msg in fetch_extra_vintages():
            print("vintages:", msg)
    if args.freeze:
        print("instantánea:", freeze(force=args.force))
    live = args.live and not (args.freeze or args.from_snapshot)
    if not live and not snapshot_path().exists():
        raise SystemExit(f"no existe {snapshot_path()}: ejecuta con --freeze (o --live)")
    df, info = build(source="live" if live else "snapshot")
    path = write(df, info["meta"], live=live)
    m = info["meta"]
    print(f"etiqueta v{m['version']}{' (LIVE, no oficial)' if live else ''}: {m['first']} → {m['last']} "
          f"({len(df)} meses) → {path}")
    print(f"s_G = {m['s_G']:.3f}, s_I = {m['s_I']:.3f} ({m['how_G']}); empalme IPC→PCE: "
          f"{m['splice_cpi_core']['adj_pp']:+.3f} pp ({m['splice_cpi_core']['from']}…{m['splice_cpi_core']['to']})")
    print(f"label_lag = {m['label_lag']['label_lag']} ({m['label_lag']})")
    if m["inputs_snapshot"]:
        print("entradas:", m["inputs_snapshot"])
    print(df.tail(6)[["date", "G", "I", "label_hard", "max_prob"]].to_string(index=False))
    print("hash salida:", content_hash(df), "| código:", m["code"]["sha256_code"])


if __name__ == "__main__":
    main()
