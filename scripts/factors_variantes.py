"""Selección de las (máx.) 3 variantes de la regla de cartera SOLO con propiedades de la señal (sin rentabilidades).
Regla fijada y commiteada ANTES de calcular nada (decisión del usuario, 26-oct):

Señal: G numérico del clasificador de reglas (regime_monthly.G, congelado). Estado DEFENSIVO cuando G < θ durante
k meses seguidos; vuelve a NORMAL cuando G ≥ θ durante k meses seguidos (exigencia de duración = histéresis en la regla,
el clasificador no se toca). Malla: θ ∈ {−0,5, −0,25, 0, 0,25}, k ∈ {1, 2, 3, 6}.
Propiedades (1963-07 → 2004-12, y 1975-01 → 2004-12 informativo): cambios de estado al año, duración media de cada
estado, % del tiempo en DEFENSIVO, κ de Cohen frente a la etiqueta (DEFENSIVO ↔ etiqueta G↓, p_g_high ≤ 0,5).
Elegibles: ≤ 1,0 cambios al año y DEFENSIVO entre el 10 % y el 50 % del tiempo.
- V1 = elegible con mayor κ.
- V2 = elegible con mayor κ entre las de θ distinto de V1 (robustez al umbral).
- V3 = ancla a priori θ = 0, k = 3; si no es elegible o coincide con V1/V2, la elegible siguiente por κ.
Empates por κ: menos cambios al año; después θ más cercano a 0.
Uso: .venv/bin/python -m scripts.factors_variantes
"""
from __future__ import annotations

import json
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

from src.factors import data as F
from src.models.vault import LabelVault
from src.warehouse import db

OUT = Path(__file__).resolve().parents[1] / "research" / "factors"
THETAS, KS = (-0.5, -0.25, 0.0, 0.25), (1, 2, 3, 6)
MAX_CAMBIOS, DEF_MIN, DEF_MAX = 1.0, 0.10, 0.50


def estado(g: pd.Series, theta: float, k: int) -> pd.Series:
    """True = DEFENSIVO. Cambia solo tras k meses seguidos al otro lado de θ (causal)."""
    out, cur, run_bajo, run_alto = [], False, 0, 0
    for v in g:
        if np.isnan(v):
            out.append(cur); continue
        run_bajo, run_alto = (run_bajo + 1, 0) if v < theta else (0, run_alto + 1)
        if not cur and run_bajo >= k:
            cur = True
        elif cur and run_alto >= k:
            cur = False
        out.append(cur)
    return pd.Series(out, index=g.index)


def kappa(a: pd.Series, b: pd.Series) -> float:
    po = (a == b).mean()
    pe = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())
    return float((po - pe) / (1 - pe))


def props(s: pd.Series, lab: pd.Series) -> dict:
    cambios = int((s != s.shift()).sum() - 1)
    runs = s.groupby((s != s.shift()).cumsum()).agg(["first", "size"])
    return {"cambios_año": round(cambios / (len(s) / 12), 2), "pct_defensivo": round(float(s.mean()), 3),
            "dur_def": round(float(runs[runs["first"]]["size"].mean()), 1) if s.any() else None,
            "dur_normal": round(float(runs[~runs["first"]]["size"].mean()), 1) if (~s).any() else None,
            "kappa": round(kappa(s, lab), 3)}


def main() -> None:
    con = db.connect(read_only=True)
    cla = con.execute("select date, G from regime_monthly where date <= ?", [F.DEV_END.date()]).df()
    con.close()
    cla["date"] = pd.to_datetime(cla["date"]).dt.to_period("M")
    g_all = cla.set_index("date")["G"]
    lab = LabelVault("development").load(end="2004-12-31")
    lab.index = lab.index.to_period("M")
    filas = []
    for th, k in product(THETAS, KS):
        s_all = estado(g_all, th, k)                    # se calcula sobre toda la historia causal ≤ 2004
        fila = {"theta": th, "k": k}
        for nom, desde in (("1963", "1963-07"), ("1975", "1975-01")):
            idx = pd.period_range(desde, "2004-12", freq="M")
            s = s_all.reindex(idx)
            lb = (lab["p_g_high"].reindex(idx) <= 0.5)
            ok = s.notna() & lab["p_g_high"].reindex(idx).notna()
            fila[nom] = props(s[ok].astype(bool), lb[ok])
        p = fila["1963"]
        fila["elegible"] = p["cambios_año"] <= MAX_CAMBIOS and DEF_MIN <= p["pct_defensivo"] <= DEF_MAX
        filas.append(fila)
    orden = lambda f: (-f["1963"]["kappa"], f["1963"]["cambios_año"], abs(f["theta"]))
    eleg = sorted([f for f in filas if f["elegible"]], key=orden)
    v = {}
    if eleg:
        v["V1"] = eleg[0]
        resto = [f for f in eleg if f["theta"] != v["V1"]["theta"]]
        if resto:
            v["V2"] = resto[0]
        usados = [(x["theta"], x["k"]) for x in v.values()]
        ancla = next((f for f in eleg if f["theta"] == 0.0 and f["k"] == 3), None)
        if ancla is not None and (0.0, 3) not in usados:
            v["V3"] = ancla
        else:
            sig = [f for f in eleg if (f["theta"], f["k"]) not in usados]
            if sig:
                v["V3"] = sig[0]
    res = {"regla": __doc__, "malla": filas, "variantes": {k: {"theta": x["theta"], "k": x["k"]} for k, x in v.items()}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "variantes_senal.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    for f in filas:
        print(f"θ={f['theta']:+.2f} k={f['k']}  {f['1963']}  eleg={f['elegible']}")
    print("VARIANTES:", res["variantes"])


if __name__ == "__main__":
    main()
