---
documento: revisión de literatura (ampliación) — autoencoders y métodos de descubrimiento de relaciones ocultas o causales
fecha: 2026-10-23
autor: Investigador
encargo: ampliación pedida por el usuario sobre docs/research/2026-10-23_mejoras_nowcast_regimen.md
datos: ninguno. No he leído la etiqueta, ni datos ≥ 2005, ni corrido modelos, ni tocado código
aviso: la sesión llegó al límite de búsquedas web antes de cubrir todo. Lo que no pude comprobar hoy va marcado "(no verificado hoy)"
---

# Autoencoders y relaciones ocultas: ¿aportan algo a nuestro nowcast?

## 0. Veredicto corto

- **Autoencoders.** La evidencia seria fuera de muestra y en tiempo real (Andreini, Izzo y Ricco, D2FM) existe,
  pero: (a) es para el **PIB** con un panel de **≈ 130 series**; (b) su periodo de evaluación es **2006-2020**, es
  decir, **todo nuestro bloqueado**; (c) su propio Monte Carlo dice que, si el proceso es lineal, el D2FM **empata**
  con el DFM. Con nuestro panel de 4-6 series la ganancia esperada es pequeña. Va como **sensibilidad anidada del
  DFM lineal**, con arquitectura fijada a priori, **detrás** de las cinco ideas del ranking anterior.
- **Error de reconstrucción como alerta.** No he encontrado **ninguna** evaluación fuera de muestra frente a
  recesiones ni a giros macro. Lo que hay es de mercados (2012-2019) o de sistemas de pago, siempre después de 2005.
  En el aprendizaje automático de alerta temprana, lo mejor validado es un aviso: en crisis bancarias **la logística
  gana al ML fuera de muestra** (Beutel, List y von Schweinitz). Con un decodificador lineal, el error de
  reconstrucción es casi el residuo idiosincrásico del DFM. **Recomiendo usar la innovación estandarizada del
  Kalman** (gratis dentro del DFM del §3.2 anterior) y no un autoencoder.
- **Descubrimiento de relaciones.** Lo que encaja con nuestro protocolo son **knockoffs para series temporales**
  (control de la tasa de falsos descubrimientos, FDR) y **PCMCI** (controla los falsos positivos por
  autocorrelación). Ambos sirven como **herramienta de descubrimiento ≤ 2004 con una división interna**, para la
  **siguiente** generación de variables (base v0.5), no para los aspirantes actuales. La causalidad de Granger no
  lineal y la transfer entropy son redundantes o frágiles con ≈ 440 meses. **CCM, SINDy y MIC no encajan**: suponen
  dinámica determinista, son sensibles al ruido o tienen poca potencia.
- **Problema de fondo:** todos estos métodos miden **dependencia media en todos los meses**. Nuestro margen está en
  **≈ 10 giros**, que es justo donde más fácil es hacer minería: un "descubrimiento" que solo actúa en los giros se
  apoya en un puñado de eventos.

---

## 1. Deep Dynamic Factor Models (D2FM): Andreini, Izzo y Ricco

**Referencia:** P. Andreini, C. Izzo y G. Ricco, *Deep Dynamic Factor Models*, arXiv 2007.11887 (v1 de julio de
2020, revisada en marzo de 2024): https://arxiv.org/abs/2007.11887 (texto: https://ar5iv.labs.arxiv.org/html/2007.11887).
El encargo menciona el Banco de Italia; en la versión de arXiv que he leído no consta esa afiliación.

**Arquitectura** (texto leído):
- **Autoencoder asimétrico.** El codificador es un perceptrón no lineal de 3 capas ocultas (tanh, dos capas de
  *batch normalisation*); el ancho se elige por validación cruzada. El **decodificador es lineal**: y = Λf + ε, de
  modo que los factores se interpretan como en un DFM.
- Componente idiosincrásico AR(1); factores con un VAR(2), como en Bańbura-Modugno (2014).
- Frecuencia mixta mediante una capa fija de agregación de Mariano-Murasawa. Admite el borde desigual de
  publicación.
- Entrenamiento con ADAM, 100 épocas, lotes de ≥ 100 meses.

