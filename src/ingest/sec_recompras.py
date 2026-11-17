"""Recompras de acciones y acciones en circulación de las acciones de EE. UU. de «Mis activos» (alertas del panel,
docs/panel/alertas_v1.md; semanal, ~30 s).

    .venv/bin/python -m src.ingest.sec_recompras

Fuente: SEC XBRL «companyfacts» (data.sec.gov/api/xbrl/companyfacts/CIK##########.json: todos los datos XBRL de los
10-Q/10-K de la empresa, 2-4 MB por empresa). Se guardan SOLO los conceptos de abajo (compacto, fuera de git):
importe pagado por recompras (flujo de caja), importe/acciones recompradas (patrimonio), programa autorizado y lo que
queda de él, y acciones en circulación (portada `dei` y balance). El cálculo (trimestres, 12 meses, % de la
capitalización) está en src/report/alertas.py.

SEC: User-Agent genérico (sin datos del usuario), ≤ 5 peticiones/s (limitador común), plazo total por descarga.
Fuera de git: $FIN_DATA_ROOT/sec_recompras/hechos.json.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.ingest import sec_form4_detalle as F4

log = F4.get_logger("sec_recompras")
CONCEPTOS = {
    "us-gaap": ["PaymentsForRepurchaseOfCommonStock", "PaymentsForRepurchaseOfEquity",
                "StockRepurchasedDuringPeriodValue", "StockRepurchasedAndRetiredDuringPeriodValue",
                "StockRepurchasedDuringPeriodShares", "StockRepurchasedAndRetiredDuringPeriodShares",
                "StockRepurchaseProgramAuthorizedAmount1", "StockRepurchaseProgramRemainingAuthorizedRepurchaseAmount1",
                "CommonStockSharesOutstanding", "WeightedAverageNumberOfDilutedSharesOutstanding"],
    "srt": ["StockRepurchaseProgramAuthorizedAmount1"],
    "dei": ["EntityCommonStockSharesOutstanding"],
}
CAMPOS = ("start", "end", "val", "form", "filed", "fp", "fy", "accn")


def salida() -> Path:
    d = F4.root() / "sec_recompras"
    d.mkdir(parents=True, exist_ok=True)
    return d


def compactar(cf: dict) -> dict:
    """{"tax:Concepto": [hechos]} solo con los conceptos de CONCEPTOS (unidad USD o shares)."""
    out = {}
    f = cf.get("facts") or {}
    for tax, cs in CONCEPTOS.items():
        for c in cs:
            u = ((f.get(tax) or {}).get(c) or {}).get("units") or {}
            v = u.get("USD") or u.get("shares")
            if v:
                out[f"{tax}:{c}"] = [{k: x.get(k) for k in CAMPOS if k in x} for x in v]
    return out


def run() -> dict:
    ciks = F4.acciones()
    out, fallos = {}, []
    for t, cik in ciks.items():
        try:
            cf = F4.sec_get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json", total=180).json()
            out[t] = {"cik": cik, "nombre": cf.get("entityName"), "hechos": compactar(cf)}
            log.info("%s: %d conceptos", t, len(out[t]["hechos"]))
        except Exception as e:  # noqa: BLE001
            fallos.append(t)
            log.warning("%s: %s", t, e)   # p. ej. VYLR (recién escindida) aún sin companyfacts
    if not out:
        raise SystemExit("sec_recompras: FALLO (ninguna empresa)")
    p = salida() / "hechos.json"
    p.write_text(json.dumps({"actualizado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             "fuente": "SEC XBRL companyfacts", "empresas": out, "fallos": fallos}))
    log.info("sec_recompras: %d empresas, fallos %s", len(out), fallos)
    return {"empresas": len(out), "fallos": fallos}


if __name__ == "__main__":
    run()
