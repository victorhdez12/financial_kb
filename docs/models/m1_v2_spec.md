---
documento: especificación a priori de M1 v2 (logística por eje con variables de riesgo de giro y eje I estructural)
version: 1.0 (congelada ANTES de correr nada con la etiqueta)
fecha: 2026-10-23
hipotesis: H-M1-002 (research/hypotheses.yaml) — DECLARADA CONTAMINADA por los resultados de desarrollo de M1 v1
origen: docs/reviews/2026-10-16_estratega_macro_m1.md (§2, §3, §4-ii, §5, §6), decisión del usuario del 23-oct
codigo: src/models/models_logit.py (LogitAxisV2, REGISTRY m1v2_*), src/models/m1v2_run.py (placebo, corridas, comparación, coeficientes)
config: config/harness/m1v2_principal.yaml, m1v2_long.yaml, m1v2_sens.yaml
tests: tests/test_models_m1v2.py (solo datos sintéticos: ningún test corre M1 v2 con la etiqueta real)
datos: base PIT v0.4 CANDIDATA (docs/models/pit_base.md §9), solo ≤ 2004-12 (fase development). Nada ≥ 2005.
depende_de: arnés v2.1 (✅ con condiciones operativas, docs/validation/2026-10-16_harness_v2_1_m1.md), etiqueta v1.1 y base PIT v0.3 congeladas (no se tocan)
---

# M1 v2: especificación a priori

Este documento se escribe y se commitea (y se empuja a `origin`) **antes** de correr M1 v2 con la etiqueta, incluido
su placebo. Los resultados irán a `docs/models/m1_v2_results_dev.md`. **Una sola pasada de desarrollo**: no se itera
mirando sus resultados y no habrá una v3 construida mirando esa tabla. Un cambio técnico se anota como post hoc (§9).

## 0. Contaminación declarada

M1 v2 es una **hipótesis nueva, post hoc**. Sus tres cambios los propone el Estratega **después** de ver:
- los resultados de desarrollo de M1 v1 (`docs/models/m1_results_dev.md`: no bate a M0; Sahm con el signo contrario;
  eje I con el subyacente peor que M0);
- su estudio de eventos de M0/M1 en los giros de G (C3) y los descriptivos Sahm × `growth_rt` × etiqueta (C4), que
  son relaciones variable-etiqueta ≤ 2004 (trial log, 16-oct).

Consecuencias:
- en desarrollo ≤ 2004 M1 v2 **no puede demostrar nada** (sus cambios se eligieron mirando ese periodo); la corrida de
  desarrollo sirve para el placebo, la estabilidad de signos, los controles de fuga y como descripción;
- la prueba que decide será la **evaluación única**, con **M1 v1 y M1 v2 juntas frente a M0 y Holm k = 2**
  (borrador `docs/models/p_eval_base_draft.md` v3), para que la elección entre ellas no se haga con datos de
  desarrollo;
- M1 v1 y M1 v2 cuentan como **dos ensayos** en el trial log (Deflated Sharpe, `PLAN.md`).

## 1. Estructura

Igual que M1 v1 (`m1_spec.md` §1): dos logísticas binarias por eje con objetivo blando (`p_g_high`, `p_i_high` de la
etiqueta recalculada con datos ≤ T), pesos de madurez del arnés y producto de ejes (`AxisModel`). Walk-forward del
arnés v2.1 sin cambios: refit mensual, embargo 6, purga, mínimos por eje (120 meses, ≥ 2 recesiones NBER conocidas,
≥ 8 cambios de G).

**Eje G** (con variables estimadas, como en M1 v1):

    logit P(G alto) = c_G + b_G · logit(clip(pers_g, 1e-3)) + Σ_j β_j · (x_j − μ_j) / σ_j

**Eje I estructural** (Estratega §3; pendiente FIJA, no se estima con la etiqueta):

    logit P(I alta) = c_I + b_I · logit(clip(pers_i, 1e-3)) + 1,7 · (core_cpi_6m_ann − 2,9) / s,   s = 0,75 pp

