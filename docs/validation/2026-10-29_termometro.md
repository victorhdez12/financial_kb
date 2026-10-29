---
documento: validación del termómetro de recesión informativo (traducción mensual del logit anual de INT-4)
fecha: 2026-10-29
autor: Validador independiente (rama val-termometro, worktree financial_kb_int3b); no ha escrito este código
objeto: docs/int/TERMOMETRO_diseno_v1.md (v1.2 §8 `e9ec71d`; v1.3 §9 `a94ac09`), src/intl/termometro.py,
  scripts/termometro_puerta.py (1.er intento, `24979da`), scripts/termometro_puerta_v2.py (2.º, `eb3c73d`),
  tests/test_intl_termometro.py, research/int/termometro_puerta{,_v2}.{json,md}
restricciones: solo datos ≤ 2004 (load_dev / load_dev_curado); no se miran rentabilidades; los resultados oficiales no se
  reescriben; las sensibilidades (scripts/val_termometro_sens.py, commit `ada66e7`, commiteado antes de correrlo) son a
  posteriori y no cambian el veredicto
---

# Validación del termómetro informativo

## Veredicto global

(se rellena al final)

## 1. "As of" y corte ≤ 2004 — ✅

Comprobado leyendo el código y con valores reales (USA, abril de 1991):

| dato | retraso en el código | qué se ve en el fin de abril de t + 1 | comprobación |
|---|---|---|---|
| BIS crédito/PIB (Δ 20 trimestres) | `RETRASO_BIS = 183` días tras el fin del trimestre (`asof_q`) | trimestre III de t (30-sep + 183 = 1-abr) | C2 USA 1991-04-30 = Δ20 de 1990T3 (14,75); el 31-mar todavía es 1990T2 ✅ |
| PIB trimestral (S4, fechado) | `RETRASO_PIB = 75` | trimestre IV de t (31-dic + 75 = 16-mar) | por código (`asof_q`, `estado_mensual`) ✅ |
| IPC | 45 días (`src/intl/lags.py`) | febrero de t + 1 (28-feb + 45 = 14-abr; marzo llega el 15-may) | ipc_yoy USA 1991-04-30 = log IPC feb-91/feb-90 (0,05176) ✅ |
| tipos y bolsa | 1 día | marzo de t + 1 | tipo_3m USA 1991-04-30 = 6,45 = marzo ✅ |
| JST anual (año t) | 120 días | año t | ✅ |

- Las transformaciones (Δ20, Δ4, interanuales, medias de 12 meses) se hacen sobre la rejilla completa y después se desplazan
  (`_rejilla_q` + `asof_q`; `panel._mensual_completa` + `lags.asof`); `merge_asof` es hacia atrás. Ninguna fila usa un dato
  publicado después del fin de abril de t + 1.
- Corte: `load_dev` filtra `date ≤ 2004-12-31` y `check()` falla si se cuela algo; `load_dev_curado` igual para el PIB.
  `panel.anual` falla con años > 2004. Las filas usan t ≤ 2003 (abril de 2004). El BIS y el PIB traen el trimestre
  2004T4, pero su fecha de disponibilidad (2005) nunca se alcanza en la rejilla (acaba en 2004-12). Nada de JST ≥ 2005.
- ⚠️ (declarado en el diseño, se recuerda): niveles REVISADOS (obs_latest), no vintages; y el PIB trimestral OCDE de los
  años sesenta-setenta de varios países europeos es en parte interpolado de datos anuales por los institutos. Eso
  favorece al fechado trimestral y a S4 en desarrollo frente a lo que se verá en vivo.
- Nota de diseño de INT-4 (no de este código): el origen es el 30 de abril de t + 1 y el objetivo es "entrada en t + 1";
  los meses enero-marzo de t + 1 están a la vez en la información mensual y en el año objetivo. Es la convención de INT-4,
  no una fuga del termómetro.

## 2. Rectas de escala — ✅ con una fuga menor (⚠️)

