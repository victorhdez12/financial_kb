"""CFTC Commitments of Traders -> curated/cftc_cot (docs/DATA_CONTRACT.md).

    .venv/bin/python -m src.ingest.cftc_cot

Three report families, futures-only, "All" (old+other crop years) columns, from the public
historical-compressed zips on cftc.gov (full history + yearly files; current year re-downloaded
when older than 20 h):
* Legacy (deacot*, 1986+):      non-commercial / commercial net positions + open interest
* TFF (fut_fin_txt, 2006+):     dealer, asset manager, leveraged-funds net positions (financials)
* Disaggregated (fut_disagg_txt, 2006+): managed money, producer/merchant net (commodities)

date = the report "as of" date (Tuesday). The report is published the following Friday 15:30 ET,
i.e. 3 calendar days later (4 if a Monday holiday delays it): use date + 3d as the earliest
point-in-time availability. Contracts are identified by CFTC contract-market code; the
exchange/name changes inside a code (e.g. IMM -> CME) are NOT a splice (same code, same series).
Raw zips are kept intact in $FIN_DATA_ROOT/raw/cftc_cot/.
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, log, raw_dir

SOURCE = "cftc_cot"
HIST = "https://www.cftc.gov/files/dea/history/{}.zip"
LICENSE = "CFTC public data, free to use (US government work); cite CFTC Commitments of Traders"
FIRST_YEAR_YEARLY = 2017
THIS_YEAR = pd.Timestamp.today().year

# code -> (slug, label, family) ; family: fin (TFF) | com (Disaggregated)
MARKETS = {
    "13874A": ("sp500_emini", "E-mini S&P 500", "fin"),
    "209742": ("nasdaq_mini", "Nasdaq-100 mini", "fin"),
    "042601": ("ust2y", "UST 2-year note", "fin"),
    "044601": ("ust5y", "UST 5-year note", "fin"),
    "043602": ("ust10y", "UST 10-year note", "fin"),
    "020601": ("ust_bond", "UST bond (30y)", "fin"),
    "043607": ("ultra10y", "Ultra 10-year T-note", "fin"),
    "020604": ("ultra_bond", "Ultra T-bond", "fin"),
    "132741": ("eurodollar", "3-month Eurodollar", "fin"),
    "134741": ("sofr3m", "3-month SOFR", "fin"),
    "099741": ("eur", "Euro FX", "fin"),
    "097741": ("jpy", "Japanese yen", "fin"),
    "096742": ("gbp", "British pound", "fin"),
    "092741": ("chf", "Swiss franc", "fin"),
    "098662": ("dxy", "US Dollar Index", "fin"),
    "1170E1": ("vix", "VIX futures", "fin"),
    "088691": ("gold", "Gold (COMEX)", "com"),
    "084691": ("silver", "Silver (COMEX)", "com"),
    "085692": ("copper", "Copper (COMEX)", "com"),
    "067651": ("wti", "WTI crude oil (NYMEX)", "com"),
    "023651": ("natgas", "Natural gas (NYMEX)", "com"),
}
CAT = {"fin": "markets", "com": "commodities"}
CAT_OVERRIDE = {"ust2y": "rates", "ust5y": "rates", "ust10y": "rates", "ust_bond": "rates",
                "ultra10y": "rates", "ultra_bond": "rates", "eurodollar": "rates", "sofr3m": "rates",
                "eur": "fx", "jpy": "fx", "gbp": "fx", "chf": "fx", "dxy": "fx",
                "gold": "gold"}

FILES = {  # family -> (historic zips, yearly prefix)
    "legacy": (["deacot1986_2016"], "deacot{}"),
    "tff": (["fin_fut_txt_2006_2016"], "fut_fin_txt_{}"),
    "disagg": (["fut_disagg_txt_hist_2006_2016"], "fut_disagg_txt_{}"),
}


def norm(c: str) -> str:
    return re.sub(r"[^a-z0-9]", "", c.lower())


def load_family(fam: str) -> pd.DataFrame:
    hist, yearly = FILES[fam]
    names = hist + [yearly.format(y) for y in range(FIRST_YEAR_YEARLY, THIS_YEAR + 1)]
    frames = []
    rd = raw_dir(SOURCE)
    for n in names:
        age = 24 * 365 if not n.endswith(str(THIS_YEAR)) else 20
        try:
            z = download(HIST.format(n), rd / f"{n}.zip", "zip", min_age_hours=age)
        except Exception as e:  # noqa: BLE001
            log.warning("CFTC %s unavailable: %s", n, e)
            continue
        with zipfile.ZipFile(z) as zf:
            member = zf.namelist()[0]
            d = pd.read_csv(io.BytesIO(zf.read(member)), dtype=str, low_memory=False,
                            encoding="latin1")
        d.columns = [norm(c) for c in d.columns]
        d = d.rename(columns={d.columns[2]: "date", d.columns[3]: "code"})
        d["date"] = pd.to_datetime(d["date"].str.replace(r"\s+12:00:00\s*AM", "", regex=True),
                                   format="mixed", errors="coerce")
        d["code"] = d["code"].str.strip()
        d = d[d["code"].isin(MARKETS)]
        # 099741 was the ECU before the euro (1986 rows): not the same contract
        d = d[~d[d.columns[0]].str.contains("EUROPEAN CURRENCY UNIT", case=False, na=False)]
        frames.append(d)
    out = pd.concat(frames, ignore_index=True)
    # one row per (code, date); a duplicate would double count -> keep last (newest file)
    n0 = len(out)
    out = out.drop_duplicates(["code", "date"], keep="last")
    if n0 != len(out):
        log.info("%s: dropped %d duplicate (code,date) rows", fam, n0 - len(out))
    return out


def num(d: pd.DataFrame, col: str) -> pd.Series:
    if col not in d.columns:
        raise KeyError(col)
    return pd.to_numeric(d[col], errors="coerce")


def run() -> pd.DataFrame:
    cw = CatalogWriter(SOURCE, url="https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
                       license=LICENSE)
    lag = ("date = as-of Tuesday; published Friday 15:30 ET (about +3 days): not known before "
           "date+3d. Futures only.")
    today = pd.Timestamp.today().normalize()

    def add(sid, s, label, what, units, fam, slug, note=""):
        s = s[s.index <= today]
        cat = CAT_OVERRIDE.get(slug, CAT[fam])
        cw.add(sid, s, name=f"CFTC {label}: {what}", category=cat, frequency="W", units=units,
               country="US", transform_notes=f"{lag} {note}".strip())

    # --- Legacy
    d = load_family("legacy")
    for code, (slug, label, fam) in MARKETS.items():
        x = d[d.code == code].sort_values("date").set_index("date")
        if x.empty:
            continue
        ncl, ncs = num(x, "noncommercialpositionslongall"), num(x, "noncommercialpositionsshortall")
        cl, cs = num(x, "commercialpositionslongall"), num(x, "commercialpositionsshortall")
        oi = num(x, "openinterestall")
        add(f"cftc_{slug}_oi", oi, label, "open interest (legacy, all)", "contracts", fam, slug)
        add(f"cftc_{slug}_nc_net", ncl - ncs, label, "non-commercial net position (long-short, legacy)",
            "contracts", fam, slug, "Non-commercial net excludes spreading.")
        add(f"cftc_{slug}_nc_net_pct_oi", 100 * (ncl - ncs) / oi.where(oi > 0), label,
            "non-commercial net as % of open interest", "% of OI", fam, slug)
        add(f"cftc_{slug}_comm_net", cl - cs, label, "commercial net position (long-short, legacy)",
            "contracts", fam, slug)
    # --- TFF
    d = load_family("tff")
    for code, (slug, label, fam) in MARKETS.items():
        if fam != "fin":
            continue
        x = d[d.code == code].sort_values("date").set_index("date")
        if x.empty:
            continue
        oi = num(x, "openinterestall")
        for key, col, what in (("lev", "levmoney", "leveraged funds"), ("am", "assetmgr", "asset managers"),
                               ("dealer", "dealer", "dealers/intermediaries")):
            net = num(x, f"{col}positionslongall") - num(x, f"{col}positionsshortall")
            add(f"cftc_{slug}_{key}_net", net, label, f"{what} net position (long-short, TFF)",
                "contracts", fam, slug, "TFF starts 2006-06-13; spreading excluded.")
            if key == "lev":
                add(f"cftc_{slug}_lev_net_pct_oi", 100 * net / oi.where(oi > 0), label,
                    "leveraged funds net as % of open interest (TFF)", "% of OI", fam, slug)
    # --- Disaggregated
    d = load_family("disagg")
    for code, (slug, label, fam) in MARKETS.items():
        if fam != "com":
            continue
        x = d[d.code == code].sort_values("date").set_index("date")
        if x.empty:
            continue
        oi = num(x, "openinterestall")
        mm = num(x, "mmoneypositionslongall") - num(x, "mmoneypositionsshortall")
        pm = num(x, "prodmercpositionslongall") - num(x, "prodmercpositionsshortall")
        add(f"cftc_{slug}_mm_net", mm, label, "managed money net position (long-short, disaggregated)",
            "contracts", fam, slug, "Disaggregated starts 2006-06-13; spreading excluded.")
        add(f"cftc_{slug}_mm_net_pct_oi", 100 * mm / oi.where(oi > 0), label,
            "managed money net as % of open interest", "% of OI", fam, slug)
        add(f"cftc_{slug}_prodmerc_net", pm, label, "producer/merchant net position (long-short, disaggregated)",
            "contracts", fam, slug)
    return cw.close()


if __name__ == "__main__":
    run()
