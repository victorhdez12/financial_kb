---
documento: INT-11 v2 — motor de escenarios: arreglos, horizonte móvil, potencia y plan de confirmación
version: 0.1 (2026-10-30)
estado: DISEÑO + CÓDIGO + POTENCIA SINTÉTICA. Nada de v2 se ha evaluado con datos reales; ningún resultado real se ha
        cruzado con el régimen en esta fase.
parte_de: docs/int/INT11_diseno.md (v1), docs/int/INT11_prerregistro_v1.md (v1 congelado), research/int/int11_resultado.md
          (corrida única v1), docs/validation/2026-10-30_int11.md (validación v1)
codigo: src/intl/escenarios.py (Config.v2, estado_movil, ventana_objetivo), src/intl/int11.py (proceso sintético v2),
        src/report/escenarios_vivo.py (estado_actual_movil), scripts/int11_v2_potencia.py, tests/test_intl_int11_v2.py
potencia: research/int/int11_v2_potencia.json
prerregistro: borrador docs/int/INT11_prerregistro_v2_v0.md
---

# INT-11 v2: abanicos que digan la verdad sobre su propia anchura

## 0. En una frase
v1 daba abanicos del 90 % que acertaban el **88,6 %** (y peor en los países volátiles y en los regímenes raros). v2
arregla las **tres causas que encontró el diagnóstico** (no las que sugieren los resultados), cambia la salida "hoy" a
un **horizonte móvil de 12 meses** que empieza mañana (no el año natural ya medio vivido) y propone **cómo confirmar de
verdad**, porque los datos ≤ 2004 ya están gastados para esta pregunta.

**Idea clave para aprender:** un abanico del 90 % es "fiable" si, mirado sobre muchos casos, contiene lo que pasó 9 de
cada 10 veces, **también** en los casos difíciles (países volátiles, situaciones raras). Un modelo puede acertar el
90 % de media y fallar donde más importa. Por eso v2 mira la calibración por régimen y por país, no solo la media.

## 1. Qué falló en v1 y por qué (diagnóstico, no resultado)
| síntoma (v1, ≤ 2004) | causa identificada | ¿se arregla mirando más resultados? |
|---|---|---|
| cobertura LOCO 88,6 % frente a banda [89,3; 90,0] | ≈ ¼ heterogeneidad entre países (nulo heterogéneo: 89,4 %); ≈ 0,5 pp condicionar por régimen; ≈ 0,4 pp celdas (s_{t−1}, s_t) pequeñas | no: es mecánico (abajo) |
| regímenes raros 83-87 % (estanflación 34 filas, crec. bajo 65) | **cuantiles de muestra finita**: con n = 34 el intervalo p5-p95 de la muestra contiene una observación nueva con prob. ≈ 31/35 = 0,886 (fórmula de estadísticos de orden), con n = 20 ≈ 0,85. El bootstrap bayesiano NO lo corrige (su predictiva es la propia muestra) | no: se demuestra con muestras iid sintéticas |
| FIN / PRT / JPN 81-84 % | el país dejado fuera recibe la dispersión **media** del panel; si es más volátil, falla más (DEU 1,57; FIN 1,15-1,48; JPN 1,28 frente a 1) | no: la dispersión propia se mide sin el régimen |
| κ en el borde (10^3,5) | la rejilla era corta; no se sabe si "todos los países iguales" o "algo distintos" | no |
| "hoy" describe el año natural t + 1 | el motor es anual; con estado 2025 el abanico era para 2026 (10 meses ya pasados); EE. UU. con un mes de IPC perdido retrocedía a 2024 | no |
| temporal: bolsa 80,5 % (≤ 1949 → 1950-2004) | **no estacionariedad** (la dispersión de la bolsa después de 1950 no es la de antes) | **v2 no lo arregla** (ver §6, riesgo declarado) |

**Comprobación de la causa "muestra finita" (sintético, iid t con ν = 4,5, 3.000 réplicas):**

