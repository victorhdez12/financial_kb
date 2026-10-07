#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FINANCIAL ARCHIVE BUILDER v2

Downloads and organizes:
  - SEC EDGAR 10-K filings (1994 -> present)
  - SEC CompanyFacts XBRL data
  - FRED macroeconomic / market series
  - BLS labor / CPI series
  - Optional historical annual-report PDFs from a user-supplied CSV

Historical limitation:
  SEC EDGAR starts in 1994/1995. This script therefore does NOT pretend
  that SEC 10-K documents exist electronically back to 1920.
  The optional legacy module downloads pre-1994 annual reports only from
  URLs explicitly listed in legacy_sources.csv.

Designed for a financial KG / RAG / quantitative research archive.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

try:  # Optional: read FIN_DATA_ROOT / API keys from the project's .env file.
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

# ============================================================
# CONFIG
# ============================================================

ROOT = Path(os.getenv("FIN_DATA_ROOT", "~/financial_archive")).expanduser()
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "").strip()
FRED_API_KEY = os.getenv("FRED_API_KEY", "").strip()
# Optional. Without a key the BLS API returns at most 10 years per request.
BLS_API_KEY = os.getenv("BLS_API_KEY", "").strip()

SEC_BASE = "https://www.sec.gov"
SEC_DATA_BASE = "https://data.sec.gov"
FRED_BASE = "https://api.stlouisfed.org/fred"
BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

SEC_SLEEP = 0.30  # ~3.3 req/s, comfortably below SEC's stated 10 req/s limit.
GENERAL_SLEEP = 0.25

# Explicit CIKs for a stable research universe.
# XOM intentionally includes both the historical Exxon Mobil Corporation CIK
# and the 2026 successor registrant CIK.
COMPANIES: Dict[str, List[Dict[str, str]]] = {
    "AAPL": [{"cik": "0000320193", "name": "Apple Inc."}],
    "MSFT": [{"cik": "0000789019", "name": "Microsoft Corporation"}],
    "KO": [{"cik": "0000021344", "name": "The Coca-Cola Company"}],
    "GE": [{"cik": "0000040545", "name": "General Electric Company"}],
    "XOM": [
        {"cik": "0000034088", "name": "Exxon Mobil Corporation"},
        {"cik": "0002115436", "name": "ExxonMobil Holdings Corporation"},
    ],
    "JPM": [{"cik": "0000019617", "name": "JPMorgan Chase & Co."}],
}

# 10-K405 was used until 2002 when an insider-filing box was checked; it is a full annual report.
TEN_K_FORMS = {"10-K", "10-K405"}

