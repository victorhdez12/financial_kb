"""Missing periods in the series the regime classifier uses, and their effect on positional shifts.

`src.warehouse.db.series` drops NULL values and `src.regime.features` transforms (yoy, ann6m,
qoq_ann, d12, sahm) use `shift(k)` by POSITION. When a month is missing, the observation k rows
back is k+1 months back (e.g. the 'yoy' of Nov-2025 CPI compares with Oct-2024: 13 months).

For every feature/candidate this module:
  1. lists calendar periods absent from the series as the classifier sees it;
  2. recomputes the transform on a calendar-complete index (missing -> NaN) and counts the
     observations whose value changes (or that should not exist at all);
  3. propagates both versions to the month-end decision grid with the classifier's own
     `asof_on_grid` and reports the grid months that differ and the max difference;
  4. repeats (3) for the ALFRED-vintage path (`vintage_asof` also does `snap.dropna()`).
Only reads: warehouse opened read_only; the regime code is imported, not modified.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.audit.common import Finding, fmt
from src.regime import asof
from src.regime.features import FEATURES, level

try:  # the classifier's own pre-transform step (2026-10-12 fix); audit what it really computes
    from src.regime.features import regularize as _classifier_prep
except ImportError:  # pre-fix code: transforms ran directly on the gappy series
    def _classifier_prep(s: pd.Series) -> pd.Series:
        return s
from src.warehouse import db

FREQ_RULE = {"M": "MS", "Q": "QS"}


def calendar_fn(fn, s: pd.Series, freq: str) -> pd.Series:
    """Apply fn on a calendar-complete index (missing periods = NaN) and return it on s.index."""
    full = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq=FREQ_RULE[freq]))
    return fn(full).reindex(s.index)


def _cmp(a: pd.Series, b: pd.Series, tol: float = 1e-9) -> pd.Series:
    """Boolean: positions where a and b disagree (value differs, or one is NaN and the other not)."""
    both = a.notna() & b.notna()
    return (both & ((a - b).abs() > tol)) | (a.notna() ^ b.notna())


def analyse(con, today: pd.Timestamp, vintage_tail_months: int = 24) -> tuple[list[Finding], pd.DataFrame]:
    grid = asof.month_grid("1947-01-31", today.date())
    out: list[Finding] = []
    rows = []
    seen_v: set[tuple[str, str]] = set()
    for f in FEATURES:
        for rank, sid in enumerate(f.sids):
            s = db.series(con, sid)
            if s.empty:
                rows.append(dict(feature=f.name, series_id=sid, rank=rank, status="sin datos en warehouse"))
                continue
            freq = asof.infer_freq(s.index)
            rec = dict(feature=f.name, series_id=sid, rank=rank, freq=freq, transform=f.fn.__name__,
                       first=fmt(s.index.min()), last=fmt(s.index.max()), n=len(s))
            if freq in FREQ_RULE:
                exp = pd.date_range(s.index.min(), s.index.max(), freq=FREQ_RULE[freq])
                miss = exp.difference(s.index)
                rec["missing"] = ",".join(fmt(d) for d in miss)
                rec["n_missing"] = len(miss)
            else:  # D / W: report the longest gap only
                gaps = np.diff(s.index.values).astype("timedelta64[D]").astype(int)
                rec["n_missing"] = 0
                rec["max_gap_days"] = int(gaps.max()) if len(gaps) else 0
            if f.fn is level or freq not in FREQ_RULE or rec["n_missing"] == 0:
                rec["status"] = "ok" if rec.get("n_missing", 0) == 0 else "hueco sin efecto (nivel)"
                rows.append(rec)
                continue
            pos = f.fn(_classifier_prep(s)).reindex(s.index)
            cal = calendar_fn(f.fn, s, freq)
            bad = _cmp(pos, cal)
            rec["obs_afectadas"] = int(bad.sum())
            rec["obs_afectadas_fechas"] = ",".join(fmt(d) for d in bad[bad].index[:24])
            dif = (pos - cal).abs()
            rec["max_dif_obs"] = float(dif.max()) if dif.notna().any() else np.nan
            g_pos = asof.asof_on_grid(pos, sid, grid)
            g_cal = asof.asof_on_grid(cal, sid, grid)
            gbad = _cmp(g_pos, g_cal)
            rec["meses_grid_afectados"] = int(gbad.sum())
            rec["grid_fechas"] = ",".join(fmt(d) for d in gbad[gbad].index)
            gd = (g_pos - g_cal).abs()
            rec["max_dif_grid"] = float(gd.max()) if gd.notna().any() else np.nan
            if gbad.any():
                d0 = gd.idxmax() if gd.notna().any() else gbad[gbad].index[0]
                rec["peor_mes"] = fmt(d0)
                rec["peor_pos"] = g_pos.get(d0)
                rec["peor_cal"] = g_cal.get(d0)
            # vintage path (ALFRED), only for the first candidate as in build_feature
            if f.vintage and rank == 0 and (f.name, sid) not in seen_v:
                seen_v.add((f.name, sid))
                v = db.vintages(con, sid)
                if not v.empty:
                    tail = grid[grid["date"] >= miss.min()].head(vintage_tail_months) if len(miss) else grid.iloc[:0]
                    vp = asof.vintage_asof(v, tail, lambda snap: f.fn(_classifier_prep(snap)).dropna().iloc[-1])
                    vc = asof.vintage_asof(
                        v, tail, lambda snap: calendar_fn(f.fn, snap, freq).dropna().iloc[-1])
                    vbad = _cmp(vp, vc)
                    rec["vintage_meses_afectados"] = int(vbad.sum())
                    vd = (vp - vc).abs()
                    rec["vintage_max_dif"] = float(vd.max()) if vd.notna().any() else np.nan
                    rec["vintage_fechas"] = ",".join(fmt(d) for d in vbad[vbad].index)
            rec["status"] = "AFECTADA" if (rec["meses_grid_afectados"] or rec.get("vintage_meses_afectados")) else "hueco sin efecto"
            rows.append(rec)
    df = pd.DataFrame(rows)
    for r in df[df["status"] == "AFECTADA"].to_dict("records"):
        primary = r["rank"] == 0
        sev = "CRITICA" if primary and r.get("max_dif_grid", 0) and r["max_dif_grid"] > 0.1 else "ALTA"
        out.append(Finding(
            "clasificador.shift_posicional", sev, "warehouse", r["series_id"],
            f"feature {r['feature']} ({r['transform']}): huecos {r['missing']} -> {r['obs_afectadas']} obs y "
            f"{r['meses_grid_afectados']} meses del grid alterados; máx |dif| grid = {r.get('max_dif_grid', np.nan):.3f}"
            + (f"; ruta ALFRED: {r.get('vintage_meses_afectados', 0)} meses, máx {r.get('vintage_max_dif', np.nan):.3f}"
               if "vintage_meses_afectados" in r and pd.notna(r.get("vintage_meses_afectados")) else ""),
            {"peor_mes": r.get("peor_mes"), "posicional": round(float(r.get("peor_pos", np.nan)), 3),
             "calendario": round(float(r.get("peor_cal", np.nan)), 3), "candidato": r["rank"]},
            "features.py: reindexar a calendario completo (asfreq MS/QS) antes de f.fn y en vintage_asof "
            "(o usar shift(freq=...)); db.series no debe ocultar huecos: devolver NaN explícitos"))
    return out, df


def _calendarised(fn):
    """Wrap a features.py transform so it runs on a calendar-complete index (M/Q)."""
    def g(s: pd.Series) -> pd.Series:
        freq = asof.infer_freq(s.index)
        if freq not in FREQ_RULE or s.empty:
            return fn(s)
        return calendar_fn(fn, s, freq)
    g.__name__ = fn.__name__
    return g


def regime_impact(con, today: pd.Timestamp, months: int = 14) -> pd.DataFrame:
    """Rebuild the regime panel in memory twice (current code vs calendar-complete transforms) and
    compare the classifier outputs for the last `months` months. Nothing is written."""
    import dataclasses

    from src.regime import features as F
    from src.regime.run import classify_all

    grid = asof.month_grid(today=today.date())
    base_panel, _ = F.build_panel(con, grid)
    orig = list(F.FEATURES)
    try:
        F.FEATURES[:] = [dataclasses.replace(f, fn=_calendarised(f.fn)) if f.fn is not level else f for f in orig]
        fix_panel, _ = F.build_panel(con, grid)
    finally:
        F.FEATURES[:] = orig
    a, b = classify_all(base_panel), classify_all(fix_panel)
    cols = ["G", "G_state", "I", "I_state", "quadrant", "sahm_trigger", "core_accel_3m", "z_core_gap"]
    pcols = ["core_6m", "infl_yoy", "real_ff", "sahm", "unrate_d12", "headline_cpi_yoy", "core_cpi_yoy"]
    tail = a.index[-months:]
    rows = []
    for d in tail:
        r = {"date": fmt(d)}
        for c in pcols:
            r[f"{c}_actual"], r[f"{c}_corr"] = base_panel.loc[d, c], fix_panel.loc[d, c]
        for c in cols:
            r[f"{c}_actual"], r[f"{c}_corr"] = a.loc[d, c], b.loc[d, c]
        rows.append(r)
    return pd.DataFrame(rows)
