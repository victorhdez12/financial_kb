---
documento: revisión económica de M1 (logística por eje) y de sus resultados de desarrollo
hito: docs/models/m1_spec.md (bf7049d), docs/models/m1_results_dev.md (9b64c5c), research/trials/m1_v1/
fecha: 2026-10-16
revisor: Estratega macro
veredicto: ❌ NO gastar el periodo bloqueado en M1 v1 · ⚠️ el resultado de desarrollo es informativo y orienta una M1 v2
---

# Revisión económica de M1 (desarrollo ≤ 2004)

## Veredicto

**❌ M1 v1 no debe ir a la evaluación única.** No es un problema de fuga (el placebo está limpio) ni de implementación
(la especificación se respetó). Es un **fallo de diseño económico mío** en el conjunto a priori:
- **Las variables describen el estado, no el giro.** M1 está más seguro que M0 cuando el ciclo no cambia y se equivoca
  con más seguridad justo antes y durante los giros. Eso es lo contrario de lo que se buscaba.
- **El signo de Sahm** estaba mal preregistrado para una especificación lineal en nivel (§2).
- **El eje I con el subyacente** está mal identificado si el pendiente se estima libremente (§3).

Gastar el bloqueado ahora daría casi con certeza un "no", **con un coste irreversible**: la evaluación limpia es una
sola. Recomiendo **una M1 v2 preregistrada con 3 cambios mínimos y con mecanismo**, la base **PIT v0.4** con 4
variables de giro, y evaluar **v1 y v2 juntas** en la misma corrida única (§4).

**Periodo bloqueado.** No he leído nada ≥ 2005-01 ni he desbloqueado la caja fuerte. Los cálculos (C3, C4) están al
final, para el trial log.

---

## 1. ¿Por qué M1 gana en los meses estables y no en los giros?

**Estudio de eventos (C3).** Uso los 9 giros de G con ≥ 6 meses a cada lado en la ventana larga (1975-06 → 2004,
vintage): P(G alto) de M0 y de M1 frente a la etiqueta oficial, del mes −6 al +8 respecto al giro.

| | k = −4 | −2 | −1 | **0** | +1 | +2 | +4 | +6 |
|---|---|---|---|---|---|---|---|---|
| **G↓ (5 giros)**: etiqueta p_g | 0,88 | 0,79 | 0,58 | 0,31 | 0,16 | 0,09 | 0,08 | 0,15 |
| M0 | 0,64 | 0,61 | 0,59 | 0,59 | 0,58 | 0,59 | 0,56 | 0,49 |
| M1 | 0,75 | 0,71 | 0,69 | **0,70** | 0,66 | 0,65 | 0,52 | 0,39 |
| mejora de M1 (nats) | +0,04 | −0,03 | −0,10 | **−0,26** | −0,23 | −0,22 | +0,08 | +0,13 |
| **G↑ (4 giros)**: etiqueta p_g | 0,14 | 0,17 | 0,26 | 0,56 | 0,78 | 0,80 | 0,82 | 0,73 |
| M0 | 0,46 | 0,48 | 0,47 | 0,46 | 0,45 | 0,47 | 0,53 | 0,62 |
| M1 | 0,62 | 0,57 | 0,57 | 0,56 | 0,60 | 0,61 | 0,71 | 0,79 |
| mejora de M1 (nats) | **−0,36** | −0,24 | −0,16 | +0,02 | +0,23 | +0,20 | +0,16 | +0,12 |

**Lectura.** M0 no sabe nada del giro: se queda en ~0,5-0,6 todo el tiempo. Gana en los giros solo porque **no se
compromete**. M1 sí se compromete, y en la dirección equivocada en dos momentos:
- **Antes de una caída de G** sigue leyendo fortaleza (0,70 en k = 0) y solo reacciona en k ≥ 3-4.
  - `growth_rt` es coincidente: el ritmo de 3 meses hasta t−1 está centrado en ~t−2, así que en k = 0 todavía refleja
    el régimen anterior **por construcción**.
  - Al final del ciclo, la bolsa y la curva en nivel no avisan a 0-4 meses vista.
- **Antes de una subida de G** se adelanta 4-6 meses ("falso amanecer").
  - La curva muy empinada tras los recortes y el rebote de la bolsa (coeficientes +0,54 y +0,35) anticipan la
    recuperación con 6-12 meses de antelación.
  - La etiqueta solo mira **4** meses adelante. El adelanto de los mercados es **más largo y más variable** que el
    horizonte de la etiqueta.

