"""Jorda-Schularick-Taylor Macrohistory Database (R6), 18 countries, annual 1870-2020.

Run: .venv/bin/python -m src.ingest.jst_macrohistory
Raw:     $FIN_DATA_ROOT/raw/jst_macrohistory/JSTdatasetR6.xlsx
Curated: $FIN_DATA_ROOT/curated/jst_macrohistory/jst_<iso>_<var>.parquet
Events:  $FIN_DATA_ROOT/events/jst_crises.parquet
"""
from __future__ import annotations

import re

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, events_dir, find_link, log, raw_dir

SOURCE = "jst_macrohistory"
PAGE = "https://www.macrohistory.net/database/"
FALLBACK = "https://www.macrohistory.net/app/download/9834512569/JSTdatasetR6.xlsx"
LICENSE = ("CC BY-NC-SA 4.0 (macrohistory.net); cite Jorda, Schularick & Taylor (2017) NBER Macro Annual "
           "and Jorda et al. (2019) QJE 'The Rate of Return on Everything'")

# var -> (name, category, units)
VARS = {
    "pop": ("Population", "growth", "thousands"),
    "rgdpmad": ("Real GDP per capita (Maddison)", "growth", "PPP 1990 USD"),
    "rgdpbarro": ("Real GDP per capita index (Barro)", "growth", "index 2005=100"),
    "rconsbarro": ("Real consumption per capita index (Barro)", "growth", "index 2006=100"),
    "gdp": ("Nominal GDP", "growth", "local currency, billions"),
    "iy": ("Investment-to-GDP ratio", "growth", "ratio"),
    "cpi": ("Consumer prices", "inflation", "index 1990=100"),
    "ca": ("Current account", "growth", "local currency, billions"),
    "imports": ("Imports", "growth", "local currency, billions"),
    "exports": ("Exports", "growth", "local currency, billions"),
    "narrowm": ("Narrow money", "money", "local currency, billions"),
    "money": ("Broad money", "money", "local currency, billions"),
    "stir": ("Short-term interest rate", "rates", "percent p.a."),
    "ltrate": ("Long-term interest rate (gov bonds)", "rates", "percent p.a."),
    "hpnom": ("House prices (nominal index)", "housing", "index 1990=100"),
    "unemp": ("Unemployment rate", "employment", "percent"),
    "wage": ("Wages", "employment", "index 1990=100"),
    "debtgdp": ("Public debt-to-GDP ratio", "fiscal", "ratio"),
    "revenue": ("Government revenues", "fiscal", "local currency, billions"),
    "expenditure": ("Government expenditure", "fiscal", "local currency, billions"),
    "xrusd": ("USD exchange rate (local currency per USD)", "fx", "LCU/USD"),
    "tloans": ("Total loans to non-financial private sector", "credit", "local currency, billions"),
    "tmort": ("Mortgage loans to non-financial private sector", "credit", "local currency, billions"),
    "thh": ("Total loans to households", "credit", "local currency, billions"),
    "tbus": ("Total loans to business", "credit", "local currency, billions"),
    "bdebt": ("Corporate business debt", "credit", "local currency, billions"),
    "lev": ("Bank capital ratio (capital/assets)", "credit", "percent"),
    "ltd": ("Banks loans-to-deposits ratio", "credit", "percent"),
    "noncore": ("Banks noncore funding ratio", "credit", "percent"),
    "crisisJST": ("Systemic banking crisis (start year, 0/1)", "crisis", "dummy"),
    "crisisJST_old": ("Systemic banking crisis, previous chronology (0/1)", "crisis", "dummy"),
    "peg": ("Peg dummy", "fx", "dummy"),
    "peg_strict": ("Strict peg dummy", "fx", "dummy"),
    "JSTtrilemmaIV": ("JST trilemma instrument", "rates", "percentage points"),
    "eq_tr": ("Equity total return, nominal", "equity_returns", "fraction p.a."),
    "housing_tr": ("Housing total return, nominal", "housing", "fraction p.a."),
    "bond_tr": ("Government bond total return, nominal", "bond_returns", "fraction p.a."),
    "bill_rate": ("Bill rate (short safe return), nominal", "rates", "fraction p.a."),
    "rent_ipolated": ("Rent-price ratio, interpolated", "housing", "ratio"),
    "housing_capgain_ipolated": ("Housing capital gain, interpolated", "housing", "fraction p.a."),
    "housing_capgain": ("Housing capital gain", "housing", "fraction p.a."),
    "housing_rent_rtn": ("Housing rental return", "housing", "fraction p.a."),
    "housing_rent_yd": ("Housing rental yield", "housing", "fraction"),
    "eq_capgain": ("Equity capital gain, nominal", "equity_returns", "fraction p.a."),
    "eq_dp": ("Equity dividend-price ratio", "valuation", "ratio"),
    "eq_capgain_interp": ("Equity capital gain, interpolated", "equity_returns", "fraction p.a."),
    "eq_tr_interp": ("Equity total return, interpolated", "equity_returns", "fraction p.a."),
    "eq_dp_interp": ("Equity dividend-price ratio, interpolated", "valuation", "ratio"),
    "bond_rate": ("Government bond yield (JST returns basis)", "rates", "fraction p.a."),
    "eq_div_rtn": ("Equity dividend return", "equity_returns", "fraction p.a."),
    "capital_tr": ("Total return on wealth (weighted)", "equity_returns", "fraction p.a."),
    "risky_tr": ("Total return on risky assets (equity+housing)", "equity_returns", "fraction p.a."),
    "safe_tr": ("Total return on safe assets (bonds+bills)", "bond_returns", "fraction p.a."),
}

