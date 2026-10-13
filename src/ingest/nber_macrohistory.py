"""NBER Macrohistory Database - curated selection of pre-1940/pre-1960 US (and some European)
interest rates, prices, stock prices, activity and money series that FRED does not carry
(or carries only from later dates).

Run: .venv/bin/python -m src.ingest.nber_macrohistory
Raw:     $FIN_DATA_ROOT/raw/nber_macrohistory/<id>.dat + <id>.txt (documentation)
Curated: $FIN_DATA_ROOT/curated/nber_macrohistory/nber_<id>.parquet
"""
from __future__ import annotations

import re
import time

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, http_get, log, raw_dir, validate_bytes

SOURCE = "nber_macrohistory"
BASE = "https://data.nber.org/databases/macrohistory/rectdata/{ch}/{sid}.dat"
DOC = "https://data.nber.org/databases/macrohistory/rectdata/{ch}/docs/{sid}.txt"
PAGE = "https://www.nber.org/research/data/nber-macrohistory-database"
LICENSE = "NBER Macrohistory Database - public, free for research use; cite NBER and original sources in docs"

# id -> (category, country)
SELECTION = {
    # 13 interest rates
    "m13001": ("rates", "USA"),   # call money rates 1857-1970
    "m13002": ("rates", "USA"),   # commercial paper NYC 1857-1971
    "m13009": ("rates", "USA"),   # NY Fed discount rate 1914-1969
    "m13019": ("credit", "USA"),  # railroad bond yields high grade (Macaulay) 1857-1937
    "m13029a": ("rates", "USA"),  # short-term US securities 1920-1934
    "m13033a": ("rates", "USA"),  # long-term US bond yield 1919-1944
    "m13033b": ("rates", "USA"),  # long-term US bond yield 1941-1967
    "m13035": ("credit", "USA"),  # corporate bonds highest rating 1919-1968
    "m13036": ("credit", "USA"),  # corporate bonds lowest rating 1919-1968
    "q13020": ("rates", "USA"),   # municipal bond yields 1857-1914 (quarterly)
    "m13013": ("rates", "GBR"),   # Bank of England minimum discount rate 1836-1939
    "m13016": ("rates", "GBR"),   # London open market discount 1824-1939
    "m13014": ("rates", "FRA"),   # Bank of France discount rate 1852-1940
    "m13015": ("rates", "DEU"),   # Reichsbank discount rate 1876-1938
    # 11 security markets
    "m11025a": ("markets", "USA"),  # Cowles/S&P all common stock index 1871-1956
    "m11005": ("markets", "USA"),   # railroad stock prices 1855-1937
    "m11009b": ("markets", "USA"),  # Dow Jones industrials 1914-1968
    "m11016": ("bond_returns", "USA"),  # railroad bond prices 1857-1937
    # 04 prices
    "m04048a": ("inflation", "USA"),  # wholesale prices 1850-1894
    "m04048b": ("inflation", "USA"),  # BLS WPI 1890-1914
    "m04048c": ("inflation", "USA"),  # BLS WPI 1913-1968
    "m04072": ("inflation", "USA"),   # cost of living 1910-1944
    "m04128": ("inflation", "USA"),   # CPI all items 1913-1970
    "m04053": ("inflation", "GBR"),   # GB wholesale prices 1885-1951
    "m04057": ("inflation", "FRA"),   # France wholesale prices 1913-1939
    "m04054": ("inflation", "DEU"),   # Hamburg wholesale prices 1879-1914
    "m04202": ("commodities", "USA"),  # 15 sensitive industrial raw commodities 1919-1958
    # 01/08/12/16 activity
    "m01001": ("growth", "USA"),   # Babson business activity 1889-1957
    "m01130a": ("growth", "USA"),  # pig iron production 1877-1941
    "a01206": ("growth", "USA"),   # pig iron production annual 1846-1963
    "m08292a": ("employment", "USA"),  # unemployment rate 1929-1942
    "m12014": ("growth", "USA"),   # bank clearings outside NYC 1875-1964
    "m12020a": ("growth", "USA"),  # clearings index of business 1875-1929
    "m12020b": ("growth", "USA"),  # clearings index of business 1919-1939
    "m16002a": ("growth", "USA"),  # leading index 1919-1940
    "m16003a": ("growth", "USA"),  # coincident index 1919-1940
    # 14 money & banking
    "m14144a": ("money", "USA"),   # money stock 1907-1946
    "m14076a": ("money", "USA"),   # monetary gold stock 1878-1914
    "m14076b": ("money", "USA"),   # monetary gold stock 1914-1946
}


