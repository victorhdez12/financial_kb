---
documento: BORRADOR del preregistro de la evaluación única del modelo base (P-EVAL-BASE)
version: 3.0 (2026-10-23; M1 v1 y M1 v2 frente a M0 con Holm k = 2; criterio de éxito del 16-oct; base PIT v0.4)
fecha: 2026-10-23
estado: BORRADOR. NO está en research/hypotheses.yaml y NO abre el periodo bloqueado. Pendiente de la aprobación del
  usuario; antes de registrarlo: Validador + Estratega sobre la v0.4 y M1 v2, base PIT v0.4 CONGELADA, placebos sin
  fuga ni aviso, configuración commiteada, ensayo en seco `ok` y protección de rama comprobada por el código (A3-1).
autor: Constructor (M1 v2), sobre el borrador v2 (arnés v2.1) y la revisión del Estratega de M1 (§4-iv)
---

# P-EVAL-BASE (borrador v3)

Escrito **sin mirar ningún dato ≥ 2005** de la etiqueta ni ninguna relación entre variables y etiqueta ≥ 2005. La
versión v2 de este borrador (M1 v1 sola frente a M0) queda debajo, en §B, como historia: **la v3 la sustituye**.

## A1. Qué cambia frente a la v2

- **Dos hipótesis, no una:** M1 v1 (`m1_logit_axis`, H-M1-001) y M1 v2 (`m1v2_logit_axis`, H-M1-002), cada una frente a
  M0, en la **misma** apertura y sobre los **mismos** meses. **Holm con k = 2** sobre las dos (Estratega §4-ii): la
  elección entre v1 y v2 no se hace con datos de desarrollo y el coste de la búsqueda queda contado.
- **Criterio de éxito del 16-oct** (aceptado por el usuario antes de mirar el bloqueado; trial log): giros ≥ 0 frente a
  M0 (sustituye a "> 0"/"≥ 0,25"), **falsas alarmas ≤ 0,5 al año**, mejora total ≥ 0,05 nats con IC > 0.
- **Base PIT v0.4** (`pit_version: "0.4"`) para las dos: las 58 columnas de M1 v1 son idénticas bit a bit en la v0.4
  (test), así que M1 v1 da lo mismo con una u otra matriz. La v0.4 tiene que estar **congelada** (el arnés lo exige).
- **Protección de rama** comprobada por el código antes de abrir (A3-1, arnés v2.2).

## A2. Hipótesis (dos) y corrección

| id | modelo | contraste | modo | ventana |
|---|---|---|---|---|
| H1 | **M1 v1** `m1_logit_axis` (`m1_spec.md` v1.0, sin cambios) | mejora de log-loss blanda de 4 cuadrantes frente a M0 | vintage | 2005-01 → 2021-10 |
| H2 | **M1 v2** `m1v2_logit_axis` (`m1_v2_spec.md` v1.0, sin cambios) | ídem | vintage | 2005-01 → 2021-10 |

- **Holm (k = 2), α = 0,05, unilateral**, sobre `p_h0` de la mejora de log-loss de cada una frente a M0 (bootstrap
  circular por bloques de 12 meses, 5.000 réplicas, semilla 20261015). Familia `principal_holm_k2` en la configuración.
- **Qué se declara:** un modelo **pasa** si cumple TODOS los criterios de A3 **y** su p ajustada por Holm < 0,05. Si
  pasan los dos, se promociona el de mayor mejora media (decisión mecánica, fijada ahora). Si no pasa ninguno, M0 sigue
  siendo el modelo base.
- M1 v2 está **contaminada** por el desarrollo (H-M1-002): la evaluación única es su única prueba limpia.
- Secundarias informativas (no entran en Holm): M1 v2 − M1 v1 pareado; ejes G e I de cada una frente a M0 (familia
  `secundarias_ejes`, Holm aparte, informativa); sensibilidades de §A5.

## A3. Criterio de éxito (cada hipótesis; se exigen TODOS) y su clave en el informe

Clave base: `c = report["frente_al_baseline"]["vintage/<modelo>"]`; detección: `d = report["deteccion_giros_g"]`.

