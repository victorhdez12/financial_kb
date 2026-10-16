---
tipo: estado_proyecto
actualizado: 2026-10-15
fase_real: Fase 3 (modelos); fase de datos cerrada el 14-oct
---

# Estado del proyecto

> [!info] Para retomar en una sesión nueva
> Lee esta nota, después [[Proyecto/Agentes]] (roles e instrucciones completas) y [[Proyecto/Bitácora]] (qué se hizo y cuándo).
> Código: `~/Proyectos/financial_kb` (movido del Escritorio el 13-oct) · Datos: `~/financial_archive` (enlace `data/archive`) · Plan original: `docs/PLAN.md`.

## 🎯 Objetivo de la Fase 3 (acordado el 14-oct)

**Tener un nowcast del régimen de EE. UU. validado:** que el sistema diga cada mes en qué cuadrante estamos y con qué probabilidad, usando solo la información disponible en esa fecha, y que esté demostrado en un backtest honesto que lo hace mejor que las alternativas sencillas.

**Entregables, por orden:** (1) ✅ etiqueta **v1.1** congelada y validada ✅ (15-oct, tag `label-v1.1`; [[Proyecto/Etiqueta de régimen]]) · (2) ✅ base point-in-time **v0.3 congelada** (16-oct, tag `pit-v0.3`, validador ✅) · (3) ▶ arnés walk-forward (embargo 6 m, periodo 2016-2026 bloqueado, registro de pruebas) · (4) baselines: persistencia, reglas, logística, Markov · (5) GBM solo si los bate · (6) calibración. En paralelo: investigación de relaciones adelantadas (las validadas entran como variables).

**Criterios de cierre:**
- [ ] Bate a la persistencia en log-loss fuera de muestra, también en el periodo bloqueado, con intervalos que no incluyen el cero.
- [ ] Probabilidades calibradas.
- [ ] Sin fugas: test point-in-time, placebo y señal plantada superados.
- [ ] Las relaciones que usa tienen mecanismo, son estables por épocas/países y sobreviven a la corrección por comparaciones múltiples.
- [ ] **Veredicto ✅ del Validador independiente.**
- [ ] Ficha del modelo + informe de resultados del Reportero.
- [ ] Sustituye al clasificador de reglas en el reporte semanal.

**Fuera de esta fase:** factores y cartera (siguiente fase), zona euro, forecast a 6 m, informe para empresas.

**Agentes de la fase:** Constructor · Investigador de relaciones · **Validador independiente** · **Reportero** (ver [[Proyecto/Agentes]]). Informe: [[Reports/Fase 3/Informe de resultados]].

## ▶ Retomar aquí (16-oct)

**Base PIT v0.3 CONGELADA** (tag `pit-v0.3`; veredicto ✅ `docs/validation/2026-10-16_pit_base_v0.3.md`; `tcu_gap` principal desde 1984-01 por decisión del usuario). Siguiente: Reportero (base PIT en el informe) → **entregable (3) arnés walk-forward** (ver punto 5 de abajo) → circuito Validador + Estratega.

## Retomar (15-oct, tarde) — histórico

**Dónde estamos:** Fase 3, entregable (2) **base point-in-time**, a punto de cerrarse.
- ✅ (1) Etiqueta **v1.1 congelada** (tag `label-v1.1`, validador ✅). Listón: persistencia PIT.
- ⏳ (2) Base PIT: v0.1 → v0.2 (re-auditoría ⚠️ "muy cerca de ✅", `docs/validation/2026-10-15_pit_base_v0.2.md`) → **v0.3 candidata hecha** (commit `64186fe`, 92/92 tests; **re-auditoría final del Validador en marcha**) con las correcciones: herencia automática de `principal_desde` (infl_energy_pressure), `vix` condicional < 2003-09, control "etiqueta t−4" en el placebo + tabla de potencia honesta, v0.3 **fuera de `FROZEN` hasta el ✅**, hash del meta de la etiqueta en los baselines, preregistros completos.
- Documentos clave: `docs/models/pit_base.md` (registro de cambios por versión), `docs/models/pit_calendar.md`, `research/pit_whitelist.yaml`, `research/hypotheses.yaml`, `research/trial_log.md`.

**Pasos para seguir (en orden):**
1. ✅ v0.3 terminada y commiteada.
2. (16-oct) Validador relanzado → `docs/validation/2026-10-16_pit_base_v0.3.md`. Si no existe al retomar, relanzarlo con el encargo de la Bitácora.
3. **Re-auditoría final del Validador** sobre la v0.3 → `docs/validation/<fecha>_pit_base_v0.3.md`. Si da ✅: meter la v0.3 en `FROZEN` (`src/features/pit.py`), tag `pit-v0.3`, instantánea de solo lectura, Bitácora y este Estado.
4. Reportero: añadir la base PIT al informe ([[Reports/Fase 3/Informe de resultados]]).
5. Siguiente entregable **(3) arnés walk-forward**: modo principal `vintage` (ALFRED) y `latest_truncated` como sensibilidad, puntuando en los dos sobre los mismos meses; etiqueta de entrenamiento recalculada con datos ≤ T en cada corte; embargo 6 m; periodo bloqueado 2005-01→ intocable; variables solo desde la lista blanca + `assert_no_forbidden`; estabilidad de cada variable a ambos lados del salto revisado → primera publicación; registro de pruebas. Baselines a batir (≤ 2004, 579 meses): vintage 61,1 % / log-loss 1,300; latest_truncated 63,0 % / 1,182.
6. Circuito en cada hito (preferencia del usuario): Constructor → **Validador** + **Estratega macro** en paralelo → paquete de correcciones al usuario → Constructor → **re-auditoría**.

