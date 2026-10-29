---
documento: Inventario honesto de relaciones (oro, dinero, crédito, relaciones entre países y otros) — qué se ha probado, con qué resultado y qué falta
version: 1.0 (2026-10-29)
estado: SOLO RECOPILA. No hay ningún contraste nuevo. Los datos del warehouse se describen solo por cobertura (fechas y recuentos con fecha ≤ 2004), nunca por sus valores.
fuentes: docs/int/ATLAS_regimenes.md · docs/int/INT3_prerregistro_v0.md, INT3b_, INT3d_ · research/int/int3*_resultado.md · docs/int/INT4_diseno_v0.md, INT4_prerregistro_v0.md · research/int/int4_resultado.md · docs/int/INT4ML_prerregistro_v0.md, research/int/int4ml_resultado.md · docs/int/INT5_diseno_v0.md · docs/validation/2026-10-26_int3b_int3d_int4.md, 2026-10-29_* · obsidian/Proyecto/Bitácora.md · research/pit_whitelist.yaml · catálogo del warehouse (tabla `catalog`, `obs_latest`) · config/sources.yaml
---

# Inventario de relaciones: qué está probado y qué falta

## 0. Cómo leerlo
- **Confianza.** Uso las mismas clases que el atlas (§0 de `ATLAS_regimenes.md`):
  - **establecido**: cumple todos los criterios de su prerregistro en la corrida única;
  - **probable**: signo esperado y pasa la sensibilidad robusta, pero no todos los criterios;
  - **no establecido**;
  - **descriptivo**: sin contraste;
  - **sin probar**.
- **"No establecido" no es "no existe".** Muchas pruebas tenían poca potencia. Lo indico cuando es el caso.
- **Muestra de casi todo:** 14 países JST del núcleo, 1870-2004, datos anuales revisados. **El periodo 2005-2020 de JST
  está bloqueado y nada de lo que sigue lo ha usado.** EE. UU. mensual (Fase 3): ≤ 2004 y con datos "as of" (PIT).
- **Tipos de pregunta.** Distingo tres, porque no es lo mismo:
  - **(R) régimen → activo**: cómo rinde un activo en un estado; contemporáneo y ex post;
  - **(P) predicción de un giro**: si un indicador "as of" anticipa la entrada o la salida de una recesión, o un giro de
    la inflación;
  - **(A) predicción de un activo**: si un indicador "as of" anticipa la rentabilidad del año siguiente.
  - De (A) **casi no hay nada probado**: solo la versión operable del atlas (§8), que usa estados de inflación y
    crecimiento observados.

## 1. Resumen en una tabla

