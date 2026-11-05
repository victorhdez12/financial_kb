---
documento: INT-11 v4-correlaciones — borrador v0 (diseño + potencia; SIN puerta, SIN prerregistro congelado)
fecha: 2026-11-05
estado: borrador para decisión del usuario
script: scripts/int11_v4_potencia.py (commit 4ea97f8, árbol limpio) → research/int/int11_v4_potencia.json
datos: solo ≤ 2004 (load_dev; JST anual 14 países del núcleo + sensibilidad con 18; OCDE mensual 1957-2004). Nada ≥ 2005 leído.
---

# INT-11 v4-correlaciones: ¿debe el motor hacer que la correlación entre activos dependa del régimen?

## 0. Resumen
1. **v3 ya condiciona la dependencia al régimen, de forma implícita.** El motor no usa una correlación fija ni una
   cópula: sortea **filas completas** país-año (bolsa, bonos, letras, vivienda, oro, inflación y crecimiento a la vez)
   dentro de la celda de transición (s_{t−1}, s_t). Por eso la correlación de sus escenarios ya cambia con el régimen:
   bolsa-bonos ≈ 0,10-0,26 partiendo de expansión y ≈ 0,39-0,52 partiendo de sobrecalentamiento (4 países, §1.2).
2. **Descriptivo ≤ 2004:** la correlación bolsa-bonos es mayor con inflación alta (0,435 frente a 0,179; Δ = +0,26,
   IC 90 % [+0,12; +0,40]; 12 de 14 países con el mismo signo; también en OCDE mensual, Δ = +0,20 [+0,09; +0,30], 11/12).
   Bonos-oro: negativa con inflación alta (−0,28) y ≈ 0 o positiva con inflación baja (IC muy ancho; solo 1972-2004).
   Bolsa-vivienda y bolsa-oro: sin diferencia por régimen.
3. **Potencia:** pasar de una correlación fija a una por régimen mejora las puntuaciones de la distribución conjunta
   **muy poco** (energy score +0,013 % con la Δ observada) y **no se puede demostrar**: con la Δ medida (0,26) la
   potencia es 0,19 (energy score) y ≤ 0,04 (CRPS de la 60/40). **MDE (80 %, LOCO ≤ 2004): Δρ ≈ 0,70** en energy
   score (2,7 veces la observada); CRPS de la 60/40 y Brier de caída de la 60/40: **sin potencia** en toda la rejilla
   (hasta Δρ = 0,77). En el bloqueado hipotético (2005-2020) la potencia no pasa de 0,48.
4. **Veredicto / recomendación:** **no construir una v4 de correlaciones paramétrica** ni gastar una puerta en ella.
   Lo que sí merece un arreglo pequeño (ingeniería, sin puerta propia) es la **imputación independiente** de activos
   sin dato (oro antes de 1972, el 70 % de las filas; vivienda, el 17 %), que diluye la dependencia del oro y de la
   vivienda con el resto, y documentar la dependencia por régimen como **descriptiva** en la salida "hoy".