| # | criterio | clave |
|---|---|---|
| 1 | Mejora media frente a M0 **≥ 0,05 nats** y **límite inferior del IC 95 % > 0** | `c.mejora_logloss.mean ≥ 0,05` y `c.mejora_logloss.lo > 0` |
| 2 | **Giros no peor que M0:** mejora en los meses de giro **≥ 0** | `c.cortes.giro.mean ≥ 0` |
| 3 | **Estables:** no empeora más de 0,05 nats | `c.cortes.estable.mean ≥ −0,05` |
| 4 | **Falsas alarmas de G ≤ 0,5 al año** (definición v2.1) | `d["vintage/<modelo>"].falsas_alarmas_por_año ≤ 0,5` |
| 5 | **Mismo signo** de la mejora en 2005-01 → 2014-12 y 2015-01 → 2021-10 | `c.subperiodos_mismo_signo == true` |
| 6 | **Signos** de los coeficientes que deciden iguales a los preregistrados en la ventana y estables en los saltos de vintage (los saltos son anteriores a 2005: esa mitad la decide el desarrollo; Validador A3-6) | `report["signos_coeficientes"]["vintage/<modelo>"].criterio_signos_cumple` |
| 7 | **Holm k = 2:** p ajustada < 0,05 | `report["holm_familias"]["principal_holm_k2"].ajustado[<id>] < 0,05` |

**Advertencia conocida (desarrollo):** M1 v1 tiene la Sahm con el signo contrario al preregistrado en ~100 % de los
cortes ≤ 2004, así que su criterio 6 fallará casi con certeza. Se mantiene tal cual (cambiarlo sería post hoc puro;
Validador §4-1). M1 v1 entra para que la familia cuente las dos especificaciones probadas.

**Promoción a la Etapa 2:** además, detección de giros de G no peor que M0: `c.deteccion_frente_al_comparador.
retraso_pareado_medio ≤ 0` y `censurados_modelo ≤ censurados_comparador`. Con pocos giros en 2005-2021 se lee como
"no empeora", no como prueba.

## A4. Modelos y especificaciones (congeladas en git antes de desbloquear)

| modelo | especificación | variables | parámetros |
|---|---|---|---|
| M0 `m0_calibrated_persistence` | harness.md §8 | — (persistencia calibrada por eje) | eps 1e-3, L2 1,0 |
| M1 v1 `m1_logit_axis` | `m1_spec.md` v1.0 | G: growth_rt, unrate_sahm, baa_spread, eq_ret_6m, curve_10y3m (débil, no decide); I: core_cpi_6m_ann | L2 6,0; pers L2 1,0; eps 1e-3 |
| M1 v2 `m1v2_logit_axis` | `m1_v2_spec.md` v1.0 | G: growth_rt, claims_4w_yoy, curve_min12, baa_gap10y, baa_d6m, eq_ret_6m, sahm_d3m; I estructural: 1,7·(core − 2,9)/0,75 | L2 6,0; pers L2 1,0; eps 1e-3; s = 0,75 |
| persistencia cruda, climatología | harness.md §8 | — | referencias |

- **Arnés:** refit mensual, embargo 6, purga, pesos de madurez, mínimos por eje (120 m, ≥ 2 recesiones, ≥ 8 cambios de
  G), política `principal`, `pit_version: "0.4"`.
- **`test_start` = 1978-07** (primer corte en que el eje G de M1 v2 es elegible en todos los cortes; el de M1 v1 lo es
  desde 1975-06, el eje I con el subyacente desde 1989-10). Los cortes < 2005 no puntúan: dan la trayectoria de los
  coeficientes y `sign_stability`.

## A5. Sensibilidades (misma apertura, se publican siempre, no deciden)

