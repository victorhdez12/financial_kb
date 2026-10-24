---
documento: especificación a priori de M2, nowcast ESTRUCTURAL del eje G (factor coincidente con ragged edge + composición exacta de Ĝ)
version: 1.0 (congelada ANTES de cualquier contacto con la etiqueta; se empuja a origin antes de implementar nada que lea datos)
fecha: 2026-10-24
hipotesis: H-M2-001 (research/hypotheses.yaml) — DECLARADA CONTAMINADA (post hoc respecto a M1 v1/v2; ver §0)
equivale_a: "H-M2-002 / m2_struct_g" de la revisión del Estratega (docs/reviews/2026-10-23_estratega_macro_m1v2.md §3.2), en la versión del Investigador (docs/research/2026-10-23_mejoras_nowcast_regimen.md §3.2, §3.4)
papel: COMPONENTE del pool (docs/models/pool_spec.md). No es contraste principal: frente a M0 solo se informa (secundaria fuera de Holm)
codigo: src/models/regime_components.py (esqueleto y constantes de esta spec; sin implementar); implementación futura en src/models/models_struct.py
tests: tests/test_regime_components.py (solo datos sintéticos)
datos: base PIT v0.4 CONGELADA (tag pit-v0.4) + niveles PIT de las 4 series de la etiqueta vía PITLabeler.levels_at (§2); desarrollo solo ≤ 2004-12
depende_de: arnés v2.3 (eje G continuo, harness.md §5c) + extensiones v2.4 de §8 (sin implementar); etiqueta v1.1 congelada
---

# M2: nowcast estructural de G (especificación a priori)

Este documento se escribe, se commitea y se empuja a `origin` **antes** de cualquier contacto con la etiqueta (ni
oficial ni recalculada, ni siquiera para contar meses elegibles) y antes de implementar el modelo. La marca de tiempo
del push lo demuestra. **Una sola pasada de desarrollo** (§6); no se itera mirando sus resultados. Un cambio técnico
posterior se anota en §9 con lo que se había visto.

## 0. Contaminación declarada

- La familia (nowcast estructural de G) la propone el Estratega el 23-oct **después** de ver M1 v1 y M1 v2 en
  desarrollo ≤ 2004 (horizonte: 1/3 de G conocido y 2/3 de previsión a 0-4 meses). La versión con factor coincidente y
  *ragged edge* la propone el Investigador el mismo día con literatura anterior a 2005 (Stock-Watson, Kim-Nelson,
  Chauvet-Piger, Camacho-Pérez-Quirós-Poncela; Jacobs-van Norden y Kishor-Koenig para las revisiones).
- La elección de las peticiones de paro y de Filadelfia como indicadores adicionales viene de la lista del Estratega
  (post M1 v2).
- **Atenuante (no exime):** M2 **no ajusta ningún parámetro con la etiqueta**. El factor se estima solo con las
  series (máxima verosimilitud, §3) y la incertidumbre sale del filtro, de las revisiones y de la tendencia (§4). La
  etiqueta recalculada solo se usa para la puntuación del arnés. Lo que está contaminado es el **diseño**, no los
  parámetros.
- Consecuencia: en desarrollo M2 no demuestra nada. La prueba limpia es la evaluación única, y allí M2 entra **solo
  como componente del pool** (P-EVAL-BASE v4, borrador). Cuenta como un ensayo en el registro (Deflated).

## 1. Hipótesis H-M2-001

> Con la información publicada hasta la fecha de decisión t, un factor dinámico de 1 factor sobre las tasas mensuales
> de los 4 indicadores coincidentes de la etiqueta más las peticiones de paro y Filadelfia, con el *ragged edge* real
> de cada serie, prevé las tasas que faltan de la ventana de G(t) (t−3 … t+4). Compuesto **exactamente** como la
> etiqueta (mismo código), da una previsión gaussiana de G(t) cuya probabilidad P(G alto) = Φ(Ĝ/√(σ̂² + s_G²))
> mejora la log-loss del eje G frente a M0.

