---
documento: calendario de publicación point-in-time
version: 0.3
fecha: 2026-10-15
ficheros: research/pit_calendar.yaml (máquina), research/pit_calendar_measured.csv (medición), src/features/calendar.py, src/features/alfred_raw.py
---

# Calendario de publicación point-in-time

Responde a una sola pregunta: **¿desde qué día se conocía cada observación?** La matriz de variables
(`docs/models/pit_base.md`) solo usa en la fecha de decisión t lo que estaba publicado ese día.

**Fecha de decisión:** último día hábil del mes t (calendario federal de EE. UU., ficha de la etiqueta §9). Ojo: cuando
el 1 de enero cae en sábado, el 31 de diciembre es festivo federal (p. ej. la decisión de 2004-12 es el 2004-12-30).

## 1. Reglas (en este orden)

1. **Fecha medida.** Si las vintages ALFRED/RTDSM de la serie, o de otra serie del **mismo comunicado de prensa**
   (`proxies_publicacion`: CPILFESL → CPIAUCSL, AWHMAN → PAYEMS, TCU → INDPRO, W875RX1 → PCEPI, WPU0561 → PPIACO),
   contienen la observación d y es una primera publicación, la fecha es ese `realtime_start`.
2. **Carga inicial o historia añadida después.** Si d ya está en la primera vintage del archivo, o aparece más de
   200 días después de su periodo (ALFRED añadió en 1994 el IPC de 1947-71 y en 1999 el PPI de 1913-95), no es una
   primera publicación: se usa mín(calendario, esa vintage).
3. **Calendario.** Antes del archivo de vintages, o en series sin vintages: ancla (fin del periodo de referencia; inicio
   del trimestre para el SPF) + `retardo_dias`, **conservador**: el **máximo** medido en la época más antigua con
   vintages propias, redondeado hacia arriba, o un supuesto documentado (`supuesto: true`). Excepciones documentadas
   (el test exige ahí el p90): CMRMTSPL, cuya única medición (2013+) incluye los cierres del Gobierno y no representa el
   tramo anterior a 2013 donde se usa la reserva; Filadelfia, cuyo máximo (18 días) es una vintage ALFRED que falta en
   2015-05.
4. **Sin vintages que lo recojan → no disponible.** Si d es posterior a lo que cubren las vintages, no se usa (aunque la
   última vintage del warehouse lo tenga). Así el resultado no cambia si el warehouse se trunca en t.
5. **Monotonía:** una observación cuenta como disponible cuando lo están también todas las anteriores.
6. **Suelo:** una serie anclada al fin de periodo nunca está disponible antes del día siguiente. ALFRED fecha algunos
   comunicados de empleo de 1961-63 el último día del mes o antes (retardos medidos de −2 a 0 días); con el suelo, el
   dato del mes t nunca se usa en la decisión del mes t.

En el modo `vintage` la regla es más simple: la serie es la vintage vigente en t (`realtime_start ≤ t`), con el
mismo suelo.

## 2. Retardos medidos (días desde el fin del periodo hasta la primera publicación)

`.venv/bin/python -m src.features.calendar` → `research/pit_calendar_measured.csv`. Solo primeras publicaciones
(después de la carga inicial, retardo entre −40 y 200 días).

