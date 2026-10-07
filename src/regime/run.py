"""Build `regime_monthly` in data/warehouse.duckdb (1950 -> current month).

Run: .venv/bin/python -m src.regime.run
USREC is never used here (it is published 6-18 months late); it only appears in validate.py.
"""
from __future__ import annotations

import json
from datetime import date

import pandas as pd

from src.regime import classify as C
from src.regime.asof import month_grid
from src.regime.credit import credit_monitor
from src.regime.features import build_panel
from src.warehouse import db

START = "1950-01-31"


# inputs that define G and I (headline CPI is only a pre-1957 proxy; PPI has no ALFRED file)
CORE_VINTAGE = ["indpro_yoy", "payems_yoy", "gdp_qoq_ann", "unrate_d12", "sahm", "core_cpi_6m", "core_pce_6m"]


def vintage_mode(panel: pd.DataFrame) -> pd.Series:
    """'alfred' if every core G/I input came from an ALFRED vintage, 'mixed' if some, else 'latest'."""
    vcols = [f"_v_{c}" for c in CORE_VINTAGE]
    used = panel[vcols].sum(axis=1)
    return pd.Series(pd.NA, index=panel.index, dtype=object).mask(used == 0, "latest") \
        .mask((used > 0) & (used < len(vcols)), "mixed").mask(used == len(vcols), "alfred")


def classify_all(panel: pd.DataFrame) -> pd.DataFrame:
    g = C.growth(panel)
    i = C.inflation(panel)
    d = C.debt_cycle_inputs(panel, i["I_state"])
    phase, why = C.debt_cycle_phase(d)
    lc = C.long_cycle(panel, g["sahm_trigger"])
    lq = C.liquidity(panel)
    cr = credit_monitor(panel)
    out = pd.concat([g, i.drop(columns=["core_6m"]), lc, lq, cr], axis=1)
    out["quadrant"] = C.quadrant(g["G_state"], i["I_state"])
    out["debt_phase"] = phase
    out["debt_phase_reason"] = why
    out["inverted_months"] = d["inverted_months"]
    out["curve_d6"] = d["curve_d6"]
    out["ff_d12"] = d["ff_d12"]
    out["z_curve"] = C.zscore(panel["curve"])
    out["z_real_ff"] = C.zscore(panel["real_ff"])
    out["z_baa_spread"] = C.zscore(panel["baa_spread"])
    out["z_nfci"] = C.zscore(panel["nfci"])
    return out


def build(today: date | None = None) -> pd.DataFrame:
    con = db.connect(read_only=True)
    grid = month_grid(today=today)
    panel, meta = build_panel(con, grid)
    con.close()
    res = classify_all(panel)
    raw = panel.drop(columns=[c for c in panel.columns if c.startswith("_v_")])
    df = pd.concat([raw, res], axis=1)
    df["vintage_mode"] = vintage_mode(panel)
    df["cutoff"] = grid.set_index("date")["cutoff"].reindex(df.index).values
    df = df[df.index >= START].reset_index().rename(columns={"index": "date"})
    save(df, meta)
    return df


def save(df: pd.DataFrame, meta: dict) -> None:
    con = db.connect(read_only=False)
    con.register("rm", df)
    con.execute("create or replace table regime_monthly as select * from rm")
    con.execute("create or replace table regime_meta as select ? as meta_json, current_timestamp as built_at",
                [json.dumps(meta)])
    con.close()


def main() -> None:
    df = build()
    last = df.iloc[-1]
    print(f"regime_monthly: {len(df)} rows {df['date'].min().date()} -> {df['date'].max().date()} "
          f"(cutoff {pd.Timestamp(last['cutoff']).date()})")
    print(f"  now: {last['quadrant']} | G={last['G']:.2f} ({last['G_state']}) I={last['I_state']} "
          f"core6m={last['core_6m']:.2f} | deuda: {last['debt_phase']} | crédito: {last['credit_light']} "
          f"| liquidez: {last['liquidity']} | vintage_mode={last['vintage_mode']}")


if __name__ == "__main__":
    main()
