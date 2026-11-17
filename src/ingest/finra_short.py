"""Volumen en corto diario de FINRA (Reg SHO «daily short sale volume») de los activos de «Mis activos» (alertas del
panel, docs/panel/alertas_v1.md; diaria, segundos).

    .venv/bin/python -m src.ingest.finra_short [--sesiones 70]

Fuente: ficheros públicos de FINRA (https://cdn.finra.org/equity/regsho/daily/CNMSshvolAAAAMMDD.txt, uno por sesión,
~0,5 MB, todo el mercado: fecha|símbolo|volumen en corto|exento|volumen total|mercados). Se baja cada sesión una sola
vez (las que faltan de las últimas `--sesiones`), se filtran los símbolos de «Mis activos» y se borra el fichero.

QUÉ ES: ventas en corto declaradas en los mercados fuera de bolsa y TRF de FINRA (no todo el volumen de la bolsa), en
gran parte creadores de mercado que venden en corto para dar contrapartida a compradores: un 40-60 % es normal y NO
equivale a «posiciones cortas» (eso es el short interest, quincenal). Solo contexto.
Fuera de git: $FIN_DATA_ROOT/finra_short/short_diario.parquet + meta.json.
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from src.ingest import _http
from src.ingest.yahoo_precios import ACTIVOS

log = logging.getLogger("finra_short")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{d}.txt"
UA = "financial-kb-panel/1.0 research-client"   # genérico: sin datos del usuario


def salida() -> Path:
    d = Path(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")).expanduser() / "finra_short"
    d.mkdir(parents=True, exist_ok=True)
    return d


def simbolos() -> list[str]:
    return [t for t in ACTIVOS if "." not in t and "=" not in t]


def parse(txt: str, sims: list[str]) -> pd.DataFrame:
    d = pd.read_csv(io.StringIO(txt), sep="|", dtype={"Date": str, "Symbol": str})
    d = d[d["Symbol"].isin(sims)]
    return pd.DataFrame({"fecha": pd.to_datetime(d["Date"], format="%Y%m%d"), "ticker": d["Symbol"],
                         "corto": pd.to_numeric(d["ShortVolume"], errors="coerce"),
                         "total": pd.to_numeric(d["TotalVolume"], errors="coerce")})


def run(sesiones: int = 70) -> dict:
    out = salida()
    pp = out / "short_diario.parquet"
    prev = pd.read_parquet(pp) if pp.exists() else pd.DataFrame(columns=["fecha", "ticker", "corto", "total"])
    vistos = {pd.Timestamp(x).date() for x in prev["fecha"].unique()}
    hoy = date.today()
    dias = [hoy - timedelta(days=k) for k in range(0, int(sesiones * 1.5) + 5)]
    dias = [d for d in dias if d.weekday() < 5 and d not in vistos][:sesiones]
    sims, nuevos, faltan = simbolos(), [], 0
    for d in sorted(dias):
        try:
            r = _http.get(URL.format(d=d.strftime("%Y%m%d")), headers={"User-Agent": UA}, timeout=30, total=60)
            if r.status_code in (403, 404):   # festivo o aún no publicado (sale hacia las 18:00 de Nueva York)
                faltan += 1
                continue
            r.raise_for_status()
            nuevos.append(parse(r.text, sims))
        except Exception as e:  # noqa: BLE001
            log.warning("%s: %s", d, e)
        time.sleep(0.2)
    d = pd.concat([x for x in [prev, *nuevos] if len(x)], ignore_index=True) if nuevos else prev
    d = d.drop_duplicates(["fecha", "ticker"], keep="last").sort_values(["ticker", "fecha"])
    d = d[d["fecha"] >= pd.Timestamp(hoy) - pd.Timedelta(days=400)]
    d.to_parquet(pp, index=False)
    meta = {"actualizado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sesiones_nuevas": len(nuevos),
            "sin_fichero": faltan, "ultima": str(pd.Timestamp(d["fecha"].max()).date()) if len(d) else None,
            "fuente": "FINRA Reg SHO daily short sale volume (CNMS)"}
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    log.info("finra_short: %s", meta)
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sesiones", type=int, default=70)
    run(ap.parse_args().sesiones)
