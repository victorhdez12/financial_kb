# Liquidez EE. UU. y global: datos (2026-10-13)

Agente de datos "Liquidez EE. UU. y global". Dos fuentes nuevas, sin tocar `src/warehouse`, `src/regime`, `Makefile`, ni hacer commits.

| fuente | script | series | filas | contenido |
|---|---|---|---|---|
| `us_liquidity` | `src/ingest/us_liquidity.py` | 55 | 98.815 | TGA diaria y flujos del DTS, emisión (DTS y subastas), recompras, extras H.4.1 y proxies de la Fed antes de 2002 |
| `cb_balance_sheets` | `src/ingest/cb_balance_sheets.py` | 38 | 13.739 | balances BoJ/SNB/BoE/PBoC, M2 de Japón, China y Reino Unido |

Ejecución: `.venv/bin/python -m src.ingest.us_liquidity` y `.venv/bin/python -m src.ingest.cb_balance_sheets` (idempotentes; reutilizan raw de menos de 20 h). Raw intacto en `~/financial_archive/raw/<fuente>/`. Series ya existentes y no duplicadas: WALCL, WRESBAL, WTREGEN, WDTGAL, RRPONTSYD, M2SL, BOGMBASE, balance del Eurosistema (`ecb_eurosystem_total_assets_w`, M2/M3 `ecb_m2_stock_m`) y los tipos de cambio DEXUSEU, DEXJPUS, DEXUSUK, DEXSZUS, DEXCHUS (curated/fred, diarios).

## 1. Cómo medir la liquidez (fórmulas propuestas, sin implementar)

**Unidades: cuidado.** WALCL, WDTGAL, WTREGEN y `usliq_tga_*` están en millones de USD; `RRPONTSYD` está en miles de millones de USD (2.553,7 el 2022-12-30). `features.py` ya resta WALCL − TGA − RRP; confirmar que el RRP se pasa a millones (x1000) antes de restar.

### 1.1 Liquidez neta de la Fed, diaria
`NetLiq_d(t) = WALCL(t) − usliq_tga_close_d(t) − 1000 × RRPONTSYD(t)`   (millones de USD)

- `WALCL` es semanal (nivel del miércoles, publicado el jueves): arrastrar con `ffill` y desplazarlo a la fecha de publicación (jueves) para no usar información futura. La TGA del DTS se publica a las 16:00 del día siguiente hábil. RRP del día t se publica el día hábil siguiente a las 08:30.
- La TGA diaria de `us_liquidity` coincide exactamente con `WDTGAL` en los 1.084 miércoles comunes (diferencia máxima 0), así que sustituye a la semanal sin romper la serie histórica (WDTGAL tiene huecos de frecuencia, esta no).
- Variante estricta de reservas: añadir la cuenta del programa de financiación suplementaria `usliq_sfp_close_d` (2008-2012) a la TGA: `TGA_total = usliq_tga_close_d + usliq_sfp_close_d`. Antes de 2008 no existe; el SFP también drena reservas.
- Valores de control: 2020-03-02 = 3,75 billones $; 2022-12-30 = 5,55; 2023-06-02 = 6,22; 2026-10-08 = 5,86.

### 1.2 Liquidez global en USD
`GlobalLiq_m(t) = WALCL_m + ECB_m × EURUSD_m + BoJ_m / USDJPY_m + SNB_m / USDCHF_m + PBoC_m / USDCNY_m [+ BoE_m × GBPUSD_m]`

Series exactas (medias mensuales de cada balance; tipos de cambio medios del mes, ya en `fred`):

| pieza | serie | unidad original | a billones de USD |
|---|---|---|---|
| Fed | `WALCL` | M USD | / 1e6 |
| Eurosistema | `ecb_eurosystem_total_assets_w` | M EUR | / 1e6 × `DEXUSEU` |
| BoJ | `cbbs_boj_total_assets_m` | 100 M JPY | / 1e4 / `DEXJPUS` |
| SNB | `cbbs_snb_total_assets_m` | M CHF | / 1e6 / `DEXSZUS` |
| PBoC | `cbbs_pboc_total_assets_m` | M CNY | / 1e6 / `DEXCHUS` |
| BoE | sin total moderno (ver 5) | | |

