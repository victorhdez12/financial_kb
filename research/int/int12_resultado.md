---
documento: Resultado P-DEV-INT12 v1.0 (corrida única de desarrollo del modelo de riesgo de mercado)
prerregistro: docs/int/INT12_prerregistro_v1.md (cba3c5e)
procedencia: {'commit': 'dec66c13e49b2e11f66da10899b28fac7bfba515', 'arbol_limpio': True, 'hora_utc': '2026-10-30T13:17:13+00:00'}
datos: EE. UU. diario 1926-2004 (AQR/CRSP), evaluación 1950-01 … 2004-11 (1 m). NADA ≥ 2005
---

# INT-12: resultado de la corrida de desarrollo

## Contrastes confirmatorios (QLIKE, 1 mes, N = 659; Holm-3; signo en las dos mitades)
| contraste | ganancia QLIKE | 1950-77 | 1977-2004 | t (NW, 6 retardos) | p | p Holm | p bootstrap | veredicto |
|---|---|---|---|---|---|---|---|---|
| C1 HAR frente a σ̂ 12 m (B1) | 34,3 % | 43,3 % | 23,8 % | 4.38 | 0.0000 | 0.0000 | 0.0005 | **establecido** |
| C2 HAR-X frente a HAR | -4,7 % | -4,8 % | -4,6 % | -1.73 | 0.9584 | 1.0000 | 0.9560 | **no establecido** |
| C3 GB frente a HAR-X | -22,1 % | -13,3 % | -29,7 % | -1.91 | 0.9722 | 1.0000 | 0.9525 | **no establecido** |

## QLIKE medio por modelo (menos es mejor)
| modelo | 1 m | 3 m |
|---|---|---|
| b1_12m | 0.4176 | 0.3484 |
| ewma | 0.3109 | 0.3517 |
| har | 0.2742 | 0.2455 |
| harx | 0.2870 | 0.2717 |
| gb | 0.3504 | 0.3656 |
| mlp | 0.3342 | 0.2911 |

## Descriptivos a 3 meses (mismos contrastes, no deciden)
| contraste | ganancia | t | p |
|---|---|---|---|
| C1 HAR frente a σ̂ 12 m (B1) | 29,5 % | 2.59 | 0.0048 |
| C2 HAR-X frente a HAR | -10,7 % | -2.15 | 0.9841 |
| C3 GB frente a HAR-X | -34,5 % | -2.86 | 0.9979 |
| D_ewma_vs_har (1 m) | 11,8 % | 2.36 | 0.0091 |
| D_mlp_vs_harx (1 m) | -16,4 % | -1.20 | 0.8848 |
| D_gb_vs_har (1 m) | -27,8 % | -2.01 | 0.9779 |
| D_harx_vs_b1 (1 m) | 31,3 % | 3.75 | 0.0001 |

## Colas (descriptivo): VaR 5 % (Kupiec), FZ0, P(caída ≥ 10 % en 3 m)
| modelo | excedencias VaR 1 m (tasa, p Kupiec) | FZ0 1 m | excedencias VaR 3 m | Brier caída 3 m |
|---|---|---|---|---|
| b1_12m | 37 (5,6 %, 0.477) | -2.3192 | 39 (5,9 %) | 0.1067 |
| ewma | 35 (5,3 %, 0.717) | -2.3993 | 33 (5,0 %) | 0.1044 |
| har | 36 (5,5 %, 0.591) | -2.4342 | 38 (5,8 %) | 0.1043 |
| harx | 41 (6,2 %, 0.165) | -2.4143 | 44 (6,7 %) | 0.1055 |
| gb | 46 (7,0 %, 0.027) | -2.3684 | 55 (8,4 %) | 0.1140 |
| mlp | 33 (5,0 %, 0.993) | -2.4355 | 36 (5,5 %) | 0.1043 |

Orígenes con caída ≥ 10 % en 3 m en la evaluación: 80.

