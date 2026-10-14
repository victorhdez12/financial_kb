"""Historical analogs of the current macro state and what assets did afterwards.

Distance: diagonal Mahalanobis (each dimension divided by its historical std) over the vector of
point-in-time z-scores in regime_monthly. Candidates within ±24 months of today are excluded and
only one representative per episode is kept (greedy: after picking the nearest month, all months
within ±24 months of it are removed). Forward returns are ex-post outcomes of PAST analog dates,
so they are not look-ahead with respect to today.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.warehouse import db

ANALOG_DIMS = ["G", "G_d6", "z_core_gap", "z_curve", "z_real_ff", "z_baa_spread", "liquidity_score"]
EXCLUDE_MONTHS = 24
MIN_DIMS = 5
HORIZON = 12

# asset -> list of (series_id pattern, kind). kind: 'ret_frac' monthly return fraction,
# 'ret_pct' monthly return in %, 'level' price level, 'yield' 10y yield (duration approx.)
ASSET_SOURCES = {
    "acciones EE. UU. (TR)": [("^shiller_nominal_stock_tr_ret_m$", "ret_frac"), ("^ff_mkt_rf_m$", "ret_pct_plus_rf"),
                              ("^SP500$", "level")],
    "bonos 10a (TR)": [("^shiller_nominal_bond_tr_ret_m$", "ret_frac"), ("^GS10$", "yield"), ("^DGS10$", "yield")],
    "oro": [("^gold_usd_monthly$", "level"), ("^wb_gold$", "level")],
}
# first month in which an asset had a market price. Gold was fixed by the US Treasury
# ($20.67 to 1933, $35 to 1971) and `gold_usd_monthly` repeats annual averages before 1960, so its
# "returns" before the end of convertibility (Aug 1971) are artificial zeros, not outcomes.
ASSET_VALID_FROM = {"oro": pd.Timestamp("1971-08-31")}


def _to_month(s: pd.Series) -> pd.Series:
    s = s.copy()
    s.index = s.index + pd.offsets.MonthEnd(0)
    return s.groupby(level=0).last()


def bond_return_from_yield(y: pd.Series, duration: float = 7.5) -> pd.Series:
    """Approximate 10y total return: carry y/12 minus duration x change in yield (in %)."""
    y = _to_month(y)
    return (y.shift(1) / 1200) - duration * (y.diff() / 100)


def monthly_returns(con) -> tuple[dict[str, pd.Series], dict[str, str]]:
    rets, used = {}, {}
    for asset, options in ASSET_SOURCES.items():
        for pat, kind in options:
            sid = db.find_series(con, [pat])
            if sid is None:
                continue
            s = db.series(con, sid)
            if kind == "ret_frac":
                r = _to_month(s)
            elif kind == "ret_pct_plus_rf":
                rf = _to_month(db.series(con, "ff_rf_m"))
                r = (_to_month(s) + rf.reindex(_to_month(s).index).fillna(0)) / 100
            elif kind == "yield":
                r = bond_return_from_yield(s)
            else:
                r = _to_month(s).pct_change()
            r = r.dropna()
            if asset in ASSET_VALID_FROM:
                r = r[r.index >= ASSET_VALID_FROM[asset]]
            rets[asset], used[asset] = r, sid
            break
    return rets, used


def forward_return(r: pd.Series, d: pd.Timestamp, h: int = HORIZON) -> float | None:
    """Compounded return over the h months AFTER month d (d's own return excluded)."""
    fwd = r[(r.index > d) & (r.index <= d + pd.offsets.MonthEnd(h))]
    if len(fwd) < h:
        return None
    return float((1 + fwd).prod() - 1) * 100


def distances(rm: pd.DataFrame, now: pd.Series) -> pd.Series:
    X = rm[ANALOG_DIMS]
    sd = X.std()
    diff = (X - now[ANALOG_DIMS].astype(float)) / sd
    n = diff.notna().sum(axis=1)
    dist = np.sqrt((diff ** 2).sum(axis=1) / n)  # RMS over common dims (comparable across coverage)
    return dist.where(n >= MIN_DIMS)


def pick_analogs(dist: pd.Series, today: pd.Timestamp, k: int = 5) -> list[pd.Timestamp]:
    cand = dist.dropna()
    cand = cand[(cand.index < today - pd.DateOffset(months=EXCLUDE_MONTHS))]
    picks = []
    while len(picks) < k and not cand.empty:
        d = cand.idxmin()
        picks.append(d)
        lo, hi = d - pd.DateOffset(months=EXCLUDE_MONTHS), d + pd.DateOffset(months=EXCLUDE_MONTHS)
        cand = cand[(cand.index < lo) | (cand.index > hi)]
    return picks


MAJOR_TYPES = {"war", "banking_crisis", "market_crash", "recession", "pandemic", "oil_shock", "credit_event",
               "sovereign_default", "policy"}


def nearby_events(con, d: pd.Timestamp, months: int = 12, k: int = 3) -> list[str]:
    """Events overlapping d ± `months`; multi-decade spells (e.g. 1918-1986 defaults) are skipped;
    US/global and major event types first, then closest start date."""
    if not db.has_table(con, "events"):
        return []
    ev = con.execute(
        """select name, type, country, start_date, end_date from events
           where start_date <= ? and coalesce(end_date, start_date) >= ?
             and date_diff('year', start_date, coalesce(end_date, start_date)) <= 3""",
        [(d + pd.DateOffset(months=months)).date(), (d - pd.DateOffset(months=months)).date()]).df()
    if ev.empty:
        return []
    ev["us"] = ev["country"].fillna("").str.contains("USA|United States|US$|^US;|World|Global", regex=True)
    ev["major"] = ev["type"].isin(MAJOR_TYPES)
    ev["gap"] = (pd.to_datetime(ev["start_date"]) - d).abs().dt.days
    ev = ev.sort_values(["us", "major", "gap"], ascending=[False, False, True]).drop_duplicates("name")
    return [f"{r['name']} ({pd.Timestamp(r['start_date']):%Y-%m})" for _, r in ev.head(k).iterrows()]


def find_analogs(con, rm: pd.DataFrame, k: int = 5) -> tuple[list[dict], dict]:
    rm = rm.set_index("date") if "date" in rm.columns else rm
    now = rm.iloc[-1]
    dist = distances(rm, now)
    picks = pick_analogs(dist, rm.index[-1], k)
    rets, used = monthly_returns(con)
    usrec = _to_month(db.series(con, "USREC"))
    out = []
    for d in picks:
        row = rm.loc[d]
        fwd = {a: forward_return(r, d) for a, r in rets.items()}
        rec12 = usrec[(usrec.index > d) & (usrec.index <= d + pd.offsets.MonthEnd(12))]
        out.append({
            "date": f"{d:%Y-%m}", "distance": round(float(dist[d]), 2),
            "quadrant": row["quadrant"], "debt_phase": row["debt_phase"], "credit_light": row["credit_light"],
            "G": _r(row["G"]), "core_6m": _r(row["core_6m"]),
            "fwd_12m_pct": {a: _r(v, 1) for a, v in fwd.items()},
            "G_12m_later": _r(rm["G"].get(d + pd.offsets.MonthEnd(12))),
            "nber_recession_next_12m": bool((rec12 == 1).any()) if len(rec12) else None,
            "events": nearby_events(con, d),
        })
    return out, {"dims": ANALOG_DIMS, "return_series": used, "horizon_months": HORIZON}


def _r(v, n: int = 2):
    try:
        return None if v is None or pd.isna(v) else round(float(v), n)
    except (TypeError, ValueError):
        return None
