"""Cross-source consistency: series that measure the same thing in different sources.

Reads the files directly (curated parquet + legacy CSV) so it does not depend on how fresh the
warehouse is. Each pair has a comparison mode and a tolerance; anything beyond it is a finding.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.audit.common import CURATED, LEGACY_BLS, LEGACY_FRED, Finding, fmt, sources

_INDEX: dict[str, str] = {}


def _index() -> dict[str, str]:
    if not _INDEX:
        for src in sources():
            for p in (CURATED / src).glob("*.parquet"):
                _INDEX.setdefault(p.stem, src)
    return _INDEX


def load(ref: str) -> pd.Series:
    """'fred:CPIAUCSL' (curated), 'legacy_fred:CPIAUCSL', 'legacy_bls:CUSR0000SA0'."""
    kind, sid = ref.split(":", 1)
    if kind == "legacy_fred":
        df = pd.read_csv(LEGACY_FRED / f"{sid}.csv", usecols=["date", "value"])
    elif kind == "legacy_bls":
        df = pd.read_csv(LEGACY_BLS / f"{sid}.csv", usecols=["date", "value"])
    else:
        df = pd.read_parquet(CURATED / kind / f"{sid}.parquet")
        if "realtime_end" in df:
            df = df[df["realtime_end"].isna()]
    s = pd.Series(pd.to_numeric(df["value"], errors="coerce").values,
                  index=pd.to_datetime(df["date"]), name=ref).dropna().sort_index()
    return s[~s.index.duplicated(keep="last")]


def to_month(s: pd.Series, how: str = "last") -> pd.Series:
    g = s.groupby(s.index.to_period("M"))
    s = g.mean() if how == "mean" else g.last()
    s.index = s.index.to_timestamp()
    return s


def to_year(s: pd.Series, how: str = "mean") -> pd.Series:
    g = s.groupby(s.index.year)
    out = g.mean() if how == "mean" else (g.last() if how == "last" else g.apply(lambda x: (1 + x).prod() - 1))
    out.index = pd.to_datetime(out.index.astype(str) + "-01-01")
    return out


def compare(a: pd.Series, b: pd.Series, rel: bool = True) -> dict:
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    if j.empty:
        return {"n": 0}
    x, y = j.iloc[:, 0], j.iloc[:, 1]
    d = (x - y).abs() / (y.abs() if rel else 1)
    i = d.idxmax()
    return {"n": len(j), "desde": fmt(j.index.min()), "hasta": fmt(j.index.max()),
            "max_dif": float(d.max()), "fecha_max": fmt(i), "va": float(x[i]), "vb": float(y[i]),
            "mediana_dif": float(d.median()), "corr": float(x.corr(y)) if len(j) > 2 else np.nan}


def yoy_m(s: pd.Series) -> pd.Series:
    s = s.asfreq("MS")
    return (s / s.shift(12) - 1) * 100


# (name, ref_a, ref_b, transform, relative?, tolerance, note)
PAIRS = [
    ("IPC SA nivel: FRED vs BLS legacy", "fred:CPIAUCSL", "legacy_bls:CUSR0000SA0", "level", True, 1e-4, ""),
    ("IPC NSA nivel: FRED vs BLS legacy", "fred:CPIAUCNS", "legacy_bls:CUUR0000SA0", "level", True, 1e-4, ""),
    ("IPC NSA: Shiller vs FRED CPIAUCNS", "shiller:shiller_cpi", "fred:CPIAUCNS", "level", True, 0.005,
     "Shiller usa CPI-U NSA; el último mes es estimado"),
    ("IPC yoy: Shiller vs FRED CPIAUCNS (pp)", "shiller:shiller_cpi", "fred:CPIAUCNS", "yoy", False, 0.3, ""),
    ("Inflación anual dic/dic: Damodaran vs FRED CPIAUCNS (pp)", "damodaran:damodaran_inflation", "fred:CPIAUCNS",
     "dec_dec", False, 0.5, "Damodaran en fracción"),
    ("IPC yoy anual: JST vs FRED CPIAUCNS media anual (pp)", "jst_macrohistory:jst_usa_cpi", "fred:CPIAUCNS",
     "annual_avg_yoy", False, 0.5, ""),
    ("10 años: Shiller GS10 vs FRED GS10 (pp)", "shiller:shiller_gs10", "fred:GS10", "level_m", False, 0.05, ""),
    ("10 años: JST ltrate vs FRED GS10 media anual (pp)", "jst_macrohistory:jst_usa_ltrate", "fred:GS10",
     "annual_avg", False, 0.5, "JST en fracción"),
    ("S&P 500: Shiller precio (media mensual) vs FRED SP500 media mensual", "shiller:shiller_sp_price", "fred:SP500",
     "mean_m", True, 0.01, ""),
    ("S&P 500 TR anual: Shiller (compuesto) vs Damodaran (pp)", "shiller:shiller_nominal_stock_tr_ret_m",
     "damodaran:damodaran_sp500_tr", "annual_compound", False, 3.0, "Shiller usa medias mensuales; Damodaran fin de año"),
    ("Paro: FRED UNRATE vs BLS LNS14000000", "fred:UNRATE", "legacy_bls:LNS14000000", "level", False, 1e-6, ""),
    ("Empleo: FRED PAYEMS vs BLS CES0000000001", "fred:PAYEMS", "legacy_bls:CES0000000001", "level", True, 1e-6, ""),
    ("Salario/hora: FRED vs BLS CES0500000003", "fred:CES0500000003", "legacy_bls:CES0500000003", "level", True, 1e-6, ""),
    ("Participación: FRED CIVPART vs BLS LNS11300000", "fred:CIVPART", "legacy_bls:LNS11300000", "level", False, 1e-6, ""),
    ("Oro: gold_usd_monthly vs WB Pink Sheet (1960+)", "gold:gold_usd_monthly", "wb_pinksheet:wb_gold", "level", True, 0.01, ""),
    ("Oro: datahub vs WB Pink Sheet (1960+)", "gold:gold_datahub_usd_m", "wb_pinksheet:wb_gold", "level", True, 0.01, ""),
    ("Oro: MW Nueva York anual vs media anual gold_usd_monthly", "gold:gold_mw_newyork_usd_a", "gold:gold_usd_monthly",
     "annual_avg", True, 0.01, ""),
    ("Fed funds: FRED FEDFUNDS vs BIS policy rate US (pp)", "bis:bis_cbpol_us", "fred:FEDFUNDS", "level_m", False, 0.5,
     "BIS = objetivo fin de mes; FEDFUNDS = efectivo medio"),
    ("T-bill: Ken French RF mensual x12 vs FRED TB3MS (pp)", "ken_french:ff_rf_m", "fred:TB3MS", "rf", False, 0.5, ""),
    ("Bolsa larga: NBER/Cowles M1125 vs Shiller precio (ret. mensual, pp)", "fred:M1125AUSM343NNBR",
     "shiller:shiller_sp_price", "ret_m", False, 3.0, ""),
]


def _apply(kind: str, a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series]:
    if kind == "level":
        return a, b
    if kind == "level_m":
        return to_month(a), to_month(b)
    if kind == "mean_m":
        return to_month(a, "mean"), to_month(b, "mean")
    if kind == "yoy":
        return yoy_m(to_month(a)), yoy_m(to_month(b))
    if kind == "dec_dec":
        bd = b[b.index.month == 12]
        bd = (bd / bd.shift(1) - 1) * 100
        bd.index = pd.to_datetime(bd.index.year.astype(str) + "-01-01")
        return a * 100, bd
    if kind == "annual_avg_yoy":
        ya = (a / a.shift(1) - 1) * 100
        yb = to_year(b)
        return ya, (yb / yb.shift(1) - 1) * 100
    if kind == "annual_avg":
        scale = 100 if a.abs().max() < 1 else 1
        return a * scale, to_year(b)
    if kind == "annual_compound":
        return to_year(a, "compound") * 100, b * 100
    if kind == "rf":
        return to_month(a) * 12, to_month(b)
    if kind == "ret_m":
        ra, rb = to_month(a).pct_change() * 100, to_month(b).pct_change() * 100
        return ra, rb
    raise ValueError(kind)


def run() -> tuple[list[Finding], pd.DataFrame]:
    out, rows = [], []
    for name, ra, rb, kind, rel, tol, note in PAIRS:
        try:
            a, b = load(ra), load(rb)
        except FileNotFoundError as exc:
            rows.append({"par": name, "a": ra, "b": rb, "error": str(exc)})
            continue
        xa, xb = _apply(kind, a, b)
        r = compare(xa, xb, rel=rel)
        j = pd.concat([xa, xb], axis=1, join="inner").dropna()
        d = ((j.iloc[:, 0] - j.iloc[:, 1]).abs() / (j.iloc[:, 1].abs() if rel else 1)) if len(j) else pd.Series(dtype=float)
        r.update(par=name, a=ra, b=rb, modo=kind, tolerancia=tol, n_fuera=int((d > tol).sum()), nota=note)
        if len(d) and (d > tol).any():
            bad = d[d > tol]
            r["fechas_fuera"] = ",".join(fmt(x) for x in bad.index[:8])
        # coverage: does one side stop earlier?
        r["fin_a"], r["fin_b"] = fmt(a.index.max()), fmt(b.index.max())
        rows.append(r)
        if r.get("n_fuera"):
            share = r["n_fuera"] / max(r["n"], 1)
            sev = "ALTA" if share > 0.05 and tol <= 0.05 else ("MEDIA" if share > 0.01 else "BAJA")
            out.append(Finding("consistencia.entre_fuentes", sev, f"{ra.split(':')[0]}|{rb.split(':')[0]}",
                               f"{ra.split(':')[1]}~{rb.split(':')[1]}",
                               f"{name}: {r['n_fuera']}/{r['n']} obs fuera de tolerancia {tol}"
                               f"{' (relativa)' if rel else ''}; máx {r['max_dif']:.4g} en {r['fecha_max']} "
                               f"({r["va"]:.6g} vs {r["vb"]:.6g})",
                               {"fechas": r.get("fechas_fuera", "")}, note))
    out += legacy_vs_curated(rows)
    return out, pd.DataFrame(rows)


def legacy_vs_curated(rows: list) -> list[Finding]:
    """Every macro/fred legacy CSV against its curated/fred twin (same id)."""
    out = []
    for p in sorted(LEGACY_FRED.glob("*.csv")):
        sid = p.stem
        if not (CURATED / "fred" / f"{sid}.parquet").exists():
            out.append(Finding("consistencia.legacy_sin_curated", "BAJA", "fred_legacy", sid,
                               "serie legacy sin equivalente en curated/fred"))
            continue
        a, b = load(f"legacy_fred:{sid}"), load(f"fred:{sid}")
        r = compare(a, b, rel=True)
        miss_in_cur = a.index.difference(b.index)
        miss_in_leg = b.index.difference(a.index)
        d = pd.concat([a, b], axis=1, join="inner").dropna()
        n_diff = int(((d.iloc[:, 0] - d.iloc[:, 1]).abs() > 1e-9 * d.iloc[:, 1].abs().clip(lower=1)).sum()) if len(d) else 0
        rows.append({"par": f"legacy vs curated {sid}", "a": f"legacy_fred:{sid}", "b": f"fred:{sid}", "modo": "level",
                     **r, "n_dif": n_diff, "solo_legacy": len(miss_in_cur), "solo_curated": len(miss_in_leg),
                     "fin_a": fmt(a.index.max()), "fin_b": fmt(b.index.max())})
        if n_diff or len(miss_in_cur):
            out.append(Finding("consistencia.legacy_vs_curated", "MEDIA" if n_diff else "BAJA", "fred_legacy|fred", sid,
                               f"{n_diff} valores distintos en {r.get('n', 0)} fechas comunes; {len(miss_in_cur)} fechas solo en legacy, "
                               f"{len(miss_in_leg)} solo en curated (legacy termina {fmt(a.index.max())}, curated {fmt(b.index.max())})",
                               {"max_dif_rel": f"{r.get('max_dif', 0):.3g}", "fecha": r.get("fecha_max", "")},
                               "obs_latest ya prioriza curated; retirar legacy del build cuando curated cubra todo"))
    return out
