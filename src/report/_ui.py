"""Piezas comunes de interfaz del panel (UX v2, 17-nov-2026): visor de gráficos ampliables, navegación, «qué
significa esto para ti», leyenda de colores, «volver arriba» y ajustes de legibilidad.

Solo presentación: aquí no se calcula ni se cambia ninguna cifra. Todo va inline (sin librerías ni red).
Lo usa `src/report/panel.py`; los módulos de cada pestaña no necesitan saber nada de esto: el visor detecta solo
cualquier `<svg>` con viewBox, `<img>` o barra `.segbar` dentro de `<main>` (o lo marcado con `data-zoom`).
Para excluir un elemento: `data-zoom="no"`. Título/nota propios opcionales: `data-zoom-titulo`, `data-zoom-nota`.
"""
from __future__ import annotations

import html

from src.report import panel_paises as PP


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


# icono (símbolo de texto, sin emoji en color: ︎ fuerza la variante de texto) y descripción corta por pestaña
PESTANA_INFO = {
    "diario": ("☀︎", "el parte del día"),
    "quehacer": ("✔︎", "decisión del mes"),
    "paises": ("⚑︎", "semáforo de 18 países"),
    "hoy": ("⌂︎", "fase y riesgo de recesión"),
    "escenarios": ("↕︎", "rangos a 12 meses"),
    "activos": ("★︎", "tus acciones y ETF"),
    "manos": ("⚖︎", "qué hacen los grandes"),
    "atlas": ("▦︎", "un siglo de historia"),
    "cartera": ("◔︎", "cartera de seguimiento"),
    "estado": ("⚙︎", "fiabilidad y glosario"),
    "verificacion": ("✓︎", "el sistema se pone nota"),
}