## 1. Cómo trata v3 la dependencia entre activos
### 1.1 Mecanismo (src/intl/escenarios.py, `Generador._lote`, `_valores_v2`)
- **Bootstrap de filas completas por celda (s_{t−1}, s_t)** con respaldo jerárquico si la celda tiene < 25 filas: la
  dependencia contemporánea entre activos y con la macro se conserva **sin modelizarla** (diseño v1, §"conserva la
  dependencia conjunta"). Como la celda depende del régimen, la dependencia también: es una "correlación por régimen"
  no paramétrica, sin encogimiento explícito (la celda (·, j) o el todo actúan de respaldo).
- **Bloques** (continuación con prob. 1 − 1/3 si el régimen casa) y **peso bayesiano por año** común a todos los
  países: conserva parte de la autocorrelación y de la dependencia entre países.
- **Lo que la rompe o la diluye:**
  (a) **huecos**: un activo sin dato en la fila sorteada se rellena con un **donante independiente** de la misma celda
      (`_valores_v2`, `donantes`) → oro (70 % de las filas sin dato, todo antes de 1972) y vivienda (17 %) salen
      independientes del resto en esas trayectorias;
  (b) **suavizado** (ruido t5 de varianza c/n·var, c = 5,25) **independiente entre activos**: atenúa la correlación
      por un factor ≈ 1/(1 + c/n) (≈ 0,83 en una celda de 25 filas, ≈ 0,95 con 100); en la práctica casi no se ve (§1.2);
  (c) **factor de país por activo** sorteado por lote y de forma independiente entre activos: cambia escalas, no el
      signo de la dependencia.
- El modo paramétrico "t" (no usado en v3) sí tiene una covarianza por celda encogida hacia la del pool (n0_cov = 30).
- La pertenencia suave de v3 mezcla regímenes de partida → la dependencia de la predictiva es la mezcla de la de las
  celdas, como debe ser.

### 1.2 La salida del motor (descriptivo; `D_motor_v3`, sin comparar con resultados)
Correlación (log) en 10 000 sorteos a 1 año, motor ajustado con todas las filas ≤ 2004:

| país | partida | bolsa-bonos | bonos-oro | bolsa-vivienda |
|---|---|---|---|---|
| USA | expansión | 0,11 | −0,02 | 0,09 |
| USA | sobrecalentamiento | 0,45 | −0,18 | 0,12 |
| DEU | expansión / sobrecal. | 0,15 / 0,42 | −0,08 / −0,18 | 0,05 / 0,06 |
| GBR | expansión / sobrecal. | 0,22 / 0,50 | −0,04 / −0,20 | −0,04 / 0,01 |
| ESP | expansión / sobrecal. | 0,22 / 0,48 | −0,09 / −0,12 | 0,08 / 0,13 |
| filas crudas s_{t−1} | expansión / sobrecal. | 0,22 / 0,46 | 0,02 / −0,26 (n 168 / 291) | 0,11 / 0,12 |

Sin suavizado las cifras casi no cambian (±0,03): la atenuación (b) es despreciable. La de bonos-oro sí está diluida
(−0,26 en las filas con oro frente a −0,12/−0,20 en los sorteos): efecto de (a).

## 2. Descriptivos ≤ 2004 (publicables: no son un contraste)
Correlación de los **choques** (log 1 + r real, menos la media del país dentro del estado), agrupada; IC 90 % por
bootstrap de años (1000 réplicas; todas las filas de un año juntas). Núcleo de 14 países sin guerras ni hiperinflación
(misma carga que el motor). Estados: P3 = régimen operable del motor (π_t > 3 %), P3 previo = conocido al empezar el año,
INT-3 = cuadrante ex post de INT-1 (relativa + 2 %, ventanas centradas: **no PIT**).

| par | estado | ρ baja / alta | Δ (alta − baja) [IC 90 %] | países mismo signo |
|---|---|---|---|---|
| bolsa-bonos | incondicional | 0,371 | | |
| bolsa-bonos | P3 inflación del año | 0,179 / 0,435 | **+0,26 [+0,12; +0,40]** | 12/14 |
| bolsa-bonos | P3 inflación previa | 0,235 / 0,448 | +0,21 [+0,09; +0,33] | 12/14 |
| bolsa-bonos | INT-3 inflación (ex post) | 0,221 / 0,467 | +0,25 [+0,12; +0,37] | 12/14 |
| bolsa-bonos | INT-3 crecimiento bajo / alto | 0,464 / 0,310 | −0,15 [−0,28; −0,02] | 9/14 |
| bolsa-vivienda | P3 inflación del año | 0,145 / 0,094 | −0,05 [−0,16; +0,06] | 9/14 |
| bonos-vivienda | P3 inflación del año | 0,025 / 0,145 | +0,12 [−0,01; +0,27] | 7/14 |
| bonos-oro (1972-) | P3 inflación del año | 0,101 / −0,277 | −0,38 [−0,74; +0,05] | 4/4 |
| bonos-oro (1972-) | INT-3 crecimiento bajo / alto | 0,146 / −0,404 | −0,55 [−0,77; −0,25] | — |
| bolsa-oro (1972-) | P3 inflación del año | −0,049 / −0,052 | ≈ 0 | |

- **Cuadrante INT-3 (4 estados), bolsa-bonos:** expansión 0,19, sobrecalentamiento 0,31, **estanflación 0,59**
  [0,48; 0,67], crecimiento bajo 0,24. La correlación alta se concentra en la estanflación (inflación alta + crecimiento
  bajo), coherente con un choque común de tipos/inflación que hunde bolsa y bonos a la vez.
- **18 países:** mismas cifras (Δ bolsa-bonos +0,24 [+0,11; +0,38], 13/16).
- **Subperiodos (P3):** bolsa-bonos Δ = +0,21 antes de 1950 y +0,27 en 1950-2004 (mismo signo); **1998-2004**: ρ
  −0,16 con inflación baja (solo 6 filas con inflación alta). Bonos-oro: la diferencia por régimen se concentra en
  1950-1997 (inflación baja +0,43, alta −0,28; n baja = 93).
- **OCDE mensual 1957-2004** (12 países; nominal; bolsa suavizada por la media mensual): ρ 0,137 (inflación as-of
  ≤ 3 %) / 0,335 (> 3 %), Δ +0,20 [+0,09; +0,30], 11/12 países. Por décadas, Δ > 0 en los 70, 80 y 90; **en 2000-2004
  ρ ≈ −0,17 / −0,11 en los dos estados**: el cambio a correlación negativa de principios de siglo aparece como una
  época, no como un régimen de inflación (con inflación baja en las dos épocas).

### 2.1 Cambios estructurales (descriptivo)
Serie anual c_t = media entre países de z_bolsa·z_bono (su media es la correlación agrupada):
- sup-F de un cambio de media = 3,74 (año 1973; 0,27 antes, 0,56 después), por debajo del valor crítico asintótico
  de Andrews al 5 % (≈ 8,85); p por bootstrap de bloques de 5 años = 0,54. **Sin cambio estructural demostrable.**
- Quitando el efecto medio del régimen de inflación, sup-F baja a 1,75 (p 0,88): buena parte del "salto" de 1973 es
  el paso a inflación alta.
- Media móvil de 20 años: ≈ 0,2 hasta 1910, ≈ 0,45-0,5 en entreguerras, ≈ 0,15-0,3 en 1950-1972, **0,55-0,71 en
  1977-1992**, 0,34 en 2002 (bajando). Por país, el máximo F está en 1974 en ESP, PRT, DNK, NOR (supF 9-10 en ESP/PRT,
  sin corregir por multiplicidad) y en 1986-1987 en DEU y SWE.

## 3. Diseño de una v4-correlaciones (lo que habría que prerregistrar si se hiciera)
Opción paramétrica (la que se ha evaluado en potencia):
- Marginales como v3; dependencia por **cópula t** con matriz R_s por estado de inflación del año (2 estados: el eje de
  crecimiento P3 tiene solo 85 filas con brecha < 0), encogida hacia la agrupada: R_s = (n_s R̂_s + n0 R̄)/(n_s + n0),
  n0 = 30. Predictiva = mezcla sobre s_t con P(s_t | s_{t−1}) (lo que el motor conoce).
- Contraste en desarrollo (≤ 2004; contaminado por estos descriptivos → solo desarrollo): LOCO, energy score de
  (bolsa, bonos) como principal, CRPS de la 60/40 y log score como secundarios, DM unilateral por años; confirmación
  solo en la fase C única, con su Holm.

Opción no paramétrica (la de v3, mínima): mantener el bootstrap de filas (ya es "por régimen") y arreglar la
imputación: el activo sin dato se sortea **condicionado** a los activos con dato de la fila (vecino más próximo en
(bolsa, bonos) dentro de la celda, o regresión + residuo de la celda), o bien restringir los escenarios con oro al
pool ≥ 1972 y declararlo.

## 4. Potencia (`E_potencia`; 200 réplicas por punto, semilla 20261105)
**Verdad sintética** con la estructura real ≤ 2004: las 1484 filas con bolsa y bonos del núcleo, su régimen observado
(41,5 % de inflación alta; P(alta | alta previa) = 0,72, P(alta | baja previa) = 0,19), medias y dt por estado, efecto
país (dt 1,9 pp / 0,75 pp), parte común del año (ICC 0,39 / 0,42), colas t5. Correlación verdadera
R_s(λ) = R̄ + λ(R̂_s − R̄) con R̄ = 0,323, R̂ = 0,179 / 0,435 (λ = 1 = lo medido; λ = 0 = nulo de correlación fija).
**Modelos:** M_fija (R̄ del entrenamiento) frente a M_reg (encogida, n0 = 30); mismas marginales; números aleatorios
comunes. **Diseños:** LOCO por país (principal), LOCO con el régimen del año conocido (oráculo: cota superior) y
bloqueado hipotético (entrena ≤ 2004; prueba 16 años × 14 países con 15 % o 30 % de inflación alta **supuesta**).

| Δρ verdadera (λ) | potencia ES | mejora ES | potencia CRPS 60/40 | potencia log score | potencia Brier 60/40 ≤ −15 % |
|---|---|---|---|---|---|
| 0 (0) | 0,01 | 0,000 % | 0,01 | 0,11 | 0,02 |
| 0,13 (0,5) | 0,06 | 0,003 % | 0,03 | 0,01 | 0,01 |
| **0,26 (1, observado)** | **0,19** | **0,013 %** | **0,04** | 0,01 | 0,02 |
| 0,38 (1,5) | 0,38 | 0,030 % | 0,06 | 0,07 | 0,00 |
| 0,51 (2) | 0,61 | 0,056 % | 0,06 | 0,23 | 0,01 |
| 0,77 (3) | 0,87 | 0,12 % | 0,12 | 0,78 | 0,01 |

- **MDE (potencia 0,8, LOCO):** energy score Δρ ≈ **0,70** (λ ≈ 2,7); CRPS de la 60/40, log score y Brier: no se
  alcanza en la rejilla. **Oráculo** (régimen del año conocido, imposible en tiempo real): ES Δρ ≈ 0,40, log score
  Δρ ≈ 0,43; CRPS de la 60/40 sigue sin potencia (0,51 en Δρ = 0,77).
- **Magnitud práctica:** con la Δ observada, la mejora del energy score es del 0,013 % y la del CRPS de la 60/40 del
  0,009 %: aunque se pudiera demostrar, no movería ninguna decisión. La razón: en la 60/40 la covarianza bolsa-bonos
  aporta poco a la varianza (0,48·ρ·σ_b·σ_o frente a 0,36·σ_b²): pasar de ρ 0,32 a 0,44 sube la dt de la cartera
  ≈ 3 % en inflación alta.
- **Cobertura p5-p95 de la 60/40 por estado:** inflación baja 0,92 / alta 0,85-0,86 con los **dos** modelos (M_reg
  +0,4 pp en alta con la Δ observada). La infracobertura en inflación alta viene de las marginales y de no conocer el
  régimen del año, no de la correlación (con oráculo los dos dan 0,89-0,90).
- **Bloqueado hipotético:** potencia ES 0,18-0,31 con la Δ observada, ≤ 0,49 con Δρ 0,77; el tamaño con λ = 0 es
  0,08-0,13 (16 conglomerados de año: el DM sale algo liberal; habría que corregirlo con t de pocos conglomerados o
  bootstrap si se usara).

## 5. Veredicto
- La dependencia por régimen **existe** en los datos ≤ 2004 (bolsa-bonos, y probablemente bonos-oro) y **v3 ya la
  reproduce** por construcción.
- Hacerla explícita (paramétrica) **no tiene potencia** ni con ≤ 2004 ni con el bloqueado, y su efecto en las
  métricas conjuntas que importan (cartera 60/40) es despreciable. Por la regla "potencia antes de construir": **no se
  construye v4-correlaciones** como modelo nuevo ni se le dedica una puerta.
- El riesgo real para la distribución conjunta futura no es el régimen sino la **época**: la correlación bolsa-bonos se
  volvió negativa en 1998-2004 con inflación baja, y el motor, con semivida 50 años, en inflación baja da ≈ +0,1-0,2.
  Eso no se puede contrastar con ≤ 2004 (5-7 años) y es una pregunta para la fase C o para el registro en vivo.

## 6. Decisiones pendientes (usuario)
| # | decisión | opciones | recomendación |
|---|---|---|---|
| V1 | construir v4-correlaciones paramétrica | sí (prerregistro + puerta) / **no** | **no** (MDE ≈ 2,7 veces la Δ observada; mejora < 0,02 %) |
| V2 | arreglar la imputación independiente (oro < 1972, vivienda) | **imputación condicionada** / pool ≥ 1972 para escenarios con oro / dejarlo | **imputación condicionada**, como cambio de ingeniería declarado; obliga a serie nueva del registro en vivo y no se evalúa con ≤ 2004 (contaminado) |
| V3 | publicar la dependencia por régimen en la salida "hoy" | **sí, descriptiva** (tabla §2 + la del motor §1.2) / no | **sí**, con "≤ 2004, no confirmado" |
| V4 | correlación negativa reciente (época) | **seguimiento descriptivo en el registro en vivo** / semivida más corta en v4 | **seguimiento**; cambiar la semivida sería minería sobre ≤ 2004 |
| V5 | crecimiento como condicionante | solo INT-3 ex post (descriptivo) / eje P3 | **solo descriptivo**: el eje P3 (brecha < 0) tiene 85 filas y el ex post no es PIT |

## 7. Contaminación y límites (declarados)
- Los descriptivos cruzan rentabilidades reales con el régimen en ≤ 2004 (permitido aquí por ser descriptivo); la
  medición de la verdad sintética usa esas mismas correlaciones → cualquier contraste futuro de v4 en ≤ 2004 sería
  **desarrollo**, nunca confirmación.
- Verdad sintética simplificada: 2 activos, 2 estados, parte común con la correlación agrupada, t5 común a la fila,
  sin bloques temporales ni escala por país; predictiva normal-t con marginales del estado agrupadas (las dos igual).
- OCDE mensual: bolsa con precio medio mensual (suavizada) y bono aproximado desde el tipo; nominal.
- sup-F por país sin corregir por multiplicidad; valor crítico asintótico con T ≈ 112 años.
