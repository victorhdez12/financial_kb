---
documento: revisión económica de M1 v2 (logística por eje con variables de riesgo de giro y eje I estructural) y propuesta del siguiente aspirante
hito: docs/models/m1_v2_spec.md (4d2b1ac), docs/models/m1_v2_results_dev.md (0553476), docs/models/pit_base.md v0.4 (657b6eb), research/trial_log.md (23-oct)
fecha: 2026-10-23
revisor: Estratega macro
veredicto: ❌ NO gastar el periodo bloqueado en M1 v1 + v2 (no registrar P-EVAL-BASE v3) · ✅ proceso (spec a priori, placebo, una pasada, publicado tal cual) · ⚠️ siguiente aspirante (Markov con transiciones variables) solo con las restricciones de §3 y con una alternativa estructural en paralelo
---

# Revisión económica de M1 v2 (desarrollo ≤ 2004)

## Veredicto

**❌ Ni M1 v2 ni M1 v1 deben ir a la evaluación única.** El proceso ha sido limpio (✅): spec commiteada antes de la
etiqueta, placebo sin fuga ni aviso, una sola pasada, resultado negativo publicado tal cual. El fallo es **económico y
en buena parte mío**:

- De mis cuatro derivadas de la v0.4, dos funcionan como decía el mecanismo (`curve_min12` y `baa_d6m`, con su signo
  en el 100 % de los cortes) y dos no: `sahm_d3m` es redundante y `baa_gap10y` mide **daño acumulado**, que en esta
  etiqueta anuncia rebote, no caída (§1.2).
- Elegí variables con **adelantos de 6-18 meses** para una etiqueta cuyo horizonte útil es de **0-5 meses** (§1.1).
  Por eso M1 v2 confirma antes los giros (−1,6 / −2,3 meses frente a M0), pero da 0,75 falsas alarmas al año.
- La logística aditiva no puede dar a una misma variable un efecto distinto según la fase del ciclo (§1.3).

Gastar ahora el bloqueado daría un "no" casi seguro. El criterio 6 (signos) falla por construcción: la Sahm en v1 y
`baa_gap10y` en v2 tienen el signo contrario en el 100 % de los cortes. Una evaluación cuyo resultado ya se conoce no
informa y tiene un coste irreversible.

**Periodo bloqueado:** no he leído ni puntuado nada ≥ 2005-01, no he abierto la caja fuerte, no he corrido ningún
modelo con la etiqueta y no he tocado código. El único cálculo propio (C5, al final) es descriptivo: usa la matriz PIT
v0.4 ≤ 2004, **sin etiqueta**, y la cronología pública del NBER.

---

## 1. ¿Por qué falla?

Responde a la pregunta de si el problema está en las variables, en la etiqueta o en el enfoque logístico.

**Respuesta corta:** sobre todo en las **variables** (horizonte y forma), con una parte en la **forma funcional**. La
etiqueta no está mal, pero su aritmética fija el horizonte útil y no la tuvimos en cuenta al elegir las variables. Hay
además un límite de **potencia** que conviene tener presente (§1.4).

### 1.1 Lo que impone la etiqueta: 1/3 conocido y 2/3 de previsión a 0-4 meses

- G(t) es el ritmo entre los niveles suavizados de t−3 y t+3. Equivale a una media de las tasas mensuales
  r<sub>t−3</sub> … r<sub>t+4</sub> con pesos 1, 2, 3, 3, 3, 3, 2, 1 (suma 18), menos una tendencia de 10 años
  (ficha de la etiqueta §3).
- En la fecha de decisión (fin del mes t) se conocen, a lo sumo, las tasas hasta t−1. Pesan 1 + 2 + 3 = **6/18 = 1/3**
  del valor de G(t). Las ventas reales (CMRMTSPL) llegan con un mes más de retraso.
