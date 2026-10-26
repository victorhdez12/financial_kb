"""Deutsche Bundesbank time-series database (SDMX REST, no key): pre-euro German history.

Discount and Lombard rates (1948-1998), Frankfurt money-market rates (overnight / 1m / 3m from
1959-60), FIBOR (1990-1999), yields on debt securities outstanding ("Umlaufsrendite", 1955-),
public and corporate bond yields, and the Svensson term structure of Federal securities (1972-).
Also a spliced German policy rate (Bundesbank discount rate -> ECB MRO) for long backtests.

Run: .venv/bin/python -m src.ingest.bundesbank
Raw:     $FIN_DATA_ROOT/raw/bundesbank/<FLOW>.<KEY>.csv
Curated: $FIN_DATA_ROOT/curated/bundesbank/bundesbank_*.parquet + _catalog.csv
"""
from __future__ import annotations

import csv
import io
import os

import pandas as pd

from src.ingest._europe_common import CatalogWriter, add_series, cached_get, log, raw_dir, spliced, to_period_start

SOURCE = "bundesbank"
API = "https://api.statistiken.bundesbank.de/rest/data/{flow}/{key}?format=csv&lang=en"
PAGE = "https://www.bundesbank.de/dynamic/action/en/statistics/time-series-databases/time-series-databases/759784/759784?tsId={flow}.{key}"
LICENSE = "Deutsche Bundesbank: free re-use with source attribution (Bundesbank terms of use)"

# (series_id, flow, key, name, category, units, positive, notes)
SEL = [
    ("bundesbank_discount_rate_m", "BBIN1", "M.DE.BBK.BBKDIS.DEM.ME", "Bundesbank discount rate (Diskontsatz), end of month", "rates", "% p.a.", False,
     "Bank deutscher Länder until 1957. Ends 1998-12 (replaced by ECB rates)."),
    ("bundesbank_lombard_rate_m", "BBIN1", "M.DE.BBK.BBKLOM.DEM.ME", "Bundesbank Lombard rate, end of month", "rates", "% p.a.", False, "Ends 1998-12."),
    ("bundesbank_base_rate_m", "BBIN1", "M.DE.BBK.BBKBAS2.EUR.ME", "Base rate as per German Civil Code (Basiszinssatz §247 BGB)", "rates", "% p.a.", False, ""),
    ("bundesbank_mm_overnight_m", "BBIG1", "M.D0.EUR.MMKT.GMFFM.ON.AVE.MA", "Frankfurt money market, overnight money, monthly average", "rates", "% p.a.", False,
     "Rates reported by Frankfurt banks (Tagesgeld), DM before 1999, EUR after."),
    ("bundesbank_mm_1m_m", "BBIG1", "M.D0.EUR.MMKT.GMFFM.M01.AVE.MA", "Frankfurt money market, 1-month funds, monthly average", "rates", "% p.a.", False, ""),
    ("bundesbank_mm_3m_m", "BBIG1", "M.D0.EUR.MMKT.GMFFM.M03.AVE.MA", "Frankfurt money market, 3-month funds, monthly average", "rates", "% p.a.", False, ""),
    ("bundesbank_mm_12m_m", "BBIG1", "M.D0.EUR.MMKT.GMFFM.M12.AVE.MA", "Frankfurt money market, 12-month funds, monthly average", "rates", "% p.a.", False, ""),
    ("bundesbank_fibor_3m_m", "BBIG1", "M.DE.DEM.MMKT.FIBOR.M03.AVE.MA", "FIBOR 3-month, monthly average", "rates", "% p.a.", False, "1990-07 to 1999 (predecessor of Euribor)."),
    ("bundesbank_fibor_12m_m", "BBIG1", "M.DE.DEM.MMKT.FIBOR.M12.AVE.MA", "FIBOR 12-month, monthly average", "rates", "% p.a.", False, ""),
    ("bundesbank_umlaufsrendite_m", "BBSIS", "M.I.UMR.RD.EUR.A.B.A.A.R.A.A._Z._Z.A", "Yield on debt securities outstanding (Umlaufsrendite), total", "rates", "% p.a.", False,
     "All domestic bearer bonds, monthly average."),
    ("bundesbank_public_bond_yield_m", "BBSIS", "M.I.UMR.RD.EUR.S13.B.A.A.R.A.A._Z._Z.A", "Yield on public debt securities outstanding", "rates", "% p.a.", False, ""),
    ("bundesbank_public_bond_yield_9_10y_m", "BBSIS", "M.I.UMR.RD.EUR.S13.B.A.R0910.R.A.A._Z._Z.A", "Yield on public debt securities, residual maturity 9-10 years", "rates", "% p.a.", False,
     "Closest long-history proxy for the 10y Bund before 1972."),
    ("bundesbank_corp_bond_yield_m", "BBSIS", "M.I.UMR.RD.EUR.X2000.B.A.A.R.A.A._Z._Z.A", "Yield on corporate bonds (non-MFIs) outstanding", "credit", "% p.a.", False, ""),
    ("bundesbank_mortgage_pfandbrief_yield_m", "BBSIS", "M.I.UMR.RD.EUR.MFISX.B.X100.A.R.A.A._Z._Z.A", "Yield on mortgage Pfandbriefe outstanding", "rates", "% p.a.", False, ""),
]
for m in ["01", "02", "05", "10"]:
    SEL.append((f"bundesbank_bund_zero_{int(m)}y_m", "BBSIS", f"M.I.ZST.ZI.EUR.S1311.B.A604.R{m}XX.R.A.A._Z._Z.A",
                f"Federal securities zero-coupon yield {int(m)}y (Svensson), monthly", "rates", "% p.a.", False,
                "Bundesbank term-structure estimate from listed Federal securities, since 1972-09."))

