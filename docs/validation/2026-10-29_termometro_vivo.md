---
documento: validación de la parte EN VIVO del termómetro de recesión informativo
fecha: 2026-10-29
autor: Validador independiente (rama val-vivo, worktree financial_kb_int3b); no ha escrito este código
objeto: src/report/termometro_vivo.py, scripts/termometro_vivo.py, tests/test_termometro_vivo.py,
  research/int/termometro_vivo_ultimo.json (código en `aa72ed2`)
contexto: docs/int/TERMOMETRO_diseno_v1.md (§1-4, §8, §9), src/intl/termometro.py, scripts/termometro_puerta_v2.py,
  research/int/termometro_puerta_v2_corr.json (`final`), docs/validation/2026-10-29_termometro.md
método: lectura del código; reproducción con el warehouse real (fechas ≤ 2004, código de desarrollo sin redondeo frente
  al módulo en vivo con el JSON); pruebas sintéticas de "as of" estricto y de series que faltan o se cortan; bootstrap
  de la puerta de T2 con la S4 corregida (para el texto del aviso). Scripts del Validador fuera del repo (scratchpad):
  no se ha tocado el módulo.
---

# Validación del termómetro en vivo

## Veredicto global

(se completa al final)

## 1. Nada de JST, nada reajustado con datos ≥ 2005, parámetros solo del JSON congelado — ✅ (con un matiz ⚠️)

- **Lectura de datos.** El único acceso al warehouse es `_serie` (l. 104-113): rechaza todo `jst_*` y todo lo que no esté
  en `D.FAMILIAS` antes de consultar (`FactorCutoffError`). `cargar` solo pide `oecd_{irlt,ir3m,share}_*`,
  `oecd_cpi_*_idx`, `oecd_gdpq_*` y `bis_creditgap_*_ratio`. No se llama a `load_dev`, `P.anual`, `P.mensual` ni a nada
  que lea JST; `P._mensual_completa`, `Lg.asof` y las funciones de `T` no tocan la base. ✅
- **Parámetros.** `parametros()` lee solo `final` de `termometro_puerta_v2_corr.json` (modelo T2, `cal` T2, `rectas`,
  percentiles p50/p80/p95 de T2) y el veredicto. Falla explícitamente si falta algo, si T2 no consta aprobado o si T1 no
  consta como NO aprobado. En el módulo no hay ninguna llamada a `logit_fit`, `congelar`, `rectas`, `calibrar` ni
  `polyfit`. ✅
- **Redondeo del JSON.** Medido con el código de la puerta sin redondear (≤ 2004): coeficientes de T2 a ≤ 4e-5;
  (α, β) = (0,03097; 0,94830) frente a (0,031; 0,9483); pendientes de las rectas a ≤ 0,03 % salvo **C2: 0,93 %** de error
  relativo (lo que ya declara el docstring). Efecto máximo en la probabilidad de T2 mes a mes, 1960-2004: **5,3e-4**. ✅
- ⚠️ **Referencias ≤ 2004 que no están congeladas.** El percentil histórico de cada indicador y el "centro" de las
  contribuciones (media de [B1, S1-S5] en los meses en recesión 1960-2004) se recalculan en cada ejecución con
  `obs_latest`. No usan datos ≥ 2005 (la rejilla ≤ 2004 solo ve datos disponibles antes de 2005-01; comprobado que el
  bloque mensual con corte 2004-12 es idéntico al de desarrollo), pero **no están congelados**: si una recarga del
  warehouse revisa la historia OCDE/BIS, cambian sin aviso. No es un reajuste del modelo (no cambian ni la probabilidad
  ni la banda), pero rompe la promesa "todo lo ≤ 2004 queda fijo". Propuesta (diff 5): congelarlos una vez en un JSON
  con procedencia, o fijar en un test su huella (centro medido hoy: B1 0,1531; S1 0,3638; S2 −0,0049; S3 0,1470;
  S4 0,2905; S5 0,1234).

## 2. "As of" en vivo igual que en desarrollo, sin mirar el futuro — ✅ (con dos avisos ⚠️)

- **Mismas reglas.** Mensuales: `P._mensual_completa` + `Lg.asof` (fin de mes + 1 día tipos y bolsa, + 45 días IPC,
  más viejo que 120 días = ausente) — las mismas funciones que `panel.mensual`. Trimestrales: `T.asof_q` (BIS + 183 días,
  PIB + 75, máximo 200 días) y `T.estado_mensual` (fechado conocido 75 días tras el trimestre). La única diferencia con
  desarrollo es que `_serie` corta en la fecha de cálculo en lugar de 2004-12. El test con corte 2004-12 lo confirma
  (bloque mensual y PIB idénticos a `load_dev`/`load_dev_curado`). ✅
