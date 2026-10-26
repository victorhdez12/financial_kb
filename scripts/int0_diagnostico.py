"""INT-0, diagnóstico para el Validador (solo ≤ 2004, todo por src/intl/data.load_dev; sin etiqueta, sin modelos).
(1) Casos raros frente a JST: por país, diferencia del bono por subperiodo (ESP), y bolsa con tres variantes para
    separar causas: precio OCDE solo frente a eq_tr (¿índice de rentabilidad total? → doble conteo del dividendo),
    precio OCDE frente a eq_tr − eq_dp (plusvalía), correlación con desfase de ±1 año (¿año fiscal?), y los 3 años con
    más residuo (¿ruptura de serie?).
(2) Saltos en producción industrial, ventas e IPC: |Δlog mensual| > 8 MAD, huecos dentro de la serie y la
    reunificación alemana (1990-1992).
Uso: .venv/bin/python -m scripts.int0_diagnostico → research/int/diagnostico.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import data as D
from src.intl import panel as P

REPO = Path(__file__).resolve().parents[1]


def casos_jst(a: pd.DataFrame, m: pd.DataFrame, paises=("ESP", "FRA", "DNK", "JPN")) -> dict:
    out = {}
    for c in paises:
        mm, j = m.loc[c], a.loc[c]
        anio = mm.index.year
        bono = (1 + mm["r_bono"]).groupby(anio).prod(min_count=12) - 1
        precio = np.exp(mm["r_bolsa_precio"].groupby(anio).sum(min_count=12)) - 1
        x = pd.DataFrame({"bono": bono, "jst_bono": j["bond_tr"], "precio": precio, "jst_eq": j["eq_tr"],
                          "jst_plusvalia": j["eq_tr"] - j["eq_dp"], "dp": j["eq_dp"]}).loc[1960:2004]
        r = {}
        z = x[["bono", "jst_bono"]].dropna()
        if len(z) >= 10:
            dif = z["bono"] - z["jst_bono"]
            r["bono_dif_pp"] = {k: round(float(dif.loc[a0:a1].mean() * 100), 2)
                                for k, (a0, a1) in {"≤1991": (1960, 1991), "≥1992": (1992, 2004)}.items()
                                if len(dif.loc[a0:a1])}
        z = x[["precio", "jst_eq", "jst_plusvalia", "dp"]].dropna()
        if len(z) >= 10:
            res = (z["precio"] + z["dp"]) - z["jst_eq"]
            r["bolsa"] = {
                "precio_vs_eq_tr": {"corr": round(float(z["precio"].corr(z["jst_eq"])), 3),
                                    "dif_pp": round(float((z["precio"] - z["jst_eq"]).mean() * 100), 2)},
                "precio_vs_plusvalia": {"corr": round(float(z["precio"].corr(z["jst_plusvalia"])), 3),
                                        "dif_pp": round(float((z["precio"] - z["jst_plusvalia"]).mean() * 100), 2)},
                "corr_desfase": {str(k): round(float(z["precio"].corr(z["jst_plusvalia"].shift(k))), 3) for k in (-1, 1)},
                "peores_años": {int(k): round(float(v * 100), 1) for k, v in res.abs().nlargest(3).items()},
                "corr_sin_peor_año": round(float(z.drop(res.abs().idxmax())[["precio", "jst_plusvalia"]].corr().iloc[0, 1]), 3)}
        out[c] = r
    return out


def saltos(s: pd.Series, k: float = 8.0) -> dict:
    s = s.dropna()
    if len(s) < 24:
        return {}
    d = np.log(s).diff().dropna()
    mad = float((d - d.median()).abs().median()) or 1e-12
    big = d[(d - d.median()).abs() > k * 1.4826 * mad]
    full = pd.date_range(s.index.min(), s.index.max(), freq="MS")
    return {"saltos": {f"{t:%Y-%m}": round(float(v), 4) for t, v in big.items()},
            "meses_que_faltan": int(len(full) - len(s)), "desde": f"{s.index.min():%Y-%m}"}


def main() -> None:
    con = D.connect()
    try:
        a, m = P.anual(con), P.mensual(con)
        sal = {}
        for c in D.PAISES:
            lc = c.lower()
            for sid in (f"oecd_ip_{lc}", f"oecd_retail_{lc}", f"oecd_cpi_{lc}_idx", f"oecd_cpicore_{lc}_idx"):
                r = saltos(D.load_dev(con, sid))
                if r and (r["saltos"] or r["meses_que_faltan"]):
                    sal[sid] = r
    finally:
        con.close()
    res = {"casos_jst": casos_jst(a, m), "saltos_y_huecos": sal}
    (REPO / "research" / "int" / "diagnostico.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res["casos_jst"], indent=1, ensure_ascii=False))
    print(f"{len(sal)} series con saltos o huecos (ver research/int/diagnostico.json)")


if __name__ == "__main__":
    main()
