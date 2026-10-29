---
documento: P-DEV-INT7 — valoración → rentabilidad (prerregistro interno)
version: 0.1 BORRADOR (2026-10-29)
estado: BORRADOR, pendiente de las decisiones del usuario (§10). No se ha cruzado ningún indicador de valoración con ninguna rentabilidad. Solo varianzas incondicionales, AR(1), correlaciones entre países de cada serie POR SEPARADO, recuentos y disponibilidad.
depende_de: INVENTARIO_relaciones.md (§3 y §4, hueco 8), INT-6 v1 §8 (anotada como candidata a INT-7), INT-3b (método de panel, Driscoll-Kraay, placebo calibrado, Holm), INT-3c (C1, descomposición de la bolsa)
potencia: scripts/int7_potencia.py (28d1359, árbol limpio, 2026-10-29T18:12:36Z) → research/int/int7_potencia.json (22d20b5)
---

# P-DEV-INT7 (borrador v0.1): valoración → rentabilidad futura

## 0. Qué es y qué no es
- **Qué es.** Cubre el gran hueco del inventario (`INVENTARIO_relaciones.md`, fila "Valoración" y hueco 8): **¿una bolsa
  cara anticipa rentabilidades reales menores?** Es la relación más documentada de la literatura financiera y la única de
  ese tipo que el proyecto no ha probado. Lo único probado de valoración es C1 (INT-3c), una descomposición
  contemporánea, no una predicción.
- **Muestra:** solo JST ≤ 2004 (14 países del núcleo) y Shiller ≤ 2004 (EE. UU.). **No gasta el periodo bloqueado.**
- **Preguntas.** Se consideran 5. **Quedan 2 confirmatorias** (recomendado), elegidas por valor y potencia; una tercera,
  el CAPE de EE. UU., queda como opción del usuario (decisión 2). Las demás pasan a informativas o descriptivas.
- **No es una regla de inversión ni de market timing.** Mide si la valoración anticipa la rentabilidad media en la
  historia. Goyal-Welch (2008) mostraron que casi todos estos predictores fallan **fuera de muestra**; aquí se publica
  esa medida al lado (§4.4), pero no decide. Nada se conecta al reporte ni a la cartera sin una decisión registrada.
- **Gobierno: el de siempre.**
  1. El usuario decide (§10) y el texto se congela con hora.
  2. Se commitea un script de corrida con puerta (árbol limpio, commit y hora en la salida).
  3. **Una sola corrida.**
  4. Validador independiente.

## 1. Las 5 preguntas y su destino

| id | pregunta | signo | muestra | MDE simulado (1 contraste / Holm-2 / Holm-3) | plausible (literatura) | destino |
|---|---|---|---|---|---|---|
| **V1** | ¿un **D/P alto** en t → **más bolsa real** en t + 1? (panel, efecto total: común + propio) | + | 14 países, 1871-2004; 1.656 filas | **2,4-2,5 / 2,6-2,9 / 2,8-3,0 pp por 1 dt** de log D/P (R² a 1 año ≈ 1,3 / 1,5-1,8 / 1,7-2,0 %) | ≈ 2-4 pp por dt (R² 1-3 % a 1 año) | **confirmatoria** |
| **V2** | ¿un país **más barato que los demás el mismo año** (D/P relativo) → más bolsa real en t + 1? (efectos de país y de año) | + | ídem | **1,7 / 1,8-1,9 / 1,9-2,0 pp por 1 dt** de log D/P (1,3 / 1,4 / 1,5 por dt del D/P relativo) | ≈ 1-3 pp por dt | **confirmatoria** |
| **V3** | D/P → bolsa real **a 5 años** (t + 1 … t + 5; solapada) | + | ídem; 1.577 filas | 3,0-3,2 / 3,4-3,5 / 3,6-3,7 pp por dt **en unidades de 1 año** (≈ 10-12 pp acumulados a 5 años) | la misma relación que V1, vista a 5 años | **informativa** (menos potencia que V1 y casi redundante) |
| **V4** | **CAPE alto** (EE. UU.) → menos bolsa real; a **10 años** y a 1 año | − | EE. UU., 1881-2004; 123 años (1 año) / 114 solapados, **11 no solapados** (10 años) | 1 año: **4,6-4,9 / 5,2-5,6 / 5,6-5,9 pp por dt** de log CAPE (R² 6-10 %); 10 años: **5,6 / 6,5 / 6,8** en unidades de 1 año con δ = −0,9 (35-42 pp acumulados) y **> 7,1** (fuera de la rejilla) con δ = −0,5 y −0,7 | 1 año: ≈ 3-5 pp por dt (R² 3-8 %) | **opción del usuario** (decisión 2); recomendado: **descriptiva** (réplica de Campbell-Shiller con sus mismos datos) |
| **V5** | ¿la valoración **modula** el efecto de la estanflación del atlas? (diferencia de pendientes de V1 entre estanflación y resto) | + | 237 país-años en estanflación (86 años), 1.318 resto | **5,7 / 6,2 / 6,5 pp por dt** de diferencia de pendientes (analítico, sin Stambaugh: optimista) | ≈ 1-3 pp (no hay una referencia firme) | **descartada → descriptiva** |

