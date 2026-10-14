"""Monthly point-in-time feature panel built from the warehouse.

Each feature = (candidate series ids in priority order, transform on the observation index,
whether ALFRED vintages should be used). See asof.py for the anti look-ahead rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from src.regime.asof import asof_on_grid, infer_freq, vintage_asof
from src.warehouse import db


# ---------------------------------------------------------------- transforms (observation index)
CAL_FREQ = {"M": "MS", "Q": "QS", "A": "YS"}


def regularize(s: pd.Series) -> pd.Series:
    """Reindex a monthly/quarterly/annual series onto its full calendar so that a missing
    observation (e.g. CPI Oct-2025, never published after the 2025 shutdown) becomes NaN instead of
    silently disappearing. Position-based shifts (yoy = shift(12)) are then calendar-correct:
    yoy and 6m changes that would need the missing month are NaN, not a 13-month change.
    Daily/weekly series and series not dated at period start are returned unchanged."""
    s = s.dropna()
    if len(s) < 3:
        return s
    freq = infer_freq(s.index)
    cal = CAL_FREQ.get(freq)
    if cal is None:
        return s
    full = pd.date_range(s.index.min(), s.index.max(), freq=cal)
    if not s.index.isin(full).all():
        return s
    return s.reindex(full)


def _periods_per_year(s: pd.Series) -> int:
    return {"D": 252, "W": 52, "M": 12, "Q": 4, "A": 1}[infer_freq(s.index)]


def level(s: pd.Series) -> pd.Series:
    return s


def yoy(s: pd.Series) -> pd.Series:
    return (s / s.shift(_periods_per_year(s)) - 1) * 100


def ann6m(s: pd.Series) -> pd.Series:
    return ((s / s.shift(6)) ** 2 - 1) * 100


def qoq_ann(s: pd.Series) -> pd.Series:
    return ((s / s.shift(1)) ** 4 - 1) * 100


def d12(s: pd.Series) -> pd.Series:
    return s - s.shift(12)


def sahm(s: pd.Series) -> pd.Series:
    """Sahm rule: 3m avg unemployment minus the minimum 3m avg of the previous 12 months.

    A single missing month (NaN after `regularize`) must not blank the rule for a year: the 3m
    average needs 2 of 3 months (but is never produced for the missing month itself) and the
    12-month minimum needs 11 of 12."""
    m3 = s.rolling(3, min_periods=2).mean().where(s.notna())
    return m3 - m3.shift(1).rolling(12, min_periods=11).min()


@dataclass(frozen=True)
class Feature:
    name: str
    sids: tuple[str, ...]
    fn: Callable[[pd.Series], pd.Series] = level
    vintage: bool = False  # True for growth/inflation inputs (ALFRED if available)


FEATURES: list[Feature] = [
    # growth
    Feature("indpro_yoy", ("INDPRO",), yoy, True),
    Feature("payems_yoy", ("PAYEMS", "bls_CES0000000001"), yoy, True),
    Feature("gdp_qoq_ann", ("GDPC1",), qoq_ann, True),
    Feature("unrate", ("UNRATE", "bls_LNS14000000"), level, True),
    Feature("unrate_d12", ("UNRATE", "bls_LNS14000000"), d12, True),
    Feature("sahm", ("UNRATE", "bls_LNS14000000"), sahm, True),
    Feature("tcu", ("TCU",), level, True),
    Feature("cfnai", ("CFNAI",), level, True),
    # inflation
    Feature("core_cpi_6m", ("CPILFESL",), ann6m, True),
    Feature("core_pce_6m", ("PCEPILFE",), ann6m, True),
    Feature("headline_cpi_6m", ("CPIAUCSL", "bls_CUSR0000SA0"), ann6m, True),
    Feature("core_cpi_yoy", ("CPILFESL",), yoy, True),
    Feature("headline_cpi_yoy", ("CPIAUCSL", "bls_CUSR0000SA0"), yoy, True),
    Feature("ppi_yoy", ("PPIACO",), yoy, True),
    Feature("t5yie", ("T5YIE",)),
    # rates / curve
    Feature("fedfunds", ("FEDFUNDS", "DFF")),
    Feature("dgs10", ("DGS10", "GS10", "shiller_gs10")),
    Feature("gs10", ("GS10", "shiller_gs10")),
    Feature("tb3", ("DGS3MO", "TB3MS")),
    Feature("tb3ms", ("TB3MS",)),
    Feature("t10y3m", ("T10Y3M",)),
    Feature("dfii10", ("DFII10",)),
    # credit / stress
    Feature("baa10y", ("BAA10Y",)),
    Feature("baa", ("BAA",)),
    Feature("hy_oas", ("BAMLH0A0HYM2",)),
    Feature("ig_oas", ("BAMLC0A0CM",)),
    Feature("nfci", ("NFCI",)),
    Feature("anfci", ("ANFCI",)),
    Feature("nfci_credit", ("NFCICREDIT",)),
    Feature("nfci_leverage", ("NFCILEVERAGE",)),
    Feature("nfci_risk", ("NFCIRISK",)),
    Feature("stlfsi", ("STLFSI4", "STLFSI3", "STLFSI2")),
    Feature("sloos_ci", ("DRTSCILM",)),
    Feature("delinq_all", ("DRALACBS", "DRALACBN")),
    Feature("delinq_cc", ("DRCCLACBS",)),
    Feature("ted", ("TEDRATE",)),
    Feature("vix", ("VIXCLS",)),
    # liquidity
    Feature("m2_yoy", ("M2SL",), yoy, True),
    Feature("gdp_nom_yoy", ("GDP",), yoy, True),
    Feature("walcl", ("WALCL",)),
    Feature("walcl_yoy", ("WALCL",), yoy),
    Feature("tga", ("WTREGEN",)),
    Feature("rrp", ("RRPONTSYD",)),
    # long cycle
    Feature("debt_gdp", ("GFDEGDQ188S",)),
    Feature("deficit_gdp", ("FYFSGDA188S",)),
    Feature("fed_interest", ("A091RC1Q027SBEA",)),
    Feature("fed_receipts", ("W006RC1Q027SBEA",)),
    Feature("private_credit_gdp", ("QUSPAM770A",)),
]


# fallback when the curated catalog has no units yet (FRED units as of 2026)
KNOWN_UNITS = {"WALCL": "Millions", "WTREGEN": "Millions", "RRPONTSYD": "Billions"}


def to_billions(con, sid: str, s: pd.Series) -> pd.Series:
    """Scale to USD billions using the catalog units (WALCL is in millions, TGA/RRP in billions)."""
    row = con.execute("select units from catalog where series_id = ? and units is not null limit 1",
                      [sid]).fetchone()
    units = (row[0] if row else KNOWN_UNITS.get(sid, "")).lower()
    if "million" in units:
        return s / 1000
    if "trillion" in units:
        return s * 1000
    return s


def build_feature(con, f: Feature, grid: pd.DataFrame, use_vintages: bool):
    """Return (values on grid, came_from_vintage bool series, chosen sid, last obs date)."""
    flag = pd.Series(False, index=grid["date"].values)
    vals = pd.Series(np.nan, index=grid["date"].values)
    sid, raw = None, None
    # splice candidates in priority order: the first series wins wherever it has data,
    # later candidates only fill dates it does not cover (e.g. DGS10 1962+, then Shiller GS10)
    for cand in f.sids:
        s = db.series(con, cand)
        if s.empty:
            continue
        if f.name in ("walcl", "tga", "rrp"):
            s = to_billions(con, cand, s)
        vals = vals.combine_first(asof_on_grid(f.fn(regularize(s)), cand, grid))
        if sid is None:
            sid, raw = cand, s
    if sid is None:
        return vals, flag, None, None
    if f.vintage and use_vintages:
        v = db.vintages(con, sid)
        if not v.empty:
            vv = vintage_asof(v, grid, lambda snap: f.fn(regularize(snap)).dropna().iloc[-1])
            flag = vv.notna()
            vals = vv.combine_first(vals)
    return vals, flag, sid, raw.index.max()


def build_panel(con, grid: pd.DataFrame, use_vintages: bool = True) -> tuple[pd.DataFrame, dict]:
    panel = pd.DataFrame(index=grid["date"].values)
    meta: dict = {"sources": {}, "vintage_features": []}
    for f in FEATURES:
        vals, flag, sid, last = build_feature(con, f, grid, use_vintages)
        panel[f.name] = vals.values
        if f.vintage:
            panel[f"_v_{f.name}"] = flag.values
            if flag.any():
                meta["vintage_features"].append(f.name)
        meta["sources"][f.name] = {"series_id": sid, "last_obs": str(last.date()) if last is not None else None}
    panel.index.name = "date"
    return derive(panel), meta


def derive(p: pd.DataFrame) -> pd.DataFrame:
    """Composite raw features that combine several series (all inputs already point-in-time)."""
    p = p.copy()
    p["core_6m"] = p[["core_cpi_6m", "core_pce_6m"]].mean(axis=1)
    p["core_is_headline_proxy"] = p["core_6m"].isna() & p["headline_cpi_6m"].notna()
    p["core_6m"] = p["core_6m"].fillna(p["headline_cpi_6m"])  # pre-1957: headline CPI proxy
    p["infl_yoy"] = p["core_cpi_yoy"].fillna(p["headline_cpi_yoy"])
    p["real_ff"] = p["fedfunds"] - p["infl_yoy"]
    # 10y-3m curve: official T10Y3M (1982+), then monthly GS10-TB3MS, then 10y - fed funds
    p["curve"] = (p["t10y3m"].combine_first(p["gs10"] - p["tb3ms"])
                  .combine_first(p["dgs10"] - p["tb3"]).combine_first(p["dgs10"] - p["fedfunds"]))
    # Moody's Baa - 10y Treasury: daily BAA10Y (1986+), else monthly BAA - GS10
    p["baa_spread"] = p["baa10y"].combine_first(p["baa"] - p["gs10"])
    p["net_liquidity"] = p["walcl"] - p["tga"].fillna(0) - p["rrp"].fillna(0)
    p.loc[p["tga"].isna(), "net_liquidity"] = np.nan  # only meaningful once TGA is loaded
    p["net_liq_yoy"] = (p["net_liquidity"] / p["net_liquidity"].shift(12) - 1) * 100
    p["m2_minus_gdp"] = p["m2_yoy"] - p["gdp_nom_yoy"]
    p["fed_interest_receipts"] = p["fed_interest"] / p["fed_receipts"] * 100
    return p
