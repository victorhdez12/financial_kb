"""Weekly report -> obsidian/Reports/AAAA-MM-DD_semanal.md + AAAA-MM-DD_signal.json.

Reads regime_monthly (point-in-time) from the warehouse; every number in the report comes from
Python. Run: .venv/bin/python -m src.report.weekly
"""
from __future__ import annotations

import json
from datetime import date, datetime

import numpy as np
import pandas as pd

from src.regime.credit import THRESHOLDS
from src.report.analogs import find_analogs
from src.report.narrative import reading
from src.warehouse import db

REPORTS = db.REPO / "obsidian" / "Reports"
DISCLAIMER = ("Apoyo a la decisión, no asesoramiento financiero. Cifras calculadas por Python a partir de datos "
              "públicos; pueden contener errores o revisiones. Ninguna decisión debe basarse solo en este reporte.")

# (label, regime_monthly column, unit, source feature for the observation date or None)
INDICATORS = [
    ("Compuesto de crecimiento G (z)", "G", "z", None),
    ("Producción industrial a/a", "indpro_yoy", "%", "indpro_yoy"),
    ("Nóminas no agrícolas a/a", "payems_yoy", "%", "payems_yoy"),
    ("PIB real t/t anualizado", "gdp_qoq_ann", "%", "gdp_qoq_ann"),
    ("Tasa de paro", "unrate", "%", "unrate"),
    ("Regla de Sahm", "sahm", "pp", "sahm"),
    ("IPC subyacente 6m anualizado", "core_cpi_6m", "%", "core_cpi_6m"),
    ("PCE subyacente 6m anualizado", "core_pce_6m", "%", "core_pce_6m"),
    ("PPI a/a", "ppi_yoy", "%", "ppi_yoy"),
    ("Inflación implícita 5a (T5YIE)", "t5yie", "%", "t5yie"),
    ("Fed funds", "fedfunds", "%", "fedfunds"),
    ("Tipo real fed funds", "real_ff", "pp", None),
    ("Curva 10a−3m", "curve", "pp", "t10y3m"),
    ("Tipo real 10a (DFII10)", "dfii10", "%", "dfii10"),
    ("Diferencial Baa−10a", "baa_spread", "pp", "baa10y"),
    ("HY OAS", "hy_oas", "pp", "hy_oas"),
    ("NFCI", "nfci", "índice", "nfci"),
    ("STLFSI", "stlfsi", "índice", "stlfsi"),
    ("SLOOS C&I endurecimiento neto", "sloos_ci", "%", "sloos_ci"),
    ("Morosidad total préstamos bancarios", "delinq_all", "%", "delinq_all"),
    ("VIX", "vix", "índice", "vix"),
    ("M2 a/a − PIB nominal a/a", "m2_minus_gdp", "pp", None),
    ("Liquidez neta Fed (WALCL−TGA−RRP)", "net_liquidity", "mm USD", None),
    ("Deuda pública / PIB", "debt_gdp", "%", "debt_gdp"),
    ("Utilización de capacidad", "tcu", "%", "tcu"),
]
CREDIT_LABELS = {"baa_spread": "Baa−10a", "hy_oas": "HY OAS", "nfci": "NFCI", "anfci": "ANFCI",
                 "nfci_credit": "NFCI crédito", "stlfsi": "STLFSI", "sloos_ci": "SLOOS C&I",
                 "delinq_all": "Morosidad (nivel; regla Δ12m)", "ted": "TED", "curve": "Curva 10a−3m"}
STATUS = {0: "🟢 verde", 1: "🟡 ámbar", 2: "🔴 rojo"}


def r(v, n: int = 2):
    if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v):
        return None
    return round(float(v), n)


def load() -> tuple[pd.DataFrame, dict]:
    con = db.connect()
    rm = con.execute("select * from regime_monthly order by date").df()
    meta = json.loads(con.execute("select meta_json from regime_meta").fetchone()[0])
    con.close()
    rm["date"] = pd.to_datetime(rm["date"])
    return rm, meta


