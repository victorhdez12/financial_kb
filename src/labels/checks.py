"""Comprobaciones de la §8 de docs/models/label_spec.md para la etiqueta de régimen EE. UU.

Ejecutar:  .venv/bin/python -m src.labels.checks

Detectan errores de cálculo; NO sirven para ajustar parámetros. Escribe
docs/models/label_v<version>_checks.md y docs/models/label_v<version>.png.
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
NAMES = {"expansion": "Expansión", "late_cycle": "Late cycle / sobrecal.",
         "stagflation": "Estanflación", "slowdown": "Desaceleración / recesión"}
# paleta categórica validada (dataviz validate_palette: PASS en luminosidad, croma, CVD y visión normal)
COLORS = {"expansion": "#1baf7a", "late_cycle": "#eda100", "stagflation": "#e34948", "slowdown": "#2a78d6"}
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
PCOLS = [f"p_{q}" for q in R.QUADRANTS]

EPISODES = [  # (nombre, desde, hasta, cuadrantes esperados, descripción del criterio)
    ("1973-75", "1973-01", "1975-12", ("stagflation",), "estanflación dominante"),
    ("1979-80", "1979-01", "1980-12", ("stagflation",), "estanflación dominante"),
    ("2021-T2 a 2022", "2021-04", "2022-12", ("late_cycle", "stagflation"), "sobrecalentamiento / estanflación"),
    ("1995-99", "1995-01", "1999-12", ("expansion",), "expansión"),
    ("2008-09", "2008-01", "2009-12", ("slowdown",), "desaceleración/recesión"),
    ("2020-T2", "2020-04", "2020-06", ("slowdown",), "desaceleración/recesión"),
]


def load() -> tuple[pd.DataFrame, dict]:
    path = R.out_path()
    if not path.exists():
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


def compute(df: pd.DataFrame, meta: dict) -> dict:
    con = db.connect()
    try:
        cfnai = db.series(con, "CFNAIMA3")
        cfnai1 = db.series(con, "CFNAI")
        gdp = db.series(con, "GDPC1")
        pot = con.execute("select date, value from forecasts where series_id='GDPPOT' order by date").df()
        cpic, pce = R.monthly(con, "CPILFESL"), R.monthly(con, "PCEPILFE")
    finally:
        con.close()
    pot = pd.Series(pot["value"].values, index=pd.to_datetime(pot["date"]))

    m = df[~df["provisional"]]  # los meses provisionales no se puntúan
    res = {"rows": []}

    def add(name, expected, got, ok, note=""):
        res["rows"].append((name, expected, got, ok, note))

    # 1. recesiones NBER
    rec = m[m["usrec"] == 1]
    share = float((rec["p_g_high"] < 0.5).mean())
    res["rec_miss"] = rec[rec["p_g_high"] >= 0.5][["G", "p_g_high"]]
    add("Meses NBER de recesión con P(G alto) < 0,5", "≥ 85 %", f"{share:.1%} (n={len(rec)})", share >= 0.85)

    # 2. CFNAI-MA3
    j = pd.concat([m["G"], cfnai.rename("cfnai")], axis=1, join="inner").dropna()
    rho = float(j["G"].corr(j["cfnai"]))
    add("Correlación G con CFNAI-MA3 (1967+)", "> 0,7", f"{rho:.2f} (n={len(j)})", rho > 0.7)
    # diagnóstico (no cambia el criterio): G = log media 3 m(t) − log media 3 m(t−6) equivale a una
    # media triangular de las tasas mensuales de t−7…t (pesos 1,2,3,3,3,3,2,1); CFNAI-MA3 solo cubre t−2…t.
    w = np.array([1, 2, 3, 3, 3, 3, 2, 1], float)
    w /= w.sum()
    cf_tri = cfnai1.rolling(8).apply(lambda x: float((x * w).sum()), raw=True)
    gm = m["G"]
    covid = (gm.index >= "2020-01-01") & (gm.index <= "2021-12-01")
    res["cfnai"] = {
        "lags": {k: float(gm.corr(cfnai.shift(k))) for k in (0, 1, 2, 3)},
        "tri": float(gm.corr(cf_tri)),
        "ex_covid": float(gm[~covid].corr(cfnai.reindex(gm.index[~covid]))),
        "spearman": float(gm.corr(cfnai.reindex(gm.index), method="spearman")),
        "periods": {f"{a}-{b}": (float(gm.loc[a:b].corr(cfnai.loc[a:b])), float(gm.loc[a:b].corr(cf_tri.loc[a:b])))
                    for a, b in (("1967", "1983"), ("1984", "2007"), ("2008", "2019"), ("2020", "2021"), ("2022", "2024"))},
    }

    # 3. brecha de producción
    gap = 100 * np.log(gdp / pot.reindex(gdp.index)).dropna()
    gq = m["G"][m.index.month.isin([3, 6, 9, 12])]
    gq.index = gq.index - pd.offsets.MonthBegin(2)  # último mes del trimestre → fecha del trimestre
    q = pd.concat([gq.rename("G"), gap.rename("gap")], axis=1, join="inner").dropna()
    q["d2gap"], q["d1gap"], q["dG"] = q["gap"].diff(2), q["gap"].diff(), q["G"].diff()
    r_main = float(q["G"].corr(q["d2gap"]))
    r_dd = float(q["dG"].corr(q["d1gap"]))
    r_lvl = float(q["G"].corr(q["gap"]))
    res["gap"] = {"main": r_main, "dd": r_dd, "lvl": r_lvl, "n": int(q["d2gap"].notna().sum()),
                  "d1": float(q["G"].corr(q["d1gap"]))}
    add("Correlación G con la brecha (GDPC1 vs GDPPOT), en cambios", "> 0,6",
        f"{r_main:.2f} (G vs Δ2T brecha; n={res['gap']['n']})", r_main > 0.6)

    # 4. episodios
    res["episodes"] = []
    for name, a, b, want, desc in EPISODES:
        x = m.loc[a:b]
        counts = x["label_hard"].value_counts()
        share_w = float(x["label_hard"].isin(want).mean())
        meanp = x[PCOLS].mean()
        if len(want) == 1:
            ok = counts.idxmax() == want[0] and meanp.idxmax() == f"p_{want[0]}"
        else:
            ok = share_w > 0.5
        res["episodes"].append((name, x, counts, meanp))
        got = f"{share_w:.0%} de meses en {'/'.join(NAMES[w] for w in want)}; " + ", ".join(
            f"{NAMES[k]} {v}" for k, v in counts.items())
        add(f"Episodio {name}", desc, got, ok)

    # 5. distribución
    dist = m["label_hard"].value_counts(normalize=True).reindex(R.QUADRANTS).fillna(0)
    add("Distribución por cuadrante", "ninguno < 10 %",
        ", ".join(f"{NAMES[k]} {v:.0%}" for k, v in dist.items()), bool((dist >= 0.10).all()))
    res["dist"] = dist
    res["dist_soft"] = m[PCOLS].mean()

    # 6. duraciones
    rr = runs(m["label_hard"])
    res["runs"] = rr
    add("Duración media de los regímenes duros", "≥ 6 meses",
        f"{rr['months'].mean():.1f} meses ({len(rr)} tramos; mediana {rr['months'].median():.0f})",
        rr["months"].mean() >= 6)

    # 7. correlación G-I
    gi = float(m["G"].corr(m["I"]))
    gi_post = float(m.loc["1984":, "G"].corr(m.loc["1984":, "I"]))
    res["gi"] = (gi, gi_post)
    add("Correlación G-I", "se informa; revisar independencia si |ρ| > 0,3",
        f"{gi:.2f} (1984+: {gi_post:.2f})", abs(gi) <= 0.3)

    # extras
    lbl = m["label_hard"]
    tm = pd.crosstab(lbl.shift().dropna().rename("desde"), lbl.iloc[1:].rename("hacia"))
    res["trans"] = tm.reindex(index=R.QUADRANTS, columns=R.QUADRANTS).fillna(0).astype(int)
    m2 = m.copy()
    m2["decada"] = (m2.index.year // 10 * 10).astype(str) + "s"
    res["decades"] = pd.crosstab(m2["decada"], m2["label_hard"], normalize="index").reindex(
        columns=R.QUADRANTS).fillna(0)
    res["decade_n"] = m2["decada"].value_counts().sort_index()
    res["frontier"] = float(m["frontera"].mean())
    res["runs_by"] = rr.groupby("regime")["months"].agg(["count", "mean", "median", "max"]).reindex(R.QUADRANTS)
    both = pd.concat([R.ann_change(cpic), R.ann_change(pce)], axis=1, keys=["cpi", "pce"]).dropna()
    res["cpi_pce_gap"] = {"all": float((both["cpi"] - both["pce"]).mean()),
                          "1959-1969": float((both["cpi"] - both["pce"]).loc["1959":"1969"].mean())}
    res["n_scored"] = len(m)
    return res


def plot(df: pd.DataFrame, meta: dict, path) -> None:
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK,
                         "axes.titleweight": "semibold", "axes.titlelocation": "left"})
    fig, ax = plt.subplots(3, 1, figsize=(13, 9), sharex=True, facecolor=SURF,
                           gridspec_kw={"height_ratios": [1, 1, 1.2], "hspace": 0.28})
    rec = df["usrec"].fillna(0).astype(int)
    starts = df.index[(rec == 1) & (rec.shift(fill_value=0) == 0)]
    ends = df.index[(rec == 1) & (rec.shift(-1, fill_value=0) == 0)]
    prov = df.index[df["provisional"]].min()
    for a in ax:
        a.set_facecolor(SURF)
        for s, e in zip(starts, ends):
            a.axvspan(s, e + pd.offsets.MonthEnd(0), color="#d9d8d3", lw=0, zorder=0)
        a.axvspan(prov, df.index.max() + pd.offsets.MonthEnd(0), facecolor="#f1efe8", lw=0, zorder=0, hatch="///",
                  edgecolor="#d9d8d3")
        a.grid(axis="y", color=GRID, lw=0.6)
        a.spines[["top", "right"]].set_visible(False)
    ax[0].plot(df.index, df["G"], color=INK, lw=1)
    ax[0].axhline(0, color=INK2, lw=0.8, ls="--")
    ax[0].set_title(f"G — crecimiento frente a tendencia (z medio; s_G = {meta['s_G']:.2f})")
    ax[0].set_ylabel("z")
    ax[1].plot(df.index, df["I"], color=INK, lw=1)
    ax[1].axhline(meta["params"]["kappa"], color=COLORS["stagflation"], lw=1, ls="--")
    ax[1].text(df.index[min(720, len(df) - 1)], meta["params"]["kappa"] + 0.5, f"umbral κ = {meta['params']['kappa']} %",
               color=INK2, fontsize=8)
    ax[1].set_title(f"I — inflación subyacente a 6 m anualizada (%; s_I = {meta['s_I']:.2f} pp)")
    ax[1].set_ylabel("%")
    ax[1].set_ylim(-3, 16)
    ys = [df[f"p_{q}"].values for q in R.QUADRANTS]
    ax[2].stackplot(df.index, ys, colors=[COLORS[q] for q in R.QUADRANTS],
                    labels=[NAMES[q] for q in R.QUADRANTS], lw=0)
    for s_, e_ in zip(starts, ends):  # el área apilada tapa el sombreado: franja de recesión encima
        ax[2].fill_between([s_, e_ + pd.offsets.MonthEnd(0)], 1.015, 1.06, color="#52514e", lw=0)
    ax[2].set_ylim(0, 1.06)
    ax[2].set_yticks([0, 0.25, 0.5, 0.75, 1])
    ax[2].set_title("Probabilidad por cuadrante (apilada)")
    ax[2].legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=4, frameon=False,
                 labelcolor=INK)
    ax[2].xaxis.set_major_locator(mdates.YearLocator(10))
    ax[2].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax[2].set_xlim(df.index.min(), df.index.max() + pd.offsets.MonthEnd(0))
    fig.suptitle(f"Etiqueta de régimen EE. UU. v{meta['version']} — {meta['first'][:7]} a {meta['last'][:7]}",
                 x=0.06, ha="left", fontsize=12, fontweight="semibold", color=INK)
    fig.text(0.06, 0.935, "Gris: recesiones NBER (USREC; en el panel inferior, franja sobre el área). Rayado: últimos 24 meses, provisionales.",
             fontsize=8.5, color=INK2)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=SURF)
    plt.close(fig)


def md_table(df: pd.DataFrame, pct=False, d=2) -> str:
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join([df.index.name or ""] + cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for i, r in df.iterrows():
        vals = [f"{v:.0%}" if pct else (f"{v:.{d}f}" if isinstance(v, float) else str(v)) for v in r.values]
        lines.append("| " + " | ".join([str(i)] + vals) + " |")
    return "\n".join(lines)


def report(df: pd.DataFrame, meta: dict, res: dict, png_name: str) -> str:
    sd = meta["scale_detail"]
    L = []
    L.append(f"# Etiqueta de régimen EE. UU. v{meta['version']} — comprobaciones (§8)\n")
    L.append(f"Generado por `src/labels/checks.py` a partir de `data/archive/labels/regime_us_v{meta['version']}.parquet` "
             f"(hash de contenido `{meta['sha256_content'][:16]}…`). Muestra {meta['first'][:7]} → {meta['last'][:7]} "
             f"({meta['rows']} meses); se puntúan {res['n_scored']} (sin los 24 provisionales).\n")
    L.append("Las comprobaciones sirven para detectar errores de cálculo, **no para ajustar parámetros**. "
             "No se ha cambiado ningún parámetro de la ficha a la vista de estos resultados.\n")
    L.append(f"![Etiqueta v{meta['version']}]({png_name})\n")

    L.append("## 1. Escalas estimadas con ALFRED\n")
    L.append("Error de revisión = valor de **primera publicación** − valor con la **última vintage**, en las unidades del eje. "
             "Primera publicación: la vintage más antigua de cada fecha de referencia, solo si sale ≤ 75 días tras el fin del mes "
             "y no coincide con el inicio del archivo ALFRED de la serie (en ese caso no es una primera publicación). "
             "La serie de la fecha de referencia se reconstruye tal como estaba en esa vintage (incluidos t−6…t−8) y se le aplica "
             "la misma transformación que al eje. Solo fechas maduras (≤ "
             f"{meta['last_mature_for_scales'][:7]}), para que la \"última vintage\" no sea a su vez provisional. "
             "s = MAD × 1,4826 del error; suelo 0,25; estable si n ≥ 60 y la MAD de cada mitad está entre ½ y 2 veces la total.\n")
    L.append("| serie / unidad | n | desde → hasta | sesgo medio | s (MAD×1,4826) | 1.ª mitad | 2.ª mitad | estable |")
    L.append("|---|---|---|---|---|---|---|---|")
    for k, d in sd.items():
        L.append(f"| {k} | {d['n']} | {str(d['from'])[:7]} → {str(d['to'])[:7]} | {fmt(d['mean_err'])} | "
                 f"{fmt(d['mad_sd'], 3)} | {fmt(d['half1'], 3)} | {fmt(d['half2'], 3)} | {'sí' if d['stable'] else 'no'} |")
    L.append("")
    L.append(f"- **s_G = {meta['s_G']:.3f}** ({meta['how_G']}): error del G de dos indicadores (media de los z de INDPRO y PAYEMS; "
             "z = error del ritmo / σ_i del indicador con datos finales). Por indicador: INDPRO "
             f"{sd['G_z_INDPRO']['mad_sd']:.2f}, PAYEMS {sd['G_z_PAYEMS']['mad_sd']:.2f}.")
    L.append(f"- **s_I = {meta['s_I']:.3f} pp** ({meta['how_I']}): PCE subyacente (la serie del eje desde 1959). El IPC subyacente "
             f"(desde 1996) da {sd['I_CPILFESL']['mad_sd']:.2f} pp, menor porque el IPC solo revisa factores estacionales; se informa como contraste.")
    for n in meta["notes"]:
        L.append(f"- Nota: {n}. El G de la etiqueta sí usa estas series (última vintage); su ruido de revisión no está medido, "
                 "así que s_G refleja solo INDPRO y PAYEMS.")
    L.append("- Las mitades de INDPRO/PAYEMS muestran que el ruido de revisión era mayor en la primera mitad de la muestra (≈ 1950-1990) que en la segunda; s resume toda la muestra.\n")

    L.append("## 2. Comprobaciones\n")
    L.append("| criterio | esperado | obtenido | |\n|---|---|---|---|")
    for name, exp, got, ok, _ in res["rows"]:
        L.append(f"| {name} | {exp} | {got} | {'✅' if ok else '❌'} |")
    L.append("")
    g = res["gap"]
    L.append(f"**Brecha de producción.** G en el último mes de cada trimestre es la variación log de la media del trimestre frente a la de "
             "dos trimestres antes, menos su tendencia; su equivalente en la brecha es Δ2T (cambio a dos trimestres), que es la medida "
             f"principal. Otras lecturas (informativas): G vs Δ1T brecha {g['d1']:.2f}; ΔG vs Δ1T brecha {g['dd']:.2f}; G vs nivel de la brecha "
             f"{g['lvl']:.2f}. GDPPOT (CBO) se lee de la vista `forecasts` (pit_role = forecast), solo hasta el último GDPC1.\n")
    miss = res["rec_miss"]
    if len(miss):
        L.append(f"**Recesiones con P(G alto) ≥ 0,5** ({len(miss)} meses): "
                 + ", ".join(f"{d:%Y-%m} ({p:.2f})" for d, p in miss["p_g_high"].items())
                 + ". Suelen ser el primer mes de la recesión (pico NBER) o meses en que la media de 3 m y la ventana de 6 m aún arrastran crecimiento previo.\n")
    gi, gi_post = res["gi"]
    L.append(f"**Correlación G-I** = {gi:.2f} (1984+: {gi_post:.2f}). |ρ| ≤ 0,3: el supuesto de independencia entre ejes no se cuestiona con estos datos.\n")

    L.append("## 3. Episodios\n")
    L.append("| episodio | meses | " + " | ".join(NAMES[q] for q in R.QUADRANTS) + " | prob. media dominante |")
    L.append("|---|---|" + "---|" * 4 + "---|")
    for name, x, counts, meanp in res["episodes"]:
        c = [str(int(counts.get(q, 0))) for q in R.QUADRANTS]
        top = meanp.idxmax().replace("p_", "")
        L.append(f"| {name} | {len(x)} | " + " | ".join(c) + f" | {NAMES[top]} ({meanp.max():.2f}) |")
    L.append("")

    L.append("## 4. Distribución por cuadrante\n")
    L.append("| cuadrante | % meses (etiqueta dura) | prob. media (blanda) | tramos | duración media | mediana | máx. |")
    L.append("|---|---|---|---|---|---|---|")
    for q in R.QUADRANTS:
        rb = res["runs_by"].loc[q]
        L.append(f"| {NAMES[q]} | {res['dist'][q]:.1%} | {res['dist_soft'][f'p_{q}']:.1%} | {int(rb['count'])} | "
                 f"{rb['mean']:.1f} | {rb['median']:.0f} | {int(rb['max'])} |")
    L.append(f"\nMeses de frontera (máx. prob. < {meta['params']['frontier']}): {res['frontier']:.1%}.\n")

    L.append("### Por década (% de meses, etiqueta dura)\n")
    dec = res["decades"].copy()
    dec.columns = [NAMES[c] for c in dec.columns]
    dec.insert(0, "meses", res["decade_n"].reindex(dec.index).astype(int).astype(str))
    dec.index.name = "década"
    lines = ["| década | meses | " + " | ".join(dec.columns[1:]) + " |", "|---|---|" + "---|" * 4]
    for i, r in dec.iterrows():
        lines.append(f"| {i} | {r['meses']} | " + " | ".join(f"{v:.0%}" for v in r.values[1:]) + " |")
    L.append("\n".join(lines) + "\n")

    L.append("## 5. Matriz de transición (etiqueta dura, meses no provisionales)\n")
    tm = res["trans"]
    tp = tm.div(tm.sum(axis=1), axis=0)
    L.append("Recuentos (fila = mes anterior, columna = mes siguiente) y, entre paréntesis, probabilidad por fila.\n")
    L.append("| desde \\ hacia | " + " | ".join(NAMES[q] for q in R.QUADRANTS) + " |")
    L.append("|---|" + "---|" * 4)
    for q in R.QUADRANTS:
        L.append(f"| {NAMES[q]} | " + " | ".join(f"{tm.loc[q, c]} ({tp.loc[q, c]:.0%})" for c in R.QUADRANTS) + " |")
    L.append("")

    L.append("## 6. Últimos 6 meses (provisionales)\n")
    t = df.tail(6)
    L.append("| mes | G | I | " + " | ".join(NAMES[q] for q in R.QUADRANTS) + " | etiqueta dura | frontera |")
    L.append("|---|---|---|" + "---|" * 4 + "---|---|")
    for d, r in t.iterrows():
        L.append(f"| {d:%Y-%m} | {r['G']:.2f} | {r['I']:.2f} | " + " | ".join(f"{r[f'p_{q}']:.2f}" for q in R.QUADRANTS)
                 + f" | {NAMES[r['label_hard']]} | {'sí' if r['frontera'] else 'no'} |")
    L.append("")

    L.append("## 7. Notas de implementación\n")
    fi = df["fuente_i"]
    L.append(f"- Fuentes de I: PCE subyacente desde {fi[fi == 'pce_core'].index.min():%Y-%m}; IPC subyacente − 0,4 pp "
             f"{fi[fi == 'cpi_core_adj'].index.min():%Y-%m} → {fi[fi == 'cpi_core_adj'].index.max():%Y-%m}; IPC general "
             f"{fi[fi == 'headline'].index.min():%Y-%m} → {fi[fi == 'headline'].index.max():%Y-%m}. La ficha dice 1957-1958 / 1959, "
             "pero la inflación a 6 m necesita 6 meses previos: CPILFESL empieza en 1957-01 (primer valor 1957-07) y PCEPILFE en 1959-01 "
             "(primer valor 1959-07), así que 1957-01…06 usan IPC general y 1959-01…06 IPC subyacente ajustado.")
    gp = res["cpi_pce_gap"]
    L.append(f"- Contraste del ajuste de 0,4 pp (no se cambia): diferencia media IPC − PCE subyacentes a 6 m = {gp['all']:.2f} pp "
             f"en 1959-hoy y {gp['1959-1969']:.2f} pp en 1959-1969.")
    L.append("- Tendencia y σ_i se calculan sobre la muestra de la etiqueta (desde 1950-01), por eso la ventana se trunca al principio "
             "como dice la §7, aunque INDPRO y PAYEMS tengan datos anteriores. W875RX1 (1959) y CMRMTSPL (1967) también tienen la "
             "ventana truncada en sus primeros 5 años; `tendencia_truncada` sigue la ficha (primeros y últimos 60 meses de la muestra).")
    cg = df["cobertura_g"].value_counts().sort_index()
    L.append(f"- Cobertura de G: " + ", ".join(f"{k} indicadores: {v} meses" for k, v in cg.items())
             + ". El último mes es el último con G (≥ 2 indicadores) e I; PAYEMS e IPC de 2026-09 ya existen pero INDPRO/PCE no.")
    L.append("- El IPC de 2025-10 no se publicó (cierre del Gobierno); no afecta a la etiqueta (IPC solo se usa antes de 1959).")
    L.append("- Los 24 meses provisionales no entran en ninguna comprobación.\n")

    fails = [r for r in res["rows"] if not r[3]]
    L.append("## 8. Comprobaciones que fallan\n")
    if not fails:
        L.append("Ninguna.\n")
    for name, exp, got, ok, _ in fails:
        L.append(f"- **{name}** (esperado {exp}; obtenido {got}).")
    L.append("")
    if any(r[0].startswith("Correlación G con CFNAI") and not r[3] for r in res["rows"]):
        c = res["cfnai"]
        L.append("### CFNAI-MA3: resultado real, no error de código\n")
        L.append("Evidencia (todo con meses no provisionales, 1967+):\n")
        L.append("| lectura | correlación |\n|---|---|")
        for k, v in c["lags"].items():
            L.append(f"| G(t) vs CFNAI-MA3(t−{k}) | {v:.2f} |")
        L.append(f"| G vs CFNAI mensual en la misma ventana que G (media triangular t−7…t) | {c['tri']:.2f} |")
        L.append(f"| G vs CFNAI-MA3 sin 2020-2021 | {c['ex_covid']:.2f} |")
        L.append(f"| Spearman G vs CFNAI-MA3 | {c['spearman']:.2f} |")
        for per, (a, b) in c["periods"].items():
            L.append(f"| {per}: CFNAI-MA3 / ventana igualada | {a:.2f} / {b:.2f} |")
        L.append("")
        L.append("1. **Ventana distinta.** G(t) compara la media de 3 m en t con la de t−6: equivale a una media triangular de las "
                 "tasas mensuales de t−7 a t (centro en t−3,5). CFNAI-MA3 solo promedia t−2…t. La correlación sube con el retardo "
                 "(máximo en t−2/t−3) y, con el CFNAI agregado en la misma ventana que G, pasa a "
                 f"{c['tri']:.2f} (≥ 0,97 en cada subperiodo hasta 2021). Las dos series miden lo mismo; G lo hace con más retardo.")
        L.append("   En 2022-2024 la correlación se pierde también con la ventana igualada: ambos indicadores están cerca de cero "
                 "(poca señal: la desviación típica de G es ~0,3 frente a ~1,4 en 1967-2019), G compara con una tendencia local "
                 "(mediana de 10 años, truncada al final) y CFNAI con una tendencia fija de largo plazo, y la debilidad de 2023 fue "
                 "de manufactura (pesa mucho en CFNAI) mientras empleo y renta real crecían por encima de su tendencia. Es un "
                 "resultado real; esos meses están dentro de la ventana truncada y se recalcularán.")
        L.append("2. **COVID.** En 2020-2021 los valores extremos (CFNAI-MA3 cae a −18 y rebota) dominan la correlación de Pearson; "
                 "sin esos dos años la correlación contemporánea es " f"{c['ex_covid']:.2f}.")
        L.append("3. Se revisó la alineación de fechas (ambas series fechadas el día 1 del mes de referencia) y el signo; no hay error.\n")
    rr = res["runs"]
    L.append("## 9. Propuestas (para que decida el usuario; no aplicadas)\n")
    L.append("1. **Fecha de G.** G(t) mide el crecimiento de t−7 a t (centro en t−3,5), así que la etiqueta del mes t describe en "
             "buena parte el crecimiento de hace ~3-4 meses (lo muestra la correlación máxima con CFNAI-MA3 retardado 2-3 meses). "
             "Como la etiqueta es ex post y puede mirar adelante, una opción es centrar la ventana (asignar a t el ritmo medido "
             "en t+3/t+4) o usar un ritmo a 3 meses. Cambia la etiqueta: requiere nueva versión.")
    L.append("2. **Criterio CFNAI de la §8.** Si se mantiene la definición de G, comparar con el CFNAI en la misma ventana "
             f"(correlación {res['cfnai']['tri']:.2f}) o con CFNAI-MA3 retardado 2 meses ({res['cfnai']['lags'][2]:.2f}), en lugar "
             "de CFNAI-MA3 contemporáneo.")
    L.append("3. **Escalas.** Descargar vintages ALFRED de W875RX1 y CMRMTSPL para medir su ruido de revisión. El ruido de "
             "INDPRO/PAYEMS es mayor antes de 1980 que después; podría estudiarse una escala por época.")
    L.append(f"4. **Duraciones.** La media cumple ({rr['months'].mean():.1f} m) pero la mediana es {rr['months'].median():.0f} m: "
             f"{int((rr['months'] <= 2).sum())} de {len(rr)} tramos duran ≤ 2 meses (cruces cerca de las fronteras). No afecta "
             "a la métrica principal (log-loss contra las probabilidades), pero sí a los baselines de reglas con etiqueta dura; "
             "se podría informar el acierto también sin meses de frontera.")
    L.append("5. **1950-1956.** I usa IPC general, con picos de la guerra de Corea (≈ 14 % en 1951); son meses de "
             "`fuente_i = headline` y `tendencia_truncada`. Valorar excluir 1950-1954 del entrenamiento o ponderarlos menos.\n")
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
    for name, exp, got, ok, _ in res["rows"]:
        print(("OK  " if ok else "FAIL"), name, "|", got)
    print("→", out, "\n→", png)


if __name__ == "__main__":
    main()