FRED_SERIES = {
    # Growth / activity
    "GNPCA": ("growth", "Real Gross National Product"),
    "GDP": ("growth", "Gross Domestic Product"),
    "GDPC1": ("growth", "Real Gross Domestic Product"),
    "A191RL1Q225SBEA": ("growth", "Real GDP Growth Rate"),
    "INDPRO": ("growth", "Industrial Production Index"),
    "TCU": ("growth", "Capacity Utilization"),

    # Inflation
    "CPIAUCSL": ("inflation", "CPI All Urban Consumers"),
    "CPILFESL": ("inflation", "CPI Less Food and Energy"),
    "PCEPI": ("inflation", "PCE Price Index"),
    "PCEPILFE": ("inflation", "Core PCE Price Index"),
    "PPIACO": ("inflation", "Producer Price Index All Commodities"),
    "T5YIE": ("inflation_expectations", "5-Year Breakeven Inflation Rate"),
    "T10YIE": ("inflation_expectations", "10-Year Breakeven Inflation Rate"),

    # Labor
    "UNRATE": ("employment", "US Unemployment Rate"),
    "U6RATE": ("employment", "U-6 Unemployment Rate"),
    "PAYEMS": ("employment", "Total Nonfarm Payroll Employment"),
    "CIVPART": ("employment", "Civilian Labor Force Participation Rate"),
    "EMRATIO": ("employment", "Employment-Population Ratio"),
    "ICSA": ("employment", "Initial Unemployment Claims"),
    "JTSJOL": ("employment", "Job Openings"),
    "CES0500000003": ("wages", "Average Hourly Earnings of All Private Employees"),

    # Consumption
    "PCE": ("consumption", "Personal Consumption Expenditures"),
    "PCEDG": ("consumption", "PCE Durable Goods"),
    "PCEND": ("consumption", "PCE Nondurable Goods"),
    "RSAFS": ("consumption", "Advance Retail Sales"),
    "UMCSENT": ("consumer_sentiment", "University of Michigan Consumer Sentiment"),

    # Rates / curve
    "FEDFUNDS": ("interest_rates", "Effective Federal Funds Rate"),
    "DFF": ("interest_rates", "Federal Funds Effective Rate Daily"),
    "DGS3MO": ("interest_rates", "3-Month Treasury Constant Maturity Rate"),
    "DGS2": ("interest_rates", "2-Year Treasury Constant Maturity Rate"),
    "DGS5": ("interest_rates", "5-Year Treasury Constant Maturity Rate"),
    "DGS10": ("interest_rates", "10-Year Treasury Constant Maturity Rate"),
    "DGS30": ("interest_rates", "30-Year Treasury Constant Maturity Rate"),
    "T10Y2Y": ("yield_curve", "10-Year Minus 2-Year Treasury Yield"),
    "T10Y3M": ("yield_curve", "10-Year Minus 3-Month Treasury Yield"),
    "SOFR": ("interest_rates", "Secured Overnight Financing Rate"),
    "MORTGAGE30US": ("housing_rates", "30-Year Mortgage Rate"),

    # Money / liquidity / financial conditions
    "M1SL": ("money", "M1 Money Stock"),
    "M2SL": ("money", "M2 Money Stock"),
    "WALCL": ("liquidity", "Federal Reserve Total Assets"),
    "NFCI": ("financial_conditions", "Chicago Fed National Financial Conditions Index"),
    "ANFCI": ("financial_conditions", "Adjusted National Financial Conditions Index"),
    "BAMLH0A0HYM2": ("credit", "US High Yield Option-Adjusted Spread"),
    "BAMLC0A0CM": ("credit", "US Corporate Master Option-Adjusted Spread"),
    "BAA10Y": ("credit", "Moody's Baa Corporate Bond Spread Proxy"),
    "AAA10Y": ("credit", "Moody's Aaa Corporate Bond Spread Proxy"),

    # Housing
    "HOUST": ("housing", "Housing Starts"),
    "PERMIT": ("housing", "Building Permits"),
    "HNFSEPUSSA": ("housing", "New One Family Houses Sold"),
    "CSUSHPISA": ("housing", "S&P/Case-Shiller US National Home Price Index"),

    # Market / commodities / FX
    "SP500": ("markets", "S&P 500 Index"),
    "VIXCLS": ("markets", "CBOE Volatility Index"),
    "DTWEXBGS": ("fx", "Trade Weighted US Dollar Index"),
    "DEXUSEU": ("fx", "US Dollar / Euro Exchange Rate"),
    "DCOILWTICO": ("commodities", "WTI Crude Oil Price"),
    # GOLDAMGBD228NLBM (LBMA gold) was discontinued on FRED; source gold elsewhere.

    # Fiscal / cycle
    "GFDEBTN": ("fiscal", "Federal Debt Total Public Debt"),
    "GFDEGDQ188S": ("fiscal", "Federal Debt as Percent of GDP"),
    "FYFSGDA188S": ("fiscal", "Federal Surplus or Deficit as Percent of GDP"),
    "USREC": ("business_cycle", "US Recession Indicator"),
}

BLS_SERIES = {
    "LNS14000000": "Unemployment Rate",
    "LNS11000000": "Civilian Labor Force",
    "LNS12000000": "Employment Level",
    "LNS11300000": "Labor Force Participation Rate",
    "CES0000000001": "Total Nonfarm Payroll Employment",
    "CES0500000003": "Average Hourly Earnings",
    "CUUR0000SA0": "CPI All Urban Consumers NSA",
    "CUSR0000SA0": "CPI All Urban Consumers SA",
}

# ============================================================
# DIRECTORIES / LOGGING
# ============================================================

DIRECTORIES = [
    "sec/companies",
    "sec/10k",
    "sec/companyfacts",
    "macro/fred",
    "macro/bls",
    "macro/derived",
    "legacy_annual_reports",
    "manifests",
    "logs",
]

for d in DIRECTORIES:
    (ROOT / d).mkdir(parents=True, exist_ok=True)

