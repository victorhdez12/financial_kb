# Auditoría de cobertura frente a la lista de datos "imprescindibles" (2026-10-13)

Solo lectura: se consultó `data/warehouse.duckdb` (tabla `catalog`, 14.026 series) sin descargar ni modificar nada. "Última fecha" = campo `end` del catálogo. Hoy es 2026-10-13.

## Resumen
- Cubierto bien: macro EE. UU. (empleo, IPC, PCE, PIB, producción industrial), tipos y curva (Fed Funds, Treasuries, TIPS), VIX, zona euro (HICP, PIB, paro, BCE, €STR, bonos por país, CISS), OCDE/FMI/Banco Mundial, petróleo, oro, factores Fama-French de EE. UU. (mensual).
- No lo tenemos: PMI/ISM, factores AQR, factores JKP, factores Fama-French internacionales/Europa/diarios, índices de bolsa fuera de EE. UU. (salvo IBEX mensual y proxies OCDE), MSCI World/EM, ETFs de factores, DXY, empleo de la zona euro, Brent diario.
- Parcial por licencia: los spreads ICE BofA de FRED solo tienen los últimos 3 años (desde 2023-10), y S&P 500 / Dow solo 10 años (desde 2016-10).
- Observación de frescura: las series diarias de `fred` llegan a 2026-10-05/06 (DGS*, VIX, HY OAS), unos 7 días de retraso; Nasdaq/Dow llegan a 2026-10-12. Conviene reejecutar la ingesta diaria de FRED.

## Tabla de cobertura