- **Mecanismo:** G(t) es una media triangular (1, 2, 3, 3, 3, 3, 2, 1)/18 de las tasas mensuales de t−3 a t+4 frente a
  su tendencia. En t se conocen t−3 … t−1 de INDPRO y PAYEMS (6/18 = 1/3 del peso) y menos de W875RX1 y CMRMTSPL. Las
  peticiones de paro (semanales, del propio mes t) y Filadelfia (encuesta del mes t) son los únicos datos del mes t:
  informan del factor en t y, a través de su dinámica, de t+1 … t+4. M0 ve la etiqueta de t−5.
- **Signos esperados** (se informan; no se imponen ni deciden, porque no se estiman con la etiqueta): cargas del
  factor > 0 en las 4 tasas coincidentes y en Filadelfia; < 0 en las peticiones de paro.
- **Contraste informativo:** M2 − M0 en log-loss blanda de 4 cuadrantes (= la del eje G, porque el eje I de M2 es el de
  M0, §5), vintage. No entra en Holm (el contraste principal es el pool, k = 1).

## 2. Datos (todo PIT; nada nuevo en la base)

| bloque | serie | de dónde | transformación | qué mes informa |
|---|---|---|---|---|
| coincidentes (4) | `INDPRO`, `PAYEMS`, `W875RX1`, `CMRMTSPL` | **niveles conocidos en la fecha de decisión** vía `PITLabeler.levels_at(fecha)` del mismo modo (las mismas entradas, vintages y calendario que usa la etiqueta recalculada y la persistencia M0) | r = 100·Δln(nivel), mensual; desviación frente a su mediana de los 120 meses previos (τʳ, §3) | su propio mes; borde desigual según la última observación publicada |
| semanal | `claims_4w_yoy` | matriz PIT v0.4 (estado `principal_epoca`, vintage desde 2009-05) | estandarizada (media y desviación del tramo de estimación) | el mes de la fecha de decisión |
| encuesta | `philly_neworders` | matriz PIT v0.4 (`principal_epoca`, latest_truncated) | estandarizada | el mes de la fecha de decisión |

- **Por qué niveles vía `levels_at` y no una base v0.5.** La composición exacta de Ĝ necesita los **niveles** de las 4
  series con su borde desigual, no las tasas de 3 meses de la matriz (`indpro_3m_ann` …), y la estimación del factor
  necesita la historia completa de la vintage de cada corte, que no cabe en una fila de la matriz. `levels_at` ya
  existe, es PIT (es la misma función que da la etiqueta de entrenamiento y la persistencia de M0) y tiene la barrera
  `HoldoutLocked` para fechas ≥ 2005-01. Las 4 series no son columnas prohibidas (la lista negra es la de la
  etiqueta + USREC). La base v0.4 congelada no se toca. Exige la extensión del arnés §8-1 (el modelo pide los
  niveles al arnés; nunca abre ficheros).
- **Modo:** el mismo de la corrida. En `vintage`, cada serie entra como se publicó en la fecha (la vintage de
  INDPRO/PAYEMS; W875RX1 desde 2010-05 y CMRMTSPL desde 2013-06; antes, latest_truncated, como en la etiqueta PIT).
  En `latest_truncated`, la última vintage truncada por publicación.
- **Ventana de datos del factor:** meses 1968-06 → mes de la fecha de decisión (el primero con las 6 series posibles;
  antes de su primer dato o de su τʳ una serie es NaN y el filtro la trata como faltante).
- **Variables de la matriz con historia hasta el corte:** el factor necesita `claims_4w_yoy` y `philly_neworders` de
  los meses m0−5 … m0, que el embargo de la etiqueta deja fuera de `Xtr`. Son variables conocidas en m0 (sin etiqueta):
  extensión del arnés §8-2.
- **S-PIT-001 (Filadelfia prudente antes de 1990-07)** se aplica tal como está preregistrada (§6, corrida
  `s_pit_001`). Si su criterio se dispara en desarrollo, `philly_neworders` antes de 1990-07 pasa a NaN en el factor
  (regla mecánica fijada ahora; ningún otro cambio).

