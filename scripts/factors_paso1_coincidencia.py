"""Paso 1 de la fase de factores: coincidencia del clasificador de reglas (congelado) con la etiqueta v1.1, ≤ 2004.
Sin rentabilidades. Etiqueta vía LabelVault (desarrollo, acceso registrado). Muestra 1963-07 → 2004-12.
Regla fijada ANTES de correr: "coinciden poco" si en algún eje la concordancia < 70 % o la kappa de Cohen < 0,40.
Equivalencias: etiqueta G↑ = p_g_high > 0,5; I↑ = p_i_high > 0,5; expansion = Goldilocks (G↑I↓),
late_cycle = Reflación (G↑I↑), stagflation = Estanflación (G↓I↑), low_growth_disinfl = Deflación/recesión (G↓I↓).
Giro de un eje = cambio de estado en la serie mensual; retraso = meses desde el giro de la etiqueta hasta el primer mes
(desde t − 6) en que el clasificador está en el nuevo estado, y la variante "y lo mantiene 3 meses". Sin emparejar en
[t − 6, t + 24] = no detectado.
Uso: .venv/bin/python -m scripts.factors_paso1_coincidencia
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.factors import data as F
from src.models.vault import LabelVault
from src.warehouse import db

OUT = Path(__file__).resolve().parents[1] / "research" / "factors"
DESDE, HASTA = "1963-07", "2004-12"
UMBRAL_CONC, UMBRAL_KAPPA = 0.70, 0.40
QMAP = {"expansion": "Goldilocks", "late_cycle": "Reflación", "stagflation": "Estanflación",
        "low_growth_disinfl": "Deflación/recesión"}


def kappa(a: pd.Series, b: pd.Series) -> float:
    ct = pd.crosstab(a, b)
    n = ct.values.sum()
    po = np.trace(ct.reindex(index=ct.columns, fill_value=0).values) / n if set(ct.index) == set(ct.columns) else \
        (a == b).mean()
    pe = sum((a == k).mean() * (b == k).mean() for k in set(a) | set(b))
    return float((po - pe) / (1 - pe))


def rachas(s: pd.Series) -> dict:
    g = (s != s.shift()).cumsum()
    r = s.groupby(g).agg(["first", "size"])
    return {str(k): {"rachas": int(len(v)), "media_meses": round(float(v["size"].mean()), 1),
                     "mediana_meses": float(v["size"].median())} for k, v in r.groupby("first")}


def retrasos(lab: pd.Series, cla: pd.Series, mantener: int) -> dict:
    giros = lab.index[(lab != lab.shift()) & lab.shift().notna()]
    out = []
    for t in giros:
        nuevo = lab.loc[t]
        i0 = lab.index.get_loc(t)
        lag = None
        for k in range(-6, 25):
            j = i0 + k
            if j < 0 or j + mantener > len(cla):
                continue
            if (cla.iloc[j:j + mantener] == nuevo).all():
                lag = k
                break
        out.append({"giro": str(t)[:7], "a": str(nuevo), "retraso": lag})
    lags = [o["retraso"] for o in out if o["retraso"] is not None]
    return {"giros": len(out), "detectados": len(lags), "mediana": float(np.median(lags)) if lags else None,
            "media": round(float(np.mean(lags)), 1) if lags else None, "detalle": out}


def main() -> None:
    lab = LabelVault("development").load(end=f"{HASTA}-31")
    lab.index = lab.index.to_period("M")
    con = db.connect(read_only=True)
    cla = con.execute("select date, G_state, I_state, quadrant from regime_monthly where date <= ?",
                      [F.DEV_END.date()]).df()
    con.close()
    cla["date"] = pd.to_datetime(cla["date"]).dt.to_period("M")
    cla = cla.set_index("date")
    idx = pd.period_range(DESDE, HASTA, freq="M")
    lab, cla = lab.reindex(idx), cla.reindex(idx)
    L = pd.DataFrame({"G": np.where(lab["p_g_high"] > 0.5, "up", "down"),
                      "I": np.where(lab["p_i_high"] > 0.5, "up", "down"),
                      "Q": lab["label_hard"].map(QMAP), "frontera": lab["frontera"].astype(bool)}, index=idx)
    C = pd.DataFrame({"G": cla["G_state"], "I": cla["I_state"], "Q": cla["quadrant"]}, index=idx)
    ok = C.notna().all(axis=1) & L["Q"].notna()
    L, C = L[ok], C[ok]
    res = {"muestra": f"{L.index.min()} → {L.index.max()}", "meses": int(len(L)),
           "regla_poco": f"concordancia < {UMBRAL_CONC} o kappa < {UMBRAL_KAPPA} en algún eje"}
    for eje in ("G", "I", "Q"):
        sub = {"todos": slice(None), "sin_frontera": ~L["frontera"].values}
        res[eje] = {}
        for k, m in sub.items():
            a, b = L[eje][m], C[eje][m]
            res[eje][k] = {"concordancia": round(float((a == b).mean()), 3), "kappa": round(kappa(a, b), 3),
                           "matriz (filas etiqueta, columnas clasificador)": pd.crosstab(a, b).to_dict(orient="index")}
        res[eje]["duracion_etiqueta"] = rachas(L[eje])
        res[eje]["duracion_clasificador"] = rachas(C[eje])
        if eje != "Q":
            res[eje]["retraso"] = retrasos(L[eje], C[eje], 1)
            res[eje]["retraso_mantiene_3m"] = retrasos(L[eje], C[eje], 3)
    poco = any(res[e]["todos"]["concordancia"] < UMBRAL_CONC or res[e]["todos"]["kappa"] < UMBRAL_KAPPA
               for e in ("G", "I"))
    res["coinciden_poco"] = bool(poco)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "paso1_coincidencia.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    for e in ("G", "I", "Q"):
        print(e, {k: (v["concordancia"], v["kappa"]) for k, v in res[e].items() if k in ("todos", "sin_frontera")})
        print("  matriz:", res[e]["todos"]["matriz (filas etiqueta, columnas clasificador)"])
        print("  duración etiqueta:", res[e]["duracion_etiqueta"])
        print("  duración clasificador:", res[e]["duracion_clasificador"])
        if e != "Q":
            for k in ("retraso", "retraso_mantiene_3m"):
                r = res[e][k]
                print(f"  {k}: giros {r['giros']}, detectados {r['detectados']}, mediana {r['mediana']}, media {r['media']}")
    print("COINCIDEN POCO:", poco)


if __name__ == "__main__":
    main()
