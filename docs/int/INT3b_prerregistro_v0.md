---
documento: P-DEV-INT3b — prerregistro interno de INT-3b (materias primas, oro, energía y crédito por régimen) e INT-3c (por qué: descomposición de la rentabilidad)
version: 1.0 CONGELADA (2026-10-26T19:08Z)
estado: APROBADO por el usuario el 2026-10-26 ("confío, dale": todas las recomendaciones). Congelado antes de escribir el código de la corrida; nada cruzado.
depende_de: INT-1 (etiquetas anuales), INT-2 v0.2 (potencia), INT-3 (P-DEV-INT3 v0.1 y su resultado), Validador de INT-3 (docs/validation/2026-10-26_int3.md)
potencia: scripts/int3b_potencia.py → research/int/int3b_potencia.json (commit 3fd7ed8, árbol limpio, 2026-10-26T18:52:37Z)
---

# P-DEV-INT3b v0.1 (borrador): materias primas, oro, energía y crédito por régimen, y por qué rinde cada activo como rinde

## 0. Qué es y qué no es
- **INT-3b** amplía el mapa de régimen a activos de INT-3 a cuatro activos nuevos: materias primas (futuros), oro,
  energía y crédito corporativo. Es una **descripción histórica**, ex post. Usa los mismos regímenes de INT-3: cuadrantes
  de crecimiento × inflación y recesión.
- **INT-3c** pregunta **por qué**. Parte la rentabilidad en sus piezas y contrasta el mecanismo que se propuso en INT-3
  para cada efecto. Bolsa: dividendo + crecimiento + valoración. Bonos: cupón frente a variación de tipos. Vivienda:
  alquiler frente a precio. Materias primas: spot frente a roll.
- **No es una regla de inversión.** Las series spot del Banco Mundial y los derivados (VIX, CFTC, curva de futuros) son
  **indicadores**, no activos. Se catalogan aquí y se usan en INT-4.
- **Pocas preguntas**, porque la potencia es menor que en INT-3. Las materias primas tienen un solo precio mundial: una
  observación por año, no una por país-año. Son 4 contrastes en INT-3b y 4 en INT-3c. El resto se publica como tabla
  descriptiva, sin contraste y sin la etiqueta de "establecido".

## 1. Fuentes: qué se ha conseguido y qué falta

Todo pasa por `src/intl/data.py`, con corte ≤ 2004-12 y familias permitidas. Las variables se construyen en
`src/intl/activos3b.py`, que no lee regímenes. Las etiquetas de régimen existen para **1876-1999**: la ventana de 11 años
trunca los extremos. Por eso la muestra efectiva termina en **1999** aunque los activos lleguen a 2004.

### 1.1 Activos (para contrastar)