## QLIKE por década (1 m)
| década | B1-12m | HAR | HAR-X | GB |
|---|---|---|---|---|
| 1950s | 0.435 | 0.286 | 0.284 | 0.329 |
| 1960s | 0.500 | 0.315 | 0.316 | 0.370 |
| 1970s | 0.363 | 0.151 | 0.181 | 0.180 |
| 1980s | 0.483 | 0.466 | 0.497 | 0.675 |
| 1990s | 0.352 | 0.200 | 0.198 | 0.231 |
| 2000s | 0.326 | 0.179 | 0.202 | 0.283 |

Importancia por permutación de GB (último ajuste, dentro de muestra, descriptiva): {'lrv5': 0.141, 'lrv21': 0.1442, 'lrv63': 0.1958, 'credito': 0.0613, 'curva': 0.0722, 'corto': 0.0773, 'reg_infl': 0.0138, 'reg_brecha': 0.0002}
Coeficientes HAR-X del último ajuste (constante, lrv5, lrv21, lrv63, credito, curva, corto, reg_infl, reg_brecha): [-3.3072, 0.1233, 0.2771, 0.2838, 0.1737, -0.0157, 0.0094, -0.0542, 0.0601]

## Lectura (redactada después de la corrida; no cambia ningún veredicto)
- **C1 establecido:** prever la volatilidad del mes siguiente con datos **diarios** (HAR) en vez de con los 12 últimos
  rendimientos mensuales (la σ̂ de B1) reduce el QLIKE un **34 %** (43 % en 1950-77, 24 % en 1977-2004; p bootstrap
  0,0005). La fase 1 lo anticipaba (≈ 48 % en simulación). Es un resultado conocido: aquí queda confirmado en nuestra medida.
  El EWMA también bate a la σ̂ de 12 meses, y el HAR bate al EWMA (11,8 %, descriptivo).
- **C2 no establecido, y con el signo contrario:** añadir crédito (BAA − AAA), curva, tipo corto y régimen macro
  **empeora** la previsión fuera de muestra (−4,7 % a 1 mes, −10,7 % a 3 meses, en las dos mitades). Con los datos ≤ 2004
  y estos rasgos, la información macro-financiera **no añade nada** a la propia historia de la volatilidad; los niveles de
  tipos y diferenciales cambian de escala entre décadas (lo peor, los años 80) y el modelo los extrapola mal.
- **C3 no establecido:** el boosting con hiperparámetros fijados es **un 22 % peor** que el lineal con la misma
  información (y la red pequeña, descriptiva, un 16 %). Con 190-850 meses de entreno y un objetivo muy ruidoso (RV de
  datos diarios), la capacidad extra sobreajusta. Su VaR también sale mal calibrado (7 % de excedencias, Kupiec p 0,03).
- **Colas (descriptivo):** HAR, EWMA y la red dan coberturas del VaR 5 % correctas (5,0-5,5 %); las diferencias en FZ0 y
  en el Brier de la caída ≥ 10 % son mínimas, como predijo la potencia (80 orígenes con caída, ≈ 25 episodios).
- **Consecuencias decididas de antemano (prerregistro §7):** (a) B1′ cumple su condición de apertura (C1 establecido);
  falta la aprobación del usuario para pasar a código (`docs/factors/B1prima_spec.md`). (b) El modelo operativo de
  volatilidad es el **HAR lineal sin rasgos X**; el ML queda descriptivo. (c) Para INT-11 §5.1 el ancla de largo plazo es
  la media del propio HAR, no la del régimen (C2 no establecido); y solo si INT-11 v2 pasa su puerta de calibración.
- **Declaraciones:** antes de la corrida, y solo tras la comprobación con `--sintetico`, se añadieron dos detalles de
  implementación (commit dec66c1): el objetivo del MLP se centra (sin centrar no convergía) y los ajustes se hacen con
  un hilo de OpenMP/BLAS (solo velocidad). Ningún dato ≥ 2005. Una sola corrida.