# 3-5 frases llanas por pestaña. Solo explican cómo leerla y qué te dice; sin cifras (las cifras están debajo).
PARA_TI = {
    "diario": [
        "Es el «parte del día»: los indicadores que más se mueven (dinero, miedo en bolsa, crédito, inflación, empleo), "
        "cada uno con su color.",
        "Arriba tienes solo lo que está en rojo o ámbar: si esa lista es corta, el día es tranquilo.",
        "Verde no significa «compra» ni rojo «vende»: son reglas fijas, no validadas, para llamar tu atención.",
        "El percentil dice si el dato está alto o bajo frente a su propia historia (p90 = más alto que el 90 % de las veces).",
        "Pulsa cualquier minigráfico para verlo en grande.",
    ],
    "quehacer": [
        "Aquí está lo que haría este mes la cartera de seguimiento y por qué.",
        "Si dice «mantener», la regla no ve motivo para cambiar el reparto entre bolsa, bonos y letras.",
        "Los abanicos enseñan el rango de lo que puede pasar en 12 meses: fíjate en lo ancho que es, no solo en el centro.",
        "No es una recomendación personal: es lo que haría una regla probada solo con datos del pasado.",
    ],
    "paises": [
        "Un vistazo a 18 países con semáforo: verde bien, ámbar vigilar, rojo mal.",
        "Cada color sale de una regla fija sobre el último dato oficial; no es una previsión.",
        "Pulsa un país para ver todo su detalle, sus previsiones y lo que dice el motor.",
        "Si tu dinero o tu trabajo dependen de un país concreto, mira sobre todo su inflación, su empleo y sus bonos.",
    ],
    "hoy": [
        "La foto semanal de EE. UU., que suele marcar el paso al resto del mundo, y el riesgo de recesión por país.",
        "Las tarjetas de arriba dicen en qué fase está la economía; las tablas de abajo son el detalle.",
        "Un percentil alto en crédito o en miedo indica tensión; uno bajo, calma.",
        "Mira siempre la fecha de cada dato: algunos llegan con semanas o meses de retraso.",
    ],
    "escenarios": [
        "Qué rango de rentabilidad real (ya descontada la inflación) es razonable a 12 meses para cada activo y país.",
        "Cada barra es un abanico: el 90 % de los escenarios cae dentro y el punto es el caso central.",
        "Una barra muy larga significa mucha incertidumbre, no una oportunidad.",
        "Úsalo para hacerte una idea de cuánto podrías ganar o perder, no como precio objetivo.",
    ],
    "activos": [
        "Tus acciones, ETF y materias primas: cuánto han subido o bajado, cuánto se mueven y dos simulaciones a 12 meses.",
        "Un activo con mucha volatilidad o una gran caída desde su máximo puede darte sustos aunque a la larga vaya bien.",
        "Las simulaciones enseñan el rango posible, no un precio objetivo, y no están validadas.",
        "Pulsa un activo para abrir su ficha completa.",
    ],
    "manos": [
        "Qué hacen los grandes inversores en los futuros (gestoras, fondos especulativos, productores) y si los "
        "directivos compran acciones de sus propias empresas.",
        "Una posición «en extremo» frente a los últimos 3 años llama la atención, pero por puro azar siempre hay unas cuantas.",
        "Es información descriptiva: no se ha probado que sirva para anticipar precios.",
    ],
    "atlas": [
        "Qué tal les fue a la bolsa, los bonos, las letras, la vivienda y el oro en cada situación económica, con más de "
        "un siglo de datos de los países ricos de la base histórica JST (cuántos y qué años, abajo).",
        "Las tarjetas resaltadas son las que corresponden a la situación de hoy.",
        "Cada cifra dice cuánto fiarte de ella: «establecido», «frágil» o solo «descriptivo».",
        "Sirve para saber qué suele aguantar mejor cuando la economía cambia de fase.",
    ],
    "cartera": [
        "Lo que haría tu cartera de seguimiento (versiones B0, B1 y B1′) este mes, con dinero ficticio.",
        "B1 solo reduce la bolsa cuando la volatilidad supera un umbral fijado de antemano.",
        "Es un experimento para comprobar en vivo si las reglas funcionan; los resultados irán apareciendo con los meses.",
    ],
    "estado": [
        "Cuánto fiarte de cada herramienta del panel y qué datos tienen problemas.",
        "Si aquí sale un aviso, la parte afectada puede estar desactualizada: tenlo en cuenta al leer las otras pestañas.",
        "Al final está el glosario con todas las palabras técnicas explicadas.",
    ],
    "verificacion": [
        "Aquí el sistema se pone nota: antes de cada dato oficial (IPC, empleo, PIB) apunta su predicción y después la "
        "compara con lo que salió.",
        "Si acierta más que las previsiones ingenuas («igual que el último dato» o «la media del año»), merece algo más "
        "de confianza; si no, menos.",
        "También compara cómo se mueven juntos bolsa, bonos y oro con lo que supone el motor.",
    ],
}


def nav_boton(k: str, nombre: str, extra: str = "") -> str:
    ico, desc = PESTANA_INFO.get(k, ("•", ""))
    return (f'<button type="button" role="tab" data-t="{esc(k)}" aria-controls="{esc(k)}" title="{esc(desc)}">'
            f'<span class="tn"><span class="ti" aria-hidden="true">{ico}</span>{esc(nombre)}{esc(extra)}</span>'
            f'<span class="td">{esc(desc)}</span></button>')


def titulo_pestana(k: str, nombre: str) -> str:
    ico, desc = PESTANA_INFO.get(k, ("", ""))
    i = f'<span class="ti" aria-hidden="true">{ico}</span> ' if ico else ""
    d = f' <span class="h2d">· {esc(desc)}</span>' if desc else ""
    return f"<h2>{i}{esc(nombre)}{d}</h2>"


def para_ti(k: str) -> str:
    fr = PARA_TI.get(k)
    if not fr:
        return ""
    return ('<div class="parati"><h3><span aria-hidden="true">ℹ︎</span> Qué significa esto para ti</h3><ul>'
            + "".join(f"<li>{esc(f)}</li>" for f in fr) + "</ul></div>")


