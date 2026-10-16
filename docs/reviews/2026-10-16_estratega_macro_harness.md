---
documento: revisión económica del arnés walk-forward (Fase 3, entregable 3)
hito: commit b01e7ee; docs/models/harness.md v1.0; config/harness/baselines_v1.yaml; src/models/
fecha: 2026-10-16
revisor: Estratega macro (ciclos, regímenes, asignación de activos)
veredicto: ⚠️ SIRVE CON CAMBIOS
---

# Revisión económica del arnés walk-forward

## Veredicto: ⚠️ sirve con cambios

La parte de proceso está muy bien resuelta y no pido cambiarla:
- caja fuerte con filtro de lectura;
- etiquetas de entrenamiento recalculadas en T;
- embargo y purga;
- lista blanca por nombre;
- registro de pruebas;
- placebo con potencia.

Como instrumento para **medir el valor económico de un nowcast de régimen**, en cambio, tiene un fallo de diseño. Si no
se corrige antes de preregistrar la evaluación única, el criterio de éxito queda casi garantizado y no dice nada:

> **La persistencia PIT sin calibrar es un listón demasiado bajo.** Una mezcla fija del 80 % de persistencia y el 20 %
> de climatología, **sin ninguna variable macro**, pasa de 1,2997 a **0,983 nats** en vintage (−0,317) y de 1,1824 a
> **0,918** en latest_truncated (cálculo C2 abajo). Por tanto, "batir a la persistencia en log-loss con un IC que
> excluya el cero" lo cumpliría cualquier modelo que solo aprenda a **no estar seguro** en los giros. El listón tiene
> que ser una **persistencia calibrada** dentro del walk-forward.

Hay otros cuatro cambios necesarios antes del preregistro P-EVAL-BASE:
1. **Métricas por eje (G, I).** La adenda P-EVAL-MOD ya las exige y el arnés no las calcula.
2. **Cortes de giro frente a estable** y de época.
3. **Episodios** limitados a las rachas de 6 meses o más.
4. **Ventana de evaluación fija a priori** que no dependa de qué modelos entren en la corrida, y ventanas de
   entrenamiento **por eje**, para que el IPC subyacente (principal desde 1978) no recorte el modelo de crecimiento.

**Periodo bloqueado.** No he leído nada con fecha ≥ 2005-01, no he desbloqueado la caja fuerte y no he mirado ninguna
relación entre variables y etiqueta. Los dos cálculos (C1, C2) están al final, para el trial log.

---

## 1. Dónde falla la persistencia: el diagnóstico que debe guiar todo

Descompongo la corrida `20261016-092402_baselines_v1_27cae755` (579 meses, 1956-10 → 2004-12). Llamo **mes de giro**
a un mes cuya etiqueta dura oficial es distinta de la de t − 5, que es la que ve la persistencia (cálculo C1).

| corte (vintage) | meses | log-loss persistencia | acierto | % de la log-loss total |
|---|---|---|---|---|
| giro (etiqueta(t) ≠ etiqueta(t−5)) | 175 (30 %) | **2,72** | 15 % | **63 %** |
| estable | 404 | 0,69 | 81 % | 37 % |
| giro solo en G | 136 | 2,46 | 20 % | 44 % |
| giro solo en I | 27 | 3,42 | 0 % | 12 % |
| giro en los dos ejes | 12 | 4,10 | 0 % | 7 % |
| 1956-79 | 279 | 1,42 | 56 % | — |
| 1980-2004 | 300 | 1,19 | 66 % | — |
| recesión NBER ± 6 m | 179 | 1,42 | 75 % | 34 % |

Log-loss binaria de la persistencia por eje (C2), frente a `p_g_high` y `p_i_high`:
- **eje G: 0,957** (vintage) / 0,869 (latest_truncated);
- **eje I: 0,324** / 0,298.

Lectura económica:
- **El problema es el crecimiento en los giros.** Cuatro de cada cinco meses de giro son de G. El eje I cruza κ pocas
  veces (es un marcador de época, como dije en la revisión de la etiqueta). Donde lo cruza, la persistencia se equivoca
  con total seguridad, pero eso pesa solo el 12 % de la pérdida.
