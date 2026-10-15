---
documento: base point-in-time de variables (Fase 3, entregable 2)
version: 0.3
fecha: 2026-10-15
estado: CANDIDATA (hashes en CANDIDATE y en el meta; entra en FROZEN solo tras el ✅ del Validador). Sustituye a la v0.2
codigo: src/features/{calendar,pit,placebo,alfred_raw}.py, src/ingest/umich.py
datos: <FIN_DATA_ROOT>/features/ (data/archive/features/)
tests: tests/test_pit_leaks.py (+ tests/pit_helpers.py), 41 tests
revisiones: docs/validation/2026-10-15_pit_base_v0.1.md, docs/validation/2026-10-15_pit_base_v0.2.md (Validador ⚠️, muy cerca de ✅), docs/reviews/2026-10-15_estratega_macro_pit_base.md
---

# Base point-in-time de variables (nowcast EE. UU.), v0.3

## 1. Qué hay

| fichero | contenido |
|---|---|
| `research/pit_whitelist.yaml` | **Lista blanca v0.3**: 58 variables públicas + 26 auxiliares, con mecanismo, serie(s), transformación fijada a priori, modo, estado, `desde`/`principal_desde` y regla de admisión; 21 candidatas **rechazadas** con su motivo |
| `research/pit_calendar.yaml` | Calendario de publicación de las 61 series que lee el constructor, con `supuesto` por tramo y la variante prudente de Filadelfia |
| `research/pit_calendar_measured.csv` | Retardos medidos con vintages (warehouse + `features/raw/alfred`), por épocas |
| `src/features/calendar.py` | Reglas de disponibilidad y medición |
| `src/features/pit.py` | Constructor, linaje, persistencia PIT, instantánea (`FROZEN`, `CANDIDATE`, `write_snapshot`, `write_candidate`, `read_snapshot`), herencia de `principal_desde` (`effective_principal_desde`), parámetros de la etiqueta con hash (`label_params`) y escritura |
| `src/features/placebo.py` | Walk-forward logístico mínimo y **placebo con potencia** (reutilizable por el arnés) |
| `src/features/alfred_raw.py` | Vintages ALFRED fuera del warehouse → `features/raw/alfred/` (PERMIT, CMRMTSPL, NFCI, W875RX1, AWHMAN, AHETPI, CUSR0000SASLE, Filadelfia ×3, UMCSENT, MICH) |
| `src/ingest/umich.py` | Fuente nueva: Universidad de Michigan directa (`curated/umich`: `umich_ics`, `umich_px1_md`, `umich_px5_md`) |
| `features/inputs/pit_us_v0.2_inputs.parquet` | **Instantánea de datos** (la misma para la v0.2 y la v0.3, sin releer el warehouse): 1,30 M filas (última vintage, vintages y catálogo de las 61 series), solo lectura, copia en `inputs/backup/` |
| `features/inputs/pit_us_v0.3_{whitelist,calendar}.yaml`, `pit_us_v0.3_inputs.json` | Copias congeladas de la lista blanca y el calendario v0.3 y su info (con el hash de los datos reutilizados); hashes en `CANDIDATE` |
| `features/pit_us_v0.3_{vintage,latest_truncated}.parquet` | Matriz oficial: 921 fechas de decisión (1950-01 → 2026-09) × 58 columnas |
| `features/pit_us_v0.3_vintage_filadelfia_prudente.parquet` | Sensibilidad preregistrada S-PIT-001 (Filadelfia con t−1 antes de 1990-07) |
| `features/pit_us_v0.3_{…}_lineage.parquet` | Linaje por celda: serie, fecha de la observación usada, modo efectivo |
| `features/baseline_persistence_v0.3_{modo}.parquet` | Persistencia PIT en los dos modos **sobre la misma muestra** (predicciones `pers_*`, no variables) |
| `features/pit_us_v0.3.meta.json` | Hashes de salida, instantánea (`candidata` = `CANDIDATE`, estado), versión sustituida, parámetros de la etiqueta y hash de su meta, código, cobertura por columna (con `principal_desde_efectivo`), baseline ≤ 2004 y la regla del arnés |

Uso:

```bash
.venv/bin/python -m src.ingest.umich            # Michigan directo (ya en INGEST_DAILY del Makefile)
.venv/bin/python -m src.features.alfred_raw     # vintages ALFRED fuera del warehouse
.venv/bin/python -m src.features.calendar       # (re)mide retardos
.venv/bin/python -m src.features.pit --freeze   # warehouse vivo + raw → instantánea de datos (se niega con una versión en FROZEN)
.venv/bin/python -m src.features.pit --candidate  # lista blanca/calendario nuevos sobre la instantánea de datos existente
.venv/bin/python -m src.features.pit            # matriz OFICIAL desde la instantánea (~95 s)
.venv/bin/python -m src.features.pit --live     # seguimiento desde el warehouse vivo (*_live; no oficial)
.venv/bin/python -m pytest -q tests             # 92 tests (~2,5 min)
```

## 2. Principios de construcción

