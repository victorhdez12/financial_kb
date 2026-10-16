---
documento: especificación a priori de M1 (logística por eje) y del clasificador de reglas (Fase 3, entregable 4)
version: 1.0 (congelada ANTES de correr nada con la etiqueta)
fecha: 2026-10-16
hipotesis: H-M1-001 (research/hypotheses.yaml)
codigo: src/models/models_logit.py (M1), src/models/models_rules.py (reglas), src/models/m1_run.py (placebo, corridas, épocas, coeficientes)
config: config/harness/m1_logit_axis_v1.yaml (principal), m1_logit_axis_v1_long.yaml (ventana larga), *_sens.yaml, *_w_{uno,excluir}.yaml (sensibilidades)
tests: tests/test_models_m1.py
datos: solo ≤ 2004-12 (fase development). Nada ≥ 2005.
depende_de: arnés v2 (commit e58a054; aprobado para desarrollo, docs/validation/2026-10-16_harness_v2.md), etiqueta v1.1, base PIT v0.3
---

# M1 y clasificador de reglas: especificación a priori

Este documento se escribe y se commitea **antes** de correr M1 o las reglas con la etiqueta. Lo único que se ha
calculado antes es el **recuento de elegibilidad** (§2b): meses, recesiones y cambios de G de la etiqueta recalculada
en cada corte, sin ajustar ningún modelo ni mirar ninguna relación variable-etiqueta (anotado en el trial log).
Los resultados irán a un documento aparte (`docs/models/m1_results_dev.md`). **No se itera la especificación mirando
resultados**: un cambio por motivos técnicos se anota como post hoc.

## 1. Estructura (Estratega, revisión del arnés §4 "Conjunto a priori")

Dos logísticas binarias, una por eje, con objetivo blando (`p_g_high`, `p_i_high` de la etiqueta recalculada con datos
≤ T), pesos de madurez del arnés y combinación en producto (`AxisModel`, harness.md §5b):

    P(eje alto) = Λ(c + b · logit(clip(pers_axis, 1e-3)) + Σ_j β_j · (x_j − μ_j) / σ_j)

- `pers_axis`: P(eje alto) de la persistencia PIT, la misma entrada y el mismo recorte que M0. M1 **anida** a M0
  (β = 0 ⇒ M1 = M0), así que M1 − M0 mide el valor de las variables.
- μ_j, σ_j: media y desviación (ddof = 0) de las filas de entrenamiento del corte (ventana expansiva →
  estandarización expansiva). σ = 0 → 1.
- Walk-forward del arnés v2 sin cambios: refit mensual, embargo 6, purga, mínimos de entrenamiento por eje (120 m,
  ≥ 2 recesiones NBER conocidas, ≥ 8 cambios de G), peso de madurez de los provisionales recalculados.

## 2. Variables (lista blanca v0.3, estado `principal` en todas las fechas usadas)

| eje | variable | inicio en la matriz (estado) | signo preregistrado |
|---|---|---|---|
| G | `growth_rt` | 1963-11 (principal) | + |
| G | `unrate_sahm` | 1950-01 (principal) | − |
| G | `baa_spread` | 1953-05 (principal) | − |
| G | `eq_ret_6m` | 1950-01 (principal) | + |
| G | `curve_10y3m` | 1953-05 (principal) | + (débil: se informa, no decide) |
| G | logit de `pers_axis_growth` | 1956-10 | + |
| I | `core_cpi_6m_ann` | 1978-01 (`principal_desde` 1978-01-01; el arnés empieza la ventana ahí) | + |
| I | `headline_cpi_6m_ann` | 1950-01 (principal) | + (solo en la época previa, §2b) |
| I | logit de `pers_axis_infl` | 1956-10 | + |

Comprobado en las dos matrices (vintage y latest_truncated): los siete nombres existen con esos nombres, su estado es
`principal`, y no tienen ningún NaN después de su inicio. **No hay sustituciones.**

### 2b. Épocas del eje I y ventanas fijas

El arnés v2 admite **una** ventana fija por eje (la del inicio más tardío de sus variables) y pide declarar las épocas
como especificaciones separadas (harness.md §5). Por eso:

- **M1 (`m1_logit_axis`)** = eje G de §2 + eje I con el **IPC subyacente**. Es el M1 de P-EVAL-BASE: en el periodo
  bloqueado el subyacente es principal en todos los meses y la energía no mueve I.
- **M1-general (`m1_logit_axis_hl`)** = el mismo eje G + eje I con el **IPC general**. Es la especificación de la
  época anterior al subyacente. Su eje G es idéntico al de M1 (mismas variables, misma ventana, mismas predicciones).
