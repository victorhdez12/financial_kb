---
documento: INT-9 fase 1 — factores comunes y clusters de los indicadores ("sin mirar resultados")
fecha: 2026-10-30
estado: DESCRIPTIVO. Ningún contraste, ningún objetivo cruzado con un factor. Base del borrador INT9_prerregistro_v0.md
procedencia: scripts/int9_fase1.py, commit 55075f6 (árbol limpio), 2026-10-30T06:43:23Z, semilla 20261030 → research/int/int9_fase1.json
datos: JST ≤ 2004, 14 países del núcleo, 1870-2004 (sin guerras 1914-18 / 1939-45 ni hiperinflación); OCDE mensual "as of" 1961-2004. Nada ≥ 2005
literatura: docs/research/2026-10-23_autoencoders_relaciones_ocultas.md (DFM/PCA lineal antes que autoencoder; descubrimiento con división interna)
---

# INT-9 fase 1: ¿qué estructura común tienen los indicadores?

## 0. En una frase
Hay **dos factores globales sólidos** en 130 años de 14 países: **F1, un "factor nominal mundial"** (años de inflación
alta en todas partes, tipo real negativo, tipos largos subiendo) y **F2, unas "condiciones financieras mundiales"**
(bolsas subiendo, tipos largos bajando, curva empinada). Un tercero existe en la muestra completa pero **no es estable**.
Los países forman un **gran bloque** (10 de 14) con Iberia, Japón y Finlandia aparte; los **factores regionales son
débiles** (apenas por encima del azar). Para la fase 2 la potencia solo alcanza para efectos **grandes** (≈ el tamaño
de lo ya establecido en X1).

## 1. Qué se hizo (y qué no)
- **Indicadores (X), 8 por país-año:** crecimiento del PIB real, inflación, Δ crédito/PIB, curva (largo − corto), tipo
  real corto, Δ tipo largo, bolsa real del año y vivienda real del año (los dos últimos son el *pasado* en t + 1, no un
  objetivo). Winsorización 1/99 conjunta. Variante "solo macro" (6, sin rentabilidades) como sensibilidad.
- **Métodos** (todos lineales, como recomienda la nota de literatura): PCA con huecos por EM (Stock-Watson) sobre la
  matriz años × (país·indicador) = 123 años × 112 columnas (92,6 % de celdas con dato) → factores **globales**;
  PCA de los indicadores dentro de cada país → estructura **entre indicadores**; clusters jerárquicos (enlace medio,
  1 − correlación) de países y de indicadores; factores **regionales** = PC1 de los residuos dentro de cada cluster,
  comparado con grupos de países al azar.
- **Número de factores:** Bai-Ng (IC_p1/p2/p3), autovalores (scree) y análisis paralelo de Horn.
- **Estabilidad:** dos mitades (1871-1949 / 1950-2004) y bootstrap de bloques móviles de 10 años (300 réplicas).
- **Decisiones fijadas antes de mirar:** describir R = 3 factores; cortar dendrogramas en 4 grupos de países y 3 de
  indicadores; semilla fija.
- **NO se hizo:** ninguna correlación ni regresión de un factor con recesiones o rentabilidades futuras. La potencia
  (§6) usa objetivos **sintéticos** con propiedades de Y medidas por separado (tasa de eventos, agrupamiento por año,
  dispersión de la bolsa).

## 2. ¿Cuántos factores?

| criterio | resultado | lectura |
|---|---|---|
| Autovalores (cuota de la varianza) | 15,9 % · 9,3 % · 6,2 % · 4,7 % · 4,6 % … | codo claro tras el 2.º-3.º |
| Bai-Ng IC_p2 (el habitual) | **3** (IC_p1 5; IC_p3 8, conocido por sobrestimar) | 3 en la muestra completa |
| Bai-Ng IC_p2 en mitades | 4 (1871-1949) / 3 (1950-2004) | |
| Bai-Ng IC_p2 en bootstrap | 3: 2 %, 4: 16 %, 5: 29 %, 6: 53 % | **inestable** (los bloques repetidos inflan el número) |
| Análisis paralelo | 10 | sobreestima con series autocorrelacionadas; no informativo aquí |

**Conclusión:** 2 factores robustos; el 3.º se describe pero no se usa (ver §4). Con guerras dentro: también IC_p2 = 3 y
F1 casi igual (cuota 16,8 %).

## 3. Interpretación económica (cargas medias por indicador sobre los 14 países)

