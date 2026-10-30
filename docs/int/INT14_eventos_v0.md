---
documento: INT-14 — EVENTOS que mueven bolsa y materias primas (shock del petróleo, crisis bancaria, subida fuerte del dólar, pico de volatilidad/VIX): inventario, definiciones operativas, recuentos, potencia e integración con INT-11
version: 0.1-borrador (2026-10-30)
estado: BORRADOR para el usuario (fase 1). DEFINICIONES FIJADAS ANTES DE MIRAR NINGÚN EFECTO. Ninguna rentabilidad se ha cruzado con ningún evento. Periodo ≥ 2005 sin tocar.
codigo: src/intl/eventos.py (definiciones + estudio de eventos, puro, solo probado con sintéticos), tests/test_intl_int14_eventos.py
potencia: scripts/int14_potencia.py (corrida con puerta, árbol limpio) → research/int/int14_potencia.json
prerregistro: borrador docs/int/INT14_prerregistro_v0.md
depende_de: INT-11 v2 (motor de escenarios, src/intl/escenarios.py — NO se modifica), INT-12 (volatilidad realizada diaria de EE. UU.)
---

# INT-14: eventos como escenario (A) y como objetivo a anticipar (B) — borrador v0.1

## 0. Qué se pregunta, en una frase
**A)** Cuando ocurre un shock del petróleo, una crisis bancaria, una subida fuerte del dólar o un pico de volatilidad,
¿qué les pasa en los 1-24 meses / 1-3 años siguientes a la bolsa, los bonos, las letras, la vivienda, el oro y las
materias primas? **B)** ¿Tiene sentido intentar *anticipar* esos eventos con los datos que hay?

**Idea clave para aprender.** En un estudio de eventos lo que cuenta es el **número de eventos independientes**, no el
número de meses. Un shock del petróleo afecta a todos los países a la vez: 12 shocks × 17 países siguen siendo ≈ 12
observaciones, no 204. Por eso el primer trabajo es **contar bien** y el segundo **calcular la potencia**: qué efecto
mínimo podríamos distinguir del ruido. Si ese mínimo es enorme, el resultado será "no se puede saber", y es mejor
saberlo antes.

**Orden de trabajo (disciplina del proyecto):** (1) definiciones fijadas en este documento → (2) recuentos solo con la
serie que define el evento → (3) potencia con rentabilidades **sintéticas** en las fechas reales → (4) prerregistro
congelado → (5) una sola corrida. Este documento cubre (1)-(3) y el diseño de integración. **Nada de (5) se ha hecho.**

## 1. Inventario (≤ 2004; detalle en `int14_potencia.json → inventario`)

| papel | serie | frecuencia | desde | notas PIT / calidad |
|---|---|---|---|---|
| petróleo, tramo 1 | `nber_m04079` precio en pozo EE. UU. | mensual | 1890-01 (→ 1941-06) | mercado de EE. UU. (entonces ≈ el mundial) |
| petróleo, tramo 2 | `WPU0561` PPI crudo doméstico | mensual | 1947 | **precio controlado 1971-81** (por eso no es el principal desde 1960); hueco 1941-46 |
| petróleo, tramo 3 | `wb_crude_oil_average` (Banco Mundial, media Brent/Dubai/WTI) | mensual | 1960 | precio mundial; 1960-70 casi plano (precios "posted") |
| petróleo, otros | `boe_uk_oil_price_usd_a` (anual, 1861), `MCOILWTICO` (1986), `eia_wti_fut_c1` (1983) | — | — | sensibilidad / no necesarios |
| dólar | `TWEXMMTH` índice Fed frente a monedas principales | mensual | **1973-01** | antes no hay índice ponderado; `TWEXBMTH` (amplio) igual desde 1973; `DTWEXBGS` solo ≥ 2006 |
| dólar largo | `jst_*_xrusd` (16 monedas/USD) | anual | 1870 | cesta igual-ponderada; antes de 1973 los "saltos" son **devaluaciones** de otros (patrón oro, Bretton Woods) |
| volatilidad realizada | `aqr_mkt_usa_d` + `ffx_us_rf_d` (CRSP diario) | diaria | **1926-07** | la de INT-12; vol. del mes = √(252·media r²) |
| VIX | `VIXCLS` | diaria | 1990-01 | **recalculado en 2003 hacia atrás**; el VXO (1986) **no está** en el archivo |
| crisis bancarias | `jst_*_crisisjst` (JST R6) | anual | 1870 (IRL 1920) | marca el **año de inicio**; fechado **a posteriori** por historiadores: no es "en tiempo real" |
| crisis, contraste | `raw/financial_crises/` Reinhart-Rogoff 2016 y Laeven-Valencia 2018 | anual | — | sin curar; solo como sensibilidad del fechado (fase 2) |
| resultados mensuales | bolsa EE. UU. (CRSP, 1926), letras (`ffx_us_rf_d`), bono 10 a. aproximado (`shiller_gs10`, bono a la par), oro (`gold_usd_monthly`, **libre desde 1968**), materias: `aqr_cfp_commodities_market_m` (1926), `aqr_clr_ew_xret_m` (1877, exceso), Banco Mundial energía / metales base / preciosos (1960), precio del petróleo | mensual | — | **vivienda: no hay mensual ≤ 2004 con historia** → solo anual |
| resultados anuales | JST: `eq_tr`, `bond_tr`, `bill_rate`, `housing_tr`, deflactados con `cpi` (rentabilidad **real**, como INT-11) | anual | 1871 | 17 países; vivienda con huecos |

