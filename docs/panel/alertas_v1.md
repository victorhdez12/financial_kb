# Alertas de flujos en «Mis activos» v1 (17-nov-2026)

Petición del usuario: «yo quiero ventas institucionales, no de esta gente programadas [10b5-1 de directivos]. Que si el
volumen de venta o compra es muy grande me salte alerta y así veo si es buen momento, o si los directivos hacen
recompras como en Uber».

**Todo es descriptivo.** Las alertas no son una señal de compra o venta, no entran en el signal, en las simulaciones
ni en ningún modelo, y no se han validado como predictor. Los umbrales de abajo se fijaron por adelantado y **no se
ajustan mirando qué alertas «acertaron»**. La única excepción está en «Cambios antes de congelar». La UI lo dice en
cada bloque.

Código: `src/report/alertas.py` (cálculo, HTML y notificación). Tabla de historia: `scripts/alertas_descriptivo.py`.
Tests: `tests/test_alertas.py` (15 tests, datos sintéticos, sin red).

## Dónde se ven

1. **Bloque «Alertas de flujos en tus activos»**, arriba en «Hoy» y en «Mis activos».
   - Muestra las alertas de los últimos 7 días, ordenadas por fuerza (fuerte, moderada) y luego por fecha.
   - Cada fila lleva fecha, activo, fuerza, tipo y una frase llana.
   - El nombre del activo enlaza a su ficha (`#act-XXX`): desde «Hoy» cambia de pestaña, abre la ficha y baja hasta
     ella.
   - Un desplegable añade las de 90 días.
2. **Sección «Flujos fuertes (12 meses)» en cada ficha.**
   - Tabla de todas las alertas de 12 meses. Incluye los días especiales, rotulados «no cuenta: …», y los 13D/13G sin
     cambio relevante, como informativos.
   - Recompras de la empresa.
   - Volumen en corto de FINRA como contexto.
   - Nota de la historia descriptiva (ver «Historia»).
   - Las alertas se marcan en el gráfico de precio de la ficha con símbolos distintos de los de directivos (▲▼▽):
     - ◆ volumen anormal: verde azulado si sube, naranja si cae, gris si no se mueve;
     - ■ amarillo para institucional o recompra;
     - las fuertes van más grandes.
   - El visor de gráficos ampliables las muestra igual.
3. **Notificación de macOS tras la actualización** (`scripts/actualizar.sh`, el mismo `osascript` que ya avisa de los
   fallos).
   - Solo salta con alertas **fuertes** nuevas de los últimos 5 días.
   - Cada alerta tiene una clave (tipo, activo, fecha o formulario) y se apunta en
     `~/financial_archive/alertas/notificadas.json`, así que nunca se notifica dos veces.
   - Se desactiva con `FIN_ALERTAS_NOTIFICAR=0` o con `{"notificar": false}` en `~/financial_archive/config/alertas.json`.
     Las dos opciones quedan fuera de git.

## Fuentes (todas fuera de git, en `$FIN_DATA_ROOT`; el repo es público)

| Bloque | Fuente | Ingesta | Guardado | Cuándo |
|---|---|---|---|---|
| OHLC diario | Yahoo v8 chart (la misma petición que precios y volumen) | `yahoo_precios` | `mercados/volumen/{apertura,alto,bajo}_diario.parquet` | diaria |
| Volumen en corto | FINRA Reg SHO daily short sale volume (`cdn.finra.org/equity/regsho/daily/CNMSshvolAAAAMMDD.txt`) | `finra_short` | `finra_short/short_diario.parquet` | diaria (1 fichero de ~0,5 MB por sesión nueva) |
| 13D/13G y resultados | EDGAR submissions del emisor + XML de Schedule 13D/13G; 8-K con el punto 2.02 | `sec_flujos` | `sec_flujos/{participaciones.parquet, resultados.json, xml/, paginas/}` | diaria (≈ 35 s la 1.ª vez, luego segundos) |
| Recompras | SEC XBRL `companyfacts` (solo los conceptos de recompra y de acciones en circulación) | `sec_recompras` | `sec_recompras/hechos.json` | diaria (≈ 5 s) |
| Form 4 | lo de `activos_v2` + columna nueva `owned_after` (acciones tras la operación) | `sec_form4_detalle` | `sec_form4/operaciones.parquet` | diaria |
| 13F | lo de `activos_v2` | `sec_13f` | `sec_13f/posiciones.parquet` | semanal |

Peticiones a la SEC:

