---
documento: especificación a priori de M3, Markov de 2 estados con transiciones variables (TVTP) SOLO para el eje G, con emisión desde el factor coincidente de M2
version: 1.2 (2026-10-24; v1.1 = d1bde77, v1.0 = 1a5f1f9. Las tres congeladas ANTES de cualquier contacto con la etiqueta PARA M2/M3/pool y empujadas antes de implementar; cambios en §9)
fecha: 2026-10-24
hipotesis: H-M3-001 (research/hypotheses.yaml) — DECLARADA CONTAMINADA (post hoc respecto a M1 v1/v2; ver §0)
equivale_a: "H-M2-001 / m2_tvtp_g" de la revisión del Estratega (docs/reviews/2026-10-23_estratega_macro_m1v2.md §3.1), con la emisión del Investigador (docs/research/2026-10-23_mejoras_nowcast_regimen.md §3.3)
papel: COMPONENTE del pool (docs/models/pool_spec.md). Frente a M0 y frente a su referencia de transiciones constantes solo se informa (fuera de Holm)
codigo: src/models/regime_components.py (esqueleto y constantes; sin implementar); implementación futura en src/models/models_tvtp.py
tests: tests/test_regime_components.py (solo datos sintéticos)
datos: base PIT v0.4 CONGELADA (tag pit-v0.4) + la emisión de M2 (m2_structural_spec.md); desarrollo solo ≤ 2004-12
depende_de: m2_structural_spec.md v1.3 (factor y Ĝ en tiempo real; en la versión que resulte de S-PIT-001, M2 §2), arnés v2.4 (§8 de M2 y §8 de aquí)
revisiones: docs/validation/2026-10-24_specs_pool_v4.md (M-1, M-4, B-1, B-4, B-5), docs/reviews/2026-10-24_estratega_macro_specs_pool.md (§2.4)
---

# M3: Markov TVTP del eje G (especificación a priori)

Se escribe, se commitea y se empuja **antes** de cualquier contacto con la etiqueta **para M2/M3/pool** y antes de
implementar. **Una sola
pasada de desarrollo**; no se itera. Cambios técnicos posteriores en §9.

## 0. Contaminación declarada

- La familia (Markov con transiciones variables; Filardo 1994, Diebold-Lee-Weinbach 1994) la propone el Estratega el
  16-oct tras M1 v1; la especificación concreta, el 23-oct tras M1 v2. Las variables de transición se eligen con lo
  visto en M1 v2 (fuera `sahm_d3m`; `baa_gap10y` fuera por decisión del usuario).
- La emisión desde el factor coincidente (Chauvet-Piger 2008) la propone el Investigador el 23-oct.
- A diferencia de M2, M3 **sí estima con la etiqueta** (transiciones y emisiones supervisadas, calibración). Con ≈ 8-10
  transiciones por sentido en cada ventana de entrenamiento, las previas mandan (§3).
- Cuenta como un ensayo; su referencia `m3_ctp_g` cuenta como otro.

## 1. Hipótesis H-M3-001

> Un filtro de Markov de 2 estados (G alto / G bajo, **definidos por la etiqueta**) anclado en la persistencia PIT,
> con emisión desde el nowcast en tiempo real del factor coincidente de M2 y probabilidades de transición que dependen
> de la curva, del crédito y de la bolsa (γ ≥ 0), mejora la log-loss del eje G frente a M0 **y** frente al mismo
> filtro con transiciones constantes.

- **Mecanismo:** el estado de G es muy persistente (por eso M0 es fuerte); el riesgo de que cambie sube con una
  inversión reciente de la curva y con el empeoramiento del crédito (salida de G alto), y la recuperación se acelera
  con la compresión del crédito y el rebote de la bolsa (salida de G bajo). La emisión coincidente confirma o no el
  cambio: la bolsa ya no puede producir sola un "falso amanecer".
- **Signos impuestos** (no solo comprobados): γ1…γ4 ≥ 0 en la forma de §3. Como el signo no puede salir al revés, lo
  que se contrasta es si cada γ **se separa de 0**: criterio 8 de P-EVAL-BASE v4 (§5; decisión del usuario 24-oct).

## 2. Estados, datos y emisión

