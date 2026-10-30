---
documento: INT-8b — regla de combinación del nowcast mensual DESCRIPTIVO (congelada antes de escribir código)
version: 1.0 CONGELADA (2026-10-30)
estado: fijada por escrito y commiteada ANTES de escribir código y sin haber calculado ningún resultado (ni con datos
  ≤ 2004 ni en vivo). Cualquier cambio posterior será una versión nueva, declarada a posteriori.
depende_de: docs/int/INT8_diseno_v0.md §5 (alternativa recomendada), src/intl/termometro.py, src/report/termometro_vivo.py
---

# INT-8b: regla congelada del nowcast mensual (descriptivo)

**Pregunta (descriptiva, no confirmatoria):** "¿está empezando ya una recesión, o empezará en 0-3 meses?". La respuesta
es un **percentil y una banda frente a la propia historia 1960-2004**, nunca una probabilidad a 3 meses. Siempre con la
frase *"Informativo, no es una señal de cartera."*

## 1. Indicadores (solo los ya establecidos o coincidentes; no se buscan otros)
Por país c y fin de mes t, todos "as of" con los retrasos de `src/intl/lags.py` y `src/intl/termometro.py`. Se orientan de
modo que **alto = más parecido a una recesión**.

| clave | indicador | cálculo | orientación |
|---|---|---|---|
| K1 | curva | C1 del termómetro: media 12 m de (10 años − 3 meses) | baja = riesgo (se usa 100 − percentil) |
| K2 | difusión de curvas invertidas | C4 del termómetro: % de los otros países del núcleo con C1 < 0 (≥ 5 con dato) | alta = riesgo |
| K3 | bolsa real 12 m | C6 del termómetro: log precio 12 m − IPC interanual (sin DNK ni JPN) | baja = riesgo |
| K4 | crédito | C2 del termómetro: Δ 20 trimestres del crédito/PIB del BIS | alta = riesgo (signo de INT-4) |
| K5 | difusión de la producción industrial | % de los otros países del núcleo con IP interanual (log, 12 m) < 0 (≥ 5 con dato), como C4 | alta = riesgo |
| K6 | regla tipo Sahm | media 3 m del paro − mínimo de esa media en los 12 meses anteriores (pp), sobre el mes de observación y después "as of" (75 días); paro interpolado de 9 países fuera antes de 1998 (`src/intl/panel.py`) | alta = riesgo |

El **fechado trimestral en vivo** (`termometro.fechado_trimestral`, conocido 75 días tras el trimestre) se muestra al lado
como "confirmado por el PIB (con retraso)", pero **no entra en la combinación**: es la referencia que el nowcast intenta
adelantar; meterlo sería circular.

## 2. Regla de combinación: pesos iguales de percentiles (sin modelo, sin afinar)
1. **Percentil de cada indicador** frente a los meses 1960-01 → 2004-12 del **propio país** (valores finitos), con rango
   medio si hay empates: p = 100 · (#{h < v} + #{h ≤ v}) / (2 n). Orientado según la tabla (100 − p si "baja = riesgo").
   Si el país tiene menos de **60 meses** de historia de ese indicador, el indicador no cuenta para ese país (en ningún
   mes, tampoco en vivo).
2. **Índice del país** N(c, t) = **media simple** de los percentiles orientados disponibles ese mes, si hay **≥ 4 de los 6**;
   si no, sin dato. Pesos iguales; ni logit, ni ponderaciones estimadas, ni umbrales elegidos con el objetivo.
3. **Percentil del índice** frente a los meses 1960-2004 del propio país de N (rango medio, ≥ 60 meses; si no, "historia
   corta": se da N sin banda).
4. **Banda** (las mismas del termómetro): percentil < 50 **bajo**; 50-80 **medio**; 80-95 **alto**; ≥ 95 **muy alto**.
5. **Agregado del núcleo** (14 países): A(t) = media de N(c, t) de los países del núcleo con dato, si hay **≥ 10**; su
   percentil y su banda frente a A 1960-2004 con la misma regla. Se informa también cuántos países del núcleo están en
   "alto" o "muy alto" y cuántos están en recesión según el fechado.
6. Las distribuciones de referencia 1960-2004 (indicadores, N y A) se calculan **solo con datos de desarrollo**
   (`load_dev`, `load_dev_curado`), se congelan en un JSON con procedencia y en vivo **solo se leen** (nunca se recalculan
   con datos ≥ 2005).

## 3. Lo que NO se hace
- No se estima ningún peso ni se compara con ningún objetivo ≤ 2004 (ni AUC, ni aciertos, ni elección entre variantes).
- No se muestra ninguna probabilidad ni porcentaje "a 3 meses".
- El gráfico 1960-2004 con las recesiones es solo ilustración y se declara **contaminado** (los indicadores se eligieron
  sabiendo que funcionaron en 1974-75, 1980-82, 1990-93 y 2001-03).
