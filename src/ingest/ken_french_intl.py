"""Kenneth R. French Data Library, part 2: US DAILY factors and INTERNATIONAL factors.

Complements src/ingest/ken_french.py (US monthly/annual, left untouched). Own source_id so the
stale-file cleanup of one script never deletes the other's parquets.

Run: .venv/bin/python -m src.ingest.ken_french_intl
Raw:     $FIN_DATA_ROOT/raw/ken_french_intl/*.zip
Curated: $FIN_DATA_ROOT/curated/ken_french_intl/ffx_<region>_<factor>_<m|d>.parquet

Units: PERCENT per period (1.5 = 1.5 %), identical to ken_french (ff_*_m). Not converted.
Monthly files hold a monthly block and an annual block; only the monthly block is stored.
Daily files hold a single block. Missing (-99.99/-999) -> NaN.
Dates: first day of month (monthly) or the trading day (daily).
3-factor files (2x3 sorts differ slightly from the 5-factor files) only contribute smb3/hml3.
"""
from __future__ import annotations

import re
import zipfile

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, log, raw_dir

SOURCE = "ken_french_intl"
BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
LIB = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"
LICENSE = ("Kenneth R. French Data Library, (c) Eugene F. Fama and Kenneth R. French; free for "
           "research/personal use with citation; site says reproduction in part or whole needs "
           "permission of K. French/DFA -> do not redistribute. Underlying data: CRSP (US), Bloomberg (intl).")

# region id -> (label, country code, {kind: file stem})
REGIONS: dict[str, tuple[str, str, dict[str, str]]] = {
    "us": ("United States", "USA", {
        "f3_d": "F-F_Research_Data_Factors_daily_CSV",
        "f5_d": "F-F_Research_Data_5_Factors_2x3_daily_CSV",
        "mom_d": "F-F_Momentum_Factor_daily_CSV",
    }),
}
for rid, label, stem, ccode in [
    ("dev", "Developed", "Developed", "DEV"),
    ("devxus", "Developed ex US", "Developed_ex_US", "DEVXUS"),
    ("eur", "Europe", "Europe", "EUR"),
    ("jpn", "Japan", "Japan", "JPN"),
    ("apxj", "Asia Pacific ex Japan", "Asia_Pacific_ex_Japan", "APXJ"),
    ("na", "North America", "North_America", "NAMER"),
]:
    REGIONS[rid] = (label, ccode, {
        "f5_m": f"{stem}_5_Factors_CSV", "mom_m": f"{stem}_Mom_Factor_CSV",
        "f3_m": f"{stem}_3_Factors_CSV",
        "f5_d": f"{stem}_5_Factors_Daily_CSV", "mom_d": f"{stem}_Mom_Factor_Daily_CSV",
        "f3_d": f"{stem}_3_Factors_Daily_CSV",
    })
# Emerging Markets: monthly only (no daily files, no 3-factor file on the site)
REGIONS["em"] = ("Emerging Markets", "EM", {
    "f5_m": "Emerging_5_Factors_CSV", "mom_m": "Emerging_MOM_Factor_CSV"})
# US monthly stays in ken_french (ff_*_m, ff5_*_m, ff_mom_m): not duplicated here.

NAMES = {
    "mkt_rf": "Market excess return (Mkt-RF)", "smb": "Size (SMB)", "hml": "Value (HML)",
    "rmw": "Profitability (RMW)", "cma": "Investment (CMA)", "rf": "Risk-free rate (1m T-bill)",
    "mom": "Momentum (UMD/WML)", "smb3": "Size (SMB), 3-factor sorts", "hml3": "Value (HML), 3-factor sorts",
}


def sections(text: str) -> list[tuple[str, pd.DataFrame]]:
    """Like ken_french.sections but accepts 8-digit (daily) dates. A block starts at a header line
    beginning with ',' and continues while lines start with a 4-8 digit date."""
    lines = text.splitlines()
    out, i = [], 0
    while i < len(lines):
        if lines[i].lstrip().startswith(","):
            cols = [c.strip() for c in lines[i].split(",")[1:]]
            rows = []
            i += 1
            while i < len(lines) and re.match(r"^\s*\d{4,8}\s*,", lines[i]):
                rows.append([p.strip() for p in lines[i].split(",")][: len(cols) + 1])
                i += 1
            out.append(("", pd.DataFrame(rows, columns=["date"] + cols)))
        else:
            i += 1
    return out


def key_of(col: str) -> str:
    k = re.sub(r"[^a-z0-9]+", "_", col.lower()).strip("_")
    return {"wml": "mom", "umd": "mom"}.get(k, k)


def idx_of(dates: pd.Series) -> pd.DatetimeIndex:
    d = dates.astype(str).str.strip()
    return pd.to_datetime(d + ("01" if len(d.iloc[0]) == 6 else ""), format="%Y%m%d")


def main() -> None:
    cw = CatalogWriter(SOURCE, url=LIB, license=LICENSE)
    for rid, (label, ccode, files) in REGIONS.items():
        for kind, stem in files.items():
            freq = kind[-1]  # m | d
            dest = raw_dir(SOURCE) / f"{stem}.zip"
            try:
                download(BASE + stem + ".zip", dest, "zip")
            except Exception as e:  # noqa: BLE001
                if not dest.exists():
                    log.error("skip %s: %s", stem, e)
                    continue
                log.warning("%s download failed (%s); cached", stem, e)
            with zipfile.ZipFile(dest) as z:
                text = z.read(z.namelist()[0]).decode("latin-1")
            m = re.search(r"(\d{6}) (CRSP|Bloomberg) database", text)
            vint = f"{m.group(2)} vintage {m.group(1)}" if m else ""
            want = 6 if freq == "m" else 8
            block = next((df for _, df in sections(text)
                          if len(df) and df["date"].str.strip().str.len().eq(want).all()), None)
            if block is None:
                log.warning("%s: no %s block", stem, freq)
                continue
            idx = idx_of(block["date"])
            for col in block.columns[1:]:
                k = key_of(col)
                if kind.startswith("f3") and k in ("smb", "hml"):
                    k += "3"
                if rid == "us" and k in ("mkt_rf", "rf") and kind.startswith("f5"):
                    continue  # US: Mkt-RF/RF come from the 3-factor file (history from 1926)
                if kind.startswith("f3") and k in ("mkt_rf", "rf") and rid != "us":
                    continue  # identical to the 5-factor file
                sid = f"ffx_{rid}_{k}_{freq}"
                vals = pd.to_numeric(block[col].str.strip(), errors="coerce")
                vals = vals.mask(vals.isin([-99.99, -999.0]))
                cw.add(sid, pd.Series(vals.values, index=idx),
                       name=f"Fama-French {label}: {NAMES.get(k, col)}, {'monthly' if freq == 'm' else 'daily'}",
                       category="rates" if k == "rf" else "equity_returns", frequency=freq.upper(),
                       units="percent per period", country=ccode,
                       transform_notes=(f"{stem}.zip; {vint}; percent (not fraction), same as ken_french; "
                                        "-99.99 -> NaN; USD; annual block dropped"),
                       url=BASE + stem + ".zip")
    cat = cw.close()
    print(cat[["series_id", "frequency", "start", "end"]].to_string(index=False))


if __name__ == "__main__":
    main()
