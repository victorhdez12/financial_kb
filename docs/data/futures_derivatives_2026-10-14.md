# Futuros y derivados — recopilación 2026-10-14

**Agente:** Recopilador de futuros y derivados.
**Objetivo:** expectativas de mercado para el nowcast de régimen: trayectoria de tipos, inflación esperada, pendiente de curvas de materias primas, estructura temporal de la volatilidad y distribuciones implícitas.

**Ya existían (no se duplican):**
- CFTC COT (`cftc_cot`) y CBOE (`cboe`: VIX3M/6M/9D, VVIX, SKEW, OVX, GVZ, COR, put/call).
- Breakevens de FRED (T5YIE, T10YIE, T5YIFR) y GSW de la Fed (`fed_yieldcurve`).
- EXPINF1YR y EXPINF10YR (Cleveland, en `fred_us`).
- Forwards de la curva del BCE (`ecb_yc_*_fwd_*`) y EBP (`fed_ebp`).

## 1. Fuentes integradas (5 fuentes, 213 series)

| source_id | series | rango | frec. | licencia | retardo PIT |
|---|---|---|---|---|---|
| `cboe_vx` | 10 | 2004-03-26 → 2026-10-13 | D | Cboe/CFE, descarga pública, uso personal, sin redistribución | t+1 (liquidación 16:15 ET) |
| `eia_futures` | 12 | 1983-04-04 → **2024-04-05** (congelada) | D | EIA, dominio público | t+1 hábil (histórico) |
| `atl_mpt` | 11 | 2023-03-29 → 2026-10-09 | D | Fed Atlanta: **solo uso personal/educativo**; datos CME con permiso | t+1 hábil |
| `clev_inflexp` | 12 | 1982-01 → 2026-10 | M | Fed Cleveland, uso libre con cita | se publica a mitad del mismo mes: usar fecha + 15 d |
| `mpls_mpd` | 168 | 2006-01 → 2026-09-30 | W | Fed Minneapolis, uso libre con cita | semanal, hasta unos 14 d (último dato 09-30 visto el 10-14) |

Scripts: `src/ingest/{cboe_vx,eia_futures,atl_mpt,clev_inflexp,mpls_mpd}.py`.
- Son idempotentes y cachean el raw en `~/financial_archive/raw/<source_id>/`.
- `cboe_vx` reutiliza los contratos vencidos: la segunda ejecución tarda unos 5 s.

### 1.1 `cboe_vx`: estructura temporal de los futuros del VIX

**Fuente:** un CSV de liquidaciones por contrato.
- CDN nuevo (`.../historical_data/VX/VX_<vencimiento>.csv`), vencimientos de 2013 en adelante.
- Archivo antiguo (`.../archive/volume-and-price/CFE_<M><YY>_VX.csv`), 2004-2014, con huecos posteriores.

**Empalme:**
- Gana el CDN; el archivo antiguo rellena.
- Solo contratos mensuales (se ignoran los semanales).
- `settle = 0` → NaN.
- Antes del 2007-03-26 el VX cotizaba sobre 10×VIX: esos precios se dividen entre 10. Verificado: no hay salto en marzo de 2007.

**Vencimiento:** regla CFE (miércoles 30 días antes del 3.er viernes del mes siguiente), probando ±1-2 días por festivos.
- El contrato n es el n-ésimo con vencimiento posterior a la fecha de negociación.
- El contrato que vence ese día queda excluido.
- 274 contratos, 5.676 días.
- En 2004-2005 no hay contrato para todos los meses (CFE no listaba todos). Por eso `dte_f1` llega a 63 días en esos años.

**Series:**
- `cboe_vx_f1..f4`
- `cboe_vx_dte_f1`
- `cboe_vx_cm30/cm60/cm90`: vencimiento constante por interpolación lineal en días; por debajo del primer vencimiento se usa F1; sin extrapolación.
- `cboe_vx_slope_f2_f1` (puntos)
- `cboe_vx_ratio_cm60_cm30` (%)

**Comprobaciones:**
- 2020-03-16: F1 72,6 y F2 59,2 → pendiente −13,5 (inversión).
- 2008-10-24: pendiente −12,3.
- Mediana de la pendiente: +1,0 (contango normal).
- Proporción de días en backwardation: 49 % en 2008, 29 % en 2020, 1 % en 2021.

### 1.2 `eia_futures`: WTI y gas natural, contratos 1-4

**Fuente:** xls de la EIA `hist_xls/RCLC{1-4}d.xls` y `RNGC{1-4}d.xls`.
- **La EIA dejó de publicar los futuros de NYMEX el 2024-04-05** (licencia). La página de futuros de petróleo ya no tiene enlaces.
- Se integra como histórico; el script la refresca solo una vez al mes por si se reanuda.