def leyenda_colores() -> str:
    return ('<p class="leyenda-col"><strong>Colores:</strong> '
            f'{PP.chip("verde", "verde = bien / normal")} {PP.chip("ambar", "ámbar = vigilar")} '
            f'{PP.chip("rojo", "rojo = mal / alerta")} {PP.chip("gris", "gris = sin dato o solo descriptivo")} '
            '<span class="muted">· cada color va siempre con su palabra · pulsa un gráfico para verlo en grande '
            '<span aria-hidden="true">⤢</span></span></p>')


def extras_body() -> str:
    """Visor modal y botón «volver arriba» (al final de <body>)."""
    return ('<dialog id="zoom" class="zoom" aria-labelledby="zoom-t">'
            '<div class="zoom-box"><div class="zoom-h"><div><h3 id="zoom-t"></h3><p class="zoom-s muted"></p></div>'
            '<button type="button" class="zoom-x" aria-label="Cerrar el gráfico ampliado">✕ <span>Cerrar</span>'
            '</button></div><div class="zoom-c"></div><div class="zoom-n"></div>'
            '<p class="zoom-ayuda muted">Esc, clic fuera o «Cerrar» para volver.</p></div></dialog>'
            '<button type="button" id="arriba" class="arriba" aria-label="Volver arriba" hidden>↑ Arriba</button>')


