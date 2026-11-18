"""Pestaña «Manos fuertes» del panel web: posicionamiento en futuros (CFTC COT) y compras/ventas de directivos (SEC
Form 4). El cálculo está en src/report/manos_fuertes.py. Descriptivo y no validado; no es una recomendación.
"""
from __future__ import annotations

from datetime import date

from src.report import manos_fuertes as MF
from src.report.panel_paises import chip, esc, n

SECCIONES = [("Bolsa y volatilidad", ["sp500_emini", "nasdaq_mini", "vix"]),
             ("Bonos y tipos de EE. UU.", ["ust2y", "ust5y", "ust10y", "ust_bond", "sofr3m"]),
             ("Divisas (frente al dólar)", ["dxy", "eur", "jpy", "gbp", "chf"]),
             ("Materias primas", ["gold", "silver", "copper", "wti", "natgas"])]
CSS = """
.mf-spark{width:150px;height:34px;display:block}.mf-spark .ln{fill:none;stroke:var(--s1);stroke-width:1.5}
.mf-spark .bd{fill:var(--band1)}.mf-spark .z{stroke:var(--axis);stroke-width:1;stroke-dasharray:2 2}
.mf-spark .pt{fill:var(--s1);stroke:var(--surface);stroke-width:1.5}
table.mf td,table.mf th{white-space:nowrap;padding:5px 6px}table.mf td.lect{white-space:normal;min-width:180px}
table.mf tr.grp th{background:var(--hl);color:var(--ink);font-size:13px}
"""


def _fd(s: str | None) -> str:
    if not s:
        return "—"
    d = date.fromisoformat(s[:10])
    m = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"][d.month - 1]
    return f"{d.day}-{m}-{d.year}"


def spark(vals: list[float], lo: float | None = None, hi: float | None = None, tip: str = "",
          w: int = 150, h: int = 34) -> str:
    """Mini-gráfico SVG: línea, banda p10–p90 (si se da) y referencia en 0 si cae dentro del rango."""
    if not vals or len(vals) < 2:
        return ""
    a, b = min(vals + [lo if lo is not None else vals[0]]), max(vals + [hi if hi is not None else vals[0]])
    if b - a < 1e-9:
        b = a + 1
    pad = 3

    def y(v):
        return pad + (h - 2 * pad) * (1 - (v - a) / (b - a))

    def x(i):
        return pad + (w - 2 * pad) * i / (len(vals) - 1)
    p = [f'<svg class="mf-spark" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(tip)}" data-tip="{esc(tip)}" tabindex="0">']
    if lo is not None and hi is not None:
        p.append(f'<rect class="bd" x="{pad}" y="{y(hi):.1f}" width="{w - 2 * pad}" height="{max(0.5, y(lo) - y(hi)):.1f}"/>')
    if a < 0 < b:
        p.append(f'<line class="z" x1="{pad}" x2="{w - pad}" y1="{y(0):.1f}" y2="{y(0):.1f}"/>')
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
    p.append(f'<polyline class="ln" points="{pts}"/>')
    p.append(f'<circle class="pt" cx="{x(len(vals) - 1):.1f}" cy="{y(vals[-1]):.1f}" r="2.8"/></svg>')
    return "".join(p)


def _chip_senal(sg: str | None) -> str:
    if not sg:
        return '<span class="muted">dentro de lo normal</span>'
    return chip("ambar", sg, "Regla fija del panel: percentil de 3 años ≥ 90 o ≤ 10. Dato de contexto, no una señal validada.")


def _fila(m: dict, clave: str, g: dict, primera: bool, filas_m: int) -> str:
    tip = (f"{m['nombre']} · {g['etiqueta']}: {n(g['valor'], 1, ' % del interés abierto')}. "
           f"Banda = p10–p90 de 3 años ({n(g['p10_3a'], 0, ' %')} a {n(g['p90_3a'], 0, ' %')}); "
           f"mín. {n(g['min_3a'], 0, ' %')}, máx. {n(g['max_3a'], 0, ' %')}.")
    cel_m = (f'<td rowspan="{filas_m}"><strong>{esc(m["nombre"])}</strong>'
             + (f'<br><span class="muted" style="white-space:normal">{esc(m["nota"])}</span>' if m["nota"] else "")
             + "</td>") if primera else ""
    return (f"<tr>{cel_m}<td>{esc(g['etiqueta'])}</td><td><strong>{n(g['valor'], 1, ' %', True)}</strong></td>"
            f"<td>{n(g['d1'], 1, '', True)}</td><td>{n(g['d4'], 1, '', True)}</td>"
            f"<td>{n(g['p3a'], 0, '')}</td><td>{n(g['phist'], 0, '')} <span class='muted'>desde {g['desde'][:4]}</span></td>"
            f"<td>{spark(g['spark'], g['p10_3a'], g['p90_3a'], tip)}</td><td class='lect'>{_chip_senal(g['senal'])}</td></tr>")


