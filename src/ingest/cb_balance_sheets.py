"""Central-bank balance sheets and broad money (BoJ, BoE, SNB, PBoC, China M2) -> curated/cb_balance_sheets.

    .venv/bin/python -m src.ingest.cb_balance_sheets

Sources (all public, no key except FRED):
* BoJ  Time-Series Data Search API (stat-search.boj.or.jp/api/v1/getDataCode): BS01 Bank of Japan
  Accounts (monthly, 1998-04+), MD01 Monetary Base, MD02 Money Stock M1/M2/M3 (2003-04+).
* SNB  data.snb.ch cubes snbbipo (balance sheet, monthly 1996-12+).
* BoE  Interactive Database (IADB) CSV: LPMAUYN (M4), RPWB75A (Bank Return total assets 2006-2014).
* IMF  MFS via DBnomics: PBoC (China) total assets and reserve money, monthly (lags ~1 year).
* China M2/M1/M0: Eastmoney data-center mirror of PBoC releases (third party; see license note).
* FRED: JPNASSETS, UKASSETS (disc.), SNBMONTBASE, long OECD/IMF broad-money history for JP/CN/GB.
FX conversion series are NOT duplicated: DEXJPUS, DEXUSUK, DEXSZUS, DEXCHUS, DEXUSEU are in curated/fred.

Raw (untouched downloads) -> $FIN_DATA_ROOT/raw/cb_balance_sheets/.
"""
from __future__ import annotations

import io
import json
import time

import pandas as pd
import requests

from src.ingest._extlong_common import UA, CatalogWriter, http_get, log, raw_dir
from src.ingest.fred_extended import Fred

SOURCE = "cb_balance_sheets"
LICENSE = "Public statistics of each central bank / IMF; personal research use. FRED series carry FRED terms."
BOJ_API = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"


def mstart(s: pd.Series) -> pd.DatetimeIndex:
    return pd.to_datetime(s).dt.to_period("M").dt.to_timestamp()


def cached_text(url: str, name: str, *, hours: float = 20, params: dict | None = None) -> str:
    p = raw_dir(SOURCE) / name
    if p.exists() and (time.time() - p.stat().st_mtime) / 3600 < hours:
        return p.read_text(encoding="utf-8-sig")
    r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=120)
    r.raise_for_status()
    p.write_bytes(r.content)
    log.info("downloaded %s (%d bytes)", name, len(r.content))
    return r.content.decode("utf-8-sig")


# ------------------------------------------------------------------ BoJ
BOJ = [
    # db, code, series_id, name, category, units-note
    ("BS01", "MABJMTA", "cbbs_boj_total_assets_m", "BoJ total assets (end of month)", "liquidity"),
    ("BS01", "MABJMA5", "cbbs_boj_jgs_m", "BoJ holdings of Japanese government securities (JGBs + bills)", "liquidity"),
    ("BS01", "MABJMA5B", "cbbs_boj_jgb_m", "BoJ holdings of JGBs", "liquidity"),
    ("BS01", "MABJMA002", "cbbs_boj_corpbonds_m", "BoJ holdings of corporate bonds", "liquidity"),
    ("BS01", "MABJMA003", "cbbs_boj_etf_m", "BoJ holdings of index-linked ETFs (pecuniary trusts)", "liquidity"),
    ("BS01", "MABJMA@01", "cbbs_boj_loans_m", "BoJ loans and discounts", "liquidity"),
    ("BS01", "MABJMA12", "cbbs_boj_fxassets_m", "BoJ foreign currency assets", "liquidity"),
    ("BS01", "MABJML1", "cbbs_boj_banknotes_m", "BoJ banknotes in circulation", "money"),
    ("BS01", "MABJML11", "cbbs_boj_currentdep_m", "BoJ current deposits (bank reserves)", "liquidity"),
    ("BS01", "MABJML3", "cbbs_boj_govdep_m", "BoJ deposits of the government", "liquidity"),
    ("MD01", "MABS1AN11", "cbbs_boj_monbase_avg_m", "BoJ monetary base, average amounts outstanding", "money"),
    ("MD01", "MABS1AN113", "cbbs_boj_currentacct_avg_m", "BoJ current account balances, average amounts outstanding", "liquidity"),
    ("MD02", "MAM1NAM2M2MO", "cbbs_jp_m2_avg_m", "Japan M2, average amounts outstanding (from 2003-04)", "money"),
    ("MD02", "MAM1NAM3M3MO", "cbbs_jp_m3_avg_m", "Japan M3, average amounts outstanding (from 2003-04)", "money"),
    ("MD02", "MAM1NAM3M1MO", "cbbs_jp_m1_avg_m", "Japan M1, average amounts outstanding (from 2003-04)", "money"),
]