- **M1 por épocas (`m1_epocas`)** = M1-general antes del cambio de época y M1 desde él. Cambio = **1988-06**, el
  primer corte en que el eje I con el subyacente es elegible. Se construye empalmando las puntuaciones mes a mes de
  las dos corridas oficiales y recalculando el informe con `harness.report` (`m1_run.epocas`). No es un modelo
  nuevo: es la regla "subyacente desde que se puede, general antes".

**Primeros cortes elegibles** (recuento previo, sin ajustar modelos; los dos modos dan lo mismo; coinciden con el
Validador v2 §5):

| especificación | primer corte | n | recesiones | cambios de G |
|---|---|---|---|---|
| eje G (5 variables) | **1975-06** | 134 | 2 | 11 |
| eje I, IPC general | 1973-01 | 190 | 3 | 14 |
| eje I, IPC subyacente | **1988-06** | 120 | 2 | 8 |
| reglas (época general / subyacente) | 1975-06 / 1988-06 | | | |

**Ventanas de evaluación fijas** (`allow_shrink: false`; todos los modelos de cada corrida las cubren):

| corrida | ventana | meses | modelos | para qué |
|---|---|---|---|---|
| **principal** `m1_logit_axis_v1` | **1989-10 → 2004-12** (era 1988-06; §9) | 183 | persistencia, climatología, M0, **M1**, M1-general, reglas | M1 frente a M0 (el contraste de P-EVAL-BASE) |
| larga `m1_logit_axis_v1_long` | **1975-06 → 2004-12** | 355 | persistencia, climatología, M0, M1-general, reglas | eje G con 5 recesiones (1980, 1981-82, 1990-91, 2001 y la salida de 1975); M1 por épocas |

Las dos en vintage (principal) y latest_truncated (sensibilidad). `test_start` = 1956-10 en todas (M0 y la
persistencia reproducen la corrida de los baselines v2 en los mismos cortes). Subperiodos: 1988-06 → 1996-12 /
1997-01 → 2004-12 (principal) y 1975-06 → 1989-12 / 1990-01 → 2004-12 (larga). Épocas: las del arnés.

## 3. Regularización (fijada a priori)

- **Variables: L2 = 6,0** sobre los β estandarizados, en la escala de suma del arnés (la misma que M0).
  - Lectura bayesiana: prior normal β ~ N(0, τ²) con **τ = 1** (un movimiento de 1 σ de una variable cambia los
    log-odds del eje en ≤ ~2 con un 95 % de probabilidad a priori: efectos grandes posibles, enormes no).
  - La log-loss suma meses muy autocorrelacionados (la etiqueta de t usa t−3…t+4; las rachas duran ≥ 6 meses). Con
    una **longitud de dependencia k = 12 meses** (la misma que el proyecto ya fijó para el bootstrap por bloques,
    "≥ 2× el embargo; la etiqueta solapa ~9 meses"), la información efectiva es ~1/12 de la nominal.
  - Equivale a L2 = k / (2τ²) = 12 / 2 = **6**. Es fuerte al principio (en 1975-06 el eje G tiene 134 meses: unos 11
    "meses efectivos") y se relaja al crecer la muestra, que es lo que pide el Estratega para pocos episodios por
    variable.
  - No se ajusta con datos de desarrollo. La sensibilidad del Validador sobre M0 (L2 de 0,1 a 10: 0,8107-0,8159) no
    dice nada sobre la de M1 y no se usó.
- **Persistencia: L2 = 1,0** sobre b y **eps = 1e-3**: los de M0, para que M1 anide exactamente a M0.
- **Constante sin penalizar.**
- No se adopta el "eje I casi estructural" del Estratega (b encogido hacia el valor que implica κ). Es una alternativa
  razonable, pero exige fijar ese valor y una escala, y el encargo pide la logística con L2. Queda como posible M1 v2
  preregistrada si el eje I sale mal identificado.

## 4. Clasificador de reglas (`rules_v1`): traducción congelada

Reglas de `src/regime/classify.py` (Fase 1) sobre la matriz PIT v0.3, **sin tocar umbrales**, con la traducción del
Estratega (revisión del arnés §3e). Es un `Model` de 4 cuadrantes.