- Solo c_I y b_I se estiman, exactamente como en M0. Con el offset fijado el eje está identificado aunque no haya
  ningún cruce de κ en la ventana (el problema de M1 v1 con "excluir").
- **2,9 %** = equivalente en IPC subyacente de κ = 2,5 % en PCE subyacente (ficha de la etiqueta §4). **1,7** convierte
  probit en logit. **s = 0,75 pp** suma el ruido de revisión del eje (s_I = 0,31) y el de los meses de la ventana de la
  etiqueta (t−3…t+3) que el subyacente de 6 meses en t−1 no cubre.
- μ_j, σ_j: media y desviación (ddof = 0) del entrenamiento del corte (estandarización expansiva). σ = 0 → 1.
- M1 v2 **no anida** a M0 en el eje I (el offset no puede valer 0); en el eje G sí (β = 0 ⇒ eje G de M0).

## 2. Variables y signos preregistrados (base PIT v0.4; estado `principal`, salvo `claims_4w_yoy` `principal_epoca`: los dos los admite la política `principal`)

| eje | variable | definición | mecanismo | signo | decide |
|---|---|---|---|---|---|
| G | `growth_rt` | ritmo coincidente frente a su tendencia (v0.3) | el estado del ciclo; ancla del nowcast | + | sí |
| G | `claims_4w_yoy` | peticiones de paro, media de 4 semanas a/a (v0.3) | el único dato de empleo **del propio mes t** (Estratega §5, fila 1) | − | sí |
| G | `curve_min12` | mínimo de `curve_10y3m` en t−11 … t (**v0.4**) | inversión **reciente** → riesgo de caída a 6-18 m; sustituye a la pendiente en nivel, que tras los recortes da el "falso amanecer" (§1 del Estratega) | + | sí |
| G | `baa_gap10y` | `baa_spread` − mediana de los 120 m previos (**v0.4**) | precio del riesgo de crédito frente a lo normal, sin deriva secular | − | sí |
| G | `baa_d6m` | Δ6m de `baa_spread` (**v0.4**) | empeoramiento del crédito = entrada; compresión = salida (simétrico) | − | sí |
| G | `eq_ret_6m` | log-rendimiento de 6 m del S&P (v0.3) | la bolsa descuenta beneficios | + | sí |
| G | `sahm_d3m` | Δ3m de `unrate_sahm` (**v0.4**) | señal de entrada de la Sahm con signo coherente al salir (§2 del Estratega: la Sahm en nivel mide el rebote) | − | sí |
| G | logit de `pers_axis_growth` | | persistencia (como M0) | + | sí |
| I | `core_cpi_6m_ann` | IPC subyacente 6 m anualizado (v0.3, `principal_desde` 1978-01) | **offset fijo** 1,7/s por pp (no se estima; +2,27 con s = 0,75) | + (fijo) | no (no se estima) |
| I | logit de `pers_axis_infl` | | persistencia (como M0) | + | sí |

**Los tres cambios frente a M1 v1** (Estratega §4-ii), y nada más:
1. **Sin `unrate_sahm` en nivel**; entra `sahm_d3m` con signo −.
2. **Eje I estructural** (§1) en lugar del subyacente con pendiente libre.
3. **Variables de riesgo de giro** en el eje G: `curve_min12`, `baa_gap10y`, `baa_d6m` sustituyen a `curve_10y3m` y
   `baa_spread` en nivel; entra `claims_4w_yoy` (lista del Estratega §6, punto 3).

**Qué NO entra, y por qué (fijado ahora):**
- **Filadelfia** (`philly_activity`, `philly_neworders`; fila 6 de la tabla del Estratega): su lista definitiva
  (§6, punto 3) y el cambio 3 de §4-ii no la incluyen. Añadirla después de ver resultados sería selección; queda para
  el siguiente aspirante (Markov con transiciones variables).
- Ninguna otra variable de nivel contemporáneo (el Estratega lo desaconseja: `ff_d12m`, `real_ff`, otros plazos de
  bolsa).
