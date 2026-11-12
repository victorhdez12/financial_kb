"""Pestaña «Mis activos» del panel web: acciones, ETF y materias primas (src/report/mis_activos.py).

Se calcula al generar el panel (local): los precios de Yahoo NO pasan por el signal ni por el repo (público).
Descriptivo y no validado; no es una recomendación de compra o venta.
"""
from __future__ import annotations

import json
from datetime import date

from src.report import mis_activos as MA
from src.report.panel_paises import chip, esc, n, term

GRUPOS = ["Acciones", "Agro / pesticidas", "Oro y materias primas", "ETF sectoriales", "Referencias"]
CUAD = ["Goldilocks", "Reflación", "Estanflación", "Deflación/recesión"]


def _datos(s: dict, pul: dict | None) -> dict:
    from src.report.panel import INT11_HOY
    from src.warehouse import db
    try:
        es = json.loads(INT11_HOY.read_text())
    except Exception:  # noqa: BLE001
        es = None
    infl = None
    try:
        infl = pul["paises"]["USA"]["prevision_fmi"][str(date.today().year + 1)]["inflacion"]
    except (KeyError, TypeError):
        pass
    con = db.connect(read_only=True)
    try:
        rf = con.execute("select last(value order by date) from obs_latest where series_id = 'DTB3'").fetchone()[0]
        return MA.analizar(con, date.today(), es, infl, float(rf) if rf is not None else None)
    finally:
        con.close()


def _c(v):
    """color por signo para rentabilidades."""
    if v is None:
        return "gris"
    return "verde" if v > 0.5 else ("rojo" if v < -0.5 else "ambar")


def _rango(sim: dict | None) -> str:
    if not sim:
        return '<span class="nd">—</span>'
    return (f"<strong>{n(100 * sim['p50'], 0, ' %', True)}</strong> "
            f"<br><span class='muted'>{n(100 * sim['p5'], 0, '', True)} a {n(100 * sim['p95'], 0, ' %', True)}</span>")


def sec_activos(s: dict, pul: dict | None) -> str:
    d = _datos(s, pul)
    if "error" in d:
        return f'<div class="card"><p class="nd">{esc(d["error"])}</p></div>'
    A = d["activos"]
    sup = d["supuestos"]
    from collections import Counter
    fecha_comun = Counter(r.get("fecha") for r in A.values()).most_common(1)[0][0]
    filas_g = []
    for gr in GRUPOS:
        ts = [t for t, r in A.items() if r.get("grupo") == gr]
        if not ts:
            continue
        filas = []
        for t in ts:
            r = A[t]
            if "error" in r:
                filas.append(f"<tr><td>{esc(r.get('nombre', t))}</td><td colspan='8' class='nd'>{esc(r['error'])}</td></tr>")
                continue
            av = " ▲" if r.get("avisos") else ""
            filas.append(
                f"<tr><td><a href='#act-{esc(t)}' class='actlink'>{esc(r['nombre'])}</a><span class='muted'> {esc(t)}{av}</span></td>"
                f"<td>{n(r['precio'], 2, ' ' + esc(r.get('moneda') or ''))}"
                + (f"<br><span class='muted'>{esc(r['fecha'])}</span>" if r['fecha'] != fecha_comun else "") + "</td>"
                + "".join(f"<td>{chip(_c(r.get(k)), n(r.get(k), 1, ' %', True).replace('<span class=\"nd\">s/d</span>', 's/d'))}</td>"
                          for k in ("r_1m", "r_ytd", "r_12m"))
                + f"<td>{n(r.get('vol_1a'), 0)}</td><td>{n(r.get('caida_max52'), 0, ' %', True)}</td>"
                f"<td>{n(r.get('beta_3a'), 2, '')}</td><td>{_rango(r.get('sim_historia'))}</td><td>{_rango(r.get('sim_motor'))}</td></tr>")
        filas_g.append(f"<tr class='grp'><th colspan='10'>{esc(gr)}</th></tr>" + "".join(filas))
    tabla = (f"<div class='tw'><table class='num act'><thead><tr><th>Activo</th><th>Precio <span class='muted'>({esc(fecha_comun)})</span></th><th>1 mes</th><th>En el año</th>"
             "<th>12 meses</th><th data-tip='Volatilidad anualizada del último año (diaria)'>Volat. 1 a</th>"
             "<th data-tip='Caída desde el máximo de las últimas 52 semanas'>Desde máx.</th>"
             "<th data-tip='Sensibilidad semanal al S&P 500 (3 años): 1 = se mueve como el mercado'>Beta</th>"
             "<th data-tip='Simulación A: su propia historia (bootstrap). Mediana y rango 90 %'>12 m · historia</th>"
             "<th data-tip='Simulación B: enlazada al motor de escenarios de la bolsa de EE. UU. (sin alfa). Mediana y rango 90 %'>12 m · motor</th>"
             f"</tr></thead><tbody>{''.join(filas_g)}</tbody></table></div>")
    fichas = "".join(_ficha(t, r) for t, r in A.items() if "error" not in r)
    return f'''<div class="intro"><p><strong>Tus acciones, ETF y materias primas.</strong> Cómo van, cuánto riesgo tienen,
cómo se comportaron en cada situación de EE. UU. y dos simulaciones a 12 meses. Pulsa un activo para su ficha.</p>
<p class="small">Las simulaciones son <strong>rentabilidades nominales en la moneda del activo</strong>: «mediana (rango del
90 %)». <strong>A · historia</strong> remuestrea su propia historia (si subió mucho en el pasado, arrastra esa subida:
optimista). <strong>B · motor</strong> parte de los escenarios de la bolsa de EE. UU. del motor (+ inflación prevista
por el FMI {n(sup.get("inflacion_usa_fmi"), 1)}; letra a 3 meses {n(sup.get("rf_3m"), 2)}) y le aplica la beta del activo
sin suponer que vaya a batir al mercado. Ninguna está validada: <strong>no son recomendaciones</strong>. Precios: Yahoo
Finance, cierre ajustado ({esc(str(d.get("descarga"))[:16])} UTC); el último precio puede ser del día en curso.</p></div>
<div class="card">{tabla}</div>
<h3>Fichas</h3>{fichas}
<details class="card"><summary><h3>Cómo se calcula</h3></summary><p class="small">{esc(MA.__doc__)}</p></details>'''


