---
documento: especificación a priori de M2, nowcast ESTRUCTURAL del eje G (factor coincidente con ragged edge + composición exacta de Ĝ)
version: 1.3 (2026-10-24; v1.2 = 68e66dd, v1.1 = d1bde77, v1.0 = 1a5f1f9. v1.0-v1.2 congeladas ANTES de cualquier contacto con la etiqueta para M2/M3/pool; v1.3 ANTES de cualquier corrida con la etiqueta REAL: hasta su push la etiqueta solo se ha leído en la sonda de elegibilidad (recuentos) y en placebos barajados ≤ 2004; cambios en §9)
fecha: 2026-10-24
hipotesis: H-M2-001 (research/hypotheses.yaml) — DECLARADA CONTAMINADA (post hoc respecto a M1 v1/v2; ver §0)
equivale_a: "H-M2-002 / m2_struct_g" de la revisión del Estratega (docs/reviews/2026-10-23_estratega_macro_m1v2.md §3.2), en la versión del Investigador (docs/research/2026-10-23_mejoras_nowcast_regimen.md §3.2, §3.4)
papel: COMPONENTE del pool (docs/models/pool_spec.md). No es contraste principal: frente a M0 solo se informa (secundaria fuera de Holm)
codigo: src/models/regime_components.py (esqueleto y constantes de esta spec; sin implementar); implementación futura en src/models/models_struct.py
tests: tests/test_regime_components.py (solo datos sintéticos)
datos: base PIT v0.4 CONGELADA (tag pit-v0.4) + niveles PIT de las 4 series de la etiqueta vía PITLabeler.levels_at (§2); desarrollo solo ≤ 2004-12
depende_de: arnés v2.3 (eje G continuo, harness.md §5c) + extensiones v2.4 de §8 (sin implementar); etiqueta v1.1 congelada
revisiones: docs/validation/2026-10-24_specs_pool_v4.md (Validador: M-2, M-4, B-1, B-2), docs/reviews/2026-10-24_estratega_macro_specs_pool.md (Estratega: imprescindible 1)
---

# M2: nowcast estructural de G (especificación a priori)

Este documento se escribe, se commitea y se empuja a `origin` **antes** de cualquier contacto con la etiqueta **para
M2, M3 o el pool** (ni oficial ni recalculada, ni siquiera para contar meses elegibles) y antes de implementar el
modelo. Las lecturas ≤ 2004 de ese día por otros motivos (suite, potencia, reproducción de M1 v1) están en §9. La marca de tiempo
del push lo demuestra. **Una sola pasada de desarrollo** (§6); no se itera mirando sus resultados. Un cambio técnico
posterior se anota en §9 con lo que se había visto.

## 0. Contaminación declarada

- La familia (nowcast estructural de G) la propone el Estratega el 23-oct **después** de ver M1 v1 y M1 v2 en
  desarrollo ≤ 2004 (horizonte: 1/3 de G conocido y 2/3 de previsión a 0-4 meses). La versión con factor coincidente y
  *ragged edge* la propone el Investigador el mismo día con literatura anterior a 2005 (Stock-Watson, Kim-Nelson,
  Chauvet-Piger, Camacho-Pérez-Quirós-Poncela; Jacobs-van Norden y Kishor-Koenig para las revisiones).
- La elección de las peticiones de paro y de Filadelfia como indicadores adicionales viene de la lista del Estratega
  (post M1 v2).
- **Atenuante (no exime):** M2 **no ajusta ningún parámetro con la etiqueta**. El factor se estima solo con las
  series (máxima verosimilitud, §3) y la incertidumbre sale del filtro, de las revisiones y de la tendencia (§4). La
  etiqueta recalculada solo se usa para la puntuación del arnés. Lo que está contaminado es el **diseño**, no los
  parámetros.
- Consecuencia: en desarrollo M2 no demuestra nada. La prueba limpia es la evaluación única, y allí M2 entra **solo
  como componente del pool** (P-EVAL-BASE v4, borrador). Cuenta como un ensayo en el registro (Deflated).

## 1. Hipótesis H-M2-001

> Con la información publicada hasta la fecha de decisión t, un factor dinámico de 1 factor sobre las tasas mensuales
> de los 4 indicadores coincidentes de la etiqueta más las peticiones de paro y Filadelfia, con el *ragged edge* real
> de cada serie, prevé las tasas que faltan de la ventana de G(t) (t−3 … t+4). Compuesto **exactamente** como la
> etiqueta (mismo código), da una previsión gaussiana de G(t) cuya probabilidad P(G alto) = Φ(Ĝ/√(σ̂² + s_G²))
> mejora la log-loss del eje G frente a M0.

- **Mecanismo:** G(t) es una media triangular (1, 2, 3, 3, 3, 3, 2, 1)/18 de las tasas mensuales de t−3 a t+4 frente a
  su tendencia. En t se conocen t−3 … t−1 de INDPRO y PAYEMS (6/18 = 1/3 del peso) y menos de W875RX1 y CMRMTSPL. Las
  peticiones de paro (semanales, del propio mes t) y Filadelfia (encuesta del mes t) son los únicos datos del mes t:
  informan del factor en t y, a través de su dinámica, de t+1 … t+4. M0 ve la etiqueta de t−5.
- **Peticiones de paro = flujo** (v1.1): el nivel de las peticiones iniciales (despidos nuevos) se mueve con el ritmo
  de crecimiento **del mes** (ln C<sub>m</sub> ≈ a − b·f<sub>m</sub>, como en el índice ADS); su tasa interanual
  ln C<sub>m</sub> − ln C<sub>m−12</sub> carga, por tanto, en f<sub>m</sub> − f<sub>m−12</sub> (§3), no en la media de
  12 meses de f (forma de un stock). Con la forma de stock la serie se leería con ≈ 6 meses de retraso al entrar en
  una recesión y con el signo cambiado al principio de la recuperación (Estratega, revisión del 24-oct §1.2).
- **Signos esperados** (se informan; no se imponen ni deciden, porque no se estiman con la etiqueta): cargas del
  factor > 0 en las 4 tasas coincidentes y en Filadelfia; < 0 en las peticiones de paro.
