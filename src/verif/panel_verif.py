"""Pestaña «Verificación» del panel: predicciones pendientes, puntuación (vivo y retrospectivo separados), gráfico de
errores y monitor de correlaciones. Solo lee research/verif/resumen_v1.json y el warehouse; no escribe nada."""
from __future__ import annotations

import html
import json
from pathlib import Path

from src.verif import correlaciones as C
from src.verif import metodo as M
from src.verif import registro as R

CSS = """
.verif .chart .err-in{fill:var(--s1);stroke:var(--surface);stroke-width:1}
.verif .chart .err-out{fill:var(--serious);stroke:var(--surface);stroke-width:1}
.verif .chart .int80{fill:var(--band2)}.verif .chart .l36{fill:none;stroke:var(--s1);stroke-width:2}
.verif .chart .l12{fill:none;stroke:var(--s2);stroke-width:1.2;opacity:.75}
.verif .chart .lmot{stroke:var(--ink2);stroke-width:1.5;stroke-dasharray:5 4}
.verif .sm{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.verif .sm .card{margin:0}
"""


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def _n(v, dec=2, signo=False):
    if v is None:
        return '<span class="nd">—</span>'
    s = f"{v:+.{dec}f}" if signo else f"{v:.{dec}f}"
    return s.replace(".", ",").replace("-", "−")


def _pct(v, dec=0):
    return '<span class="nd">—</span>' if v is None else f"{100 * v:.{dec}f} %".replace(".", ",")


def _tabla(cab, filas):
    th = "".join(f'<th scope="col">{c}</th>' for c in cab)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in f) + "</tr>" for f in filas)
    return f'<div class="tw"><table class="num"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def _dec(var):
    return 0 if var == "nominas" else 2


def tabla_puntos(filas: list[dict]) -> str:
    cab = ["variable", "n", "periodos", "error medio abs. (MAE)", "MAE «último»", "MAE «media 12 m»",
           "MAE / último", "MAE / media 12 m", "gana a «último»", "cobertura del 80 %"]
    out = []
    for f in filas:
        if not f.get("n"):
            out.append([esc(f["nombre"]), "0"] + ['<span class="nd">—</span>'] * 8)
            continue
        d = _dec(f["variable"])
        rel = lambda x: (f"<strong>{_n(x)}</strong>" if x is not None and x < 1 else _n(x))  # noqa: E731
        cob = f["cobertura80"]
        cob_txt = _pct(cob) + ("" if cob is None or abs(cob - 0.8) <= 0.08 else
                               ' <span class="badge b-warn"><span aria-hidden="true">▲</span> lejos del 80 %</span>')
        out.append([esc(f["nombre"]), esc(f["n"]), f'{esc(f["desde"][:7])} → {esc(f["hasta"][:7])}',
                    f'{_n(f["mae"], d)} {esc(f["unidad"])}', _n(f["mae_ultimo"], d), _n(f["mae_media12"], d),
                    rel(f["rel_ultimo"]), rel(f["rel_media12"]), _pct(f["gana_ultimo"]), cob_txt])
    return _tabla(cab, out)


