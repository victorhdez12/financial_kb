# Datos históricos largos externos (no FRED/BLS)

Generado 2026-10-07. Todas las fuentes siguen `docs/DATA_CONTRACT.md`:
raw intacto en `$FIN_DATA_ROOT/raw/<source_id>/`, una serie por parquet en
`$FIN_DATA_ROOT/curated/<source_id>/<series_id>.parquet` (`date, value, series_id, source`) y `_catalog.csv`.
Cada script es idempotente: `.venv/bin/python -m src.ingest.<source_id>`. Helper común: `src/ingest/_extlong_common.py`
(descarga con User-Agent, reintentos, validación de magic bytes / rechazo de HTML, escritura de catálogo y borrado de parquets obsoletos).

| source_id | Series | Cobertura | Frecuencia | Licencia |
|---|---|---|---|---|
| `shiller` | 21 | 1871-01 → 2026-10 (CAPE desde 1881) | M | Datos públicos de R. Shiller, citar fuente |
| `jst_macrohistory` | 998 (+88 eventos) | 1870 → 2020, 18 países | A | CC BY-NC-SA 4.0, citar JST (2017) y Jordà et al. (2019) |
| `gold` | 10 | 1257 → 2026-09 (USD mensual empalmado 1791 →) | A / M | MeasuringWorth (no comercial, citar); WB CC BY 4.0; datahub PDDL |
| `wb_pinksheet` | 87 | 1960-01 → 2026-09 | M | CC BY 4.0 (World Bank) |
| `ken_french` | 88 | 1926-07 → 2026-08 (FF5 desde 1963-07) | M / A | Ken French Data Library, citar (derivado de CRSP) |
| `damodaran` | 19 | 1928 → 2025 | A | A. Damodaran (NYU Stern), uso educativo/investigación |
| `boe_millennium_uk` | 45 | 1209 → 2016/2017 | A / M | Bank of England, reutilización con atribución |
| `nber_macrohistory` | 39 | 1824 → 1971 | M / Q / A | NBER, uso libre en investigación, citar |

Total: 1.307 series, sin colisiones de `series_id`.

## 1. Shiller (`shiller_*`)
- Fuente: `ie_data.xls` enlazado desde https://shillerdata.com/ (la URL de Yale sigue respondiendo pero puede estar desfasada; el script lee el enlace vigente de shillerdata.com y usa Yale como respaldo).
- Series: precio S&P Composite, dividendos, beneficios, CPI, GS10, precio real, índice real de rentabilidad total, CAPE, TR-CAPE, excess CAPE yield, rentabilidad mensual de bonos (bruta) e índice real de bonos.
- Derivadas: `shiller_real_stock_tr_ret_m`, `shiller_nominal_stock_tr_ret_m`, `shiller_nominal_bond_tr_ret_m`.
- Control: rentabilidad real geométrica 1871-2026 = 7,1 % anual.
- Limitaciones: los precios son **medias mensuales** de cierres diarios, no cierres a fin de mes (2008 da −39 % frente a −36,6 % de Damodaran, que usa fin de año). Dividendos y beneficios están interpolados y llegan con retraso (terminan en 2026-06). El último mes es provisional (precio del día 2 y CPI estimado). `shiller_fwd10y_*` son **rentabilidades futuras a 10 años** (look-ahead): no deben usarse como predictores.

