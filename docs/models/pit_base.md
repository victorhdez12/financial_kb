---
documento: base point-in-time de variables (Fase 3, entregable 2)
version: 0.1
fecha: 2026-10-15
estado: borrador para revisión (sin commit)
codigo: src/features/calendar.py, src/features/pit.py
datos: <FIN_DATA_ROOT>/features/ (data/archive/features/)
tests: tests/test_pit_leaks.py (+ tests/pit_helpers.py)
---

# Base point-in-time de variables (nowcast EE. UU.)

## 1. Qué hay

| fichero | contenido |
|---|---|
| `research/pit_whitelist.yaml` | **Lista blanca**: 46 variables públicas + 20 auxiliares, con mecanismo, serie(s), transformación fijada a priori, modo, estado y regla de admisión; y 16 candidatas **rechazadas** con el motivo |
| `research/pit_calendar.yaml` | Calendario de publicación de las 56 series que lee el constructor |
| `research/pit_calendar_measured.csv` | Retardos medidos con vintages, por épocas (`docs/models/pit_calendar.md`) |
| `src/features/calendar.py` | Medición de retardos y reglas de disponibilidad |
| `src/features/pit.py` | Constructor de la matriz, linaje, persistencia point-in-time y escritura |
| `features/pit_us_v0.1_{vintage,latest_truncated}.parquet` | Matriz: 921 fechas de decisión (1950-01 → 2026-09) × 46 columnas |
| `features/pit_us_v0.1_{modo}_lineage.parquet` | Linaje por celda: serie, fecha de referencia de la última observación usada, modo efectivo |
| `features/baseline_persistence_v0.1_{modo}.parquet` | Persistencia point-in-time (predicciones `pers_*`, **no** son variables) |
| `features/pit_us_v0.1.meta.json` | Hashes (ficheros, contenido, lista blanca, calendario, código), build del warehouse, instantánea de la etiqueta, cobertura por columna y métricas del baseline ≤ 2004 |

Uso:

```bash
.venv/bin/python -m src.features.calendar   # (re)mide retardos → research/pit_calendar_measured.csv
.venv/bin/python -m src.features.pit        # construye los dos modos + baseline → data/archive/features/ (~80 s)
.venv/bin/python -m pytest -q tests         # incluye los tests de fugas (~45 s)
```

```python
from src.features import pit as P
X, lineage, info = P.build_matrix(con, "vintage")        # o "latest_truncated"; índice = fecha de decisión
B = P.persistence(con, "vintage")                         # baseline con el MISMO modo (M-4)
```

## 2. Principios de construcción

- **Fecha de decisión** = último día hábil del mes t (calendario federal). Para emparejar con la etiqueta, la fila t
  corresponde al mes de la etiqueta t (columna `month` del baseline).
- **Solo lista blanca.** El constructor lee únicamente las series de `pit_whitelist.yaml` (y sus proxies de calendario),
  exige `pit_role = observed` en el catálogo, rechaza series con raíz prohibida, comprueba las unidades declaradas y, al
  final, llama a `src.labels.regime_us.assert_no_forbidden` sobre las columnas (segunda barrera; Validador P-4).
- **Transformaciones sobre la serie conocida en t**: en modo vintage se reconstruye la serie tal como se publicó en t y
  se transforma; en modo latest_truncated se transforma la última vintage y cada valor transformado entra cuando su
  última observación (y todas las anteriores) está publicada (`asof.py`, regla 3).
- **Derivadas** (curva, compuestos, histéresis, liquidez) se calculan sobre la rejilla de decisión con valores ya PIT;
  los z-scores son **expansivos** (solo la trayectoria hasta t, mínimo 120 meses) y la histéresis es recursiva sobre
  valores PIT.
- **Datos que caducan:** un valor cuyo periodo terminó hace más de 45 días (D/W), 130 (M), 280 (Q) pasa a NaN (series
  cortadas o interrumpidas).
- **Salida fuera del warehouse** (`data/archive/features/`), con hashes en el meta.

## 3. Modos (Validador M-4)

| modo | qué valor ve el modelo en t | dónde |
|---|---|---|
| `vintage` | la serie **tal como se publicó** en t (ALFRED; RTDSM para el PIB 1965-1991) | 13 series con vintages; fuera del archivo y en las variables declaradas `latest_truncated` cae al modo siguiente (el linaje marca cada celda: `vintage:<serie>` o `latest_truncated`) |
| `latest_truncated` | la **última vintage** (revisada), truncada por la fecha de publicación de cada observación | todas |

