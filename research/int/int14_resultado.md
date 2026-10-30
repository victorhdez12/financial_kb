# INT-14: qué les pasa a los activos tras cuatro tipos de evento (corrida única de desarrollo, ≤ 2004)

Prerregistro: `docs/int/INT14_prerregistro_v1.md` (v1.0). Procedencia: commit `609475c`, árbol limpio, 2026-10-30T17:50:04+00:00. Nada ≥ 2005. Unidades: % acumulado (pp para diferencias); capa mensual nominal en USD; panel JST real por país.

## 0. Leer primero: veredicto, corrección declarada y lectura

**Corrección declarada (defecto de implementación, detectado tras la corrida única).** En la capa anual, el placebo
de las crisis (país-evento) exigía un año falso por **cada** crisis verdadera, también por las que no entran en la
estimación por falta de rentabilidad (CAN 1907 no tiene datos JST de rentabilidad; oro antes de 1969). Era imposible
→ **0 placebos válidos → p = 1 por construcción**, no por los datos (las tablas de abajo, generadas por la corrida, lo
muestran con "(1.0)"). La corrección (`placebo_panel(..., solo_con_dato=True)`, commit `cadcba1`, script con puerta
`scripts/int14_placebo_corregido.py` → `research/int/int14_placebo_corregido.json`) sortea falsos solo para los
eventos que entran en el efecto, que es lo que dice el prerregistro §4. **No cambia efectos ni IC**, solo valores p.
Como la corrección se hizo **después** de ver el resultado, todo lo que cambia de veredicto por ella queda marcado y
pide validación independiente.

| id | pregunta | n | efecto frente a lo normal | IC 90 % | p placebo (corregido) | p Holm | veredicto |
|---|---|---|---|---|---|---|---|
| H1 | crisis bancaria → vivienda real, t+1..t+3 | 43 | **−6,7 pp** | [−13,3; −0,5] | 0,011 (v1.0: 1,0, degenerado) | **0,042** | **establecido tras corrección declarada** (antes: no establecido por p degenerado) |
| H2 | crisis bancaria → bolsa real, t+1 | 63 | −0,6 pp | [−4,2; 3,8] | 0,82 | 1,0 | no establecido |
| H3 | pico de volatilidad → bolsa EE. UU., 12 m | 16 | +4,0 pp | [−4,6; 12,9] | 0,56 | 1,0 | no establecido |
| H4 | shock del petróleo → bolsa real, t+1 | 157 (12 años) | −3,7 pp | [−13,7; 4,7] | 0,37 (v1.0: 0,32) | 1,0 | no establecido |

H4 cambia algo porque con la corrección el año 2004 (sin t+1 ≤ 2004) ya no pide un año falso. H1 queda justo en el
límite (p Holm 0,042) y además el MDE de fase 1 era optimista (autocorrelación de la vivienda): **tómese como
"probable", no como hecho**; la confirmación es ≥ 2005 (2008 en adelante).

**Lectura por evento (en lenguaje llano; descriptivo salvo H1-H4; n pequeño → IC anchos):**
- **Crisis bancaria (71 país-evento, 1870-2004).** El golpe a la bolsa llega **el mismo año** (−18 pp frente a lo
  normal, p corregido 0,003); después **no sigue cayendo** (t+1: −0,6 pp, H2) y a 2-3 años rebota (+9 pp). La
  **vivienda real sí sigue bajando** 1-3 años (−6,7 pp; −19 pp en las 12 crisis de 1946-2004). Lo que **protege**: los
  activos seguros en términos reales — **bonos +19 pp y letras +7,6 pp** a 3 años frente a lo normal (inflación baja
  tras las crisis). Materias primas (CLR) **sufren** (−18 pp a 3 años, 18 episodios globales). Oro: solo 5 episodios
  con oro libre → no se sabe.