**Notas a la tabla:**
- **Unidades:** pp de rentabilidad real (log) al año por 1 dt del indicador. El rango recorre los tres δ supuestos
  (§2.2). En V4 el indicador es −log CAPE para que el signo esperado sea + en la simulación.
- **"MDE simulado"** = efecto con el que el contraste del prerregistro (§3) rechaza el 80 % de las veces, con su valor
  crítico calibrado con la nula simulada que **incluye** el sesgo de Stambaugh. Es el MDE que cuenta.
- **Familia de Holm recomendada:** Holm-2 = {V1, V2} (decisión 2). Si el usuario quiere V4 confirmatoria: Holm-3.

## 2. Potencia (`research/int/int7_potencia.json`)

### 2.1 Estadísticos incondicionales (cada serie por separado)

| serie | n | dt | ρ entre países | AR(1) (media; mín-máx por país) |
|---|---|---|---|---|
| log D/P (JST, 14 países, ≤ 2004, sin hiperinflación) | 1.676 | 0,52 | 0,36 | **0,79** (0,54-0,95) |
| log D/P relativo (sin efectos de país ni de año) | 1.676 | 0,40 (77 % de la total) | −0,07 | 0,72 (0,45-0,92) |
| bolsa real, log, 1 año (JST) | 1.739 | 21,2 % | 0,33 | 0,14 (−0,11-0,40) |
| bolsa real relativa (sin efectos de país ni de año) | 1.739 | 16,8 % | −0,08 | 0,06 |
| bolsa real, log, 5 años solapados | 1.655 | 50,3 % | 0,47 | 0,80 (por el solape) |
| log CAPE (Shiller, diciembre, 1881-2004) | 124 | 0,40 | — | **0,885** anual (0,921 en 1950-2004; 0,994 mensual) |
| bolsa real de EE. UU., log (Shiller, año natural) | 133 | 17,7 % | — | 0,03 |
| log D/P de EE. UU. (JST) | 134 | 0,40 | — | 0,87 |

Calidad: 7 país-años con D/P ≤ 0 en JST (quedan fuera por la regla del indicador, §3). PRT acaba en 1987; FIN empieza en
1912; ESP, NLD en 1899-1900; JPN en 1886.

### 2.2 Por qué hace falta simular: el sesgo de Stambaugh
- El D/P y el CAPE son **muy persistentes** (AR(1) 0,79-0,89 anual) y sus innovaciones están **muy correlacionadas con
  la rentabilidad** del mismo año (si sube el precio, baja el D/P): δ ≈ −0,7 a −0,95 en la literatura (Stambaugh 1999;
  Lewellen 2004; Campbell-Yogo 2006).
- Con eso, la pendiente MCO **está sesgada hacia la predictibilidad** (Stambaugh 1999), y con efectos fijos el sesgo es
  de orden 1/T **por país**: no se diluye al añadir países (Hjalmarsson 2008).
