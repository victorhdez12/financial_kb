"""Tabla «Competición» del panel (pestaña «Mi cartera»; docs/factors/C1_claude_gestor_spec.md v1.0 §4).

Compara, desde el inicio común de cada bloque, B0, B1 y B1′ (paper teórico y cuentas Alpaca), D1 y C1:
rentabilidad, volatilidad, Sharpe, caída máxima, rotación, costes y número de operaciones (y, en C1, el coste de
`claude -p`). Solo lee: el signal semanal (valoración teórica de src/paper/informe.py), los registros
(research/paper/decisiones_c1.jsonl, decisiones_d1.jsonl si existe, ~/financial_archive/alpaca/espejo.jsonl) y, si
no está apagado (`FIN_PANEL_SIN_ALPACA=1`, siempre en los tests), el historial diario de valor de cada cuenta paper.
Lo que no exista aún sale como «sin datos».

Dos bloques que NO se mezclan: el teórico es mensual, en EUR, con proxies y costes fijos; las cuentas Alpaca son
diarias, en USD, con ETFs y ejecución simulada. Sharpe = rentabilidad media anualizada / volatilidad anualizada, sin
restar el tipo sin riesgo (se declara; con meses de datos no significa nada).
"""
from __future__ import annotations

import datetime as dt
import html
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

from src.broker import alpaca as A

REPO = A.REPO
LOG_C1 = REPO / "research" / "paper" / "decisiones_c1.jsonl"
LOG_D1 = REPO / "research" / "paper" / "decisiones_d1.jsonl"
AVISO = ("Meses de datos no distinguen habilidad de suerte: hacen falta años (docs/factors/paper_trading.md §5). "
         "Esta tabla sirve para seguir la ejecución, no para elegir ganador.")
TEORICOS = [("b0", "B0 · estática 70/15/15"), ("b1", "B1 · ajuste por volatilidad"), ("b1p", "B1′ · HAR diario")]
CUENTAS = [("B0", "B0 · espejo Alpaca"), ("B1", "B1 · espejo Alpaca"), ("B1P", "B1′ · espejo Alpaca"),
           ("D1", "D1 · tendencia diaria"), ("C1", "C1 · Claude gestor")]
SD = '<span class="nd">sin datos</span>'


def _e(x) -> str:
    return html.escape("" if x is None else str(x))


def _pct(x, dec: int = 1) -> str:
    return SD if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{100 * x:+.{dec}f} %".replace(".", ",")


def _n(x, dec: int = 2) -> str:
    return SD if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{dec}f}".replace(".", ",")


def _jsonl(p: Path) -> list[dict]:
    if not Path(p).exists():
        return []
    out = []
    for x in Path(p).read_text(encoding="utf-8").splitlines():
        if not x.strip():
            continue
        try:
            out.append(json.loads(x))
        except json.JSONDecodeError:
            continue
    return out


# --------------------------------------------------------------------------- métricas
def metricas_serie(v: pd.Series, por_anio: int = 252) -> dict:
    """Rentabilidad, volatilidad, Sharpe (sin tipo sin riesgo) y caída máxima de una serie de valores."""
    v = pd.Series(v, dtype=float).dropna()
    v = v[v > 0]
    if len(v) < 2:
        return {"rent": None, "vol": None, "sharpe": None, "caida": None, "n": len(v)}
    r = v.pct_change().dropna()
    sd = float(r.std(ddof=1)) if len(r) > 1 else float("nan")
    return {"rent": float(v.iloc[-1] / v.iloc[0] - 1),
            "vol": sd * math.sqrt(por_anio) if math.isfinite(sd) else None,
            "sharpe": float(r.mean() / sd * math.sqrt(por_anio)) if math.isfinite(sd) and sd > 0 else None,
            "caida": float((v / v.cummax() - 1).min()), "n": len(v)}


def fila_teorica(v: dict | None) -> dict | None:
    """Fila del bloque teórico a partir de la valoración de src/paper/informe.py (signal["paper"]["valoracion"][k])."""
    if not v or "nota" in v or v.get("meses") is None:
        return None
    meses, rent, vol = v["meses"], v.get("rent_acumulada"), v.get("vol_anual")
    anual = (1 + rent) ** (12 / meses) - 1 if rent is not None and meses else None
    return {"desde": v.get("desde"), "hasta": v.get("hasta"), "rent": rent, "vol": vol,
            "sharpe": anual / vol if anual is not None and vol else None, "caida": v.get("caida_max"),
            "rotacion": v.get("rotacion"), "costes": v.get("costes"), "operaciones": None, "periodos": meses}