Valores de control (billones $, medias mensuales): Fed+BCE+BoJ+SNB = 4,0 (dic-2007), 15,5 (dic-2019), 25,9 (mar-2022, máximo), 19,9 (jun-2025); con PBoC 6,3 / 20,8 / 32,1 / 26,2. Sept-2026: Fed 6,74, BCE 6,80, BoJ 4,00 (SNB y PBoC en retraso, ver huecos). La liquidez global "a cuatro" (sin BoE ni PBoC) se puede calcular desde 2002-12 hasta el último mes con SNB (2026-08); la versión con PBoC solo hasta 2025-06 (retraso del espejo del FMI).
Aviso metodológico: el efecto de tipos de cambio domina a veces la variación en USD; considerar también la versión a tipos constantes (suma en USD con FX fijo de la fecha base).

### 1.3 Impulso
`Impulso_k(t) = X(t) − X(t−k)` en billones de USD (o `% = X(t)/X(t−k) − 1`), con k = 13 y 26 semanas para series semanales/diarias (k = 3 y 6 meses en las mensuales). Se puede normalizar por PIB nominal de EE. UU. o por la capitalización. Ejemplo (global a cuatro): −0,41 billones a 3 meses y −0,69 a 6 meses a agosto de 2026. Para la Fed, aplicar el mismo impulso a `NetLiq_d` con ventana de 65 y 130 días hábiles.

### 1.4 Piezas complementarias ya disponibles
- Oferta de títulos del Tesoro (la parte "fiscal" de la liquidez): `usliq_dts_bills_net_m` y `usliq_dts_coupons_net_m` (emisión neta mensual de letras y de cupones desde 2005-10). Letras netas positivas con RRP alto = financiación absorbida del colchón RRP, no de reservas; cupones netos = drenaje de ahorro a largo plazo. Cuota de letras en subastas: `usliq_auc_bill_share_m`.
- Flujos diarios de caja: `usliq_tga_deposits_exdebt_d` menos `usliq_tga_withdrawals_exdebt_d` = déficit/superávit primario de caja del día; el resto de la variación de la TGA es la emisión neta de deuda (`usliq_tga_debt_issues_d − usliq_tga_debt_redemptions_d`).
- Recompras del Tesoro (apoyo a la liquidez del mercado): `usliq_buyback_*`.
- Fed: `TREAST`, `usliq_fred_wshobl`, `usliq_fred_wshonbnl`, WSHOMCB (QT/QE por tipo), ventana de descuento `WLCFLPCL` + `usliq_fred_wlcfll/wlcflsecl/wlcflscl`, repos FIMA `usliq_fred_h41resppalgtrfnww`, swaps `SWPT`.

## 2. Verificación (valores conocidos)

| comprobación | resultado |
|---|---|
| TGA diaria vs `WDTGAL` (FRED) en miércoles comunes | 1.084 coincidencias, diferencia 0 |
| TGA: 2020-05-29 (pico del Covid) | 1,449 billones $ |
| TGA 2023 (techo de deuda): cierre 2023-03-01 / 2023-05-31 / mínimo anual 2023-06-01 | 177,7 / 48,5 / 22,9 miles de millones $ |
| RRP 2022-12-30 (`RRPONTSYD`, ya existente) | 2.553,7 mM$ (2,55 billones) |
| Identidad `ΔTGA = depósitos − retiros` | residuo dentro de ±5 M$ en ~95 % de los días; las excepciones son días con movimientos de las cuentas SFP/T&L/instituciones financieras de 2008-2010 y redondeos |
| Emisión neta DTS vs variación de `ust_mspd_marketable_m` | diferencia media 3.947 M$ al mes (máx. 26.278 M$): el MSPD incluye accretion TIPS e intereses capitalizados y el DTS es de caja |
| Subastas (públicas, ex SOMA) vs emisión bruta DTS | ratio mediano 0,97 (varias fechas de emisión y recompras fuera de subasta explican el resto) |
| China M2 (Eastmoney) vs FRED/OCDE `MYAGM2CNM189N` | idéntico en 2008-01 (41,78 billones CNY) y 2019-08 (193,55) |
| China M2 interanual calculado vs publicado | 7,48 % vs 7,5 % (ago-2026) |
| SNB total activo ene-2022 | 1,063 billones CHF (correcto) |
| BoJ total activo sept-2026 | 625,0 billones JPY; coincide con FRED `JPNASSETS` |
| BoE M4 ago-2026 | 3,31 billones GBP |
| PBoC total activo jun-2025 | 45,8 billones CNY |

