"""Control PIT por truncamiento de M2 con la instantánea real ≤ 2004 (m2_structural_spec.md §6, "Controles antes de la
etiqueta real": 3 cortes × 2 modos, sintético Y con la instantánea ≤ 2004). La versión sintética es
tests/test_models_struct.py::test_pit_by_truncation.

Sin etiqueta: solo la matriz PIT v0.4 y los niveles PIT de las 4 coincidentes (`PITData.pit_levels`), en desarrollo.
No llama a `train_targets` ni a nada que lea G/I. Para cada corte t y modo, el nowcast de t (μ, σ̂) se calcula con:
  A  información del arnés cortada en t (`H._v24_info`, cota = t);
  B  información hasta 2004-12 (cota = 2004-12), sin tocar;
  C  como B, pero con los niveles pedidos para fechas > decisión(t) multiplicados por 1,3 y las variables de los meses
     > t con el signo cambiado.
Pasa si A = B = C bit a bit y si, en C, M2 no pide niveles posteriores a la fecha de decisión de t.
Salida: research/validation/m2_pit_truncamiento_real/resultado.json. Una sola pasada.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.models import harness as H
from src.models import models_struct as MS

CUTS = ("1988-01", "1995-01", "2002-01")
MODES = ("vintage", "latest_truncated")
BOUND = pd.Timestamp("2004-12-01")
OUT = Path("research/validation/m2_pit_truncamiento_real")


def _nowcast(data, t, bound, alter=False):
    MS.clear_engines()
    m = MS.StructuralG()
    feats = m.axis_features["G"]
    info = H._v24_info(m, data, feats, None, bound, None)
    dec_t = data.decision[t]
    asked = []
    if alter:
        base = info["pit_levels"]

        def pit_levels(date):
            date = pd.Timestamp(date)
            asked.append(date)
            o = base(date)
            if date > dec_t:
                return {"levels": {k: v * 1.3 for k, v in o["levels"].items()}, "from_vintage": o["from_vintage"]}
            return o
        fh = info["features_history"].copy()
        fh.loc[fh.index > t] = -fh.loc[fh.index > t]
        info = {**info, "pit_levels": pit_levels, "features_history": fh}
    info = {**info, "refit_month": t, "decision_date": dec_t, "mode": data.mode, "axis": "G"}
    m.fit_axis_continuous("G", None, None, None, None, info)
    mu, sd = m.predict_axis_continuous("G", pd.DataFrame(index=[t]), info)
    late = [d for d in asked if d > dec_t]
    return float(mu[0]), float(sd[0]), (f"{max(late):%Y-%m-%d}" if late else None)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for mode in MODES:
        data = H.PITData(mode)
        for c in CUTS:
            t = pd.Timestamp(c + "-01")
            a = _nowcast(data, t, t)
            b = _nowcast(data, t, BOUND)
            cc = _nowcast(data, t, BOUND, alter=True)
            ok = a[:2] == b[:2] == cc[:2] and cc[2] is None and np.isfinite(a[:2]).all()
            rows.append({"modo": mode, "corte": c, "A": a[:2], "B": b[:2], "C": cc[:2],
                         "C_pide_niveles_posteriores": cc[2], "ok": bool(ok)})
            print(rows[-1], flush=True)
    sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    res = {"script_sha256": sha, "cortes": rows, "veredicto": "PASA" if all(r["ok"] for r in rows) else "FALLA"}
    (OUT / "resultado.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(res["veredicto"])


if __name__ == "__main__":
    main()