## 3. Modelo del factor (fijado)

Observaciones estandarizadas x<sub>j,m</sub> (j = 1…6; m = mes):

    coincidentes i ∈ {INDPRO, PAYEMS, W875RX1, CMRMTSPL}:
        x_i,m = (r_i,m − τʳ_i,m) / d_i  =  λ_i·f_m + u_i,m + ε_i,m
    peticiones de paro (tasa interanual de una media de 4 semanas):
        x_c,m = λ_c·(1/12)·Σ_{k=0..11} f_{m−k} + u_c,m + ε_c,m
    Filadelfia, nuevos pedidos (índice de difusión ≈ ritmo del mes):
        x_p,m = λ_p·f_m + u_p,m + ε_p,m

    f_m   = φ1·f_{m−1} + φ2·f_{m−2} + η_m,          η ~ N(0, 1)            (factor AR(2), varianza de innovación 1)
    u_j,m = ρ_j·u_j,{m−1} + e_j,m,                   e_j ~ N(0, q_j)        (idiosincrático AR(1))
    ε_j,m ~ N(0, 1e-4)                                                       (regularización numérica fija, no se estima)

- **τʳ<sub>i,m</sub>** = mediana de r<sub>i</sub> en los 120 meses m−120 … m−1 (≥ 90 presentes; si no, NaN). Hace el
  factor relativo a la tendencia de 10 años, como la etiqueta. Para los meses futuros se fija τʳ en su último valor.
- **d<sub>i</sub>**, y media/desviación de `claims_4w_yoy` y `philly_neworders`: del tramo de estimación del corte
  (ddof = 0). Se congelan junto a los parámetros (abajo).
- **Parámetros:** 6 cargas λ, φ1, φ2, 6 ρ, 6 q = **20**. Normalización: varianza de η = 1 y λ<sub>PAYEMS</sub> > 0.
  Restricciones: |ρ<sub>j</sub>| < 0,99; (φ1, φ2) en la región estacionaria; q > 0.
- **Estimación:** máxima verosimilitud exacta del filtro de Kalman con datos faltantes (statsmodels `MLEModel`,
  0.15.0, o una implementación propia que dé la misma verosimilitud con tolerancia 1e-8 en un test). Optimizador
  L-BFGS-B, `maxiter` = 1000, `gtol` = 1e-6. **Arranque determinista:** λ = cargas del primer componente principal
  del panel balanceado más largo; φ y ρ por MCO; q = varianza residual. Sin semillas: no hay nada aleatorio.
- **Cadencia (PIT):** el arnés llama a `fit` cada mes (refit_every = 1). Los parámetros, d<sub>i</sub> y las medias se
  **reestiman en el primer corte y después solo en los cortes de enero**, con los datos conocidos en ese corte, y
  arrancando del óptimo anterior. Entre eneros, el filtro corre cada mes con los parámetros vigentes sobre los datos
  conocidos en la fecha de decisión. Todo ≤ corte.
- **Estado aumentado para la previsión:** para la composición (§4) el estado incluye los retardos 0…11 de f, 0…7 de
  u<sub>i</sub> (las 4 coincidentes), u<sub>c</sub> y u<sub>p</sub> (dimensión 46). Con los mismos parámetros, la
  verosimilitud es idéntica a la de la representación mínima (test). Se extiende la muestra con 4 meses de NaN
  (t+1 … t+4) y se lee la media y la covarianza del estado en t+4 condicionadas a todo lo observado: dan la
  distribución **conjunta** de todas las tasas que faltan, por serie y mes.

## 4. Composición de Ĝ y su incertidumbre σ̂ (fijadas)

**Media Ĝ<sub>t</sub> (exacta, con el código de la etiqueta).**
1. Para cada coincidente, tasas previstas r̂ = τʳ<sub>i,t</sub> + d<sub>i</sub>·E[λ<sub>i</sub>f + u<sub>i</sub>]
   en los meses posteriores a su última observación hasta t+4.
