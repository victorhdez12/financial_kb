---
documento: arnés de backtest walk-forward (Fase 3, entregable 3)
version: 2.3 (23-oct: eje G continuo, §5c; v2.2: A3-1 y pit_version; v2.1 ✅ con condiciones operativas; v2.0 = e58a054)
fecha: 2026-10-16
codigo: src/models/{harness,pit_labels,vault,metrics,base,trials,placebo,probes}.py
config: config/harness/baselines_v2_1.yaml (v2: baselines_v2.yaml; v1: baselines_v1.yaml, históricas); sonda de P-EVAL-BASE: p_eval_base_probe.yaml
tests: tests/test_harness.py (17) + tests/test_harness_v2.py (48) + tests/test_harness_gcont.py (13, eje continuo); suite completa: ver §9
datos: solo ≤ 2004-12 (periodo bloqueado 2005-01 → INTOCABLE)
depende_de: etiqueta v1.1 (tag label-v1.1; adenda de uso 2026-10-16), base PIT v0.3 (tag pit-v0.3)
revisiones: docs/validation/2026-10-16_harness_v1.md (⚠️), docs/reviews/2026-10-16_estratega_macro_harness.md (⚠️), docs/validation/2026-10-16_harness_v2.md (⚠️; dev ✅)
---

# Arnés de backtest walk-forward (nowcast de régimen EE. UU.)

El arnés es la única vía por la que un modelo se entrena y se puntúa. Hace cumplir las reglas de `docs/PLAN.md`
("Validación", "Regla de admisión", "Periodo bloqueado y reglas del arnés"), de la ficha de la etiqueta (§7, §12 y la
adenda del 2026-10-16) y de la base PIT (`pit_base.md` §3). Todavía **no hay modelos aspirantes con variables**: se
entrega con la persistencia cruda, la climatología y **M0, la persistencia calibrada**, que es el listón principal.

```bash
.venv/bin/python -m src.models.harness --config config/harness/baselines_v2.yaml --official   # ≤ 2004; código commiteado
.venv/bin/python -m src.models.harness --dry-run config/harness/p_eval_base_probe.yaml     # ensayo en seco (§4e)
.venv/bin/python -m src.models.placebo <salida.json>                                        # tabla de potencia (§9b)
.venv/bin/python -m pytest -q tests/test_harness.py tests/test_harness_v2.py
```

## 1. Piezas

| fichero | qué hace |
|---|---|
| `src/models/harness.py` | Configuración (`HarnessConfig`), datos (`PITData`; `ArrayData` para placebo y tests), pesos de madurez, ventanas por eje y mínimos de entrenamiento, walk-forward, puntuación en ventana fija, informe con cortes, signos y familias de Holm, `run()` (desarrollo), **ensayo en seco** (`dry_run_prereg`) y **`evaluate_holdout()` (único punto de entrada de la evaluación única)**, registro de modelos (`model_registry`: `base` + `models_*.py`), CLI |
| `src/models/pit_labels.py` | `PITLabeler`: la etiqueta v1.1 completa recalculada con los datos conocidos en T; **barrera** para T ≥ 2005-01 |
| `src/models/vault.py` | `LabelVault`: única puerta a la etiqueta oficial; desbloqueo con consumo commiteado en git; registros de accesos |
| `src/models/metrics.py` | log-loss blanda y binaria por eje, Brier, BSS, acierto, bootstrap (12 y 24 m), Holm, prueba de signo, calibración, cortes, episodios, detección de giros |
| `src/models/base.py` | Interfaz `Model` (con `sample_weight`), `AxisModel` (un modelo por eje), baselines: `PersistencePIT`, `Climatology`, `CalibratedPersistence` (M0) |
| `src/models/placebo.py` | Placebo pareado y tabla de potencia |
| `src/models/probes.py` | Sonda `axis_window_probe` para el ensayo en seco: mismas variables por eje que el aspirante, sin usarlas |
| `src/models/trials.py` | Registro automático de pruebas (rutas fijas durante la evaluación única, N7) |
| `research/holdout/evaluations.jsonl` | Registro de consumo de la evaluación única (ruta fija, versionado en git y empujado a `origin`; hoy vacío) |
| `research/holdout/dry_runs.jsonl` | Ensayos en seco registrados (ruta fija, versionado) |

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
- **`PITLabeler.at(T ≥ 2005-01)`** (M-1/D4) y, desde la v2.1, **`PITLabeler.levels_at(T ≥ 2005-01)`** (N4) lanzan
  `HoldoutLocked` y lo registran, salvo con la caja desbloqueada de la evaluación única (identidad, no duck typing).
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

**Antes de crear la caja, `evaluate_holdout` exige el ensayo en seco (§4e):** una línea `ok` con el mismo hash de
configuración + código en `research/holdout/dry_runs.jsonl` (commiteada), y lo **repite** sin tocar ningún registro
versionado. Si falla, se niega **antes de gastar** nada.

