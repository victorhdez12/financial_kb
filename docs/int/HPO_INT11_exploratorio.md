---
documento: HPO EXPLORATORIO del motor de escenarios INT-11 v3 (configuración paralela "v3-hpo")
version: 0.1 (2026-11-04) — §1-§3 (espacio, presupuesto, regla) escritos y commiteados ANTES de correr
código: scripts/hpo_int11.py (corrida) · scripts/hpo_int11_analiza.py (anidado) · salida research/int/hpo_int11/
NO toca: Config.v3 (congelada, va a la confirmación), research/int/int11_v3_resultado.json, la salida "hoy"
datos: SOLO ≤ 2004 (cargar_real_v3 de la fase D). Nada ≥ 2005
---

# HPO exploratorio de INT-11 v3

## 0. Naturaleza (leer primero)
- **Exploratorio y contaminante.** Ajustar hiperparámetros con ≤ 2004 gasta más ese periodo de desarrollo (ya usado
  por v1, v2 y v3). Nada de aquí es evidencia de calibración. Config.v3 sigue siendo la que va a la fase C.
- Si algo destaca, solo se puede proponer una **"v4" a prerregistrar**, cuya evidencia vendría únicamente de la
  confirmación (≥ 2005), declarando que la elección se hizo mirando ≤ 2004.

## 1. Espacio (lo que el motor expone y afecta a la predictiva H = 1 en LOCO)
| hiperparámetro | v3 | espacio |
|---|---|---|
| `c_suavizado` (ensanchamiento 1 + c/n) | 5,25 | U[1; 10] |
| `nu_suavizado` (colas del ruido) | 5 | {3, 4, 5, 7, 10, 30} |
| `sigma_infl` (pertenencia suave, Δlog) | 0,005 | U[0; 0,0125] (0 = duro en ese eje) |
| `sigma_brecha` | 0,01 | U[0; 0,025] |
| `n0_curtosis` (encogimiento de la curtosis por país) | 50 | log-U[5; 1000] |
| `semivida_epoca` (años; 0 = apagada) | 50 | {0, 25, 35, 50, 75, 100, 150} |
| `n_min_celda` | 25 | {15, 20, 25, 30, 40, 50} |
| κ (fuerza del Dirichlet de la transición) | Bayes empírico, log10 κ ∈ [0; 6] | ½ "EB" (como v3), ½ log10 κ fijo ~ U[0; 4] |

Fuera del espacio, declarado: `k_pais` (en LOCO el país predicho no está en el pool: no tiene efecto medible),
`bloque_medio` (solo actúa con H > 1), `k_mezcla` (descartado en v2), eventos (apagados hasta INT-14), escala por país
(se deja encendida; su incertidumbre la regula `n0_curtosis`).

## 2. Presupuesto (fijado antes)
- **Búsqueda aleatoria**, N = 80 configuraciones + θ0 = Config.v3() exacta (81 candidatos), semilla del espacio
  20261105 (`scripts.hpo_int11.candidatos`).
- Sorteos: 50 lotes × 100 por régimen de partida (v3 oficial: 200 × 100). Comprobación: con 200 × 100 la tubería
  reproduce BIT A BIT la S5 LOCO oficial de v3 (0,897642) y cada S_a.
- Ajustes por candidato: 14 LOCO simples + 91 pares (fuera {c, d}), números aleatorios comunes entre candidatos.
- **Dos semillas Monte Carlo completas**: 20261104 (A) y 20261204 (B).
- Puntuaciones por fila y activo (rentabilidad real simple): CRPS de la mezcla ponderada (exacto para la muestra),
  log-score (núcleo gaussiano de Silverman por régimen de partida, mezcla de densidades), PIT = F(y), dentro del
  p5-p95 (cuantil de la CDF de la mezcla, como la fase D), anchura.
- Ejecución (cambio de ejecución sin ver resultados, 4-nov): la máquina estaba compartida y un trabajador del Pool
  murió y colgó el primer intento (sin resultados leídos). Ahora son 4 procesos independientes (≤ 4, BLAS a 1 hilo)
  con caché por configuración, y los pares guardan solo CRPS y dentro90, que es lo único que usa la regla interna.
  Los resultados no cambian: cada configuración es determinista dada la semilla (se comprobó con `prueba`).

## 3. Regla de elección y evaluación (fijada antes)
- **Anidado LOCO por país:** para cada país externo c, el interno es el LOCO sobre los otros 13 (ajuste sin {c, d},
  predice d). Admisibles: |S5_int − 0,90| ≤ 0,01 y todo activo |S_a,int − 0,90| ≤ 0,03. Entre ellos, **menor CRPS
  relativo a v3** (media por activo de ΣCRPS_θ / ΣCRPS_v3 en las mismas filas internas). Si ninguno, v3. El externo
  evalúa c con la θ elegida (ajuste sin c). El país externo nunca entra en la elección.
- **Comparación con v3** en las mismas filas y la misma semilla: ΔS5, Δcobertura de la bolsa, CRPS relativo, Δlog-score;
  **IC 90 % por bloques móviles de años** (5 años, B = 2000; todos los países de un año juntos). Por país y por régimen
  de partida (duro): S5, S_a, CRPS, PIT (χ² 10 bins por activo; máx |decil − 0,10|).
- **Ruido Monte Carlo:** v3(B) frente a v3(A) con el mismo bootstrap; el anidado se repite con B; y "cruzado": las
  elecciones hechas con A se evalúan con los sorteos externos de B (si la ganancia era suerte MC de la selección, se
  esfuma).
- **Registro de todas las pruebas:** research/int/hpo_int11/registro.csv (LOCO plano de los 81, dos semillas). La
  "mejor del LOCO plano" se informa solo para medir el optimismo frente al anidado.
- Criterio de "destaca" (para proponer v4): CRPS relativo anidado con IC 90 % entero < 0 en las DOS semillas y en el
  cruzado, mayor en valor absoluto que el ruido MC de v3, sin empeorar la calibración (S5 anidado dentro de 0,90 ± 0,01,
  PIT no peor que v3).

## 4. Resultado
(pendiente de la corrida)
