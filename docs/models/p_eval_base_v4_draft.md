---
documento: BORRADOR del preregistro de la evaluación única del modelo base (P-EVAL-BASE), versión 4
version: 4.2-borrador (2026-10-24; contraste único pool − M0, Holm k = 1, criterio 1 con IC 95 %, criterio 8 de signos de M3; 4.1 = d1bde77, 4.0 = 1a5f1f9; 4.2: N-5/N-6 del Validador, componentes en v1.2)
fecha: 2026-10-24
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

Los cambios 1-3 y 6-9 son decisiones del usuario **antes** de abrir el bloqueado; se anotan en `research/trial_log.md`
como cambios de diseño posteriores a los resultados de desarrollo de M1 v1/v2 (no del bloqueado).

**Estado de los hallazgos de la v3** (Validador B-8, 24-oct): **M4-1** ejecutable por diseño (A8 + ensayo en seco
A9-5), abierto hasta A9-5; **M4-2** corregido (filas 4, 5 y 10); **M4-3** corregido (sin alternativas condicionales:
el criterio de signos ya está decidido, fila 3).

## A2. Hipótesis (una) y contraste

| id | modelo | contraste | modo | ventana |
|---|---|---|---|---|
| H1 | **`pool_g`** (`pool_spec.md` v1.2, H-POOL-001), con sus componentes M0, `m2_struct_g` (`m2_structural_spec.md` v1.2, H-M2-001, en la versión que resulte de S-PIT-001) y `m3_tvtp_g` (`m3_tvtp_spec.md` v1.2, H-M3-001) | mejora de log-loss blanda de 4 cuadrantes frente a M0 (`m0_calibrated_persistence`): d<sub>t</sub> = ll(M0)<sub>t</sub> − ll(pool)<sub>t</sub> (`pool_spec.md` §4) | vintage | 2005-01 → 2021-10 |

- **Holm con k = 1** (familia `principal_k1`, un miembro: `pool_g` frente a M0, métrica `logloss`, `p_h0`), α = 0,05
  unilateral. Con un solo miembro, Holm es p<sub>h0</sub> < 0,05. Bootstrap circular por bloques de 12 meses, 5.000
  réplicas, semilla 20261015, IC percentil 95 %.
- **Qué se declara:** el pool **pasa** si cumple **todos** los criterios de A3. Si no pasa, M0 sigue siendo el modelo
  base. No hay desempate (una sola hipótesis): la pregunta A8.2 de la v3 desaparece (M4-3).
- El pool y sus componentes están **contaminados** por el desarrollo (H-POOL-001, H-M2-001, H-M3-001): la evaluación
  única es su única prueba limpia.

## A3. Criterio de éxito (se exigen TODOS) y su clave en el informe

Clave base: `c = report["frente_al_baseline"]["vintage/pool_g"]`; detección: `d = report["deteccion_giros_g"]`.

| # | criterio | clave |
|---|---|---|
| 1 | Mejora media frente a M0 **≥ 0,05 nats** y **límite inferior del IC 95 % > 0** | `c.mejora_logloss.mean ≥ 0,05` y `c.mejora_logloss.lo > 0` |
| 2 | **Eje G:** mejora de la log-loss binaria > 0 | `c.mejora_ll_g.mean > 0` |
| 3 | **Giros no peor que M0:** mejora en los meses de giro ≥ 0 | `c.cortes.giro.mean ≥ 0` |
| 4 | **Estables:** no empeora más de 0,05 nats | `c.cortes.estable.mean ≥ −0,05` |
| 5 | **Falsas alarmas de G ≤ 0,5 al año** (definición v2.1, harness.md §6) | `d["vintage/pool_g"].falsas_alarmas_por_año ≤ 0,5` |
| 6 | **Mismo signo** de la mejora en 2005-01 → 2014-12 y 2015-01 → 2021-10 | `c.subperiodos_mismo_signo == true` |
| 7 | **Holm k = 1:** p < 0,05 | `report["holm_familias"]["principal_k1"].ajustado["pool_g"] < 0,05` |
| 8 | **Signos de M3:** para **cada** j = 1…4 por separado, fracción de cortes de `m3_tvtp_g` (vintage) cuyo mes está en 2005-01 → 2021-10 con **γ<sub>j</sub> > 0,01** (estricto) **≥ 0,50**; un corte sin coeficientes cuenta como no cumplido; sin cláusula de vintage (`m3_tvtp_spec.md` §5) | `s = report["signos_coeficientes"]["vintage/m3_tvtp_g"]`: `s.fraccion_umbral["G:gamma<j>"].frac ≥ 0,50` para j = 1…4, es decir `s.criterio_fraccion_cumple == true` (clave nueva, arnés v2.4). **No** vale `s.criterio_signos_cumple` (con γ ≥ 0 impuesto se cumple trivialmente) |

- **Criterio 7 redundante con el 1** (Validador M-3): con k = 1, el límite inferior del IC 95 % > 0 ya equivale a
  p ≈ < 0,025, así que "p < 0,05" no añade protección. Se mantiene escrito por coherencia con la familia Holm.