# Daily Svensson term structure of listed Federal securities (europe_daily_spain, 2026-10-13)
DAILY = []
for m in ["01", "02", "05", "10", "30"]:
    DAILY.append((f"bundesbank_bund_zero_{int(m)}y_d", "BBSIS", f"D.I.ZST.ZI.EUR.S1311.B.A604.R{m}XX.R.A.A._Z._Z.A",
                  f"Federal securities zero-coupon yield {int(m)}y (Svensson), daily", "rates", "% p.a.", False,
                  "Bundesbank daily term-structure estimate from listed Federal securities (benchmark DE sovereign, daily since 1972)."))
DAILY.append(("bundesbank_umlaufsrendite_d", "BBSIS", "D.I.UMR.RD.EUR.A.B.A.A.R.A.A._Z._Z.A", "Yield on debt securities outstanding (Umlaufsrendite), total, daily",
              "rates", "% p.a.", False, "Daily, all domestic bearer bonds."))
DAILY.append(("bundesbank_usd_dem_d", "BBEX3", "D.USD.DEM.AA.AC.000", "Frankfurt exchange fixing, DEM per USD, daily",
              "fx", "DEM per USD", True, "Daily official fixing 1948-1998 (ends with the euro). Month-end FX for the "
              "paper-trading sigma* (docs/factors/paper_trading.md)."))


def fetch(flow: str, key: str) -> tuple[pd.Series, str]:
    content = cached_get(API.format(flow=flow, key=key), raw_dir(SOURCE) / f"{flow}.{key}.csv", min_bytes=100)
    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
    title = rows[1][1] if len(rows) > 1 and len(rows[1]) > 1 else ""
    idx, vals = [], []
    for r in rows:
        if len(r) < 2:
            continue
        d = to_period_start(r[0])
        if d is None:
            continue
        idx.append(d)
        try:
            vals.append(float(r[1].replace(",", ".")))
        except ValueError:  # '.', '' = no value
            vals.append(float("nan"))
    return pd.Series(vals, index=pd.DatetimeIndex(idx)).sort_index(), title


def main() -> pd.DataFrame:
    cw = CatalogWriter(SOURCE, url="https://www.bundesbank.de/en/statistics/time-series-databases", license=LICENSE)
    got = {}
    for sid, flow, key, name, cat, units, pos, notes in SEL:
        try:
            s, title = fetch(flow, key)
        except Exception as e:  # noqa: BLE001
            log.warning("%s failed: %s", sid, e)
            continue
        got[sid] = s
        n = add_series(cw, sid, s, positive=pos, name=name, category=cat, frequency="M", units=units, country="DE",
                       transform_notes=f"Bundesbank {flow}.{key}: {title}. {notes}".strip(), url=PAGE.format(flow=flow, key=key))
        log.info("%-40s %5d obs", sid, n)
    for sid, flow, key, name, cat, units, pos, notes in DAILY:
        try:
            s_, title = fetch(flow, key)
        except Exception as e:  # noqa: BLE001
            log.warning("%s failed: %s", sid, e)
            continue
        n = add_series(cw, sid, s_, positive=pos, name=name, category=cat, frequency="D", units=units, country="DE",
                       transform_notes=f"Bundesbank {flow}.{key}: {title}. {notes}".strip(), url=PAGE.format(flow=flow, key=key))
        log.info("%-40s %5d obs", sid, n)
    # Spliced German/euro policy rate: Bundesbank discount rate -> ECB MRO (monthly, end of month)
    ecb_mro = os.path.join(os.path.expanduser(os.environ.get("FIN_DATA_ROOT", "~/financial_archive")), "curated/ecb/ecb_mro_d.parquet")
    if "bundesbank_discount_rate_m" in got and os.path.exists(ecb_mro):
        m = pd.read_parquet(ecb_mro)
        mro = pd.Series(m["value"].values, index=pd.to_datetime(m["date"]))
        mro_m = mro.resample("MS").last()  # value in force at month end, dated at month start
        pol = spliced([(got["bundesbank_discount_rate_m"], None, "1998-12-01"), (mro_m, "1999-01-01", None)])
        add_series(cw, "bundesbank_de_policy_rate_spliced_m", pol, name="German policy rate: Bundesbank discount rate to 1998, ECB MRO from 1999",
                   category="rates", frequency="M", units="% p.a.", country="DE",
                   transform_notes="SPLICE at 1999-01: Bundesbank Diskontsatz (end of month) 1948-1998 -> ECB main refinancing rate "
                                   "(ecb_mro_d, value at month end). The discount rate was a floor-type rate below the Bundesbank repo rate; "
                                   "level comparability across the splice is approximate. Run src.ingest.ecb first.")
    else:
        log.warning("spliced policy rate skipped (run src.ingest.ecb first)")
    return cw.close()


if __name__ == "__main__":
    main()
