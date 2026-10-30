---
documento: INT-12 — modelo de RIESGO DE MERCADO a 1-3 meses (volatilidad, VaR/ES, P de caída): inventario, diseño y potencia
version: 0.1-borrador (2026-10-30)
estado: BORRADOR para el usuario (fase 1). Ningún predictor cruzado con ningún resultado. Ningún modelo ajustado a datos reales. Periodo ≥ 2005 sin tocar.
potencia: scripts/int12_potencia.py (commit 5e1bc93, árbol limpio, 2026-10-30T12:31Z, 515 s) → research/int/int12_potencia.json
tests: tests/test_intl_int12_potencia.py (sintéticos)
depende_de: INT-11 (motor macro anual), INT-10 (lección "información, no capacidad"), B1 (docs/factors/paper_trading.md)
---

# INT-12: riesgo de mercado a 1-3 meses, como complemento del motor macro (borrador v0.1)

## 0. Qué se pregunta, en una frase
¿Puede un modelo de ML **demostrar** (con los datos ≤ 2004 y una sola corrida) que prevé mejor que los listones clásicos
la **volatilidad** del próximo mes o trimestre, el **VaR / ES al 5 %** y la **probabilidad de una caída ≥ 10 % en 3 meses**?
Y si no, ¿qué parte de esto sí se puede demostrar y sirve para el motor macro y para B1?

**Idea clave para aprender.** La *dirección* de la bolsa a 1-3 meses es casi impredecible; su *volatilidad*, en cambio, es
muy persistente (un mes agitado suele ir seguido de otro agitado). Por eso aquí sí hay señal de sobra, y muchas más
observaciones que en el trabajo anual: ≈ 660 meses de evaluación en EE. UU. 1950-2004 frente a ≈ 80 episodios de recesión
en INT-10. Pero hay que separar **dos preguntas** (lección de INT-10):
1. **¿Ayuda la información?** (datos diarios en vez de mensuales; crédito, curva, VIX, régimen macro): se mide con un
   modelo **lineal** que usa esa información (HAR-X).
2. **¿Ayuda la capacidad?** (árboles, redes): se mide comparando el ML con el HAR-X **con la misma información**.
Solo la segunda es "ML de verdad". La primera es la que suele dar casi toda la ganancia.

## 1. Inventario (solo cobertura; `research/int/int12_potencia.json → inventario`)
Corte de desarrollo: **≤ 2004-12-31**. "Meses ≤ 2004" = meses con dato.