- **Prueba estricta del Validador (sintética):** con fecha 2026-03-31 se multiplican por 3 los datos con fecha ≤ corte
  que todavía no se conocen ese día (tipos y bolsa de marzo, IPC de febrero y marzo, PIB 2026T1 × 0,5, BIS 2025T4 × 3) →
  **resultado idéntico byte a byte**. Y al revés, cambiar el tipo a 10 años de febrero (ya conocido) sí cambia C1
  (3,17 → 3,59). ✅
- **Hoy (2026-10-29 → fecha de cálculo 2026-09-30):** tipos y bolsa de agosto, IPC de julio, BIS 2026T1
  (31-mar + 183 = 30-sep, justo), PIB 2026T2 (30-jun + 75 = 13-sep). Comprobado en el warehouse. ✅
- ⚠️ **Hasta un mes de retraso evitable.** La fecha de cálculo es el último fin de mes ≤ la fecha pedida: el 29-oct se
  ignoran los tipos y la bolsa de septiembre y el IPC de agosto, ya publicados. No es mirar el futuro (es lo prudente y
  coincide con la rejilla de desarrollo), pero el reporte semanal irá hasta 4 semanas por detrás. El título del Markdown
  dice la fecha de cálculo; conviene decirlo en palabras ("datos conocidos al 30-sep-2026").
- ⚠️ **Arrastre de datos viejos dentro de las medias de 12 meses** (heredado de desarrollo, no nuevo): un tipo que deja de
  publicarse se repite hasta 120 días en la curva "as of", y C1 (media de 12 meses con ≥ 9) puede salir calculada con
  3-4 meses repetidos. Con la GBR real: el tipo a 3 meses acaba en 2026-02; en julio-agosto la C1 de GBR aún salía,
  con marzo-mayo iguales a febrero; en septiembre ya sale vacía. Es la regla de desarrollo; solo falta decirlo (§6).

## 3. Misma traducción, recalibración y bandas que el desarrollo — ✅ (reproducido mes a mes)

- **Código compartido.** `calcular` usa `T.mensuales`, `T.traducir` con las rectas del JSON, `T.fechado_trimestral`,
  `T.estado_mensual`, `T.b1_vivo(·, "T2")`, `M.logit_pred` y `T.aplicar_cal`. `prob_salida` construye S5 igual que
  `referencia_cal` de `scripts/termometro_puerta_v2.py` (C2 traducida en el primer mes conocido en recesión, arrastrada
  mientras dura). Las bandas usan p50/p80/p95 de `final.percentiles_referencia.T2` con los cortes de §4
  (< p50 bajo; [p50, p80) medio; [p80, p95) alto; ≥ p95 muy alto). ✅
- **Reproducción del Validador** (warehouse real): probabilidad de desarrollo con el código de la puerta **sin redondear**
  (rectas y recalibración con todos los años ≤ 2004, `load_dev`) frente a `V.termometro(con, fecha)` con el JSON:

| fecha | país | en vivo (JSON) | desarrollo, JSON | desarrollo, sin redondear | banda vivo / desarrollo |
|---|---|---|---|---|---|
| 1975-06-30 | DEU | 0,785 | 0,7849 | 0,7849 | bajo / bajo |
| 1975-06-30 | USA | 0,625 | 0,6249 | 0,6248 | bajo / bajo |
| 1981-01-31 | USA | 0,824 | 0,8244 | 0,8244 | medio / medio |
| 1991-04-30 | FIN | 0,265 | 0,2653 | 0,2654 | bajo / bajo |
| 1992-10-31 | FIN | 0,200 | 0,1995 | 0,1996 | bajo / bajo |
| 1992-10-31 | GBR | 0,634 | 0,6338 | 0,6343 | bajo / bajo |
| 1992-10-31 | SWE | 0,237 | 0,2366 | 0,2367 | bajo / bajo |
| 1993-04-30 | FIN | 0,873 | 0,8732 | 0,8733 | medio / medio |
| 1993-04-30 | SWE | 0,662 | 0,6620 | 0,6622 | bajo / bajo |
| 2003-06-30 | PRT | 0,412 | 0,4118 | 0,4116 | bajo / bajo |

  Diferencia máxima JSON frente a sin redondear en todos los meses en recesión 1960-2004 del núcleo: 5,3e-4. Percentiles
  sin redondear: 0,81599 / 0,90683 / 0,95521 (JSON: 0,816 / 0,9068 / 0,9552). Ninguna banda cambia. ✅
