---
documento: resultados de desarrollo (≤ 2004) de M1 y del clasificador de reglas (Fase 3, entregable 4)
fecha: 2026-10-16
especificacion: docs/models/m1_spec.md (commit bf7049d, previo a cualquier corrida con la etiqueta; post hoc técnicos en §9)
codigo_corridas: commit 1f9c52b (worktree limpio, git_dirty false; núcleo del arnés = v2, e58a054)
corridas: 20261016-141709_m1_logit_axis_v1_3f435b7b (principal), 20261016-141648_m1_logit_axis_v1_long_0e55b60b (larga),
  20261016-141837_m1_logit_axis_v1_sens_b46bc3ca, 20261016-141842_m1_logit_axis_v1_long_sens_e83a438f,
  20261016-141826_m1_logit_axis_v1_w_uno_9250a8c0, 20261016-141825_m1_logit_axis_v1_w_excluir_ef4e6296
derivados: research/trials/m1_v1/{placebo_m1_v1.json, epocas_report.json, coef_*.json}
datos: solo ≤ 2004-12. Nada ≥ 2005 leído.
---

# M1 y reglas frente a M0: desarrollo ≤ 2004

**Resumen.** M1 **no bate a M0** de forma distinguible en desarrollo.
- En la ventana principal (1989-10 → 2004-12, M1 con IPC subyacente) M1 queda **por debajo** de M0: −0,019 nats
  [−0,128; +0,076].
- En la ventana larga (1975-06 → 2004-12, eje I con IPC general) M1-general mejora a M0 en **+0,046** [−0,016; +0,103].
  Toda la mejora viene del eje G y de los meses **estables**, no de los giros.
- **Ninguna alarma de fuga:** el placebo está limpio y ninguna mejora se acerca a 0,25 nats.
- Dos problemas que importan para P-EVAL-BASE:
  1. **El coeficiente de `unrate_sahm` tiene el signo contrario al preregistrado en todos los cortes** (+0,18 a +0,34).
  2. **El eje I con el subyacente empeora a M0** (−0,032 nats en I).
- Las reglas calibradas quedan muy por debajo de M0 (−0,57 a −0,85 nats). Fallan en I, como avisó el Estratega.

## 1. Placebo (antes de la etiqueta real; `placebo_m1_v1.json`)

Δ = ll(M0) − ll(M1) con la etiqueta barajada en bloques de 24 meses, 20 semillas, la L2 de M1 (m1_spec.md §5).

| caso | media Δ | semillas > 0 | t | ¿fuga (> 0,02)? | ¿aviso (signo p < 0,01 o t > 3)? |
|---|---|---|---|---|---|
| **M1 (subyacente), 1989-2004** | **−0,036** | 2 / 20 | −5,0 | no | no |
| **M1-general, 1976-2004** | **−0,029** | 2 / 20 | −6,1 | no | no |
| potencia: ruido | −0,005 | 0 / 20 | −7,5 | no | no |
| potencia: control t−5 (sin fuga) | −0,023 | 0 / 20 | −8,8 | no | no |
| potencia: t+1, σ = 1 | +0,042 | 20 / 20 | 13,8 | **sí** | **sí** |
| potencia: t+1, σ = 2 | +0,006 | 16 / 20 | 4,1 | no | **sí** |
| potencia: t, σ = 2 | +0,008 | 16 / 20 | 4,9 | no | **sí** |
| potencia: calendario t−4 | +0,019 | 19 / 20 | 6,6 | **no** | **sí** |

**Lectura:**
- El placebo de M1 está limpio, con el sesgo negativo esperable de una L2 que no anula variables sin señal.
- La regla complementaria del Validador es **necesaria** con esta L2. Con la L2 de M1, la regla de 0,02 **no**
  detecta la fuga de calendario de un mes (+0,019); la regla de signo o t sí la detecta, y también las de σ = 2. Es
  específica: ni el ruido ni el control dan aviso.

## 2. Corrida principal: 1989-10 → 2004-12 (183 meses)