**`LabelVault(mode="holdout_evaluation")` comprueba, antes de leer nada:**
1. **Solo identificadores de evaluación explícitos** (D9):
   - prefijo `P-EVAL-`;
   - `tipo: evaluacion_holdout`;
   - estado "preregistrada…".
   Hoy **ninguna** hipótesis registrada lo cumple (test sobre el `hypotheses.yaml` real). P-EVAL-BASE es un borrador
   fuera del fichero; P-EVAL-MOD y los H-MOD quedan fuera de P-EVAL-BASE (decisión del usuario 16-oct).
2. **Confirmación explícita:** `FKB_HOLDOUT_UNLOCK = "EVALUACION-UNICA <prereg_id>"`.
3. **Git falla cerrado** (D6):
   - git disponible y `REPO` = raíz del repositorio;
   - una **rama** (no HEAD suelto): es la que se empuja;
   - árbol limpio, **incluidos los no rastreados** y los **ignorados relevantes** (N6, v2.1). Cuentan los ficheros
     ignorados en `src/`, `config/`, `tests/` y `research/`. No cuentan:
     - `__pycache__`/`*.pyc`: los genera Python; plantar un `.pyc` es intención, no accidente;
     - `research/trials/` y `research/holdout/runs/`: son salidas del arnés, no entradas;
     - `.env` (raíz): guarda las credenciales de las fuentes. Durante la evaluación las rutas de registro son fijas y
       los datos se comprueban por SHA-256, así que nada de `.env` redirige la evaluación.

   Cualquier error de git (sin binario, fuera de un repo, `git archive`) = no hay evaluación.
4. **Ancla externa** (v2.1; decisión del usuario 16-oct: repositorio privado en GitHub):
   - remoto con nombre fijo `origin` y URL de GitHub (`https://github.com/…`, `git@github.com:…` o
     `ssh://git@github.com/…`). La comprobación de la URL solo se relaja en los tests, por inyección explícita
     (`vault.REMOTE_URL_RE`), nunca por variable de entorno;
   - con el **cerrojo** tomado (abajo): `git fetch origin`, la rama local **contiene** `origin/<rama>` (si no, el
     remoto puede tener un consumo que aquí falta), y se empuja HEAD (`git push origin <rama>`, comprobado con
     `ls-remote`). El preregistro y su configuración quedan en el remoto antes de gastar nada.
5. **Registro de consumo en una ruta fija:** `research/holdout/evaluations.jsonl`, relativa al código. Ninguna
   variable de entorno la cambia (D2). Además:
   - debe estar rastreado por git;
   - **ninguna línea vista en cualquier versión del fichero** puede faltar. Se miran **todas las refs** (ramas,
     etiquetas, refs remotas tras el fetch, stash) **y el reflog** (`git rev-list --all --reflog`; M2-1).
     Un `reset --hard` (N2), una rama creada antes del consumo (N2b) o un push forzado que lo borre del remoto no lo
     esconden: un consumo visto en cualquier ref, reflog o remoto cuenta como gastado;
   - un commit en el que el fichero no existe también falla cerrado.
6. **No consumido:** ni el id ni ninguno de los que `incluye` se han consumido antes, tampoco como parte de otra
   evaluación.
7. **Una sola apertura por proceso.** Si ya hay evaluaciones, la nueva es una **ampliación** (B2-1/N9):
   - declara `amplia: <id anterior>`;
   - su ventana de evaluación no se solapa con ninguna ya evaluada (el registro guarda la ventana).

**Cerrojo (M2-1, N8).** Desde el paso 4 hasta que el consumo queda anclado, `fcntl.flock` exclusivo y no bloqueante
sobre `<git-dir>/fkb-holdout.lock`:
- vive dentro de `.git`, así que no ensucia el árbol;
- lo libera el sistema si el proceso muere;
- un segundo proceso falla en el acto ("cerrojo ocupado"). Lo prueba un test con dos procesos y la ventana
  ensanchada 4 s.

**Consumo antes de leer, anclado fuera de la máquina.** Si todo pasa, con el cerrojo tomado:
1. se **anota** la línea (con ventana, rama, remoto y `amplia`);
2. se **commitea** solo ese fichero;
3. se comprueba que el registro tiene **una** línea del id;
4. se **empuja** a `origin/<rama>`;
5. se comprueba que el commit de consumo **está en el remoto** (`git ls-remote` = el commit, y
   `git branch -r --contains` tras un fetch).

Solo entonces se abre la caja. Si el commit, el push o la comprobación fallan, la caja **no se abre** y el id queda
gastado (falla cerrado). Un fallo posterior también gasta la evaluación (por eso existe el ensayo en seco).

**Resultados en rutas fijas (N7).** Durante la evaluación, `FKB_TRIALS_DIR`, `FKB_RUNS_DIR` y `FKB_TRIAL_LOG` no
cuentan. Las rutas son fijas:
- `research/trials/harness_runs.jsonl`;
- `research/trial_log.md`;
- `research/holdout/runs/<run_id>/` (informe y predicciones también en CSV).

