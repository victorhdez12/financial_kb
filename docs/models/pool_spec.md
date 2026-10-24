---
documento: especificación a priori del POOL de log-scores {M0, M2 estructural, M3 TVTP} del eje G con recalibración beta (BLP), contraste principal único de P-EVAL-BASE v4
version: 1.0 (congelada ANTES de cualquier contacto con la etiqueta; se empuja a origin antes de implementar nada que lea datos)
fecha: 2026-10-24
hipotesis: H-POOL-001 (research/hypotheses.yaml) — DECLARADA CONTAMINADA (elegida el 23-24 oct tras ver M1 v1/v2; ver §0)
origen: decisión del usuario (24-oct): contraste principal = pool de log-scores + recalibración beta, Holm k = 1; docs/research/2026-10-23_mejoras_nowcast_regimen.md §3.1 y §5.6
codigo: src/models/regime_components.py (esqueleto, constantes y la transformación beta; sin implementar el ajuste); implementación futura en src/models/models_pool.py
tests: tests/test_regime_components.py (solo datos sintéticos)
depende_de: m2_structural_spec.md v1.0, m3_tvtp_spec.md v1.0, arnés v2.4 (§6)
---

# Pool de log-scores con recalibración beta (especificación a priori)

Se escribe, se commitea y se empuja **antes** de cualquier contacto con la etiqueta. **Una sola pasada de
desarrollo**; no se itera ni se elige entre variantes con datos de desarrollo.

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
  `m3_tvtp_g`, con sus specs congeladas. **No** entran `m3_ctp_g`, M1 v1/v2 ni las sensibilidades.
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
  el eje I es el mismo, **d<sub>t</sub> es exactamente la diferencia de log-loss binaria del eje G** (harness.md §5b):
  d<sub>t</sub> = −[t ln p<sub>M0</sub> + (1−t) ln(1−p<sub>M0</sub>)] + [t ln P<sub>pool</sub> + (1−t) ln(1−P<sub>pool</sub>)].
- Es la clave `report["frente_al_baseline"]["vintage/pool_g"]["mejora_logloss"]` del arnés: media, IC percentil 95 %
  por bootstrap circular por bloques de **12** meses (24 como sensibilidad), 5.000 réplicas, semilla **20261015**,
  `p_h0` unilateral. Se informa además `sd_mensual` de d (§6-3).
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
incluye claramente el 0, gastar el bloqueado tiene una potencia < 30 % (`power_holdout.md` §4).

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
de M2, M3 y del pool. 6. **Una** corrida de desarrollo de cada configuración (M2, M3, pool). 7. Validador + Estratega
(specs, desarrollo y P-EVAL-BASE v4) → usuario.

## 8. Cambios post hoc (técnicos) y fechas fijadas por regla

| fecha | cambio | por qué | qué se había visto |
|---|---|---|---|
| — | ninguno por ahora (aquí irá la ventana principal) | | |
| 2026-10-24 | ninguno (nota de proceso) | antes del push de esta spec se corrió la suite completa (235 tests, 09:47-09:52Z, exigida por el encargo). Sus tests **preexistentes** del arnés (M0, baselines, placebo, ensayo en seco) leen la etiqueta ≤ 2004 en `development` (registro `research/trials/full/label_access.jsonl`) | nada de M2, M3 ni del pool (no existen); la spec ya estaba escrita y no se cambió después |
