---
documento: INT-10 — ¿con qué palanca LEGÍTIMA tendría potencia un modelo de ML frente al logit? Potencia y borrador de diseño
version: 0.1-borrador (2026-10-30)
estado: BORRADOR para el usuario. Solo potencia: ningún indicador cruzado con ningún objetivo. Ningún modelo ajustado. Periodo ≥ 2005 sin tocar.
potencia: scripts/int10_potencia.py (commit d3629f0, árbol limpio, 2026-10-30T06:42Z) → research/int/int10_potencia.json (98d30be)
depende_de: INT-4-ML (cerrada, research/int/int4ml_resultado.md), INT-4 (T1, T3), INT-6 (K1, X1), INT-7 (D/P), INT-8 (mensual)
---

# INT-10: "aumentar la potencia de los modelos de ML" (borrador v0.1)

## 0. Qué se pregunta y qué NO se puede hacer
El usuario pide "aumentar la potencia de los modelos de ML". INT-4-ML ya se corrió una vez y **no batió al logit**
(ΔAUC −0,05 … +0,02); por su regla de cierre, **no se pueden probar otros modelos ni otros hiperparámetros sobre la
misma pregunta (entrada T1 / salida T2) y los mismos datos ≤ 2004**. Darle "más capacidad" al modelo (más árboles, redes,
búsqueda de hiperparámetros) no es una palanca: sería la misma pregunta otra vez, y además **no sube la potencia**.

**Idea clave para aprender:** la potencia de un contraste "ML frente a logit" depende de dos cosas: (a) cuántos eventos
**independientes** hay para evaluar, y (b) cuánto se parecen las predicciones de los dos modelos. Con los mismos
indicadores, ML y logit dan predicciones casi iguales (correlación ≈ 0,9), así que su diferencia de AUC se mide con
bastante precisión… pero la diferencia **esperada** también es muy pequeña (+0,00 … +0,03). Lo único legítimo es
añadir **eventos** (más objetivos, más países) o **información** (rasgos nuevos), no capacidad.

Palancas evaluadas: L1 objetivos más frecuentes, L2 multitarea (apilar objetivos), L3 más países, L4 rasgos nuevos
(solo inventario), L5 horizonte.

## 1. Método (solo recuentos, propiedades de cada serie y simulación)
- **Objetivos (solo recuentos):** JST anual, núcleo de 14 países, 1871-2004 sin guerras, h = 1 (igual que INT-4):
  T1 entrada en recesión; T3 entrada en inflación alta (etiqueta de INT-4); K inicio de crisis bancaria (`crisisjst`,
  exclusión de 4 años como INT-6); B1 año con bolsa real total ≤ −20 %; B2 entrada en mercado bajista (caída ≥ 20 %
  desde el máximo del índice real; sale al volver a < −10 %). Mensual: bajistas con la bolsa OCDE deflactada por el IPC
  (1957-2004, sin DNK ni JPN por roturas) y con Shiller (EE. UU., 1871-2004).
- **Indicadores (cada serie por separado):** cobertura, AR(1) y correlación media entre países. AR(1) mediana 0,66;
  correlación entre países mediana 0,32 → son los parámetros del ruido simulado.
- **Simulación:** estructura **real** de filas en riesgo y eventos; puntuaciones **simuladas** (binormales) para "ML" y
  "logit" con ruido AR(1) en el tiempo, componente común entre países y correlación r_mb entre los dos modelos. Listón
  supuesto: AUC del logit 0,70 (INT-4 midió 0,73). ΔAUC con varianza agrupada por **año** (todos los países juntos) y
  **valor crítico sacado de la nula simulada** (tamaño real 3-7 %). Δlog-loss con probabilidades bien calibradas del
  binormal, mismo agrupamiento. 300 réplicas por punto (error Monte Carlo de la potencia ≈ ±0,03). Un solo contraste
  (con Holm-k las MDE suben ≈ 15-25 %).
- **Calibración de r_mb sin datos nuevos:** se usa el error típico de ΔAUC **ya publicado** por INT-4-ML en T1
  (M-L2: 0,009; M-GB: 0,015). La simulación da 0,0125 con r_mb = 0,9 y 0,0094 con 0,95 (0,018 con 0,8; 0,028 con 0,6).
  → **r_mb = 0,9 es el valor realista** para "ML frente a logit con los mismos indicadores". r_mb = 0,6 se muestra
  como el caso en que el ML usa información distinta (más ruido en la diferencia, **menos** potencia).