def tabla_cot(cot: list[dict]) -> str:
    por = {m["slug"]: m for m in cot}
    cab = ["mercado", "quién", "neto (% del interés abierto)", "Δ 1 sem. (pp)", "Δ 4 sem. (pp)",
           "percentil 3 años", "percentil histórico", "3 años (banda p10–p90)", "lectura"]
    tr = []
    for tit, slugs in SECCIONES:
        ms = [por[s] for s in slugs if s in por]
        if not ms:
            continue
        tr.append(f'<tr class="grp"><th colspan="{len(cab)}">{esc(tit)}</th></tr>')
        for m in ms:
            gs = list(m["grupos"].items())
            for i, (k, g) in enumerate(gs):
                tr.append(_fila(m, k, g, i == 0, len(gs)))
    th = "".join(f"<th>{esc(c)}</th>" for c in cab)
    return f'<div class="tw"><table class="mf num"><thead><tr>{th}</tr></thead><tbody>{"".join(tr)}</tbody></table></div>'


def extremos(cot: list[dict]) -> list[str]:
    """Frases de los grupos en extremo; primero los que también lo están en toda su historia."""
    xs = []
    for m in cot:
        for g in m["grupos"].values():
            if not g["senal"]:
                continue
            n3 = len(g["spark"])
            if g["p3a"] >= MF.P_ALTO:
                lado = ("la posición más compradora de los 3 últimos años" if g["p3a"] >= 100 else
                        f"más compradora (o menos vendedora) que en el {n(g['p3a'], 0, ' %')} de las semanas de los 3 últimos años")
            else:
                lado = ("la posición más vendedora de los 3 últimos años" if g["p3a"] <= 100 / n3 else
                        f"más vendedora (o menos compradora) que en el {n(100 - g['p3a'], 0, ' %')} de las semanas de los 3 últimos años")
            hist = "historia" in g["senal"]
            xs.append((not hist, f"<strong>{esc(m['nombre'])}</strong> · {esc(g['etiqueta'].lower())}: "
                                 f"{n(g['valor'], 1, ' %', True)} del interés abierto; {lado}"
                                 + (" (y extremo en toda su historia, desde 2006)" if hist else "") + "."))
    return [t for _, t in sorted(xs, key=lambda z: z[0])]


def _ins_tiles(a: dict) -> str:
    t = []
    for k, etq in (("4s", "últimas 4 semanas"), ("13s", "últimas 13 semanas")):
        v = a["ventanas"].get(k)
        if not v:
            continue
        t.append(f'<div class="tile"><span class="muted">{etq} (hasta {_fd(a["hasta"])})</span>'
                 f'<strong>{n(v["amplitud"], 0, " %")}</strong>'
                 f'<span class="small">«amplitud»: empresas con compras de directivos frente a empresas con compras + empresas con ventas (una empresa con las dos cuenta dos veces) '
                 f'({int(v["empresas_compra"])} con compras, {int(v["empresas_venta"])} con ventas). '
                 f'Media histórica {n(v["media_amplitud"], 0, " %")}; percentil {n(v["p_amplitud"], 0, "")} '
                 f'de {int(v["n_hist"])} ventanas desde {_fd(a["desde"])[-4:]}.</span>'
                 f'<span class="small">Importe: compras {n(v["importe_compra"] / 1e6, 0, " M$")} frente a ventas '
                 f'{n(v["importe_venta"] / 1e6, 0, " M$")} ({n(v["pct_importe_compra"], 1, " %")} compras; '
                 f'percentil {n(v["p_pct_importe"], 0, "")}).</span></div>')
    v13 = a["ventanas"].get("13s") or {}
    lect = ""
    if v13.get("p_amplitud") is not None:
        pa = v13["p_amplitud"]
        q = ("más empresas con compras de directivos que en el " + n(pa, 0, " %") + " de las ventanas desde " + a["desde"][:4]
             if pa >= 50 else "menos empresas con compras de directivos que en el " + n(100 - pa, 0, " %")
             + " de las ventanas desde " + a["desde"][:4])
        ext = (" Es un extremo (regla fija ≥ p90 / ≤ p10)." if pa >= MF.P_ALTO or pa <= MF.P_BAJO
               else " No llega a extremo (regla fija ≥ p90 / ≤ p10).")
        lect = f'<p><strong>Lectura (13 semanas):</strong> {q}.{ext}</p>'
    sp = ""
    if v13.get("spark"):
        sp = (f'<p class="small">Amplitud de 13 semanas (% de empresas con compras), semana a semana desde '
              f'{_fd(v13.get("spark_desde"))}:</p>'
              + spark(v13["spark"], tip="% de empresas con compras de directivos en ventanas de 13 semanas", w=420, h=60)
              .replace('class="mf-spark"', 'class="mf-spark" style="width:100%;max-width:420px;height:60px"'))
    return f'{lect}<div class="tiles">{"".join(t)}</div>{sp}'


