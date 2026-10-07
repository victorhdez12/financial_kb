"""Minimal ex-post validation of regime_monthly -> docs/phase1_validation.md.

USREC (NBER) is used here ONLY as an ex-post check; it is never an input of the classifier.
Run: .venv/bin/python -m src.regime.validate
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from src.warehouse import db

OUT = db.REPO / "docs" / "phase1_validation.md"
EPISODES = {
    "1973-74 (embargo petrolero)": ("1973-01-31", "1974-12-31"),
    "1979-80 (Volcker)": ("1979-01-31", "1980-12-31"),
    "2008 (GFC)": ("2007-07-31", "2009-06-30"),
    "2020 (COVID)": ("2020-01-31", "2020-12-31"),
    "2022 (inflación/endurecimiento)": ("2021-10-31", "2022-12-31"),
}
SHOW_COLS = ["quadrant", "G", "I_state", "core_6m", "debt_phase", "credit_light", "liquidity"]


def md_table(df: pd.DataFrame, floatfmt: str = "{:.2f}") -> str:
    def fmt(v):
        if isinstance(v, float):
            return "" if pd.isna(v) else floatfmt.format(v)
        return "" if v is None or (not isinstance(v, str) and pd.isna(v)) else str(v)
    cols = [df.index.name or ""] + list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for idx, row in df.iterrows():
        lines.append("| " + " | ".join([str(idx)] + [fmt(v) for v in row.values]) + " |")
    return "\n".join(lines)


def load() -> pd.DataFrame:
    con = db.connect()
    rm = con.execute("select * from regime_monthly order by date").df()
    usrec = db.series(con, "USREC")
    con.close()
    rm["date"] = pd.to_datetime(rm["date"])
    us = usrec.copy()
    us.index = us.index + pd.offsets.MonthEnd(0)
    rm["usrec"] = rm["date"].map(us)
    return rm.set_index("date")


def by_decade(rm: pd.DataFrame) -> pd.DataFrame:
    dec = (rm.index.year // 10 * 10).astype(str) + "s"
    t = pd.crosstab(dec, rm["quadrant"], normalize="index") * 100
    t.index.name = "década"
    return t.round(1)


def phase_by_decade(rm: pd.DataFrame) -> pd.DataFrame:
    dec = (rm.index.year // 10 * 10).astype(str) + "s"
    t = (pd.crosstab(dec, rm["debt_phase"], normalize="index") * 100).round(1)
    t.index.name = "década"
    return t


def recession_hit_rate(rm: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """% of months with G-down inside NBER recessions, in the 6m before, and in expansions."""
    rec = rm["usrec"] == 1
    gdown = rm["G_state"] == "down"
    pre6 = rm["usrec"][::-1].rolling(6, min_periods=1).max()[::-1].shift(-1).eq(1) & ~rec
    rows = {
        "en recesión NBER": gdown[rec].mean(),
        "6 meses antes de recesión": gdown[pre6].mean(),
        "expansión (resto)": gdown[~rec & ~pre6 & rm["usrec"].notna()].mean(),
        "todos los meses": gdown.mean(),
    }
    summary = pd.DataFrame({"% meses G↓": {k: round(v * 100, 1) for k, v in rows.items()}})
    summary.index.name = "periodo"
    # per recession episode
    ep = (rec != rec.shift()).cumsum()[rec]
    per = []
    for _, idx in ep.groupby(ep).groups.items():
        start, end = idx.min(), idx.max()
        window = rm.loc[start - pd.offsets.MonthEnd(3): end]
        first_down = window.index[(window["G_state"] == "down")]
        per.append({"recesión": f"{start:%Y-%m} → {end:%Y-%m}",
                    "% G↓ dentro": round(gdown.loc[start:end].mean() * 100, 1),
                    "Sahm disparada": bool(rm.loc[start:end, "sahm_trigger"].any()),
                    "crédito rojo/ámbar dentro": bool(rm.loc[start:end, "credit_light"].isin(["rojo", "ámbar"]).any()),
                    "cuadrante dominante": rm.loc[start:end, "quadrant"].mode().iat[0]
                    if rm.loc[start:end, "quadrant"].notna().any() else None})
    per_df = pd.DataFrame(per).set_index("recesión")
    return summary, per_df


def episodes(rm: pd.DataFrame) -> str:
    parts = []
    for name, (a, b) in EPISODES.items():
        sub = rm.loc[a:b, SHOW_COLS].iloc[::3].copy()
        sub.index = sub.index.strftime("%Y-%m")
        sub.index.name = "mes"
        dom = rm.loc[a:b, "quadrant"].value_counts(normalize=True).mul(100).round(0)
        parts.append(f"### {name}\n\nDistribución: " + ", ".join(f"{k} {v:.0f} %" for k, v in dom.items())
                     + "\n\n" + md_table(sub))
    return "\n\n".join(parts)


def current(rm: pd.DataFrame) -> str:
    last = rm.iloc[-6:][SHOW_COLS + ["sahm", "curve", "baa_spread", "vintage_mode"]].copy()
    last.index = last.index.strftime("%Y-%m")
    last.index.name = "mes"
    return md_table(last)


def main() -> None:
    rm = load()
    summary, per = recession_hit_rate(rm)
    vm = rm["vintage_mode"].value_counts().to_dict()
    doc = f"""# Validación Fase 1 — clasificador de régimen