| tema | qué se ha probado | resultado y confianza | ¿qué falta de verdad? |
|---|---|---|---|
| **Oro** | (R) oro real en moneda local con inflación alta (B3); por cuadrante; en USD desde 1972 | **no establecido, con el signo contrario** (−6,0 pp; mecánico por el precio fijo hasta 1971); desde 1972: −6,8 [−17,4; +3,7] n. s. | **oro en recesiones y crisis** (refugio), **oro y tipo real**, oro como predictor (cobre/oro): **sin probar** en el panel |
| **Dinero (M2 aprox.)** | (P) crecimiento del dinero amplio (P1) para el repunte y la vuelta de la inflación (T3/T4) | **no establecido** (T3 + P1: +0,035 [−0,002; +0,076]; T4 + P1: +0,031; informativos) | **dinero → bolsa y bonos** al año siguiente; **dinero → recesión**: **sin probar** |
| **Crédito (cantidad)** | (P) Δ5 crédito/PIB para la entrada en recesión (C2) y crédito al pico para la salida (S5) | **no establecido** (C2: +0,018 [−0,009; +0,044]; S5: +0,044 n. s.); C2 sí está dentro del termómetro T1 combinado (establecido) | **auge de crédito → crisis financiera** (Schularick-Taylor): **sin probar** con nuestro método |
| **Crédito (precio: diferenciales)** | (R) exceso del crédito frente al bono del Estado en recesión (B4, EE. UU. + R. U.); en EE. UU. mensual, `baa_spread`, `baa_gap10y`, `baa_d6m` en el nowcast M1/M1 v2 | B4 **no establecido** (−0,7 pp [−1,9; +0,5]; de pico a valle −1,5, p = 0,005, informativo); en M1 v2, `baa_gap10y` con el **signo al revés en el 100 % de los cortes** (rebote, *plucking*) | **diferenciales → entrada en recesión** (EE. UU. y resto, contagio): **sin probar**; EBP: no es "as of" |
| **Relaciones entre países** | (P) difusión global de curvas invertidas (C4) para la entrada; difusión de caídas del PIB (S4) para la salida; (R) materias primas con la cuota mundial (B1/B2); correlaciones entre países (INT-2) | **C4 establecido** (+0,126 [+0,065; +0,189]); S4 **no establecido** (+0,087 n. s.); B2 −17,4 [−37; +2] **no establecido (indicio)** | **¿la recesión de EE. UU. o del agregado anticipa la de los demás?**; factor global de la bolsa: **sin probar** |
| **Tipo real** | (P) Δ tipo real corto para la entrada (C5); nivel para el repunte de la inflación (P5); (R) letras con inflación alta (Q4) | C5 **no establecido** (+0,012); P5 **no** (−0,009); Q4 **probable** (−7,7 pp) | **oro y tipo real**; tipo real → bolsa: **sin probar** |
| **Divisa / dólar** | (P) depreciación frente al dólar para T3 (exploratorio) | **no se corrió** (omitido; Validador, 26-oct, BAJO) | dólar → oro y → materias primas; refugio del dólar en recesiones mundiales: **sin probar** |
| **Petróleo / materias primas** | (R) materias primas con inflación alta y recesión mundiales (B1, B2, C5); petróleo spot (descriptivo); (P) P4 para T3 (informativo) | B1 **no** (+0,7, signo cambia de época); B2 **no (indicio)**; petróleo +21 [−10; +52] **descriptivo**; P4 +0,016 n. s. | choque del petróleo → recesión: **sin probar** (solo hay spot anual) |
| **Volatilidad** | volatilidad de 12 meses como listón (diseño INT-4, EE. UU. mensual); VIX en la base PIT (condicional < 2003) | **sin contraste** (EE. UU. mensual sin potencia: 6 entradas NBER) | volatilidad realizada histórica (Shiller, JST) → caídas y recesiones: **sin probar** |
| **Valoración** | (R) parte de valoración de la bolsa en estanflación (C1) | C1 **no establecido** (+1,6 [−2,9; +6,1]) | **D/P o CAPE → rentabilidad futura** (lo más conocido de la literatura): **sin probar** |

## 2. Detalle por tema

### 2.1 Oro
**Probado:**

| pregunta | resultado | confianza | documento |
|---|---|---|---|
| B3: oro real en moneda local con inflación alta del país (1877-1999, 14 países) | −6,0 pp [−9,5; −2,6], p_cal 0,001 | **no establecido** (signo contrario) | `research/int/int3b_resultado.md`; `ATLAS_regimenes.md` §1 |
| B3 con precio libre (≥ 1972) | −6,8 pp [−17,4; +3,7], p = 0,19 | n. s. | `docs/validation/2026-10-26_int3b_int3d_int4.md` §(b) |
| Oro en USD con precio libre (1972-1999) frente al régimen de EE. UU. | −0,4 [−23; +22] | descriptivo | ATLAS §1 |
| Oro por cuadrante | expansión +3,0; sobrecalentamiento −3,9; estanflación −4,2; crecimiento bajo +0,9 | descriptivo | ATLAS §1 |
| Fase 3 (EE. UU. mensual, 1955-2004, ex post) | oro en estanflación +7,0 %/año; con "G baja e inflación acelerando" +16,9 % | descriptivo, sin contraste | Bitácora 15-oct (revisión económica) |
| Oro como peso fijo del 10 % en la cartera (P-DEV-FACT, 1975-2004) | B1 = 80/10/10; ninguna variante táctica mejora a B1 | decisión de cartera, no relación | Bitácora 26-oct |

