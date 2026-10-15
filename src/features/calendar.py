"""Calendario de publicación point-in-time (ficha: docs/models/pit_calendar.md).

Fichero máquina: research/pit_calendar.yaml (una entrada por serie del warehouse). Retardos medidos con
las vintages ALFRED/RTDSM: research/pit_calendar_measured.csv, que genera

    .venv/bin/python -m src.features.calendar            # mide y escribe el csv

Reglas de disponibilidad (fecha de publicación de la observación con fecha de referencia d):
1. Si alguna serie de `proxies` (la propia serie o otra del mismo comunicado, p. ej. CPILFESL → CPIAUCSL)
   tiene vintages que contienen d:
   - d aparece por primera vez DESPUÉS de la primera vintage del archivo → publicación = ese
     realtime_start (exacta, medida);
   - d ya está en la primera vintage del archivo (carga inicial: se publicó antes), o aparece más de 200
     días después de su periodo (historia añadida al archivo más tarde) → publicación =
     mín(calendario(d), primera vintage que lo contiene).
   Con varias proxies se toma el mínimo (todas son cotas superiores de la fecha real).
2. Si d es anterior a todo lo que cubren las proxies (o no hay proxies) → calendario(d) = ancla(d) +
   retardo conservador de la época (`retardo_dias`), documentado como medido o como supuesto.
3. Si d es posterior a lo que cubren las proxies → no disponible (las vintages aún no lo recogen).
   Suelo: una serie anclada al fin de periodo nunca se publica antes del día siguiente a ese fin.
4. La disponibilidad es monótona: una observación solo cuenta como disponible cuando también lo están
   todas las anteriores (cummax), porque las transformaciones usan historia.

Ninguna regla depende de datos posteriores a la fecha de decisión: con el warehouse truncado en t
(vintages con realtime_start ≤ t) la disponibilidad en t no cambia (tests/test_pit_leaks.py).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.regime.asof import period_end
from src.warehouse import db

REPO = Path(__file__).resolve().parents[2]
CAL_PATH = REPO / "research" / "pit_calendar.yaml"
MEASURED_PATH = REPO / "research" / "pit_calendar_measured.csv"
NEVER = pd.Timestamp("2262-01-01")
# épocas para medir cambios del calendario (fecha de referencia de la observación)
EPOCHS = {"<1980": ("1900-01-01", "1979-12-31"), "1980-1999": ("1980-01-01", "1999-12-31"),
          "2000-2012": ("2000-01-01", "2012-12-31"), "2013+": ("2013-01-01", "2100-01-01")}
# retardos fuera de este rango no son primeras publicaciones (fechas añadidas por revisiones de base, etc.)
MEASURE_RANGE = (-40, 200)


@dataclass(frozen=True)
class CalEntry:
    sid: str
    freq: str                                   # D, W, M, Q, A
    anchor: str                                 # fin_periodo | inicio_periodo
    lags: tuple[tuple[pd.Timestamp, int], ...]  # (desde fecha de referencia, días), ordenado
    proxies: tuple[str, ...]                    # vintages que fechan la publicación
    vintages: tuple[str, ...]                   # fuentes de vintage para el modo `vintage` (prioridad)
    supuesto: bool                              # True si algún tramo del retardo no está medido
    fuente: str
    publicacion: str
    supuestos: tuple[bool, ...] = ()            # por tramo de `lags`: True = supuesto, False = medido

    def anchor_dates(self, idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
        if self.anchor == "inicio_periodo" or self.freq in ("D", "W"):
            return pd.DatetimeIndex(idx)
        return pd.DatetimeIndex(period_end(pd.DatetimeIndex(idx), self.freq))

    def lag_days(self, idx: pd.DatetimeIndex) -> np.ndarray:
        idx = pd.DatetimeIndex(idx)
        out = np.full(len(idx), self.lags[0][1], dtype="int64")
        for since, days in self.lags[1:]:
            out[idx >= since] = days
        return out

    def calendar_dates(self, idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
        return self.anchor_dates(idx) + pd.to_timedelta(self.lag_days(idx), unit="D")


def load_calendar(path: Path = CAL_PATH, variant: str | None = None) -> dict[str, CalEntry]:
    """Calendario de publicación. `variant='prudente'` usa `retardo_dias_prudente` donde exista (sensibilidad
    preregistrada; p. ej. Filadelfia 1968-90 con el dato de t−1)."""
    raw = yaml.safe_load(Path(path).read_text())
    out = {}
    for sid, e in raw["series"].items():
        tramos = e.get("retardo_dias_prudente") if variant == "prudente" and e.get("retardo_dias_prudente") \
            else e["retardo_dias"]
        tramos = sorted(tramos, key=lambda x: pd.Timestamp(str(x["desde"])))
        lags = tuple((pd.Timestamp(str(x["desde"])), int(x["dias"])) for x in tramos)
        sup = tuple(bool(x.get("supuesto", e.get("supuesto", True))) for x in tramos)
        out[sid] = CalEntry(sid=sid, freq=e["frecuencia"], anchor=e.get("ancla", "fin_periodo"), lags=lags,
                            proxies=tuple(e.get("proxies_publicacion") or ()),
                            vintages=tuple(e.get("vintages") or ()),
                            supuesto=any(sup), fuente=str(e.get("fuente", "")),
                            publicacion=str(e.get("publicacion", "")), supuestos=sup)
    return out


# ------------------------------------------------------------------ vintages
class VintageSet:
    """Vintages de una serie (formato ALFRED de cambios: una fila por fecha y realtime_start en que cambia
    el valor; NaN = la observación se retira). `snapshot(t)` = la serie tal como se publicó en t."""

    def __init__(self, v: pd.DataFrame, sid: str = ""):
        v = v[["date", "value", "realtime_start"]].copy()
        v["date"] = pd.to_datetime(v["date"])
        v["realtime_start"] = pd.to_datetime(v["realtime_start"])
        self.sid = sid
        self.v = v.sort_values(["realtime_start", "date"], kind="stable").reset_index(drop=True)
        self.rs = self.v["realtime_start"].to_numpy()
        self.start = self.v["realtime_start"].min() if len(v) else NEVER
        ok = self.v[self.v["value"].notna()]
        self.first_rs = ok.groupby("date")["realtime_start"].min().sort_index()
        self.min_date = self.first_rs.index.min() if len(ok) else NEVER
        self.max_date = self.first_rs.index.max() if len(ok) else None

    def __len__(self) -> int:
        return len(self.v)

    def snapshot(self, t: pd.Timestamp, since: pd.Timestamp | None = None) -> pd.Series:
        k = int(np.searchsorted(self.rs, np.datetime64(t), side="right"))
        sub = self.v.iloc[:k]
        if since is not None:
            sub = sub[sub["date"] >= since]
        sub = sub.drop_duplicates("date", keep="last")
        sub = sub[sub["value"].notna()].sort_values("date")
        return pd.Series(sub["value"].to_numpy(float), index=pd.DatetimeIndex(sub["date"]), name=self.sid)


def publication_dates(entry: CalEntry, dates: pd.DatetimeIndex, proxies: list[VintageSet]) -> pd.Series:
    """Fecha de publicación (primera disponibilidad) de cada fecha de referencia, reglas 1-3 del módulo.
    Sin la regla 4 (monotonía): ver `availability`."""
    dates = pd.DatetimeIndex(dates)
    cal = pd.Series(entry.calendar_dates(dates), index=dates)
    proxies = [p for p in proxies if p is not None and len(p)]
    if not proxies:
        return cal
    best = pd.Series(NEVER, index=dates)
    min_date = min(p.min_date for p in proxies)
    anchor = pd.Series(entry.anchor_dates(dates), index=dates)
    for p in proxies:
        fr = p.first_rs.reindex(dates)
        # carga inicial del archivo o historia añadida después (ALFRED añadió en 1994 el IPC de 1947-71):
        # no es una primera publicación → calendario, acotado por la fecha en que ya consta publicada
        backfill = (fr - anchor).dt.days > MEASURE_RANGE[1]
        bulk = (fr.eq(p.start) | backfill).fillna(False).astype(bool)
        a = fr.copy()
        a[bulk] = cal[bulk].where(cal[bulk] <= fr[bulk], fr[bulk])
        best = best.where(a.isna() | (best <= a), a)
    before = dates < min_date
    best[before] = cal[before]
    if entry.anchor == "fin_periodo" and entry.freq in ("M", "Q", "A") and min(d for _, d in entry.lags) >= 0:
        # ALFRED fecha algunos comunicados de empleo de 1961-63 en el último día del mes o antes (ver
        # pit_calendar.md): una serie de fin de periodo nunca cuenta como publicada antes del día siguiente
        floor = pd.Series(entry.anchor_dates(dates) + pd.Timedelta(days=1), index=dates)
        best = best.where(best >= floor, floor)
    return best


def availability(entry: CalEntry, dates: pd.DatetimeIndex, proxies: list[VintageSet]) -> pd.Series:
    """Fecha desde la que la observación d (y todas las anteriores) está publicada (regla 4)."""
    pub = publication_dates(entry, dates, proxies).sort_index()
    return pub.cummax()


# ------------------------------------------------------------------ medición
def first_release_lags(v: VintageSet, freq: str) -> pd.Series:
    """Días entre el fin del periodo de referencia y la primera publicación, para las fechas que aparecen
    después de la carga inicial del archivo de vintages."""
    fr = v.first_rs[v.first_rs > v.start]
    if fr.empty:
        return pd.Series(dtype=float)
    pe = pd.DatetimeIndex(period_end(fr.index, freq)) if freq not in ("D", "W") else fr.index
    lag = pd.Series((fr.to_numpy() - pe.to_numpy()).astype("timedelta64[D]").astype(int), index=fr.index)
    return lag[(lag >= MEASURE_RANGE[0]) & (lag <= MEASURE_RANGE[1])]


def load_vintage_set(con, sid: str, raw: bool = True) -> VintageSet | None:
    """Vintages de `sid` en el warehouse o, si no están y `raw`, en features/raw/alfred."""
    df = con.execute("select date, value, realtime_start from vintages where series_id = ?", [sid]).df()
    if df.empty and raw:
        from src.features import alfred_raw
        df = alfred_raw.load(sid)
        if df is None:
            return None
    return VintageSet(df, sid) if len(df) else None


def measure(con, cal: dict[str, CalEntry]) -> pd.DataFrame:
    rows = []
    vids = sorted({p for e in cal.values() for p in (*e.proxies, *e.vintages)})
    freq = {sid: e.freq for sid, e in cal.items()}
    for sid in vids:
        v = load_vintage_set(con, sid)
        if v is None:
            continue
        lag = first_release_lags(v, freq.get(sid, "M"))
        for ep, (a, b) in {"todas": ("1900-01-01", "2100-01-01"), **EPOCHS}.items():
            x = lag[(lag.index >= a) & (lag.index <= b)]
            if len(x) < 6:
                continue
            rows.append({"series_id": sid, "epoca": ep, "n": len(x), "desde": f"{x.index.min():%Y-%m}",
                         "hasta": f"{x.index.max():%Y-%m}", "mediana": float(np.median(x)),
                         "p90": float(np.percentile(x, 90)), "max": int(x.max()), "min": int(x.min()),
                         "archivo_desde": f"{v.start:%Y-%m-%d}"})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(MEASURED_PATH))
    a = ap.parse_args()
    cal = load_calendar()
    con = db.connect()
    df = measure(con, cal)
    df.to_csv(a.out, index=False, float_format="%.1f")
    print(df.to_string(index=False))
    print(f"→ {a.out}")


if __name__ == "__main__":
    main()
