---
documento: P-EVAL-INT4 — cálculo de potencia de la confirmación fuera de muestra (una sola vez) de T1 y T2 de INT-4 en el bloqueado JST 2005-2020
version: 0.1 (2026-10-29)
estado: §1-§2 commiteados (f1b8d15) ANTES del script (f8e5fe3) y de la corrida (2026-10-29T14:34Z, árbol limpio; salida research/int/peval_int4_potencia.json, 10fc87e). Bloqueado NO gastado: no se ha leído ningún indicador ni hecho ninguna predicción ≥ 2005.
depende_de: docs/int/INT4_prerregistro_v0.md (v1.0), research/int/int4_resultado.json, research/int/int4_sensibilidad_liston*.json, docs/int/INT5_diseno_v0.md §3.1
---

# P-EVAL-INT4: potencia (solo recuentos de eventos del bloqueado)

## 0. Qué se pregunta
INT-5 §3.1 propone gastar **una vez** el periodo bloqueado de JST (años objetivo 2005-2020) para confirmar fuera de
muestra los modelos T1 (entrada en recesión a 1 año) y T2 (salida) de INT-4, congelados con datos ≤ 2004. Antes de
decidir si se gasta, este documento calcula **cuánta potencia** tendría esa confirmación, contando solo eventos.

## 1. Qué se lee del bloqueado (fijado antes de leer nada)
Para contar las recesiones de 2005-2020 hace falta el **objetivo** (el PIB real per cápita), no los indicadores.
Se lee exactamente esto y nada más:

- **Series:** `jst_{iso}_rgdpmad` (PIB real per cápita, JST R6) de los 14 países del núcleo (BEL, DEU, DNK, ESP, FIN,
  FRA, GBR, ITA, JPN, NLD, NOR, PRT, SWE, USA) y de los 4 de prueba (AUS, CAN, CHE, IRL), **todos los años**
  (1870-2020). Lo ≤ 2004 ya se conocía; lo nuevo es 2005-2020.
- **Para qué:** únicamente para fechar picos y valles con la misma regla de `src/intl/regimes.recesiones_anuales`
  (convención JST) sobre la serie completa, y de ahí: entradas (pico + 1) y salidas (valle + 1) con año en 2005-2020,
  filas en riesgo de T1 (orígenes t = 2004 … 2019 fuera de recesión) y de T2 (orígenes t = 2004 … 2019 en recesión).
- **Qué sale del script:** solo años de pico, valle, entrada y salida y recuentos por país y año. **Ningún valor ni
  tasa de crecimiento del PIB** se escribe ni se imprime. El tipo de recesión (financiera/normal) **no** se calcula
  (necesitaría `crisisjst` ≥ 2005).
- **Lectura aislada:** una función del script, con consulta SQL a `obs_latest` restringida a esas 18 series
  (`load_dev` corta en 2004 por diseño; no se toca `src/intl/`). Ninguna otra serie se lee con fechas ≥ 2005.
- **Qué NO se lee nunca:** ningún indicador ≥ 2005 (ltrate, stir, tloans, gdp, cpi, eq_tr…), ni siquiera su
  disponibilidad (no se cuentan casos completos), ni `crisisjst`, ni ninguna predicción. Supuesto declarado: en
  2005-2020 los indicadores de T1/T2 están completos en el núcleo (JST R6 cubre esas variables hasta 2020); el número
  real de filas completas solo se conocerá al evaluar.
- **Comprobación de coherencia (solo ≤ 2004):** el fechado con la serie completa se compara con
  `recesiones_anuales_dev.parquet` en los eventos ≤ 2004 (puede cambiar como mucho el último valle, truncado en 2004).

## 2. Método de potencia (sin datos de indicadores)
- **Estructura real de eventos** del bloqueado (qué filas son y = 1 y en qué año) y **puntuaciones simuladas**:
  binormal, s | y ~ N(μ·y, 1) para el modelo y el listón, AUC = Φ(μ/√2), correlación del ruido modelo-listón r = 0,5,
  y un componente común por año (ICC ρ = 0 / 0,3 / 0,6) para imitar que los indicadores globales (C4, C6, S3, S4) mueven
  a todos los países a la vez.
- **Efectos de desarrollo:** T1 listón 0,55 → modelo 0,73 (ΔAUC +0,18; estratificado ≈ +0,20); T2 listón 0,58 →
  0,77 (estratificado +0,19). También la mitad del efecto (encogimiento fuera de muestra) y H0 (Δ = 0).
- **Inferencia como en INT-4:** bootstrap por bloques de año (se remuestrean años con todos sus países) sobre las
  predicciones; IC 95 % de ΔAUC; Holm sobre 2 (T1, T2).
- **Criterios alternativos:** (a) ΔAUC > 0 con IC por bloques; (b) AUC del modelo > 0,5 con IC; (c) signo de ΔAUC;
  (d) Δlog-loss < 0; (e) calibración (pendiente en [0,5; 1,5]) con el intercepto congelado de desarrollo.
