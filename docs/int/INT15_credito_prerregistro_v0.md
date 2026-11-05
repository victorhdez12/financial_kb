---
documento: P-DEV-INT15 — "crédito antes que bolsa": ¿el diferencial de crédito de EE. UU. añade aviso de entrada en mercado bajista (6 m) y de volatilidad (1 m) al modelo actual sin crédito? Diseño + potencia + borrador de prerregistro
version: 0.1 (borrador, 2026-11-05) — NO congelado; nada corrido sobre resultados
estado: BORRADOR. Solo diseño y potencia. Ninguna serie de crédito se ha cruzado con ningún objetivo; ningún dato ≥ 2005 leído.
potencia: scripts/int15_potencia.py (commit af1f43e, árbol limpio, 2026-11-05T08:16Z, 533 s) → research/int/int15_potencia.json
depende_de: docs/int/INT12_prerregistro_v1.md (HAR, QLIKE, DM, calendario de re-estimación), research/int/int12_resultado.md
  (C1 HAR establecido frente a B1; C2 HAR-X con crédito NO establecido, −4,7 %), docs/int/E1_prerregistro_v1.md (formato,
  ΔAUC, placebo circular), docs/int/INVENTARIO_relaciones.md §2.4 (crédito-precio: "sin probar" frente a la bolsa)
---

# P-DEV-INT15: ¿el crédito avisa antes que la bolsa? (borrador v0.1)

## 0. Qué se pregunta (y lo que NO)
- **Pregunta principal (O1):** con datos mensuales "as of" de EE. UU. ≤ 2004, ¿añadir el **cambio a 6 meses del
  diferencial Baa − Aaa** al modelo actual de riesgo (el **HAR** de INT-12, sin crédito) ordena mejor los meses en los que
  la bolsa de EE. UU. **entra en mercado bajista (−15 %) en los 6 meses siguientes**, fuera de muestra (walk-forward)?
- **H1 (unilateral):** ΔAUC = AUC(A) − AUC(L) > 0, con A = HAR + crédito y L = HAR (listón). **H0:** ΔAUC ≤ 0.
- **Secundaria (O2, recomendada como descriptiva, decisión 2):** ¿el mismo rasgo reduce el QLIKE de la volatilidad
  realizada a 1 mes frente al HAR?
- **No es** un modelo de *timing* ni una regla de cartera (eso es B1′ y otra pregunta, sin potencia); no es un nowcast de
  recesión (eso fue M1/M1 v2 y E1); no usa NFCI (no es "as of"), ni EBP, ni BAMLH* (solo desde 2023), ni el VIX.
- **Listón = el modelo actual sin crédito** (HAR lineal de INT-12, que es el modelo operativo de volatilidad). La pregunta
  es solo si el crédito **añade** (anidado).

## 1. Contaminación (declarada) y mitigación
**Por qué INT-15 no es ciega:**
1. **La idea es famosa y se elige por eso.** "El crédito se ensancha antes de que caiga la bolsa" es folclore de mercado
   y literatura con resultados positivos publicados (sesgo de publicación). Se recuerdan de memoria episodios que la
   favorecen (1998 LTCM, 2000-02, 2007 fuera de muestra) y otros que no (1987: sin aviso del crédito). → **Maldición del
   ganador:** el efecto realista se fija en la **mitad** del "optimista" (ΔAUC +0,04 frente a +0,08; §6).
2. **El crédito ya se cruzó con la volatilidad ≤ 2004 (INT-12 C2):** HAR-X (con Baa − Aaa en **nivel**, curva, corto y
   régimen) fue **un 4,7 % peor** que el HAR a 1 m (−10,7 % a 3 m), y en el descriptivo de P(caída ≥ 10 % en 3 m) HAR-X
   no mejoró el Brier (0,1055 frente a 0,1043). Sabemos, pues, que **el nivel** del diferencial no ayuda en los datos
   ≤ 2004. O2 queda **muy contaminada** (por eso se propone descriptiva) y O1 algo (el objetivo de INT-12 era distinto:
   caída ≥ 10 % desde el origen a 3 m, no entrada en bajista a 6 m, y el crédito iba en nivel).