**Datos y diseño fuera de muestra:**
- FRED-MD **en tiempo real** (vintages de 1980-01 a 2020-05), 128 series mensuales + 2 PMI + PIB trimestral.
- Estimación hasta **2005-12**; evaluación **en tiempo real, ventana expansiva, 2006-01 → 2020-05**.
- Hiperparámetros (neuronas, número de factores, retardos) por **validación cruzada fuera de muestra** en bloques
  consecutivos, **repetida en cada corte** con un año de validación. Los factores y retardos elegidos cambian con
  el tiempo.

**Evidencia:**
- PIB: RMSE relativo al AR(1) por debajo del DFM-EM (2 y 3 factores) en 5 de 6 horizontes; ejemplo, 0,80 frente a
  0,87-0,89 a 14 semanas. En el horizonte más corto empata o pierde un poco (0,832 frente a 0,826).
- Variables mensuales: ≈ 80 % mejoran frente al AR(1).
- Monte Carlo: con un proceso **lineal**, D2FM ≈ DFM; con uno **no lineal**, recupera el 15-34 % más de varianza
  de los factores.
- **Giros y recesiones:** no da cifras por episodio (2008, 2020). Solo hay gráficos con las recesiones NBER
  sombreadas. **Ni log-loss ni probabilidades de régimen.**

**Contaminación: alta para nuestras expectativas.** El método no se ajusta a nuestros datos, pero **toda** su
evidencia fuera de muestra está en 2006-2020. Que "funcionara en 2008" es información sobre nuestro bloqueado.
Además, la validación cruzada repetida es una búsqueda de especificación que el artículo no penaliza.

**Encaje con el nowcast estructural** (variante del §3.2 del documento anterior):
- Nuestro panel sería de **4-6 series** (INDPRO, PAYEMS, W875RX1, CMRMTSPL + `claims_4w_yoy`, `philly_neworders`).
  La ventaja del D2FM viene de comprimir paneles grandes con relaciones no lineales. Con 6 series y un factor, el
  margen es pequeño. Un D2FM con decodificador lineal y 1 factor solo cambia **cómo se extrae** el factor
  (codificador no lineal), no cómo se relaciona con los datos.
- **Cómo probarlo honestamente:**
  - arquitectura **fijada a priori**, sin validación cruzada: 1 capa oculta de 8 tanh, 1 factor, VAR(2) como el
    DFM, decodificador lineal, semilla fija y 5 semillas como sensibilidad;
  - **reentrenado en cada corte** con datos ≤ T y el mismo calendario PIT;
  - comparado **anidado** con el DFM lineal (mismo panel, mismo filtro, misma composición de Ĝ). La pregunta
    preregistrada es "¿ll(D2FM) − ll(DFM) > 0?", no "¿bate a M0?".
- **Coste:** M (PyTorch; la capa de frecuencia mixta no hace falta: todo es mensual). **Riesgo de sobreajuste:**
  medio-alto. Con ≈ 300-450 meses de entrenamiento y una red de ~100 parámetros, la regularización (early stopping,
  L2) es otra elección que hay que fijar a priori.
- **Lugar en el ranking:** sexto, detrás de las cinco ideas anteriores. Solo merece la pena si el DFM lineal
  muestra residuos con estructura no lineal en desarrollo (p. ej., asimetría del factor en los giros). Esa
  comprobación debe ser descriptiva y no mirar la etiqueta.

---

## 2. Autoencoders para anomalías y *statistical arbitrage*: el error de reconstrucción como alerta

### 2.1 Lo que he encontrado

