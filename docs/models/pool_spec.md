---
documento: especificación a priori del POOL de log-scores {M0, M2 estructural, M3 TVTP} del eje G con recalibración beta (BLP), contraste principal único de P-EVAL-BASE v4
version: 1.2 (2026-10-24; v1.1 = d1bde77, v1.0 = 1a5f1f9. Las tres congeladas ANTES de cualquier contacto con la etiqueta PARA M2/M3/pool y empujadas antes de implementar; cambios en §8)
fecha: 2026-10-24
hipotesis: H-POOL-001 (research/hypotheses.yaml) — DECLARADA CONTAMINADA (elegida el 23-24 oct tras ver M1 v1/v2; ver §0)
origen: decisión del usuario (24-oct): contraste principal = pool de log-scores + recalibración beta, Holm k = 1; docs/research/2026-10-23_mejoras_nowcast_regimen.md §3.1 y §5.6
codigo: src/models/regime_components.py (esqueleto, constantes y la transformación beta; sin implementar el ajuste); implementación futura en src/models/models_pool.py
tests: tests/test_regime_components.py (solo datos sintéticos)
depende_de: m2_structural_spec.md v1.3, m3_tvtp_spec.md v1.2, arnés v2.4 (§6)
revisiones: docs/validation/2026-10-24_specs_pool_v4.md (B-1, B-6, M-3, M-4), docs/reviews/2026-10-24_estratega_macro_specs_pool.md (§3, §4.2)
---

# Pool de log-scores con recalibración beta (especificación a priori)

Se escribe, se commitea y se empuja **antes** de cualquier contacto con la etiqueta **para M2/M3/pool**. **Una sola
pasada de desarrollo**; no se itera ni se elige entre variantes con datos de desarrollo.

## 0. Contaminación declarada

- Herramienta genérica y anterior a nuestros datos (Geweke-Amisano 2011; Hall-Mitchell 2007; Ranjan-Gneiting 2010),
  pero **elegida el 23-24 oct** después de ver que M1 v1/v2 no batían a M0 en desarrollo. Hipótesis post hoc.
- Sus componentes M2 y M3 están contaminados (sus specs, §0). El pool cuenta como **un ensayo más**.
- Elegir el pool como único contraste principal (k = 1) en lugar de dos aspirantes (k = 2) es una **decisión del
  usuario** (24-oct), anotada como tal en P-EVAL-BASE v4.

## 1. Hipótesis H-POOL-001

> La combinación lineal de las probabilidades del eje G de M0, M2 y M3, con pesos estimados solo con las log-scores
> fuera de muestra ya maduras y recalibrada con una transformación beta (BLP), mejora la log-loss blanda de 4
> cuadrantes frente a M0 (el eje I es el de M0 en todos).

- **Mecanismo:** con modelos mal especificados el pool óptimo da peso a varios (Geweke-Amisano); con M0 dentro, el
  pool tiende a no ser peor que M0 salvo por el error de estimar los pesos; mezclar con M0 amortigua los cruces de 0,5
  (falsas alarmas) y reduce la varianza de d<sub>t</sub> (potencia; `power_holdout.md` §4). Un promedio de
  probabilidades calibradas está infradispersado; la beta lo corrige (Ranjan-Gneiting).
- Si con pocos giros el peso va casi entero a M0, el pool ≈ M0 y el contraste fallará: es una respuesta honesta.

## 2. Componentes y entrada

- **Componentes (exactamente 3, en este orden):** k = 0 M0 `m0_calibrated_persistence`, k = 1 `m2_struct_g`, k = 2
  `m3_tvtp_g`, con sus specs congeladas (M2 en la versión que resulte de S-PIT-001, `m2_structural_spec.md` §2);
  la marca `model_params.m2_struct_g.philly_pre1990_nan` la heredan `pool_g` y sus variantes, v1.2, Validador N-6). **No** entran `m3_ctp_g`, M1 v1/v2 ni las sensibilidades.
