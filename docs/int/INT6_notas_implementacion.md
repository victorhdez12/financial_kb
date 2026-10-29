---
documento: Notas de implementación de P-DEV-INT6 v1.0 (docs/int/INT6_prerregistro_v1.md, congelado 2026-10-29T18:01:03Z)
estado: escritas y commiteadas ANTES de la corrida única; ningún resultado visto. Ninguna lectura se ha elegido mirando datos de resultado (solo fechas y recuentos de disponibilidad de las series).
código: src/intl/int6.py (motor, funciones puras), scripts/int6_corrida.py (carga y corrida con puerta), tests/test_intl_int6.py (sintéticos)
---

# INT-6: notas de implementación

Regla seguida: donde el texto congelado admite más de una lectura, se elige la **más literal** (o, si no hay una más
literal, la que repite lo ya hecho en INT-3b / INT-4 / INT-4-ML o en `scripts/int6_potencia.py`, que fijó las mismas
definiciones para el cálculo de potencia). Cada elección se declara aquí.

## A. Datos y reglas comunes
1. **Corte.** Todo pasa por `src/intl/data.load_dev` (≤ 2004-12) y `src/intl/panel.anual`. El script comprueba que ningún
   año del panel ni ninguna fecha mensual pasa de 2004.
2. **Decisión 4.** `boe_uk_corp_bond_spread_m` añadido a las familias permitidas (commit aparte, 4b3789a). Existe en el
   warehouse (BoE Millennium, mensual, 1854-01 a 2016-12; ≤ 2004: 1.812 meses, ningún diciembre 1854-1918 falta).
3. **Hiperinflación (regla común).** "Inflación > 50 %" = tasa simple del IPC de JST, exp(Δlog cpi) − 1 > 0,5 (como
   `activos3b.inflacion_jst` en INT-3b). La fila (país, t) sale si la inflación de t **o** la de t + 1 supera el 50 %.
   **Lectura literal:** está en las "reglas comunes", así que se aplica a todas las preguntas de panel, también a K1, K2,
   X1 y M3 (en INT-4 no se aplicaba); en G1 descriptiva, igual.
4. **Guerras.** K1, K2, X1 (y M3): fuera las filas cuya ventana t … t + h toca 1914-1918 o 1939-1945 (INT-4). M1 / M2:
   todas las filas; la sensibilidad "sin guerras" quita las filas con t o t + 1 en esos años (la misma ventana t … t + 1).
5. **Países de prueba.** Siempre con el modelo congelado en el núcleo, informativos: K1, K2, X1 con AUS, CHE, CAN e IRL
   (no necesitan bolsa); M1 con AUS y CHE (bolsa); M2 con AUS, CHE, CAN e IRL. En M1 / M2 se publica la pendiente de cada
   país de prueba con z estandarizada con la media y la dt del núcleo.

## B. G2 (oro y tipo real, EE. UU. mensual)
1. Rejilla mensual completa (`panel._mensual_completa`), meses 1973-01 … 2004-12 (384).
2. y_m = Δlog `gold_wb_usd_m`. Inflación interanual del IPC = log(cpi_m) − log(cpi_{m−12}) (logarítmica, como
   `scripts/int6_potencia.py`, que fijó la serie para la potencia); x_m = Δ(ir3m_m / 100 − infl_{m−1}).
3. MCO con constante, Newey-West con **6 retardos fijos** (§3), t con T − 1 gl (`int3b.nw`). b se publica en "% de oro
   por 1 pp de Δ tipo real" (= b, porque y y x están en fracción) y estandarizada (b · dt(x) / dt(y) = r).
4. Placebo: x desplazada en círculo (np.roll) k = 12 … T − 12, todas; φ = máx(1, dt de las t placebo);
   p_cal = 2 · P(t_{T−1} > |t| / φ) (`int3b.calibrar`, bilateral como en INT-3b).
5. Criterio (iv): signo de la pendiente MCO en 1973-1988 y en 1989-2004 (submuestras de las mismas filas).
   Criterio (v): diciembre a diciembre, y = Δlog del oro de diciembre; x = Δ del tipo real de diciembre (tipo de diciembre
   − inflación interanual de noviembre); años 1973-2004 (32); solo el signo de la pendiente.
6. Sensibilidades: tipo real largo (`GS10`/100 − la misma inflación); sin 1979-1980 (meses de esos años fuera).
   **Oro en EUR (BIS/BCE): omitida.** No hay una serie EUR/USD (o ECU) antes de 1999 en las familias permitidas de
   `src/intl/data.py`, y el prerregistro solo autoriza añadir `boe_uk_corp_bond_spread_m`. Ampliar las familias por una
   sensibilidad sería una decisión no tomada. Se declara en la salida.

## C. M1 / M2 (dinero real → bolsa / bonos de t + 1)
1. x_it = Δlog `jst_*_money` − Δlog `jst_*_cpi`. Filas: núcleo, t con x_it y y_{i,t+1} (`eq_tr_real` / `bond_tr_real`
   de t + 1), t + 1 ≤ 2004, sin hiperinflación (A.3).
