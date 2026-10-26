---
documento: INT-4 — termómetro de riesgo (forecast de recesión y de caídas fuertes de bolsa en el panel): diseño
version: 0.1-borrador (2026-10-26)
estado: BORRADOR para el usuario. Solo diseño y potencia. Ningún indicador cruzado con ningún objetivo.
plan: docs/PLAN_internacional_v0.md (pieza 3, fase INT-4)
depende_de: INT-0 (panel, retrasos, decisiones sobre CLI y crisisjst), INT-1 (fechado anual de recesiones), INT-2 (método de potencia)
fuente_potencia: scripts/int4_potencia.py → research/int/int4_potencia.json (procedencia: commit 6b75e45, árbol limpio)
---

# INT-4: termómetro de riesgo (diseño v0.1)

## 0. Qué es y qué no es
- **Pregunta:** con lo que se sabía en cada momento, ¿unos pocos indicadores con mecanismo conocido anticipan la
  **entrada en recesión** (y las **caídas fuertes de bolsa**) a 1-2 años en el panel de países, mejor que los listones
  ingenuos? Es la pieza 3 del plan.
- **Es un termómetro de riesgo:** una probabilidad para reducir riesgo antes, no una regla para batir al mercado. Si sale,
  pasa a INT-5 (B2 en sombra frente a B1); nunca sustituye a B1 sin decisión registrada.
- **No es** un nowcast del cuadrante, ni minería de indicadores, ni una evaluación en el periodo bloqueado (≥ 2005).

## 1. Objetivos (fijados a priori)

### 1.1 Anual, panel JST (principal)
- **Núcleo:** 14 países (BEL, DEU, DNK, ESP, FIN, FRA, GBR, ITA, JPN, NLD, NOR, PRT, SWE, USA). **Países de prueba** (AUS,
  CHE, CAN, IRL): nunca entran en ningún ajuste ni elección; se miran al final con el modelo congelado.
- **Fechado:** el anual de INT-1 (`$FIN_DATA_ROOT/intl/recesiones_anuales_dev.parquet`, convención JST: pico = máximo
  local del PIB real per cápita). **Año de entrada** E = pico + 1 (primer año con caída).
- **Origen del pronóstico:** 30 de abril de t + 1 (datos JST del año t, retraso de 120 días de `src/intl/lags.py`).
- **Objetivo y_h(i, t) = 1** si país i entra en recesión en algún año de t + 1 … t + h; h = 1 (principal) y h = 2.
  **Filas en riesgo:** años t que no son de recesión (pico + 1 … valle). Nota: con h = 1 el año t + 1 ya lleva cuatro
  meses en marcha en el origen; es en parte un nowcast (declarado; ver decisión 4).
- **Subtipos:** recesión **normal** o **financiera** (crisis JST a ± 2 años del pico, como en INT-1). `crisisjst` es una
  clasificación ex post: sirve para **etiquetar el objetivo**, nunca como predictor (decisión de INT-0).
- **Caída fuerte de bolsa (secundario):** y = 1 si algún año de t + 1 … t + h tiene una **rentabilidad real total de la
  bolsa ≤ −20 %** (`eq_tr_real` de JST). Sin restricción de filas en riesgo.
- **Periodos:** principal **1871-2004 sin guerras** (se quitan las filas cuya ventana t … t + h toca 1914-1918 o
  1939-1945); contraste 1950-2004.

### 1.2 Mensual, solo EE. UU. (secundario, informativo)
- **Recesión:** entrada NBER (`USREC`, primer mes con 1 tras un 0), solo como **objetivo**: `src/intl/data.py` prohíbe
  usarlo como variable. y = 1 si hay entrada en t + 1 … t + h, h = 6 y 12 meses; meses en riesgo: fuera de recesión NBER
  (definición de la muestra con el fechado ex post, declarada). Muestra desde 1964-07 (primer mes con curva "as of").
- **Caída fuerte de bolsa:** el índice de precios OCDE (`oecd_share_usa`, media mensual: suavizado declarado) cae ≥ 20 %
  desde su máximo previo; el episodio termina cuando vuelve a menos del 10 % del máximo.