- **Pico de volatilidad (16, 1931-2004).** La bolsa de EE. UU. a 12 m: +4 pp frente a lo normal, IC [−4,6; 12,9]: **no
  se puede decir que "comprar en el pánico" rinda más** (con sep. 6: +8,8 pp, IC [1,5; 18,3], p 0,11). Lo que mejor se
  porta: **bonos del Tesoro 10 a. (+4,4 pp a 12 m, IC [1,4; 7,2], p placebo 0,003 en todos los horizontes)** — el
  refugio clásico. **Metales base sufren** (−11 pp a 12 m, −18 pp a 24 m). Oro: sin protección clara (−6 pp a 12 m;
  −21 pp a 24 m, n 10). En el panel (años globales), la bolsa real cae el año del pico (−7 pp) y no se recupera
  claramente a 3 años.
- **Shock del petróleo (13; 6-12 con datos mensuales).** Bolsa EE. UU. a 12 m ≈ igual que lo normal (+0,5 pp, IC
  [−7; 18]); en el panel real −3,7 pp a 1 año y −7 pp a 3 años, sin significación. Suben las **letras** (+3 pp a 12 m:
  son los años 70, de tipos altos) y, con IC muy anchos, **oro (+18 pp), metales preciosos (+22 pp, p 0,003) y energía
  (+11 pp)** a 12 m. **Bonos reales a 3 años −16 pp** (p corregido 0,043): la inflación del shock castiga la renta fija.
  Sensibilidad Hamilton (10 episodios 1947-2002): bolsa −3,2 pp a 12 m, IC [−11; 4].
- **Subida fuerte del dólar (3: 1981, 1984, 2000).** **n insuficiente**; solo medias: bolsa −11 pp, materias −13 a
  −23 pp, oro −13 pp a 12 m (lo que dice la teoría: dólar fuerte → materias y oro débiles), sin ninguna prueba.

**Tabla del §2:** la fila de la **bolsa** es la **referencia** de cada evento (su etiqueta "protege" solo dice que su
media fue > 0). Para el motor INT-11 interesan sobre todo las filas del panel (real, 1-3 años).

**Avisos:** capa mensual nominal (los años 70 inflan letras/oro/materias tras el petróleo); petróleo y volatilidad se
solapan en 5 de 6 shocks con datos diarios; dos celdas mensuales (oro a 24 m tras volatilidad y dólar u05) y varias
de oro anual no admiten placebo (fechas falsas imposibles con la separación fijada) → p no calculable.

## 1. Contrastes principales (Holm, α = 5 %) — salida ORIGINAL de la corrida (p de H1-H2 degenerado; ver §0)

| id | pregunta | n | efecto frente a lo normal | IC 90 % | p placebo | p Holm | veredicto |
|---|---|---|---|---|---|---|---|
| H1 | crisis bancaria → vivienda real, t+1..t+3 (panel JST) | 43 | -6.73 pp | [-13.34, -0.54] | 1.0 | 1.0 | **no establecido** |
| H2 | crisis bancaria → bolsa real, t+1 (panel JST) | 63 | -0.61 pp | [-4.21, 3.75] | 1.0 | 1.0 | **no establecido** |
| H3 | pico de volatilidad → bolsa EE. UU., 12 m | 16 | 3.99 pp | [-4.62, 12.94] | 0.5642 | 1.0 | **no establecido** |
| H4 | shock del petróleo → bolsa real, t+1 (panel JST, años globales) | 157 | -3.74 pp | [-13.7, 4.65] | 0.3183 | 1.0 | **no establecido** |

"Establecido" = p Holm < 0,05 y el IC 90 % no contiene 0. "No establecido" no prueba que no haya efecto: el MDE (80 %) era 7-13 pp.

## 2. Qué activo protege en cada evento (descriptivo; orientativo con n pequeño)

"protege" = rentabilidad media tras el evento > 0 y mayor que la de la bolsa en la misma capa; "sufre" = efecto frente a lo normal con IC 90 % entero < 0.