2. **Winsorización "en los percentiles 1 y 99 del conjunto":** percentiles de x sobre **todas** las filas del núcleo con x
   (1871-2004) tras el filtro de hiperinflación, una sola vez, los mismos para M1 y M2 (la regla mira solo el indicador).
3. z = (x_w − media) / dt, con la media y la dt de x_w en las filas de cada contraste. b en pp por 1 dt.
4. Driscoll-Kraay por año (`int3.driscoll_kraay`, retardos por defecto); el "año" de la fila es t.
5. Placebo: `int3.desplazar` de z (misma k en todos los países, en círculo dentro de [mín, máx] de t),
   k = 6 … L − 6, todas; t de DK en las filas con valor desplazado; φ y p_cal con `int3b.calibrar`, gl = años − 1.
6. Criterio (iv) "mismo signo en 1950-2004": filas con t ≥ 1950 (como el tramo "1950_2004" de la potencia, t ∈ 1950-2003).
7. Criterio (v): pendiente MCO de y sobre z **por país** (sin encoger), y DerSimonian-Laird (`int3.encoger`) de las
   pendientes por país de y **sin la media de cada año**; varianza de cada pendiente = MCO clásica s² / Σ(z − z̄)². Umbral
   ≥ 2/3 de los países en los dos (como `int3b.criterios`). Países con < 10 filas no cuentan.
8. Criterio (vi) "efectos de año": MCO con efectos fijos de país **y** de año; solo el signo de b.
9. Sensibilidades (efecto, IC y p de DK, sin placebo): sin guerras; "exceso de dinero" = Δlog dinero nominal − Δlog PIB
   real **total** (`rgdpmad` × `pop`); dinero estrecho real = Δlog `narrowm` − Δlog cpi; x_t → y_{t+2} (versión estricta);
   y = `bill_rate_real` de t + 1. Cada indicador alternativo se winsoriza con sus propios p1 / p99 (misma regla).

## D. K1 (auge de crédito → crisis bancaria)
1. Objetivo y filas: los de `scripts/int6_potencia.objetivo_crisis` (inicio = `crisisjst` = 1; en riesgo sin inicio en
   t − 4 … t; t + h ≤ 2004 y años con PIB; sin guerras en t … t + h), con la lista de países como parámetro, más el
   filtro de hiperinflación (A.3).
2. x_t = Δ5 (`tloans` / `gdp`) × 100 (pp del PIB).
3. **B1 = log(1 + años desde el último inicio de crisis ≤ t).** "Censurado al inicio de la muestra": sin inicio previo,
   años desde el primer año del país en el panel (primer año con PIB), como la concreción del listón de INT-4.
4. Evaluación (igual para K1, K2, X1 y M3): logit agrupado sin penalización (`int4.logit_fit`), dejar un país fuera,
   **AUC estratificada por país** (copia de `scripts/int4_sensibilidad_liston.auc_estrat`, un test comprueba que es igual);
   IC por bootstrap por bloques de año sobre las predicciones (2.000 réplicas, semilla 0), p bloques bilateral como en
   INT-4; Δlog-loss agrupada; pendiente de calibración (`int4.calibracion`) del modelo dejando un país fuera.
5. Placebo: el panel años × países del indicador candidato se desplaza k años en círculo dentro de 1870-2004, la misma k
   en todos los países, k = 6 … 129 (todas, `int4.KS`), como INT-4; se rehacen las filas completas y los dos modelos;
   ΔAUC estratificada; z = (Δ − media) / dt de los placebos, **p = 1 − Φ(z) unilateral (mejora)**, como INT-4-ML. El p
   por rangos se publica aparte, sin Holm.
6. Criterio (iv) de K1: ΔAUC estratificada de las predicciones (dejar un país fuera, ya hechas) restringidas a
   t ≤ 1913 y a t ≥ 1919, > 0 en las dos. 1950-2004 y la evaluación temporal: informativos.
7. Sensibilidades (sin placebo): h = 2; cronología `crisisjst_old` (objetivo, filas en riesgo y B1); "crédito en log" =
   Δ5 log(`tloans`); exclusión de 3 años (sin inicio en t − 2 … t).

