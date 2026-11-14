"""SEC insider transactions (Forms 3/4/5) -> curated/sec_insiders/ (light, incremental).

    .venv/bin/python -m src.ingest.sec_insiders [--desde 2016] [--sin-recientes]

Two layers, both open-market only (Form 4 non-derivative transaction codes P = purchase, S = sale):

1. Aggregate (whole market): the SEC "Insider Transactions Data Sets" (one zip per calendar quarter of FILING
   date, ~8-17 MB each, 2006q1+). Only quarters >= --desde are downloaded (default 2016 -> ~40 zips, ~0.4 GB);
   closed quarters are downloaded once and kept intact in raw/sec_form345/. The data set for a quarter appears a
   few days after the quarter ends, so the aggregate is complete only up to the end of the last published quarter.
2. Recent (only the tickers in «Mis activos»): Form 4 XMLs filed after the end of layer 1, from the issuer's
   data.sec.gov submissions list (one request per issuer + one per new filing; parsed XML cached per accession in
   raw/sec_form4_xml/, so reruns only fetch new filings).

Rate limit and User-Agent: src/ingest/sec_common (<= 5 req/s, SEC_USER_AGENT from .env; never logged).
Point-in-time: use filing_date (a Form 4 is due 2 business days after the trade), not trans_date.

Out: curated/sec_insiders/trans_ps.parquet  (one row per P/S non-derivative line)
     curated/sec_insiders/recientes_ps.parquet (layer 2, same columns)
     curated/sec_insiders/meta.json
"""
from __future__ import annotations

import argparse
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd

from src.ingest.sec_common import (curated_dir, get_logger, now_utc, raw_dir, sec_download, sec_get,
                                   write_json)

LISTA = "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets"
CODES = ("P", "S")
COLS = ["accession", "filing_date", "trans_date", "issuer_cik", "ticker", "issuer", "owner_cik", "code", "shares", "price",
        "value", "director", "officer", "ten_pct", "plan_10b5_1", "fuente"]
log = get_logger("sec_insiders")


# ------------------------------------------------------------------------------------- capa 1: data sets
def listar_zips() -> dict[str, str]:
    """{'2026q3': url absoluta} desde la página de la SEC (1 petición)."""
    t = sec_get(LISTA, timeout=60).text
    out = {}
    for href in re.findall(r'href="([^"]*insider-transactions-data-sets/(\d{4}q[1-4])_form345\.zip)"', t):
        out[href[1]] = "https://www.sec.gov" + href[0] if href[0].startswith("/") else href[0]
    return dict(sorted(out.items()))


def _fecha(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, format="%d-%b-%Y", errors="coerce")