| corrida | qué cambia | modelos |
|---|---|---|
| principal, `latest_truncated` | modo | M1 v1, M1 v2, M0, persistencia, climatología |
| `s_i_050`, `s_i_100` | escala del eje I estructural s = 0,5 / 1,0 (`m1_v2_spec.md` §4) | M1 v2 (variantes), M0 |
| `pesos_uno`, `pesos_excluir` | ponderación de los provisionales recalculados | M1 v1, M1 v2, M0 |
| `s_pit_001_filadelfia` | matriz con Filadelfia prudente | M1 v1, M1 v2, M0 (ninguno usa Filadelfia: debe salir idéntica; comprobación mecánica) |

`incluye: []` (como en la v2, §B-1b): S-PIT-001/002 y los H-MOD no se gastan.

## A6. Muestra, inferencia y alarmas

Como en la v2 (§B-4, §B-5, §B-7): ventana fija 2005-01 → 2021-10 (`allow_shrink: false`; 202 meses; 2022 fuera por
provisional), subperiodos 2005-14 / 2015-21-10, bootstrap por bloques de 12 (24 como sensibilidad), prueba de signo por
episodio. **Alarma de fuga:** una mejora > 0,25 nats se audita antes de creerla.

## A7. Procedimiento (cuando el usuario lo apruebe; nada de esto está hecho)

1. Validador y Estratega revisan la base PIT v0.4 y M1 v2 (desarrollo). Con ✅: **congelar la v0.4** (B-5, tag
   `pit-v0.4`).
2. Escribir `config/harness/p_eval_base.yaml` (= la sonda `p_eval_base_probe.yaml` con `pit_version: "0.4"`,
   `test_start: 1978-07`, los modelos de A4, `principal: m1v2_logit_axis`, `expected_signs` de los dos, las familias
   `principal_holm_k2` (miembros H1, H2; `p_h0`; métrica `logloss`; comparador M0) y `secundarias_ejes`, y las
   sensibilidades de A5) y commitearla.
3. `python -m src.models.harness --check-protection` (A3-1) y **ensayo en seco** registrado
   (`--dry-run config/harness/p_eval_base.yaml`; también comprueba la protección), commiteado.
4. Añadir a `research/hypotheses.yaml` la entrada `P-EVAL-BASE` (`tipo: evaluacion_holdout`, `incluye: []`,
   `config_arnes: config/harness/p_eval_base.yaml`, `documento: docs/models/p_eval_base_draft.md (v3, aprobado)`).
5. `FKB_HOLDOUT_UNLOCK="EVALUACION-UNICA P-EVAL-BASE"` + `evaluate_holdout("P-EVAL-BASE")`: comprueba otra vez la
   protección de rama, repite el ensayo, consume y ancla en GitHub antes de leer. **Una vez.** Mientras el repositorio
   sea **público** (en privado sin Pro no hay protección de rama → el código se niega).

## A8. Decisiones para el usuario

1. Aprobar este borrador v3 (o cambiarlo) **antes** de ver los resultados de desarrollo de M1 v2, si se quiere que la
   elección no dependa de ellos. (Si se aprueba después, constará en el trial log.)
2. Regla de desempate si pasan las dos (A2): mayor mejora media. ¿De acuerdo?
3. ¿Incluir las sensibilidades `pesos_*` y Filadelfia también para M1 v1 (más corridas, mismas comparaciones)?

---

# §B. Borrador v2 (2026-10-16) — HISTORIA, sustituido por la v3


Escrito **sin mirar ningún dato ≥ 2005** de la etiqueta ni ninguna relación entre variables macro y la etiqueta en
ningún periodo. Lo único que se ha mirado de 2005 en adelante es la **disponibilidad** (sí/no) de las variables de M1
en la matriz congelada, en el ensayo en seco (§9), y está anotado en el trial log.

**Qué cambia frente al borrador v1** (re-auditoría del arnés v2, A2-1):
- Solo **M1 frente a M0**. Los módulos H-MOD salen (decisión del usuario 16-oct, §10).
- M1 es **una** especificación ejecutable por el arnés: `m1_logit_axis` de `m1_spec.md` (eje I con el IPC
  subyacente; §3b justifica por qué no hay épocas).
- Ventana de evaluación, subperiodos, sensibilidades, signos y familia de Holm **escritos en la configuración** y
  comprobados por el **ensayo en seco** del arnés v2.1 (§9) con una sonda de M1 que no usa variables.
