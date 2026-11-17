"""Form 4 detallados de las acciones de «Mis activos» (ficha v2 del panel: dónde compraron/vendieron los directivos).

    .venv/bin/python -m src.ingest.sec_form4_detalle [--meses 24]

A diferencia de src/ingest/sec_insiders.py (solo P/S, sin nombres, para el agregado de todo el mercado), aquí se guardan
TODAS las operaciones no derivadas (tabla I del Form 4) de las ~10 acciones de EE. UU. de «Mis activos», con nombre y
cargo del declarante, para poder etiquetar compras en mercado abierto (P), ventas (S), ventas con plan 10b5-1,
ejercicios de opciones (M/X/C), concesiones (A), retenciones fiscales (F), regalos (G) y otras.

Dos capas (las mismas fuentes públicas de la SEC):
1. Ficheros trimestrales «Insider Transactions Data Sets» ya descargados por sec_insiders en raw/sec_form345/ (aquí NO
   se descargan: solo se leen los de los últimos `--meses`). Traen nombre (RPTOWNERNAME), cargo (RPTOWNER_TITLE),
   casilla 10b5-1 (AFF10B5ONE) y notas al pie.
2. Form 4 presentados después del último trimestre publicado: XML de EDGAR (lista data.sec.gov/submissions del emisor
   + un XML por presentación; el XML crudo se guarda en sec_form4/xml/ y no se vuelve a pedir).

Plan 10b5-1: casilla AFF10B5ONE del Form 4 (desde abr-2023) o una nota al pie DE ESA LÍNEA que mencione «10b5-1».
SEC: User-Agent genérico de cliente (sin datos personales), ≤ 5 peticiones/s (límite de la SEC: 10/s; el limitador es
el de src/ingest/sec_common, común a todo el proceso) y plazo total por descarga (_http).
Fuera de git: $FIN_DATA_ROOT/sec_form4/operaciones.parquet + meta.json (datos de terceros; el repo es público).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from src.ingest import _http
from src.ingest.sec_common import _LIMITER, get_logger

UA = "financial-kb-panel/1.0 research-client contact@example.org"   # genérico: sin datos del usuario
COLS = ["accession", "filing_date", "trans_date", "issuer_cik", "ticker", "owner_cik", "owner_name", "title",
        "director", "officer", "ten_pct", "code", "acq_disp", "shares", "price", "plan_10b5_1", "fuente"]
RE_PLAN = re.compile(r"10b5-?1", re.I)
log = get_logger("sec_form4_detalle")
_S: requests.Session | None = None


def root() -> Path:
    return Path(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")).expanduser()


def salida() -> Path:
    d = root() / "sec_form4"
    (d / "xml").mkdir(parents=True, exist_ok=True)
    return d


def sec_get(url: str, total: float = 60) -> requests.Response:
    global _S
    if _S is None:
        _S = requests.Session()
        _S.headers.update({"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    _LIMITER.wait()
    r = _http.get(url, session=_S, timeout=30, total=total)
    r.raise_for_status()
    return r


def acciones() -> dict[str, str]:
    """{ticker: cik} de las acciones de EE. UU. de «Mis activos» (los ETF, futuros y Bayer no presentan Form 4)."""
    from src.ingest.sec_insiders import tickers_mis_activos
    tk = tickers_mis_activos()
    meta = root() / "curated" / "sec_insiders" / "meta.json"
    ciks = {}
    try:
        ciks = json.loads(meta.read_text()).get("recientes_ciks") or {}
    except Exception:  # noqa: BLE001
        pass
    if not all(t in ciks for t in tk):
        try:
            d = sec_get("https://www.sec.gov/files/company_tickers.json").json()
            m = {v["ticker"].upper(): str(v["cik_str"]) for v in d.values()}
            ciks = {**{t: m[t] for t in tk if t in m}, **ciks}
        except Exception as e:  # noqa: BLE001
            log.warning("company_tickers: %s", e)
    return {t: str(ciks[t]).lstrip("0") for t in tk if t in ciks}


# ------------------------------------------------------------------------------------- capa 1: ficheros trimestrales
def _fn_ids(row: pd.Series, cols: list[str]) -> set[str]:
    out = set()
    for c in cols:
        v = row.get(c)
        if isinstance(v, str) and v:
            out.update(x.strip() for x in v.split(",") if x.strip())
    return out


def parse_zip(path: Path, ciks: dict[str, str]) -> pd.DataFrame:
    por_cik = {c: t for t, c in ciks.items()}
    with zipfile.ZipFile(path) as zf:
        def tsv(n):
            return pd.read_csv(io.BytesIO(zf.read(f"{n}.tsv")), sep="\t", dtype=str, quoting=3, on_bad_lines="skip",
                               encoding="utf-8", encoding_errors="replace")
        sub = tsv("SUBMISSION")
        sub["cik"] = sub["ISSUERCIK"].fillna("").str.lstrip("0")
        sub = sub[sub["DOCUMENT_TYPE"].isin(["4", "4/A"]) & sub["cik"].isin(por_cik)]
        acc = set(sub["ACCESSION_NUMBER"])
        tr = tsv("NONDERIV_TRANS")
        tr = tr[tr["ACCESSION_NUMBER"].isin(acc)]
        own = tsv("REPORTINGOWNER")
        own = own[own["ACCESSION_NUMBER"].isin(acc)]
        fn = tsv("FOOTNOTES")
        fn = fn[fn["ACCESSION_NUMBER"].isin(acc)]
    if tr.empty:
        return pd.DataFrame(columns=COLS)
    notas = {(a, i): str(x) for a, i, x in zip(fn["ACCESSION_NUMBER"], fn["FOOTNOTE_ID"], fn["FOOTNOTE_TXT"])}
    o1 = own.groupby("ACCESSION_NUMBER").agg(owner_cik=("RPTOWNERCIK", "first"), owner_name=("RPTOWNERNAME", "first"),
                                             title=("RPTOWNER_TITLE", lambda s: next((x for x in s if isinstance(x, str)), None)),
                                             rel=("RPTOWNER_RELATIONSHIP", lambda s: ",".join(x for x in s if isinstance(x, str))))
    d = tr.merge(sub[["ACCESSION_NUMBER", "FILING_DATE", "cik", "AFF10B5ONE"]], on="ACCESSION_NUMBER").merge(
        o1, left_on="ACCESSION_NUMBER", right_index=True, how="left")
    fn_cols = [c for c in d.columns if c.endswith("_FN")]
    plan_nota = [any(RE_PLAN.search(notas.get((r["ACCESSION_NUMBER"], i), "")) for i in _fn_ids(r, fn_cols))
                 for _, r in d.iterrows()]
    rel = d["rel"].fillna("")
    out = pd.DataFrame({
        "accession": d["ACCESSION_NUMBER"], "filing_date": pd.to_datetime(d["FILING_DATE"], format="%d-%b-%Y", errors="coerce"),
        "trans_date": pd.to_datetime(d["TRANS_DATE"], format="%d-%b-%Y", errors="coerce"),
        "issuer_cik": d["cik"], "ticker": d["cik"].map(por_cik), "owner_cik": d["owner_cik"].fillna("").str.lstrip("0"),
        "owner_name": d["owner_name"], "title": d["title"],
        "director": rel.str.contains("Director"), "officer": rel.str.contains("Officer"),
        "ten_pct": rel.str.contains("TenPercentOwner"), "code": d["TRANS_CODE"], "acq_disp": d["TRANS_ACQUIRED_DISP_CD"],
        "shares": pd.to_numeric(d["TRANS_SHARES"], errors="coerce"),
        "price": pd.to_numeric(d["TRANS_PRICEPERSHARE"], errors="coerce"),
        "plan_10b5_1": d["AFF10B5ONE"].isin(["1", "true", "True"]).values | pd.Series(plan_nota, index=d.index).values,
        "fuente": path.stem})
    return out[COLS]


# ------------------------------------------------------------------------------------- capa 2: XML de EDGAR
def _txt(el, path: str) -> str | None:
    x = el.find(path)
    return x.text.strip() if x is not None and x.text else None


def parse_xml(xml: str, accession: str, filing_date: str, ticker: str) -> list[dict]:
    """Todas las líneas de la tabla I (no derivadas) de un Form 4, con nombre, cargo y plan 10b5-1 por línea."""
    r = ET.fromstring(xml)
    if (_txt(r, "documentType") or "") not in ("4", "4/A"):
        return []
    rels = r.findall("reportingOwner/reportingOwnerRelationship")

    def flag(tag):
        return any((_txt(x, tag) or "").lower() in ("1", "true") for x in rels)
    titulo = next((_txt(x, "officerTitle") for x in rels if _txt(x, "officerTitle")), None)
    notas = {f.get("id"): "".join(f.itertext()) for f in r.findall("footnotes/footnote")}
    casilla = (_txt(r, "aff10b5One") or "").lower() in ("1", "true")
    out = []
    for t in r.findall("nonDerivativeTable/nonDerivativeTransaction"):
        ids = {f.get("id") for f in t.iter("footnoteId")}
        sh = pd.to_numeric(_txt(t, "transactionAmounts/transactionShares/value"), errors="coerce")
        pr = pd.to_numeric(_txt(t, "transactionAmounts/transactionPricePerShare/value"), errors="coerce")
        out.append({"accession": accession, "filing_date": filing_date, "trans_date": _txt(t, "transactionDate/value"),
                    "issuer_cik": (_txt(r, "issuer/issuerCik") or "").lstrip("0"), "ticker": ticker,
                    "owner_cik": (_txt(r, "reportingOwner/reportingOwnerId/rptOwnerCik") or "").lstrip("0"),
                    "owner_name": _txt(r, "reportingOwner/reportingOwnerId/rptOwnerName"), "title": titulo,
                    "director": flag("isDirector"), "officer": flag("isOfficer"), "ten_pct": flag("isTenPercentOwner"),
                    "code": _txt(t, "transactionCoding/transactionCode"),
                    "acq_disp": _txt(t, "transactionAmounts/transactionAcquiredDisposedCode/value"),
                    "shares": sh, "price": pr,
                    "plan_10b5_1": casilla or any(RE_PLAN.search(notas.get(i, "") or "") for i in ids),
                    "fuente": "form4_xml"})
    return out


def capa_xml(ciks: dict[str, str], despues_de: pd.Timestamp, max_nuevos: int = 3000) -> pd.DataFrame:
    cache = salida() / "xml"
    filas, nuevos = [], 0
    for t, cik in ciks.items():
        try:
            sub = sec_get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json").json()["filings"]["recent"]
        except Exception as e:  # noqa: BLE001
            log.warning("%s: submissions %s", t, e)
            continue
        for i, f in enumerate(sub["form"]):
            if f not in ("4", "4/A") or pd.Timestamp(sub["filingDate"][i]) <= despues_de:
                continue
            acc = sub["accessionNumber"][i]
            cp = cache / f"{acc}.xml"
            if cp.exists():
                xml = cp.read_text()
            else:
                if nuevos >= max_nuevos:
                    continue
                doc = re.sub(r"^xslF345X\d+/", "", sub["primaryDocument"][i])
                try:
                    xml = sec_get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}").text
                except Exception as e:  # noqa: BLE001
                    log.warning("%s %s: %s", t, acc, e)
                    continue
                cp.write_text(xml)
                nuevos += 1
            try:
                filas.extend(parse_xml(xml, acc, sub["filingDate"][i], t))
            except Exception as e:  # noqa: BLE001
                log.warning("%s %s ilegible: %s", t, acc, e)
    d = pd.DataFrame(filas, columns=COLS)
    log.info("XML: %d líneas, %d descargas nuevas", len(d), nuevos)
    return d


def normalizar(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    for c in ("filing_date", "trans_date"):
        d[c] = pd.to_datetime(d[c], errors="coerce")
    for c in ("shares", "price"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    for c in ("director", "officer", "ten_pct", "plan_10b5_1"):
        d[c] = d[c].fillna(False).astype(bool)
    return d


def run(meses: int = 24) -> dict:
    ciks = acciones()
    desde = pd.Timestamp.now().normalize() - pd.DateOffset(months=meses)
    zips = sorted((root() / "raw" / "sec_form345").glob("*_form345.zip"))
    zips = [z for z in zips if pd.Period(z.stem[:6].replace("q", "Q"), "Q").end_time >= desde]
    frames = []
    for z in zips:
        try:
            frames.append(parse_zip(z, ciks))
        except Exception as e:  # noqa: BLE001
            log.warning("%s: %s", z.name, e)
    base = normalizar(pd.concat(frames, ignore_index=True)) if frames else pd.DataFrame(columns=COLS)
    hasta_zip = base["filing_date"].max() if len(base) else desde
    hasta_zip = pd.Timestamp(hasta_zip) if pd.notna(hasta_zip) else desde
    rec = normalizar(capa_xml(ciks, hasta_zip))
    rec = rec[~rec["accession"].isin(set(base["accession"]))]
    d = pd.concat([x for x in (base, rec) if len(x)], ignore_index=True) if len(base) or len(rec) else base
    d = d[d["filing_date"] >= desde].drop_duplicates().sort_values(["ticker", "trans_date"])
    out = salida()
    d.to_parquet(out / "operaciones.parquet", index=False)
    meta = {"actualizado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "desde": str(desde.date()),
            "trimestrales_hasta": str(hasta_zip.date()), "lineas": int(len(d)), "lineas_xml": int(len(rec)),
            "ciks": ciks, "zips": [z.name for z in zips],
            "fuente": "SEC Insider Transactions Data Sets + Form 4 XML (EDGAR)"}
    (out / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    log.info("form4 detalle: %s", {k: meta[k] for k in ("lineas", "lineas_xml", "trimestrales_hasta")})
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--meses", type=int, default=24)
    run(ap.parse_args().meses)