- **Estados** S<sub>s</sub> ∈ {A = G alto, B = G bajo} = etiqueta dura del eje G **recalculada con datos ≤ T**
  (p<sub>g_high</sub> ≥ 0,5 → A), en los meses de entrenamiento que da el arnés (embargo 6, purga), con los pesos de
  madurez. Supervisado; no un Hamilton sin supervisión.
- **Emisión** x<sub>s</sub> = **Ĝ<sup>rt</sup><sub>s</sub>**: la media del nowcast estructural de M2 para el mes s,
  calculada **en la fecha de decisión de s** (datos conocidos en s: niveles `levels_at(s)`, `claims_4w_yoy` y
  `philly_neworders` ≤ s), con los parámetros del factor vigentes en el corte T (estimados con datos ≤ T). Es el factor
  de M2 llevado a las unidades de la etiqueta (pesos, tendencia, σ<sub>i</sub>): los estados son "por encima o por
  debajo de la tendencia", no recesiones NBER. Se cachea por (modo, s, versión de parámetros).
  - **Coherencia con M2 (v1.1, B-4):** para s = m (el mes de la fila de decisión) la emisión es **exactamente** el Ĝ
    de M2 en ese corte (mismos datos y parámetros). Para s < m (meses filtrados y de entrenamiento) usa los parámetros
    del factor vigentes en el corte m, no los del corte s: es PIT (todo ≤ m) pero **no coincide** con la predicción
    fuera de muestra que M2 produjo en el corte s. Es deliberado: una sola versión de parámetros por corte.
  - En entrenamiento y en predicción la emisión es la misma cantidad en tiempo real (no el suavizado con datos
    posteriores), así que su ruido entra en la varianza de emisión de forma natural.
- **Variables de transición** (matriz PIT v0.4, estado `principal`, desde 1953-54): `curve_min12`, `baa_d6m`,
  `eq_ret_6m`, estandarizadas con media y desviación (ddof = 0) del entrenamiento del corte; z<sub>s</sub> es el valor
  de la fila de decisión de s y gobierna la transición s−1 → s. **No** entran `baa_gap10y`, `sahm_d3m`, Filadelfia, la
  Sahm en nivel ni la pendiente en nivel.

## 3. Modelo (fijado)

Transiciones mensuales (Λ = logística):

    P(S_s = B | S_{s−1} = A) = Λ(α_A − γ1·z(curve_min12)_s + γ2·z(baa_d6m)_s)      [salida de G alto]
    P(S_s = A | S_{s−1} = B) = Λ(α_B − γ3·z(baa_d6m)_s     + γ4·z(eq_ret_6m)_s)    [salida de G bajo]
    γ1, γ2, γ3, γ4 ≥ 0

Emisión: x<sub>s</sub> | S<sub>s</sub> = k ~ N(μ<sub>k</sub>, ω²) (medias por estado, varianza común), **templada**:
la verosimilitud de cada mes se eleva a **λ = 1/3** (fijo). Ĝ<sup>rt</sup> solapa 8 meses de tasas y el filtro
contaría varias veces la misma información sin templar.

**Estimación (supervisada, en cada corte, todo con datos ≤ T):**
- Transiciones: dos logísticas ponderadas sobre los pares (s−1, s) de meses de entrenamiento consecutivos, una por
  estado de partida; peso del par = peso de madurez de s. Previa normal **N(0; 0,5²)** sobre cada γ (penalización
  2·γ² en escala de suma); α sin penalizar; γ ≥ 0 por cotas (L-BFGS-B). Arranque γ = 0, α = logit de la frecuencia.
- Emisión: μ<sub>A</sub>, μ<sub>B</sub> y ω² = medias y varianza común ponderadas (pesos de madurez). Cerradas.
- Parámetros: 2 α + 4 γ + 2 μ + 1 ω² + 2 de calibración = **11** (el Estratega contaba 15 con emisión bivariante).

**Anclaje PIT y filtro (el punto delicado):**
- Para la fila de decisión m (prueba o entrenamiento), el ancla es el **mes de la persistencia** a = `label_month` de
  la persistencia PIT de esa fila (el mismo que usa M0; h = m − a, normalmente 5). π<sub>a</sub> = P(A) =
  clip(`pers_axis_growth`<sub>m</sub>, 1e-3, 1 − 1e-3).