- **Criterio 8 sobre un componente:** el pool puede no pasar por M3 aunque mejore a M0 (Estratega P10: γ3 tiene
  ≈ 50 % de probabilidad de quedar < 50 %). Es la decisión del usuario; se anotará así en el trial log.

**Promoción a la Etapa 2** (además de 1-8): detección de giros de G **mejor** que M0 con la definición v2.1:
`c.deteccion_frente_al_comparador.retraso_pareado_medio < 0` y `censurados_modelo ≤ censurados_comparador`. Con pocos
giros en 2005-2021 tiene poca potencia; se lee como indicio, no como prueba.

## A4. Modelos y especificaciones (congeladas en git antes de desbloquear)

| modelo | especificación | variables | papel |
|---|---|---|---|
| M0 `m0_calibrated_persistence` | harness.md §8 | — | listón y componente |
| `m2_struct_g` | `m2_structural_spec.md` v1.2 (versión resuelta por S-PIT-001) | niveles PIT de INDPRO, PAYEMS, W875RX1, CMRMTSPL; `claims_4w_yoy`, `philly_neworders` | componente |
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

- Ventana fija **2005-01 → 2021-10** (`allow_shrink: false`; 202 meses; desde 2021-11 la etiqueta oficial es
  provisional), subperiodos 2005-01 → 2014-12 / 2015-01 → 2021-10. Bootstrap por bloques de 12; **bloques de 24
  como sensibilidad, publicada siempre**: clave `c.mejora_logloss_b24` (la calcula el arnés en toda comparación,
  `harness._cmp`; no necesita configuración; el ensayo en seco comprueba que está, A8). Prueba de signo por episodio, sin los truncados en el borde.
- **Alarma de fuga:** una mejora > 0,25 nats se audita antes de creerla.

## A7. Potencia: qué se puede esperar (`power_holdout.md`)

- **MDE con 80 % de potencia** (criterio 1 + p < 0,05; k = 1 ≈ k = 2 porque el IC 95 % > 0 ya exige p ≈ < 0,025):
  **≈ 0,12-0,15 nats** si d<sub>t</sub> es tan ruidosa como la de M1 (desv. mensual 0,30-0,36); **≈ 0,07** si el pool
  la reduce a la mitad (supuesto, no medido; el Estratega lo ve optimista si la beta extremiza: ×0,6-0,8); 0,15-0,22 con colas ×1,5 (2008-09, 2020).
- **Umbral observado** para pasar el criterio 1: ≈ 0,10 nats (≈ 0,05-0,07 con ruido ×0,5).
- **Expectativa realista:** lo mejor visto en desarrollo es +0,035 nats (eje G de M1 v2, ventana larga). Con un efecto
  verdadero de 0,04-0,06 la potencia es ≈ 0,23-0,42 con el ruido de M1 y ≈ 0,35-0,67 con ruido ×0,5 (tabla 3.2); con +0,035, ≈
  0,15-0,30. **Lo más probable, aun con un pool que funcione, es "M0 sigue"**. La potencia conjunta con los criterios
  2-8 es menor (el criterio 3 se cumple por azar ≈ 52 % si no hay mejora en giros).
- El tamaño empírico del contraste con efecto 0 es **≥ 5-9 %** (nominal 2,5 %) con ruido ×1 **si la dependencia de d
  no pasa de ≈ 12 meses**, y 0-1 % con ruido ×0,5: el umbral de 0,05 nats lo contiene en parte. Es una **cota
  inferior**: el generador de `power.py` corta la dependencia en 12 meses; con memoria larga el tamaño real es mayor
  (Validador, sintético AR(1): 9,3 % con φ = 0,85 y 19,8 % con φ = 0,95). No se cambia el contraste: la conjunción de
  los criterios 1-8 y el umbral lo bajan (`power_holdout.md` §2).
- **Puerta de gasto (lectura, no criterio):** si en la corrida de desarrollo del pool la mejora es < 0,05 nats o su IC
  incluye claramente el 0, la potencia es < 30 % y se recomienda **no** registrar todavía (decide el usuario).

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
sign_fraction:                            # criterio 8 (A3). Clave nueva del arnés v2.4 → signos_coeficientes[...].fraccion_umbral
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
criterio 8 (`signos_coeficientes["vintage/m3_tvtp_g"].fraccion_umbral` y `criterio_fraccion_cumple`), con `n_cortes` = número de meses de corte de `dry_run_window` para cada γ (v4.2, N-5).

## A9. Condiciones para registrar (todas; nada de esto está hecho)

1. Arnés v2.4 y los modelos M2, M3 y pool implementados según sus specs, con tests sintéticos en verde; Validador ✅.
2. Placebos de M2, M3 y del pool **sin fuga ni aviso**; una corrida de desarrollo ≤ 2004 de cada uno, publicada tal
   cual (sea cual sea el resultado).
3. Revisión del Validador y del Estratega de las specs, del desarrollo y de este borrador.
4. Aprobación del usuario de este texto completo. El criterio de signos ya está decidido (A1-3, criterio 8: decisión
   del usuario 24-oct); no queda ninguna alternativa condicional.
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
