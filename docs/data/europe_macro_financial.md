# Datos de Europa, BCE y España

Generado el 2026-10-12. Todas las fuentes siguen `docs/DATA_CONTRACT.md`: el raw se guarda intacto en `$FIN_DATA_ROOT/raw/<source_id>/` y cada serie va en su propio parquet en `$FIN_DATA_ROOT/curated/<source_id>/<series_id>.parquet` (`date, value, series_id, source`), con su `_catalog.csv`.
Los scripts son idempotentes: `.venv/bin/python -m src.ingest.<source_id>`. Reutilizan el raw si tiene menos de 20 h y, si falla la red, recurren al último raw disponible.
El helper común es `src/ingest/_europe_common.py`, que se apoya en `_extlong_common.py`. Hace lo siguiente:
- Normaliza las fechas al **inicio del periodo**: `2024-Q2` pasa a 2024-04-01, `MAR 1995` trimestral del BdE pasa a 1995-01-01, y una semana ISO pasa a su lunes.
- **Descarta observaciones con fecha posterior a hoy**.
- En las series de stocks, índices y precios marcadas `positive`, guarda como **NaN los ceros**, porque ahí son datos ausentes.
- Mantiene los NaN, sin rellenarlos.

En las tasas de variación, saldos y tipos el cero es un valor legítimo y se conserva. Por ejemplo, hay meses de 2014-2015 con IPC subyacente del 0,0 %.

**Orden de ejecución:** `ecb` → `eurostat` → `bde` → `ine` → `bundesbank`. `bundesbank` va al final porque usa `ecb_mro_d` para construir el empalme del tipo oficial.

| source_id | Series | Filas | Cobertura | Frecuencias | Licencia |
|---|---|---|---|---|---|
| `ecb` | 116 | 286.491 | 1980-01 → 2026-10-12 | D 37 · M 70 · Q 7 · W 2 | BCE, reutilización libre citando la fuente |
| `eurostat` | 98 | 22.896 | 1980-01 → 2026-09 | M 37 · Q 39 · A 22 | CC BY 4.0 (Eurostat) |
| `bde` | 53 | 23.007 | **1933-07** → 2026-09 | M 37 · Q 15 · A 1 | Banco de España, reutilización con atribución |
| `ine` | 13 | 2.567 | 1962-01 → 2026-09 | M 4 · Q 9 | INE, reutilización con atribución |
| `bundesbank` | 19 | 11.536 | **1948-07** → 2026-10 | M 19 | Bundesbank, reutilización con atribución |

En total son **299 series**. Ningún `series_id` coincide con otra fuente, porque todos llevan prefijo de fuente. Ninguna serie termina en una fecha futura.

## 1. BCE, ECB Data Portal (`ecb_*`)
- **API**: `https://data-api.ecb.europa.eu/service/data/<FLOW>/<KEY>?format=csvdata`, sin clave. El raw es un CSV por serie (`raw/ecb/<FLOW>.<KEY>.csv`), con todos los atributos (97 MB).
  - **Ojo**: el WAF del BCE bloquea las ráfagas y las consultas con muchos comodines ("Your access has been blocked"). El script hace una petición por clave y espera 0,4 s entre una y otra.
- **Tipos oficiales (diarios y escalonados, desde 1999)**: `ecb_dfr_d` (facilidad de depósito), `ecb_mlf_d` (facilidad marginal de crédito), `ecb_mro_fixed_d` y `ecb_mro_minbid_d`.
  - **Empalme** `ecb_mro_d`: usa el tipo fijo de 1999-01 a 2000-06-27, el mínimo de puja de 2000-06-28 a 2008-10-14 y de nuevo el tipo fijo desde 2008-10-15.
- **Interbancario**: `ecb_estr_d` (€STR desde 2019-10), `ecb_eonia_d` (EONIA diario de 1999 a 2021), `ecb_eonia_m` y `ecb_euribor_{1m,3m,6m,12m}_m` (media mensual desde 1994).
  - **Empalme** `ecb_overnight_eonia_estr_d`: EONIA hasta 2019-09-30 y €STR desde 2019-10-01, **sin ajustar**. Hay un escalón de unos −8,5 pb, porque desde 2019-10 el EONIA era €STR + 8,5 pb.
