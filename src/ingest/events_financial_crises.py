"""Financial crises chronologies -> events/financial_crises.parquet.

Sources
  * Laeven & Valencia (2018) "Systemic Banking Crises Revisited", IMF WP/18/206, database
    1970-2017 (151 systemic banking crises, currency crises, sovereign debt crises and
    restructurings). IMF's CDN blocks scripted downloads (HTTP 403), so the identical file is
    fetched from the Internet Archive snapshot of the official IMF URL.
  * Reinhart & Rogoff "Global Crises Data by Country" (Behavioral Modern Histories of
    Financial Crises), 70 countries 1800-2016, hosted by HBS Behavioral Finance & Financial
    Stability project. Annual 0/1 dummies -> consecutive years collapsed into episodes.

Types: banking_crisis, currency_crisis, sovereign_default, inflation_crisis.
Annual data: start_date = Jan 1 of first year, end_date = Jan 1 of last year (inclusive year).

Run: .venv/bin/python -m src.ingest.events_financial_crises
"""
from __future__ import annotations

import io
import re
import zipfile

import pandas as pd

from src.ingest._events_common import download, iso3, log, raw_dir, write_events

LV_URLS = [
    "https://www.imf.org/~/media/Files/Publications/WP/2018/datasets/wp18206.ashx",
    "http://web.archive.org/web/20240711232159id_/https://www.imf.org/~/media/Files/"
    "Publications/WP/2018/datasets/wp18206.ashx",
]
LV_PAGE = "https://www.imf.org/en/Publications/WP/Issues/2018/09/14/Systemic-Banking-Crises-Revisited-46232"
RR_URLS = [
    "https://www.hbs.edu/behavioral-finance-and-financial-stability/Documents/ChartData/"
    "GlobalCrisesData/20160923_global_crisis_data.xlsx",
]
RR_PAGE = "https://www.hbs.edu/behavioral-finance-and-financial-stability/data/Pages/global.aspx"


def _y(x) -> int | None:
    m = re.match(r"\s*(\d{4})", str(x))
    return int(m.group(1)) if m else None


def _num(x) -> str:
    try:
        return f"{float(x):.1f}"
    except Exception:  # noqa: BLE001
        return "n/a"


def laeven_valencia(raw) -> list[dict]:
    zp = download(LV_URLS, raw / "wp18206_laeven_valencia_2018.zip", "zip", max_age_hours=24 * 90)
    with zipfile.ZipFile(zp) as z:
        name = [n for n in z.namelist() if n.lower().endswith(".xlsx")][0]
        xb = z.read(name)
    (raw / "SYSTEMIC_BANKING_CRISES_DATABASE_2018.xlsx").write_bytes(xb)
    rows: list[dict] = []

    # banking crises with end dates and costs
    res = pd.read_excel(io.BytesIO(xb), sheet_name="Crisis Resolution and Outcomes", header=0)
    res.columns = ["country", "start", "end", "output_loss", "fiscal_cost", "fiscal_cost_net",
                   "fiscal_cost_fin_assets", "peak_liquidity", "liquidity_support", "peak_npl",
                   "debt_increase"]
    seen = set()
    for _, r in res.iterrows():
        sy = _y(r["start"])
        if sy is None or not isinstance(r["country"], str):
            continue
        cc = iso3(r["country"])
        ey = None if str(r["end"]).strip().lower() == "ongoing" else _y(r["end"])
        seen.add((cc, sy))
        rows.append({
            "event_id": f"lv_bank_{cc}_{sy}",
            "name": f"Systemic banking crisis {re.sub(r'\s*\d+/', '', r['country']).strip()} {sy}",
            "type": "banking_crisis", "country": cc,
            "start_date": f"{sy}-01-01", "end_date": f"{ey}-01-01" if ey else None,
            "severity": f"output_loss_pct_gdp={_num(r['output_loss'])}",
            "source": "laeven_valencia_2018", "url": LV_PAGE,
            "notes": (f"LV2018 systemic banking crisis {sy}-{r['end']}; output loss {_num(r['output_loss'])}% GDP, "
                      f"fiscal cost {_num(r['fiscal_cost'])}% GDP, peak NPLs {_num(r['peak_npl'])}%, "
                      f"public debt +{_num(r['debt_increase'])}% GDP"
                      + ("; end 'ongoing' at 2017" if ey is None else "")),
        })

    yrs = pd.read_excel(io.BytesIO(xb), sheet_name="Crisis Years", header=None).iloc[2:]
    yrs.columns = ["country", "banking", "currency", "sov_debt", "sov_restructuring"]
    kinds = {
        "banking": ("banking_crisis", "Systemic banking crisis"),
        "currency": ("currency_crisis", "Currency crisis"),
        "sov_debt": ("sovereign_default", "Sovereign debt crisis"),
        "sov_restructuring": ("sovereign_default", "Sovereign debt restructuring"),
    }
    for _, r in yrs.iterrows():
        if not isinstance(r["country"], str):
            continue
        cc = iso3(r["country"])
        cname = re.sub(r"\s*\d+/", "", r["country"]).strip()
        for col, (typ, label) in kinds.items():
            for y in re.findall(r"\d{4}", str(r[col])):
                y = int(y)
                if col == "banking" and (cc, y) in seen:
                    continue
                tag = {"banking": "bank", "currency": "fx", "sov_debt": "sovdebt",
                       "sov_restructuring": "sovrestr"}[col]
                rows.append({
                    "event_id": f"lv_{tag}_{cc}_{y}",
                    "name": f"{label} {cname} {y}", "type": typ, "country": cc,
                    "start_date": f"{y}-01-01", "end_date": None,
                    "severity": {"currency": "nominal depreciation >=30% and +10pp vs prior year",
                                 "sov_debt": "default", "sov_restructuring": "restructuring"}.get(col, "systemic"),
                    "source": "laeven_valencia_2018", "url": LV_PAGE,
                    "notes": f"LV2018 crisis years sheet: {label.lower()} starting {y} (end not given)",
                })
    return rows