- User-Agent genérico, sin datos del usuario.
- Como mucho 5 peticiones por segundo, con el limitador común.
- Plazo total en cada descarga (`_http.get(total=…)`).

Cada fuente se carga y se calcula en su propio try/except: si falla, sale «s/d» y el panel sigue.

## Definiciones y umbrales (fijados por adelantado: `UMBRALES` en `src/report/alertas.py`)

### 1. Volumen anormal (una sesión)

- **Media**: media de las 63 sesiones anteriores (≈ 3 meses), sin contar la sesión. «×» = volumen / media.
- **z robusto**: (log-volumen − mediana) / (rango intercuartílico / 1,349), con las 252 sesiones anteriores (≈ 1 año;
  mínimo 126). Es robusto a los picos pasados y al sesgo del volumen.
- **Moderada**: × ≥ 2 y z ≥ 2. **Fuerte**: × ≥ 3 y z ≥ 3. Hacen falta las dos cosas: el × solo dispara en valores de
  poco volumen y el z solo en valores muy estables.
- **Clase**: según k = rentabilidad logarítmica del día / σ diaria de las 63 sesiones anteriores.
  - k ≥ 1,5: «con subida fuerte (posible compra institucional/acumulación)».
  - k ≤ −1,5: «con caída fuerte (posible venta/distribución)».
  - Si no, «sin movimiento de precio» (compradores y vendedores equilibrados, o cruces de bloques).
  - 1,5 σ es un umbral redondo: un día así ocurre en ≈ 13 % de las sesiones normales.
- **Dónde cerró en el rango del día**: (cierre − mínimo) / (máximo − mínimo). ≥ 0,75 es «cerca del máximo», ≤ 0,25
  «cerca del mínimo». Solo se describe; no cambia la clase.
- **Por qué solo «posible»**: cada acción negociada tiene un comprador y un vendedor. El volumen solo dice que hubo
  prisa, y la dirección del precio sugiere de qué lado estaba. No hay forma de saber con datos públicos diarios si eran
  instituciones. La UI lo dice.
- **Volumen alto sostenido (5 sesiones)**: media de las 5 últimas / media de las 63 anteriores a ellas. Es moderada
  con ≥ 1,75 y fuerte con ≥ 2,5. Solo sale el día en que sube de nivel, no cada día de la racha. La dirección es la del
  precio en esas 5 sesiones, frente a 1,5 σ·√5.
- **Días especiales (se marcan y NO alertan)**:
  - **Sesión en curso**: si la fecha es ≥ la de la descarga de Yahoo, el volumen está incompleto.
  - **Vencimiento trimestral** de opciones y futuros (triple witching) y **rebalanceo trimestral del S&P**: 3.er
    viernes de marzo, junio, septiembre y diciembre. Si es festivo, la sesión anterior (Juneteenth 2026 → 18-jun).
  - **Reconstitución de Russell**: último viernes de junio.
  - **Revisiones trimestrales de MSCI**: último día hábil de febrero, mayo, agosto y noviembre.
  - **Resultados trimestrales**: día del 8-K con el punto 2.02 de EDGAR y la sesión siguiente, para cubrir las
    publicaciones tras el cierre. Hay fechas desde 2004 para las acciones de EE. UU.
  - **Split o escisión**: las 5 sesiones desde el evento de Yahoo, cuando los índices y fondos se reajustan. Por
    ejemplo, CTVA y Vylor el 1-oct-2026.
  - En las 5 sesiones, la racha no alerta si incluye un día de resultados o de split.
- **Futuros (BZ=F, CL=F)**: sin alertas de volumen. El volumen es del 1.er vencimiento y cae y salta en cada cambio
  de contrato.

### 2a. 13F (trimestral, hasta 45 días de retraso)

- **Gestoras**: las 20 mayores en cualquiera de los dos trimestres.
- **Alerta por gestora** si cambia ≥ 50 % su posición o entra/sale por completo, y además mueve ≥ 0,1 % de las
  acciones de la empresa. Es **fuerte** si mueve ≥ 1 % de la empresa. Las acciones en circulación salen de XBRL.
- **No alertan**:
  - Entradas y salidas que son la misma gestora con otro CIK: misma primera palabra del nombre, como Vanguard en 2026.
  - Gestoras que no presentaron ningún 13F de las acciones seguidas en el otro trimestre. Es un informe ausente del
    fichero de la SEC, no una venta. Sin esta regla, Norges Bank y JPMorgan «salían» de todas las acciones a la vez.
