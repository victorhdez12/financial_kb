---
documento: revisión del diseño económico de las specs a priori del pool (commit 1a5f1f9)
fecha: 2026-10-24
autor: Estratega macro
objeto: docs/models/m2_structural_spec.md v1.0, m3_tvtp_spec.md v1.0, pool_spec.md v1.0, p_eval_base_v4_draft.md (v4 borrador), power_holdout.md v1.0
antecedente: docs/reviews/2026-10-23_estratega_macro_m1v2.md (propuse el Markov TVTP del eje G y el nowcast estructural de G)
datos_leidos: ninguno. Ni la etiqueta ni ningún dato (tampoco ≤ 2004). Solo specs, la ficha de la etiqueta, la documentación de la base PIT (definición de variables) y la Bitácora
---

# Revisión del diseño económico de las specs del pool

**Alcance.** Reviso solo el diseño económico: los mecanismos, los signos, los horizontes y si las variables cuadran con
la etiqueta. La corrección técnica y el PIT son cosa del Validador. Las decisiones ya tomadas por el usuario no se
reabren: pool {M0, M2, M3} con beta, Holm k = 1, IC 95 % y ≥ 0,05 nats, criterio de signos alternativo, `levels_at`,
`incluye: []`, bloqueado 2005-01 reservado, `baa_gap10y` fuera y eje I = M0.

**Este documento se commitea antes de cualquier corrida de desarrollo de M2, M3 o el pool.** Las predicciones de §4
son, por tanto, a priori. La marca de tiempo del commit lo demuestra.

## Veredicto por spec

| spec | veredicto | motivo principal |
|---|---|---|
| `m2_structural_spec.md` | ⚠️ | El diseño es bueno, pero la ecuación de medida de las peticiones de paro está mal: trata un **flujo** como si fuera un **stock** (§1.2). Es imprescindible corregirla y obliga a un push v1.1. |
| `m3_tvtp_spec.md` | ✅ (condicionado) | Las variables, los signos, las previas, λ y el ancla tienen sentido. No hay riesgo de signos al revés. Hereda la corrección de M2 por la emisión. Falta fijar qué cuenta como "γ > 0" (§2.4). |
| `pool_spec.md` | ✅ | La previa y N<sub>min</sub> son razonables. Ojo: en la práctica es un pool de 2 bloques (M0 frente al factor) y su ventana de desarrollo no incluye 1980 ni 1981-82 (§3). |
| `p_eval_base_v4_draft.md` | ⚠️ | Le falta reflejar la decisión del usuario sobre los signos: A1-3 y A3 todavía dicen "sin criterio de signos". Hay que escribir el criterio 8 con su clave y su umbral numérico. Es solo de texto. |
| `power_holdout.md` | ✅ | El cálculo es correcto. El supuesto "ruido ×0,5" para el pool es optimista si la beta extremiza (§4.1). |

## 1. M2: ¿el factor captura bien los 2/3 de G(t) que son previsión?

### 1.1 Qué puede y qué no puede capturar

- **El reparto de la ventana.** G(t) pesa las tasas mensuales de t−3 a t+4 con (1, 2, 3, 3, 3, 3, 2, 1)/18. Para
  INDPRO y PAYEMS (las dos que se publican antes) se reparte así:
  - **conocido** (t−3 … t−1): 6/18;
  - **mes t**: 3/18, el *nowcast* puro;
  - **t+1**: 3/18;
  - **t+2 … t+4**: 6/18.
- **Lo que el factor sí aporta.** Las peticiones de paro y Filadelfia del propio mes t informan de f<sub>t</sub>. Con eso
  el factor puede cubrir bien el 3/18 del mes t y una parte del de t+1. Esa es la parte de la ventana donde hay
  información real.
