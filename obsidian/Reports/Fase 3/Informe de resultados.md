---
tipo: informe_resultados
fase: 3
version: 0.1 (primera versión)
actualizado: 2026-10-14
autor: Reportero
graficos: src/report/fase3/make_figures.py
cifras_derivadas: "obsidian/Reports/Fase 3/img/cifras.json"
---

# Fase 3 · Informe de resultados

> [!info] Cómo leer este informe
> Está pensado para leerse sin saber econometría. Cada cifra importante lleva su fuente: un fichero del proyecto o el warehouse. Las cifras que he calculado yo para este informe (por ejemplo, la comparación con el clasificador de reglas) salen del script `src/report/fase3/make_figures.py` y quedan guardadas en `img/cifras.json`. Las palabras técnicas están en el [[#6. Glosario|glosario]] del final.
> Ver también [[Proyecto/Estado del proyecto]], [[Proyecto/Etiqueta de régimen]] y [[Proyecto/Agentes]].

---

## 1. Resumen en una página

### Qué queremos conseguir
Queremos que el sistema diga **cada mes en qué "clima económico" (régimen) está EE. UU. y con qué probabilidad**, usando solo la información que existía ese día. Además, tiene que quedar **demostrado en un backtest honesto que lo hace mejor que las alternativas sencillas**; la más importante es "el mes que viene, lo mismo que este"[^obj].

### Dónde estamos

**Entregables** (en orden)[^obj]:

| # | entregable | estado |
|---|---|---|
| 1 | Etiqueta de régimen v1.0 (la "respuesta correcta") | ✅ congelada el 14-oct (tag `label-v1.0`) |
| 2 | Base point-in-time + calendario de publicación + test de fugas | ⏳ pendiente |
| 3 | Arnés walk-forward (embargo de 6 m, 2016-2026 bloqueado, registro de pruebas) | ⏳ pendiente |
| 4 | Modelos sencillos: persistencia, reglas, logística, Markov | ⏳ pendiente |
| 5 | GBM, solo si bate a los anteriores | ⏳ pendiente |
| 6 | Calibración | ⏳ pendiente |
| — | En paralelo: investigación de relaciones adelantadas | 🟡 programa escrito (`docs/models/research_program.md`), sin resultados todavía |

**Criterios de cierre de la fase**[^obj]:

| criterio | estado |
|---|---|
| Bate a la persistencia en log-loss fuera de muestra, también en el periodo bloqueado, con intervalos que no incluyen el cero | ⬜ sin modelos aún |
| Probabilidades calibradas | ⬜ |
| Sin fugas: test point-in-time, placebo y señal plantada superados | ⬜ |
| Relaciones con mecanismo, estables por épocas y países, que sobreviven a la corrección por comparaciones múltiples | ⬜ |
| Veredicto ✅ del Validador independiente | ⬜ (la etiqueta v1.0 está en revisión; ver §3.8) |
| Ficha del modelo + informe de resultados | 🟡 este informe es la primera versión; la ficha del modelo no existe todavía |
| Sustituye al clasificador de reglas en el reporte semanal | ⬜ |

**En una frase:** hemos terminado el primer paso, que consiste en definir con cuidado qué estamos intentando adivinar. Todavía no hay ningún modelo que adivine nada.

### Régimen actual según la etiqueta (provisional)

- **Último mes con etiqueta: abril de 2026 → Estanflación, con un 60 % de probabilidad.** El resto se reparte así: late cycle 31 %, crecimiento bajo/desinflación 6 % y expansión 3 %. El crecimiento está algo por debajo de su tendencia (G = −0,17) y la inflación subyacente va al 2,9 % anualizado[^ult].
- En los últimos 24 meses con etiqueta, **19 caen en estanflación**. Desde noviembre de 2025 lo están todos, aunque febrero y marzo de 2026 son meses "frontera": ninguna opción llega al 55 %[^ult24].
- ⚠️ **Es provisional y no debe leerse como un dato firme.** Los últimos 54 meses (2021-11 → 2026-04) cambiarán a medida que lleguen datos y se revisen (ver §3.6). Además, la etiqueta **termina en abril de 2026**: para fijar el mes t hacen falta datos hasta t+4, así que de mayo a octubre de 2026 aún no hay etiqueta.

### Diferencia con el clasificador de reglas actual

El reporte semanal sigue usando el **clasificador de reglas de la Fase 1** (`src/regime`). Su lectura actual es **"Deflación/recesión" en septiembre y octubre de 2026**, y "Estanflación" de mayo a agosto[^reglas].

| | clasificador de reglas (Fase 1) | etiqueta v1.0 |
|---|---|---|
| Para qué sirve | Decir el régimen **hoy**, solo con el pasado | Decir **a posteriori** qué régimen hubo, con datos definitivos |
| Mira hacia delante | No | Sí (hasta t+4 meses). Por eso no puede usarse como predictor |
| Coincidencia con la etiqueta, 1955-2021 (802 meses) | **51 %** de los meses | — |
| Coincidencia en los últimos 24 meses con etiqueta | 9 de 24 | — |

La coincidencia del 51 % es un cálculo mío y solo **orientativo**[^comp]. Los dos sistemas no usan las mismas definiciones (los nombres de los cuadrantes solo se corresponden de forma aproximada), y esto no es el backtest point-in-time oficial. Aun así, enseña algo importante: **adivinar el régimen en tiempo real es difícil**, y el clasificador actual solo coincide con la "respuesta correcta" en la mitad de los meses. Es justo el listón que tienen que superar los modelos de la Fase 3.

---

## 2. Los datos

### Qué tenemos

- **15.610 series** de **55 fuentes** en la base de datos (`data/warehouse.duckdb`, tabla `catalog`, 14-oct)[^cob], con unos 12,5 millones de observaciones[^estado]. Además hay vintages ALFRED (las versiones "tal como se publicaron") de 18 series clave, con 185.606 filas (tabla `vintages`).
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
- **Actualización automática:** desde el 13-oct, launchd actualiza los datos de lunes a sábado a las 7:30 (fuentes diarias + base de datos + régimen) y los domingos a las 7:00 (todo + auditoría + reporte). Hay una tarea de arranque que recupera la actualización si el Mac estaba apagado[^estado].

![[Reports/Fase 3/img/01_cobertura_por_bloque.png]]

*Cómo leerlo:* cada franja de color es un bloque, y la altura total es el número de series con algún dato ese año. La caída de los últimos años no quiere decir que se pierdan datos. Una serie solo cuenta en 2026 si ya tiene un dato de 2026 (hoy son 7.646), y muchas son anuales, se publican con retraso o están cerradas (por ejemplo, el ECU o el Eurodollar). La caída puntual de 1941-45 **no la he investigado**; probablemente se debe a series que se interrumpen durante la guerra.

### Cómo se auditaron
Hay un agente **Auditor de datos** que no modifica nada: solo comprueba. Revisa el contrato de datos, los huecos, los valores raros, la coherencia entre fuentes, el point-in-time y las licencias. Su última auditoría completa (14-oct) dio[^aud]:
- **0 problemas críticos y 33 altos.** 32 de los altos ya estaban explicados (precios oficiales fijos del oro, valores centinela falsos…) y el otro era un falso positivo.
- Un **error real**: la EPA del INE de 1976-2001 por sexo leía columnas equivocadas. Se corrigió el mismo día[^estado]. No afectaba a ninguna serie de EE. UU. ni al régimen.
- Valores de control comprobados a mano (por ejemplo, el excess bond premium de octubre de 2008 = 3,41 ✓, y el mercado de Ken French en octubre de 2008 = −17,2 % ✓).

### Limitaciones que quedan
- **Huecos de pago o sin API:** PMI, Euribor diario, MOVE, Global Financial Data y las curvas de futuros por vencimiento (cobre, oro, cereales; CME/LME)[^aud][^fut]. Para los futuros falta decidir si se paga Databento (pago por uso) o Norgate (~USD 300-600/año)[^fut].
- **Fuentes que ya no se actualizan:** los futuros de WTI y gas de la EIA dejaron de publicarse el 2024-04-05. Sirven para investigar, pero no para el modelo de producción (regla de admisión de variables, `docs/PLAN.md`).
- **Licencias:** AQR y Cboe solo permiten uso personal y prohíben redistribuir; JKP es CC BY-NC (no comercial); JST, solo uso no comercial; Fed Atlanta (`atl_mpt`), uso personal o educativo[^aud][^fut]. **Esto importa si algún día el informe se comparte fuera.**
- **Point-in-time incompleto:** varias series se reescriben hacia atrás (AQR, JKP, Z.1, SOFR), y `GDPPOT` es una proyección de la CBO. Hay que tratarlas con cuidado antes de usarlas como predictores[^aud].

---

## 3. La etiqueta de régimen (v1.0)

### 3.1 Qué es y por qué hace falta
Para saber si un modelo "acierta" el régimen, primero hay que decir **cuál fue el régimen de verdad** en cada mes. Eso es la etiqueta: la **respuesta correcta del examen**. Todo lo que venga después (persistencia, logística, GBM…) se medirá contra ella.

Por eso se define **antes** de modelar y se **congela**, para que nadie la retoque a escondidas y así los modelos "salgan mejor". Cualquier cambio obliga a crear una versión nueva y a repetir todas las comprobaciones[^spec].

La etiqueta **sí puede mirar el futuro**: usa datos revisados y meses posteriores, porque describe el pasado con todo lo que sabemos hoy. Los modelos no pueden hacerlo. Por eso la etiqueta **nunca** puede entrar como variable de un modelo.

### 3.2 Cómo se define, en lenguaje llano
Cada mes se responde a dos preguntas[^spec]:

1. **¿La economía crece por encima o por debajo de lo normal?** (eje **G**). Se usan los cuatro indicadores que mira el comité que fecha las recesiones en EE. UU. (NBER): producción industrial, empleo, renta real sin transferencias y ventas reales. Para cada uno se mide su ritmo de crecimiento en una ventana de unos 6 meses **centrada en el mes**, y se compara con su ritmo "normal" (la mediana de los 10 años de alrededor). Si G > 0, la economía crece por encima de su tendencia.
2. **¿La inflación de fondo está alta?** (eje **I**). Se usa la inflación subyacente PCE (la medida que sigue la Fed), anualizada en una ventana de 6 meses centrada en el mes, y se compara con un **umbral fijo de 2,5 %** (el objetivo del 2 % más un margen).

Las dos respuestas forman **cuatro cuadrantes**:

| | inflación baja (< 2,5 %) | inflación alta (> 2,5 %) |
|---|---|---|
| **crecimiento alto** | 🟢 **Expansión** | 🟡 **Late cycle / sobrecalentamiento** |
| **crecimiento bajo** | 🔵 **Crecimiento bajo / desinflación** | 🔴 **Estanflación** |

"Recesión" **no** es un cuadrante: es una capa aparte (las fechas oficiales del NBER). Un mes de crecimiento bajo no tiene por qué ser una recesión.

### 3.3 Por qué probabilidades y no una etiqueta fija
Los datos se revisan, y un mes que está justo en la raya podría caer a cualquier lado. Por eso, en vez de decir "estanflación sí o no", la etiqueta da **una probabilidad para cada cuadrante**. Cuanto más lejos del umbral, más segura.

La "anchura" de esa incertidumbre (s) **no se ha elegido a ojo**. Sale de cuánto se revisan de verdad los datos entre su primera publicación y hoy (archivo ALFRED): **s_G = 0,40** y **s_I = 0,31 puntos**[^spec][^chk].

> [!example] Ejemplo: abril de 2026
> - **Crecimiento:** G = −0,17, un poco por debajo de lo normal. La distancia al umbral es −0,17 / 0,40 ≈ −0,4 "anchuras", así que P(crecimiento alto) = **34 %**.
> - **Inflación:** I = 2,93 %, por encima de 2,5. La distancia es (2,93 − 2,5) / 0,31 ≈ +1,4 anchuras, así que P(inflación alta) = **92 %**.
> - **Estanflación** = crecimiento bajo × inflación alta = 0,66 × 0,92 ≈ **60 %**. Late cycle = 0,34 × 0,92 ≈ **31 %**.
> - Como la duda está sobre todo en el crecimiento, el mes oscila entre estanflación y late cycle; casi no hay probabilidad de expansión.
>
> Valores del fichero `regime_us_v1.0.parquet` (columnas `G`, `I`, `p_g_high` = 0,339 y `p_i_high` = 0,915).

Los modelos se puntuarán contra estas probabilidades (log-loss). Además existe una **etiqueta dura** (el cuadrante más probable) para leer los resultados. Cuando la opción más probable no llega al 55 %, el mes se marca como **frontera**: pasa en el 8 % de los meses[^chk].

### 3.4 La historia desde 1950

![[Reports/Fase 3/img/02_historia_cuadrantes.png]]

- **Años 70 y Volcker (1979-82):** domina el rojo y el ámbar. El 75 % de los meses de 1973-75 y de 1979-80 salen como estanflación[^chk].
- **1995-99:** expansión (verde) en el 78 % de los meses.
- **2008-09:** crecimiento bajo/desinflación en el 96 %. **2020:** un desplome cortísimo (67 % de los 3 meses del segundo trimestre).
- **2021-22:** sobrecalentamiento. Los meses maduros de 2021 (abril a octubre) son 100 % late cycle; 2022 ya es provisional.
- **Recesiones:** en el **100 % de los 103 meses de recesión NBER** puntuables, la etiqueta dice que el crecimiento estaba por debajo de tendencia. De esos meses, 57 son estanflación (sobre todo en los 70 y principios de los 80) y 46 crecimiento bajo/desinflación[^cifras].

Por décadas se ve que **los regímenes van por épocas**: en los 70 y 80 apenas hay expansión (0-1 %), y en 2000-2019 casi no hay estanflación (0-3 %)[^chk]. Esto importa para los modelos: un modelo entrenado en una época puede no haber visto nunca el régimen de la siguiente.

### 3.5 El mapa crecimiento × inflación

![[Reports/Fase 3/img/03_mapa_G_I.png]]

Cada punto es un mes. El cuadrante solo depende de dos cosas: el lado de la línea vertical (G = 0) y el lado de la horizontal (inflación = 2,5 %). Los puntos cerca de las líneas son los meses dudosos.

Los episodios caen donde deben: 1974-75 y 1979-80 arriba a la izquierda, 2008-09 abajo a la izquierda, 1997-99 abajo a la derecha y 2021 arriba a la derecha. **Los últimos 6 meses (provisionales) están pegados a la línea de crecimiento cero**, y por eso dudan entre estanflación y late cycle.

### 3.6 Cuánto dura cada régimen

![[Reports/Fase 3/img/04_reparto_y_duracion.png]]

- **Reparto equilibrado:** expansión 30 %, late cycle 23 %, estanflación 23 % y crecimiento bajo 24 % de los 802 meses puntuables[^chk].
- **Los regímenes duran poco:** 86 tramos, con una media de 9,3 meses y una mediana de 6. La expansión dura más (media de 12,1 meses, máximo 50) y la estanflación es la más corta en mediana (4 meses)[^chk].
- **De un mes al siguiente, el régimen se repite el 87-92 % de las veces** (matriz de transición)[^chk]. Por eso la **persistencia** ("el mes que viene, lo mismo") es un rival muy duro: acierta casi siempre, salvo justo en los giros, que es lo que de verdad interesa.

### 3.7 Qué salió en las comprobaciones
Antes de congelar la etiqueta se pasó una batería de comprobaciones de **sentido común**. Sirven para detectar errores, **no para ajustar parámetros** hasta que la historia "cuadre"[^spec]. En la v1.0, **las 13 pasan**[^chk]:

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

**Acierto esperado de la etiqueta dura frente a la probabilística:** 82,9 % (85,8 % sin los meses frontera)[^chk]. Dicho de otro modo, incluso la "respuesta correcta" lleva incorporado algo menos de un 20 % de duda.

**Lo que no cuadra del todo (y se ha explicado, no tapado):** en 2022-2024, G y el CFNAI se mueven en sentido contrario (correlación −0,55). El estudio de revisión comprobó que no es un fallo de cálculo ni un efecto del final de la muestra. Fue un tramo casi plano: la manufactura estaba floja (pesa mucho en el CFNAI) mientras el empleo y la renta real crecían por encima de su tendencia. Esos meses ya son provisionales y no puntúan[^chk][^rev].

### 3.8 La historia v0.1 → v0.2 → v1.0 (y por qué se valida)

**v0.1: un desfase de 4 meses que no se veía a simple vista.** La primera versión medía el crecimiento con ventanas **hacia atrás** (de t−7 a t). Parecía razonable, pero una comprobación falló: la correlación con el CFNAI del mismo mes salía 0,62, por debajo del 0,7 exigido (11 de 12 comprobaciones superadas)[^v01].

En vez de bajar el listón, se investigó por qué. La correlación era **máxima con el CFNAI de 2-3 meses antes**. Es decir, la etiqueta del mes t estaba describiendo en realidad el crecimiento de unos 4 meses antes[^v01].

![[Reports/Fase 3/img/07_desfase_v01_v02.png]]

*Cómo leerlo:* a la izquierda, la línea gris (v0.1) tiene su máximo a la izquierda del cero: se parecía más al pasado. La negra (v0.2/v1.0) lo tiene a la derecha, en k = +1/+2. Esto es lo esperado, porque el CFNAI-MA3 de t+1 cubre de t−1 a t+1, centrado en t[^chk][^cifras]. A la derecha, en la crisis de 2008, la v0.1 tocaba fondo en abril de 2009 y la v0.2 en diciembre de 2008: **4 meses de diferencia**[^cifras].

**v0.2: ventanas centradas.** Como la etiqueta describe el pasado, puede usar datos posteriores, así que se centraron las ventanas en t (de t−3 a t+3). Con eso:
- **cambiaron de cuadrante 244 de 856 meses (28,5 %)**, casi todos alrededor de los giros;
- se renombró el cuadrante G↓I↓ (de "desaceleración/recesión" a "crecimiento bajo/desinflación", para no confundirlo con recesión);
- 1950-54 pasó a tener peso 0.

Resultado: 13/13 comprobaciones[^v02]. **Lección:** un error así no da ningún mensaje de error. Solo aparece si se comprueba la etiqueta contra una referencia independiente.

**v1.0: congelada.** Solo cambian las escalas de incertidumbre (s_G de 0,33 a 0,40, estimada con más años de revisiones). No cambia el cuadrante de ningún mes; cambian algo las probabilidades (Δp medio 0,019) y los meses frontera pasan de 72 a 84. Además se fijan los **54 meses provisionales** y un **embargo de 6 meses** para el backtest[^chk][^spec].

### 3.9 El estudio de revisión: qué significan los 54 meses provisionales
**El problema:** para fijar el mes t, la etiqueta necesita datos de hasta 4 meses después, y la tendencia necesita 5 años a cada lado. Por eso **los meses recientes todavía cambiarán** cuando lleguen datos nuevos.

**La pregunta:** ¿cuántos meses hay que esperar para dar un mes por "cerrado"?

**Cómo se respondió:** se viajó al pasado 100 veces (un corte cada 6 meses entre 1975 y 2024)[^rev]. En cada corte se recalculó la etiqueta **solo con los datos que había hasta esa fecha** y se comparó con la etiqueta definitiva. La regla para decidir se fijó **antes** de ver los resultados: el primer k desde el que, de forma sostenida, la etiqueta dura coincide al menos el 95 % de las veces **y** la probabilidad que se mueve (Δp) es como mucho 0,05.

![[Reports/Fase 3/img/05_estudio_revision.png]]

- Con 4 meses de antigüedad, la etiqueta dura coincide el 92,6 % de las veces y Δp = 0,094. Con 24 meses, aún solo el 89,7 %. Con 54-55 meses se superan los dos umbrales[^rev].
- **k* = 55 meses** desde el corte de datos. Restando el desfase de 4 meses y redondeando a múltiplo de 6, salen **54 meses provisionales**[^rev].
- **La mayor parte de la revisión viene de cortar la ventana, no de que se revisen los datos.** Añadir las vintages ALFRED (variante B) solo sube Δp unas milésimas[^rev]. Ojo: la variante B solo revisa INDPRO y PAYEMS, así que es una **cota inferior** de la revisión real.

**Qué significa en la práctica:**
- Hoy, **todo lo posterior a octubre de 2021 es provisional**: no sirve para entrenar ni para puntuar modelos.
- El régimen "actual" de la etiqueta (§1) puede cambiar, y bastante.
- **Consecuencia incómoda:** el periodo bloqueado previsto (2016-2026) solo tiene hoy unos 70 meses puntuables, incluido 2020. El Constructor propone adelantar su inicio o aceptar que madure con el tiempo. **Está pendiente de decisión del usuario**[^chk].

### 3.10 Los últimos 24 meses

![[Reports/Fase 3/img/06_ultimos_24_meses.png]]

*Cómo leerlo:* cada barra es un mes con sus cuatro probabilidades apiladas (todas provisionales; "F" = mes frontera). Debajo está lo que decía el clasificador de reglas ese mes, con la correspondencia aproximada de colores. Durante el último año la etiqueta se ha asentado en **estanflación**, mientras que el clasificador de reglas ha ido saltando entre estanflación, deflación/recesión y reflación. De mayo a octubre de 2026 no hay etiqueta todavía.

### 3.11 Veredicto del validador
**Pendiente.** El Validador independiente está revisando la etiqueta v1.0 (`docs/validation/2026-10-14_label_v1.0.md`), pero el documento todavía no existe. Hasta que emita su veredicto, la etiqueta está **congelada pero no validada de forma independiente**.

---

## 4. Qué viene después

En orden, según `docs/PLAN.md` y el objetivo de la fase[^obj][^plan]:

1. **Base point-in-time + calendario de publicación + test de fugas.** Para cada mes, una "foto" con **solo lo que estaba publicado ese día**: vintages ALFRED, retrasos de publicación y z-scores calculados solo con el pasado. Un test automático comprobará que ninguna variable tiene fecha de publicación posterior a la fecha de decisión.
2. **Arnés walk-forward.** Una máquina de backtest que entrena con el pasado y prueba en el futuro inmediato, avanzando mes a mes. Deja **6 meses de embargo** entre entrenamiento y prueba (porque la etiqueta mira hasta t+4), **no toca 2016-2026** hasta la evaluación final (una sola vez) y apunta **todas** las pruebas, también las fallidas.
3. **Modelos sencillos (el listón):**
   - persistencia ("lo mismo que el mes anterior");
   - el clasificador de reglas actual;
   - una regresión logística con 5-10 variables con sentido económico (curva de tipos, excess bond premium, regla de Sahm, inflación subyacente);
   - un modelo de Markov.
4. **GBM** (árboles potenciados, poco profundos y muy regularizados). **Solo entra si bate a los sencillos fuera de muestra.** Si no, se queda fuera.
5. **Calibración:** que cuando el modelo diga "70 %", acierte de verdad alrededor del 70 % de las veces.
6. **Investigación de relaciones adelantadas** (en paralelo): hipótesis con mecanismo económico escrito y **preregistrado** (crédito, política monetaria, actividad adelantada, inflación, mercados…). Para que una relación cuente, tiene que funcionar también en otros países y épocas (JST, OCDE, zona euro) y sobrevivir a la corrección por comparaciones múltiples[^rp]. Las que se validen entrarán como variables.

### Cómo se va a garantizar que funciona
- **Un Validador independiente**, al estilo de la validación de modelos de un banco: no construye ni arregla; **reproduce, ataca e informa**. Sin su ✅, la fase no se cierra[^ag].
- **Pruebas placebo:** si se baraja la etiqueta en bloques o se meten variables aleatorias, el modelo **no** debe acertar más que el azar. Si lo hace, hay una fuga o un error.
- **Señal plantada:** en datos inventados con una relación conocida, el método tiene que encontrarla; y si no hay relación, no tiene que inventarse ninguna.
- **Contar episodios, no meses:** desde 1950 hay unas 11 recesiones y unas pocas decenas de cambios de régimen. Los resultados se darán por episodio y con intervalos (bootstrap por bloques), no solo como medias.

---

## 5. Limitaciones

- **Todavía no hay modelo.** Este informe solo describe los datos y la "respuesta correcta". No hay ninguna evidencia aún de que se pueda adivinar el régimen mejor que con la persistencia.
- **La etiqueta es una definición, no una verdad revelada.** Otras elecciones razonables (umbral del 2 % o del 3 %, tendencia de 7 años, ventana de 12 meses) darían otra historia en los meses dudosos. Se fijaron antes de modelar para no hacer trampas, no porque sean las únicas posibles[^spec].
- **Supuesto de independencia entre crecimiento e inflación** al combinar probabilidades. La correlación es baja en toda la muestra (−0,13), pero desde 1984 es 0,27, cerca del umbral de revisión de 0,3[^chk].
- **La muestra que puntúa termina en octubre de 2021.** Todo lo posterior es provisional, y el periodo bloqueado tiene pocos meses maduros.
- **Pocos episodios:** unas 11 recesiones y 86 tramos de régimen en 1955-2021. Cualquier resultado tendrá intervalos amplios.
- **La comparación con el clasificador de reglas (51 %) es orientativa:** las definiciones no son iguales y no es un backtest point-in-time.
- **Datos:** huecos de pago (PMI, curvas de futuros), fuentes congeladas (futuros de la EIA), licencias no comerciales (AQR, JKP, Cboe, JST) y series que se reescriben hacia atrás.
- **Solo EE. UU.** La zona euro queda fuera de esta fase.

---

## 6. Glosario

| término | qué significa aquí |
|---|---|
| **Régimen** | El "clima económico" de un mes: uno de los 4 cuadrantes de crecimiento × inflación |
| **Nowcast** | "Pronóstico del presente": estimar el régimen del mes en curso, del que aún no hay casi datos oficiales. No es predecir el futuro (eso sería un *forecast*) |
| **Point-in-time** | Usar en cada fecha solo la información que estaba publicada ese día, sin revisiones ni datos posteriores |
| **Vintage** | Cada versión publicada de una serie. El PIB de 2008 que se publicó en 2009 es una vintage distinta del que vemos hoy, ya revisado. ALFRED las archiva |
| **Walk-forward** | Backtest que avanza en el tiempo: entrena con el pasado, prueba en el mes siguiente y repite, como si se viviera cada momento |
| **Embargo** | Hueco de meses entre los datos de entrenamiento y los de prueba, para que la etiqueta (que mira hasta t+4) no "chive" la respuesta. Aquí son 6 meses |
| **Log-loss** | Nota de un pronóstico probabilístico: castiga mucho decir "95 % seguro" y fallar. Cuanto más baja, mejor |
| **Calibración** | Que las probabilidades signifiquen lo que dicen: de todas las veces que se dice "70 %", debe ocurrir alrededor del 70 % |
| **Persistencia** | El modelo más tonto y difícil de batir: "el régimen del mes que viene será el mismo que el de este" |
| **Placebo** | Prueba con datos sin sentido (la etiqueta barajada o variables aleatorias). Si el modelo "acierta" con ellos, hay un fallo |
| **Señal plantada** | Prueba con datos inventados con una relación conocida: el método tiene que encontrarla, y no inventarse ninguna si no la hay |
| **Etiqueta provisional** | Mes reciente cuya etiqueta aún cambiará. No entrena ni puntúa |
| **Mes frontera** | Mes en que el cuadrante más probable no llega al 55 % |
| **Periodo bloqueado** | 2016-2026: se reserva y solo se usa una vez, al final, como examen definitivo |

---

### Reproducir los gráficos
`.venv/bin/python -m src.report.fase3.make_figures` lee la etiqueta v1.0 y sus versiones anteriores, el estudio de revisión y el warehouse (solo lectura). Escribe los 7 PNG y `img/cifras.json`.

[^obj]: `obsidian/Proyecto/Estado del proyecto.md`, sección "🎯 Objetivo de la Fase 3" (14-oct).
[^ult]: `data/archive/labels/regime_us_v1.0.parquet`, fila 2026-04 (también en `docs/models/label_v1.0_checks.md` §7).
[^ult24]: `data/archive/labels/regime_us_v1.0.parquet`, últimos 24 meses (2024-05 → 2026-04); detalle mes a mes en `img/cifras.json` → `ultimos24`.
[^reglas]: Tabla `regime_monthly` de `data/warehouse.duckdb` (columna `quadrant`) y `obsidian/Reports/2026-10-14_signal.json`.
[^comp]: Cálculo del Reportero en `src/report/fase3/make_figures.py` (`comp_reglas`), guardado en `img/cifras.json` → `reglas_vs_etiqueta`. Son meses con weight = 1 y no provisionales, 1955-01 → 2021-10. Correspondencia usada: Goldilocks = expansión, Reflación = late cycle, Estanflación = estanflación, Deflación/recesión = crecimiento bajo. Sin meses frontera, la coincidencia es del 52 %.
[^cob]: Tablas `catalog` y `series_summary` de `data/warehouse.duckdb` (14-oct-2026); cálculo en `img/cifras.json` → `cobertura`. 15.121 de las 15.610 series tienen observaciones en `series_summary`; las 489 restantes no están en esa vista: 480 son previsiones (`pit_role = forecast`, 477 del WEO del FMI), 5 son `lookahead` y 4 son de `rtdsm`.
[^estado]: `obsidian/Proyecto/Estado del proyecto.md` (15.610 series y 12,53 M de filas el 14-oct por la tarde; automatización; arreglo de INE).
[^aud]: `docs/data/audit_2026-10-14.md`.
[^fut]: `docs/data/futures_derivatives_2026-10-14.md`, §1.2, §2 y §3.
[^spec]: `docs/models/label_spec.md` (ficha v1.0, congelada).
[^chk]: `docs/models/label_v1.0_checks.md` (muestra puntuable de 802 meses).
[^cifras]: `img/cifras.json` (`recesion`, `desfase`), calculado por `make_figures.py` a partir de las etiquetas v0.1, v0.2 y v1.0 y de `CFNAIMA3` del warehouse, en la muestra 1967-01 → 2021-10.
[^v01]: `docs/models/label_v0.1_checks.md`, §2 y §8.
[^v02]: `docs/models/label_v0.2_checks.md`, §2 y §9; `obsidian/Proyecto/Etiqueta de régimen.md`.
[^rev]: `docs/models/label_revision_study.md` y `data/archive/labels/revision_study.json`.
[^plan]: `docs/PLAN.md`, sección "Fase 3 — arquitectura de modelos".
[^rp]: `docs/models/research_program.md`.
[^ag]: `obsidian/Proyecto/Agentes.md`, §5.