## 2. Eventos por palanca (≤ 2004)

### L1 — objetivos más frecuentes (núcleo 14, h = 1)
| objetivo | filas en riesgo | eventos | años distintos | efecto de diseño | positivos efectivos | ya visto en |
|---|---|---|---|---|---|---|
| T1 entrada en recesión (referencia) | 1.332 | 222 | 84 | 2,66 | 83 | INT-4, **INT-4-ML (cerrada)** |
| T3 entrada en inflación alta | 1.103 | 247 | 91 | 2,69 | 92 | INT-4 (logit; ΔAUC +0,03, no establecido) |
| K inicio de crisis bancaria | 1.345 | 61 | 33 | 2,71 | 22-33 | INT-6 K1 (crédito; +0,11, no establecido) |
| B1 año con bolsa real ≤ −20 % | 1.553 | 143 | 50 | 4,41 | 32-50 | INT-4 (solo recuentos); INT-7 (D/P → bolsa) |
| B2 entrada en bajista (−20 %) | 859 | 68 | 38 | 3,07 | 22-38 | INT-7 indirectamente |
| BM bajista mensual OCDE real | 1.996 meses-país (h = 12) | 74 | 22 episodios | 3,3 | 22 | INT-4 (EE. UU., 5 entradas) |
| BM bajista mensual Shiller EE. UU. | 647 | 17 | 17 | 1,0 | 17 | INT-7 (CAPE) |

Lectura: **ningún objetivo nuevo tiene más eventos efectivos que T1** salvo T3 (≈ igual). Las caídas de bolsa son
muy simultáneas entre países (efecto de diseño 3-4,4): 143 años malos de bolsa valen ≈ 32-50 eventos. Las crisis
bancarias son pocas (61). Mensual no añade episodios (22 en 48 años; igual que INT-8 con recesiones).

### L2 — multitarea / apilar objetivos
- Coincidencias **entre objetivos** (mismo país, ± 1 año): el 70 % de las crisis bancarias coincide con una entrada en
  recesión; el 47 % de los bajistas con T1 y el 62 % con T3; el 50 % de los años de bolsa ≤ −20 % con T3.
- Suma de eventos T1 + T3 + B1 + B2 + K = 741, pero **579 país-años distintos y 116 años distintos**. Apilar no
  cuadruplica la información: muchos eventos son el mismo episodio visto con otra etiqueta.
