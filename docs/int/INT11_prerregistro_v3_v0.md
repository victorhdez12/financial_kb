---
documento: P-INT11 v3 — BORRADOR de prerregistro del motor de escenarios v3 (fase D de desarrollo + fase C de confirmación FUTURA)
version: 0.1 (2026-10-30) — BORRADOR, NO congelado. Requiere las decisiones del usuario (§10) antes de congelar.
diseño: docs/int/INT11_v3_diseno.md · motor: src/intl/escenarios.py (Config.v3) · sintético: src/intl/int11v3.py
potencia: research/int/int11_v3_potencia_P{0,1,2}.json · constante: research/int/int11_v3_c_suavizado.json
antecedentes: P-INT11 v2 v1.0 (congelado d824933), su corrida (PASA) y su validación (docs/validation/2026-10-30_int11v2.md)
datos: fase D SOLO ≤ 2004 (load_dev). El periodo ≥ 2005 sigue BLOQUEADO; la fase C se escribe aquí pero NO se ejecuta
---

# P-INT11 v3 (borrador v0): ¿dicen la verdad los abanicos del motor v3, también en la frontera y en otra época?

## 0. Naturaleza y contaminación (leer primero)
- **v1 y v2 ya se corrieron en ≤ 2004** (LOCO y temporal, 14 países). v3 se diseñó después de leer esas corridas y su
  validación. Por tanto **la fase D de v3 (≤ 2004) es DESARROLLO**: comprueba que los arreglos hacen lo que se espera en
  los datos que los inspiraron; **no confirma nada**. Su resultado no se puede presentar como evidencia de calibración.
- Cada valor nuevo se fijó a priori o en sintético (diseño §1); ningún resultado real se ha cruzado con el régimen en
  la fase de diseño de v3 (solo la dt robusta de la brecha, macro, para el sintético).
- **Fase C (confirmación):** solo dentro de la confirmación final ÚNICA del proyecto (como v2, opción C). Va **un solo
  motor** a C: v3 si pasa su puerta D, si no v2 (que ya la pasó). Elegir entre v2 y v3 con ≤ 2004 es selección en
  datos de desarrollo (ya contaminados): no afecta a C, que no se ha mirado.
- Nada se ajusta después de ver resultados; cualquier cambio = prerregistro nuevo + fila en `research/trial_log.md`.

## 1. Modelo que se congelaría
`E.Generador(E.Config.v3())` en el commit de la congelación: todo lo de v2 (bootstrap, k_pais 40, bloque 3, n mínimo
de celda 25, sin contagio, incertidumbre de parámetros, escala por país, k_mezcla 0, ruido t5, κ ∈ [1; 10^6]) más:
`curtosis_escala` = "pais", `n0_curtosis` = 50; `c_suavizado` = 5,25 (regla sintética); `semivida_epoca` = 50 años
(año de referencia = último año del entrenamiento); pertenencia suave `sigma_infl` = 0,5 pp, `sigma_brecha` = 1 pp;
`eventos` = () (desactivados). Datos, exclusiones (guerras, hiperinflación > 50 %), oro ≥ 1972, moneda local, 14 países,
régimen P3: **idénticos a v1/v2** (`scripts.int11_corrida.cargar_real`), con `preparar_filas(..., estado_previo=True)`
para la inflación y la brecha observadas de t − 1.

## 2. Fase D — diseños y puntuaciones
- **LOCO (principal)** y **temporal** (< 1950 → 1950-2004; descriptivo), H = 1, 200 lotes × 100 sorteos por régimen de
  partida, con `src/intl/int11v3.evaluar_suave` (predictiva de cada fila = mezcla de los 4 regímenes de partida con
  `pesos_estado(π_{t−1}, brecha_{t−1}, 0,5 pp, 1 pp)`). Semilla base 20261104.
- Puntuaciones: S5 (media por fila de la cobertura p5-p95 de los activos con dato), S_a por activo, S_raros
  (s_{t−1} ∈ {estanflación, crecimiento bajo}, régimen duro como etiqueta), S5_cerca (|π_{t−1} − 3 %| < 0,5 pp), anchura
  media del p5-p95, cobertura por país; Brier de inflación > 5 % (M1 frente a la frecuencia de M0), global y cerca del
  umbral, con DM por años (descriptivo).
- Comparación descriptiva con v2 en los mismos pliegues y semillas (v2 = régimen duro).

## 3. Valor crítico (nulo)
R = 200 paneles del proceso **P1** (`scripts.int11_v3_potencia.panel_v3`: nulo heterogéneo congelado de v2 + inflación
y brecha continuas + error de medida 0,25 pp / 0,5 pp), con la estructura de huecos del panel real
(`scripts.int11_corrida.estructura`), el MISMO procedimiento (Config.v3, LOCO y temporal) con 20 × 100 sorteos
(declarado: la banda es algo más ancha que con 200 × 100). Semilla de la réplica r: 20261104 + 7r. Bandas 2,5-97,5 y
percentil 10 de S5, S_a y S_raros.

## 4. Puerta D (LOCO; todas) — propuesta (decisión D5)
1. **S5 ≥ percentil 2,5 de su banda nula** y S5 ≤ 0,93 (techo: con cambio de época v3 llega al 91,9 % en LOCO
   sintético, banda hasta 92,5 %; la puerta busca infracobertura). No se admite la tolerancia ±1,5 pp de v2, que es ≈ 3 veces la
   banda: hallazgo 2 de la validación).