- Los **2/3 restantes** son tasas de t a t+4, con pesos 3, 3, 3, 2 y 1. Su horizonte medio ponderado es de **≈ 1,6
  meses después de t**, es decir, unos 2,6 meses después del último dato.
- **Consecuencia:** el nowcast de G es casi un problema de **previsión a muy corto plazo**. Las variables útiles son
  las que adelantan **0-5 meses**:
  - peticiones de paro;
  - encuestas del propio mes (Filadelfia, sobre todo nuevos pedidos);
  - cambios recientes del crédito y de la bolsa.
  La curva invertida (adelanto de 6-18 meses, Estrella-Mishkin 1998) y el nivel del crédito frente a su mediana miran
  **demasiado lejos**. En una logística aditiva bajan P(G alto) meses antes de que la etiqueta cambie: son falsas
  alarmas o adelantos prematuros.
- El patrón del desarrollo encaja con esto:
  - `curve_min12` es el coeficiente más grande (+0,59) y está en el 100 % de los cortes;
  - los giros se confirman antes;
  - las falsas alarmas suben de 0,19 (M0) a 0,75 al año;
  - los meses estables empeoran (−0,012).
- **No es un fallo de la etiqueta:** "mirar 4 meses hacia delante" es lo que hace de la etiqueta un nowcast honesto
  del mes t. Pero obliga a **elegir las variables por su horizonte**, y yo no lo hice en §5 de mi revisión anterior.

### 1.2 El signo de `baa_gap10y`: daño acumulado y rebote (mecanismo, no minería)

Lo explican tres piezas. Ninguna se ha estimado con la etiqueta.

1. **Álgebra de la regresión.**
   - Por definición, `baa_gap10y`(t) = [Baa(t−6) − mediana] + `baa_d6m`(t), con una mediana de 120 meses que casi no
     se mueve en 6 meses.
   - Con las dos variables en el modelo, el coeficiente de `baa_gap10y` mide el efecto del **diferencial de hace 6
     meses frente a lo normal**, manteniendo fijo el empeoramiento reciente.
   - En unidades (C5: σ = 0,62 y 0,48 pp; coeficientes estandarizados medios +0,29 y −0,32), el eje G de M1 v2
     equivale aproximadamente a: **+0,46 por pp del gap de hace 6 meses** y **−0,21 por pp de Δ6m**.
   - Es decir: crédito **caro desde hace tiempo pero que ya no empeora** ⇒ G alto.
   - Sin condicionar, el signo es el esperado: corr(`baa_gap10y`, `growth_rt`) = −0,44. La inversión es parcial (un
     efecto de supresión), no un error de datos.
2. **Economía del ciclo** (descriptivo C5, 6 valles NBER 1970-2001; solo variables, sin etiqueta).

   | meses tras el valle NBER | 0 | +3 | +6 | +9 | +12 |
   |---|---|---|---|---|---|
   | `baa_gap10y` (pp) | 1,21 | 0,93 | 0,83 | 0,73 | 0,69 |
   | `baa_d6m` (pp) | +0,82 | +0,12 | −0,35 | −0,16 | −0,11 |
   | `growth_rt` | −2,99 | −0,92 | +0,15 | −0,15 | −0,20 |

   - El diferencial **alcanza su máximo en el valle** y tarda más de un año en normalizarse.
   - Mientras tanto ya comprime y la actividad se recupera. En esos meses la prima de riesgo es alta y, por tanto, el
     rendimiento esperado del crédito y la relajación financiera por delante también lo son.
3. **La etiqueta es crecimiento frente a tendencia.**
   - Tras una contracción, la economía crece **por encima de la tendencia** aunque el nivel siga por debajo del de
     antes. Es el *plucking model* (Friedman 1964/1993; Kim-Nelson 1999; Dupraz-Nakamura-Steinsson): cuanto más
     profunda la caída, más fuerte el rebote.
   - Por tanto, en esta etiqueta **todo indicador de "daño acumulado"** (un nivel frente a una referencia hacia atrás)
     anuncia **rebote**, condicionado al momento actual.

