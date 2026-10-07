# FRED extendido + ALFRED vintages

Generado el 2026-10-07. Scripts: `src/ingest/fred_extended.py`, `src/ingest/alfred_vintages.py`
(idempotentes; reutilizan el raw si tiene < 20 h, `--refresh` fuerza la descarga).

```
.venv/bin/python -m src.ingest.fred_extended
.venv/bin/python -m src.ingest.alfred_vintages
```

## Salidas

| capa | ruta | contenido |
|---|---|---|
| raw | `raw/fred_extended/<id>.series.json`, `<id>.observations.json`, `_run_summary.json` | respuestas de la API sin tocar |
| curated | `curated/fred/<series_id>.parquet` + `_catalog.csv` | **362 series** (`date` date32, `value` float64, `series_id`, `source='fred'`) |
| raw | `raw/alfred/<id>.vintages.json` | respuestas ALFRED sin tocar |
| curated | `curated/alfred/<series_id>.parquet` + `_catalog.csv` | 7 series con todas las vintages |

El catálogo FRED trae las columnas del contrato más `requested_id, n_obs, observation_start,
observation_end, seasonal_adjustment, last_updated, notes` (notas recortadas a 400 caracteres).

## Composición de curated/fred (362)

- **59 legacy** de `macro/fred/*.csv`, re-normalizadas desde el CSV (no re-descargadas; el legacy no se toca).
- **111 nuevas** de la lista explícita (`UNIVERSE` en el script).
- **192 ICE BofA (BAML*)** descubiertas con `series/search` (60 US, 8 euro, 124 emergentes): OAS, effective yield, total return.

Por categoría: credit 212 (192 BAML), rates 42, growth 21, employment 16, inflation 11, commodities 11,
fx 10, fiscal 8, markets 8, financial_conditions 7, housing 5, liquidity 4, money 3, gold 2, valuation 2.
Por frecuencia: D 224, M 95, Q 25, W 14, A 4. 0 fallos de descarga.

### Historia larga destacada

| serie | rango | qué es |
|---|---|---|
| M1125AUSM343NNBR | 1871-01 → 1956-12 | índice Cowles/S&P de todas las acciones (NBER) |
| M13001USM156NNBR | 1857-01 → 1970-11 | call money (NBER) |
| M13002US35620M156NNBR | 1857-01 → 1971-12 | commercial paper NY (NBER) |
| M13019USM156NNBR | 1857-01 → 1937-01 | bonos ferroviarios high grade (NBER) |
| M13026USM156NNBR / M13021USM156NNBR | 1900 → 1972 / 1967 | bonos industriales Aaa / índice high grade |
| M1333AUSM156NNBR | 1919-01 → 1944-02 | rendimiento bonos largos del Tesoro |
| M13009USM156NNBR | 1914-11 → 1969-07 | tipo de descuento, Fed de NY |
| M04051USM324NNBR | 1860-01 → 1939-11 | nivel general de precios (NBER) |
| M0892A/B/C (desempleo NBER) | 1929-04 → 1966-12 | tres tramos (1929-42, 1940-46, 1947-66) |
| M1109A/BUSM293NNBR | 1897 → 1968 | Dow Jones industrial (NBER) |
| M1346BUSM156NNBR | 1926 → 1969 | rentabilidad por dividendo NYSE |
| M1476BUSM027NNBR | 1914 → 1946 | stock de oro monetario EE. UU. |
| CPIAUCNS | 1913-01 → | IPC sin desestacionalizar |
| AAA, BAA | 1919-01 → | Moody's |
| FYFSGDA188S, FYONGDA188S | 1929 → 2025 | saldo y gasto federal / PIB |
| TB3MS | 1934-01 → | letra a 3 meses |

## IDs sustituidos o añadidos como alternativa

