---
documento: P-EVAL-INT4 — prueba de REFUTACIÓN (una sola vez) de T1 y T2 de INT-4 en el bloqueado JST 2005-2020: prerregistro
version: 1.0 CONGELADA (2026-10-29)
estado: CONGELADO pero NO EJECUTABLE. Solo se ejecuta tras una decisión registrada del usuario (§7). El bloqueado NO se ha
  gastado: no se ha leído ningún indicador ≥ 2005, ni su disponibilidad, ni ninguna predicción ≥ 2005. Lo único conocido
  del bloqueado son los recuentos de eventos de docs/int/PEVAL_INT4_potencia.md (solo el objetivo, rgdpmad).
depende_de: docs/int/PEVAL_INT4_potencia.md (recomendación §4, aceptada por el usuario el 2026-10-29),
  research/int/peval_int4_potencia.json (10fc87e), docs/int/INT4_prerregistro_v0.md (v1.0, fa6d4c9),
  research/int/int4_resultado.json (73dd63e), research/int/termometro_referencias.json (b845741)
script: scripts/peval_int4_refutacion.py (commiteado DESPUÉS de este documento; fija su sha256)
---

# P-EVAL-INT4: prueba de refutación en el bloqueado JST (prerregistro v1.0)

## 0. Qué es y qué no es
- **Es una prueba de refutación, no de confirmación.** La potencia (PEVAL_INT4_potencia §3) mostró que el bloqueado
  (5-6 años distintos con evento) no puede confirmar la ventaja de INT-4 (criterio de INT-4: potencia 0,45 en T1 sin
  2020 y 0,42 en T2), pero sí puede **tumbarla** con poco riesgo de equivocarse si el efecto de desarrollo es real.
- La pregunta es: con los modelos T1 (entrada en recesión) y T2 (salida) de INT-4 **congelados con datos ≤ 2004** y sin
  reajustar nada, ¿ordenan los país-años de 2005-2020 **peor o igual** que el listón B1 (también congelado)? Si sí, la
  ventaja de desarrollo queda refutada fuera de muestra.
- Un "no refutado" **no es una confirmación**: solo dice que el bloqueado no la contradice. La evidencia de ventaja sigue
  siendo la de desarrollo (INT-4: ΔAUC +0,18 en T1 y +0,30 en T2; países de prueba AUS/CHE +0,21 / +0,22).
- Se gasta **una sola vez** y solo cuando el usuario lo decida (§7). Este documento no se puede cambiar después de
  congelado sin una enmienda con hora **antes** de la autorización (el script comprueba su sha256).

## 1. Modelo congelado (exacto)
- **Definición:** el logit agrupado de la familia principal de INT-4 (prerregistro v1.0 §4, `fa6d4c9`; motor
  `src/intl/int4.py` de `e4cceb5`), ajustado **una vez con todas las filas completas** del núcleo de 14 países,
  1871-2004 sin guerras, h = 1 (como `src/intl/int4.congelado` y `src/intl/termometro.congelar`):
  - **T1** (entrada): B1 (primer año tras un valle; log años desde el último valle) + C1 pendiente de la curva, C2 Δ5
    crédito/PIB, C4 difusión global de curvas invertidas, C5 Δ1 tipo real corto, C6 bolsa real del año t.
    1.090 filas, 166 eventos.
  - **T2** (salida): B1 (log años que lleva la recesión) + S1 curva, S2 Δ1 tipo real corto, S3 bolsa real, S4 difusión
    de caídas del PIB en los otros países, S5 Δ5 crédito/PIB al pico. 235 filas, 163 eventos.
- **Coeficientes** (intercepto, B1…, indicadores en el orden anterior). Fuente de verdad, sin redondeo:
  `research/int/termometro_referencias.json` → `final_sin_redondeo.modelo` (commit `b845741`;
  **sha256 `6d95d0f309048898f0c491b0cc840373246538ca701a9777d213c6f9a04bfeff`**):
  - T1: −1,776519; −0,193523; −0,404346; −0,135264; 1,405820; 1,935719; −1,009465; −3,028963
  - T2: 0,955983; 0,222135; 0,046778; 2,275585; 5,429558; −0,541010; −1,540102
- **Listón B1 congelado:** logit con solo las columnas de B1, ajustado con las mismas filas (no se guardó antes; se
  re-ajusta de forma determinista con ≤ 2004): T1 −1,245498; −0,133628; −0,319044 · T2 0,749634; 0,268394.
- **Comprobación previa (sin datos ≥ 2005):** el script re-ajusta ambos con datos ≤ 2004 (`load_dev`) y aborta si los
  coeficientes del modelo difieren de los del JSON en más de 1e-8. Comprobado el 2026-10-29: diferencia 0,0 en T1 y T2
  (1.090/166 y 235/163 filas/eventos, idénticos a `int4_resultado.json`).
