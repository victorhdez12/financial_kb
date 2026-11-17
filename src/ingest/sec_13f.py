"""Carteras 13F (gestoras con > 100 M$) en las acciones de «Mis activos» (ficha v2 del panel; semanal).

    .venv/bin/python -m src.ingest.sec_13f [--trimestres 5] [--rehacer]

Fuente: SEC «Form 13F Data Sets» (un zip de ~100 MB por trimestre de PRESENTACIÓN: p. ej. 01jun2026-31aug2026 trae
sobre todo las carteras a 30-jun-2026, que se presentan hasta 45 días después del trimestre). Cada zip se descarga UNA
vez a un temporal, se filtra por los CUSIP de las acciones de abajo y se borra: solo se guarda lo filtrado
(sec_13f/posiciones.parquet, fuera de git) y la lista de zips ya leídos (meta.json).

Solo informes originales 13F-HR (sin enmiendas 13F-HR/A, que pueden ser parciales) y solo acciones (SH, sin PUT/CALL);
si un gestor presentó dos para el mismo trimestre se queda el último. SEC: User-Agent genérico, ≤ 5 peticiones/s, plazo
total por descarga.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.ingest import sec_form4_detalle as F4

LISTA = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"
# CUSIP de 9 dígitos (clase que cotiza en «Mis activos»). VYLR (escindida en oct-2026) aún no sale en ningún 13F.
CUSIP = {"GOOGL": "02079K305", "MSFT": "594918104", "META": "30303M102", "UBER": "90353T100", "CHTR": "16119P108",
         "UNH": "91324P102", "CTVA": "22052L104", "FMC": "302491303", "NEM": "651639106"}
log = F4.get_logger("sec_13f")


def salida() -> Path:
    d = F4.root() / "sec_13f"
    d.mkdir(parents=True, exist_ok=True)
    return d


def listar() -> list[str]:
    t = F4.sec_get(LISTA).text
    urls = re.findall(r'href="([^"]*form-13f-data-sets/[^"]*_form13f\.zip)"', t)
    urls = ["https://www.sec.gov" + u if u.startswith("/") else u for u in urls]

    def fin(u):  # 01jun2026-31aug2026 → fecha final
        m = re.search(r"-(\d{2}[a-z]{3}\d{4})_form13f", u)
        return pd.to_datetime(m.group(1), format="%d%b%Y") if m else pd.Timestamp(0)
    return sorted(set(urls), key=fin)


def parse_zip(path: Path, cusip: dict[str, str]) -> pd.DataFrame:
    inv = {v: k for k, v in cusip.items()}
    with zipfile.ZipFile(path) as zf:
        nombres = {Path(n).name.upper(): n for n in zf.namelist()}

        def tsv(n, cols):
            return pd.read_csv(io.BytesIO(zf.read(nombres[n])), sep="\t", dtype=str, usecols=cols, quoting=3,
                               on_bad_lines="skip", encoding="utf-8", encoding_errors="replace")
        sub = tsv("SUBMISSION.TSV", ["ACCESSION_NUMBER", "FILING_DATE", "SUBMISSIONTYPE", "CIK", "PERIODOFREPORT"])
        cov = tsv("COVERPAGE.TSV", ["ACCESSION_NUMBER", "FILINGMANAGER_NAME"])
        it = tsv("INFOTABLE.TSV", ["ACCESSION_NUMBER", "CUSIP", "VALUE", "SSHPRNAMT", "SSHPRNAMTTYPE", "PUTCALL"])
    it = it[it["CUSIP"].str.upper().isin(inv) & (it["SSHPRNAMTTYPE"].str.upper() == "SH") & it["PUTCALL"].isna()]
    sub = sub[sub["SUBMISSIONTYPE"] == "13F-HR"]
    d = it.merge(sub, on="ACCESSION_NUMBER").merge(cov, on="ACCESSION_NUMBER", how="left")
    d = d.assign(ticker=d["CUSIP"].str.upper().map(inv), shares=pd.to_numeric(d["SSHPRNAMT"], errors="coerce"),
                 value=pd.to_numeric(d["VALUE"], errors="coerce"),
                 period=pd.to_datetime(d["PERIODOFREPORT"], format="%d-%b-%Y", errors="coerce"),
                 filing_date=pd.to_datetime(d["FILING_DATE"], format="%d-%b-%Y", errors="coerce"),
                 cik=d["CIK"].str.lstrip("0"), gestor=d["FILINGMANAGER_NAME"])
    g = (d.groupby(["ticker", "period", "cik", "ACCESSION_NUMBER", "filing_date"], as_index=False)
         .agg(gestor=("gestor", "first"), shares=("shares", "sum"), value=("value", "sum")))
    g = g.rename(columns={"ACCESSION_NUMBER": "accession"})
    g["zip"] = path.name
    return g


def run(trimestres: int = 5, rehacer: bool = False) -> dict:
    out = salida()
    mp, pp = out / "meta.json", out / "posiciones.parquet"
    meta = json.loads(mp.read_text()) if mp.exists() and not rehacer else {"leidos": []}
    prev = pd.read_parquet(pp) if pp.exists() and not rehacer else pd.DataFrame()
    urls = listar()[-trimestres:]
    nuevos = []
    for u in urls:
        nom = u.rsplit("/", 1)[-1]
        if nom in meta["leidos"]:
            continue
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / nom
            t0 = time.monotonic()
            r = F4.sec_get(u, total=1800)
            dest.write_bytes(r.content)
            log.info("%s: %.0f MB en %.0f s", nom, dest.stat().st_size / 1e6, time.monotonic() - t0)
            try:
                nuevos.append(parse_zip(dest, CUSIP))
                meta["leidos"].append(nom)
            except Exception as e:  # noqa: BLE001
                log.warning("%s ilegible: %s", nom, e)
    d = pd.concat([x for x in [prev, *nuevos] if len(x)], ignore_index=True) if (len(prev) or nuevos) else prev
    if len(d):
        d = (d.sort_values("filing_date").drop_duplicates(["ticker", "period", "cik"], keep="last")
             .sort_values(["ticker", "period", "shares"], ascending=[True, True, False]))
        d.to_parquet(pp, index=False)
    meta.update({"actualizado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "fuente": LISTA,
                 "cusip": CUSIP, "filas": int(len(d)),
                 "periodos": sorted({str(x.date()) for x in d["period"].dropna()}) if len(d) else []})
    mp.write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    log.info("13F: %d filas, periodos %s", meta["filas"], meta["periodos"])
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trimestres", type=int, default=5)
    ap.add_argument("--rehacer", action="store_true")
    a = ap.parse_args()
    run(a.trimestres, a.rehacer)
