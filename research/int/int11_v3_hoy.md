---
documento: INT-11 v3.1 "hoy" — abanicos de los próximos 12 meses por país (DESCRIPTIVO)
procedencia: {'commit': 'a40b9c176877483b3f81a304328f67b4467c4ca0', 'arbol_limpio': True, 'hora_utc': '2026-11-05T10:12:38+00:00'}
emision: 2026-11-05 (datos en vivo hasta 2026-10-31)
ventana: 2026-12-01 → 2027-11-30
aviso: DESCRIPTIVO. Motor v3.1 estimado SOLO con ≤ 2004 (JST, 14 países); estado OCDE en vivo (12 meses móviles, PIB per cápita con población Maddison extrapolada) con pertenencia suave al régimen. Calibración comprobada solo en desarrollo (contaminado); NO confirmada fuera de muestra. Rentabilidades reales en moneda local. No es una recomendación.
---

# Escenarios para 2026-12 … 2027-11 (motor v3.1 estimado con ≤ 2004)

**v3.1** = v3 con un único cambio de ingeniería declarado: cuando la fila histórica sorteada no tiene un activo (oro
antes de 1972, vivienda en ≈ 17 % de las filas), el dato se toma de una fila de la misma celda PARECIDA en el resto de
variables (emparejamiento por la media predicha), no de una al azar; así no se diluye la dependencia entre activos
(docs/int/INT11_v3_1_imputacion.md). Serie nueva del registro en vivo; no se mezcla con v3.

**Cuánto acertaron estos abanicos en el pasado** (fase D de v3, cada país predicho sin sus propios datos, 1876-2004):
el abanico "del 90 %" contuvo lo realizado el **89.8 %** de las veces (bolsa 92 %, bonos 91 %, letras 88 %, vivienda 90 %, oro 90 %); cerca del umbral del
3 %, el 94.0 %. Puerta de desarrollo: pasó. Recalculada con v3.1 (informativo, no es una puerta nueva): 89.9 %. Fuera de
muestra todavía **no está comprobado** (confirmación futura K1).

**Aviso del umbral (frontera del 3 % y brecha 0).** Países a menos de 0,5 pp del 3 % de inflación o a menos de 1 pp de
brecha 0: BEL (inflación -0.18 pp del 3 %, brecha +5.3 %: P(inflación > 5 %) 22 % suave frente a 7 % con la regla dura); DEU (inflación -0.54 pp del 3 %, brecha +0.8 %: P(inflación > 5 %) 12 % suave frente a 5 % con la regla dura); ESP (inflación +0.25 pp del 3 %, brecha +11.1 %: P(inflación > 5 %) 39 % suave frente a 54 % con la regla dura); GBR (inflación +0.24 pp del 3 %, brecha +4.1 %: P(inflación > 5 %) 35 % suave frente a 48 % con la regla dura); NLD (inflación -0.11 pp del 3 %, brecha +6.1 %: P(inflación > 5 %) 24 % suave frente a 6 % con la regla dura); NOR (inflación +0.12 pp del 3 %, brecha +4.7 %: P(inflación > 5 %) 33 % suave frente a 50 % con la regla dura); PRT (inflación -0.26 pp del 3 %, brecha +14.3 %: P(inflación > 5 %) 20 % suave frente a 7 % con la regla dura); USA (inflación +0.15 pp del 3 %, brecha +10.9 %: P(inflación > 5 %) 32 % suave frente a 48 % con la regla dura). En v3 su abanico es una MEZCLA de los regímenes vecinos (pesos en la columna "estado"), en
lugar de saltar de uno a otro por décimas: por eso su P(inflación > 5 %) queda entre los dos extremos. Aun así, un dato
nuevo de IPC puede mover bastante esas cifras.

