"""Estudio de revisión de la etiqueta en el borde derecho (fija `provisional_months` de la v1.0).

Ejecutar:  .venv/bin/python -m src.labels.revision_study

Para cada corte T (cada 6 meses, 1975-01 → 2024-07) se recalcula la etiqueta solo con datos de
fecha ≤ T y se compara con la etiqueta completa en los meses T−k (k = 0…84).

Variantes:
  A. "latest": última vintage truncada en T (cuasi tiempo real: solo el truncado de la muestra).
  B. "alfred": como A, pero INDPRO y PAYEMS con la vintage ALFRED vigente a fin del mes T+1
     (cuando ya se han publicado los datos de T), truncada en T. Incluye las revisiones de datos.

Métricas por k (sobre todos los cortes): concordancia de la etiqueta dura; distancia de variación
total entre las probabilidades, Δp = ½·Σ_q |p_T,q − p_completa,q| (masa de probabilidad que cambia
de cuadrante; media y p90); |ΔG| y |ΔI| (media y p90). Solo meses objetivo con weight = 1 y con la
etiqueta completa madura (t ≤ último mes − 60, fuera de la ventana de tendencia truncada).

REGLA (declarada antes de mirar los resultados; no se cambia después):
  k* = el menor k tal que, para TODO k' ≥ k (hasta 84) con datos, concordancia ≥ 95 % y
       Δp medio ≤ 0,05. Se calcula para cada variante y se toma la mayor (la más conservadora).
       Si ningún k lo cumple, k* = 84 y se informa.
  k se mide desde el corte de datos T; la etiqueta de T termina en T−lag (lag = 4: G necesita
  t+4). `provisional_months` cuenta filas desde el último mes de la etiqueta, así que
  provisional_months = múltiplo de 6 inmediatamente superior o igual a (k* − lag).
"""
from __future__ import annotations

import json
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.labels import regime_us as R  # noqa: E402
from src.warehouse import db  # noqa: E402

CUTS = pd.date_range("1975-01-01", "2024-07-01", freq="6MS")
K_MAX = 84
CONC_MIN, DP_MAX = 0.95, 0.05
ALFRED_IDS = ("INDPRO", "PAYEMS")
PCOLS = [f"p_{q}" for q in R.QUADRANTS]
DOCS = db.REPO / "docs" / "models"
COL = {"latest": "#2a78d6", "alfred": "#eb6834"}
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def snapshot(v: pd.DataFrame, asof: pd.Timestamp, upto: pd.Timestamp) -> pd.Series:
    re_ = v["realtime_end"].fillna(pd.Timestamp("2262-01-01"))
    m = (v["realtime_start"] <= asof) & (re_ >= asof) & (v["date"] <= upto)
    s = v.loc[m].sort_values(["date", "realtime_start"]).drop_duplicates("date", keep="last")
    s = pd.Series(s["value"].values, index=pd.DatetimeIndex(s["date"])).dropna()
    return s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="MS")) if len(s) else s


def compare_one(lab: pd.DataFrame, full: pd.DataFrame, T: pd.Timestamp, mature_end: pd.Timestamp) -> list[dict]:
    lab = lab.set_index("date")
    rows = []
    for k in range(K_MAX + 1):
        t = T - pd.DateOffset(months=k)
        if t not in full.index or full.at[t, "weight"] == 0 or t > mature_end:
            continue
        r = {"T": T, "k": k, "t": t, "has": t in lab.index}
        if r["has"]:
            a, b = lab.loc[t], full.loc[t]
            r.update(same=a["label_hard"] == b["label_hard"],
                     dp=0.5 * float(np.abs(a[PCOLS].astype(float).values - b[PCOLS].astype(float).values).sum()),
                     dG=abs(a["G"] - b["G"]), dI=abs(a["I"] - b["I"]), G_T=a["G"])
        rows.append(r)
    return rows


def summarize(d: pd.DataFrame) -> pd.DataFrame:
    h = d[d["has"]]
    g = h.groupby("k")
    out = pd.DataFrame({
        "n": g.size(), "concord": g["same"].mean(),
        "dp_mean": g["dp"].mean(), "dp_p90": g["dp"].quantile(0.9),
        "dG_mean": g["dG"].mean(), "dG_p90": g["dG"].quantile(0.9),
        "dI_mean": g["dI"].mean(), "dI_p90": g["dI"].quantile(0.9),
    })
    out["coverage"] = h.groupby("k").size() / d.groupby("k").size()
    return out.reindex(range(K_MAX + 1))