## 2. Definiciones operativas v0 (FIJADAS; `src/intl/eventos.py`, constantes `PETROLEO`, `DOLAR`, `VOL`, `CRISIS`)
Regla común de **episodio** ("cruce"): el evento es el **primer mes en que se cruza el umbral** (el mes anterior no lo
cumplía) y a ≥ *separación* del evento anterior. Así una racha larga no cuenta mil veces, y tampoco se traga episodios
distintos (la racha de volatilidad alta 1997-2003 contiene varios picos). Sensibilidad: modo "racha" (encadena).

| evento | definición principal (v0) | retraso de publicación | sensibilidades fijadas |
|---|---|---|---|
| **E1 shock del petróleo** | Subida neta de Hamilton (NOPI) a 3 años: `max(0, log p_t − log max(p_{t−1..t−36}))`, **acumulada 12 meses ≥ 0,20** (≈ el precio ha subido > 22 % por encima de su máximo de 3 años en el último año). Precio nominal; cadena **mundial**: pozo EE. UU. 1890-1941, PPI crudo 1947-59, Banco Mundial 1960-2004 (los empalmes se tratan como hueco: ninguna ventana mezcla tramos). Separación 24 meses. | 1 mes | umbral 0,10 y 0,30; cadena doméstica (PPI hasta 2004); lista de la literatura (Hamilton 2011, tabla 1: 1947-48, 1952-53, 1956-57, 1969, 1970, 1973-74, 1978-79, 1980-81, 1990, 1999-2000, 2002-03; **meses exactos por verificar contra el original antes de congelar**); anual con `boe` antes de 1890 |
| **E2 crisis bancaria** | JST `crisisJST` = 1 (año de inicio), por país; un año marcado a < 5 años del anterior del mismo país = continuación. **Episodio global**: años de crisis (de cualquier país) a ≤ 1 año del anterior se encadenan. | ninguno (fechado ex post; se declara) | `crisisJST_old`; Reinhart-Rogoff y Laeven-Valencia (fase 2) |
| **E3 subida fuerte del dólar** | Δlog 12 m del índice `TWEXMMTH` **≥ 0,10**, separación 24 meses. Solo **1973-2004** (era de tipos flotantes). | 1 mes | umbral 0,05 y 0,15; cesta anual JST 1870-2004 (con y sin años de guerra) — solo descriptivo |
| **E4 pico de volatilidad ("VIX")** | Volatilidad realizada mensual de la bolsa de EE. UU. (CRSP diario) **≥ percentil 90 de TODOS los meses anteriores** (ventana creciente, ≥ 60 meses de historia: as of), separación 12 meses. 1931-2004. | 0 (se conoce al cerrar el mes) | P95; separación 6; modo racha; **VIX ≥ su P90 expansivo (1990-2004)** como réplica en la era del VIX |