- **Pares/impares:** `rectas()` ajusta con `par_fit(t)` y cuenta la otra mitad con `par_puerta(t)` sobre los años
  1950-2003 con ambos datos (no solo las filas del modelo, como pide §8). En el 2.º intento se llama dos veces, con los
  papeles cambiados (`PAR, IMPAR` y `IMPAR, PAR`). ✅
- **Regla propia/agrupada:** propia si ≥ 15 años con ambos en cada mitad; si no, la agrupada (años de ajuste de los 14 del
  núcleo; los de prueba no entran en la agrupada). ✅ Test sintético `test_rectas_propia_y_agrupada` ✅. Rectas propias
  del 1.er intento: C1 en BEL, DEU, FRA, USA; C2 en 10 del núcleo; C5 en BEL, DEU, FRA, USA; C6 en 8. Se publican en el JSON.
- **C4 y S4 sin recta** (`traducir` los pasa tal cual). ✅
- **S5 leído en abril del pico + 1** (`matriz_mensual`: `años = filas["pico"]` para S5, fecha `pico + 1`-04-30), con la
  recta de C2. ✅
- **Unidades:** BIS en % y JST en fracción → la pendiente de C2 sale ≈ 0,005 (0,0054 agrupada; 0,0043-0,0084 propias), es
  decir 0,5 en las mismas unidades (el crédito total del BIS se mueve ≈ el doble que los préstamos bancarios de JST).
  C1 en puntos (b ≈ 0,9-1,07), C5 y C6 en fracción en los dos lados. Coherente. ✅
- ⚠️ **Fuga menor en S5 (T2):** la paridad se aplica a t, pero S5 lee C2 en el pico. En una fila de puerta con t = pico + 1
  (impar), el pico es par, y el par (C2 anual del pico, C2 mensual de abril pico + 1) está en el ajuste de la recta de C2
  de ese pliegue. Es un punto entre ≥ 15 (propia) o ≈ 250 (agrupada), y solo de un indicador: efecto pequeño, pero la
  separación no es estricta para S5. Arreglo posible: separar por la paridad del pico en S5 (no se propone rehacer la puerta).

## 3. Fechado trimestral, `estado_mensual` y B1 en vivo — ⚠️

**Fechado (`fechado_trimestral`) ✅.** d(q) = S(q) − S(q − 1), con S la suma móvil de 4 trimestres (= PIB(q) − PIB(q − 4)).
Entra en el trimestre de la 2.ª caída seguida estando fuera; sale en el de la 2.ª subida seguida estando dentro. Es causal
(cada trimestre solo usa datos ≤ q) y coincide con §3. El test sintético lo cubre. Concordancia publicada (no es puerta):
40/45 entradas y 36/45 salidas JST cazadas a ± 1 año, 8 entradas trimestrales sin recesión JST.

**`estado_mensual` ✅.** El estado del trimestre q se conoce en fin(q) + 75 días (`merge_asof`). "Meses desde la entrada"
y "desde la salida" se cuentan desde el mes de cierre del trimestre de giro. Sin salida previa, se cuenta desde el primer
trimestre con PIB. Si el último estado conocido tiene más de 200 días, `en_rec` = NaN (y la fila no entra ni en "fuera"
ni en "dentro"). Correcto.

**⚠️ S4 no es la de §8 d.** El diseño dice: "% de los otros países con la **suma de 4 trimestres** del PIB real por debajo
de la de 4 trimestres antes", es decir S(q) < S(q − 4). El código (`mensuales`, l. 98) usa
`log PIB(q) − log PIB(q − 4) < 0`, la interanual de UN trimestre. Son cosas distintas: en abril de t + 1 las dos difusiones
correlacionan solo 0,59 (1961-2003, todos los países). Con la de §8 d, T2 **sigue pasando**, con menos margen: r 0,818,
pendiente 0,906 (oficial: 0,878 / 0,943); sin recalibrar, 0,890 / 0,869. **No cambia el veredicto**, pero es una desviación
del diseño fijado y el margen de r pasa de 0,078 a 0,018. La suma de 4 trimestres es además la medida más parecida a la
caída del PIB anual que usa JST. Diff en §9.