- **Por qué no sabemos nada del oro:** hasta 1971 tuvo precio fijo en USD (20,67 $ y 35 $). En moneda local, el oro solo se
  movía por el tipo de cambio. Desde 1972 hay 28-33 años, con una desviación típica anual de ≈ 25-30 %.
- **Sin probar:**
  1. **El oro como refugio en recesiones y crisis financieras.** Nunca se ha cruzado el oro con la recesión ni con las
     crisis. Solo con la inflación y los cuadrantes.
  2. **El oro y el tipo de interés real** (coste de oportunidad; Erb-Harvey 2013, Barsky-Summers 1988).
  3. **Cobre/oro como indicador del ciclo.** Está en la base PIT de EE. UU. (`copper_gold_6m`, desde 1973) como variable
     del nowcast, pero sin una prueba propia.
  4. **El oro frente a la depreciación de la moneda local**, que es lo que de verdad protegió antes de 1971.

### 2.2 Dinero (M2 y dinero amplio)
**Probado:**

| pregunta | resultado | confianza | documento |
|---|---|---|---|
| T3 (repunte de la inflación) con P1 = Δlog dinero amplio JST, dentro del combinado P1-P2-P3-P5 | combinado +0,028 [−0,009; +0,069] | **no establecido** | `research/int/int4_resultado.md` |
| T3 + P1 solo (informativo) | +0,035 [−0,002; +0,076] | informativo | ídem |
| T4 + P1 solo (informativo) | +0,031 [−0,013; +0,075] | informativo | ídem |
| Fase 3: `m2_real_yoy` en la base PIT (principal desde 1980-02) | entra en el nowcast; M0 (persistencia) no se batió | sin prueba propia | `research/pit_whitelist.yaml`; Bitácora 16-26 oct |

- **Sin probar:**
  1. **El dinero real como predictor de la bolsa y de los bonos del año siguiente** (pregunta A).
  2. **El dinero como predictor de la recesión.** P1 no se usó en T1.
  3. **El dinero estrecho (`narrowm`)** no se ha usado nunca.
  4. **La liquidez de los bancos centrales** (WALCL, liquidez neta, liquidez global), solo descriptiva desde 2002-2005 y
     casi toda dentro del bloqueado.

### 2.3 Crédito: cantidad (auges de crédito)
**Probado:**

| pregunta | resultado | confianza | documento |
|---|---|---|---|
| C2: Δ5 crédito/PIB (JST `tloans`/`gdp`) añadido a B1, entrada en recesión h = 1 | +0,018 [−0,009; +0,044], placebo p 0,10 | **no establecido** | `research/int/int4_resultado.md` (secundaria Holm-6) |
| C2 dentro del combinado T1 (C1, C2, C4, C5, C6) | combinado +0,178 (estratificada +0,198) | **establecido** (el combinado, no C2) | ídem |
| S5: Δ5 crédito/PIB al pico → salida de recesión | +0,044 [−0,023; +0,111] | informativo, n. s. | ídem |
| C2 × C3 (auge de crédito + vivienda) | no se corrió (exploratorio fuera de la corrida) | — | Validador 26-oct (BAJO) |
| Termómetro en vivo: Δ 20 trimestres del crédito/PIB del BIS | hoy en el percentil ≈ 0 casi en todos los países | descriptivo | Bitácora 29-oct |

