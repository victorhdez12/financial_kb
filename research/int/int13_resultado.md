---
documento: Resultado INT-13 (EXPLORATORIO): XGBoost por paquetes como corrección de un logit clásico
plan: docs/int/INT13_plan_exploratorio.md (d315777)
procedencia: {'commit': '3bfd43a8babfc846b6e1e91724487a71a83d8e89', 'arbol_limpio': True, 'hora_utc': '2026-10-30T14:16:17+00:00'}
datos: panel OCDE mensual de 18 países, orígenes 1960-01 … 2004-12 − h. NADA ≥ 2005
---

# INT-13: qué paquete de datos aporta a qué objetivo (exploratorio)

> **Exploratorio: cualquier hallazgo necesita prerregistro y confirmación en vivo o en el bloqueado.** Los datos ≤ 2004 ya se usaron en INT-4, INT-4-ML, INT-8 e INT-12.

**Número de pruebas:** 32 (4 objetivos × [base frente a clima + 6 paquetes + combinación frente a la base]) en V1, corregidas con Holm; V2 repite las mismas como comprobación.

## Muestras

| objetivo | filas | eventos | meses con evento | países | V2 (1990-2004): filas / eventos |
|---|---|---|---|---|---|
| E1_6 | 5292 | 152 | 86 | 18 | 2284 / 64 |
| E1_12 | 5232 | 380 | 157 | 18 | 2224 / 158 |
| E2 | 8635 | 1215 | 357 | 17 | 2856 / 74 |
| E3 | 6640 | 1635 | 408 | 16 | 2114 / 255 |

## Calidad de la probabilidad (V1, dejar un país fuera)

