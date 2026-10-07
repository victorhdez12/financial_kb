"""NBER US business-cycle reference dates -> events/us_recessions.parquet.

Source: https://www.nber.org/research/data/us-business-cycle-expansions-and-contractions
JSON: https://data.nber.org/data/cycles/business_cycle_dates.json (monthly peaks/troughs, 1854-)

Each recession = peak month -> trough month (NBER convention: the recession starts the month
after the peak; we store the peak month as start_date as published). severity = contraction
length in months. NB: announced with 6-21 months delay -> not usable in real time.

Run: .venv/bin/python -m src.ingest.events_nber
"""
from __future__ import annotations

import json

import pandas as pd

from src.ingest._events_common import download, log, raw_dir, write_events

URLS = ["https://data.nber.org/data/cycles/business_cycle_dates.json"]
PAGE = "https://www.nber.org/research/data/us-business-cycle-expansions-and-contractions"


def main() -> None:
    f = download(URLS, raw_dir("nber") / "business_cycle_dates.json", "json", max_age_hours=24 * 7)
    data = json.loads(f.read_text())
    rows, prev_trough = [], None
    for r in data:
        peak, trough = r.get("peak") or None, r.get("trough") or None
        if peak:
            p = pd.Timestamp(peak)
            t = pd.Timestamp(trough) if trough else None
            months = (t.year - p.year) * 12 + (t.month - p.month) if t is not None else None
            exp = ((p.year - prev_trough.year) * 12 + (p.month - prev_trough.month)
                   if prev_trough is not None else None)
            rows.append({
                "event_id": f"nber_rec_{p:%Y%m}",
                "name": f"US recession {p:%Y-%m} to {t:%Y-%m}" if t is not None else f"US recession from {p:%Y-%m}",
                "type": "recession",
                "country": "USA",
                "start_date": p.date(),
                "end_date": t.date() if t is not None else None,
                "severity": str(months) if months is not None else None,
                "source": "nber",
                "url": PAGE,
                "notes": (f"NBER peak {p:%Y-%m}, trough {t:%Y-%m}" if t is not None else f"NBER peak {p:%Y-%m}, no trough yet")
                         + f"; severity = contraction months (peak to trough)"
                         + (f"; preceding expansion {exp} months" if exp is not None else ""),
            })
        if trough:
            prev_trough = pd.Timestamp(trough)
    df = write_events(rows, "us_recessions")
    log.info("NBER: %d recessions %s..%s; last trough %s", len(df), df.start_date.min(),
             df.start_date.max(), df.end_date.max())


if __name__ == "__main__":
    main()
