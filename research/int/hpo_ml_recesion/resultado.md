# HPO-ML-RECESIÓN (exploratorio): resultado anidado

Procedencia: commit `9240372`, árbol limpio True, 2026-11-04T16:03:14+00:00 → 2026-11-04T18:00:50+00:00. scikit-learn 1.5.2. Presupuesto 20 configuraciones por candidato; placebo 30 réplicas. Listón: logit de INT-4. Métrica: AUC estratificada por país.

## T1 (1090 filas / 166 eventos; AUC estrat. logit 0.732)

| selector | AUC estrat. | ΔAUC anidada | IC 95 % bloques | p bloques | placebo media [p5; p95] | z (p) | Δlog-loss [IC] | pendiente | ¿candidata? |
|---|---|---|---|---|---|---|---|---|---|
| GB | 0.752 | +0.020 | [-0.014; +0.054] | 0.243 | +0.001 [-0.048; +0.049] | +0.54 (0.293) | -0.0060 [-0.0195; +0.0062] | 1.07 | no |
| RF | 0.749 | +0.017 | [-0.016; +0.049] | 0.291 | -0.000 [-0.039; +0.070] | +0.48 (0.315) | -0.0086 [-0.0227; +0.0057] | 1.07 | no |
| EN | 0.724 | -0.007 | [-0.017; +0.002] | 0.109 | +0.003 [-0.048; +0.055] | -0.31 (0.624) | +0.0142 [+0.0000; +0.0376] | 0.72 | no |
| TODOS | 0.752 | +0.020 | [-0.014; +0.054] | 0.239 | -0.002 [-0.044; +0.049] | +0.70 (0.241) | -0.0057 [-0.0190; +0.0065] | 1.06 | no |

Optimismo de elegir SIN anidar: la mejor de las 60 configuraciones medida en el propio LOCO externo da ΔAUC +0.035 (placebo: media +0.045, p95 +0.089).

Mejores 5 configuraciones por puntuación interna media (registro completo en resultado.json):

| id | params | interna media | LOCO no anidado ΔAUC |
|---|---|---|---|
| GB09 | `{"l2_regularization": 1.0, "learning_rate": 0.0392, "max_depth": 3, "max_iter": 50, "min_samples_leaf": 10, "monotonia": true}` | 0.761 | +0.035 |
| GB07 | `{"l2_regularization": 10.0, "learning_rate": 0.068, "max_depth": 2, "max_iter": 100, "min_samples_leaf": 80, "monotonia": true}` | 0.757 | +0.028 |
| GB14 | `{"l2_regularization": 0.1, "learning_rate": 0.0265, "max_depth": 3, "max_iter": 50, "min_samples_leaf": 80, "monotonia": true}` | 0.755 | +0.024 |
| GB17 | `{"l2_regularization": 1.0, "learning_rate": 0.0161, "max_depth": 2, "max_iter": 100, "min_samples_leaf": 20, "monotonia": true}` | 0.754 | +0.026 |
| GB01 | `{"l2_regularization": 10.0, "learning_rate": 0.0356, "max_depth": 2, "max_iter": 200, "min_samples_leaf": 10, "monotonia": false}` | 0.754 | +0.024 |

## T2 (235 filas / 163 eventos; AUC estrat. logit 0.770)

| selector | AUC estrat. | ΔAUC anidada | IC 95 % bloques | p bloques | placebo media [p5; p95] | z (p) | Δlog-loss [IC] | pendiente | ¿candidata? |
|---|---|---|---|---|---|---|---|---|---|
| GB | 0.729 | -0.042 | [-0.100; +0.021] | 0.173 | -0.013 [-0.082; +0.094] | -0.48 (0.686) | +0.0113 [-0.0324; +0.0488] | 1.08 | no |
| RF | 0.709 | -0.061 | [-0.124; -0.001] | 0.050 | +0.006 [-0.071; +0.073] | -1.26 (0.896) | +0.0149 [-0.0226; +0.0481] | 1.10 | no |
| EN | 0.774 | +0.003 | [-0.012; +0.021] | 0.686 | -0.001 [-0.058; +0.079] | +0.09 (0.465) | +0.0166 [-0.0256; +0.0533] | 1.14 | no |
| TODOS | 0.738 | -0.033 | [-0.083; +0.016] | 0.189 | -0.014 [-0.094; +0.089] | -0.32 (0.627) | +0.0265 [-0.0179; +0.0653] | 1.21 | no |

Optimismo de elegir SIN anidar: la mejor de las 60 configuraciones medida en el propio LOCO externo da ΔAUC +0.000 (placebo: media +0.069, p95 +0.132).

Mejores 5 configuraciones por puntuación interna media (registro completo en resultado.json):

| id | params | interna media | LOCO no anidado ΔAUC |
|---|---|---|---|
| EN09 | `{"C": 0.0029, "interacciones": false, "l1_ratio": 0.0}` | 0.764 | -0.002 |
| EN18 | `{"C": 3.6148, "interacciones": false, "l1_ratio": 0.5}` | 0.764 | +0.000 |
| EN12 | `{"C": 0.0251, "interacciones": false, "l1_ratio": 0.0}` | 0.762 | +0.000 |
| EN06 | `{"C": 0.7569, "interacciones": false, "l1_ratio": 0.5}` | 0.762 | -0.001 |
| EN15 | `{"C": 0.2832, "interacciones": false, "l1_ratio": 0.25}` | 0.760 | -0.004 |

Criterios (todos para 'candidata a prerregistro'): T1|GB: {'a_ic_holm': False, 'b_placebo_holm': False, 'c_dlogloss_neg': True, 'd_supera_mde_0.05': False}; T1|RF: {'a_ic_holm': False, 'b_placebo_holm': False, 'c_dlogloss_neg': True, 'd_supera_mde_0.05': False}; T1|EN: {'a_ic_holm': False, 'b_placebo_holm': False, 'c_dlogloss_neg': False, 'd_supera_mde_0.05': False}; T1|TODOS: {'a_ic_holm': False, 'b_placebo_holm': False, 'c_dlogloss_neg': True, 'd_supera_mde_0.05': False}; T2|GB: {'a_ic_holm': False, 'b_placebo_holm': False, 'c_dlogloss_neg': False, 'd_supera_mde_0.05': False}; T2|RF: {'a_ic_holm': False, 'b_placebo_holm': False, 'c_dlogloss_neg': False, 'd_supera_mde_0.05': False}; T2|EN: {'a_ic_holm': False, 'b_placebo_holm': False, 'c_dlogloss_neg': False, 'd_supera_mde_0.05': False}; T2|TODOS: {'a_ic_holm': False, 'b_placebo_holm': False, 'c_dlogloss_neg': False, 'd_supera_mde_0.05': False}