def parse_zip(path: Path) -> pd.DataFrame:
    """Líneas P/S no derivadas de un zip trimestral, con la relación del declarante (directivo/consejero/10 %)."""
    with zipfile.ZipFile(path) as zf:
        def tsv(n, cols):
            return pd.read_csv(io.BytesIO(zf.read(f"{n}.tsv")), sep="\t", dtype=str, usecols=cols,
                               quoting=3, on_bad_lines="skip", encoding="utf-8", encoding_errors="replace")
        sub = tsv("SUBMISSION", lambda c: c in {"ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK",
                                                 "ISSUERNAME", "ISSUERTRADINGSYMBOL", "AFF10B5ONE"})
        tr = tsv("NONDERIV_TRANS", ["ACCESSION_NUMBER", "TRANS_DATE", "TRANS_CODE", "TRANS_SHARES",
                                    "TRANS_PRICEPERSHARE"])
        own = tsv("REPORTINGOWNER", ["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP"])
    sub = sub[sub["DOCUMENT_TYPE"].isin(["4", "4/A"])]
    tr = tr[tr["TRANS_CODE"].isin(CODES)]
    rel = own.assign(r=own["RPTOWNER_RELATIONSHIP"].fillna("")).groupby("ACCESSION_NUMBER")["r"].agg(",".join)
    first = own.groupby("ACCESSION_NUMBER")["RPTOWNERCIK"].first()
    d = tr.merge(sub, on="ACCESSION_NUMBER", how="inner")
    r = d["ACCESSION_NUMBER"].map(rel).fillna("")
    shares = pd.to_numeric(d["TRANS_SHARES"], errors="coerce")
    price = pd.to_numeric(d["TRANS_PRICEPERSHARE"], errors="coerce")
    out = pd.DataFrame({
        "accession": d["ACCESSION_NUMBER"], "filing_date": _fecha(d["FILING_DATE"]),
        "trans_date": _fecha(d["TRANS_DATE"]), "issuer_cik": d["ISSUERCIK"].str.lstrip("0"),
        "ticker": d["ISSUERTRADINGSYMBOL"].fillna("").str.upper().str.strip(), "issuer": d["ISSUERNAME"],
        "owner_cik": d["ACCESSION_NUMBER"].map(first).fillna("").str.lstrip("0"), "code": d["TRANS_CODE"], "shares": shares, "price": price, "value": shares * price,
        "director": r.str.contains("Director"), "officer": r.str.contains("Officer"),
        "ten_pct": r.str.contains("TenPercentOwner"),
        "plan_10b5_1": d["AFF10B5ONE"].isin(["1", "true", "True"]) if "AFF10B5ONE" in d else False,
        "fuente": path.stem,
    })
    return out[COLS]


def capa_datasets(desde: int) -> pd.DataFrame:
    rd = raw_dir("sec_form345")
    zips = {q: u for q, u in listar_zips().items() if int(q[:4]) >= desde}
    ultimo = max(zips) if zips else None
    frames = []
    for q, u in zips.items():
        dest = rd / f"{q}_form345.zip"
        # trimestres cerrados: una sola descarga; el último publicado se refresca si tiene > 7 días
        viejo = dest.exists() and q == ultimo and (pd.Timestamp.now().timestamp() - dest.stat().st_mtime) > 7 * 86400
        if not dest.exists() or viejo:
            log.info("descargando %s", dest.name)
            sec_download(u, dest, log=log)
        try:
            frames.append(parse_zip(dest))
        except Exception as e:  # noqa: BLE001
            log.warning("%s ilegible: %s", dest.name, e)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLS)


# ------------------------------------------------------------------------------------- capa 2: recientes
def _txt(el, path: str) -> str | None:
    x = el.find(path)
    return x.text.strip() if x is not None and x.text else None


def parse_form4_xml(xml: str, accession: str, filing_date: str) -> list[dict]:
    root = ET.fromstring(xml)
    if (_txt(root, "documentType") or "") not in ("4", "4/A"):
        return []
    rels = root.findall("reportingOwner/reportingOwnerRelationship")

    def flag(tag):
        return any((_txt(r, tag) or "").lower() in ("1", "true") for r in rels)
    plan = (_txt(root, "aff10b5One") or "").lower() in ("1", "true")
    out = []
    for t in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = _txt(t, "transactionCoding/transactionCode")
        if code not in CODES:
            continue
        sh = pd.to_numeric(_txt(t, "transactionAmounts/transactionShares/value"), errors="coerce")
        pr = pd.to_numeric(_txt(t, "transactionAmounts/transactionPricePerShare/value"), errors="coerce")
        out.append({"accession": accession, "filing_date": filing_date,
                    "trans_date": _txt(t, "transactionDate/value"),
                    "issuer_cik": (_txt(root, "issuer/issuerCik") or "").lstrip("0"),
                    "ticker": (_txt(root, "issuer/issuerTradingSymbol") or "").upper(),
                    "issuer": _txt(root, "issuer/issuerName"),
                    "owner_cik": (_txt(root, "reportingOwner/reportingOwnerId/rptOwnerCik") or "").lstrip("0"),
                    "code": code, "shares": sh, "price": pr,
                    "value": sh * pr if sh == sh and pr == pr else None,
                    "director": flag("isDirector"), "officer": flag("isOfficer"),
                    "ten_pct": flag("isTenPercentOwner"), "plan_10b5_1": plan, "fuente": "form4_xml"})
    return out


