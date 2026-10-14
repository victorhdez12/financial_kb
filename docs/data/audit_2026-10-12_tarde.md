# Reauditoría de datos — 2026-10-12 (tarde)

Actualiza `audit_2026-10-12.md`, que se escribió por la mañana antes de las ingestas nuevas y de las correcciones. El CSV `audit_2026-10-12_series.csv` corresponde ya a esta pasada (`.venv/bin/python -m src.audit.run`, unos 110 s).

## Resultado

| | mañana | tarde |
|---|---:|---:|
| series en el warehouse | ~3.700 (con un 52 % de las fuentes base sin cargar) | **9.623** (todas las fuentes curadas) |
| hallazgos CRÍTICA | 3 | **0** |
| hallazgos ALTA | 262 | **28** (todos explicados abajo) |
| MEDIA / BAJA | 1.131 / 1.775 | 1.980 / 2.899 (más series; no revisadas una a una) |

## Corregido hoy

1. **Fallo del IPC/paro de oct-2025** (antes CRÍTICA).
   - **Arreglo:** `src/regime/features.py: regularize()` reindexa las series M/Q/A al calendario completo antes de calcular `yoy`, `ann6m`, `d12`, `qoq_ann` y Sahm, tanto en la ruta normal como en la de ALFRED. Sahm tolera un mes ausente (3m con `min_periods=2`, mínimo de 12m con `min_periods=11`).
   - **Efecto en sep-2026:** inflación interanual de 2,76 a **2,45 %**; tipo real fed funds de 0,99 a **1,30 pp**; subyacente 6m de mar-2026 de 3,05 a 2,73 %.
   - **Cuadrantes:** no cambia ningún mes de los 922.
   - **Auditoría:** `src/audit/classifier_gaps.py` comprueba ahora el cálculo real del clasificador, así que volverá a saltar si alguien quita `regularize`.
2. **Base de datos desfasada** (antes CRÍTICA). Reconstruida con todas las fuentes. `build.py` ahora:
   - deja una fila por `series_id` en `catalog` (curada > alfred > legacy);
   - añade `pit_role` (478 `forecast`, 4 `lookahead`), que se excluyen de `obs_latest` y van a la vista `forecasts`;
   - añade `country_iso3` (97 % de las series);
   - añade `realtime_end`;
   - fecha las series fiscales anuales al 1 de enero;
   - convierte `monthly` en tabla.
3. **TEDRATE**, discontinuada en 2022 y que seguía votando en verde. `asof_on_grid` descarta los valores de más de `MAX_STALE_DAYS` (D/W 45, M 120, Q 250 y A 550 días). El semáforo de crédito pasa a 9 indicadores y TED sale "sin dato".
4. **Oro a precio fijo en los análogos.** `src/report/analogs.py` solo usa las rentabilidades del oro desde 1971-08 y el reporte lo explica en una nota.
5. **Look-ahead sin marcar.** Ahora `pit_role` lo marca (ver `DATA_CONTRACT.md`).
6. **Vintages ALFRED.** Las 14 están cargadas. TCU, CFNAI, M2SL y GDP usan ahora `vintage=True`, lo que cambia 39 meses de liquidez, todos con la puntuación cerca del umbral ±0,5. Hoy la liquidez pasa de neutral (−0,49) a **escasa (−0,51)**.
7. **IMF COFER.** Se descartan las series de economías avanzadas y emergentes porque la API solo da 1999. Los ceros de los niveles en USD pasan a NaN. Quedan 22 series del total mundial.
8. **Valores 9999** (código de dato faltante) en `fred_us/H1RIFSPABM03NWF`: ahora son NaN (`fred_us.drop_sentinels`). `DALLCCACBEP = 9999` en 1996-07 es un **valor real** (millones de USD, entre 8.758 y 10.996), así que el aviso que queda es un falso positivo.
9. **Ceros en `oecd_share_bra`** (105): ahora son NaN. `oecd._series(zero_is_missing=True)` en los índices.

## Hallazgos ALTA que quedan (28), y por qué no son errores

| fuente | n | motivo | tratamiento |
|---|---:|---|---|
| wb_pinksheet | 16 | tramos constantes en los años 60-70: precios oficiales de petróleo, aluminio, potasa y oro | son históricos y reales; no usar como precio de mercado antes de ~1973 |
| gold | 8 | oro a 20,67 $ y 35 $ (precio oficial) | real; los análogos ya lo excluyen antes de 1971-08 |
| shiller | 3 | `shiller_fwd10y_*` (look-ahead) | marcadas como `pit_role=lookahead`, fuera de `obs_latest` |
| fred_us | 1 | DALLCCACBEP = 9999 | valor real (ver punto 8) |

## Pendiente (MEDIA, no bloquea)

- **`BOGZ1FL073164003Q`:** el catálogo dice "Percent" pero es un índice, con un salto ×10 en 1952-01.
- **`nber_m12014`:** 1915 viene dividido por 10.
- **`shiller_gs10`:** 2019-07 vale 1,63 frente a 2,06 en FRED.
- **`wb_rice_thai_25`:** valores a 0 de mar a jun de 2008, que deberían ser NaN. Hay que limpiarlo en `wb_pinksheet.py`.
- **`M1SL`:** ruptura de definición en 2020-05. Es real, pero hay que anotarla y evitar la variación interanual en 2020-21.
- **Eventos:** el tipo `inflation_crisis` no está en el contrato, y `cow_extra_321` tiene `end < start`.
- **`maddison/_catalog.csv`:** 7 filas duplicadas. La base de datos ya las deduplica, pero el CSV sigue así.
- **rtdsm** (tiempo real de la Fed de Filadelfia): cargado, pero sin conectar al clasificador.
- **MEDIA de las fuentes nuevas:** sin revisar una a una, sobre todo `fred_us` (563, en su mayoría huecos y series discontinuadas de releases antiguas) e `imf_weo` (478, las previsiones ya marcadas).

## Semáforo por fuente (tarde)

| semáforo | fuentes |
|---|---|
| 🟢 verde | warehouse, boe_millennium_uk, damodaran, gpr, jst_macrohistory (solo uso no comercial), ken_french, sipri, spf, ecb, eurostat, bde, ine, bundesbank, bis_ext, oecd, imf_weo (con las previsiones marcadas), imf_gdd, imf_hpdd, wb_wdi, fed_yieldcurve, us_treasury, nyfed_hhdc, shiller_housing, measuringworth |
| 🟠 ámbar | fred (BOGZ, M1SL), fred_us (MEDIA sin revisar), alfred (cobertura desde 1972/1991/1996), bis, maddison, nber_macrohistory, nyfed, rtdsm, shiller, wb_pinksheet, gold (uso correcto solo desde 1971), imf_cofer (solo el total mundial), us_hist_labor (Romer/Coen, sin Lebergott) |
| 🔴 rojo | — |
