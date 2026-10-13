""""Changing World Order" indicators: Maddison Project Database 2023 (GDP pc + population since
year 1), IMF COFER (currency composition of FX reserves, 1995 ->) and SIPRI military
expenditure (1949 ->).

source_ids: maddison, imf_cofer, sipri.
Run: .venv/bin/python -m src.ingest.cycle_worldorder [--refresh] [maddison|cofer|sipri]

Notes
- dataverse.nl sits behind an Anubis anti-bot wall for browser User-Agents; a plain
  non-browser UA receives the file (signed S3 redirect).
- IMF COFER via the new SDMX 3.0 API (api.imf.org), JSON.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import warnings

import pandas as pd
import requests

from ._extlong_common import CatalogWriter, download, log, raw_dir, validate_bytes

warnings.filterwarnings("ignore")

MADDISON_URL = "https://dataverse.nl/api/access/datafile/421302"
MADDISON_PAGE = "https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023"
COFER_URL = ("https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/COFER/+/*"
             "?dimensionAtObservation=TIME_PERIOD&attributes=dsd&measures=all")
SIPRI_PAGE = "https://www.sipri.org/databases/milex"
SIPRI_FALLBACK = "https://www.sipri.org/sites/default/files/SIPRI-Milex-data-1949-2025_v1.2.xlsx"

SIPRI_COUNTRIES = {
    "United States of America": "usa", "China": "chn", "Russia": "rus", "USSR": "sun",
    "United Kingdom": "gbr", "France": "fra", "Germany": "deu", "German Federal Republic": "deu_west",
    "German Democratic Republic": "deu_east", "Japan": "jpn", "India": "ind", "Saudi Arabia": "sau",
    "Spain": "esp", "Italy": "ita", "Israel": "isr", "Ukraine": "ukr", "Korea, South": "kor",
    "Iran": "irn", "Turkey": "tur", "Türkiye": "tur", "Poland": "pol", "Brazil": "bra", "Pakistan": "pak",
    "Australia": "aus", "Canada": "can", "Taiwan": "twn", "Netherlands": "nld",
}


def _get(url, ua="python-requests/2.34 (financial_kb research)") -> bytes:
    r = requests.get(url, headers={"User-Agent": ua}, timeout=180, allow_redirects=True)
    r.raise_for_status()
    return r.content


def maddison(refresh=False):
    rd = raw_dir("maddison")
    dest = rd / "mpd2023_web.xlsx"
    if refresh or not dest.exists():
        b = _get(MADDISON_URL)
        validate_bytes(b, "xlsx")
        dest.write_bytes(b)
    cw = CatalogWriter("maddison", url=MADDISON_PAGE,
                       license="CC BY 4.0; cite Bolt & van Zanden (2024) Maddison Project Database 2023")
    d = pd.read_excel(dest, sheet_name="Full data")
    for (iso, country), g in d.groupby(["countrycode", "country"]):
        idx = [dt.date(int(y), 1, 1) for y in g["year"]]
        gdppc = pd.Series(g["gdppc"].values, index=idx)
        pop = pd.Series(g["pop"].values, index=idx)
        c = iso.lower()
        note = "Full data sheet; benchmark years before 1820 are sparse (1, 730, 1000, ...)"
        cw.add(f"maddison_{c}_gdppc", gdppc, name=f"Maddison GDP per capita, {country}", category="growth",
               frequency="A", units="2011 int. $ (PPP)", country=iso, transform_notes=note)
        cw.add(f"maddison_{c}_pop", pop, name=f"Maddison population, {country}", category="growth",
               frequency="A", units="thousands", country=iso, transform_notes=note)
        cw.add(f"maddison_{c}_gdp", gdppc * pop / 1e6, name=f"Maddison total GDP (gdppc x pop), {country}",
               category="growth", frequency="A", units="billions 2011 int. $", country=iso,
               transform_notes="derived gdppc*pop/1e6; " + note)
    # The sheet has two blocks side by side with the same region names: GDP per capita, then population
    # (block titles in row 0; region names in row 1, except the World column whose name is in row 0).
    reg = pd.read_excel(dest, sheet_name="Regional data", header=None)
    titles, names = reg.iloc[0].tolist(), reg.iloc[1].tolist()
    body = reg.iloc[2:]
    body = body[pd.to_numeric(body[0], errors="coerce").notna()]
    idx = [dt.date(int(y), 1, 1) for y in body[0]]
    pop_start = next(j for j, t in enumerate(titles) if isinstance(t, str) and t.strip().lower().startswith("regional population"))
    for j in range(1, len(names)):
        nm = names[j] if isinstance(names[j], str) else titles[j] if isinstance(titles[j], str) else None
        if nm is None:
            continue
        is_pop = j >= pop_start
        nm = re.sub(r"\s*(GDP pc|Population)$", "", nm.strip()).replace("Sub Saharan SSA", "Sub Saharan Africa")
        slug = re.sub(r"[^a-z0-9]+", "_", nm.lower()).strip("_")
        vals = pd.Series(pd.to_numeric(body[j], errors="coerce").values, index=idx)
        if is_pop:
            cw.add(f"maddison_region_{slug}_pop", vals, name=f"Maddison regional population, {nm}",
                   category="growth", frequency="A", units="thousands", country=nm,
                   transform_notes="Regional data sheet, population block")
        else:
            cw.add(f"maddison_region_{slug}_gdppc", vals, name=f"Maddison regional GDP per capita, {nm}",
                   category="growth", frequency="A", units="2011 int. $", country=nm,
                   transform_notes="Regional data sheet, GDP per capita block")
    return cw.close()


MIN_COFER_OBS = 8


def cofer(refresh=False):
    rd = raw_dir("imf_cofer")
    dest = rd / "cofer_all.json"
    if refresh or not dest.exists():
        b = _get(COFER_URL)
        json.loads(b)
        dest.write_bytes(b)
    js = json.loads(dest.read_text())
    st = js["data"]["structures"][0]
    sdims = st["dimensions"]["series"]
    times = [v.get("id", v.get("value")) for v in st["dimensions"]["observation"][0]["values"]]
    cw = CatalogWriter("imf_cofer", url="https://data.imf.org/en/datasets/IMF.STA:COFER",
                       license="IMF data, free reuse with attribution (IMF terms)")
    area = {"G001": "world", "G110": "adv", "G200": "em"}
    ind = {"AFXRA": "allocated", "TFXRA": "total", "UFXRA": "unallocated", "TFXRA_IMP": "total_imputed"}
    for key, s in js["data"]["dataSets"][0]["series"].items():
        k = [sdims[i]["values"][int(x)]["id"] for i, x in enumerate(key.split(":"))]
        kd = dict(zip([dd["id"] for dd in sdims], k))
        if kd.get("FREQUENCY") != "Q":
            continue
        obs = s.get("observations", {})
        vals, idx = [], []
        for t, v in obs.items():
            tp = times[int(t)]
            try:
                idx.append(pd.Period(tp.replace("-", ""), "Q").start_time)
                vals.append(float(v[0]) if v[0] is not None else float("nan"))
            except Exception:  # noqa: BLE001
                continue
        cur = kd["FXR_CURRENCY"].replace("CI_", "").lower()
        unit = "share" if kd["TYPE_OF_TRANSFORMATION"] == "SHRO_PT" else "usd"
        ser = pd.Series(vals, index=idx, dtype=float)
        if unit == "usd":
            ser = ser.mask(ser == 0)  # e.g. world "unallocated" = 0 in 2000-2026: not reported, not zero
        if ser.notna().sum() < MIN_COFER_OBS:
            # the API only returns 1999 for the advanced/emerging split (4-5 quarters): a stub, not a series
            print(f"cofer: skip {kd['COUNTRY']} {kd['INDICATOR']} ({ser.notna().sum()} obs)")
            continue
        sid = f"cofer_{area.get(kd['COUNTRY'], kd['COUNTRY'].lower())}_{ind.get(kd['INDICATOR'], kd['INDICATOR'].lower())}_{cur}_{unit}"
        cw.add(sid, ser,
               name=f"IMF COFER {ind.get(kd['INDICATOR'])} FX reserves in {cur.upper()}, "
                    f"{ {'world': 'all reporters', 'adv': 'advanced economies', 'em': 'emerging & developing'}.get(area.get(kd['COUNTRY']), kd['COUNTRY'])}",
               category="fx", frequency="Q",
               units="% of allocated reserves" if unit == "share" else "USD",
               country=kd["COUNTRY"], transform_notes=f"SDMX key {kd}")
    return cw.close()


def sipri(refresh=False):
    rd = raw_dir("sipri")
    page_link = None
    try:
        html = requests.get(SIPRI_PAGE, headers={"User-Agent": "Mozilla/5.0"}, timeout=60).text
        m = re.search(r'href="([^"]*SIPRI-Milex-data-[^"]+\.xlsx)"', html)
        if m:
            page_link = requests.compat.urljoin("https:", m.group(1)) if m.group(1).startswith("//") else \
                requests.compat.urljoin(SIPRI_PAGE, m.group(1))
    except Exception as e:  # noqa: BLE001
        log.warning("sipri page: %s", e)
    url = page_link or SIPRI_FALLBACK
    dest = rd / url.rsplit("/", 1)[-1]
    download(url, dest, "xlsx", min_age_hours=0 if refresh else 24 * 30)
    cw = CatalogWriter("sipri", url=SIPRI_PAGE,
                       license="SIPRI Military Expenditure Database, free for non-commercial use with citation")
    sheets = {"Constant (2024) US$": ("const_usd", "US$ m, constant 2024 prices"),
              "Share of GDP": ("share_gdp", "% of GDP"),
              "Share of Govt. spending": ("share_govt", "% of general govt expenditure")}
    for sheet, (tag, units) in sheets.items():
        raw = pd.read_excel(dest, sheet_name=sheet, header=None)
        hdr = raw.index[raw[0].astype(str).str.strip() == "Country"][0]
        cols = raw.iloc[hdr].tolist()
        body = raw.iloc[hdr + 1:]
        ycols = [j for j, c in enumerate(cols) if re.fullmatch(r"\d{4}(\.0)?", str(c))]
        for _, row in body.iterrows():
            nm = str(row[0]).strip()
            if nm not in SIPRI_COUNTRIES:
                continue
            code = SIPRI_COUNTRIES[nm]
            vals = pd.to_numeric(pd.Series([row[j] for j in ycols]), errors="coerce").values
            idx = [dt.date(int(float(cols[j])), 1, 1) for j in ycols]
            s = pd.Series(vals, index=idx)
            if tag == "share_gdp" or tag == "share_govt":
                s = s * 100 if s.dropna().max() < 1.5 else s  # sheet stores fractions
            cw.add(f"sipri_{code}_{tag}", s, name=f"SIPRI military expenditure ({units}), {nm}",
                   category="geopolitics", frequency="A", units=units, country=nm,
                   transform_notes=f"sheet '{sheet}'; '...'/'xxx' -> NaN", url=url)
    raw = pd.read_excel(dest, sheet_name="Regional totals", header=None)
    hdr = raw.index[raw[0].astype(str).str.strip() == "Region"][0]
    cols = raw.iloc[hdr].tolist()
    for _, row in raw.iloc[hdr + 1:].iterrows():
        nm = str(row[0]).strip()
        if nm in ("World", "Europe", "Asia & Oceania", "Americas", "Middle East", "East Asia", "Western Europe"):
            ycols = [j for j, c in enumerate(cols) if re.fullmatch(r"\d{4}(\.0)?", str(c))]
            s = pd.Series(pd.to_numeric(pd.Series([row[j] for j in ycols]), errors="coerce").values,
                          index=[dt.date(int(float(cols[j])), 1, 1) for j in ycols])
            slug = re.sub(r"[^a-z0-9]+", "_", nm.lower()).strip("_")
            cw.add(f"sipri_region_{slug}_const_usd", s, name=f"SIPRI military expenditure, {nm} total",
                   category="geopolitics", frequency="A", units="US$ bn, constant 2024 prices", country=nm,
                   transform_notes="sheet 'Regional totals' (last year at current-year prices per SIPRI note)",
                   url=url)
    return cw.close()


def main(refresh=False, which=None):
    for name, fn in (("maddison", maddison), ("cofer", cofer), ("sipri", sipri)):
        if which and name not in which:
            continue
        try:
            cat = fn(refresh)
            log.info("%s: %d series", name, len(cat))
        except Exception as e:  # noqa: BLE001
            log.error("%s failed: %s", name, e)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(refresh="--refresh" in sys.argv, which=args or None)
