"""Precios diarios de acciones, ETF y materias primas que sigue el usuario (panel web, pestaña «Mis activos»).

Fuente: Yahoo Finance (endpoint público de gráficos v8; uso personal). El repositorio es PÚBLICO: los precios se
guardan SOLO en $FIN_DATA_ROOT/mercados/ (fuera de git y fuera del warehouse/catálogo); al repo solo llegan resultados
derivados (rentabilidades, simulaciones) dentro del panel local.

Guarda `precios_diarios.parquet` (columnas = tickers, cierre AJUSTADO por dividendos y splits; índice = fecha) y
`activos.json` (lista, nombres, moneda, fecha de la descarga).
Uso: .venv/bin/python -m src.ingest.yahoo_precios
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

log = logging.getLogger("yahoo_precios")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ticker → (nombre, grupo). Grupo solo para ordenar el panel.
ACTIVOS = {
    "GOOGL": ("Alphabet (Google)", "Acciones"), "MSFT": ("Microsoft", "Acciones"), "META": ("Meta Platforms", "Acciones"),
    "UBER": ("Uber", "Acciones"), "CHTR": ("Charter Communications", "Acciones"),
    "UNH": ("UnitedHealth", "Acciones"),
    "CTVA": ("Corteva (semillas y fitosanitarios)", "Agro / pesticidas"), "FMC": ("FMC (fitosanitarios)", "Agro / pesticidas"),
    "BAYN.DE": ("Bayer (EUR)", "Agro / pesticidas"), "MOO": ("ETF agronegocio (VanEck MOO)", "Agro / pesticidas"),
    "GLD": ("Oro (ETF GLD)", "Oro y materias primas"), "GDX": ("Mineras de oro (ETF GDX)", "Oro y materias primas"),
    "NEM": ("Newmont (minera de oro)", "Oro y materias primas"),
    "BZ=F": ("Petróleo Brent (futuro, 1.er vencimiento)", "Oro y materias primas"),
    "CL=F": ("Petróleo WTI (futuro, 1.er vencimiento)", "Oro y materias primas"),
    "XLE": ("ETF energía EE. UU. (XLE)", "ETF sectoriales"), "XLK": ("ETF tecnología (XLK)", "ETF sectoriales"),
    "XLV": ("ETF salud (XLV)", "ETF sectoriales"), "XLF": ("ETF financieras (XLF)", "ETF sectoriales"),
    "XLU": ("ETF eléctricas (XLU)", "ETF sectoriales"), "XLP": ("ETF consumo básico (XLP)", "ETF sectoriales"),
    "XLI": ("ETF industria (XLI)", "ETF sectoriales"), "XLB": ("ETF materiales (XLB)", "ETF sectoriales"),
    "XLC": ("ETF comunicaciones (XLC)", "ETF sectoriales"), "XLRE": ("ETF inmobiliario (XLRE)", "ETF sectoriales"),
    "SPY": ("S&P 500 (ETF SPY)", "Referencias"), "QQQ": ("Nasdaq 100 (ETF QQQ)", "Referencias"),
    "TLT": ("Bonos EE. UU. 20+ años (ETF TLT)", "Referencias"), "VGK": ("Bolsa europea (ETF VGK)", "Referencias"),
}
URL = ("https://query1.finance.yahoo.com/v8/finance/chart/{t}?period1=0&period2=9999999999&interval=1d"
       "&events=div%2Csplit")  # range=max mezcla frecuencias; con period1/period2 es diario de verdad
UA = "Mozilla/5.0 (Macintosh) personal-research"


def salida() -> Path:
    d = Path(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")).expanduser() / "mercados"
    d.mkdir(parents=True, exist_ok=True)
    return d


def descargar(t: str) -> tuple[pd.Series, dict]:
    for k in range(3):
        try:
            r = requests.get(URL.format(t=t), headers={"User-Agent": UA}, timeout=60)
            r.raise_for_status()
            res = r.json()["chart"]["result"][0]
            break
        except Exception as e:  # noqa: BLE001
            if k == 2:
                raise
            log.warning("%s: reintento (%s)", t, e)
            time.sleep(3 * (k + 1))
    ts = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert(None).normalize()
    adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose")
    cierre = adj if adj is not None else res["indicators"]["quote"][0]["close"]
    s = pd.Series(cierre, index=ts, dtype=float).dropna()
    s = s[~s.index.duplicated(keep="last")]
    m = res["meta"]
    return s, {"moneda": m.get("currency"), "tipo": m.get("instrumentType"), "mercado": m.get("fullExchangeName"),
               "ajustado": adj is not None}


def main() -> None:
    cols, meta, fallos = {}, {}, []
    for t, (nom, grupo) in ACTIVOS.items():
        try:
            s, m = descargar(t)
            cols[t] = s
            meta[t] = {"nombre": nom, "grupo": grupo, **m, "desde": str(s.index[0].date()), "hasta": str(s.index[-1].date())}
            log.info("%s: %d días %s → %s", t, len(s), s.index[0].date(), s.index[-1].date())
        except Exception as e:  # noqa: BLE001
            fallos.append(t)
            log.error("%s: FALLO %s", t, e)
        time.sleep(0.4)
    if not cols:
        raise SystemExit("yahoo_precios: ninguna descarga")
    d = salida()
    pd.DataFrame(cols).sort_index().to_parquet(d / "precios_diarios.parquet")
    (d / "activos.json").write_text(json.dumps({"descarga": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                                "fuente": "Yahoo Finance (v8 chart, cierre ajustado)",
                                                "activos": meta, "fallos": fallos}, ensure_ascii=False, indent=1))
    log.info("yahoo_precios: %d activos, %d fallos → %s", len(cols), len(fallos), d)
    if fallos:
        raise SystemExit(f"yahoo_precios: fallos {fallos}")


if __name__ == "__main__":
    main()
