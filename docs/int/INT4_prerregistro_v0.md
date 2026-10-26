---
documento: P-DEV-INT4 — termómetro de riesgo ampliado (entradas y salidas de recesión; repunte y vuelta de la inflación): prerregistro
version: 1.0 CONGELADA (2026-10-26T19:08Z)
estado: APROBADO por el usuario el 2026-10-26 ("confío, dale": todas las recomendaciones). Congelado antes de escribir el código de la corrida; nada cruzado.
diseño: docs/int/INT4_diseno_v0.md (las 7 recomendaciones de su §8, aceptadas por defecto por el usuario el 26-oct)
potencia: research/int/int4_potencia.json (commit 6b75e45) y research/int/int4b_potencia.json (script bca4e7d, salida 813b6d8, árbol limpio)
---

# P-DEV-INT4 (borrador v0.1)

## 0. Qué se pregunta
Con lo que se sabía en cada momento (30 de abril de t + 1, datos JST del año t), ¿un termómetro sencillo, fijado aquí,
ordena mejor que el listón de "estado retardado" los país-años con más probabilidad de que **cambie el régimen** al año
siguiente? Cuatro giros, los que mueven los activos según INT-3:

| id | giro | filas en riesgo en t | y = 1 si en t + 1 … | para qué sirve (INT-3) |
|---|---|---|---|---|
| **T1** | **entrada en recesión** | fuera de recesión | empieza una recesión (pico + 1) | bolsa −5,5 pp en recesión (Q5) |
| **T2** | **salida de recesión ("la luz")** | en recesión (pico + 1 … valle) | primer año de crecimiento (valle + 1) | volver a asumir riesgo |
| **T3** | **repunte de la inflación** | fuera del régimen de inflación alta | entra en inflación alta | bonos −10,1 pp, bolsa −8,7 pp en estanflación (Q1, Q2) |
| **T4** | **vuelta de la inflación** | en inflación alta | sale de inflación alta | bonos +7,9 pp en desinflación (Q3) |

Es un **termómetro de riesgo** (probabilidad), no una regla de compraventa. Si sale, pasa a INT-5 (B2 en sombra frente a
B1 en el paper trading); nunca sustituye a B1 sin decisión registrada. Nada ≥ 2005 (bloqueado, P-EVAL-INT4 aparte).

## 1. Datos y muestra (fijos)
- **Panel anual JST**, núcleo de 14 países (BEL, DEU, DNK, ESP, FIN, FRA, GBR, ITA, JPN, NLD, NOR, PRT, SWE, USA). **Países
  de prueba** (AUS, CHE; CAN e IRL sin bolsa → variante sin C6/S3) solo al final, una vez, con el modelo congelado.
- **Principal:** 1871-2004 **sin guerras** (fuera las filas cuya ventana t … t + h toca 1914-1918 o 1939-1945).
  **Contraste temporal:** 1950-2004 (solo signo; potencia baja).
- **Fechado de recesiones:** el anual de INT-1 (convención JST). **Régimen de inflación:** etiqueta anual de INT-1
  (principal: inflación por encima de su media centrada de 11 años Y del 2 %, probabilística; **inflación alta si
  p_i_alta ≥ 0,5**). Sensibilidad: absoluta 3 % (no usa datos futuros). La etiqueta principal usa una ventana centrada:
  es válida como **objetivo** (describe dónde se estuvo), **nunca** como predictor; los años con ventana truncada (cerca
  de 2004 y del inicio de cada serie) van en una sensibilidad sin ellos.
- **h = 1** (principal; origen en abril de t + 1, así que en parte es nowcast, declarado). h = 2 informativo para T1, T3 y
  T4; **T2 sin h = 2** (tasa base 0,90: casi toda recesión acaba en dos años, no hay nada que ordenar).
- Datos revisados (JST y la OCDE ≤ 2004): fechas honestas, niveles no (INT-0).

