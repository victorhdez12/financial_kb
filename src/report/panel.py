"""Panel web local (uso personal): UN fichero HTML autocontenido a partir del último reporte semanal.

Fuentes (solo lectura):
- el último `obsidian/Reports/AAAA-MM-DD_signal.json` (src/report/weekly.py);
- `src/report/panel_atlas.json` (extracto versionado de docs/int/ATLAS_regimenes.md, INT-6, INT-12 e INT-14, con la
  fuente y el estado de cada cifra);
- el estado de los registros en vivo (research/int/e1_vivo.jsonl, k1_vivo.jsonl, int11_v3_1_vivo/,
  research/paper/*.jsonl) y la calibración de desarrollo de INT-11 (research/int/int11_v3_resultado.json).

Salida: `<FIN_PANEL_DIR o DATA_ROOT/panel>/index.html` y una copia fechada `panel_AAAA-MM-DD.html`.
Sin servidor, sin JS externo: CSS, JS y gráficos (SVG propio) van dentro. El resumen de arriba sale de REGLAS fijas
(sin LLM). Si falta una clave del signal, la sección dice "no disponible" y el resto se genera igual.

Uso: .venv/bin/python -m src.report.panel [--signal RUTA] [--out CARPETA]
Informativo; no es asesoramiento ni una recomendación de compra o venta.
"""
from __future__ import annotations

import argparse
import html
import json
import os
from datetime import date, datetime
from pathlib import Path

from src.report import panel_activos as PA
from src.report import panel_paises as PP
from src.report import panel_que_hacer as QH
from src.warehouse import db

REPO = db.REPO
REPORTS = REPO / "obsidian" / "Reports"
ATLAS = Path(__file__).with_name("panel_atlas.json")
INT11_RES = REPO / "research/int/int11_v3_resultado.json"
INT11_HOY = REPO / "research/int/int11_v3_hoy.json"
REG = {"e1": REPO / "research/int/e1_vivo.jsonl", "k1": REPO / "research/int/k1_vivo.jsonl",
       "int11": REPO / "research/int/int11_v3_1_vivo", "paper_b1": REPO / "research/paper/decisiones.jsonl",
       "paper_b1p": REPO / "research/paper/decisiones_b1prima.jsonl", "paper_activo": REPO / "research/paper/ACTIVO",
       "sigma_star": REPO / "research/paper/sigma_star.json",
       "b1p_congelado": REPO / "research/paper/b1prima_congelado.json"}

AVISO_GENERAL = ("Informativo y de uso personal. No es asesoramiento financiero ni una recomendación de compra o venta. "
                 "Cifras calculadas por Python con datos públicos; pueden tener errores o revisiones.")
ETIQ_VIVO = "validado solo en el pasado; en seguimiento en vivo"
NO_OOS = "no confirmado fuera de muestra"
ND = '<span class="nd">no disponible</span>'
ACTIVOS = [("bolsa", "Bolsa"), ("bonos", "Bonos"), ("letras", "Letras"), ("vivienda", "Vivienda"), ("oro", "Oro")]
# nombres llanos (12-nov): «expansión» del motor = solo «sin caída fuerte del PIB e inflación ≤ 3 %»
REGIMEN_NOMBRE = {"expansion": "expansión (sin caída del PIB, inflación ≤ 3 %)",
                  "sobrecalentamiento": "sobrecalentamiento (sin caída del PIB, inflación > 3 %)",
                  "estanflacion": "estanflación (PIB cayendo, inflación > 3 %)",
                  "crecimiento_bajo": "crecimiento bajo (PIB cayendo, inflación ≤ 3 %)"}
# cuadrante mensual de EE. UU. (src/regime/classify.QUADRANTS) → tarjetas del atlas que le corresponden
CUADRANTE_ATLAS = {"Goldilocks": ["expansion"], "Reflación": ["sobrecalentamiento", "inflacion_alta"],
                   "Estanflación": ["estanflacion", "inflacion_alta"], "Deflación/recesión": ["crecimiento_bajo"]}
INT11_ATLAS = {"expansion": ["expansion"], "sobrecalentamiento": ["sobrecalentamiento", "inflacion_alta"],
               "estanflacion": ["estanflacion", "inflacion_alta"], "crecimiento_bajo": ["crecimiento_bajo"]}
NOMBRE_PAIS = {"BEL": "Bélgica", "DEU": "Alemania", "DNK": "Dinamarca", "ESP": "España", "FIN": "Finlandia",
               "FRA": "Francia", "GBR": "Reino Unido", "ITA": "Italia", "JPN": "Japón", "NLD": "Países Bajos",
               "NOR": "Noruega", "PRT": "Portugal", "SWE": "Suecia", "USA": "EE. UU.", "AUS": "Australia",
               "CHE": "Suiza", "CAN": "Canadá", "IRL": "Irlanda"}
BANDAS_NOWCAST = [(50, "bajo"), (80, "medio"), (95, "alto")]   # = src/intl/int8b.BANDAS (percentil del índice)
PICO_VIX_PCT = 90          # regla del panel (no validada) para resaltar "picos de volatilidad"
DIAS_SIGNAL_VIEJO = 9      # el semanal sale cada domingo
DIAS_DATO_VIEJO = 150      # indicador mensual/trimestral sin actualizar en ≈ 5 meses


# ----------------------------------------------------------------------------------------------- utilidades
def esc(x) -> str:
    return html.escape(str(x), quote=True)


def g(d, *ks, default=None):
    """Acceso seguro anidado: g(s, "regime", "quadrant")."""
    for k in ks:
        if isinstance(d, dict) and k in d:
            d = d[k]
        elif isinstance(d, list) and isinstance(k, int) and -len(d) <= k < len(d):
            d = d[k]
        else:
            return default
    return d if d is not None else default


def num(v, dec: int = 1, suf: str = "", signo: bool = False) -> str:
    """Número en castellano (coma decimal, signo menos tipográfico)."""
    if v is None or isinstance(v, bool):
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return esc(v)
    if f != f:
        return "—"
    t = f"{abs(f):,.{dec}f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    s = "−" if f < 0 and round(abs(f), dec) != 0 else ("+" if signo and f > 0 else "")
    return f"{s}{t}{suf}"


def pct(p, dec: int = 0) -> str:
    return "—" if p is None else num(100 * float(p), dec, " %")