- **Contraste informativo:** M2 − M0 en log-loss blanda de 4 cuadrantes (= la del eje G, porque el eje I de M2 es el de
  M0, §5), vintage. No entra en Holm (el contraste principal es el pool, k = 1).

## 2. Datos (todo PIT; nada nuevo en la base)

| bloque | serie | de dónde | transformación | qué mes informa |
|---|---|---|---|---|
| coincidentes (4) | `INDPRO`, `PAYEMS`, `W875RX1`, `CMRMTSPL` | **niveles conocidos en la fecha de decisión** vía `PITLabeler.levels_at(fecha)` del mismo modo (las mismas entradas, vintages y calendario que usa la etiqueta recalculada y la persistencia M0) | r = 100·Δln(nivel), mensual; desviación frente a su mediana de los 120 meses previos (τʳ, §3) | su propio mes; borde desigual según la última observación publicada |
| semanal | `claims_4w_yoy` | matriz PIT v0.4 (estado `principal_epoca`, vintage desde 2009-05) | estandarizada (media y desviación del tramo de estimación) | el mes de la fecha de decisión |
| encuesta | `philly_neworders` | matriz PIT v0.4 (`principal_epoca`, latest_truncated) | estandarizada | el mes de la fecha de decisión |

- **Por qué niveles vía `levels_at` y no una base v0.5.** La composición exacta de Ĝ necesita los **niveles** de las 4
  series con su borde desigual, no las tasas de 3 meses de la matriz (`indpro_3m_ann` …), y la estimación del factor
  necesita la historia completa de la vintage de cada corte, que no cabe en una fila de la matriz. `levels_at` ya
  existe, es PIT (es la misma función que da la etiqueta de entrenamiento y la persistencia de M0) y tiene la barrera
  `HoldoutLocked` para fechas ≥ 2005-01. Las 4 series no son columnas prohibidas (la lista negra es la de la
  etiqueta + USREC). La base v0.4 congelada no se toca. Exige la extensión del arnés §8-1 (el modelo pide los
  niveles al arnés; nunca abre ficheros).
- **Modo:** el mismo de la corrida. En `vintage`, cada serie entra como se publicó en la fecha (la vintage de
  INDPRO/PAYEMS; W875RX1 desde 2010-05 y CMRMTSPL desde 2013-06; antes, latest_truncated, como en la etiqueta PIT).
  En `latest_truncated`, la última vintage truncada por publicación.
- **Ventana de datos del factor:** meses 1968-06 → mes de la fecha de decisión (el primero con las 6 series posibles;
  antes de su primer dato o de su τʳ una serie es NaN y el filtro la trata como faltante).
- **Variables de la matriz con historia hasta el corte:** el factor necesita `claims_4w_yoy` y `philly_neworders` de
  los meses m0−5 … m0, que el embargo de la etiqueta deja fuera de `Xtr`. Son variables conocidas en m0 (sin etiqueta):
  extensión del arnés §8-2.
- **S-PIT-001 (Filadelfia prudente antes de 1990-07)** se aplica en desarrollo con esta **regla operativa** (v1.1,
  Validador M-4; concreta el criterio preregistrado el 15-oct, que no decía qué modelo, qué contraste ni qué
  intervalo):
  - d<sup>pr</sup><sub>t</sub> = ll(M0)<sub>t</sub> − ll(M2, matriz principal)<sub>t</sub> en `m2_long`, vintage;
    d<sup>fp</sup><sub>t</sub> = lo mismo con la matriz `vintage_filadelfia_prudente` (corrida `s_pit_001`), **mismos
    meses**. M0 no usa Filadelfia, así que es el mismo en las dos.
  - Δ<sub>S</sub> = media(d<sup>fp</sup>) − media(d<sup>pr</sup>); h = semiamplitud del IC 95 % de `mejora_logloss` de
    M2 frente a M0 en `m2_long`, vintage, matriz principal = (hi − lo)/2.
  - **Se dispara si |Δ<sub>S</sub>| > h** (en cualquier sentido: el dato de Filadelfia antes de 1990-07 no es fiable
    si su calendario cambia el resultado más que el propio error de muestreo).
  - Si se dispara, `philly_neworders` antes de 1990-07 pasa a **NaN** en el factor (regla mecánica fijada ahora;
    ningún otro cambio) y esa versión (`m2_struct_g` con la marca `philly_pre1990_nan`) es la **única** que se usa
    después: en las demás corridas de M2, como emisión de M3, como componente del pool y en P-EVAL-BASE. Si no se
    dispara, sigue la principal. En los dos casos la corrida `s_pit_001` se publica.
  - **Series exigidas (v1.2, Validador N-2):** d<sup>pr</sup> y d<sup>fp</sup> tienen que ser **finitas en todos** los
    meses puntuados de `m2_long` (vintage), estar **alineadas por mes** y tener **el mismo índice** (los mismos meses,
    en el mismo orden). Si no, la regla lanza un error y **se para**: no se toma la intersección ni se elige nada
    (`regime_components.s_pit_001_triggered`, con test).
  - **Marca de configuración (v1.2, Validador N-6):** la versión se escribe como
    `model_params.m2_struct_g: {philly_pre1990_nan: false}` (no se dispara) o `{philly_pre1990_nan: true}` (se
    dispara). Los modelos que dependen de M2 (`m3_tvtp_g`, `m3_ctp_g`, `pool_g`, sus variantes y las sensibilidades de
    M2 y M3) **heredan** el valor de `m2_struct_g` (el arnés lo copia y da error si alguno declara otro). Entra en el
    hash de configuración. En 6c solo se rellena ese booleano.
  - **Orden:** se resuelve (§6, pasos 6a-6c) y se commitea **antes** de cualquier corrida de M3 o del pool.

## 3. Modelo del factor (fijado)