def boj_series(db: str, code: str) -> tuple[pd.Series, str]:
    txt = cached_text(BOJ_API, f"boj_{db}_{code.replace('@', 'x')}.csv",
                      params={"format": "csv", "lang": "en", "db": db, "code": code, "startDate": "195001"})
    lines = txt.splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith("SERIES_CODE"))
    df = pd.read_csv(io.StringIO("\n".join(lines[i:])))
    df = df[df["SERIES_CODE"] == code]
    df = df[df["VALUES"].astype(str).str.fullmatch(r"-?[\d.]+")]
    idx = pd.to_datetime(df["SURVEY_DATES"].astype(str) + "01", format="%Y%m%d")
    return pd.Series(pd.to_numeric(df["VALUES"]).values, index=idx), str(df["UNIT"].iloc[0]) if len(df) else ""


# ------------------------------------------------------------------ SNB
SNB = [("T0", "cbbs_snb_total_assets_m", "SNB total assets (end of month)", "liquidity"),
       ("GFG", "cbbs_snb_gold_m", "SNB gold holdings and claims from gold transactions", "liquidity"),
       ("D", "cbbs_snb_fxinv_m", "SNB foreign currency investments", "liquidity"),
       ("N", "cbbs_snb_banknotes_m", "SNB banknotes in circulation", "money"),
       ("GB", "cbbs_snb_sightdep_dom_m", "SNB sight deposits of domestic banks (reserves)", "liquidity"),
       ("GBI", "cbbs_snb_sightdep_for_m", "SNB sight deposits of foreign banks and institutions", "liquidity")]


# ------------------------------------------------------------------ BoE IADB
def iadb(code: str, start: str = "01/Jan/1963") -> pd.Series:
    url = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
    txt = cached_text(url, f"boe_{code}.csv", params={
        "csv.x": "yes", "Datefrom": start, "Dateto": "now", "SeriesCodes": code, "CSVF": "TN",
        "UsingCodes": "Y", "VPD": "Y", "VFD": "N"})
    if txt.lstrip().lower().startswith("<!doctype"):
        raise RuntimeError(f"BoE IADB returned HTML for {code}")
    df = pd.read_csv(io.StringIO(txt))
    return pd.Series(pd.to_numeric(df[code], errors="coerce").values,
                     index=pd.to_datetime(df["DATE"], format="%d %b %Y"))


# ------------------------------------------------------------------ IMF MFS via DBnomics
def dbnomics(code: str) -> pd.Series:
    txt = cached_text(f"https://api.db.nomics.world/v22/series/{code}", f"dbnomics_{code.replace('/', '_')}.json",
                      params={"observations": 1})
    d = json.loads(txt)["series"]["docs"][0]
    s = pd.Series([None if v == "NA" else v for v in d["value"]], index=pd.to_datetime(d["period"]))
    return pd.to_numeric(s, errors="coerce")


def eastmoney_m2() -> pd.DataFrame:
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    txt = cached_text(url, "eastmoney_china_money_supply.json", params={
        "reportName": "RPT_ECONOMY_CURRENCY_SUPPLY", "columns": "ALL", "pageNumber": 1, "pageSize": 1000,
        "sortColumns": "REPORT_DATE", "sortTypes": -1})
    df = pd.DataFrame(json.loads(txt)["result"]["data"])
    df["date"] = mstart(df["REPORT_DATE"])
    return df.set_index("date").sort_index()


