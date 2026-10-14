"""Validación independiente de la etiqueta de régimen v1.0 (no es código de producción).

Ejecutar desde la raíz del repo:
    .venv/bin/python -m tests.validation.label_v1_validation [salida.json]

No escribe en data/archive ni toca src/labels: construye variantes en memoria con
dataclasses.replace(R.PARAMS, ...) y las compara con la etiqueta oficial.

Partes:
  1. Sensibilidad (κ, ventana de tendencia, ritmo 12 m, escalas ×0,5 / ×2, otras).
  2. Estudio de revisión: variante C (añade PCEPILFE con vintage ALFRED), robustez de k*.
  3. Periodo bloqueado: meses puntuables, recesiones y cambios de régimen por alternativa.
  4. Diagnósticos de la ficha (empalmes de inflación, IPC general 1955-57, σ_i con muestra completa).
  5. Contrastes externos que faltan en la §8 (IPC mediano, PCE recortada, episodios de inflación, giros NBER).
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

from src.labels import checks as C
from src.labels import regime_us as R
from src.labels import revision_study as RS
from src.warehouse import db

P0 = R.PARAMS
PCOLS = [f"p_{q}" for q in R.QUADRANTS]
OFFICIAL = R.out_dir() / "regime_us_v1.0.parquet"


def scored(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["weight"] > 0) & ~df["provisional"]]


def runs_mean(lbl: pd.Series) -> float:
    return float(C.runs(lbl)["months"].mean())


# ------------------------------------------------------------------ 1. sensibilidad
def sensitivity(inputs: dict, ext: dict, base: pd.DataFrame) -> list[dict]:
    variants = {
        "κ = 2,0": dict(p=replace(P0, kappa=2.0)),
        "κ = 3,0": dict(p=replace(P0, kappa=3.0)),
        "tendencia 7 años (±42 m)": dict(p=replace(P0, trend_half_window=42)),
        "tendencia 12 años (±72 m)": dict(p=replace(P0, trend_half_window=72)),
        "ritmo 12 m (t−6…t+6)": dict(p=replace(P0, pace_lead=6, pace_lag=6)),
        "inflación 12 m (t−6…t+6)": dict(p=replace(P0, infl_lead=6, infl_lag=6)),
        "s_G, s_I × 0,5": dict(p=P0, sG=0.20, sI=0.155),
        "s_G, s_I × 2": dict(p=P0, sG=0.80, sI=0.62),
        "ajuste IPC subyacente 0,0 pp": dict(p=replace(P0, cpi_core_adj=0.0)),
        "solo INDPRO + PAYEMS": dict(p=replace(P0, growth_ids=("INDPRO", "PAYEMS"))),
    }
    b = base.set_index("date")
    bs = scored(b)
    out = []
    for name, v in variants.items():
        p = v["p"]
        lab, _ = R.make_label(inputs, p, v.get("sG", P0.s_G_fixed), v.get("sI", P0.s_I_fixed))
        lab = lab.set_index("date")
        idx = bs.index.intersection(lab.index)
        a, c = bs.loc[idx], lab.loc[idx]
        ch = a["label_hard"] != c["label_hard"]
        g_flip = np.sign(a["G"]) != np.sign(c["G"])
        i_flip = np.sign(a["I"] - P0.kappa) != np.sign(c["I"] - p.kappa)
        tv = 0.5 * (a[PCOLS] - c[PCOLS]).abs().sum(axis=1)
        # §8 con la variante, en las mismas fechas puntuables
        crit = C.criteria(c.assign(provisional=False), ext)
        fails = [r[0] for r in crit if not r[3]]
        eps = {}
        for ename, s, e, want, _ in C.EPISODES:
            x = c.loc[s:e]
            eps[ename] = f"{x['label_hard'].isin(want).mean():.0%}" if len(x) else "—"
        dist = c["label_hard"].value_counts(normalize=True).reindex(R.QUADRANTS).fillna(0)
        out.append({
            "variante": name, "n": int(len(idx)), "cambian": int(ch.sum()), "pct": float(ch.mean()),
            "flip_G": int(g_flip.sum()), "flip_I": int(i_flip.sum()), "tv_mean": float(tv.mean()),
            "frontera": int((c["max_prob"] < P0.frontier).sum()), "frontera_base": int(a["frontera"].sum()),
            "dur_media": runs_mean(c["label_hard"]), "dist_min": float(dist.min()),
            "fallan_8": fails, "episodios": eps,
            "por_decada": {int(k): float(x) for k, x in ch.groupby(ch.index.year // 10 * 10).mean().items()},
        })
    return out


# ------------------------------------------------------------------ 2. estudio de revisión
def revision_variant_c(inputs: dict) -> dict:
    """Como la variante B, pero también PCEPILFE (y CPILFESL) con la vintage ALFRED vigente a fin de T+1.
    Solo cortes con vintage de PCE con historia suficiente (desde ~2000)."""
    p = P0
    con = db.connect()
    try:
        ids = ("INDPRO", "PAYEMS", "PCEPILFE", "CPILFESL")
        vint = {sid: R.load_vintages(con, sid)[0] for sid in ids}
    finally:
        con.close()
    full, _ = R.make_label(inputs, p, p.s_G_fixed, p.s_I_fixed)
    full = full.set_index("date")
    mature_end = full.index.max() - pd.DateOffset(months=p.truncated_months)
    rows = {"B_desde_2000": [], "C_desde_2000": [], "A_desde_2000": []}
    used = []
    for T in RS.CUTS:
        asof = T + pd.offsets.MonthEnd(2)
        snaps = {sid: RS.snapshot(vint[sid], asof, T) for sid in ids}
        pce = snaps["PCEPILFE"]
        if pce.empty or pce.index.min() > pd.Timestamp("1959-02-01"):
            continue
        used.append(str(T.date()))
        lab_a, _ = R.make_label(inputs, p, p.s_G_fixed, p.s_I_fixed, cutoff=T)
        rows["A_desde_2000"] += RS.compare_one(lab_a, full, T, mature_end)
        lvb = dict(inputs["levels"])
        for sid in ("INDPRO", "PAYEMS"):
            if not snaps[sid].empty and snaps[sid].index.min() <= pd.Timestamp("1949-01-01"):
                lvb[sid] = snaps[sid]
        lab_b, _ = R.make_label({"levels": lvb, "usrec": inputs["usrec"]}, p, p.s_G_fixed, p.s_I_fixed, cutoff=T)
        rows["B_desde_2000"] += RS.compare_one(lab_b, full, T, mature_end)
        lvc = dict(lvb)
        for sid in ("PCEPILFE", "CPILFESL"):
            if not snaps[sid].empty:
                lvc[sid] = snaps[sid]
        lab_c, _ = R.make_label({"levels": lvc, "usrec": inputs["usrec"]}, p, p.s_G_fixed, p.s_I_fixed, cutoff=T)
        rows["C_desde_2000"] += RS.compare_one(lab_c, full, T, mature_end)
    summ = {k: RS.summarize(pd.DataFrame(v)) for k, v in rows.items()}
    ks = {k: RS.k_star(s) for k, s in summ.items()}
    tab = {k: s.loc[[4, 6, 12, 24, 36, 42, 48, 54, 55, 60, 72, 84], ["n", "concord", "dp_mean", "dI_mean"]]
           .round(4).reset_index().to_dict("records") for k, s in summ.items()}
    return {"cuts_used": used, "k_star": ks, "tab": tab}


def revision_robustness(inputs: dict) -> dict:
    """Sensibilidad de k* a la definición de la regla, con los detalles de la variante oficial (A y B)."""
    import pickle  # resultado de RS.run() guardado por el validador para no recalcular
    import os
    f = os.environ.get("RS_PICKLE")
    if f and os.path.exists(f):
        res = pickle.load(open(f, "rb"))
    else:
        res = RS.run()
    out = {}
    for v in ("latest", "alfred"):
        s = res["summ"][v]
        det = res["det"][v]
        d = {}
        for conc, dp in ((0.95, 0.05), (0.90, 0.05), (0.95, 0.10), (0.97, 0.03)):
            ok = ((s["concord"] >= conc) & (s["dp_mean"] <= dp)) | s["n"].isna()
            k = next((k for k in range(RS.K_MAX + 1) if not pd.isna(s.at[k, "n"]) and ok.loc[k:].all()), None)
            d[f"conc≥{conc:.0%}, Δp≤{dp}"] = k
        # bootstrap por cortes (remuestreo de cortes T con reemplazo)
        h = det[det["has"]]
        Ts = h["T"].unique()
        rng = np.random.default_rng(0)
        kb = []
        for _ in range(300):
            pick = rng.choice(Ts, len(Ts), replace=True)
            hh = pd.concat([h[h["T"] == t] for t in pick])
            g = hh.groupby("k")
            ss = pd.DataFrame({"n": g.size(), "concord": g["same"].mean(), "dp_mean": g["dp"].mean()}).reindex(
                range(RS.K_MAX + 1))
            kb.append(RS.k_star(ss) or RS.K_MAX)
        kb = np.array(kb)
        d["bootstrap_k*"] = {"p05": float(np.percentile(kb, 5)), "p50": float(np.median(kb)),
                             "p95": float(np.percentile(kb, 95)), "share_gt_58": float((kb > 58).mean())}
        # cortes 1990+ solamente
        h2 = h[h["T"] >= pd.Timestamp("1990-01-01")]
        g = h2.groupby("k")
        ss = pd.DataFrame({"n": g.size(), "concord": g["same"].mean(), "dp_mean": g["dp"].mean()}).reindex(
            range(RS.K_MAX + 1))
        d["solo cortes ≥ 1990"] = RS.k_star(ss)
        # concordancia en meses maduros (k ≥ 58, ya no provisionales con 54) por cuadrante de frontera
        m = h[h["k"] >= 58]
        d["concord_k≥58"] = float(m["same"].mean())
        out[v] = d
    return out


# ------------------------------------------------------------------ 3. periodo bloqueado
def blocked(base: pd.DataFrame) -> list[dict]:
    b = base.set_index("date")
    mature_last = b.index[~b["provisional"]].max()
    sc = scored(b)
    rec = b["usrec"].fillna(0).astype(int)
    starts = rec.index[(rec == 1) & (rec.shift(fill_value=0) == 0)]
    cands = [("2016-01 → abierto (plan)", "2016-01"), ("2012-01 → abierto", "2012-01"),
             ("2008-01 → abierto", "2008-01"), ("2005-01 → abierto", "2005-01"),
             ("2000-01 → abierto", "2000-01")]
    out = []
    for name, s in cands:
        x = sc.loc[s:]
        tr = sc.loc[:pd.Timestamp(s) - pd.DateOffset(months=P0.embargo_months + 1)]
        lbl = x["label_hard"]
        n_ch = int((lbl != lbl.shift()).iloc[1:].sum())
        recs_in = [f"{d:%Y-%m}" for d in starts if pd.Timestamp(s) <= d <= mature_last]
        recs_tr = [d for d in starts if d < pd.Timestamp(s) and d >= pd.Timestamp("1955-01-01")]
        dist = lbl.value_counts().reindex(R.QUADRANTS).fillna(0).astype(int).to_dict()
        # cambios de régimen en el eje I (I cruza κ) dentro del bloque
        hi = (x["I"] > P0.kappa).astype(int)
        i_cross = int((hi != hi.shift()).iloc[1:].sum())
        out.append({"bloque": name, "meses_puntuables": int(len(x)), "hasta": f"{mature_last:%Y-%m}",
                    "recesiones": recs_in, "cambios_regimen": n_ch, "cruces_I": i_cross, "dist": dist,
                    "train_meses": int(len(tr)), "train_recesiones": len(recs_tr),
                    "train_cambios": int((tr["label_hard"] != tr["label_hard"].shift()).iloc[1:].sum())})
    return out


# ------------------------------------------------------------------ 4. diagnósticos
def diagnostics(inputs: dict, base: pd.DataFrame) -> dict:
    b = base.set_index("date")
    lv = inputs["levels"]
    out = {}
    # empalmes: diferencia IPC subyacente − PCE subyacente por periodo
    cpi = R.ann_change(lv["CPILFESL"].dropna())
    pce = R.ann_change(lv["PCEPILFE"].dropna())
    head = R.ann_change(lv["CPIAUCSL"].dropna())
    d = (cpi - pce).dropna()
    out["cpi_core_minus_pce_core"] = {k: float(d.loc[a:z].mean()) for k, (a, z) in {
        "1959-1969": ("1959", "1969"), "1959-1964": ("1959", "1964"), "1970-1999": ("1970", "1999"),
        "2000-2024": ("2000", "2024"), "todo": ("1959", "2026")}.items()}
    dh = (head - cpi).dropna()
    out["cpi_head_minus_core_1957_1965"] = float(dh.loc["1957":"1965"].mean())
    # salto en los empalmes
    for t0, lab in (("1957-04-01", "headline→cpi_core_adj"), ("1959-04-01", "cpi_core_adj→pce_core")):
        t0 = pd.Timestamp(t0)
        out[f"I alrededor de {lab}"] = {f"{d_:%Y-%m}": round(float(b.at[d_, "I"]), 2) for d_ in
                                         pd.date_range(t0 - pd.DateOffset(months=3), t0 + pd.DateOffset(months=2),
                                                       freq="MS")}
    # 1955-01 → 1957-03 con IPC general y κ de PCE: cuántos meses cambiarían con κ_IPC ≈ 2,9
    x = b.loc["1955-01":"1957-03"]
    out["headline_1955_57"] = {"n": int(len(x)), "I_alta_k2.5": int((x["I"] > 2.5).sum()),
                               "I_alta_k2.9": int((x["I"] > 2.9).sum()),
                               "I_alta_k2.5_menos_0.4": int((x["I"] - 0.4 > 2.5).sum())}
    # proximidad al umbral: meses puntuables con |I−κ| < s_I y |G| < s_G
    sc = scored(b)
    out["cerca_umbral"] = {"I": int(((sc["I"] - P0.kappa).abs() < P0.s_I_fixed).sum()),
                           "G": int((sc["G"].abs() < P0.s_G_fixed).sum()), "n": int(len(sc))}
    # σ_i con muestra completa → ¿cambian los meses maduros al añadir datos? (σ hasta 2021-10 vs completa)
    gc = R.growth_components(inputs["levels"], P0)["comp"]
    sig_trunc = {sid: R.robust_sd((c["g"] - c["tau"]).loc[:"2016-12"]) for sid, c in gc.items()}
    out["sigma_full_vs_2016"] = {sid: (round(c["sigma"], 3), round(sig_trunc[sid], 3)) for sid, c in gc.items()}
    # inflación: meses de la etiqueta en que la persistencia ingenua (t−1) difiere de la etiqueta disponible en t
    lbl = sc["label_hard"]
    out["persistencia_t1_vs_t5"] = {"acierto_t-1": float((lbl == lbl.shift(1)).mean()),
                                    "acierto_t-5": float((lbl == lbl.shift(5)).mean()),
                                    "acierto_t-6": float((lbl == lbl.shift(6)).mean())}
    # G-I por épocas
    out["corr_GI"] = {e: float(sc.loc[a:z, "G"].corr(sc.loc[a:z, "I"])) for e, (a, z) in
                      {"1955-1983": ("1955", "1983"), "1984-2021": ("1984", "2021")}.items()}
    # 2020-T2: qué pasa en 2020-06
    out["2020"] = b.loc["2020-01":"2020-09", ["G", "I", "label_hard", "max_prob"]].round(2).astype(str).to_dict("index")
    out["2020"] = {f"{k:%Y-%m}": v for k, v in out["2020"].items()}
    return out



# ------------------------------------------------------------------ 5. contrastes externos que faltan en la §8
def external_extra(base: pd.DataFrame) -> dict:
    b = base.set_index("date")
    sc = scored(b)
    con = db.connect()
    try:
        med = db.series(con, "MEDCPIM158SFRBCLE")      # IPC mediano, % mensual anualizado (Cleveland Fed)
        trim12 = db.series(con, "PCETRIM12M159SFRBDAL")  # PCE media recortada, % interanual (Dallas Fed)
        sticky = db.series(con, "CORESTICKM159SFRBATL")
        headline = R.monthly(con, "CPIAUCSL")
    finally:
        con.close()
    out = {}
    # (a) eje I frente a medidas alternativas, misma ventana (tasas mensuales t−2…t+3)
    med6 = med.rolling(6).mean().shift(-3)
    j = pd.concat([sc["I"], med6.rename("m")], axis=1, join="inner").dropna()
    off = float((j["m"] - j["I"]).median())
    agree = ((j["I"] > P0.kappa) == (j["m"] > P0.kappa + off)).mean()
    out["IPC_mediano"] = {"n": int(len(j)), "corr": float(j["I"].corr(j["m"])), "desfase_mediano": off,
                          "acuerdo_signo_umbral_equiv": float(agree)}
    t12 = trim12.shift(-6)  # interanual en t+6 ≈ ventana centrada t−5…t+6
    j = pd.concat([sc["I"], t12.rename("m")], axis=1, join="inner").dropna()
    off = float((j["m"] - j["I"]).median())
    out["PCE_recortada_12m"] = {"n": int(len(j)), "corr": float(j["I"].corr(j["m"])), "desfase_mediano": off,
                                "acuerdo_signo_umbral_equiv": float(((j["I"] > P0.kappa) == (j["m"] > P0.kappa + off)).mean())}
    # (b) episodios de inflación de la literatura (Neville et al., 2021: IPC interanual > 5 %, EE. UU.)
    yoy = 100 * (headline / headline.shift(12) - 1)
    hi = yoy > 5
    eps = []
    grp = (hi != hi.shift()).cumsum()
    for _, g in yoy[hi].groupby(grp[hi]):
        a, z = g.index.min(), g.index.max()
        if a < pd.Timestamp("1955-01-01") or len(g) < 6:
            continue
        x = sc.loc[a:z]
        eps.append({"desde": f"{a:%Y-%m}", "hasta": f"{z:%Y-%m}", "n_puntuables": int(len(x)),
                    "pct_I_alta": float((x["I"] > P0.kappa).mean()) if len(x) else None})
    out["episodios_inflacion_IPC>5%"] = eps
    # (c) puntos de giro NBER: meses entre el pico/valle y el primer cruce de G por cero
    rec = b["usrec"].fillna(0).astype(int)
    peaks = rec.index[(rec == 1) & (rec.shift(fill_value=0) == 0)]
    troughs = rec.index[(rec == 1) & (rec.shift(-1, fill_value=0) == 0)]
    G = b["G"]
    tp = []
    for pk, tr in zip(peaks, troughs):
        if pk < pd.Timestamp("1955-01-01"):
            continue
        w = G.loc[pk - pd.DateOffset(months=12): pk + pd.DateOffset(months=12)]
        neg = w[(w < 0) & (w.shift(1) >= 0)]
        cross_dn = int(round((neg.index - pk).days.values[np.argmin(np.abs((neg.index - pk).days.values))] / 30.44)) if len(neg) else None
        w2 = G.loc[tr - pd.DateOffset(months=12): tr + pd.DateOffset(months=12)]
        pos = w2[(w2 > 0) & (w2.shift(1) <= 0)]
        cross_up = int(round((pos.index - tr).days.values[np.argmin(np.abs((pos.index - tr).days.values))] / 30.44)) if len(pos) else None
        tp.append({"pico": f"{pk:%Y-%m}", "valle": f"{tr:%Y-%m}", "G<0 frente al pico (m)": cross_dn,
                   "G>0 frente al valle (m)": cross_up})
    out["giros_NBER"] = tp
    # (d) meses NBER con P(G alto) < 0,5 que ya estaban por debajo antes del pico (efecto ventana centrada)
    pre = []
    for pk in peaks:
        if pk < pd.Timestamp("1955-01-01"):
            continue
        x = b.loc[pk - pd.DateOffset(months=4): pk - pd.DateOffset(months=1)]
        pre.append(int((x["p_g_high"] < 0.5).sum()))
    out["meses_pre_pico_con_G_bajo"] = {"total": int(sum(pre)), "de": 4 * len(pre)}
    return out


def main() -> None:
    con = db.connect()
    try:
        inputs = R.load_inputs(con, P0)
        ext = C.external(con)
    finally:
        con.close()
    base = pd.read_parquet(OFFICIAL)
    assert R.content_hash(base) == json.loads(OFFICIAL.with_suffix(".meta.json").read_text())["sha256_content"]
    res = {
        "sensibilidad": sensitivity(inputs, ext, base),
        "bloqueado": blocked(base),
        "diagnosticos": diagnostics(inputs, base),
        "revision_robustez": revision_robustness(inputs),
        "revision_C": revision_variant_c(inputs),
        "externos": external_extra(base),
    }
    out = sys.argv[1] if len(sys.argv) > 1 else None
    txt = json.dumps(res, indent=1, ensure_ascii=False, default=str)
    if out:
        open(out, "w").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
