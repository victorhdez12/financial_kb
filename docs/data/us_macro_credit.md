# EE. UU.: mercado laboral, tipos, crédito, liquidez y fiscal (ampliación 2026-10)

Generado el 2026-10-12. Todo sigue `docs/DATA_CONTRACT.md`: el raw se guarda intacto en `$FIN_DATA_ROOT/raw/<source_id>/` y cada serie va en un parquet `curated/<source_id>/<series_id>.parquet` (`date, value, series_id, source`), con su `_catalog.csv`.
Los scripts son idempotentes y se ejecutan con `.venv/bin/python -m src.ingest.<source_id>`.

| source_id | script | series | cobertura | frecuencia | licencia |
|---|---|---|---|---|---|
| `alfred` (ampliado) | `alfred_vintages.py` | 14 (antes 7) | vintages 1980 → 2026-10 | M / Q / W | FRED/ALFRED |
| `fred_us` (nuevo) | `fred_us.py` | 1.691 | 1901 → 2026-10 | D / W / M / Q / A | FRED (terceros: Moody's, Freddie Mac, ICE) |
| `fed_yieldcurve` (nuevo) | `fed_yieldcurve.py` | 73 | 1961-06-14 → 2026-10-02 | D | Fed Board, investigación pública |
| `us_treasury` (nuevo) | `us_treasury.py` | 25 | 1790 → 2026-10-08 | A / M / D | dominio público |
| `nyfed_hhdc` (nuevo) | `nyfed_hhdc.py` | 103 | 1999 → 2026-Q2 | Q | NY Fed / Equifax CCP |
| `nber_macrohistory` (ampliado) | `nber_macrohistory.py` | 1.627 (antes 39) | 1820 → 1970s | M / Q / A | NBER, investigación |
| `shiller_housing` (nuevo) | `shiller_housing.py` | 9 | 1890 → 2026-07 | A / M | R. Shiller |
| `us_hist_labor` (nuevo) | `us_hist_labor.py` | 2 | 1890 → 2010 | A | OpenIntro (Romer / Coen / BLS) |

En total se añaden unas **3.500 series**. Ningún `series_id` nuevo choca con los existentes: `fred_us` excluye en tiempo de ejecución todo lo que ya está en `curated/fred/_catalog.csv` (se saltaron 35 IDs). La única excepción es ALFRED, que por diseño reutiliza el ID de FRED; sus filas tienen `realtime_start`, así que `obs_latest` las excluye.

## 1. ALFRED: vintages de los inputs del clasificador
- Se han añadido **ICSA, TCU, M2SL, PPIACO, GDP, PCEPI y CFNAI** a las 7 que ya había (GDPC1, PAYEMS, CPIAUCSL, CPILFESL, PCEPILFE, INDPRO, UNRATE). Con esto ALFRED cubre todas las series de `src/regime/features.py` con `vintage=True`, y además GDP (`gdp_nom_yoy`), M2SL, TCU, ICSA y CFNAI.
- Vintages por serie: ICSA 901 (desde 2009-05), TCU 385 (desde 1996-11), M2SL 1.931 (desde 1980-02), PPIACO 367 (desde 1996-12), GDP 415 (desde 1991-12), PCEPI 316 (desde 2000-08), CFNAI 182 (desde 2011-05).
- Limitación: antes de la primera vintage, `as_of()` devuelve una serie vacía. Para ICSA (2009) y CFNAI (2011) el clasificador seguirá usando la serie final en los años anteriores.

## 2. `fred_us`: universo de EE. UU. sobre la API de FRED
Se combinan una lista explícita (`EXPLICIT`, 274 series) y releases completas de FRED descubiertas con `fred/release/series` (`RELEASES`):

| bloque | nº | contenido |
|---|---|---|
| SLOOS (release 191) | 636 | encuesta completa: endurecimiento y demanda por tipo de préstamo y tamaño de banco, 1990+ |
| Charge-offs y morosidad (231) | 260 | tasas de fallidos y morosidad por tipo de préstamo y por tamaño de banco, SA y NSA, 1985+ |
| H.15 (18) | 181 | curva del Tesoro diaria, semanal y mensual (1M-30Y), CP, prime, EFFR, TIPS y series discontinuadas (bono compuesto >10Y desde 1925, Moody's desde 1919) |
| G.19 (14) | 159 | crédito al consumo revolving y no revolving por tenedor, 1943+ |
| H.8 (22) | 66 | todas las partidas semanales SA de "All Commercial Banks" (crédito, valores, CRE, consumo, depósitos), 1973+ |
| PMMS Freddie Mac (190) | 57 | hipotecas a 30, 15 y 5 años y puntos, 1971+ |
| JOLTS (192) | 41 | 12 agregados nacionales (vacantes, contrataciones, bajas voluntarias, despidos, en nivel y tasa) más tasas de vacantes y bajas voluntarias por industria, 2000-12+ |
| MTS / valor de mercado de la deuda / OBFR / ratios de servicio de deuda | 17 | ingresos, gastos y déficit mensuales del Tesoro (1980+), OBFR, DSR de hogares |
| explícitas: empleo | 67 | U-1 a U-5 (SA y NSA, 1948+), duración del paro (UEMPMEAN, UEMPMED, UEMP27OV…), PRIME-age EPOP, nóminas por sector CES (1939+), AHE, ECI, productividad y CLU, Atlanta Fed wage tracker, ICNSA, IC4WSA, CCNSA |
| explícitas: tipos | 41 | Kim-Wright: rendimientos y prima por plazo de 1 a 10 años (THREEFYTP1-9, THREEFY1-9) y forwards; IORB/IOER, SOFR medias e índice, RRP, DAAA/DBAA diarios, breakevens 5y5y |
| explícitas: crédito Z.1 | 33 | deuda por sector desde 1945: hogares (CMDEBT, hipotecas, consumo), empresas no financieras (BCNSDODNS, TBSDODNS, no corporativas), gobierno federal y local, sector financiero, GSE, resto del mundo, MDOAH, deuda empresarial sobre valor de mercado, patrimonio neto de hogares, crédito de valores; también H.8 mensual desde 1947 (LOANS, REALLN, INVEST, USGSEC) |
| explícitas: liquidez y dinero | 35 | H.4.1 en detalle (Treasuries, MBS, RRP de extranjeros y otros, préstamos, swaps, TGA); históricas semanales desde 1914 (billetes en circulación, oro de la Fed, TGA 1915-2018); reservas, préstamos de la Fed, velocidad M1/M2, M2 real |
| explícitas: fiscal | 15 | ingresos, gastos y saldo federal (FYFR, FYONET, FYFSD, 1901+), intereses (FYOINT), deuda/PIB anual, tenencias extranjeras y de la Fed, cuentas federales trimestrales |
| explícitas: crecimiento y beneficios | 36 | PIB potencial (CBO), GDI, renta y consumo real, pedidos, inventarios, ventas de vehículos, beneficios NIPA (CP, CPATAX, no financieros, anuales desde 1929) |
| explícitas: inflación | 20 | sticky CPI, mediana y media recortada (Cleveland, Dallas), vivienda, servicios, PPI de demanda final, expectativas (Cleveland, UMich), precios de importación |
| explícitas: vivienda y condiciones | 27 | precio medio de venta, Case-Shiller NSA, FHFA, ventas nuevas, meses de oferta, tasa de propietarios y vacantes, Optimal Blue, CP 3M, CPFF |

**Comprobaciones**: U1RATE en 2026-09 = 1,8 %. CMDEBT en 2026-Q2 = 21,4 billones de USD. GSW 10y menos DGS10 da una mediana de +0,06 pp y en 2026-10 coinciden. El déficit MTS de 2026-08 es −166.797 millones. La primera observación de FYFR es de 1901.

**IDs que no existen en FRED** (quedan registrados en `raw/fred_us/_run_summary.json`): `LNS13008636`, `CES0500000008` y `BOGZ1FL104104006Q`.

**Advertencias**
- Se conserva la fecha que da FRED. En los anuales fiscales (FYFR, FYONET, FYFSD, FYOINT) la fecha es el **final del año fiscal** (p. ej. 1901-06-30), no el 1 de enero. El resto de series M/Q/A van fechadas al inicio del periodo.
- 111 series de H.15 están marcadas como DISCONTINUED, porque son historia (CP antiguos, Moody's mensual antiguo, bono compuesto). MDOAH termina en 2019-07.
- SLOOS cambia de preguntas con el tiempo: muchas series son cortas o tienen huecos.

## 3. `fed_yieldcurve`: curvas Gürkaynak-Sack-Wright (Fed Board)
- **Nominal** (`feds200628.csv`): rendimientos cupón cero `gsw_sveny01` a `gsw_sveny30` y forwards a 1 año `gsw_sven1f01`, `gsw_sven1f04` y `gsw_sven1f09`. Diario desde **1961-06-14**; 8-10y desde 1971, 16-20y desde 1981, 21-30y desde 1985.
- **TIPS** (`feds200805.csv`): tipos reales cupón cero `gsw_tipsy02` a `gsw_tipsy20`, breakevens `gsw_bkeven02` a `gsw_bkeven20`, y `gsw_bkeven1f4`, `gsw_bkeven1f9` y `gsw_bkeven5f5` (5y5y). Desde 1999-01.
- Unidades: %, con capitalización continua, así que no son directamente comparables con los rendimientos par de H.15. Las primas por plazo están en otras fuentes: ACM en `curated/nyfed` y Kim-Wright en `fred_us` (THREEFYTP*).

## 4. `us_treasury`: Treasury FiscalData API
- `ust_debt_outstanding_a`: **deuda federal desde 1790** (71 M$) hasta 2026 (40,17 billones), en millones. La fecha es el 1 de enero del año fiscal, pero el valor es el nivel en la fecha de registro: 1 de enero hasta 1842, 30 de junio entre 1843 y 1976, y 30 de septiembre desde 1977. El año 1843 trae dos registros y se conserva el posterior.
- `ust_dtp_*_d`: Debt to the Penny diaria. El total arranca en 1993-04; la deuda en manos del público y la intragubernamental, en 1997-09.
- `ust_mspd_*_m`: MSPD mensual desde 2001: deuda negociable y no negociable, total y en manos del público, y desglose en bills, notes, bonds, TIPS y FRN.
- `ust_avgrate_*_m`: tipo medio de la deuda (total, negociable, bills, notes, bonds, TIPS) desde 2001.
- `ust_interest_expense_*_m`: gasto por intereses mensual desde 2010-05, en total, de emisiones públicas y de GAS. Control: total del FY2025 = 1,22 billones de USD.
- Los ingresos y gastos MTS se toman de FRED (release 363, en `fred_us`), que llega hasta 1980. La versión de FiscalData empieza en 2015.

## 5. `nyfed_hhdc`: Household Debt and Credit (NY Fed)
- Libro `HHD_C_Report_2026Q2.xlsx`. El script busca el último trimestre disponible.
- 103 series trimestrales (`hhdc_*`): saldos por producto desde 2003 (control: total 2026-Q2 = 18,77 billones), cuentas, consultas de crédito, originaciones hipotecarias y de autos por tramo de score, score de las originaciones, estado de morosidad, 90+ por producto, nuevas entradas en mora a 30+ y 90+, transiciones, ejecuciones hipotecarias y quiebras, cobros, saldo por edad y transición a mora grave por edad y producto (desde 1999-2000).
- Se omiten las páginas de foto por estado y `delstat_total`, que vale 100 por construcción. Algunos títulos de página dicen "Percent" aunque la columna está en otra unidad; el catálogo lo corrige en los casos conocidos (cobros en USD, scores).

## 6. NBER Macrohistory (ampliado de 39 a 1.627)
- Las 39 series curadas originales no cambian (`SELECTION`). La ampliación se hace por reglas sobre los índices de capítulo (`contents/chapterNN.html`, cacheados en `raw/nber_macrohistory/_index/`). Solo se toman series de **EE. UU.**:
  - Capítulos completos: 04 precios (278), 07 comercio exterior (40), 09 situación financiera de las empresas, quiebras y beneficios (139), 10 ahorro, inversión y emisiones (151), 11 mercados de valores (16), 12 volumen de transacciones (49), 13 tipos de interés (64), 14 dinero y banca (193), 15 finanzas públicas (41) y 16 índices cíclicos (130).
  - Filtrados por título: 01 producción (104: índices, arrabio, acero, autos, electricidad), 02 construcción (119: totales e índices), 03 transporte (21), 06 distribución (98: ventas totales y minoristas) y 08 empleo y renta (184: paro, empleo total y fabril, salarios y horas, renta personal y nacional).
- Categorías asignadas por capítulo, con reglas: los préstamos y descuentos del capítulo 14 y las quiebras del 09 van a `credit`, y los bonos corporativos y municipales del 13 también.
- 326 series empiezan antes de 1900. Tres IDs del índice no tienen `.dat` (404) y quedan en `_index/missing.txt`.
- Los ficheros NBER están congelados desde 2001-2002. En la ampliación se reutiliza el raw cacheado y la descarga se hace en paralelo con 6 hilos.
- Limitaciones: las unidades vienen del `.txt` (6 series sin unidad). Hay tramos solapados (a/b/c) con cambios de metodología, así que no hay que empalmarlos sin ajustar. Muchas series son regionales o sectoriales y tienen huecos.

## 7. `shiller_housing`: precios de vivienda desde 1890
- `Fig3-1.xls` de shillerdata.com. Incluye el índice real y nominal de precios de vivienda: anual de 1890 a 1952 (`*_a`) y mensual desde 1953-01 (`*_m`), separados para no mezclar frecuencias. También el coste de construcción real y nominal, la población, el **tipo largo de enero desde 1890** (Homer, *A History of Interest Rates*, antes de GS10) y el CPI anual.

## 8. `us_hist_labor`: paro anual 1890-2010
- Dataset `unempl` de OpenIntro: Romer (1986) para 1890-1929, Coen (1973) para 1930-1939 y BLS desde 1940. `us_unemp_romer_flag_a` marca qué valores son datos oficiales.
- Atención: Coen da un paro más bajo que Lebergott en los años 30 (1933: 19,8 % frente a 24,9 %).

## Huecos pendientes (no cubiertos y por qué)
- **Lebergott (1800-1890) y Weir (1992)**: solo están en *Historical Statistics of the US* (Cambridge, de pago). Para 1929-1966 hay tramos mensuales NBER (`M0892*`, `nber_m08292a`).
- **Homer & Sylla**: es un libro y no hay datos descargables. Como sustitutos sirven el tipo largo de Shiller desde 1890 (de Homer), los tipos NBER desde 1857 y los MeasuringWorth que hay en `gold`.
- **API BLS v2**: no se ha usado, porque todo lo pedido (U-1 a U-6, duración, CES por sector, salarios, JOLTS) está en FRED con la misma historia. Quedaría para series sin espejo en FRED, como los flujos brutos de la CPS o las JOLTS por tamaño de empresa.
- **Z.1 completo** (unos 48.000 IDs en FRED o el zip del DDP de la Fed): solo se han cogido las partidas clave de la tabla D.3 y del patrimonio neto. Para tener más habría que descargar `z1_csv_files.zip`.
- **Banking and Monetary Statistics 1914-1941** (release 388 de FRED, 1.993 series): no se ha descargado. Sería útil para estudiar la banca de entreguerras.
- **SOFR antes de 2018 y repo general**: no existe. Las series BGCR y TGCR de la NY Fed no se han buscado.
- **MTS antes de 1980 en formato mensual**: no está accesible por API.

## Cambios necesarios en `src/warehouse/build.py`
Ninguno es obligatorio. `curated_frames()` ya carga por glob `curated/*/*.parquet` y `curated/*/_catalog.csv`, y `reindex(columns=CATALOG_COLS)` descarta las columnas extra (`requested_id`, `n_obs`, `n_vintages`...). Recomendaciones:
1. **Duplicado de catálogo de ALFRED**: los 14 IDs de ALFRED aparecen también en `curated/fred`. Si `catalog` se usa con `series_id` como clave única, conviene deduplicar dando prioridad a `source='fred'`, o renombrar el catálogo de ALFRED con un sufijo. Para las observaciones no hace falta nada, porque `obs_latest` ya filtra por `realtime_start is null`.
2. **Columna `realtime_end`**: los parquets de ALFRED la traen, pero `normalize_curated` la descarta. Sin ella, la vista `vintages` no sabe hasta cuándo fue válido cada valor. Para hacer point-in-time en SQL habría que añadirla a `OBS_COLS`.
3. **Volumen**: se añaden unos 2,7 M de filas (más las vintages de ALFRED) (sobre todo `fed_yieldcurve` diario, SLOOS y NBER). No debería haber problemas de memoria, pero el build tardará algo más.
4. **Fechas de fin de año fiscal** en FYFR, FYONET, FYFSD y FYOINT: la vista `monthly` las colocará en junio o septiembre. Si se quiere uniformidad, habría que normalizar las fechas anuales a 1 de enero en la carga.
