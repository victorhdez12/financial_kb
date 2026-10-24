---
documento: re-auditoría del Validador independiente de las correcciones a las specs a priori del pool (v1.1) y de P-EVAL-BASE v4.1 (borrador)
fecha: 2026-10-24
objeto: commit d1bde77 (m2_structural_spec.md v1.1, m3_tvtp_spec.md v1.1, pool_spec.md v1.1, p_eval_base_v4_draft.md v4.1, power_holdout.md v1.1, research/hypotheses.yaml, research/trial_log.md, src/models/regime_components.py, tests/test_regime_components.py)
antecedentes: docs/validation/2026-10-24_specs_pool_v4.md (M-1…M-4, B-1…B-9), docs/reviews/2026-10-24_estratega_macro_specs_pool.md (imprescindibles 1 y 2), decisiones del usuario A/B/C (Bitácora 24-oct)
contacto_con_datos: NINGUNO. No he cargado la etiqueta (ni ≤ 2004), ni la base PIT, ni scores. Solo he leído los registros de accesos y de corridas, la actividad de GitHub, el código, los documentos y datos SINTÉTICOS. El registro de accesos tiene 2.483 líneas antes y después de mi script. Sin corridas de modelos y nada registrado.
script: tests/validation/specs_pool_v4_reaudit.py (sintético; < 5 s)
---

# Re-auditoría de las specs v1.1 y de P-EVAL-BASE v4.1

## Veredictos

| objeto | veredicto | comentario |
|---|---|---|
| Prioridad a priori (push de v1.1 frente a lecturas de la etiqueta y corridas) | ✅ | push 10:46:29Z; ninguna lectura entre los dos pushes; ninguna corrida de M2, M3 ni del pool |
| M2 v1.1 (`m2_structural_spec.md`, H-M2-001) | ✅ con bajas | M-2, M-4 y B-2 cerrados; nuevas N-1 (texto antiguo sin quitar), N-2 (S-PIT-001 con NaN), N-3, N-4 |
| M3 v1.1 (`m3_tvtp_spec.md`, H-M3-001) | ✅ | M-1, B-4 y B-5 cerrados. El criterio 8 está bien definido en el texto; N-5 es un requisito para implementarlo |
| Pool v1.1 (`pool_spec.md`, H-POOL-001) | ✅ | B-6 y M-3.2 cerrados; la decisión C está recogida y la cita es literal |
| P-EVAL-BASE v4.1 (borrador) | ✅ (texto) con bajas | M-1, M-3, B-7 y B-8 cerrados; nueva N-6 (cómo se escribe en A8 la versión de M2 que salga de S-PIT-001) |
| `power_holdout.md` v1.1 | ✅ | M-3.1 y B-9 cerrados |
| `research/hypotheses.yaml` y trial log | ✅ | criterio 8 en H-POOL-001 y en H-M3-001; regla de S-PIT-001 añadida sin tocar el criterio del 15-oct; la fila del trial log dice que el criterio recae en un componente |
| Esqueleto y tests sintéticos | ✅ con bajas | 4 tests nuevos correctos; N-2 y N-5 se cierran en la implementación |

No hay hallazgos ALTOS ni MEDIOS nuevos. Las 7 bajas nuevas (N-1 a N-7) son de texto o de implementación y ninguna
cambia el diseño. **N-1, N-2 y N-5 deben cerrarse antes de la primera corrida de desarrollo.** Las demás, antes de
registrar.

## 1. Estado de los hallazgos