## 2. Indicadores (fijados aquí; como mucho 5-6 por giro; todo "as of", unidades económicas, sin estandarizar con la muestra)

**T1, entrada en recesión** — los del diseño, modelo principal con los **5 sin vivienda** (decisión 2):
C1 pendiente de la curva; C2 Δ5 crédito/PIB; C4 difusión global (% de los otros 13 con curva invertida, ≥ 5 con dato);
C5 Δ1 tipo real corto; C6 bolsa real del año t. C3 (vivienda real Δ3) solo como secundario; C2 × C3 solo exploratorio.

**T2, salida de recesión:**
| id | indicador | mecanismo (signo esperado sobre la probabilidad de salir) |
|---|---|---|
| S1 | pendiente de la curva en t (= C1) | el banco central ya ha bajado el corto (+) |
| S2 | Δ1 tipo real corto (= C5) | relajación monetaria real (− : bajadas → más salida) |
| S3 | bolsa real del año t (= C6) | el mercado descuenta la recuperación antes (+) |
| S4 | difusión: % de los otros países del núcleo con PIB real per cápita cayendo en t (≥ 5 con dato) | recesión global → salida más lenta (−) |
| S5 | Δ5 crédito/PIB al **pico** de la recesión | tras un auge de crédito la recesión es más larga (−); usa solo datos ≤ pico |

**T3 y T4, repunte y vuelta de la inflación** (los mismos 5; los signos se invierten en T4):
| id | indicador | mecanismo (signo en T3) |
|---|---|---|
| P1 | crecimiento del dinero amplio (Δlog `money`) en t | más dinero que producción (+) |
| P2 | crecimiento de los salarios nominales (Δlog `wage`) en t | espiral salarios-precios, costes (+) |
| P3 | brecha del PIB **unilateral**: log PIB real pc − media de t−10 … t−1 | economía por encima de su capacidad (+) |
| P4 | **precio mundial de las materias primas** (Δlog anual) | choque de costes importado (+) — **condicionado** a que INT-3b consiga una serie ≤ 2004 con cobertura desde ≈ 1870 (p. ej., índice de Jacks); si no, T3/T4 van con 4 |
| P5 | tipo real corto en t (nivel) | política laxa (tipo real negativo) (−) |
- La **depreciación frente al dólar** (Δlog `xrusd`) queda **exploratoria**: no existe para EE. UU. y el tipo frente al
  dólar no es el efectivo.
- P4 es una variable **común** a todos los países (1 dato por año): dejar un país fuera no la valida; su evidencia
  descansa en la evaluación temporal (declarado).
- Petróleo, alimentos, metales y carne del Banco Mundial (desde 1960) **no** entran en el modelo principal (no cubren
  1871-1959): solo en el contraste 1950-2004 como informativos, si INT-3b los cataloga.

**Cobertura** (núcleo, país-años 1870-2004 / 1950-2004, `int4b_potencia.json`): P1 1.732 / 740; P2 1.857 / 770;
P3 1.750 / 770; P5 1.798 / 762; S4 1.876 / 770.

## 3. Listones (siempre publicados)
- **B0:** tasa base incondicional (del pliegue de ajuste). AUC = 0,5.
- **B1 (listón principal), solo información conocida en el origen:**
  - T1: "t es el primer año tras un valle" y log(años desde el último valle) (como el diseño).
  - T2: log(años que lleva la recesión en t) (duración) — **es un listón fuerte**: la mayoría de las recesiones JST dura
    un año.
  - T3/T4: inflación observada en t y en t − 1 (persistencia). **No** se usa la etiqueta ni los años en el régimen
    (la etiqueta mira al futuro).
- Las AUC de los listones no se han medido; la potencia las supone (0,6 / 0,7).