- **Cambio agregado del trimestre**: `resumen_13f` de `activos_v2`, solo gestoras presentes en los dos trimestres.
  Moderada si el neto es ≥ 1 % de la empresa; fuerte si es ≥ 2 %.
- **Fecha**: la de presentación de la gestora. Para salidas y el agregado, el plazo legal (fin del trimestre + 45 días).
- **Rótulo**: «Trimestral, con hasta 45 días de retraso».

### 2b. 13D / 13G (participaciones del 5 %+, días de retraso)

- **Qué se lee**: los XML de Schedule 13D/13G y sus /A, obligatorios desde el 18-dic-2024. Se guardan solo si el
  emisor (`issuerCik`) es la propia empresa. La lista de EDGAR de UBER incluye también los 13D de UBER sobre Grab y
  Aurora.
- **13D nuevo**: fuerte. Es el formulario de quien no es inversor pasivo: posible activista, socio o fusión.
- **13D/A**: alerta si cambia ≥ 1 punto (fuerte si ≥ 2) o baja del 5 % (fuerte si tenía ≥ 10 %).
- **13G nuevo con ≥ 5 %**: moderada («cruza el 5 %»).
- **13G/A**: moderada si cambia ≥ 1 punto o baja del 5 %.
- **Reorganizaciones**: el formulario lo dice, como el «realignment» de Vanguard en 2026. Pasar a 0 % o el 13G nuevo
  de la entidad nueva es informativo, no alerta.

### 2c. Form 4 (solo lo informativo)

- **Quién cuenta**: consejeros, directivos y propietarios del 10 %.
- **Qué alerta**:
  - **Compra en mercado abierto (P)**: moderada con ≥ 100 000 $ y fuerte con ≥ 1 M$.
  - **Venta (S) SIN plan 10b5-1**: moderada con ≥ 10 M$, o con ≥ 20 % de su tenencia y ≥ 1 M$. Fuerte con ≥ 50 M$, o
    con ≥ 50 % de su tenencia y ≥ 5 M$.
- **% de su tenencia**: acciones vendidas / (vendidas + `owned_after` de la última línea del día). Es aproximado:
  `owned_after` es por forma de tenencia (directa, fideicomiso…).
- **Qué NO alerta**: las ventas con plan 10b5-1, las concesiones (A), las retenciones fiscales (F), los ejercicios
  (M/X/C), los regalos ni el resto.
- **Datos**: una persona, un día y un tipo, con los mismos filtros de precio absurdo de `activos_v2`. La fecha es la
  de presentación, cuando se hace público.

### 3. Recompras de la empresa (XBRL de 10-Q/10-K)

- **Importe por trimestre**: `PaymentsForRepurchaseOfCommonStock` (flujo de caja). Si falta, se usan
  `PaymentsForRepurchaseOfEquity`, `StockRepurchasedDuringPeriodValue` y `…AndRetired…`, por ese orden.
  - El primer concepto con datos de los últimos 15 meses.
  - Si la empresa solo da el acumulado del año, el trimestre es la diferencia con el acumulado anterior del mismo año
    fiscal.
  - Las cifras revisadas toman el último valor, pero la **fecha** es la primera vez que se publicó.
- **12 meses** = suma de los 4 últimos trimestres consecutivos.
- **Buyback yield** = 12 meses / capitalización actual.
  - Capitalización = acciones en circulación de la portada (`dei:EntityCommonStockSharesOutstanding`) × precio.
  - Si faltan, se usa `CommonStockSharesOutstanding` y, en último caso, la media diluida del trimestre.
  - Alphabet y Meta tienen varias clases y no dan la portada.
- **Variación de acciones en circulación en 12 meses**: recompra neta de la emisión a empleados, ajustada por splits.
- **Alertas**:
  - **Trimestre ≥ 0,75 % de la capitalización** de entonces: moderada, «recompra alta». Con ≥ 1,5 %, fuerte.
  - **≥ 2× la media de los 4 anteriores y ≥ 0,4 %**: moderada.
  - **Parón**: menos del 10 % de la media de los 4 anteriores cuando esa media era ≥ 0,4 % de la capitalización.
  - **Programa ampliado o nuevo**: sube ≥ 5 % el importe autorizado (`StockRepurchaseProgramAuthorizedAmount1`, us-gaap
    o srt).
- **Qué no se intenta**: detectar programas nuevos leyendo el texto de los 8-K. No es fiable.

## Cambios antes de congelar (sin mirar resultados)

Al revisar la primera salida real cambiaron tres cosas:

- **13F**: se subió el umbral de cambio de 25 % a 50 %, se añadió el mínimo de 0,1 % de la empresa y el umbral de
  fuerte pasó de 0,5 % a 1 %. Motivo: 117 alertas en 12 meses, sobre todo en valores medianos como FMC. Se miró la
  **cantidad**, no qué pasó con el precio después.
- **13F**: regla de «informe ausente».
- **Volumen**: exclusión de split/escisión.

Las dos últimas corrigen artefactos de datos. Ningún umbral se ha comparado con rentabilidades posteriores. Desde
aquí quedan congelados en v1; cualquier cambio sería v2, con fecha y motivo.

## Historia (descriptiva, NO es una validación)

`scripts/alertas_descriptivo.py`, 10 años (nov-2016 a nov-2026, o desde que cotiza). Alertas de volumen de un día,
moderadas y fuertes, sin días especiales. Muestra cuántas habría dado cada activo y qué hizo el precio 1, 5 y 20
sesiones después. La rentabilidad es en % sobre el cierre del día de la alerta (cierre sin ajustar por dividendos).
Para 20 sesiones se da media ± desviación típica.

| Activo | desde | alertas (≈/año) | sube: n · 1 s · 5 s · 20 s | baja: n · 1 s · 5 s · 20 s | plano: n · 20 s | cualquier día 20 s |
|---|---|---|---|---|---|---|
| GOOGL | 2016-11 | 42 (4.2) | 12 · −0,5 · −0,0 · +2,6 ± 4,0 | 16 · +1,1 · +2,7 · +5,0 ± 8,5 | 14 · +4,7 ± 7,8 | +1,9 ± 7,7 |
| MSFT | 2016-11 | 40 (4.0) | 8 · −3,7 · −4,2 · +4,1 ± 9,4 | 16 · +2,7 · +1,9 · +4,3 ± 12,7 | 16 · +2,0 ± 12,3 | +2,0 ± 6,6 |
| META | 2016-11 | 63 (6.3) | 9 · −1,6 · +0,2 · −1,5 ± 11,2 | 18 · +0,8 · +2,2 · +9,1 ± 9,9 | 36 · +2,9 ± 10,7 | +1,9 ± 10,4 |
| UBER | 2019-05 | 36 (3.6) | 7 · +1,4 · +2,1 · +4,8 ± 14,3 | 9 · +0,9 · −0,1 · −2,0 ± 9,2 | 20 · +5,1 ± 5,6 | +1,4 ± 13,1 |
| CHTR | 2016-11 | 52 (5.2) | 9 · −4,8 · −6,6 · −0,5 ± 11,2 | 16 · −0,2 · −2,8 · +1,4 ± 11,2 | 27 · −2,1 ± 13,0 | −0,1 ± 10,1 |
| UNH | 2016-11 | 62 (6.2) | 14 · +0,3 · +0,2 · −5,0 ± 13,5 | 30 · +1,0 · +0,0 · +3,6 ± 11,2 | 18 · +6,1 ± 13,4 | +1,1 ± 8,2 |
| CTVA | 2019-05 | 13 (1.3) | 2 · −0,9 · +0,8 · −4,3 ± 8,6 | 2 · +0,3 · +0,2 · −4,8 ± 8,1 | 9 · +2,8 ± 7,5 | +1,4 ± 7,8 |
| FMC | 2016-11 | 34 (3.4) | 3 · −0,7 · −2,0 · +1,3 ± 7,9 | 7 · +2,5 · +4,3 · +3,1 ± 17,4 | 24 · −0,7 ± 12,9 | −1,0 ± 11,6 |
| BAYN.DE | 2016-11 | 82 (8.2) | 16 · +0,6 · +1,2 · −0,5 ± 8,9 | 36 · +0,2 · −0,6 · −1,4 ± 13,0 | 30 · −0,1 ± 12,2 | +0,0 ± 9,8 |
| MOO | 2016-11 | 154 (15.4) | 21 · +0,5 · +0,9 · +4,0 ± 4,4 | 14 · +0,7 · +0,2 · +3,5 ± 5,5 | 119 · +1,7 ± 5,6 | +0,5 ± 5,0 |
| GLD | 2016-11 | 84 (8.4) | 33 · −0,0 · +0,2 · +0,5 ± 4,2 | 23 · +0,3 · +1,0 · +3,5 ± 5,3 | 28 · +2,1 ± 4,8 | +1,0 ± 4,3 |
| GDX | 2016-11 | 53 (5.3) | 19 · +0,7 · +1,1 · +5,0 ± 12,0 | 23 · +0,1 · +1,8 · +10,8 ± 18,4 | 11 · +3,3 ± 9,7 | +1,6 ± 9,8 |
| NEM | 2016-11 | 46 (4.6) | 10 · +1,1 · +2,7 · +1,3 ± 7,4 | 14 · −0,2 · +2,4 · +8,8 ± 15,9 | 22 · +1,9 ± 13,4 | +1,5 ± 9,9 |
| XLE | 2016-11 | 61 (6.1) | 12 · −0,7 · +0,2 · +1,8 ± 16,7 | 26 · −1,7 · −4,2 · −8,7 ± 19,6 | 23 · +5,8 ± 10,5 | +0,9 ± 8,6 |
| XLK | 2016-11 | 75 (7.5) | 12 · −2,7 · −3,1 · +3,7 ± 7,7 | 30 · +1,1 · +1,4 · +2,6 ± 8,5 | 33 · +3,7 ± 8,3 | +1,8 ± 6,1 |
| XLV | 2016-11 | 62 (6.2) | 10 · −2,5 · −4,0 · −1,0 ± 7,2 | 24 · +0,7 · +1,3 · +3,2 ± 7,0 | 28 · +3,8 ± 5,4 | +0,9 ± 4,2 |
| XLF | 2016-11 | 59 (5.9) | 13 · −2,4 · −4,5 · −2,2 ± 12,0 | 33 · +0,2 · −1,5 · −1,0 ± 11,8 | 13 · −0,2 ± 9,4 | +0,9 ± 5,7 |
| XLU | 2016-11 | 36 (3.6) | 6 · +0,4 · +0,6 · +0,6 ± 6,8 | 13 · +0,2 · −1,7 · −1,1 ± 10,4 | 17 · +1,6 ± 7,9 | +0,6 ± 4,8 |
| XLP | 2016-11 | 61 (6.1) | 11 · −0,7 · −1,2 · +0,9 ± 5,2 | 12 · −0,5 · +1,1 · +1,0 ± 5,2 | 38 · +0,7 ± 4,1 | +0,5 ± 3,7 |
| XLI | 2016-11 | 49 (4.9) | 5 · −2,1 · −6,1 · −8,0 ± 14,9 | 20 · +0,8 · +1,6 · +0,3 ± 11,6 | 24 · −1,0 ± 9,7 | +0,9 ± 5,4 |
| XLB | 2016-11 | 76 (7.6) | 14 · +0,2 · +0,7 · −0,6 ± 6,6 | 23 · +0,2 · +1,1 · +2,1 ± 9,5 | 39 · +1,4 ± 6,4 | +0,7 ± 5,4 |
| XLC | 2018-06 | 54 (5.4) | 6 · −1,1 · −0,0 · +1,1 ± 3,1 | 15 · +1,1 · +0,3 · +0,6 ± 10,4 | 33 · +3,7 ± 7,4 | +0,9 ± 5,4 |
| XLRE | 2016-11 | 86 (8.6) | 11 · −0,6 · −3,9 · −5,3 ± 11,7 | 26 · +0,1 · −1,5 · −0,2 ± 11,9 | 49 · +0,2 ± 7,7 | +0,4 ± 5,3 |
| SPY | 2016-11 | 56 (5.6) | 9 · −3,5 · −6,2 · −2,3 ± 10,4 | 30 · +0,5 · −0,8 · +0,8 ± 10,7 | 17 · +2,9 ± 11,4 | +1,1 ± 4,5 |
| QQQ | 2016-11 | 74 (7.4) | 12 · −2,7 · −3,6 · +1,1 ± 8,7 | 40 · +0,5 · −0,6 · −0,2 ± 9,6 | 22 · +3,6 ± 9,9 | +1,6 ± 5,6 |
| TLT | 2016-11 | 81 (8.1) | 23 · −0,4 · −0,3 · +0,1 ± 4,3 | 25 · +0,3 · −0,3 · +0,8 ± 5,2 | 33 · +0,5 ± 4,1 | −0,2 ± 3,7 |
| VGK | 2016-11 | 79 (7.9) | 12 · −0,4 · −2,5 · −2,1 ± 11,7 | 20 · +0,1 · −1,2 · +2,4 ± 10,3 | 47 · +2,1 ± 6,1 | +0,6 ± 5,1 |