- **Curvas de tipos (Svensson, cupón cero, diarias desde 2004-09-06)**: `ecb_yc_{aaa,all}_spot_{3m,1y,2y,5y,10y,20y,30y}_d`, para bonos AAA y para todos los bonos del área. Derivadas: `ecb_yc_{aaa,all}_10y2y_slope_d` (pb).
- **Bonos a 10 años por país** (rendimiento de convergencia IRS, mensual): `ecb_gov10y_{de,es,it,fr,pt,gr,nl,ie,be,at,fi}_m`. Empiezan entre 1986 (FR, NL), 1990 (DE), 1991 (ES, IT) y 1992-93 (GR, PT, IE, AT).
  - Diferenciales derivados frente a Alemania, en pb: `ecb_spread10y_{es,it,fr,pt,gr,nl,ie,be}_de_m`. El máximo griego fue de 2.739 pb en 2012-02.
- **Dinero y crédito (BSI)**: `ecb_m{1,2,3}_stock_m` (stock desestacionalizado, desde 1980) y `ecb_m{1,2,3}_yoy_m`. También `ecb_loans_{hh,nfc}_adj_yoy_m`: crecimiento de préstamos ajustados por ventas y titulizaciones, desde 2003.
- **Tipos bancarios (MIR, coste compuesto de nuevas operaciones, desde 2003)**: `ecb_mir_nfc_cost_{ea,es,de,it,fr}_m` y `ecb_mir_hh_house_cost_{ea,es,de,it,fr}_m`.
- **Bank Lending Survey (trimestral, desde 2003)**:
  - Área euro: criterios de concesión a empresas, hipotecas y consumo, y demanda de empresas y de hipotecas (`ecb_bls_*_ea_q`, porcentaje neto ponderado).
  - España: criterios a empresas y a hipotecas (`ecb_bls_*_es_q`). Son porcentajes netos sin ponderar de una muestra pequeña de bancos, por lo que hay muchos ceros legítimos.
  - Un valor positivo significa endurecimiento o aumento de la demanda.
- **Balance del Eurosistema**: `ecb_eurosystem_total_assets_w` (semanal, 1999 → hoy, en millones de EUR). La fecha es el lunes de la semana ISO.
- **Estrés sistémico**:
  - `ecb_ciss_new_ea_d` y por país `ecb_ciss_new_{de,es,fr,it,pt,nl,ie}_d` (nuevo CISS diario, desde 1980 para EA y DE).
  - `ecb_ciss_ea_w` (CISS original, semanal de 1999 a 2025-05, discontinuado). Sus fechas venían en viernes y se movieron al lunes de esa semana.
  - `ecb_sovciss_ea_m`.
- **Tipos de cambio**: `ecb_eur{usd,gbp,jpy,chf,cny}_d` (fixing de referencia, divisa por EUR, desde 1999), `ecb_eer41_nominal_m` y `ecb_eer41_real_cpi_m`.
- **IPCA**: se usa el **nuevo dataflow `HICP`** (ECOICOP v2). El antiguo `ICP` y el `prc_hicp_manr` de Eurostat quedaron congelados en 2025-12 con el cambio de 2026.
  - Área euro: `ecb_hicp_index_ea_m` (índice), general, subyacente (`XEF000`), servicios, bienes industriales no energéticos, energía, alimentos, alimentos no elaborados y general sin energía (`ecb_hicp_*_yoy_ea_m`).
  - Por país (ES, DE, FR, IT, NL, PT, GR, IE): `ecb_hicp_{headline,core}_yoy_<pais>_m`.
- **Área euro**: `U2` es la composición cambiante (EA11 en 1999, EA21 desde 2026-01 con Bulgaria). Se anota en `transform_notes`.
- **Comprobaciones**:
  - DFR = −0,50 % el 2019-10-01 y el 2020-06-15. El mínimo histórico es −0,50 %.
  - MRO = 2,00 % el 2005-01-03 y 4,25 % el 2008-07-09.
  - IPCA del área euro de 2022-10 = 10,6 %.

## 2. Eurostat (`eurostat_*`)
- **API**: SDMX 2.1, `https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/<ds>/<key>?format=SDMX-CSV`, sin clave. El raw es un CSV por consulta.
- **Área euro**: se usa **`EA21`**, de composición fija retropolada (incluye Bulgaria). Si no está, se usa `EA20`. El código usado se anota en `transform_notes`. El `EA` de composición cambiante no se mezcla.
  - Grecia es `EL` en Eurostat, pero el `series_id` usa `gr`.
