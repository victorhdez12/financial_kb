---
documento: HPO-ML-RECESIÓN — ajuste de hiperparámetros EXPLORATORIO del ML de recesión (T1 entrada, T2 salida)
version: 1.0 (plan congelado antes de correr; §1-§5 no cambian tras ver el resultado)
estado: EXPLORATORIO declarado. NO reabre la línea ML (P-DEV-INT4-ML cerrada, §7 de su prerregistro; INT-10: sin potencia). Ningún resultado congelado se toca.
codigo: scripts/hpo_ml_recesion.py · espacio congelado: research/int/hpo_ml_recesion/espacio.json
salida: research/int/hpo_ml_recesion/resultado.{json,md}
depende_de: INT-4 (filas, indicadores, listón logit), INT-4-ML (resultado y regla de cierre), INT-10 (MDE)
---

# HPO-ML-RECESIÓN: ¿cambia la conclusión un ajuste serio de hiperparámetros? (exploratorio)

## 0. Pregunta y estatus
INT-4-ML probó dos modelos con hiperparámetros fijos (M-L2, M-GB) y ninguno batió al logit de INT-4 (ΔAUC estratificada
−0,05 … +0,02). Crítica razonable: "quizá con hiperparámetros bien elegidos sí gana". Aquí se responde **sin trampas**:
la elección de hiperparámetros se hace **dentro** de cada pliegue de entrenamiento (validación cruzada anidada), con el
mismo presupuesto para cada candidato y declarado antes, y la ganancia se compara con un placebo que repite **todo** el
procedimiento con el objetivo permutado.

**Estatus:** exploratorio. Los datos ≤ 2004 están muy usados (INT-1 … INT-4, INT-4-ML, INT-10, INT-13). Aunque saliera
algo, **no se establece nada**: como mucho se nombra una configuración a prerregistrar para datos que no se hayan visto.
El periodo ≥ 2005 no se toca.

## 1. Datos y evaluación (idénticos a INT-4 / INT-4-ML)
- Núcleo 14 países JST, 1871-2004 sin guerras, h = 1, casos completos. T1: 1.090 filas / 166 eventos (C1, C2, C4, C5, C6
  + B1); T2: 235 / 163 (S1-S5 + B1). El código comprueba que ningún año objetivo pasa de 2004.
- **Externo:** dejar un país fuera (14 pliegues), como INT-4. **Interno:** dejar un país fuera sobre los 13 países de
  ajuste (13 pliegues). INT-4 no usa embargo temporal en el dejar-un-país-fuera (los pliegues son países, no años); se
  mantiene igual en los dos niveles. (Truco de cálculo, sin efecto en el resultado: el ajuste sin {c, d} sirve al
  pliegue externo c y al d; se ajusta una vez por par, 91 pares.)
- **Criterio interno:** AUC estratificada por país de las predicciones internas juntas (13 países). Gana la configuración
  con la mayor; empate → la primera de la lista. La elegida se reajusta con los 13 países y predice el país externo.
- **Listón:** el logit de INT-4 (B1 + indicadores, sin penalizar), en los mismos pliegues externos. **Métrica principal:
  AUC estratificada por país** (solo pares del mismo país: arreglo del sesgo LOCO del intercepto, sensibilidad de INT-4).
  Secundarias: Δlog-loss, pendiente de calibración.

## 2. Espacio y presupuesto (declarado antes; igual para todos)
**20 configuraciones por candidato**, muestreo aleatorio (`ParameterSampler`, semilla = índice del candidato) del espacio
siguiente. La lista exacta de las 60 está en `espacio.json` (generada sin datos y congelada con este documento; el
script se niega a correr si no coincide).

| candidato | hiperparámetros buscados | fijos |
|---|---|---|
| **GB** gradient boosting (`HistGradientBoostingClassifier`) | profundidad {1, 2, 3, 4}; tasa log-uniforme [0,01; 0,2]; árboles {50, 100, 200, 400}; mínimo por hoja {10, 20, 40, 80}; L2 {0; 0,1; 1; 10}; monotonía de INT-4-ML {sí, no} | sin parada temprana, semilla 0 |
| **RF** bosque aleatorio | profundidad {2, 3, 4, 6, sin límite}; mínimo por hoja {5, 10, 20, 40, 80}; variables por corte {√p, 0,5, 1}; submuestra {completa, 0,5} | 100 árboles, semilla 0 |
| **EN** logit regularizado | C log-uniforme [0,001; 10]; mezcla L1 {0 (= L2), 0,25, 0,5, 0,75, 1 (= L1)}; interacciones de 2.º orden entre indicadores {no, sí} | saga, estandarización del pliegue |
| **TODOS** | el interno elige entre las 60 | — |

Coste: 60 configuraciones × (91 pares internos + 14 externos) = 6.300 ajustes por giro y réplica.

## 3. Inferencia
- **IC 95 %** de ΔAUC estratificada (selector − logit) y de Δlog-loss: bootstrap por bloques de año (2.000 réplicas,
  semilla 0) sobre las predicciones externas anidadas, como INT-4-ML.
- **Placebo (ganancia por azar):** el objetivo se permuta por bloques dentro de cada país (filas del país ordenadas por
  año, bloques consecutivos de 5 filas en T1 y 3 en T2, se baraja el orden de los bloques; conserva la tasa base de cada
  país y parte de la dependencia). **30 réplicas** (coste: ≈ 840 s de CPU por réplica; la máquina es compartida), y en cada una se repite TODO: las 60 configuraciones, la selección
  interna y el logit. p del placebo = 1 − Φ(z), z = (ΔAUC obs − media placebo) / dt placebo (como INT-4-ML), y p por
  rangos informativa.
- **Multiplicidad:** 4 selectores × 2 giros = **Holm-8**.
- **Registro de todas las pruebas:** para cada una de las 60 configuraciones y cada giro se guardan su puntuación interna
  (media, mín., máx. sobre los 14 pliegues), su ΔAUC LOCO **no anidada** y cuántas veces la eligió el interno. Se publica
  el "optimismo de no anidar": la mejor de las 60 medida en el propio LOCO externo, frente al mismo máximo en el placebo.

## 4. Criterio para nombrar una configuración "a prerregistrar" (no "establecida")
Todos: (a) ΔAUC estratificada anidada > 0 con IC por bloques que excluye 0 tras Holm-8; (b) p del placebo < 0,05 tras
Holm-8; (c) Δlog-loss < 0; (d) **ΔAUC ≥ 0,05**, el extremo bajo de la MDE de INT-4-ML/INT-10 (0,05-0,07 con r 0,8-0,9;
INT-10 da 0,040 para un solo contraste en T1). Si alguna cumple, se escribe la configuración elegida con más frecuencia
como candidata para un prerregistro en datos nuevos; si no, nada.

## 5. Contaminación (declarada)
- Datos ≤ 2004 usados en INT-4 e INT-4-ML con estas mismas filas e indicadores; sabemos que el logit funciona y que
  M-GB dio +0,018 en T1. El espacio se eligió sabiendo eso (incluye la zona de M-GB).
- Una pasada `--prueba` (2 configuraciones por candidato, 2 réplicas de placebo) sirvió para medir tiempos; su salida
  está enmascarada (solo tiempos y tamaños; ninguna AUC impresa ni guardada). Por esos tiempos (máquina compartida con
  otros agentes) se bajó, antes de congelar, el bosque de 200 a 100 árboles y el placebo de 100 a 30 réplicas.

## 6. Resultado
(Pendiente: se rellena tras la corrida con puerta, sin cambiar §1-§5.)

## 7. Conclusión
(Pendiente.)
