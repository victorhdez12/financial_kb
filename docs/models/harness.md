---
documento: arnés de backtest walk-forward (Fase 3, entregable 3)
version: 1.0 (candidato; pendiente del Validador)
fecha: 2026-10-16
codigo: src/models/{harness,pit_labels,vault,metrics,base,trials}.py
config: config/harness/baselines_v1.yaml
tests: tests/test_harness.py (18 tests; 115 en toda la suite)
datos: solo ≤ 2004-12 (periodo bloqueado 2005-01 → INTOCABLE)
depende_de: etiqueta v1.1 (tag label-v1.1), base PIT v0.3 (tag pit-v0.3)
---

# Arnés de backtest walk-forward (nowcast de régimen EE. UU.)

El arnés es la única vía por la que un modelo se entrena y se puntúa. Hace cumplir las reglas de `docs/PLAN.md`
("Validación", "Regla de admisión", "Periodo bloqueado y reglas del arnés"), de la ficha de la etiqueta (§7 y §12) y
de la base PIT (`pit_base.md` §3). Todavía **no hay modelos aspirantes**: se entrega con dos baselines (persistencia
PIT y climatología) para demostrar que funciona.

```bash
.venv/bin/python -m src.models.harness --config config/harness/baselines_v1.yaml   # ~1-2 min; solo ≤ 2004
.venv/bin/python -m pytest -q tests/test_harness.py                                 # 18 tests, ~2 min
```

## 1. Piezas

| fichero | qué hace |
|---|---|
| `src/models/harness.py` | Configuración (`HarnessConfig`), datos (`PITData`; `ArrayData` para placebo y tests), selección de variables, walk-forward, puntuación, informe, placebo (`placebo_data`), estabilidad a ambos lados de los saltos (`vintage_breaks`, `sign_stability`), CLI |
| `src/models/pit_labels.py` | `PITLabeler`: la etiqueta v1.1 **completa recalculada con los datos conocidos en T** (mismo cálculo que `pit.persistence`) |
| `src/models/vault.py` | `LabelVault`: única puerta a la etiqueta oficial; periodo bloqueado; registro de accesos |
| `src/models/metrics.py` | log-loss blanda, Brier, BSS, acierto, bootstrap por bloques, episodios |
| `src/models/base.py` | Interfaz `Model` (fit / predict_proba) y baselines (`PersistencePIT`, `Climatology`) |
| `src/models/trials.py` | Registro automático de pruebas (`research/trials/harness_runs.jsonl` + fila en `research/trial_log.md` + artefactos en `FIN_DATA_ROOT/models/runs/<run_id>/`) |

## 2. Cortes walk-forward, embargo y purga

- **Ventana expansiva.** Primer mes de prueba `test_start` (por defecto 1956-10, el primero de la persistencia PIT
  común a los dos modos), último `test_end` (≤ 2004-12 en desarrollo).
- **Reentreno cada `refit_every` meses** (1 = mensual). En el corte de mes m0 (fecha de decisión T0 = último día hábil
  de m0) se entrena una vez y se predicen m0 … m0 + k − 1, cada mes con las variables de **su** fecha de decisión
  (que es ≥ T0; usa solo lo publicado en ella).
- **Embargo:** solo entrenan los meses s ≤ m0 − `embargo_months`. Mínimo 6 (ficha §7); un valor menor se rechaza.
- **Purga:** la ventana de la etiqueta de s llega a s + 4 (`LABEL_FORWARD = pace_need`); el arnés comprueba en cada
  corte que s + 4 < m0 (con el embargo de 6 sobra un margen de 2 meses). Además, como las etiquetas de entrenamiento se
  recalculan con datos ≤ T0 (§3), ninguna lleva información posterior a T0: la purga clásica (etiquetas que
  solapan con el periodo de prueba) queda cubierta por construcción.
- **Meses que no entrenan ni puntúan:** `weight = 0` (1950-1954) y los provisionales oficiales (desde
  `last − 53` del meta de la etiqueta: 2021-11; todos dentro del periodo bloqueado).