**¿Puede un nowcast con estas variables adelantar giros?** Solo en parte, y no con estas formas funcionales:
- La ventana de G(t) usa niveles de t−4 a t+4. En la fecha de decisión, los datos coincidentes oficiales llegan hasta
  t−1. **Ningún dato coincidente puede ver el giro antes de k ≈ +2.** Es un suelo estructural, no un fallo de M1.
- Lo único que puede ver el mes t es la **información del propio mes**:
  - peticiones de paro semanales;
  - Filadelfia;
  - mercados.
  De ellas solo los mercados están en M1, y en una forma (nivel lineal) que mezcla horizontes.
- Lo que sí puede aportar un indicador adelantado en un nowcast es **modular la confianza**, es decir, el riesgo de
  giro (hazard). Por ejemplo, "la curva estuvo invertida hace 6-18 meses" no debe subir ni bajar P(G) de forma
  lineal: debe **acercarla a 0,5** (o a la baja) en la fase tardía. Una logística lineal en niveles contemporáneos no
  puede expresar eso.
- Objetivo realista en los giros: **no perder frente a M0 en k = −2…+2** y ganar de k = +2 en adelante, con menos
  falsas alarmas. **No** detectar el giro antes de que ocurra.

**Implicación para el criterio.** Mi listón "≥ 0,25 nats en los meses de giro" (revisión del arnés §4) era demasiado
ambicioso para un nowcast con datos coincidentes con retraso. Para P-EVAL-BASE lo sustituyo por: **giros ≥ 0**
(no peor que M0) **y** mejora total ≥ 0,05 **y** falsas alarmas ≤ 0,5 al año. Es un cambio de criterio y se anota como
tal, antes de evaluar nada en el periodo bloqueado.

## 2. El signo de la Sahm: es un efecto de rebote, no un artefacto

Descriptivos ≤ 2004 (C4, matriz vintage y etiqueta oficial, 1964-2004):
- La correlación de `unrate_sahm` con `growth_rt` es **−0,54**: colinealidad moderada, no extrema.
- Cuando la Sahm está activa (≥ 0,5) y `growth_rt` > 0 (20 meses), el p_g_high medio es **0,73**. Cuando está activa
  y `growth_rt` < 0, es 0,19.
- **Del fin de la recesión NBER en adelante**, la Sahm sigue en 1,4-2,2 durante 8 meses mientras p_g_high sube de 0
  a 0,4-0,6.

Mecanismo: la Sahm compara la media del paro de 3 meses con su **mínimo de 12 meses**, que es el de antes de la
recesión. Por eso, en la práctica, mide "hubo una recesión en el último año". Y G se mide **frente a la tendencia**: las
recuperaciones crecen por encima de la tendencia (rebote). Condicionada a `growth_rt`, una Sahm alta señala la fase
de rebote, así que **el signo positivo es económicamente correcto** en una especificación lineal en nivel.

El error estuvo en el preregistro: la Sahm es una señal de **entrada** (cruce de 0,5), asimétrica. Ya lo escribí en
la tabla de mecanismos ("útil al entrar e inútil al salir") y aun así la metí en nivel con signo negativo.
**Colinealidad sola, no**: el efecto aparece en el 98-100 % de los cortes y tiene una explicación de ciclo.

**Para la v2:**
- **quitar la Sahm en nivel**;
- la alternativa con mecanismo simétrico es su **cambio de 3 meses** (sube al entrar y baja al salir: signo −
  coherente en las dos fases), que requiere la v0.4 (§5).

## 3. El eje I con el subyacente: sí al eje "casi estructural"

- **Qué pasó.** El coeficiente del subyacente queda en +0,17 (el del IPC general, en +0,40), y con "excluir
  provisionales" la log-loss de I se dispara (0,86 frente a 0,41).
  - En 1978-88 la inflación está casi siempre muy por encima de κ: la pendiente cerca del umbral no se identifica.
  - La estandarización con la σ de la Gran Inflación (~3 pp) agrava el problema: con L2 sobre un β por σ, la
    pendiente **por punto porcentual cerca de 2,9 %** queda aplastada.
- **Propuesta para la v2 (fijada sin estimar con la etiqueta).** Un *offset* estructural con pendiente fija y solo los
  parámetros de M0 libres:

  logit P(I alta) = c + b · logit(pers_i) + **1,7 · (core_cpi_6m_ann − 2,9) / s**, con s = **0,75 pp**

  - **2,9 %** es el equivalente en IPC de κ = 2,5 % en PCE (ficha §4). **1,7** convierte probit en logit.
  - **s** suma el ruido de revisión del eje (s_I = 0,31) y el de los meses que faltan de la ventana: el subyacente de
    6 meses en t−1 cubre la mitad de la ventana t−3…t+3 de la etiqueta. Tomo 0,75 pp a priori, con sensibilidades
    preregistradas de 0,5 y 1,0 que se publican y **no eligen**.
  - Lo que se estima son c y b, como en M0: con el offset fijado, está identificado aunque no haya ningún cruce.