- **δ no se ha medido** (sería cruzar indicador y rentabilidad). Se supone una rejilla δ ∈ {−0,5, −0,7, −0,9}.
- **Lo que mide la simulación** (3.000 réplicas por caso; panel sintético con la disponibilidad, la φ, las ρ y las dt
  reales; MCO con efectos fijos y Driscoll-Kraay):

| caso | sesgo medio bajo la nula | tamaño real del t ingenuo al 5 % | t crítico calibrado (1 contraste / Holm-2) |
|---|---|---|---|
| V1 (1 año) | +0,3 a +0,5 pp por dt | **9-13 %** | 2,5-2,9 / 2,8-3,4 |
| V2 (1 año, efectos de año) | +0,3 a +0,5 | 9-16 % | 2,6-3,0 / 3,0-3,3 |
| V3 (5 años) | +1,4 a +2,6 pp por dt (acumulado) | **15-25 %** | 3,2-3,8 / 3,6-4,5 |
| V4 (1 año) | +0,6 a +1,1 | 8-10 % | 2,4-2,7 / 2,7-3,1 |
| V4 (10 años) | **+4,9 a +8,3 pp por dt (acumulado)** | **22-27 %** | 4,1-4,7 / 4,7-5,6 |

- **Lectura:** un contraste ingenuo (t de Student o el placebo desplazado de INT-3b, que **rompe** la correlación δ y no
  reproduce el sesgo) daría falsos positivos del 10-27 %. Por eso el p principal de INT-7 es un **bootstrap nulo que
  conserva δ** (§3.2), no el p_cal del placebo.
- Una aproximación cerrada (Kendall: E[φ̂ − φ] ≈ −(1 + 3φ)/T) da sesgos parecidos para 1 año (0,5-0,9 pp por dt).

### 2.3 Lectura de la potencia
- **V1:** con Holm-2, MDE 2,6-2,9 pp por dt (prudente analítico, con ρ_y en lugar de ρ_x·ρ_y: 3,9). La potencia para
  2,5 pp es ≈ 65-80 %; para 3 pp, ≈ 80-90 %. **Justa a buena.** En 1950-2004 el MDE sube a 4,2-6,1: ese tramo solo
  aporta el signo.
- **V2:** la que más potencia tiene: quitar el año elimina la parte común (ρ ≈ 0) y la dt de la rentabilidad baja a
  16,8 %. MDE 1,8-1,9 pp por dt con Holm-2. **Buena** si el efecto relativo es ≥ 2 pp.
- **V3 (5 años):** con un predictor AR(1), el horizonte largo **no añade información** sobre la de 1 año y pierde
  potencia por el solape (Boudoukh-Richardson-Whitelaw 2008; Valkanov 2003). Lo confirma la simulación: MDE 3,4-3,5
  frente a 2,6-2,9 de V1 con el mismo Holm. Ponerla en la familia cuesta potencia a V1 y V2 y apenas aporta. → informativa.
- **V4 (CAPE, EE. UU.):** una sola serie. A 1 año el MDE es R² ≈ 8-10 % (Holm-2/3), en el borde alto de lo publicado; con Holm-3 la
  potencia es del 25-35 % para 3,5 pp por dt y del 50-60 % para 4,6 pp. **A 10 años es peor**, no mejor: 11 observaciones
  independientes, sesgo de +5 a +8 pp, MDE ≥ 35-42 pp acumulados por dt (y fuera de la rejilla con δ = −0,5 y −0,7).
- **V5 (interacción):** 237 país-años en estanflación. Detectar una diferencia de pendientes exige ≥ 6 pp por dt, el
  doble del efecto principal plausible. **Sin potencia** → descriptiva.

## 3. Definición de las confirmatorias (fijada antes de mirar)

**Reglas comunes:**
- **Núcleo:** 14 países (BEL, DEU, DNK, ESP, FIN, FRA, GBR, ITA, JPN, NLD, NOR, PRT, SWE, USA). **Países de prueba**
  (AUS, CHE): solo al final, con el modelo congelado; informativos.
