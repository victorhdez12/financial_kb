---
documento: revisión económica de la base point-in-time v0.1 (lista blanca y calendario)
hito: docs/models/pit_base.md, docs/models/pit_calendar.md, research/pit_whitelist.yaml, research/pit_calendar.yaml
fecha: 2026-10-15
revisor: Estratega macro (buy-side, nowcasting EE. UU.)
veredicto: ⚠️ SIRVE CON CAMBIOS
---

# Revisión económica de la base point-in-time v0.1

## Veredicto: ⚠️ sirve con cambios

La arquitectura es buena:
- lista blanca cerrada, con mecanismo por variable;
- calendario medido con vintages donde las hay, con supuestos documentados donde no;
- dos modos (vintage y latest_truncated), con un baseline por modo;
- tests de fuga serios.

No he encontrado ninguna fuga de información en el calendario de las variables principales. Los fallos son de **diseño
económico**: varias variables no miden lo que dice su mecanismo en toda la muestra, y faltan cuatro o cinco piezas
baratas que ya están en el warehouse. Sin ellas, el bloque de inflación y las capas ex post no se pueden nowcastear.

Hay **tres cambios que deberían hacerse antes de congelar la v0.2** y de preregistrar el arnés:
1. **`growth_rt` no es el análogo PIT de G**, y su histéresis no hace lo que se pidió en la Fase 1 (H1, H2).
2. **Variables cuyo mecanismo no existía antes de 1971-73** (cobre/oro, dólar) y niveles con deriva secular (TCU,
   Michigan) que enseñan al modelo "en qué década estamos" (H3, H4).
3. **Faltan los motores de la inflación subyacente** (servicios, salarios, holgura, expectativas antes de 1981). Sin
   ellos, el eje I, que es casi la mitad del problema, queda nowcasteado con energía y con su propio pasado (H5, H6).

**Periodo bloqueado.** No he mirado ninguna relación entre variables y etiqueta, ni rendimientos. Solo he calculado
estadísticos descriptivos de las propias variables (medias y desviaciones por década, frecuencia de flags, retardo
efectivo en meses según el linaje), siempre con fechas de decisión ≤ 2004-12. Basta anotarlo en `research/trial_log.md`
como "descriptivos de variables, sin etiqueta, ≤ 2004".

---

## Hallazgos priorizados

### H1 (alta). `growth_rt` usa una media expansiva, no la tendencia de 10 años de G
- **Qué hace el código.** `zexp` (`src/features/pit.py:102`) estandariza cada ritmo de 3 meses con la media y la
  desviación **expansivas desde 1950**.
- **Qué hace la etiqueta.** G compara el ritmo con una **mediana de 10 años** y escala con la MAD (`label_spec.md` §3).
- **Por qué importa.** La tendencia de la producción industrial pasó de ~4-5 %/año (1960s) a ~1 % (2000s) y a ~0 en
  la última década. La del empleo también cae, por oferta de trabajo. Una media expansiva que arrastra los años 60:
  - lee "crecimiento bajo" de forma crónica justo en el periodo bloqueado y en producción;
  - repite el error que ya señalé en la etiqueta (M1: inmigración frente a demanda).
- **Evidencia ≤ 2004, sin etiqueta.** Media de `growth_rt` por década: 1960s +0,12; 1970s −0,19; 1980s −0,08; 1990s
  −0,04; **2000-04 −0,29**. Media de `growth_rt_state` en 2000-04: **−0,50**. Media de `indpro_3m_ann`: 4,6 (1960s)
  frente a 1,2 (2000-04). El sesgo ya aparece antes del periodo bloqueado, y después solo puede crecer.
- **Propuesta (a priori, sin mirar la etiqueta).** Para cada entrada,
  `z = (g_t − mediana(g, t−119…t)) / (1,4826·MAD expansiva de g − tendencia)`,
  es decir, la versión **unilateral** de la G de la ficha, con un mínimo de 120 meses. Así G y su análogo PIT miden lo
  mismo, salvo el retardo y la ventana.

### H2 (alta). La histéresis ±0,15 está en otras unidades y apenas reduce la rotación
- La banda ±0,15 se propuso en la Fase 1 sobre una G de 3 meses **en unidades de G** (desviación frente a la tendencia,
  escalada por σ robusta). En esas unidades daba **0,43 cambios/año** (`2026-10-07_estratega_macro.md` §1).
