---
documento: INT-2 — cálculo de potencia del mapa régimen → activos (panel anual)
version: 0.1 (2026-10-27)
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
