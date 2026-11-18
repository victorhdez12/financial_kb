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

import re

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
    if v == v and round(v, dec) == 0:   # sin «−0,0» (prueba de uso 17-nov, B8)
        v = 0.0
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
        return "rojo", "en recesión"
    b = nw.get("banda")
    if b:
        return {"bajo": "verde", "medio": "ambar", "alto": "rojo"}.get(b, "gris"), f"{b} · p{nw.get('percentil')}"
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


CAB = {"crecimiento": ("Crecimiento", "PIB real frente a hace un año"),
       "inflacion": ("Inflación", "último dato a/a (IPC o IPCA)"),
       "empleo": ("Paro", "tasa (cambio en 12 meses, pp)"),
       "bonos": ("Bono 10 años", "tipo (euro: diferencial con Alemania; resto: cambio en 3 meses)"),
       "fiscal": ("Deuda · saldo", "deuda pública / PIB · saldo / PIB (FMI)"),
       "bolsa": ("Bolsa", "caída desde su máximo de 12 meses"),
       "confianza": ("CLI", "indicador adelantado OCDE (100 = tendencia) y dirección en 3 meses")}
ACTIVO_N = {"bolsa": "Bolsa", "bonos": "Bonos del Estado", "letras": "Letras (liquidez)", "vivienda": "Vivienda",
            "oro": "Oro"}


def sec_paises(s: dict, es: dict | None) -> str:
    pul = pulso_desde(s)
    if not pul:
        return '<div class="card"><p class="nd">Pulso por país no disponible.</p></div>'
    P = pul["paises"]
    leyenda = " ".join(chip(k, PALABRA[k]) for k in ("verde", "ambar", "rojo", "gris"))
    cab = "".join(f'<span data-tip="{esc(d)}">{esc(t)}</span>' for t, d in CAB.values())
    filas = []
    for c in [x for x in ORDEN if x in P]:
        r = P[c]
        if "error" in r:
            filas.append(f'<details class="pais"><summary><span class="pn">{esc(r.get("nombre", c))}</span>'
                         f'<span class="nd">sin datos ({esc(r["error"])})</span></summary></details>')
            continue
        celdas = []
        for k, (tit, desc) in CAB.items():
            v = r["colores"][k]
            ayuda = f"{tit}: {v['texto']} · {desc} · dato de {v['fecha']}"
            celdas.append(f'<span class="cell" data-l="{esc(tit)}">{chip(v["color"], v["cifra"], ayuda)}</span>')
        rc, rt = _banda_recesion(s, c)
        celdas.append(f'<span class="cell" data-l="Recesión">{chip(rc, rt, "Riesgo de recesión hoy: " + rt)}</span>')
        m = _motor(es, c)
        reg = m.get("regimen_dominante")
        reg_t = REG_LLANO.get(reg, "—") if reg else "no incluido en el motor"
        filas.append(f'''<details class="pais" id="pais-{esc(c)}"><summary>
<span class="pn">{esc(r["nombre"])} <span class="muted">{esc(c)}</span></span>
<span class="cells">{"".join(celdas)}</span></summary>
{_detalle(c, r, m, reg_t, s, es)}</details>''')
    return f'''<div class="intro"><p><strong>Los 18 países de un vistazo.</strong> Cada celda es una cifra real con un color
que la resume (reglas fijas). <strong>Pulsa un país</strong> para ver la explicación en frases, qué se espera (FMI), sus
probabilidades y escenarios, el dinero y todas las cifras con su fecha.</p>
<p class="small">Leyenda: {leyenda}. Pasa el ratón por una cifra o por el título de una columna para ver qué es y de
qué mes es el dato.{f' Semáforo calculado con los datos del {esc(pul["fecha"])}.' if pul.get("fecha") else ""}</p></div>
<div class="card ptabla"><div class="phead"><span>País</span><span class="cells">{cab}<span data-tip="nowcast descriptivo o fechado trimestral">Recesión</span></span></div>
{"".join(filas)}</div>
<details class="card"><summary><h3>¿Cómo se decide cada color?</h3></summary>
<p class="small">{esc(pul.get("aviso"))}</p><ul class="small">{"".join(f"<li><strong>{esc(CAB[k][0])}:</strong> {esc(pul['reglas'].get(k, ''))}</li>" for k in CAB)}
<li><strong>Recesión:</strong> rojo si el fechado trimestral marca recesión; si no, la banda del {term("nowcast")}
(bajo / medio / alto) frente a 1960-2004.</li></ul></details>'''


