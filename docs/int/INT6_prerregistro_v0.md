---
documento: P-DEV-INT6 — oro, dinero, crédito y relaciones entre países (prerregistro interno)
version: 0.1 BORRADOR (2026-10-29), sin congelar
estado: BORRADOR para el usuario. No se ha cruzado ningún indicador con ningún resultado. Solo recuentos, varianzas incondicionales y disponibilidad.
depende_de: INVENTARIO_relaciones.md (qué falta), INT-3/3b (método de los paneles), INT-4 (objetivo T1, listón B1, evaluación), INT-4-ML (MDE sobre el logit), Validadores 26-29 oct
potencia: scripts/int6_potencia.py (v1 4e628a1 → salida 1.ª; v2 5e19c60, árbol limpio, 2026-10-29T14:43:50Z) → research/int/int6_potencia.json (21024f5)
---

# P-DEV-INT6 (borrador v0.1): oro, dinero, crédito y relaciones entre países

## 0. Qué es y qué no es
- **Qué es.** Rellena los huecos de valor alto del inventario (`docs/int/INVENTARIO_relaciones.md` §4) que se pueden
  contestar **sin gastar el periodo bloqueado**: solo JST ≤ 2004 y EE. UU. ≤ 2004.
- **Preguntas.** Se consideran 8, una por mecanismo. **Quedan 6 confirmatorias**, elegidas por valor y potencia; dos se
  descartan por falta de potencia y pasan a descriptivas o informativas.
- **No es una regla de inversión.** Las preguntas de tipo A (indicador → rentabilidad) miden si algo anticipa el
  rendimiento del año siguiente; las de tipo P (indicador → giro), si anticipa un giro del ciclo. Nada de esto se
  conecta al reporte ni a la cartera sin una decisión registrada.
- **Gobierno: el de siempre.**
  1. El usuario aprueba y el texto se congela con hora.
  2. Se commitea un script de corrida con puerta (árbol limpio, commit y hora en la salida).
  3. **Una sola corrida.**
  4. Validador independiente.

## 1. Las 8 preguntas y su destino

| id | pregunta | tipo | signo | muestra | MDE (1 contraste / Holm-6) | ¿alcanzable? | destino |
|---|---|---|---|---|---|---|---|
| **G1** | ¿el oro protege en recesiones y crisis? (desde 1972 frente a toda la historia) | R | + | 14 países; 1972-2004 / 1877-2004 | **29,9 / 37,1 pp/año** (1972-2004); 12,3 / 15,3 (1877-2004, pero mecánico) | **no** | **descartada → descriptiva** |
| **G2** | ¿el oro se mueve al revés que el tipo real? | relación contemporánea | − | EE. UU., mensual, 1973-2004 (384 meses) | **r = 0,155 / 0,192** | justo | **confirmatoria** |
| **M1** | ¿más dinero real en t → más bolsa real en t + 1? | A | + | 14 países, 1871-2004 (1.610 filas) | **2,4 / 3,0 pp por 1 dt** (central × 1,3) | justo | **confirmatoria** |
| **M2** | ¿más dinero real en t → más bonos reales en t + 1? | A | + | ídem (1.676 filas) | **1,3 / 1,6 pp por 1 dt** | probable | **confirmatoria** |
| **M3** | ¿el dinero anticipa la entrada en recesión? (añadido a INT-4) | P | − | 14 países, 1871-2004 sin guerras | frente a B1 0,10 / 0,12; sobre el logit 0,044-0,061 / 0,054-0,076 | **no** (lo esperable es +0,01-0,02) | **descartada → informativa** |
| **K1** | ¿un auge de crédito (Δ5 crédito/PIB) anticipa una crisis bancaria? | P | + | 14 países, 1871-2004 sin guerras; 49 crisis en 27 años | **ΔAUC 0,16 / 0,20** frente a B1 | justo (≈ 50 %) | **confirmatoria** |
| **K2** | ¿el estrés de crédito del centro financiero (Δ del diferencial corporativo) anticipa la recesión de los 14 países? | P | + | 14 países, 1871-2004 sin guerras; 222 entradas en 84 años | **0,10 / 0,12** frente a B1 | justo | **confirmatoria** |
| **X1** | **Contagio:** si en t cae el PIB de muchos de los otros países, ¿entra el país en recesión en t + 1? | P | + | ídem | **0,10 / 0,12** frente a B1 | justo | **confirmatoria** |

