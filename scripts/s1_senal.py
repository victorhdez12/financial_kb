"""S1, paso 2 (docs/factors/S1_rotacion_sectorial_spec.md v1.0 §1-§2): señal PIT del cuadrante ≤ 2004 y fijación del
inicio del periodo de puntuación SOLO por disponibilidad de datos. NO calcula ninguna rentabilidad (ni lee industrias).

Señal = el MISMO código que corre en vivo (`make regime` → `src.regime.run`): `src.regime.features.build_panel` (capa
point-in-time: vintages ALFRED donde existen; si no, la última vintage con los retrasos de publicación de
`src/regime/asof.py`) + `src.regime.run.classify_all` (`src/regime/classify.py`). La rejilla se corta en 2004-12-31:
ninguna fecha de corte (cutoff) posterior entra en el panel. Se comprueba además que la serie coincide con la tabla
viva `regime_monthly` en ≤ 2004 (lo que publica la diaria).

Salidas (research/factors/): s1_senal.csv (cuadrante por mes, con su modo de vintage) y s1_senal.json (inicio de la
puntuación, propiedades de la señal, sha256 del CSV, semilla de los placebos, commit del código).
Uso: .venv/bin/python -m scripts.s1_senal
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from src.regime.asof import month_grid
from src.regime.features import build_panel
from src.regime.run import START, classify_all, vintage_mode
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "research" / "factors"
FIN = pd.Timestamp("2004-12-31")
SEMILLA, N_PLACEBOS, BLOQUE = 20261119, 1000, 12          # declarados ANTES de calcular rentabilidades
CUADRANTES = ("Goldilocks", "Reflación", "Estanflación", "Deflación/recesión")


def cuadrante_pit(con) -> pd.DataFrame:
    """date (fin de mes t), quadrant, vintage_mode, G, G_state, I_state, core_6m: información al cierre de t ≤ 2004."""
    grid = month_grid(today=FIN.date())
    assert grid["cutoff"].max() <= FIN
    panel, _ = build_panel(con, grid)
    res = classify_all(panel)
    df = res[["G", "G_state", "I_state"]].copy()
    df["core_6m"] = panel["core_6m"]
    df["quadrant"] = res["quadrant"]
    df["vintage_mode"] = vintage_mode(panel)
    df = df[df.index >= pd.Timestamp(START)]
    df.index.name = "date"
    return df


def propiedades(q: pd.Series) -> dict:
    """Solo de la señal (no hay rentabilidades): frecuencias, cambios al año, duraciones, cuadrantes por año."""
    v = q.dropna()
    tramos = v.groupby((v != v.shift()).cumsum()).agg(["first", "size"])
    cambios = int((v != v.shift()).sum() - 1)
    por_año = (pd.crosstab(v.index.year, v.values).reindex(columns=list(CUADRANTES), fill_value=0))
    return {"meses": int(len(q)), "meses_sin_cuadrante": int(q.isna().sum()),
            "frecuencia": {c: round(float((v == c).mean()), 4) for c in CUADRANTES},
            "cambios": cambios, "cambios_año": round(cambios / (len(v) / 12), 3),
            "duracion_media_meses": {c: round(float(tramos[tramos["first"] == c]["size"].mean()), 2)
                                     for c in CUADRANTES if (tramos["first"] == c).any()},
            "tramos": int(len(tramos)),
            "por_año": {int(a): {c: int(n) for c, n in fila.items()} for a, fila in por_año.iterrows()}}


def git(*a) -> str:
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True).stdout.strip()


def main() -> None:
    con = db.connect(read_only=True)
    try:
        df = cuadrante_pit(con)
        viva = con.execute("select date, quadrant from regime_monthly where date <= ?", [FIN.date()]).df()
    finally:
        con.close()
    viva = viva.set_index(pd.to_datetime(viva["date"]))["quadrant"].reindex(df.index)
    distintos = df.index[(df["quadrant"].fillna("∅") != viva.fillna("∅"))]
    q = df["quadrant"]
    t0 = q.first_valid_index()
    inicio = (t0 + pd.offsets.MonthBegin(1))               # primer mes cuya rentabilidad rigen los pesos de t0
    OUT.mkdir(parents=True, exist_ok=True)
    csv = OUT / "s1_senal.csv"
    df.reset_index().assign(date=lambda x: x["date"].dt.strftime("%Y-%m-%d")).to_csv(csv, index=False,
                                                                                     float_format="%.10g")
    sha = hashlib.sha256(csv.read_bytes()).hexdigest()
    p_all = propiedades(q.loc[t0:FIN - pd.offsets.MonthEnd(1)])     # cuadrantes que gobiernan 1950-02 … 2004-12
    res = {
        "documento": "S1 paso 2: señal PIT del cuadrante y periodo de puntuación (sin rentabilidades)",
        "spec": "docs/factors/S1_rotacion_sectorial_spec.md v1.0 (commit 7a0b1a3)",
        "generado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "git_head_codigo": git("rev-parse", "HEAD"),
        "codigo": "src/regime/features.build_panel + src/regime/run.classify_all (src/regime/classify.py), rejilla "
                  "month_grid(today=2004-12-31), recorte START de src/regime/run.py",
        "csv": str(csv.relative_to(REPO)), "csv_sha256": sha,
        "coincide_con_regime_monthly_vivo": len(distintos) == 0,
        "meses_distintos_de_regime_monthly": [str(d.date()) for d in distintos],
        "primer_cuadrante": str(t0.date()),
        "puntuacion": {"desde": inicio.strftime("%Y-%m"), "hasta": "2004-12",
                       "motivo": "primer cuadrante PIT no nulo del clasificador en vivo (la tabla viva empieza en "
                                 "START = 1950-01-31; antes no hay cuadrante publicado por el código en vivo); "
                                 "industrias y mercado de Ken French existen desde 1926-07, no limitan"},
        "placebos": {"n": N_PLACEBOS, "bloque_meses": BLOQUE, "semilla": SEMILLA, "rng": "numpy.random.default_rng"},
        "modo_vintage": {str(k): int(v) for k, v in df["vintage_mode"].value_counts(dropna=False).items()},
        "propiedades_periodo_puntuado": p_all,
    }
    (OUT / "s1_senal.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in res.items() if k != "propiedades_periodo_puntuado"}, indent=1,
                     ensure_ascii=False))
    print({k: v for k, v in p_all.items() if k != "por_año"})


if __name__ == "__main__":
    main()
