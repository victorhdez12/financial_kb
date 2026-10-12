"""Per-series checks on the curated layer: contract, catalog, time integrity and values.

Every curated parquet is read once; the function returns findings plus a per-series profile
(first/last date, frequency, n obs) that the other modules reuse.
"""
from __future__ import annotations

import re
from collections import defaultdict

import numpy as np
import pandas as pd

from src.audit.common import (CATEGORIES, CONTRACT_COLS, FREQS, FROZEN_SOURCES, OPTIONAL_COLS, PERIOD,
                              REQUIRED_CATALOG, STALE_DAYS, Finding, expected_index, fmt, infer_freq,
                              load_catalog, parquet_files, period_end, read_series, schema_of, sources)

LEVEL_UNITS = re.compile(r"index|=100|usd|\$|dollar|gbp|£|persons|thousands$|millions|billions|"
                         r"troy|fine oz|/mt|/kg|/bbl|/mmbtu|per share|oz silver", re.I)
NOT_LEVEL = re.compile(r"%|percent|pct|change|return|fraction|\bpp\b|rate|spread|dummy|balance|"
                       r"gap|deficit|surplus|net|flow|diff", re.I)
NAME_NOT_LEVEL = re.compile(r"\bchange\b|return|spread|balance|account|activity index|diffusion|"
                            r"\bnet\b", re.I)
NO_LEVEL_CATS = {"fiscal", "rates", "equity_returns", "bond_returns", "financial_conditions", "crisis"}
# NBER-style legacy sentinel values that sometimes survive as data
SENTINELS = [1e-37, -99.99, -999.0, -9999.0, 9999.0, -99.0]


def _is_level(cat_row: dict) -> bool:
    units = str(cat_row.get("units") or "")
    name = str(cat_row.get("name") or "")
    if cat_row.get("category") in NO_LEVEL_CATS:
        return False
    if NOT_LEVEL.search(units) or NAME_NOT_LEVEL.search(name):
        return False
    return bool(LEVEL_UNITS.search(units))


def _longest_run(v: np.ndarray) -> tuple[int, int]:
    """(length, start position) of the longest run of identical consecutive values."""
    if len(v) == 0:
        return 0, 0
    change = np.r_[True, v[1:] != v[:-1]]
    starts = np.flatnonzero(change)
    lens = np.diff(np.r_[starts, len(v)])
    i = int(np.argmax(lens))
    return int(lens[i]), int(starts[i])


def _robust_z(x: pd.Series) -> pd.Series:
    med = x.median()
    mad = (x - med).abs().median() * 1.4826
    if not np.isfinite(mad) or mad == 0:
        return pd.Series(np.nan, index=x.index)
    return (x - med) / mad