# ------------------------------------------------------------------ FRED
FRED = [
    # id, series_id suffix, category, country, note
    ("JPNASSETS", "BoJ total assets (FRED mirror, 100 mil. yen, end of month)", "liquidity", "JP", "cross-check of BoJ BS01"),
    ("UKASSETS", "Bank of England total central bank assets, DISCONTINUED 2014-09", "liquidity", "GB", "discontinued"),
    ("SNBMONTBASE", "Swiss monetary base aggregate", "money", "CH", ""),
    ("MYAGM2JPM189N", "Japan M2 (+CDs), NSA, OECD/IMF vintage, ends 2017-02", "money", "JP",
     "old definition (M2+CD); do NOT splice with cbbs_jp_m2_avg_m without a break"),
    ("MYAGM2CNM189N", "China M2, NSA, OECD/IMF vintage, ends 2019-08", "money", "CN", "national currency"),
    ("MABMM301GBM189S", "UK broad money M3, SA, OECD MEI, ends 2023-11", "money", "GB", "OECD M3, not BoE M4"),
    ("MABMM301JPM189S", "Japan broad money M3, SA, OECD MEI, ends 2023-11", "money", "JP", ""),
    ("MABMM301CNM189S", "China broad money M3, SA, OECD MEI, ends 2018-12", "money", "CN", ""),
    ("MYAGM4GBM189N", "UK M4, NSA, OECD/IMF vintage, 1982-2016", "money", "GB", "ends 2016-08"),
]


def fred_series(f: Fred, sid: str) -> tuple[pd.Series, dict]:
    meta = f.get("series", series_id=sid)["seriess"][0]
    obs = f.get("series/observations", series_id=sid)["observations"]
    (raw_dir(SOURCE) / f"fred_{sid}.json").write_text(json.dumps({"series": meta, "observations": obs}))
    s = pd.Series([float(o["value"]) if o["value"] != "." else None for o in obs],
                  index=pd.to_datetime([o["date"] for o in obs]), dtype="float64")
    return s, meta