- **Entrada:** p<sub>k,s</sub> = P(G alto) **fuera de muestra** del componente k para el mes s, la que el walk-forward
  produjo en el corte de s (en tiempo real), en el mismo modo. Nunca una predicción reajustada después. Recorte
  [1e-6, 1 − 1e-6].
- **Eje I:** el de M0 (igual en los tres componentes). P(cuadrante) = P<sub>pool</sub>(G)·P<sub>M0</sub>(I).

## 3. Regla exacta de los pesos y de la beta (recursiva, solo información pasada)

En cada corte m0 (fecha de decisión de m0, refit_every = 1):

1. **Muestra de estimación** S<sub>m0</sub> = meses s con: s ≤ m0 − 6 (embargo del arnés), los tres p<sub>k,s</sub>
   disponibles y objetivo de entrenamiento del corte (etiqueta recalculada con datos ≤ m0: p<sub>g_high,s</sub>,
   peso de madurez ω<sub>s</sub> × `weight`). Ventana **expansiva** desde la primera predicción de M2/M3.
2. **Arranque:** si |S<sub>m0</sub>| < **N<sub>min</sub> = 60** meses, el pool es M0: w = (1, 0, 0), a = b = 1 ⇒
   P<sub>pool</sub> = p<sub>0</sub>.
3. **Si no**, MAP conjunto (BLP de Ranjan-Gneiting estimado de una vez, no en dos pasos):

       P(w, a, b; s) = B_{a,b}( Σ_k w_k·p_{k,s} )                       (B = función de distribución beta regularizada)
       max_{w ∈ simplex, a > 0, b > 0}   Σ_{s∈S} ω_s·[ t_s·ln P + (1 − t_s)·ln(1 − P) ]
                                       + κ·Σ_k m_k·ln w_k                (previa de Dirichlet, α_k = 1 + κ·m_k)
                                       − [ (ln a)² + (ln b)² ] / (2·0,5²)  (previa lognormal centrada en a = b = 1)
       con t_s = p_g_high,s,  m = (1/2, 1/4, 1/4),  κ = 20

   - **Previa de los pesos:** Dirichlet con moda m = (½ M0, ¼ M2, ¼ M3) y κ = 20 (≈ 20 meses de pseudo-evidencia, el
     8 % de una ventana de 240): mantiene los pesos en el interior y encoge hacia una mezcla con M0 dominante.
   - **Previa de la beta:** ln a, ln b ~ N(0; 0,5²): encoge hacia la identidad (a = b = 1).
   - **Optimización determinista:** parámetros libres (v<sub>1</sub>, v<sub>2</sub>, ln a, ln b), w = softmax(0,
     v<sub>1</sub>, v<sub>2</sub>); L-BFGS-B, `maxiter` = 500, `gtol` = 1e-8; arranque en la moda de la previa
     (w = m, a = b = 1). Sin semillas.
4. **Predicción** del mes m0: P<sub>pool,m0</sub> = B<sub>a,b</sub>(Σ w<sub>k</sub>·p<sub>k,m0</sub>) con los
   p<sub>k,m0</sub> de los componentes en ese mismo corte. Recorte [1e-6, 1 − 1e-6].
5. Pesos y beta se **reestiman cada mes** (expansiva, sin olvido): nada de pesos que cambien rápido (Aastveit et al.
   descartado por flexible y contaminado).
6. **Isotónica: prohibida** (sobreajusta con ≈ 300 meses).

**Coeficientes por corte** (para el informe): `G:w_m0`, `G:w_m2`, `G:w_m3`, `G:blp_a`, `G:blp_b`, `G:n_est`.

## 4. La serie d<sub>t</sub> frente a M0 (lo que contrasta P-EVAL-BASE v4)

