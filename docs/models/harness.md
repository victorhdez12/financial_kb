---
documento: arnés de backtest walk-forward (Fase 3, entregable 3)
version: 2.0 (candidato; pendiente de la re-auditoría del Validador)
fecha: 2026-10-16
codigo: src/models/{harness,pit_labels,vault,metrics,base,trials,placebo}.py
config: config/harness/baselines_v2.yaml (v1: baselines_v1.yaml, histórica)
tests: tests/test_harness.py (17) + tests/test_harness_v2.py (30); suite completa: ver §9
datos: solo ≤ 2004-12 (periodo bloqueado 2005-01 → INTOCABLE)
depende_de: etiqueta v1.1 (tag label-v1.1; adenda de uso 2026-10-16), base PIT v0.3 (tag pit-v0.3)
revisiones: docs/validation/2026-10-16_harness_v1.md (⚠️), docs/reviews/2026-10-16_estratega_macro_harness.md (⚠️)
---

# Arnés de backtest walk-forward (nowcast de régimen EE. UU.)

El arnés es la única vía por la que un modelo se entrena y se puntúa. Hace cumplir las reglas de `docs/PLAN.md`
("Validación", "Regla de admisión", "Periodo bloqueado y reglas del arnés"), de la ficha de la etiqueta (§7, §12 y la
adenda del 2026-10-16) y de la base PIT (`pit_base.md` §3). Todavía **no hay modelos aspirantes con variables**: se
entrega con la persistencia cruda, la climatología y **M0, la persistencia calibrada**, que es el listón principal.

```bash
.venv/bin/python -m src.models.harness --config config/harness/baselines_v2.yaml --official   # ≤ 2004; código commiteado
.venv/bin/python -m src.models.placebo <salida.json>                                        # tabla de potencia (§9b)
.venv/bin/python -m pytest -q tests/test_harness.py tests/test_harness_v2.py
```

## 1. Piezas

| fichero | qué hace |
|---|---|
| `src/models/harness.py` | Configuración (`HarnessConfig`), datos (`PITData`; `ArrayData` para placebo y tests), pesos de madurez, ventanas por eje y mínimos de entrenamiento, walk-forward, puntuación en ventana fija, informe con cortes, `run()` (desarrollo) y **`evaluate_holdout()` (único punto de entrada de la evaluación única)**, CLI |
| `src/models/pit_labels.py` | `PITLabeler`: la etiqueta v1.1 completa recalculada con los datos conocidos en T; **barrera** para T ≥ 2005-01 |
| `src/models/vault.py` | `LabelVault`: única puerta a la etiqueta oficial; desbloqueo con consumo commiteado en git; registros de accesos |
| `src/models/metrics.py` | log-loss blanda y binaria por eje, Brier, BSS, acierto, bootstrap (12 y 24 m), Holm, prueba de signo, calibración, cortes, episodios, detección de giros |
| `src/models/base.py` | Interfaz `Model` (con `sample_weight`), `AxisModel` (un modelo por eje), baselines: `PersistencePIT`, `Climatology`, `CalibratedPersistence` (M0) |
| `src/models/placebo.py` | Placebo pareado y tabla de potencia |
| `src/models/trials.py` | Registro automático de pruebas |
| `research/holdout/evaluations.jsonl` | Registro de consumo de la evaluación única (ruta fija, versionado en git; hoy vacío) |

## 2. Cortes walk-forward, embargo y purga

Sin cambios respecto a la v1:
- ventana expansiva;
- reentreno cada `refit_every` meses;
- embargo ≥ 6 (s ≤ m0 − 6);
- purga comprobada en cada corte (s + 4 < m0);
- `weight = 0` y provisionales oficiales nunca entrenan ni puntúan.

## 3. Etiqueta de entrenamiento recalculada con datos ≤ T

Sin cambios respecto a la v1 (`PITLabeler.at(T)`, mismo bucle que `pit.persistence`; la última fila coincide bit a bit
con los baselines congelados).

**Constantes de definición (Validador B-6).** s_G = 0,40, s_I = 0,31 y el empalme IPC → PCE (+0,204 pp) son
constantes de muestra completa que entran en todas las etiquetas recalculadas. Forman parte de la definición
congelada del objetivo (ficha §11), no son resultados del periodo bloqueado. Por eso la etiqueta recalculada es "con
datos ≤ T" en sus niveles, ventanas, tendencia y σᵢ, pero **no** es "100 % PIT" en esas tres constantes.