- **No hay objetivo mensual internacional:** el fechado Bry-Boschan mensual de INT-1 **no pasó su puerta** (6/8 picos NBER
  en los dos intentos, < 80 %) y quedó **solo informativo** (commit 9017620, Validador 2026-10-27). No se usa como objetivo.

## 2. Indicadores candidatos (6 como máximo, fijados aquí)

Todos "as of" con `src/intl/lags.py` (JST anual: 120 días; mercado: 1 día; IPC: 45; IP: 75). Unidades económicas, sin
estandarizar con la muestra completa. Cobertura en país-años del núcleo con dato (de `research/int/int4_potencia.json`,
solo recuentos).

| id | indicador | mecanismo | serie (anual / EE. UU. mensual) | cobertura núcleo 1870-2004 / 1950-2004 | huecos | ¿conocido antes de 2005? (contaminación) |
|---|---|---|---|---|---|---|
| **C1** | **pendiente de la curva** (largo − corto) | el banco central sube el corto por encima del largo cuando frena la economía; el mercado descuenta bajadas futuras | `jst_*_ltrate` − `jst_*_stir` / `oecd_irlt_usa` − `oecd_ir3m_usa` (`curva`) | 1.792 / 762 | DNK desde 1875, JPN 1879, PRT 1880; EE. UU. mensual desde 1964-07 | sí: Kessel 1965, Harvey 1988, Estrella-Hardouvelis 1991, Estrella-Mishkin 1998, Bernard-Gerlach 1998 (8 países). **Baja** (pero sabemos que acertó en 2007 y 2019) |
| **C2** | **cambio a 5 años del crédito / PIB** | los auges de crédito acumulan deuda y fragilidad; el desapalancamiento alarga y hunde la recesión (Minsky, Kindleberger) | `jst_*_tloans` / `jst_*_gdp`, Δ5 (`credito_pib` de `src/intl/panel.py`) / el anual de EE. UU. "as of" | 1.565 / 760 | ESP, FRA, NLD desde 1905; BEL 1890 | concepto sí (Kaminsky-Reinhart 1999, Borio-Lowe 2002); **la evidencia con JST es de 2012-2013 (Schularick-Taylor; Jordà-Schularick-Taylor) y con este mismo panel y estos años: contaminación ALTA por muestra** (aquí es una réplica, no un descubrimiento) |
| **C3** | **vivienda real, cambio a 3 años** | el precio de la vivienda sostiene el colateral y el consumo; su caída lo retira | log(`jst_*_hpnom` / `jst_*_cpi`), Δ3 / el anual de EE. UU. "as of" | 1.330 / 667 | **ESP desde 1974, ITA 1973, PRT 1991**, FIN 1908, JPN 1916 | Bordo-Jeanne 2002, Borio-McGuire 2004: sí; lo fuerte (JST 2015-2016, 2008) es posterior. **Media-alta** |
| **C4** | **difusión global**: % de los otros 13 países del núcleo con curva invertida (anual) / con IP interanual < 0 (mensual) | los choques comunes y el comercio sincronizan las recesiones (1974, 1980-82, 1991, 2001) | C1 de los otros países / `oecd_ip_*` (`ip_yoy`) | 1.890 / 770 | exige ≥ 5 países con dato; mensual desde 1956 | la idea (índices de difusión, Burns-Mitchell 1946; Kose-Otrok-Whiteman 2003) sí; **la construcción concreta se elige hoy**. Baja-media |
| **C5** | **cambio a 1 año del tipo real corto** | el endurecimiento monetario en términos reales precede a las recesiones | Δ1(`jst_*_stir`/100 − Δlog `jst_*_cpi`) / Δ12(`tipo_3m` − `ipc_yoy`) | 1.776 / 759 | ITA desde 1886, PRT 1881 | sí: Romer-Romer 1989, Bernanke-Blinder 1992. **Baja** |
| **C6** | **rentabilidad real de la bolsa del año t** (momentum) | el mercado descuenta antes la caída de beneficios | `jst_*_eq_tr_real` / `bolsa_12m` (`oecd_share_usa`) | 1.763 / 770 | ESP, NLD desde 1900; FIN 1896 | sí para recesión (Stock-Watson 1989/2003, Estrella-Mishkin 1998). **Baja**; para caídas de bolsa, el momentum de series temporales es más reciente (media) |

