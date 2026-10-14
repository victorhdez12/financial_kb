"""IMF World Economic Outlook (full database) via the IMF SDMX 3.0 API (api.imf.org, dataflow
IMF.RES/WEO, the latest published vintage).

Raw: the complete WEO (all 210 countries/aggregates x 145 indicators) as SDMX-JSON, plus the
structure (codelists) JSON. Curated: KEY indicators for COUNTRIES (G20 + euro area members ES/NL +
CH + aggregates).

Forecasts are separated from history:
  imf_weo_<iso>_<ind>        years <= PUB_YEAR-1 (realised / latest IMF estimate)
  imf_weo_<iso>_<ind>_proj   years >= PUB_YEAR (IMF projections of that vintage)
PUB_YEAR is the year of the vintage publication (dataset PUBLICATION_DATE, e.g. 2026-04-14 ->
2026). The API does not expose WEO's per-country "estimates start after" year
(LATEST_ACTUAL_ANNUAL_DATA is empty), so the last history year (PUB_YEAR-1) may still be an IMF
estimate for some countries; this is written in transform_notes.

Also exposes `parse_sdmx_json` / `fetch_imf` used by imf_hpdd.py and imf_gdd.py.

Run: .venv/bin/python -m src.ingest.imf_weo [--refresh]
"""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from ._extlong_common import CatalogWriter, log, raw_dir

SRC = "imf_weo"
API = "https://api.imf.org/external/sdmx/3.0/"
UA = "python-requests/2.34 (financial_kb research)"
LIC = "IMF data, free reuse with attribution (IMF copyright and usage terms)"
PAGE = "https://data.imf.org/en/datasets/IMF.RES:WEO"

COUNTRIES = ["USA", "G163", "DEU", "FRA", "ITA", "ESP", "NLD", "GBR", "JPN", "CHN", "CAN", "CHE", "AUS",
             "KOR", "IND", "BRA", "MEX", "RUS", "ZAF", "TUR", "IDN", "SAU", "ARG",
             "G001", "G110", "G200", "G119"]
ISO_OUT = {"G163": "EA", "G001": "WLD", "G110": "ADV", "G200": "EMDE", "G119": "G7"}
INDICATORS = {  # code -> (category, units)
    "NGDP_RPCH": ("growth", "% change, constant prices"),
    "NGDPD": ("growth", "USD billions, current prices"),
    "PPPGDP": ("growth", "international $ billions (PPP), current prices"),
    "PPPSH": ("growth", "% of world GDP (PPP)"),
    "NGDPRPPPPC": ("growth", "international $ per capita, constant prices (PPP)"),
    "NGAP_NPGDP": ("growth", "% of potential GDP"),
    "PCPIPCH": ("inflation", "% change, annual average CPI"),
    "PCPIEPCH": ("inflation", "% change, end-of-period CPI"),
    "LUR": ("employment", "% of labour force"),
    "GGXWDG_NGDP": ("fiscal", "% of GDP"),
    "GGXWDN_NGDP": ("fiscal", "% of GDP"),
    "GGXCNL_NGDP": ("fiscal", "% of GDP"),
    "GGXONLB_NGDP": ("fiscal", "% of GDP"),
    "GGSB_NPGDP": ("fiscal", "% of potential GDP"),
    "GGR_NGDP": ("fiscal", "% of GDP"),
    "GGX_NGDP": ("fiscal", "% of GDP"),
    "BCA_NGDPD": ("growth", "% of GDP"),
    "NGSD_NGDP": ("growth", "% of GDP"),
    "NID_NGDP": ("growth", "% of GDP"),
}


DIV_1E9 = {"NGDPD", "PPPGDP"}


def fetch_imf(url: str, dest: Path, refresh: bool, min_age_hours: float = 20, accept: str | None = None) -> dict:
    """GET an IMF SDMX JSON document, cache it intact in dest, return parsed json."""
    fresh = dest.exists() and (time.time() - dest.stat().st_mtime) / 3600 < min_age_hours
    if refresh or not fresh:
        try:
            h = {"User-Agent": UA}
            if accept:
                h["Accept"] = accept
            for k in range(3):
                try:
                    r = requests.get(url, headers=h, timeout=600)
                    r.raise_for_status()
                    break
                except requests.RequestException:
                    if k == 2:
                        raise
                    time.sleep(10 * (k + 1))
            js = r.json()
            if "data" not in js:
                raise ValueError("no data in response")
            dest.write_bytes(r.content)
            log.info("downloaded %s (%d bytes)", dest.name, len(r.content))
        except Exception as e:  # noqa: BLE001
            if not dest.exists():
                raise
            log.warning("IMF fetch failed (%s); using cached %s", e, dest.name)
    return json.loads(dest.read_text())


def codelist_names(structure: dict) -> dict[str, dict[str, str]]:
    return {cl["id"]: {c["id"]: c.get("name", c["id"]) for c in cl["codes"]}
            for cl in structure["data"].get("codelists", [])}


