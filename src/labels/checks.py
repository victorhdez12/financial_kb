"""Comprobaciones de la §8 de docs/models/label_spec.md para la etiqueta de régimen EE. UU.

Ejecutar:  .venv/bin/python -m src.labels.checks

Detectan errores de cálculo; NO sirven para ajustar parámetros. Escribe
docs/models/label_v<version>_checks.md y docs/models/label_v<version>.png. Si existe la versión
anterior (PREV_VERSION) en la carpeta de etiquetas, añade la comparación entre versiones.

Muestra puntuable: weight > 0 (fuera 1950-1954) y no provisional (fuera los últimos 24 meses).
Cada criterio se calcula en esa muestra y, aparte, sin los meses de frontera.
"""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.labels import regime_us as R  # noqa: E402
from src.warehouse import db  # noqa: E402

DOCS = db.REPO / "docs" / "models"
PREV_VERSION = "0.2"
NAMES = {"expansion": "Expansión", "late_cycle": "Late cycle / sobrecal.",
         "stagflation": "Estanflación", "low_growth_disinfl": "Crec. bajo / desinflación"}
# paleta categórica validada (dataviz validate_palette: PASS en luminosidad, croma, CVD y visión normal)
COLORS = {"expansion": "#1baf7a", "late_cycle": "#eda100", "stagflation": "#e34948",
          "low_growth_disinfl": "#2a78d6"}
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
PCOLS = [f"p_{q}" for q in R.QUADRANTS]
# CFNAI mensual ≈ crecimiento del mes k. G(t) = media triangular de las tasas de t−3…t+4
W_G = np.array([1, 2, 3, 3, 3, 3, 2, 1], float) / 18

EPISODES = [  # (nombre, desde, hasta, cuadrantes esperados, descripción del criterio)
    ("1973-75", "1973-01", "1975-12", ("stagflation",), "estanflación dominante"),
    ("1979-80", "1979-01", "1980-12", ("stagflation",), "estanflación dominante"),
    ("2021-T2 a 2022", "2021-04", "2022-12", ("late_cycle", "stagflation"), "sobrecalentamiento / estanflación"),
    ("1995-99", "1995-01", "1999-12", ("expansion",), "expansión"),
    ("2008-09", "2008-01", "2009-12", ("low_growth_disinfl",), "crecimiento bajo / desinflación"),
    ("2020-T2", "2020-04", "2020-06", ("low_growth_disinfl",), "crecimiento bajo / desinflación"),
]


def load(version: str | None = None) -> tuple[pd.DataFrame, dict]:
    version = version or R.PARAMS.version
    path = R.out_dir() / f"regime_us_v{version}.parquet"
    if version == R.PARAMS.version and not path.exists():
        df, info = R.build()
        R.write(df, info["meta"])
    df = pd.read_parquet(path)
    meta = json.loads(path.with_suffix(".meta.json").read_text())
    return df.set_index("date"), meta


def runs(lbl: pd.Series) -> pd.DataFrame:
    grp = (lbl != lbl.shift()).cumsum()
    r = lbl.groupby(grp).agg(["first", "size"])
    r.columns = ["regime", "months"]
    return r


def fmt(x, d=2):
    return "—" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{d}f}"


def external(con) -> dict:
    cfnai3 = db.series(con, "CFNAIMA3")
    cfnai = db.series(con, "CFNAI")
    gdp = db.series(con, "GDPC1")
    pot = con.execute("select date, value from forecasts where series_id='GDPPOT' order by date").df()
    pot = pd.Series(pot["value"].values, index=pd.to_datetime(pot["date"]))
    # CFNAI en la ventana de G: media triangular de t−3…t+4
    cf_g = cfnai.rolling(8).apply(lambda x: float((x * W_G).sum()), raw=True).shift(-4)
    gap = 100 * np.log(gdp / pot.reindex(gdp.index)).dropna()
    return {"cfnai3": cfnai3, "cfnai": cfnai, "cf_g": cf_g, "gap": gap,
            "cpic": R.monthly(con, "CPILFESL"), "pce": R.monthly(con, "PCEPILFE")}