## E. K2 (diferencial del centro financiero → entrada en recesión)
1. x_t = diferencial de diciembre de t − el de diciembre de t − 1 (pp), **dentro de cada serie**: R. U.
   (`boe_uk_corp_bond_spread_m`) para t ≤ 1918; `BAA` − `AAA` para t ≥ 1919. Como `BAA`/`AAA` empiezan en 1919-01, no hay
   Δ de EE. UU. para 1919: **x_1919 queda vacío** (lectura literal de "el Δ se calcula dentro de cada serie" y "R. U. para
   t ≤ 1918"; no se usa el R. U. en 1919).
2. Objetivo y filas: T1 de INT-4 (`int4.obj_entrada`, h = 1, 1871-2004 sin guerras) + hiperinflación (A.3). Listón B1 de
   INT-4 (`int4.liston`, "T1"). Evaluación: D.4-D.5.
3. Criterio (iv) = ΔAUC **estratificada** temporal 1950-2004 > 0 (`int4.temporal`, ventana creciente por décadas; como
   INT-4-ML, que midió el criterio temporal con la AUC estratificada).
4. Sensibilidades (sin placebo): solo EE. UU. (filas t ≥ 1919); R. U. en todos los años; nivel frente a la mediana de 10
   años = diferencial de diciembre de t − mediana de los diciembres t − 9 … t, dentro de cada serie (R. U. ≤ 1918,
   EE. UU. ≥ 1919); sobre el logit de INT-4 (listón = B1 + C1, C2, C4, C5, C6; filas completas para todos);
   EE. UU. con su propio diferencial: solo filas de EE. UU., dentro de muestra (no se puede dejar un país fuera con un
   país), descriptivo. **EBP: omitido** (no está en las familias permitidas; la decisión 4 no lo añade; es solo
   descriptivo con 4 entradas y no es "as of"). Se declara en la salida.

## F. X1 (contagio)
1. x_it = panel S4 de INT-4 (`int4.paneles`): % de los otros países del núcleo con Δlog `rgdpmad` < 0 en t, con ≥ 5 con
   dato (para los países de prueba, los 14 del núcleo). Mismas filas, B1, evaluación y criterios que K2.
2. Sensibilidades (sin placebo): "EE. UU. con el PIB cayendo en t" (1/0) para los otros 13 (sin filas de EE. UU.); cuota
   ponderada por el PIB real total de t (`rgdpmad` × `pop`) de los otros con dato (≥ 5); sobre el logit de INT-4; filas
   1950-2004 (objetivo T1 desde 1950 sin quitar guerras, como `t1_50` de la potencia).

## G. Multiplicidad (§5) y veredictos
1. Familia única Holm-6 (α = 0,05) sobre **G2: p_cal, M1: p_cal, M2: p_cal, K1 / K2 / X1: p de la z del placebo**. Es el
   criterio (2) de G2, M1 y M2 y el (ii) de K1, K2 y X1.
2. **Criterio (i) de K1, K2, X1 ("el IC de ΔAUC estratificada excluye el 0 tras Holm-6").** INT-4 lo implementó como
   Holm sobre los p bootstrap de su familia. Aquí la familia es de 6 y G2, M1, M2 no tienen p bootstrap. Lectura: Holm-6
   sobre {G2, M1, M2: p_cal; K1, K2, X1: p bloques de la ΔAUC estratificada}, con ΔAUC > 0. Así el IC se ajusta con el
   mismo m = 6 y el mismo orden por pasos.
3. "Establecido" = todos los criterios de su pregunta. Lo que no es establecido se publica como "no establecido" (y, en
   M1 / M2 con el signo contrario, se dice así: no es un descubrimiento).

## H. Descriptivas e informativas (§4; sin Holm ni veredicto)
1. G1: oro real en moneda local (`activos3b.oro_panel`) en recesión (años pico + 1 … valle), recesión financiera (tipo
   "financiera") y crisis (año de inicio de `crisisjst` y el siguiente) frente al resto, efecto fijo de país y IC de
   Driscoll-Kraay (`int3b.panel_contraste` sin placebo), en 1972-2004, 1877-1971 y 1877-2004; MDE al lado, leído de
   `research/int/int6_potencia.json`. Oro real en USD (`activos3b.mundial`) frente a la cuota del núcleo en recesión
   (Newey-West). Oro (Δlog `gold_wb_usd_m`) en los meses con Δlog `oecd_share_usa` ≤ −5 % y ≤ −8 % frente al resto,
   1973-2004, diferencia de medias por MCO con NW (6 retardos). Frase obligatoria literal.
2. M3: x de M1 (dinero real winsorizado), objetivo T1, añadido a B1 y sobre el logit de INT-4 (B1 + C1, C2, C4, C5, C6),
   con la evaluación de D.4-D.5 (placebo incluido, solo del dinero). Sin veredicto.
3. ICC por décadas (1870-1879 … 2000-2004), núcleo: ICC de ANOVA por año (`scripts/int4_potencia.icc_anova`) del
   crecimiento del PIB real per cápita y del estado de recesión.

## I. Ejecución
Una sola corrida: `.venv/bin/python -m scripts.int6_corrida` con el árbol limpio. Salida `research/int/int6_resultado.json`
y `.md` y una línea en `research/trial_log.md`. Si falla antes de escribir la salida, se arregla el fallo técnico y se
declara en un commit con el motivo.

Comprobaciones previas que NO son corridas (ningún indicador cruzado con ningún resultado real):
- `--comprobar`: carga los datos reales y solo cuenta filas y eventos (T1 1.314 / 220 tras el filtro de hiperinflación,
  frente a 1.332 / 222 de la potencia sin él; K1 antes de exigir el crédito 1.329 / 60; Δ diferencial 1855-2004 sin 1919,
  149 años; 41 país-años fuera por hiperinflación en t o t + 1).
- Ensayo de extremo a extremo con datos **inventados** (fuera del repositorio) para cazar errores de programación.
- Orden de escritura: primero el JSON y la línea del registro; después el `.md`. Si el `.md` fallara, se rehace desde
  el JSON con `--informe` (no recalcula nada).