- **Nada se reajusta, recalibra ni re-escala** con datos ≥ 2005. Sin intercepto nuevo ni recalibración del termómetro
  en vivo (eso es otra cosa: la traducción mensual de INT-5 no entra aquí; esto es el modelo anual JST).

## 2. Filas del bloqueado (fijadas; recuentos ya conocidos)
- **Núcleo de 14 países** (BEL, DEU, DNK, ESP, FIN, FRA, GBR, ITA, JPN, NLD, NOR, PRT, SWE, USA). AUS y CHE **no** entran
  (la potencia mostró que no cambian nada: AUS solo aporta 2020); CAN e IRL tampoco.
- **Orígenes t = 2004 … 2019, h = 1, año objetivo t + 1 = 2005 … 2020.** Datos de JST R6 hasta 2020 (la lectura se corta
  en 2020-12-31 aunque el warehouse tuviera años posteriores).
- **Fechado:** `src/intl/regimes.recesiones_anuales` sobre `jst_{iso}_rgdpmad` completo (≤ 2020), filas con
  `scripts/peval_int4_potencia.filas_bloqueado` (las mismas de la potencia). El tipo (financiera/normal) no se usa.
- **Muestras:**

| muestra | papel | filas en riesgo | eventos | años objetivo con evento (nº de países) |
|---|---|---|---|---|
| **T1 sin 2020** | **principal** | 164 | 25 | 2008 (10), 2009 (4), 2011 (3), 2012 (6), 2013 (2) |
| **T2** | **principal** | 46 | 25 | 2010 (13), 2012 (2), 2013 (3), 2014 (5), 2015 (2) |
| T1 con 2020 | sensibilidad (sin veredicto) | 178 | 39 | las anteriores + 2020 (14) |

- **2020 fuera de T1 a priori:** la pandemia es un choque exógeno que ningún indicador macro-financiero de t = 2019
  debería anticipar; incluirlo diluye el efecto (potencia ≈ 0,3) y lo mezcla con suerte. Se publica como sensibilidad.
  T2 no tiene filas de 2020 que cuenten (la salida de 2020 cae en 2021, fuera de R6).
- **Casos completos:** cada comparación usa las filas con B1 y todos los indicadores del giro (como INT-4). Se publican
  las filas en riesgo y las completas. Supuesto de la potencia: indicadores completos en 2005-2020.
- **Comprobación de recuentos antes de leer indicadores:** si el fechado con los datos del momento de la ejecución no da
  exactamente los recuentos de la tabla (filas, eventos y eventos por año), el script aborta **antes de leer ningún
  indicador ≥ 2005** (señal de que JST ha cambiado de versión; hace falta enmienda, §9).

## 3. Indicadores ≥ 2005 que se leerán (solo tras la autorización)
`jst_{iso}_{ltrate, stir, tloans, gdp, cpi, eq_tr_real}` (y `rgdpmad`, ya usado para el objetivo) del núcleo, ≤ 2020.
Paneles con las mismas fórmulas de `src/intl/int4.paneles` (parámetro `hasta = 2020`, retrocompatible; con el valor por
defecto los paneles de desarrollo son idénticos, test `test_paneles_hasta_no_cambia_desarrollo`) y derivadas de
`src/intl/panel.anual` (test `test_anual_desde_series_igual_que_panel_anual`). No se leen `crisisjst`, `hpnom`, `money`,
`wage` ni nada más.

## 4. Estadísticos (de las predicciones congeladas; nada se ajusta)
- p₁ = modelo congelado, p₀ = listón B1 congelado, en las mismas filas completas.
- **AUC** (Mann-Whitney, empates promediados) de cada uno; **ΔAUC = AUC(p₁) − AUC(p₀)**.
- **Bootstrap por bloques de año** (`src/intl/int4.bloques`: 2.000 réplicas, semilla 0; se remuestrean años objetivo con
  todos sus países): IC 95 % de ΔAUC, p bilateral, Δlog-loss, ΔBrier; y con los **mismos remuestreos** el IC 95 %
  percentil de la AUC del modelo.
- Calibración: pendiente e intercepto de logit(y) sobre logit(p₁).

## 5. Criterio (fijado aquí)

### 5.1 Umbrales
| símbolo | qué | umbral |
|---|---|---|
| S | signo de ΔAUC (estimación puntual) | **ΔAUC ≤ 0 → refuta** el giro |
| A | AUC del modelo, extremo inferior del IC 95 % por bloques | **> 0,5** para "no refutado" |
| D | datos suficientes en las filas completas | eventos ≥ 10, no eventos ≥ 10, años objetivo distintos con evento ≥ 3 |

