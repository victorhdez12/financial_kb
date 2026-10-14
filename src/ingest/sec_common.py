"""Shared helpers for the SEC company-universe layer (sec_universe, sec_bulk,
sec_fundamentals, sec_10k_text, sec_10k_sections).

- SEC fair-access: one process-wide token bucket at <= 5 req/s (SEC global limit is 10 req/s;
  another agent/process may use the other half). User-Agent from .env SEC_USER_AGENT.
- Paths follow docs/DATA_CONTRACT.md: raw/sec_*/, curated/sec_*/, sec/universe/.
- Never logs the User-Agent or any key.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except Exception:  # pragma: no cover
    pass

MAX_RPS = float(os.environ.get("SEC_MAX_RPS", "5"))
MAX_RPS = min(MAX_RPS, 5.0)


def data_root() -> Path:
    return Path(os.path.expanduser(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")))


ROOT = data_root()
UNIVERSE_DIR = ROOT / "sec" / "universe"
LEGACY_10K = ROOT / "sec" / "10k"
LOG_DIR = ROOT / "logs"
MANIFEST_DIR = ROOT / "manifests"


def raw_dir(name: str) -> Path:
    p = ROOT / "raw" / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def curated_dir(name: str) -> Path:
    p = ROOT / "curated" / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_logger(name: str) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    lg = logging.getLogger(name)
    if not lg.handlers:
        lg.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        fh = logging.FileHandler(LOG_DIR / f"{name}.log")
        fh.setFormatter(fmt)
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        lg.addHandler(fh)
        lg.addHandler(sh)
        lg.propagate = False
    return lg


def user_agent() -> str:
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if not ua:
        raise SystemExit("SEC_USER_AGENT missing in .env (format: 'Name email@example.com')")
    return ua


class _RateLimiter:
    def __init__(self, rps: float):
        self.interval = 1.0 / rps
        self.lock = threading.Lock()
        self.next_t = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            if now < self.next_t:
                time.sleep(self.next_t - now)
                now = time.monotonic()
            self.next_t = now + self.interval


_LIMITER = _RateLimiter(MAX_RPS)
_SESSION: requests.Session | None = None


def session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        s = requests.Session()
        retry = Retry(total=5, backoff_factor=2.0, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET", "HEAD"), respect_retry_after_header=True)
        s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=8))
        s.headers.update({"User-Agent": user_agent(), "Accept-Encoding": "gzip, deflate"})
        _SESSION = s
    return _SESSION


def sec_get(url: str, *, stream: bool = False, timeout: int = 90) -> requests.Response:
    """Rate-limited GET against sec.gov / data.sec.gov (<= 5 req/s)."""
    _LIMITER.wait()
    r = session().get(url, stream=stream, timeout=timeout)
    if r.status_code == 403 and b"Request Rate Threshold" in (r.content[:2000] if not stream else b""):
        time.sleep(600)  # SEC throttling block: back off 10 minutes
        _LIMITER.wait()
        r = session().get(url, stream=stream, timeout=timeout)
    r.raise_for_status()
    return r


def sec_download(url: str, dest: Path, *, log: logging.Logger | None = None,
                 chunk: int = 1 << 20) -> Path:
    """Stream a (large) file to dest atomically. Single request -> rate limiter once."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with sec_get(url, stream=True, timeout=600) as r:
        total = 0
        with open(tmp, "wb") as fh:
            for block in r.iter_content(chunk):
                fh.write(block)
                total += len(block)
    tmp.replace(dest)
    if log:
        log.info("downloaded %s (%.1f MB)", dest.name, total / 1e6)
    return dest


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str))
    tmp.replace(path)


def append_manifest(path: Path, row: dict, fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def cik10(cik) -> str:
    return str(int(cik)).zfill(10)