- Aquí se aplica a una media de z expansivos de tasas de 3 meses sin suavizar (desviación típica 0,5-0,8 por década).
  Con esa escala, 0,15 equivale a ~0,2-0,3 σ.
- **Resultado medido ≤ 2004: `growth_rt_state` cambia 1,06 veces/año.** La rotación es la misma que la de la etiqueta
  dura (~1,3/año), así que no cumple su función.
- **Propuesta.**
  - Rehacer `growth_rt` como en H1.
  - Fijar la banda en unidades de su propia desviación, **±0,5 σ expansiva**, y exigir **2 meses de confirmación**
    para cambiar de estado (la Sahm ≥ 0,5 manda sin confirmación).
  - Fijarlo antes de ver la etiqueta y medir solo la rotación.

### H3 (alta). Variables sin mecanismo antes de 1971-73: rompen la regla 4 por la puerta de atrás
| variable | problema | propuesta |
|---|---|---|
| `copper_gold_6m` | El oro estuvo fijado a 35 $ hasta 1968 (pool de Londres) y con doble mercado hasta 1971-73. Antes de 1971 el cociente es **solo cobre**: el canal "refugio" no existía | Empezar en **1973-01**. Si se quiere una señal antes, crear una variable aparte, `copper_6m` |
| `usd_neer_yoy` | Bretton Woods: tipos fijos hasta 1971-08 (desviación típica de la tasa a/a 0,9 en los 60 frente a 4,5-9 después) | Empezar en **1973-03** (flotación generalizada) |
| `oil_yoy` | Precio administrado (Texas RRC) hasta 1973 (desviación típica 1,5 en los 60 frente a 15-31 después) | Mantenerla, porque el shock de 1973 es información. Anotar que antes de 1973 es casi constante y que el arnés no debe leer "petróleo plano = años 60" |

Una variable que es casi constante en una época y volátil en otra hace de indicador de época igual que un hueco. Es la
misma lógica que la regla 4.

### H4 (media-alta). Niveles con deriva secular que actúan como reloj
| variable | evidencia ≤ 2004 | propuesta |
|---|---|---|
| `tcu` (nivel) | media de 87,3 (1960s) → 82,8 → 79,7 → 82,1 → **77,4** (2000-04). La capacidad se revisa con cada referencia | `tcu_gap` = TCU − media de los 120 meses previos (PIT). Si no, quitarla: `indpro_3m_ann` ya recoge el ciclo industrial |
| `umcsent` (nivel) | Trimestral hasta 1977 (retardo efectivo de 2 a 4 meses: cambia el régimen de frecuencia). Michigan pasó a encuesta web en 2024, con un salto de nivel a la baja en el sentimiento y al alza en las expectativas de inflación (afecta al periodo bloqueado y a producción) | **Empezar en 1978-01** (como MICH, época E3). Anotar el corte de 2024 en el preregistro y, para la evaluación única, preregistrar también la sensibilidad con Δ12m |
| `core_cpi_*` antes de 1983 | El IPC incluía los intereses hipotecarios en vivienda hasta 1983 (equivalencia de alquiler desde 1983). En 1979-81 sobrestima la subyacente frente al PCE de la etiqueta | Es lo que se veía en t, así que es correcto como PIT. Documentarlo en `pit_base.md` §7 y no "arreglarlo" |

### H5 (alta). El bloque de inflación nowcastea energía, no la subyacente de la etiqueta
- **Qué exige I.** I<sub>t</sub> es el PCE subyacente de t−3 a t+3. Nowcastearla exige **prever 3 meses de
  subyacente**, y eso lo mueven los servicios, la vivienda y los salarios, que son persistentes.
- **Qué hay en la lista blanca:**
  - subyacente pasada (IPC 6m y 12m);
  - tres medidas sensibles a la energía (general, PPIACO, petróleo);
  - expectativas solo desde 1978-81;
  - dólar.
- **`infl_composite` pondera la energía con 3 de 4 entradas.** Además la expresa en z expansivos: con un umbral fijo de
  2,5 %, el mismo 3 % no significa lo mismo en 1965 que en 1995. Para el eje I, las unidades correctas son **puntos
  porcentuales**.