- **Fecha de decisión** = último día hábil del mes t (calendario federal); la fecha final de la rejilla queda fijada en
  la instantánea (`grid_end` = 2026-09-30).
- **Solo desde la instantánea.** La matriz oficial lee únicamente la instantánea (sin warehouse vivo ni raw);
  `read_snapshot` se niega a usar ficheros cuyo SHA-256 no coincida con `FROZEN` o, para una candidata, con
  `CANDIDATE`; `write_snapshot` y `write_candidate` no tocan una versión congelada. Una actualización diaria del
  warehouse no cambia la matriz oficial.
- **Parámetros de la etiqueta para la persistencia** (`label_params`): s_G y s_I de `R.PARAMS` (código en git) y el
  empalme recalculado desde la instantánea congelada de la etiqueta (hash en `R.FROZEN`). El `meta.json` de la etiqueta
  solo se usa para comprobar que coinciden, y su SHA-256 está fijado en `LABEL_META_SHA256`: si cambia, falla.
- **Solo lista blanca**, `pit_role = observed`, unidades comprobadas, sin raíces prohibidas y `assert_no_forbidden` al
  final (segunda barrera).
- **Transformaciones sobre la serie conocida en t** (vintage: la serie tal como se publicó; latest_truncated: la última
  vintage, cada observación desde su publicación). Derivadas sobre la rejilla con valores ya PIT; tendencias, escalas y
  z-scores **solo hacia atrás**.
- `desde`: la columna es NaN antes (sin mecanismo o sin datos fiables). `principal_desde`: antes, la variable es
  **condicional** (existe en la matriz, pero el arnés no la usa en el modelo principal).
- **Regla general de herencia (v0.3):** una derivada entra en el modelo principal desde el `principal_desde` **más
  tardío de todas sus entradas**, recorriendo el grafo de dependencias en código (`effective_principal_desde`). El meta
  lo publica por columna como `principal_desde_efectivo` (y `principal_desde_heredado`). Hoy solo cambia
  `infl_energy_pressure` (→ 1978-01, por `headline_minus_core_6m`).

## 3. Modos y regla del arnés (decisión B)

| modo | qué ve el modelo en t | papel |
|---|---|---|
| `vintage` | la serie tal como se publicó en t (ALFRED; RTDSM para el PIB 1965-91; vintages propias de PERMIT, CMRMTSPL, NFCI, W875RX1, AHETPI, CUSR0000SASLE) | **modo principal** |
| `latest_truncated` | la última vintage truncada por la fecha de publicación de cada observación | **sensibilidad**; se puntúa también |

**Reglas que el arnés (entregable 3) debe cumplir:**
1. Entrenar y puntuar en `vintage`; repetir en `latest_truncated` y publicar las dos.
2. Comparar cada modelo con el baseline de persistencia **de su mismo modo**, sobre la **misma muestra de meses**.
3. **Estabilidad a ambos lados del salto revisado → primera publicación.** En modo vintage, cada columna con vintages
   cambia de régimen de ruido en la fecha `vintage_desde` (tabla §4; p. ej. IPC subyacente 1996-12, IPC 1972-07, M2
   1980-02, TCU 1996-11, peticiones de paro 2009-05, PIB 1965-11 y 1991-12). El arnés debe comprobar que la
   importancia y el signo de cada variable son estables antes y después de esos saltos, y puede añadir una columna de
   época **solo para diagnosticar, nunca como variable**. Saltos de **composición** que también cuentan: `growth_rt`
   empieza en 1963-11 con 2 entradas (INDPRO, PAYEMS), pasa a 3 en **1973-04** (W875RX1) y a 4 en **1981-05**
   (CMRMTSPL). Cada entrada necesita ≥ 108 meses para su tendencia (mediana de 120 meses con el 90 % de la ventana:
   W875RX1 desde 1968-05, CMRMTSPL desde 1976-06) y después ≥ 60 meses de desviaciones para la escala MAD. Esos 108/60
   meses son los mínimos reales; el Estratega proponía 120. `infl_core_pressure` cambia de composición en 1967-68
   (servicios) y el petróleo de `infl_energy_pressure` en el empalme de 1987.
4. No usar ninguna variable antes de su `principal_desde_efectivo` (meta) en el modelo principal; las condicionales
   solo en sensibilidad.
5. Publicar la sensibilidad S-PIT-001 (Filadelfia prudente) y S-PIT-002 (Michigan en Δ12m), preregistradas.
6. Repetir el placebo (`src/features/placebo.py`) sobre sus propias predicciones: sin fuga debe pasar y con una fuga
   inyectada debe fallar.

## 4. Variables (58) y cobertura

Estados: **principal** 36 (de ellas 9 solo desde su `principal_desde_efectivo`, una por herencia), **principal_epoca** 13, **condicional** 5,
**modulo_adicional** 4. "Recesiones" = recesiones NBER que empiezan después del primer dato utilizable en el modelo
principal (máx. de primer dato y `principal_desde`), en total y ≤ 2004 (regla 2: ≥ 3).

