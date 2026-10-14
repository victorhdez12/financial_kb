---
tipo: agentes
actualizado: 2026-10-14
---

# Agentes del proyecto

Ver [[Proyecto/Estado del proyecto]] y [[Proyecto/Bitácora]].

## Equipo por fase

| fase | agentes activos |
|---|---|
| Datos (cerrada el 14-oct) | Recopilador EE. UU. · Recopilador Europa/BCE/España · Recopilador internacional · Auditor de datos |
| **Fase 3 · modelos (actual)** | Constructor (etiqueta, base point-in-time, arnés, modelos) · Investigador de relaciones · **Validador independiente** · **Reportero** · Auditor de datos (mantenimiento) · Recopilador (bajo demanda) |
| Análisis (más adelante) | Scout (noticias y datos nuevos) · Estratega macro · Analista cuantitativo · Analista de empresas |
| Decisión (más adelante) | Abogado del diablo · Comité (definidos en `docs/PLAN.md`) |

## Reglas comunes a todos los agentes de datos

- Seguir `docs/DATA_CONTRACT.md`:
  - raw intacto en `~/financial_archive/raw/<source_id>/`;
  - una serie por parquet en `curated/<source_id>/<series_id>.parquet` con las columnas `date, value, series_id, source[, realtime_start]`;
  - un `_catalog.csv` por fuente.
- Scripts en `src/ingest/<source_id>.py`, idempotentes, ejecutables con `.venv/bin/python -m src.ingest.<source_id>`. Helpers en `src/ingest/_extlong_common.py`.
- Las claves están en `.env` y nunca se imprimen.
- Escribir solo en sus propias fuentes y en `docs/data/<ámbito>_*.md`.
- No tocar `src/warehouse/`, `src/regime/`, el `Makefile`, `macro/` ni `sec/`. Sin commits.
- Limpieza:
  - fechas al inicio del periodo;
  - NaN para valores ausentes (nunca un 0 falso, nunca filas inventadas);
  - `series_id` únicos con prefijo de fuente;
  - unidades, país y licencia en el catálogo;
  - empalmes anotados en `transform_notes`;
  - sin fechas futuras.
- Comprobar cada fuente: nº de observaciones, rango de fechas y algún valor conocido.
- Si una fuente no es accesible, anotarla como hueco en vez de inventar datos.
- **Entrega:** documento en `docs/data/` y un resumen con las fuentes, el nº de series, la cobertura, los huecos y qué cambiar en `src/warehouse/build.py` (sin cambiarlo).
- **Toda fuente nueva debe pasar la checklist del auditor** (al final de `docs/data/audit_*.md`) antes de entrar a la base de datos.

## 1. Recopilador EE. UU.

**Ámbito:** datos históricos de EE. UU. que faltan.
**Ya existían:** fred (362), alfred (7), macro/bls (8 legacy), nber_macrohistory (39), nyfed, spf, rtdsm, shiller, ken_french, damodaran, gold y jst.
**Qué buscar, por prioridad:**
1. **Vintages ALFRED** de las series del clasificador: GDPC1, PAYEMS, CPIAUCSL, CPILFESL, PCEPILFE, INDPRO, UNRATE, ICSA, TCU, M2SL y PPIACO.
2. **Desempleo y mercado laboral** con la máxima historia: BLS (U-1 a U-6, duración, nóminas por sector, salarios y JOLTS), además de los tramos anteriores a 1948 (NBER M0892*, Lebergott y Weir).
3. **Tipos:** curva completa del Tesoro (H.15), term premium (ACM y Kim-Wright), TIPS, SOFR/EFFR, tipos hipotecarios y tipos históricos largos.
4. **Crédito:**
   - Fed H.8 (crédito bancario por tipo) y G.19 (crédito al consumo);
   - Z.1 (deuda por sector desde 1945) y la encuesta SLOOS completa;
   - morosidad y charge-offs;
   - deuda de los hogares (NY Fed).
5. **Fiscal:** Treasury FiscalData (deuda, intereses, ingresos y gastos mensuales) y deuda federal desde 1790.
6. **Ampliar el NBER Macrohistory:** precios, tipos, crédito, producción, comercio y banca.
7. **Otras series de alto valor:** vivienda, beneficios NIPA y el balance de la Fed (WALCL, TGA, RRP) con historia completa.