| hallazgo | qué pedía | estado | evidencia |
|---|---|---|---|
| **M-1** criterio de signos | criterio 8 operativo, con umbral, ventana y clave nueva; quitar A1-3 y A9-4 | **cerrado** | v4.1 A1-3, A3-8, A8 `sign_fraction`, A9-4. M3 §1, §5 y §8-2. H-M3-001 `criterio_signos`; H-POOL-001 `criterio_de_referencia`. El umbral es el 0,01 del Estratega y del usuario (A), no el 1e-6 que propuse; es lo decidido. La desigualdad es estricta, un faltante cuenta como fallo, no hay cláusula de vintage y la ventana es 2005-01 → 2021-10. A3 excluye de forma explícita `criterio_signos_cumple`. Requisito de implementación: N-5 |
| **M-2** V<sub>rev</sub> no PIT | declararlo (o hacerlo PIT) y fijar la muestra de Var(r) | **cerrado** | M2 §4: declarado no PIT, como s<sub>G</sub>, y es la única excepción al "≤ corte". Var(r) se mide en la última vintage, 1968-06 → 2004-12, ddof 0, y ρ̄ con esa misma muestra. La sensibilidad PIT `m2_struct_g_revpit` tiene una regla completa (s ≤ T − 24, ≥ 30 pares, relleno con el tramo más joven, solo vintage), no es principal y está en A5/A8. Así lo decidió el usuario (B) |
| **M-3** el tamaño es una cota inferior; falta b24 | comunicarlo; ACF 1-24; b24 en A8 | **cerrado** | `power_holdout.md` §2 (cota inferior, tabla φ, p informativos ×2-3) y §4. v4.1 A6 (`mejora_logloss_b24`: la calcula ya `harness._cmp`, línea 781; lo he comprobado), A7, A3 (criterio 7 redundante). M2 §8-4 y pool §4 (`acf_1_24`). La repetición de `power.py` con bloques de 24/36 era opcional y no se ha hecho |
| **M-4** S-PIT-001 | regla operativa; orden; versión única aguas abajo | **cerrado** (con N-2) | M2 §2: Δ<sub>S</sub> = media(d<sup>fp</sup>) − media(d<sup>pr</sup>) en los mismos meses; h = (hi − lo)/2 del IC 95 % de M2 − M0 en `m2_long`, vintage; se dispara si \|Δ<sub>S</sub>\| > h; en ese caso Filadelfia < 1990-07 = NaN y esa es la única versión. Orden en M2 §6: 6a → 6b → 6c (commit y push) → 6d → 6e; M3 §5 y pool §7 exigen el push de 6c; v4.1 A1-11 y A9-4b; S-PIT-001 en `hypotheses.yaml`. Script, prueba 4: M0 se cancela, así que la regla compara solo M2 consigo mismo |
| **B-1** nota de proceso | todas las lecturas del 24-oct | **cerrado** (con N-7) | §9/§8 de las tres specs. He reconstruido las cinco agrupaciones del registro (102/5, 102/5, 1, 18 y 102/5 accesos/denegados, con horas UTC) y coinciden exactamente |
| **B-2** grados de libertad en M2 | una sola implementación, panel, no convergencia, arranque | **cerrado** (con N-1 y N-4) | statsmodels 0.15.0 como única implementación; panel definido (tramo contiguo más largo con las 6 series, o con las 4 si < 60 m); regla de no convergencia; arranque fijo en cada reestimación; igualdad de parámetros del ensayo en seco en cada enero como test |
| **B-3** placebo de M2 | solo lectura | **no requería cambio** | — |
| **B-4** coherencia M3-M2 | decirlo en M3 §2 | **cerrado** | M3 §2 |
| **B-5** calibración de M3 dentro de muestra; optimizador | declararla; fijar `maxiter`/`gtol` | **cerrado** | M3 §3: L-BFGS-B, 500, 1e-8, arranque determinista; `TVTPSpec.opt_*` + test |
| **B-6** "exactamente" en d<sub>t</sub> | "exacta salvo recorte" | **cerrado** | pool §4. El recorte del pool se queda en 1e-6, declarado (era opcional) |
| **B-7** `test_start` | declararlo en A1 | **cerrado** | v4.1 A1-10 y A4 |
| **B-8** estado de M4-1/2/3 | — | **cerrado** | v4.1 A1: M4-2 y M4-3 corregidos; **M4-1 sigue abierto** hasta el ensayo en seco (A9-5), y es lo correcto |
| **B-9** `power_holdout.md` desfasado | IC decidido; numeración | **cerrado** | §2, §3.4 y §4 |
| **Estratega 1** peticiones de paro como flujo | λ<sub>c</sub>(f<sub>m</sub> − f<sub>m−12</sub>), estado 47 | **cerrado** | M2 §1, §3 y §9 (fila 1-2); H-M2-001; `claims_factor_loading`, `state_dim` = 13 + 32 + 2 = 47. Script, prueba 1: equivale a Σ Δf, y al inicio de una recuperación la forma de flujo da −2,0 (el signo observado), mientras que la de stock de la v1.0 da +0,7 |
| **Estratega 2** umbral γ > 0,01 | M3 §5, §8-2 y criterio 8 | **cerrado** | ver M-1 |
| **Usuario A** | criterio 8, no trivial | **cerrado** (con N-5) | ver M-1 y N-5 |
| **Usuario B** | V<sub>rev</sub> no PIT + sensibilidad PIT + muestra de Var(r) | **cerrado** | ver M-2 |
| **Usuario C** | pool y M2 en el estudio de eventos, con la cita literal de §4.2 | **cerrado** | pool §5b: M2, M3, `m3_ctp_g` y el pool, k = −6 … +8, tres tramos y estables. Script, prueba 5: las 28 líneas de §4.2 (P1-P11 y "prueba del mecanismo") son **idénticas** a la cita, y el fichero del Estratega no ha cambiado desde `1b02ae7` (10:01:25Z, anterior a d1bde77). No es criterio. H-POOL-001 `predicciones_a_priori` |

