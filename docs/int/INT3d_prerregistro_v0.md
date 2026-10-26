---
documento: P-DEV-INT3d — prerregistro interno del estudio de eventos de giros (recesiones y cambios de régimen) en el panel internacional anual
version: 0.1-borrador (2026-10-26)
estado: BORRADOR para el usuario. Nada cruzado: ninguna rentabilidad calculada alrededor de ningún evento real. Diseño y potencia (corrida, commit 3c588c1).
plan: docs/PLAN_internacional_v0.md (pieza 2, ampliación INT-3d pedida por el usuario el 26-oct; Bitácora "Ampliación pedida por el usuario")
depende_de: INT-1 (fechado anual de recesiones y etiqueta anual), INT-2 (método de potencia), INT-3 y su validación (docs/validation/2026-10-26_int3.md)
fuente_potencia: scripts/int3d_potencia.py → research/int/int3d_potencia.json (procedencia en el JSON)
---

# P-DEV-INT3d v0.1 (borrador): ¿cuándo tocan fondo los activos y cuánto cuesta esperar a confirmar el giro?

## 0. Qué es y qué no es
- **Pregunta del usuario (26-oct):** saber "cuándo se ve la luz" y cuándo cambia el régimen: en qué momento, respecto al
  pico y al valle de la recesión, tocan fondo la bolsa, los bonos, la vivienda y las letras; cuánto se pierde (o se gana)
  por esperar a **confirmar** el giro con los datos tal como se publicaban; y si las recesiones financieras son distintas
  de las normales.
- **Es** un estudio de eventos ex post, anual, en el panel JST (núcleo de 14 países, 1870-2004), con unos pocos
  contrastes fijados aquí y el resto descriptivo. Más un secundario **mensual de EE. UU.** (NBER) declarado **sin
  potencia**.
- **No es** una regla de inversión ni un forecast (eso es INT-4: entrada y salida de recesión con indicadores "as of").
  Aquí el evento se fecha con datos revisados y ex post; lo único "en tiempo real" es la **fecha de confirmación** (§2.3).
- **Nada ≥ 2005.** El periodo bloqueado (JST 2005-2020) queda para una evaluación única aparte, si el usuario la decide.

## 1. Datos y muestra
- **Rentabilidades:** JST R6, reales anuales: `eq_tr_real`, `bond_tr_real`, `bill_rate_real`, `housing_tr_real`, siempre
  en **log(1 + r)** (con r ≥ −0,99): las ventanas suman años y la media aritmética de rentabilidades se rompe con las
  hiperinflaciones (lección M3 de la validación de INT-3). Excesos: bolsa − letras y bonos − letras (diferencia de logs).
- **Núcleo:** BEL, DEU, DNK, ESP, FIN, FRA, GBR, ITA, JPN, NLD, NOR, PRT, SWE, USA. **1870-2004.**
- **Países de prueba:** AUS y CHE (CAN e IRL no tienen rentabilidades JST). No entran en nada; al final solo se publican
  los signos de los contrastes con su fechado.
- **Cobertura:** un evento entra en un contraste solo si **todos** los años de su ventana tienen dato del activo y caen en
  1870-2004 (ventanas que tocarían 2005 o más: fuera; nunca se rellenan). Recuentos por contraste en §10.

## 2. Eventos (fijados aquí)

### 2.1 Recesiones (principal)
- **Fechado anual de INT-1** (`$FIN_DATA_ROOT/intl/recesiones_anuales_dev.parquet`, convención JST): **pico P** = año con
  PIB real per cápita máximo local antes de una caída; **valle V** = último año de caída. Años de recesión: P + 1 … V.
- **Tipo:** **financiera** si hay crisis JST (`crisisjst`) en P ± 2; si no, **normal** (como INT-1 e INT-3).
- **Recuento (núcleo, ≤ 2004): 267 recesiones**, 194 normales y 73 financieras; **95 años de pico distintos**; duración
  media 1,6 años (mediana 1). Años con más picos a la vez: 1916 (10 países), 1939 (9), 1913, 1929 y 1992 (8).

### 2.2 Cambios de cuadrante (crecimiento × inflación)
- **Etiqueta anual de INT-1** (principal: inflación relativa + 2 %; `regimen_anual_dev.parquet`), años sin truncar.
- **Evento E-I, entrada en inflación alta** (sobrecalentamiento ∪ estanflación) en el año t: inflación alta en t e
  inflación baja en t − 1 y t − 2 (racha previa ≥ 2 años, para no contar los vaivenes de un año). Es la transición con
  mecanismo más claro y la que conecta con el resultado más sólido de INT-3 (Q2, bonos con inflación alta).