## 4. Método (igual para los cuatro giros)
- **Modelo:** logit agrupado (sin efectos fijos de país), B1 + candidatos del giro, sin penalización, casos completos.
- **Evaluación principal: dejar un país fuera** (14 pliegues, 1871-2004 sin guerras); predicciones fuera de muestra
  juntas. **Temporal:** ventana creciente por décadas (ajuste con filas cuyo objetivo acaba antes de la década; décadas
  1950 … 2000-2004); sensibilidad con efectos fijos de país.
- **Métrica principal:** AUC. Secundarias: log-loss, Brier, calibración (intercepto y pendiente).
- **Inferencia:** **bootstrap por bloques de año** (2.000 réplicas; se remuestrean años con todos sus países) para el IC
  95 % de ΔAUC, Δlog-loss y ΔBrier frente a B1. Se añade la corrección del Validador de INT-3: **placebo desplazado**
  (indicadores desplazados en círculo k ≥ 6 años, misma k para todos los países, todas las k posibles) y el p-valor se
  calibra con esa distribución.
- **Familias de contrastes (Holm):**
  1. **Principal (Holm sobre 4):** combinado frente a B1, un contraste por giro (T1, T2, T3, T4), h = 1, dejar un país
     fuera.
  2. **Secundaria T1 (Holm sobre 6):** cada candidato C1-C6 añadido a B1 por separado (decisión 3 del diseño).
  3. Candidato a candidato en T2-T4, h = 2, financieras frente a normales, 1950-2004, etiqueta abs3, sin truncadas, EE.
     UU. mensual y países de prueba: **informativos** (se publican, no se "establecen").
- **Criterio de "establecido"** (todos): (i) ΔAUC > 0 con el IC 95 % por bloques que excluye 0 tras Holm; (ii) p del
  placebo calibrado < 0,05 tras Holm; (iii) Δlog-loss < 0 (mejora fuera de muestra, no solo de orden); (iv) el signo de
  ΔAUC en la evaluación temporal 1950-2004 es positivo; (v) calibración: pendiente en [0,5; 1,5].
- **Una sola corrida** con puerta (`src/intl/procedencia.py`: commit, árbol limpio, hora UTC); todo al registro de
  pruebas. Validador independiente del diseño de la corrida y del resultado.

## 5. Potencia (solo recuentos; MDE de ΔAUC, 80 %, A0 = 0,6 / 0,7; un contraste — Holm)

| giro | muestra | filas | eventos | años distintos | tasa base | MDE A0 = 0,6 | MDE A0 = 0,7 |
|---|---|---|---|---|---|---|---|
| T1 entrada | 1871-2004 sin guerras | 1.332 | 222 | 84 | 0,17 | 0,10 — 0,12 | 0,09 — 0,11 |
| T1, con los 5 sin vivienda | ídem | 1.090 | 166 | 72 | — | 0,11 — 0,14 | — |
| **T2 salida** | ídem | 334 | 220 | 84 | 0,66 | 0,11-0,12 — 0,14-0,15 | 0,10 — 0,12 |
| T2 salida | 1950-2004 | 81 | 62 | 25 | 0,77 | 0,30 — inalcanzable | inalcanzable |
| **T3 repunte** | 1871-2004 sin guerras | 1.103 | 247 | 91 | 0,22 | 0,10 — 0,12 | 0,09 — 0,11 |
| T3, con P1-P2-P3-P5 | ídem | 938 | 207 | 83 | — | 0,10 — 0,12 | 0,09 — 0,12 |
| **T4 vuelta** | ídem | 563 | 263 | 89 | 0,47 | 0,11 — 0,13 | 0,10 — 0,12 |
| T3 / T4 | 1950-2004 | 440 / 316 | 115 / 117 | 42 / 38 | 0,26 / 0,37 | 0,15 — 0,18 | 0,13-0,14 — 0,16-0,17 |
| T3 / T4 abs3 | 1871-2004 sin guerras | 979 / 687 | 183 / 199 | 70 / 74 | — | 0,11-0,12 / 0,12-0,14 | — |

