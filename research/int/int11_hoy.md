---
documento: INT-11 "hoy" — escenarios a 1 año por país (DESCRIPTIVO)
procedencia: {'commit': '4a21e13bc5aa854419331d60e6a7cc4cf341d91f', 'arbol_limpio': True, 'hora_utc': '2026-10-30T08:38:48+00:00'}
fecha: 2026-10-30 (datos en vivo hasta 2026-09-30)
aviso: DESCRIPTIVO. Motor estimado SOLO con datos ≤ 2004 (JST, 14 países); el estado actual sale de datos OCDE en vivo (PIB total en lugar de per cápita). Rentabilidades reales en moneda local. No es una recomendación.
---

# Escenarios a 1 año desde el estado actual (estimado con datos ≤ 2004)

| país | estado operable (año; inflación, brecha) | bolsa real: p5 … p50 … p95 | bonos p5 … p95 | vivienda p5 … p95 | P(bolsa ≤ −20 %) [IC 90 % parámetros] | P(inflación > 5 %) [IC] |
|---|---|---|---|---|---|---|
| BEL | expansion (2025; infl. 2.4 %, brecha +8.9 %) | -21 % … 7 % … 40 % | -8 % … 17 % | -4 % … 24 % | 6 % [3 %-9 %] | 8 % [6 %-10 %] |
| DEU | expansion (2025; infl. 2.1 %, brecha +2.8 %) | -24 % … 7 % … 41 % | -7 % … 14 % | -6 % … 24 % | 8 % [5 %-12 %] | 6 % [4 %-8 %] |
| DNK | expansion (2025; infl. 1.9 %, brecha +13.0 %) | -16 % … 7 % … 32 % | -8 % … 18 % | -4 % … 20 % | 4 % [2 %-6 %] | 8 % [6 %-10 %] |
| ESP | expansion (2025; infl. 2.6 %, brecha +12.4 %) | -20 % … 7 % … 38 % | -8 % … 21 % | -7 % … 26 % | 5 % [3 %-7 %] | 7 % [6 %-9 %] |
| FIN | expansion (2025; infl. 0.3 %, brecha +3.3 %) | -22 % … 7 % … 65 % | -9 % … 20 % | -6 % … 24 % | 6 % [3 %-9 %] | 8 % [8 %-8 %] |
| FRA | expansion (2025; infl. 0.9 %, brecha +7.3 %) | -21 % … 4 % … 37 % | -9 % … 17 % | -2 % … 21 % | 6 % [2 %-10 %] | 7 % [6 %-7 %] |
| GBR | sobrecalentamiento (2025; infl. 3.8 %, brecha +7.5 %) | -32 % … 5 % … 47 % | -14 % … 22 % | -9 % … 25 % | 10 % [7 %-13 %] | 49 % [44 %-54 %] |
| ITA | expansion (2025; infl. 1.5 %, brecha +7.4 %) | -20 % … 6 % … 38 % | -8 % … 19 % | -5 % … 20 % | 5 % [2 %-9 %] | 6 % [6 %-7 %] |
| JPN | sobrecalentamiento (2025; infl. 3.1 %, brecha +3.2 %) | -32 % … 3 % … 52 % | -14 % … 19 % | -7 % … 24 % | 12 % [8 %-17 %] | 53 % [48 %-58 %] |
| NLD | sobrecalentamiento (2025; infl. 3.2 %, brecha +9.5 %) | -32 % … 3 % … 44 % | -15 % … 20 % | -10 % … 26 % | 13 % [8 %-17 %] | 51 % [44 %-57 %] |
| NOR | sobrecalentamiento (2025; infl. 3.0 %, brecha +8.9 %) | -31 % … 1 % … 53 % | -15 % … 17 % | -9 % … 24 % | 14 % [8 %-19 %] | 49 % [44 %-55 %] |
| PRT | expansion (2025; infl. 2.3 %, brecha +13.2 %) | -19 % … 9 % … 32 % | -8 % … 21 % | -5 % … 21 % | 4 % [2 %-6 %] | 7 % [7 %-8 %] |
| SWE | expansion (2025; infl. 0.7 %, brecha +8.4 %) | -21 % … 8 % … 38 % | -8 % … 22 % | -4 % … 21 % | 6 % [3 %-9 %] | 7 % [6 %-9 %] |
| USA | expansion (2024; infl. 2.9 %, brecha +14.2 %) | -21 % … 8 % … 37 % | -9 % … 15 % | -5 % … 21 % | 5 % [3 %-8 %] | 6 % [4 %-9 %] |

Cómo leerlo: "p5 … p95" es el abanico del 90 %: en 9 de cada 10 escenarios la rentabilidad real del próximo año cae
dentro. El IC entre corchetes es solo la duda sobre los parámetros (no la mala suerte, que ya está en la probabilidad).
Letras y oro en research/int/int11_hoy.json.

**Aviso de calibración (corrida de desarrollo, research/int/int11_resultado.md):** la puerta no pasó. Dejando cada país
fuera, los abanicos del 90 % aciertan el 88,6 %, es decir, son algo estrechos. Entrenando con la historia anterior a
1950, la bolsa de 1950-2004 solo se cubrió el 80,5 %. Por eso conviene leer los extremos de la bolsa (p5, p95) como
probablemente **demasiado optimistas en anchura**. La probabilidad de inflación > 5 % es lo más informativo del motor
(Brier +25 % frente a la frecuencia histórica).