**`b1_vivo` frente a `int4.liston`: no son equivalentes (⚠️, no afecta a la puerta).** La puerta usa, por diseño (§8 e),
el B1 de JST en las dos probabilidades; `b1_vivo` solo entra en los percentiles de referencia y en vivo. Comparado en las
filas del modelo, en abril de t + 1 (1962-2003):

| | T1 (525 filas) | T2 (63 filas) |
|---|---|---|
| estado en vivo = estado de la fila (fuera / dentro) | 98,7 % | **69,8 %** |
| "primer año tras el valle" igual | 93 % (corr 0,42) | — |
| log años desde el valle / log duración | corr 0,69 (medias 1,84 / 1,70) | corr 0,85 en las 44 filas que coinciden, igual en el 52 % |

- La definición se corresponde (meses/12 con suelo 1 ↔ años con suelo 1), pero el fechado es otro (PIB total trimestral
  frente a PIB per cápita anual; p. ej. DEU 1990, con la reunificación).
- En T2, 3 de cada 10 filas en recesión según JST están "fuera" según el fechado en vivo. En vivo no se mostraría la
  probabilidad de salir, o se mostraría la de entrar. Y cuando coinciden, la duración difiere en la mitad de los casos.
- La puerta **no mide** este error. Es el mayor error que no se ha medido en la cadena de T2 en vivo.
- Recomendación (sin rehacer la puerta): publicar junto a T2 la concordancia del estado (70 %). Y, como informativo, la
  correlación de p anual con la p mensual que usa B1 en vivo, en las filas donde coinciden los estados.

## 4. Recalibración y validación cruzada (2.º intento) — ✅ (la puerta mide lo que dice §9), con matices ⚠️

- **Solo usa las probabilidades.** `calibrar(pa, pm)` hace la MCO de logit(p anual) sobre logit(p mensual). Ni `f.y` ni
  ninguna rentabilidad entran en `calibrar`, `rectas`, `traducir` ni `puerta`. El objetivo solo entra en `congelar` (el logit
  de INT-4 con todas las filas ≤ 2004, que es el modelo congelado por diseño y es común a las dos probabilidades). ✅
- **Sin fugas entre pliegues:** en cada pliegue, las rectas y (α, β) se ajustan con las filas de la mitad de ajuste
  (`mf`), y la puerta se llena solo con las de la otra mitad (`mg`). Cada fila se predice una vez, con el pliegue que no
  la usó. La única excepción es la de S5 (§2), menor. ✅
- **Reproducido exactamente** con `scripts/val_termometro_sens.py`: T1 190 filas, r 0,7882 / pendiente 0,7943 (no pasa);
  T2 31 filas, r 0,8781 / pendiente 0,9428 (pasa).
- **¿Mide lo que dice §9?** Sí: los mismos umbrales, filas de los dos pliegues juntas, regla de rectas igual y puerta
  propia por país con ≥ 8 filas en total. ✅
- ⚠️ **La recalibración apenas arregla lo que pretendía.** Se ajusta en escala logit, pero la puerta mide la pendiente en
  probabilidad. En T1, β ≈ 1,01 (pares) y 0,84 (impares): la pendiente pasa de 0,68 (sin recalibrar, cruzada) a 0,79, a
  0,006 del umbral. En T2 la recalibración **empeora** el r (0,910 → 0,878), porque (α, β) se ajusta con 13 y 18 filas. T2
  pasaba también sin recalibrar (0,910 / 0,873). No es un error: así estaba fijado.
