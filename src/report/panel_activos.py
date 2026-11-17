"""Pestaña «Mis activos» del panel web: acciones, ETF y materias primas (src/report/mis_activos.py).

Se calcula al generar el panel (local): los precios de Yahoo NO pasan por el signal ni por el repo (público).
Descriptivo y no validado; no es una recomendación de compra o venta.
"""
from __future__ import annotations

import json
from datetime import date

from src.report import activos_v2 as AV
from src.report import alertas as AL
from src.report import mis_activos as MA
from src.report.panel_paises import chip, esc, n, term

GRUPOS = ["Acciones", "Agro / pesticidas", "Oro y materias primas", "ETF sectoriales", "Referencias"]
CUAD = ["Goldilocks", "Reflación", "Estanflación", "Deflación/recesión"]


def _emision_motor(s: dict) -> tuple[str | None, dict | None, str]:
    """Emisión del motor que se reproduce: la del signal (la que enseñan «Escenarios» y «Qué hacer»), comprobada contra
    sus abanicos de bolsa de EE. UU.; si el signal no la trae, la de research/int/int11_v3_hoy.json (rejilla 1-99)."""
    es = (s or {}).get("escenarios") or {}
    try:
        ab = es["paises"]["USA"]["abanicos"]["bolsa"]
        return es["emision"], {p: ab[f"p{p}"] for p in (5, 25, 50, 75, 95)}, "signal semanal"
    except (KeyError, TypeError):
        pass
    from src.report.panel import INT11_HOY
    try:
        h = json.loads(INT11_HOY.read_text())
        q = h["paises"]["USA"]["cuantiles_1_99"]["bolsa"]
        return h["emision"], {i + 1: v for i, v in enumerate(q)}, "research/int/int11_v3_hoy.json"
    except Exception:  # noqa: BLE001
        return None, None, "sin emisión"


def _datos(s: dict, pul: dict | None) -> dict:
    from src.warehouse import db
    con = db.connect(read_only=True)
    try:
        rf = con.execute("select last(value order by date) from obs_latest where series_id = 'DTB3'").fetchone()[0]
        emision, ref, fuente = _emision_motor(s)
        motor, error_motor = None, None
        if emision:
            try:
                motor = MA.trayectorias_motor(emision, con, ref)
                motor["fuente_emision"] = fuente
            except Exception as e:  # noqa: BLE001
                error_motor = f"{type(e).__name__}: {e}"
        d = MA.analizar(con, date.today(), motor, float(rf) if rf is not None else None)
        if "supuestos" in d:
            if motor is not None:
                d["supuestos"]["motor"]["fuente_emision"] = fuente
            d["supuestos"]["error_motor"] = error_motor or (None if emision else "no hay emisión del motor")
        return d
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
                f"<td>{n(r.get('beta_3a'), 2, '')}</td>"
                + (f"<td colspan='2' class='nd'>{esc(r['historia_insuficiente'])}</td></tr>" if r.get("historia_insuficiente")
                   else f"<td>{_rango(r.get('sim_historia'))}</td><td>{_rango(r.get('sim_motor'))}</td></tr>"))
        filas_g.append(f"<tr class='grp'><th colspan='10'>{esc(gr)}</th></tr>" + "".join(filas))
    tabla = (f"<div class='tw'><table class='num act'><thead><tr><th>Activo</th><th>Precio <span class='muted'>({esc(fecha_comun)})</span></th><th>1 mes</th><th>En el año</th>"
             "<th>12 meses</th><th data-tip='Volatilidad anualizada del último año (diaria)'>Volat. 1 a</th>"
             "<th data-tip='Caída desde el máximo de las últimas 52 semanas'>Desde máx.</th>"
             "<th data-tip='Sensibilidad semanal al S&P 500 (3 años): 1 = se mueve como el mercado'>Beta</th>"
             "<th data-tip='Simulación A: su propia historia (bootstrap). Mediana y rango 90 %'>12 m · historia</th>"
             "<th data-tip='Simulación B: cada trayectoria del motor (bolsa de EE. UU. e inflación conjuntas), beta del activo, sin alfa. NOMINAL en USD. Mediana y rango 90 %; la real y las colas, en la ficha'>12 m · motor<br><span class='muted'>(nominal)</span></th>"
             f"</tr></thead><tbody>{''.join(filas_g)}</tbody></table></div>")
    hoy_q = (s.get("regime") or {}).get("quadrant")
    v2 = AV.cargar_seguro()   # volumen, Form 4, 13F y analistas (fuera de git); si falla, «s/d» en cada ficha
    R = AL.calcular_seguro(v2)   # alertas de flujos (descriptivas; si fallan, «s/d»)
    if v2 is not None:
        v2 = {**v2, "alertas": R}
    fichas = "".join(_ficha(t, r, hoy_q, v2) for t, r in A.items() if "error" not in r)
    return f'''<div class="intro"><p><strong>Tus acciones, ETF y materias primas.</strong> Cómo van, cuánto riesgo tienen,
cómo se comportaron en cada situación de EE. UU. y dos simulaciones a 12 meses. Pulsa un activo para su ficha.</p>
<p class="small">En la tabla, las simulaciones son <strong>rentabilidades nominales en la moneda del activo</strong>:
«mediana (rango del 90 %)». <strong>A · historia</strong> remuestrea su propia historia (si subió mucho en el pasado,
arrastra esa subida: optimista). {_texto_b(sup)} Ninguna está validada: <strong>no son recomendaciones</strong>. Precios: Yahoo
Finance, cierre ajustado ({esc(str(d.get("descarga"))[:16])} UTC); el último precio puede ser del día en curso.</p></div>
{AL.bloque_alertas(R, "activos")}
<div class="card">{tabla}</div>
<h3>Fichas</h3>{fichas}
<details class="card"><summary><h3>Cómo se calcula</h3></summary><p class="small">{esc(MA.__doc__)}</p></details>'''


