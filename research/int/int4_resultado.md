# INT-4: resultado de la corrida única

Procedencia: commit `e4cceb5`, árbol limpio True, 2026-10-26T19:20:17+00:00. Prerregistro v1.0 (fa6d4c9). Núcleo 14 países, 1871-2004 sin guerras, h = 1, dejar un país fuera; bootstrap por bloques de año (2.000); placebo con indicadores desplazados k = 6 … 129 años. Criterios (i)-(v) del §4.

## Familia principal (Holm-4)

| contraste | filas / eventos | AUC B1 → modelo | ΔAUC | IC 95 % bloques | p bloques | p placebo | Δlog-loss | ΔAUC temporal 1950-2004 | pendiente | ESTABLECIDO |
|---|---|---|---|---|---|---|---|---|---|---|
| T1 (C1, C2, C4, C5, C6) | 1090 / 166 | 0.546 → 0.725 | +0.178 | [+0.101; +0.255] | 0.0010 | 0.008 | -0.0408 | +0.311 | 0.88 | **sí** |
| T2 (S1, S2, S3, S4, S5) | 235 / 163 | 0.446 → 0.744 | +0.297 | [+0.199; +0.379] | 0.0010 | 0.008 | -0.0887 | +0.326 | 0.81 | **sí** |
| T3 (P1, P2, P3, P5) | 938 / 207 | 0.596 → 0.624 | +0.028 | [-0.009; +0.069] | 0.1139 | 0.016 | -0.0100 | +0.093 | 0.58 | **no** |
| T4 (P1, P2, P3, P5) | 483 / 224 | 0.554 → 0.656 | +0.103 | [+0.028; +0.170] | 0.0070 | 0.312 | -0.0267 | +0.019 | 0.80 | **no** |

Criterios: T1: {'i_dauc_ic_holm': True, 'ii_placebo_holm': True, 'iii_dlogloss_neg': True, 'iv_temporal_1950_2004_pos': True, 'v_pendiente_0.5_1.5': True}; T2: {'i_dauc_ic_holm': True, 'ii_placebo_holm': True, 'iii_dlogloss_neg': True, 'iv_temporal_1950_2004_pos': True, 'v_pendiente_0.5_1.5': True}; T3: {'i_dauc_ic_holm': False, 'ii_placebo_holm': True, 'iii_dlogloss_neg': True, 'iv_temporal_1950_2004_pos': True, 'v_pendiente_0.5_1.5': True}; T4: {'i_dauc_ic_holm': True, 'ii_placebo_holm': False, 'iii_dlogloss_neg': True, 'iv_temporal_1950_2004_pos': True, 'v_pendiente_0.5_1.5': True}

## Secundaria T1 (Holm-6, cada indicador añadido a B1)

| contraste | filas / eventos | AUC B1 → modelo | ΔAUC | IC 95 % bloques | p bloques | p placebo | Δlog-loss | ΔAUC temporal 1950-2004 | pendiente | ESTABLECIDO |
|---|---|---|---|---|---|---|---|---|---|---|
| C1 | 1286 / 212 | 0.541 → 0.635 | +0.094 | [+0.046; +0.144] | 0.0010 | 0.008 | -0.0045 | +0.092 | 0.66 | **sí** |
| C2 | 1141 / 177 | 0.544 → 0.562 | +0.018 | [-0.009; +0.044] | 0.1899 | 0.104 | -0.0003 | +0.019 | 0.58 | **no** |
| C3 | 979 / 140 | 0.456 → 0.463 | +0.007 | [-0.020; +0.031] | 0.5817 | 0.376 | +0.0007 | +0.004 | -1.18 | **no** |
| C4 | 1332 / 222 | 0.545 → 0.671 | +0.126 | [+0.065; +0.189] | 0.0010 | 0.008 | -0.0227 | +0.227 | 0.94 | **sí** |
| C5 | 1268 / 212 | 0.546 → 0.557 | +0.012 | [-0.004; +0.028] | 0.1429 | 0.048 | -0.0013 | +0.001 | 0.74 | **no** |
| C6 | 1253 / 201 | 0.544 → 0.662 | +0.118 | [+0.069; +0.165] | 0.0010 | 0.008 | -0.0140 | +0.171 | 0.86 | **sí** |

