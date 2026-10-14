# Huecos Europa/FMI - INE retrospectivo e IFS del FMI (2026-10-13)

Agente de datos "Huecos Europa/FMI", rama `fase-datos`. Scripts: `src/ingest/ine.py` (ampliado, solo se añaden series) y `src/ingest/imf_ifs.py` (fuente nueva `imf_ifs`). Ambos son idempotentes: `.venv/bin/python -m src.ingest.ine` y `.venv/bin/python -m src.ingest.imf_ifs [--refresh]`.

## Resumen

| fuente | series nuevas | observaciones | cobertura |
|---|---|---|---|
| `ine` (ya existía, 13 -> 60 series) | 47 | 7.580 | EPA 1976T3-2026T2; IPC desde 1961-01 |
| `imf_ifs` (nueva) | 305 | 187.036 | 22 países, 1914-2026 según serie |

Huecos: ver al final.

## 1. EPA 1976-2001 (INE)

**El API Tempus no sirve la EPA anterior a 2002** (las 1.039 tablas de la operación EPA empiezan en 2002). La serie retrospectiva oficial está en un Excel del INE: `https://ine.es/epa02/series76_01.xls` (página `https://ine.es/epa02/repercusion_nacio7601.htm`). Se guarda intacto en `raw/ine/series76_01.xls` y se lee con `xlrd` (ya instalado en el venv).

Contenido: 3T 1976 - 4T 2001, trimestral, sin desestacionalizar, "datos publicados" y "datos reponderados" (reponderados con las proyecciones de población posteriores a 2001). Usamos los **reponderados** como serie principal; la tasa de paro total "tal como se publicó" se guarda aparte.

Importante: **la definición de paro es la antigua** (pre-2002). En 2002 el INE cambió la definición (EPA-2002, para armonizar con Eurostat) y la nueva lee más baja. El INE publicó en 2005 un documento de enlace 1976-2000 (`https://ine.es/daco/daco42/daco4211/epa_reest_paro.pdf`, método probit) pero **no he encontrado las series numéricas enlazadas descargables** (el PDF solo trae el método y las probabilidades). Es un hueco abierto: el empalme que se entrega es un empalme de niveles **sin ajuste**, con la ruptura anotada.

Series (todas con `country=ES`, frecuencia `Q`, fecha = inicio del trimestre):

- `ine_epa76_<var>_<t|m|f>_q`: 1976T3-2001T4 (reponderadas, definición antigua). `<var>` = `unemp_rate`, `act_rate`, `activos`, `ocupados`, `parados`; t = ambos sexos, m = varones, f = mujeres. 15 series, más `ine_epa76_unemp_rate_published_t_q` (tasa total como se publicó).
- `ine_epa_<var>_<t|m|f>_q`: 2002T1-2026T2 desde Tempus (base 2021). 14 series nuevas (`ine_epa_unemp_rate_q` ya existía; es el total).
- `ine_epa_<var>_<t|m|f>_linked_q`: 1976T3-2026T2 empalmadas (15 series). Ruptura en 2002T1 anotada en `transform_notes`.

Unidades: tasas en %, niveles en miles de personas.

### Comprobaciones

- Paro España 1994 (reponderado): 24,6 / 24,2 / 23,8 / 23,9 % (T1-T4). Esperado ~21-24 %: correcto.
- Paro España 1976T3: 4,4 %; máximos de los años 80-90 coherentes con la historia conocida.
- Empalme en 2001T4 -> 2002T1: 12,75 % -> 11,55 % (parados 2.354,8 -> 2.152,8 miles). Parte de ese salto de ~1,2 pp es la **ruptura de definición**, no el ciclo.
- Ocupados 1976T3: 12.777 mil; 2026T2: 22.779 mil.
- 200 trimestres en la serie empalmada y sin huecos (el salto máximo entre fechas es de 92 días).

## 2. IPC del INE anterior a 2002

- `ine_ipc_yoy_m` ya cubría 1962-2026 (tasa anual oficial); no se toca.
- **Tempus solo sirve el índice general (base 2021) desde 2002** (tabla 24077 "series desde 1961" devuelve 296 obs). No hay índice subyacente anterior a 2002 en Tempus (`IPC292510/11` empiezan en 2002).
- Nueva `ine_ipc_mom_m` (IPC290752): variación mensual oficial desde 1961-02 (788 obs).
- Nueva `ine_ipc_index_linked_m`: índice general 1961-01 a 2026-08 (788 obs, base 2021=100). 2002+ = INE Tempus; 1961-2001 = `bde_es_cpi_m` x 0,788847.

### Solape con `bde_es_cpi_m`

