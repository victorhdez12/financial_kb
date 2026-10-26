"""Paso 0a de la fase de factores: qué parte del histórico del clasificador de reglas ≤ 2004 sale de vintages ALFRED
y qué parte de datos revisados (vintage_mode), por serie y por década. Sin factores, sin etiqueta, sin cartera.
Uso: .venv/bin/python -m scripts.factors_paso0_vintages
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from src.regime.asof import month_grid
from src.regime.features import FEATURES, build_panel
from src.regime.run import CORE_VINTAGE, START, vintage_mode
from src.warehouse import db

OUT = Path(__file__).resolve().parents[1] / "research" / "factors"


def main() -> None:
    con = db.connect(read_only=True)
    grid = month_grid(today=date(2004, 12, 31))
    panel, meta = build_panel(con, grid)
    con.close()
    panel = panel[panel.index >= START]
    assert panel.index.max() <= pd.Timestamp("2004-12-31")
    dec = (panel.index.year // 10 * 10).astype(str) + "s"
    vfeat = [f.name for f in FEATURES if f.vintage]
    # % de meses con dato que salen de vintage ALFRED, por serie y década (NaN = sin dato en esa década)
    filas = {}
    for f in vfeat:
        has = panel[f].notna()
        v = panel[f"_v_{f}"].astype(bool) & has
        g = pd.DataFrame({"has": has, "v": v, "dec": dec}).groupby("dec")
        filas[f] = (100 * g["v"].sum() / g["has"].sum().replace(0, float("nan"))).astype(float).round(0)
    tabla = pd.DataFrame(filas).T
    tabla["serie"] = [meta["sources"][f]["series_id"] for f in tabla.index]
    tabla["nucleo_G_I"] = [f in CORE_VINTAGE for f in tabla.index]
    vm = vintage_mode(panel)
    modo = pd.crosstab(dec, vm.fillna("sin dato"), normalize="index").mul(100).round(0)
    primero = {m: str(vm[vm == m].index.min().date()) if (vm == m).any() else None for m in ("mixed", "alfred")}
    OUT.mkdir(parents=True, exist_ok=True)
    res = {"generado": str(pd.Timestamp.now("UTC")), "corte": "2004-12", "por_serie_y_decada_pct_vintage":
           json.loads(tabla.to_json(orient="index")), "vintage_mode_pct_por_decada": json.loads(modo.to_json(orient="index")),
           "primer_mes": primero}
    (OUT / "paso0a_vintages.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(tabla.to_string()); print(); print(modo.to_string()); print(primero)


if __name__ == "__main__":
    main()