- **Auge conjunto crédito + vivienda (C2 × C3):** solo **exploratorio**, fuera de los contrastes, porque la evidencia
  ("Leveraged bubbles", JST 2015) es posterior a 2008 y con este panel: contaminación alta.
- **Excluidos como predictores:** CLI de la OCDE (filtro de dos lados, muy revisado) y `crisisjst` (ex post), por las
  decisiones de INT-0; también Sahm, EBP y NFCI (diseñados con 2008-2019).
- **Cobertura conjunta** (solo disponibilidad, nunca el valor; `anual_con_datos` del JSON), recesión h = 1, 1871-2004 sin
  guerras: con los 5 sin vivienda, 1.090 filas y **166 entradas** (72 años distintos); con los 6, 867 filas y **119
  entradas** (60 años). La vivienda cuesta ≈ 30 % de los eventos.
- **Datos revisados:** JST y la OCDE ≤ 2004 son series revisadas; las fechas son honestas, los niveles no (INT-0).

## 3. Listones (siempre publicados)
- **B0, tasa base incondicional** (estimada en el pliegue de ajuste): AUC = 0,5 por construcción.
- **B1, estado retardado (anual):** logit con dos variables derivadas del fechado JST y conocidas en el origen: "t es el
  primer año tras un valle" y log(años desde el último valle). **Listón principal.**
- **EE. UU. mensual:** B0 y **volatilidad reciente** (desviación típica de los 12 últimos rendimientos mensuales del índice;
  medias mensuales, declarado). No hay estado retardado: `USREC` no puede ser variable.
- Las AUC de los listones **no se han medido**: en la potencia se suponen (0,50 / 0,60 / 0,70 / 0,75).

## 4. Método (a fijar en el prerregistro)
- **Modelo principal:** logit **agrupado** (pooled), sin efectos fijos de país (con dejar un país fuera no se puede estimar
  el efecto fijo del país dejado), con B1 + los candidatos del modelo principal (decisión 2). Sin penalización: con 5
  covariables y ≈ 166 entradas hay ≈ 30 eventos por parámetro. Casos completos.
- **Evaluación en dos ejes, todo ≤ 2004:**
  1. **Dejar un país fuera** (14 pliegues, 1871-2004 sin guerras): predicciones fuera de muestra de todos los países
     juntas. **Contraste principal.**
  2. **Tiempo, ventana creciente por décadas:** ajuste con las filas cuyo objetivo termina antes del inicio de la década
     (t + h < inicio) y predicción de la década; décadas 1950 … 2000-2004. Aquí se permiten efectos fijos de país
     (sensibilidad). Es de contraste: su potencia es la de 1950-2004 (§5).
- **Métricas:** **AUC** (principal; la potencia está calculada para ella), Brier y log-loss (secundarias), calibración
  (intercepto y pendiente). Inferencia con **bootstrap por bloques de año** (se remuestrean años con todos sus países;
  2.000 réplicas): IC 95 % de ΔAUC, Δlog-loss y ΔBrier frente a B1.
- **Contrastes:** uno principal (modelo combinado frente a B1, recesión h = 1, dejar un país fuera) y como mucho 6
  secundarios con **Holm** (cada candidato añadido a B1 por separado). h = 2, recesiones financieras, caídas de bolsa,
  1950-2004 y EE. UU. mensual: **informativos** (§6).
- **Placebo:** los mismos contrastes con los indicadores desplazados ≥ 6 años en círculo (misma k para todos los países,
  como INT-2): tasa de falsos positivos.
- **Países de prueba** (al final, una vez, con el modelo congelado): AUS y CHE con todo; CAN e IRL no tienen bolsa en JST
  → variante sin C6, fijada a priori.

## 5. Potencia (calculada; solo recuentos de eventos y tasas base)

`scripts/int4_potencia.py` → `research/int/int4_potencia.json`. Solo cuenta eventos, años con eventos y la agrupación del
**objetivo** entre países en el mismo año (ICC por año, con la corrección de Kish del tamaño de grupo); de los indicadores,
solo cuántos datos hay. **No se ha calculado ninguna AUC, correlación ni media condicionada de ningún indicador.**
MDE = mejora mínima detectable de AUC frente a un listón de AUC A0, 80 % de potencia, bilateral 5 % (z = 2,80; con Holm
sobre 6 contrastes, z = 3,48), error típico de Hanley-McNeil y AUC correlacionadas (r = 0,5). Positivos efectivos: central
= eventos / efecto de diseño; prudente = años distintos con algún evento. Se toma **el mayor de los dos**.