- Se filtran los meses a+1 … m: predicción con la matriz de transición de z<sub>s</sub> y actualización con la emisión
  templada de x<sub>s</sub> = Ĝ<sup>rt</sup><sub>s</sub>. Todo lo que entra es ≤ m. Nunca se usa la etiqueta de meses
  inmaduros. Resultado: p<sub>filtro,m</sub> = P(S<sub>m</sub> = A | …).

**Calibración** (como M0): P(G alto)<sub>m</sub> = Λ(c + b·logit(clip(p<sub>filtro,m</sub>, 1e-3))), L2 = 1,0 sobre b,
ajustada en el entrenamiento del corte con el objetivo blando p<sub>g_high</sub> y los pesos de madurez, usando
p<sub>filtro</sub> de cada mes de entrenamiento con su propio ancla (de su fila).
- **Dentro de muestra (declarado, v1.1, B-5):** la capa se ajusta con p<sub>filtro</sub> de los meses de
  entrenamiento, calculados con transiciones y emisión estimadas en esos mismos meses. Es algo optimista (M0 hace lo
  mismo con 2 parámetros; M3, con 9 antes de la capa); no se corrige (no hay validación cruzada interna).
- **Optimizador (fijado, v1.1, B-5):** las dos logísticas de transición y la calibración, L-BFGS-B con `maxiter` = 500
  y `gtol` = 1e-8 (como el pool), arranque determinista (transiciones: γ = 0, α = logit de la frecuencia; calibración:
  c = 0, b = 1). Si no converge, se usa el punto final y se anota `fit_converged = false` en el corte.

**Anidamiento:** con γ = 0 y emisión plana (μ<sub>A</sub> = μ<sub>B</sub>) el filtro propaga la persistencia h pasos
con transiciones constantes y la calibración lo lleva a ≈ M0.

## 4. Eje I, interfaz y nombres

- `m3_tvtp_g`: `AxisModel`; eje G como arriba; **eje I = el de M0** (decisión del usuario). `uses_persistence = True`,
  `uses_pit_levels = True` (para la emisión), `axis_features = {"G": ("curve_min12", "baa_d6m", "eq_ret_6m",
  "claims_4w_yoy", "philly_neworders"), "I": ()}` (las dos últimas solo alimentan la emisión de M2).
- **Referencia anidada `m3_ctp_g`** (secundaria, fuera de Holm, cuenta como ensayo): el mismo modelo con γ ≡ 0
  (transiciones constantes). Aísla lo que aportan las transiciones variables: si M3 no supera a `m3_ctp_g`, el
  mecanismo no está demostrado aunque el total gane.
- Emisión, factor y parámetros del factor **compartidos** con M2 (una sola implementación, misma caché): la diferencia
  entre M2 y M3 es "composición continua" frente a "estados discretos con transiciones".

## 5. Ventanas, corridas y controles (desarrollo, ≤ 2004)

- **Orden (v1.1, M-4):** ninguna corrida de M3 empieza antes de que la resolución de S-PIT-001 esté commiteada y
  empujada (`m2_structural_spec.md` §6, paso 6c). M3 usa como emisión **la versión de M2 que resulte** (la principal o
  la de Filadelfia < 1990-07 = NaN); no se corre M3 con la otra. La marca es
  `model_params.m2_struct_g.philly_pre1990_nan` (M2 §2, v1.2, Validador N-6): `m3_tvtp_g`, `m3_ctp_g` y las
  sensibilidades de M3 la heredan de `m2_struct_g` (el arnés la copia; error si alguno declara otra).
- **Ventanas:** las de M2 (`m2_structural_spec.md` §6, misma regla W<sub>G</sub>; la larga es la ventana de M3) y la
  comparable 1989-10 → 2004-12. Mismos ajustes del arnés (refit 1, embargo 6, madurez, `pit_version` 0.4, vintage +
  latest_truncated, `allow_shrink: false`, `test_start` 1956-10).

