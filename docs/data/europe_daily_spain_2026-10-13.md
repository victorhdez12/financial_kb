# Europa diaria y España: ampliación de datos (2026-10-13)

Agente: "Europa y España diario". Solo se han añadido series (nada existente se ha roto) y se han creado dos fuentes nuevas (`ifo`, `zew`). Todos los scripts se han ejecutado de punta a punta sin errores: `python -m src.ingest.{ecb,eurostat,ine,bundesbank,oecd,ifo,zew}`. No se ha tocado `src/warehouse`, `src/regime`, `Makefile`, ni se ha hecho commit.

## Resumen por fuente

| Fuente | Series totales (catálogo) | Series nuevas | Contenido nuevo | Licencia |
|---|---|---|---|---|
| `ecb` | 134 | 18 | Forwards instantáneos diarios 1/2/5/10a (curvas AAA y todos los bonos, desde 2004-09), €STR compuesto 1s/1m/3m/6m/12m (diario), rendimiento benchmark EA 2a y 10a (mensual), diferencial curva "todos" menos AAA a 10a (pb) y forward 1a-1a derivado | Libre con atribución (BCE) |
| `bundesbank` | 25 | 6 | Rendimiento Bund cupón cero Svensson DIARIO 1/2/5/10/30a (desde 1972) y Umlaufsrendite diaria | Libre con atribución |
| `eurostat` | 186 | 24+ (empleo, vacantes, confianza) | Empleados contabilidad nacional (miles, y/y), empleados EPA, tasa de empleo 20-64, tasa y número de vacantes (trimestral; EA21, DE, ES, FR, IT, NL, PT, GR, IE, BE, AT), ESI para GR/IE/BE/AT y confianza industrial/servicios EA, ES, DE, FR, IT | CC BY 4.0 |
| `ine` | 79 | 21 | IPV: segunda mano, nueva y/y, q/q; compraventa de viviendas (ETDP, mensual desde 2007: total, nueva, usada, protegida); hipotecas sobre viviendas (H) número e importe (base nueva 2003+ y antigua 1994-2003); Índice de Producción Industrial (SCA, calendario, bruto; índice, y/y, m/m) | INE: reutilización libre con atribución |
| `oecd` | 339 | 30 | Arreglo del IPC parado + nuevas áreas (ver abajo) | CC BY 4.0 |
| `ifo` (nueva) | 32 | 32 | Clima empresarial Alemania (índice 2015=100 y saldos; situación y expectativas), incertidumbre, semáforo, sectores (industria y comercio, manufacturas, servicios, comercio mayorista/minorista, construcción), 1991/2005 a 2026-09 | Descarga pública de ifo.de, citar fuente; sin términos de redistribución explícitos (uso de investigación) |
| `zew` (nueva) | 2 | 2 | Sentimiento económico y situación actual de Alemania (saldos), 1991-12 a 2026-09 | Descarga pública de zew.de; citar |

Afiliación a la Seguridad Social: ya existía `bde_es_ss_affiliates_m` (BdE, 1982-01 a 2026-09, fin de mes). No se ha duplicado.

## Arreglo del IPC de la OCDE (punto 6)

Causa: tras el cambio a ECOICOP-2 de 2026 la OCDE ha movido a un dataflow nuevo, `DSD_PRICES_COICOP2018@DF_PRICES_C2018_ALL` (misma estructura de 8 dimensiones), los países de la zona euro y otros. El dataflow antiguo `DF_PRICES_ALL` quedó congelado en 2025-12 para ESP, FRA, ITA, NLD, SWE, CHE, TUR, EA20 (también JPN 2021-06, MEX 2024-07, ZAF 2025-01); DEU, USA, GBR, etc. siguen en el antiguo. Además `EA20` ya no se publica: el agregado vigente es `EA` (composición cambiante).

Corrección en `src/ingest/oecd.py` (nueva consulta `cpi2`): para cada serie se conserva la histórica del dataflow antiguo y se empalma después de su último mes con el nuevo (misma base 2015=100; en el solape el factor de reescalado es ≈1,0000, p. ej. ESP 128,4016 vs 128,4012 en 2025-12). Las notas de empalme van en `transform_notes`. Resultado: `oecd_cpi_esp_*`, `fra`, `ita`, `nld`, `swe`, `che`, `tur`... llegan a 2026-08/09; nuevas series `oecd_cpi_ea_*`, `oecd_cpicore_ea_*` (a 2026-09) y PRT, GRC, BEL, AUT, IRL, FIN, EU27_2020. `oecd_cpi_ea20_*` se mantiene (termina en 2025-12; usar `ea`). Los 309 `series_id` anteriores siguen presentes (ahora 339). Valor: IPC OCDE España interanual 2026-08 = 4,28 %.

## Decisiones y huecos

