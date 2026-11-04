---
documento: HPO EXPLORATORIO del motor de escenarios INT-11 v3 (configuración paralela "v3-hpo")
version: 1.0 (2026-11-04) — §1-§3 (espacio, presupuesto, regla) commiteados ANTES de correr (bb8b1fa); §4-§6 tras la corrida
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

## 4. Resultado (research/int/hpo_int11/resultado.json, registro.csv)
Procedencia: corridas A d1f40bc y B 67db661, análisis 4de264e, las tres con el árbol limpio. Las matrices por fila
(`corrida_s{0,1}.npz`, 40 MB) quedan fuera de git y se reproducen con el código y las semillas.

### 4.1 En una frase
El ajuste anidado **no mejora a v3 de forma distinguible**. El CRPS baja un 0,16 % (semilla A) y un 0,24 % (B), con
IC 90 % que incluyen el 0 en las dos semillas y en el cruzado. La cobertura queda algo por encima del 90 % (90,5-90,8 %
frente al 89,8 % de v3). La mejora real está en la **forma**: el PIT de la bolsa pasa de claramente no uniforme a
uniforme, porque se cambia el exceso de anchura de la bolsa por la falta de anchura de las letras. En los 34 años de
estanflación, en cambio, empeora.

### 4.2 Anidado frente a v3 (mismas filas y semilla; IC 90 % por bloques de 5 años)
| | semilla A | semilla B | cruzado (elige A, evalúa B) | ruido MC (v3 B − v3 A) |
|---|---|---|---|---|
| S5 anidado (v3) | 0,9054 (0,8975) | 0,9078 (0,8979) | 0,9061 (0,8979) | — |
| ΔS5 | +0,79 pp [+0,36; +1,32] | +1,00 pp [+0,53; +1,56] | +0,83 pp [+0,32; +1,44] | +0,04 pp [−0,18; +0,27] |
| Δ cobertura bolsa | −1,28 pp [−1,77; −0,68] | −0,94 pp [−1,50; −0,34] | −1,01 pp [−1,54; −0,46] | −0,07 pp [−0,40; +0,34] |
| CRPS relativo | **−0,16 % [−0,70; +0,38]** | **−0,24 % [−0,84; +0,35]** | −0,28 % [−0,82; +0,35] | +0,04 % [−0,02; +0,11] |
| Δ log-score (< 0 mejor) | −0,012 [−0,036; +0,004] | +0,001 [−0,015; +0,019] | −0,008 [−0,020; +0,002] | +0,001 [−0,015; +0,017] |

Cobertura por activo (A; entre paréntesis v3): bolsa 0,914 (0,927), bonos 0,908 (0,905), letras 0,910 (0,881),
vivienda 0,907 (0,895), oro 0,892 (0,898). **PIT, χ² con 10 bins (p):** bolsa 7,4 (0,59) frente a v3 65,7 (< 0,001), y en B
12,5 (0,19) frente a 64,4 (< 0,001). Bonos 7,2 (0,62) frente a 17,3 (0,04). El resto queda igual de uniforme. Máx
|decil − 0,10|: 0,0085 frente a 0,0107 (A) y 0,0112 frente a 0,0093 (B).

La diferencia de CRPS es mayor que el ruido MC (±0,07 %), pero mucho menor que la incertidumbre por años (±0,6 %). La
ordenación de los 81 candidatos es estable entre semillas (Spearman del CRPS relativo LOCO plano = 0,97), así que
**no es suerte Monte Carlo**: es una mejora pequeña que los datos no distinguen.

### 4.3 Optimismo de la selección
- Interno (13 países): el elegido mejora el CRPS de v3 entre un 0,31 % y un 0,64 % según el país. En el externo la mejora
  queda en el 0,16-0,24 %, así que alrededor de la mitad era sesgo de selección. LOCO plano (elige y evalúa en las mismas
  filas): −0,35 % (A, id 74) y −0,43 % (B, id 48).