### 3b. Peso de madurez de los provisionales recalculados (M-4; decisión del usuario 2026-10-16)

La etiqueta recalculada en T marca como provisionales sus últimos 54 meses. Antes de la v2 entrenaban con peso 1, en
contra del texto de la ficha. Ahora entrenan con un **peso de madurez** w(k), fijado **a priori**: se escribió antes de
correr ningún modelo con variables y sale del estudio de revisión congelado (`label_revision_study.md`), no de la tabla
del Validador ni de ningún resultado del arnés.

- c(k) = mínimo de la concordancia de la etiqueta dura de las variantes A y B del estudio en cada k de su tabla.
- c̃(k) = min{c(k′): k′ ≥ k}: envolvente inferior monótona; un k suelto con buena concordancia por azar no gana peso.
- w(k) = c̃(k) / c̃(60), con c̃(60) = 97 % (la concordancia madura). Los meses no provisionales tienen w = 1.
- k es la distancia en meses entre el corte y el mes objetivo, con la convención del estudio (su última fila es
  k = 4; la de `at(T)` es m0 − 5, así que k = (m0 − s) − 1).

| k (estudio) | ≤ 12 | 13-42 | 43-48 | 49-54 | 55 | ≥ 56 |
|---|---|---|---|---|---|---|
| w | 0,858 | 0,897 | 0,928 | 0,969 | 0,979 | 1 |

**Por qué esta función.**
- Es la probabilidad (relativa a la madurez) de que la etiqueta dura del mes no cambie al madurar. Un mes con un 14 %
  de probabilidad de estar mal etiquetado pesa un 14 % menos.
- El peso 0,5 del Estratega era una regla simple, pero arbitraria. El usuario pidió una función derivada del estudio.
- La envolvente usa la variante más conservadora y no premia picos aislados de la tabla.

**Sensibilidades preregistradas:** `provisional_weighting: uno` y `excluir`. Se publican siempre, nunca para elegir
después. Afecta a todos los modelos que entrenan (climatología y M0 incluidos) mediante `sample_weight`.

**Enmienda de la ficha:** adenda fechada en la ficha §7 y §12. La etiqueta v1.1, sus hashes y la puntuación no cambian.

## 4. Periodo bloqueado 2005-01 → INTOCABLE

### 4a. Desarrollo

- **Caja fuerte (`LabelVault`).** En `development` lee la etiqueta oficial con el filtro de pyarrow
  `date < 2005-01-01`: las filas ≥ 2005 no se decodifican.
  - Antes de leer comprueba el SHA-256 del fichero; después, el hash de contenido de las 660 filas ≤ 2004.
  - `limit` es una **propiedad de solo lectura**: `v.limit = None` lanza `AttributeError` (D1).
- **Variables:** las matrices se leen con el mismo filtro (`decision_date < 2005-01-01`).
- **Arnés:**
  - `run()` **solo** trabaja en `development`;
  - un `test_end`, una `eval_window` o un corte ≥ 2005-01 lanzan `HoldoutLocked`;
  - `ArrayData.phase` es de solo lectura y siempre vale `development`.
- **`PITLabeler.at(T ≥ 2005-01)`** (M-1/D4) lanza `HoldoutLocked` y lo registra, salvo con la caja desbloqueada de la
  evaluación única (identidad, no duck typing).
- **`pit.score_training`** (M-1/D5) lee con el filtro `date < 2005-01` y exige `end < 2005-01` (antes `<=`).
  - El cambio está en `src/features/pit.py` y **no cambia ningún fichero congelado** de la v0.3. Las matrices, los
    baselines y el meta no se regeneran.
  - Un test comprueba que `score_training` sobre los baselines congelados da exactamente lo que dice el meta congelado.

### 4b. La evaluación única (A-1)

**Un único punto de entrada: `harness.evaluate_holdout(prereg_id)`.**
- Lee la configuración que declara el propio preregistro (`config_arnes`, commiteada), con `phase: holdout_evaluation`
  y el mismo `prereg_id`.
- Crea **él mismo** la caja fuerte y los datos: no acepta `datas`, `registry` ni modelos externos.
- Ejecuta **una** corrida, siempre registrada, y cierra la caja al terminar. Una caja cerrada no lee, ni siquiera
  desde la caché.

