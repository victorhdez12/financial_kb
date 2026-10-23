---
documento: revisión de literatura — métodos para mejorar el nowcast PIT del régimen G (e I) frente a M0
fecha: 2026-10-23
autor: Investigador
encargo: decisión del usuario del 23-oct (dos aspirantes: Markov TVTP solo eje G y nowcast estructural de G; buscar mejoras en internet)
contexto_leido: obsidian/Proyecto/Estado del proyecto.md, docs/models/label_spec.md, docs/models/m1_v2_results_dev.md, docs/reviews/2026-10-23_estratega_macro_m1v2.md, research/pit_whitelist.yaml, docs/models/pit_base.md, docs/models/harness.md (definición de falsas alarmas)
datos: ninguno. No he leído la etiqueta, ni datos ≥ 2005, ni corrido modelos, ni tocado código
---

# Mejoras para el nowcast de régimen: qué dice la literatura con evidencia fuera de muestra

## 0. Resumen

**El problema, en los términos del Estratega:** G(t) tiene 1/3 conocido en t y 2/3 de previsión a 0-4 meses. M0
(persistencia calibrada) es fuerte porque G es muy persistente. Los modelos con adelantados de 6-18 meses dan
falsas alarmas, y los "stocks de daño" cambian de signo en el rebote. Hay pocos giros (≈ 10 en 1978-2004) y poca
potencia: hacen falta ≈ 0,10 nats observados en el bloqueado.

**Lo que dice la literatura, en una frase:** los métodos que mejor aguantan en tiempo real para **fechar el estado
actual** son los que (a) extraen la señal **de los propios indicadores coincidentes** con un filtro (factor dinámico
o Markov-factor: Chauvet-Piger, Camacho-Pérez-Quirós-Poncela, ADS), (b) **combinan** varios modelos en lugar de
elegir uno (Geweke-Amisano, Berge, Aastveit et al., Hamilton) y (c) **recalibran** la combinación (Ranjan-Gneiting).
Los adelantados financieros sirven para el riesgo de giro a 6-12 meses, no para el estado del mes. El ML con pocos
giros gana en ROC en algunos estudios, pero con muestras que incluyen 2008 y 2020 y sin evaluación por log-loss.

**Ranking (detalle en §3):**

1. **Capa común: *pool* lineal de log-scores {M0, estructural, TVTP} con pesos walk-forward + recalibración
   beta (BLP).** Es la mejor relación evidencia/coste y, sobre todo, permite **un único contraste principal**
   (Holm k = 1), lo que ataca el problema de potencia.
2. **Estructural: nowcast de los 4 indicadores coincidentes con un factor dinámico pequeño (ragged edge,
   Kalman) y composición exacta de Ĝ con los pesos de la etiqueta.** Ataca directamente el 1/3 conocido y el
   horizonte de 0-4 meses.
3. **Markov: emisión desde ese mismo factor coincidente (Chauvet-Piger/Kim-Nelson) en lugar de `growth_rt` +
   peticiones de paro, con regla de confirmación como métrica secundaria.**
4. **Varianza de revisión en σ̂ (Jacobs-van Norden / Kishor-Koenig, versión mínima).** Barato; mejora la
   calibración en el borde de la muestra, que es donde M0 y los modelos sufren en los giros.
5. **Rebote tipo *plucking* (Kim-Nelson 1999; Sichel 1994) en forma dependiente del estado.** Mecanismo sólido
   y anterior a 2005, pero la idea de usarlo aquí nace de ver M1 v1/v2: va como **sensibilidad**, no en la
   principal.

**Descartados o aparcados:** ML (boosting/RF, Döpke; Vrontos), Michez y variantes de Sahm (contaminados y sin
datos de vacantes PIT), MIDAS semanal (poco que ganar con datos mensuales), GDPNow/NY Fed (objetivo trimestral,
evidencia post-2011), LVQ (interesante, pero sin log-loss y otro aspirante más).

---

## 1. Qué se busca y cómo se juzga cada método

Criterios del encargo, aplicados a cada fuente:

- **Evidencia fuera de muestra**: ¿es en **tiempo real** (vintages) o con datos revisados? ¿Mide giros y falsas
  alarmas? ¿Usa log-loss o solo acierto/ROC? Distingo, como Hamilton (2011), el tiempo real **simulado** (replay
  con vintages) del **real de verdad** (predicciones publicadas antes de conocer el resultado).
- **Encaje PIT** con `research/pit_whitelist.yaml` y la base v0.4: ¿están las series, con vintage o al menos
  `latest_truncated`?
- **Coste** de implementación para el Constructor (B = días; M = una o dos semanas; A = más).
- **Riesgo de sobreajuste**, sobre todo por número de parámetros frente a ≈ 10 giros.
- **Contaminación** respecto al bloqueado (≥ 2005): **alta** si el método se diseñó o se ajustó mirando 2008,
  2020 o 2024 (por ejemplo, umbrales elegidos con esos episodios); **media** si la evidencia publicada que lo
  respalda incluye esos episodios aunque el método sea anterior; **baja** si método y evidencia principal son
  anteriores a 2005.

> **Aviso sobre las fuentes.** He leído resúmenes, páginas de editoriales y repositorios, y algunos documentos de
> trabajo. Varios textos completos están tras muro de pago. Donde una cifra viene solo de un resumen o de una
> fuente secundaria lo indico ("según el resumen"). Nada de esto se ha verificado con nuestros datos.

---

## 2. Tabla comparativa