def criteria(m: pd.DataFrame, ext: dict) -> list[tuple]:
    """Criterios §8 sobre la muestra `m`. Devuelve (nombre, esperado, obtenido, ok)."""
    rows = []
    rec = m[m["usrec"] == 1]
    share = float((rec["p_g_high"] < 0.5).mean()) if len(rec) else np.nan
    rows.append(("Meses NBER de recesión con P(G alto) < 0,5", "≥ 85 %", f"{share:.1%} (n={len(rec)})", share >= 0.85))
    j = pd.concat([m["G"], ext["cfnai3"].rename("c")], axis=1, join="inner").dropna()
    rho = float(j["G"].corr(j["c"]))
    rows.append(("Correlación G con CFNAI-MA3 contemporáneo (1967+)", "> 0,7", f"{rho:.2f} (n={len(j)})", rho > 0.7))
    j = pd.concat([m["G"], ext["cf_g"].rename("c")], axis=1, join="inner").dropna()
    rho = float(j["G"].corr(j["c"]))
    rows.append(("Correlación G con CFNAI en la ventana de G (t−3…t+4)", "> 0,7", f"{rho:.2f} (n={len(j)})", rho > 0.7))
    # brecha: G en el mes central del trimestre Q = media de Q+1 frente a Q−1 → gap(Q+1) − gap(Q−1)
    gap = ext["gap"]
    gq = m["G"][m.index.month.isin([2, 5, 8, 11])]
    gq.index = gq.index - pd.offsets.MonthBegin(1)
    d2c = (gap.shift(-1) - gap.shift(1)).rename("d2c")
    q = pd.concat([gq.rename("G"), d2c], axis=1, join="inner").dropna()
    r_main = float(q["G"].corr(q["d2c"]))
    rows.append(("Correlación G con la brecha (GDPC1 vs GDPPOT), en cambios", "> 0,6",
                 f"{r_main:.2f} (G vs Δ brecha T−1→T+1; n={len(q)})", r_main > 0.6))
    for name, a, b, want, desc in EPISODES:
        x = m.loc[a:b]
        if x.empty:
            rows.append((f"Episodio {name}", desc, "sin meses", False))
            continue
        counts = x["label_hard"].value_counts()
        share_w = float(x["label_hard"].isin(want).mean())
        meanp = x[PCOLS].mean()
        ok = (counts.idxmax() == want[0] and meanp.idxmax() == f"p_{want[0]}") if len(want) == 1 else share_w > 0.5
        got = f"{share_w:.0%} en {'/'.join(NAMES[w] for w in want)} (n={len(x)})"
        rows.append((f"Episodio {name}", desc, got, ok))
    dist = m["label_hard"].value_counts(normalize=True).reindex(R.QUADRANTS).fillna(0)
    rows.append(("Distribución por cuadrante", "ninguno < 10 %", f"mín. {dist.min():.0%} ({NAMES[dist.idxmin()]})",
                 bool((dist >= 0.10).all())))
    rr = runs(m["label_hard"])
    rows.append(("Duración media de los regímenes duros", "≥ 6 meses",
                 f"{rr['months'].mean():.1f} m ({len(rr)} tramos; mediana {rr['months'].median():.0f})",
                 rr["months"].mean() >= 6))
    gi = float(m["G"].corr(m["I"]))
    rows.append(("Correlación G-I", "se informa; revisar si |ρ| > 0,3", f"{gi:.2f}", abs(gi) <= 0.3))
    return rows