- **Matiz importante:** entrenar con varias tareas (multitarea) ayuda a **estimar** el modelo, pero **no** da más eventos
  para **evaluar** una tarea concreta. Solo si el contraste es **uno solo y apilado** ("¿el ML gana de media en las
  tareas?") sube la potencia. Es otra pregunta, más débil que "¿gana en T1?".

### L3 — más países
Núcleo + CAN + IRL (16; AUS y CHE siguen fuera): T1 222 → 244 eventos (84 → 88 años); T3 247 → 277; K 61 → 62;
bolsa: **sin cambio** (CAN e IRL no tienen bolsa en el panel). Ganancia ≈ +5-10 % de eventos, y **CAN e IRL ya se
usaron** como países de prueba informativos en INT-4 e INT-6. No hay más países en JST R6; la OCDE mensual añade meses,
no episodios (INT-8).

### L4 — rasgos nuevos ya establecidos (solo inventario; nunca junto a un objetivo)
| rasgo | país-años 1870-2004 (1950-2004) | AR(1) mediana | corr. entre países | ya cruzado con |
|---|---|---|---|---|
| X1 % de otros países con el PIB cayendo | 1.876 (770) | 0,44 | **0,98** | T1 en INT-6 (**establecido**, +0,12 frente a B1) |
| D/P | 1.707 (753) | 0,81 | 0,34 | bolsa t + 1 en INT-7 (no establecido) |
| crédito/PIB Δ5 (K1) | 1.565 (760) | 0,89 | 0,25 | crisis en INT-6 (no establecido) y T1 en INT-4 |
| curva, bolsa real, inflación (ya en el logit) | 1.763-1.876 | 0,09-0,72 | 0,23-0,41 | INT-4 |

Lectura: X1 es casi un efecto de año (corr. 0,98 entre países): informa del "cuándo", no del "quién". Un rasgo nuevo
**sube la AUC de los dos modelos**; para atribuir la mejora al ML hay que comparar ML y logit **con el mismo rasgo**, y
se vuelve al caso r_mb ≈ 0,9. Además todos ya se han cruzado con sus objetivos: un ML con ellos sería réplica.

### L5 — horizonte
Acortar o alargar el horizonte **no cambia los eventos** (T1: 222 / 221 / 218 con h = 1 / 2 / 3), pero sube el efecto
de diseño (2,66 → 3,32 → 3,86) y bajan los positivos efectivos (83 → 67 → 56). **h = 1 es el que más potencia da.**
Dónde podría ganar más el ML no lineal (literatura, de memoria, orden de magnitud): en interacciones de **crédito ×
curva/tipos** para crisis bancarias (Bluwstein et al., 2023, JST: árboles aleatorios ≈ +0,05 de AUC sobre el logit, pero
con validación cruzada que incluye 2008); Beutel, List y von Schweinitz (2019) encuentran que **el ML no mejora al logit
fuera de muestra** en crisis bancarias; para recesiones (Puglia y Tucker, 2020; Döpke et al., 2017; Vrontos et al.,
2021) las ganancias fuera de muestra son **+0,00 … +0,03**. Nuestro propio INT-4-ML: −0,05 … +0,02. **Efecto realista:
+0,01 … +0,02; optimista: +0,03.** Una ganancia de AUC de +0,02 equivale a Δlog-loss ≈ −0,005 … −0,008.

## 3. Potencia (ML frente a logit, r_mb = 0,9 calibrado; un contraste; 80 %)
| palanca · caso | MDE ΔAUC | MDE en Δlog-loss (a) | potencia si Δ = +0,02 | si Δ = +0,03 | con r_mb = 0,6: MDE |
|---|---|---|---|---|---|
| L0 T1 (como INT-4-ML, referencia) | 0,040 | −0,017 | 25 % | 51 % | 0,066 |
| L1 T3 inflación | 0,032 | −0,017 | 39 % | 76 % | 0,062 |
| L1 K crisis bancaria | 0,058 | −0,009 | 20 % | 31 % | 0,111 |
| L1 B1 bolsa real ≤ −20 % | 0,050 | −0,014 | 24 % | 36 % | 0,100 |
| L1 B2 bajista anual | 0,054 | −0,013 | 28 % | 36 % | 0,107 |
| L1 bajista mensual OCDE (h = 12) | 0,061 | −0,047 | 18 % | 30 % | 0,121 |
| L3 T1 con 16 países | 0,036 | −0,016 | 39 % | 66 % | 0,074 |
| L2 apilado T1 + T3 + B2 + K | **0,021** (0,023 b) | −0,007 | **78 %** (71 % b) | 97 % | 0,041 |
| L2 apilado **sin T1** (T3 + B1 + K) | 0,026 (0,029 b) | −0,008 | 62 % (46 % b) | 93 % (85 % b) | 0,049 |
| L2 + L3 apilado, 16 países | 0,025 (0,022 b) | −0,009 | 67 % (76 % b) | 94 % (95 % b) | 0,044 |

(a) Δlog-loss esperado en la MDE de ΔAUC (el contraste de log-loss tiene MDE casi igual en ΔAUC).
(b) ruido compartido entre tareas del mismo país-año (pesimista: los errores salen de los mismos indicadores).
Error Monte Carlo ≈ ±0,03 en cada potencia; por eso (b) a veces sale mejor que el caso base.

Lectura:
- **Ningún objetivo suelto** llega al 80 % con +0,02; solo T3 se acerca con +0,03 (76 %). Las bolsas, las crisis y el
  mensual tienen **menos** potencia que T1, no más.
- **Solo apilar tareas** (L2) baja la MDE a ≈ 0,021-0,029, es decir, potencia ≈ 46-78 % con +0,02 y ≥ 85 % con +0,03.
  El mejor número (78 %) **incluye T1, que está cerrada**; sin T1, 46-67 %.
- Más países (L3) ayuda poco (0,040 → 0,036) y gasta países ya usados como prueba.

## 4. Contaminación (declarada)
- T1 y T2: **cerradas para ML** (INT-4-ML). Meter T1 en un apilado sería reabrir la misma pregunta por la puerta de atrás.
- T3: el logit con P1-P5 ya se corrió (INT-4: +0,03 frente a B1). K: INT-6 (crédito → crisis, +0,11). B1/B2: INT-7 ya
  mostró que el D/P ordena la bolsa del año siguiente (t 2,3, no establecido) y los regímenes de INT-1/3 describen la bolsa
  en recesión. X1: establecida en INT-6. Cualquier ML con estos rasgos y objetivos se diseñaría **sabiendo** qué funcionó.
- CAN e IRL: países de prueba informativos en INT-4 e INT-6. AUS y CHE: usados en INT-4-ML.
- Este estudio no cruzó ningún indicador con ningún objetivo (solo recuentos, coincidencias entre objetivos, AR(1) y
  correlaciones de cada serie) y usó el error típico ya publicado de INT-4-ML para calibrar r_mb.
- El periodo ≥ 2005 no se ha tocado. Sería la única muestra limpia (con 2008 y 2020), pero es la reserva final del
  proyecto y gastarla en "¿gana el ML?" sería un mal uso: es una corrida única.

## 5. Veredicto honesto
- **Ninguna palanca da ≥ 80 % de potencia para el efecto realista (+0,01 … +0,02).** La única que se acerca es apilar
  objetivos (L2), y su mejor caso (78 %) incluye T1, que no se puede usar. Sin T1: 46-67 % con +0,02; ≥ 85 % solo si el
  ML ganara +0,03 de media en **todas** las tareas, que está por encima de lo que dio INT-4-ML y de la literatura fuera
  de muestra.
- **"Más eventos" no existe en ≤ 2004:** bolsas y crisis son menos y más simultáneas que las recesiones; mensual no añade
  episodios; más países añade ≈ 5-10 %.
- **"Más información" (rasgos)** sí puede mejorar la predicción, pero esa mejora es del **rasgo**, no del ML (el logit
  también la recoge), y los rasgos candidatos ya están vistos.
- Conclusión: con los datos ≤ 2004, **la línea ML no tiene una prueba confirmatoria con potencia suficiente**. Lo que sí
  daría potencia es el tiempo (datos nuevos) o el periodo ≥ 2005, que no se debe gastar en esto.

## 6. Borrador de diseño (solo si el usuario quiere, contra la recomendación)
"INT-10 apilado": un único contraste ML (M-GB de INT-4-ML, mismos hiperparámetros congelados, sin búsqueda) frente al
logit, sobre T3 + B1 + K apiladas, núcleo 14 (o 16), h = 1, dejar un país fuera, AUC estratificada por país × tarea,
bootstrap por bloques de año, placebo desplazado, Δlog-loss < 0. MDE ≈ 0,026-0,029 (potencia ≈ 50-60 % con +0,02).
Resultado esperado más probable: "no establecido". Exploratorio en el mejor de los casos.

## 7. Decisiones del usuario
1. **Mantener cerrada la línea ML sobre ≤ 2004** y no construir INT-10 como prueba (**recomendado**): ninguna palanca
   llega al 80 % con un efecto realista.
2. Si se quiere una última comprobación: el **apilado T3 + B1 + K sin T1** (§6), una sola corrida, con la MDE (≈ 0,027) y
   la potencia (≈ 50-60 %) escritas delante y etiquetado **exploratorio** (no recomendado; probable "no establecido").
3. **No usar el periodo ≥ 2005** para preguntas de ML (recomendado): reservarlo para la validación final de lo ya
   establecido (T1/T2 del logit, X1, G2).
4. Dirigir el esfuerzo a **información**, no a modelos (recomendado): p. ej. llevar X1 (establecido) al termómetro como
   indicador descriptivo, y anotar qué datos nuevos (no JST: más países o series de crédito/diferenciales largas) harían
   falta antes de volver a plantear ML.
5. Revisar la pregunta cuando haya datos nuevos en vivo (≈ 1 década añade ≈ 15-20 eventos T1 en el núcleo; no cambia
   el veredicto a corto plazo).