| modo | modelo | acierto | log-loss 4 c. | G | I |
|---|---|---|---|---|---|
| vintage | M0 | 67,2 % | **0,948** | 0,586 | 0,362 |
| vintage | **M1** (subyacente) | 65,6 % | 0,966 | **0,572** | 0,394 |
| vintage | M1-general | 65,6 % | **0,932** | 0,572 | **0,360** |
| vintage | reglas (épocas) | 31,1 % | 1,790 | 0,656 | 1,122 |
| vintage | persistencia cruda | 62,8 % | 1,250 | 0,740 | 0,500 |
| latest_truncated | M0 | 62,8 % | 0,930 | 0,563 | 0,367 |
| latest_truncated | M1 | 63,9 % | 0,943 | 0,566 | 0,376 |
| latest_truncated | M1-general | 62,8 % | 0,934 | 0,566 | 0,367 |

Diferencias frente a M0 (positivo = mejor que M0; IC 95 % por bloques de 12 meses; los de 24 meses son casi iguales):

| | M1 vintage | M1 latest_tr. | M1-general vintage | reglas vintage |
|---|---|---|---|---|
| total | **−0,019** [−0,128; +0,076] | −0,013 [−0,129; +0,083] | +0,015 [−0,062; +0,087] | −0,843 [−1,109; −0,567] |
| eje G | +0,013 [−0,065; +0,086] | −0,003 | +0,013 | −0,071 |
| eje I | **−0,032** [−0,083; +0,006] | −0,010 | +0,002 | −0,760 |
| giro / estable | −0,160 / +0,023 | −0,199 / +0,043 | +0,003 / +0,019 | −0,640 / −0,903 |
| 1989-10→1996 / 1997→2004 | −0,120 / +0,074 (signo distinto) | −0,117 / +0,081 | −0,056 / +0,080 | −0,73 / −0,95 |
| frontera / no frontera | −0,282 / +0,007 | −0,303 / +0,015 | −0,072 / +0,024 | |
| episodios ganados: NBER ± 6 / rachas / giros G | 2 de 2 / 4 de 9 / 3 de 7 | 2 / 5 / 3 | 1 / 6 / 4 | 0 / 0 / 0 |

Holm frente a M0: p ajustada 1,0 para todos.

## 3. Ventana larga: 1975-06 → 2004-12 (355 meses)

| modo | modelo | acierto | log-loss 4 c. | G | I |
|---|---|---|---|---|---|
| vintage | M0 | 67,9 % | 0,818 | 0,604 | 0,214 |
| vintage | **M1-general** | **72,4 %** | **0,772** | **0,561** | 0,211 |
| vintage | M1 por épocas (general → subyacente en 1989-10) | 72,4 % | 0,789 | 0,561 | 0,229 |
| vintage | reglas (IPC general) | 38,9 % | 1,386 | 0,649 | 0,723 |
| vintage | climatología | 29,6 % | 1,389 | 0,693 | 0,688 |
| latest_truncated | M0 / M1-general | 67,6 % / 72,7 % | 0,795 / 0,758 | 0,577 / 0,542 | 0,218 / 0,216 |

| frente a M0 | M1-general vintage | M1-general latest_tr. | M1 por épocas vintage | reglas vintage |
|---|---|---|---|---|
| total | **+0,046** [−0,016; +0,103] (frac ≤ 0: 0,074) | +0,037 [−0,021; +0,090] | +0,029 [−0,046; +0,095] | −0,568 [−0,786; −0,368] |
| eje G | **+0,043** [−0,019; +0,099] | +0,035 | +0,043 | −0,045 |
| eje I | +0,003 [−0,001; +0,008] | +0,002 | −0,015 | −0,509 |
| giro | **−0,021** [−0,112; +0,072] | −0,006 | −0,097 | −0,364 |
| estable | **+0,069** [+0,008; +0,125] | +0,051 | +0,072 | −0,638 |
| 1975-06→1979 / 1980→2004 | +0,170 / +0,024 | +0,175 / +0,011 | +0,170 / +0,003 | |
| 1975-89 / 1990-2004 | +0,079 / +0,015 (mismo signo) | +0,078 / −0,004 | +0,079 / −0,020 | |
| frontera / no frontera | −0,084 / +0,055 | −0,106 / +0,046 | −0,230 / +0,047 | |
| episodios: NBER ± 6 / rachas / giros G | 3 de 4 / 12 de 17 / 10 de 16 | 3 / 11 / 9 | 4 / 10 / 9 | 0 / 1 / 3 |

Holm vintage: M1-general 0,24; M1 por épocas 0,30 (ninguno significativo).