**Es el mismo mecanismo que la Sahm en nivel en M1 v1** (mi §2 del 16-oct). Debí generalizarlo entonces:
- los **flujos o cambios** (`baa_d6m`, `claims_4w_yoy`, `eq_ret_6m`) tienen un signo estable entre fases;
- los **stocks de daño** (Sahm en nivel, `baa_gap10y`) cambian de signo según la fase.
Un stock de daño solo tiene sentido en una forma **que dependa del estado**, como la probabilidad de salir de G bajo
(§3). En una forma lineal no.

**`sahm_d3m` ≈ 0:** está correlada a +0,66 con `claims_4w_yoy` y a −0,55 con `growth_rt` (C5). Las peticiones de
paro del propio mes ya contienen su información. Es redundancia, no un fallo de mecanismo.

### 1.3 La forma logística

- En los **meses estables** la logística no es el problema: el eje G aislado gana +0,046 en ellos en la ventana larga.
- En los **giros** sí lo es. La logística suma evidencias en una escala única: una curva invertida baja P(G alto)
  tanto en plena expansión como en el rebote. No puede expresar "los adelantados cambian la **probabilidad de
  transición** y los coincidentes dicen el **estado**".
- Esa asimetría es justo la que han revelado los dos signos invertidos (Sahm y `baa_gap10y`).

### 1.4 Potencia: el desarrollo no puede distinguir ganancias de 0,05 nats

- En la principal, el IC de M1 v2 − M0 es [−0,131; +0,078], lo que da un error típico de ≈ 0,053 nats con 183 meses.
- En el bloqueado (2005-01 → 2021-10, ≈ 202 meses) sería de ≈ 0,05. Para cumplir "≥ 0,05 **y** límite inferior
  > 0" hace falta una mejora **observada de ≈ 0,10 nats**.
- La mejor ganancia vista en desarrollo es la del eje G aislado: +0,035. **Ningún aspirante de esta familia está cerca
  del listón.** Es una decisión para el usuario (§4, punto 6), no una razón para cambiar nada en silencio.

## 2. ¿Gastar el periodo bloqueado en M1 v1 + v2? **No, reservarlo.**

- **El resultado está casi decidido de antemano:**
  - ninguna cumple en desarrollo el total, los giros (v1) ni las falsas alarmas;
  - las dos fallan el criterio 6 por un signo invertido en el 100 % de los cortes.
  Una evaluación cuyo resultado se conoce no informa.
- **El coste es irreversible:** la apertura grande 2005-01 → 2021-10 es una sola. Los meses que maduran después son
  pocos y casi no tienen giros.
- **Esperar no cuesta nada económico:** el sistema no opera hasta que haya un modelo validado. La única urgencia es
  operativa: la protección de rama solo existe mientras el repo sea público. No es motivo para gastar el bloqueado en
  un "no" seguro. Si el repo vuelve a privado, se paga Pro o se abre antes de cambiarlo.
- **Qué hacer con v1 y v2:**
  - se quedan en el trial log como **dos ensayos** del modelo base (cuentan para Deflated);
  - en la evaluación futura entran como **secundarias informativas** (fuera de Holm), para que el registro quede
    completo sin quitar potencia a los aspirantes.
  - Esto corrige mi recomendación del 16-oct ("v1 y v2 juntas con Holm"). Aquella servía para no elegir entre ellas
    con datos de desarrollo; ahora el desarrollo las descarta a las dos. Descartar en desarrollo y validar en el
    bloqueado solo lo que pasa el filtro es legítimo: el bloqueado sigue limpio para lo que se le presente.
- **P-EVAL-BASE v3 no se registra.** Habrá una v4 con los aspirantes de §3.

## 3. El siguiente aspirante

### 3.1 Markov con transiciones variables (Filardo 1994; Diebold-Lee-Weinbach 1994): `m2_tvtp_g` (H-M2-001)