CSS = """
body{font-size:16px;line-height:1.6}
h2{font-size:22px;margin:26px 0 10px;display:flex;align-items:baseline;gap:6px;flex-wrap:wrap}
h2 .ti{color:var(--s1)}h2 .h2d{font-size:14px;font-weight:400;color:var(--muted)}
table{font-size:14px}.note,.small{font-size:14px}.muted{font-size:13.5px}
.card{padding:16px 18px;margin:14px 0}
p,li{max-width:110ch}
/* navegación fija arriba, con icono y descripción corta */
.navwrap{position:sticky;top:0;z-index:20;background:var(--page);border-bottom:1px solid var(--grid);
box-shadow:0 6px 10px -10px rgba(0,0,0,.35)}
.navwrap nav.tabs{max-width:1280px;margin:0 auto;padding:0 16px;border-bottom:0;flex-wrap:wrap;gap:2px}
nav.tabs button{display:flex;flex-direction:column;align-items:flex-start;line-height:1.25;padding:8px 10px 7px;
border-radius:6px 6px 0 0}
nav.tabs button .tn{display:inline-flex;gap:6px;align-items:baseline}nav.tabs button .ti{color:var(--muted);font-size:13px}
nav.tabs button[aria-selected="true"] .ti{color:var(--s1)}
nav.tabs button .td{font-size:11.5px;color:var(--muted);font-weight:400}
nav.tabs button:hover{background:var(--hl);color:var(--ink)}
nav.tabs button[aria-selected="true"]{background:var(--hl)}
@media (max-width:900px){.navwrap nav.tabs{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch}
nav.tabs button .td{display:none}nav.tabs button{padding:10px 10px}}
/* «qué significa esto para ti» */
.parati{background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--s1);border-radius:8px;
padding:10px 16px 8px;margin:10px 0 12px}
.parati h3{font-size:15.5px;margin:0 0 4px;color:var(--ink)}.parati h3 span{color:var(--s1)}
.parati ul{margin:2px 0 4px;padding-left:20px}.parati li{margin:3px 0}
.leyenda-col{display:flex;flex-wrap:wrap;gap:6px 8px;align-items:center;font-size:13.5px;margin:8px 0}
/* tooltips y glosario más visibles */
#tip{font-size:14px;max-width:360px;padding:8px 10px;line-height:1.45;box-shadow:0 6px 18px rgba(0,0,0,.25);z-index:30}
abbr.term{text-decoration-color:var(--s1);text-decoration-thickness:1.5px}
abbr.term:hover,abbr.term:focus{background:var(--hl);border-radius:3px;outline:none}
/* gráficos ampliables */
.zwrap{position:relative}
/* abanicos de «Qué hacer»: las etiquetas p95 van arriba a la derecha → el botón «Ampliar» se pone encima (B3) */
.qh-cel .zwrap{padding-top:30px}
[data-zoomable]{cursor:zoom-in}
svg[data-zoomable]:hover,img[data-zoomable]:hover,.segbar[data-zoomable]:hover{outline:1px dashed var(--axis);outline-offset:3px;border-radius:4px}
.zbtn{position:absolute;top:2px;right:2px;font:inherit;font-size:12.5px;line-height:1;padding:5px 8px;border-radius:6px;
border:1px solid var(--axis);background:var(--surface);color:var(--ink2);cursor:pointer;opacity:.75}
.zbtn:hover,.zbtn:focus-visible{opacity:1;color:var(--ink);outline:2px solid var(--s1);outline-offset:1px}
@media (hover:none){.zbtn{opacity:.9;padding:7px 10px}}
dialog.zoom{border:0;padding:0;margin:auto;width:min(1200px,96vw);max-width:96vw;max-height:94vh;background:transparent;
color:var(--ink);overflow:visible}
dialog.zoom::backdrop{background:rgba(0,0,0,.62)}
dialog.zoom:not([open]){display:none}
.zoom-fallback{position:fixed;inset:0;z-index:50;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.62)}
.zoom-box{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 18px 10px;
max-height:94vh;overflow:auto;box-shadow:0 20px 60px rgba(0,0,0,.4)}
.zoom-h{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.zoom-h h3{font-size:18px;margin:0}.zoom-s{margin:2px 0 0}
.zoom-x{font:inherit;font-size:15px;padding:6px 12px;border-radius:8px;border:1px solid var(--axis);background:var(--page);
color:var(--ink);cursor:pointer;white-space:nowrap}.zoom-x:focus-visible{outline:2px solid var(--s1);outline-offset:2px}
.zoom-c{margin:12px 0 6px;display:flex;justify-content:center}.zoom-anc{display:contents!important}
.zoom-c svg{width:100%!important;height:auto!important;max-width:100%;max-height:70vh;display:block;overflow:visible}
.zoom-c svg *{vector-effect:non-scaling-stroke}
.zoom-c .spark path,.zoom-c .spark polyline,.zoom-c .mf-spark .ln{stroke-width:2.5px}
.zoom-c img{max-width:100%;max-height:72vh;object-fit:contain}
.zoom-c .segbar{width:100%;height:56px}.zoom-c .seg{font-size:15px}
.zoom-n{font-size:14px;color:var(--ink2)}.zoom-n p{margin:6px 0}.zoom-ayuda{margin:8px 0 2px;font-size:12.5px}
@media (max-width:600px){.zoom-box{padding:10px 10px 8px;border-radius:10px}.zoom-h h3{font-size:16px}
.zoom-x span{display:none}.zoom-c svg{max-height:60vh}}
/* tablas largas plegadas */
tr.plegada{display:none}.masfilas{font:inherit;font-size:13.5px;margin:4px 0 10px;padding:5px 12px;border-radius:6px;
border:1px solid var(--axis);background:var(--surface);color:var(--s1);cursor:pointer}
/* volver arriba */
.arriba{position:fixed;right:16px;bottom:16px;z-index:25;font:inherit;font-size:14px;padding:8px 14px;border-radius:999px;
border:1px solid var(--axis);background:var(--surface);color:var(--ink);cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.2)}
.arriba:focus-visible{outline:2px solid var(--s1);outline-offset:2px}
/* saltos a fichas (#act-, #pais-, #atlas-): que la barra fija no tape el título (B1, prueba de uso 17-nov) */
main [id],main details{scroll-margin-top:calc(var(--navh,110px) + 8px)}
/* móvil: nada sale por la derecha (M3): insignias y chips se parten; tablas anchas con scroll propio */
.tw-auto{overflow-x:auto;-webkit-overflow-scrolling:touch;max-width:100%}
.dblk,.dgrid>*,.grid2>*{min-width:0}
@media (max-width:700px){.badge,.chip{white-space:normal;max-width:100%;line-height:1.3}main{overflow-wrap:anywhere}}
/* móvil */
@media (max-width:600px){body{font-size:15.5px}header,main,footer{padding:0 12px}h1{font-size:20px}
h2{font-size:19px}h2 .h2d{font-size:13px}.card{padding:12px 12px}.tiles{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
th,td{padding:6px 6px}}
@media print{.navwrap,.zbtn,.arriba,dialog.zoom,.masfilas{display:none!important}tr.plegada{display:table-row}}
"""