- **Series**:
  - `eurostat_gdp_real_<pais>_q`: PIB en volumen encadenado de 2010, desestacionalizado y corregido de calendario (`namq_10_gdp`).
  - `eurostat_gdp_{qoq,yoy}_<pais>_q`.
  - `eurostat_unemp_<pais>_m`: paro mensual desestacionalizado con definición OIT (EA, EU27, DE, ES, FR, IT, NL, PT, GR, IE).
  - `eurostat_unemp_youth_<pais>_m`: paro juvenil.
  - `eurostat_ip_<pais>_m`: producción industrial B-D, base 2021, desestacionalizada.
  - `eurostat_esi_<pais>_m`: sentimiento económico, desde 1980.
  - `eurostat_consconf_<pais>_m`: confianza del consumidor.
  - `eurostat_gov_debt_gdp_<pais>_a` y `eurostat_gov_balance_gdp_<pais>_a`: deuda y saldo del protocolo de déficit excesivo (PDE), en % del PIB, desde 1995.
  - `eurostat_gov_debt_gdp_q_<pais>_q`: deuda trimestral.
  - `eurostat_ca_balance_<pais>_q`: balanza por cuenta corriente, BPM6, en millones de EUR, sin desestacionalizar.
- **Comprobaciones**: paro en España de 2013-04 = 26,3 %; deuda española de 2020 = 119,3 % del PIB; máximo de la deuda griega = 209,4 %.

## 3. Banco de España, Boletín Estadístico (`bde_*`)
- **Fuente**: el paquete completo `be.zip`, con unos 650 CSV en latin-1 y unos 18.000 códigos de serie, que se guarda intacto en `raw/bde/`.
  - Cada CSV tiene cinco filas de metadatos: código, alias, descripción, unidades y frecuencia.
  - Los valores ausentes vienen como `_` o `...` y se convierten en NaN.
  - Las fechas trimestrales del BdE llevan el último mes del trimestre (`MAR 1995`) y se pasan al inicio del trimestre.
- **Tipos**:
  - `bde_es_mibor_1y_m`: MIBOR a 1 año desde 1977. Es la referencia hipotecaria oficial y, desde 1999, el BdE publica en ese mismo código el Euribor a 12 meses, así que hay un empalme implícito.
  - `bde_es_irph_m` (desde 1990).
  - Mercado secundario: `bde_es_letras_1y_secondary_m` (desde 1987), `bde_es_bono_3y_secondary_m` y `bde_es_gov10y_secondary_m` (desde 1991).
  - `bde_es_gov_long_yield_m` (desde 1987) y los bonos a 10 años de `bde_{de,fr,it}_gov10y_m` (desde 1980-1989).
  - Subastas: `bde_es_obligaciones_10y_auction_m` y `bde_es_letras_12m_auction_m`. Solo hay valor en los meses con subasta.
  - Tipos sintéticos de nuevas operaciones (`bde_es_loan_rate_{hh,nfc}_new_m`, `bde_es_deposit_rate_hh_new_m`, desde 2003), tipo preferencial (1981-2012) e interés legal del dinero (desde 1973).
- **Crédito y morosidad**:
  - `bde_es_credit_osr_m` y `bde_es_doubtful_loans_osr_m` (desde **1962**). Desde 2014-01 se excluyen los establecimientos financieros de crédito (EFC), lo que supone una ruptura.
  - `bde_es_npl_ratio_m`: ratio oficial de dudosidad desde 1980-12, con máximo de 13,62 % en 2013-12.
  - `bde_es_npl_ratio_computed_m`: dudosos/crédito × 100, calculado desde 1962. Coincide con el oficial donde se solapan, pero antes de 1980 la definición de "dudosos" es distinta.
- **Endeudamiento y riqueza** (cuentas financieras, desde 1995):
  - Hogares: `bde_es_hh_debt_rdi_q` y `bde_es_hh_loans_rdi_q` (en % de la renta bruta disponible), y `bde_es_hh_loans_stock_q` y `bde_es_hh_housing_loans_stock_q`.
  - Empresas: `bde_es_nfc_loans_stock_q` y `bde_es_nfc_debt_securities_stock_q`.
  - Riqueza de los hogares: `bde_es_hh_net_wealth_q` y `bde_es_hh_housing_wealth_q` (desde 1980).