| objetivo | modelo | log-loss [IC 95 %] | Brier | AUC [IC 95 %] | pendiente calibración |
|---|---|---|---|---|---|
| E1_6 | clima | 0.1305 [+0.0763; +0.2019] | 0.0279 | +0.408 [+0.331; +0.486] | -15.31 |
| E1_6 | base | 0.1282 [+0.0750; +0.1993] | 0.0281 | +0.661 [+0.567; +0.740] | +0.68 |
| E1_6 | P1_curva_tipos | 0.1209 [+0.0701; +0.1905] | 0.0278 | +0.766 [+0.686; +0.824] | +0.69 |
| E1_6 | P2_credito | 0.1309 [+0.0748; +0.2038] | 0.0285 | +0.638 [+0.530; +0.752] | +0.48 |
| E1_6 | P3_actividad | 0.1033 [+0.0597; +0.1610] | 0.0255 | +0.858 [+0.784; +0.912] | +0.82 |
| E1_6 | P4_precios | 0.1163 [+0.0658; +0.1827] | 0.0269 | +0.763 [+0.658; +0.844] | +0.79 |
| E1_6 | P5_mercados | 0.1156 [+0.0676; +0.1767] | 0.0275 | +0.797 [+0.726; +0.850] | +0.78 |
| E1_6 | P6_global | 0.1053 [+0.0587; +0.1628] | 0.0255 | +0.836 [+0.728; +0.899] | +0.89 |
| E1_6 | combinacion | 0.1047 [+0.0587; +0.1648] | 0.0262 | +0.886 [+0.821; +0.928] | +1.50 |
| E1_12 | clima | 0.2609 [+0.1642; +0.3801] | 0.0674 | +0.406 [+0.346; +0.472] | -15.23 |
| E1_12 | base | 0.2520 [+0.1584; +0.3661] | 0.0660 | +0.661 [+0.577; +0.732] | +0.79 |
| E1_12 | P1_curva_tipos | 0.2455 [+0.1529; +0.3601] | 0.0661 | +0.739 [+0.662; +0.805] | +0.61 |
| E1_12 | P2_credito | 0.2580 [+0.1578; +0.3779] | 0.0669 | +0.656 [+0.542; +0.759] | +0.52 |
| E1_12 | P3_actividad | 0.2148 [+0.1331; +0.3164] | 0.0589 | +0.828 [+0.753; +0.887] | +0.87 |
| E1_12 | P4_precios | 0.2309 [+0.1448; +0.3291] | 0.0606 | +0.753 [+0.655; +0.831] | +0.73 |
| E1_12 | P5_mercados | 0.2265 [+0.1452; +0.3226] | 0.0633 | +0.794 [+0.733; +0.849] | +0.78 |
| E1_12 | P6_global | 0.2052 [+0.1240; +0.2945] | 0.0553 | +0.825 [+0.711; +0.902] | +0.86 |
| E1_12 | combinacion | 0.2075 [+0.1259; +0.3036] | 0.0581 | +0.855 [+0.769; +0.909] | +1.30 |
| E2 | clima | 0.4076 [+0.3102; +0.5220] | 0.1212 | +0.384 [+0.336; +0.424] | -15.42 |
| E2 | base | 0.4036 [+0.3058; +0.5173] | 0.1202 | +0.563 [+0.490; +0.635] | +0.82 |
| E2 | P1_curva_tipos | 0.3733 [+0.2836; +0.4730] | 0.1122 | +0.708 [+0.638; +0.760] | +0.90 |
| E2 | P2_credito | 0.3967 [+0.2945; +0.5194] | 0.1189 | +0.620 [+0.547; +0.681] | +0.74 |
| E2 | P3_actividad | 0.3600 [+0.2712; +0.4593] | 0.1106 | +0.746 [+0.691; +0.789] | +0.94 |
| E2 | P4_precios | 0.3645 [+0.2801; +0.4512] | 0.1085 | +0.717 [+0.629; +0.783] | +1.01 |
| E2 | P5_mercados | 0.4032 [+0.3069; +0.5153] | 0.1200 | +0.588 [+0.535; +0.627] | +0.59 |
| E2 | P6_global | 0.3503 [+0.2726; +0.4354] | 0.1046 | +0.759 [+0.667; +0.810] | +1.10 |
| E2 | combinacion | 0.3554 [+0.2698; +0.4512] | 0.1080 | +0.793 [+0.729; +0.836] | +2.11 |
| E3 | clima | 0.5599 [+0.4764; +0.6574] | 0.1862 | +0.400 [+0.355; +0.448] | -14.10 |
| E3 | base | 0.5458 [+0.4623; +0.6458] | 0.1809 | +0.591 [+0.497; +0.683] | +0.84 |
| E3 | P1_curva_tipos | 0.5406 [+0.4611; +0.6339] | 0.1793 | +0.623 [+0.552; +0.688] | +0.74 |
| E3 | P2_credito | 0.5434 [+0.4657; +0.6421] | 0.1792 | +0.616 [+0.544; +0.671] | +0.70 |
| E3 | P3_actividad | 0.5288 [+0.4527; +0.6264] | 0.1748 | +0.662 [+0.605; +0.714] | +0.73 |
| E3 | P4_precios | 0.5148 [+0.4386; +0.5986] | 0.1689 | +0.687 [+0.617; +0.751] | +0.93 |
| E3 | P5_mercados | 0.5225 [+0.4490; +0.6134] | 0.1724 | +0.669 [+0.621; +0.723] | +0.98 |
| E3 | P6_global | 0.4895 [+0.4265; +0.5627] | 0.1588 | +0.735 [+0.656; +0.783] | +1.02 |
| E3 | combinacion | 0.5010 [+0.4311; +0.5856] | 0.1639 | +0.737 [+0.674; +0.789] | +1.72 |

## Contrastes (Δ = modelo − listón; log-loss negativo = mejor). Ordenados por p de V1