- d<sub>t</sub> = ll<sub>4</sub>(M0)<sub>t</sub> − ll<sub>4</sub>(pool)<sub>t</sub>, con ll<sub>4</sub> la log-loss blanda de
  4 cuadrantes del arnés frente a la **etiqueta oficial** (caja fuerte), mes a mes en la ventana de evaluación. Como
  el eje I es el mismo, **d<sub>t</sub> es la diferencia de log-loss binaria del eje G** (harness.md §5b), **exacta salvo
  cuando actúa el recorte por cuadrante** `metrics.CLIP` = 1e-4 (v1.1, Validador B-6: con P<sub>pool</sub> = 1e-5 la
  diferencia llega a 1,28 nats en un mes; el recorte del pool, 1e-6, es más fino que el del arnés y se mantiene). El
  criterio 2 de P-EVAL-BASE usa la binaria (`mejora_ll_g`):
  d<sub>t</sub> = −[t ln p<sub>M0</sub> + (1−t) ln(1−p<sub>M0</sub>)] + [t ln P<sub>pool</sub> + (1−t) ln(1−P<sub>pool</sub>)].
- Es la clave `report["frente_al_baseline"]["vintage/pool_g"]["mejora_logloss"]` del arnés: media, IC percentil 95 %
  por bootstrap circular por bloques de **12** meses (24 como sensibilidad), 5.000 réplicas, semilla **20261015**,
  `p_h0` unilateral. La sensibilidad de bloques de 24 es la clave `mejora_logloss_b24` (ya la publica el arnés para
  toda comparación). Se informan además `sd_mensual` de d y su **autocorrelación en los retardos 1-24**
  (`acf_1_24`; Validador M-3.2) (§6-3).
- En los meses con |S| < N<sub>min</sub>, d<sub>t</sub> = 0 por construcción (pool = M0). En el bloqueado no ocurre:
  en 2005-01 hay > 20 años de predicciones fuera de muestra de M2 y M3.

## 5. Ventanas, corridas, sensibilidades y controles (desarrollo, ≤ 2004)

- **Primeras predicciones** de M2/M3: W<sub>G</sub> (regla de `m2_structural_spec.md` §6; ≈ 1978-07…10). **Activación
  del pool:** primer corte con |S| ≥ 60 (≈ W<sub>G</sub> + 66 meses ≈ 1984-01…04); con `pesos_excluir`, +53 meses.
- **Ventana principal del pool (regla):** del primer enero ≥ activación (con la ponderación principal) a 2004-12 (se
  espera 1985-01 → 2004-12, 240 meses); fecha anotada en §8 tras la sonda de elegibilidad. **Comparable:** 1989-10 →
  2004-12. `test_start` = 1956-10 para que los componentes construyan su historia fuera de muestra; refit 1, embargo 6,
  madurez, `pit_version` 0.4, vintage + latest_truncated, `allow_shrink: false`.

| corrida | modelos |
|---|---|
| `pool_dev` (ventana principal) | persistencia, climatología, M0, m2_struct_g, m3_tvtp_g, m3_ctp_g, **pool_g**, variantes de abajo |
| `pool_m1cmp` (1989-10 → 2004-12) | M0, pool_g, m2_struct_g, m3_tvtp_g, `m1v2_logit_axis`, `m1_logit_axis` |
| `pool_pesos_uno`, `pool_pesos_excluir` (vintage) | M0, componentes, pool_g |

**Sensibilidades preregistradas** (se publican siempre; **no eligen**, y elegir entre BLP y beta de Kull con datos de
desarrollo está prohibido):

| id | cambio |
|---|---|
| `pool_g_eq` | pesos iguales (1/3) y sin recalibración |
| `pool_g_lin` | pool lineal MAP (misma previa de pesos) sin beta |
| `pool_g_kull` | beta de Kull et al. (3 parámetros, Λ(c + a·ln p − b·ln(1−p))) sobre el pool lineal MAP, previas a, b como arriba y c ~ N(0; 0,5²) |
| `pool_g_unif` | previa de pesos centrada en (1/3, 1/3, 1/3) |

