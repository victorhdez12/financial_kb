"""Gráficos del informe de resultados de la Fase 3 (Reportero).

Lee solo ficheros de resultados y el warehouse (en modo lectura) y escribe:
- PNG en ``obsidian/Reports/Fase 3/img/``
- ``obsidian/Reports/Fase 3/img/cifras.json`` con las cifras derivadas que cita el informe.

Uso: ``.venv/bin/python -m src.report.fase3.make_figures``
No modifica datos ni código de producción.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
VERSION = "1.1"  # etiqueta congelada que usa el informe (tag label-v1.1)
LABELS = ROOT / "data" / "archive" / "labels"
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
OUT = ROOT / "obsidian" / "Reports" / "Fase 3" / "img"

Q = ["expansion", "late_cycle", "stagflation", "low_growth_disinfl"]
QNAME = {
    "expansion": "Expansión",
    "late_cycle": "Crecimiento con inflación alta",  # id late_cycle (v1.1); puede ser recuperación temprana o sobrecalentamiento
    "stagflation": "Estanflación",
    "low_growth_disinfl": "Crecimiento bajo / desinflación",
}
QSHORT = {"expansion": "Expansión", "late_cycle": "Crec. con infl. alta", "stagflation": "Estanflación",
          "low_growth_disinfl": "Crec. bajo / desinfl."}
QCOL = {"expansion": "#1a9e77", "late_cycle": "#e6a000", "stagflation": "#d64545",
        "low_growth_disinfl": "#2b6fd1"}
PCOL = {q: f"p_{q}" for q in Q}
REC = "#dcdcdc"
INK = "#222222"
MUTED = "#666666"
# Correspondencia aproximada de cuadrantes del clasificador de reglas (src/regime) con la etiqueta
RULES_MAP = {"Goldilocks": "expansion", "Reflación": "late_cycle", "Estanflación": "stagflation",
             "Deflación/recesión": "low_growth_disinfl"}

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "font.size": 10, "axes.titlesize": 12.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#999999",
    "axes.labelcolor": INK, "xtick.color": "#444444", "ytick.color": "#444444",
    "axes.grid": True, "grid.color": "#ececec", "grid.linewidth": 0.8, "legend.frameon": False,
})


def footer(fig, text):
    fig.text(0.01, -0.01, "Fuente: " + text, fontsize=7.5, color=MUTED, ha="left", va="top", wrap=True)


def save(fig, name):
    fig.savefig(OUT / name, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("escrito", OUT / name)


def rec_spans(df):
    """Tramos contiguos con usrec == 1 → lista de (inicio, fin_exclusivo)."""
    r = df.set_index("date")["usrec"].fillna(0).astype(int)
    spans, start = [], None
    for d, v in r.items():
        if v == 1 and start is None:
            start = d
        if v == 0 and start is not None:
            spans.append((start, d))
            start = None
    if start is not None:
        spans.append((start, r.index[-1] + pd.offsets.MonthBegin(1)))
    return spans


def runs(labels: pd.Series):
    out, cur, n = [], None, 0
    for v in labels:
        if v == cur:
            n += 1
        else:
            if cur is not None:
                out.append((cur, n))
            cur, n = v, 1
    out.append((cur, n))
    return out


# ---------------------------------------------------------------- datos
def load():
    lab = pd.read_parquet(LABELS / f"regime_us_v{VERSION}.parquet")
    meta = json.loads((LABELS / f"regime_us_v{VERSION}.meta.json").read_text())
    rev = json.loads((LABELS / "revision_study.json").read_text())
    v01 = pd.read_parquet(LABELS / "regime_us_v0.1.parquet")
    v02 = pd.read_parquet(LABELS / "regime_us_v0.2.parquet")
    v10 = pd.read_parquet(LABELS / "regime_us_v1.0.parquet")
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    cat = con.sql("select c.series_id, c.source, c.category, c.country_iso3, c.pit_role, "
                  "s.first_date, s.last_date, s.n_obs from catalog c "
                  "left join series_summary s using (series_id)").df()
    rules = con.sql("select date, quadrant, vintage_mode from regime_monthly order by date").df()
    cfma3 = con.sql("select date, value from obs_latest where series_id = 'CFNAIMA3' order by date").df()
    con.close()
    return lab, meta, rev, v01, v02, v10, cat, rules, cfma3


BLOCKS = {
    "Crecimiento, empleo y vivienda": ["growth", "employment", "housing"],
    "Inflación y materias primas": ["inflation", "commodities", "gold"],
    "Tipos y crédito": ["rates", "credit", "bond_returns", "financial_conditions", "crisis"],
    "Dinero y liquidez": ["money", "liquidity"],
    "Mercados (bolsa, divisas, valoración)": ["equity_returns", "markets", "valuation", "fx"],
    "Fiscal, geopolítica y otros": ["fiscal", "geopolitics", None],
}
BCOL = ["#33507a", "#9a6fb0", "#4aa3a2", "#c27c3a", "#6b8e23", "#a8a8a8"]


def block_of(cat):
    for b, cats in BLOCKS.items():
        if cat in cats:
            return b
    return "Fiscal, geopolítica y otros"


# ---------------------------------------------------------------- 1 cobertura
def fig_cobertura(cat, cifras):
    c = cat.dropna(subset=["first_date", "last_date"]).copy()
    c["block"] = c["category"].map(block_of)
    c["y0"] = pd.to_datetime(c["first_date"]).dt.year
    c["y1"] = pd.to_datetime(c["last_date"]).dt.year
    years = np.arange(1900, 2027)
    tab = pd.DataFrame({b: [((g.y0 <= y) & (g.y1 >= y)).sum() for y in years]
                        for b, g in c.groupby("block")}, index=years)[list(BLOCKS)]
    tot = tab.sum(axis=1)
    usa = c[c.country_iso3 == "USA"]
    cifras["cobertura"] = {
        "series_catalogo": int(len(cat)),
        "series_con_observaciones": int(len(c)),
        "por_bloque_catalogo": cat["category"].map(block_of).value_counts().to_dict(),
        "series_activas": {str(y): int(tot.loc[y]) for y in (1900, 1950, 1970, 2000, 2026)},
        "series_usa_activas_1950": int(((usa.y0 <= 1950) & (usa.y1 >= 1950)).sum()),
        "series_con_dato_2026": int(tot.loc[2026]),
        "pit_role": cat["pit_role"].value_counts().to_dict(),
    }
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.stackplot(years, [tab[b].values for b in BLOCKS], labels=list(BLOCKS), colors=BCOL,
                 edgecolor="white", linewidth=0.4)
    for y in (1950, 1970, 2000):
        ax.annotate(f"{tot.loc[y]:,}".replace(",", "."), (y, tot.loc[y]), xytext=(0, 8),
                    textcoords="offset points", ha="center", fontsize=8.5, color=INK)
    ax.set_xlim(1900, 2026)
    ax.set_ylabel("nº de series con dato ese año")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", ".")))
    ax.legend(loc="upper left", fontsize=8.5, ncol=2)
    ax.set_title(f"Desde 1950 hay {tot.loc[1950]:,} series con dato; hoy la base reúne "
                 f"{len(cat):,} series de {cat.source.nunique()} fuentes".replace(",", "."))
    footer(fig, "tablas catalog y series_summary de data/warehouse.duckdb (14-oct-2026). Una serie cuenta en un año si "
                "su primer dato es ≤ ese año y el último ≥ ese año. Bloques agrupando la columna category.")
    save(fig, "01_cobertura_por_bloque.png")


# ---------------------------------------------------------------- 2 historia
def shade_rec(ax, spans, **kw):
    for a, b in spans:
        ax.axvspan(a, b, color=REC, lw=0, zorder=0, **kw)


def fig_historia(lab, cifras):
    d = lab.set_index("date")
    spans = rec_spans(lab)
    sc = lab[(lab.weight == 1) & (~lab.provisional)]
    recm = sc[sc.usrec == 1]
    share_low_g = float((recm.p_g_high < 0.5).mean())
    cifras["recesion"] = {"meses_nber_puntuables": int(len(recm)),
                          "pct_p_g_alto_bajo_0_5": share_low_g,
                          "reparto_cuadrante_en_recesion": recm.label_hard.value_counts().to_dict()}
    fig, (axr, ax) = plt.subplots(2, 1, figsize=(12, 5.8), sharex=True,
                                  gridspec_kw={"height_ratios": [0.09, 1], "hspace": 0.04})
    shade_rec(axr, spans)
    axr.set_yticks([])
    axr.grid(False)
    for s in ("left", "bottom"):
        axr.spines[s].set_visible(False)
    axr.text(lab.date.iloc[0], 0.5, "Recesiones NBER ", ha="right", va="center", fontsize=8, color=MUTED)
    ax.stackplot(d.index, [d[PCOL[q]].values for q in Q], colors=[QCOL[q] for q in Q],
                 labels=[QNAME[q] for q in Q], linewidth=0)
    shade_rec(ax, spans, alpha=0.0)
    for a, b in spans:  # bordes finos de las recesiones sobre el área
        ax.axvline(a, color="white", lw=0.6, alpha=0.8)
    prov0 = lab.loc[lab.provisional, "date"].min()
    w0end = lab.loc[lab.weight == 0, "date"].max()
    for a, b, t in [(lab.date.min(), w0end + pd.offsets.MonthBegin(1), "peso 0\n(1950-54)"),
                    (prov0, lab.date.max() + pd.offsets.MonthBegin(1), "provisional\n(54 meses)")]:
        ax.axvspan(a, b, facecolor="none", hatch="///", edgecolor="white", lw=0, zorder=3)
        ax.text(a + (b - a) / 2, 0.03, t, ha="center", va="bottom", fontsize=7.5, color=INK, zorder=4,
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))
    ann = [("1974-06-01", "Años 70:\nestanflación"), ("1981-01-01", "Volcker\n1979-82"),
           ("1999-01-01", "Expansión\n1995-99"), ("2009-01-01", "2008-09:\ncrisis financiera"),
           ("2020-04-01", "COVID\n2020"), ("2021-08-01", "2021-22: crec.\ncon infl. alta")]
    for i, (dt, t) in enumerate(ann):
        x = pd.Timestamp(dt)
        y = 1.12 if i % 2 == 0 else 1.30
        ax.annotate(t, (x, 1.0), xytext=(x, y), textcoords="data", ha="center", va="bottom",
                    fontsize=8, color=INK, arrowprops=dict(arrowstyle="-", color="#888888", lw=0.7))
    ax.set_ylim(0, 1)
    ax.set_xlim(lab.date.min(), lab.date.max() + pd.offsets.MonthBegin(1))
    ax.set_ylabel("probabilidad de cada cuadrante")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.xaxis.set_major_locator(mdates.YearLocator(10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=4, fontsize=8.5)
    axr.set_title(f"La etiqueta marca crecimiento bajo (P(G alto) < 0,5) en el {share_low_g:.0%} de los "
                  f"{len(recm)} meses de recesión NBER".replace("%", " %"), pad=95)
    footer(fig, "data/archive/labels/regime_us_v1.1.parquet (etiqueta v1.1, 1950-01 → 2026-04); recesiones = columna "
                "usrec (NBER). Meses puntuables: weight = 1 y no provisionales (1955-01 → 2021-10). Rayado: no puntúan.")
    save(fig, "02_historia_cuadrantes.png")


# ---------------------------------------------------------------- 3 mapa G × I
def fig_mapa(lab, cifras):
    s = lab[lab.weight == 1].copy()
    xl, yl = (-4, 4), (-1, 12)
    fig, ax = plt.subplots(figsize=(9.5, 7))
    out = s[(s.G < xl[0]) | (s.G > xl[1]) | (s.I < yl[0]) | (s.I > yl[1])]
    for q in Q:
        g = s[s.label_hard == q]
        mat = g[~g.provisional]
        ax.scatter(mat.G.clip(*xl), mat.I.clip(*yl), s=14, color=QCOL[q], alpha=0.55, lw=0,
                   label=f"{QNAME[q]} ({len(mat)} m)")
        pr = g[g.provisional]
        ax.scatter(pr.G.clip(*xl), pr.I.clip(*yl), s=22, facecolor="white", edgecolor=QCOL[q], lw=1.1)
    ax.scatter([], [], s=22, facecolor="white", edgecolor="#777777", lw=1.1, label="mes provisional (2021-11 →)")
    ax.axvline(0, color=INK, lw=1)
    ax.axhline(2.5, color=INK, lw=1)
    ax.text(xl[1] - 0.1, 2.6, "umbral κ = 2,5 %", ha="right", va="bottom", fontsize=8, color=INK)
    ax.text(0.08, yl[1] - 0.2, "← por debajo de tendencia | por encima →", ha="center", va="top",
            fontsize=8, color=INK)
    corners = [(3.0, 0.0, "Expansión", "expansion"), (3.0, 10.8, "Crec. con\ninfl. alta", "late_cycle"),
               (-3.0, 10.8, "Estanflación", "stagflation"), (-3.0, 0.0, "Crec. bajo /\ndesinflación",
                                                               "low_growth_disinfl")]
    for x, y, t, q in corners:
        ax.text(x, y, t, ha="center", va="center", fontsize=11, fontweight="bold", color=QCOL[q], alpha=0.9)
    eps = [("1974-01", "1975-03", "1974-75"), ("1979-06", "1980-06", "1979-80"),
           ("2008-09", "2009-06", "2008-09"), ("1997-01", "1999-12", "1997-99"),
           ("2021-04", "2021-10", "2021"), ("2025-11", "2026-04", "últimos 6 m\n(provisional)")]
    pos = []
    for a, b, t in eps:
        g = s[(s.date >= a) & (s.date <= b)]
        x, y = float(g.G.clip(*xl).mean()), float(g.I.clip(*yl).mean())
        pos.append({"episodio": t, "G_medio": x, "I_medio": y})
        ax.annotate(t, (x, y), xytext=(14, 10), textcoords="offset points", fontsize=8.5, color=INK,
                    fontweight="bold", arrowprops=dict(arrowstyle="-", color=INK, lw=0.8),
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#bbbbbb", lw=0.6))
        ax.scatter([x], [y], s=46, color=INK, marker="x", zorder=5)
    cifras["mapa"] = {"meses_fuera_de_ejes_recortados": int(len(out)), "episodios": pos}
    ax.set_xlim(*xl)
    ax.set_ylim(*yl)
    ax.set_xlabel("G: crecimiento frente a su tendencia (desviaciones típicas robustas, z)")
    ax.set_ylabel("I: inflación subyacente PCE, ventana centrada de 6 meses (% anualizado)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8)
    ax.set_title("Cada mes es un punto: el cuadrante solo depende de si G > 0 y de si I > 2,5 %")
    footer(fig, f"data/archive/labels/regime_us_v1.1.parquet, meses con weight = 1 (1955-01 → 2026-04). "
                f"{len(out)} meses extremos (1957-58, 1974-75, 1980, 2008-09, 2019-20) se dibujan en el borde. × = media del episodio.")
    save(fig, "03_mapa_G_I.png")


# ---------------------------------------------------------------- 4 reparto y duración
def fig_reparto(lab, cifras):
    sc = lab[(lab.weight == 1) & (~lab.provisional)].reset_index(drop=True)
    share = sc.label_hard.value_counts(normalize=True).reindex(Q)
    r = runs(sc.label_hard)
    rd = pd.DataFrame(r, columns=["q", "n"])
    cifras["reparto"] = {"meses": int(len(sc)), "pct": share.to_dict(),
                         "tramos": int(len(rd)), "duracion_media": float(rd.n.mean()),
                         "duracion_mediana": float(rd.n.median()),
                         "por_cuadrante": {q: {"tramos": int((rd.q == q).sum()),
                                               "media": float(rd[rd.q == q].n.mean()),
                                               "mediana": float(rd[rd.q == q].n.median()),
                                               "max": int(rd[rd.q == q].n.max())} for q in Q},
                         "pct_frontera": float(sc.frontera.mean())}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"width_ratios": [1, 1.25], "wspace": 0.45})
    y = np.arange(len(Q))[::-1]
    a1.barh(y, share.values, color=[QCOL[q] for q in Q], height=0.6)
    for yi, v in zip(y, share.values):
        a1.text(v + 0.005, yi, f"{v:.0%}".replace("%", " %"), va="center", fontsize=9, color=INK)
    a1.set_yticks(y, [QSHORT[q] for q in Q])
    a1.set_xlim(0, 0.38)
    a1.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    a1.axvline(0.10, color=MUTED, lw=0.8, ls="--")
    a1.text(0.102, y[-1] - 0.45, "mínimo exigido 10 %", fontsize=7.5, color=MUTED)
    a1.set_xlabel("% de los meses puntuables (etiqueta dura)")
    a1.set_title("Ningún cuadrante domina: todos entre 23 % y 30 %", fontsize=11)
    rng = np.random.default_rng(0)
    for yi, q in zip(y, Q):
        n = rd[rd.q == q].n.values
        a2.scatter(n, yi + rng.uniform(-0.18, 0.18, len(n)), s=18, color=QCOL[q], alpha=0.75, lw=0)
        a2.plot([np.median(n)] * 2, [yi - 0.3, yi + 0.3], color=INK, lw=2)
        a2.text(n.max() + 1, yi, f"media {n.mean():.1f} · mediana {np.median(n):.0f}".replace(".", ","),
                va="center", fontsize=8, color=INK)
    a2.set_yticks(y, [QSHORT[q] for q in Q])
    a2.set_xlim(0, 75)
    a2.set_xlabel("duración de cada tramo (meses seguidos en el mismo cuadrante)")
    a2.set_title(f"Un régimen dura de media {rd.n.mean():.1f} meses; la mitad, ≤ {rd.n.median():.0f}".replace(".", ","),
                 fontsize=11)
    footer(fig, f"data/archive/labels/regime_us_v1.1.parquet, {len(sc)} meses puntuables (1955-01 → 2021-10), "
                f"{len(rd)} tramos. Raya negra = mediana. Cifras coherentes con docs/models/label_v1.1_checks.md §4.")
    save(fig, "04_reparto_y_duracion.png")


# ---------------------------------------------------------------- 5 estudio de revisión
def fig_revision(rev, cifras):
    A = pd.DataFrame(rev["summary_latest"]).dropna(subset=["concord"])
    B = pd.DataFrame(rev["summary_alfred"]).dropna(subset=["concord"])
    kf = rev["k_final"]
    cifras["revision"] = {"k_star": rev["k_star"], "k_final": kf, "lag": rev["lag"],
                          "provisional_months": rev["provisional_months"], "n_cortes": len(rev["cuts"])}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"wspace": 0.25})
    for ax, col, thr, lab_, fmt in [(a1, "concord", 0.95, "concordancia de la etiqueta dura", "pct"),
                                    (a2, "dp_mean", 0.05, "Δp medio (probabilidad que cambia de cuadrante)", "num")]:
        ax.plot(A.k, A[col], color="#33507a", lw=2, label="A: última vintage cortada en T")
        ax.plot(B.k, B[col], color="#9a6fb0", lw=2, ls="--", label="B: + vintages ALFRED de INDPRO y PAYEMS")
        ax.axhline(thr, color=INK, lw=0.9, ls=":")
        ax.axvline(kf, color="#d64545", lw=1.2)
        ax.text(kf + 1, ax.get_ylim()[0] if False else (0.80 if fmt == "pct" else 0.075),
                f"k* = {kf} meses\n→ 54 provisionales", color="#d64545", fontsize=8.5)
        ax.set_xlabel("k = meses entre el corte de datos T y el mes etiquetado")
        ax.set_ylabel(lab_)
        ax.set_xlim(0, 85)
        if fmt == "pct":
            ax.set_ylim(0.78, 1.0)
            ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
            ax.text(1, thr + 0.003, "regla: ≥ 95 %", fontsize=8, color=INK)
        else:
            ax.set_ylim(0, 0.12)
            ax.legend(loc="upper right", fontsize=8)
            ax.text(1, thr + 0.002, "regla: ≤ 0,05", fontsize=8, color=INK)
    fig.suptitle(f"Un mes no se puede dar por cerrado hasta ~{kf} meses después del dato: antes, la etiqueta aún cambia",
                 x=0.01, ha="left", fontsize=12.5, fontweight="bold", y=1.02)
    footer(fig, f"data/archive/labels/revision_study.json ({len(rev['cuts'])} cortes semestrales 1975-01 → 2024-07; "
                "docs/models/label_revision_study.md). provisional = múltiplo de 6 ≥ k* − 4 (desfase de la etiqueta).")
    save(fig, "05_estudio_revision.png")


# ---------------------------------------------------------------- 6 últimos 24 meses
def fig_ultimos(lab, rules, cifras):
    last = lab.tail(24).reset_index(drop=True)
    r = rules.copy()
    r["m"] = r.date.dt.to_period("M")
    months = pd.period_range(last.date.iloc[0].to_period("M"), r.m.max(), freq="M")
    x = np.arange(len(months))
    idx = {m: i for i, m in enumerate(months)}
    fig, (ax, axr) = plt.subplots(2, 1, figsize=(12, 5.6), sharex=True,
                                  gridspec_kw={"height_ratios": [1, 0.13], "hspace": 0.12})
    bottom = np.zeros(len(last))
    xl = np.array([idx[d.to_period("M")] for d in last.date])
    for q in Q:
        ax.bar(xl, last[PCOL[q]], bottom=bottom, color=QCOL[q], width=0.86, label=QNAME[q],
               edgecolor="white", linewidth=0.6)
        bottom += last[PCOL[q]].values
    for i, row in last.iterrows():
        if row.frontera:
            ax.text(xl[i], 1.02, "F", ha="center", fontsize=7.5, color=MUTED)
    nolab = [i for m, i in idx.items() if m > last.date.iloc[-1].to_period("M")]
    ax.axvspan(min(nolab) - 0.5, max(nolab) + 0.5, color="#f4f4f4", lw=0)
    ax.text(np.mean(nolab), 0.5, "sin etiqueta todavía\n(necesita datos\nhasta t+4)", ha="center", va="center",
            fontsize=8.5, color=MUTED)
    ax.set_ylim(0, 1.08)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_ylabel("probabilidad (etiqueta v1.1)")
    ax.grid(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.13), ncol=4, fontsize=8.5)
    rr = r.set_index("m").reindex(months)
    for i, m in enumerate(months):
        qn = rr.loc[m, "quadrant"]
        if isinstance(qn, str):
            axr.bar(i, 1, color=QCOL[RULES_MAP[qn]], width=0.86, edgecolor="white", linewidth=0.6)
    axr.set_yticks([0.5], ["clasificador\nde reglas"])
    axr.set_ylim(0, 1)
    axr.grid(False)
    axr.set_xticks(x, [m.strftime("%b\n%y") if (m.month in (1, 4, 7, 10)) else "" for m in months], fontsize=8)
    axr.set_xlim(-0.6, len(months) - 0.4)
    lr = last.iloc[-1]
    comp = []
    for _, row in last.iterrows():
        m = row.date.to_period("M")
        qn = rr.loc[m, "quadrant"] if m in rr.index else None
        comp.append({"mes": str(m), "etiqueta": row.label_hard, "p_max": float(row.max_prob),
                     "reglas": qn, "coinciden": RULES_MAP.get(qn) == row.label_hard})
    cifras["ultimos24"] = {"coinciden": int(sum(c["coinciden"] for c in comp)), "n": len(comp), "detalle": comp,
                           "reglas_hasta": str(r.m.max()),
                           "reglas_ultimos": {str(m): rr.loc[m, "quadrant"] for m in months[-6:]}}
    n_ok = cifras["ultimos24"]["coinciden"]
    ax.set_title(f"Último mes con etiqueta ({lr.date:%Y-%m}): inflación persistente con crecimiento en torno a "
                 f"tendencia (estanflación {lr.p_stagflation:.0%}, provisional)\n"
                 f"El clasificador de reglas coincide en {n_ok} de 24 meses".replace("%", " %"),
                 pad=30, fontsize=11.5)
    footer(fig, "etiqueta: data/archive/labels/regime_us_v1.1.parquet (todos provisionales; F = mes frontera, prob. máx. "
                "< 0,55). Reglas: tabla regime_monthly del warehouse (src/regime), colores por correspondencia aproximada.")
    save(fig, "06_ultimos_24_meses.png")


# ---------------------------------------------------------------- 7 desfase v0.1 → v0.2
def fig_desfase(v01, v02, cfma3, cifras):
    c = cfma3.assign(date=pd.to_datetime(cfma3.date)).set_index("date")["value"]
    c.index = c.index.to_period("M")
    end = pd.Period("2021-10", "M")
    res = {}
    ks = range(-6, 7)
    for name, d in [("v0.1", v01), ("v0.2 a v1.1 (misma G)", v02)]:
        g = d.set_index(d.date.dt.to_period("M"))["G"]
        g = g[(g.index >= pd.Period("1967-01", "M")) & (g.index <= end)]
        res[name] = [float(g.corr(c.shift(-k).reindex(g.index))) for k in ks]
    cifras["desfase"] = {"k": list(ks), **res, "muestra": "1967-01 → 2021-10",
                         "nota": "corr(G(t), CFNAI-MA3(t+k)); CFNAIMA3 de obs_latest"}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"wspace": 0.25})
    for (name, vals), col, ls in zip(res.items(), ["#999999", INK], ["--", "-"]):
        a1.plot(list(ks), vals, color=col, lw=2, ls=ls, marker="o", ms=4, label=name)
        kmax = list(ks)[int(np.nanargmax(vals))]
        a1.annotate(f"máx. en k = {kmax:+d}", (kmax, max(vals)), xytext=(0, 8), textcoords="offset points",
                    ha="center", fontsize=8, color=col)
    a1.axvline(0, color=MUTED, lw=0.8, ls=":")
    a1.set_xlabel("k (meses): G del mes t frente al índice de actividad CFNAI-MA3 del mes t+k")
    a1.set_ylabel("correlación")
    a1.legend(loc="lower center", fontsize=8.5)
    a1.set_title("La v0.1 se parecía más a la actividad de hace 2-3 meses", fontsize=11)
    w = (pd.Timestamp("2007-01-01"), pd.Timestamp("2010-12-01"))
    spans = rec_spans(v02)
    shade_rec(a2, [(a, b) for a, b in spans if b > w[0] and a < w[1]])
    for name, d, col, ls in [("v0.1", v01, "#999999", "--"), ("v0.2 a v1.1 (misma G)", v02, INK, "-")]:
        dd = d[(d.date >= w[0]) & (d.date <= w[1])]
        a2.plot(dd.date, dd.G, color=col, lw=2, ls=ls, label=name)
    a2.axhline(0, color=MUTED, lw=0.8)
    a2.set_ylabel("G (z frente a tendencia)")
    t01 = v01.loc[v01[(v01.date >= w[0]) & (v01.date <= w[1])].G.idxmin(), "date"]
    t02 = v02.loc[v02[(v02.date >= w[0]) & (v02.date <= w[1])].G.idxmin(), "date"]
    lagm = (t01.year - t02.year) * 12 + t01.month - t02.month
    cifras["desfase"]["fondo_2008"] = {"v0.1": str(t01.date()), "v0.2": str(t02.date()), "meses": lagm}
    a2.set_title(f"Recesión de 2008 (gris): la v0.1 tocaba fondo {lagm} meses más tarde", fontsize=11)
    a2.xaxis.set_major_locator(mdates.YearLocator())
    a2.legend(loc="lower right", fontsize=8.5)
    a2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle("El error de la v0.1: la etiqueta del mes t describía el crecimiento de unos 4 meses antes",
                 x=0.01, ha="left", fontsize=12.5, fontweight="bold", y=1.02)
    footer(fig, "data/archive/labels/regime_us_v0.1.parquet y regime_us_v0.2.parquet; CFNAIMA3 de data/warehouse.duckdb. "
                "Muestra 1967-01 → 2021-10. Ver docs/models/label_v0.1_checks.md §8 y label_v0.2_checks.md.")
    save(fig, "07_desfase_v01_v02.png")


# ---------------------------------------------------------------- utilidades para leer tablas de informes .md
def md_table(path: Path, header_has: str):
    """Filas (listas de celdas) de la primera tabla markdown cuya cabecera contiene ``header_has``."""
    lines = path.read_text().splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("|") and header_has in ln:
            rows = []
            for r in lines[i + 2:]:
                if not r.startswith("|"):
                    break
                rows.append([c.strip() for c in r.strip().strip("|").split("|")])
            head = [c.strip() for c in ln.strip().strip("|").split("|")]
            return head, rows
    raise ValueError(f"tabla con '{header_has}' no encontrada en {path}")


def num(cell: str) -> float:
    """Primer número de una celda con formato español ('**+15,4** (12)' → 15.4; '−2,1' → -2.1)."""
    import re
    m = re.search(r"[+\-−]?\d+(?:,\d+)?", cell.replace("**", ""))
    return float(m.group(0).replace("−", "-").replace(",", "."))


# ---------------------------------------------------------------- 8 empalme 1957-59 (v1.0 → v1.1)
def fig_empalme(lab, lab10, meta, cifras):
    w = (pd.Timestamp("1956-01-01"), pd.Timestamp("1960-12-01"))
    a = lab10[(lab10.date >= w[0]) & (lab10.date <= w[1])].set_index("date")
    b = lab[(lab.date >= w[0]) & (lab.date <= w[1])].set_index("date")
    m = lab10.merge(lab, on="date", suffixes=("_0", "_1"))
    m = m[m.weight_1 == 1]
    chg = m[m.label_hard_0 != m.label_hard_1]
    sp = meta["splice_cpi_core"]
    cifras["empalme"] = {"ajuste_pp_v1_1": sp["adj_pp"], "ventana": [sp["from"], sp["to"]],
                         "meses_cambian_cuadrante": [str(d.date())[:7] for d in chg.date],
                         "cambios": {f"{a}->{b}": int(n) for (a, b), n in
                                     chg.groupby(["label_hard_0", "label_hard_1"]).size().items()},
                         "max_abs_dI": float((m.I_1 - m.I_0).abs().max())}
    fig, ax = plt.subplots(figsize=(11, 4.4))
    ax.axvspan(pd.Timestamp("1957-04-01"), pd.Timestamp("1959-04-01"), facecolor="none", hatch="..",
               edgecolor="#d9c9a0", lw=0, zorder=0)
    shade_rec(ax, [(x, y) for x, y in rec_spans(lab) if y > w[0] and x < w[1]])
    ax.text(pd.Timestamp("1958-04-01"), 4.55, "tramo empalmado\n(IPC subyacente + ajuste)", ha="center", va="top",
            fontsize=8, color=MUTED)
    ax.plot(a.index, a.I, color="#999999", lw=1.8, ls="--", label="v1.0 (IPC subyacente − 0,4 pp)")
    ax.plot(b.index, b.I, color=INK, lw=2, label=f"v1.1 (IPC subyacente + {sp['adj_pp']:.2f} pp)".replace(".", ","))
    ax.axhline(2.5, color="#d64545", lw=1, ls=":")
    ax.text(w[1], 2.55, "umbral κ = 2,5 %", ha="right", va="bottom", fontsize=8, color="#d64545")
    for d in chg.date:
        ax.scatter([d], [b.loc[d, "I"]], s=60, facecolor="none", edgecolor=QCOL["stagflation"], lw=1.6, zorder=5)
    ax.scatter([], [], s=60, facecolor="none", edgecolor=QCOL["stagflation"], lw=1.6,
               label="mes que pasa de crec. bajo a estanflación")
    ax.set_ylabel("I: inflación subyacente, 6 m centrada (% anualizado)")
    ax.set_ylim(0.5, 4.7)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(loc="lower left", fontsize=8.5)
    ax.set_title(f"v1.1: el empalme de 1957-59 sube I ~0,6 pp y {len(chg)} meses de 1957 pasan de crec. bajo a "
                 "estanflación; la serie ya no salta en 1959-04")
    footer(fig, "data/archive/labels/regime_us_v1.0.parquet y regime_us_v1.1.parquet (+ meta.json → splice_cpi_core); "
                "gris = recesiones NBER (1957-58 y 1960-61); punteado = tramo empalmado 1957-04 → 1959-03. Ver docs/models/label_v1.1_checks.md §6 y label_spec.md §4.")
    save(fig, "08_empalme_v10_v11.png")


# ---------------------------------------------------------------- 9 el listón: persistencia point-in-time
def fig_persistencia(cifras):
    src = ROOT / "docs" / "models" / "label_v1.1_checks.md"
    head, rows = md_table(src, "log-loss (blando)")
    tab = [dict(zip(head, r)) for r in rows]
    sel = {"PIT (t−5, datos de t)": ("Persistencia point-in-time\n(etiqueta de t−5 con lo\npublicado en t)", "ok"),
           "final desplazada 5": ("Etiqueta definitiva\nde t−5", "fuga"),
           "final desplazada 1 (con fuga)": ("\"Mes anterior\"\n(etiqueta definitiva\nde t−1)", "fuga")}
    pts = [r for r in tab if r["muestra"] == "puntuable" and r["baseline"] in sel]
    ent = [r for r in tab if r["muestra"] == "entrenamiento" and r["baseline"] == "PIT (t−5, datos de t)"][0]
    acc = [float(r["acierto"].rstrip("%")) / 100 for r in pts]
    ll = [float(r["log-loss (blando)"]) for r in pts]
    cifras["liston"] = {r["baseline"]: {"n": int(r["n"]), "acierto": a, "logloss_blando": l}
                        for r, a, l in zip(pts, acc, ll)}
    cifras["liston"]["PIT_entrenamiento_hasta_2004"] = {"n": int(ent["n"]),
                                                        "acierto": float(ent["acierto"].rstrip("%")) / 100,
                                                        "logloss_blando": float(ent["log-loss (blando)"])}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 4.9), gridspec_kw={"width_ratios": [1.25, 1], "wspace": 0.6})
    # izquierda: qué datos hay el día de la decisión
    months = list(range(-6, 5))
    a1.axvspan(0.5, 4.6, color="#f6e3e3", lw=0)
    a1.text(2.55, 0.75, "FUTURO: aún no publicado\nel día de la decisión", ha="center", va="center", fontsize=8.5,
            color="#a33")
    a1.axvline(0.5, color=INK, lw=1.4)
    a1.text(0.45, 3.95, "día de la decisión\n(fin del mes t)", ha="right", va="top", fontsize=8.5, color=INK)
    bars = [(3, -1, 4, "#d64545", "Etiqueta del mes t−1: necesita datos hasta t+3 → no existe aún", "con fuga"),
            (2, -5, 4, QCOL["expansion"], "Etiqueta del mes t−5: necesita datos hasta t−1 → calculable", "permitida"),
            (1, -6, 0, "#999999", "Último dato publicado: producción y empleo de t−1; PCE de t−2", "")]
    for y, c, half, col, txt, tag in bars:
        if half:
            a1.barh(y, 9, left=c - 4.5, height=0.45, color=col, alpha=0.35)
            a1.scatter([c], [y], color=col, s=55, zorder=4)
        else:
            a1.barh(y, 6.5, left=-7, height=0.45, color=col, alpha=0.35)
        a1.text(-6.85, y + 0.33, txt, fontsize=8, color=INK, va="bottom")
    a1.set_yticks([])
    a1.set_xticks(months, [f"t{m:+d}" if m else "t" for m in months], fontsize=8)
    a1.set_xlim(-7, 4.6)
    a1.set_ylim(0.4, 4.1)
    a1.grid(False)
    a1.spines["left"].set_visible(False)
    a1.set_xlabel("meses")
    a1.set_title("La etiqueta del mes t necesita datos hasta t+4:\nel día t, la más reciente calculable es la de t−5",
                 fontsize=11)
    # derecha: acierto y log-loss
    y = np.arange(len(pts))[::-1]
    for yi, r, a_, l_ in zip(y, pts, acc, ll):
        lab_, kind = sel[r["baseline"]]
        col = QCOL["expansion"] if kind == "ok" else "#d64545"
        a2.barh(yi, a_, color=col, alpha=0.9 if kind == "ok" else 0.35, height=0.6,
                hatch=None if kind == "ok" else "///", edgecolor=col)
        a2.text(a_ + 0.01, yi, f"{a_:.1%} · log-loss {l_:.3f}".replace(".", ",").replace("%", " %"), va="center",
                fontsize=8.5, color=INK)
    a2.set_yticks(y, [sel[r["baseline"]][0] for r in pts], fontsize=8.5)
    a2.set_xlim(0, 1.18)
    a2.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    a2.set_xlabel(f"acierto del cuadrante ({pts[0]['n']} meses puntuables)")
    a2.set_title("El listón honesto es 63,6 %; el 89 % del \"mes anterior\"\nusa datos del futuro (rayado = con fuga)",
                 fontsize=11)
    footer(fig, "docs/models/label_v1.1_checks.md §6b (tabla de persistencia, muestra puntuable 1955-06 → 2021-10) y "
                "label_spec.md §12. Log-loss blanda: menor es mejor. Retrasos de publicación según el calendario del Constructor.")
    save(fig, "09_liston_persistencia.png")


# ---------------------------------------------------------------- 10 rendimientos por cuadrante 1955-2004 (Estratega)
def fig_rendimientos(cifras):
    src = ROOT / "docs" / "reviews" / "2026-10-15_estratega_macro_etiqueta.md"
    head, rows = md_table(src, "Expansión (149 m)")
    assets = {"RV EE. UU.": "Bolsa EE. UU.", "Bono 10a": "Bono 10 años", "Materias primas (colat.)": "Materias primas",
              "Oro": "Oro", "60/40": "Cartera 60/40"}
    qcols = head[1:5]
    M = pd.DataFrame([[num(c) for c in r[1:5]] for r in rows if r[0] in assets],
                     index=[assets[r[0]] for r in rows if r[0] in assets], columns=Q)
    _, erows = md_table(src, "1955-79: RV / bono / MP / oro")
    qmap = {"Expansión": "expansion", "Late": "late_cycle", "Estanflación": "stagflation", "Bajo / desinf.": "low_growth_disinfl"}
    ep = {}
    for r in erows:
        q = qmap[r[0].replace("**", "").strip()]
        e1 = [num(x) for x in r[1].split("/")]
        e2 = [num(x) for x in r[2].split("/")]
        ep[q] = {"1955-79": {"RV": e1[0], "bono": e1[1]}, "1980-2004": {"RV": e2[0], "bono": e2[1]}}
    _, rrows = md_table(src, "| RV real | bono real")
    rec = {r[0]: {"RV": num(r[1]), "bono": num(r[2])} for r in rrows}
    cifras["rendimientos_1955_2004"] = {"fuente": str(src.relative_to(ROOT)), "cuadrante": M.to_dict(),
                                        "meses_por_cuadrante": dict(zip(Q, [num(c.split("(")[1]) for c in qcols])),
                                        "por_epoca": ep, "recesion": rec}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.0), gridspec_kw={"width_ratios": [1.15, 1], "wspace": 0.38})
    vmax = 16
    im = a1.imshow(M.values, cmap="RdBu", vmin=-vmax, vmax=vmax, aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M.values[i, j]
            a1.text(j, i, f"{v:+.1f}".replace(".", ","), ha="center", va="center", fontsize=9.5,
                    color="white" if abs(v) > 10 else INK)
    a1.set_xticks(range(4), [f"{QSHORT[q]}\n({int(n)} m)" for q, n in
                             zip(Q, cifras["rendimientos_1955_2004"]["meses_por_cuadrante"].values())], fontsize=8.5)
    a1.set_yticks(range(M.shape[0]), M.index, fontsize=9)
    a1.grid(False)
    for q, j in zip(Q, range(4)):
        a1.add_patch(plt.Rectangle((j - 0.5, -0.62), 1, 0.12, color=QCOL[q], clip_on=False))
    cb = fig.colorbar(im, ax=a1, fraction=0.04, pad=0.02)
    cb.set_label("% real anual")
    a1.set_title("Rendimiento real medio por cuadrante, 1955-2004 (% anual)", fontsize=11, pad=14)
    # derecha: inestabilidad por épocas (bolsa)
    x = np.arange(4)
    w_ = 0.36
    v1 = [ep[q]["1955-79"]["RV"] for q in Q]
    v2 = [ep[q]["1980-2004"]["RV"] for q in Q]
    a2.bar(x - w_ / 2, v1, w_, color="#9a9a9a", label="1955-79")
    a2.bar(x + w_ / 2, v2, w_, color="#33507a", label="1980-2004")
    for xi, a_, b_ in zip(x, v1, v2):
        for xx, v in ((xi - w_ / 2, a_), (xi + w_ / 2, b_)):
            a2.text(xx, v + (0.4 if v >= 0 else -0.4), f"{v:+.1f}".replace(".", ","), ha="center",
                    va="bottom" if v >= 0 else "top", fontsize=8)
        if np.sign(a_) != np.sign(b_):
            a2.text(xi, max(a_, b_) + 2.6, "cambia\nde signo", ha="center", fontsize=8, color="#d64545",
                    fontweight="bold")
    a2.axhline(0, color=INK, lw=0.8)
    a2.set_xticks(x, [QSHORT[q] for q in Q], fontsize=8.5)
    a2.set_ylim(-5, 22)
    a2.set_ylabel("bolsa EE. UU., % real anual")
    a2.legend(loc="upper right", fontsize=8.5)
    a2.set_title("Bolsa por épocas: \"Estanflación\" y \"Crec. bajo\" cambian de signo", fontsize=11)
    fig.suptitle("DESCRIPCIÓN A POSTERIORI, NO OPERABLE: la etiqueta usa datos futuros. Solo \"Expansión → bolsa\" y "
                 "\"Crec. bajo → bonos\" se mantienen en las dos épocas", x=0.01, ha="left", fontsize=12,
                 fontweight="bold", y=1.03, color="#7a1f1f")
    footer(fig, "docs/reviews/2026-10-15_estratega_macro_etiqueta.md §3.1 (cálculo del Estratega macro con la etiqueta dura "
                "v1.1 y series del warehouse; reales con CPIAUCSL). Solo 1955-01 → 2004-12; nada del periodo bloqueado "
                "(2005 →). Unos 20 tramos por cuadrante: incertidumbre grande.")
    save(fig, "10_rendimientos_por_cuadrante_1955_2004.png")


# ---------------------------------------------------------------- comparación con el clasificador de reglas
def comp_reglas(lab, rules, cifras):
    r = rules.assign(m=rules.date.dt.to_period("M"))
    l = lab.assign(m=lab.date.dt.to_period("M"))
    x = l.merge(r[["m", "quadrant", "vintage_mode"]], on="m")
    s = x[(x.weight == 1) & (~x.provisional)].copy()
    s["r"] = s.quadrant.map(RULES_MAP)
    cifras["reglas_vs_etiqueta"] = {
        "meses": int(len(s)), "concordancia": float((s.r == s.label_hard).mean()),
        "concordancia_sin_frontera": float((s[~s.frontera].r == s[~s.frontera].label_hard).mean()),
        "tabla": pd.crosstab(s.label_hard, s.quadrant).to_dict(),
        "nota": "correspondencia aproximada Goldilocks=expansion, Reflación=late_cycle, Estanflación=stagflation, "
                "Deflación/recesión=low_growth_disinfl; las definiciones no son idénticas",
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lab, meta, rev, v01, v02, v10, cat, rules, cfma3 = load()
    cifras = {"etiqueta": {"version": meta["version"], "estado": meta["status"], "sha256_content": meta["sha256_content"],
                           "primer_mes": str(lab.date.min().date()), "ultimo_mes": str(lab.date.max().date()),
                           "meses": int(len(lab)), "puntuables": int(((lab.weight == 1) & ~lab.provisional).sum()),
                           "provisional_desde": str(lab.loc[lab.provisional, 'date'].min().date()),
                           "ultimo": lab.iloc[-1][["date", *PCOL.values(), "label_hard", "frontera", "G", "I"]]
                           .astype(str).to_dict()}}
    fig_cobertura(cat, cifras)
    fig_historia(lab, cifras)
    fig_mapa(lab, cifras)
    fig_reparto(lab, cifras)
    fig_revision(rev, cifras)
    fig_ultimos(lab, rules, cifras)
    fig_desfase(v01, v02, cfma3, cifras)
    fig_empalme(lab, v10, meta, cifras)
    fig_persistencia(cifras)
    fig_rendimientos(cifras)
    comp_reglas(lab, rules, cifras)
    from src.report.fase3 import make_figures_pit  # base PIT v0.3: gráficos 11-13 y clave pit_base
    make_figures_pit.run(cifras)
    (OUT / "cifras.json").write_text(json.dumps(cifras, ensure_ascii=False, indent=1, default=str))
    print("escrito", OUT / "cifras.json")


if __name__ == "__main__":
    main()
