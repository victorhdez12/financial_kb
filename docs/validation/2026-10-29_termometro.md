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