def _json(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return None


def _jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for ln in p.read_text().splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                out.append({"_error": "línea ilegible"})
    return out


def ultimo_signal(carpeta: Path = REPORTS) -> Path | None:
    xs = sorted(carpeta.glob("*_signal.json"))
    return xs[-1] if xs else None


def salida_dir() -> Path:
    return Path(os.path.expanduser(os.environ.get("FIN_PANEL_DIR", str(db.DATA_ROOT / "panel"))))


def estado_badge(e: str | None) -> str:
    e = (e or "").strip()
    if e.startswith("establecido"):
        cls, ico = ("ok", "●") if "frágil" not in e else ("warn", "◐")
    elif e.startswith("probable"):
        cls, ico = "warn", "◐"
    elif e.startswith("no establecido"):
        cls, ico = "no", "○"
    elif e.startswith("descriptivo"):
        cls, ico = "desc", "◌"
    else:
        cls, ico = "desc", "·"
    return f'<span class="badge b-{cls}"><span aria-hidden="true">{ico}</span> {esc(e or "—")}</span>'


def tabla(cab: list[str], filas: list[list[str]], cls: str = "") -> str:
    """Tabla HTML; las celdas ya vienen escapadas/formateadas."""
    th = "".join(f"<th scope=\"col\">{c}</th>" for c in cab)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in f) + "</tr>" for f in filas)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def md_html(md: str) -> str:
    """Markdown mínimo (tablas, ###, **negrita**, `código`, listas, párrafos) para incrustar la tabla 5f tal cual."""
    import re

    def inline(t: str) -> str:
        t = esc(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
        return t

    out, lineas, i = [], md.splitlines(), 0
    while i < len(lineas):
        ln = lineas[i].rstrip()
        if ln.startswith("|"):
            bloque = []
            while i < len(lineas) and lineas[i].startswith("|"):
                bloque.append([c.strip() for c in lineas[i].strip().strip("|").split("|")])
                i += 1
            cab = bloque[0]
            cuerpo = [f for f in bloque[1:] if not all(set(c) <= set("-: ") for c in f)]
            out.append(tabla([inline(c) for c in cab], [[inline(c) for c in f] for f in cuerpo]))
            continue
        if ln.startswith("#"):
            out.append(f"<h4>{inline(ln.lstrip('#').strip())}</h4>")
        elif ln.startswith("- "):
            out.append(f"<ul><li>{inline(ln[2:])}</li></ul>")
        elif ln.strip():
            out.append(f"<p>{inline(ln)}</p>")
        i += 1
    return "\n".join(out).replace("</ul>\n<ul>", "")


def seccion_segura(fn, *a) -> str:
    try:
        return fn(*a)
    except Exception as e:  # noqa: BLE001
        return f'<div class="card"><p>{ND}: error al generar esta parte ({esc(type(e).__name__)}: {esc(e)}).</p></div>'


# ----------------------------------------------------------------------------------------------- datos derivados
def acierto_int11() -> dict:
    """Acierto medido en desarrollo (fase D de v3, LOCO, ≤ 2004) de las dos probabilidades de INT-11."""
    r = _json(INT11_RES) or {}
    return {"infl5": g(r, "loco", "infl5"), "caida20": g(r, "loco", "caida20"), "fuente": "research/int/int11_v3_resultado.json (fase D, LOCO, ≤ 2004)"}


def _abanico(v):
    from src.report.weekly import abanico
    return abanico(v)


def escenarios_completos(s: dict) -> tuple[dict | None, str]:
    """Escenarios del signal; si el signal es anterior a que llevara los abanicos (p5/p50/p95), los toma de
    research/int/int11_v3_hoy.json cuando su emisión es de la misma semana. Devuelve (escenarios, nota de fuente)."""
    es = s.get("escenarios")
    if isinstance(es, dict) and "error" not in es and all("abanicos" in v for v in (es.get("paises") or {}).values()) \
            and es.get("paises"):
        return es, "signal semanal"
    h = _json(INT11_HOY)
    if not h or "paises" not in h:
        return (es if isinstance(es, dict) and "error" not in es else None), "signal semanal (sin abanicos)"
    try:
        dias = abs((date.fromisoformat(str(h.get("emision"))[:10]) - date.fromisoformat(str(s.get("asof"))[:10])).days)
    except ValueError:
        dias = 999
    if dias > 8:
        return (es if isinstance(es, dict) and "error" not in es else None), "signal semanal (sin abanicos)"
    paises = {}
    for c, r in h["paises"].items():
        q = r.get("cuantiles_1_99") or {}
        paises[c] = {k: r.get(k) for k in ("regimen_dominante", "p_caida_bolsa_20", "p_inflacion_5", "dependencia_hoy",
                                            "dependencia_por_regimen", "pesos_regimen", "cerca_umbral")}
        paises[c]["abanicos"] = {a: _abanico(v) for a, v in q.items() if len(v) == 99}
        paises[c]["estado"] = {k: (r.get("estado") or {}).get(k) for k in ("mes_ipc", "inflacion", "brecha")}
    return ({"emision": h.get("emision"), "ventana": h.get("ventana_objetivo"), "aviso": h.get("aviso"),
             "motor": h.get("version_motor") or h.get("motor"), "paises": paises,
             "dependencia_descriptiva_2004": h.get("dependencia_descriptiva_2004"),
             "acierto_medido_fase_D": h.get("acierto_medido_fase_D")},
            f"research/int/int11_v3_hoy.json (emisión {h.get('emision')}; el signal de esa semana no traía los abanicos)")


def registros(hoy: date) -> dict:
    e1, k1 = _jsonl(REG["e1"]), _jsonl(REG["k1"])
    int11 = sorted(REG["int11"].glob("*.json")) if REG["int11"].exists() else []
    b1, b1p = _jsonl(REG["paper_b1"]), _jsonl(REG["paper_b1p"])

    def ult(xs, *ks):
        for r in reversed(xs):
            for k in ks:
                if r.get(k):
                    return str(r[k])
        return None

    # próximas fechas según las reglas de los lanzadores (scripts/*.sh): día 20 (INT-11), día 3 (paper, E1, K1)
    def prox_dia(d: int) -> date:
        y, m = hoy.year, hoy.month
        if hoy.day >= d:
            m += 1
            if m == 13:
                y, m = y + 1, 1
        return date(y, m, d)

    return {
        "int11": {"n": len(int11), "ultimo": int11[-1].stem if int11 else None,
                  "proximo": f"desde el {prox_dia(20).isoformat()} (emisión mensual a partir del día 20)",
                  "que": "INT-11 v3.1: abanicos a 12 meses por país (ventanas de 12 meses; la primera cierra un año después de emitirse)"},
        "e1": {"n": len(e1), "ultimo": ult(e1, "cierre", "mes"),
               "proximo": "primer cierre registrable 2026-11-30; se registra desde el día 3 del mes siguiente"
               if not e1 else f"mensual, desde el {prox_dia(3).isoformat()}",
               "que": "P-E1 / P-E1b: P(entrada en recesión a 12 y 6 meses) con modelos congelados; veredicto con ≥ 12 episodios nuevos"},
        "k1": {"n": len(k1), "ultimo": ult(k1, "t", "año"),
               "proximo": "anual: t = 2026 cuando el BIS publique el 4.º trimestre de 2026 (≈ mediados de 2027)",
               "que": "P-K1v: P(inicio de crisis bancaria al año siguiente); veredicto con ≥ 20 inicios nuevos"},
        "paper": {"n_b1": len(b1), "n_b1p": len(b1p), "ultimo": ult(b1, "cierre"), "activo": REG["paper_activo"].exists(),
                  "proximo": f"decisión mensual desde el {prox_dia(3).isoformat()} (cierre del mes anterior)",
                  "que": "paper trading B0 / B1 / B1′: seguimiento de la implementación, sin potencia para distinguir carteras"},
        "_b1": b1, "_b1p": b1p,
    }


def avisos_datos(s: dict, hoy: date) -> list[str]:
    """Avisos de datos viejos, fuentes cortadas y partes que fallaron, leídos del signal."""
    out = []
    try:
        asof = date.fromisoformat(str(s.get("asof"))[:10])
        if (hoy - asof).days > DIAS_SIGNAL_VIEJO:
            out.append(f"El reporte semanal es del {asof.isoformat()} ({(hoy - asof).days} días): ¿falló la "
                       "actualización del domingo?")
    except ValueError:
        out.append("El signal no tiene fecha (asof) legible.")
        asof = hoy
    for k in ("termometro", "nowcast", "liquidez_credito", "paper", "escenarios"):
        v = s.get(k)
        if v is None:
            out.append(f"Sección «{k}» ausente en el signal.")
        elif isinstance(v, dict) and "error" in v:
            out.append(f"Sección «{k}» falló al generarse: {v['error']}")
    for nom, d in (g(s, "credit", "indicators", default={}) or {}).items():
        if isinstance(d, dict) and d.get("value") is None:
            out.append(f"Monitor de crédito: «{nom}» sin dato (fuente cortada o discontinuada).")
    for r in s.get("indicators") or []:
        if r.get("valor") is None:
            out.append(f"Indicador «{r.get('indicador')}» sin dato.")
            continue
        try:
            f = date.fromisoformat(str(r.get("fecha_dato"))[:10])
            if (asof - f).days > DIAS_DATO_VIEJO:
                out.append(f"Indicador «{r.get('indicador')}»: último dato del {f.isoformat()} "
                           f"({(asof - f).days} días antes del reporte).")
        except ValueError:
            pass
    for c, p in (g(s, "termometro", "paises", default={}) or {}).items():
        for a in p.get("avisos_datos") or []:
            out.append(f"Termómetro {c}: {a}")
        for a in p.get("empalmes") or []:
            out.append(f"Termómetro {c} (empalme declarado): {a}")
    lc = s.get("liquidez_credito") or {}

    def recorre(d, ruta):
        if isinstance(d, dict):
            if d.get("viejo") is True:
                out.append(f"Liquidez y crédito: «{ruta}» con dato viejo (último {d.get('fecha')}).")
            for k, v in d.items():
                recorre(v, f"{ruta}/{k}" if ruta else k)
    if "error" not in lc:
        recorre(lc, "")
    return out


# ----------------------------------------------------------------------------------------------- resumen (reglas)
def resumen(s: dict, es: dict | None) -> list[str]:
    """3-5 frases con REGLAS fijas (sin LLM): cada frase solo si están sus datos."""
    fr = []
    q = g(s, "regime", "quadrant")
    if q:
        flecha = {"up": "al alza", "down": "a la baja"}
        t = (f"EE. UU. está en **{q}** según el cuadrante mensual (crecimiento {flecha.get(g(s, 'regime', 'G_state'), '?')}, "
             f"inflación {flecha.get(g(s, 'regime', 'I_state'), '?')}; subyacente 6 m {num(g(s, 'regime', 'core_6m'), 2, ' %')})")
        q3, q6 = g(s, "changes", "3m", "quadrant"), g(s, "changes", "6m", "quadrant")
        if q3 and q3 != q:
            t += f"; hace 3 meses estaba en {q3}"
        elif q6 and q6 != q:
            t += f"; hace 6 meses estaba en {q6}"
        elif q3:
            t += "; sin cambios en 3 meses"
        fr.append(t + ".")
    dc, lc = g(s, "debt_cycle", "phase"), g(s, "long_cycle", "stage")
    if dc or lc:
        t = f"Ciclo de deuda corto: **{dc or 'no disponible'}**; ciclo largo: **{lc or 'no disponible'}**"
        flags = g(s, "long_cycle", "flags")
        if flags:
            t += f" (alertas: {flags.replace('_', ' ')})"
        fr.append(t + ".")
    nc = g(s, "nowcast", "agregado")
    if nc and nc.get("banda"):
        rec = g(s, "termometro", "en_recesion", default=[]) or []
        t = (f"Recesión: el nowcast del núcleo está en banda **{nc['banda']}** (percentil {nc.get('percentil')} frente a "
             f"1960-2004)")
        t += f"; en recesión según el fechado: {', '.join(rec)}" if rec else "; ningún país en recesión según el fechado"
        alto = nc.get("paises_alto") or []
        if alto:
            t += f"; banda alta o muy alta en {', '.join(alto)}"
        fr.append(t + ".")
    cr, liq = g(s, "credit", "light"), g(s, "liquidity", "state")
    if cr or liq:
        t = f"Crédito en **{cr or '—'}** ({g(s, 'credit', 'reds', default=0)} rojos, {g(s, 'credit', 'ambers', default=0)} ámbar) y liquidez **{liq or '—'}**"
        altos = [d.get("etiqueta") + f" (p{num(d.get('percentil'), 0)})"
                 for d in (g(s, "liquidez_credito", "credito", default={}) or {}).values()
                 if isinstance(d, dict) and (d.get("percentil") or 0) >= 80]
        if altos:
            t += f"; en lo alto de su historia: {', '.join(altos)}"
        fr.append(t + ".")
    u = g(es or {}, "paises", "USA")
    if u and g(u, "abanicos", "bolsa"):
        b = u["abanicos"]["bolsa"]
        fr.append(f"Escenario a 12 meses de EE. UU. (descriptivo): bolsa real entre {pct(b['p5'])} y {pct(b['p95'])} "
                  f"(mediana {pct(b['p50'])}), P(bolsa ≤ −20 %) {pct(g(u, 'p_caida_bolsa_20', 'p'))} y "
                  f"P(inflación > 5 %) {pct(g(u, 'p_inflacion_5', 'p'))}; {ETIQ_VIVO}.")
    elif u:
        fr.append(f"Escenario a 12 meses de EE. UU.: P(bolsa ≤ −20 %) {pct(g(u, 'p_caida_bolsa_20', 'p'))}, "
                  f"P(inflación > 5 %) {pct(g(u, 'p_inflacion_5', 'p'))}; {ETIQ_VIVO}.")
    return fr[:5]


def _md_negrita(t: str) -> str:
    import re
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(t))