- **Solo descriptivos** (sin contraste): entrada en estanflación, salida de la inflación alta (alta → baja con racha
  previa ≥ 2), entrada en crecimiento bajo. Los giros del eje de crecimiento ya los cubren las recesiones.
- **Limitación grave, declarada:** la etiqueta es **ex post y centrada** (tendencia e inflación media de t − 5 … t + 5).
  En tiempo real no se podía saber en abril de t + 1 que t era "inflación alta" según esta etiqueta. La fecha de
  confirmación de §2.3 es por tanto **optimista** para E-I (el coste de esperar sale como cota inferior). Ver decisión 3.

### 2.3 Fechas de confirmación (retrasos reales de `src/intl/lags.py`)
- JST anual: el dato del año t se da por conocido el **30 de abril de t + 1** (`RETRASO_DIAS["jst"] = 120`).
- **Entrada en recesión:** se confirma cuando se publica el primer año de caída (P + 1) → **30-abr de P + 2**.
- **Salida de recesión:** se confirma cuando se publica el primer año de crecimiento (V + 1) → **30-abr de V + 2**.
- **Entrada en inflación alta:** se "confirma" al publicarse el año t → **30-abr de t + 1** (optimista, §2.2).
- **Fecha del oráculo** (quien supiera el giro al instante): 1 de enero del primer año del nuevo estado (P + 1, V + 1, t).
- Entre el oráculo y la confirmación pasan **16 meses**. Con datos anuales, los 4 meses del segundo año se aproximan como
  **4/12 de su rentabilidad log** (deriva constante dentro del año; supuesto declarado). Sensibilidades: confirmación a
  12 meses (lo que se sabría a fin de año si no hubiera retraso) y a 24 meses.
- **Coste de esperar** = rentabilidad relativa acumulada entre el oráculo y la confirmación (el tramo que se pierde o se
  evita por no actuar hasta tener el dato). Interpretación: en la salida, positivo = el rebote que se pierde; en la
  entrada, negativo = la caída que se come quien espera para vender.

### 2.4 Ventanas de evento (en años de calendario)

| uso | ventana |
|---|---|
| trayectorias descriptivas alrededor del pico | P − 3 … P + 5 |
| trayectorias descriptivas alrededor del valle | V − 3 … V + 3 |
| "fondo" de cada activo (año del mínimo del índice acumulado) | niveles a fin de P − 2 (= 0), P − 1, …, V + 3 |
| caída máxima de la bolsa en el episodio | desde fin de P − 1 hasta el mínimo de fin de P … V + 1 (incluye el año del pico: lección M4 de INT-3) |
| vivienda en el episodio | P … V + 2 |
| bonos durante la recesión | P + 1 … V (media por año) |
| coste de esperar (entrada / salida / inflación) | P + 1 + 4/12·(P + 2) · V + 1 + 4/12·(V + 2) · t + 4/12·(t + 1) |
| "lo que queda" tras confirmar (descriptivo) | de la confirmación al fin del 3.er año del nuevo estado |

## 3. Contrastes candidatos (orden de prioridad y efecto plausible fijados ANTES de calcular la potencia)

Efecto "anómalo" = valor en las fechas reales menos la media de los placebos (§5): descuenta lo que la ventana da a
cualquier fecha (p. ej., la prima de la bolsa sobre las letras en 16 meses, ≈ +8 pp, o el centro geométrico de la
ventana en los contrastes de "fondo"). Los efectos plausibles salen de la literatura y del mecanismo; algunos están
contaminados por INT-3 (última columna).