- **Por qué no el IPC general**, aunque gane en desarrollo:
  - elegirlo ahora sería seleccionar con datos de desarrollo;
  - la etiqueta es subyacente: en un periodo con grandes shocks de energía, el IPC general movería I en sentido
    contrario a la etiqueta. Es el mecanismo que ya argumenté antes de ver nada.
  - Su ventaja en 1975-2004 está en la época en que el eje I es un marcador de época.

## 4. Decisiones del usuario: recomendación

### (i) ¿Gastar el periodo bloqueado en M1 v1? **No.**
- No cumple en desarrollo los criterios 1 (mejora con IC > 0), 3 (giros) ni 5 (signos), y duplica las falsas alarmas.
- Las ampliaciones futuras del bloqueado (meses que maduran) son pequeñas. La evaluación grande, 2005-2021-10, es una
  sola.
- Esperar no cuesta nada económico: el sistema no opera hasta tener un modelo validado.

### (ii) M1 v2: preregistrarla, minimizando la contaminación
Cambios, **limitados a tres** y cada uno con el mecanismo escrito antes de correr nada:
1. **Quitar la Sahm en nivel** (§2). Si la v0.4 está lista, entra su Δ3m con signo −.
2. **Eje I estructural** con el subyacente (§3).
3. **Variables de riesgo de giro de la v0.4** en el eje G (§5): mínimo de la curva en 12 meses, Baa frente a su
   mediana de 10 años y Δ6m del Baa. Sustituyen a `curve_10y3m` en nivel.

**Cómo minimizar la contaminación:**
- Escribir y commitear la especificación de la v2 **antes** de cualquier corrida con la etiqueta, con este
  diagnóstico citado como origen. Es post hoc declarado.
- En desarrollo, correr la v2 **solo** para el placebo, la estabilidad de signos y los controles de fuga. **No** se
  vuelve a iterar con su log-loss de desarrollo: una sola corrida, se publica tal como salga, y no hay v3 mirando
  esa tabla.
- En la evaluación única, **v1 y v2 juntas** frente a M0, con Holm (k = 2) sobre las dos. Así la elección entre ellas
  no se hace con datos de desarrollo, y el coste de la búsqueda queda contado. Se anotan las dos especificaciones en
  el trial log como intentos (Deflated, `PLAN.md`).

### (iii) Eje I para P-EVAL-BASE
**Subyacente estructural** (§3), con el subyacente libre (v1) como comparación dentro de la misma corrida. No el IPC
general.

### (iv) P-EVAL-BASE (ajustes al borrador de mi revisión del arnés)
- **Hipótesis principal:** M1 v2 frente a M0, en vintage.
- **Criterio de éxito:**
  - mejora ≥ 0,05 con IC > 0;
  - **giros ≥ 0** (era ≥ 0,25; §1);
  - meses estables sin empeorar más de 0,05;
  - mismo signo en 2005-14 y 2015+;
  - signos preregistrados;
  - **falsas alarmas ≤ 0,5 al año**.
- **Secundarios:** v1, reglas, persistencia cruda, climatología y, si están listos, Markov con transiciones variables
  y GBM.
- **Cuándo:** solo con la v2 y la v0.4 congeladas y validadas.

## 5. Variables nuevas con mecanismo para los giros. Sí hace falta una base PIT v0.4

Por orden de prioridad:

| # | variable | definición (a priori) | mecanismo | signo | inicio |
|---|---|---|---|---|---|
| 1 | `claims_4w_yoy` (ya en la v0.3) | — | El dato de despidos del **propio mes**: el único dato de empleo que ve t | − | 1968 |
| 2 | `curve_min12` (**v0.4**) | Mínimo de `curve_10y3m` en los 12 meses hasta t | Una inversión **reciente** eleva el riesgo de caída a 6-18 meses. Recoge el adelanto en lugar de la pendiente actual, que tras los recortes se empina y da el "falso amanecer" | + | 1954 |
| 3 | `baa_gap10y` (**v0.4**) | `baa_spread` − su mediana de los 120 meses previos | Precio del riesgo de crédito frente a lo normal, sin la deriva secular del nivel (~1 pp en los 50, 2-3 en los 80) | − | 1963 |
| 4 | `baa_d6m` (**v0.4**) | Cambio de 6 meses de `baa_spread` | El **empeoramiento** del crédito coincide con la entrada; la **compresión**, con la salida. Simétrico | − | 1954 |
| 5 | `sahm_d3m` (**v0.4**) | Cambio de 3 meses de `unrate_sahm` | Señal de entrada con signo coherente en la salida (§2) | − | 1951 |
| 6 | `philly_activity` / `philly_neworders` (ya en la v0.3) | — | Encuesta del propio mes | + | 1968 |

