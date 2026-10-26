---
documento: Línea B — el nowcast como herramienta: diseño (potencia, candidatas, listón)
version: 0.1-borrador (2026-10-26)
estado: BORRADOR. Solo diseño: nada corrido, ninguna rentabilidad mirada para escribirlo. Candidatas sin fijar.
depende_de: docs/PLAN.md "Reconducción del proyecto (2026-10-26)"
---

# Línea B — diseño v0.1 (borrador)

**Pregunta única:** ¿la información macro adelanta el riesgo lo bastante como para mejorar el **momento de los recortes
de B1**, frente a usar solo la volatilidad? Incluye el **forecast de riesgo**: ¿anticipa, con 1 a 6 meses, subidas de
volatilidad o entradas en recesión mejor que la volatilidad reciente sola? No se le pide ganar rentabilidad. No hay
forecast del cuadrante.

## a) Potencia (datos ≤ 2004, contando episodios)

**Episodios independientes disponibles** (solo la señal, sin rentabilidades de cartera):
- Recesiones: **6** en 1963-2004 (1969-70, 1973-75, 1980, 1981-82, 1990-91, 2001); **4** desde 1975 (con oro).
- Subidas de volatilidad (volatilidad realizada mensual de EE. UU. > 1,5 × su mediana causal, tras ≥ 6 meses sin
  serlo): **18** en 1963-2004, **12-13** desde 1975. Se agrupan: varias caen dentro de las mismas recesiones.

**Efecto mínimo detectable (80 % de potencia, bilateral al 5 %)**, contraste pareado entre episodios:

| episodios K | MDE en desviaciones típicas de la diferencia | adelanto del recorte (si la dispersión entre episodios es 3 / 6 meses) | ΔAUC frente a "solo volatilidad" (AUC 0,75, correlación 0,5) | mejor p posible con la prueba de signos |
|---|---|---|---|---|
| 4 (recesiones desde 1975) | 2,1 | 6 / 12 meses | 0,27 | 0,125 (**nunca significativa**) |
| 6 (recesiones desde 1963) | 1,4 | 4 / 9 meses | 0,22 | 0,031 (solo si gana las 6) |
| 12 (subidas de vol. desde 1975) | 0,9 | 3 / 5 meses | 0,16 | — |
| 18 (subidas de vol. desde 1963) | 0,7 | 2 / 4 meses | 0,13 | — |

Traducido a las métricas de la pregunta:
- **Caída por episodio (recesiones):** la dispersión entre episodios de la diferencia B1 − B0 en la corrida registrada de
  P-DEV-FACT es ≈ 3,4 pp (episodios: 0 / 3,1 / 3,5 / 8,3 pp). Si B2 − B1 se dispersa parecido, haría falta que B2 recortara
  la caída **≈ 7 pp en cada una de las 4 recesiones** (desde 1975) o **≈ 5 pp en cada una de las 6** (desde 1963, sin
  oro). Es del orden de **todo** lo que B1 ya consigue frente a B0: improbable.
- **Volatilidad realizada:** el error típico de σ(B2) − σ(B1) en desarrollo es ≈ 0,22 pp → MDE ≈ **0,6 pp**. B1 recorta 1,7 pp
  frente a B0 en total; B2 tendría que añadir ≈ 40 % de ese efecto, moviendo los mismos 15 pp de RV.
- **Adelanto del recorte (meses):** con 6 recesiones, la señal macro tendría que adelantarse **≥ 4-9 meses de forma
  consistente**; con 12-18 subidas de volatilidad, ≥ 2-5 meses.
- **Forecast de riesgo por horizonte:** alargar h (1 → 3 → 6 meses) **no añade episodios independientes** (solo más meses
  dentro de los mismos episodios) y la asociación suele debilitarse, así que la potencia no mejora con h:
  - **entradas en recesión a 3-6 meses (K = 6): no hay potencia** salvo una mejora de AUC de ≥ 0,22, casi imposible si la
    volatilidad sola ya tiene AUC ≈ 0,75;
  - **subidas de volatilidad a 1-6 meses (K = 12-18):** solo efectos grandes (ΔAUC ≥ 0,13-0,16). Es el único sitio donde
    hay algo de margen, y es limitado.

**Conclusión (dicha claramente):** con datos hasta 2004 **no se puede demostrar** una mejora realista en la caída por
recesión ni en el forecast de recesión a 3 meses o más. Lo único que se podría distinguir son efectos grandes en la
anticipación de **subidas de volatilidad**. Para todo lo demás, **la única prueba es el paper trading, y tardará años**
(una recesión cada 6-8 años de media: varias décadas para reunir 4-6 episodios nuevos). La línea B debe asumirse como
investigación de largo plazo, no como mejora a corto.

## b) Candidatas (máximo 2-3; se fijan después, solo con propiedades de la señal)

Propuesta de familias (cada una con ≤ 1 parámetro libre, a fijar por una regla commiteada antes de calcular, como en
`scripts/factors_variantes.py`: frecuencia de alarmas ≤ 1/año, % del tiempo en alarma 10-30 %, coincidencia con las
recesiones de la etiqueta ≤ 2004; nunca rentabilidades):
1. **C1 — G del clasificador con exigencia de duración** (G < θ durante k meses). Ya conocida (V1-V3); aquí solo como
   disparador **adicional** de recorte, no sustituto.
2. **C2 — curva invertida** (T10Y3M < 0 durante ≥ k meses): indicador adelantado conocido antes de 2005
   (Estrella-Mishkin, 1996-98) → sin contaminación de diseño posterior.
3. **C3 (opcional) — probabilidad de recesión** de un probit sobre la curva, estimado solo con datos ≤ 2004 y congelado.
   Alternativa descartada por contaminación: Sahm (2019), EBP (2012), NFCI (2011).

**Cómo entrarían en B2 (propuesta):** B2 = B1 con un recorte **adicional y temprano**: RV = min(objetivo de B1, 55 %) mientras
la señal macro esté en alarma; sin alarma, B2 = B1. Así la macro solo puede **adelantar** recortes, nunca deshacer los de
la volatilidad. La desviación táctica máxima sigue en − 15 pp (RV entre 55 % y 70 %).

## c) Listón y gobierno
- **Listón: B1 tal cual** (paper trading, línea A).
- **B2** solo entra en el paper trading como **cartera en sombra**, tras un **prerregistro interno aprobado por el usuario**
  (candidatas fijadas, métricas, criterio). **B2 nunca sustituye a B1 sin una decisión registrada del usuario.**
- Métricas en sombra: caída por episodio, volatilidad realizada, adelanto del recorte en meses, falsas alarmas al año,
  rotación y costes.
- Se mantienen todas las reglas: periodo bloqueado intacto (≥ 2005-01), corte técnico en `src/factors/data.py`, etiqueta
  solo ≤ 2004, registro de todas las pruebas.

## Siguiente (pendiente del usuario)
Aprobar o ajustar este diseño → regla de selección de candidatas commiteada → selección (solo señal) → prerregistro
interno de B2 → aprobación → B2 en sombra.