- 61 de los 81 candidatos son admisibles en LOCO plano, v3 incluida. El CRPS relativo varía entre −0,4 % y +0,3 %
  salvo en las configuraciones con colas ν ≤ 4, que de vez en cuando explotan (CRPS × 2-8700 en una de las dos semillas:
  ids 2, 42, 45, 66), porque un sorteo t3/t4 en log da una rentabilidad absurda tras `expm1`. **ν = 5 (v3) es el
  mínimo seguro.**
- Elegidos: en A, id 74 en 8 países, 35, 48 y 64 en dos cada uno, y 55 en uno. En B, 74 en 7 países, 7, 35 y 48 en dos
  cada uno, y 64 y 21 en uno. Patrón común: **c ≈ 2,5-3,7 (menos que el 5,25 de v3), σ más anchas (σπ ≈ 0,6-1,2 pp,
  σb ≈ 1,5-2,5 pp), semivida apagada o larga (100-150 años)**. κ, n0_curtosis y n_min_celda no muestran un patrón.

### 4.4 Por régimen de partida y por país (anidado, A; B igual de signo)
| régimen | filas | S5 anidado | S5 v3 | CRPS rel. | máx desv. PIT (v3) |
|---|---|---|---|---|---|
| expansión | 833 | 0,918 | 0,905 | −0,42 % | 0,018 (0,020) |
| sobrecalentamiento | 616 | 0,898 | 0,890 | −0,26 % | 0,008 (0,013) |
| **estanflación** | 34 | **0,787** (B 0,838) | 0,875 | **+5,8 %** (B +5,5 %) | 0,112 (0,035) |
| crecimiento bajo | 65 | 0,878 | 0,887 | −0,45 % | 0,023 (0,032) |

Por país: la S5 sube en 10 de los 14 (lo que más, ESP +2,9 pp, DNK +2,4 pp y PRT +1,9 pp) y baja algo en GBR
(−1,1 pp), JPN (−0,7 pp) y SWE (−0,3 pp); FRA queda igual. Los 14 países quedan dentro de su banda nula por país de la
corrida oficial (DNK, con 0,952, es el que más se acerca al techo de su banda, 0,958). FIN (0,828) y PRT (0,859) siguen siendo los peor cubiertos, como en v3: el HPO
no arregla la heterogeneidad entre países. El CRPS empeora en FRA (+1,2 %) y GBR (+0,6 %, solo en A).

## 5. Conclusión
- **No se cumple el criterio de "destaca"** (§3): el IC del CRPS relativo cruza el 0 en las dos semillas y en el
  cruzado, y en estanflación empeora. **No se propone una v4 como mejora de exactitud.** Config.v3 sigue siendo el motor
  de la confirmación, sin cambios.
- Lo único que tiene contenido es la **forma**: v3 se pasa de anchura en la bolsa y se queda corta en las letras. La
  región "c más bajo + σ más anchas" lo reequilibra y vuelve uniforme el PIT de la bolsa sin perder CRPS. Si en algún
  momento se quiere una v4, **solo como prerregistro nuevo** y con estas condiciones:
  - candidata fijada de antemano (p. ej. la id 74: c 3,73, ν 10, σπ 0,62 pp, σb 2,47 pp, semivida apagada,
    n_min_celda 20, κ EB, n0 36);
  - declarar que salió de ajustar con ≤ 2004 (contamina el desarrollo; su fase D no valdría como prueba);
  - evidencia **solo** en el bloqueado ≥ 2005, compitiendo con v3 dentro del Holm de la confirmación final (D7 dice un
    solo motor; meter v4 exigiría cambiar D7, que es una decisión del usuario);
  - vigilar la estanflación (34 filas: es donde una pertenencia más suave mezcla de más).
- Recomendación: **no merece la pena**. La ganancia esperada (≈ 0,2 % de CRPS) no compensa el coste en potencia de
  añadir un motor a la familia de la confirmación.
- Lección de ingeniería: no bajar de ν = 5 en el ruido de suavizado (con ν ≤ 4 hay explosiones esporádicas).

## 6. Qué no se ha hecho
H > 1 (`bloque_medio`), `k_pais` (sin efecto en LOCO), el diseño temporal, Brier de inflación > 5 % y caída ≥ 20 %,
banda nula propia del HPO (la anchura de la incertidumbre se mide por bloques de años, no con el nulo P1).
