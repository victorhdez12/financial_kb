"""Gold price, longest available history, plus spliced monthly USD series.

Sources (all public, no login):
  - MeasuringWorth "Gold Prices and the Ratio to the Price of Silver" (annual):
      New York market price USD 1791-present, U.S. official price 1786-present,
      London market price (GBP 1718-1949, USD 1950-present), British official price 1257-1945,
      gold/silver ratio 1687-present.
  - World Bank Pink Sheet gold (monthly avg, USD/troy oz, London-based), 1960-present.
  - datahub.io core/gold-prices monthly (Timothy Green annual 1833-1959 repeated monthly
      + World Bank from 1960) - kept as a cross-check.
Spliced series gold_usd_monthly:
  1791-01 .. 1959-12  MeasuringWorth New York market price (annual avg, repeated each month)
  1960-01 .. latest   World Bank Pink Sheet monthly average
  gold_usd_monthly_flag: 1 where the value is an annual figure repeated, 0 for true monthly.

Run: .venv/bin/python -m src.ingest.gold
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from src.ingest import wb_pinksheet
from src.ingest._extlong_common import UA, CatalogWriter, download, log, raw_dir

SOURCE = "gold"
MW_URL = "https://www.measuringworth.com/datasets/gold/result.php"
MW_LICENSE = ("MeasuringWorth (Officer & Williamson); free for non-commercial research use with citation "
              "'Lawrence H. Officer and Samuel H. Williamson, The Price of Gold, 1257-Present, MeasuringWorth'")
DH_URL = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"
DH_LICENSE = "ODC-PDDL-1.0 (datahub.io core/gold-prices)"
WB_LICENSE = wb_pinksheet.LICENSE


def fetch_measuringworth() -> Path:
    dest = raw_dir(SOURCE) / "measuringworth_gold.html"
    form = {"london": "on", "goldsilver": "on", "newyork": "on", "us": "on", "British": "on",
            "year_source": "1257", "year_result": str(date.today().year)}
    try:
        r = requests.post(MW_URL, data=form, headers={"User-Agent": UA}, timeout=120)
        r.raise_for_status()
        if "New York Market Price" not in r.text or r.text.count("<tr>") < 100:
            raise ValueError("MeasuringWorth response has no data table")
        dest.write_text(r.text, encoding="utf-8")
        log.info("downloaded MeasuringWorth gold table (%d bytes)", len(r.content))
    except Exception as e:  # noqa: BLE001
        if not dest.exists():
            raise
        log.warning("MeasuringWorth failed (%s); using cached html", e)
    return dest


def parse_measuringworth(path: Path) -> pd.DataFrame:
    html = path.read_text(encoding="utf-8")
    rows = re.findall(r"<tr><td>(\d{4})</td>(.*?)</tr>", html, flags=re.S)
    recs = []
    for yr, rest in rows:
        cells = [re.sub(r"<[^>]+>|&pound;|&#36;|\$|,|\s", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", rest, re.S)]
        recs.append([int(yr)] + cells)
    cols = ["year", "british_official_gbp", "us_official_usd", "newyork_usd", "gold_silver_ratio", "london"]
    df = pd.DataFrame(recs, columns=cols[: len(recs[0])]).set_index("year")
    df = df.apply(pd.to_numeric, errors="coerce")
    df.index = pd.to_datetime(df.index.astype(str) + "-01-01")
    return df


def main() -> None:
    mw = parse_measuringworth(fetch_measuringworth())
    dh_path = raw_dir(SOURCE) / "datahub_gold_monthly.csv"
    try:
        download(DH_URL, dh_path, "csv")
    except Exception as e:  # noqa: BLE001
        log.warning("datahub download failed: %s", e)
    wb_url, wb_path = wb_pinksheet.fetch()
    wb = {n: s for n, _, _, s in wb_pinksheet.load_prices(wb_path)}["Gold"].dropna()

    cw = CatalogWriter(SOURCE, url="https://www.measuringworth.com/datasets/gold/", license=MW_LICENSE)
    years = mw.index.year
    cw.add("gold_mw_newyork_usd_a", mw["newyork_usd"], name="Gold, New York market price (annual avg)",
           category="gold", frequency="A", units="USD per fine oz", country="USA",
           transform_notes="MeasuringWorth; annual average")
    cw.add("gold_mw_us_official_usd_a", mw["us_official_usd"], name="Gold, U.S. official price (end of year)",
           category="gold", frequency="A", units="USD per fine oz", country="USA",
           transform_notes="MeasuringWorth; end of year")
    cw.add("gold_mw_british_official_gbp_a", mw["british_official_gbp"],
           name="Gold, British official price (end of year)", category="gold", frequency="A",
           units="GBP per fine oz", country="GBR", transform_notes="MeasuringWorth; 1257-1945")
    cw.add("gold_mw_london_gbp_a", mw["london"].where(years <= 1949), name="Gold, London market price (GBP)",
           category="gold", frequency="A", units="GBP per fine oz", country="GBR",
           transform_notes="MeasuringWorth London market price, GBP segment 1718-1949")
    cw.add("gold_mw_london_usd_a", mw["london"].where(years >= 1950), name="Gold, London market price (USD)",
           category="gold", frequency="A", units="USD per fine oz", country="GBR",
           transform_notes="MeasuringWorth London market price, USD segment 1950-present")
    cw.add("gold_mw_gold_silver_ratio_a", mw["gold_silver_ratio"], name="Gold/silver price ratio",
           category="gold", frequency="A", units="oz silver per oz gold", country="",
           transform_notes="MeasuringWorth")
    cw.add("gold_wb_usd_m", wb, name="Gold, World Bank Pink Sheet monthly average", category="gold",
           frequency="M", units="USD per troy oz", country="WLD",
           transform_notes="UK London-based price, avg of daily rates", url=wb_url, license=WB_LICENSE)
    if dh_path.exists():
        dh = pd.read_csv(dh_path)
        dh.index = pd.to_datetime(dh["Date"] + "-01")
        cw.add("gold_datahub_usd_m", dh["Price"], name="Gold, datahub core/gold-prices monthly",
               category="gold", frequency="M", units="USD per troy oz", country="",
               transform_notes="1833-1959 Timothy Green annual avg repeated monthly; 1960+ World Bank",
               url=DH_URL, license=DH_LICENSE)

    # splice
    ny = mw["newyork_usd"].dropna()
    ny = ny[ny.index < "1960-01-01"]
    monthly_idx = pd.date_range(ny.index.min(), "1959-12-01", freq="MS")
    pre = ny.reindex(monthly_idx, method="ffill")
    pre = pre[pre.index.year.isin(ny.index.year)]
    spliced = pd.concat([pre, wb[wb.index >= "1960-01-01"]])
    flag = pd.Series(0.0, index=spliced.index)
    flag[flag.index < "1960-01-01"] = 1.0
    notes = ("SPLICE: 1791-1959 MeasuringWorth New York market annual average repeated in each month "
             "(no intra-year variation; ~$20.67 1834-1932, $35 1934-1959 official regime); "
             "1960-present World Bank Pink Sheet monthly average (London). See gold_usd_monthly_flag.")
    cw.add("gold_usd_monthly", spliced, name="Gold price USD, spliced monthly 1791-present", category="gold",
           frequency="M", units="USD per troy oz", country="", transform_notes=notes,
           license=f"{MW_LICENSE}; {WB_LICENSE}")
    cw.add("gold_usd_monthly_flag", flag, name="Flag: 1 = annual value repeated (pre-1960), 0 = true monthly",
           category="gold", frequency="M", units="dummy", transform_notes="companion of gold_usd_monthly")
    cat = cw.close()
    # cross-check overlap
    if dh_path.exists():
        both = pd.concat([spliced, dh["Price"]], axis=1, keys=["spl", "dh"]).dropna()
        both = both[both.index >= "1960-01-01"]
        log.info("max abs diff spliced vs datahub 1960+: %.3f", (both.spl - both.dh).abs().max())
    print(cat[["series_id", "start", "end"]].to_string(index=False))
    print(spliced.loc[["1791-01-01", "1850-06-01", "1933-01-01", "1935-01-01", "1959-12-01", "1960-01-01", "1980-01-01"]])
    print(spliced.tail(3))


if __name__ == "__main__":
    main()
