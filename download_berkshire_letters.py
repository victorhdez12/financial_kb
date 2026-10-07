#!/usr/bin/env python3
"""
Descarga las cartas anuales de Berkshire Hathaway (1977 → último año publicado).

- 1977-1999: HTML → se guarda como texto limpio (.txt)
- 2000-hoy : PDF  → se guarda tal cual (.pdf)

Destino: $FIN_DATA_ROOT/berkshire_letters (por defecto ~/financial_archive/berkshire_letters).
"""

import os
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(os.getenv("FIN_DATA_ROOT", "~/financial_archive")).expanduser()
OUTPUT_DIR = ROOT / "berkshire_letters"
BASE_URL = "https://www.berkshirehathaway.com/letters"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

FIRST_YEAR = 1977
# La carta del año N se publica en febrero/marzo de N+1.
LAST_YEAR = datetime.now().year - 1


def letter_url(year: int) -> str:
    """El patrón de URL de berkshirehathaway.com cambia según la época."""
    if year <= 1997:
        return f"{BASE_URL}/{year}.html"
    if year <= 1999:
        return f"{BASE_URL}/{year}htm.html"
    if year <= 2002:
        return f"{BASE_URL}/{year}pdf.pdf"
    return f"{BASE_URL}/{year}ltr.pdf"


def clean_text(html: str) -> str:
    """Extrae el texto legible de la carta."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    lines = [line.strip() for line in soup.get_text(separator="\n").splitlines()]
    text = "\n".join(line for line in lines if line)
    text = re.sub(r"^[\x00-\x1f]+", "", text)
    return text.strip()


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"📁 Guardando en: {OUTPUT_DIR}\n")

    ok = fail = skipped = 0

    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        url = letter_url(year)
        is_pdf = url.endswith(".pdf")
        filepath = OUTPUT_DIR / f"{year}_Berkshire_Letter.{'pdf' if is_pdf else 'txt'}"

        if filepath.exists() and filepath.stat().st_size > 3000:
            skipped += 1
            continue

        print(f"⬇️  {year}...", end=" ", flush=True)
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()

            if is_pdf:
                if not r.content.startswith(b"%PDF"):
                    print("❌ La respuesta no es un PDF")
                    fail += 1
                    continue
                filepath.write_bytes(r.content)
                print(f"OK ({len(r.content)//1024} KB)")
            else:
                r.encoding = r.apparent_encoding or "windows-1252"
                text = clean_text(r.text)
                if len(text) < 1000:
                    print("❌ Texto demasiado corto (posible error)")
                    fail += 1
                    continue
                filepath.write_text(text, encoding="utf-8")
                print(f"OK ({len(text)//1024} KB)")
            ok += 1

        except Exception as e:
            print(f"❌ {e}")
            fail += 1

        time.sleep(0.7)

    print("\n" + "=" * 50)
    print(f"✅ Descargadas : {ok}")
    print(f"⏭️  Omitidas   : {skipped}")
    print(f"❌ Fallidas   : {fail}")
    print(f"📂 Carpeta    : {OUTPUT_DIR}")
    print("=" * 50)


if __name__ == "__main__":
    main()