## 2. Prioridad a priori ✅

- **Push:** según la API de eventos de GitHub, `d1bde77` llegó a `main` a las **2026-10-24T10:46:29Z** (`before` = `b74f66d`).
  El commit es de las 10:46:27Z. `58d4036` (10:52:38Z) solo toca Obsidian, y desde `d1bde77` no ha cambiado ningún
  fichero de `docs/models`, `research`, `src` ni `tests`.
- **Lecturas de la etiqueta** (`research/trials/full/label_access.jsonl`):
  - entre el push de v1.0 (09:53:14Z) y el de v1.1 (10:46:29Z): **ninguna**;
  - después del push de v1.1: **una sola pasada**, de 10:47:11Z a 10:50:19Z. Son 102 accesos, todos de pytest y todos
    con `git_head` = `d1bde77`. Llegan como mucho a 2004-12 (90 desde la caché). Los 5 denegados son los tests de la
    barrera (`test_vault_development_never_decodes_holdout`, `test_M1_pitlabeler_blocks_holdout`,
    `test_N4_levels_at_blocks_holdout`). Es la "suite de 10:46-10:52Z" del Constructor;
  - el registro principal (`research/trials/label_access.jsonl`) termina en `power.py` a las 09:05:52Z.
- **Corridas:**
  - `harness_runs.jsonl` sigue terminando en la corrida del 23-oct (`20261023-112119_m1v2_sens`).
  - `harness_runs_unrecorded.jsonl` tiene, después de v1.0, 57 entradas, todas de pytest (10:47:14-10:50:23Z, `d1bde77`).
    Sus modelos son los de los tests antiguos (M0, M1 v1, sondas, juguetes). No hay ningún `m2_*`, `m3_*` ni `pool_*`.
  - Los esqueletos siguen lanzando `NotImplementedError` y siguen fuera de `model_registry`.
- **¿Contamina algo?** No. La pasada es posterior al push y repite tests que ya existían. Las specs v1.1 estaban
  congeladas en origin antes de que empezara.

## 3. Hallazgos nuevos

### N-1 (BAJA; antes de implementar) · Queda una frase de la v1.0 que contradice el arranque fijo

M2 §3, en el párrafo "Cadencia (PIT)", sigue diciendo "…reestiman en el primer corte y después solo en los cortes de
enero… y **arrancando del óptimo anterior**". Eso contradice el punto anterior ("en cada reestimación se arranca de
cero (no del óptimo anterior)"), la fila 4 de la tabla de cambios y `StructSpec.warm_start = False`. La intención no deja
dudas, pero el texto que se congela tiene que ser coherente: hay que borrar la frase. La fila de §9 ya cubre el cambio.

### N-2 (BAJA; antes de 6c) · La regla de S-PIT-001 "no se dispara" en silencio si hay un NaN

