"""Howard Marks / Oaktree memos (1990 -> today), from oaktreecapital.com/insights/memos.

The memos page lists (a) archived memos 1990-2020 as direct PDF links and
(b) recent memos (2020-10 ->) as /insights/memo/<slug> pages, each with an English PDF.
For (b) we download the English PDF; if there is none we keep the HTML page.

    .venv/bin/python -m src.ingest.texts_oaktree
"""
from __future__ import annotations

import html as htmlmod
import re

from src.ingest.texts_common import Doc, http_get, log, run_docs

BASE = "https://www.oaktreecapital.com"
LIST_URL = f"{BASE}/insights/memos"
LICENSE = ("Published free of charge by the rights holder (Oaktree Capital Management) on "
           "oaktreecapital.com/insights; personal research use, no redistribution")
COLL = "manager_memos/oaktree_marks"


def slugify(s: str) -> str:
    s = htmlmod.unescape(s).lower().replace("’", "").replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:70]


def english_pdf(page: str) -> str | None:
    for title, url in re.findall(r"openPDF\('(.*?)','(.*?)'\)", page):
        if "translated-memos" in url or re.search(r"_(JPN|KRN|SC|TC|ESP|POR|GER|FRA)$", title):
            continue
        return url
    m = re.search(r'href="([^"]*/docs/default-source/memos/[^"]+\.pdf[^"]*)"', page)
    return (BASE + m.group(1) if m and m.group(1).startswith("/") else m.group(1)) if m else None


def build_docs() -> list[Doc]:
    page = http_get(LIST_URL).text
    docs: list[Doc] = []
    seen: set[str] = set()
    archived = re.findall(
        r'datetime="?>?([0-9-]{10})T[^>]*>[^<]*</time>\s*<a class="oc-title-link" '
        r"href=\"javascript:openPDF\('(.*?)','(.*?)'\)", page)
    cards = re.findall(
        r'datetime="?>?([0-9-]{10})T[^>]*>[^<]*</time>\s*<a class="oc-title-link" '
        r'href="(/insights/memo/[^"]+)">([^<]+)<', page)
    log.info("oaktree: %d archived PDFs, %d memo pages", len(archived), len(cards))
    for date, title, url in archived:
        mid = f"marks_{date}_{slugify(title)}"
        if mid in seen:
            continue
        seen.add(mid)
        docs.append(Doc(mid, COLL, "Howard Marks", htmlmod.unescape(title), date,
                        url.split("?")[0] if False else url, LICENSE, expect="pdf"))
    for date, path, title in cards:
        mid = f"marks_{date}_{slugify(title)}"
        if mid in seen:
            continue
        seen.add(mid)
        try:
            mp = http_get(BASE + path).text
            pdf = english_pdf(mp)
        except Exception as e:  # pragma: no cover
            log.error("memo page %s: %s", path, e)
            pdf = None
        if pdf:
            docs.append(Doc(mid, COLL, "Howard Marks", htmlmod.unescape(title), date, pdf,
                            LICENSE, expect="pdf"))
        else:
            docs.append(Doc(mid, COLL, "Howard Marks", htmlmod.unescape(title), date,
                            BASE + path, LICENSE, expect="html", selector=".article-content"))
    return docs


def main() -> None:
    run_docs(build_docs())


if __name__ == "__main__":
    main()
