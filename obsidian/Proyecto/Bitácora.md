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
