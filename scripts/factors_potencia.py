"""Cálculo de potencia de la fase de factores, ANTES de construir nada (plan de la fase, ajuste 4).
Solo usa: (i) estadísticos INCONDICIONALES de los factores 1963-07 → 2004-12 (σ, curtosis, AR(1); vía el corte
técnico src/factors/data.py), y (ii) cuántos meses y episodios hay en cada estado del clasificador de reglas ≤ 2004.
NO cruza rendimientos con regímenes (ninguna media condicionada). Sin etiqueta, sin cartera.
Uso: .venv/bin/python -m scripts.factors_potencia
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.factors import data as F
from src.warehouse import db

OUT = Path(__file__).resolve().parents[1] / "research" / "factors"
DESDE, Z = pd.Timestamp("1963-07-01"), 2.80          # 80 % de potencia, bilateral al 5 %: 1,96 + 0,84
FACTORES = {"mercado": "ff5_mkt_rf_m", "tamaño": "ff5_smb_m", "value": "ff5_hml_m", "rentabilidad": "ff5_rmw_m",
            "inversión": "ff5_cma_m", "momentum": "ff_mom_m", "calidad (AQR QMJ)": "aqr_qmj_usa_m",
            "beta baja (AQR BAB)": "aqr_bab_usa_m"}
TAUS = [0.0, 0.05, 0.10]                            # heterogeneidad anualizada entre episodios (escenarios)


def episodios(estado: pd.Series) -> int:
    """Número de rachas de meses consecutivos con estado True."""
    e = estado.astype(bool)
    return int((e & ~e.shift(1, fill_value=False)).sum())


def main() -> None:
    con = db.connect(read_only=True)
    reg = con.execute("select date, quadrant, G_state, sahm_trigger from regime_monthly where date <= ?",
                      [F.DEV_END.date()]).df()
    fs = {k: F.load_dev(con, sid) for k, sid in FACTORES.items()}
    con.close()
    reg["date"] = pd.to_datetime(reg["date"]); reg = reg.set_index("date")
    reg = reg[reg.index >= DESDE + pd.offsets.MonthEnd(0)]
    F.check(reg)
    estados = {"G↓ (cualquier I)": reg["G_state"] == "down"}
    for q in sorted(reg["quadrant"].dropna().unique()):
        estados[q] = reg["quadrant"] == q
    n = len(reg)
    est = {}
    for k, s in estados.items():
        n1, K = int(s.sum()), episodios(s)
        est[k] = {"meses": n1, "episodios": K, "meses_por_episodio": round(n1 / max(K, 1), 1)}
    fac = {}
    for k, s in fs.items():
        s = s[s.index >= DESDE] / 100
        x = s.to_numpy()
        fac[k] = {"desde": str(s.index.min().date()), "meses": len(x), "sigma_anual": float(x.std(ddof=1) * np.sqrt(12)),
                  "curtosis": float(pd.Series(x).kurt() + 3), "ar1": float(pd.Series(x).autocorr(1))}
    # MDE de la diferencia de rentabilidad media anual (estado frente al resto), 80 % / 5 %
    tabla = {}
    for ke, e in est.items():
        n1, K = e["meses"], max(e["episodios"], 1)
        n0 = n - n1
        fila = {}
        for kf, f in fac.items():
            sm = f["sigma_anual"] / np.sqrt(12)
            infl = np.sqrt((1 + f["ar1"]) / (1 - f["ar1"]))          # corrección por autocorrelación
            se_iid = 12 * sm * infl * np.sqrt(1 / n1 + 1 / n0)
            mde = {f"tau={t:.2f}": round(Z * np.sqrt(se_iid ** 2 + t ** 2 / K), 3) for t in TAUS}
            # volatilidad: SE(log σ) ≈ sqrt((κ − 1) / (4 n)) por grupo → MDE del cociente de σ
            se_lv = np.sqrt((f["curtosis"] - 1) / 4 * (1 / n1 + 1 / n0)) * infl
            fila[kf] = {"mde_rent_anual": mde, "mde_sharpe_tau0": round(mde["tau=0.00"] / f["sigma_anual"], 2),
                        "mde_sharpe_tau0.05": round(mde["tau=0.05"] / f["sigma_anual"], 2),
                        "mde_ratio_vol": round(float(np.exp(Z * se_lv)), 2)}
        tabla[ke] = fila
    res = {"generado": str(pd.Timestamp.now("UTC")), "muestra": f"{reg.index.min().date()} → {reg.index.max().date()}",
           "meses_totales": n, "estados": est, "factores_incondicional": fac, "mde": tabla,
           "nota": "MDE = efecto mínimo detectable con 80 % de potencia, bilateral 5 %; tau = dispersión anualizada de "
                   "la media entre episodios (escenario, no estimada). Sin medias condicionadas."}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "potencia_factores.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps({"estados": est, "factores": fac}, indent=1, ensure_ascii=False))
    for ke, fila in tabla.items():
        print(f"\n{ke} ({est[ke]['meses']} m, {est[ke]['episodios']} episodios)")
        for kf, v in fila.items():
            print(f"  {kf:22s} rent {v['mde_rent_anual']}  Sharpe τ0 {v['mde_sharpe_tau0']} τ.05 {v['mde_sharpe_tau0.05']}  ratio vol {v['mde_ratio_vol']}")


if __name__ == "__main__":
    main()
