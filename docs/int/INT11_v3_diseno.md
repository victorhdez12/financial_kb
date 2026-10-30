---
documento: INT-11 v3 — motor de escenarios: arreglos de la validación v2, pertenencia suave, época, eventos y potencia
version: 0.1 (2026-10-30)
estado: DISEÑO + CÓDIGO + POTENCIA SINTÉTICA. Nada de v3 se ha evaluado con datos reales; ningún resultado real se ha
        cruzado con el régimen en esta fase. El periodo ≥ 2005 sigue BLOQUEADO y sin gastar.
parte_de: docs/int/INT11_v2_diseno.md (v2), docs/int/INT11_prerregistro_v2.md (v2 congelado), research/int/int11_v2_resultado.md
          (corrida única v2), docs/validation/2026-10-30_int11v2.md (validación v2), docs/int/INT14_eventos_v0.md §6
codigo: src/intl/escenarios.py (Config.v3, pesos_estado, simular_suave, eventos), src/intl/int11v3.py (sintético),
        src/report/registro_vivo.py + src/report/escenarios_vivo.py (registro en vivo), scripts/int11_v3_c_suavizado.py,
        scripts/int11_v3_potencia.py, tests/test_intl_int11_v3.py
resultados_sinteticos: research/int/int11_v3_c_suavizado.json, research/int/int11_v3_potencia_P{0,1,2}.json
prerregistro: borrador docs/int/INT11_prerregistro_v3_v0.md
---

# INT-11 v3: abanicos fiables también cerca de las fronteras y cuando el mundo cambia

## 0. En una frase
v2 pasó su puerta, pero el validador encontró **por qué sigue algo estrecho** (los países volátiles se encogen de más,
el "4" del ensanchamiento no estaba guardado y da algo menos de 90 %) y **dos fragilidades** (la frontera dura del 3 %
hace saltar P(inflación > 5 %) de 0,07 a 0,5 por décimas de punto, y la bolsa cambia de época). v3 arregla cada causa
con un mecanismo fijado **antes** de mirar datos, añade **eventos** (petróleo, crisis, pico de volatilidad) como estados
opcionales del Monte Carlo y repara el **registro en vivo**.

**Idea clave para aprender:** "fiable" no es solo "acierta el 90 % de media". Es acertar el 90 % también en los casos
difíciles: países volátiles, regímenes raros, países **justo en la frontera** entre dos regímenes y épocas distintas de
aquella con la que se estimó. v3 ataca uno por uno esos casos.

## 1. Qué arregla v3 y de dónde sale cada número
| hallazgo (validación v2) | arreglo v3 | parámetro | origen del valor |
|---|---|---|---|
| 1. La curtosis AGRUPADA (16,8 en bolsa) encoge de más a los volátiles (FIN 81 %, PRT 85 %, JPN 86 %) | curtosis **por país**, estandarizada y encogida hacia la del panel | `curtosis_escala="pais"`, `n0_curtosis` = 50 | a priori (§2.1) |
| 5. El "4" de c sale de un sintético no guardado y da 0,892-0,894 con n = 20 | experimento **en el repo**, regla fijada antes de correrlo | `c_suavizado` = **5,25** | sintético (§2.3) |
| 4. Frontera dura del 3 %: 7/14 países a < 0,5 pp; P(infl > 5 %) salta 0,07 ↔ 0,5 | **pertenencia suave** al régimen de partida (inflación Y brecha) | `sigma_infl` = 0,5 pp, `sigma_brecha` = 1 pp | a priori (incertidumbre de medida, §2.2) |
| 7(iv). Temporal bolsa 81,6 % (no estacionariedad) | **semivida por época**: lo reciente pesa más; el suavizado usa el n efectivo | `semivida_epoca` = 50 años | a priori (§2.4) |
| 3. Registro en vivo: la 2.ª emisión aborta; se puede emitir con fecha atrasada (fuga) | sin reescribir "hoy", árbol sucio solo en el registro, rechazo de fechas atrasadas, vintages, huella | — | §2.5 |
| 2. La tolerancia ±1,5 pp es más laxa que la banda nula | puerta D de v3 con la **banda nula** (unilateral por abajo) | — | borrador de prerregistro §4 |