El baseline de persistencia se construye con el mismo modo (§6). Con los dos ficheros, el arnés puede entrenar y
puntuar baseline y variables en `vintage` (lo más realista) y comprobar la sensibilidad en `latest_truncated`.

## 4. Variables admitidas (46) y cobertura

Estados: **principal** (25, desde ≤ 1965), **principal_epoca** (12: entran por épocas desde su inicio), **condicional**
(4: duda point-in-time, decide el usuario), **modulo_adicional** (4: nacen en 2003, en el borde del periodo bloqueado;
deben preregistrarse y evaluarse aparte). "Recesiones" = recesiones NBER que empiezan después de `desde` (regla 2:
≥ 3), en total y dentro del periodo de investigación (≤ 2004).

| variable | bloque | estado | series | transformación | modo | desde | vintage desde | recesiones | ≤ 2004 |
|---|---|---|---|---|---|---|---|---|---|
| `payems_3m_ann` | crecimiento | principal | PAYEMS | log_diff_ann k=3 | vintage | 1950-01 | 1955-05 | 11 | 9 |
| `unrate_sahm` | crecimiento | principal | UNRATE | sahm | vintage | 1950-01 | 1960-03 | 11 | 9 |
| `indpro_3m_ann` | crecimiento | principal | INDPRO | log_diff_ann k=3 | vintage | 1950-01 | 1950-01 | 11 | 9 |
| `tcu` | crecimiento | principal_epoca | TCU | level | vintage | 1967-02 | 1996-11 | 8 | 6 |
| `claims_4w_yoy` | crecimiento | principal_epoca | ICSA | rolling_log_yoy n=4 | vintage | 1968-02 | 2009-05 | 8 | 6 |
| `awhman_d3` | crecimiento | principal | AWHMAN | diff k=3 | latest_truncated | 1950-01 | — | 11 | 9 |
| `permit_yoy` | crecimiento | principal | PERMIT | log_diff k=12 | latest_truncated | 1961-02 | — | 8 | 6 |
| `philly_activity` | crecimiento | principal_epoca | GACDFSA066MSFRBPHI | level | latest_truncated | 1968-05 | — | 8 | 6 |
| `philly_neworders` | crecimiento | principal_epoca | NOCDFSA066MSFRBPHI | level | latest_truncated | 1968-05 | — | 8 | 6 |
| `umcsent` | crecimiento | principal | UMCSENT | level | latest_truncated | 1953-01 | — | 11 | 9 |
| `cfnai_ma3` | crecimiento | condicional | CFNAI | rolling_mean n=3 | vintage | 1967-06 | 2011-05 | 8 | 6 |
| `gdp_qoq_ann` | crecimiento | principal | GDPC1 | log_diff_ann k=1 | vintage | 1950-01 | 1965-11 | 11 | 9 |
| `w875rx1_3m_ann` | crecimiento | principal | W875RX1 | log_diff_ann k=3 | latest_truncated | 1959-06 | — | 9 | 7 |
| `cmrmtspl_3m_ann` | crecimiento | principal_epoca | CMRMTSPL | log_diff_ann k=3 | latest_truncated | 1967-07 | — | 8 | 6 |
| `spf_rgdp_4q` | crecimiento | principal_epoca | SPF rgdp_6/rgdp_2 | 100·log(ratio) | derivada | 1968-12 | — | 8 | 6 |
| `growth_rt` | crecimiento | principal | — | media de z expansivos de indpro, payems, w875rx1, cmrmtspl (≥ 2) | derivada | 1959-12 | 1950-01 | 9 | 7 |
| `growth_rt_state` | crecimiento | principal | — | histéresis ±0,15 o Sahm ≥ 0,5 | derivada | 1959-12 | 1950-01 | 9 | 7 |
| `core_cpi_6m_ann` | inflación | principal | CPILFESL | pct_ann k=6 | vintage | 1957-09 | 1996-12 | 10 | 8 |
| `core_cpi_yoy` | inflación | principal | CPILFESL | pct_ann k=12 | vintage | 1958-03 | 1996-12 | 9 | 7 |
| `headline_cpi_6m_ann` | inflación | principal | CPIAUCSL | pct_ann k=6 | vintage | 1950-01 | 1972-07 | 11 | 9 |
| `core_pce_6m_ann` | inflación | condicional | PCEPILFE | pct_ann k=6 | vintage | 1959-09 | 2000-08 | 9 | 7 |
| `ppi_yoy` | inflación | principal | PPIACO | pct_ann k=12 | vintage | 1950-01 | 1996-12 | 11 | 9 |
| `oil_yoy` | inflación | principal | MCOILWTICO → WPU0561 | log_diff k=12 | latest_truncated | 1950-01 | — | 11 | 9 |
| `infl_composite` | inflación | principal | — | media de z expansivos de subyacente, general, PPI, petróleo (≥ 3) | derivada | 1959-12 | 1972-07 | 9 | 7 |
| `mich_infl_exp` | inflación | principal_epoca | MICH | level | latest_truncated | 1978-03 | — | 6 | 4 |
| `spf_cpi_4q` | inflación | principal_epoca | spf_mean_cpi_6 | level | latest_truncated | 1981-08 | — | 5 | 3 |
| `usd_neer_yoy` | inflación | principal | BIS NEER estrecha | log_diff k=12 | latest_truncated | 1965-03 | — | 8 | 6 |
| `curve_10y3m` | financieras | principal | T10Y3M → DGS10/GS10 − DTB3/TB3MS | nivel | derivada | 1953-05 | — | 11 | 9 |
| `curve_d3m` | financieras | principal | — | Δ3m de la curva | derivada | 1953-08 | — | 11 | 9 |
| `level_d3m` | financieras | principal | — | Δ3m de (10a + 3m)/2 | derivada | 1953-08 | — | 11 | 9 |
| `bear_steepening` | financieras | principal | — | 1 si Δcurva > 0 y Δnivel > 0 | derivada | 1953-08 | — | 11 | 9 |
| `bull_steepening` | financieras | principal | — | 1 si Δcurva > 0 y Δnivel < 0 | derivada | 1953-08 | — | 11 | 9 |
| `ff_d12m` | financieras | principal | DFF | Δ12m | derivada | 1955-07 | — | 10 | 8 |
| `real_ff` | financieras | principal | DFF − core_cpi_yoy | diferencia | derivada | 1958-03 | 1996-12 | 9 | 7 |
| `baa_spread` | financieras | principal | BAA10Y → BAA − GS10 | nivel | derivada | 1953-05 | — | 11 | 9 |
| `gz_spread` | financieras | principal_epoca | fed_ebp_gz_spread | level | latest_truncated | 1973-03 | — | 7 | 5 |
| `ebp` | financieras | condicional | fed_ebp_ebp | level | latest_truncated | 1973-03 | — | 7 | 5 |
| `nfci` | financieras | condicional | NFCI | level | latest_truncated | 1971-01 | — | 7 | 5 |
| `vix` | financieras | principal_epoca | VIXCLS | level | latest_truncated | 1990-01 | — | 4 | 2 |
| `eq_ret_6m` | financieras | principal | shiller_sp_price | log_diff k=6 | latest_truncated | 1950-01 | — | 11 | 9 |
| `copper_gold_6m` | financieras | principal | wb_copper / wb_gold | Δ6m del log del cociente | derivada | 1960-08 | — | 8 | 6 |
| `m2_real_yoy` | liquidez | principal | M2SL a/a − IPC a/a | diferencia | derivada | 1960-02 | 1972-07 | 9 | 7 |
| `net_liq_yoy` | liquidez | modulo_adicional | WALCL − TGA (DTS/WTREGEN) − RRP | log a/a | derivada | 2003-12 | — | 2 | 0 |
| `global_cb_usd_yoy` | liquidez | modulo_adicional | Fed + BCE·USD/EUR + BoJ/JPY | log a/a | derivada | 2003-12 | — | 2 | 0 |
| `t5yie` | inflación | modulo_adicional | T5YIE | level | latest_truncated | 2003-01 | — | 2 | 0 |
| `dfii10` | financieras | modulo_adicional | DFII10 | level | latest_truncated | 2003-01 | — | 2 | 0 |

