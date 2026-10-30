---
documento: P-DEV-INT12 — prerregistro de la corrida de DESARROLLO del modelo de riesgo de mercado a 1-3 meses
version: 1.0 (2026-10-30) — CONGELADO en este commit, antes de escribir el código de la corrida
parte_de: docs/int/INT12_diseno_v0.md (fase 1, potencia: research/int/int12_potencia.json, commit 5e1bc93) + decisiones
          del usuario (30-oct, delegadas): todas las recomendaciones del §8 (D1-D8)
datos: SOLO ≤ 2004-12-31 (src/intl/data.load_dev). El periodo ≥ 2005 está BLOQUEADO y no se toca
---

# P-DEV-INT12 v1.0: ¿mejoran la previsión de la volatilidad a 1 mes (a) los datos diarios, (b) la información macro-financiera, (c) la capacidad del ML?

## 0. Naturaleza de esta corrida (leer primero)
- **Una sola corrida de desarrollo**, con datos ≤ 2004. El script se niega a correr si la salida ya existe o el árbol de
  git está sucio. Nada se ajusta después de ver resultados; una versión nueva exige prerregistro nuevo.
- **Qué es nuevo y qué no:** C1 (diarios frente a 12 meses) es un resultado conocido en la literatura: aquí se
  **confirma** en nuestra medida. C2 y C3 no se han mirado nunca en este proyecto (ningún rasgo se ha cruzado con la
  volatilidad futura; `INVENTARIO_relaciones.md`: "sin probar").
- **Potencia (fase 1):** C1 ≈ 100 %; C2 80-99 % si la información mejora el QLIKE ≥ 3-5 %; C3 **baja** (44-80 % para el
  2 % realista). Un "no establecido" en C3 es lo esperable y no demuestra que el ML no sirva.

## 1. Datos (todos con `load_dev`, ≤ 2004-12-31)
Se añaden a las familias permitidas de `src/intl/data.py` **solo** estas tres series (decisión de este prerregistro):
`aqr_mkt_usa_d` (mercado EE. UU., exceso diario, %, CRSP vía AQR), `TB3MS` (letra a 3 meses, mensual, 1934-),
`shiller_gs10` (tipo largo de Shiller, mensual; GS10 desde 1953, empalme antes). Ya permitidas: `BAA`, `AAA` (Moody's,
mensual, 1919-) y el panel anual JST (`src/intl/panel.anual`) para el régimen.

- **Rendimientos:** r_d = `aqr_mkt_usa_d` / 100 (exceso sobre la letra, en decimales).
- **Orígenes:** último día hábil de cada mes. **Evaluación: orígenes 1950-01 … 2004-11** (objetivo a 1 mes dentro de
  2004; N = 659). A 3 meses: 1950-01 … 2004-09 (N = 657).
- **Objetivo Y1:** RV = Σ r² de los días hábiles del mes siguiente. **Y2 (descriptivo):** los 3 meses siguientes.
  R = rentabilidad compuesta (1 + r) del periodo − 1. Caída: la trayectoria compuesta toca ≤ −10 % desde el origen.

## 2. Rasgos ("as of" en el origen del mes M)
- **HAR (diarios):** log de la media de r² de los últimos 5, 21 y 63 días hábiles hasta el origen (incluido).
- **X (información):**
  - `credito` = BAA − AAA (pp) del **mes M − 1**;
  - `curva` = `shiller_gs10` − `TB3MS` del mes M − 1; `corto` = `TB3MS` del mes M − 1;
  - `reg_infl` y `reg_brecha`: régimen operable de EE. UU. (INT-11 / Atlas §8; `src/intl/escenarios.estados_operables`,
    eje P3, con `inflacion` y `rgdpmad` de `panel.anual`): inflación del año > 3 % (0/1) y brecha P3 < 0 (0/1) del
    **último año conocido**: año Y − 1 si M ≥ abril del año Y; si no, Y − 2.
- Ninguna fila con un rasgo ausente entra en entreno ni en evaluación de los modelos que lo usan (en la evaluación no
  falta ninguno: X existe desde 1934).

## 3. Modelos (uno por horizonte; todos con el MISMO calendario de re-estimación)
- **B1-12m** (listón de B1, sin estimación): varianza muestral (ddof = 1) de los 12 últimos rendimientos mensuales
  compuestos; previsión a h meses = h × esa varianza.