| objetivo | comparación | Δlog-loss V1 [IC 95 %] | p V1 | p Holm-32 | Δlog-loss V2 [IC 95 %] | pend. cal. | ¿candidato? | potencia 20 a (Δ / Δ½) |
|---|---|---|---|---|---|---|---|---|
| E3 | combinacion_vs_base | -0.0449 [-0.0643; -0.0276] | +0.000 | +0.000 | -0.0204 [-0.0360; -0.0070] | +1.72 | no | +0.93 / +0.46 |
| E1_12 | combinacion_vs_base | -0.0445 [-0.0669; -0.0290] | +0.000 | +0.000 | -0.0191 [-0.0331; -0.0028] | +1.30 | **sí** | +0.91 / +0.44 |
| E1_6 | combinacion_vs_base | -0.0236 [-0.0367; -0.0142] | +0.000 | +0.000 | -0.0167 [-0.0239; -0.0100] | +1.50 | no | +0.87 / +0.40 |
| E2 | combinacion_vs_base | -0.0482 [-0.0742; -0.0285] | +0.000 | +0.001 | -0.0559 [-0.0758; -0.0365] | +2.11 | no | +0.84 / +0.37 |
| E2 | P3_actividad_vs_base | -0.0436 [-0.0704; -0.0202] | +0.000 | +0.009 | -0.0830 [-0.1139; -0.0417] | +0.94 | **sí** | +0.74 / +0.31 |
| E3 | P6_global_vs_base | -0.0564 [-0.0972; -0.0216] | +0.002 | +0.049 | -0.0371 [-0.0811; +0.0140] | +1.02 | **sí** | +0.62 / +0.25 |
| E1_12 | P3_actividad_vs_base | -0.0372 [-0.0645; -0.0145] | +0.002 | +0.053 | -0.0287 [-0.0850; +0.0178] | +0.87 | no | +0.61 / +0.25 |
| E1_6 | P3_actividad_vs_base | -0.0249 [-0.0456; -0.0100] | +0.003 | +0.080 | -0.0172 [-0.0468; +0.0050] | +0.82 | no | +0.57 / +0.23 |
| E1_6 | P6_global_vs_base | -0.0229 [-0.0435; -0.0101] | +0.004 | +0.096 | -0.0001 [-0.0156; +0.0121] | +0.89 | no | +0.55 / +0.22 |
| E1_12 | P6_global_vs_base | -0.0468 [-0.0899; -0.0198] | +0.006 | +0.128 | +0.0215 [-0.0305; +0.0531] | +0.86 | no | +0.52 / +0.21 |
| E2 | P6_global_vs_base | -0.0532 [-0.1015; -0.0189] | +0.006 | +0.135 | -0.0116 [-0.0653; +0.0368] | +1.10 | no | +0.51 / +0.21 |
| E2 | P1_curva_tipos_vs_base | -0.0302 [-0.0555; -0.0076] | +0.006 | +0.136 | -0.0665 [-0.0981; -0.0329] | +0.90 | no | +0.50 / +0.21 |
| E3 | P4_precios_vs_base | -0.0310 [-0.0624; -0.0071] | +0.014 | +0.274 | +0.0186 [-0.0315; +0.0454] | +0.93 | no | +0.43 / +0.18 |
| E3 | P5_mercados_vs_base | -0.0233 [-0.0451; -0.0032] | +0.014 | +0.274 | +0.0281 [+0.0069; +0.0491] | +0.98 | no | +0.43 / +0.18 |
| E1_12 | P5_mercados_vs_base | -0.0255 [-0.0529; -0.0046] | +0.021 | +0.372 | -0.0082 [-0.0281; +0.0160] | +0.78 | no | +0.39 / +0.17 |
| E2 | P4_precios_vs_base | -0.0391 [-0.0828; -0.0104] | +0.022 | +0.378 | -0.0206 [-0.0630; +0.0069] | +1.01 | no | +0.38 / +0.16 |
| E1_6 | P4_precios_vs_base | -0.0119 [-0.0255; -0.0017] | +0.027 | +0.437 | +0.0024 [-0.0149; +0.0207] | +0.79 | no | +0.36 / +0.16 |
| E1_6 | P5_mercados_vs_base | -0.0126 [-0.0275; -0.0010] | +0.030 | +0.450 | -0.0094 [-0.0192; +0.0084] | +0.78 | no | +0.35 / +0.15 |
| E1_12 | P4_precios_vs_base | -0.0211 [-0.0488; -0.0042] | +0.036 | +0.497 | +0.0287 [-0.0267; +0.0867] | +0.73 | no | +0.33 / +0.15 |
| E1_6 | P1_curva_tipos_vs_base | -0.0074 [-0.0161; +0.0010] | +0.049 | +0.639 | -0.0036 [-0.0157; +0.0109] | +0.69 | no | +0.29 / +0.14 |
| E1_12 | base_vs_clima | -0.0089 [-0.0206; +0.0006] | +0.054 | +0.643 | -0.0050 [-0.0203; +0.0182] | +0.79 | no | +0.28 / +0.13 |
| E3 | P3_actividad_vs_base | -0.0170 [-0.0417; +0.0052] | +0.075 | +0.828 | +0.0166 [-0.0232; +0.0707] | +0.73 | no | +0.25 / +0.12 |
| E3 | base_vs_clima | -0.0140 [-0.0369; +0.0082] | +0.116 | +1.000 | -0.0427 [-0.0585; -0.0249] | +0.84 | no | +0.20 / +0.11 |
| E2 | base_vs_clima | -0.0040 [-0.0104; +0.0027] | +0.116 | +1.000 | +0.0128 [+0.0083; +0.0177] | +0.82 | no | +0.20 / +0.11 |
| E1_6 | base_vs_clima | -0.0022 [-0.0066; +0.0014] | +0.132 | +1.000 | -0.0054 [-0.0095; +0.0007] | +0.68 | no | +0.18 / +0.10 |
| E2 | P2_credito_vs_base | -0.0069 [-0.0231; +0.0124] | +0.219 | +1.000 | -0.0118 [-0.0271; +0.0026] | +0.74 | no | +0.13 / +0.08 |
| E3 | P1_curva_tipos_vs_base | -0.0053 [-0.0186; +0.0093] | +0.237 | +1.000 | +0.0222 [+0.0027; +0.0527] | +0.74 | no | +0.12 / +0.08 |
| E1_12 | P1_curva_tipos_vs_base | -0.0065 [-0.0270; +0.0108] | +0.252 | +1.000 | +0.0164 [-0.0280; +0.0535] | +0.61 | no | +0.12 / +0.08 |
| E3 | P2_credito_vs_base | -0.0025 [-0.0154; +0.0126] | +0.367 | +1.000 | +0.0428 [+0.0041; +0.0691] | +0.70 | no | +0.08 / +0.06 |
| E2 | P5_mercados_vs_base | -0.0004 [-0.0048; +0.0055] | +0.440 | +1.000 | -0.0092 [-0.0156; +0.0002] | +0.59 | no | +0.06 / +0.06 |
| E1_12 | P2_credito_vs_base | +0.0059 [-0.0097; +0.0239] | +0.761 | +1.000 | +0.0012 [-0.0176; +0.0314] | +0.52 | no | +0.12 / +0.08 |
| E1_6 | P2_credito_vs_base | +0.0026 [-0.0040; +0.0093] | +0.779 | +1.000 | -0.0031 [-0.0146; +0.0068] | +0.48 | no | +0.13 / +0.08 |