- ⚠️ **El B1 común infla el r.** Las dos probabilidades llevan el mismo B1 de JST (§8 e). Mirando solo la parte de
  indicadores del logit (Xβ anual frente a Xβ mensual traducida, sin recalibrar), T1 da r 0,870 / pendiente 0,885 y T2,
  0,858 / 0,844. La traducción de los indicadores de T1 es razonable en escala logit; el fallo de T1 en probabilidad viene
  sobre todo de la no linealidad. Es informativo y a posteriori: **no cambia el veredicto** (la puerta fijada es en
  probabilidad).

## 5. Orden de commits y procedencia — ✅ (con la salvedad de siempre ⚠️)

| commit | hora (CET) | contenido |
|---|---|---|
| `e9ec71d` | 12:17:25 | diseño v1.2 (§8) |
| `24979da` | 12:20:33 | código + tests + script del 1.er intento |
| `188cc30` | 12:20:56 | salidas del 1.er intento (procedencia: `24979da`, árbol limpio, 11:20:34 UTC) |
| `a94ac09` | 12:28:56 | diseño v1.3 (§9), con contaminación declarada |
| `eb3c73d` | 12:29:38 | código del 2.º intento (+17 líneas en termometro.py: solo `_lg`, `calibrar`, `aplicar_cal`; el resto, sin tocar) |
| `d9f1291` | 12:30:12 | salidas del 2.º (procedencia: `eb3c73d`, árbol limpio, 11:29:39 UTC) |

- El orden diseño → código → ejecución se cumple en los dos intentos. `procedencia()` aborta con el árbol sucio. Las
  salidas son de commits que solo tocan resultados, bitácora y estado. `trial_log.md` tiene las dos líneas (108-109). Los
  módulos de base (int4, panel, lags, data) no cambian después de 6a2c633 (26-oct).
- ⚠️ Entre el diseño v1.3 y el código pasan 42 segundos, y entre el código y la ejecución, 1 segundo. El código estaba
  escrito antes de commitear el diseño. Las horas prueban el orden de los commits, no que el diseño se fijara antes de
  escribir el código. El 2.º intento se diseñó, además, conociendo el resultado del 1.º (declarado). La compensación
  declarada (mismos umbrales, sin 3.er intento) es razonable. El riesgo que queda es haber elegido el remedio
  (recalibración + cruzada) sabiendo que T2 subiría con más filas.

## 6. T2 con 31 filas y la lista de países — ⚠️ (T2 se puede mostrar, como banda y con avisos) / ❌ (lista de países)

**¿Bastan 31 filas?** Pasa, pero con poco respaldo:
- 31 filas = **22 episodios** (país, pico) en **12 años** (1970, 1974-75, 1980, 1982, 1988, 1990-93, 2002-03). Ningún
  país llega a 8 filas (DEU y USA 6, FIN 4, SWE 3; BEL, ESP, FRA y NOR, 1), así que **todos** dependen solo del agregado.
- Bootstrap por años (2.000 réplicas, 12 bloques): r IC 95 % [0,65; 0,96], pendiente [0,78; 1,16]; **pasa en el 85 %**
  de las réplicas. Por episodio (22 bloques): r [0,70; 0,94], pendiente [0,76; 1,11], pasa en el 89 %.
- Con S4 como dice §8 d, el r baja a 0,818 (§3). Y en vivo se añade un error que la puerta no mide: el estado "en
  recesión" del fechado trimestral coincide con JST en solo el 70 % de las filas de T2 (§3).
- **Opinión del Validador:** la regla fijada se cumple y el veredicto "T2 pasa" se mantiene. Pero la evidencia es de ≈ 20
  episodios agrupados en 4-5 ciclos mundiales. Basta para enseñar la **banda** (bajo/medio/alto/muy alto frente a los
  percentiles, como ya prevé §4), no para leer el número. Propuesta: (i) la probabilidad entre paréntesis, con la nota
  "puerta con 31 filas / 22 episodios; IC 95 % del r 0,65-0,96"; (ii) T2 solo cuando el fechado en vivo lleve ≥ 2
  trimestres en recesión (cuando hay fecha de entrada); (iii) nada por país "con puerta propia", porque no la tiene ninguno.