| corrida | ventana | modelos |
|---|---|---|
| `m3_long` | larga | persistencia, climatología, M0, **m3_tvtp_g**, **m3_ctp_g**, m2_struct_g |
| `m3_m1cmp` | 1989-10 → 2004-12 | M0, m3_tvtp_g, m3_ctp_g, `m1v2_logit_axis` |
| `m3_sens` | larga, vintage | M0, m3_tvtp_g y las sensibilidades de §7 |

- Se informan los cortes del arnés (total, giros/estables, subperiodos, episodios, detección de giros v2.1, falsas
  alarmas, calibración) y el **estudio de eventos por episodio** de `pool_spec.md` §5b (k = −6 … +8 alrededor de los
  giros de G, con M0, M2, M3 y el pool).
- **Criterio de signos (v1.1; decisión del usuario 24-oct; criterio 8 de P-EVAL-BASE v4 A3):** para **cada** j = 1…4
  **por separado**, la fracción de cortes de `m3_tvtp_g` (modo vintage) cuyo mes cae en la ventana con
  **γ<sub>j</sub> > 0,01** debe ser **≥ 0,50**.
  - Umbral 0,01 en unidades de z (efecto de odds ≈ 1 % por desviación típica; por debajo, "pegado a 0"; Estratega
    §2.4). Desigualdad **estricta**: γ = 0 exacto, 1e-10 o 0,01 exacto **no** cuentan.
  - Denominador = cortes de la ventana en que el modelo debía ajustarse; un corte sin coeficientes (no elegible o
    sin ajuste) cuenta como **no cumplido**. **Implementación (v1.2, Validador N-5):** el arnés pasa como denominador
    **todos los meses de corte de `eval_window`** en el modo (los 202 del bloqueado con refit 1), nunca el índice de los
    cortes que tienen coeficientes; el ensayo en seco comprueba que `n_cortes` = número de meses de corte de
    `dry_run_window`. Tests: cortes sin coeficientes y todos los γ = 0 dan `criterio_fraccion_cumple = false`.
  - Sin cláusula de estabilidad en los saltos de vintage (`sign_stability` se sigue informando, no decide). El
    `criterio_signos_cumple` de `expected_signs` **no** es este criterio: con γ ≥ 0 impuesto se cumple casi siempre.
  - Clave nueva del arnés v2.4: `report["signos_coeficientes"]["vintage/m3_tvtp_g"]["fraccion_umbral"]` con, por
    γ, `{umbral, n_cortes, n_sin_coef, frac}`, y `criterio_fraccion_cumple` (todos los frac ≥ 0,50); función de
    referencia `regime_components.gamma_fraction_criterion` (test sintético).
  - **Ventana:** en la evaluación única, 2005-01 → 2021-10 (decide). En desarrollo se calcula igual sobre la ventana
    de la corrida (`m3_long`) y **solo se informa**.
  - Se aplica a un componente: el pool puede fallar P-EVAL-BASE por M3 aunque mejore a M0 (se anota así en el trial
    log). La referencia `m3_ctp_g` (γ ≡ 0) no tiene criterio de signos.
- **Controles antes de la etiqueta real:**
  - **señal plantada:** un TVTP sintético con γ conocidos (p. ej. γ = (1; 0,5; 0,5; 1)) y emisión gaussiana; el
    estimador recupera el signo y el orden de magnitud (tolerancias en el test) con 600 meses;
  - **ruido:** con z = ruido independiente, los γ se encogen hacia 0 y ll(`m3_tvtp_g`) ≤ ll(`m3_ctp_g`) + 0,005 en la
    media de 20 semillas sintéticas;
  - **PIT por truncamiento** del filtro anclado (alterar lo posterior a m no cambia p<sub>filtro,m</sub>);
  - **placebo pareado** (arnés §9b): etiqueta ≤ 2004 barajada en bloques de 24, semillas 1…20, refit cada 12; Δ =
    ll(M0) − ll(M3). **Fuga** si la media > 0,02 nats; **aviso** si p < 0,01 (signo) o t > 3. Con fuga o aviso no se
    corre con la etiqueta real.

## 6. Regla de confirmación 3 m × 80/20 — SOLO métrica secundaria