**Notas a la tabla:**
- **Unidades del MDE:** pp de rentabilidad real al año (G1, M1, M2); correlación (G2); mejora de AUC (M3, K1, K2, X1).
- **Cómo leer "justo".** El MDE está en el rango de los efectos de la literatura, así que la potencia es de ≈ 40-80 %. Lo
  más probable en varias es "no establecido", aunque el efecto exista.
- **Familia de Holm:** las 6 confirmatorias forman una sola familia, Holm-6 (decisión 2).

## 2. Potencia (solo recuentos y varianzas; `research/int/int6_potencia.json`)

### 2.1 Por qué se descarta G1 (oro como refugio)
- **Panel en moneda local, 1972-2004:**
  - 462 país-años, de ellos 61 en recesión, 15 en recesión financiera y 20 en crisis (año de inicio y el siguiente).
  - El oro tiene una dt de 24,8 %. Su correlación entre países es de **0,93**: con precio libre es casi una sola serie
    en dólares.
  - Resultado: **61 país-años en recesión valen ≈ 7 observaciones efectivas.** MDE de 29,9 pp (recesión), 36,6
    (financiera) y 31,4 (crisis).
- **Serie mundial en USD, 1972-2004** (33 años) frente a la cuota de países en recesión: MDE de 14,3 pp por 1 dt de la
  cuota, y de 53 pp con la mayoría.
- **Toda la historia, 1877-2004:** MDE de 12,3 pp. Pero hasta 1971 el oro tenía precio fijo y lo que se mide es la
  devaluación de cada moneda, no el oro (atlas, aviso 4).
- **Refugio a corto plazo** (EE. UU., 1973-2004): en los 24 meses en que la bolsa cayó ≥ 5 % (14 meses con ≥ 8 %), el MDE
  es de **3,3 / 4,1 pp en el mes** (4,3 / 5,4 con ≥ 8 %). Un efecto de refugio plausible es de +1-2 pp: no se alcanza.
- **Conclusión:** con datos ≤ 2004 **no se puede contestar** si el oro protege en recesiones. Se publica como descriptiva
  (§4.1), con su IC, sin veredicto.
  - Lo único que podría contestarlo con más potencia es el periodo **2005-2025 (bloqueado)**, que incluye 2008 y 2020.
  - Es candidato a la evaluación única **si** el usuario decide gastarlo.

### 2.2 Por qué se descarta M3 (dinero → recesión)
- **Frente a B1:** 1.238 filas, 208 entradas en 83 años; MDE de 0,10 / 0,12.
- **Sobre el logit de INT-4** (AUC estratificada 0,732, modelos anidados, r = 0,8-0,95): 1.037 filas, 159 entradas; MDE de
  0,031-0,061 con un contraste y 0,039-0,076 con Holm-6.
- **Lo esperable** de un indicador suelto con mecanismo débil es +0,01-0,02, como C2 (+0,018) y C5 (+0,012) en INT-4.
  **No hay potencia.** Pasa a informativa (§4.2).

### 2.3 Las confirmatorias

| id | filas / eventos (años distintos) | ICC / efecto de diseño | MDE 1 / Holm-6 | 1950-2004 | MDE sobre el logit de INT-4 (informativo; r 0,8 / 0,9 / 0,95, Holm-6) | plausible (literatura) |
|---|---|---|---|---|---|---|
| G2 | 384 meses; AR(1) 0,28 / 0,28; n efectivo 328 | — | r 0,155 / 0,192 (pendiente ≈ 1,1 / 1,4 % de oro por 1 pp de Δ tipo real) | 1980-2004: 0,167 / 0,207 | — | r entre −0,1 y −0,3 en variaciones mensuales (Erb-Harvey 2013, con TIPS ≥ 1997) |
| M1 | 1.610; ρ dinero 0,10, ρ bolsa 0,30; n efectivo 1.160 | m* 12,4 | 1,8 / 2,3 pp por dt (× 1,3: 2,4 / 3,0); prudente 3,4 / 4,2 | 3,3 / 4,1 | — | 1-3 pp por dt (Baks-Kramer 1999; liquidez global) |
| M2 | 1.676; ρ bonos 0,45; n efectivo 998 | m* 12,7 | 1,0 / 1,2 (× 1,3: 1,3 / 1,6); prudente 2,0 / 2,5 | 1,4 / 1,7 | — | ≈ 1 pp por dt |
| K1 | 1.146 / 49 (27) | 0,19 / 2,9 | 0,16 / 0,20 (A0 = 0,5-0,6) | **10 crisis en 8 años: inalcanzable (0,27-0,34)** | — | ΔAUC ≈ 0,15-0,20 (Schularick-Taylor 2012: AUC ≈ 0,67-0,72 frente a 0,5) |
| K2 | 1.332 / 222 (84) con el empalme R. U. → EE. UU.; solo EE. UU. desde 1919: 906 / 114 (45) | 0,15 / 2,7 | 0,10 / 0,12; solo EE. UU.: 0,13 / 0,16 | 0,17 / 0,21 | 0,076 / 0,054 / 0,039 | 0,05-0,10 (en INT-4, C1 +0,094; C4 +0,126) |
| X1 | 1.332 / 222 (84) | 0,15 / 2,7 | 0,10 / 0,12 | 0,17 / 0,21 | 0,076 / 0,054 / 0,039 | 0,05-0,10 (S4 en la salida: +0,087, n. s.) |