def main() -> None:
    cw = CatalogWriter(SOURCE, url="https://www.stat-search.boj.or.jp/", license=LICENSE)

    for db, code, sid, name, cat in BOJ:
        try:
            s, unit = boj_series(db, code)
        except Exception as e:  # noqa: BLE001
            log.warning("BoJ %s/%s failed: %s", db, code, e)
            continue
        cw.add(sid, s, name=name, category=cat, frequency="M", units=f"{unit} (JPY)", country="JP",
               transform_notes=(f"BoJ API db={db} code={code}; month-start date; BS01 = end-of-month stock, "
                                "MD01/MD02 = monthly averages"),
               url="https://www.stat-search.boj.or.jp/")

    snb = cached_text("https://data.snb.ch/api/cube/snbbipo/data/csv/en", "snb_snbbipo.csv")
    lines = snb.splitlines()
    i = next(k for k, l in enumerate(lines) if l.startswith('"Date"'))
    d = pd.read_csv(io.StringIO("\n".join(lines[i:])), sep=";")
    for code, sid, name, cat in SNB:
        sub = d[d["D0"] == code]
        s = pd.Series(pd.to_numeric(sub["Value"], errors="coerce").values, index=mstart(sub["Date"]))
        cw.add(sid, s, name=name, category=cat, frequency="M", units="CHF millions", country="CH",
               transform_notes=f"SNB cube snbbipo item {code}; end-of-month stock dated to month start",
               url="https://data.snb.ch/en/topics/snb/cube/snbbipo")

    boe = [("LPMAUYN", "cbbs_boe_m4_m", "UK M4 money stock, amounts outstanding (IADB LPMAUYN)", "money", "M",
            "GBP millions", "month-end stock dated to month start; BoE IADB code LPMAUYN (M4 amounts outstanding)"),
           ("RPWB75A", "cbbs_boe_bankreturn_assets_w", "Bank of England Bank Return total assets (2006-2014)",
            "liquidity", "W", "GBP millions",
            "IADB RPWB75A weekly (Wednesday); series stops with the 2014 Bank Return reform; no post-2014 total in IADB")]
    for code, sid, name, cat, fq, unit, note in boe:
        try:
            s = iadb(code)
        except Exception as e:  # noqa: BLE001
            log.warning("BoE %s failed: %s", code, e)
            continue
        if fq == "M":
            s.index = s.index.to_period("M").to_timestamp()
        cw.add(sid, s, name=name, category=cat, frequency=fq, units=unit, country="GB", transform_notes=note,
               url="https://www.bankofengland.co.uk/boeapps/database/")

    # PBoC via IMF MFS (DBnomics)
    for code, sid, name, cat in [("IMF/MFS/M.CN.10RA__XDC", "cbbs_pboc_total_assets_m",
                                  "PBoC total assets (IMF MFS, non-standardized presentation)", "liquidity"),
                                 ("IMF/MFS/M.CN.14____XDC", "cbbs_pboc_reserve_money_m",
                                  "PBoC reserve money (IMF MFS)", "money")]:
        try:
            s = dbnomics(code)
        except Exception as e:  # noqa: BLE001
            log.warning("DBnomics %s failed: %s", code, e)
            continue
        cw.add(sid, s, name=name, category=cat, frequency="M", units="CNY millions", country="CN",
               transform_notes=f"IMF MFS {code.split('/')[-1]} via DBnomics mirror; mirror lags the IMF by about a year",
               url="https://db.nomics.world/IMF/MFS", license="IMF terms of use (DBnomics mirror)")

    # China M2 / M1 / M0 (units: 100 million CNY -> CNY millions)
    try:
        em = eastmoney_m2()
        for col, sid, nm in [("BASIC_CURRENCY", "cbbs_cn_m2_m", "China M2 (broad money)"),
                             ("CURRENCY", "cbbs_cn_m1_m", "China M1"), ("FREE_CASH", "cbbs_cn_m0_m", "China M0 (currency in circulation)")]:
            cw.add(sid, em[col] * 100.0, name=nm, category="money", frequency="M", units="CNY millions",
                   country="CN",
                   transform_notes=("Eastmoney data-center mirror of PBoC monetary survey; source unit 100 million CNY x100; "
                                    "NOTE Eastmoney BASIC_CURRENCY=M2, CURRENCY=M1, FREE_CASH=M0 (checked vs YoY); "
                                    "third-party mirror, PBoC original is the authority"),
                   url="https://data.eastmoney.com/cjsj/hbgyl.html",
                   license="Third-party mirror of PBoC public statistics; research use only")
        cw.add("cbbs_cn_m2_yoy_m", em["BASIC_CURRENCY_SAME"], name="China M2 year-on-year growth (as published)",
               category="money", frequency="M", units="Percent", country="CN",
               transform_notes="as published by PBoC via Eastmoney mirror", url="https://data.eastmoney.com/cjsj/hbgyl.html",
               license="Third-party mirror of PBoC public statistics; research use only")
    except Exception as e:  # noqa: BLE001
        log.warning("China M2 failed: %s", e)

    f = Fred()
    for sid, name, cat, ctry, note in FRED:
        try:
            s, meta = fred_series(f, sid)
        except Exception as e:  # noqa: BLE001
            log.warning("FRED %s failed: %s", sid, e)
            continue
        cw.add(f"cbbs_fred_{sid.lower()}", s, name=name, category=cat, frequency=meta["frequency_short"][:1],
               units=meta["units"], country=ctry,
               transform_notes=f"FRED {sid}; {note}".strip("; "), url=f"https://fred.stlouisfed.org/series/{sid}",
               license="FRED terms of use (underlying: " + meta.get("notes", "")[:0] + "BoJ/BoE/SNB/OECD/IMF)")

    cat = cw.close()
    print(cat[["series_id", "frequency", "start", "end"]].to_string(index=False))


if __name__ == "__main__":
    main()
