---
documento: BORRADOR del preregistro de la evaluación única del modelo base (P-EVAL-BASE), versión 4
version: 4.3-borrador (2026-10-25; contraste único pool − M0, Holm k = 1; criterio 1 = límite inferior del IC 95 % > 0 sin suelo; criterio 8 INFORMATIVO; componentes: M2 v1.3, M3 v1.2, pool v1.2. 4.2 = 68e66dd, 4.1 = d1bde77, 4.0 = 1a5f1f9)
fecha: 2026-10-24 (v4.3: 2026-10-25)
estado: BORRADOR. NO está en research/hypotheses.yaml y NO abre el periodo bloqueado. Sustituye a la v3
  (docs/models/p_eval_base_draft.md, que queda como historia). Antes de registrarlo, todo lo de §A9.
autor: Constructor, sobre la v3, las decisiones del usuario del 23-24 oct y la revisión del Validador
  (docs/validation/2026-10-23_pit_v0.4_m1v2.md §4); 4.1: revisiones docs/validation/2026-10-24_specs_pool_v4.md
  (Validador) y docs/reviews/2026-10-24_estratega_macro_specs_pool.md (Estratega) + decisiones del usuario del 24-oct
---

# P-EVAL-BASE (borrador v4)

Escrito **sin mirar ningún dato ≥ 2005** de la etiqueta ni de las variables, y **antes** de cualquier corrida de los
componentes del pool con la etiqueta (sus specs se empujan en el mismo commit). El texto está cerrado: no deja
opciones abiertas dentro del preregistro (M4-3). Lo que falta para registrarlo son **condiciones** (§A9), no
decisiones de diseño.

## A1. Qué cambia frente a la v3, y por qué (cada cambio declarado; M4-2)