Generado: {date.today()} por `src/regime/validate.py`. Muestra: {rm.index.min():%Y-%m} → {rm.index.max():%Y-%m}
({len(rm)} meses). `vintage_mode`: {vm}. USREC se usa **solo** como verificación ex post.

> Contar episodios, no meses: hay ~11 recesiones NBER en la muestra; cualquier tasa de acierto
> tiene un intervalo de confianza amplio.

## 1. Distribución de cuadrantes por década (% de meses)

{md_table(by_decade(rm), "{:.1f}")}

## 2. Crecimiento G↓ alrededor de recesiones NBER

{md_table(summary, "{:.1f}")}

### Por recesión

{md_table(per)}

## 3. Episodios clave (muestra trimestral)

{episodes(rm)}

## 4. Estado actual (últimos 6 meses)

{current(rm)}

## Notas y limitaciones

- G↑ exige G > 0 **y** ΔG(6m) > 0: por construcción G↓ es el estado por defecto (más del 50 % de los meses);
  no debe leerse como "probabilidad de recesión".
- Antes de 1957 la inflación subyacente se aproxima con el IPC general; antes de 1971 no hay NFCI y antes de
  1986 el diferencial Baa usa BAA−GS10 mensual si existe en curated/fred.
- `vintage_mode`: 'alfred' = todas las entradas de G e I salen de la vintage vigente en cada fecha; 'mixed' = solo
  algunas (ALFRED empieza en 1955 para PAYEMS, 1991 para GDPC1 y 1996 para el IPC subyacente); 'latest' = datos
  revisados actuales con retrasos de publicación. Los meses no-ALFRED tienen sesgo favorable (datos revisados).
- La regla de desapalancamiento del PLAN (NFCI > 0) marca casi todos los años 70-80 como desapalancamiento/crédito
  rojo: el NFCI está normalizado sobre toda su historia (1971+) y esa época fue estructuralmente más tensa.
  Pendiente para Fase 3: usar ANFCI o un z-score móvil del NFCI.
- Los umbrales (Sahm 0,5; core 2-2,5 %; Baa 3 pp) son los del PLAN, no están optimizados: no hay ajuste in-sample.

## Fases del ciclo de deuda corto (% de meses por década)

{md_table(phase_by_decade(rm), "{:.1f}")}
"""
    OUT.write_text(doc)
    print(f"validation -> {OUT}")
    print(summary.to_string())


if __name__ == "__main__":
    main()