| regla original (`classify.py`) | traducción a la v0.3 |
|---|---|
| G compuesto = media de z de INDPRO a/a, PAYEMS a/a, PIB t/t, −ΔUNRATE 12 m (z de 120 m) | `growth_rt` (análogo PIT de G de la v0.3: media de ritmos de 3 m frente a su tendencia de 10 años, en MAD) |
| G "up" ⇔ G > 0 y ΔG(6 m) > 0 y Sahm < 0,5 | `growth_rt(t) > 0` y `growth_rt(t) − growth_rt(t−6) > 0` y `unrate_sahm(t) < 0,5` |
| I: histéresis `inflation_state` sobre la subyacente 6 m: > 2,5 % y acelerando → up; < 2,0 % o desacelerando > 0,5 pp → down; si no, mantiene | la **misma función** `inflation_state` importada (no copiada), con aceleración = x(t) − x(t−3) (NaN → 0, como el original) |
| x = IPC subyacente 6 m | x = `core_cpi_6m_ann` cuando el arnés lo admite (120 meses desde 1978-01: corte 1988-06) y `headline_cpi_6m_ann` antes. Mecanismo: `features = (growth_rt, unrate_sahm, headline_cpi_6m_ann, core_cpi_6m_ann)` con la política de épocas de la v1 para modelos de 4 cuadrantes (harness.md §5); al entrar el subyacente la ventana de entrenamiento empieza en 1978-01 |

- **Calibración:** tabla 4 × 4 en cada corte del walk-forward. Estado de las reglas (G up/down × I up/down) →
  distribución de la etiqueta recalculada con datos ≤ T (objetivo blando, pesos de madurez), Dirichlet α = 1:
  12 parámetros libres. Un mes sin estado (falta un eje) recibe la climatología del corte.
- **Historia (t−3, t−6).** El arnés solo pasa al modelo las filas de entrenamiento (≤ corte − 6) y la del mes que
  predice. Cada fila de la matriz es la información publicada en su propia fecha de decisión, así que el modelo
  **memoriza** las filas que ha recibido (todas ≤ t) y calcula los estados con ellas. En los ≤ 5 meses siguientes a
  su primer corte elegible (1975-06…1975-10) y al cambio de época (1988-06…), le faltan las filas de los meses
  m0 − 5…m0 − 1: sin t−6, la condición de ΔG(6 m) se omite (solo signo de `growth_rt` y Sahm); sin t−3, la aceleración
  vale 0 (como en el original); la histéresis mantiene el estado anterior. Es una limitación declarada (necesidad del
  núcleo, §8).
- **Aviso a priori (Estratega):** la regla de I mide **aceleración** y la etiqueta, **nivel** (κ = 2,5 % en PCE
  subyacente, ~2,9 % en IPC). Se espera que falle en el eje I (p. ej. 1981-82: inflación alta y bajando). **No se
  corrige.** Las reglas quedan **fuera del criterio de éxito**: responden a si las reglas de la Fase 1 aportaban algo
  sobre la persistencia y dan continuidad a los informes.

## 5. Placebo pareado de M1 (antes de mirar el resultado real)

Diseño del arnés §9b (`harness.placebo_data`: variables PIT reales, etiqueta oficial ≤ 2004 barajada en bloques de
24 meses), con **la especificación y la L2 de M1** (Validador M2-5):

- **Contraste principal (por especificación: M1 y M1-general):** Δ = log-loss(M0) − log-loss(M1), con la misma
  permutación; 20 semillas (1…20); refit cada 12 meses; mínimo 120 meses (las recesiones y los cambios de G de una
  etiqueta barajada no significan nada: mínimos 0); ventanas 1989-01 → 2004-12 (M1) y 1976-01 → 2004-12 (M1-general),
  después de su primer corte elegible; ponderación "uno" (no hay provisionales en la barajada).
- **Reglas (fijadas ahora):**
  - **fuga** si la media de Δ sobre las 20 semillas > **0,02 nats** (regla del arnés);
  - **aviso de fuga** (regla complementaria del Validador, M2-5) si la prueba de signo unilateral sobre las 20
    semillas da **p < 0,01** (≥ 15 de 20 positivas) **o t > 3**. El aviso obliga a investigar antes de correr M1 con la
    etiqueta real.
  - Se informan también Δ por eje (G, I).
- **Potencia con la L2 de M1** (solo M1-general, ventana más larga): Δ_C = log-loss(M1) − log-loss(M1 + C), con C
  (3 columnas del objetivo barajado, `src/models/placebo.py`) añadida a los dos ejes: ruido, control t−5, t+1 con
  σ = 1 y 2, t con σ = 2 y calendario t−4. Mide si las reglas detectan fugas plantadas con este regularizador.
- **Si el placebo da fuga o aviso**, no se corre M1 con la etiqueta real hasta entenderlo; se documenta.
- Salida: `research/trials/m1_v1/placebo_m1_v1.json`; fila en el trial log (corridas con `record=False`).