| evento | capa | activo | n | media tras evento | frente a lo normal | IC 90 % | etiqueta |
|---|---|---|---|---|---|---|---|
| petroleo | mensual EE. UU./mundo, 12 m (nominal) | bolsa | 6 | 10.52 % | 0.5 pp | [-7.42, 18.15] | protege |
| petroleo | mensual EE. UU./mundo, 12 m (nominal) | letras | 6 | 6.6 % | 3.06 pp | [2.06, 4.79] | — |
| petroleo | mensual EE. UU./mundo, 12 m (nominal) | bonos_10a_aprox | 12 | 4.97 % | 0.2 pp | [-2.78, 3.48] | — |
| petroleo | mensual EE. UU./mundo, 12 m (nominal) | oro | 6 | 24.2 % | 17.73 pp | [-15.7, 51.76] | protege |
| petroleo | mensual EE. UU./mundo, 12 m (nominal) | materias_aqr_cfp | 6 | 13.69 % | 5.03 pp | [-6.25, 15.58] | protege |
| petroleo | mensual EE. UU./mundo, 12 m (nominal) | materias_aqr_clr_exceso | 12 | -0.22 % | -4.58 pp | [-14.29, 4.14] | — |
| petroleo | mensual EE. UU./mundo, 12 m (nominal) | petroleo | 12 | 9.22 % | 2.68 pp | [-20.78, 25.45] | — |
| petroleo | mensual EE. UU./mundo, 12 m (nominal) | energia_bm | 6 | 21.59 % | 11.46 pp | [-26.28, 49.69] | protege |
| petroleo | mensual EE. UU./mundo, 12 m (nominal) | metales_base_bm | 6 | 7.31 % | 2.1 pp | [-23.42, 26.37] | — |
| petroleo | mensual EE. UU./mundo, 12 m (nominal) | metales_preciosos_bm | 6 | 28.86 % | 21.86 pp | [-15.06, 58.94] | protege |
| vol | mensual EE. UU./mundo, 12 m (nominal) | bolsa | 16 | 13.97 % | 3.99 pp | [-4.62, 12.94] | protege |
| vol | mensual EE. UU./mundo, 12 m (nominal) | letras | 16 | 3.99 % | 0.46 pp | [-1.17, 2.1] | — |
| vol | mensual EE. UU./mundo, 12 m (nominal) | bonos_10a_aprox | 16 | 9.38 % | 4.35 pp | [1.36, 7.19] | — |
| vol | mensual EE. UU./mundo, 12 m (nominal) | oro | 10 | 3.98 % | -5.99 pp | [-18.05, 4.61] | — |
| vol | mensual EE. UU./mundo, 12 m (nominal) | materias_aqr_cfp | 16 | 9.35 % | 0.96 pp | [-5.52, 10.08] | — |
| vol | mensual EE. UU./mundo, 12 m (nominal) | materias_aqr_clr_exceso | 16 | 5.15 % | 1.43 pp | [-5.4, 10.29] | — |
| vol | mensual EE. UU./mundo, 12 m (nominal) | petroleo | 15 | 0.63 % | -4.32 pp | [-19.44, 13.24] | — |
| vol | mensual EE. UU./mundo, 12 m (nominal) | energia_bm | 11 | 1.92 % | -7.97 pp | [-22.28, 14.71] | — |
| vol | mensual EE. UU./mundo, 12 m (nominal) | metales_base_bm | 11 | -5.63 % | -11.19 pp | [-18.43, -1.58] | sufre |
| vol | mensual EE. UU./mundo, 12 m (nominal) | metales_preciosos_bm | 11 | 1.59 % | -6.89 pp | [-16.11, 7.46] | — |
| dolar | mensual EE. UU./mundo, 12 m (nominal) | bolsa | 3 | -1.78 % | -10.91 pp | None | n insuficiente |
| dolar | mensual EE. UU./mundo, 12 m (nominal) | letras | 3 | 8.15 % | 4.43 pp | None | n insuficiente |
| dolar | mensual EE. UU./mundo, 12 m (nominal) | bonos_10a_aprox | 3 | 18.36 % | 12.51 pp | None | n insuficiente |
| dolar | mensual EE. UU./mundo, 12 m (nominal) | oro | 3 | -6.79 % | -13.11 pp | None | n insuficiente |
| dolar | mensual EE. UU./mundo, 12 m (nominal) | materias_aqr_cfp | 3 | -4.85 % | -13.04 pp | None | n insuficiente |
| dolar | mensual EE. UU./mundo, 12 m (nominal) | materias_aqr_clr_exceso | 3 | -12.1 % | -16.68 pp | None | n insuficiente |
| dolar | mensual EE. UU./mundo, 12 m (nominal) | petroleo | 3 | -16.27 % | -22.85 pp | None | n insuficiente |
| dolar | mensual EE. UU./mundo, 12 m (nominal) | energia_bm | 3 | -16.14 % | -27.18 pp | None | n insuficiente |
| dolar | mensual EE. UU./mundo, 12 m (nominal) | metales_base_bm | 3 | -15.17 % | -20.14 pp | None | n insuficiente |
| dolar | mensual EE. UU./mundo, 12 m (nominal) | metales_preciosos_bm | 3 | -9.96 % | -15.49 pp | None | n insuficiente |
| crisis | panel JST real, t+1..t+3 | bolsa | 63 | 26.69 % | 9.01 pp | [3.55, 13.3] | protege |
| crisis | panel JST real, t+1..t+3 | bonos | 63 | 24.56 % | 18.85 pp | [11.83, 24.8] | — |
| crisis | panel JST real, t+1..t+3 | letras | 65 | 13.86 % | 7.55 pp | [3.69, 10.57] | — |
| crisis | panel JST real, t+1..t+3 | vivienda | 43 | 16.25 % | -6.73 pp | [-13.34, -0.54] | sufre |
| crisis | mundial anual (USD), t+1..t+3 | oro_real_usd | 5 | 8.69 % | 0.89 pp | [-34.18, 38.85] | — |
| crisis | mundial anual (USD), t+1..t+3 | materias_clr_exceso | 18 | -3.51 % | -17.79 pp | [-30.9, -4.59] | sufre |
| petroleo_global | panel JST real, t+1..t+3 | bolsa | 157 | 10.78 % | -7.24 pp | [-24.74, 10.34] | protege |
| petroleo_global | panel JST real, t+1..t+3 | bonos | 157 | -6.53 % | -15.85 pp | [-37.81, 3.3] | — |
| petroleo_global | panel JST real, t+1..t+3 | letras | 157 | 4.84 % | -1.96 pp | [-6.73, 2.82] | — |
| petroleo_global | panel JST real, t+1..t+3 | vivienda | 136 | 21.54 % | -2.52 pp | [-8.03, 3.05] | protege |
| petroleo_global | mundial anual (USD), t+1..t+3 | oro_real_usd | 6 | 16.3 % | 3.47 pp | [-29.62, 41.58] | protege |
| petroleo_global | mundial anual (USD), t+1..t+3 | materias_clr_exceso | 10 | 16.5 % | 12.88 pp | [-9.52, 34.95] | protege |
| vol_global | panel JST real, t+1..t+3 | bolsa | 207 | 9.05 % | -10.37 pp | [-26.37, 5.77] | protege |
| vol_global | panel JST real, t+1..t+3 | bonos | 207 | 10.08 % | 5.34 pp | [-4.4, 15.55] | protege |
| vol_global | panel JST real, t+1..t+3 | letras | 205 | 2.88 % | -4.76 pp | [-10.17, 0.48] | — |
| vol_global | panel JST real, t+1..t+3 | vivienda | 200 | 21.01 % | -3.97 pp | [-8.06, -0.15] | sufre |
| vol_global | mundial anual (USD), t+1..t+3 | oro_real_usd | 9 | -2.33 % | -16.17 pp | [-38.15, 8.07] | — |
| vol_global | mundial anual (USD), t+1..t+3 | materias_clr_exceso | 13 | 22.82 % | 19.61 pp | [3.98, 34.13] | protege |
| dolar_global | panel JST real, t+1..t+3 | bolsa | 48 | 19.89 % | 3.59 pp | None | n insuficiente |
| dolar_global | panel JST real, t+1..t+3 | bonos | 48 | 21.04 % | 15.7 pp | None | n insuficiente |
| dolar_global | panel JST real, t+1..t+3 | letras | 48 | 8.07 % | 1.97 pp | None | n insuficiente |
| dolar_global | panel JST real, t+1..t+3 | vivienda | 48 | 22.56 % | -0.35 pp | None | n insuficiente |
| dolar_global | mundial anual (USD), t+1..t+3 | oro_real_usd | 3 | 9.94 % | 0.39 pp | None | n insuficiente |
| dolar_global | mundial anual (USD), t+1..t+3 | materias_clr_exceso | 3 | 6.79 % | 0.13 pp | None | n insuficiente |