### 5.2 Por giro principal (T1 sin 2020; T2), en este orden
1. Si falla D → **no concluyente (datos)**.
2. Si ΔAUC ≤ 0 → **REFUTADO** (el modelo congelado no ordena mejor que el listón fuera de muestra).
3. Si ΔAUC > 0 y el IC 95 % de la AUC del modelo está por encima de 0,5 → **NO REFUTADO**.
4. Si ΔAUC > 0 pero el IC de la AUC del modelo incluye 0,5 → **NO CONCLUYENTE**.

### 5.3 Global (INT-4 en el bloqueado)
- **Refutado** si al menos un giro principal está refutado (se dice cuál).
- **No refutado** si los dos giros principales están no refutados.
- **No concluyente** en cualquier otro caso.
- T1 con 2020 no entra en el veredicto (sensibilidad); si su resultado difiere del de T1 sin 2020 se publica y se
  atribuye a 2020, sin cambiar nada.
- Sin corrección por multiplicidad en el signo: es una regla de refutación conservadora a favor de refutar (dos
  oportunidades de refutar); su error se da en §6.

### 5.4 Informativos (se publican, no cambian el veredicto; potencia delante)
- IC 95 % de ΔAUC que excluye 0 tras Holm-2 (T1 sin 2020, T2): potencia 0,45 / 0,42.
- Δlog-loss < 0 (incluye la calibración del intercepto congelado): 0,90 / 0,90.
- Pendiente de calibración en [0,5; 1,5]: 0,72 / 0,60.
- Paquete INT-4 completo (IC Holm + Δlog-loss + pendiente): 0,31 / 0,24.
- **Ninguno de ellos se usará para decir "confirmado"**: su potencia no lo permite.

### 5.5 Qué implica cada resultado (fijado ahora, para no decidirlo viendo el resultado)
- **Refutado en T1:** B2 (cuyo recorte depende de p_T1) **no sustituye a B1** salvo nueva decisión registrada del usuario
  que lo justifique por escrito; la sombra puede seguir como registro. El paper y el Obsidian dicen "la ventaja de T1 no
  sobrevivió fuera de muestra".
- **Refutado solo en T2:** la parte de B2 que vuelve al peso de B1 con p_T2 se sustituye por la vuelta con el fechado
  (sin termómetro); T1 sigue como antes.
- **No refutado:** nada cambia; la decisión B2 frente a B1 sigue dependiendo de la sombra y de la evidencia de
  desarrollo. Se cita como "no contradicho fuera de muestra (prueba de baja potencia para confirmar)", **nunca** como
  confirmación.
- **No concluyente / no concluyente (datos):** como no refutado, pero no se cita como evidencia en ningún sentido.

## 6. Potencia de cada criterio (ya calculada; `research/int/peval_int4_potencia.json`, nada nuevo simulado)
Simulación con la estructura real de eventos, binormal, 1.000 réplicas × 1.000 bootstrap por bloques; ρ = parte común
por año del ruido (0,3 central). "Efecto dev" = AUC 0,55 → 0,73 (T1) y 0,58 → 0,77 (T2); "mitad" = la mitad de ΔAUC;
H0 = sin ventaja (AUC del modelo = la del listón).

**Por giro (ρ = 0,3; entre paréntesis ρ = 0 / ρ = 0,6):**

| criterio | T1 sin 2020 | T2 | T1 con 2020 (sensib.) |
|---|---|---|---|
| S: P(refutar) si **H0** (potencia para refutar un modelo sin ventaja) | **0,50** (0,51 / 0,50) | **0,49** (0,49 / 0,48) | 0,50 |
| S: P(refutar) si **efecto dev** (falsa refutación) | **0,024** (0,00 / 0,07) | **0,052** (0,01 / 0,11) | 0,020 |
| S: P(refutar) si **mitad** del efecto (falsa refutación) | 0,18 (0,07 / 0,23) | 0,22 (0,13 / 0,27) | 0,16 |
| A: P(IC AUC modelo > 0,5) si efecto dev | 0,73 (0,94 / 0,55) | 0,76 (0,86 / 0,67) | 0,79 |
| A: ídem si H0 (AUC = listón 0,55 / 0,58) | 0,10 | 0,16 | 0,12 |
| A: MDE 80 % (AUC del modelo) | 0,76 | 0,78 | 0,73 |
| "No refutado" (S y A) si efecto dev: cota [S + A − 1; min(S, A)] | [0,70; 0,73] | [0,70; 0,76] | [0,77; 0,79] |
| Razón de verosimilitudes de "refutado" (H0 / dev) | ≈ 21 | ≈ 9 | ≈ 25 |
| Razón de verosimilitudes de "ΔAUC > 0" (dev / H0) | ≈ 2,0 | ≈ 1,9 | ≈ 2,0 |

