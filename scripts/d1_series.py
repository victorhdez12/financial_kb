"""D1, paso 1: inventario de series diarias ≤ 2004 y periodo de puntuación SOLO por disponibilidad
(docs/factors/D1_tendencia_diaria_spec.md v1.0 §1 y §3). No calcula ninguna rentabilidad de D1 ni ninguna estadística
de rentabilidad de los activos: solo fechas, recuentos y huecos. Escribe research/factors/d1_series.json (se commitea
ANTES de la corrida de desarrollo).
Uso: .venv/bin/python -m scripts.d1_series
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

from src.factors import d1 as M
from src.factors import data as F

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "research" / "factors" / "d1_series.json"

SERIES = {
    "us": {"vivo": "SPY", "series": ["ffx_us_mkt_rf_d", "ffx_us_rf_d"],
           "nota": "mercado EE. UU. de Ken French diario (Mkt-RF + RF), F-F_Research_Data_Factors_daily"},
    "xus": {"vivo": "VEA", "series": ["ffx_devxus_mkt_rf_d", "ffx_devxus_rf_d"],
            "nota": "Ken French «Developed ex US» diario en USD (Mkt-RF + RF); es el mejor índice diario fuera de "
                    "EE. UU. del archivo; cierres asíncronos con EE. UU. (Asia/Europa cierran antes), compuesto al "
                    "calendario de EE. UU. sin perder días"},
    "bonos": {"vivo": "TLT", "series": ["DGS20", "DGS10"],
              "nota": f"r_t = y_(t−1)/252 − {F.D1_DURACION:g}·Δy (duración declarada 17); DGS20 cuando "
                      "existe; DGS10 en el hueco del 20 a (1987-01 a 1993-09); un rendimiento se arrastra como mucho "
                      f"{F.D1_HUECO_MAX} días (festivos del mercado de bonos)"},
    "efectivo": {"vivo": "(cuenta)", "series": ["ffx_us_rf_d"], "nota": "RF diario de Ken French"},
}
EXCLUIDOS = {
    "oro": {"vivo": "GLD", "motivo": (
        "NO hay precio DIARIO del oro ≤ 2004 en el archivo: solo mensual (Banco Mundial, datahub) y anual "
        "(MeasuringWorth). Fuentes públicas probadas el 19-nov-2026 sin éxito: FRED/ALFRED (las series LBMA "
        "GOLDAMGBD228NLBM/GOLDPMGBD228NLBM se retiraron y ALFRED no las conserva), LBMA (prices.lbma.org.uk tras "
        "Cloudflare), Stooq (verificación JavaScript), Bundesbank BBEX3 (solo el fixing de Frankfurt en DEM, "
        "1968-06 a 1998-12, sin serie en USD ni tras 1998)."),
        "bloqueante": True},
    "mp": {"vivo": "DBC", "motivo": (
        "No hay índice diario de materias primas ≤ 2004 en el archivo (GSCI/BCOM no están; AQR y Pink Sheet son "
        "mensuales). El futuro de crudo de la EIA (RCLC1d) es una sola materia prima y un precio sin rentabilidad de "
        "rollo: no es un índice. Se excluye del desarrollo (spec §1)."), "bloqueante": False},
}


def cobertura(s) -> dict:
    v = s.dropna()
    if v.empty:
        return {"desde": None, "hasta": None, "dias": 0}
    tramo = s.loc[v.index.min():v.index.max()]
    return {"desde": str(v.index.min().date()), "hasta": str(v.index.max().date()), "dias": int(len(v)),
            "huecos_dentro": int(tramo.isna().sum())}


def main() -> int:
    con = F.connect()
    try:
        df, rf = F.d1_dev(con)
    finally:
        con.close()
    F.check(df)
    cob = {k: cobertura(df[k]) for k in df.columns} | {"efectivo": cobertura(rf)}
    nucleo_ok = not any(v["bloqueante"] for v in EXCLUIDOS.values())
    out = {
        "documento": "D1: series diarias y periodo de puntuación por disponibilidad (spec v1.0 §1, §3)",
        "spec": "docs/factors/D1_tendencia_diaria_spec.md v1.0 (commit 7d04137)",
        "creado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "git_head": subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True,
                                   text=True).stdout.strip(),
        "corte": str(F.DEV_END.date()),
        "incluidos": {k: {**v, "cobertura": cob[k]} for k, v in SERIES.items()},
        "excluidos": EXCLUIDOS,
        "periodo": None if not nucleo_ok else "pendiente",
        "estado": ("BLOQUEADO: el periodo de §3 exige «al menos bolsa EE. UU., bonos y oro» y L1 (§4) es 70/15/15 con "
                   "oro; sin oro diario ≤ 2004 no se puede fijar el periodo ni L1 sin cambiar el diseño. Decide el "
                   "usuario (opciones en docs/factors/D1_resultado_desarrollo.md). No se ha calculado ninguna "
                   "rentabilidad de D1.") if not nucleo_ok else "listo",
        "calendario": "días hábiles de Ken French EE. UU. (NYSE)",
        "calentamiento_dias": max(M.VENTANAS),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: out[k] for k in ("incluidos", "periodo", "estado")}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