**DNK y JPN en la lista: confirmado (❌, error de código; no cambia el agregado).**
`paises_con_probabilidad` usa `pasa[g] and v["pasa"] is not False`. "Sin puerta propia" deja `pasa = None`, así que entran
los países con 0 filas. DNK y JPN tienen C6 = NaN (`SIN_BOLSA`, §8: "sin T1 ni T2, solo indicadores"), así que tienen 0 filas
en T1 y T2. Aun así salen en la lista de T2 del veredicto de `termometro_puerta_v2.{json,md}`. El mismo fallo está en
`termometro_puerta.py`, pero allí no se notó porque no pasó nada. En vivo su probabilidad sería NaN, pero la lista oficial
promete algo que el diseño prohíbe. Con la regla corregida, T2 se muestra en **12 países**: BEL, DEU, ESP, FIN, FRA, GBR,
ITA, NLD, NOR, PRT, SWE, USA. Diff en §9. Se propone corregir el JSON/MD con una nota de errata (sin cambiar r ni pendiente).

## 7. ¿Algún error que, corregido, cambie el veredicto? — ✅ No se ha encontrado

Revisados como candidatos:
- S4 fuera de §8 d → T2 sigue pasando (0,818 / 0,906).
- La fuga de S5 por paridad → en la dirección que favorece a la puerta y de tamaño pequeño. No puede hacer pasar a T1, que
  no usa S5. Para que T2 no pasara, el r tendría que bajar más de 0,078 (0,018 con S4 de §8 d). No lo he cuantificado
  rehaciendo los pliegues (§9, diff 3).
- "As of", unidades, regla propia/agrupada, pliegues → correctos.
- Lista de países → error real, pero no toca el r ni la pendiente.

**Ningún error encontrado invierte T1 (no pasa) ni T2 (pasa).** Lo más cercano a un cambio no es un error. Al quitar FIN,
T1 pasaría (0,814 / 0,863, §8). Y la combinación de S4 según §8 d con la fuga de S5 podría acercar T2 al umbral de r. Si se
aplica el diff 2, conviene volver a medir T2 (sería un informativo, no un 3.er intento).

## 8. Sensibilidades a posteriori (no cambian el veredicto)

Script `scripts/val_termometro_sens.py` (commit `ada66e7`, antes de correrlo); salida `research/int/val_termometro_sens.json`.

| sensibilidad | resultado |
|---|---|
| Reproducción de la puerta cruzada | T1 0,788 / 0,794 (190 filas); T2 0,878 / 0,943 (31): idéntica a la oficial |
| T2, bootstrap por años (12 bloques, B = 2.000) | r [0,65; 0,88; 0,96], pendiente [0,78; 0,93; 1,16]; pasa el 85 % |
| T2, bootstrap por episodio (22) | r [0,70; 0,88; 0,94], pendiente [0,76; 0,94; 1,11]; pasa el 89 % |
| T1, bootstrap por años (22) | r [0,64; 0,79; 0,92], pendiente [0,53; 0,80; 1,15]; pasa el 37 % |
| T1, dejando fuera un país | no pasa con 11 de 12 (r 0,768-0,797; pendiente 0,747-0,810); **sin FIN pasa** (0,814 / 0,863). Sin NOR, el peor (0,768 / 0,747). DNK y JPN no aportan filas |
| Sin el B1 común (parte Xβ) | T1 0,870 / 0,885; T2 0,858 / 0,844 |
| S4 según §8 d | T2 0,818 / 0,906 (sin recalibrar 0,890 / 0,869); corr con la S4 del código 0,59 |
| B1 en vivo frente a JST | ver §3 |

Lectura: T1 está en el borde (un país, FIN, decide; el 37 % de las réplicas pasa), y el "no pasa" fijado es legítimo.
T2 pasa en la mayoría de las réplicas, pero con una base estrecha.