Observaciones estandarizadas x<sub>j,m</sub> (j = 1…6; m = mes):

    coincidentes i ∈ {INDPRO, PAYEMS, W875RX1, CMRMTSPL}:
        x_i,m = (r_i,m − τʳ_i,m) / d_i  =  λ_i·f_m + u_i,m + ε_i,m
    peticiones de paro (tasa interanual de una media de 4 semanas):
        x_c,m = λ_c·(f_m − f_{m−12}) + u_c,m + ε_c,m          (v1.1: flujo; = λ_c·Σ_{k=0..11} Δf_{m−k})
    Filadelfia, nuevos pedidos (índice de difusión ≈ ritmo del mes):
        x_p,m = λ_p·f_m + u_p,m + ε_p,m

    f_m   = φ1·f_{m−1} + φ2·f_{m−2} + η_m,          η ~ N(0, 1)            (factor AR(2), varianza de innovación 1)
    u_j,m = ρ_j·u_j,{m−1} + e_j,m,                   e_j ~ N(0, q_j)        (idiosincrático AR(1))
    ε_j,m ~ N(0, 1e-4)                                                       (regularización numérica fija, no se estima)

- **τʳ<sub>i,m</sub>** = mediana de r<sub>i</sub> en los 120 meses m−120 … m−1 (≥ 90 presentes; si no, NaN). Hace el
  factor relativo a la tendencia de 10 años, como la etiqueta. Para los meses futuros se fija τʳ en su último valor.
- **d<sub>i</sub>**, y media/desviación de `claims_4w_yoy` y `philly_neworders`: del tramo de estimación del corte
  (ddof = 0). Se congelan junto a los parámetros (abajo).
- **Parámetros:** 6 cargas λ, φ1, φ2, 6 ρ, 6 q = **20** (sin cambio en v1.1: λ<sub>c</sub> sigue siendo una carga; signo
  esperado < 0). Normalización: varianza de η = 1 y λ<sub>PAYEMS</sub> > 0.
  Restricciones: |ρ<sub>j</sub>| < 0,99; (φ1, φ2) en la región estacionaria; q > 0.
- **Estimación:** máxima verosimilitud exacta del filtro de Kalman con datos faltantes. **Implementación única
  (v1.1, B-2): statsmodels `MLEModel` 0.15.0** (la instalada en `.venv`); una implementación propia solo puede
  existir como comprobación en un test (misma verosimilitud, tolerancia 1e-8), nunca para producir predicciones.
  Optimizador L-BFGS-B, `maxiter` = 1000, `gtol` = 1e-6.
- **Arranque determinista, siempre el mismo (v1.1, B-2):** en **cada** reestimación se arranca de cero (no del óptimo
  anterior), así que los parámetros de un corte dependen solo de los datos ≤ ese corte y no del primer corte de la
  corrida. Valores: λ = cargas del primer componente principal (escaladas a varianza 1 del componente, signo con
  λ<sub>PAYEMS</sub> > 0) del **panel balanceado más largo** = el tramo contiguo más largo de meses del tramo de
  estimación con las 6 x<sub>j</sub> presentes; si ese tramo tiene < 60 meses, el de las 4 coincidentes, y las series
  que quedan fuera arrancan con λ = 0,1 × su signo esperado. Para las peticiones, la regresión del arranque es sobre
  la diferencia a 12 meses del componente. φ por MCO del AR(2) del componente; ρ por MCO del AR(1) del residuo de
  cada serie (recortado a ±0,9); q = varianza de ese residuo AR(1) (mínimo 1e-3). Sin semillas: no hay nada
  aleatorio.
- **Si L-BFGS-B no converge** (`success = False` o `maxiter` agotado) se conservan los parámetros vigentes (los de la
  reestimación anterior) y se anota `fit_converged = false` en los diagnósticos del corte; en la primera reestimación
  de la corrida, sin parámetros previos, se usa el punto final del optimizador y se anota igual. Se informa el número
  de reestimaciones sin convergencia.
- **Cadencia (PIT):** el arnés llama a `fit` cada mes (refit_every = 1). Los parámetros, d<sub>i</sub> y las medias se
  **reestiman en el primer corte y después solo en los cortes de enero**, con los datos conocidos en ese corte (con el
  arranque determinista fijo del punto anterior; v1.2, Validador N-1: se borra «arrancando del óptimo anterior», que
  contradecía ese punto). Entre eneros, el filtro corre cada mes con los parámetros vigentes sobre los datos
  conocidos en la fecha de decisión. Todo ≤ corte. Con el arranque fijo, una corrida que empieza en enero (p. ej. el
  ensayo en seco, `dry_run_window` 1993-01) da en cada enero los **mismos parámetros** que la corrida desde
  `test_start` (test de implementación), **en todas las reestimaciones con `fit_converged = true` en las dos
  corridas** (v1.2, Validador N-4: con la regla de no convergencia, un enero sin convergencia vuelve a hacer depender
  los parámetros de la historia de la corrida; esas excepciones se informan con su mes y no cuentan como fallo del test); entre el primer corte y el primer enero la corrida no es comparable y no se
  puntúa (los cortes antes de W<sub>G</sub> no se puntúan).
- **Estado aumentado para la previsión:** para la composición (§4) el estado incluye los retardos **0…12** de f (13;
  v1.1, por f<sub>m−12</sub> en la ecuación de las peticiones), 0…7 de u<sub>i</sub> (las 4 coincidentes: 32),
  u<sub>c</sub> y u<sub>p</sub> (2): **dimensión 47** (46 en v1.0). La representación mínima también lleva los retardos
  0…12 de f. Con los mismos parámetros, la
  verosimilitud es idéntica a la de la representación mínima (test). Se extiende la muestra con 4 meses de NaN
  (t+1 … t+4) y se lee la media y la covarianza del estado en t+4 condicionadas a todo lo observado: dan la
  distribución **conjunta** de todas las tasas que faltan, por serie y mes.

## 4. Composición de Ĝ y su incertidumbre σ̂ (fijadas)

**Media Ĝ<sub>t</sub> (exacta, con el código de la etiqueta).**
1. Para cada coincidente, tasas previstas r̂ = τʳ<sub>i,t</sub> + d<sub>i</sub>·E[λ<sub>i</sub>f + u<sub>i</sub>]
   en los meses posteriores a su última observación hasta t+4.