- **Propuesta:** dividir en dos compuestos.
  - `infl_core_pressure`, en pp: media de la subyacente 6m, los servicios sin energía 6m y los salarios a/a menos 1,5 pp
    de productividad, fijado a priori.
  - `infl_energy_pressure`, en z: petróleo, PPI y general − subyacente.
  - Con esto se cumple el punto 3 de la Fase 1 ("I compuesta… no I↓ con core > 2,5"): la subyacente manda en el nivel y
    la energía en la capa.

### H6 (alta). Faltan variables clave, ya disponibles en el warehouse y gratuitas
Las he comprobado todas en `catalog`: `pit_role = observed` y fuente viva. Las ordeno por valor y esfuerzo. Son pocas y
son las que faltan.

| # | variable propuesta | serie (desde) | transformación a priori | calendario | mecanismo | ≤ 2004: recesiones |
|---|---|---|---|---|---|---|
| A1 | `core_services_cpi_6m_ann` | `CUSR0000SASLE` (1967) | pct_ann k=6 | proxy CPIAUCSL | Servicios sin energía ≈ 60 % de la subyacente: vivienda, sanidad y transporte. Es la parte persistente que determina I en t+1…t+3 | 6 |
| A2 | `ahe_yoy` | `AHETPI` (1964) | pct_ann k=12 | proxy PAYEMS | Salarios → coste de los servicios (6-18 m); también mide la tensión del mercado laboral | 6 |
| A3 | `unrate_gap10y` | `UNRATE` (vintage) | UNRATE − mediana de los 120 meses previos | como UNRATE | Holgura PIT sin NROU (rechazada con razón). Curva de Phillips; separa recuperación de sobrecalentamiento dentro de G+ I+ | 9 |
| A4 | `spf_pgdp_4q` | `spf_med_pgdp_6/_2` (1968-T4) | 100·log(ratio), **mediana** (en la ASA-NBER había pocos encuestados) | como el SPF | Expectativas de inflación fechadas **antes de 1981**: cubren la gran inflación (la variable `spf_cpi_4q` solo tiene 3 recesiones ≤ 2004 y ninguna de los 70) | 6 |
| A5 | `spf_anxious` | `spf_anxious_index` (1969) | nivel | como el SPF | Probabilidad de caída del PIB según la encuesta: es un juicio fechado, no un modelo reestimado. Es el sustituto PIT legítimo de las probabilidades de recesión rechazadas | 6 |
| A6 | `fedpath_1y` | `GS1` − media mensual de `DFF` (1955) | diferencia | mercado, 1 día | Lo descontado por el mercado sobre la Fed a 12 meses (punto 4 de la Fase 1). Positivo = subidas descontadas. Empieza décadas antes que el 2y (1976) | 9 |
| A7 | `philly_prices_paid` | `PPCDFSA066MSFRBPHI` (1968) | nivel | como Filadelfia (mes en curso) | Es el **único dato de precios del propio mes t**. Adelanta el PPI y la inflación general | 6 |
| A8 | `headline_minus_core_6m` | derivada | `headline_cpi_6m_ann − core_cpi_6m_ann` | — | Análogo PIT exacto de la capa `energy_shock` (L-CAP-002). La logística no lo puede construir sola | 8 |
| A9 | `core_cpi_dir` | derivada | `core_cpi_6m_ann − core_cpi_6m_ann(t−6)` | — | Análogo PIT de la capa `infl_dir` (L-CAP-001) | 8 |

**Segunda línea** (solo si sobra presupuesto de grados de libertad):
- `CCSA`, peticiones continuas (1967): el empleo se frena por falta de contratación aunque no haya despidos.
- `TOTALSA`, ventas de vehículos (1976): demanda de duraderos sensible a tipos, publicada a 1-3 días.
- `HOUST` no aporta nada sobre `PERMIT`.

**Coherente con la regla de admisión que sigan fuera:**
- ventas minoristas, pedidos de duraderos y existencias: `RSAFS`, `DGORDER` y `NEWORDER` empiezan en 1992 (2
  recesiones ≤ 2004);
- precios de importación: `IR` empieza en 1982-09;
- ECI (2001), `TEMPHELPS` (1990) y `JTSJOL` (2000);
- encuestas regionales distintas de Filadelfia: empiezan en 1993-2004;
- ISM: no está en el warehouse y tiene licencia.

### H7 (media). Bear/bull steepening: mal definido y ruidoso
- **El nivel medio no atribuye el movimiento.** El mecanismo dice que lo mueve el tramo largo, pero el flag se decide
  con el nivel medio (10a + 3m)/2. Ejemplo: si el 10a sube 30 pb y el 3m baja 50 pb, la curva sube 80 pb y el nivel
  baja 10 pb, y el flag lo clasifica como "bull".