## 6. Orden de las corridas (todas al registro de pruebas y al trial log, también las fallidas)

1. Placebo (§5). 2. Corrida principal (`m1_logit_axis_v1.yaml`, `--official`). 3. Ventana larga
(`m1_logit_axis_v1_long.yaml`). 4. M1 por épocas (`m1_run epocas`). 5. Coeficientes (`m1_run analyze`).
6. **Sensibilidades preregistradas** (se publican siempre, **no eligen**): L2 = 2 y 18 (÷3 y ×3) en las dos ventanas
(`*_sens.yaml`, vintage); ponderación de provisionales "uno" y "excluir" (`*_w_*.yaml`, vintage, ventana principal).

Todas desde un `git worktree` limpio en el commit de esta especificación (el núcleo del arnés se está modificando en
paralelo en el árbol principal), con `FKB_TRIALS_DIR` y `FKB_TRIAL_LOG` apuntando al registro del repositorio
principal.

## 7. Qué se informa (desarrollo; nada de esto es el criterio de P-EVAL-BASE)

- Log-loss blanda de 4 cuadrantes y binaria por eje; M1 − M0 con IC por bloques de 12 (y 24) meses.
- Giro / estable; épocas y subperiodos; por cuadrante y frontera; episodios (NBER ± 6, rachas ≥ 6 m, giros de G) con
  prueba de signo.
- Detección de giros de G (retraso) y falsas alarmas, con la definición del arnés v2 (commit e58a054). El Validador
  señaló defectos en esa definición (M2-3), que corrige el arnés v2.1 en paralelo: las cifras de detección de esta
  entrega son **provisionales** y se recalcularán con la v2.1 sobre las mismas predicciones.
- Calibración por eje (tramos de 0,1); correlación de residuos G-I (umbral 0,2, harness.md §5b).
- **Signos y estabilidad de los coeficientes**: por corte; fracción de cortes con el signo preregistrado; media antes
  y después de los saltos de vintage (`harness.sign_stability`, ≥ 12 cortes a cada lado).
- **Alarma de fuga (Estratega):** si M1 bate a M0 por **> 0,25 nats** (4 cuadrantes, vintage), se trata como
  sospecha de fuga y se audita (placebo, espía de columnas y fechas, señal plantada) antes de creerla.

## 8. Lo que necesitaría del núcleo (no se toca aquí)

- Que el arnés pase al modelo la **historia de las variables ≤ t** (filas de meses ya decididos, no solo el
  entrenamiento y el mes predicho), para reglas o variables con retardos sin memoria interna.
- Épocas por eje como especificación del arnés (dos ventanas preregistradas por eje y cambio en una fecha fija), en
  lugar del empalme de puntuaciones de dos corridas.
- `report()` con signos de coeficientes y `sign_stability` (Validador M2-4; en curso en la v2.1).

## 9. Cambios post hoc (técnicos; ninguno tras ver resultados)

| fecha | cambio | por qué | qué se había visto |
|---|---|---|---|
| 2026-10-16 | `m1_run.placebo_seed`: claves `ll_g`/`ll_i` (commit 353ac63) | error de claves; el placebo falló antes de imprimir nada | nada |
| 2026-10-16 | `models_rules.rule_states`: si falta `growth_rt` (o Sahm) en las filas, el estado de G es "sin estado" → climatología del corte | con `test_start` 1956-10 el arnés hace elegibles las reglas con `unrate_sahm` y el IPC general antes de que `growth_rt` tenga 120 meses (~1974); las dos corridas oficiales fallaron con `KeyError` antes de puntuar. No afecta a las ventanas de evaluación (desde 1975-06 `growth_rt` ya está admitido) | nada (fallaron antes de puntuar; anotadas en el trial log) |
| 2026-10-16 | **Ventana principal 1988-06 → 1989-10 → 2004-12** (183 meses); cambio de época de M1 por épocas también en **1989-10**; en la ventana larga, reglas con IPC general en todos los meses (`rules_v1_hl`); en la sensibilidad "excluir", `allow_shrink: true` | el recuento previo (§2b) buscó el **primer** corte elegible y no comprobó que lo siguiera siendo: en vintage la etiqueta recalculada pierde cambios de G en la ventana desde 1978 y el eje I con subyacente (y las reglas por épocas) no son elegibles en 1989-03…09 (6-7 cambios de G < 8). Desde 1989-10 lo son en todos los cortes de los dos modos. Con "excluir" no lo son hasta 1992-11 | nada: las dos corridas fallaron en la comprobación de cobertura, antes de puntuar; las coberturas salen de un recuento sin ajustar modelos |