2. Se acumulan sobre el último nivel publicado: L̂<sub>m</sub> = L<sub>último</sub>·exp(Σ r̂/100).
3. A los niveles conocidos en t, extendidos con L̂, se les aplica **`R.growth_components` y `R.growth_axis` de
   `src/labels/regime_us.py`** (el código congelado de la etiqueta): ritmo g con la media de 3 meses centrada y la
   variación t−3 → t+3 (pesos 1, 2, 3, 3, 3, 3, 2, 1), tendencia = mediana centrada de ±60 meses truncada en el borde
   (la que tendría la etiqueta recalculada si se conocieran los datos hasta t+4), σ<sub>i</sub> = MAD × 1,4826 de toda
   la muestra disponible, y media de los z con mínimo 2 indicadores. Ĝ<sub>t</sub> = la columna G en t.
4. Ningún parámetro libre: los pesos, la tendencia, σ<sub>i</sub> y el mínimo de indicadores son los de la ficha.

**Varianza σ̂²<sub>t</sub> = V<sub>filtro</sub> + V<sub>rev</sub> + V<sub>tend</sub>** (se suponen independientes; supuesto
declarado).

- **V<sub>filtro</sub>** (tasas que faltan). Linealización de G en las tasas: ∂G<sub>t</sub>/∂r<sub>i,m</sub> =
  c<sub>i,m</sub> = (1/n<sub>t</sub>)·(2/3)·w<sub>m−t</sub>/σ<sub>i</sub>, con w = (1, 2, 3, 3, 3, 3, 2, 1) para m = t−3
  … t+4 y n<sub>t</sub> = indicadores presentes. V<sub>filtro</sub> = c′Σc con Σ = covarianza conjunta de las tasas que
  faltan (§3, en unidades de r: d<sub>i</sub>d<sub>j</sub>·Cov). Se ignora el efecto de esas tasas sobre la mediana de
  la tendencia y sobre σ<sub>i</sub> (1 de 61 valores; declarado). Un test sintético compara la linealización con el
  código exacto de la etiqueta (tolerancia 1 %, `tests/test_regime_components.py`).
- **V<sub>rev</sub>** (revisión de las tasas ya publicadas; Jacobs-van Norden / Kishor-Koenig, versión mínima). Solo en
  modo `vintage` y solo para las series que en esa fecha entran desde una vintage (en `latest_truncated`, 0).
  V<sub>rev</sub> = Σ<sub>i,m conocido</sub> c<sub>i,m</sub>²·v<sub>i</sub>(edad), edad = mes de decisión − m.
  - **Tabla v(edad), fijada antes de la pasada de desarrollo y sin etiqueta:** con las vintages ALFRED de INDPRO y
    PAYEMS de la instantánea congelada de la etiqueta, fechas de decisión y meses observados **≤ 2004-12**,
    error = r en la vintage de la fecha − r en la última vintage (la que usa la etiqueta), y v = **error cuadrático
    medio** por edad: 1, 2, 3, 4, 5, 6, 7-12, ≥ 13 meses. Se commitea en `research/trials/m2/revision_var.json` antes
    de la primera carga de la etiqueta.
  - W875RX1 y CMRMTSPL no tienen vintages ≤ 2004 (empiezan en 2010-05 y 2013-06): cuando entren desde una vintage
    (solo en el bloqueado) se usa v<sub>i</sub>(edad) = ρ̄(edad)·Var(r<sub>i</sub>), con ρ̄ = media de
    v/Var(r) de INDPRO y PAYEMS (supuesto declarado).
  - No se propaga la revisión a la previsión del filtro (efecto de segundo orden; declarado).
