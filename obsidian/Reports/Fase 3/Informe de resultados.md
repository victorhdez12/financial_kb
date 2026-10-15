---
tipo: informe_resultados
fase: 3
version: 0.2 (etiqueta v1.1, validaciones y revisión económica)
actualizado: 2026-10-15
autor: Reportero
graficos: src/report/fase3/make_figures.py
cifras_derivadas: "obsidian/Reports/Fase 3/img/cifras.json"
---

# Fase 3 · Informe de resultados

> [!info] Cómo leer este informe
> Está pensado para leerse sin saber econometría. Cada cifra importante lleva su fuente: un fichero del proyecto o el warehouse. Las cifras que he calculado yo para este informe (por ejemplo, la comparación con el clasificador de reglas) salen del script `src/report/fase3/make_figures.py` y quedan guardadas en `img/cifras.json`. Las palabras técnicas están en el [[#10. Glosario|glosario]] del final.
> Ver también [[Proyecto/Estado del proyecto]], [[Proyecto/Etiqueta de régimen]] y [[Proyecto/Agentes]].

> [!note] Qué ha cambiado desde la versión del 14-oct
> - La etiqueta pasa a la **v1.1, congelada y validada ✅** (§3.8 y §4). Todos los gráficos usan ya la v1.1.
> - Nuevo **§4 Validación independiente**: la v1.0 salió ⚠️ con condiciones; la v1.1, ⚠️ y después ✅ en la re-auditoría de cierre.
> - Nuevo **§5 El listón que hay que batir**: la persistencia point-in-time acierta el **63,6 %**. El 89 % del "mes anterior" hace trampa.
> - Nuevo **§6 Revisión económica del Estratega macro**: la etiqueta "sirve con cambios". El cuadrante `late_cycle` se llama ahora **"Crecimiento con inflación alta"** en todo el informe.
> - Nuevo **§7 Decisiones del 15-oct**: capas ex post preregistradas, lo que se pospone y el registro de pruebas.
> - El periodo bloqueado es ahora **2005-01 → abierto** (antes se preveía 2016-2026).

---

## 1. Resumen en una página

### Qué queremos conseguir
Queremos que el sistema diga **cada mes en qué "clima económico" (régimen) está EE. UU. y con qué probabilidad**, usando solo la información que existía ese día. Además, tiene que quedar **demostrado en un backtest honesto que lo hace mejor que las alternativas sencillas**. La más importante es la persistencia: "el régimen sigue igual que el último que se podía conocer"[^obj].

### Dónde estamos

**Entregables** (en orden)[^obj]:

| # | entregable | estado |
|---|---|---|
| 1 | Etiqueta de régimen (la "respuesta correcta") | ✅ **v1.1 congelada y validada** el 15-oct (tag `label-v1.1`) |
| 2 | Base point-in-time + calendario de publicación + test de fugas | ▶ **en marcha** (Constructor, lanzado el 15-oct) |
| 3 | Arnés walk-forward (embargo de 6 m, 2005-01 → bloqueado, registro de pruebas) | ⏳ pendiente |
| 4 | Modelos sencillos: persistencia, reglas, logística, Markov | ⏳ pendiente. El listón de la persistencia ya está medido: **63,6 %** (§5) |
| 5 | GBM, solo si bate a los anteriores | ⏳ pendiente |
| 6 | Calibración | ⏳ pendiente |
| — | En paralelo: investigación de relaciones adelantadas | 🟡 programa escrito y 5 hipótesis preregistradas (2 de derivados, 3 capas ex post); sin resultados de modelos |

**Semáforo de los criterios de cierre de la fase**[^obj]:

| criterio | estado |
|---|---|
| Bate a la persistencia en log-loss fuera de muestra, también en el periodo bloqueado, con intervalos que no incluyen el cero | ⬜ sin modelos aún. Lo que sí hay: el **listón medido** (persistencia PIT, log-loss 1,235; §5) |
| Probabilidades calibradas | ⬜ |
| Sin fugas: test point-in-time, placebo y señal plantada superados | 🟡 lista negra de columnas en código con tests; la base PIT, el placebo y la señal plantada están en construcción |
| Relaciones con mecanismo, estables por épocas y países, que sobreviven a la corrección por comparaciones múltiples | ⬜ hay registro de hipótesis y de pruebas; sin resultados |
| Veredicto ✅ del Validador independiente | 🟡 ✅ para la **etiqueta v1.1**; falta todo lo demás |
| Ficha del modelo + informe de resultados | 🟡 este informe va por la v0.2; la ficha del modelo no existe todavía |
| Sustituye al clasificador de reglas en el reporte semanal | ⬜ |

**En una frase:** la "respuesta correcta" ya está definida, congelada, validada por un auditor independiente y revisada por un economista, y sabemos qué nota tiene que batir un modelo (63,6 % de acierto). Todavía no hay ningún modelo.

### Régimen actual según la etiqueta (provisional)

- **Último mes con etiqueta: abril de 2026 → inflación persistente con crecimiento en torno a tendencia, con sesgo estanflacionario.** El cuadrante más probable es Estanflación (60 %); el resto se reparte así: crecimiento con inflación alta 31 %, crecimiento bajo/desinflación 6 % y expansión 3 %. El crecimiento está algo por debajo de su tendencia (G = −0,17) y la inflación subyacente va al 2,9 % anualizado[^ult].
- **Por qué no decimos "Estanflación" a secas:** la palabra evoca 1974 o 1980 (recesión con inflación del 8-9 %), y hoy no hay recesión. G está a menos de una "anchura" de incertidumbre del cero, el paro está estable y el PIB creció un 2-2,5 % en el primer semestre de 2026. Esta es la lectura que pide el Estratega macro (§6.4)[^macro].
- En los últimos 24 meses con etiqueta, **19 caen en el cuadrante de estanflación**. Desde noviembre de 2025 lo están todos, aunque febrero y marzo de 2026 son meses "frontera": ninguna opción llega al 55 %[^ult24].
- ⚠️ **Es provisional y no debe leerse como un dato firme.** Los últimos 54 meses (2021-11 → 2026-04) cambiarán a medida que lleguen datos y se revisen (§3.9). Además, la etiqueta **termina en abril de 2026**: para fijar el mes t hacen falta datos hasta t+4, así que de mayo a octubre de 2026 aún no hay etiqueta. Tampoco recoge todavía el shock del petróleo de 2026 (WTI por encima de 90 $ desde marzo), que afecta sobre todo a la inflación general[^macro].

### Diferencia con el clasificador de reglas actual

El reporte semanal sigue usando el **clasificador de reglas de la Fase 1** (`src/regime`). Su lectura actual es **"Deflación/recesión" en septiembre y octubre de 2026**, y "Estanflación" de mayo a agosto[^reglas].

| | clasificador de reglas (Fase 1) | etiqueta v1.1 |
|---|---|---|
| Para qué sirve | Decir el régimen **hoy**, solo con el pasado | Decir **a posteriori** qué régimen hubo, con datos definitivos |
| Mira hacia delante | No | Sí (hasta t+4 meses, y la tendencia hasta t+60). Por eso no puede usarse como predictor |
| Coincidencia con la etiqueta, 1955-2021 (802 meses) | **52 %** de los meses (51,6 %) | — |
| Coincidencia en los últimos 24 meses con etiqueta | 9 de 24 | — |

La coincidencia del 52 % es un cálculo mío y solo **orientativo**[^comp]. Los dos sistemas no usan las mismas definiciones y esto no es el backtest point-in-time oficial. Además, el Validador advierte que las reglas de la Fase 1 se diseñaron conociendo 2008 y 2020, así que su resultado no es "limpio"[^val10]. Aun así, enseña algo importante: **adivinar el régimen en tiempo real es difícil**. El listón formal es la persistencia point-in-time (§5).

---

## 2. Los datos

*(Sin cambios de fondo desde el 14-oct; el gráfico se ha regenerado el 15-oct y da las mismas cifras.)*

### Qué tenemos

- **15.610 series** de **55 fuentes** en la base de datos (`data/warehouse.duckdb`, tabla `catalog`)[^cob], con unos 12,5 millones de observaciones[^estado]. Además hay vintages ALFRED (las versiones "tal como se publicaron") de 18 series clave, con 185.606 filas (tabla `vintages`).
- El 58 % de las series es de EE. UU. (9.099 con `country_iso3 = USA`). El resto cubre la zona euro, España, Alemania, Reino Unido, Japón y el resto del mundo.
- **Por bloque económico** (agrupando la columna `category` del catálogo):

| bloque | series |
|---|---|
| Tipos y crédito | 6.559 |
| Crecimiento, empleo y vivienda | 3.504 |
| Dinero y liquidez | 1.884 |
| Mercados (bolsa, divisas, valoración) | 1.646 |
| Inflación y materias primas | 1.125 |
| Fiscal, geopolítica y otros | 892 |

- **Historia:** 1.569 series tienen dato en 1900, 4.686 en 1950 y 9.728 en 2000[^cob]. Las más largas vienen de NBER Macrohistory, JST (18 países desde 1870), Shiller, el Banco de Inglaterra y MeasuringWorth.
- **Actualización automática:** launchd actualiza los datos de lunes a sábado a las 7:30 y los domingos a las 7:00 (todo + auditoría + reporte), con una tarea de arranque que recupera la actualización si el Mac estaba apagado[^estado].

![[Reports/Fase 3/img/01_cobertura_por_bloque.png]]

*Cómo leerlo:* cada franja de color es un bloque, y la altura total es el número de series con algún dato ese año. La caída de los últimos años no quiere decir que se pierdan datos. Una serie solo cuenta en 2026 si ya tiene un dato de 2026 (hoy son 7.646), y muchas son anuales, se publican con retraso o están cerradas. La caída puntual de 1941-45 **no la he investigado**; probablemente se debe a series que se interrumpen durante la guerra.

### Cómo se auditaron
El **Auditor de datos** no modifica nada: solo comprueba. Su última auditoría completa (14-oct) dio **0 problemas críticos y 33 altos** (32 ya explicados y un falso positivo) y un **error real** en la EPA del INE de 1976-2001, corregido el mismo día. No afectaba a ninguna serie de EE. UU. ni al régimen[^aud][^estado].

### Limitaciones que quedan
- **Huecos de pago o sin API:** PMI, Euribor diario, MOVE, Global Financial Data y las curvas de futuros por vencimiento[^aud][^fut].
- **Fuentes que ya no se actualizan:** los futuros de WTI y gas de la EIA (hasta 2024-04-05). Sirven para investigar, no para producción.
- **Licencias:** AQR y Cboe solo uso personal; JKP y JST, no comercial; Fed Atlanta, personal o educativo[^aud][^fut]. **Importa si el informe se comparte fuera.**
- **Point-in-time incompleto:** varias series se reescriben hacia atrás (AQR, JKP, Z.1, SOFR) y `GDPPOT` es una proyección de la CBO. Esta última ya está en la **lista negra** de variables (§3.8)[^spec].

---

## 3. La etiqueta de régimen (v1.1)

### 3.1 Qué es y por qué hace falta
Para saber si un modelo "acierta" el régimen, primero hay que decir **cuál fue el régimen de verdad** en cada mes. Eso es la etiqueta: la **respuesta correcta del examen**. Todo lo que venga después (persistencia, logística, GBM…) se medirá contra ella.

Por eso se define **antes** de modelar y se **congela**, para que nadie la retoque a escondidas y así los modelos "salgan mejor". Cualquier cambio obliga a crear una versión nueva y a repetir todas las comprobaciones[^spec].

La etiqueta **sí puede mirar el futuro**: usa datos revisados y meses posteriores, porque describe el pasado con todo lo que sabemos hoy. Los modelos no pueden hacerlo. Por eso la etiqueta **nunca** puede entrar como variable de un modelo; desde la v1.1 esto lo impide el propio código (§3.8).

### 3.2 Cómo se define, en lenguaje llano
Cada mes se responde a dos preguntas[^spec]:

1. **¿La economía crece por encima o por debajo de lo normal?** (eje **G**). Se usan los cuatro indicadores que mira el comité que fecha las recesiones en EE. UU. (NBER): producción industrial, empleo, renta real sin transferencias y ventas reales. Para cada uno se mide su ritmo de crecimiento en una ventana de unos 6 meses **centrada en el mes** y se compara con su ritmo "normal" (la mediana de los 10 años de alrededor). Si G > 0, la economía crece por encima de su tendencia.
2. **¿La inflación de fondo está alta?** (eje **I**). Se usa la inflación subyacente PCE (la que sigue la Fed), anualizada en una ventana de 6 meses centrada en el mes, y se compara con un **umbral fijo de 2,5 %** (el objetivo del 2 % más un margen).

Las dos respuestas forman **cuatro cuadrantes**:

| | inflación baja (< 2,5 %) | inflación alta (> 2,5 %) |
|---|---|---|
| **crecimiento por encima de tendencia** | 🟢 **Expansión** | 🟡 **Crecimiento con inflación alta** |
| **crecimiento por debajo de tendencia** | 🔵 **Crecimiento bajo / desinflación** | 🔴 **Estanflación** |

> [!warning] Sobre los nombres
> - **"Crecimiento con inflación alta"** (identificador interno `late_cycle`) se llamaba antes "Late cycle / sobrecalentamiento". El Estratega macro mostró que el nombre engañaba: como G mide el **ritmo** frente a la tendencia, en este cuadrante caen tanto los sobrecalentamientos (1976-79) como las **recuperaciones tempranas** con paro alto e inflación que baja (1975-76, 1983-85). Son situaciones opuestas para invertir[^macro].
> - **"Estanflación"** aquí solo quiere decir crecimiento por debajo de tendencia con inflación subyacente > 2,5 %. **No implica recesión.**
> - "Recesión" **no** es un cuadrante: es una capa aparte (las fechas oficiales del NBER).

### 3.3 Por qué probabilidades y no una etiqueta fija
Los datos se revisan, y un mes que está justo en la raya podría caer a cualquier lado. Por eso, en vez de decir "estanflación sí o no", la etiqueta da **una probabilidad para cada cuadrante**. Cuanto más lejos del umbral, más segura.

La "anchura" de esa incertidumbre (s) **no se ha elegido a ojo**. Sale de cuánto se revisan de verdad los datos entre su primera publicación y hoy (archivo ALFRED): **s_G = 0,40** y **s_I = 0,31 puntos**[^spec][^chk].

> [!example] Ejemplo: abril de 2026
> - **Crecimiento:** G = −0,17, un poco por debajo de lo normal. La distancia al umbral es −0,17 / 0,40 ≈ −0,4 "anchuras", así que P(crecimiento alto) = **34 %**.
> - **Inflación:** I = 2,93 %, por encima de 2,5. La distancia es (2,93 − 2,5) / 0,31 ≈ +1,4 anchuras, así que P(inflación alta) = **92 %**.
> - **Estanflación** = crecimiento bajo × inflación alta = 0,66 × 0,92 ≈ **60 %**. Crecimiento con inflación alta = 0,34 × 0,92 ≈ **31 %**.
> - La duda está casi toda en el crecimiento: lo que es seguro es que la inflación sigue por encima del objetivo.
>
> Valores del fichero `regime_us_v1.1.parquet` (columnas `G`, `I`, `p_g_high` = 0,339 y `p_i_high` = 0,915).

Los modelos se puntuarán contra estas probabilidades (log-loss). Además existe una **etiqueta dura** (el cuadrante más probable) para leer los resultados. Cuando la opción más probable no llega al 55 %, el mes se marca como **frontera**: pasa en el 8 % de los meses puntuables (64 de 802)[^chk].

### 3.4 La historia desde 1950

![[Reports/Fase 3/img/02_historia_cuadrantes.png]]

- **Años 70 y Volcker (1979-82):** domina el rojo y el ámbar. El 75 % de los meses de 1973-75 y de 1979-80 salen como estanflación[^chk].
- **1995-99:** expansión (verde) en el 78 % de los meses.
- **2008-09:** crecimiento bajo/desinflación en el 96 %. **2020:** un desplome cortísimo (67 % de los 3 meses del segundo trimestre).
- **2021-22:** crecimiento con inflación alta. Los meses maduros de 2021 (mayo a octubre) son todos de ese cuadrante; 2022 ya es provisional.
- **Recesiones:** en el **100 % de los 103 meses de recesión NBER** puntuables, la etiqueta dice que el crecimiento estaba por debajo de tendencia. De esos meses, 60 son estanflación (sobre todo en los 70 y principios de los 80) y 43 crecimiento bajo/desinflación. Con la v1.0 eran 57 y 46: la diferencia son 3 meses de la recesión de 1957 que cambian con el nuevo empalme (§3.8)[^cifras].

Por décadas se ve que **los regímenes van por épocas**: en los 70 y 80 apenas hay expansión (0-1 %), y en 2000-2019 casi no hay estanflación (0-3 %)[^chk]. Esto importa para los modelos (un modelo entrenado en una época puede no haber visto nunca el régimen de la siguiente) y es el centro de la crítica del Estratega macro (§6).

### 3.5 El mapa crecimiento × inflación

![[Reports/Fase 3/img/03_mapa_G_I.png]]

Cada punto es un mes. El cuadrante solo depende de dos cosas: el lado de la línea vertical (G = 0) y el lado de la horizontal (inflación = 2,5 %). Los puntos cerca de las líneas son los meses dudosos.

Los episodios caen donde deben: 1974-75 y 1979-80 arriba a la izquierda, 2008-09 abajo a la izquierda, 1997-99 abajo a la derecha y 2021 arriba a la derecha. **Los últimos 6 meses (provisionales) están pegados a la línea de crecimiento cero**, y por eso dudan entre estanflación y crecimiento con inflación alta.

### 3.6 Cuánto dura cada régimen

![[Reports/Fase 3/img/04_reparto_y_duracion.png]]

- **Reparto equilibrado:** expansión 30 %, crecimiento con inflación alta 23 %, estanflación 24 % y crecimiento bajo 23 % de los 802 meses puntuables[^chk].
- **Los regímenes duran poco:** 86 tramos, con una media de 9,3 meses y una mediana de 6. La expansión dura más (media de 12,1 meses, máximo 50); la estanflación y el crecimiento bajo son los más cortos en mediana (4 meses)[^chk].
- **De un mes al siguiente, el régimen se repite el 88-92 % de las veces** (matriz de transición)[^chk]. Parece que eso hace muy fácil la persistencia, pero **es una trampa**: el mes anterior todavía no se conoce el día en que hay que decidir (§5).

### 3.7 Qué salió en las comprobaciones
Antes de congelar la etiqueta se pasa una batería de comprobaciones de **sentido común**. Sirven para detectar errores, **no para ajustar parámetros** hasta que la historia "cuadre"[^spec]. En la v1.1, **las 13 pasan**[^chk]:

| comprobación | exigido | resultado |
|---|---|---|
| Meses de recesión NBER con crecimiento bajo | ≥ 85 % | **100 %** (103 meses) ✅ |
| Correlación con el índice de actividad CFNAI-MA3, mismo mes | > 0,7 | **0,74** ✅ |
| Correlación con el CFNAI en la misma ventana que G | > 0,7 | **0,95** ✅ |
| Correlación con los cambios de la brecha de producción | > 0,6 | **0,88** ✅ |
| Episodios (1973-75, 1979-80, 1995-99, 2008-09, 2020, 2021-22) | el régimen esperado | todos ✅ |
| Ningún cuadrante por debajo del 10 % | ≥ 10 % | mínimo 23 % ✅ |
| Duración media de los regímenes | ≥ 6 meses | 9,3 meses ✅ |
| Correlación entre G e I | se informa | −0,13 (1984+: 0,27) ✅ |

**Acierto esperado de la etiqueta dura frente a la probabilística:** 82,8 % (85,7 % sin los meses frontera)[^chk]. Incluso la "respuesta correcta" lleva incorporado algo menos de un 20 % de duda.

**Lo que no cuadra del todo (y se ha explicado, no tapado):**
- El Validador señaló que **varias comprobaciones son débiles o en parte circulares**. La del CFNAI en la ventana de G (0,95) usa casi los mismos datos que G y solo demuestra que el cálculo es correcto. La de recesiones solo mide un lado: G < 0 en el 46,9 % de los meses, y solo el 27,4 % de esos meses son de recesión. **No había ninguna comprobación del eje de inflación**; el Validador hizo las que faltaban y salen bien (correlación 0,96 con la PCE media recortada de la Fed de Dallas; 100 % de acierto en los episodios de inflación de la literatura)[^val10].
- En 2022-2024, G y el CFNAI se mueven en sentido contrario (correlación −0,55). No es un fallo de cálculo: la manufactura estaba floja mientras el empleo y la renta real crecían. Esos meses son provisionales y no puntúan[^rev].

### 3.8 La historia v0.1 → v0.2 → v1.0 → v1.1

**v0.1: un desfase de 4 meses que no se veía a simple vista.** La primera versión medía el crecimiento con ventanas **hacia atrás**. Una comprobación falló (correlación con el CFNAI del mismo mes 0,62 < 0,7) y, en vez de bajar el listón, se investigó por qué: la etiqueta del mes t describía en realidad el crecimiento de unos 4 meses antes[^v01].

![[Reports/Fase 3/img/07_desfase_v01_v02.png]]

*Cómo leerlo:* a la izquierda, la línea gris (v0.1) tiene su máximo a la izquierda del cero: se parecía más al pasado. La negra (v0.2 a v1.1, que comparten la misma G) lo tiene en k = +1/+2, como se espera. A la derecha, en la crisis de 2008, la v0.1 tocaba fondo **4 meses más tarde**[^cifras].

**v0.2: ventanas centradas.** Cambiaron de cuadrante 244 de 856 meses (28,5 %), casi todos alrededor de los giros, y el cuadrante G↓I↓ pasó a llamarse "crecimiento bajo/desinflación"[^v02]. **Lección:** un error así no da ningún mensaje de error; solo aparece si se compara la etiqueta con una referencia independiente.

**v1.0 (14-oct): congelada.** Solo cambian las escalas de incertidumbre (s_G de 0,33 a 0,40). Se fijan los **54 meses provisionales** y un **embargo de 6 meses**[^spec].

**v1.1 (15-oct): congelada y validada.** Responde a las condiciones del Validador sobre la v1.0 (§4). No cambia la definición. Cambia cuatro cosas:

1. **Empalme de 1957-59 medido, no supuesto.** Antes de 1959 no existe la PCE subyacente y se usa el IPC subyacente con un ajuste. La v1.0 restaba 0,4 pp (la diferencia media de *toda* la muestra). El Validador vio que esa cifra no representa los años del empalme. La v1.1 mide el ajuste en los 24 primeros meses en que coexisten las dos series (1959-04 → 1961-03): **+0,20 pp**. Resultado: I sube 0,60 pp en 1957-04 → 1959-03 y **6 meses de 1957 pasan de crecimiento bajo a estanflación**. Nada más cambia: ni G, ni el resto de la historia, ni los parámetros[^chk11][^spec]. La regla la eligió el usuario tras ver que cualquier ajuste entre 0 y +0,30 pp da la misma etiqueta dura[^val11].
2. **Entradas congeladas.** La etiqueta oficial ya no se calcula desde la base de datos viva (que se actualiza cada día), sino desde una **instantánea** de las 7 series de entrada con su huella digital (SHA-256) guardada en git. Si alguien altera la instantánea o el fichero oficial, los tests fallan. La instantánea y el parquet están sin permisos de escritura y hay copia de respaldo[^spec][^bit].
3. **Lista de columnas prohibidas.** Ninguna columna de la etiqueta (`G`, `I`, `p_*`, `label_hard`, `frontera`, `usrec`…), ni las 485 series del warehouse que son previsiones o miran al futuro (como `GDPPOT`), puede entrar como variable de un modelo, **ni tampoco sus derivadas** (`usrec_lag1`, `G_lag5`…). Lo comprueba el código (`assert_no_forbidden`) con tests. Como una lista por nombre no detecta una columna renombrada sin rastro, el arnés construirá las variables desde una **lista blanca** y la lista negra queda como segunda barrera[^spec].
4. **Uso point-in-time documentado:** la etiqueta más reciente calculable el día de la decisión es la de t−5, el listón de la persistencia es el 63,6 % (§5) y el periodo bloqueado empieza en 2005-01[^spec].

![[Reports/Fase 3/img/08_empalme_v10_v11.png]]

*Cómo leerlo:* la línea discontinua es la inflación de la v1.0 y la negra la de la v1.1. Solo difieren en el tramo punteado. Con la v1.0 había un salto artificial en 1959-04 (de 1,62 a 2,22); con la v1.1 la serie es continua (2,22 → 2,22). Los círculos rojos son los 6 meses que cruzan el umbral del 2,5 %[^chk11][^val11].

### 3.9 El estudio de revisión: qué significan los 54 meses provisionales
**El problema:** para fijar el mes t, la etiqueta necesita datos de hasta 4 meses después, y la tendencia necesita 5 años a cada lado. Por eso **los meses recientes todavía cambiarán** cuando lleguen datos nuevos.

**Cómo se respondió:** se viajó al pasado 100 veces (un corte cada 6 meses entre 1975 y 2024). En cada corte se recalculó la etiqueta **solo con los datos que había hasta esa fecha** y se comparó con la definitiva. La regla para decidir se fijó **antes** de ver los resultados[^rev].

![[Reports/Fase 3/img/05_estudio_revision.png]]

- Con 4 meses de antigüedad, la etiqueta dura coincide el 92,6 % de las veces. Con 54-55 meses se superan los dos umbrales (≥ 95 % y Δp ≤ 0,05) → **54 meses provisionales**[^rev].
- **Qué añadió el Validador:**
  - **k\* es frágil** ante el muestreo (en remuestreos sale entre 50 y 80), aunque 54 está en el codo. Recomienda probar también con 60 meses provisionales en el backtest[^val10].
  - **La inflación tiene un suelo de ruido que no se va con el tiempo.** El estudio solo revisaba el crecimiento. Con las vintages de la PCE (2000-2024), incluso con 84 meses de antigüedad la etiqueta dura solo coincide en el ~94 % de los meses, porque las grandes revisiones de las cuentas nacionales reescriben la inflación pasada. Además, la primera publicación de la inflación va de media 0,16 pp por debajo de la final. **Ningún modelo en tiempo real puede acertar el 100 %**[^val10][^spec].

**Qué significa en la práctica:**
- Hoy, **todo lo posterior a octubre de 2021 es provisional**: no sirve para entrenar ni para puntuar.
- El régimen "actual" de la etiqueta (§1) puede cambiar, y bastante.
- **Periodo bloqueado:** el previsto 2016-2026 solo tenía unos 70 meses maduros. Por recomendación del Validador, el usuario lo adelantó a **2005-01 → abierto** (202 meses maduros hoy, 2 recesiones, 21 cambios de régimen). Toda la investigación usa solo datos hasta 2004-12[^val10][^plan].

### 3.10 Los últimos 24 meses

![[Reports/Fase 3/img/06_ultimos_24_meses.png]]

*Cómo leerlo:* cada barra es un mes con sus cuatro probabilidades apiladas (todas provisionales; "F" = mes frontera). Debajo está lo que decía el clasificador de reglas ese mes. Durante el último año la etiqueta se ha asentado en el cuadrante de estanflación, pero con mucho ámbar (crecimiento con inflación alta): el crecimiento está en la raya. El clasificador de reglas ha ido saltando entre estanflación, deflación/recesión y reflación. De mayo a octubre de 2026 no hay etiqueta todavía.

---

## 4. Validación independiente

El **Validador independiente** funciona como la validación de modelos de un banco: no construye ni arregla; **reproduce, ataca e informa**[^ag].

### 4.1 Etiqueta v1.0 (14-oct): ⚠️ aprobada con condiciones

**Lo bueno**[^val10]:
- La etiqueta **se reproduce bit a bit** y el código hace lo que dice la ficha.
- **No hay indicios de ajuste ad hoc**: el umbral, la frontera y la ventana de tendencia no cambiaron desde el borrador.
- **Es robusta:** con cambios razonables de parámetros cambia de cuadrante entre el 3,7 % y el 12,1 % de los meses, y ningún episodio se da la vuelta. Lo más influyente es el umbral κ, sobre todo en los años 1990-2000, cuando la inflación rondó el 2-2,5 %.

**Lo que pedía** (sin cambiar la definición)[^val10]:

| condición | qué significa | cómo se cerró en la v1.1 |
|---|---|---|
| A1. Entradas congeladas | La reproducción dependía de una base de datos que cambia cada día; y era falso que los datos nuevos solo tocaran los meses provisionales | Instantánea con huella en git, tests y ficha corregida ✅ |
| A2. La tendencia mira 60 meses al futuro | El embargo de 6 meses no basta. En el backtest, las etiquetas de entrenamiento se recalculan con datos ≤ fecha de corte | Regla escrita en la ficha y el PLAN; se aplica en el arnés (pendiente) |
| A3. Persistencia honesta y columnas prohibidas | La persistencia no puede usar la etiqueta de t−1; `usrec` es ex post (el NBER fecha las recesiones con 4-21 meses de retraso) | Persistencia point-in-time (§5) y lista negra en código ✅ |
| M1. Ruido de la inflación | Documentar el suelo de ruido y el sesgo de −0,16 pp | En la ficha §7 ✅ |
| M6. Empalme de 1957-59 | El −0,4 pp no representaba el empalme | +0,20 pp medido ✅ |

### 4.2 Etiqueta v1.1 (15-oct): ⚠️ y después ✅

- **Primera revisión (⚠️):** la serie era correcta y reproducible, y solo cambiaba lo declarado. Pero faltaba actualizar la ficha, no había tests que fijaran la huella ni protegieran los meses maduros, la lista negra dejaba pasar nombres derivados (`usrec_lag1`, `G_lag5`) y el PLAN citaba un listón equivocado (68 % en vez de 63,6 %)[^val11].
- **Re-auditoría de cierre (✅):** tras las correcciones, el Validador reprodujo la etiqueta bit a bit **sin la base de datos**, pasó 35 de 35 tests e intentó romper la protección con mutaciones (cambiar κ, alterar un mes, reescribir la instantánea…). Los tests las detectaron. **Veredicto: ✅ aprobado; se puede poner el tag `label-v1.1`**[^val11].
- **Pendiente para el arnés (no para la etiqueta):** construir las variables desde lista blanca y añadir las capas ex post a la lista negra. Tras la re-auditoría se blindó además la escritura de versiones congeladas (45/45 tests)[^val11][^bit].

> [!tip] Por qué importa
> Un error en la "respuesta correcta" contaminaría todo lo que venga después sin dar ningún aviso (como pasó con la v0.1). Que un auditor independiente la reproduzca e intente romperla es la garantía de que el examen está bien puesto.

---

## 5. El listón que hay que batir: la persistencia point-in-time

### 5.1 La idea
El rival más sencillo es la **persistencia**: "el régimen de este mes es el mismo que el último que conozco". Parece trivial, pero con regímenes que duran meses es muy difícil de batir. El criterio de cierre de la fase dice que el modelo tiene que superarla[^obj].

### 5.2 La trampa del "mes anterior"
La versión ingenua ("lo mismo que el mes anterior") acierta el **89 %**. Pero **hace trampa**: la etiqueta del mes t−1 necesita datos hasta t+3 (por la ventana centrada), y esos datos **no existen** el día en que hay que decidir (final del mes t)[^chk11][^val10].

![[Reports/Fase 3/img/09_liston_persistencia.png]]

*Cómo leerlo:*
- **A la izquierda**, la línea vertical es el día de la decisión y todo lo que queda a su derecha es futuro. La etiqueta de t−1 necesita datos de ese futuro; la de t−5 no. Por eso la más reciente que se puede calcular de verdad es la de **t−5** (`label_lag` = 5).
- **A la derecha**, lo que acierta cada versión de la persistencia en los 797 meses puntuables:
  - **Persistencia point-in-time** (la honesta): la etiqueta de t−5, **recalculada solo con los datos publicados en t** (en su versión provisional). **Acierto 63,6 %, log-loss 1,235.** En el periodo de entrenamiento (hasta 2004, 595 meses): 62,9 % y 1,227.
  - **Etiqueta definitiva de t−5:** 68,0 %. Tiene una fuga más sutil: usa la versión revisada y con la tendencia completa, que el día t no existía.
  - **"Mes anterior":** 89,3 %. Fuga clara.
  - Fuente: `label_v1.1_checks.md` §6b. El Validador la reimplementó por su cuenta y obtuvo 63,5 %[^chk11][^val11].

### 5.3 Qué significa
- **El listón oficial es la persistencia point-in-time:** log-loss blanda **1,235** (menor es mejor) y 63,6 % de acierto. El PLAN y la ficha ya lo recogen así[^spec].
- Un modelo que "solo" acierte el 70 % puede ser bueno; uno que diga el 90 % casi seguro tiene una fuga.
- **Limitación declarada:** esta persistencia trunca los datos en el tiempo, pero usa la última versión revisada, no los datos tal como se publicaron. El arnés tiene que tratar el baseline y las variables del modelo igual, para que la comparación sea justa[^spec][^val11].

---

## 6. Revisión económica del Estratega macro (15-oct)

El usuario pidió que un experto en finanzas revisara si la etiqueta tiene sentido económico y para invertir. **Veredicto: ⚠️ "sirve con cambios"**[^macro]:
- **Como objetivo del nowcast, sirve y no hay que tocarla.** Además, cambiarla después de haber visto rendimientos de activos sería minería de datos.
- **Como "régimen de inversión", no basta por sí sola.** Hacen falta capas adicionales (§7).

### 6.1 Hallazgos principales

| # | hallazgo | en lenguaje llano |
|---|---|---|
| A1 | **El eje de inflación marca épocas, no regímenes de activos** | Como compara un **nivel** con un umbral fijo, I cruza el 2,5 % solo 27 veces en 802 meses (G lo cruza 58 veces). Los 70-80 son casi enteros de "inflación alta" y 2010-2019 entero de "baja". Lo que mueve a los activos es más bien la **dirección** de la inflación (si acelera o frena) |
| A2 | **"Late cycle" estaba mal nombrado** | Las salidas de recesión con inflación alta pero bajando (1975-07 → 1976-05, 1983-01 → 1985-01) caían ahí con probabilidad ≈ 0,9. Llamarlas "sobrecalentamiento" invierte el posicionamiento. Ahora es **"Crecimiento con inflación alta"** |
| A3 | **La recesión pesa tanto como el cuadrante** | La diferencia de rendimientos entre meses con y sin recesión es del mismo tamaño que entre cuadrantes. "Estanflación" y "Crecimiento bajo" mezclan recesiones con pausas sin recesión |
| M1 | El borde actual de G está sesgado | El empleo crece poco en parte por menos inmigración (oferta, no demanda), y la producción industrial pesa un 25 % en G aunque la manufactura sea ~10 % del PIB. La "estanflación" de 2024-07 → 2024-11 (provisional, 5 de 5 meses frontera) es dudosa con el PIB creciendo al 3 % |
| M2 | La inflación subyacente ignora los shocks energéticos | Correcto para el eje, pero la inflación general y la subyacente caen a distinto lado del umbral en el 11,1 % de los meses de 1959-2004, justo en episodios importantes (1986, 1999-2000) |
| M3 | Salidas de recesión desinflacionarias como "Estanflación" | 1982-H2 y 1991-04 → 1992-02 salen como estanflación con mucha confianza, y fueron de los mejores momentos para comprar bonos y bolsa |

### 6.2 ¿Distinguen los cuadrantes los rendimientos? (1955-2004)

> [!danger] Esto es una descripción a posteriori y NO es operable
> La etiqueta usa datos hasta t+4 y la tendencia hasta t+60: en tiempo real nadie sabía en qué cuadrante estaba. Solo se usan datos de 1955-01 a 2004-12; **no se ha mirado nada del periodo bloqueado (2005 →)**. Hay unos 20 tramos por cuadrante, así que la incertidumbre es grande. Esta mirada queda anotada en el registro de pruebas (§7.3).

![[Reports/Fase 3/img/10_rendimientos_por_cuadrante_1955_2004.png]]

*Cómo leerlo:* a la izquierda, el rendimiento real medio anual (descontada la inflación) de cada activo en cada cuadrante; azul = gana, rojo = pierde. A la derecha, la bolsa partida en dos épocas.

| activo (real, % anual) | Expansión (149 m) | Crec. con infl. alta (167 m) | Estanflación (186 m) | Crec. bajo / desinfl. (98 m) |
|---|---|---|---|---|
| Bolsa EE. UU. | **+15,4** | +6,3 | +4,1 | +4,8 |
| Bono a 10 años | −0,0 | +1,3 | +3,0 | **+8,3** |
| Materias primas | +2,2 | **+10,4** | +3,7 | +9,4 |
| Oro | −3,1 | +1,7 | **+7,0** | +2,8 |
| Cartera 60/40 | **+9,3** | +4,3 | +3,6 | +6,2 |

Fuente: Estratega macro, §3.1[^macro].

**Lectura:**
- **A primera vista discrimina como se espera:** bolsa en Expansión, bonos en Crecimiento bajo, oro en Estanflación y materias primas en Crecimiento con inflación alta.
- **Pero no es estable entre épocas.** La bolsa en "Estanflación" pasa de −2,1 % (1955-79) a +10,5 % (1980-2004), y en "Crecimiento bajo" de +11,9 % a −1,0 %. En 1980-2004, muchos meses de "Estanflación" son en realidad desinflaciones (1981-82, 1985-86, 1989-92) con la subyacente aún por encima del 2,5 %[^macro].
- **Solo dos relaciones mantienen el signo en las dos épocas:** **Expansión → bolsa** y **Crecimiento bajo → bonos**. Lo del oro y las materias primas en Estanflación es básicamente un resultado de los años 70 (2-3 episodios).
- **La recesión explica tanto como el cuadrante:** bolsa +1,2 % real en meses de recesión frente a +8,7 % en el resto; bonos +9,9 % frente a +1,5 %[^macro].
- **La alternativa por dirección de la inflación separa mejor.** Con crecimiento bajo **e inflación acelerando**, la bolsa pierde (−1,5 %) y el oro gana (+16,9 %). Es una sola partición alternativa elegida por teoría, pero también ex post, así que se lleva como **hipótesis preregistrada** (§7.1) y no como cambio de la etiqueta[^macro].

### 6.3 Tramos discutibles
Los errores económicos se concentran en dos sitios[^macro]:
- **Las salidas de recesión con inflación alta pero bajando** (1975-76, 1982-85, 1991-92).
- **La inflación general frente a la subyacente** (1986, 1999-2000).

No son meses frontera: la etiqueta está muy segura (probabilidad máxima ≈ 0,90 en 1983-85), así que la versión probabilística no los rescata. También hay artefactos de un mes: 2001-12 sale estanflación por un salto puntual de la subyacente, y en 1971-72 los controles de precios de Nixon reprimen la inflación medida.

### 6.4 La lectura del régimen actual
- **Lo sólido:** la inflación está por encima del objetivo y no baja (PCE subyacente ~3,0-3,2 % interanual en 2026). Desde marzo de 2026 la empeora un shock energético (WTI entre 91 y 102 $ de marzo a mayo), que la etiqueta todavía no recoge[^macro].
- **Lo débil:** el "crecimiento bajo" es en parte de oferta. El PIB crece al 2,2-2,5 %, el paro está en el 4,1-4,2 %, la regla de Sahm ronda 0 y los diferenciales de crédito están en mínimos. G < 0 sale sobre todo de comparar el empleo con una tendencia inflada por la inmigración y de una producción industrial floja[^macro].
- **Lectura recomendada:** "**inflación persistente con crecimiento en torno a tendencia, sesgo estanflacionario**", siempre con las probabilidades, **provisional y en frontera**. Para activos, el riesgo relevante es la **duración** (tipos largos y prima por plazo), no un desplome de beneficios[^macro].

> [!caution] Que el Estratega coincida con la etiqueta no es una validación
> La lectura actual es provisional: los 54 últimos meses aún cambiarán. Además, los datos de 2026 que cita el Estratega son descriptivos y no se han usado para buscar relaciones.

---

## 7. Decisiones del usuario del 15-oct

### 7.1 Capas ex post preregistradas
La etiqueta v1.1 **no se toca**. Lo que falta para invertir se añade como **capas aparte**, igual que la de recesión. Son **ex post** (también miran al futuro) y, por tanto, **están prohibidas como variables** de los modelos: entrarán en la lista negra cuando existan. Se definieron por teoría **antes** de evaluarlas y no se exploran variantes[^hyp][^bit]:

| id | capa | qué mide | definición fijada |
|---|---|---|---|
| L-CAP-001 | **Dirección de la inflación** (`infl_dir`) | Si la inflación acelera o frena | I<sub>t</sub> − I<sub>t−6</sub>, con banda de incertidumbre s_I·√2. Contraste principal preregistrado: "crecimiento bajo con inflación acelerando" frente al resto. **Ojo:** ya se miró una vez en 1955-2004 (§6.2) y cuenta como prueba |
| L-CAP-002 | **Shock energético** (`energy_shock`) | Lo que la subyacente deja fuera | PCE general − subyacente > ±1 pp, o crudo interanual > ±40 % (PPI del crudo hasta 1985 y WTI después); si se contradicen, manda la brecha PCE |
| L-CAP-003 | **Holgura** (`slack`) | Distinguir recuperación de sobrecalentamiento dentro de "Crecimiento con inflación alta" | Paro − NAIRU de la CBO: > +0,5 pp = holgura (recuperación), < −0,5 pp = tensión (sobrecalentamiento) |

Criterio de éxito para la Etapa 2 (activos): **el mismo signo del contraste en 1955-79 y en 1980-2004**; el periodo bloqueado se evalúa una sola vez[^hyp].

### 7.2 Lo que se pospone
- **Etiqueta v2.0** con un eje de inflación **frente a lo esperado** (inflación realizada menos expectativas: Livingston, SPF, Michigan). Solo si la Etapa 2 lo justifica con datos hasta 2004[^macro][^bit].
- **Capa EUR** para el inversor español: etiqueta propia de la zona euro y el EUR/USD como canal. Va a su fase[^bit].
- **Fiscalidad española:** implementar las rotaciones con fondos traspasables (el traspaso no tributa) y no con ETF, e incluir el coste fiscal en la cartera. Va a su fase[^bit].

### 7.3 Registro de pruebas
Se crea `research/trial_log.md`. **Toda mirada a resultados** (rendimientos de activos, acierto de un modelo o de una regla) se anota ahí, **aunque no se use**. Sirve para dos cosas:
- **Corregir por comparaciones múltiples:** si se prueban 20 ideas, alguna "funcionará" por azar.
- **Saber qué está contaminado.**

Primera entrada: la revisión del Estratega (1955-2004, 2 particiones probadas)[^trial].

---

## 8. Qué viene después

En orden, según `docs/PLAN.md` y el estado del proyecto[^obj][^plan]:

1. **▶ Base point-in-time (en marcha desde el 15-oct).** El Constructor prepara:
   - un **calendario de publicación** con los retrasos medidos con ALFRED (`docs/models/pit_calendar.md`);
   - una **lista blanca** de variables con mecanismo económico y regla de admisión;
   - el constructor de la matriz PIT (`src/features/`, con datos tal como se publicaron o con la última versión truncada);
   - los **tests de fugas** (publicación posterior a la decisión, truncamiento, placebo, señal plantada, lista negra).
   La exploración usa solo datos hasta 2004. Al terminar: Validador → Estratega macro → correcciones → re-auditoría[^bit].
2. **Arnés walk-forward.** Entrena con el pasado y prueba en el futuro inmediato, mes a mes. Lleva 6 meses de embargo y **recalcula las etiquetas de entrenamiento solo con datos ≤ corte** (condición A2). No toca 2005-01 → hasta la evaluación final, que se hace una sola vez. Apunta todas las pruebas en el registro.
3. **Modelos sencillos:** persistencia point-in-time (el listón, 63,6 %), clasificador de reglas, regresión logística con 5-10 variables con sentido económico y un modelo de Markov.
4. **GBM**, solo si bate a los sencillos fuera de muestra.
5. **Calibración:** que cuando el modelo diga "70 %", acierte de verdad alrededor del 70 % de las veces.
6. **Investigación de relaciones adelantadas** (en paralelo), con hipótesis preregistradas. Las dos de derivados (H-DER-001, la pendiente de la curva de futuros del VIX; H-DER-002, la volatilidad implícita de los bonos) nacen en 2004-2006 y solo se evaluarán dentro de la evaluación única[^hyp].

### Cómo se va a garantizar que funciona
- **El Validador independiente** revisa cada hito; sin su ✅, la fase no se cierra[^ag].
- **Pruebas placebo y señal plantada:** con la etiqueta barajada o variables aleatorias el modelo no debe acertar; en datos inventados con una relación conocida, tiene que encontrarla.
- **Contar episodios, no meses:** resultados por episodio y con intervalos (bootstrap por bloques).
- **Sensibilidad pedida por el Validador:**
  - resultados con la incertidumbre de la etiqueta ×0,5 y ×2;
  - con 60 meses provisionales;
  - sin los meses de inflación cerca del umbral;
  - por episodio, con y sin meses de choque[^val10].

---

## 9. Limitaciones

- **Todavía no hay modelo.** No hay ninguna evidencia aún de que se pueda adivinar el régimen mejor que la persistencia point-in-time.
- **La etiqueta es una definición, no una verdad revelada.** Otras elecciones razonables cambiarían entre el 3,7 % y el 12,1 % de los meses. El umbral κ es lo que más pesa, sobre todo en los 90 y 2000[^val10].
- **La ventana centrada adelanta los choques.** La mitad del peso de G está en t+1…t+4: enero y febrero de 2020 salen "crecimiento bajo" antes de la COVID. El nowcast es en parte una previsión a 1-4 meses[^val10].
- **Suelo de ruido de la inflación:** ~6 % de meses y Δp ≈ 0,07 que no desaparecen con el tiempo, por las revisiones de las cuentas nacionales[^spec].
- **El eje de inflación marca épocas** (§6.1). El riesgo es que un modelo aprenda "en qué década estamos" en lugar del régimen. Por eso las variables de nivel deben estandarizarse con ventanas móviles[^macro].
- **Como régimen de inversión, la etiqueta no basta:** solo "Expansión → bolsa" y "Crecimiento bajo → bonos" son estables entre épocas, y todo eso es ex post (§6.2).
- **Supuesto de independencia entre crecimiento e inflación:** correlación −0,13 en toda la muestra, pero 0,27 desde 1984, cerca del umbral de revisión de 0,3[^chk].
- **La muestra que puntúa termina en octubre de 2021**; el periodo bloqueado (2005 →) tiene 202 meses maduros y casi nada de estanflación ni de crecimiento con inflación alta maduros. El eje de inflación solo se pondrá a prueba de verdad con 2021-2023, hoy provisional[^val10].
- **Pocos episodios:** unas 11 recesiones y 86 tramos de régimen en 1955-2021. Cualquier resultado tendrá intervalos amplios.
- **La persistencia point-in-time usa la última versión de los datos**, no los datos tal como se publicaron (§5.3).
- **La comparación con el clasificador de reglas (52 %) es orientativa** y no es limpia: sus reglas se diseñaron conociendo 2008 y 2020.
- **Datos:** huecos de pago, fuentes congeladas, licencias no comerciales y series que se reescriben hacia atrás.
- **Solo EE. UU.**: la zona euro y la capa EUR quedan fuera de esta fase.

---

## 10. Glosario

| término | qué significa aquí |
|---|---|
| **Régimen** | El "clima económico" de un mes: uno de los 4 cuadrantes de crecimiento × inflación |
| **Crecimiento con inflación alta** | Cuadrante G↑ I↑ (id interno `late_cycle`). Puede ser una recuperación temprana o un sobrecalentamiento; la capa de holgura los distingue |
| **Nowcast** | "Pronóstico del presente": estimar el régimen del mes en curso, del que aún no hay casi datos oficiales. No es predecir el futuro (eso sería un *forecast*) |
| **Point-in-time (PIT)** | Usar en cada fecha solo la información que estaba publicada ese día, sin revisiones ni datos posteriores |
| **Vintage** | Cada versión publicada de una serie. El PIB de 2008 publicado en 2009 es una vintage distinta del que vemos hoy. ALFRED las archiva |
| **Fuga (leakage)** | Que entre en el modelo, sin querer, información que no existía el día de la decisión. Infla los resultados y es el error más peligroso |
| **Persistencia point-in-time** | El listón: predecir que el régimen es el de la última etiqueta calculable (t−5) con los datos publicados ese día. Acierta el 63,6 % |
| **Walk-forward** | Backtest que avanza en el tiempo: entrena con el pasado, prueba en el mes siguiente y repite |
| **Embargo** | Hueco de meses entre entrenamiento y prueba, para que la etiqueta (que mira hasta t+4) no "chive" la respuesta. Aquí son 6 meses |
| **Log-loss** | Nota de un pronóstico probabilístico: castiga mucho decir "95 % seguro" y fallar. Cuanto más baja, mejor |
| **Calibración** | Que las probabilidades signifiquen lo que dicen: de todas las veces que se dice "70 %", debe ocurrir alrededor del 70 % |
| **Placebo** | Prueba con datos sin sentido (la etiqueta barajada o variables aleatorias). Si el modelo "acierta" con ellos, hay un fallo |
| **Señal plantada** | Prueba con datos inventados con una relación conocida: el método tiene que encontrarla, y no inventarse ninguna si no la hay |
| **Etiqueta provisional** | Mes reciente cuya etiqueta aún cambiará (los últimos 54). No entrena ni puntúa |
| **Mes frontera** | Mes en que el cuadrante más probable no llega al 55 % |
| **Periodo bloqueado** | 2005-01 → abierto: se reserva y solo se usa una vez, al final, como examen definitivo |
| **Empalme** | Unir dos series que miden lo mismo de forma distinta (aquí, IPC subyacente antes de 1959 y PCE subyacente después) con un ajuste para que no haya un salto artificial |
| **Instantánea (snapshot) y hash** | Copia congelada de los datos de entrada, con una "huella digital" (SHA-256) que cambia si se altera un solo número |
| **Lista negra / lista blanca** | Negra: columnas que nunca pueden ser variables (la etiqueta, la recesión, previsiones). Blanca: las únicas variables admitidas, con fecha de publicación conocida |
| **Capa ex post** | Información añadida a la etiqueta que también mira al futuro (recesión, dirección de la inflación, shock energético, holgura). Sirve para describir e invertir, nunca como variable |
| **Dirección de la inflación** | Si la inflación acelera o frena (I<sub>t</sub> − I<sub>t−6</sub>), frente a su nivel |
| **Holgura (NAIRU)** | Distancia del paro a su nivel "de equilibrio" estimado por la CBO. Paro por encima = holgura (recuperación); por debajo = tensión (sobrecalentamiento) |
| **Preregistro** | Escribir la hipótesis, la definición y el criterio de éxito **antes** de mirar los datos |
| **Registro de pruebas** | Lista de todo lo que se ha mirado, funcione o no, para corregir por comparaciones múltiples |
| **Minería de datos (snooping)** | Probar muchas variantes hasta que una "funcione" por azar. Lo que se intenta evitar con el preregistro y el registro de pruebas |

---

### Reproducir los gráficos
`.venv/bin/python -m src.report.fase3.make_figures` lee la etiqueta v1.1 (y la v1.0, v0.2 y v0.1 para las comparaciones), el estudio de revisión, el warehouse (solo lectura), la tabla §6b de `label_v1.1_checks.md` y las tablas §3.1 de la revisión del Estratega. Escribe los 10 PNG y `img/cifras.json`.

[^obj]: `obsidian/Proyecto/Estado del proyecto.md`, secciones "🎯 Objetivo de la Fase 3" y "▶ Retomar aquí (15-oct)".
[^ult]: `data/archive/labels/regime_us_v1.1.parquet`, fila 2026-04 (también en `docs/models/label_v1.1_checks.md` §7).
[^ult24]: `data/archive/labels/regime_us_v1.1.parquet`, últimos 24 meses (2024-05 → 2026-04); detalle en `img/cifras.json` → `ultimos24`.
[^reglas]: Tabla `regime_monthly` de `data/warehouse.duckdb` (columna `quadrant`, consultada el 15-oct); `img/cifras.json` → `ultimos24.reglas_ultimos`.
[^comp]: Cálculo del Reportero en `src/report/fase3/make_figures.py` (`comp_reglas`), guardado en `img/cifras.json` → `reglas_vs_etiqueta` (51,6 %; 52,6 % sin frontera). Meses con weight = 1 y no provisionales, 1955-01 → 2021-10. Correspondencia: Goldilocks = expansión, Reflación = crecimiento con inflación alta, Estanflación = estanflación, Deflación/recesión = crecimiento bajo.
[^cob]: Tablas `catalog` y `series_summary` de `data/warehouse.duckdb` (15-oct-2026); `img/cifras.json` → `cobertura`.
[^estado]: `obsidian/Proyecto/Estado del proyecto.md` (15.610 series y 12,53 M de filas; automatización; arreglo de INE).
[^aud]: `docs/data/audit_2026-10-14.md`.
[^fut]: `docs/data/futures_derivatives_2026-10-14.md`, §1.2, §2 y §3.
[^spec]: `docs/models/label_spec.md` (ficha v1.1, congelada): §4 empalme, §7 provisionales y ruido de inflación, §10 congelación, §12 uso en modelos, §13 registro de cambios.
[^chk]: `docs/models/label_v1.1_checks.md` §2-§5 (muestra puntuable de 802 meses).
[^chk11]: `docs/models/label_v1.1_checks.md` §6 (comparación v1.0 → v1.1) y §6b (persistencia point-in-time); `img/cifras.json` → `empalme` y `liston`.
[^cifras]: `img/cifras.json` (`recesion`, `desfase`), calculado por `make_figures.py` a partir de las etiquetas v0.1, v0.2 y v1.1 y de `CFNAIMA3` del warehouse.
[^v01]: `docs/models/label_v0.1_checks.md`, §2 y §8.
[^v02]: `docs/models/label_v0.2_checks.md`, §2 y §9; `obsidian/Proyecto/Etiqueta de régimen.md`.
[^rev]: `docs/models/label_revision_study.md` y `data/archive/labels/revision_study.json`.
[^val10]: `docs/validation/2026-10-14_label_v1.0.md` (Validador independiente, ⚠️ aprobado con condiciones): hallazgos A1-A3, M1-M6, sensibilidad y periodo bloqueado.
[^val11]: `docs/validation/2026-10-15_label_v1.1.md` (⚠️ en la primera revisión; ✅ en la "Re-auditoría de cierre", commit `ebccae1`).
[^macro]: `docs/reviews/2026-10-15_estratega_macro_etiqueta.md` (Estratega macro, ⚠️ "sirve con cambios"): §1-§6. Los rendimientos son de 1955-01 → 2004-12, ex post.
[^hyp]: `research/hypotheses.yaml` (L-CAP-001/002/003; H-DER-001/002).
[^trial]: `research/trial_log.md`.
[^bit]: `obsidian/Proyecto/Bitácora.md`, entradas del 2026-10-15 (decisiones del usuario, tag `label-v1.1`, blindaje `6aaf3f7`, lanzamiento de la base PIT).
[^plan]: `docs/PLAN.md`, secciones "Fase 3 — arquitectura de modelos" y "Periodo bloqueado y reglas del arnés".
[^ag]: `obsidian/Proyecto/Agentes.md`, §5.