def percentile(col: pd.Series) -> float | None:
    s = col.dropna()
    if len(s) < 24:
        return None
    return round(float((s <= s.iloc[-1]).mean() * 100), 0)


def indicator_rows(rm: pd.DataFrame, meta: dict) -> list[dict]:
    rows = []
    cutoff = pd.Timestamp(rm["cutoff"].iloc[-1]).date()
    for label, col, unit, feat in INDICATORS:
        if col not in rm or pd.isna(rm[col].iloc[-1]):
            continue
        src = meta["sources"].get(feat or "", {})
        rows.append({"indicador": label, "valor": r(rm[col].iloc[-1]), "unidad": unit,
                     "serie": src.get("series_id") or "derivado",
                     "fecha_dato": src.get("last_obs") or str(cutoff),
                     "percentil_hist": percentile(rm[col]),
                     "desde": f"{rm.loc[rm[col].notna(), 'date'].iloc[0]:%Y}"})
    return rows


def snapshot(row: pd.Series) -> dict:
    return {"date": f"{row['date']:%Y-%m}", "quadrant": row["quadrant"], "G": r(row["G"]),
            "I_state": row["I_state"], "debt_phase": row["debt_phase"], "credit_light": row["credit_light"],
            "liquidity": row["liquidity"]}


def credit_block(last: pd.Series) -> dict:
    ind = {}
    for k in THRESHOLDS:
        st = last.get(f"cs_{k}")
        val_col = {"delinq_all": "delinq_all"}.get(k, k)
        ind[k] = {"status": None if pd.isna(st) else STATUS[int(st)].split()[1],
                  "value": r(last.get(val_col))}
    return {"light": last["credit_light"], "reds": int(last["credit_reds"]), "ambers": int(last["credit_ambers"]),
            "n": int(last["credit_n"]), "baa_spread_pct": r(last["baa_spread_pct"], 0),
            "baa_spread_d3": r(last["baa_spread_d3"]), "hy_oas_pct": r(last["hy_oas_pct"], 0),
            "hy_oas_d3": r(last["hy_oas_d3"]), "indicators": ind}


def build_signal(rm: pd.DataFrame, meta: dict, analogs: list, analog_meta: dict) -> dict:
    last = rm.iloc[-1]
    ago = lambda k: snapshot(rm.iloc[-1 - k])  # noqa: E731
    return {
        "asof": str(pd.Timestamp(last["cutoff"]).date()), "generated_at": datetime.now().isoformat(timespec="seconds"),
        "vintage_mode": last["vintage_mode"],
        "regime": {"quadrant": last["quadrant"], "G": r(last["G"]), "G_d6": r(last["G_d6"]),
                   "G_state": last["G_state"], "I_state": last["I_state"], "core_6m": r(last["core_6m"]),
                   "core_accel_3m": r(last["core_accel_3m"]), "I_composite_z": r(last["I"]),
                   "sahm": r(last["sahm"]), "sahm_trigger": bool(last["sahm_trigger"])},
        "changes": {"1m": ago(1), "3m": ago(3), "6m": ago(6)},
        "debt_cycle": {"phase": last["debt_phase"], "reason": last["debt_phase_reason"], "curve": r(last["curve"]),
                       "inverted_months": int(last["inverted_months"]), "ff_d12": r(last["ff_d12"]),
                       "real_ff": r(last["real_ff"]), "tcu": r(last["tcu"])},
        "long_cycle": {"stage": last["long_cycle"], "flags": last["long_flags_list"],
                       "debt_gdp": r(last["debt_gdp"]), "deficit_gdp": r(last["deficit_gdp"]),
                       "fed_interest_receipts_pct": r(last["fed_interest_receipts"]),
                       "private_credit_gdp": r(last["private_credit_gdp"])},
        "liquidity": {"state": last["liquidity"], "score": r(last["liquidity_score"]),
                      "m2_minus_gdp": r(last["m2_minus_gdp"]), "net_liquidity_bn": r(last["net_liquidity"], 0),
                      "net_liq_yoy": r(last["net_liq_yoy"]), "dfii10": r(last["dfii10"]), "nfci": r(last["nfci"])},
        "credit": credit_block(last),
        "indicators": indicator_rows(rm, meta),
        "analogs": analogs, "analog_method": analog_meta,
        "disclaimer": DISCLAIMER,
    }