- **V<sub>tend</sub>** (tendencia truncada y σ<sub>i</sub> con datos ≤ t). Se mide en cada reestimación de enero,
  con los niveles conocidos en el corte T y sin etiqueta: para cada mes s de 1965-01 a T−65,
  e<sub>s</sub> = G<sub>s</sub>(niveles de T truncados en s+4) − G<sub>s</sub>(niveles de T), las dos con el código de
  la etiqueta. El primero reproduce la situación del borde (tendencia hacia atrás, σ con datos ≤ s+4) sin error de
  previsión; el segundo es G de la etiqueta recalculada en T con la ventana de tendencia completa.
  V<sub>tend</sub> = media de e<sub>s</sub>² (incluye el sesgo). Se congela hasta la siguiente reestimación.
- **Probabilidad:** el arnés (v2.3, §5c) convierte (Ĝ<sub>t</sub>, σ̂<sub>t</sub>) en P(G alto) =
  Φ(Ĝ<sub>t</sub>/√(σ̂²<sub>t</sub> + s<sub>G</sub>²)) con s<sub>G</sub> = 0,40 de la ficha. **Sin capa de calibración**
  en la principal: la escala sale de la aritmética de la etiqueta, no de un ajuste.

## 5. Eje I, interfaz y nombre

- `m2_struct_g`: `ContinuousAxisModel` con `continuous_axes = ("G",)`; `axis_features = {"G": ("claims_4w_yoy",
  "philly_neworders"), "I": ()}`; `uses_persistence = True` (solo para el eje I) y `uses_pit_levels = True` (§8-1).
- **Eje I = el de M0** (persistencia calibrada, eps 1e-3, L2 1,0; decisión del usuario: eje I = M0). Por eso la
  log-loss de 4 cuadrantes de M2 − M0 es exactamente la mejora del eje G (harness.md §5b).
- El objetivo continuo `g` que pasa el arnés **no se usa para estimar nada**; solo se guarda para diagnósticos
  (residuo walk-forward, informativo).

## 6. Ventanas, corridas y orden (desarrollo, ≤ 2004)

**Ventanas fijadas por regla** (las fechas se anotan en §9 con la sonda de elegibilidad, que solo cuenta meses y no
puntúa nada, **después** de este push):
- **larga** `m2_long`: desde W<sub>G</sub> = primer corte en el que M2 **y** M3 (`m3_tvtp_spec.md`) son elegibles en
  todos los cortes siguientes de los dos modos (mínimos del arnés: 120 meses, ≥ 2 recesiones conocidas, ≥ 8 cambios de
  G; ventana del eje G desde 1968-05 por Filadelfia → se espera W<sub>G</sub> ≈ 1978-07…1978-10) hasta 2004-12.
  Subperiodos [W<sub>G</sub>, 1989-12] y [1990-01, 2004-12].
- **comparable** con M1 v2: 1989-10 → 2004-12.
- `test_start` = 1956-10 (M0 y la persistencia reproducen sus baselines), `allow_shrink: false`, `refit_every: 1`,
  embargo 6, pesos de madurez, `pit_version: "0.4"`, modos vintage (principal) y latest_truncated (sensibilidad).

| corrida | ventana | modelos | para qué |
|---|---|---|---|
| `m2_long` | larga | persistencia, climatología, M0, **m2_struct_g**, `m1v2_g` (referencia) | M2 frente a M0 |
| `m2_m1cmp` | 1989-10 → 2004-12 | M0, m2_struct_g, `m1v2_logit_axis` | comparación con M1 v2 en sus meses |
| `m2_sens` | larga, vintage | M0 y las 4 sensibilidades de §7 | sensibilidades (no eligen) |
| `s_pit_001` | larga, matriz `vintage_filadelfia_prudente` | M0, m2_struct_g | criterio de S-PIT-001 (§2) |

**Orden** (todo al registro de pruebas y al trial log, también lo que falle):
1. Este push. 2. Extensiones del arnés v2.4 (§8) e implementación, con tests sintéticos (abajo) en verde. 3. Tabla
v(edad) (§4) sin etiqueta → commit. 4. Sonda de elegibilidad (solo recuentos) → ventanas en §9 → commit. 5. Placebo
(abajo) → commit. 6. Corridas `--official` en el orden de la tabla, desde un árbol limpio. 7. Validador + Estratega.

