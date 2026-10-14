"""Minneapolis Fed Market-based Probability Densities (options-implied) -> curated/mpls_mpd.

    .venv/bin/python -m src.ingest.mpls_mpd

Source: minneapolisfed.org/-/media/files/banking/mpd/mpd_stats.csv (public, no key), weekly
statistics of risk-neutral distributions of log returns over a fixed horizon
(maturity_target months), estimated from CME / exchange options (dealer quotes when illiquid).
Markets kept: S&P 500 (6m, 12m), 10y/5y Treasury note futures, EUR/GBP/JPY vs USD, gold,
silver, WTI, corn, wheat, soybeans, REIT ETF (iyr), BAC, Citi, CPI caps/floors inflation 1/2/5y
and 3m LIBOR 3y/5y out (the last two families are discontinued).
Per market: mu, sd, skew, p10, p50, p90, prDec, prInc (probability of a "large" move; the size
threshold is in lg_change_decr/incr and, for inflation, the probabilities are P(<1%) / P(>3%)).
Rows whose maturity_target differs from the market's modal one are dropped (a single sp12m
6-month row on 2013-03-07). LIBOR rows have no maturity_target (kept).
date = estimation date (weekly, mostly Wednesdays). Point-in-time: weekly file updates; on
2026-10-14 the last row was 2026-09-30 -> assume up to ~14 days of publication lag.
"""
from __future__ import annotations

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, find_link, log, raw_dir

SOURCE = "mpls_mpd"
PAGE = "https://www.minneapolisfed.org/banking/current-and-historical-market--based-probabilities"
FALLBACK = "https://www.minneapolisfed.org/-/media/files/banking/mpd/mpd_stats.csv"
LICENSE = "Federal Reserve Bank of Minneapolis public data; free use with attribution"
MARKETS = {  # market -> (slug, label, category, country)
    "sp6m": ("spx6m", "S&P 500, 6 months out", "markets", "US"),
    "sp12m": ("spx12m", "S&P 500, 12 months out", "markets", "US"),
    "tr10yr": ("ust10y", "10-year Treasury note futures price", "rates", "US"),
    "tr5yr": ("ust5y", "5-year Treasury note futures price", "rates", "US"),
    "euro": ("eur", "EUR/USD", "fx", "EA"),
    "pound": ("gbp", "GBP/USD", "fx", "GBR"),
    "yen": ("jpy", "JPY/USD", "fx", "JPN"),
    "gold": ("gold", "Gold (CME)", "gold", "US"),
    "silver": ("silver", "Silver (CME)", "commodities", "US"),
    "oil": ("wti", "WTI crude oil (CME)", "commodities", "US"),
    "corn": ("corn", "Corn (CME)", "commodities", "US"),
    "wheat": ("wheat", "Wheat (CME)", "commodities", "US"),
    "soybns": ("soy", "Soybeans (CME)", "commodities", "US"),
    "iyr": ("reit", "iShares US real estate ETF", "markets", "US"),
    "bac": ("bac", "Bank of America", "markets", "US"),
    "citi": ("citi", "Citigroup", "markets", "US"),
    "infl1y": ("infl1y", "CPI inflation 1y (caps/floors)", "inflation", "US"),
    "infl2y": ("infl2y", "CPI inflation 2y (caps/floors)", "inflation", "US"),
    "infl5y": ("infl5y", "CPI inflation 5y (caps/floors)", "inflation", "US"),
    "LR3y3m": ("libor3y", "3m LIBOR 3 years out", "rates", "US"),
    "LR5y3m": ("libor5y", "3m LIBOR 5 years out", "rates", "US"),
}
STATS = {
    "mu": ("mean", "log return (fraction)"), "sd": ("standard deviation", "log return (fraction)"),
    "skew": ("skewness", "unitless"), "p10": ("10th percentile", "log return (fraction)"),
    "p50": ("median", "log return (fraction)"), "p90": ("90th percentile", "log return (fraction)"),
    "prDec": ("probability of a large decline", "probability (0-1)"),
    "prInc": ("probability of a large increase", "probability (0-1)"),
}
INFL_UNITS = {"mu": "rate level (fraction)", "p10": "rate level (fraction)", "p50": "rate level (fraction)", "p90": "rate level (fraction)",
              "sd": "rate level (fraction)"}


def run() -> pd.DataFrame:
    url = find_link(PAGE, r"mpd_stats\.csv") or FALLBACK
    p = download(url, raw_dir(SOURCE) / "mpd_stats.csv", "csv", min_age_hours=20)
    lines = p.read_text(encoding="latin1").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith('"market"'))
    d = pd.read_csv(p, skiprows=start, encoding="latin1")
    d["date"] = pd.to_datetime(d["idt"], format="%m/%d/%Y")
    cw = CatalogWriter(SOURCE, url=PAGE, license=LICENSE)
    for mk, (slug, label, cat, ctry) in MARKETS.items():
        g = d[d["market"] == mk]
        if g.empty:
            log.warning("market %s missing", mk)
            continue
        if g["maturity_target"].notna().any():
            mode = g["maturity_target"].mode().iloc[0]
            g = g[g["maturity_target"] == mode]
            hz = f"{int(mode)}-month horizon"
        else:
            hz = "horizon n/a (LIBOR 3m rate 3/5y out)"
        g = g.set_index("date").sort_index()
        thr = f"thresholds {g['lg_change_decr'].median():g}/{g['lg_change_incr'].median():g}"
        for st, (stname, units) in STATS.items():
            if mk.startswith(("infl", "LR")):
                units = INFL_UNITS.get(st, units)  # inflation/LIBOR MPDs are levels, not returns
            cw.add(f"mpls_mpd_{slug}_{st.lower()}", g[st],
                   name=f"Minneapolis Fed MPD {label}: {stname} ({hz})", category=cat, frequency="W",
                   units=units, country=ctry,
                   transform_notes=(f"options-implied risk-neutral distribution, {hz}; large-move {thr} "
                                    "(lg_change_decr/incr, % change); weekly; PIT lag up to ~14 d"))
    return cw.close()


if __name__ == "__main__":
    run()