- **Lo que no aporta.** Un AR(2) de un factor **coincidente** no prevé tasas mensuales a 2-4 meses mucho mejor que su
  media. Así que el 6/18 de t+2 … t+4 se rellenará cerca de la tendencia, y su incertidumbre irá a σ̂.
  - Esto es correcto: es la respuesta honesta a "¿qué se sabe en t?".
  - Pero significa que, en la práctica, M2 "conoce" ≈ 55-60 % de la ventana, no el 100 %.
  - El resto lo cubre σ̂, y la calibración por la aritmética de la etiqueta (Φ(Ĝ/√(σ̂² + s<sub>G</sub>²))) es la forma
    correcta de tratarlo.
- **Para W875RX1 y CMRMTSPL** (se publican más tarde) la parte conocida es menor. Dependen más del factor, lo cual está
  bien: es justo lo que hace un factor.
- **Conclusión.** La estructura (composición exacta, horizonte hasta t+4, varianza conjunta, V<sub>rev</sub>,
  V<sub>tend</sub>) está bien diseñada. El techo de M2 lo marca la información disponible, no el diseño.

### 1.2 Imprescindible: la ecuación de medida de las peticiones de paro está al revés en el tiempo

- **Qué dice la spec** (§3): x<sub>c,m</sub> = λ<sub>c</sub>·(1/12)·Σ<sub>k=0..11</sub> f<sub>m−k</sub>. Es decir, la
  tasa interanual de las peticiones es proporcional a la **media de crecimiento del último año**.
- **Esa forma sirve para un stock, no para un flujo.**
  - Sería la forma correcta para un stock como la tasa de paro. Por Okun, Δ12 u ≈ −Σ de los 12 desvíos de
    crecimiento.
  - Las peticiones iniciales son un **flujo**: los despidos nuevos de la semana. Su **nivel** se mueve con el ritmo
    de crecimiento **del mes**, ln C<sub>m</sub> ≈ a − b·f<sub>m</sub>. Así las trata el índice ADS
    (Aruoba-Diebold-Scotti), con una carga contemporánea sobre el nivel.
- **La forma correcta.** La variable de la base es `rolling_log_yoy` de la media de 4 semanas (`pit_base.md`):
  ln C<sub>m</sub> − ln C<sub>m−12</sub>. Por tanto:

      x_c,m = λ_c·(f_m − f_{m−12}) + u_c,m + ε_c,m          (λ_c < 0 esperado; estado con retardos 0…12 de f)

  Equivale a Σ<sub>k=0..11</sub> Δf<sub>m−k</sub>: la suma de los **cambios** del factor, no de sus niveles.
- **Por qué importa justo donde M2 tiene que ganar:**
  1. **Inicio de una recesión.** f<sub>m</sub> cae y f<sub>m−12</sub> todavía es positivo. La forma correcta predice
     una tasa interanual de las peticiones muy positiva, que es lo que se observa. La forma de la spec predice ≈ 0
     (la media del año sigue alta). Para explicar el salto, el filtro tiene que inventar un f<sub>m</sub> enorme (con
     peso 1/12) o tirar el dato al idiosincrático.
  2. **Inicio de la recuperación.** f<sub>m</sub> > 0 y f<sub>m−12</sub> ≪ 0. La forma correcta da una tasa
     interanual muy negativa, que es lo que se observa: las peticiones caen con fuerza respecto al pico de la
     recesión. La forma de la spec espera una tasa **positiva**, porque la media del año aún es negativa. Lee al revés
     la mejor señal de salida que tenemos.
  3. **Retraso.** Con la media de 12 meses, la serie se comporta como un indicador **retrasado** (≈ 6 meses), cuando
     en realidad es de los pocos **adelantados** en los valles.
- **El MLE no lo arreglará solo.** Lo más probable es que estime λ<sub>c</sub> ≈ 0 y ρ<sub>c</sub> ≈ 0,99, y la serie
  quede fuera en silencio. O, peor, que meta un sesgo en los giros. Es el mismo tipo de error de M1 (stock frente a
  flujo, §1.2 de mi revisión del 23-oct), esta vez en la ecuación de medida.
