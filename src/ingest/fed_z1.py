"""Federal Reserve Z.1 Financial Accounts of the United States -> curated/fed_z1.

    .venv/bin/python -m src.ingest.fed_z1 [--refresh]

Raw (untouched) in raw/fed_z1/:
* FRB_Z1_csv.zip       'all CSV' long format (1 row per observation, 3.3 GB unzipped; kept as zip,
                       not parsed: the per-table files below carry the same numbers)
* z1_csv_files.zip     one wide CSV per table (csv/<table>.csv, header = series ids)
  + data_dictionary (inside the same zip) and z1_table_mapping.csv (new table name -> old L.*/B.*/D.*)
Curated: every QUARTERLY LEVEL series ("amounts outstanding end of period", NSA, market value
or SA) found in the data dictionary = balance sheets of all sectors (B.*/L.* in the old
numbering, e.g. S1M.b, S11.b ...), instrument tables (F.*/L.* levels) and D.3 debt by sector
(LA* series). ~1,935 quarterly series, millions of USD. Flows (FA/FU), revaluations and other changes
are NOT curated (they remain in the raw zip). Series that already exist in curated/fred or
curated/fred_us as BOGZ1<id> are skipped (same data; reported in raw/fed_z1/_run_summary.json).
Dates: 'YYYY:Qn' -> first day of the quarter. 'ND'/'NA'/blank -> NaN.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import zipfile

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, data_root, download, log, raw_dir

SOURCE = "fed_z1"
BASE = "https://www.federalreserve.gov/releases/z1/"
LICENSE = "Federal Reserve Board - US government work, public domain"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    refresh = ap.parse_args().refresh
    raw = raw_dir(SOURCE)
    age = 0 if refresh else 20
    download(BASE + "data/FRB_Z1_csv.zip", raw / "FRB_Z1_csv.zip", "zip", min_age_hours=age)
    zp = download(BASE + "current/z1_csv_files.zip", raw / "z1_csv_files.zip", "zip", min_age_hours=age)
    download(BASE + "current/z1_table_mapping.csv", raw / "z1_table_mapping.csv", "csv", min_age_hours=age)
    mapping = {r["new"]: (r["old"], r["title"]) for r in csv.DictReader(
        open(raw / "z1_table_mapping.csv", encoding="utf-8-sig"))}

    existing = set()
    for s in ("fred", "fred_us"):
        p = data_root() / "curated" / s / "_catalog.csv"
        if p.exists():
            existing |= set(pd.read_csv(p, usecols=["series_id"])["series_id"])

    # content-level overlap: curated/fred(_us) Q series with same last date, last value and n_obs
    sig: dict[tuple, str] = {}
    for src in ("fred", "fred_us"):
        cp = data_root() / "curated" / src / "_catalog.csv"
        if not cp.exists():
            continue
        c = pd.read_csv(cp, usecols=["series_id", "frequency", "end"])
        for sid in c[(c["frequency"] == "Q") & (c["end"] >= "2025-01-01")]["series_id"]:
            d = pd.read_parquet(data_root() / "curated" / src / f"{sid}.parquet", columns=["date", "value"]).dropna()
            if len(d):
                sig[(str(d["date"].iloc[-1]), float(d["value"].iloc[-1]), len(d))] = sid
    zf = zipfile.ZipFile(zp)
    # data dictionary: series \t description \t line \t table title \t units
    meta: dict[str, dict] = {}
    for n in zf.namelist():
        if not n.startswith("data_dictionary/") or not n.endswith(".txt"):
            continue
        tbl = n.split("/")[-1][:-4]  # e.g. S1M_b
        for line in zf.read(n).decode("utf-8-sig", "replace").splitlines():
            f = line.split("\t")
            if len(f) < 5 or not f[4].startswith("Millions of dollars; amounts outstanding"):
                continue
            sid = f[0]
            if not sid.endswith(".Q"):  # .A = annual Integrated Macro Accounts matrices (same codes as .Q)
                continue
            if sid not in meta:  # first table where the series appears
                meta[sid] = {"desc": f[1], "table": tbl, "title": f[3], "units": f[4]}
    log.info("level series in dictionary: %d", len(meta))

    cw = CatalogWriter(SOURCE, url=BASE, license=LICENSE)
    by_table: dict[str, list[str]] = {}
    for sid, m in meta.items():
        by_table.setdefault(m["table"], []).append(sid)
    skipped, missing, nobs = [], [], 0
    for tbl, sids in sorted(by_table.items()):
        name = f"csv/{tbl}.csv"
        if name not in zf.namelist():
            missing += sids
            continue
        df = pd.read_csv(io.BytesIO(zf.read(name)), dtype=str)
        dates = pd.PeriodIndex(df["date"].str.replace(":", "", regex=False), freq="Q").to_timestamp()
        for sid in sids:
            if sid not in df.columns:
                missing.append(sid)
                continue
            code = sid.split(".")[0]
            if f"BOGZ1{code}Q" in existing:
                skipped.append(sid)
                continue
            s = pd.Series(pd.to_numeric(df[sid], errors="coerce").values, index=dates)
            d = s.dropna()
            k = (str(d.index[-1].date()), float(d.iloc[-1]), len(d)) if len(d) else None
            if k in sig:  # identical series already curated under a FRED id (e.g. TODNS)
                skipped.append(f"{sid}=={sig[k]}")
                continue
            m = meta[sid]
            tkey = tbl.replace("_", ".", 1)
            old = mapping.get(tkey, ("", ""))[0]
            mv = "market value" in m["units"]
            n = cw.add(f"z1_{code}_q", s, name=m["desc"], category="credit", frequency="Q", units="Millions of USD", country="US",
                       transform_notes=(f"Z.1 table {m['title']} (csv {tbl}; old name {old or 'n/a'}); "
                                        f"{m['units']}; 'YYYY:Qn' -> quarter start date; ND/NA -> NaN; "
                                        f"{'market-value series (LM)' if mv else 'level series'}; "
                                        f"FRED equivalent BOGZ1{code}Q"),
                       url=BASE + "current/z1_csv_files.zip")
            nobs += n
    cat = cw.close()
    (raw / "_run_summary.json").write_text(json.dumps({
        "run_utc": pd.Timestamp.now("UTC").isoformat(), "n_series": len(cat), "n_obs": nobs,
        "skipped_in_fred_or_fred_us": skipped, "missing_in_wide_csv": missing}, indent=2))
    log.info("fed_z1: %d series, %d obs, %d skipped (BOGZ1 already in FRED), %d missing",
             len(cat), nobs, len(skipped), len(missing))


if __name__ == "__main__":
    main()
