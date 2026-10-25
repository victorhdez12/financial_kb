---
documento: checklist de REGISTRO de P-EVAL-BASE (borrador v4.3, §A9) y entrada para research/hypotheses.yaml (SIN activar)
fecha: 2026-10-25
autor: Validador (rama claude/puerta-gasto); NO registra nada: los pasos los hace el usuario en local, con datos y con la protección de rama activa
configuracion: config/harness/p_eval_base.yaml = byte a byte el bloque YAML de §A8 del borrador (lo comprueba tests/test_p_eval_base_registro.py)
---

# Registro de P-EVAL-BASE: checklist (A9)

El ensayo en seco se ancla con el hash de los **bytes** de `config/harness/p_eval_base.yaml` + el código de
`src/models` + las dependencias de la etiqueta PIT (`harness.prereg_config_sha`). Después del paso 5, cualquier
cambio en esos ficheros invalida el ensayo y hay que repetirlo. Los documentos (`docs/`) y `research/hypotheses.yaml`
no entran en ese hash.

## 0. Condiciones previas (A9-1 a A9-4b)

1. Corridas de desarrollo hechas y publicadas tal cual: 6e de M2 (`m2_m1cmp`, `m2_sens`), M3 (`m3_long`, `m3_m1cmp`,
   `m3_sens`), placebo del pool repetido con el código actual (sin fuga ni aviso) y pool (`pool_dev`, `pool_m1cmp`,
   `pool_pesos_uno`, `pool_pesos_excluir`).
2. Puerta de gasto leída (no es criterio): `PYTHONPATH=. .venv/bin/python tests/validation/puerta_gasto.py --pool-dev
   <id> --pool-m1cmp <id> --pool-uno <id> --pool-excluir <id> --m2-long 20261025-090304_m2_long_6314b5b0 --m3-long
   <id> --out research/validation/puerta_gasto/`. Si desaconseja registrar, decide el usuario.
3. Revisión del Validador y del Estratega del desarrollo y del borrador v4.3 (A9-3).
4. Aprobación del usuario del texto completo de la v4.3 (A9-4). Si llega después de los resultados de desarrollo del
   pool, se anota así en el trial log (B4-1).
5. **Código congelado:** a partir del paso 5 no se toca `src/models/` ni `src/labels/regime_us.py`,
   `src/features/pit.py`, `src/features/calendar.py`, `src/models/pit_labels.py`.

## 1. Configuración (A9-5, primera parte)

6. `config/harness/p_eval_base.yaml` en `main` (esta rama) y `pytest tests/test_p_eval_base_registro.py` en verde
   (comprueba que es el bloque de A8, que parsea, que los modelos están registrados y que la familia `principal_k1`
   tiene un solo miembro, `pool_g` frente a M0).
7. Árbol limpio (`git status --porcelain` vacío, también sin ignorados relevantes), en la rama `main` y al día con
   `origin/main`.

## 2. Protección de rama (A9-7, A3-1)

8. `.venv/bin/python -m src.models.harness --check-protection` → `ok: true`, con `allow_force_pushes = false`,
   `allow_deletions = false` y `enforce_admins = true` en `main` de `origin`. Si falla, no seguir.

## 3. Ensayo en seco registrado (A9-5, segunda parte)

9. `.venv/bin/python -m src.models.harness --dry-run config/harness/p_eval_base.yaml` → código de salida 0,
   `"ok": true`, `errores: []`. Revisar la tabla de elegibilidad (primer corte bloqueado; M2/M3: ventana del eje G
   desde 1968-05; pool: N_min = 60) y los `ensayos` (run_id de las corridas en `dry_run_window` 1993-01 → 2004-12).
10. El ensayo añade una línea a `research/holdout/dry_runs.jsonl` con `prereg_id: P-EVAL-BASE`, `config_sha` y
    `ok: true`. Commit solo de ese fichero ("P-EVAL-BASE: dry run ok, config_sha <12 primeros>") y push.