**Qué se informa** (desarrollo, descriptivo): lo del arnés para pool y componentes (total con IC, giros/estables,
subperiodos, episodios, detección v2.1, falsas alarmas, calibración); **`sd_mensual` de d** del pool frente a la de
cada componente (¿reduce el ruido?, `power_holdout.md` §4); trayectoria de w y (a, b) por corte; 3 m × 80/20
(`m3_tvtp_spec.md` §6). Lectura de potencia (no criterio): si en desarrollo la mejora del pool es < 0,05 nats o su IC
incluye claramente el 0, gastar el bloqueado tiene poca potencia (v4.3, `p_eval_base_v4_draft.md` A7 y `power_holdout.md` §6: ≈ 0,66 con Δ = 0,05 y ≈ 0,41 con Δ = 0,03; umbral de la lectura sin cambio).

### 5b. Estudio de eventos por episodio (v1.1; decisión del usuario 24-oct, C)

- **Qué:** para M2, M3, `m3_ctp_g` y el pool, d<sub>t</sub> = ll(M0)<sub>t</sub> − ll(modelo)<sub>t</sub> (4 cuadrantes =
  eje G), modo vintage, en k = −6 … +8 meses alrededor de **cada giro v2.1 de G** del arnés (A→B y B→A por separado;
  como el C3 del 16-oct), y su media por episodio en tres tramos: **antes** (k = −6 … −1), **entrada/salida**
  (k = 0 … +4) y **después** (k = +5 … +8). Más la media en los meses estables de la ventana. Cada modelo, en las
  corridas donde aparece (M2 en la corrida principal **resuelta** por S-PIT-001, `m2_long` o `m2_long_phnan`, y M3 en
  `m3_long`, desde W<sub>G</sub>, con 1980 y 1981-82; el pool en `pool_dev`, desde su activación; v1.2, Validador
  N-3: las predicciones P1, P4 y P7 sobre M2 se leen en la corrida resuelta).
- **Nada de esto es criterio** ni cambia ninguno: es lectura de desarrollo, que hace comprobables las predicciones
  a priori del Estratega. La "puerta de gasto" (§5) se lee **junto con** estos episodios (Estratega §6-3: la ventana
  del pool solo tiene 1990-91 y 2001).
- **Predicciones a priori** (citadas tal cual de `docs/reviews/2026-10-24_estratega_macro_specs_pool.md` §4.2, commit
  `1b02ae7`, 10:01:25Z del 24-oct, escritas sin ver la etiqueta ni ningún resultado; el informe de desarrollo dirá,
  para cada una, "se cumple / es falsa / no evaluable" con la regla de su columna "falsa si"):