2. Se acumulan sobre el último nivel publicado: L̂<sub>m</sub> = L<sub>último</sub>·exp(Σ r̂/100).
3. A los niveles conocidos en t, extendidos con L̂, se les aplica **`R.growth_components` y `R.growth_axis` de
   `src/labels/regime_us.py`** (el código congelado de la etiqueta): ritmo g con la media de 3 meses centrada y la
   variación t−3 → t+3 (pesos 1, 2, 3, 3, 3, 3, 2, 1), tendencia = mediana centrada de ±60 meses truncada en el borde
   (la que tendría la etiqueta recalculada si se conocieran los datos hasta t+4), σ<sub>i</sub> = MAD × 1,4826 de toda
   la muestra disponible, y media de los z con mínimo 2 indicadores. Ĝ<sub>t</sub> = la columna G en t.
4. Ningún parámetro libre: los pesos, la tendencia, σ<sub>i</sub> y el mínimo de indicadores son los de la ficha.

**Varianza (v1.3): σ̂²<sub>t</sub> = V<sub>conj</sub> + V<sub>rev,t</sub>.** V<sub>conj</sub> es la varianza del
error **conjunto** de previsión y de tendencia truncada, medida directamente (incluye su covarianza y el sesgo);
sustituye a la suma V<sub>filtro</sub> + V<sub>tend</sub> de la v1.2, que suponía los dos errores independientes (el
control sintético preregistrado lo refutó, §9). V<sub>filtro</sub> y V<sub>tend</sub> se siguen calculando como
diagnóstico, pero no entran en σ̂.

- **V<sub>conj</sub> (regla exacta, v1.3).** Se mide en cada reestimación T (primer corte y cada enero), sin etiqueta,
  con los niveles conocidos en la fecha de decisión de T y la versión de parámetros (λ, φ, ρ, q, d<sub>i</sub>, medias)
  recién estimada en T, y se congela hasta la siguiente reestimación:
  1. ℓ<sub>i</sub> = mes de T − último mes observado de la coincidente i en los niveles de T (el borde desigual del
     corte).
  2. Para cada mes s de **1968-06 a T − 65** (meses con ventana de tendencia completa en los niveles de T): niveles
     pseudo-tiempo-real = niveles de T de cada coincidente truncados en s − ℓ<sub>i</sub>; `claims_4w_yoy` y
     `philly_neworders` de las filas ≤ s (con la marca `philly_pre1990_nan` si aplica). Ĝ<sup>ps</sup><sub>s</sub> =
     el Ĝ de §3-§4 (mismo código: τʳ de esos datos, filtro con la versión de T, composición con el código de la
     etiqueta).
  3. e<sub>s</sub> = Ĝ<sup>ps</sup><sub>s</sub> − G<sub>s</sub>(niveles de T), el segundo con el código de la etiqueta y
     los niveles completos de T (el de V<sub>tend</sub>).
  4. V<sub>conj</sub> = media de e<sub>s</sub>² sobre los meses con Ĝ<sup>ps</sup><sub>s</sub> finito.
  - Declarado: los parámetros de T se estimaron con esos mismos meses (algo optimista) y el borde desigual se toma el
    del corte T para todos los s.
  - Las sensibilidades `_coinc` y `_ar1` miden V<sub>conj</sub> con su propio factor; `_norev` hace V<sub>rev</sub> = 0;
    `_revpit` solo cambia V<sub>rev</sub>.

- **V<sub>filtro</sub>** (tasas que faltan; v1.3: solo diagnóstico). Linealización de G en las tasas: ∂G<sub>t</sub>/∂r<sub>i,m</sub> =
  c<sub>i,m</sub> = (1/n<sub>t</sub>)·(2/3)·w<sub>m−t</sub>/σ<sub>i</sub>, con w = (1, 2, 3, 3, 3, 3, 2, 1) para m = t−3
  … t+4 y n<sub>t</sub> = indicadores presentes. V<sub>filtro</sub> = c′Σc con Σ = covarianza conjunta de las tasas que
  faltan (§3, en unidades de r: d<sub>i</sub>d<sub>j</sub>·Cov). Se ignora el efecto de esas tasas sobre la mediana de
  la tendencia y sobre σ<sub>i</sub> (1 de 61 valores; declarado). Un test sintético compara la linealización con el
  código exacto de la etiqueta (tolerancia 1 %, `tests/test_regime_components.py`).