**Controles antes de la etiqueta real:**
- **Señal plantada (sintético):** un panel generado con el modelo de §3 y parámetros conocidos; el estimador recupera
  λ, φ, ρ (tolerancias en el test) y la cobertura del intervalo del 80 % de G sintético está entre 0,75 y 0,85.
- **PIT por truncamiento:** la predicción en t no cambia si se alteran los niveles o las variables posteriores a la
  fecha de decisión (3 cortes × 2 modos, sintético y con la instantánea ≤ 2004).
- **Composición:** con tasas futuras conocidas (oráculo sintético), Ĝ = G del código de la etiqueta bit a bit.
- **Placebo pareado** (arnés §9b): etiqueta ≤ 2004 barajada en bloques de 24, semillas 1…20, refit cada 12 meses. Como
  M2 no usa la etiqueta, Δ = ll(M0) − ll(M2) debe ser ≤ 0 (mide G real frente a una etiqueta sin relación). Reglas:
  **fuga** si la media > 0,02 nats; **aviso** si prueba de signo unilateral p < 0,01 o t > 3. Con fuga o aviso no se
  corre con la etiqueta real hasta entenderlo.

## 7. Sensibilidades preregistradas (se publican siempre; NO eligen ni entran en el pool)

| id | cambio | por qué |
|---|---|---|
| `m2_struct_g_platt` | capa Λ(c + b·logit P) sobre la P de M2, L2 = 1 sobre b, eps 1e-3 (como M0) | ¿la escala σ̂ está bien? |
| `m2_struct_g_norev` | V<sub>rev</sub> = 0 | aporte de la varianza de revisión |
| `m2_struct_g_coinc` | factor solo con las 4 coincidentes (sin peticiones de paro ni Filadelfia) | aporte de los datos del mes t |
| `m2_struct_g_ar1` | factor AR(1) | dinámica del factor |
| modo `latest_truncated` | (todas las corridas) | sensibilidad de modo |

*Plucking* (término de recuperación) **no** entra ni como sensibilidad aquí: el Investigador lo propone como
sensibilidad post hoc; se deja para una spec aparte si el usuario lo pide, para no abrir más comparaciones.

## 8. Qué necesita del núcleo (arnés v2.4; no implementado, se hará con tests y sin etiqueta)

1. **`uses_pit_levels`:** `info["pit_levels"](fecha)` → niveles de INDPRO, PAYEMS, W875RX1, CMRMTSPL conocidos en esa
   fecha de decisión (`PITLabeler.levels_at`, mismo modo, misma barrera ≥ 2005) y, por serie, si vienen de una
   vintage. Solo fechas ≤ la fecha de decisión del corte (el arnés lo comprueba). Queda en el registro de accesos.
2. **`info["features_history"]`:** filas de la matriz con las variables declaradas por el modelo, desde el inicio de
   la ventana del eje hasta el mes del corte inclusive (sin columnas de la etiqueta; `assert_no_forbidden`).
3. **`info["decision_dates"]`** de las filas de prueba (con refit_every = 1, una fila).
4. Informe: `mejora_logloss.sd_mensual` (desviación de d; `power_holdout.md` §4) y la detección declarada 3 m × 80/20
   (`m3_tvtp_spec.md` §6) para todos los modelos.

## 9. Cambios post hoc (técnicos) y fechas fijadas por regla

| fecha | cambio | por qué | qué se había visto |
|---|---|---|---|
| — | ninguno por ahora (aquí irán W<sub>G</sub> y la tabla v(edad)) | | |
| 2026-10-24 | ninguno (nota de proceso) | antes del push de esta spec se corrió la suite completa (235 tests, 09:47-09:52Z, exigida por el encargo). Sus tests **preexistentes** del arnés (M0, baselines, placebo, ensayo en seco) leen la etiqueta ≤ 2004 en `development` (registro `research/trials/full/label_access.jsonl`) | nada de M2, M3 ni del pool (no existen); la spec ya estaba escrita y no se cambió después |