> Con "giro de G" me refiero a los giros v2.1 del arnés. Las fechas de abajo son la cronología **pública** del NBER, que
> sirve de orientación; la entrada y la salida de G pueden adelantarse a ella. d = ll(M0) − ll(modelo), y > 0 significa
> que el modelo es mejor. **Si el diseño funciona:**
>
> | # | episodio | modelo | predicción | falsa si |
> |---|---|---|---|---|
> | P1 | **1980** (pico 1980-01, valle 1980-07; caída y rebote bruscos: controles de crédito, pico de las peticiones en primavera) | M2, M3 | d > 0 en la **entrada** (k = 0 … +4 desde el giro A→B) y en la **salida** (k = 0 … +4 desde B→A). Es el episodio de mayor ganancia por mes, junto con 2001 | d medio ≤ 0 en la entrada o en la salida |
> | P2 | **1981-82** (pico 1981-07, valle 1982-11) | M3 | **entrada:** d > 0 en k = 0 … +4 (`curve_min12` muy invertida). **Antes:** coste de falsa alarma en los meses A de 1980-11 … 1981-06 (d < 0 para M3 y menor para M2). **Salida:** d > 0 (rally desde 1982-08 y compresión del crédito) | d ≤ 0 en la entrada o en la salida de M3 |
> | P3 | **1990-91** (pico 1990-07, valle 1991-03; entrada gradual tras una desaceleración en 1989, recuperación sin empleo) | pool | **entrada:** ganancia pequeña (0 < d < ganancia de 2001). **Salida y 1991-04 … 1992-12:** sin ganancia (d ≈ 0, ≥ −0,05 de media); M3 puede perder por un "falso amanecer" de la bolsa | d medio < −0,05 en 1991-04 … 1992-12, o ganancia en la entrada mayor que en 2001 |
> | P4 | **2001** (pico 2001-03, valle 2001-11; IP cae desde finales de 2000, peticiones al alza, Filadelfia negativa, curva invertida en 2000) | pool, M2, M3 | **entrada:** d > 0 con claridad en k = 0 … +4: la mayor ganancia de la ventana del pool. **Salida (2002-03, sin empleo):** d ≈ 0 | d medio ≤ 0 en la entrada |
> | P5 | **Estables** de la ventana del pool | pool | d entre −0,03 y 0. Las posibles falsas alarmas (1998: LTCM, crédito; 1995) cuestan poco en el pool | d medio < −0,05 en los estables |
> | P6 | **1987** (crack) | M3 | sin falsa alarma: la bolsa no entra en la salida de A | M3 cruza 0,5 hacia "G bajo" a finales de 1987 sin que haya giro |
>
> **Predicciones agregadas (desarrollo):**
> - **P7.** Las ganancias del pool y de M2 se concentran en las **entradas** (A→B), sobre todo las bruscas (1980, 2001).
>   En las salidas solo ganan en las recuperaciones en V (1980, 1982-83).
> - **P8.** Pool − M0 en su ventana: **+0,01 a +0,06 nats**. `sd_mensual` de d del pool ≈ 0,5-0,8 veces la de M2.
> - **P9.** M3 − `m3_ctp_g`: ≤ +0,02 nats en total, con la ganancia concentrada en 1981 (entrada) y 1980/1982 (salida).
> - **P10.** Fracción de cortes con γ > 0,01: **γ1 (curva) ≥ 50 %** con alta probabilidad; γ2 y γ4 en torno al 50 %;
>   **γ3 (crédito, salida de B) < 50 %** con probabilidad ≈ 0,5.
>   - Es un aviso para el usuario: el criterio de signos que eligió puede tumbar el pool por un componente con poco
>     peso.
>   - La decisión está tomada y no la reabro. Solo la cuantifico.
> - **P11.** Pesos del pool en 2004-12: w<sub>M0</sub> ∈ [0,35; 0,7]; w<sub>M2</sub> + w<sub>M3</sub> el resto; la beta
>   con a, b ≥ 1.
> - **Prueba del mecanismo.** Si **ni** 1980 **ni** 2001 muestran ganancia en la entrada (P1 y P4 falsas), el mecanismo
>   (información del mes t sobre la ventana de G) no funciona. Entonces no tiene sentido gastar el bloqueado, sea cual
>   sea la media.

- **Nota (25-oct, posterior a la cita y fuera de ella):** el aviso de P10 sobre el criterio de signos ya no aplica a la
  decisión: en P-EVAL-BASE v4.3 el criterio 8 es **informativo** (decisión del usuario del 25-oct, A1-16 del borrador).
  P10 se sigue evaluando como predicción.

**Controles antes de la etiqueta real:**
- **Sintéticos:** (i) con un componente oráculo y dos ruidosos, los pesos convergen al oráculo; (ii) con tres
  componentes sin información, w → la previa y P<sub>pool</sub> ≈ p<sub>0</sub>; (iii) con un pool infradispersado
  conocido, la beta recupera a > 1, b > 1; (iv) **PIT:** cambiar p<sub>k,s</sub> o la etiqueta de meses s > m0 − 6 no
  cambia los pesos de m0; (v) antes de N<sub>min</sub>, P<sub>pool</sub> = p<sub>M0</sub> bit a bit.
- **Placebo del pool** (no solo de los componentes): etiqueta ≤ 2004 barajada en bloques de 24, semillas 1…20, refit
  cada 12, **toda la pila** (M0, M3 y el pool se reajustan con la etiqueta barajada; M2 no la usa). Δ = ll(M0) −
  ll(pool). **Fuga** si la media > 0,02 nats; **aviso** si p < 0,01 (signo) o t > 3.