def _texto_b(sup: dict) -> str:
    mo = sup.get("motor")
    if not mo:
        return (f"<strong>B · motor</strong>: no disponible ({esc(sup.get('error_motor') or 'sin trayectorias del motor')}).")
    pi, v, c = mo["inflacion"], mo.get("ventana") or {}, mo.get("comprobacion")
    if c is None:
        comp = "sin cuantiles publicados con que comprobarla"
    elif c["coincide"]:
        comp = f"reproduce la emisión publicada ({esc(mo.get('fuente_emision'))}; dif. máx. {n(100 * c['max_dif'], 2, ' pp')})"
    else:
        comp = (f"<strong>▲ NO coincide con la emisión publicada</strong> ({esc(mo.get('fuente_emision'))}; dif. máx. "
                f"{n(100 * c['max_dif'], 1, ' pp')}): son trayectorias recalculadas con los datos de hoy")
    rec = ("sin recortar colas (se usan todas las trayectorias)" if not mo.get("recortadas") else
           f"<strong>recorte por estabilidad numérica</strong>: {mo['recortadas']} trayectorias con bolsa real ≤ −99,9 % acotadas")
    return (f"<strong>B · motor</strong> usa cada una de las {mo['trayectorias']:,} trayectorias del motor INT-11 v3.1".replace(",", ".")
            + f" (emisión {esc(mo.get('emision'))}, ventana {esc(str(v.get('desde'))[:7])} a {esc(str(v.get('hasta'))[:7])}; {comp}):"
            f" la bolsa de EE. UU. <em>real</em> y la <strong>inflación de esa misma trayectoria</strong> (IPC medio de EE. UU.,"
            f" la que simula el motor: mediana {n(100 * pi['p50'], 1)}, rango del 90 % {n(100 * pi['p5'], 1, '')} a"
            f" {n(100 * pi['p95'], 1)}). Bolsa nominal = real + inflación; al activo se le aplica su beta sin suponer que"
            f" vaya a batir al mercado (letra a 3 meses {n(sup.get('rf_3m'), 2)}); su rentabilidad <em>real</em> (en la ficha)"
            f" = nominal − la misma inflación. Distribución completa, {rec}.")


