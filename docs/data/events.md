# Capa de eventos e indicadores geopolíticos/crisis

Generado el 2026-10-07. Todos los ficheros siguen `docs/DATA_CONTRACT.md` (sección Eventos):
`event_id, name, type, country, start_date, end_date, severity, source, url, notes`
(`start_date`/`end_date` = `date32`; `severity` = **string** en todos los ficheros para que el
`UNION` en DuckDB no choque de tipos; cuando es numérico, es un número parseable o `clave=valor`).
`country` = ISO3 (varios separados por `;`), `WLD` = global, `EMU` = zona euro.

**Extensión del enum `type`:** se añade `inflation_crisis` (cronología Reinhart-Rogoff, pedido
explícitamente). El resto de tipos son los del contrato.

## Scripts (idempotentes; descargas validadas: magic bytes, no-HTML, tamaño mínimo)

| script | salida | filas |
|---|---|---|
| `python -m src.ingest.events_gpr` | `curated/gpr/*.parquet` + `_catalog.csv` | 99 series (96 M, 3 D) |
| `python -m src.ingest.events_wars` | `events/wars.parquet` | 768 (COW 592, UCDP 176) |
| `python -m src.ingest.events_financial_crises` | `events/financial_crises.parquet` | 2.228 (LV 541, RR 1.687) |
| `python -m src.ingest.events_nber` | `events/us_recessions.parquet` | 34 recesiones (1857-2020) |
| `python -m src.ingest.events_curated [--check-urls]` | `events/curated_market_events.parquet` | 151 (44 `credit_event`) |

Helpers comunes: `src/ingest/_events_common.py` (descarga validada, `write_events` con
esquema pyarrow fijo y comprobación de tipos/ids duplicados, mapeo nombre→ISO3 sin fuzzy).
Originales intactos en `$FIN_DATA_ROOT/raw/{gpr,wars,financial_crises,nber}/`.
`events/jst_crises.parquet` lo genera otro agente (JST) — no se toca aquí.

## Fuentes, cobertura y licencias

### 1. Geopolitical Risk Index (Caldara-Iacoviello) → `curated/gpr/`
- URL: <https://www.matteoiacoviello.com/gpr.htm> (`data_gpr_export.xls`, `data_gpr_daily_recent.xls`).
- Series: `gpr` (1985-, 10 periódicos, 1985-2019=100), `gpr_threats`, `gpr_acts`;
  `gpr_hist` (**1900-01 → 2026-09**, 3 periódicos, 1900-2019=100), `gpr_hist_threats/acts`,
  `gpr_share`, `gpr_hist_share`; diario `gpr_daily`, `gpr_daily_acts`, `gpr_daily_threats`
  (1985-01-01 → 2026-10-05); **por país** `gpr_country_<iso3>` (44 países, 1985-, % de artículos)
  y `gpr_hist_country_<iso3>` (1900-). Categoría `geopolitics`.
- Picos: GPRH 484 (sep-1939), 473 (jun-1944), 472 (ago-1914); GPR reciente 513 (oct-2001),
  379 (ene-1991), 359 (mar-2003) y **330 en mar-2026** (guerra de Irán; máximo desde 2003).
- Licencia: libre para investigación citando Caldara & Iacoviello (2022), AER 112(4).