CRISIS_NOTE = ("JST chronology (R6): crisisJST=1 marks the first year of a systemic banking crisis; "
               "end year not provided in the dataset")


def fetch():
    dest_dir = raw_dir(SOURCE)
    link = find_link(PAGE, r"JSTdataset.*\.xlsx") or FALLBACK
    m = re.search(r"(JSTdataset\w+\.xlsx)", link)
    dest = dest_dir / (m.group(1) if m else "JSTdataset.xlsx")
    try:
        download(link, dest, "xlsx")
    except Exception as e:  # noqa: BLE001
        log.warning("JST download failed (%s); trying cached", e)
        cands = sorted(dest_dir.glob("JSTdataset*.xlsx"))
        if not cands:
            raise
        dest = cands[-1]
    # documentation (best effort)
    doc = find_link(PAGE, r"JST_documentation.*\.pdf")
    if doc:
        try:
            from src.ingest._extlong_common import http_get
            (dest_dir / "JST_documentation.pdf").write_bytes(http_get(doc).content)
        except Exception as e:  # noqa: BLE001
            log.warning("doc download failed: %s", e)
    return link, dest


def main() -> None:
    url, path = fetch()
    version = re.search(r"R\d+", path.name).group(0) if re.search(r"R\d+", path.name) else "?"
    d = pd.read_excel(path)
    d["date"] = pd.to_datetime(d["year"].astype(int).astype(str) + "-01-01")
    cw = CatalogWriter(SOURCE, url=url, license=LICENSE)
    for iso, g in d.groupby("iso"):
        g = g.set_index("date").sort_index()
        country = g["country"].iloc[0]
        for var, (name, cat, units) in VARS.items():
            if var not in g:
                continue
            cw.add(f"jst_{iso.lower()}_{var.lower()}", g[var], name=f"{country}: {name}", category=cat,
                   frequency="A", units=units, country=iso,
                   transform_notes=f"JST {version}; annual, dated Jan-1 of year")
        # derived ratios
        for num, label in [("tloans", "Private credit"), ("tmort", "Mortgage credit"), ("thh", "Household credit"),
                           ("tbus", "Business credit")]:
            cw.add(f"jst_{iso.lower()}_{num}_gdp", g[num] / g["gdp"], name=f"{country}: {label} / GDP",
                   category="credit", frequency="A", units="ratio", country=iso,
                   transform_notes=f"derived: {num}/gdp (JST {version})")
        cpi = g["cpi"]
        infl = cpi.pct_change(fill_method=None)
        cw.add(f"jst_{iso.lower()}_inflation", infl, name=f"{country}: CPI inflation", category="inflation",
               frequency="A", units="fraction p.a.", country=iso, transform_notes="derived: cpi pct_change")
        for var in ["eq_tr", "bond_tr", "bill_rate", "housing_tr"]:
            cw.add(f"jst_{iso.lower()}_{var.lower()}_real", (1 + g[var]) / (1 + infl) - 1,
                   name=f"{country}: {VARS[var][0]} (real, CPI-deflated)", category=VARS[var][1],
                   frequency="A", units="fraction p.a.", country=iso,
                   transform_notes="derived: (1+nominal)/(1+cpi inflation)-1")
    cat = cw.close()

    # crises events
    cr = d[d["crisisJST"] == 1][["iso", "country", "year"]].sort_values(["iso", "year"])
    ev = pd.DataFrame({
        "event_id": [f"jst_crisis_{i.lower()}_{y}" for i, y in zip(cr.iso, cr.year)],
        "name": [f"Systemic banking crisis {c} {y}" for c, y in zip(cr.country, cr.year)],
        "type": "banking_crisis",
        "country": cr["iso"].values,
        "start_date": pd.to_datetime(cr["year"].astype(str) + "-01-01").dt.date.values,
        "end_date": pd.NaT,
        "severity": "systemic",
        "source": SOURCE,
        "url": "https://www.macrohistory.net/database/",
        "notes": CRISIS_NOTE,
    })
    import pyarrow as pa
    import pyarrow.parquet as pq

    schema = pa.schema([(c, pa.date32() if c.endswith("_date") else pa.string()) for c in ev.columns])
    ev["end_date"] = None
    tbl = pa.Table.from_pandas(ev, schema=schema, preserve_index=False)
    pq.write_table(tbl, events_dir() / "jst_crises.parquet")
    log.info("jst_crises: %d events", len(ev))
    print(f"{len(cat)} series; years {d.year.min()}-{d.year.max()}; {len(ev)} crises")


if __name__ == "__main__":
    main()