- **Muestra mínima:** un modelo con entrenamiento no predice en un corte con menos de `min_train_months` meses.

## 3. Etiqueta de entrenamiento recalculada con datos ≤ T

`PITLabeler(mode).at(T)` reconstruye la etiqueta v1.1 entera (G, I, `p_*`, `label_hard`, `weight`) con los niveles
conocidos en T, desde las instantáneas congeladas de la etiqueta (`R.FROZEN`) y de la base PIT (`P.FROZEN`, para el
calendario), con s_G, s_I y el empalme de `P.label_params` (hash del meta fijado):

- `vintage`: las series tal como se publicaron en T; fuera del archivo de vintages, la última vintage truncada por fecha
  de publicación;
- `latest_truncated`: la última vintage truncada por fecha de publicación.

Es el **mismo bucle** que `src.features.pit.persistence`; la diferencia es que devuelve la etiqueta entera y no solo su
última fila. La última fila es la persistencia PIT: un test comprueba que coincide **bit a bit** con los baselines
congelados de la v0.3 (los 579 meses ≤ 2004 de cada modo). El resto de filas son las **etiquetas de entrenamiento**
del corte: tendencia (±60 m) y σᵢ calculadas solo con los datos hasta T. La etiqueta final precalculada **nunca** entra
en `fit`: un test espía comprueba en 8 cortes (1978-1985) que lo que recibe el modelo es `at(T)` y que difiere de la
etiqueta oficial.

## 4. Periodo bloqueado 2005-01 → INTOCABLE

- **Caja fuerte (`LabelVault`).** En `development` la etiqueta oficial se lee con un filtro de pyarrow
  `date < 2005-01-01`: las filas ≥ 2005 **no se decodifican** (un test intercepta la lectura y comprueba el filtro).
  Antes se verifica el SHA-256 del fichero (bytes, sin decodificar) y después el hash de contenido de las 660 filas
  ≤ 2004 (los dos fijados en git). Pedir cualquier mes ≥ 2005-01 lanza `HoldoutLocked`.
- **Variables:** las matrices PIT se leen con el mismo filtro (`decision_date < 2005-01-01`).
- **Arnés:** `test_end` ≥ 2005-01 o un corte ≥ 2005-01 lanzan `HoldoutLocked` antes de cargar nada.
- **Registro de accesos:** cada lectura concedida o denegada añade una línea a `research/trials/label_access.jsonl`
  (fecha, commit, llamador, modo, preregistro, rango).
- **Evaluación única (`phase: holdout_evaluation`), NO ejecutada.** Exige, en este orden, antes de leer nada:
  1. `prereg_id` que exista en `research/hypotheses.yaml` con estado "preregistrada";
  2. la variable de entorno `FKB_HOLDOUT_UNLOCK = "EVALUACION-UNICA <prereg_id>"` (confirmación explícita del usuario);
  3. el árbol de git limpio (el código evaluado es el commiteado);
  4. que ese preregistro no se haya evaluado antes: el consumo se anota en `research/trials/holdout_evaluations.jsonl`
     **antes** de leer, así que un fallo a mitad también gasta la evaluación.
  Los tests prueban las negativas y el camino de desbloqueo **sobre una etiqueta sintética** (nunca la oficial),
  incluida la negativa del segundo intento.
- **Límite declarado:** la barrera es del arnés. Cualquier script que lea `regime_us_v1.1.parquet` directamente (por
  ejemplo `pit.score_training`, `src/labels/checks.py` o los tests de la etiqueta) ve el fichero completo. La regla
  sigue siendo de proceso: todo lo que puntúe un modelo pasa por el arnés.

## 5. Variables y modelos

- **Solo la matriz PIT congelada v0.3**: el arnés comprueba el SHA-256 de la matriz (fijado en git), que sus columnas
  sean exactamente las públicas de la lista blanca congelada y llama a `assert_no_forbidden` al cargar y **antes de cada
  `fit`**. Un modelo pide variables **por nombre**; un nombre fuera de la matriz (`label_hard`, `usrec`, `G`, cualquier
  columna nueva) da `KeyError`. No hay forma de pasarle columnas propias a `PITData`.