- **Umbral cero.** El 17-19 % de los meses tiene |Δcurva| o |Δnivel| < 10 pb (≤ 2004). El 47 % de los meses lleva algún
  flag.
- **Faltan los dos aplanamientos.** El **bear flattening**, la Fed subiendo con la curva aplanándose, es la señal
  clásica de final de ciclo. Con dos flags, los dos aplanamientos quedan en (0, 0) y son indistinguibles.
- **Propuesta:** una variable categórica `curve_regime_3m` con 4 estados más "sin cambio".
  - "Sin cambio" si |Δcurva| < **25 pb**.
  - Si no, el tramo dominante decide: steepening si Δcurva > 0 y flattening si < 0; bear si el tramo que más se mueve
    sube y bull si baja (bear steepening = Δ10a > 0 dominante; bear flattening = Δ3m > 0 dominante).
  - Mantener `curve_d3m` y `level_d3m` continuas para los árboles.

### H8 (media). Módulo de liquidez: más útil para la Etapa 2 que para el nowcast
- `net_liq_yoy` y `global_cb_usd_yoy` están bien construidas: las unidades cuadran (millones de USD) y el empalme de la
  TGA está anotado.
- Su mecanismo opera sobre **precios de activos**, no sobre G e I del mes. Además, en 2003-2008 el balance de la Fed
  apenas varía.
- **Propuesta:** preregistrarlas como variables de la **Etapa 2** (preferencias de activos) más que del módulo
  adicional del nowcast. Si se quedan en el nowcast, que sea como módulo, como está propuesto.

### H9 (baja). Otras transformaciones
- **`permit_yoy`:** los permisos mensuales tienen mucho ruido (±10 % m/m). Mejor la tasa a/a de la **media de 3
  meses**, como en las peticiones de paro.
- **`vix`:** tiene **2 recesiones ≤ 2004** (1990 y 2001), aunque cuente 4 en total. Con la regla 2 aplicada al periodo
  de investigación, no llega. Tratarla como E4 sabiendo que la investigación ≤ 2004 no la puede validar, o pasarla al
  módulo.
- **Bien elegidas y transformadas:**
  - `payems_3m_ann`, `unrate_sahm` (vintage), `indpro_3m_ann`, `claims_4w_yoy`;
  - `awhman_d3`, Filadelfia actividad y pedidos;
  - `gdp_qoq_ann`, `spf_rgdp_4q`;
  - las dos subyacentes del IPC, `real_ff`, `ff_d12m`, `baa_spread`, `gz_spread`, `eq_ret_6m`, `m2_real_yoy`.
- **Signos:** todos tienen sentido. La única ambigüedad es `ff_d12m`, que está bien anotada.
- **Condicionales** (`cfnai_ma3`, `core_pce_6m_ann`, `ebp`, `nfci`): de acuerdo con excluirlas del modelo principal
  ≤ 2004. `gz_spread` es la versión limpia de la EBP: precios de mercado agregados y sin regresión de toda la muestra.

### H10 (rechazadas). Bien rechazadas. Una vuelve con otra definición
- **Bien rechazadas, todas:** USREC, NROU/GDPPOT, las probabilidades de la EBP y de la NY Fed, la prima ACM, Cleveland,
  TEDRATE, TWEXB, la base monetaria, futuros de energía, MPT, la estructura del VIX, STLFSI, SAHMREALTIME y las capas
  L-CAP.
- **Vuelven con otra definición:**
  - **"Probabilidad de recesión"**, como encuesta fechada (`spf_anxious`, A5), en lugar de un modelo reestimado;
  - **"Brecha de paro"**, sin NROU (`unrate_gap10y`, A3);
  - **"Prima por plazo / expectativas de tipos"**, sin modelo: `fedpath_1y` (A6). Para la v0.3 hay una versión de
    encuesta: el 10a menos la media de las previsiones SPF de letras/bonos.

---

## Calendario (punto 4)

**Regla práctica.** Con la decisión en el último día hábil del mes, lo que cuenta en una serie mensual es si su retardo
cruza **~28-31 días**: si lo cruza, el modelo ve t−2 en vez de t−1. Que el retardo sea de 15 o de 25 días da igual. He
medido el retardo efectivo en meses con el linaje (vintage, ≤ 2004):