- **Qué hay que cambiar:**
  - **M2 §3:** ecuación de medida f<sub>m</sub> − f<sub>m−12</sub>.
  - **M2 §3, estado aumentado:** retardos 0…12 de f; dimensión 47 en lugar de 46.
  - **M2 §1:** el signo esperado no cambia (λ<sub>c</sub> < 0).
  - El arranque determinista con componentes principales no cambia.
  - **M3:** hereda el cambio a través de la emisión y su texto no se toca.
  - **Filadelfia:** su carga contemporánea sobre f<sub>m</sub> es correcta. El índice de difusión de nuevos pedidos
    mide el **cambio** del mes, que es un flujo.
- **Coste:** un push a priori **v1.1** de `m2_structural_spec.md`, con la fila del cambio en §9 y "qué se había visto:
  nada (sin implementación ni datos)". Todavía no hay código ni contacto con la etiqueta, así que el cambio es
  limpio.

### 1.3 ¿Falta o sobra alguna serie (en tiempo real antes de 2005)?

- **No sobra ninguna.** Las 4 coincidentes son obligatorias para la composición. Filadelfia es el único dato de
  actividad del mes t junto con las peticiones (S-PIT-001 ya trata su linaje antes de 1990-07).
- **Lo que falta, con mecanismo claro, sería:**
  - **(a) Horas semanales en manufacturas (`AWHMAN`).** Se publican con PAYEMS y están en la vintage desde los años
    60. Las empresas ajustan las horas antes que la plantilla: adelantan PAYEMS e INDPRO 1-3 meses. Es un componente
    clásico del índice adelantado.
  - **(b) Nuevos pedidos del ISM/NAPM (nacional).** Mismo mecanismo que Filadelfia, con más señal. Pero su licencia
    y su disponibilidad PIT son dudosas.
- **Los dos exigen datos nuevos en la base.** Eso choca con la decisión del usuario de no hacer una v0.5. **No los
  propongo ahora.** Los dejo anotados como la extensión natural si el pool fallara por falta de señal a 1-3 meses.
- **No añadiría:**
  - permisos de vivienda: horizonte de 6-12 meses, el mismo error de horizonte que M1;
  - paro (Δu): redundante con PAYEMS y las peticiones;
  - curva, crédito o bolsa: van en M3, en la transición, que es su sitio.

### 1.4 Otras observaciones sobre M2 (no imprescindibles)

- **Tendencia hacia atrás en el factor y centrada en la composición.** Es coherente: el factor solo prevé desvíos y la
  diferencia de tendencias va a V<sub>tend</sub>. Bien.
- **Asimetría.** Un factor gaussiano AR(2) se queda corto en las caídas bruscas y en los rebotes (*plucking*). σ̂ lo
  cubre en parte. El *plucking* queda fuera por decisión previa. No lo reabro.
- **V<sub>rev</sub>.** Supone revisiones independientes entre meses. Las revisiones de referencia anuales de PAYEMS
  están correladas positivamente entre meses, así que V<sub>rev</sub> está algo infraestimada. Es un efecto pequeño.
  Opcional.

## 2. M3: transiciones, signos, previa, templado y ancla

### 2.1 Variables y signos: tienen sentido y no hay riesgo de relaciones al revés

| término | mecanismo | ¿estable entre fases? | riesgo |
|---|---|---|---|
| −γ1·z(`curve_min12`) en la salida de A | una inversión reciente eleva el riesgo de caída (Estrella-Mishkin) | es un "stock de aviso", pero **solo se usa partiendo de A**, que es donde tiene sentido | el `min12` sigue invertido unos meses tras volver a A (1980 → 1981). Va en la dirección correcta: hubo doble recesión |
| +γ2·z(`baa_d6m`) en la salida de A | el crédito empeora al entrar (Gilchrist-Zakrajšek) | sí (flujo) | falsa alarma en 1998 (LTCM), que la emisión debe frenar |
| −γ3·z(`baa_d6m`) en la salida de B | la compresión del crédito anuncia la salida | sí (flujo) | el menos identificado (≈ 4-5 salidas) |
| +γ4·z(`eq_ret_6m`) en la salida de B | la bolsa toca fondo ≈ 3-5 meses antes del valle | sí (flujo) | "falso amanecer" en las recuperaciones sin empleo (1991, 2002), que la emisión debe frenar |

