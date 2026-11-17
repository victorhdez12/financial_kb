"""Precios diarios de acciones, ETF y materias primas que sigue el usuario (panel web, pestaña «Mis activos»).

Fuente: Yahoo Finance (endpoint público de gráficos v8; uso personal). El repositorio es PÚBLICO: los precios se
guardan SOLO en $FIN_DATA_ROOT/mercados/ (fuera de git y fuera del warehouse/catálogo); al repo solo llegan resultados
derivados (rentabilidades, simulaciones) dentro del panel local.

Guarda `precios_diarios.parquet` (columnas = tickers, cierre AJUSTADO por dividendos y splits; índice = fecha) y
`activos.json` (lista, nombres, moneda, fecha de la descarga). En la misma petición (sin coste extra) guarda también en
`mercados/volumen/` (añadido el 17-nov-2026 para la ficha v2, docs/panel/activos_v2.md): `volumen_diario.parquet`
(acciones/participaciones negociadas por sesión; en futuros, contratos del 1.er vencimiento), `cierre_diario.parquet`
(cierre ajustado SOLO por splits, no por dividendos: es el que se compara con los precios de los Form 4) y
`splits.json` (fecha y factor de cada split según Yahoo). Desde el 17-nov-2026 (alertas, docs/panel/alertas_v1.md)
también `apertura_diario.parquet`, `alto_diario.parquet` y `bajo_diario.parquet` (OHLC de la misma petición, en la
misma escala que `cierre_diario`: ajustados solo por splits).
Uso: .venv/bin/python -m src.ingest.yahoo_precios [--solo-volumen]   (--solo-volumen: no reescribe los precios)
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.ingest import _http

log = logging.getLogger("yahoo_precios")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ticker → (nombre, grupo). Grupo solo para ordenar el panel.
ACTIVOS = {
    "GOOGL": ("Alphabet (Google)", "Acciones"), "MSFT": ("Microsoft", "Acciones"), "META": ("Meta Platforms", "Acciones"),
    "UBER": ("Uber", "Acciones"), "CHTR": ("Charter Communications", "Acciones"),
    "UNH": ("UnitedHealth", "Acciones"),
    "CTVA": ("Corteva (fitosanitarios; semillas escindidas en Vylor el 1-oct-2026)", "Agro / pesticidas"),
    "VYLR": ("Vylor (semillas; escindida de Corteva el 1-oct-2026)", "Agro / pesticidas"), "FMC": ("FMC (fitosanitarios)", "Agro / pesticidas"),
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
    s, m, _ = descargar_detalle(t)
    return s, m


def descargar_detalle(t: str) -> tuple[pd.Series, dict, dict]:
    """(cierre ajustado, meta, extra) con extra = {"volumen", "cierre"} (Series) y "splits" (lista)."""
    for k in range(3):
        try:
            r = _http.get(URL.format(t=t), headers={"User-Agent": UA}, timeout=60)
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
    q = (res["indicators"].get("quote") or [{}])[0]

    def _serie(v):
        if v is None:
            return pd.Series(dtype=float)
        x = pd.Series(v, index=ts, dtype=float).dropna()
        return x[~x.index.duplicated(keep="last")]
    splits = [{"fecha": str(pd.Timestamp(int(v["date"]), unit="s").date()),
               "factor": float(v["numerator"]) / float(v["denominator"])}
              for v in ((res.get("events") or {}).get("splits") or {}).values()
              if v.get("numerator") and v.get("denominator")]
    extra = {"volumen": _serie(q.get("volume")), "cierre": _serie(q.get("close")), "apertura": _serie(q.get("open")),
             "alto": _serie(q.get("high")), "bajo": _serie(q.get("low")),
             "splits": sorted(splits, key=lambda x: x["fecha"])}
    return s, extra_meta(m, adj), extra


def extra_meta(m: dict, adj) -> dict:
    return {"moneda": m.get("currency"), "tipo": m.get("instrumentType"), "mercado": m.get("fullExchangeName"),
            "ajustado": adj is not None}


def guardar_volumen(d: Path, vol: dict, cie: dict, spl: dict, ohlc: dict | None = None) -> None:
    dv = d / "volumen"
    dv.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(vol).sort_index().to_parquet(dv / "volumen_diario.parquet")
    pd.DataFrame(cie).sort_index().to_parquet(dv / "cierre_diario.parquet")
    for k, x in (ohlc or {}).items():   # apertura / alto / bajo (alertas de volumen: dónde cerró en el rango del día)
        if x:
            pd.DataFrame(x).sort_index().to_parquet(dv / f"{k}_diario.parquet")
    (dv / "splits.json").write_text(json.dumps({"descarga": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                                "fuente": "Yahoo Finance (v8 chart: volume, close, events=split)",
                                                "splits": spl}, ensure_ascii=False, indent=1))


def main(solo_volumen: bool = False) -> None:
    """solo_volumen=True: descarga igual pero escribe solo mercados/volumen/ (no toca precios_diarios ni activos.json)."""
    cols, meta, fallos = {}, {}, []
    vol, cie, spl = {}, {}, {}
    ohlc: dict[str, dict] = {"apertura": {}, "alto": {}, "bajo": {}}
    for t, (nom, grupo) in ACTIVOS.items():
        try:
            s, m, ex = descargar_detalle(t)
            cols[t] = s
            vol[t], cie[t], spl[t] = ex["volumen"], ex["cierre"], ex["splits"]
            for k in ohlc:
                ohlc[k][t] = ex[k]
            meta[t] = {"nombre": nom, "grupo": grupo, **m, "desde": str(s.index[0].date()), "hasta": str(s.index[-1].date())}
            log.info("%s: %d días %s → %s", t, len(s), s.index[0].date(), s.index[-1].date())
        except Exception as e:  # noqa: BLE001
            fallos.append(t)
            log.error("%s: FALLO %s", t, e)
        time.sleep(0.4)
    if not cols:
        raise SystemExit("yahoo_precios: ninguna descarga")
    d = salida()
    if not solo_volumen:
        pd.DataFrame(cols).sort_index().to_parquet(d / "precios_diarios.parquet")
        (d / "activos.json").write_text(json.dumps({"descarga": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                                    "fuente": "Yahoo Finance (v8 chart, cierre ajustado)",
                                                    "activos": meta, "fallos": fallos}, ensure_ascii=False, indent=1))
    try:  # volumen y cierre sin ajuste de dividendos (ficha v2); un fallo aquí no tumba los precios
        guardar_volumen(d, vol, cie, spl, ohlc)
    except Exception as e:  # noqa: BLE001
        log.error("volumen: FALLO %s", e)
    log.info("yahoo_precios: %d activos, %d fallos → %s", len(cols), len(fallos), d)
    if fallos:
        raise SystemExit(f"yahoo_precios: fallos {fallos}")


if __name__ == "__main__":
    import sys
    main(solo_volumen="--solo-volumen" in sys.argv[1:])