| variable | bloque | estado | principal desde | serie(s) / función | modo | primer dato | vintage desde | recesiones (≤ 2004) |
|---|---|---|---|---|---|---|---|---|
| `payems_3m_ann` | crecimiento | principal | — | PAYEMS · log_diff_ann k=3 | vintage | 1950-01 | 1955-05 | 11 (9) |
| `unrate_sahm` | crecimiento | principal | — | UNRATE · sahm | vintage | 1950-01 | 1960-03 | 11 (9) |
| `unrate_gap10y` (A3) | crecimiento | principal | — | UNRATE − mediana de los 120 meses previos | derivada | 1959-01 | 1960-03 | 9 (7) |
| `indpro_3m_ann` | crecimiento | principal | — | INDPRO · log_diff_ann k=3 | vintage | 1950-01 | 1950-01 | 11 (9) |
| `tcu_gap` | crecimiento | principal_epoca | — | TCU − media de los 120 meses previos | derivada | 1976-02 | 1996-11 | 6 (4) |
| `claims_4w_yoy` | crecimiento | principal_epoca | — | ICSA · rolling_log_yoy n=4 | vintage | 1968-02 | 2009-05 | 8 (6) |
| `awhman_d3` | crecimiento | principal | — | AWHMAN · diff k=3 | latest_truncated | 1950-01 | — | 11 (9) |
| `permit_yoy` | crecimiento | principal | — | PERMIT · log_diff k=12 | vintage | 1961-02 | 1999-08 | 8 (6) |
| `philly_activity` | crecimiento | principal_epoca | — | GACDFSA066MSFRBPHI · level | latest_truncated | 1968-05 | — | 8 (6) |
| `philly_neworders` | crecimiento | principal_epoca | — | NOCDFSA066MSFRBPHI · level | latest_truncated | 1968-05 | — | 8 (6) |
| `umcsent` | crecimiento | principal_epoca | — | umich_ics · level (desde 1978-01) | latest_truncated | 1978-01 | — | 6 (4) |
| `cfnai_ma3` | crecimiento | condicional | 2011-05 | CFNAI · rolling_mean n=3 | vintage | 1967-06 | 2011-05 | 1 (0) |
| `gdp_qoq_ann` | crecimiento | principal | — | GDPC1 · log_diff_ann k=1 | vintage | 1950-01 | 1965-11 | 11 (9) |
| `w875rx1_3m_ann` | crecimiento | principal | — | W875RX1 · log_diff_ann k=3 | vintage | 1959-06 | 2010-05 | 9 (7) |
| `cmrmtspl_3m_ann` | crecimiento | principal_epoca | — | CMRMTSPL · log_diff_ann k=3 | vintage | 1967-07 | 2013-06 | 8 (6) |
| `spf_rgdp_4q` | crecimiento | principal_epoca | — | 100·log(SPF rgdp_6 / rgdp_2) | derivada | 1968-12 | — | 8 (6) |
| `spf_anxious` (A5) | crecimiento | principal_epoca | — | spf_anxious_index · level | latest_truncated | 1969-04 | — | 8 (6) |
| `growth_rt` | crecimiento | principal | — | media de z frente a la tendencia de 10 años (MAD) de indpro, payems, w875rx1, cmrmtspl (≥ 2) | derivada | 1963-11 | (entradas) | 8 (6) |
| `growth_rt_state` | crecimiento | principal | — | histéresis ±0,5 σ, 2 meses; Sahm ≥ 0,5 inmediato | derivada | 1968-10 | (entradas) | 8 (6) |
| `core_cpi_6m_ann` | inflación | principal | 1978-01 | CPILFESL · pct_ann k=6 | vintage | 1957-09 | 1996-12 | 6 (4) |
| `core_cpi_yoy` | inflación | principal | 1978-01 | CPILFESL · pct_ann k=12 | vintage | 1958-03 | 1996-12 | 6 (4) |
| `core_services_cpi_6m_ann` (A1) | inflación | principal | 1978-01 | CUSR0000SASLE · pct_ann k=6 | vintage | 1967-09 | 2011-04 | 6 (4) |
| `headline_cpi_6m_ann` | inflación | principal | — | CPIAUCSL · pct_ann k=6 | vintage | 1950-01 | 1972-07 | 11 (9) |
| `core_pce_6m_ann` | inflación | condicional | 2000-08 | PCEPILFE · pct_ann k=6 | vintage | 1959-09 | 2000-08 | 3 (1) |
| `ahe_yoy` (A2) | inflación | principal | — | AHETPI · pct_ann k=12 | vintage | 1965-02 | 1999-08 | 8 (6) |
| `ppi_yoy` | inflación | principal | — | PPIACO · pct_ann k=12 | vintage | 1950-01 | 1996-12 | 11 (9) |
| `oil_yoy` | inflación | principal | — | MCOILWTICO → WPU0561 · log_diff k=12 | latest_truncated | 1950-01 | — | 11 (9) |
| `headline_minus_core_6m` (A8) | inflación | principal | 1978-01 | general 6m − subyacente 6m | derivada | 1957-09 | 1972-07 | 6 (4) |
| `core_cpi_dir` (A9) | inflación | principal | 1978-01 | Δ6m de core_cpi_6m_ann | derivada | 1958-03 | 1996-12 | 6 (4) |
| `infl_core_pressure` | inflación | principal | 1978-01 | media (pp) de subyacente 6m, servicios 6m, salarios a/a − 1,5 | derivada | 1965-02 | 1996-12 | 6 (4) |
| `infl_energy_pressure` | inflación | principal | **1978-01 (heredado)** | media de z expansivos de petróleo, PPI, general − subyacente | derivada | 1959-12 | (entradas) | 6 (4) |
| `philly_prices_paid` (A7) | inflación | principal_epoca | — | PPCDFSA066MSFRBPHI · level | latest_truncated | 1968-05 | — | 8 (6) |
| `mich_infl_exp` | inflación | principal_epoca | — | umich_px1_md · level | latest_truncated | 1978-02 | — | 6 (4) |
| `spf_pgdp_4q` (A4) | inflación | principal_epoca | — | 100·log(SPF pgdp_6 / pgdp_2), mediana | derivada | 1968-12 | — | 8 (6) |
| `spf_cpi_4q` | inflación | principal_epoca | — | spf_mean_cpi_6 · level | latest_truncated | 1981-09 | — | 4 (2) |
| `usd_neer_yoy` | inflación | principal | — | BIS NEER estrecha · log_diff k=12 (desde 1973-03) | latest_truncated | 1973-03 | — | 7 (5) |
| `curve_10y3m` | financieras | principal | — | T10Y3M → DGS10/GS10 − DTB3/TB3MS | derivada | 1953-05 | — | 11 (9) |
| `curve_d3m` | financieras | principal | — | Δ3m de la curva | derivada | 1953-08 | — | 11 (9) |
| `level_d3m` | financieras | principal | — | Δ3m de (10a + 3m)/2 | derivada | 1953-08 | — | 11 (9) |
| `curve_bear_steep` / `_bull_steep` / `_bear_flat` / `_bull_flat` | financieras | principal | — | 4 estados de Δ3m (25 pb, tramo dominante) | derivada | 1953-08 | — | 11 (9) |
| `ff_d12m` | financieras | principal | — | Δ12m de DFF | derivada | 1955-07 | — | 10 (8) |
| `real_ff` | financieras | principal | 1978-01 | DFF − core_cpi_yoy | derivada | 1958-03 | 1996-12 | 6 (4) |
| `fedpath_1y` (A6) | financieras | principal | — | GS1 − FEDFUNDS (medias mensuales) | derivada | 1954-08 | — | 10 (8) |
| `baa_spread` | financieras | principal | — | BAA10Y → BAA − GS10 | derivada | 1953-05 | — | 11 (9) |
| `gz_spread` | financieras | condicional | 2012-01 | fed_ebp_gz_spread · level | latest_truncated | 1973-03 | — | 1 (0) |
| `ebp` | financieras | condicional | nunca | fed_ebp_ebp · level | latest_truncated | 1973-03 | — | 0 (0) |
| `nfci` | financieras | condicional | 2011-05 | NFCI · level | vintage | 1971-01 | 2011-05 | 1 (0) |
| `vix` | financieras | principal_epoca | **2003-09** | VIXCLS · level (definición actual desde 2003-09-22) | latest_truncated | 1990-01 | — | 2 (0) |
| `eq_ret_6m` | financieras | principal | — | shiller_sp_price · log_diff k=6 | latest_truncated | 1950-01 | — | 11 (9) |
| `copper_gold_6m` | financieras | principal | — | Δ6m del log(cobre/oro) (desde 1973-01) | derivada | 1973-01 | — | 7 (5) |
| `m2_real_yoy` | liquidez | principal | 1980-02 | M2 a/a − IPC a/a | derivada | 1960-02 | 1972-07 | 6 (4) |
| `net_liq_yoy` | liquidez | modulo_adicional (H-MOD-001) | — | log a/a de WALCL − TGA − RRP | derivada | 2003-12 | — | 2 (0) |
| `global_cb_usd_yoy` | liquidez | modulo_adicional (H-MOD-002) | — | log a/a de Fed + BCE·USD/EUR + BoJ/JPY | derivada | 2003-12 | — | 2 (0) |
| `t5yie` | inflación | modulo_adicional (H-MOD-003) | — | T5YIE · level | latest_truncated | 2003-01 | — | 2 (0) |
| `dfii10` | financieras | modulo_adicional (H-MOD-004) | — | DFII10 · level | latest_truncated | 2003-01 | — | 2 (0) |