def svg_errores(regs: list[dict], var: str) -> str:
    """Errores (real − predicción) en el tiempo, con la banda del 80 % centrada en 0. Punto naranja = fuera."""
    xs = [r for r in regs if r["variable"] == var and r.get("estado") == "puntuada"]
    if not xs:
        return '<p class="nd">sin datos</p>'
    W, H, iz, de, ar, ab = 340, 170, 44, 8, 10, 22
    vals = [abs(r["error"]) for r in xs] + [abs(r["sup80"] - r["punto"]) for r in xs]
    lim = sorted(vals)[int(0.97 * (len(vals) - 1))] * 1.15 or 1
    per = [r["periodo"] for r in xs]
    n = len(xs)

    def x(i):
        return iz + (i + 0.5) / n * (W - iz - de)

    def y(v):
        v = max(-lim, min(lim, v))
        return ar + (lim - v) / (2 * lim) * (H - ar - ab)

    p = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="Errores de {esc(M.VARIABLES[var]["nombre"])}">']
    for t in (-lim / 2, lim / 2):
        p.append(f'<line class="grid" x1="{iz}" x2="{W - de}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
                 f'<text class="tick" x="{iz - 4}" y="{y(t) + 4:.1f}" text-anchor="end">{_n(t, _dec(var) if var == "nominas" else 2, True)}</text>')
    band = " ".join(f"{x(i):.1f},{y(r['sup80'] - r['punto']):.1f}" for i, r in enumerate(xs))
    band += " " + " ".join(f"{x(i):.1f},{y(r['inf80'] - r['punto']):.1f}" for i, r in reversed(list(enumerate(xs))))
    p.append(f'<polygon class="int80" points="{band}"/>')
    p.append(f'<line class="base" x1="{iz}" x2="{W - de}" y1="{y(0):.1f}" y2="{y(0):.1f}"/>')
    for i, r in enumerate(xs):
        tip = (f'{r.get("periodo_txt") or r["periodo"][:7]}: real {_n(r["real"], _dec(var))}, predicción '
               f'{_n(r["punto"], _dec(var))} [{_n(r["inf80"], _dec(var))}; {_n(r["sup80"], _dec(var))}], '
               f'error {_n(r["error"], _dec(var), True)}; «último» erraba {_n(r["err_ultimo"], _dec(var), True)}')
        cls = "err-in" if r["dentro80"] else "err-out"
        p.append(f'<g class="row" tabindex="0" data-tip="{esc(tip)}"><rect class="hit" x="{x(i) - (W - iz - de) / n / 2:.1f}" '
                 f'y="{ar}" width="{max((W - iz - de) / n, 1):.1f}" height="{H - ar - ab}"/>'
                 f'<circle class="{cls}" cx="{x(i):.1f}" cy="{y(r["error"]):.1f}" r="{2.6 if n > 60 else 4}"/></g>')
    anos = sorted({s[:4] for s in per})
    for a in anos[:: max(1, len(anos) // 4)]:
        i = next(k for k, s in enumerate(per) if s.startswith(a))
        p.append(f'<text class="tick" x="{x(i):.1f}" y="{H - 6}" text-anchor="middle">{a}</text>')
    p.append("</svg>")
    return "".join(p)


def svg_corr(serie: dict, motor_v, titulo: str) -> str:
    c36, c12 = serie.get("c36") or [], serie.get("c12") or []
    if not c36:
        return '<p class="nd">sin datos</p>'
    meses = sorted({m for m, _ in c36} | {m for m, _ in c12})
    idx = {m: i for i, m in enumerate(meses)}
    W, H, iz, de, ar, ab = 340, 160, 32, 8, 8, 20

    def x(m):
        return iz + idx[m] / max(len(meses) - 1, 1) * (W - iz - de)

    def y(v):
        return ar + (1 - v) / 2 * (H - ar - ab)

    p = [f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(titulo)}">']
    for t in (-0.5, 0.5):
        p.append(f'<line class="grid" x1="{iz}" x2="{W - de}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
                 f'<text class="tick" x="{iz - 4}" y="{y(t) + 4:.1f}" text-anchor="end">{_n(t, 1, True)}</text>')
    p.append(f'<line class="base" x1="{iz}" x2="{W - de}" y1="{y(0):.1f}" y2="{y(0):.1f}"/>')
    p.append('<polyline class="l12" points="' + " ".join(f"{x(m):.1f},{y(v):.1f}" for m, v in c12) + '"/>')
    p.append('<polyline class="l36" points="' + " ".join(f"{x(m):.1f},{y(v):.1f}" for m, v in c36) + '"/>')
    if motor_v is not None:
        p.append(f'<line class="lmot" x1="{iz}" x2="{W - de}" y1="{y(motor_v):.1f}" y2="{y(motor_v):.1f}"/>')
    d12 = dict(c12)
    paso = max(1, len(c36) // 60)
    for m, v in c36[::paso]:
        tip = f"{m}: 36 m {_n(v, 2, True)} · 12 m {_n(d12.get(m), 2, True)}" + (
            f" · motor {_n(motor_v, 2, True)}" if motor_v is not None else "")
        p.append(f'<g class="row" data-tip="{esc(tip)}"><rect class="hit" x="{x(m) - 3:.1f}" y="{ar}" width="6" '
                 f'height="{H - ar - ab}"/></g>')
    for m in meses:
        if m.endswith("-01") and int(m[:4]) % 5 == 0:
            p.append(f'<text class="tick" x="{x(m):.1f}" y="{H - 5}" text-anchor="middle">{m[:4]}</text>')
    p.append("</svg>")
    return "".join(p)


def sec_correlaciones(mon: dict) -> str:
    filas, avisos = [], []
    for q in mon["pares"]:
        if q["difiere_signo"]:
            est = '<span class="badge b-warn"><span aria-hidden="true">▲</span> signo distinto al del motor</span>'
            avisos.append(q["nombre"])
        elif q["difiere_mucho"]:
            est = '<span class="badge b-warn"><span aria-hidden="true">◐</span> mismo signo, diferencia ≥ 0,3</span>'
        elif q["motor"] is None:
            est = '<span class="badge b-desc"><span aria-hidden="true">·</span> el motor no la modela</span>'
        else:
            est = '<span class="badge b-ok"><span aria-hidden="true">✓</span> mismo signo</span>'
        filas.append([esc(q["nombre"]), esc(q["ultimo_mes"]), _n(q["c36"], 2, True), _n(q["c12"], 2, True),
                      _n(q["c_10a"], 2, True), _n(q["motor"], 2, True), est])
    graf = "".join(
        f'<div class="card"><h4>{esc(q["nombre"])}</h4>'
        + svg_corr(mon["series"][q["par"]], q["motor"], f'Correlación móvil {q["nombre"]}') + "</div>"
        for q in mon["pares"])
    aviso = (f'<p><span class="badge b-warn"><span aria-hidden="true">▲</span> Aviso</span> La correlación de los '
             f'últimos 36 meses tiene distinto signo que la del motor en: <strong>{esc(", ".join(avisos))}</strong>. '
             'Los escenarios a 12 meses mezclan los activos como en ≤ 2004; tenlo en cuenta al leer el abanico conjunto.</p>'
             if avisos else "")
    return ('<div class="card"><h3>Monitor de correlaciones (EE. UU., rentabilidades mensuales)</h3>'
            '<p class="note">¿Se mueven juntos los activos como supone el motor de escenarios (INT-11)? Solo descriptivo: '
            'no cambia el motor. El motor usa rentabilidades reales a 12 meses de filas ≤ 2004 (la tabla «Dependencia '
            'entre activos por régimen» de la pestaña Escenarios); aquí son nominales mensuales, así que lo que se '
            f'compara es sobre todo el signo. Referencia del motor: emisión {esc(mon.get("motor_emision") or "—")}.</p>'
            + aviso
            + _tabla(["par", "último mes", "ρ 36 m", "ρ 12 m", "ρ 10 años", "ρ del motor (hoy, EE. UU.)", "estado"], filas)
            + '<ul class="legend inline"><li><span class="sw s1"></span>36 meses</li><li><span class="sw s2"></span>12 meses'
              '</li><li>- - - motor INT-11</li></ul>'
            + f'<div class="sm">{graf}</div>'
            + f'<p class="small">{esc(mon.get("nota"))}</p></div>')


def sec_verificacion(resumen_path: Path | None = None, mon: dict | None = None) -> str:
    rp = resumen_path or R.RUTA_RESUMEN
    intro = ('<div class="card"><h3>Qué se verifica aquí y qué no</h3><ol class="small">'
             '<li>Se verifica, dato a dato y en semanas: antes de cada publicación de EE. UU. (IPC general y subyacente, '
             'nóminas, paro, PIB avance) se guarda UNA predicción con su intervalo del 80 % y luego se compara con la '
             'primera publicación y con dos referencias ingenuas («último valor» y «media 12 m»).</li>'
             '<li>No se verifica aquí el percentil del nowcast de la pestaña Hoy (es descriptivo, no una cifra) ni los '
             'escenarios a 12 meses: esos se verifican en sus registros congelados (pestaña «Estado y avisos»: E1/E1b, '
             'K1v, INT-11 v3.1, paper B0/B1/B1′).</li>'
             '<li>El método v1 está fijado de antemano (docs/verif/metodo_v1.md). El «retrospectivo» es un backtest con '
             'los datos tal como se conocían entonces (vintages ALFRED): NO es en vivo y cuenta menos.</li></ol></div>')
    try:
        res = json.loads(Path(rp).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        res = None
    partes = [intro]
    if res is None:
        partes.append('<div class="card"><p class="nd">Sin resumen de verificación todavía '
                      '(lo escribe scripts/verif_registrar.py en la actualización diaria).</p></div>')
    else:
        vivo = res["vivo"]["registros"]
        pend = [r for r in vivo if r.get("estado") == "pendiente"]
        fp = [[esc(r["nombre"]), esc(r["periodo_txt"]), esc(r["fecha_emision"]),
               f'<strong>{_n(r["punto"], _dec(r["variable"]))}</strong> {esc(r["unidad"])}',
               f'[{_n(r["inf80"], _dec(r["variable"]))}; {_n(r["sup80"], _dec(r["variable"]))}]',
               _n(r["bench_ultimo"], _dec(r["variable"])), _n(r["bench_media12"], _dec(r["variable"]))] for r in pend]
        prox = [[esc(M.VARIABLES[e["variable"]]["nombre"]), esc(e.get("periodo", "—")[:7]),
                 esc(e.get("emision_prevista") or "cuando salgan las entradas"), esc(e["estado"])]
                for e in res.get("estados_hoy") or [] if e.get("estado") != "ya emitida"]
        partes.append('<div class="card"><h3>En vivo: predicciones emitidas pendientes del dato</h3>'
                      + (_tabla(["variable", "periodo", "emitida", "predicción", "intervalo 80 %", "«último»", "«media 12 m»"], fp)
                         if fp else '<p class="nd">Ninguna pendiente ahora mismo.</p>')
                      + ('<h4>Próximas emisiones</h4>' + _tabla(["variable", "periodo", "se emite a partir de", "estado"], prox)
                         if prox else "")
                      + f'<p class="small">Registro append-only: research/verif/vivo_v1.jsonl · método {esc(res.get("metodo"))} '
                        f'(sha256 {esc(str(res.get("metodo_sha256"))[:12])}…) · resumen generado {esc(res.get("generado"))}.</p></div>')
        nv = sum(f.get("n", 0) for f in res["vivo"]["resumen"])
        partes.append('<div class="card"><h3>Puntuación EN VIVO (acumulada)</h3>'
                      + (tabla_puntos(res["vivo"]["resumen"]) if nv else
                         '<p class="nd">Aún no hay ningún dato en vivo puntuado: el registro empezó en noviembre de 2026.</p>')
                      + "</div>")
        partes.append(f'<div class="card"><h3>Puntuación RETROSPECTIVA <span class="badge b-desc"><span aria-hidden="true">◌</span> '
                      f'{esc(res.get("etiqueta_retro"))}</span></h3>'
                      '<p class="note">Sin los meses covid (2020-03 a 2021-06). «MAE / último» &lt; 1 (en negrita) = el método '
                      'erró menos que repetir el último dato. Cobertura: cuántas veces el dato cayó dentro del intervalo '
                      'del 80 % (lo honesto es ≈ 80 %).</p>'
                      + tabla_puntos(res["retro"]["resumen_sin_covid"])
                      + '<details><summary class="small">Con los meses covid</summary>'
                      + tabla_puntos(res["retro"]["resumen_todo"]) + "</details></div>")
        partes.append('<div class="card"><h3>Errores en el tiempo (retrospectivo)</h3>'
                      '<p class="note">Cada punto = dato real − predicción. Banda = intervalo del 80 % alrededor de la '
                      'predicción. Azul: dentro; naranja: fuera. Los valores extremos (covid) se recortan al borde.</p>'
                      '<div class="sm">' + "".join(
                          f'<div class="card"><h4>{esc(meta["nombre"])} ({esc(meta["unidad"])})</h4>'
                          + svg_errores(res["retro"]["registros"], v) + f'<p class="small">{esc(meta["metodo"])}</p></div>'
                          for v, meta in M.VARIABLES.items()) + "</div></div>")
    try:
        partes.append(sec_correlaciones(mon or C.calcular()))
    except Exception as e:  # noqa: BLE001
        partes.append(f'<div class="card"><p class="nd">Monitor de correlaciones no disponible ({esc(type(e).__name__)}).</p></div>')
    return f'<style>{CSS}</style><div class="verif">' + "".join(partes) + "</div>"
