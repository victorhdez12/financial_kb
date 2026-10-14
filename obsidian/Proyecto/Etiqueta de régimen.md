---
tipo: modelo
version: 1.0
estado: CONGELADA (tag git label-v1.0)
actualizado: 2026-10-14
---

# Etiqueta de régimen EE. UU. (nowcast)

Define qué régimen hubo "de verdad" cada mes; es lo que los modelos intentan adivinar con la información de cada fecha.
Ficha completa: `docs/models/label_spec.md` · comprobaciones: `docs/models/label_v1.0_checks.md` · código: `src/labels/` · datos: `~/financial_archive/labels/regime_us_v1.0.parquet`. Ver [[Proyecto/Estado del proyecto]] y [[Proyecto/Bitácora]].

![[Proyecto/img/label_v1.0.png]]

## Definición (decisiones del usuario, 14-oct)
- **Nowcast** del mes t, 4 cuadrantes, **EE. UU.** desde 1950 (zona euro después, con ficha propia).
- **Crecimiento (G):** conjunto coincidente del NBER (producción industrial, empleo, renta real sin transferencias, ventas reales) frente a su tendencia de 10 años; ventana **centrada en t** (t−3 a t+3).
- **Inflación (I):** PCE subyacente anualizada, centrada en t, frente a un **umbral fijo de 2,5 %**.
- **Etiqueta probabilística:** P = Φ(distancia al umbral / s), con s estimada con las revisiones de ALFRED: **s_G = 0,33 z, s_I = 0,31 pp**. Frontera si la probabilidad máxima < 0,55.
- **Cuadrantes:** Expansión (G↑ I↓) · Late cycle / sobrecalentamiento (G↑ I↑) · Estanflación (G↓ I↑) · **Crecimiento bajo / desinflación** (G↓ I↓). La recesión es una capa aparte (NBER).
- 1950-54 con peso 0 (IPC general, guerra de Corea). Últimos 24 meses provisionales; la etiqueta llega a 2026-04 porque necesita datos hasta t+4.

## Resultados v0.2
| comprobación | resultado |
|---|---|
| Meses de recesión NBER con crecimiento bajo | 100 % ✅ |
| Correlación con CFNAI-MA3 (contemporáneo / misma ventana) | 0,74 / 0,95 ✅ |
| Correlación con la brecha de producción | 0,88 ✅ |
| Episodios (años 70, 1995-99, 2008, 2020, 2021-22) | todos ✅ |
| Reparto | expansión 29 %, late cycle 24 %, estanflación 23 %, crecimiento bajo 23 % ✅ |
| Duración media | 9,1 meses (mediana 6) ✅ |
| Acierto esperado de la etiqueta dura | 84 % (87 % sin meses frontera, que son el 7 %) |

**Lectura reciente (provisional):** estanflación de 2025-11 a 2026-04, con G ligeramente por debajo de tendencia e inflación subyacente 2,9-3,9 %; marzo de 2026 en zona frontera con late cycle.

## Historia de versiones
- **v0.1** (14-oct): 11/12 comprobaciones. Fallo de diseño: las ventanas miraban hacia atrás y la etiqueta iba ~4 meses retrasada (CFNAI 0,62).
- **v0.2** (14-oct): ventanas centradas, cuadrante renombrado, peso 0 en 1950-54, escalas con los 4 indicadores. 13/13 comprobaciones. Cambian 244 de 856 meses (28,5 %), casi todos alrededor de los giros.
- **v1.0** (14-oct): s_G = 0,40, 54 meses provisionales (estudio de revisión), embargo de 6 meses. CONGELADA.

## v1.0 congelada (14-oct)
- **s_G = 0,40** (INDPRO + PAYEMS, 1955-2024; la de 4 indicadores, 0,33, solo cubría 2013-24) · **s_I = 0,31**.
- **Meses provisionales = 54**, medidos con un estudio de revisión (100 cortes semestrales 1975-2024, regla declarada antes de ejecutar: concordancia ≥ 95 % y Δp ≤ 0,05). Casi toda la revisión viene de truncar la tendencia de 10 años; las revisiones de datos de ALFRED añaden muy poco. Informe: `docs/models/label_revision_study.md`.
- **Embargo del backtest: 6 meses.** Provisional o peso 0 → no entrena ni puntúa.
- 13/13 comprobaciones; acierto esperado de la etiqueta dura 83 % (86 % sin frontera). La etiqueta dura es idéntica a la v0.2; cambian las probabilidades (Δp medio 0,019).
- Último mes maduro: **2021-10** (late cycle, 0,81). De 2025-11 a 2026-04: estanflación (0,53-0,78), provisional.
- El CFNAI negativo de 2022-24 **no** es por la revisión: es un desacuerdo de composición en un tramo casi plano.
- Hash del contenido `38250f0a…`, código `103314f1…`, commit limpio.

![[Proyecto/img/label_revision_study.png]]

## Decisión pendiente
Con 54 meses provisionales, el periodo bloqueado 2016-2026 solo tendría ~70 meses puntuables. Hay que redefinir el periodo bloqueado (ver [[Proyecto/Estado del proyecto]]).

## Cualquier cambio
Crea una v1.1/v2.0 con revalidación completa (ficha §10).