def parse_sdmx_json(js: dict) -> list[tuple[dict, dict, pd.Series]]:
    """SDMX-JSON 2.0 (dimensionAtObservation=TIME_PERIOD) -> [(dims, series_attrs, annual Series)]."""
    st = js["data"]["structures"][0]
    ds = js["data"]["dataSets"][0]
    sdims = st["dimensions"]["series"]
    times = [v.get("value", v.get("id")) for v in st["dimensions"]["observation"][0]["values"]]
    sattrs = st["attributes"].get("series", [])
    out = []
    for key, s in ds["series"].items():
        idx = [int(i) for i in key.split(":")]
        dims = {d["id"]: d["values"][i]["id"] for d, i in zip(sdims, idx)}
        attrs = {}
        for a, v in zip(sattrs, s.get("attributes", [])):
            if v is None:
                continue
            vals = a.get("values", [])
            attrs[a["id"]] = vals[v].get("id", vals[v].get("value")) if isinstance(v, int) and v < len(vals) else v
        obs = s.get("observations", {})
        if not obs:
            continue
        tp = [times[int(i)] for i in obs]
        vals = [pd.to_numeric(o[0], errors="coerce") if o and o[0] is not None else float("nan") for o in obs.values()]
        ser = pd.Series(vals, index=pd.PeriodIndex([str(t) for t in tp], freq="Y").start_time).sort_index()
        out.append((dims, attrs, ser))
    return out


def main(refresh: bool = False) -> None:
    rd = raw_dir(SRC)
    js = fetch_imf(API + "data/dataflow/IMF.RES/WEO/+/*?dimensionAtObservation=TIME_PERIOD&attributes=series&measures=all",
                   rd / "weo_all.json", refresh)
    stc = fetch_imf(API + "structure/dataflow/IMF.RES/WEO/+?references=descendants", rd / "weo_structure.json",
                    refresh, min_age_hours=24 * 30, accept="application/json")
    names = codelist_names(stc)
    ind_names, cty_names = names.get("CL_WEO_INDICATOR", {}), names.get("CL_WEO_COUNTRY", {})
    # vintage: publication date from a one-series CSV call (dataset-level attribute)
    pub = None
    try:
        r = requests.get(API + "data/dataflow/IMF.RES/WEO/+/USA.NGDP_RPCH.A?attributes=all&measures=all",
                         headers={"User-Agent": UA, "Accept": "application/vnd.sdmx.data+csv;version=2.0.0"}, timeout=120)
        hdr = pd.read_csv(io.StringIO(r.text), nrows=1)
        pub = str(hdr["PUBLICATION_DATE"].iloc[0])[:10]
        (rd / "weo_vintage.txt").write_text(pub + "\n")
    except Exception as e:  # noqa: BLE001
        if (rd / "weo_vintage.txt").exists():
            pub = (rd / "weo_vintage.txt").read_text().strip()
        log.warning("could not read WEO publication date (%s); cached=%s", e, pub)
    if not pub:
        raise RuntimeError("unknown WEO vintage")
    pub_year = int(pub[:4])
    vintage = f"WEO vintage published {pub}"

    cw = CatalogWriter(SRC, url=PAGE, license=LIC)
    n_hist = n_proj = 0
    allseries = parse_sdmx_json(js)
    log.info("WEO raw: %d series, %d obs", len(allseries), sum(len(s) for _, _, s in allseries))
    for dims, attrs, s in allseries:
        c, ind = dims["COUNTRY"], dims["INDICATOR"]
        if c not in COUNTRIES or ind not in INDICATORS:
            continue
        cat, units = INDICATORS[ind]
        iso = ISO_OUT.get(c, c)
        base = f"imf_weo_{iso.lower()}_{ind.lower()}"
        nm = f"IMF WEO {ind_names.get(ind, ind)}, {cty_names.get(c, c)}"
        if ind in DIV_1E9:  # API delivers levels in units; store billions
            s = s / 1e9
        hist = s[s.index.year < pub_year]
        proj = s[s.index.year >= pub_year]
        note = f"{vintage}; scale={attrs.get('SCALE', '?')}; country update {attrs.get('COUNTRY_UPDATE_DATE', '?')}"
        n_hist += cw.add(base, hist, name=nm, category=cat, frequency="A", units=units, country=iso,
                         transform_notes=f"REALISED/ESTIMATE: years < {pub_year}; last year ({pub_year - 1}) may be an IMF "
                                         f"estimate; {note}") > 0
        n_proj += cw.add(base + "_proj", proj, name=nm + " [PROJECTION]", category=cat, frequency="A", units=units,
                         country=iso, transform_notes=f"FORECAST: IMF projections, years >= {pub_year}; {note}") > 0
    cat = cw.close()
    log.info("imf_weo: %d history + %d projection series (%d total)", n_hist, n_proj, len(cat))


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)