| prioridad | id | pregunta | estadístico por evento | agrupación | signo | efecto plausible | mecanismo / literatura | contaminación |
|---|---|---|---|---|---|---|---|---|
| 1 | **C1** | ¿cuesta esperar a confirmar la **salida**? | bolsa − letras, V + 1 + 4/12·(V + 2) | año del valle | + | **+8 pp** | la bolsa rebota antes que el PIB (Moore 1983; Siegel 1991: fondo ≈ 4-5 meses antes del valle NBER) | baja |
| 2 | **C2** | ¿cae más la bolsa en las recesiones **financieras**? | caída máxima de la bolsa real (§2.4); financiera − normal | año del pico | − | **−10 pp** | desapalancamiento, crisis bancaria (Reinhart-Rogoff 2009: −56 % real en crisis; JST 2013) | media: Q5b de INT-3 (+1,4 pp con otra definición) |
| 3 | **C3** | ¿protegen los bonos durante la recesión? | bonos − letras, media por año de P + 1 … V | año del pico | + | **+3 pp/año** | bajan los tipos largos; huida a la calidad | media: Q3 de INT-3 (bonos en crecimiento bajo) |
| 4 | **C4** | ¿cuesta esperar a confirmar la **entrada**? | bolsa − letras, P + 1 + 4/12·(P + 2) | año del pico | − | **−6 pp** | la bolsa sigue cayendo en el primer año de recesión (INT-3 Q5: −5,5 pp/año en recesión) | media: Q5 de INT-3 |
| 5 | **C5** | ¿cuesta esperar a confirmar la **inflación alta**? | bonos − letras, t + 4/12·(t + 1) | año t | − | **−5 pp** | la inflación no esperada sube los tipos largos (Fisher; INT-3 Q2: −10 pp/año) | alta: Q2 de INT-3 |
| 6 | **C6** | ¿cae más la **vivienda** en las financieras? | vivienda real, P … V + 2; financiera − normal | año del pico | − | **−8 pp** | auges de crédito hipotecario (JST "Leveraged bubbles" 2015; Reinhart-Rogoff: −35 % en 6 años) | media (JST con este panel) |
| 7 | **C7** | ¿toca **fondo la bolsa antes** del valle? | año del mínimo del índice de bolsa real − V | año del valle | − | **−0,5 años** | la bolsa descuenta la recuperación | baja |
| 8 | **C8** | ¿toca **fondo la vivienda después** del valle? | año del mínimo del índice de vivienda real − V | año del valle | + | **+1 año** | precios rígidos, ajuste lento (Reinhart-Rogoff: caídas de 6 años) | media |

Las letras no tienen contraste: su "fondo" no tiene mecanismo claro (tipo real de corto plazo). Van en descriptivos.

## 4. Unidad de inferencia y agregación
- **Valor por evento** x_e (país-recesión o país-entrada en inflación alta).
- **Agrupación por año común:** los eventos que comparten el **año ancla** (pico para entradas y comparaciones; valle para
  salidas y "fondos"; t para E-I) forman un grupo, porque comparten el choque global (1916: 10 países; 1929: 8).
- **Estadístico principal:** media de las medias por año ancla (**cada año ancla pesa 1**); en las comparaciones
  financiera − normal, esa media en cada grupo y su diferencia. **Sensibilidad:** cada evento pesa 1.
- Los años ancla cercanos (1929 y 1930) son grupos distintos pero sus ventanas se solapan; eso **no** se corrige con la
  agrupación sino con el placebo (§5), que conserva exactamente los solapes.
- **Por país:** signos por país, sin encoger, solo descriptivos (lección A1 de INT-3: con choques comunes, el
  encogimiento de DerSimonian-Laird hace que "14/14" salga por construcción).

## 5. Inferencia: placebo, Holm y número de contrastes
- **Por qué no CR2 por año:** en INT-3 el error agrupado por año fue anticonservador (6-14 % de falsos positivos) por los
  choques comunes persistentes; aquí, además, las ventanas de varios años se solapan entre grupos. Se usa el placebo como
  referencia principal desde el diseño.
- **Placebo con fechas desplazadas:** todas las fechas de evento se mueven **k años** (la **misma k** en todos los
  países, en círculo dentro de 1870-2004), k = 6 … 129 (124 desplazamientos); se conservan la agrupación por año, los
  solapes, las duraciones y el tipo (financiera / normal). Los eventos desplazados cuya ventana sale de la muestra o no
  tiene datos se quitan en ese desplazamiento. Los placebos que caen cerca de recesiones reales se dejan (hace el
  contraste conservador).
- **p principal (z calibrada con el placebo):** z = (T − media de los placebos) / desviación típica de los placebos;
  p = 2·(1 − Φ(|z|)). No tiene el suelo de 1/125 del p por rangos (con Holm a 0,05/6 = 0,0083 ese suelo ya no deja pasar
  nada: le pasó a la sensibilidad robusta de INT-3).