## Δ AUC y Δ Brier frente a la base (V1; descriptivo)

| objetivo | paquete | Δ AUC [IC 95 %] | Δ Brier [IC 95 %] |
|---|---|---|---|
| E1_6 | base_vs_clima | +0.252 [+0.155; +0.346] | +0.00023 [-0.00040; +0.00100] |
| E1_6 | P1_curva_tipos_vs_base | +0.105 [+0.018; +0.187] | -0.00037 [-0.00156; +0.00070] |
| E1_6 | P2_credito_vs_base | -0.022 [-0.103; +0.075] | +0.00039 [-0.00017; +0.00088] |
| E1_6 | P3_actividad_vs_base | +0.197 [+0.111; +0.285] | -0.00261 [-0.00642; -0.00003] |
| E1_6 | P4_precios_vs_base | +0.102 [-0.010; +0.203] | -0.00122 [-0.00297; +0.00013] |
| E1_6 | P5_mercados_vs_base | +0.137 [+0.034; +0.242] | -0.00069 [-0.00255; +0.00080] |
| E1_6 | P6_global_vs_base | +0.175 [+0.092; +0.259] | -0.00266 [-0.00585; -0.00064] |
| E1_6 | combinacion_vs_base | +0.225 [+0.158; +0.301] | -0.00194 [-0.00334; -0.00088] |
| E1_12 | base_vs_clima | +0.255 [+0.158; +0.344] | -0.00143 [-0.00432; +0.00082] |
| E1_12 | P1_curva_tipos_vs_base | +0.079 [+0.002; +0.159] | +0.00011 [-0.00513; +0.00465] |
| E1_12 | P2_credito_vs_base | -0.005 [-0.087; +0.079] | +0.00095 [-0.00160; +0.00325] |
| E1_12 | P3_actividad_vs_base | +0.167 [+0.100; +0.226] | -0.00705 [-0.01508; -0.00123] |
| E1_12 | P4_precios_vs_base | +0.092 [+0.010; +0.170] | -0.00538 [-0.01168; -0.00067] |
| E1_12 | P5_mercados_vs_base | +0.133 [+0.066; +0.213] | -0.00269 [-0.00917; +0.00208] |
| E1_12 | P6_global_vs_base | +0.164 [+0.085; +0.235] | -0.01070 [-0.02134; -0.00374] |
| E1_12 | combinacion_vs_base | +0.194 [+0.140; +0.250] | -0.00788 [-0.01280; -0.00426] |
| E2 | base_vs_clima | +0.178 [+0.114; +0.253] | -0.00100 [-0.00265; +0.00081] |
| E2 | P1_curva_tipos_vs_base | +0.145 [+0.052; +0.222] | -0.00808 [-0.01636; -0.00171] |
| E2 | P2_credito_vs_base | +0.057 [-0.048; +0.161] | -0.00132 [-0.00561; +0.00307] |
| E2 | P3_actividad_vs_base | +0.184 [+0.093; +0.272] | -0.00968 [-0.01855; -0.00283] |
| E2 | P4_precios_vs_base | +0.154 [+0.048; +0.249] | -0.01176 [-0.02796; -0.00205] |
| E2 | P5_mercados_vs_base | +0.025 [-0.024; +0.066] | -0.00024 [-0.00145; +0.00117] |
| E2 | P6_global_vs_base | +0.196 [+0.087; +0.276] | -0.01569 [-0.03266; -0.00384] |
| E2 | combinacion_vs_base | +0.230 [+0.137; +0.309] | -0.01222 [-0.02087; -0.00646] |
| E3 | base_vs_clima | +0.191 [+0.075; +0.291] | -0.00537 [-0.01486; +0.00300] |
| E3 | P1_curva_tipos_vs_base | +0.032 [-0.019; +0.078] | -0.00158 [-0.00783; +0.00496] |
| E3 | P2_credito_vs_base | +0.025 [-0.042; +0.083] | -0.00169 [-0.00623; +0.00339] |
| E3 | P3_actividad_vs_base | +0.071 [+0.003; +0.152] | -0.00603 [-0.01632; +0.00263] |
| E3 | P4_precios_vs_base | +0.097 [+0.027; +0.167] | -0.01202 [-0.02555; -0.00189] |
| E3 | P5_mercados_vs_base | +0.079 [+0.001; +0.160] | -0.00846 [-0.01713; -0.00030] |
| E3 | P6_global_vs_base | +0.144 [+0.051; +0.226] | -0.02206 [-0.03996; -0.00705] |
| E3 | combinacion_vs_base | +0.146 [+0.072; +0.215] | -0.01702 [-0.02514; -0.00996] |