**Épocas** (regla 4): E0 1960+ (27 principales sin `principal_desde_efectivo`), E1 1968-77 (Filadelfia, peticiones de paro,
CMRMTSPL, SPF, `tcu_gap` desde 1976), E2 1973 (`usd_neer_yoy`, `copper_gold_6m`), E3 1978-81 (bloque del IPC
subyacente, `infl_energy_pressure`, Michigan, SPF IPC), 1980 (`m2_real_yoy`), E4 2003-09 (VIX, solo en el periodo
bloqueado). La matriz no lleva indicadores de disponibilidad. `spf_cpi_4q` cumple la regla 2 con su historia total,
pero solo tiene 2 recesiones ≤ 2004; `vix` no tiene ninguna en el modelo principal ≤ 2004: la investigación ≤ 2004 no
las puede validar.

**Descriptivos sin etiqueta (≤ 2004, en trial_log):** `growth_rt_state` cambia 0,44 veces/año (v0.1: 1,06; objetivo
Fase 1: 0,43). Los 4 estados de la curva marcan el 59 % de los meses (11/16/20/11 %).

## 5. Tests (47 en `tests/test_pit_leaks.py`; 92 en total, en verde). Corren sobre la instantánea

| grupo | qué comprueba | resultado |
|---|---|---|
| (h) instantánea | la v0.3 está en `CANDIDATE` y **no** en `FROZEN`; datos = los de la v0.2 (mismo hash); instantánea, lista blanca, calendario e info = `CANDIDATE`; solo lectura y respaldo idéntico; las versiones congeladas (v0.2) siguen intactas; `research/*.yaml` = copias de la v0.3; copia alterada rechazada; los dos escritores se niegan con una versión congelada; **reproducción de las 3 matrices y de los 2 baselines** frente al meta; parámetros de la etiqueta fijados (un `meta.json` alterado hace fallar) | ok |
| (I-1) herencia | recorrido independiente del grafo: el `principal_desde_efectivo` de cada columna = el más tardío del nodo y de todos sus ancestros, en código y en el meta; solo `infl_energy_pressure` hereda (1978-01) | ok |
| (I-2) VIX | `principal_desde` = 2003-09-22 | ok |
| (a) publicación ≤ t | publicación recalculada desde `observations` sin `calendar.py`; sin calendario, ningún dato de un periodo sin terminar; **BCE**: dato usado siempre ≥ 8 días antes de t | 0 celdas fuera |
| (v) valores | ≥ 150 celdas por modo recalculadas con SQL y la transformación escrita en el test (sin `src.features`) | iguales (rtol 1e-9) |
| (v) calendario frente a otra fuente | **proxies "mismo comunicado"** verificadas con las vintages propias de 8 series (AWHMAN, AHETPI, UNRATE → PAYEMS; servicios, subyacente → IPC; W875RX1, PCE subyacente → PCEPI; TCU → INDPRO): la serie nunca se publica después que su proxy (mismo día en el 100 % de 150-800 fechas). **Supuestos frente a ALFRED**: Filadelfia −7 d (≥ 95 %, 2015+), PERMIT 23 d (100 % de 1999-2012), CMRMTSPL 70 d (≥ 90 %). Reserva ≥ p90 medido en la época más antigua | ok |
| (b) truncamiento | fila t idéntica con entradas truncadas en t, 5 cortes (1962, 1979, 1996, 2004, 2014) × 2 modos; persistencia idéntica truncando la instantánea de la etiqueta; los dos baselines tienen las mismas fechas | ok |
| (c) placebo con potencia | etiqueta ≤ 2004 barajada en bloques de 24 meses, 8 permutaciones, L2 = 0,05: **sin fuga** −0,06 a −0,21 nats (pasa); **con la fuga fuerte** (objetivo del propio mes + ruido σ = 0,5; σ elegida tras un fallo, anotado en el trial log) +0,37 a +0,50 (falla); **control a priori "etiqueta de t−4"** (fuga de calendario de 1 mes, definida por el mecanismo) falla en las 8 permutaciones. Potencia completa en la tabla de abajo | ok |
| (d) señal plantada | intervalo a priori **[0,20; 0,40]** (simulación del Validador): 0,230; ruido < 0,02; **control positivo con fuga** (dato de t en t): 0,465 > 0,42; linaje en t−1; vintage = primera publicación, latest = revisado | ok |
| (e) lista negra | `assert_no_forbidden` (meta oficial y lista), sin columnas de la etiqueta ni `pers_*`; rechazo de `USREC` y `usrec_lag1` | ok |
| (f) forecast/lookahead | todas las series `observed`; rechazo de GDPPOT; SPF anclado al inicio del trimestre + ≥ 45 días | ok |
| lista blanca | documentación completa; reclasificaciones de GZ, M2 e IPC subyacente; columnas con `desde` vacías antes | ok |

