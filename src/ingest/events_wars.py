"""Wars -> events/wars.parquet (type=war, severity = battle deaths).

Sources
  * Correlates of War (COW) v4: inter-state (1823-2003), intra-state v4.1 (1818-2014),
    extra-state (1816-2007). https://correlatesofwar.org/data-sets/cow-war/
  * UCDP/PRIO Armed Conflict Dataset v25.1 (1946-2024) + UCDP Battle-Related Deaths v25.1
    (1989-2024). https://ucdp.uu.se/downloads/  Only episodes that reached intensity 2
    (>=1,000 battle deaths in a calendar year) are kept, to match the COW "war" threshold.

COW and UCDP overlap for 1946-2007: both kept (source column tells them apart); for the
modern era prefer source == 'ucdp_prio'.

Run: .venv/bin/python -m src.ingest.events_wars
"""
from __future__ import annotations

import io
import zipfile

import pandas as pd

from src.ingest._events_common import download, is_iso3, iso3, log, raw_dir, write_events

SOURCE = "wars"
COW = "https://correlatesofwar.org/wp-content/uploads/"
FILES = {
    "inter": ("Inter-StateWarData_v4.0.csv", "inter-state"),
    "intra": ("Intra-StateWarData_v4.1.csv", "intra-state"),
    "extra": ("Extra-StateWarData_v4.0.csv", "extra-state"),
}
UCDP_ACD = ["https://ucdp.uu.se/downloads/ucdpprio/ucdp-prio-acd-251-csv.zip"]
UCDP_BRD = ["https://ucdp.uu.se/downloads/brd/ucdp-brd-conf-251-csv.zip"]
COW_PAGE = "https://correlatesofwar.org/data-sets/cow-war/"
UCDP_PAGE = "https://ucdp.uu.se/downloads/"
UCDP_TYPES = {1: "extrasystemic", 2: "interstate", 3: "intrastate", 4: "internationalized intrastate"}


def _d(y, m, d, end: bool = False):
    """COW date; unknown month/day (-9, -8) -> start of the period, or its last day when end=True
    (an end date of 'Apr-1838, day unknown' must not fall before a start on 17-Apr-1838)."""
    try:
        y = int(y)
    except Exception:  # noqa: BLE001
        return None
    if y <= 0:
        return None
    m = int(m) if pd.notna(m) and 1 <= int(m) <= 12 else (12 if end else 1)
    if pd.notna(d) and 1 <= int(d) <= 31:
        d = int(d)
    else:
        d = pd.Timestamp(year=y, month=m, day=1).days_in_month if end else 1
    try:
        return pd.Timestamp(year=y, month=m, day=d).date()
    except ValueError:
        return pd.Timestamp(year=y, month=m, day=1).date()


def _end(r, cols1, cols2):
    e2 = _d(*[r[c] for c in cols2], end=True) if cols2[0] in r else None
    e1 = _d(*[r[c] for c in cols1], end=True)
    return e2 or e1


def _num(x) -> float:
    try:
        v = float(x)
    except Exception:  # noqa: BLE001
        return 0.0
    return v if v > 0 else 0.0


def _codes(names) -> str:
    out = []
    for n in names:
        if not isinstance(n, str) or n.strip() in ("", "-8", "-9"):
            continue
        for part in n.split(","):
            c = iso3(part.strip())
            if is_iso3(c) and c not in out:
                out.append(c)
    return ";".join(out)