| Dato | ¿Lo tenemos? | Serie(s) y fuente | Cobertura y última fecha | Comentario |
|---|---|---|---|---|
| EE. UU. nóminas | sí | `PAYEMS` (fred) | M, 1939-01 a 2026-09 | Al día. Hay versiones ALFRED parciales (14 series). |
| EE. UU. paro | sí | `UNRATE` (fred); `oecd_unemp_usa` | M, 1948-01 a 2026-09 | Contrastada con BLS en la auditoría. |
| Solicitudes semanales de desempleo | sí | `ICSA`, `CCSA` (fred) | W, 1967-01 a 2026-09-26 | Falta la última semana o dos (retraso normal ~1 semana + ingesta). |
| CPI | sí | `CPIAUCSL`, `CPILFESL` (fred); también BLS y Shiller | M, 1947/1957 a 2026-08 | Al día (sale septiembre ~15-oct). |
| PCE | sí | `PCEPI`, `PCEPILFE` (fred) | M, 1959-01 a 2026-08 | Al día. |
| PIB | sí | `GDPC1`, `GDP` (fred) | Q, 1947-Q1 a 2026-Q2 | Falta Q3 (aún no publicado). |
| PMI/ISM manufacturero y servicios | no | Ninguna serie con "ISM" ni "PMI" | - | Es de pago/licenciado (ISM, S&P Global). Proxies: `oecd_bci_*`, `oecd_cli_*`, `eurostat_esi_*`, `UMCSENT`; en FRED solo regionales (Philly, Empire, etc.) que habría que añadir. |
| Producción industrial EE. UU. | sí | `INDPRO` (fred) | M, 1920-01 a 2026-08 | Al día. |
| Fed Funds | sí | `FEDFUNDS` (M), `DFF` (D) (fred) | 1954-07 a 2026-10-05 (D) | Diaria 8 días atrasada. |
| Treasuries 2/5/10/30 años | sí | `DGS2`, `DGS5`, `DGS10`, `DGS30` (fred); `fed_yieldcurve` (73 series, curva Gürkaynak-Sack-Wright); `us_treasury` | D, desde 1976/1962/1962/1977 a 2026-10-05; yieldcurve a 2026-10-02 | Cobertura de sobra. |
| Yields reales TIPS | sí | `DFII5`, `DFII7`, `DFII10`, `DFII20`, `DFII30` (fred/fred_us); breakevens `T5YIE`, `T10YIE` | D, 2003 a 2026-10-08 | Al día. |
| VIX | sí | `VIXCLS` (fred) | D, 1990-01 a 2026-10-06 | Sin VIX3M/VVIX/VXV ni MOVE. |
| Spread High Yield ICE BofA OAS | parcial | `BAMLH0A0HYM2` (fred) | D, **2023-10-09** a 2026-10-06 | FRED recortó el histórico a 3 años por licencia. Para historia larga ver hueco 6. |
| Spread IG/Corporate ICE BofA OAS | parcial | `BAMLC0A0CM` y por rating AAA/AA/A/BBB (fred) | D, **2023-10-09** a 2026-10-06 | Igual: solo 3 años. Proxy largo ya cargado: Moody's `AAA`/`BAA` (M, 1919-01 a 2026-09) y `AAA10Y`/`BAA10Y` (D, 1983/1986 a 2026-10-05) en fred; Damodaran Baa anual. |
| Factores Ken French: Value, Size, Momentum, Profitability, Investment (EE. UU.) | parcial | `ff_hml_m`, `ff_smb_m`, `ff_mom_m`, `ff_mkt_rf_m`, `ff_rf_m` (1926-07); `ff5_rmw_m`, `ff5_cma_m`, `ff5_*` (1963-07); versiones anuales; carteras de 10/12 industrias | M a 2026-08; A a 2025 | Solo mensual y anual. **Faltan los diarios** y los carteras 2x3/25 por tamaño-valor. Fuente gratuita (mrfrench). Licencia de Ken French: uso académico, citar. |
| Factores French internacionales / desarrollados / Europa | no | 0 series (ken_french = 88, todas EE. UU.) | - | Gratuito: mismo sitio (Developed, Europe, Japan, Asia-Pacific ex Japan, North America, Emerging; 5 factores + Mom, mensual y diario). Prioridad alta. |
| AQR: QMJ, BAB, Value and Momentum Everywhere, Time Series Momentum | no | Nada | - | AQR publica Excel gratuitos en su web de datasets (mensuales, QMJ y BAB por país/global; VME; TSMOM). Licencia: uso académico/investigación con atribución; revisar términos antes de usar en producto. |
| JKP factors (jkpfactors.com) | no | Nada | - | Gratuito, CSV por país/región/global (153 factores, ponderado por capitalización y equiponderado), mensual y diario. Licencia: citar Jensen-Kelly-Pedersen (2023). Pesado pero muy útil. |
| Zona euro: PIB | sí | `eurostat_gdp_real_ea_q`, `eurostat_gdp_qoq_ea_q`, `_yoy_` y por país | Q, 1995-Q1 a 2026-Q2 | Falta histórico previo a 1995 (usar OCDE/AWM del BCE, ver huecos). |
| Zona euro: HICP | sí | `ecb_hicp_*` (índice, headline, core, energía, servicios, por 9 países) | M, 1996/1997 a 2026-09 | Al día. |
| Zona euro: empleo | parcial | Paro `eurostat_unemp_ea_m` (2000-01 a 2026-08), `oecd_unemp_*`; paro jóvenes | M | **No hay empleo (nivel de ocupados) de la zona euro ni vacantes**; sí paro. Añadir `namq_10_pe`/`une_rt` de Eurostat. |
| Zona euro: PMI | no | Nada | - | De pago (S&P Global/HCOB). Proxy gratuito: ESI de la Comisión Europea (`eurostat_esi_ea_m`, 1980-01 a 2026-09) y confianza del consumidor; está bien. |
| Tipos BCE | sí | `ecb_dfr_d`, `ecb_mro_d`, `ecb_mlf_d` | D, 1999-01 a 2026-10-12 | Al día. |
| €STR | sí | `ecb_estr_d`; `ecb_overnight_eonia_estr_d` (empalme con EONIA) | D, 2019-10-01 a 2026-10-09; empalmado desde 1999 | Al día. |
| Euribor | parcial | `ecb_euribor_1m/3m/6m/12m_m` | **Mensual**, 1994-01 a 2026-09 | Falta el diario (Euribor oficial es de pago, EMMI; hay Euribor diario en el Banco de España/ECB con restricciones). Ver hueco. |
| Bonos a 10 años por país (euro) | sí | `ecb_gov10y_{at,be,de,es,fi,fr,gr,ie,it,nl,pt}_m` y `ecb_spread10y_*_de_m`; `bde_es_gov10y_secondary_m`; `bundesbank_bund_zero_*` | **Mensual**, 1986-1993 a 2026-08 | Solo mensual. Falta diario por país (ECB SDW tiene diario por país, FM/IRS; ver huecos). La curva diaria euro agregada sí: `ecb_yc_aaa_*` y `ecb_yc_all_*` (2004-09 a 2026-10-08). |
| Condiciones financieras: CISS | sí | `ecb_ciss_new_ea_d` + 7 países (D, 1980 a 2026-10-08); `ecb_ciss_ea_w` (cierra 2025-04), `ecb_sovciss_ea_m` (cierra 2025-04) | | La CISS nueva sustituye a la antigua. SovCISS ya no se actualiza. |
| Diferenciales soberanos | sí | `ecb_spread10y_*_de_m` (mensual) | M, a 2026-08 | Mensual. |
| Condiciones financieras EE. UU. | sí (extra) | `NFCI`, `STLFSI4` (fred) | W a 2026-10-02 | |
| OCDE comparable | sí | `oecd` (309 series): CLI, confianza empresarial y consumidor, CPI/core, tipos 3m/call/10y, paro, índices de bolsa | M, a 2026-08/09; CPI de EA20 y España llega solo a 2025-12 | **Revisar:** el CPI OCDE de España y EA20 está parado en 2025-12 (hay 9 meses de retraso). |
| FMI | sí | `imf_weo` (955), `imf_ifs` (305), `imf_gdd` (155), `imf_hpdd` (31), `imf_cofer` (22) | WEO 1980-2031 (con previsiones); IFS a 2026-09 | WEO de abril; el de octubre aún sin salir (anotado como pendiente). |
| Banco Mundial | sí | `wb_wdi` (375, anual 1960-2025) y `wb_pinksheet` (87 materias primas, M a 2026-09) | | Cebada acaba en 2020-08 (descontinuada). |
| Oro | sí | `gold_usd_monthly` (1791 a 2026-09), `gold_wb_usd_m` | **Mensual** | Falta el diario (LBMA fix PM). `GOLDAMGBD228NLBM` ya no está en FRED. |
| Petróleo WTI | sí | `DCOILWTICO` (D, 1986-01 a 2026-10-06), `MCOILWTICO` | | Al día. |
| Petróleo Brent | parcial | `POILBREUSDM` (fred, M, 1992 a 2026-07), `wb_crude_oil_brent` (M, 1960 a 2026-09) | Mensual | Falta Brent diario (`DCOILBRENTEU` de FRED). Fácil de añadir. |
| Dólar (DXY o ponderado) | parcial | `DTWEXBGS` (D, 2006-01 a 2026-10-02), `RTWEXBGS`; `TWEXB`/`TWEXBMTH` (descontinuadas, 1973-2020); `DEXUSEU`, `DEXJPUS`, `DEXUSUK`, `DEXSZUS`, `DEXCHUS` | | Sin DXY propiamente (licencia ICE). El broad index de la Fed es mejor sustituto; faltan `DTWEXAFEGS`/`DTWEXEMEGS`. Empalmar 1973-2005 con `TWEXBMTH`. |
| Euro: tipos de cambio | sí | `ecb_eurusd_d`, `ecb_eurgbp_d`, `ecb_eurjpy_d`, `ecb_eurchf_d`, `ecb_eurcny_d` (D desde 1999 a 2026-10-09); `ecb_eer41_nominal_m`, `ecb_eer41_real_cpi_m` | | |
| S&P 500 | parcial | `SP500` (fred, D, **2016-10** a 2026-10-06); `shiller_real_price` y TR mensual desde 1871; `damodaran_sp500_tr` anual 1928 | | Diario largo no disponible; Shiller sirve para historia mensual con total return. |
| Nasdaq | parcial | `NASDAQCOM` (fred, D, 1971-02 a 2026-10-12) | | Solo precio, no total return. |
| Dow Jones | parcial | `DJIA` (fred, D, **2016-10** a 2026-10-12) | | Solo 10 años. |
| Euro Stoxx 50 | no | `bde_eurostoxx_broad_m` (STOXX Europe broad, M, 1991-12 a 2026-08); `oecd_share_ea20` (M, 1986-12 a 2026-09) | | Proxies mensuales. Nada diario ni TR. |
| IBEX 35 | parcial | `bde_es_ibex35_m` (M, 1987-01 a 2026-08); `oecd_share_esp` | | Mensual, solo precio. |
| DAX / CAC / FTSE / Nikkei | parcial | `oecd_share_deu`, `oecd_share_fra`, `oecd_share_gbr`, `oecd_share_jpn` (M, 1950-60 a 2026-09); `boe_uk_share_prices_m` (1709-2017) | | Solo índices OCDE mensuales, sin ticker oficial ni TR. |
| MSCI World / MSCI EM | no | Nada | - | De pago (MSCI). Proxy gratuito: ETFs (URTH/ACWI/EEM/IWDA vía Stooq/Yahoo, uso personal) y índices Fama-French global/EM; para total return largo, JST (`jst_*`, anual a 2020) y Dimson-Marsh-Staunton (no gratuito). |
| Total return de bolsa | parcial | Shiller (mensual 1871), Damodaran (anual 1928), JST (anual 1870-2020) | | Solo EE. UU. mensual; resto anual y hasta 2020. |
| ETFs de factores (MTUM, QUAL, VLUE, USMV, SIZE…) | no | Nada | - | Yahoo/Stooq (precios ajustados, uso personal; condiciones de uso restrictivas). Mejor: reemplazar por factores académicos (French/AQR/JKP). |