| # | v3 | v4 | motivo | quién |
|---|---|---|---|---|
| 1 | dos hipótesis (M1 v1, M1 v2) con Holm k = 2 | **una**: el pool `pool_g` frente a M0, k = 1 | contraste principal único; M1 v1/v2 no baten a M0 en desarrollo | usuario, 23-oct (reservar el bloqueado) y 24-oct (pool, k = 1) |
| 2 | M1 v1/v2 en Holm | M1 v1 y v2 **informativas, fuera de Holm** (cuentan como 2 ensayos) | ídem | usuario, 23-oct |
| 3 | criterio 6: signos de los coeficientes (signo de la media + estabilidad por vintage) | **criterio 8**: cada γ<sub>j</sub> de M3 **> 0,01** en ≥ 50 % de los cortes de 2005-01 → 2021-10, por separado, sin cláusula de vintage; clave nueva (A3, A8) | los pesos del pool (simplex), la beta y el factor de M2 (sin etiqueta) no tienen signo preregistrable; los γ de M3 son ≥ 0 por restricción, así que el criterio de la v3 se cumpliría siempre. Lo que sí puede fallar es que un γ se separe de 0. La propuesta 4.0 (retirar el criterio) **no** se aprueba | **usuario, 24-oct** (decisión A; umbral del Estratega; operatividad: Validador M-1) |
| 4 | (v2) "eje G > 0", quitado en la v3 sin declararlo | **recuperado** como criterio 2 | M4-2. Con el eje I = M0 en todos, la mejora de 4 cuadrantes es exactamente la del eje G (harness.md §5b), así que es redundante con el criterio 1, pero se escribe para que no desaparezca en silencio | Constructor (corrige M4-2) |
| 5 | promoción: retraso pareado **≤ 0** (cambio no declarado frente al **< 0** de la v2) | **< 0** (el de la v2) | M4-2: se vuelve al último texto sin cambios no declarados | Constructor (corrige M4-2) |
| 6 | eje I de M1 (estructural en v2) | **eje I = M0** en el pool y en sus componentes | el eje I no es donde está la ganancia; menos comparaciones | usuario, 23-oct |
| 7 | — | `baa_gap10y` fuera de todo modelo del pool | contaminada por M1 v2 (rebote) | usuario, 23-oct |
| 8 | base PIT v0.4 candidata | v0.4 **congelada** (tag `pit-v0.4`) | ✅ del Validador | usuario, 23-oct |
| 9 | criterio 1: ≥ 0,05 nats y límite inferior del **IC 95 %** > 0 | **sin cambio** (se mantiene el 95 %, no se pasa al 90 %) | el bootstrap por bloques ya es algo liberal (≥ 5-9 % de pases con efecto 0, cota inferior; `power_holdout.md` §2); el Validador (M-3) concluye que la decisión queda reforzada | usuario, 24-oct |
| 10 | `test_start` = 1978-07 | **1956-10** | los cortes < 2005 no puntúan; construyen la historia fuera de muestra de M2/M3 que necesita el pool (A4). Declarado aquí (Validador B-7, residuo de M4-2) | Constructor |
| 11 | — | **S-PIT-001** resuelta en desarrollo con regla operativa, antes de M3 y del pool; la versión de M2 resultante es la única de A4 | Validador M-4 (`m2_structural_spec.md` §2, §6) | Constructor |
| 12 | — | componentes en sus specs **v1.1** (M2: peticiones de paro con f<sub>m</sub> − f<sub>m−12</sub>; V<sub>rev</sub> declarado no PIT + sensibilidad PIT) | Estratega (imprescindible 1); Validador M-2; usuario 24-oct (B) | Constructor / usuario |
| 13 | — | **v4.2**: componentes en **v1.2**; marca `model_params.m2_struct_g.philly_pre1990_nan` en A8, heredada; denominador del criterio 8 = todos los meses de corte de `eval_window`, comprobado en el ensayo en seco | Validador N-5, N-6 (re-auditoría 24-oct); sin cambio de criterio ni de diseño | Constructor |
| 14 | — | `m2_struct_g` en la spec **v1.3**: σ̂² = V<sub>conj</sub> + V<sub>rev</sub> (error conjunto medido sin etiqueta) | el control sintético preregistrado de M2 falló (decisión del usuario sobre Q0); cambio a priori, antes de cualquier corrida con la etiqueta real | usuario / Constructor |
| 15 | criterio 1: media ≥ 0,05 nats **y** límite inferior del IC 95 % > 0 | **solo** límite inferior del IC 95 % > 0 (mismo bootstrap); 0,05 nats pasa a efecto mínimo de interés que se informa y no decide | estudio de potencia sintético (`research/validation/potencia_holdout/`, rama `claude/potencia-holdout`): con el ruido que da el pool real (desv. de d ≈ 0,13-0,25, ACF(1) ≈ 0,4-0,6), el suelo de 0,05 quita 0,17-0,26 de potencia con Δ = 0,05-0,07 y apenas cambia el error tipo I (0,5 % → 2,4 %; 1,1 % → 3,9 % en forma reducida; ≤ 8,4 % con dependencia φ = 0,85, igual que hoy) | **usuario, 25-oct (D1)**, a propuesta del Validador |
| 16 | criterio 8 (signos de M3) **decide** (fila 3, decisión A del usuario del 24-oct) | criterio 8 **informativo**: se calcula y se publica (`criterio_fraccion_cumple`, `fraccion_umbral` por γ, y los signos por componente), pero **no decide** | **reabre la decisión A1-3 del 24-oct.** Con las probabilidades a priori del Estratega (P10) pasaba por sí solo con probabilidad ≈ 0,11-0,5 **sea cual sea la mejora del pool** (estudio de potencia, A7): limitaba la potencia sin proteger frente a falsos positivos del pool (no depende de que el pool mejore a M0). Decidido antes de cualquier corrida de M3 o del pool y sin ver el bloqueado | **usuario, 25-oct (D2)** |
| 17 | sonda de configuración de la v3 (`p_eval_base_probe.yaml` con una sonda de M1, `test_start` 1975-06) | sonda = configuración de A8 (`test_start` 1956-10, familia `principal_k1`, `sign_fraction` informativo); declaraciones de A2 (contaminación residual), A3 (marca de giro del criterio 3), A6 (202 meses; prueba de signo por episodio informativa) y A8 (lectura `notna` del ensayo en seco); A7 con la potencia del pool real; versiones de los componentes en la cabecera | hallazgos 5-15 del Validador (revisión del 25-oct); sin cambio de criterio | Constructor/Validador |
| — | — | **no** se adopta un contraste unilateral al 5 % (el bootstrap b12/b24 unilateral da un error tipo I del 6-13 %) | estudio de potencia | **usuario, 25-oct (D3)** |