**Contaminación declarada.** La familia la propuse el 16-oct tras ver M1 v1. La elección de variables usa lo visto en
M1 v2: fuera `sahm_d3m`, y `baa_gap10y` solo como opción. Es una hipótesis post hoc: una pasada de desarrollo y la
prueba limpia es la evaluación única.

**Alcance:** **solo el eje G.** El eje I es el de M0 (la versión estructural de M1 v2 quedó en −0,004; s = 1,0 en
+0,006): el eje I no es donde está la ganancia y así hay menos comparaciones. La ganancia total será la del eje G.

**Estados.**
- Dos estados, S<sub>t</sub> ∈ {A = G alto, B = G bajo}, **identificados por la etiqueta** (enfoque supervisado). En
  cada corte, la etiqueta de entrenamiento se recalcula con datos ≤ T, como hace el arnés.
- **No** un Hamilton sin supervisión: sus estados aprenderían las recesiones NBER, no "por encima o por debajo de la
  tendencia", y habría que mapearlos después.
- Para estimar, el estado de cada mes de entrenamiento es la etiqueta dura (`p_g_high` ≥ 0,5), con los pesos de
  madurez del arnés. La puntuación sigue siendo la log-loss blanda.

**Transiciones mensuales** (z = variables estandarizadas de forma expansiva; γ ≥ 0 por restricción).

    logit P(S_t = B | S_{t−1} = A) = α_A − γ1·z(curve_min12) + γ2·z(baa_d6m)      [salida de G alto]
    logit P(S_t = A | S_{t−1} = B) = α_B − γ3·z(baa_d6m)     + γ4·z(eq_ret_6m)    [salida de G bajo]

- **Salida de G alto:**
  - una inversión reciente de la curva eleva el riesgo de caída (Estrella-Mishkin);
  - el empeoramiento del crédito coincide con la entrada (Gilchrist-Zakrajšek 2012).
- **Salida de G bajo:**
  - la compresión del crédito y el rebote de la bolsa anuncian la recuperación.
  - Aquí la bolsa ya no puede producir el "falso amanecer" de M1: solo **acelera la transición**, y la emisión
    (`growth_rt`, peticiones de paro) tiene que confirmarla.
- **Opción (decisión del usuario, §4):** añadir + γ5·z(`baa_gap10y`) a la salida de G bajo (el rebote del §1.2, con su
  forma correcta). Está contaminada por el desarrollo de M1 v2. Mi recomendación es **dejarla fuera** de la principal.

**Emisión.**
- x<sub>t</sub> = (`growth_rt`, `claims_4w_yoy`), los datos del estado y del propio mes, en su valor PIT de la fecha
  de decisión.
- Gaussiana con medias propias de cada estado y covarianza común. Las medias absorben el desfase de `growth_rt`
  (centrada en ~t−2).
- **Templado** de la verosimilitud: λ = 1/3, fijo a priori. `growth_rt` solapa tres meses y las peticiones de paro son
  una tasa interanual: sin templar, el filtro contaría la misma información varias veces y daría probabilidades de
  0/1. Esa sobreconfianza es la que castiga la log-loss.
- Sensibilidades preregistradas: λ = 1/6 y λ = 1/2. Se publican y **no eligen**.

**Anclaje PIT del filtro** (el punto delicado).
- Se arranca en el último mes con estado PIT conocido: el mismo desfase h que usa la persistencia PIT del arnés
  (`pers_axis_growth`; el Constructor confirma h, ≈ 5).
- La probabilidad inicial es π = `pers_axis_growth`, con el mismo recorte de 1e-3 que M0.
- Después se filtran h pasos con las filas de decisión t−h+1 … t. Cada fila contiene solo información ≤ su fecha y,
  por tanto, ≤ t.
- Nunca se usa la etiqueta de meses inmaduros.