| país | estado: pesos de régimen (12 meses móviles) | bolsa real: p5 … p50 … p95 (acierto medido del p5-p95) | bonos p5 … p95 | vivienda p5 … p95 | P(bolsa ≤ −20 %) [IC 90 % parámetros] | P(inflación > 5 %) [IC] |
|---|---|---|---|---|---|---|
| BEL | expan 64 %, sobre 36 % (IPC a 2026-09: 2.82 %; brecha pc +5.3 %) | -26 % … 6 % … 44 % (acertó 92 % país / 93 % régimen) | -11 % … 18 % | -6 % … 24 % | 9 % [5 %-13 %] | 22 % [19 %-24 %] |
| DEU | expan 68 %, sobre 11 %, estan 3 %, creci 18 % (IPC a 2026-09: 2.46 %; brecha pc +0.8 %) | -29 % … 8 % … 63 % (acertó 87 % país / 93 % régimen) | -9 % … 20 % | -7 % … 26 % | 11 % [6 %-16 %] | 12 % [11 %-13 %] |
| DNK | expan 100 % (IPC a 2026-09: 1.65 %; brecha pc +11.9 %) | -21 % … 8 % … 38 % (acertó 97 % país / 93 % régimen) | -10 % … 21 % | -2 % … 20 % | 5 % [1 %-10 %] | 7 % [5 %-9 %] |
| ESP | expan 31 %, sobre 69 % (IPC a 2026-09: 3.25 %; brecha pc +11.1 %) | -27 % … 5 % … 50 % (acertó 95 % país / 91 % régimen) | -14 % … 21 % | -8 % … 26 % | 11 % [8 %-14 %] | 39 % [36 %-43 %] |
| FIN | expan 99 %, creci 1 % (IPC a 2026-09: 1.18 %; brecha pc +2.4 %) | -33 % … 8 % … 72 % (acertó 83 % país / 93 % régimen) | -11 % … 21 % | -6 % … 28 % | 10 % [3 %-17 %] | 7 % [5 %-9 %] |
| FRA | expan 100 % (IPC a 2026-09: 1.61 %; brecha pc +4.5 %) | -27 % … 6 % … 45 % (acertó 94 % país / 93 % régimen) | -10 % … 22 % | -1 % … 23 % | 9 % [2 %-16 %] | 6 % [4 %-8 %] |
| GBR | expan 31 %, sobre 69 % (IPC a 2026-09: 3.24 %; brecha pc +4.1 %) | -25 % … 7 % … 48 % (acertó 96 % país / 91 % régimen) | -13 % … 21 % | -7 % … 24 % | 8 % [5 %-12 %] | 35 % [30 %-39 %] |
| ITA | expan 94 %, sobre 6 % (IPC a 2026-09: 2.22 %; brecha pc +8.7 %) | -23 % … 7 % … 46 % (acertó 91 % país / 93 % régimen) | -9 % … 19 % | -5 % … 21 % | 9 % [4 %-14 %] | 9 % [7 %-10 %] |
| JPN | expan 99 %, sobre 1 % (IPC a 2026-09: 1.84 %; brecha pc +4.7 %) | -22 % … 10 % … 52 % (acertó 89 % país / 93 % régimen) | -9 % … 17 % | -3 % … 20 % | 8 % [3 %-12 %] | 7 % [5 %-8 %] |
| NLD | expan 59 %, sobre 41 % (IPC a 2026-09: 2.89 %; brecha pc +6.1 %) | -24 % … 7 % … 43 % (acertó 97 % país / 93 % régimen) | -11 % … 18 % | -7 % … 23 % | 8 % [5 %-11 %] | 24 % [21 %-27 %] |
| NOR | expan 40 %, sobre 60 % (IPC a 2026-09: 3.12 %; brecha pc +4.7 %) | -28 % … 6 % … 51 % (acertó 96 % país / 91 % régimen) | -11 % … 17 % | -5 % … 22 % | 10 % [6 %-15 %] | 33 % [30 %-36 %] |
| PRT | expan 70 %, sobre 30 % (IPC a 2026-09: 2.74 %; brecha pc +14.3 %) | -32 % … 8 % … 57 % (acertó 84 % país / 93 % régimen) | -14 % … 24 % | -5 % … 21 % | 11 % [8 %-15 %] | 20 % [18 %-23 %] |
| SWE | expan 100 % (IPC a 2026-09: 0.49 %; brecha pc +4.2 %) | -25 % … 10 % … 42 % (acertó 96 % país / 93 % régimen) | -8 % … 23 % | -4 % … 21 % | 8 % [2 %-13 %] | 7 % [5 %-8 %] |
| USA | expan 38 %, sobre 62 % (IPC a 2026-09: 3.15 %; brecha pc +10.9 %) | -25 % … 8 % … 43 % (acertó 96 % país / 91 % régimen) | -12 % … 22 % | -5 % … 21 % | 9 % [6 %-12 %] | 32 % [28 %-36 %] |