- **HAR:** MCO de log(RV / n_días) sobre [1, rasgos HAR]; previsión = n_días del periodo × exp(ajuste) × media de
  exp(residuo) del entreno (Duan).
- **HAR-X:** igual que HAR con [rasgos HAR + X].
- **GB:** `sklearn.ensemble.HistGradientBoostingRegressor(loss="squared_error", learning_rate=0.05, max_iter=300,
  max_depth=3, min_samples_leaf=20, l2_regularization=1.0, early_stopping=False, random_state=20261030)` sobre
  log(RV / n_días) con [rasgos HAR + X]; misma corrección de Duan. **Hiperparámetros fijados aquí; no hay búsqueda.**
- Descriptivos: **EWMA** λ = 0,94 (previsión n_días × σ²_{d+1}); **MLP** `MLPRegressor(hidden_layer_sizes=(16,),
  alpha=0.01, max_iter=2000, random_state=20261030)` con rasgos estandarizados en el entreno, igual que GB.
- **Entreno:** todas las filas mensuales con origen ≥ 1934-02 (primer mes con X completo) cuyo objetivo **acaba antes
  o en** el día del origen de la re-estimación (embargo: ninguna fila cuyo objetivo se solape con el futuro). Se
  re-estima **cada enero** (y el primer origen de evaluación); HAR, HAR-X y GB usan exactamente las mismas filas.

## 4. Contrastes confirmatorios (QLIKE, horizonte 1 mes)
QLIKE(f, RV) = RV/f − log(RV/f) − 1. d_t = QLIKE(listón) − QLIKE(retador); ganancia = 1 − media(L_retador) / media(L_listón).
- **C1:** HAR frente a B1-12m. **C2:** HAR-X frente a HAR. **C3:** GB frente a HAR-X.
- **Prueba:** Diebold-Mariano unilateral (retador mejor), varianza HAC de Newey-West (Bartlett) con
  L = ⌊4 (N/100)^{2/9}⌋ = 6 retardos; p = 1 − Φ(t).
- **Multiplicidad:** Holm sobre {C1, C2, C3}, α = 0,05 familiar.
- **"Establecido"** = Holm rechaza **y** la ganancia es > 0 en las dos mitades de la evaluación (orígenes 1950-01 …
  1977-06 y 1977-07 … 2004-11). Si Holm rechaza pero una mitad tiene signo contrario: "no establecido (inestable)".
- Se publican siempre: ganancia, t, p bruto y de Holm, IC 95 % de la diferencia media (NW), ganancias por mitad.

## 5. Descriptivos (no deciden nada)
- Los tres contrastes a **3 meses** (L = 2 + 6 = 8) y EWMA / MLP frente a sus listones naturales (EWMA frente a HAR;
  MLP frente a HAR-X).
- **VaR / ES al 5 %:** VaR = −k_v √f, ES = −k_e √f, con k_v, k_e de los rendimientos estandarizados R/√f de las filas
  de entreno (ajuste dentro de muestra) en cada re-estimación. Pinball, FZ0, tasa de excedencias y prueba de Kupiec.
- **P(caída ≥ 10 % en 3 meses):** logística de la caída sobre log f de cada modelo, ajustada en las filas de entreno en
  cada re-estimación; Brier y log score; recuento de episodios.
- p por bootstrap de bloques estacionario (bloque medio 12, 2.000 réplicas, semilla 20261030) de C1-C3: sensibilidad.
- Importancia por permutación de GB en el último ajuste: solo descriptiva.

## 6. Qué NO se hace
- Ningún dato ≥ 2005. Ningún otro rasgo (VIX, NFCI, EBP, CISS…). Ninguna búsqueda de hiperparámetros. Ninguna LSTM.
- No se repite la corrida si un resultado no gusta. Errores de código que impidan correr: se arreglan **antes** de la
  corrida (con `--sintetico`); un error descubierto **después** se documenta y la corrección es una versión nueva
  declarada.

## 7. Consecuencias decididas de antemano
- **B1′** (`docs/factors/B1prima_spec.md`): se abre en paralelo **solo si C1 queda establecido**; B1 no se toca.
- **Integración con INT-11** (§5.1 del diseño): solo si INT-11 v2 pasa su puerta de calibración; si C2 establece que el
  régimen/crédito/curva ayudan, el ancla de régimen de §5.1 queda justificada; si no, el ancla es solo la media de largo
  plazo del HAR.
- C3 no establecido → el modelo operativo es el lineal (HAR o HAR-X); el ML queda como descriptivo.