En total: 319 «sube», 561 «baja» y 790 «plano», en 27 activos. Aproximadamente 4-8 alertas al año por valor y hasta
15 en ETF de poco volumen como MOO.

Lectura honesta:

- **Este proyecto no puede decir si las alertas sirven.** Hay pocos casos por clase (2-40), los activos están muy
  correlacionados (las alertas de SPY, QQQ y XLK caen los mismos días de pánico), las ventanas de 20 sesiones se
  solapan y no hay grupo de control emparejado ni corrección por comparaciones múltiples.
- **El ruido supera a las diferencias.** La desviación típica a 20 sesiones (4-20 puntos) es varias veces mayor que
  cualquier diferencia de medias.
- **El patrón más visible es el contrario de la lectura ingenua.** Tras «caída fuerte con volumen», la media a 20
  sesiones es mayor que la de cualquier día en 16 de los 27 activos (rebotes tras días de pánico). En los otros 11 es
  menor (XLE −8,7 %). Es compatible con el azar y con la reversión a corto plazo. No es una regla.
- **Por qué no son señales.** Las alertas dicen «ha pasado algo grande con prisa», no «compra» ni «vende». Por eso los
  umbrales no se tocan a la vista de esta tabla.
- **Datos de la tabla.** Yahoo, cierre sin ajustar por dividendos (en ETF de bonos, como TLT, la rentabilidad infravalora
  unas décimas). Las fechas de resultados salen de EDGAR desde 2004. En los ETF no hay días de resultados.

