"""Regime rules from docs/PLAN.md ("Marco de regímenes").

All statistics are causal: z-scores use a trailing 10-year (120 month) window ending at t,
percentiles use an expanding window ending at t, and state machines (hysteresis) only look
at t and earlier rows. Inputs come from the point-in-time panel (features.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

Z_WINDOW, Z_MIN = 120, 36   # 10y trailing window; 3y minimum so the series starts ~1950


def zscore(x: pd.Series, window: int = Z_WINDOW, min_periods: int = Z_MIN) -> pd.Series:
    r = x.rolling(window, min_periods=min_periods)
    return (x - r.mean()) / r.std()


def row_mean(df: pd.DataFrame, min_count: int = 1) -> pd.Series:
    """Row mean that is NaN unless at least `min_count` inputs are present."""
    return df.mean(axis=1).where(df.notna().sum(axis=1) >= min_count)


def pct_rank(x: pd.Series, min_periods: int = 24) -> pd.Series:
    """Percentile of the current value among all values up to and including t (no future)."""
    return x.expanding(min_periods=min_periods).rank(pct=True) * 100


# ---------------------------------------------------------------- growth
G_INPUTS = {"indpro_yoy": 1, "payems_yoy": 1, "gdp_qoq_ann": 1, "unrate_d12": -1}


def growth(p: pd.DataFrame) -> pd.DataFrame:
    """G = mean z of INDPRO yoy, PAYEMS yoy, GDPC1 q/q ann., -ΔUNRATE(12m).

    UNRATE enters as its 12-month change (inverted): the level is trending/lagging, the change
    is the growth signal. Sahm >= 0.5pp forces G-down. G-up iff G > 0 and ΔG(6m) > 0."""
    out = pd.DataFrame(index=p.index)
    for col, sign in G_INPUTS.items():
        out[f"z_{col}"] = sign * zscore(p[col])
    zc = [f"z_{c}" for c in G_INPUTS]
    out["G"] = row_mean(out[zc], 2)
    out["G_d6"] = out["G"] - out["G"].shift(6)
    out["sahm_trigger"] = p["sahm"] >= 0.5
    up = (out["G"] > 0) & (out["G_d6"] > 0) & ~out["sahm_trigger"]
    out["G_state"] = np.where(out["G"].isna(), None, np.where(up, "up", "down"))
    return out


# ---------------------------------------------------------------- inflation
def inflation_state(core6m: pd.Series, accel: pd.Series) -> pd.Series:
    """I-up if core 6m > 2.5% and accelerating; I-down if < 2% or decelerating > 0.5pp;
    otherwise keep the previous state (hysteresis, avoids flip-flopping in the 2-2.5% band)."""
    states, prev = [], None
    for c, a in zip(core6m, accel):
        if np.isnan(c):
            states.append(None)
            continue
        a = 0.0 if np.isnan(a) else a
        if c > 2.5 and a > 0:
            prev = "up"
        elif c < 2.0 or a < -0.5:
            prev = "down"
        elif prev is None:
            prev = "up" if c > 2.25 else "down"
        states.append(prev)
    return pd.Series(states, index=core6m.index, dtype=object)


def inflation(p: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=p.index)
    out["core_6m"] = p["core_6m"]
    out["core_accel_3m"] = p["core_6m"] - p["core_6m"].shift(3)
    out["z_core_gap"] = zscore(p["core_6m"] - 2.0)
    out["z_ppi_yoy"] = zscore(p["ppi_yoy"])
    out["z_t5yie"] = zscore(p["t5yie"])
    out["I"] = row_mean(out[["z_core_gap", "z_ppi_yoy", "z_t5yie"]])  # informative composite
    out["I_state"] = inflation_state(p["core_6m"], out["core_accel_3m"])
    return out


QUADRANTS = {("up", "up"): "Reflación", ("up", "down"): "Goldilocks",
             ("down", "up"): "Estanflación", ("down", "down"): "Deflación/recesión"}


def quadrant(g: pd.Series, i: pd.Series) -> pd.Series:
    return pd.Series([QUADRANTS.get((a, b)) for a, b in zip(g, i)], index=g.index, dtype=object)


# ---------------------------------------------------------------- short-term debt cycle
PHASES = ["expansión temprana", "expansión tardía", "endurecimiento", "techo",
          "desapalancamiento", "reflación"]


def debt_cycle_inputs(p: pd.DataFrame, i_state: pd.Series) -> pd.DataFrame:
    d = pd.DataFrame(index=p.index)
    d["curve"] = p["curve"]
    d["curve_d6"] = p["curve"] - p["curve"].shift(6)
    d["baa_d3"] = p["baa_spread"] - p["baa_spread"].shift(3)
    d["baa_d6"] = p["baa_spread"] - p["baa_spread"].shift(6)
    d["ff_d12"] = p["fedfunds"] - p["fedfunds"].shift(12)
    inverted = (p["curve"] < 0).astype(int)
    d["inverted_months"] = inverted.groupby((inverted == 0).cumsum()).cumsum()
    d["rules"] = pd.DataFrame({
        "desapalancamiento": (p["baa_spread"] > 3) | (p["nfci"] > 0),
        "reflación": (d["ff_d12"] <= -1.5) | (p["walcl_yoy"] > 10),
        "techo": d["inverted_months"] >= 3,
        "endurecimiento": (d["ff_d12"] >= 1.0) | ((p["real_ff"] > 1) & (d["ff_d12"] > 0.25)),
        "expansión tardía": (p["tcu"] > 80) & (i_state == "up"),
        "expansión temprana": (p["curve"] > 1) & (d["curve_d6"] > 0) & ~(d["baa_d6"] > 0),
    }).fillna(False).to_dict("records")
    return d


def debt_cycle_phase(d: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Priority: deleveraging (unless policy is already reflating AND spreads tighten) >
    reflation > top > tightening > late > early. No rule firing: hold the previous phase up to
    6 months, then fall back to early/late expansion by curve slope (documented heuristic)."""
    phases, why, prev, held = [], [], None, 0
    for rules, baa_d3, curve in zip(d["rules"], d["baa_d3"], d["curve"]):
        fired = None
        if rules["desapalancamiento"] and not (rules["reflación"] and baa_d3 < 0):
            fired = "desapalancamiento"
        else:
            for ph in ["reflación", "techo", "endurecimiento", "expansión tardía", "expansión temprana"]:
                if rules[ph]:
                    fired = ph
                    break
        if fired:
            prev, held, reason = fired, 0, "regla"
        elif prev is not None and held < 6:
            held += 1
            reason = "mantiene"
        else:
            prev = "expansión temprana" if (not np.isnan(curve) and curve > 1) else "expansión tardía"
            held, reason = 0, "fallback curva"
        phases.append(prev)
        why.append(reason)
    return pd.Series(phases, index=d.index, dtype=object), pd.Series(why, index=d.index, dtype=object)