| indicador | F1 | F2 | F3 |
|---|---|---|---|
| inflación | **+0,73** | +0,05 | −0,20 |
| tipo real corto | **−0,70** | −0,15 | +0,02 |
| Δ tipo largo | +0,35 | **−0,46** | +0,21 |
| crecimiento PIB | +0,29 | +0,17 | +0,31 |
| curva | +0,17 | +0,31 | +0,23 |
| bolsa real | −0,20 | **+0,46** | +0,01 |
| vivienda real | −0,13 | +0,04 | +0,26 |
| Δ crédito/PIB | −0,14 | +0,02 | +0,14 |

- **F1 — factor nominal mundial (16 % de la varianza).** Sube cuando la inflación sube en todos los países a la vez y
  los tipos reales caen (el tipo nominal no sigue a los precios), con tipos largos subiendo y activos reales sufriendo.
  Explica el 47 % de la inflación y el 42 % del tipo real de cada país, y casi nada del crédito (4 %) o de la vivienda
  (3 %). Años más altos: 1920, 1974, 1951 (Corea), 1919, 1975-76; más bajos: 1921-22 (deflación de posguerra), 1931,
  1870s. **Aviso mecánico:** inflación, tipo real y rentabilidades reales comparten el IPC; parte de F1 es contable
  (un año de inflación alta baja por definición el tipo real y la bolsa real).
- **F2 — condiciones financieras mundiales (9 %).** Bolsas reales al alza, tipos largos a la baja, curva empinada y algo
  de crecimiento: un "risk-on" mundial con bajada de tipos. Altos: 1983, 1996-97, 1993, 1986; bajos: 1974, 1990, 1931,
  1980-81, 1920. Se parece a un **factor de ciclo financiero** clásico (Miranda-Agrippino y Rey, a escala anual).
- **F3 — actividad real / vivienda (6 %).** Crecimiento, vivienda, crédito y algo de curva. **Inestable**: en la
  primera mitad su congruencia con la muestra completa es 0,36 y en el bootstrap la mediana es 0,63. **No usar.**
- **Dentro de cada país** (PCA de los 8 indicadores, filas país-año): P1 (27 %) es el mismo eje nominal (inflación
  −0,89, tipo real +0,87, bolsa/vivienda/crédito ≈ +0,4); P2 (18 %) es bolsa + curva + crecimiento − Δ tipo largo (como
  F2); P3 (15 %) vivienda + crecimiento + Δ tipo largo. En 13 de 14 países el P1 propio coincide con el común
  (congruencia 0,76-0,98). El P1 propio de cada país **está muy correlacionado con F1** (−0,68): no es un factor distinto.
- **Solo macro (sin bolsa ni vivienda):** F1 sale igual (cuota 20 %, congruencia bootstrap 0,96); F2 cambia de
  significado (Δ tipo largo − curva) y es menos estable (0,45 en la primera mitad). F2 necesita la bolsa.
- **Contraste con la OCDE mensual (1961-2004, otro conjunto de datos):** el PC1 entre países explica el 73 % de la
  inflación interanual y el 42 % de la producción industrial; el primer factor mensual, promediado por año, tiene
  correlación |0,71| con F1 anual en los 44 años comunes. F1 **se reproduce** con datos independientes.

## 4. Estabilidad

| | F1 | F2 | F3 |
|---|---|---|---|
| congruencia 1871-1949 vs todo | 0,90 | 0,74 | 0,36 |
| congruencia 1950-2004 vs todo | 0,83 | 0,75 | 0,81 |
| bootstrap: mediana (p10) | 0,94 (0,80) | 0,90 (0,77) | 0,63 (0,24) |
| bootstrap: % réplicas ≥ 0,85 | 82 % | 69 % | 11 % |
| cuota (IC 90 % bootstrap) | 17 % (15-20) | 10 % (8,5-12) | 7,6 % (6-9) |

Congruencia de Tucker: 1 = mismas cargas; ≥ 0,85 se suele leer "el mismo factor", 0,65-0,85 "parecido". **F1 es
estable, F2 razonablemente estable, F3 no.** Lo "global" de cada variable crece en 1950-2004 (PC1 entre países del
crecimiento: 27 % → 43 %; inflación 43 % → 69 %), salvo la curva (42 % → 27 %, patrón oro antes de 1914).

## 5. Clusters