**Potencia honesta de (c) y (d)** (Validador v0.2, `tests/validation/pit_v0_2_power.py`; mismas variables del
placebo en la v0.3):

| prueba | caso | habilidad, media [mín; máx] | ¿lo detecta? |
|---|---|---|---|
| (c) placebo, 8 permutaciones | sin fuga | −0,138 [−0,207; −0,061] | pasa (correcto) |
| | objetivo de t + ruido σ = 0,5 (la del test) | 0,421 [0,370; 0,497] | sí, 8/8 |
| | objetivo de t + ruido σ = 1,0 | 0,071 [0,002; 0,153] | por la media sí; **no** en todas las permutaciones |
| | objetivo de t + ruido **σ ≥ 1,5** | ≤ −0,04 | **no: una fuga débil no se detecta** |
| | **etiqueta de t−4** (fuga de calendario de 1 mes; control del test) | 0,087 [0,030; 0,183] | sí, 8/8 |
| | etiqueta de t−3 / t−1 | 0,20 / 0,59 | sí |
| (d) señal plantada, 20 semillas | calendario correcto (t−1) | 0,279 [0,230; 0,344] | 20/20 en [0,20; 0,40] |
| | fuga de 1 mes (dato de t en t) | 0,542 [0,460; 0,663] | 20/20 > 0,42 |
| | **retardo demasiado corto** en una serie **sin vintages** (calendario 20 d, publicación real 50 d) | 0,304 [0,263; 0,363] | **0/20: pasa inadvertido** |
| | demasiado conservador (t−2) | 0,177 [0,137; 0,214] | a veces (< 0,20) |
| | ruido | −0,005 [−0,019; 0,001] | < 0,02 |