- **Reglas**: no se repiten (M1 v1 ya las descartó).

Sustituciones: ninguna. Los 8 nombres existen en las dos matrices v0.4 (comprobado con `PITData.colinfo`, sin
etiqueta): `principal` salvo `claims_4w_yoy`, `principal_epoca` (desde 1968-02).

## 3. Elegibilidad y ventanas (recuento SIN ajustar modelos con variables)

Recuento hecho antes de esta especificación con una sonda (`AxisWindowProbe`: declara las variables por eje y solo
ajusta la persistencia calibrada; se leyeron **solo** los diagnósticos de elegibilidad de `walk_forward`, ninguna
puntuación). Comprobado en **todos** los cortes 1975-01 → 2004-12 de los dos modos (lección B3-1 del Validador):

| eje | inicio de la ventana del eje | primer corte elegible en TODOS los cortes siguientes (vintage / latest_truncated) |
|---|---|---|
| G de M1 v2 | 1968-02 (`claims_4w_yoy`) | **1978-07** / 1978-07 |
| I (IPC subyacente) | 1978-01 | **1989-10** / 1988-06 (en vintage no es elegible en 1989-03…09: ya visto en M1 v1) |

**Ventanas fijas** (`allow_shrink: false`; todos los modelos las cubren en los dos modos):

| corrida | ventana | meses | modelos | para qué |
|---|---|---|---|---|
| **principal** `m1v2_principal` | **1989-10 → 2004-12** | 183 | persistencia, climatología, M0, **M1 v2**, M1 v1 (`m1_logit_axis`) | M1 v2 frente a M0 y frente a M1 v1, mismos meses que la principal de M1 v1 |
| larga `m1v2_long` | **1978-07 → 2004-12** | 318 | persistencia, climatología, M0, **`m1v2_g`** (eje G de M1 v2 + eje I de M0), `m1_logit_axis_hl` (eje G de M1 v1 + IPC general) | el eje G con 4 recesiones (1980, 1981-82, 1990-91, 2001) y más giros |
| sensibilidad `m1v2_sens` | 1989-10 → 2004-12, vintage | 183 | M0, M1 v2 con s = 0,5 y s = 1,0 | escala del eje I (§4) |

- Principal y larga en **vintage (principal)** y **latest_truncated (sensibilidad)**; `test_start` = 1956-10 (M0 y la
  persistencia reproducen las de los baselines v2 y las de M1 v1 en los mismos cortes).
- Subperiodos: 1989-10 → 1996-12 / 1997-01 → 2004-12 (principal) y 1978-07 → 1989-12 / 1990-01 → 2004-12 (larga).
- Coste aceptado (Estratega §5): el eje G empieza en 1978-07, no en 1975-06; se pierde la salida de 1975.
- `m1v2_g` no es un modelo para la evaluación única: es el eje G de M1 v2 aislado (su eje I es exactamente el de M0).

## 4. Regularización y parámetros (fijados a priori)

- **Eje G: L2 = 6,0** sobre los β estandarizados (escala de suma), **la misma de M1 v1** y con el mismo razonamiento
  (`m1_spec.md` §3: τ = 1, dependencia k = 12). No se ajusta con datos de desarrollo.
- **Persistencia: L2 = 1,0** sobre b y eps = 1e-3 (los de M0), en los dos ejes. Constantes sin penalizar.
- **Eje I: pendiente 1,7, centro 2,9 %, escala s = 0,75 pp.** Sensibilidades preregistradas **s = 0,5 y s = 1,0**
  (`m1v2_sens.yaml`): se publican y **no eligen**.
- No hay sensibilidades de L2 (menos comparaciones; M1 v1 ya mostró que la L2 apenas importa: ±0,01 nats).

## 5. Placebo pareado de M1 v2 (ANTES de mirar el resultado real)

Diseño de `m1_spec.md` §5 sin cambios, con la especificación y la L2 de M1 v2 y la matriz v0.4
(`m1v2_run placebo` → `research/trials/m1_v2/placebo_m1_v2.json`):