- **p por rangos** (fracción de placebos con |T_k − media| ≥ |T − media|): criterio adicional, ≤ 0,05.
- **Holm** sobre la familia, con la p principal.
- **Número de contrastes limitado por la potencia (regla fijada aquí):** para k = 1 … 6 se calcula el MDE de cada
  candidato con Bonferroni-k (80 %, bilateral 5 %). **k\*** = el mayor k tal que al menos k candidatos tienen MDE ≤ su
  efecto plausible; entran esos (si sobran, los primeros por prioridad). Los demás pasan a **descriptivos** (se publican
  con su intervalo y su placebo, sin veredicto). Máximo 6. Se aplica a la muestra principal; la familia queda escrita en
  §10 antes de cruzar nada.
- Q5b de INT-3 enseñó que una diferencia financiera − normal puede salir por la definición de la ventana: aquí la ventana
  incluye el año del pico y la medida es **por episodio** (cada recesión pesa 1 dentro de su año ancla).

## 6. Criterio de "efecto establecido" (para los contrastes de la familia)
1. Signo igual al esperado.
2. p principal significativa tras **Holm** (5 %).
3. p por rangos ≤ 0,05 (fuera del 95 % de los placebos).
4. Mismo signo **sin los eventos cuyas ventanas tocan 1914-1918 o 1939-1945** y **quitando el año ancla más influyente**
   (el que más mueve el estadístico).
5. (Informativo, no decide; ver decisión 4) signo en 1950-2004, publicado con la probabilidad de acertar el signo que da
   la potencia de esa submuestra.

## 7. Descriptivos (se publican siempre; no deciden)
- **Trayectorias medias** de la rentabilidad real anómala (frente a la media de cada país) de bolsa, bonos, letras y
  vivienda, en P − 3 … P + 5 y V − 3 … V + 3, con bandas del 5-95 % de los placebos; normales y financieras por separado.
- **Distribución del año del fondo** (respecto a V) de los cuatro activos, real y placebo.
- **Coste de esperar en bruto** (sin restar el placebo) y **lo que queda** tras confirmar (§2.4), por activo y tipo, en
  la entrada, la salida y E-I.
- **Cambios de cuadrante sin contraste:** entrada en estanflación, salida de la inflación alta, entrada en crecimiento
  bajo: trayectorias t − 2 … t + 3 de los cuatro activos y coste de esperar en bruto.
- Los candidatos que no entren en la familia.
- Signos por país (sin encoger) y signos en AUS y CHE.

## 8. Sensibilidades (se publican siempre; no deciden)
Sin guerras (criterio 4); 1950-2004; cada evento pesa 1; confirmación a 12 y 24 meses; rentabilidades winsorizadas al
1 %-99 % de la distribución incondicional de cada activo; sin años con inflación > 50 % (hiperinflaciones); E-I sin
años en "frontera"; inflación absoluta del 3 % (etiqueta de sensibilidad de INT-1) para E-I; en C2 y C6, nula por
permutación de la etiqueta financiera / normal entre años ancla (en vez de fechas desplazadas).

## 9. Secundario informativo: EE. UU. mensual (NBER), SIN potencia
- **Eventos:** picos y valles NBER (`USREC`, solo fechas, nunca como variable) con ventana −12 … +24 meses completa:
  6 picos (1969-12, 1973-11, 1980-01, 1981-07, 1990-07, 2001-03) y 6 valles (1970-11, 1975-03, 1980-07, 1982-11,
  1991-03, 2001-11); la letra mensual empieza en 1964-07.
- **Activos:** `r_bolsa_tr` (índice OCDE de **medias mensuales**, suavizado, más dividendo JST repartido: declarado),
  `r_bono`, `r_letra` del panel mensual de INT-0; reales con `inflacion_mes`. Sin vivienda mensual.
- **Qué se mira:** mes del fondo del índice real de bolsa y de bonos respecto al pico y al valle; coste de esperar con
  dos fechas de confirmación: (a) **anuncio del NBER** donde existe (pico 1980-01 → 3-jun-1980; valle 1980-07 →
  8-jul-1981; pico 1981-07 → 6-ene-1982; valle 1982-11 → 8-jul-1983; pico 1990-07 → 25-abr-1991; valle 1991-03 →
  22-dic-1992; pico 2001-03 → 26-nov-2001; valle 2001-11 → 17-jul-2003); (b) **regla mecánica** con los retrasos de
  `src/intl/lags.py`: giro + 6 meses (fase mínima de Bry-Boschan de INT-1) + 75 días de la producción industrial ≈
  **9 meses**, para los 12 eventos.
