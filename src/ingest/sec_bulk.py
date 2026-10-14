"""Download SEC bulk archives (companyfacts.zip, submissions.zip) to raw/sec_bulk/.

Run: .venv/bin/python -m src.ingest.sec_bulk [--force]
Idempotent: skips a file whose local size matches the remote Content-Length and whose
local mtime is newer than the remote Last-Modified (unless --force).
"""
from __future__ import annotations

import argparse
import email.utils

from src.ingest.sec_common import (MANIFEST_DIR, append_manifest, get_logger, now_utc,
                                   raw_dir, sec_download, session)

FILES = {
    "companyfacts.zip": "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip",
    "submissions.zip": "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip",
}
log = get_logger("sec_bulk")


def main(force: bool = False) -> None:
    out = raw_dir("sec_bulk")
    for name, url in FILES.items():
        dest = out / name
        h = session().head(url, timeout=60)
        size = int(h.headers.get("content-length", 0))
        lm = h.headers.get("last-modified")
        remote_ts = email.utils.parsedate_to_datetime(lm).timestamp() if lm else 0
        if (not force and dest.exists() and dest.stat().st_size == size
                and dest.stat().st_mtime >= remote_ts):
            log.info("up to date: %s (%.2f GB)", name, size / 1e9)
            continue
        log.info("downloading %s (%.2f GB)", name, size / 1e9)
        sec_download(url, dest, log=log)
        append_manifest(MANIFEST_DIR / "sec_bulk_manifest.csv",
                        {"file": name, "url": url, "bytes": dest.stat().st_size,
                         "remote_last_modified": lm, "downloaded_at_utc": now_utc()},
                        ["file", "url", "bytes", "remote_last_modified", "downloaded_at_utc"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    main(ap.parse_args().force)