## 4. Detección de giros de G y falsas alarmas (definición v2; provisional, Validador M2-3)

| ventana, vintage | M0 | M1 / M1-general | reglas |
|---|---|---|---|
| larga (16 giros): retraso medio, detectados | 3,81 m, 15 | **2,75 m**, 13 | 2,94 m, 15 |
| larga: falsas alarmas al año | **0,30** | 0,55 | 1,44 |
| principal (7 giros): retraso, detectados | 2,14 m, 7 | 3,29 m, 5 | 2,14 m, 7 |
| principal: falsas alarmas al año | 0,19 | 0,56 | 1,22 |

**Lectura:**
- En la ventana larga M1 confirma los giros ~1 mes antes, pero **detecta menos** (13 de 16) y **duplica las falsas
  alarmas** (0,55 al año, por encima del listón del Estratega de ≤ 0,5).
- En la ventana principal empeora en los dos.
- Con la definición v2 los giros no detectados entran en la media de forma distinta (M2-3). Hay que recalcular con la
  v2.1 sobre las mismas predicciones antes de sacar conclusiones.

## 5. Calibración y dependencia entre ejes

- Correlación de residuos G-I:
  - M1: 0,095 (vintage, ventana principal);
  - M1-general: 0,005 (principal) / 0,036 (larga);
  - todas por debajo del umbral de 0,2;
  - las reglas dan −0,26 en la ventana principal (no aplica: no es un modelo producto).
- La calibración por tramos de cada modelo está en los `report.json` (`calibracion`). No se ajusta nada.

## 6. Coeficientes (estandarizados; `coef_*.json`)

| coeficiente | signo preregistrado | M1-general vintage, 355 cortes: media [mín; máx] | cortes con el signo preregistrado |
|---|---|---|---|
| G: logit persistencia | + | +0,18 [+0,14; +0,33] | 100 % |
| G: `growth_rt` | + | +0,66 [+0,35; +0,79] | 100 % |
| G: **`unrate_sahm`** | **−** | **+0,18 [−0,09; +0,28]** | **1,7 %** (0 % en latest_truncated y en M1 subyacente) |
| G: `baa_spread` | − | −0,24 [−0,38; −0,10] | 100 % |
| G: `eq_ret_6m` | + | +0,35 [+0,27; +0,50] | 100 % |
| G: `curve_10y3m` | + (débil) | +0,54 [+0,35; +0,69] | 100 % |
| I: logit persistencia | + | +0,47 [+0,31; +0,51] | 100 % |
| I: `headline_cpi_6m_ann` | + | +0,40 [+0,33; +0,64] | 100 % |
| I: `core_cpi_6m_ann` (M1, 192 cortes) | + | +0,17 [+0,05; +0,29] | 100 % |

**Estabilidad a los dos lados de los saltos de vintage.** Mismo signo en todos los saltos con ≥ 12 cortes a cada lado:
- `growth_rt` en 1981-05: +0,50 → +0,70;
- `core_cpi_6m_ann` en 1996-12: +0,11 → +0,23.

**Lectura del signo de Sahm.**
- Condicionado a `growth_rt` (que ya recoge el deterioro del empleo y la producción) y a la persistencia, la Sahm
  entra con signo positivo. Es una colinealidad o un efecto de "rebote": la Sahm sigue alta en la salida de la
  recesión, cuando la etiqueta ya ha vuelto a G alto.
- No se corrige (sería iterar con resultados). Con el criterio 5 del borrador de P-EVAL-BASE (signos iguales a los
  preregistrados), **M1 tal como está fallaría ese criterio**. Es una decisión para el usuario y el Estratega (§9).

## 7. Sensibilidades preregistradas (vintage; no eligen)

| corrida | M1 − M0 total | G | I |
|---|---|---|---|
| L2 = 2 (principal) | −0,027 [−0,153; +0,083] | +0,001 | −0,028 |
| **L2 = 6 (a priori, principal)** | **−0,019** | +0,013 | −0,032 |
| L2 = 18 (principal) | −0,011 [−0,101; +0,064] | +0,023 | −0,034 |
| L2 = 2 (larga, general) | +0,042 [−0,034; +0,110] | +0,038 | +0,004 |
| **L2 = 6 (larga, general)** | **+0,046** | +0,043 | +0,003 |
| L2 = 18 (larga, general) | +0,044 [−0,002; +0,087] | +0,042 | +0,002 |
| provisionales "uno" (principal) | −0,018 [−0,126; +0,076] | +0,013 | −0,031 |
| provisionales "excluir" (principal; muestra reducida a 146 m, desde 1992-11) | **−0,409** [−0,773; −0,093] | +0,042 | **−0,451** |