# ----------------------------------------------------------------------------------------------- gráficos SVG
def svg_rangos(filas: list[dict], xmin: float, xmax: float, titulo: str, paso: float = 0.2,
               resaltar: str | None = None) -> str:
    """Gráfico de rangos horizontal: barra p5-p95, punto en p50, línea del 0. filas: {etq, p5, p50, p95, tip, id}."""
    if not filas:
        return f"<p>{ND}</p>"
    W, izq, der, alto_f, arriba = 640, 96, 52, 30, 26
    H = arriba + alto_f * len(filas) + 8
    def x(v):
        return izq + (min(max(v, xmin), xmax) - xmin) / (xmax - xmin) * (W - izq - der)
    p = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(titulo)}">']
    t = xmin
    while t <= xmax + 1e-9:
        cls = "base" if abs(t) < 1e-9 else "grid"
        p.append(f'<line class="{cls}" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{arriba - 6}" y2="{H - 6}"/>')
        p.append(f'<text class="tick" x="{x(t):.1f}" y="{arriba - 12}" text-anchor="middle">{num(100 * t, 0, " %")}</text>')
        t = round(t + paso, 6)
    for i, f in enumerate(filas):
        y = arriba + alto_f * i + alto_f / 2
        hl = " hl" if resaltar and f.get("id") == resaltar else ""
        tip = esc(f.get("tip", ""))
        did = f' data-id="{esc(f["id"])}"' if f.get("id") else ""
        p.append(f'<g class="row{hl}"{did} tabindex="0" data-tip="{tip}"><rect class="hit" x="0" y="{y - alto_f / 2:.1f}" '
                 f'width="{W}" height="{alto_f}"/>')
        p.append(f'<text class="lab" x="{izq - 10}" y="{y + 4:.1f}" text-anchor="end">{esc(f["etq"])}</text>')
        if None in (f.get("p5"), f.get("p50"), f.get("p95")):
            p.append(f'<text class="tick" x="{izq}" y="{y + 4:.1f}">no disponible</text></g>')
            continue
        x5, x50, x95 = x(f["p5"]), x(f["p50"]), x(f["p95"])
        p.append(f'<rect class="rng" x="{x5:.1f}" y="{y - 5:.1f}" width="{max(x95 - x5, 2):.1f}" height="10" rx="5"/>')
        p.append(f'<circle class="med" cx="{x50:.1f}" cy="{y:.1f}" r="5"/>')
        p.append(f'<text class="val" x="{x5 - 5:.1f}" y="{y + 4:.1f}" text-anchor="end">{pct(f["p5"])}</text>'
                 if x5 - izq > 34 else "")
        p.append(f'<text class="val" x="{x95 + 5:.1f}" y="{y + 4:.1f}">{pct(f["p95"])}</text></g>')
    p.append("</svg>")
    return "".join(p)


def svg_puntos(filas: list[dict], titulo: str, bandas=BANDAS_NOWCAST) -> str:
    """Dot plot 0-100 (percentil del nowcast) con las bandas sombreadas. filas: {etq, v, tip}."""
    W, izq, der, alto_f, arriba = 640, 96, 20, 22, 30
    H = arriba + alto_f * len(filas) + 8
    def x(v):
        return izq + v / 100 * (W - izq - der)
    p = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(titulo)}">']
    lim = [0] + [b for b, _ in bandas] + [100]
    noms = [n for _, n in bandas] + ["muy alto"]
    for i in range(len(noms)):
        p.append(f'<rect class="band band{i}" x="{x(lim[i]):.1f}" y="{arriba - 8}" width="{x(lim[i + 1]) - x(lim[i]):.1f}" '
                 f'height="{H - arriba}"/>')
        p.append(f'<text class="tick" x="{(x(lim[i]) + x(lim[i + 1])) / 2:.1f}" y="{arriba - 14}" '
                 f'text-anchor="middle">{noms[i]}</text>')
    for i, f in enumerate(filas):
        y = arriba + alto_f * i + alto_f / 2
        p.append(f'<g class="row" tabindex="0" data-tip="{esc(f.get("tip", ""))}"><rect class="hit" x="0" '
                 f'y="{y - alto_f / 2:.1f}" width="{W}" height="{alto_f}"/>')
        p.append(f'<text class="lab" x="{izq - 10}" y="{y + 4:.1f}" text-anchor="end">{esc(f["etq"])}</text>')
        if f.get("v") is None:
            p.append(f'<text class="tick" x="{izq + 4}" y="{y + 4:.1f}">sin dato</text></g>')
            continue
        p.append(f'<circle class="med" cx="{x(f["v"]):.1f}" cy="{y:.1f}" r="5"/></g>')
    p.append("</svg>")
    return "".join(p)


def barra_segmentada(pesos: dict, nombre: str) -> str:
    """Barra segmentada alta (una cartera = un todo): RV / RF / oro con su % dentro y leyenda aparte."""
    partes = [("rv", "Renta variable", "s1"), ("rf", "Renta fija", "s2"), ("oro", "Oro", "s3")]
    tot = sum(float(pesos.get(k) or 0) for k, _, _ in partes) or 1
    seg = []
    for k, etq, c in partes:
        w = float(pesos.get(k) or 0) / tot
        if w <= 0:
            continue
        lab = f"{num(100 * w, 0)} %" if w >= 0.08 else ""
        seg.append(f'<div class="seg {c}" style="flex:{w:.4f}" tabindex="0" data-tip="{esc(etq)}: {num(100 * w, 1)} %">'
                   f'<span>{lab}</span></div>')
    return (f'<div class="segbar" role="img" aria-label="{esc(nombre)}: ' +
            ", ".join(f"{etq} {num(100 * float(pesos.get(k) or 0) / tot, 0)} %" for k, etq, _ in partes) +
            f'">{"".join(seg)}</div>')


def medidor(v: float | None, umbral: float | None, etq: str) -> str:
    """σ̂ frente al umbral: pista hasta 1,6 × umbral; marca en el umbral."""
    if v is None or umbral is None:
        return f"<p>{esc(etq)}: {ND}</p>"
    top = max(umbral * 1.6, v * 1.1)
    w, u = min(v / top, 1) * 100, umbral / top * 100
    estado = "por encima del umbral: B1 recorta renta variable" if v > umbral else "por debajo del umbral: sin recorte"
    return (f'<div class="meter-wrap"><div class="meter-lab"><span>{esc(etq)}</span><strong>{num(100 * v, 1)} %</strong>'
            f'<span class="muted">umbral {num(100 * umbral, 2)} % · {estado}</span></div>'
            f'<div class="meter" role="img" aria-label="{esc(etq)} {num(100 * v, 1)} % frente a umbral {num(100 * umbral, 2)} %">'
            f'<div class="fill{" over" if v > umbral else ""}" style="width:{w:.1f}%"></div>'
            f'<div class="mark" style="left:{u:.1f}%"></div></div></div>')