**`LabelVault(mode="holdout_evaluation")` comprueba, antes de leer nada:**
1. **Solo identificadores de evaluación explícitos** (D9):
   - prefijo `P-EVAL-`;
   - `tipo: evaluacion_holdout`;
   - estado "preregistrada…".
   Hoy **ninguna** de las 13 hipótesis preregistradas lo cumple. P-EVAL-MOD y P-EVAL-S-PIT-002 no tienen `tipo` y no
   se editan: se evaluarán **dentro** de P-EVAL-BASE (`incluye`). Un test lo comprueba sobre el `hypotheses.yaml` real.
2. **Confirmación explícita:** `FKB_HOLDOUT_UNLOCK = "EVALUACION-UNICA <prereg_id>"`.
3. **Git falla cerrado** (D6):
   - git disponible;
   - `REPO` = raíz del repositorio;
   - árbol limpio, **incluidos los ficheros no rastreados**.
   Cualquier error de git (sin binario, fuera de un repo, `git archive`) = no hay evaluación.
4. **Registro de consumo en una ruta fija:** `research/holdout/evaluations.jsonl`, relativa al código. Ninguna
   variable de entorno la cambia; `FKB_TRIALS_DIR` ya no la toca (D2). Además:
   - debe estar rastreado por git y sin cambios respecto a HEAD;
   - ninguna línea de ningún commit anterior puede faltar (un id consumido no puede desaparecer, ni commiteando el
     borrado).
5. **No consumido:** ni el id ni ninguno de los que `incluye` se han consumido antes, tampoco como parte de otra
   evaluación.
6. **Una sola apertura por proceso.**

**Consumo antes de leer.** Si todo pasa, el consumo se **anota y se commitea** (solo ese fichero) antes de leer. Si el
commit falla, la caja no se abre y el id queda gastado. Un fallo posterior también gasta la evaluación.

**Datos de la evaluación (D3/D3b).**
- `PITData(phase="holdout_evaluation")` exige, **antes de leer nada**:
  - la caja creada por `evaluate_holdout` (identidad en `_ISSUED`);
  - **tipo exacto** `LabelVault`, desbloqueada y del mismo preregistro;
  - el contexto activo de `evaluate_holdout`.
- Un objeto con `.mode = "holdout_evaluation"`, una subclase o una caja de desarrollo dan `HoldoutLocked`/`TypeError`.
- `walk_forward` y `_run` rechazan cualquier dato que no sea `PITData` con esa caja.

**Tests.** Cada ataque del Validador v1 está reproducido en `tests/test_harness_v2.py` y ahora falla. Se usa un
repositorio git temporal con su `hypotheses.yaml` y su registro, y una etiqueta sintética 1990-2012; `R.out_path`
apunta a la sintética, de modo que ninguna vía puede tocar la oficial.

| ataque v1 | test v2 | resultado |
|---|---|---|
| D1 `limit = None` | `test_D1_limit_is_read_only_and_dev_filter_fixed` | `AttributeError`; el filtro de desarrollo no cambia |
| D2 redirigir `FKB_TRIALS_DIR` | `test_D2_trials_dir_redirect_does_not_reopen` | 3 intentos con 3 directorios: denegados |
| D2b borrar el consumo (sin commit / con commit / dejar de rastrear) | `test_registry_tampering_fails_closed` | denegado (árbol sucio / historial / no rastreado) |
| D3 `run(cfg, datas=…)` en holdout, ×3 | `test_D3_run_and_walk_forward_refuse_holdout` | `HoldoutLocked` en `run`, `walk_forward` y `_run` |
| D3b caja falsa (pato, subclase, de desarrollo, ninguna, real fuera de `evaluate_holdout`) | `test_D3b_pitdata_rejects_fake_vaults_before_reading` | denegado; 0 lecturas |
| D4 `PITLabeler.at(2010)` | `test_M1_pitlabeler_blocks_holdout` | `HoldoutLocked` + registro |
| D5 `score_training(end=2005-01)` | `test_M1_score_training_strict_and_unchanged` | `AssertionError`; resultado congelado intacto |
| D6 git: sin binario, fuera de repo, no rastreados | `test_D6_git_fails_closed` | denegado (falla cerrado) |
| D9 ids no de evaluación / borrador / sin tipo | `test_D9_only_explicit_evaluation_ids`, `test_D9_no_real_hypothesis_can_open_today` | denegados |
| id incluido en otra evaluación | `test_included_ids_are_consumed_too` | denegado |
| reapertura en el mismo proceso | `test_single_opening_per_process` | denegada |
| consumo antes de leer / fallo a mitad | `test_unlock_consumes_and_commits_before_read`, `test_failed_read_still_spends_the_evaluation` | anotado **y commiteado** antes de la lectura; un fallo lo gasta |
| caja reutilizada tras la corrida | `test_evaluate_holdout_single_entry_and_closes_vault` | cerrada; segundo `evaluate_holdout` denegado |

