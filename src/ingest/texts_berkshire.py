"""Register the existing Berkshire Hathaway letters (~/financial_archive/berkshire_letters)
in texts/manifest.parquet WITHOUT re-downloading them.

Findings about the legacy folder (left untouched):
  * 15 of the .html files (1980-1999, 2001-2002) were saved as raw *brotli* bytes
    (Content-Encoding not decoded) and several legacy .txt files are therefore binary
    garbage. We decode brotli in memory and re-extract the text here.
  * 1998/1999 .html are only index stubs pointing to the PDF; those two PDFs are
    gap-filled into texts/shareholder_letters/berkshire/ (official URLs).
Extracted text always goes to texts/shareholder_letters/berkshire/berkshire_<year>.txt.

    .venv/bin/python -m src.ingest.texts_berkshire
"""
from __future__ import annotations

import datetime as dt

from src.ingest.texts_common import (clean_text, data_root, extract_html, extract_pdf,
                                     http_get, log, sha256, texts_root, upsert_manifest,
                                     validate)

BASE = "https://www.berkshirehathaway.com/letters"
LICENSE = ("Published free of charge by the rights holder (Berkshire Hathaway Inc.) on "
           "berkshirehathaway.com; personal research use, no redistribution")
GAP_FILL = {1998: f"{BASE}/1998pdf.pdf", 1999: f"{BASE}/final1999pdf.pdf"}


def url_for(year: int) -> str:
    if year in GAP_FILL:
        return GAP_FILL[year]
    if year <= 1997:
        return f"{BASE}/{year}.html"
    if year <= 2002:
        return f"{BASE}/{year}pdf.pdf"
    return f"{BASE}/{year}ltr.pdf"


def maybe_brotli(b: bytes) -> bytes:
    if b.lstrip()[:1] == b"<":
        return b
    import brotli
    return brotli.decompress(b)


def main() -> None:
    src = data_root() / "berkshire_letters"
    out = texts_root() / "shareholder_letters" / "berkshire"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    years = sorted({int(p.name[:4]) for p in src.glob("*_Berkshire_Letter.*")})
    for year in years:
        pdf, html = src / f"{year}_Berkshire_Letter.pdf", src / f"{year}_Berkshire_Letter.html"
        txt = out / f"berkshire_{year}.txt"
        if year in GAP_FILL:
            orig = out / f"berkshire_{year}.pdf"
            if not orig.exists():
                content = http_get(GAP_FILL[year]).content
                validate(content, "pdf")
                orig.write_bytes(content)
            fmt = "pdf"
        elif pdf.exists() and pdf.read_bytes()[:5] == b"%PDF-":
            orig, fmt = pdf, "pdf"
        elif html.exists():
            orig, fmt = html, "html"
        else:
            log.error("no usable file for %d", year)
            continue
        content = orig.read_bytes()
        if not txt.exists():
            text = extract_pdf(orig) if fmt == "pdf" else extract_html(maybe_brotli(content))
            txt.write_text(clean_text(text), encoding="utf-8")
        text = txt.read_text(encoding="utf-8")
        if len(text) < 8000:
            log.warning("short text for %d: %d chars", year, len(text))
        rows.append({
            "id": f"berkshire_{year}", "collection": "shareholder_letters/berkshire",
            "author": "Warren E. Buffett",
            "title": f"Berkshire Hathaway Chairman's Letter to Shareholders {year}",
            "date": f"{year + 1}-02-28", "url": url_for(year), "license_basis": LICENSE,
            "sha256": sha256(content), "n_chars": len(text), "format": fmt,
            "retrieved_at": dt.datetime.fromtimestamp(orig.stat().st_mtime).isoformat(timespec="seconds"),
            "path": str(orig), "text_path": str(txt),
        })
    upsert_manifest(rows)
    log.info("berkshire: %d letters registered", len(rows))


if __name__ == "__main__":
    main()