- **V<sub>rev</sub>** (revisión de las tasas ya publicadas; Jacobs-van Norden / Kishor-Koenig, versión mínima). Solo en
  modo `vintage` y solo para las series que en esa fecha entran desde una vintage (en `latest_truncated`, 0).
  V<sub>rev</sub> = Σ<sub>i,m conocido</sub> c<sub>i,m</sub>²·v<sub>i</sub>(edad), edad = mes de decisión − m.
  - **Tabla v(edad), fijada antes de la pasada de desarrollo y sin etiqueta:** con las vintages ALFRED de INDPRO y
    PAYEMS de la instantánea congelada de la etiqueta, fechas de decisión y meses observados **≤ 2004-12**,
    error = r en la vintage de la fecha − r en la última vintage (la que usa la etiqueta), y v = **error cuadrático
    medio** por edad: 1, 2, 3, 4, 5, 6, 7-12, ≥ 13 meses. Se commitea en `research/trials/m2/revision_var.json` antes
    de la primera carga de la etiqueta para M2. Una sola tabla, la misma en todos los cortes y en el bloqueado.
  - **Declarado NO PIT (v1.1, decisión del usuario 24-oct sobre M-2):** la referencia (última vintage) incluye
    revisiones publicadas después de 2004 (*benchmarks*, cambios de base) de meses ≤ 2004, así que en un corte de
    1985 la escala de V<sub>rev</sub> usa información que no se conocía en 1985. Es **un hiperparámetro de escala
    fijo**, de la misma naturaleza que s<sub>G</sub> = 0,40 de la ficha (primera publicación − última vintage), y es
    coherente con el objetivo puntuado (la etiqueta oficial con la última vintage). No lee ningún mes ≥ 2005 ni la
    etiqueta. Excepción declarada al "todo ≤ corte" de §3: es la única.
  - **Muestra de Var(r<sub>i</sub>) (v1.1, M-2):** Var(r<sub>i</sub>) = varianza (ddof = 0) de r<sub>i</sub> =
    100·Δln(nivel) en la **última vintage**, meses **1968-06 → 2004-12**, para las cuatro series; se calcula una vez y
    se guarda en el mismo `revision_var.json`. ρ̄(edad) = media simple de v<sub>INDPRO</sub>(edad)/Var(r<sub>INDPRO</sub>)
    y v<sub>PAYEMS</sub>(edad)/Var(r<sub>PAYEMS</sub>), con esa misma muestra.
  - W875RX1 y CMRMTSPL no tienen vintages ≤ 2004 (empiezan en 2010-05 y 2013-06): cuando entren desde una vintage
    (solo en el bloqueado) se usa v<sub>i</sub>(edad) = ρ̄(edad)·Var(r<sub>i</sub>) (supuesto declarado).
  - **Sensibilidad PIT** `m2_struct_g_revpit` (§7, **no principal**, no entra en el pool ni elige): la tabla se
    reestima en cada reestimación de enero T solo con vintages publicadas ≤ T: error = r en la vintage de la fecha s −
    r en la vintage de T, para fechas s ≤ T − 24 meses (la referencia ha tenido ≥ 24 meses para revisar) y meses
    observados ≤ s, desde la primera vintage disponible; v = error cuadrático medio por tramo de edad; un tramo con
    < 30 pares toma el valor del tramo más joven con ≥ 30 (si no hay ninguno, V<sub>rev</sub> = 0 en ese corte).
    Var(r<sub>i</sub>) y ρ̄ con la vintage de T, meses 1968-06 → T. Solo modo `vintage`.
  - No se propaga la revisión a la previsión del filtro (efecto de segundo orden; declarado).
- **V<sub>tend</sub>** (tendencia truncada y σ<sub>i</sub> con datos ≤ t). Se mide en cada reestimación de enero,
  con los niveles conocidos en el corte T y sin etiqueta: para cada mes s de 1965-01 a T−65,
  e<sub>s</sub> = G<sub>s</sub>(niveles de T truncados en s+4) − G<sub>s</sub>(niveles de T), las dos con el código de
  la etiqueta. El primero reproduce la situación del borde (tendencia hacia atrás, σ con datos ≤ s+4) sin error de
  previsión; el segundo es G de la etiqueta recalculada en T con la ventana de tendencia completa.
  V<sub>tend</sub> = media de e<sub>s</sub>² (incluye el sesgo). Se congela hasta la siguiente reestimación. (v1.3:
  solo diagnóstico.)
- **Probabilidad:** el arnés (v2.3, §5c) convierte (Ĝ<sub>t</sub>, σ̂<sub>t</sub>) en P(G alto) =
  Φ(Ĝ<sub>t</sub>/√(σ̂²<sub>t</sub> + s<sub>G</sub>²)) con s<sub>G</sub> = 0,40 de la ficha. **Sin capa de calibración**
  en la principal: la escala sale de la aritmética de la etiqueta, no de un ajuste.

## 5. Eje I, interfaz y nombre

- `m2_struct_g`: `ContinuousAxisModel` con `continuous_axes = ("G",)`; `axis_features = {"G": ("claims_4w_yoy",
  "philly_neworders"), "I": ()}`; `uses_persistence = True` (solo para el eje I) y `uses_pit_levels = True` (§8-1).
- **Eje I = el de M0** (persistencia calibrada, eps 1e-3, L2 1,0; decisión del usuario: eje I = M0). Por eso la
  log-loss de 4 cuadrantes de M2 − M0 es exactamente la mejora del eje G (harness.md §5b).
- El objetivo continuo `g` que pasa el arnés **no se usa para estimar nada**; solo se guarda para diagnósticos
  (residuo walk-forward, informativo).

## 6. Ventanas, corridas y orden (desarrollo, ≤ 2004)

**Ventanas fijadas por regla** (las fechas se anotan en §9 con la sonda de elegibilidad, que solo cuenta meses y no
puntúa nada, **después** de este push):
- **larga** `m2_long`: desde W<sub>G</sub> = primer corte en el que M2 **y** M3 (`m3_tvtp_spec.md`) son elegibles en
  todos los cortes siguientes de los dos modos (mínimos del arnés: 120 meses, ≥ 2 recesiones conocidas, ≥ 8 cambios de
  G; ventana del eje G desde 1968-05 por Filadelfia → se espera W<sub>G</sub> ≈ 1978-07…1978-10) hasta 2004-12.
  Subperiodos [W<sub>G</sub>, 1989-12] y [1990-01, 2004-12].
- **comparable** con M1 v2: 1989-10 → 2004-12.
- `test_start` = 1956-10 (M0 y la persistencia reproducen sus baselines), `allow_shrink: false`, `refit_every: 1`,
  embargo 6, pesos de madurez, `pit_version: "0.4"`, modos vintage (principal) y latest_truncated (sensibilidad).

| corrida | ventana | modelos | para qué |
|---|---|---|---|
| `m2_long` | larga | persistencia, climatología, M0, **m2_struct_g**, `m1v2_g` (referencia) | M2 frente a M0 |
| `m2_m1cmp` | 1989-10 → 2004-12 | M0, m2_struct_g, `m1v2_logit_axis` | comparación con M1 v2 en sus meses |
| `s_pit_001` | larga, matriz `vintage_filadelfia_prudente` | M0, m2_struct_g | regla operativa de S-PIT-001 (§2) |
| `m2_long_phnan` | larga | como `m2_long`, con `philly_neworders` < 1990-07 = NaN | **solo si S-PIT-001 se dispara**: pasa a ser la corrida principal de M2 |
| `m2_sens` | larga, vintage | M0 y las 5 sensibilidades de §7 | sensibilidades (no eligen) |

`m2_m1cmp` y `m2_sens` se corren con la versión de M2 que resulte de S-PIT-001 (la principal o la de NaN).