class RedactSecretsFilter(logging.Filter):
    """Keep API keys out of logs (exception messages include full request URLs)."""

    PATTERN = re.compile(r"((?:api_key|registrationkey)=)[^&\s'\"]+", re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = self.PATTERN.sub(r"\1REDACTED", message)
        if redacted != message:
            record.msg, record.args = redacted, None
        return True


_log_handlers = [
    logging.FileHandler(ROOT / "logs" / "download.log"),
    logging.StreamHandler(sys.stdout),
]
for _handler in _log_handlers:
    _handler.addFilter(RedactSecretsFilter())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=_log_handlers,
)
logger = logging.getLogger("financial_archive")

# ============================================================
# HTTP
# ============================================================


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=6,
        connect=6,
        read=6,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SEC_SESSION = build_session()
FRED_SESSION = build_session()
BLS_SESSION = build_session()
GENERIC_SESSION = build_session()


def validate_sec() -> None:
    if not SEC_USER_AGENT:
        raise RuntimeError(
            'SEC_USER_AGENT is missing. Example:\n'
            'export SEC_USER_AGENT="Victor Financial Research victor@example.com"'
        )


def validate_fred() -> None:
    if not FRED_API_KEY:
        raise RuntimeError(
            'FRED_API_KEY is missing. Example:\n'
            'export FRED_API_KEY="YOUR_FRED_KEY"'
        )


SEC_HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
}


def sec_get(url: str, *, stream: bool = False) -> requests.Response:
    response = SEC_SESSION.get(url, headers=SEC_HEADERS, timeout=90, stream=stream)
    response.raise_for_status()
    time.sleep(SEC_SLEEP)
    return response


