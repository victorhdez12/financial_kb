"""Participaciones del 5 %+ (Schedule 13D/13G y sus enmiendas) y fechas de resultados (8-K, punto 2.02) de las acciones
de EE. UU. de «Mis activos» (alertas del panel, docs/panel/alertas_v1.md; diaria, segundos).

    .venv/bin/python -m src.ingest.sec_flujos [--meses 24]

Fuente: EDGAR (data.sec.gov/submissions del emisor). La lista de presentaciones de un emisor incluye tanto las que
presenta él como las que otros presentan SOBRE él (un 13G de Vanguard sobre UBER sale en la lista de UBER) y también
las que el emisor presenta sobre OTRAS empresas (UBER declara su 13D sobre Grab o Aurora): por eso se lee el XML y se
guarda solo si el emisor del 13D/G (issuerCik) es la propia empresa.

1. 13D/13G: desde el 18-dic-2024 son XML estructurados (SCHEDULE 13D, SCHEDULE 13G, …/A): se guarda quién declara,
   % de la clase (classPercent: el mayor de las personas del formulario), acciones, fecha del hecho y si el formulario
   dice que es una reorganización interna (p. ej. «realignment» de Vanguard en 2026: pasa a 0 % sin vender nada). Los
   antiguos en texto/HTML (SC 13D, SC 13G) NO se guardan (sin leer su cabecera no se sabe si son sobre la empresa o de
   la empresa sobre otra; además son anteriores a los 12 meses de las alertas).
2. Resultados trimestrales: fechas de los 8-K con el punto 2.02 («Results of Operations») y su hora de aceptación (si
   es después del cierre, el volumen de la reacción es el de la sesión siguiente). Se leen también las páginas
   antiguas de la lista (submissions-00N.json; cacheadas: no cambian) para marcar los días de resultados en la
   historia de volumen.

SEC: User-Agent genérico (sin datos del usuario), ≤ 5 peticiones/s (limitador común), plazo total por descarga.
Fuera de git: $FIN_DATA_ROOT/sec_flujos/{participaciones.parquet, resultados.json, meta.json, xml/, paginas/}.
"""
from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.ingest import sec_form4_detalle as F4

log = F4.get_logger("sec_flujos")
FORMAS = {"SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A", "SCHEDULE 13D", "SCHEDULE 13D/A", "SCHEDULE 13G", "SCHEDULE 13G/A"}
COLS = ["ticker", "issuer_cik", "accession", "form", "filing_date", "event_date", "filer_cik", "filer", "pct",
        "acciones", "reorganizacion", "xml"]
RE_REORG = re.compile(r"realign|reorganiz|disaggregat|internal restructur", re.I)


def salida() -> Path:
    d = F4.root() / "sec_flujos"
    (d / "xml").mkdir(parents=True, exist_ok=True)
    (d / "paginas").mkdir(parents=True, exist_ok=True)
    return d


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _buscar(el, nombre: str) -> list:
    return [x for x in el.iter() if _local(x.tag) == nombre]