Lectura: el placebo detecta fugas fuertes y fugas de calendario de la etiqueta de ≥ 1 mes, pero **no fugas débiles
(σ ≥ 1,5)**. La señal plantada detecta fugas de un mes entero, pero **no un retardo demasiado corto en una serie sin
vintages**: eso solo lo pueden ver los tests (a)/(v) donde hay una fuente externa. Por eso los supuestos sin fuente
siguen siendo riesgo declarado.

**Límites de los tests:** (a) y (b) prueban la implementación del calendario, no que un supuesto sea correcto. Por eso
el grupo (v) compara con ALFRED donde hay vintages. Los supuestos sin ninguna fuente externa (Filadelfia 1968-90, SPF
antes de 1990, Michigan, Pink Sheet, BIS, GZ/EBP, BoJ, BCE) siguen siendo supuestos documentados.

## 6. Persistencia point-in-time (decisión B, muestra común), solo ≤ 2004

| modo | n | acierto | log-loss blanda |
|---|---|---|---|
| vintage (principal) | 579 (1956-10 → 2004-12) | 61,1 % | 1,300 |
| latest_truncated | 579 (mismos meses) | 63,0 % | 1,182 |

La referencia de la ficha (62,9 %, 1,227 en 595 meses) usa latest_truncated con los 16 meses de 1955-56 que el modo
vintage no puede calcular (falta historia de PAYEMS en sus primeras vintages).

## 7. Limitaciones

1. **Historia reconstruida.** Antes del archivo de vintages, latest_truncated usa datos revisados con fechas correctas.
   Las series que no existían en tiempo real con su definición pasan a condicionales hasta su `principal_desde`: PCE
   subyacente (2000), CFNAI y NFCI (2011), GZ (2012), EBP (siempre), M2 (1980), IPC subyacente y servicios (1978),
   VIX (2003-09-22: VIXCLS 1990-2003 es una reconstrucción; sin empalme con VXO) y, por herencia, toda derivada de
   ellas (`infl_energy_pressure` 1978).
2. **Fechas de existencia no verificadas (supuestos, Validador M-2):** la búsqueda de fuentes primarias no dio
   resultado para ninguna de estas (solo aparecen las series reconstruidas):
   - **servicios sin energía** (`CUSR0000SASLE`, agregado especial): se le aplica el mismo 1978 que al IPC subyacente;
   - **TCU de la industria total**: `tcu_gap` es principal_epoca desde 1976-02 suponiendo que la utilización de la
     industria total se publicaba en tiempo real; pudo empezar después que la de manufacturas (decisión del usuario:
     mantener, o poner `principal_desde` en la fecha que se verifique);
   - **`spf_anxious`**: el nombre del índice es posterior, pero la probabilidad de caída del PIB se preguntaba desde
     1968-T4 (aceptable).
3. **IPC subyacente:** la fecha de primera publicación del agregado "sin alimentos ni energía" **no está verificada** con
   una fuente primaria (las fuentes secundarias solo dicen que la serie empieza en 1957, que es la historia
   reconstruida). Se usa 1978-01 como supuesto prudente del Validador. Hasta 1983 el IPC incluía los intereses
   hipotecarios en vivienda: es lo que se veía en t (no se corrige).
4. **Petróleo administrado antes de 1973** (Texas RRC): `oil_yoy` es casi constante y no debe leerse como "años 60".
5. **Retardos que cambian con la época** (no son fugas, pero el arnés debe tenerlos en cuenta junto a la regla 4):
   - IPC antes de 1972: 32 días de reserva → el modelo ve t−2 (en la realidad, probablemente t−1); desde 1972, fechas ALFRED → t−1;
   - renta personal (W875RX1) en 2000: pasa de 35 días de reserva a las fechas de PCEPI → t−2 → t−1 en ~20 % de los meses;
   - CMRMTSPL: 90 días antes de 2000, 70 en 2000-12 y fechas ALFRED desde 2013;
   - SPF: 90 días antes de 1990-T3 y 50 después.
6. **Empalmes en fechas fijas:** TGA semanal H.4.1 (media de la semana) → saldo diario DTS en 2005-10 (conceptos
   distintos; el a/a cruza el empalme durante 12 meses, dentro del periodo bloqueado); petróleo PPI → WTI en 1987;
   curva T10Y3M en 1982; Baa diario en 1986.