**Global (dos giros; aproximación con independencia entre T1 y T2, que usan años y filas distintos en su mayoría):**
- P(refutado global) si ninguno tiene ventaja (H0 en ambos): ≈ **0,75** (1 − 0,50 · 0,51).
- P(refutado global) si los dos tienen el efecto de desarrollo: ≈ **0,075** (ρ = 0: 0,01; ρ = 0,6: 0,17).
- P(refutado global) si los dos tienen la mitad del efecto: ≈ 0,36 (ρ = 0: 0,19; ρ = 0,6: 0,44).
- P(no refutado global) si los dos tienen el efecto de desarrollo: ≈ 0,49-0,55 (producto de las cotas por giro).

**Lectura honesta:** la prueba detecta la mitad de las veces un modelo sin ventaja (por giro; tres de cada cuatro con dos
giros), y si la ventaja de desarrollo es real la tumba por error 2-5 % de las veces por giro (≈ 7 % global). Si la
ventaja real es la mitad (encogimiento fuera de muestra plausible), la falsa refutación sube a ≈ 18-22 % por giro (≈ 36 %
global): **un "refutado" con ΔAUC cerca de 0 es compatible con una ventaja pequeña**, y así se dirá (se publica ΔAUC con su
IC). Un "no refutado" es evidencia débil (razón ≈ 2). Supuesto optimista heredado: la simulación da a todos los años
el mismo efecto e indicadores completos.

## 7. Regla de un solo uso y autorización
- **Quién decide:** solo el usuario. Ningún agente puede crear la autorización ni ejecutar el script sin ella.
- **Cuándo:** cuando el usuario vaya a decidir si B2 sustituye a B1 (INT-5) o cuando JST publique una versión con 2021+
  (en ese caso, antes, enmienda §9). No antes.
- **Cómo:** el usuario crea y **commitea** `research/int/PEVAL_INT4_AUTORIZADO` (texto plano) con estos campos:
  ```
  autoriza: usuario
  fecha: AAAA-MM-DD
  motivo: decision_B2_B1        (o jst_nueva_version)
  decision: <una frase del usuario: por qué se gasta ahora>
  ```
  y lo anota en el registro de decisiones / Obsidian (Bitácora). Después: `.venv/bin/python -m scripts.peval_int4_refutacion`.
- **Puerta doble del script** (lo primero que hace, antes de abrir el warehouse): (1) existe el fichero con esos campos
  (`autoriza: usuario`, motivo válido) y está commiteado; (2) árbol de git limpio (`src/intl/procedencia.py`). Además,
  sha256 de este documento y de `termometro_referencias.json` iguales a los fijados en el script.
- **Un solo uso:** si existe `research/int/peval_int4_refutacion.json`, el script se niega a correr. El resultado
  (JSON, MD y línea en `research/trial_log.md` con commit y hora) se publica sea cual sea. Si una ejecución autorizada
  falla a medias después de leer indicadores ≥ 2005, el bloqueado se considera gastado igualmente: se documenta el fallo,
  se arregla solo lo mecánico (sin mirar resultados) y se vuelve a correr con el mismo criterio.

## 8. Abortos previstos (todos antes de leer indicadores ≥ 2005)
1. Ya gastado (existe la salida). 2. Falta la autorización o está mal formada o sin commitear. 3. Árbol sucio.
4. Este documento o el modelo congelado han cambiado (sha256). 5. El re-ajuste ≤ 2004 no reproduce los coeficientes.
6. El fechado ≥ 2005 no reproduce los recuentos de §2 (en ese caso solo se habrá leído `rgdpmad`, ya conocido).
Tests sintéticos en `tests/test_peval_int4_refutacion.py` (los lectores de datos se sustituyen por trampas).

## 9. Enmiendas
- **JST con 2021+:** antes de autorizar, una enmienda v1.1 con hora puede alargar la ventana (T2 ganaría las salidas de
  2021), recontando la potencia **solo con el objetivo** (como PEVAL_INT4_potencia) y **sin cambiar** el modelo, los
  estadísticos, los umbrales ni las reglas §5. 2020 seguiría fuera de T1 principal. Si no hay enmienda, se usa la
  ventana 2005-2020 de esta versión aunque el warehouse tenga años posteriores (la lectura se corta en 2020).
- Cualquier otro cambio después de congelar invalida la prueba (el script lo detecta por el sha256).

## 10. Lo que este documento NO ha hecho
No se ha ejecutado nada contra el bloqueado. Para fijarlo solo se ha re-ajustado el modelo con datos ≤ 2004 (§1).