def operaciones(registro: list[dict], *, desde: str | None = None) -> dict:
    """Nº de ejecuciones con cantidad, valor operado y coste (deslizamiento vs precio al enviar, en $) de una lista de
    filas de ejecución (formato de espejo.jsonl o de decisiones_c1.jsonl)."""
    n, valor, coste = 0, 0.0, 0.0
    for e in registro:
        q = float(e.get("qty_ejecutada") or 0)
        if q <= 0:
            continue
        if desde and str(e.get("ts") or e.get("hora_ejecucion") or e.get("fecha") or "")[:10] < desde:
            continue
        val = e.get("valor_usd")
        val = float(val) if val is not None else q * float(e.get("precio_medio") or 0)
        n += 1
        valor += val
        if e.get("deslizamiento_pb_vs_ref") is not None:
            coste += val * float(e["deslizamiento_pb_vs_ref"]) / 1e4
    return {"operaciones": n, "valor_operado": valor, "coste_usd": coste}


def ejecuciones_c1(reg: list[dict]) -> list[dict]:
    out = []
    for r in reg:
        for e in (r.get("ejecuciones") or []) + (r.get("seguimiento_previo") or []):
            out.append({**e, "fecha": r.get("fecha")})
    # una orden puede aparecer en su día (parcial) y en el seguimiento del siguiente (final): la última manda
    ult = {}
    for e in out:
        ult[e.get("orden_id") or id(e)] = e
    return list(ult.values())


def inicio_registro(reg: list[dict]) -> str | None:
    for r in reg:
        for k in ("fecha", "cierre", "registrado", "ts"):
            if r.get(k):
                return str(r[k])[:10]
    return None


def fila_cuenta(serie: pd.Series | None, ops: dict, desde: str | None, coste_claude: float | None = None) -> dict | None:
    if serie is None or len(serie) == 0:
        return None
    s = serie[serie.index >= pd.Timestamp(desde)] if desde else serie
    m = metricas_serie(s)
    if m["n"] < 2:
        return None
    media = float(s.mean())
    return {"desde": str(s.index[0].date()), "hasta": str(s.index[-1].date()), "rent": m["rent"], "vol": m["vol"],
            "sharpe": m["sharpe"], "caida": m["caida"], "rotacion": ops["valor_operado"] / media if media else None,
            "costes": ops["coste_usd"] / media if media else None, "operaciones": ops["operaciones"],
            "coste_claude_usd": coste_claude, "periodos": m["n"]}


# --------------------------------------------------------------------------- datos (lectura)
def serie_historial(h: dict) -> pd.Series:
    ts, eq = h.get("timestamp") or [], h.get("equity") or []
    idx = pd.to_datetime([dt.datetime.fromtimestamp(int(t), dt.timezone.utc).date() for t in ts])
    return pd.Series([float(x) if x is not None else np.nan for x in eq], index=idx).dropna()


def clientes_por_cartera() -> dict[str, A.Cliente]:
    """Cuenta paper de cada cartera (B0, B1, B1P por su perfil o ALPACA_CARTERA; D1 y C1 por su perfil)."""
    from src.broker import espejo as E   # solo lectura
    out: dict[str, A.Cliente] = {}
    for p in A.perfiles():
        c = A.cliente(p or None)
        if c is None:
            continue
        k = E.cartera_de(c.cred) or (c.cred.perfil if c.cred.perfil in ("D1", "C1") else None)
        if k and k not in out:
            out[k] = c
    return out