`Config()` reproduce v1 y `Config.v2()` reproduce v2 **bit a bit** (tests `test_config_por_defecto_reproduce_v1_bit_a_bit`
y `test_config_v2_reproduce_v2_bit_a_bit`): todo lo nuevo está apagado por defecto. `Config.v3()` lo enciende.

## 2. Arreglos del motor

### 2.1 Curtosis por país en el error de medida del factor de escala
- v2: el factor de dispersión del país f̂_c tiene error se² = (κ + 2)/(4 n_c) con κ = exceso de curtosis de la
  desviación **de todo el panel**. Si los países tienen escalas distintas, la mezcla tiene colas más gordas que cada
  país (una mezcla de normales con varianzas distintas no es normal): κ sale 16,8 en bolsa en vez de ≈ 4. Con más error
  supuesto, el Bayes jerárquico se fía menos del dato del país y lo arrastra hacia la media: DEU 1,59 → 1,08.
- v3: z = desviación / dt **del propio país**; κ_c = curtosis de z en el país; κ̄ = la de todos los z juntos (ya sin
  mezcla de escalas). Encogimiento: κ_c* = (n_c·κ_c + n0·κ̄)/(n_c + n0), n0 = 50. Por qué encoger: la curtosis de 100
  datos tiene un error enorme (≈ √(24/n) ≈ 0,5 con normales, mucho más con colas gordas); n0 = 50 da a un país típico
  (≈ 110 años) un peso de ≈ 2/3 a su propia curtosis. Valor elegido por esa regla de error, no por resultados.
- Test sintético: choques normales, un país 2,5 veces más volátil: curtosis agrupada 3,8, por país 0,5; el factor
  posterior del volátil pasa de 1,53 a 1,60 (más cerca de su valor) y su peso del dato propio B = 0,90.

### 2.2 Pertenencia suave al régimen de partida (inflación y brecha)
- El régimen operable es una regla dura: inflación > 3 % y brecha < 0. Pero la inflación que vemos es una **medida**
  (IPC de la OCDE frente al de JST, media anual frente a 12 meses móviles, revisiones; un mes interpolado en EE. UU.) y la
  brecha también (revisiones del PIB, población extrapolada: sesgo de +2,7 pp en ESP según la validación). Un país a
  +0,1 pp del umbral no "está" en sobrecalentamiento con certeza.
- v3: P(alta) = Φ((π − 3 %)/σπ), P(baja) = Φ(−brecha/σb), independientes; pesos de los 4 regímenes = productos
  (`E.pesos_estado`). La predictiva es la **mezcla** de las predictivas de cada régimen de partida. El motor se estima
  igual (régimen duro en el entrenamiento); los regímenes FUTUROS siguen la cadena de Markov.
- σπ = 0,5 pp y σb = 1 pp: incertidumbre de medida/definición fijada a priori (diferencias IPC OCDE-JST y de
  definición ≈ 0,25-0,5 pp; revisiones del PIB real ≈ 0,5-1 pp y la población extrapolada ≈ 1-3 pp en la brecha per
  cápita). La validación v2 probó 0,25 y 0,5 pp en sintético (§5.4): misma calibración global, Brier cerca del umbral
  −12 % / −17 %. Se elige 0,5 por ser el extremo alto de la incertidumbre de medida razonable (decisión D1).
- `gen.simular_suave(pais, inflacion, brecha)`: cada lote reparte sus trayectorias entre regímenes en proporción a los
  pesos (resto mayor, sin azar extra: con pesos puros es **idéntico** a `simular` del régimen). Salida nueva
  `Escenarios.inicio` (régimen de partida de cada trayectoria) y `meta["estado_observado"]`.
- Lo que NO arregla (validación v2): el sesgo de nivel cerca del umbral (p media 0,29 frente a frecuencia 0,22).
  Haría falta condicionar en la inflación continua (núcleo sobre π_{t−1}): cambio mayor, no incluido.

### 2.3 La constante de ensanchamiento, re-derivada y guardada
- Mecanismo (sin cambios desde v2): a cada valor sorteado se le suma ruido t5 × dt de la celda × √(c/n): la varianza
  predictiva pasa a (1 + c/n)·var. Corrige que el p5-p95 de una muestra pequeña es estrecho (con n = 20, ≈ 85 %).
