# INT-6: resultado de la corrida única (oro, dinero, crédito y relaciones entre países)

Procedencia: commit `12f6307`, árbol limpio True, 2026-10-29T18:25:27+00:00. Prerregistro: docs/int/INT6_prerregistro_v1.md (v1.0, congelado 2026-10-29T18:01:03Z, 1bdecf8). Concreciones: `docs/int/INT6_notas_implementacion.md`. Datos ≤ 2004 (nada de JST ≥ 2005).

## Resumen

| id | pregunta | efecto | IC 95 % | p_cal (placebo) | umbral Holm-6 | pasa Holm | veredicto |
|---|---|---|---|---|---|---|---|
| G2 | oro frente a Δ tipo real (EE. UU., mensual 1973-2004; signo −) | -1.351 % de oro por pp (r = -0.187) | [-2.073; -0.629] | 0.0010 | 0.0167 | sí | **establecido** |
| M1 | dinero real en t → bolsa real en t + 1 (signo +) | +0.91 pp por 1 dt | [-0.68; +2.50] | 0.2800 | 0.0500 | no | **no establecido** |
| M2 | dinero real en t → bonos reales en t + 1 (signo +) | -0.68 pp por 1 dt | [-1.36; -0.00] | 0.0568 | 0.0250 | no | **no establecido** |
| K1 | Δ5 crédito/PIB → inicio de crisis bancaria en t + 1 (signo +) | ΔAUC estrat. +0.113 (0.556 → 0.669) | [-0.007; +0.231] | 0.0008 | 0.0125 | sí | **no establecido** |
| K2 | Δ diferencial corporativo del centro (R. U. ≤ 1918, EE. UU. ≥ 1919) → entrada en recesión (signo +) | ΔAUC estrat. +0.071 (0.548 → 0.619) | [+0.012; +0.132] | 0.0000 | 0.0100 | sí | **no establecido** |
| X1 | % de otros países con el PIB cayendo → entrada en recesión (signo +) | ΔAUC estrat. +0.123 (0.543 → 0.666) | [+0.064; +0.187] | 0.0000 | 0.0083 | sí | **establecido** |

p_cal: G2, M1 y M2, p bilateral con la t dividida por φ = máx(1, dt de las t placebo) (INT-3b); K1, K2 y X1, p unilateral de la z del placebo de la ΔAUC estratificada (INT-4-ML). Holm-6 sobre estos seis p (α = 0,05).

## Detalle por pregunta

### G2: oro y tipo real

- 384 meses (1973-01-01 a 2004-12-01). b = -1.351 (% de oro por 1 pp de Δ tipo real), IC 95 % [-2.073; -0.629], t de Newey-West (6 retardos) -3.68, p 0.0003; r = -0.187.
- Placebo (361 desplazamientos): φ = 1.11, p_cal = 0.0010, p95 de |t| placebo = 2.18, p por rangos 0.003 (sin Holm).
- Mitades: 1973-1988 -1.508, 1989-2004 -0.010; anual diciembre a diciembre (32 años) -1.200.
- Criterios: {'1_b_negativo': True, '2_holm6_p_cal': True, '3_supera_p95_placebo': True, '4_signo_1973_1988_y_1989_2004': True, '5_signo_anual_dic_dic': True, 'ESTABLECIDO': True}.
- Sensibilidades (no deciden): tipo real largo b -1.802 (p 0.0016); sin 1979-1980 b -1.186 (p 0.0028); oro en EUR: omitida (no hay EUR/USD (ni ECU) antes de 1999 en las familias permitidas de src/intl/data.py y el prerregistro solo autoriza añadir boe_uk_corp_bond_spread_m (notas §B.6)).

### M1: dinero real → bolsa real del año siguiente

- 1585 filas, 14 países, 1871-2003. b = +0.91 pp por 1 dt de dinero real (dt = 6.2 pp), IC 95 % DK [-0.68; +2.50], t +1.13, p 0.2609.
- Placebo (122): φ = 1.04, p_cal = 0.2800, p por rangos 0.252.
- 1950-2004: +2.53 pp; con efectos de año: +1.17 pp; países con signo +: 7/14 sin encoger, 9/14 DL sin la media del año.
- Criterios: {'1_signo': True, '2_holm6_p_cal': False, '3_supera_p95_placebo': False, '4_signo_1950_2004': True, '5a_paises_sin_encoger_2_3': False, '5b_paises_dl_sin_año_2_3': False, '6_signo_efectos_de_año': True, 'ESTABLECIDO': False}.
- Sensibilidades (pp por 1 dt [IC]): sin_guerras +1.01 [-0.82; +2.84]; exceso_de_dinero -1.93 [-3.86; +0.00]; dinero_estrecho_real +0.98 [-0.30; +2.26]; t_mas_2 -2.35 [-3.91; -0.79]; letras_reales_informativa -0.23 [-0.70; +0.24]
- Países de prueba (pendiente con la z del núcleo, pp): AUS -0.48 (133 filas); CHE +1.45 (105 filas)