## 3. Trayectoria por horizonte (capa mensual, eventos principales)

### shock del petróleo — efecto frente a lo normal (pp) [IC 90 %] (p placebo)

| activo | n | 1 m | 3 m | 6 m | 12 m | 24 m |
|---|---|---|---|---|---|---|
| bolsa | 6 | 1.56 [0.06; 3.04] (0.4053) | 2.39 [0.55; 4.98] (0.5349) | 2.87 [-2.81; 16.04] (0.6478) | 0.5 [-7.42; 18.15] (0.9668) | -3.52 [-15.02; 21.28] (0.7542) |
| letras | 6 | 0.18 [0.05; 0.37] (0.0299) | 0.63 [0.27; 1.05] (0.0266) | 1.61 [1.22; 2.41] (0.0033) | 3.06 [2.06; 4.79] (0.0066) | 5.58 [3.04; 9.31] (0.0399) |
| bonos_10a_aprox | 12 | 0.41 [-0.0; 0.8] (0.196) | -0.03 [-1.01; 1.23] (0.9801) | 0.86 [-0.47; 2.58] (0.4186) | 0.2 [-2.78; 3.48] (0.8937) | 2.28 [-1.92; 7.91] (0.3389) |
| oro | 6 | 1.03 [-2.65; 4.86] (0.5781) | -0.67 [-4.86; 3.78] (0.8738) | -2.58 [-9.91; 4.98] (0.6445) | 17.73 [-15.7; 51.76] (0.0897) | 14.86 [-19.41; 47.31] (0.3422) |
| materias_aqr_cfp | 6 | -0.59 [-2.65; 1.27] (0.6678) | 1.77 [-3.57; 5.34] (0.5216) | 2.33 [-7.64; 7.22] (0.6312) | 5.03 [-6.25; 15.58] (0.5581) | 2.68 [-21.93; 26.75] (0.8339) |
| materias_aqr_clr_exceso | 12 | 2.3 [0.05; 4.62] (0.093) | 3.67 [-0.19; 6.82] (0.1827) | 1.09 [-3.39; 5.13] (0.7708) | -4.58 [-14.29; 4.14] (0.4086) | -6.87 [-21.51; 7.95] (0.3522) |
| petroleo | 12 | 3.89 [1.96; 5.75] (0.0664) | 6.92 [-2.74; 16.35] (0.0831) | 2.77 [-13.1; 15.2] (0.6445) | 2.68 [-20.78; 25.45] (0.6811) | -9.02 [-39.09; 19.54] (0.5648) |
| energia_bm | 6 | 4.52 [1.89; 7.81] (0.0664) | 1.86 [-6.59; 14.23] (0.6744) | 2.28 [-21.74; 22.3] (0.7076) | 11.46 [-26.28; 49.69] (0.1993) | 6.14 [-47.57; 54.1] (0.9767) |
| metales_base_bm | 6 | 2.11 [-1.53; 5.39] (0.186) | 1.96 [-7.39; 8.21] (0.5116) | 2.92 [-11.92; 12.78] (0.6113) | 2.1 [-23.42; 26.37] (0.7907) | -17.28 [-33.16; -3.76] (0.2957) |
| metales_preciosos_bm | 6 | 1.5 [-2.23; 5.23] (0.3854) | 0.33 [-4.3; 4.93] (0.9203) | -1.03 [-8.85; 7.26] (0.8306) | 21.86 [-15.06; 58.94] (0.0033) | 15.01 [-16.2; 45.26] (0.1329) |