**Lectura:**
- La L2 apenas importa: ±0,01 nats dentro de un factor 9.
- "Excluir" **rompe el eje I con el subyacente**: log-loss de I 0,86 frente a 0,41 de M0. Sin los 54 meses
  provisionales, la ventana desde 1978 tiene muy pocos cruces de κ. Confirma el problema de identificación que
  anticipó el Estratega (revisión del arnés §3d).

## 8. Diagnóstico

1. **Fuga:** no hay indicios.
   - El placebo está limpio.
   - Las mejoras son pequeñas (≤ 0,05 nats, lejos de 0,25).
   - Los coeficientes son estables y económicamente razonables salvo la Sahm.
   - Las predicciones de M0 y de la persistencia cruda son **idénticas bit a bit** a las de la corrida oficial de los
     baselines v2 (`20261016-132138_baselines_v2_1a6d6df8`) en los meses comunes (924 y 1.158 filas; diferencia
     máxima 0). La log-loss de M0 cambia (0,818 frente a 0,811) solo porque la ventana empieza en 1975-06 en vez de en
     1975-01.
2. **El valor de las variables está en G.**
   - Es pequeño (+0,04 nats en 1975-2004, IC que toca el 0).
   - Se concentra en los meses estables: M1 está más seguro cuando el ciclo no cambia.
   - No mejora los giros, que es justo donde estaba el margen (Estratega: ≥ 0,25 nats en giros). Las variables
     actuales no adelantan los giros más que la persistencia calibrada.
3. **El eje I con el subyacente es el punto débil de M1.**
   - En 1989-2004 empeora a M0 en I (−0,032). En cambio, el IPC general, con 30 años más de entrenamiento y muchos
     más cruces, no empeora.
   - Para el periodo bloqueado, la ventana del subyacente será 1978 → T (27+ años, con cruces en 1991-94 y 2001-03),
     así que el problema debería atenuarse, pero no está demostrado.
4. **Reglas:**
   - en G son algo mejores que la climatología (0,649 frente a 0,693) y peores que M0;
   - en I son peores que la climatología (0,72 frente a 0,69), por la aceleración frente al nivel;
   - sus falsas alarmas (1,2-1,4 al año) las descartan como señal de cartera.
   - No aportan nada sobre M0.

## 9. Decisiones para el usuario (no tomadas aquí)

1. **Signo de la Sahm:** ¿mantener M1 tal como está (y aceptar que el criterio 5 de P-EVAL-BASE probablemente
   falle), o preregistrar una **M1 v2** sin `unrate_sahm`, o con Sahm solo como umbral (≥ 0,5)? Cualquiera de las
   dos alternativas es una especificación nueva, contaminada por este resultado de desarrollo, y debe anotarse así.
2. **Eje I para P-EVAL-BASE:** ¿subyacente (lo preregistrado; peor en desarrollo, mal identificado con "excluir") o
   general? ¿O el eje I "casi estructural" del Estratega? Ojo: elegir el general **después** de ver esta tabla es
   selección con datos de desarrollo y cuenta como prueba.
3. **¿Merece M1 la evaluación única?** En desarrollo no cumple los criterios 1 (≥ 0,05 nats con IC > 0), 3 (giros
   > 0) ni 5 (signos) del borrador de P-EVAL-BASE, y empeora las falsas alarmas. Gastar el bloqueado en esta versión
   probablemente produzca un "no" informativo pero caro.

## Anexo A (2026-10-24). Por qué M1 v1 ya no reproduce su `results_sha256`

**Síntoma** (Bitácora del 23-oct): al repetir `m1_logit_axis_v1` y `m1_logit_axis_v1_long` (`record=False`) el
`results_sha256` no coincide con el registrado (`3f435b7b…`, `0e55b60b…`), ni en el HEAD de hoy ni en el anterior al
23-oct. Las corridas de los baselines v2.1 y de M1 v2 sí se reproducen bit a bit.

