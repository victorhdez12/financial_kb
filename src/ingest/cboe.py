"""CBOE volatility / skew / put-call data -> curated/cboe (docs/DATA_CONTRACT.md).

    .venv/bin/python -m src.ingest.cboe

Sources (public, no key):
* cdn.cboe.com/api/global/us_indices/daily_prices/<INDEX>_History.csv  (daily; close used)
* cdn.cboe.com/resources/options/volume_and_call_put_ratios/*.csv     (put/call archives,
  frozen at 2019-10-04) spliced with
* cdn.cboe.com/data/us/options/market_statistics/daily/<YYYY-MM-DD>_daily_options (JSON per
  trading day, 2019-10-07 -> today; cached in raw/cboe/pc_daily/, incremental).
VIX3M history on CBOE starts 2009-09-18; the FRED VXVCLS series (fred_us) goes back to 2007-12.
Raw files are kept intact in $FIN_DATA_ROOT/raw/cboe/.
"""
from __future__ import annotations

import io
import json
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

from src.ingest._extlong_common import CatalogWriter, UA, download, log, raw_dir

SOURCE = "cboe"
BASE = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{}_History.csv"
PC = "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/{}.csv"
DAILY = "https://cdn.cboe.com/data/us/options/market_statistics/daily/{}_daily_options"
LICENSE = ("CBOE Global Markets delayed/historical data, free public download; personal research "
           "use, redistribution not permitted without CBOE consent")

INDICES = {  # file -> (series_id, name, category, note)
    "VIX3M": ("cboe_vix3m", "CBOE 3-Month Volatility Index (VIX3M, ex-VXV), close", "markets",
              "CBOE file starts 2009-09-18; FRED VXVCLS (fred_us) covers 2007-12 onward"),
    "VIX6M": ("cboe_vix6m", "CBOE 6-Month Volatility Index (VIX6M), close", "markets", ""),
    "VIX9D": ("cboe_vix9d", "CBOE 9-Day Volatility Index (VIX9D), close", "markets", ""),
    "VIX1D": ("cboe_vix1d", "CBOE 1-Day Volatility Index (VIX1D), close", "markets", ""),
    "VVIX": ("cboe_vvix", "CBOE VVIX (volatility of VIX), close", "markets",
             "first two obs of the CBOE file (2006-03-06 71.73, 2006-03-15 15.71) look like "
             "vendor start-up glitches and are kept as published"),
    "SKEW": ("cboe_skew", "CBOE SKEW Index, close", "markets", ""),
    "VXN": ("cboe_vxn", "CBOE Nasdaq-100 Volatility Index (VXN), close", "markets", ""),
    "RVX": ("cboe_rvx", "CBOE Russell 2000 Volatility Index (RVX), close", "markets", ""),
    "OVX": ("cboe_ovx", "CBOE Crude Oil Volatility Index (OVX), close", "commodities", ""),
    "GVZ": ("cboe_gvz", "CBOE Gold Volatility Index (GVZ), close", "commodities", ""),
    "VXEEM": ("cboe_vxeem", "CBOE Emerging Markets ETF Volatility Index (VXEEM), close", "markets", ""),
    "VXTLT": ("cboe_vxtlt", "CBOE 20+ Year Treasury Bond ETF Volatility Index (VXTLT), close", "rates", ""),
    "COR1M": ("cboe_cor1m", "CBOE 1-Month Implied Correlation Index (COR1M), close", "markets", ""),
    "COR3M": ("cboe_cor3m", "CBOE 3-Month Implied Correlation Index (COR3M), close", "markets", ""),
}

# product -> (ratio series, name, [archive csvs oldest first, current csv], daily-json name)
PCS = {
    "total": ("cboe_pc_total", "CBOE total put/call volume ratio", ["totalpcarchive", "totalpc"],
              "TOTAL PUT/CALL RATIO"),
    "equity": ("cboe_pc_equity", "CBOE equity options put/call volume ratio", ["equitypcarchive", "equitypc"],
               "EQUITY PUT/CALL RATIO"),
    "index": ("cboe_pc_index", "CBOE index options put/call volume ratio", ["indexpcarchive", "indexpc"],
              "INDEX PUT/CALL RATIO"),
    "etp": ("cboe_pc_etp", "CBOE exchange-traded-products put/call volume ratio", ["etppc"],
            "EXCHANGE TRADED PRODUCTS PUT/CALL RATIO"),
    "vix": ("cboe_pc_vix", "CBOE VIX options put/call volume ratio", ["vixpc"],
            "CBOE VOLATILITY INDEX (VIX) PUT/CALL RATIO"),
    "spx": ("cboe_pc_spx", "CBOE SPX (+SPXW from 2019-10) options put/call volume ratio", ["spxpc"],
            "SPX + SPXW PUT/CALL RATIO"),
}
CSV_END = pd.Timestamp("2019-10-04")