| serie (comunicado) | archivo desde | <1980 med / p90 / máx | 1980-99 | 2000-12 | 2013+ | reserva usada |
|---|---|---|---|---|---|---|
| PAYEMS / UNRATE (Employment Situation) | 1955-05 / 1960-03 | 7 / 11 / 16 | 5 / 8 / 19 | 5 / 7,5 / 10 | 5 / 8 / 51 | 16 |
| INDPRO / TCU (G.17) | 1927-01 / 1996-11 | 18 / 28 / 33 | 15 / 17 / 24 | 15 / 17 / 18 | 16 / 17,7 / 64 | 33 |
| CPIAUCSL / CPILFESL (CPI) | 1972-07 / 1996-12 | 21 / 26 / 31 | 19 / 24 / 32 | 16 / 19 / 23 | 13 / 18 / 30 | 32 |
| PCEPI / PCEPILFE (Personal Income) | 2000-08 | — | — | 30 / 32 / 35 | 29 / 32 / 83 | 35 |
| PPIACO (PPI) | 1996-12 | — | 12 / 14 / 18 (1996-99) | 15 / 19 / 47 | 13 / 16 / 75 | 21 (supuesto) |
| M2SL (H.6) | 1980-02 | — | 13 / 16 / 18 | 13 / 16 / 16 | 15 / 27 / 28 | 21 (supuesto) |
| GDPC1 (avance) | 1991-12 | — | 29 / 31 / 54 | 29 / 31 / 31 | 29 / 30 / 84 | 60 |
| rtdsm_routput (RTDSM, mitad de mes) | 1965-11 | 46 / 46 / 46 | 46 / 46 / 75 | 46 | 46 | — |
| ICSA (semanal, desde la semana) | 2009-05 | — | — | 5 / 5 / 5 | 5 / 5 / 54 | 6 |
| CFNAI | 2011-05 | — | — | 23,5 / 26 / 26 | 23 / 26 / 87 | 28 |
| W875RX1 (labels/raw, sin vintages en el warehouse) | 2010-05 | — | — | 29 / 32 / 83 (2010+) | | 35 / fechas de PCEPI |
| CMRMTSPL (features/raw/alfred) | 2013-06 | — | — | — | 60 / 66 / 114 | 90 < 2000, 70 en 2000-12 (supuestos) |
| PERMIT (features/raw/alfred) | 1999-08 | — | — | 17 / 20 / 22 | 18 / 20 / 101 | 23 (supuesto) |
| NFCI (features/raw/alfred, semanal) | 2011-05 | — | — | 5 / 6 / 12 | 5 / 6 / 20 | 12 (supuesto; v0.2: 7) |
| AWHMAN / AHETPI (Employment Situation) | 1961-11 / 1999-08 | 5,5 / 10 / 16 | 5 / 8 / 19 | 5 / 7,5 / 10 | 5 / 8 / 51 | 16 / fechas de PAYEMS |
| CUSR0000SASLE (CPI) | 2011-04 | — | — | 15 / 18 / 19 | 13 / 18 / 30 | 32 / fechas de CPIAUCSL |
| Filadelfia ×3 (mismo mes) | 2015-04 | — | — | — | −12 / −10 / 18 | −7 (supuesto; prudente +25 antes de 1990-07) |

**Cambios de calendario visibles:** el IPC se publica cada vez antes (mediana 21 → 13 días); la producción industrial
tardaba más y era más variable antes de 1980 (p90 28, máx 33); el M2 pasó del H.6 semanal al mensual en 2021 (p90 16 →
27); los máximos de 2013+ son los cierres del Gobierno (2013 y 2025: el IPC de octubre de 2025 nunca se publicó).

