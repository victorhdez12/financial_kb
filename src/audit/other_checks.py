"""Warehouse freshness, events, point-in-time/vintage coverage, look-ahead series and licences."""
from __future__ import annotations

import re

import duckdb
import pandas as pd

from src.audit.common import (CURATED, DATA_ROOT, FROZEN_SOURCES, Finding, all_catalogs, fmt, mtime,
                              parquet_files, sources, warehouse_path)
from src.regime.features import FEATURES

EVENT_COLS = ["event_id", "name", "type", "country", "start_date", "end_date", "severity", "source", "url", "notes"]
EVENT_TYPES = {"war", "banking_crisis", "currency_crisis", "sovereign_default", "market_crash", "recession",
               "pandemic", "oil_shock", "policy", "credit_event", "inflation_crisis"}  # contrato 2026-10-12
NC_RX = re.compile(r"non-?commercial|\bNC\b|BY-NC", re.I)
# forward RATES (yield-curve forwards) are fine; forward RETURNS / projections are look-ahead
LOOKAHEAD_RX = re.compile(r"fwd\d|forward \d+y annualized|forward[- ]looking|look-?ahead|projection|proyecci|"
                          r"future return|most[_ ]recent|latest vintage", re.I)


# ---------------------------------------------------------------- warehouse
def warehouse(today: pd.Timestamp) -> tuple[list[Finding], dict]:
    out: list[Finding] = []
    info: dict = {}
    con = duckdb.connect(str(warehouse_path()), read_only=True)
    try:
        built = con.execute("select max(built_at) from build_log").fetchone()[0]
        built = pd.Timestamp(built).tz_convert(None) if getattr(built, "tzinfo", None) else pd.Timestamp(built)
        info["built_at"] = str(built)
        info["tables"] = {t: con.execute(f'select count(*) from "{t}"').fetchone()[0]
                          for (t,) in con.execute("select table_name from information_schema.tables").fetchall()}
        wh = con.execute("""select source, series_id, count(*) as n, max(date) as last_date
                            from observations group by 1, 2""").df()
        rm = con.execute("select (select max(date) from regime_monthly), (select max(built_at) from regime_meta)").fetchone() \
            if "regime_monthly" in info["tables"] else None
        info["regime_last"] = str(rm[0]) if rm else None
    finally:
        con.close()
    info["by_source"] = []
    for src in sources():
        files = parquet_files(src)
        if not files:
            continue
        newest = max(mtime(p) for p in files + [CURATED / src / "_catalog.csv"] if p.exists())
        loaded = wh[wh["source"] == src]
        stems = {p.stem for p in files}
        missing = sorted(stems - set(loaded["series_id"]))
        gone = sorted(set(loaded["series_id"]) - stems)
        info["by_source"].append({"source": src, "files": len(files), "in_warehouse": len(set(loaded["series_id"])),
                                  "missing": len(missing), "newest_file": str(newest.floor("s")),
                                  "stale": newest > built})
        if missing:
            whole = len(missing) == len(stems)
            out.append(Finding("warehouse.no_cargada", "ALTA" if whole else "MEDIA", src,
                               "*" if whole else ",".join(missing[:5]),
                               f"{len(missing)}/{len(stems)} series del curated no están en el warehouse "
                               f"(build {fmt(built)} {built.strftime('%H:%M')}, fichero más nuevo {newest.floor('s')})",
                               {"ejemplos": ",".join(missing[:8])},
                               "make warehouse && make regime (reconstrucción completa e idempotente)"))
        if gone:
            out.append(Finding("warehouse.huerfana", "BAJA", src, ",".join(gone[:5]),
                               f"{len(gone)} series en el warehouse que ya no existen en curated"))
        # loaded but stale: row-count / last-date drift per series
        if len(loaded):
            drift = []
            for p in files:
                r = loaded[loaded["series_id"] == p.stem]
                if r.empty:
                    continue
                n = pd.read_parquet(p, columns=["date"]).shape[0]
                if n != int(r["n"].iloc[0]):
                    drift.append((p.stem, int(r["n"].iloc[0]), n))
            if drift:
                out.append(Finding("warehouse.desfasada", "MEDIA", src, ",".join(d[0] for d in drift[:5]),
                                   f"{len(drift)} series con nº de filas distinto entre parquet y warehouse",
                                   {"ejemplos": "; ".join(f"{a}: wh={b} parquet={c}" for a, b, c in drift[:5])},
                                   "reconstruir el warehouse"))
    return out, info