- **Sin probar:**
  1. **Auge de crédito → crisis financiera** (Schularick-Taylor 2012), con `crisisjst` como objetivo, nunca como
     predictor. Es la relación más conocida de este mismo panel: sería una réplica con contaminación alta, pero con el
     método nuestro (dejar un país fuera, "as of", placebo).
  2. **Recesiones financieras más profundas tras un auge de crédito** (JST 2013, "When credit bites back"). Solo existe
     el descriptivo de INT-3d: con IC de ± 9-10 pp, sin potencia.
  3. **Crédito de hogares frente a empresas** (`thh`, `tbus`). Solo hay datos desde ≈ 1950 en la mayoría de los países.
  4. **Apalancamiento bancario** (`lev`, `noncore`, `ltd`): nunca se ha usado.

### 2.4 Crédito: precio (diferenciales)
**Probado:**

| pregunta | resultado | confianza | documento |
|---|---|---|---|
| B4: exceso del crédito (corporativo − Estado) en recesión; EE. UU. (Damodaran Baa, 1928-1999) + R. U. (BoE, aproximado, 1877-1999) | −0,7 pp [−1,9; +0,5] | **no establecido** (2 países; MDE 2,2 pp) | `research/int/int3b_resultado.md` |
| B4 de pico a valle | −1,5 pp, p = 0,005 | informativo (cambio de ventana a posteriori) | Validador 26-oct |
| Rentabilidad real del crédito por cuadrante | crecimiento bajo +7,3; expansión +3,9; estanflación +0,1; sobrecalentamiento −5,5 | descriptivo ("se comporta como un bono") | ATLAS §1 |
| M1 v1 (EE. UU. mensual, eje G): `baa_spread` | M1 no bate a M0 | no establecido | Bitácora 16-oct |
| M1 v2: `baa_gap10y` y `baa_d6m` | **`baa_gap10y` con el signo al revés en el 100 % de los cortes**: el diferencial alto marca el rebote, no la caída (*plucking*) | no establecido; lección de forma | Bitácora 23-oct; `docs/reviews/2026-10-23_estratega_macro_m1v2.md` |

- **Excluidos a propósito como predictores:**
  - **EBP y GZ** (`fed_ebp_*`, desde 1973). El EBP es el residuo de una regresión con toda la muestra, incluido 2005-2026:
    no es "as of" ("siempre condicional" en la base PIT). El GZ es condicional antes de 2012.
  - `fed_ebp_recession_prob`: mira al futuro (*lookahead*).
  - NFCI: condicional antes de 2011.
  - Todos se diseñaron mirando 2008-2019 (INT-4 diseño §2).
- **Sin probar:**
  1. **Diferencial Baa − Aaa (o Baa − Tesoro) a fin de año → entrada en recesión de EE. UU.** al año siguiente.
  2. **El diferencial de EE. UU. o del R. U. como indicador común (contagio) → recesión de los otros países.**
  3. **El diferencial corporativo mensual del R. U.** (`boe_uk_corp_bond_spread_m`, 1854-2016): está en el warehouse y no
     se ha usado nunca, aunque es la serie de crédito más larga que tenemos.

### 2.5 Relaciones entre países
**Probado:**

| pregunta | resultado | confianza | documento |
|---|---|---|---|
| C4: % de los otros 13 países con curva invertida → entrada en recesión | +0,126 [+0,065; +0,189]; temporal +0,227 | **establecido** | `research/int/int4_resultado.md` |
| S4: % de los otros países con el PIB cayendo → salida de recesión | +0,087 [−0,024; +0,186] | informativo, n. s. | ídem |
| B1/B2: materias primas con la cuota mundial de inflación alta / recesión | +0,7 / −17,4 | no establecidos | `research/int/int3b_resultado.md` |
| Correlación media entre países de las rentabilidades reales (incondicional) | bolsa 0,31 (1870-2004) y 0,38 (1950-2004); bonos 0,41-0,51 | descriptivo (para la potencia) | `docs/int/INT2_potencia.md` |
| ICC por año de la entrada en recesión | 0,15 (1871-2004 sin guerras), 0,22 (1950-2004) | descriptivo | `docs/int/INT4_diseno_v0.md` §5 |
| Países de prueba (AUS, CHE) con el modelo congelado | T1 +0,21; T2 +0,22 | informativo | `research/int/int4_resultado.md` |