## Importancias (descriptivas; |SHAP| medio, modelo ajustado con todo ≤ 2004)

- **E1_6** — P1_curva_tipos: corto 0.657, tipo_real 0.571; P2_credito: cred_d4 0.421, cred_d20 0.402; P3_actividad: confianza_emp 0.510, d6_confianza 0.461; P4_precios: ipc_yoy 0.531, mp_3m 0.330; P5_mercados: bolsa_real_12m 0.959, caida_24m 0.380; P6_global: dif_curva_inv 0.572, usa_d12_corto 0.440
- **E1_12** — P1_curva_tipos: corto 0.524, tipo_real 0.519; P2_credito: cred_d4 0.437, cred_d20 0.375; P3_actividad: d6_confianza 0.439, confianza_emp 0.437; P4_precios: ipc_yoy 0.617, sub_yoy 0.269; P5_mercados: bolsa_real_12m 1.073, caida_24m 0.152; P6_global: dif_curva_inv 0.574, usa_d12_corto 0.483
- **E2** — P1_curva_tipos: d12_10a 0.403, corto 0.285; P2_credito: cred_d20 0.280, cred_jst_d1 0.257; P3_actividad: confianza_emp 0.676, ip_yoy 0.259; P4_precios: mp_12m 0.422, sub_yoy 0.271; P5_mercados: caida_24m 0.173, bolsa_real_12m 0.107; P6_global: dif_ip_neg 0.340, usa_d12_corto 0.235
- **E3** — P1_curva_tipos: tipo_10a 0.243, curva 0.205; P2_credito: cred_jst_d1 0.272, cred_d20 0.252; P3_actividad: confianza_emp 0.295, d6_confianza 0.272; P4_precios: mp_12m 0.335, mp_3m 0.195; P5_mercados: bolsa_real_12m 0.305, vol_12m 0.258; P6_global: usa_d12_corto 0.439, glob_ipc 0.287

## Candidatos para prerregistro

- E1_12 · combinacion_vs_base: Δlog-loss V1 -0.0445, V2 -0.0191; potencia aproximada en 20 años del bloqueado +0.91 (con la mitad del efecto, +0.44).
- E2 · P3_actividad_vs_base: Δlog-loss V1 -0.0436, V2 -0.0830; potencia aproximada en 20 años del bloqueado +0.74 (con la mitad del efecto, +0.31).
- E3 · P6_global_vs_base: Δlog-loss V1 -0.0564, V2 -0.0371; potencia aproximada en 20 años del bloqueado +0.62 (con la mitad del efecto, +0.25).

_Exploratorio: cualquier hallazgo necesita prerregistro y confirmación en vivo o en el bloqueado._