### pico de volatilidad — efecto frente a lo normal (pp) [IC 90 %] (p placebo)

| activo | n | 1 m | 3 m | 6 m | 12 m | 24 m |
|---|---|---|---|---|---|---|
| bolsa | 16 | -0.02 [-3.9; 4.62] (0.99) | 3.78 [-0.17; 8.76] (0.0831) | 2.78 [-1.68; 7.8] (0.3422) | 3.99 [-4.62; 12.94] (0.5642) | 1.42 [-8.95; 11.8] (0.9568) |
| letras | 16 | 0.06 [-0.08; 0.23] (0.2857) | 0.16 [-0.24; 0.57] (0.3322) | 0.28 [-0.49; 1.04] (0.4518) | 0.46 [-1.17; 2.1] (0.5482) | 0.56 [-2.77; 3.88] (0.8106) |
| bonos_10a_aprox | 16 | 1.24 [0.35; 2.34] (0.0033) | 3.35 [1.03; 6.25] (0.0033) | 3.57 [1.15; 6.26] (0.0033) | 4.35 [1.36; 7.19] (0.0033) | 6.8 [1.92; 11.62] (0.0033) |
| oro | 10 | 0.65 [-3.9; 5.29] (0.6545) | 2.71 [-5.01; 10.11] (0.3488) | 3.52 [-5.04; 11.8] (0.4252) | -5.99 [-18.05; 4.61] (0.412) | -21.42 [-41.11; -6.74] (1.0) |
| materias_aqr_cfp | 16 | 2.3 [-0.84; 5.71] (0.0399) | 4.07 [-0.81; 10.13] (0.0399) | 3.6 [-0.89; 9.17] (0.2027) | 0.96 [-5.52; 10.08] (0.7807) | 3.35 [-4.63; 11.25] (0.6047) |
| materias_aqr_clr_exceso | 16 | 2.29 [-0.88; 5.72] (0.0664) | 4.06 [-0.83; 10.25] (0.0631) | 3.75 [-0.87; 9.58] (0.3223) | 1.43 [-5.4; 10.29] (0.7741) | 2.98 [-7.08; 13.21] (0.7143) |
| petroleo | 15 | 8.78 [-0.62; 22.2] (0.0199) | 2.33 [-8.64; 18.21] (0.4585) | -3.69 [-16.81; 12.59] (0.4618) | -4.32 [-19.44; 13.24] (0.485) | 3.87 [-11.13; 19.46] (0.7076) |
| energia_bm | 11 | 12.14 [1.78; 31.16] (0.0033) | 8.29 [-3.28; 27.86] (0.0066) | -3.34 [-16.06; 18.25] (0.5183) | -7.97 [-22.28; 14.71] (0.2525) | -7.09 [-21.27; 14.93] (0.7317) |
| metales_base_bm | 11 | -2.31 [-4.47; -0.46] (0.0631) | -2.54 [-6.02; 1.01] (0.3322) | -2.69 [-7.19; 2.94] (0.495) | -11.19 [-18.43; -1.58] (0.0764) | -17.58 [-27.97; -4.1] (0.0122) |
| metales_preciosos_bm | 11 | -0.83 [-6.01; 5.46] (0.5581) | 1.94 [-4.67; 12.79] (0.3854) | 3.6 [-4.33; 15.61] (0.3688) | -6.89 [-16.11; 7.46] (0.2924) | -21.34 [-35.72; -7.2] (0.1341) |