## Informativos (sin veredicto)

| contraste | filas / eventos | AUC B1 → modelo | ΔAUC | IC 95 % bloques | p bloques | p placebo | Δlog-loss | ΔAUC temporal | pendiente |
|---|---|---|---|---|---|---|---|---|---|
| T2 + S1 | 318 / 209 | 0.459 → 0.469 | +0.009 | [-0.027; +0.044] | 0.6727 | – | +0.0035 | – | -0.36 | 
| T2 + S2 | 318 / 208 | 0.456 → 0.467 | +0.011 | [-0.027; +0.059] | 0.6127 | – | +0.0010 | – | -0.56 | 
| T2 + S3 | 300 / 201 | 0.433 → 0.711 | +0.278 | [+0.183; +0.355] | 0.0010 | – | -0.0731 | – | 0.88 | 
| T2 + S4 | 334 / 220 | 0.452 → 0.538 | +0.087 | [-0.024; +0.186] | 0.1279 | – | -0.0044 | – | 0.45 | 
| T2 + S5 | 258 / 175 | 0.411 → 0.455 | +0.044 | [-0.023; +0.111] | 0.2049 | – | +0.0022 | – | -1.08 | 
| T3 + P1 | 1025 / 227 | 0.595 → 0.630 | +0.035 | [-0.002; +0.076] | 0.0560 | – | -0.0047 | – | 0.54 | 
| T3 + P2 | 1090 / 239 | 0.570 → 0.624 | +0.053 | [+0.009; +0.105] | 0.0100 | – | -0.0114 | – | 0.70 | 
| T3 + P3 | 1017 / 225 | 0.574 → 0.584 | +0.010 | [-0.023; +0.044] | 0.5537 | – | -0.0017 | – | 0.15 | 
| T3 + P5 | 1066 / 232 | 0.586 → 0.577 | -0.009 | [-0.034; +0.015] | 0.4968 | – | -0.0013 | – | 0.40 | 
| T4 + P1 | 520 / 244 | 0.568 → 0.599 | +0.031 | [-0.013; +0.075] | 0.1729 | – | +0.0052 | – | 0.34 | 
| T4 + P2 | 555 / 261 | 0.557 → 0.600 | +0.042 | [+0.002; +0.085] | 0.0390 | – | +0.0016 | – | 0.49 | 
| T4 + P3 | 523 / 244 | 0.464 → 0.563 | +0.099 | [+0.039; +0.158] | 0.0020 | – | +0.0020 | – | -0.09 | 
| T4 + P5 | 531 / 249 | 0.559 → 0.611 | +0.052 | [-0.009; +0.118] | 0.1149 | – | -0.0157 | – | 0.85 | 
| T1_h2 | 1056 / 287 | 0.536 → 0.714 | +0.177 | [+0.108; +0.249] | 0.0010 | – | -0.0528 | +0.250 | 0.85 | 
| T3_h2 | 913 / 373 | 0.570 → 0.626 | +0.057 | [+0.018; +0.096] | 0.0020 | – | -0.0089 | +0.108 | 0.62 | 
| T4_h2 | 469 / 344 | 0.480 → 0.711 | +0.230 | [+0.124; +0.328] | 0.0010 | – | -0.0463 | +0.099 | 0.82 | 
| T1_financieras | 980 / 56 | 0.640 → 0.828 | +0.188 | [+0.108; +0.259] | 0.0010 | – | -0.0342 | +0.560 | 0.85 | 
| T1_normales | 1034 / 110 | 0.409 → 0.663 | +0.254 | [+0.161; +0.346] | 0.0010 | – | -0.0165 | +0.251 | 0.75 | 
| T3_abs3 | 828 / 146 | 0.589 → 0.645 | +0.056 | [-0.004; +0.118] | 0.0700 | – | -0.0135 | +0.181 | 0.75 | 
| T3_sin_truncadas | 896 / 196 | 0.595 → 0.621 | +0.026 | [-0.013; +0.067] | 0.1809 | – | -0.0097 | +0.097 | 0.57 | 
| T3_P4_sobre_combinado | 938 / 207 | 0.624 → 0.640 | +0.016 | [-0.022; +0.052] | 0.4058 | – | -0.0099 | +0.047 | 0.71 | 
| T4_abs3 | 593 / 162 | 0.720 → 0.794 | +0.074 | [+0.021; +0.126] | 0.0080 | – | -0.0668 | +0.011 | 0.84 | 
| T4_sin_truncadas | 455 / 213 | 0.562 → 0.666 | +0.104 | [+0.024; +0.176] | 0.0070 | – | -0.0286 | -0.003 | 0.79 | 
| T4_P4_sobre_combinado | 483 / 224 | 0.656 → 0.660 | +0.004 | [-0.023; +0.031] | 0.7686 | – | +0.0016 | -0.003 | 0.73 | 