**Orden** (todo al registro de pruebas y al trial log, también lo que falle):
1. Este push. 2. Extensiones del arnés v2.4 (§8) e implementación, con tests sintéticos (abajo) en verde. 3. Tabla
v(edad) (§4) sin etiqueta → commit. 4. Sonda de elegibilidad (solo recuentos) → ventanas en §9 → commit. 5. Placebo
(abajo) → commit. 6. Corridas `--official`, desde un árbol limpio, **en este orden fijo** (v1.1, M-4):
   - 6a. `m2_long`; 6b. `s_pit_001`;
   - 6c. **resolución de S-PIT-001** con la regla de §2 (Δ<sub>S</sub>, h, dispara sí/no), escrita en §9 con los dos
     `run_id`, **commit y push** antes de seguir;
   - 6d. si se disparó, `m2_long_phnan`;
   - 6e. `m2_m1cmp` y `m2_sens` con la versión resuelta.
   Ninguna corrida de M3 ni del pool empieza antes del push de 6c (`m3_tvtp_spec.md` §5, `pool_spec.md` §7).
7. Validador + Estratega.

**Controles antes de la etiqueta real:**
- **Señal plantada (sintético):** un panel generado con el modelo de §3 y parámetros conocidos; el estimador recupera
  λ, φ, ρ (tolerancias en el test) y la cobertura del intervalo del 80 % de G sintético está entre 0,75 y 0,85.
  **v1.3 (fijado antes de correrlo):** generador `tests/m2_synth.py`, **semillas 3, 7, 11 y 21**, cortes mensuales
  1980-01 → 2004-08, G verdadero = el de la etiqueta con los niveles sintéticos completos; **las cuatro** coberturas del
  80 % tienen que caer en **[0,75; 0,85]**. Si alguna queda fuera, no se itera el diseño: se para y se pregunta al
  usuario.
- **PIT por truncamiento:** la predicción en t no cambia si se alteran los niveles o las variables posteriores a la
  fecha de decisión (3 cortes × 2 modos, sintético y con la instantánea ≤ 2004).
- **Composición:** con tasas futuras conocidas (oráculo sintético), Ĝ = G del código de la etiqueta bit a bit.
- **Placebo pareado** (arnés §9b): etiqueta ≤ 2004 barajada en bloques de 24, semillas 1…20, refit cada 12 meses. Como
  M2 no usa la etiqueta, Δ = ll(M0) − ll(M2) debe ser ≤ 0 (mide G real frente a una etiqueta sin relación). Reglas:
  **fuga** si la media > 0,02 nats; **aviso** si prueba de signo unilateral p < 0,01 o t > 3. Con fuga o aviso no se
  corre con la etiqueta real hasta entenderlo.

## 7. Sensibilidades preregistradas (se publican siempre; NO eligen ni entran en el pool)

| id | cambio | por qué |
|---|---|---|
| `m2_struct_g_platt` | capa Λ(c + b·logit P) sobre la P de M2, L2 = 1 sobre b, eps 1e-3 (como M0) | ¿la escala σ̂ está bien? |
| `m2_struct_g_norev` | V<sub>rev</sub> = 0 | aporte de la varianza de revisión |
| `m2_struct_g_revpit` | tabla v(edad) PIT: solo vintages ≤ T, reestimada cada enero (§4; v1.1, decisión del usuario sobre M-2) | ¿importa que la principal no sea PIT? |
| `m2_struct_g_coinc` | factor solo con las 4 coincidentes (sin peticiones de paro ni Filadelfia) | aporte de los datos del mes t |
| `m2_struct_g_ar1` | factor AR(1) | dinámica del factor |
| modo `latest_truncated` | (todas las corridas) | sensibilidad de modo |

*Plucking* (término de recuperación) **no** entra ni como sensibilidad aquí: el Investigador lo propone como
sensibilidad post hoc; se deja para una spec aparte si el usuario lo pide, para no abrir más comparaciones.

## 8. Qué necesita del núcleo (arnés v2.4; no implementado, se hará con tests y sin etiqueta)

1. **`uses_pit_levels`:** `info["pit_levels"](fecha)` → niveles de INDPRO, PAYEMS, W875RX1, CMRMTSPL conocidos en esa
   fecha de decisión (`PITLabeler.levels_at`, mismo modo, misma barrera ≥ 2005) y, por serie, si vienen de una
   vintage. Solo fechas ≤ la fecha de decisión del corte (el arnés lo comprueba). Queda en el registro de accesos.
2. **`info["features_history"]`:** filas de la matriz con las variables declaradas por el modelo, desde el inicio de
   la ventana del eje hasta el mes del corte inclusive (sin columnas de la etiqueta; `assert_no_forbidden`).
3. **`info["decision_dates"]`** de las filas de prueba (con refit_every = 1, una fila).
4. Informe: `mejora_logloss.sd_mensual` (desviación de d; `power_holdout.md` §4), la **autocorrelación de d en los
   retardos 1-24** (`mejora_logloss.acf_1_24`; Validador M-3) y la detección declarada 3 m × 80/20
   (`m3_tvtp_spec.md` §6) para todos los modelos.
5. **Estudio de eventos por episodio** (`pool_spec.md` §5b; decisión del usuario 24-oct, C): d<sub>t</sub> frente a M0
   en k = −6 … +8 alrededor de cada giro v2.1 de G y por episodio; M2 se incluye en las corridas `m2_m1cmp` y en la
   corrida principal **resuelta** por S-PIT-001: `m2_long` si no se dispara, `m2_long_phnan` si se dispara (v1.2,
   Validador N-3). Las predicciones P1, P4 y P7 sobre M2 se leen en esa corrida resuelta.
6. Diagnóstico `fit_converged` por reestimación (§3).

## 9. Cambios post hoc (técnicos) y fechas fijadas por regla