def generic_get(url: str, *, headers: Optional[dict] = None) -> requests.Response:
    response = GENERIC_SESSION.get(url, headers=headers, timeout=90)
    response.raise_for_status()
    time.sleep(GENERAL_SLEEP)
    return response


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def download_file(
    url: str,
    destination: Path,
    *,
    session: requests.Session,
    headers: Optional[dict] = None,
    sleep_seconds: float = GENERAL_SLEEP,
    force: bool = False,
) -> bool:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 100 and not force:
        return True

    response = session.get(url, headers=headers, timeout=120, stream=True)
    response.raise_for_status()

    tmp = destination.with_suffix(destination.suffix + ".part")
    with tmp.open("wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
    tmp.replace(destination)
    time.sleep(sleep_seconds)
    return True


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("_")

# ============================================================
# SEC HELPERS
# ============================================================


def save_sec_company_reference() -> None:
    """Save SEC ticker universe for reference only."""
    validate_sec()
    url = f"{SEC_BASE}/files/company_tickers.json"
    destination = ROOT / "sec/companies/sec_company_tickers.json"
    try:
        data = sec_get(url).json()
        write_json(destination, data)
    except Exception as exc:
        logger.warning("Could not save SEC company ticker reference: %s", exc)


def normalize_submission_table(blob: dict) -> List[dict]:
    if "filings" in blob and isinstance(blob["filings"], dict) and "recent" in blob["filings"]:
        blob = blob["filings"]["recent"]

    arrays = [v for v in blob.values() if isinstance(v, list)]
    if not arrays:
        return []
    n = len(arrays[0])

    rows = []
    for i in range(n):
        row = {}
        for key, value in blob.items():
            if isinstance(value, list) and len(value) == n:
                row[key] = value[i]
        rows.append(row)
    return rows


def get_all_submissions(cik: str) -> List[dict]:
    validate_sec()
    cik = f"{int(cik):010d}"
    url = f"{SEC_DATA_BASE}/submissions/CIK{cik}.json"

    data = SEC_SESSION.get(url, headers=SEC_HEADERS, timeout=90)
    data.raise_for_status()
    time.sleep(SEC_SLEEP)

    rows = normalize_submission_table(data.json())
    files = data.json().get("filings", {}).get("files", [])

    for info in files:
        filename = info.get("name")
        if not filename:
            continue
        logger.info("SEC historical submissions: %s", filename)
        old_url = f"{SEC_DATA_BASE}/submissions/{filename}"
        response = SEC_SESSION.get(old_url, headers=SEC_HEADERS, timeout=90)
        response.raise_for_status()
        rows.extend(normalize_submission_table(response.json()))
        time.sleep(SEC_SLEEP)

    unique = {}
    for row in rows:
        acc = row.get("accessionNumber")
        if acc:
            unique[acc] = row
    return list(unique.values())


def filing_year(filing: dict) -> Optional[int]:
    for field in ("reportDate", "filingDate"):
        value = str(filing.get(field, ""))
        m = re.match(r"(\d{4})", value)
        if m:
            return int(m.group(1))
    return None


def sec_url_candidates(cik: str, accession: str, primary_document: str) -> Dict[str, List[str]]:
    cik_int = str(int(cik))
    acc_compact = accession.replace("-", "")

    # Per SEC documentation, direct complete-file/index paths use the accession
    # number with dashes. Post-May-2000 filings also have an alternate directory
    # path containing the accession without dashes.
    complete = [
        f"{SEC_BASE}/Archives/edgar/data/{cik_int}/{accession}.txt",
        f"{SEC_BASE}/Archives/edgar/data/{cik_int}/{acc_compact}/{accession}.txt",
    ]
    index = [
        f"{SEC_BASE}/Archives/edgar/data/{cik_int}/{accession}-index.html",
        f"{SEC_BASE}/Archives/edgar/data/{cik_int}/{acc_compact}/{accession}-index.html",
    ]
    primary = []
    if primary_document:
        primary.extend([
            f"{SEC_BASE}/Archives/edgar/data/{cik_int}/{acc_compact}/{primary_document}",
        ])

    return {"complete": complete, "index": index, "primary": primary}


def download_first_available(
    urls: Iterable[str],
    destination: Path,
    *,
    force: bool = False,
) -> Optional[str]:
    if destination.exists() and destination.stat().st_size > 100 and not force:
        return "existing"

    last_error = None
    for url in urls:
        try:
            download_file(
                url,
                destination,
                session=SEC_SESSION,
                headers=SEC_HEADERS,
                sleep_seconds=SEC_SLEEP,
                force=force,
            )
            return url
        except requests.HTTPError as exc:
            last_error = exc
            continue
        except Exception as exc:
            last_error = exc
            continue

    logger.warning("All SEC URL candidates failed for %s: %s", destination, last_error)
    return None


def decode_sec_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def extract_10k_document(raw_submission: str) -> Tuple[str, str]:
    """Return (filename, cleaned_text) for the 10-K block inside complete submission."""
    blocks = re.findall(r"<DOCUMENT>(.*?)</DOCUMENT>", raw_submission, flags=re.IGNORECASE | re.DOTALL)

    selected = None
    selected_filename = ""
    for block in blocks:
        type_match = re.search(r"<TYPE>\s*([^\s<]+)", block, flags=re.IGNORECASE)
        doc_type = type_match.group(1).upper() if type_match else ""
        if doc_type == "10-K":
            selected = block
            fn = re.search(r"<FILENAME>\s*([^\r\n<]+)", block, flags=re.IGNORECASE)
            selected_filename = fn.group(1).strip() if fn else ""
            break

    if selected is None:
        # Some old submissions are irregular. Fall back to the whole submission.
        selected = raw_submission

    text_match = re.search(r"<TEXT>(.*?)(?:</TEXT>|$)", selected, flags=re.IGNORECASE | re.DOTALL)
    body = text_match.group(1) if text_match else selected

    # Strip SGML/HTML/XML into readable text while preserving table-ish line breaks.
    soup = BeautifulSoup(body, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text("\n")
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return selected_filename, text.strip()


def download_single_10k(
    ticker: str,
    company_name: str,
    cik: str,
    filing: dict,
    *,
    force: bool = False,
) -> Optional[dict]:
    accession = filing.get("accessionNumber", "")
    if not accession:
        return None

    year = filing_year(filing)
    if year is None:
        return None

    primary_document = str(filing.get("primaryDocument") or "")
    urls = sec_url_candidates(cik, accession, primary_document)

    dest = (
        ROOT
        / "sec"
        / "10k"
        / safe_name(ticker)
        / str(year)
        / accession.replace("-", "")
    )
    # download_file() creates the directory, so a failed download leaves no empty folder.

    submission_path = dest / "submission.txt"
    index_path = dest / "filing_index.html"
    clean_path = dest / "10k_clean.txt"
    primary_path = dest / safe_name(primary_document) if primary_document else None
    metadata_path = dest / "metadata.json"

    complete_url = download_first_available(urls["complete"], submission_path, force=force)
    if complete_url is None:
        return None

    index_url = download_first_available(urls["index"], index_path, force=force)

    primary_url = None
    if primary_path and primary_document:
        primary_url = download_first_available(urls["primary"], primary_path, force=force)

    try:
        raw = decode_sec_text(submission_path)
        extracted_filename, clean_text = extract_10k_document(raw)
        if not clean_path.exists() or force:
            clean_path.write_text(clean_text, encoding="utf-8")
    except Exception as exc:
        logger.warning("Could not create clean 10-K for %s %s: %s", ticker, accession, exc)
        extracted_filename = ""

    metadata = {
        "ticker": ticker,
        "company_name": company_name,
        "cik": f"{int(cik):010d}",
        "form": filing.get("form"),
        "filing_date": filing.get("filingDate"),
        "report_date": filing.get("reportDate"),
        "accession_number": accession,
        "primary_document": primary_document,
        "extracted_10k_document": extracted_filename,
        "complete_submission_url": complete_url if complete_url != "existing" else urls["complete"][0],
        "index_url": index_url if index_url and index_url != "existing" else urls["index"][0],
        "primary_url": primary_url if primary_url and primary_url != "existing" else (urls["primary"][0] if urls["primary"] else None),
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json(metadata_path, metadata)
    return metadata


def load_existing_manifest(path: Path) -> Dict[str, dict]:
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        return {}
    out = {}
    for _, row in df.iterrows():
        key = f"{row.get('ticker','')}|{row.get('accession_number','')}"
        out[key] = row.to_dict()
    return out


def save_sec_manifest(rows: List[dict]) -> None:
    path = ROOT / "manifests" / "sec_10k_manifest.csv"
    merged = load_existing_manifest(path)
    for row in rows:
        key = f"{row.get('ticker','')}|{row.get('accession_number','')}"
        merged[key] = row
    if not merged:
        return
    df = pd.DataFrame(list(merged.values()))
    cols = [
        "ticker", "company_name", "cik", "report_year", "filing_date",
        "report_date", "form", "accession_number", "primary_document",
        "complete_submission_url", "index_url", "primary_url",
    ]
    cols = [c for c in cols if c in df.columns] + [c for c in df.columns if c not in cols]
    df = df[cols].sort_values(["ticker", "report_year", "filing_date"], kind="stable")
    df.to_csv(path, index=False)


def download_companyfacts(cik: str, ticker: str, force: bool = False) -> Optional[Path]:
    validate_sec()
    cik_padded = f"{int(cik):010d}"
    url = f"{SEC_DATA_BASE}/api/xbrl/companyfacts/CIK{cik_padded}.json"
    path = ROOT / "sec" / "companyfacts" / f"{safe_name(ticker)}_{cik_padded}.json"
    if path.exists() and not force:
        return path
    try:
        response = SEC_SESSION.get(url, headers=SEC_HEADERS, timeout=90)
        response.raise_for_status()
        write_json(path, response.json())
        time.sleep(SEC_SLEEP)
        return path
    except Exception as exc:
        logger.warning("CompanyFacts failed for %s / %s: %s", ticker, cik_padded, exc)
        return None


def download_sec(
    tickers: List[str],
    start_year: int,
    end_year: int,
    *,
    include_companyfacts: bool = True,
    force: bool = False,
) -> None:
    validate_sec()
    save_sec_company_reference()

    all_manifest_rows: List[dict] = []
    seen_accessions = set()

    for ticker in tqdm(tickers, desc="SEC companies"):
        ticker = ticker.upper()
        if ticker not in COMPANIES:
            logger.warning("Ticker not configured: %s", ticker)
            continue

        for entity in COMPANIES[ticker]:
            cik = entity["cik"]
            company_name = entity["name"]
            logger.info("Processing %s - %s - CIK %s", ticker, company_name, cik)

            try:
                filings = get_all_submissions(cik)
            except Exception as exc:
                logger.error("Submissions failed for %s/%s: %s", ticker, cik, exc)
                continue

            tenks = []
            for filing in filings:
                if filing.get("form") not in TEN_K_FORMS:
                    continue
                year = filing_year(filing)
                if year is None or not (start_year <= year <= end_year):
                    continue
                tenks.append(filing)

            tenks.sort(key=lambda f: (f.get("reportDate", ""), f.get("filingDate", "")))

            for filing in tqdm(tenks, desc=f"{ticker} 10-K", leave=False):
                accession = filing.get("accessionNumber", "")
                if accession in seen_accessions:
                    continue
                seen_accessions.add(accession)

                metadata = download_single_10k(
                    ticker,
                    company_name,
                    cik,
                    filing,
                    force=force,
                )
                if metadata:
                    all_manifest_rows.append(metadata | {"report_year": filing_year(filing)})

            if include_companyfacts:
                download_companyfacts(cik, ticker, force=force)

    save_sec_manifest(all_manifest_rows)

# ============================================================
# FRED
# ============================================================


def fred_get(endpoint: str, params: dict) -> dict:
    validate_fred()
    full_params = dict(params)
    full_params.update({"api_key": FRED_API_KEY, "file_type": "json"})
    url = f"{FRED_BASE}/{endpoint}"
    response = FRED_SESSION.get(url, params=full_params, timeout=90)
    response.raise_for_status()
    time.sleep(GENERAL_SLEEP)
    return response.json()


def download_fred_series(
    series_id: str,
    category: str,
    description: str,
    start_year: int,
    end_year: int,
    *,
    force: bool = False,
) -> Optional[Path]:
    csv_path = ROOT / "macro" / "fred" / f"{series_id}.csv"
    meta_path = ROOT / "macro" / "fred" / f"{series_id}.metadata.json"

    if csv_path.exists() and not force:
        return csv_path

    try:
        meta = fred_get("series", {"series_id": series_id})
        write_json(meta_path, meta)

        obs = fred_get(
            "series/observations",
            {
                "series_id": series_id,
                "observation_start": f"{start_year:04d}-01-01",
                "observation_end": f"{end_year:04d}-12-31",
                "sort_order": "asc",
                "output_type": 1,
                "limit": 100000,
            },
        )

        rows = []
        for item in obs.get("observations", []):
            value = item.get("value")
            try:
                value = float(value) if value not in (None, "", ".") else None
            except ValueError:
                value = None
            rows.append({
                "date": item.get("date"),
                "value": value,
                "series_id": series_id,
                "category": category,
                "description": description,
            })

        df = pd.DataFrame(rows)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df.to_csv(csv_path, index=False)
        return csv_path
    except Exception as exc:
        logger.error("FRED failed for %s: %s", series_id, exc)
        return None


def download_fred(start_year: int, end_year: int, force: bool = False) -> None:
    validate_fred()
    manifest = []
    for series_id, (category, description) in tqdm(FRED_SERIES.items(), desc="FRED series"):
        path = download_fred_series(
            series_id,
            category,
            description,
            start_year,
            end_year,
            force=force,
        )
        manifest.append({
            "source": "FRED",
            "series_id": series_id,
            "category": category,
            "description": description,
            "start_year": start_year,
            "end_year": end_year,
            "file": str(path) if path else "",
        })

    pd.DataFrame(manifest).to_csv(ROOT / "manifests" / "fred_manifest.csv", index=False)

# ============================================================
# BLS
# ============================================================


def download_bls(start_year: int, end_year: int, force: bool = False) -> None:
    all_rows = {sid: [] for sid in BLS_SERIES}
    # BLS API v2 limit: 20 years per request with a registration key, 10 without.
    chunk_size = 20 if BLS_API_KEY else 10
    if not BLS_API_KEY:
        logger.warning("BLS_API_KEY not set: using 10-year requests (25 requests/day limit).")

    for chunk_start in range(start_year, end_year + 1, chunk_size):
        chunk_end = min(chunk_start + chunk_size - 1, end_year)
        logger.info("BLS request: %s-%s", chunk_start, chunk_end)

        payload = {
            "seriesid": list(BLS_SERIES.keys()),
            "startyear": str(chunk_start),
            "endyear": str(chunk_end),
        }
        if BLS_API_KEY:
            payload["registrationkey"] = BLS_API_KEY

        try:
            response = BLS_SESSION.post(
                BLS_URL,
                json=payload,
                headers={"Content-type": "application/json"},
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            time.sleep(GENERAL_SLEEP)

            if data.get("status") != "REQUEST_SUCCEEDED":
                logger.warning("BLS API status: %s", data.get("message", data.get("status")))
                continue

            for series in data.get("Results", {}).get("series", []):
                sid = series.get("seriesID")
                for item in series.get("data", []):
                    period = item.get("period", "")
                    year = int(item.get("year"))
                    if period.startswith("M") and period[1:].isdigit():
                        month = int(period[1:])
                        date = pd.Timestamp(year=year, month=month, day=1)
                    else:
                        date = pd.Timestamp(year=year, month=1, day=1)
                    try:
                        value = float(item.get("value"))
                    except (TypeError, ValueError):
                        value = None
                    all_rows[sid].append({
                        "date": date,
                        "value": value,
                        "series_id": sid,
                        "description": BLS_SERIES.get(sid, ""),
                        "period": period,
                        "period_name": item.get("periodName", ""),
                    })
        except Exception as exc:
            logger.error("BLS request failed: %s", exc)

    manifest = []
    for sid, rows in all_rows.items():
        path = ROOT / "macro" / "bls" / f"{sid}.csv"
        if path.exists() and not force:
            manifest.append({"source": "BLS", "series_id": sid, "file": str(path)})
            continue
        df = pd.DataFrame(rows)
        if not df.empty:
            df.sort_values("date").to_csv(path, index=False)
        manifest.append({"source": "BLS", "series_id": sid, "file": str(path) if path.exists() else ""})

    pd.DataFrame(manifest).to_csv(ROOT / "manifests" / "bls_manifest.csv", index=False)

# ============================================================
# DERIVED MACRO PANEL
# ============================================================


def load_fred_series(series_id: str) -> Optional[pd.Series]:
    path = ROOT / "macro" / "fred" / f"{series_id}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")
    if df.empty:
        return None
    return df.set_index("date")["value"]


def build_macro_panel() -> None:
    mapping = {
        "cpi": "CPIAUCSL",
        "core_cpi": "CPILFESL",
        "pce_price": "PCEPI",
        "core_pce_price": "PCEPILFE",
        "unemployment": "UNRATE",
        "fed_funds": "FEDFUNDS",
        "treasury_10y": "DGS10",
        "treasury_2y": "DGS2",
        "real_gdp": "GDPC1",
        "sp500": "SP500",
        "vix": "VIXCLS",
        "oil_wti": "DCOILWTICO",
        "usd_index": "DTWEXBGS",
        "m2": "M2SL",
        "fed_assets": "WALCL",
        "nfci": "NFCI",
    }

    panel = pd.DataFrame()
    for name, sid in mapping.items():
        s = load_fred_series(sid)
        if s is None:
            continue
        # Normalize all frequencies to month-end using last available observation.
        panel[name] = s.resample("ME").last()

    if panel.empty:
        logger.warning("No FRED data available for derived panel.")
        return

    if "cpi" in panel:
        panel["cpi_yoy"] = panel["cpi"].pct_change(12, fill_method=None) * 100
    if "core_cpi" in panel:
        panel["core_cpi_yoy"] = panel["core_cpi"].pct_change(12, fill_method=None) * 100
    if "pce_price" in panel:
        panel["pce_yoy"] = panel["pce_price"].pct_change(12, fill_method=None) * 100
    if "core_pce_price" in panel:
        panel["core_pce_yoy"] = panel["core_pce_price"].pct_change(12, fill_method=None) * 100
    if "treasury_10y" in panel and "treasury_2y" in panel:
        panel["10y_minus_2y"] = panel["treasury_10y"] - panel["treasury_2y"]
    if "treasury_10y" in panel and "cpi_yoy" in panel:
        panel["approx_real_10y"] = panel["treasury_10y"] - panel["cpi_yoy"]
    if "real_gdp" in panel:
        panel["real_gdp_yoy"] = panel["real_gdp"].pct_change(12, fill_method=None) * 100

    out = panel.reset_index().rename(columns={"index": "date"})
    out.to_csv(ROOT / "macro" / "derived" / "macro_monthly_dashboard.csv", index=False)


def build_fred_long() -> None:
    files = sorted((ROOT / "macro" / "fred").glob("*.csv"))
    frames = []
    for path in files:
        try:
            df = pd.read_csv(path)
            if {"date", "series_id", "value"}.issubset(df.columns):
                frames.append(df[["date", "series_id", "value", "category", "description"]])
        except Exception as exc:
            logger.warning("Could not read FRED file %s: %s", path, exc)
    if frames:
        master = pd.concat(frames, ignore_index=True)
        master["date"] = pd.to_datetime(master["date"], errors="coerce")
        master["value"] = pd.to_numeric(master["value"], errors="coerce")
        master.sort_values(["series_id", "date"]).to_csv(
            ROOT / "macro" / "derived" / "fred_master_long.csv",
            index=False,
        )

# ============================================================
# LEGACY ANNUAL REPORTS
# ============================================================


def create_legacy_template() -> Path:
    path = ROOT / "manifests" / "legacy_sources.csv"
    if not path.exists():
        pd.DataFrame(columns=["ticker", "year", "url", "filename"]).to_csv(path, index=False)
    return path


def download_legacy(start_year: int, end_year: int, force: bool = False) -> None:
    """
    Download pre-1994 annual reports from URLs explicitly listed by the user.
    This is deliberately source-neutral rather than pretending SEC contains
    electronic 1920s filings.
    """
    path = create_legacy_template()
    df = pd.read_csv(path, dtype=str).fillna("")
    if df.empty:
        logger.info("No legacy_sources.csv entries yet. Template created at %s", path)
        return

    rows = []
    for _, row in df.iterrows():
        ticker = row["ticker"].upper().strip()
        try:
            year = int(row["year"])
        except ValueError:
            continue
        if not (start_year <= year <= end_year):
            continue
        url = row["url"].strip()
        if not url:
            continue
        filename = row["filename"].strip() or f"{year}.pdf"
        destination = ROOT / "legacy_annual_reports" / safe_name(ticker) / filename

        status = "downloaded"
        try:
            download_file(
                url,
                destination,
                session=GENERIC_SESSION,
                headers={"User-Agent": "FinancialArchiveResearch/1.0"},
                sleep_seconds=GENERAL_SLEEP,
                force=force,
            )
        except Exception as exc:
            status = f"ERROR: {exc}"
            logger.warning("Legacy report failed %s %s: %s", ticker, year, exc)

        rows.append({
            "ticker": ticker,
            "year": year,
            "url": url,
            "destination": str(destination),
            "status": status,
        })

    pd.DataFrame(rows).to_csv(ROOT / "manifests" / "legacy_download_manifest.csv", index=False)

# ============================================================
# DIAGNOSTICS / CLI
# ============================================================


def diagnostics() -> None:
    print("\nFINANCIAL ARCHIVE DIAGNOSTICS")
    print("=" * 60)
    print(f"ROOT: {ROOT}")
    print(f"SEC_USER_AGENT: {'OK' if SEC_USER_AGENT else 'MISSING'}")
    print(f"FRED_API_KEY:   {'OK' if FRED_API_KEY else 'MISSING'}")
    print(f"Python:         {sys.version.split()[0]}")
    print(f"Requests:       {requests.__version__}")
    print(f"Pandas:         {pd.__version__}")
    print("=" * 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Historical financial archive builder")
    parser.add_argument("--mode", choices=["sec", "macro", "legacy", "all", "check"], default="check")
    parser.add_argument("--start-year", type=int, default=1920)
    parser.add_argument("--end-year", type=int, default=datetime.now().year)
    parser.add_argument("--tickers", nargs="+", default=list(COMPANIES.keys()))
    parser.add_argument("--no-companyfacts", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.mode == "check":
        diagnostics()
        return

    logger.info("=" * 70)
    logger.info("FINANCIAL ARCHIVE BUILDER v2")
    logger.info("Mode: %s", args.mode)
    logger.info("Years: %s -> %s", args.start_year, args.end_year)
    logger.info("Tickers: %s", ", ".join(args.tickers))
    logger.info("Data root: %s", ROOT)
    logger.info("=" * 70)

    if args.mode in ("sec", "all"):
        download_sec(
            [t.upper() for t in args.tickers],
            args.start_year,
            args.end_year,
            include_companyfacts=not args.no_companyfacts,
            force=args.force,
        )

    if args.mode in ("macro", "all"):
        download_fred(args.start_year, args.end_year, force=args.force)
        download_bls(args.start_year, args.end_year, force=args.force)
        build_fred_long()
        build_macro_panel()

    if args.mode in ("legacy", "all"):
        download_legacy(args.start_year, args.end_year, force=args.force)

    logger.info("=" * 70)
    logger.info("DONE")
    logger.info("Data location: %s", ROOT)
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