- **El suelo irreducible** (entropía media de la etiqueta blanda) es **0,361 nats**: 0,475 en los giros y 0,310 en los
  meses estables. El margen real que puede cerrar un modelo con variables está entre la persistencia calibrada (~0,98)
  y ese suelo, y casi todo está en los 179 meses de giro: 1,73 con la mezcla frente a 0,48 de suelo.
- **La penalización de usar vintages se concentra en 2000-04**: 1,345 en vintage frente a 0,959 en latest_truncated.
  Es la recesión de 2001, que la primera publicación del empleo no mostraba. El periodo bloqueado incluye 2008, con
  revisiones de la misma familia. **El modo vintage es el que cuenta.** Ahí es donde un modelo con mercados (crédito,
  bolsa) debería ganar a uno que solo use datos de actividad.

---

## 2. Pregunta 1: ¿evalúa lo que importa?

**Lo que está bien:**
- La **log-loss blanda como métrica principal** es correcta para invertir: el error caro es estar **seguro y
  equivocado** en un giro, y la log-loss lo castiga más que el Brier.
- **BSS, décadas, episodios y la sensibilidad de modo** son los cortes adecuados.

**Cambios:**

| # | cambio | por qué |
|---|---|---|
| E1 | **Baseline "persistencia calibrada"** (M0) como listón del criterio principal: por eje, una logística de la probabilidad blanda de la etiqueta recalculada sobre el logit de la persistencia (`pers_g`, `pers_i`), entrenada en el mismo walk-forward. Alternativa equivalente: matriz de transición a 5 meses (estado de t − 5 → etiqueta de t) con suavizado de Dirichlet | La sección 1 y C2: la mitad de la "mejora" sobre la persistencia cruda es solo calibración |
| E2 | **Métricas por eje:** log-loss binaria de P(G alto) frente a `p_g_high` y de P(I alta) frente a `p_i_high` | La adenda P-EVAL-MOD las preregistró y el arnés no las calcula (`metrics.py` no las tiene). Sin E2 no se puede ejecutar P-EVAL-MOD |
| E3 | **Corte giro / estable** (etiqueta(t) ≠ etiqueta(t−5)), además de 0-5 m, 6-11 m y ≥ 12 m desde el último cambio | Es donde está la información (63 % de la pérdida). Un modelo que gane en los giros y pierda poco en los meses estables vale; uno que gane solo en los estables, no |
| E4 | **Épocas 1956-79 frente a 1980-2004**, con la mejora frente a M0 en cada una | La Gran Inflación y la Gran Moderación tienen mecanismos distintos (el petróleo administrado antes de 1973, la Fed antes y después de Volcker). 1980-2004 es la época más parecida al periodo bloqueado |
| E5 | **Por cuadrante oficial** (log-loss y acierto por clase) y **meses de frontera aparte** | Para la cartera no da igual fallar en estanflación que en expansión. La ficha §5 exige informar la frontera y el arnés no lo hace |
| E6 | **Retraso de detección de giros de G** (meses desde el cambio oficial de G hasta que P(G alto) cruza 0,5 de forma sostenida, en rachas ≥ 6 m) y **falsas alarmas** en los meses estables (cruces por año) | Es la traducción directa a la cartera: la persistencia detecta tarde por construcción (5-6 meses) |
| E7 | **Curvas de calibración** (fiabilidad por decil, por eje) | Lo exige `PLAN.md` (Validación) y no está |
| E8 | **Bootstrap con bloques de 24 meses como sensibilidad**, más una **prueba de signo por episodio** (en cuántos giros gana) | La pérdida se concentra en unos 30 giros. La N efectiva se parece más al número de giros que a 579 meses, y bloques de 12 meses pueden dar IC demasiado estrechos |
| E9 | **Ventana de evaluación fija y declarada** en la configuración, por ejemplo una muestra de desarrollo principal 1975-01 → 2004-12 y la completa como referencia | Hoy la muestra es la intersección de todos los modelos de la corrida: añadir un modelo que empieza tarde cambia la muestra de todos. La comparación debe ser estable entre corridas |

La métrica de inversión de verdad es la de la Etapa 2, de extremo a extremo (cartera frente a la cartera estática del
IPS). La log-loss del nowcast es un medio, no el fin. No pido adelantarla, pero el preregistro debe decir que **un
nowcast que gana en log-loss y no mejora la detección de giros (E6) no se promociona** a la Etapa 2.

