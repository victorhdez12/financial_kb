---
documento: P-DEV-INT11 — prerregistro de la corrida de DESARROLLO del motor de escenarios
version: 1.0 (2026-10-30) — CONGELADO en este commit, antes de escribir el código de la corrida
parte_de: docs/int/INT11_prerregistro_v0.md (borrador) + decisiones del usuario 30-oct ("haz lo que recomiendes"):
          D1 a, D2 guerras fuera de la evaluación, D3 oro solo ≥ 1972, D4 40/3/25, D5 sin contagio en M1, D6 M2 descriptivo,
          D7 bootstrap, D8 solo C1, D9 bloqueado NO, D10 moneda local, D11 un país
diseño: docs/int/INT11_diseno.md · motor: src/intl/escenarios.py (6f3352c) · potencia: research/int/int11_potencia.json
datos: SOLO ≤ 2004 (load_dev). El periodo ≥ 2005 no se toca (D9)
---

# P-DEV-INT11 v1.0: ¿son calibradas y mejores que "no saber el régimen" las distribuciones a 1 año del motor?

## 0. Naturaleza de esta corrida (leer primero)
- Es una corrida de **desarrollo**, una sola vez. **No es confirmatoria** para C1: el Atlas §8 ya cruzó el régimen
  operable con las rentabilidades de 1876-1999. Un "C1 establecido" aquí significa "coherente con lo ya sabido, medido
  como distribución", no un descubrimiento nuevo. La **calibración** sí es información nueva (nadie ha mirado la
  anchura de los abanicos).
- Nada se ajusta después de ver resultados. Si algo falla, se informa y una versión nueva necesita prerregistro nuevo.

## 1. Datos
- `src/intl/panel.anual` (JST, ≤ 2004), núcleo de 14 países: BEL DEU DNK ESP FIN FRA GBR ITA JPN NLD NOR PRT SWE USA.
- Activos (rentabilidad real simple del año, moneda local): bolsa `eq_tr_real`, bonos `bond_tr_real`, letras
  `bill_rate_real`, vivienda `housing_tr_real`, oro `oro_real_local` de `src/intl/activos3b.oro_panel` **solo años
  ≥ 1972** (antes, hueco; D3). Macro: inflación = Δlog IPC (`inflacion` del panel), `rgdpmad`.
- Régimen operable con eje P3 (D1): `src/intl/escenarios.preparar_filas(eje="p3")`.
- **Excluidos** (D2) de entrenamiento y evaluación: años 1914-1918 y 1939-1945 (todos los países) y país-años con
  inflación simple > 50 % en t o t + 1 (`src/intl/int6.hiper_fuera`).
- Filas: todas las que deja `preparar_filas` (régimen de t − 1 y de t definidos) con año ≤ 2004.

## 2. Modelos
- **M1** = `Generador(Config())` con los valores por defecto del commit 6f3352c: bootstrap, k_pais 40, bloque medio 3,
  n mínimo de celda 25, sin contagio, con incertidumbre de parámetros (D4, D5, D7). Para cada fila de prueba (país c,
  año t) la predictiva es `simular(c, estado = s_{t−1}, horizonte = 5, n_lotes = 200, por_lote = 100)` ajustado SOLO con
  las filas de entrenamiento del diseño; el año 1 da la predictiva a 1 año. Como solo depende de (diseño, pliegue, país,
  s_{t−1}), se simula una vez por combinación. Semilla = 20261030 + 1000·pliegue + 10·índice del país + s_{t−1}.
- **M0** = distribución empírica incondicional de las filas de entrenamiento (todas, pesos iguales), por activo.
- M2 (inclinación con termómetro/F1/D-P): **no se corre** en esta corrida (D6: descriptivo, aplazado a cuando existan
  las covariables históricas por país-año).

## 3. Diseños
- **LOCO (principal):** 14 pliegues; se entrena con los otros 13 países (todos los años ≤ 2004) y se evalúa el país
  dejado fuera (su credibilidad propia es 0 → panel puro). Declarado: el entrenamiento incluye años posteriores de otros
  países.
- **Temporal (robustez):** se entrena con filas de año < 1950 y se evalúa 1950-2004 (todos los países). El oro no tiene
  filas de entrenamiento → queda fuera de este diseño.