- **Política `principal`** (por defecto): estados `principal` y `principal_epoca`; cada columna solo desde
  `max(primer dato, desde, principal_desde_efectivo)` (este último con la herencia de `P.effective_principal_desde`).
  `condicional` y `modulo_adicional` no entran (pedirlas explícitamente da error). **Política `sensibilidad`**: añade
  las condicionales e ignora `principal_desde`.
- **Épocas:** en cada corte una columna entra si tiene ≥ `min_train_months` meses de entrenamiento desde su inicio; la
  ventana de entrenamiento empieza en el inicio más tardío de las columnas usadas (modelo por época) y solo usa filas
  completas. Nunca se usa "dato presente / ausente" como señal. Un hueco en el mes de prueba se imputa con la media del
  entrenamiento (se cuenta en el diagnóstico).
- **Persistencia como entrada:** un modelo con `uses_persistence = True` recibe `pers_*` (la persistencia PIT de cada
  mes, calculada en su fecha de decisión). Son predicciones PIT, no columnas de la etiqueta.
- **Interfaz** (`src/models/base.py`): `fit(X, Y, y, info)` con `Y` = probabilidades blandas de la etiqueta
  recalculada (n × 4) e `y` = etiqueta dura; `predict_proba(X, info)` → n × 4. Opcional `coefficients()` → dict, que el
  arnés guarda por corte para la regla de estabilidad (`sign_stability` frente a los saltos de `vintage_breaks`:
  `vintage_desde` de cada columna y los saltos de composición de `growth_rt` en 1973-04 y 1981-05). Para enchufar
  logística, Markov, GBM o calibración: subclase + registro en `REGISTRY`.
- **Sensibilidades preregistradas:** `matrix_variant: filadelfia_prudente` (S-PIT-001, solo vintage). S-PIT-002
  (Michigan en Δ12m) es una transformación del modelo, no de la matriz: se hará en el modelo principal.

## 6. Puntuación y métricas

- Contra la etiqueta **oficial congelada v1.1** (caja fuerte), meses con `weight > 0`, no provisionales y ≤ `test_end`.
- **Mismos meses para todo:** la muestra es la intersección de los meses puntuados de **todos** los modelos en
  **los dos modos** (`vintage` principal, `latest_truncated` sensibilidad).
- Probabilidades recortadas a 1e-4 y renormalizadas (como `pit.score_training`).
- **log-loss blanda** (principal) = −Σ T_q log P_q frente a `p_*` oficiales; **Brier** blando = Σ (P_q − T_q)²;
  **BSS** = 1 − ΣBrier / ΣBrier de la persistencia del mismo modo; **acierto** = argmax frente a `label_hard`.
- **Diferencias frente al baseline** (persistencia PIT del mismo modo) mes a mes, con **bootstrap por bloques circular
  de 12 meses, 5.000 réplicas, semilla 20261015, IC percentil al 95 %** y p unilateral = proporción de réplicas ≤ 0
  (los mismos parámetros que la adenda P-EVAL-MOD).
- **Por década** (métricas y mejora frente al baseline) y **por episodio**, contando episodios y no meses. Episodios
  fijados a priori (antes de ver resultados): (a) cada recesión NBER (`usrec` oficial) ± 6 meses; (b) cada racha de la
  etiqueta dura oficial. Se informa en cuántos gana el modelo al baseline.
- **Sensibilidad de modo:** diferencia de log-loss latest_truncated − vintage del mismo modelo, con IC.

## 7. Registro de pruebas

Cada corrida (también las de placebo) añade una línea a `research/trials/harness_runs.jsonl`: `run_id`, fecha, quién,
fase, `kind` (`pit` = evidencia; `placebo`/`synthetic` = pruebas de la tubería), configuración completa, hash del
código (`src/models/*.py` y, aparte, de la etiqueta/base PIT/calendario) con commit y si estaba sucio, hashes de datos
(matriz, instantáneas, etiqueta), **hash de resultados** (predicciones + informe) y métricas. Además escribe una fila
en `research/trial_log.md` y guarda predicciones, puntuaciones e informe en `FIN_DATA_ROOT/models/runs/<run_id>/`.
Los tests redirigen todo a un directorio temporal (`FKB_TRIALS_DIR`, `FKB_RUNS_DIR`, `FKB_TRIAL_LOG`).