---

## 3. Pregunta 2: decisiones pendientes

### (a) Los 54 meses provisionales de la etiqueta recalculada: **ponderar por madurez**

- **Excluirlos no.** El modelo aprendería con 5 años de retraso: en 2021 no habría visto nada posterior a 2016, y los
  cambios estructurales (la inflación de 2021, el empleo tras la COVID) llegarían tarde.
- **Incluirlos con el mismo peso tampoco.** Cerca del borde, la tendencia de ±60 m es unilateral, así que la etiqueta
  recalculada se parece más al concepto en tiempo real que al final, y el modelo aprendería a reproducir el ruido del
  borde.
- **Recomendación (fijar a priori, antes de correr ningún modelo con variables):**
  - peso 0,5 para los meses provisionales de la etiqueta recalculada y 1 para el resto (regla simple, sin estimar);
  - incluir con peso 1 y excluir se informan como **sensibilidades**, nunca para elegir después.
  - La persistencia ya usa justo el mes más provisional (t − 5), así que entrenar con ellos es coherente con el listón.
  - El arnés necesita `sample_weight` en `fit` (hoy solo hay incluir/excluir).

### (b) Contenido de P-EVAL-BASE (propuesta)

| elemento | propuesta |
|---|---|
| Hipótesis principal (una) | El modelo principal **M1** (logística/probit por eje, §4) mejora a la **persistencia calibrada M0** en log-loss blanda de 4 cuadrantes, modo **vintage** |
| Modelos en la corrida | M1 (principal), M0, persistencia PIT cruda, climatología y clasificador de reglas calibrado (secundarios). Si para entonces están listos, Markov switching y GBM **en la misma corrida** como secundarios, porque la caja fuerte gasta el `prereg_id` en una sola corrida. Las especificaciones y los hiperparámetros quedan congelados en git antes de desbloquear |
| Muestra | Meses puntuables del periodo bloqueado: 2005-01 → 2021-10 (los provisionales oficiales empiezan en 2021-11), unos 202 meses. Ojo: deja fuera casi todo 2022, el episodio de inflación |
| Inferencia | Bootstrap circular por bloques de 12 m, 5.000 réplicas, semilla 20261015, IC al 95 %. Sensibilidad con bloques de 24 m |
| **Criterio de éxito (todas)** | (1) Mejora media frente a M0 **≥ 0,05 nats** y límite inferior del IC > 0. (2) **Eje G**: mejora > 0. (3) Meses de **giro**: mejora > 0. **Meses estables**: no empeora más de 0,05. (4) Mismo signo de la mejora en 2005-14 y en 2015-2021-10. (5) Signos de los coeficientes iguales a los preregistrados y estables a los dos lados de los saltos de vintage (`sign_stability`) |
| Se informa sin decidir | Frente a la persistencia cruda (BSS, acierto), latest_truncated, por episodio (en el periodo bloqueado solo hay 2 recesiones NBER, 2008-09 y 2020, así que no puede ser criterio), retraso de detección de giros, calibración, por cuadrante, frontera |
| Multiplicidad | Holm sobre las comparaciones secundarias frente a M0. La principal no se corrige porque es una sola |
| Regla de promoción | M1 pasa a la Etapa 2 solo si cumple (1)-(5) **y** reduce el retraso medio de detección de giros de G frente a M0 |

### (c) Episodios

- **NBER ± 6 meses: confirmar.** En ≤ 2004, los episodios de 1980 y 1981-82 quedan contiguos sin solaparse; está bien.
- **Rachas: solo las de ≥ 6 meses.** De las 61 rachas ≤ 2004, **20 duran ≤ 2 meses** y 12 duran 3-5 meses. Las 29
  rachas de ≥ 6 meses cubren 500 de los 579 meses.
  - Contar como episodio un parpadeo de un mes (por ejemplo, `late_cycle 1992-03`) mete ruido y premia a quien acierte
    oscilaciones de frontera, que no tienen valor para la cartera.
  - Las rachas cortas ya pesan en el corte de giros (E3). La regla coincide con el criterio de la ficha §8 (duración
    media ≥ 6 meses).
