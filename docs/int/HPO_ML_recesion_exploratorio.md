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
Corrida con puerta: commit `9240372` (árbol limpio), 2026-11-04 16:03 → 18:00 UTC; el plan se congeló en `bd49a1e` y el
único cambio entre ambos fue limitar los procesos a 5 de un hilo (máquina compartida; no cambia el cálculo). La corrida
escribió `resultado.json` y falló al dibujar la tabla (claves de cuantiles); `resultado.md` y la línea del registro se
rehicieron desde el JSON sin recalcular (`--informe`, commit siguiente). Detalle: `research/int/hpo_ml_recesion/resultado.md`.

ΔAUC estratificada anidada (selector − logit de INT-4), IC 95 % por bloques de año, placebo (30 réplicas con todo el
procedimiento repetido) y Δlog-loss:

| giro · selector | AUC logit → selector | ΔAUC [IC 95 %] | placebo media (dt) | z (p) | Δlog-loss [IC] | ¿≥ MDE 0,05? |
|---|---|---|---|---|---|---|
| T1 · GB | 0,732 → 0,752 | +0,020 [−0,014; +0,054] | +0,001 (0,034) | +0,54 (0,29) | −0,006 [−0,020; +0,006] | no |
| T1 · RF | 0,732 → 0,749 | +0,017 [−0,016; +0,049] | −0,000 (0,037) | +0,48 (0,31) | −0,009 [−0,023; +0,006] | no |
| T1 · EN | 0,732 → 0,724 | −0,007 [−0,017; +0,002] | +0,003 (0,032) | −0,31 (0,62) | +0,014 [0,000; +0,038] | no |
| T1 · TODOS | 0,732 → 0,752 | +0,020 [−0,014; +0,054] | −0,002 (0,031) | +0,70 (0,24) | −0,006 [−0,019; +0,007] | no |
| T2 · GB | 0,770 → 0,729 | −0,042 [−0,100; +0,021] | −0,013 (0,060) | −0,48 (0,69) | +0,011 [−0,032; +0,049] | no |
| T2 · RF | 0,770 → 0,709 | −0,061 [−0,124; −0,001] | +0,006 (0,054) | −1,26 (0,90) | +0,015 [−0,023; +0,048] | no |
| T2 · EN | 0,770 → 0,774 | +0,003 [−0,012; +0,021] | −0,001 (0,049) | +0,09 (0,47) | +0,017 [−0,026; +0,053] | no |
| T2 · TODOS | 0,770 → 0,738 | −0,033 [−0,083; +0,016] | −0,014 (0,058) | −0,32 (0,63) | +0,027 [−0,018; +0,065] | no |

- **Ningún selector cumple ningún criterio de §4 salvo (c) Δlog-loss < 0 en T1 (GB, RF, TODOS).** Ningún IC excluye 0
  a favor del ML (ni sin Holm), ningún placebo da p < 0,2, y ninguna ganancia llega a la MDE (0,05-0,07; ni a 0,040 de INT-10).
- **T1:** la búsqueda deja al GB en +0,020, prácticamente lo mismo que el M-GB fijo de INT-4-ML (+0,018). El interno
  elige casi siempre GB poco profundos y monótonos (GB09: profundidad 3, 50 árboles, tasa 0,04, monotonía sí; 7 de 14
  pliegues). La ganancia es ≈ 0,6 dt del placebo: ruido.
- **T2:** los árboles empeoran (RF −0,061, el único IC que excluye 0, **en contra** del ML); el selector global acaba
  eligiendo logits regularizados **sin interacciones**, es decir, el propio logit (EN +0,003).
- **Optimismo de no anidar:** escoger la mejor de las 60 mirando el LOCO externo daría T1 +0,035 y T2 +0,000; pero con el
  objetivo permutado ese mismo máximo sale de media +0,045 (T1) y +0,069 (T2), p95 +0,089 / +0,132. Es decir, **el
  máximo observado está por debajo de lo que da el azar** con 60 configuraciones: quien publicara "la mejor
  configuración" sin anidar estaría reportando ruido.
- Todas las pruebas (60 configuraciones × 2 giros, con su puntuación interna, su ΔAUC LOCO no anidada y cuántas veces
  se eligió) están en `resultado.json`.

## 7. Conclusión
Un ajuste serio de hiperparámetros, bien anidado, **no cambia la conclusión de INT-4-ML ni de INT-10**: en la entrada
(T1) el mejor ML gana ≈ +0,02 de AUC estratificada, igual que el modelo fijo, dentro del ruido (placebo z ≈ 0,5-0,7) y
por debajo de la MDE (0,05-0,07); en la salida (T2) el ML pierde y la búsqueda vuelve al logit. La línea ML sigue
cerrada sobre ≤ 2004. **No hay configuración que prerregistrar** (§4 no se cumple en ningún caso). Si en el futuro hay
datos nuevos, la única forma con sentido sería un GB poco profundo y monótono como el GB09 o el M-GB ya congelado, y aun
así con potencia insuficiente para +0,02 (INT-10).