- **No hay riesgo de relaciones al revés como en M1.** En M1 el problema era usar stocks de daño (la Sahm,
  `baa_gap10y`) en una logística lineal y común a todas las fases. Aquí:
  - los flujos tienen el signo estable que vi en el C5 del 23-oct;
  - el único "stock" (`curve_min12`) solo actúa en la salida de A;
  - el signo de la bolsa no se usa en A, así que el crack de 1987 no genera falsas alarmas.
- **El *plucking* sigue fuera, y aun así está cubierto en parte.** Un rebote proporcional a la profundidad de la caída
  se refleja en la compresión del crédito y en el rebote de la bolsa, que son mayores tras las caídas hondas. γ3 y γ4
  recogen así parte del *plucking* con el signo correcto, sin una variable de profundidad.

### 2.2 Previa N(0; 0,5²), γ ≥ 0

- **Qué permite la previa.** Un γ de 0,5 multiplica las odds por 1,65 por cada desviación típica. La literatura da a la
  curva un efecto mayor, del orden de ×3 por desviación típica (γ ≈ 1,1). La previa lo encoge, pero no lo impide: con
  ≈ 5 eventos, el MAP quedará en 0,3-0,7.
- **No la cambiaría.** Hacerlo ahora, por mecanismo y sin datos, sería legítimo, pero con ≈ 5 eventos por logística el
  riesgo de sobreajuste pesa más que el sesgo. ✅

### 2.3 Templado λ = 1/3 y ancla PIT

- **λ = 1/3 es razonable.** Las Ĝ<sup>rt</sup> de meses consecutivos comparten ≈ 7/8 de las tasas, así que en 5 pasos
  hay ≈ 1,5-2 "observaciones" independientes. Las sensibilidades 1/6 y 1/2 cubren el rango. ✅
- **Ancla en el `label_month` de la persistencia (h ≈ 5).** Es correcta y es la que propuse.
  - Hay un pequeño doble cómputo: π<sub>a</sub> ya contiene tasas de a−3 … a+4, que se solapan con lo que miden las
    emisiones a+1 … m.
  - El templado y la capa de calibración lo absorben. ✅
- **Emisión real-time "congelada".** Para s < m se usa la Ĝ<sup>rt</sup><sub>s</sub> de la fecha s, no un nowcast
  actualizado. Se pierde algo de información, pero es la misma cantidad en entrenamiento y en predicción. Es la
  elección correcta para un preregistro. ✅

### 2.4 Riesgos económicos de M3 (sin cambio de spec)

- **Parpadeos de la etiqueta.**
  - Los estados son la etiqueta dura (p ≥ 0,5). G "frente a la tendencia" cruza 0 en desaceleraciones sin recesión
    (1984-86, 1995, 1998) y parpadea cerca de 0 (1991-93, 2002-03).
  - Esos cruces no los mueven la curva ni el crédito. Inflan α (la tasa base de salida) y diluyen γ.
  - Resultado esperado: γ pequeños y M3 ≈ `m3_ctp_g`, salvo en las recesiones de verdad.
  - Usar transiciones "blandas" (recuentos esperados con p<sub>g_high</sub>) sería mejor en teoría. Es **opcional y
    no lo recomiendo ahora**: sería otro cambio de spec por un efecto de segundo orden.
