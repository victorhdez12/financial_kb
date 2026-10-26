# INT-3d: resultado de la corrida única

Procedencia: commit `8a05f09`, árbol limpio True, 2026-10-26T19:13:28+00:00. Prerregistro v1.0 (fa6d4c9). Núcleo 14 países, 1870-2004, 267 recesiones (73 financieras), 212 entradas en inflación alta. Log real; efecto = valor en las fechas reales − media de 124 placebos desplazados (pp, o años en C7/C8).

## Familia (Holm-2)

| id | efecto | IC 95 % | p (z placebo) | p rangos | Holm | sin guerras | sin año influyente | 1950-2004 | países | ESTABLECIDO |
|---|---|---|---|---|---|---|---|---|---|---|
| C1_espera_salida | +2.8 | [+0.1; +5.4] | 0.0389 | 0.024 | no | +2.2 | +1.9 (sin 1984) | +9.6 | 13/14 | **no** |
| C3_bonos_recesion | +1.2 | [+0.1; +2.2] | 0.0289 | 0.024 | no | +1.3 | +1.0 (sin 1880) | +2.6 | 12/14 | **no** |

Bruto (sin restar el placebo) y sensibilidades de la familia:

- C1_espera_salida: bruto +7.6, placebo medio +4.8; por_evento +2.5; winsor +2.4; sin_hiperinflacion +2.5; confirmacion_12m +2.1; confirmacion_24m +3.6; países de prueba {'AUS': 0.025, 'CHE': 0.023}
- C3_bonos_recesion: bruto +2.1, placebo medio +0.9; por_evento +1.2; winsor +1.1; sin_hiperinflacion +1.2; países de prueba {'AUS': 0.009, 'CHE': 0.024}

## Descriptivos (sin veredicto)

| id | efecto | IC 95 % | p | p rangos | eventos | sin guerras | 1950-2004 |
|---|---|---|---|---|---|---|---|
| C2_fin_bolsa | -3.1 | [-12.0; +5.7] | 0.4854 | 0.456 | 245 | -4.0 | -28.9 |
| C4_espera_entrada | -3.2 | [-5.6; -0.9] | 0.0073 | 0.008 | 233 | -4.3 | -3.8 |
| C5_espera_inflac | -2.3 | [-3.6; -0.9] | 0.0008 | 0.008 | 200 | -2.2 | -3.3 |
| C6_fin_vivienda | -5.0 | [-15.0; +4.9] | 0.3190 | 0.408 | 174 | -6.6 | -27.3 |
| C7_fondo_bolsa | +0.19 años | [-0.21 años; +0.59 años] | 0.3467 | 0.432 | 239 | -0.23 años | -0.02 años |
| C8_fondo_vivienda | +0.15 años | [-0.17 años; +0.47 años] | 0.3708 | 0.424 | 168 | -0.20 años | -0.25 años |

Año del fondo respecto al valle (media real / placebo):

- todas: eq -1.28 / -1.66 (n = 239); bond -1.36 / -1.36 (n = 246); bill -1.70 / -1.70 (n = 244); viv -2.48 / -2.80 (n = 168)
- normales: eq -1.21 / -1.64 (n = 170); bond -0.94 / -1.35 (n = 176); bill -1.20 / -1.72 (n = 174); viv -2.33 / -2.79 (n = 129)
- financieras: eq -1.43 / -1.71 (n = 69); bond -2.40 / -1.40 (n = 70); bill -2.94 / -1.66 (n = 70); viv -2.95 / -2.82 (n = 39)

Coste de esperar en bruto (16 meses) y lo que queda hasta el fin del 3.er año, pp (anómalo entre paréntesis):