def tabla_tickers(ts: list[dict]) -> str:
    cab = ["acción", "compras (13 sem.)", "ventas (13 sem.)", "de ellas con plan 10b5-1", "compras (12 m)",
           "ventas (12 m)", "última compra", "último Form 4 P/S"]
    filas = []
    for r in ts:
        a, b = r["13s"], r["12m"]

        def cv(x, tipo):
            k, imp = (x["n_compra"], x["importe_compra"]) if tipo == "c" else (x["n_venta"], x["importe_venta"])
            return f"{k}" + (f" <span class='muted'>({n(imp / 1e6, 1, ' M$')})</span>" if k else "")
        filas.append(f"<tr><td><strong>{esc(r['ticker'])}</strong> <span class='muted'>{esc(r['nombre'])}</span></td>"
                     f"<td>{cv(a, 'c')}</td><td>{cv(a, 'v')}</td><td>{a['plan_venta']}</td><td>{cv(b, 'c')}</td>"
                     f"<td>{cv(b, 'v')}</td><td>{_fd(r['ultima_compra'])}</td><td>{_fd(r['ultimo_form4'])}</td></tr>")
    th = "".join(f"<th>{esc(c)}</th>" for c in cab)
    return f'<div class="tw"><table class="mf num"><thead><tr>{th}</tr></thead><tbody>{"".join(filas)}</tbody></table></div>'