- **Qué significa "γ > 0" en el criterio de signos.** El usuario eligió como criterio "γ > 0 en ≥ 50 % de los
  cortes".
  - Con cotas en L-BFGS-B, un γ que la verosimilitud empuja hacia lo negativo termina **en** 0 o en 1e-9, según la
    tolerancia. Un γ que apenas aporta queda en 1e-4.
  - **Imprescindible** fijar el umbral antes de la corrida de desarrollo. Propongo **γ<sub>j</sub> > 0,01** (en
    unidades de z: un efecto de odds de 1 %; por debajo, "pegado a 0").
  - Hay que escribirlo en M3 §5, en M3 §8-2 y en el criterio 8 de P-EVAL v4.
  - Es una aclaración, no un cambio de diseño. Puede ir en el mismo push v1.1.
- **El γ con más riesgo de fallar el criterio es γ3** (crédito en la salida de G bajo), con la menor identificación.
  Mi predicción a priori está en §4.3.

## 3. El pool

- **Dirichlet con moda (½, ¼, ¼), κ = 20** (α = (11, 6, 6)).
  - Pesa ≈ 20 meses frente a 60-250 de datos en desarrollo y ≈ 300-500 en el bloqueado: los datos mandan pronto.
  - Encoge hacia M0 lo justo. ✅
- **N<sub>min</sub> = 60.** Razonable. Además tiene una ventaja económica no buscada: el pool se activa en ≈ 1984 con
  pesos estimados sobre 1978-83, que incluye las recesiones de 1980 y 1981-82, las más ricas en giros. ✅
- **Correlación de errores M2-M3.** Es alta: comparten la emisión y el factor. El pool funciona en la práctica como
  **dos bloques**: M0 (persistencia, se equivoca en los giros con ≈ 4 meses de retraso) frente al factor (se equivoca
  en las falsas alarmas y por exceso de confianza).
  - El reparto entre M2 y M3 está casi sin identificar. La previa lo regulariza, así que no es un problema.
  - El total de peso fuera de M0 sí está identificado. Ahí está todo el valor, y es real: los errores de M0 y del
    factor se concentran en meses distintos.
  - El pool **sí** puede aportar.
  - M3 dentro del pool añade poco frente a M2, salvo en las salidas de G bajo de las recesiones en V.
  - No pido cambios.
- **Riesgo de régimen de datos (sin cambio).**
  - Antes de 2005, W875RX1, CMRMTSPL y las peticiones entran como latest_truncated, es decir, más limpias que en
    tiempo real.
  - En el bloqueado pasan a vintage desde 2009-05, 2010-05 y 2013-06.
  - Los pesos aprendidos antes de 2005 sobreponderan algo al factor justo cuando sus datos empeoran.
  - Para la puntuación, V<sub>rev</sub> = 0 con datos latest_truncated es correcto: el objetivo también usa datos
    finales. El problema es solo de pesos. Lo informo y no pido cambios.
- **Ventana de desarrollo del pool: 1985-01 → 2004-12.**
  - Solo contiene **2 recesiones** (1990-91 y 2001) y las desaceleraciones de 1985-86, 1995 y 1998.
  - **1980 y 1981-82 solo se ven en M2 y M3** (ventana larga desde W<sub>G</sub>).
  - Por eso la "puerta de gasto" (mejora < 0,05 → no registrar) se decide con 2 recesiones y es muy ruidosa. Conviene
    que el usuario lo sepa al leerla (§6, decisión 3).

## 4. Potencia, expectativa y predicciones falsables

### 4.1 Expectativa realista

- **Dónde puede ganar el pool.** En los meses de giro (≈ 25 %), M0 llega tarde ≈ 4 meses. El factor puede recortar
  2-3 meses del retraso.
- **Cuánto puede ganar.** Con una ganancia de ≈ 0,3-0,5 nats por mes de giro y un peso fuera de M0 de ≈ 0,4-0,6 (más
  la beta), y una pérdida de −0,01 a −0,02 en los estables por las falsas alarmas, la media esperada del pool frente a
  M0 queda en **≈ +0,03 a +0,07 nats**.
- **Frente al MDE.** Está por debajo del MDE de 0,12-0,15 y cerca del umbral observado (≈ 0,10, o 0,05-0,07 si el ruido
  baja a la mitad).