Al terminar se commitean y se empujan; si eso falla, solo se avisa, porque el consumo ya está anclado.

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
| caja reutilizada tras la corrida | `test_evaluate_holdout_single_entry_and_closes_vault` | cerrada; segundo `evaluate_holdout` denegado; rutas fijas durante la corrida (N7) |
| **v2.1** sin remoto / remoto que no es GitHub | `test_anchor_requires_github_origin` | denegado antes de gastar |
| **v2.1** push del consumo rechazado | `test_push_failure_spends_but_never_opens` | gastado y sin abrir; reintento denegado |
| **v2.1** N2 `reset --hard`, push forzado, N2b rama previa | `test_N2_history_rewrite_does_not_reopen` | denegado (remoto / reflog) |
| **v2.1** consumo en el remoto que falta en local | `test_remote_consumption_missing_locally_is_seen` | denegado |
| **v2.1** N8 carrera | `test_lock_blocks_concurrent_unlock`, `test_N8_race_two_processes_second_fails` | el segundo falla por el cerrojo; una sola línea |
| **v2.1** N6 ignorados relevantes | `test_N6_ignored_relevant_files_are_dirty` | sucio; `__pycache__` no cuenta |
| **v2.1** N9 ampliación | `test_N9_extension_needs_amplia_and_new_months` | exige `amplia:` y ventana sin solape |
| **v2.1** sin ensayo en seco / ensayo que falla / de otra configuración | `test_evaluate_holdout_refuses_before_spending_without_dry_run` | denegado antes de gastar |

**Separación física del bloqueado: no se hace en la v2/v2.1, y es una decisión, no un olvido.** Partir los ficheros en una
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
`_ISSUED`), y las vías de §4c leen los ficheros completos. Lo que la v2.1 sí cambia frente a la intención: la
**unicidad** queda anclada en el remoto. Reescribir el historial local o el remoto deja rastro en el otro y en el
reflog, y un tercero puede comprobar en GitHub el commit de consumo y su fecha antes de los resultados.

### 4c. Vías restantes (declaradas) y cómo se controlan

| vía | qué ve | control |
|---|---|---|
| `regime_us_v1.1.parquet`, `regime_us_v1.0.parquet` (hasta 2026-04) leídos directamente | etiqueta del bloqueado | Norma: todo lo que puntúe un modelo pasa por la caja. Lectores directos conocidos: `src/labels/checks.py`, `tests/test_labels.py` (hash de integridad del fichero completo, sin relación con variables), validaciones antiguas del Validador. `pit.score_training` ya filtra (§4a) |
| `regime_us_v1.1_inputs.parquet` (niveles hasta 2026-09) | permite recalcular la etiqueta del bloqueado | `PITLabeler.at` bloquea T ≥ 2005 (§4a); `R.make_label` directo: norma |
| `baseline_persistence_v0.3_{vintage,latest_truncated}.parquet` (hasta 2026-09; `pers_*` de t es casi la etiqueta de t − 5) | casi la etiqueta del bloqueado | El arnés no los lee (recalcula la persistencia con `PITLabeler`). El test del listón los lee **con filtro** `decision_date < 2005`. Norma para el resto |
| Matrices v0.3 y sus `lineage` (variables hasta 2026-09) | variables del bloqueado (sin etiqueta) | `PITData` filtra en desarrollo. Mirar variables sin la etiqueta no evalúa nada, pero cualquier descriptivo ≥ 2005 se anota en el trial log |
| Figuras del Reportero (`src/report/fase3/make_figures*.py`): **dibujan la etiqueta hasta 2026-04** | la etiqueta del bloqueado, a la vista | Norma: ya están publicadas; no se superpone ninguna predicción de modelo sobre ≥ 2005. Propuesta: que las figuras nuevas recorten a ≤ 2004 o se marquen "solo etiqueta" |
| `PITLabeler.levels_at(T ≥ 2005)` (N4) | niveles del bloqueado | **Barrera técnica** desde la v2.1 (como `at`) |
| Python dentro del proceso (`_EVAL`, `_ISSUED`, `_PROCESS`, `REMOTE_URL_RE`, monkeypatch; N1) | todo | Norma; separación física como solución de fondo (§10) |
| Un id `P-EVAL-…` nuevo con un commit (N9) | otra evaluación | Barrera parcial (v2.1): exige `amplia:` y ventana sin solape con lo ya evaluado; un preregistro nuevo es la vía prevista y queda en git y en el remoto |
| Disponibilidad de variables ≥ 2005 en el ensayo en seco | solo sí/no por mes de las variables pedidas (sin valores, sin etiqueta) | Necesaria para la cobertura; queda en el registro de accesos y en el trial log |

### 4e. Ensayo en seco de un preregistro (M2-2, v2.1)

`dry_run_prereg(prereg_id | cfg_path)`, `validate_prereg` o `evaluate_holdout(prereg_id, dry_run=True)` ejecutan
**toda** la configuración de una evaluación única sin abrir la caja ni gastar nada:
1. **Comprobaciones estáticas:**
   - fase `holdout_evaluation` e id `P-EVAL-…` que coincide;
   - `allow_shrink: false` (en la evaluación única la ventana no se reduce);
   - `eval_window` explícita, desde 2005-01 y antes del primer provisional oficial (meta de la etiqueta);
   - `test_start`, subperiodos dentro de la ventana y `dry_run_window` ≤ 2004;
   - `principal` y todos los modelos registrados (`model_registry`: `base`, la sonda y cada `src/models/models_*.py`);
   - `expected_signs` con claves `<eje>:<variable>` y familias de Holm bien formadas;
   - los `incluye` existen.