- **Regla, fijada antes de correr** (src/intl/int11v3.py): c* = el menor c de la rejilla 0-12 (paso 0,25) con cobertura
  del p5-p95 ≥ 0,90 en n = 20 **y** n = 34 (tamaños de las celdas raras), t con ν = 4,5, 20.000 réplicas por n,
  reproduciendo el mecanismo del motor (bootstrap bayesiano 20 × 200 + ruido t5). Resultado (commit 3221034, 58 s):

| c | 0 | 4 (v2) | 5 | **5,25** | 6 | 8 |
|---|---|---|---|---|---|---|
| n = 20 | 0,855 | 0,895 | 0,900 | **0,902** | 0,905 | 0,914 |
| n = 34 | 0,875 | 0,894 | 0,899 | **0,900** | 0,903 | 0,910 |

  Sensibilidad (c = 5,25): ν = 3,5 → 0,894 / 0,897; ν = 6 → 0,900 / 0,898; normal → 0,903 / 0,903; n = 65 → 0,902;
  n = 150 → 0,897 (MC ± 0,004). Coincide con la reproducción del validador (c = 4: 0,892-0,894 en n = 20).
- Con la semivida (§2.4), el n de la fórmula es el **n efectivo de Kish** de la celda ((Σw)²/Σw²): menos datos
  efectivos → más ensanchamiento, de forma automática.

### 2.4 No estacionariedad: semivida por época
- La bolsa después de 1950 no se mueve como antes (temporal v1 80,5 %, v2 81,6 %). La confirmación (entrena ≤ 2004,
  prueba 2005-2020) es justo un diseño temporal, así que es el riesgo principal.
- v3: cada fila pesa 0,5^((año_ref − año)/50) en el sorteo (año_ref = último año del entrenamiento): una fila de 1954
  pesa la mitad que una de 2004, una de 1904 un cuarto. Se aplica al bootstrap (y al modo t vía los pesos) y la dt y el
  n de Kish de cada celda se calculan con esos pesos (§2.3). El factor de escala por país no se pondera.
- Por qué semivida y no "cortar en 1950" o "inflar × k": 1950 es justo el corte en el que se vio el fallo (elegirlo
  sería usar el resultado); inflar exige medir cuánto, y medirlo en ≤ 2004 sería ajustar al fallo visto. Una semivida
  genérica de 50 años (≈ dos generaciones de mercado; n efectivo ≈ 75-85 % del real) se fija sin mirar nada.
- Lo que NO arregla: si la época futura es distinta de TODO el pasado, nada estimado con el pasado lo corrige. En el
  diseño temporal de desarrollo (< 1950 → 1950-2004) la semivida no puede ayudar (pondera 1900-1949, que no informa
  de lo posterior): la potencia (§5) lo muestra.

### 2.5 Registro en vivo (docs/int/INT11_registro_vivo.md v0.2)
- La emisión con registro **no reescribe** la salida "hoy" (era lo que ensuciaba el árbol y abortaba la 2.ª emisión).
- `procedencia_registro`: el árbol puede tener cambios **solo** dentro de `research/int/int11_vivo/`.
- `comprobar_fecha`: emisión = hoy ± 3 días; si no, se niega (datos revisados = fuga). `--vintage`: emite solo los
  países con vintages ALFRED (EE. UU.: CPIAUCSL, GDPC1) leídos "tal como se publicaron" en la fecha
  (`escenarios_vivo.serie_asof`). La OCDE del warehouse no tiene vintages.
- Huella: las series exactas de IPC y PIB usadas y su sha256 se guardan en cada emisión y en el índice.

## 3. Eventos como estados opcionales del generador (interfaz; INT-14 §6.3)
- `Config(eventos=("petroleo", "crisis", ...))` + columnas `ev_<e>` en las filas (`preparar_filas(..., eventos=...)`,
  0/1 del evento EN el año, sin retardo).
- **Probabilidad anual por recuentos ≤ 2004** (`ajustar` rechaza años posteriores): si el indicador es igual en todos
  los países cada año → evento GLOBAL, se cuentan años; si no → país-años. `recuentos_evento={e: (k, n)}` permite dar los
  recuentos de INT-14 §3. Por lote, riesgo ~ Beta(k + ½, n − k + ½) (incertidumbre de parámetros); en cada año y
  trayectoria, evento ~ Bernoulli(riesgo). **Independiente del régimen y entre años** (INT-14: condicionar sería usar
  una relación no probada).
