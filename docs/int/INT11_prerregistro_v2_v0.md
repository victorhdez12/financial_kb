---
documento: P-INT11 v2 — BORRADOR de prerregistro (motor de escenarios v2: desarrollo + confirmación)
version: 0.1 (2026-10-30) — BORRADOR, NO congelado. Requiere las decisiones del usuario de §9.
diseño: docs/int/INT11_v2_diseno.md · motor: src/intl/escenarios.py (Config.v2) · potencia: research/int/int11_v2_potencia.json
antecedentes: P-DEV-INT11 v1.0 (puerta NO pasa; C1 "no establecido (motor no calibrado)"), validación 2026-10-30
datos: desarrollo SOLO ≤ 2004. El periodo ≥ 2005 sigue BLOQUEADO y sin gastar; este borrador propone cómo y cuándo usarlo.
---

# P-INT11 v2 (borrador): ¿dicen la verdad los abanicos del motor v2?

## 0. Naturaleza (leer primero)
- **Fase D (desarrollo, ≤ 2004): NO es confirmatoria.** v2 se diseñó después de ver la corrida v1 en los mismos
  datos. Pasar la puerta D significa "los arreglos funcionan como se esperaba en los datos que inspiraron el
  arreglo"; no significa "el motor está calibrado".
- **Fase C (confirmación): la única que puede afirmar algo.** Sobre datos que nadie ha usado para esta pregunta.
- Corrida única por fase; nada se ajusta después de ver resultados; cualquier cambio = prerregistro nuevo y una fila más
  en `research/trial_log.md` (contamos los caminos probados).

## 1. Modelo congelado
`Generador(Config.v2())` del commit de congelación: bootstrap; k_pais 40; bloque 3; n mínimo de celda 25; sin
contagio; incertidumbre de parámetros; `escala_pais` (Bayes jerárquico, §2.1 del diseño); `k_mezcla` = 0 (D3);
`c_suavizado` = 4 con ruido t5; rejilla log10 κ ∈ [0; 6], 121 puntos. Predictiva por fila: 200 lotes × 100. M0 =
distribución incondicional del entrenamiento (como v1). Datos, exclusiones (guerras, hiperinflación), oro ≥ 1972,
moneda local y régimen operable P3: **idénticos a v1 §1**.

## 2. Fase D — desarrollo (≤ 2004; LOCO principal, temporal descriptivo)
Mismos diseños, semillas (20261030 + …) y puntuaciones que v1 §3-§4 (CRPS, cobertura p5-p95, S5, Sb, S_a).

**Valor crítico:** R = 200 paneles sintéticos con el **nulo heterogéneo** (factores de país medidos sin el régimen,
`medicion_v2.factor_pais`; inflación continua), misma estructura de huecos, el MISMO procedimiento (v2, LOCO y
temporal), 20 × 100 sorteos. Bandas 2,5-97,5 de S5, Sb y S_raros (filas con s_{t−1} ∈ {estanflación, crec. bajo}).

**Puerta D (todas):**
1. |S5 (LOCO) − 0,90| ≤ 0,015: tolerancia **del tamaño que importa** en lugar de la banda LOCO (que mide ±0,4 pp y
   rechazaría por diferencias irrelevantes; hallazgo 2 del validador). Potencia (§5.2 del diseño): un motor que cubre
   85 % falla siempre; v2 calibrado (90,3 % en sintético) pasa siempre. La banda nula se informa. [D1]
2. Cada activo: |S_a − 0,90| ≤ 0,03 (v1: 0,05). Con v2 calibrado en sintético: 0 falsas alarmas.
3. Regímenes raros: S_raros ≥ 2,5 % inferior de su banda nula (≈ 0,86 en la potencia; se recalcula).
4. (Descriptivo, sin decidir) cobertura por país; v1 tenía FIN 80,7 %.

**Contrastes en D:** ninguno con decisión. C1 (CRPS frente a M0) y Brier se informan como descriptivos.
**Si D no pasa:** se informa, v2 NO va a confirmación, y no se ajusta nada con ≤ 2004 sin un prerregistro v3 que
declare explícitamente el nuevo camino.

## 3. Fase C — confirmación (recomendada: §7 del diseño)
Recomendación (diseño §7, opción C): **dentro de la confirmación final ÚNICA del proyecto** con el periodo bloqueado,
y registro en vivo desde ya. Si el usuario elige B (bloqueado solo para INT-11) el texto es el mismo.
- Datos: JST 2005-2020, 14 países, mismas exclusiones; motor ajustado con TODAS las filas ≤ 2004 (diseño "temporal");
  estado s_{t−1} del año anterior (JST).