- **Países (bloques de 8 indicadores, correlación media 0,31):** {BEL, DEU, DNK, FRA, GBR, ITA, NLD, NOR, SWE, USA},
  {ESP, PRT}, {FIN}, {JPN}. Bootstrap: dos países del bloque grande caen juntos el 84 % de las veces; de clusters
  distintos, el 6 %. Entre mitades el índice de Rand ajustado es 0,53 (cada mitad frente al total 0,76): la
  periferia (Iberia, Japón, a veces Finlandia/Noruega) cambia, el núcleo no.
- **Regional (tras quitar 3 factores globales):** aparecen {DNK, FIN, NOR, SWE} (nórdicos), {BEL, DEU, FRA, GBR, ITA,
  NLD, USA}, {ESP, PRT}, {JPN}. Pero el PC1 dentro de cada cluster explica casi lo mismo que en grupos al azar:
  nórdicos 10,9 % frente a 11,1 % (p 0,57), Iberia 17,1 % frente a 16,2 % (p 0,27), núcleo 10,0 % frente a 8,8 %
  (p 0,015, sin corrección y 1 de 3). **Los factores regionales son débiles: no compensa modelizarlos.**
- **Indicadores** (1 − |r| dentro de país): {crecimiento, inflación, crédito, tipo real, vivienda}, {Δ tipo largo,
  bolsa}, {curva}. **Inestables** entre mitades (Rand ajustado 0,25): no sirven para agrupar variables.

## 6. Potencia para la fase 2 (objetivos sintéticos; ningún factor cruzado con ningún objetivo)

**Cómo:** se toman las filas reales (país, t) de cada objetivo y los valores reales del factor en ellas (solo X). Se
generan objetivos falsos con un efecto plantado β y con propiedades de Y medidas aparte: tasa de entradas en recesión
16,7 % (220 en 1.314 filas) y su agrupamiento por año (sobredispersión 2,5 → choque común de año σ_u = 1,2); bolsa
real con dt común entre años 13,0 pp y propia 17,7 pp. Contraste: el previsto en la fase 2, con su valor crítico
**simulado bajo la nula** y α = 0,05/3 (Holm con 3, peor caso). 400 réplicas por punto.

| contraste (simulado) | MDE al 80 % | traducción |
|---|---|---|
| F1 → entrada en recesión t+1 (ΔAUC estratificada, dejando un país fuera) | odds ratio ≈ 1,7 por dt (β 0,5-0,6) | ΔAUC ≈ +0,12-0,13 |
| F2 → entrada en recesión t+1 | odds ratio ≈ 1,65 por dt | ΔAUC ≈ +0,11 |
| P1 propio → entrada en recesión t+1 | odds ratio ≈ 1,5 por dt | ΔAUC ≈ +0,09 |
| F1 → recesión **sobre S4** (X1 ya establecido; corr F1-S4 −0,37) | odds ratio ≈ 1,7 por dt | ΔAUC incremental ≈ +0,04-0,05 |
| F1 → bolsa real t+1 (DK, efectos de país) | ≈ 4,5 pp por dt | |
| F2 → bolsa real t+1 | ≈ 4,5-5 pp por dt | |
| P1 propio → bolsa real t+1 | ≈ 3,5 pp por dt | |

**Lectura.** (a) En recesiones solo se detectaría un efecto del tamaño de X1 (ΔAUC +0,12, el más fuerte que tiene el
proyecto). (b) En bolsa, el MDE (4-5 pp por dt) es el doble de lo que dio la valoración en INT-7 (2-3 pp): la bolsa
está **infrapotenciada** y debería ser informativa. (c) Simplificaciones declaradas: factor con cargas de toda la
muestra (en la fase 2 se recomienda ajuste cruzado, que añade ruido); sin el listón B1 en el generador; sin sesgo de
Stambaugh en la bolsa (INT-7 mostró que puede importar). Por todo ello el MDE real es algo **peor**.

## 7. Avisos
- 1870 tiene pocas celdas (todo lo que es una diferencia empieza en 1871) y su puntuación de F1 (−3,7) es un artefacto
  de la imputación: en la fase 2, exigir cobertura mínima por año.
- F1 contiene una parte contable (IPC en tres de sus variables). Es honesto llamarlo "nominal", no "riesgo".
- P1 propio ≈ −F1: no son dos ideas, es una.
- Contaminación: las cargas se han visto con todo 1870-2004; los objetivos no. La fase 2 no está "limpia" de X, solo de Y.
