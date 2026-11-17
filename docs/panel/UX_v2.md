# Panel UX v2: gráficos ampliables y un panel más fácil de usar

**Fecha:** 17-nov-2026.

**Petición del usuario:**
- «me gustaría que los gráficos que aparecen en pequeño se puedan hacer grandes»;
- «me gusta todo lo que tenemos, pero ¿podemos hacerlo un poco más user friendly?».

**Regla:** solo cambia la presentación. No se toca ningún cálculo ni ninguna cifra. Para comprobarlo comparé el panel antes y después: los 12 391 números visibles del HTML son idénticos, quitando lo nuevo, que no lleva cifras propias.

## Dónde está

- **`src/report/_ui.py` (nuevo).** Reúne todas las piezas comunes:
  - el visor de gráficos;
  - la navegación con icono y descripción;
  - el recuadro «Qué significa esto para ti»;
  - la leyenda de colores;
  - el botón «volver arriba»;
  - el plegado de tablas largas;
  - el CSS de legibilidad.

  Todo va inline, sin librerías ni red.
- **`src/report/panel.py`.** Solo lo integra: el CSS y el JS de `_ui`, los botones de las pestañas, el título y el resumen de cada pestaña, la barra de pestañas fuera de la cabecera y el visor al final del `<body>`. Además se tocaron algunas líneas del JS de las pestañas (ver abajo).
- **`src/report/panel_paises.py`.** La guía «¿Cómo leo este panel?» tiene 2 líneas más.
- **No se ha tocado** `mis_activos.py`, `panel_activos.py`, `manos_fuertes.py` ni `panel_manos_fuertes.py`. Sus gráficos se pueden ampliar igual, porque el visor los detecta solo.
- **Tests:** `tests/test_panel_ux.py` (5).

## Cambios (antes → después)

| # | Antes | Después |
|---|---|---|
| 1 | Los gráficos pequeños (minigráficos de «Hoy» de 150 × 34 px, posiciones COT de «Manos fuertes», abanicos de «Qué hacer», puntos de recesión, abanicos por país, errores de «Verificación», correlaciones, barra de pesos de «Mi cartera») solo se veían a su tamaño. | **Todos se pueden ampliar** con un clic o un toque. Se abren en un visor modal a casi toda la pantalla (`<dialog>` nativo, hasta 1200 px y el 96 % del ancho). Se cierra con Esc, con un clic fuera o con el botón «Cerrar». Con teclado: los gráficos grandes llevan un botón «⤢ Ampliar»; en una ficha de «Hoy» o en un minigráfico COT, Intro o Espacio lo abren. Al cerrar, el foco vuelve a donde estaba. |
| 2 | — | **En grande se ve:** el título (el encabezado más cercano o el nombre y valor de la ficha), el subtítulo (la descripción del gráfico) y la nota que lo acompaña (el párrafo o la leyenda de debajo, o la regla del color en las fichas de «Hoy»). Los tooltips de cada fila siguen funcionando dentro del visor. |
| 3 | — | **Los SVG salen nítidos:** se clona el SVG vectorial y se reescala con su viewBox. Las líneas mantienen su grosor en pantalla (`non-scaling-stroke`). Los gráficos con texto no pasan de ×2,4, para que las letras no salgan enormes. Los puntos de los minigráficos no se inflan. Los estilos que dependen de dónde está el gráfico (p. ej. `.verif .chart .int80`) se siguen aplicando, porque se reproducen las clases de sus antecesores con `display:contents`. Funciona en tema claro y oscuro y en móvil. |
| 4 | Cada pestaña solo tenía «En una frase» (y no todas). | **«Qué significa esto para ti»** en las 11 pestañas. Son de 3 a 5 frases llanas: qué mirar, cómo leer los colores y percentiles, y qué no significa (no es una recomendación). Son textos fijos y sin cifras; hay un test que lo vigila. Se mantiene «En una frase». |
| 5 | Las pestañas eran solo texto y estaban dentro de la cabecera: al bajar por la página desaparecían. | **La barra de pestañas se queda fija arriba** al desplazarte. Cada pestaña tiene un icono y una descripción corta («el parte del día», «semáforo de 18 países»…). En móvil se ocultan las descripciones y la barra se desliza en horizontal. Se puede cambiar de pestaña con las flechas ← →. Al cambiar de pestaña, la página vuelve al principio del contenido. |
| 6 | Siempre abría «Hoy». Además, el panel **saltaba solo hasta la pestaña** al abrirse y escondía la cabecera y el resumen de la semana: `history.replaceState('#…')` antes de que terminara la carga activaba el salto al ancla. | **Recuerda la última pestaña** (`localStorage`, siempre dentro de try/catch). El panel abre arriba, con el resumen a la vista. Los enlaces directos `#pais-XXX`, `#act-XXX` y `#<pestaña>` siguen funcionando. |
| 7 | — | **Botón «↑ Arriba»** fijo abajo a la derecha. Aparece al bajar más de 700 px. |
| 8 | Los colores se explicaban solo dentro de la guía plegada. | **Leyenda de colores siempre visible** bajo la guía. Usa los mismos chips con símbolo y palabra que el resto del panel (● verde = bien / normal, ▲ ámbar = vigilar, ■ rojo = mal / alerta, ○ gris = sin dato o descriptivo), así que nunca depende solo del color. También avisa de que los gráficos se amplían. |
| 9 | Tooltip de 12,5 px y sin sombra. Las palabras del glosario tenían un subrayado de puntos gris. | Tooltip de 14 px, más ancho y con sombra. Se oculta al desplazar la página o con Esc. Las palabras del glosario tienen el subrayado en azul y se resaltan al pasar el ratón o al enfocarlas. |
| 10 | Texto de 15 px y tablas de 13,5 px. | Texto de 16 px con interlineado 1,6 y tablas y notas de 14 px. Tarjetas algo más amplias. Las líneas de texto tienen como máximo unos 110 caracteres. Los títulos de pestaña son más grandes e incluyen icono y descripción. En móvil hay márgenes de 12 px y fichas más estrechas. |
| 11 | — | **Tablas largas.** Las de más de 40 filas que no estén ya en un desplegable ni agrupen filas (`rowspan`) muestran 15 filas y un botón «Mostrar las N filas restantes». Hoy ninguna tabla lo activa: las largas ya iban dentro de desplegables. Es una red de seguridad. Para excluir una tabla: `data-no-plegar`. |
| 12 | — | **Impresión:** se ocultan la barra de pestañas, el visor y los botones, y se ven todas las filas. |