2. **Elegibilidad analítica en la ventana bloqueada:** para cada corrida (principal y sensibilidades), modo, modelo y
   eje, en el **primer corte** que toca la ventana. Para una ventana de inicio fijo los recuentos crecen con el corte.
   - **Meses de entrenamiento:** meses ≤ 2004 con todas las variables (matriz de desarrollo), más meses 2005…corte − 6
     con todas las variables. Esta parte sale de la **disponibilidad** de la matriz congelada: solo `notna`, sin
     valores y sin etiqueta, y queda registrada. Con `excluir`, se restan los 53 provisionales recalculados.
   - **Recesiones NBER y cambios de G:** cotas inferiores con los datos ≤ 2004.
   - **Supuesto declarado:** `weight > 0` después de 2004 (en la etiqueta solo vale 0 en 1950-54).
3. **Ensayo:** la misma configuración en desarrollo sobre `dry_run_window` (≤ 2004): mismos modelos, modos,
   sensibilidades, pesos, signos y Holm, con los subperiodos partidos en las dos mitades de la ventana y
   `allow_shrink: false`. Comprueba que el informe trae todo lo que pide el preregistro para `principal`:
   - mejora con IC, eje G, giro/estable y subperiodos;
   - detección pareada;
   - signos con `sign_stability`;
   - las familias de Holm.

Con `record`, cada ensayo deja sus corridas en el registro de pruebas (son corridas de desarrollo reales) y una línea
en `research/holdout/dry_runs.jsonl` con el **hash de configuración + código** (`src/models` y dependencias de la
etiqueta PIT). `evaluate_holdout` exige esa línea `ok` con el mismo hash, commiteada, y repite el ensayo (§4b).

**Demostración con P-EVAL-BASE:** `config/harness/p_eval_base_probe.yaml` es la configuración del borrador con la
sonda `axis_window_probe` en lugar de M1. La sonda declara las mismas variables por eje y no usa ninguna: persistencia
calibrada por eje y coeficiente 0 por variable.
- **Primera prueba (sin registrar):** el ensayo **falló** por un motivo real. Con `excluir`, el eje I con el IPC
  subyacente no es elegible hasta ~1992-11, así que el ensayo en 1990-01 → 2004-12 no cubría su ventana.
- **Corrección:** se cambió la ventana del **ensayo** (1993-01), no la de la evaluación.
- **Corrida registrada:** ver la línea `ok` en `dry_runs.jsonl`; elegibilidad en `p_eval_base_draft.md` §9.

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
- **L2 fijada a priori:** M0 usa L2 = 1,0 sobre la pendiente (escala de suma). La de M1 está en `m1_spec.md` §3
  (L2 = 6 sobre las variables estandarizadas, 1 sobre el logit de la persistencia).
- **Coeficientes (v2.1, criterio 5):** `model.coefficients()` en cada corte. Claves `"<eje>:<variable>"` (sonda) o
  `"<eje>_<variable>"` (M1, `models_logit`), normalizadas a `"<eje>:<variable>"`; el logit de la persistencia es
  `<eje>:pers`. La interfaz `Model` no cambia (compatible con el entregable 4).

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

### 5c. Eje continuo: previsión de G con su incertidumbre (v2.3, 23-oct)

Lo exige el nowcast estructural de G (Estratega, revisión de M1 v2 §3.2; decisión 3 del usuario). **Solo
infraestructura: ningún modelo especificado.**

- **Interfaz** (`base.ContinuousAxisModel`, subclase de `AxisModel`): `continuous_axes = ("G",)`;
  `fit_axis_continuous(axis, X, g, t, w, info)` y `predict_axis_continuous(axis, X, info) → (media, desv.)`. Los
  ejes que no están en `continuous_axes` (el I) siguen la interfaz de siempre.
- **Objetivo:** `g` = valor continuo de G de la **etiqueta recalculada con datos ≤ T** (columna `G` de
  `PITLabeler.at`), en los mismos meses, con el mismo embargo, purga y pesos de madurez que el objetivo blando `t`
  (que también recibe). Nunca la etiqueta oficial. Si falta la columna o no es finita, error.
- **De G a probabilidad:** la etiqueta define p_g_high = Φ(G/s_G) (ficha §5, s_G = 0,40). Si G ~ N(μ, σ²),
  E[p_g_high] = **Φ(μ/√(σ² + s_G²))** (`base.gaussian_axis_prob`; para I, centro κ y s_I). Es la previsión que
  minimiza la log-loss esperada frente al objetivo blando si la previsión de G es correcta. La escala sale de la
  etiqueta congelada (`PITData.axis_scale` → `PITLabeler.lp`), no del modelo.
- **Puntuación:** P(G alto) se combina con P(I alta) en 4 cuadrantes y se puntúa **exactamente igual que M0**:
  log-loss, ejes, giros/estables, episodios, falsas alarmas, retraso, calibración, Holm. Comparable con M0 sin más.
- **Métricas informativas** (`report["g_continuo"]`, solo si hay algún modelo continuo; no deciden): por modo y
  modelo, CRPS gaussiano, RMSE, sesgo y cobertura de los intervalos centrales del 50 % y el 80 % (PIT) sobre los
  **mismos meses** que la log-loss; y, entre pares de modelos continuos de la misma corrida, la mejora de CRPS con el
  bootstrap del arnés. M0 no tiene previsión continua: frente a M0 solo cuenta la log-loss.