# ---------------------------------------------------------------- long-term debt cycle
def long_cycle(p: pd.DataFrame, sahm_trigger: pd.Series) -> pd.DataFrame:
    out = pd.DataFrame(index=p.index)
    flags = pd.DataFrame(index=p.index)
    flags["deuda_pub>100%_y_sube"] = (p["debt_gdp"] > 100) & (p["debt_gdp"] - p["debt_gdp"].shift(12) > 0)
    flags["deficit<-5%_sin_recesion"] = (p["deficit_gdp"] < -5) & ~sahm_trigger
    flags["intereses/ingresos>p90"] = pct_rank(p["fed_interest_receipts"]) >= 90
    flags["credito_privado/PIB>150%"] = p["private_credit_gdp"] > 150
    avail = pd.DataFrame({
        "deuda_pub>100%_y_sube": p["debt_gdp"].notna(), "deficit<-5%_sin_recesion": p["deficit_gdp"].notna(),
        "intereses/ingresos>p90": p["fed_interest_receipts"].notna(),
        "credito_privado/PIB>150%": p["private_credit_gdp"].notna()})
    out["long_flags"] = (flags & avail).sum(axis=1)
    out["long_flags_avail"] = avail.sum(axis=1)
    out["long_flags_list"] = [", ".join(c for c in flags.columns if r[c] and a[c]) for (_, r), (_, a)
                              in zip(flags.iterrows(), avail.iterrows())]
    ratio = out["long_flags"] / out["long_flags_avail"].replace(0, np.nan)
    out["long_cycle"] = np.select([ratio >= 0.75, ratio >= 0.5, ratio.notna()],
                                  ["tardío (riesgo de desapalancamiento)", "tardío", "temprano/medio"], None)
    return out


# ---------------------------------------------------------------- liquidity
def liquidity(p: pd.DataFrame) -> pd.DataFrame:
    """Score = mean z of (M2-GDP growth gap, net-liquidity yoy, -DFII10, -NFCI); >0.5 abundant."""
    out = pd.DataFrame(index=p.index)
    out["z_m2_minus_gdp"] = zscore(p["m2_minus_gdp"])
    out["z_net_liq_yoy"] = zscore(p["net_liq_yoy"], min_periods=24)
    out["z_real_rate_neg"] = -zscore(p["dfii10"], min_periods=24)
    out["z_nfci_neg"] = -zscore(p["nfci"])
    cols = ["z_m2_minus_gdp", "z_net_liq_yoy", "z_real_rate_neg", "z_nfci_neg"]
    out["liquidity_score"] = row_mean(out[cols])
    out["liquidity"] = np.select([out["liquidity_score"] > 0.5, out["liquidity_score"] < -0.5,
                                  out["liquidity_score"].notna()], ["abundante", "escasa", "neutral"], None)
    return out
