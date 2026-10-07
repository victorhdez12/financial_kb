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
