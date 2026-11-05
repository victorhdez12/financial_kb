"""Informe mensual del paper trading B0 / B1 / B1′ (formato fijado ANTES del primer dato:
docs/factors/paper_informe_formato.md, 5-nov-2026).

Qué mide (y nada más):
1. Valoración de las tres carteras con los proxies de docs/factors/paper_trading.md §4 en EUR (RV: French Developed
   mercado + letra, en EUR con el BCE de fin de mes; RF: Bund cupón cero 5 años, rentabilidad ≈ y_{t−1}/12 − 5·Δy; oro:
   Banco Mundial media mensual en EUR, órdenes con un mes de retraso), con las MISMAS reglas de rebalanceo, costes y TER
   que el backtest de desarrollo (`src.factors.backtest.simular`). Rentabilidad acumulada, volatilidad realizada
   anualizada, caída máxima, rotación y costes. Alarma (no cambia reglas) si alguna cae más de −30 % desde máximo.
2. Calidad de la previsión (B1′ spec §4): para cada decisión de cierre t, la varianza realizada del mes t + 1
   (suma de r² diarios del S&P 500 en EUR, como B1′) frente a la previsión de B1 (σ̂²/12) y de B1′ (f_varianza_mes):
   QLIKE = RV/f − ln(RV/f) − 1, mes a mes y su media. Descriptivo: sin potencia para ventajas de cartera.
Solo lee los registros inmutables y el warehouse; no escribe en el repositorio (no redistribuye datos de French).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.factors import backtest as BT
from src.paper import b1prima as BP

REPO = Path(__file__).resolve().parents[2]
LOG_B1 = REPO / "research/paper/decisiones.jsonl"
LOG_B1P = REPO / "research/paper/decisiones_b1prima.jsonl"
BASE = {"rv": 0.70, "rf": 0.15, "oro": 0.15}
ALARMA_CAIDA = -0.30


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def registros(log_b1: Path = LOG_B1, log_b1p: Path = LOG_B1P) -> pd.DataFrame:
    """Una fila por cierre: pesos de B0, B1, B1′ (NaN si B1′ no registró ese mes) y las previsiones."""
    filas = {}
    for r in _jsonl(log_b1):
        filas[r["cierre"]] = {"b0": r["b0"], "b1": r["b1"], "sigma_b1": r["sigma_hat"]}
    for r in _jsonl(log_b1p):
        filas.setdefault(r["cierre"], {}).update({"b1p": r["b1prima"], "sigma_b1p": r["sigma_hat_prima"],
                                                  "f_b1p": r.get("f_varianza_mes")})
    d = pd.DataFrame.from_dict(filas, orient="index")
    if d.empty:
        return d
    d.index = pd.PeriodIndex(pd.to_datetime(d.index), freq="M")
    return d.sort_index()


def rendimientos(rv_usd_pct: pd.Series, rf_usd_pct: pd.Series, usd_por_eur_d: pd.Series, bund5_pct: pd.Series,
                 oro_usd: pd.Series) -> pd.DataFrame:
    """Rendimientos mensuales en EUR por tramo (índice Period M). Funciones puras: los datos entran ya leídos."""
    per = lambda s: pd.Series(s.values, index=pd.DatetimeIndex(s.index).to_period("M"))  # noqa: E731
    eur_por_usd = 1 / usd_por_eur_d.dropna()
    fx_m = per(eur_por_usd.groupby(eur_por_usd.index.to_period("M")).last().to_timestamp())
    rv_usd = per((rv_usd_pct + rf_usd_pct) / 100)
    rv = (1 + rv_usd) * (1 + fx_m.pct_change().reindex(rv_usd.index)) - 1
    y5 = per(bund5_pct)
    rf = y5.shift(1) / 1200 - 5 * (y5 - y5.shift(1)) / 100
    oro_eur = per(oro_usd) * fx_m.reindex(per(oro_usd).index)
    oro = oro_eur.pct_change()
    return pd.DataFrame({"rv": rv, "rf": rf, "oro": oro}).dropna()


def valorar(reg: pd.DataFrame, r: pd.DataFrame) -> dict:
    """Valora B0, B1 y B1′ desde el mes siguiente al primer cierre registrado de cada una hasta el último mes con los
    tres rendimientos. Los pesos de un cierre t rigen desde t + 1 (como en desarrollo)."""
    out = {}
    for k in ("b0", "b1", "b1p"):
        if k not in reg or reg[k].dropna().empty:
            out[k] = {"nota": "sin decisiones registradas"}
            continue
        dec = reg[k].dropna()
        meses = r.index[r.index > dec.index.min()]
        if len(meses) == 0:
            out[k] = {"nota": "sin meses valorables todavía", "primer_cierre": str(dec.index.min())}
            continue
        # simular: el objetivo de la fila m es la decisión del cierre m (rige desde m + 1); el primer mes arranca con la
        # decisión del primer cierre (pesos_base)
        obj = pd.DataFrame([dec[dec.index <= m].iloc[-1] for m in meses], index=meses)[list(BT.ACTIVOS)]
        res = BT.simular(r.loc[meses], obj, pesos_base=dict(dec.iloc[0]))
        v = (1 + res.neto).cumprod()
        caida = float((v / v.cummax() - 1).min())
        out[k] = {"desde": str(meses[0]), "hasta": str(meses[-1]), "meses": int(len(meses)),
                  "rent_acumulada": float(v.iloc[-1] - 1), "vol_anual": float(res.neto.std(ddof=1) * np.sqrt(12))
                  if len(meses) > 1 else None, "caida_max": caida, "rotacion": float(res.rotacion.sum()),
                  "costes": float(res.costes.sum()), "alarma_caida_30": caida < ALARMA_CAIDA,
                  "pesos_ultimos": {a: round(float(x), 4) for a, x in res.pesos.iloc[-1].items()}}
    return out


def qlike(rv: float, f: float) -> float:
    x = rv / f
    return float(x - np.log(x) - 1)


def prevision(reg: pd.DataFrame, r_eur_d: pd.Series) -> dict:
    """QLIKE de σ̂ (B1) y σ̂′ (B1′) frente a la varianza realizada del mes siguiente (suma de r² diarios en EUR)."""
    rv = (r_eur_d ** 2).groupby(r_eur_d.index.to_period("M")).sum()
    filas = []
    for t, x in reg.iterrows():
        m = t + 1
        if m not in rv.index or m >= r_eur_d.index.max().to_period("M"):   # solo meses completos
            continue
        f1 = x.get("sigma_b1") ** 2 / 12 if pd.notna(x.get("sigma_b1")) else np.nan
        f2 = x.get("f_b1p") if pd.notna(x.get("f_b1p")) else np.nan
        filas.append({"cierre": str(t), "mes": str(m), "rv": float(rv[m]), "vol_realizada": float(np.sqrt(12 * rv[m])),
                      "sigma_b1": x.get("sigma_b1"), "sigma_b1p": x.get("sigma_b1p"),
                      "qlike_b1": qlike(rv[m], f1) if np.isfinite(f1) else None,
                      "qlike_b1p": qlike(rv[m], f2) if np.isfinite(f2) else None})
    d = pd.DataFrame(filas)
    if d.empty:
        return {"meses": [], "nota": "sin meses completos tras una decisión"}
    ambos = d.dropna(subset=["qlike_b1", "qlike_b1p"])
    return {"meses": filas, "n_comparables": int(len(ambos)),
            "qlike_medio_b1": float(ambos.qlike_b1.mean()) if len(ambos) else None,
            "qlike_medio_b1p": float(ambos.qlike_b1p.mean()) if len(ambos) else None}


def cargar(con) -> tuple[pd.DataFrame, pd.Series]:
    q = lambda sid: (lambda d: pd.Series(d.value.astype(float).values, index=pd.to_datetime(d.date)))(  # noqa: E731
        con.execute("select date, value from obs_latest where series_id = ? and value is not null order by date",
                    [sid]).df())
    fx = q("ecb_eurusd_d")
    r = rendimientos(q("ffx_dev_mkt_rf_m"), q("ffx_dev_rf_m"), fx, q("bundesbank_bund_zero_5y_m"), q("gold_wb_usd_m"))
    r_d = BP.r_eur_diario(BP.precio_a_rendimiento(q("SP500")), 1 / fx)
    return r, r_d


def informe(con, log_b1: Path = LOG_B1, log_b1p: Path = LOG_B1P) -> dict:
    reg = registros(log_b1, log_b1p)
    if reg.empty:
        return {"nota": "sin decisiones registradas"}
    r, r_d = cargar(con)
    return {"cierres": [str(x) for x in reg.index], "valoracion": valorar(reg, r), "prevision": prevision(reg, r_d),
            "ultimo_mes_valorable": str(r.index.max()), "formato": "docs/factors/paper_informe_formato.md"}


def markdown(o: dict) -> str:
    if "valoracion" not in o:
        return "### 5f. Paper trading (B0 / B1 / B1′)\n\n" + o.get("nota", "") + "\n"
    nom = {"b0": "B0 estática 70/15/15", "b1": "B1 ajuste por volatilidad", "b1p": "B1′ (HAR diario)"}
    pct = lambda x: "—" if x is None else f"{100 * x:+.2f} %"  # noqa: E731
    L = ["### 5f. Paper trading (B0 / B1 / B1′) — seguimiento, no evaluación de ventaja", "",
         f"Cierres registrados: {', '.join(o['cierres'])}. Último mes valorable: {o['ultimo_mes_valorable']} "
         "(proxies con ≈ 2 meses de retraso).", "",
         "| cartera | meses | rent. acumulada | vol. anual | caída máx. | rotación | costes | pesos | alarma −30 % |",
         "|---|---|---|---|---|---|---|---|---|"]
    for k, v in o["valoracion"].items():
        if "nota" in v:
            L.append(f"| {nom[k]} | — | {v['nota']} | | | | | | |")
            continue
        L.append(f"| {nom[k]} | {v['meses']} | {pct(v['rent_acumulada'])} | {pct(v['vol_anual'])} | "
                 f"{pct(v['caida_max'])} | {v['rotacion']:.3f} | {pct(v['costes'])} | "
                 f"{'/'.join(f'{100 * x:.0f}' for x in v['pesos_ultimos'].values())} | "
                 f"{'⚠️ sí' if v['alarma_caida_30'] else 'no'} |")
    p = o["prevision"]
    L += ["", "**Previsión de la volatilidad del mes siguiente** (QLIKE, menor es mejor; descriptivo):", ""]
    if not p.get("meses"):
        L.append(p.get("nota", ""))
    else:
        L += ["| decisión | mes | vol. realizada | σ̂ B1 | σ̂′ B1′ | QLIKE B1 | QLIKE B1′ |", "|---|---|---|---|---|---|---|"]
        f = lambda x: "—" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.3f}"  # noqa: E731
        for m in p["meses"]:
            L.append(f"| {m['cierre']} | {m['mes']} | {f(m['vol_realizada'])} | {f(m['sigma_b1'])} | "
                     f"{f(m['sigma_b1p'])} | {f(m['qlike_b1'])} | {f(m['qlike_b1p'])} |")
        L.append(f"\nMedia en {p['n_comparables']} meses comparables: B1 {f(p['qlike_medio_b1'])}, "
                 f"B1′ {f(p['qlike_medio_b1p'])}.")
    L += ["", "Sin potencia para distinguir carteras en años (docs/factors/paper_trading.md §5); esto valida la "
          "implementación y el comportamiento en vivo."]
    return "\n".join(L) + "\n"