Los cambios 1-3, 6-9, 15 y 16 son decisiones del usuario **antes** de abrir el bloqueado; se anotan en
`research/trial_log.md` como cambios de diseño posteriores a los resultados de desarrollo de M1 v1/v2 y de `m2_long`
(no del bloqueado). El 16 reabre una decisión anterior (la A del 24-oct) y se anota como tal.

**Estado de los hallazgos de la v3** (Validador B-8, 24-oct): **M4-1** ejecutable por diseño (A8 + ensayo en seco
A9-5), abierto hasta A9-5; **M4-2** corregido (filas 4, 5 y 10); **M4-3** corregido (sin alternativas condicionales:
el criterio de signos está decidido: fila 3, reabierta en la fila 16 → informativo).

## A2. Hipótesis (una) y contraste

| id | modelo | contraste | modo | ventana |
|---|---|---|---|---|
| H1 | **`pool_g`** (`pool_spec.md` v1.2, H-POOL-001), con sus componentes M0, `m2_struct_g` (`m2_structural_spec.md` v1.3, H-M2-001, en la versión que resulte de S-PIT-001) y `m3_tvtp_g` (`m3_tvtp_spec.md` v1.2, H-M3-001) | mejora de log-loss blanda de 4 cuadrantes frente a M0 (`m0_calibrated_persistence`): d<sub>t</sub> = ll(M0)<sub>t</sub> − ll(pool)<sub>t</sub> (`pool_spec.md` §4) | vintage | 2005-01 → 2021-10 |

- **Holm con k = 1** (familia `principal_k1`, un miembro: `pool_g` frente a M0, métrica `logloss`, `p_h0`), α = 0,05
  unilateral. Con un solo miembro, Holm es p<sub>h0</sub> < 0,05. Bootstrap circular por bloques de 12 meses, 5.000
  réplicas, semilla 20261015, IC percentil 95 %.
- **Qué se declara:** el pool **pasa** si cumple **todos** los criterios de A3. Si no pasa, M0 sigue siendo el modelo
  base. No hay desempate (una sola hipótesis): la pregunta A8.2 de la v3 desaparece (M4-3).
- El pool y sus componentes están **contaminados** por el desarrollo (H-POOL-001, H-M2-001, H-M3-001): la evaluación
  única es su única prueba limpia.
- **Contaminación residual (v4.3, declarada; no se puede corregir):** quienes diseñan conocen la historia pública de
  2005-2021 (2008-09, 2020), que es la del bloqueado. Algunas elecciones (p. ej. las peticiones de paro y Filadelfia
  como datos del mes t) pueden estar influidas por ese conocimiento general, aunque ningún dato ≥ 2005 de la etiqueta
  ni de las variables se ha usado para elegir nada.

## A3. Criterio de éxito (se exigen los criterios 1-7; el 8 es informativo) y su clave en el informe

Clave base: `c = report["frente_al_baseline"]["vintage/pool_g"]`; detección: `d = report["deteccion_giros_g"]`.