- **Predicciones:** columnas `g_mu`, `g_sd` (NaN en los modelos no continuos). **Solo existen si hay algún modelo
  continuo**: las corridas previas no cambian de columnas, de informe ni de `results_sha256` (comprobado bit a bit:
  baselines v2.1 y M1 v2; Bitácora del 23-oct).
- Controles en el arnés: forma (n,) de media y desviación, finitas, desviación > 0; `assert_no_forbidden` sigue
  actuando (una columna con nombre de la etiqueta, p. ej. `g_true`, se rechaza).
- Tests: `tests/test_harness_gcont.py` (13, datos sintéticos): transformación frente a Monte Carlo, CRPS en forma
  cerrada, señal plantada (bate a M0; RMSE del residuo), oráculo (CRPS ≈ 0 y log-loss binaria = entropía del objetivo),
  sin señal no inventa, embargo del objetivo continuo, errores, y "sin modelos continuos no cambia nada".

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
  - **retraso de detección de los giros de G** (definición **v2.1**, M2-3, fijada antes de recalcular nada y anotada
    en el trial log):
    - giros = cambios del G duro oficial **sin parpadeos**. Una racha < 6 m toma el valor de la última racha larga,
      así que los giros alternan de dirección. El mes del giro es el inicio de la racha larga nueva;
    - **retraso hasta la confirmación**: el mes c del tercer mes seguido de P(G alto) del lado nuevo, buscando desde
      el giro − 3 m. Retraso = c − giro, **sin cota en 0**: puede ser −1 (se permite anticipar);
    - no confirmado dentro de la racha nueva = **censurado**: se cuenta aparte y **no entra en la media**;
    - frente al comparador: retraso **pareado** en los giros que detectan los dos, y censurados de cada uno
      (`deteccion_frente_al_comparador`);
  - **falsas alarmas**: cruces al lado contrario en la parte estable de las rachas de G ≥ 6 m, a partir del sexto mes,
    por año.
- **Episodios** (decisión del usuario, fijados a priori), cada uno con el número de episodios ganados y una **prueba
  de signo** binomial:
  1. recesiones NBER ± 6 m;
  2. rachas de la etiqueta dura de **≥ 6 meses** (los parpadeos ya pesan en el corte de giros);
  3. **giros del eje G** (v2.1): los giros sin parpadeos de arriba, ventana de −3 a +6 meses **sin solape** (si la
     ventana posterior de un giro alcanza la anterior del siguiente, se recorta para que el siguiente conserve sus 3
     meses previos).

  Un episodio **truncado** por el borde de la muestra se informa, pero no entra en la prueba de signo (B2-5): por
  ejemplo, una recesión ya en curso al empezar ("rec 1975-01"), o una ventana ± pad o una racha que tocan el borde.
  `por_periodo` publica además el rango real cubierto (`desde_real`/`hasta_real`).
- **Signos de los coeficientes (v2.1, M2-4):** con `expected_signs` en la configuración,
  `report["signos_coeficientes"][modo/modelo]` publica:
  - por coeficiente: media y fracción de cortes con el signo preregistrado en la ventana, y `coincide`;
  - `sign_stability`: todos los cortes, también los anteriores a la ventana; media antes y después de cada salto de
    vintage con ≥ 12 cortes a cada lado;
  - `criterio_signos_cumple`: solo cuentan los coeficientes que deciden.
- **Familias de Holm preregistradas (v2.1, M2-4):** `holm_families` en la configuración. Cada miembro (modelo,
  comparador, métrica `logloss`/`ll_g`/`ll_i`) con el p preregistrado (`frac_rep_le0` o `p_h0`). Ejemplo, P-EVAL-MOD:
  cada M1 + módulo frente a M1 en su eje, con `frac_rep_le0`. Salen en `report["holm_familias"]`.
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

**Corrida oficial v2.1:** `20261016-141704_baselines_v2_1_4261f2ca` con `config/harness/baselines_v2_1.yaml`
(código en `2fd94e0`, árbol de código limpio; hash `4261f2ca…`, r10 `1ae36a52…`). Misma configuración que la v2:
**todas las log-loss, Brier y aciertos son idénticos**; cambian solo la detección de giros y los episodios (v2.1,
tabla de abajo). La corrida v2 queda como histórica:

**Corrida oficial v2 (histórica):** `20261016-132138_baselines_v2_1a6d6df8` con `config/harness/baselines_v2.yaml`.
- Código en el commit `e58a054`, `git_dirty: false`.
- Hash de resultados `1a6d6df8…`; redondeado (r10) `509dba25…`.
- Refit mensual, embargo 6, mínimo de entrenamiento 120 m + 2 recesiones + 8 cambios de G, peso de madurez.
- **Ventana fija 1975-01 → 2004-12 (360 meses)**, la misma para todos los modelos y modos; sin avisos.
- Sin ninguna variable macro.

**Listón de la v1 intacto:** la persistencia cruda en su muestra completa 1956-10 → 2004-12 (579 meses) da
61,14 % / **1,2997** (vintage) y 63,04 % / **1,1824** (latest_truncated), igual que en la v1.