- **Añadir giros de G** como episodio: ventana de −3 a +6 meses alrededor de cada cambio del eje G en rachas ≥ 6 m. Es
  la base de E6.
- Las tres definiciones son mecánicas y se fijan **ahora**, antes de ver el periodo bloqueado.

### (d) `min_train_months` = 120

Como suelo está bien, pero **los meses no son la unidad que importa**. Propongo:
- **120 meses y, además, ≥ 2 recesiones NBER y ≥ 8 cambios del eje G** en la ventana de entrenamiento. Es la regla 2
  de admisión (contar episodios) aplicada al entrenamiento.
- Con 5-6 parámetros por eje y unos 13 episodios efectivos en 10 años, hay pocos eventos por variable. Hace falta una
  **L2 fuerte fijada a priori**, no ajustada con los datos de desarrollo.

**Problema del eje I.** El IPC subyacente solo es principal desde 1978, y en 1978-88 la inflación está casi siempre por
encima de κ, con muy pocos cruces. Una logística libre con el subyacente en 1988 tendría el coeficiente mal
identificado. Recomiendo un **eje I casi estructural**: P(I alta) = Λ(a + b·(subyacente 6m − 2,9) + c·logit(pers_i)),
con b encogido hacia el valor que implica la propia etiqueta (umbral equivalente en IPC ≈ 2,9 %, ficha §4), no hacia
cero.

**Problema del arnés.** Hoy la ventana de entrenamiento empieza en el inicio más tardío de **todas** las columnas del
modelo. Si M1 usa el subyacente, el eje G perdería 1964-77 (las recesiones de 1969-70 y 1973-75). Hacen falta
**ventanas por eje** (grupos de variables con su propia ventana) o que el modelo reciba las filas con NaN y haga el
`dropna` por eje.

### (e) Clasificador de reglas como baseline: **sí, prioridad baja**

- Reescribirlo como `Model` sobre la v0.3:
  - G: signo de `growth_rt` y su Δ6m, con Sahm ≥ 0,5 forzando G↓;
  - I: la histéresis 2,0/2,5 % con aceleración sobre `core_cpi_6m_ann` desde 1978 y `headline_cpi_6m_ann` antes.
- Calibrarlo con una **tabla 4 × 4** (estado de las reglas → distribución de la etiqueta recalculada en el
  entrenamiento, Dirichlet α = 1; 12 parámetros libres).
- Sirve para contestar si las reglas de la Fase 1 aportaban algo sobre la persistencia, y para dar continuidad a los
  informes.
- **Aviso a priori:** su regla de I exige aceleración y la etiqueta mide nivel. Por ejemplo, en 1981-82 la inflación
  era alta y bajaba: las reglas dirán I↓ y la etiqueta, I alta. Saldrá mal en el eje I. Eso es una diferencia de
  concepto conocida y **no debe corregirse ajustando las reglas a la etiqueta**.
- No entra en el criterio de éxito.

---

## 4. Pregunta 3: qué mejora es significativa, dónde y con qué variables

### Listón económico

| referencia (vintage, ≤ 2004) | log-loss |
|---|---|
| climatología | 1,415 |
| persistencia PIT cruda | 1,300 |
| persistencia + 20 % climatología (sin información, C2) | **0,983** |
| suelo irreducible (entropía de la etiqueta) | 0,361 |

- **Significativa:** ≥ **0,05 nats** frente a M0 como mínimo para el éxito, y **0,10 o más** para que valga la pena
  en la Etapa 2. Debe venir sobre todo de los giros: **≥ 0,25 nats en los meses de giro**, sin empeorar más de 0,03
  en los estables.
- En términos de cartera: el **retraso medio de detección de los giros de G** debe bajar de los ~5-6 meses de la
  persistencia a **≤ 3 meses**, con **≤ 1 falsa alarma cada 2 años** en los meses estables.
- **Alarma de fuga:** una mejora de más de ~0,25 nats frente a M0 en desarrollo es sospechosa. Hay que auditarla
  (placebo, señal plantada) antes de creerla. Es del orden de la fuga plantada que detectan los tests.

### Dónde fallará la persistencia y qué familia debería ayudar

La etiqueta del mes t usa niveles hasta t+4 (G) y t+3 (I). Por eso el "nowcast" tiene **un componente de previsión de
~4 meses**, y los indicadores adelantados y de mercado son legítimos y útiles.

