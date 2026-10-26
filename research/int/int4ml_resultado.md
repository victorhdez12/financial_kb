# INT-4-ML: resultado de la corrida única

Procedencia: commit `34858ee`, árbol limpio True, 2026-10-26T20:31:59+00:00. Prerregistro v1.0 (e1f67a6). scikit-learn 1.5.2. Listón = logit de INT-4 (B1 + indicadores). Núcleo 14 países, 1871-2004 sin guerras, h = 1, dejar un país fuera. Métrica principal: AUC estratificada por país.

| candidato · giro | filas / eventos | AUC estrat. logit → ML | ΔAUC estrat. | IC 95 % | p bloques | z placebo (p) | p rangos | ΔAUC agrupada | Δlog-loss [IC] | temporal | pendiente | ESTABLECIDO |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M-L2|T1 | 1090 / 166 | 0.732 → 0.729 | -0.003 | [-0.019; +0.016] | 0.8036 | -0.21 (0.5843) | 0.528 | -0.001 | +0.0163 [-0.0021; +0.0403] | -0.015 | 0.65 | **no** |
| M-GB|T1 | 1090 / 166 | 0.732 → 0.750 | +0.018 | [-0.011; +0.049] | 0.2359 | +0.64 (0.2616) | 0.288 | +0.013 | -0.0025 [-0.0164; +0.0102] | -0.015 | 0.74 | **no** |
| M-L2|T2 | 235 / 163 | 0.770 → 0.724 | -0.047 | [-0.087; -0.014] | 0.0070 | -0.95 (0.8280) | 0.832 | -0.034 | +0.0435 [+0.0177; +0.0733] | -0.231 | 0.60 | **no** |
| M-GB|T2 | 235 / 163 | 0.770 → 0.748 | -0.023 | [-0.091; +0.040] | 0.4958 | -0.19 (0.5738) | 0.552 | -0.028 | +0.0419 [-0.0022; +0.0879] | +0.088 | 0.55 | **no** |

Criterios: M-L2|T1: {'i_ic_estratificada_holm': False, 'ii_z_placebo_holm': False, 'iii_dlogloss_neg': False, 'iv_temporal_pos': False, 'v_pendiente_0.5_1.5': True}; M-GB|T1: {'i_ic_estratificada_holm': False, 'ii_z_placebo_holm': False, 'iii_dlogloss_neg': True, 'iv_temporal_pos': False, 'v_pendiente_0.5_1.5': True}; M-L2|T2: {'i_ic_estratificada_holm': False, 'ii_z_placebo_holm': False, 'iii_dlogloss_neg': False, 'iv_temporal_pos': False, 'v_pendiente_0.5_1.5': True}; M-GB|T2: {'i_ic_estratificada_holm': False, 'ii_z_placebo_holm': False, 'iii_dlogloss_neg': False, 'iv_temporal_pos': True, 'v_pendiente_0.5_1.5': True}

Regla de cierre: si ninguno queda establecido, la línea de ML queda cerrada con estos datos (§7): no se prueban otros modelos ni hiperparámetros sobre ≤ 2004.

## Países de prueba (AUS, CHE; modelos congelados; informativo)

| giro · candidato | filas / eventos | ΔAUC estrat. [IC] | ΔAUC agrupada | Δlog-loss |
|---|---|---|---|---|
| T1 · M-L2 | 147 / 36 | +0.014 [-0.014; +0.042] | +0.018 | -0.0107 |
| T1 · M-GB | 147 / 36 | -0.033 [-0.104; +0.036] | -0.030 | +0.0276 |
| T2 · M-L2 | 53 / 35 | +0.009 [-0.050; +0.084] | +0.005 | -0.0096 |
| T2 · M-GB | 53 / 35 | -0.036 [-0.140; +0.053] | -0.020 | -0.0115 |
