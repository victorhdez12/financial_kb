---
documento: P-DEV-INT4-ML — ¿un modelo de machine learning ordena mejor la entrada (T1) y la salida (T2) de recesión que el logit de INT-4?
version: 1.0 CONGELADA (2026-10-26T20:28Z)
estado: APROBADO por el usuario (26-oct): los dos candidatos, Holm-4, correr una vez. Congelado antes de escribir el código. NO se ha ajustado ningún modelo de ML.
potencia: scripts/int4ml_potencia.py (commit previo a la salida) → research/int/int4ml_potencia.json
---

# P-DEV-INT4-ML (borrador v0.1)

## 1. Pregunta
Con los mismos datos, objetivos, filas e indicadores que P-DEV-INT4 v1.0, ¿un modelo flexible ordena mejor que el **logit
de INT-4** (el listón aquí es el logit, no B1)?

## 2. Candidatos (como mucho 2, todo fijado ahora, sin búsqueda de hiperparámetros)
- **M-L2: logit con regularización L2** sobre B1 + los indicadores de INT-4 del giro + **todas las interacciones de
  segundo orden** entre indicadores (sin cuadrados). Variables estandarizadas con media y desviación del pliegue de ajuste.
  Penalización fija **C = 1** (λ = 1 en las variables estandarizadas), sin validación cruzada interna.
- **M-GB: gradient boosting poco profundo** (`sklearn.ensemble.HistGradientBoostingClassifier`): profundidad máxima 2,
  200 árboles, tasa de aprendizaje 0,05, mínimo 20 filas por hoja, L2 = 1, sin parada temprana, semilla 0.
  **Restricciones de monotonía con el signo del mecanismo:**
  - T1: curva −, Δ5 crédito/PIB +, difusión de curvas invertidas +, Δ tipo real +, bolsa −;
  - T2: curva +, Δ tipo real −, bolsa +, difusión de caídas −, crédito al pico −;
  - variables de B1: sin restricción.
- Mismo tratamiento de huecos que INT-4 (casos completos), misma muestra (núcleo 14 países, 1871-2004 sin guerras, h = 1).

## 3. Evaluación (idéntica a INT-4 corregida)
- **Dejar un país fuera** (14 pliegues), ML y logit ajustados en los mismos pliegues.
- **Métrica principal: AUC estratificada por país** (solo pares del mismo país; evita el sesgo del intercepto que encontró
  la sensibilidad de INT-4). Secundarias: AUC agrupada, log-loss, Brier, calibración.
- **Bootstrap por bloques de año** (2.000 réplicas) para el IC 95 % de ΔAUC (ML − logit) y Δlog-loss.
- **Placebo:** indicadores desplazados en círculo k ≥ 6 años (todas las k, la misma en todos los países), reajustando los
  DOS modelos; **p con z calibrada** (media y dispersión de los placebos) y p por rangos informativa.
- **Temporal:** ventana creciente por décadas 1950-2004 (solo signo).
- **Familia: 4 contrastes** (M-L2 y M-GB × T1 y T2), **Holm-4**.
- **Establecido** si: (i) IC 95 % de ΔAUC estratificada > 0 tras Holm; (ii) z placebo con Holm; (iii) Δlog-loss < 0;
  (iv) signo positivo en la evaluación temporal; (v) pendiente de calibración en [0,5; 1,5].
- Países de prueba (AUS, CHE) al final con el modelo congelado; informativo.

## 4. Potencia (ΔAUC mínima detectable, 80 %, frente al logit)
Listón = AUC estratificada del logit ya medida (T1 0,732; T2 0,770). La correlación entre las AUC de los dos modelos es
desconocida y alta (mismos datos y mismos indicadores): rejilla r.

| giro | positivos / negativos efectivos | r = 0,5 | r = 0,7 | r = 0,8 | r = 0,9 |
|---|---|---|---|---|---|
| T1 entrada | 72 / 336 | 0,11 | 0,09 | 0,07 | 0,05 |
| T2 salida | 129 / 67 | 0,10 | 0,08 | 0,07 | 0,05 |

(con Holm-4; con un solo contraste, ≈ 0,01-0,02 menos)

**Lectura clara:** con la correlación más realista (r ≈ 0,8-0,9) solo se detectaría una mejora de **≈ 0,05-0,07** de AUC.
Lo habitual del ML frente a un logit bien especificado, con 5 indicadores y ≈ 200 eventos, es **+0,00-0,03**. **Lo más
probable es "no establecido".** Con r = 0,5 el umbral pasa de 0,10: entonces solo efectos enormes.

## 5. Contaminación (declarada)
- Los datos ≤ 2004 ya se han usado mucho (INT-1 a INT-4 y sus sensibilidades). Los indicadores, los signos de monotonía y
  la forma del listón se eligieron sabiendo que el logit funciona en T1 y T2.
- La pregunta sigue siendo honesta porque los hiperparámetros se fijan ahora y no hay búsqueda: un resultado positivo
  diría "hay no linealidad útil"; uno negativo, "el logit basta".

## 6. Decisiones del usuario
1. Aprobar los 2 candidatos tal cual o quedarse con uno (con uno solo: Holm-2, umbral ≈ 0,01 menor).
2. Correrlo sabiendo que lo más probable es "no establecido" (recomendado: es barato y cierra la pregunta), o no correrlo.

## 7. Decisiones del usuario y regla de cierre (congelado v1.0)
- Los dos candidatos (M-L2 y M-GB), Holm-4, una sola corrida con puerta (árbol limpio), después Validador.
- **Si el resultado es "no establecido", la línea de ML queda cerrada con estos datos: no se prueban otros modelos ni otros
  hiperparámetros sobre ≤ 2004.**
