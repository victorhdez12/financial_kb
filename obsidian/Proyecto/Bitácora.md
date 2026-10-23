---
tipo: bitacora
---

# Bitácora del proyecto

Las entradas más recientes van arriba. Ver también [[Proyecto/Estado del proyecto]] y [[Proyecto/Agentes]].

## 2026-10-12

- **Revisión del vault y del estado del proyecto.** Las Fases 0 y 1 están hechas y la 2a, sin commitear. El vault está casi vacío: las carpetas Assets, Countries, Decisions, Indicators, News, Strategies y Theses no tienen notas, y el índice enlaza a notas que no existen (Liquidity, Monetary Policy, Real Rates, Valuation).
- **No había agentes definidos como ficheros** (ni `.claude/agents/` en el proyecto ni en `~/.claude/agents`). Solo se habían usado agentes puntuales el 7 oct (5 para el plan y 2 para revisar la Fase 1).
- **Decisión del usuario:** el proyecto sigue en la fase de datos. El abogado del diablo no hace falta todavía; ahora toca recopilar, limpiar y almacenar, con un agente que supervise y audite los datos.
- **Inventario previo:** unas 3.700 series. Faltaban:
  - casi todo Europa (BCE, Eurostat, Banco de España, INE);
  - BLS (solo había 8 series);
  - ALFRED (solo 7 series);
  - el crédito de EE. UU. por sector (crédito bancario, crédito al consumo, deuda por sectores).
