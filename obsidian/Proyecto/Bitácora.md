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