| modo | modelo | acierto | log-loss 4 c. | log-loss G | log-loss I | Brier |
|---|---|---|---|---|---|---|
| vintage | persistencia cruda | 65,28 % | 1,1522 | 0,8575 | 0,2751 | 0,3132 |
| vintage | **M0 (persistencia calibrada)** | **68,33 %** | **0,8110** | **0,5993** | **0,2117** | 0,2565 |
| vintage | climatología | 30,56 % | 1,3863 | 0,6931 | 0,6876 | 0,5250 |
| latest_truncated | persistencia cruda | 68,33 % | 1,0216 | 0,7722 | 0,2329 | 0,2502 |
| latest_truncated | **M0** | 68,06 % | **0,7873** | **0,5717** | 0,2156 | 0,2376 |
| latest_truncated | climatología | 30,56 % | 1,3864 | 0,6930 | 0,6864 | 0,5249 |

**M0 frente a la persistencia cruda** (mejora = log-loss de la persistencia − log-loss de M0; IC 95 % por bloques de
12 m; los de 24 m son casi iguales):

| corte | vintage | latest_truncated |
|---|---|---|
| total (4 cuadrantes) | **+0,341** [+0,145; +0,579] (b24: [+0,157; +0,551]) | +0,234 [+0,052; +0,459] |
| eje G | +0,258 [+0,081; +0,478] | +0,201 [+0,030; +0,410] |
| eje I | +0,063 [+0,007; +0,129] | +0,017 [−0,022; +0,059] |
| meses de **giro** (90) | **+1,270** [+0,583; +2,078] | +1,075 [+0,487; +1,761] |
| meses **estables** (270) | +0,032 [−0,083; +0,152] | −0,046 [−0,133; +0,043] |
| 1975-79 / 1980-2004 | +0,314 / +0,347 | +0,254 / +0,230 |
| 1975-89 / 1990-2004 | +0,374 / +0,309 | +0,325 / +0,143 |
| frontera / no frontera | +0,583 / +0,325 | +0,454 / +0,219 |
| episodios ganados (v2.1, sin truncados): NBER ± 6 / rachas ≥ 6 m / giros de G | 3 de 4 / 12 de 17 / **10 de 11** (signo p = 0,012) | 4 de 4 / 9 de 17 / 7 de 11 (p = 0,55) |
| giros de G (v2.1: sin parpadeos) / detectados / censurados | 11 / 10 / 1 (los dos modelos) | 11 / 10 / 1 |
| retraso medio hasta la **confirmación** (detectados) | 4,9 → **4,6** meses | 3,8 → 3,2 meses |
| retraso pareado M0 − persistencia (10 pares) | −0,3 meses | −0,6 meses |
| falsas alarmas por año (parte estable) | 0,40 → 0,30 | 0,40 → 0,40 |
| *(v2, histórico: 16 "giros", retraso hasta el inicio)* | *4,00 → 3,81* | *3,75 → 3,88* |

**Lectura:**
- **La calibración sola vale ~0,34 nats en vintage.** M0 recorta la seguridad de la persistencia: en el eje G, la
  pendiente del logit de la persistencia es ~0,24.
  - Casi toda la ganancia está en los meses de giro (2,46 → 1,19 nats), y sin coste en los estables.
  - Esto confirma el diagnóstico del Estratega: el listón crudo era demasiado bajo. **M0 es el listón principal:**
    un aspirante que solo "aprenda a dudar" no lo bate.
- **La calibración no adelanta la detección.** El retraso hasta la confirmación (~4,6-4,9 meses en vintage, v2.1; el
  "~4" de la v2 medía hasta el inicio de la racha y contaba parpadeos) y las falsas alarmas apenas cambian:
  M0 no sabe **cuándo** gira el ciclo, solo duda más.
  - Ese es el margen para las variables: ≤ 3 meses de retraso con ≤ 0,5 falsas alarmas al año (Estratega).
  - En los meses de giro, M0 sigue a 1,19 nats frente al suelo de ~0,48.
- **Sensibilidad de modo:** M0 pierde solo 0,024 nats [−0,000; +0,046] al pasar a vintage, frente a 0,131 de la
  persistencia cruda. La calibración absorbe buena parte del coste de usar las primeras publicaciones.
- **Independencia de ejes (§5b):** la correlación de los residuos G-I es 0,015 (vintage) y 0,035 (latest_truncated),
  muy por debajo del umbral de 0,2.
- **Calibración por tramos (M0, eje G, vintage):** M0 queda algo infraconfiado por encima de 0,5 (en el tramo
  0,7-0,8 predice 0,75 y observa 0,94). Se informa; no se ajusta nada.