- **Corte:** `src/intl/data.load_dev`, todo ≤ 2004-12. **Nada de JST ≥ 2005.** La fila t exige y_{t+1} ≤ 2004.
- **Indicador:** x_it = log(`jst_*_eq_dp`) del año t. D/P ≤ 0 → ausente (regla sobre el indicador solo).
- **Resultado:** y_{i,t+1} = log(1 + `eq_tr_real`) del año t + 1 (rentabilidad total real de la bolsa, JST).
- **Hiperinflación:** fuera los país-años con inflación > 50 % en t o en t + 1 (regla de INT-3b; mira solo el IPC).
- **Guerras:** todos los años en la principal; sin 1914-1918 ni 1939-1945 (en t o t + 1) como sensibilidad.
- **"As of".** El D/P es un **dato de mercado**: precio de cierre de t y dividendos pagados en t. Que JST lo publique
  años después no introduce información de t + 1 en x_t: la regresión no mira el futuro. Lo que sí hay es una brecha de
  **implementabilidad** (¿se conocían los dividendos del año el 31 de diciembre?), que se declara y se cubre con la
  sensibilidad estricta x_{t−1} → y_{t+1}. **A verificar por el Validador antes de la corrida:** que `eq_dp` de JST R6
  usa el precio de fin de año (si es la media del año, la fila sigue sin mirar el futuro, pero se anota).

### V1 — D/P → bolsa real del año siguiente (panel, efecto total)
- **Hipótesis:** + (Campbell-Shiller 1988; Fama-French 1988). Un D/P alto es un precio bajo frente al dividendo: o
  anticipa más rentabilidad, o menos crecimiento del dividendo. La identidad de Campbell-Shiller obliga a una de las dos.
- **Hipótesis rival declarada:** el D/P anticipa **dividendos** y no rentabilidades (lo habitual fuera de EE. UU.;
  Engsted-Pedersen 2010; Rangvid-Schmeling-Schrimpf 2014). Si V1 sale "no establecido", la descriptiva §4.3 (D/P →
  crecimiento real del dividendo) dirá hacia dónde se va la identidad.
- **Contraste:**
  - y_{i,t+1} = α_i + b·z_it + e, z = x estandarizada (dt del conjunto); b en pp por 1 dt.
  - Errores Driscoll-Kraay por año (`src/intl/int3.driscoll_kraay`, retardos por defecto).
  - **Pendiente corregida** de Amihud-Hurvich (2004), versión de panel: se añade a la regresión el residuo v̂_it de un
    AR(1) del indicador por país con φ corregida por Kendall. Se publica junto a la MCO; el **efecto que se lee** es el
    corregido.
- **p principal: bootstrap nulo que conserva δ** (§3.2). Holm se aplica sobre este p.
- **Establecido si:**
  1. signo + (MCO y corregida);
  2. p del bootstrap nulo ≤ el umbral de Holm-2;
  3. |t| > p95 de las |t| del placebo desplazado (k = 6 … T − 6, misma k en todos los países; regla de INT-3b,
     **criterio aparte**: no reproduce el sesgo, por eso no decide solo);
  4. mismo signo en 1871-1949 y en 1950-2004, sin exigir significación;
  5. mismo signo en ≥ 2/3 de los países sin encoger y en DerSimonian-Laird sin la media de cada año.
- **Sensibilidades:** sin guerras; estricta x_{t−1} → y_{t+1}; D/P en niveles; exceso sobre letras (`bill_rate_real`);
  winsorizado 1-99 del indicador; sin la regla de hiperinflación; AUS y CHE; Hodrick 1B en lugar de DK; t + 2.

### V2 — D/P relativo → bolsa real relativa del año siguiente (efectos de país y de año)
- **Hipótesis:** + . El país más barato **que los demás ese año** rinde más que los demás el año siguiente. Es "value"
  entre países (Asness-Moskowitz-Pedersen 2013; Keimling 2016 con CAPE desde 1979). Aquí, en una historia de 130 años.
  Quita los ciclos mundiales (los años 70, 1929, 2000): es la lección del atlas §8 y el criterio 6 de INT-6.