7. **Michigan:** encuesta web desde 2024 (salto de nivel; sensibilidad S-PIT-002). La fuente directa no tiene vintages:
   retardo prudente de 20 días.
8. **El salto revisado → primera publicación** dentro de cada columna en modo vintage puede hacer de reloj (regla 3 del
   arnés).
9. **Supuestos sin fuente externa:** Filadelfia 1968-90 (con variante prudente), SPF antes de 1990 (90 días), Pink
   Sheet, BIS, GZ/EBP, BoJ, BCE.

## 8. Qué quedó fuera

Ver `rechazadas` en la lista blanca (21): USREC, GDPPOT/NROU, probabilidades de recesión de la EBP y de la NY Fed,
prima ACM, Cleveland, TEDRATE, TWEXB, base monetaria, futuros de energía, MPT, derivados (H-DER), STLFSI,
SAHMREALTIME, capa EUR, capas L-CAP (entran sus análogos PIT), Michigan vía FRED, `tcu` en nivel, `infl_composite`,
`bear/bull_steepening` y la segunda línea del Estratega (CCSA, TOTALSA, HOUST). Tampoco: `permit_yoy` sobre la media de
3 meses (H9 del Estratega, no incluida en las 12 correcciones aprobadas), la sorpresa de inflación `infl_surprise_12m`
(v0.3).

## 9. Registro de cambios

### v0.2 → v0.3 (re-auditoría del Validador, `docs/validation/2026-10-15_pit_base_v0.2.md`)

**Sobre la v0.2 en `FROZEN` (I-4).** La v0.2 entró en `FROZEN` antes del veredicto del Validador, al revés de la norma
del proyecto (`src/labels/regime_us.py`: una versión pasa a `FROZEN` tras el veredicto y la aprobación del usuario).
Fue un **error de orden**, sin efecto en los datos (el Validador lo comprobó). La entrada se conserva como registro (sus
ficheros siguen intactos y lo comprueba un test), pero la v0.2 está **sustituida por la v0.3** (`SUPERSEDED`). Desde la
v0.3, las candidatas van en `CANDIDATE`, con sus hashes también en el meta, y pasan a `FROZEN` solo tras el ✅.

| # | cambio | origen | dónde |
|---|---|---|---|
| 1 | **Herencia de `principal_desde` por dependencias**, en código: una derivada entra en el modelo principal desde el `principal_desde` más tardío de todas sus entradas (`effective_principal_desde`; meta `principal_desde_efectivo`). Test con recorrido independiente del grafo. Revisadas todas las derivadas: solo arrastra a `infl_energy_pressure` (→ 1978-01, por `headline_minus_core_6m`) | Validador I-1 | `pit.py`, lista blanca (cabecera), test I-1 |
| 2 | **`vix` condicional antes de 2003-09-22** (definición actual; 1990-2003 es reconstrucción). Sin empalme con VXO | Validador I-2 | lista blanca, test I-2 |
| 3 | **Placebo (c):** control a priori "etiqueta de t−4" (fuga de calendario de 1 mes; falla 8/8). Tabla de potencia honesta (§5): con σ ≥ 1,5 no se detecta; un retardo demasiado corto en una serie sin vintages pasa inadvertido en (d). Las entradas del trial log las añadió el coordinador | Validador I-3 | test (c), §5 |
| 4 | **v0.3 candidata, no congelada:** `CANDIDATE`, `write_candidate` (lista blanca y calendario nuevos sobre la **misma instantánea de datos** de la v0.2, sin releer el warehouse), `SUPERSEDED`; tests de que la versión actual no está en `FROZEN` y de que la v0.2 sigue intacta | Validador I-4 | `pit.py`, tests (h) |
| M-1 | **Parámetros de la etiqueta** desde la etiqueta congelada (`R.PARAMS` + empalme recalculado desde su instantánea), comprobados contra su `meta.json` con hash fijado; test de alteración. **Reproducción** de las 3 matrices (con la variante de Filadelfia) y de los 2 baselines | Validador M-1 | `label_params`, tests (h) |
| M-2 | Fechas de existencia de servicios sin energía, TCU de industria total y `spf_anxious`: **no verificadas**, declaradas como supuestos | Validador M-2 | lista blanca, §7.2 |
| M-3 | **Regla 3 = máximo** de la época medida más antigua; el test usa ahora el máximo, con excepciones documentadas (CMRMTSPL, solo medido con los cierres de 2013+; Filadelfia, una vintage ALFRED que falta en 2015-05). NFCI sube a 12 días (máximo medido): cambian 336 celdas de `nfci`, todas antes de 2011-05, donde es condicional | Validador M-3 | calendario, test, `pit_calendar.md` |
| M-4 | Ventanas mínimas reales de `growth_rt` (108 / 60 meses) y saltos de composición (1973-04, 1981-05) en la regla 3 del arnés; "vintage desde" de las derivadas corregido | Validador M-4 | §3, §4 |
| M-5 | Sin cambios: `umich` ya está en `INGEST_DAILY` (documentación corregida en §1) | Validador M-5 | §1 |
| M-6 | **Adenda de evaluación** (sin editar los preregistros): modelo base, métrica por eje (G: log-loss binaria frente a `p_g_high`; I: frente a `p_i_high`), bootstrap por bloques circular de 12 meses (5.000 réplicas), Holm sobre los 4 módulos, estabilidad 2005-14 frente a 2015+, y criterio de decisión de S-PIT-002 | Validador M-6 | `hypotheses.yaml` (P-EVAL-MOD, P-EVAL-S-PIT-002) |