### M2: dinero real → bonos real del año siguiente

- 1651 filas, 14 países, 1871-2003. b = -0.68 pp por 1 dt de dinero real (dt = 6.2 pp), IC 95 % DK [-1.36; -0.00], t -1.99, p 0.0491.
- Placebo (122): φ = 1.03, p_cal = 0.0568, p por rangos 0.081.
- 1950-2004: -1.10 pp; con efectos de año: -0.33 pp; países con signo +: 3/14 sin encoger, 0/14 DL sin la media del año.
- Criterios: {'1_signo': False, '2_holm6_p_cal': False, '3_supera_p95_placebo': False, '4_signo_1950_2004': False, '5a_paises_sin_encoger_2_3': False, '5b_paises_dl_sin_año_2_3': False, '6_signo_efectos_de_año': False, 'ESTABLECIDO': False}.
- Sensibilidades (pp por 1 dt [IC]): sin_guerras -0.74 [-1.51; +0.02]; exceso_de_dinero -3.10 [-4.35; -1.86]; dinero_estrecho_real -1.24 [-1.94; -0.54]; t_mas_2 -1.67 [-2.54; -0.80]; letras_reales_informativa -0.23 [-0.70; +0.24]
- Países de prueba (pendiente con la z del núcleo, pp): AUS +0.10 (105 filas); CHE +2.63 (104 filas)

### K1

- 1137 filas, 49 eventos en 27 años. AUC estratificada B1 0.556 → modelo 0.669: ΔAUC +0.113 [-0.007; +0.231], p bloques 0.0630; ΔAUC agrupada +0.077; Δlog-loss -0.0050; pendiente de calibración 0.85.
- Placebo (124): media +0.015, dt 0.031, z +3.15, p_z 0.0008, p por rangos 0.024 (sin Holm).
- Periodos (ΔAUC estratificada): 1871_1913 +0.152 (21 ev.); 1919_2004 +0.165 (28 ev.); 1950_2004 +0.527 (10 ev.); temporal 1950-2004 +0.344.
- Criterios: {'i_dauc_estrat_ic_holm6': False, 'ii_z_placebo_holm6': True, 'iii_dlogloss_neg': True, 'iv_dauc_1871_1913_y_1919_2004_pos': True, 'v_pendiente_0.5_1.5': True, 'ESTABLECIDO': False}.
- Sensibilidades (ΔAUC estratificada; no deciden): h2 +0.102 [+0.004; +0.203]; crisisjst_old +0.122 [+0.002; +0.244]; credito_en_log +0.011 [-0.008; +0.028]; exclusion_3_años +0.144 [+0.022; +0.269]
- Países de prueba (modelo congelado): 372 filas / 6 eventos, ΔAUC estrat. +0.325 [+0.184; +0.491].

### K2

- 1304 filas, 218 eventos en 82 años. AUC estratificada B1 0.548 → modelo 0.619: ΔAUC +0.071 [+0.012; +0.132], p bloques 0.0180; ΔAUC agrupada +0.061; Δlog-loss -0.0091; pendiente de calibración 0.83.
- Placebo (124): media +0.006, dt 0.013, z +4.91, p_z 0.0000, p por rangos 0.008 (sin Holm).
- Periodos (ΔAUC estratificada): 1950_2004 +0.237 (61 ev.); temporal 1950-2004 +0.172.
- Criterios: {'i_dauc_estrat_ic_holm6': False, 'ii_z_placebo_holm6': True, 'iii_dlogloss_neg': True, 'iv_temporal_1950_2004_pos': True, 'v_pendiente_0.5_1.5': True, 'ESTABLECIDO': False}.
- Sensibilidades (ΔAUC estratificada; no deciden): solo_EEUU_1919_2004 +0.154 [+0.038; +0.269]; RU_todos_los_años +0.024 [-0.021; +0.073]; nivel_menos_mediana_10_años +0.046 [+0.001; +0.097]; sobre_logit_INT4_informativo +0.014 [-0.005; +0.036]; EEUU_propio_diferencial_descriptivo_dentro_de_muestra +0.253
- Países de prueba (modelo congelado): 329 filas / 66 eventos, ΔAUC estrat. +0.061 [-0.014; +0.143].

### X1

- 1314 filas, 220 eventos en 83 años. AUC estratificada B1 0.543 → modelo 0.666: ΔAUC +0.123 [+0.064; +0.187], p bloques 0.0010; ΔAUC agrupada +0.109; Δlog-loss -0.0139; pendiente de calibración 0.89.
- Placebo (124): media +0.011, dt 0.017, z +6.42, p_z 0.0000, p por rangos 0.008 (sin Holm).
- Periodos (ΔAUC estratificada): 1950_2004 +0.260 (61 ev.); temporal 1950-2004 +0.173.
- Criterios: {'i_dauc_estrat_ic_holm6': True, 'ii_z_placebo_holm6': True, 'iii_dlogloss_neg': True, 'iv_temporal_1950_2004_pos': True, 'v_pendiente_0.5_1.5': True, 'ESTABLECIDO': True}.
- Sensibilidades (ΔAUC estratificada; no deciden): EEUU_con_PIB_cayendo_otros_13 +0.049 [-0.006; +0.105]; cuota_ponderada_PIB +0.096 [+0.039; +0.157]; sobre_logit_INT4_informativo +0.022 [+0.000; +0.044]; 1950_2004 +0.056 [-0.042; +0.160]
- Países de prueba (modelo congelado): 330 filas / 66 eventos, ΔAUC estrat. +0.124 [+0.031; +0.219].