3. **El cambio a 6 meses ya se usó** como rasgo `baa_d6m` (Baa − GS10) en M1 v2 y M3 TVTP (nowcast del eje de
   crecimiento, ≤ 2004): allí tuvo el signo esperado en el 100 % de los cortes; `baa_gap10y` (nivel frente a su mediana)
   salió al revés (marca rebote). La elección "cambio y no nivel" **usa** esas lecciones: no es ciega.
4. **Los datos ≤ 2004 están gastados en general** (INT-3b, INT-4, INT-12, INT-13, M1…). Lo nuevo es solo el cruce
   crédito → entrada en bajista, que nadie ha mirado en el proyecto (`INVENTARIO_relaciones.md` §2.4: "sin probar").

**Mitigación (todo fijado antes de cruzar nada):**
- (M1) **Una variable, un objetivo, un contraste** (O1); O2 descriptiva. Sin búsqueda de umbrales, horizontes ni
  transformaciones: −15 %/+15 %, 6 m y Δ6 están fijados aquí, antes de cruzar.
- (M2) **Potencia con el efecto a la mitad** y veredicto honesto escrito antes (§6, §7).
- (M3) **Evaluación fuera de muestra (walk-forward con embargo de 6 m)**: ninguna métrica dentro de muestra cuenta.
- (M4) **Placebos** (§8): desplazamiento circular del crédito (da el p), crédito retrasado 24 m y signo al revés.
- (M5) Publicar el ΔAUC **por episodio** (11 episodios en la evaluación) para que no lo decida uno solo (2000-02 tiene
  5 entradas).
- (M6) **Procedencia** con puerta (§9). Es una corrida de **desarrollo** con datos ≤ 2004: un "establecido" sería un
  candidato, no una confirmación (la confirmación necesitaría el bloqueado o el vivo; decisión 6).

