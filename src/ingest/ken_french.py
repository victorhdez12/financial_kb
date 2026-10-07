"""Kenneth R. French Data Library: Fama-French factors and industry portfolios.

Run: .venv/bin/python -m src.ingest.ken_french
Raw:     $FIN_DATA_ROOT/raw/ken_french/*.zip
Curated: $FIN_DATA_ROOT/curated/ken_french/ff_*.parquet  (returns in percent per period)
"""
from __future__ import annotations

import io
import re
import zipfile

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, log, raw_dir

SOURCE = "ken_french"
BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
LIB = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"
LICENSE = "Kenneth R. French Data Library; free for research, cite source (returns derived from CRSP)"

# factor files: first monthly (YYYYMM) block and first annual (YYYY) block
FACTOR_BLOCKS = {"__monthly__": ("m", "M", "monthly"), "__annual__": ("a", "A", "annual")}

# file -> (prefix, {section-title regex: (suffix, freq, label)})
FILES = {
    "F-F_Research_Data_Factors_CSV.zip": ("ff3", FACTOR_BLOCKS),
    "F-F_Momentum_Factor_CSV.zip": ("ffmom", FACTOR_BLOCKS),
    "F-F_Research_Data_5_Factors_2x3_CSV.zip": ("ff5", FACTOR_BLOCKS),
    "10_Industry_Portfolios_CSV.zip": ("ind10", {
        r"value weighted returns -- monthly": ("vw_m", "M", "value-weighted monthly"),
        r"equal weighted returns -- monthly": ("ew_m", "M", "equal-weighted monthly"),
        r"value weighted returns -- annual": ("vw_a", "A", "value-weighted annual"),
    }),
    "12_Industry_Portfolios_CSV.zip": ("ind12", {
        r"value weighted returns -- monthly": ("vw_m", "M", "value-weighted monthly"),
        r"equal weighted returns -- monthly": ("ew_m", "M", "equal-weighted monthly"),
        r"value weighted returns -- annual": ("vw_a", "A", "value-weighted annual"),
    }),
}

FACTOR_NAMES = {
    "mkt_rf": ("Market excess return (Mkt-RF)", "equity_returns"),
    "smb": ("Size factor (SMB)", "equity_returns"),
    "hml": ("Value factor (HML)", "equity_returns"),
    "rmw": ("Profitability factor (RMW)", "equity_returns"),
    "cma": ("Investment factor (CMA)", "equity_returns"),
    "rf": ("Risk-free rate (1-month T-bill)", "rates"),
    "mom": ("Momentum factor (UMD)", "equity_returns"),
}


def sections(text: str) -> list[tuple[str, pd.DataFrame]]:
    """Split a French CSV into (title, DataFrame) blocks. A block starts at a header line
    beginning with ',' and continues while lines start with a date (YYYY or YYYYMM)."""
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        if lines[i].startswith(",") or lines[i].lstrip().startswith(","):
            # title = nearest non-empty line above that is not data
            j, title = i - 1, ""
            while j >= 0 and not lines[j].strip():
                j -= 1
            if j >= 0 and not re.match(r"^\s*\d{4}", lines[j]):
                title = lines[j].strip()
            cols = [c.strip() for c in lines[i].split(",")[1:]]
            rows = []
            i += 1
            while i < len(lines) and re.match(r"^\s*\d{4,6}\s*,", lines[i]):
                parts = [p.strip() for p in lines[i].split(",")]
                rows.append(parts[: len(cols) + 1])
                i += 1
            df = pd.DataFrame(rows, columns=["date"] + cols)
            out.append((title, df))
        else:
            i += 1
    return out


def to_index(dates: pd.Series) -> pd.DatetimeIndex:
    d = dates.astype(str)
    if d.str.len().eq(6).all():
        return pd.to_datetime(d + "01", format="%Y%m%d")
    return pd.to_datetime(d + "0101", format="%Y%m%d")


def main() -> None:
    cw = CatalogWriter(SOURCE, url=LIB, license=LICENSE)
    for fname, (prefix, wanted) in FILES.items():
        dest = raw_dir(SOURCE) / fname
        try:
            download(BASE + fname, dest, "zip")
        except Exception as e:  # noqa: BLE001
            if not dest.exists():
                log.error("skip %s: %s", fname, e)
                continue
            log.warning("%s download failed (%s); using cached", fname, e)
        with zipfile.ZipFile(dest) as z:
            text = z.read(z.namelist()[0]).decode("latin-1")
        crsp = re.search(r"(\d{6}) CRSP", text)
        vintage = f"CRSP vintage {crsp.group(1)}" if crsp else ""
        used = set()
        for title, df in sections(text):
            t = title.lower()
            match = None
            is_monthly = df["date"].astype(str).str.len().eq(6).all()
            for pat, spec in wanted.items():
                if spec[0] in used:
                    continue
                if pat == "__monthly__":
                    hit = is_monthly
                elif pat == "__annual__":
                    hit = not is_monthly
                else:
                    hit = re.search(pat, t) is not None
                if hit:
                    match = spec
                    break
            if not match:
                continue
            suffix, freq, label = match
            used.add(suffix)
            idx = to_index(df["date"])
            for col in df.columns[1:]:
                key = re.sub(r"[^a-z0-9]+", "_", col.lower()).strip("_")
                vals = pd.to_numeric(df[col], errors="coerce")
                vals = vals.mask(vals.isin([-99.99, -999.0]))
                s = pd.Series(vals.values, index=idx)
                if prefix.startswith("ind"):
                    sid = f"ff_{prefix}_{key}_{suffix}"
                    name = f"French {prefix[3:]}-industry portfolio {col}, {label} return"
                    cat = "equity_returns"
                else:
                    sid = f"ff5_{key}_{suffix}" if prefix == "ff5" else f"ff_{key}_{suffix}"
                    nm, cat = FACTOR_NAMES.get(key, (col, "equity_returns"))
                    name = f"Fama-French {nm}, {label}"
                cw.add(sid, s, name=name, category=cat, frequency=freq, units="percent per period",
                       country="USA", transform_notes=f"{fname}; {vintage}; -99.99/-999 -> NaN; simple returns in %",
                       url=BASE + fname)
    cat = cw.close()
    print(cat[["series_id", "frequency", "start", "end"]].to_string(index=False))


if __name__ == "__main__":
    main()