| pedido | resultado |
|---|---|
| WILL5000INDFC | **no existe** (Wilshire retiró sus índices de FRED en 2024) → `BOGZ1FL073164003Q` (NYSE Composite, Z.1, trimestral 1945+). Añadido `NCBEILQ027S` (valor de mercado de las acciones de empresas no financieras; numerador del ratio de Buffett) |
| M13009USM156NNBR | existe, pero es el **tipo de descuento de la Fed de NY**, no commercial paper. Commercial paper = `M13002US35620M156NNBR`, call money = `M13001USM156NNBR` |
| M1333AUSM156NNBR | existe: rendimiento de los bonos largos del Tesoro 1919-1944 |
| TCMDO | existe, pero es la deuda de **todos los sectores**. Para la deuda no financiera se añade `TCMDODNS` |
| QUSPAM770A | se añaden también QUSCAM770A (total no financiero), QUSHAM770A (hogares) y QUSNAM770A (empresas) del BIS |
| Precio del oro | **no hay ninguna serie viva** (GOLDAMGBD228NLBM/GOLDPMGBD228NLBM retiradas). Proxy: `IR14270` (índice de precios de importación de oro no monetario, 1992+). Precio real → fuente `gold` (otro ingestor) |
| PCOPPNEW (PLAN) | no existe → `PCOPPUSDM` (FMI, 1992+) |
| Paro eurozona | solo `LRHUTTTTEZM156S` (OCDE MEI, **termina en 2023-01**); no hay sustituto vivo en FRED |
| IPC eurozona | `CP0000EZ19M086NEST` (EA19, 1996+) y `CP00MI15EA20M086NEST` (EA20, 1999+) |
| CLI OCDE | vivos: USA, DEU, GBR, JPN, CHN, G7 (`xxxLOLITOAASTSAM`, hasta 2026-08). `EA19LOLITOAASTSAM` termina en 2022-11 |
| Extras | GS2, GS3, GS7, DFII30, THREEFY10, DRALACBS, DRBLACBS, BOGMBASE, FYONGDA188S, FYOIGDA188S, TWEXMMTH, RTWEXBGS, DJIA, IRLTLT01FRM156N |

## Huecos y advertencias (lo que FRED no cubre bien)

- **ICE BofA (BAML*)**: FRED solo sirve los **últimos 3 años** (2023-10-09 en adelante) por licencia. Para spreads largos usar BAA10Y (1986+), BAA/AAA mensual (1919+) y los rendimientos NBER.
- **SP500 y DJIA**: solo 10 años (2016-10 en adelante) por licencia de S&P. Historia larga → Shiller y NBER M1125AUSM343NNBR.
- **Discontinuadas**: TEDRATE (hasta 2022-01), TWEXB (2020-01), TWEXBMTH y TWEXMMTH (2019-12). INTDSRUSM193N (FMI) termina en 2021-08.
- **Materias primas del FMI** (P*USDM, P*INDEXM): solo desde 1992. Historia larga → World Bank Pink Sheet.
- **NROU** incluye proyecciones de la CBO hasta 2036: filtrar `date <= today`.
- **Fechas semanales/diarias**: se conserva la fecha de FRED (semana que termina en sábado para ICSA/CCSA, viernes para NFCI, miércoles para el H.4.1). Para el resto, la fecha es el inicio del periodo, como pide el contrato.
- Tramos NBER: hay solapes y cambios de metodología entre tramos; no empalmar sin ajustar.
- WILL5000INDFC sigue en la lista para documentar el sustituto; cuesta 1 petición fallida por ejecución.

## ALFRED vintages (curated/alfred)

Petición `series/observations` con `realtime_start=1776-07-04&realtime_end=9999-12-31` (output_type=1),
paginada. Formato largo: `date, value, realtime_start, realtime_end, series_id, source='alfred'`.
`realtime_end` es inclusivo y vale NULL si el valor sigue vigente.

| serie | filas | vintages | primera vintage | última |
|---|---|---|---|---|
| GDPC1 | 4.425 | 419 | 1991-12-04 | 2026-09-30 |
| PAYEMS | 13.691 | 860 | 1955-05-06 | 2026-10-02 |
| CPIAUCSL | 3.362 | 669 | 1972-07-21 | 2026-09-11 |
| INDPRO | 39.362 | 1.223 | 1927-01-26 | 2026-09-18 |
| UNRATE | 2.199 | 800 | 1960-03-15 | 2026-10-02 |
| PCEPILFE | 9.167 | 316 | 2000-08-01 | 2026-09-30 |
| CPILFESL | 2.260 | 376 | 1996-12-12 | 2026-09-11 |

```python
from src.ingest.alfred_vintages import as_of
as_of("GDPC1", "2008-10-15")   # última obs. 2008-04-01 (el avance del 3T08 salió el 30-oct)
as_of("UNRATE", "2020-05-09")  # incluye abril 2020 = 14,7 (publicado el 8 de mayo)
```

Comprobado: `as_of("UNRATE","2020-05-01")` termina en 2020-03, y `as_of("PAYEMS","1990-01-01")` termina en 1989-11.

**Huecos de vintages:** antes de la primera vintage, `as_of` devuelve una serie vacía. GDPC1 en ALFRED solo empieza en 1991-12 (antes la medida principal era el PNB real: habría que usar GNPC96/GNP), CPIAUCSL en 1972, CPILFESL en 1996 y PCEPILFE en 2000. Para backtests anteriores hay que usar el Real-Time Data Set de la Fed de Filadelfia o aplicar retrasos de publicación a la serie revisada.