**Correspondencia VIX ↔ volatilidad realizada (solape 1990-01 … 2004-12, 180 meses; solo los dos definidores):**
correlación 0,84 en niveles y 0,87 en logs; VIX medio 19,9 frente a RV media 14,1 (la "prima de varianza": el VIX
va ≈ 5,8 puntos por encima); **P90 del VIX = 28,2 ↔ P90 de la RV = 25,2**. Acuerdo mes a mes en "mes alto" (≥ P90 de
cada uno): 90 %, κ de Cohen 0,44; de los meses de VIX alto, la RV también es alta en la mitad. Con el mismo método en
1990-2004: VIX → 5 eventos (1997-08, 1998-08, 2000-04, 2001-09, 2003-02); RV → 6 (1996-07, 1997-10, 1998-12, 2000-01,
2001-03, 2002-07): **los mismos episodios con 1-5 meses de desfase**. Lectura: la RV es un sustituto razonable del VIX
para *fechar episodios*; no lo es para *niveles exactos* (el VIX lleva prima y anticipa algo). Por eso E4 se define con
la RV en toda la muestra (una sola regla 1931-2004) y el VIX queda como réplica.

## 3. Recuentos (solo eventos; `int14_potencia.json → eventos`)

| evento | eventos ≤ 2004 | utilizables con resultados mensuales (CRSP, ≥ 1926-07) | con 24 m completos ≤ 2004 | fechas |
|---|---|---|---|---|
| E1 petróleo (principal) | **13** | 7 | 6 | 1895-01, 1899-09, 1903-12, 1913-01, 1917-09, 1920-01, 1971-01, 1973-04, 1979-01, 1990-08, 1996-10, 2000-06, 2004-08 |
| E1 umbral 0,10 / 0,30 / doméstico | 15 / 9 / 12 | | | |
| E2 crisis (país-evento) | **72** (3 descartadas por < 5 años) | — | — | 39 años distintos; **21 episodios globales**; 1946-2004: 12 crisis en 5 episodios |
| E3 dólar (principal) | **3** | 3 | 3 | 1981-06, 1984-10, 2000-10 |
| E3 umbral 0,05 / 0,15 | 8 / 2 | | | |
| E4 pico de volatilidad (principal) | **16** | 16 | 16 | 1931-09, 1933-03, 1937-10, 1940-05, 1946-09, 1962-05, 1970-05, 1973-12, 1980-03, 1982-08, 1987-10, 1990-08, 1997-10, 1999-10, 2000-10, 2002-07 |
| E4 P95 / sep. 6 / racha | 8 / 21 / 12 | | | |
| E4 réplica VIX 1990-2004 | 5 | | | |

Crisis por periodo: 1870-1913 la mayoría; los grandes episodios globales son 1889-91 (6 países), 1907-08 (6),
1920-22 (9), **1930-31 (11)** y **1987-91 (8, nórdicas; Japón 1997 aparte)**. Por periodo: 1870-1913 36 crisis en 12
episodios; 1914-45 24 en 6; 1946-2004 12 en 5. Una cae en año de guerra (excluida del panel, como en INT-11).
Lectura: **las crisis bancarias son el único evento con muchos casos** (72 país-evento), pero muy agrupadas: el tamaño
efectivo está más cerca de 21-40 que de 72. **El dólar tiene 3 eventos**: con eso no se demuestra nada.

**Solapes entre eventos (±12 meses; `solapes_12m`).** Petróleo ~ pico de volatilidad en **5 de 6** shocks con datos
diarios (1971/1970, 1973-04/1973-12, 1990-08/1990-08, 1996-10/1997-10, 2000-06/1999-10 y 2000-10); dólar 2000-10 ~
volatilidad 2000-10 y petróleo 2000-06; dólar 1984-10 ~ crisis de EE. UU. 1984 (Continental Illinois). Ninguna crisis
de EE. UU. a ≤ 12 meses de un pico (1930 ↔ 1931-09 está a 14). El estudio trata cada evento **por separado** y declara
los solapes; no intenta separar causas (con estos n no se puede).

**Probabilidad incondicional del evento (para el generador; solo recuentos):** pico de volatilidad ≈ 16 en 74 años
(≈ 22 %/año); shock del petróleo ≈ 13 en 115 años (≈ 11 %/año; 6 en 1960-2004 ≈ 13 %/año); crisis bancaria ≈ 72 en
≈ 2.250 país-años (≈ 3 %/año por país, muy agrupado); subida fuerte del dólar ≈ 3 en 31 años (≈ 10 %/año).