- **Sin probar:**
  1. **¿La recesión de EE. UU. (o la proporción de países en recesión) anticipa la del resto al año siguiente?** C4 lo
     hace con las curvas, no con las recesiones.
  2. **Factor global:** qué parte del ciclo de cada país es común y si esa parte ha crecido después de 1950. Solo está el
     ICC.
  3. **Contagio de las crisis financieras:** ¿una crisis en EE. UU. o en el R. U. eleva el riesgo de crisis en los
     demás?
  4. **Bolsa mundial frente a la local en recesiones globales** (diversificación que falla cuando más falta).

### 2.6 Otros temas
- **Tipo real.**
  - Probado: C5 (Δ1 del tipo real corto → entrada en recesión) +0,012, no establecido; P5 (nivel del tipo real →
    repunte de la inflación) −0,009, no establecido; Q4 (letras reales con inflación alta) −7,7 pp, probable.
  - Atlas §8 operable: con la inflación observada > 3 % en t − 1, letras −5,1 pp, no pasa Holm.
  - Sin probar: oro y tipo real; tipo real → bolsa y vivienda.
- **Divisa / dólar.**
  - La depreciación frente al dólar como exploratorio de T3 **no se corrió** (Validador 26-oct, BAJO: estaba declarada
    en el docstring y no en el prerregistro).
  - Fase 3, descriptivo: el dólar cayó en crecimiento bajo (1973-2004: −3,4 %/año).
  - Sin probar: el dólar como refugio en recesiones mundiales; el dólar y el oro.
- **Petróleo y materias primas.** Ver §1. El petróleo solo existe como spot anual (BoE, 1861-) y diario desde 1983-1987. La
  capa L-CAP-002 (choque energético) está prerregistrada en Fase 3, sin correr.
- **Volatilidad.**
  - El VIX solo existe desde 1990. H-DER-001 (pendiente de la curva de futuros del VIX) y H-DER-002 (volatilidad implícita
    del Treasury) están prerregistradas, pero sus datos empiezan en 2004 o después: casi todo cae en el bloqueado.
  - La volatilidad realizada histórica se puede construir con Shiller (mensual, 1871-) o con JST (anual). No se ha hecho.
- **Valoración.**
  - Probado: C1, la parte de valoración de la bolsa en estanflación (+1,6 n. s.). Es una descomposición, no una
    predicción.
  - **Sin probar:** la relación más documentada de la literatura, **D/P o CAPE → rentabilidad a 1-10 años** (Campbell-Shiller
    1988; Fama-French 1988). Datos: JST `eq_dp` (16 países, desde 1870-1900) y Shiller CAPE (EE. UU., 1881-).

## 3. Qué datos hay en el warehouse (cobertura; recuentos con fecha ≤ 2004)