**Épocas** (regla 4: la presencia/ausencia de un dato no puede hacer de señal): E0 1960+ (los 25 principales),
E1 1968-69+ (TCU, peticiones de paro, Filadelfia, CMRMTSPL, SPF PIB, CFNAI), E2 1971-73+ (NFCI, GZ, EBP),
E3 1978-82+ (Michigan, SPF IPC), E4 1990+ (VIX), módulo 2003+. La matriz deja NaN antes del inicio y **no** incluye
indicadores de disponibilidad; el arnés debe elegir el conjunto de variables por época (fecha `desde` en el meta).

**Pendientes de la Fase 1 cubiertos:** histéresis de G (`growth_rt_state`), inflación compuesta con petróleo y PPI
(`infl_composite`, `oil_yoy`, `ppi_yoy`), bear/bull steepening, liquidez neta diaria (`net_liq_yoy`, con la TGA diaria
del DTS desde 2005-10) y global (`global_cb_usd_yoy`). La capa EUR queda para su fase.

## 5. Tests de fugas (`tests/test_pit_leaks.py`, 18 tests, todos en verde)

| test | qué comprueba | resultado |
|---|---|---|
| (a) `test_a_no_cell_uses_unpublished_data` ×2 modos | Para cada celda del linaje, la fecha de publicación **recalculada desde `observations`** sin usar `calendar.py` (vintages: primera fila no nula con `realtime_start ≤ t`; resto: proxies del yaml o ancla + retardo) es ≤ t; y, sin calendario, ningún dato de un periodo que no ha terminado (salvo las encuestas del propio mes) | 0 celdas fuera. Prueba de mutación: con PERMIT a −3 días el test detecta 788 celdas |
| (b) `test_b_truncation_same_row` ×5 cortes | Con el warehouse truncado en t (última vintage con fecha ≤ t; vintages con `realtime_start ≤ t`), la fila t es idéntica a la de la matriz completa, en los dos modos. Cortes: 1962-03, 1979-10, 1996-12 (inicio de vintages del IPC subyacente), 2004-12 y 2011-05 (solo datos, sin etiqueta) | idénticas (rtol 1e-9) |
| (b) `test_b_truncation_persistence` ×2 | La persistencia en t no cambia con la instantánea de la etiqueta y las vintages truncadas en t | idéntica |
| (c) `test_c_placebo_block_shuffled_label` | Etiqueta ≤ 2004 barajada en bloques de 24 meses (10 permutaciones); logística multinomial (8 variables) + persistencia frente a solo persistencia, walk-forward anual 1975-2004, embargo 6 | mejora de log-loss −0,37 a −0,67 nats (media −0,48): ninguna habilidad, solo sobreajuste |
| (d) `test_d_planted_signal…` | Warehouse sintético: régimen de Markov, una serie = f(régimen) + ruido publicada a 20 días con primera publicación ruidosa y revisión a 110 días, y una serie de ruido | Calendario correcto (en t se usa el dato de t−1); el modo vintage da la primera publicación y latest_truncated la revisada; señal recuperada +0,23 nats; ruido < 0,02 |
| (e) `test_e_*` | `assert_no_forbidden` (meta oficial), ninguna columna de la etiqueta, `pers_*`, `label*`, `p_*`; ninguna serie prohibida en el linaje; columnas = lista blanca; el constructor rechaza `USREC` como serie y `usrec_lag1` como derivada | ok |
| (f) `test_f_*` | Todas las series leídas son `observed`; el constructor rechaza `GDPPOT`; las expectativas son encuestas fechadas (SPF anclado al inicio del trimestre + ≥ 45 días) | ok |
| calendario / lista blanca | El retardo de reserva ≥ p90 medido en la época más antigua; cada variable documentada (mecanismo, admisión, transformación conocida) | ok |