JS = r"""
(function(){
var main=document.querySelector('main'),dlg=document.getElementById('zoom');if(!main||!dlg)return;
var cont=dlg.querySelector('.zoom-c'),tit=dlg.querySelector('#zoom-t'),sub=dlg.querySelector('.zoom-s'),
nota=dlg.querySelector('.zoom-n'),tip=document.getElementById('tip'),prev=null,nativo=typeof dlg.showModal==='function';
function txt(el){return el?(el.textContent||'').replace(/\s+/g,' ').trim():''}
function ok(el){if(el.closest('[data-zoom="no"]')||el.closest('#zoom'))return false;
if(el.tagName.toLowerCase()==='svg'){if(el.parentNode&&el.parentNode.closest&&el.parentNode.closest('svg'))return false;
var vb=el.getAttribute('viewBox');if(!vb&&!(el.getAttribute('width')&&el.getAttribute('height')))return false;return true}
return true}
var els=[].slice.call(main.querySelectorAll('svg,img,.segbar,[data-zoom]')).filter(function(el){
return el.getAttribute('data-zoom')!=='no'&&ok(el)});
els.forEach(function(el){el.setAttribute('data-zoomable','');
var tile=el.closest('.tile');
if(el.getAttribute('aria-hidden')==='true'){el.removeAttribute('aria-hidden');el.setAttribute('role','img');
el.setAttribute('aria-label','Gráfico'+(tile?': '+txt(tile.querySelector('.tl')):'')+' (pulsa para ampliar)')}
if(el.classList.contains('chart')&&!el.closest('.zwrap')){var w=document.createElement('div');w.className='zwrap';
el.parentNode.insertBefore(w,el);w.appendChild(el);var b=document.createElement('button');b.type='button';b.className='zbtn';
b.innerHTML='<span aria-hidden="true">⤢</span> Ampliar';b.setAttribute('aria-label','Ampliar gráfico: '+(el.getAttribute('aria-label')||''));
b.addEventListener('click',function(e){e.preventDefault();e.stopPropagation();abrir(el,b)});w.appendChild(b)}
else if(!tile&&!el.hasAttribute('tabindex')&&!el.closest('a,button,summary')){el.setAttribute('tabindex','0')}});
function titulo(el){var sec=el.closest('main>section')||main,hs=[].slice.call(sec.querySelectorAll('h2,h3,h4,summary,.zona-h')),t='';
hs.forEach(function(h){if(h.compareDocumentPosition(el)&Node.DOCUMENT_POSITION_FOLLOWING&&!h.contains(el)){t=txt(h)}});return t}
function notas(el){var out=[],base=el.closest('.zwrap')||el,s=base.nextElementSibling,n=0;
while(s&&n<3){if(s.matches('p.small,p.note,p.muted,.legend,ul.legend,.cart-h')){out.push(s.cloneNode(true));n++;s=s.nextElementSibling}else break}
var p=base.previousElementSibling;if(p&&p.matches('.legend,ul.legend'))out.unshift(p.cloneNode(true));return out}
function abrir(el,origen){prev=origen||document.activeElement;var c=el.cloneNode(true);
c.removeAttribute('data-zoomable');c.removeAttribute('tabindex');c.removeAttribute('style');
if(c.tagName.toLowerCase()==='svg'){if(!c.getAttribute('viewBox')&&c.getAttribute('width')){c.setAttribute('viewBox','0 0 '+parseFloat(c.getAttribute('width'))+' '+parseFloat(c.getAttribute('height')))}
c.removeAttribute('width');c.removeAttribute('height');c.setAttribute('preserveAspectRatio','xMidYMid meet');
if(c.getAttribute('data-tip')){c.removeAttribute('data-tip')}}
cont.innerHTML='';
/* reproduce las clases de los antecesores (sin caja: display:contents) para que sigan valiendo los estilos
   del tipo «.verif .chart .int80» que dependen de dónde estaba el gráfico */
var raiz=cont,anc=[];for(var a=el.parentElement;a&&a!==main&&a!==document.body;a=a.parentElement){anc.unshift(a)}
anc.forEach(function(a){var tg=a.tagName.toLowerCase();if(!/^(div|section|article|table|thead|tbody|tr|td|th|ul|ol|li|p|span|dl|dd|dt|figure|aside)$/.test(tg))tg='div';
var w=document.createElement(tg);w.className=((a.getAttribute('class')||'')+' zoom-anc').trim();raiz.appendChild(w);raiz=w});
raiz.appendChild(c);nota.innerHTML='';
var tile=el.closest('.tile'),t=el.getAttribute('data-zoom-titulo')||'',s='',extra=el.getAttribute('data-zoom-nota')||'';
if(!t&&tile){t=txt(tile.querySelector('.tl'));var v=txt(tile.querySelector('.v'));if(v)t+=' · '+v;s=txt(tile.querySelector('.small'));extra=extra||tile.getAttribute('data-tip')||''}
var al=el.getAttribute('aria-label')||'';if(/pulsa para ampliar/.test(al))al='';
if(!t){t=titulo(el)||'Gráfico'}
if(!s&&al&&al!==t)s=al;
tit.textContent=t;sub.textContent=s;sub.hidden=!s;
if(!tile)notas(el).forEach(function(n){nota.appendChild(n)});
if(extra){var p=document.createElement('p');p.textContent=extra;nota.appendChild(p)}
if(tip){tip.style.display='none';dlg.appendChild(tip)}
if(nativo){try{dlg.showModal()}catch(e){dlg.setAttribute('open','');dlg.classList.add('zoom-fallback')}}
else{dlg.setAttribute('open','');dlg.classList.add('zoom-fallback')}
if(c.tagName.toLowerCase()==='svg'){var vb=(c.getAttribute('viewBox')||'').split(/[\s,]+/).map(parseFloat),vw=vb[2]||0;
/* con texto, no más de ×2,6 (si no, las letras salen enormes); sin texto (minigráficos), todo el ancho */
if(vw&&c.querySelector('text')){c.style.maxWidth='min(100%,'+Math.round(vw*2.4)+'px)'}
var esc_=vw?c.getBoundingClientRect().width/vw:1;
if(esc_>2){[].forEach.call(c.querySelectorAll('circle'),function(ci){var r0=parseFloat(ci.getAttribute('r'))||0;
if(r0){ci.setAttribute('r',(Math.min(r0*esc_,Math.max(r0*2,6))/esc_).toFixed(3))}})}}
var x=dlg.querySelector('.zoom-x');if(x)x.focus()}
function cerrar(){if(!dlg.hasAttribute('open'))return;if(nativo&&dlg.close){try{dlg.close()}catch(e){dlg.removeAttribute('open')}}else{dlg.removeAttribute('open')}
dlg.classList.remove('zoom-fallback');cont.innerHTML='';if(tip){tip.style.display='none';document.body.appendChild(tip)}
if(prev&&prev.focus){try{prev.focus()}catch(e){}}prev=null}
dlg.addEventListener('close',function(){if(tip&&tip.parentNode===dlg){tip.style.display='none';document.body.appendChild(tip)}cont.innerHTML='';
if(prev&&prev.focus){try{prev.focus()}catch(e){}}prev=null});
dlg.querySelector('.zoom-x').addEventListener('click',cerrar);
dlg.addEventListener('click',function(e){if(e.target===dlg||e.target.classList.contains('zoom-fallback'))cerrar()});
dlg.addEventListener('cancel',function(e){e.preventDefault();cerrar()});
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&dlg.hasAttribute('open')){e.preventDefault();cerrar();return}
if((e.key==='Enter'||e.key===' ')&&!dlg.hasAttribute('open')){var a=document.activeElement;if(!a||a===document.body)return;
var z=a.hasAttribute('data-zoomable')?a:null;
if(!z&&a.classList.contains('tile')){z=a.querySelector('[data-zoomable]')}
if(z){e.preventDefault();abrir(z,a)}}});
main.addEventListener('click',function(e){var z=e.target.closest('[data-zoomable]');if(!z||z.closest('#zoom'))return;
if(e.target.closest('a,button,select,input,label')&&!e.target.closest('svg'))return;
if(z.closest('summary')){e.preventDefault()}
abrir(z)});
/* tablas: si no van ya dentro de un contenedor con scroll, se envuelven en uno (sin scroll horizontal de página) */
[].forEach.call(main.querySelectorAll('table'),function(t){var p=t.parentElement;if(!p||p.closest('#zoom'))return;
if(p.classList.contains('tw')||p.classList.contains('tw-auto')||getComputedStyle(p).overflowX!=='visible')return;
var w=document.createElement('div');w.className='tw-auto';p.insertBefore(w,t);w.appendChild(t)});
/* altura de la barra fija → scroll-margin-top de los destinos de enlace */
var nwb=document.querySelector('.navwrap');function navh(){if(nwb)document.documentElement.style.setProperty('--navh',nwb.offsetHeight+'px')}
navh();addEventListener('resize',navh);
/* tablas largas: se pliegan a partir de la fila 15 (si no van ya dentro de un desplegable y no agrupan filas) */
[].forEach.call(main.querySelectorAll('table'),function(t){if(t.closest('details')||t.querySelector('[rowspan]')||t.hasAttribute('data-no-plegar'))return;
var b=t.tBodies[0];if(!b)return;var rs=[].slice.call(b.rows);if(rs.length<=40)return;
rs.slice(15).forEach(function(r){r.classList.add('plegada')});var w=t.closest('.tw')||t,bt=document.createElement('button');
bt.type='button';bt.className='masfilas';bt.setAttribute('aria-expanded','false');var m='Mostrar las '+(rs.length-15)+' filas restantes';bt.textContent=m;
bt.addEventListener('click',function(){var abierto=bt.getAttribute('aria-expanded')==='true';
rs.slice(15).forEach(function(r){r.classList.toggle('plegada',abierto)});bt.setAttribute('aria-expanded',abierto?'false':'true');
bt.textContent=abierto?m:'Mostrar solo las 15 primeras'});w.parentNode.insertBefore(bt,w.nextSibling)});
/* volver arriba */
var up=document.getElementById('arriba');if(up){var vis=false;
addEventListener('scroll',function(){var v=scrollY>700;if(v!==vis){vis=v;up.hidden=!v}if(tip)tip.style.display='none'},{passive:true});
up.addEventListener('click',function(){try{scrollTo({top:0,behavior:'smooth'})}catch(e){scrollTo(0,0)}})}
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&tip)tip.style.display='none'});
})();
"""
