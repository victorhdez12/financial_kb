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

## 4. Resultado
(se redacta después de la corrida)