- `evento_condiciona=False` (por defecto): el evento se simula y se informa (`Escenarios.eventos`, `prob_evento`,
  columnas `ev_<e>` en `a_tabla`) **sin tocar las rentabilidades** → "P(algún shock del petróleo en 5 años)", sin
  pretender su efecto. `True`: las filas del año se sortean entre años con el MISMO patrón de eventos (celda → (·, s) →
  todos, mínimo 5 filas); el efecto sale de los datos, sin estimarlo aquí. Solo bootstrap.
- Hoy NO se estima ni se activa nada: INT-14 mide los efectos (corrida A). Se activará con prerregistro propio solo
  para los eventos que INT-14 establezca. Tests sintéticos: recuentos global/país, frecuencia simulada = Beta, sin
  condicionar no hay diferencia, condicionando aparece el efecto plantado.

## 4. Contaminación (leer antes de interpretar cualquier número de v3 con datos ≤ 2004)
- **v1 y v2 ya se corrieron en ≤ 2004** (LOCO y temporal) y v3 se diseñó después de leer esos resultados y su
  validación (coberturas por país, temporal de la bolsa, distancia al umbral). Aunque cada arreglo sale de un mecanismo
  y sus valores se fijan a priori o en sintético, **cualquier evaluación de v3 en ≤ 2004 es DESARROLLO, no
  confirmación**.
- Datos reales usados en esta fase: solo la **dt robusta de la brecha** P3 (macro, sin régimen ni rentabilidades) para
  el proceso sintético, y las mediciones ya congeladas de v1/v2. Ningún resultado real cruzado con el régimen.
- La salida "hoy" no se ha recalculado con v3.
- Lo único que puede confirmar v3: el periodo bloqueado (≥ 2005), dentro de la confirmación final única, y el registro
  en vivo.

## 5. Potencia por simulación (research/int/int11_v3_potencia_P{0,1,2}.json)
PENDIENTE: se rellena con los resultados de scripts/int11_v3_potencia.py (commit 8c6d5c5, árbol limpio).

## 6. Riesgos y lo que v3 NO arregla
- Sesgo de nivel de P(inflación > 5 %) cerca del umbral (§2.2).
- Época futura distinta de todo el pasado (§2.4); la semivida solo ayuda si el cambio ya empezó dentro del entrenamiento.
- Los σ de la pertenencia suave son supuestos de medida, no estimados; si la medida es mejor de lo supuesto, la mezcla
  difumina de más (en sintético sin ruido no empeora la calibración).
- Sobrecobertura posible (c mayor + semivida): preferimos errar hacia ancho; se informa la anchura.
- Eventos: probabilidad sin condicionar y sin persistencia; efectos sin medir.
- Moneda local, 14 países ricos, datos revisados (no "as of") en el entrenamiento.

## 7. INT-12 (HAR diario) como ancla de volatilidad a corto plazo — no incluido
El motor es anual. Un ancla HAR (volatilidad realizada prevista a 1-3 meses) podría reescalar el primer año de la
bolsa (como `inclinacion` o un factor de escala por lote). No se incluye en v3: INT-12 no está confirmado y mezclar
frecuencias exige su propio diseño. Queda como opción v4 si INT-12 confirma.

## 8. Interfaz
```python
gen = E.Generador(E.Config.v3()).ajustar(filas)                     # filas ≤ 2004
esc = gen.simular_suave("ESP", inflacion=0.0325, brecha=0.012, horizonte=5, n_lotes=200, por_lote=100, semilla=s)
esc.inicio; esc.meta["estado_observado"]; gen.escala_resumen["curtosis_pais"]
# eventos (opcional, sin efectos hasta INT-14):
f = E.preparar_filas(df, eventos=("petroleo",)); g = E.Generador(E.Config.v3(eventos=("petroleo",))).ajustar(f)
g.simular(...).prob_evento("petroleo", h=5)
```

## 9. Decisiones del usuario
Ver el borrador de prerregistro (docs/int/INT11_prerregistro_v3_v0.md §10), con la recomendación de cada una.