- **Alarma de fuga:** una mejora frente a M0 > 0,25 nats se audita (placebo, espía, señal plantada) antes de creerla.

## 6. Qué necesita del núcleo (arnés v2.4)

1. **Modelo apilado** (`StackedAxisModel`, `components = (...)`): el arnés corre antes los componentes en el mismo modo
   y le pasa, en cada corte m0, las predicciones **fuera de muestra** de P(G alto) de cada componente para todos los
   meses < m0 en que existan y para m0, con su mes de corte; comprueba que cada p<sub>k,s</sub> se produjo en el corte
   de s (test).
2. El objetivo de entrenamiento y los pesos de madurez del corte en esos meses (los que ya da a cualquier modelo).
3. `mejora_logloss.sd_mensual` y la métrica 3 m × 80/20 en el informe.

## 7. Orden

1. Este push (junto con M2, M3 y el borrador P-EVAL-BASE v4). 2. Arnés v2.4 + M2, M3 y pool con tests sintéticos.
3. Tabla v(edad) de M2 (sin etiqueta). 4. Sonda de elegibilidad (solo recuentos) → fechas en las §9/§8. 5. Placebos
de M2, M3 y del pool. 6. **Una** corrida de desarrollo de cada configuración, en este orden fijo (v1.1, M-4): M2
(`m2_long`, `s_pit_001`) → **resolución de S-PIT-001 commiteada y empujada** (`m2_structural_spec.md` §6, 6c) → resto
de M2 con la versión resuelta → M3 → pool. Ninguna corrida de M3 o del pool antes de ese push. 7. Validador + Estratega
(specs, desarrollo y P-EVAL-BASE v4) → usuario.

## 8. Cambios post hoc (técnicos) y fechas fijadas por regla