## 4. Potencia del uso A (estudio de eventos)
**Método** (`scripts/int14_potencia.py`): se generan rentabilidades **sintéticas** (t de 5 g. l. con la desviación
típica marginal real de cada activo; en el panel, choque común con la correlación contemporánea media real entre
países y la misma disponibilidad país-año) y se aplica **exactamente** el estadístico del estudio en las **fechas
reales** de los eventos: media de la acumulada tras el evento menos la media de los orígenes sin evento. La dispersión
de ese estadístico bajo la nula da el **efecto mínimo detectable (MDE)** con potencia del 80 %: a α = 5 % bilateral y
a α = 1,25 % (Holm, el más exigente de 4 contrastes). En pp de rentabilidad acumulada (log ≈ %).

**Mensual (EE. UU./mundo), MDE a α = 5 % [pp]:**

| evento → activo | n | 1 m | 3 m | 6 m | 12 m | 24 m |
|---|---|---|---|---|---|---|
| pico vol. → bolsa EE. UU. | 16 | 3,8 | 6,7 | 9,4 | **13,0** | 21,0 |
| pico vol. → bono 10 a. (aprox.) | 16 | 0,8 | 1,4 | 2,0 | 2,8 | 4,5 |
| pico vol. → materias (AQR CFP) | 16 | 3,3 | 5,6 | 7,8 | 11,2 | 17,7 |
| pico vol. → oro (≥ 1968) | 10 | 4,6 | 7,9 | 11,0 | 16,1 | 26,0 |
| petróleo → bolsa EE. UU. | 6-7 | 5,8 | 10,1 | 14,9 | 21,3 | 31,1 |
| petróleo → materias (AQR CLR, 1877) | 12-13 | 3,9 | 7,0 | 10,2 | 14,7 | 20,0 |
| petróleo → metales base (BM) | 6-7 | 4,7 | 7,7 | 12,3 | 17,3 | 24,3 |
| dólar → bolsa / oro / materias | 3 | 7-9 | 12-15 | 19-23 | **26-31** | 37-44 |
| VIX (1990-2004) → bolsa | 5 | 6,8 | 11,7 | 17,3 | 23,9 | 46,2 |

Con la volatilidad **más alta tras el evento** (× 1,5 en los 24 meses siguientes, lo esperable tras un pico) los MDE
de "pico → bolsa" suben ≈ 50 % (12 m: 13,0 → **20,1 pp**; `vol->bolsa_volpost_x1.5`). En el panel, el ruido es
independiente en el tiempo: para la **vivienda**, cuya rentabilidad anual está muy autocorrelacionada, el MDE a 3 años
es optimista (orden de magnitud realista ≈ 10-12 pp).

**Panel anual JST (17 países, real), MDE a α = 5 % [pp], acumulada t+1..t+H:**

| evento → activo | n país-evento | 1 año | 2 años | 3 años |
|---|---|---|---|---|
| crisis (sin guerras) → bolsa | 64 | **8,4** | 12,8 | 16,1 |
| crisis → bonos | 64 | 4,8 | 7,7 | 10,6 |
| crisis → letras | 66 | 2,6 | 4,1 | 4,8 |
| crisis → vivienda | 44 | 3,8 | 5,5 | **6,9** |
| crisis 1946-2004 → bolsa / vivienda | 12 | 17,3 / 7,5 | 25,0 / 9,8 | 32,1 / 12,9 |
| petróleo (12 años globales) → bolsa | 173 | **10,6** | 15,4 | 18,5 |
| petróleo → vivienda | 148 | 2,9 | 3,8 | 5,4 |
| pico vol. (años globales) → bolsa | 239 | 8,5 | 13,1 | 16,9 |
| dólar (3 años globales) → bolsa | 48 | 20,0 | 30,7 | 32,4 |