| # | criterio | clave |
|---|---|---|
| 1 | **Límite inferior del IC 95 % > 0** de la mejora media frente a M0. Se informa además si la media alcanza **0,05 nats** (efecto mínimo de interés), pero eso **no decide** (A1-15) | `c.mejora_logloss.lo > 0` |
| 2 | **Eje G:** mejora de la log-loss binaria > 0 | `c.mejora_ll_g.mean > 0` |
| 3 | **Giros no peor que M0:** mejora en los meses de giro ≥ 0. Mes de giro = la etiqueta dura de **4 cuadrantes** en t distinta de la de t − 5 (`metrics.month_cuts`, lag 5): incluye los cambios del eje I, donde la d del eje G no tiene por qué ser positiva (declarado, v4.3) | `c.cortes.giro.mean ≥ 0` |
| 4 | **Estables:** no empeora más de 0,05 nats | `c.cortes.estable.mean ≥ −0,05` |
| 5 | **Falsas alarmas de G ≤ 0,5 al año** (definición v2.1, harness.md §6) | `d["vintage/pool_g"].falsas_alarmas_por_año ≤ 0,5` |
| 6 | **Mismo signo** de la mejora en 2005-01 → 2014-12 y 2015-01 → 2021-10 | `c.subperiodos_mismo_signo == true` |
| 7 | **Holm k = 1:** p < 0,05 | `report["holm_familias"]["principal_k1"].ajustado["pool_g"] < 0,05` |
| 8 | **INFORMATIVO (v4.3, A1-16; no decide).** **Signos de M3:** para **cada** j = 1…4 por separado, fracción de cortes de `m3_tvtp_g` (vintage) cuyo mes está en 2005-01 → 2021-10 con **γ<sub>j</sub> > 0,01** (estricto) **≥ 0,50**; un corte sin coeficientes cuenta como no cumplido; sin cláusula de vintage (`m3_tvtp_spec.md` §5) | `s = report["signos_coeficientes"]["vintage/m3_tvtp_g"]`: `s.fraccion_umbral["G:gamma<j>"].frac ≥ 0,50` para j = 1…4, es decir `s.criterio_fraccion_cumple == true` (clave nueva, arnés v2.4). **No** vale `s.criterio_signos_cumple` (con γ ≥ 0 impuesto se cumple trivialmente) |

- **Criterio 7 redundante con el 1** (Validador M-3): con k = 1, el límite inferior del IC 95 % > 0 ya equivale a
  p ≈ < 0,025, así que "p < 0,05" no añade protección. Se mantiene escrito por coherencia con la familia Holm.
- **Tamaño real del criterio 1** (estudio de potencia, A7): el bootstrap por bloques de 12 es liberal; con efecto 0 el
  límite inferior del IC 95 % queda > 0 en el 2-5 % de las evaluaciones con la dependencia vista en desarrollo y en el
  ≈ 8-9 % con φ = 0,85. Se publica como sensibilidad el contraste HAC EWC unilateral (A6), que no decide.
- **Criterio 8 informativo (v4.3, A1-16):** se calcula, se publica y el ensayo en seco comprueba que la clave existe
  (A8), pero **no entra** en la decisión: el pool pasa o no por los criterios 1-7. Recae en un componente (M3) y no
  depende de que el pool mejore a M0 (Estratega P10: γ3 tiene ≈ 50 % de probabilidad de quedar < 50 %).

**Promoción a la Etapa 2** (además de 1-7): detección de giros de G **mejor** que M0 con la definición v2.1:
`c.deteccion_frente_al_comparador.retraso_pareado_medio < 0` y `censurados_modelo ≤ censurados_comparador`. Con pocos
giros en 2005-2021 tiene poca potencia; se lee como indicio, no como prueba.

## A4. Modelos y especificaciones (congeladas en git antes de desbloquear)

| modelo | especificación | variables | papel |
|---|---|---|---|
| M0 `m0_calibrated_persistence` | harness.md §8 | — | listón y componente |
| `m2_struct_g` | `m2_structural_spec.md` v1.3 (versión resuelta por S-PIT-001) | niveles PIT de INDPRO, PAYEMS, W875RX1, CMRMTSPL; `claims_4w_yoy`, `philly_neworders` | componente |
| `m3_tvtp_g` | `m3_tvtp_spec.md` v1.2 | emisión de M2; transiciones `curve_min12`, `baa_d6m`, `eq_ret_6m` | componente |
| **`pool_g`** | `pool_spec.md` v1.2 | predicciones fuera de muestra de los tres | **H1** |
| `m3_ctp_g` | `m3_tvtp_spec.md` §4 | como M3 con γ = 0 | informativa |
| `m1_logit_axis`, `m1v2_logit_axis` | `m1_spec.md`, `m1_v2_spec.md` | las suyas | informativas, fuera de Holm |
| persistencia cruda, climatología | harness.md §8 | — | referencias |

- **Arnés v2.4** (las extensiones de `m2_structural_spec.md` §8, `m3_tvtp_spec.md` §8 y `pool_spec.md` §6, validadas),
  refit mensual, embargo 6, purga, pesos de madurez, mínimos por eje (120 m, ≥ 2 recesiones, ≥ 8 cambios de G),
  política `principal`, `pit_version: "0.4"` (congelada).