Efecto en la matriz: frente a la v0.2 solo cambian 336 celdas de `nfci` anteriores a 2011-05 (en los 3 ficheros);
el resto es idéntico, y los baselines también.

### v0.1 → v0.2

| # | cambio | origen | dónde |
|---|---|---|---|
| 1 | **Instantánea congelada** de entradas (observaciones, vintages, catálogo, calendario, lista blanca), SHA-256 en `FROZEN`, solo lectura, copia de respaldo; matriz oficial solo desde ella; tests de hash, de alteración, de reproducción y de ficheros `research/` | Validador G-1, M-5 | `pit.py` (`write_snapshot`, `read_snapshot`, `build_official`), tests (h) |
| 2 | **BCE 8 días** (semana fechada en lunes, publicación el martes siguiente) | Validador I-3 | calendario, test (a) BCE |
| 3 | **Condicionales** antes de su fecha: GZ < 2012, M2 < 1980, IPC subyacente < 1978 (y `core_cpi_*`, `real_ff`, servicios, A8, A9, `infl_core_pressure`); campo `principal_desde` | Validador I-4 | lista blanca, test |
| 4 | **Tests rehechos:** placebo con potencia (falla con fuga), señal plantada con intervalo a priori [0,20; 0,40] y control positivo > 0,42, valores recalculados sin `src.features`, calendario y proxies frente a ALFRED | Validador G-2, I-1, I-2 | `placebo.py`, tests (c), (d), (v) |
| 5 | **`growth_rt`** frente a la mediana de los 120 meses hasta t con escala MAD expansiva; **histéresis** ±0,5 σ y 2 meses de confirmación (0,44 cambios/año) | Estratega H1, H2 | `trend_zmean`, `hysteresis_state` |
| 6 | **Relojes de época:** `copper_gold_6m` desde 1973-01, `usd_neer_yoy` desde 1973-03, nota del petróleo administrado, `tcu` → `tcu_gap`, `umcsent` desde 1978 | Estratega H3, H4 | lista blanca (`desde`), §7 |
| 7 | **Inflación separada:** `infl_core_pressure` (pp) e `infl_energy_pressure` (z); se retira `infl_composite` | Estratega H5 | lista blanca |
| 8 | **A1-A9:** servicios sin energía, salarios, brecha de paro, SPF deflactor (mediana), SPF anxious, `fedpath_1y`, precios pagados de Filadelfia, general − subyacente, dirección de la subyacente | Estratega H6 | lista blanca |
| 9 | **Curva en 4 estados** (bear/bull × steep/flat, 25 pb, tramo dominante); se retiran los 2 flags de la v0.1 | Estratega H7 | `curve_regime` |
| 10 | **PERMIT, CMRMTSPL, NFCI** (y W875RX1, AHETPI, servicios, Filadelfia, Michigan-FRED) con vintages ALFRED en `features/raw/alfred` (cubren los cierres de 2013 y 2025 en PERMIT/CMRMTSPL); `nfci`, `permit_yoy`, `w875rx1_3m_ann`, `cmrmtspl_3m_ann` pasan a modo vintage | Validador I-3, usuario | `alfred_raw.py`, calendario |
| 11 | **Supuestos prudentes:** Michigan con fuente directa (`src/ingest/umich.py`) a 20 d; SPF < 1990 a 90 d; Filadelfia < 1990 con variante prudente t−1 (matriz aparte, S-PIT-001); CMRMTSPL 90 d < 2000; BIS 20 d; además NFCI 7 d y PERMIT 23 d de reserva (p90/máx. medidos) | Estratega C1-C5, Validador I-3 | calendario, `umich.py`, hypotheses.yaml |
| 12 | **Menores:** recuentos corregidos (§4); `supuesto` por tramo (CMRMTSPL < 2013, W875RX1 < 2000, ICSA < 2009, etc.); huecos de `umcsent` eliminados (empieza en 1978); documentados el empalme de la TGA en 2005, el IPC antes de 1972 y la renta personal en 2000 | Validador M-1 a M-6 | calendario, §7 |
| B | Modo principal `vintage`, sensibilidad `latest_truncated`; baselines en la misma muestra; regla de estabilidad del arnés escrita (§3) | usuario | `common_sample`, meta `regla_arnes` |
| C | Preregistro de `net_liq_yoy`, `global_cb_usd_yoy`, `t5yie`, `dfii10` (H-MOD-001 a 004) y de las sensibilidades S-PIT-001/002 | usuario | `research/hypotheses.yaml` |