## Lectura (redactada DESPUÉS de la corrida; no cambia ninguna cifra ni la regla de candidatos)
- **Cómo leer esto:** 32 pruebas en V1 con Holm; V2 (1990-2004) solo filtra. Las cifras de V1 tienen dos sesgos a
  favor: (a) dejar un país fuera no quita las **mismas fechas** de los otros países, así que el paquete global (P6) y
  los rasgos de nivel pueden "aprender el calendario" del ciclo común; (b) los datos ≤ 2004 ya se habían mirado. Por eso
  pesa más lo que se sostiene en V2.
- **Recesión (E1):** el logit de la base (curva y Δ12 del tipo corto) ordena poco (AUC 0,66 en V1). El paquete de
  **actividad** (P3: IP, paro, regla tipo Sahm, confianza empresarial) es el que más aporta y el más estable: AUC V1
  0,86 (6 m) / 0,83 (12 m), y en V2 0,88 / 0,82 frente a 0,73 / 0,66 de la base. Pero a 6 m es casi un **nowcast**
  (el fechado va 2-3 trimestres detrás del pico, INT-8) y Holm no lo rechaza por poco (p Holm 0,08 y 0,05). La
  **combinación** de los 6 paquetes a 12 m es el único candidato en E1 (Δlog-loss −0,045 V1, −0,019 V2; AUC V2 0,82),
  con una advertencia: promediar correcciones las encoge (pendiente de calibración 1,3: probabilidades algo tímidas).
  El paquete global (P6) gana en V1 y **pierde en V2 a 12 m** (+0,022): típico de "aprender el calendario". Crédito
  (P2) no aporta nada en ningún horizonte.
- **Subida de inflación (E2):** el candidato P3 (actividad) mejora la log-loss en V2 sobre todo por **nivel**
  (calibración), no por ordenar mejor: en 1990-2004 su AUC (0,69) es **menor** que la de la base (0,74), cuya
  pendiente de calibración se dispara (10,9) porque la inflación de los 90 se comportó distinto. Precios (P4: materias
  primas) y curva (P1) ayudan en V1 pero no pasan Holm. Solo 59 meses con evento en V2: muy poca información.
- **Subida de tipos (E3):** el candidato P6 (global: Δ tipos de EE. UU. y de los demás) pasa Holm por los pelos (0,049)
  y mejora la log-loss en V2, pero su AUC en V2 (0,55) es **peor** que la base (0,60) y su pendiente de calibración en
  V2 es 0,21: otra vez una corrección de nivel, no de orden. El resto de paquetes no se sostiene en V2.
- **Comparación con INT-4-ML e INT-12:** aquí el XGBoost sí mejora a la base, pero la base es deliberadamente simple
  (2-3 variables); no se ha comparado con un logit que use los mismos paquetes, así que **no** muestra que el boosting
  supere a un lineal con la misma información (esa es la pregunta que INT-4-ML e INT-12 contestaron que no).
- **Importancias:** solo descriptivas; la confianza empresarial domina P3 en E1 y E2, la bolsa real 12 m domina P5 en
  E1 y la difusión de curvas invertidas domina P6 en E1 (coherente con INT-4/INT-8b).
- **Candidatos para un prerregistro futuro (en orden de solidez):** (1) E1-12 con la combinación, o más sencillo y
  más estable, **E1 con el paquete de actividad** (V2 consistente, potencia ≈ 0,6-0,9 en 20 años si el efecto fuese el
  de V1, ≈ 0,25-0,45 con la mitad); (2) E2 y E3 solo si el prerregistro separa la mejora de **nivel** (calibración) de
  la de **orden** (AUC), porque aquí la primera es la única que se sostiene. La pregunta confirmatoria natural sería
  "logit con actividad frente a logit con curva", no "XGBoost frente a logit".
- **Declaraciones:** una sola corrida (commit 3bfd43a, árbol limpio, 2026-10-30T14:16Z, 75 s). El plan decía "Φ(Δ̄/dt)"
  para el p de AUC; el código usa 1 − Φ(Δ̄/dt) (p de mejora, como en la log-loss): es un error de redacción del plan,
  solo afecta a un descriptivo que no se publica en la tabla. El clima tiene AUC < 0,5 y pendiente negativa en V1 por
  construcción (una constante distinta por país dejado fuera): no significa nada. Nada ≥ 2005.

_Exploratorio: cualquier hallazgo necesita prerregistro y confirmación en vivo o en el bloqueado._