**Causa: un cambio de código del arnés, no de datos ni de dependencias.** Las dos corridas se registraron con el código
de `1f9c52b` (16-oct 14:14; `src_models` = `5ad07fef…`, que es el hash de los `.py` de `src/models` en ese commit). Un
minuto después llegó `2fd94e0` (harness v2.1: **detección de giros v2.1**, episodios truncados, límites reales de los
periodos), que cambia el **informe**. El hash es de predicciones **+ informe** (`harness.results_hash`), así que cambia
aunque las predicciones sean idénticas. Los baselines v2.1 se registraron ya con `2fd94e0` (`8d55f1f6…`), por eso esos sí
se reproducen.

**Comprobación** (una pasada, `record=False`, registros en el scratchpad con `FKB_TRIALS_DIR`/`FKB_TRIAL_LOG`;
`research/trials/harness_runs.jsonl` intacto; worktrees temporales de git; mismos ficheros de datos, mismas versiones de
Python/numpy/pandas/scipy/pyarrow que en el registro):

| árbol | `src_models` | `results_sha256` (principal) | predicciones frente a las registradas | informe |
|---|---|---|---|---|
| `1f9c52b` (el del registro) | `5ad07fef…` | **`3f435b7b…` = registrado** | idénticas (dif. máx. 0) | idéntico |
| `2fd94e0` (harness v2.1) | `8d55f1f6…` | `1371fc71…` | idénticas (dif. máx. 0) | 396 diferencias |
| HEAD `d5b1e00` (24-oct) | `20500ac2…` | `1371fc71…` (= `2fd94e0`) | idénticas (dif. máx. 0) | las mismas 396 |

Ventana larga en el HEAD: predicciones idénticas (dif. máx. 0), 330 diferencias de informe, todas del mismo tipo. Entre
`2fd94e0` y el HEAD el hash de M1 v1 no cambia (el resto de commits no toca su resultado). No hace falta `git bisect`:
el único commit entre el del registro y el que ya da el hash nuevo es `2fd94e0`.

**Qué cambia en el informe** (todas las diferencias, clasificadas): solo `deteccion_giros_g` (número de giros,
detectados, censurados, retraso medio), `por_episodio` (episodios truncados, recuentos, prueba del signo por episodios),
`deteccion_frente_al_comparador` (nuevo), `retraso_medio_menos_comparador` (sustituido) y `desde_real`/`hasta_real` de los
periodos. **Ninguna** diferencia en log-loss (total, ejes, giros/estables, por periodo, por década), Brier, IC, `p_h0`,
Holm, calibración, cobertura ni falsas alarmas por año.

**¿Afecta a las conclusiones?** **No.** "M1 v1 no bate a M0" se apoya en la log-loss (−0,019 nats en la principal; IC con
0), que no cambia ni un bit, igual que las predicciones. Lo único que cambia es la tabla del §4 (definición v2 de la
detección, que ya estaba marcada como provisional). Con la detección v2.1 sobre las **mismas** predicciones (vintage):

| ventana | M0: giros, detectados, retraso, FA/año | M1 v1: detectados, retraso, FA/año | reglas: detectados, retraso, FA/año |
|---|---|---|---|
| principal 1989-10 → 2004 (5 giros, 0 censurados) | 5, 5, 4,4 m, 0,19 | 5, **2,4 m**, 0,56 | 5, 5,0 m, 1,22 |
| larga 1975-06 → 2004 (11 giros, 1 censurado) | 11, 10, 4,6 m, 0,30 | 10, **3,0 m**, 0,55 | 11, 5,0 m, 1,44 |

Lectura: con la v2.1 M1 v1 confirma los giros antes que M0 en las dos ventanas (en la v2 salía peor en la principal),
pero sigue con ≈ 0,55 falsas alarmas al año (por encima del listón de 0,5): la conclusión del §8-§9 se mantiene. Son
las cifras que ya usaba `m1_v2_results_dev.md` para M1 v1 (FA 0,56).

**Consecuencia práctica:** el `results_sha256` registrado de M1 v1 sigue siendo válido **para el código de `1f9c52b`**, y
se reproduce con él. Cualquier comparación futura con M1 v1 en el código actual debe usar las predicciones (idénticas) o
el hash nuevo (`1371fc71…` principal, `50092aac…` larga), anotándolo. No se registra ninguna corrida nueva.