- entrada|todas|eq_x: espera +1.8 (-3.2); queda +8.5 (+2.3)
- entrada|todas|bond_x: espera +2.0 (+0.9); queda +2.5 (+1.1)
- entrada|todas|viv: espera +6.4 (-2.3); queda +8.8 (-2.0)
- entrada|normales|eq_x: espera +3.4 (-1.5); queda +9.0 (+2.9)
- entrada|normales|bond_x: espera +2.2 (+1.1); queda +2.9 (+1.5)
- entrada|normales|viv: espera +7.0 (-1.7); queda +10.2 (-0.6)
- entrada|financieras|eq_x: espera -2.9 (-8.4); queda +8.6 (+1.8)
- entrada|financieras|bond_x: espera +0.6 (-0.5); queda +2.6 (+1.1)
- entrada|financieras|viv: espera +4.2 (-4.5); queda +3.4 (-7.4)
- salida|todas|eq_x: espera +7.6 (+2.8); queda +11.2 (+5.1)
- salida|todas|bond_x: espera +1.6 (+0.5); queda +2.1 (+0.7)
- salida|todas|viv: espera +6.7 (-2.1); queda +9.1 (-1.7)
- salida|normales|eq_x: espera +8.2 (+3.5); queda +13.0 (+7.0)
- salida|normales|bond_x: espera +1.9 (+0.9); queda +2.3 (+0.9)
- salida|normales|viv: espera +6.4 (-2.2); queda +8.8 (-2.0)
- salida|financieras|eq_x: espera +4.5 (-0.9); queda +6.5 (-0.3)
- salida|financieras|bond_x: espera +1.5 (+0.3); queda +3.0 (+1.5)
- salida|financieras|viv: espera +6.2 (-2.5); queda +7.0 (-3.9)

Bolsa real anómala por año respecto al valle (todas; media, banda placebo 5-95 %):

- V-3: -0.4 [-2.4; +2.9]; V-2: -1.7 [-2.4; +2.8]; V-1: -6.2 [-2.5; +2.6]; V+0: +0.4 [-2.6; +2.6]; V+1: +1.3 [-2.9; +2.1]; V+2: -1.1 [-2.9; +2.2]; V+3: +1.7 [-2.9; +2.2]

Cambios de cuadrante (espera bruta 16 meses / anómala):

- entrada_inflacion_alta (n = 212): eq_x +7.1 / +2.3; bond_x -1.1 / -2.3; viv +7.2 / -1.6
- entrada_estanflacion (n = 155): eq_x +4.0 / -1.1; bond_x -1.1 / -2.3; viv +3.8 / -5.2
- salida_inflacion_alta (n = 158): eq_x +10.9 / +6.0; bond_x +2.6 / +1.5; viv +10.5 / +1.6
- entrada_crecimiento_bajo (n = 200): eq_x +9.8 / +4.7; bond_x +3.3 / +2.2; viv +8.8 / +0.2

## EE. UU. mensual (secundario, sin potencia)

| giro | fondo bolsa (meses) | fondo bono | espera NBER (meses; bolsa − letras) | espera regla 9 m (bolsa − letras) |
|---|---|---|---|---|
| pico 1969-12 | +7 | +5 | sin anuncio | -15.6 |
| pico 1973-11 | +13 | +22 | sin anuncio | -35.0 |
| pico 1980-01 | +3 | +20 | 5; -1.6 | +10.6 |
| pico 1981-07 | +12 | +2 | 6; -15.0 | -18.7 |
| pico 1990-07 | +3 | -3 | 9; +2.4 | +2.4 |
| pico 2001-03 | +24 | -13 | 8; -6.2 | -5.0 |
| valle 1970-11 | -4 | -6 | sin anuncio | +14.4 |
| valle 1975-03 | -3 | +6 | sin anuncio | +3.7 |
| valle 1980-07 | +24 | +14 | 12; -0.5 | +5.8 |
| valle 1982-11 | -4 | -13 | 8; +16.5 | +13.1 |
| valle 1991-03 | -5 | -11 | 21; +13.4 | +3.2 |
| valle 2001-11 | +16 | -13 | 20; -8.7 | -15.8 |