## 6. Persistencia point-in-time con los dos modos (M-4), solo entrenamiento ≤ 2004

Misma regla que la ficha §12 (última etiqueta calculable en t, normalmente t − 5, recalculada desde la instantánea
congelada con los datos conocidos en t), pero con las fechas de publicación reales del calendario.

| modo | n | acierto | log-loss blanda |
|---|---|---|---|
| latest_truncated (todos los meses ≤ 2004) | 595 (1955-06 → 2004-12) | 62,9 % | 1,228 (= `label_v1.1_checks.md` §6b: 62,9 %, 1,227) |
| vintage | 579 (1956-10 → 2004-12) | 61,1 % | 1,300 |
| latest_truncated, mismos 579 meses | 579 | 63,0 % | 1,182 |

Con los datos tal como se publicaron, la persistencia es **peor** (log-loss +0,12): el listón honesto depende del
modo. El arnés debe comparar cada modelo con el baseline de su mismo modo. No se ha mirado el periodo bloqueado
(`score_training` falla si se le pasa).

## 7. Limitaciones

1. **Historia reconstruida en latest_truncated.** Antes del archivo de vintages se usan datos revisados con fechas de
   publicación correctas. Además hay series que **no existían en tiempo real** con su definición actual: PCE subyacente
   antes de ~1996-2000 (por eso `core_pce_6m_ann` es condicional), M2 antes de 1980, CFNAI antes de 2001, GZ/EBP antes de
   2012, y probablemente el IPC subyacente en los años 50-60 (supuesto, sin verificar).