## 2. Jordà-Schularick-Taylor (`jst_<iso>_<var>`)
- Fuente: JST Macrohistory **R6** (`JSTdatasetR6.xlsx`; es la última versión publicada en macrohistory.net a fecha de hoy) y documentación en PDF dentro de raw.
- Hay 18 países (AUS BEL CAN CHE DEU DNK ESP FIN FRA GBR IRL ITA JPN NLD NOR PRT SWE USA) y las 54 variables originales, entre ellas `eq_tr`, `bond_tr`, `bill_rate`, `housing_tr`, `tloans`, `tmort`, `stir`, `ltrate`, `cpi`, `debtgdp`, `crisisJST`, `capital_tr`, `risky_tr` y `safe_tr`.
- Derivadas: `*_tloans_gdp`, `*_tmort_gdp`, `*_thh_gdp` y `*_tbus_gdp` (crédito/PIB); `*_inflation`; y `*_eq_tr_real`, `*_bond_tr_real`, `*_bill_rate_real` y `*_housing_tr_real`, deflactadas con el CPI.
- Eventos: `$FIN_DATA_ROOT/events/jst_crises.parquet` contiene 88 crisis bancarias sistémicas entre 1870 y 2008, con `type=banking_crisis`.
- Limitaciones: la serie termina en 2020 y es anual (fechada el 1 de enero). **Canadá e Irlanda no tienen rentabilidades** de activos. Faltan algunos tramos, como las guerras o la hiperinflación alemana. `crisisJST` solo marca el año de inicio, así que `end_date` queda vacío. La licencia **no permite uso comercial**. Se descartaron 118 combinaciones país×variable porque estaban vacías.

## 3. Oro (`gold_*`)
| Tramo | Fuente | Serie |
|---|---|---|
| 1257-1945 | MeasuringWorth: precio oficial británico (GBP) | `gold_mw_british_official_gbp_a` |
| 1718-1949 / 1950- | MeasuringWorth: mercado de Londres (GBP / USD) | `gold_mw_london_gbp_a`, `gold_mw_london_usd_a` |
| 1786- | MeasuringWorth: precio oficial de EE. UU. | `gold_mw_us_official_usd_a` |
| 1791- | MeasuringWorth: mercado de Nueva York (media anual) | `gold_mw_newyork_usd_a` |
| 1687- | Ratio oro/plata | `gold_mw_gold_silver_ratio_a` |
| 1960- | World Bank Pink Sheet (media mensual, Londres) | `gold_wb_usd_m` |
| 1833- | datahub core/gold-prices (control cruzado) | `gold_datahub_usd_m` |

- **`gold_usd_monthly`** empalma dos fuentes. De 1791 a 1959 usa la media anual de Nueva York de MeasuringWorth, repetida en los 12 meses. Desde 1960 usa la media mensual del World Bank. `gold_usd_monthly_flag` vale 1 cuando el valor es anual repetido.
- La serie recoge la prima *greenback* de la Guerra Civil (42 $ en 1864) y la revaluación de 1933-34 (24,44 $ → 35 $). La diferencia máxima con datahub desde 1960 es de 0,47 $.
- Limitaciones: antes de 1960 no hay variación dentro del año, así que no sirve para volatilidad mensual. MeasuringWorth termina en 2025, porque es anual. FRED retiró la serie LBMA y la API JSON de LBMA no es pública (devuelve HTML). World Gold Council exige registro, así que no se usó.

## 4. Materias primas: World Bank Pink Sheet (`wb_*`, `wb_idx_*`)
- Fuente: `CMO-Historical-Data-Monthly.xlsx`. El enlace vigente se obtiene de la página commodity-markets; el de 2025 estaba desfasado y terminaba en 2025-12.
- Contiene 71 precios nominales en USD (energía, metales, agrícolas, fertilizantes) y 16 índices con base 2010=100 (total, energía, no energía, metales, metales preciosos, alimentos, etc.).
- Limitaciones: datos solo en dólares nominales y solo desde 1960. Algunas series terminaron antes, como cebada y sorgo (2020) o gambas (2023), y otras empiezan tarde, como el WTI (1982). Los cambios de especificación se explican en la hoja Description del raw.
- Las series de Jacks (desde 1850) no se han buscado ni descargado todavía; quedan pendientes. Para materias primas antes de 1960 hay NBER (`nber_m04202`, precios mayoristas) y el petróleo de BoE (`boe_uk_oil_price_usd_a`, desde 1861).