**Lectura honesta:**
- **M2** (dinero → bonos) es la que tiene más potencia relativa.
- **K2 y X1** están en el límite: un indicador de la fuerza de la curva (C1) o de la difusión de curvas (C4) saldría; uno
  más débil, no.
- **K1** es la más valiosa y la más contaminada. Con 49 crisis su potencia es de ≈ 50 % para el efecto de la
  literatura, y en 1950-2004 no hay potencia ninguna (10 crisis).
- **G2** detecta |r| ≥ 0,16-0,19. Con el tipo real ex post (ruidoso) es probable que el efecto real sea menor.
- **El efecto incremental sobre el termómetro** (K2 y X1 añadidos al logit de INT-4) exige ≥ 0,04-0,08: queda como
  **informativo**.
- **Datos de EE. UU. solo:** con el diferencial propio de EE. UU., 12 entradas, MDE de 0,25-0,30. Con el EBP (1973-2004),
  4 entradas: inalcanzable. Los dos quedan **solo descriptivos**.

## 3. Definición de cada confirmatoria (fijada antes de mirar)

**Reglas comunes:**
- **Núcleo:** 14 países (BEL, DEU, DNK, ESP, FIN, FRA, GBR, ITA, JPN, NLD, NOR, PRT, SWE, USA).
- **Países de prueba** (AUS, CHE; CAN e IRL sin bolsa): solo al final, con el modelo congelado; informativos.
- **Corte:** `src/intl/data.load_dev`, todo ≤ 2004-12. **Nada de JST ≥ 2005.**
- **"As of":** el dato JST del año t se conoce el 30 de abril de t + 1 (120 días, `src/intl/lags.py`); la OCDE con sus
  retrasos; el mercado, al cierre del mes.
- **Hiperinflación:** fuera los país-años con inflación > 50 %, en t o en t + 1 (regla de INT-3b).
- **Guerras:** en los objetivos de giro (K1, K2, X1), fuera las filas cuya ventana t … t + h toca 1914-1918 o 1939-1945
  (como en INT-4). En M1 y M2, todos los años, con una sensibilidad sin guerras.

### G2 — oro y tipo real (EE. UU., mensual, 1973-01 a 2004-12)
- **Hipótesis:** cuando sube el tipo real, el oro baja (signo −). Es el coste de oportunidad de un activo sin
  rendimiento (Barsky-Summers 1988; Erb-Harvey 2013).
- **Datos:**
  - y_m = Δlog `gold_wb_usd_m`: media mensual del Banco Mundial, en USD nominales; desde 1973, cuando el precio ya era
    libre, como `copper_gold_6m` en la base PIT.
  - x_m = Δ(`oecd_ir3m_usa`/100 − inflación interanual del IPC de EE. UU. del mes m − 1), con `oecd_cpi_usa_idx`.
- **"As of":** es una relación **contemporánea**, no una predicción. Usa la inflación del mes anterior, que es la que se
  conoce. Se declara así.
- **Contraste:** MCO y = a + b·x, errores Newey-West (6 retardos); b se publica estandarizada (es la correlación) y en %
  por pp.
- **Placebo:** x desplazada en círculo k = 12 … T − 12 meses (todas las k); φ = máx(1, dt de las t placebo); p_cal como
  en INT-3b.
- **Establecido si:**
  1. b < 0;
  2. p_cal ≤ el umbral de Holm-6;
  3. |t| > percentil 95 de las |t| placebo;
  4. mismo signo en 1973-1988 y en 1989-2004;
  5. mismo signo en anual (diciembre a diciembre, 32 años; solo el signo).
