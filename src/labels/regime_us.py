"""Etiqueta de régimen EE. UU. v0.2 (ficha: docs/models/label_spec.md).

Ejecutar:
    .venv/bin/python -m src.labels.regime_us                    # construye la etiqueta
    .venv/bin/python -m src.labels.regime_us --fetch-vintages   # descarga antes las vintages
                                                                # ALFRED que faltan en el warehouse

La etiqueta es EX POST: usa la última vintage y ventanas CENTRADAS en t (mira meses hacia
delante). Nunca debe entrar como variable de un modelo. Las únicas piezas que usan vintages
(ALFRED) son las escalas s_G y s_I, que miden el ruido de revisión (primera publicación − última
vintage).

Salida: <FIN_DATA_ROOT>/labels/regime_us_v0.2.parquet (+ .meta.json con parámetros, escalas y
hash). `data/archive` es un enlace a FIN_DATA_ROOT, así que queda en data/archive/labels/.
La v0.1 (ventanas hacia atrás) está en git, commit 35a0375.
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
    version: str = "0.2"
    start: str = "1950-01-01"                   # inicio de la muestra de la etiqueta
    growth_ids: tuple[str, ...] = ("INDPRO", "PAYEMS", "W875RX1", "CMRMTSPL")
    min_growth_ind: int = 2                     # mínimo de indicadores para G
    smooth_months: int = 3                      # media de 3 m del nivel, centrada en el mes
    pace_lead: int = 3                          # ritmo: nivel suavizado en t+3 ...
    pace_lag: int = 3                           # ... frente a t−3 (6 m, anualizado ×2)
    trend_half_window: int = 60                 # mediana centrada ±60 meses (10 años)
    mad_k: float = 1.4826
    kappa: float = 2.5                          # umbral de inflación (PCE subyacente, %)
    cpi_core_adj: float = 0.4                   # IPC subyacente − 0,4 pp ≈ PCE subyacente
    infl_lead: int = 3                          # inflación: índice en t+3 ...
    infl_lag: int = 3                           # ... frente a t−3, anualizada
    frontier: float = 0.55                      # máx. prob. < 0,55 → frontera
    provisional_months: int = 24
    truncated_months: int = 60                  # meses con ventana de tendencia truncada
    zero_weight_until: str = "1954-12-01"       # weight = 0 hasta aquí (IPC general, Corea)
    # escalas: estimadas con ALFRED; suelo y valor de reserva
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
def growth_components(con, p: Params = PARAMS) -> dict:
    """Para cada indicador: ritmo g, tendencia τ, σ y z (todo con la última vintage).

    La tendencia y σ se calculan sobre la muestra de la etiqueta (desde p.start); por eso la
    ventana está truncada al principio (1950-1954) y al final (últimos 60 meses)."""
    start = pd.Timestamp(p.start)
    out, notes = {}, []
    for sid in p.growth_ids:
        lv = monthly(con, sid)
        if lv.empty:
            notes.append(f"{sid}: sin datos en obs_latest; se omite")
            continue
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
def inflation_axis(con, p: Params = PARAMS) -> pd.DataFrame:
    """PCE subyacente (desde su primer valor centrado, 1959-04); antes IPC subyacente − 0,4 pp
    (desde 1957-04); antes IPC general (`headline`)."""
    pce = ann_change(monthly(con, "PCEPILFE"), p)
    cpic = ann_change(monthly(con, "CPILFESL"), p) - p.cpi_core_adj
    head = ann_change(monthly(con, "CPIAUCSL"), p)
    idx = pd.date_range(p.start, max(s.dropna().index.max() for s in (pce, cpic, head)), freq="MS")
    pce, cpic, head = (s.reindex(idx) for s in (pce, cpic, head))
    m_pce = idx >= pce.first_valid_index()
    m_cpic = (idx >= cpic.first_valid_index()) & ~m_pce
    m_head = ~m_pce & ~m_cpic
    I = pd.Series(np.nan, index=idx)
    src = pd.Series(None, index=idx, dtype=object)
    I[m_pce], src[m_pce] = pce[m_pce], "pce_core"
    I[m_cpic], src[m_cpic] = cpic[m_cpic], "cpi_core_adj"
    I[m_head], src[m_head] = head[m_head], "headline"
    src[I.isna()] = None
    return pd.DataFrame({"I": I, "fuente_i": src})


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


def estimate_scales(con, comp: dict, last_mature: pd.Timestamp, p: Params = PARAMS) -> dict:
    """s_G y s_I = MAD×1,4826 del error de revisión (primera publicación − última vintage), en
    las unidades del eje (ventanas centradas); solo fechas maduras (≤ last_mature).

    s_G: error del G compuesto con TODOS los indicadores que tienen vintages, en las fechas en que
    todos tienen primera publicación (con W875RX1 y CMRMTSPL, desde ~2013). Se informa también el
    compuesto INDPRO+PAYEMS de toda la muestra. Suelo p.scale_floor; si no es estable, fallback."""
    notes, detail, origins = [], {}, {}
    infl_err = {}
    for sid in ("PCEPILFE", "CPILFESL"):
        v, origins[sid] = load_vintages(con, sid)
        fr = first_release(v, lambda s: ann_change(s, p), p.infl_lead, p)
        fin = ann_change(monthly(con, sid), p)
        e = fr - fin.reindex(fr.index)
        infl_err[sid] = e[e.index <= last_mature]
        detail[f"I_{sid}"] = _scale_from_errors(infl_err[sid], p)
    z_err = {}
    for sid in p.growth_ids:
        v, origins[sid] = load_vintages(con, sid)
        if v.empty or sid not in comp:
            notes.append(f"{sid}: sin vintages ALFRED (ni en el warehouse ni en labels/raw); no entra en s_G")
            continue
        fr = first_release(v, lambda s: pace(s, p), pace_need(p), p)
        fin = pace(monthly(con, sid), p)
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


# ------------------------------------------------------------------ construcción
def build(con=None, p: Params = PARAMS) -> tuple[pd.DataFrame, dict]:
    own = con is None
    con = con or db.connect()
    try:
        gc = growth_components(con, p)
        g = growth_axis(gc["comp"], p)
        i = inflation_axis(con, p)
        df = g.join(i, how="outer")
        df = df[df.index >= pd.Timestamp(p.start)]
        ok = df["G"].notna() & df["I"].notna()
        last = df.index[ok].max()
        df = df.loc[:last]
        last_mature = last - pd.DateOffset(months=p.provisional_months)
        sc = estimate_scales(con, gc["comp"], last_mature, p)
        usrec = db.series(con, "USREC")
        data_end = {sid: str(db.series(con, sid).index.max().date())
                    for sid in (*p.growth_ids, "PCEPILFE")}
    finally:
        if own:
            con.close()

    p_g = pd.Series(norm.cdf(df["G"] / sc["s_G"]), index=df.index).where(df["G"].notna())
    p_i = pd.Series(norm.cdf((df["I"] - p.kappa) / sc["s_I"]), index=df.index).where(df["I"].notna())
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
    out["usrec"] = usrec.reindex(out.index).astype("Int64")
    out["weight"] = np.where(out.index <= pd.Timestamp(p.zero_weight_until), 0.0, 1.0)
    out.index.name = "date"
    out = out.reset_index()
    meta = {
        "version": p.version, "params": asdict(p), "s_G": sc["s_G"], "s_I": sc["s_I"],
        "how_G": sc["how_G"], "how_I": sc["how_I"], "scale_detail": sc["detail"],
        "g_composite_ids": sc["g_composite_ids"], "vintage_origin": sc["vintage_origin"],
        "notes": gc["notes"] + sc["notes"], "aliases_v0_1": ALIASES,
        "sigma_i": {k: v["sigma"] for k, v in gc["comp"].items()},
        "first": str(out["date"].min().date()), "last": str(out["date"].max().date()),
        "data_end": data_end, "last_mature_for_scales": str(last_mature.date()),
    }
    return out, {"meta": meta, "scales": sc, "components": gc["comp"]}


def content_hash(df: pd.DataFrame) -> str:
    num = df.select_dtypes("float").columns
    h = pd.util.hash_pandas_object(df.assign(**{c: df[c].round(12) for c in num}), index=False).values
    return hashlib.sha256(h.tobytes()).hexdigest()


def write(df: pd.DataFrame, meta: dict, p: Params = PARAMS) -> Path:
    path = out_path(p)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    meta = dict(meta, sha256_content=content_hash(df), rows=len(df))
    path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=str))
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch-vintages", action="store_true",
                    help="descarga de ALFRED las vintages de W875RX1 y CMRMTSPL a labels/raw/alfred")
    args = ap.parse_args()
    if args.fetch_vintages:
        for msg in fetch_extra_vintages():
            print("vintages:", msg)
    df, info = build()
    path = write(df, info["meta"])
    m = info["meta"]
    print(f"etiqueta v{m['version']}: {m['first']} → {m['last']} ({len(df)} meses) → {path}")
    print(f"s_G = {m['s_G']:.3f} ({m['how_G']}; {'+'.join(m['g_composite_ids'])}), "
          f"s_I = {m['s_I']:.3f} ({m['how_I']})")
    for k, d in m["scale_detail"].items():
        print(f"  {k}: n={d['n']} sd={d['mad_sd']:.3f} mitades={d['half1']:.3f}/{d['half2']:.3f} "
              f"estable={d['stable']} {d['from']}→{d['to']}")
    for n in m["notes"]:
        print("  nota:", n)
    print(df.tail(6)[["date", "G", "I", "label_hard", "max_prob"]].to_string(index=False))
    print("hash:", content_hash(df))


if __name__ == "__main__":
    main()
