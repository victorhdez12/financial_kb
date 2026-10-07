"""World Bank Commodity Price Data (The Pink Sheet), monthly 1960-present.

Run: .venv/bin/python -m src.ingest.wb_pinksheet
Raw:     $FIN_DATA_ROOT/raw/wb_pinksheet/CMO-Historical-Data-Monthly.xlsx
Curated: $FIN_DATA_ROOT/curated/wb_pinksheet/wb_<commodity>.parquet, wb_idx_<group>.parquet
"""
from __future__ import annotations

import re

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, find_link, log, raw_dir

SOURCE = "wb_pinksheet"
PAGE = "https://www.worldbank.org/en/research/commodity-markets"
FALLBACK = ("https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/"
            "related/CMO-Historical-Data-Monthly.xlsx")
LICENSE = "CC BY 4.0 (World Bank Open Data terms of use)"


def slug(s: str) -> str:
    s = s.lower().replace("**", "").replace("*", "")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def fetch():
    dest = raw_dir(SOURCE) / "CMO-Historical-Data-Monthly.xlsx"
    link = find_link(PAGE, r"CMO-Historical-Data-Monthly\.xlsx") or FALLBACK
    try:
        download(link, dest, "xlsx")
    except Exception as e:  # noqa: BLE001
        if not dest.exists():
            raise
        log.warning("Pink Sheet download failed (%s); using cached file", e)
    return link, dest


def parse_dates(col: pd.Series) -> pd.DatetimeIndex:
    s = col.astype(str).str.strip()
    ok = s.str.fullmatch(r"\d{4}M\d{2}")
    return pd.to_datetime(s.where(ok).str.replace("M", "-") + "-01", errors="coerce")


def category_for(name: str) -> str:
    n = name.lower()
    if "gold" in n:
        return "gold"
    return "commodities"


def load_prices(path) -> list[tuple[str, str, str, pd.Series]]:
    d = pd.read_excel(path, sheet_name="Monthly Prices", header=None)
    hdr_row = d.index[d.iloc[:, 1].astype(str).str.contains("Crude oil", na=False)][0]
    names, units = d.iloc[hdr_row], d.iloc[hdr_row + 1]
    body = d.iloc[hdr_row + 2:]
    idx = parse_dates(body[0])
    body = body[idx.notna()]
    idx = idx[idx.notna()]
    out = []
    for c in d.columns[1:]:
        name = str(names[c]).strip()
        if name == "nan":
            continue
        vals = pd.to_numeric(body[c].replace({"…": None, "..": None}), errors="coerce")
        out.append((name, str(units[c]).strip().strip("()"), "price", pd.Series(vals.values, index=idx)))
    return out


def load_indices(path) -> list[tuple[str, str, str, pd.Series]]:
    d = pd.read_excel(path, sheet_name="Monthly Indices", header=None)
    first = d.index[d[0].astype(str).str.fullmatch(r"\d{4}M\d{2}")][0]
    hdr = d.iloc[4:first, 1:]
    body = d.iloc[first:]
    idx = parse_dates(body[0])
    out = []
    for c in d.columns[1:]:
        labels = [str(v).strip() for v in hdr[c] if pd.notna(v) and str(v).strip()]
        if not labels:
            continue
        name = labels[-1]
        vals = pd.to_numeric(body[c], errors="coerce")
        out.append((name, "index 2010=100 (nominal USD)", "index", pd.Series(vals.values, index=idx)))
    return out


def main() -> None:
    url, path = fetch()
    cw = CatalogWriter(SOURCE, url=url, license=LICENSE)
    seen = set()
    for name, units, kind, s in load_prices(path) + load_indices(path):
        sid = ("wb_idx_" if kind == "index" else "wb_") + slug(name)
        if sid in seen:
            log.warning("duplicate id %s (%s) skipped", sid, name)
            continue
        seen.add(sid)
        cw.add(sid, s, name=f"World Bank Pink Sheet: {name.replace('**', '').strip()}",
               category=category_for(name) if kind == "price" else "commodities", frequency="M",
               units=units, country="WLD",
               transform_notes="monthly average, nominal USD; '…' -> NaN; see Description sheet in raw xlsx")
    cat = cw.close()
    print(cat[["series_id", "units", "start", "end"]].to_string(index=False))


if __name__ == "__main__":
    main()