# ----------------------------------------------------------------------------------------------- secciones
def sec_hoy(s: dict, es: dict | None) -> str:
    out = []
    r = s.get("regime") or {}
    # evolución del cuadrante
    pasos = [("hace 6 meses", g(s, "changes", "6m")), ("hace 3 meses", g(s, "changes", "3m")),
             ("hace 1 mes", g(s, "changes", "1m")),
             ("hoy", {"date": s.get("asof"), "quadrant": r.get("quadrant"), "G": r.get("G"),
                      "debt_phase": g(s, "debt_cycle", "phase"), "credit_light": g(s, "credit", "light"),
                      "liquidity": g(s, "liquidity", "state")})]
    chips = []
    for etq, d in pasos:
        if not d:
            chips.append(f'<li class="step"><span class="muted">{etq}</span><strong>{ND}</strong></li>')
            continue
        chips.append(f'<li class="step{" now" if etq == "hoy" else ""}"><span class="muted">{etq} · {esc(d.get("date") or "")}</span>'
                     f'<strong>{esc(d.get("quadrant") or "—")}</strong><span class="small">G {num(d.get("G"), 2)} · deuda {esc(d.get("debt_phase") or "—")}'
                     f' · crédito {esc(d.get("credit_light") or "—")} · liquidez {esc(d.get("liquidity") or "—")}</span></li>')
    out.append('<div class="card"><h3>Cuadrante de EE. UU. (mensual) y su evolución</h3>'
               '<p class="note">Informativo: la cartera operativa no usa el cuadrante (las reglas de régimen no superaron '
               'al ajuste por volatilidad, P-DEV-FACT).</p>'
               f'<ol class="steps">{"".join(chips)}</ol>' + (
                   f'<p class="small">Crecimiento G = {num(r.get("G"), 2)} z (Δ6m {num(r.get("G_d6"), 2, signo=True)}), '
                   f'Sahm {num(r.get("sahm"), 2)} pp ({"disparada" if r.get("sahm_trigger") else "no disparada"}), '
                   f'subyacente 6 m {num(r.get("core_6m"), 2, " %")}, aceleración 3 m {num(r.get("core_accel_3m"), 2, " pp", True)}.</p>'
                   if r else f"<p>{ND}</p>") + "</div>")
    # ciclos
    dc, lc = s.get("debt_cycle") or {}, s.get("long_cycle") or {}
    out.append('<div class="grid2"><div class="card"><h3>Ciclo de deuda corto</h3>' + (
        f'<p class="big">{esc(dc.get("phase"))}</p><p class="small">{esc(dc.get("reason") or "")}. Curva 10a−3m {num(dc.get("curve"), 2, " pp")}, '
        f'meses invertida {esc(dc.get("inverted_months"))}, Δ fed funds 12 m {num(dc.get("ff_d12"), 2, " pp", True)}, '
        f'tipo real {num(dc.get("real_ff"), 2, " pp")}, utilización {num(dc.get("tcu"), 1, " %")}.</p>' if dc else f"<p>{ND}</p>") +
        '</div><div class="card"><h3>Ciclo largo</h3>' + (
        f'<p class="big">{esc(lc.get("stage"))}</p><p class="small">Alertas: {esc((lc.get("flags") or "ninguna").replace("_", " "))}. '
        f'Deuda/PIB {num(lc.get("debt_gdp"), 1, " %")}, déficit/PIB {num(lc.get("deficit_gdp"), 1, " %")}, '
        f'intereses/ingresos federales {num(lc.get("fed_interest_receipts_pct"), 1, " %")}, crédito privado/PIB '
        f'{num(lc.get("private_credit_gdp"), 1, " %")}.</p>' if lc else f"<p>{ND}</p>") + "</div></div>")
    # termómetro + nowcast
    tv, nc = s.get("termometro") or {}, s.get("nowcast") or {}
    if "error" in tv or not tv.get("paises"):
        out.append(f'<div class="card"><h3>Termómetro de recesión</h3><p>{ND}{": " + esc(tv["error"]) if "error" in tv else ""}</p></div>')
    else:
        filas = []
        for c, p in tv["paises"].items():
            est = p.get("estado") or {}
            sal = p.get("salida_12m") or {}
            if est.get("en_recesion"):
                rec = f'<span class="badge b-warn"><span aria-hidden="true">▲</span> en recesión</span>'
                salida = (f'banda <strong>{esc(sal["banda"])}</strong> <span class="muted">({esc(sal.get("aviso", ""))})</span>'
                          if sal.get("banda") else esc(sal.get("motivo") or "—"))
            else:
                rec, salida = '<span class="badge b-desc"><span aria-hidden="true">·</span> no</span>', '<span class="muted">—</span>'
            ncp = g(nc, "paises", c, default={}) or {}
            nb = (f'<strong>{esc(ncp["banda"])}</strong> <span class="muted">(p{esc(ncp.get("percentil"))})</span>'
                  if ncp.get("banda") else '<span class="muted">sin dato</span>')
            filas.append([f'{esc(NOMBRE_PAIS.get(c, c))} <span class="muted">{esc(c)} · {esc(p.get("grupo", ""))}</span>',
                          rec, esc(est.get("ultimo_trimestre_pib") or "—"), salida, nb])
        out.append('<div class="card"><h3>Termómetro de recesión por país</h3>'
                   f'<p class="note">{esc(tv.get("aviso", ""))}</p><p class="note">{esc(tv.get("aviso_T2", ""))}</p>'
                   + tabla(["país", "¿en recesión? (fechado trimestral)", "último trimestre de PIB",
                            "salida en ≈ 12 meses (banda)", "nowcast (banda)"], filas) + "</div>")
    if "error" not in nc and nc.get("paises"):
        filas = []
        for c, p in nc["paises"].items():
            ind = "; ".join(f'{v.get("indicador")}: {num(v.get("valor"), 2)} (p{v.get("percentil_orientado") if v.get("percentil_orientado") is not None else "—"})'
                            for v in (p.get("indicadores") or {}).values())
            filas.append({"etq": c, "v": p.get("percentil"),
                          "tip": f'{NOMBRE_PAIS.get(c, c)}: banda {p.get("banda") or "—"}, percentil {p.get("percentil")}, '
                                 f'índice {num(p.get("indice"), 1)}. {ind}'})
        ag = nc.get("agregado") or {}
        out.append('<div class="card"><h3>Nowcast de recesión (percentil del índice frente a 1960-2004)</h3>'
                   f'<p class="note">{esc(nc.get("aviso", ""))}</p>'
                   f'<p>Agregado del núcleo: banda <strong>{esc(ag.get("banda") or "—")}</strong> (percentil {esc(ag.get("percentil"))}, '
                   f'{esc(ag.get("paises_con_dato"))} países con dato). Pasa el ratón o el foco por un país para ver sus indicadores.</p>'
                   + svg_puntos(filas, "Percentil del nowcast por país") + "</div>")
    else:
        out.append(f'<div class="card"><h3>Nowcast de recesión</h3><p>{ND}</p></div>')
    out.append(seccion_segura(sec_liquidez, s))
    # indicadores clave
    ind = s.get("indicators") or []
    if ind:
        filas = [[esc(r.get("indicador")), num(r.get("valor"), 2) + (" " + esc(r.get("unidad")) if r.get("unidad") else ""),
                  esc(r.get("fecha_dato") or "—"), num(r.get("percentil_hist"), 0), esc(r.get("desde") or "—")] for r in ind]
        out.append('<details class="card"><summary><h3>Indicadores clave de EE. UU.</h3></summary>'
                   + tabla(["indicador", "valor", "fecha del dato", "percentil histórico", "desde"], filas, "num") + "</details>")
    return "\n".join(out)


def sec_liquidez(s: dict) -> str:
    lc = s.get("liquidez_credito")
    lq = s.get("liquidity") or {}
    base = (f'<p>Estado de liquidez del reporte: <strong>{esc(lq.get("state") or "—")}</strong> (score {num(lq.get("score"), 2)}; '
            f'M2 − PIB {num(lq.get("m2_minus_gdp"), 2, " pp")}, tipo real 10a {num(lq.get("dfii10"), 2, " %")}, NFCI {num(lq.get("nfci"), 2)}).</p>'
            if lq else "")
    cr = s.get("credit") or {}
    base += (f'<p>Monitor de fractura de crédito: <strong>{esc(cr.get("light") or "—")}</strong> '
             f'({esc(cr.get("reds", 0))} rojos, {esc(cr.get("ambers", 0))} ámbar de {esc(cr.get("n", "—"))}).</p>' if cr else "")
    if not isinstance(lc, dict) or "error" in lc:
        return (f'<div class="card"><h3>Liquidez y crédito (EE. UU.)</h3>{base}<p>Detalle 5e: {ND}'
                f'{": " + esc(lc["error"]) if isinstance(lc, dict) and "error" in lc else ""}.</p></div>')
    liq = lc.get("liquidez") or {}
    tiles = []
    for etq, d, k, suf in [("Liquidez neta Fed", g(liq, "neta"), "flujo_13s", "13 sem."),
                           ("Reservas", g(liq, "reservas"), "cambio_13s", "13 sem."),
                           ("M2", g(liq, "m2"), "cambio_3m", "3 meses")]:
        if not d:
            tiles.append(f'<div class="tile"><span class="muted">{etq}</span><strong>{ND}</strong></div>')
            continue
        tiles.append(f'<div class="tile"><span class="muted">{etq} (mm USD)</span><strong>{num(d.get("valor"), 0)}</strong>'
                     f'<span class="small">{num(d.get(k), 0, signo=True)} en {suf} · dato {esc(d.get("fecha") or "—")}'
                     f'{" · <b>viejo</b>" if d.get("viejo") else ""}</span></div>')
    bolsa = lc.get("bolsa") or {}
    tiles.append(f'<div class="tile"><span class="muted">S&amp;P 500</span><strong>{num(bolsa.get("cambio_1m_pct"), 1, " %", True)}</strong>'
                 f'<span class="small">a 1 mes · {num(bolsa.get("cambio_3m_pct"), 1, " %", True)} a 3 meses</span></div>')
    filas = []
    for d in (lc.get("credito") or {}).values():
        p = d.get("percentil")
        barra = (f'<span class="pbar" role="img" aria-label="percentil {num(p, 0)}"><span style="width:{float(p):.0f}%"></span></span> '
                 f'{num(p, 0)}' if p is not None else "—")
        filas.append([esc(d.get("etiqueta")) + (f' <span class="muted">({esc(d["nota"])})</span>' if d.get("nota") else ""),
                      num(d.get("valor"), 2), num(d.get("cambio_1m"), 2, signo=True), num(d.get("cambio_3m"), 2, signo=True),
                      barra, esc(d.get("desde") or "—"), esc(d.get("fecha") or "—") + (" <b>viejo</b>" if d.get("viejo") else "")])
    dz = lc.get("diez_anos") or {}
    dzt = []
    for h, etq in (("4s", "4 semanas"), ("13s", "13 semanas")):
        a, b = g(dz, h, "real_vs_inflacion", default={}) or {}, g(dz, h, "prima_vs_expectativas", default={}) or {}
        dzt.append([etq, num(a.get("total"), 2, " pp", True), num(a.get("tipo_real"), 2, signo=True),
                    num(a.get("inflacion_implicita"), 2, signo=True), num(b.get("prima_plazo"), 2, signo=True),
                    num(b.get("expectativas"), 2, signo=True)])
    div = [d for d in lc.get("divergencias") or [] if d.get("se_da")]
    divt = ("<ul>" + "".join(f"<li>{esc(d['divergencia'])}</li>" for d in div) + "</ul>") if div else \
        "<p>Ninguna de las divergencias de la lista fija se da esta semana.</p>"
    return ('<div class="card"><h3>Liquidez y crédito (EE. UU., descriptivo)</h3>'
            f'<p class="note">{esc(lc.get("aviso", ""))}</p>{base}<div class="tiles">{"".join(tiles)}</div>'
            + tabla(["crédito y volatilidad", "nivel", "Δ 1 mes", "Δ 3 meses", "percentil en su historia", "desde", "dato"], filas, "num")
            + "<h4>Movimiento del 10 años</h4>"
            + tabla(["plazo", "Δ 10 años", "tipo real", "inflación implícita", "prima por plazo (ACM)", "expectativas (ACM)"], dzt, "num")
            + f"<h4>Divergencias (lista fija, solo signos)</h4>{divt}</div>")


