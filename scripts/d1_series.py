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
    "oro": {"vivo": "GLD", "series": ["raw/gold/fred_GOLDPMGBD228NLBM_archive_20171122.txt"],
            "nota": "fixing LBMA de la tarde (15:00 Londres) en USD/oz, serie FRED GOLDPMGBD228NLBM (copia de "
                    f"archive.org, sha256 {F.SHA_ORO_D[:12]}…; LEEME_oro_diario.md); aprobado por el usuario (opción A, "
                    "sin cambio de diseño). Festivo de Londres ('.') → precio arrastrado ≤ 5 días: rentabilidad 0 ese día "
                    "y el cambio entra el siguiente con fixing; cierre asíncrono (15:00 Londres frente a 16:00 Nueva York)"},
    "efectivo": {"vivo": "(cuenta)", "series": ["ffx_us_rf_d"], "nota": "RF diario de Ken French"},
}
EXCLUIDOS = {
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
    # periodo SOLO por disponibilidad: primer día de decisión con 252 rentabilidades seguidas de bolsa EE. UU., bonos
    # y oro (recuento de datos, no valores); se puntúa desde el día siguiente hasta el corte
    nucleo = ["us", "bonos", "oro"]
    listo = df[nucleo].notna().rolling(max(M.VENTANAS)).sum().eq(max(M.VENTANAS)).all(axis=1)
    primero_dec = listo.idxmax()
    dias = df.index[df.index > primero_dec]
    huecos = {k: int(df.loc[dias, k].isna().sum()) for k in nucleo}
    if any(huecos.values()):
        raise SystemExit(f"huecos dentro del periodo en {huecos}: no se fija el periodo")
    xus_dec = df["xus"].notna().rolling(max(M.VENTANAS)).sum().eq(max(M.VENTANAS)).idxmax()
    out = {
        "documento": "D1: series diarias y periodo de puntuación por disponibilidad (spec v1.0 §1, §3)",
        "spec": "docs/factors/D1_tendencia_diaria_spec.md v1.0 (commit 7d04137)",
        "creado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "git_head": subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True,
                                   text=True).stdout.strip(),
        "corte": str(F.DEV_END.date()),
        "incluidos": {k: {**v, "cobertura": cob[k]} for k, v in SERIES.items()},
        "excluidos": EXCLUIDOS,
        "periodo": {"desde": str(dias[0].date()), "hasta": str(dias[-1].date()), "dias": int(len(dias)),
                    "activos": ["us", "xus", "bonos", "oro"],
                    "primer_dia_decision": str(primero_dec.date()),
                    "xus_entra_tras_su_calentamiento": str(xus_dec.date()),
                    "regla": "primer día con 252 rentabilidades de bolsa EE. UU., bonos y oro; el día siguiente se "
                             "puntúa; fuera de EE. UU. pesa 0 (y no cuenta en N) hasta tener su historia completa"},
        "estado": "listo",
        "calendario": "días hábiles de Ken French EE. UU. (NYSE)",
        "calentamiento_dias": max(M.VENTANAS),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: out[k] for k in ("incluidos", "periodo", "estado")}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