def recoger(s: dict | None, *, con_alpaca: bool | None = None, log_c1: Path = LOG_C1, log_d1: Path = LOG_D1,
            espejo: list[dict] | None = None, series: dict[str, pd.Series] | None = None) -> dict:
    """{'teoricos': {k: fila|None}, 'cuentas': {k: fila|None}, 'inicio_teorico', 'inicio_cuentas', 'notas'}."""
    notas = []
    val = ((s or {}).get("paper") or {}).get("valoracion") or {}
    teo = {k: fila_teorica(val.get(k)) for k, _ in TEORICOS}
    con_alpaca = (os.environ.get("FIN_PANEL_SIN_ALPACA") != "1") if con_alpaca is None else con_alpaca
    reg_c1, reg_d1 = _jsonl(log_c1), _jsonl(log_d1)
    if espejo is None:
        try:
            from src.broker import espejo as E
            espejo = E.leer_registro()
        except Exception:  # noqa: BLE001
            espejo = []
    ej = {k: [r for r in espejo if r.get("tipo") == "ejecucion" and r.get("cartera") == k] for k in ("B0", "B1", "B1P")}
    inicios = {k: (min(str(r.get("ts"))[:10] for r in v) if v else None) for k, v in ej.items()}
    inicios["C1"] = inicio_registro([r for r in reg_c1 if not r.get("ensayo")])
    inicios["D1"] = inicio_registro(reg_d1)
    ej["C1"] = ejecuciones_c1(reg_c1)
    ej["D1"] = [e for r in reg_d1 for e in (r.get("ejecuciones") or []) if isinstance(e, dict)]
    coste_claude = sum(float((r.get("claude") or {}).get("coste_usd") or 0) for r in reg_c1) if reg_c1 else None
    if series is None:
        series = {}
        if con_alpaca:
            try:
                for k, c in clientes_por_cartera().items():
                    if inicios.get(k):
                        try:
                            series[k] = serie_historial(c.historial_cartera(desde=dt.date.fromisoformat(inicios[k])))
                        except (A.AlpacaError, ValueError) as e:
                            notas.append(f"{k}: Alpaca no responde ({type(e).__name__})")
            except Exception as e:  # noqa: BLE001 — la tabla nunca tumba el panel
                notas.append(f"Alpaca: {type(e).__name__}")
        else:
            notas.append("Cuentas Alpaca no consultadas (FIN_PANEL_SIN_ALPACA=1).")
    con_datos = [inicios[k] for k, _ in CUENTAS if inicios.get(k) and k in series and len(series[k])]
    inicio_c = max(con_datos) if con_datos else None
    cuentas = {k: (fila_cuenta(series.get(k), operaciones(ej.get(k) or [], desde=inicio_c), inicio_c,
                               coste_claude if k == "C1" else None) if inicios.get(k) else None) for k, _ in CUENTAS}
    desde_t = [f["desde"] for f in teo.values() if f]
    if len(set(desde_t)) > 1:
        notas.append("Teórico: las carteras empiezan en meses distintos (B1′ se registró más tarde); "
                     "la valoración del informe mensual no se puede recortar al inicio común.")
    return {"teoricos": teo, "cuentas": cuentas, "inicio_teorico": max(desde_t) if desde_t else None,
            "inicio_cuentas": inicio_c, "notas": notas}


# --------------------------------------------------------------------------- HTML
def _filas(defs, datos: dict, con_claude: bool) -> list[str]:
    out = []
    for k, nombre in defs:
        f = datos.get(k)
        if not f:
            out.append(f"<tr><td>{_e(nombre)}</td>" + f"<td>{SD}</td>" * (9 if con_claude else 8) + "</tr>")
            continue
        celdas = [_e(nombre), f"{_e(f['desde'])} → {_e(f['hasta'])}", _pct(f["rent"]), _pct(f["vol"]),
                  _n(f["sharpe"]), _pct(f["caida"]), _n(f["rotacion"]), _pct(f["costes"], 2),
                  SD if f.get("operaciones") is None else str(f["operaciones"])]
        if con_claude:
            celdas.append(SD if f.get("coste_claude_usd") is None else f"{f['coste_claude_usd']:.2f} $".replace(".", ","))
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in celdas) + "</tr>")
    return out


def html_competicion(d: dict) -> str:
    cab = ["cartera", "periodo", "rentabilidad", "volatilidad anual", "Sharpe*", "caída máx.", "rotación", "costes",
           "nº operaciones"]
    th = lambda cs: "".join(f'<th scope="col">{c}</th>' for c in cs)  # noqa: E731
    teo = ("<h4>Paper teórico (mensual, EUR, proxies; src/paper/informe.py)"
           + (f" · inicio común {_e(d['inicio_teorico'])}" if d.get("inicio_teorico") else "") + "</h4>"
           f'<div class="tw"><table><thead><tr>{th(cab)}</tr></thead><tbody>'
           + "".join(_filas(TEORICOS, d["teoricos"], False)) + "</tbody></table></div>")
    cue = ("<h4>Cuentas Alpaca PAPER (diario, USD, ejecución simulada)"
           + (f" · inicio común {_e(d['inicio_cuentas'])}" if d.get("inicio_cuentas") else "") + "</h4>"
           f'<div class="tw"><table><thead><tr>{th(cab + ["coste Claude"])}</tr></thead><tbody>'
           + "".join(_filas(CUENTAS, d["cuentas"], True)) + "</tbody></table></div>")
    notas = "".join(f'<p class="small">{_e(n)}</p>' for n in d.get("notas") or [])
    return ('<div class="card" id="competicion"><h3>Competición</h3>'
            f'<p class="note"><strong>Aviso:</strong> {_e(AVISO)}</p>{teo}{cue}'
            '<p class="small">* Sharpe = rentabilidad media anualizada / volatilidad anualizada, sin restar el tipo sin '
            'riesgo. Rotación = valor operado / valor medio. Costes: teórico = costes fijos del backtest; Alpaca = '
            'deslizamiento frente al precio al enviar (paper: optimista). Los dos bloques no son comparables entre sí '
            '(moneda, instrumentos y frecuencia distintos).</p>' + notas + "</div>")


def sec_competicion(s: dict | None) -> str:
    return html_competicion(recoger(s))