- **Holm** frente a M0 (persistencia cruda y climatología): p ajustada 1,0 en los dos modos. Ningún baseline bate a M0.
- La corrida v1 (`20261016-092402_baselines_v1_27cae755`) queda como registro histórico. La v1 no tenía M0, pesos ni
  ventana fija, así que sus cifras de climatología no son comparables.

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
- **Regla complementaria (v2.1, M2-5; preregistrada antes de correr ningún placebo de un aspirante con ella):**
  **aviso de fuga** si, sobre las 20 semillas, la prueba de signo unilateral da p < 0,01 (≥ 15 de 20 positivas) **o**
  t > 3. El aviso obliga a investigar; no falla solo. La regla principal (media > 0,02) no cambia.

  Aplicada a la tabla ya publicada (`placebo.leak_rules`, sin correr nada nuevo):

  | caso | t | signo p | ¿aviso? |
  |---|---|---|---|
  | ruido | −4,5 | 0,9998 | no ✔ |
  | control t−5 | 1,6 | 0,13 | no ✔ |
  | t+1, σ 2 | 4,4 | 0,0002 | **sí** ✔ |
  | t, σ 2 | 5,2 | 0,0002 | **sí** ✔ |
  | t, σ 4 | −0,5 | 0,75 | no (indetectable) |

  Las fugas fuertes (σ 1, calendario) dan fuga y aviso.
- Estas cifras miden la potencia frente a columnas **añadidas** y con **este** regularizador (L2 = 0,05 frente a la
  log-loss media), que también encoge la columna sospechosa.
- **El placebo de un aspirante usa su especificación y su L2** (`placebo.model_placebo(pit, sin, con)`): incremento
  pareado = log-loss(modelo sin las variables) − log-loss(modelo con ellas), con la etiqueta barajada, las mismas
  permutaciones y las dos reglas. El de M1 lo hace el entregable 4 (`m1_spec.md` §5).

## 10. Decisiones pendientes (usuario)

1. **P-EVAL-BASE:** borrador **v2, ejecutable**, en `docs/models/p_eval_base_draft.md`. Solo M1 frente a M0, con el
   ensayo en seco demostrado con una sonda. No está en `hypotheses.yaml` ni puede abrir nada hasta que:
   - lo apruebes;
   - el placebo de M1 salga limpio;
   - se commiteen su configuración y su ensayo en seco.
1b. **Ancla en GitHub (pasos tuyos; el arnés no crea el repositorio ni empuja nada fuera de la evaluación):**
   1. `gh auth login`;
   2. crear un repositorio **privado** vacío (p. ej. `gh repo create <usuario>/financial_kb --private`);
   3. `git remote add origin <URL de GitHub>` (el nombre **tiene** que ser `origin`);
   4. `git push -u origin main`.

   Sin eso, `evaluate_holdout` se niega antes de gastar nada.
2. **Separación física y cifrado del bloqueado** (§4b): cifrar con tu clave la etiqueta v1.0/v1.1, su instantánea de
   entradas, los baselines y las matrices completas, y dejar en disco solo versiones ≤ 2004. Es una versión nueva de
   artefactos congelados; hasta entonces la caja es anti-accidente.
3. **Figuras del Reportero** con la etiqueta hasta 2026-04: ¿recortar las nuevas a ≤ 2004?
4. **Clasificador de reglas** (prioridad baja): no se ha hecho en la v2; pasa al entregable 4 (reglas congeladas antes
   de correrlo, calibración 4 × 4 de Dirichlet dentro del walk-forward, fuera del criterio de éxito).

## 11. Registro de cambios

### v2.3 (2026-10-23, tarde)

| # | cambio | origen | dónde |
|---|---|---|---|
| — | **Eje G continuo** (§5c): `ContinuousAxisModel`, `gaussian_axis_prob`, `gaussian_crps`; `_fit_predict_axes` pasa el G continuo de la etiqueta recalculada y convierte (μ, σ) en P(G alto); `continuous_report` → `report["g_continuo"]` (CRPS/RMSE informativos). Sin modelos continuos no cambia nada (columnas, informe, hash) | decisión del usuario 23-oct (3); Estratega M1 v2 §3.2 | `base.py`, `harness.py`; `tests/test_harness_gcont.py` |
| — | **Cálculo de potencia** de la evaluación única (`src/models/power.py`; `docs/models/power_holdout.md`): solo desarrollo ≤ 2004 y la longitud pública del bloqueado | decisión del usuario 23-oct (4) | `power.py` |

### v2.2 (2026-10-23)

