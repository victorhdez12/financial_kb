# Prueba de uso del panel (17-nov-2026)

**Objeto:** `~/financial_archive/panel/index.html` (reporte semanal del 2026-11-17, panel generado el 2026-11-17 15:13; signal 2026-11-17T08:38).
**Método:** Chrome headless (`--headless=new`) manejado por CDP con un script de Node (sin playwright); recorrido de las 11 pestañas a 1280 px, 1100 px (tema claro), 480 px y 400 px (emulación móvil). No se ha tocado código de producción.
**Veredicto:** ✅ usable. **0 fallos altos**, 4 medios y 10 bajos. Ninguno impide usar el panel; los medios afectan a la coherencia de cifras entre pestañas, a datos con retraso y a la lectura en móvil.

## Qué pasó sin problemas

| comprobación | resultado |
|---|---|
| Errores de consola JS (excepciones, `console.error/warn`, Log) al cargar y en todas las interacciones | **0** |
| Las 11 pestañas se muestran, con contenido (2.000-11.500 caracteres cada una) | ✅ |
| Texto «undefined», «NaN», «None», «null», «Infinity» (con todos los desplegables abiertos) | **0** |
| Visor de gráficos: abre con clic (8 pestañas, 1-37 gráficos ampliables por pestaña); cierra con Esc, con «Cerrar» y con clic fuera; con teclado (foco + Enter) abre y, al cerrar con Esc, el foco vuelve al gráfico | ✅ |
| Enlaces internos: 30 `a.actlink` (#act-XXX), 14 `a[data-pais]` (→ Escenarios con el país elegido), 3 `#atlas-…`; 0 rotos | ✅ |
| Enlaces profundos al cargar (`#act-MSFT`, `#act-BZ=F`, `#act-BAYN.DE`, `#pais-ESP`, `#atlas-expansion`, `#escenarios`): abren la pestaña y el desplegable correctos | ✅ (ver B1) |
| Tema claro/oscuro: cambia fondo y texto; se guarda (`panel_tema`) y se mantiene al recargar | ✅ |
| Recordar pestaña: al recargar vuelve a la última (`panel_pestana`) | ✅ |
| Desplegables: 66 `<details>`, todos con `<summary>` y contenido | ✅ |
| Fecha de cabecera = fecha del signal (2026-11-17) = «Procedencia» en Estado; «Estado y avisos (5)» = 5 avisos | ✅ |
| Cifras repetidas coherentes: IPC EE. UU. 3,9 % (Hoy) / 3,95 % (Qué hacer); paro EE. UU. 4,1 %; curva 10a−3m 0,83 pp; NFCI −0,46; liquidez neta Fed 5.844 mm; σ̂ B1 10,7 % (Qué hacer = Mi cartera); lista de 9 países en rojo (Hoy) = celdas rojas de Países | ✅ (salvo M1, M2, B4) |

## Fallos

| id | gravedad | pestaña | fallo | cómo reproducir |
|---|---|---|---|---|
| M1 | **Media** | Países (frente a Hoy y Qué hacer) | La inflación de EE. UU. en el semáforo de Países es **3,7 % (dato de sep-2026)**, mientras Hoy muestra **3,9 % (dato del 2026-10-01)** y Qué hacer «IPC actual 3,95 % (2026-10)». El IPC de octubre salió el 10-nov y Países sigue con el de septiembre: la misma cifra clave aparece distinta en dos pestañas. | Países → fila EE. UU., pasar el ratón por «3,7 %» (tooltip «dato de sep-2026»); comparar con Hoy → ficha «IPC general a/a». |
| M2 | **Media** | Hoy (frente a Mis activos) | Los datos de mercado de Hoy (VIX, crédito HY/IG, curvas, caída del S&P 500) son del **13-nov (viernes)**, no del último día hábil (**16-nov**), y Mis activos sí usa el 16-nov. Resultado: la caída del S&P 500 desde máximos es **−3,3 %** en Hoy y **−5,0 %** en la ficha de SPY. Causa probable: FRED publica el cierre del día D por la tarde de D+1 y la ingesta corre a las 7:25-7:30, así que Hoy siempre va 1-2 días hábiles por detrás. Cada ficha enseña su fecha, pero nada avisa de que no es el último cierre. El WTI de Hoy es del 11-nov. | Hoy → fichas VIX/«S&P 500: caída desde su máximo» («dato del 2026-11-13»); Mis activos → «Precio (2026-11-16)», ficha SPY «Caída desde máximo 52 semanas −5,0 %». |
| M3 | **Media** | Qué hacer, Escenarios, Manos fuertes, Verificación, Países y Mis activos (fichas abiertas) | **Móvil (400-480 px): el contenido se sale por la derecha.** Las insignias y chips con `white-space: nowrap` no se ajustan: Qué hacer (insignia «B1 es la única regla…», ancho del documento **1.237 px**; el texto queda cortado e ilegible), Escenarios (insignia «cerca del umbral del 3 %…», 558 px), Manos fuertes (chip «la CFTC ya habrá publicado…», 575 px), Verificación (insignia «retrospectivo…», 468 px a 400 px). Con fichas abiertas, la tabla de escenarios por activo de Países (742 px) y las tablas de las fichas de Mis activos (751 px) tampoco caben. | Chrome, ancho 400 px (DevTools, modo dispositivo) → Qué hacer: la insignia verde bajo la recomendación sale cortada; `document.documentElement.scrollWidth` = 1237. |
| M4 | **Media** | Manos fuertes | El posicionamiento CFTC es del **3-nov** (publicado el 6-nov); el informe posterior (publicado el 13-nov) no está cargado. El panel lo avisa con un chip («el warehouse no se ha reconstruido con él»), pero tras la ejecución semanal del 17-nov el dato sigue con 2 semanas de retraso. | Manos fuertes → «Qué dice hoy (futuros)». |
| B1 | Baja | Mis activos, Países, Atlas (enlaces) | Al seguir un enlace a una ficha (`#act-XXX` desde la tabla, o un enlace profundo `#act-…/#pais-…/#atlas-…`), el destino queda en `top: 0` y la **barra de pestañas fija (106 px a 1280 px) tapa el título** de la ficha (falta `scroll-margin-top`). | Abrir `index.html#act-UBER`: se ve «Situación (2026-11-16)», pero no el título «Uber UBER». |
| B2 | Baja | Países, Mis activos | **«s/d» (74 en Países y 32 en Mis activos).** *Justificados:* VYLR (cotiza desde el 1-oct-2026: sin 3 meses, año, 12 m, volatilidad ni beta); Form 4/13F de BAYN.DE (no cotiza en EE. UU.); 13F de VYLR. *Estructurales, mejor ocultarlos:* «diferencial con Alemania» en DEU (consigo mismo) y en países fuera del euro (USA, GBR, JPN, SWE, DNK, NOR, CHE, CAN, AUS); «IPCA (BCE)» en países no UE (USA, GBR, JPN, NOR, CHE, CAN, AUS); beta/correlación de SPY con el S&P 500 (es el propio índice: 1/1). *Huecos de datos a revisar:* IPCA (BCE) de **BEL y FIN** (zona euro) y de SWE y DNK; CLI OCDE en NLD, BEL, PRT, IRL, FIN, SWE, DNK, NOR y CHE (probablemente la OCDE no lo publica para ellos); tipo a 3 meses y curva 10a−3m de GBR y JPN (a GBR se le declara un empalme BoE SONIA en el termómetro, pero el detalle de Países sigue en s/d); paro de CHE; producción industrial y percentil del IPC de AUS; confianza del consumidor de NOR; dinero amplio (FMI) de GBR y CHE. | Países → abrir cada país; Mis activos → fichas VYLR, BAYN.DE y SPY. |
| B3 | Baja | Qué hacer | En el abanico de **Oro** (EE. UU.), la etiqueta «p95 56 %» se solapa con el botón «Ampliar». | Qué hacer → abanicos, país EE. UU., tarjeta Oro. |
| B4 | Baja | Hoy frente a Países | Irlanda «en recesión» sale en **ámbar** en «En rojo o ámbar hoy» y en **rojo (■)** en la columna Recesión de Países. | Comparar las dos pestañas. |
| B5 | Baja | Qué funciona en cada régimen | «Qué significa esto para ti» y «En una frase» dicen **18 países**; el cuerpo dice «14 países ricos (JST), 1870-2004». | Abrir la pestaña. |
| B6 | Baja | Manos fuertes frente a Mis activos | «Fuentes, retrasos y lo que falta» dice «13F (carteras de grandes gestoras), **no incluido**», pero las fichas de Mis activos sí tienen la sección «Grandes gestoras (SEC 13F, trimestral)». | Manos fuertes → abrir «Fuentes…»; Mis activos → ficha MSFT. |
| B7 | Baja | Hoy | En «Datos nuevos publicados», **PPIACO sale dos veces** (una con «vintage ALFRED» y otra con «fecha de actualización de FRED»). | Hoy → tabla «Datos nuevos publicados». |
| B8 | Baja | Hoy, EE. UU., Manos fuertes | Formatos: «Δ −0,00» (CISS), «−0,0 %» (gas natural, productores); separador de miles distinto para la misma cifra («5 844 mm USD» en Hoy, «5.844» en EE. UU. y recesión). | Ver las fichas citadas. |
| B9 | Baja (claridad) | Hoy | El paro de la zona euro sale en «ámbar · **sube**» con «Δ +0,0 pp vs anterior»: la regla mira el cambio en 12 meses (≥ 0,2 pp) y la ficha enseña el cambio frente al mes anterior. Solo el tooltip lo aclara. Lo mismo pasa con la deuda/PIB de EE. UU.: **127 %** (Países, FMI) frente a **121,2 %** (EE. UU. y recesión, ciclo largo), que vienen de fuentes distintas sin rotularlo. | Hoy → Zona euro → Paro (tooltip). |
| B10 | Baja (info) | Mis activos | Bayer (BAYN.DE) tiene precio del **13-nov** y el resto del 16-nov. La fecha se muestra en la tabla, así que la diferencia se ve. | Mis activos → tabla, fila Bayer. |

## Notas

- La prueba no cambia el panel; los arreglos quedan para el generador (`src/report/panel*.py`, `_ui.py`, `activos_v2.py`).
- Guía de uso generada aparte (fuera de git, porque contiene datos de terceros): `~/financial_archive/panel/Guia_panel.pdf` (fuente en `~/financial_archive/panel/guia_src/`).
