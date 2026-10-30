---
documento: INT-11 v2 — diseño del registro mensual en vivo (para evaluar K1 y K2 sin gastar el periodo bloqueado)
version: 0.2 (2026-10-30) — DISEÑO + arreglos de la validación v2 (hallazgo 3). launchd NO activado.
parte_de: docs/int/INT11_prerregistro_v2.md §5-§8 · código: scripts/int11_v2_hoy.py (--registro),
          src/report/registro_vivo.py (reglas), src/report/escenarios_vivo.py (vintages)
---

# Registro en vivo de INT-11 v2

## 0. Para qué
La única evidencia que **crece sola y no gasta nada**: cada mes se congela lo que el motor dice de los 12 meses
siguientes, y cuando esos 12 meses pasan se anota dónde cayó lo realizado. Así se medirá K1 (¿el abanico del 90 %
acierta el 90 %?) y K2 (¿la probabilidad de inflación > 5 % mejora a la frecuencia histórica?) en datos que nadie
conocía al emitir.

## 1. Qué se guarda cada mes (inmutable)
`research/int/int11_vivo/AAAA-MM.json` (escrito por `scripts.int11_v2_hoy --registro`; se niega a sobrescribir) +
una línea en `research/int/int11_vivo/indice.csv` con el **sha256** del archivo y el **commit** del código.
Contenido:
- procedencia (commit, árbol limpio, hora UTC), versión y configuración completa del motor, κ y si está en el borde;
- `emision`, `corte_datos` (último fin de mes con datos) y `ventana_objetivo` (12 meses desde el mes siguiente);
- por país: estado móvil completo (mes del IPC, trimestre del PIB, inflación, brecha per cápita, régimen, huecos
  interpolados), **percentiles 1-99** de la rentabilidad real de 12 meses de cada activo (bastan para la cobertura de
  cualquier intervalo y para el PIT por interpolación), P(bolsa ≤ −20 %) y P(inflación > 5 %) con su IC de parámetros,
  factor de dispersión del país;
- el acierto medido en la fase D con el que se etiquetó.
Regla: un mes sin emisión queda vacío (no se rellena después). El código del motor no cambia entre emisiones salvo
prerregistro nuevo; si cambia, el registro empieza una serie nueva.

## 1 bis. Reglas que lo hacen fiable (v0.2, tras la validación v2)
- **La 2.ª emisión ya no aborta.** Con `--registro` el script NO reescribe `research/int/int11_v2_hoy.{json,md}` (antes
  los reescribía y el mes siguiente el árbol estaba sucio → la emisión abortaba). La comprobación de procedencia tolera
  cambios sin commitear SOLO dentro de `research/int/int11_vivo/` (p. ej. si falló el commit automático del mes
  anterior; se anotan en `procedencia.pendientes_en_registro`); cualquier otro cambio sigue abortando.
- **Sin fechas atrasadas.** La fecha de emisión debe ser hoy ± 3 días. Una emisión atrasada usaría datos OCDE revisados
  después de esa fecha (fuga). Excepción `--vintage`: solo emite los países con vintages en el warehouse (ALFRED:
  EE. UU., IPC CPIAUCSL y PIB GDPC1 "tal como se publicaron" en la fecha); el resto queda "sin vintages". La OCDE del
  warehouse no tiene vintages.
- **Huella de las entradas.** Cada emisión guarda las series exactas de IPC (30 meses) y PIB (48 trimestres) que usó y
  su sha256 (`entradas`, y columna `sha256_entradas` del índice): es la "vintage propia" del registro.

## 2. Cuándo
Día 20 de cada mes (después de la publicación habitual del IPC OCDE del mes anterior), emisión con `fecha` = ese día;
la ventana empieza el día 1 del mes siguiente. Plantilla de launchd (NO instalada):
`~/Library/LaunchAgents/com.financialkb.int11vivo.plist` con `StartCalendarInterval` {Day 20, Hour 9} ejecutando
`cd ~/Proyectos/financial_kb && .venv/bin/python -m scripts.int11_v2_hoy --registro && git add research/int/int11_vivo
&& git commit -m "INT-11 live record AAAA-MM"` (con v0.2 la emisión solo escribe en `research/int/int11_vivo`, así que
este `git add` deja el árbol limpio para el mes siguiente). Se activa solo con permiso del usuario (como el resto de automatizaciones;
ver Actualizaciones.md).

## 3. Cómo se evaluará (cuando cierre cada ventana; script futuro `scripts/int11_v2_vivo_eval.py`)
- **Realizado de inflación (K2):** log(media IPC OCDE de los 12 meses de la ventana / media de los 12 anteriores)
  > log 1,05 → 0/1. Brier de M1 (la P guardada) frente a M0 (frecuencia ≤ 2004, 26,2 %).
- **Realizado de los activos (K1):** rentabilidad real de 12 meses en moneda local de cada activo (bolsa: índice de
  rentabilidad total del país — **fuente a fijar (D9) antes de la primera evaluación**; bonos y letras: índices de
  deuda pública o reconstrucción con tipos OCDE; vivienda: precios OCDE + alquiler imputado; oro en moneda local),
  deflactada con el IPC OCDE. Dentro/fuera del p5-p95 guardado; PIT con los percentiles 1-99.
- **Solapes:** las ventanas mensuales se solapan 11 de 12 meses; la inferencia usa **conglomerados por año de
  emisión** (o una sola emisión por año, la de diciembre, como análisis principal a decidir antes de evaluar).
- **Semáforo** (sin contraste, cada año): cobertura acumulada frente a la banda simulada del motor para ese nº de
  años (diseño §5.2: en vivo 5 años [79,7; 96,0], 10 años [82,7; 95,0]); verde dentro del 80 % central, ámbar 80-95 %,
  rojo fuera.
- **Contraste formal:** calibración (K1) y Brier de inflación (K2) a los 10 años de registro (potencia ≈ 0,55-0,6;
  a 20 años ≈ 0,8-0,9), salvo que antes llegue la confirmación final única con el bloqueado (prerregistro §6).

## 4. Qué NO hace el registro
No reajusta el motor con los datos nuevos (sigue estimado con ≤ 2004); no cambia el umbral ni las ventanas; no se mira
el dentro/fuera parcial de una ventana abierta.