## 2. Datos (todo "as of" en el último día hábil del mes M; NADA ≥ 2005)
| uso | serie | familia permitida (`src/intl/data.py`) | desde | "as of" en el fin de M |
|---|---|---|---|---|
| crédito (rasgo) | `BAA`, `AAA` (Moody's, media mensual, %) | ya permitidas (`BAA|AAA|GS10`) | 1919-01 | se usa **M − 1** (como INT-12: la media de M se publica a primeros de M + 1) |
| crédito (alternativa, decisión 3) | `BAA` − `GS10` | ya permitidas | 1953-04 | M − 1 |
| crédito diario (no se usa) | `DBAA`, `DAAA`, `BAA10Y`, `AAA10Y` | **no** permitidas | 1983/86 | solo inventario: no cubren 1950-1985 |
| bolsa (objetivo y HAR) | `aqr_mkt_usa_d` (exceso diario CRSP, %) | ya permitida (INT-12) | 1926-07 | cierre del día |
| letra (para rentabilidad total aprox.) | `TB3MS` | ya permitida (INT-12) | 1934-01 | objetivo ex post: TB3MS del mes / 252 por día (0 antes de 1934) |

- **Rasgo de crédito (único, decisión 1):** `cred_d6(M) = (BAA − AAA)(M − 1) − (BAA − AAA)(M − 7)`, en pp. Signo esperado:
  **+** (ensanchamiento → más riesgo de entrada en bajista). Razón del cambio y no del nivel: el nivel tiene deriva
  secular y escalas distintas por década (lo que hundió a HAR-X en INT-12) y, en nivel alto, marca rebote (M1 v2).
- **Listón (HAR, de `src/intl/int12.rasgos_diarios`):** log de la media de r² de 5, 21 y 63 días hasta el origen; la
  previsión HAR a 1 m de INT-12 (`log f_HAR`), re-estimada cada enero exactamente como en INT-12.
- Inventario de cobertura en `research/int/int15_potencia.json → inventario` (sin leer valores de crédito).

## 3. Objetivo O1: entrada en mercado bajista en los 6 meses siguientes
- **Índice:** rentabilidad total aproximada = Π(1 + exceso diario AQR + TB3MS/252). Declarado: no es el S&P de precio;
  las caídas de un índice de rentabilidad total son algo menores (el dividendo compensa) y la letra resta en los 70-80.
- **Fechado (Lunde-Timmermann 2004, filtros fijos):** en un tramo alcista se sigue el máximo; el día en que el índice cae
  **15 %** por debajo de ese máximo hay una **entrada en bajista**; el tramo bajista sigue el mínimo y termina cuando el
  índice sube **15 %** desde él. El estado en el origen solo usa precios ≤ origen ("as of").
- **y(M) = 1** si hay una entrada en (origen M, origen M + 6 meses]. **En riesgo:** orígenes en estado alcista.
- **Evaluación:** orígenes 1950-01 … 2004-06 (el objetivo acaba ≤ 2004-12), como INT-12. **Ajuste:** desde 1926-10
  (primer origen con 63 días), ventana creciente, embargo: solo filas cuyo objetivo de 6 m acabó antes del origen.

**Estructura de eventos ≤ 2004 (solo la bolsa; ningún rasgo cruzado)** (`eventos_*` en el JSON):

| definición | muestra | orígenes en riesgo | positivos | entradas | episodios (gap 12 m) |
|---|---|---|---|---|---|
| **LT −15 % / +15 % (principal)** | evaluación 1950-01 … 2004-06 | **571** (de 654) | **81** (14,2 %) | **15** | **11** |
| ídem | ajuste + evaluación 1926-10 … 2004-06 | 789 | 157 | 34 | 17 |
| LT −20 % / +20 % (variante) | evaluación | 597 | 69 | 12 | 10 |
| caída ≥ 15 % desde el origen en 6 m (variante, todos en riesgo) | evaluación | 654 | 68 | — | 11 |
| caída ≥ 20 % desde el origen en 6 m (variante) | evaluación | 654 | 36 | — | 5 |

Entradas en la evaluación (LT 15/15): 1957-10, 1962-05, 1966-08, 1969-07, 1973-05, 1980-03, 1981-09, 1987-10, 1990-08,
1998-08, 2000-04, 2000-11, 2001-09, 2002-06, 2002-10. En el ajuste antes de 1950: 19 entradas, 13 en los años 30.
**Lectura:** ≈ 11 episodios independientes en la evaluación; es la cantidad de información que manda (como en E1).

## 4. Modelos (fijados aquí)
- **L (listón):** logit(y ~ `log f_HAR`) — el "modelo actual sin crédito" (HAR de INT-12; en INT-12 la P(caída) también
  era una logística sobre log f). Signo esperado +.
- **A (candidato):** logit(y ~ `log f_HAR` + `cred_d6`). Anidado; signo esperado de `cred_d6`: +.
- Ajuste con `src/intl/int4.logit_fit` (sin penalizar), re-estimado **cada enero** desde 1950 con las filas de ajuste
  disponibles (embargo 6 m); predicción de los 12 orígenes de ese año. Mismo calendario y mismas filas para L y A.
- Si el signo de `cred_d6` sale negativo en la mayoría de los ajustes anuales, se publica y no se cambia nada.

## 5. Métrica y contraste único
- **Principal: ΔAUC "de índice"** sobre los orígenes de evaluación apilados: listón = `log f_HAR` (su rango no depende
  del reajuste anual), candidato = `log f_HAR + (β̂₂/β̂₁)·cred_d6` con los coeficientes de ese año. Aísla si el crédito
  **añade orden** y evita un artefacto hallado en la simulación (§6): al apilar las probabilidades de cada año, la deriva
  del intercepto (el ajuste arranca con los años 30, tasa 20 %) baja el AUC del listón de 0,64 a ≈ 0,56 y añade ruido.
  El ΔAUC "apilado" (probabilidades) se publica como secundario.
- **p del contraste:** placebo de desplazamiento circular de `cred_d6` (§8 P1), unilateral; α = 0,05 (o 0,025 si se
  aprueba la familia Holm-2 con O2, decisión 2).
- **Secundarios (sin veredicto):** Δlog-loss y ΔBrier de las probabilidades apiladas; ΔAUC por episodio; variantes de
  objetivo de §3 (−20 %, desde el origen); ΔAUC con la alternativa Baa − GS10 (1953-, solo si se aprueba, decisión 3).
- **O2 (descriptiva, recomendado):** HAR frente a HAR + `cred_d6` en QLIKE a 1 m (fórmula, DM HAC NW 6 y calendario de
  INT-12, orígenes 1950-01 … 2004-11); con el ajuste de Clark-West para modelos anidados como p principal de O2 si se
  eleva a confirmatoria.

## 6. Potencia (antes que nada)
**Método** (`scripts/int15_potencia.py`; 600 réplicas por punto en O1 y 300 en O2; error Monte Carlo ≈ ± 0,02-0,03):
- **O1:** estructura de eventos **real** ≤ 2004 (789 filas en riesgo 1926-10 … 2004-06, 34 entradas; evaluación 571 / 81
  / 15 entradas / 11 episodios) y rasgos **simulados**: `x1` = HAR (a·y + u) con AUC poblacional del listón 0,65 (rejilla
  0,60-0,70; no se ha medido el AUC real del HAR para este objetivo, para no cruzar nada), `x2` = crédito (b_e·y + w).
  u y w AR(1) mensuales φ = 0,9 (sensibilidad 0,97); b_e = b + τ·N(0,1) por entrada (**heterogeneidad entre episodios**:
  1987 sin aviso del crédito, 1998 con mucho). Walk-forward **idéntico** al diseño (logit re-estimado cada enero desde
  1950, embargo 6 m). Contraste unilateral con el **valor crítico de la nula simulada** (b = 0), que equivale al p del
  placebo P1. "Δ poblacional" = ΔAUC del oráculo (coeficientes verdaderos), la escala en la que se expresa el MDE.
- **O2:** log RV mensual simulado (dos componentes AR 0,98 / 0,7 + ruido t5; dt marginal 0,886 = la real de 1950-2004 en
  INT-12; R² del HAR 0,45-0,65), crédito AR(1) 0,85 correlacionado ρ con los choques de volatilidad (0 / 0,4); HAR
  mensual frente a HAR + crédito por MCO walk-forward anual con Duan; DM HAC NW 6 con el crítico nominal (1,645) y con el
  de la nula simulada (≈ Clark-West: el modelo anidado paga el coste de estimar un coeficiente).
- **Historia del script (declarada):** la primera versión (commit 7fc9b1c) solo medía el ΔAUC "apilado"; al ver en la
  simulación (datos inventados, ningún dato real cruzado) que la deriva del intercepto hundía el AUC del listón de 0,64
  a ≈ 0,56, se añadió el ΔAUC "de índice" (commit af1f43e) y se rehízo la tirada. El JSON de la primera tirada no se
  guardó; sus cifras del apilado coinciden con las de la segunda (misma semilla).

**O1 — ΔAUC índice (principal), unilateral 5 %** (`potencia_O1.*.indice`):

| escenario | MDE 80 % (Δ poblacional) | potencia si +0,04 (realista) | potencia si +0,08 (optimista) | P(ΔAUC ≤ 0) si +0,04 / +0,08 / sin efecto |
|---|---|---|---|---|
| **central** (AUC listón 0,65, τ 0,25, φ 0,9) | **0,11** | **0,42** | **0,66** | 0,37 / 0,19 / 0,81 |
| τ 0 | 0,11 | 0,39 | 0,63 | 0,36 / 0,19 / 0,80 |
| τ 0,5 | 0,13 | 0,33 | 0,60 | 0,45 / 0,19 / 0,78 |
| AUC listón 0,60 | 0,14 | 0,30 | 0,51 | 0,43 / 0,27 / 0,79 |
| AUC listón 0,70 | 0,09 | 0,44 | 0,74 | 0,34 / 0,13 / 0,80 |
| φ 0,97 (más persistencia) | 0,13 | 0,31 | 0,62 | 0,46 / 0,19 / 0,78 |

Con Holm-2 (α 2,5 %): MDE 0,12-0,19; potencia con +0,04: 0,17-0,32. El ΔAUC "apilado" (secundario) da MDE parecidos
(0,08-0,14), pero con el AUC del listón hundido a ≈ 0,56 por la deriva del intercepto (por eso no es el principal).
Bajo la nula, el ΔAUC índice medio es −0,02 a −0,035 (coste de estimar un coeficiente con pocos eventos al principio):
sin efecto, P(ΔAUC > 0) ≈ 0,20.

**O2 — ganancia de QLIKE a 1 m, 659 orígenes** (`potencia_O2`):

| escenario | MDE 80 % (crítico de la nula ≈ CW) | MDE 80 % (DM nominal 1,645) | potencia con ganancia ≈ 1 % (crít. nula / nominal) | ídem ≈ 3 % |
|---|---|---|---|---|
| R² HAR 0,55, ρ 0,4 (central) | 7,0 % | > 9 % (no se alcanza) | 0,25 / 0,13 | 0,61 / 0,43 |
| R² 0,55, ρ 0 | 5,7 % | 8,9 % | 0,41 / 0,22 | 0,67 / 0,48 |
| R² 0,45, ρ 0,4 | 7,8 % | 10,4 % | 0,29 / 0,20 | 0,55 / 0,42 |
| R² 0,65, ρ 0,4 | 5,5 % | > 9 % | 0,44 / 0,24 | 0,67 / 0,45 |

(INT-12, con su simulación diaria y el "ML" como mezcla hacia el oráculo, daba MDE ≈ 2 % para la información; aquí, con
un rasgo cuyo coeficiente hay que estimar y RV con colas t5, sale 5,5-8 %. La cifra prudente es la de este script.)

**Lectura honesta:**
- **O1: MDE ΔAUC ≈ 0,11 (0,09-0,14).** El efecto realista (+0,04, la mitad del optimista por la maldición del ganador)
  tiene **potencia 0,30-0,44**; incluso el optimista (+0,08), solo 0,51-0,74. La razón es la de E1 e INT-8: **11
  episodios** en 1950-2004 (2000-02 concentra 5 de las 15 entradas). Muchas filas, poca información.
- **El signo informa poco:** con +0,04, P(ΔAUC ≤ 0) ≈ 0,34-0,46; sin efecto, ≈ 0,8 → un ΔAUC ≤ 0 multiplica por ≈ 2 la
  verosimilitud de "no añade" (× 4 frente a +0,08). Un ΔAUC > 0 apenas confirma (≈ × 2,5-3,3).
- **O2: MDE ≈ 5,5-8 % de QLIKE**, frente a una ganancia realista ≤ 1-2 % (y un precedente propio negativo: HAR-X −4,7 %
  con el crédito en nivel). **Sin potencia** y muy contaminada.
- **Veredicto: sin potencia para establecer nada con un efecto realista.** O1 solo detectaría con un 80 % un efecto
  ≥ 0,11 de ΔAUC, más de lo que cabe esperar de un rasgo famoso tras la maldición del ganador. No recomiendo gastar ahora
  el cruce crédito → bolsa ≤ 2004 (§10, decisión 5).

## 7. Criterios (O1, muestra 1950-2004)
- **Establecido (todos):** (i) ΔAUC índice > 0 con p del placebo P1 < 0,05 (unilateral); (ii) Δlog-loss apilado < 0;
  (iii) β̂(`cred_d6`) > 0 en ≥ 2/3 de los ajustes anuales; (iv) ΔAUC > 0 en ≥ 6 de los 11 episodios **y** sin 2000-02.
- **Refutado** ("el cambio del crédito no añade aviso al HAR"): ΔAUC índice ≤ 0. Probabilidad de refutar por error si el
  efecto real es +0,04: ≈ 0,34-0,46; si es +0,08: ≈ 0,13-0,27; sin efecto: ≈ 0,8 (el coste de estimar un coeficiente más).
- **Ni lo uno ni lo otro** (lo más probable con un efecto realista): "no contradicho; sin potencia para establecerlo".
- **Consecuencia decidida de antemano:** aunque saliera establecido, **no** entra en B1 ni en el reporte como señal de
  venta: abre (a) un prerregistro de confirmación (bloqueado o vivo, decisión 6) y (b) un descriptivo en el reporte
  semanal ("crédito: Δ6 en el percentil p"), sin probabilidad.

## 8. Placebos y controles
- **P1 desplazamiento circular (da el p):** `cred_d6` se desplaza k meses en círculo sobre 1926-10 … 2004-06
  (k ∈ [24, T − 24]); se repite el walk-forward completo; p = (1 + #{ΔAUC_k ≥ ΔAUC_obs}) / (1 + nº de k). Conserva la
  persistencia del crédito y la estructura de eventos; rompe la alineación.
- **P2 crédito retrasado 24 m:** no debería ayudar; si ayuda, algo va mal (fuga o efecto de nivel). Descriptivo.
- **P3 signo:** si β̂ < 0 en la mayoría de los años, se publica como "el crédito marca rebote" (la lección de M1 v2).
- **P4 señal plantada (sintético, antes de la corrida):** la tubería con datos inventados recupera una señal conocida y
  da ΔAUC ≈ 0 sin señal (la simulación de este script ya fija los órdenes de magnitud).
- **P5 corte PIT:** test de que nada ≥ 2005 entra (load_dev) y de que `cred_d6` en el origen M solo usa meses ≤ M − 1.

## 9. Procedencia y puerta
- `scripts/int15_corrida.py` (no escrito): `src/intl/procedencia.procedencia(exigir_limpio=True)`; comprueba el sha256
  de este documento congelado (v1.0); se niega si la salida ya existe; solo `load_dev` (≤ 2004). Una corrida; entrada en
  `research/trial_log.md`; Validador independiente.

## 10. Decisiones pendientes del usuario (con mi recomendación)
1. **Rasgo de crédito:** **recomendado uno solo, `cred_d6` (Δ6 de Baa − Aaa, M − 1)**. Alternativas: + nivel de
   Baa − Aaa (2 rasgos: más coste de estimación y el nivel ya falló en INT-12 C2); Δ3 en lugar de Δ6 (más rápido pero más
   ruidoso; elegir entre los dos después de mirar sería minería).
2. **Objetivos y familia:** **recomendado O1 único (sin Holm); O2 solo descriptiva**. O2 está contaminada por INT-12 C2 y
   su MDE (5,5-8 % de QLIKE) está muy por encima de lo realista. Alternativa: Holm-2 {O1, O2} (MDE de O1 sube a
   0,12-0,19).
3. **Diferencial:** **recomendado Baa − Aaa** (1919-, cubre todo el ajuste, el riesgo de impago "puro" sin el término
   de plazo del Tesoro). Baa − GS10 (1953-) solo como secundario: deja el ajuste sin los años 30 (la mitad de las entradas).
4. **Objetivo:** **recomendado LT −15 % / +15 % a 6 m** (15 entradas / 11 episodios en la evaluación). −20 % deja 12 / 10;
   "caída ≥ 20 % desde el origen" solo 5 episodios. Todas las variantes, descriptivas.
5. **¿Correr INT-15 ahora?** **Recomendado: NO.** Con 11 episodios, la potencia para el efecto realista es 0,30-0,44 y
   el resultado más probable ("no establecido") no cambiaría ninguna decisión (B1 no usa el crédito; el reporte no da
   señales de venta). Correrlo gastaría el único cruce limpio crédito → bolsa ≤ 2004 sin poder interpretarlo.
   Alternativas: (a) correrlo igualmente como prueba de **refutación** (formato P-EVAL-INT4: solo un ΔAUC ≤ 0 informa,
   × 2); (b) **registro prospectivo en vivo** como E1 (barato; sin respuesta útil en décadas: ≈ 1 entrada en bajista
   cada 4-5 años); (c) solo un **descriptivo** en el reporte semanal (Δ6 del crédito y su percentil histórico, sin
   probabilidad ni regla). **Mi recomendación: (c), y (b) si se quiere dejar la puerta abierta.**
6. **Si se corriera y saliera establecido:** confirmación en el bloqueado o en vivo, nunca con ≤ 2004. **Recomendado: en
   vivo** (el bloqueado se reserva para lo ya establecido: P-EVAL-INT4, X1, motor v3), y declarar que el bloqueado tiene
   ≈ 3-4 entradas en bajista conocidas de memoria (2007-08, 2011, 2020, 2022), con 2020 sin aviso del crédito.
7. **Métrica principal:** **recomendado ΔAUC de índice** (invariante a la deriva del intercepto); el apilado y la
   log-loss como secundarios/condición.
8. Si se aprueban 1-7 y la decisión 5 es correr, este borrador pasa a v1.0 con hora **antes** de escribir
   `scripts/int15_corrida.py` (que reutilizaría `src/intl/int12` para el HAR).