- **Fiscal y sector exterior**: `bde_es_gov_debt_gdp_q` (PDE trimestral desde 1995), `bde_es_gov_balance_gdp_a`, `bde_es_ca_balance_q` y `bde_es_niip_q` (posición de inversión internacional neta).
- **Mercados**:
  - `bde_es_ibex35_m` (desde 1987) y `bde_es_madrid_general_index_m` (IGBM, desde 1985). Ambos son índices de precios, sin dividendos.
  - `bde_es_madrid_market_cap_m`: capitalización de la Bolsa de Madrid desde **1940**, con solo un dato al año (diciembre) en los primeros años.
  - `bde_es_per_m` (desde 1991) y `bde_eurostoxx_broad_m`.
- **Vivienda**: `bde_es_house_price_m2_q`, precio de tasación por m² de vivienda libre (desde 1995).
- **Empleo y actividad**:
  - `bde_es_registered_unemployed_m`: paro registrado desde **1933-07**, con rupturas metodológicas en 1985 y 2005.
  - `bde_es_ss_affiliates_m`: afiliados a la Seguridad Social desde 1982.
  - `bde_es_unemp_rate_epa_q` (EPA base 2021, desde 2002) y `bde_es_unemp_rate_sa_m` (desde 1986).
  - `bde_{es,de}_ip_m`: producción industrial desde 1975-76.
  - `bde_es_real_gdp_q` y `bde_fr_real_gdp_q`, este último desde 1950.
- **Precios**:
  - `bde_{es,de,fr,it}_cpi_m`: IPC largo, base 2015 = 100, desde **1954-55**. El de Alemania corresponde a la RFA antes de 1991.
  - `bde_es_hicp_yoy_long_m`: tasa interanual de 1962 a 2021-06, discontinuada.
  - `bde_es_ppi_m`: índice de precios industriales (IPRI), desde 1975.
- **Tipo de cambio**: `bde_usd_per_eur_ecu_m`, empalmado por el BdE: ECU de 1979 a 1998 y euro desde 1999.
- **Comprobaciones**: MIBOR a 1 año de 1990-01 = 15,64 %; ratio de morosidad de 2007 = 0,75 %; paro registrado de 1933-07 = 544.837 personas.

## 4. INE (`ine_*`)
- **API**: Tempus3 JSON, `https://servicios.ine.es/wstempus/js/ES/DATOS_SERIE/<COD>?nult=5000`. Responde con una redirección 301 a `jsCache`, que hay que seguir. El periodo se toma de `Anyo` y `FK_Periodo`: 1-12 son meses, 19-22 trimestres y 28 es anual. No conviene usar `Fecha`, que es la medianoche local expresada en UTC.
- **Series**:
  - `ine_ipc_yoy_m`: tasa interanual oficial del IPC desde **1962**. Máximo de 28,4 % en 1977-08.
  - `ine_ipc_index_m` y la subyacente `ine_ipc_core_{yoy,index}_m`, desde 2002.
  - `ine_epa_unemp_rate_q` (EPA base 2021, desde 2002; 26,94 % en 2013T1) y por edades (16-19 y 20-24).
  - `ine_gdp_volume_index_q`, `ine_gdp_{qoq,yoy}_q`: Contabilidad Nacional Trimestral (CNTR), desestacionalizada y corregida de calendario, desde 1995.
  - `ine_ipv_*_q`: índice de precios de vivienda, desde 2007.
- El índice del IPC y la tasa del mes en curso pueden ir desfasados un mes, porque la tasa incluye el dato adelantado.