- **Fórmula de referencia:** MDE de Hanley-McNeil como en `scripts/int4_potencia.py` (positivos efectivos centrales
  con efecto de diseño por año, y prudentes = años distintos con evento).
- **Sensibilidad:** sin 2020 (choque exógeno de la pandemia: se quitan las filas con año objetivo 2020).

## 3. Resultados

### 3.1 Qué se leyó y coherencia
- Solo `jst_{iso}_rgdpmad` de los 18 países (último año 2020 en todos). Fechado con la serie completa idéntico al de
  desarrollo en los 343 episodios con valle ≤ 2003 (ninguna diferencia; ningún valle truncado en 2004).
- Ningún indicador ≥ 2005, ni su disponibilidad, ni `crisisjst`, ni predicciones.

### 3.2 Eventos del bloqueado (núcleo, 14 países, orígenes t = 2004 … 2019, h = 1)

| giro | filas en riesgo | eventos | tasa base (dev) | años objetivo con evento (nº de países) | años distintos | ICC del objetivo por año |
|---|---|---|---|---|---|---|
| **T1 entrada** | 178 | **39** | 0,22 (0,15) | 2008 (10), 2009 (4), 2011 (3), 2012 (6), 2013 (2), **2020 (14)** | **6** | 0,70 |
| T1 sin 2020 | 164 | 25 | 0,15 | 2008-09 (14), 2011-13 (11) | 5 | 0,56 |
| **T2 salida** | 46 | **25** | 0,54 (0,69) | **2010 (13)**, 2012 (2), 2013 (3), 2014 (5), 2015 (2) | **5** | 0,52 |
| + AUS, CHE (T1 / T2) | 209 / 47 | 42 / 26 | — | AUS solo 2020; CHE 2009 / 2010 | 6 / 5 | — |

Por país (año de entrada en T1): BEL 2009, 2013, 2020 · DEU 2009, 2020 · DNK 2008, 2012, 2020 · ESP 2008, 2020 ·
FIN 2009, 2012, 2020 · FRA 2008, 2012, 2020 · GBR 2008, 2020 · ITA 2008, 2012, 2020 · JPN 2008, 2011, 2020 ·
NLD 2009, 2012, 2020 · NOR 2008, 2011, 2013, 2020 · PRT 2008, 2011, 2020 · SWE 2008, 2012, 2020 · USA 2008, 2020.
Salidas (T2): 2010 en 13 países tras la Gran Recesión (ESP sale en 2014 de una recesión 2008-2013); 2012-2015 las de
la crisis del euro. **La salida de 2020 cae en 2021, fuera de JST R6: 2020 no aporta nada a T2** (por eso T2 "sin 2020"
es idéntico).

Lectura: hay 39 + 25 eventos, pero **solo 6 y 5 años distintos**, y un año (2020 en T1, 2010 en T2) concentra un tercio
o la mitad. En términos efectivos, el bloqueado equivale a ≈ 4-6 eventos independientes por giro, frente a 72-84 años
distintos en desarrollo.

### 3.3 Potencia del criterio de INT-4: ΔAUC frente a B1, IC 95 % por bloques de año que excluye 0
Simulación (1.000 réplicas × 1.000 bootstrap por bloques) con la estructura real de eventos. ρ = parte común por año
del ruido de las puntuaciones (los indicadores globales C4, C6, S3, S4 mueven a todos a la vez); **ρ = 0,3 es el caso
central**, ρ = 0 es optimista (filas independientes). Tamaño bajo H0: 2-4 % (correcto).

| giro y muestra | MDE 80 %, Holm-2 (ρ = 0,3) | potencia, efecto dev, Holm-2: ρ = 0 / **0,3** / 0,6 | ídem, un solo contraste (ρ = 0,3) | potencia con la mitad del efecto (ρ = 0,3) |
|---|---|---|---|---|
| T1, ΔAUC +0,18 (0,55 → 0,73) | **0,25** | 0,86 / **0,51** / 0,36 | 0,60 | 0,17 |
| T1, estratificado +0,20 (→ 0,75) | — | 0,92 / **0,59** / 0,43 | 0,68 | — |
| T1 sin 2020, +0,18 | 0,28 | 0,69 / **0,45** / 0,34 | 0,56 | 0,15 |
| T2, ΔAUC +0,19 (0,58 → 0,77) | **0,30** | 0,51 / **0,42** / 0,38 | 0,52 | 0,14 |

- Hanley-McNeil (referencia): con positivos "prudentes" = años distintos (5-6), MDE ≈ **0,35-0,40** en T1 e
  **inalcanzable** en T2 (46 filas); con el efecto de diseño central (DE ≈ 9 en T1, 5 en T2) inalcanzable en ambos.
- **AUC estratificada por país en T2: sin potencia** (6-8 %): casi todos los países tienen una sola salida y pocas filas
  de "seguir en recesión"; no sirve como criterio en el bloqueado.
