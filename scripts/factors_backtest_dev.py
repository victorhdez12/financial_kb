"""Corrida ÚNICA de desarrollo de P-DEV-FACT v0.1 (docs/factors/prerreg_desarrollo_v0.md, aprobada y commiteada 7877246).
Exige el árbol de git limpio; guarda el resultado en research/factors/runs/<id>/ y una línea en research/trial_log.md.
Uso: .venv/bin/python -m scripts.factors_backtest_dev
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from src.factors import backtest as B
from src.factors import data as F
from src.warehouse import db

REPO = Path(__file__).resolve().parents[1]
IDX = pd.period_range("1975-01", "2004-12", freq="M")
IDX63 = pd.period_range("1963-07", "2004-12", freq="M")
VARIANTES = {"V1": (0.0, 1), "V2": (-0.25, 1), "V3": (0.0, 3)}     # research/factors/variantes_senal.json
RHO_ORO = 0.161                                                     # §5.6 (EUR, 1975-2004)
N_PLACEBO, BLOQUE_PLACEBO, SEMILLA = 500, 24, 20261026


def per(s: pd.Series) -> pd.Series:
    s = s.copy(); s.index = s.index.to_period("M"); return s[~s.index.duplicated(keep="last")]


def datos(con) -> dict:
    rv_usd = per((F.load_dev(con, "ff_mkt_rf_m") + F.load_dev(con, "ff_rf_m")) / 100)
    fx = per(F.load_dev(con, "bis_xru_xm_eur_m").combine_first(F.load_dev(con, "bis_xru_de_eur_m")))   # EUR por USD
    rv_eur = (1 + rv_usd) * (1 + fx.pct_change().reindex(rv_usd.index)) - 1
    y5 = per(F.load_dev(con, "bundesbank_bund_zero_5y_m"))
    rf_eur = y5.shift(1) / 1200 - 5 * (y5 - y5.shift(1)) / 100
    oro_eur = per(F.gold_eur_dev(con)).pct_change()
    oro_usd = per(F.load_dev(con, "gold_wb_usd_m")).pct_change()
    caja_eur = per(F.load_dev(con, "oecd_ir3m_deu")).shift(1) / 1200
    g5 = F.load_dev(con, "gsw_sveny05")
    y5u = per(g5.groupby(g5.index.to_period("M")).last().to_timestamp())
    rf_usd = y5u.shift(1) / 1200 - 5 * (y5u - y5u.shift(1)) / 100
    caja_usd = per(F.load_dev(con, "TB3MS")).shift(1) / 1200
    G = con.execute("select date, G from regime_monthly where date <= ?", [F.DEV_END.date()]).df()
    G = pd.Series(G["G"].values, index=pd.to_datetime(G["date"]).dt.to_period("M"))
    F.check(G.to_timestamp())
    return dict(rv_usd=rv_usd, rv_eur=rv_eur, rf_eur=rf_eur, oro_eur=oro_eur, oro_usd=oro_usd, caja_eur=caja_eur,
                rf_usd=rf_usd, caja_usd=caja_usd, G=G)


def corrida(r: pd.DataFrame, rv_hist: pd.Series, G: pd.Series, caja: pd.Series, idx, episodios, *, coste_mult=1.0,
            ventana_b1=12, base=B.ESTRATEGICO, defens=B.DEFENSIVO, bloque_boot=12, placebos=0) -> dict:
    r = r.reindex(idx)
    assert not r.isna().any().any(), r[r.isna().any(axis=1)].head()
    objs = {"B0": B.objetivo_fijo(idx, base), "B1": B.objetivo_vol(rv_hist, idx, ventana_b1, normal=base)}
    estados = {}
    for v, (th, k) in VARIANTES.items():
        estados[v] = B.estado(G, th, k).reindex(idx).astype(bool)
        objs[v] = B.objetivo_estado(estados[v], base, defens)
    res = {k: B.simular(r, o, coste_mult, pesos_base=base) for k, o in objs.items()}
    met = {k: B.metricas(x, caja, episodios) for k, x in res.items()}
    ex = {k: x.neto - caja.reindex(idx) for k, x in res.items()}
    srs = [float(e.mean() / e.std(ddof=1)) for e in ex.values()]
    dsr = {k: B.dsr(e, srs, n=len(ex)) for k, e in ex.items()}
    crit = {}
    for v in VARIANTES:
        boot = B.bootstrap_dif_vol(res[v].neto, res["B1"].neto, bloque_boot)
        ce, cb = met[v]["caidas_episodio"], met["B1"]["caidas_episodio"]
        mejor = sum(ce[e] > cb[e] for e in ce)
        c = {"a_boot": boot, "b_episodios_mejor": mejor, "b_episodios_total": len(ce),
             "b_caida_total_no_peor": met[v]["caida_max"] >= met["B1"]["caida_max"],
             "d_dsr": dsr[v], "d_dsr_B1": dsr["B1"], "d_cumple": dsr[v] >= dsr["B1"]}
        if placebos:
            rng = np.random.default_rng(SEMILLA + int(v[1]))
            obs = met["B1"]["vol_anual"] - met[v]["vol_anual"]
            nulos = []
            for _ in range(placebos):
                sb = B.barajar_bloques(estados[v], BLOQUE_PLACEBO, rng)
                rp = B.simular(r, B.objetivo_estado(sb, base, defens), coste_mult, pesos_base=base)
                nulos.append(met["B1"]["vol_anual"] - float(rp.neto.std(ddof=1) * np.sqrt(12)))
            nulos = np.array(nulos)
            c["c_placebo"] = {"reduccion_obs": obs, "p95_nulo": float(np.quantile(nulos, 0.95)),
                              "p": float((1 + (nulos >= obs).sum()) / (1 + placebos))}
        crit[v] = c
    if placebos:
        ha = B.holm({v: crit[v]["a_boot"]["p"] for v in VARIANTES})
        hc = B.holm({v: crit[v]["c_placebo"]["p"] for v in VARIANTES})
        for v in VARIANTES:
            c = crit[v]
            c["a_cumple"] = c["a_boot"]["hi"] < 0 and ha[v]
            c["c_cumple"] = c["c_placebo"]["reduccion_obs"] > c["c_placebo"]["p95_nulo"] and hc[v]
            c["b_cumple"] = c["b_episodios_mejor"] >= 3 and c["b_caida_total_no_peor"]
            c["CUMPLE_TODO"] = bool(c["a_cumple"] and c["b_cumple"] and c["c_cumple"] and c["d_cumple"])
    return {"metricas": met, "dsr": dsr, "criterios": crit,
            "pct_defensivo": {v: float(s.mean()) for v, s in estados.items()}}


def main() -> None:
    sucio = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"], capture_output=True, text=True).stdout
    if sucio.strip():
        raise SystemExit("árbol de git sucio: commitea antes de la corrida única\n" + sucio)
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    rid = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S") + "_pdevfact_v01"
    con = db.connect(read_only=True)
    d = datos(con)
    con.close()
    out = {"run_id": rid, "git_head": head, "prerreg": "docs/factors/prerreg_desarrollo_v0.md v0.1 (7877246)"}
    r_main = pd.DataFrame({"rv": d["rv_eur"], "rf": d["rf_eur"], "oro": d["oro_eur"]})
    r_corr = r_main.assign(oro=B.desuavizar(d["oro_eur"], RHO_ORO))
    out["principal_sin_correccion"] = corrida(r_main, d["rv_eur"], d["G"], d["caja_eur"], IDX, B.EPISODIOS,
                                              placebos=N_PLACEBO)
    out["principal_oro_corregido"] = corrida(r_corr, d["rv_eur"], d["G"], d["caja_eur"], IDX, B.EPISODIOS,
                                             placebos=N_PLACEBO)
    # sensibilidades (§7; no deciden, sin placebos)
    r_usd = pd.DataFrame({"rv": d["rv_usd"], "rf": d["rf_usd"], "oro": d["oro_usd"]})
    sin_oro = {"rv": 0.80, "rf": 0.20, "oro": 0.0}
    def_sin_oro = {"rv": 0.65, "rf": 0.35, "oro": 0.0}
    sens = {
        "usd": corrida(r_usd, d["rv_usd"], d["G"], d["caja_usd"], IDX, B.EPISODIOS),
        "1963_sin_oro_usd": corrida(r_usd.assign(oro=0.0), d["rv_usd"], d["G"], d["caja_usd"], IDX63,
                                    B.EPISODIOS_1963, base=sin_oro, defens=def_sin_oro),
        "costes_x2": corrida(r_corr, d["rv_eur"], d["G"], d["caja_eur"], IDX, B.EPISODIOS, coste_mult=2.0),
        "boot_bloques_24": corrida(r_corr, d["rv_eur"], d["G"], d["caja_eur"], IDX, B.EPISODIOS, bloque_boot=24),
        "b1_ventana_6": corrida(r_corr, d["rv_eur"], d["G"], d["caja_eur"], IDX, B.EPISODIOS, ventana_b1=6),
        "b1_ventana_24": corrida(r_corr, d["rv_eur"], d["G"], d["caja_eur"], IDX, B.EPISODIOS, ventana_b1=24),
    }
    out["sensibilidades"] = sens
    out["declaraciones"] = ["BIS EUR/USD es media mensual (verif_cierre.json): RV en EUR mezcla cierre (RV) y media (divisa); "
                            "sensibilidad en USD", "1963-2004 sin oro corre en USD: no hay renta fija en EUR antes de 1972-09"]
    dest = REPO / "research" / "factors" / "runs" / rid
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "resultado.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=float))
    veredicto = {k: {v: out[k]["criterios"][v]["CUMPLE_TODO"] for v in VARIANTES}
                 for k in ("principal_sin_correccion", "principal_oro_corregido")}
    linea = (f"| {dt.date.today()} | Constructor (P-DEV-FACT v0.1, corrida única) | `{rid}` (git {head[:7]}): B0, B1, V1-V3, "
             f"1975-01 → 2004-12, 500 placebos por variante; veredicto (CUMPLE TODO) {json.dumps(veredicto, ensure_ascii=False)}; "
             f"resultado en research/factors/runs/{rid}/resultado.json |\n")
    with open(REPO / "research" / "trial_log.md", "a") as fh:
        fh.write(linea)
    print(json.dumps({"run_id": rid, "veredicto": veredicto}, ensure_ascii=False))


if __name__ == "__main__":
    main()