## 8. Baselines mínimos (≤ 2004)

Corrida registrada `20261016-092402_baselines_v1_27cae755` con `config/harness/baselines_v1.yaml` (refit mensual,
embargo 6, 579 meses comunes 1956-10 → 2004-12; hash de resultados `27cae755…`; detalle en
`research/trials/harness_runs.jsonl`). La corrida anterior `20261016-091604_…` (mismo hash de resultados) se hizo
antes de corregir la apertura única de la caja fuerte en la evaluación única; se conserva en el registro.

| modo | modelo | acierto | log-loss blanda | Brier | mejora de log-loss frente a la persistencia [IC 95 %] | BSS [IC 95 %] |
|---|---|---|---|---|---|---|
| vintage | **persistencia PIT** | **61,14 %** | **1,2997** | 0,3702 | — | — |
| vintage | climatología | 28,67 % | 1,4151 | 0,5425 | −0,115 [−0,331; +0,136] | −0,465 [−0,798; −0,214] |
| latest_truncated | **persistencia PIT** | **63,04 %** | **1,1824** | 0,3119 | — | — |
| latest_truncated | climatología | 27,98 % | 1,4124 | 0,5416 | −0,230 [−0,460; +0,034] | −0,736 [−1,229; −0,389] |

- **El listón se reproduce exactamente** (vintage 61,14 % / 1,2997; latest_truncated 63,04 % / 1,1824; 579 meses),
  en la muestra completa de la persistencia y en la muestra común del walk-forward. **No hay diferencia por embargo ni
  por muestra**: la persistencia no entrena, y con `min_train_months = 12` la climatología tiene predicción desde
  1956-10 (16 meses de etiqueta recalculada 1955-01 → 1956-04), así que la muestra común es la misma de 579 meses.
- La climatología es claramente peor en Brier y acierto; en log-loss el IC incluye el cero en vintage porque la
  persistencia se equivoca con confianza en los giros (en los años 50 la climatología gana: +1,11 nats en vintage,
  +1,26 en latest_truncated; pierde en todas las demás décadas). Por episodios gana en 4 de 8 recesiones (± 6 m) y en
  30 de 61 rachas de régimen. Es el patrón esperado de un baseline sin información.
- **Sensibilidad de modo:** la persistencia es 0,117 nats mejor en latest_truncated que en vintage [IC 0,043; 0,192]:
  el coste de usar los datos tal como se publicaron. La climatología apenas cambia (+0,003 [−0,001; +0,008]).
- **Clasificador de reglas actual (`src/regime/`): no incluido.** No es "fácil de hacer PIT" de forma coherente con la
  v0.3: (1) usa su propio calendario de publicación (`src/regime/asof.PUB_LAG`), no el calendario validado de la base
  PIT; (2) su eje I usa el IPC subyacente antes de 1978 y el PCE subyacente antes de 2000, que en la v0.3 son
  **condicionales** (no existían en tiempo real); (3) lee el warehouse vivo, no una instantánea congelada; (4) da un
  cuadrante duro sin probabilidades (haría falta calibrarlo con la etiqueta recalculada, lo que ya es un modelo).
  Propuesta para el entregable (4): reescribir sus reglas como un `Model` sobre columnas de la matriz v0.3 (Sahm,
  `growth_rt_state`, `core_cpi_6m_ann` desde 1978…) con una calibración de Dirichlet de su salida, y tratarlo como un
  baseline más.

## 9. Tests (`tests/test_harness.py`, 18)

