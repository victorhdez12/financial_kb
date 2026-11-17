# Ficha v2 de «Mis activos»: volumen, manos fuertes y analistas (17-nov-2026)

Petición del usuario: «en las acciones volumen negociado, en qué punto compraron las manos fuertes, en qué punto se
vendió, y opiniones de analistas si fuese posible». Todo es **descriptivo**: no entra en el signal, ni en las
simulaciones A/B, ni en ningún modelo; no es una señal de cartera ni se ha validado como predictor.

Código: `src/report/activos_v2.py` (cálculo + HTML; lo llama `_ficha` de `src/report/panel_activos.py`).
Tests: `tests/test_activos_v2.py` (datos sintéticos, sin red).

## Fuentes (todas FUERA de git: el repo es público)

| Bloque | Fuente | Ingesta | Dónde se guarda (`$FIN_DATA_ROOT`) | Cuándo |
|---|---|---|---|---|
| Volumen | Yahoo Finance v8 chart (misma petición que los precios) | `src/ingest/yahoo_precios.py` | `mercados/volumen/volumen_diario.parquet`, `cierre_diario.parquet`, `splits.json` | diaria |
| Directivos | SEC Insider Transactions Data Sets (zips ya bajados por `sec_insiders`) + Form 4 XML de EDGAR posteriores | `src/ingest/sec_form4_detalle.py` | `sec_form4/operaciones.parquet`, `meta.json`, `xml/` (caché) | diaria (≈ 25 s; solo pide los Form 4 nuevos) |
| Gestoras | SEC Form 13F Data Sets (≈ 100 MB por trimestre de presentación) | `src/ingest/sec_13f.py` | `sec_13f/posiciones.parquet` (solo lo filtrado; el zip se borra), `meta.json` | semanal |
| Analistas | Yahoo Finance quoteSummary (financialData, recommendationTrend, upgradeDowngradeHistory) | `src/ingest/yahoo_analistas.py` | `mercados/analistas/analistas.json` | diaria (≈ 7 s) |

`yahoo_precios --solo-volumen` descarga igual pero solo escribe `mercados/volumen/` (no toca los precios).

SEC: User-Agent **genérico** de cliente (`financial-kb-panel/1.0 research-client contact@example.org`, sin datos del
usuario), ≤ 5 peticiones/s (limitador común de `sec_common`; el límite de la SEC es 10/s) y plazo total por descarga
(`_http.get(total=…)`).

## Definiciones

**Volumen** (todos los activos). Último volumen = sesión del último dato de Yahoo; medias de las 20 y 63 (≈ 3 meses)
sesiones **anteriores** (sin la última); cociente último/media; importe = volumen × cierre en la moneda del activo.
Si la última sesión es la del día de la descarga se marca «sesión en curso: volumen incompleto». En los futuros
(BZ=F, CL=F) el volumen son contratos del 1.er vencimiento (cae al acercarse el vencimiento) y no se pasa a dinero.
Gráfico: 12 meses de cierre ajustado **solo por splits** (no por dividendos, para compararlo con los precios del
Form 4) + barras de volumen diario y su media de 20 sesiones.

**Directivos** (acciones de EE. UU.: GOOGL, MSFT, META, UBER, CHTR, UNH, CTVA, VYLR, FMC, NEM). Todas las líneas de la
tabla I (no derivadas) de los Form 4 de los últimos 24 meses, con nombre y cargo. Tipos:

* compra (P) — compra en mercado abierto: marca ▲ verde;
* venta (S) sin plan — marca ▼ roja;
* venta con plan 10b5-1 — casilla `aff10b5One` del Form 4 (desde abr-2023) o nota al pie **de esa línea** que menciona
  «10b5-1»: marca ▽ hueca (programada de antemano, poco informativa);
* ejercicio de opciones/derivados (M, X, C…), concesiones (A), retenciones fiscales (F), regalos (G) y otras: se
  cuentan («excluidas») pero no se pintan ni entran en medias.

Solo consejeros y directivos entran en las medias; los accionistas de > 10 % que no lo son salen en la tabla rotulados
«no entra en medias». Precios y acciones se pasan a la escala de los splits de Yahoo. Se descartan líneas P/S con
precio ≤ 0 o a más de un 50 % del cierre de Yahoo de ese día (errores de tecleo). Precio medio **ponderado por
acciones** de 12 meses (por fecha de operación) de compras, ventas sin plan y todas las ventas, y «actual vs. medio» =
precio actual / precio medio − 1. Tabla: las 15 más recientes, una fila por persona, día y tipo (precio medio ponderado
de sus líneas).

**Gestoras 13F (aproximación)**. Acciones de cada gestora al cierre de los 5 últimos trimestres disponibles; las 10
mayores en el último; Δ % entre trimestres e importe ≈ Δ acciones × precio medio de cierre del trimestre (en la escala
de entonces). **No** es el precio al que operaron. Fila final: gestoras presentes en los dos trimestres que suben/bajan
y Δ neto aproximado. Solo 13F-HR originales, solo acciones (SH, sin PUT/CALL), último informe por gestora y trimestre;
se descartan líneas con valor declarado / acciones a más de un 50 % del cierre (errores de unidades: p. ej. un fondo
que declara 4 000 M de acciones de MSFT por 10 M$). «sin dato previo» = el CIK no declaraba la acción el trimestre
anterior (posición nueva, cambio de entidad —Vanguard reorganizó sus CIK en 2026— o informe ausente del fichero).

**Analistas**. Consenso del mes (`recommendationTrend` 0m): comprar = compra fuerte + compra, mantener, vender = venta +
venta fuerte; media 1–5; precio objetivo medio/alto/bajo frente al precio actual; cambios de 90 días (primero subidas,
bajadas e inicios de cobertura). Rótulo fijo: «opinión de terceros, no validada; el consenso de analistas tiene sesgo
optimista conocido».

## Fallos

Cada fuente se carga por separado (`cargar()`); cada bloque de la ficha va en su try/except y muestra «s/d (motivo)».
Si `cargar()` entero falla, la ficha muestra «s/d» y el resto del panel sigue (`cargar_seguro`).

## Limitaciones

* Retrasos: Form 4 hasta 2 días hábiles; 13F hasta 45 días tras el trimestre (la última foto el 17-nov-2026 es de
  30-jun-2026: el fichero de la SEC con las carteras de 30-sep sale a primeros de diciembre).
* 13F: solo largos en acciones de EE. UU. de gestoras > 100 M$; los mayores son indexados (sus cambios son flujos);
  solo la clase A de Alphabet (CUSIP 02079K305); VYLR (escindida el 1-oct-2026) y Bayer aún no salen.
* CTVA: Yahoo trató la escisión de Vylor como un split 6,665:1; los precios de Form 4 anteriores a oct-2026 se dividen
  por ese factor (coherentes con el gráfico, no con el precio que pagaron entonces).
* Bayer: no presenta Form 4 (no cotiza en EE. UU.); solo volumen y analistas.
* Plan 10b5-1 antes de abr-2023: solo si lo dice una nota de la línea.
* Analistas: Yahoo agrega fuentes que no publica; datos sin auditar; los precios objetivo son a 12 meses y suelen ir
  por encima del precio.
* Nada de esto se ha contrastado como predictor en el proyecto.