## 5. Bundesbank (`bundesbank_*`), historia pre-euro
- **API**: `https://api.statistiken.bundesbank.de/rest/data/<FLOW>/<KEY>?format=csv`. Las claves antiguas `BBK01.*` ya no funcionan y ahora se usan los flujos `BBIN1`, `BBIG1` y `BBSIS`.
- **Tipos oficiales**: `bundesbank_discount_rate_m` y `bundesbank_lombard_rate_m`, de **1948-07 a 1998-12**. El tipo de descuento de 1992-08 fue 8,75 %. También está `bundesbank_base_rate_m`, el tipo básico del BGB.
- **Mercado monetario de Fráncfort**: `bundesbank_mm_{overnight,1m,3m}_m` de **1959-12 a 2012-05** (discontinuado) y `bundesbank_mm_12m_m`. También `bundesbank_fibor_{3m,12m}_m`, de 1990-07 a 1998-12.
- **Rentabilidades**:
  - `bundesbank_umlaufsrendite_m` (desde **1955**) y `bundesbank_public_bond_yield_m` (desde 1956).
  - `bundesbank_public_bond_yield_9_10y_m` (desde 1973), la mejor aproximación larga al Bund a 10 años.
  - `bundesbank_corp_bond_yield_m` (desde 1957) y `bundesbank_mortgage_pfandbrief_yield_m`.
  - `bundesbank_bund_zero_{1,2,5,10}y_m`: curva Svensson de los títulos federales, desde 1972-09.
- **Empalme** `bundesbank_de_policy_rate_spliced_m`: tipo de descuento del Bundesbank de 1948 a 1998 y MRO del BCE (valor a fin de mes) desde 1999-01.
  - Pasa de 2,5 % en 1998-12 a 3,0 % en 1999-01.
  - Ojo: el tipo de descuento era un tipo suelo, inferior al repo del Bundesbank, así que el nivel solo es comparable de forma aproximada.

## Huecos pendientes y motivos
- **PMI** (S&P Global/HCOB): es de pago y no hay fuente gratuita. Como sustitutos están el ESI y la confianza del consumidor de Eurostat.
- **Banque de France (Webstat)**: ahora exige registro y clave de API, así que no se usó. Para Francia antes del euro hay alternativas:
  - Bono a 10 años desde 1960 en FRED/OCDE (`IRLTLT01FRM156N`) y desde 1981 en `bde_fr_gov10y_m`.
  - IPC desde 1955 en `bde_fr_cpi_m`.
  - Tipos de la Banque de France del siglo XIX y principios del XX en `nber_*`, y datos anuales en JST.
- **EPA desde 1976**: Tempus solo ofrece la EPA base 2021 desde 2002, y `EPA815` va de 2002 a 2023. Las series retrospectivas de 1976 a 2001 están en INEbase/PC-Axis y no tienen API estable. Hasta añadirlas, se puede cubrir con `bde_es_unemp_rate_sa_m` (desde 1986) y con el paro registrado (desde 1933).
- **Índice del IPC español anterior a 2002 en el INE**: Tempus solo da el índice desde 2002. Para el índice largo hay que usar `bde_es_cpi_m` (desde 1954) y, para la tasa, `ine_ipc_yoy_m` (desde 1962).
- **Tipo de intervención del BdE y el interbancario español a 3 meses antes de 1999**: no están en el Boletín Estadístico actual. Hay alternativas:
  - `bis_cbpol_es`, tipo oficial del BIS, a cargo de otro agente.
  - OCDE `IR3TIB01ESM156N` (FRED/OCDE).
  - MIBOR a 1 año, desde 1977 (`bde_es_mibor_1y_m`).
- **Pre-€STR** (2017-2019) y **Euribor diario**: el BCE no publica el Euribor diario en su portal (es licencia de EMMI), solo la media mensual.
- **SovCISS**: el BCE lo actualiza con retraso. **CISS original**: discontinuado en 2025-05.
- **IPCA del área euro antes de 1996-97**: el dataflow `HICP` empieza en 1996-97. Para antes hay que usar el IPC nacional largo del BdE.

## Notas generales
- Ninguna fuente es point-in-time: son revisiones actuales. Para hacer backtests hay que aplicar retrasos de publicación (PIB unos 45-60 días, PDE anual unos 4 meses, cuentas financieras unos 3 meses).
- Las series de nivel (stocks en miles o millones de EUR, índices) tienen unidades heterogéneas. Las unidades exactas están en la columna `units` del catálogo; en `bde` se copian de la cabecera del CSV, salvo el ratio de dudosidad, que se corrige a "%".
- Las series duplicadas entre fuentes son intencionadas y llevan `series_id` distinto. Por ejemplo, el bono español a 10 años aparece en `ecb_gov10y_es_m`, `bde_es_gov10y_secondary_m` y FRED `IRLTLT01ESM156N`, y el Euribor 12m en `ecb_euribor_12m_m` y `bde_es_mibor_1y_m` desde 1999. Sirven de control cruzado.