# --------------------------------------------------------------------------------------
# Extension (2026-10): rule-based selection of US series from the chapter index pages.
# The curated SELECTION above keeps its categories; everything below is added on top.
# NBER Macrohistory files are frozen (last modified 2001-2002), so cached raw .dat/.txt
# files are reused instead of re-downloaded.
# --------------------------------------------------------------------------------------
INDEX = "https://data.nber.org/databases/macrohistory/contents/chapter{ch}.html"
EXT_ALL = {"04", "07", "09", "10", "11", "12", "13", "14", "15", "16"}  # all U.S. series
EXT_RULES = {  # chapter -> regex on the index title (U.S. series only)
    "01": r"index of|industrial production|pig iron|steel ingot|automobile|electric(al)? (power|energy)"
          r"|bituminous coal production|crude petroleum production|cotton consumption",
    "02": r"total|index",
    "03": r"freight car|ton-miles, revenue",
    "06": r"total|index|department store|retail|sales",
    "08": r"unemploy|labor force|personal income|national income|payroll|employment, total|total employ"
          r"|nonagricultural|all manufactur|manufacturing industries|composite"
          r"|factory employment, (total|seasonally)|index of factory employment(?!,)|wage"
          r"|earnings, (all|total|manufactur)|hours of work per week, (all|total|manufactur)|insured",
}
CH_CAT = {"01": "growth", "02": "housing", "03": "growth", "04": "inflation", "06": "growth",
          "07": "growth", "08": "employment", "09": "growth", "10": "credit", "11": "markets",
          "12": "growth", "13": "rates", "14": "money", "15": "fiscal", "16": "growth"}


def ext_category(sid: str, title: str) -> str:
    ch = sid[1:3]
    t = title.lower()
    if ch == "14" and re.search(r"loan|credit|discount|debits|failure|suspension", t):
        return "credit"
    if ch == "09" and re.search(r"failure|liabilit|debt", t):
        return "credit"
    if ch == "13" and re.search(r"corporate|railroad|municipal|industrial|utility", t):
        return "credit"
    if ch == "11" and "bond" in t:
        return "bond_returns"
    return CH_CAT[ch]


def extended_selection() -> dict[str, tuple[str, str, str]]:
    """id -> (category, country, index title) for the rule-based extension."""
    idx_dir = raw_dir(SOURCE) / "_index"
    idx_dir.mkdir(exist_ok=True)
    out = {}
    for ch in sorted(EXT_ALL | set(EXT_RULES)):
        p = idx_dir / f"chapter{ch}.html"
        if not p.exists():
            try:
                p.write_text(http_get(INDEX.format(ch=ch), timeout=90).text)
            except Exception as e:  # noqa: BLE001
                log.warning("index chapter %s unavailable: %s", ch, e)
                continue
        for m in re.finditer(r"<td>([amq]\d{5}[a-z]?)</td><td>([^<]+)</td>", p.read_text(errors="replace")):
            sid, title = m[1], m[2].strip()
            if not title.startswith("U.S.") or sid in SELECTION:
                continue
            if ch in EXT_ALL or (ch in EXT_RULES and re.search(EXT_RULES[ch], title, re.I)):
                out[sid] = (ext_category(sid, title), "USA", title)
    log.info("extended NBER selection: %d series", len(out))
    return out


def prefetch(ids: list[str], workers: int = 6) -> None:
    """Download missing .dat/.txt files of the extension in parallel (polite: 6 workers).
    404s are recorded in raw/_index/missing.txt and not retried on later runs."""
    import requests
    from concurrent.futures import ThreadPoolExecutor

    from src.ingest._extlong_common import UA

    rd = raw_dir(SOURCE)
    miss_p = rd / "_index" / "missing.txt"
    missing = set(miss_p.read_text().split()) if miss_p.exists() else set()
    todo = [i for i in ids if not (rd / f"{i}.dat").exists() and i not in missing]
    sess = requests.Session()
    sess.headers["User-Agent"] = UA

    def one(sid: str) -> str | None:
        ch = re.search(r"\d{2}", sid).group(0)
        for attempt in range(3):
            try:
                r = sess.get(BASE.format(ch=ch, sid=sid), timeout=60)
                if r.status_code == 404:
                    return sid
                r.raise_for_status()
                if r.content.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
                    return sid
                d = sess.get(DOC.format(ch=ch, sid=sid), timeout=60)
                if d.ok:
                    (rd / f"{sid}.txt").write_text(d.text)
                (rd / f"{sid}.dat").write_bytes(r.content)
                return None
            except Exception:  # noqa: BLE001
                time.sleep(2 * (attempt + 1))
        log.warning("prefetch failed %s", sid)
        return None

    log.info("prefetching %d NBER files", len(todo))
    with ThreadPoolExecutor(workers) as ex:
        new_missing = {m for m in ex.map(one, todo) if m}
    if new_missing:
        miss_p.write_text("\n".join(sorted(missing | new_missing)))
        log.info("%d ids listed in the index have no .dat file (404)", len(new_missing))


