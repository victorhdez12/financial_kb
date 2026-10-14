"""NY Fed Markets API secured reference rates -> curated/nyfed_repo (docs/DATA_CONTRACT.md).

    .venv/bin/python -m src.ingest.nyfed_repo

SOFR, BGCR, TGCR (rate, percentiles 1/25/75/99, volume in USD billions) and the SOFR Averages
& Index (30/90/180-day averages, index). Endpoint (no key, public):
https://markets.newyorkfed.org/api/rates/secured/<sofr|bgcr|tgcr|sofrai>/search.json?startDate=&endDate=
Publication starts 2018-04-02 (SOFR/BGCR/TGCR; the NY Fed also published a 2014-2018 indicative
history of SOFR, which the search endpoint does not return -> gap). SOFR averages/index: API returns from 2020-03-02 (first publication).
Raw: raw/nyfed_repo/<rate>.json (all rows as returned, one call per calendar year, concatenated).
Values are the latest published (revisions applied; revisionIndicator kept in raw).
"""
from __future__ import annotations

import json
import time

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, http_get, log, raw_dir

SOURCE = "nyfed_repo"
API = "https://markets.newyorkfed.org/api/rates/secured/{k}/search.json?startDate={a}&endDate={b}"
PAGE = "https://www.newyorkfed.org/markets/reference-rates/"
LICENSE = "Federal Reserve Bank of New York - public data, free use with attribution"
START = 2018


def fetch(kind: str) -> list[dict]:
    rows = []
    for y in range(START, pd.Timestamp.today().year + 1):
        end = min(pd.Timestamp(f"{y}-12-31"), pd.Timestamp.today().normalize())
        r = http_get(API.format(k=kind, a=f"{y}-01-01", b=end.date()), timeout=60).json()
        rows += r["refRates"]
        time.sleep(0.3)
    (raw_dir(SOURCE) / f"{kind}.json").write_text(json.dumps({"kind": kind, "refRates": rows}))
    log.info("%s: %d rows", kind, len(rows))
    return rows


def main() -> None:
    cw = CatalogWriter(SOURCE, url=PAGE, license=LICENSE)
    desc = {"sofr": ("SOFR - Secured Overnight Financing Rate", "secured/sofr"),
            "bgcr": ("BGCR - Broad General Collateral Rate", "secured/bgcr"),
            "tgcr": ("TGCR - Tri-Party General Collateral Rate", "secured/tgcr")}
    for k, (nm, path) in desc.items():
        d = pd.DataFrame(fetch(k))
        idx = pd.to_datetime(d["effectiveDate"])
        for col, suf, label, cat, units in [
                ("percentRate", "rate", "rate", "rates", "Percent"),
                ("percentPercentile1", "p01", "1st percentile", "rates", "Percent"),
                ("percentPercentile25", "p25", "25th percentile", "rates", "Percent"),
                ("percentPercentile75", "p75", "75th percentile", "rates", "Percent"),
                ("percentPercentile99", "p99", "99th percentile", "rates", "Percent"),
                ("volumeInBillions", "volume", "transaction volume", "liquidity", "Billions of USD")]:
            s = pd.Series(pd.to_numeric(d[col], errors="coerce").values, index=idx)
            cw.add(f"nyfed_{k}_{suf}_d", s, name=f"{nm}: {label}", category=cat, frequency="D",
                   units=units, country="US",
                   transform_notes=("business-day value for the effective date; latest revised value "
                                    "from the NY Fed Markets API; percentiles of volume-weighted "
                                    "transactions" if suf != "rate" else
                                    "business-day value for the effective date; latest revised value"),
                   url=PAGE + path)
    d = pd.DataFrame(fetch("sofrai"))
    idx = pd.to_datetime(d["effectiveDate"])
    for col, sid, nm, units in [("average30day", "nyfed_sofr_avg30_d", "30-day average", "Percent"),
                                ("average90day", "nyfed_sofr_avg90_d", "90-day average", "Percent"),
                                ("average180day", "nyfed_sofr_avg180_d", "180-day average", "Percent"),
                                ("index", "nyfed_sofr_index_d", "index (base 1.0 on 2018-04-02)",
                                 "Index")]:
        s = pd.Series(pd.to_numeric(d[col], errors="coerce").values, index=idx)
        cw.add(sid, s, name=f"SOFR Averages and Index: {nm}", category="rates", frequency="D",
               units=units, country="US", transform_notes="business-day value; compounded in arrears",
               url=PAGE + "secured/sofrai")
    cat = cw.close()
    print(cat[["series_id", "frequency", "start", "end"]].to_string(index=False))


if __name__ == "__main__":
    main()