def sec_escenarios(s: dict, es: dict | None, fuente: str) -> str:
    if not es or not es.get("paises"):
        err = g(s, "escenarios", "error")
        return f'<div class="card"><p>Escenarios: {ND}{": " + esc(err) if err else ""}.</p></div>'
    ac = acierto_int11()
    acf = es.get("acierto_medido_fase_D") or {}
    paises = es["paises"]
    defecto = "USA" if "USA" in paises else next(iter(paises))
    opts = "".join(f'<option value="{esc(c)}"{" selected" if c == defecto else ""}>{esc(NOMBRE_PAIS.get(c, c))} ({esc(c)})</option>'
                   for c in paises)
    v = es.get("ventana") or {}
    cab = (f'<div class="card"><p class="note">{esc(es.get("aviso") or "")}</p>'
           f'<p>Emisión {esc(es.get("emision") or "—")} · ventana {esc(v.get("desde") or "—")} → {esc(v.get("hasta") or "—")} · '
           f'motor {esc(es.get("motor") or "—")} · fuente: {esc(fuente)}.</p>'
           f'<p><span class="badge b-warn"><span aria-hidden="true">◐</span> {ETIQ_VIVO}</span> '
           f'<span class="badge b-no"><span aria-hidden="true">○</span> {NO_OOS}</span></p>'
           f'<label class="sel">País <select id="pais">{opts}</select></label></div>')
    bloques = []
    i5, c20 = ac.get("infl5") or {}, ac.get("caida20") or {}
    for c, r in paises.items():
        ab = r.get("abanicos") or {}
        accp = g(acf, "pais", c, default={}) or {}
        filas = []
        for k, etq in ACTIVOS:
            a = ab.get(k)
            if not a:
                filas.append({"etq": etq, "p5": None, "p50": None, "p95": None})
                continue
            cub = accp.get(k)
            filas.append({"etq": etq, **a, "tip": f"{etq} real 12 m: p5 {pct(a['p5'])} · p50 {pct(a['p50'])} · p95 {pct(a['p95'])}"
                          + (f" · el abanico del 90 % contuvo lo realizado el {pct(cub)} de las veces en {c} (desarrollo)" if cub else "")})
        pes = r.get("pesos_regimen") or {}
        pes_t = ", ".join(f"{REGIMEN_NOMBRE.get(k, k)} {pct(w)}" for k, w in sorted(pes.items(), key=lambda kv: -kv[1]) if w and w >= 0.005)
        est = r.get("estado") or {}
        pb, pi = r.get("p_caida_bolsa_20") or {}, r.get("p_inflacion_5") or {}

        def ic(d):
            x = d.get("ic90")
            return f"IC 90 % parámetros [{pct(x[0])}; {pct(x[1])}]" if x and d.get("ic_estimable", True) else "IC no estimable"
        cub_txt = ", ".join(f"{etq.lower()} {pct(accp.get(k))}" for k, etq in ACTIVOS if accp.get(k) is not None)
        tiles = (f'<div class="tiles">'
                 f'<div class="tile"><span class="muted">P(bolsa real ≤ −20 % en 12 meses)</span><strong>{pct(pb.get("p"))}</strong>'
                 f'<span class="small">{ic(pb)}</span><span class="small">Acierto medido (desarrollo, ≤ 2004): mejora de Brier '
                 f'{pct(c20.get("bss"), 1)} sobre la frecuencia histórica ({pct(c20.get("frecuencia"), 1)}), p = {num(c20.get("p"), 3)}: '
                 f'apenas mejor que la frecuencia.</span></div>'
                 f'<div class="tile"><span class="muted">P(inflación &gt; 5 % en 12 meses)</span><strong>{pct(pi.get("p"))}</strong>'
                 f'<span class="small">{ic(pi)}</span><span class="small">Acierto medido (desarrollo, ≤ 2004): mejora de Brier '
                 f'{pct(i5.get("bss"), 1)} sobre la frecuencia; cerca del umbral la p media fue {pct(i5.get("p_media_cerca"))} '
                 f'frente a {pct(i5.get("frec_cerca"))} realizado (sobrestima).</span></div></div>'
                 f'<p class="small"><span class="badge b-warn"><span aria-hidden="true">◐</span> {ETIQ_VIVO}</span> {NO_OOS}.</p>')
        dep = r.get("dependencia_por_regimen") or {}
        dh = r.get("dependencia_hoy") or {}
        depf = [[f"<strong>hoy</strong> (mezcla con los pesos de régimen)", num(dh.get("bolsa-bonos"), 2), num(dh.get("bonos-oro"), 2)]]
        depf += [[esc(REGIMEN_NOMBRE.get(k, k)), num(d.get("bolsa-bonos"), 2), num(d.get("bonos-oro"), 2)] for k, d in dep.items()]
        cerca = (' <span class="badge b-warn"><span aria-hidden="true">▲</span> cerca del umbral del 3 %: un dato nuevo de IPC '
                 'puede mover bastante P(inflación &gt; 5 %)</span>') if r.get("cerca_umbral") else ""
        bloques.append(
            f'<div class="pais-blk" data-pais="{esc(c)}"{"" if c == defecto else " hidden"}>'
            f'<div class="card"><h3>{esc(NOMBRE_PAIS.get(c, c))}: rentabilidad real a 12 meses (p5 · p50 · p95)</h3>'
            f'<p>Estado de partida: <strong>{esc(REGIMEN_NOMBRE.get(r.get("regimen_dominante"), r.get("regimen_dominante") or "—"))}</strong>'
            f' ({esc(pes_t or "—")}; IPC media 12 m frente a los 12 previos {pct(est.get("inflacion"), 2)} hasta {esc(str(est.get("mes_ipc") or "—")[:7])}, '
            f'brecha per cápita {pct(est.get("brecha"), 1)}).{cerca}</p>'
            + svg_rangos(filas, -0.4, 0.8, f"Abanico de {c}") +
            f'<p class="small">Barra = abanico nominal del 90 % (p5-p95); punto = mediana. Acierto medido del p5-p95 en '
            f'{esc(c)} (desarrollo, sin sus propios datos, 1876-2004): {esc(cub_txt or "no disponible")}; global '
            f'{pct(acf.get("global"), 1)}. Moneda local, real.</p></div>'
            f'<div class="card"><h3>Probabilidades de {esc(NOMBRE_PAIS.get(c, c))}</h3>{tiles}</div>'
            f'<div class="card"><h3>Dependencia entre activos por régimen ({esc(c)})</h3>'
            '<p class="note">Correlación (log) de los escenarios a 12 meses heredada de las filas ≤ 2004; no contrastada '
            '(sin potencia) y no confirmada fuera de muestra. La correlación negativa bolsa-bonos de los últimos años '
            '(época, no régimen) no la reproduce el motor.</p>'
            + tabla(["partiendo de", "bolsa-bonos", "bonos-oro"], depf, "num") + "</div></div>")
    # todos los países, bolsa
    todos = [{"etq": c, "id": c, **(r.get("abanicos") or {}).get("bolsa", {"p5": None, "p50": None, "p95": None}),
              "tip": f"{NOMBRE_PAIS.get(c, c)}: P(bolsa ≤ −20 %) {pct(g(r, 'p_caida_bolsa_20', 'p'))}, "
                     f"P(inflación > 5 %) {pct(g(r, 'p_inflacion_5', 'p'))}"} for c, r in paises.items()]
    resumen_t = [[f'{esc(NOMBRE_PAIS.get(c, c))} <span class="muted">{esc(c)}</span>',
                  esc(REGIMEN_NOMBRE.get(r.get("regimen_dominante"), r.get("regimen_dominante") or "—")),
                  pct(g(r, "abanicos", "bolsa", "p5")) + " · " + pct(g(r, "abanicos", "bolsa", "p50")) + " · " + pct(g(r, "abanicos", "bolsa", "p95")),
                  pct(g(r, "p_caida_bolsa_20", "p")), pct(g(r, "p_inflacion_5", "p"))] for c, r in paises.items()]
    dd = es.get("dependencia_descriptiva_2004") or {}
    ddt = []
    for k in ("bolsa-bonos", "bonos-oro"):
        d = dd.get(k)
        if d:
            ddt.append([esc(k), f'{esc(d.get("años", ["", ""])[0])}-{esc(d.get("años", ["", ""])[-1])}',
                        f'{num(g(d, "baja", "rho"), 2)} (n {esc(g(d, "baja", "n"))})', f'{num(g(d, "alta", "rho"), 2)} (n {esc(g(d, "alta", "n"))})',
                        f'{num(d.get("dif"), 2, signo=True)} [{num(g(d, "dif_ic90", 0), 2)}; {num(g(d, "dif_ic90", 1), 2)}]',
                        esc(d.get("paises_mismo_signo") or "—")])
    comun = ('<div class="card"><h3>Bolsa real a 12 meses en los 14 países</h3>'
             + svg_rangos(todos, -0.4, 0.8, "Bolsa real 12 meses por país", resaltar=defecto)
             + tabla(["país", "régimen de partida", "bolsa p5 · p50 · p95", "P(bolsa ≤ −20 %)", "P(inflación > 5 %)"], resumen_t, "num")
             + "</div>" + (('<div class="card"><h3>Dependencia por régimen en la historia (≤ 2004, descriptivo)</h3>'
                            + tabla(["par", "años", "ρ con inflación baja", "ρ con inflación alta", "diferencia [IC 90 %]", "países con el mismo signo"], ddt, "num")
                            + f'<p class="small">Fuente: {esc(dd.get("fuente") or "—")}. {NO_OOS}.</p></div>') if ddt else ""))
    return cab + "".join(bloques) + comun


