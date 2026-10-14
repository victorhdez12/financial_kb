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
LABELS = ROOT / "data" / "archive" / "labels"
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
OUT = ROOT / "obsidian" / "Reports" / "Fase 3" / "img"

Q = ["expansion", "late_cycle", "stagflation", "low_growth_disinfl"]
QNAME = {
    "expansion": "Expansión",
    "late_cycle": "Late cycle / sobrecalentamiento",
    "stagflation": "Estanflación",
    "low_growth_disinfl": "Crecimiento bajo / desinflación",
}
QSHORT = {"expansion": "Expansión", "late_cycle": "Late cycle", "stagflation": "Estanflación",
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
    lab = pd.read_parquet(LABELS / "regime_us_v1.0.parquet")
    meta = json.loads((LABELS / "regime_us_v1.0.meta.json").read_text())
    rev = json.loads((LABELS / "revision_study.json").read_text())
    v01 = pd.read_parquet(LABELS / "regime_us_v0.1.parquet")
    v02 = pd.read_parquet(LABELS / "regime_us_v0.2.parquet")
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    cat = con.sql("select c.series_id, c.source, c.category, c.country_iso3, c.pit_role, "
                  "s.first_date, s.last_date, s.n_obs from catalog c "
                  "left join series_summary s using (series_id)").df()
    rules = con.sql("select date, quadrant, vintage_mode from regime_monthly order by date").df()
    cfma3 = con.sql("select date, value from obs_latest where series_id = 'CFNAIMA3' order by date").df()
    con.close()
    return lab, meta, rev, v01, v02, cat, rules, cfma3


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
           ("2020-04-01", "COVID\n2020"), ("2021-08-01", "2021-22:\nsobrecalent.")]
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
    footer(fig, "data/archive/labels/regime_us_v1.0.parquet (etiqueta v1.0, 1950-01 → 2026-04); recesiones = columna "
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
    corners = [(3.0, 0.0, "Expansión", "expansion"), (3.0, 10.8, "Late cycle", "late_cycle"),
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
    footer(fig, f"data/archive/labels/regime_us_v1.0.parquet, meses con weight = 1 (1955-01 → 2026-04). "
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
    footer(fig, f"data/archive/labels/regime_us_v1.0.parquet, {len(sc)} meses puntuables (1955-01 → 2021-10), "
                f"{len(rd)} tramos. Raya negra = mediana. Cifras coherentes con docs/models/label_v1.0_checks.md §4.")
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
    ax.set_ylabel("probabilidad (etiqueta v1.0)")
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
    ax.set_title(f"Último mes con etiqueta ({lr.date:%Y-%m}): estanflación con {lr.p_stagflation:.0%} "
                 f"(provisional); el clasificador de reglas coincide en {n_ok} de 24 meses".replace("%", " %"),
                 pad=30, fontsize=11.5)
    footer(fig, "etiqueta: data/archive/labels/regime_us_v1.0.parquet (todos provisionales; F = mes frontera, prob. máx. "
                "< 0,55). Reglas: tabla regime_monthly del warehouse (src/regime), colores por correspondencia aproximada.")
    save(fig, "06_ultimos_24_meses.png")


# ---------------------------------------------------------------- 7 desfase v0.1 → v0.2
def fig_desfase(v01, v02, cfma3, cifras):
    c = cfma3.assign(date=pd.to_datetime(cfma3.date)).set_index("date")["value"]
    c.index = c.index.to_period("M")
    end = pd.Period("2021-10", "M")
    res = {}
    ks = range(-6, 7)
    for name, d in [("v0.1", v01), ("v0.2 / v1.0", v02)]:
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
    for name, d, col, ls in [("v0.1", v01, "#999999", "--"), ("v0.2 / v1.0", v02, INK, "-")]:
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
    lab, meta, rev, v01, v02, cat, rules, cfma3 = load()
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
    comp_reglas(lab, rules, cifras)
    (OUT / "cifras.json").write_text(json.dumps(cifras, ensure_ascii=False, indent=1, default=str))
    print("escrito", OUT / "cifras.json")


if __name__ == "__main__":
    main()