**Cómo leerlo.** Un MDE de 13 pp a 12 meses significa: si de verdad la bolsa rinde, de media, 13 pp más (o menos) en el
año siguiente a un pico de volatilidad, lo detectaríamos 8 de cada 10 veces; si el efecto real es de 5 pp (lo que
sugiere la literatura), lo más probable es "no establecido". La literatura sí documenta efectos **grandes** en dos
casos: **vivienda real tras crisis bancarias** (caídas acumuladas de dos dígitos a 3-5 años; Jordà-Schularick-Taylor)
y **bolsa real tras crisis** (caída mayoritariamente en el año de la crisis, que aquí NO cuenta: se mide desde t+1).
**Dólar: imposible con 3 eventos** — solo descripción.

## 5. Potencia del uso B (anticipar el evento)
Caso-control sintético con el número **real** de eventos independientes; listón con AUC ≈ 0,70 (una variable buena,
como el crecimiento del crédito para las crisis); el modelo añade una variable nueva; probabilidades de oráculo
(optimista); contraste unilateral 5 % por bootstrap pareado. `int14_potencia.json → potencia_B`.

| objetivo | eventos / no eventos | MDE ΔAUC (80 %) | MDE Brier skill |
|---|---|---|---|
| pico de volatilidad en 12 m (anual 1931-2004) | 16 / 58 | ≈ **0,19** | no se alcanza |
| shock del petróleo en 12 m (1890-2004) | 13 / 96 | ≈ **0,18** | no se alcanza |
| subida del dólar (1974-2004) | 3 / 28 | no se alcanza | no se alcanza |
| crisis bancaria país-año (72 eventos, como si fueran independientes) | 72 / 1.900 | ≈ 0,054 | ≈ 0,033 |
| crisis, contando episodios (21) | 21 / 475 | ≈ 0,125 | ≈ 0,13 |

**Recomendación B: no hacerlo como contraste** para petróleo, dólar y volatilidad: solo se demostraría un salto de
AUC de ≈ 0,7 a ≈ 0,9, que no es realista (la literatura sobre predecir shocks del petróleo o picos de volatilidad a 12
meses da ganancias pequeñas). Para **crisis bancarias** la potencia es mejor (ΔAUC 0,05-0,13 según se cuenten
eventos o episodios; la verdad está en medio), pero la pregunta ya está muy estudiada
(crecimiento del crédito: Schularick-Taylor 2012; el termómetro y el régimen del proyecto) y los datos ≤ 2004 del
panel JST ya se han usado en INT-4/INT-10. Si se quisiera, sería un **INT-14B** aparte, con su propio prerregistro y
confirmación en ≥ 2005 (2007-08 aporta un episodio global grande).

## 6. Integración con INT-11 (diseño; `src/intl/escenarios.py` NO se modifica)
El motor INT-11 v2 es **anual**, por país, con estados de régimen (inflación × brecha) y bootstrap por bloques de
filas país-año. Tiene ya un mecanismo de **inclinación** (`simular(..., inclinacion={col: (valor, ancho)})`) que pesa
las filas del primer año simulado según covariables `z_col` (que `preparar_filas` toma con un año de retraso).

**6.1 Escenario condicionado "si hay evento X este año" (estrés).** Sin tocar el motor:
1. Construir por país-año la columna `ev_X_sig` = indicador del evento en el año **siguiente** (eventos globales: igual
   para todos los países; crisis: la del país). Como `preparar_filas` retrasa un año las covariables, la fila del año t
   recibe `z_ev_X_sig` = evento **en t**.
2. `g.simular(pais, estado, inclinacion={"ev_X_sig": (1, 0.1)})`: el primer año se sortea casi solo entre años-país
   con evento (núcleo gaussiano muy estrecho sobre un 0/1), y la primera transición de régimen se inclina en la misma
   proporción (`_ratio_inclinacion`). Los años 2-5 siguen el bloque (probabilidad 1 − 1/3 de continuar con el año
   siguiente del mismo país): la **dinámica post-evento sale de los datos**.
3. Salida: abanico por activo (`abanico`), `prob_caida`, y la **diferencia con el escenario base** (mismo estado sin
   inclinación). Esto es "qué activo va bien si pasa X": una tabla evento × activo × horizonte con p10-p50-p90.
4. Cautelas: las celdas son pequeñas (12 años globales de petróleo; 64 crisis), así que el suavizado de v2
   (`c_suavizado`) ensancha el abanico — es lo correcto. El escenario es **hipotético** ("si ocurre"), no una previsión.

