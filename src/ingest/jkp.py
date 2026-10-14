"""Jensen-Kelly-Pedersen (JKP) Global Factor Data (https://jkpfactors.com), public downloads.

Run: .venv/bin/python -m src.ingest.jkp
Raw:     $FIN_DATA_ROOT/raw/jkp/[loc]_[theme]_[freq]_[weight].zip   (S3, direct, no registration)
Curated: $FIN_DATA_ROOT/curated/jkp/jkp_<loc>_<theme>_<m|d>.parquet

What: 13 characteristic themes (long-short, 'high minus low' direction already aligned so that
positive = historical premium) + the market, weighting vw_cap (capped value-weighted: stocks
capped at the NYSE 80th size percentile), all-stocks universe, excess returns in USD.
Units: JKP gives decimals (0.01 = 1 %); stored in PERCENT (x100), as French/AQR here.
Dates: month-end -> first of month; daily keep the trading day.
Not downloaded (still available on the site): the 153 single factors ('all_factors'), ew/vw
weighting, size-bucket universes, portfolios, industry data, 90+ other countries.
"""
from __future__ import annotations

import io
import zipfile

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, log, raw_dir

SOURCE = "jkp"
S3 = "https://jkpfactors-data.s3.amazonaws.com/public/"
PAGE = "https://jkpfactors.com/data"
LICENSE = ("Data: CC BY-NC 4.0 (jkpfactors.com footer): free, attribution required "
           "(cite Jensen, Kelly & Pedersen 2023, 'Is There a Replication Crisis in Finance?', J. Finance 78(5)), "
           "NON-COMMERCIAL use only. Code: MIT.")
# Europe is not a region on the site; major European countries are used instead.
LOCATIONS = {
    "usa": ("United States", "USA"), "world": ("World", "WLD"), "world_ex_us": ("World ex US", "WLDXUS"),
    "developed": ("Developed markets", "ADV"), "emerging": ("Emerging markets", "EM"),
    "esp": ("Spain", "ESP"), "deu": ("Germany", "DEU"), "fra": ("France", "FRA"),
    "gbr": ("United Kingdom", "GBR"), "ita": ("Italy", "ITA"), "nld": ("Netherlands", "NLD"),
    "che": ("Switzerland", "CHE"),
}
FREQS = {"monthly": "M", "daily": "D"}
WEIGHT = "vw_cap"
THEME_LABEL = {"mkt": "Market (excess return)"}


def main() -> None:
    cw = CatalogWriter(SOURCE, url=PAGE, license=LICENSE)
    for loc, (label, iso) in LOCATIONS.items():
        for freq, f1 in FREQS.items():
            for theme in ("all_themes", "mkt"):
                stem = f"[{loc}]_[{theme}]_[{freq}]_[{WEIGHT}]"
                dest = raw_dir(SOURCE) / f"{stem}.zip"
                url = S3 + stem.replace("[", "%5B").replace("]", "%5D") + ".zip"
                try:
                    download(url, dest, "zip", min_age_hours=12)
                except Exception as e:  # noqa: BLE001
                    if not dest.exists():
                        log.warning("GAP %s: %s", stem, str(e)[:120])
                        continue
                with zipfile.ZipFile(dest) as z:
                    df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), dtype={"name": str})
                df["date"] = pd.to_datetime(df["date"])
                if f1 == "M":
                    df["date"] = df["date"].dt.to_period("M").dt.to_timestamp()
                for name, g in df.groupby("name"):
                    s = pd.Series(pd.to_numeric(g["ret"], errors="coerce").values * 100, index=g["date"])
                    is_mkt = name == "mkt"
                    cw.add(f"jkp_{loc}_{name}_{f1.lower()}", s,
                           name=f"JKP {label}: {'market excess return' if is_mkt else name + ' theme (long-short)'}, "
                                f"{WEIGHT}, {freq}",
                           category="equity_returns", frequency=f1, units="percent per period (USD excess return)",
                           country=iso,
                           transform_notes=(f"{stem}.zip; decimal x100 -> percent; vw_cap = value-weighted, size capped "
                                            "at NYSE 80th pct; all stocks; month-end -> first of month; "
                                            "theme = cluster of characteristics (JKP 2023), sign aligned to the "
                                            "expected premium; rebuilt in full at each release"),
                           url=PAGE)
    cat = cw.close()
    print(cat.groupby("frequency").agg(n=("series_id", "size"), start=("start", "min"), end=("end", "max")))
    print(cat.groupby("country").agg(n=("series_id", "size"), start=("start", "min"), end=("end", "max")))


if __name__ == "__main__":
    main()