- Criterios traducidos a claves concretas del informe del arnés (§6). Detección de giros con la definición v2.1.

## 1. Cómo entra en el arnés (cuando se apruebe)

1. El placebo de M1 con su L2 (`m1_spec.md` §5) no da **ni fuga ni aviso** (reglas del arnés §9b).
2. Se escribe `config/harness/p_eval_base.yaml` = `config/harness/p_eval_base_probe.yaml` con `m1_logit_axis` (y sus
   parámetros de `m1_spec.md` §3) en lugar de la sonda `axis_window_probe`. Nada más cambia.
3. Ensayo en seco con el código y la configuración definitivos, **commiteado**:
   `.venv/bin/python -c "from src.models import harness as H; H.evaluate_holdout('P-EVAL-BASE', dry_run=True)"`
   (o `--dry-run P-EVAL-BASE` cuando ya esté en `hypotheses.yaml`). Su línea `ok` queda en
   `research/holdout/dry_runs.jsonl` con el hash de configuración + código.
4. Se añade a `research/hypotheses.yaml`:

```yaml
- id: P-EVAL-BASE
  registrada: <fecha de aprobación>
  autor: usuario + coordinador (Constructor arnés v2.1)
  estado: preregistrada (sin datos mirados después de 2004)
  tipo: evaluacion_holdout
  incluye: []                      # §1b
  config_arnes: config/harness/p_eval_base.yaml
  documento: docs/models/p_eval_base_draft.md (v2, aprobado)
```

5. Remoto `origin` en GitHub configurado y con sesión (§11). Solo entonces
   `FKB_HOLDOUT_UNLOCK="EVALUACION-UNICA P-EVAL-BASE"` + `evaluate_holdout("P-EVAL-BASE")` puede abrir el
   bloqueado, **una vez**. Antes de gastar nada repite el ensayo en seco y, si falla, se niega (harness.md §4b, §4e).

### 1b. `incluye: []`

- **P-EVAL-MOD, H-MOD-001…004:** fuera (decisión del usuario, §10). No se gastan.
- **S-PIT-001** (Filadelfia prudente antes de 1990): M1 no usa ninguna variable de Filadelfia. La corrida con esa matriz
  se publica como secundaria (§3), pero **no puede contrastar** S-PIT-001. Gastar su id aquí impediría contrastarlo
  más tarde con un modelo que sí use Filadelfia.
- **S-PIT-002 / P-EVAL-S-PIT-002** (Michigan en Δ12m): M1 no usa Michigan. **No aplica** a P-EVAL-BASE; queda para un
  modelo que use `umcsent`/`mich_infl_exp`.

## 2. Hipótesis principal (una)

**M1** (`m1_logit_axis`: dos logísticas binarias por eje con objetivo blando, combinadas como producto; `AxisModel`)
mejora a **M0** (`m0_calibrated_persistence`, persistencia calibrada por eje) en **log-loss blanda de 4 cuadrantes**,
modo **vintage**, en la ventana **2005-01 → 2021-10**.

M1 anida a M0 (β = 0 ⇒ M1 = M0; `m1_spec.md` §1), así que M1 − M0 mide exactamente el valor de las variables.

## 3. Modelos y especificación (congelados en git antes de desbloquear)

M1 es la especificación congelada de `m1_spec.md` v1.0 (H-M1-001), sin ningún cambio:

| eje | variable | inicio de la ventana | signo preregistrado | decide |
|---|---|---|---|---|
| G | `growth_rt` | 1963-11 | + | sí |
| G | `unrate_sahm` | | − | sí |
| G | `baa_spread` | | − | sí |
| G | `eq_ret_6m` | | + | sí |
| G | `curve_10y3m` | | + | **no** (débil; se informa) |
| G | logit de `pers_axis_growth` | | + | sí |
| I | `core_cpi_6m_ann` | 1978-01 (`principal_desde`) | + | sí |
| I | logit de `pers_axis_infl` | | + | sí |