## 3. Qué se ha ingerido

### 3.1 `us_liquidity` (FiscalData API + FRED)
- **TGA diaria** (`usliq_tga_close_d`, 2005-10-03 a 2026-10-08, 5.280 obs). La API del DTS solo empieza el 2005-10-03; antes hay que usar `WTREGEN`/`WDTGAL` (2002-12+) o los PDF antiguos (hueco). La serie empalma tres etiquetas distintas ("Federal Reserve Account" hasta 2021-09-30, "Treasury General Account (TGA)" hasta 2022-04-15, "TGA Closing Balance" desde 2022-04-18; en esta última el cierre viene en la columna `open_today_bal`). Más `usliq_sfp_close_d` (2008-09 a 2022-04) y `usliq_tl_close_d` (cuentas Tax & Loan en bancos comerciales, 2005-2012; no es dinero en la Fed).
- **Flujos diarios**: depósitos y retiros totales, ex deuda y deuda emitida/amortizada (6 series `usliq_tga_*_d`). Se excluyen las líneas "Sub-Total" (duplicaban 2022-04 a 2023-09) y las transferencias Table V en las versiones "ex deuda".
- **Emisión**: (a) DTS tabla III-A diaria por tipo (letras, notas, bonos; emisiones y amortizaciones) y mensuales bruta/amortización/neta de letras, cupones y total marketable (2005-10+); (b) subastas, emisión bruta mensual por tipo y fecha de emisión desde 1979-11 (letras desde 1980, TIPS desde 1997, FRN desde 2014; importe público = `total_accepted − soma_accepted`; incluye la cuota de letras y las ampliaciones SOMA); (c) recompras mensuales: dos programas, 2000-03 a 2002-04 y 2024-05+, por tipo de operación.
- **Fed (FRED)**: 11 series H.4.1 semanales de detalle (préstamos totales, crédito estacional y secundario, activos en divisas, depósitos de oficiales extranjeros, primas, bills, notas y bonos, agencias, repos FIMA, TREAST) y proxies anteriores a 2002 (7 series, ver 4).

### 3.2 `cb_balance_sheets`
- **BoJ** (API oficial de series temporales, 1998-04+): total activo, JGB, bonos corporativos, ETF, préstamos, activos en divisas, billetes, depósitos corrientes (reservas), depósitos del gobierno, base monetaria (1970+) y saldo de cuentas corrientes (1981+); M1/M2/M3 desde 2003-04.
- **SNB** (data.snb.ch, 1996-12+): total activo, oro, inversiones en divisas, billetes, depósitos a la vista nacionales y extranjeros.
- **BoE** (IADB): M4 (`cbbs_boe_m4_m`, 1982-06+) y el total de activos del Bank Return semanal 2006-2014.
- **PBoC** (FMI MFS vía DBnomics, 1985-06 a 2025-06): total activo y dinero de reserva.
- **China** M0/M1/M2 mensual desde 2008-01 y M2 interanual (espejo Eastmoney de los datos del PBoC).
- **FRED** (continuidad histórica): `JPNASSETS`, `UKASSETS` (2006-2014), `SNBMONTBASE`, M2 Japón (1967-2017), M2 China (1998-2019), M3 OCDE Japón/China/UK y M4 Reino Unido (1982-2016).
- **Tipos de cambio**: no se añade nada; ya están `DEXUSEU`, `DEXJPUS`, `DEXUSUK`, `DEXSZUS` y `DEXCHUS` diarios.