**Formas que no recomiendo:** más variables de nivel contemporáneo (`ff_d12m`, `real_ff`, `eq_ret_6m` en otros
plazos). Añaden nitidez en los meses estables y error en los giros: es el patrón de M1.

**Coste de usar peticiones de paro y Filadelfia:** el eje G empieza en ~1978 en lugar de 1975-06. Se pierde 1975-77,
la salida de 1975 y parte de la ganancia de época de +0,17. Lo acepto: es la única información del propio mes.

**Familia de modelo (para el entregable siguiente, no para M1).** El mecanismo "los coincidentes dicen el estado y los
adelantados cambian la probabilidad de transición" es exactamente el **Markov switching con probabilidades de
transición variables** (TVTP, Filardo 1994; Diebold-Lee-Weinbach). Debería ser el siguiente aspirante, con las
variables 2-5 en la matriz de transición y `growth_rt` y peticiones de paro en la emisión. Un GBM con restricciones
de monotonía también captaría la asimetría de la Sahm.

**¿v0.4?** Sí:
- 4 derivadas nuevas (2-5), fijadas a priori con su mecanismo;
- placebo y tests de fuga como en la v0.3, y validación;
- alternativa más barata a medio plazo: que el arnés pase al modelo la historia de las variables ≤ t (m1_spec §8).
  Pero las derivadas congeladas en la matriz son más auditables.

## 6. Resumen priorizado
1. **No** evaluar M1 v1 en el periodo bloqueado.
2. Base PIT v0.4: `curve_min12`, `baa_gap10y`, `baa_d6m`, `sahm_d3m` (a priori, con validación).
3. M1 v2 preregistrada antes de correrla:
   - sin Sahm en nivel (con `sahm_d3m`);
   - eje I estructural (s = 0,75; sensibilidades 0,5 y 1,0);
   - eje G con `growth_rt`, `claims_4w_yoy`, `curve_min12`, `baa_gap10y`, `baa_d6m` y `eq_ret_6m`.
   - En desarrollo, una sola corrida, sin iterar.
4. Ajustar P-EVAL-BASE: giros ≥ 0 y falsas alarmas ≤ 0,5 al año; v1 y v2 juntas con Holm.
5. Siguiente aspirante: Markov con transiciones variables. La evaluación única se hace cuando estén v2, Markov y,
   si llega, el GBM.

No he modificado código ni datos del proyecto.

---

## Cálculos para el trial log (2026-10-16, Estratega macro)

- **C3. Estudio de eventos de M0 y M1-general en los giros de G.**
  - Predicciones publicadas de la corrida `20261016-141648_m1_logit_axis_v1_long_0e55b60b` (vintage), puntuadas
    contra la etiqueta oficial **≤ 2004** (`LabelVault('development')`; acceso registrado en
    `research/trials/label_access.jsonl`, caller `m1_diag.py:10`).
  - Giro = p_g_high oficial cruza 0,5 con ≥ 6 meses a cada lado: 9 giros (1979-02↓, 1983-01↑, 1985-02↓, 1985-09↑,
    1989-01↓, 1993-08↑, 1995-01↓, 1996-02↑, 2000-04↓).
  - Ventana k = −6…+8; log-loss binaria con recorte 1e-4.
  - Solo es descriptivo: no ajusta nada.
- **C4. Descriptivos de la Sahm (1964-2004, matriz vintage v0.3 leída con el filtro `decision_date` < 2005 y etiqueta
  oficial ≤ 2004).**
  - corr(Sahm, `growth_rt`) = −0,536;
  - p_g_high medio por (Sahm ≥ 0,5) × (`growth_rt` > 0):
    - (no, no) 0,370 en 160 meses;
    - (no, sí) 0,745 en 213 meses;
    - (sí, no) 0,185 en 99 meses;
    - (sí, sí) 0,727 en 20 meses;
  - quintiles del residuo de la Sahm sobre `growth_rt`;
  - trayectoria de la Sahm, `growth_rt` y p_g_high a 0-12 meses del fin de cada recesión NBER.
  - Es una relación variable-etiqueta ≤ 2004 **mirada después** de M1 v1: contamina la elección de la v2 y se declara
    como tal (§4-ii).
- Script: `/private/tmp/claude-501/-Users-victorhdez12/f2807248-3571-41e4-8cad-d757e8c013db/scratchpad/m1_diag.py`. Nada ≥ 2005.