- **Contraste:** como V1, con efectos fijos de país **y de año** (y = α_i + λ_t + b·z_it + e). b se publica por 1 dt del
  log D/P total y por 1 dt del D/P relativo (× 0,77).
  - Driscoll-Kraay por año (los efectos de año ya quitan la correlación contemporánea; DK cubre el resto).
  - Pendiente corregida de Amihud-Hurvich con el AR(1) del D/P **relativo** por país.
- **p principal, criterios 1-5 y sensibilidades:** como V1. En el criterio 5, la pendiente de cada país sobre su D/P
  relativo.
- **Lectura conjunta V1-V2:** V1 sin V2 = la predictibilidad es sobre todo **común** (época mundial); V2 sin V1 = sirve para
  **elegir países**, no para entrar o salir de la bolsa. Ninguna de las dos lecturas es un descubrimiento por sí sola.

### 3.2 El bootstrap nulo (p principal de V1 y V2; también en V4 si es confirmatoria)
Como Nelson-Kim (1993) y Goyal-Welch (2008), en panel:
1. Bajo H0 (b = 0): ê_it = y_it − ȳ_i (V2: además − media del año); el indicador sigue un AR(1) por país,
   x_it = c_i + φ_i^{BC}·x_{i,t−1} + v_it, con φ corregida por Kendall y v̂ sus residuos.
2. Se remuestrean **años enteros** con reemplazo, en **bloques de 5 años** consecutivos: se toman juntos los vectores
   (ê_t, v̂_t) de todos los países. Así se conservan δ, la correlación entre países y algo de dependencia temporal.
3. Se reconstruye x* desde el valor inicial real de cada país, y* = ȳ_i + ê*, con los mismos huecos de disponibilidad.
4. Se calcula la t de Driscoll-Kraay de la MCO, igual que con los datos. 4.999 réplicas; semilla fijada en el script.
5. p = 2·mín(P(t* ≥ t), P(t* ≤ t)). El suelo es 1/5.000, lejos del umbral de Holm-2 (0,0125).

Los mismos pasos dan el IC del efecto corregido (bootstrap con b̂ impuesta). La simulación de §2 valida que con este
valor crítico el tamaño es el nominal.

## 4. Informativas y descriptivas (se publican siempre; sin Holm y sin "establecido")

### 4.1 V3, D/P → 5 años (informativa)
y = Σ log(1 + `eq_tr_real`) de t + 1 a t + 5; misma especificación que V1; errores Hodrick 1B (regresión inversa) y
Driscoll-Kraay con 5 retardos; p del bootstrap nulo de §3.2 con el horizonte 5. Con su MDE al lado (3,4-3,5 pp por dt en
unidades de 1 año, ≈ 11-12 pp acumulados).

### 4.2 V4, CAPE de EE. UU. (descriptiva salvo decisión 2)
- x_t = log CAPE **"as of"** de diciembre de t: precio real de diciembre sobre la media de 10 años del beneficio real
  hasta junio de t (`shiller_real_price`, `shiller_real_earnings`), para no usar beneficios aún no publicados. El
  `shiller_cape` de Shiller (beneficios hasta diciembre) va como sensibilidad.
- y: log de la rentabilidad total real de Shiller (`shiller_real_stock_tr_ret_m`) en el año natural t + 1 y en t + 1 …
  t + 10.
- Newey-West (1 año; 10 retardos a 10 años) y Hodrick 1B; p del bootstrap nulo de una serie.
- **Requiere** añadir las series de Shiller a las familias permitidas de `src/intl/data.py` (decisión 4).
- Al lado: el log D/P de JST de EE. UU. (AR(1) 0,87) con lo mismo, como puente con V1.

### 4.3 La otra mitad de la identidad
D/P → crecimiento real del dividendo en t + 1 (`eq_dp`·precio, deflactado). Sin Holm. Sirve para leer V1 si sale nula
(§3, hipótesis rival).