def atlas_resaltados(s: dict, es: dict | None) -> dict[str, str]:
    """Tarjetas del atlas que aplican hoy y por qué (reglas fijas)."""
    out: dict[str, list[str]] = {}
    q = g(s, "regime", "quadrant")
    for k in CUADRANTE_ATLAS.get(q, []):
        out.setdefault(k, []).append(f"cuadrante mensual de EE. UU.: {q}")
    u = g(es or {}, "paises", "USA", default={}) or {}
    rd = u.get("regimen_dominante")
    for k in INT11_ATLAS.get(rd, []):
        w = g(u, "pesos_regimen", rd)
        out.setdefault(k, []).append(f"estado anual de EE. UU. en INT-11: {REGIMEN_NOMBRE.get(rd, rd)}" + (f" ({pct(w)})" if w else ""))
    if g(s, "regime", "sahm_trigger") or "USA" in (g(s, "termometro", "en_recesion", default=[]) or []):
        out.setdefault("recesion", []).append("EE. UU. en recesión según Sahm o el fechado")
    if g(s, "credit", "light") == "rojo":
        out.setdefault("crisis_bancaria", []).append("monitor de crédito en rojo")
    vp = g(s, "liquidez_credito", "credito", "vix", "percentil")
    if vp is not None and vp >= PICO_VIX_PCT:
        out.setdefault("volatilidad", []).append(f"VIX en el percentil {num(vp, 0)} (regla del panel, no validada)")
    return {k: "; ".join(v) for k, v in out.items()}


def sec_atlas(s: dict, es: dict | None) -> str:
    at = _json(ATLAS)
    if not at:
        return f'<div class="card"><p>Atlas: {ND}.</p></div>'
    hl = atlas_resaltados(s, es)
    leyenda = "".join(f"<li>{estado_badge(k)} {esc(v)}</li>" for k, v in at["leyenda_estado"].items())
    out = [f'<div class="card"><p>{esc(at["muestra"])}</p><p class="note">{esc(at["aviso_etiqueta"])}</p>'
           f'<ul class="legend">{leyenda}</ul>'
           + (f'<p>Hoy aplica: ' + "; ".join(f'<a href="#atlas-{esc(k)}">{esc(next((r["nombre"] for r in at["regimenes"] if r["id"] == k), k))}</a> '
                                             f'<span class="muted">({esc(v)})</span>' for k, v in hl.items()) + ".</p>" if hl else "")
           + '<p class="small">El cuadrante mensual (crecimiento e inflación de EE. UU., cambio a 6 meses) y el estado anual de '
             'INT-11 (inflación observada &gt; 3 % y brecha del PIB, el mismo eje que la versión «a tiempo» del atlas) son '
             'definiciones distintas y pueden discrepar.</p></div>']
    lado_ico = {"sufre": "▼ sufre", "gana": "▲ gana", "aguanta": "▲ aguanta", "no se sabe": "? no se sabe", "mecanismo": "· contexto"}
    for r in at["regimenes"]:
        filas = [[f'<strong>{esc(f["activo"])}</strong>', esc(lado_ico.get(f["lado"], f["lado"])), esc(f["efecto"]), esc(f["ic"]),
                  estado_badge(f["estado"]), esc(f["nota"]), f'<span class="muted">{esc(f["fuente"])}</span>'] for f in r["filas"]]
        h = hl.get(r["id"])
        out.append(f'<div class="card atlas{" hoy" if h else ""}" id="atlas-{esc(r["id"])}"><h3>{esc(r["nombre"])}'
                   + (' <span class="badge b-now">régimen de hoy</span>' if h else "") + "</h3>"
                   f'<p class="small">{esc(r["definicion"])}{" · " + esc(h) if h else ""}</p>'
                   + tabla(["activo", "", "efecto", "IC 95 % (salvo indicación)", "estado", "en una frase", "fuente"], filas) + "</div>")
    out.append('<div class="card"><h3>Lo que NO sabemos</h3><ul>' + "".join(f"<li>{esc(x)}</li>" for x in at["no_sabemos"]) + "</ul>"
               f'<p class="small">Extracto versionado: {esc(at["version"])} · {esc(", ".join(at["fuentes"].values()))}.</p></div>')
    return "\n".join(out)


def sec_cartera(s: dict, reg: dict) -> str:
    out = []
    b1 = reg["_b1"][-1] if reg["_b1"] else None
    b1p = reg["_b1p"][-1] if reg["_b1p"] else None
    ss = _json(REG["sigma_star"]) or {}
    bc = _json(REG["b1p_congelado"]) or {}
    sig_star = ss.get("sigma_star_nuevo")
    sig_star_p = g(bc, "parametros", "sigma_star_prima")
    activo = reg["paper"]["activo"]
    out.append('<div class="card"><p class="note">Paper trading (carteras ficticias): sirve para comprobar que las reglas '
               'se ejecutan bien en vivo, no para decidir cuál es mejor (sin potencia en años). No es una recomendación.</p>'
               f'<p>Estado: <strong>{"activo" if activo else "no activado"}</strong>'
               + (f' · última decisión: cierre {esc(b1.get("cierre"))} (registrada {esc(str(b1.get("registrado") or "")[:10])})' if b1 else " · sin decisiones registradas")
               + "</p></div>")
    carteras = [("B0 · estática 70/15/15", (b1 or {}).get("b0") or {"rv": 0.70, "rf": 0.15, "oro": 0.15}, "pesos fijos"),
                ("B1 · ajuste por volatilidad (σ̂ 12 meses)", (b1 or {}).get("b1"), "cambio este mes: " + ("sí" if (b1 or {}).get("cambio_b1") else "no")),
                ("B1′ · HAR diario", (b1p or {}).get("b1p") or (b1p or {}).get("pesos"), "")]
    filas = []
    for nom, p, nota in carteras:
        if not p:
            filas.append(f'<div class="cart"><div class="cart-h"><strong>{esc(nom)}</strong><span class="muted">sin decisiones registradas</span></div></div>')
            continue
        filas.append(f'<div class="cart"><div class="cart-h"><strong>{esc(nom)}</strong><span class="muted">{esc(nota)}</span></div>'
                     + barra_segmentada(p, nom) + "</div>")
    leyenda = ('<ul class="legend inline"><li><i class="sw s1"></i>Renta variable</li><li><i class="sw s2"></i>Renta fija</li>'
               '<li><i class="sw s3"></i>Oro</li></ul>')
    out.append(f'<div class="card"><h3>Pesos actuales</h3>{leyenda}{"".join(filas)}</div>')
    m = [medidor((b1 or {}).get("sigma_hat"), sig_star, "B1: σ̂ (volatilidad realizada 12 meses, RV EE. UU. en EUR)")]
    if b1p:
        sp = b1p.get("sigma_hat") or b1p.get("sigma_hat_prima")
        m.append(medidor(sp, b1p.get("sigma_star_prima") or sig_star_p, "B1′: σ̂′ (previsión HAR del mes siguiente)"))
    else:
        m.append(f'<p class="small">B1′: sin decisiones registradas todavía (umbral congelado σ*′ = {num(100 * sig_star_p, 2, " %") if sig_star_p else "—"}).</p>')
    out.append('<div class="card"><h3>Volatilidad estimada frente al umbral</h3>' + "".join(m)
               + '<p class="small">Regla: renta variable = 70 % × mín(1, σ*/σ̂), con suelo; por encima del umbral se recorta. '
                 'Umbrales: research/paper/sigma_star.json y b1prima_congelado.json.</p></div>')
    p = s.get("paper")
    if isinstance(p, dict) and "error" not in p:
        try:
            from src.paper import informe as PI
            out.append('<div class="card">' + md_html(PI.markdown(p)) + "</div>")
        except Exception as e:  # noqa: BLE001
            out.append(f'<div class="card"><p>Tabla 5f: {ND} ({esc(type(e).__name__)}).</p></div>')
    else:
        out.append(f'<div class="card"><h4>5f. Paper trading</h4><p>{ND}{": " + esc(p["error"]) if isinstance(p, dict) and "error" in p else ""}.</p></div>')
    return "\n".join(out)


