# Datos internacionales: fuentes multilaterales y globales

Generado el 2026-10-12. Todo sigue `docs/DATA_CONTRACT.md`: el raw se guarda intacto en `$FIN_DATA_ROOT/raw/<source_id>/` y cada serie va en un parquet propio en `$FIN_DATA_ROOT/curated/<source_id>/<series_id>.parquet` (columnas `date, value, series_id, source`), con su `_catalog.csv`. Los scripts son idempotentes: `.venv/bin/python -m src.ingest.<source_id> [--refresh]`. Usan el helper `_extlong_common.py` y, sin `--refresh`, reutilizan la caché del raw (20 h o más).

| source_id | Script | Series | Cobertura | Frec. | Licencia |
|---|---|---|---|---|---|
| `bis_ext` | `bis_ext.py` | 366 | 1662 → 2026-09 | M / Q / A | BIS, reutilización con atribución |
| `oecd` | `oecd.py` | 309 | 1914 → 2026-09 | M | OECD, CC BY 4.0 |
| `imf_weo` | `imf_weo.py` | 955 (478 históricas + 477 de previsión) | 1980 → 2031 | A | IMF, reutilización con atribución |
| `imf_hpdd` | `imf_hpdd.py` | 31 | 1800 → 2015 | A | IMF; citar a Abbas et al. (2010) |
| `imf_gdd` | `imf_gdd.py` | 155 | 1950 → 2024 | A | IMF; citar a Mbaye et al. (2018) |
| `wb_wdi` | `wb_wdi.py` | 375 | 1960 → 2025 | A | CC BY 4.0 (World Bank) |
| `measuringworth` | `measuringworth.py` | 16 | 1209 → 2025 | A | MeasuringWorth, uso no comercial con cita |

En total son **2.207 series nuevas**, sin colisiones de `series_id` con el resto de `curated/`. La columna `country` usa ISO3 para los países y estos códigos para los agregados: `EA` (área euro), `WLD`, `ADV`, `EMDE`, `G7`, `OECD`, `LMY` y los códigos BIS o OCDE cuando el agregado es propio de la fuente.

**Criterio de selección.** El raw se guarda completo, pero solo se curan las economías principales: EE. UU., área euro, DEU, FRA, ITA, ESP, NLD, GBR, JPN, CHN, CAN, CHE y AUS, el resto del G20 (KOR, IND, BRA, MEX, RUS, ZAF, TUR, IDN, SAU, ARG) y agregados. Hay dos excepciones: el CLI y la confianza de la OCDE (todas las áreas publicadas) y la deuda histórica del FMI (ver §4).

## 1. BIS, ampliación (`bis_ext`)
`bis_ext` es un `source_id` distinto de `bis`, porque `cycle_bis.py` borra los parquets que no genera él mismo en `curated/bis`. Antes de crearlo revisé lo que `bis` ya tenía:
- Credit-to-GDP gap, ratio y tendencia (`bis_creditgap_*`).
- DSR (`bis_dsr_*`).
- Crédito total, del total de sectores y de los bancos, al sector privado no financiero, hogares, empresas y gobierno, en % del PIB (`bis_tc_*`, donde `_pb_` es crédito bancario y `g` es deuda pública).
- Precios de vivienda nominales y reales (`bis_spp_*`).
- Tipos oficiales (`bis_cbpol_*`).

Todo eso ya existía y no se ha tocado. Lo que añade `bis_ext`:

| Prefijo | Dataset | Contenido |
|---|---|---|
| `bis_eer_<cty>_neer_m` / `_reer_m` (y `_narrow_m`) | WS_EER | Tipo de cambio efectivo nominal y real (deflactado por IPC), media mensual, 2020=100 (subida = apreciación). Cesta amplia (64 economías) para 23 economías desde 1994 y cesta estrecha (27 economías) para 14 desde 1964 (`_narrow`). |
| `bis_gli_<moneda>_<prestatario>_<códigos>_<unidad>` | WS_GLI | **Liquidez global**: crédito en USD, EUR y JPY a no residentes (préstamos bancarios y bonos), en millones, % del PIB y % interanual. Abarca agregados mundiales, EME y regiones, y los principales emergentes. 225 series trimestrales desde 2000. |
| `bis_cpi_<cty>_idx_m` / `_yoy_a` | WS_LONG_CPI | IPC largo: índice mensual 2010=100 e inflación anual. EE. UU. empieza en 1913/14, GBR tiene inflación anual **desde 1662** y NLD desde 1901. |
| `bis_xru_<cty>_<cur>_m` | WS_XRU | Unidades de moneda nacional por USD (media mensual). GBP desde 1791. Los países del euro aparecen en EUR, con la historia convertida al tipo irrevocable. |