**Separación física del bloqueado: no se hace en la v2, y es una decisión, no un olvido.** Partir los ficheros en una
parte de desarrollo ≤ 2004 y otra cifrada (age/gpg) no protege nada mientras los ficheros completos sigan en disco
sin cifrar:
- la etiqueta v1.1, su instantánea de entradas, las matrices v0.3 y los baselines están **congelados** con sus SHA-256
  en git;
- cifrarlos o borrarlos cambiaría artefactos congelados y el archivo de datos, y eso está fuera del encargo;
- la instantánea de entradas de la etiqueta (niveles hasta 2026-09) permite además recalcular el bloqueado con
  `PITLabeler`: habría que cifrarla también.

Hacerlo bien es una operación del **usuario** (cifrar con su clave y retirar los originales legibles) y una versión
nueva de los artefactos. Lo propongo como decisión pendiente (§10). Mientras tanto la caja fuerte es
**anti-accidente, no anti-intención**: Python no tiene atributos privados (se puede fijar `_EVAL`, añadir una caja a
`_ISSUED` o reescribir el registro desde fuera de git), y las vías de §4c leen los ficheros completos.

### 4c. Vías restantes (declaradas) y cómo se controlan

| vía | qué ve | control |
|---|---|---|
| `regime_us_v1.1.parquet`, `regime_us_v1.0.parquet` (hasta 2026-04) leídos directamente | etiqueta del bloqueado | Norma: todo lo que puntúe un modelo pasa por la caja. Lectores directos conocidos: `src/labels/checks.py`, `tests/test_labels.py` (hash de integridad del fichero completo, sin relación con variables), validaciones antiguas del Validador. `pit.score_training` ya filtra (§4a) |
| `regime_us_v1.1_inputs.parquet` (niveles hasta 2026-09) | permite recalcular la etiqueta del bloqueado | `PITLabeler.at` bloquea T ≥ 2005 (§4a); `R.make_label` directo: norma |
| `baseline_persistence_v0.3_{vintage,latest_truncated}.parquet` (hasta 2026-09; `pers_*` de t es casi la etiqueta de t − 5) | casi la etiqueta del bloqueado | El arnés no los lee (recalcula la persistencia con `PITLabeler`). El test del listón los lee **con filtro** `decision_date < 2005`. Norma para el resto |
| Matrices v0.3 y sus `lineage` (variables hasta 2026-09) | variables del bloqueado (sin etiqueta) | `PITData` filtra en desarrollo. Mirar variables sin la etiqueta no evalúa nada, pero cualquier descriptivo ≥ 2005 se anota en el trial log |
| Figuras del Reportero (`src/report/fase3/make_figures*.py`): **dibujan la etiqueta hasta 2026-04** | la etiqueta del bloqueado, a la vista | Norma: ya están publicadas; no se superpone ninguna predicción de modelo sobre ≥ 2005. Propuesta: que las figuras nuevas recorten a ≤ 2004 o se marquen "solo etiqueta" |
| Python dentro del proceso (`_EVAL`, `_ISSUED`, `_PROCESS`, monkeypatch) | todo | Norma; separación física como solución de fondo (§10) |

### 4d. Registro de accesos

- **Registro completo** en una ruta fija, fuera de git: `research/trials/full/label_access.jsonl`. Recoge todos los
  intentos de la caja y del `PITLabeler`, concedidos, denegados o servidos **desde la caché**. Cada línea lleva proceso,
  llamador, commit, test de pytest si lo hay y el `FKB_TRIALS_DIR` vigente. Así los tests y las exploratorias también
  dejan rastro (B-3).
- **Registro versionado** `<trials>/label_access.jsonl`: las aperturas reales del fichero (como en la v1).
- Una corrida con `record=False` deja una línea mínima en `research/trials/full/harness_runs_unrecorded.jsonl`.

## 5. Variables y modelos