## Huecos relevantes para un inversor residente en España (regímenes macro y de liquidez)

Prioridad por utilidad para el clasificador de régimen y su coste. "Gratuita y legal" = descarga por API/CSV con términos que permiten uso personal/investigación.

### Prioridad alta
1. **Factores internacionales (French Developed/Europe/Japan/EM + AQR + JKP).** Gratuitos (CSV/Excel). Aporta 4 puntos: factores diarios y mensuales fuera de EE. UU., indispensables para un inversor europeo. Fuente: `mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html`, `aqr.com/Insights/Datasets`, `jkpfactors.com`. Verificar licencia de cada uno.
2. **Spreads de crédito con historia larga (HY/IG).** FRED limita ICE BofA a 3 años. Ya tenemos los proxies de Moody's (`AAA10Y`, `BAA10Y`, `AAA`, `BAA`), pero no son high yield. Gratuito para HY/IG largo: Gilchrist-Zakrajsek excess bond premium (Fed, gratuito, trimestral/mensual desde 1973), y el ICE BofA completo es de pago. Euro: iBoxx es de pago; usar `ecb_` MIR de coste de crédito y CISS como proxy.
3. **Bonos soberanos euro diarios por país (10 años) y Euribor diario.** BCE SDW (`FM` y `IRS`) tiene series diarias por país gratuitas; Euribor oficial es de EMMI (de pago el histórico diario), pero €STR (ya cargado) más swaps OIS reemplazan al Euribor para liquidez. Añadir `ESTR` compuesto y la curva de tipos forward del BCE.
4. **Posicionamiento CFTC (COT).** Gratuito en `cftc.gov` (CSV semanal, desde 1986 en legacy; 2006 en disaggregated/TFF). Muy útil para dólar, petróleo, oro, Treasuries y S&P.
5. **Sentimiento y estrés de mercado adicional.** Gratuito: `UMCSENT` ya está; falta AAII (CSV/Excel gratuito en aaii.com, con registro y condiciones de uso restringidas), CNN Fear & Greed (sin API oficial), NFIB (de pago/gratis resumen), VIX3M/VVIX/SKEW (CBOE, CSV gratuito con histórico diario), **MOVE** (ICE, de pago; proxy gratuito: volatilidad realizada de `DGS10` o `fed_yieldcurve`).