def _ficha(t: str, r: dict) -> str:
    pc = r.get("por_cuadrante") or {}
    cuad = "".join(f"<tr><td>{esc(q)}</td><td><strong>{n((pc.get(q) or {}).get('anual'), 1, ' %', True)}</strong></td>"
                   f"<td>{n((pc.get(q) or {}).get('positivos'), 0)}</td><td>{(pc.get(q) or {}).get('meses', '—')}"
                   f"{' <span class=muted>(pocos)</span>' if (pc.get(q) or {}).get('meses', 0) < 24 else ''}</td></tr>" for q in CUAD)
    sims = ""
    for k, tit in (("sim_historia", "A · su propia historia"), ("sim_motor", "B · enlazada al motor (sin alfa)")):
        x = r.get(k)
        if not x:
            continue
        extra = (f"desde {x.get('desde')} ({x.get('meses_historia')} meses)" if k == "sim_historia"
                 else f"beta 10 años {n(x.get('beta_10a'), 2, '')}, volatilidad propia {n(x.get('vol_idio_anual'), 0)}")
        sims += (f"<tr><td>{tit}<br><span class='muted'>{esc(extra)}</span></td>"
                 f"<td><strong>{n(100 * x['p50'], 0, ' %', True)}</strong></td><td>{n(100 * x['p5'], 0, ' %', True)} a {n(100 * x['p95'], 0, ' %', True)}</td>"
                 f"<td>{n(100 * x['p25'], 0, ' %', True)} a {n(100 * x['p75'], 0, ' %', True)}</td>"
                 f"<td>{n(100 * x['p_perdida'], 0)}</td><td>{n(100 * x['p_caida20'], 0)}</td></tr>")
    avisos = "".join(f"<p class='small'>▲ {esc(a)}</p>" for a in r.get("avisos") or [])
    return f'''<details class="card pais" id="act-{esc(t)}"><summary><span class="pn">{esc(r["nombre"])} <span class="muted">{esc(t)} · {esc(r.get("grupo"))}</span></span></summary>
<div class="pdet">{avisos}<div class="dgrid">
<div class="dblk"><h4>Situación ({esc(r["fecha"])})</h4><table class="num"><tbody>
<tr><td>Precio</td><td><strong>{n(r["precio"], 2, " " + esc(r.get("moneda") or ""))}</strong></td></tr>
<tr><td>1 mes / 3 meses</td><td><strong>{n(r.get("r_1m"), 1, " %", True)} / {n(r.get("r_3m"), 1, " %", True)}</strong></td></tr>
<tr><td>En el año / 12 meses</td><td><strong>{n(r.get("r_ytd"), 1, " %", True)} / {n(r.get("r_12m"), 1, " %", True)}</strong></td></tr>
<tr><td>3 años (anualizado)</td><td><strong>{n(r.get("r_3a_anual"), 1, " %", True)}</strong></td></tr>
<tr><td>Volatilidad 1 año</td><td><strong>{n(r.get("vol_1a"), 0)}</strong></td></tr>
<tr><td>Caída desde máximo 52 semanas</td><td><strong>{n(r.get("caida_max52"), 1, " %", True)}</strong></td></tr>
<tr><td>Beta / correlación con S&amp;P 500 (3 años)</td><td><strong>{n(r.get("beta_3a"), 2, "")} / {n(r.get("corr_3a"), 2, "")}</strong></td></tr>
</tbody></table></div>
<div class="dblk"><h4>En cada situación de EE. UU. ({term("cuadrante")})</h4><table class="num"><thead><tr><th></th><th>Rent. anualizada</th>
<th>% meses +</th><th>Meses</th></tr></thead><tbody>{cuad}</tbody></table>
<p class="small">Hoy: Goldilocks. Medias de meses pasados de este activo, sin contrastar: con pocos meses, ruido.</p></div>
<div class="dblk wide"><h4>Simulación a 12 meses (nominal, {esc(r.get("moneda") or "")})</h4><table class="num"><thead><tr><th>Modelo</th><th>Mediana</th>
<th>{term("p5-p95", "Rango 90 %")}</th><th>Rango 50 %</th><th>P(perder)</th><th>P(caer ≥ 20 %)</th></tr></thead><tbody>{sims or "<tr><td colspan=6 class=nd>sin historia suficiente</td></tr>"}</tbody></table>
<p class="small">No validado. Una acción individual puede salirse de cualquier rango por noticias propias (resultados, juicios, escisiones).</p></div>
</div></div></details>'''


CSS = """
table.act td,table.act th{white-space:nowrap;padding:6px 6px}table.act td:first-child{white-space:normal;min-width:180px}table.act tr.grp th{background:var(--hl);color:var(--ink);font-size:13px}
.actlink{color:var(--ink);text-decoration:none;font-weight:600}.actlink:hover{text-decoration:underline}
"""
JS = """
(function(){document.addEventListener('click',function(e){var a=e.target.closest('a.actlink');if(!a)return;e.preventDefault();
var d=document.getElementById(a.getAttribute('href').slice(1));if(d){d.open=true;d.scrollIntoView({behavior:'smooth'})}});})();
"""