- El IC por bloques con 5-6 años con evento es ancho (± 0,15 en T1, ± 0,18-0,20 en T2 a ρ = 0,3) y poco fiable como
  aproximación (pocos bloques informativos).
- **Supuesto optimista:** la simulación da a 2020 el mismo efecto que al resto. La pandemia es un choque exógeno: si en
  2020 el modelo no discrimina (lo esperable), el efecto medio de T1 con 2020 se diluye ≈ 14/39 → ≈ +0,12 y la potencia
  cae a ≈ 0,3. Por eso T1 sin 2020 (potencia 0,45) es la muestra honesta, no la de 0,51.
- Añadir AUS y CHE apenas cambia nada (T1 0,47-0,54, T2 0,37): AUS solo aporta 2020.

### 3.4 Criterios alternativos (ρ = 0,3; potencia con el efecto de desarrollo / tasa de "pasa" bajo H0)

| criterio | T1 | T1 sin 2020 | T2 | lectura |
|---|---|---|---|---|
| (a) ΔAUC IC excluye 0, Holm-2 | 0,51 / 0,02 | 0,45 / 0,02 | 0,42 / 0,03 | moneda al aire |
| (b) AUC del modelo > 0,5, IC 95 % | 0,79 / 0,12* | 0,73 / 0,10* | 0,76 / 0,16* | más potente, pero no compara con el listón |
| (c) signo ΔAUC > 0 | 0,98 / 0,50 | 0,98 / 0,50 | 0,95 / 0,51 | **sirve para refutar, no para confirmar** |
| (d) Δlog-loss < 0 (punto) | 0,92 / 0,50 | 0,90 / 0,49 | 0,90 / 0,51 | ídem (incluye el intercepto congelado) |
| (d') Δlog-loss IC 95 % < 0 | 0,40 / 0,05 | 0,34 / 0,04 | 0,49 / 0,09 | sin potencia |
| (e) pendiente de calibración en [0,5; 1,5] | 0,73 / 0,20 | 0,72 / 0,20 | 0,60 / 0,21 | discrimina poco; 1 de cada 4 modelos bien calibrados falla |
| INT-4 completo: (a) + (d) + (e) | **0,35** | **0,31** | **0,24** | casi seguro "no confirmado" aunque funcione |

\* Bajo H0 de (b) el modelo tiene la AUC del listón (0,55 / 0,58), no 0,5: por eso "pasa" el 10-16 %. MDE de (b): AUC del
modelo ≥ 0,73 (T1) y 0,78 (T2) para el 80 %.

Interpretación de (c) como **prueba de refutación**: si el efecto de desarrollo es real, P(ΔAUC ≤ 0) ≈ 2 % (T1) y 5 %
(T2); si no hay efecto, 50 %. Un signo negativo multiplica por ≈ 10-25 la verosimilitud de "no funciona"; un signo
positivo solo por ≈ 2 la de "funciona". Es asimétrica, pero es lo único que el bloqueado puede decir con fiabilidad.

## 4. Recomendación

**No gastar el bloqueado ahora como "confirmación"**: con el criterio de INT-4 la potencia es ≈ 0,45-0,51 en T1 (0,3 si
2020 no es predecible) y ≈ 0,42 en T2; con el paquete completo (a)+(d)+(e), ≈ 0,24-0,35. Lo más probable es un "no
confirmado" que no distinguiría "no funciona" de "no hay datos", y el bloqueado se habría gastado. La MDE (0,25-0,30) está
por encima de lo que INT-5 §3.1 fijó como umbral para que valiera la pena (> 0,20 → decide el usuario; aquí se supera).

Qué hacer:
1. **Prerregistrar ya (sin correr) el criterio de P-EVAL-INT4 como prueba de refutación, no de confirmación:**
   principal = signo de ΔAUC > 0 en T1 (sin 2020) y en T2, más AUC del modelo > 0,5 con IC por bloques; "refutado" si
   ΔAUC < 0 en un giro; el IC de ΔAUC (Holm-2) y la calibración solo informativos, con su potencia (≈ 0,45 / 0,42)
   escrita delante. T1 con 2020 como sensibilidad (choque exógeno, excluido a priori). La AUC estratificada, fuera de T2.
2. **Gastarlo solo cuando una decisión dependa de él:** cuando el usuario vaya a decidir si B2 sustituye a B1 (INT-5), no
   antes. Hasta entonces la sombra de B2 corre con el modelo congelado y no lo necesita.
3. **Esperar a una versión de JST con 2021+ si llega antes de esa decisión:** T2 ganaría las salidas de 2021 (≈ 14 países
   tras 2020) y T1 el periodo 2021-…; no cambia mucho los años distintos (+1-2), así que no compensa esperar
   indefinidamente: si no hay versión nueva cuando haga falta decidir, se gasta con el criterio de refutación del punto 1.
4. La evidencia de ventaja sigue viniendo de desarrollo (INT-4: 72-84 años distintos, países de prueba AUS/CHE con
   ΔAUC +0,21 / +0,22); el bloqueado de JST puede como mucho **tumbarla**, no reforzarla mucho.
