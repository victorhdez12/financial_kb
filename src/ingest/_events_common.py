"""Shared helpers for the events / geopolitics layer (src/ingest/events_*.py).

Follows docs/DATA_CONTRACT.md (section "Eventos"). Kept separate from
_extlong_common.py on purpose (owned by another ingest workstream).
"""
from __future__ import annotations

import datetime as dt
import logging
import os
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
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

EVENT_COLS = [
    "event_id", "name", "type", "country", "start_date", "end_date",
    "severity", "source", "url", "notes",
]
# Contract enum + inflation_crisis (explicitly requested for the RR chronology).
EVENT_TYPES = {
    "war", "banking_crisis", "currency_crisis", "sovereign_default", "market_crash",
    "recession", "pandemic", "oil_shock", "policy", "credit_event", "inflation_crisis",
}

log = logging.getLogger("ingest.events")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def data_root() -> Path:
    return Path(os.path.expanduser(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")))


def raw_dir(source: str) -> Path:
    p = data_root() / "raw" / source
    p.mkdir(parents=True, exist_ok=True)
    return p


def curated_dir(source: str) -> Path:
    p = data_root() / "curated" / source
    p.mkdir(parents=True, exist_ok=True)
    return p


def events_path(dataset: str) -> Path:
    p = data_root() / "events"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{dataset}.parquet"


_MAGIC = {
    "xls": [b"\xd0\xcf\x11\xe0"],
    "xlsx": [b"PK\x03\x04"],
    "zip": [b"PK\x03\x04"],
}


def validate_bytes(content: bytes, kind: str) -> None:
    head = content[:512].lstrip().lower()
    if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
        raise ValueError("download is an HTML page, not data")
    if kind in _MAGIC and not any(content.startswith(m) for m in _MAGIC[kind]):
        raise ValueError(f"unexpected magic bytes for {kind}: {content[:8]!r}")
    if kind == "csv" and b"," not in content[:2000]:
        raise ValueError("csv without commas")
    if kind == "json" and not head.startswith((b"[", b"{")):
        raise ValueError("not JSON")
    if len(content) < 500:
        raise ValueError(f"download too small ({len(content)} bytes)")


def download(urls: str | list[str], dest: Path, kind: str, *, max_age_hours: float = 24) -> Path:
    """Download the first working URL to dest (validated, atomic). Reuses dest if it is
    younger than max_age_hours. If every URL fails but dest exists, keeps the old copy."""
    if isinstance(urls, str):
        urls = [urls]
    if dest.exists() and (time.time() - dest.stat().st_mtime) / 3600 < max_age_hours:
        log.info("reuse cached %s", dest.name)
        return dest
    errors = []
    for url in urls:
        for attempt in range(3):
            try:
                r = requests.get(url, headers={"User-Agent": UA}, timeout=180)
                r.raise_for_status()
                validate_bytes(r.content, kind)
                tmp = dest.with_suffix(dest.suffix + ".part")
                tmp.write_bytes(r.content)
                tmp.replace(dest)
                log.info("downloaded %s (%d bytes) <- %s", dest.name, len(r.content), url)
                return dest
            except Exception as e:  # noqa: BLE001
                errors.append(f"{url}: {e}")
                time.sleep(2 * (attempt + 1))
                if isinstance(e, ValueError):
                    break  # bad content: no point retrying the same URL
    if dest.exists():
        log.warning("all downloads failed, keeping cached %s: %s", dest.name, errors[-1])
        return dest
    raise RuntimeError(f"download failed for {dest.name}: {errors}")


def to_date(x) -> dt.date | None:
    if x is None or (isinstance(x, float) and pd.isna(x)) or x is pd.NaT:
        return None
    try:
        ts = pd.Timestamp(x)
    except Exception:  # noqa: BLE001
        return None
    return None if pd.isna(ts) else ts.date()


def write_events(rows: list[dict] | pd.DataFrame, dataset: str) -> pd.DataFrame:
    df = pd.DataFrame(rows).reindex(columns=EVENT_COLS)
    bad = set(df["type"]) - EVENT_TYPES
    if bad:
        raise ValueError(f"unknown event types: {bad}")
    if df["event_id"].duplicated().any():
        dups = df.loc[df["event_id"].duplicated(), "event_id"].tolist()[:10]
        raise ValueError(f"duplicate event_id: {dups}")
    for c in ("start_date", "end_date"):
        df[c] = df[c].map(to_date)
    if df["start_date"].isna().any():
        raise ValueError("events without start_date")
    for c in ("event_id", "name", "type", "country", "severity", "source", "url", "notes"):
        df[c] = df[c].map(lambda v: None if v is None or (isinstance(v, float) and pd.isna(v)) else str(v))
        df[c] = df[c].astype("string")
    df = df.sort_values(["start_date", "event_id"]).reset_index(drop=True)
    import pyarrow as pa
    import pyarrow.parquet as pq

    schema = pa.schema([
        ("event_id", pa.string()), ("name", pa.string()), ("type", pa.string()),
        ("country", pa.string()), ("start_date", pa.date32()), ("end_date", pa.date32()),
        ("severity", pa.string()), ("source", pa.string()), ("url", pa.string()),
        ("notes", pa.string()),
    ])
    table = pa.Table.from_pandas(df, schema=schema, preserve_index=False)
    out = events_path(dataset)
    pq.write_table(table, out)
    log.info("%s: wrote %d events -> %s (%s)", dataset, len(df), out,
             df["type"].value_counts().to_dict())
    return df


# ---------------------------------------------------------------- country codes
_ISO_OVERRIDES = {
    "Bolivia": "BOL", "Cape Verde": "CPV", "Congo, Dem. Rep.": "COD", "Congo, Dem. Rep. of": "COD",
    "Congo, Rep.": "COG", "Congo, Rep. of": "COG", "Côte d'Ivoire": "CIV", "Cote d'Ivoire": "CIV",
    "Ivory Coast": "CIV", "Iran": "IRN", "Korea": "KOR", "South Korea": "KOR", "North Korea": "PRK",
    "Russia": "RUS", "Russian Federation": "RUS", "Turkey": "TUR", "Venezuela": "VEN",
    "Vietnam": "VNM", "Laos": "LAO", "Lao PDR": "LAO", "Syria": "SYR", "Tanzania": "TZA",
    "Macedonia": "MKD", "Macedonia, FYR": "MKD", "Moldova": "MDA", "Kyrgyz Republic": "KGZ",
    "Slovak Republic": "SVK", "Czech Republic": "CZE", "Swaziland": "SWZ", "Burma": "MMR",
    "Myanmar": "MMR", "Taiwan": "TWN", "United States": "USA", "United States of America": "USA",
    "United Kingdom": "GBR", "UK": "GBR", "Yugoslavia": "YUG", "Yugoslavia, SFR": "YUG",
    "Serbia": "SRB", "Gambia": "GMB", "Gambia, The": "GMB", "Guinea-Bissau": "GNB",
    "Central African Rep.": "CAF", "Central African Republic": "CAF", "Bosnia and Herzegovina": "BIH",
    "Sao Tome and Principe": "STP", "São Tomé and Príncipe": "STP", "Egypt": "EGY",
    "Germany": "DEU", "Prussia": "DEU", "Germany (Prussia)": "DEU", "German Federal Republic": "DEU",
    "Austria-Hungary": "AUT", "Ottoman Empire": "TUR", "Persia": "IRN", "Siam": "THA",
    "Sardinia": "ITA", "Piedmont": "ITA", "Kingdom of the Two Sicilies": "ITA", "Two Sicilies": "ITA",
    "Papal States": "VAT", "Bavaria": "DEU", "Baden": "DEU", "Saxony": "DEU", "Württemberg": "DEU",
    "Wuerttemburg": "DEU", "Hanover": "DEU", "Hesse Electoral": "DEU", "Hesse Grand Ducal": "DEU",
    "Mecklenburg Schwerin": "DEU", "Tuscany": "ITA", "Modena": "ITA", "Parma": "ITA",
    "Republic of Vietnam": "VNM", "Vietnam, Republic of": "VNM", "Yemen Arab Republic": "YEM",
    "Yemen People's Republic": "YEM", "Zanzibar": "TZA", "Kosovo": "XKX", "East Timor": "TLS",
    "Hong Kong": "HKG", "Hong Kong SAR": "HKG", "Micronesia": "FSM", "Brunei": "BRN",
    "Bahamas": "BHS", "Bahamas, The": "BHS", "Dominican Rep.": "DOM", "Dominican Republic": "DOM",
    "Democratic Republic of the Congo": "COD", "Congo": "COG", "Cambodia (Kampuchea)": "KHM",
    "Zimbabwe (Rhodesia)": "ZWE", "Rhodesia": "ZWE", "Sri Lanka": "LKA", "Libya": "LBY",
    "Madagascar (Malagasy)": "MDG", "Surinam": "SUR", "Belarus": "BLR", "Ukraine": "UKR",
    "Turkey/Ottoman Empire": "TUR", "Russia (Soviet Union)": "RUS", "Soviet Union": "RUS",
    "Bosnia-Herzegovina": "BIH", "Yemen (North Yemen)": "YEM", "South Yemen": "YEM",
    "Serbia (Yugoslavia)": "SRB", "Cambodia": "KHM", "Netherlands": "NLD", "Philippines": "PHL",
    "USSR": "RUS", "Myanmar (Burma)": "MMR", "DR Congo (Zaire)": "COD", "South Vietnam": "VNM",
    "Vietnam (North Vietnam)": "VNM", "North Vietnam": "VNM", "Sardinia/Piedmont": "ITA",
    "Cambodia (Kampuchea)": "KHM", "Yemen (North Yemen)": "YEM", "Bosnia-Herzegovina": "BIH",
    "Taiwan": "TWN", "Kosovo": "XKX",
    "Central African Rep": "CAF", "China, Mainland": "CHN", "China, P.R.": "CHN",
    "Congo, Dem Rep": "COD", "Congo, Rep": "COG", "Côte d’Ivoire": "CIV", "Dominican Rep": "DOM",
    "Iran, I.R. of": "IRN", "Kyrgyz Rep": "KGZ", "Lao People’s Dem. Rep.": "LAO",
    "Serbia, Republic of": "SRB", "Slovak Rep": "SVK", "St. Kitts and Nevis": "KNA",
    "São Tomé & Príncipe": "STP", "São Tomé and Principe": "STP",
}
_cache: dict[str, str] = {}


def iso3(name: str) -> str:
    """Best-effort country name -> ISO3. Returns the cleaned name if unknown."""
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return ""
    n = str(name).strip().rstrip("*").strip()
    import re

    n = re.sub(r"\s+\d+/?$", "", n)  # footnote markers like 'Argentina 8/'
    n = re.sub(r"\s+\d+/", "", n).strip()
    if n in _cache:
        return _cache[n]
    code = _ISO_OVERRIDES.get(n)
    if code is None:
        try:
            import pycountry

            code = pycountry.countries.lookup(n).alpha_3
        except Exception:  # noqa: BLE001
            code = n  # no fuzzy matching: rebel groups etc. must not map to countries
    _cache[n] = code
    return code


def is_iso3(code: str) -> bool:
    """True if code looks like a resolved ISO3 code (or a known historical override)."""
    return bool(code) and len(code) == 3 and code.isupper() and code.isalpha()