## 4. Hashes que anotar (en el trial log y en la entrada de §5)

11. `sha256sum config/harness/p_eval_base.yaml`.
12. `config_sha` del ensayo (paso 9).
13. `PYTHONPATH=. .venv/bin/python -c "from src.models import trials; print(trials.code_sha())"` → `src_models`,
    `pit_labels_deps`, `git_head`, `git_dirty` (tiene que ser `false`).
14. Datos: `LABEL_FILE_SHA256["1.1"]` (`src/models/vault.py`) y `MATRIX_SHA256_BY_VERSION["0.4"]`
    (`src/models/harness.py`); el ensayo los comprueba al leer.
15. `sha256sum tests/validation/potencia_holdout_comun.py` (contraste EWC de la sensibilidad de A6, "sha256 fijado
    al registrar"); anotarlo también en A6 del borrador.

## 5. Registro (A9-6)

16. Copiar la entrada de abajo al final de `research/hypotheses.yaml`, rellenando los `<…>` con los valores de los
    pasos 9-15 y la fecha. Cambiar en el borrador `version: 4.3-borrador` por `4.3 (aprobado <fecha>)` (los docs no
    cambian el `config_sha`).
17. Commit ("Register P-EVAL-BASE (v4.3): config_sha <…>") y push a `origin/main`. **Este push es el preregistro.**
18. Comprobar: `PYTHONPATH=. .venv/bin/python -c "from src.models import vault as V; print(V.eval_entry('P-EVAL-BASE'))"`
    devuelve la entrada (prefijo `P-EVAL-`, `tipo: evaluacion_holdout`, estado "preregistrada…").
19. Fila en `research/trial_log.md` con el commit del registro, los hashes y la nota B4-1.

## 6. Después (A10; NO forma parte del registro)

20. La apertura es un paso aparte, cuando lo decida el usuario: `FKB_HOLDOUT_UNLOCK="EVALUACION-UNICA P-EVAL-BASE"` +
    `evaluate_holdout("P-EVAL-BASE")`. Repite la protección y el ensayo en seco (`_preflight` exige la línea `ok` del
    paso 10 con el mismo `config_sha`), consume el preregistro y lo ancla en GitHub antes de leer. Una vez. Si falla
    después de consumir, la evaluación cuenta como gastada (A10).

## Entrada para research/hypotheses.yaml (NO activada: no está en el fichero hasta el paso 16)

```yaml
- id: P-EVAL-BASE
  registrada: <AAAA-MM-DD>
  autor: usuario (aprobación del texto v4.3) + Constructor/Validador
  tipo: evaluacion_holdout
  estado: preregistrada (sin datos mirados después de 2004; exposición previa de la etiqueta declarada en A2)
  documento: docs/models/p_eval_base_v4_draft.md (v4.3, aprobado <AAAA-MM-DD>)
  config_arnes: config/harness/p_eval_base.yaml
  incluye: []
  hipotesis_principal: H-POOL-001 (pool_g frente a m0_calibrated_persistence; Holm k = 1, familia principal_k1)
  ventana: ["2005-01", "2021-10"]
  criterio: >
    P-EVAL-BASE v4.3 §A3: criterios 1-7 (1 = límite inferior del IC 95 % > 0 de la mejora de log-loss blanda frente
    a M0, bootstrap por bloques de 12, 5.000 réplicas, semilla 20261015; 0,05 nats = efecto mínimo de interés que se
    informa y no decide); criterio 8 (signos de M3) informativo.
  hashes:
    config_file_sha256: <paso 11>
    config_sha_ensayo: <paso 12>
    src_models: <paso 13>
    pit_labels_deps: <paso 13>
    git_head_ensayo: <paso 13>
    ewc_script_sha256: <paso 15>
  ensayo_en_seco: research/holdout/dry_runs.jsonl (línea ok del <AAAA-MM-DD>, commit <…>)
```