- **`test_start` = 1956-10.** Los cortes < 2005 no puntúan: construyen la historia fuera de muestra de M2 y M3 que
  necesita el pool (1978 → 2004) y la trayectoria de pesos y coeficientes. El eje G de M1 v2 es elegible desde
  1978-07 y el de M1 v1 desde 1975-06; con este `test_start` M1 v1 conserva sus saltos de vintage de 1981-05 (y el de
  1996-12 del subyacente); el de 1973-04 de `growth_rt` cae antes de su primer corte elegible (B4-3: solo afecta a la
  `sign_stability` informativa de M1 v1). Cambio frente a la v3 declarado en A1-10.
- **V<sub>rev</sub>(edad) de M2 no es PIT** (frente a la última vintage; hiperparámetro fijo como s<sub>G</sub>;
  `m2_structural_spec.md` §4, decisión del usuario 24-oct). Su sensibilidad PIT `m2_struct_g_revpit` se publica (A5).

## A5. Sensibilidades (misma apertura; se publican siempre; no deciden)

| corrida | qué cambia | modelos |
|---|---|---|
| principal, `latest_truncated` | modo | todos los de A4 |
| `pesos_uno`, `pesos_excluir` | ponderación de los provisionales recalculados | M0, M2, M3, pool_g |
| variantes del pool | `pool_g_eq`, `pool_g_lin`, `pool_g_kull`, `pool_g_unif` (`pool_spec.md` §5) | junto al pool en la principal |
| componentes | `m2_struct_g_platt`, `_norev`, `_revpit`, `_coinc`, `_ar1`; `m3_tvtp_g_l16`, `_l12`, `_fac`, `_nocal` | junto a M0, vintage |
| `s_pit_001_filadelfia` | matriz `vintage_filadelfia_prudente` | M0, M2, M3, pool_g (M2 usa Filadelfia: aquí **sí** cambia) |

Familias informativas (no deciden): `secundarias_componentes` (M2, M3, `m3_ctp_g` frente a M0, `p_h0`, Holm
aparte), `m3_tvtp_frente_a_ctp` (M3 frente a `m3_ctp_g`) y M1 v1/v2 frente a M0. Sus p son **liberales**, del orden
de ×2-3 (`p_h0 < 0,05` pasa con efecto 0 el 10-15 % de las veces; Validador M-3). Se informan también
`mejora_logloss.sd_mensual`, su ACF 1-24, el estudio de eventos por episodio (`pool_spec.md` §5b), la detección declarada 3 m × 80/20 (`m3_tvtp_spec.md` §6) y la trayectoria de los pesos
del pool.

**`incluye: []`.** S-PIT-001 es una sensibilidad de **desarrollo** (su criterio compara log-loss ≤ 2004;
`hypotheses.yaml`) y se aplica en la corrida de desarrollo de M2 (`m2_structural_spec.md` §2, §6); aquí solo se
publica la corrida con la matriz prudente. S-PIT-002 no aplica (nadie usa Michigan). H-MOD/P-EVAL-MOD, fuera (decisión
del 16-oct).

## A6. Muestra, inferencia y alarmas

- Ventana fija **2005-01 → 2021-10** (`allow_shrink: false`; **202 meses**, no ≈ 250: desde 2021-11 la etiqueta
  oficial es provisional y esos meses no puntúan), subperiodos 2005-01 → 2014-12 / 2015-01 → 2021-10. Bootstrap por bloques de 12; **bloques de 24
  como sensibilidad, publicada siempre**: clave `c.mejora_logloss_b24` (la calcula el arnés en toda comparación,
  `harness._cmp`; no necesita configuración; el ensayo en seco comprueba que está, A8). Prueba de signo por episodio, sin los truncados en el borde (**informativa; no decide**).
- **Sensibilidad HAC (no decide):** p unilateral del contraste de la media de d con HAC EWC (Lazarus-Lewis-Stock-Watson
  2018, ν = ⌊0,4·n^{2/3}⌋ = 13 con n = 202), calculada sobre la d de `scores.parquet` con
  `tests/validation/potencia_holdout_comun.ewc` (sha256 fijado al registrar).