| variable | 1950-71 | 1972-89 | 1990-2004 | lectura |
|---|---|---|---|---|
| `payems_3m_ann` | t−1 (100 %) | t−1 | t−1 | correcto (primer viernes) |
| `indpro_3m_ann` | t−1 (97 %) | t−1 | t−1 | correcto |
| `core/headline_cpi_6m` | **t−2 (100 %)** | t−1 (97 %) | t−1 (99 %) | **conservador antes de 1972**: el IPC salía hacia la 4.ª semana, así que en la realidad se veía t−1. No hay fuga, pero el retardo cambia en 1972 |
| `ppi_yoy` | t−1 | t−1 | t−1 | ok |
| `w875rx1_3m_ann` | t−2 | t−2 | t−2 (79 %) / t−1 (21 %) | cambio en 2000 al pasar a las fechas de PCEPI. Es aceptable, pero también cambia el retardo |
| `cmrmtspl_3m_ann` | t−3 | t−3 | t−3 | el retardo de 70 días solo está medido desde 2013 |
| `usd_neer_yoy` | t−1 (74 %) / t−2 (26 %) | igual | igual | **artefacto**: 30 días frente a la longitud del mes. Es un precio de mercado (calculable con H.10): debería ser t−1 siempre |
| `umcsent`, `mich_infl_exp` | t−2…t−4 (trimestral) | **t−2** | **t−2** | **demasiado conservador**: ver C1 |
| `spf_cpi_4q` | — | t−1…t−4 | t−1…t−3 | correcto para una encuesta trimestral; ver C2 antes de 1990 |
| `philly_activity` | — | **t (mes en curso)** | t | supuesto: ver C3 |

**Propuestas:**
- **C1 (media). Michigan.** El retardo de 35 días es el de la licencia de FRED, no el de la publicación: la final del
  mes t sale a finales de t. Así se pierde la única virtud de la encuesta, la rapidez.
  - Descargar de la propia Universidad de Michigan, que es gratuita.
  - Retardo conservador desde 1978: **20 días**, que da t−1 seguro.
  - Antes de 1978 (trimestral, con informes publicados semanas después), **90 días** o, mejor, empezar en 1978 (H4).
  - Si se mantiene FRED, documentar que se renuncia a un mes de información.
- **C2 (media). SPF antes de 1990-T2 (ASA-NBER).** Las encuestas se hacían a mitad del trimestre y los resultados se
  publicaban en el NBER Reporter / Amstat News con semanas o meses de retraso. **Inicio del trimestre + 60 días no es
  claramente conservador.** Propongo **+90 días** antes de 1990-T3, es decir, disponible desde el trimestre siguiente.
  Cuesta poco: las expectativas son persistentes. Afecta a `spf_rgdp_4q`, `spf_cpi_4q` y a las nuevas `spf_pgdp_4q` y
  `spf_anxious`.
- **C3 (media). Filadelfia 1968-90.** Es la única variable del mes en curso y por eso **es la que más puede fugar** si
  el supuesto falla. Creo que el tercer jueves es correcto desde el principio, pero no está verificado.
  - Hasta verificarlo con el archivo de la Fed de Filadelfia, preregistrar una **sensibilidad con t−1** antes de 1990.
  - Lo mismo aplica a la nueva `philly_prices_paid`.
  - Los factores estacionales se reestiman cada año (latest_truncated): en un índice de difusión es un efecto menor.
- **C4 (baja). CMRMTSPL antes de 2013.** Los 70 días están medidos solo con vintages de 2013 en adelante. Antes, las
  ventas reales de manufactura y comercio salían con unos 2 meses o más. Propongo **90 días antes de 2000**. El impacto
  es pequeño, porque `growth_rt` solo necesita 2 de las 4 entradas.
- **C5 (baja). BIS NEER:** pasar a **20 días** (la serie es un agregado de tipos de mercado), para que el retardo no
  dependa de si el mes tiene 30 o 31 días.
- **C6 (info). Retardos que cambian con la época** (IPC en 1972, renta personal en 2000): no son fugas, pero el arnés
  debería **registrar el retardo efectivo por época** (ya está en el linaje) y repasarlo junto a la regla 4.