- En esas mismas fechas, DNK y JPN salen "sin bolsa mensual", los de prueba "sin puerta propia" y GBR/ITA/PRT de los
  setenta "falta algún indicador" (sin tipo a 3 meses OCDE): coherente con desarrollo.

## 4. T1 nunca, T2 solo en los 12 países y solo en recesión — ✅

- **T1:** el módulo no calcula ninguna probabilidad de entrar (no lee `modelo.T1` ni `cal.T1`; no hay ninguna clave de
  entrada en la salida). `parametros()` exige que T1 conste como NO aprobado. ✅
- **Lista de T2:** `paises_T2 = [c in NUCLEO si c en veredicto.paises_con_probabilidad.T2 y c ∉ SIN_BOLSA]` → BEL, DEU,
  ESP, FIN, FRA, GBR, ITA, NLD, NOR, PRT, SWE, USA (test). Doble filtro: aunque el JSON volviera a traer DNK/JPN, no
  entrarían. ✅
- **Solo en recesión:** `salida_12m` solo se rellena si `en_rec` del último mes es 1 según el fechado trimestral en vivo
  (`estado_mensual`); `prob_salida` pone NaN fuera. DNK/JPN en recesión → motivo "sin bolsa mensual"; AUS/CHE/CAN/IRL →
  "país de prueba: sin puerta propia de T2". Visto en el test sintético y hoy con IRL real. ✅
- "En recesión" exige ya dos caídas seguidas de la suma de 4 trimestres (la recomendación (ii) del Validador anterior
  queda cubierta por la propia regla de entrada).

## 5. Contribuciones al logit y percentiles de los indicadores — ✅ cálculo / ⚠️ empates

- **Contribuciones:** `b_k · (x_k − centro_k)` con k = B1, S1-S5 (`b_T2[1:]`, 6 coeficientes, en el orden de la matriz
  Z). Comprobado en FIN 1992-10: b0 + b·centro + Σ contribuciones = logit sin recalibrar (−1,4977, igual a 1e-15), y
  σ(α + β·logit(σ(·))) = la probabilidad publicada (0,1995). Como β = 0,948 > 0, el signo de la contribución es el signo
  del efecto sobre la probabilidad recalibrada; y = 1 es "sale" en `int4.obj_salida`, así que "a favor de salir" es
  correcto. Centro: meses 1960-2004 en recesión, con probabilidad finita, de los 12 países de T2. ✅ (referencia ≤ 2004;
  ver el matiz de §1 sobre que no está congelada).
- **Percentiles:** `(h ≤ v).mean()` frente a los meses 1960-2004 del propio país, sin traducir, con ≥ 60 meses (si no,
  "—"). Comprobado a mano: USA C1 = 0,50 pp → 43,9 % → p44. ✅
- ⚠️ **Empates en C4 y S4 (difusiones discretas).** Con "≤", un valor muy repetido queda en lo alto de su bloque de
  empates. S4 = 0 % (ningún otro país con PIB cayendo) aparece como **p60** en los 18 países, porque el 59,7 % de los
  meses 1960-2004 tienen S4 = 0 y ninguno < 0: el lector entiende "por encima de la mediana" cuando es el valor mínimo
  posible. C4 = 8,33 % sale p36 (29,6 % < y 36,3 % ≤). Propuesta (diff 3): rango medio, `((h < v).mean() + (h <= v).mean())/2`
  → S4 = 0 daría p30, o decir "mínimo (como en el 60 % de los meses)".
- Menor: B1 (duración) entra como una "variable" más en "lo que más pesa"; es correcto, pero en los primeros 12 meses de
  recesión B1 = 0 y siempre restará frente a un centro de 0,15 (el modelo cree que las recesiones recién empezadas salen
  menos): conviene que el texto lo diga como "duración aún corta" en vez de una variable de indicador.

## 6. Robustez ante series que faltan o se cortan — ⚠️ (no miente, pero calla el porqué; un caso tumba todo)

Pruebas sintéticas del Validador (warehouse en memoria de los tests) y caso real:

| caso | qué pasa | juicio |
|---|---|---|
| GBR real: `oecd_ir3m_gbr` acaba en 2026-02 | C1 (y C5/S2) de GBR = "—" desde sep-2026; C4 de los demás pasa a contar 12 países sin decirlo; si GBR entrara en recesión, "falta algún indicador de T2 este mes" | ⚠️ silencio sobre la causa; GBR pierde T2 indefinidamente sin que el reporte lo diga |
| tipo a 3 meses de ESP cortado en 2026-03, ESP en recesión | C1 "—", salida "falta algún indicador de T2 este mes" | ⚠️ no dice cuál ni desde cuándo |
| falta entera `oecd_share_usa`, `oecd_ir3m_usa`, `oecd_cpi_usa_idx` o `bis_creditgap_us_ratio` | el indicador afectado sale `None`/"—", el resto se calcula | ✅ no inventa, ⚠️ no avisa |
| falta entera `oecd_gdpq_esp` | **excepción `ValueError: start and end must not be NaT`** en `T.mensuales` (`_rejilla_q` de una serie vacía): no sale nada para ningún país | ❌ falla ruidosa pero críptica, y un país sin PIB tumba los 18 (`calcular` ya prevé `pib` vacío en el bucle de estados, pero `mensuales` no) |
| warehouse sin actualizar (mensual hasta 2026-03, PIB hasta 2025T4), fecha 2026-10-29 | sigue "en recesión" con el PIB de 2025T4 (198 días < 200); C6 "—"; C1 sale con meses repetidos; ningún aviso de datos viejos (solo "(2025Q4)" en la columna) | ⚠️ |
| fecha futura (2030-01-15) | calcula 2029-12-31: todo "sin dato" / "—", sin error ni aviso | ⚠️ menor |

- Lo bueno: nunca rellena con datos inventados ni muestra una probabilidad con un indicador ausente (NaN se propaga y
  `prob_salida` exige todo). La columna "(último PIB)" deja ver un PIB viejo.
- Lo que falta para el reporte semanal (diff 2): (a) que `mensuales` acepte un país sin PIB (o que `cargar` lo excluya
  con un aviso explícito), en vez de abortar todo; (b) por país, la última fecha conocida de cada serie y una lista
  `avisos_datos` ("GBR: tipo a 3 meses sin datos desde 2026-02 → sin curva ni T2"), que el Markdown imprima; (c) el motivo
  de "falta algún indicador" con el nombre del indicador; (d) un aviso global si la fecha pedida está más de ≈ 45 días
  por delante del último dato mensual del núcleo.
- **Acción de datos (fuera de este módulo):** comprobar por qué `oecd_ir3m_gbr` se corta en 2026-02 (cambio de
  dataset/clave en la OCDE o del ingest). Sin ella, GBR —uno de los 12 de T2— no puede mostrar probabilidad de salir.

## 7. Texto de los avisos — ⚠️ / ❌ (una cifra del aviso de T2 es de la versión anterior)

- `AVISO` ✅: "Informativo, no es una señal de cartera", modelo 1871-2004, T1 no pasó → solo indicadores, T2 con pocas
  filas, la inflación no se anticipa. Se aparta del texto fijo de §4 (que citaba AUC 0,73/0,77) solo en lo que obliga el
  veredicto (T1 no pasa); aceptable.
- `AVISO_NIVEL` ("nivel no calibrado en vivo") ✅ y "Léase la banda, no el porcentaje" ✅ (lo pedido en el diff 4 anterior).
- ❌ **El intervalo del r en `AVISO_T2` no corresponde al r que cita.** Dice "r 0,82, IC 95 % ≈ [0,65; 0,96]". El 0,82 es
  la puerta corregida (S4 de §8 d: 0,8183 / 0,9064, reproducido aquí), pero [0,65; 0,96] es el bootstrap de la versión
  ANTERIOR (S4 errónea, r 0,878). Rehecho por el Validador con el código actual (mismo `boot`, 2.000 réplicas, semilla 0):
  - por años (12 bloques): **r IC 95 % [0,49; 0,94]**, pendiente [0,54; 1,08]; **pasa en el 58 %** de las réplicas
    (antes 85 %);
  - por episodio (22): r [0,51; 0,91], pendiente [0,61; 1,05]; pasa en el 59 %.
  El aviso hace parecer la evidencia más sólida de lo que es. Corrección de texto (diff 1). "31 filas / 22 episodios"
  ✅; "≈ 70 %" de coincidencia del estado ✅ (no depende de S4).
