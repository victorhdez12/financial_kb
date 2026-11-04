---
documento: HPO-INT12 — ajuste de hiperparámetros EXPLORATORIO del ML de volatilidad de INT-12
version: 1.0 (2026-11-04). §1-§3 (espacio, presupuesto, reglas) escritos y commiteados ANTES de correr, junto con
         el código (scripts/hpo_int12.py). §4-§6 se redactan después de la corrida única.
parte_de: INT-12 (docs/int/INT12_prerregistro_v1.md; resultado research/int/int12_resultado.md, congelado, no se toca)
datos: SOLO ≤ 2004-12-31 (los de P-DEV-INT12 vía scripts/int12_corrida.cargar_real). El periodo ≥ 2005 está BLOQUEADO
naturaleza: EXPLORATORIO. No cambia ningún veredicto de INT-12. Si algo destaca, solo produce una configuración a
            PRERREGISTRAR para una confirmación futura (que aquí NO se corre)
---

# HPO-INT12: ¿con hiperparámetros ajustados, el boosting bate al HAR?

## 0. Pregunta y contexto
INT-12 estableció que el HAR (datos diarios) reduce el QLIKE un 34 % frente a la σ̂ de 12 meses de B1, y que ni los
rasgos macro-financieros (C2) ni el boosting con hiperparámetros fijados (C3, −22 % frente a HAR-X; −28 % frente a HAR)
mejoran. La fase 1 (potencia) dio al ML una ventaja realista de ≈ 2-5 % frente al HAR. Objeción natural: "el GB salió
mal porque sus hiperparámetros eran malos". Aquí se busca la mejor configuración **sin inflar la cifra por la búsqueda**.

## 1. Espacio de búsqueda (HistGradientBoostingRegressor, sklearn 1.5.2, loss = squared_error, sin early stopping)
| hiperparámetro | rango | muestreo |
|---|---|---|
| `rasgos` | {HAR (lrv5, lrv21, lrv63), HAR + X (las 5 de INT-12)} | uniforme |
| `modo` | {directo: GB sobre log(RV/n); residuo: HAR lineal (MCO) + GB sobre su residuo} | uniforme |
| `learning_rate` | [0,005; 0,2] | log-uniforme |
| `max_iter` | [20; 500] | log-uniforme, entero |
| `max_depth` | {1, …, 5} | uniforme |
| `min_samples_leaf` | [5; 200] | log-uniforme, entero |
| `l2_regularization` | [0,001; 100] | log-uniforme |
| `max_features` | [0,3; 1] | uniforme |

Objetivo y previsión como en INT-12: log(RV/n_días), previsión = n_días · exp(ajuste) · Duan (media de exp(residuo) del
entreno). `random_state` = 20261104. El modo "residuo" encoge hacia el HAR (si el GB no aprende nada, queda el HAR).

## 2. Presupuesto (fijo, declarado antes)
- **Búsqueda aleatoria** (optuna no está instalado; no se instala nada): **60 configuraciones**; la nº 0 es exactamente
  el GB de INT-12 (HAR + X, directo, lr 0,05, 300 iter., prof. 3, hoja 20, L2 1, todas las variables); las 1-59 se
  sortean con `numpy.random.default_rng(20261104)`. Las mismas 60 en todos los bloques y en todas las réplicas placebo.
- **Placebo:** R = 50 réplicas. Total ≈ 51 × 11 bloques × 60 configuraciones × 5 pliegues ≈ 170.000 ajustes.
- Se registran TODAS las pruebas: `pruebas_internas.csv` (bloque × configuración: QLIKE interno y su ganancia frente al
  HAR interno), `pruebas_externas_todas.csv` (las 60 configuraciones evaluadas fuera de muestra en 1950-2004, solo
  descriptivo: NO se usa para elegir; muestra la dispersión y lo que daría un "oráculo"), `placebo.csv`.

## 3. Reglas (validación anidada walk-forward con embargo)
- **Bucle externo (evalúa):** orígenes 1950-01 … 2004-11 (N = 659, como INT-12), ventana creciente desde 1934-02,
  embargo (solo filas cuyo objetivo acaba ≤ origen de la re-estimación) y re-estimación cada enero, igual que INT-12.
  La configuración se elige al inicio de cada **bloque de 5 años** (1950, 1955, …, 2000; 11 selecciones) y se mantiene
  durante el bloque (re-estimando cada enero con ella).