### 2. Guerras → `events/wars.parquet` (type=war, severity = muertes en batalla)
- **Correlates of War v4** (<https://correlatesofwar.org/data-sets/cow-war/>): inter-state v4.0
  (1823-2003), intra-state v4.1 (1818-2014), extra-state v4.0 (1816-2007). Una fila por guerra;
  severity = suma de muertes de participantes (inter) o lado A+B (intra/extra). Participantes en `notes`.
  27 guerras intra-estado de actores no estatales quedan con `country` vacío.
- **UCDP/PRIO ACD v25.1** (1946-2024) + **UCDP Battle-Related Deaths v25.1** (1989-2024)
  (<https://ucdp.uu.se/downloads/>). Una fila por episodio de conflicto que alcanzó intensidad 2
  (≥1.000 muertes/año); severity = muertes "best" sumadas (antes de 1989 vacío). Episodios sin
  `end_date` = en curso a fin de 2024 (p. ej. Rusia-Ucrania 2022: 242.368 muertes 2022-24).
- Solape COW/UCDP 1946-2007: se mantienen ambos; para la era moderna filtrar `source='ucdp_prio'`.
- Licencias: COW uso académico libre con cita; UCDP CC BY 4.0.
- No disponible: COW intra-state v5.1 (URL 404), COW non-state (no incluido).

### 3. Crisis financieras → `events/financial_crises.parquet`
- **Laeven & Valencia (2018)**, IMF WP/18/206, 1970-2017: 151 crisis bancarias sistémicas con
  fin, pérdida de output, coste fiscal, NPL pico (en `severity`/`notes`), + años de crisis
  cambiaria (239), crisis de deuda soberana y reestructuraciones (151). El CDN del FMI devuelve
  403 a scripts → se descarga **el mismo zip oficial** desde el snapshot de Internet Archive
  (2024-07-11). La actualización 2020 (CEPR DP14569) no se pudo descargar (403).
- **Reinhart-Rogoff "Global Crises Data by Country"** (HBS Behavioral Finance & Financial
  Stability, <https://www.hbs.edu/behavioral-finance-and-financial-stability/data/Pages/global.aspx>),
  70 países, **1800-2016**: banca (303 episodios, flag `systemic`), divisa (635), inflación ≥20 %
  (485, con pico de inflación), impago doméstico y externo (264). Dummies anuales colapsadas en
  episodios de años consecutivos. carmenreinhart.com es una SPA sin enlaces directos; se usa el
  espejo HBS (mismos datos de "This Time Is Different").
- Licencia: uso de investigación con cita (FMI / Reinhart-Rogoff).

### 4. Recesiones EE. UU. → `events/us_recessions.parquet`
- NBER (<https://data.nber.org/data/cycles/business_cycle_dates.json>): 34 recesiones pico→valle,
  1857-06 → 2020-02/04; severity = meses de contracción; `notes` incluye la expansión previa.
  Recordatorio (PLAN.md): el NBER anuncia con 6-21 meses de retraso → no usar en tiempo real.
  Dominio público.

### 5. Lista curada → `events/curated_market_events.parquet`
151 eventos 1819-2026: pánicos del XIX, 1907, 1929, Gran Depresión, devaluación 1933-34, WWI/II,
Bretton Woods 1944/1971, shocks del petróleo 1973/1979/1990/2014/2020/**2026 (Ormuz)**, Volcker,
1987, S&L, ERM, Tequila, Asia, Rusia/LTCM, dot-com, 9/11, GFC (BNP, Northern Rock, Bear, GSEs,
Lehman, Reserve Primary), euro, taper tantrum, China 2015, Volmageddon, repo 2019, COVID, 2022,
LDI, SVB/CS/First Republic, Ucrania, Gaza, Mar Rojo, yen carry 2024, DeepSeek, Liberation Day
2025, Twelve-Day War, Tricolor/First Brands/Zions 2025, Venezuela 2026, Blue Owl 2026 y guerra de
Irán 2026. Cada evento tiene URL (Wikipedia, Fed, o prensa para 2025-26) — **las 144 URLs únicas
se comprobaron con HTTP 200** (`--check-urls`). Cifras de 2024-2026 contrastadas con FRED local
(p. ej. WTI 114,58 $ abr-2026, VIX 52,33 abr-2025). Licencia: lista propia; textos de Wikipedia
CC BY-SA (solo hechos + enlace).

## Indicadores de fractura de crédito

**Definición.** `type=credit_event` = rotura de un canal de crédito o financiación: run sobre
financiación mayorista/depósitos no asegurados (Continental 1984, Northern Rock, SVB), congelación
de un mercado monetario (Penn Central/CP 1970, BNP ago-2007, Reserve Primary 2008, repo sep-2019,
"dash for cash" mar-2020), espiral de colateral/apalancamiento (LTCM, Archegos, LDI 2022) o
quiebra opaca de crédito no bancario (Greensill, Tricolor/First Brands 2025, Blue Owl 2026).

### Qué marcaban las series antes de cada evento (FRED local, vintage actual)

Cálculo sobre los 37 `credit_event` desde 1971 con `~/financial_archive/macro/fred`
(t = día anterior al evento; percentil = histórico disponible hasta t):

| evento | NFCI t-3m → t | BAA10Y t-3m → t (pctl) | VIX t | T10Y3M mín. 12m | ΔFed funds 12m |
|---|---|---|---|---|---|
| Continental Illinois 1984 | -0,13 → 0,51 | n/d | n/d | 1,47 | +2,66 |
| LTCM 1998 | -0,56 → -0,12 | 1,67 → 2,35 (89) | 36,6 | **-0,13** | 0,0 |
| BNP 9-ago-2007 | -0,58 → -0,18 | 1,65 → 1,87 (46) | 21,5 | **-0,64** | +0,16 |
| Bear Stearns 2008 | 0,57 → 0,88 | 2,55 → 3,39 (98) | 27,3 | -0,53 | -2,28 |
| Lehman 2008 | 0,61 → 1,24 (máx. +3m 3,08) | 2,90 → 3,43 (99; máx. +3m 6,16) | 25,7 | 0,33 | -2,61 |
| Repo sep-2019 | -0,57 → -0,51 | 2,42 → 2,21 (50) | 13,7 | **-0,52** | +0,33 |
| Dash for cash mar-2020 | -0,56 → -0,13 | 2,05 → 2,55 (máx. 4,31) | 41,9 | -0,52 | -1,31 |
| LDI gilts 2022 | -0,19 → -0,15 | 2,20 → 2,08 (42) | 27,4 | 0,04 | **+3,00** |
| SVB 2023 | -0,19 → -0,24 | 1,90 → 1,85 (29) | 22,6 | **-1,32** | **+4,49** |
| First Brands 2025 | -0,49 → -0,52 | 1,79 → 1,65 (16) | 15,3 | **-0,97** | -0,74 |
| Zions/WAL oct-2025 | -0,51 → -0,52 | 1,73 → 1,68 (19) | 20,6 | -0,70 | -0,72 |
| Blue Owl feb-2026 | -0,51 → -0,54 | 1,79 → 1,67 (18) | 19,6 | -0,27 | -0,69 |

Lecciones (con los números):
1. **Los índices de condiciones financieras son coincidentes, no adelantados.** Solo el 32 % de
   los eventos tenía NFCI > 0 el día antes; el 41 % mostraba una subida de NFCI > 0,25 en 3 meses.
   En 2019-2026 casi todas las fracturas ocurrieron con NFCI < -0,15. NFCI/ANFCI sirven para
   **medir contagio** (Lehman: 1,24 → 3,08 en 3 meses), no para anticipar el detonante.
2. **Las condiciones previas son monetarias, no de spreads.** De 33 eventos desde 1982, **23 (70 %)**
   venían precedidos de curva 10a-3m invertida en los 12 meses previos (19) o de subidas de Fed
   funds > 100 pb en 12 meses (8), frente a un 41 % de días "base" con alguna de las dos
   condiciones desde 1983 → lift ≈ 1,7×. Los que no encajan son mayoritariamente contagio de una
   crisis ya en marcha (GSEs/Lehman/Reserve Primary 2008) o fraudes idiosincráticos (Greensill,
   Archegos, Terra).
3. **Spreads ajustados = complacencia.** BAA10Y estaba en percentil < 50 antes de BNP 2007 (46),
   repo 2019 (50), SVB (29) y los eventos de crédito privado 2025-26 (16-19). La señal útil es el
   **cambio** (BAA10Y +0,25 pb en 3m en el 26 % de los casos) y el nivel extremo como confirmación
   (>3,1 = p90 histórico; >3,3 = p95, alcanzado en Bear/Lehman/2002).
4. **VIX > 20** el día anterior en el 68 % de los eventos (n=31); p90 histórico 28,5.
5. Estado actual (2026-10-02): NFCI -0,49, ANFCI -0,50, **BAA10Y 1,46 (percentil 3 desde 1986)**,
   IG OAS 0,83 (mín. 0,73 ene-2026), HY OAS 3,03 (rango 2023-26: 2,59-4,61), VIX 15,3, curva 10a-3m
   +1,09 tras inversión, Fed funds 3,88 %. Spreads en mínimos tras tres sustos de crédito privado
   (Tricolor/First Brands, Zions, Blue Owl) = patrón 2005-07 (BAA10Y mín. 1,48) más que 2019.

### Panel propuesto y umbrales (alertas, no señales)

| bloque | serie FRED | ¿en archivo local? | umbral de alerta (propuesta) | ejemplo real |
|---|---|---|---|---|
| Spreads | `BAA10Y` (1986-), `AAA10Y`; `BAA`/`AAA` mensual (1919-) para historia larga | sí / falta BAA,AAA | Δ3m > +0,50 pp o nivel > 3,1 (p90) | 1998: 1,71 (jul) → 2,57 (sep) |
| Spreads ICE | `BAMLH0A0HYM2`, `BAMLC0A0CM` | sí, solo 2023- | HY OAS Δ1m > +100 pb; IG > 1,5 | abr-2025: HY 4,61 |
| Condiciones | `NFCI`, `ANFCI`, subíndices `NFCICREDIT`, `NFCILEVERAGE`, `NFCIRISK` | NFCI/ANFCI sí; subíndices no | NFCI > 0 o Δ4s > +0,3; **NFCILEVERAGE > 0** como pre-condición | Lehman: NFCI 1,24 → 3,08 |
| Estrés | `STLFSI4` (1993-) | no | > 1 (1 desv. típica) | — |
| Financiación | `TEDRATE` (1986-2022, discontinuada), sustituto FRA-OIS (no en FRED) o `SOFR` − `IORB` / `RRPONTSYD` | SOFR sí; TED/IORB no | SOFR − IORB > +10 pb; TED > 100 pb | SOFR 2,43 → **5,25 %** el 17-sep-2019 |
| Reservas | `WRESBAL`/`TOTRESNS`, `WALCL`, `WTREGEN`, `RRPONTSYD` | WALCL sí | reservas/activos bancarios cerca del mínimo de 2019 (~7 %); RRP ≈ 0 | WALCL 3,76 bn$ (sep-2019) → 4,17 (ene-2020) |
| Oferta de crédito | SLOOS `DRTSCILM`, `DRTSCIS`, `DRTSCLCC` (trimestral) | no | % neto endureciendo C&I > 20 % | (2008, 2020, 2023: > 40 %) |
| Morosidad | `DRALACBN`, `DRCCLACBS`, `DRBLACBS`, `DRCRELEXFACBS` | no | Δ4T > +0,5 pp | — |
| Política | `DFF`, `T10Y3M` | sí | ΔDFF 12m > +100 pb; T10Y3M < 0 en últimos 12-24m | SVB: ΔDFF +4,49, curva -1,32 |
| Volatilidad | `VIXCLS` | sí | > 28,5 (p90) | 9-mar-2020: 41,9 |

Regla compuesta sugerida para `src/decision`: **pre-condición** (curva invertida en 24m *o*
ΔDFF > +1 pp *o* NFCILEVERAGE > 0) × **disparador** (ΔBAA10Y 3m > +0,5 *o* ΔNFCI 4s > +0,3 *o*
SOFR−IORB > 10 pb *o* VIX > 28,5). Validar con walk-forward y vintages ALFRED: **NFCI se revisa
cada semana** — los valores de esta tabla son el vintage de 2026-10-07, no lo que se veía en tiempo
real. Muestra pequeña (≈ 12 episodios independientes): tratar como alerta, no como señal operable.

## Fallos y huecos conocidos
- IMF (403) → Laeven-Valencia vía Internet Archive; actualización LV 2020 no disponible.
- carmenreinhart.com sin descargas directas → espejo HBS (hasta 2016).
- COW intra-state v5.1 no localizado (404); UCDP termina en 2024 (v25.1; v25.2 no publicada).
- Cronologías LV de divisa/deuda solo con año de inicio (sin fin).
- NBER no ha fechado ninguna recesión tras 2020.