- **Solo la matriz PIT congelada v0.3:** SHA-256 fijado, columnas = lista blanca pública, `assert_no_forbidden` al
  cargar y antes de cada `fit`. Un nombre fuera de la matriz da `KeyError`.
- **Política `principal`** (por defecto) o `sensibilidad`, como en la v1.
- **Interfaz:**
  - `Model.fit(X, Y, y, info, sample_weight=None)`. `sample_weight` es el peso de madurez (§3b) multiplicado por
    `weight`.
  - Con `uses_persistence`, el modelo recibe `pers_*` (blanda) y `pers_hard_*` (one-hot de la dura).
- **`AxisModel` (M-2; decisión del usuario):** un modelo por eje.
  - Cada eje declara **sus** variables por nombre (`axis_features = {"G": (...), "I": (...)}`) y entrena con el
    objetivo blando del eje (`p_g_high` / `p_i_high` de la etiqueta recalculada) y los pesos de madurez.
  - Su **ventana es fija**: empieza en el inicio más tardío de **sus** variables (`colinfo.start`, que ya incluye
    `principal_desde_efectivo`) y no depende del otro eje. Ejemplo: el eje G no pierde 1964-77 porque el eje I use el
    IPC subyacente (`test_M2_axis_windows_independent_and_minimums`).
  - Con `uses_persistence`, cada eje recibe `pers_axis_growth` / `pers_axis_infl` (P(eje alto) de la persistencia PIT).
- **Política de épocas de la v1 (M-2):** `features="principal"` en un modelo de 4 cuadrantes conserva el salto de
  ventana de la v1, solo para pruebas. Los aspirantes son `AxisModel` con variables explícitas: la ventana la fija la
  lista de variables preregistrada, no un `max()` implícito. Un eje que necesite épocas (p. ej. el I de M1: general
  antes del subyacente) se declara como dos especificaciones preregistradas, no como un cambio automático.
- **Mínimo de entrenamiento por eje (§ decisión del usuario):** un modelo, o un eje, solo predice en un corte si su
  ventana tiene:
  - ≥ `min_train_months` = **120** meses;
  - ≥ **2 recesiones NBER**, contadas por su pico en [primer mes, último mes de entrenamiento − 12]. El anuncio del
    pico llega con 4-12 meses de retraso, así que solo cuentan las que se conocían en el corte. `usrec` solo se usa
    como umbral de admisión, nunca como variable;
  - ≥ **8 cambios del eje G** en la etiqueta recalculada (p_g ≥ 0,5).

  El diagnóstico guarda, por corte y eje, la ventana efectiva, n, recesiones, cambios de G, filas quitadas por `dropna`
  y celdas imputadas. Consecuencia ya visible: un eje G con `growth_rt` no es elegible hasta ~1975-05 (en 1975-01 solo
  conoce el pico de 1969-12); un eje I con el subyacente, hasta ~1988.
- **L2 fijada a priori:** M0 usa L2 = 1,0 sobre la pendiente (escala de suma). La de M1 se fijará en su preregistro
  antes de correrlo con variables (`p_eval_base_draft.md` §8).

### 5b. Combinación en 4 cuadrantes y supuesto de independencia condicional

- P(q) = P(G)·P(I) (`metrics.combine_axes`). **Para el objetivo es exacto:** la etiqueta define p_q = p_G·p_I (ficha
  §5).
- Por eso la log-loss blanda de 4 cuadrantes de un modelo producto es **exactamente** la suma de las dos log-loss
  binarias (test `test_axis_logloss_decomposes_for_product`).
- El supuesto solo afecta a la incertidumbre del modelo: que los errores de los dos ejes no estén correlacionados dada
  la información.
- **Cómo se comprueba:**
  - el informe publica, por modelo, la correlación de los residuos (p_G etiqueta − P(G)) y (p_I etiqueta − P(I)) en la
    ventana de evaluación (`dependencia_ejes`);
  - si en desarrollo es grande (|ρ| > 0,2, umbral fijado ahora), se probará un término de interacción preregistrado
    en el entregable 4, no un cambio post hoc.

## 6. Puntuación y métricas