| n de la celda | 20 | 34 | 65 | 150 | 400 | 1.000 |
|---|---|---|---|---|---|---|
| cobertura del p5-p95 empírico (v1) | 0,850 | 0,885 | 0,883 | 0,899 | 0,892 | 0,896 |
| con suavizado c = 4 (v2) | 0,899 | 0,901 | 0,896 | 0,908 | 0,890 | 0,902 |

(ruido de simulación ± 0,005). Es exactamente el patrón de v1: bien en celdas grandes, estrecho en las pequeñas.

## 2. Arreglos del motor (todos opcionales en `Config`; `Config()` reproduce v1 bit a bit, `Config.v2()` los activa)

### 2.1 Dispersión propia del país, encogida hacia el panel (Bayes jerárquico) — `escala_pais`
- Para cada fila del pool, en log(1 + r): **media del año** (choque común, con ≥ 3 países) y **desviación propia**
  dev = y − media del año (corregida por n/(n − 1), porque la media incluye la propia fila).
- Factor del país c y activo a: f̂_c = dt(dev del país) / dt(dev del panel). Error de medida en log:
  se² = (curtosis + 2) / (4 n_c) (con colas gruesas el error es mayor que el normal 1/(2n)).
- Entre países: log f_c ~ N(m, τ²), τ² por momentos (varianza de log f̂ menos el error medio). Posterior de cada país
  (se encoge hacia m tanto más cuanto menos datos tenga); **país fuera del pool** (dejar un país fuera, o un país nuevo)
  → predictiva N(m, τ²): no sabemos si es volátil, y el abanico lo refleja.