# ---------------------------------------------------------------- events
def events() -> list[Finding]:
    out = []
    for p in sorted((DATA_ROOT / "events").glob("*.parquet")):
        d = pd.read_parquet(p)
        miss = [c for c in EVENT_COLS if c not in d]
        if miss:
            out.append(Finding("eventos.columnas", "ALTA", "events", p.stem, f"faltan columnas {miss}"))
            continue
        dup = d["event_id"].duplicated().sum()
        if dup:
            out.append(Finding("eventos.id_duplicado", "MEDIA", "events", p.stem, f"{dup} event_id duplicados",
                               {"ejemplos": ",".join(d.loc[d['event_id'].duplicated(), 'event_id'].astype(str)[:5])}))
        bad_t = d.loc[~d["type"].isin(EVENT_TYPES), "type"].value_counts()
        if len(bad_t):
            out.append(Finding("eventos.tipo", "BAJA", "events", p.stem,
                               f"tipos fuera del contrato: {bad_t.to_dict()}",
                               fix="añadir el tipo al contrato o mapearlo"))
        s, e = pd.to_datetime(d["start_date"], errors="coerce"), pd.to_datetime(d["end_date"], errors="coerce")
        if s.isna().any():
            out.append(Finding("eventos.fecha", "MEDIA", "events", p.stem, f"{int(s.isna().sum())} start_date nulos"))
        inv = (e < s).sum()
        if inv:
            out.append(Finding("eventos.fecha", "MEDIA", "events", p.stem, f"{inv} eventos con end_date < start_date",
                               {"ejemplos": ",".join(d.loc[e < s, 'event_id'].astype(str)[:5])}))
    return out


# ---------------------------------------------------------------- vintages / look-ahead / licences
def vintages_lookahead(today: pd.Timestamp) -> tuple[list[Finding], pd.DataFrame]:
    out, rows = [], []
    alfred = {p.stem: p for p in parquet_files("alfred")}
    con = duckdb.connect(str(warehouse_path()), read_only=True)
    wh_alfred = {r[0] for r in con.execute(
        "select distinct series_id from observations where source='alfred'").fetchall()}
    con.close()
    for f in FEATURES:
        sid = f.sids[0]
        r = {"feature": f.name, "series_id": sid, "vintage_flag": f.vintage, "alfred_file": sid in alfred,
             "alfred_en_warehouse": sid in wh_alfred}
        if sid in alfred:
            v = pd.read_parquet(alfred[sid], columns=["realtime_start"])
            r["primera_vintage"] = fmt(pd.to_datetime(v["realtime_start"]).min())
            r["n_vintages"] = int(v["realtime_start"].nunique())
        rows.append(r)
        if f.vintage and sid not in alfred:
            out.append(Finding("pit.sin_vintages", "ALTA", "alfred", sid,
                               f"feature {f.name} marcada vintage=True pero no hay ALFRED: usa datos revisados (look-ahead de revisiones)",
                               fix="añadir a src/ingest/alfred_vintages.py y reconstruir"))
        elif f.vintage and sid not in wh_alfred:
            out.append(Finding("pit.vintages_no_cargadas", "ALTA", "alfred", sid,
                               f"feature {f.name}: hay fichero ALFRED pero no está en el warehouse", fix="make warehouse"))
        elif f.vintage and r.get("primera_vintage", "9999") > "1960-01-01":
            out.append(Finding("pit.cobertura_parcial", "MEDIA", "alfred", sid,
                               f"feature {f.name}: ALFRED empieza en {r['primera_vintage']}; antes usa la serie revisada",
                               fix="empalmar con rtdsm (Philadelphia RTDSM) para vintages anteriores"))
    cat = all_catalogs()
    for r in cat.to_dict("records"):
        txt = f"{r.get('name', '')} {r.get('transform_notes', '')} {r.get('series_id', '')}"
        if LOOKAHEAD_RX.search(str(txt)):
            out.append(Finding("pit.lookahead", "ALTA" if "fwd" in str(r["series_id"]) else "MEDIA",
                               r["_dir"], r["series_id"],
                               f"posible look-ahead: '{str(r.get('name'))[:80]}'",
                               fix="añadir columna `predictor_ok`/`lookahead` al catálogo y bloquearla en features.py"))
    return out, pd.DataFrame(rows)


def licences() -> tuple[list[Finding], pd.DataFrame]:
    cat = all_catalogs()
    cat["license"] = cat["license"].fillna("")
    lic = cat.groupby(["_dir", "license"]).size().reset_index(name="n")
    out = []
    for r in lic.to_dict("records"):
        if NC_RX.search(r["license"]):
            out.append(Finding("licencia.no_comercial", "INFO", r["_dir"], "*",
                               f"{r['n']} series con licencia no comercial: {r['license'][:140]}",
                               fix="mantener solo uso personal/investigación; no redistribuir derivados"))
        if not r["license"].strip():
            out.append(Finding("licencia.vacia", "MEDIA", r["_dir"], "*", f"{r['n']} series sin licencia"))
    return out, lic


def new_dirs(known: set[str]) -> list[dict]:
    """Quick pass over curated dirs that appeared/changed (files vs catalog, schema readable)."""
    rows = []
    for src in sources():
        files = parquet_files(src)
        catp = CURATED / src / "_catalog.csv"
        ncat = len(pd.read_csv(catp)) if catp.exists() else 0
        newest = max([mtime(p) for p in files] + ([mtime(catp)] if catp.exists() else []), default=None)
        rows.append({"source": src, "nuevo": src not in known, "parquets": len(files), "filas_catalogo": ncat,
                     "ultimo_cambio": str(newest.floor("s")) if newest is not None else "",
                     "en_curso": (ncat != len(files)) or not catp.exists() or len(files) == 0,
                     "congelada": src in FROZEN_SOURCES})
    return rows