- **K1 calibración**: S5 dentro de la banda 2,5-97,5 de 200 paneles con el nulo heterogéneo y la estructura de huecos de
  2005-2020 (calculada y congelada ANTES de abrir el bloqueado). Sin criterio por activo (falsas alarmas 0,69).
- **K2 inflación > 5 %**: BSS > 0 y DM (años como conglomerados, Newey-West 2, unilateral) p < α frente a la
  frecuencia ≤ 2004. Variante D7: con IPC/PIB OCDE 2005-2025 y origen mensual (ventanas móviles; conglomerados por año).
- Multiplicidad: K1 y K2 entran en el Holm del lote final del proyecto (α familiar 0,05); si INT-11 va solo (B),
  Holm-2.
- Descriptivos: C1 (CRPSS), K3 caída ≥ 20 % (sin potencia), cobertura por régimen y país, PIT.
- Clasificación: "calibrado fuera de muestra" (K1 pasa), "mejora la probabilidad de inflación alta" (K2 pasa).
  Si K1 falla, la salida "hoy" pasa a llevar el aviso "calibración rechazada fuera de muestra" y no se ensancha nada
  a mano.

## 4. Salida "hoy" v2 (descriptiva, después de D)
Motor `Config.v2()` ajustado con todas las filas ≤ 2004; estado `escenarios_vivo.estado_actual_movil` (12 meses móviles,
per cápita con población Maddison extrapolada); ventana = 12 meses desde el mes siguiente a la emisión, rotulada
"desde … hasta …". Por país: abanico p5/p10/p50/p90/p95 de cada activo, P(bolsa ≤ −20 %), P(inflación > 5 %) con IC
de parámetros, `kappa_en_borde`, factor de dispersión del país. Aviso fijo: "estimado con ≤ 2004; calibración solo
comprobada en desarrollo (contaminada)" hasta que exista la fase C.

## 5. Registro en vivo (empieza con la primera emisión v2, haya o no confirmación con el bloqueado)
- **Mensual**: emitir y guardar (commit + hash) para los 14 países: estado móvil, abanicos de 12 meses, P(inflación > 5 %),
  P(bolsa ≤ −20 %). Las ventanas mensuales se solapan: la evaluación usa conglomerados por **año de emisión**.
- **Al cerrar cada ventana**: dentro/fuera, PIT, Brier. Inflación de la ventana con el IPC OCDE; bolsa real con el
  índice de rentabilidad total de la fuente de vivo que se fije en la congelación (D9).
- **Semáforo** (sin contraste) frente a la banda simulada del propio motor; **contraste formal** según §3.

## 6. Salidas
`scripts/int11_v2_corrida.py` (puerta: árbol limpio y procedencia; se niega si la salida existe) →
`research/int/int11_v2_resultado.{json,md}`; `scripts/int11_v2_hoy.py` → `research/int/int11_v2_hoy.{json,md}`;
fila en `research/trial_log.md`. Ninguno existe todavía (se escriben tras congelar).

## 9. Decisiones del usuario (con recomendación)
| # | decisión | opciones | recomendación |
|---|---|---|---|
| D1 | puerta de desarrollo, criterio global | banda LOCO (±0,4 pp) / tolerancia ±1,5 pp / ±1 pp | **±1,5 pp** (tamaño que importa; potencia 1,0 frente a 85 %) |
| D2 | suavizado | c = 4 (fijado en iid sintético) / c = 2 / sin suavizado | **c = 4**, ruido t5 |
| D3 | mezcla con el incondicional | k = 0 / k = 10 | **k = 0** (no aporta cobertura; resta en raros); k = 10 si se quiere más encogimiento del efecto del régimen |
| D4 | escala por país | Bayes jerárquico (EB) / no | **sí** (es el arreglo de la parte global) |
| D5 | rejilla de κ | [1; 10^6] | **sí**, con aviso de borde en la salida |
| D6 | salida "hoy" | año natural (v1) / 12 meses móviles desde la emisión, per cápita | **móvil, per cápita** (Maddison extrapolada; declarado) |
| D7 | evento de inflación en la confirmación | JST 2005-2020 anual / OCDE 2005-2025 con origen mensual | **OCDE 2005-2025** (potencia ≈ 0,8, prueba el puente mensual) |
| D8 | confirmación | A solo vivo / B bloqueado ya, solo INT-11 / C dentro de la confirmación final única + vivo | **C** |
| D9 | fuente de la bolsa en vivo (rentabilidad total real, moneda local) | a fijar al congelar (MSCI/índices nacionales TR) | decidir antes de la primera emisión |
| D10 | temporal (no estacionariedad, v1 bolsa 80,5 %) | descriptivo / añadir "escala por época" (v3) | **descriptivo**; v3 solo con prerregistro propio |