Holm sobre 4 en la familia principal: z ≈ 3,30 (entre las columnas "un contraste" y "Holm-6"): MDE ≈ 0,11-0,14.

**Lectura honesta:**
- Los cuatro giros tienen la misma potencia con toda la historia: se detecta una mejora de AUC de **≈ 0,11-0,14** sobre
  el listón. Un modelo combinado con mecanismo puede llegar ahí frente a un listón flojo; frente a uno fuerte (duración
  en T2, persistencia de la inflación en T3/T4, que pueden dar AUC ≈ 0,7-0,8), **no es probable**.
- **T2 tiene el listón más difícil:** la duración ya predice mucho (la mayoría de las recesiones duran un año).
- **1950-2004** solo sirve para ver el signo; **T2 en 1950-2004 no tiene potencia**.
- La etiqueta de inflación principal cambia a menudo (≈ 247 entradas en 14 países en 130 años: un cambio cada ≈ 4-5 años
  por país): muchos giros son pequeños o de frontera. Por eso se publica también la abs3.
- **"No establecido" no es "no existe".** Cualquier indicador individual (+0,02-0,05) queda por debajo de lo detectable.

## 6. Contaminación (declarada)
- C2, C3 y el auge crédito + vivienda: elegidos sabiendo que funcionaron con este panel (Schularick-Taylor 2012,
  JST 2015) → réplica, no descubrimiento.
- Dinero y salarios para la inflación (P1, P2): ideas anteriores a 2005 (Friedman, curva de Phillips de salarios); que
  el dinero perdiera relación con la inflación después de 1980 es conocido → expectativa: más débil en 1950-2004.
- Materias primas (P4): el papel del petróleo en 1973-1979 es conocido por todos; contaminación media-alta en la
  evaluación temporal.
- S1-S5 (salida): curva y bolsa como adelantados de la recuperación son anteriores a 2005; S5 (crédito al pico) es una
  réplica de JST 2013 ("When credit bites back").

## 7. Fuera de esta corrida
- INT-3b (activos nuevos), INT-3c (por qué) e INT-3d (giros: cuándo tocan fondo los activos) tienen sus propios
  prerregistros (agentes en paralelo). INT-3d mide **cuánto cuesta esperar** a confirmar el giro; INT-4 mide **si se
  puede anticipar**. Juntos dicen si el termómetro vale dinero; INT-5 lo prueba en sombra.
- EE. UU. mensual: solo descriptivo (6 entradas NBER ≤ 2004; sin potencia).

## 8. Decisiones del usuario antes de congelar
1. **Familia principal de 4** (T1-T4) con Holm, o solo T1 como principal y T2-T4 secundarios (más potencia para T1:
   MDE 0,10 en lugar de ≈ 0,12). *Recomendado: los 4, porque la pregunta es "cuándo cambia el régimen", no solo la
   recesión.*
2. **Etiqueta de inflación:** principal (relativa + 2 %, la de INT-3; recomendado para enlazar con los activos) o abs3
   (observable, sin ventana centrada).
3. **P4 materias primas:** esperar a INT-3b o congelar ya T3/T4 con 4 indicadores (P1, P2, P3, P5). *Recomendado:
   congelar con 4 y P4 como informativo, para no depender de otra fase.*
4. **Criterio (iv)** (signo positivo en 1950-2004): mantenerlo como obligatorio (recomendado, protege frente a un
   resultado solo del siglo XIX) o informativo.
5. Aprobar → se congela como v1.0 con hora antes de escribir el código de la corrida.

## Decisiones del usuario (2026-10-26, congelado v1.0)
Todas las recomendadas: (1) familia principal de 4 (T1-T4) con Holm; (2) etiqueta de inflación principal (relativa + 2 %, la de INT-3), abs3 como sensibilidad; (3) T3/T4 con P1, P2, P3, P5; P4 materias primas solo informativo; (4) criterio (iv), signo positivo en 1950-2004, obligatorio.