### 4.4 Fuera de muestra (Goyal-Welch)
R² fuera de muestra de V1 y V2 frente a la media histórica, con ventana creciente (estimar con ≤ t, predecir t + 1),
evaluado en 1950-2004; y la prueba de Clark-West. Solo informativa: en la literatura casi siempre es ≤ 0 y no tiene
potencia. Se publica porque es la pregunta práctica.

### 4.5 V5, valoración × estanflación (descriptiva)
Pendiente de V1 en los país-años de estanflación (etiquetas de INT-1, ≤ 1999) frente al resto, con su IC y el MDE al lado
(≈ 6 pp por dt). **Frase obligatoria:** "con 237 país-años en estanflación esto no puede distinguir una modulación de
1-3 pp de cero".

## 5. Multiplicidad
- **Una familia, Holm-2:** V1 y V2 (recomendado; decisión 2).
- **Alternativa:** Holm-3 con V4 (CAPE de EE. UU. a 1 año). El MDE de V1 y V2 sube ≈ 5 % y V4 entra con una potencia del
  25-60 % para 3,5-4,6 pp por dt.
- **No recomendado:** Holm-4 con V3. V3 es casi la misma hipótesis que V1 con menos potencia: gastaría Holm en una
  repetición.
- Holm se aplica sobre los p del bootstrap nulo (§3.2). El p del placebo desplazado se publica aparte (criterio 3).

## 6. Contaminación (declarada): **muy alta**

| id | nivel | por qué |
|---|---|---|
| V4 | **máxima** | Campbell-Shiller (1988, 1998, 2001) y Shiller (*Irrational Exuberance*) construyeron el CAPE **con estos mismos datos** y publicaron el resultado a 10 años en EE. UU. hasta ≈ 2000. Sabemos el signo y el orden de magnitud dentro de la muestra. Es una réplica, no una prueba |
| V1 | **muy alta** | Fama-French (1988), Campbell-Shiller (1988), Cochrane (2008) en EE. UU.; Goyal-Welch (2008), que lo matan fuera de muestra; evidencia internacional mezclada (Ang-Bekaert 2007; Engsted-Pedersen 2010; Rangvid-Schmeling-Schrimpf 2014; Golez-Koudijs 2018 con datos largos). JST (Jordà et al. 2019) publica la rentabilidad de este mismo panel |
| V2 | alta | value entre países (Asness-Moskowitz-Pedersen 2013; Keimling 2016), sobre todo desde 1970-1980. En la historia larga de JST no conocemos un resultado publicado con este diseño, pero el signo esperado es conocido |
| V3 | muy alta | la literatura de horizontes largos (Fama-French 1988; Valkanov 2003; Boudoukh-Richardson-Whitelaw 2008) |
| V5 | media | C1 (INT-3c) cruzó la **variación** del D/P con la estanflación (contemporáneo; +1,6 n. s.); el nivel del D/P nunca se ha cruzado con la rentabilidad futura |

**Lo que ha visto el agente que redacta:**
- dt, AR(1) y correlación entre países de cada serie **por separado** (§2.1), y recuentos y disponibilidad;
- la literatura citada (lo sabe de antemano; no se puede "desver").

Ningún indicador de valoración cruzado con ninguna rentabilidad. δ **no** se ha medido.

## 7. Expectativa honesta (antes de correr)
- **V1:** signo + muy probable dentro de muestra (casi toda la literatura lo encuentra con MCO). Que sobreviva al
  sesgo de Stambaugh con el bootstrap y a Holm-2 es **dudoso-probable**: el sesgo se come 0,3-0,5 pp de un efecto de 2-4,
  y fuera de EE. UU. buena parte del D/P anticipa dividendos. El criterio de las dos mitades (≤ 1949 y ≥ 1950) puede
  fallar: 1995-2004 (D/P mínimo y bolsas que siguieron subiendo hasta 2000) pesa en contra en la segunda.
- **V2:** la más nueva y la que tiene más potencia. Signo + **probable**; que salga "establecido", **probable si el
  efecto relativo es ≥ 2 pp por dt**.