En `bis_gli`, los códigos del id (`naib` = prestatario no bancario, prestamista total, cross-border y local en divisa, crédito total) se explican en `name` y en `transform_notes`.

Comprobaciones: IPC de EE. UU. en 1980 = 13,55 % (correcto); crédito en USD a no bancos fuera de EE. UU. en 2026T1 = 14,7 billones de USD (BIS publica unos 14 bn); REER del área euro, 2020-06 = 101.

## 2. OCDE (`oecd`)
Se usa la API SDMX de Data Explorer (`sdmx.oecd.org`) y cada consulta se guarda como un CSV completo en raw. La API limita a unas 20 consultas por hora, y el script hace solo 4 y las cachea 20 h.

| Prefijo | Flujo | Contenido |
|---|---|---|
| `oecd_cli_<area>` | DF_CLI, LI/AA | Indicador compuesto adelantado, con amplitud ajustada, de **todas las áreas** (22, incl. G7, G20, OECD, EA20, CHN, IND, BRA). |
| `oecd_bci_*`, `oecd_cci_*` | DF_CLI, BCICP/CCICP | Confianza empresarial (55 áreas) y del consumidor (51). |
| `oecd_unemp_<area>` | DF_IALFS_UNE_M | Paro armonizado, 15+, desestacionalizado (16 áreas; EE. UU., CAN y JPN desde 1955). |
| `oecd_ir3m_*`, `oecd_irlt_*`, `oecd_ircall_*` | DF_FINMARK | Tipo a 3 meses, bono a 10 años y tipo a un día (medias mensuales). |
| `oecd_share_*` | DF_FINMARK | Índice de cotizaciones, 2015=100. |
| `oecd_cpi_<area>_idx/_yoy`, `oecd_cpicore_*` | DF_PRICES_ALL | IPC general y subyacente (sin alimentos ni energía), índice y tasa interanual, sin desestacionalizar, metodología nacional. |

Comprobaciones: paro de EE. UU. en 2020-04 = 14,8 %; bono a 10 años de EE. UU. en 1981-09 = 15,32 %; IPC de España en 2022-07 = 10,8 %; CLI de EE. UU. en 2026-05 = 100,65.

## 3. FMI, World Economic Outlook (`imf_weo`)
- **Fuente.** Se usa la API SDMX 3.0 de `api.imf.org`, dataflow `IMF.RES/WEO`. Es la vintage **publicada el 2026-04-14** (WEO de abril de 2026); la de octubre de 2026 aún no estaba en la API. El raw guarda el WEO completo, 8.197 series y 361.733 observaciones (210 economías × 145 indicadores, incl. precios de materias primas), y la estructura con los códigos.
- **Indicadores curados.** Para 27 economías y agregados:
  - Actividad: crecimiento real, PIB en USD y PPP, peso en el PIB mundial, PIB per cápita PPP y output gap.
  - Precios y empleo: inflación media y de fin de periodo, y paro.
  - Cuentas públicas: deuda bruta y neta, saldo total, primario y estructural, ingresos y gasto.
  - Sector exterior: cuenta corriente, ahorro e inversión.

  `NGDPD` y `PPPGDP` se dividen entre 1e9 (miles de millones).
- **Previsiones separadas.** `imf_weo_<iso>_<ind>` contiene los años anteriores al de publicación (≤2025) e `imf_weo_<iso>_<ind>_proj` los años ≥2026, que son **previsión**. En `transform_notes`, las primeras empiezan por `REALISED/ESTIMATE` y las segundas por `FORECAST`, y el nombre lleva `[PROJECTION]`.
- **Limitación.** La API no publica el campo de WEO *estimates start after* (`LATEST_ACTUAL_ANNUAL_DATA` viene vacío), así que el último año histórico (2025) puede ser una estimación del FMI en algunos países. Las previsiones son de una sola vintage: no hay histórico de vintages, aunque la API ofrece flujos `WEO_<año>_<mes>_VINTAGE` desde 2025.
- Comprobaciones: PIB de EE. UU. en 2025 = 30,77 bn USD; deuda de Japón en 2024 = 214 % del PIB; paro de España en 2025 = 10,5 %.