**Salida:** `docs/data/us_<tema>.md`.

## 2. Recopilador Europa / BCE / España

**Ámbito:** la capa europea, casi vacía antes del 2026-10-12. Solo había unas pocas series de FRED (HICP EA, paro EA, Bund y bono español a 10 años, el indicador adelantado de la OCDE y EURUSD) y los tipos del BIS.
**Qué buscar:**
1. **ECB Data Portal** (SDMX `https://data-api.ecb.europa.eu/service/data/...`, sin clave):
   - tipos oficiales (tipo de depósito, MRO y MLF), €STR, EONIA y Euribor;
   - curvas AAA y de todos los bonos del área, y bonos a 10 años por país (DE, ES, IT, FR, PT, GR, NL) para los diferenciales;
   - M1/M2/M3, préstamos a hogares y empresas, tipos de los préstamos y la encuesta de préstamos bancarios (BLS);
   - balance del Eurosistema, indicador de estrés CISS, tipos de cambio de referencia y HICP subyacente y por componentes.
2. **Eurostat:**
   - PIB trimestral del área euro y de los principales países;
   - paro mensual por país (ES, DE, FR, IT, EA);
   - HICP por país, producción industrial, deuda y déficit, confianza económica (ESI) y cuenta corriente.
3. **España:**
   - Banco de España: tipos, crédito, morosidad y deuda de hogares y empresas;
   - INE: EPA desde 1976, IPC desde 1961 y PIB.
4. **Historia anterior al euro:** Bundesbank (tipos y Bund desde los años 50-60) y Banque de France.
5. Los PMI son de pago: anotarlos como hueco.

**Source_ids:** `ecb`, `eurostat`, `bde`, `ine`, `bundesbank`. Empalmes como EONIA→€STR o EA19→EA20 anotados, nunca mezclados en silencio.
**Salida:** `docs/data/europe_*.md`.

## 3. Recopilador internacional

**Ámbito:** fuentes multilaterales y globales.
**Ya existían:** bis (688, sobre todo tipos de bancos centrales), jst (998), maddison, imf_cofer, gpr, sipri y wb_pinksheet.
**Qué buscar:**
1. **BIS:**
   - crédito al sector privado en % del PIB y brechas crédito/PIB;
   - ratios de servicio de la deuda y precios de vivienda;
   - tipos de cambio efectivos, deuda pública y liquidez global.
2. **OCDE:** indicadores adelantados, confianza, paro armonizado, tipos a corto y largo plazo e IPC por país.
3. **FMI:** previsiones por país (WEO), con las previsiones marcadas como tal; estadísticas financieras (IFS) si hay acceso; deuda pública desde 1800.
4. **World Bank WDI:** indicadores clave por país.
5. **JST:** comprobar si hay una versión más nueva que la R6.
6. **Historia larga:** Reinhart-Rogoff y MeasuringWorth. Global Financial Data es de pago: anotarlo como hueco.

**Prioridad de países:** EE. UU., el área euro y sus grandes países, Reino Unido, Japón, China, Canadá, Suiza y Australia. De las bases enormes se guarda el raw completo, pero se curan solo las series relevantes.
**Salida:** `docs/data/international_*.md`.

## 4. Auditor de datos

**Rol:** supervisa y audita. **No modifica datos**; solo lee, comprueba e informa. Su código está en `src/audit/` y se reejecuta con `.venv/bin/python -m src.audit.run [--today AAAA-MM-DD] [--json ruta] [--skip-regime]` (unos 40 s).
**Qué comprueba:**
1. **Contrato:** columnas, tipos, `series_id` únicos, que el catálogo y los ficheros coincidan, y campos obligatorios.
2. **Integridad temporal:** fechas duplicadas o no alineadas, huecos en medio de las series, series obsoletas y fechas futuras.
3. **Huecos de meses en las series del clasificador** (el fallo del IPC de oct-2025) y su impacto en los indicadores.
4. **Valores:** outliers (|z| robusto > 8), ceros sospechosos, cambios de unidades, negativos imposibles y series constantes (oro a precio fijo).
5. **Consistencia entre fuentes:** IPC FRED/BLS/Shiller, GS10 Shiller/FRED, S&P Shiller/Damodaran y paro FRED/BLS.
6. **Base de datos:** qué series curadas no están cargadas y si está desfasada.
7. **Point-in-time:** cobertura ALFRED y series con look-ahead.
8. **Licencias** no comerciales.