## 5. Ken French (`ff_*`, `ff5_*`, `ff_ind10_*`, `ff_ind12_*`)
- Factores 3F (`ff_mkt_rf`, `ff_smb`, `ff_hml` y `ff_rf`) mensuales desde 1926-07 y anuales. También momentum (`ff_mom`, desde 1927) y FF5 (`ff5_*`, con RMW y CMA, desde 1963-07).
- Las 10 y 12 carteras sectoriales tienen versión mensual ponderada por capitalización (`_vw_m`) y equiponderada (`_ew_m`), y versión anual ponderada (`_vw_a`).
- Unidades: **porcentaje por periodo**. Los valores −99,99 y −999 se tratan como NaN. La versión CRSP es 202608.
- Control: 2008 Mkt = −36,7 %; media Mkt-RF = 0,70 % mensual.
- Limitaciones: Ken French reconstruye la historia en cada actualización, así que los valores pasados pueden cambiar entre versiones y no son point-in-time.

## 6. Damodaran (`damodaran_*`)
- Rentabilidades anuales nominales y reales de 1928 a 2025: S&P 500, small caps, T-bill a 3 meses, T-bond a 10 años, bonos Baa, inmobiliario y oro. También incluye primas de riesgo, ERP implícita (desde 1960) e inflación. Fichero actualizado el 2026-01-01.
- Limitaciones: rentabilidades de año natural, con una actualización al año. Antes de 1957 la serie usa índices predecesores del S&P. La serie de oro se basa en precios de fin de año.

## 7. Bank of England, *A millennium of macroeconomic data* (`boe_uk_*`)
- Versión 3.1, congelada: **termina en 2016 en las series anuales y en 2017-02 en las mensuales**. La BoE ya no la actualiza.
- Solo se extrajo una selección de las hojas A1 (anual) y M1 (mensual): PIB real y nominal, población, paro, deflactor, CPI desde 1209, WPI, salarios, Bank Rate desde 1694, consols desde 1703, bono a 10 años, tipo hipotecario, bonos corporativos y diferencial, acciones desde 1709, $/£ desde 1791, vivienda, crédito, M0, M4, balance de la BoE/PIB, déficit/PIB, deuda/PIB y cuenta corriente/PIB.
- Limitaciones: hay empalmes y cambios de frontera (GB, GB+Irlanda, UK) documentados en `transform_notes`. Las series mensuales mezclan valores de fin de mes y medias. La inflación anual está en porcentaje, no en fracción.

## 8. NBER Macrohistory (`nber_<id>`)
- Selección de 39 series anteriores a 1940 que no están en FRED o que en FRED empiezan más tarde:
  - Tipos: call money y commercial paper desde 1857; descuento de la Fed de NY; bonos ferroviarios de Macaulay de 1857 a 1937; bonos largos de EE. UU. de 1919 a 1967; bonos corporativos de máxima y mínima calificación; municipales trimestrales.
  - Tipos europeos: Bank of England desde 1836, mercado abierto de Londres desde 1824, Banque de France y Reichsbank.
  - Bolsa: Cowles/S&P de 1871 a 1956, acciones ferroviarias desde 1855 y Dow Jones de 1914 a 1968.
  - Precios: mayoristas desde 1850, CPI de 1913 a 1970 y coste de la vida; precios mayoristas de GB, Francia y Hamburgo.
  - Actividad: Babson, producción de arrabio, compensaciones bancarias e índices adelantado y coincidente de 1919 a 1940.
  - Dinero: M2 de 1907 a 1946 y stock de oro monetario.
- Cada serie conserva su `.dat` y su documentación `.txt` en raw, con la fuente original y las notas.
- Limitaciones: muchas series tienen sufijos a/b/c que son tramos no empalmados con bases distintas, así que hay que empalmarlas antes de usarlas. El código de valor ausente 1E-37 se convierte en NaN. Las unidades vienen del fichero de documentación, y en las series a01206 y m01001 hay que consultar el `.txt`.

## Notas generales
- Ninguna de estas fuentes es point-in-time: son revisiones actuales de datos históricos. Para hacer backtests hay que aplicar retrasos de publicación (Shiller tiene unos 3 meses de retraso en beneficios y JST, varios años).
- Licencias no comerciales: JST (CC BY-NC-SA) y MeasuringWorth. El uso es personal y de investigación, como establece el contrato.
- No se ha añadido Caldara-Iacoviello, porque lo cubre otro agente.