Leyenda: **TR** = evidencia con vintages en tiempo real; **Rev** = datos revisados; **FA** = falsas alarmas.
Contaminación: **B** baja, **M** media, **A** alta.

| # | Método | Referencia | Idea | Evidencia fuera de muestra | Encaje PIT | Coste | Sobreajuste | Contam. |
|---|---|---|---|---|---|---|---|---|
| 1 | Markov con transiciones variables (TVTP) | Filardo (1994) [JBES 12(3)](https://ideas.repec.org/a/bes/jnlbes/v12y1994i3p299-308.html); Diebold-Lee-Weinbach (1994), en Hargreaves (ed.), OUP; Filardo (1999) [*How reliable are recession prediction models?*](https://fedinprint.org/item/fedker/31521) | Las probabilidades de cambio de estado dependen de adelantados (logit). | 1994: en muestra; los adelantados "ayudan a predecir giros". 1999: revisa cinco modelos con datos en tiempo real; no he podido leer el texto completo, el resumen solo plantea la fiabilidad como problema. **Sin log-loss**. | Bueno (`curve_min12`, `baa_d6m`, `eq_ret_6m`). | M | **Alto**: cada logit de transición con 4-5 eventos (lo dice el Estratega). | B (método); M en nuestras variables (post-M1 v2) |
| 2 | Markov-factor dinámico (MS-DFM) con los 4 coincidentes | Chauvet-Piger (2008) [JBES 26](https://www.fedinprint.org/item/fedlwp/9583/original) (WP 2005); Kim-Nelson (1998/1999) | Un factor común de empleo, IP, ventas reales y renta real sin transferencias, cuya media cambia según un estado Markov. | **TR** (vintages propias de los 4 coincidentes): identifica todos los giros NBER del periodo **sin falsos positivos**, y los valles bastante antes que el NBER. Regla de decisión: 3 meses seguidos > 80 % para declarar recesión y < 20 % para la salida ([VoxEU](https://cepr.org/index%2ephp/voxeu/columns/calling-recessions-real-time)). Funcionó en 2008 publicado de verdad (Piger lo publica desde 2006). **Objetivo NBER, no G**. | **Muy bueno**: son las **mismas 4 series de la etiqueta**, todas en la base con vintage (W875RX1 desde 2010-05 y CMRMTSPL desde 2013-06; antes, `latest_truncated`). | M | Medio: pocos parámetros; los estados se identifican con recesiones. | **B** (muestra de evaluación ≈ 1977-2006 según mi lectura; verificar en el texto); su uso en 2008 es real, no ajustado |
| 3 | MS-DFM con frecuencia mixta y *ragged edge* | Camacho, Pérez-Quirós y Poncela (2018) [IJF 34(4)](https://www.bde.es/wbe/en/publicaciones/analisis-economico-investigacion/documentos-trabajo/markovswitching-dynamic-factor-models-real-time.html) | Como el #2, pero tratando los retrasos de publicación y el PIB trimestral dentro del filtro. | **TR** en EE. UU. y Monte Carlo: las ganancias vienen de usar el borde desigual de datos; según el resumen, mejora la inferencia del estado en tiempo real. | Bueno; el *ragged edge* coincide con nuestro calendario PIT (`pit_calendar.md`). | M-A | Medio | M (la muestra incluye 2008) |
| 4 | Índice ADS (factor dinámico de frecuencia mixta) | Aruoba-Diebold-Scotti (2009) [JBES 27(4)](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/ads) | Factor diario/semanal con peticiones de paro semanales, nóminas, IP, renta, ventas y PIB; filtro de Kalman. | El índice publicado se actualiza en tiempo real; la evaluación académica de su capacidad para fechar es sobre todo ex post. Valores < −0,8 suelen asociarse a recesión. | Las entradas están en la base (ICSA en `claims_4w_yoy`, vintage desde 2009-05). El índice publicado **no** es PIT (se reestima): habría que reconstruirlo. | M | Bajo-medio | M |
| 5 | Nowcast de factores y puentes (NY Fed, GDPNow) | Giannone-Reichlin-Small (2008); Bok et al. (2018) [NY Fed SR 830](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr830.pdf); Higgins (2014) [GDPNow WP 2014-7](https://www.atlantafed.org/research/publications/wp/2014/07) | Factor dinámico sobre un panel amplio, con ponderación por noticias, y puentes por componentes. | Para el **PIB trimestral**: GDPNow bate referencias estadísticas desde 2000 con la vintage actual, y en tiempo real (2011-) queda cerca del Blue Chip. **No** se evalúa en régimen ni en giros. | El principio encaja; el objetivo no (G es mensual). | A (panel grande) | Medio | **A** (desarrollados en 2011-2017 con muestras post-2005) |
| 6 | MIDAS con cambio de régimen | Guérin-Marcellino (2013) [JBES 31(1)](https://ideas.repec.org/p/cpr/ceprdp/8234.html) | Regresión MIDAS con parámetros que cambian según un estado Markov. | Pseudo fuera de muestra en EE. UU.; "muy útil" según los autores, para previsión y estado. | Solo aporta con datos semanales (peticiones de paro); el resto es mensual. | M | Alto (Markov + polinomio MIDAS) | M (incluye 2008) |
| 7 | Probit dinámico/autorregresivo | Kauppi-Saikkonen (2008) [REStat 90(4)](https://ideas.repec.org/a/tpr/restat/v90y2008i4p777-791.html) | El índice latente depende de su propio retardo, de la recesión retardada y de los adelantados. Da persistencia de forma natural. | Fuera de muestra con la curva; los pronósticos iterados ganan a los directos. Datos revisados, objetivo NBER. | Bueno, pero la "recesión retardada" PIT es la persistencia de la etiqueta con su retraso h ≈ 5. | B | Bajo-medio | B-M |
| 8 | Promedio y selección de modelos (BMA, combinaciones) | Berge (2015) [J. Forecasting 34(6)](https://ideas.repec.org/p/fip/fedkrw/41003.html) (WP KC Fed 13-05) | Promediar probits con varios adelantados frente a selección no lineal. | Fuera de muestra, datos revisados; el modelo preferido es no lineal y combina la curva con otros indicadores, sobre todo a horizontes muy cortos y muy largos. | Bueno. | B | Bajo (si las ponderaciones son simples) | M (muestra hasta 2010) |
| 9 | *Pool* óptimo de log-scores | Geweke-Amisano (2011) [J. Econometrics 164(1)](https://www.princeton.edu/~erp/pools_paper.pdf); Hall-Mitchell (2007, IJF) | Combinación lineal de densidades con pesos que maximizan la log-score; con modelos mal especificados el pool óptimo da peso positivo a varios. | Fuera de muestra (rentabilidades del S&P 500); la log-score es cóncava en los pesos, de modo que el pool **no puede ser peor que el mejor componente en muestra**, y en la práctica supera a BMA. | **Perfecto**: combina salidas de modelos y no necesita datos nuevos. | **B** | Bajo (1-2 pesos), salvo si se estiman con pocos meses | **B** (es una herramienta) |
| 10 | *Pool* lineal con transformación beta (BLP) | Ranjan-Gneiting (2010) [JRSS-B 72(1)](https://ideas.repec.org/a/bla/jorssb/v72y2010i1p71-91.html) | Un promedio de probabilidades calibradas está **descalibrado** (le falta nitidez); se corrige aplicando una beta a la combinación. | Fuera de muestra en probabilidad de precipitación (NWS) y simulaciones; mejora la log-score frente al pool lineal sin transformar. | Perfecto. | B | Bajo (2 + k parámetros) | B |
| 11 | Combinación de densidades con pesos variables | Aastveit, Ravazzolo y van Dijk (2017/18) [JBES](https://www.norges-bank.no/en/Published/Papers/Working-Papers/2014/17/) | Pesos latentes que aprenden del rendimiento reciente (Monte Carlo secuencial). | **TR**, 120 series de EE. UU.: mejores densidades del PIB que la selección y que otras combinaciones; buenas señales en tiempo real de la probabilidad de crecimiento negativo, tanto para entrar como para salir de recesión. | Encaja como capa, pero es caro. | A | **Medio-alto** (pesos que se mueven con ≈ 10 giros) | **A** (evaluada en 2008-2013) |
| 12 | Calibración: Platt, isotónica, beta | Platt (1999); Kull, Silva Filho y Flach (2017) [AISTATS / EJS 11(2)](https://projecteuclid.org/euclid.ejs/1513306867) | Recalibrar las probabilidades: Platt = logit lineal (lo que ya hace M0); beta = 3 parámetros y contiene la identidad; isotónica = no paramétrica. | Las comparaciones de aprendizaje automático muestran que la beta mejora a la logística en muchos clasificadores y que la **isotónica sobreajusta con muestras pequeñas**. | Perfecto. | B | Isotónica alto; beta bajo; Platt muy bajo | B |
| 13 | Reglas de confirmación y rachas (filtros anti-falsas alarmas) | Chauvet-Piger (2008) (regla 80/20 × 3 meses); Berge-Jordà (2011) [AEJ Macro 3(2)](https://www.aeaweb.org/articles/pdf/doi/10.1257/mac.3.2.246) (curvas ROC) | Declarar el giro solo si la señal persiste k meses; elegir umbrales sobre la frontera ROC entre aciertos y falsas alarmas. | **TR** en Chauvet-Piger: cero falsos positivos con la regla de 3 meses, a cambio de retraso. Berge-Jordà: el CFNAI sale entre los mejores clasificadores del estado actual. | Perfecto (es una capa de decisión), **pero** nuestra métrica principal es la log-loss de la probabilidad, que no mejora con un filtro duro. | B | Bajo si k y el umbral se fijan a priori | B |
| 14 | Regla de Sahm y Michez (Michaillat-Saez) | Sahm (2019); Michaillat-Saez (2024-25) [arXiv 2408.05856](https://arxiv.org/abs/2408.05856v2); [*anticipation-precision frontier*](https://econbrowser.com/archives/2025/07/guest-contribution-recession-detection-along-the-anticipation-precision-frontier) | Mínimo de la brecha de paro (Sahm) y de la brecha de vacantes; umbrales de 0,3 y 0,8 pp. | Los autores dicen que detecta todas las recesiones desde 1929 a los 0,8 meses (Sahm: 2,1), sin falsas alarmas; **no he encontrado una evaluación independiente**. La Sahm dio una falsa alarma en 2024, y aplicada a la OCDE ≈ 1/3 de las señales no coinciden con recesiones ([OCDE 2026](https://www.oecd.org/en/blogs/2026/03/Can-we-predict-recessions-using-only-unemployment-data--Applying-the-Sahm-rule-to-OECD-countries.html)). | Sahm ya está (`unrate_sahm`, con signo contrario en M1 v1). **Las vacantes no están en la lista blanca** (JOLTS desde 2000-12; antes, Help-Wanted empalmado, sin vintages). | M (habría que añadir vacantes a la base) | **Alto** (umbrales elegidos con toda la historia) | **A** (Sahm 2019, Michez 2024: ambos diseñados mirando el periodo bloqueado) |
| 15 | *Plucking* y choques asimétricos | Friedman (1964/1993); Kim-Nelson (1999) [JMCB 31(3)](https://ideas.repec.org/b/mtp/titles/0262112388.html); Sichel (1994); Dupraz, Nakamura y Steinsson (2019/2025) [NBER w26351](https://www.nber.org/papers/w26351) | Las caídas son "tirones" por debajo de un techo; el rebote es proporcional a la caída; las subidas del paro van seguidas de bajadas de tamaño parecido, pero no al revés. | Evidencia **en muestra** de la asimetría (paro de EE. UU., producto); no hay evaluación de pronóstico en tiempo real. | Bueno: profundidad de la caída medible PIT (p. ej. `unrate_gap10y`, caída acumulada de `growth_rt`). | B-M | Medio (un término que solo actúa tras ≈ 10 valles) | B (teoría anterior a 2005), pero **M para nosotros**: lo elegimos después de ver M1 v1/v2 |
| 16 | Aprendizaje automático (boosting, RF, redes) | Döpke, Fritsche y Pierdzioch (2017) [IJF 33(4)](https://ideas.repec.org/p/gwc/wpaper/2015-004.html); Vrontos, Galakis y Vrontos (2021) [IJF 37(2)](https://ideas.repec.org/a/eee/intfor/v37y2021i2p647-671.html) | Árboles potenciados o bosques aleatorios sobre adelantados; no linealidades e interacciones. | Döpke: datos **alemanes**, revisados; mejor que el probit fuera de muestra (ROC). Vrontos: EE. UU., comparación amplia a favor del ML; ROC y acierto, no log-loss. | Encaja en datos; no en potencia. | M | **Alto** (≈ 10 giros; estos estudios no penalizan por búsqueda) | **A** (Vrontos: muestra hasta ≈ 2019, con 2008) |
| 17 | Clasificación no paramétrica (LVQ) | Giusto-Piger (2013 WP; versión en IJF) [Dalhousie WP 2013-02](https://wp.economics.dal.ca/RePEc/dal/wpaper/DalEconWP2013-02.pdf) | Cuantización vectorial de los 4 coincidentes para clasificar el mes. | **TR**: fecha los giros tan rápido como el Markov-factor y con pocos supuestos. Sin probabilidades bien definidas: sin log-loss. | Muy bueno (mismas 4 series). | M | Medio | M |
| 18 | Modelar las revisiones (noticia frente a ruido) | Jacobs-van Norden (2011) [J. Econometrics](https://rdrr.io/cran/reviser/man/jvn_nowcast.html); Kishor-Koenig (2012) [JBES 30(2)](https://ideas.repec.org/p/fip/feddwp/05-01.html); Fossati (2015) [Applied Econ. 47(53)](https://ideas.repec.org/a/taf/applec/v47y2015i53p5726-5738.html) | Espacio de estados con el valor "verdadero" y las vintages; las revisiones son noticia (impredecible) o ruido (predecible). Fossati: los factores sufren menos con las revisiones que los indicadores sueltos. | Kishor-Koenig: los VAR que tienen en cuenta las revisiones prevén mejor la vintage final. Fossati: las conclusiones del probit con factores se mantienen con datos en tiempo real. | **Bueno**: tenemos vintages ALFRED de las 4 series para medir la varianza de revisión por "edad" del dato (ya se hizo para s<sub>G</sub>). | B (versión mínima) / A (completa) | Bajo en la versión mínima | B (Fossati: M) |

**Fuera de la tabla, a efectos de método:** Hamilton (2011) [*Calling recessions in real time*, IJF 27(4)](https://www.nber.org/papers/w16162)
insiste en que el tiempo real simulado sobreestima lo que se consigue en tiempo real de verdad (revisiones,
relaciones que cambian). Recomienda modelos parsimoniosos y **combinar** enfoques. Es justo nuestra situación: el
bloqueado es nuestro "tiempo real de verdad".

---

## 3. Ranking de las ideas más prometedoras y cómo se integran

### 3.1 (1º) Capa común: *pool* de log-scores {M0, estructural, TVTP} + recalibración beta (#9, #10, #12)

**Por qué la primera:**
- Es la única idea que mejora **a la vez** la log-loss esperada, las falsas alarmas y la **potencia**:
  - **Log-loss:** el pool óptimo da peso positivo a varios modelos mal especificados (Geweke-Amisano) y, como
    incluye a M0, por construcción tiende a no ser peor que M0 salvo por el error de estimar los pesos.
  - **Falsas alarmas:** promediar con M0 (que da 0,19 al año) amortigua los cruces de 0,5 de los aspirantes. Las
    falsas alarmas del arnés son **cruces** de 0,5 en la parte estable de las rachas (`harness.md`), así que un
    pool con peso apreciable en M0 las reduce de forma casi mecánica.
  - **Potencia:** si se preregistra el **pool como único contraste principal**, Holm pasa de k = 2 a **k = 1**.
    Los dos aspirantes van como secundarios informativos. Con un error típico de ≈ 0,05 nats, pasar de k = 2 a
    k = 1 el primer p-valor se compara con α en vez de α/2 y el listón observado baja algo, aunque no
    mucho. Lo que más pesa es que el pool tenga menos varianza que cada componente.
- Coste bajo: trabaja sobre las predicciones walk-forward que el arnés ya guarda.
- Contaminación baja: es una herramienta genérica, anterior a cualquier mirada a nuestros datos.

**Diseño concreto** (para la spec):
1. Componentes por eje G: p<sub>M0</sub>, p<sub>struct</sub>, p<sub>tvtp</sub>. El eje I sigue siendo M0
   (decisión del usuario).
2. Pesos w ∈ simplex estimados en cada corte con las log-scores **ya maduras** del propio walk-forward (respetando
   el embargo de 6 meses), con una previa de Dirichlet centrada en (1/3, 1/3, 1/3) o (½ M0, ¼, ¼). Ventana
   expansiva, sin pesos que cambien rápido: el #11 (Aastveit) es demasiado flexible para ≈ 10 giros.
3. Recalibración BLP: P = Beta<sub>a,b</sub>(Σ w<sub>k</sub> p<sub>k</sub>), con a, b estimados con la misma
   ventana y una previa que encoge hacia a = b = 1. Alternativa más simple: beta calibration de Kull (3 parámetros)
   sobre el pool. **Nunca isotónica** (sobreajusta con ≈ 300 meses).
4. Arranque: mientras no haya N<sub>min</sub> meses maduros de log-score de los aspirantes (p. ej. 60), w = (1, 0, 0).
   Es decir, M0. Esto es conservador y PIT.

**Riesgos:** con tan pocos giros el peso puede ir casi todo a M0 y el pool ≈ M0. Sería una respuesta honesta.
Estimar pesos y beta es una tercera capa de parámetros: hay que preregistrar previas y ventana.

### 3.2 (2º) Estructural: factor coincidente con *ragged edge* y composición exacta de Ĝ (#2, #3, #4, #5)

**Idea.** En lugar de regresar G sobre `growth_rt` y cuatro adelantados (§3.2 del Estratega), **reconstruir la
etiqueta**. G(t) es una combinación conocida (pesos 1, 2, 3, 3, 3, 3, 2, 1 / 18) de las tasas mensuales de los 4
coincidentes, menos su tendencia, dividida por σ<sub>i</sub>. Entonces:

1. Un factor dinámico pequeño (1 factor, AR(2)), en la tradición Stock-Watson / Kim-Nelson / ADS, sobre las
   **tasas mensuales** de INDPRO, PAYEMS, W875RX1 y CMRMTSPL, con `claims_4w_yoy` y `philly_neworders` como
   indicadores adicionales del factor, estimado por Kalman con el **borde desigual** de cada vintage
   (Camacho-Pérez-Quirós-Poncela; Bańbura-Modugno).
2. El filtro da, para cada indicador, las tasas que faltan (t−1 si no se ha publicado, t … t+4) con su varianza.
3. Ĝ<sub>t</sub> se compone **exactamente** como la etiqueta: tasas observadas o previstas, la tendencia PIT de
   10 años (mediana hacia atrás; la parte centrada hacia delante de la tendencia es otra fuente de error que va a
   σ̂) y σ<sub>i</sub>.
4. P(G alto) = Φ(Ĝ<sub>t</sub> / √(V̂<sub>filtro</sub> + V̂<sub>tendencia</sub> + s<sub>G</sub><sup>2</sup>)),
   donde V̂ sale del filtro y no de un residuo ajustado.

**Por qué es mejor que la regresión del Estratega:**
- El 1/3 conocido se usa con su peso exacto en lugar de a través de `growth_rt` (centrada en ≈ t−2, con su propio
  suavizado).
- Las peticiones de paro y Filadelfia entran donde la literatura muestra que aportan, **en el nowcast del mes y
  el siguiente**, no como logit aditivo.
- La varianza del pronóstico crece con el horizonte de forma automática: es la calibración "de la aritmética de
  la etiqueta" que el Estratega pedía, pero mejor fundada.
- Chauvet-Piger muestran, en tiempo real y antes de 2005, que la señal coincidente de estas 4 series fecha los
  giros **sin falsas alarmas**.

**Encaje PIT:** las 4 series tienen vintages en la base (W875RX1 y CMRMTSPL solo desde 2010 y 2013; antes,
`latest_truncated`, que es como entran hoy en `growth_rt`). El calendario de `pit_calendar.md` da el borde
desigual. **Ojo:** el Constructor tiene que pasar al modelo las **tasas mensuales PIT de cada indicador**, no solo
`growth_rt`. Esto puede requerir columnas nuevas en una base v0.5 o que el modelo lea la instantánea de entradas
con el linaje. Es una decisión que hay que tomar en la spec.

**Coste:** M (un Kalman de 1 factor es estándar; `statsmodels` `DynamicFactorMQ` lo hace con datos faltantes).
**Sobreajuste:** bajo-medio: ≈ 15-20 parámetros de un modelo lineal gaussiano, identificados con **todos** los meses,
no con los giros. **Contaminación:** baja en el método; la elección de `claims` y Filadelfia viene del Estratega
(post-M1 v2), declarada.

**Riesgo:** M0 ya recoge mucho; si el factor no prevé t…t+4 mejor que un AR, Ĝ ≈ persistencia + 1/3 conocido.
Aun así, debería ganar a M0 en los meses posteriores a un giro, que es donde M0 tarda 4,4 meses.

### 3.3 (3º) Markov: emisión desde el factor coincidente (Chauvet-Piger) y confirmación como métrica (#1, #2, #13)

**Cambio propuesto al §3.1 del Estratega**, que mantiene todo lo demás (estados = etiqueta, TVTP restringido,
anclaje PIT, templado, calibración, referencia de transiciones constantes):

- **Emisión:** en lugar de x<sub>t</sub> = (`growth_rt`, `claims_4w_yoy`), usar la innovación o el nivel del
  **factor coincidente del §3.2** (una sola variable, ya filtrada). Ventajas:
  1. Es el diseño con mejor historial **en tiempo real** de la literatura (Chauvet-Piger: sin falsos positivos).
  2. Reduce el solape que obliga a templar con λ = 1/3 (`growth_rt` solapa 3 meses); el factor mensual tiene
     menos autocorrelación inducida y λ puede quedar como sensibilidad.
  3. Comparte infraestructura con el estructural: un solo filtro para los dos aspirantes.
- **TVTP:** mantener solo γ en `curve_min12` y `baa_d6m` (salida de G alto) y `baa_d6m` y `eq_ret_6m` (salida de G
  bajo), con γ ≥ 0 y previas N(0; 0,5). La literatura (Filardo 1994; Filardo 1999) no da evidencia en tiempo real
  de que los TVTP batan a los de transiciones constantes de forma robusta: la referencia anidada `m2_ctp_g` es
  imprescindible, como dice el Estratega.
- **Confirmación (Chauvet-Piger, 3 meses × 80/20):** **no** aplicarla a la probabilidad puntuada (empeora la
  log-loss y añade retraso). Preregistrarla como **métrica secundaria** de la decisión dura ("giro declarado") junto
  a la definición actual de falsas alarmas. Cambiar la definición de falsas alarmas del criterio sería un cambio de
  criterio: decisión del usuario, antes de abrir.

**Coste:** bajo si ya existe el factor del §3.2. **Sobreajuste:** igual o menor que la versión del Estratega (una
variable de emisión en lugar de dos). **Contaminación:** baja (Chauvet-Piger evalúa ≈ 1977-2006 y se publica en
tiempo real desde 2006 sin reajuste del diseño).

### 3.4 (4º) Varianza de revisión en σ̂ (#18, versión mínima)

- Hoy s<sub>G</sub> = 0,40 es **fija** para toda la muestra (`label_spec.md` §5). Pero la incertidumbre de lo que
  conocemos en t depende de la **edad** de cada dato: la primera publicación de PAYEMS o INDPRO se revisa más que
  la tercera.
- Versión mínima (sin espacio de estados completo): con las vintages ALFRED ≤ 2004 de las 4 series, estimar a
  priori la varianza de revisión de la tasa mensual por edad (1, 2, 3, ≥ 12 meses) y sumarla a V̂ en el
  estructural (§3.2) y a la emisión del Markov.
- Es exactamente lo que hacen, en su versión mínima, Jacobs-van Norden y Kishor-Koenig: tratar la vintage reciente
  como medida ruidosa del valor final. Fossati añade que trabajar con factores amortigua las revisiones.
- **Coste:** B (un cálculo descriptivo sin etiqueta, como el estudio de revisión ya hecho para s<sub>G</sub>).
  **Sobreajuste:** muy bajo si se fija antes de ver la etiqueta. **Contaminación:** baja si se mide solo con
  vintages ≤ 2004.
- **Efecto esperado:** probabilidades menos extremas justo en el borde, donde están los giros; ayuda a la log-loss
  en los giros más que en los estables.

### 3.5 (5º, sensibilidad) Rebote tipo *plucking* en forma dependiente del estado (#15)

- Mecanismo bien documentado y anterior a 2005 (Friedman; Sichel 1994; Kim-Nelson 1999), con la versión moderna de
  Dupraz-Nakamura-Steinsson para el paro: el rebote es proporcional a la caída.
- Integración:
  - **Markov:** + γ<sub>5</sub> · profundidad en la salida de G bajo. La profundidad debe ser PIT, p. ej. la caída
    acumulada del factor coincidente desde su último máximo, o `unrate_gap10y`. Es la forma correcta que el
    Estratega dio para `baa_gap10y`.
  - **Estructural:** un término de "recuperación" en el AR del factor (más crecimiento esperado cuanto más hondo el
    hoyo), activo solo cuando P(G bajo)<sub>t−1</sub> alta.
- **Contaminación para nosotros: media-alta.** La idea de aplicarlo aquí nace de los signos invertidos de M1 v1 y
  v2 (desarrollo ≤ 2004). Recomiendo que vaya **solo como sensibilidad preregistrada**, que no elige ni entra en
  Holm. Lo mismo que el Estratega propone para `baa_gap10y`.

### 3.6 Lo que no recomiendo ahora

- **ML (#16):** la evidencia favorable usa ROC o acierto, no log-loss. Usa muestras que contienen 2008 (y a veces
  2020) y no corrige por la búsqueda de hiperparámetros. Con ≈ 10 giros, el riesgo de sobreajuste es el mayor de
  la tabla. Ya estaba detrás de los dos aspirantes en el plan; la literatura no da motivo para adelantarlo.
- **Michez y variantes de Sahm (#14):** contaminación alta (diseñados en 2019 y 2024 con toda la historia, incluido
  el bloqueado). Las vacantes no están en la lista blanca, y la Sahm en nivel ya falló por el mecanismo de rebote.
  Como mucho, la **forma** (mínimo de dos brechas) podría inspirar una variable en una v0.5, declarada contaminada.
- **MIDAS y MS-MIDAS (#6):** solo ganaríamos algo con las peticiones de paro semanales; la base es mensual en la
  fecha de decisión. El factor del §3.2 ya absorbe las peticiones.
- **NY Fed y GDPNow (#5):** son útiles como principio, pero su objetivo es el PIB trimestral, su evidencia es
  posterior a 2011 y el panel grande es caro.
- **Pesos variables tipo Aastveit (#11):** la evidencia está contaminada (2008-2013) y es demasiado flexible para
  nuestra muestra. Los pesos lentos del §3.1 son la versión prudente.
- **LVQ (#17):** buen historial en tiempo real, pero sin probabilidades para la log-loss y sería un tercer
  aspirante.

---

## 4. Cómo queda el plan con estas ideas

| pieza | Markov TVTP eje G (H-M2-001) | Estructural de G (H-M2-002) | Capa común |
|---|---|---|---|
| señal coincidente | factor del §3.2 como emisión (sustituye a `growth_rt` + peticiones de paro) | factor del §3.2 → tasas t−1…t+4 → Ĝ exacto | — |
| adelantados | solo en las transiciones, γ ≥ 0 (como el Estratega) | `claims_4w_yoy`, `philly_neworders` como indicadores del factor; `baa_d6m`, `eq_ret_6m` opcionales en el AR | — |
| incertidumbre | templado λ (sensibilidad) + varianza de revisión | V̂ del filtro + tendencia + revisión + s<sub>G</sub> | — |
| *plucking* | sensibilidad: + γ<sub>5</sub>·profundidad | sensibilidad: término de recuperación | — |
| calibración | Platt (como M0) | ninguna aparte (σ̂ estructural) o Platt como sensibilidad | **BLP / beta** sobre el pool |
| combinación | — | — | **pool** {M0, struct, tvtp}, pesos walk-forward con previa |
| decisión dura | regla 3 m × 80/20 como métrica secundaria | ídem | ídem |

Infraestructura compartida: **un solo filtro de factor coincidente** alimenta a los dos aspirantes. Esto abarata
la implementación y hace que la diferencia entre ellos sea sobre todo "estados discretos con transiciones" frente a
"composición continua". Es una comparación limpia.

---

## 5. Qué habría que preregistrar (antes de cargar la etiqueta)

1. **Contraste principal y Holm.** Elegir entre:
   - (a) lo decidido: dos aspirantes, Holm k = 2;
   - (b) **recomendado:** el **pool** como único contraste principal (k = 1), con los dos aspirantes y M1 v1/v2
     como secundarios informativos.
   Cambiar de (a) a (b) es una decisión del usuario y debe anotarse como tal en P-EVAL-BASE v4. El cálculo de
   potencia del Constructor debería hacerse para las dos opciones.
2. **Factor coincidente:** series (las 4 de la etiqueta + `claims_4w_yoy` + `philly_neworders`), transformación
   (tasas log mensuales), número de factores (1), dinámica (AR(2)), tratamiento del borde desigual (calendario PIT
   v0.4), modo de cada serie (vintage o `latest_truncated`, como en la base), frecuencia de reestimación
   (mensual, walk-forward).
3. **Composición de Ĝ:** los pesos de la etiqueta (1, 2, 3, 3, 3, 3, 2, 1 / 18), la tendencia PIT (mediana de
   10 años hacia atrás), σ<sub>i</sub> (solo con datos ≤ T), mínimo de indicadores.
4. **Varianza de revisión:** método y muestra (vintages ≤ 2004, sin etiqueta), cifras fijadas **antes** de la
   pasada de desarrollo.
5. **Markov:** la emisión (factor), λ y sus sensibilidades, γ ≥ 0 y previas, anclaje PIT, la referencia `m2_ctp_g`,
   como en el §3.1 del Estratega.
6. **Pool:** componentes, previa de los pesos, ventana, N<sub>min</sub> de arranque (pesos = M0 hasta entonces),
   tratamiento del embargo al usar las log-scores maduras; la forma de la recalibración (BLP o beta de Kull) y su
   previa. **Prohibido:** elegir entre BLP y beta con los datos de desarrollo; se fija una y la otra es sensibilidad.
7. **Métricas secundarias:** la regla de confirmación 3 m × 80/20 (giros declarados, retraso, falsas alarmas
   "declaradas") junto a las del arnés; el estudio de eventos k = −6 … +8.
8. **Sensibilidades que no eligen:** *plucking* (γ<sub>5</sub> y término de recuperación), λ = 1/6 y 1/2,
   Filadelfia prudente, `latest_truncated`.
9. **Contaminación declarada** en `research/hypotheses.yaml` y en el trial log:
   - factor coincidente y pool: método anterior a 2005, elegido el 23-oct tras ver M1 v1/v2 → hipótesis post hoc,
     una pasada de desarrollo;
   - *plucking*: post hoc, solo sensibilidad;
   - cada componente y el pool cuentan como ensayos para Deflated.
10. **Controles:** placebo con la etiqueta barajada para el pool (no solo para los componentes) y señal plantada en
    el factor (un régimen sintético que el filtro recupera).

---

## 6. Contaminación: resumen

| nivel | métodos | por qué |
|---|---|---|
| **Alta** | Michez y Sahm (#14), NY Fed y GDPNow (#5), Aastveit (#11), Vrontos (#16) | diseñados, ajustados o evaluados principalmente con 2008, 2020 o 2024 |
| **Media** | Camacho et al. (#3), ADS (#4), MS-MIDAS (#6), Berge (#8), LVQ (#17), Döpke (#16, datos alemanes, incluye 2008), Fossati (#18) | método anterior o neutro, pero la evidencia publicada incluye el periodo bloqueado |
| **Baja** | Filardo y DLW (#1), Chauvet-Piger (#2), Kauppi-Saikkonen (#7), *pools* y BLP (#9, #10), calibración (#12), regla de confirmación (#13), Jacobs-van Norden y Kishor-Koenig (#18) | método y evidencia principal ≤ 2006, o herramientas genéricas |
| **Post hoc para nosotros** | *plucking* (#15), las variables de las transiciones del TVTP | teoría antigua, pero la elección viene de mirar M1 v1/v2 en desarrollo |

Nota: incluso los de contaminación baja se han **elegido hoy**, sabiendo que la literatura los presenta como
exitosos en 2008 (Chauvet-Piger lo publicó en tiempo real). Eso no ajusta nada a nuestros datos, pero sesga las
expectativas: el listón de ≈ 0,10 nats sigue siendo exigente.

---

## 7. Fuentes consultadas

- Filardo (1994), JBES 12(3): https://ideas.repec.org/a/bes/jnlbes/v12y1994i3p299-308.html
- Filardo (1999), KC Fed Economic Review: https://fedinprint.org/item/fedker/31521
- Diebold, Lee y Weinbach (1994), en Hargreaves (ed.), *Nonstationary Time Series Analysis and Cointegration*, OUP, 283-302 (citado en https://econweb.ucsd.edu/~jhamilton/palgrav1.pdf)
- Chauvet y Piger (2008), JBES 26: https://www.fedinprint.org/item/fedlwp/9583/original ; regla 80/20: https://cepr.org/index%2ephp/voxeu/columns/calling-recessions-real-time ; https://www.calculatedriskblog.com/2013/03/update-recession-probability-chart.html
- Camacho, Pérez-Quirós y Poncela (2018), IJF 34(4): https://www.bde.es/wbe/en/publicaciones/analisis-economico-investigacion/documentos-trabajo/markovswitching-dynamic-factor-models-real-time.html
- Aruoba, Diebold y Scotti (2009), JBES 27(4): https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/ads
- Bok et al. (2018), NY Fed SR 830: https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr830.pdf
- Higgins (2014), GDPNow, Atlanta Fed WP 2014-7: https://www.atlantafed.org/research/publications/wp/2014/07
- Guérin y Marcellino (2013), JBES 31(1): https://ideas.repec.org/p/cpr/ceprdp/8234.html
- Kauppi y Saikkonen (2008), REStat 90(4): https://ideas.repec.org/a/tpr/restat/v90y2008i4p777-791.html
- Berge (2015), J. Forecasting 34(6): https://ideas.repec.org/p/fip/fedkrw/41003.html ; https://www.kansascityfed.org/documents/7708/rwp13-05.pdf
- Berge y Jordà (2011), AEJ Macro 3(2): https://www.aeaweb.org/articles/pdf/doi/10.1257/mac.3.2.246
- Geweke y Amisano (2011), J. Econometrics 164(1): https://www.princeton.edu/~erp/pools_paper.pdf
- Ranjan y Gneiting (2010), JRSS-B 72(1): https://ideas.repec.org/a/bla/jorssb/v72y2010i1p71-91.html
- Aastveit, Ravazzolo y van Dijk, JBES: https://www.norges-bank.no/en/Published/Papers/Working-Papers/2014/17/
- Kull, Silva Filho y Flach (2017), EJS 11(2) / AISTATS: https://projecteuclid.org/euclid.ejs/1513306867
- Michaillat y Saez (2024-25): https://arxiv.org/abs/2408.05856v2 ; https://econbrowser.com/archives/2025/07/guest-contribution-recession-detection-along-the-anticipation-precision-frontier
- OCDE (2026), regla de Sahm en la OCDE: https://www.oecd.org/en/blogs/2026/03/Can-we-predict-recessions-using-only-unemployment-data--Applying-the-Sahm-rule-to-OECD-countries.html
- Kim y Nelson (1999), JMCB 31(3), y libro MIT Press: https://ideas.repec.org/b/mtp/titles/0262112388.html
- Dupraz, Nakamura y Steinsson, NBER w26351: https://www.nber.org/papers/w26351
- Döpke, Fritsche y Pierdzioch (2017), IJF 33(4): https://ideas.repec.org/p/gwc/wpaper/2015-004.html
- Vrontos, Galakis y Vrontos (2021), IJF 37(2): https://ideas.repec.org/a/eee/intfor/v37y2021i2p647-671.html
- Giusto y Piger, LVQ: https://wp.economics.dal.ca/RePEc/dal/wpaper/DalEconWP2013-02.pdf
- Jacobs y van Norden (2011), J. Econometrics: https://rdrr.io/cran/reviser/man/jvn_nowcast.html
- Kishor y Koenig (2012), JBES 30(2): https://ideas.repec.org/p/fip/feddwp/05-01.html
- Fossati (2015), Applied Economics 47(53): https://ideas.repec.org/a/taf/applec/v47y2015i53p5726-5738.html
- Hamilton (2011), IJF 27(4): https://www.nber.org/papers/w16162
- Stock y Watson (2014), J. Econometrics 178 (fechado ex post con 270 series; no se usa): https://www.nber.org/papers/w16532

No he leído la etiqueta, ni datos ≥ 2005, ni corrido ningún modelo, ni tocado código.