- Contra la etiqueta **oficial congelada v1.1** (caja fuerte), meses con `weight > 0`, no provisionales.
- **Ventana de evaluación FIJA (M-3, Estratega E9).** `eval_window: [desde, hasta]` está declarada en la
  configuración: todos los modelos de todos los modos deben predecir **todos** sus meses.
  - Si alguno no la cubre, la corrida **falla**.
  - Con `allow_shrink: true` hay un aviso (`UserWarning`), queda en `report.avisos`, en el registro y en el trial log,
    y `ventana_evaluacion.reducida = true`.
  - Añadir un modelo ya no cambia en silencio la muestra de los demás.
  - Además se publica la cobertura completa de cada modelo (`cobertura_completa_por_modelo`) y la persistencia cruda
    en su muestra completa (`persistencia_muestra_completa`, el listón de la v1).
- **Ventana de desarrollo de los baselines v2:** 1975-01 → 2004-12 (360 meses), la que propuso el Estratega.
  - La de M1 la fija su preregistro. El eje G con `growth_rt` es elegible desde ~1975-05 y el I con subyacente desde
    ~1988, así que M1 necesitará su propia ventana o su especificación por épocas.
- **Métricas:**
  - **log-loss blanda** de 4 cuadrantes (principal);
  - **log-loss binaria por eje** (P-EVAL-MOD): P(G alto) = P_expansion + P_late_cycle frente a `p_g_high`;
    P(I alta) = P_late_cycle + P_stagflation frente a `p_i_high`;
  - Brier, BSS (cociente de sumas) y acierto.
- **Comparaciones** frente a `baseline` (M0) y frente a `reference` (persistencia cruda), mes a mes, en los mismos
  meses:
  - mejora de log-loss con bootstrap circular por bloques de **12** (principal) y **24** meses (sensibilidad), 5.000
    réplicas, semilla 20261015;
  - mejora por eje; Brier, BSS y acierto;
  - por década, por **época** (1956-79 / 1980-2004) y por **subperiodo** (`subperiods`, con `subperiodos_mismo_signo`).
- **p-valores (B-4):**
  - `frac_rep_le0` = proporción de réplicas con media ≤ 0. Es la "p unilateral" preregistrada en P-EVAL-MOD: un
    percentil-bootstrap, **no** un p-valor bajo H0. Antes se llamaba `p_le0`.
  - `p_h0` = p-valor unilateral bajo H0 con la distribución bootstrap centrada.
  - **Holm** sobre la familia de comparaciones frente al baseline, con `p_h0`. P-EVAL-MOD aplicará Holm con su
    `frac_rep_le0` preregistrado; las dos están en el informe.
- **Cortes (Estratega E3-E7):**
  - **giro** (etiqueta dura oficial t ≠ t − 5) frente a **estable**, con IC;
  - meses desde el último cambio (0-5, 6-11, ≥ 12);
  - por **cuadrante** oficial;
  - **frontera** frente a no frontera;
  - **calibración** por eje: fiabilidad por tramos de 0,1;
  - **retraso de detección de los giros de G**: meses desde el cambio oficial del G duro, en rachas nuevas ≥ 6 m,
    hasta que P(G alto) queda del lado nuevo 3 meses seguidos; si no ocurre, censurado;
  - **falsas alarmas**: cruces al lado contrario en la parte estable de las rachas de G ≥ 6 m, a partir del sexto mes,
    por año.
- **Episodios** (decisión del usuario, fijados a priori), cada uno con el número de episodios ganados y una **prueba
  de signo** binomial:
  1. recesiones NBER ± 6 m;
  2. rachas de la etiqueta dura de **≥ 6 meses** (los parpadeos ya pesan en el corte de giros);
  3. **giros del eje G**: ventana de −3 a +6 meses alrededor de cada cambio del G duro cuya racha nueva dura ≥ 6 m.
- **Sensibilidad de modo:** latest_truncated − vintage del mismo modelo, con IC.

## 7. Registro de pruebas

Cada corrida añade una línea a `research/trials/harness_runs.jsonl` con:
- configuración completa;
- hash del código con commit y `git_dirty` de `src/`, `config/` y `tests/`, calculado **antes** de escribir nada;
- versiones de python/numpy/pandas/pyarrow/scipy y máquina;
- hashes de datos;
- hash de resultados **bit a bit** (`results_sha256`) y **redondeado a 10 decimales** (`results_sha256_r10`, estable
  entre máquinas: un cambio de 1e-13 no lo mueve; B-1);
- ventana de evaluación, avisos y métricas.

Además escribe una fila en `research/trial_log.md` (con los avisos) y los artefactos en
`FIN_DATA_ROOT/models/runs/<run_id>/`.