- **Probabilidad de pasar el criterio 1: ≈ 20-35 %.** Coincido con A7: **lo más probable es "M0 sigue"**, aunque el
  diseño funcione.
- **El supuesto "ruido ×0,5" es optimista.** Si la beta extremiza (a, b > 1), el ruido de d no baja en proporción a w.
  Lo esperable está entre ×0,6 y ×0,8.

### 4.2 Predicciones falsables a priori (escritas sin ver la etiqueta ni ningún resultado)

Con "giro de G" me refiero a los giros v2.1 del arnés. Las fechas de abajo son la cronología **pública** del NBER, que
sirve de orientación; la entrada y la salida de G pueden adelantarse a ella. d = ll(M0) − ll(modelo), y > 0 significa
que el modelo es mejor. **Si el diseño funciona:**

| # | episodio | modelo | predicción | falsa si |
|---|---|---|---|---|
| P1 | **1980** (pico 1980-01, valle 1980-07; caída y rebote bruscos: controles de crédito, pico de las peticiones en primavera) | M2, M3 | d > 0 en la **entrada** (k = 0 … +4 desde el giro A→B) y en la **salida** (k = 0 … +4 desde B→A). Es el episodio de mayor ganancia por mes, junto con 2001 | d medio ≤ 0 en la entrada o en la salida |
| P2 | **1981-82** (pico 1981-07, valle 1982-11) | M3 | **entrada:** d > 0 en k = 0 … +4 (`curve_min12` muy invertida). **Antes:** coste de falsa alarma en los meses A de 1980-11 … 1981-06 (d < 0 para M3 y menor para M2). **Salida:** d > 0 (rally desde 1982-08 y compresión del crédito) | d ≤ 0 en la entrada o en la salida de M3 |
| P3 | **1990-91** (pico 1990-07, valle 1991-03; entrada gradual tras una desaceleración en 1989, recuperación sin empleo) | pool | **entrada:** ganancia pequeña (0 < d < ganancia de 2001). **Salida y 1991-04 … 1992-12:** sin ganancia (d ≈ 0, ≥ −0,05 de media); M3 puede perder por un "falso amanecer" de la bolsa | d medio < −0,05 en 1991-04 … 1992-12, o ganancia en la entrada mayor que en 2001 |
| P4 | **2001** (pico 2001-03, valle 2001-11; IP cae desde finales de 2000, peticiones al alza, Filadelfia negativa, curva invertida en 2000) | pool, M2, M3 | **entrada:** d > 0 con claridad en k = 0 … +4: la mayor ganancia de la ventana del pool. **Salida (2002-03, sin empleo):** d ≈ 0 | d medio ≤ 0 en la entrada |
| P5 | **Estables** de la ventana del pool | pool | d entre −0,03 y 0. Las posibles falsas alarmas (1998: LTCM, crédito; 1995) cuestan poco en el pool | d medio < −0,05 en los estables |
| P6 | **1987** (crack) | M3 | sin falsa alarma: la bolsa no entra en la salida de A | M3 cruza 0,5 hacia "G bajo" a finales de 1987 sin que haya giro |

**Predicciones agregadas (desarrollo):**
- **P7.** Las ganancias del pool y de M2 se concentran en las **entradas** (A→B), sobre todo las bruscas (1980, 2001).
  En las salidas solo ganan en las recuperaciones en V (1980, 1982-83).
- **P8.** Pool − M0 en su ventana: **+0,01 a +0,06 nats**. `sd_mensual` de d del pool ≈ 0,5-0,8 veces la de M2.
- **P9.** M3 − `m3_ctp_g`: ≤ +0,02 nats en total, con la ganancia concentrada en 1981 (entrada) y 1980/1982 (salida).
- **P10.** Fracción de cortes con γ > 0,01: **γ1 (curva) ≥ 50 %** con alta probabilidad; γ2 y γ4 en torno al 50 %;
  **γ3 (crédito, salida de B) < 50 %** con probabilidad ≈ 0,5.
  - Es un aviso para el usuario: el criterio de signos que eligió puede tumbar el pool por un componente con poco
    peso.
  - La decisión está tomada y no la reabro. Solo la cuantifico.
