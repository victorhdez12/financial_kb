"""S1, paso 3: corrida ÚNICA de desarrollo (≤ 2004) según docs/factors/S1_rotacion_sectorial_spec.md v1.0 (CONGELADA).
S1, L0, 1 000 placebos barajados por bloques de 12 meses (semilla de research/factors/s1_senal.json), mitades, caída
máxima, rotación, costes y cuadrantes por año; criterios §5 a)-d).

Fallo cerrado: la señal se lee de research/factors/s1_senal.csv y su sha256 debe coincidir con el de s1_senal.json
(commiteado antes de calcular rentabilidades). Si research/factors/s1_desarrollo.json ya existe, se niega a correr: una
re-corrida solo con `--recorrida "motivo"` (bug anotado en el registro; no puede tocar el diseño).
Uso: .venv/bin/python -m scripts.s1_desarrollo [--recorrida "motivo"]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.factors import data as F
from src.factors import s1 as S

REPO = Path(__file__).resolve().parents[1]
DIR = REPO / "research" / "factors"
SENAL_JSON, SENAL_CSV, OUT = DIR / "s1_senal.json", DIR / "s1_senal.csv", DIR / "s1_desarrollo.json"


def git(*a) -> str:
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True).stdout.strip()


def cargar_senal() -> tuple[pd.Series, dict]:
    meta = json.loads(SENAL_JSON.read_text())
    sha = hashlib.sha256(SENAL_CSV.read_bytes()).hexdigest()
    if sha != meta["csv_sha256"]:
        raise RuntimeError(f"s1_senal.csv no coincide con su sha256 congelado ({sha} ≠ {meta['csv_sha256']})")
    df = pd.read_csv(SENAL_CSV, parse_dates=["date"])
    q = pd.Series(df["quadrant"].where(df["quadrant"].notna(), None).values,
                  index=pd.PeriodIndex(df["date"], freq="M"), dtype=object)
    return q, meta


def rentabilidades(desde: str, hasta: str) -> tuple[pd.DataFrame, pd.Series]:
    con = F.connect()
    try:
        ind = F.industrias12_dev(con)
        mkt, rf = F.mercado_dev(con)
    finally:
        con.close()
    r = ind.copy()
    r.insert(0, "mkt", mkt.reindex(ind.index))
    r.index = r.index.to_period("M")
    rf.index = rf.index.to_period("M")
    idx = pd.period_range(desde, hasta, freq="M")
    r, rf = r.reindex(idx), rf.reindex(idx)
    if r.isna().any().any() or rf.isna().any():
        raise RuntimeError("huecos en rentabilidades del periodo puntuado")
    return r, rf


def redondea(x):
    if isinstance(x, dict):
        return {k: redondea(v) for k, v in x.items()}
    if isinstance(x, list):
        return [redondea(v) for v in x]
    if isinstance(x, float):
        return round(x, 6)
    return x


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recorrida", help="motivo (bug anotado); sin él no se corre dos veces")
    a = ap.parse_args(argv)
    if OUT.exists() and not a.recorrida:
        print(f"{OUT.relative_to(REPO)} ya existe: S1 tiene UNA corrida de desarrollo. --recorrida 'motivo' solo por bug.")
        return 3
    senal, meta = cargar_senal()
    desde, hasta = meta["puntuacion"]["desde"], meta["puntuacion"]["hasta"]
    pl = meta["placebos"]
    r, rf = rentabilidades(desde, hasta)
    res = S.simular(r, senal)
    s1, l0 = res.neto, r["mkt"]
    años = len(r) / 12
    m_s1, m_l0 = S.metricas(s1, rf), S.metricas(l0, rf)
    m_s1.update({"rotacion_anual": float(res.rotacion.sum() / años), "coste_anual": float(res.costes.sum() / años),
                 "operaciones": int((res.rotacion > 0).sum())})
    m_l0.update({"rotacion_anual": 0.0, "coste_anual": 0.0, "operaciones": 0})
    act = S.activa(s1, l0)
    act["activa_bruta_arit"] = float((res.bruto - l0).mean() * 12)
    plac = S.placebos(r, senal, l0, pl["n"], pl["bloque_meses"], pl["semilla"])
    pct = S.percentil_placebo(act["activa_arit"], plac["activa_arit"])
    pct_geo = S.percentil_placebo(act["activa_geo"], plac["activa_geo"])
    mit = []
    for h in S.mitades(r.index):
        mit.append({"desde": str(h[0]), "hasta": str(h[-1]), **S.activa(s1.loc[h], l0.loc[h]),
                    "s1": S.metricas(s1.loc[h], rf), "l0": S.metricas(l0.loc[h], rf)})
    crit = S.criterios(act, pct, mit, m_s1["caida_max"], m_l0["caida_max"])
    # tablas informativas: por año (cuadrante vigente en meses, rentabilidades) y por cuadrante vigente
    por_año = {}
    for y in sorted(set(r.index.year)):
        k = r.index[r.index.year == y]
        vc = res.cuadrante.loc[k].value_counts()
        por_año[int(y)] = {"meses_por_cuadrante": {q: int(vc.get(q, 0)) for q in S.SECTORES},
                           "s1": float(np.prod(1 + s1.loc[k]) - 1), "l0": float(np.prod(1 + l0.loc[k]) - 1),
                           "operaciones": int((res.rotacion.loc[k] > 0).sum())}
    por_cuadrante = {}
    for q in S.SECTORES:
        k = res.cuadrante.index[res.cuadrante == q]
        d = (s1.loc[k] - l0.loc[k])
        por_cuadrante[q] = {"meses": int(len(k)), "activa_arit": float(d.mean() * 12) if len(k) else None}
    out = {
        "documento": "S1 corrida de desarrollo (≤ 2004)", "spec": meta["spec"],
        "generado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "git_head": git("rev-parse", "HEAD"), "recorrida": a.recorrida,
        "senal": {"csv_sha256": meta["csv_sha256"], "git_head_senal": meta["git_head_codigo"]},
        "periodo": {"desde": desde, "hasta": hasta, "meses": len(r)},
        "s1": m_s1, "l0": m_l0, "activa": act,
        "placebos": {**pl, "activa_arit": pct, "activa_geo": pct_geo,
                     "cambios_medios": float(plac["cambios"].mean()), "ir_p95": float(plac["ir"].quantile(0.95))},
        "mitades": mit, "criterios": crit,
        "por_cuadrante_vigente": por_cuadrante, "por_año": por_año,
    }
    OUT.write_text(json.dumps(redondea(out), indent=1, ensure_ascii=False))
    print(json.dumps(redondea({k: out[k] for k in ("periodo", "s1", "l0", "activa", "placebos", "criterios")}),
                     indent=1, ensure_ascii=False))
    for m in mit:
        print(m["desde"], m["hasta"], {k: round(m[k], 4) for k in ("activa_arit", "activa_geo", "ir")})
    print(redondea(por_cuadrante))
    return 0


if __name__ == "__main__":
    sys.exit(main())
