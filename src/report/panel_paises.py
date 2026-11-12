"""Partes del panel web pensadas para LEER FÁCIL (src/report/panel.py las monta):

- `sec_paises`: pestaña «Países» — los 18 países de un vistazo (semáforo por tema) y, al pulsar, el detalle completo de
  cada uno (frase en lenguaje llano + todas las cifras + lo que dicen los modelos de ese país).
- `guia`: «Cómo leer este panel» (desplegable arriba).
- `INTRO`: una frase al principio de cada pestaña y su «¿cómo leo esta pestaña?».
- `GLOSARIO` y `term()`: definiciones al pasar el ratón; el glosario completo va en «Estado y avisos».
- `cambios_semana`: qué se ha movido frente al reporte semanal anterior (solo comparaciones, sin reglas nuevas).

Todo es presentación: no cambia ningún modelo, probabilidad ni señal. El pulso por país sale de
src/report/pulso_paises.py (descriptivo, reglas fijas no validadas).
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ORDEN = ["USA", "DEU", "FRA", "ITA", "ESP", "GBR", "JPN", "NLD", "BEL", "PRT", "IRL", "FIN", "SWE", "DNK", "NOR", "CHE",
         "CAN", "AUS"]
TEMAS = [("crecimiento", "Crecimiento"), ("inflacion", "Inflación"), ("empleo", "Empleo"), ("bonos", "Bonos"),
         ("fiscal", "Cuentas públicas"), ("bolsa", "Bolsa"), ("confianza", "Confianza")]
ICO = {"verde": "●", "ambar": "▲", "rojo": "■", "gris": "○"}
PALABRA = {"verde": "bien", "ambar": "vigilar", "rojo": "mal", "gris": "sin dato"}
REG_LLANO = {"expansion": "sin caída del PIB · inflación ≤ 3 %", "sobrecalentamiento": "sin caída del PIB · inflación > 3 %",
             "estanflacion": "PIB cayendo · inflación > 3 %", "crecimiento_bajo": "PIB cayendo · inflación ≤ 3 %"}

GLOSARIO = {
    "percentil": "Dónde está el dato frente a su propia historia: 50 = lo normal, 90 = más alto que el 90 % de las "
                 "veces, 10 = más bajo que el 90 % de las veces.",
    "p5-p95": "Abanico del 90 %: en el pasado, 9 de cada 10 veces el resultado cayó dentro. El punto es la mediana "
              "(lo más típico).",
    "régimen": "La «situación» económica. En el motor de escenarios son 4, según solo dos cosas: si la inflación "
               "media de 12 meses supera el 3 % y si el PIB por habitante está por debajo de su media de los 10 años "
               "anteriores (eso solo pasa con caídas fuertes).",
    "cuadrante": "Clasificación mensual de EE. UU. según si el crecimiento y la inflación suben o bajan: Goldilocks "
                 "(crece, inflación baja), Reflación (crece, inflación sube), Estanflación (no crece, inflación sube), "
                 "Deflación/recesión (no crece, inflación baja).",
    "diferencial": "Lo que paga de más el bono a 10 años de un país frente al de Alemania. Cuanto más alto, más "
                   "riesgo ve el mercado en esa deuda.",
    "r − g": "Tipo de interés a 10 años menos crecimiento nominal de la economía. Si es positivo, la deuda/PIB "
             "tiende a subir sola salvo que haya superávit primario.",
    "saldo primario": "Saldo público sin contar los intereses de la deuda. El saldo total = primario − intereses.",
    "CLI": "Indicador adelantado compuesto de la OCDE: 100 = la economía va en su tendencia; por debajo y bajando "
           "suele anticipar menos crecimiento en los meses siguientes.",
    "curva": "Tipo a 10 años menos tipo a 3 meses. Cuando es negativa («invertida») suele preceder recesiones.",
    "nowcast": "Foto del momento con 6 indicadores, comparada con la historia 1960-2004. Describe, no predice.",
    "termómetro": "Modelo histórico (1871-2004) del riesgo de entrar o salir de una recesión en ~12 meses.",
    "Brier": "Puntuación del acierto de una probabilidad (menor es mejor). «Mejora de Brier» = cuánto acierta más "
             "que usar siempre la frecuencia histórica.",
    "validado en el pasado": "Funcionó con datos hasta 2004 que el modelo no vio al ajustarse; desde 2026 se "
                             "registra cada mes para comprobar si sigue funcionando en vivo.",
    "a/a": "Variación frente al mismo mes o trimestre del año anterior.",
    "pp": "Puntos porcentuales: de 3 % a 4 % es +1 pp.",
    "VIX": "Volatilidad esperada de la bolsa de EE. UU. Normal ≈ 12-20; por encima de 30, miedo.",
    "HY / CCC": "Diferencial de los bonos de empresas de peor calidad (alto rendimiento / CCC) frente a la deuda "
                "pública: sube cuando el mercado teme impagos.",
    "B0 / B1 / B1′": "Tu cartera de seguimiento: B0 fija 70/15/15; B1 baja la bolsa cuando la volatilidad supera el "
                     "umbral; B1′ igual con volatilidad diaria.",
}


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def term(palabra: str, texto: str | None = None) -> str:
    d = GLOSARIO.get(palabra)
    t = esc(texto or palabra)
    return f'<abbr class="term" tabindex="0" data-tip="{esc(d)}">{t}</abbr>' if d else t


def n(v, dec=1, suf=" %", signo=False) -> str:
    if v is None:
        return '<span class="nd">s/d</span>'
    try:
        v = float(v)
    except (TypeError, ValueError):
        return esc(v)
    s = f"{v:+,.{dec}f}" if signo else f"{v:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".").replace("-", "−") + suf


def chip(color: str, texto: str, titulo: str = "") -> str:
    return (f'<span class="chip c-{esc(color)}" data-tip="{esc(titulo)}"><span aria-hidden="true">{ICO.get(color, "○")}'
            f'</span> {esc(texto)}</span>')


def pulso_desde(s: dict) -> dict | None:
    p = s.get("pulso_paises")
    if isinstance(p, dict) and p.get("paises"):
        return p
    try:  # signals anteriores al 12-nov no lo traen: se calcula con el warehouse (solo lectura)
        from datetime import date

        from src.report import pulso_paises as PP
        from src.warehouse import db
        con = db.connect(read_only=True)
        try:
            return PP.pulso(con, date.fromisoformat(str(s.get("asof"))[:10]) if s.get("asof") else date.today())
        finally:
            con.close()
    except Exception:  # noqa: BLE001
        return None


def _banda_recesion(s: dict, c: str) -> tuple[str, str]:
    t = ((s.get("termometro") or {}).get("paises") or {}).get(c) or {}
    nw = ((s.get("nowcast") or {}).get("paises") or {}).get(c) or {}
    if (t.get("estado") or {}).get("en_recesion"):
        return "rojo", "en recesión (fechado)"
    b = nw.get("banda")
    if b:
        return {"bajo": "verde", "medio": "ambar", "alto": "rojo"}.get(b, "gris"), f"nowcast {b} (p{nw.get('percentil')})"
    return "gris", "sin dato"


def _p(x) -> str:
    """Probabilidad del motor ({"p", "ic90"} o número) en %, con su IC 90 % de parámetros si existe."""
    if isinstance(x, dict):
        ic = x.get("ic90") if x.get("ic_estimable", True) else None
        x, ic = x.get("p"), ic
    else:
        ic = None
    if x is None:
        return "s/d"
    s = n(100 * float(x), 0)
    return s + (f' <span class="muted">(IC 90 % {n(100 * ic[0], 0, "")}-{n(100 * ic[1], 0)})</span>' if ic else "")


def _motor(es: dict | None, c: str) -> dict:
    return ((es or {}).get("paises") or {}).get(c) or {}


def sec_paises(s: dict, es: dict | None) -> str:
    pul = pulso_desde(s)
    if not pul:
        return '<div class="card"><p class="nd">Pulso por país no disponible.</p></div>'
    P = pul["paises"]
    leyenda = " · ".join(f'{chip(k, PALABRA[k])}' for k in ("verde", "ambar", "rojo", "gris"))
    cab = "".join(f"<span>{esc(t)}</span>" for _, t in TEMAS)
    filas = []
    for c in [x for x in ORDEN if x in P]:
        r = P[c]
        if "error" in r:
            filas.append(f'<details class="pais"><summary><span class="pn">{esc(r.get("nombre", c))}</span>'
                         f'<span class="nd">sin datos ({esc(r["error"])})</span></summary></details>')
            continue
        col = r["colores"]
        chips = "".join(f'<span class="cell" data-l="{esc(t)}">{chip(col[k]["color"], col[k]["texto"], t + ": " + col[k]["texto"])}</span>'
                        for k, t in TEMAS)
        rc, rt = _banda_recesion(s, c)
        m = _motor(es, c)
        reg = m.get("regimen_dominante")
        reg_t = REG_LLANO.get(reg, "—") if reg else "no incluido en el motor"
        filas.append(f'''<details class="pais" id="pais-{esc(c)}"><summary>
<span class="pn">{esc(r["nombre"])} <span class="muted">{esc(c)}</span></span>
<span class="cells">{chips}<span class="cell" data-l="Recesión">{chip(rc, rt, "Riesgo de recesión: " + rt)}</span></span>
<span class="frase1">{esc(r["frase"])}</span></summary>
{_detalle(c, r, m, reg_t, s)}</details>''')
    return f'''<div class="intro"><p><strong>Los 18 países de un vistazo.</strong> Cada fila es un país y cada color resume un
tema con reglas fijas y sencillas. <strong>Pulsa un país</strong> para ver la explicación en frases, todas las cifras y lo que
dicen los modelos.</p><p class="small">Leyenda: {leyenda}. Pasa el ratón por un color para ver qué significa.</p></div>
<div class="card"><div class="phead"><span>País</span><span class="cells">{cab}<span>Recesión</span></span></div>
{"".join(filas)}</div>
<details class="card"><summary><h3>¿Cómo se decide cada color?</h3></summary>
<p class="small">{esc(pul.get("aviso"))}</p><ul class="small">{"".join(f"<li><strong>{esc(t)}:</strong> {esc(pul['reglas'].get(k, ''))}</li>" for k, t in TEMAS)}
<li><strong>Recesión:</strong> rojo si el fechado trimestral la marca; si no, la banda del {term("nowcast")} (bajo / medio / alto).</li></ul></details>'''


def _detalle(c: str, r: dict, m: dict, reg_t: str, s: dict) -> str:
    cr, inf, em, ti, fi, bo, vi, co = (r.get(k) or {} for k in
                                       ("crecimiento", "inflacion", "empleo", "tipos", "fiscal", "bolsa", "vivienda", "confianza"))
    fi_año = f"{fi.get('año')}{' (previsión FMI)' if fi.get('proyeccion') else ''}"
    filas = [
        ("Crecimiento", [("PIB real " + term("a/a"), n(cr.get("pib_aa"), signo=True), cr.get("trimestre", "")[:7]),
                         ("PIB último trimestre (anualizado)", n(cr.get("pib_trim_anualizado"), signo=True), ""),
                         ("Media de los últimos 10 años", n(cr.get("media_10a")) + " al año", ""),
                         ("Producción industrial a/a", n(cr.get("ip_aa"), signo=True), (cr.get("ip_mes") or "")[:7]),
                         ("Previsión del FMI para este año", n(cr.get("weo_crec_año"), signo=True), "WEO")]),
        ("Inflación", [("IPC a/a (último mes)", n(inf.get("ipc_aa")), (inf.get("mes") or "")[:7]),
                       ("IPC media 12 meses (la que usa el motor)", n(inf.get("ipc_media_12m")), ""),
                       ("Subyacente a/a (sin energía ni alimentos)", n(inf.get("subyacente_aa")), (inf.get("mes_sub") or "")[:7]),
                       (term("percentil") + " del IPC en su historia", n(inf.get("pct_ipc"), 0, ""), "")]),
        ("Empleo", [("Tasa de paro", n(em.get("paro")), (em.get("mes") or "")[:7]),
                    ("Cambio en 12 meses", n(em.get("delta_12m"), 1, " pp", True), ""),
                    (term("percentil") + " del paro en su historia", n(em.get("pct_paro"), 0, ""), "")]),
        ("Tipos y bonos", [("Tipo a 3 meses", n(ti.get("corto_3m"), 2), ""),
                           ("Bono a 10 años", n(ti.get("largo_10a"), 2), (ti.get("mes") or "")[:7]),
                           ("Cambio del 10 años en 3 meses", n(ti.get("delta_3m_10a"), 2, " pp", True), ""),
                           (term("diferencial") + " frente a Alemania", n(ti.get("dif_alemania"), 2, " pp", True), ""),
                           (term("curva") + " 10a − 3m", n(ti.get("curva_10a_3m"), 2, " pp", True), ""),
                           (term("r − g"), n(ti.get("r_menos_g"), 1, " pp", True), ""),
                           (term("percentil") + " del 10 años en su historia", n(ti.get("pct_10a"), 0, ""), "")]),
        ("Cuentas públicas", [("Deuda pública bruta / PIB", n(fi.get("deuda_pib"), 0), fi_año),
                              ("Saldo público / PIB", n(fi.get("saldo_pib"), 1, " %", True), fi_año),
                              (term("saldo primario") + " / PIB", n(fi.get("saldo_primario_pib"), 1, " %", True), fi_año),
                              ("Intereses de la deuda / PIB", n(fi.get("intereses_pib"), 1), fi_año)]),
        ("Mercados", [("Bolsa (precio) a/a", n(bo.get("aa"), signo=True), (bo.get("mes") or "")[:7]),
                      ("Caída desde el máximo de 12 meses", n(bo.get("caida_max_12m"), signo=True), ""),
                      ("Vivienda (precio) a/a", n(vi.get("precio_aa"), signo=True), (vi.get("trimestre") or "")[:7])]),
        ("Confianza", [(term("CLI") + " OCDE (100 = tendencia)", n(co.get("cli"), 1, ""), (co.get("mes") or "")[:7]),
                       ("Cambio del CLI en 3 meses", n(co.get("delta_3m_cli"), 2, "", True), ""),
                       ("Confianza empresarial", n(co.get("empresas"), 1, ""), ""),
                       ("Confianza del consumidor", n(co.get("consumidores"), 1, ""), "")]),
    ]
    bloques = "".join(f'<div class="dblk"><h4>{t}</h4><table class="num"><tbody>' +
                      "".join(f"<tr><td>{a}</td><td><strong>{b}</strong></td><td class='muted'>{esc(f)}</td></tr>" for a, b, f in fs)
                      + "</tbody></table></div>" for t, fs in filas)
    if m:
        ps = m.get("pesos_regimen") or {}
        pes = ", ".join(f"{REG_LLANO.get(k, k)} {round(100 * w)} %" for k, w in sorted(ps.items(), key=lambda kv: -kv[1]) if w and w >= 0.01)
        if max(ps.values() or [0]) >= 0.99:
            pes = ""
        mot = (f'<p><strong>Motor de escenarios ({term("validado en el pasado")}):</strong> situación de partida '
               f'«{esc(reg_t)}»{(" — " + esc(pes)) if pes else ""}. P(bolsa real ≤ −20 % en 12 meses) '
               f'<strong>{_p(m.get("p_caida_bolsa_20"))}</strong>; P(inflación &gt; 5 %) <strong>{_p(m.get("p_inflacion_5"))}</strong>. '
               f'<a href="#escenarios" data-pais="{esc(c)}">Ver sus abanicos de rentabilidad →</a></p>'
               f'<p class="small">Ojo: el {term("régimen")} del motor solo mira la inflación media de 12 meses y si el PIB '
               f'ha caído con fuerza; no mira el ritmo de este año, ni los bonos, ni la deuda. Por eso un país estancado '
               f'puede salir «sin caída». Léelo junto con los colores de arriba.</p>')
    else:
        mot = '<p class="small">Este país no está en el motor de escenarios (solo en el termómetro y el nowcast).</p>'
    viejo = (f'<p class="small">▲ Datos con retraso: {esc(", ".join(r["datos_antiguos"]))}.</p>'
             if r.get("datos_antiguos") else "")
    return f'<div class="pdet"><p class="frase">{esc(r["frase"])}</p>{mot}{viejo}<div class="dgrid">{bloques}</div></div>'


def guia() -> str:
    return f'''<details class="guia"><summary><strong>¿Cómo leo este panel?</strong> <span class="muted">(1 minuto)</span></summary>
<ol>
<li><strong>Empieza por el resumen</strong> (justo debajo): 5-6 frases con lo importante de la semana.</li>
<li><strong>«Qué ha cambiado»</strong> te dice solo lo que se ha movido desde el domingo anterior.</li>
<li><strong>Pestaña Países:</strong> los 18 países con colores ({chip("verde", "bien")} {chip("ambar", "vigilar")}
{chip("rojo", "mal")}). Pulsa un país para ver todo su detalle.</li>
<li><strong>Escenarios 12 meses:</strong> rangos probables de rentabilidad de cada activo por país. Lee la barra
(el abanico {term("p5-p95")}), no un número suelto.</li>
<li><strong>Qué funciona en cada régimen:</strong> qué activos fueron mejor o peor en cada situación, con más de un siglo
de datos.</li>
<li><strong>Mi cartera:</strong> qué haría cada versión de tu cartera de seguimiento este mes.</li>
<li><strong>Estado y avisos:</strong> cuánto fiarte de cada herramienta, datos con problemas y el glosario.</li>
</ol>
<p class="small">Cuánto fiarte: <span class="badge b-ok"><span>●</span> establecido</span> = superó su prueba con datos
hasta 2004 · <span class="badge b-warn"><span>◐</span> frágil</span> = la superó por poco ·
<span class="badge b-no"><span>○</span> no establecido</span> / <span class="badge b-desc"><span>◌</span> descriptivo</span> =
solo describe. Nada está confirmado todavía en vivo (los registros empezaron en 2026). Las palabras
<abbr class="term" tabindex="0" data-tip="Así: pasa el ratón o toca para ver la definición.">subrayadas</abbr> tienen
definición al pasar el ratón.</p></details>'''


INTRO = {
    "paises": ("Cómo está cada país hoy, en colores y en frases.",
               "Una fila por país; los colores salen de reglas fijas (no son predicciones). Pulsa el país para el detalle."),
    "hoy": ("La foto de esta semana: situación de EE. UU., riesgo de recesión por país, liquidez y crédito.",
            "Mira primero las tarjetas grandes; las tablas de abajo son el detalle. En las tablas, fíjate en el "
            "percentil (dónde está el dato frente a su historia) y en la fecha del dato."),
    "escenarios": ("Qué rango de rentabilidad real a 12 meses es razonable para cada activo y país.",
                   "Elige el país. Cada barra es un abanico del 90 % (p5-p95) y el punto la mediana. Debajo, la "
                   "probabilidad de una caída fuerte de la bolsa y de inflación alta, con su acierto medido."),
    "atlas": ("Qué activos fueron mejor o peor en cada situación económica (1870-2004, 18 países).",
              "Las tarjetas resaltadas son las de la situación actual. Cada cifra dice si está establecida o es solo "
              "descriptiva."),
    "cartera": ("Qué haría tu cartera de seguimiento (B0, B1, B1′) este mes.",
                "Hoy la volatilidad está por debajo del umbral, así que B1 no recorta la bolsa. Las rentabilidades "
                "empiezan a aparecer en diciembre (los datos llegan con ≈ 2 meses de retraso)."),
    "estado": ("Cuánto fiarte de cada herramienta, avisos de datos y glosario.",
               "Si una fuente falla o un dato está viejo, sale aquí. El glosario explica cada término."),
}


def intro(k: str) -> str:
    a, b = INTRO.get(k, ("", ""))
    if not a:
        return ""
    return (f'<div class="enfrase"><p><strong>En una frase:</strong> {esc(a)}</p>'
            f'<details><summary>¿Cómo leo esta pestaña?</summary><p class="small">{esc(b)}</p></details></div>')


def glosario_html() -> str:
    return ('<details class="card" id="glosario"><summary><h3>Glosario</h3></summary><dl class="glos">'
            + "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in GLOSARIO.items()) + "</dl></details>")


def _prev_signal(s: dict, carpeta: Path) -> dict | None:
    asof = str(s.get("asof") or "")[:10]
    xs = sorted(p for p in carpeta.glob("*_signal.json") if p.name[:10] < asof)
    if not xs:
        return None
    try:
        return json.loads(xs[-1].read_text())
    except Exception:  # noqa: BLE001
        return None


def cambios_semana(s: dict, carpeta: Path) -> str:
    prev = _prev_signal(s, carpeta)
    if not prev:
        return '<p class="small nd">Sin reporte anterior con el que comparar.</p>'
    out = []
    g = lambda d, *ks: _get(d, *ks)  # noqa: E731
    pares = [("Cuadrante de EE. UU.", ("regime", "quadrant")), ("Crédito", ("credit", "light")),
             ("Liquidez", ("liquidity", "state")), ("Ciclo de deuda", ("debt_cycle", "phase")),
             ("Nowcast agregado", ("nowcast", "agregado", "banda"))]
    for nom, ks in pares:
        a, b = g(prev, *ks), g(s, *ks)
        if a is not None and b is not None and a != b:
            out.append(f"<li><strong>{esc(nom)}</strong>: {esc(a)} → <strong>{esc(b)}</strong></li>")
    for c in ORDEN:
        a, b = g(prev, "nowcast", "paises", c, "banda"), g(s, "nowcast", "paises", c, "banda")
        if a and b and a != b:
            out.append(f"<li>Nowcast de {esc(c)}: {esc(a)} → <strong>{esc(b)}</strong></li>")
        a, b = g(prev, "termometro", "paises", c, "estado", "en_recesion"), g(s, "termometro", "paises", c, "estado", "en_recesion")
        if a is not None and b is not None and a != b:
            out.append(f"<li>{esc(c)}: {'entra en' if b else 'sale de'} recesión según el fechado</li>")
        pa, pb = g(prev, "pulso_paises", "paises", c, "colores") or {}, g(s, "pulso_paises", "paises", c, "colores") or {}
        for k, t in TEMAS:
            ca, cb = (pa.get(k) or {}).get("color"), (pb.get(k) or {}).get("color")
            if ca and cb and ca != cb:
                out.append(f"<li>{esc(c)} · {esc(t)}: {PALABRA[ca]} → <strong>{PALABRA[cb]}</strong> "
                           f"({esc((pb.get(k) or {}).get('texto'))})</li>")
    ia = {r.get("indicador"): r for r in (g(prev, "indicators") or []) if isinstance(r, dict)}
    for r in g(s, "indicators") or []:
        if not isinstance(r, dict):
            continue
        k = r.get("indicador")
        pa, pb = (ia.get(k) or {}).get("percentil_hist"), r.get("percentil_hist")
        if pa is not None and pb is not None and abs(pb - pa) >= 15:   # salto grande frente a su historia
            out.append(f"<li>{esc(k)}: percentil {pa:.0f} → <strong>{pb:.0f}</strong></li>")
    fa = esc(str(prev.get("asof"))[:10])
    if not out:
        return f'<p class="small">Sin cambios relevantes frente al reporte del {fa}.</p>'
    return f'<p class="small">Frente al reporte del {fa}:</p><ul class="cambios">{"".join(out[:20])}</ul>'


def _get(d, *ks):
    for k in ks:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


CSS = """
.guia,.enfrase,.intro{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:10px 14px;margin:10px 0}
.guia summary,.enfrase summary{cursor:pointer}.guia ol{margin:6px 0;padding-left:20px}.guia li{margin:3px 0}
.enfrase details summary{color:var(--s1);font-size:13.5px}
abbr.term{text-decoration:underline dotted;text-underline-offset:3px;cursor:help}
.chip{display:inline-flex;gap:4px;align-items:center;border-radius:999px;padding:1px 8px;font-size:12px;white-space:nowrap;
border:1px solid var(--border);background:var(--page)}
.chip.c-verde>span{color:var(--good)}.chip.c-ambar>span{color:var(--warn)}.chip.c-rojo>span{color:var(--crit)}.chip.c-gris>span{color:var(--muted)}
.chip.c-verde{box-shadow:inset 3px 0 0 var(--good)}.chip.c-ambar{box-shadow:inset 3px 0 0 var(--warn)}.chip.c-rojo{box-shadow:inset 3px 0 0 var(--crit)}
.phead{display:grid;grid-template-columns:150px 1fr;gap:8px;font-size:12px;color:var(--ink2);font-weight:600;padding:0 0 6px;border-bottom:1px solid var(--grid)}
.phead .cells span{white-space:nowrap}
.cells{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:4px;align-items:center}
.cell .chip{max-width:100%;overflow:hidden;text-overflow:ellipsis}
details.pais{border-bottom:1px solid var(--grid)}details.pais>summary{display:grid;grid-template-columns:150px 1fr;gap:8px;
padding:8px 0;cursor:pointer;list-style:none;align-items:center}details.pais>summary::-webkit-details-marker{display:none}
details.pais>summary:hover{background:var(--hl)}details.pais[open]>summary{background:var(--hl)}
.pn{font-weight:600}.pn::before{content:"▸ ";color:var(--muted)}details.pais[open] .pn::before{content:"▾ "}
.frase1{grid-column:1/-1;font-size:12.5px;color:var(--ink2);display:none}
.pdet{padding:6px 4px 14px}.frase{font-size:15px}
.dgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:10px}
.dblk{border:1px solid var(--grid);border-radius:6px;padding:6px 10px}.dblk h4{margin:4px 0}.dblk td{padding:4px 6px}
.cambios{margin:4px 0;padding-left:20px}.cambios li{margin:2px 0}
dl.glos dt{font-weight:600;margin-top:8px}dl.glos dd{margin:2px 0 0 0;color:var(--ink2)}
@media (max-width:860px){.phead{display:none}details.pais>summary{grid-template-columns:1fr}
.cells{grid-template-columns:repeat(2,minmax(0,1fr))}.cell::before{content:attr(data-l) " ";font-size:11px;color:var(--muted);display:block}
.frase1{display:block}}
"""

JS = """
(function(){document.addEventListener('click',function(e){var a=e.target.closest('a[data-pais]');if(!a)return;
var sel=document.getElementById('pais');if(sel){sel.value=a.dataset.pais;sel.dispatchEvent(new Event('change'))}
var b=document.querySelector('nav.tabs button[data-t="escenarios"]');if(b){e.preventDefault();b.click();scrollTo(0,0)}});})();
"""