## 4. Balance de la Fed antes de 2002
FRED/H.4.1 estructurado empieza el 2002-12-18 (`WALCL`). Para antes **no hay serie semanal de total de activos** accesible por API; lo que cubre el hueco:
- `BOGMBASE` (existente, base monetaria, 1959+) y `usliq_fred_ambsl` (base ajustada St. Louis, **1918-2019**, mensual) y `usliq_fred_base` (quincenal 1984-2019): proxy más largo del tamaño de la Fed.
- `TOTRESNS` (existente, reservas totales, 1959+) y `usliq_fred_bognonbr` (reservas no prestadas, 1959-2013), `BORROW` (existente, préstamos de la Fed, 1959+).
- NBER: `usliq_fred_m14066usm144nnbr` (valores y letras en poder de los bancos de la Reserva, 1914-1969), oro (1914-1949) y depósitos (1914-1949).
- Hueco: 1969-2002 sin activos totales de la Fed (solo base, reservas y préstamos). Las tablas H.4.1 en HTML de 1996-2002 existen en federalreserve.gov/releases/h41 pero no son estructuradas; no se han raspado.

## 5. Huecos y limitaciones
- **BoE posterior a 2014**: IADB no publica ya el total del balance; solo el Bank Return hasta 2014-09 y `UKASSETS` mensual hasta 2014-09. No se encontró el código IADB de reservas ni de las tenencias del APF; en la web del banco solo hay una foto de las tenencias de gilts del APF (488,1 mM GBP a la fecha de descarga) en `table-for-website.xlsx`. Para la liquidez global se puede omitir la BoE o estimarla con M4/APF; decisión del coordinador.
- **PBoC**: el espejo DBnomics del FMI llega solo a 2025-06 (retraso de ~1 año); el PBoC publica su balance mensual en su web (HTML/PDF no estructurado, no raspado). La serie de China M2 es de un agregador (Eastmoney), no del PBoC directamente (licencia anotada; contrastado con FRED 2008-2019 y con el interanual publicado).
- **SNB**: último dato 2026-08 (publicación mensual con retraso).
- **Eurosistema**: ya existe; la entrada es semanal con fecha del lunes.
- **M2 de Japón**: la serie del BoJ (2003-04+) tiene definición distinta de la antigua M2+CD de FRED (1967-2017); no empalmar sin ajuste (anotado en `transform_notes`).
- **DTS anterior a 2005-10**: no está en la API (hueco); `WTREGEN` cubre 2002-12+ semanal.
- **Subastas**: el mes en curso se descarta; en los años 80 faltan letras (empiezan 1980); TIPS se cuentan a valor nominal.
- **Buybacks**: dos programas separados por 22 años; 228 operaciones.
- **Ventana de descuento**: cubierto con `WLCFLPCL` (existente), `WLCFLL`, seasonal y secondary; el crédito primario antes de 2002 no está (hay solo la tasa de descuento histórica `DISCOUNT`, 1934-2002 en FRED, no ingerida).
- RRP a nivel de contraparte, uso de la facilidad SRF/standing repo: `RPONTSYD` existente; no se amplió.
- `BASE` y `usliq_fred_base`: quincenal; la frecuencia queda como `W` en el catálogo (aprox.).

## 6. Resumen
- **Fuentes nuevas**: 2 (`us_liquidity`: FiscalData + FRED; `cb_balance_sheets`: BoJ, SNB, BoE, FMI/DBnomics, Eastmoney, FRED). 93 series, 112.554 filas, sin colisiones de `series_id` con otras fuentes.
- **Cobertura**: TGA diaria 2005-10 a 2026-10; emisión DTS 2005-10+, subastas 1979+; balances de bancos centrales 1996/1998 a 2026-08/09 (PBoC 2025-06); dinero amplio China 2008+, Japón 2003+ (1967-2017 FRED), UK 1982+; Fed antes de 2002 solo por proxies.
- **Huecos**: ver 5 (BoE posterior a 2014, PBoC desde 2025-07, Fed 1969-2002, DTS antes de 2005).
- **Pendiente de auditoría**: debe pasar la checklist del auditor antes de entrar al warehouse. Flujos y subastas de los meses con datos preliminares sin verificar.
- **Cambios sugeridos en `src/warehouse/build.py` (no aplicados)**: (1) añadir `us_liquidity` y `cb_balance_sheets` a la lista de fuentes curadas (o confirmar que se descubren por glob de `curated/*`); (2) las categorías usadas son `liquidity` y `money`, ya válidas; (3) ninguna regla `PIT_RULES` hace falta (todo `observed`); la publicación real del DTS es el día hábil siguiente, la de WALCL el jueves, por lo que `asof` debería aplicar retardo si se usa en el clasificador; (4) en `src/regime/features.py` (decisión del coordinador): sustituir `tga` semanal por `usliq_tga_close_d` y comprobar que `rrp` está en millones (RRPONTSYD viene en miles de millones), y la variable `net_liquidity` hoy queda NaN antes de que exista TGA; con `usliq_tga_close_d` y `WALCL` ya se puede calcular desde 2005-10.