# ---------------------------------------------------------------- markdown
def table(rows: list[dict], cols: list[str]) -> str:
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in rows:
        out.append("| " + " | ".join("" if row.get(c) is None else str(row.get(c)) for c in cols) + " |")
    return "\n".join(out)


def md_changes(s: dict) -> str:
    now = {"date": "actual", **{k: v for k, v in snapshot_from_signal(s).items() if k != "date"}}
    rows = [now] + [{**s["changes"][k], "date": f"hace {k} ({s['changes'][k]['date']})"} for k in ("1m", "3m", "6m")]
    return table(rows, ["date", "quadrant", "G", "I_state", "debt_phase", "credit_light", "liquidity"])


def snapshot_from_signal(s: dict) -> dict:
    return {"quadrant": s["regime"]["quadrant"], "G": s["regime"]["G"], "I_state": s["regime"]["I_state"],
            "debt_phase": s["debt_cycle"]["phase"], "credit_light": s["credit"]["light"],
            "liquidity": s["liquidity"]["state"]}


def md_credit(c: dict) -> str:
    rows = [{"indicador": CREDIT_LABELS[k], "valor": v["value"],
             "estado": STATUS.get({"verde": 0, "ámbar": 1, "rojo": 2}.get(v["status"]), "sin dato"),
             "ámbar si": THRESHOLDS[k][0], "rojo si": THRESHOLDS[k][1]} for k, v in c["indicators"].items()]
    head = (f"**Semáforo global: {c['light'].upper()}** — {c['reds']} rojos, {c['ambers']} ámbar de {c['n']} "
            f"indicadores con dato. Baa−10a: percentil {c['baa_spread_pct']}, Δ3m {c['baa_spread_d3']} pp. "
            f"HY OAS: percentil {c['hy_oas_pct']} (historia corta), Δ3m {c['hy_oas_d3']} pp.\n\n"
            "Regla: ROJO si ≥ 2 rojos o 1 rojo + ≥ 2 ámbar; ÁMBAR si ≥ 1 rojo o ≥ 2 ámbar; si no, VERDE.\n\n")
    return head + table(rows, ["indicador", "valor", "estado", "ámbar si", "rojo si"])


def md_analogs(s: dict) -> str:
    if not s["analogs"]:
        return "_Sin análogos (datos insuficientes)._"
    assets = list(s["analogs"][0]["fwd_12m_pct"].keys())
    rows = []
    for a in s["analogs"]:
        row = {"fecha": a["date"], "dist.": a["distance"], "cuadrante": a["quadrant"], "ciclo deuda": a["debt_phase"],
               "crédito": a["credit_light"], "recesión NBER 12m": "sí" if a["nber_recession_next_12m"] else "no",
               "eventos cercanos (±12m)": "; ".join(a["events"]) or "—"}
        row.update({f"{k} 12m %": v for k, v in a["fwd_12m_pct"].items()})
        rows.append(row)
    cols = ["fecha", "dist.", "cuadrante", "ciclo deuda", "crédito"] + [f"{k} 12m %" for k in assets] + \
           ["recesión NBER 12m", "eventos cercanos (±12m)"]
    m = s["analog_method"]
    meds = {k: np.nanmedian([a["fwd_12m_pct"][k] if a["fwd_12m_pct"][k] is not None else np.nan
                             for a in s["analogs"]]) for k in assets}
    foot = (f"\n\nMétodo: Mahalanobis diagonal sobre {', '.join(m['dims'])}; excluye ±24 meses y 1 análogo por "
            f"episodio. Rentabilidades nominales a {m['horizon_months']} meses desde el mes del análogo; series: "
            + ", ".join(f"{k} = `{v}`" for k, v in m["return_series"].items())
            + ". Mediana: " + ", ".join(f"{k} {v:.1f} %" for k, v in meds.items() if not np.isnan(v))
            + ". Con 5 episodios esto es anecdótico, no una distribución.")
    return table(rows, cols) + foot