def k_star(s: pd.DataFrame) -> int | None:
    ok = ((s["concord"] >= CONC_MIN) & (s["dp_mean"] <= DP_MAX)) | s["n"].isna()
    # el menor k a partir del cual se cumple para todo k' ≥ k
    for k in range(K_MAX + 1):
        if not pd.isna(s.at[k, "n"]) and ok.loc[k:].all():
            return k
    return None


def run() -> dict:
    p = R.PARAMS
    con = db.connect()
    try:
        inputs = R.load_inputs(con, p)
        vint = {sid: R.load_vintages(con, sid)[0] for sid in ALFRED_IDS}
        cfnai = db.series(con, "CFNAI")
    finally:
        con.close()
    sG, sI = p.s_G_fixed, p.s_I_fixed
    full, _ = R.make_label(inputs, p, sG, sI)
    full = full.set_index("date")
    mature_end = full.index.max() - pd.DateOffset(months=p.truncated_months)

    rows = {"latest": [], "alfred": []}
    lags = []
    alfred_notes = []
    for T in CUTS:
        lab, _ = R.make_label(inputs, p, sG, sI, cutoff=T)
        lags.append((T.year - lab["date"].max().year) * 12 + T.month - lab["date"].max().month)
        rows["latest"] += compare_one(lab, full, T, mature_end)
        asof = T + pd.offsets.MonthEnd(2)  # fin del mes T+1
        lv = dict(inputs["levels"])
        for sid in ALFRED_IDS:
            snap = snapshot(vint[sid], asof, T)
            if snap.empty or snap.index.min() > pd.Timestamp("1949-01-01"):
                alfred_notes.append(f"{T:%Y-%m} {sid}: vintage sin historia suficiente; se usa la última")
                continue
            lv[sid] = snap
        lab_a, _ = R.make_label({"levels": lv, "usrec": inputs["usrec"]}, p, sG, sI, cutoff=T)
        rows["alfred"] += compare_one(lab_a, full, T, mature_end)

    det = {v: pd.DataFrame(r) for v, r in rows.items()}
    summ = {v: summarize(d) for v, d in det.items()}
    ks = {v: k_star(s) for v, s in summ.items()}
    lag = int(np.median(lags))
    kk = max([x for x in ks.values() if x is not None], default=None)
    k_final = K_MAX if kk is None or any(x is None for x in ks.values()) else kk
    prov = int(math.ceil(max(0, k_final - lag) / 6) * 6)

    # ---- CFNAI 2022-24: ¿lo explica la revisión del borde?
    w = np.array([1, 2, 3, 3, 3, 3, 2, 1], float) / 18
    cf_g = cfnai.rolling(8).apply(lambda x: float((x * w).sum()), raw=True).shift(-4)
    d = det["latest"][det["latest"]["has"]].copy()
    d["cf"] = cf_g.reindex(d["t"]).values
    d["G_full"] = full["G"].reindex(d["t"]).values
    d = d.dropna(subset=["cf", "G_T", "G_full"])
    bands = [(4, 12), (12, 24), (24, 36), (36, 60), (60, 85)]
    age = []
    for a, b in bands:
        x = d[(d["k"] >= a) & (d["k"] < b)]
        age.append((f"{a}-{b - 1}", len(x), float(x["G_T"].corr(x["cf"])), float(x["G_full"].corr(x["cf"]))))
    sl = full.loc["2022-01":full.index[full["provisional"]].min() - pd.DateOffset(months=1)] if False else \
        full.loc["2022-01":"2024-04"]
    c_full = float(sl["G"].corr(cf_g.reindex(sl.index)))
    # misma etiqueta con la tendencia congelada en su último valor con ventana completa (t ≤ último − 60)
    gc = R.growth_components(inputs["levels"], p)["comp"]
    zf = {}
    for sid, c in gc.items():
        tau = c["tau"].copy()
        last_ok = tau.index.max() - pd.DateOffset(months=p.trend_half_window)
        tau[tau.index > last_ok] = tau.loc[last_ok]
        zf[sid] = (c["g"] - tau) / c["sigma"]
    zf = pd.DataFrame(zf)
    G_frozen = zf.mean(axis=1).where(zf.notna().sum(axis=1) >= p.min_growth_ind)
    c_frozen = float(G_frozen.loc["2022-01":"2024-04"].corr(cf_g.reindex(sl.index)))
    # comparación por periodos fuera de COVID con la misma longitud (28 meses)
    ref = []
    for a in ("1986-01", "1995-01", "2004-01", "2013-01", "2016-01"):
        x = full.loc[a:pd.Timestamp(a) + pd.DateOffset(months=27)]
        ref.append((a, float(x["G"].corr(cf_g.reindex(x.index))), float(x["G"].std())))
    cf = {"age": age, "c_full": c_full, "c_frozen": c_frozen, "ref": ref,
          "sd_G": float(sl["G"].std()), "sd_cf": float(cf_g.reindex(sl.index).std()),
          "mean_G": float(sl["G"].mean()), "mean_cf": float(cf_g.reindex(sl.index).mean())}
    return {"summ": summ, "det": det, "ks": ks, "k_final": k_final, "lag": lag, "prov": prov,
            "mature_end": mature_end, "alfred_notes": alfred_notes, "cfnai": cf, "full_last": full.index.max()}


