"""Run the full read-only data audit and write the per-series CSV.

    .venv/bin/python -m src.audit.run                       # today, default output paths
    .venv/bin/python -m src.audit.run --today 2026-10-12 --json /tmp/audit.json

Outputs: docs/data/audit_<date>_series.csv (one row per series with findings) and, optionally,
a JSON with every finding and auxiliary table. The markdown report is written by hand from them.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from src.audit import classifier_gaps, cross_source, other_checks, series_checks
from src.audit.common import SEVERITY_ORDER, today
from src.warehouse import db

REPO = Path(__file__).resolve().parents[2]
BASELINE_SOURCES = {"alfred", "bis", "boe_millennium_uk", "damodaran", "fred", "gold", "gpr", "imf_cofer",
                    "jst_macrohistory", "ken_french", "maddison", "nber_macrohistory", "nyfed", "rtdsm",
                    "shiller", "sipri", "spf", "wb_pinksheet"}


def per_series_csv(findings: pd.DataFrame) -> pd.DataFrame:
    f = findings.copy()
    f["rank"] = f["severity"].map(SEVERITY_ORDER)
    f = f.sort_values("rank")
    g = f.groupby(["source", "series_id"], sort=False)
    out = g.agg(severidad_max=("severity", "first"), n_hallazgos=("check", "size"),
                checks=("check", lambda x: "|".join(dict.fromkeys(x))),
                detalle=("detail", lambda x: " || ".join(list(dict.fromkeys(x))[:4])),
                evidencia=("evidence", lambda x: " || ".join(e for e in list(dict.fromkeys(x))[:3] if e)),
                correccion=("fix", lambda x: " || ".join(e for e in dict.fromkeys(x) if e)[:400])).reset_index()
    out["rank"] = out["severidad_max"].map(SEVERITY_ORDER)
    return out.sort_values(["rank", "source", "series_id"]).drop(columns="rank")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--today")
    ap.add_argument("--csv")
    ap.add_argument("--json")
    ap.add_argument("--skip-regime", action="store_true", help="skip the in-memory regime rebuild (slow)")
    a = ap.parse_args()
    t = today(a.today)
    csv = Path(a.csv) if a.csv else REPO / "docs" / "data" / f"audit_{t:%Y-%m-%d}_series.csv"

    findings, aux = [], {}
    f, prof = series_checks.run(t)
    findings += f
    con = db.connect(read_only=True)
    f, gaps = classifier_gaps.analyse(con, t)
    findings += f
    aux["classifier_gaps"] = gaps.to_dict("records")
    if not a.skip_regime:
        aux["regime_impact"] = classifier_gaps.regime_impact(con, t).to_dict("records")
    con.close()
    f, pairs = cross_source.run()
    findings += f
    aux["cross_source"] = pairs.to_dict("records")
    f, info = other_checks.warehouse(t)
    findings += f
    aux["warehouse"] = info
    findings += other_checks.events()
    f, vint = other_checks.vintages_lookahead(t)
    findings += f
    aux["vintages"] = vint.to_dict("records")
    f, lic = other_checks.licences()
    findings += f
    aux["licences"] = lic.to_dict("records")
    aux["dirs"] = other_checks.new_dirs(BASELINE_SOURCES)

    fd = pd.DataFrame([x.row() for x in findings])
    table = per_series_csv(fd[fd["series_id"] != "*"])
    csv.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(csv, index=False)
    if a.json:
        Path(a.json).write_text(json.dumps({"today": str(t.date()), "findings": fd.to_dict("records"),
                                            "profiles": prof.astype(str).to_dict("records"), **aux},
                                           default=str, ensure_ascii=False, indent=1))
    print(f"audit {t.date()}: {len(fd)} hallazgos, {len(table)} series con problemas -> {csv}")
    print(pd.crosstab(fd["source"], fd["severity"]).reindex(columns=list(SEVERITY_ORDER), fill_value=0).to_string())


if __name__ == "__main__":
    main()