- **Sin contrastes ni veredicto.** MDE ingenuo (6 eventos independientes, 16 meses) ≈ **16 pp** de exceso de la bolsa:
  solo se ve un efecto enorme. Se publica como ilustración con fechas precisas, no como evidencia.

## 10. Potencia (corrida con puerta: commit `3c588c1`, árbol limpio, 2026-10-26T18:49:17Z; `research/int/int3d_potencia.json`)
Solo fechas de eventos, disponibilidad de datos (sí/no) y estadísticos incondicionales de los activos (log real, núcleo,
≤ 2004): bolsa σ = 0,23, ρ entre países 0,32; bonos − letras σ = 0,08, ρ 0,35; vivienda σ = 0,10, ρ 0,09; bolsa −
letras σ = 0,21, ρ 0,31; AR(1) del factor común 0,25-0,66 según el activo. 2.000 paneles simulados (factor común AR(1) +
país AR(1)) sin efecto en las fechas reales → desviación típica (SD) del estadístico; 300 más con los 124 placebos →
tamaño y potencia de la z calibrada. Colas gruesas (t con 4 gl): MDE prácticamente iguales.

**Recuentos y solapes (muestra principal):** 233-245 eventos con ventana completa en los contrastes de bolsa y bonos
(91-94 años ancla distintos, m* de Kish ≈ 3,9 eventos por año ancla), 168-174 en vivienda, 200 entradas en inflación
alta (77 años; 154 sin frontera). Pares de eventos de países distintos con ventanas solapadas: 2-4 % en las ventanas
cortas, ≈ 10 % en las de "fondo". 61 recesiones desde 1950. Sin guerras se pierde un 13-25 % de los eventos.

| id | eventos (años ancla) | SD | MDE k = 1 | MDE k = 2 / 4 / 6 | efecto plausible | potencia (k = 1) | tamaño z-placebo | sin guerras MDE k = 1 | 1950-2004 MDE k = 1 |
|---|---|---|---|---|---|---|---|---|---|
| C1 espera salida | 234 (94) | 2,5 pp | 7,1 pp | 7,8 / 8,5 / 8,9 | +8 | 0,88 | 0,03 | 7,5 | 13,5 |
| C2 financiera bolsa | 245 (93; 69 financ.) | 4,7 | 13,1 | 14,4 / 15,6 / 16,2 | −10 | 0,57 | 0,08 | 13,4 | 38 |
| C3 bonos en recesión | 243 (92) | 0,6 | 1,8 | 1,9 / 2,1 / 2,2 | +3 /año | 1,00 | 0,07 | 2,0 | 3,7 |
| C4 espera entrada | 233 (91) | 2,4 | 6,8 | 7,4 / 8,1 / 8,4 | −6 | 0,70 | 0,06 | 7,7 | 12,9 |
| C5 espera inflación | 200 (77) | 0,9 | 2,4 | 2,6 / 2,9 / 3,0 | −5 | 1,00 | 0,05 | 2,6 | 3,8 |
| C6 financiera vivienda | 174 (82; 41 financ.) | 5,1 | 14,4 | 15,8 / 17,1 / 17,9 | −8 | 0,34 | 0,08 | 15,4 | 35 |
| C7 fondo bolsa | 239 (92) | 0,37 años | 1,03 años | 1,13 / 1,22 / 1,27 | −0,5 | 0,28 | 0,06 | 1,11 | 1,75 |
| C8 fondo vivienda | 168 (75) | 0,33 años | 0,91 años | 1,01 / 1,09 / 1,14 | +1 | 0,87 | 0,09 | 0,98 | 1,52 |

**Regla del §5 aplicada (muestra principal): k\* = 2 → familia = {C1, C3}.** Con k = 3 solo pasan C3 y C5 (C1 necesita
8,2 pp > 8 y C8 1,06 > 1 año), así que no caben 3. Con k = 2 pasan C1 (7,8 pp), C3 y C5 (C8 se queda a 1,01 años),
y entran los dos primeros por prioridad.
**C5 queda fuera solo por el orden de prioridad**, no por falta de potencia (ver decisión 1). Todo lo demás es
descriptivo: C2 y C6 (financiera frente a normal) y C7 (fondo de la bolsa) no tienen potencia para efectos plausibles;
C4 está en el límite.

