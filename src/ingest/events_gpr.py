"""Caldara-Iacoviello Geopolitical Risk (GPR) index -> curated/gpr/.

Source: https://www.matteoiacoviello.com/gpr.htm
  - data_gpr_export.xls       monthly: GPR (1985-, 10 newspapers), GPRH (1900-, 3 newspapers),
                              threats/acts split, and country GPR (GPRC_xxx 1985-, GPRHC_xxx 1900-)
  - data_gpr_daily_recent.xls daily GPRD 1985- (with acts/threats)

Run: .venv/bin/python -m src.ingest.events_gpr
"""
from __future__ import annotations

import pandas as pd

from src.ingest._events_common import curated_dir, download, log, raw_dir

SOURCE = "gpr"
PAGE = "https://www.matteoiacoviello.com/gpr.htm"
URL_M = "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls"
URL_D = "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls"
LICENSE = ("Free for research with citation: Caldara, D. & Iacoviello, M. (2022), "
           "'Measuring Geopolitical Risk', AER 112(4)")
CATALOG_COLS = ["series_id", "source", "name", "category", "frequency", "units", "country",
                "start", "end", "transform_notes", "url", "license"]

MAIN = {
    "GPR": ("gpr", "Geopolitical Risk Index (recent, 10 newspapers)", "Index 1985-2019=100"),
    "GPRT": ("gpr_threats", "GPR Threats (recent)", "Index 1985-2019=100"),
    "GPRA": ("gpr_acts", "GPR Acts (recent)", "Index 1985-2019=100"),
    "GPRH": ("gpr_hist", "Historical GPR Index (3 newspapers, 1900-)", "Index 1900-2019=100"),
    "GPRHT": ("gpr_hist_threats", "Historical GPR Threats", "Index 1900-2019=100"),
    "GPRHA": ("gpr_hist_acts", "Historical GPR Acts", "Index 1900-2019=100"),
    "SHARE_GPR": ("gpr_share", "Share of GPR articles (recent)", "% of articles"),
    "SHARE_GPRH": ("gpr_hist_share", "Share of GPR articles (historical)", "% of articles"),
}
DAILY = {
    "GPRD": ("gpr_daily", "Daily Geopolitical Risk Index", "Index 1985-2019=100"),
    "GPRD_ACT": ("gpr_daily_acts", "Daily GPR Acts", "Index 1985-2019=100"),
    "GPRD_THREAT": ("gpr_daily_threats", "Daily GPR Threats", "Index 1985-2019=100"),
}


def main() -> None:
    raw = raw_dir(SOURCE)
    fm = download(URL_M, raw / "data_gpr_export.xls", "xls")
    fd = download(URL_D, raw / "data_gpr_daily_recent.xls", "xls")
    out = curated_dir(SOURCE)
    rows: list[dict] = []

    def put(sid: str, s: pd.Series, name: str, freq: str, units: str, country: str, notes: str,
            url: str) -> None:
        s = pd.to_numeric(s, errors="coerce").dropna()
        if s.empty:
            log.warning("empty %s", sid)
            return
        df = pd.DataFrame({"date": s.index.date, "value": s.values.astype("float64"),
                           "series_id": sid, "source": SOURCE})
        df["series_id"] = df["series_id"].astype("string")
        df["source"] = df["source"].astype("string")
        df.to_parquet(out / f"{sid}.parquet", index=False)
        rows.append({"series_id": sid, "source": SOURCE, "name": name, "category": "geopolitics",
                     "frequency": freq, "units": units, "country": country,
                     "start": str(s.index.min().date()), "end": str(s.index.max().date()),
                     "transform_notes": notes, "url": url, "license": LICENSE})

    m = pd.read_excel(fm)
    m["month"] = pd.to_datetime(m["month"])
    m = m.set_index("month").sort_index()
    labels = dict(zip(m["var_name"].dropna(), m["var_label"].dropna()))
    for col, (sid, name, units) in MAIN.items():
        put(sid, m[col], name, "M", units, "WLD", "as published", URL_M)
    for col in m.columns:
        if col.startswith(("GPRC_", "GPRHC_")):
            cc = col.split("_", 1)[1]
            hist = col.startswith("GPRHC_")
            sid = f"gpr_{'hist_' if hist else ''}country_{cc.lower()}"
            name = labels.get(col, col) + (" — historical (3 newspapers)" if hist else "")
            put(sid, m[col], name, "M", "% of articles mentioning GPR and the country", cc,
                "as published; country GPR = share of all newspaper articles (not rebased)", URL_M)

    d = pd.read_excel(fd)
    d["date"] = pd.to_datetime(d["DAY"].astype(int).astype(str), format="%Y%m%d")
    d = d.set_index("date").sort_index()
    for col, (sid, name, units) in DAILY.items():
        put(sid, d[col], name, "D", units, "WLD", "as published (raw daily, no smoothing)", URL_D)

    cat = pd.DataFrame(rows, columns=CATALOG_COLS).sort_values("series_id")
    keep = set(cat.series_id)
    for f in out.glob("*.parquet"):
        if f.stem not in keep:
            f.unlink()
    cat.to_csv(out / "_catalog.csv", index=False)
    log.info("gpr: %d series; GPRH %s..%s; GPRD last %s", len(cat),
             cat.loc[cat.series_id == "gpr_hist", "start"].item(),
             cat.loc[cat.series_id == "gpr_hist", "end"].item(),
             cat.loc[cat.series_id == "gpr_daily", "end"].item())


if __name__ == "__main__":
    main()