def reinhart_rogoff(raw) -> list[dict]:
    f = download(RR_URLS, raw / "20160923_global_crisis_data.xlsx", "xlsx", max_age_hours=24 * 90)
    d = pd.read_excel(f)
    d.columns = [str(c).strip() for c in d.columns]
    d = d.iloc[1:].copy()
    d = d[pd.to_numeric(d["Year"], errors="coerce").notna()]
    d["Year"] = d["Year"].astype(float).astype(int)
    ext = [c for c in d.columns if c.startswith("SOVEREIGN EXTERNAL DEBT 1")][0]
    specs = [
        ("Banking Crisis", "banking_crisis", "bank", "Banking crisis"),
        ("Currency Crises", "currency_crisis", "fx", "Currency crisis"),
        ("Inflation Crises", "inflation_crisis", "infl", "Inflation crisis"),
        ("Domestic_Debt_In_Default", "sovereign_default", "domdef", "Domestic sovereign default"),
        (ext, "sovereign_default", "extdef", "External sovereign default/restructuring"),
    ]
    rows: list[dict] = []
    for (cc, country), g in d.groupby(["CC3", "Country"]):
        g = g.sort_values("Year").set_index("Year")
        syst = pd.to_numeric(g["Systemic Crisis"], errors="coerce").fillna(0)
        infl = pd.to_numeric(g.get("Inflation, Annual percentages of average consumer prices"), errors="coerce")
        for col, typ, tag, label in specs:
            flag = pd.to_numeric(g[col], errors="coerce").fillna(0) >= 1
            if not flag.any():
                continue
            years = flag[flag].index.tolist()
            # collapse consecutive years into episodes
            eps, start, prev = [], years[0], years[0]
            for y in years[1:]:
                if y != prev + 1:
                    eps.append((start, prev))
                    start = y
                prev = y
            eps.append((start, prev))
            for s, e in eps:
                n = e - s + 1
                sev = f"duration_years={n}"
                extra = ""
                if typ == "banking_crisis":
                    is_sys = bool(syst.loc[s:e].max() >= 1)
                    sev += ";systemic" if is_sys else ""
                if typ == "inflation_crisis" and infl is not None:
                    pk = infl.loc[s:e].max()
                    if pd.notna(pk):
                        sev += f";peak_inflation_pct={pk:.0f}"
                if typ == "currency_crisis":
                    extra = " (RR: annual depreciation vs USD/anchor >=15%)"
                if typ == "inflation_crisis":
                    extra = " (RR: annual inflation >=20%)"
                rows.append({
                    "event_id": f"rr_{tag}_{str(cc).strip()}_{s}",
                    "name": f"{label} {country} {s}" + (f"-{e}" if e != s else ""),
                    "type": typ, "country": str(cc).strip(),
                    "start_date": f"{s}-01-01", "end_date": f"{e}-01-01",
                    "severity": sev, "source": "reinhart_rogoff", "url": RR_PAGE,
                    "notes": f"Reinhart-Rogoff Global Crises Data ({col[:40]}), years {s}-{e}{extra}",
                })
    return rows


def main() -> None:
    raw = raw_dir("financial_crises")
    lv, rr = laeven_valencia(raw), reinhart_rogoff(raw)
    df = write_events(lv + rr, "financial_crises")
    log.info("financial_crises: LV=%d RR=%d; by source/type:\n%s", len(lv), len(rr),
             df.groupby(["source", "type"]).size().to_string())


if __name__ == "__main__":
    main()