def _ficha(t: str, r: dict, hoy_q: str | None = None, v2: dict | None = None) -> str:
    pc = r.get("por_cuadrante") or {}
    cuad = "".join(f"<tr><td>{esc(q)}</td><td><strong>{n((pc.get(q) or {}).get('anual'), 1, ' %', True)}</strong></td>"
                   f"<td>{n((pc.get(q) or {}).get('positivos'), 0)}</td><td>{(pc.get(q) or {}).get('meses', '—')}"
                   f"{' <span class=muted>(pocos)</span>' if (pc.get(q) or {}).get('meses', 0) < 24 else ''}</td></tr>" for q in CUAD)
    sims = ""
    filas = [("sim_historia", None, "A · su propia historia (nominal)"),
             ("sim_motor", None, "B · motor, nominal"), ("sim_motor", "real", "B · motor, real (− inflación de la trayectoria)"),
             ("sim_motor_infl", None, "B′ · + beta a la inflación, nominal (informativa)"),
             ("sim_motor_infl", "real", "B′ · + beta a la inflación, real (informativa)")]
    for k, sub, tit in filas:
        x = r.get(k)
        if not x:
            continue
        if k == "sim_historia":
            extra = f"desde {x.get('desde')} ({x.get('meses_historia')} meses)"
        elif k == "sim_motor" and sub is None:
            extra = (f"beta 10 años {n(x.get('beta_10a'), 2, '')}, volatilidad propia {n(x.get('vol_idio_anual'), 0)}"
                     f" ({x.get('meses')} meses hasta {x.get('hasta', '')[:7]})")
        elif k == "sim_motor_infl" and sub is None:
            extra = (f"beta a la inflación mensual {n(x.get('beta_pi'), 1, '')} (error típico {n(x.get('se_pi'), 1, '')}),"
                     f" beta mercado {n(x.get('beta_m'), 2, '')}; IPC publicado hasta {x.get('ipc_hasta')}")
        else:
            extra = "real = nominal − inflación de esa misma trayectoria del motor"
        y = x[sub] if sub else x
        sims += (f"<tr><td>{tit}<br><span class='muted'>{esc(extra)}</span></td>"
                 f"<td><strong>{n(100 * y['p50'], 0, ' %', True)}</strong></td><td>{n(100 * y['p5'], 0, ' %', True)} a {n(100 * y['p95'], 0, ' %', True)}</td>"
                 f"<td>{n(100 * y['p25'], 0, ' %', True)} a {n(100 * y['p75'], 0, ' %', True)}</td>"
                 f"<td class='muted'>{n(100 * y['min'], 0, '', True)} · {n(100 * y['p1'], 0, '', True)} · {n(100 * y['p99'], 0, '', True)} · {n(100 * y.get('max'), 0, ' %', True) if y.get('max') is not None else 's/d'}</td>"
                 f"<td>{n(100 * y['p_perdida'], 0)}</td><td>{n(100 * y['p_caida20'], 0)}</td></tr>")
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
<p class="small">Hoy: {esc(hoy_q or "s/d")} (cuadrante mensual del signal). Medias de meses pasados de este activo, sin contrastar: con pocos meses, ruido.</p></div>
<div class="dblk wide"><h4>Simulación a 12 meses ({esc(r.get("moneda") or "")}; nominal salvo las filas «real»)</h4><table class="num"><thead><tr><th>Modelo</th><th>Mediana</th>
<th>{term("p5-p95", "Rango 90 %")}</th><th>Rango 50 %</th><th data-tip='Colas completas, sin recortar (informativo: con una sola historia y un motor no validado, poco fiables)'>Mín · p1 · p99 · Máx</th><th>P(perder)</th><th>P(caer ≥ 20 %)</th></tr></thead><tbody>{sims or f"<tr><td colspan=7 class=nd>{esc(r.get('historia_insuficiente') or 'sin historia suficiente')}</td></tr>"}</tbody></table>
<p class="small">No validado. La inflación de las filas «real» y de B es la que simula el motor para EE. UU. en cada trayectoria (no una previsión fija). Una acción individual puede salirse de cualquier rango por noticias propias (resultados, juicios, escisiones).</p></div>
{AV.ficha_v2(t, r, v2)}</div></div></details>'''


CSS = AV.CSS + AL.CSS + """
table.act td,table.act th{white-space:nowrap;padding:6px 6px}table.act td:first-child{white-space:normal;min-width:180px}table.act tr.grp th{background:var(--hl);color:var(--ink);font-size:13px}
.actlink{color:var(--ink);text-decoration:none;font-weight:600}.actlink:hover{text-decoration:underline}
"""
JS = """
(function(){document.addEventListener('click',function(e){var a=e.target.closest('a.actlink');if(!a)return;e.preventDefault();
var d=document.getElementById(a.getAttribute('href').slice(1));if(d){d.open=true;d.scrollIntoView({behavior:'smooth'})}});})();
"""