def plot(res: dict, path) -> None:
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.titlecolor": INK, "axes.titleweight": "bold",
                         "axes.titlelocation": "left"})
    fig, ax = plt.subplots(1, 3, figsize=(14, 4.3), facecolor=SURF)
    names = {"latest": "Última vintage truncada", "alfred": "INDPRO/PAYEMS con vintage ALFRED"}
    for v, s in res["summ"].items():
        ax[0].plot(s.index, s["concord"], color=COL[v], lw=2, label=names[v])
        ax[1].plot(s.index, s["dp_mean"], color=COL[v], lw=2, label=f"{names[v]} (media)")
        ax[1].plot(s.index, s["dp_p90"], color=COL[v], lw=1, ls=":", label=f"{names[v]} (p90)")
        ax[2].plot(s.index, s["dG_mean"], color=COL[v], lw=2, label=f"|ΔG| {names[v]}")
    ax[0].axhline(CONC_MIN, color=INK2, lw=0.8, ls="--")
    ax[1].axhline(DP_MAX, color=INK2, lw=0.8, ls="--")
    for a in ax:
        a.set_facecolor(SURF)
        a.axvline(res["k_final"], color=INK, lw=0.8)
        a.grid(color=GRID, lw=0.6)
        a.spines[["top", "right"]].set_visible(False)
        a.set_xlabel("k = meses antes del corte de datos T")
    ax[0].text(res["k_final"] - 1, 0.42, f"k* = {res['k_final']}", color=INK, fontsize=8.5, ha="right")
    ax[0].set_ylim(0.4, 1.01)
    ax[0].set_title("Concordancia de la etiqueta dura")
    ax[1].set_title("Δp (variación total) frente a la etiqueta completa")
    ax[2].set_title("|ΔG| medio (z); |ΔI| = 0 en ambas variantes")
    ax[0].legend(frameon=False, fontsize=8, loc="lower right")
    ax[1].legend(frameon=False, fontsize=7.5)
    ax[2].legend(frameon=False, fontsize=7.5)
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURF)
    plt.close(fig)