def sec_manos_fuertes(hoy: date | None = None, datos: dict | None = None) -> str:
    hoy = hoy or date.today()
    d = datos if datos is not None else MF.calcular(hoy)
    cot = d.get("cot") or []
    ins = d.get("insiders") or {}
    p = ['<div class="enfrase"><p><strong>En una frase:</strong> quién está comprando o vendiendo: fondos en los '
         'futuros (CFTC, semanal) y directivos de empresas en su propia acción (SEC, Form 4).</p>'
         '<details><summary>¿Cómo leo esta pestaña?</summary><p class="small">«Neto» = contratos comprados menos '
         'vendidos de ese grupo, en % de todos los contratos abiertos. El percentil dice en qué lugar está el dato de '
         'hoy entre todas las semanas de la ventana (90 = más comprado que el 90 % de las semanas). «Extremo» es una '
         'regla fija del panel (percentil de 3 años ≥ 90 o ≤ 10): describe, no predice. Este proyecto no ha medido si '
         'estos extremos anticipan algo; no hay historial de aciertos.</p></details></div>']
    p.append('<p class="disc"><strong>Contexto, no señal.</strong> Un posicionamiento extremo no es una señal validada '
             'de compra ni de venta: puede durar meses, y en bonos y divisas buena parte son coberturas y arbitrajes. '
             'No es asesoramiento.</p>')
    # ---------------- COT
    if cot:
        f0 = max(g["fecha"] for m in cot for g in m["grupos"].values())
        pub = max(g["publicado"] for m in cot for g in m["grupos"].values())
        aviso = ""
        if (hoy - date.fromisoformat(pub)).days > 7:
            aviso = (f' <span class="chip c-ambar"><span aria-hidden="true">▲</span> la CFTC ya habrá publicado un '
                     f'informe posterior: el warehouse no se ha reconstruido con él</span>')
        ex = extremos(cot)
        n_series = sum(len(m["grupos"]) for m in cot)
        p.append('<div class="card"><h3>Qué dice hoy (futuros)</h3>'
                 f'<p class="small">Posiciones del martes {_fd(f0)}, publicadas por la CFTC el viernes {_fd(pub)}.{aviso}</p>'
                 + ("<ul>" + "".join(f"<li>{x}</li>" for x in ex) + "</ul>" if ex else
                    "<p>Ningún grupo está en un extremo de 3 años.</p>")
                 + f'<p class="small">{len(ex)} de {n_series} series en extremo. Ojo: por pura casualidad, con una regla '
                 f'que marca el 20 % de las semanas, unas {round(0.2 * n_series)} lo estarían cualquier semana; y en '
                 f'bonos, divisas y materias primas buena parte del posicionamiento son coberturas y arbitrajes.</p></div>')
        p.append('<div class="card"><h3>Posicionamiento en futuros por mercado</h3>'
                 '<p class="small">Financieros (informe TFF): <strong>gestoras</strong> = «dinero real» (fondos de '
                 'pensiones y de inversión, aseguradoras); <strong>fondos apalancados</strong> = hedge funds y CTA. '
                 'Materias primas (informe desagregado): <strong>fondos especulativos</strong> («managed money») y '
                 '<strong>productores y comerciantes</strong> (quien produce o consume y se cubre; suelen ir al revés '
                 'del precio). Δ en puntos porcentuales del interés abierto. Solo futuros (sin opciones).</p>'
                 + tabla_cot(cot) + "</div>")
    else:
        p.append(f'<div class="card"><p class="nd">COT no disponible: {esc(d.get("cot_error", "sin datos"))}</p></div>')
    # ---------------- directivos
    p.append('<div class="card"><h3>Directivos comprando o vendiendo su propia acción (SEC Form 4)</h3>')
    if ins.get("error"):
        p.append(f'<p class="nd">{esc(ins["error"])}</p>')
    else:
        a = ins.get("agregado")
        p.append('<p class="small">Solo compras (código P) y ventas (código S) en mercado abierto de consejeros y '
                 'directivos; sin opciones, regalos ni acciones de su sueldo. Todo el mercado cotizado de EE. UU. '
                 '(no solo el S&amp;P 500: el proyecto no guarda su composición histórica), con precio ≥ 1 $ e importe '
                 'recortado en 50 M$ por operación (hay errores de tecleo). Las ventas son la norma (cobran en '
                 'acciones, diversifican, planes 10b5-1); lo que suele leerse como informativo son las compras, y '
                 'sobre todo cuántas empresas distintas las tienen («amplitud»).</p>')
        if a:
            p.append(f'<p class="small"><strong>Retraso:</strong> el agregado sale de los ficheros trimestrales de la '
                     f'SEC y llega hasta el {_fd(a["hasta"])} (último trimestre publicado); la SEC publica cada '
                     f'trimestre unos días después de cerrarlo.</p>' + _ins_tiles(a))
        ts = ins.get("tickers") or []
        if ts:
            p.append('<h4>Tus acciones («Mis activos»)</h4>'
                     f'<p class="small">Form 4 presentados hasta el {_fd(ins.get("recientes_hasta") or a and a["hasta"])}. '
                     'Número de declaraciones (y su importe). Los ETF, futuros y Bayer (Alemania) no presentan Form 4. '
                     'En las grandes tecnológicas casi todo son ventas programadas (plan 10b5-1).</p>' + tabla_tickers(ts))
    p.append("</div>")
    # ---------------- fuentes y límites
    p.append('<details class="card"><summary><h3>Fuentes, retrasos y lo que falta</h3></summary><ul class="small">'
             '<li><strong>CFTC Commitments of Traders</strong> (cftc.gov): posiciones de cada martes, publicadas el '
             'viernes a las 15:30 (hora de Nueva York). Informe TFF y desagregado desde jun-2006; solo futuros.</li>'
             '<li><strong>SEC Form 4</strong> (sec.gov): el directivo tiene 2 días hábiles para declarar. Ficheros '
             'trimestrales «Insider Transactions Data Sets» (desde 2016 en este panel) + Form 4 recientes de tus '
             'acciones leídos de EDGAR.</li>'
             '<li><strong>13F (carteras de grandes gestoras):</strong> no se resume en esta pestaña, pero cada ficha de '
             '«Mis activos» lo trae para su acción («Grandes gestoras (SEC 13F, trimestral)»). Es trimestral y se presenta hasta '
             '45 días después del trimestre (la foto llega con 1,5–4,5 meses de retraso), solo muestra posiciones '
             'largas en acciones de EE. UU. (sin cortos, sin derivados casi, sin efectivo) y solo de gestoras con '
             '> 100 M$. Sirve para ver qué tenía un fondo, no lo que hace hoy.</li>'
             '<li>Nada de esto se ha validado en este proyecto como predictor: sin historial de aciertos.</li></ul></details>')
    return "".join(p)