- **Bucle interno (elige):** para el bloque que empieza en enero de B, validación walk-forward sobre los orígenes
  (B − 10)-01 … (B − 1)-12, en 5 pliegues de 2 años; cada pliegue re-estima con las filas de 1934-02 en adelante cuyo
  objetivo acaba ≤ origen del primer mes del pliegue. Todo objetivo interno acaba ≤ origen de enero de B (comprobado
  con `assert`): el bucle interno no ve nada de lo que evalúa el externo. Se elige la configuración con menor QLIKE
  medio interno (los 120 meses agregados).
- **Listón y métrica:** HAR de INT-12 (MCO + Duan, mismo calendario), QLIKE a 1 mes. ganancia = 1 − QLIKE(HPO)/QLIKE(HAR).
- **Contraste:** DM unilateral con varianza Newey-West (6 retardos, como INT-12) e **IC 95 % por bootstrap de bloques
  estacionario** (bloque medio 12, 2.000 réplicas, semilla 20261104) de la ganancia y de la diferencia media; ganancia
  por mitades (1950-77 / 1977-2004).
- **Placebo:** (rv, n_días) barajados por bloques contiguos de 12 meses en toda la tabla (semilla 20261104 + r); rasgos
  intactos; se repite el procedimiento anidado ENTERO (elección incluida) y se mide la ganancia externa HPO frente a
  HAR. Es la nula de "cuánto gana la búsqueda por azar". p_placebo = (1 + #{placebo ≥ real}) / (R + 1).
- **"Destaca de verdad"** (criterio fijado antes): ganancia externa > 0 **y** IC 95 % bootstrap con extremo inferior
  > 0 **y** ganancia > percentil 95 del placebo **y** ganancia > 0 en las dos mitades. Solo entonces se propone una
  configuración a prerregistrar.
- **Una sola corrida** con procedencia (árbol limpio; `src/intl/procedencia.py`); el script se niega si la salida
  (`research/int/hpo_int12/`) existe. Nada ≥ 2005.

## 4. Resultado (corrida única; procedencia commit 28339b6, árbol limpio, 2026-11-04T14:06:44Z; 292 s + 1.995 s de placebo)
Salida: `research/int/hpo_int12/` (`resultado.json`, `resumen.txt`, `pruebas_internas.csv` (660 = 11 × 60),
`pruebas_externas_todas.csv` (60), `placebo.csv` (50), `previsiones.csv`). Comprobación: el HAR reproduce el QLIKE de
INT-12 (0,2742).

### 4.1 Principal: HPO-GB anidado frente a HAR (QLIKE, 1 mes, N = 659)
| | valor |
|---|---|
| QLIKE HAR / HPO-GB | 0,2742 / 0,3346 |
| **ganancia anidada** | **−22,0 %** |
| IC 95 % bootstrap de bloques (ganancia) | **[−40,7 %; −2,4 %]** (entero por debajo de 0) |
| IC 95 % bootstrap de la diferencia media d | [−0,152; −0,005] |
| DM-NW (6 retardos) | t = −1,48, p unilateral = 0,93 (p bootstrap 0,92) |
| por mitades (1950-77 / 1977-2004) | −0,0 % / −41,1 % |
| ganancia **interna** media del elegido (lo que "prometía" la búsqueda) | +7,0 % |

Selección por bloque (configuración, ganancia interna frente a HAR): 1950 #11 (+16,7 %), 1955 #34 (+11,6 %), 1960 #55
(+11,4 %), 1965 #31 (+2,6 %), 1970 #25 (+4,4 %), 1975 #54 (+6,9 %), 1980 #3 (+9,5 %), 1985 #40 (+8,4 %), 1990 #33
(+1,8 %), 1995 #22 (+2,7 %), 2000 #10 (+1,2 %). La elección **salta de configuración en cada bloque** (11 distintas de
60; ambos modos, ambos conjuntos de rasgos, profundidad 1-5): no hay un óptimo estable, señal de que se elige ruido.