**Lectura:**
- **Sí hay potencia** para la pregunta del usuario más útil (C1: cuánto rebote se pierde por esperar a confirmar la
  salida, si es ≥ 8 pp anómalos) y para el papel de los bonos en la recesión (C3, ≥ 2 pp/año).
- **No hay potencia** para distinguir recesiones financieras de normales en rentabilidades por episodio (hace falta
  ≥ 13 pp en bolsa, ≥ 14 pp en vivienda: solo 69 y 41 financieras, concentradas en pocos años). Se describen.
- **Con datos anuales no se puede fechar el fondo** con precisión de meses: el MDE es ≈ 1 año. El "cuándo" fino solo lo da
  el secundario mensual de EE. UU., sin potencia (MDE ingenuo ≈ 16 pp con 6 eventos).
- **1950-2004** solo sirve para signos: los MDE se duplican (C1 13,5 pp; C3 3,7 pp).
- **Calibración de la z placebo** (300 paneles sin efecto, 5 % nominal): 3-7 % en C1, C3, C4, C5 y C7; **8-9 % en C2, C6
  y C8** (algo anticonservadora en las comparaciones financiera − normal y en el fondo de la vivienda: por eso el
  criterio 3 del p por rangos). La SD de los placebos sale menor que la SD entre paneles en C1, C4, C7 y C8 porque la
  media de los placebos se mueve con el mismo factor común; lo que importa es el tamaño de la z, que sale bien.
- Supuestos de la simulación (declarados): Gaussiana o t₄, un solo ρ y un AR(1) común por activo, sin subida de la
  correlación en las crisis; con correlaciones que suben en las recesiones, la potencia real será algo menor.

## 11. Contaminación declarada
- Sabemos qué pasó en 1929-33, 1973-75, 1991-93 (crisis nórdicas) y 2001; la literatura de recesiones financieras con
  este panel (Jordà-Schularick-Taylor 2013, 2015) es posterior y usa estos años.
- INT-3 ya miró rentabilidades por régimen y en años de recesión (Q2, Q3, Q5, Q5b): C3, C4 y C5 no son independientes de
  lo que ya sabemos; su novedad es el **momento** (antes o después de confirmar), no el signo.
- Los efectos plausibles de §3 se escribieron sabiendo los resultados de INT-3.

## 12. Orden y gobierno
1. Este borrador y el script de potencia se commitean **antes** de correr la potencia (procedencia en el JSON).
   Declarado: el script se depuró con `--prueba` (200 + 20 simulaciones, sin puerta, sin escribir nada) antes del commit;
   los candidatos, su orden y sus efectos plausibles ya estaban escritos en el script y no se cambiaron después.
2. La potencia se corre una vez con la puerta (árbol limpio) y fija la familia (§5, §10).
3. El usuario aprueba el texto → commit y push con hora **antes** de cruzar nada.
4. Código del estudio de eventos con tests sintéticos, commiteado antes de correr; **una sola corrida** con la puerta;
   todo al registro de pruebas.
5. Validador independiente del resultado.

## 13. Decisiones del usuario
1. **Familia de contrastes:** la regla da **{C1, C3}** (k = 2). Alternativa: {C1, C3, C5} con Holm-3 (C5 tiene potencia de
   sobra; C1 baja a potencia ≈ 0,77 con su efecto plausible). Recomendado: mantener la regla tal cual ({C1, C3}) y C5
   como descriptivo destacado, porque además depende de la etiqueta ex post (decisión 3).
2. **Guerras:** principal con todos los eventos y sin guerras como criterio 4 (recomendado, como INT-3) o principal sin
   guerras (como INT-4; se pierde ≈ 15-20 % de los eventos).
3. **E-I (inflación alta) con etiqueta ex post centrada:** mantener C5 con la confirmación optimista declarada
   (recomendado si la familia lo admite) o dejar E-I solo descriptivo hasta tener una etiqueta "as of" de un solo lado.
4. **1950-2004:** solo informativo (recomendado: poca potencia) o criterio de signo como en INT-3.
5. **Secundario de EE. UU.:** con los anuncios del NBER y la regla de 9 meses (recomendado) o solo una de las dos.