def cik_por_ticker() -> dict[str, str]:
    d = sec_get("https://www.sec.gov/files/company_tickers.json", timeout=60).json()
    return {v["ticker"].upper(): str(v["cik_str"]) for v in d.values()}


def capa_recientes(tickers: list[str], despues_de: pd.Timestamp, mapa: dict[str, str] | None = None) -> pd.DataFrame:
    cache = raw_dir("sec_form4_xml")
    mapa = mapa or cik_por_ticker()
    filas: list[dict] = []
    for t in tickers:
        cik = mapa.get(t.upper())
        if not cik:
            log.info("%s: sin CIK en la SEC (ETF/futuro/extranjera): se omite", t)
            continue
        sub = sec_get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", timeout=60).json()["filings"]["recent"]
        for i, f in enumerate(sub["form"]):
            if f not in ("4", "4/A") or pd.Timestamp(sub["filingDate"][i]) <= despues_de:
                continue
            acc = sub["accessionNumber"][i]
            cp = cache / f"{acc}.json"
            if cp.exists():
                filas.extend(json.loads(cp.read_text()))
                continue
            doc = re.sub(r"^xslF345X\d+/", "", sub["primaryDocument"][i])
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}"
            try:
                rows = parse_form4_xml(sec_get(url, timeout=60).text, acc, sub["filingDate"][i])
            except Exception as e:  # noqa: BLE001
                log.warning("%s %s: %s", t, acc, e)
                continue
            cp.write_text(json.dumps(rows, default=str))
            filas.extend(rows)
    d = pd.DataFrame(filas, columns=COLS)
    for c in ("filing_date", "trans_date"):
        d[c] = pd.to_datetime(d[c], errors="coerce")
    for c in ("shares", "price", "value"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    for c in ("director", "officer", "ten_pct", "plan_10b5_1"):
        d[c] = d[c].fillna(False).astype(bool)
    return d


def tickers_mis_activos() -> list[str]:
    """Acciones de EE. UU. de «Mis activos» (los ETF, futuros y valores extranjeros no presentan Form 4)."""
    from src.ingest.yahoo_precios import ACTIVOS
    return [t for t, (nom, grupo) in ACTIVOS.items() if re.fullmatch(r"[A-Z]{1,5}", t)
            and "ETF" not in nom and grupo not in ("ETF sectoriales", "Referencias")]


def run(desde: int = 2016, recientes: bool = True) -> dict:
    out = curated_dir("sec_insiders")
    d = capa_datasets(desde)
    d = d.drop_duplicates()
    d.to_parquet(out / "trans_ps.parquet", index=False)
    fin = d["filing_date"].max()
    meta = {"actualizado_utc": now_utc(), "desde_trimestre": f"{desde}q1", "lineas": len(d),
            "datasets_hasta_filing_date": str(fin.date()) if pd.notna(fin) else None,
            "fuente": LISTA}
    if recientes and pd.notna(fin):
        tk = tickers_mis_activos()
        mapa = cik_por_ticker()
        r = capa_recientes(tk, fin, mapa)
        r.to_parquet(out / "recientes_ps.parquet", index=False)
        meta["recientes_lineas"] = len(r)
        meta["recientes_ciks"] = {t: mapa[t] for t in tk if t in mapa}
    write_json(out / "meta.json", meta)
    log.info("insiders: %s", meta)
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", type=int, default=2016)
    ap.add_argument("--sin-recientes", action="store_true")
    a = ap.parse_args()
    run(a.desde, not a.sin_recientes)