- **No** se aplica a la probabilidad puntuada (empeoraría la log-loss y añadiría retraso).
- **Definición (fijada; se calcula para todos los modelos de la corrida, M0 incluido):** sobre P(G alto)<sub>t</sub>,
  estado declarado inicial = lado de P en el primer mes de la ventana (≥ 0,5 → alto). Se declara **G bajo** en el
  tercer mes seguido con P ≤ 0,20 estando declarado alto, y **G alto** en el tercero seguido con P ≥ 0,80 estando
  declarado bajo.
- **Métricas:** giros declarados; retraso = mes declarado − mes del giro (giros v2.1 del arnés, sin parpadeos), en los
  giros con una declaración del mismo sentido en [giro − 3, siguiente giro); giros sin declarar (censurados); **giros
  declarados falsos** = declaraciones sin un giro del mismo sentido en [declaración − 6, declaración + 3], por año.
- Es información para leer la decisión dura ("giro declarado"). **No cambia** la definición de falsas alarmas del
  criterio 4 de P-EVAL-BASE (cambiarla sería un cambio de criterio, decisión del usuario).

## 7. Sensibilidades preregistradas (se publican; NO eligen ni entran en el pool)

| id | cambio |
|---|---|
| `m3_tvtp_g_l16`, `m3_tvtp_g_l12` | templado λ = 1/6 y λ = 1/2 |
| `m3_tvtp_g_fac` | emisión = factor en tiempo real f̂<sub>s|s</sub> de M2 (estandarizado) en lugar de Ĝ<sup>rt</sup><sub>s</sub> (la forma literal de Chauvet-Piger) |
| `m3_tvtp_g_nocal` | sin la capa de calibración (P = p<sub>filtro</sub>) |
| modo `latest_truncated` | todas las corridas |

`baa_gap10y` (rebote, *plucking*) **fuera** de la principal y de las sensibilidades (decisión del usuario; contaminada
por M1 v2).

## 8. Qué necesita del núcleo (además de §8 de M2)

1. `label_month` de la persistencia de cada fila (columna `pers_label_month`, ya calculada en `PITData.pers_rows`) en
   las filas de entrenamiento y de prueba.
2. Coeficientes por corte (`coefficients()`: `G:alpha_A`, `G:alpha_B`, `G:gamma1…4`, `G:mu_A`, `G:mu_B`, `G:omega`,
   `G:cal_c`, `G:cal_b`) para el informe de signos y el **criterio 8** (fracción de cortes con γ<sub>j</sub> > 0,01,
   §5; clave `fraccion_umbral`, configuración `sign_fraction` de P-EVAL-BASE v4 A8).
3. La métrica 3 m × 80/20 de §6 en `metrics.py` + informe (`deteccion_declarada_8020`).

## 9. Cambios post hoc (técnicos)

