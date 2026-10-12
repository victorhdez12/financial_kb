---
tipo: estado_proyecto
actualizado: 2026-10-12 (tarde)
fase_real: recopilación y limpieza de datos
---

# Estado del proyecto

> [!info] Para retomar en una sesión nueva
> Lee esta nota, después [[Proyecto/Agentes]] (roles e instrucciones completas) y [[Proyecto/Bitácora]] (qué se hizo y cuándo).
> Código: `~/Desktop/financial_kb` · Datos: `~/financial_archive` (enlace `data/archive`) · Plan original: `docs/PLAN.md`.

## Fase actual (decisión del 2026-10-12)

Aunque `docs/PLAN.md` ya habla de la Fase 2 (Neo4j, agentes de decisión), **seguimos en la fase de datos**: recopilar, limpiar, almacenar y auditar.
- **Agentes activos:** recopiladores (EE. UU., Europa/BCE/España e internacional) y un auditor de datos.
- **Aparcados hasta tener datos completos y fiables:** abogado del diablo, comité, estratega y cuantitativo.

## Hecho

- **Fase 0** (2026-10-07): limpieza, git y datos unificados en `data/archive`.
- **Fase 1** (2026-10-07, commit `9c3f887`): base de datos DuckDB, clasificador de régimen desde 1950 (4 cuadrantes, ciclo de deuda, crédito y liquidez), validación en `docs/phase1_validation.md` y primer reporte en [[Reports/2026-10-07_semanal]].
- **Fase 2a** (sin commitear): Neo4j local en Docker (`src/graph/`, `make graph-up/graph-load`) e ingestas de ciclos (BIS, NY Fed, RTDSM).
- **Revisiones de la Fase 1:** `docs/reviews/2026-10-07_estratega_macro.md` y `docs/reviews/2026-10-07_pm_abogado_diablo.md`. Veredicto: **el reporte aún no sirve para decidir.**
- **Auditoría de datos** (2026-10-12): `docs/data/audit_2026-10-12.md` y su CSV. Reejecutar con `.venv/bin/python -m src.audit.run`.

## Inventario de datos (`~/financial_archive/curated`, 2026-10-12 por la mañana)

| fuente | series | estado |
|---|---|---|
| fred | 362 | ámbar (auditoría) |
| alfred | 14 | ámbar; ampliándose |
| bis | 688 | ámbar |
| jst_macrohistory | 998 | verde (solo uso no comercial) |
| maddison | 517 | ámbar (catálogo duplicado) |
| spf | 488 | verde |
| ken_french, damodaran, gpr, sipri, boe_millennium_uk | 88, 19, 99, 77, 45 | verde |
| shiller, nyfed, rtdsm, nber_macrohistory, wb_pinksheet | 21, 42, 16, 39, 87 | ámbar |
| gold, imf_cofer | 10, 58 | rojo |
| **EE. UU. (terminado):** fred_us, fed_yieldcurve, us_treasury, nyfed_hhdc, us_hist_labor, shiller_housing, + alfred 14, nber_macrohistory 1.627 | 1.691, 73, 25, 103, 2, 9 (~3.500 en total) | hecho y auditado (tarde). Doc: `docs/data/us_macro_credit.md` |
| **nuevas hoy (internacional, terminado):** bis_ext, oecd, imf_weo, imf_gdd, imf_hpdd, wb_wdi, measuringworth | 366, 309, 955, 155, 31, 375, 16 (2.207 en total) | hecho y auditado (tarde). Doc: `docs/data/international_macro.md` |
| **Europa (terminado):** ecb, eurostat, bde, ine, bundesbank | 116, 98, 53, 13, 19 (299 en total) | hecho y auditado (tarde). Doc: `docs/data/europe_macro_financial.md` |

## Problemas abiertos (reauditoría del 2026-10-12 por la tarde)

Los problemas en rojo de la mañana (fallo del IPC, base de datos desfasada, TED, oro en los análogos, look-ahead sin marcar y COFER) están **corregidos**: ver `docs/data/audit_2026-10-12_tarde.md`. Ya no hay ninguna fuente en rojo.

Quedan problemas de prioridad MEDIA que no bloquean:
- **`BOGZ1FL073164003Q`:** unidades mal en el catálogo y salto ×10 en 1952.
- **`nber_m12014`:** 1915 dividido por 10.
- **`shiller_gs10`:** el dato de 2019-07 está desplazado.
- **Arroz:** valores a 0 en 2008; hay que limpiarlo en `wb_pinksheet.py`.
- **M1SL:** ruptura de definición en 2020-05.
- **Eventos:** tipo `inflation_crisis` fuera del contrato y `cow_extra_321` con fechas al revés.
- **Catálogo de maddison:** filas duplicadas.
- **rtdsm:** sin conectar al clasificador.
- **Fuentes nuevas:** quedan muchas MEDIA por revisar (`fred_us`, `imf_weo`).

Huecos de fuentes (de pago o sin API):
- PMI, Lebergott/Weir, Homer & Sylla, Global Financial Data y Euribor diario.
- Banque de France (exige clave).
- EPA 1976-2001 (solo en INEbase).
- IFS del FMI sin curar.
- Release 388 de FRED (1914-41) y Z.1 completo (zip de la Fed).

## Próximos pasos

1. Corregir los problemas MEDIA de la lista anterior (los scripts de ingesta afectados, sin tocar los datos a mano).
2. Cubrir los huecos accesibles: release 388 de FRED, Z.1 completo, IFS del FMI, EPA anterior a 2002 (PC-Axis del INE) y repo BGCR/TGCR.
3. Volver a ejecutar `imf_weo` cuando salga el WEO de octubre de 2026, guardando antes la versión de abril.
4. Pendientes de la revisión de la Fase 1, que seguirán cuando el usuario dé por cerrada la fase de datos: histéresis de G, I compuesta (que incluya petróleo y PPI), bear frente a bull steepening y capa EUR.
5. Ciclo de mantenimiento: `make data` (ingest → warehouse → regime → audit).
