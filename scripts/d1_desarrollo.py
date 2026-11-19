"""D1, paso 2: corrida ÚNICA de desarrollo (≤ 2004) según docs/factors/D1_tendencia_diaria_spec.md v1.0 (CONGELADA).
D1, L1, L2, 1 000 placebos (bloques de 63 días, SEMILLA), mitades, caída, rotación y costes; criterios §5 a)-d).

Fallo cerrado, en este orden (nada calcula rentabilidades antes de pasar los tres):
1. Sellado: el prerregistro congelado (7d04137) debe estar en origin/main (`git merge-base --is-ancestor`).
2. research/factors/d1_series.json debe decir estado = «listo» con un periodo fijado (commiteado antes).
   Hoy dice BLOQUEADO (sin oro diario ≤ 2004): el script se niega.
3. Si research/factors/d1_desarrollo.json ya existe, se niega (re-corrida solo con --recorrida "motivo", bug anotado).
Uso: .venv/bin/python -m scripts.d1_desarrollo [--recorrida "motivo"]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src.factors import d1 as M
from src.factors import data as F

REPO = Path(__file__).resolve().parents[1]
DIR = REPO / "research" / "factors"
SERIES, OUT = DIR / "d1_series.json", DIR / "d1_desarrollo.json"
SPEC_COMMIT = "7d04137"
SEMILLA = 20261119          # declarada antes de correr (fecha de la spec congelada)
N_PLACEBOS = 1000


def git(*a) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True)


def sellado() -> None:
    git("fetch", "-q", "origin")
    if git("merge-base", "--is-ancestor", SPEC_COMMIT, "origin/main").returncode != 0:
        raise SystemExit(f"SELLADO: {SPEC_COMMIT} no está en origin/main (falta que el usuario haga push). No se corre.")


def periodo() -> tuple[pd.Timestamp, pd.Timestamp, list[str]]:
    meta = json.loads(SERIES.read_text())
    if meta.get("estado") != "listo" or not isinstance(meta.get("periodo"), dict):
        raise SystemExit(f"d1_series.json no está listo: {meta.get('estado')}")
    p = meta["periodo"]
    return pd.Timestamp(p["desde"]), pd.Timestamp(p["hasta"]), list(p["activos"])


def correr(desde: pd.Timestamp, hasta: pd.Timestamp, activos: list[str]) -> dict:
    con = F.connect()
    try:
        r_all, rf = F.d1_dev(con)          # el oro (y lo que se añada) debe entrar también por data.py
    finally:
        con.close()
    faltan = [a for a in activos if a not in r_all.columns]
    if faltan:
        raise SystemExit(f"activos sin serie en src/factors/data.py: {faltan}")
    r_all = r_all[activos]
    F.check(r_all)
    s, sig = M.tendencia(r_all), M.volatilidad(r_all)
    dias = r_all.loc[desde:hasta].index
    r = r_all.loc[dias]
    r = r.mask(s.shift(1).loc[dias].isna() & r.isna(), 0.0)   # fuera del universo (peso 0); un hueco dentro falla
    obj = M.objetivos(s, sig)
    d1 = M.simular(r, rf, obj)
    l2 = M.simular(r, rf, M.objetivos(s.where(s.isna(), 1.0), sig))
    o1, reb = M.l1_objetivos(r_all.index, [c for c in activos])
    l1 = M.simular(r, rf, o1, rebalanceo=reb, coste_lado={k: 0.0 for k in activos})
    m = {k: M.metricas(x.neto, rf, x.rotacion) for k, x in (("D1", d1), ("L1", l1), ("L2", l2))}
    m["D1"]["coste_anual"] = float(d1.costes.mean() * 252)
    plac = M.placebos(r, rf, s, sig, N_PLACEBOS, SEMILLA)
    pct = M.percentil_placebo(m["D1"]["sharpe"], plac)
    mit = []
    for ix in M.mitades(dias):
        mit.append({"desde": str(ix[0].date()), "hasta": str(ix[-1].date()),
                    **{k: M.metricas(x.neto.loc[ix], rf) for k, x in (("D1", d1), ("L1", l1), ("L2", l2))}})
    crit = M.criterios(m["D1"], m["L1"], m["L2"], pct, [(x["D1"]["sharpe"], x["L2"]["sharpe"]) for x in mit])
    return {"metricas": m, "placebo": pct, "mitades": mit, "criterios": crit,
            "peso_medio": d1.pesos.mean().round(4).to_dict(), "efectivo_medio": float(1 - d1.pesos.sum(axis=1).mean())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recorrida", help="motivo (bug anotado en research/trial_log.md); nunca cambia el diseño")
    a = ap.parse_args(argv)
    sellado()
    desde, hasta, activos = periodo()
    if OUT.exists() and not a.recorrida:
        raise SystemExit(f"{OUT.name} ya existe: la corrida es única")
    res = correr(desde, hasta, activos)
    out = {"spec": f"docs/factors/D1_tendencia_diaria_spec.md v1.0 ({SPEC_COMMIT})", "semilla": SEMILLA,
           "n_placebos": N_PLACEBOS, "bloque": M.BLOQUE_PLACEBO, "periodo": [str(desde.date()), str(hasta.date())],
           "activos": activos, "corrido": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "git_head": git("rev-parse", "HEAD").stdout.strip(), "recorrida": a.recorrida, **res}
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