ARROW = {"up": "↑", "down": "↓"}


def markdown(s: dict, lectura: str, origin: str) -> str:
    r_ = dict(s["regime"])
    r_["G_state"] = "G" + ARROW.get(r_["G_state"], "?")
    r_["I_state"] = "I" + ARROW.get(r_["I_state"], "?")
    lc, lq, dc = s["long_cycle"], s["liquidity"], s["debt_cycle"]
    return f"""---
tipo: reporte_semanal
fecha: {s['asof']}
regimen: {r_['quadrant']}
ciclo_deuda: {dc['phase']}
credito: {s['credit']['light']}
liquidez: {lq['state']}
vintage_mode: {s['vintage_mode']}
---

# Reporte semanal — {s['asof']}

> [!warning] Descargo
> {DISCLAIMER}

## 1. Régimen actual

**{r_['quadrant']}** — crecimiento **{r_['G_state']}** (G = {r_['G']}, ΔG 6m = {r_['G_d6']}, Sahm = {r_['sahm']} pp,
disparada: {'sí' if r_['sahm_trigger'] else 'no'}), inflación **{r_['I_state']}** (subyacente 6m anualizada
{r_['core_6m']} %, aceleración 3m {r_['core_accel_3m']} pp; compuesto I = {r_['I_composite_z']} z).

**Ciclo de deuda corto:** {dc['phase']} ({dc['reason']}). Curva 10a−3m {dc['curve']} pp, meses invertida {dc['inverted_months']},
Δ fed funds 12m {dc['ff_d12']} pp, tipo real {dc['real_ff']} pp, TCU {dc['tcu']} %.

**Ciclo largo:** {lc['stage']} — alertas: {lc['flags'] or 'ninguna'} (deuda/PIB {lc['debt_gdp']} %, déficit/PIB
{lc['deficit_gdp']} %, intereses/ingresos federales {lc['fed_interest_receipts_pct']} %, crédito privado/PIB {lc['private_credit_gdp']} %).

### Cambio frente a 1/3/6 meses

{md_changes(s)}

## 2. Indicadores clave

{table(s['indicators'], ['indicador', 'valor', 'unidad', 'fecha_dato', 'percentil_hist', 'desde', 'serie'])}

Percentil: posición del valor actual en la historia mensual disponible (desde la columna "desde").

## 3. Monitor de fractura de crédito

{md_credit(s['credit'])}

## 4. Liquidez

Estado **{lq['state']}** (score {lq['score']} = media de z de M2−PIB, liquidez neta a/a, −DFII10, −NFCI).
M2 a/a − PIB nominal a/a: {lq['m2_minus_gdp']} pp · Liquidez neta Fed: {lq['net_liquidity_bn']} mm USD
(a/a {lq['net_liq_yoy']} %) · DFII10: {lq['dfii10']} % · NFCI: {lq['nfci']}.

## 5. Análogos históricos

{md_analogs(s)}

## 6. Lectura

_Origen: {origin}._

{lectura}

---
Señal: `{s['asof']}_signal.json` · Diario de decisiones: [[Templates/Decision]] · {DISCLAIMER}
"""


def main(today: date | None = None) -> None:
    rm, meta = load()
    con = db.connect()
    analogs, analog_meta = find_analogs(con, rm)
    con.close()
    signal = build_signal(rm, meta, analogs, analog_meta)
    lectura, origin = reading(signal)
    stamp = (today or date.today()).isoformat()
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"{stamp}_signal.json").write_text(json.dumps(signal, ensure_ascii=False, indent=2, default=str))
    (REPORTS / f"{stamp}_semanal.md").write_text(markdown(signal, lectura, origin))
    print(f"weekly -> {REPORTS / (stamp + '_semanal.md')} (lectura: {origin})")


if __name__ == "__main__":
    main()
