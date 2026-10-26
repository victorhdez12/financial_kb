---
documento: INT-2 — cálculo de potencia del mapa régimen → activos (panel anual)
version: 0.2 (2026-10-27) — rehecho tras el Validador (G anual alineada con la v1.1; MDE con corrección de Kish y placebo)
fuente: scripts/int2_potencia.py → research/int/int2_potencia.json
---

# INT-2: potencia (antes de construir INT-3)

Solo con cuántos país-años hay en cada estado (etiquetas de INT-1, 14 países del núcleo, sin años truncados) y con
estadísticos **incondicionales** de las rentabilidades reales anuales de JST (≤ 2004). No se ha cruzado ninguna
rentabilidad con ningún régimen. Efecto de diseño por agrupación en años (correlación media entre países en el mismo
año) y corrección por autocorrelación. MDE = diferencia mínima detectable de rentabilidad real media anual entre un
estado y el resto (80 % de potencia, bilateral 5 %).

| estado | país-años 1870-2004 | MDE bolsa | MDE bonos | MDE letras | MDE vivienda |
|---|---|---|---|---|---|
| expansión | 661 | 6,1 pp | 4,6 pp | 4,8 pp | 2,5 pp |
| sobrecalentamiento | 283 | 6,9 | 5,2 | 5,3 | 3,1 |
| estanflación | 314 | 6,8 | 5,1 | 5,3 | 2,9 |
| crecimiento bajo | 478 | 6,3 | 4,7 | 4,9 | 2,7 |
| recesión (años de pico a valle) | 406 | 6,6 | 4,9 | 5,1 | 2,8 |

Solo 1950-2004 (más parecido al mundo actual): bolsa ≈ 11,5-14 pp, bonos ≈ 5-6 pp, letras ≈ 3,5-4 pp, vivienda ≈ 4-5 pp.

**Comparación:** con EE. UU. solo (fase de factores) hacían falta 15-19 pp en bolsa. El panel internacional reduce el umbral
a ≈ 6-7 pp con toda la historia.

**Lectura:**
- Con 1870-2004 **sí hay potencia para los efectos grandes** que describe la literatura (del orden de −5 a −10 pp reales en
  bolsa y bonos en episodios de inflación alta; protección de los bonos en recesiones desinflacionistas). Los efectos de
  2-3 pp en bolsa no se pueden distinguir del ruido.
- Con 1950-2004 solo, la bolsa necesita efectos de > 11 pp: el periodo moderno solo sirve para contrastar, no para estimar
  la bolsa por sí solo. Bonos, letras y vivienda aguantan mejor.
- Las correlaciones entre países son la clave: en bolsa ≈ 0,31 (1870-2004) y 0,38 (1950-2004); en bonos 0,41-0,51. Un
  modelo jerárquico no crea información nueva, pero reparte bien la que hay.

**Consecuencias para el prerregistro de INT-3:**
1. Estimación principal con **1870-2004** (núcleo), contraste con 1950-2004.
2. Preguntas limitadas a **efectos grandes** con mecanismo (bolsa y bonos en estanflación y sobrecalentamiento; bonos en
   recesión desinflacionista; letras reales en inflación alta; vivienda como contraste).
3. Inferencia agrupada por año; resultados en real y por activo; los países de prueba (AUS, CHE, CAN, IRL) para comprobar
   fuera de muestra.
4. El periodo bloqueado (2005-2020 en JST) queda para la evaluación única.

## v0.2 (27-oct, tras el Validador `docs/validation/2026-10-27_int1_int2.md`)
Rehecho con la G anual corregida (nivel frente a tendencia) y con dos MDE más (commit de la ejecución en
`research/int/int2_potencia.json` → `procedencia`). Bolsa real, 1870-2004 (analítico / con corrección de Kish por la
variación de países por año / placebo con regímenes desplazados ≥ 6 años):

| estado | país-años | MDE bolsa | Kish | placebo | bonos (Kish) | letras (Kish) | vivienda (Kish) |
|---|---|---|---|---|---|---|---|
| expansión | 573 | 6,2 | 6,7 | 4,9 | 5,1 | 5,2 | 2,6 |
| sobrecalentamiento | 324 | 6,8 | 7,7 | 5,9 | 5,8 | 5,9 | 3,1 |
| estanflación | 273 | 7,0 | 7,7 | 6,0 | 5,8 | 6,0 | 3,3 |
| crecimiento bajo | 566 | 6,2 | 6,7 | 5,4 | 5,1 | 5,2 | 2,7 |
| recesión | 406 | 6,6 | 7,3 | 5,1 | 5,5 | 5,6 | 3,0 |

**Lectura corregida (más prudente que la v0.1):**
- Referencia para INT-3: el **MDE de Kish** (el mayor de los tres). Con varios contrastes hay que multiplicarlo:
  × 1,24 con 6 contrastes, × 1,38 con 20 → bolsa ≈ **8-10 pp**, bonos y letras ≈ 6-8 pp, vivienda ≈ 3,5-4,5 pp.
- **"Hay potencia" solo para efectos grandes:** con un MDE de ≈ 7 pp, un efecto verdadero de 5 pp se detecta con
  probabilidad ≈ 0,5. Los efectos de la literatura en episodios de inflación alta (−5 a −10 pp reales) están en el límite.
- Además (Validador): las correlaciones entre países suben en las crisis (que caen en recesión y estanflación) y hay años
  extremos (guerras, hiperinflaciones) con mucho peso → el MDE real puede ser algo mayor. INT-3 tendrá que usar inferencia
  robusta (agrupada por año) y una sensibilidad sin los años de guerra.
- Consecuencia: el prerregistro de INT-3 debe tener **pocos contrastes** (≤ 6), elegidos por mecanismo, no 20.