## 4. Puntuaciones
- **CRPS** por fila y activo (`escenarios.crps_muestra` sobre los 20.000 sorteos; M0 sobre su pool). Normalización:
  CRPS / media del CRPS de M0 de ese activo en ese diseño. Puntuación de la fila d = media, sobre los activos con dato,
  de (CRPS_M0 − CRPS_M1) normalizado. CRPSS por activo = 1 − media CRPS_M1 / media CRPS_M0.
- **Cobertura** del intervalo p5-p95 de M1 por fila y activo (dentro = 1). Estadísticos: S5 = media sobre filas de la
  media por fila de los activos con dato; Sb = cobertura de la bolsa; S_a por activo.

## 5. Puerta de calibración (requisito previo de C1)
- **Valor crítico simulado:** R = 200 paneles SINTÉTICOS con el proceso de `src/intl/int11` y la medición congelada de
  `research/int/int11_potencia.json` (latentes de régimen, dt común/propia, ν, correlaciones; δ = 1), con la MISMA
  estructura de huecos que el panel real (qué país-año-activo existe, tras las exclusiones), 14 países × 1876-2004,
  convertidos en filas (`inflacion` = 5 % si el régimen es de inflación alta y 1 % si no; rentabilidad simple = exp(log) − 1)
  y pasados por EL MISMO procedimiento (M1 completo, LOCO y temporal) con 2.000 sorteos por predictiva (20 × 100)
  en lugar de 20.000 (declarado, por tiempo). Bandas = percentiles 2,5 y 97,5 de S5 y Sb en las 200 réplicas, por diseño.
  Semilla 20261030.
- **Calibrado (LOCO)** si y solo si: S5 y Sb dentro de sus bandas simuladas **y** |S5 − 0,90| ≤ 0,05 **y** para cada
  activo |S_a − 0,90| ≤ 0,05.
- El diseño temporal se informa con sus propias bandas, sin decidir nada.

## 6. Contraste C1 (único; Holm-1, α = 0,05)
- H1: M1 mejor que M0. Diebold-Mariano sobre d (LOCO), años como conglomerados, Newey-West 2 retardos, t con
  (años − 1) g. l., **unilateral** (`escenarios.dm_conglomerado`).
- **C1 establecido** si: (i) la puerta de calibración pasa; (ii) p < 0,05 y media de d > 0 en LOCO; (iii) media de d
  > 0 en el diseño temporal (mismo signo, sin exigir significación).
- Si la puerta no pasa, C1 se informa con su p pero se clasifica "no establecido (motor no calibrado)".

## 7. Descriptivo (sin contraste, sin decisión)
- CRPSS por activo y diseño; cobertura p10-p90; cobertura p5-p95 por régimen de partida; histograma PIT (10 casillas)
  por activo; Brier de "bolsa ≤ −20 % en el año" y "inflación simple > 5 % en el año" (M1 frente a frecuencia de M0).
- **h = 5 (LOCO):** rentabilidad real acumulada de 5 años consecutivos con fila (ventanas que empiezan en años
  ≡ 1 mod 5, sin solape); M1 = acumulada de sus trayectorias; M0 = acumuladas de todas las ventanas de 5 años
  consecutivos del entrenamiento. CRPSS y cobertura p5-p95. Sin potencia (§4.2 del diseño): solo descriptivo.

## 8. Salida "hoy" (descriptiva; script aparte, después de la corrida)
- Motor ajustado con **todas** las filas ≤ 2004 (14 países). Estado actual de cada país con datos en vivo de la OCDE
  (nunca JST, como `src/report/termometro_vivo`): inflación = Δlog de la media anual del IPC del último año completo
  publicado; brecha P3 aproximada con el **PIB real total** trimestral (suma de 4 trimestres; no per cápita: declarado)
  frente a la media de los 10 años anteriores. Se publica por país: estado, abanico p5/p10/p50/p90/p95 a 1 año de cada
  activo, P(bolsa ≤ −20 %), P(inflación > 5 %), con IC de parámetros. Todo marcado "estimado con datos ≤ 2004".

## 9. Salidas y registro
`scripts/int11_corrida.py` (puerta: árbol limpio, procedencia; se niega si `research/int/int11_resultado.json` ya
existe) → `research/int/int11_resultado.{json,md}`; fila en `research/trial_log.md`. `scripts/int11_hoy.py` →
`research/int/int11_hoy.{json,md}`.