| giro | qué falla en la persistencia | familia que debe aportar | mecanismo |
|---|---|---|---|
| **G↓, entrada en recesión** | 5-6 meses tarde, con mucha seguridad | **Sahm** (confirma la entrada); **crédito** (`baa_spread`: el diferencial se abre con el deterioro de la financiación; la EBP no es admisible, porque es condicional siempre, y la GZ solo desde 2012); **bolsa** (`eq_ret_6m`, que descuenta antes) | Despidos no lineales (Sahm); acelerador financiero (Bernanke-Gertler); precio de los activos = valor descontado |
| **G↓ sin recesión** (1966-67, 1985-86, 1995) | Igual, sin NBER | `growth_rt` (la parte ya observada de la ventana) | Momentum coincidente frente a la tendencia de 10 años |
| **G↑, salida** | Mantiene "crecimiento bajo" demasiado tiempo | `growth_rt`, **bolsa** y **compresión del diferencial** (los mercados se adelantan al mínimo). La Sahm sale tarde, porque mira el mínimo de 12 meses: es asimétrica, útil al entrar e inútil al salir | Asimetría del ciclo |
| **Hazard de final de ciclo** | No lo ve | **Curva** (`curve_10y3m`): la inversión precede a la recesión en 6-18 meses. En el nowcast su efecto será débil o de signo dudoso en el arranque, porque al empezar la recesión la Fed recorta y la curva se empina | Política monetaria restrictiva → crédito → actividad |
| **Cruce de κ en I** | Seguro y equivocado, pero son pocos meses | **Subyacente de 6 meses**: en la fecha de decisión ya cubre la mitad de la ventana de la etiqueta (t−3…t−1) | Es casi la propia definición del eje |
| Shocks energéticos | La etiqueta mira el subyacente: el petróleo **no** debe mover I en el nowcast | Ninguna. La energía es para la Etapa 2 (L-CAP-002) | — |

Salarios, holgura y expectativas mueven la inflación a 6-18 meses: sirven para el **forecast**, no para el nowcast
del eje I.

### Conjunto a priori para la logística/probit del entregable (4)

**Estructura:** dos logísticas binarias con objetivo blando (`p_g_high`, `p_i_high`), combinadas como producto. Es
coherente con la independencia entre ejes de la ficha §5, tiene la mitad de parámetros que una multinomial de 4 clases
y permite una ventana de entrenamiento por eje. Cada eje lleva el logit de la persistencia como entrada, así que
M1 − M0 mide exactamente el valor de la información macro.

| eje | variable (lista blanca principal) | desde | signo preregistrado | por qué |
|---|---|---|---|---|
| G | `growth_rt` | 1963-11 | + | Análogo PIT unilateral de G: la parte observada de la ventana de la etiqueta |
| G | `unrate_sahm` | 1950 | − | Entrada en recesión (no lineal) |
| G | `baa_spread` | 1953 | − | Crédito: el canal más rápido y que no se revisa (pesa en modo vintage) |
| G | `eq_ret_6m` | 1950 | + | Descuenta los ~4 meses de futuro de la etiqueta; no se revisa |
| G | `curve_10y3m` | 1953 | + (débil) | Hazard de final de ciclo; se espera un coeficiente pequeño |
| G | `pers_g` (logit) | 1956-10 | + | Ancla de M0 |
| I | `core_cpi_6m_ann` | 1978 (principal) | + | Mitad de la ventana del eje ya observada |
| I | `headline_cpi_6m_ann` | 1950 | + | **Solo** en la época anterior a la entrada del subyacente (modelo por época del eje I); después, fuera, para que la energía no mueva I |
| I | `pers_i` (logit) | 1956-10 | + | Ancla de M0 |

- Son **7 variables de la lista blanca más las 2 de persistencia**. Todas existen antes de 1964, salvo el subyacente
  (eje I, con su propia ventana).
- El eje G predice desde ~1974 con 120 meses de entrenamiento, así que la muestra de desarrollo conserva 1973-75
  (parcial), 1980, 1981-82, 1990-91 y 2001.