### subida fuerte del dólar — efecto frente a lo normal (pp) [IC 90 %] (p placebo)

| activo | n | 1 m | 3 m | 6 m | 12 m | 24 m |
|---|---|---|---|---|---|---|
| bolsa | 3 | n<5 | n<5 | n<5 | n<5 | n<5 |
| letras | 3 | n<5 | n<5 | n<5 | n<5 | n<5 |
| bonos_10a_aprox | 3 | n<5 | n<5 | n<5 | n<5 | n<5 |
| oro | 3 | n<5 | n<5 | n<5 | n<5 | n<5 |
| materias_aqr_cfp | 3 | n<5 | n<5 | n<5 | n<5 | n<5 |
| materias_aqr_clr_exceso | 3 | n<5 | n<5 | n<5 | n<5 | n<5 |
| petroleo | 3 | n<5 | n<5 | n<5 | n<5 | n<5 |
| energia_bm | 3 | n<5 | n<5 | n<5 | n<5 | n<5 |
| metales_base_bm | 3 | n<5 | n<5 | n<5 | n<5 | n<5 |
| metales_preciosos_bm | 3 | n<5 | n<5 | n<5 | n<5 | n<5 |

## 4. Panel anual JST (real), efecto frente a lo normal (pp) [IC 90 %] (p placebo)

### crisis