| fecha | cambio | por qué | qué se había visto |
|---|---|---|---|
| — | (aquí irá la ventana principal) | | |
| 2026-10-24 | **Ventana principal del pool = 1985-01 → 2004-12** (sonda de elegibilidad, solo recuentos; `research/trials/m2/elegibilidad.json`): W<sub>G</sub> = 1978-10, activación (|S| ≥ 60, madurez) en 1984-03; con `pesos_excluir`, activación en 1988-08 | regla de §5 (primer enero ≥ activación) | recuentos de meses de entrenamiento ≥ W<sub>G</sub>; ninguna puntuación ni ningún modelo |
| 2026-10-24 | **v1.0 → v1.1** (push a priori, antes de implementar y de cualquier contacto con la etiqueta para M2/M3/pool) | (1) §5b: estudio de eventos por episodio con pool, M2 y M3 y las predicciones a priori del Estratega (decisión del usuario, C); (2) §7: orden con la resolución de S-PIT-001 antes de M3/pool (M-4); (3) §4: d<sub>t</sub> exacta salvo recorte (B-6); `mejora_logloss_b24` y ACF 1-24 de d (M-3); (4) depende de M2/M3 v1.1; (5) nota de proceso completa (B-1). Pesos, previas, beta, N<sub>min</sub> y ventanas: **sin cambio** | nada de M2/M3/pool (sin implementación, datos ni corridas) |
| 2026-10-24 | ninguno (nota de proceso, **completada en v1.1**, Validador B-1) | lecturas de la etiqueta del 24-oct **anteriores** al push de v1.0 (09:53:14Z), todas en `development` y ≤ 2004-12 (o caché ≤ 2004; las denegadas son tests de la barrera ≥ 2005), según `research/trials/full/label_access.jsonl` y `research/trials/label_access.jsonl` (horas del registro en local, UTC+2; aquí en UTC): **(1)** suite completa 08:47:38-08:52:20Z (102 accesos, 5 denegados); **(2)** suite completa 08:57:31-09:02:12Z (ídem); **(3)** `src/models/power.py` 09:05:52Z (1 acceso, también en el registro principal: marca de giros ≤ 2004 para la potencia); **(4)** reproducciones de M1 v1 con `record=False` 09:10:59-09:13:25Z y 09:20:10-09:20:14Z (18 accesos); **(5)** suite completa 09:47:59-09:51:07Z (102 accesos, 5 denegados). Ninguna después del push de v1.0 ni hasta el push de v1.1 | (1), (2), (5): nada de M2, M3 ni del pool (no existían); los tests preexistentes solo reproducen M0, baselines, placebos y ensayos en seco ya conocidos desde el 16-oct. (3): las d<sub>t</sub> de M1 y los MDE de `power_holdout.md` **sí informan el diseño** (`sd_mensual`, puerta de gasto, expectativa de A7), declarado en §0. (4): resultados de M1 v1 ya conocidos. La spec ya estaba escrita y no se cambió por ninguna de ellas. "Antes de cualquier contacto con la etiqueta" significa **para M2/M3/pool** |
| 2026-10-24 | **v1.1 → v1.2** (push a priori, antes de implementar nada que lea datos y de cualquier contacto con la etiqueta para M2/M3/pool) | re-auditoría del Validador (`docs/validation/2026-10-24_specs_pool_v4_reaudit.md`): (1) §5b: M2 en el estudio de eventos desde la corrida resuelta por S-PIT-001 (N-3); (2) §2: marca de la versión de M2 heredada (N-6); (3) depende de M2/M3 v1.2; (4) nota de proceso (N-7, fila siguiente). Pesos, previas, beta, N<sub>min</sub> y ventanas: **sin cambio** | nada de M2/M3/pool (sin implementación, datos ni corridas) |
| 2026-10-24 | ninguno (nota de proceso, v1.2, Validador N-7) | lectura de la etiqueta **posterior** al push de v1.1 (10:46:29Z) y anterior al de v1.2: **(6)** suite completa 10:47:11-10:50:19Z (102 accesos ≤ 2004-12, 90 desde la caché, 5 denegados de la barrera ≥ 2005, pytest, `git_head` = `d1bde77`). Ninguna otra entre los dos pushes | nada de M2, M3 ni del pool (no existían); tests preexistentes. Posterior al push de v1.1: no afecta a la prioridad |
| 2026-10-24 | ninguno de diseño (nota de proceso) | filas añadidas en el commit `1cdd9e7` (empujado 13:07:31Z), **después** de las primeras lecturas de la etiqueta para M2/M3/pool: sonda de elegibilidad (recuentos de la etiqueta recalculada ≤ T, 12:54:51-12:55:47Z) y placebos con la etiqueta ≤ 2004 **barajada** (12:56-13:07Z). Solo contienen (a) las fechas que la propia spec fija por regla tras la sonda (W<sub>G</sub>, ventana del pool), (b) la tabla v(edad) ya empujada a las 12:54:43Z y (c) el resultado del control sintético de M2 | ningún resultado con la etiqueta real; el texto del modelo, previas, ventanas por regla y criterios no cambian. La sobrecobertura de M2 queda como **pregunta para el usuario**, no como cambio |
| 2026-10-25 | ninguno en esta spec (nota) | P-EVAL-BASE **v4.3** (decisiones del usuario D1-D3 del 25-oct): criterio 1 sin el suelo de 0,05 nats; criterio 8 (signos de M3) **informativo**; sin contraste unilateral al 5 %. Pesos, previas, beta, N<sub>min</sub>, ventanas y la serie d de §4: **sin cambio**. Nota añadida tras la cita del Estratega en §5b | estudio de potencia sintético (`research/validation/potencia_holdout/`); ninguna corrida de M3 ni del pool; nada del bloqueado |
| 2026-10-24 | ninguno en esta spec (nota) | depende ahora de `m2_structural_spec.md` **v1.3** (σ̂ de M2 con el error conjunto; decisión del usuario sobre Q0, push a priori antes de cualquier corrida con la etiqueta real). La emisión de M3 (Ĝ) y la entrada del pool no cambian de definición | solo sonda (recuentos) y placebos barajados ≤ 2004 |