| papel | serie (warehouse) | frecuencia | desde | uso posible ≤ 2004 | notas PIT / calidad |
|---|---|---|---|---|---|
| **objetivo EE. UU.** | `aqr_mkt_usa_d` (mercado EE. UU., CRSP vía AQR, exceso sobre letra) | diaria | **1926-07** | 21.048 días, 941 meses | sin revisiones relevantes; exceso de rentabilidad (la vol. casi idéntica a la total) |
| objetivo, otros países | `aqr_mkt_<país>_d` (≈ 22 países) | diaria | 1984-1988 | 1991-2004 (168 meses) | **correlación contemporánea de log RV entre países 0,53 → 23 países valen ≈ 1,8** |
| objetivo, desarrollados | `ffx_dev_mkt_rf_d` (French Developed) | diaria | 1990-07 | 14 años | el universo de B1 |
| objetivo largo | `shiller_*` (S&P desde 1871), `ff_mkt_rf_m` (1926) | mensual | 1871 / 1926 | solo mensual | Shiller usa **medias mensuales de cierres diarios**: suaviza la volatilidad y crea autocorrelación artificial (efecto Working). **No sirve para RV**; para caídas solo con aviso |
| volatilidad implícita | `VIXCLS` | diaria | **1990-01** | 15 años | el VIX actual se **recalculó en 2003** hacia atrás; el que se veía en tiempo real era el VXO (no está). VVIX, SKEW, futuros: ≥ 2004 o casi |
| crédito | `BAA`, `AAA` (Moody's) | mensual | **1919** | 86 años | diario (`DBAA`, `BAA10Y`) desde 1986; TED 1986; CP 1997 |
| crédito / estrés compuesto | `NFCI` (1971), `fed_ebp` (1973), `STLFSI4` (1993), CISS zona euro (1980) | sem./mens./diaria | — | — | **re-estimados con toda la muestra: no son "as of"** → fuera del contraste |
| tipos y curva | `TB3MS` (1934), `GS10`/`GS1` (1953), `DTB3` (1954, diaria), `DGS10` (1962, diaria), `T10Y3M` (1982) | — | — | curva desde 1953 | tipos: no se revisan |
| incertidumbre | `USEPUINDXD` (1985, diaria) | diaria | 1985 | 20 años | índice de prensa, re-escalado |
| macro con vintages | `INDPRO`, `PAYEMS`, `CPIAUCSL`, `UNRATE`, `ICSA` | mens./sem. | 1919-1967 | sí | ALFRED: versiones "as of" disponibles |
| régimen / termómetro | motor INT-11 (régimen operable, anual JST), termómetro INT-4 (mensual ≤ 2004) | anual / mensual | 1870 / 1950 | sí | ya construidos ≤ 2004 |
| divisa para B1 | `bundesbank_usd_dem_d` (1948-1998) + `ecb_eurusd_d` (1999) | diaria | 1948 | sí | lo mismo que σ\* de B1 |
| precio en vivo | `SP500` (FRED) | diaria | 2016 | **no** | solo para la señal en vivo |

Qué **no** hay: datos intradía (la "volatilidad realizada" se construye con rendimientos **diarios**, más ruidosa que la de
la literatura con datos de 5 minutos); VXO antes de 1990; rendimientos diarios antes de 1926 (Schwert / Dow diario no están
en `~/financial_archive`).

**Muestras de evaluación posibles (fuera de muestra, orígenes a fin de mes):**
- A — EE. UU. 1950-2004 (entreno desde 1926): **660 meses**. B — 1960-2004: 540. C — 1975-2004: 360.
- D — con VIX: entreno 1990-1994, evaluación 1995-2004: **120 meses** (y 5 episodios de caída ≥ 10 %).
- E — panel de 16-23 países 1991-2004: 168 meses × países, pero con correlación 0,53 entre países.

## 2. Objetivos, listones y candidatos
**Objetivos** (orígenes = último día hábil de cada mes; objetivo con los días hábiles de los meses siguientes):
- **Y1 / Y2: volatilidad realizada a 1 y 3 meses**, RV = Σ r² de los días del periodo. Pérdida **QLIKE** = RV/f − log(RV/f) − 1
  (Patton 2011): es la que no se deja engañar por el ruido del proxy y no la dominan las crisis como el error cuadrático.
- **Y3: VaR y ES al 5 %** de la rentabilidad a 1 y 3 meses: pérdidas **pinball** (VaR) y **FZ0** (VaR y ES juntos;
  Patton, Ziegel y Chen 2019).
- **Y4: P(caída ≥ 10 % en 3 meses)**: la trayectoria toca −10 % desde el origen en algún momento de los 63 días. **Brier**.

**Recuentos reales (solo el objetivo; `objetivos_marginales_EEUU`):**

| muestra (orígenes ≤ 2004) | meses | vol. anual media | sd log RV 1 m | curtosis diaria | caídas ≥ 10 % en 3 m: orígenes con evento | episodios (meses a ≤ 3 de distancia) | años distintos |
|---|---|---|---|---|---|---|---|
| 1926-2004 | 941 | 16,7 % | 1,03 | 20,5 | 147 (15,7 %) | 39 | 38 |
| **1950-2004 (A)** | 659 | 13,5 % | 0,89 | 21,6 | 80 (12,2 %) | **25** | 24 |
| 1960-2004 (B) | 539 | 14,1 % | 0,91 | 21,2 | 75 (14,0 %) | 22 | 21 |
| 1990-2004 (≈ D) | 179 | 15,9 % | 0,91 | 7,2 | 24 (13,6 %) | **5** | 5 |

Lectura: para la **volatilidad** cada mes es una observación útil (≈ 660 en A); para la **caída ≥ 10 %** cuentan los
episodios, no los meses: **25 en 55 años** (5 en la era del VIX). Es el mismo problema de pocos eventos de INT-10.

**Listones** (los que hay que batir; todos con la misma información de rendimientos diarios salvo el de B1):
- **HAR** (Corsi 2009) en logaritmos con medias de r² de 5, 21 y 63 días, MCO, ventana creciente, re-estimado cada año.
- **GARCH(1,1) y GJR-GARCH** con t (fase 2; en esta simulación no se ajustan, el EWMA hace de representante).
- **EWMA λ = 0,94** (RiskMetrics).
- **σ̂ de B1**: varianza de los **12 últimos rendimientos mensuales**. Ojo: **B1 no usa EWMA**, usa una ventana de 12 meses
  con datos mensuales (docs/factors/paper_trading.md §2).

**Candidatos:**
- **HAR-X** (lineal; la pregunta de la información): HAR + diferencial BAA−AAA, pendiente de la curva, tipo corto,
  termómetro / régimen macro de INT-11 (y VIX solo en la muestra D).
- **ML de capacidad:** gradient boosting (histogramas, pocos árboles, pérdida cuantílica para VaR) y una red pequeña
  (MLP de 1 capa; LSTM solo si el usuario lo pide, ver D4), con **los mismos rasgos que HAR-X** + los rasgos HAR.
  Hiperparámetros fijados de antemano o elegidos **dentro** de cada ventana de entreno (validación anidada), nunca mirando
  la evaluación.

## 3. Potencia (simulación; `simulacion` en el JSON)
### 3.1 Método, en palabras
- **Proceso simulado** de volatilidad estocástica con 3 componentes (vidas medias ≈ 460, 23 y 2,4 días: valores de la
  literatura, **no** estimados aquí), colas gruesas (t de 6 g. l.) y efecto apalancamiento (los días malos suben la
  volatilidad). De los datos reales solo se toman **momentos marginales** del objetivo 1950-2004: volatilidad media
  (13,5 % anual), deriva y dispersión de log RV 1 m (0,89). Nunca la autocorrelación (eso sería mirar el resultado del HAR).
- En cada réplica se ajustan **de verdad** el HAR (con embargo: una fila de entreno solo vale si su objetivo acaba antes
  del origen), el EWMA y la σ̂ de B1. Hay además un **oráculo** que conoce el estado oculto: es el techo, nadie lo alcanza.
- El **"ML"** se representa como un punto intermedio entre el HAR y el oráculo: log f_ML = (1 − w) log f_HAR + w log f_oráculo
  + ruido de estimación (sd 0,05; sensibilidad 0,10). Variando w se recorre la ganancia en QLIKE de 0 al techo.
- **Contraste:** Diebold-Mariano unilateral al 5 % con varianza HAC (Newey-West, retardos = h − 1 + 4 (N/100)^{2/9}),
  con el **valor crítico de la nula simulada** (dos previsiones igual de buenas), como en INT-10. 300 réplicas (100 en el panel); error Monte Carlo de cada potencia ≈ ± 0,03 (± 0,05 en el panel). El tamaño real del DM con 1,645 sale 4-10 %; con el valor crítico simulado, 5 % por construcción.
- VaR, ES y P(caída) se sacan de la misma previsión de volatilidad con una **escala calibrada en la propia muestra para
  todos los modelos** (optimista para todos por igual): así se ve cuánto de la mejora en volatilidad llega a las colas.
- La MDE de todas las pérdidas se expresa **en ganancia de QLIKE** del mismo ML: "con un ML que mejora el QLIKE un x %,
  ¿detecto la mejora en el VaR?".

### 3.2 Resultados
**(a) Listones entre sí** (modelos reales ajustados en la simulación; ganancia = reducción relativa de la pérdida media):

| contraste (A: 1950-2004, 660 meses) | QLIKE 1 m: ganancia · potencia | QLIKE 3 m | pinball (VaR 5 %) 1 m | FZ0 (VaR+ES) 1 m | Brier caída 3 m |
|---|---|---|---|---|---|
| **HAR frente a σ̂ 12 m de B1** | **48 % · 100 %** | **55 % · 100 %** | 5,8 % · 58 % | 61 % | 1,3 % · 16 % |
| HAR frente a EWMA 0,94 | 19 % · 100 % | 37 % · 100 % | 1,3 % · 25 % | 17 % | 0,0 % · 4 % |
| oráculo frente a HAR (**techo**, inalcanzable) | 32 % · 100 % | 33 % · 100 % | 3,4 % · 41 % | 52 % | 2,2 % · 41 % |

La σ̂ de 12 meses es **peor que una previsión constante** en QLIKE (fracción del recorrido constante → oráculo > 1).

**(b) "ML" frente a HAR: MDE expresada en ganancia de QLIKE (80 %, un contraste)** y potencia si la ganancia en QLIKE es 2 / 5 / 10 %:

| escenario | meses (N efectivo de la diferencia) | QLIKE 1 m: MDE · pot. 2/5/10 % | QLIKE 3 m: MDE · pot. | pinball 1 m: pot. 2/5/10 % (techo) | FZ0 1 m: pot. (techo) | Brier 3 m: pot. 2/5/10 % (techo) |
|---|---|---|---|---|---|---|
| **A EE. UU. 1950-2004** | 660 (≈ 700; 3 m ≈ 350) | **2,0 %** · 79/99/100 | **3,2 %** · 64/96/100 | 12/31/54 (38) | 16/39/66 (49) | 10/22/40 (40) |
| B 1960-2004 | 540 | 2,0 % · 80/100/100 | 3,1 % · 64/96/100 | 12/30/55 (43) | 13/33/56 (45) | 14/25/41 (39) |
| C 1975-2004 | 360 | 2,2 % · 73/98/100 | 4,3 % · 48/88/100 | 12/26/40 (32) | 15/31/53 (38) | 12/19/28 (28) |
| D con VIX 1995-2004 | 120 | 4,4 % · 48/88/99 | 7,4 % · 27/62/89 | 4/10/15 (15) | 6/13/20 (21) | 7/8/8 (11) |
| E panel 16 países 1991-2004 | 168 × 16 (corr. 0,53) | 2,0 % · 79/100/100 | 1,9 % · 83/100/100 | **MDE 5,6 %** · 30/72/96 | MDE 5,6 % | 17/41/60 (53) |
| S1 = A con ruido del ML 0,10 | 660 | **3,6 %** · 44/95/100 | **5,6 %** · 34/73/99 | 9/20/40 (45) | 14/25/47 (53) | 11/17/28 (35) |
| S2 = A con menos dispersión (sd 0,70) | 660 | 1,9 % · 85/100/100 | 3,7 % · 57/95/100 | 13/29/53 (41) | 15/34/58 (45) | 14/22/36 (40) |

(Brier: columnas de 3 m; a 1 m la caída ≥ 10 % es rara, 2 %, y la potencia aún menor.)

### 3.3 Lectura
- **Volatilidad (QLIKE): hay potencia.** Con 1950-2004 se detecta una mejora del **2 % a 1 mes** y del **3 % a 3 meses**
  si el ML se parece mucho al HAR (ruido 0,05), y del **3,6 % / 5,6 %** si su ruido de estimación es el doble. Es decir:
  una mejora del 5 % se demuestra casi seguro; una del 2 % es una moneda al aire. Diez veces más observaciones efectivas
  que en INT-10, y por eso aquí el ML sí tiene una prueba posible.
- **Colas (VaR, ES, P de caída): no hay potencia.** Ni siquiera el **oráculo**, que mejora el QLIKE un 32 %, llega al 80 %
  en pinball, FZ0 o Brier con 660 meses (38-49 %). Un VaR al 5 % solo "aprende" de ≈ 33 excedencias, y la caída ≥ 10 % de
  25 episodios. Solo el panel de 16 países lo acerca (MDE 5,6 % en VaR a 1 mes), con países muy correlacionados.
- **El VIX no se puede usar en un contraste**: 120 meses de evaluación dan MDE 4,4-7,4 % en QLIKE y nada en colas.
- **Pasar de σ̂ de 12 meses (B1) a datos diarios** es una mejora enorme (≈ 50 % en QLIKE), detectable con potencia ≈ 100 %
  en cualquier muestra, también en 1995-2004. Ya en VaR la potencia baja a ≈ 58 %.
- Realismo de la simulación: reproduce la dispersión de log RV (0,87 frente a 0,89) pero tiene **menos curtosis** diaria
  (12 frente a 21) y **menos caídas** ≥ 10 % (9 % frente a 12 % de los orígenes). Colas reales más gordas → diferencias de
  pérdida más ruidosas → la potencia real en QLIKE puede ser algo **menor** que la de la tabla; en Brier, con más eventos,
  algo mayor (sigue lejos del 80 %).

## 4. Validación temporal (para la fase 2; todo ≤ 2004)
- **Ventana creciente**: entreno desde 1926-07 (los rasgos de crédito existen desde 1919; la curva completa desde 1953:
  los modelos con curva empiezan su entreno en 1953 y su evaluación en 1965, declarado). Re-estimación anual.
- **Embargo / purga**: una fila de entreno con origen d solo entra si su objetivo (d + h días) acaba antes del origen de
  evaluación; además 21 días de margen extra para rasgos con retraso de publicación.
- **"As of" de los rasgos**: macro con vintages ALFRED; crédito y tipos sin revisión con 1 día de retraso; termómetro y
  régimen tal como los da INT-11/INT-4 en desarrollo (fin de abril de t + 1 para lo anual). NFCI, EBP y STLFSI fuera.
- **Una sola corrida** con el prerregistro congelado (hash), procedencia (`src/intl/procedencia.py`), árbol limpio.
- **≥ 2005 BLOQUEADO**: no se usa para nada, ni para "ver si funciona".

## 5. Integración con el motor INT-11 y con B1
### 5.1 Con el motor macro (anual → mensual)
El motor INT-11 da, para el régimen de hoy, una **distribución** de la rentabilidad real a 1-5 años (sin predicción
puntual). El modelo de mercado no sabe nada de la dirección; sabe de la **escala** a corto plazo. Propuesta (sencilla y
comprobable):
1. **El macro fija el ancla**: para cada régimen operable, la varianza mensual de la bolsa en ese régimen (de las celdas del
   motor) es el **nivel de largo plazo** hacia el que revierte la volatilidad.
2. **El mercado fija el punto de partida**: el HAR/ML da la varianza de los próximos 1-3 meses. La trayectoria de varianza
   esperada mes a mes va del valor de mercado al ancla del régimen con la vida media del propio HAR (≈ 2-6 meses).
3. **Distribución a 1 año**: se re-escala la **dispersión** de las trayectorias del motor (no su centro) por
   κ = √(varianza anual de esa trayectoria / varianza anual del régimen). Si hoy el mercado está tranquilo, el abanico a
   1 año se estrecha un poco; si está agitado, se ensancha. A 2-5 años κ → 1 (el mercado ya no informa).
4. **Colas a 1-3 meses**: VaR/ES y P(caída ≥ 10 %) salen del modelo de mercado (residuos estandarizados de la propia
   historia), y el régimen entra como **rasgo** (HAR-X), no como regla.
Esto se puede evaluar sin gastar nada nuevo: la calibración del abanico a 1 año con y sin κ es un contraste más (descriptivo
hasta que INT-11 v2 pase su puerta de calibración).

### 5.2 Con B1
- Hoy B1 recorta la renta variable con σ̂ = volatilidad de **12 rendimientos mensuales**. La simulación dice que esa σ̂ es
  una previsión **muy pobre** de la volatilidad del mes siguiente (peor que una constante en QLIKE: 12 datos dan una
  varianza muy ruidosa) y que un HAR o un EWMA con datos diarios la mejoran ≈ 45-55 % en QLIKE, con potencia ≈ 100 %.
- Moreira y Muir (2017) usan precisamente la volatilidad diaria del último mes para sus carteras "gestionadas por
  volatilidad". El dato diario en vivo existe (`SP500` FRED + BCE).
- Pero **una mejor previsión de volatilidad no garantiza una mejor cartera**: B1 está acotada a [55 %, 70 %] y solo cambia
  con ≥ 2,5 pp; el efecto en la cartera (volatilidad, caídas) es otra pregunta, con mucha menos potencia (paper_trading
  §5: 36 meses no distinguen B1 de B0). Y cambiar σ̂ **cierra el paper trading actual** (§5) o exige una **B1′ en paralelo**.

## 6. Contaminación (declarada)
- **No se ha cruzado ningún predictor con ningún resultado.** Del objetivo solo se miraron recuentos y momentos marginales
  (nivel, dispersión, curtosis, caídas y episodios) y la correlación **contemporánea** entre países.
- P-DEV-FACT (B1) ya usó ≤ 2004 una volatilidad de 12 meses como señal de cartera (French mensual, 1963-2004): se miró
  el efecto en **cartera**, no la calidad de la **previsión** de volatilidad. σ\* = 17,02 % se calculó con esos datos.
- El termómetro y el régimen operable se construyeron ≤ 2004 (INT-4, Atlas §8, INT-11); nunca se cruzaron con la
  volatilidad. `INVENTARIO_relaciones.md` marca "volatilidad realizada → caídas": **sin probar**.
- Conocimiento de la literatura (no es contaminación de datos, pero se declara): que el HAR bate a la ventana de 12 meses
  y al EWMA a 1-3 meses es **conocido**; demostrarlo aquí es confirmar, no descubrir.

## 7. Veredicto honesto de potencia
- **Sí hay una prueba con potencia, pero solo para la VOLATILIDAD y solo para ganancias ≥ 3-5 %.** Con EE. UU. 1950-2004
  (660 meses), MDE en QLIKE ≈ 2-3,6 % a 1 mes y ≈ 3-5,6 % a 3 meses.
- **¿Es realista una ganancia de ese tamaño del ML sobre el HAR?** La literatura (de memoria, orden de magnitud) da
  2-10 % en QLIKE, casi toda por **información** (VIX, crédito, macro: Paye 2012; Christiansen, Schmeling y Schrimpf 2012;
  Christensen, Siggaard y Veliyev 2023) y poca por **capacidad**: con la misma información, el ML gana 0-3 % sobre un
  lineal bien hecho (Branco, Rubesam y Zevallos 2024: "nada bate claramente a los lineales"). Además sin intradía y sin
  VIX ≤ 1989, nuestra información es más pobre que la de esos estudios.
  → **Contraste de información (HAR-X frente a HAR):** potencia **razonable** (si gana 3-5 %, 80-99 %).
  → **Contraste de capacidad (ML frente a HAR-X):** potencia **insuficiente** para el efecto realista (2 %: 44-80 %).
- **Colas: sin potencia en ningún escenario de una sola serie.** VaR/ES/P(caída) se pueden producir y calibrar, pero no
  "demostrar que el ML las mejora". Se evaluarán por **calibración** (cobertura de excedencias, Kupiec/Christoffersen) y
  como consecuencia de la volatilidad.
- **Lo más útil y lo más seguro no es ML:** cambiar la σ̂ de 12 meses de B1 por una previsión diaria (HAR o EWMA).
  Potencia ≈ 100 %, pero es un resultado conocido (confirmación, no descubrimiento).

## 8. Decisiones del usuario (con mi recomendación)
| # | decisión | opciones | recomendación |
|---|---|---|---|
| D1 | ¿Fase 2 (prerregistro + corrida única ≤ 2004)? | sí / no | **Sí**, con la jerarquía de D2. Es la primera línea del proyecto donde el ML tiene una prueba con potencia razonable |
| D2 | Contrastes y orden (Holm sobre los confirmatorios) | — | **C1** HAR frente a σ̂ 12 m (QLIKE 1 m; confirmación de B1); **C2** HAR-X (crédito BAA−AAA, curva, tipo corto, termómetro/régimen) frente a HAR (QLIKE 1 m: la información); **C3** GB frente a HAR-X (QLIKE 1 m: la capacidad; declarado de potencia baja, 44-80 % para 2 %). Todo lo demás (3 m, VaR/ES, Brier, MLP, VIX) **descriptivo** |
| D3 | Muestra de evaluación | A 1950-2004 / B 1960-2004 | **A** (660 meses; entreno desde 1926). Los rasgos de curva empiezan en 1953: C2/C3 en 1965-2004 si los incluyen (≈ 480 meses, MDE ≈ 2,1-4 %, interpolado entre B y C) |
| D4 | Red neuronal | MLP pequeño / LSTM / ninguna | **Solo GB en el confirmatorio**; MLP descriptivo. Una LSTM con ≈ 900 meses es sobreajuste casi seguro y no añade potencia |
| D5 | Horizonte principal | 1 m / 3 m | **1 m** (más potencia; es el de B1). 3 m descriptivo |
| D6 | B1 | dejar / B1′ en paralelo / sustituir | **B1′ en paralelo** (σ̂ = HAR o EWMA diario en EUR, σ\* recalculada en la misma medida ≤ 2004), declarada antes de mirar; B1 sigue intacta. Sustituirla cerraría el paper trading |
| D7 | Integración con INT-11 | §5.1 / no | **§5.1** (ancla de régimen + re-escalado de la dispersión a 1 año), pero **después** de que INT-11 v2 pase su puerta de calibración; hasta entonces, descriptivo |
| D8 | ≥ 2005 | — | **Sigue bloqueado.** No se gasta en "¿gana el ML?" |
