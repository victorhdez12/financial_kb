"""Descarga puntual (18-nov-2026) de cotizaciones diarias completas + intradía de hoy para el informe
«caída del oro y las bolsas» (obsidian/Reports/2026-11-18_caida_oro_bolsas.md).

Mismo mecanismo que src/ingest/yahoo_precios.py (endpoint público v8 de Yahoo, uso personal). Los datos en bruto se
guardan SOLO fuera de git: $FIN_DATA_ROOT/mercados/intradia/<fecha>/ (diario.parquet, intradia_5m.parquet,
meta.json). No toca precios_diarios.parquet ni ningún registro.
Uso: .venv/bin/python -m scripts.caida_2026_11_18_descarga [AAAA-MM-DD]
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.ingest import _http
from src.ingest.yahoo_precios import ACTIVOS, UA

MERCADO = {
    # ticker: (nombre, grupo)
    "GC=F": ("Oro (futuro COMEX)", "Oro y metales"), "GLD": ("Oro (ETF GLD)", "Oro y metales"),
    "SI=F": ("Plata (futuro)", "Oro y metales"), "SLV": ("Plata (ETF SLV)", "Oro y metales"),
    "GDX": ("Mineras de oro (GDX)", "Oro y metales"), "HG=F": ("Cobre (futuro)", "Oro y metales"),
    "^GSPC": ("S&P 500", "Bolsa EE. UU."), "ES=F": ("S&P 500 (futuro)", "Bolsa EE. UU."),
    "^NDX": ("Nasdaq 100", "Bolsa EE. UU."), "NQ=F": ("Nasdaq 100 (futuro)", "Bolsa EE. UU."),
    "^RUT": ("Russell 2000", "Bolsa EE. UU."), "RTY=F": ("Russell 2000 (futuro)", "Bolsa EE. UU."),
    "^STOXX50E": ("Euro Stoxx 50", "Bolsa Europa"), "^GDAXI": ("DAX", "Bolsa Europa"),
    "^IBEX": ("IBEX 35", "Bolsa Europa"), "^FTSE": ("FTSE 100", "Bolsa Europa"),
    "^N225": ("Nikkei 225", "Bolsa Asia"), "^HSI": ("Hang Seng", "Bolsa Asia"), "^KS11": ("Kospi", "Bolsa Asia"),
    "000001.SS": ("Shanghái", "Bolsa Asia"), "EEM": ("Emergentes (EEM)", "Bolsa Asia"),
    "^VIX": ("VIX", "Riesgo"), "HYG": ("Bonos high yield (HYG)", "Riesgo"), "LQD": ("Bonos grado inversión (LQD)", "Riesgo"),
    "DX-Y.NYB": ("Dólar (DXY)", "Divisas"), "EURUSD=X": ("EUR/USD", "Divisas"), "JPY=X": ("USD/JPY", "Divisas"),
    "CHF=X": ("USD/CHF", "Divisas"),
    "^TNX": ("Bono 10a EE. UU. (rentab. ×10)", "Tipos"), "^IRX": ("Letra 13 sem. (rentab. ×10)", "Tipos"),
    "ZN=F": ("Futuro bono 10a", "Tipos"), "TIP": ("Bonos ligados a inflación (TIP)", "Tipos"),
    "IEF": ("Bonos 7-10a (IEF)", "Tipos"), "SHY": ("Bonos 1-3a (SHY)", "Tipos"),
    "CL=F": ("Petróleo WTI", "Energía"), "BZ=F": ("Petróleo Brent", "Energía"),
    "BTC-USD": ("Bitcoin", "Cripto"),
}
TODOS = {**{t: v for t, v in ACTIVOS.items()}, **MERCADO}
DIARIO = ("https://query1.finance.yahoo.com/v8/finance/chart/{t}?period1=0&period2=9999999999&interval=1d"
          "&events=div%2Csplit")
INTRA = "https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=5d&interval=5m&includePrePost=true"


def _get(url: str) -> dict:
    for k in range(3):
        try:
            r = _http.get(url, headers={"User-Agent": UA}, timeout=60)
            r.raise_for_status()
            return r.json()["chart"]["result"][0]
        except Exception:  # noqa: BLE001
            if k == 2:
                raise
            time.sleep(3 * (k + 1))
    raise RuntimeError


def main(fecha: str) -> None:
    out = Path(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")).expanduser() / "mercados" / "intradia" / fecha
    out.mkdir(parents=True, exist_ok=True)
    cierre, volumen, intra, meta, fallos = {}, {}, {}, {}, []
    for t, (nom, grupo) in TODOS.items():
        try:
            res = _get(DIARIO.format(t=t))
            ts = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert(None).normalize()
            q = res["indicators"]["quote"][0]
            adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose")
            s = pd.Series(adj if adj is not None else q["close"], index=ts, dtype=float)
            v = pd.Series(q.get("volume"), index=ts, dtype=float)
            cierre[t] = s[~s.index.duplicated(keep="last")]
            volumen[t] = v[~v.index.duplicated(keep="last")]
            m = res["meta"]
            meta[t] = {"nombre": nom, "grupo": grupo, "moneda": m.get("currency"), "tipo": m.get("instrumentType"),
                       "ultimo": m.get("regularMarketPrice"), "hora_ultimo_utc":
                       datetime.fromtimestamp(m.get("regularMarketTime", 0), timezone.utc).isoformat(),
                       "cierre_previo_meta": m.get("chartPreviousClose"),
                       "max_52s": m.get("fiftyTwoWeekHigh"), "min_52s": m.get("fiftyTwoWeekLow"),
                       "zona": m.get("exchangeTimezoneName")}
            time.sleep(0.3)
            ri = _get(INTRA.format(t=t))
            if ri.get("timestamp"):
                ti = pd.to_datetime(ri["timestamp"], unit="s", utc=True)
                intra[t] = pd.Series(ri["indicators"]["quote"][0]["close"], index=ti, dtype=float)
                intra[t] = intra[t][~intra[t].index.duplicated(keep="last")]
            time.sleep(0.3)
            print(t, "ok", meta[t]["ultimo"], meta[t]["hora_ultimo_utc"])
        except Exception as e:  # noqa: BLE001
            fallos.append(t)
            print(t, "FALLO", e)
    pd.DataFrame(cierre).sort_index().to_parquet(out / "diario.parquet")
    pd.DataFrame(volumen).sort_index().to_parquet(out / "volumen.parquet")
    pd.DataFrame(intra).sort_index().to_parquet(out / "intradia_5m.parquet")
    (out / "meta.json").write_text(json.dumps({"descarga": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                               "fuente": "Yahoo Finance v8 chart (uso personal)", "activos": meta,
                                               "fallos": fallos}, ensure_ascii=False, indent=1))
    print("guardado en", out, "fallos:", fallos)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d"))
