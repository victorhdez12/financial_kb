"""Datos en tiempo real para la verificación: vintages y primera publicación.

Fuentes:
- tabla `vintages` del warehouse (ALFRED, refrescada en la ingesta semanal) -> historial completo;
- descarga ligera de FRED/ALFRED (`refrescar`), solo de las series del registro y solo los vintages vigentes desde
  hace ~400 días, a ~/financial_archive/verif/cache/<serie>.parquet. La usa el flujo diario para saber, el mismo día,
  qué dato ya se ha publicado (la ingesta ALFRED del warehouse es semanal).

`Vintages.as_of(serie, fecha)` = la serie tal como se conocía al cierre de `fecha` (incluye lo publicado ese día).
`Vintages.publicacion(serie, periodo)` = primera fecha de publicación de ese periodo.
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.warehouse import db

SERIES = ["CPIAUCSL", "CPILFESL", "PAYEMS", "UNRATE", "GDPC1", "INDPRO", "ICSA"]
DIARIAS = ["DCOILWTICO"]          # precios de mercado (no se revisan): se leen de obs_latest
log = logging.getLogger("verif.datos")


def dir_archivo() -> Path:
    return Path(os.path.expanduser(os.environ.get("FIN_VERIF_DIR", str(db.DATA_ROOT / "verif"))))


def dir_cache() -> Path:
    return dir_archivo() / "cache"


def refrescar(series: list[str] = SERIES, dias: int = 400) -> dict:
    """Descarga los vintages recientes de FRED (≈ 7 llamadas). Devuelve {serie: n filas} o lanza si falla."""
    from src.ingest.fred_extended import Fred
    fred = Fred()
    desde = (date.today() - timedelta(days=dias)).isoformat()
    dir_cache().mkdir(parents=True, exist_ok=True)
    out = {}
    for sid in series:
        obs, offset, count = [], 0, None
        while count is None or offset < count:
            j = fred.get("series/observations", series_id=sid, realtime_start=desde, realtime_end="9999-12-31",
                         observation_start="1990-01-01", limit=100000, offset=offset)
            count = int(j["count"])
            if not j["observations"]:
                break
            obs += j["observations"]
            offset = len(obs)
        df = pd.DataFrame(obs)
        df = pd.DataFrame({
            "date": pd.to_datetime(df["date"]),
            "value": pd.to_numeric(df["value"].replace(".", None), errors="coerce").astype("float64"),
            "realtime_start": pd.to_datetime(df["realtime_start"]),
            "realtime_end": pd.to_datetime(df["realtime_end"].where(~df["realtime_end"].str.startswith("9999"))),
            "series_id": sid})
        # ALFRED recorta realtime_start a `desde`: esas filas valen para as_of, no para fechar la publicación
        df["clip"] = df["realtime_start"] == pd.Timestamp(desde)
        tmp = dir_cache() / f"{sid}.parquet.part"
        df.to_parquet(tmp, index=False)
        tmp.replace(dir_cache() / f"{sid}.parquet")
        out[sid] = len(df)
    (dir_cache() / "_descarga.txt").write_text(date.today().isoformat())
    return out


def cache_de_hoy(hoy: date | None = None) -> bool:
    p = dir_cache() / "_descarga.txt"
    return p.exists() and p.read_text().strip() == (hoy or date.today()).isoformat()


class Vintages:
    """Acceso point-in-time a las series del registro. `tablas` permite inyectar datos sintéticos (tests)."""

    def __init__(self, tablas: dict[str, pd.DataFrame] | None = None, diarias: dict[str, pd.Series] | None = None,
                 usar_cache: bool = True):
        if tablas is not None:
            self.t = {k: self._norm(v) for k, v in tablas.items()}
            self.d = diarias or {}
            return
        con = db.connect()
        try:
            self.t = {}
            for sid in SERIES:
                df = con.execute("select date, value, realtime_start, realtime_end from vintages "
                                 "where series_id = ? and source = 'alfred'", [sid]).df()
                c = dir_cache() / f"{sid}.parquet"
                if usar_cache and c.exists():
                    dc = pd.read_parquet(c)[["date", "value", "realtime_start", "realtime_end", "clip"]]
                    df = pd.concat([df, dc], ignore_index=True)
                self.t[sid] = self._norm(df)
            self.d = {sid: db.series(con, sid) for sid in DIARIAS}
        finally:
            con.close()

    @staticmethod
    def _norm(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["clip"] = df["clip"].fillna(False).astype(bool) if "clip" in df else False
        for c in ("date", "realtime_start", "realtime_end"):
            df[c] = pd.to_datetime(df[c])
        # la descarga reciente pisa a la del warehouse (realtime_end actualizado)
        return df.drop_duplicates(["date", "realtime_start"], keep="last").sort_values(["date", "realtime_start"])

    def as_of(self, sid: str, d) -> pd.Series:
        df = self.t[sid]
        t = pd.Timestamp(d)
        m = (df["realtime_start"] <= t) & (df["realtime_end"].isna() | (df["realtime_end"] >= t))
        s = df.loc[m].drop_duplicates("date", keep="last").set_index("date")["value"].dropna()
        return s.sort_index()

    def publicacion(self, sid: str, periodo) -> pd.Timestamp | None:
        df = self.t[sid]
        r = df.loc[(df["date"] == pd.Timestamp(periodo)) & df["value"].notna() & ~df["clip"], "realtime_start"]
        return r.min() if len(r) else None

    def ultimo_publicado(self, sid: str, d) -> pd.Timestamp | None:
        s = self.as_of(sid, d)
        return s.index.max() if len(s) else None

    def diaria(self, sid: str, hasta) -> pd.Series:
        s = self.d.get(sid, pd.Series(dtype=float))
        return s[s.index <= pd.Timestamp(hasta)]