EURO_PANEL = {"DEU", "FRA", "ITA", "ESP", "NLD", "BEL", "PRT", "IRL", "FIN"}
# huecos de la fuente (no de la ingesta), comprobados el 17-nov-2026 con el warehouse: (país, inicio de la etiqueta) → texto
NO_PUBLICA = {
    **{(c, "CLI"): "la OCDE no publica el CLI de este país" for c in ("NLD", "BEL", "PRT", "IRL", "FIN", "SWE", "DNK", "NOR", "CHE")},
    ("CHE", "Tasa de paro"): "la OCDE no publica el paro armonizado mensual de Suiza",
    ("CHE", "Cambio en"): "la OCDE no publica el paro armonizado mensual de Suiza",
    ("CHE", "percentil del paro"): "la OCDE no publica el paro armonizado mensual de Suiza",
    ("AUS", "Producción industrial"): "Australia no publica producción industrial mensual",
    ("AUS", "percentil del IPC"): "IPC mensual de Australia solo desde 2024: historia corta",
    ("NOR", "Confianza del consumidor"): "la OCDE no publica la confianza del consumidor de Noruega",
    ("GBR", "dinero amplio"): "el FMI no publica el dinero amplio del Reino Unido",
    ("CHE", "dinero amplio"): "el FMI no publica el dinero amplio de Suiza en esta serie",
}


def _sin_dato(c: str, fila: tuple) -> tuple:
    """Si la cifra es «s/d» y la fuente no la publica para el país, lo dice en la columna de la fecha."""
    a, b, f = fila
    if "s/d" not in str(b) or (f and str(f).strip() not in ("—", "-", "None")):
        return fila
    txt = re.sub(r"<[^>]+>", "", str(a))
    for (pais, ini), motivo in NO_PUBLICA.items():
        if pais == c and (txt.startswith(ini) or ini.lower() in txt.lower()):
            return a, b, motivo
    return fila


def _tabla(filas) -> str:
    return ('<table class="num"><tbody>' + "".join(
        f"<tr><td>{a}</td><td><strong>{b}</strong></td><td class='muted'>{esc(f)}</td></tr>" for a, b, f in filas)
        + "</tbody></table>")


