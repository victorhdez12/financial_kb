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