- Simulación: la fila (c', t) se convierte en una fila "del país c": y* = media_t + g_c · dev / f̂_c', con g_c
  **sorteado por lote** (incertidumbre de parámetros). Si g_c = f̂_c' la fila queda igual.
- Por qué así y no "ensanchar todo": conserva el choque común (un 2008 sigue siendo un 2008 para todos) y solo
  reescala lo propio del país, que es donde está la heterogeneidad medida.

### 2.2 Ensanchamiento por incertidumbre de la celda — `c_suavizado = 4`, `nu_suavizado = 5`
- **Bootstrap suavizado**: a cada valor sorteado se le suma ruido t (ν = 5, varianza unidad) × dt de la celda ×
  √(c / n_celda). La varianza predictiva de la celda pasa a (1 + c/n)·var: con n = 34 → +12 %; con n = 800 → +0,5 %.
- Es la versión no paramétrica de la predictiva t de Student (la de "media y varianza desconocidas":
  var × (1 + 1/n) × colas t), con c mayor que 1 porque los cuantiles extremos se estiman peor que la media.
- **c = 4 se fijó en el experimento iid de §1** (sintético, sin datos reales): es el menor valor que lleva la cobertura
  a 0,90 con n = 20-34. Las colas del ruido (t5) dan valores más allá de lo observado, que es lo que le faltaba al
  bootstrap puro (nunca sorteaba un año peor que el peor de la celda).
- Solo se suaviza la **rentabilidad**; la inflación y el crecimiento se sortean tal cual (si no, se rompería la
  coherencia "régimen de inflación alta ⇔ inflación > 3 %", que es lo que hace bueno el Brier de inflación).
- En `modo="t"` el equivalente es multiplicar la covarianza de la celda por (1 + c/n).

### 2.3 Mezcla con el incondicional según el tamaño de la celda — `k_mezcla` (implementada; **recomendado 0**, D3)
- Con probabilidad k/(n + k) la fila se sortea del **"incondicional coherente"**: todas las filas cuyo régimen de
  llegada está del mismo lado de la inflación que el simulado (sin condicionar al régimen de partida).
- Con n = 34 (estanflación) → 23 % de la mezcla; con n = 400 → 2 %. Es encogimiento del efecto del régimen hacia
  "no sé", proporcional a lo poco que sabemos: protege de la **maldición del ganador** (los efectos del Atlas §8
  probablemente están inflados) y ensancha donde hay pocas filas. Con mezcla, el suavizado usa n + k.
- **Por qué se recomienda k = 0** (potencia §5.1, sintético): la mezcla no añade cobertura (±0,1 pp frente a sin mezcla)
  y con regímenes raros más dispersos la **resta** (87,3 % frente a 88,0 %), porque trae filas de la celda grande, más
  tranquilas. El suavizado ya cubre la incertidumbre de la celda. Queda como opción (D3) si el usuario prefiere
  protegerse de efectos inflados a costa de un poco de cobertura en los raros.

### 2.4 Rejilla de κ ampliada — `rejilla_kappa = (0, 6, 121)`
log10 κ ∈ [0; 6] (v1: [0; 3,5]). Salida nueva `kappa_en_borde` en `meta`. Si κ sigue en el borde superior, la lectura
es "los países no se distinguen en sus transiciones de régimen" y se dice así en la salida.

### 2.5 Nulo heterogéneo para el valor crítico
El proceso sintético (src/intl/int11.dgp_rent) acepta `fac_pais` (N × A): el choque propio de cada país se multiplica
por su factor de dispersión **medido en el panel real sin el régimen** (solo Y; research/int/int11_v2_potencia.json,
`medicion_v2.factor_pais`). Y `fac_raro` (sensibilidad hipotética: los años tras un régimen raro, más dispersos).
También acepta una **inflación continua** (lineal en el latente de inflación, coherente con el régimen y con la
frecuencia real de inflación > 5 %), necesaria para simular el Brier.

## 3. Horizonte móvil de 12 meses (salida "hoy")
- **Estado mensual (OCDE)** con ventanas móviles que terminan en el último dato publicado (`E.estado_movil`):
  inflación = log(media del IPC de los 12 últimos meses / media de los 12 anteriores); brecha = log PIB de los 4 últimos
  trimestres − media de las 10 ventanas de 4 trimestres anteriores, **per cápita** con la población de Maddison
  (extrapolada desde 2022 con su crecimiento de 10 años; arregla el sesgo de +2,9 pp del PIB total que vio el validador).
- **Puente con JST**: cuando el último mes es diciembre y el último trimestre el T4, `estado_movil` es **idéntico** al
  estado anual (test `test_estado_movil_en_diciembre_es_el_estado_anual`). El motor se estima con años naturales y se
  aplica a una ventana de 12 meses que empieza en otro mes: el supuesto (declarado) es que la distribución de 12 meses
  dada la situación de los 12 anteriores no depende del mes de arranque. No se puede comprobar con JST (anual); el
  registro en vivo lo comprobará.
- **Ventana objetivo** (`E.ventana_objetivo`): los 12 meses que siguen a la **fecha de emisión** (p. ej. emitido el
  30-oct-2026 → noviembre 2026 a octubre 2027). La salida rotula siempre "desde … hasta …", nunca "el próximo año".
- Un mes de IPC perdido (EE. UU., oct-2025) se **interpola** (máx. 1 hueco dentro de la ventana) en lugar de
  retroceder un año entero; con 2 huecos o más se retrocede y se avisa.
- Desfase: el estado usa datos hasta el mes m (IPC) y el trimestre q (PIB, ≈ 5-7 meses antes). En JST el estado se
  conocía ≈ 4 meses tarde respecto del año evaluado (hallazgo 6(i) del validador); el horizonte móvil elimina esa
  ventaja: es **más honesto** que la evaluación histórica.
- Evento de inflación para el Brier en vivo: inflación de la ventana = log(media IPC de los 12 meses de la ventana /
  media de los 12 anteriores) > log(1,05). Misma definición que la anual de JST.

## 4. Contaminación (leer antes de interpretar cualquier número de v2 con datos ≤ 2004)
- v1 ya se corrió sobre 1876-2004 y v2 se diseñó **después de ver** su cobertura por país, por régimen y por diseño.
  Aunque cada arreglo se justifica por un mecanismo (y se calibra en sintético), **cualquier evaluación de v2 en ≤ 2004
  es DESARROLLO, no confirmación**: pasaría por construcción con más facilidad que un modelo nuevo.
- Los factores por país (§2.1) se miden en ≤ 2004 sin el régimen (solo Y) — permitido por la disciplina del proyecto,
  pero el validador ya los había visto a posteriori.
- La salida "hoy" de v1 ya miró el estado actual de los países (no resultados futuros): no contamina nada.
- Lo único que puede **confirmar** v2: datos que nadie ha usado para esta pregunta → el periodo bloqueado (≥ 2005) o el
  registro en vivo (§7).

## 5. Potencia por simulación (research/int/int11_v2_potencia.json)
Commit 12e1b3a (árbol limpio, 2026-10-30T12:05Z, 1.291 s). Motor completo (no un sustituto) con 20 × 100 sorteos por
predictiva. S1: 100 réplicas por proceso; S2-S3: 200. **Medido sin el régimen (≤ 2004):** dispersión entre países
τ(log factor) = 0,24 bolsa, 0,25 bonos, 0,38 letras, 0,18 vivienda, 0,35 oro; inflación > 5 % en el 26,2 % de los
país-años (> 3 %: 40,5 %). Nota: S2-S3 se corrieron con `k_mezcla` = 10 (valor del commit); S1 muestra que k = 0 y
k = 10 dan la misma cobertura global (±0,1 pp), así que los números valen para la recomendación k = 0.

### 5.1 Calibración: v1 frente a v2 (cobertura del p5-p95 nominal 90 %; media de 100 paneles)
| proceso nulo | diseño | v1: S5 / raros | v2 (k = 10): S5 / raros | v2 sin mezcla (recomendado) | v2 sin suavizado | CRPSS medio v1 → v2 |
|---|---|---|---|---|---|---|
| homogéneo (el de v1) | LOCO | 89,7 / 88,0 | 90,7 / 90,6 | 90,7 / 90,3 | 90,5 / 89,4 | 2,7 → 2,7 % |
| heterogéneo (factores medidos) | LOCO | **89,5** / 87,8 | 90,4 / 90,4 | **90,3 / 90,0** | 90,2 / 89,3 | 2,9 → 2,9 % |
| heterogéneo | temporal | 89,4 / 88,1 | 90,4 / 89,9 | 90,3 / 89,8 | 90,1 / 89,2 | 3,5 → 3,8 % |
| heterogéneo + raros × 1,5 (hipot.) | LOCO | 89,5 / **85,9** | 90,4 / 87,3 | 90,3 / **88,0** | 90,1 / 86,3 | 2,8 → 2,9 % |

Lectura: (1) v1 en su propio nulo homogéneo da 89,7 % [89,3; 90,0]: se reproduce la banda de la corrida v1. (2) v2
lleva la cobertura global al 90,3-90,7 % (ligera **sobrecobertura**, ≈ 0,3-0,5 pp: preferible para "rangos
fiables") y la de los regímenes raros de 87,8 % a 90,0 %. (3) El suavizado es lo que arregla los raros (+0,7 a +1,7 pp);
la escala por país, lo global. (4) **La finura no se pierde**: el CRPSS frente a M0 no baja. (5) Con raros más dispersos
de verdad, ningún motor llega al 90 % en ellos (v2 88 %): pocas filas son pocas filas.

### 5.2 Potencia de la puerta de calibración (v2, nulo heterogéneo)
Intervalos escalados por k para simular un motor que cubre de verdad ≈ 85 % o ≈ 80 % (realizado: 85,6-86,6 % y
81,5-82,8 %). "Detección" = probabilidad de que S5 salga de la banda nula 2,5-97,5.

| diseño | filas aprox. | banda nula de S5 | falsa alarma | detecta 85 % | detecta 80 % | algún activo a > 5 pp con motor calibrado |
|---|---|---|---|---|---|---|
| desarrollo LOCO (≤ 2004) | 1.550 | [90,0; 90,9] | 0,045 | **1,00** | 1,00 | 0,00 |
| desarrollo temporal (1950-2004) | 760 | [87,7; 92,9] | 0,045 | 0,80 | 1,00 | 0,09 |
| **bloqueado 2005-2020** (14 países) | 224 | [84,6; 93,4] | 0,05 | 0,26-0,35 | **0,80** | **0,69** |
| en vivo 5 años | 70 | [79,7; 96,0] | 0,05 | 0,07-0,12 | 0,17-0,28 | 0,94 |
| en vivo 10 años | 140 | [82,7; 95,0] | 0,05 | 0,18-0,22 | 0,52-0,59 | 0,79-0,85 |
| en vivo 20 años | 280 | [85,1; 93,2] | 0,05 | 0,29-0,41 | 0,83-0,91 | 0,65 |

(rangos = escenario estacionario / "tranquilo"). Lectura: con el bloqueado se puede **detectar una infracobertura seria**
(80 %) con prob. 0,80, no una leve (85 %). El criterio "cada activo a ±5 pp" **no sirve fuera de muestra** (con un motor
perfecto falla el 65-94 % de las veces: 224 filas por activo son pocas y los fallos van en racimos): en la confirmación
la puerta debe ser solo S5 contra su banda simulada.

### 5.3 Brier de los dos eventos (v2 frente a la frecuencia histórica; DM por años, unilateral, α = 0,05)
| diseño | inflación > 5 %: BSS medio [2,5-97,5] | potencia | eventos | bolsa ≤ −20 %: BSS medio | potencia |
|---|---|---|---|---|---|
| desarrollo LOCO | +28 % [17; 40] | **1,00** | 482 | +0,3 % | 0,06 |
| desarrollo temporal | +28 % [8; 50] | 0,93 | 199 | +0,6 % | 0,18 |
| **bloqueado 2005-2020**, estacionario | +30 % [−3; 69] | **0,67** | 59 | +0,5 % | 0,10 |
| bloqueado, "tranquilo" (inflación > 5 % ≈ 8 %) | +44 % [3; 92] | **0,76** | 18 | +0,5 % | 0,14 |
| en vivo 5 años (estac. / tranq.) | +33 / +38 % | 0,48 / 0,51 | 18 / 6 | ≈ 0 | 0,13 |
| en vivo 10 años | +31 / +43 % | 0,56 / 0,60 | 37 / 12 | ≈ 0 | 0,12 |
| en vivo 20 años | +30 / +44 % | 0,76 / 0,82 | 74 / 22 | +0,5 % | 0,13 |

Lectura: (1) la **inflación > 5 %** es la afirmación con más potencia de todo INT-11 (la real de v1 fue +25 %, en línea
con el sintético +28 %): con el bloqueado se confirmaría con prob. 0,67-0,76; (2) la **caída de la bolsa ≥ 20 %** no se
puede demostrar nunca (potencia ≤ 0,18 en cualquier diseño, BSS ≈ 0,5 %): el motor la dará como probabilidad
descriptiva, sin pretender que mejora a la frecuencia histórica.

## 6. Riesgos y lo que v2 NO arregla
- **No estacionariedad** (temporal bolsa 80,5 % en v1): si la dispersión de la bolsa cambia de época, ningún arreglo de
  v2 lo corrige; el periodo bloqueado (entrenado con ≤ 2004, probado en 2005-2020) es justo un diseño "temporal", así que
  es el riesgo principal de la confirmación. Una "escala por época" (dispersión reciente del país) sería un cambio de
  modelo no justificado por el diagnóstico de LOCO; se deja como v3 posible, declarado aquí antes de ver nada ≥ 2005.
- **Sobrecobertura ligera**: en sintético v2 cubre ≈ 90,3-90,7 % en LOCO. Preferimos errar hacia abanicos algo anchos
  (el objetivo del usuario son rangos fiables); se informa.
- El suavizado podría diluir el efecto del régimen; en sintético la finura (CRPSS) no baja (2,9 % → 2,9 %).
- La potencia supone estacionariedad (salvo el escenario "tranquilo", que solo baja la inflación); si 2005-2020 es
  más volátil que 1876-2004, la confirmación puede fallar por el motivo de §6 primero.
- Factores de país por activo independientes en el sorteo (un país volátil en bolsa no se supone volátil en bonos).
- El horizonte móvil supone que la relación anual vale para cualquier mes de arranque (§3).
- Moneda local, sin costes, 14 países ricos, datos revisados (no "as of").

## 7. Cómo confirmar de verdad (recomendación)
**Opciones:**
| opción | qué | ventaja | coste |
|---|---|---|---|
| A. Solo en vivo | registro mensual desde la primera emisión v2; contraste formal a los 10 años | no gasta nada | calibración: detecta 80 % con prob. 0,52-0,59 a 10 años; inflación 0,56-0,60. Una década sin confirmar |
| B. Bloqueado ya, solo para INT-11 | corrida única 2005-2020 | 0,80 (calibración 80 %) y 0,67-0,76 (inflación) **ahora** | gasta el único periodo no visto del proyecto para un estudio |
| **C. Bloqueado dentro de la confirmación final ÚNICA del proyecto + en vivo desde ya** | INT-11 v2 entra con 2 afirmaciones (K1 calibración, K2 Brier inflación) en el lote final junto con el resto de estudios congelados; mientras, registro en vivo | misma potencia que B, sin gastar el bloqueado estudio a estudio (el problema de las comparaciones múltiples se resuelve una vez, con Holm sobre todo el lote) | hay que esperar a que el resto del proyecto esté congelado |

**Recomendación: C.** (1) Fase D (≤ 2004) una sola vez como **comprobación de que los arreglos funcionan**, no como
prueba. (2) Si pasa, congelar v2 entero (código, semillas, banda nula del bloqueado calculada antes con el nulo
heterogéneo) y meterlo en la confirmación final única. (3) Empezar **ya** el registro en vivo mensual (con la salida
"hoy" v2 rotulada como no confirmada); es gratis y es la única evidencia que crece sola.

**Afirmaciones para la confirmación** (con su potencia):
- **K1 calibración**: S5 (5 activos, h = 12 meses ≈ año natural en JST) en 2005-2020, 14 países, dentro de la banda nula
  del bloqueado ([84,6; 93,4] en esta potencia; se recalcula al congelar). Detecta 80 % con 0,80; 85 % con ≈ 0,3.
  Sin criterio por activo (falsas alarmas 0,69).
- **K2 inflación > 5 %**: BSS > 0 y DM unilateral p < 0,05 frente a la frecuencia de ≤ 2004. Potencia 0,67-0,76 con
  JST 2005-2020. **Mejora posible** (D7): el evento solo necesita IPC y PIB, que la OCDE tiene hasta 2025 y con origen
  mensual → 21 años de ventanas móviles (incluye 2021-2023); potencia ≈ la de "en vivo 20 años", 0,76-0,82, y prueba el
  puente mensual de §3. Aviso: que hubo inflación alta en 2021-2023 es de conocimiento público; no cambia el modelo
  (congelado antes), pero se declara.
- **K3 caída ≥ 20 %**, C1 (CRPS) y la cobertura por régimen: descriptivos (sin potencia).

## 8. Interfaz (sin cambios para el consumidor; nuevo en `meta`)
```python
gen = E.Generador(E.Config.v2()).ajustar(filas)            # filas ≤ 2004
esc = gen.simular("ESP", estado, horizonte=1, n_lotes=200, por_lote=100, semilla=s)
esc.meta["kappa_en_borde"]; gen.escala_resumen             # κ y factores de dispersión por país (m, τ, f_c)
est = V.estado_actual_movil(con, "2026-10-30")             # estado móvil por país + ventana_objetivo
```
El contrato de `Escenarios` (trayectorias equiprobables, `lote` = sorteo de parámetros, sin pronóstico puntual) no cambia.