def sec_estado(s: dict, reg: dict, hoy: date) -> str:
    out = []
    at = _json(ATLAS) or {}
    est = {"establecido": [], "frágil o probable": [], "no establecido": []}
    for r in at.get("regimenes", []):
        for f in r["filas"]:
            e = f["estado"]
            k = ("frágil o probable" if ("frágil" in e or e.startswith("probable")) else
                 "establecido" if e.startswith("establecido") else "no establecido" if e.startswith("no establecido") else None)
            if k:
                est[k].append(f'{r["nombre"]}: {f["activo"]} ({f["efecto"]})')
    herramientas = [
        ["Termómetro: entrada en recesión (T1)", estado_badge("no establecido"), "no superó su puerta en vivo: solo se muestran sus indicadores"],
        ["Termómetro: salida de recesión (T2)", estado_badge("establecido (frágil)"), "31 filas / 22 episodios; léase la banda"],
        ["Nowcast INT-8b", estado_badge("descriptivo"), "percentil, no probabilidad; su evaluación en vivo necesitará décadas"],
        ["Escenarios INT-11 v3.1", estado_badge("probable"), f"calibración pasada en desarrollo (contaminado); {NO_OOS}"],
        ["Liquidez y crédito 5e", estado_badge("descriptivo"), "no validado (historia corta)"],
        ["Cuadrante mensual", estado_badge("descriptivo"), "informativo; la cartera no lo usa"],
        ["B1′ (HAR diario, previsión de volatilidad)", estado_badge("establecido"), "INT-12 C1 en desarrollo; en paper trading"],
    ]
    out.append('<div class="card"><h3>Qué está validado y qué no</h3>'
               + tabla(["herramienta", "estado", "por qué"], [[esc(a), b, esc(c)] for a, b, c in herramientas])
               + "".join(f'<details><summary>{estado_badge(k if k != "frágil o probable" else "probable")} {esc(k)} en el atlas ({len(v)})</summary>'
                         f'<ul>{"".join(f"<li>{esc(x)}</li>" for x in v)}</ul></details>' for k, v in est.items())
               + "</div>")
    filas = []
    for k, nom in (("int11", "INT-11 v3.1"), ("e1", "P-E1 / P-E1b"), ("k1", "P-K1v")):
        d = reg[k]
        filas.append([esc(nom), esc(d["que"]), esc(d["n"]), esc(d["ultimo"] or "—"), esc(d["proximo"])])
    d = reg["paper"]
    filas.append(["Paper trading", esc(d["que"]), f'B1 {d["n_b1"]} · B1′ {d["n_b1p"]}', esc(d["ultimo"] or "—"), esc(d["proximo"])])
    out.append('<div class="card"><h3>Registros en vivo y próximos hitos</h3>'
               + tabla(["registro", "qué guarda", "entradas", "última", "próxima"], filas)
               + '<p class="small">Ningún registro tiene todavía una ventana cerrada: no hay acierto en vivo que enseñar. '
                 'Las fechas «próxima» salen de las reglas de los lanzadores (scripts/int11_vivo_mensual.sh, '
                 'scripts/paper_mensual.sh) y pueden retrasarse si el Mac está apagado o falta un dato.</p></div>')
    av = avisos_datos(s, hoy)
    out.append('<div class="card"><h3>Avisos de datos</h3>' + (
        "<ul class=\"avisos\">" + "".join(f'<li><span class="badge b-warn"><span aria-hidden="true">▲</span> aviso</span> {esc(a)}</li>' for a in av) + "</ul>"
        if av else "<p>Sin avisos: todas las fuentes del signal están al día.</p>") + "</div>")
    out.append(f'<div class="card"><h3>Procedencia</h3><p class="small">Signal {esc(s.get("asof") or "—")} (generado '
               f'{esc(s.get("generated_at") or "—")}, vintages: {esc(s.get("vintage_mode") or "—")}). '
               f'{esc(s.get("disclaimer") or "")}</p></div>')
    return "\n".join(out)


# ----------------------------------------------------------------------------------------------- página
CSS = """
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#6f6d68;--grid:#e1e0d9;
--axis:#c3c2b7;--border:rgba(11,11,11,.10);--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--rng:rgba(42,120,214,.35);
--good:#0ca30c;--warn:#fab219;--serious:#ec835a;--crit:#d03b3b;--band0:rgba(42,120,214,.04);--band1:rgba(42,120,214,.09);
--band2:rgba(42,120,214,.16);--band3:rgba(42,120,214,.25);--hl:rgba(42,120,214,.08);--tipbg:#0b0b0b;--tipink:#f0efec}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;
--ink:#f0efec;--ink2:#c3c2b7;--muted:#9a988f;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);--s1:#3987e5;
--s2:#d95926;--s3:#199e70;--rng:rgba(57,135,229,.45);--band0:rgba(57,135,229,.05);--band1:rgba(57,135,229,.11);
--band2:rgba(57,135,229,.19);--band3:rgba(57,135,229,.30);--hl:rgba(57,135,229,.12);--tipbg:#f0efec;--tipink:#0b0b0b}}
:root[data-theme="dark"]{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#9a988f;
--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);--s1:#3987e5;--s2:#d95926;--s3:#199e70;--rng:rgba(57,135,229,.45);
--band0:rgba(57,135,229,.05);--band1:rgba(57,135,229,.11);--band2:rgba(57,135,229,.19);--band3:rgba(57,135,229,.30);
--hl:rgba(57,135,229,.12);--tipbg:#f0efec;--tipink:#0b0b0b}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--page);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header,main,footer{max-width:1280px;margin:0 auto;padding:0 16px}
header{padding-top:20px}h1{font-size:22px;margin:0 0 4px}h2{font-size:18px;margin:24px 0 8px}h3{font-size:16px;margin:0 0 8px}
h4{font-size:14px;margin:14px 0 6px}p{margin:6px 0}a{color:var(--s1)}
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}
.disc{border-left:3px solid var(--warn);background:var(--surface);padding:8px 12px;border-radius:4px;margin:10px 0;font-size:14px}
.resumen{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin:10px 0}
.resumen ol{margin:4px 0;padding-left:20px}.resumen li{margin:4px 0}
nav.tabs{display:flex;gap:4px;overflow-x:auto;border-bottom:1px solid var(--grid);margin-top:12px;scrollbar-width:thin}
nav.tabs button{font:inherit;background:none;border:0;border-bottom:2px solid transparent;color:var(--ink2);padding:8px 10px;
cursor:pointer;white-space:nowrap}nav.tabs button[aria-selected="true"]{color:var(--ink);border-bottom-color:var(--s1);font-weight:600}
nav.tabs button:focus-visible,.row:focus-visible,.seg:focus-visible{outline:2px solid var(--s1);outline-offset:2px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px 16px;margin:12px 0}
details.card>summary{cursor:pointer;list-style:none}details.card>summary h3{display:inline}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}.grid2 .card{margin:0}
@media (max-width:700px){.grid2{grid-template-columns:1fr}}
.note{color:var(--ink2);font-size:13px}.small{font-size:13px;color:var(--ink2)}.muted{color:var(--muted);font-size:13px}
.big{font-size:20px;font-weight:600;margin:2px 0}.nd{color:var(--muted);font-style:italic}
.steps{list-style:none;display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:0;margin:8px 0}
@media (max-width:700px){.steps{grid-template-columns:1fr 1fr}}
.step{border:1px solid var(--grid);border-radius:6px;padding:8px;display:flex;flex-direction:column;gap:2px}
.step strong{font-size:16px}.step.now{border-color:var(--s1);box-shadow:inset 3px 0 0 var(--s1)}
.tw{overflow-x:auto;margin:8px 0}table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--grid);vertical-align:top}
th{color:var(--ink2);font-weight:600;white-space:nowrap}table.num td{font-variant-numeric:tabular-nums}
.badge{display:inline-flex;gap:4px;align-items:center;border-radius:999px;padding:1px 8px;font-size:12px;white-space:nowrap;
border:1px solid var(--border);color:var(--ink)}
.b-ok{box-shadow:inset 3px 0 0 var(--good)}.b-ok>span{color:var(--good)}.b-warn{box-shadow:inset 3px 0 0 var(--warn)}
.b-warn>span{color:var(--serious)}.b-no>span,.b-desc>span{color:var(--muted)}.b-now{background:var(--s1);color:#fff;border-color:transparent}
.legend{list-style:none;padding:0;margin:8px 0;display:flex;flex-direction:column;gap:4px;font-size:13px}
.legend.inline{flex-direction:row;flex-wrap:wrap;gap:14px}.sw{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.sw.s1,.seg.s1{background:var(--s1)}.sw.s2,.seg.s2{background:var(--s2)}.sw.s3,.seg.s3{background:var(--s3)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:8px 0}
.tile{border:1px solid var(--grid);border-radius:6px;padding:10px;display:flex;flex-direction:column;gap:3px}
.tile strong{font-size:24px;font-weight:600}
.chart{width:100%;height:auto;display:block;margin:6px 0;overflow:visible}
.chart .grid{stroke:var(--grid);stroke-width:1}.chart .base{stroke:var(--axis);stroke-width:1}
.chart .tick{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}.chart .lab{fill:var(--ink);font-size:12.5px}
.chart .val{fill:var(--ink2);font-size:11px;font-variant-numeric:tabular-nums}
.chart .rng{fill:var(--rng)}.chart .med{fill:var(--s1);stroke:var(--surface);stroke-width:2}
.chart .hit{fill:transparent}.chart .row:hover .hit,.chart .row:focus .hit{fill:var(--hl)}.chart .row.hl .hit{fill:var(--hl)}
.chart .row.hl .lab{font-weight:700}
.band0{fill:var(--band0)}.band1{fill:var(--band1)}.band2{fill:var(--band2)}.band3{fill:var(--band3)}
.segbar{display:flex;gap:2px;height:28px;margin:6px 0 2px}
.seg{border-radius:4px;display:flex;align-items:center;padding-left:6px;min-width:2px;color:#fff;font-size:12px;font-weight:600}
.cart{margin:10px 0}.cart-h{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap}
.meter-wrap{margin:10px 0}.meter-lab{display:flex;gap:10px;flex-wrap:wrap;align-items:baseline}
.meter{position:relative;height:10px;background:var(--band1);border-radius:5px;margin-top:6px}
.meter .fill{height:100%;background:var(--s1);border-radius:5px}.meter .fill.over{background:var(--serious)}
.meter .mark{position:absolute;top:-4px;width:2px;height:18px;background:var(--ink)}
.pbar{display:inline-block;width:60px;height:6px;background:var(--band1);border-radius:3px;vertical-align:middle}
.pbar span{display:block;height:100%;background:var(--s1);border-radius:3px}
.atlas.hoy{border-color:var(--s1);box-shadow:inset 4px 0 0 var(--s1)}
.sel select{font:inherit;margin-left:6px;padding:4px 6px;border-radius:6px;border:1px solid var(--axis);background:var(--surface);color:var(--ink)}
.avisos{padding-left:0;list-style:none}.avisos li{margin:6px 0}
#tip{position:fixed;pointer-events:none;background:var(--tipbg);color:var(--tipink);font-size:12.5px;padding:6px 8px;border-radius:6px;
max-width:320px;z-index:10;display:none;line-height:1.35}
.themebtn{font:inherit;font-size:13px;background:var(--surface);color:var(--ink);border:1px solid var(--axis);border-radius:6px;padding:4px 10px;cursor:pointer}
footer{padding:16px;color:var(--muted);font-size:12.5px}
@media print{nav.tabs,.themebtn{display:none}section[hidden]{display:block!important}}
"""