**Series:**
- `eia_{wti,ng}_fut_c1..c4`
- `*_spread_c2_c1` (USD; > 0 = contango)
- `*_slope_c4_c1` (%, C4/C1 − 1). Es NaN si C1 ≤ 0.
- Contratos n-ésimos tal como los rueda la EIA en cada vencimiento, sin ajuste.

**Comprobaciones:**
- WTI 2020-04-20: C1 = −37,63 (pendiente NaN).
- 2020-04-21: pendiente +116 % (contango extremo).
- WTI 2022-03-08: −10,4 % (backwardation).

### 1.3 `atl_mpt`: trayectoria esperada de tipos (opciones sobre SOFR 3M)

**Fuente:** `mpt_histdata.xlsx` de la Fed de Atlanta, formato largo por ventana trimestral de referencia.

**Tratamiento:** las ventanas tienen fechas fijas, así que se construye un horizonte constante por fecha.
- Interpolación lineal en días hasta el inicio de la ventana, sin extrapolación.
- `sofr_mean_3m` falta 53 días porque la primera ventana empieza a más de 91 días.

**Series:**
- `atl_mpt_sofr_mean_{3,6,12,24}m` (%)
- `atl_mpt_chg_{6,12}m`: media menos el punto medio del rango objetivo del FOMC, en pp; < 0 = recortes descontados.
- `atl_mpt_prob_{cut,hike}_{6,12}m`
- `atl_mpt_iqr_12m`

**Comprobaciones:**
- 2024-09-03: −2,11 pp a 12 m y probabilidad de recorte del 97 % (ciclo de recortes).
- 2023-10-02: probabilidad de subida a 6 m del 52 %.

**Limitación:** la historia empieza en 2023-03. Sirve para el nowcast actual, no para entrenar reglas.

### 1.4 `clev_inflexp`: curva de inflación esperada (modelo de la Fed de Cleveland)

**Fuente:** `inflation-expectations.xlsx`; el modelo combina bonos, swaps de inflación y encuestas.

**Series:**
- Inflación esperada a 2, 3, 5, 7, 20 y 30 años. La de 1 y 10 años ya está en `fred_us`; coincide: 2026-09 = 2,57 en FRED.
- `clev_expinf_5y5y`: derivada como (10·E10 − 5·E5)/5.
- Primas de riesgo real y de inflación a 10 años.
- Tipos reales a 1 m, 1 a y 10 a.
- Las hojas de expectativas y de tipos reales vienen en fracción: se pasan a %.

### 1.5 `mpls_mpd`: distribuciones implícitas en opciones (Fed de Minneapolis)

**Fuente:** `mpd_stats.csv`, semanal.

**Mercados (21):**
- S&P 500 a 6 y 12 m.
- **Futuros del Treasury a 10 y 5 años** (volatilidad implícita de tipos: sustituto parcial del MOVE).
- **EUR, GBP y JPY** (volatilidad implícita de divisas).
- Oro, plata, WTI (hasta 2020-04), maíz, trigo y soja.
- REIT (IYR), BAC y Citi.
- Inflación IPC por caps/floors a 1, 2 y 5 años (terminan en 2018, 2019 y 2025-05).
- LIBOR 3m a 3 y 5 años vista (termina en 2021).

**Estadísticos por mercado:** `mu, sd, skew, p10, p50, p90, prdec, princ`, sobre log-rendimientos en fracción. En inflación y LIBOR son niveles en fracción.
- Se descarta la única fila con un horizonte distinto del modal (sp12m, 2013-03-07).

**Comprobación:** la desviación típica a 6 m del S&P sube de 0,105 (2020-02-19) a 0,382 (2020-03-18).

## 2. Evaluación de futuros continuos (ES, NQ, ZN, ZB, 6E, GC, CL…)

| opción | estado (2026-10-14) | historia/calidad | roll | términos |
|---|---|---|---|---|
| Stooq (`cl.f`, `es.f`…) | **No accesible**: reto JavaScript de prueba de trabajo antes de cualquier CSV | front month sin ajustar | desconocido | uso personal; no se automatiza para no saltarse el bloqueo |
| Yahoo Finance (`CL=F`, `ES=F`…), yfinance | **HTTP 429** en query1/query2 desde esta IP | ~2000+, solo el contrato cercano, sin ajuste por roll; huecos y errores conocidos | salta al vencimiento, sin ajuste | prohíbe el uso automatizado/comercial; no oficial |
| Investing.com | 403 | — | — | prohíbe el scraping |
| Nasdaq Data Link CHRIS (Wiki) | descontinuado | — | — | — |