- **Regularización** (`m1_spec.md` §3, fijada a priori): L2 = 6,0 sobre las variables estandarizadas con el
  entrenamiento del corte; L2 = 1,0 sobre el logit de la persistencia y eps = 1e-3 (los de M0); constante sin
  penalizar. Escala de suma del arnés. Cierra la pregunta abierta del borrador v1.
- **Arnés:** refit mensual, embargo 6, purga, peso de madurez de los provisionales recalculados, mínimos por eje (120
  meses, ≥ 2 recesiones NBER conocidas, ≥ 8 cambios de G), política `principal`.
- **Primeros cortes elegibles** (recuento sin ajustar modelos; `m1_spec.md` §2b y Validador v2 §5): eje G 1975-06;
  eje I 1988-06. En la ventana bloqueada los dos ejes son elegibles en todos los cortes (§9).
- **`test_start` = 1975-06.** Los cortes anteriores a 2005 **no puntúan**: sirven para la trayectoria de los
  coeficientes y para `sign_stability` a ambos lados de los saltos de vintage (`growth_rt` 1973-04 y 1981-05;
  `core_cpi_6m_ann` 1996-12).

**Modelos en la misma corrida** (configuración `p_eval_base_probe.yaml` con M1 en lugar de la sonda):

| corrida | modos | modelos | papel |
|---|---|---|---|
| principal | vintage (decide), latest_truncated (sensibilidad de modo) | M1, M0, persistencia cruda, climatología | contraste y referencias |
| `s_pit_001_filadelfia` | vintage, matriz `vintage_filadelfia_prudente` | M1, M0 | secundaria informativa (M1 no usa Filadelfia: debe salir idéntica; es una comprobación mecánica) |
| `pesos_uno` | vintage, provisionales con peso 1 | M1, M0 | sensibilidad de los pesos de madurez |
| `pesos_excluir` | vintage, provisionales excluidos | M1, M0 | sensibilidad de los pesos de madurez |

Todas en la misma apertura de la caja, sobre los mismos meses, y todas se publican siempre.

### 3b. Eje I: por qué el IPC subyacente y no épocas

- **Decisión:** M1 = eje I **solo con `core_cpi_6m_ann`** (ventana fija desde 1978-01). No hay especificación por
  épocas en P-EVAL-BASE.
- **Por qué:**
  1. **El arnés lo soporta tal cual:** una ventana fija por eje. No hace falta código nuevo ni empalmar puntuaciones
     de dos corridas (que es lo que hace `m1_epocas` en desarrollo, y que el arnés no puede ejecutar como un modelo).
  2. **En la ventana bloqueada las épocas no cambian nada.** El empalme "general antes, subyacente después"
     (`m1_spec.md` §2b) solo difiere del subyacente **antes de 1988-06**. Desde 2005-01 los dos son el mismo modelo:
     el subyacente es elegible en todos los cortes, con ≥ 16 años de entrenamiento (de 1978 a 2004).
  3. **La pérdida de 1973-75 en el entrenamiento** (estanflación con IPC general) no importa para predecir
     2005-2021. La ventana desde 1978 incluye el episodio de inflación alta de 1978-81.
  4. Es la decisión de `m1_spec.md` (H-M1-001): "el M1 de P-EVAL-BASE" es `m1_logit_axis`.
- **M1-general** (`m1_logit_axis_hl`) no entra: añadiría una comparación más sin información nueva sobre el
  bloqueado.

## 4. Muestra

- **Ventana de evaluación fija:** `eval_window: [2005-01, 2021-10]`, `allow_shrink: false`. Es el primer mes
  bloqueado y el último mes no provisional de la etiqueta oficial v1.1 (los provisionales oficiales empiezan en
  2021-11; meta de la etiqueta). Son 202 meses de calendario; puntúan los que tienen `weight > 0` (en la etiqueta solo
  vale 0 en 1950-54).
- **Subperiodos:** 2005-01 → 2014-12 y 2015-01 → 2021-10.
- **Nota:** 2022 (el episodio de inflación) queda fuera por provisional. Solo hay 2 recesiones NBER (2008-09 y 2020):
  los episodios se informan, no deciden. Los giros de G en 2005-2021 son pocos: la regla de promoción por detección
  (§6) tiene muy poca potencia y se lee como "no empeora", no como prueba.