| fuente | qué hace | evidencia fuera de muestra | contaminación |
|---|---|---|---|
| *Detecting Changes in Asset Co-Movement Using the Autoencoder Reconstruction Ratio*, arXiv 2002.02008 ([enlace](https://arxiv.org/abs/2002.02008); comentario en [Risk.net](https://risk.net/our-take/7661811/spotting-co-movement-breakdowns-with-neural-networks)) | Autoencoder disperso y con eliminación de ruido sobre rentabilidades; la ratio de reconstrucción es el sucesor no lineal de la *absorption ratio* de PCA (Kritzman et al.). | Entrenamiento 2012-2014, validación 2015, prueba después. Valores bajos coinciden con más volatilidad y caídas, y mejora predictores de volatilidad y crashes **a corto plazo**. **Mercados, no macro.** | **A** (todo post-2012) |
| Autoencoder sobre flujos de pagos (Latin American Journal of Central Banking, 2021; [DOAJ](https://doaj.org/article/050fb9c900e64a869061b024734034ed); [CEMLA](https://www.cemla.org/actividades/2021-final/2021-06-regional-conference-payments-markets-infrastructures/2021-06-regional-conference-payments-markets-infrastructures-18.pdf)) | Entrenado con datos "normales"; el error de reconstrucción sube en escenarios de estrés. | Fuera de muestra contra **escenarios simulados**, no contra crisis reales. | A |
| Gu, Kelly y Xiu, *Autoencoder Asset Pricing Models* ([SSRN 3335536](https://papers.ssrn.com/abstract=3335536); J. Econometrics 2021, no verificado hoy) | Autoencoder condicional: exposiciones como función no lineal de características. | Errores de valoración fuera de muestra mucho menores que otros modelos de factores. Es para **valoración de activos**, no para alertas. | A (muestra hasta ≈ 2016) |
| Avellaneda y Lee (2010), *Statistical arbitrage in the US equities market*, Quantitative Finance (no verificado hoy) | Residuos de PCA o ETF como señal de reversión a la media. | Rentable en 1997-2007, con deterioro en la parte final según recuerdo; **no verificado hoy**. | M |
| Beutel, List y von Schweinitz (2019), *An evaluation of early warning models for systemic banking crises: does machine learning improve predictions?*, Bundesbank DP 48/2018 ([enlace](https://www.bundesbank.de/en/publications/research/discussion-papers/an-evaluation-of-early-warning-models-for-systemic-banking-crises-does-machine-learning-improve-predictions--770992)) | ML frente a logit para crisis bancarias en economías avanzadas (45 años). | **El ML ajusta muy bien en muestra pero pierde contra la logística en evaluación recursiva fuera de muestra**, de forma robusta a métrica, definición de crisis y variables. | M (incluye 2008) |

**No he encontrado ninguna evaluación fuera de muestra del error de reconstrucción de un autoencoder como alerta
de recesión o de giro macro.** La búsqueda dirigida no dio resultados, y la sesión agotó su límite antes de poder
ampliarla con otros términos.

### 2.2 ¿Aporta algo frente a un DFM lineal?

- **En teoría, poco con nuestro panel.** Con decodificador lineal y un factor, el error de reconstrucción es
  y − Λ f̂, donde f̂ sale de un codificador no lineal. En el DFM lineal, el equivalente es el **residuo
  idiosincrásico** y la **innovación de predicción** del Kalman (v<sub>t</sub> y su varianza F<sub>t</sub>). Las
  dos miden "los datos de este mes no encajan con la estructura común". La diferencia solo importa si la
  estructura común es **no lineal**, que es lo que el D2FM intenta capturar y lo que con 6 series no podremos
  distinguir bien.
- **Alternativas lineales ya conocidas** que cubren la misma necesidad:
  - innovación estandarizada del Kalman, v<sub>t</sub>′F<sub>t</sub><sup>−1</sup>v<sub>t</sub> (χ² bajo el
    modelo), como detector de sorpresas;
  - contrastes de cambio estructural en las cargas de los factores (Breitung-Eickmeier 2011, J. Econometrics;
    Chen, Dolado y Gonzalo 2014, J. Econometrics; no verificados hoy), que detectan "la estructura ha cambiado",
    pero ex post y con retraso, por lo que valen poco para un nowcast;
  - la *absorption ratio* de PCA (Kritzman et al. 2011) para mercados.
- **Para el Markov TVTP:** una variable de "sorpresa" en las transiciones (p. ej., el χ² de la innovación en
  P(A→B)) es una idea razonable. Pero es un **stock de sorpresa sin signo**: sube tanto en caídas como en
  rebotes, lo que repite el problema que vimos con `baa_gap10y`. Si se usa, debe ser con signo: la innovación del
  **factor**, no el error total.

### 2.3 Recomendación

- **No** construir un autoencoder de anomalías.
- **Sí**, como subproducto gratuito del DFM del §3.2 anterior, guardar la innovación del factor y el χ² del Kalman
  y estudiarlos de forma **descriptiva y sin etiqueta** frente a la cronología NBER ≤ 2004, como hizo el Estratega
  con C5. Si muestran algo, entran como **hipótesis nueva preregistrada** para el TVTP en una versión posterior.

---

## 3. Métodos para descubrir relaciones ocultas o causales

**Contexto común:** el periodo ≤ 2004 ya se ha usado para M1 v1, M1 v2 y el diseño de los aspirantes. Cualquier
descubrimiento en él es una búsqueda más, que cuenta para Deflated y necesita confirmarse en datos que no la han
generado. Con ≈ 440 meses (1968-2004) y ≈ 60 variables, la potencia frente a la dependencia media es razonable;
**frente a relaciones que solo actúan en los giros (≈ 10 eventos) es casi nula**.

| método | idea | evidencia y validación | ¿usado en macro o finanzas? | riesgo de minería con pocos eventos | encaje en el protocolo |
|---|---|---|---|---|---|
| **Granger no lineal** (Hiemstra-Jones 1994; Diks-Panchenko 2006, JEDC 30; redes neuronales, Tank et al. 2021, IEEE TPAMI, no verificado hoy) | ¿El pasado de X mejora la predicción de Y más allá del pasado de Y, aunque sea de forma no lineal? | Diks y Panchenko muestran que Hiemstra-Jones **sobrerrechaza**: bajo la nula la tasa de rechazo puede tender a 1 al crecer la muestra, de modo que parte de la evidencia aplicada "debe reinterpretarse" ([Diks-Panchenko](https://www.lem.sssup.it/Diks_Panchenko_2005.pdf); [revisión](https://arxiv.org/abs/1701.03992)). Su versión corrige el tamaño; ancho de banda según n. | Sí, mucho en finanzas (volumen-precio, petróleo-bolsa). | Alto: los contrastes no paramétricos con n ≈ 440 tienen poca potencia; hay que aplicarlos a los residuos de un VAR para no redescubrir lo lineal. | Posible como cribado de pares (variable → `growth_rt`, no → la etiqueta), con Holm/BH. Poco valor añadido sobre un Granger lineal con selección. |
| **Transfer entropy** (Schreiber 2000; *effective TE*, Marschinski-Kantz 2002; Dimpfl-Peter 2013) | Flujo de información direccional, sin suponer linealidad. | Sesgo fuerte en muestra pequeña: la ETE resta la TE de series barajadas ([EPJ B](https://epjb.epj.org/articles/epjb/abs/2002/22/b01535/b01535.html)). Para procesos gaussianos **equivale a Granger** (Barnett, Barrett y Seth 2009, no verificado hoy). | Finanzas: Dow-DAX al minuto, CDS frente a bonos soberanos ([Pagnottoni et al.](https://irinsubria.uninsubria.it/handle/11383/2170077)). Macro: no he encontrado. | Alto: hay que discretizar, y los resultados dependen del número de cajas y del retardo (más grados de libertad). | No recomendado: redundante con Granger en lo lineal y frágil en lo no lineal con n ≈ 440. |
| **Convergent cross mapping (CCM)** (Sugihara et al. 2012, Science 338) | Reconstrucción del espacio de estados (Takens): si X causa Y, la historia de Y permite reconstruir X. Pensado para sistemas deterministas débilmente acoplados, que Granger no cubre. | Ecología (sardina-anchoa-temperatura) ([PDF](https://www.science.ntu.edu.tw/wp-content/uploads/2012/10/causalityCCM.pdf)). Con **sincronización fuerte** puede dar causalidad inversa espuria; necesita series largas o réplicas espaciales (CCM multiespacial) ([CRAN](https://packages.oit.ncsu.edu/cran/web/packages/multispatialCCM/refman/multispatialCCM.html)). | No he encontrado una evaluación seria en macro. | Alto: la macro mensual es **estocástica y ruidosa**, lo contrario de lo que supone. | No encaja. |
| **PCMCI / PCMCI+ / LPCMCI (Tigramite)** (Runge et al. 2019, Science Advances 5(11); PCMCI+ 2020) | Descubrimiento causal por independencia condicional en dos fases: selección de padres (PC1) y contraste MCI condicionado en los padres de las dos variables, lo que **controla los falsos positivos por autocorrelación**. Contrastes lineales (ParCorr) o no lineales (GPDC, CMI). | Clima y simulaciones grandes: más potencia que los métodos previos ([arXiv](https://arxiv.org/abs/1702.07007)). PCMCI+ mejora recall y control de falsos positivos con autocorrelación fuerte ([arXiv](https://arxiv.org/abs/2003.03685)). Supuestos: suficiencia causal (salvo LPCMCI), fidelidad, estacionariedad. | Macro: una preprint de 2025 con 4 variables trimestrales de EE. UU. 1970-2021 ([arXiv 2509.07036](https://arxiv.org/abs/2509.07036v1)); poca cosa y contaminada. Existe una variante dependiente del régimen (Saggioro et al. 2020, Chaos, no verificado hoy). | Medio: con ParCorr y α fijo es conservador; los contrastes no lineales (CMI) necesitan más datos. La no estacionariedad (épocas) viola un supuesto. | **Encaja como descubrimiento ≤ 2004**: grafo entre las ≈ 60 variables de la base y `growth_rt` (no la etiqueta), con corrección FDR que la propia Tigramite permite. Es la mejor herramienta de su familia para nuestro problema de autocorrelación. |
| **SINDy / regresión simbólica** (Brunton, Proctor y Kutz 2016, PNAS 113(15)) | Regresión dispersa sobre una biblioteca de funciones candidatas para descubrir ecuaciones diferenciales que gobiernan el sistema. | Sistemas canónicos (Lorenz, estela de un cilindro) ([PNAS](https://pmc.ncbi.nlm.nih.gov/articles/PMC4839439)). Sensible al ruido y a derivadas numéricas; supone dinámica determinista de baja dimensión. | No he encontrado aplicaciones en macro; las finanzas solo aparecen como motivación (SINDYc). | **Muy alto**: con una biblioteca grande y ≈ 10 giros, cualquier término no lineal puede "explicar" los giros. | No encaja. Lo que sí sirve (regresión dispersa con interacciones dependientes del estado) es lo que ya hacemos con L2 y signos impuestos. |
| **MIC (Maximal Information Coefficient)** (Reshef et al. 2011, Science 334) | Medida de dependencia "equitativa" para cualquier forma funcional. | Simon y Tibshirani (2011): **menos potencia** que la correlación de distancias. Kinney y Atwal (2014, PNAS): la equitabilidad, tal como se define, no la cumple ninguna medida no trivial, y la información mutua tiene más potencia que el MIC ([CSHL](https://repository.cshl.edu/id/eprint/29568/)). Respuesta de Reshef et al. (2014). | Poco en macro. | Alto, y además con baja potencia: lo peor de los dos mundos. | No recomendado. Si hace falta una medida no lineal, usar la **correlación de distancias** o la información mutua con permutaciones por bloques. |
| **Knockoffs** (Barber-Candès 2015, Ann. Statist. 43(5); model-X: Candès, Fan, Janson y Lv 2018, JRSS-B; series temporales: Chi, Fan, Ing y Lv, arXiv 2112.09851) | Copias "falsas" de cada variable con la misma estructura de correlación; una variable se selecciona solo si gana claramente a su copia. **Control exacto del FDR** en muestra finita (fixed-X, n ≥ p) ([arXiv](https://arxiv.org/abs/1404.5609)). | Teoría sólida y simulaciones. TSKI extiende el control (asintótico) del FDR a series dependientes mediante submuestreo y e-valores, con una aplicación a la **inflación** ([arXiv](https://arxiv.org/abs/2112.09851)). DeepLINK-T genera las copias con LSTM ([arXiv](https://arxiv.org/html/2404.04317v1)). | Sí: inflación (TSKI); en finanzas, selección en el *factor zoo* (no verificado hoy). | Medio-bajo: es el único de la lista diseñado **para controlar falsos descubrimientos**. Pero el FDR se refiere a la dependencia media, no a los giros. | **Encaja mejor que ninguno**: selección de variables ≤ 2004 para el objetivo continuo (G o `growth_rt` adelantada), con FDR q = 0,1 fijado a priori. Las seleccionadas pasan a ser hipótesis preregistradas. |

---

## 4. Protocolo de descubrimiento propuesto (si el usuario quiere usarlo)

1. **Separar el descubrimiento de la evaluación dentro del desarrollo.** El periodo ≤ 2004 ya está gastado en parte.
   Proponer:
   - **descubrimiento:** 1968-02 → 1989-12 (≈ 260 meses, 5 recesiones NBER);
   - **confirmación interna:** 1990-01 → 2004-12, con una sola pasada y **solo** sobre lo que salga del
     descubrimiento;
   - el bloqueado (≥ 2005) sigue intacto para la evaluación única.
2. **Objetivo del descubrimiento:** la etiqueta continua G ≤ 1989 recalculada como en el arnés, o, para no gastar
   la etiqueta, `growth_rt` adelantada 2-4 meses (una aproximación PIT de los 2/3 por conocer). Lo segundo usa solo
   variables y deja la etiqueta para la confirmación interna. **Decisión del usuario.**
3. **Herramientas, por orden:** (a) knockoffs para series temporales con q = 0,1; (b) PCMCI+ con ParCorr y FDR,
   con CMI como sensibilidad. **Solo estas dos**, fijadas a priori, sin iterar parámetros.
4. **Qué cuenta como hallazgo:** variable (o interacción con el estado, p. ej. × P(G bajo)<sub>t−1</sub>)
   seleccionada por las dos herramientas, **con mecanismo económico escrito antes** de la confirmación interna y con
   el mismo signo en las dos mitades del periodo de descubrimiento.
5. **Contabilidad:** cada variable examinada es un ensayo en `research/trial_log.md`. El número total de candidatas
   (≈ 60 × retardos) se declara.
6. **Salida:** los hallazgos confirmados pasan a una **base PIT v0.5** y a hipótesis preregistradas para la
   **siguiente** generación de modelos, no para los aspirantes M2 actuales, cuyas specs no deben esperar a esto.

---

## 5. Veredicto y orden respecto al ranking anterior

| orden | idea | documento | estado |
|---|---|---|---|
| 1 | *Pool* de log-scores {M0, estructural, TVTP} + recalibración beta | anterior §3.1 | probar (capa común) |
| 2 | DFM lineal coincidente con *ragged edge* → Ĝ exacto | anterior §3.2 | probar (aspirante estructural) |
| 3 | TVTP con emisión desde el factor | anterior §3.3 | probar (aspirante Markov) |
| 4 | Varianza de revisión en σ̂ | anterior §3.4 | probar (barato) |
| 5 | *Plucking* dependiente del estado | anterior §3.5 | solo sensibilidad |
| **6** | **D2FM pequeño, arquitectura fija, anidado frente al DFM lineal** | este §1 | sensibilidad secundaria, fuera de Holm; solo si el DFM lineal está hecho |
| **7** | **Innovación del Kalman del factor como variable de alerta, descriptiva ≤ 2004 sin etiqueta** | este §2.3 | descriptivo ahora; hipótesis para más adelante |
| **8** | **Descubrimiento ≤ 2004 con knockoffs (TSKI) + PCMCI+, división 1968-89 / 1990-2004** | este §4 | para la base v0.5 y la siguiente generación; decisión del usuario |
| — | autoencoder de anomalías, Granger no paramétrico, transfer entropy, CCM, SINDy, MIC | este §2-3 | no probar |

**Qué habría que preregistrar si se aprueba algo de esto:**
- **D2FM (6):** arquitectura exacta (capas, neuronas, activación, número de factores, VAR(2)), regularización y
  parada temprana, semillas, panel y calendario idénticos al DFM, y la pregunta anidada ll(D2FM) − ll(DFM). Va como
  **secundaria fuera de Holm**. Contaminación declarada: toda la evidencia publicada está en 2006-2020.
- **Innovación del Kalman (7):** definición (innovación del factor con signo; χ² como sensibilidad), cronología NBER
  ≤ 2004 como única referencia y nada de etiqueta. Si después entra en el TVTP, es una hipótesis nueva (H-M2-00x)
  declarada post hoc.
- **Descubrimiento (8):** periodos de descubrimiento y de confirmación, objetivo (G o `growth_rt` adelantada),
  herramientas y sus parámetros (q, α, retardos máximos, test de independencia), criterio de hallazgo (§4.4) y
  número de candidatas. Los hallazgos se registran como hipótesis **antes** de la confirmación interna.

**Contaminación, resumen:**
- D2FM: **alta** para las expectativas (evaluación 2006-2020).
- Autoencoders de anomalías: **alta** (todo post-2012).
- Beutel et al.: media (incluye 2008), pero su conclusión es **contraria** al ML, así que no infla expectativas.
- Knockoffs, PCMCI, Granger, TE, CCM, SINDy, MIC: herramientas genéricas (**baja**). Lo que se contamina es el
  uso: cualquier hallazgo en ≤ 2004 es post hoc respecto a M1 v1/v2 y se declara así.

---

## 6. Fuentes

- Andreini, Izzo y Ricco, *Deep Dynamic Factor Models*: https://arxiv.org/abs/2007.11887 ; https://ar5iv.labs.arxiv.org/html/2007.11887
- Autoencoder Reconstruction Ratio: https://arxiv.org/abs/2002.02008 ; https://risk.net/our-take/7661811/spotting-co-movement-breakdowns-with-neural-networks
- Autoencoder en sistemas de pago (LAJCB 2021): https://doaj.org/article/050fb9c900e64a869061b024734034ed ; https://www.cemla.org/actividades/2021-final/2021-06-regional-conference-payments-markets-infrastructures/2021-06-regional-conference-payments-markets-infrastructures-18.pdf
- Gu, Kelly y Xiu, *Autoencoder Asset Pricing Models*: https://papers.ssrn.com/abstract=3335536
- Beutel, List y von Schweinitz: https://www.bundesbank.de/en/publications/research/discussion-papers/an-evaluation-of-early-warning-models-for-systemic-banking-crises-does-machine-learning-improve-predictions--770992
- Diks y Panchenko: https://www.lem.sssup.it/Diks_Panchenko_2005.pdf ; *The Hiemstra-Jones test revisited*: https://arxiv.org/abs/1701.03992
- Transfer entropy efectiva: https://epjb.epj.org/articles/epjb/abs/2002/22/b01535/b01535.html ; Pagnottoni et al.: https://irinsubria.uninsubria.it/handle/11383/2170077
- Sugihara et al. (2012): https://www.science.ntu.edu.tw/wp-content/uploads/2012/10/causalityCCM.pdf ; CCM multiespacial: https://packages.oit.ncsu.edu/cran/web/packages/multispatialCCM/refman/multispatialCCM.html
- Runge et al. (2019), PCMCI: https://arxiv.org/abs/1702.07007 ; PCMCI+: https://arxiv.org/abs/2003.03685 ; aplicación macro: https://arxiv.org/abs/2509.07036v1
- Brunton, Proctor y Kutz (2016), SINDy: https://pmc.ncbi.nlm.nih.gov/articles/PMC4839439
- MIC, Kinney y Atwal: https://repository.cshl.edu/id/eprint/29568/ ; Simon y Tibshirani (comentario, 2011)
- Barber y Candès (2015): https://arxiv.org/abs/1404.5609 ; Chi, Fan, Ing y Lv, TSKI: https://arxiv.org/abs/2112.09851 ; DeepLINK-T: https://arxiv.org/html/2404.04317v1
- No verificados hoy (límite de búsqueda): Avellaneda y Lee (2010); Breitung y Eickmeier (2011); Chen, Dolado y Gonzalo (2014); Tank et al. (2021); Barnett, Barrett y Seth (2009); Saggioro et al. (2020); Kritzman et al. (2011).

No he leído la etiqueta, ni datos ≥ 2005, ni corrido ningún modelo, ni tocado código.
