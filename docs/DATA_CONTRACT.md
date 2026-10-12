# Contrato de datos (curated layer)

Todas las fuentes, sea cual sea su origen, se normalizan a este formato para que el warehouse (DuckDB) las cargue sin código específico.

## Ubicación

```
$FIN_DATA_ROOT/raw/<source_id>/...            # descarga original intacta (xlsx, csv, zip...)
$FIN_DATA_ROOT/curated/<source_id>/<series_id>.parquet
$FIN_DATA_ROOT/curated/<source_id>/_catalog.csv
$FIN_DATA_ROOT/events/<dataset>.parquet       # eventos (guerras, crisis, shocks)
```

`$FIN_DATA_ROOT` = `~/financial_archive` (accesible desde el repo como `data/archive`).

## Series temporales: `<series_id>.parquet`

| columna | tipo | notas |
|---|---|---|
| `date` | date | fecha de la observación (inicio del periodo: 1974-03-01 para marzo 1974; 1974-01-01 para el año 1974) |
| `value` | float64 | NaN si falta |
| `series_id` | string | único globalmente; prefijo por fuente si hay riesgo de colisión (`shiller_cape`, `jst_usa_eq_tr`) |
| `source` | string | `source_id` |
| `realtime_start` | date, opcional | solo vintages (ALFRED): fecha desde la que ese valor era conocido |

## Catálogo: `_catalog.csv` (una fila por serie)

`series_id, source, name, category, frequency (D/W/M/Q/A), units, country, start, end, transform_notes, url, license`

Categorías: `growth, inflation, employment, rates, credit, money, liquidity, fiscal, markets, equity_returns, bond_returns, commodities, gold, fx, housing, valuation, financial_conditions, geopolitics, crisis`.

## Eventos: `events/<dataset>.parquet`

`event_id, name, type (war|banking_crisis|currency_crisis|sovereign_default|market_crash|recession|pandemic|oil_shock|policy|credit_event), country, start_date, end_date, severity (texto o numérico), source, url, notes`

## Reglas

- Scripts de descarga en `src/ingest/<source_id>.py`, idempotentes, ejecutables con `.venv/bin/python -m src.ingest.<source_id>`.
- Claves en `.env` (python-dotenv). Nunca imprimir claves en logs.
- No reescribir datos ya existentes en `macro/fred`, `macro/bls` ni `sec/` (legacy); las capas nuevas van en `raw/` y `curated/`.
- Licencias: uso personal/investigación; anotar la licencia en el catálogo.

## Metadatos que añade el warehouse (2026-10-12)

`src/warehouse/build.py` enriquece la tabla `catalog` (no hace falta escribirlos en `_catalog.csv`):

| columna | regla |
|---|---|
| `pit_role` | `observed` (por defecto), `forecast` (proyecciones: `*_proj`, `transform_notes` que empieza por `FORECAST`, `NROU`) o `lookahead` (el valor en t usa información posterior a t: `shiller_fwd10y_*`, `nyfed_recprob_target`). Reglas en `PIT_RULES`. **Toda fuente nueva con previsiones o look-ahead debe cumplir una de estas reglas o añadir la suya.** |
| `country_iso3` | `country` normalizado a ISO3 (acepta ISO3, ISO2 o nombre en inglés). Agregados: `EA`, `EU`, `WLD`, `G7`, `G20`, `OECD`, `EM`, `ADV`, `EMDE`. NULL si no se reconoce (grupos BIS, regiones). |

Además:
- `catalog` tiene una fila por `series_id`. Si una serie aparece en varias fuentes, gana la fuente curada, después `alfred` y por último la legacy.
- `obs_latest` solo contiene series `observed` y fechas ≤ fecha de construcción. Las demás están en la vista `forecasts`.
- `observations.realtime_end` se conserva para hacer consultas point-in-time en SQL.
- Las series anuales con fecha distinta del 1 de enero (años fiscales de FRED, 30-jun/30-sep) se fechan al 1 de enero de ese año.
- Un mes ausente en una serie mensual (p. ej. IPC oct-2025) se queda como hueco. El clasificador reindexa al calendario completo (`src/regime/features.py: regularize`) antes de calcular variaciones, así que nunca hace una variación interanual de 13 meses.
- Las series sin publicar durante más de `MAX_STALE_DAYS` (`src/regime/asof.py`) dejan de votar en el clasificador.
