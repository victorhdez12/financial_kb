"""Shared loaders, constants and the Finding record used by every audit check."""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from src.warehouse.db import DATA_ROOT, WAREHOUSE

CURATED = DATA_ROOT / "curated"
LEGACY_FRED = DATA_ROOT / "macro" / "fred"
LEGACY_BLS = DATA_ROOT / "macro" / "bls"

CONTRACT_COLS = {"date": "date32", "value": "double", "series_id": "string", "source": "string"}
OPTIONAL_COLS = {"realtime_start": "date32"}
CATALOG_COLS = ["series_id", "source", "name", "category", "frequency", "units", "country",
                "start", "end", "transform_notes", "url", "license"]
REQUIRED_CATALOG = ["name", "category", "frequency", "units", "url", "license"]
CATEGORIES = {"growth", "inflation", "employment", "rates", "credit", "money", "liquidity", "fiscal",
              "markets", "equity_returns", "bond_returns", "commodities", "gold", "fx", "housing",
              "valuation", "financial_conditions", "geopolitics", "crisis"}
FREQS = {"D", "W", "M", "Q", "A"}

# sources whose upstream is a closed historical release: an old last date is expected
FROZEN_SOURCES = {"jst_macrohistory": "JST R6 termina en 2020",
                  "nber_macrohistory": "NBER Macrohistory congelada (1960s)",
                  "boe_millennium_uk": "BoE Millennium v3.1 termina en 2016",
                  "maddison": "Maddison 2023 termina en 2022"}
# max age (days) of the last observation's PERIOD END for a live source, by frequency
STALE_DAYS = {"D": 21, "W": 35, "M": 150, "Q": 300, "A": 800}

SEVERITY_ORDER = {"CRITICA": 0, "ALTA": 1, "MEDIA": 2, "BAJA": 3, "INFO": 4}


@dataclass
class Finding:
    check: str
    severity: str
    source: str
    series_id: str
    detail: str
    evidence: dict = field(default_factory=dict)
    fix: str = ""

    def row(self) -> dict:
        d = asdict(self)
        d["evidence"] = "; ".join(f"{k}={v}" for k, v in self.evidence.items())
        return d


def today(override: str | None = None) -> pd.Timestamp:
    return pd.Timestamp(override or dt.date.today())


def sources() -> list[str]:
    return sorted(p.name for p in CURATED.iterdir() if p.is_dir() and not p.name.startswith((".", "_")))


def load_catalog(source: str) -> pd.DataFrame:
    p = CURATED / source / "_catalog.csv"
    if not p.exists():
        return pd.DataFrame(columns=CATALOG_COLS)
    return pd.read_csv(p, dtype=str, keep_default_na=False, na_values=[""])


def all_catalogs() -> pd.DataFrame:
    frames = []
    for s in sources():
        c = load_catalog(s)
        c["_dir"] = s
        frames.append(c)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def parquet_files(source: str) -> list[Path]:
    return sorted(p for p in (CURATED / source).glob("*.parquet") if not p.name.startswith("_"))


def schema_of(path: Path) -> dict[str, str]:
    s = pq.read_schema(path)
    return {n: str(t) for n, t in zip(s.names, s.types)}


def read_series(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "realtime_start" in df:
        df["realtime_start"] = pd.to_datetime(df["realtime_start"], errors="coerce")
    return df


def infer_freq(idx: pd.DatetimeIndex) -> str:
    if len(idx) < 3:
        return "?"
    d = np.median(np.diff(np.sort(idx.values)).astype("timedelta64[D]").astype(int))
    for f, lim in (("D", 4), ("W", 10), ("M", 45), ("Q", 120)):
        if d <= lim:
            return f
    return "A"


PERIOD = {"M": "MS", "Q": "QS", "A": "YS"}


def period_end(d: pd.Timestamp, freq: str) -> pd.Timestamp:
    return {"M": d + pd.offsets.MonthEnd(0), "Q": d + pd.offsets.QuarterEnd(0),
            "A": d + pd.offsets.YearEnd(0)}.get(freq, d)


def expected_index(first: pd.Timestamp, last: pd.Timestamp, freq: str) -> pd.DatetimeIndex:
    return pd.date_range(first, last, freq=PERIOD[freq])


def fmt(d) -> str:
    return "" if d is None or pd.isna(d) else pd.Timestamp(d).strftime("%Y-%m-%d")


def warehouse_path() -> Path:
    return WAREHOUSE


def mtime(p: Path) -> pd.Timestamp:
    return pd.Timestamp(os.path.getmtime(p), unit="s")