- La L2 se fija a priori. Las variables se estandarizan con la media y la desviación del entrenamiento del corte.
- **Fuera del núcleo, a propósito** (candidatas para el GBM o para una v2 preregistrada):
  - `claims_4w_yoy` y `philly_activity` (1968): son buenas, pero llevarían el inicio del eje G a ~1978 y se perdería
    1973-75;
  - `spf_anxious`, `unrate_gap10y` e `infl_core_pressure`: más útiles para el forecast;
  - `ff_d12m`, `real_ff` y `fedpath_1y`: redundantes con la curva en el nowcast;
  - `oil_yoy` e `infl_energy_pressure`: Etapa 2.
- **Para la v0.4 de la lista blanca** (preregistro, no ahora):
  - `baa_spread` frente a su mediana de 10 años, porque el nivel tiene deriva secular (~1 pp en los 50 frente a 2-3
    pp en los 80);
  - la curva retardada 12 meses o su mínimo de 12 meses, que es el mecanismo real de la inversión.

---

## 5. Resumen de cambios pedidos (antes de P-EVAL-BASE)

1. Persistencia calibrada M0 como listón del criterio principal (E1).
2. Métricas por eje G e I (E2). Bloquea P-EVAL-MOD.
3. Cortes nuevos (E3-E7):
   - giro/estable;
   - épocas;
   - cuadrante y frontera;
   - retraso de detección y falsas alarmas;
   - calibración.
4. Inferencia: bloques de 24 m como sensibilidad y prueba de signo por giros (E8).
5. Ventana de evaluación fija en la configuración (E9).
6. Ventanas de entrenamiento por eje y `sample_weight` (peso 0,5 para los meses provisionales recalculados).
7. Episodios: NBER ± 6 sí; rachas solo de ≥ 6 m; añadir los giros de G.
8. `min_train_months` = 120 más ≥ 2 recesiones y ≥ 8 cambios de G; L2 fijada a priori.
9. Preregistrar P-EVAL-BASE con el contenido del §3(b) **antes** de entrenar M1 con variables.

No he modificado código ni datos del proyecto.

---

## Cálculos para el trial log (2026-10-16, Estratega macro)

- **C1. Descomposición de los baselines por meses de giro, eje, época y recesión.**
  - Corrida `20261016-092402_baselines_v1_27cae755`. La etiqueta dura ≤ 2004 se reconstruye **solo** desde las rachas
    publicadas en su `report.json`, sin leer la etiqueta de nuevo; las recesiones salen de los episodios NBER del
    mismo informe.
  - No usa variables ni nada ≥ 2005.
  - Script: `/private/tmp/claude-501/-Users-victorhdez12/f2807248-3571-41e4-8cad-d757e8c013db/scratchpad/giros.py`.
- **C2. Mezclas fijas de persistencia y climatología, log-loss por eje y entropía de la etiqueta.**
  - Usa las predicciones walk-forward publicadas de la misma corrida, puntuadas contra la etiqueta oficial **≤ 2004**
    leída con `LabelVault('development')`. El acceso quedó registrado en `research/trials/label_access.jsonl`
    (caller `mezcla.py:10`, 660 filas, hasta 2004-12).
  - Mezclas w = 1,0 / 0,9 / 0,8 / 0,7 / 0,6 / 0,5:
    - vintage: 1,2997 / 1,0090 / 0,9832 / 0,9861 / 1,0052 / 1,0367;
    - latest_truncated: 1,1824 / 0,9366 / 0,9184 / 0,9284 / 0,9545 / 0,9932.
  - Persistencia por eje: G 0,957 / I 0,324 (vintage); G 0,869 / I 0,298 (latest_truncated).
  - Entropía media de la etiqueta: 0,361 (0,475 en los giros, 0,310 en los estables).
  - Giros frente a estables (vintage): w = 1,0 da 2,691 / 0,677; w = 0,8 da 1,726 / 0,651.
  - **La rejilla de w se miró dentro de la muestra.** Solo dimensiona la ganancia que viene de la calibración y **no**
    fija ningún parámetro: M0 debe ajustarse en el walk-forward.
  - No usa variables ni nada ≥ 2005.
  - Script: `/private/tmp/claude-501/-Users-victorhdez12/f2807248-3571-41e4-8cad-d757e8c013db/scratchpad/mezcla.py`.