### Prioridad media
6. **PMI/ISM.** De pago (ISM, S&P Global/HCOB). Alternativas gratuitas parciales: FRED regionales (`GACDISA066MSFRBNY` Empire, `GACDFSA066MSFRBPHI` Philly, Richmond, Kansas, Dallas), Comisión Europea ESI/confianza (ya cargados), OCDE CLI/BCI (ya cargados), Sentix (de pago), ifo (descarga gratuita parcial), ZEW (gratuito parcial).
7. **Índices de bolsa diarios con total return fuera de EE. UU.** MSCI/STOXX/S&P son de pago. Opciones gratuitas con matices legales: Stooq y Yahoo Finance (uso personal, términos restrictivos para redistribución); ETFs UCITS comparables (IWDA, EUNL, VWCE, CSPX) vía Yahoo/Stooq para backtests recientes (desde ~2009) con precio ajustado.
8. **Flujos de fondos.** ICI (semanal, gratuito, EE. UU.: ETFs y fondos) y EPFR (de pago). Para España/UE: Inverco (mensual, gratuito) y EFAMA (mensual, gratuito).
9. **Curvas de futuros de materias primas y del VIX.** Exigen proveedor (CME/ICE/CBOE): mayormente de pago; gratuitos parciales vía CBOE VIX futures históricos (CSV gratuito) y `EIA` (WTI/Brent spot y futuros 1-4 meses, gratuito, API con clave gratuita).
10. **Beneficios esperados / revisiones de beneficios.** Datos de consenso (I/B/E/S, FactSet) son de pago. Gratuito: beneficios agregados (NIPA, `CP` de FRED, Shiller E/P ya cargado), Damodaran (earnings implícitos anuales, ya cargado), y la encuesta de analistas del SPF (ya cargada). Revisiones: sin alternativa gratuita seria.
11. **Precios de vivienda en España.** Gratuito: INE (IPV trimestral desde 2007, Tabla 25171), Ministerio (MIVAU, ya cargado como `bde_es_house_price_m2_q`), Notarios (mensual), Registradores, Idealista/Fotocasa (sin API pública gratuita). Añadir IPV del INE (nacional y CCAA), compraventas de viviendas (INE ETDP, mensual) y hipotecas constituidas.
12. **Empleo zona euro (ocupados) y vacantes.** Gratuito en Eurostat (`namq_10_pe`, `jvs_q_nace2`). En España: afiliación a la Seguridad Social (mensual, gratuito, ya hay paro registrado `bde_es_registered_unemployed_m` y EPA).

