"""Tabla «Competición» del panel (pestaña «Mi cartera»; docs/factors/C1_claude_gestor_spec.md v1.0 §4).

Compara, desde el inicio común de cada bloque, B0, B1 y B1′ (paper teórico mensual), las tres cuentas Alpaca que
gestiona el agente desde el 20-nov-2026 (C1 libre, M1 macro y A1 selección de acciones) y los teóricos diarios: D1
(solo papel), la sombra de M1 (docs/factors/M1_cartera_macro_spec.md §4-§5) y la de A1
(docs/factors/A1_seleccion_acciones_spec.md §4): rentabilidad, volatilidad, Sharpe, caída máxima, rotación,
costes y número de operaciones (y, en C1 y M1, el coste de `claude -p`); debajo, el «uso de modelos» de M1. Solo lee: el signal semanal (valoración teórica de src/paper/informe.py), los registros
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
LOG_M1 = REPO / "research" / "paper" / "decisiones_m1.jsonl"
LOG_M1_SOMBRA = REPO / "research" / "paper" / "decisiones_m1_sombra.jsonl"
LOG_A1 = REPO / "research" / "paper" / "decisiones_a1.jsonl"
LOG_A1_SOMBRA = REPO / "research" / "paper" / "decisiones_a1_sombra.jsonl"
MAPEO_D1 = REPO / "config" / "alpaca_etfs_d1.json"
AVISO = ("Meses de datos no distinguen habilidad de suerte: hacen falta años (docs/factors/paper_trading.md §5). "
         "Esta tabla sirve para seguir la ejecución, no para elegir ganador.")
TEORICOS = [("b0", "B0 · estática 70/15/15"), ("b1", "B1 · ajuste por volatilidad"), ("b1p", "B1′ · HAR diario")]
# 20-nov-2026: las tres cuentas paper las gestiona el agente; B0/B1/B1′/D1 quedan solo en papel (sin espejo)
CUENTAS = [("C1", "C1 · Claude gestor libre (…4JGR)"), ("M1", "M1 · Claude gestor macro (…ZFJX)"),
           ("A1", "A1 · Claude selección de acciones (…X9F9)")]
GESTORES = ("C1", "M1", "A1")
SOMBRA = [("D1T", "D1 · tendencia diaria (teórico, solo papel)"), ("M1S", "M1 · sombra teórica (regla 0.1)"),
          ("A1S", "A1 · sombra teórica (20 de mayor calidad XBRL)")]
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
    """Cuenta paper de cada cartera gestionada (C1, M1, A1), por el nombre de su perfil. Desde el 20-nov-2026 no hay
    cuentas de B0/B1/B1′/D1 (solo papel): un perfil antiguo (por defecto, D1…) no se asocia a ninguna cartera."""
    out: dict[str, A.Cliente] = {}
    for p in A.perfiles():
        if p not in GESTORES:
            continue
        c = A.cliente(p)
        if c is not None and c.cred.cartera in (None, p):
            out[p] = c
    return out


def fila_sombra(reg: list[dict], desde: str | None) -> dict | None:
    """Fila de la sombra teórica de M1 (research/paper/decisiones_m1_sombra.jsonl): la serie es la valoración que guarda
    cada línea (valor al último cierre completo); rotación y costes, los acumulados de la última línea."""
    pts = {}
    for r in reg:
        v = r.get("valoracion") or {}
        if v.get("hasta") and v.get("valor"):
            pts[v["hasta"]] = float(v["valor"])
    if len(pts) < 2:
        return None
    s = pd.Series(pts).sort_index()
    s.index = pd.to_datetime(s.index)
    if desde:
        s = s[s.index >= pd.Timestamp(desde)]
    m = metricas_serie(s)
    if m["n"] < 2:
        return None
    ult = (reg[-1].get("valoracion") or {})
    return {"desde": str(s.index[0].date()), "hasta": str(s.index[-1].date()), "rent": m["rent"], "vol": m["vol"],
            "sharpe": m["sharpe"], "caida": m["caida"], "rotacion": ult.get("rotacion"), "costes": ult.get("costes"),
            "operaciones": ult.get("rebalanceos"), "coste_claude_usd": None, "periodos": m["n"]}


def fila_d1_teorica(reg_d1: list[dict], desde: str | None, precios: pd.DataFrame | None = None) -> dict | None:
    """D1 en PAPEL: valor teórico de los pesos registrados (research/paper/decisiones_d1.jsonl; cada decisión rige
    desde el cierre de su sesión) con los cierres ajustados del archivo (sin red) y 5 pb por unidad operada
    (src/paper/m1_sombra.valorar). Sin cierres → sin datos."""
    from src.paper import m1_sombra as S
    if not reg_d1:
        return None
    etf = {k: v["etf"] for k, v in json.loads(MAPEO_D1.read_text(encoding="utf-8"))["tramos"].items()}
    lineas = []
    for r in reg_d1:
        w = {etf[k]: float(v) for k, v in (r.get("d1") or {}).items() if k in etf and float(v) > 0}
        w["efectivo"] = max(0.0, 1 - sum(w.values()))
        lineas.append({"fecha": r["cierre"], "objetivo": {"pesos": w}})
    if precios is None:
        try:
            precios, _ = S.cierres(sorted(etf.values()), dt.date.fromisoformat(lineas[0]["fecha"]) - dt.timedelta(days=5),
                                   dt.date.today(), None, yahoo=False)
        except Exception:  # noqa: BLE001
            return None
    v = S.valorar(lineas, precios)
    serie = pd.Series(v.get("serie") or {}, dtype=float)
    if len(serie) < 2:
        return None
    serie.index = pd.to_datetime(serie.index)
    if desde:
        serie = serie[serie.index >= pd.Timestamp(desde)]
    m = metricas_serie(serie)
    if m["n"] < 2:
        return None
    return {"desde": str(serie.index[0].date()), "hasta": str(serie.index[-1].date()), "rent": m["rent"], "vol": m["vol"],
            "sharpe": m["sharpe"], "caida": m["caida"], "rotacion": v.get("rotacion"), "costes": v.get("costes"),
            "operaciones": v.get("rebalanceos"), "coste_claude_usd": None, "periodos": m["n"]}


def uso_modelos(reg_m1: list[dict], serie: pd.Series | None = None) -> list[dict]:
    """Spec M1 §5 (descriptivo): por modelo, % de días en que M1 le hizo caso (declaración «si» o «parcial»), nº de
    órdenes que lo citan y rentabilidad media de la cuenta en la sesión siguiente a los días con órdenes que lo citan."""
    from src.broker import m1_guardia as MG
    dias = [r for r in reg_m1 if not r.get("ensayo") and (r.get("uso_modelos") or {}).get("declaracion")]
    sig = None
    if serie is not None and len(serie) > 1:
        sig = serie.sort_index().pct_change().shift(-1)
    out = []
    for m in MG.MODELOS:
        caso = [(r.get("uso_modelos") or {}).get("declaracion", {}).get(m) for r in dias]
        con = [r for r in dias if any(m in (o.get("modelos") or []) for o in (r.get("uso_modelos") or {}).get("citas_ordenes") or [])]
        n_ord = sum(sum(1 for o in (r.get("uso_modelos") or {}).get("citas_ordenes") or [] if m in (o.get("modelos") or []))
                    for r in dias)
        rent = None
        if sig is not None and con:
            xs = [sig.get(pd.Timestamp(r["fecha"])) for r in con]
            xs = [float(x) for x in xs if x is not None and math.isfinite(float(x))]
            rent = float(np.mean(xs)) if xs else None
        out.append({"modelo": m, "dias": len(dias),
                    "pct_caso": (sum(c in ("si", "parcial") for c in caso) / len(dias)) if dias else None,
                    "pct_no": (sum(c == "no" for c in caso) / len(dias)) if dias else None,
                    "ordenes": n_ord, "dias_con_ordenes": len(con), "rent_sesion_siguiente": rent})
    return out


def recoger(s: dict | None, *, con_alpaca: bool | None = None, log_c1: Path = LOG_C1, log_d1: Path = LOG_D1,
            espejo: list[dict] | None = None, series: dict[str, pd.Series] | None = None,
            log_m1: Path = LOG_M1, log_m1_sombra: Path = LOG_M1_SOMBRA, log_a1: Path = LOG_A1,
            log_a1_sombra: Path = LOG_A1_SOMBRA, precios_d1: pd.DataFrame | None = None) -> dict:
    """{'teoricos': {k: fila|None}, 'cuentas': {k: fila|None}, 'inicio_teorico', 'inicio_cuentas', 'notas',
    'uso_modelos'}."""
    notas = []
    val = ((s or {}).get("paper") or {}).get("valoracion") or {}
    teo = {k: fila_teorica(val.get(k)) for k, _ in TEORICOS}
    con_alpaca = (os.environ.get("FIN_PANEL_SIN_ALPACA") != "1") if con_alpaca is None else con_alpaca
    reg_c1, reg_d1, reg_m1, reg_s = _jsonl(log_c1), _jsonl(log_d1), _jsonl(log_m1), _jsonl(log_m1_sombra)
    reg_a1, reg_as = _jsonl(log_a1), _jsonl(log_a1_sombra)
    # espejo.jsonl ya no alimenta la tabla (sin espejo desde el 20-nov); se mantiene el parámetro por compatibilidad
    regs = {"C1": reg_c1, "M1": reg_m1, "A1": reg_a1}
    inicios = {k: inicio_registro([r for r in reg if not r.get("ensayo")]) for k, reg in regs.items()}
    ej = {k: ejecuciones_c1(reg) for k, reg in regs.items()}
    coste = {k: (sum(float((r.get("claude") or {}).get("coste_usd") or 0) for r in reg) if reg else None)
             for k, reg in regs.items()}
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
                               coste.get(k)) if inicios.get(k) else None) for k, _ in CUENTAS}
    cuentas["M1S"] = fila_sombra(reg_s, inicio_c)
    cuentas["A1S"] = fila_sombra(reg_as, inicio_c)
    try:
        cuentas["D1T"] = fila_d1_teorica(reg_d1, inicio_c, precios_d1)
    except Exception as e:  # noqa: BLE001 — la tabla nunca tumba el panel
        cuentas["D1T"] = None
        notas.append(f"D1 teórico: {type(e).__name__}")
    desde_t = [f["desde"] for f in teo.values() if f]
    if len(set(desde_t)) > 1:
        notas.append("Teórico: las carteras empiezan en meses distintos (B1′ se registró más tarde); "
                     "la valoración del informe mensual no se puede recortar al inicio común.")
    return {"teoricos": teo, "cuentas": cuentas, "inicio_teorico": max(desde_t) if desde_t else None,
            "inicio_cuentas": inicio_c, "notas": notas, "uso_modelos": uso_modelos(reg_m1, series.get("M1"))}


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


def html_uso_modelos(filas: list[dict]) -> str:
    cab = ["modelo", "días", "le hizo caso", "lo descartó", "órdenes que lo citan", "rent. sesión siguiente*"]
    th = "".join(f'<th scope="col">{c}</th>' for c in cab)
    tr = []
    for f in filas or []:
        tr.append("<tr>" + "".join(f"<td>{c}</td>" for c in (
            _e(f["modelo"]), str(f["dias"]), _pct(f["pct_caso"], 0).replace("+", ""), _pct(f["pct_no"], 0).replace("+", ""),
            str(f["ordenes"]), _pct(f["rent_sesion_siguiente"], 2))) + "</tr>")
    return ('<h4>M1 · uso de modelos (descriptivo; docs/factors/M1_cartera_macro_spec.md §5)</h4>'
            f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{"".join(tr)}</tbody></table></div>'
            '<p class="small">«Le hizo caso» = declaración diaria «si» o «parcial»; * rentabilidad media de la cuenta M1 '
            'en la sesión siguiente a los días con órdenes que citan ese modelo. Muchos años para concluir nada.</p>')


def html_competicion(d: dict) -> str:
    cab = ["cartera", "periodo", "rentabilidad", "volatilidad anual", "Sharpe*", "caída máx.", "rotación", "costes",
           "nº operaciones"]
    th = lambda cs: "".join(f'<th scope="col">{c}</th>' for c in cs)  # noqa: E731
    teo = ("<h4>Paper teórico (mensual, EUR, proxies; src/paper/informe.py)"
           + (f" · inicio común {_e(d['inicio_teorico'])}" if d.get("inicio_teorico") else "") + "</h4>"
           f'<div class="tw"><table><thead><tr>{th(cab)}</tr></thead><tbody>'
           + "".join(_filas(TEORICOS, d["teoricos"], False)) + "</tbody></table></div>")
    cue = ("<h4>Cuentas Alpaca PAPER gestionadas por el agente y teóricos diarios (USD)"
           + (f" · inicio común {_e(d['inicio_cuentas'])}" if d.get("inicio_cuentas") else "") + "</h4>"
           f'<div class="tw"><table><thead><tr>{th(cab + ["coste Claude"])}</tr></thead><tbody>'
           + "".join(_filas(CUENTAS + SOMBRA, d["cuentas"], True)) + "</tbody></table></div>")
    notas = "".join(f'<p class="small">{_e(n)}</p>' for n in d.get("notas") or [])
    return ('<div class="card" id="competicion"><h3>Competición</h3>'
            f'<p class="note"><strong>Aviso:</strong> {_e(AVISO)}</p>{teo}{cue}'
            '<p class="small">* Sharpe = rentabilidad media anualizada / volatilidad anualizada, sin restar el tipo sin '
            'riesgo. Rotación = valor operado / valor medio. Costes: teórico = costes fijos del backtest; Alpaca = '
            'deslizamiento frente al precio al enviar (paper: optimista). D1 (solo papel desde el 20-nov) y las sombras de M1 '
            'y A1 son TEÓRICAS (sin cuenta: cierres ajustados y 5 pb por lado; nº operaciones = reequilibrios). Los dos bloques no son comparables '
            'entre sí (moneda, instrumentos y frecuencia distintos).</p>' + html_uso_modelos(d.get("uso_modelos") or [])
            + notas + "</div>")


def sec_competicion(s: dict | None) -> str:
    return html_competicion(recoger(s))