## Apéndice A: series de `us_liquidity`
| series_id | frec | unidades | inicio | fin | n |
|---|---|---|---|---|---|
| `usliq_auc_bill_gross_m` | M | USD millions | 1980-01-01 | 2026-09-01 | 561 |
| `usliq_auc_bill_share_m` | M | Percent | 1980-01-01 | 2026-09-01 | 561 |
| `usliq_auc_bond_gross_m` | M | USD millions | 1979-11-01 | 2026-09-01 | 315 |
| `usliq_auc_cmb_gross_m` | M | USD millions | 1980-03-01 | 2026-05-01 | 323 |
| `usliq_auc_count_m` | M | Count | 1979-11-01 | 2026-09-01 | 562 |
| `usliq_auc_coupons_gross_m` | M | USD millions | 1979-11-01 | 2026-09-01 | 541 |
| `usliq_auc_frn_gross_m` | M | USD millions | 2014-01-01 | 2026-09-01 | 138 |
| `usliq_auc_note_gross_m` | M | USD millions | 1979-11-01 | 2026-09-01 | 535 |
| `usliq_auc_soma_addon_m` | M | USD millions | 2008-04-01 | 2026-09-01 | 222 |
| `usliq_auc_tips_gross_m` | M | USD millions | 1997-02-01 | 2026-09-01 | 245 |
| `usliq_buyback_accepted_m` | M | USD millions | 2000-03-01 | 2026-09-01 | 66 |
| `usliq_buyback_cashmgmt_m` | M | USD millions | 2024-09-01 | 2026-09-01 | 10 |
| `usliq_buyback_liqsupport_m` | M | USD millions | 2024-05-01 | 2026-09-01 | 29 |
| `usliq_dts_bills_gross_m` | M | USD millions | 2005-10-01 | 2026-09-01 | 252 |
| `usliq_dts_bills_issues_d` | D | USD millions | 2005-10-03 | 2026-10-08 | 5280 |
| `usliq_dts_bills_net_m` | M | USD millions | 2005-10-01 | 2026-09-01 | 252 |
| `usliq_dts_bills_redeem_m` | M | USD millions | 2005-10-01 | 2026-09-01 | 252 |
| `usliq_dts_bills_redemptions_d` | D | USD millions | 2005-10-03 | 2026-10-08 | 5280 |
| `usliq_dts_bonds_issues_d` | D | USD millions | 2005-10-03 | 2026-10-08 | 5280 |
| `usliq_dts_bonds_redemptions_d` | D | USD millions | 2005-10-03 | 2026-10-08 | 5280 |
| `usliq_dts_coupons_gross_m` | M | USD millions | 2005-10-01 | 2026-09-01 | 252 |
| `usliq_dts_coupons_net_m` | M | USD millions | 2005-10-01 | 2026-09-01 | 252 |
| `usliq_dts_coupons_redeem_m` | M | USD millions | 2005-10-01 | 2026-09-01 | 252 |
| `usliq_dts_marketable_gross_m` | M | USD millions | 2005-10-01 | 2026-09-01 | 252 |
| `usliq_dts_marketable_net_m` | M | USD millions | 2005-10-01 | 2026-09-01 | 252 |
| `usliq_dts_marketable_redeem_m` | M | USD millions | 2005-10-01 | 2026-09-01 | 252 |
| `usliq_dts_notes_issues_d` | D | USD millions | 2005-10-03 | 2026-10-08 | 5280 |
| `usliq_dts_notes_redemptions_d` | D | USD millions | 2005-10-03 | 2026-10-08 | 5280 |
| `usliq_fred_ambsl` | M | Billions of Dollars | 1918-01-01 | 2019-11-01 | 1223 |
| `usliq_fred_base` | W | Billions of Dollars | 1984-02-15 | 2019-12-18 | 936 |
| `usliq_fred_bogambsl` | M | Billions of Dollars | 1959-01-01 | 2013-05-01 | 653 |
| `usliq_fred_bognonbr` | M | Billions of Dollars | 1959-01-01 | 2013-05-01 | 653 |
| `usliq_fred_h41resppalgtrfnww` | W | Millions of U.S. Dollars | 2002-12-18 | 2026-10-07 | 1243 |
| `usliq_fred_m14062usm027nnbr` | M | Billions of Dollars | 1914-11-01 | 1949-05-01 | 415 |
| `usliq_fred_m14066usm144nnbr` | M | Millions of Dollars | 1914-11-01 | 1969-10-01 | 660 |
| `usliq_fred_m14070usm027nnbr` | M | Billions of Dollars | 1914-11-01 | 1949-04-01 | 414 |
| `usliq_fred_treast` | W | Millions of U.S. Dollars | 2002-12-18 | 2026-10-07 | 1243 |
| `usliq_fred_wdfol` | W | Millions of U.S. Dollars | 2002-12-18 | 2026-10-07 | 1243 |
| `usliq_fred_wfcda` | W | Millions of U.S. Dollars | 2002-12-18 | 2026-10-07 | 1243 |
| `usliq_fred_wlcfll` | W | Millions of U.S. Dollars | 2002-12-18 | 2026-10-07 | 1243 |
| `usliq_fred_wlcflscl` | W | Millions of U.S. Dollars | 2002-12-18 | 2026-10-07 | 1243 |
| `usliq_fred_wlcflsecl` | W | Millions of U.S. Dollars | 2002-12-18 | 2026-10-07 | 1243 |
| `usliq_fred_wshobl` | W | Millions of U.S. Dollars | 2002-12-18 | 2026-10-07 | 1243 |
| `usliq_fred_wshofadsl` | W | Millions of U.S. Dollars | 2002-12-18 | 2026-10-07 | 1243 |
| `usliq_fred_wshonbnl` | W | Millions of U.S. Dollars | 2002-12-18 | 2026-10-07 | 1243 |
| `usliq_fred_wupsho` | W | Millions of U.S. Dollars | 2002-12-18 | 2026-10-07 | 1243 |
| `usliq_sfp_close_d` | D | USD millions | 2008-09-18 | 2022-04-15 | 3413 |
| `usliq_tga_close_d` | D | USD millions | 2005-10-03 | 2026-10-08 | 5280 |
| `usliq_tga_debt_issues_d` | D | USD millions | 2005-10-03 | 2026-10-08 | 5280 |
| `usliq_tga_debt_redemptions_d` | D | USD millions | 2005-10-03 | 2026-10-08 | 5280 |
| `usliq_tga_deposits_d` | D | USD millions | 2005-10-03 | 2026-10-08 | 5280 |
| `usliq_tga_deposits_exdebt_d` | D | USD millions | 2005-10-03 | 2026-10-08 | 5280 |
| `usliq_tga_withdrawals_d` | D | USD millions | 2005-10-03 | 2026-10-08 | 5280 |
| `usliq_tga_withdrawals_exdebt_d` | D | USD millions | 2005-10-03 | 2026-10-08 | 5280 |
| `usliq_tl_close_d` | D | USD millions | 2005-10-03 | 2012-09-28 | 1759 |