- **Sensibilidades:** tipo real largo (`GS10` − inflación); oro en EUR (BIS/BCE); sin 1979-1980.

### M1 / M2 — dinero real → bolsa y bonos del año siguiente (panel JST)
- **Hipótesis:**
  - M1 (bolsa): + (liquidez y recomposición de carteras; Baks-Kramer 1999).
  - M2 (bonos): +, porque el dinero abundante acompaña a tipos que bajan.
  - **Hipótesis rival declarada:** el canal de la inflación (más dinero → más inflación → bonos −). Si sale negativo,
    es "no establecido" con el signo contrario, no un descubrimiento.
- **Datos:**
  - x_it = Δlog `jst_*_money` − Δlog `jst_*_cpi` en t (dinero amplio real; BEL solo desde 1979).
  - Se winsoriza en los percentiles 1 y 99 del conjunto. La regla mira **solo el indicador** (reformas monetarias,
    guerras).
  - y = `eq_tr_real` (M1) y `bond_tr_real` (M2) de t + 1.
- **"As of":** x_t se conoce el 30 de abril de t + 1; la rentabilidad de t + 1 empieza en enero. Hay ≈ 4 meses de
  solape, el mismo que en el atlas §8 (declarado). La versión estricta, x_t → y_{t+2}, es informativa.
- **Contraste:**
  - y_{i,t+1} = α_i + b·z_it + e, con z = x estandarizada (dt del conjunto); b en pp por 1 dt.
  - Errores Driscoll-Kraay por año (`src/intl/int3.driscoll_kraay`).
  - Placebo: x desplazada en círculo k = 6 … T − 6 años, la misma k en todos los países; φ y p_cal como en INT-3b.
- **Establecido si** (INT-3b §5.1, más un criterio):
  1. signo +;
  2. p_cal ≤ el umbral de Holm-6;
  3. |t| > p95 del placebo;
  4. mismo signo en 1950-2004;
  5. mismo signo en ≥ 2/3 de los países sin encoger y en DerSimonian-Laird sin la media de cada año;
  6. **mismo signo con efectos de año**: la parte propia de cada país, no la época. Lección del atlas §8 (los años 70).
- **Sensibilidades:** sin guerras; dinero nominal menos el PIB real ("exceso de dinero"); dinero estrecho (`narrowm`);
  t + 2; letras reales (`bill_rate_real`, informativa).

### K1 — auge de crédito → crisis bancaria
- **Hipótesis:** un aumento fuerte del crédito bancario sobre el PIB en los 5 años anteriores eleva la probabilidad de
  una crisis bancaria al año siguiente (signo +; Minsky; Schularick-Taylor 2012).
- **Objetivo:** y = 1 si `crisisjst` marca el **inicio** de una crisis en t + 1. Es una clasificación ex post: solo vale
  como objetivo, nunca como predictor (INT-0).
- **Filas en riesgo:** sin un inicio de crisis en t − 4 … t (después de una crisis el crédito cae por pura mecánica).
- **Indicador:** x_t = Δ5 (`tloans`/`gdp`) en t, en pp del PIB, conocido el 30 de abril de t + 1. JST está revisado: las
  fechas son honestas, los niveles no.
- **Modelo:** logit agrupado con **B1 = log(1 + años desde el último inicio de crisis)** (censurado al inicio de la
  muestra) + x.
  - Evaluación: dejar un país fuera (14 pliegues).
  - **Métrica: AUC estratificada por país.** Es la lección del listón de INT-4.
  - IC por bootstrap por bloques de año (2.000 réplicas).
  - Placebo: x desplazada en círculo, k ≥ 6, todas las k, misma k en todos los países; p con la z calibrada.
- **Establecido si** (INT-4 §4, con (iv) adaptado):
  1. el IC de ΔAUC estratificada excluye el 0 tras Holm-6;
  2. la z del placebo pasa Holm-6;
  3. Δlog-loss < 0;
  4. **ΔAUC > 0 en 1871-1913 y en 1919-2004 por separado.** En 1950-2004 solo hay 10 crisis: ese periodo es solo
     informativo;
  5. pendiente de calibración en [0,5; 1,5].
- **Sensibilidades:** h = 2; cronología `crisisjst_old`; crédito en log en lugar de cociente; con los 3 años previos de
  exclusión en lugar de 5.