def _read_index(path) -> pd.Series:
    d = pd.read_csv(path)
    col = "CLOSE" if "CLOSE" in d.columns else d.columns[1]
    d["DATE"] = pd.to_datetime(d["DATE"], format="%m/%d/%Y")
    s = d.set_index("DATE")[col].astype(float)
    return s.mask(s <= 0)


def _read_pc_csv(path) -> pd.Series:
    txt = path.read_bytes().decode("latin1")
    lines = txt.splitlines()
    i = next(k for k, l in enumerate(lines) if l.lower().lstrip(", ").startswith(("date", "trade_date")))
    d = pd.read_csv(io.StringIO("\n".join(lines[i:])), skipinitialspace=True)
    d.columns = [c.strip() for c in d.columns]
    ratio = [c for c in d.columns if "ratio" in c.lower()][0]
    dt = pd.to_datetime(d.iloc[:, 0], format="%m/%d/%Y", errors="coerce")
    s = pd.Series(pd.to_numeric(d[ratio], errors="coerce").values, index=dt).dropna()
    return s[s.index.notna()]


def _daily_json(day: pd.Timestamp, cache) -> dict | None:
    f = cache / f"{day:%Y-%m-%d}.json"
    if f.exists():
        return json.loads(f.read_text()) if f.stat().st_size > 2 else None
    try:
        r = requests.get(DAILY.format(f"{day:%Y-%m-%d}"), headers={"User-Agent": UA}, timeout=60)
    except Exception as e:  # noqa: BLE001
        log.warning("daily pc %s: %s", day.date(), e)
        return None
    if r.status_code in (403, 404):  # holiday/weekend: no file
        f.write_text("")
        return None
    r.raise_for_status()
    f.write_text(r.text)
    return r.json()


def _daily_pc(cache) -> pd.DataFrame:
    days = pd.bdate_range(CSV_END + pd.Timedelta(days=1), pd.Timestamp.today().normalize())
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda d: _daily_json(d, cache), days))
    rows = []
    for d, j in zip(days, res):
        if not j:
            continue
        rec = {r["name"]: pd.to_numeric(r["value"], errors="coerce") for r in j.get("ratios", [])}
        rec["date"] = d
        rows.append(rec)
    return pd.DataFrame(rows).set_index("date")


def run() -> pd.DataFrame:
    raw = raw_dir(SOURCE)
    cw = CatalogWriter(SOURCE, url="https://www.cboe.com/tradable_products/vix/vix_historical_data/",
                       license=LICENSE)
    for key, (sid, name, cat, note) in INDICES.items():
        try:
            p = download(BASE.format(key), raw / f"{key}_History.csv", "csv", min_age_hours=20)
        except Exception as e:  # noqa: BLE001
            log.warning("%s unavailable: %s", key, e)
            continue
        cw.add(sid, _read_index(p), name=name, category=cat, frequency="D", units="index points",
               country="US", transform_notes="daily close of CBOE history file" + (f"; {note}" if note else ""),
               url=BASE.format(key))
    cache = raw / "pc_daily"
    cache.mkdir(exist_ok=True)
    daily = _daily_pc(cache)
    for key, (sid, name, files, jname) in PCS.items():
        parts = []
        for f in files:
            try:
                p = download(PC.format(f), raw / f"{f}.csv", "csv", min_age_hours=20 * 24)
            except Exception as e:  # noqa: BLE001
                log.warning("%s unavailable: %s", f, e)
                continue
            parts.append(_read_pc_csv(p))
        s = pd.Series(dtype=float)
        for part in parts:  # later files win on overlap
            s = part.combine_first(s) if s.empty else part.combine_first(s)
        s = s[s.index <= CSV_END]
        if jname in daily:
            s = pd.concat([s, daily[jname].dropna()])
        note = ("archive CSVs (frozen 2019-10-04) spliced with Cboe daily market-statistics JSON "
                "from 2019-10-07; no data 2019-10-05/06; ratio = put volume / call volume")
        if key == "spx":
            note += "; CSV definition is SPX only, JSON is SPX+SPXW (possible level break)"
        cw.add(sid, s, name=name, category="markets", frequency="D", units="ratio", country="US",
               transform_notes=note, url=PC.format(files[-1]))
    return cw.close()


if __name__ == "__main__":
    run()