**16-oct:** re-auditoría v0.3 ⚠️ con 2 condiciones (H-1 `tcu_gap` desde 1984-01, **decidido por el usuario**; H-2 guarda de `write_snapshot`) → Constructor corrigiendo → comprobación rápida del Validador → FROZEN + tag.

**Pendiente de decisión del usuario (no urgente):** v0.3 de la lista blanca con `permit_yoy` sobre media de 3 m y "sorpresa de inflación" (propuestas del Estratega no aprobadas aún); empalme VIX con VXO; inicio real del IPC subyacente del BLS (hueco).

### Retomar (14-oct, histórico)

**Fases del plan (`docs/PLAN.md`) y estado:**
| Fase | Contenido | Estado |
|---|---|---|
| 0 | Limpieza, git, datos unificados | ✅ hecha (7-oct) |
| 1 · MVP | DuckDB, clasificador de régimen, reporte semanal | ✅ hecha (7-oct); la revisión dijo que el reporte aún no sirve para decidir |
| Fase de datos (añadida por el usuario el 12-oct) | Recopilar, limpiar, auditar | ✅ cerrada el 14-oct: 15.397 series, 12,25 M filas, fusionada en `main` |
| 2 | Neo4j, textos (Dalio, Berkshire, 10-K), agentes Scout/Estratega/Abogado del diablo | 🟡 empezada y aparcada (Neo4j en Docker, ingestas de ciclos/textos); agentes de análisis parados hasta cerrar datos |
| 3 | Modelos (ver `docs/PLAN.md`, "Fase 3 — arquitectura de modelos") | ▶ **siguiente**: etiqueta + base point-in-time + test de fugas |
| 4 | Cron diario, analista de empresas, calculadora fiscal, dashboard | 🟡 actualización automática montada el 13-oct; resto pendiente |
| +6 meses | Paper trading antes de dinero real | ⏳ |

**Hecho el 14-oct:** auditoría completa con las fuentes nuevas (`docs/data/audit_2026-10-14.md`, 0 críticas), arreglos de INE (EPA por sexo), CFTC (ECU) y `PIT_RULES`, reporte [[Reports/2026-10-14_semanal]] y commit en `fase-datos`. Tarea launchd de arranque (`com.financialkb.arranque`) instalada: recupera la actualización perdida al encender el Mac.

**14-oct (tarde):** etiqueta de régimen v0.2 lista ([[Proyecto/Etiqueta de régimen]]: 13/13 comprobaciones; falta decidir 4 propuestas y congelar v1.0). Programa de investigación de relaciones adelantadas en `docs/models/research_program.md`. Futuros y derivados integrados (5 fuentes, 213 series; decisión pendiente: ¿pagar Databento/Norgate?). Base de datos: 15.610 series, 12,53 M filas.

**Siguiente paso (Fase 3, orden de `docs/PLAN.md`):**
1. Especificación de la etiqueta de régimen (ex post, nowcast vs forecast, horizonte) + matriz de variables point-in-time + test de fugas.
2. Pendientes de la revisión de la Fase 1 como variables (histéresis de G, inflación compuesta, bear/bull steepening, liquidez neta diaria y global, capa EUR).
3. Arnés walk-forward → baselines (persistencia, reglas, logística, Markov) → GBM → calibración → etapa 2 + cartera → reglas de oro → informe con Claude → paper trading.
- Más adelante: reactivar la Fase 2 (grafo y agentes de análisis). Volver a ejecutar `imf_weo` con el WEO de octubre de 2026.

## Fase de datos (decisión del 2026-10-12; cerrada el 14-oct)

Aunque `docs/PLAN.md` ya habla de la Fase 2 (Neo4j, agentes de decisión), **seguimos en la fase de datos**: recopilar, limpiar, almacenar y auditar.
- **Agentes activos:** recopiladores (EE. UU., Europa/BCE/España e internacional) y un auditor de datos.
- **Aparcados hasta tener datos completos y fiables:** abogado del diablo, comité, estratega y cuantitativo.

## Hecho