### K2 — estrés de crédito del centro financiero → entrada en recesión
- **Hipótesis:** si el diferencial corporativo del centro financiero se abre durante el año t, la probabilidad de que cada
  país entre en recesión en t + 1 sube (signo +). Mecanismos:
  - acelerador financiero y oferta de crédito (Bernanke-Gertler 1989; Gilchrist-Zakrajšek 2012);
  - ciclo financiero global dictado por el centro (Rey 2013).
- **Indicador común:**
  - x_t = diferencial de diciembre de t menos el de diciembre de t − 1, en pp.
  - Diferencial del R. U. (`boe_uk_corp_bond_spread_m`, BoE, 1854-) para t ≤ 1918; Moody's Baa − Aaa de EE. UU. (`BAA`
    − `AAA`, FRED, 1919-) para t ≥ 1919.
  - **El Δ se calcula dentro de cada serie:** no se empalman niveles.
  - Se usa la **variación** y no el nivel por la lección de la Fase 3: en EE. UU. el nivel alto marcaba el rebote,
    no la caída (`baa_gap10y` al revés en el 100 % de los cortes; contaminación declarada).
- **Requiere** añadir `boe_uk_corp_bond_spread_m` a las familias permitidas de `src/intl/data.py` (decisión 4).
- **Objetivo y filas:** T1 de INT-4 (entrada en recesión a h = 1; 1871-2004 sin guerras; filas fuera de recesión).
- **Modelo:** B1 de INT-4 + x. Misma evaluación que K1.
  - Al ser una variable **común**, dejar un país fuera no la valida (como P4 en INT-4): su evidencia descansa en la
    evaluación temporal (declarado).
- **Establecido si:** criterios (i)-(v) de INT-4, con (iv) = ΔAUC temporal 1950-2004 > 0.
- **Sensibilidades:**
  - solo EE. UU. 1919-2004; R. U. en todos los años;
  - nivel frente a la mediana de 10 años;
  - **sobre el logit de INT-4** (informativo, MDE 0,04-0,08);
  - EE. UU. con su propio diferencial (descriptivo, 12 entradas).
  - **EBP:** solo descriptivo (4 entradas; no es "as of").

### X1 — contagio entre países
- **Hipótesis:** cuantos más de los otros países del núcleo tienen el PIB cayendo en t, más probable es que el país entre
  en recesión en t + 1 (signo +). Comercio, banca y choques comunes que llegan con retraso (Burns-Mitchell;
  Kose-Otrok-Whiteman 2003).
- **Indicador:** x_it = % de los otros 13 países con Δlog `rgdpmad` < 0 en t; exige ≥ 5 con dato. Se conoce el 30 de
  abril de t + 1.
- **Objetivo, filas, modelo y criterio:** como K2 (T1, B1 + x, criterios (i)-(v)).
  - Este sí varía por país: dejar un país fuera vale.
- **Sensibilidades:**
  - "EE. UU. con el PIB cayendo en t" para los otros 13 (¿la locomotora?);
  - cuota ponderada por PIB;
  - **sobre el logit de INT-4**, que ya tiene C4, la difusión de curvas (informativo);
  - 1950-2004.

## 4. Descriptivas e informativas (se publican siempre; sin Holm y sin "establecido")

### 4.1 G1, oro como refugio
- Oro real en moneda local en los años de recesión, de recesión financiera y de crisis, frente al resto, en tres tramos:
  1972-2004, 1877-1971 y 1877-2004. Con el efecto, el IC de Driscoll-Kraay y el MDE al lado.
- Oro real en USD frente a la cuota mundial de recesión.
- Oro en los meses con caída de la bolsa de EE. UU. ≥ 5 % y ≥ 8 % (1973-2004).
- **Frase obligatoria en el resultado:** "con datos ≤ 2004 esto no puede distinguir un refugio de +10-20 pp de cero".

### 4.2 M3, dinero → recesión
Añadido a B1 y sobre el logit de INT-4, con la misma evaluación. Sin veredicto.

### 4.3 Otras
- La parte de cada país que es común (ICC del crecimiento y de la recesión por décadas), solo para describir.

## 5. Multiplicidad
- **Una familia, Holm-6:** G2, M1, M2, K1, K2 y X1 (recomendado; decisión 2).
- Alternativa: familias por mecanismo (oro 1, dinero 2, crédito 2, países 1). Cada MDE bajaría ≈ 15-20 %, a costa de
  controlar peor los falsos positivos de un programa que, por diseño, abre muchos frentes a la vez.
