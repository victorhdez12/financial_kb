"""Shared helpers for long-history external sources (Shiller, JST, gold, Pink Sheet,
Ken French, Damodaran, BoE millennium). Follows docs/DATA_CONTRACT.md."""
from __future__ import annotations

import io
import logging
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except Exception:  # pragma: no cover
    pass

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
CATALOG_COLS = [
    "series_id", "source", "name", "category", "frequency", "units", "country",
    "start", "end", "transform_notes", "url", "license",
]

log = logging.getLogger("ingest")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def data_root() -> Path:
    root = os.environ.get("FIN_DATA_ROOT", "~/financial_archive")
    return Path(os.path.expanduser(root))


def raw_dir(source: str) -> Path:
    p = data_root() / "raw" / source
    p.mkdir(parents=True, exist_ok=True)
    return p


def curated_dir(source: str) -> Path:
    p = data_root() / "curated" / source
    p.mkdir(parents=True, exist_ok=True)
    return p


def events_dir() -> Path:
    p = data_root() / "events"
    p.mkdir(parents=True, exist_ok=True)
    return p


_MAGIC = {
    "xls": [b"\xd0\xcf\x11\xe0"],
    "xlsx": [b"PK\x03\x04"],
    "zip": [b"PK\x03\x04"],
    "dta": [b"<stata_dta>", b"\x72", b"\x73", b"\x71"],
}


def http_get(url: str, *, timeout: int = 120, retries: int = 3) -> requests.Response:
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            return r
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"GET failed {url}: {last}")


def validate_bytes(content: bytes, kind: str) -> None:
    head = content[:512].lstrip().lower()
    if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
        raise ValueError("download is an HTML page, not data")
    if kind in _MAGIC and not any(content.startswith(m) for m in _MAGIC[kind]):
        raise ValueError(f"unexpected magic bytes for {kind}: {content[:8]!r}")
    if kind == "csv" and b"," not in content[:2000]:
        raise ValueError("csv without commas")
    if len(content) < 1000:
        raise ValueError(f"download too small ({len(content)} bytes)")


def download(url: str, dest: Path, kind: str, *, min_age_hours: float = 0) -> Path:
    """Download url to dest after validating. Idempotent: if dest exists and is newer than
    min_age_hours, reuse it. Keeps the original bytes intact."""
    if dest.exists() and min_age_hours > 0:
        age = (time.time() - dest.stat().st_mtime) / 3600
        if age < min_age_hours:
            log.info("reuse cached %s", dest.name)
            return dest
    r = http_get(url)
    validate_bytes(r.content, kind)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(r.content)
    tmp.replace(dest)
    log.info("downloaded %s (%d bytes) <- %s", dest.name, len(r.content), r.url)
    return dest


def find_link(page_url: str, pattern: str) -> str | None:
    """Return the first href on page_url matching regex pattern (absolute URL)."""
    try:
        html = http_get(page_url, timeout=60).text
    except Exception as e:  # noqa: BLE001
        log.warning("could not read %s: %s", page_url, e)
        return None
    for m in re.finditer(r'href="([^"]+)"', html):
        href = m.group(1).replace("&amp;", "&")
        if re.search(pattern, href, re.I):
            return requests.compat.urljoin(page_url, href)
    return None


class CatalogWriter:
    """Writes one parquet per series and accumulates _catalog.csv rows."""

    def __init__(self, source: str, *, url: str, license: str):
        self.source = source
        self.url = url
        self.license = license
        self.out = curated_dir(source)
        self.rows: list[dict] = []

    def add(self, series_id: str, s: pd.Series, *, name: str, category: str, frequency: str,
            units: str, country: str = "", transform_notes: str = "", url: str | None = None,
            license: str | None = None, dropna: bool = True) -> int:
        s = pd.to_numeric(s, errors="coerce").astype("float64")
        s.index = pd.to_datetime(s.index)
        s = s.sort_index()
        s = s[~s.index.duplicated(keep="last")]
        if dropna:
            s = s.dropna()
        if s.empty:
            log.warning("empty series %s skipped", series_id)
            return 0
        df = pd.DataFrame({
            "date": s.index.date,
            "value": s.values,
            "series_id": series_id,
            "source": self.source,
        })
        df["series_id"] = df["series_id"].astype("string")
        df["source"] = df["source"].astype("string")
        df.to_parquet(self.out / f"{series_id}.parquet", index=False)
        self.rows.append({
            "series_id": series_id, "source": self.source, "name": name, "category": category,
            "frequency": frequency, "units": units, "country": country,
            "start": str(s.index.min().date()), "end": str(s.index.max().date()),
            "transform_notes": transform_notes, "url": url or self.url,
            "license": license or self.license,
        })
        return len(df)

    def close(self) -> pd.DataFrame:
        cat = pd.DataFrame(self.rows, columns=CATALOG_COLS).sort_values("series_id")
        dup = cat["series_id"][cat["series_id"].duplicated()].unique().tolist()
        if dup:  # a repeated id means one parquet silently overwrote another (maddison regions, 2026-10)
            raise ValueError(f"{self.source}: duplicated series_id {dup[:10]}")
        # drop stale parquet files no longer produced
        keep = set(cat["series_id"])
        for f in self.out.glob("*.parquet"):
            if f.stem not in keep:
                f.unlink()
        cat.to_csv(self.out / "_catalog.csv", index=False)
        log.info("%s: wrote %d series to %s", self.source, len(cat), self.out)
        return cat