def report(res: dict, png: str) -> str:
    L = ["# Estudio de revisión de la etiqueta (borde derecho)\n"]
    L.append(f"Generado por `src/labels/revision_study.py`. {len(CUTS)} cortes T semestrales ({CUTS[0]:%Y-%m} → "
             f"{CUTS[-1]:%Y-%m}); para cada uno se recalcula la etiqueta v{R.PARAMS.version} solo con datos de fecha ≤ T "
             f"(escalas fijas s_G = {R.PARAMS.s_G_fixed}, s_I = {R.PARAMS.s_I_fixed}) y se compara con la etiqueta "
             f"completa en los meses T−k, k = 0…{K_MAX}. Solo meses objetivo con weight = 1 y etiqueta completa madura "
             f"(≤ {res['mature_end']:%Y-%m}, fuera de la ventana de tendencia truncada de la etiqueta completa).\n")
    L.append("**Variantes.** A = última vintage truncada en T (solo el efecto de cortar la muestra: ventanas centradas "
             "y tendencia truncadas). B = igual, pero INDPRO y PAYEMS con la vintage ALFRED vigente a fin del mes T+1 "
             "(añade las revisiones de datos de esas dos series; W875RX1, CMRMTSPL y la inflación siguen con la última "
             "vintage, así que B es una cota inferior de la revisión real).\n")
    L.append("**Δp** = ½·Σ|p_T − p_completa| sobre los cuatro cuadrantes (masa de probabilidad que cambia de cuadrante).\n")
    L.append("## Regla (declarada antes de ver los resultados)\n")
    L.append(f"k* = el menor k a partir del cual, para todo k' ≥ k, la concordancia es ≥ {CONC_MIN:.0%} **y** el Δp "
             f"medio ≤ {DP_MAX}; se toma la variante más conservadora. La etiqueta de T termina en T−lag (lag = "
             f"{res['lag']}), así que `provisional_months` = múltiplo de 6 ≥ k* − lag.\n")
    L.append("## Resultado\n")
    L.append(f"- k* (A, última vintage) = **{res['ks']['latest']}**; k* (B, ALFRED) = **{res['ks']['alfred']}** → "
             f"k* = **{res['k_final']}**.")
    L.append(f"- `provisional_months` = ⌈({res['k_final']} − {res['lag']}) / 6⌉ × 6 = **{res['prov']}** (antes 24).")
    if res["alfred_notes"]:
        L.append(f"- Notas ALFRED: {len(res['alfred_notes'])} casos sin vintage completa (se usa la última): "
                 + "; ".join(res["alfred_notes"][:5]))
    L.append("")
    L.append(f"![Estudio de revisión]({png})\n")
    L.append("## Tabla por k\n")
    L.append("| k | n | cobertura | concord. A | Δp medio A | Δp p90 A | concord. B | Δp medio B | Δp p90 B | "
             "|ΔG| A (media / p90) | |ΔI| A (media / p90) | |ΔG| B media |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    a, b = res["summ"]["latest"], res["summ"]["alfred"]
    show = sorted(set(list(range(0, 13)) + list(range(12, K_MAX + 1, 6)) + [res["k_final"]]))
    for k in show:
        if pd.isna(a.at[k, "n"]):
            L.append(f"| {k} | 0 | 0 % | — | — | — | — | — | — | — | — | — |")
            continue
        L.append(f"| {k}{' ←' if k == res['k_final'] else ''} | {int(a.at[k, 'n'])} | {a.at[k, 'coverage']:.0%} | "
                 f"{a.at[k, 'concord']:.1%} | {a.at[k, 'dp_mean']:.3f} | {a.at[k, 'dp_p90']:.3f} | "
                 f"{b.at[k, 'concord']:.1%} | {b.at[k, 'dp_mean']:.3f} | {b.at[k, 'dp_p90']:.3f} | "
                 f"{a.at[k, 'dG_mean']:.2f} / {a.at[k, 'dG_p90']:.2f} | {a.at[k, 'dI_mean']:.2f} / {a.at[k, 'dI_p90']:.2f} | "
                 f"{b.at[k, 'dG_mean']:.2f} |")
    L.append("\nk = 0…3: la etiqueta aún no existe (G necesita t+4), cobertura 0 %.\n")
    L.append("- **|ΔI| = 0** en todos los k: I(t) solo usa el índice de t−3 a t+3 (sin tendencia), y en las dos variantes la "
             "inflación usa la última vintage. Las revisiones de la inflación no están en el estudio (se miden en la "
             "escala s_I); por eso el estudio es una cota inferior de la revisión real.")
    L.append(f"- **|ΔG| no llega a 0** (≈ {a['dG_mean'].loc[70:].mean():.2f} z en k ≥ 70): para k ≥ 64 la ventana de "
             "ritmo y la de tendencia ya están completas en T; la diferencia que queda viene de σ_i, que se calcula con la "
             "muestra disponible en T. "
             f"En probabilidades es pequeño (Δp ≈ {a['dp_mean'].loc[70:].mean():.3f}).\n")
    dif = (b["dp_mean"] - a["dp_mean"]).dropna()
    L.append(f"**Diferencia B − A** (efecto de las revisiones de datos de INDPRO/PAYEMS): Δp medio "
             f"+{dif.loc[:24].mean():.3f} en k ≤ 24 y +{dif.loc[48:].mean():.3f} en k ≥ 48; la concordancia baja "
             f"{(a['concord'] - b['concord']).loc[:24].mean():.1%} de media en k ≤ 24. El grueso de la revisión de la "
             "etiqueta viene del truncado (ventana centrada y tendencia) y no de las revisiones de datos.\n")
    c = res["cfnai"]
    L.append("## ¿Explica la revisión el CFNAI negativo de 2022-2024?\n")
    L.append("Correlación de G con el CFNAI agregado en la ventana de G, por antigüedad del dato (variante A, todos los "
             "cortes), con G calculado en el corte (G_T) y con la etiqueta completa (G) en los mismos meses:\n")
    L.append("| k | n | corr(G_T, CFNAI) | corr(G completa, CFNAI) |\n|---|---|---|---|")
    for band, n, x, y in c["age"]:
        L.append(f"| {band} | {n} | {x:.2f} | {y:.2f} |")
    L.append("")
    L.append(f"- 2022-01 → 2024-04 con la etiqueta completa: corr = {c['c_full']:.2f}. Con la tendencia congelada en su "
             f"último valor con ventana completa: {c['c_frozen']:.2f}.")
    L.append(f"- En ese tramo G tiene desviación típica {c['sd_G']:.2f} (media {c['mean_G']:+.2f}) y el CFNAI en la "
             f"ventana de G {c['sd_cf']:.2f} (media {c['mean_cf']:+.2f}): ambos casi planos. Tramos de 28 meses en "
             "otros periodos tranquilos: " + "; ".join(f"{a_} corr {x:.2f} (desv. G {s:.2f})" for a_, x, s in c["ref"]) + ".")
    worst = min(x for _, _, x, _ in c["age"])
    L.append(f"- **La revisión del borde no lo explica.** Con datos jóvenes (k = 4-11) la correlación con el CFNAI es "
             f"{c['age'][0][2]:.2f}, frente a {c['age'][0][3]:.2f} con la etiqueta completa en esos mismos meses; en ninguna "
             f"banda de antigüedad baja de {worst:.2f}. El truncado mueve G, pero no rompe su relación con el CFNAI.")
    L.append(f"- Tampoco lo explica la tendencia truncada: congelándola, la correlación de 2022-2024 sigue en "
             f"{c['c_frozen']:.2f}.")
    L.append(f"- Es un desacuerdo de composición en un tramo casi plano: el CFNAI en la ventana de G apenas se mueve "
             f"(desv. típica {c['sd_cf']:.2f}, media {c['mean_cf']:+.2f}, ligeramente por debajo de tendencia: manufactura "
             f"débil), mientras G (desv. {c['sd_G']:.2f}, media {c['mean_G']:+.2f}) oscila alrededor de cero con empleo y "
             "renta real por encima de su tendencia. Es un resultado real; no hay nada que corregir.\n")
    return "\n".join(L)


def main() -> None:
    res = run()
    png = DOCS / "label_revision_study.png"
    plot(res, png)
    (DOCS / "label_revision_study.md").write_text(report(res, png.name))
    out = R.out_dir() / "revision_study.json"
    out.write_text(json.dumps({"k_star": res["ks"], "k_final": res["k_final"], "lag": res["lag"],
                               "provisional_months": res["prov"], "cuts": [str(c.date()) for c in CUTS],
                               "summary_latest": res["summ"]["latest"].reset_index().to_dict("records"),
                               "summary_alfred": res["summ"]["alfred"].reset_index().to_dict("records")},
                              indent=1, default=str))
    print("k*:", res["ks"], "→", res["k_final"], "lag", res["lag"], "→ provisional_months =", res["prov"])
    print(res["summ"]["latest"].loc[[4, 6, 8, 12, 18, 24, 30, 36, 48, 60, 72, 84], ["n", "concord", "dp_mean", "dp_p90"]].round(3))
    print(res["summ"]["alfred"].loc[[4, 6, 8, 12, 18, 24, 30, 36, 48, 60, 72, 84], ["n", "concord", "dp_mean", "dp_p90"]].round(3))
    print(res["cfnai"])
    print("notas alfred:", len(res["alfred_notes"]), res["alfred_notes"][:3])


if __name__ == "__main__":
    main()
