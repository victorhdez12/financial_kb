"""INT-2: cálculo de potencia del mapa régimen → activos con el panel ANUAL (≤ 2004), ANTES de construir INT-3.
Solo usa: (i) cuántos país-años y rachas hay en cada cuadrante y en recesión (etiquetas de INT-1, núcleo de 14 países), y
(ii) estadísticos INCONDICIONALES de las rentabilidades reales anuales de JST (desviación típica agrupada, correlación media
entre países en el mismo año, AR(1)). NO cruza rentabilidades con regímenes.
MDE (80 %, bilateral 5 %) de la diferencia de rentabilidad real media anual entre un estado y el resto, con efecto de
diseño por agrupación en años: n_ef = n / (1 + (m − 1)·ρ), m = país-años medios por año en ese estado, ρ = correlación
media entre países; y corrección por AR(1). Periodos: 1870-2004 y 1950-2004.
Uso: .venv/bin/python -m scripts.int2_potencia
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.intl import data as D
from src.intl import panel as P
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
PRUEBA = {"AUS", "CHE", "CAN", "IRL"}
NUCLEO = [c for c in D.PAISES if c not in PRUEBA]
ACTIVOS = {"bolsa": "eq_tr_real", "bonos": "bond_tr_real", "letras": "bill_rate_real", "vivienda": "housing_tr_real"}
Z = 2.80


def main() -> None:
    con = D.connect()
    a = P.anual(con)
    con.close()
    et = pd.read_parquet(db.DATA_ROOT / "intl" / "regimen_anual_dev.parquet")
    rec = pd.read_parquet(db.DATA_ROOT / "intl" / "recesiones_anuales_dev.parquet")
    et = et[et.pais.isin(NUCLEO) & et.cuadrante.notna() & ~et.truncada]
    a = a.loc[a.index.get_level_values(0).isin(NUCLEO)]
    en_rec = set()
    for _, r in rec[rec.pais.isin(NUCLEO)].iterrows():
        for y in range(int(r.pico) + 1, int(r.valle) + 1):
            en_rec.add((r.pais, y))
    res = {"nucleo": NUCLEO}
    for nom, desde in (("1870_2004", 1870), ("1950_2004", 1950)):
        e = et[et.año >= desde]
        estados = {q: set(zip(e[e.cuadrante == q].pais, e[e.cuadrante == q].año))
                   for q in ("expansion", "sobrecalentamiento", "estanflacion", "crecimiento_bajo")}
        todos = set(zip(e.pais, e.año))
        estados["recesion"] = {k for k in en_rec if k in todos}
        stats = {}
        for act, col in ACTIVOS.items():
            x = a[col].dropna()
            x = x[x.index.get_level_values(1) >= desde]
            ancho = x.unstack(0)
            pares = [ancho[[i, j]].dropna().corr().iloc[0, 1] for i, j in itertools.combinations(ancho.columns, 2)
                     if ancho[[i, j]].dropna().shape[0] >= 20]
            ar1 = float(np.nanmean([ancho[c].dropna().autocorr(1) for c in ancho.columns if ancho[c].dropna().size > 20]))
            stats[act] = {"sd": float(x.std()), "rho_paises": float(np.nanmean(pares)), "ar1": ar1, "n": int(x.size)}
        mde = {}
        for q, s1 in estados.items():
            fila = {}
            for act, st in stats.items():
                col = ACTIVOS[act]
                disp = set(a[col].dropna().index)
                g1 = [k for k in s1 if k in disp]
                g0 = [k for k in todos - s1 if k in disp]
                if len(g1) < 10:
                    continue
                def n_ef(g):
                    m = pd.Series([y for _, y in g]).value_counts().mean()
                    de = 1 + (m - 1) * st["rho_paises"]
                    return len(g) / de * (1 - st["ar1"]) / (1 + st["ar1"])
                n1, n0 = n_ef(g1), n_ef(g0)
                d = Z * st["sd"] * np.sqrt(1 / n1 + 1 / n0)
                fila[act] = {"pais_años": len(g1), "n_efectivo": round(n1, 1), "mde_pp": round(100 * d, 1),
                             "mde_en_sd": round(d / st["sd"], 2)}
            mde[q] = fila
        res[nom] = {"estadisticos_incondicionales": {k: {kk: round(v, 3) if isinstance(v, float) else v for kk, v in s.items()}
                                                      for k, s in stats.items()},
                    "pais_años": {q: len(s) for q, s in estados.items()}, "mde": mde}
    (REPO / "research" / "int" / "int2_potencia.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    for nom in ("1870_2004", "1950_2004"):
        print("==", nom, res[nom]["pais_años"])
        print("  incondicional:", res[nom]["estadisticos_incondicionales"])
        for q, f in res[nom]["mde"].items():
            print(f"  {q:20s}", {k: (v['n_efectivo'], v['mde_pp']) for k, v in f.items()})


if __name__ == "__main__":
    main()