La ficha de cada activo lleva esta misma nota resumida: número de alertas, ≈ por año y 20 sesiones por clase frente a
cualquier día.

## UBER (el ejemplo del usuario), dato real del 17-nov-2026

**Recompras de la empresa** (XBRL, `PaymentsForRepurchaseOfCommonStock`; acumulados del año pasados a trimestres):

| Trimestre | Importe | % de la capitalización de entonces |
|---|---|---|
| T4-2025 | 1 912 M$ | 1,1 % |
| T1-2026 | 3 011 M$ | 2,1 % (alerta fuerte, 10-Q del 6-may-2026) |
| T2-2026 | 518 M$ | 0,4 % |
| T3-2026 | 750 M$ | 0,5 % |

- **12 meses hasta el 30-sep-2026**: **6 191 M$**.
- **Buyback yield ≈ 4,3 %** sobre una capitalización de ≈ 142,6 mil M$.
- **Acciones en circulación**: de 2 077,8 M (30-oct-2025) a 2 041,9 M (30-oct-2026), **−1,7 %**. La recompra neta de
  la emisión a empleados es real.
- **Programa autorizado**: 27 mil M$ (dato al 31-dic-2025); pendiente 15 mil M$ (30-sep-2026).

**Directivos (Form 4, fuertes)**: compras en mercado abierto, no recompras de la empresa.

- Dara Khosrowshahi (CEO), 141 000 acciones a 70,96 $ (≈ 10,0 M$) el 10-sep-2026.
- Andrew Macdonald, 70 000 a 75,83 $ (≈ 5,3 M$) el 4-sep-2026.

## Limitaciones

- **Retrasos.** Form 4: hasta 2 días hábiles. 13D/13G: 5-10 días hábiles (13D) o 45 días tras el trimestre (13G de
  pasivos). 13F: hasta 45 días tras el trimestre; la foto más reciente es de 30-jun-2026. Recompras: con el 10-Q
  (~1 mes tras el trimestre).
- **Bayer (BAYN.DE).** Sin Form 4, 13D/G, recompras XBRL ni fechas de resultados: sus días de resultados no se excluyen
  (la ficha lo dice). Tampoco tiene volumen en corto de FINRA.
- **VYLR.** Escindida el 1-oct-2026: poca historia, sin z robusto hasta tener 126 sesiones.
- **Fechas de índices.** Russell pasa a ser semestral desde 2026: la reconstitución de diciembre no está codificada (el
  vencimiento trimestral de diciembre cubre parte). Tampoco hay vencimientos mensuales ni inclusiones o exclusiones en
  índices.
- **Volumen en corto de FINRA.** Es contexto: buena parte es contrapartida de creadores de mercado (40-60 % es normal) y
  no son posiciones cortas.
- **13F.** Solo largos en acciones de gestoras de > 100 M$. Muchos de los mayores son indexados: sus cambios son flujos,
  no opinión.
- **Recompras.** Si una empresa cambia el concepto XBRL a mitad de año, el trimestre derivado puede faltar. Alphabet
  declara 0 $ de recompra en 2026; el dato es de su 10-Q, no un error del cálculo.
- **Nada de esto se ha contrastado como predictor en el proyecto.**
