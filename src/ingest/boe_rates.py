"""Bank of England - short-term sterling rates at 3 months (substitute for the OECD UK 3-month rate,
`oecd_ir3m_gbr`, which the OECD stopped publishing after 2026-02; docs/int/GBR_3m_sustituto.md).

Series (monthly, dated at month start like the OECD ones):
- boe_ois3m_m     monthly average of the daily UK OIS (SONIA) spot rate at 3 months, BoE yield-curve data
                  (sheet "spot, short end", maturity 0.25 years; from 2016-01). USED by the live recession
                  thermometer for GBR after the last OECD month (src/report/termometro_vivo.py).
- boe_tbill3m_m   IADB IUMAJNB: monthly average Sterling Treasury bills 3-month discount rate. Discontinued by
                  the BoE in 2017-06 (the DMO stopped publishing T-bill reference prices in July 2017): kept only
                  as reference, it cannot cover 2026.
- boe_sonia_m     IADB IUMASOIA: monthly average SONIA (overnight), for comparison.

Only complete months are curated: the month of the last daily observation (in progress) and months with fewer than
10 daily observations are dropped from boe_ois3m_m.

Run: .venv/bin/python -m src.ingest.boe_rates
Raw:     $FIN_DATA_ROOT/raw/boe_rates/{oisddata.zip, latest-yield-curve-data.zip, iadb_<code>.csv}
Curated: $FIN_DATA_ROOT/curated/boe_rates/boe_*_m.parquet
"""
from __future__ import annotations

import io
import zipfile

import pandas as pd

from src.ingest._extlong_common import CatalogWriter, download, log, raw_dir

SOURCE = "boe_rates"
YC = "https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/"
YC_PAGE = "https://www.bankofengland.co.uk/statistics/yield-curves"
IADB = ("https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom={desde}"
        "&Dateto=now&SeriesCodes={code}&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N")
IADB_PAGE = "https://www.bankofengland.co.uk/boeapps/database/"
# IADB answers an HTML page (not CSV) when Datefrom is far before the series start: one start per series
LICENSE = "Bank of England statistics; free re-use with attribution (BoE terms, Open Government Licence style)"
MIN_DIAS = 10        # a month needs >= 10 daily observations

IADB_SERIES = [  # (series_id, IADB code, Datefrom, name, units)
    ("boe_tbill3m_m", "IUMAJNB", "01/Jan/1970", "UK: monthly average Sterling Treasury bills 3-month discount rate (BoE IADB IUMAJNB; "
                                 "discontinued 2017-06)", "% per annum, monthly average"),
    ("boe_sonia_m", "IUMASOIA", "01/Jan/1996", "UK: monthly average SONIA overnight rate (BoE IADB IUMASOIA)",
     "% per annum, monthly average"),
]


def ois_3m_daily(zbytes: bytes) -> pd.Series:
    """Daily 3-month OIS spot rate from every workbook of a BoE yield-curve zip that has a 'spot, short end' sheet
    with a 0.25-year column (the 2009-2015 workbook starts at 0.5 years: skipped)."""
    out = []
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        for name in sorted(z.namelist()):
            if not (name.startswith("OIS") and name.endswith(".xlsx")):
                continue
            x = pd.ExcelFile(io.BytesIO(z.read(name)))
            hoja = next((h for h in x.sheet_names if "spot, short end" in h), None)
            if hoja is None:
                log.info("boe_rates: %s without short-end spot sheet, skipped", name)
                continue
            d = pd.read_excel(x, hoja, header=None)
            fila = next(i for i, v in d[0].items() if str(v).strip() == "years:")
            anos = pd.to_numeric(d.loc[fila], errors="coerce")
            col = next(i for i, v in anos.items() if abs(v - 0.25) < 1e-6)
            fechas = pd.to_datetime(d[0], errors="coerce", format="mixed")
            s = pd.Series(pd.to_numeric(d[col], errors="coerce").values, index=fechas)
            out.append(s[s.index.notna()].dropna())
    if not out:
        raise ValueError("no OIS short-end spot sheet found in zip")
    s = pd.concat(out).sort_index()
    return s[~s.index.duplicated(keep="last")]


def mensual_completa(daily: pd.Series) -> pd.Series:
    """Monthly average (dated at month start) of complete months only: drops the month of the last observation (in
    progress) and months with fewer than MIN_DIAS observations."""
    daily = daily.dropna()
    if daily.empty:
        return daily
    g = daily.groupby(daily.index.to_period("M"))
    m = g.mean()[g.count() >= MIN_DIAS]
    m = m[m.index < daily.index.max().to_period("M")]
    m.index = m.index.to_timestamp()
    return m


def iadb_monthly(raw: bytes, code: str) -> pd.Series:
    d = pd.read_csv(io.BytesIO(raw))
    if list(d.columns) != ["DATE", code]:
        raise ValueError(f"IADB {code}: unexpected columns {list(d.columns)}")
    idx = pd.DatetimeIndex(pd.to_datetime(d["DATE"], format="%d %b %Y")).to_period("M").to_timestamp()
    return pd.Series(pd.to_numeric(d[code], errors="coerce").values, index=idx)


def main() -> None:
    rd = raw_dir(SOURCE)
    cw = CatalogWriter(SOURCE, url=YC_PAGE, license=LICENSE)
    arch = download(YC + "oisddata.zip", rd / "oisddata.zip", "zip", min_age_hours=20)
    last = download(YC + "latest-yield-curve-data.zip", rd / "latest-yield-curve-data.zip", "zip", min_age_hours=20)
    daily = pd.concat([ois_3m_daily(arch.read_bytes()), ois_3m_daily(last.read_bytes())]).sort_index()
    daily = daily[~daily.index.duplicated(keep="last")]
    m = mensual_completa(daily)
    cw.add("boe_ois3m_m", m, name="UK: monthly average of the daily OIS (SONIA) spot rate at 3 months (BoE yield curves)",
           category="rates", frequency="M", units="% per annum, monthly average", country="GBR",
           transform_notes=f"BoE OIS daily data (oisddata.zip + latest-yield-curve-data.zip), sheet 'spot, short end', "
                           f"maturity 0.25 years; mean of daily values per month, only complete months (>= {MIN_DIAS} "
                           f"days, month of last daily obs {daily.index.max():%Y-%m-%d} dropped); dated at month start. "
                           "Substitute for oecd_ir3m_gbr after 2026-02 (docs/int/GBR_3m_sustituto.md)",
           url=YC + "oisddata.zip")
    for sid, code, desde, name, units in IADB_SERIES:
        url = IADB.format(code=code, desde=desde)
        try:
            f = download(url, rd / f"iadb_{code}.csv", "csv", min_age_hours=20)
        except Exception as e:  # noqa: BLE001
            log.warning("boe_rates: IADB %s failed (%s)", code, e)
            continue
        cw.add(sid, iadb_monthly(f.read_bytes(), code), name=name, category="rates", frequency="M", units=units,
               country="GBR", transform_notes=f"BoE IADB {code}, monthly (month-end dated in source), re-dated at "
                                              "month start", url=url)
    cat = cw.close()
    print(cat[["series_id", "units", "start", "end"]].to_string(index=False))


if __name__ == "__main__":
    main()