## 4. FMI, deuda (`imf_hpdd`, `imf_gdd`)
- **HPDD** (`imf_hpdd_<iso>_debt_gdp`): deuda bruta de las administraciones públicas en % del PIB, de **1800 a 2015** (base congelada en 2015). Se curan las economías principales y además cualquier país cuya serie empiece antes de 1914, lo que da 31 series (GBR, USA y SWE desde 1800; NLD desde 1814). El raw contiene los 191 países. En algunos tramos la serie cubre el gobierno central en lugar del general (ver notas del FMI). Comprobaciones para 1946: GBR 270 % y USA 121 %; Japón en 1944, 204 %.
- **Global Debt Database** (`imf_gdd_<iso>_<indicador>`): deuda privada total, de hogares, de empresas no financieras, pública, del gobierno general y del central, en % del PIB, de 1950 a 2024, con dos variantes: todos los instrumentos o solo préstamos y valores. Abarca 22 países. Comprobación: deuda de los hogares de EE. UU. en 2024 = 71 % del PIB.

## 5. World Bank WDI (`wb_wdi`)
Se usa la API v2 y se guarda un JSON por indicador en raw. Se cubren 26 economías y agregados: G20 + ESP, NLD, CHE, EA (EMU), WLD, OECD y LMY. Hay 16 indicadores: crecimiento, PIB en USD, PIB per cápita PPP, población, IPC, deflactor, paro (estimación modelizada de la OIT), crédito doméstico del sector financiero, crédito al sector privado (total y bancario), tipo real, cuenta corriente, comercio sobre PIB, reservas (en USD y en meses de importaciones) y deuda del gobierno central. Los `series_id` siguen el formato `wdi_<iso>_<código con _>`, por ejemplo `wdi_usa_fp_cpi_totl_zg`. Comprobaciones: inflación de EE. UU. en 1980 = 13,5 %; crecimiento de China en 2007 = 14,2 %.

## 6. Historia larga: MeasuringWorth (`measuringworth`)
- **Tipos de interés** (`mw_<us|uk>_rate_<long|short_ordinary|short_surplus>_<consistent|contemporary>_a`): Reino Unido desde 1729 (largo plazo) y EE. UU. desde 1798 (largo) y 1831 (corto), hasta 2025. La versión *consistent* homogeneiza el concepto a lo largo del tiempo y la *contemporary* recoge la cotización de cada época.
- **Precios y salarios.**
  - `mw_us_cpi_a`: IPC de EE. UU. desde 1774 (1982-84=100), con la inflación derivada en `mw_us_cpi_inflation_a`.
  - `mw_uk_rpi_a`: RPI del Reino Unido desde 1209 (2010=100). Prolonga hasta 2025 la serie de BoE, que termina en 2016.
  - `mw_uk_avg_earnings_a`: salario nominal medio.
- Comprobaciones: CPI de EE. UU. en 2024 = 313,7; tipo largo de EE. UU. en 1981 = 14,2 %.
- El precio del oro de MeasuringWorth ya está en `gold`.

## 7. Revisado sin cambios
- **JST Macrohistory**: macrohistory.net sigue ofreciendo solo la **R6**, que ya está en `jst_macrohistory`. No hay versión nueva.
- **Reinhart-Rogoff**: las crisis y los defaults ya están como eventos (`events_financial_crises.py`, a partir de `raw/financial_crises/20160923_global_crisis_data.xlsx`). La deuda pública larga queda cubierta por HPDD.
- **Global Financial Data**: es **de pago** y no se ha usado.

## 8. Huecos pendientes
- **IFS del FMI**: ya no existe como base única. El FMI la ha dividido en flujos `IMF.STA` (MFS_IR, MFS_MA, CPI, ER, EER, BOP...), todos accesibles con la misma API y el parser de `imf_weo.py` (`parse_sdmx_json`). No se han curado porque BIS y OCDE cubren tipos, IPC y tipos de cambio. Si hicieran falta, M2 o reservas por país vendrían de `MFS_MA`.
- **WEO de octubre de 2026**: se publica hacia mediados de octubre. Hay que volver a ejecutar `imf_weo` y, si se quieren conservar las previsiones anteriores, guardar la vintage de abril (por ejemplo, desde el flujo `WEO_2026_APR_VINTAGE`).
- **OCDE**: no hay paro mensual armonizado del **área euro** (lo cubre el agente de Eurostat), de **Suiza** (solo trimestral) ni de CHN, IND, BRA, etc. `oecd_ir3m_gbr` termina en 2026-02 y `oecd_irlt_idn` en 2024-12 porque la OCDE ha dejado de actualizarlas.
- **BIS**: los tipos de cambio efectivos diarios y los bilaterales diarios están en el raw pero no se han curado (solo los mensuales). Tampoco se han curado las estadísticas bancarias internacionales (LBS/CBS) ni los valores de deuda.
- La HPDD se detiene en 2015. Para años posteriores hay que empalmarla con `imf_weo_*_ggxwdg_ngdp` o `imf_gdd_*_fl_s13_pogdp_pt`.