def _detalle(c: str, r: dict, m: dict, reg_t: str, s: dict, es: dict | None = None) -> str:
    cr, inf, em, ti, fi, bo, vi, co, di = (r.get(k) or {} for k in ("crecimiento", "inflacion", "empleo", "tipos",
                                                                    "fiscal", "bolsa", "vivienda", "confianza", "dinero"))
    fi_año = f"{fi.get('año')}{' (previsión FMI)' if fi.get('proyeccion') else ''}"
    # filas que nunca tendrán dato se ocultan (IPCA fuera del euro, diferencial de Alemania consigo misma o fuera del
    # euro); los huecos porque la fuente no lo publica se rotulan (prueba de uso 17-nov, B2)
    euro = bool(r.get("euro")) or c in EURO_PANEL
    mes3 = ti.get("mes_corto") or ti.get("mes")
    pct = lambda v, d: (n(v, 0, "") + (f" (desde {d})" if d else "")) if v is not None else n(None)  # noqa: E731
    bloques = [
        ("Crecimiento", [("PIB real " + term("a/a"), n(cr.get("pib_aa"), signo=True), cr.get("trimestre")),
                         ("PIB último trimestre, anualizado", n(cr.get("pib_trim_anualizado"), signo=True), cr.get("trimestre")),
                         ("Media de los últimos 10 años", n(cr.get("media_10a")) + " al año", ""),
                         ("Producción industrial a/a", n(cr.get("ip_aa"), signo=True), cr.get("ip_mes"))]),
        ("Inflación", [("Inflación general (" + esc(inf.get("general_fuente")) + ")", n(inf.get("general")), inf.get("general_mes")),
                       ("IPC nacional a/a (OCDE)", n(inf.get("ipc_aa")), inf.get("mes")),
                       ("IPCA a/a (BCE)", n(inf.get("hicp_aa")), inf.get("mes_hicp")) if euro else None,
                       ("IPC media 12 meses (la del motor)" + (" · 1 mes interpolado" if inf.get("huecos_media_12m") else ""),
                        n(inf.get("ipc_media_12m")), inf.get("mes_media_12m", "")),  # su mes es el del índice, no el del a/a
                       ("Subyacente a/a (OCDE)", n(inf.get("subyacente_aa")), inf.get("mes_sub")),
                       ("Subyacente IPCA a/a (BCE)", n(inf.get("hicp_sub_aa")), inf.get("mes_hicp_sub")) if euro else None,
                       (term("percentil") + " del IPC en su historia", pct(inf.get("pct_ipc"), inf.get("pct_ipc_desde")), "")]),
        ("Empleo", [("Tasa de paro", n(em.get("paro")), em.get("mes")),
                    (f"Cambio en {em.get('delta_meses', 12)} meses" + (" (el mes de hace 12 no se publicó)" if em.get("delta_meses") == 13 else ""),
                     n(em.get("delta_12m"), 1, " pp", True), ""),
                    (term("percentil") + " del paro en su historia", pct(em.get("pct_paro"), em.get("pct_paro_desde")), "")]),
        ("Tipos y bonos", [("Tipo a 3 meses" + (" (mismo mes)" if mes3 == ti.get("mes") else "")
                            + (f' <span class="muted">({esc(ti["fuente_corto"])})</span>' if ti.get("fuente_corto") else ""),
                            n(ti.get("corto_3m"), 2), mes3),
                           ("Bono a 10 años", n(ti.get("largo_10a"), 2), ti.get("mes")),
                           ("Cambio del 10 años en 3 meses", n(ti.get("delta_3m_10a"), 2, " pp", True), ""),
                           (term("diferencial") + " con Alemania (mismo mes)", n(ti.get("dif_alemania"), 2, " pp", True), ti.get("mes"))
                           if euro and c != "DEU" else None,
                           (term("curva") + " 10a − 3m", n(ti.get("curva_10a_3m"), 2, " pp", True), mes3),
                           (term("r − g") + " (aprox.)", n(ti.get("r_menos_g"), 1, " pp", True), ""),
                           (term("percentil") + " del 10 años en su historia", pct(ti.get("pct_10a"), ti.get("pct_10a_desde")), "")]),
        ("Cuentas públicas", [("Deuda pública bruta / PIB", n(fi.get("deuda_pib"), 0), fi_año),
                              ("Saldo público / PIB", n(fi.get("saldo_pib"), 1, " %", True), fi_año),
                              (term("saldo primario") + " / PIB", n(fi.get("saldo_primario_pib"), 1, " %", True), fi_año),
                              ("Intereses de la deuda / PIB", n(fi.get("intereses_pib"), 1), fi_año)]),
        ("Dinero y crédito", [(esc(di.get("agregado") or "Dinero"), n(di.get("aa"), signo=True), di.get("mes")),
                              ("M2 real (descontada la inflación)", n(di.get("real_aa"), signo=True), di.get("mes")) if "real_aa" in di else None,
                              ("M1 zona euro a/a", n(di.get("m1_aa"), signo=True), di.get("mes")) if "m1_aa" in di else None,
                              ("Préstamos a hogares (euro) a/a", n(di.get("prestamos_hogares_aa"), signo=True), di.get("mes")) if "m1_aa" in di else None,
                              ("Préstamos a empresas (euro) a/a", n(di.get("prestamos_empresas_aa"), signo=True), di.get("mes")) if "m1_aa" in di else None]),
        ("Mercados", [("Bolsa (precio, media mensual) a/a", n(bo.get("aa"), signo=True), bo.get("mes")),
                      ("Caída desde el máximo de 12 meses", n(bo.get("caida_max_12m"), signo=True), bo.get("mes")),
                      ("Vivienda (precio nominal) a/a", n(vi.get("precio_aa"), signo=True), vi.get("trimestre"))]),
        ("Confianza", [(term("CLI") + " OCDE (100 = tendencia)", n(co.get("cli"), 1, ""), co.get("mes")),
                       ("Cambio del CLI en 3 meses", n(co.get("delta_3m_cli"), 2, "", True), ""),
                       ("Confianza empresarial (OCDE)", n(co.get("empresas"), 1, ""), ""),
                       ("Confianza del consumidor (OCDE)", n(co.get("consumidores"), 1, ""), "")]),
    ]
    html_bl = "".join(f'<div class="dblk"><h4>{t}</h4>{_tabla([_sin_dato(c, f) for f in fs if f])}</div>' for t, fs in bloques)
    nota_din = (f'<p class="small">Dinero: {esc(di.get("nota"))}. ' if di.get("nota") else '<p class="small">') + \
        "El dinero es descriptivo: en nuestras pruebas (INT-6, 1870-2004) su crecimiento no anticipó la inflación ni la bolsa.</p>"

    # Qué se espera (FMI)
    pv = r.get("prevision_fmi") or {}
    años = sorted(pv)
    fmi = ""
    if años:
        filas = [("Crecimiento del PIB real", "crecimiento", 1, True), ("Inflación media del año", "inflacion", 1, False),
                 ("Paro", "paro", 1, False), ("Deuda pública / PIB", "deuda", 0, False), ("Saldo público / PIB", "saldo", 1, True)]
        cab = "".join(f"<th>{esc(a)}</th>" for a in años)
        cuerpo = "".join("<tr><td>" + esc(t) + "</td>" + "".join(f"<td><strong>{n((pv[a] or {}).get(k), d, ' %', sg)}</strong></td>" for a in años) + "</tr>"
                         for t, k, d, sg in filas)
        fmi = (f'<div class="dblk"><h4>Qué se espera (previsión del FMI, WEO oct-2026)</h4><table class="num"><thead><tr><th></th>{cab}</tr></thead>'
               f'<tbody>{cuerpo}</tbody></table><p class="small">Previsión externa del FMI (no es nuestra ni está validada aquí). '
               f'Sirve de referencia de «lo esperado»: las sorpresas frente a ella son lo que mueve los mercados.</p></div>')

    # Probabilidades y escenarios (motor INT-11)
    if m:
        ab = m.get("abanicos") or {}
        filas_ab = []
        for a, nom in ACTIVO_N.items():
            q = ab.get(a)
            if not q:
                continue
            filas_ab.append((nom, q))
        filas_ab.sort(key=lambda x: -(x[1].get("p50") or -9))
        tab = "".join(
            f"<tr><td>{esc(nom)}</td><td><strong>{n(100 * q['p50'], 1, ' %', True)}</strong></td>"
            f"<td>{n(100 * q['p5'], 0, ' %', True)} a {n(100 * q['p95'], 0, ' %', True)}</td>"
            f"<td>{n(100 * q['p25'], 0, ' %', True) if q.get('p25') is not None else n(None)} a {n(100 * q['p75'], 0, ' %', True) if q.get('p75') is not None else n(None)}</td>"
            f"<td>{n(100 * q['p_neg'], 0) if q.get('p_neg') is not None else n(None)}</td></tr>" for nom, q in filas_ab)
        ps = m.get("pesos_regimen") or {}
        pes = ", ".join(f"{REG_LLANO.get(k, k)} {round(100 * w)} %" for k, w in sorted(ps.items(), key=lambda kv: -kv[1]) if w and w >= 0.01)
        if max(ps.values() or [0]) >= 0.99:
            pes = ""
        mot = (f'<div class="dblk wide"><h4>Probabilidades y escenarios a 12 meses (motor, {term("validado en el pasado")})</h4>'
               f'<p class="small">Situación de partida: «{esc(reg_t)}»{(" — " + esc(pes)) if pes else ""}. '
               f'Rentabilidades REALES (descontada la inflación) en moneda local, de dic-2026 a nov-2027.</p>'
               f'<table class="num"><thead><tr><th>Activo (ordenado por mediana)</th><th>Mediana</th><th>{term("p5-p95", "Rango 90 %")}</th>'
               f'<th>Rango 50 %</th><th>P(perder en términos reales)</th></tr></thead><tbody>{tab}</tbody></table>'
               f'<p>P(bolsa real ≤ −20 % en 12 meses) <strong>{_p(m.get("p_caida_bolsa_20"))}</strong> · '
               f'P(inflación &gt; 5 % el próximo año) <strong>{_p(m.get("p_inflacion_5"))}</strong>. '
               f'<a href="#escenarios" data-pais="{esc(c)}">Ver gráfico →</a></p>'
               f'<p class="small">Lectura: la mediana es el resultado típico; el rango 90 % es lo que pasó 9 de cada 10 '
               f'veces en situaciones parecidas (1870-2004). El orden de la tabla NO es una recomendación de compra: '
               f'las medianas se parecen mucho entre sí frente a la anchura de los rangos. El {term("régimen")} solo '
               f'mira la inflación media de 12 meses y si el PIB ha caído con fuerza (no el ritmo de este año, ni '
               f'bonos, ni deuda).</p></div>')
    else:
        mot = ('<div class="dblk wide"><h4>Probabilidades y escenarios</h4><p class="small">Este país no está en el motor '
               'de escenarios (que usa 14 países con historia desde 1870); solo en el termómetro y el nowcast.</p></div>')
    t2 = ((s.get("termometro") or {}).get("paises") or {}).get(c) or {}
    sal = (t2.get("salida") or t2.get("T2") or {}) if isinstance(t2, dict) else {}
    rec = ""
    if (t2.get("estado") or {}).get("en_recesion"):
        rec = (f'<p><strong>En recesión según el fechado trimestral.</strong> {esc(json.dumps(sal, ensure_ascii=False)) if sal else ""}</p>')
    viejo = (f'<p class="small">▲ Datos con retraso: {esc(", ".join(r["datos_antiguos"]))}.</p>' if r.get("datos_antiguos") else "")
    nota = f'<p class="small">▲ {esc(r["nota"])}</p>' if r.get("nota") else ""
    return (f'<div class="pdet"><p class="frase">{esc(r["frase"])}</p>{nota}{viejo}{rec}'
            f'<div class="dgrid">{mot}{fmi}{html_bl}</div>{nota_din}</div>')


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
<li><strong>En cada pestaña</strong>, el recuadro «Qué significa esto para ti» resume en lenguaje llano qué mirar.</li>
<li><strong>Gráficos:</strong> pulsa (o toca) cualquier gráfico, minigráfico o abanico para verlo en grande; se cierra
con Esc, tocando fuera o con «Cerrar». El panel recuerda la última pestaña que abriste.</li>
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
    "atlas": ("Qué activos fueron mejor o peor en cada situación económica (1870-2004, 14 países ricos de la base JST).",
              "Las tarjetas resaltadas son las de la situación actual. Cada cifra dice si está establecida o es solo "
              "descriptiva."),
    "cartera": ("Qué haría tu cartera de seguimiento (B0, B1, B1′) este mes.",
                "Hoy la volatilidad está por debajo del umbral, así que B1 no recorta la bolsa. Las rentabilidades "
                "empiezan a aparecer en diciembre (los datos llegan con ≈ 2 meses de retraso)."),
    "activos": ("Tus acciones, ETF y materias primas: cómo van, su riesgo y dos simulaciones a 12 meses.",
                "La tabla resume; pulsa un activo para su ficha. Las simulaciones no están validadas y no son "
                "recomendaciones: sirven para ver el RANGO de lo que puede pasar, no un precio objetivo."),
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
        ba, bb = (ia.get(k) or {}).get("percentil_base"), r.get("percentil_base")
        if ba is not None and bb is not None and ba != bb:   # bases distintas (mensual vs nativa): no comparables
            continue
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
.cells{display:grid;grid-template-columns:.8fr .7fr 1fr 1.25fr 1.2fr .8fr .8fr 1fr;gap:4px;align-items:center}
.cell .chip{white-space:normal;line-height:1.25;padding:2px 7px;font-variant-numeric:tabular-nums}
details.pais{border-bottom:1px solid var(--grid)}details.pais>summary{display:grid;grid-template-columns:150px 1fr;gap:8px;
padding:8px 0;cursor:pointer;list-style:none;align-items:center}details.pais>summary::-webkit-details-marker{display:none}
details.pais>summary:hover{background:var(--hl)}details.pais[open]>summary{background:var(--hl)}
.pn{font-weight:600}.pn::before{content:"▸ ";color:var(--muted)}details.pais[open] .pn::before{content:"▾ "}
.frase1{grid-column:1/-1;font-size:12.5px;color:var(--ink2);display:none}
.pdet{padding:6px 4px 14px}.frase{font-size:15px}
.dgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:10px}
.dblk{border:1px solid var(--grid);border-radius:6px;padding:6px 10px}.dblk.wide{grid-column:1/-1}.dblk td:nth-child(2),.dblk td:nth-child(3){white-space:nowrap}.dblk h4{margin:4px 0}.dblk td{padding:4px 6px}
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