2. Cada activo: |S_a − 0,90| ≤ 0,03 (como v2).
3. S_raros ≥ percentil 10 de su distribución nula (v2 usaba el 2,5, poco exigente).
Descriptivo (sin decidir): banda nula completa, temporal, cobertura por país (con su banda nula por país), S5_cerca,
Brier cerca del umbral frente a v2. **Si pasa**, v3 sustituye a v2 en la fase C. **Si no**, se informa, va v2 a C y no
se ajusta nada con ≤ 2004 sin un prerregistro v4.

## 5. Descriptivos de la fase D
C1 (DM del CRPS frente a M0) solo informativo; PIT; κ y borde; factores por país y curtosis por país
(`escala_resumen`); n efectivo de Kish de las celdas raras; Brier de "bolsa ≤ −20 %".

## 6. Fase C — confirmación FUTURA (escrita ahora, NO ejecutada; dentro de la confirmación final única)
- **Requisito:** puerta D de v3 pasada; motor del commit de la congelación.
- **K1 calibración:** JST 2005-2020, 14 países, mismas exclusiones; motor ajustado con TODAS las filas ≤ 2004
  (semivida con año de referencia 2004); predictiva suave con π y brecha JST de t − 1. S5 dentro de la banda 2,5-97,5 de
  200 paneles P1 con la estructura de 2005-2020 (diseño "entrena ≤ 2004, prueba 2005-2020"), calculada y congelada ANTES
  de abrir el bloqueado. Sin criterio por activo.
- **K2 inflación > 5 %:** estado móvil mensual OCDE (`E.estado_movil`, per cápita) en cada fin de mes de 2004-12 a
  2024-12; P(inflación de los 12 meses siguientes > 5 %) del motor con **pertenencia suave** sobre (π, brecha) móviles;
  M0 = frecuencia ≤ 2004. BSS > 0 y DM unilateral (conglomerados por año de origen, Newey-West 12) p < α.
- **Multiplicidad:** K1 y K2 en el Holm del lote final (α familiar 0,05). Si va v2 en lugar de v3, rige §6 de P-INT11 v2.
- **Descriptivos de C:** caída ≥ 20 %, cobertura por régimen/país, PIT, eventos (si INT-14 los ha establecido antes).

## 7. Potencia (sintética; diseño §5)
Detalle en docs/int/INT11_v3_diseno.md §5. En corto: v3 cubre 90,7 % en LOCO sintético (v2 90,4 %), 90,7 % cerca del
umbral con error de medida (v2 89,5 %); con cambio de época, bloqueado 88,3 % (v2 86,9 %). K1 detecta una cobertura
real ≈ 82 % con 0,83 (v2 0,80). K2 (inflación > 5 %, bloqueado JST): potencia 0,69-0,76 (v2 0,61-0,62); con OCDE mensual
2005-2024 será mayor (más orígenes). La curtosis por país no mueve el sintético (su efecto está en el dato real).

## 8. Salida "hoy" v3 y registro en vivo
- "Hoy" v3 (descriptiva; script futuro `scripts/int11_v3_hoy.py`, después de la fase D): `simular_suave` con el estado
  móvil (π, brecha); cada abanico etiquetado con el acierto medido en la fase D de v3 y "no confirmado fuera de muestra".
- Registro en vivo: reglas v0.2 (docs/int/INT11_registro_vivo.md). Si v3 se congela, **serie nueva** del registro (el
  motor cambia); la serie v2 puede empezar ya.

## 9. Salidas previstas
`scripts/int11_v3_corrida.py` (puerta: árbol limpio, procedencia, se niega si existe el resultado) →
`research/int/int11_v3_resultado.{json,md}`; fila en `research/trial_log.md`.

## 10. Decisiones del usuario (con recomendación)
| # | decisión | opciones | recomendación |
|---|---|---|---|
| D1 | σ de la pertenencia suave | σπ 0,25 / **0,5** pp; σb 0,5 / **1** pp; o régimen duro | **0,5 pp y 1 pp** (extremo alto de la incertidumbre de medida; sintético: misma calibración, mejor Brier cerca del umbral) |
| D2 | constante de ensanchamiento | 4 (v2) / **5,25** (regla) | **5,25** (la regla fijada antes del experimento) |
| D3 | no estacionariedad | apagada / semivida 75 / **50** / 30 años | **50 años** (ver potencia §5: ayuda algo en el bloqueado si el cambio ya empezó, coste pequeño si no) |
| D4 | curtosis del factor de país | agrupada (v2) / **por país, n0 = 50** | **por país, n0 = 50** |
| D5 | puerta D | ±1,5 pp (v2) / **banda nula unilateral + techo 0,93** | **banda nula** (la tolerancia de v2 era 3 veces la banda) |
| D6 | eventos | **interfaz apagada** hasta INT-14 / activar ya con condiciona | **apagada**; activar por prerregistro propio solo los eventos que INT-14 establezca |
| D7 | qué motor va a la confirmación final | **v3 si pasa D, si no v2** / los dos | **uno solo** (evita duplicar la familia de Holm) |
| D8 | registro en vivo | empezar ya la serie v2 (launchd, con permiso) / esperar a v3 | **empezar ya v2** (la evidencia que crece sola); serie v3 nueva al congelar |
| D9 | correr la fase D de v3 | **sí, una vez** / saltar a C | **sí, una vez** (comprueba los arreglos; declarado como desarrollo) |