def _num(x) -> float | None:
    try:
        return float(str(x).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def parse_13dg(xml: str) -> dict:
    """De un XML de Schedule 13D/13G (esquema 2024): emisor, declarante, % (el mayor), acciones, fecha, reorganización."""
    r = ET.fromstring(xml)

    def primero(nombre):
        xs = _buscar(r, nombre)
        return (xs[0].text or "").strip() if xs and xs[0].text else None
    pcts = [_num(x.text) for x in _buscar(r, "classPercent") + _buscar(r, "percentOfClass")]
    pcts = [p for p in pcts if p is not None]
    acc = [_num(x.text) for x in _buscar(r, "reportingPersonBeneficiallyOwnedAggregateNumberOfShares")
           + _buscar(r, "aggregateAmountOwned")]
    acc = [a for a in acc if a is not None]
    coment = " ".join("".join(x.itertext()) for x in _buscar(r, "comments"))
    fecha = primero("eventDateRequiresFilingThisStatement") or primero("dateOfEvent")
    try:
        fecha = str(pd.to_datetime(fecha, format="%m/%d/%Y").date()) if fecha else None
    except Exception:  # noqa: BLE001
        fecha = None
    nombre = primero("reportingPersonName") or primero("filingPersonName")
    return {"issuer_cik": (primero("issuerCik") or primero("issuerCIK") or "").lstrip("0"),
            "filer_cik": (primero("cik") or "").lstrip("0"), "filer": nombre,
            "pct": max(pcts) if pcts else None, "acciones": max(acc) if acc else None, "event_date": fecha,
            "reorganizacion": bool(RE_REORG.search(coment or ""))}


def resultados_de(sub: dict) -> list[dict]:
    """8-K con el punto 2.02 de una página de submissions (recent o submissions-00N)."""
    out = []
    for i, f in enumerate(sub.get("form") or []):
        if f in ("8-K", "8-K/A") and "2.02" in str((sub.get("items") or [""] * (i + 1))[i]):
            out.append({"fecha": sub["filingDate"][i], "aceptado": (sub.get("acceptanceDateTime") or [None] * (i + 1))[i],
                        "accession": sub["accessionNumber"][i]})
    return out


def run(meses: int = 24) -> dict:
    out = salida()
    ciks = F4.acciones()
    desde = pd.Timestamp.now().normalize() - pd.DateOffset(months=meses)
    filas, res, fallos, nuevos = [], {}, [], 0
    for t, cik in ciks.items():
        try:
            d = F4.sec_get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json").json()
        except Exception as e:  # noqa: BLE001
            log.warning("%s: submissions %s", t, e)
            fallos.append(t)
            continue
        rec = d["filings"]["recent"]
        r8 = resultados_de(rec)
        for pg in d["filings"].get("files") or []:   # páginas antiguas: no cambian, se cachean
            cp = out / "paginas" / pg["name"]
            try:
                js = json.loads(cp.read_text()) if cp.exists() else F4.sec_get(f"https://data.sec.gov/submissions/{pg['name']}").json()
                if not cp.exists():
                    cp.write_text(json.dumps(js))
                r8 += resultados_de(js)
            except Exception as e:  # noqa: BLE001
                log.warning("%s: página %s %s", t, pg.get("name"), e)
        res[t] = sorted({x["fecha"]: x for x in r8}.values(), key=lambda x: x["fecha"])
        for i, f in enumerate(rec["form"]):
            if f not in FORMAS or pd.Timestamp(rec["filingDate"][i]) < desde:
                continue
            acc, doc = rec["accessionNumber"][i], rec["primaryDocument"][i]
            fila = {"ticker": t, "issuer_cik": cik, "accession": acc, "form": f, "filing_date": rec["filingDate"][i],
                    "event_date": None, "filer_cik": acc.split("-")[0].lstrip("0"), "filer": None, "pct": None,
                    "acciones": None, "reorganizacion": False, "xml": False}
            if doc.endswith(".xml"):
                cp = out / "xml" / f"{acc}.xml"
                try:
                    if cp.exists():
                        xml = cp.read_text()
                    else:
                        doc = re.sub(r"^xsl[^/]+/", "", doc)
                        xml = F4.sec_get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}").text
                        cp.write_text(xml)
                        nuevos += 1
                    p = parse_13dg(xml)
                    if p["issuer_cik"] and p["issuer_cik"] != str(cik):
                        continue   # el emisor declara SU participación en otra empresa (UBER sobre Grab, Aurora…)
                    fila.update({k: p[k] for k in ("event_date", "filer_cik", "filer", "pct", "acciones", "reorganizacion")})
                    fila["xml"] = True
                except Exception as e:  # noqa: BLE001
                    log.warning("%s %s: %s", t, acc, e)
            else:
                continue   # formato antiguo (texto/HTML, antes del 18-dic-2024): sin emisor fiable, no se guarda
            filas.append(fila)
    df = pd.DataFrame(filas, columns=COLS)
    for c in ("filing_date", "event_date"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df.to_parquet(out / "participaciones.parquet", index=False)
    (out / "resultados.json").write_text(json.dumps(res, indent=0))
    meta = {"actualizado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "desde": str(desde.date()),
            "formularios": int(len(df)), "xml_nuevos": nuevos, "fallos": fallos,
            "fuente": "SEC EDGAR submissions + Schedule 13D/13G XML"}
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    log.info("sec_flujos: %s", meta)
    if fallos and len(fallos) == len(ciks):
        raise SystemExit("sec_flujos: FALLO en todos los emisores")
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--meses", type=int, default=24)
    run(ap.parse_args().meses)