- **V3:** irá con V1, con IC más anchos.
- **V4:** dentro de muestra saldrá con el signo esperado (es conocido); con el bootstrap y a 1 año, **dudosa** como
  establecida; a 10 años, aunque la t ingenua sea enorme, la calibrada no lo será.
- **Fuera de muestra (§4.4):** lo más probable es un R² ≤ 0 o apenas positivo.
- "No establecido" no es "no existe".

## 8. Fuera de INT-7 (anotado para después)
- **Confirmación en el bloqueado (2005-2020)**: el D/P y el CAPE tienen ahí una prueba fuera de muestra limpia (2008,
  tipos cero). Solo una vez y por decisión del usuario; antes, su potencia (con 16 años, poca).
- **Otras valoraciones:** rendimiento de beneficios menos tipo real (`shiller_excess_cape_yield`, la "prima" del CAPE),
  prima implícita de Damodaran (1960-, 45 años, EE. UU.), q de Tobin: no se plantean (pocas series o muestra corta).
- **Valoración de la vivienda** (alquiler/precio de JST → vivienda real): mismo diseño; candidata natural si V1-V2
  aportan algo.
- **Bonos:** la pendiente de la curva → bonos (Campbell-Shiller 1991) ya está cerca de INT-4 (C1); no se duplica.

## 9. Lo que pide al código (antes de la corrida)
- `scripts/int7_corrida.py` con puerta: carga, V1-V2 con bootstrap nulo y Amihud-Hurvich, placebo, criterios, §4.
- Si se aprueba la decisión 4: familia `shiller_(cape|real_price|real_earnings|real_dividend|real_stock_tr_ret_m)` en
  `src/intl/data.py`. Ahora mismo `scripts/int7_potencia.py` lee `shiller_cape` y `shiller_real_stock_tr_ret_m` con el
  mismo corte y la misma comprobación que `load_dev`, pero fuera de las familias (declarado; solo para la potencia).
- Tests sintéticos del bootstrap: tamaño nominal bajo la nula con δ = −0,9 y φ = 0,9.

## 10. Decisiones del usuario (antes de congelar)
1. **Confirmatorias: V1 y V2** (*recomendado*). V3 informativa, V5 descriptiva (sin potencia).
2. **CAPE de EE. UU. (V4):** descriptiva (*recomendado*: es una réplica de Campbell-Shiller con sus mismos datos, y su
   potencia a 1 año con Holm-3 es del 25-60 % para el efecto plausible, y a 10 años menor) **o** confirmatoria a 1 año dentro de Holm-3 (V1 y V2 pierden
   ≈ 5 % de MDE). En ningún caso como confirmatoria a 10 años: con 11 observaciones independientes es la peor opción.
3. **Inferencia:** p principal del **bootstrap nulo que conserva δ** (*recomendado*; el placebo desplazado de INT-3b no
   reproduce el sesgo de Stambaugh y daría un 10-25 % de falsos positivos) y efecto leído con Amihud-Hurvich.
4. **Datos:** añadir la familia de Shiller a `src/intl/data.py` (necesario para V4 incluso como descriptiva). *Recomendado:
   sí.* No hace falta descargar nada: las series ya están en el warehouse (`shiller_cape`, `shiller_tr_cape`,
   `shiller_real_price`, `shiller_real_earnings`, `shiller_real_stock_tr_ret_m`, 1871/1881-2004).
5. **"As of" del D/P:** tratarlo como dato de mercado conocido al cierre de t, con la sensibilidad estricta x_{t−1}
   (*recomendado*), o hacer la estricta la principal (pierde la fila más informativa; el MDE apenas cambia, el efecto
   esperado baja).
6. **Fuera de muestra (§4.4):** solo informativa (*recomendado*) o criterio adicional de "establecido" (con su potencia
   casi nula, sería exigir lo imposible).

Si se aprueba: se congela como v1.0 con hora, se escribe `scripts/int7_corrida.py` con puerta, se commitea sin ejecutar,
**una sola corrida**, Validador, y después Bitácora, atlas e inventario.