K2, EBP: omitido (fed_ebp_* no está en las familias permitidas (la decisión 4 no lo añade); solo descriptivo, 4 entradas, no es 'as of' (notas §E.4)).

## Descriptivas e informativas (sin Holm, sin veredicto)

### G1: oro como refugio

**Con datos ≤ 2004 esto no puede distinguir un refugio de +10-20 pp de cero.**

| tramo · estado | efecto (pp/año) | IC 95 % DK | n (en el estado) | MDE 1 / Holm-6 (pp) |
|---|---|---|---|---|
| 1972_2004|recesion | -3.3 | [-18.3; +11.7] | 462 (61) | 29.9 / 37.1 |
| 1972_2004|recesion_financiera | -0.4 | [-15.3; +14.5] | 462 (15) | 36.6 / 45.5 |
| 1972_2004|crisis_inicio_y_siguiente | -7.6 | [-15.9; +0.7] | 462 (20) | 31.4 / 39.0 |
| 1877_1971|recesion | +1.7 | [-2.6; +6.1] | 1288 (325) | 11.6 / 14.4 |
| 1877_1971|recesion_financiera | +3.5 | [-1.3; +8.4] | 1288 (97) | 15.5 / 19.3 |
| 1877_1971|crisis_inicio_y_siguiente | +6.4 | [+1.3; +11.4] | 1288 (101) | 16.2 / 20.1 |
| 1877_2004|recesion | +0.3 | [-4.9; +5.5] | 1750 (386) | 12.3 / 15.3 |
| 1877_2004|recesion_financiera | +2.5 | [-2.4; +7.5] | 1750 (112) | 16.0 / 19.8 |
| 1877_2004|crisis_inicio_y_siguiente | +3.7 | [-1.3; +8.8] | 1750 (121) | 16.4 / 20.4 |
- Oro real en USD frente a la cuota del núcleo en recesión, 1972_2004: -26.3 pp de 0 % a 100 % [-77.4; +24.8] (-4.9 pp por 1 dt de la cuota; MDE 0→100 76.8 / 95.4).
- Oro real en USD frente a la cuota del núcleo en recesión, 1877_2004: -6.6 pp de 0 % a 100 % [-22.9; +9.7] (-1.4 pp por 1 dt de la cuota; MDE 0→100 20.7 / 25.7).
- Oro en los 24 meses con la bolsa de EE. UU. ≤ −5 % (1973-2004): -0.86 pp en el mes frente al resto [-3.43; +1.70] (MDE 3.3 / 4.1).
- Oro en los 14 meses con la bolsa de EE. UU. ≤ −8 % (1973-2004): -0.34 pp en el mes frente al resto [-4.00; +3.32] (MDE 4.33 / 5.38).

### M3: dinero → entrada en recesión (informativa)

- frente_a_B1: 1224 filas / 206 eventos; ΔAUC estratificada +0.074 [+0.024; +0.121]; z placebo +7.11; temporal 1950-2004 +0.158.
- sobre_logit_INT4: 1034 filas / 159 eventos; ΔAUC estratificada +0.005 [-0.011; +0.021]; z placebo +2.34; temporal 1950-2004 +0.010.

### ICC por décadas (parte común entre países; solo descriptiva)

| década | filas | ICC crecimiento | ICC recesión |
|---|---|---|---|
| 1870s | 126 | 0.04 | 0.19 |
| 1880s | 140 | 0.06 | 0.05 |
| 1890s | 140 | 0.01 | 0.01 |
| 1900s | 140 | 0.15 | 0.05 |
| 1910s | 140 | 0.32 | 0.30 |
| 1920s | 140 | 0.06 | 0.01 |
| 1930s | 140 | 0.20 | 0.25 |
| 1940s | 140 | 0.07 | 0.13 |
| 1950s | 140 | 0.09 | 0.16 |
| 1960s | 140 | 0.01 | 0.00 |
| 1970s | 140 | 0.35 | 0.34 |
| 1980s | 140 | 0.26 | 0.14 |
| 1990s | 140 | 0.29 | 0.32 |
| 2000s | 70 | 0.57 | 0.14 |

"No establecido" no es "no existe": varias preguntas tenían una potencia de ≈ 40-80 % (§2 del prerregistro).
Detalle completo en `research/int/int6_resultado.json`.