| # | cambio | origen | dónde |
|---|---|---|---|
| A3-1 | **Protección de rama comprobada por código.** `vault.check_branch_protection(rama)` consulta `gh api repos/<o>/<r>/branches/<rama>/protection` (propietario/repositorio leídos de la URL de `origin`) y exige `allow_force_pushes.enabled = false`, `allow_deletions.enabled = false` y `enforce_admins.enabled = true`. Falla **cerrado**: sin `gh`, sin sesión, 404/403, JSON raro, clave ausente o mal formada → `HoldoutLocked`. Se llama (1) en `LabelVault._unlock`, paso 4b, **antes** del cerrojo, del push y del consumo (nada se gasta si falla); (2) al principio de `evaluate_holdout`; (3) en `dry_run_prereg` con `record=True` (el ensayo registrado es el paso previo a registrar un `P-EVAL-…`: sin protección no queda ninguna línea `ok`). CLI: `python -m src.models.harness --check-protection`. Comprobado el 23-oct en `victorhdez12/financial_kb` (público): `main` con las tres condiciones | Validador v2.1, A3-1 | `vault.py`, `harness.py`; tests `test_A31_*` (respuestas de `gh api` simuladas) |
| — | **`pit_version` por configuración** (v0.3 por defecto; hashes de las matrices en `MATRIX_SHA256_BY_VERSION`). Una versión **candidata** (la v0.4) solo se acepta en desarrollo: `HarnessConfig.validate` y `PITData` en `holdout_evaluation` exigen una versión en `P.FROZEN` | base PIT v0.4 / M1 v2 | `harness.py` |
| B3-1 | **`_check_eval_config` rechaza una `pit_version` que no esté en `P.FROZEN`** (añadido en `0553476`, después de los resultados de desarrollo de M1 v2; neutro para las cifras de desarrollo, que el Validador reprodujo con el mismo hash tras el cambio). Motivo: una base candidata fallaba en `_run` **después** de consumir el preregistro; ahora el ensayo en seco (y `_preflight`, que lo repite antes de abrir la caja) la para antes. Registro añadido aquí el 23-oct (Validador, B3-1) | M1 v2 / Validador B3-1 | `harness.py`; `tests/test_models_m1v2.py::test_dry_run_flags_candidate_pit_before_spending` |
| — | **Base PIT v0.4 congelada** (23-oct, tag `pit-v0.4`): `HarnessConfig`/`PITData` la aceptan ya en `holdout_evaluation`. `PIT_VERSION` por defecto sigue en `"0.3"` (baselines y M1 v1 se reproducen sin tocar sus configuraciones). Los tests de "candidata rechazada" usan ahora una versión ficticia | decisión del usuario 23-oct (1) | `pit.py`, tests |

Nota operativa: la protección de rama en un repositorio **privado** exige GitHub Pro (403 sin él). Si el repositorio
vuelve a privado sin Pro, `check_branch_protection` falla y no hay evaluación única (falla cerrado, como debe).

### v2.1 (2026-10-16)

| hallazgo (Validador v2) | cambio |
|---|---|
| M2-1 (N2, N2b, N8) | ancla externa (decisión del usuario): `origin` en GitHub, fetch + la rama contiene `origin/<rama>`, push del preregistro y del consumo, comprobados en el remoto antes de leer; registro comprobado contra todas las refs y el reflog; cerrojo `fcntl` exclusivo; una sola línea del id tras el commit |
| M2-1 (N6, N7) | ignorados relevantes = sucio (con excepciones declaradas); rutas de resultados fijas durante la evaluación |
| M2-2 | ensayo en seco (`dry_run_prereg`, `evaluate_holdout(dry_run=True)`), exigido con su hash y repetido antes de gastar |
| A2-1 | `p_eval_base_draft.md` v2: M1 frente a M0, eje I con el subyacente, ventana 2005-01 → 2021-10, sensibilidades en la misma corrida; demostrado con la sonda |
| M2-3 | detección v2.1: confirmación, censura aparte, giros sin parpadeos, ventanas sin solape, anticipación |
| M2-4 | signos de los coeficientes y `sign_stability` en el informe; familias de Holm preregistradas con su p |
| M2-5 | regla complementaria del placebo (signo p < 0,01 o t > 3); `model_placebo` con el modelo del aspirante |
| B2-1 | barrera en `levels_at` (N4); `amplia:` y ventanas sin solape (N9) |
| B2-2 | = N6/N7 |
| B2-5 | episodios truncados fuera de la prueba de signo; `por_periodo` con el rango real |
| B2-3, B2-4, B2-6, B2-7 | documentadas (§11b) |
| decisión (b) del usuario | módulos H-MOD fuera de P-EVAL-BASE; nota en `hypotheses.yaml` |
| entregable 4 | `model_registry()` descubre los `REGISTRY` de `src/models/models_*.py` (M1 sin tocar sus ficheros); claves `G_x` de M1 aceptadas |

### 11b. BAJAS documentadas sin cambio de código

- **B2-3.** Los pesos de madurez salen de un estudio de revisión con cortes de 1975 a 2024, así que incorporan el
  comportamiento de las revisiones de la **etiqueta** en el periodo bloqueado. No incorporan variables, igual que
  s_G/s_I (constantes de definición, §3). Van de 0,86 a 1: las sensibilidades `uno`/`excluir` lo cubren. El "a
  priori" no se puede verificar con git (un solo commit); como la función solo usa el estudio congelado, no había
  ventaja que buscar.
- **B2-4.** El recuento de recesiones usa el primer mes con `usrec = 1` (pico + 1). El retraso de los anuncios del
  NBER antes de 1980 no está documentado en el proyecto. Solo decide la **elegibilidad**, nunca entra como variable,
  y el margen de 18 meses cubre los anuncios conocidos (4-12 meses).
- **B2-6.** El orden "eps y L2 de M0 escritos antes de verlo" no se puede verificar (un solo commit). La sensibilidad
  del Validador (0,8107-0,8159) muestra que no importa.
- **B2-7.** El `code_sha256["pit.py"]` del meta v0.3 no coincide con `pit.py` en el tag `pit-v0.3`. Ningún test ni
  artefacto congelado depende de él, y el meta congelado no se toca. La procedencia del código de cada corrida está
  en `pit_labels_deps` del registro de pruebas.

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