### Prioridad baja
13. **Oro diario (LBMA PM fix) y Brent diario.** LBMA es de pago; alternativa gratuita: `DCOILBRENTEU` (FRED) y oro del Banco Mundial mensual (ya cargado) / Stooq (XAUUSD). Poco impacto en el régimen.
14. **MOVE exacto, SKEW, Fear & Greed, flujos EPFR.** De pago o sin API; ver alternativas arriba.
15. **Series del Tesoro/Fed de más frecuencia que ya están** (revisar frescura): ingesta diaria de FRED con ~7 días de retraso.

## Acciones recomendadas inmediatas (todas gratuitas)
1. Ejecutar la ingesta diaria de FRED para ponerla al día y añadir `DCOILBRENTEU`, `DTWEXAFEGS`, `DTWEXEMEGS`, regionales de la Fed (Empire/Philly, no cargados) y `NASDAQ100`.
2. Ingestar French (Developed, Europe, Japan, EM; 5 factores + Mom; mensual y diario), AQR y JKP en una fuente nueva con licencia anotada.
3. Ingestar CFTC COT (TFF y legacy) y CBOE VIX3M/VVIX/SKEW.
4. Ingestar BCE diario por país (rendimientos 10 años) y empleo de Eurostat.
5. Revisar con el recopilador internacional por qué `oecd_cpi_esp_*` y `oecd_cpi_ea20_*` terminan en 2025-12.