### 4.2 Placebo (R = 50, objetivo barajado por bloques de 12 meses, procedimiento anidado entero)
- Ganancia externa placebo: media −7,8 %, mediana −7,8 %, p95 +2,3 %, máx. +4,0 %.
- Ganancia **interna** del elegido en el placebo: media +11,8 % (p95 +18,3 %) — **sin ninguna señal**, la búsqueda
  "promete" más que en los datos reales (+7,0 %). Es decir: la ganancia interna real está dentro de lo que la búsqueda
  produce por azar.
- Real frente a placebo: p = (1 + #{placebo ≥ −22,0 %}) / 51 = **0,96**: la cifra real es peor que el 94 % de las
  réplicas sin señal (el periodo real tiene saltos de volatilidad —1987— que castigan al GB más que en el barajado).

### 4.3 Todas las pruebas (descriptivo; 60 configuraciones evaluadas fuera de muestra sin elegir)
- Ganancia externa frente a HAR: mediana −8,6 %, media −13,7 %, rango [−56,8 %; +1,2 %]; solo **9 de 60 > 0**, todas
  entre +0,3 % y +1,2 % y todas (salvo #19, también residuo) de modo **residuo** con poca capacidad (lr ≤ 0,016 o
  ≤ 30 iteraciones, profundidad 1-2): son "HAR + un pellizco".
- Por modo: mediana residuo −1,8 %, directo −17,9 %. Por rasgos: HAR −9,2 %, HAR + X −6,8 %.
- La nº 0 (GB de INT-12) da −27,8 %, igual que el descriptivo D_gb_vs_har de INT-12 (comprobación).
- La mejor ex post (#47, +1,2 %) es un **oráculo** (elegida mirando la evaluación) y queda por debajo del p95 del
  placebo (+2,3 %).
- Interno: solo el 26 % de las 660 pruebas bloque × configuración batieron al HAR dentro de muestra de validación.

## 5. Conclusión
- **Ajustar hiperparámetros no rescata al ML.** Con la búsqueda honesta (anidada, con embargo), el GB ajustado es un
  **22 % peor** que el HAR (IC 95 % [−41 %; −2 %]); no mejora al GB fijado de INT-12 frente a HAR (−28 %) de forma
  apreciable, y es peor que el HAR-X lineal. Confirma (exploratoriamente) C3 de INT-12: con 190-850 meses y un objetivo
  tan ruidoso, la capacidad extra sobreajusta, y el bucle interno elige configuraciones distintas cada 5 años.
- **La búsqueda infla:** promete +7 % dentro (+12 % en el placebo sin señal) y entrega −22 % fuera. Sin anidamiento,
  la cifra a publicar habría sido la interna o la del oráculo (+1,2 %): ambas engañosas.
- **El techo es el HAR:** lo único que no pierde es "HAR + residuo muy encogido", con ganancias de ≈ +1 % ex post, dentro
  del ruido del placebo (p95 +2,3 %) y por debajo del 2-5 % que la fase 1 consideraba realista.
- **Criterio "destaca de verdad" (§3): NO se cumple** (ganancia < 0, IC < 0, por debajo del p95 del placebo, una mitad
  negativa). **No se propone ninguna configuración para prerregistrar.** El modelo operativo de volatilidad sigue
  siendo el HAR lineal (INT-12 §7). Si en el futuro se quisiera insistir, la única vía con sentido sería un HAR con
  corrección no lineal pequeña (modo residuo, lr ≈ 0,01, profundidad 1-2) frente al HAR en el periodo bloqueado; con
  ganancias esperadas ≈ 1 % no tendría potencia, así que **no se recomienda gastar el bloqueado en ello**.

## 6. Declaraciones
- Exploratorio: no cambia ningún veredicto de INT-12; `research/int/int12_resultado.*` no se ha tocado.
- Nada ≥ 2005. Una sola corrida (el script se niega si la salida existe). Sin paquetes nuevos (búsqueda aleatoria con
  numpy; sklearn 1.5.2, joblib para el placebo en 12 procesos, un hilo BLAS/OpenMP por proceso).
- Detalles que el lector debe saber: la selección se renueva cada 5 años (no cada enero) para acotar el coste; el
  horizonte a 3 meses y las colas (VaR/ES) no se evaluaron; el placebo baraja (rv, n_días) juntos y deja los rasgos
  intactos; el embargo interno→externo se comprueba con `assert` en cada bloque.