- ⚠️ El Markdown dice "su percentil frente a los meses 1960-2004 del propio país": para C4 y S4 es la difusión vista desde
  ese país (los otros del núcleo) y tiene el problema de empates de §5.
- ⚠️ Las bandas de T2 son relativas a meses en recesión (p50 = 0,82): "bajo" con 0,78 de probabilidad de salir puede leerse
  como "la recesión sigue". El texto ya dice "banda frente a los meses en recesión 1960-2004"; conviene añadir "más alto =
  más probable salir" en la línea de cada país.
- ⚠️ `scripts/termometro_vivo.py` usa `procedencia(exigir_limpio=False)`: la salida commiteada en `aa72ed2` venía de
  `4d091c7` con el árbol sucio. Para el reporte es aceptable (es informativo y queda anotado), pero el JSON del reporte
  semanal debería generarse con el árbol limpio o marcarlo en el Markdown.

## 8. ¿Prueban los tests lo que dicen? — ⚠️

9 tests, todos pasan (4,2 s).

| test | ¿lo prueba? |
|---|---|
| `test_estado_y_probabilidad_solo_en_recesion` | ✅ estado, fecha de cálculo, último trimestre, motivos de DNK/AUS, nada fuera de recesión |
| `test_contribuciones_suman_al_logit` | ❌ **el nombre promete la suma y solo comprueba que `empuja_mas` es el máximo en valor absoluto**. La suma es correcta (medida aquí), pero el test no la mide (diff 4) |
| `test_markdown` | ✅ avisos, sin DNK en la lista de probabilidades, EE. UU. una vez |
| `test_no_mira_el_futuro` | ⚠️ débil: altera solo datos con fecha > 2026-03-01, que el filtro SQL `date ≤ corte` ya excluye. No prueba los retrasos (datos con fecha ≤ corte aún no publicados). La versión estricta del Validador (§2) pasa; conviene añadirla (diff 4) |
| `test_nunca_jst` | ✅ para `_serie`; no comprueba que `cargar` no pida nada fuera de OCDE/BIS (estructural, aceptable) |
| `test_bandas_y_fin_de_mes` | ✅ |
| `test_parametros_incompletos` | ✅ lista de 12 países, recta que falta, T2 no aprobado |
| `test_fuera_de_src_intl` | ✅ |
| `test_corte_2004_reproduce_desarrollo` | ✅ bloque mensual y PIB idénticos; percentiles de T2 a 5e-4. ⚠️ el docstring habla de "diferencia máxima por mes ≈ 5e-4", que el test no comprueba (lo he medido: 5,3e-4) |

Faltan: un test de serie que falta/se corta (que hoy revelaría el ❌ del PIB vacío) y uno de empates en percentiles.

## 9. Ejecución de hoy (2026-10-29) y si tiene sentido — ✅

`.venv/bin/python -m scripts.termometro_vivo` con el árbol limpio en `aa72ed2`: idéntico a la salida commiteada salvo
la procedencia (antes `4d091c7`, árbol sucio; ahora `aa72ed2`, limpio). No se ha commiteado la salida regenerada.

- **Fecha de cálculo 2026-09-30.** Ningún país del núcleo está en recesión según el fechado trimestral (último PIB
  2026T2 en los 18) → **no se muestra ninguna probabilidad**, lo que es correcto (T1 no pasó; T2 solo en recesión).
- **IRL "en recesión" desde 2026T1** (país de prueba → solo indicadores). Viene del PIB irlandés: 2025T1 536.883 →
  2026T1 465.102 (−13 %), el efecto de las multinacionales (exportaciones farmacéuticas adelantadas a 2025T1). La regla lo
  marca bien; económicamente es ruido del PIB irlandés. Que sea país de prueba y no muestre nada es lo prudente.
- **Indicadores:** curvas positivas en todos menos NOR (−0,17 pp, p61: Noruega tuvo a menudo curva invertida antes de
  2005); C4 = 1 de 12-13 países con curva invertida (NOR); bolsa real 12 m alta (p54-p92); **Δ5 años crédito/PIB muy
  negativo en todos (p0-p19; NLD −80 pp, IRL −76, ESP −53)**. Comprobado en el BIS: NLD 343 % (2021T1) → 263 % (2026T1).
  Es la caída del ratio por el PIB nominal de 2021-2025, algo casi sin precedente antes de 2005 (de ahí el p0). Con el
  signo de T1 (más crédito = más riesgo), lectura de riesgo bajo. S4 = 0 % en todos (ningún PIB de 4 trimestres cae),
  mostrado como p60 por los empates (§5).