| fecha | cambio | por qué | qué se había visto |
|---|---|---|---|
| — | (aquí irán W<sub>G</sub>, la tabla v(edad) y la resolución de S-PIT-001) | | |
| 2026-10-24 | **tabla v(edad)** fijada (§4), antes de cualquier carga de la etiqueta para M2: `research/trials/m2/revision_var.json` (commit `8e34264`, empujado 12:54:43Z) | regla de §4 (vintages ALFRED de INDPRO/PAYEMS de la instantánea, fechas de decisión de la matriz PIT ≤ 2004-12, todos los meses observados ≤ 2004-12; Var(r) 1968-06 → 2004-12) | nada de la etiqueta: solo niveles y vintages |
| 2026-10-24 | **W<sub>G</sub> = 1978-10** (sonda de elegibilidad, solo recuentos; `research/trials/m2/elegibilidad.json`, `src/models/pool_dev.py probe`, 12:54:51-12:55:47Z) → `m2_long` = 1978-10 → 2004-12, subperiodos [1978-10, 1989-12] y [1990-01, 2004-12] | regla de §6: primer corte desde el que los ejes G de M2 y M3 (y el I) son elegibles en todos los cortes siguientes de los dos modos (120 meses, ≥ 2 recesiones, ≥ 8 cambios de G; ventana del eje G desde 1968-05) | recuentos de meses, recesiones y cambios de G de la etiqueta recalculada ≤ T; ninguna puntuación ni ningún modelo |
| 2026-10-24 | ninguno — **control de señal plantada NO superado** (§6), anotado; espera decisión del usuario antes de `m2_long` | `src/models/pool_dev.py controls` (sintético): cobertura del intervalo del 80 % de G = **0,878** (semilla 7, 296 cortes; spec: 0,75-0,85); semillas 3/11/21: 0,855 / 0,909 / 0,922 (`research/trials/m2/controles_sinteticos.json`, `controles_m2_semillas_extra.json`). λ, φ, ρ se recuperan bien. Diagnóstico (`controles_m2_diagnostico.json`): V<sub>filtro</sub> y V<sub>tend</sub> están cada uno ≈ calibrados (ECM 0,196 frente a 0,232; 0,089 frente a 0,074), pero el error del filtro y el de la tendencia truncada tienen correlación **−0,31**, y §4 los suma como independientes (supuesto declarado): σ̂ sobrestima | solo datos sintéticos; placebos con la etiqueta barajada (Δ M2 −0,37, M3 −0,016, pool −0,022: sin fuga ni aviso). Ningún dato de la etiqueta real para M2. No se ha cambiado nada del modelo |
| 2026-10-24 | **v1.2 → v1.3** (decisión del usuario sobre Q0; push a priori antes de cualquier corrida con la etiqueta real) | ver la tabla de cambios v1.3, abajo: el control sintético preregistrado de §6 falló (cobertura del 80 % = 0,878 / 0,855 / 0,909 / 0,922 con las semillas 7 / 3 / 11 / 21) por la correlación −0,31 entre el error del filtro y el de la tendencia | el fallo lo detectó el **sintético**, no la etiqueta. Hasta este push la etiqueta solo se ha leído en la sonda de elegibilidad (recuentos de la etiqueta recalculada ≤ T, 12:54:51-12:55:47Z) y en los placebos con la etiqueta ≤ 2004 **barajada** (12:56-13:07Z), más las suites (tests preexistentes). Ningún resultado de M2 con la etiqueta real |
| 2026-10-24 | **v1.0 → v1.1** (push a priori, antes de implementar y de cualquier contacto con la etiqueta para M2/M3/pool) | ver la tabla de cambios v1.1, abajo | nada de M2/M3/pool: sin implementación, sin datos, sin corridas. Solo las revisiones del Validador y del Estratega (documentales y sintéticas) |
| 2026-10-24 | ninguno (nota de proceso, **completada en v1.1**, Validador B-1) | lecturas de la etiqueta del 24-oct **anteriores** al push de v1.0 (09:53:14Z), todas en `development` y ≤ 2004-12 (o caché ≤ 2004; las denegadas son tests de la barrera ≥ 2005), según `research/trials/full/label_access.jsonl` y `research/trials/label_access.jsonl` (horas del registro en local, UTC+2; aquí en UTC): **(1)** suite completa 08:47:38-08:52:20Z (102 accesos, 5 denegados); **(2)** suite completa 08:57:31-09:02:12Z (ídem); **(3)** `src/models/power.py` 09:05:52Z (1 acceso, también en el registro principal: marca de giros ≤ 2004 para la potencia); **(4)** reproducciones de M1 v1 con `record=False` 09:10:59-09:13:25Z y 09:20:10-09:20:14Z (18 accesos); **(5)** suite completa 09:47:59-09:51:07Z (102 accesos, 5 denegados). Ninguna después del push de v1.0 ni hasta el push de v1.1 | (1), (2), (5): nada de M2, M3 ni del pool (no existían); los tests preexistentes solo reproducen M0, baselines, placebos y ensayos en seco ya conocidos desde el 16-oct. (3): las d<sub>t</sub> de M1 y los MDE de `power_holdout.md` **sí informan el diseño** (`sd_mensual`, puerta de gasto, expectativa de A7), declarado en §0. (4): resultados de M1 v1 ya conocidos. La spec ya estaba escrita y no se cambió por ninguna de ellas. "Antes de cualquier contacto con la etiqueta" significa **para M2/M3/pool** |
| 2026-10-24 | **v1.1 → v1.2** (push a priori, antes de implementar nada que lea datos y antes de cualquier contacto con la etiqueta para M2/M3/pool) | ver la tabla de cambios v1.2, abajo (Validador, re-auditoría `docs/validation/2026-10-24_specs_pool_v4_reaudit.md`, N-1…N-7) | nada de M2/M3/pool: sin implementación, datos ni corridas |
| 2026-10-24 | ninguno (nota de proceso, v1.2, Validador N-7) | lectura de la etiqueta **posterior** al push de v1.1 (10:46:29Z) y anterior al de v1.2: **(6)** suite completa 10:47:11-10:50:19Z (102 accesos ≤ 2004-12, 90 desde la caché, 5 denegados de la barrera ≥ 2005, todos de pytest con `git_head` = `d1bde77`). No hay ninguna otra entre los dos pushes (el Validador solo leyó registros y datos sintéticos) | nada de M2, M3 ni del pool (no existían): los tests preexistentes reproducen M0, baselines, placebos y ensayos en seco ya conocidos. Posterior al push de v1.1: no afecta a la prioridad |