| activo | n | año t | t+1 | t+1..t+2 | t+1..t+3 |
|---|---|---|---|---|---|
| bolsa | 63 | -17.94 [-21.94; -13.47] (1.0) | -0.61 [-4.21; 3.75] (1.0) | 7.61 [2.86; 12.09] (1.0) | 9.01 [3.55; 13.3] (1.0) |
| bonos | 63 | 0.74 [-2.44; 2.76] (1.0) | 8.67 [5.7; 10.81] (1.0) | 15.44 [9.73; 19.5] (1.0) | 18.85 [11.83; 24.8] (1.0) |
| letras | 65 | 2.56 [0.77; 4.38] (1.0) | 4.6 [2.74; 5.95] (1.0) | 6.94 [3.7; 9.31] (1.0) | 7.55 [3.69; 10.57] (1.0) |
| vivienda | 43 | -2.42 [-5.81; 0.45] (1.0) | -2.26 [-5.57; 1.7] (1.0) | -5.29 [-10.45; -0.07] (1.0) | -6.73 [-13.34; -0.54] (1.0) |

### crisis_1946_2004

| activo | n | año t | t+1 | t+1..t+2 | t+1..t+3 |
|---|---|---|---|---|---|
| bolsa | 12 | -21.68 [-56.41; -11.42] (0.0033) | 2.93 [-11.31; 19.96] (0.6113) | 13.9 [-16.72; 25.17] (0.0797) | 11.72 [-23.04; 28.23] (0.2425) |
| bonos | 12 | -0.95 [-17.81; 5.62] (0.7243) | 6.76 [-4.48; 11.07] (0.0266) | 14.33 [-8.04; 21.87] (0.0033) | 13.58 [-7.23; 21.46] (0.0166) |
| letras | 12 | 0.06 [-6.09; 1.74] (0.9734) | 0.46 [-5.07; 2.01] (0.7807) | 0.59 [-8.15; 3.11] (0.7575) | 0.83 [-12.33; 4.58] (0.8106) |
| vivienda | 12 | -6.28 [-7.25; -4.5] (0.0332) | -9.26 [-11.47; -1.72] (0.0133) | -15.03 [-18.53; -2.05] (0.0033) | -19.45 [-23.6; -6.62] (0.0033) |

### petroleo_global

| activo | n | año t | t+1 | t+1..t+2 | t+1..t+3 |
|---|---|---|---|---|---|
| bolsa | 157 | -4.81 [-11.86; 1.65] (0.1561) | -3.74 [-13.7; 4.65] (0.3183) | -7.0 [-21.3; 4.9] (0.2658) | -7.24 [-24.74; 10.34] (0.4319) |
| bonos | 157 | -1.32 [-5.74; 2.48] (0.6811) | 1.35 [-2.95; 5.56] (0.6944) | 2.04 [-4.52; 9.08] (0.8571) | -15.85 [-37.81; 3.3] (0.0631) |
| letras | 158 | -0.93 [-3.08; 0.82] (0.4684) | 0.08 [-1.59; 1.75] (0.9568) | -1.56 [-4.42; 1.22] (0.5648) | -1.96 [-6.73; 2.82] (0.6246) |
| vivienda | 136 | 0.14 [-0.95; 1.16] (0.9037) | -0.25 [-1.86; 1.31] (0.7708) | -0.79 [-5.06; 3.44] (0.6977) | -2.52 [-8.03; 3.05] (0.3721) |

### vol_global

| activo | n | año t | t+1 | t+1..t+2 | t+1..t+3 |
|---|---|---|---|---|---|
| bolsa | 239 | -7.25 [-13.85; 0.07] (0.0266) | -3.87 [-10.49; 2.43] (0.2757) | -5.03 [-17.0; 7.51] (0.4352) | -10.37 [-26.37; 5.77] (0.2857) |
| bonos | 238 | 0.35 [-2.61; 3.19] (0.9037) | 2.15 [-1.89; 6.38] (0.5814) | 3.48 [-3.37; 9.45] (0.8339) | 5.34 [-4.4; 15.55] (0.7043) |
| letras | 237 | -0.36 [-2.43; 1.62] (0.7143) | -1.17 [-3.41; 0.85] (0.3455) | -2.64 [-6.66; 0.96] (0.2791) | -4.76 [-10.17; 0.48] (0.412) |
| vivienda | 232 | 0.28 [-1.02; 1.46] (0.7409) | -0.29 [-1.56; 0.97] (0.7043) | -1.31 [-4.35; 1.61] (0.5282) | -3.97 [-8.06; -0.15] (0.2027) |