- **Fase 0** (2026-10-07): limpieza, git y datos unificados en `data/archive`.
- **Fase 1** (2026-10-07, commit `9c3f887`): base de datos DuckDB, clasificador de régimen desde 1950 (4 cuadrantes, ciclo de deuda, crédito y liquidez), validación en `docs/phase1_validation.md` y primer reporte en [[Reports/2026-10-07_semanal]].
- **Fase 2a** (sin commitear): Neo4j local en Docker (`src/graph/`, `make graph-up/graph-load`) e ingestas de ciclos (BIS, NY Fed, RTDSM).
- **Revisiones de la Fase 1:** `docs/reviews/2026-10-07_estratega_macro.md` y `docs/reviews/2026-10-07_pm_abogado_diablo.md`. Veredicto: **el reporte aún no sirve para decidir.**
- **13-oct:** 7 arreglos MEDIA cerrados (incluido un fallo real en Maddison regional), 6 fuentes nuevas (release 388, Z.1, repo SOFR/BGCR/TGCR, liquidez EE. UU., balances de bancos centrales, IFS del FMI) e `ine` ampliado (EPA desde 1976, IPC desde 1961). Base de datos: **14.026 series**, 6,46 M de filas. Auditoría `docs/data/audit_2026-10-13.md`: 0 críticas, 32 altas explicadas. Reporte [[Reports/2026-10-13_semanal]].
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

## Actualización automática (desde el 13-oct)
launchd en el Mac: **diario** lun-sáb 7:30 (`make daily`: fuentes diarias + warehouse + régimen) y **semanal** domingo 7:00 (`make semanal`: todo + auditoría + reporte). Resultado de cada ejecución en [[Proyecto/Actualizaciones]]; notificación de macOS si falla algo. Detalle: `docs/automatizacion.md`.

## Segunda tanda del 13-oct (huecos de prioridad alta)
- Factores: `ken_french_intl` (internacional y diario), `aqr` (QMJ con España, BAB, VME, TSMOM, Century; **sin redistribuir**), `jkp` (13 temas, 12 zonas; **no comercial**).
- Mercado y sentimiento: `cftc_cot` (posicionamiento, 21 contratos), `cboe` (VIX3M, VVIX, SKEW, put/call…), `fed_ebp` (excess bond premium), +51 en `fred_us` (Brent diario, encuestas regionales de la Fed, dólar AFE/EME).
- Europa y España: Bund diario 1-30 años, forwards y estrés soberano diario del BCE, empleo euro, vivienda España (IPV, compraventas, hipotecas), producción industrial, `ifo`, `zew`; IPC de la OCDE desbloqueado.
- Series diarias de FRED que estaban congeladas: arregladas.
- Base de datos: **15.397 series, 12,2 M de filas.**
- Huecos que quedan: PMI (de pago), bonos soberanos diarios por país salvo Alemania, Euribor diario, MOVE, flujos ICI e Inverco, índices MSCI/STOXX con dividendos.

## Liquidez (petición del 13-oct)
Datos para medir cuánta liquidez meten la Fed, el Tesoro y los grandes bancos centrales (doc `docs/data/liquidity_2026-10-13.md`):
- EE. UU.: balance de la Fed (WALCL + detalle H.4.1), reservas, TGA **diaria** desde 2005, RRP, SRF, emisión neta de letras/cupones, subastas desde 1979, recompras, M2 mensual y semanal, repo SOFR/BGCR/TGCR.
- Global: Eurosistema, BoJ, SNB, BoE (balance solo 2006-14; M4 desde 1982), PBoC (hasta 2025-06), M2 de China.
- El clasificador ya usa liquidez neta = WALCL − TGA − RRP (semanal). Propuesto para la fase de modelo: versión diaria, agregado global en USD e impulso a 13/26 semanas.
- Hoy: liquidez **neutral** por poco (score −0,47; ayer escasa, −0,51), liquidez neta 5,86 billones $ (+4,5 % a/a).

## Problemas abiertos (reauditoría del 2026-10-12 por la tarde)
> 13-oct: los MEDIA de esta lista están **cerrados** salvo rtdsm (modelo) y la revisión una a una de `fred_us`/`imf_weo`.

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
0. (13-oct) Fusionar `fase-datos` en `main` cuando el usuario lo apruebe. Huecos que siguen: MTS anterior a 1980, BoE tras 2014, total de activos de la Fed 1969-2002, IPC subyacente de España antes de 2002, PMI, Euribor diario.

1. Corregir los problemas MEDIA de la lista anterior (los scripts de ingesta afectados, sin tocar los datos a mano).
2. Cubrir los huecos accesibles: release 388 de FRED, Z.1 completo, IFS del FMI, EPA anterior a 2002 (PC-Axis del INE) y repo BGCR/TGCR.
3. Volver a ejecutar `imf_weo` cuando salga el WEO de octubre de 2026, guardando antes la versión de abril.
4. Pendientes de la revisión de la Fase 1, que seguirán cuando el usuario dé por cerrada la fase de datos: histéresis de G, I compuesta (que incluya petróleo y PPI), bear frente a bull steepening y capa EUR.
5. Ciclo de mantenimiento: `make data` (ingest → warehouse → regime → audit).