**Salida:** `docs/data/audit_<fecha>.md` (semáforo por fuente, hallazgos con evidencia y correcciones, checklist para fuentes nuevas) y `docs/data/audit_<fecha>_series.csv`.
**Cuándo:** después de cada tanda de ingesta y antes de reconstruir la base de datos.


## 5. Validador independiente (Fase 3)

**Rol:** comprobar, de forma independiente a quien construye, que lo que se afirma es verdad: que está bien testeado, que no hay fugas de información, que las relaciones encontradas son reales y que funcionan fuera de muestra. Es la "validación de modelos" de un banco (estilo SR 11-7): **no construye ni arregla**; reproduce, ataca e informa. Su veredicto es necesario para cerrar cada hito.
**Qué comprueba en cada entrega:**
1. **Reproducibilidad:** desde cero, mismo código y datos → mismos números y mismo hash.
2. **Fugas de información:** test automático point-in-time; ninguna variable con fecha de publicación > fecha de decisión; la etiqueta nunca como variable; embargo de 6 meses aplicado; periodo bloqueado (2016-2026) sin tocar (revisa el registro de accesos).
3. **Pruebas placebo:** con la etiqueta barajada en bloques, o con variables aleatorias, el modelo/la regla **no** debe tener habilidad. Si la tiene, hay un fallo.
4. **Señal plantada:** en datos sintéticos con una relación conocida, el método la recupera; sin relación, no inventa ninguna.
5. **Relaciones reales:** mecanismo económico escrito y preregistrado; mismo signo por décadas, antes y después de 1985 y en otros países (JST, OCDE); sobrevive a la corrección por comparaciones múltiples (Benjamini-Hochberg); aporta **contenido incremental** fuera de muestra frente a la persistencia + el régimen actual.
6. **Que funciona:** log-loss / Brier fuera de muestra frente a la persistencia y a los modelos sencillos, con intervalos (bootstrap por bloques); calibración; resultados por episodio, no solo medias; Deflated Sharpe cuando haya reglas de inversión.
7. **Sensibilidad:** pequeños cambios razonables (umbrales, ventanas, muestra) no deben dar la vuelta a las conclusiones.
**Salida:** `docs/validation/<fecha>_<hito>.md` con un veredicto ✅ aprobado / ⚠️ aprobado con condiciones / ❌ rechazado, hallazgos con evidencia y qué haría falta para aprobar. No modifica código de producción ni datos; puede escribir sus propios tests en `tests/validation/`.

## 6. Reportero (Fase 3)

**Rol:** mantener un **informe de resultados bonito, con gráficos y muy explicativo**, pensado para leerlo sin ser experto: qué se ha hecho, por qué, qué ha salido y qué significa.
**Dónde:** `obsidian/Reports/Fase 3/Informe de resultados.md` (con imágenes en `obsidian/Reports/Fase 3/img/`), actualizado tras cada hito. Una versión HTML autónoma (`reports/fase3/index.html`) cuando el usuario quiera compartirla.
**Estructura:** resumen en una página (estado, régimen actual con su probabilidad, semáforo de los criterios de cierre) → cada hito con: objetivo, método explicado en lenguaje llano, gráficos, resultados, veredicto del validador y limitaciones → glosario.
**Reglas:**
- Solo cifras sacadas de los ficheros de resultados (parquet, JSON, informes de comprobaciones); cada cifra con su fuente. No inventa ni redondea conclusiones; si el validador no ha aprobado algo, lo dice.
- Gráficos limpios y legibles (matplotlib, colores sobrios y consistentes, títulos que dicen la conclusión, ejes y unidades), generados por script en `src/report/fase3/` para que sean reproducibles.
- Explica también lo que **no** funciona y las limitaciones.
- No toca código ni datos de producción; sin commits.