JS = """
(function(){
var tabs=[].slice.call(document.querySelectorAll('nav.tabs button')),secs=[].slice.call(document.querySelectorAll('main>section'));
function show(id){tabs.forEach(function(b){b.setAttribute('aria-selected',b.dataset.t===id?'true':'false')});
secs.forEach(function(s){s.hidden=s.id!==id});try{history.replaceState(null,'','#'+id)}catch(e){}}
tabs.forEach(function(b){b.addEventListener('click',function(){show(b.dataset.t)})});
var h=(location.hash||'').slice(1);
var dp=h&&!secs.some(function(s){return s.id===h})?document.getElementById(h):null;
if(dp&&dp.closest('main>section')){show(dp.closest('main>section').id);dp.open=true;setTimeout(function(){dp.scrollIntoView()},0)}
else{show(secs.some(function(s){return s.id===h})?h:'paises')}
document.addEventListener('click',function(e){var a=e.target.closest('a[href^="#atlas-"]');if(a){show('atlas');}});
var sel=document.getElementById('pais');
function pais(c){[].forEach.call(document.querySelectorAll('.pais-blk'),function(d){d.hidden=d.dataset.pais!==c});
[].forEach.call(document.querySelectorAll('#escenarios .row[data-id]'),function(r){r.classList.toggle('hl',r.dataset.id===c)});
try{localStorage.setItem('panel_pais',c)}catch(e){}}
if(sel){var g=null;try{g=localStorage.getItem('panel_pais')}catch(e){}
if(g&&[].some.call(sel.options,function(o){return o.value===g})){sel.value=g}pais(sel.value);
sel.addEventListener('change',function(){pais(sel.value)})}
var tip=document.getElementById('tip');
function on(e){var el=e.target.closest('[data-tip]');if(!el||!el.dataset.tip){tip.style.display='none';return}
tip.textContent=el.dataset.tip;tip.style.display='block';var r=el.getBoundingClientRect(),x=(e.clientX||r.left+20),y=(e.clientY||r.top);
var w=tip.offsetWidth;tip.style.left=Math.max(8,Math.min(x+12,innerWidth-w-8))+'px';tip.style.top=(y+16)+'px'}
document.addEventListener('mousemove',on);document.addEventListener('focusin',on);
document.addEventListener('mouseleave',function(){tip.style.display='none'});
var tb=document.getElementById('theme'),root=document.documentElement;
try{var t=localStorage.getItem('panel_tema');if(t)root.setAttribute('data-theme',t)}catch(e){}
tb.addEventListener('click',function(){var d=root.getAttribute('data-theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
var n=d==='dark'?'light':'dark';root.setAttribute('data-theme',n);try{localStorage.setItem('panel_tema',n)}catch(e){}});
})();
"""

PESTANAS = [("paises", "Países"), ("quehacer", "Qué hacer"), ("hoy", "Hoy (EE. UU. y recesión)"), ("escenarios", "Escenarios 12 meses"), ("activos", "Mis activos"), ("atlas", "Qué funciona en cada régimen"),
            ("cartera", "Mi cartera"), ("estado", "Estado y avisos")]


def construir(s: dict, hoy: date | None = None) -> str:
    """HTML completo a partir de un signal (dict). No escribe nada."""
    hoy = hoy or date.today()
    s = s if isinstance(s, dict) else {}
    try:
        es, fuente_es = escenarios_completos(s)
    except Exception:  # noqa: BLE001
        es, fuente_es = None, "no disponible"
    reg = registros(hoy)
    try:
        fr = resumen(s, es)
    except Exception:  # noqa: BLE001
        fr = []
    res = ("<ol>" + "".join(f"<li>{_md_negrita(f)}</li>" for f in fr) + "</ol>") if fr else f"<p>{ND}</p>"
    av = avisos_datos(s, hoy)
    secciones = {"quehacer": seccion_segura(QH.sec_que_hacer, s, es), "activos": seccion_segura(PA.sec_activos, s, PP.pulso_desde(s)), "paises": seccion_segura(PP.sec_paises, s, es), "hoy": seccion_segura(sec_hoy, s, es), "escenarios": seccion_segura(sec_escenarios, s, es, fuente_es),
                 "atlas": seccion_segura(sec_atlas, s, es), "cartera": seccion_segura(sec_cartera, s, reg),
                 "estado": seccion_segura(sec_estado, s, reg, hoy) + PP.glosario_html()}
    nav = "".join(f'<button type="button" role="tab" data-t="{k}" aria-controls="{k}">{esc(v)}'
                  + (f" ({len(av)})" if k == "estado" and av else "") + "</button>" for k, v in PESTANAS)
    cuerpo = "".join(f'<section id="{k}" role="tabpanel" aria-label="{esc(v)}"><h2>{esc(v)}</h2>{PP.intro(k)}{secciones[k]}</section>'
                     for k, v in PESTANAS)
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>Panel macro personal</title>
<style>{CSS}{PP.CSS}{PA.CSS}{QH.CSS}</style></head>
<body>
<header><div class="top"><div><h1>Panel macro personal</h1>
<p class="muted">Reporte semanal del {esc(s.get("asof") or "—")} · panel generado el {esc(datetime.now().strftime("%Y-%m-%d %H:%M"))}</p></div>
<button type="button" class="themebtn" id="theme" aria-label="Cambiar entre modo claro y oscuro">Claro / oscuro</button></div>
<p class="disc"><strong>No es asesoramiento.</strong> {esc(AVISO_GENERAL)} Cada probabilidad lleva su acierto medido en el pasado y está {NO_OOS}.</p>
{PP.guia()}
<div class="resumen"><h3>Resumen de la semana <span class="muted">(reglas fijas, sin IA)</span></h3>{res}
<details><summary><strong>Qué ha cambiado esta semana</strong></summary>{seccion_segura(PP.cambios_semana, s, REPORTS)}</details></div>
<nav class="tabs" role="tablist">{nav}</nav></header>
<main>{cuerpo}</main>
<footer>{esc(AVISO_GENERAL)} Generado por src/report/panel.py a partir de obsidian/Reports/{esc(s.get("asof") or "—")}_signal.json.</footer>
<div id="tip" role="tooltip"></div>
<script>{JS}{PP.JS}{PA.JS}{QH.JS}</script>
</body></html>"""


def generar(signal_path: Path | None = None, out_dir: Path | None = None, hoy: date | None = None) -> Path:
    """Escribe index.html y panel_AAAA-MM-DD.html; devuelve la ruta de index.html."""
    sp = signal_path or ultimo_signal()
    if sp is None:
        raise FileNotFoundError(f"no hay ningún *_signal.json en {REPORTS}")
    s = json.loads(Path(sp).read_text())
    doc = construir(s, hoy)
    out = Path(out_dir) if out_dir else salida_dir()
    out.mkdir(parents=True, exist_ok=True)
    idx = out / "index.html"
    idx.write_text(doc, encoding="utf-8")
    (out / f"panel_{(hoy or date.today()).isoformat()}.html").write_text(doc, encoding="utf-8")
    return idx


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Panel web local (HTML autocontenido) a partir del último signal semanal")
    ap.add_argument("--signal", type=Path, default=None, help="signal concreto (por defecto, el último de obsidian/Reports)")
    ap.add_argument("--out", type=Path, default=None, help="carpeta de salida (por defecto FIN_PANEL_DIR o DATA_ROOT/panel)")
    a = ap.parse_args(argv)
    idx = generar(a.signal, a.out)
    print(f"panel -> {idx}")


if __name__ == "__main__":
    main()
