"""Vintages ALFRED que la base point-in-time necesita y no están en el warehouse.

Se guardan fuera del warehouse, en <FIN_DATA_ROOT>/features/raw/alfred/<serie>.parquet (igual que hace la etiqueta
con labels/raw/alfred). Reutiliza el cliente de src/ingest sin modificarlo. Dos usos:
- fuente de vintages / fechas de publicación (PERMIT, CMRMTSPL, NFCI, W875RX1...) en el calendario;
- verificación independiente de los retardos supuestos del calendario (tests/test_pit_leaks.py).

    .venv/bin/python -m src.features.alfred_raw            # descarga (caché de 20 h en los .json)
"""
from __future__ import annotations

import argparse

import pandas as pd

from src.warehouse import db

RAW_SERIES = (
    # fuentes de vintages/fechas en el calendario
    "PERMIT", "CMRMTSPL", "NFCI", "W875RX1",
    # verificación de supuestos (y proxies de las variables nuevas)
    "AWHMAN", "AHETPI", "CUSR0000SASLE", "GACDFSA066MSFRBPHI", "NOCDFSA066MSFRBPHI", "PPCDFSA066MSFRBPHI",
    "UMCSENT", "MICH",
)


def raw_dir():
    return db.DATA_ROOT / "features" / "raw" / "alfred"


def load(sid: str) -> pd.DataFrame | None:
    """Vintages descargadas de `sid` (date, value, realtime_start), o None."""
    f = raw_dir() / f"{sid}.parquet"
    if not f.exists():
        return None
    df = pd.read_parquet(f)[["date", "value", "realtime_start"]]
    df["date"] = pd.to_datetime(df["date"])
    df["realtime_start"] = pd.to_datetime(df["realtime_start"])
    return df


def fetch(sids=RAW_SERIES, refresh: bool = False) -> list[str]:
    from src.ingest.alfred_vintages import download, normalise
    from src.ingest.fred_extended import Fred

    raw = raw_dir()
    raw.mkdir(parents=True, exist_ok=True)
    fred, msgs = Fred(), []
    for sid in sids:
        try:
            _, obs = download(fred, sid, raw, refresh)
            df = normalise(obs, sid)
            df.to_parquet(raw / f"{sid}.parquet", index=False)
            msgs.append(f"{sid}: {len(df)} filas, {df['realtime_start'].nunique()} vintages "
                        f"({df['realtime_start'].min()} → {df['realtime_start'].max()})")
        except Exception as e:  # noqa: BLE001 — si ALFRED no la tiene, se anota y se sigue
            msgs.append(f"{sid}: ALFRED no la devuelve ({type(e).__name__}: {e})")
    return msgs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true")
    for m in fetch(refresh=ap.parse_args().refresh):
        print(m)


if __name__ == "__main__":
    main()