1. **Rendimientos soberanos diarios por país: hueco (salvo Alemania).** El BCE no publica bonos soberanos diarios por país: solo las curvas de la zona euro (AAA y todos los bonos) y mensuales (`IRS` convergencia, ya en `ecb_gov10y_*_m`, y benchmark `FM`). No hay serie diaria gratuita y estable para ES, IT, FR, PT, GR, NL, BE, AT, IE: el Banco de España solo publica mensual en el paquete be.zip (sin series diarias), Stooq exige verificación JavaScript y su licencia no permite redistribuir, y los datos de proveedores (Refinitiv, Bloomberg) son de pago. Proxy diario: `ecb_yc_all_minus_aaa_10y_d` (194 pb el 2012-07-24) y los forwards. Alemania sí: `bundesbank_bund_zero_10y_d`.
2. **Valor conocido (bono español a 10 años ≈ 7,6 % el 24-jul-2012):** no se puede comprobar en diario (7,6 % fue el máximo intradía). Sí es coherente el mensual: `ecb_gov10y_es_m` = `bde_es_gov10y_secondary_m` = 6,79 % de media en julio 2012. Bund 10a Svensson 2012-07-24 = 1,36 %.
3. **Euribor diario: hueco por licencia.** El histórico diario oficial es de EMMI (de pago). Gratis: Euribor mensual del BCE (`ecb_euribor_{1m,3m,6m,12m}_m`, ya existían), Euribor 12m/MIBOR mensual del BdE (`bde_es_mibor_1y_m`) y como proxy diario el €STR (`ecb_estr_d`) y las curvas AAA 3M/1Y/2Y.
4. **OIS/swaps: hueco por licencia.** No hay OIS a plazo gratuitos. Se añade lo oficial más cercano: €STR compuesto retrospectivo del BCE a 1s/1m/3m/6m/12m (realizado, no a plazo de mercado) y forwards de la curva de bonos del BCE (no son swaps). Series de €STR compuesto empiezan 2022-09 (1w desde 2019-10).
5. **Empleo zona euro:** trimestral (contabilidad nacional desde 1995; EPA desde 2005 o 2009 según país). Eurostat no ofrece nivel de empleo mensual (solo paro mensual, ya existente). FR, PT y GR no tienen empleo "SCA": se usa "SA" (anotado en el nombre). Vacantes: `job_vacancies` de EA21 e IT no están disponibles; `job_vacancy_rate_ea` llega a 2025-Q4 (publicación con retraso).
6. **Vivienda España:** IPV (trimestral desde 2007): el y/y es negativo en 2012 (−12,6 %, −14,4 %, −15,2 %, −12,8 % por trimestres). Corregidas las unidades del catálogo: el índice del IPV es base 2025=100, no 2015. ETDP y H son mensuales hasta 2026-07. Hipotecas: dos bases (antigua 1994-2003 y nueva 2003+); se dejan separadas, sin empalmar.
7. **Afiliación:** 22,36 millones en 2026-09 y 16,09 millones en el mínimo de 2013-02 (coherente con 21-22 millones en 2025-26).
8. **IPI España:** nuevo en `ine` (1992+ SCA y calendario; 1975+ bruto). Ya existía `bde_es_ip_m`.
9. **ifo:** disponible 2005+ (general) y 1991+ (sectores) en la descarga pública. El histórico occidental 1960-1990 es otro Excel (no recogido) y las series anteriores solo se obtienen por correo a ifo. El nombre del fichero lleva el mes (`gsk-e-YYYYMM.xlsx`), el script prueba el mes actual y retrocede hasta 6 meses.
10. **ZEW:** solo es gratuito el indicador de Alemania (sentimiento y situación). El de la zona euro, por países y sectorial, es de pago o bajo licencia: hueco. Comprobación: máximo 89,6 en 2000-01 y mínimo −63,9 en 2008-07 (valores conocidos).
11. **ESI:** ya existía en `eurostat` (`eurostat_esi_*`); se ha ampliado a GR, IE, BE, AT y se han añadido confianza industrial y de servicios para EA, ES, DE, FR, IT.
12. **Inverco: hueco.** No hay CSV ni Excel: solo PDF por mes (`files/estadisticas/fondos_inversion/AAMM_Mes-AAAA/...pdf`, p. ej. patrimonio y suscripciones/reembolsos por categoría). El PDF de patrimonio incluye cierres anuales 1991-2025 y los últimos 9 meses, pero el texto sale con columnas pegadas (no separable con fiabilidad) y la historia mensual exigiría bajar y parsear cada PDF mensual. Pendiente para otra tanda (necesita un parser de PDF en `.venv`; ahora solo `pypdf` en el Python del sistema). La nota de prensa mensual se puede usar para valores recientes (patrimonio ≈ 478.000 M EUR a 2026-09).

## Qué cambiar en `src/warehouse/build.py` (sin cambiarlo)

- Incluir las fuentes nuevas `ifo` y `zew` en la lista de fuentes que carga (se han creado `curated/ifo/` y `curated/zew/` con `_catalog.csv`).
- Recargar `ecb`, `eurostat`, `ine`, `bundesbank` y `oecd` (hay series nuevas; ninguna eliminada).
- Frecuencia diaria: ahora hay series `D` de Bund y forwards del BCE, comprobar que la carga admite frecuencia D en esas fuentes (ya admitía `ecb_*_d`).
- Para el clasificador: `oecd_cpi_esp_yoy` y `oecd_cpi_ea_yoy` sustituyen a `oecd_cpi_ea20_yoy` (parado en 2025-12).
- Sugerencia de mapeo: `eurostat_job_vacancy_rate_*` y `eurostat_emp_*` en `employment`; `ine_hpt_*`, `ine_etdp_*`, `ine_ipv_*` en `housing`/`credit`.

## Checklist del auditor (comprobado)

`series_id` únicos con prefijo de fuente en las 7 fuentes; sin fechas futuras; NaN en vez de ceros falsos (índices con `positive=True`); raw intacto en `~/financial_archive/raw/<fuente>/`; licencia y empalmes anotados; ejecución idempotente.