- **Alarma de fuga:** una mejora > 0,25 nats se audita antes de creerla. La auditoría solo puede terminar en dos
  resultados, escritos aquí: (a) sin fuga → el resultado se publica tal cual; (b) fuga demostrada → la evaluación se
  declara **inválida** y el pool **no pasa**. En ningún caso se corrige el código y se vuelve a correr sobre el
  bloqueado.

## A7. Potencia: qué se puede esperar (`power_holdout.md` §6)

- **Criterio de la v4.3 con el pool real** (estudio sintético; pool exactamente como `pool_spec.md` §3, MAP con previa
  de Dirichlet + recalibración beta; 202 meses; 2.000 réplicas por celda, semillas fijas;
  `research/validation/potencia_holdout/estructural_v43.json`). Decisión con los criterios 1-4, 6 y 7 (el 5 no se puede
  simular con d; el 8 ya no decide):

  | mejora verdadera Δ (nats) | 0 | 0,03 | 0,05 | 0,07 | 0,10 |
  |---|---|---|---|---|---|
  | **v4.3** (criterio 1 = IC 95 % lo > 0) | **0,024** (error tipo I) | 0,41 | 0,66 | 0,80 | 0,89 |
  | v4.2 (con el suelo de 0,05 nats), referencia | 0,005 | 0,12 | 0,40 | 0,65 | 0,81 |

  Δ realizadas: −0,0001 / 0,029 / 0,050 / 0,073 / 0,097. **MDE con 80 % de potencia ≈ 0,074 nats** (v4.2: ≈ 0,096).
  Error de Monte Carlo ≤ 0,011. Desviación mensual de d del pool ≈ 0,08-0,25 según Δ (≈ 0,55 veces la de M2) y ACF(1)
  ≈ 0,4-0,6. Con la misma calidad de M2, contrastar **M2 solo** frente a M0 daría 0,03 / 0,11 / 0,22 / 0,32 con Δ de
  M2 = −0,01 / 0,025 / 0,054 / 0,078: el pool es el contraste con más potencia.
- **Sensibilidad (forma reducida, `reducida.json`; potencia con Δ = 0,07 → v4.3):** base (σ 0,22, φ 0,3) 0,87;
  φ = 0,6 0,68; σ = 0,29 0,69; σ = 0,365 (ruido de M2) 0,54; 2 recesiones 0,87; n = 250 0,93; adverso (2 recesiones,
  φ 0,6, σ 0,29, τ 1) 0,47; φ = 0,85 0,48. El error tipo I va del 2,4 % (estructural) y 3,9 % (base) al 5,2 % (φ 0,6)
  y al **8,4 % con φ = 0,85** (igual que la v4.2): con memoria larga, el bootstrap por bloques de 12 es liberal.
- **Criterio 8 (informativo):** con las probabilidades a priori del Estratega (P10) habría pasado por sí solo con
  probabilidad ≈ 0,11-0,5 sea cual sea la mejora del pool; por eso deja de decidir (A1-16). Ya no multiplica la
  potencia.
- **Expectativa realista:** P8 del Estratega espera pool − M0 de +0,01 a +0,06 nats en desarrollo; con Δ = 0,03-0,05 la
  potencia es 0,41-0,66. El criterio 5 (falsas alarmas) no está simulado: la potencia real es algo menor.
- **Cifras de la v4.2 con el ruido de M1** (`power_holdout.md` §3, historia): MDE ≈ 0,12-0,15 nats con desviación
  mensual 0,30-0,36. Ese ruido es el de M1, no el del pool.
- **Puerta de gasto (lectura, no criterio; umbral sin cambio desde la v4.2):** si en la corrida de desarrollo del pool la
  mejora es < 0,05 nats o su IC incluye claramente el 0, se recomienda **no** registrar todavía (decide el usuario).
  Con el criterio de la v4.3, una mejora verdadera de 0,05 da potencia ≈ 0,66 y una de 0,03, ≈ 0,41.

## A8. Ejecutabilidad (corrige M4-1)

La v3 no tenía configuración ni ensayo en seco. En la v4 la configuración queda **fijada aquí** y su ensayo en seco es
**condición para registrar** (§A9). Contenido de `config/harness/p_eval_base.yaml` (se escribe cuando existan los
modelos; cualquier diferencia con esto es un cambio que se declara):

