# Validación Fase 1 — clasificador de régimen

Generado: 2026-10-12 por `src/regime/validate.py`. Muestra: 1950-01 → 2026-10
(922 meses). `vintage_mode`: {'mixed': 608, 'alfred': 314}. USREC se usa **solo** como verificación ex post.

> Contar episodios, no meses: hay ~11 recesiones NBER en la muestra; cualquier tasa de acierto
> tiene un intervalo de confianza amplio.

## 1. Distribución de cuadrantes por década (% de meses)

| década | Deflación/recesión | Estanflación | Goldilocks | Reflación |
|---|---|---|---|---|
| 1950s | 54.2 | 19.2 | 20.8 | 5.8 |
| 1960s | 40.0 | 22.5 | 28.3 | 9.2 |
| 1970s | 20.8 | 49.2 | 11.7 | 18.3 |
| 1980s | 28.3 | 44.2 | 3.3 | 24.2 |
| 1990s | 24.2 | 38.3 | 21.7 | 15.8 |
| 2000s | 61.7 | 13.3 | 21.7 | 3.3 |
| 2010s | 51.7 | 0.0 | 48.3 | 0.0 |
| 2020s | 45.1 | 43.9 | 1.2 | 9.8 |

## 2. Crecimiento G↓ alrededor de recesiones NBER

| periodo | % meses G↓ |
|---|---|
| en recesión NBER | 96.5 |
| 6 meses antes de recesión | 80.3 |
| expansión (resto) | 63.5 |
| todos los meses | 68.8 |

### Por recesión

| recesión | % G↓ dentro | Sahm disparada | crédito rojo/ámbar dentro | cuadrante dominante |
|---|---|---|---|---|
| 1953-08 → 1954-05 | 100.00 | True | False | Deflación/recesión |
| 1957-09 → 1958-04 | 100.00 | True | True | Deflación/recesión |
| 1960-05 → 1961-02 | 80.00 | True | False | Deflación/recesión |
| 1970-01 → 1970-11 | 100.00 | True | True | Estanflación |
| 1973-12 → 1975-03 | 100.00 | True | True | Estanflación |
| 1980-02 → 1980-07 | 100.00 | True | True | Estanflación |
| 1981-08 → 1982-11 | 87.50 | True | True | Deflación/recesión |
| 1990-08 → 1991-03 | 100.00 | True | True | Deflación/recesión |
| 2001-04 → 2001-11 | 100.00 | True | True | Deflación/recesión |
| 2008-01 → 2009-06 | 100.00 | True | True | Deflación/recesión |
| 2020-03 → 2020-04 | 100.00 | False | True | Deflación/recesión |

## 3. Episodios clave (muestra trimestral)

### 1973-74 (embargo petrolero)

Distribución: Estanflación 75 %, Goldilocks 12 %, Reflación 12 %

| mes | quadrant | G | I_state | core_6m | debt_phase | credit_light | liquidity |
|---|---|---|---|---|---|---|---|
| 1973-01 | Goldilocks | 1.01 | down | 2.84 | desapalancamiento | ámbar | neutral |
| 1973-04 | Reflación | 1.23 | up | 2.94 | desapalancamiento | rojo | neutral |
| 1973-07 | Estanflación | 0.68 | up | 4.03 | desapalancamiento | rojo | neutral |
| 1973-10 | Estanflación | 0.13 | up | 5.12 | desapalancamiento | rojo | escasa |
| 1974-01 | Estanflación | 0.15 | up | 5.80 | desapalancamiento | rojo | escasa |
| 1974-04 | Estanflación | -0.88 | up | 6.68 | desapalancamiento | rojo | escasa |
| 1974-07 | Estanflación | -0.70 | up | 9.89 | desapalancamiento | rojo | escasa |
| 1974-10 | Estanflación | -1.32 | up | 12.49 | desapalancamiento | rojo | escasa |

### 1979-80 (Volcker)

Distribución: Estanflación 79 %, Deflación/recesión 21 %

| mes | quadrant | G | I_state | core_6m | debt_phase | credit_light | liquidity |
|---|---|---|---|---|---|---|---|
| 1979-01 | Estanflación | 0.73 | up | 7.85 | desapalancamiento | rojo | escasa |
| 1979-04 | Estanflación | 0.47 | up | 7.92 | desapalancamiento | rojo | escasa |
| 1979-07 | Estanflación | 0.13 | up | 8.87 | desapalancamiento | rojo | escasa |
| 1979-10 | Estanflación | 0.19 | up | 9.51 | desapalancamiento | rojo | escasa |
| 1980-01 | Estanflación | -0.11 | up | 10.44 | desapalancamiento | rojo | escasa |
| 1980-04 | Estanflación | -0.36 | up | 12.21 | desapalancamiento | rojo | escasa |
| 1980-07 | Estanflación | -1.61 | up | 12.12 | desapalancamiento | rojo | neutral |
| 1980-10 | Deflación/recesión | -1.10 | down | 9.08 | desapalancamiento | rojo | neutral |

### 2008 (GFC)

Distribución: Deflación/recesión 58 %, Estanflación 29 %, Goldilocks 12 %

