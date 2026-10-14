"""Shared helpers for the investor-texts library (src/ingest/texts_*.py).

Layout (see docs/data/texts.md):
    $FIN_DATA_ROOT/texts/<collection>/<id>.<pdf|txt|html>   original
    $FIN_DATA_ROOT/texts/<collection>/<id>.txt              extracted text (for pdf/html)
    $FIN_DATA_ROOT/texts/manifest.parquet                   one row per document
    $FIN_DATA_ROOT/texts/catalog_copyrighted.csv            bibliographic cards only

LEGAL RULE: only texts offered free of charge by the rights holder, or public
domain (documented in `license_basis`). Never pirate mirrors.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except Exception:  # pragma: no cover
    pass

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

MANIFEST_COLS = [
    "id", "collection", "author", "title", "date", "url", "license_basis",
    "sha256", "n_chars", "format", "retrieved_at", "path", "text_path",
]

log = logging.getLogger("ingest.texts")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def data_root() -> Path:
    return Path(os.path.expanduser(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")))


def texts_root() -> Path:
    p = data_root() / "texts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def manifest_path() -> Path:
    return texts_root() / "manifest.parquet"


# --------------------------------------------------------------------------- HTTP
_last_hit: dict[str, float] = {}
# sec.gov shared with another agent: keep this process well under 3 req/s.
_MIN_INTERVAL = {"sec.gov": 0.4}
_DEFAULT_INTERVAL = 0.5


def _throttle(url: str) -> None:
    host = urlparse(url).hostname or ""
    key = "sec.gov" if host.endswith("sec.gov") else host
    gap = _MIN_INTERVAL.get(key, _DEFAULT_INTERVAL)
    wait = _last_hit.get(key, 0) + gap - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_hit[key] = time.time()


def _headers(url: str) -> dict:
    host = urlparse(url).hostname or ""
    if host.endswith("sec.gov"):
        ua = os.environ.get("SEC_USER_AGENT") or "financial_kb research"
        return {"User-Agent": ua, "Accept-Encoding": "gzip, deflate"}
    return {"User-Agent": BROWSER_UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}


def http_get(url: str, *, retries: int = 3, timeout: int = 60) -> requests.Response:
    last = None
    for i in range(retries):
        _throttle(url)
        try:
            r = requests.get(url, headers=_headers(url), timeout=timeout, allow_redirects=True)
            if r.status_code == 200:
                return r
            last = RuntimeError(f"HTTP {r.status_code} for {url}")
            if r.status_code in (403, 404, 410):
                break
        except requests.RequestException as e:  # pragma: no cover
            last = e
        time.sleep(2 * (i + 1))
    raise last  # type: ignore[misc]


# --------------------------------------------------------------------------- validation
def sniff_format(content: bytes) -> str:
    head = content[:2048].lstrip()
    if content[:5] == b"%PDF-":
        return "pdf"
    low = head.lower()
    if low.startswith(b"<!doctype html") or low.startswith(b"<html") or b"<html" in low[:1024] \
            or b"<body" in low or b"<div" in low[:1024] or low.startswith(b"<?xml") and b"html" in low:
        return "html"
    return "txt"


ERROR_PATTERNS = re.compile(
    rb"(page not found|404 not found|access denied|request rejected|captcha|"
    rb"just a moment\.\.\.|attention required|enable javascript and cookies)",
    re.I,
)


def validate(content: bytes, expect: str, min_bytes: int = 2000) -> str:
    """Return the detected format or raise if this is not a real document."""
    if len(content) < min_bytes:
        raise ValueError(f"too small ({len(content)} bytes)")
    fmt = sniff_format(content)
    if expect == "pdf" and fmt != "pdf":
        raise ValueError(f"expected PDF, got {fmt} (first bytes {content[:40]!r})")
    if fmt == "pdf" and b"%%EOF" not in content[-2048:]:
        log.warning("PDF without trailing %%EOF (may be truncated)")
    if fmt != "pdf" and ERROR_PATTERNS.search(content[:20000]) and len(content) < 60000:
        raise ValueError("looks like an error / bot-check page")
    return fmt


# --------------------------------------------------------------------------- extraction
def extract_pdf(path: Path) -> str:
    import pymupdf

    with pymupdf.open(path) as doc:
        return "\n".join(page.get_text("text") for page in doc)


def extract_html(content: bytes, selector: str | None = None) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content, "lxml")
    for t in soup(["script", "style", "noscript", "nav", "header", "footer", "form", "svg"]):
        t.decompose()
    node = None
    if selector:
        node = soup.select_one(selector)
    node = node or soup.find("article") or soup.find("main") or soup.body or soup
    text = node.get_text("\n")
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip() + "\n"


def strip_gutenberg(text: str) -> str:
    """Keep only the body between Gutenberg START/END markers (license kept in manifest)."""
    m1 = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG[^\n]*\n", text)
    m2 = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG", text)
    if m1 and m2 and m2.start() > m1.end():
        return text[m1.end():m2.start()]
    return text


# --------------------------------------------------------------------------- documents
@dataclass
class Doc:
    id: str
    collection: str
    author: str
    title: str
    date: str               # ISO yyyy-mm-dd (or yyyy-01-01 if only year known)
    url: str
    license_basis: str
    expect: str = "any"     # pdf | html | txt | any
    selector: str | None = None   # CSS selector for HTML main content
    gutenberg: bool = False
    min_chars: int = 3000
    extra: dict = field(default_factory=dict)


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fetch_doc(d: Doc, *, force: bool = False) -> dict | None:
    """Download (idempotent), validate, extract. Returns a manifest row or None on failure."""
    cdir = texts_root() / d.collection
    cdir.mkdir(parents=True, exist_ok=True)
    existing = [p for p in cdir.glob(f"{d.id}.*") if p.suffix in (".pdf", ".html", ".txt")]
    orig = next((p for p in existing if p.suffix in (".pdf", ".html")), None) or \
        next((p for p in existing if p.suffix == ".txt"), None)
    if orig is not None and not force:
        content = orig.read_bytes()
        fmt = orig.suffix.lstrip(".")
        retrieved = dt.datetime.fromtimestamp(orig.stat().st_mtime).isoformat(timespec="seconds")
    else:
        try:
            r = http_get(d.url)
            content = r.content
            fmt = validate(content, d.expect)
        except Exception as e:
            log.error("FAIL %s/%s: %s", d.collection, d.id, e)
            return None
        orig = cdir / f"{d.id}.{fmt}"
        orig.write_bytes(content)
        retrieved = dt.datetime.now().isoformat(timespec="seconds")

    txt_path = cdir / f"{d.id}.txt"
    if fmt == "txt":
        text = content.decode("utf-8", errors="replace")
        if d.gutenberg:
            # keep the original intact; body-only copy goes alongside
            txt_path = cdir / f"{d.id}.body.txt"
            text = strip_gutenberg(text)
    elif txt_path.exists() and not force:
        text = txt_path.read_text(encoding="utf-8")
    else:
        try:
            text = extract_pdf(orig) if fmt == "pdf" else extract_html(content, d.selector)
        except Exception as e:
            log.error("FAIL extract %s: %s", d.id, e)
            return None
    text = clean_text(text)
    if len(text) < d.min_chars:
        log.error("FAIL %s/%s: extracted only %d chars (scanned PDF or stub page?)",
                  d.collection, d.id, len(text))
        # keep the original but flag in the manifest via n_chars
    if fmt != "txt" or d.gutenberg:
        txt_path.write_text(text, encoding="utf-8")
    else:
        txt_path = orig
    log.info("ok %s/%s  %s  %d chars", d.collection, d.id, fmt, len(text))
    return {
        "id": d.id, "collection": d.collection, "author": d.author, "title": d.title,
        "date": d.date, "url": d.url, "license_basis": d.license_basis,
        "sha256": sha256(content), "n_chars": len(text), "format": fmt,
        "retrieved_at": retrieved, "path": str(orig), "text_path": str(txt_path),
    }


def run_docs(docs: list[Doc], *, force: bool = False) -> pd.DataFrame:
    rows, fails = [], []
    for d in docs:
        row = fetch_doc(d, force=force)
        (rows.append(row) if row else fails.append(d.id))
    if rows:
        upsert_manifest(rows)
    log.info("collection run: %d ok, %d failed %s", len(rows), len(fails), fails)
    return pd.DataFrame(rows)


def upsert_manifest(rows: list[dict]) -> None:
    new = pd.DataFrame(rows, columns=MANIFEST_COLS)
    mp = manifest_path()
    if mp.exists():
        old = pd.read_parquet(mp)
        old = old[~old["id"].isin(new["id"])]
        new = pd.concat([old, new], ignore_index=True)
    dup = new["id"].duplicated()
    if dup.any():
        raise ValueError(f"duplicate ids: {new.loc[dup, 'id'].tolist()}")
    new["n_chars"] = new["n_chars"].astype("int64")
    for c in MANIFEST_COLS:
        if c != "n_chars":
            new[c] = new[c].astype("string")
    new = new.sort_values(["collection", "date", "id"]).reset_index(drop=True)
    tmp = mp.with_suffix(".tmp.parquet")
    new.to_parquet(tmp, index=False)
    tmp.replace(mp)
