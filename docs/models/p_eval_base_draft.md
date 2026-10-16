---
documento: BORRADOR del preregistro de la evaluación única del modelo base (P-EVAL-BASE)
fecha: 2026-10-16
estado: BORRADOR. NO está en research/hypotheses.yaml y NO abre el periodo bloqueado. Pendiente de la aprobación del
  usuario; después, del modelo M1 congelado (entregable 4) y de su configuración commiteada.
autor: Constructor (arnés v2), a partir de la decisión del usuario (16-oct), la revisión del Estratega (§3b) y el
  Validador v1 (§10b)
---

# P-EVAL-BASE (borrador)

Escrito **sin mirar ningún dato ≥ 2005** ni ninguna relación entre variables macro y la etiqueta en ningún periodo. El
único resultado de desarrollo conocido al escribirlo es el de los baselines sin variables (persistencia cruda,
climatología y M0, ≤ 2004; `harness.md` §8).

## 1. Cómo entra en el arnés (cuando se apruebe)

- Se añade a `research/hypotheses.yaml` con `tipo: evaluacion_holdout`, `estado: preregistrada`, `incluye:` (abajo) y
  `config_arnes:` con la ruta de su configuración **commiteada** (`phase: holdout_evaluation`, `prereg_id:
  P-EVAL-BASE`). Solo entonces `evaluate_holdout("P-EVAL-BASE")` puede abrir el bloqueado (una vez; `harness.md` §4).
- **Todo en una única corrida**: el modelo base, los módulos H-MOD y las sensibilidades S-PIT. Por eso `incluye`
  gasta también esos ids: ninguno podrá evaluarse aparte después.

```yaml
- id: P-EVAL-BASE
  registrada: <fecha de aprobación>
  autor: usuario + coordinador (Constructor arnés v2)
  estado: preregistrada (sin datos mirados después de 2004)
  tipo: evaluacion_holdout
  incluye: [P-EVAL-MOD, H-MOD-001, H-MOD-002, H-MOD-003, H-MOD-004, P-EVAL-S-PIT-002, S-PIT-001, S-PIT-002]
  config_arnes: config/harness/p_eval_base.yaml
```

## 2. Hipótesis principal (una)

**M1** (dos logísticas binarias por eje con objetivo blando, combinadas como producto; `AxisModel`) mejora a **M0**
(persistencia calibrada por eje, `m0_calibrated_persistence`) en **log-loss blanda de 4 cuadrantes**, modo **vintage**.
M1 lleva el logit de la persistencia del eje como entrada, así que M1 − M0 mide exactamente el valor de las variables.

## 3. Modelos y especificación (congelados en git antes de desbloquear)

| eje | variables (lista blanca v0.3, principal) | signo preregistrado del coeficiente |
|---|---|---|
| G | `growth_rt` | + |
| G | `unrate_sahm` | − |
| G | `baa_spread` | − |
| G | `eq_ret_6m` | + |
| G | `curve_10y3m` | + (débil; se informa, no decide si el IC incluye 0) |
| G | logit de `pers_axis_growth` | + |
| I | `core_cpi_6m_ann` (época desde su `principal_desde`) | + |
| I | `headline_cpi_6m_ann` (solo en la época anterior al subyacente) | + |
| I | logit de `pers_axis_infl` | + |

- L2 fijada **a priori** (valor a cerrar en el entregable 4 **antes** de cualquier corrida con variables; no se ajusta
  con datos de desarrollo). Variables estandarizadas con la media y la desviación del entrenamiento de cada corte.
- Mínimo de entrenamiento por eje: 120 meses, ≥ 2 recesiones NBER y ≥ 8 cambios de G (`harness.md` §5).
- Provisionales recalculados con el peso de madurez (ficha, adenda 2026-10-16); "peso 1" y "excluir" como
  sensibilidades.
- Modelos en la misma corrida: M1 (principal), M0 (listón), persistencia cruda, climatología; M1 + cada módulo H-MOD
  (P-EVAL-MOD); M1 con Michigan en Δ12m (P-EVAL-S-PIT-002); M1 con la matriz `vintage_filadelfia_prudente`
  (S-PIT-001); M1 en `latest_truncated` (sensibilidad de modo). Si el clasificador de reglas, Markov o GBM están listos
  y congelados, entran como secundarios **en esta misma corrida**.

## 4. Muestra

- Meses puntuables del bloqueado: **2005-01 → 2021-10** (los provisionales oficiales empiezan en 2021-11), unos 202
  meses. `eval_window` fija en la configuración; `allow_shrink: false`.
- **Nota:** 2022 (el episodio de inflación) queda casi fuera por provisional. No se puede evaluar con esta etiqueta.
  Solo 2 recesiones NBER (2008-09 y 2020): los episodios se informan, no deciden.

## 5. Inferencia

Bootstrap circular por bloques de 12 meses, 5.000 réplicas, semilla 20261015, IC percentil al 95 %; bloques de 24
meses como sensibilidad. Prueba de signo por giro de G. Holm sobre las comparaciones secundarias frente a M0 (la
principal no se corrige: es una).

## 6. Criterio de éxito (se exigen TODAS)

1. Mejora media frente a M0 **≥ 0,05 nats** y **límite inferior del IC > 0** (vintage, 4 cuadrantes).
2. **Eje G**: mejora de la log-loss binaria frente a M0 > 0.
3. **Meses de giro** (etiqueta dura t ≠ t − 5): mejora > 0. **Meses estables**: no empeora más de 0,05 nats.
4. **Mismo signo** de la mejora en 2005-01 → 2014-12 y en 2015-01 → 2021-10.
5. **Signos de los coeficientes** iguales a los preregistrados (§3) y estables a ambos lados de los saltos de vintage
   (`sign_stability`).

Regla de promoción a la Etapa 2: (1)-(5) **y** reducción del retraso medio de detección de los giros de G frente a M0.
Un nowcast que gana en log-loss y no mejora la detección no se promociona.

## 7. Se informa sin decidir

Frente a la persistencia cruda (BSS, acierto); `latest_truncated`; por episodio (NBER ± 6, rachas ≥ 6 m, giros de G)
con prueba de signo; retraso de detección y falsas alarmas; calibración por eje; por cuadrante y frontera; eje I;
correlación de residuos entre ejes (supuesto de independencia condicional, `harness.md` §5b).

## 8. Preguntas abiertas para el usuario

- ¿La L2 de M1 se fija por regla (p. ej. la misma escala que M0) o con un valor teórico? Debe quedar escrita antes de
  correr M1 con variables ≤ 2004.
- Ampliaciones del bloqueado (datos posteriores a 2021-10 cuando maduren): necesitarán su propio `P-EVAL-…` sobre
  meses **nuevos**; el arnés ya impide reevaluar los ids consumidos.