| fecha | cambio | por qué | qué se había visto |
|---|---|---|---|
| 2026-10-24 | **v1.0 → v1.1** (push a priori, antes de implementar y de cualquier contacto con la etiqueta para M2/M3/pool) | (1) §5, §8: criterio de signos = γ<sub>j</sub> > 0,01 en ≥ 50 % de los cortes, cada γ por separado, ventana del bloqueado, clave nueva (decisión del usuario 24-oct; Validador M-1; Estratega §2.4); (2) §5: orden tras la resolución de S-PIT-001 (M-4); (3) §2: coherencia de la emisión con M2 (B-4); (4) §3: calibración dentro de muestra declarada y `maxiter`/`gtol` fijados (B-5); (5) depende de M2 v1.1 (peticiones de paro con f<sub>m</sub> − f<sub>m−12</sub>; el texto de M3 no cambia por ello); (6) estudio de eventos en `pool_spec.md` §5b; (7) nota de proceso completa (B-1) | nada de M2/M3/pool (sin implementación, datos ni corridas) |
| 2026-10-24 | ninguno (nota de proceso, **completada en v1.1**, Validador B-1) | lecturas de la etiqueta del 24-oct **anteriores** al push de v1.0 (09:53:14Z), todas en `development` y ≤ 2004-12 (o caché ≤ 2004; las denegadas son tests de la barrera ≥ 2005), según `research/trials/full/label_access.jsonl` y `research/trials/label_access.jsonl` (horas del registro en local, UTC+2; aquí en UTC): **(1)** suite completa 08:47:38-08:52:20Z (102 accesos, 5 denegados); **(2)** suite completa 08:57:31-09:02:12Z (ídem); **(3)** `src/models/power.py` 09:05:52Z (1 acceso, también en el registro principal: marca de giros ≤ 2004 para la potencia); **(4)** reproducciones de M1 v1 con `record=False` 09:10:59-09:13:25Z y 09:20:10-09:20:14Z (18 accesos); **(5)** suite completa 09:47:59-09:51:07Z (102 accesos, 5 denegados). Ninguna después del push de v1.0 ni hasta el push de v1.1 | (1), (2), (5): nada de M2, M3 ni del pool (no existían); los tests preexistentes solo reproducen M0, baselines, placebos y ensayos en seco ya conocidos desde el 16-oct. (3): las d<sub>t</sub> de M1 y los MDE de `power_holdout.md` **sí informan el diseño** (`sd_mensual`, puerta de gasto, expectativa de A7), declarado en §0. (4): resultados de M1 v1 ya conocidos. La spec ya estaba escrita y no se cambió por ninguna de ellas. "Antes de cualquier contacto con la etiqueta" significa **para M2/M3/pool** |
| 2026-10-24 | **v1.1 → v1.2** (push a priori, antes de implementar nada que lea datos y de cualquier contacto con la etiqueta para M2/M3/pool) | re-auditoría del Validador (`docs/validation/2026-10-24_specs_pool_v4_reaudit.md`): (1) §5, criterio 8: denominador = todos los meses de corte de `eval_window`, nunca el índice de los cortes con coeficientes; tests con cortes sin coeficientes y con γ = 0; el ensayo en seco comprueba `n_cortes` (N-5); (2) §5: la marca de la versión de M2 es `model_params.m2_struct_g.philly_pre1990_nan`, heredada (N-6); (3) depende de M2 v1.2; (4) nota de proceso (N-7, fila siguiente). Modelo, previas, ventanas y criterio: **sin cambio** | nada de M2/M3/pool (sin implementación, datos ni corridas) |
| 2026-10-24 | ninguno (nota de proceso, v1.2, Validador N-7) | lectura de la etiqueta **posterior** al push de v1.1 (10:46:29Z) y anterior al de v1.2: **(6)** suite completa 10:47:11-10:50:19Z (102 accesos ≤ 2004-12, 90 desde la caché, 5 denegados de la barrera ≥ 2005, pytest, `git_head` = `d1bde77`). Ninguna otra entre los dos pushes | nada de M2, M3 ni del pool (no existían); tests preexistentes. Posterior al push de v1.1: no afecta a la prioridad |
| 2026-10-24 | **ventana larga de M3 = W<sub>G</sub> = 1978-10 → 2004-12** (la de M2, misma regla; sonda de elegibilidad, solo recuentos, `research/trials/m2/elegibilidad.json`) | regla de §5 | recuentos; ninguna puntuación ni ningún modelo |
| 2026-10-24 | ninguno de diseño (nota de proceso) | filas añadidas en el commit `1cdd9e7` (empujado 13:07:31Z), **después** de las primeras lecturas de la etiqueta para M2/M3/pool: sonda de elegibilidad (recuentos de la etiqueta recalculada ≤ T, 12:54:51-12:55:47Z) y placebos con la etiqueta ≤ 2004 **barajada** (12:56-13:07Z). Solo contienen (a) las fechas que la propia spec fija por regla tras la sonda (W<sub>G</sub>, ventana del pool), (b) la tabla v(edad) ya empujada a las 12:54:43Z y (c) el resultado del control sintético de M2 | ningún resultado con la etiqueta real; el texto del modelo, previas, ventanas por regla y criterios no cambian. La sobrecobertura de M2 queda como **pregunta para el usuario**, no como cambio |
| 2026-10-24 | ninguno en esta spec (nota) | depende ahora de `m2_structural_spec.md` **v1.3** (σ̂ de M2 con el error conjunto; decisión del usuario sobre Q0, push a priori antes de cualquier corrida con la etiqueta real). La emisión de M3 (Ĝ) y la entrada del pool no cambian de definición | solo sonda (recuentos) y placebos barajados ≤ 2004 |
