from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import fitz  # PyMuPDF
import pandas as pd


def stable_id(prefix: str, *parts: str) -> str:
    raw = "||".join(str(p) for p in parts)
    return f"{prefix}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:20]}"


def chunk_text(text: str, max_chars: int = 1800, overlap: int = 220):
    text = " ".join(text.split())
    if not text:
        return []
    out = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        out.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return out


def extract_pdf(path: Path):
    doc = fitz.open(path)
    rows = []
    title = path.stem.replace('_', ' ')
    for page_no, page in enumerate(doc, start=1):
        text = page.get_text("text")
        for idx, chunk in enumerate(chunk_text(text)):
            rows.append({
                "chunk_id": stable_id("chunk", str(path.resolve()), str(page_no), str(idx)),
                "document_id": stable_id("doc", str(path.resolve())),
                "source_file": str(path.name),
                "title": title,
                "page": page_no,
                "chunk_index": idx,
                "text": chunk,
            })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    input_dir = Path(args.input)
    rows = []
    for path in sorted(input_dir.rglob('*.pdf')):
        print(f'Extracting {path}')
        rows.extend(extract_pdf(path))
    if not rows:
        raise SystemExit('No PDFs found.')
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(out, index=False)
    print(f'Wrote {len(rows):,} chunks -> {out}')


if __name__ == '__main__':
    main()