**6.2 Estado observable "ya ha ocurrido" (uso en la salida de hoy).** Columna `ev_X` = evento en el año (sin
adelantar) → `z_ev_X` = evento el año anterior. Responde a "hubo un pico de volatilidad / una crisis el año pasado:
¿qué abanico tienen los próximos años?". Mismo mecanismo de inclinación.

**6.3 Eventos como estados del generador Monte Carlo (propuesta INT-11 v3, requiere cambiar el motor más adelante).**
Estado ampliado (régimen, evento) con:
- **Riesgo (hazard) del evento** por año, sorteado por lote de su posterior Beta(eventos + ½, años sin evento + ½)
  (recuentos de §3; p. ej. pico de volatilidad ≈ 22 %/año, petróleo ≈ 11-13 %/año, crisis ≈ 3 %/año por país con
  contagio vía el régimen mundo). **Sin condicionar en el régimen** hasta que exista un contraste (uso B) que lo
  justifique: hoy condicionar sería usar una relación no probada.
- Si el evento sale en la trayectoria, las filas del año se sortean de la celda (régimen, evento) — exactamente la
  inclinación de 6.1, pero en cualquier año de la trayectoria, no solo el primero.
- Resultado: los abanicos incorporan la probabilidad de los eventos **y** su impacto, y se puede leer "P(algún shock del
  petróleo en 5 años) ≈ 1 − 0,88⁵ ≈ 45 %; en esas trayectorias, la bolsa…".
- Validación: la misma de v2 (cobertura LOCO y temporal) más que la frecuencia simulada del evento cuadre con la
  histórica. Confirmación solo en ≥ 2005 con puerta de gasto.

**6.4 Capa mensual (1-24 meses).** El motor anual no da trayectorias de 1-24 meses. Tras la corrida A, la capa
mensual sería **descriptiva**: trayectorias empíricas post-evento (las de los 6-16 eventos, bootstrap por bloques de
calendario), presentadas con su IC y con el aviso de n pequeño. No entra en el motor.

## 7. Riesgos y límites declarados
- **Pocos eventos**: 3-16 por tipo (salvo crisis). Los IC serán anchos; "no establecido" será el resultado frecuente.
- **Fechado ex post de las crisis** (JST): sirve para escenarios, no para una regla en tiempo real.
- **Petróleo pre-1960 = mercado de EE. UU.**; 1960-70 precio mundial administrado (por eso no hay eventos).
- **Oro fijo hasta 1968** (solo se usa ≥ 1968); **vivienda solo anual**; **bono mensual aproximado** desde el tipo.
- **Solape de eventos** (1973-74, 1990): no se separan causas.
- **No estacionariedad**: la mayoría de las crisis son anteriores a 1946; los shocks del petróleo con CRSP son 1971-2000.

## 8. Decisiones del usuario (con recomendación)
| # | decisión | recomendación |
|---|---|---|
| D1 | Umbrales v0 (petróleo Σ12 NOPI ≥ 0,20; dólar ≥ 10 %; vol. ≥ P90 expansivo; crisis JST) | **aceptar** (fijados antes de ver efectos; sensibilidades ya listadas) |
| D2 | Contrastes principales A (≤ 4, Holm) | **los 4 del prerregistro**: crisis → vivienda real 3 a.; crisis → bolsa real 1 a.; pico vol. → bolsa EE. UU. 12 m; petróleo → bolsa real (panel) 1 a. |
| D3 | Dólar | **solo descriptivo** (3 eventos) |
| D4 | Uso B (anticipar) | **no** para petróleo/dólar/vol.; crisis solo como INT-14B aparte si interesa |
| D5 | Lista de Hamilton (2011) como sensibilidad | **sí**, verificando los meses contra el original antes de congelar |
| D6 | Integración | **6.1 y 6.2 ya** (sin tocar el motor, tras la corrida A); **6.3 como INT-11 v3** con prerregistro propio |
| D7 | Confirmación | ≥ 2005 aporta 2007-08 (crisis global, petróleo, VIX), 2010-11, 2014-15 (dólar), 2020, 2022: pedir puerta de gasto solo tras la corrida de desarrollo |