### dolar_global

| activo | n | año t | t+1 | t+1..t+2 | t+1..t+3 |
|---|---|---|---|---|---|
| bolsa | 48 | n<5 | n<5 | n<5 | n<5 |
| bonos | 48 | n<5 | n<5 | n<5 | n<5 |
| letras | 48 | n<5 | n<5 | n<5 | n<5 |
| vivienda | 48 | n<5 | n<5 | n<5 | n<5 |

## 5. Capa mundial anual (oro real en USD desde 1969; materias CLR exceso desde 1878)

- crisis_episodios → oro_real_usd (n 5): año t / t+1 / t+1..2 / t+1..3 = 3.01 [-17.37; 22.89] · -12.46 [-26.79; -0.68] · 1.78 [-29.15; 36.61] · 0.89 [-34.18; 38.85]
- crisis_episodios → materias_clr_exceso (n 18): año t / t+1 / t+1..2 / t+1..3 = -11.59 [-19.25; -4.77] · -5.24 [-13.65; 2.53] · -12.69 [-25.61; -0.14] · -17.79 [-30.9; -4.59]
- petroleo → oro_real_usd (n 6): año t / t+1 / t+1..2 / t+1..3 = 15.6 [-1.81; 35.63] · 6.92 [-9.87; 21.74] · -0.54 [-24.33; 25.32] · 3.47 [-29.62; 41.58]
- petroleo → materias_clr_exceso (n 10): año t / t+1 / t+1..2 / t+1..3 = 2.41 [-10.08; 14.65] · -5.7 [-16.58; 4.13] · 2.67 [-16.96; 22.86] · 12.88 [-9.52; 34.95]
- vol → oro_real_usd (n 10): año t / t+1 / t+1..2 / t+1..3 = 2.08 [-7.5; 12.3] · -6.21 [-16.35; 4.96] · -18.32 [-31.54; -4.77] · -16.17 [-38.15; 8.07]
- vol → materias_clr_exceso (n 15): año t / t+1 / t+1..2 / t+1..3 = 4.64 [-6.16; 14.08] · -1.12 [-14.12; 10.65] · 2.98 [-7.03; 13.17] · 19.61 [3.98; 34.13]
- dolar → oro_real_usd (n 3): año t / t+1 / t+1..2 / t+1..3 = n<5 · n<5 · n<5 · n<5
- dolar → materias_clr_exceso (n 3): año t / t+1 / t+1..2 / t+1..3 = n<5 · n<5 · n<5 · n<5

## 6. Sensibilidades (capa mensual, bolsa a 12 m)

- petroleo: n 6, efecto 0.5 pp, IC [-7.42, 18.15], p 0.9668
- vol: n 16, efecto 3.99 pp, IC [-4.62, 12.94], p 0.5642
- dolar: n 3, efecto -10.91 pp, IC None, p None
- petroleo_sens_u10: n 8, efecto -3.42 pp, IC [-17.57, 9.57], p 0.6777
- petroleo_sens_u30: n 4, efecto -11.58 pp, IC None, p None
- petroleo_sens_domestico: n 5, efecto -2.24 pp, IC [-19.28, 13.74], p 0.7807
- petroleo_sens_hamilton2011: n 10, efecto -3.22 pp, IC [-10.88, 3.98], p 0.6312
- vol_sens_p95: n 8, efecto 2.76 pp, IC [-4.21, 11.76], p 0.701
- vol_sens_sep6: n 21, efecto 8.77 pp, IC [1.52, 18.27], p 0.1096
- vol_sens_racha: n 12, efecto 4.33 pp, IC [-5.4, 13.02], p 0.495
- vol_sens_vix_1990: n 5, efecto -2.37 pp, IC [-9.45, 25.97], p 0.814
- dolar_sens_u05: n 8, efecto -4.94 pp, IC [-18.07, 9.06], p 0.4884

Detalle completo (todas las combinaciones, fechas de cada evento): `research/int/int14_resultado.json`.