## 5. Inferencia

- Bootstrap circular por bloques de 12 meses, 5.000 réplicas, semilla 20261015, IC percentil al 95 %. Bloques de 24
  meses como sensibilidad.
- **La principal no se corrige:** es una sola hipótesis.
- **Familia de Holm preregistrada `secundarias_frente_a_M0`** (informativa, `p_h0`, vintage): M1 frente a M0 en el
  eje G (`ll_g`) y en el eje I (`ll_i`).
- Prueba de signo por episodio, sin los episodios truncados en el borde de la ventana.

## 6. Criterio de éxito (se exigen TODOS) y su clave en el informe

Clave base: `report["frente_al_baseline"]["vintage/m1_logit_axis"]` (= `c`).

| # | criterio | clave del informe |
|---|---|---|
| 1 | Mejora media frente a M0 **≥ 0,05 nats** y **límite inferior del IC > 0** (4 cuadrantes) | `c.mejora_logloss.mean ≥ 0,05` y `c.mejora_logloss.lo > 0` |
| 2 | **Eje G:** mejora de la log-loss binaria > 0 | `c.mejora_ll_g.mean > 0` |
| 3 | **Meses de giro** (etiqueta dura t ≠ t − 5): mejora > 0. **Meses estables:** no empeora más de 0,05 nats | `c.cortes.giro.mean > 0` y `c.cortes.estable.mean ≥ −0,05` |
| 4 | **Mismo signo** de la mejora en los dos subperiodos | `c.subperiodos_mismo_signo == true` |
| 5 | **Signos de los coeficientes** iguales a los preregistrados (§3; los que deciden) en la ventana, y **estables** a ambos lados de los saltos de vintage con ≥ 12 cortes a cada lado | `report["signos_coeficientes"]["vintage/m1_logit_axis"].criterio_signos_cumple == true` |

**Regla de promoción a la Etapa 2:** (1)-(5) **y** detección de giros de G no peor que M0 con la definición v2.1
(harness.md §6):
- `c.deteccion_frente_al_comparador.retraso_pareado_medio < 0`: confirma antes que M0, en los giros que detectan los
  dos;
- `censurados_modelo ≤ censurados_comparador`.

Un nowcast que gana en log-loss y no mejora la detección no se promociona.

## 7. Se informa sin decidir

- Frente a la persistencia cruda: BSS y acierto.
- La sensibilidad `latest_truncated`.
- Las corridas secundarias de §3.
- Los episodios (NBER ± 6, rachas ≥ 6 m, giros de G) con prueba de signo.
- Retraso de detección, censurados y falsas alarmas.
- Calibración por eje; cuadrante y frontera; eje I.
- La familia de Holm `secundarias_frente_a_M0`.
- La correlación de residuos entre ejes (`harness.md` §5b).
- **Alarma de fuga (Estratega; `m1_spec.md` §7):** una mejora frente a M0 > 0,25 nats se audita antes de creerla.

## 8. Placebo de M1 (M2-5)

Antes de registrar: el placebo pareado de M1 con **su** especificación y **su** L2 (`m1_spec.md` §5;
`placebo.model_placebo` del arnés). Las dos reglas están fijadas en el arnés §9b:
- **fuga:** media sobre 20 semillas > 0,02 nats;
- **aviso:** prueba de signo unilateral p < 0,01 o t > 3.

Con fuga o con aviso, P-EVAL-BASE **no se registra** hasta entenderlo.

## 9. Ensayo en seco (M2-2): demostración de que es ejecutable

Con la sonda (`config/harness/p_eval_base_probe.yaml`: misma configuración, `axis_window_probe` en lugar de M1, con las
mismas variables por eje pero **sin usarlas**):

```bash
.venv/bin/python -m src.models.harness --dry-run config/harness/p_eval_base_probe.yaml
```