- GBR sin curva (tipo a 3 meses cortado, §6); JPN y CHE sin percentil de la curva (< 60 meses antes de 2005); AUS sin
  percentil de bolsa (sin historia ≤ 2004 de `oecd_share_aus`). Coherente con los datos.
- Lectura global: un cuadro tranquilo (ningún país del núcleo en recesión, curvas positivas, bolsa fuerte, desapalancamiento).
  Tiene sentido; lo que menos sentido tiene a la vista es el "p60" de S4 = 0.

## 10. Diffs propuestos (no aplicados)

**Diff 1 — `AVISO_T2` con el intervalo de la puerta corregida (❌, bloquea).** `src/report/termometro_vivo.py`:
```diff
-AVISO_T2 = ("Léase la banda, no el porcentaje: la puerta de T2 se pasó con solo 31 filas / 22 episodios (r 0,82, IC 95 % "
-            "≈ [0,65; 0,96]), y el «en recesión» del fechado trimestral coincide con el anual de JST solo ≈ 70 % de las "
-            "veces.")
+AVISO_T2 = ("Léase la banda, no el porcentaje: la puerta de T2 se pasó con solo 31 filas / 22 episodios (r 0,82, IC 95 % "
+            "≈ [0,49; 0,94]; pasa en ≈ 6 de cada 10 réplicas bootstrap), y el «en recesión» del fechado trimestral "
+            "coincide con el anual de JST solo ≈ 70 % de las veces.")
```
(Bootstrap del Validador con la S4 corregida, `scripts/val_termometro_sens.boot`, 2.000 réplicas por años, semilla 0.)

**Diff 2 — series que faltan: no abortar y decirlo (❌ el PIB vacío; ⚠️ el resto; bloquea la parte a).**
```diff
 def cargar(con, fecha):
     ...
-        pib[c] = _serie(con, f"oecd_gdpq_{lc}", corte)
+        if not (q := _serie(con, f"oecd_gdpq_{lc}", corte)).empty:
+            pib[c] = q          # sin PIB: sin estado ni S4 propios; aviso en calcular, no excepción
     ...
+def avisos_datos(con, corte) -> list[str]:
+    """Por país y serie: último dato con fecha ≤ corte; aviso si su disponibilidad (lags) es > MAX_VIEJO antes de corte."""
```
y en `calcular`: `estado["sin_pib"]`, `salida["motivo"] = f"falta {nombre} este mes"` (comprobar `np.isfinite(Z2[c][i])`
por columna) y un bloque `> [!warning] Datos` en `markdown` con la lista de avisos (p. ej. "GBR: tipo a 3 meses sin datos
desde 2026-02 → sin curva, sin Δ tipo real, sin T2").

**Diff 3 — percentil con rango medio (⚠️).**
```diff
-    return int(round(float((h <= v).mean() * 100))), int(len(h))
+    return int(round(float(((h < v).mean() + (h <= v).mean()) / 2 * 100))), int(len(h))   # rango medio: empates de C4/S4
```

**Diff 4 — tests.** (a) `test_contribuciones_suman_al_logit`: comprobar de verdad la suma
```python
    z = ...  # Z del último mes (exponer Z o recomputar con V.prob_salida)
    assert b[0] + b[1:] @ centro + sum(c.values()) == pytest.approx(logit(p_sin_recal), abs=1e-3)
```
(b) `test_no_mira_el_futuro_estricto`: alterar con `update` los datos con fecha ≤ 2026-03-31 aún no publicados (tipos de
marzo, IPC feb-mar, PIB 2026T1, BIS 2025T4) y exigir salida idéntica; y que alterar febrero (tipos) sí la cambie.
(c) `test_falta_pib_de_un_pais`: borrar `oecd_gdpq_esp` → el resto se calcula y ESP sale "sin dato" con aviso.
(d) `test_percentil_empates`: S4 = 0 con 60 % de ceros → p30.

**Diff 5 — congelar las referencias ≤ 2004 (⚠️).** Guardar una vez (script con procedencia, árbol limpio) el centro de las
contribuciones y, por país e indicador, los cuantiles 1960-2004 (o el vector ordenado) en
`research/int/termometro_vivo_referencias.json`; `calcular` los lee en lugar de recalcularlos, y un test comprueba que
recalcularlos con `obs_latest` da lo mismo (si no, la recarga del warehouse ha revisado la historia: se avisa, no se
cambia en silencio).