- Holm se aplica sobre los p calibrados con el placebo (p_cal, o la z placebo en las AUC), como en INT-3b e INT-4-ML. El
  p por rangos se publica aparte, sin Holm (tiene suelo).

## 6. Contaminación (declarada)

| id | nivel | por qué |
|---|---|---|
| K1 | **alta** | Schularick-Taylor 2012 y JST 2013 usaron **este mismo panel**: es una réplica con nuestro método ("as of", dejar un país fuera, placebo), no un descubrimiento. Sabemos además que en INT-4 el Δ5 crédito/PIB no anticipó la recesión (+0,018) |
| K2 | media-alta | GZ 2012 y 2008 son conocidos. Elegir el Δ en lugar del nivel viene de un resultado nuestro (Fase 3, M1 v2) |
| X1 | media | C4 (difusión de curvas) establecido; S4 (difusión de caídas) para la salida, +0,087 n. s. Hemos visto ambos |
| M1 / M2 | media | P1 (dinero) no anticipó la inflación en INT-4; el dinero nunca se ha cruzado con rentabilidades |
| G2 | media | la relación oro-tipo real de 2005-2020 (TIPS) es famosa, pero la muestra de aquí acaba en 2004 |

**Lo que ha visto el agente que redacta:**
- recuentos de eventos y estados;
- dt, AR(1) y correlación entre países de cada serie **por separado**;
- disponibilidad de los datos.

Ningún indicador cruzado con ningún resultado.

## 7. Expectativa honesta (antes de correr)
- **M2** es la más probable, si el canal de la liquidez domina al de la inflación; el signo es dudoso.
- **M1:** probable en signo, justa en potencia.
- **K1:** el signo es muy probable (réplica). Que salga "establecido" es dudoso: con 49 crisis la potencia es de ≈ 50 %, y
  el criterio de las dos mitades es exigente.
- **K2 y X1:** dudosas. La difusión de curvas (C4) ya capta buena parte del contagio. El diferencial puede funcionar mejor
  en el siglo XIX (Londres) que después.
- **G2:** dudosa con el tipo real ex post mensual (ruido de la inflación).
- **G1:** sin respuesta posible con ≤ 2004.
- "No establecido" no es "no existe".

## 8. Fuera de INT-6 (anotado para después)
- **Valoración (D/P de JST, CAPE de Shiller) → rentabilidad a 1-5 años.** Es el gran hueco del inventario y tiene mucha
  potencia en el panel, pero merece su propio prerregistro (horizontes solapados, contaminación muy alta). Candidata a
  INT-7.
- **Volatilidad realizada → caídas fuertes; dólar → oro y materias primas; crédito de hogares frente a empresas;
  apalancamiento bancario:** valor medio, en lista.
- **Confirmación en el bloqueado (2005-2020)** de lo que salga aquí y de G1: solo una vez y por decisión del usuario. Si
  se decide, primero su potencia.

## 9. Decisiones del usuario (antes de congelar)
1. **Las 6 confirmatorias** (G2, M1, M2, K1, K2, X1), con **G1 y M3 descartadas** por falta de potencia (G1 pasa a
   descriptiva, M3 a informativa). *Recomendado: sí.* Lo que más le interesa del oro no se puede contestar con ≤ 2004, y
   es mejor decirlo que forzarlo.
2. **Multiplicidad:** una sola familia Holm-6 (*recomendado*) o familias por mecanismo.
3. **K2, el indicador de crédito:** empalme R. U. (≤ 1918) → EE. UU. (≥ 1919) en variaciones (*recomendado*: cubre toda la
   muestra, MDE 0,10 / 0,12) o solo EE. UU. desde 1919 (MDE 0,13 / 0,16).
4. **Datos:** añadir `boe_uk_corp_bond_spread_m` a las familias permitidas de `src/intl/data.py` (necesario para K2) y
   usar `fed_ebp_*` solo como descriptivo. *Recomendado: sí.*
5. **K1:** mantenerla aunque su potencia ronde el 50 % (*recomendado*: es la relación más valiosa del tema crédito, y
   pasarla a descriptiva sería elegir por miedo al resultado) o pasarla a descriptiva.

Si se aprueba: se congela como v1.0 con hora, se escribe `scripts/int6_corrida.py` con puerta, se commitea sin ejecutar,
**una sola corrida**, Validador, y después Bitácora y atlas.