Cómo leerlo: "p5 … p95" es el abanico nominal del 90 % de la rentabilidad real de los 12 meses de la ventana; entre
paréntesis, con qué frecuencia un abanico así contuvo lo realizado en el pasado para ese país y para su régimen de
partida dominante (si es < 90 %, el abanico es más estrecho de lo que dice). El IC entre corchetes es solo la duda
sobre los parámetros. κ = 1e+06 (en el borde: True). Letras, oro y la rejilla completa de
percentiles en research/int/int11_v3_hoy.json.

### Dependencia entre activos por régimen (≤ 2004, no confirmado)

Correlación (log) de los escenarios a 12 meses, bolsa-bonos / bonos-oro: hoy (con los pesos de régimen de cada país) y
partiendo de cada régimen. Con inflación alta (sobrecalentamiento) bolsa y bonos se mueven más juntos y el oro se mueve
más contra los bonos. Es la dependencia que el motor hereda de las filas históricas ≤ 2004; **no está confirmada fuera
de muestra** y no se ha contrastado (la potencia no da: docs/int/INT11_v4_correlaciones_v0.md). La correlación
negativa bolsa-bonos de los últimos años (época, no régimen) no la reproduce el motor. La de "hoy" mezcla regímenes
con medias distintas y puede quedar algo por encima de las dos columnas de partida.

| país | hoy | partiendo de expansión | partiendo de sobrecalentamiento |
|---|---|---|---|
| BEL | +0,36 / -0,17 | +0,30 / +0,01 | +0,41 / -0,33 |
| DEU | +0,22 / -0,06 | +0,14 / -0,05 | +0,43 / -0,29 |
| DNK | +0,04 / +0,05 | +0,04 / +0,05 | +0,33 / -0,32 |
| ESP | +0,42 / -0,23 | +0,21 / -0,05 | +0,47 / -0,21 |
| FIN | +0,12 / -0,06 | +0,10 / -0,08 | +0,43 / -0,24 |
| FRA | +0,21 / +0,03 | +0,20 / +0,06 | +0,49 / -0,36 |
| GBR | +0,46 / -0,26 | +0,20 / -0,04 | +0,52 / -0,28 |
| ITA | +0,21 / -0,08 | +0,19 / -0,05 | +0,41 / -0,26 |
| JPN | +0,22 / -0,00 | +0,22 / -0,02 | +0,31 / -0,29 |
| NLD | +0,24 / -0,21 | +0,14 / -0,03 | +0,34 / -0,29 |
| NOR | +0,33 / -0,22 | +0,21 / +0,11 | +0,34 / -0,31 |
| PRT | +0,39 / -0,11 | +0,24 / -0,01 | +0,54 / -0,17 |
| SWE | +0,10 / +0,00 | +0,12 / +0,01 | +0,37 / -0,24 |
| USA | +0,34 / -0,21 | +0,11 / +0,03 | +0,44 / -0,23 |

**Descriptiva ≤ 2004** (14 países, choques sin la media del país en cada estado, IC 90 % por bootstrap de años; research/int/int11_v4_potencia.json (commit 4ea97f8)): bolsa-bonos (1881-2004): inflación previa ≤ 3 % +0,23 [+0,13; +0,35] (n 851), > 3 % +0,45 [+0,35; +0,54] (n 633); diferencia +0,21 [+0,09; +0,33], 12/14 países con el mismo signo. bonos-oro (1972-2004): inflación previa ≤ 3 % +0,03 [-0,35; +0,35] (n 170), > 3 % -0,27 [-0,44; -0,03] (n 292); diferencia -0,30 [-0,58; +0,11], 2/3 países con el mismo signo.