En los 296 meses de solape, el cociente INE/BdE es constante (0,788803-0,788892; max/min - 1 = 1e-4), es decir, `bde_es_cpi_m` es el propio índice enlazado del INE en otra base. El empalme es un cambio de base, no un empalme de dos fuentes. Además, la tasa anual calculada con el índice enlazado coincide con la oficial `ine_ipc_yoy_m` con diferencia media de 0,046 pp; el único tramo discrepante es ene-sep 2002 (hasta 1,3 pp, artefacto del cambio de base 2001/2002; para 2002 usar `ine_ipc_yoy_m`). `bde_es_cpi_m` empieza en 1954-03, antes que el INE (1961).

Comprobación: IPC España 1977: tasa anual 22,2 % (ene) - 28,4 % (ago), 26,4 % en diciembre. Esperado ~24-26 %: correcto (el FMI da 26,39 % en dic-1977).

## 3. IFS del FMI (`imf_ifs`)

### Estado del API

- `dataservices.imf.org` (JSON RestData) está desmantelado. El nuevo API es **`https://api.imf.org/external/sdmx/3.0/`**, **sin clave** (el mismo que usa `imf_weo`).
- **No existe un dataflow "IFS".** Su contenido se ha repartido en dataflows temáticos de `IMF.STA`: `CPI` (v5.0.0), `ER` (4.0.1), `MFS_IR` (9.0.0), `MFS_MA` (10.0.1), `MFS_DC` (8.0.0), `MFS_CBS` (24.0.0), `IL` (13.0.1), `MFS_FMP` (3.0.0; solo índices bursátiles, no se usa).
- Se piden CSV SDMX 2.0 por país y dataflow (clave `PAÍS.INDICADOR.…`). Raw intacto: `raw/imf_ifs/<flow>_<ISO3>.csv`.
- `OBS_VALUE` ya viene en unidades completas (SCALE es solo metadato de visualización; comprobado: reservas de EE. UU. 1950 = 24.076.419.999 USD). Los importes se guardan en **millones**.

### Países (22)

G20 sin la UE (ARG, AUS, BRA, CAN, CHN, FRA, DEU, IND, IDN, ITA, JPN, KOR, MEX, RUS, SAU, ZAF, TUR, GBR, USA) más ESP, CHE, NLD. Series `imf_ifs_<iso3>_<corto>`, mensuales.

### Series (305 en total)

| corto | qué es | países | desde | notas |
|---|---|---|---|---|
| `cpi_ix`, `cpi_yoy` | IPC general, índice y variación anual | 22 | 1914 (EE. UU.) / 1954 (ESP) | índice en base nacional |
| `fx_usd_avg`, `fx_usd_eop` | moneda local por USD, media y fin de periodo | 21 (todos menos EE. UU.) | 1957 | sin rebasar cambios de moneda; ESP acaba en 1998 (euro) |
| `rate_policy` | tipo oficial de política monetaria | 13 | 1969-07 | |
| `rate_discount`, `rate_refi` | tipo de descuento / refinanciación | 5 / 1 | 1950 / 1985 | |
| `rate_moneymkt` | tipo del mercado monetario | 13 | 1954-07 | |
| `rate_tbill_yield`, `rate_govbond` | rendimiento de letras / bonos del Estado | 9 / 14 | 1950 | |
| `rate_deposit`, `rate_lending` | tipos de depósito / préstamo | 14 / 14 | 1953 / 1950 | |
| `money_base_nd` | base monetaria, definición nacional (MFS_MA) | 10 | 1950 (EE. UU. 1959-2017) | el reporte termina cuando el país deja de enviarla |
| `money_broad_ma` | dinero amplio (MFS_MA) | 12 | 1998 | |
| `money_broad_dc` | dinero amplio, depository corporations (SRF) | 13 | 2000-12 | |
| `monbase_cbs` | base monetaria, balance del banco central (SRF) | 13 | 2000-12 | |
| `res_total_gold_mv`, `res_ex_gold`, `res_gold_nv`, `res_gold_oz` | reservas internacionales (con oro a mercado, sin oro, oro a valor nacional, onzas) | 22 | 1950-12 | millones de USD / millones de onzas |

Por categoría del catálogo: liquidity 88, rates 83, money 48, inflation 44, fx 42. `rate_policy` existe para ARG, AUS, BRA, CAN, CHE, IDN, JPN, KOR, MEX, RUS, TUR, USA y ZAF.

### Comprobaciones

