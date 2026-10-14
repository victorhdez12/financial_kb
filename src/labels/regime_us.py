"""Etiqueta de régimen EE. UU. v0.1 (ficha: docs/models/label_spec.md).

Ejecutar:  .venv/bin/python -m src.labels.regime_us

La etiqueta es EX POST: usa la última vintage y ventanas centradas. Nunca debe entrar como
variable de un modelo. Las únicas piezas que usan vintages (ALFRED) son las escalas s_G y s_I,
que miden el ruido de revisión (primera publicación − última vintage).

Salida: <FIN_DATA_ROOT>/labels/regime_us_v0.1.parquet (+ .meta.json con parámetros, escalas y
hash). `data/archive` es un enlace a FIN_DATA_ROOT, así que queda en data/archive/labels/.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from src.warehouse import db


# ------------------------------------------------------------------ parámetros (ficha §11)
@dataclass(frozen=True)
class Params:
    version: str = "0.1"
    start: str = "1950-01-01"                   # inicio de la muestra de la etiqueta
    growth_ids: tuple[str, ...] = ("INDPRO", "PAYEMS", "W875RX1", "CMRMTSPL")
    min_growth_ind: int = 2                     # mínimo de indicadores para G
    smooth_months: int = 3                      # media móvil del nivel
    pace_months: int = 6                        # ventana del ritmo (anualizado ×12/6)
    trend_half_window: int = 60                 # mediana centrada ±60 meses (10 años)
    mad_k: float = 1.4826
    kappa: float = 2.5                          # umbral de inflación (PCE subyacente, %)
    cpi_core_adj: float = 0.4                   # IPC subyacente − 0,4 pp ≈ PCE subyacente
    infl_months: int = 6                        # inflación a 6 m anualizada
    frontier: float = 0.55                      # máx. prob. < 0,55 → frontera
    provisional_months: int = 24
    truncated_months: int = 60                  # meses con ventana de tendencia truncada
    # escalas: estimadas con ALFRED; suelo y valor de reserva
    scale_floor: float = 0.25
    scale_fallback: float = 0.5
    first_release_max_days: int = 75            # primera vintage ≤ 75 días tras fin de mes
    scale_min_n: int = 60                       # mínimo de fechas para una estimación estable
    scale_half_ratio: float = 2.0               # MAD de cada mitad dentro de ×/÷ 2 del total


PARAMS = Params()
QUADRANTS = ("expansion", "late_cycle", "stagflation", "slowdown")


def out_dir() -> Path:
    return db.DATA_ROOT / "labels"


def out_path(p: Params = PARAMS) -> Path:
    return out_dir() / f"regime_us_v{p.version}.parquet"


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
    """Ritmo: variación log a 6 m de la media de 3 m del nivel, anualizada, en %."""
    sm = level.rolling(p.smooth_months, min_periods=p.smooth_months).mean()
    return 100 * (12 / p.pace_months) * (np.log(sm) - np.log(sm.shift(p.pace_months)))


def ann_change(level: pd.Series, p: Params = PARAMS) -> pd.Series:
    """Inflación: variación a 6 m del índice, anualizada, en %."""
    return 100 * ((level / level.shift(p.infl_months)) ** (12 / p.infl_months) - 1)


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
    """PCE subyacente (desde su primer 6 m, 1959-07); antes IPC subyacente − 0,4 pp (desde
    1957-07); antes IPC general (`headline`)."""
    pce = ann_change(monthly(con, "PCEPILFE"), p)
    cpic = ann_change(monthly(con, "CPILFESL"), p) - p.cpi_core_adj
    head = ann_change(monthly(con, "CPIAUCSL"), p)
    idx = pd.date_range(p.start, max(s.dropna().index.max() for s in (pce, cpic, head)), freq="MS")
    pce, cpic, head = (s.reindex(idx) for s in (pce, cpic, head))
    first_pce = pce.first_valid_index()
    first_cpic = cpic.first_valid_index()
    I = pd.Series(np.nan, index=idx)
    src = pd.Series(None, index=idx, dtype=object)
    m_pce = idx >= first_pce
    m_cpic = (idx >= first_cpic) & ~m_pce
    m_head = ~m_pce & ~m_cpic
    I[m_pce], src[m_pce] = pce[m_pce], "pce_core"
    I[m_cpic], src[m_cpic] = cpic[m_cpic], "cpi_core_adj"
    I[m_head], src[m_head] = head[m_head], "headline"
    src[I.isna()] = None
    return pd.DataFrame({"I": I, "fuente_i": src})


# ------------------------------------------------------------------ escalas con ALFRED
def load_vintages(con, sid: str) -> pd.DataFrame:
    df = con.execute(
        "select date, value, realtime_start, realtime_end from vintages where series_id = ?", [sid]
    ).df()
    for c in ("date", "realtime_start", "realtime_end"):
        df[c] = pd.to_datetime(df[c])
    return df


def first_release(v: pd.DataFrame, fn, p: Params = PARAMS) -> pd.Series:
    """Para cada fecha de referencia t cuya primera vintage sale ≤ p.first_release_max_days tras
    el fin de mes (es decir, una primera publicación real y no el inicio del archivo ALFRED),
    reconstruye la serie tal como estaba en esa vintage y aplica `fn` (que devuelve el valor
    transformado en t)."""
    if v.empty:
        return pd.Series(dtype=float)
    r0 = v.groupby("date")["realtime_start"].min()
    lag = (r0 - (r0.index + pd.offsets.MonthEnd(0))).dt.days
    # fuera las fechas cuya "primera" vintage es el inicio del archivo ALFRED (no es 1.ª publicación)
    r0 = r0[(lag >= 0) & (lag <= p.first_release_max_days) & (r0 > v["realtime_start"].min())]
    rs, re_ = v["realtime_start"].values, v["realtime_end"].fillna(pd.Timestamp("2262-01-01")).values
    dates, vals = v["date"].values, v["value"].values
    out = {}
    for t, r in r0.items():
        rr = np.datetime64(r)
        m = (rs <= rr) & (re_ >= rr) & (dates <= np.datetime64(t))
        snap = pd.Series(vals[m], index=pd.DatetimeIndex(dates[m])).sort_index()
        snap = snap[~snap.index.duplicated(keep="last")]
        snap = snap.reindex(pd.date_range(t - pd.DateOffset(months=12), t, freq="MS"))
        try:
            out[t] = float(fn(snap).loc[t])
        except Exception:
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
    las unidades del eje; solo fechas maduras (≤ last_mature) para que la "última vintage" no
    sea a su vez provisional. Suelo p.scale_floor; si no es estable, p.scale_fallback."""
    notes, detail = [], {}
    # --- I
    infl_err = {}
    for sid, adj in (("PCEPILFE", 0.0), ("CPILFESL", 0.0)):
        v = load_vintages(con, sid)
        fr = first_release(v, lambda s: ann_change(s, p), p)
        fin = ann_change(monthly(con, sid), p)
        e = (fr - fin.reindex(fr.index))
        infl_err[sid] = e[e.index <= last_mature]
        detail[f"I_{sid}"] = _scale_from_errors(infl_err[sid], p)
    # --- G (en z: error del ritmo / σ_i del indicador)
    z_err = {}
    for sid in p.growth_ids:
        v = load_vintages(con, sid)
        if v.empty or sid not in comp:
            notes.append(f"{sid}: sin vintages ALFRED en `vintages`; no entra en s_G")
            continue
        fr = first_release(v, lambda s: pace(s, p), p)
        fin = pace(monthly(con, sid), p)
        e = (fr - fin.reindex(fr.index)) / comp[sid]["sigma"]
        z_err[sid] = e[(e.index <= last_mature) & (e.index >= pd.Timestamp(p.start))]
        detail[f"G_z_{sid}"] = _scale_from_errors(z_err[sid], p)
    zdf = pd.DataFrame(z_err)
    comp_err = zdf.mean(axis=1).where(zdf.notna().sum(axis=1) == zdf.shape[1])
    detail["G_composite"] = _scale_from_errors(comp_err, p)

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
            "detail": detail, "notes": notes,
            "errors": {"I": infl_err, "G": z_err, "G_composite": comp_err}}


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
    finally:
        if own:
            con.close()

    p_g = pd.Series(norm.cdf(df["G"] / sc["s_G"]), index=df.index).where(df["G"].notna())
    p_i = pd.Series(norm.cdf((df["I"] - p.kappa) / sc["s_I"]), index=df.index).where(df["I"].notna())
    probs = pd.DataFrame({
        "p_expansion": p_g * (1 - p_i),
        "p_late_cycle": p_g * p_i,
        "p_stagflation": (1 - p_g) * p_i,
        "p_slowdown": (1 - p_g) * (1 - p_i),
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
    out.index.name = "date"
    out = out.reset_index()
    meta = {
        "version": p.version, "params": asdict(p), "s_G": sc["s_G"], "s_I": sc["s_I"],
        "how_G": sc["how_G"], "how_I": sc["how_I"], "scale_detail": sc["detail"],
        "notes": gc["notes"] + sc["notes"],
        "sigma_i": {k: v["sigma"] for k, v in gc["comp"].items()},
        "first": str(out["date"].min().date()), "last": str(out["date"].max().date()),
        "last_mature_for_scales": str(last_mature.date()),
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
    df, info = build()
    path = write(df, info["meta"])
    m = info["meta"]
    print(f"etiqueta v{m['version']}: {m['first']} → {m['last']} ({len(df)} meses) → {path}")
    print(f"s_G = {m['s_G']:.3f} ({m['how_G']}), s_I = {m['s_I']:.3f} ({m['how_I']})")
    for k, d in m["scale_detail"].items():
        print(f"  {k}: n={d['n']} sd={d['mad_sd']:.3f} mitades={d['half1']:.3f}/{d['half2']:.3f} "
              f"estable={d['stable']} {d['from']}→{d['to']}")
    for n in m["notes"]:
        print("  nota:", n)
    print(df.tail(6)[["date", "G", "I", "label_hard", "max_prob"]].to_string(index=False))
    print("hash:", content_hash(df))


if __name__ == "__main__":
    main()
