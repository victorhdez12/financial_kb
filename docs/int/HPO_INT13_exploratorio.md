---
documento: HPO-INT13 — ajuste de hiperparámetros ANIDADO (exploratorio) del XGBoost por paquetes de INT-13
version: 1.0 (2026-11-04) — §1-§6 CONGELADOS en el commit del código, ANTES de la corrida. §7 (resultado) se añade después
naturaleza: EXPLORATORIO declarado. Mismos datos ≤ 2004 que INT-13 (y que INT-4, INT-4-ML, INT-8, INT-12)
datos: SOLO ≤ 2004-12-31 (los mismos loaders que INT-13: scripts/int13_corrida.cargar_real). 2005+ BLOQUEADO, no se toca
código: src/intl/hpo_int13.py, scripts/hpo_int13_corrida.py, tests/test_intl_hpo_int13.py
salida: research/int/hpo_int13/ (real.json, pruebas_internas.jsonl, pred_*.csv.gz, placebo/*.json, resultado.{json,md})
---

# HPO-INT13: ¿un XGBoost bien ajustado bate al logit por encima del ruido de la búsqueda? (exploratorio)

## 0. Qué es y qué no es
- INT-13 fijó los hiperparámetros a priori (max_depth 2, η 0,05, 100 árboles…). Pregunta de este trabajo: **¿ajustarlos
  hace que el XGBoost por paquetes bata al logit simple (curva) — y al logit con los mismos rasgos — de forma que supere
  la ganancia que una búsqueda de hiperparámetros obtiene por puro azar (placebo)?**
- **Exploratorio.** No cambia ningún resultado congelado (INT-13 queda como está). Nada de aquí es "establecido".
- **Contaminación adicional (declarada):** el ajuste usa los mismos datos ≤ 2004 que INT-13 y que el desarrollo del
  prerregistro E1 (recesión a 12 m: "logit actividad frente a curva", lo redacta otro agente; no se toca aquí). Si de
  aquí saliese una configuración que E1 adoptase, quedaría elegida con esos datos: la confirmación de E1 solo puede venir
  del periodo bloqueado (≥ 2005) o del vivo, y el registro de pruebas de E1 debe sumar estas búsquedas.
- **Revisión OCDE (aviso):** la ingesta del 2-nov revisó series OCDE ≤ 2004 (Bitácora 4-nov). El XGBoost "por defecto"
  de INT-13 se recalcula aquí con los datos actuales, así que sus cifras pueden diferir algo de
  `research/int/int13_resultado.md`; todas las comparaciones de este documento usan la MISMA muestra.

## 1. Alcance (fijo)
- **Objetivos:** los tres a 12 meses de INT-13: **E1_12** (entrada en recesión en 12 m), **E2** (inflación +2 pp en
  12 m), **E3** (tipo corto +100 pb en 12 m). E1-6 no se ajusta. Definiciones, conjunto en riesgo, muestras, rasgos
  "as of", paquetes P1-P6, restricciones monótonas, base logit y combinación (media de correcciones en logit): **idénticos
  a INT-13** (`src/intl/int13.py`, sin cambios).
- **Modelos por objetivo y paquete (P1-P6 y combinación):**
  - `def` = XGBoost de INT-13 (parámetros fijos, 100 árboles), recalculado.
  - `hpo` = XGBoost con hiperparámetros elegidos en el bucle interno (mismas monotonías, `base_margin` = logit base).
  - `lgt` = **logit con los mismos rasgos** (base + rasgos del paquete; estandarizados con el entreno; NaN → media del
    entreno; sin penalizar) — listón adicional, el que INT-13 echó en falta.
  - Listones de INT-13: `clima` y `base` (logit simple de 2-3 variables).

## 2. Espacio de búsqueda y presupuesto (fijos antes de correr)
- **20 configuraciones**, semilla `20261104` (`hpo_int13.muestrear_configs`): la nº 0 = INT-13
  (η 0,05, depth 2, mcw 10, subsample 0,8, colsample 1, λ 5, α 0); 19 al azar:
  η log-uniforme [0,02; 0,3]; max_depth ∈ {1, 2, 3, 4, 6}; min_child_weight log-uniforme [1; 100]; subsample U[0,5; 1];
  colsample_bytree U[0,5; 1]; λ log-uniforme [0,1; 100]; α = 0 con prob. ½, si no log-uniforme [0,01; 10].
- **Nº de árboles (early stopping):** cada configuración se entrena 300 rondas en cada pliegue interno; se elige la ronda
  (≥ 10) que minimiza la log-loss de validación interna apilada. Selección final = argmin conjunto (configuración, ronda)
  ⇒ **20 × 291 = 5.820 candidatos** por (objetivo, paquete, pliegue externo).
- **Por qué este presupuesto (decidido antes de mirar datos reales):** una prueba de tiempo con datos SINTÉTICOS con
  30 configuraciones × 500 rondas tardó ≈ 400 s por objetivo y bucle V1 con 12 países, con la máquina compartida (carga
  ≈ 100 por otros agentes); con 18 países y 20 réplicas placebo × 3 objetivos serían > 12 h. Se recortó a 20 × 300 y
  R = 10 réplicas (≈ 3 h).
- Fijos: `binary:logistic`, `hist`, `max_bin 64`, `seed 20261030` (la de INT-13), `nthread 1`.

## 3. Validación anidada
- **Externo = INT-13:** V1 dejar un país fuera (18 pliegues; principal) y V2 temporal (entreno con objetivo ≤ 1989-12;
  prueba 1990-01 … 2004-12 − h). El pliegue externo de prueba nunca entra en la búsqueda.
- **Interno (solo con el entreno externo):**
  - V1: los 17 países de entreno en **3 grupos de países** (semilla fija por pliegue); validación = cada grupo.
  - V2: 2 cortes **walk-forward con embargo** dentro de ≤ 1989: entreno con objetivo ≤ 1974-12 → validación 1975-01 …;
    entreno con objetivo ≤ 1981-12 → validación 1982-01 … (siempre con objetivo ≤ 1989-12).
  - En cada pliegue interno la base logit se reajusta con su entreno (el margen nunca ve la validación).
- Con la configuración y ronda elegidas, reajuste con todo el entreno externo y predicción del pliegue externo.

## 4. Métricas e incertidumbre (las de INT-13)
Log-loss (principal), Brier, AUC, pendiente de calibración, sobre las predicciones externas apiladas; IC 95 % por
**bootstrap de bloques móviles de 24 meses** (todos los países del mes juntos), 1.000 réplicas, semilla 20261030;
p unilateral de mejora = 1 − Φ(−Δ̄/dt_boot) (`int13.comparar`).

## 5. Familias, placebo y regla de decisión (fijas)
- **F1 (21 pruebas):** `hpo_m` frente a `base`, m ∈ {P1…P6, combinación} × 3 objetivos, V1, **Holm-21**.
- **F2 (21 pruebas):** `hpo_m` frente a `def_m` (ganancia del ajuste), V1, **Holm-21**.
- Descriptivos: `hpo_m` frente a `lgt_m`; `def_m` y `lgt_m` frente a `base`; V2 para todo.
- **Placebo:** el objetivo se permuta **por bloques dentro de cada país** (las filas del país, en orden de fecha,
  con desplazamiento circular al azar, se cortan en bloques de 24 filas y se baraja el orden de los bloques; conserva
  eventos y persistencia por país, rompe rasgo → objetivo). Sobre cada objetivo permutado se repite **todo** el bucle
  anidado V1 (misma búsqueda, mismo presupuesto) y se guarda Δlog-loss de cada comparación y el "optimismo interno"
  (log-loss interna de INT-13 − la de la mejor configuración). Réplicas: **R = 10 por objetivo** (semillas
  20261104 + 1000·(k+1) + r). p placebo de rango = (1 + #{Δ_placebo ≤ Δ_real}) / (R + 1) (no baja de 1/11: descriptivo);
  **z placebo** = (Δ_real − media placebo) / dt placebo (decide).
- **"Destaca" (y solo entonces se propone una configuración)** para (objetivo, m) si se cumplen TODAS:
  1. regla de INT-13 sobre `hpo_m` frente a `base`: Holm-21 (F1) rechaza en V1, Δ V2 < 0, pendiente de calibración V1
     en [0,5; 1,5];
  2. el ajuste aporta: Holm-21 (F2) rechaza en V1, **z placebo de `hpo_m − def_m` ≤ −1,645** (la ganancia real del ajuste queda
     ≥ 1,645 dt por debajo de la que la misma búsqueda logra con el objetivo permutado) y Δ(hpo − def) V2 < 0.
  Además se informa (no decide) si `hpo_m` bate a `lgt_m`.
- Si algo destaca: la configuración a prerregistrar se elige con el mismo bucle interno (3 grupos de países) sobre TODA
  la muestra ≤ 2004 y se publica con sus parámetros y nº de árboles. Si nada destaca, se dice así.
- **Nº de pruebas que se registran:** 42 (F1 + F2) en V1, repetidas en V2 como filtro, cada una con 5.820 candidatos
  internos por pliegue; + 10 × 3 réplicas placebo del bucle completo. Entrada en `research/trial_log.md`.

## 6. Procedencia
Código y este plan commiteados antes de correr; el script exige árbol limpio, se niega a repetir la parte real si ya
existe `real.json`; las réplicas placebo (deterministas) se reanudan si se cortan, solo con el mismo commit y sin cambios
fuera de la carpeta de salida.

---

## 7. Resultado (redactado DESPUÉS de la corrida; no cambia ninguna regla de §1-§6)
Corrida única: commit `73664ae` (árbol limpio, 2026-11-04T14:19Z); parte real 6.292 s, 10 réplicas placebo × 3
objetivos (máquina compartida con carga 100-265). Detalle completo: `research/int/hpo_int13/resultado.md`; todas las
pruebas internas (324 búsquedas × 20 configuraciones = 6.480 filas, cada una con su mejor ronda) en
`pruebas_internas.jsonl`; predicciones externas en `pred_*.csv.gz`. La base (logit curva) reproduce INT-13 (log-loss
V1 E1_12 0,2520); el XGBoost por defecto difiere en la 4.ª cifra (p. ej. P3 E1_12 −0,0377 frente a −0,0372), coherente
con la revisión OCDE del 2-nov.

### 7.1 Resultado anidado (Δlog-loss, V1 dejar un país fuera [IC 95 % bloques 24 m] · V2 1990-2004)
| objetivo · modelo | hpo − base | hpo − def (ganancia del ajuste) | z placebo | hpo − logit mismo paquete |
|---|---|---|---|---|
| E1_12 · P3 actividad | −0,035 [−0,063; −0,012] · V2 −0,028 | **+0,003** [−0,001; +0,006] · V2 +0,001 | +3,0 | 0,000 · V2 −0,016 |
| E1_12 · combinación | −0,041 [−0,063; −0,027] · V2 −0,017 | **+0,003** [+0,001; +0,005] · V2 +0,002 | +4,2 | +0,003 · V2 +0,008 |
| E1_12 · P6 global | −0,050 · V2 +0,002 | −0,003 [−0,009; +0,002] · V2 −0,019 | +1,0 | −0,011 · V2 −0,034 |
| E2 · P6 global | −0,072 [−0,122; −0,033] · V2 −0,013 | **−0,018** [−0,029; −0,008] · V2 −0,006 | **−5,7** | −0,044 · V2 **+0,057** |
| E2 · P3 actividad | −0,042 · V2 −0,082 | +0,002 · V2 +0,001 | +2,2 | −0,014 · V2 −0,038 |
| E3 · P6 global | −0,098 [−0,151; −0,053] · V2 −0,021 | −0,041 [−0,067; −0,022] · V2 **+0,016** | −17,2 | −0,070 · V2 −0,001 |
| E3 · P4 precios | −0,044 · V2 +0,024 | −0,013 [−0,020; −0,004] · V2 +0,005 | −2,0 | −0,025 · V2 +0,027 |
| E3 · combinación | −0,061 · V2 −0,006 | −0,016 [−0,024; −0,009] · V2 **+0,014** | −12,6 | −0,030 · V2 +0,019 |

(Resto de filas en el resultado: en ninguna otra el ajuste mejora a INT-13 con Holm-21.)

### 7.2 Placebo: cuánto "gana" la búsqueda por azar
Con el objetivo permutado, la búsqueda mejora al XGBoost por defecto en **−0,003 a −0,012 nats** (V1) y su optimismo
interno es de +0,007 a +0,016: el defecto de INT-13 sobreajusta un poco el ruido y la búsqueda lo corrige eligiendo
modelos más prudentes. Ese es el listón de ruido. Frente a él, la ganancia **real** del ajuste es **menor** que la del
placebo (z > 0) en casi todo, y en particular en **todo E1_12** (P3 actividad: +0,003 real frente a −0,009 placebo): en
recesión el defecto de INT-13 ya estaba en el punto bueno y ajustar no añade nada. Solo P6 global (E2, E3), P4 precios
(E3) y las combinaciones de E2/E3 ganan más que el placebo en V1, y casi siempre con la misma configuración (nº 10:
**max_depth 6**, min_child_weight 3, η 0,04: árboles profundos sobre rasgos globales).

### 7.3 Conclusión
- **Pregunta clave — no para recesión.** En E1_12 el XGBoost ajustado no bate al XGBoost de INT-13 (empeora +0,003)
  ni al **logit con los mismos rasgos de actividad** (Δ 0,000 en V1; el logit es mejor en V2, −0,016). La ventaja frente
  a la curva (≈ −0,035 nats, AUC 0,82 frente a 0,66) es **de la información (actividad), no del boosting ni del
  ajuste**. Esto apoya la forma del prerregistro E1 (logit actividad frente a logit curva) y desaconseja meter XGBoost
  ajustado en E1.
- **Inflación y tipos:** el ajuste solo "supera al placebo" con P6 global, eligiendo árboles profundos. Es el patrón de
  "aprender el calendario" del ciclo común que ya advertía INT-13 (dejar un país fuera deja las mismas fechas de los
  otros 17): **no se sostiene en V2** en E3 (+0,016) y en E2 la mejora V2 es pequeña (−0,006, IC que cruza 0 de sobra),
  la pendiente de calibración V2 es 5,3 y el logit con los mismos rasgos le gana en V2 por +0,057.
- **Regla §5:** destaca mecánicamente **una** fila, **E2 · P6 global** (Holm F1 0,021; Holm F2 0,007; z placebo −5,7;
  V2 −0,006; pendiente V1 1,04). Por regla se publica su configuración (búsqueda interna sobre toda la muestra ≤ 2004):
  `eta 0,0378, max_depth 6, min_child_weight 3,02, subsample 0,849, colsample_bytree 0,670, lambda 8,25, alpha 0,
  115 árboles` (+ monotonía de INT-13, `base_margin` = logit ipc_yoy + d12_ipc). **Recomendación (juicio, no regla):
  no prerregistrarla todavía**: V2 apenas la apoya, pierde contra un logit con los mismos rasgos fuera de la muestra
  temporal y su mecanismo plausible es una fuga de calendario entre países. Si se quisiera probar, el prerregistro
  debería ser temporal (no LOCO) y compararla con el logit P6.
- **Contaminación:** 42 pruebas externas (F1 + F2) × 5.820 candidatos internos por pliegue + 30 réplicas placebo,
  sobre los mismos datos ≤ 2004 que INT-13 y que el desarrollo de E1. Anotado en `research/trial_log.md`.

_Exploratorio: cualquier hallazgo necesita prerregistro y confirmación en vivo o en el bloqueado._