## Países de prueba (modelo congelado en el núcleo)

| giro | grupo | filas / eventos | ΔAUC | IC 95 % | por país |
|---|---|---|---|---|---|
| T1 | AUS_CHE | 147 / 36 | +0.207 | [+0.073; +0.336] | AUS +0.181 (20 ev.); CHE +0.259 (16 ev.) |
| T1 | CAN_IRL_sin_bolsa | 105 / 9 | +0.049 | [-0.252; +0.383] | CAN +0.161 (5 ev.); IRL -0.040 (4 ev.) |
| T2 | AUS_CHE | 53 / 35 | +0.221 | [+0.024; +0.403] | AUS +0.308 (20 ev.); CHE +0.093 (15 ev.) |
| T2 | CAN_IRL_sin_bolsa | 14 / 10 | +0.163 | [-0.179; +0.500] | CAN -0.021 (6 ev.); IRL – (4 ev.) |
| T3 | AUS_CHE | 145 / 27 | -0.011 | [-0.129; +0.117] | AUS -0.074 (14 ev.); CHE +0.034 (13 ev.) |
| T3 | CAN_IRL_sin_bolsa | 71 / 18 | -0.060 | [-0.196; +0.063] | CAN -0.077 (9 ev.); IRL -0.060 (9 ev.) |
| T4 | AUS_CHE | 72 / 30 | +0.145 | [-0.024; +0.302] | AUS +0.207 (16 ev.); CHE +0.096 (14 ev.) |
| T4 | CAN_IRL_sin_bolsa | 49 / 18 | +0.145 | [-0.032; +0.335] | CAN +0.326 (9 ev.); IRL -0.014 (9 ev.) |

## Sensibilidad del listón (declarada a posteriori, `scripts/int4_sensibilidad_liston.py`; no cambia la clasificación)
Causa del AUC < 0,5 del listón: sesgo de dejar un país fuera con un predictor débil (el intercepto se mueve contra la tasa
base del país dejado fuera; correlación tasa del país frente a predicción media del listón: T2 −0,97, T3 −0,67, T4 −0,53,
T1 +0,26). Corrección: AUC estratificada por país (solo pares del mismo país) y listón dentro de muestra (conservador).

| giro | corrida (agrupada) | estratificada | listón dentro de muestra |
|---|---|---|---|
| T1 entrada | +0,178 [+0,101; +0,255] | +0,198 [+0,121; +0,273] | +0,149 [+0,069; +0,227] |
| T2 salida | +0,298 [+0,199; +0,379] | **+0,188 [+0,081; +0,280]** | +0,209 [+0,111; +0,291] |
| T3 repunte | +0,028 [−0,009; +0,069] | +0,003 [−0,037; +0,045] | −0,004 |
| T4 vuelta | +0,103 [+0,028; +0,170] | +0,078 [+0,005; +0,148] | +0,067 [−0,003; +0,134] |

Lectura: T1 y T2 siguen claros (todas las IC lejos de 0); el efecto de T2 estaba inflado ≈ 0,1 por el listón: el real es
≈ +0,19-0,21. T3 no aporta nada. T4 se debilita (ya fallaba por el placebo).