def check_series(src: str, path, cat: dict | None, today: pd.Timestamp, out: list[Finding]) -> dict:
    sid_file = path.stem
    add = lambda chk, sev, det, ev=None, fix="": out.append(  # noqa: E731
        Finding(chk, sev, src, sid_file, det, ev or {}, fix))
    prof = {"source": src, "series_id": sid_file, "ok_read": False}

    # ---------------- contract: schema
    try:
        sch = schema_of(path)
        df = read_series(path)
    except Exception as exc:  # corrupt / half-written
        add("contrato.lectura", "ALTA", f"parquet ilegible: {exc}", fix="re-ejecutar el ingest de la fuente")
        return prof
    prof["ok_read"] = True
    missing = [c for c in CONTRACT_COLS if c not in sch]
    if missing:
        add("contrato.columnas", "ALTA", f"faltan columnas {missing}", {"schema": sch},
            "añadir columnas en src/ingest/<source>.py")
    for c, t in {**CONTRACT_COLS, **OPTIONAL_COLS}.items():
        if c in sch and t not in sch[c]:
            add("contrato.tipos", "MEDIA", f"columna {c} es {sch[c]}, contrato pide {t}", fix="castear en el ingest")
    extra = sorted(set(sch) - set(CONTRACT_COLS) - set(OPTIONAL_COLS))
    is_vintage = "realtime_start" in df
    if extra:
        add("contrato.columnas_extra", "INFO", f"columnas fuera de contrato {extra} (el warehouse las ignora)",
            fix="documentar en DATA_CONTRACT.md (realtime_end) o eliminarlas")
    if "series_id" in df:
        ids = df["series_id"].dropna().unique()
        if len(ids) != 1 or ids[0] != sid_file:
            add("contrato.series_id", "ALTA", f"series_id interno {list(ids)[:3]} != nombre de fichero",
                fix="alinear series_id y nombre de fichero")
    if "source" in df:
        srcs = df["source"].dropna().unique()
        if len(srcs) != 1 or srcs[0] != src:
            add("contrato.source", "MEDIA", f"source interno {list(srcs)[:3]} != directorio {src}")

    # ---------------- catalog
    if cat is None:
        add("catalogo.sin_fila", "ALTA", "parquet sin fila en _catalog.csv",
            fix=f"regenerar curated/{src}/_catalog.csv")
        cat = {}
    else:
        empty = [k for k in REQUIRED_CATALOG if not str(cat.get(k) or "").strip()]
        if empty:
            add("catalogo.campos_vacios", "MEDIA", f"campos obligatorios vacíos: {empty}",
                fix=f"rellenar en el ingest de {src}")
        if cat.get("frequency") and cat["frequency"] not in FREQS:
            add("catalogo.frequency", "MEDIA", f"frequency='{cat['frequency']}' fuera de D/W/M/Q/A")
        if cat.get("category") and cat["category"] not in CATEGORIES:
            add("catalogo.category", "BAJA", f"category='{cat['category']}' fuera de la lista del contrato")

    if df.empty or "date" not in df or "value" not in df:
        add("valores.vacia", "ALTA", "serie sin filas")
        return prof
    if df["date"].isna().any():
        add("tiempo.fecha_nula", "MEDIA", f"{int(df['date'].isna().sum())} fechas no parseables")
    base = df.dropna(subset=["date"])
    if is_vintage:
        # vintages: one current value per date (realtime_end null) is the comparable 'latest' series
        dups = base.duplicated(["date", "realtime_start"]).sum()
        if dups:
            add("tiempo.duplicados", "ALTA", f"{dups} filas duplicadas (date, realtime_start)")
        if "realtime_end" in base:
            base = base[base["realtime_end"].isna()]
        else:
            base = base.sort_values("realtime_start").groupby("date", as_index=False).last()
    else:
        dups = base["date"].duplicated(keep=False)
        if dups.any():
            dd = base.loc[dups, "date"]
            add("tiempo.duplicados", "ALTA", f"{int(dups.sum())} filas con fecha duplicada",
                {"ejemplos": ",".join(fmt(x) for x in dd.unique()[:5])},
                "deduplicar en el ingest (keep='last')")
            base = base.drop_duplicates("date", keep="last")
    s = base.set_index("date")["value"].sort_index().astype(float)
    nn = s.dropna()
    prof.update(n=len(s), n_valid=len(nn), first=nn.index.min() if len(nn) else None,
                last=nn.index.max() if len(nn) else None, vintage=is_vintage)
    if nn.empty:
        add("valores.todo_nan", "ALTA", "todos los valores son NaN")
        return prof

    fcat = cat.get("frequency")
    finf = infer_freq(nn.index)
    freq = fcat if fcat in FREQS else finf
    prof["freq"] = freq
    if fcat in FREQS and finf != "?" and fcat != finf and not (fcat == "A" and finf in "AQ"):
        add("catalogo.frecuencia_inconsistente", "MEDIA",
            f"catálogo dice {fcat}, la mediana de espaciado sugiere {finf}")

    # catalog start/end vs data
    for k, real in (("start", nn.index.min()), ("end", nn.index.max())):
        cv = pd.to_datetime(cat.get(k), errors="coerce")
        if cat and pd.notna(cv) and abs((cv - real).days) > 40 and freq in "DWM":
            add("catalogo.rango", "BAJA", f"catálogo {k}={fmt(cv)} pero datos {fmt(real)}",
                fix="recalcular start/end del catálogo al escribir")

    # ---------------- time integrity
    fut = nn.index[nn.index > today]
    if len(fut):
        add("tiempo.fechas_futuras", "MEDIA", f"{len(fut)} observaciones con fecha > {fmt(today)}",
            {"primera": fmt(fut.min()), "ultima": fmt(fut.max())},
            "filtrar date <= hoy o marcar como proyección en el catálogo")
    if freq in PERIOD:
        idx = nn.index
        bad = {"M": idx.day != 1, "Q": (idx.day != 1) | ~idx.month.isin([1, 4, 7, 10]),
               "A": (idx.day != 1) | (idx.month != 1)}[freq]
        if bad.any():
            add("tiempo.alineacion", "MEDIA", f"{int(bad.sum())}/{len(idx)} fechas no alineadas al inicio de periodo ({freq})",
                {"ejemplos": ",".join(fmt(x) for x in idx[bad][:4])},
                "normalizar date a inicio de periodo en el ingest")
        else:
            exp = expected_index(idx.min(), idx.max(), freq)
            miss = exp.difference(idx)
            if len(miss):
                recent = miss[miss >= today - pd.DateOffset(years=10)]
                sev = "MEDIA" if len(recent) and src not in FROZEN_SOURCES else "BAJA"
                explicit_nan = int(s.loc[s.index.isin(miss)].isna().sum())
                add("tiempo.huecos", sev,
                    f"{len(miss)} periodos ausentes entre {fmt(idx.min())} y {fmt(idx.max())} "
                    f"({explicit_nan} como NaN explícito, {len(miss) - explicit_nan} sin fila)",
                    {"ejemplos": ",".join(fmt(x) for x in miss[:6]), "recientes": ",".join(fmt(x) for x in recent[:6])},
                    "no rellenar: reindexar a calendario completo antes de cualquier shift (ver hallazgo IPC oct-2025)")
            prof["n_missing"] = len(miss)
    elif freq in ("D", "W") and len(nn) > 3:
        gaps = pd.Series(np.diff(nn.index.values).astype("timedelta64[D]").astype(int), index=nn.index[1:])
        lim = 10 if freq == "D" else 15
        big = gaps[gaps > lim]
        if len(big):
            add("tiempo.huecos", "BAJA", f"{len(big)} saltos > {lim} días; máximo {int(big.max())} días",
                {"mayor_hueco_termina": fmt(big.idxmax())})

    # staleness
    pend = period_end(nn.index.max(), freq)
    age = (today - pend).days
    prof["age_days"] = age
    if freq in STALE_DAYS and age > STALE_DAYS[freq]:
        name = str(cat.get("name") or "") + " " + str(cat.get("transform_notes") or "")
        if src in FROZEN_SOURCES:
            pass  # expected; summarised per source in the report
        else:
            disc = bool(re.search(r"discontinu|DISCONTINUED|termina|retirad", name, re.I))
            closed = nn.index.max() < pd.Timestamp("2000-01-01")  # historical series that ended long ago
            add("tiempo.obsoleta", "BAJA" if (disc or closed) else "MEDIA",
                f"último dato {fmt(nn.index.max())} ({age} días tras fin de periodo, freq {freq})"
                + (" — discontinuada" if disc else ""),
                {"ultimo": fmt(nn.index.max())},
                "sustituir por serie viva o marcar discontinued en el catálogo")

    # ---------------- values
    v = nn.values
    if nn.nunique() == 1:
        add("valores.constante", "MEDIA", f"serie constante = {v[0]} en {len(v)} obs")
    else:
        min_run = {"D": 60, "W": 26, "M": 36, "Q": 16, "A": 15}.get(freq, 36)
        run, pos = _longest_run(v)
        if run >= min_run:
            sev = "ALTA" if cat.get("category") in ("gold", "commodities", "markets") else "BAJA"
            add("valores.tramo_constante", sev,
                f"{run} obs consecutivas idénticas = {v[pos]}",
                {"desde": fmt(nn.index[pos]), "hasta": fmt(nn.index[pos + run - 1])},
                "marcar el tramo (precio administrado / interpolado) o excluirlo de cálculos de mercado")
    for sv in SENTINELS:
        hits = np.isclose(v, sv, rtol=0, atol=abs(sv) * 1e-6 if sv else 1e-40)
        if hits.sum() and (sv != -99.0 or hits.sum() > 1):
            add("valores.centinela", "ALTA", f"{int(hits.sum())} valores = {sv} (código de faltante)",
                {"ejemplo": fmt(nn.index[hits][0])}, "convertir a NaN en el ingest")
    level = _is_level(cat)
    prof["level"] = level
    if level:
        z0 = (nn == 0)
        if z0.any():
            add("valores.ceros", "MEDIA", f"{int(z0.sum())} ceros en una serie de nivel/precio ({cat.get('units')})",
                {"ejemplos": ",".join(fmt(x) for x in nn.index[z0][:4])}, "probable faltante codificado como 0 → NaN")
        neg = nn < 0
        if neg.any():
            add("valores.negativos", "MEDIA", f"{int(neg.sum())} negativos en una serie de nivel ({cat.get('units')})",
                {"min": float(nn.min()), "fecha": fmt(nn.idxmin())})
    # jumps: log changes for strictly positive series, differences otherwise
    if len(nn) >= 24:
        pos_ser = (nn > 0).all()
        ch = np.log(nn).diff().dropna() if pos_ser else nn.diff().dropna()
        z = _robust_z(ch)
        if z.notna().any():
            zmax = z.abs().max()
            prof["zmax"] = float(zmax)
            n8 = int((z.abs() > 8).sum())
            if zmax > 8:
                d = z.abs().idxmax()
                prev = nn.loc[:d].iloc[-2]
                sev = "MEDIA" if zmax > 30 else "BAJA"
                add("valores.outlier", sev,
                    f"{n8} cambios con |z robusto|>8; máx |z|={zmax:.1f} en {fmt(d)} ({prev:.6g} → {nn.loc[d]:.6g})",
                    {"fecha": fmt(d), "antes": f"{prev:.6g}", "despues": f"{nn.loc[d]:.6g}"},
                    "verificar contra la fuente; si es error, corregir en el ingest")
        # unit change: persistent jump by ~x10^k
        rate_like = (cat.get("category") in NO_LEVEL_CATS or
                     bool(re.search(r"%|percent|fraction|\bpp\b|per annum|p\.a\.|articles", str(cat.get("units") or ""), re.I)))
        if pos_ser and len(nn) >= 30 and not rate_like:  # near-zero rates make x10 moves meaningless
            r = np.log10(nn).diff()
            for d in r[r.abs() > 0.9].index[:3]:
                i = nn.index.get_loc(d)
                before, after = nn.iloc[max(0, i - 12):i].median(), nn.iloc[i:i + 12].median()
                if before > 0 and abs(np.log10(after / before)) > 0.9:
                    add("valores.cambio_unidades", "MEDIA",
                        f"salto persistente x{after / before:.3g} en {fmt(d)} (mediana 12 antes {before:.4g}, después {after:.4g})",
                        {"fecha": fmt(d)}, "revisar unidades/base en la fuente; reescalar el tramo en el ingest")
    return prof