```yaml
name: p_eval_base
prereg_id: P-EVAL-BASE
phase: holdout_evaluation
principal: pool_g
pit_version: "0.4"
models: [pool_g, m0_calibrated_persistence, m2_struct_g, m3_tvtp_g, m3_ctp_g,   # m2_struct_g = versión resuelta por S-PIT-001
         pool_g_eq, pool_g_lin, pool_g_kull, pool_g_unif,
         m1_logit_axis, m1v2_logit_axis, persistence_pit, climatology]
model_params:                              # los de cada spec, sin cambios (m1: L2 6,0; M0: eps 1e-3, L2 1,0; …)
  m0_calibrated_persistence: {eps: 0.001, l2: 1.0}
  m2_struct_g: {philly_pre1990_nan: false}   # S-PIT-001 (M2 §2, 6c): false si no se dispara, true si se dispara.
                                             # Heredado por m3_tvtp_g, m3_ctp_g, pool_g, sus variantes y las
                                             # sensibilidades de M2/M3 (el arnés lo copia; error si otro declara
                                             # un valor distinto). Entra en el hash de configuración (v4.2, N-6)
  climatology: {alpha: 1.0}
modes: [vintage, latest_truncated]
refit_every: 1
embargo_months: 6
min_train_months: 120
min_train_recessions: 2
min_train_g_changes: 8
test_start: "1956-10"
test_end: "2021-10"
eval_window: ["2005-01", "2021-10"]
allow_shrink: false
epochs: []
subperiods: [["2005-01", "2014-12"], ["2015-01", "2021-10"]]
feature_policy: principal
provisional_weighting: madurez
baseline: m0_calibrated_persistence
reference: persistence_pit
dry_run_window: ["1993-01", "2004-12"]    # cubre la activación del pool también con `excluir` (≈ 1988-10)
expected_signs:                           # SOLO informativos (decide: false); M1 v1/v2: los de sus specs
  m3_tvtp_g:                              # impuestos (γ ≥ 0): criterio_signos_cumple NO es el criterio 8
    "G:gamma1": {signo: "+", decide: false}
    "G:gamma2": {signo: "+", decide: false}
    "G:gamma3": {signo: "+", decide: false}
    "G:gamma4": {signo: "+", decide: false}
sign_fraction:                            # criterio 8, INFORMATIVO (A3, v4.3): se calcula y se publica; no decide.
                                          # Clave del arnés v2.4 → signos_coeficientes[...].fraccion_umbral
  m3_tvtp_g:
    coefs: ["G:gamma1", "G:gamma2", "G:gamma3", "G:gamma4"]
    threshold: 0.01                       # γ > 0,01 estricto
    min_frac: 0.5                         # cada γ por separado; ventana = eval_window
    missing_counts_as_fail: true          # denominador = TODOS los meses de corte de eval_window (202), nunca el
                                          # índice de los cortes con coeficientes (v4.2, Validador N-5)
# bloques de 24 (A6): mejora_logloss_b24, siempre en el informe (sin clave de configuración)
holm_families:
  - nombre: principal_k1
    modo: vintage
    p: p_h0
    miembros:
      - {id: pool_g, modelo: pool_g, metrica: logloss, comparador: m0_calibrated_persistence}
  - nombre: secundarias_componentes
    modo: vintage
    p: p_h0
    miembros:
      - {id: m2, modelo: m2_struct_g, metrica: logloss, comparador: m0_calibrated_persistence}
      - {id: m3, modelo: m3_tvtp_g, metrica: logloss, comparador: m0_calibrated_persistence}
      - {id: m3_ctp, modelo: m3_ctp_g, metrica: logloss, comparador: m0_calibrated_persistence}
  - nombre: m3_tvtp_frente_a_ctp
    modo: vintage
    p: p_h0
    miembros:
      - {id: tvtp_vs_ctp, modelo: m3_tvtp_g, metrica: ll_g, comparador: m3_ctp_g}
sensitivities:
  - {name: s_pit_001_filadelfia, modes: [vintage], matrix_variant: filadelfia_prudente,
     models: [pool_g, m0_calibrated_persistence, m2_struct_g, m3_tvtp_g], reference: null}
  - {name: pesos_uno, modes: [vintage], provisional_weighting: uno,
     models: [pool_g, m0_calibrated_persistence, m2_struct_g, m3_tvtp_g], reference: null}
  - {name: pesos_excluir, modes: [vintage], provisional_weighting: excluir,
     models: [pool_g, m0_calibrated_persistence, m2_struct_g, m3_tvtp_g], reference: null}
  - {name: componentes_sens, modes: [vintage],
     models: [m0_calibrated_persistence, m2_struct_g_platt, m2_struct_g_norev, m2_struct_g_revpit, m2_struct_g_coinc,
              m2_struct_g_ar1,
              m3_tvtp_g_l16, m3_tvtp_g_l12, m3_tvtp_g_fac, m3_tvtp_g_nocal], reference: null}
who: Constructor
```

