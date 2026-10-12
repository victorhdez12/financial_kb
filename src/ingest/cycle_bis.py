"""BIS bulk data (data.bis.org flat CSV): credit-to-GDP gaps, debt service ratios, total credit
by sector, central-bank policy rates (monthly) and residential property prices; all countries.

source_id = bis. series_id = bis_<dataset>_<cty>_<codes> (cty = BIS 2-letter code lower case,
e.g. us, xm = euro area, es = Spain, 5r = advanced economies aggregate).
Quarterly obs dated at quarter start (contract), BIS values are end-of-period.

Run: .venv/bin/python -m src.ingest.cycle_bis [--refresh]
"""
from __future__ import annotations

import sys
import zipfile

import pandas as pd

from ._extlong_common import CatalogWriter, download, log, raw_dir

SRC = "bis"
BULK = "https://data.bis.org/static/bulk/{}_csv_flat.zip"
LIC = "BIS statistics, free reuse with attribution (BIS terms of use)"
DATASETS = ["WS_CREDIT_GAP", "WS_DSR", "WS_TC", "WS_CBPOL", "WS_SPP"]
TC_SECTORS = {"P": "private non-financial sector", "H": "households & NPISHs",
              "N": "non-financial corporations", "G": "general government", "C": "non-financial sector"}


def _code(x) -> str:
    return str(x).split(":")[0].strip()


def _label(x) -> str:
    s = str(x)
    return s.split(":", 1)[1].strip() if ":" in s else s


def _date(tp: pd.Series) -> pd.DatetimeIndex:
    tp = tp.astype(str)
    if tp.str.contains("-Q").any():
        return pd.PeriodIndex(tp.str.replace("-Q", "Q"), freq="Q").start_time
    if tp.str.len().max() == 7:
        return pd.PeriodIndex(tp, freq="M").start_time
    return pd.to_datetime(tp)


def _read(rd, ds, usecols=None, filt=None) -> pd.DataFrame:
    z = zipfile.ZipFile(rd / f"{ds}_csv_flat.zip")
    name = z.namelist()[0]
    parts = []
    for ch in pd.read_csv(z.open(name), chunksize=500_000, low_memory=False, usecols=usecols):
        if filt is not None:
            ch = ch[filt(ch)]
        parts.append(ch)
    d = pd.concat(parts)
    d.columns = [c.split(":")[0] for c in d.columns]
    return d.dropna(subset=["TIME_PERIOD", "OBS_VALUE"])


def _emit(cw, d, keys, make_id, make_meta):
    n = 0
    for k, g in d.groupby(keys):
        k = k if isinstance(k, tuple) else (k,)
        s = pd.Series(g["OBS_VALUE"].astype(float).values, index=_date(g["TIME_PERIOD"]))
        sid = make_id(*[_code(x) for x in k])
        name, cat, units, freq = make_meta(g.iloc[0], *[_code(x) for x in k])
        n += cw.add(sid, s, name=name, category=cat, frequency=freq, units=units,
                    country=_label(g.iloc[0][keys[0]]), transform_notes=f"BIS bulk {keys}={k}") > 0
    return n


def main(refresh: bool = False) -> None:
    rd = raw_dir(SRC)
    for ds in DATASETS:
        download(BULK.format(ds), rd / f"{ds}_csv_flat.zip", "zip", min_age_hours=0 if refresh else 20)
    cw = CatalogWriter(SRC, url="https://data.bis.org/", license=LIC)

    # credit-to-GDP gaps: A ratio, B HP trend, C gap
    d = _read(rd, "WS_CREDIT_GAP")
    lab = {"A": "ratio", "B": "trend", "C": "gap"}
    n = _emit(cw, d, ["BORROWERS_CTY", "CG_DTYPE"],
              lambda c, t: f"bis_creditgap_{c.lower()}_{lab.get(t, t.lower())}",
              lambda r, c, t: (f"BIS credit-to-GDP {lab.get(t, t)} (private non-fin, all lenders), {_label(r['BORROWERS_CTY'])}",
                               "credit", "% of GDP (gap: pp vs one-sided HP trend, lambda=400k)", "Q"))
    log.info("credit gap series: %d", n)

    d = _read(rd, "WS_DSR")
    n = _emit(cw, d, ["BORROWERS_CTY", "DSR_BORROWERS"],
              lambda c, b: f"bis_dsr_{c.lower()}_{b.lower()}",
              lambda r, c, b: (f"BIS debt service ratio, {_label(r['DSR_BORROWERS'])}, {_label(r['BORROWERS_CTY'])}",
                               "credit", "% of income", "Q"))
    log.info("dsr series: %d", n)

    def tc_filter(ch):
        b = ch["TC_BORROWERS:Borrowing sector"].astype(str).str[0]
        l = ch["TC_LENDERS:Lending sector"].astype(str).str[0]
        u = ch["UNIT_TYPE:Unit type"].astype(str).str[:3]
        a = ch["TC_ADJUST:Adjustment"].astype(str).str[0]
        return b.isin(list(TC_SECTORS)) & (u == "770") & (a == "A") & (l.isin(["A", "B"]))
    d = _read(rd, "WS_TC", filt=tc_filter)
    d = d[~((d["TC_LENDERS"].astype(str).str[0] == "B") & (d["TC_BORROWERS"].astype(str).str[0] != "P"))]
    n = _emit(cw, d, ["BORROWERS_CTY", "TC_BORROWERS", "TC_LENDERS", "VALUATION"],
              lambda c, b, l, v: f"bis_tc_{c.lower()}_{b.lower()}{l.lower()}_{v.lower()}",
              lambda r, c, b, l, v: (f"BIS total credit to {TC_SECTORS[b]} from {'banks' if l == 'B' else 'all sectors'}"
                                     f" ({_label(r['VALUATION'])}), {_label(r['BORROWERS_CTY'])}",
                                     "fiscal" if b == "G" else "credit", "% of GDP", "Q"))
    log.info("total credit series: %d", n)

    d = _read(rd, "WS_CBPOL", usecols=["FREQ:Frequency", "REF_AREA:Reference area", "TIME_PERIOD:Time period or range",
                                       "OBS_VALUE:Observation Value"],
              filt=lambda ch: ch["FREQ:Frequency"].astype(str).str[0] == "M")
    n = _emit(cw, d, ["REF_AREA"], lambda c: f"bis_cbpol_{c.lower()}",
              lambda r, c: (f"BIS central bank policy rate (monthly, end of period), {_label(r['REF_AREA'])}",
                            "rates", "% per year", "M"))
    log.info("policy rate series: %d", n)

    d = _read(rd, "WS_SPP")
    d = d[d["UNIT_MEASURE"].astype(str).str[:3] == "628"]  # index 2010=100
    n = _emit(cw, d, ["REF_AREA", "VALUE"], lambda c, v: f"bis_spp_{c.lower()}_{v.lower()}",
              lambda r, c, v: (f"BIS residential property price index ({_label(r['VALUE'])}), {_label(r['REF_AREA'])}",
                               "housing", "index 2010=100", "Q"))
    log.info("property price series: %d", n)
    cat = cw.close()
    log.info("bis: %d series", len(cat))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