**Recuentos (núcleo, ≤ 2004):**

| objetivo | periodo | filas en riesgo | entradas | años distintos | tasa base | ICC por año | efecto de diseño |
|---|---|---|---|---|---|---|---|
| recesión h = 1 | 1871-2004 sin guerras | 1.332 | 222 (151 normales, 71 financieras) | 84 | 16,7 % | 0,15 | 2,7 |
| recesión h = 2 | ídem | 1.297 | 221 | 84 | 29,8 % | 0,21 | 3,3 |
| recesión h = 1 | 1950-2004 | 675 | 61 (54 / 7) | 24 | 9,0 % | 0,22 | 3,7 |
| recesión h = 2 | 1950-2004 | 665 | 61 | 24 | 17,7 % | 0,28 | 4,3 |
| bolsa ≤ −20 % real, h = 1 | 1871-2004 sin guerras | 1.553 | 143 años-evento | 50 | 9,2 % | 0,28 | 4,4 |
| bolsa ≤ −20 % real, h = 1 | 1950-2004 | 756 | 85 | 27 | 11,2 % | 0,31 | 5,1 |

**MDE de ΔAUC (A0 = 0,50 / 0,60 / 0,70; un contraste — con Holm-6):**

| objetivo | muestra | MDE |
|---|---|---|
| **recesión h = 1** | 1871-2004 sin guerras, todas las filas | **0,10 / 0,10 / 0,09 — 0,12 / 0,12 / 0,11** |
| recesión h = 1 | ídem, con los 5 candidatos sin vivienda | 0,11 (A0 = 0,6) — 0,14 |
| recesión h = 1 | ídem, con los 6 | 0,13 (A0 = 0,6) — 0,16 |
| **recesión h = 2** | 1871-2004 sin guerras | **0,11 / 0,11 / 0,10 — 0,14 / 0,14 / 0,13** |
| recesión financiera h = 1 / h = 2 | 1871-2004 sin guerras (71 entradas, 41 años) | 0,16 / 0,18 (A0 = 0,6) — 0,20 / 0,22 |
| recesión h = 1 / h = 2 | 1950-2004 (evaluación temporal) | 0,21 / 0,23 (A0 = 0,5); 0,20 / 0,22 (0,6) — 0,24-0,27 |
| recesión financiera | 1950-2004 (7 entradas, 6 años) | ≥ 0,31 o inalcanzable |
| bolsa ≤ −20 %, h = 1 / h = 2 | 1871-2004 sin guerras | 0,15 / 0,15 (A0 = 0,6) — 0,18 / 0,19 |
| bolsa ≤ −20 %, h = 1 / h = 2 | 1950-2004 | 0,20 / 0,21 (A0 = 0,6) — 0,25 |

**EE. UU. mensual (desde 1964-07, con curva "as of"):**

| objetivo | entradas (≤ 2004) | meses en riesgo | MDE A0 = 0,50 | A0 = 0,60 | A0 ≥ 0,70 |
|---|---|---|---|---|---|
| NBER, h = 6 meses | 6 (1970-01, 1973-12, 1980-02, 1981-08, 1990-08, 2001-04) | 415 | 0,33 | 0,31 | inalcanzable |
| NBER, h = 12 meses | 6 | 409 | 0,34 | 0,33 | inalcanzable |
| caída ≥ 20 %, h = 6 / 12 | 4 (1970-04, 1973-12, 1987-11, 2002-07) | 378 / 372 | 0,38 / 0,39 | inalcanzable | inalcanzable |

Desde 1957 (sin curva: 8 entradas NBER, 5 caídas) el MDE baja a ≈ 0,28-0,29 con A0 = 0,6: sigue siendo inalcanzable con
un listón de volatilidad realista (≈ 0,75, como en `docs/lineaB/diseno_v0.md`). 1966 y 1990 no llegan al −20 % en medias
mensuales (declarado).