| mes | quadrant | G | I_state | core_6m | debt_phase | credit_light | liquidity |
|---|---|---|---|---|---|---|---|
| 2007-07 | Deflación/recesión | 0.01 | down | 2.11 | endurecimiento | ámbar | escasa |
| 2007-10 | Deflación/recesión | -0.01 | down | 1.83 | desapalancamiento | rojo | escasa |
| 2008-01 | Estanflación | -0.71 | up | 2.57 | desapalancamiento | rojo | neutral |
| 2008-04 | Estanflación | -0.85 | up | 2.35 | desapalancamiento | rojo | escasa |
| 2008-07 | Deflación/recesión | -0.93 | down | 2.14 | desapalancamiento | rojo | neutral |
| 2008-10 | Estanflación | -1.85 | up | 2.59 | desapalancamiento | rojo | neutral |
| 2009-01 | Deflación/recesión | -3.01 | down | 1.38 | reflación | rojo | abundante |
| 2009-04 | Deflación/recesión | -3.66 | down | 1.23 | reflación | rojo | abundante |

### 2020 (COVID)

Distribución: Deflación/recesión 83 %, Estanflación 17 %

| mes | quadrant | G | I_state | core_6m | debt_phase | credit_light | liquidity |
|---|---|---|---|---|---|---|---|
| 2020-01 | Deflación/recesión | -0.54 | down | 2.02 | techo | verde | neutral |
| 2020-04 | Deflación/recesión | -3.15 | down | 1.48 | desapalancamiento | rojo | abundante |
| 2020-07 | Deflación/recesión | -5.77 | down | 0.25 | reflación | rojo | abundante |
| 2020-10 | Deflación/recesión | -0.76 | down | 1.84 | reflación | rojo | abundante |

### 2022 (inflación/endurecimiento)

Distribución: Estanflación 67 %, Deflación/recesión 27 %, Reflación 7 %

| mes | quadrant | G | I_state | core_6m | debt_phase | credit_light | liquidity |
|---|---|---|---|---|---|---|---|
| 2021-10 | Reflación | 0.69 | up | 5.85 | reflación | verde | abundante |
| 2022-01 | Deflación/recesión | 0.80 | down | 4.75 | reflación | verde | neutral |
| 2022-04 | Estanflación | 0.56 | up | 5.76 | reflación | ámbar | escasa |
| 2022-07 | Estanflación | 0.47 | up | 5.83 | endurecimiento | ámbar | escasa |
| 2022-10 | Estanflación | 0.49 | up | 5.87 | endurecimiento | ámbar | escasa |

## 4. Estado actual (últimos 6 meses)

| mes | quadrant | G | I_state | core_6m | debt_phase | credit_light | liquidity | sahm | curve | baa_spread | vintage_mode |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-05 | Estanflación | -0.11 | up | 3.03 | expansión tardía | verde | neutral | 0.13 | 0.76 | 1.57 | alfred |
| 2026-06 | Estanflación | -0.06 | up | 3.62 | expansión tardía | verde | neutral | 0.10 | 0.51 | 1.55 | alfred |
| 2026-07 | Estanflación | -0.12 | up | 3.17 | expansión tardía | verde | neutral | 0.07 | 0.86 | 1.64 | alfred |
| 2026-08 | Estanflación | -0.10 | up | 2.94 | expansión tardía | verde | neutral | -0.03 | 0.83 | 1.54 | alfred |
| 2026-09 | Deflación/recesión | -0.04 | down | 2.66 | expansión temprana | verde | escasa | -0.07 | 1.01 | 1.46 | alfred |
| 2026-10 | Deflación/recesión | -0.05 | down | 2.66 | expansión temprana | verde | escasa | 0.00 | 1.06 | 1.46 | alfred |

## Notas y limitaciones

- G↑ exige G > 0 **y** ΔG(6m) > 0: por construcción G↓ es el estado por defecto (más del 50 % de los meses);
  no debe leerse como "probabilidad de recesión".
- Antes de 1957 la inflación subyacente se aproxima con el IPC general; antes de 1971 no hay NFCI y antes de
  1986 el diferencial Baa usa BAA−GS10 mensual si existe en curated/fred.
- `vintage_mode`: 'alfred' = todas las entradas de G e I salen de la vintage vigente en cada fecha; 'mixed' = solo
  algunas (ALFRED empieza en 1955 para PAYEMS, 1991 para GDPC1 y 1996 para el IPC subyacente); 'latest' = datos
  revisados actuales con retrasos de publicación. Los meses no-ALFRED tienen sesgo favorable (datos revisados).
- La regla de desapalancamiento del PLAN (NFCI > 0) marca casi todos los años 70-80 como desapalancamiento/crédito
  rojo: el NFCI está normalizado sobre toda su historia (1971+) y esa época fue estructuralmente más tensa.
  Pendiente para Fase 3: usar ANFCI o un z-score móvil del NFCI.
- Los umbrales (Sahm 0,5; core 2-2,5 %; Baa 3 pp) son los del PLAN, no están optimizados: no hay ajuste in-sample.

## Fases del ciclo de deuda corto (% de meses por década)

| década | desapalancamiento | endurecimiento | expansión tardía | expansión temprana | reflación | techo |
|---|---|---|---|---|---|---|
| 1950s | 0.0 | 25.8 | 20.8 | 43.3 | 10.0 | 0.0 |
| 1960s | 0.0 | 75.0 | 4.2 | 6.7 | 11.7 | 2.5 |
| 1970s | 55.0 | 7.5 | 15.0 | 4.2 | 17.5 | 0.8 |
| 1980s | 62.5 | 5.8 | 1.7 | 5.0 | 25.0 | 0.0 |
| 1990s | 14.2 | 30.8 | 18.3 | 15.0 | 21.7 | 0.0 |
| 2000s | 26.7 | 25.8 | 0.0 | 19.2 | 18.3 | 10.0 |
| 2010s | 25.8 | 6.7 | 1.7 | 24.2 | 36.7 | 5.0 |
| 2020s | 3.7 | 6.1 | 12.2 | 2.4 | 30.5 | 45.1 |