**Formato de números:** ya era español (`num()`: coma decimal, punto de miles y signo menos tipográfico). No se tocó ninguna cifra. Quedan restos con punto decimal en textos que vienen tal cual del signal (p. ej. «+0.02 pp» en un aviso de empalme). No los toqué porque son textos del semanal.

## Cómo marcar gráficos nuevos (para otros módulos)

No hace falta hacer nada: el visor detecta cualquier `<svg>` con viewBox (o con width y height), cualquier `<img>` y cualquier `.segbar` dentro de `<main>`. Los atributos opcionales son:
- `data-zoom` para ampliar cualquier otro elemento HTML;
- `data-zoom="no"` para excluir uno;
- `data-zoom-titulo` y `data-zoom-nota` para fijar el título y la nota del visor.

## Comprobaciones

- **Panel generado** con `--out` en el scratchpad (no en `~/financial_archive/panel`), con el signal del 17-nov y una copia del warehouse: «error al generar» = 0.
- **JS:** `node --check` sin errores; también va en un test.
- **Chrome headless** (script de prueba inyectado) sobre 108 elementos ampliables, de ellos 46 con botón:
  - se abre con clic en el botón, con clic en el minigráfico y con Intro sobre la ficha o sobre el minigráfico COT;
  - se cierra con Esc, con un clic fuera y con «Cerrar», y el foco vuelve;
  - abre bien en «Hoy», «Qué hacer», «EE. UU. y recesión», «Escenarios», «Manos fuertes», «Mi cartera» y «Verificación»;
  - la última pestaña se recuerda;
  - 0 errores JS.
- **Capturas** a 1300 px en claro y oscuro y a 500 px (el mínimo de headless).
- **Tests:** `test_panel_ux`, `test_intl_panel`, `test_panel_paises`, `test_panel_hoy`, `test_panel_que_hacer`, `test_mis_activos`, `test_mis_activos_corta`, `test_manos_fuertes`, `test_percentil`, `test_verif` y `tests/validation/`: **95 pasan** (antes 90, más los 5 nuevos).