| grupo | qué comprueba |
|---|---|
| listón | persistencia del arnés = baselines congelados v0.3 bit a bit (2 modos); métricas = 61,14 % / 1,2997 y 63,04 % / 1,1824 en 579 meses; los dos modos se puntúan sobre los mismos meses y nada ≥ 2005 |
| fuga de etiqueta | (i) en 8 cortes el `fit` recibe exactamente `PITLabeler.at(T)` (≠ etiqueta final) y nada posterior a T − 6; (ii) `label_hard`, `p_expansion`, `usrec`, `G` o una columna inventada no pueden entrar (`KeyError`); `assert_no_forbidden` rechaza derivadas; `ArrayData` no puede hacerse pasar por PIT; (iii) una matriz alterada (columna añadida) no pasa el hash; (iv) **señal plantada con la etiqueta futura** (objetivo de t + 1 + ruido) en el placebo: habilidad +0,21 / +0,30 / +0,31 nats > 0,10 → detectada |
| placebo | etiqueta ≤ 2004 **barajada en bloques de 24 meses**, logística de prueba con las 8 variables a priori del placebo de la base PIT + persistencia del objetivo, refit anual 1975-2004: habilidad −0,28 / −0,17 / −0,05 nats < 0,02 → sin habilidad |
| embargo | embargo < 6 rechazado; con 9, el último mes de entrenamiento es exactamente m0 − 9 en todos los cortes |
| reentreno | con `refit_every = 6`, un modelo por corte y predicciones solo de m0 … m0 + 5 |
| variables | política principal: nunca condicionales ni módulos; ninguna columna antes de su `principal_desde_efectivo` (IPC subyacente y `infl_energy_pressure` fuera en 1975, dentro en 1990; `tcu_gap` dentro en 1990; VIX fuera); pedir una condicional da error; con `sensibilidad`, sí |
| estabilidad | `vintage_breaks` y `sign_stability` detectan un cambio de signo en un salto (datos sintéticos) |
| reproducibilidad | misma config → mismo hash de resultados (dos corridas desde cero); otra config → otro hash |
| registro | entrada en `harness_runs.jsonl` con hashes, fila en el trial log y artefactos |
| periodo bloqueado | la caja fuerte lee con el filtro `date < 2005-01` (660 filas), deniega 2005-01 y 2015-06 y lo registra; el arnés rechaza `test_end` y cortes ≥ 2005; la evaluación única se niega sin preregistro, con uno inexistente o sin la confirmación, y el desbloqueo (sobre una etiqueta sintética) es de un solo uso; en una corrida de evaluación única la caja fuerte se abre **una sola vez** y la comparten los dos modos (con dobles de prueba, sin leer datos) |

Umbrales de los tests de placebo y fuga fijados **antes** de correrlos: tolerancia del placebo 0,02 nats
(`PLACEBO_TOL` de la base PIT) y umbral de detección de la fuga 0,10 nats.

## 10. Decisiones pendientes (usuario)

1. **Meses "provisionales" de la etiqueta recalculada.** La etiqueta recalculada en T marca como provisionales sus
   últimos 54 meses (ficha §7). Por defecto **entrenan** (`exclude_recomputed_provisional: false`): si no, la etiqueta
   de entrenamiento terminaría en T − 59 y el modelo aprendería con 5 años de retraso. Son etiquetas con más ruido
   (concordancia < 95 % en el estudio de revisión). Alternativas: excluirlas, o ponderarlas por madurez.
2. **Preregistro de la evaluación única del modelo principal.** P-EVAL-MOD solo cubre los módulos H-MOD. Falta un
   preregistro (p. ej. `P-EVAL-BASE`) del criterio principal (bate a la persistencia en log-loss con IC que excluye el
   cero, en vintage; latest_truncated como sensibilidad; estabilidad 2005-14 frente a 2015+). La caja fuerte gasta
   cada `prereg_id` en una sola corrida, así que todo lo que se evalúe con un preregistro va en la misma corrida.
3. **Episodios** (recesiones NBER ± 6 meses y rachas de la etiqueta dura): confirmar la definición.
4. **`min_train_months` de los modelos con variables:** 12 en los baselines; se propone 120 para logística/GBM.
5. **Clasificador de reglas** (§8): ¿reescribirlo sobre la matriz v0.3 como baseline del entregable (4)?
