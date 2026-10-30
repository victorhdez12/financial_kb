---
documento: P-INT11 v2 — prerregistro del motor de escenarios v2 (fase D de desarrollo + fase C de confirmación FUTURA)
version: 1.0 (2026-10-30) — CONGELADO en este commit, antes de escribir el código de la corrida
parte_de: borrador docs/int/INT11_prerregistro_v2_v0.md + decisiones del usuario 30-oct (delegadas: "se aceptan todas
          las recomendaciones D1-D10"): D1 ±1,5 pp, D2 c = 4 t5, D3 k_mezcla = 0, D4 escala por país, D5 κ ∈ [1; 10^6],
          D6 "hoy" móvil 12 meses per cápita, D7 inflación OCDE 2005-2025 en la confirmación, D8 opción C (el bloqueado
          NO se gasta ahora), D9 fuente de bolsa en vivo a fijar antes de la 1.ª evaluación, D10 temporal descriptivo
diseño: docs/int/INT11_v2_diseno.md · motor: src/intl/escenarios.py (Config.v2, commit de esta congelación)
potencia: research/int/int11_v2_potencia.json (12e1b3a) · antecedentes: P-DEV-INT11 v1.0 y su validación
datos: fase D SOLO ≤ 2004 (load_dev). El periodo ≥ 2005 sigue BLOQUEADO; la fase C se escribe aquí pero NO se ejecuta
---

# P-INT11 v2 v1.0: ¿dicen la verdad los abanicos del motor v2?

## 0. Naturaleza (leer primero)
- **Fase D (desarrollo, ≤ 2004), una sola corrida: NO es confirmatoria.** v2 se diseñó después de ver la corrida v1 en
  los mismos datos. Pasar la puerta D significa "los arreglos funcionan como se esperaba en los datos que inspiraron el
  arreglo", no "el motor está calibrado".
- **Fase C (confirmación):** solo dentro de la confirmación final ÚNICA del proyecto (D8, opción C). No se ejecuta ahora.
- Nada se ajusta después de ver resultados; cualquier cambio = prerregistro nuevo + fila en `research/trial_log.md`.

## 1. Modelo congelado
`E.Generador(E.Config.v2())` en el commit de esta congelación: bootstrap; k_pais 40; bloque medio 3; n mínimo de celda
25; sin contagio; incertidumbre de parámetros; `escala_pais` = True (Bayes jerárquico; diseño §2.1); `k_mezcla` = 0;
`c_suavizado` = 4, `nu_suavizado` = 5; rejilla log10 κ ∈ [0; 6] (121 puntos). M0 = distribución empírica incondicional
de las filas de entrenamiento. Datos, exclusiones (1914-1918, 1939-1945, hiperinflación > 50 % en t o t + 1), oro solo
≥ 1972, moneda local, 14 países del núcleo, régimen operable P3: **idénticos a P-DEV-INT11 v1.0 §1**
(`scripts.int11_corrida.cargar_real`).

## 2. Fase D — diseños y puntuaciones
- **LOCO (principal)** y **temporal** (< 1950 → 1950-2004; descriptivo), con `src/intl/int11.evaluar_motor`
  (cfg = Config.v2()), 200 lotes × 100 sorteos por predictiva; LOCO con H = 5 (h = 5 descriptivo, como v1), temporal
  H = 1. Semilla base 20261101 (fórmula por pliegue/país/estado de v1).
- Puntuaciones como v1 §4: CRPS (M1 frente a M0), cobertura p5-p95 (S5 = media por fila de los activos con dato; Sb;
  S_a por activo), cobertura p10-p90. Nuevo: **S_raros** = cobertura p5-p95 de todas las celdas fila×activo con
  s_{t−1} ∈ {estanflación, crecimiento bajo}; cobertura por país (descriptiva).

## 3. Valor crítico (nulo heterogéneo)
R = 200 paneles sintéticos (generador `np.random.default_rng(20261101)`): `scripts.int11_v2_potencia.panel_v2` con la
medición congelada de `research/int/int11_potencia.json` (latentes, dt común/propia, ν, R, δ = 1) y de
`research/int/int11_v2_potencia.json` (`medicion_v2.factor_pais`, `frecuencia_infl_5`), inflación continua,
`fac_raro` = 1; misma estructura de huecos que el panel real (`scripts.int11_corrida.estructura`); filas con
`Q.filas_sinteticas(..., infl=...)`; el MISMO procedimiento (Config.v2, LOCO y temporal, H = 1) con 20 × 100 sorteos
(declarado). Semilla de simulación de la réplica r: 20261101 + 7r. Bandas 2,5-97,5 de S5, Sb, S_raros por diseño.

## 4. Puerta D (LOCO; todas)
1. |S5 − 0,90| ≤ 0,015.
2. Para cada activo: |S_a − 0,90| ≤ 0,03.
3. S_raros ≥ percentil 2,5 de su distribución en el nulo LOCO.
La banda nula de S5 y Sb y el diseño temporal se informan sin decidir. **Si la puerta pasa**, v2 queda apto para la
fase C. **Si no pasa**, se informa, v2 no va a la fase C y no se ajusta nada con ≤ 2004 sin un prerregistro v3.

## 5. Descriptivos (sin contraste con decisión)
C1 (DM del CRPS frente a M0, como v1 §6) con su p, sin clasificación de descubrimiento (contaminado); CRPSS por activo;
cobertura por régimen de partida y por país; PIT; Brier de "bolsa ≤ −20 %" e "inflación simple > 5 %" (M1 frente a la
frecuencia de M0); h = 5 como v1 §7; κ y si está en el borde; factores de dispersión por país (`escala_resumen`).

## 6. Fase C — confirmación FUTURA (escrita ahora, NO ejecutada; dentro de la confirmación final única del proyecto)
- **Requisito:** puerta D pasada; motor del commit de esta congelación (o del que congele la confirmación final, sin
  cambios en el modelo).
- **K1 calibración:** JST 2005-2020, 14 países, mismas exclusiones; motor ajustado con TODAS las filas ≤ 2004; cada fila
  (c, t) con su s_{t−1} JST. S5 dentro de la banda 2,5-97,5 de 200 paneles del nulo de §3 con la estructura de huecos de
  2005-2020 (diseño "entrena ≤ 2004, prueba 2005-2020"), calculada y congelada ANTES de abrir el bloqueado. Sin
  criterio por activo (falsas alarmas 0,69, diseño §5.2). Potencia: detecta 80 % con 0,80.
- **K2 inflación > 5 % (D7):** estado móvil mensual con IPC y PIB OCDE (`E.estado_movil`, per cápita con Maddison) en
  cada fin de mes de 2004-12 a 2024-12; evento = inflación de los 12 meses siguientes (log media IPC ventana / media
  12 previos) > log 1,05; M1 = P(inflación > 5 %) del motor (h = 1) dado el estado; M0 = frecuencia ≤ 2004 (JST).
  BSS > 0 y DM unilateral (conglomerados por año de origen, Newey-West 12 retardos mensuales) p < α. Potencia
  ≈ 0,76-0,82. Declarado: la inflación de 2021-2023 es de conocimiento público (el modelo está congelado antes).
- **Multiplicidad:** K1 y K2 entran en el Holm del lote de la confirmación final (α familiar 0,05).
- **Descriptivos de C:** C1, caída ≥ 20 % (sin potencia), cobertura por régimen/país, PIT.

## 7. Salida "hoy" v2 (descriptiva; script aparte, después de la corrida D)
Motor Config.v2 con todas las filas ≤ 2004; estado `escenarios_vivo.estado_actual_movil` (12 meses móviles, per cápita);
ventana = 12 meses desde el mes siguiente a la emisión. Por país: abanico p5/p10/p50/p90/p95, P(bolsa ≤ −20 %),
P(inflación > 5 %) con IC de parámetros, κ/borde, factor del país. Cada abanico se etiqueta con el **acierto medido**
en la fase D (cobertura LOCO del activo, del régimen de partida y del país) y con el aviso "no confirmado fuera de
muestra".

## 8. Registro en vivo (diseño: docs/int/INT11_registro_vivo.md; launchd NO se activa aquí)

## 9. Salidas
`scripts/int11_v2_corrida.py` (puerta: árbol limpio, procedencia; se niega si existe `research/int/int11_v2_resultado.json`)
→ `research/int/int11_v2_resultado.{json,md}`; fila en `research/trial_log.md`. `scripts/int11_v2_hoy.py` →
`research/int/int11_v2_hoy.{json,md}`.