**Capa de calibración.**
- P<sub>final</sub> = Λ(c + b·logit(p<sub>filtro</sub>)), con L2 = 1 sobre b, en walk-forward, como M0. Así se
  controla la sobreconfianza que quede.
- Con γ = 0 y emisión plana, el modelo se reduce a una persistencia calibrada.

**Restricciones a priori.**
1. γ1-γ4 ≥ 0 (signos impuestos, no solo comprobados).
2. Previa normal N(0; 0,5) sobre cada γ por σ (ridge). Los α, las medias y la covarianza de la emisión van libres.
3. Covarianza común y λ fijo.
4. **No** se meten Filadelfia, la Sahm, el nivel de la curva ni nada más. Son 15 parámetros: 2 α, 4 γ, 4 medias,
   3 de covarianza y 2 de calibración.
5. Mínimos del arnés sin cambios. Por las peticiones de paro (desde 1968-02), la ventana de desarrollo es la larga del
   eje G: **1978-07 → 2004-12**, 318 meses y 10 giros.

**Cómo se compara con M0 en el arnés.**
- Mismo walk-forward v2.1: refit mensual, embargo de 6 meses, purga, vintage como modo principal y latest_truncated
  como sensibilidad, base PIT v0.4 **congelada**.
- **Una sola pasada de desarrollo** sobre 1978-07 → 2004-12 y su subventana 1989-10 → 2004-12, para comparar con
  M1 v2.
- Se informan los mismos cortes que en M1 v2:
  - total, giros y estables;
  - subperiodos y episodios;
  - detección de giros de G con retraso y falsas alarmas al año;
  - calibración;
  - signos de los γ.
- Además, un **estudio de eventos k = −6 … +8** como el C3 del 16-oct. El objetivo realista es no perder frente a M0
  en k = −2 … +2 y ganar de k = +2 en adelante.
- **Referencias anidadas** (secundarias, fuera de Holm):
  - el mismo Markov con γ = 0 (`m2_ctp_g`, transiciones constantes), que aísla lo que aportan las transiciones
    variables;
  - el eje G de M1 v2.
- **Controles antes de la etiqueta real:**
  - placebo con la etiqueta barajada en bloques de 24, con las mismas reglas de fuga y aviso;
  - señal plantada: un TVTP sintético con γ conocidos que el estimador recupera;
  - con z = ruido, los γ se encogen y ll(`m2_tvtp_g`) ≤ ll(`m2_ctp_g`) + ε.
- **Criterio de éxito en la evaluación única:** el de A3 de P-EVAL-BASE, sin cambios (total, giros ≥ 0, estables
  ≥ −0,05, falsas alarmas ≤ 0,5, subperiodos y signos), con Holm sobre los aspirantes.

**Riesgos.**
1. **Identificación.**
   - Con unos 8-10 giros por ventana de entrenamiento, cada logística de transición se estima con ~4-5 eventos.
   - Las previas mandan y el modelo puede quedar ≈ `m2_ctp_g`. Por eso la referencia anidada es obligatoria: si el
     TVTP no supera al de transiciones constantes, el mecanismo no está demostrado aunque el total gane.
2. **Sobreconfianza del filtro.** Es el modo de fallo típico de los Markov con log-loss. Se mitiga con λ y con la capa
   de calibración, pero puede seguir pasando.
3. **El desajuste de horizonte del §1.1 sigue ahí.** `curve_min12` en la salida de G alto puede adelantar demasiado.
   La ventaja frente a M1 es que su efecto queda limitado por la emisión, pero no desaparece.
4. **Dos estados para una etiqueta con rebote.** El *plucking* sugiere una tercera fase de recuperación (Sichel 1994).
   No la añado: más estados con ~10 giros no se identifican.
5. **Linaje de las peticiones de paro.** Tienen vintage solo desde 2009-05; antes son latest_truncated (está en la base
   y lo trata el arnés). En el bloqueado cambia el modo de una de las dos variables de emisión.
