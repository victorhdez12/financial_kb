"""Gráficos de la base point-in-time v0.3 (entregable 2) para el informe de la Fase 3 (Reportero).

Lee solo ficheros de resultados (sin warehouse):
- ``<FIN_DATA_ROOT>/features/pit_us_v0.3.meta.json`` y ``pit_us_v0.3_vintage.parquet`` (cobertura; sin etiqueta)
- ``research/pit_calendar_measured.csv`` (retardos de publicación medidos)
- ``<FIN_DATA_ROOT>/features/baseline_persistence_v0.3_{modo}.parquet`` + etiqueta v1.1, **filtradas a ≤ 2004-12
  antes de cruzarlas** (nada del periodo bloqueado en relación con la etiqueta)

Escribe ``11_pit_cobertura_variables.png``, ``12_pit_retardos_publicacion.png``, ``13_pit_liston_modos.png`` y la
clave ``pit_base`` de ``img/cifras.json`` (conserva el resto de claves).

Uso: ``.venv/bin/python -m src.report.fase3.make_figures_pit`` (también lo llama ``make_figures``).
No modifica datos ni código de producción.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.report.fase3 import make_figures as MF  # noqa: E402  (estilo común, OUT, footer, save)

ROOT = MF.ROOT
PIT_VERSION = "0.3"  # base PIT congelada (tag pit-v0.3)
FEAT = ROOT / "data" / "archive" / "features"
LABEL = ROOT / "data" / "archive" / "labels" / "regime_us_v1.1.parquet"
HOLDOUT = pd.Timestamp("2005-01-01")
TRAIN_END = pd.Timestamp("2004-12-01")
Q = MF.Q

# paleta categórica de referencia (validada con dataviz/scripts/validate_palette.js, modo claro: pasa)
SCOL = {"principal": "#2a78d6", "principal_epoca": "#1baf7a", "condicional": "#eb6834", "modulo_adicional": "#6250d6"}
SNAME = {"principal": "Principal", "principal_epoca": "Principal por época",
         "condicional": "Condicional (fuera del modelo principal)",
         "modulo_adicional": "Módulo adicional (se evalúa aparte)"}
MCOL = {"vintage": "#2a78d6", "latest_truncated": "#eb6834"}
ECOL = {"<1980": "#86b6ef", "1980-1999": "#3987e5", "2000-2012": "#1c5cab", "2013+": "#0d366b"}  # rampa secuencial


def load_meta():
    return json.loads((FEAT / f"pit_us_v{PIT_VERSION}.meta.json").read_text())


# ---------------------------------------------------------------- 11 cobertura de variables por estado y época
def fig_cobertura_pit(meta, cifras):
    cols = meta["columns"]["vintage"]
    mat = pd.read_parquet(FEAT / f"pit_us_v{PIT_VERSION}_vintage.parquet")
    dates = pd.to_datetime(mat["decision_date"])
    est = pd.Series({c: v["estado"] for c, v in cols.items()})
    pde = {c: (pd.Timestamp(v["principal_desde_efectivo"]) if v["principal_desde_efectivo"] else None)
           for c, v in cols.items()}
    # clase de cada celda con dato: módulo adicional / condicional (antes de su principal_desde_efectivo) / estado
    counts = {k: np.zeros(len(mat), int) for k in SCOL}
    for c in cols:
        has = mat[c].notna().to_numpy()
        if est[c] == "modulo_adicional":
            counts["modulo_adicional"] += has
            continue
        p = pde[c]
        before = (dates < p).to_numpy() if p is not None else np.zeros(len(mat), bool)
        if est[c] == "condicional" and p is None:
            before[:] = True
        counts["condicional"] += has & before
        k = "principal_epoca" if est[c] == "principal_epoca" else "principal"
        counts[k] += has & ~before
    df = pd.DataFrame(counts, index=dates)
    snap = {str(y): {k: int(df.loc[df.index.year == y].iloc[-1][k]) for k in SCOL}
            for y in (1960, 1970, 1977, 1983, 1990, 2004)}
    cifras["pit_base"]["cobertura"] = {
        "n_columnas": len(cols), "por_estado": est.value_counts().to_dict(),
        "principal_desde_efectivo": {c: str(p.date()) for c, p in pde.items() if p is not None},
        "heredadas": [c for c, v in cols.items() if v.get("principal_desde_heredado")],
        "columnas_en_diciembre": snap,
        "nota": "celdas no vacías de la matriz vintage; condicional = antes de principal_desde_efectivo (o estado condicional sin fecha)",
    }

    fig, ax = plt.subplots(figsize=(12.5, 5.4))
    order = ["principal", "principal_epoca", "condicional", "modulo_adicional"]
    ax.stackplot(df.index, *[df[k] for k in order], colors=[SCOL[k] for k in order], alpha=0.9,
                 edgecolor="white", linewidth=0.6, labels=[SNAME[k] for k in order])
    ax.set_xlim(pd.Timestamp("1950-01-01"), df.index.max())
    ax.set_ylim(0, 68)
    ax.set_ylabel("columnas con dato en la fecha de decisión")
    ax.axhline(len(cols), color=MF.MUTED, lw=0.8, ls=":")
    ax.text(pd.Timestamp("1951-01-01"), len(cols) + 0.6, f"{len(cols)} columnas en la lista blanca", fontsize=8,
            color=MF.MUTED)
    ev = [("1968-05-01", "E1 · Filadelfia,\nparo semanal, SPF"), ("1973-03-01", "E2 · dólar,\ncobre/oro"),
          ("1978-01-01", "E3 · IPC subyacente\n(y heredadas), Michigan"), ("1984-01-01", "tcu_gap\n(G.17 desde 1983)"),
          ("2003-09-22", "VIX\n(definición actual)")]
    for i, (d, t) in enumerate(ev):
        x = pd.Timestamp(d)
        ax.axvline(x, color=MF.INK, lw=0.7, ls="--", alpha=0.6)
        ax.text(x + pd.Timedelta(days=60), 67.5 - 4.6 * (i % 2), t, fontsize=7.6, color=MF.INK, ha="left", va="top",
                bbox=dict(fc="white", ec="none", alpha=0.8, pad=1))
    ax.axvspan(HOLDOUT, df.index.max(), color="#f2f2f2", zorder=-1)
    ax.text(pd.Timestamp("2006-01-01"), 3, "periodo bloqueado (2005 →):\naquí solo se cuentan columnas,\nsin mirar la etiqueta",
            fontsize=7.8, color="white", va="bottom")
    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, loc="upper left", bbox_to_anchor=(0.0, -0.07), ncol=4, fontsize=8.4)
    p04 = snap["2004"]
    ax.set_title(f"El modelo principal gana variables por épocas: en 1960 puede usar {snap['1960']['principal']}, "
                 f"en 2004 ya {p04['principal'] + p04['principal_epoca']}\n"
                 "Las condicionales están en la matriz, pero solo entran en sensibilidad hasta que existían de verdad",
                 fontsize=11.5)
    fig.text(0.01, -0.06, "Fuente: " + f"data/archive/features/pit_us_v{PIT_VERSION}_vintage.parquet (celdas no vacías) y "
                   f"pit_us_v{PIT_VERSION}.meta.json → columns.vintage (estado, principal_desde_efectivo). "
                   "Épocas: docs/models/pit_base.md §4. Cálculo del Reportero (make_figures_pit.py).",
             fontsize=7.5, color=MF.MUTED, ha="left", va="top", wrap=True)
    MF.save(fig, "11_pit_cobertura_variables.png")


# ---------------------------------------------------------------- 12 retardos de publicación medidos por época
def fig_retardos(cifras):
    src = ROOT / "research" / "pit_calendar_measured.csv"
    m = pd.read_csv(src)
    sel = [("PAYEMS", "Empleo (PAYEMS)"), ("INDPRO", "Producción industrial"), ("PPIACO", "Precios de producción"),
           ("M2SL", "Dinero M2"), ("CPIAUCSL", "IPC"), ("GDPC1", "PIB (avance, trimestral)"),
           ("PCEPI", "Deflactor PCE"), ("CMRMTSPL", "Ventas reales (CMRMTSPL)")]
    epochs = list(ECOL)
    fig, ax = plt.subplots(figsize=(12.5, 5.6))
    out = {}
    off = {e: (i - 1.5) * 0.18 for i, e in enumerate(epochs)}
    for yi, (sid, name) in enumerate(sel[::-1]):
        out[sid] = {}
        for e in epochs:
            r = m[(m.series_id == sid) & (m.epoca == e)]
            if r.empty:
                continue
            r = r.iloc[0]
            out[sid][e] = {"n": int(r.n), "mediana": float(r.mediana), "p90": float(r.p90), "max": float(r["max"])}
            y = yi + off[e]
            ax.plot([r.mediana, r.p90], [y, y], color=ECOL[e], lw=2.2, solid_capstyle="round")
            ax.scatter([r.mediana], [y], color=ECOL[e], s=34, zorder=3, edgecolor="white", linewidth=1)
            ax.scatter([r["max"]], [y], color=ECOL[e], s=16, marker="x", zorder=3, linewidth=1)
    ax.set_yticks(range(len(sel)), [n for _, n in sel[::-1]], fontsize=9)
    ax.axvspan(0, 30, color="#eef5ee", zorder=-1)
    ax.text(1, -0.6, "≲ 30 días: el dato del mes anterior\nya se conoce el último día hábil del mes",
            fontsize=7.8, color="#2f6b2f", va="center")
    ax.set_xlim(0, 120)
    ax.set_ylim(-1.0, len(sel) - 0.5)
    ax.set_xlabel("días desde el fin del periodo hasta la primera publicación (ALFRED)")
    for e in epochs:
        ax.plot([], [], color=ECOL[e], lw=2.2, marker="o", label=e)
    ax.plot([], [], color=MF.MUTED, lw=0, marker="x", label="máximo (los de 2013+ son cierres del Gobierno)")
    ax.legend(loc="upper right", fontsize=8.3, title="época (punto = mediana, línea hasta el p90)", title_fontsize=8.3)
    cpi = out["CPIAUCSL"]
    ax.set_title(f"Los datos se publican cada vez antes: la mediana del IPC baja de {cpi['<1980']['mediana']:.0f} "
                 f"a {cpi['2013+']['mediana']:.0f} días\n"
                 "Antes del archivo de vintages se usa un retardo de reserva conservador (el máximo de la época más antigua)",
                 fontsize=11.5)
    MF.footer(fig, "research/pit_calendar_measured.csv (generado por src/features/calendar.py; solo primeras "
                   "publicaciones). Series sin barra en una época: sin vintages entonces. Ver docs/models/pit_calendar.md §2.")
    MF.save(fig, "12_pit_retardos_publicacion.png")
    cifras["pit_base"]["retardos"] = {"fuente": str(src.relative_to(ROOT)), "series": out}


# ---------------------------------------------------------------- 13 listón: persistencia PIT ≤ 2004 en los dos modos
def score(mode: str) -> dict:
    """Recalcula la persistencia ≤ 2004 (misma fórmula que src/features/pit.score_training).

    Etiqueta y predicciones se recortan a ≤ 2004-12 ANTES de cruzarlas: no se lee nada del periodo bloqueado.
    """
    lab = pd.read_parquet(LABEL)
    lab["date"] = pd.to_datetime(lab["date"])
    lab = lab[lab["date"] <= TRAIN_END]
    assert lab["date"].max() < HOLDOUT
    lab = lab[(lab["weight"] > 0) & ~lab["provisional"]].set_index("date")
    p = pd.read_parquet(FEAT / f"baseline_persistence_v{PIT_VERSION}_{mode}.parquet")
    p["month"] = pd.to_datetime(p["month"])
    p = p[p["month"] <= TRAIN_END].set_index("month")
    common = lab.index.intersection(p.index)
    P = np.clip(p.loc[common, [f"pers_{q}" for q in Q]].to_numpy(float), 1e-4, 1)
    P = P / P.sum(axis=1, keepdims=True)
    T = lab.loc[common, [f"p_{q}" for q in Q]].to_numpy(float)
    hard = p.loc[common, "pers_hard"].to_numpy() == lab.loc[common, "label_hard"].to_numpy()
    return {"n": int(len(common)), "desde": f"{common.min():%Y-%m}", "hasta": f"{common.max():%Y-%m}",
            "acierto": float(hard.mean()), "logloss_blanda": float(-(T * np.log(P)).sum(axis=1).mean())}


def fig_liston_modos(meta, cifras):
    res = {}
    for mode in ("vintage", "latest_truncated"):
        mine = score(mode)
        ref = meta["baseline"][mode]["entrenamiento_hasta_2004"]
        mine["coincide_con_meta"] = bool(mine["n"] == ref["n"] and abs(mine["acierto"] - ref["acierto"]) < 1e-12
                                         and abs(mine["logloss_blanda"] - ref["logloss_blanda"]) < 1e-9)
        res[mode] = mine
    cifras["pit_base"]["liston_hasta_2004"] = res
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 3.9), gridspec_kw={"wspace": 0.55})
    names = {"vintage": "vintage (principal):\ndatos tal como se publicaron",
             "latest_truncated": "latest_truncated (sensibilidad):\ndatos revisados, cortados en t"}
    modes = ["latest_truncated", "vintage"]
    for ax, key, fmt, xl, xmax in [
        (a1, "acierto", lambda v: f"{v:.2%}".replace(".", ",").replace("%", " %"), "acierto del cuadrante (más es mejor)", 1.0),
        (a2, "logloss_blanda", lambda v: f"{v:.4f}".replace(".", ","), "log-loss blanda (menos es mejor)", 1.6)]:
        for yi, mo in enumerate(modes):
            v = res[mo][key]
            ax.barh(yi, v, color=MCOL[mo], height=0.55)
            ax.text(v + xmax * 0.01, yi, fmt(v), va="center", fontsize=9.5, color=MF.INK, fontweight="bold")
        ax.set_yticks(range(len(modes)), [names[m] for m in modes], fontsize=8.8)
        ax.set_xlim(0, xmax * 1.12)
        ax.set_xlabel(xl)
        if key == "acierto":
            ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    n = res["vintage"]["n"]
    fig.suptitle(f"El arnés tendrá que batir a la persistencia de su mismo modo: con los datos tal como se "
                 f"publicaron acierta menos ({res['vintage']['acierto']:.1%} frente a {res['latest_truncated']['acierto']:.1%})"
                 .replace(".", ",").replace("%", " %"), x=0.01, ha="left", fontsize=11.5, fontweight="bold", y=1.04)
    fig.text(0.01, 0.96, f"Persistencia point-in-time (etiqueta de t−5 recalculada con lo publicado en t), "
                         f"{n} meses comunes {res['vintage']['desde']} → {res['vintage']['hasta']}. "
                         "Nada del periodo bloqueado (2005 →).", fontsize=9, color=MF.MUTED, ha="left")
    MF.footer(fig, f"data/archive/features/baseline_persistence_v{PIT_VERSION}_{{vintage,latest_truncated}}.parquet y "
                   "data/archive/labels/regime_us_v1.1.parquet, ambos recortados a ≤ 2004-12; recálculo del Reportero, "
                   f"igual al meta (pit_us_v{PIT_VERSION}.meta.json → baseline) y a docs/validation/2026-10-16_pit_base_v0.3.md §1.")
    MF.save(fig, "13_pit_liston_modos.png")


def run(cifras: dict) -> None:
    meta = load_meta()
    cifras["pit_base"] = {"version": meta["version"], "grid": meta["grid"], "sustituye_a": meta["sustituye_a"],
                          "meta_estado": meta["instantanea_entradas"].get("frozen") or "candidata (meta sin regenerar; "
                          "congelada en FROZEN de src/features/pit.py, tag pit-v0.3)",
                          "filas": meta["files"][f"pit_us_v{PIT_VERSION}_vintage.parquet"]["rows"]}
    fig_cobertura_pit(meta, cifras)
    fig_retardos(cifras)
    fig_liston_modos(meta, cifras)


def main():
    path = MF.OUT / "cifras.json"
    cifras = json.loads(path.read_text()) if path.exists() else {}
    run(cifras)
    path.write_text(json.dumps(cifras, ensure_ascii=False, indent=1, default=str))
    print("escrito", path)


if __name__ == "__main__":
    main()