**TCU: calendario frente a existencia (v0.3 tras re-auditoría, H-1).** El calendario de TCU (fechas del G.17 vía
INDPRO, 33 días de reserva antes de 1996-11) dice **cuándo** se publicaba el comunicado, no que la utilización de la
industria total existiera. Según la historia oficial del G.17 (Federal Reserve, *History of the Capacity and Capacity
Utilization Index*, https://www.federalreserve.gov/RELEASES/G17/Hist/HistCap.htm): *"In 1983, the scope of the capacity
system was increased to cover mining and utilities"*. Antes de 1983 solo existían en tiempo real la utilización de
manufacturas (Bulletin, 1968) y la de materiales (1973-08); TCU es una reconstrucción. Por eso `tcu_gap` es condicional
antes de **1984-01-01** (fecha prudente: la fuente no da el mes) en la lista blanca; el calendario no cambia.

## 3. Series sin medición o con tramos supuestos (v0.2)

| serie | regla | justificación |
|---|---|---|
| Encuesta de Filadelfia (actividad, pedidos, precios pagados) | fin de mes − 7 días; **variante prudente** (S-PIT-001): +25 días antes de 1990-07 | 3.er jueves del propio mes. ALFRED (2015+) lo confirma (mediana −12, p90 −10). 1968-90 sin verificar |
| PERMIT | vintages ALFRED desde 1999-08; antes 23 días | máximo medido en 2000-12: 22 |
| CMRMTSPL | vintages ALFRED desde 2013-06; 70 días en 2000-12; **90 días antes de 2000** | calendario anterior a 2013 no medido |
| Michigan (`umich_ics`, `umich_px1_md`) | **fuente directa**, 20 días | el dato final sale a finales del mes t; 20 días garantizan t−1. Solo desde 1978 |
| SPF | inicio del trimestre + **90 días hasta 1990-T2** / + 50 | ASA-NBER: difusión no documentada → el trimestre siguiente |
| BIS NEER | **20 días** | agregado de tipos de mercado; siempre t−1 |
| BCE (estado semanal) | **8 días** desde el lunes con que el warehouse fecha la semana | estado del viernes, publicado el martes siguiente |
| NFCI | vintages desde 2011; antes **12 días** (v0.3) | máximo medido (regla 3): 12 días en 2011-12, dentro de la época 2000-12 de la tabla §2 (las vintages empiezan en 2011-05) |
| Mercados diarios, medias mensuales de mercado, H.4.1, DTS, Pink Sheet, BoJ, GZ/EBP | sin cambios respecto a la v0.1 (1 / 1 / 1 / 1 / 7 / 7 / 35 días) | |

Cada tramo de `retardo_dias` lleva su marca `supuesto` (true = no medido), corrigiendo la v0.1 (CMRMTSPL antes de 2013,
W875RX1 antes de 2000 e ICSA antes de 2009 figuraban como medidos).

### Verificación con otra fuente (tests/test_pit_leaks.py, grupo v)

- **"Mismo comunicado de prensa":** con las vintages propias de AWHMAN, AHETPI, UNRATE (→ PAYEMS), CUSR0000SASLE,
  CPILFESL (→ CPIAUCSL), W875RX1, PCEPILFE (→ PCEPI) y TCU (→ INDPRO), la primera publicación coincide con la de la
  proxy el mismo día en el 100 % de las fechas comunes (150-800 por par).
- **Supuestos frente a ALFRED:** Filadelfia ≤ −7 días en ≥ 95 % (2015+), PERMIT ≤ 23 días en el 100 % de 1999-2012,
  CMRMTSPL ≤ 70 días en ≥ 90 %.
- Sin fuente externa disponible: Filadelfia 1968-90, SPF antes de 1990, Michigan directo, Pink Sheet, BIS, GZ/EBP, BoJ.

### Cambios de retardo efectivo con la época (no son fugas)

IPC antes de 1972 (32 días → t−2; después, fechas ALFRED → t−1); renta personal en 2000 (35 días → fechas de PCEPI:
t−2 → t−1 en ~20 % de los meses); CMRMTSPL en 2000 y 2013; SPF en 1990. El arnés debe tenerlos en cuenta con la regla 4.

## 4. Consecuencias para código existente (no tocado; propuestas)

- `src/regime/asof.py` `PUB_LAG`: CPI = 15 días **no es conservador** (mediana 19-21 y máximo 31-32 antes de 2000);
  PCE = 31 (p90 32, máx 35); INDPRO = 17 (antes de 1980 p90 28, máx 33); PAYEMS = 8 (p90 11 antes de 1980). Con
  decisión a fin de mes el efecto es pequeño (solo cuenta si el dato de t−1 salió después del último día hábil de t),
  pero existe.
- `src/labels/regime_us.months_back` (persistencia point-in-time de la ficha §12): CMRMTSPL se supone conocida hasta
  t−2, pero se publica a ~60 días (p90 66) → normalmente solo hasta t−3. INDPRO hasta t−1 falla en algunos meses de
  antes de 1980. La persistencia de `src/features/pit.py` usa las fechas reales y da el mismo resultado en
  entrenamiento (62,9 %, log-loss 1,227): G solo necesita 2 de los 4 indicadores. No cambia la etiqueta congelada.