def parse_doc(text: str) -> dict:
    lines = [l.strip().strip('"').removeprefix("c").strip() for l in text.splitlines()]
    title = ""
    for a, b in zip(lines, lines[1:]):
        if a and re.fullmatch(r"-{4,}", b):  # title is underlined with dashes
            title = a.title()
            break
    units = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("UNITS:")), "")
    units = units.strip(" \"") or "see raw doc"
    md = re.search(r"MD=\s*([-\dEe.+]+)", text)
    return {"title": title, "units": units, "md": float(md.group(1)) if md else None}


def parse_dat(text: str, freq: str, md: float | None) -> pd.Series:
    vals, idx = [], []
    for line in text.splitlines():
        p = line.split()
        if not p:
            continue
        try:
            if freq == "A":
                y, v = int(p[0]), p[1]
                d = pd.Timestamp(y, 1, 1)
            else:
                y, k, v = int(p[0]), int(p[1]), p[2]
                d = pd.Timestamp(y, k, 1) if freq == "M" else pd.Timestamp(y, 3 * (k - 1) + 1, 1)
            x = float(v)
        except (ValueError, IndexError):
            continue
        if md is not None and abs(x - md) < 1e-30 + abs(md) * 1e-6:
            x = float("nan")
        idx.append(d)
        vals.append(x)
    return pd.Series(vals, index=pd.DatetimeIndex(idx))


# Transcription errors in the NBER .dat files, verified against the neighbouring years.
# sid -> list of (first date, last date, factor, reason)
KNOWN_FIXES: dict[str, list[tuple[str, str, float, str]]] = {
    "m12014": [("1915-01-01", "1915-12-01", 10.0,
                "1915 shifted one decimal place in the NBER file (~20 vs ~197 in Dec-1914 and ~252 in Jan-1916)")],
}


def apply_fixes(sid: str, s: pd.Series) -> tuple[pd.Series, str]:
    notes = []
    for lo, hi, factor, why in KNOWN_FIXES.get(sid, []):
        m = (s.index >= pd.Timestamp(lo)) & (s.index <= pd.Timestamp(hi))
        if m.any():
            s = s.copy()
            s[m] = s[m] * factor
            notes.append(f"FIX {lo}..{hi} x{factor:g}: {why}")
    return s, ("; " + "; ".join(notes)) if notes else ""


def main() -> None:
    cw = CatalogWriter(SOURCE, url=PAGE, license=LICENSE)
    rd = raw_dir(SOURCE)
    todo = {sid: (cat, country, "") for sid, (cat, country) in SELECTION.items()}
    ext = extended_selection()
    prefetch(list(ext))
    missing_p = rd / "_index" / "missing.txt"
    missing = set(missing_p.read_text().split()) if missing_p.exists() else set()
    todo.update({k: v for k, v in ext.items() if k not in missing})
    for sid, (cat, country, idx_title) in todo.items():
        ch = re.search(r"\d{2}", sid).group(0)
        freq = {"m": "M", "q": "Q", "a": "A"}[sid[0]]
        url = BASE.format(ch=ch, sid=sid)
        try:
            if sid not in SELECTION and (rd / f"{sid}.dat").exists():
                raise FileExistsError("cached (frozen NBER file)")
            time.sleep(0.2)
            r = http_get(url, timeout=60)
            try:
                validate_bytes(r.content, "dat")
            except ValueError as ve:  # short annual series are legitimately < 1 KB
                if "too small" not in str(ve) or len(r.content) < 20:
                    raise
            (rd / f"{sid}.dat").write_bytes(r.content)
            try:
                doc = http_get(DOC.format(ch=ch, sid=sid), timeout=60).text
                (rd / f"{sid}.txt").write_text(doc)
            except Exception:  # noqa: BLE001
                doc = ""
        except Exception as e:  # noqa: BLE001
            if (rd / f"{sid}.dat").exists():
                if not isinstance(e, FileExistsError):
                    log.warning("%s download failed (%s); using cached", sid, e)
                doc = (rd / f"{sid}.txt").read_text() if (rd / f"{sid}.txt").exists() else ""
            else:
                log.error("skip %s: %s", sid, e)
                continue
        meta = parse_doc(doc)
        s = parse_dat((rd / f"{sid}.dat").read_text(errors="replace"), freq, meta["md"])
        s, fix_note = apply_fixes(sid, s)
        n = cw.add(f"nber_{sid}", s, name=meta["title"] or idx_title or sid, category=cat, frequency=freq,
                   units=meta["units"], country=country,
                   transform_notes=f"NBER series {sid}; missing code {meta['md']} -> NaN; see raw {sid}.txt for source/notes"
                                   + fix_note,
                   url=url)
        if not n:
            log.warning("no data parsed for %s", sid)
    cat = cw.close()
    print(cat[["series_id", "frequency", "start", "end", "name"]].to_string(index=False))


if __name__ == "__main__":
    main()