El ensayo en seco (harness.md §4e) comprueba en el **primer corte bloqueado** la elegibilidad analítica de cada eje
de cada modelo (M2/M3: ventana del eje G desde 1968-05; pool: N<sub>min</sub> = 60 cumplido) y, en
`dry_run_window` (≤ 2004), que el informe trae **todas** las claves de A3 para `pool_g`, incluida
`holm_familias.principal_k1`, la detección pareada, `mejora_logloss.sd_mensual`, `mejora_logloss_b24` y la clave del
criterio 8 (`signos_coeficientes["vintage/m3_tvtp_g"].fraccion_umbral` y `criterio_fraccion_cumple`; informativo desde la v4.3, pero tiene que estar en el informe), con `n_cortes` = número de meses de corte de `dry_run_window` para cada γ (v4.2, N-5).

**Lectura ≥ 2005 del ensayo en seco (declarada, v4.3):** para la elegibilidad analítica del primer corte bloqueado,
el ensayo en seco lee la **disponibilidad** (solo `notna`, nunca valores) de las variables pedidas en la matriz congelada
entre 2005-01 y ese corte (`harness.holdout_feature_availability`; queda en el registro de accesos). No lee la etiqueta.

## A9. Condiciones para registrar (todas; nada de esto está hecho)

1. Arnés v2.4 y los modelos M2, M3 y pool implementados según sus specs, con tests sintéticos en verde; Validador ✅.
2. Placebos de M2, M3 y del pool **sin fuga ni aviso**; una corrida de desarrollo ≤ 2004 de cada uno, publicada tal
   cual (sea cual sea el resultado).
3. Revisión del Validador y del Estratega de las specs, del desarrollo y de este borrador.
4. Aprobación del usuario de este texto completo. El criterio de signos está decidido (A1-3, reabierto en A1-16:
   criterio 8 informativo, decisión del usuario del 25-oct); no queda ninguna alternativa condicional.
4b. S-PIT-001 resuelta en desarrollo con la regla de `m2_structural_spec.md` §2, commiteada y empujada antes de las
   corridas de M3 y del pool; la versión de M2 resultante queda anotada en su §9 y es la de A4.
5. `config/harness/p_eval_base.yaml` = A8, commiteada; `--check-protection` ok (A3-1); **ensayo en seco registrado
   `ok`** con el hash de configuración + código definitivos, commiteado (M4-1).
6. Entrada `P-EVAL-BASE` en `research/hypotheses.yaml` (`tipo: evaluacion_holdout`, `incluye: []`,
   `config_arnes: config/harness/p_eval_base.yaml`, `documento: docs/models/p_eval_base_v4_draft.md (v4, aprobado)`),
   commiteada y empujada.
7. Repositorio **público** con la protección de rama activa (sin Pro, en privado el código se niega).

Si la aprobación llega después de la corrida de desarrollo del pool (lo previsto), se anota en el trial log que es
posterior a esos resultados (B4-1).

## A10. Procedimiento de apertura (tras A9)

`FKB_HOLDOUT_UNLOCK="EVALUACION-UNICA P-EVAL-BASE"` + `evaluate_holdout("P-EVAL-BASE")`: comprueba otra vez la
protección de rama, repite el ensayo en seco, consume y ancla en GitHub antes de leer. **Una vez.**
Si la ejecución falla **después** de consumir el preregistro (la caja ya se abrió), la evaluación cuenta como gastada:
se publica el error y lo que se haya escrito, el pool **no pasa** y no se repite sin un preregistro nuevo, que declare
lo que se vio.