`s_pit_001_triggered` solo comprueba que las dos series tengan la misma forma. Si d<sup>pr</sup> o d<sup>fp</sup>
tienen un NaN, entonces Δ<sub>S</sub> = NaN, `abs(NaN) > h` es falso y la función devuelve `dispara = False`. Lo hace
aunque la diferencia real sea enorme (script, prueba 4: Δ = −1 nat con un NaN → no dispara). Además, si los meses no
coinciden la función lanza un error, pero la spec no dice qué hacer en ese caso: se podría acabar eligiendo una
intersección después.

**Para aprobar:** en M2 §2 y en la función, exigir que d<sup>pr</sup> y d<sup>fp</sup> sean finitas en **todos** los
meses puntuados de `m2_long`, alineadas por mes y con el mismo índice. Si no lo son, error y parada, sin intersección ni
elección. Añadir un test con un NaN.

### N-3 (BAJA) · Si S-PIT-001 se dispara, ¿de qué corrida sale el estudio de eventos de M2?

M2 §8-5 dice que M2 entra en el estudio de eventos "en las corridas `m2_long` y `m2_m1cmp`", y el pool §5b dice
"`m2_long`/`m3_long`". Si S-PIT-001 se dispara, la corrida principal de M2 pasa a ser `m2_long_phnan`. Hay que decir que
el estudio de eventos (y las predicciones P1, P4 y P7 sobre M2) se lee en la corrida **resuelta**.

### N-4 (BAJA) · La igualdad de parámetros del ensayo en seco depende de que todo converja

Con la regla de no convergencia ("se conservan los parámetros vigentes"), un enero sin convergencia hace que los
parámetros dependan otra vez de la historia de la corrida. Si eso pasa en un enero ≥ 1993 o en el primero del ensayo en
seco, la corrida larga y el ensayo en seco dejan de coincidir. El test de implementación de M2 §3 debe limitar la
igualdad a "todas las reestimaciones con `fit_converged = true`" e informar las excepciones. No cambia el modelo.

### N-5 (BAJA; requisito del arnés v2.4, antes de la corrida de desarrollo) · El criterio 8 puede quedar vacío según cómo lo llame el arnés

El texto está bien: el denominador son los cortes de la ventana en que el modelo debía ajustarse, y un corte sin
coeficientes cuenta como fallo. Pero hay dos trampas de implementación, comprobadas con datos sintéticos:
- **El denominador.** `harness.coefficient_signs` construye hoy la tabla solo con los cortes que **tienen**
  coeficientes. Si la clave v2.4 pasa esos cortes como `cut_months` a `gamma_fraction_criterion`, los cortes sin ajuste
  dejan de contar como fallo. Script, prueba 2: con la mitad de los cortes sin ajuste, el criterio **falla** con la
  ventana como denominador y **pasa** con los cortes ajustados (γ3: 0,80 frente a 0,40). Con un índice de otro tipo
  (Period frente a Timestamp) falla siempre, que es lo seguro.
- **La clave antigua es vacía.** Con todos los `expected_signs` en `decide: false` (A8), `criterio_signos_cumple` vale
  **True** aunque todos los γ sean 0 (prueba 3). A3-8 ya lo excluye; hay que vigilar que ningún código ni informe lo
  presente como el criterio de signos.

**Para aprobar (tests del arnés v2.4):**
1. `cut_months` = todos los meses de corte de `eval_window` en el modo (los 202 del bloqueado), nunca el índice de los
   coeficientes.
2. Un test con cortes sin coeficientes y otro con todos los γ = 0 que dé `criterio_fraccion_cumple = false`.
3. El ensayo en seco comprueba que `n_cortes` = número de meses de `dry_run_window`.

### N-6 (BAJA; antes de registrar) · A8 no dice cómo se escribe la versión de M2 que salga de S-PIT-001

El comentario de A8 dice "m2_struct_g = versión resuelta por S-PIT-001", pero ni A8 ni M2 nombran el parámetro de
configuración. Si se dispara, M2, la emisión de M3 y el pool tienen que llevar la misma marca, y esa marca entra en el
hash de configuración.