- **Lanzados 4 agentes en paralelo:** recopilador de EE. UU., recopilador de Europa/BCE/España, recopilador internacional y auditor de datos (instrucciones en [[Proyecto/Agentes]]).
- **El agente de Europa se cortó** por un error de conexión (ECONNRESET) cuando iba por el Bundesbank. Se reanudó desde ese punto.
- **Auditor terminado.** Resultados en `docs/data/audit_2026-10-12.md`, el CSV `docs/data/audit_2026-10-12_series.csv` (3.173 filas: 3 críticas y 262 altas) y el código en `src/audit/`. Problemas principales en [[Proyecto/Estado del proyecto#Problemas abiertos (auditoría del 2026-10-12)]].
  - **Verde:** boe_millennium_uk, damodaran, gpr, jst_macrohistory, ken_french, sipri, spf.
  - **Ámbar:** fred, alfred, bis, maddison, nber_macrohistory, nyfed, rtdsm, shiller, wb_pinksheet.
  - **Rojo:** gold, imf_cofer, warehouse.
  - **Bien:** el IPC de FRED, el del BLS y el de Shiller coinciden desde 1913; el paro y las nóminas coinciden entre FRED y BLS; no hay fechas duplicadas.
- **Fuentes nuevas que aparecían durante la mañana:**
  - EE. UU.: fred_us, fed_yieldcurve, us_treasury, nyfed_hhdc, us_hist_labor, measuringworth.
  - Internacional: bis_ext, oecd, imf_weo, imf_gdd, imf_hpdd, wb_wdi.
  - Europa: todavía nada en curated.
- **Recopilador internacional terminado: 7 fuentes y 2.207 series** (doc: `docs/data/international_macro.md`).

  | fuente | series | contenido | cobertura |
  |---|---|---|---|
  | bis_ext | 366 | tipos de cambio efectivos, liquidez global, IPC largo | 1662 → 2026-09 |
  | oecd | 309 | indicadores adelantados, confianza, paro, tipos, IPC | 1914 → 2026-09 |
  | imf_weo | 955 | previsiones del FMI de abril de 2026, 27 economías; las previsiones en `*_proj` con la nota `FORECAST` | 1980 → 2031 |
  | imf_hpdd | 31 | deuda pública/PIB desde 1800 | 1800 → 2015 |
  | imf_gdd | 155 | deuda de hogares, empresas y sector público en % del PIB | 1950 → 2024 |
  | wb_wdi | 375 | 16 indicadores del Banco Mundial | 1960 → 2025 |
  | measuringworth | 16 | tipos de EE. UU. desde 1798, IPC de EE. UU. desde 1774, Reino Unido desde 1209 | 1209 → 2025 |

  - **Revisado sin cambios:** JST sigue en la R6; Reinhart-Rogoff ya estaba en los eventos.
  - **Huecos:**
    - El WEO de oct-2026 sale a mediados de mes: hay que volver a ejecutarlo y guardar antes la versión de abril.
    - Las estadísticas financieras del FMI (IFS) no están curadas.
    - Paro de la OCDE: no hay mensual del área euro ni de Suiza.
    - `oecd_ir3m_gbr` está parada en 2026-02.
    - Las series diarias del BIS no están curadas, ni las estadísticas bancarias internacionales.
    - HPDD termina en 2015.
    - Global Financial Data es de pago.
  - **Cambios propuestos para la base de datos:**
    - la carga funciona sin tocar nada (glob `curated/*/*`);
    - añadir `is_forecast` para excluir las previsiones;
    - normalizar `country` a ISO3 (bis usa nombres);
    - opcional: una vista de equivalencias entre fuentes que miden lo mismo.
- **Recopilador de Europa/BCE/España terminado: 5 fuentes y 299 series** (doc: `docs/data/europe_macro_financial.md`; scripts `src/ingest/{_europe_common,ecb,eurostat,bde,ine,bundesbank}.py`).

  | fuente | series | cobertura | contenido |
  |---|---|---|---|
  | ecb | 116 | 1980 → 2026-10 | tipo de depósito/MRO/MLF, €STR, EONIA, Euribor, curvas AAA y de todos los bonos, bonos a 10 años de 11 países y sus diferenciales, M1-M3, préstamos, tipos bancarios, encuesta de préstamos, balance, CISS y SovCISS, tipos de cambio, inflación |
  | eurostat | 98 | 1980 → 2026-09 | PIB, paro (también juvenil), producción industrial, confianza, deuda y déficit, cuenta corriente |
  | bde | 53 | 1933 → 2026-09 | MIBOR desde 1977, Letras, IRPH, morosidad desde 1962, deuda de hogares y empresas, IBEX, PER, vivienda, paro registrado desde 1933, IPC de ES/DE/FR/IT desde 1954 |
  | ine | 13 | 1962 → 2026-09 | IPC desde 1962, subyacente, EPA desde 2002, PIB, vivienda |
  | bundesbank | 19 | 1948 → 2026-10 | tipo de descuento y Lombard 1948-98, Umlaufsrendite desde 1955, curva Svensson desde 1972 |

  - **Comprobado:** tipo de depósito a −0,50 % en 2019-22, inflación del área euro del 10,6 % en oct-2022, paro en España del 26,3 % en abr-2013 y diferencial griego de 2.739 pb.
  - **Empalmes anotados:** EONIA→€STR (unos −8,5 pb), tipo de descuento del Bundesbank→MRO y MIBOR→Euribor.
  - **Huecos:**
    - PMI (de pago).
    - Banque de France (ahora exige clave).
    - EPA 1976-2001 (solo en INEbase/PC-Axis).
    - IPC del INE anterior a 2002 (cubierto por `bde_es_cpi_m`).
    - Tipo del BdE anterior a 1999.
    - Euribor diario (licencia de EMMI).
    - Inflación del área euro anterior a 1996.
    - El CISS original está discontinuado desde mayo de 2025.
  - **Recomendaciones:**
    - ejecutar `ecb` antes que `bundesbank` (el empalme alemán depende de `ecb_mro_d`);
    - una vista mensual para las 37 series diarias (unas 286.000 filas);
    - una vista de fuente preferente cuando la misma serie esté en varias fuentes.
- **Recopilador de EE. UU. terminado: unas 3.500 series** (doc: `docs/data/us_macro_credit.md`).

  | fuente | series | cobertura | contenido |
  |---|---|---|---|
  | alfred (ampliado) | 14 (antes 7) | vintages hasta 2026-10 | + ICSA, TCU, M2SL, PPIACO, GDP, PCEPI, CFNAI |
  | fred_us | 1.691 | 1901 → 2026-10 | encuesta SLOOS completa (636), charge-offs y morosidad (260), curva del Tesoro e históricos (181), crédito al consumo (159), crédito bancario semanal (66), hipotecas (57), JOLTS (41), paro U1-U5 y por duración, nóminas por sector desde 1939, term premium Kim-Wright, deuda por sector desde 1945, balance de la Fed semanal desde 1914, fiscal desde 1901, beneficios desde 1929 |
  | fed_yieldcurve | 73 | 1961 → 2026-10 diario | curva nominal GSW de 1 a 30 años, TIPS y breakevens |
  | us_treasury | 25 | 1790 → 2026-10 | deuda desde 1790, Debt to the Penny, tipo medio, intereses |
  | nyfed_hhdc | 103 | 1999 → 2026-Q2 | deuda de los hogares: saldos, morosidad, ejecuciones |
  | nber_macrohistory (ampliado) | 1.627 (antes 39) | 1820 → años 1960-70 | macrohistoria completa |
  | shiller_housing | 9 | 1890 → 2026-07 | precio de la vivienda y tipo largo desde 1890 |
  | us_hist_labor | 2 | 1890 → 2010 | paro anual (Romer/Coen) |

  - **Comprobado:**
    - el rendimiento GSW a 10 años coincide con DGS10 (mediana +0,06 pp);
    - los intereses del año fiscal 2025 son 1,22 billones de USD;
    - deuda federal de 71 M$ en 1790 y 40,17 billones en 2026;
    - deuda de los hogares de 18,77 billones en 2026-Q2.
  - **Huecos:**
    - Lebergott y Weir (de pago; se usa Romer/Coen, que da un paro en los años 30 más bajo);
    - Homer & Sylla (es un libro);
    - la Z.1 completa (falta el zip de la Fed);
    - FRED release 388 (estadísticas bancarias y monetarias 1914-41, 1.993 series);
    - los tipos repo BGCR/TGCR;
    - el MTS anterior a 1980.
  - **Recomendaciones para la base de datos:**
    - deduplicar el catálogo alfred/fred dando prioridad a fred;
    - añadir `realtime_end` a `OBS_COLS`;
    - normalizar a 1 de enero las series fiscales anuales (FYFR, FYONET, FYFSD, FYOINT);
    - unos 2,7 M de filas más;
    - marcar TCU, ICSA y M2SL con `vintage=True` en `features.py`.
- **Los 4 agentes de datos han terminado.** En total se han añadido unas 6.000 series nuevas: ~3.500 de EE. UU., 2.207 internacionales y 299 de Europa.
- **El usuario aprueba** corregir el fallo del IPC, ajustar `build.py`, reconstruir la base de datos y el régimen, volver a auditar y hacer commit de la fase de datos.
- **Hecho (tarde).** Detalle completo en `docs/data/audit_2026-10-12_tarde.md`.
  - **Fallo del IPC corregido** con `regularize()` en `features.py` y Sahm tolerante a un mes ausente. Inflación interanual de sep-2026: 2,76 → **2,45 %**; tipo real: 0,99 → **1,30 pp**. Los cuadrantes no cambian en ningún mes.
  - **`build.py`:**
    - una fila de catálogo por serie;
    - `pit_role` (forecast/lookahead fuera de `obs_latest`, en la vista `forecasts`);
    - `country_iso3`;
    - `realtime_end`;
    - años fiscales fechados al 1 de enero;
    - `monthly` como tabla.
  - **Base de datos reconstruida:** 9.623 series y 5,4 M de filas.
  - **TED:** límite de antigüedad (`MAX_STALE_DAYS`) en `asof.py`; ya no vota y el semáforo de crédito queda con 9 indicadores.
  - **Oro:** en los análogos, solo desde 1971-08.
  - **ALFRED también en TCU, CFNAI, M2SL y GDP.** Cambian 39 meses de liquidez y hoy pasa de neutral a **escasa** (−0,51).
  - **Limpieza en las ingestas:** COFER (sin los stubs de 1999 y con los ceros como NaN), `fred_us` (9999 → NaN) y OECD (ceros en índices → NaN).
  - **Makefile:** nuevos targets `ingest` (en orden: ecb antes que bundesbank), `audit` y `data`.
  - **`DATA_CONTRACT.md`** documenta `pit_role` y `country_iso3`.
  - **Nuevo reporte** [[Reports/2026-10-12_semanal]].
  - **Reauditoría:** 0 críticas y 28 altas (todas explicadas: precios oficiales históricos, look-ahead ya marcado y un falso positivo). Ninguna fuente en rojo.
- **Commit `d1acc7e` en la rama `fase-datos`** (no fusionada aún en `main`).
- **El usuario aprueba seguir** con los pendientes MEDIA y los huecos accesibles (rama `fase-datos`).
  - **Agente "Huecos EE. UU.":** FRED release 388 (1914-41), Z.1 completo, repo BGCR/TGCR/SOFR y MTS anterior a 1980.
  - **Agente "Huecos Europa/FMI":** EPA 1976-2001 (PC-Axis del INE), IPC del INE anterior a 2002 e IFS del FMI.
  - **El coordinador corrige los pendientes MEDIA:** BOGZ1FL073164003Q, nber_m12014, shiller_gs10, el arroz de 2008, M1SL, los eventos y el catálogo de maddison.

## 2026-10-13
- **Retomado.** La sesión del 12-oct se cortó: de los pendientes MEDIA solo había 2 arreglos sin commit (`nber_m12014` ×10 en 1915 y ceros del arroz en `wb_pinksheet`); los agentes "Huecos EE. UU." y "Huecos Europa/FMI" no dejaron nada.
- **Liquidez (petición del usuario):** ya estaban WALCL, WRESBAL, TGA (WTREGEN/WDTGAL), RRP, SRF (RPONTSYD), swaps, M2 mensual/semanal, MSPD por tipo y balance del Eurosistema; el clasificador ya usa liquidez neta = WALCL − TGA − RRP. Se añade un agente **"Liquidez EE. UU. y global"** para lo que falta (TGA diaria DTS, emisión neta letras/cupones, recompras, balance Fed antes de 2002, BoJ/BoE/PBoC/SNB y M2 de grandes economías).
- Lanzados en paralelo: Huecos EE. UU., Huecos Europa/FMI y Liquidez. El coordinador corrige los MEDIA.
- **Arreglos MEDIA hechos por el coordinador (13-oct, sin commit aún)**, todos en los scripts de ingesta y reejecutados:
  - `BOGZ1FL073164003Q` (`fred_extended.py`, nuevos `KNOWN_FIXES`/`CATALOG_OVERRIDES`): 1945-1951 ×10 (1.277 → 12.770 frente a 12.910 en 1952-Q1) y unidades "Index" (FRED decía "Percent").
  - `M1SL`: nota de ruptura de definición en 2020-05 (depósitos de ahorro pasan a M1; no usar a/a entre 2020-05 y 2021-04).
  - `shiller_gs10` 2019-07: 1,63 → 2,06 (Shiller repetía agosto; FRED GS10), solo mientras el fichero traiga el valor malo.
  - `nber_m12014` 1915 ×10 y arroz de 2008 a NaN (`wb_pinksheet`): comprobados.
  - Eventos: `inflation_crisis` añadido al enum de `DATA_CONTRACT.md`; COW con día/mes de fin desconocido → último día del periodo (`cow_extra_321`: fin 1838-04-30). 0 eventos con fin < inicio.
  - **Maddison (era un fallo real, no solo duplicados):** la hoja regional tiene dos bloques (PIB pc y población) y el segundo sobrescribía al primero: 7 series `maddison_region_*_gdppc` contenían población. Ahora 9 `_gdppc` + 9 `_pop` (Europa occidental 2000: 32.593 $ y 390 M hab.). `CatalogWriter.close()` falla si hay `series_id` repetidos.
  - Pendiente: rtdsm sin conectar al clasificador (es del modelo, para después de la fase de datos).
- **Agente "Huecos Europa/FMI" terminado** (doc: `docs/data/europe_gaps_2026-10-13.md`).
  - `ine`: 13 → 60 series. EPA 1976T3-2001T4 (Excel oficial `series76_01.xls`, definición antigua) + EPA Tempus desde 2002 + empalmadas `*_linked_q` (ruptura 2002 anotada: 12,75 % → 11,55 %). Paro 1994 ≈ 24 %.
  - IPC desde 1961: `ine_ipc_mom_m` e `ine_ipc_index_linked_m`; `bde_es_cpi_m` es el mismo índice con otra base (cociente 0,7888). Dic-1977 26,4 %. Ene-sep 2002: usar `ine_ipc_yoy_m`.
  - `imf_ifs` (nueva, api.imf.org SDMX 3.0): 305 series, 22 países (G20 + ESP, CHE, NLD): IPC, tipos de cambio, tipos de interés, dinero, reservas y oro. Huecos: dinero estandarizado solo desde 2000-12; tipo oficial en 13 de 22 países; sin subyacente.
- **Agente "Liquidez EE. UU. y global" terminado** (doc: `docs/data/liquidity_2026-10-13.md`, con la sección "Cómo medir la liquidez").
  - `us_liquidity` (55 series): TGA **diaria** desde 2005-10 (cuadra exacta con WDTGAL en 1.084 miércoles), depósitos/retiros diarios, emisión DTS bruta/neta de letras, notas y bonos, subastas desde 1979 (cuota de letras), recompras del Tesoro, detalle H.4.1 (ventana de descuento, FIMA) y proxies de la Fed antes de 2002 (AMBSL desde 1918, NBER 1914-69).
  - `cb_balance_sheets` (38 series): BoJ (API oficial: balance, base, M1-M3), SNB, BoE (M4 desde 1982; balance solo 2006-2014), PBoC (vía FMI/DBnomics, hasta 2025-06), M2 de China (Eastmoney, agregador).
  - Fórmulas propuestas: liquidez neta diaria = WALCL − TGA diaria − 1000 × RRP (5,86 billones $ el 2026-10-08); liquidez global USD = Fed + BCE + BoJ + SNB [+ PBoC] (15,5 → 25,9 → 19,9 billones en dic-19 / mar-22 / jun-25); impulso a 13 y 26 semanas.
  - Huecos: BoE tras 2014, PBoC tras 2025-06, total de activos de la Fed 1969-2002, DTS antes de 2005-10. Pendiente de la checklist del auditor.
  - **Para el modelo (cuando se cierre la fase de datos):** `net_liquidity` diaria desde 2005 con retardo de publicación (DTS T+1, WALCL los jueves) y el agregado global.
- **Agente "Huecos EE. UU." terminado** (doc: `docs/data/us_gaps_2026-10-13.md`).
  - `fred_banking_1914` (release 388 completa): 1.993 series 1914-1941 (balance de *member banks*, nº de bancos: 26.150 en 1914 → 14.523 en 1933).
  - `fed_z1`: 1.935 series trimestrales 1945-2026 (niveles de todos los sectores y deuda por sector; 20 duplicadas con `fred_us` omitidas; deuda no financiera 84,09 billones $ en 2026-Q2 = TODNS).
  - `nyfed_repo`: SOFR, BGCR, TGCR con percentiles y volumen desde 2018-04 (+ medias e índice SOFR desde 2020).
  - Hueco: MTS anterior a 1980 (solo PDF escaneado); se cubre con anuales desde 1901. Z.1 y SOFR se revisan: no son point-in-time.
- **Reconstrucción (13-oct):** 5 fuentes nuevas añadidas al `Makefile` (`INGEST`). `make warehouse regime audit weekly`: 14.026 series, 6,46 M filas; régimen hoy Deflación/recesión, crédito verde, **liquidez neutral** (−0,47; ayer escasa −0,51, por datos semanales más frescos). Auditoría: 0 críticas, 32 altas explicadas (precios oficiales fijos, look-ahead marcado y 5 falsos 9999/−99 que son valores reales). Resumen en `docs/data/audit_2026-10-13.md`. Reporte `Reports/2026-10-13_semanal`.
- **Auditoría de cobertura frente a la lista del usuario** (`docs/data/audit_cobertura_2026-10-13.md`): macro EE. UU./euro/global, tipos, TIPS, VIX, CISS y €STR **cubiertos**. **Faltan:** PMI/ISM (de pago; sustitutos: sentimiento CE, confianza OCDE, Fed regionales), factores French internacionales y diarios, AQR, JKP, índices MSCI/Euro Stoxx/DAX/Nikkei con historia, DXY (hay índice amplio de la Fed). **Parcial:** ICE BofA HY/IG solo 3 años (licencia FRED), S&P diario solo 10 años, bonos euro y Euribor solo mensuales. Frescura: diarias de FRED ~7 días atrás; IPC OCDE de España/euro parado en 2025-12.
  - Huecos priorizados: (alta) factores internacionales + AQR + JKP · CFTC COT · bonos euro diarios (BCE) · excess bond premium (Fed) · VIX3M/VVIX/SKEW; (media) Fed regionales/ifo/ZEW, vivienda España (INE IPV, compraventas, hipotecas, afiliación), flujos de fondos (ICI, Inverco), empleo euro.
- **El usuario aprueba (13-oct):** tanda de huecos de prioridad alta + automatización de la actualización en el Mac. (Fusionar `fase-datos` en `main`: aún sin aprobar.)
  - Agentes lanzados: **"Factores globales"** (French internacional y diario, AQR, JKP), **"Mercado, crédito y sentimiento"** (CFTC COT, CBOE VIX3M/VVIX/SKEW, excess bond premium, Brent diario, dólar AFE/EME, encuestas regionales de la Fed, flujos ICI) y **"Europa y España diario"** (bonos euro diarios BCE, Euribor/OIS, empleo euro, vivienda España, afiliación, ifo/ZEW, Inverco, IPC OCDE parado).
  - El coordinador monta la automatización (launchd) y revisa el retraso de las series diarias de FRED.
- **Series diarias de FRED congeladas: arreglado.** 59 series "heredadas" (DGS10, VIXCLS, SP500, T10Y2Y, high yield…) se cargaban de CSV antiguos y nunca se pedían a la API. Ahora `fred_extended` las renueva siempre (el CSV queda solo de respaldo): DGS10 al 8-oct, VIX al 9-oct, S&P al 12-oct.
- **Automatización preparada:** `scripts/actualizar.sh diario|semanal`, objetivos `make daily` / `make semanal`, plists en `scripts/launchd/` y `docs/automatizacion.md`. Diario lun-sáb 7:30 (fuentes diarias + warehouse + régimen); semanal domingo 7:00 (todo + auditoría + reporte). Resultado en `Proyecto/Actualizaciones.md` y notificación si algo falla.
  - Prueba de launchd: macOS **bloquea** a Python leer el proyecto en el Escritorio (se queda esperando permiso). **Decisión del usuario: mover el proyecto a `~/Proyectos/financial_kb`** cuando terminen los agentes en curso.
- **Agente "Mercado, crédito y sentimiento" terminado** (doc `docs/data/market_sentiment_2026-10-13.md`), 237 series:
  - `cftc_cot` (163, semanal): 21 contratos (S&P, Nasdaq, Treasuries 2-30 y ultra, SOFR/eurodólar, EUR, JPY, GBP, CHF, dólar, oro, plata, cobre, WTI, gas, VIX); Legacy desde 1986, TFF/Disaggregated desde 2006. Fecha = martes; se publica el viernes (retardo 3 días).
  - `cboe` (20, diario): VIX3M/6M/9D/1D, VVIX, SKEW, VXN, OVX, GVZ, correlación implícita COR1M/3M y ratios put/call (desde 2019-10 vía JSON diario; posible ruptura en SPX). Uso personal.
  - `fed_ebp` (3, mensual 1973-2026): excess bond premium (3,41 en 2008-10) y GZ spread.
  - `fred_us` +51 (modo `--only-ext`): Brent diario, dólar AFE/EME, volatilidades, incertidumbre de política, encuestas Empire/Philadelphia/Dallas, fondos monetarios semanales.
  - Huecos: ICI (bloquea descargas automáticas), Richmond/KC, MOVE y sorpresas (de pago), curva de futuros del VIX.
  - Para el warehouse: `PIT_RULES` con retardo para `^cftc_`; `fed_ebp_recession_prob` como lookahead si se usa de predictor.
- **Agente "Factores globales" terminado** (doc `docs/data/factors_2026-10-13.md`), 939 series en % por periodo:
  - `ken_french_intl` (124): EE. UU. diario desde 1926 y Developed, ex US, Europe, Japan, Asia Pac ex Japan, North America (mensual y diario desde 1990) y Emerging (mensual desde 1989). 5 factores + momentum. Mkt-RF EE. UU. oct-2008 −17,2 %; Europa −22,0 %.
  - `aqr` (479): QMJ por país (**incluida España**), BAB, HML Devil, VME, TSMOM y Century of Factor Premia (desde 1926). **Licencia: uso personal, sin redistribuir.**
  - `jkp` (336): 13 temas + mercado, vw_cap, para EE. UU., mundo, desarrollados, emergentes y ESP, DEU, FRA, GBR, ITA, NLD, CHE. Hasta 2025-12. **CC BY-NC 4.0.**
  - AQR y JKP reescriben la historia en cada versión: no son point-in-time.
- **12:40:** el agente "Europa y España diario" se cortó por el límite de uso de la sesión (había tocado ecb, eurostat, ine, bundesbank y oecd). Reanudado con su contexto tras el reinicio del límite.
- Coordinador: añadidos a `AGGREGATES` de `build.py` los códigos de región de los factores (WLDXUS, DEV, DEVXUS, EUR, NAMER, APXJ, PAC).
- Pendiente al terminar: mover el proyecto a `~/Proyectos/financial_kb`, instalar las tareas launchd, añadir las fuentes nuevas al Makefile, reconstruir, auditar y commit.
- **Agente "Europa y España diario" terminado** (doc `docs/data/europe_daily_spain_2026-10-13.md`):
  - `ecb` +18 (forwards diarios de las curvas AAA y de todos los bonos, €STR compuesto, diferencial todos−AAA a 10 años diario: proxy del estrés soberano, 194 pb el 24-jul-2012), `bundesbank` +6 (Bund cupón cero diario 1-30 años desde 1972).
  - `eurostat`: empleo trimestral (zona euro y 10 países), vacantes, confianza industrial y de servicios. `ine` +21: IPV (base 2025, corregida), compraventas, hipotecas, producción industrial. Afiliación ya estaba (`bde_es_ss_affiliates_m`: 22,36 M en 2026-09).
  - Nuevas `ifo` (32, clima empresarial alemán) y `zew` (2, sentimiento de Alemania).
  - **IPC de la OCDE arreglado:** la OCDE pasó la zona euro a un dataflow nuevo (ECOICOP-2); empalmado. España y resto llegan a 2026-08/09; usar `oecd_cpi_ea_*` (`ea20` congelada; el clasificador no la usa).
  - Huecos: bonos soberanos **diarios** por país (solo Alemania; no hay fuente gratuita estable), Euribor diario (EMMI, de pago), OIS, ZEW de la zona euro, ifo 1960-90, Inverco (solo PDF).
- **12:45:** proyecto movido a `~/Proyectos/financial_kb` (rutas del `.venv` ajustadas; sin rutas fijas en el código). Fuentes nuevas en el `Makefile` (`INGEST` e `INGEST_DAILY`: + bundesbank, cboe). `make warehouse regime`: **15.397 series, 12,2 M filas**; régimen sin cambios (Deflación/recesión, crédito verde, liquidez neutral).
- **12:46:** tareas launchd instaladas (`com.financialkb.diario` y `.semanal`) y prueba real de la diaria lanzada: ya lee el proyecto sin el bloqueo del Escritorio.
- Memoria de Claude actualizada con la ruta nueva y la automatización.
- **12:50: el usuario hace /clear.** Estado y próximos pasos en la sección "▶ Retomar aquí" de [[Proyecto/Estado del proyecto]].

## 2026-10-14
- **Tarea launchd de arranque** (`com.financialkb.arranque`, modo `scripts/actualizar.sh pendiente`): launchd no recupera las citas perdidas con el Mac apagado; al encender, lanza la semanal si tiene más de 7 días o la diaria si falta la de hoy (marcas `~/financial_archive/logs/.hecho_*`). Instalada; **sin commitear** (plist nuevo + `actualizar.sh` + `docs/automatizacion.md`).
- **17:38:** primera diaria recuperada al encender: ✅ ok, 15 min. Régimen sin cambios (Deflación/recesión, crédito verde, liquidez neutral).
- Pendiente del 13-oct sin hacer: `make audit` completo con las fuentes nuevas, resumen `docs/data/audit_2026-10-13_b.md` y `make weekly`.
- **El usuario pide cerrar el punto 1 (auditoría pendiente).** Lanzado el agente **Auditor de datos**: `make audit` → `docs/data/audit_2026-10-14.md`, foco en las fuentes nuevas del 13-oct, falsos positivos explicados y veredicto sobre cerrar la fase de datos. Al terminar: `make weekly` y commit en `fase-datos`.
- **Auditor terminado** (`docs/data/audit_2026-10-14.md`): 0 críticas, 33 altas (32 ya explicadas el 13-oct + `cftc_ust5y_nc_net` = −999, que es real). Valores conocidos correctos; contrato, catálogo y licencias bien en las 14 fuentes nuevas. Arregló `EVENT_TYPES` en `src/audit/other_checks.py` (`inflation_crisis`). Veredicto: **se puede cerrar la fase de datos** tras el arreglo del INE.
- **Arreglos aplicados por el coordinador** (verificados en el warehouse):
  - `ine.py`: desfases de columna de la EPA 1976-2001 por sexo (8/14 → 6/12); 20 series leían la «Diferencia». Hombres activos 1976-T3 = 9.556.
  - `cftc_cot.py`: descartadas las filas del ECU de 1986 mezcladas en el euro (código 099741).
  - `PIT_RULES`: `GDPPOT`/`NGDPPOT` como `forecast` y `fed_ebp_recession_prob` como `lookahead`.
  - Reingesta `ine` + `cftc_cot`, `make warehouse regime weekly`: 15.397 series, 12,25 M filas; régimen sin cambios. Reporte [[Reports/2026-10-14_semanal]].
- Pendientes menores: confirmar si DG ECFIN dejó de publicar `eurostat_rci_es`/`sci_es` (acaban en 2024-09); etiqueta `restated` para AQR/JKP/Z.1/SOFR; `make audit` no genera el `.md` (el auditor lo escribió a mano); no usar VVIX antes de 2007.
- **Arquitectura propuesta por el usuario para la Fase 3** (modelo GBM de régimen en dos etapas → reglas de oro validadas → Claude redacta → informes). Revisión: buena base; cambios propuestos: baselines sencillos + persistencia (GBM como aspirante), etiqueta de régimen ex post con variables point-in-time, métricas de probabilidad (log-loss/Brier, calibración), periodo final bloqueado y Deflated Sharpe, capa de cartera/riesgo validada después de costes (EUR, fiscalidad), monitorización y registro de modelos; informe de empresas después; ojo CNMV si llega a terceros. Pendiente de que el usuario lo apruebe para escribirlo en `docs/PLAN.md`.
- **El usuario aprueba (14-oct):** fusionar `fase-datos` en `main` (hecho, merge `a460f63`) y **cerrar la fase de datos**. Arquitectura de la Fase 3 escrita en `docs/PLAN.md` (sección "Fase 3 — arquitectura de modelos") con las correcciones de la revisión. Primer entregable: especificación de la etiqueta + matriz point-in-time + test de fugas.
- **Decisiones del usuario para la etiqueta (14-oct):** nowcast primero (forecast a 6 m después, con métricas propias); 4 cuadrantes (Expansión, Late cycle/sobrecalentamiento, Estanflación, Desaceleración/recesión); crecimiento = **ritmo frente a tendencia**; inflación = **subyacente frente a umbral fijo**; fronteras con **etiquetas probabilísticas**; **EE. UU. primero**, zona euro después. Recesión y liquidez/crédito como capas, no como regímenes.
- **Borrador de la ficha** `docs/models/label_spec.md` (v0.1, sin congelar): G = conjunto coincidente del NBER (INDPRO, PAYEMS, W875RX1, CMRMTSPL) frente a una tendencia centrada de 10 años; I = PCE subyacente a 6 m frente a κ = 2,5 %; P = Φ(distancia/s); comprobaciones de sentido; últimos 24 meses provisionales. Pendiente: el usuario confirma los parámetros de la §11 → v1.0 + tag `label-v1.0`. Después: `docs/models/pit_calendar.md` (retardos medidos con ALFRED) y la base point-in-time.
- **El usuario confirma los parámetros propuestos de la etiqueta**, con las escalas de incertidumbre estimadas con ALFRED. Pide además: (1) sacar relaciones adelantadas e indicadores/reglas para sistemas al estilo Dalio; (2) nivel muy profesional; (3) añadir precios de futuros y derivados.
  - Agentes lanzados: **"Constructor de la etiqueta"** (`src/labels/`, etiqueta v0.1, comprobaciones de la §8, tests) y **"Recopilador de futuros y derivados"** (estructura del VIX, curvas de WTI/gas de la EIA, trayectoria de tipos implícita, inflación esperada de mercado, futuros continuos; huecos de pago con coste).
  - Coordinador: programa de investigación `docs/models/research_program.md` (mecanismo antes que dato, preregistro, universalidad con JST, alerta temprana, contenido incremental fuera de muestra, Benjamini-Hochberg, ciclo de vida de las reglas, sistema de reglas frente al GBM) y enlace en `docs/PLAN.md`.
- **Etiqueta v0.1 construida** (`src/labels/`, `docs/models/label_v0.1_checks.md`, gráfico `label_v0.1.png`; parquet en `~/financial_archive/labels/`). 920 meses (1950-01 → 2026-08). Escalas ALFRED: s_G = 0,40 z, s_I = 0,30 pp. 11/12 comprobaciones ✅ (recesiones NBER 97 %, brecha de producción 0,87, los 6 episodios, duración media 9,1 m); ❌ CFNAI-MA3 0,62, porque G mide el ritmo de t−7 a t (con CFNAI retardado 0,81). Reparto: expansión 29 %, late cycle 24 %, estanflación 22 %, desaceleración 25 %. Últimos meses: estanflación en zona frontera (I > 2,5 %, G ≈ 0). 9 tests ✅ (pytest añadido a requirements).
  - Revisión del coordinador: (1) **fallo de diseño de la ficha**, no de código: la etiqueta del mes t describe el crecimiento de hace ~4 meses; la etiqueta puede usar datos futuros, así que procede **centrar las ventanas** (G e I) en t; (2) los años 2010 salen a menudo como "desaceleración/recesión" con G ≈ tendencia e inflación baja: es un problema de nombre (crecimiento en tendencia ≠ desaceleración), a resolver con la capa de recesión o renombrando; (3) diverge del clasificador de reglas (que dice Deflación/recesión por la *dirección* de la inflación). Pendiente de que el usuario decida la v0.2.
- **El usuario aprueba la v0.2 de la etiqueta** ("cuando esté, guárdalo en Obsidian"). El Constructor de la etiqueta la prepara: ventanas centradas en t (G e I), cuadrante G↓I↓ renombrado a "Crecimiento bajo / desinflación" (la recesión la da `usrec`), peso 0 para 1950-54, comprobaciones de CFNAI en la misma ventana y acierto sin meses frontera, comparación v0.1 frente a v0.2, vintages de W875RX1/CMRMTSPL si ALFRED las tiene. Al terminar: resultados aquí y en el Estado.
- **Agente "Futuros y derivados" terminado** (doc `docs/data/futures_derivatives_2026-10-14.md`), 5 fuentes y 213 series:
  - `cboe_vx` (D, 2004→): curva de futuros del VIX F1-F4, vencimientos constantes 30/60/90 d y pendientes (2020-03-16: F1 72,6 / F2 59,2). Licencia Cboe, uso personal.
  - `eia_futures` (D, 1983→**2024-04**, la EIA dejó de publicarlos): WTI y gas contratos 1-4, diferencial y pendiente (WTI −37,63 el 2020-04-20).
  - `atl_mpt` (D, 2023-03→): trayectoria esperada de tipos de la Fed de Atlanta (SOFR esperado a 3-24 m, probabilidades de recorte/subida). Uso personal/educativo.
  - `clev_inflexp` (M, 1982→): inflación esperada de la Fed de Cleveland a 2-30 años, 5y5y, primas de riesgo.
  - `mpls_mpd` (W, 2006→): distribuciones implícitas en opciones de la Fed de Minneapolis, 21 mercados; volatilidad implícita de Treasuries a 5/10 años (sustituto parcial del MOVE) y de divisas.
  - Retardos para el calendario point-in-time: `clev_inflexp` +15 d, `mpls_mpd` +14 d, el resto +1 día hábil.
  - Huecos gratuitos: curvas de WTI/gas después de 2024-04, cobre/oro/cereales por vencimiento, OIS y futuros de fondos federales antes de 2023, futuros continuos (Stooq, Yahoo e Investing bloquean). **De pago:** Databento (curvas CME, decenas-cientos de USD, la mejor relación coste/valor), Norgate (~300-600 USD/año), CME DataMine, MOVE (miles), Bloomberg/LSEG (15-30 k USD/año). **Decisión pendiente del usuario.**
- Coordinador: fuentes añadidas al `Makefile` (`INGEST`; `cboe_vx` y `atl_mpt` también en `INGEST_DAILY`). Auditoría de las fuentes nuevas: 0 críticas, 0 altas; medias esperables (EIA descontinuada, huecos de Minneapolis). Reconstrucción del warehouse cuando termine la etiqueta v0.2.
- **Etiqueta v0.2 terminada** y guardada en [[Proyecto/Etiqueta de régimen]] (con gráfico): 13/13 comprobaciones sin tocar umbrales; s_G = 0,33, s_I = 0,31; acierto esperado 84 % (87 % sin frontera); cambian 244 meses frente a la v0.1 (desfase confirmado: G v0.2(t) = G v0.1(t+4)). Últimos meses: estanflación. Pendiente: el usuario decide las 4 propuestas y congelar como v1.0.
- Warehouse reconstruido con los derivados: **15.610 series, 12,53 M filas**. Régimen del clasificador de reglas sin cambios.
- **Decisión del usuario (14-oct): no pagar por datos.** Opción sin coste a estudiar más adelante: los créditos gratuitos de bienvenida de Databento (verificar condiciones y licencia) para cubrir las curvas de futuros de 2024-2026.
- Revisión de una opinión externa sobre la v0.2: (A) **borde derecho, acierta en parte**: la ventana de ritmo no se trunca (la etiqueta acaba en 2026-04), pero la tendencia de 10 años sí se trunca en los últimos 60 meses y solo 24 son provisionales → medir empíricamente cuánto se revisa la etiqueta y fijar los meses provisionales con eso (probable causa del CFNAI negativo de 2022-24). (B) EIA cortada en 2024 y (C) historia corta de `atl_mpt`: aciertan → regla de admisión de variables al modelo. (C) Fecha de Cleveland: no aplica (fecha = día 1 del mes + 15 d = mediados del mismo mes, correcto). (D) Umbrales sin tocar (κ = 2,5; frontera 0,55), verificado.
- **El usuario aprueba congelar la v1.0:** embargo de 6 meses, s_G = 0,40, meses provisionales fijados con un estudio de revisión de la etiqueta (regla declarada de antemano: concordancia ≥ 95 % y |Δp| ≤ 0,05) y regla de admisión de variables. El Constructor de la etiqueta hace el estudio y la v1.0; el coordinador escribe la regla de admisión en `docs/PLAN.md` (fuente viva, historia mínima de 3 recesiones o 6 cambios de régimen, point-in-time, sin que la disponibilidad delate la época).
- **Objetivo y criterios de cierre de la Fase 3** escritos en el Estado (a petición del usuario): nowcast del régimen de EE. UU. validado frente a alternativas sencillas.
- **El usuario pide dos agentes nuevos:** un **Reportero** (informe bonito, con gráficos y muy explicativo) y garantías de que todo está bien testeado y de que las relaciones son reales y funcionan → **Validador independiente** (reproducibilidad, fugas, placebo, señal plantada, estabilidad, comparaciones múltiples, contenido incremental, sensibilidad; su ✅ es necesario para cerrar cada hito). Roles en [[Proyecto/Agentes]] §5-6. Se lanzan cuando esté la etiqueta v1.0, que es su primer hito.
- **Etiqueta v1.0 CONGELADA** (tag `label-v1.0`, commit limpio, hash `38250f0a…`): estudio de revisión → **54 meses provisionales** (regla declarada antes de ejecutar); s_G = 0,40; embargo 6 m; 13/13 comprobaciones; último mes maduro 2021-10. Ver [[Proyecto/Etiqueta de régimen]].
  - Consecuencia: el periodo bloqueado 2016-2026 tendría solo ~70 meses puntuables → decisión pendiente del usuario.
  - Lanzados el **Validador independiente** (primer hito: etiqueta v1.0 + estudio de revisión) y el **Reportero** (primera versión del informe: fase de datos + etiqueta).
- **Reportero: primera versión del informe** en [[Reports/Fase 3/Informe de resultados]] (resumen, datos, etiqueta v1.0, siguientes pasos, limitaciones, glosario; 7 gráficos reproducibles con `src/report/fase3/make_figures.py`). Dato nuevo: el clasificador de reglas coincide con la etiqueta solo en el 51 % de los meses (orientativo, no es un backtest point-in-time). Veredicto del validador: pendiente.
- **Validador: etiqueta v1.0 ⚠️ aprobada con condiciones** (`docs/validation/2026-10-14_label_v1.0.md`). Reproducible (mismo hash desde el tag) y sin ajustes ad hoc. Hallazgos ALTA: (A1) entradas sin congelar: el warehouse cambia cada día y las revisiones reescriben meses maduros; (A2) un embargo de 6 m no cubre la tendencia de ±60 m → recalcular las etiquetas de entrenamiento con datos ≤ corte en cada pliegue; (A3) fugas de uso: la persistencia "mes anterior" no es point-in-time (89 % frente a 68 % real con t−5), `usrec` es ex post, faltan columnas prohibidas. MEDIA: ruido de la inflación en ALFRED (~94 % de techo), k* frágil en bootstrap, 50 % del peso en el futuro (ene-feb 2020), la §8 no comprueba el eje I (contrastes hechos: OK), empalme 1957-59 mal calibrado (−0,4 frente a −0,06 pp, 6 meses). Sensibilidad: 0-12 % de meses cambian, ningún episodio se da la vuelta.
  - **Periodo bloqueado recomendado: 2005-01 → abierto** (202 meses puntuables, 2 recesiones, 21 cambios); la investigación de relaciones solo con datos ≤ 2004. Pendiente de que decida el usuario.
- **Decisiones del usuario (14-oct):** (1) **periodo bloqueado 2005-01 → abierto**; investigación y diseño del modelo base solo con datos ≤ 2004; (2) **v1.1 de la etiqueta ya**: empalme 1957-59 (−0,06 pp), entradas congeladas con SHA-256, lista negra de columnas en código y ficha; (3) **arnés**: etiqueta de entrenamiento recalculada con datos ≤ T en cada corte (obligatorio) y baseline honesto = persistencia point-in-time (~68 %); (4) `cboe_vx` y `mpls_mpd` se definen a priori por teoría y se preregistran como módulo adicional.
  - Coordinador: reglas escritas en `docs/PLAN.md` y `research_program.md`; **preregistro** en `research/hypotheses.yaml`: H-DER-001 (pendiente de la curva del VIX 60d−30d) y H-DER-002 (volatilidad implícita del Treasury a 10 años), con mecanismo, definición, signo, horizonte y criterio de éxito, sin mirar datos posteriores a 2004.
  - El Constructor de la etiqueta prepara la v1.1.

## 2026-10-15
- **Etiqueta v1.1 candidata commiteada** (`a806561`, sin tag todavía): empalme IPC→PCE subyacente medido (+0,20 pp, 1959-04→1961-03; la v1.0 usaba −0,4 pp fijo), instantánea de entradas con SHA-256 (`regime_us_v1.1_inputs.parquet`), lista negra de columnas en el código y el `meta.json`. 13/13 comprobaciones, 14/14 tests. Hash `8425b403…`.
  - Ojo: el validador había medido −0,06 pp para el empalme; la v1.1 da +0,20 pp → se le pide que explique la discrepancia.
- Lanzado el **Validador independiente** sobre la v1.1 → `docs/validation/2026-10-15_label_v1.1.md`. El tag `label-v1.1` se pone cuando apruebe.
- La actualización diaria de hoy no se había ejecutado a la hora de retomar (Mac apagado a las 7:30).
- **Validador: etiqueta v1.1 ⚠️ aprobada con condiciones** (`docs/validation/2026-10-15_label_v1.1.md`). Serie correcta y reproducible bit a bit desde `a806561` + instantánea (hash `8425b403…`); solo cambian I en 1957-04→1959-03 y 6 etiquetas duras de 1957; ningún cambio no declarado.
  - Empalme: −0,06 (validador, convención IPC−PCE, ventana 69 m) y +0,20 (v1.1, ventana 24 m) son el mismo signo; ambos defendibles; la etiqueta dura no cambia entre 0 y +0,30. **Decisión pendiente del usuario** (recomendado 24 m / +0,20).
  - ALTA: ficha `label_spec.md` sin actualizar a v1.1; sin tests que fijen el hash, el SHA de la instantánea y las filas maduras.
  - MEDIA: lista negra solo declarada (deja pasar `usrec_lag1`, `G_lag5`…); PLAN con persistencia ≈68 % (real 63,6 %, retardo 5 m) y definición "mes anterior" en l. 112; la persistencia PIT usa la última vintage (declararlo).
- **Decisión del usuario (15-oct):** empalme de 24 meses / **+0,20 pp**. Pide además que el **experto en finanzas** (Estratega macro) revise los resultados y que **otro agente audite** después de corregir.
  - Lanzado el **Estratega macro** sobre la etiqueta (sentido económico, episodios, rendimientos de activos por cuadrante solo 1955-2004, lectura actual) → `docs/reviews/2026-10-15_estratega_macro_etiqueta.md`.
  - **Correcciones del coordinador** (commit `ebccae1`): hashes de la instantánea y de la etiqueta en git (`FROZEN`); `read_snapshot` rechaza instantáneas distintas; tests de hash, de instantánea alterada, de filas maduras frente a la v1.0 y de la lista negra (35/35); `assert_no_forbidden` por raíz del nombre (derivadas `usrec_lag1`, `G_lag5`…; 0 falsos positivos en las 15.610 series) y por defecto con la lista del meta; ficha `label_spec.md` v1.1 (§4 empalme, §7 ruido de inflación, §10 congelación corregida, §11, §12 uso en modelos nuevo, §13 registro de cambios); PLAN con persistencia PIT 63,6 %. Meta regenerado desde árbol limpio: hash `8425b403…` sin cambios.
  - Lanzada la **re-auditoría de cierre** del Validador; el tag `label-v1.1` se pone si da ✅.
- **Estratega macro: etiqueta v1.1 ⚠️ "sirve con cambios"** (`docs/reviews/2026-10-15_estratega_macro_etiqueta.md`). Vale como objetivo del nowcast y **no se toca** (cambiarla tras mirar rendimientos sería minería); no vale sola como "régimen de inversión".
  - A1: el eje de inflación (nivel frente a 2,5 %) marca épocas: solo 27 cruces en 802 meses (G: 58). Estanflación y Crec. bajo cambian de signo para la bolsa entre 1955-79 y 1980-2004; estable solo Expansión → bolsa y Crec. bajo → bonos.
  - A2: "Late cycle" mal nombrado: recoge recuperaciones tempranas con inflación alta pero bajando (1975-07→76-05, 1983-01→85-01, p ≈ 0,9). Propuesta: "Crecimiento con inflación alta".
  - A3: la recesión explica tanto como el cuadrante (bolsa +1,2 % en recesión frente a +8,7 %; bonos +9,9 % frente a +1,5 %).
  - Tramos discutibles: salida de Volcker 1982-H2 y 1991-04→92-02 como estanflación; 2024-07→11 (frontera); 2001-12; 1971-72 (controles de precios). La subyacente cae al otro lado del umbral que la general en el 11 % de los meses (1986, 1999-2000, 2003-04) → falta capa de shock energético.
  - Rendimientos 1955-2004 (ex post): bolsa en Expansión +15,4 %, bonos en Crec. bajo +8,3 %, oro en Estanflación +7,0 %, materias primas en Late +10,4 %. Alternativa crecimiento × dirección de la inflación separa mejor (G↓ I acelerando: bolsa −1,5 %, oro +16,9 %).
  - Régimen actual: "estanflación suave, de oferta, en frontera" es sensata (PCE subyacente ~3 %, petróleo > 90 $ desde marzo de 2026; empleo frente a una tendencia inflada por la inmigración). En informes: "inflación persistente con crecimiento en torno a tendencia, sesgo estanflacionario".
  - Propuestas: capas ex post preregistradas (dirección de la inflación, shock energético, holgura paro − NAIRU); v2.0 con inflación frente a expectativas solo si la Etapa 2 lo justifica con datos ≤ 2004; Etapa 2 = cuadrante × recesión × dirección, mismo signo en ambas épocas; capa EUR (el dólar cayó en Crec. bajo 1973-2004: −3,4 %/año); fiscalidad: fondos traspasables, no ETF.
  - Creado `research/trial_log.md` (registro de pruebas) con esta revisión como primera entrada. **Decisiones pendientes del usuario.**
- **Decisiones del usuario sobre la revisión económica (15-oct):** (A) `late_cycle` se llama "Crecimiento con inflación alta" **solo en informes y gráficos** (cambiado en `src/report/fase3/make_figures.py`; `checks.py` tras la re-auditoría); (B) **capas ex post aparte**, preregistradas en `research/hypotheses.yaml`: L-CAP-001 dirección de la inflación (I_t − I_{t−6}, banda s_I·√2), L-CAP-002 shock energético (PCE general − subyacente > ±1 pp o crudo a/a > ±40 %; WPU0561 hasta 1985 y WTI después), L-CAP-003 holgura (paro − NAIRU de la CBO, ±0,5 pp); prohibidas como variables; (C) v2.0 (inflación frente a expectativas), capa EUR y fiscalidad, **pospuestas** a su fase. Anotado en `docs/PLAN.md`.
- **Re-auditoría de cierre del Validador: ✅ aprobada** (sección final de `docs/validation/2026-10-15_label_v1.1.md`; script `tests/validation/label_v1_1_closure.py`): reproducción bit a bit desde `ebccae1` sin warehouse; mutaciones detectadas por los tests; A-1, A-2, M-1, M-3 cerradas; M-4/M-5 declaradas.
- **Tag `label-v1.1` en `ebccae1`. Etiqueta v1.1 CONGELADA.** Instantánea sin permisos de escritura + copia en `~/financial_archive/labels/inputs/backup/` (SHA-256 `9cc855f8…`, ambas iguales); parquet oficial también de solo lectura.
- **Blindaje tras la re-auditoría** (commit `6aaf3f7`): P-1 `write_snapshot` se niega con versiones congeladas (incluso `--force`) y `write` no escribe una etiqueta oficial con hash distinto; P-2 tests sobre **todas** las versiones de `FROZEN` y `CANDIDATE_CHANGES` obligatorio para candidatas; P-3 `rtol=0`; P-4 lista negra con prefijos, infijos y tuplas MultiIndex (0 falsos positivos en 15.610 series). Ficha: 3 retoques de texto. `checks.py`: nombre visible "Crec. con infl. alta". 45/45 tests. Meta regenerado desde árbol limpio (hash `8425b403…`).
- Pendiente para el arnés: construir las variables desde **lista blanca**; añadir L-CAP-001/002/003 a la lista negra cuando existan.
- **El usuario aprueba seguir con el entregable (2).** Lanzados:
  - **Constructor (base point-in-time):** `docs/models/pit_calendar.md` (retardos medidos con ALFRED), **lista blanca** de variables con mecanismo y regla de admisión, constructor de la matriz PIT (`src/features/`, modos `vintage` y `latest_truncated`; salida en `~/financial_archive/features/`), tests de fugas (publicación > t, truncamiento, placebo, señal plantada, lista negra, forecast/lookahead), doc `docs/models/pit_base.md`. Exploración solo con datos ≤ 2004.
  - **Reportero:** informe de la Fase 3 al día (validación v1.0, v1.1 congelada, listón 63,6 %, revisión económica, capas preregistradas; "Crecimiento con inflación alta").
  - Circuito al terminar la base PIT: Validador → Estratega macro → correcciones → re-auditoría.
- **Reportero: informe de la Fase 3 v0.2** ([[Reports/Fase 3/Informe de resultados]]): recuadro "qué ha cambiado", semáforo de cierre, etiqueta v1.1 ("Crecimiento con inflación alta"), §4 validaciones, §5 listón 63,6 %, §6 revisión económica (rendimientos 1955-2004, NO operables), §7 decisiones del 15-oct; 10 gráficos reproducibles (nuevos: empalme, listón de persistencia, rendimientos por cuadrante). Excluye a propósito la persistencia del periodo bloqueado. No verificó por su cuenta los rendimientos del Estratega (script no versionado).
- **Constructor: base point-in-time v0.1 terminada** (candidata, commit `f4214fe`; doc `docs/models/pit_base.md`, calendario `docs/models/pit_calendar.md`):
  - Calendario de 56 series con retardos **medidos con ALFRED** por épocas (IPC: mediana 21 d antes de 1980 → 13 d desde 2013; INDPRO 18 → 15; PCE 30; empleo 5-7; PIB avance 29; CMRMTSPL ~60). Dos rarezas de ALFRED corregidas (comunicados fechados antes del fin del mes; historia añadida años después).
  - Lista blanca `research/pit_whitelist.yaml`: **46 variables** (25 principales, 12 por época, 4 condicionales: cfnai_ma3, core_pce_6m_ann, ebp, nfci; 4 de módulo adicional: liquidez neta y global, t5yie, dfii10) + 20 auxiliares; 16 rechazadas con motivo. Pendientes de la Fase 1 cubiertos (histéresis de G, inflación compuesta, bear/bull steepening, liquidez).
  - Matriz `src/features/pit.py` → `~/financial_archive/features/pit_us_v0.1_{vintage,latest_truncated}.parquet` (921 fechas × 46) con linaje por celda.
  - Tests de fugas (18 nuevos; 63/63): 0 celdas publicadas después de t; truncamiento idéntico en 5 cortes; placebo sin habilidad; señal plantada recuperada (+0,23 nats; umbral bajado de 0,3 a 0,10 **después** de ver el resultado → lo revisa el Validador).
  - Persistencia PIT ≤ 2004: latest_truncated 62,9 % (log-loss 1,228); **vintage 61,1 % (1,300)** → el arnés compara cada modelo con el baseline de su mismo modo.
  - Decisiones pendientes del usuario: (1) 4 condicionales fuera del modelo principal + vintages del NFCI; (2) modo principal `vintage`, `latest_truncated` como sensibilidad; (3) preregistrar las 4 del módulo adicional; (4) supuestos de calendario (Filadelfia 1968-90, SPF < 1990, Michigan 35 d, PERMIT, EBP/GZ, BIS, Pink Sheet); (5) referencia de persistencia en la ficha. Propuestas: `PUB_LAG` de `asof.py` desde el calendario (IPC 15 d no conservador); vintages W875RX1/CMRMTSPL/NFCI al warehouse.
- **Reportero: informe v0.2 commiteado** (`7033b9b`).
- Lanzados en paralelo el **Validador** (`docs/validation/2026-10-15_pit_base_v0.1.md`) y el **Estratega macro** (`docs/reviews/2026-10-15_estratega_macro_pit_base.md`) sobre la base PIT.
- (Los dos revisores se pararon por el límite de uso de la sesión; reanudados a las 12:23.)
- **Estratega macro: base PIT v0.1 ⚠️ "sirve con cambios"** (`docs/reviews/2026-10-15_estratega_macro_pit_base.md`). Arquitectura, tests y calendario sólidos; sin fugas en las principales; fallos de diseño económico. Solo miró descriptivos de las variables (≤ 2004), ninguna relación con la etiqueta.
  - `growth_rt` estandariza contra la media acumulada desde 1950 (no tendencia de 10 años como G) → "crecimiento bajo" crónico en 2000-04; histéresis ±0,15 inútil (cambia 1,06 veces/año) → banda ±0,5 y 2 meses.
  - Variables sin mecanismo antes de 1971-73 (`copper_gold_6m`, `usd_neer_yoy` → desde 1973); niveles con deriva que hacen de reloj de época (`tcu` → desviación frente a media de 10 años; `umcsent` desde 1978).
  - `infl_composite` nowcastea energía, no la subyacente → compuesto del núcleo en pp + compuesto de energía.
  - Faltan 9 (todas en el warehouse): servicios sin energía del IPC, salarios AHETPI, paro − mediana 10 años, SPF deflactor, índice Anxious del SPF, GS1 − DFF, precios pagados de Filadelfia, y análogos PIT de shock energético y dirección de la inflación.
  - Bear/bull steepening mal definido → 4 estados con umbral de 25 pb. Liquidez → mejor en la Etapa 2.
  - Calendario: Michigan 35 d (licencia FRED) → fuente directa y 20 d; SPF < 1990 → 90 d; Filadelfia 1968-90 → sensibilidad t−1 preregistrada; CMRMTSPL 90 d antes de 2000; BIS 20 d.
  - Propone lista blanca v0.2 fijada a priori antes de preregistrar el arnés.
- **Validador: base PIT v0.1 ⚠️ condicionada** (`docs/validation/2026-10-15_pit_base_v0.1.md`; scripts `tests/validation/pit_v0_1_{validation,power}.py`). 696 celdas recalculadas a mano con SQL: todas coinciden; ninguna con dato publicado después de t; reconstrucción idéntica con el mismo warehouse; persistencia coherente con la ficha.
  - ALTA: (1) depende del warehouse vivo, sin hash de entradas → instantánea congelada; (2) el placebo (c) no puede detectar fugas (pasa con una variable con fuga en 20/20 semillas).
  - MEDIA: señal plantada (d) con umbral post hoc y de un solo lado → intervalo [0,20; 0,40] + control de fuga > 0,42; **fuga pequeña confirmada en el BCE** (semana fechada en lunes, se publica el martes siguiente → 8 días); PERMIT/CMRMTSPL con retardo fijo fugan en los cierres del Gobierno de 2013/2025; Filadelfia 1968-90, SPF < 1990, Michigan 1953-77 pueden adelantar un mes; regla de admisión desigual: `gz_spread` (no existía antes de 2012), `m2_real_yoy` (M2 actual desde 1980) y `core_cpi_*`/`real_ff` antes de ~1978 deberían ser condicionales; el cambio revisado → primera publicación delata la época (puntuar en los dos modos).
  - BAJA: recuentos de la ficha (28/10 y 53 series, no 25/12 y 56), marcas `supuesto` erróneas, huecos de `umcsent` 1953-59, muestras distintas entre baselines, empalme de la TGA en 2005.
  - Cambio de umbral 0,3 → 0,10 anotado en `research/trial_log.md`.
- **Decisiones del usuario (15-oct) sobre la base PIT:** (A) aprueba el paquete completo de 12 correcciones → **lista blanca / base PIT v0.2**; (B) modo principal del arnés = **vintage (ALFRED)**, `latest_truncated` como sensibilidad, puntuando en los dos; (C) dudosas fuera del modelo principal ≤ 2004 y preregistrar las 4 del módulo adicional. Al terminar el Constructor, re-auditoría directa del Validador.
- **Constructor: base PIT v0.2 terminada** (candidata, commit `7aae6b0`; registro de cambios en `docs/models/pit_base.md`). 12 puntos + B + C hechos; hueco parcial: inicio del IPC subyacente del BLS sin fuente primaria (se mantiene 1978-01, supuesto prudente).
  - Instantánea congelada (61 series, 1,30 M filas + calendario + lista blanca), solo lectura, copia de respaldo, `FROZEN` en `src/features/pit.py` (metida antes del veredicto → lo revisa el Validador). Warehouse reconstruido una vez para incluir `umich`.
  - Lista blanca v0.2: 58 variables (36 principales, 13 por época, 5 condicionales, 4 módulo adicional) + 26 auxiliares; 21 rechazadas. Placebo (`src/features/placebo.py`) falla con fuga en 8/8; señal plantada 0,230 ∈ [0,20; 0,40], control con fuga 0,465. Histéresis de G: 0,44 cambios/año (v0.1: 1,06).
  - Michigan directo (`src/ingest/umich.py`, 20 d); vintages PERMIT/CMRMTSPL/NFCI y otras en `features/raw/alfred` (`src/features/alfred_raw.py`). Sensibilidades preregistradas S-PIT-001 (Filadelfia t−1) y S-PIT-002; módulo adicional H-MOD-001..004.
  - Baselines ≤ 2004 en los mismos 579 meses: vintage 61,1 % / 1,300; latest_truncated 63,0 % / 1,182. 86/86 tests.
  - Coordinador: `umich` añadido a `INGEST` e `INGEST_DAILY` del Makefile. Pendiente para la v0.3 (no aprobado): `permit_yoy` sobre media de 3 m y sorpresa de inflación.
  - Lanzada la **re-auditoría** del Validador → `docs/validation/2026-10-15_pit_base_v0.2.md`.
- **Re-auditoría base PIT v0.2: ⚠️ condicionada, muy cerca de ✅** (`docs/validation/2026-10-15_pit_base_v0.2.md`; scripts `tests/validation/pit_v0_2_{validation,power}.py`). Reproducción bit a bit sin warehouse; 768/768 celdas por SQL directo sobre la instantánea; 0 publicadas después de t; derivadas 921/921; cierres 2013/2025 cubiertos; `umich` correcto; reconstrucción del warehouse sin efectos no declarados. 86/86.
  - Falta: I-1 `infl_energy_pressure` usa IPC subyacente (condicional < 1978) → herencia automática del `principal_desde` de las entradas + test; I-2 `vix` condicional antes de 2003-09 (o empalme VXO); I-3 ajustes post hoc al trial log (**hecho por el coordinador**); I-4 la v0.2 entró en `FROZEN` antes del veredicto → corregir en una **v0.3** con la misma instantánea, a `FROZEN` solo tras el ✅. Menores: hash del meta de la etiqueta en los baselines y test de reproducción de baselines y variante Filadelfia; fechas de existencia (servicios sin energía, TCU); preregistros con más detalle. M-5 (`umich` fuera del diario) ya estaba resuelto en el Makefile (`INGEST_DAILY`).
- **Coordinador lanza la v0.3** de la base PIT (Constructor) con las correcciones de la re-auditoría (criterios ya aprobados: punto 3 y circuito corregir → re-auditar). El agente se paró por el límite de uso de la sesión; reanudado a las 17:20.
- **El usuario tiene poco tiempo:** pide seguir solo y dejar instrucciones. Instrucciones para retomar en [[Proyecto/Estado del proyecto]] → "Retomar aquí (15-oct, tarde)".
- **Constructor: base PIT v0.3 terminada** (candidata, commit `64186fe`, en `CANDIDATE`, no en `FROZEN`; misma instantánea de datos que la v0.2). 92/92 tests.
  - I-1 herencia automática de `principal_desde` (`effective_principal_desde`, test del grafo): solo arrastra `infl_energy_pressure` → 1978-01. I-2 `vix` condicional < 2003-09-22. Placebo con control "etiqueta t−4" (falla 8/8) y tabla de potencia honesta (`pit_base.md` §5). v0.2 marcada `SUPERSEDED`.
  - M-1 baselines con s_G/s_I de `R.PARAMS` y empalme desde la instantánea de la etiqueta (+0,2044), hash del meta fijado; reproducción de 3 matrices + 2 baselines. M-3 regla 3 = máximo → reserva del NFCI 7 → 12 d (336 celdas < 2011-05, ya condicional). M-4 saltos de composición reales en 1973-04 y 1981-05. M-6 adendas `P-EVAL-MOD` y `P-EVAL-S-PIT-002` (Holm sobre 4 módulos, bootstrap por bloques de 12 m).
  - Hueco M-2: fechas de existencia de servicios sin energía y TCU total sin fuente primaria (supuestos declarados). **Decisión del usuario:** ¿`principal_desde` prudente para `tcu_gap`?
  - Lanzada la **re-auditoría final** del Validador → `docs/validation/2026-10-15_pit_base_v0.3.md`.

## 2026-10-16
- **Sesión nueva:** la re-auditoría final de la v0.3 no llegó a terminar (no existe veredicto; quedó a medias `tests/validation/pit_v0_3_validation.py`, sin commitear). **Relanzado el Validador** → `docs/validation/2026-10-16_pit_base_v0.3.md`, con permiso para reutilizar el script empezado. Actualización diaria de hoy en marcha (recuperada al encender, 07:46).
- **Re-auditoría final base PIT v0.3: ⚠️ aprobada con 2 condiciones mecánicas** (`docs/validation/2026-10-16_pit_base_v0.3.md`; scripts `tests/validation/pit_v0_3_{validation,power}.py`). Reproducción 8/8 ficheros desde `git archive 64186fe` sin warehouse; 768 + 2.560 celdas por SQL, todas coinciden; 0 publicadas después de t; I-1..I-4, M-1, M-3, M-4, M-6 cerrados; placebo t−4 falla 8/8; señal plantada 0,279 (20/20 en [0,20; 0,40]), control con fuga 0,542; periodo bloqueado intacto; 92/92.
  - **H-1 (MEDIA):** fuente primaria de la Fed (G.17 HistCap): la utilización de la industria **total** (con minería y utilities) existe desde 1983 → `tcu_gap` debería tener `principal_desde` 1984-01 (prudente). Coste: 2 recesiones ≤ 2004. **Decisión del usuario.**
  - **H-2 (MEDIA):** `write_snapshot --freeze --force` con `DATA_VERSION {"0.3": "0.2"}` sobrescribiría la instantánea congelada compartida v0.2 → que se niegue si la versión de datos no es la propia + test.
  - BAJA: B-1 documentar escala z de `infl_energy_pressure`; B-2 entrada v0.3 en trial log; B-3 margen fino del control t−4; B-4 erratas (47 tests; NFCI 2011-12); B-5 conservar CANDIDATE o regenerar meta al congelar; B-6 aclarar P-EVAL-S-PIT-002 (¿ambos ejes?).
  - Tras corregir: comprobación rápida del Validador (sin re-auditoría completa) → FROZEN + tag `pit-v0.3`.
- **Decisión del usuario (16-oct):** `tcu_gap` → `principal_desde` **1984-01** (condicional antes, como el VIX). Lanzado el **Constructor** con H-1, H-2 y B-1..B-6 (la v0.3 mantiene nombre, se regenera; sin FROZEN ni tag). Después: comprobación rápida del Validador → FROZEN + tag `pit-v0.3`.
- **Constructor: correcciones v0.3 hechas** (commit `5b93ebe`, sigue en CANDIDATE). H-1 `tcu_gap` principal desde 1984-01 (cita G.17; recesiones 6(4) → 4(2); nadie hereda). H-2 `write_snapshot` se niega si los datos son de otra versión, también con force (2 tests en tmp). B-1..B-6 hechos (B-6: P-EVAL-S-PIT-002 exige mejora en **ambos ejes**, como aclaración). **Ninguna celda cambia** frente a `64186fe` (matrices, linajes y baselines idénticos bit a bit); meta nuevo `5d496a46…`. 96/96 tests. Procedimiento de congelación documentado en `pit.py`. Lanzada la comprobación rápida del Validador.
- **Comprobación de cierre del Validador: ✅ aprobada** (sección final de `docs/validation/2026-10-16_pit_base_v0.3.md`): H-1 y H-2 cerrados, 8/8 ficheros idénticos desde `git archive 5b93ebe`, B-6 es aclaración legítima, 96/96.
- **El usuario aprueba congelar. Base PIT v0.3 CONGELADA**: entrada en `FROZEN` de `src/features/pit.py` (mismos hashes que CANDIDATE + veredicto, procedimiento B-5), test actualizado (`test_h_current_version_is_frozen_with_verdict`; el guarda H-2 sigue probado con una versión ficticia), 97/97 tests, **tag `pit-v0.3`**. Instantánea de datos ya era de solo lectura (0o444, con respaldo). Meta sin regenerar (opcional según B-5; matrices sin cambios).
- Siguiente: Reportero (base PIT en el informe) y entregable (3) arnés walk-forward.
- Lanzados en paralelo: **Reportero** (base PIT v0.3 en el informe → v0.3 del informe) y **Constructor — entregable (3) arnés walk-forward** (`src/models/`, `docs/models/harness.md`): embargo 6 m, etiqueta recalculada con datos ≤ T, bloqueo técnico del periodo ≥ 2005-01, vintage + latest_truncated sobre los mismos meses, bootstrap por bloques, registro de pruebas automático, baselines mínimos (persistencia PIT, climatología, reglas) solo ≤ 2004. Después: Validador + Estratega.
- **Reportero: informe v0.3** ([[Reports/Fase 3/Informe de resultados]]): §8 base PIT (qué es, calendario, lista blanca 36/13/5/4, tests de fugas y potencia, listón ≤ 2004 61,14 %/63,04 %, historial de validación, limitaciones); gráficos 11-13 (`make_figures_pit.py`). Avisos: el meta v0.3 sigue diciendo "candidata" (no regenerado; la congelación consta en `FROZEN` y en el tag); el listón 63,6 % de §5 (v0.2) incluye meses ≥ 2005 → anotado como no comparable; el listón válido es el ≤ 2004 de §8.5. Cifras de catálogo 15.610 → 15.613 por el warehouse vivo.
- **Constructor: arnés walk-forward v1 terminado** (commit `b01e7ee`; `src/models/{harness,pit_labels,vault,metrics,base,trials}.py`, `docs/models/harness.md`, `config/harness/baselines_v1.yaml`). 115/115 tests (18 nuevos).
  - Cortes expansivos con `refit_every`; embargo ≥ 6 (rechaza menos) + purga s+4 < m0; etiqueta de entrenamiento `PITLabeler.at(T)` (última fila = baselines congelados bit a bit).
  - **Caja fuerte `LabelVault`**: lectura con filtro < 2005-01 (filas ≥ 2005 ni se decodifican), hashes fijados, `HoldoutLocked`, registro `research/trials/label_access.jsonl`; evaluación única solo con preregistro + `FKB_HOLDOUT_UNLOCK` + árbol limpio, de un solo uso.
  - Baselines ≤ 2004 (579 meses): persistencia PIT vintage **61,14 % / 1,2997**, latest_truncated **63,04 % / 1,1824** (listón exacto); climatología 28,67 % / 1,4151 (peor, BSS −0,47). Clasificador de reglas no incluido (no es PIT coherente con v0.3; propuesta: reescribirlo como `Model` en el entregable 4).
  - Placebo sin habilidad; fuga t+1 detectada (+0,21..0,31 nats).
  - **Decisiones del usuario pendientes:** (1) meses provisionales de la etiqueta recalculada (incluir/excluir/ponderar); (2) preregistro P-EVAL-BASE de la evaluación única; (3) episodios NBER ± 6 m + rachas; (4) `min_train_months` 120; (5) clasificador de reglas como baseline.
- Lanzados en paralelo **Validador** (`docs/validation/2026-10-16_harness_v1.md`) y **Estratega macro** (`docs/reviews/2026-10-16_estratega_macro_harness.md`) sobre el arnés; ambos opinan también sobre las 5 decisiones.
- **Estratega macro: arnés ⚠️ "sirve con cambios"** (`docs/reviews/2026-10-16_estratega_macro_harness.md`). Proceso bien; el problema es el listón: una mezcla fija 80 % persistencia + 20 % climatología baja la log-loss de 1,2997 a **0,983** sin ninguna variable → el listón debe ser una **persistencia calibrada M0** ajustada en walk-forward. Los giros (30 % de los meses) son el 63 % de la pérdida, casi todo en el eje G. Pide: M0, métricas por eje (P-EVAL-MOD no es ejecutable sin ellas), cortes giro/estable, épocas, cuadrante, frontera, retraso de detección, calibración; bootstrap 24 m como sensibilidad; ventana de evaluación fija; ventanas por eje; `sample_weight`. Recomendaciones: (a) provisionales con peso 0,5; (b) P-EVAL-BASE = M1 vs M0 vintage 2005-01→2021-10, ≥ 0,05 nats con IC > 0 + condiciones por eje/giro/subperiodo; (c) NBER ± 6 m + rachas ≥ 6 m + giros de G; (d) 120 m + ≥ 2 recesiones + ≥ 8 cambios de G, L2 fija; (e) reglas sí, prioridad baja. Logística a priori: una por eje, con el logit de la persistencia; G: growth_rt, unrate_sahm, baa_spread, eq_ret_6m, curve_10y3m; I: core_cpi_6m_ann (≥ 1978) / headline antes. Cálculos C1/C2 en el trial log (scripts en `research/trials/estratega_2026-10-16/`). Esperando al Validador.
- **Validador: arnés v1 ⚠️ condicional** (`docs/validation/2026-10-16_harness_v1.md`; `tests/validation/harness_v1_validation.py`). Vale para desarrollo ≤ 2004; **no para la evaluación única** hasta cerrar A-1. Reproducción exacta (hash `27cae755…`, 1e-16); `at(T)` no depende de datos > T; espía en 576 cortes × 2 modos sin violaciones; embargo 6 basta (margen 2 m); 0 celdas imputadas.
  - **A-1 (ALTA):** la evaluación única no la garantiza el código (demostrado con etiqueta sintética): redirigiendo `FKB_TRIALS_DIR` se reabre el mismo preregistro; `run(cfg, datas=…)` en `holdout_evaluation` salta la caja fuerte; `PITData` acepta cualquier objeto con `.mode`; git que falla se da por limpio; cualquier hipótesis "preregistrada" abre el periodo.
  - MEDIA: M-1 vías sin barrera (`PITLabeler.at(T ≥ 2005)`, ficheros/figuras hasta 2026, `score_training` con `<=`); M-2 la ventana por época reinicia el entrenamiento (desde 1994 no ve los 70); M-3 muestra común se reduce sin aviso; M-4 provisionales entrenan contra la ficha §7/§12 (concordancia 83 % a 6-12 m, 95-98 % a 60-120); M-5 placebo poco potente frente a fugas débiles (sesgo −0,13); M-6 faltan métricas por eje, Holm, estabilidad, calibración.
  - Coincide con el Estratega en (a) ponderar por madurez, (b) P-EVAL-BASE tras cerrar A-1, (c) NBER ± 6 m, (e) reglas sí.
- **Decisiones del usuario (16-oct) sobre el arnés:** (1) **aprueba el paquete completo** (A-1, M-1..M-6, M0 como listón, cortes, ventana fija, pesos por mes); (2) provisionales **ponderados por madurez** (función a priori desde el estudio de revisión; peso 1 y excluir como sensibilidades; adenda a la ficha §7/§12); (3) **ventanas por eje** (modelo G y modelo I) + mínimo 120 m con ≥ 2 recesiones y ≥ 8 cambios de G, L2 a priori; (4) episodios NBER ± 6 m + rachas ≥ 6 m + giros de G; clasificador de reglas como `Model` (prioridad baja); **P-EVAL-BASE** lo redacta el Constructor como borrador (`docs/models/p_eval_base_draft.md`) y lo aprueba el usuario antes de registrarlo.
- Lanzado el **Constructor: arnés v2**. Después: re-auditoría del Validador.
- (El Constructor del arnés v2 se paró por el límite de uso de la sesión; reanudado tras el reinicio, 12:40.)
- **Constructor: arnés v2 terminado** (`e58a054` código/tests/docs; `2159d53` corrida oficial con árbol limpio). 144 tests. Registro de consumo `research/holdout/evaluations.jsonl` vacío; nada ≥ 2005 abierto.
  - A-1: entrada única `harness.evaluate_holdout(prereg_id)`; solo ids `P-EVAL-` con `tipo: evaluacion_holdout`; `FKB_HOLDOUT_UNLOCK`; git falla cerrado (árbol limpio, raíz); registro de consumo en ruta fija rastreada, sin borrados en el historial, commiteado antes de leer; caja auténtica por tipo/identidad. Cada ataque del Validador tiene su test (repo temporal + etiqueta sintética). **No** hay separación física/cifrado (cambiaría artefactos congelados → decisión del usuario; `harness.md` §10).
  - M-4 pesos de madurez a priori: 0,858 (k ≤ 12) … 1 (k ≥ 56); adenda en `label_spec.md` §7/§12/§13. M-2 `AxisModel` (un modelo por eje, producto exacto; correlación de residuos G-I 0,015). M0 = Λ(a + b·logit P_persistencia) por eje, L2 1,0 a priori.
  - **Resultados ≤ 2004 (ventana 1975-01→2004-12, 360 m), M0 frente a persistencia cruda:** vintage **+0,341 nats** [+0,145; +0,579] (1,152 → 0,811); eje G +0,258, eje I +0,063; giros +1,270 (2,46 → 1,19); estables +0,032; 15/16 giros de G ganados; **retraso de detección casi igual (4,00 → 3,81 m)** → la calibración no adelanta la detección; ese es el margen de las variables. latest_truncated +0,234.
  - Placebo pareado (20 semillas, 0,02 nats): detecta t+1/t con σ1, t−4, t−1; control t−5 sin falsa alarma; **no detecta fugas σ=2 (~0,015)**; 2 ajustes post hoc en el trial log.
  - Borrador `docs/models/p_eval_base_draft.md` (NO registrado). No hecho: clasificador de reglas (→ entregable 4). Aviso: con ≥ 2 recesiones el eje G con `growth_rt` entrena desde ~1975-05 y el eje I con IPC subyacente desde ~1988 → M1 necesita ventana/épocas en su preregistro.
- Lanzada la **re-auditoría del Validador** → `docs/validation/2026-10-16_harness_v2.md`.
- **Re-auditoría arnés v2: ⚠️ condicional** (`docs/validation/2026-10-16_harness_v2.md`). **Aprobado para desarrollo ≤ 2004 y para construir M1 (entregable 4)**; evaluación única bloqueada hasta A2-1, M2-1, M2-2. Reproducción exacta (`1a6d6df8…`, r10 `509dba25…`), 144 tests, placebo idéntico, M0 reproducido y sin fuga (insensible a eps/L2: 0,8107-0,8159).
  - D1-D9 cerrados con barrera técnica. Abiertas: N2 `git reset --hard`/rama vieja reabren una evaluación consumida; N8 carrera entre dos procesos; N1 caja forjada (declarado); N7 resultados redirigibles; N6 ignorados no cuentan como sucio. Recomienda **anclar el registro fuera de la máquina** (push o sello de tiempo) > copias ≤ 2004 por defecto > cifrado opcional.
  - **A2-1 (ALTA):** P-EVAL-BASE (borrador) no ejecutable: módulos H-MOD no elegibles hasta ~2021-09; eje I por épocas sin implementar; con `allow_shrink: false` fallaría tras gastar el preregistro. Primeros cortes: G 1975-06, I (IPC subyacente) 1988-06.
  - MEDIA: M2-1 registro contra `--all`/reflog + cerrojo + ancla externa; M2-2 ensayo en seco sin abrir nada; M2-3 defectos en detección de giros (retraso hasta inicio, censurados mezclados, parpadeos, ventanas solapadas); M2-4 faltan signos de coeficientes/`sign_stability` y Holm de P-EVAL-MOD; M2-5 regla complementaria del placebo (signo p < 0,01 o t > 3 sobre 20 semillas; detecta σ=2 al 90 %).
- **Decisiones del usuario (16-oct) tras la re-auditoría v2:** (a) ancla externa = **repositorio privado en GitHub** (push del commit de consumo antes de leer; si falla, no hay evaluación); `gh` sin sesión → el usuario debe hacer `gh auth login`; (b) **módulos H-MOD fuera de P-EVAL-BASE** (preregistro propio más adelante); (c) seguir con las dos cosas en paralelo.
- Lanzados: **Constructor (arnés v2.1)** — M2-1 (todas las refs + reflog + cerrojo + ancla GitHub, probado con remoto bare local), M2-2 ensayo en seco, A2-1 P-EVAL-BASE ejecutable (borrador), M2-3 detección de giros, M2-4 signos/Holm, M2-5 regla complementaria del placebo; y **Constructor (entregable 4, M1)** — especificación a priori commiteada antes de correr (`docs/models/m1_spec.md`, H-M1-001): logística por eje (G: growth_rt, unrate_sahm, baa_spread, eq_ret_6m, curve_10y3m; I: core_cpi_6m_ann ≥ 1978 / headline antes) + clasificador de reglas como `Model`; placebo antes de resultados; solo ≤ 2004.
- **Usuario (16-oct):** pide ir guardando por consumo de tokens; hará `gh auth login` más tarde. Retomar: ver "Retomar aquí (16-oct)" en el Estado.
- **Constructor M1:** especificación a priori commiteada **antes** de correr con la etiqueta (`bf7049d`, `docs/models/m1_spec.md`, H-M1-001); arreglo técnico del placebo (`353ac63`, falló antes de producir salida). Placebo/corridas ≤ 2004 en marcha.
- (Los dos Constructores se pararon por el límite de uso; reanudados tras el reinicio de las 17:40.)
- **Constructor: arnés v2.1 terminado** (`2fd94e0` código/tests, `b626919`, `cd6d68a` borrador P-EVAL-BASE v2, `6902ad3` corrida oficial + ensayo en seco). 178/178 tests.
  - Ancla GitHub: `evaluate_holdout` exige `origin` en github.com; con cerrojo `fcntl`: fetch, push, anota consumo, commit, push y verificación en remoto **antes** de leer; si falla, id gastado y caja cerrada. M2-1: consumo comprobado en todas las refs + reflog; test de carrera. N6 ignorados cuentan como sucio (excepciones declaradas). N7 rutas fijas. M2-2 ensayo en seco obligatorio y commiteado (`research/holdout/dry_runs.jsonl`) con el mismo hash. M2-3 detección redefinida (11 giros de G sin parpadeos; retraso hasta confirmación; censurados aparte). M2-4 signos/`sign_stability`/Holm. M2-5 regla complementaria del placebo.
  - **P-EVAL-BASE v2 (borrador, no registrado):** M1 `m1_logit_axis` (L2 = 6) vs M0; eje I solo IPC subyacente; ventana 2005-01→2021-10; sensibilidades latest_truncated, Filadelfia, pesos uno/excluir; `incluye: []`. Ensayo con sonda ok (el primer ensayo detectó que con `excluir` el eje I no es elegible hasta ~1992-11 → habría gastado el preregistro).
  - M0 ≤ 2004 con la detección v2.1 (vintage): giros G 11, 10 detectados; retraso 4,9 → 4,6 m (pareado −0,3); 10/11 giros ganados (p = 0,012); log-loss sin cambios (0,811).
  - **Pendiente del usuario:** GitHub (`gh auth login`, repo privado, `origin`, push) y aprobar P-EVAL-BASE v2 (+ `incluye: []`, sensibilidades de L2 sí/no). Validador: esperar a M1 para auditar v2.1 + M1 juntos.
- **Constructor M1 (entregable 4) terminado — resultado NEGATIVO en desarrollo** (`bf7049d` spec a priori → `9b64c5c` resultados; `docs/models/m1_results_dev.md`). 178 tests. Sin señal de fuga (placebo M1 −0,036, sin aviso; M0/persistencia idénticas bit a bit a los baselines).
  - M1 = logit de la persistencia + variables por eje, L2 = 6 a priori. 3 cambios post hoc técnicos antes de puntuar (claves del placebo; reglas antes de `growth_rt`; **ventana principal 1988-06 → 1989-10** por continuidad de elegibilidad del eje I).
  - **M1 − M0 (vintage ≤ 2004):** principal 1989-10→2004, M1 subyacente **−0,019** [−0,128; +0,076] (eje I −0,032); M1-general +0,015; larga 1975-06→2004 M1-general **+0,046** [−0,016; +0,103]. La mejora viene de meses estables (+0,069), **no de los giros** (−0,021; principal −0,16). Detección más rápida (3,81 → 2,75 m) pero menos giros detectados (13/16 vs 15/16) y falsas alarmas 0,30 → 0,55/año. Holm p ≥ 0,24. Reglas: −0,57/−0,84, no aportan.
  - Coeficientes con el signo preregistrado salvo **`unrate_sahm` positivo en ~100 % de cortes**. "Excluir provisionales" rompe el eje I con subyacente (mal identificado).
  - Placebo: con la L2 de M1 la regla de 0,02 no detecta la fuga t−4; la complementaria sí.
  - **Decisiones del usuario:** (1) Sahm con signo contrario (mantener vs M1 v2 contaminada); (2) eje I para P-EVAL-BASE (subyacente empeora; cambiar = selección con datos de desarrollo; alternativa: eje I casi estructural); (3) ¿gastar el periodo bloqueado en esta M1? No cumple criterios 1, 3, 5 del borrador.
- Lanzados **Validador** (re-auditoría arnés v2.1 + auditoría M1 → `docs/validation/2026-10-16_harness_v2_1_m1.md`) y **Estratega** (M1 → `docs/reviews/2026-10-16_estratega_macro_m1.md`).
- **Estratega: M1 ❌ "no gastar el periodo bloqueado en M1 v1"** (`docs/reviews/2026-10-16_estratega_macro_m1.md`). Sin fuga ni error; fallo de diseño económico (sus propias variables). Estudio de eventos (C3): M0 no se compromete; M1 se compromete mal — sigue viendo fortaleza en caídas de G (`growth_rt` coincidente, ~t−2) y se adelanta 4-6 m en subidas (curva/bolsa anticipan 6-12 m, la etiqueta mira 4). Ningún coincidente ve el giro antes de ~+2 m. Sahm (C4) = rebote post-recesión, no colinealidad.
  - Cambia su listón (anotar como cambio de criterio previo a la evaluación): giros ≥ 0 frente a M0, falsas alarmas ≤ 0,5/año, total ≥ 0,05.
  - Propone **M1 v2** (post hoc declarada), 3 cambios con mecanismo commiteado antes de correr: sin Sahm en nivel; eje I estructural (pendiente fija 1,7·(core − 2,9)/0,75; sensibilidades 0,5/1,0); variables de riesgo de giro de una **base PIT v0.4** (claims_4w_yoy, curve_min12, baa_gap10y, baa_d6m, sahm_d3m, Filadelfia). Una sola corrida de desarrollo; en la evaluación única v1 y v2 juntas frente a M0 con Holm k = 2. Siguiente aspirante: Markov con transiciones variables (Filardo).
- **Validador: arnés v2.1 ✅ con condiciones operativas; borrador P-EVAL-BASE v2 ⚠️; M1 ✅ (proceso íntegro; conclusión "no bate a M0" correcta)** (`docs/validation/2026-10-16_harness_v2_1_m1.md`). Reproducción bit a bit (baselines v2.1, M1 principal y larga, placebo, ensayo en seco), 178 tests. Spec M1 (`bf7049d`, 14:03) anterior a toda métrica; cambio de ventana 1989-10 técnico y neutro; sin fuga (espía); Sahm positivo en el 100 % de cortes.
  - A3-1 (MEDIA): reabrir es posible si se reescribe el remoto con force-push + `gc` del reflog → **condición para registrar P-EVAL-BASE: protección de rama en GitHub (sin force-push ni borrado) comprobada por el código**. BAJA: acta obligatoria de `_commit_results`; hash del ensayo sin `hypotheses.yaml`; doble conteo de anticipación tras censurado; estabilidad de signos decidida por cortes < 2005.
  - Coincide con el Estratega: **no gastar el periodo bloqueado en M1 v1**; M1 v2 como hipótesis nueva marcada contaminada (quitar Sahm lineal); eje I subyacente (no cambiar al general).
- **Decisiones del usuario (16-oct, noche):** (1) **acepta el criterio nuevo** (giros ≥ 0 frente a M0, falsas alarmas ≤ 0,5/año, total ≥ 0,05 nats), anotado en trial log y en el borrador P-EVAL-BASE; (2) **parar aquí**: el plan M1 v2 + base PIT v0.4 (o Markov) queda **pendiente de decidir** otro día. No se gasta el periodo bloqueado en M1 v1.

## 2026-10-23

- **Retomado.** Automatización ok (diaria 23-oct ✅; semanal 22-oct ⚠️ en 5 fuentes por DNS al arrancar sin red, transitorio). Informe semanal 22-oct commiteado.
- **GitHub:** `gh` con sesión, `origin` = github.com/victorhdez12/financial_kb, `main` al día. La protección de rama en repo privado exige GitHub Pro (403).
- **Decisiones del usuario (23-oct):** (1) **seguir con M1 v2 + base PIT v0.4** (propuesta del Estratega, `docs/reviews/2026-10-16_estratega_macro_m1.md` §4-§5); (2) **repo público por ahora** (volver a privado si se comercializa). Revisado antes el historial: sin claves de `.env`, sin datos (solo CSV de auditoría de metadatos).
- Hecho: repo **público**; protección de `main` activada (`allow_force_pushes=false`, `allow_deletions=false`, `enforce_admins=true`) → condición A3-1 del Validador cubierta en GitHub; falta que el código la compruebe antes de registrar P-EVAL-BASE.
- ⚠️ Nota: si el repo vuelve a privado sin Pro, la protección se pierde → hacer la evaluación única **mientras sea público** (o pagar Pro).
- Lanzado **Constructor (base PIT v0.4 + M1 v2 + comprobación de protección de rama)**.
- **Constructor: base PIT v0.4 candidata** (commit `657b6eb`): 4 derivadas de riesgo de giro del Estratega §5 —
  `curve_min12` (mínimo de la curva en 12 m), `baa_gap10y` (Baa frente a su mediana de 10 años), `baa_d6m` (Δ6m del
  Baa), `sahm_d3m` (Δ3m de la Sahm)— fijadas a priori con mecanismo y signo. `claims_4w_yoy` y Filadelfia ya estaban en
  la v0.3. Misma instantánea de datos y mismo calendario: las 58 columnas de la v0.3, linajes y baselines **idénticos
  bit a bit**. En `CANDIDATE`, **no** en `FROZEN` (falta el ✅ del Validador). Tests nuevos (`tests/test_pit_v04.py`,
  20): superconjunto, valores a mano, causalidad, truncamiento, placebo (sin fuga −0,235; fuga +0,373; t−4 media
  +0,030, pareado +0,22…+0,33 en 8/8 — lectura pareada añadida tras ver el margen, anotada como post hoc del test),
  señal plantada. El arnés admite `pit_version` (la candidata solo en desarrollo).
- **Constructor: A3-1 del Validador** (commit `f1ccc8f`): `check_branch_protection` consulta `gh api
  …/branches/main/protection` y exige `allow_force_pushes=false`, `allow_deletions=false`, `enforce_admins=true`;
  falla cerrado. Se llama al abrir la caja (antes del cerrojo y del consumo), en `evaluate_holdout` y en el ensayo en
  seco registrado. Comprobado hoy en GitHub: ok. CLI `python -m src.models.harness --check-protection`. Tests con
  respuestas simuladas.
- **Constructor: especificación a priori de M1 v2** commiteada y empujada **antes** de cualquier corrida con la
  etiqueta (commit `4d2b1ac`; `docs/models/m1_v2_spec.md`, H-M1-002 **declarada contaminada**). Eje G: growth_rt,
  claims_4w_yoy, curve_min12, baa_gap10y, baa_d6m, eq_ret_6m, sahm_d3m (L2 = 6); eje I estructural
  1,7·(core − 2,9)/0,75 (sensibilidades s = 0,5 y 1,0); sin Sahm en nivel; Filadelfia fuera (no está en la lista final
  del Estratega). Ventanas (recuento sin ajustar modelos): principal 1989-10 → 2004-12 (la de M1 v1), larga del eje G
  1978-07 → 2004-12. Una sola pasada.
