"""Build a local index of every EDGAR entity that ever filed a 10-K/10-K405 (no network:
reads raw/sec_bulk/submissions.zip downloaded by sec_bulk).

Run: .venv/bin/python -m src.ingest.sec_edgar_index
Out: raw/sec_universe/edgar_10k_filers.parquet   (cik, name, former_names, tickers, exchanges,
                                                  sic, sic_desc, state_inc, first_10k, last_10k, n_10k)
     raw/sec_universe/edgar_10k_filings.parquet  (cik, form, filed, report_date, accession,
                                                  primary_document, size)
"""
from __future__ import annotations

import json
import zipfile
from collections import defaultdict

import pandas as pd

from src.ingest.sec_common import get_logger, raw_dir

ANNUAL_FORMS = {"10-K", "10-K405", "10-KT", "10-K/A", "10-K405/A", "10-KSB", "10-KSB40"}
log = get_logger("sec_edgar_index")


def _rows(cik: str, block: dict, out: list) -> None:
    forms = block.get("form", [])
    for i, f in enumerate(forms):
        if f in ANNUAL_FORMS:
            out.append({
                "cik": cik, "form": f, "filed": block["filingDate"][i],
                "report_date": block.get("reportDate", [""] * len(forms))[i] or None,
                "accession": block["accessionNumber"][i],
                "primary_document": block.get("primaryDocument", [""] * len(forms))[i] or None,
                "size": block.get("size", [0] * len(forms))[i],
            })


def main() -> None:
    src = raw_dir("sec_bulk") / "submissions.zip"
    out_dir = raw_dir("sec_universe")
    z = zipfile.ZipFile(src)
    names = z.namelist()
    mains = [n for n in names if "-submissions-" not in n]
    extras = defaultdict(list)
    for n in names:
        if "-submissions-" in n:
            extras[n.split("-")[0].replace("CIK", "")].append(n)
    filers, filings = [], []
    bad = 0
    for k, n in enumerate(mains):
        if k % 100000 == 0:
            log.info("scanned %d/%d entities, %d filers", k, len(mains), len(filers))
        try:
            d = json.loads(z.read(n))
        except Exception:  # a few entries in the bulk zip are empty
            bad += 1
            continue
        cik = str(d.get("cik", n[3:13])).zfill(10)
        rows: list = []
        _rows(cik, d["filings"]["recent"], rows)
        for e in extras.get(cik, []):
            try:
                _rows(cik, json.loads(z.read(e)), rows)
            except Exception:
                bad += 1
        if not rows:
            continue
        filings.extend(rows)
        dates = sorted(r["filed"] for r in rows if r["form"] in ("10-K", "10-K405", "10-KT"))
        filers.append({
            "cik": cik, "name": d.get("name"),
            "former_names": json.dumps(d.get("formerNames") or []),
            "tickers": ",".join(d.get("tickers") or []),
            "exchanges": ",".join(x or "" for x in (d.get("exchanges") or [])),
            "sic": d.get("sic") or None, "sic_desc": d.get("sicDescription") or None,
            "state_inc": d.get("stateOfIncorporation") or None,
            "first_10k": dates[0] if dates else None, "last_10k": dates[-1] if dates else None,
            "n_10k": len(dates),
        })
    pd.DataFrame(filers).to_parquet(out_dir / "edgar_10k_filers.parquet", index=False)
    pd.DataFrame(filings).to_parquet(out_dir / "edgar_10k_filings.parquet", index=False)
    log.info("filers=%d annual filings=%d unreadable_json=%d", len(filers), len(filings), bad)


if __name__ == "__main__":
    main()