**Conclusión:** no hay fuente gratuita y estable. Queda como **hueco**; no se integra nada como `quality=unofficial`.
- Alternativas gratuitas ya presentes: precios al contado (FRED: DCOILWTICO, oro, EURUSD) y rentabilidades de índices.
- El posicionamiento sale de CFTC.

## 3. Huecos

### Gratuitos no disponibles o discontinuados
- **WTI y gas natural por vencimiento desde 2024-04-05**: la EIA dejó de publicarlos. No hay sustituto oficial gratuito; solo el contado sigue en FRED.
- **Curvas de cobre, oro y cereales por vencimiento**: CME solo muestra las liquidaciones del día (web con protección anti-bots y términos restrictivos). Las del LME son de pago.
  - Las distribuciones de oro, plata y cereales de `mpls_mpd` cubren en parte la información implícita, no el roll yield.
- **Volatilidad de tipos y divisas de CBOE**: VXTYN, SRVIX y EVZ dan *Access Denied* en el CDN.
  - FRED tiene `EVZCLS` (2007-11 → 2025-03, discontinuada): se puede añadir a `fred_extended`, que no es fuente de este agente.
  - VXEFA, VXEWZ, VXFXI, VXSLV y VXGDX sí siguen en el CDN de CBOE: ampliación opcional de `cboe` por su responsable.
- **€STR a plazo / OIS de la zona euro**: el BCE no publica OIS forwards (ya están los forwards de la curva de deuda). Hueco.
- **SOFR a plazo (CME Term SOFR)**: licencia de CME. El MPT cubre la trayectoria esperada desde 2023.
- **Futuros de fondos federales antes de 2023** (para la trayectoria implícita histórica): sin fuente gratuita.
  - Aproximación existente: forwards GSW y EFFR/THREEFF de FRED.

### De pago (coste aproximado, a decidir por el usuario)

| producto | coste aprox. | qué aportaría |
|---|---|---|
| **Databento** (CME Globex, OHLCV diario por contrato) | pago por uso; decenas a pocos cientos de USD por el histórico diario 2010+ | todas las curvas CME (CL, NG, HG, GC, ZC, ZN, ZB, ES, 6E, SR3, ZQ) por contrato → roll yield, futuros continuos con empalme propio, fondos federales implícitos |
| CME DataMine (EOD/settlements) | de cientos a varios miles de USD por producto e historia | lo mismo con historia larga oficial (desde los años 80-90) |
| Norgate Data (futuros) | ~USD 300-600/año | futuros continuos ajustados y por contrato (~100 mercados), largo plazo; uso personal |
| ICE: índice **MOVE** | licencia ICE / terminal (miles de USD/año) | volatilidad implícita de Treasuries (ahora sustituida por `mpls_mpd_ust10y_sd`, solo desde 2014) |
| Bloomberg / Refinitiv (LSEG) | ~USD 25-30 k/año / ~15-25 k/año | swaps de inflación (ZC CPI, €HICPxT), OIS €STR/SOFR, volatilidad swaption, superficies de volatilidad FX, LME |
| LME (cobre por vencimiento) | licencia de datos, miles de GBP/año | pendiente de la curva del cobre (crecimiento global) |

## 4. Cambios propuestos (no aplicados)

**`Makefile`:**
- `INGEST` += `cboe_vx eia_futures atl_mpt clev_inflexp mpls_mpd`
- `INGEST_DAILY` += `cboe_vx atl_mpt`
- `mpls_mpd` (semanal) y `clev_inflexp` (mensual) bastan con `INGEST` en `semanal`.
- `eia_futures` está congelada: solo `INGEST`.

**`src/warehouse/build.py` → `PIT_RULES`:** **ninguna regla nueva obligatoria**.
- Todas las series son observadas en su fecha (son expectativas de mercado, no previsiones fechadas en el objetivo).
- Por eso deben quedar como `observed`, aunque contengan "prob" o "exp".
- Si alguna vez se añade una regla genérica sobre esas palabras, excluirlas explícitamente.

**Retardo de publicación** (para el *as-of* del clasificador o una futura tabla de retardos):

| fuente | retardo |
|---|---|
| `clev_inflexp` | fecha + 15 d (la fecha es el inicio del mes; se publica a mitad de ese mes) — **la más importante: sin desfase hay ~2 semanas de look-ahead** |
| `mpls_mpd` | fecha + 14 d |
| `cboe_vx`, `atl_mpt`, `eia_futures` | fecha + 1 d hábil |

**Checklist del auditor:** comprobado localmente.
- Columnas y tipos según el contrato.
- Catálogo = ficheros.
- Sin duplicados, NaN, fechas futuras ni colisiones de `series_id` con otras fuentes.
- Pendiente de pasar `src.audit.run` antes de cargar en la base de datos.