def cow_events(raw) -> list[dict]:
    rows: list[dict] = []
    for key, (fname, label) in FILES.items():
        f = download(COW + fname, raw / fname, "csv", max_age_hours=24 * 30)
        df = pd.read_csv(f, encoding="latin-1")
        df.columns = [c.strip() for c in df.columns]
        s1, e1 = ("StartYear1", "StartMonth1", "StartDay1"), ("EndYear1", "EndMonth1", "EndDay1")
        e2 = ("EndYear2", "EndMonth2", "EndDay2")
        df["_start"] = df.apply(lambda r: _d(*[r[c] for c in s1]), axis=1)
        df["_end"] = df.apply(lambda r: _end(r, e1, e2), axis=1)
        if key == "inter":
            df["_deaths"] = df["BatDeath"].map(_num)
            parts = df.groupby("WarNum")["StateName"].apply(list)
        elif key == "intra":
            df["_deaths"] = df["SideADeaths"].map(_num) + df["SideBDeaths"].map(_num)
            parts = df.groupby("WarNum").apply(lambda g: list(g["SideA"]) + list(g["SideB"]),
                                               include_groups=False)
        else:
            df["_deaths"] = df["BatDeath"].map(_num) + df["NonStateDeaths"].map(_num)
            parts = df.groupby("WarNum").apply(lambda g: list(g["SideA"]) + list(g["SideB"]),
                                               include_groups=False)
        for wn, g in df.groupby("WarNum"):
            start = min(x for x in g["_start"] if x) if g["_start"].notna().any() else None
            ends = [x for x in g["_end"] if x]
            if start is None:
                continue
            deaths = g["_deaths"].sum() if key == "inter" else g["_deaths"].max()
            names = [n for n in parts[wn] if isinstance(n, str)]
            rows.append({
                "event_id": f"cow_{key}_{int(wn)}",
                "name": str(g["WarName"].iloc[0]).strip(),
                "type": "war",
                "country": _codes(names),
                "start_date": start,
                "end_date": max(ends) if ends else None,
                "severity": str(int(deaths)) if deaths > 0 else None,
                "source": "cow",
                "url": COW_PAGE,
                "notes": (f"COW {label} war #{int(wn)}; severity = battle deaths "
                          f"({'sum over participants' if key == 'inter' else 'side A+B'}); "
                          f"participants: {', '.join(dict.fromkeys(n.strip() for n in names))[:300]}"),
            })
    return rows


def ucdp_events(raw) -> list[dict]:
    fa = download(UCDP_ACD, raw / "ucdp-prio-acd-251-csv.zip", "zip", max_age_hours=24 * 30)
    fb = download(UCDP_BRD, raw / "ucdp-brd-conf-251-csv.zip", "zip", max_age_hours=24 * 30)

    def read_zip(p):
        with zipfile.ZipFile(p) as z:
            name = [n for n in z.namelist() if n.endswith(".csv")][0]
            return pd.read_csv(io.BytesIO(z.read(name)))

    acd, brd = read_zip(fa), read_zip(fb)
    deaths = brd.groupby(["conflict_id", "year"])["bd_best"].sum()
    rows = []
    for (cid, ep_start), g in acd.groupby(["conflict_id", "start_date2"]):
        if g["intensity_level"].max() < 2:
            continue
        g = g.sort_values("year")
        last = g.iloc[-1]
        ended = int(last["ep_end"]) == 1 and isinstance(last["ep_end_date"], str)
        yrs = list(g["year"])
        bd = sum(deaths.get((cid, y), 0) for y in yrs)
        war_years = g.loc[g["intensity_level"] == 2, "year"].tolist()
        rows.append({
            "event_id": f"ucdp_{int(cid)}_{str(ep_start)[:10]}",
            "name": f"{last['side_a']} vs {last['side_b']}"
                    + (f" ({last['territory_name']})" if isinstance(last["territory_name"], str) else ""),
            "type": "war",
            "country": _codes([last["location"]]),
            "start_date": ep_start,
            "end_date": last["ep_end_date"] if ended else None,
            "severity": str(int(bd)) if bd > 0 else None,
            "source": "ucdp_prio",
            "url": UCDP_PAGE,
            "notes": (f"UCDP/PRIO ACD v25.1 conflict {int(cid)}, {UCDP_TYPES.get(int(last['type_of_conflict']))}; "
                      f"episode years {yrs[0]}-{yrs[-1]}{'' if ended else ' (ongoing at end of data)'}; "
                      f"war-intensity years: {war_years[0]}-{war_years[-1]} ({len(war_years)}); "
                      f"severity = UCDP best battle deaths summed over episode years "
                      f"(BRD only from 1989; empty/understated before)"),
        })
    return rows


def main() -> None:
    raw = raw_dir(SOURCE)
    rows = cow_events(raw) + ucdp_events(raw)
    df = write_events(rows, "wars")
    log.info("wars: cow=%d ucdp=%d, span %s..%s", (df.source == "cow").sum(),
             (df.source == "ucdp_prio").sum(), df.start_date.min(), df.start_date.max())


if __name__ == "__main__":
    main()