- **P11.** Pesos del pool en 2004-12: w<sub>M0</sub> ∈ [0,35; 0,7]; w<sub>M2</sub> + w<sub>M3</sub> el resto; la beta
  con a, b ≥ 1.
- **Prueba del mecanismo.** Si **ni** 1980 **ni** 2001 muestran ganancia en la entrada (P1 y P4 falsas), el mecanismo
  (información del mes t sobre la ventana de G) no funciona. Entonces no tiene sentido gastar el bloqueado, sea cual
  sea la media.

## 5. Cambios propuestos (todos antes de la corrida de desarrollo)

**Imprescindibles** (un solo push a priori v1.1, antes de implementar nada que lea datos):

1. **M2 §3:** la ecuación de medida de `claims_4w_yoy` pasa a λ<sub>c</sub>·(f<sub>m</sub> − f<sub>m−12</sub>), con el
   estado aumentado a 13 retardos de f (§1.2). **Obliga a reescribir la spec de M2 (v1.1, nuevo push a priori).** M3 y
   el pool no cambian de texto.
2. **Umbral "γ > 0" = γ > 0,01** en M3 §5 y §8-2, y en P-EVAL v4 (§2.4). Es una aclaración y puede ir en el mismo push.
3. **P-EVAL v4:**
   - pasar la decisión del usuario sobre los signos a A1-3 (fila nueva: "se mantiene, en forma γ > 0,01 en ≥ 50 % de
     los cortes, decisión del usuario 24-oct");
   - añadir a A3 un **criterio 8** con clave (p. ej. `report["coeficientes"]["vintage/m3_tvtp_g"]["frac_pos"]["G:gammaj"]
     ≥ 0,5` para j = 1…4);
   - actualizar A8 (`expected_signs`) y A9-4.
   - Es solo de texto y no afecta a la corrida de desarrollo, pero conviene cerrarlo en el mismo push.

**Opcionales** (no obligan a nada si no se hacen):

4. Incluir el **pool y M2** en el estudio de eventos k = −6 … +8 (hoy solo en M3 §5) e informar d por los episodios de
   §4.2. No cambia ningún criterio. Puede ir en el push v1.1.
5. Transiciones blandas en M3 (§2.4). **No lo recomiendo ahora.**
6. Series adicionales (`AWHMAN`, ISM): solo si el pool fallara por falta de señal a 1-3 meses. Requiere datos nuevos.
   **No ahora.**
7. Correlación de las revisiones en V<sub>rev</sub>: efecto pequeño. **No ahora.**

## 6. Decisiones del usuario

1. **Corregir la ecuación de medida de las peticiones de paro en M2** (f<sub>m</sub> − f<sub>m−12</sub>, push v1.1 a
   priori). **Recomiendo sí**: con la forma actual, la serie se lee al revés al principio de la recuperación y con
   retraso al entrar.
2. **Fijar el umbral del criterio de signos en γ > 0,01** y escribir el criterio 8 en P-EVAL v4. **Recomiendo sí.**
3. **Saber al leer la "puerta de gasto"** que la ventana de desarrollo del pool solo tiene 2 recesiones (1990-91,
   2001), y que 1980 y 1981-82 solo se ven en M2 y M3. **Recomiendo** leer la puerta junto con los episodios de §4.2,
   sin cambiar N<sub>min</sub> ni la regla.
4. **Estudio de eventos para el pool y M2** (opcional 4). **Recomiendo sí**, porque es barato y hace comprobables P1-P7.
5. **Expectativa:** probabilidad ≈ 20-35 % de pasar el criterio 1 aunque el diseño funcione (§4.1). Nada que decidir
   ahora; conviene asumirlo antes de gastar el bloqueado.

No he leído ningún dato ni la etiqueta, no he modificado código ni specs y no he registrado nada.