6. **Contaminación y potencia** (§1.4). Aunque sea el modelo "correcto", superar un listón de ~0,10 nats observados es
   improbable.

### 3.2 Una alternativa que considero mejor, o al menos imprescindible a su lado: el nowcast estructural de G (`m2_struct_g`, H-M2-002)

Es la consecuencia directa del §1.1 y la misma idea que el eje I estructural, aplicada a G.

- **Forma:** P(G alto)<sub>t</sub> = Φ(Ĝ<sub>t</sub> / σ̂<sub>t</sub>), con
  Ĝ<sub>t</sub> = a + b·`growth_rt` + c·Ĝ<sub>pers</sub> + β′·x<sub>t</sub>.
  - Es una **regresión del valor continuo de G** (de la etiqueta recalculada con datos ≤ T), no de la probabilidad
    `p_g_high`.
  - σ̂ es el residuo walk-forward combinado con s<sub>G</sub> = 0,40 de la ficha.
- **Variables:**
  - `growth_rt`: la parte conocida, ≈ 1/3 de la ventana;
  - Ĝ<sub>pers</sub>: el último G PIT conocido, con ventanas que se solapan;
  - x = `claims_4w_yoy` (−), `philly_neworders` (+), `baa_d6m` (−) y `eq_ret_6m` (+). Son los adelantos de 0-5
    meses para los 2/3 por conocer.
  - Signos impuestos y L2 como M1. **Sin** variables de horizonte largo ni stocks de daño.
- **Por qué puede ser mejor que el Markov:**
  1. Usa **todos los meses** y la **magnitud** de G. La logística con objetivo blando la pierde porque Φ satura cuando
     |G| > 0,8. El Markov depende de ~10 transiciones.
  2. La calibración sale de la propia aritmética de la etiqueta (σ̂ y s<sub>G</sub>), no de una capa añadida.
  3. Ataca directamente el desajuste de horizonte, que es la causa principal del fallo (§1.1).
- Es la tradición de los nowcasts puente y de factores (Giannone-Reichlin-Small 2008).
- **Coste:**
  - el arnés debe pasar al modelo el valor continuo de G de entrenamiento (cambio pequeño del Constructor: hoy pasa
    `p_g_high`);
  - Filadelfia viene de la v0.3 (latest_truncated; la matriz "prudente" como sensibilidad);
  - no hace falta una v0.5.
- **Riesgo:** como con el eje I, la persistencia puede recoger casi todo y quedar ≈ M0. Sería una respuesta honesta:
  diría que el nowcast de G con datos públicos mensuales no supera a la persistencia por un margen que se pueda
  detectar.

**Recomendación:**
- Preregistrar **los dos** (H-M2-001 TVTP y H-M2-002 estructural), con una pasada de desarrollo cada uno, y llevar a
  la evaluación única los que no fallen en desarrollo por signos o falsas alarmas, con **Holm k ≤ 2**.
- Si solo hay capacidad para uno, empezaría por el **estructural**: más barato, mejor identificado y dirigido a la
  causa.
- El GBM monótono queda detrás de los dos, por el mismo problema de pocos giros.

## 4. Decisiones para el usuario

1. **¿Gastar el bloqueado en M1 v1 + v2 (P-EVAL-BASE v3)?** Recomiendo **no**: reservarlo y no registrar la v3 (§2).
2. **Congelar la base PIT v0.4** tras el ✅ del Validador. Recomiendo **sí**: la usan los dos aspirantes. Congelarla
   no avala `baa_gap10y` ni `sahm_d3m` como predictores; solo fija la base.
3. **Siguiente aspirante:** (a) solo el Markov TVTP de §3.1; (b) solo el estructural de §3.2; (c) **los dos, con Holm
   k ≤ 2 (recomendado)**. Si solo uno, el (b).