- IPC España, tasa anual dic-1977 = 26,39 %; coincide con INE (26,4 %).
- Reservas de EE. UU. 1950-12 = 24.076 M USD (correcto); 2026-08 = 1.437.000 M USD (con oro a precio de mercado).
- Reservas de China sin oro 2026-06 = 3,48 billones de USD (correcto).
- JPY/USD 1957 = 360,0 (paridad de Bretton Woods).
- Base monetaria EE. UU. 1959-01 = 40.656 M USD (correcto).
- Dinero amplio de Japón 2026-05 = 1.637.180.900 M JPY, es decir, 1.637 billones de yenes (correcto para M3).
- Tipo oficial de Japón 2006-2025 pasa de 0,0 a 0,5 %; EE. UU. termina en oct-2025 (3,875 %): el reporte al FMI de algunos países va con retraso.
- Sin fechas futuras; NaN eliminados con `dropna`; ceros puestos a NaN en índices, tipos de cambio, dinero y reservas.

### Huecos de IFS

1. **Dinero amplio y base monetaria antes de 2001 salvo definiciones nacionales:** el IFS clásico (M1/M2/M3 mensual desde los años 50-60) no se ha migrado a los dataflows nuevos. Las series SRF (`money_broad_dc`, `monbase_cbs`) empiezan en 2000-12 y `money_base_nd` / `money_broad_ma` solo existen para unos 10-12 países. Para historia larga de dinero hay que usar otras fuentes (BCE para la zona euro, FRED para EE. UU., JST, Bundesbank).
2. **Zona euro como agregado:** no se pide (los países del euro aparecen individualmente y sus tipos oficiales son los del BCE; ver fuente `ecb`). Los tipos de política de ESP, DEU, FRA, ITA y NLD no aparecen tras 1999; los bonos y letras sí.
3. **Tipos oficiales:** `rate_policy` solo para 13 de 22; no hay tipos oficiales para algunos países (sin `rate_policy`: GBR, CHN, IND, SAU y los países del euro ESP, DEU, FRA, ITA, NLD). Se cubren con `bis`, `ecb` y `boe_millennium_uk`.
4. **IPC subyacente (`CCPI`):** la consulta al dataflow `CPI` no devuelve ningún país del conjunto, así que no hay series `cpi_core_*` en `imf_ifs`.
5. **Frecuencia:** solo mensual. No se piden las variantes trimestral y anual (existen en el API).
6. **No es un vintage del IFS:** el API devuelve la última versión del dato. No hay histórico de revisiones.
7. Series con `MFS_MA` de EE. UU. terminan en 2017-06 (`money_base_nd`).

## Huecos pendientes (resumen)

- EPA 1976-2001 con definición EPA-2002 (series enlazadas del INE de 2005): no encontradas en formato numérico. Se entrega el empalme sin ajuste.
- Desglose de la EPA por edad anterior a 2002 y por comunidad autónoma: el Excel `series76_01.xls` solo trae el total nacional por sexo. Existe la versión por CCAA en `repercusion_ccaa7601.htm` (no ingerida).
- IPC subyacente INE anterior a 2002: no está en Tempus.
- IFS: dinero amplio / base monetaria mensual anterior a 2001 para la mayoría de países (ver arriba).
- Los agregados monetarios y balances de bancos centrales (Fed, BoJ, BoE, PBoC, SNB) los cubre otro agente; aquí no hay duplicación (IFS aporta solo series por país del FMI, en moneda local).

## Qué cambiar en `src/warehouse/build.py` (no tocado)

1. **Nada obligatorio**: `curated_frames()` descubre `curated/*/*.parquet`, así que `imf_ifs` y las series nuevas de `ine` se cargan solas. `country` es ISO3 y se normaliza sin cambios.
2. `PIT_RULES`: sin cambios (nada de `imf_ifs` ni de las series INE nuevas es previsión ni look-ahead). Las series EPA retrospectivas son datos reponderados a posteriori por el INE: están marcadas en `transform_notes`, pero no son estrictamente "tal como se conocían entonces" (point-in-time) y se pueden tratar como `observed`.
3. Dedupe de catálogo: `ine_ipc_index_linked_m` y `ine_epa_*_linked_q` solapan en contenido con sus componentes (`ine_ipc_index_m`, `bde_es_cpi_m`, `ine_epa76_*`, `ine_epa_*_q`), pero con distinto `series_id`; no hay colisiones de id.
4. Sugerencia para el clasificador (`src/regime`, fuera de mi alcance): usar `ine_epa_unemp_rate_t_linked_q` si se quiere paro de España desde 1976, sabiendo que la ruptura de 2002 es de definición.

## Para la checklist del auditor

- Fuente `ine` (60 series) e `imf_ifs` (305 series) reescritas con `CatalogWriter`: columnas del contrato, `series_id` únicos con prefijo, licencia y unidades en el catálogo, empalmes anotados en `transform_notes`.
- Raw intacto: `raw/ine/series76_01.xls`, `raw/ine/*.json`, `raw/imf_ifs/<flow>_<ISO3>.csv`.
- Licencias: INE (reutilización con atribución); FMI (reutilización con atribución, términos del FMI).
