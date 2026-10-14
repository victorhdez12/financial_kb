"""Shared helpers for the European / Spanish sources (ecb, eurostat, bde, ine, bundesbank).

Builds on _extlong_common (CatalogWriter, raw/curated dirs). Adds:
- cached_get(): download once, keep the original bytes in raw/<source>/, reuse if fresh.
- to_period_start(): normalise SDMX/BdE/INE period labels to the first day of the period.
- add_series(): contract-level cleaning before CatalogWriter.add():
    * drops observations dated after today (no future dates; forecasts/placeholders),
    * positive=True turns zeros into NaN (stocks, indices, prices: a 0 there is a missing value),
    * NaN is kept as NaN (dropna) and dates are aligned to period start.
"""
from __future__ import annotations

import datetime as dt
import re
import time
from pathlib import Path

import pandas as pd
import requests

from src.ingest._extlong_common import UA, CatalogWriter, log, raw_dir  # noqa: F401

TODAY = pd.Timestamp(dt.date.today())

_SP_MONTHS = {"ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6, "JUL": 7, "AGO": 8,
              "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12}


def cached_get(url: str, dest: Path, *, max_age_hours: float = 20, timeout: int = 180,
               retries: int = 4, min_bytes: int = 50, headers: dict | None = None,
               allow_404: bool = False) -> bytes | None:
    """GET url, store the raw response at dest, reuse it if younger than max_age_hours."""
    if dest.exists() and (time.time() - dest.stat().st_mtime) / 3600 < max_age_hours and dest.stat().st_size >= min_bytes:
        return dest.read_bytes()
    last = None
    h = {"User-Agent": UA}
    h.update(headers or {})
    for i in range(retries):
        try:
            r = requests.get(url, headers=h, timeout=timeout)
            if r.status_code == 404 and allow_404:
                return None
            r.raise_for_status()
            content = r.content
            head = content[:300].lstrip().lower()
            if head.startswith(b"<html") or head.startswith(b"<!doctype html"):
                raise ValueError("HTML page instead of data (blocked?)")
            if len(content) < min_bytes:
                raise ValueError(f"response too small ({len(content)} bytes)")
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(dest.suffix + ".part")
            tmp.write_bytes(content)
            tmp.replace(dest)
            time.sleep(0.4)  # be polite with public APIs (the ECB WAF blocks bursts)
            return content
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3 * (i + 1))
    if dest.exists():
        log.warning("GET failed, using stale raw %s: %s", dest.name, last)
        return dest.read_bytes()
    raise RuntimeError(f"GET failed {url}: {last}")


def to_period_start(label: str) -> pd.Timestamp | None:
    """'2024-03-15', '2024-03', '2024-Q2', '2024-W05', '2024-S2', '2024', 'ENE 1962', 'MAR 1995'
    (BdE quarterly labels are the last month of the quarter -> handled by caller via freq)."""
    s = str(label).strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return pd.Timestamp(s)
        if re.fullmatch(r"\d{4}-\d{2}", s):
            return pd.Timestamp(s + "-01")
        m = re.fullmatch(r"(\d{4})-?Q([1-4])", s)
        if m:
            return pd.Timestamp(int(m.group(1)), 3 * int(m.group(2)) - 2, 1)
        m = re.fullmatch(r"(\d{4})-W(\d{2})", s)
        if m:
            return pd.Timestamp(dt.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1))
        m = re.fullmatch(r"(\d{4})-S([12])", s)
        if m:
            return pd.Timestamp(int(m.group(1)), 1 if m.group(2) == "1" else 7, 1)
        if re.fullmatch(r"\d{4}", s):
            return pd.Timestamp(int(s), 1, 1)
        m = re.fullmatch(r"([A-Z]{3}) (\d{4})", s.upper())
        if m and m.group(1) in _SP_MONTHS:
            return pd.Timestamp(int(m.group(2)), _SP_MONTHS[m.group(1)], 1)
    except Exception:  # noqa: BLE001
        return None
    return None


def add_series(cw: CatalogWriter, series_id: str, s: pd.Series, *, positive: bool = False,
               **kw) -> int:
    """Contract cleaning + write. Returns number of rows written."""
    s = pd.to_numeric(s, errors="coerce").astype("float64")
    s.index = pd.to_datetime(s.index)
    s = s[s.index <= TODAY]
    if positive:
        s = s.mask(s <= 0)
    return cw.add(series_id, s, **kw)


def spliced(parts: list[tuple[pd.Series, str | None, str | None]]) -> pd.Series:
    """Concatenate (series, start, end) slices; later parts never overwrite earlier dates."""
    out = []
    for s, a, b in parts:
        x = s.copy()
        if a:
            x = x[x.index >= pd.Timestamp(a)]
        if b:
            x = x[x.index <= pd.Timestamp(b)]
        out.append(x.dropna())
    res = pd.concat(out).sort_index()
    return res[~res.index.duplicated(keep="first")]
