---
tipo: modelo
version: 0.2
estado: lista para congelar como v1.0 (pendiente de decisión del usuario)
actualizado: 2026-10-14
---

# Etiqueta de régimen EE. UU. (nowcast)

Define qué régimen hubo "de verdad" cada mes; es lo que los modelos intentan adivinar con la información de cada fecha.
Ficha completa: `docs/models/label_spec.md` · comprobaciones: `docs/models/label_v0.2_checks.md` · código: `src/labels/` · datos: `~/financial_archive/labels/regime_us_v0.2.parquet`. Ver [[Proyecto/Estado del proyecto]] y [[Proyecto/Bitácora]].

![[Proyecto/img/label_v0.2.png]]

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

## Pendiente antes de congelar como v1.0
Propuestas del constructor (decide el usuario):
1. Embargo del backtest de **6 meses** (la etiqueta usa datos hasta t+4).
2. s_G: usar 0,40 (INDPRO + PAYEMS, 1955-2024) por ser más conservadora, o escalas por época; la de 4 indicadores solo cubre 2013-2024.
3. Meses provisionales: 36, o medirlo con ALFRED.
4. Revisar el CFNAI de 2022-24 cuando salga de la ventana truncada.