def compute(df: pd.DataFrame, meta: dict) -> dict:
    con = db.connect()
    try:
        ext = external(con)
    finally:
        con.close()
    m = df[(df["weight"] > 0) & ~df["provisional"]]
    nf = m[~m["frontera"]]
    res = {"m": m, "ext": ext, "rows": criteria(m, ext), "rows_nf": criteria(nf, ext), "n_nf": len(nf)}

    # acierto esperado de la etiqueta dura frente a la blanda (= media de max_prob)
    res["acc"] = {"all": float(m["max_prob"].mean()), "nf": float(nf["max_prob"].mean()),
                  "front": float(m.loc[m["frontera"], "max_prob"].mean()), "share_front": float(m["frontera"].mean())}
    res["rec_miss"] = m[(m["usrec"] == 1) & (m["p_g_high"] >= 0.5)][["G", "p_g_high"]]

    # diagnóstico CFNAI
    G = m["G"]
    res["cfnai"] = {"lags": {k: float(G.corr(ext["cfnai3"].shift(-k))) for k in (-2, -1, 0, 1, 2, 3)},
                    "ex_covid": float(G[~((G.index >= "2020-01-01") & (G.index <= "2021-12-01"))].corr(ext["cfnai3"])),
                    "periods": {f"{a}-{b}": (float(G.loc[a:b].corr(ext["cfnai3"].loc[a:b])),
                                             float(G.loc[a:b].corr(ext["cf_g"].loc[a:b])))
                                for a, b in (("1967", "1983"), ("1984", "2007"), ("2008", "2019"), ("2020", "2021"),
                                             ("2022", "2024")) if len(G.loc[a:b]) >= 12}}
    res["gi_post"] = float(m.loc["1984":, "G"].corr(m.loc["1984":, "I"]))

    episodes = []
    for name, a, b, want, desc in EPISODES:
        x = m.loc[a:b]
        episodes.append((name, x, x["label_hard"].value_counts(), x[PCOLS].mean()))
    res["episodes"] = episodes
    lbl = m["label_hard"]
    rr = runs(lbl)
    res["runs"] = rr
    res["runs_by"] = rr.groupby("regime")["months"].agg(["count", "mean", "median", "max"]).reindex(R.QUADRANTS)
    res["dist"] = lbl.value_counts(normalize=True).reindex(R.QUADRANTS).fillna(0)
    res["dist_nf"] = nf["label_hard"].value_counts(normalize=True).reindex(R.QUADRANTS).fillna(0)
    res["dist_soft"] = m[PCOLS].mean()
    tm = pd.crosstab(lbl.shift().dropna().rename("desde"), lbl.iloc[1:].rename("hacia"))
    res["trans"] = tm.reindex(index=R.QUADRANTS, columns=R.QUADRANTS).fillna(0).astype(int)
    m2 = m.copy()
    m2["decada"] = (m2.index.year // 10 * 10).astype(str) + "s"
    res["decades"] = pd.crosstab(m2["decada"], m2["label_hard"], normalize="index").reindex(
        columns=R.QUADRANTS).fillna(0)
    res["decade_n"] = m2["decada"].value_counts().sort_index()
    both = pd.concat([R.ann_change(ext["cpic"]), R.ann_change(ext["pce"])], axis=1, keys=["cpi", "pce"]).dropna()
    res["cpi_pce_gap"] = float((both["cpi"] - both["pce"]).mean())
    res["n_scored"] = len(m)
    res["compare"] = compare(df)
    return res


def compare(df: pd.DataFrame) -> dict | None:
    """Comparación con la versión anterior (PREV_VERSION): meses que cambian de cuadrante y dónde."""
    path = R.out_dir() / f"regime_us_v{PREV_VERSION}.parquet"
    if not path.exists():
        return None
    old = pd.read_parquet(path).set_index("date").rename(columns=R.ALIASES)
    old["label_hard"] = old["label_hard"].replace(R.ALIASES)
    idx = df.index.intersection(old.index)
    idx = idx[df.loc[idx, "weight"] > 0]  # misma muestra de pesos
    a, b = old.loc[idx, "label_hard"], df.loc[idx, "label_hard"]
    ch = a != b
    out = {"n": len(idx), "changed": int(ch.sum()), "share": float(ch.mean()),
           "cross": pd.crosstab(a.rename(f"v{PREV_VERSION}"), b.rename(f"v{R.PARAMS.version}")).reindex(
               index=R.QUADRANTS, columns=R.QUADRANTS).fillna(0).astype(int),
           "only_old": f"{old.index.max():%Y-%m}", "only_new_end": f"{df.index.max():%Y-%m}"}
    # desfase: correlación de G v0.2(t) con G v0.1(t+k)
    out["lag_G"] = {k: float(df["G"].corr(old["G"].shift(-k))) for k in range(0, 7)}
    out["lag_I"] = {k: float(df["I"].corr(old["I"].shift(-k))) for k in range(0, 7)}
    # cambios por episodio de la §8 y por recesión NBER
    ep = []
    for name, s, e, *_ in EPISODES:
        w = ch.loc[s:e]
        ep.append((name, int(w.sum()), len(w)))
    rec = df.loc[idx, "usrec"].fillna(0).astype(int)
    grp = (rec != rec.shift()).cumsum()
    for _, g in rec[rec == 1].groupby(grp[rec == 1]):
        w = ch.loc[g.index.min() - pd.DateOffset(months=6): g.index.max()]
        ep.append((f"recesión {g.index.min():%Y-%m}…{g.index.max():%Y-%m} (desde 6 m antes)", int(w.sum()), len(w)))
    out["episodes"] = ep
    # bloques de meses cambiados (consecutivos), los más largos
    blk = (ch != ch.shift()).cumsum()
    blocks = []
    for _, g in ch[ch].groupby(blk[ch]):
        i0, i1 = g.index.min(), g.index.max()
        trans = pd.Series([f"{NAMES[x]} → {NAMES[y]}" for x, y in zip(a.loc[i0:i1], b.loc[i0:i1])]).value_counts()
        blocks.append((i0, i1, len(g), trans.index[0]))
    out["n_blocks"] = len(blocks)
    out["short_share"] = float(sum(b[2] for b in blocks if b[2] <= 4) / max(1, sum(b[2] for b in blocks)))
    out["blocks"] = sorted(blocks, key=lambda x: -x[2])[:12]
    out["by_decade"] = ch.groupby(ch.index.year // 10 * 10).mean()
    po, pn = old.loc[idx, "provisional"], df.loc[idx, "provisional"]
    out["prov_old_from"] = f"{po[po].index.min():%Y-%m}"
    out["prov_new_from"] = f"{pn[pn].index.min():%Y-%m}"
    out["to_prov"] = int((pn & ~po).sum())
    out["changed_scored"] = int(ch[~pn].sum())
    out["n_scored"] = int((~pn).sum())
    tv = 0.5 * (old.loc[idx, PCOLS] - df.loc[idx, PCOLS]).abs().sum(axis=1)
    out["tv_mean"], out["tv_max"] = float(tv.mean()), float(tv.max())
    out["front_old"], out["front_new"] = int(old.loc[idx, "frontera"].sum()), int(df.loc[idx, "frontera"].sum())
    return out


def plot(df: pd.DataFrame, meta: dict, path) -> None:
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK,
                         "axes.titleweight": "bold", "axes.titlelocation": "left"})
    fig, ax = plt.subplots(3, 1, figsize=(13, 9), sharex=True, facecolor=SURF,
                           gridspec_kw={"height_ratios": [1, 1, 1.2], "hspace": 0.28})
    rec = df["usrec"].fillna(0).astype(int)
    starts = df.index[(rec == 1) & (rec.shift(fill_value=0) == 0)]
    ends = df.index[(rec == 1) & (rec.shift(-1, fill_value=0) == 0)]
    prov = df.index[df["provisional"]].min()
    w0 = df.index[df["weight"] == 0]
    for a in ax:
        a.set_facecolor(SURF)
        for s, e in zip(starts, ends):
            a.axvspan(s, e + pd.offsets.MonthEnd(0), color="#d9d8d3", lw=0, zorder=0)
        for lo, hi in ((prov, df.index.max()), (w0.min(), w0.max()) if len(w0) else (None, None)):
            if lo is not None:
                a.axvspan(lo, hi + pd.offsets.MonthEnd(0), facecolor="#f1efe8", lw=0, zorder=0, hatch="///",
                          edgecolor="#d9d8d3")
        a.grid(axis="y", color=GRID, lw=0.6)
        a.spines[["top", "right"]].set_visible(False)
    ax[0].plot(df.index, df["G"], color=INK, lw=1)
    ax[0].axhline(0, color=INK2, lw=0.8, ls="--")
    ax[0].set_title(f"G — crecimiento frente a tendencia, ventana centrada t−3…t+3 (z medio; s_G = {meta['s_G']:.2f})")
    ax[0].set_ylabel("z")
    ax[1].plot(df.index, df["I"], color=INK, lw=1)
    ax[1].axhline(meta["params"]["kappa"], color=COLORS["stagflation"], lw=1, ls="--")
    ax[1].text(df.index[min(720, len(df) - 1)], meta["params"]["kappa"] + 0.5,
               f"umbral κ = {meta['params']['kappa']} %", color=INK2, fontsize=8)
    ax[1].set_title(f"I — inflación subyacente t−3…t+3 anualizada (%; s_I = {meta['s_I']:.2f} pp)")
    ax[1].set_ylabel("%")
    ax[1].set_ylim(-3, 16)
    ys = [df[f"p_{q}"].values for q in R.QUADRANTS]
    ax[2].stackplot(df.index, ys, colors=[COLORS[q] for q in R.QUADRANTS],
                    labels=[NAMES[q] for q in R.QUADRANTS], lw=0)
    for s_, e_ in zip(starts, ends):  # el área apilada tapa el sombreado: franja de recesión encima
        ax[2].fill_between([s_, e_ + pd.offsets.MonthEnd(0)], 1.015, 1.06, color=INK2, lw=0)
    ax[2].set_ylim(0, 1.06)
    ax[2].set_yticks([0, 0.25, 0.5, 0.75, 1])
    ax[2].set_title("Probabilidad por cuadrante (apilada)")
    ax[2].legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=4, frameon=False, labelcolor=INK)
    ax[2].xaxis.set_major_locator(mdates.YearLocator(10))
    ax[2].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax[2].set_xlim(df.index.min(), df.index.max() + pd.offsets.MonthEnd(0))
    fig.suptitle(f"Etiqueta de régimen EE. UU. v{meta['version']} — {meta['first'][:7]} a {meta['last'][:7]}",
                 x=0.06, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.text(0.06, 0.935, "Gris: recesiones NBER (USREC; en el panel inferior, franja sobre el área). "
             "Rayado: 1950-1954 (peso 0) y últimos 24 meses (provisionales).", fontsize=8.5, color=INK2)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=SURF)
    plt.close(fig)


