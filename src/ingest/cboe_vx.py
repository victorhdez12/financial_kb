"""CBOE VIX futures (VX, CFE) term structure -> curated/cboe_vx (docs/DATA_CONTRACT.md).

    .venv/bin/python -m src.ingest.cboe_vx

Per-contract daily settlement files (public, no key):
* new CDN (expiries 2013+):  cdn.cboe.com/data/us/futures/market_statistics/historical_data/VX/VX_<expiry>.csv
* old archive (2004-2014, spotty after): cdn.cboe.com/resources/futures/archive/volume-and-price/CFE_<M><YY>_VX.csv
Only the monthly contracts are used (weeklies ignored). The expiry is computed with the CFE
rule (Wednesday 30 days before the 3rd Friday of the following month) and the CDN is tried at
that date and +-1/2 days (holidays). Per (trade date, contract) the CDN settle wins; the archive
fills gaps. Settle == 0 means "no settlement" -> NaN. Before 2007-03-26 VX was quoted on
10 x VIX: those archive prices are divided by 10.

Built series (date = trade date, settlement ~16:15 ET same day; files are refreshed overnight,
so available t+1):
  cboe_vx_f1..f4      settle of the 1st..4th monthly contract with expiry > trade date
  cboe_vx_dte_f1      calendar days to expiry of the front contract
  cboe_vx_cm30/60/90  constant-maturity VX (linear interpolation in days to expiry; below the
                      front's maturity the front settle is used; no extrapolation beyond the last)
  cboe_vx_slope_f2_f1 F2 - F1 (points; < 0 = backwardation)
  cboe_vx_ratio_cm60_cm30  cm60 / cm30 - 1 (%; < 0 = inverted term structure)
Raw files are kept intact in $FIN_DATA_ROOT/raw/cboe_vx/.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

from src.ingest._extlong_common import CatalogWriter, UA, log, raw_dir

SOURCE = "cboe_vx"
CDN = "https://cdn.cboe.com/data/us/futures/market_statistics/historical_data/VX/VX_{}.csv"
ARCH = "https://cdn.cboe.com/resources/futures/archive/volume-and-price/CFE_{}{:02d}_VX.csv"
PAGE = "https://www.cboe.com/us/futures/market_statistics/historical_data/"
LICENSE = ("Cboe Futures Exchange historical settlement data, free public download; personal "
           "research use, redistribution not permitted without Cboe consent")
CODES = "FGHJKMNQUVXZ"
FIRST = pd.Timestamp("2004-05-01")
SCALE_BREAK = pd.Timestamp("2007-03-26")  # VX re-based from 10xVIX to 1xVIX
OFFSETS = (0, -1, 1, -2, 2)
TODAY = pd.Timestamp.today().normalize()


def vx_expiry(month: pd.Timestamp) -> pd.Timestamp:
    nxt = (month + pd.offsets.MonthBegin(1)).normalize()
    fridays = pd.date_range(nxt, nxt + pd.offsets.MonthEnd(0), freq="W-FRI")
    return fridays[2] - pd.Timedelta(days=30)


def _get(url: str, dest, *, final: bool) -> bytes | None:
    """Cached GET. final=True (contract expired > 7 days ago): cached file/miss marker is final."""
    miss = dest.with_suffix(".missing")
    if final and dest.exists():
        return dest.read_bytes()
    if final and miss.exists():
        return None
    if not final and dest.exists() and (time.time() - dest.stat().st_mtime) < 20 * 3600:
        return dest.read_bytes()
    for i in range(3):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
            break
        except Exception as e:  # noqa: BLE001
            if i == 2:
                log.warning("%s: %s", url, e)
                return dest.read_bytes() if dest.exists() else None
            time.sleep(2 * (i + 1))
    if r.status_code in (403, 404):
        if final:
            miss.write_text("")
        return None
    r.raise_for_status()
    if b"Trade Date" not in r.content[:2000]:  # some archive files start with a disclaimer
        log.warning("unexpected content %s", url)
        return None
    dest.write_bytes(r.content)
    return r.content


def _parse(content: bytes, expiry: pd.Timestamp, src: str) -> pd.DataFrame:
    lines = content.decode("latin1").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("Trade Date"))
    rows = [l.rstrip(",").split(",")[:11] for l in lines[start:] if l.strip().strip(",")]
    d = pd.DataFrame(rows[1:], columns=[c.strip() for c in rows[0][:11]])
    dt = pd.to_datetime(d["Trade Date"].str.strip(), format="mixed", errors="coerce")
    settle = pd.to_numeric(d["Settle"], errors="coerce")
    settle = settle.mask(settle <= 0)
    if src == "arch":
        settle = settle.where(dt >= SCALE_BREAK, settle / 10.0)
    out = pd.DataFrame({"date": dt, "expiry": expiry, "settle": settle.values, "src": src})
    return out.dropna(subset=["date"])


def _contract(month: pd.Timestamp, raw) -> pd.DataFrame:
    exp = vx_expiry(month)
    final = exp < TODAY - pd.Timedelta(days=7)
    parts = []
    if exp.year >= 2013:
        for off in OFFSETS:
            day = exp + pd.Timedelta(days=off)
            c = _get(CDN.format(f"{day:%Y-%m-%d}"), raw / "cdn" / f"VX_{day:%Y-%m-%d}.csv", final=final)
            if c:
                parts.append(_parse(c, day, "cdn"))
                break
    if exp.year <= 2018:
        code = f"{CODES[month.month - 1]}{month.year % 100:02d}"
        c = _get(ARCH.format(CODES[month.month - 1], month.year % 100),
                 raw / "archive" / f"CFE_{code}_VX.csv", final=True)
        if c:
            a = _parse(c, exp, "arch")
            a["expiry"] = a["date"].max()  # final settlement row = actual expiry
            parts.append(a)
    if not parts:
        log.info("no VX file for %s (expiry %s)", month.strftime("%Y-%m"), exp.date())
        return pd.DataFrame()
    df = pd.concat(parts)
    if len(parts) == 2:  # align expiry to the CDN date, CDN wins on overlap
        df["expiry"] = parts[0]["expiry"].iloc[0]
    df = df.sort_values(["date", "src"], key=lambda s: s.map({"cdn": 0, "arch": 1}) if s.name == "src" else s)
    df = df.dropna(subset=["settle"]).drop_duplicates("date", keep="first")
    df["month"] = month
    return df


def load_contracts() -> pd.DataFrame:
    raw = raw_dir(SOURCE)
    (raw / "cdn").mkdir(exist_ok=True)
    (raw / "archive").mkdir(exist_ok=True)
    months = pd.date_range(FIRST, TODAY + pd.DateOffset(months=10), freq="MS")
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda m: _contract(m, raw), months))
    df = pd.concat([r for r in res if not r.empty], ignore_index=True)
    return df[df["date"] < df["expiry"]]  # only contracts still alive at the trade date


def build(df: pd.DataFrame) -> dict[str, pd.Series]:
    df = df[df["date"] <= TODAY].copy()
    df["dte"] = (df["expiry"] - df["date"]).dt.days
    df = df.sort_values(["date", "dte"])
    df["n"] = df.groupby("date").cumcount() + 1
    out = {}
    piv = df.pivot(index="date", columns="n", values="settle")
    for k in range(1, 5):
        out[f"f{k}"] = piv.get(k, pd.Series(dtype=float))
    out["dte_f1"] = df[df["n"] == 1].set_index("date")["dte"].astype(float)

    def cm(g: pd.DataFrame, h: int) -> float:
        x, y = g["dte"].to_numpy(float), g["settle"].to_numpy(float)
        if len(x) < 2 or h > x[-1]:
            return np.nan
        return float(np.interp(h, x, y))  # clamps to the front settle below x[0]

    g = df.groupby("date")
    for h in (30, 60, 90):
        out[f"cm{h}"] = g.apply(lambda d, h=h: cm(d, h))
    out["slope_f2_f1"] = out["f2"] - out["f1"]
    out["ratio_cm60_cm30"] = (out["cm60"] / out["cm30"] - 1) * 100
    return out


META = {
    "f1": ("VIX futures, 1st monthly contract settle", "index points"),
    "f2": ("VIX futures, 2nd monthly contract settle", "index points"),
    "f3": ("VIX futures, 3rd monthly contract settle", "index points"),
    "f4": ("VIX futures, 4th monthly contract settle", "index points"),
    "dte_f1": ("VIX futures, calendar days to expiry of the front contract", "days"),
    "cm30": ("VIX futures, constant-maturity 30 days (interpolated)", "index points"),
    "cm60": ("VIX futures, constant-maturity 60 days (interpolated)", "index points"),
    "cm90": ("VIX futures, constant-maturity 90 days (interpolated)", "index points"),
    "slope_f2_f1": ("VIX futures term slope F2 - F1 (<0 = backwardation)", "index points"),
    "ratio_cm60_cm30": ("VIX futures term slope cm60/cm30 - 1 (<0 = inverted)", "%"),
}
NOTE = ("CFE per-contract settlement files: CDN (expiries 2013+) spliced with the old archive "
        "(2004-2014; CDN wins on overlap); monthly contracts only; contract n = n-th expiry > trade "
        "date (expiring contract excluded on its expiry day); settle 0 -> NaN; archive prices before "
        "2007-03-26 divided by 10 (VX quoted on 10xVIX until then); constant maturities by linear "
        "interpolation in calendar days to expiry, front settle below the front maturity, no "
        "extrapolation. Point-in-time: settlement at ~16:15 ET on the date, available t+1")


def run() -> pd.DataFrame:
    df = load_contracts()
    log.info("VX: %d contract-days, %d contracts, %s -> %s", len(df), df["expiry"].nunique(),
             df["date"].min().date(), df["date"].max().date())
    cw = CatalogWriter(SOURCE, url=PAGE, license=LICENSE)
    for key, s in build(df).items():
        name, units = META[key]
        cw.add(f"cboe_vx_{key}", s, name=name, category="markets", frequency="D", units=units,
               country="US", transform_notes=NOTE)
    return cw.close()


if __name__ == "__main__":
    run()