**Corrida oficial (B-2):** `--official` se niega si `src/`, `config/` o `tests/` tienen cambios sin commitear; se corre
después del commit del código. Los ajustes post hoc se anotan en el trial log (p. ej. los dos del placebo, §9b).

## 8. Baselines v2 (≤ 2004)

PENDIENTE_TABLA_BASELINES

## 9. Tests

`tests/test_harness.py` (mecánica de la v1, actualizada) y `tests/test_harness_v2.py` (A-1, M-1…M-6, M0, métricas):

| grupo | qué comprueba |
|---|---|
| listón | persistencia del arnés = baselines congelados v0.3 bit a bit; 61,14 % / 1,2997 y 63,04 % / 1,1824 en 579 meses |
| fuga de etiqueta | el `fit` recibe `PITLabeler.at(T)` (≠ final) y nada posterior a T − 6; columnas de la etiqueta imposibles; matriz alterada rechazada |
| placebo pareado | §9b: control t−5 no se marca; t+1 con σ = 1 sí (20 semillas cada uno) |
| A-1 | §4b (13 tests) |
| M-1 | `PITLabeler.at(≥ 2005)` bloqueado y registrado; `score_training` estricto e intacto |
| M-2 | ventanas por eje independientes; mínimos de meses/recesiones/cambios de G; recuento PIT de recesiones |
| M-3 | ventana fija: error, aviso con `allow_shrink`, ventana explícita cubierta |
| M-4 | función de pesos fijada y monótona; `sample_weight` = la función en el `fit` (madurez/uno/excluir) |
| M0 | sin variables macro; entrena con ≤ corte − 6; predicción = producto de ejes |
| métricas | log-loss 4 clases = suma de ejes en un modelo producto; Holm; prueba de signo; `p_h0`; detección y falsas alarmas; episodios; informe con todos los cortes; hash redondeado estable |
| registro | entrada con hashes; fila en el trial log; línea mínima con `record=False`; registro completo con caché |

### 9b. Placebo pareado y tabla de potencia (M-5)

**Diseño** (`src/models/placebo.py`; fijado antes de correr la tabla, con dos ajustes post hoc sobre UNA semilla
anotados en el trial log):
- etiqueta oficial ≤ 2004 **barajada** en bloques de 24 meses y las 8 variables a priori del placebo de la base PIT;
- refit anual 1975-2004, embargo 6;
- base = persistencia **blanda y dura** (one-hot) **sin penalizar**, y L2 = 0,05 sobre las variables añadidas.

**Contraste principal:** incremento **pareado** = log-loss(base + vars) − log-loss(base + vars + C), con la misma
permutación, para una columna sospechosa C de 3 columnas construida desde el objetivo barajado.

**Regla (a priori):** hay **fuga** si la media sobre **20 semillas** es > **0,02 nats**.

Diagnósticos secundarios:
- `pareado_nulo`: frente a C barajada en bloques, con la misma dimensión;
- el placebo absoluto de la v1 (vars frente a base): −0,090 nats de media. El sesgo baja de −0,13 a −0,09 al no
  penalizar la persistencia, pero sigue escondiendo fugas: con la regla absoluta **ninguno** de los 9 casos falla.

Resultados (`research/trials/placebo_power_v2.json`, 20 semillas por caso):

| caso (C) | incremento pareado medio (sd) | % semillas > 0 | ¿fuga? (regla) | pareado frente al nulo |
|---|---|---|---|---|
| ruido puro (sin fuga) | −0,0055 (0,0055) | 15 % | no ✔ | −0,0004 |
| **control t−5** (persistencia dura: SIN fuga) | +0,0001 (0,0004) | 65 % | **no ✔** (v1: +0,124 pareado, falsa alarma) | +0,018 |
| etiqueta de t+1, σ = 1 | **+0,062** (0,020) | 100 % | **sí ✔** (v1 absoluta: 0 %) | +0,069 |
| etiqueta de t+1, σ = 2 | +0,012 (0,012) | 90 % | no ✘ | +0,017 |
| etiqueta de t, σ = 1 | **+0,075** (0,022) | 100 % | **sí ✔** (v1 absoluta: 17 %) | +0,082 |
| etiqueta de t, σ = 2 | +0,015 (0,013) | 90 % | no ✘ | +0,020 |
| etiqueta de t, σ = 4 | −0,001 (0,009) | 45 % | no (indetectable) | +0,004 |
| calendario t−4 (1 mes de fuga) | +0,031 (0,006) | 100 % | sí ✔ | +0,048 |
| calendario t−1 | +0,380 (0,035) | 100 % | sí ✔ | +0,407 |