- **Bien calibrados:**
  - empleo (16 días, máximo medido antes de 1980);
  - PIB (60 días antes de 1965; RTDSM a 46 días: conservador, porque el avance de los 70-80 salía a ~3-4 semanas);
  - PCE / renta personal (35);
  - peticiones de paro (6);
  - mercados (1 día);
  - suelo del día siguiente al fin de periodo;
  - monotonía.
  - PERMIT a 20 días es irrelevante para la decisión a fin de mes, porque queda lejos del umbral.

---

## Pendientes de la Fase 1 (punto 5)

| pendiente | estado en la v0.1 | veredicto |
|---|---|---|
| Histéresis de G | `growth_rt_state` | ❌ en otras unidades y sin efecto (1,06 cambios/año). Rehacer con H1 y H2 |
| Inflación compuesta | `infl_composite` | ⚠️ pondera la energía y está en z. Dividir en núcleo (pp) y energía (H5) |
| Bear/bull steepening | 2 flags | ⚠️ atribución por nivel medio, umbral 0 y sin aplanamientos (H7) |
| Liquidez neta diaria | `net_liq_yoy` | ✅ bien construida; mejor en la Etapa 2 (H8) |
| Liquidez global | `global_cb_usd_yoy` | ✅ unidades correctas; módulo / Etapa 2 |
| Eje de sorpresa (punto 4 de la Fase 1) | no está | añadir `fedpath_1y` (A6) y, en la v0.3, la sorpresa de inflación (abajo) |

## Coherencia con las capas ex post y con la Etapa 2 (punto 6)

| capa preregistrada | análogo PIT hoy | con las propuestas |
|---|---|---|
| L-CAP-001 dirección de la inflación | implícito (subyacente 6m frente a 12m) | `core_cpi_dir` (A9), `philly_prices_paid` (A7), `core_services_cpi_6m_ann` (A1) |
| L-CAP-002 shock energético | `oil_yoy`, `headline_cpi_6m_ann` | `headline_minus_core_6m` (A8): es la definición de la capa sobre datos PIT; `oil_yoy > 40` ya existe |
| L-CAP-003 holgura | **ninguno** (solo la Sahm, que mide deterioro, no nivel) | `unrate_gap10y` (A3), `ahe_yoy` (A2), `tcu_gap` (H4) |
| Recesión × cuadrante | Sahm, curva, peticiones de paro, crédito | + `spf_anxious` (A5) |
| Eje I frente a lo esperado (candidata v2.0) | Michigan (1978), SPF IPC (1981) | + `spf_pgdp_4q` (1968). Para la v0.3: `infl_surprise_12m` = subyacente a/a conocida en t − expectativa SPF (deflactor del PIB hasta 1981, IPC después) fechada 4 trimestres antes. Es PIT por construcción |

Sin A1-A3 y A8-A9, la Etapa 2 no podría condicionar en tiempo real a "dirección de la inflación" ni a "holgura": solo
podría hacerlo ex post. Es la razón principal del "con cambios".

## Resumen de propuestas (orden de ejecución)
1. **Redefinir** `growth_rt` (tendencia unilateral de 10 años, MAD) y `growth_rt_state` (±0,5 σ, 2 meses de
   confirmación).
2. **Añadir** A1-A9 (9 variables; 7 son series ya en el warehouse con calendario por proxy y 2 son derivadas).
3. **Acotar o redefinir:**
   - `copper_gold_6m` y `usd_neer_yoy` desde 1973;
   - `tcu` → `tcu_gap`;
   - `umcsent` desde 1978 y con nueva fuente;
   - `infl_composite` → núcleo (pp) + energía (z);
   - bear/bull → `curve_regime_3m` con 25 pb y atribución por tramo;
   - `permit_yoy` sobre la media de 3 meses.
4. **Calendario:**
   - Michigan a 20 días con la fuente directa;
   - SPF a +90 días antes de 1990-T3;
   - sensibilidad de Filadelfia con t−1 antes de 1990;
   - CMRMTSPL a 90 días antes de 2000;
   - BIS a 20 días.
5. **Documentar** en `pit_base.md` §7:
   - el IPC con intereses hipotecarios antes de 1983;
   - el precio del petróleo administrado antes de 1973;
   - el corte de la encuesta web de Michigan en 2024;
   - los retardos que cambian con la época.
6. Todo lo anterior se fija **a priori**, sin mirar la etiqueta: **versión nueva de la lista blanca (v0.2)** antes del
   preregistro del arnés.

No he modificado código ni datos.