## Apéndice B: series de `cb_balance_sheets`
| series_id | frec | unidades | inicio | fin | n |
|---|---|---|---|---|---|
| `cbbs_boe_bankreturn_assets_w` | W | GBP millions | 2006-05-24 | 2014-09-24 | 437 |
| `cbbs_boe_m4_m` | M | GBP millions | 1982-06-01 | 2026-08-01 | 531 |
| `cbbs_boj_banknotes_m` | M | 100 million yen (JPY) | 1998-04-01 | 2026-09-01 | 342 |
| `cbbs_boj_corpbonds_m` | M | 100 million yen (JPY) | 2009-03-01 | 2026-09-01 | 211 |
| `cbbs_boj_currentacct_avg_m` | M | 100 million yen (JPY) | 1981-04-01 | 2026-09-01 | 546 |
| `cbbs_boj_currentdep_m` | M | 100 million yen (JPY) | 1998-04-01 | 2026-09-01 | 342 |
| `cbbs_boj_etf_m` | M | 100 million yen (JPY) | 2010-12-01 | 2026-09-01 | 190 |
| `cbbs_boj_fxassets_m` | M | 100 million yen (JPY) | 1998-04-01 | 2026-09-01 | 342 |
| `cbbs_boj_govdep_m` | M | 100 million yen (JPY) | 1998-04-01 | 2026-09-01 | 342 |
| `cbbs_boj_jgb_m` | M | 100 million yen (JPY) | 2001-04-01 | 2026-09-01 | 306 |
| `cbbs_boj_jgs_m` | M | 100 million yen (JPY) | 1998-04-01 | 2026-09-01 | 342 |
| `cbbs_boj_loans_m` | M | 100 million yen (JPY) | 1998-04-01 | 2026-09-01 | 342 |
| `cbbs_boj_monbase_avg_m` | M | 100 million yen (JPY) | 1970-01-01 | 2026-09-01 | 681 |
| `cbbs_boj_total_assets_m` | M | 100 million yen (JPY) | 1998-04-01 | 2026-09-01 | 342 |
| `cbbs_cn_m0_m` | M | CNY millions | 2008-01-01 | 2026-08-01 | 224 |
| `cbbs_cn_m1_m` | M | CNY millions | 2008-01-01 | 2026-08-01 | 224 |
| `cbbs_cn_m2_m` | M | CNY millions | 2008-01-01 | 2026-08-01 | 224 |
| `cbbs_cn_m2_yoy_m` | M | Percent | 2008-01-01 | 2026-08-01 | 224 |
| `cbbs_fred_jpnassets` | M | 100 Million Yen | 1998-04-01 | 2026-09-01 | 342 |
| `cbbs_fred_mabmm301cnm189s` | M | Yuan Renminbi | 1999-01-01 | 2018-12-01 | 240 |
| `cbbs_fred_mabmm301gbm189s` | M | Pound Sterling | 1986-12-01 | 2023-11-01 | 444 |
| `cbbs_fred_mabmm301jpm189s` | M | Yen | 1980-01-01 | 2023-11-01 | 527 |
| `cbbs_fred_myagm2cnm189n` | M | National Currency | 1998-12-01 | 2019-08-01 | 249 |
| `cbbs_fred_myagm2jpm189n` | M | National Currency | 1967-01-01 | 2017-02-01 | 602 |
| `cbbs_fred_myagm4gbm189n` | M | National Currency | 1982-06-01 | 2016-08-01 | 411 |
| `cbbs_fred_snbmontbase` | M | CHF Millions | 1950-01-01 | 2026-08-01 | 920 |
| `cbbs_fred_ukassets` | M | Millions of Pounds | 2006-05-01 | 2014-09-01 | 101 |
| `cbbs_jp_m1_avg_m` | M | 100 million yen (JPY) | 2003-04-01 | 2026-08-01 | 281 |
| `cbbs_jp_m2_avg_m` | M | 100 million yen (JPY) | 2003-04-01 | 2026-08-01 | 281 |
| `cbbs_jp_m3_avg_m` | M | 100 million yen (JPY) | 2003-04-01 | 2026-08-01 | 281 |
| `cbbs_pboc_reserve_money_m` | M | CNY millions | 1985-06-01 | 2025-06-01 | 369 |
| `cbbs_pboc_total_assets_m` | M | CNY millions | 1985-06-01 | 2025-06-01 | 357 |
| `cbbs_snb_banknotes_m` | M | CHF millions | 1996-12-01 | 2026-08-01 | 357 |
| `cbbs_snb_fxinv_m` | M | CHF millions | 1996-12-01 | 2026-08-01 | 357 |
| `cbbs_snb_gold_m` | M | CHF millions | 1996-12-01 | 2026-08-01 | 357 |
| `cbbs_snb_sightdep_dom_m` | M | CHF millions | 1996-12-01 | 2026-08-01 | 357 |
| `cbbs_snb_sightdep_for_m` | M | CHF millions | 1996-12-01 | 2026-08-01 | 357 |
| `cbbs_snb_total_assets_m` | M | CHF millions | 1996-12-01 | 2026-08-01 | 357 |