**Lectura:**
- La regla ya es **específica**: el control t−5 da +0,0001 y el ruido −0,006.
- Detecta las fugas débiles que la v1 dejaba pasar (t+1 y t con σ = 1, que aportan ~0,06-0,08 nats) y la de
  calendario de un mes.
- **Límite declarado:** fugas que aportan menos de ~0,015 nats (σ = 2) quedan bajo el umbral, aunque el 90 % de las
  semillas sea positivo. No cambio el umbral después de ver la tabla.
- Propuesta para el Validador: una regla complementaria preregistrada para el entregable 4, por ejemplo "aviso si
  ≥ 80 % de las semillas > 0".
- Estas cifras miden la potencia frente a columnas **añadidas**. Para un aspirante real (M1), el placebo se aplicará a
  sus variables con el mismo diseño pareado (con frente a sin la variable), con la etiqueta barajada.

## 10. Decisiones pendientes (usuario)

1. **P-EVAL-BASE:** borrador en `docs/models/p_eval_base_draft.md`. No está en `hypotheses.yaml` ni puede abrir nada
   hasta que lo apruebes y se commitee con su configuración.
2. **Separación física y cifrado del bloqueado** (§4b): cifrar con tu clave la etiqueta v1.0/v1.1, su instantánea de
   entradas, los baselines y las matrices completas, y dejar en disco solo versiones ≤ 2004. Es una versión nueva de
   artefactos congelados; hasta entonces la caja es anti-accidente.
3. **Figuras del Reportero** con la etiqueta hasta 2026-04: ¿recortar las nuevas a ≤ 2004?
4. **Clasificador de reglas** (prioridad baja): no se ha hecho en la v2; pasa al entregable 4 (reglas congeladas antes
   de correrlo, calibración 4 × 4 de Dirichlet dentro del walk-forward, fuera del criterio de éxito).

## 11. Registro de cambios

### v2.0 (2026-10-16)

| hallazgo | cambio |
|---|---|
| A-1 (ALTA) | `evaluate_holdout` como único punto de entrada; registro de consumo fijo, versionado y comprobado contra el historial de git; consumo commiteado antes de leer; solo ids `P-EVAL-` con `tipo: evaluacion_holdout`; `incluye`; una apertura por proceso; git falla cerrado; `PITData`/`PITLabeler` por identidad y tipo exacto; `run()` solo en desarrollo; caja cerrada tras la corrida; `limit` de solo lectura. Separación física: no (§4b) |
| M-1 | barrera y registro en `PITLabeler.at(≥ 2005)`; `score_training` con filtro y `<` (sin cambiar ficheros congelados); §4c con las vías restantes |
| M-2 | `AxisModel`: ventana por eje; mínimos 120 m + 2 recesiones + 8 cambios de G; producto de ejes con el supuesto documentado (§5b) |
| M-3 | `eval_window` fija; error o aviso registrado (`allow_shrink`) |
| M-4 | pesos de madurez a priori (§3b); `sample_weight`; sensibilidades uno/excluir; adenda de la ficha |
| M-5 | placebo pareado con base rica (persistencia blanda + dura sin penalizar), 20 semillas, umbral 0,02 sobre el incremento pareado; tabla de potencia (§9b) |
| M-6 + Estratega | log-loss binaria por eje, Holm, subperiodos, épocas, calibración, giro/estable, cuadrante, frontera, detección y falsas alarmas, bootstrap 24 m, prueba de signo, episodios nuevos |
| Estratega E1 | M0 = persistencia calibrada por eje en el walk-forward, listón principal |
| B-1…B-7 | hash redondeado + versiones; `git_dirty` antes de escribir y `--official`; registro completo de accesos; `frac_rep_le0` / `p_h0`; constantes de definición declaradas (§3); `dropna` contado y avisado |
| decisión (5) de la v1 | clasificador de reglas: no hecho; entregable 4 |

### v1.0 (2026-10-16)

Primera versión (commit b01e7ee): walk-forward, etiqueta recalculada, caja fuerte, baselines persistencia y
climatología. Validación ⚠️ (A-1) y revisión del Estratega ⚠️.