**Cambios v1.0 → v1.1** (2026-10-24; ninguno se ha probado con datos):

| # | sección | v1.0 | v1.1 | motivo |
|---|---|---|---|---|
| 1 | §1, §3 | `claims_4w_yoy` carga en la media de 12 meses de f, λ<sub>c</sub>·(1/12)·Σ<sub>k=0..11</sub> f<sub>m−k</sub> | carga en **f<sub>m</sub> − f<sub>m−12</sub>** | Estratega (imprescindible 1): la tasa interanual de un **flujo** (despidos nuevos) responde al ritmo del mes; la forma de stock la retrasa ≈ 6 m al entrar y la lee al revés al principio de la recuperación |
| 2 | §3 | estado aumentado de dimensión 46 (retardos 0…11 de f) | **47** (retardos 0…12 de f) | consecuencia de 1 |
| 3 | §3 | "statsmodels o implementación propia" | statsmodels `MLEModel` 0.15.0, única | Validador B-2: dos implementaciones con óptimos locales pueden dar parámetros distintos |
| 4 | §3 | arranque desde el óptimo anterior; panel balanceado sin definir; sin regla de no convergencia | arranque determinista fijo en cada reestimación; panel = tramo contiguo más largo con las 6 (o las 4) series; sin convergencia → parámetros vigentes + `fit_converged = false` | Validador B-2 (dependencia del primer corte; ensayo en seco) |
| 5 | §4 | V<sub>rev</sub> frente a la última vintage, sin declarar; muestra de Var(r) sin fijar | **declarado no PIT** (como s<sub>G</sub>); Var(r) en la última vintage 1968-06 → 2004-12; sensibilidad PIT `m2_struct_g_revpit` (no principal) | Validador M-2; decisión del usuario 24-oct (B) |
| 6 | §2, §6 | S-PIT-001 "tal como está preregistrada", resuelta después de `m2_long`, sin orden respecto a M3/pool | regla operativa (\|Δ<sub>S</sub>\| > semiamplitud del IC 95 %), orden 6a-6e, resolución empujada antes de M3/pool, la versión resultante es la única aguas abajo | Validador M-4 |
| 7 | §8 | — | ACF de d (1-24) y estudio de eventos por episodio para M2 | Validador M-3.2; decisión del usuario 24-oct (C) |
| 8 | §9 | nota de proceso con una sola pasada de la suite | todas las lecturas del 24-oct ≤ 2004 | Validador B-1 |

**Cambios v1.1 → v1.2** (2026-10-24; re-auditoría del Validador; ninguno cambia el modelo ni se ha probado con datos):

| # | sección | v1.1 | v1.2 | motivo |
|---|---|---|---|---|
| 1 | §3 (cadencia) | "…y arrancando del óptimo anterior" | frase borrada: el arranque es el determinista fijo | Validador N-1 (contradicción interna) |
| 2 | §2 (S-PIT-001) | la regla solo exigía la misma forma | d<sup>pr</sup>, d<sup>fp</sup> finitas en todos los meses, alineadas y con el mismo índice; si no, error y parada | Validador N-2 (con un NaN la regla "no se disparaba" en silencio) |
| 3 | §2 (S-PIT-001) | "la marca `philly_pre1990_nan`" sin parámetro | `model_params.m2_struct_g: {philly_pre1990_nan: false\|true}`, heredado por M3, `m3_ctp_g`, el pool y las sensibilidades | Validador N-6 |
| 4 | §3 (test del ensayo en seco) | igualdad de parámetros en cada enero | solo en las reestimaciones con `fit_converged = true` en las dos corridas; las excepciones se informan | Validador N-4 |
| 5 | §8-5 | estudio de eventos de M2 en `m2_long` | en la corrida **resuelta** por S-PIT-001 (`m2_long` o `m2_long_phnan`) y en `m2_m1cmp`; P1, P4 y P7 sobre M2 se leen ahí | Validador N-3 |
| 6 | §9 | — | nota de proceso con la suite posterior al push de v1.1 | Validador N-7 |
| 2026-10-24 | ninguno de diseño (nota de proceso) | filas añadidas en el commit `1cdd9e7` (empujado 13:07:31Z), **después** de las primeras lecturas de la etiqueta para M2/M3/pool: sonda de elegibilidad (recuentos de la etiqueta recalculada ≤ T, 12:54:51-12:55:47Z) y placebos con la etiqueta ≤ 2004 **barajada** (12:56-13:07Z). Solo contienen (a) las fechas que la propia spec fija por regla tras la sonda (W<sub>G</sub>, ventana del pool), (b) la tabla v(edad) ya empujada a las 12:54:43Z y (c) el resultado del control sintético de M2 | ningún resultado con la etiqueta real; el texto del modelo, previas, ventanas por regla y criterios no cambian. La sobrecobertura de M2 queda como **pregunta para el usuario**, no como cambio |

**Cambios v1.2 → v1.3** (2026-10-24; decisión del usuario sobre Q0 tras el control sintético; ninguno probado con la
etiqueta real):

| # | sección | v1.2 | v1.3 | motivo |
|---|---|---|---|---|
| 1 | §4 | σ̂² = V<sub>filtro</sub> + V<sub>rev</sub> + V<sub>tend</sub> (independientes, supuesto declarado) | σ̂² = **V<sub>conj</sub>** + V<sub>rev</sub>, V<sub>conj</sub> = varianza del error conjunto medida directamente en pseudo-tiempo-real con los niveles de T (regla exacta en §4); V<sub>filtro</sub> y V<sub>tend</sub> quedan como diagnóstico | control sintético de §6 no superado (0,878 / 0,855 / 0,909 / 0,922); componentes ≈ calibrados por separado, correlación −0,31 (`research/trials/m2/controles_m2_diagnostico.json`) |
| 2 | §6 | cobertura del 80 % en [0,75; 0,85] sin semillas fijadas | semillas 3, 7, 11, 21 fijadas antes de correrlo; las cuatro dentro de [0,75; 0,85]; si no, parada y pregunta | decisión del usuario |