4. **`baa_gap10y` en la salida de G bajo del Markov:** recomiendo **fuera** (contaminada por el desarrollo de M1 v2).
5. **M1 v1 y v2 en la apertura futura:** como **secundarias informativas fuera de Holm** (recomendado) o fuera del
   todo. Cuentan siempre como dos ensayos.
6. **Potencia:**
   - Con el criterio actual, cualquier aspirante necesita ≈ 0,10 nats observados en el bloqueado (§1.4).
   - Opciones:
     - (i) mantener el criterio y asumir que lo probable es "M0 sigue";
     - (ii) antes de registrar la v4, pedir al Constructor un cálculo de potencia con datos sintéticos y decidir con
       él (recomendado);
     - (iii) reformular el contraste principal al eje G, con el retraso de detección como co-criterio.
   - Cualquier cambio de criterio se anota como tal, antes de abrir.
7. **Eje I:** dejar el de M0 en la evaluación y archivar el estructural (≈ M0). Recomiendo **sí**: no iterar más el
   eje I.
8. **Repo público:** no hay prisa por abrir. Si el repo va a volver a privado, pagar Pro o planificar la apertura
   antes de cambiarlo.

## 5. Resumen priorizado

1. M1 v2 falla sobre todo por **horizonte**: variables de 6-18 meses para una etiqueta con 2/3 de previsión a 0-4
   meses.
2. Falla también por **forma**: stocks de daño en una logística lineal. `baa_gap10y` al revés es el rebote
   (*plucking*), el mismo mecanismo que la Sahm en v1.
3. No gastar el bloqueado. v1 y v2 quedan como ensayos e informativas.
4. Siguiente aspirante: Markov TVTP solo para el eje G, con transiciones restringidas, emisión templada, anclaje PIT y
   referencia de transiciones constantes. A su lado, el nowcast estructural de G, que considero el más prometedor.
5. Calcular la potencia antes de registrar P-EVAL-BASE v4.

No he modificado código ni datos del proyecto.

---

## Cálculos para el trial log (2026-10-23, Estratega macro)

- **C5. Descriptivos de las variables de crédito y de la Sahm, ≤ 2004, SIN etiqueta.**
  - **Fuentes:** solo la matriz `pit_us_v0.4_vintage.parquet`, leída con el filtro `decision_date` < 2005-01-01, y la
    cronología pública del NBER (picos 1969-12, 1973-11, 1980-01, 1981-07, 1990-07, 2001-03; valles 1970-11,
    1975-03, 1980-07, 1982-11, 1991-03, 2001-11). Ni la etiqueta ni `LabelVault`; no se ajusta ningún modelo.
  - **Muestra:** 1968-02 → 2004-12, meses con `baa_gap10y` y `baa_d6m`.
  - **Desviaciones:** `baa_gap10y` 0,624, `baa_d6m` 0,477, `growth_rt` 0,987, `claims_4w_yoy` 19,4, `curve_min12`
    1,283, `sahm_d3m` 0,398.
  - **Correlaciones:**
    - `baa_gap10y`: con `baa_d6m` +0,42, con `growth_rt` −0,44;
    - `sahm_d3m`: con `claims_4w_yoy` +0,66, con `growth_rt` −0,55.
  - **Medias en k meses respecto a valles y picos NBER:** tabla del §1.2.
  - **Reescritura de los coeficientes publicados de M1 v2** (`m1_v2_results_dev.md` §5; no reestimados) en pp:
    +0,46 sobre el gap de hace 6 meses y −0,21 sobre Δ6m.
  - **Contaminación:** es descriptivo y no mira la etiqueta, pero se hace **después** de ver M1 v2. La forma de
    `baa_gap10y` propuesta para el Markov (salida de G bajo) queda declarada post hoc.
- Script: `/private/tmp/claude-501/-Users-victorhdez12/cd4fb921-a088-4800-bfaa-451b4eaab86f/scratchpad/baa_desc.py`.
  Nada ≥ 2005.
