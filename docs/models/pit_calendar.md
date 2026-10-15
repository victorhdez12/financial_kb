---
documento: calendario de publicación point-in-time
version: 0.1
fecha: 2026-10-15
ficheros: research/pit_calendar.yaml (máquina), research/pit_calendar_measured.csv (medición), src/features/calendar.py
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
   del trimestre para el SPF) + `retardo_dias`, **conservador**: el máximo medido en la época más antigua con medición,
   redondeado hacia arriba, o un supuesto documentado (`supuesto: true`).
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
| CMRMTSPL (labels/raw) | 2013-06 | — | — | — | 60 / 66 / 114 | 70 |

**Cambios de calendario visibles:** el IPC se publica cada vez antes (mediana 21 → 13 días); la producción industrial
tardaba más y era más variable antes de 1980 (p90 28, máx 33); el M2 pasó del H.6 semanal al mensual en 2021 (p90 16 →
27); los máximos de 2013+ son los cierres del Gobierno (2013 y 2025: el IPC de octubre de 2025 nunca se publicó).

## 3. Series sin medición (supuestos)

| serie | regla | justificación |
|---|---|---|
| Encuesta de Filadelfia (actividad, pedidos) | fin de mes − 7 días | 3.er jueves del propio mes (≤ día 21). Calendario 1968-90 no documentado |
| PERMIT | 20 días | Census, ~12.º día hábil |
| UMCSENT, MICH | 35 días | Nuestra fuente (FRED) los publica con ~1 mes de retraso de licencia: se usa el retraso de la fuente para que backtest y producción vean lo mismo |
| SPF | inicio del trimestre + 60 días (hasta 1990-T2) / + 50 | Resultados a mitad del 2.º mes (catálogo: ~45 días) |
| Mercados diarios (H.15, Moody's, VIX, WTI, H.10, RRP, DTS) | 1 día | Dato de d publicado el día hábil siguiente |
| Medias mensuales de mercado (GS10, TB3MS, BAA, WTI mensual, S&P de Shiller) | 1 día tras el fin de mes | Media de precios de mercado conocida al cierre |
| WALCL, WTREGEN | 1 día | H.4.1 del jueves con dato del miércoles |
| NFCI | 5 días | viernes → miércoles |
| BCE (estado semanal) / BoJ (fin de mes) | 5 / 7 días | calendarios de los bancos centrales |
| Pink Sheet (cobre, oro) | 7 días | publicación a primeros del mes siguiente |
| BIS NEER | 30 días | a 2026-10-15 el último dato es 2026-08 |
| GZ spread / EBP | 35 días | CSV mensual de la Fed |

## 4. Consecuencias para código existente (no tocado; propuestas)

- `src/regime/asof.py` `PUB_LAG`: CPI = 15 días **no es conservador** (mediana 19-21 y máximo 31-32 antes de 2000);
  PCE = 31 (p90 32, máx 35); INDPRO = 17 (antes de 1980 p90 28, máx 33); PAYEMS = 8 (p90 11 antes de 1980). Con
  decisión a fin de mes el efecto es pequeño (solo cuenta si el dato de t−1 salió después del último día hábil de t),
  pero existe.
- `src/labels/regime_us.months_back` (persistencia point-in-time de la ficha §12): CMRMTSPL se supone conocida hasta
  t−2, pero se publica a ~60 días (p90 66) → normalmente solo hasta t−3. INDPRO hasta t−1 falla en algunos meses de
  antes de 1980. La persistencia de `src/features/pit.py` usa las fechas reales y da el mismo resultado en
  entrenamiento (62,9 %, log-loss 1,227): G solo necesita 2 de los 4 indicadores. No cambia la etiqueta congelada.