**Lectura:**
- **Panel anual completo, dejar un país fuera:** se detecta una mejora de AUC de **≈ 0,10** (un contraste) o **≈ 0,12**
  (Holm-6) sobre un listón de 0,6; con los 6 candidatos y sus huecos, ≈ 0,13-0,16. La literatura da AUC de ≈ 0,7-0,8 con
  curva y crédito: un **modelo combinado** frente a B0/B1 está dentro de lo detectable; la aportación **incremental de un
  solo indicador** (típicamente 0,02-0,05) **no**: los secundarios saldrán casi todos "no establecidos" aunque existan.
- **h = 2 no añade eventos** (las mismas 221 entradas) y sube la agrupación por año: la potencia empeora un poco.
- **Recesiones financieras:** solo efectos grandes (≈ 0,16-0,20) y solo con toda la historia.
- **1950-2004 (evaluación temporal):** 24 años con entradas → solo mejoras de ≈ 0,20-0,27: sirve para comprobar el signo,
  no para establecer nada.
- **EE. UU. mensual:** 6 entradas → **no hay potencia** (como ya decía la línea B). Es descriptivo.
- **Caídas de bolsa:** más agrupadas entre países que las recesiones (ICC 0,28-0,34): ≈ 0,15 con toda la historia,
  ≈ 0,20 en 1950-2004. Secundario.

## 6. Qué podrán decir y qué no los resultados
- **Podrán decir:** si un termómetro sencillo, fijado de antemano, ordena mejor que el estado retardado los país-años con
  más riesgo de entrar en recesión al año siguiente, en países que no se usaron para ajustarlo, con 135 años de historia.
- **No podrán decir:** qué indicador concreto aporta más (no hay potencia para separar contribuciones pequeñas); nada fino
  sobre el periodo moderno por sí solo; nada sobre EE. UU. mensual; nada sobre ≥ 2005 (bloqueado).
- **Contaminación:** C2 y C3 se eligen sabiendo que la literatura los encontró con este panel y que "funcionaron" en 2008.
  Un buen resultado de C2 es una **réplica** de Schularick-Taylor, no evidencia nueva. C1, C5 y C6 son anteriores a 2005.
- **Expectativa honesta:** el combinado frente a B0 debería salir (AUC ≈ 0,65-0,75 es lo habitual); frente a B1, probable
  pero no seguro; los secundarios, en su mayoría no establecidos. "No establecido" no es "no existe". Útil para gestionar
  riesgo, no para batir al mercado.

## 7. Gobierno
1. **Prerregistro** P-DEV-INT4 (objetivo, candidatos, transformaciones, listones, contrastes, criterios, placebo, países
   de prueba) **aprobado por el usuario** y commiteado con hora **antes** de cualquier corrida. Hasta entonces, nada cruza
   indicadores con objetivos.
2. Una sola corrida con puerta: `src/intl/procedencia.py` (commit, árbol limpio, hora UTC en la salida). Todo al registro.
3. **Validador independiente** (sin haber escrito el código) del diseño de la corrida y del resultado.
4. El bloqueado de JST (2005-2020) solo con una evaluación única aparte (P-EVAL-INT4), si el usuario lo decide.

## 8. Decisiones del usuario
1. **Objetivo principal:** entrada en recesión a h = 1 en el panel anual, 1871-2004 sin guerras, dejando un país fuera
   (recomendado); h = 2, recesiones financieras, caídas de bolsa, 1950-2004 y EE. UU. mensual como informativos.
2. **Modelo principal:** los **5 candidatos sin vivienda** (recomendado: la vivienda cuesta ≈ 30 % de los eventos y es más
   contaminada) o los 6.
3. **Contrastes:** uno principal (combinado frente a B1) + ≤ 6 secundarios con Holm (recomendado), sabiendo que los
   secundarios tienen poca potencia.
4. **Definición de h = 1:** entrada en t + 1 con origen en abril de t + 1 (recomendado; en parte nowcast) o la estricta,
   entrada en t + 2.
5. **Umbrales de caída de bolsa:** −20 % real anual; −20 % / −10 % mensual en EE. UU.
6. **EE. UU. mensual:** mantenerlo como descriptivo (recomendado) o quitarlo. Auge conjunto crédito + vivienda: solo
   exploratorio (recomendado) o fuera.
7. Si se aprueba: redactar el prerregistro P-DEV-INT4.
