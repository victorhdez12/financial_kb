"""B1′ (docs/factors/B1prima_spec.md v1.0 §3): estima UNA vez los coeficientes log-HAR y σ*′ y los congela con sha256 en
research/paper/b1prima_congelado.json. Datos de desarrollo ≤ 2004 por la única puerta de src/factors/data.load_dev:
- r_USD: mercado de EE. UU. diario de AQR (`aqr_mkt_usa_d`, el mismo que P-DEV-INT12; % → decimal);
- divisa: EUR por USD = DEM por USD (Frankfurt, Bundesbank) / 1,95583 hasta 1998; 1 / EURUSD del BCE desde 1999.
Coeficientes: orígenes 1963-07 … 2004-11 (objetivo hasta 2004-12). σ*′: mediana de σ̂′ en 1963-07 … 2004-12 con los
coeficientes congelados; n del mes siguiente = sesiones observadas (≤ 2004-12) y, para 2004-12, el calendario de la NYSE
(2005-01; es calendario, no dato).

Uso: .venv/bin/python -m scripts.b1prima_congelar            (puerta: árbol limpio; se niega si ya existe la salida)
     .venv/bin/python -m scripts.b1prima_congelar --ensayo    (calcula e imprime; no escribe nada)
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from src.factors import data as F
from src.paper import b1prima as B

SALIDA = B.CONGELADO
DESDE, HASTA_COEF, HASTA_SIGMA = "1963-07", "2004-11", "2004-12"


def cargar_dev(con) -> tuple[pd.Series, dict]:
    r_usd = F.load_dev(con, "aqr_mkt_usa_d") / 100
    dem = F.load_dev(con, "bundesbank_usd_dem_d") / B.EUR_DEM
    ecb = 1 / F.load_dev(con, "ecb_eurusd_d")
    fx = pd.concat([dem[dem.index < "1999-01-01"], ecb[ecb.index >= "1999-01-01"]])
    for s in (r_usd, fx):
        F.check(s)
    r = B.r_eur_diario(r_usd, fx)
    F.check(r)
    huellas = {"aqr_mkt_usa_d": B.sha256_serie(r_usd), "eur_por_usd": B.sha256_serie(fx), "r_eur": B.sha256_serie(r)}
    return r, {"huellas_sha256": huellas, "r_eur_desde": str(r.index.min().date()), "r_eur_hasta": str(r.index.max().date()),
               "n_sesiones": int(len(r))}


def calcular(r: pd.Series) -> dict:
    est = B.estimar(r, DESDE, HASTA_COEF)
    T = est.pop("_tabla")
    Fh = B.rasgos_har(r)
    meses = Fh.index[(Fh.index >= pd.Period(DESDE, "M")) & (Fh.index <= pd.Period(HASTA_SIGMA, "M"))]
    n = pd.Series({m: (int(T.loc[m, "n_dias"]) if m in T.index else B.sesiones_nyse(m + 1)) for m in meses})
    f = B.prevision(Fh.loc[meses, B.HAR].values, n.values, est["beta"], est["duan"])
    sig = pd.Series(B.sigma_prima(f), index=meses)
    p = {"beta": est["beta"], "duan": est["duan"], "sigma_star_prima": float(sig.median())}
    pc = B.parametros_canonicos(p)
    return {"parametros": pc, "sha256_parametros": B.sha256_parametros(pc),
            "estimacion": {k: v for k, v in est.items() if k not in ("beta", "duan")},
            "sigma_prima_dev": {"meses": int(len(sig)), "desde": str(sig.index.min()), "hasta": str(sig.index.max()),
                                "n_mes_siguiente_2004-12_calendario_nyse": int(n.iloc[-1]),
                                "percentiles": {q: round(float(sig.quantile(q / 100)), 4) for q in (5, 25, 50, 75, 95)},
                                "ultimo_2004-12": round(float(sig.iloc[-1]), 4)},
            "recortes_dev": recortes(sig, p["sigma_star_prima"])}


def recortes(sig: pd.Series, s_star: float) -> dict:
    """Propiedad de la señal (sin rentabilidades), como scripts/paper_sigma_star.py para B1."""
    cur, objs = B.ESTRATEGICO["rv"], []
    for x in sig:
        _, cur, _ = B.rv_regla(float(x), cur, s_star)
        objs.append(cur)
    o = pd.Series(objs, index=sig.index)
    rec = o < B.ESTRATEGICO["rv"] - 1e-9
    return {"pct_meses_recortado": round(float(rec.mean()), 3),
            "rv_media_recortado": round(float(o[rec].mean()), 3) if rec.any() else None,
            "cambios_al_año": round(float((o != o.shift()).sum() - 1) / (len(o) / 12), 2)}


def main(argv=None) -> dict:
    argv = sys.argv[1:] if argv is None else argv
    ensayo = "--ensayo" in argv
    if not ensayo:
        if SALIDA.exists():
            raise SystemExit(f"{SALIDA} ya existe: los coeficientes de B1′ se estiman UNA vez y no se re-estiman")
        from src.intl.procedencia import procedencia
        proc = procedencia()
    else:
        proc = {"ensayo": True}
    con = F.connect()
    try:
        r, datos = cargar_dev(con)
    finally:
        con.close()
    o = {"documento": "B1′: coeficientes log-HAR y σ*′ congelados (docs/factors/B1prima_spec.md v1.0 §3)",
         "procedencia": proc, "spec": "docs/factors/B1prima_spec.md v1.0 (2026-10-30)",
         "apertura": {"C1": "research/int/int12_resultado.json h1.contrastes.C1.veredicto = establecido",
                      "aprobacion_usuario": "2026-11-05"},
         "medida": "RV EE. UU. diaria (AQR aqr_mkt_usa_d, exceso sobre letra, como P-DEV-INT12) en EUR: DEM/USD "
                   "Frankfurt/1,95583 ≤ 1998, BCE ≥ 1999; fixing llevado al último conocido en cada sesión",
         "modelo": "log(RV_{M+1}/n_{M+1}) = b0 + b5·lrv5 + b21·lrv21 + b63·lrv63; f = n·exp(·)·duan; σ̂′ = √(12 f)",
         "datos": datos, **calcular(r)}
    txt = json.dumps(o, ensure_ascii=False, indent=1)
    print(txt)
    if not ensayo:
        SALIDA.write_text(txt + "\n")
    return o


if __name__ == "__main__":
    main()
