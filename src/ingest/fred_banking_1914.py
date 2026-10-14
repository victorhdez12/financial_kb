"""FRED release 388 'Banking and Monetary Statistics 1914-1941' -> curated/fred_banking_1914.

    .venv/bin/python -m src.ingest.fred_banking_1914 [--refresh]

All series of the release (discovered with fred/release/series?release_id=388), ~2000
(mostly annual state-level bank counts/deposits, plus monthly/semiannual aggregates).
Raw API responses in raw/fred_banking_1914/<id>.{series,observations}.json.
Rate limit <= ~1.8 req/s (Fred client). Key never logged. Series already present in
curated/fred or curated/fred_us are skipped (series_id stays unique).
"""
from __future__ import annotations

import argparse
import json
import logging

import pandas as pd

from src.ingest.fred_extended import (CATALOG_COLS, Fred, FredError, catalog_row, data_root,
                                      fetch_series, obs_to_frame, write_parquet)
from src.ingest.fred_us import discover_release, drop_sentinels

SOURCE = "fred_banking_1914"
RID = 388
log = logging.getLogger(SOURCE)

# (keyword in lowercase title, category), first match wins
CATS = [("interest rate", "rates"), ("rates", "rates"), ("discount", "rates"), ("yield", "rates"),
        ("currency", "money"), ("money", "money"), ("circulation", "money"), ("gold", "money"),
        ("reserve", "liquidity"), ("federal reserve bank", "liquidity"),
        ("deposit", "money"), ("loans", "credit"), ("investments", "credit"),
        ("acceptance", "credit"), ("credit", "credit"), ("borrow", "credit"), ("debt", "credit"),
        ("securities", "credit"), ("assets", "credit"), ("liabilities", "credit"),
        ("capital", "credit"), ("failure", "crisis"), ("suspension", "crisis")]


def category(title: str) -> str:
    t = title.lower()
    for k, c in CATS:
        if k in t:
            return c
    return "credit"


def run(refresh: bool = False) -> pd.DataFrame:
    root = data_root()
    raw = root / "raw" / SOURCE
    out = root / "curated" / SOURCE
    raw.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    existing = set()
    for s in ("fred", "fred_us"):
        p = root / "curated" / s / "_catalog.csv"
        if p.exists():
            existing |= set(pd.read_csv(p, usecols=["series_id"])["series_id"])
    fred = Fred(min_interval=0.5)
    metas = discover_release(fred, RID)
    log.info("release %d: %d series", RID, len(metas))
    rows, failures, skipped = [], [], []
    for i, m in enumerate(metas):
        sid = m["id"]
        if sid in existing:
            skipped.append(sid)
            continue
        try:
            mm, obs = fetch_series(fred, sid, raw, refresh, m)
        except FredError as e:
            log.warning("%s: %s", sid, e)
            failures.append(sid)
            continue
        if not obs:
            failures.append(sid)
            continue
        df = obs_to_frame(obs, sid)
        df["value"] = drop_sentinels(df["value"])
        df["source"] = SOURCE
        if df["value"].notna().sum() == 0:
            failures.append(sid)
            continue
        write_parquet(out / f"{sid}.parquet", df)
        r = catalog_row(sid, mm, df, category(mm.get("title", "")), "US", sid, "",
                        f"origin: FRED API release {RID} (Banking and Monetary Statistics 1914-1941, "
                        "Board of Governors)")
        r["source"] = SOURCE
        rows.append(r)
        if i % 100 == 0:
            log.info("%d / %d", i, len(metas))
    cat = pd.DataFrame(rows, columns=CATALOG_COLS).sort_values("series_id")
    keep = set(cat["series_id"])
    for f in out.glob("*.parquet"):
        if f.stem not in keep:
            f.unlink()
    cat.to_csv(out / "_catalog.csv", index=False)
    (raw / "_run_summary.json").write_text(json.dumps({
        "run_utc": pd.Timestamp.now("UTC").isoformat(), "n_series": len(cat),
        "failures": failures, "skipped_already_curated": skipped, "requests": fred.n_requests}, indent=2))
    log.info("%s: %d series, %d failures, %d skipped", SOURCE, len(cat), len(failures), len(skipped))
    return cat


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    run(refresh=ap.parse_args().refresh)


if __name__ == "__main__":
    main()