| bloque | serie | fuente | países | años (≤ 2004 en desarrollo) | "as of" | notas |
|---|---|---|---|---|---|---|
| **Dinero amplio (M2 aprox.)** | `jst_*_money` | JST R6 | 18 | 1870 en casi todos; **BEL desde 1979**, CHE 1880, ESP 1874, IRL 1920 (124-135 años por país, salvo BEL 26) | 120 días | definición nacional, empalmes de JST; revisado |
| Dinero estrecho | `jst_*_narrowm` | JST R6 | 18 | 1870-1877 (DEU 117 años, BEL 116) | 120 días | nunca usado |
| M2 de EE. UU. | `M2SL`, `M2REAL`, `M2V`, `WM2NS` | FRED / ALFRED | USA | 1959- (semanal 1981-) | ALFRED (vintages) | el M2 actual se definió en 1980: condicional antes (base PIT) |
| Dinero de otros países | `ecb_m2/m3_*` (zona euro 1980-), `cbbs_boe_m4_m` (1982-), `cbbs_fred_myagm2jpm189n` (JPN 1967-2017), `cbbs_fred_mabmm301{gb,jp}m189s` (1980/86-), `boe_uk_broad_money_a` (1844-2016), `imf_ifs_*_money_broad_ma` (solo desde 2001-12) | BCE, BoE, OCDE, FMI | pocos | variable | sin vintages | **no hay M2 de la OCDE por país antes de ≈ 1980 en el warehouse**: para el panel largo, solo JST |
| **Oro** | `gold_mw_newyork_usd_a` (1791-), `gold_mw_london_usd_a` (1950-), `gold_mw_london_gbp_a` (1718-1949), `gold_mw_us_official_usd_a`, `gold_wb_usd_m` / `wb_gold` (mensual 1960-), `gold_usd_monthly` (empalme 1791-; anual repetido antes de 1960), `gold_datahub_usd_m` (1833-), `damodaran_gold_ret(_real)` (1928-) | MeasuringWorth (no comercial), Banco Mundial (CC BY 4.0), Damodaran | mundial (USD); en moneda local con `jst_*_xrusd` | precio libre solo **1968/1972-2004** (33 años); fijo 1834-1967 | precio de mercado (medias anual o mensual) | medias, no cierres: subestiman la volatilidad |
| Reservas de oro | `imf_ifs_*_res_gold_*` | FMI | 22 | 1950- | — | nunca usadas |
| **Crédito / PIB** | `jst_*_tloans` (crédito bancario al sector privado), `thh`, `tbus`, `tmort` | JST R6 | 18 | tloans: 1870 (ESP, FRA, NLD 1900; BEL 1885; USA 1880; GBR 1880); **thh/tbus solo desde ≈ 1950** (salvo CHE, GBR, SWE) | 120 días | revisado |
| Crédito total / PIB (BIS) | `bis_creditgap_*_ratio`, `_gap`, `_trend` | BIS | 18 + muchos | ratio desde 1947 (USA), 1955-1971 el resto; brecha desde 1957 (USA) y 1970-1981 el resto | ≈ 6 meses de retraso (declarado); la tendencia es un HP de un lado, pero sobre datos revisados | usado en el termómetro en vivo |
| Banca | `jst_*_lev`, `noncore`, `ltd` | JST R6 | 17 (sin IRL) | 1870-1920 según país | 120 días | nunca usados |
| **Crisis bancarias** | `jst_*_crisisjst` (año de inicio, 0/1) | JST R6 | 18 | 1870-2004; **68 inicios en el núcleo** (BEL 7, DEU 4, DNK 5, ESP 7, FIN 5, FRA 3, GBR 3, ITA 8, JPN 7, NLD 1, NOR 4, PRT 4, SWE 5, USA 5) + AUS 2, CAN 1, CHE 4 | **ex post**: solo como objetivo, nunca como predictor (INT-0) | |
| **Diferenciales EE. UU.** | `BAA`, `AAA` (Moody's, mensual 1919-), `GS10` (1953-), `DBAA`/`DAAA` (diario 1983/86-), `BAA10Y`, `AAA10Y` (diario 1986-) | FRED | USA | **1919-2004** (mensual) | mercado (media mensual) | `BAA`, `AAA` y `GS10` ya están en las familias permitidas de `src/intl/data.py` |
| Rentabilidades del crédito EE. UU. | `damodaran_baa_corp_tr(_real)` | Damodaran | USA | 1928- | anual | construidas desde rendimientos |
| **Diferencial corporativo R. U.** | `boe_uk_corp_bond_spread_m`, `_yield_m`, `_yield_a`, `boe_uk_consol_yield_*` | BoE Millennium | GBR | **1854-2004** (mensual) | mercado, compilado ex post | el diferencial mensual **no está aún en las familias permitidas** |
| Crédito DEU | `bundesbank_corp_bond_yield_m` | Bundesbank | DEU | 1957- | mercado | sin diferencial calculado |
| **EBP / GZ** | `fed_ebp_ebp`, `fed_ebp_gz_spread`, `fed_ebp_recession_prob` | Fed | USA | 1973- | **EBP no "as of"** (residuo con toda la muestra); GZ condicional < 2012; la probabilidad mira al futuro | 4-5 recesiones de EE. UU. ≤ 2004 |
| ICE BofA (HY, IG, euro HY) | `BAML*` | FRED | USA, zona euro | **solo desde 2023-10** (licencia de FRED) | — | inútiles para la historia |
| NFCI | `NFCI`, `ANFCI`, subíndices | Chicago Fed | USA | 1971- | vintages; condicional < 2011 | |
| **Tipos de cambio** | `jst_*_xrusd` (frente al USD) | JST | 18 | 1870- | 120 días | saltos de guerra |
| | `bis_eer_*_neer/reer_narrow_m` | BIS | 11 de 18 (sin BEL, DNK, FIN, IRL, NOR, PRT, SWE) | 1964- | mercado | |
| | `TWEXBMTH`, `TWEXMMTH` (dólar ponderado) | FRED | USA | 1973-2019 | mercado | |
| Cuenta corriente | `jst_*_ca` | JST | 18 | 1870 en casi todos | 120 días | nunca usada |
| **Petróleo** | `boe_uk_oil_price_usd_a` (1861-), `DCOILWTICO` (1986-), `eia_wti_fut_c1…c4` (1983-), `wb_crude_oil_*` (1960-) | BoE, FRED, EIA, Banco Mundial | mundial | anual 1861-; mensual 1960- | mercado | |
| Materias primas | `aqr_clr_*` (1877-), `aqr_cfp_commodities_market_m` (1926-), Pink Sheet (1960-) | AQR, Banco Mundial | mundial | | | |
| **Volatilidad** | `VIXCLS` (1990-), `cboe_*` (casi todo 2004-), `cboe_vx_*` (2004-) | Cboe, FRED | USA | casi nada ≤ 2004 | | la volatilidad realizada histórica se puede construir con `shiller_*` o `jst_*_eq_tr` |
| **Valoración** | `jst_*_eq_dp` (16 países, 1870-1900-), `shiller_cape`, `shiller_tr_cape`, `shiller_excess_cape_yield` (1881-), `damodaran_implied_erp` (1960-) | JST, Shiller, Damodaran | 16 / USA | | 120 días (JST); Shiller mensual | `shiller_fwd10y_*` usa el futuro: **solo como objetivo** |

Detalle de JST por país (primer año / nº de años con dato ≤ 2004):
- `money`: AUS 1870/135 · BEL 1979/26 · CAN 1871/134 · CHE 1880/125 · DEU 1870/124 · DNK 1870/135 · ESP 1874/126 ·
  FIN 1870/135 · FRA 1870/129 · GBR 1870/135 · IRL 1920/85 · ITA 1870/135 · JPN 1870/135 · NLD 1870/132 · NOR 1870/135 ·
  PRT 1870/135 · SWE 1871/134 · USA 1870/135.
- `tloans`: ESP 1900/95, FRA 1900/98, NLD 1900/105, BEL 1885/105, GBR 1880/125, USA 1880/125, IRL 1932/73; el resto,
  1870-1874 con 119-135 años.
- `thh` / `tbus`: casi todos desde 1945-1961 (NLD 1990, NOR 1978, PRT 1979); largos solo CHE (1870) y GBR (1880).

## 4. Qué falta, clasificado

**Valor:** alto = responde a una pregunta del usuario y tiene mecanismo claro; medio = completa algo; bajo = curiosidad.
**¿Sin gastar el bloqueado?:** "sí" = se puede hacer entero con ≤ 2004.

| # | qué falta | valor | ¿sin gastar el bloqueado? | ¿hay potencia? (provisional; INT-6 la calcula) | notas |
|---|---|---|---|---|---|
| 1 | **Auge de crédito (Δ5 crédito/PIB) → crisis financiera** | **alto** | sí (JST ≤ 2004, `crisisjst` como objetivo) | probable (≈ 68 crisis en el núcleo; el efecto de la literatura es grande) | réplica de Schularick-Taylor 2012 con contaminación alta, pero con "as of", dejar un país fuera y placebo |
| 2 | **Contagio: recesión de EE. UU. o proporción de países en recesión → recesión del resto** | **alto** | sí | probable frente a B1; dudosa como añadido al termómetro | complementa C4 (curvas), que ya está establecido |
| 3 | **Diferenciales de crédito (Baa − Aaa de EE. UU. desde 1919; R. U. desde 1854) → recesión** | **alto** | sí | justa (indicador común, ≈ 70-130 años) | el EBP no sirve (no es "as of") |
| 4 | **Oro en recesiones y crisis (refugio): solo desde 1972 frente a toda la historia** | **alto** (pregunta del usuario) | sí (1972-2004) | **baja** (33 años, dt ≈ 25 %) | probablemente solo descriptivo |
| 5 | **Oro y tipo real** | medio-alto | sí (1973-2004 mensual) | justa en mensual | contemporáneo: es una relación, no una predicción |
| 6 | **Dinero real → bolsa y bonos al año siguiente** | medio-alto | sí (JST 1871-2004) | buena en el panel | signo discutido en la literatura |
| 7 | **Dinero → entrada en recesión (añadido al termómetro)** | medio | sí | **mala** (un indicador suelto aporta +0,02-0,05; lo detectable es ≥ 0,05-0,11) | |
| 8 | **Valoración (D/P, CAPE) → rentabilidad a 1-5 años** | alto (literatura) | sí | buena a 1 año en el panel; los horizontes largos solapan | muy contaminada (Campbell-Shiller 1988); candidata a INT-7 |
| 9 | Recesiones financieras más profundas tras un auge de crédito | medio | sí | baja (INT-3d: IC ± 9-10 pp) | |
| 10 | Volatilidad realizada (Shiller, JST) → caídas y recesiones | medio | sí | justa | listón natural para "caídas fuertes" |
| 11 | Dólar / tipo de cambio → oro y materias primas; dólar como refugio | medio | sí (1973-2004) | baja-justa | |
| 12 | Crédito de hogares frente a empresas (Mian-Sufi) | medio | sí, pero solo desde 1950 | baja | |
| 13 | Apalancamiento bancario (`lev`, `noncore`) → crisis | medio | sí | justa | más contaminado (JST 2019-2021) |
| 14 | Choque del petróleo → recesión | medio | sí (anual 1861-) | baja (pocos choques grandes) | |
| 15 | **Confirmación fuera de muestra de todo lo anterior** (P-EVAL) | **alto** | **no**: gasta el bloqueado 2005-2020 | baja (2008-09, 2012, 2020) | solo una vez y por decisión del usuario |
| 16 | EBP, GZ, NFCI, VIX, curva de futuros del VIX, TIPS como predictores | bajo-medio | **no**: casi todos sus datos son ≥ 2004 o no son "as of" | — | se quedan para el seguimiento en vivo |
| 17 | M2 de la OCDE por país antes de 1980 (fuente nueva) | bajo | sí | — | JST `money` ya cubre el panel largo; solo serviría de contraste |

**Mi lectura:**
- **No lo habíamos puesto todo.** El oro, el dinero y el crédito estaban probados solo en una dirección: el oro frente a la
  inflación, el dinero frente a la inflación y la cantidad de crédito frente a la recesión. Y siempre con poca potencia.
- Lo que más valor tiene y se puede hacer **sin gastar el bloqueado** son los puntos 1, 2, 3 y 6 de la tabla.
- **El oro (4 y 5) es lo que más interesa al usuario y lo que peor se puede contestar.** Con 33 años de precio libre, solo
  se detectan efectos muy grandes.
- La valoración (8) es el gran hueco que el usuario no ha nombrado. La propongo para una fase posterior, para no inflar
  las pruebas de INT-6.