def report(df: pd.DataFrame, meta: dict, res: dict, png_name: str) -> str:
    sd = meta["scale_detail"]
    v = meta["version"]
    L = [f"# Etiqueta de régimen EE. UU. v{v} — comprobaciones (§8)\n"]
    L.append(f"Generado por `src/labels/checks.py` a partir de `data/archive/labels/regime_us_v{v}.parquet` "
             f"(hash de contenido `{meta['sha256_content'][:16]}…`). Muestra {meta['first'][:7]} → {meta['last'][:7]} "
             f"({meta['rows']} meses). **Muestra puntuable: {res['n_scored']} meses** (weight = 1 y no provisional: "
             f"fuera 1950-1954 y los {meta['params']['provisional_months']} últimos); sin frontera: {res['n_nf']}.\n")
    L.append(f"**Versión {meta.get('status', '')}.** Parámetros finales aprobados por el usuario: s_G = {meta['s_G']:.2f} y "
             f"s_I = {meta['s_I']:.2f} fijas; `provisional_months` = {meta['params']['provisional_months']} (estudio de "
             f"revisión, `docs/models/label_revision_study.md`); `embargo_months` = {meta['params']['embargo_months']}; el "
             "resto como en la v0.2. Las comprobaciones sirven para detectar errores de cálculo, **no para ajustar "
             "parámetros**; los umbrales de la §8 no cambian. Código: SHA-256 "
             f"`{meta.get('code', {}).get('sha256_code', '')[:16]}…`.\n")
    L.append(f"![Etiqueta v{v}]({png_name})\n")

    L.append("## 1. Escalas: valores fijos y estimaciones ALFRED de referencia\n")
    L.append("Error de revisión = valor del eje en t con la **primera publicación** − valor con la **última vintage**. Con "
             "ventanas centradas, la \"primera publicación\" de G(t) es la primera vintage que contiene t+4 (último nivel que "
             "necesita la media de 3 m en t+3) y la de I(t), la primera que contiene t+3; la serie se reconstruye tal como "
             "estaba en esa vintage y se le aplica la misma transformación que al eje. Esa vintage debe salir ≤ 75 días tras "
             "el fin del mes y no puede ser el inicio del archivo ALFRED. Solo fechas maduras (≤ "
             f"{meta['last_mature_for_scales'][:7]}). s = MAD × 1,4826; suelo 0,25; estable si n ≥ 60 y la MAD de cada "
             "mitad está entre ½ y 2 veces la total.\n")
    L.append("| serie / unidad | origen vintages | n | desde → hasta | sesgo medio | s | 1.ª mitad | 2.ª mitad | estable |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    org = meta.get("vintage_origin", {})
    for k, d in sd.items():
        sid = k.split("_", 2)[-1] if k.startswith(("I_", "G_z_")) else ""
        L.append(f"| {k} | {org.get(sid, '—') if sid else '—'} | {d['n']} | {str(d['from'])[:7]} → {str(d['to'])[:7]} | "
                 f"{fmt(d['mean_err'])} | {fmt(d['mad_sd'], 3)} | {fmt(d['half1'], 3)} | {fmt(d['half2'], 3)} | "
                 f"{'sí' if d['stable'] else 'no'} |")
    L.append("")
    two = sd.get("G_composite_INDPRO_PAYEMS")
    L.append(f"- **s_G = {meta['s_G']:.2f}** ({meta['how_G']}): estimación con INDPRO + PAYEMS en 1955-2024 "
             + (f"({two['mad_sd']:.3f}), " if two else "")
             + f"redondeada. La de cuatro indicadores ({sd['G_composite']['mad_sd']:.3f}, "
             f"{str(sd['G_composite']['from'])[:7]} → {str(sd['G_composite']['to'])[:7]}) era la de la v0.2: cubre solo un "
             "periodo de revisiones pequeñas.")
    L.append("- Vintages de W875RX1 y CMRMTSPL: ALFRED las tiene (desde 2010-05 y 2013-06). Se descargan con "
             "`python -m src.labels.regime_us --fetch-vintages` a `data/archive/labels/raw/alfred/` (sin tocar `src/ingest` "
             "ni el warehouse).")
    L.append(f"- **s_I = {meta['s_I']:.2f} pp** ({meta['how_I']}): PCE subyacente, estimación {sd['I_PCEPILFE']['mad_sd']:.3f}. El IPC subyacente da "
             f"{sd['I_CPILFESL']['mad_sd']:.2f} pp (solo revisa factores estacionales); contraste.")
    for n in meta["notes"]:
        L.append(f"- Nota: {n}.")
    L.append("")

    L.append("## 2. Comprobaciones\n")
    L.append("Muestra puntuable completa y, aparte, sin meses de frontera. El ✅/❌ oficial es el de la muestra completa.\n")
    L.append("| criterio | esperado | obtenido | | sin frontera | |\n|---|---|---|---|---|---|")
    for (name, exp, got, ok), (_, _, got2, ok2) in zip(res["rows"], res["rows_nf"]):
        L.append(f"| {name} | {exp} | {got} | {'✅' if ok else '❌'} | {got2} | {'✅' if ok2 else '❌'} |")
    L.append("")
    a = res["acc"]
    L.append(f"**Acierto esperado de la etiqueta dura frente a la blanda** (media de la probabilidad máxima, es decir, la "
             f"probabilidad de que el cuadrante duro coincida con el \"verdadero\"): {a['all']:.1%} en la muestra puntuable; "
             f"{a['nf']:.1%} sin frontera; {a['front']:.1%} en los {a['share_front']:.1%} de meses frontera.\n")
    L.append("**Brecha de producción.** Con la ventana centrada, G en el mes central del trimestre T compara la media de "
             "T+1 con la de T−1, así que se compara con gap(T+1) − gap(T−1). GDPPOT (CBO) sale de la vista `forecasts`, "
             "solo hasta el último GDPC1.\n")
    miss = res["rec_miss"]
    if len(miss):
        L.append(f"**Meses de recesión con P(G alto) ≥ 0,5** ({len(miss)}): "
                 + ", ".join(f"{d:%Y-%m} ({p:.2f})" for d, p in miss["p_g_high"].items()) + ".\n")
    c = res["cfnai"]
    L.append("**CFNAI (diagnóstico).** Correlación de G(t) con CFNAI-MA3(t+k): "
             + ", ".join(f"k={k:+d}: {r:.2f}" for k, r in c["lags"].items())
             + f". Sin 2020-2021: {c['ex_covid']:.2f}. Por periodos (MA3 contemporáneo / ventana de G): "
             + "; ".join(f"{p} {x:.2f} / {y:.2f}" for p, (x, y) in c["periods"].items()) + ". "
             "CFNAI-MA3(t+1) cubre t−1…t+1, centrado en t como G; el máximo está en k = +1/+2, como se espera "
             "(en la v0.1 estaba en k = −2/−3).")
    L.append("El tramo 2022-2024 (correlación negativa en la v0.2) es ahora provisional y no puntúa; el estudio de "
             "revisión muestra que no se debe al borde, sino a un desacuerdo de composición en un tramo casi plano "
             "(`docs/models/label_revision_study.md`).")
    L.append("")
    L.append(f"**Correlación G-I** (1984+: {res['gi_post']:.2f}).\n")

    L.append("## 3. Episodios\n")
    L.append("| episodio | meses | " + " | ".join(NAMES[q] for q in R.QUADRANTS) + " | prob. media dominante |")
    L.append("|---|---|" + "---|" * 4 + "---|")
    for name, x, counts, meanp in res["episodes"]:
        cc = [str(int(counts.get(q, 0))) for q in R.QUADRANTS]
        top = meanp.idxmax().replace("p_", "")
        L.append(f"| {name} | {len(x)} | " + " | ".join(cc) + f" | {NAMES[top]} ({meanp.max():.2f}) |")
    L.append("")

    L.append("## 4. Distribución por cuadrante\n")
    L.append("| cuadrante | % meses (dura) | % sin frontera | prob. media (blanda) | tramos | duración media | mediana | máx. |")
    L.append("|---|---|---|---|---|---|---|---|")
    for q in R.QUADRANTS:
        rb = res["runs_by"].loc[q]
        L.append(f"| {NAMES[q]} | {res['dist'][q]:.1%} | {res['dist_nf'][q]:.1%} | {res['dist_soft'][f'p_{q}']:.1%} | "
                 f"{int(rb['count'])} | {rb['mean']:.1f} | {rb['median']:.0f} | {int(rb['max'])} |")
    L.append("")
    L.append("### Por década (% de meses, etiqueta dura; 1950s = solo 1955-1959)\n")
    L.append("| década | meses | " + " | ".join(NAMES[q] for q in R.QUADRANTS) + " |\n|---|---|" + "---|" * 4)
    for i, r in res["decades"].iterrows():
        L.append(f"| {i} | {res['decade_n'][i]} | " + " | ".join(f"{x:.0%}" for x in r.values) + " |")
    L.append("")

    L.append("## 5. Matriz de transición (etiqueta dura, muestra puntuable)\n")
    tm = res["trans"]
    tp = tm.div(tm.sum(axis=1), axis=0)
    L.append("Recuentos (fila = mes anterior, columna = mes siguiente) y probabilidad por fila.\n")
    L.append("| desde \\ hacia | " + " | ".join(NAMES[q] for q in R.QUADRANTS) + " |\n|---|" + "---|" * 4)
    for q in R.QUADRANTS:
        L.append(f"| {NAMES[q]} | " + " | ".join(f"{tm.loc[q, x]} ({tp.loc[q, x]:.0%})" for x in R.QUADRANTS) + " |")
    L.append("")

    cmp_ = res["compare"]
    L.append(f"## 6. Comparación v{PREV_VERSION} → v{v}\n")
    if cmp_ is None:
        L.append(f"No se encuentra `regime_us_v{PREV_VERSION}.parquet`.\n")
    else:
        lg, li = cmp_["lag_G"], cmp_["lag_I"]
        L.append(f"Meses comparados: {cmp_['n']} (fechas comunes con weight = 1, 1955-01 → {cmp_['only_new_end']}). "
                 f"**Cambian de cuadrante {cmp_['changed']} meses ({cmp_['share']:.1%})**; en la muestra puntuable de la "
                 f"v{v}: {cmp_['changed_scored']} de {cmp_['n_scored']}.\n")
        L.append(f"- G e I no cambian de definición (correlación v{v} vs v{PREV_VERSION}: G {lg[0]:.3f}, I {li[0]:.3f}). "
                 "Solo cambian las escalas (s_G 0,33 → 0,40; s_I 0,305 → 0,31). Con ejes independientes, el cuadrante "
                 "de mayor probabilidad solo depende del signo de G y de I − κ, así que la etiqueta dura no cambia; cambian "
                 f"las probabilidades (Δp medio {cmp_['tv_mean']:.3f}, máximo {cmp_['tv_max']:.3f}) y los meses frontera "
                 f"({cmp_['front_old']} → {cmp_['front_new']}).")
        L.append(f"- Provisionales: desde {cmp_['prov_new_from']} (antes desde {cmp_['prov_old_from']}); "
                 f"{cmp_['to_prov']} meses dejan de puntuar.\n")
        L.append(f"| v{PREV_VERSION} \\ v{v} | " + " | ".join(NAMES[q] for q in R.QUADRANTS) + " |\n|---|" + "---|" * 4)
        for q in R.QUADRANTS:
            L.append(f"| {NAMES[q]} | " + " | ".join(str(cmp_["cross"].loc[q, x]) for x in R.QUADRANTS) + " |")
        L.append("\nCambios por episodio (meses cambiados / meses de la ventana):\n")
        L.append("| episodio | cambian | meses |\n|---|---|---|")
        for name, n, tot in cmp_["episodes"]:
            L.append(f"| {name} | {n} | {tot} |")
        if cmp_["blocks"]:
          L.append("\nBloques más largos de meses consecutivos que cambian:\n")
          L.append("| desde | hasta | meses | cambio principal |\n|---|---|---|---|")
          for i0, i1, n, tr in cmp_["blocks"]:
              L.append(f"| {i0:%Y-%m} | {i1:%Y-%m} | {n} | {tr} |")
        if cmp_["changed"]:
            L.append(f"\nLos {cmp_['changed']} meses cambiados forman {cmp_['n_blocks']} bloques; el "
                     f"{cmp_['short_share']:.0%} está en bloques de 1-4 meses.\n")
        L.append("")

    L.append("## 7. Últimos meses maduros y provisionales\n")
    mature = df[~df["provisional"]].tail(6)
    t = pd.concat([mature, df.tail(6)])
    L.append(f"Últimos 6 meses maduros (puntuables) y últimos 6 provisionales (desde {df.index[df['provisional']].min():%Y-%m}).\n")
    L.append("| mes | estado | G | I | " + " | ".join(NAMES[q] for q in R.QUADRANTS) + " | etiqueta dura | frontera |")
    L.append("|---|---|---|---|" + "---|" * 4 + "---|---|")
    for d, r in t.iterrows():
        L.append(f"| {d:%Y-%m} | {'provisional' if r['provisional'] else 'madura'} | {r['G']:.2f} | {r['I']:.2f} | "
                 + " | ".join(f"{r[f'p_{q}']:.2f}" for q in R.QUADRANTS)
                 + f" | {NAMES[r['label_hard']]} | {'sí' if r['frontera'] else 'no'} |")
    L.append("")

    L.append("## 8. Notas de implementación\n")
    de = meta.get("data_end", {})
    L.append(f"- **Final de la muestra.** Con ventanas centradas, G(t) necesita niveles hasta t+4 e I(t) hasta t+3. Último "
             f"dato: " + ", ".join(f"{k} {x[:7]}" for k, x in de.items())
             + f". G con ≥ 2 indicadores llega a {meta['last'][:7]} (2026-05 solo tendría PAYEMS), así que la etiqueta "
             f"termina en {meta['last'][:7]}, unos 4 meses antes que la v0.1. Los meses posteriores no tienen etiqueta "
             "hasta que se publiquen sus datos t+4: la etiqueta del mes t está disponible ~5 meses después.")
    L.append(f"- **Meses provisionales.** Los {meta['params']['provisional_months']} últimos de la etiqueta, fijados con la "
             "regla declarada en el estudio de revisión (concordancia ≥ 95 % y Δp medio ≤ 0,05 de forma sostenida; k* = 55 "
             "meses desde el corte de datos, 51 desde el último mes de la etiqueta, redondeado a 54). La tendencia (±60 m) "
             "sigue truncada en los últimos 60 meses.")
    L.append(f"- **Uso.** Los meses con `provisional = true` o `weight = 0` no puntúan ni entrenan. Embargo del backtest: "
             f"{meta['params']['embargo_months']} meses (la etiqueta de t usa datos hasta t+4).")
    L.append("- **Inicio.** G(1950-01) usa niveles desde 1949-09 e I(1950-01) desde 1949-10, así que el inicio no cambia. "
             "PCE subyacente centrado desde 1959-04 e IPC subyacente − 0,4 desde 1957-04 (antes 1959-07 / 1957-07). "
             f"Diferencia media IPC − PCE subyacentes (contraste del ajuste de 0,4 pp, no se cambia): {res['cpi_pce_gap']:.2f} pp.")
    L.append("- **Pesos.** `weight` = 0 en 1950-1954 (IPC general con la guerra de Corea, tendencia truncada) y 1 en el resto. "
             "Esos meses no puntúan (ni en el backtest ni en estas comprobaciones), pero se conservan en el fichero.")
    L.append("- **Nombre.** El cuadrante G↓ I↓ pasa de `slowdown` (\"desaceleración / recesión\") a `low_growth_disinfl` "
             "(\"crecimiento bajo / desinflación\"), columna `p_low_growth_disinfl`. Alias en `meta.json` (`aliases_v0_1`). "
             "La recesión es solo la capa `usrec`.")
    L.append("- `tendencia_truncada` sigue la ficha (primeros y últimos 60 meses); W875RX1 (1959) y CMRMTSPL (1967) también "
             "tienen la ventana truncada en sus primeros 5 años.\n")

    fails = [(r, r2) for r, r2 in zip(res["rows"], res["rows_nf"]) if not r[3]]
    L.append("## 9. Comprobaciones que fallan\n")
    if not fails:
        L.append("Ninguna.\n")
    for (name, exp, got, _), _ in fails:
        L.append(f"- **{name}** (esperado {exp}; obtenido {got}).")
    L.append("")
    first_prov = df.index[df["provisional"]].min()
    L.append("## 10. Propuestas (para que decida el usuario; no aplicadas)\n")
    L.append(f"1. **Periodo bloqueado.** Con {meta['params']['provisional_months']} meses provisionales, la etiqueta solo "
             f"puntúa hasta {first_prov - pd.DateOffset(months=1):%Y-%m}. Un periodo bloqueado 2016-2026 tendría hoy "
             f"~{(first_prov.year - 2016) * 12 + first_prov.month - 1} meses puntuables (incluido 2020). Valorar adelantar "
             "su inicio o aceptar que madura con el tiempo.")
    L.append("2. **Estudio de revisión.** La variante ALFRED solo revisa INDPRO y PAYEMS (cota inferior). Repetirlo al "
             "añadir vintages de PCE (desde 2000) y de W875RX1/CMRMTSPL, sin cambiar la v1.0 salvo nueva versión.\n")
    return "\n".join(L)


def main() -> None:
    df, meta = load()
    res = compute(df, meta)
    v = meta["version"]
    png = DOCS / f"label_v{v}.png"
    plot(df, meta, png)
    md = report(df, meta, res, png.name)
    out = DOCS / f"label_v{v}_checks.md"
    out.write_text(md)
    for (name, exp, got, ok), (_, _, got2, ok2) in zip(res["rows"], res["rows_nf"]):
        print(("OK  " if ok else "FAIL"), name, "|", got, "| sin frontera:", got2, "OK" if ok2 else "FAIL")
    print("acierto", res["acc"])
    print("cfnai", res["cfnai"])
    if res["compare"]:
        c = res["compare"]
        print("cambios", c["changed"], c["n"], c["lag_G"], c["lag_I"])
    print("→", out, "\n→", png)


if __name__ == "__main__":
    main()