Resultado: ver `research/holdout/dry_runs.jsonl` (línea del 2026-10-16, `ok: true`) y harness.md §4e.
- **Elegibilidad analítica** en el primer corte bloqueado (2005-01), por corrida, modo, modelo y eje:
  - **sonda/M1:** eje G con 489 meses, ≥ 6 recesiones, ≥ 34 cambios de G (cotas ≤ 2004); eje I con 319 meses, 4
    recesiones y 20 cambios de G. Con `excluir`, 436 y 266 meses;
  - **M0 y climatología:** 595 meses.

  Todos elegibles en todos los cortes de la ventana (los recuentos crecen con el corte).
- **Ensayo de las 4 corridas** en 1993-01 → 2004-12 (≤ 2004), con `allow_shrink: false`. El informe calcula todo lo
  que pide §6: mejora y su IC, eje G, giro/estable, subperiodos, signos con `sign_stability`, detección pareada y la
  familia de Holm.
- **El ensayo encontró un fallo real** (sin abrir nada): con `excluir`, el eje I con el subyacente no es elegible
  hasta ~1992-11, así que un ensayo en 1990-01 → 2004-12 no cubría la ventana. Se corrigió la ventana **del ensayo**,
  no la de la evaluación. En la evaluación real este fallo habría gastado el preregistro.

`evaluate_holdout("P-EVAL-BASE")` exige un ensayo `ok` con el **mismo hash** (configuración definitiva + código) y lo
repite antes de gastar nada.

## 10. Módulos H-MOD: fuera de P-EVAL-BASE (decisión del usuario, 16-oct)

P-EVAL-BASE evalúa **solo el modelo base**. Los módulos H-MOD-001…004 (P-EVAL-MOD) se evaluarán **más adelante, con su
propio preregistro**, cuando tengan historia suficiente. Hoy no podrían evaluarse por dos razones:
- sus variables empiezan en 2003; con 120 meses y ≥ 2 recesiones conocidas, un eje "M1 + módulo" no sería elegible
  hasta ~2021-09;
- su estado en la lista blanca (`modulo_adicional`) no lo admite la política `principal` del arnés. El ensayo en seco
  lo detecta: test `test_dry_run_catches_ineligible_models_and_bad_config` con `dfii10`.

Nota en `research/hypotheses.yaml` (sin cambiar estados). El arnés ya calcula la familia de Holm de P-EVAL-MOD con
`frac_rep_le0` (`holm_families`, M2-4) para cuando llegue.

## 11. Ampliaciones y ancla externa

- **Ampliaciones** (meses posteriores a 2021-10 cuando maduren): necesitarán su propio `P-EVAL-…` con
  `amplia: P-EVAL-BASE` y una ventana **sin solape** con 2005-01 → 2021-10. El arnés lo impone (registro de consumo con
  la ventana; N9).
- **Ancla externa:** el consumo se commitea y se empuja a `origin` (repositorio privado de GitHub), y se comprueba en
  el remoto **antes** de leer nada (harness.md §4b).

## 12. Decisiones para el usuario

1. Aprobar este borrador (o cambiarlo) **antes** de que nadie vea resultados de M1 que puedan inducir cambios.
2. `incluye: []` (§1b). ¿De acuerdo con dejar S-PIT-001/002 sin gastar?
3. ¿Las sensibilidades de L2 de M1 (`m1_logit_axis_l2lo/l2hi`, `m1_spec.md` §6) también en la evaluación única, como
   secundarias? Hoy no están (menos comparaciones).
4. Configurar el remoto de GitHub (harness.md §10).

---
**Nota del coordinador (2026-10-16, decisión del usuario):** criterio de éxito cambiado **antes** de cualquier evaluación del periodo bloqueado: giros ≥ 0 frente a M0, falsas alarmas ≤ 0,5/año, mejora total ≥ 0,05 nats (sustituye "≥ 0,25 nats en giros"). Anotado en `research/trial_log.md` como post hoc respecto a los resultados de desarrollo de M1 v1. El borrador se rehará con esto cuando haya M1 v2; **no se gasta el periodo bloqueado en M1 v1**.