**Para aprobar:** fijar ahora el nombre y el valor en los dos casos (por ejemplo,
`model_params.m2_struct_g: {philly_pre1990_nan: false|true}`, heredado por `m3_tvtp_g`, `m3_ctp_g`, `pool_g` y las
sensibilidades). Así, en 6c solo se rellena un booleano y no se escribe una configuración nueva.

**Nota.** En el bloqueado, la sensibilidad `s_pit_001_filadelfia` (matriz prudente) cambia muy poco si S-PIT-001 se
dispara, porque los meses < 1990-07 de Filadelfia ya son NaN. Es coherente y no hace falta cambiarla.

### N-7 (BAJA) · Nota de proceso: falta la pasada posterior al push de v1.1

La pasada de la suite de 10:47:11-10:50:19Z (102 accesos, 5 denegados, `d1bde77`) es **posterior** al push, así que no
afecta a la prioridad. Está en la Bitácora, pero no en las §9/§8 de las specs. Hay que añadirla en el próximo cambio de
las specs (por ejemplo, el de N-1), para que la lista de lecturas siga completa.

## 4. Coherencia entre specs, v4.1 y `hypotheses.yaml`

He comprobado que coinciden en todos los documentos:
- **Versiones y dependencias:** M2, M3 y el pool en v1.1; la v4.1 los cita en v1.1 en A2 y A4; `depende_de` actualizado.
- **Criterio 8:** M3 §5, v4.1 A1-3, A3-8 y A8, H-M3-001, H-POOL-001, el trial log y `TVTPSpec` dicen lo mismo:
  0,01 estricto, ≥ 0,5, cada γ por separado, 2005-01 → 2021-10, sin cláusula de vintage, faltante = fallo.
- **S-PIT-001:** la regla y el orden coinciden en M2 §2 y §6, M3 §5, el pool §7, v4.1 A1-11 y A9-4b, y
  `hypotheses.yaml`. El criterio preregistrado el 15-oct no se ha tocado; la concreción va en una clave fechada.
- **V<sub>rev</sub>:** M2 §4, v4.1 A4/A5/A8, H-M2-001 y `StructSpec.rev_*`.
- **Peticiones de paro y estado 47:** M2 §1, §3 y §9, H-M2-001 y `StructSpec`. M3 hereda el cambio sin tocar su texto,
  como pidió el Estratega.
- **b24, ACF y potencia:** v4.1 A6/A7/A8, `power_holdout.md`, M2 §8 y pool §4.

La única contradicción interna es **N-1**. No he encontrado otras.

## 5. ¿Es registrable la v4.1 a falta solo del ensayo en seco y del arnés v2.4?

**El texto sí**, después de N-1, N-3 y N-6 (tres retoques que se pueden hacer en el mismo push que la implementación,
declarados en las §9). Ya no queda ninguna pregunta abierta ni alternativa condicional: el criterio de signos está
decidido, S-PIT-001 tiene regla y orden, V<sub>rev</sub> está declarado y la configuración de A8 está completa, salvo
N-6. La parte de **M4-1** solo se cerrará con el ensayo en seco `ok` registrado (A9-5).

**Pero "solo" no es exacto.** Por diseño, A9 exige además de A9-5:
- A9-1: M2, M3 y pool implementados, Validador ✅;
- A9-2: placebos y **una** corrida de desarrollo de cada uno;
- A9-4b: S-PIT-001 resuelta y empujada;
- A9-3 y A9-4: revisiones del desarrollo y aprobación del usuario.

Todo eso está bien planteado y no lo cuestiono, pero queda por hacer.

## 6. Para aprobar

1. **Antes de la primera corrida de desarrollo:** N-1 (borrar la frase), N-2 (S-PIT-001 exige d finita y alineada, con
   test) y N-5 (denominador del criterio 8 = `eval_window`, con tests).
2. **Antes de registrar:** N-3, N-4, N-6 y N-7.
3. Siguiente revisión del Validador: el arnés v2.4 y la implementación (tests sintéticos, tabla v(edad), sonda,
   placebos), antes de la corrida.

**Para el usuario:** no hay decisiones nuevas. Lo único que conviene recordar es lo que ya cuantificó el Estratega
(P10): el criterio 8 puede tumbar el pool por γ3 con una probabilidad de ≈ 0,5.