2. **El cambio de vintage a revisado delata la época** dentro de una columna en modo vintage (p. ej. `core_cpi_6m_ann`
   pasa a primeras publicaciones en 1996-12). Es ruido de medición, no un hueco, pero el arnés puede comprobarlo con el
   modo latest_truncated.
3. **Supuestos de calendario** sin medir: encuestas regionales, Michigan, SPF, PERMIT, EBP/GZ, BIS, Pink Sheet. Son
   conservadores, pero no están verificados con fechas históricas de publicación.
4. **Revisiones sin vintages**: factores estacionales de Filadelfia, peticiones de paro antes de 2009, NFCI y EBP
   (reestimados con toda la muestra), CMRMTSPL y W875RX1 (las vintages están en `labels/raw`, no en el warehouse).
5. **Empalmes**: curva (T10Y3M desde 1982, antes 10a − letras en base descuento), diferencial Baa (diario desde 1986),
   petróleo (PPI de crudo hasta 1986, WTI después), TGA (semanal H.4.1 hasta 2005-10, DTS diario después). Son cambios de
   fuente en fechas fijas, anotados aquí.
6. **UMCSENT** es trimestral hasta 1977 (el valor se mantiene entre encuestas).
7. **Decisión a fin de mes**: la variante del día 15 de t+1 (ficha §9) no está construida; basta con otra rejilla
   (`decision_grid`).
8. El baseline vintage usa vintages de W875RX1/CMRMTSPL (instantánea de la etiqueta) que las variables no usan
   (latest_truncated): diferencia menor, documentada.

## 8. Qué quedó fuera y por qué

Ver `rechazadas` en `research/pit_whitelist.yaml`: USREC (ex post), GDPPOT/NROU (forecast; la brecha de paro necesita
vintages de NROU), probabilidades de recesión de la EBP y de la NY Fed (estimadas con toda la muestra), prima por plazo
ACM y expectativas de Cleveland (modelos reestimados), TEDRATE, TWEXB y la base monetaria (fuentes muertas), futuros de
energía (cortados en 2024), Atlanta MPT (desde 2023), estructura del VIX y volatilidad de tipos (preregistradas aparte,
H-DER-001/002), STLFSI (reestimado y redundante), SAHMREALTIME (duplicada), capa EUR (su fase) y las capas ex post
L-CAP (prohibidas). También fuera por ahora: ISM (no está en el warehouse), SLOOS y morosidad (trimestrales, candidatas
para la v0.2), crédito/PIB (Z.1, revisado y con retardo largo), JTSJOL y TEMPHELPS (nacen en 1990-2000).

## 9. Decisiones para el usuario

1. Variables **condicionales** (`cfnai_ma3`, `core_pce_6m_ann`, `ebp`, `nfci`): ¿entran en el modelo principal, solo
   desde que hay vintages (2000/2011), o solo en el módulo? La propuesta es excluirlas del modelo principal ≤ 2004 y
   descargar las vintages ALFRED de NFCI (2011+) para reevaluarlas.
2. **Modo principal del arnés**: propuesta `vintage` para entrenar y puntuar (con su baseline), `latest_truncated` como
   sensibilidad.
3. **Módulo adicional** (`net_liq_yoy`, `global_cb_usd_yoy`, `t5yie`, `dfii10`): preregistrarlas en
   `research/hypotheses.yaml` como H-DER-001/002 antes de la evaluación única.
4. **Supuestos de calendario** de la §3 de `pit_calendar.md`: aceptarlos o pedir verificación con calendarios
   históricos (sobre todo Filadelfia 1968-90 y SPF antes de 1990).
5. Si se acepta el hallazgo sobre `months_back` (CMRMTSPL), decidir si la ficha de la etiqueta §12 debe citar la
   persistencia de `src/features/pit.py` como referencia (mismo resultado en entrenamiento).