def run(today: pd.Timestamp) -> tuple[list[Finding], pd.DataFrame]:
    out: list[Finding] = []
    profiles = []
    owners: dict[str, list[str]] = defaultdict(list)
    for src in sources():
        cat = load_catalog(src)
        files = parquet_files(src)
        stems = {p.stem for p in files}
        if "series_id" in cat:
            dupc = cat[cat["series_id"].duplicated()]["series_id"].tolist()
            if dupc:
                out.append(Finding("catalogo.duplicado", "MEDIA", src, ",".join(dupc[:5]),
                                   f"{len(dupc)} series_id repetidos en _catalog.csv"))
            orphan = sorted(set(cat["series_id"].dropna()) - stems)
            for o in orphan:
                out.append(Finding("catalogo.sin_fichero", "MEDIA", src, o, "fila de catálogo sin parquet",
                                   fix=f"eliminar la fila o escribir el parquet en curated/{src}"))
            rows = {r["series_id"]: r for r in cat.to_dict("records")}
        else:
            rows = {}
            out.append(Finding("catalogo.ausente", "ALTA", src, "*", "sin _catalog.csv"))
        for p in files:
            owners[p.stem].append(src)
            profiles.append(check_series(src, p, rows.get(p.stem), today, out))
    # global uniqueness across sources (case-insensitive)
    lower: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for sid, srcs in owners.items():
        for s in srcs:
            lower[sid.lower()].append((s, sid))
    for k, lst in lower.items():
        if len(lst) > 1:
            out.append(Finding("contrato.colision_id", "MEDIA", "+".join(s for s, _ in lst), lst[0][1],
                               f"series_id repetido en {len(lst)} fuentes: {lst}",
                               fix="prefijar por fuente (p. ej. alfred_<id>) o documentar la excepción"))
    return out, pd.DataFrame(profiles)