| bloque | serie (id) | fuente | cobertura ≤ 2004 | frecuencia | licencia / procedencia | notas de calidad |
|---|---|---|---|---|---|---|
| **Materias primas (principal)** | `aqr_clr_ew_xret_m`, `aqr_clr_ew_xspot_m`, `aqr_clr_ew_carry_adj_m` (+ spot, carry, cartera larga-corta y backwardation agregada) | AQR, *Commodities for the Long Run* (Levine, Ooi, Richardson y Sasseville, FAJ 2018) | **1877-02 a 2004** | mensual | sin redistribución, uso de investigación. **Descargada hoy** con `src/ingest/aqr_clr.py`: raw intacto, sha256 `eeb89c65…5fe75`, 454 950 bytes, `raw/aqr_clr/provenance.json`; curada en `curated/aqr_clr/` (entra en el warehouse en la próxima reconstrucción; mientras tanto se lee con `load_dev_curado`) | cartera de **igual peso** de futuros; al principio solo hay pocos productos (granos). Identidad de AQR: exceso = spot en exceso + carry ajustado por tipos (roll). **No** se han cargado las columnas de texto: el "estado de inflación" de AQR es un régimen ajeno |
| Materias primas (contraste) | `aqr_cfp_commodities_market_m` | AQR, *Century of Factor Premia* | 1926-07 a 2004 | mensual | ya en el warehouse | misma familia de datos que la anterior: replica, no es independiente |
| **Oro** | `gold_mw_newyork_usd_a` (≤ 1959), `gold_wb_usd_m` (diciembre, ≥ 1960) + `jst_*_xrusd` | MeasuringWorth, Banco Mundial, JST | 1791 / 1960 → 2004 | anual / mensual | MW no comercial; BM CC BY 4.0 | precio en USD **administrado** de 1834 a 1967 (20,67 $ y 35 $). En moneda local el oro solo se mueve por el tipo de cambio hasta 1968. El tipo de cambio de JST da saltos de guerra y de ocupación (ITA 1942, DEU 1946 y 1949, FIN 1919): ver §3 |
| **Crédito EE. UU.** | `damodaran_baa_corp_tr`, `damodaran_tbond_10y_tr` | Damodaran (histretSP) | 1928-2004 | anual | uso educativo y de investigación, citando | rentabilidades **construidas por Damodaran** a partir de rendimientos (Moody's Baa y T-bond a 10 años), no índices de cartera |
| **Crédito R. U.** | `boe_uk_corp_bond_yield_a`, `boe_uk_consol_yield_a` | BoE, *A Millennium of Macroeconomic Data* | 1854-2004 | anual | BoE, reutilización con atribución | **solo rendimientos**. Rentabilidad aproximada **por nosotros**: bono a la par a 20 años, r = y₋₁ − D·Δy + ½·C·Δy², con la misma fórmula para el corporativo y el consol. Fuentes mezcladas (medias y fin de mes). Las etiquetas del R. U. empiezan en 1876, así que el tramo 1854-1875 no se usa |
| **Energía** | `boe_uk_oil_price_usd_a` | BoE Millennium | 1861-2004 | anual (media) | BoE | precio **spot**, no invertible. Solo descriptivo (§2.3) |
| Energía invertible | `eia_wti_fut_c1…c4` | EIA | 1983-2004 | diaria | dominio público | **17 años con etiqueta**: sin potencia. Solo indicador (pendiente de la curva) |
| Deflactores y colateral | `jst_*_cpi`, `jst_usa_bill_rate` | JST R6 | 1870-2004 | anual | CC BY-NC-SA | lo mismo que INT-3 |

### 1.2 Componentes para INT-3c (todos ya en el warehouse, JST R6, 14 países del núcleo)
`eq_tr`, `eq_capgain`, `eq_dp` (bolsa); `bond_tr`, `ltrate` (bonos); `housing_tr`, `housing_capgain` (vivienda); `cpi`.
Las materias primas usan las columnas spot y carry de AQR. En logaritmos, la descomposición es **exacta**: la comprobación
da un error ≤ 3·10⁻¹⁵ (§4.1).

### 1.3 Indicadores (no son activos; se catalogan para INT-4)
- **Banco Mundial (Pink Sheet), 1960-, mensual:** `wb_idx_energy`, `wb_idx_base_metals_ex_iron_ore`,
  `wb_idx_agriculture`, `wb_idx_food`, `wb_idx_grains`, `wb_beef`, `wb_chicken`, `wb_lamb`, `wb_crude_oil_*`,
  `wb_copper`, `wb_gold` y 60 series más.
- **Derivados y posicionamiento:** `VIXCLS` (1990-; antes de 1990 no hay nada en el warehouse, y VXO tampoco está), CFTC
  COT (1986-), pendiente de la curva del WTI (1983-), backwardation agregada de AQR (1877-).
- **Precios generales:** `PPIACO` (1913-), `boe_uk_wpi_a` (1661-).

### 1.4 Huecos (no conseguidos)
1. **Subíndices de futuros por sector** (energía, metales, agrícolas) antes de 1983. El fichero público de AQR solo trae
   la cartera agregada de igual peso y la larga-corta. Los datos de Gorton-Rouwenhorst (1959-2004) y del GSCI no son
   públicos. → **Energía solo como spot, de forma descriptiva.**
2. **Crédito fuera de EE. UU. y R. U.** Solo está `bundesbank_corp_bond_yield_m` (DEU, 1957-). Como mucho, una
   sensibilidad con 43 años.
3. **Rentabilidad total del crédito británico observada:** solo hay rendimientos; la rentabilidad se aproxima.
4. **Bonos corporativos de EE. UU. de 1866 a 1927** (Giesecke-Longstaff-Schaefer-Strebulaev): no son públicos.
5. **VIX y VXO antes de 1990:** no están. La volatilidad realizada histórica se podría construir con Shiller (mensual) si
   INT-4 la pide.
6. **Oro en moneda local:** el tipo de cambio de JST no distingue tipo oficial y tipo de mercado en guerras y controles
   de cambio.

## 2. Preguntas de INT-3b (escritas antes de mirar)

### 2.1 Estados
- **Activos de precio mundial** (materias primas, petróleo). El régimen principal es la **cuota mundial**: la fracción de
  los 14 países del núcleo que están en el estado cada año, con igual peso. El efecto se lee como "pasar del 0 % al
  100 % de países" y, para hacerlo legible, se publica también por 1 dt de la cuota. Lectura complementaria:
  **mayoría**, es decir, años con ≥ 50 % de países en el estado frente al resto. La mayoría no decide, salvo que el
  usuario la elija (§9). Hay pocos años de estanflación mundial (6 años con mayoría): **no se contrasta**.
- **Activos por país** (oro en moneda local, crédito): el estado es el del **propio país**, como en INT-3.
- Inflación alta = sobrecalentamiento + estanflación. Recesión = años de pico + 1 a valle, igual que INT-3. Mismo año t
  para rentabilidad y régimen (contemporáneo).

### 2.2 Contrastes (familia de Holm INT-3b, m = 4)

| id | pregunta (estado frente al resto) | activo y muestra | mecanismo | signo | MDE (80 %, Holm m = 4) |
|---|---|---|---|---|---|
| **B1** | materias primas reales con **inflación alta mundial** | AQR CLR de igual peso, colateralizado con letras de EE. UU. y deflactado con el IPC de EE. UU.; 1878-1999 (122 años) | los choques de inflación son en buena parte choques de precios de materias primas, que forman parte del IPC (Gorton-Rouwenhorst 2006; Levine et al. 2018; Neville et al. 2021) | + | cuota: 23,9 pp de 0 a 100 % (6,5 pp por dt); mayoría: **13,9 pp** (simulada 15,4) |
| **B2** | materias primas reales con **recesión mundial** | ídem | cae la demanda industrial y de energía; se deshacen existencias | − | cuota: 30,7 pp (6,6 por dt); mayoría: **17,6 pp** (simulada 19,6; solo 21 años) |
| **B3** | oro real en **moneda local** con **inflación alta del país** | precio en USD × tipo de cambio de JST, deflactado con el IPC local, log(1 + r); 14 países, 1877-1999; fuera los país-años con inflación > 50 % | depósito de valor frente a la devaluación de la moneda: la inflación alta coincide con depreciaciones (guerras, abandono del patrón oro, años 70) | + | **8,4 pp** (10,9 con el ×1,3 del Validador) |
| **B4** | **exceso del crédito** (corporativo − Estado) con **recesión del país** | USA (Baa de Damodaran, 1928-1999) + GBR (aproximado, 1877-1999); 195 país-años, 52 en recesión | impagos y rebajas de calificación, prima por liquidez y ensanchamiento del diferencial en las recesiones | − | **2,2 pp** (2,9 con ×1,3); dt del exceso: 3,7 pp |

### 2.3 Descriptivas de INT-3b (se publican siempre; no tienen Holm ni "establecido")
- **Petróleo real** (spot, 1877-1999) con inflación alta mundial. Esperado +, con causalidad inversa: los choques del
  petróleo **causan** inflación. MDE de 18,7 pp con mayoría.
- **Oro en USD** solo con precio libre (1972-1999, 28 años) frente al régimen de EE. UU.
- **Replicación de B1 y B2 con AQR Century** (1927-1999). MDE de 17 pp con mayoría.
- B1 y B2 con el **régimen de EE. UU.** en lugar de la cuota mundial (MDE de 14,5 y 14,9 pp).
- **Rentabilidad real del crédito** (no el exceso) con recesión (MDE de 8,6 pp) y **exceso del crédito con inflación
  alta** (sin mecanismo claro: el corporativo y el bono del Estado son nominales los dos).
- Tabla por cuadrante (4 × activo) de medias, volatilidades y caídas, como en INT-3.

## 3. Reglas de datos (fijadas antes de mirar)
- **Hiperinflación:** fuera los país-años con inflación del IPC > 50 %. Son 26 país-años en el núcleo: BEL 1916-17 y
  1941-42; DEU 1917, 1920 y 1922-24; FIN 1917-18 y 1946; FRA 1946 y 1948; ITA 1943-45 y 1947; JPN 1945-48; PRT 1918,
  1920-21 y 1923. Se aplica en B3 y en INT-3c, que trabajan en logaritmos. Es una regla de calidad de datos, decidida
  mirando solo la inflación, no los activos. El Validador de INT-3 (M3) mostró que, sin ella, las medias nominales no
  tienen sentido.
- **Oro y tipo de cambio en guerra:** la regla principal no quita nada más. Sensibilidad: sin 1914-1919 ni 1939-1949, los
  años de tipos oficiales, controles de cambio y reformas monetarias.
- **Materias primas:** el año natural se compone mes a mes y solo cuenta si tiene 12 meses, así que 1877 queda fuera. En
  INT-3c se usan **sumas** de los meses, porque la identidad exceso = spot + carry es aditiva. El residuo de la
  composición se publica: media 0,2 pp y dt 4 pp.
- **Crédito del R. U.:** misma aproximación de duración (n = 20) para el corporativo y el consol. Sensibilidad con n = 10.

## 4. INT-3c: por qué rinde cada activo como rinde

### 4.1 Descomposiciones (exactas en logaritmos; `src/intl/activos3b.py`)
- **Bolsa:** total real = ingreso [ln(1+tr) − ln(1+g)] + **dividendo real** [ln(1+g) + Δln(D/P) − ln(1+π)] +
  **valoración** [−Δln(D/P)].
- **Bonos:** total real = **cupón real** [ln(1+y₋₁) − ln(1+π)] + **capital** [ln(1+tr) − ln(1+y₋₁)], es decir, la
  variación de tipos.
- **Vivienda:** total real = **alquiler** [ln(1+tr) − ln(1+g)] + **precio real** [ln(1+g) − ln(1+π)].
- **Materias primas:** exceso = **spot en exceso** + **carry ajustado por tipos (roll)**. Es la identidad de AQR; el
  colateral (letras) va aparte.

### 4.2 Contrastes (familia de Holm INT-3c, m = 4)
Cada contraste pone a prueba el **mecanismo** que el prerregistro de INT-3 (o la §2 de este documento) dio para un efecto
total. No se contrastan las piezas que son mecánicas por definición del estado. Por ejemplo, con inflación alta el cupón
real (y₋₁ − π) cae por construcción: esas piezas solo se describen.

| id | pregunta | mecanismo que se pone a prueba | signo | MDE (Holm m = 4) |
|---|---|---|---|---|
| **C1** | **valoración** de la bolsa en **estanflación** (Q1 de INT-3: −8,7 pp en total) | la inflación sube el tipo de descuento real y la prima de riesgo, y hay ilusión monetaria (Modigliani-Cohn 1979): los múltiplos se comprimen | − | 7,9 pp (10,2 con ×1,3) |
| **C3** | **capital** del bono con **inflación alta** (Q2: −10,1 pp) | la inflación no esperada sube los tipos largos → pérdida de precio | − | **2,2 pp** (2,9) |
| **C4** | **capital** del bono en **crecimiento bajo** (Q3: +7,9 pp) | bajan los tipos → plusvalía | + | **2,1 pp** (2,8) |
| **C5** | **spot en exceso** de las materias primas con **inflación alta mundial** (B1) | la inflación sorpresa es la subida de precio spot, no el roll | + | cuota 23,5 pp (6,4 por dt); mayoría 13,6 |

### 4.3 Descriptivas de INT-3c (siempre, sin contraste)
- **Reparto de cada efecto total en sus piezas**, en pp y en % del total: Q1, Q2, Q3, Q4 (letras: tipo nominal frente a
  inflación), Q6 (vivienda frente a bolsa: diferencia de ingreso frente a diferencia de capital), B1 (spot, carry y
  colateral) y B4.
- **C2:** dividendo real de la bolsa en estanflación. MDE de 7,6 pp: ¿caen los beneficios reales o solo los múltiplos?
- **C6:** capital real de la vivienda menos capital real de la bolsa con inflación alta. MDE de 7,6 pp: ¿Q6 sale del
  precio o del mayor rendimiento por alquiler?
- **Carry de las materias primas por cuadrante.** La backwardation aumenta en mercados tensos (Gorton-Hayashi-Rouwenhorst
  2013), pero no se contrasta.

## 5. Método (el de INT-3 con las correcciones del Validador)
- **Series mundiales** (B1, B2, C5 y las descriptivas): MCO y_t = a + b·S_t + e_t, donde S_t es la cuota (o la mayoría).
  Errores **Newey-West**, que es Driscoll-Kraay con una sola unidad, con retardos ⌊4·(T/100)^(2/9)⌋ = 4 y t con T − 1
  grados de libertad.
- **Paneles** (B3, B4, C1, C3, C4): efectos fijos de país y b·D_it. Errores **Driscoll-Kraay por año** (Bartlett, retardos
  por defecto), que es la función `driscoll_kraay` de `src/intl/int3.py`. CR2 por año se publica al lado, solo como
  comparación.
- **Calibración con el placebo (principal):** el estado se desplaza en círculo k = 6 … T − 6 años, con la misma k en
  todos los países. Con las t del placebo se calcula φ = máx(1, dt(t placebo)) y p_cal = 2·P(t_{T−1} > |t|/φ). **Holm
  se aplica sobre p_cal**, dentro de cada familia.
  - **Por qué no se usa el p por rangos** (fracción de placebos con |t| ≥ |t real|) bajo Holm: tiene un **suelo**
    1/(T − 10). Con T = 124 el suelo es 0,0088, y Holm con m = 6 exige 0,0083. Por eso, en la sensibilidad robusta de
    INT-3, **ninguna** de las 6 pasó Holm con el p por rangos (`holm_p_placebo` todo `False`), aunque todas superaron
    los 113 placebos. Con T = 72, como mucho m = 3.
  - El p por rangos se mantiene como **criterio aparte**, sin Holm: |t| por encima del percentil 95 de las |t| placebo.
- **Criterio de países (paneles):** signo de los efectos por país **sin encoger** y signo del DerSimonian-Laird sobre
  efectos **sin la media de cada año** (A1 del Validador). El DL con efecto común (τ² ≈ 0) no se usa como criterio.
- **Secundaria (operable, informativa):** régimen del año t − 1 frente a rentabilidad del año t. El retardo se toma
  **por año** (unión con año − 1), no con `shift` por fila (B2 del Validador).

### 5.1 Criterio de "efecto establecido" (cada contraste de B1-B4 y C1, C3-C5)
1. Signo igual al esperado.
2. p_cal ≤ umbral de Holm de su familia (m = 4).
3. |t| > percentil 95 de las |t| placebo.
4. Mismo signo en **1950-1999**, sin exigir significación. En las series mundiales, además, mismo signo en 1878-1949.
5. Solo en paneles: mismo signo en **≥ 2/3 de los países** sin encoger y en DL sin la media del año. En B4, con 2
   países: **los dos**.

### 5.2 Sensibilidades (se publican siempre; no deciden)
- Sin años de guerra.
- Mayoría frente a cuota.
- Régimen de EE. UU. en lugar del mundial.
- Cuota ponderada por PIB (JST `rgdpmad`).
- Ventana de recesión de **pico a valle**: incluye el año del pico, por la M4 del Validador; los mercados se adelantan al
  ciclo.
- Oro: sin 1914-1919 ni 1939-1949; en aritmética; solo con precio libre (≥ 1972).
- Crédito del R. U. con n = 10.
- Materias primas: solo exceso (sin colateral) y AQR Century.
- Países de prueba AUS y CHE en B3 y en INT-3c (solo signos).
- Holm conjunto de las 8 preguntas (m = 8: MDE ≈ +7 %).

## 6. Potencia (antes de mirar; `research/int/int3b_potencia.json`)
Se ha calculado **solo** con recuentos de años por régimen y con la varianza y la autocorrelación **incondicionales** de
cada activo. Las simulaciones usan rentabilidades sintéticas: AR(1) gaussiano y t(4), 400 réplicas, aplicando el
contraste completo (Newey-West + φ del placebo + percentil 95 + signo en 1950-1999) con la trayectoria real del régimen.

| pregunta | dt anual | estado | MDE analítico | MDE simulado (completo, normal / t4) |
|---|---|---|---|---|
| B1 materias primas, inflación alta | 22,3 % | 41 años de mayoría (de 122) | 13,9 pp | 15,4 / 14,8 |
| B2 materias primas, recesión | 22,3 % | 21 años de mayoría | 17,6 pp | 20,6 / 19,6 |
| B3 oro local, inflación alta | 17,1 % (ρ entre países 0,60) | 575 país-años | 8,4 pp | — (× 1,3 → 10,9) |
| B4 exceso de crédito, recesión | 3,7 % | 52 país-años | 2,2 pp | — (× 1,3 → 2,9) |
| C1 valoración, estanflación | 29,1 % | 229 país-años | 7,9 pp | — (× 1,3 → 10,2) |
| C3 / C4 capital del bono | 7,2 % | 549 / 552 país-años | 2,2 / 2,1 pp | — (× 1,3 → 2,9 / 2,8) |
| C5 spot de materias primas, inflación alta | 21,5 % | 41 años de mayoría | 13,6 pp | 14,7 / 14,9 |
| (referencia: Q1 de INT-3 con estos datos) | 20,9 % | 247 | 8,4 pp | (resultado real: −8,7) |

**Lectura:**
- Lo previsto (~10-15 pp) se cumple en las materias primas: **≈ 14-15 pp en B1 y ≈ 18-20 en B2**. La cuota continua da
  ~25 % más potencia que la mayoría, si el efecto es lineal en la cuota.
- El crédito (B4) y los componentes de bonos (C3, C4) tienen buena potencia, porque su varianza es pequeña.
- La valoración de la bolsa (C1) está justa: sus piezas tienen **más** varianza que el total, porque el dividendo medido
  y la valoración se compensan.
- El "× 1,3" es la penalización por autocorrelación común que encontró el Validador en INT-3 (CR2 dio un 19 % de falsos
  positivos en su simulación). Se publica como cota prudente.
- Hay una advertencia de método: con las series mundiales, el p por rangos del placebo no puede bajar de 0,0088 (§5).

## 7. Contaminación declarada
- **Literatura conocida:** materias primas buenas con inflación al alza (Gorton-Rouwenhorst 2006; Erb-Harvey 2006;
  Levine et al. 2018, que además publican su propio estado de inflación en el mismo fichero; Neville et al. 2021). Oro
  mal cubridor de la inflación a horizontes cortos (Erb-Harvey 2013). Prima de crédito pequeña y concentrada en crisis
  (Asvanunt-Richardson 2017). Modigliani-Cohn.
- **INT-3c depende de totales que ya se conocen** (Q1-Q6 de INT-3). Lo nuevo son las piezas: ninguna se ha cruzado con un
  régimen.
- **Lo que ha visto el agente que redacta:**
  - las primeras filas del fichero de AQR (los 11 meses de 1877), al inspeccionar su estructura;
  - los estadísticos incondicionales de §6;
  - una lista de país-años con oro real local > 60 % en valor absoluto, junto a su inflación, mirada por calidad de
    datos (saltos de tipo de cambio en guerras; 1979 en todos los países).

  No ha cruzado ningún activo con ninguna etiqueta de régimen.
- La historia es conocida: los años 70, 1979-80 en el oro y 1931-32 en el crédito.

## 8. Expectativa honesta (antes de correr)
- **B1** (materias primas con inflación alta) es el efecto más documentado. Pero el estado "inflación alta" de INT-1 se
  define por **nivel**, y es más amplio que las "sorpresas" de la literatura: el efecto puede quedarse por debajo de los
  14-15 pp. **Probable en signo, dudoso como establecido.**
- **B2**, con solo 21 años de mayoría, necesita ≈ 20 pp: **improbable** que salga, aunque el signo sea el esperado.
- **B3** es la más incierta. Con patrón oro (≤ 1914 y 1925-1931), el oro en moneda local solo se mueve por
  devaluaciones, y la inflación alta mecánicamente **resta** (precio fijo, IPC que sube). El signo esperado depende de
  que las inflaciones altas sean sobre todo devaluaciones.
- **B4:** el exceso de crédito es pequeño (dt 3,7 pp), con un MDE de 2,2 pp. Es plausible si las recesiones de 1929-33 y
  del R. U. pesan; la ventana que excluye el año del pico puede diluirlo.
- **C3 y C4** son probables: es el mecanismo de duración de manual. **C1** es probable en signo, pero justo de potencia.
  **C5** va con B1.
- "No establecido" no es "no existe".

## 9. Decisiones del usuario (antes de aprobar)
1. **Régimen de las series mundiales:** cuota mundial (recomendado, más potencia), mayoría (más legible) o régimen de
   EE. UU.
2. **Oro (B3):** panel en moneda local 1877-1999 (recomendado; más potencia, pero mezcla "oro" con "devaluación") o solo
   USD con precio libre 1972-1999 (28 años, sin potencia; quedaría solo como descriptiva).
3. **Energía:** aceptar que entre solo como spot descriptivo, porque no hay futuros públicos antes de 1983.
4. **Familias de Holm:** INT-3b y INT-3c por separado, m = 4 + 4 (recomendado: son hipótesis distintas), o una conjunta
   con m = 8 (MDE +7 %).
5. **Ventana de recesión (B2, B4):** la de INT-3, pico + 1 a valle (recomendado, para comparar), o de pico a valle.
6. **B2:** mantenerla con su potencia baja (recomendado, para no elegir por resultados) o pasarla a descriptiva.
7. **Regla de hiperinflación** (> 50 %) y licencias: AQR no permite redistribuir, Damodaran y MW son no comerciales. Uso
   interno, como en el resto de la fase.

## 10. Orden y gobierno
1. El usuario aprueba (o corrige) este texto → commit y push con hora, **antes** de calcular nada.
2. Se escribe el script de corrida con puerta (árbol limpio, commit y hora en la salida) y se commitea sin ejecutar con
   datos. Después se hace **una sola corrida** de INT-3b + INT-3c. Todo va al registro de pruebas.
3. Validador independiente del resultado.
4. El periodo bloqueado (2005-2020/2025) queda para la evaluación única (P-EVAL), si el usuario la decide.

## Decisiones del usuario (2026-10-26, congelado v1.0)
Todas las recomendadas: (1) régimen mundial = proporción de países en el estado; (2) oro en moneda local 1877-1999; (3) energía solo descriptiva; (4) Holm en dos familias de 4 (INT-3b: B1-B4; INT-3c: C1, C3, C4, C5); (5) ventana de recesión de INT-3; (6) B2 se mantiene pese a la poca potencia; (7) se excluyen los país-años con inflación > 50 % (26) y se acepta el uso no comercial de AQR, Damodaran y MeasuringWorth.