- Etiqueta oficial ≤ 2004 barajada en bloques de 24 meses; 20 semillas (1…20); refit cada 12 meses; mínimo 120 meses
  (mínimos de recesiones y de cambios de G a 0); ponderación "uno".
- **Contraste:** Δ = log-loss(M0) − log-loss(M1 v2) con la misma permutación, en dos especificaciones:
  `m1v2_logit_axis` (ventana 1990-01 → 2004-12) y `m1v2_g` (1979-01 → 2004-12). Se informan Δ por eje.
- **Reglas (las del arnés §9b y del Validador M2-5, fijadas ya):** **fuga** si la media > 0,02 nats; **aviso** si la
  prueba de signo unilateral da p < 0,01 (≥ 15 de 20 positivas) o t > 3.
- **Potencia con la L2 de M1 v2** (solo `m1v2_g`, la ventana más larga): Δ_C = ll(M1 v2) − ll(M1 v2 + C) con C (3
  columnas del objetivo barajado) en los dos ejes: ruido, control t−5, t+1 con σ = 1 y 2, t con σ = 2 y calendario t−4.
- **Nota a priori sobre el eje I:** con la etiqueta barajada el offset estructural del eje I (fijo, informativo con la
  etiqueta real) **perjudica** por construcción → Δ_I negativo esperado. No es un fallo; por eso se informa Δ_G aparte.
- **Si hay fuga o aviso**, no se corre M1 v2 con la etiqueta real hasta entenderlo; se documenta.

## 6. Orden de las corridas (todas al registro de pruebas y al trial log, también las fallidas)

1. Placebo (§5). 2. `m1v2_principal.yaml --official`. 3. `m1v2_long.yaml --official`. 4. `m1v2_sens.yaml --official`.
5. Coeficientes (`m1v2_run analyze`) de 2 y 3. 6. Comparaciones pareadas (`m1v2_run compare`): M1 v1 → M1 v2 en la
principal; `m1_logit_axis_hl` → `m1v2_g` en la larga.

Desde un árbol limpio en el commit de esta especificación (`--official` exige `src/`, `config/` y `tests/`
commiteados).

## 7. Qué se informa (desarrollo; descriptivo, NO decide nada)

- Log-loss de 4 cuadrantes y por eje; **M1 v2 − M0** con IC por bloques de 12 meses (y 24); **M1 v2 − M1 v1** pareado.
- **Giro / estable**; subperiodos; épocas; episodios (NBER ± 6, rachas ≥ 6 m, giros de G).
- **Detección de giros de G** (definición v2.1): retraso medio, detectados, censurados, retraso pareado frente a M0,
  **falsas alarmas al año**.
- Calibración por eje; correlación de residuos G-I (umbral 0,2).
- **Signos**: fracción de cortes con el signo preregistrado y `sign_stability` en los saltos de vintage.
- **Referencia (criterio ya aceptado por el usuario para P-EVAL-BASE, 16-oct)**: giros ≥ 0 frente a M0, falsas
  alarmas ≤ 0,5 al año, mejora total ≥ 0,05 nats. En desarrollo se informa si M1 v2 lo cumpliera, sin que eso decida
  nada (la especificación está contaminada por este periodo).
- **Alarma de fuga (Estratega):** una mejora frente a M0 > 0,25 nats (4 cuadrantes, vintage) se trata como sospecha y
  se audita (placebo, espía, señal plantada) antes de creerla.
- **Si el resultado es negativo, se publica tal cual.** No se itera.

## 8. Qué necesitaría del núcleo

Nada nuevo. El arnés v2.1 ya admite `pit_version` (v0.4 candidata solo en desarrollo; la evaluación única exige una
base en `FROZEN`). Para P-EVAL-BASE hará falta congelar la v0.4 (✅ del Validador + usuario).

## 9. Cambios post hoc (técnicos)

| fecha | cambio | por qué | qué se había visto |
|---|---|---|---|
| — | ninguno por ahora | | |
