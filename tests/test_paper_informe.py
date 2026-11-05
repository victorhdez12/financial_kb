"""Informe mensual del paper trading: valoración y QLIKE con datos sintéticos (sin warehouse)."""
import json

import numpy as np
import pandas as pd

from src.paper import informe as I


def _logs(tmp_path):
    b1 = tmp_path / "b1.jsonl"
    b1p = tmp_path / "b1p.jsonl"
    w = {"rv": 0.7, "rf": 0.15, "oro": 0.15}
    b1.write_text("\n".join(json.dumps({"cierre": c, "b0": w, "b1": w, "sigma_hat": 0.12})
                            for c in ("2026-10-31", "2026-11-30", "2026-12-31")) + "\n")
    b1p.write_text("\n".join(json.dumps({"cierre": c, "b1prima": {"rv": 0.6, "rf": 0.25, "oro": 0.15},
                                         "sigma_hat_prima": 0.20, "f_varianza_mes": 0.2 ** 2 / 12})
                             for c in ("2026-11-30", "2026-12-31")) + "\n")
    return b1, b1p


def test_valorar_y_prevision(tmp_path):
    reg = I.registros(*_logs(tmp_path))
    assert list(reg.index.astype(str)) == ["2026-10", "2026-11", "2026-12"] and pd.isna(reg.loc["2026-10", "b1p"])
    idx = pd.period_range("2026-11", "2027-02", freq="M")
    r = pd.DataFrame({"rv": [0.02, -0.01, 0.03, 0.0], "rf": 0.001, "oro": 0.0}, index=idx)
    v = I.valorar(reg, r)
    assert v["b0"]["meses"] == 4 and v["b1p"]["meses"] == 3 and v["b1p"]["desde"] == "2026-12"
    assert abs(v["b0"]["rent_acumulada"] - v["b1"]["rent_acumulada"]) < 1e-12      # mismos pesos
    # previsión: mes de diciembre con vol diaria 1 % → RV ≈ 21·1e-4; la previsión de B1′ (20 %) se acerca más que B1 (12 %)
    d = pd.bdate_range("2026-11-02", "2027-01-29")
    r_d = pd.Series(np.where(np.arange(len(d)) % 2, 0.0126, -0.0126), index=d)
    p = I.prevision(reg, r_d)
    assert p["n_comparables"] == 1 and [m["mes"] for m in p["meses"]] == ["2026-11", "2026-12"]
    assert p["meses"][0]["qlike_b1p"] is None          # la decisión de octubre solo tiene B1
    assert p["qlike_medio_b1p"] < p["qlike_medio_b1"]
    assert "B1′" in I.markdown({"cierres": ["2026-10"], "valoracion": v, "prevision": p, "ultimo_mes_valorable": "2027-02"})


def test_sin_registros(tmp_path):
    assert I.registros(tmp_path / "no.jsonl", tmp_path / "no2.jsonl").empty
