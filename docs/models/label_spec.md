---
documento: ficha de la etiqueta de régimen
version: 1.0
fecha: 2026-10-14
estado: CONGELADA (aprobada por el usuario el 2026-10-14). Cualquier cambio = v1.1 / v2.0 con revalidación completa
---

# Ficha de la etiqueta de régimen — nowcast EE. UU.

Define **qué es el régimen "verdadero"** de cada mes. Es lo que los modelos intentan adivinar con la información
disponible en cada fecha. Se fija **antes** de modelar y no se toca para que los modelos salgan mejor.

## 1. Decisiones tomadas (usuario, 2026-10-14)

| decisión | elección |
|---|---|
| Objetivo | **Nowcast** del régimen del mes actual. Forecast a 6 meses más adelante, con validación y métricas propias |
| Taxonomía | 4 cuadrantes crecimiento × inflación |
| Crecimiento alto/bajo | **Ritmo frente a tendencia** |
| Inflación alta/baja | **Subyacente frente a umbral fijo** |
| Fronteras | **Etiquetas probabilísticas** (y una etiqueta dura derivada) |
| Geografía | **EE. UU. primero** (1950-hoy); la zona euro después, con ficha propia |
| Capas aparte (no son régimen) | Recesión (NBER) y, más adelante, estrés de liquidez/crédito |

## 2. Principio: la etiqueta usa datos definitivos; las variables, no

- **Etiqueta:** se calcula con la **última vintage** (datos revisados) y puede usar ventanas centradas, que miran meses
  hacia delante. Es la mejor estimación a posteriori de lo que estaba pasando.
- **Variables de los modelos:** solo lo publicado hasta la fecha de decisión (ver `docs/models/pit_calendar.md`).
- Por eso la etiqueta **nunca** puede entrar como variable, ni con retardo.

## 3. Eje de crecimiento (G)

**Indicadores** (el conjunto coincidente del NBER, mensual, última vintage):

| serie | qué mide | desde |
|---|---|---|
| `INDPRO` | producción industrial | 1919 |
| `PAYEMS` | empleo no agrícola | 1939 |
| `W875RX1` | renta personal real sin transferencias | 1959 |
| `CMRMTSPL` | ventas reales de manufactura y comercio | 1967 |

**Cálculo**, para cada indicador *i* y mes *t*:
1. Nivel suavizado: media de 3 meses del nivel, **centrada** en el mes (m−1, m, m+1).
2. Ritmo: g<sub>i,t</sub> = variación logarítmica anualizada (×2) entre el nivel suavizado **en t+3 y en t−3**. Usa los
   niveles de t−4 a t+4 y equivale a una media triangular (1,2,3,3,3,3,2,1) de las tasas mensuales **centrada en t**:
   la etiqueta del mes t describe el crecimiento del mes t, no el de meses anteriores.
3. Tendencia: τ<sub>i,t</sub> = mediana **centrada** de g<sub>i</sub> en ±60 meses (10 años). En los extremos de la
   muestra la ventana se trunca (ver §7).
4. Desviación estandarizada: z<sub>i,t</sub> = (g<sub>i,t</sub> − τ<sub>i,t</sub>) / σ<sub>i</sub>, donde σ<sub>i</sub>
   es la desviación robusta (MAD × 1,4826) de g<sub>i</sub> − τ<sub>i</sub> en toda la muestra.

**Compuesto:** G<sub>t</sub> = media de los z<sub>i,t</sub> disponibles. Mínimo 2 indicadores: entre 1950 y 1958 solo
están INDPRO y PAYEMS, y esos meses se marcan con `cobertura_g = 2`.

**Lectura:** G > 0 = la economía crece por encima de su tendencia; G < 0 = por debajo.

## 4. Eje de inflación (I)

**Serie principal:** PCE subyacente (`PCEPILFE`), desde 1959 (primer valor centrado: 1959-04). Es la medida de
referencia de la Fed.
- 1957-04 a 1959-03: IPC subyacente (`CPILFESL`) menos 0,4 pp (diferencia media IPC − PCE subyacentes), anotado.
- 1950-01 a 1957-03: IPC general (`CPIAUCSL`), marcado `fuente_i = headline`. Es un periodo con más ruido (guerra de
  Corea); 1950-1954 tiene peso 0 (§7).

**Cálculo:** I<sub>t</sub> = variación del índice **de t−3 a t+3**, anualizada, en % (ventana de 6 meses centrada en t).

**Umbral fijo:** **κ = 2,5 %**, el objetivo de la Fed (2 %) más un margen de tolerancia. Se mide en PCE subyacente; con
IPC el equivalente sería ~2,9 %.

## 5. Probabilidades por cuadrante (etiqueta probabilística)

Cada eje se convierte en una probabilidad según su distancia al umbral, escalada por la incertidumbre de medida:

- P(G alto)<sub>t</sub> = Φ(G<sub>t</sub> / s<sub>G</sub>)
- P(I alta)<sub>t</sub> = Φ((I<sub>t</sub> − κ) / s<sub>I</sub>)

s<sub>G</sub> y s<sub>I</sub> salen del ruido de revisión de ALFRED en las mismas unidades del eje y en la v1.0 son
**fijas**: **s<sub>G</sub> = 0,40** (z; INDPRO + PAYEMS, 1955-2024) y **s<sub>I</sub> = 0,31 pp** (PCE subyacente,
2000-2024). La estimación con los cuatro indicadores daba 0,33, pero solo cubre 2013-2024, un periodo de revisiones
pequeñas. Detalle en `docs/models/label_v1.0_checks.md`.

Φ = normal acumulada. Ejemplo con s<sub>G</sub> = 0,5: G = 0 da 50 %; G = +0,5 da 84 %; G = +1 da 98 %.

| cuadrante | G | I | probabilidad |
|---|---|---|---|
| **Expansión** | alto | baja/moderada | P(G alto) · (1 − P(I alta)) |
| **Late cycle / sobrecalentamiento** | alto | alta | P(G alto) · P(I alta) |
| **Estanflación** | bajo | alta | (1 − P(G alto)) · P(I alta) |
| **Crecimiento bajo / desinflación** | bajo | baja | (1 − P(G alto)) · (1 − P(I alta)) |

- Columnas: `p_expansion`, `p_late_cycle`, `p_stagflation`, `p_low_growth_disinfl` (en la v0.1, `p_slowdown`; alias en el
  `meta.json`). La palabra "recesión" queda reservada a la capa `usrec` (§6): un mes de crecimiento bajo y desinflación
  no es necesariamente una recesión.

- Se supone independencia entre ejes al combinar. Es una simplificación documentada; la correlación G-I se revisa en §8.
- **Etiqueta dura** = cuadrante de mayor probabilidad. Sirve para los baselines de reglas, para el acierto y para leer
  los resultados.
- **Frontera:** si la probabilidad máxima es < 0,55, el mes se marca `frontera = true`. Se puntúa igual en log-loss, pero
  se informa aparte.
- **Métrica principal de los modelos:** log-loss / Brier **contra las probabilidades de la etiqueta** (objetivo
  "blando"), frente a la persistencia.

## 6. Capas aparte (no cambian el cuadrante)

- **Recesión:** `USREC` (NBER), ex post. Se usa para validar la etiqueta (§8) y como objetivo secundario. No es un
  quinto régimen.
- **Estrés de liquidez/crédito:** más adelante, con su propia ficha.

## 7. Extremos de la muestra y etiqueta provisional

- La ventana centrada de tendencia necesita 60 meses de futuro. En los últimos 60 meses se trunca (usa lo que hay) y,
  además, los datos de los últimos meses aún se revisarán.
- Por eso, los **últimos 54 meses** llevan `provisional = true`. No puntúan ni entrenan (ni el periodo bloqueado ni el
  backtest) y se recalculan cada mes hasta que maduran. El número sale del estudio de revisión
  (`docs/models/label_revision_study.md`, `src/labels/revision_study.py`), con una regla declarada antes de ver los
  resultados. Se recalculó la etiqueta solo con datos ≤ T en 100 cortes semestrales (1975-2024), con dos variantes:
  la última vintage truncada y otra con INDPRO/PAYEMS de ALFRED a fecha T. La regla busca el menor k desde el corte a
  partir del cual la concordancia de la etiqueta dura es ≥ 95 % **y** el Δp medio es ≤ 0,05 de forma sostenida. Sale
  k* = 55, menos el desfase de 4 meses de la etiqueta, redondeado a múltiplo de 6: 54.
- **Uso en el backtest:** los meses con `provisional = true` o `weight = 0` no puntúan ni entrenan, con
  **`embargo_months = 6`** entre entrenamiento y prueba (la etiqueta de t usa datos hasta t+4). Ambos valores están en
  el `meta.json`.
- Con el inicio pasa lo mismo: 1950-1954 tienen la ventana truncada hacia atrás y se marcan
  `tendencia_truncada = true`.
- **Final de la muestra con ventanas centradas:** G(t) necesita niveles hasta t+4 e I(t) hasta t+3, así que la etiqueta
  termina ~4 meses antes que el último dato y la del mes t está disponible ~5 meses después. En el backtest, el
  purging/embargo debe cubrir ese horizonte.
- **Pesos:** columna `weight` = 0 en 1950-1954 (IPC general con la guerra de Corea y tendencia truncada) y 1 en el resto.
  Los meses con peso 0 se conservan en el fichero, pero **no puntúan** (ni en el backtest ni en las comprobaciones).

## 8. Comprobaciones antes de congelar (sentido, no ajuste)

Sirven para detectar errores de cálculo, **no para ajustar los parámetros** hasta que la etiqueta "cuente la historia
que queremos". Si alguna falla, se documenta el porqué antes de cambiar nada.

| comprobación | criterio esperado |
|---|---|
| Meses NBER de recesión | ≥ 85 % con P(G alto) < 0,5 |
| Correlación con CFNAI-MA3 contemporáneo (1967+) | > 0,7 |
| Correlación con CFNAI agregado en la misma ventana que G (t−3…t+4) | > 0,7 |
| Correlación con la brecha de producción (GDPC1 vs GDPPOT, trimestral) | > 0,6 en cambios |
| Episodios: 1973-75 y 1979-80 | estanflación dominante |
| Episodios: 2021-T2 a 2022 | sobrecalentamiento / estanflación |
| Episodios: 1995-99 | expansión |
| Episodios: 2008-09 y 2020-T2 | crecimiento bajo / desinflación |
| Distribución por cuadrante | ninguno < 10 % de los meses |
| Duración media de los regímenes duros | ≥ 6 meses |
| Correlación G-I | se informa; si es \|ρ\| > 0,3, se revisa el supuesto de independencia |

Muestra: meses con `weight = 1` y no provisionales. Cada criterio se informa también sin meses de frontera, junto con
el acierto esperado de la etiqueta dura (media de la probabilidad máxima).

## 9. Fecha de decisión del nowcast

- **Último día hábil del mes t**, con todo lo publicado hasta ese día. Se nowcastea el régimen del mes t, para el que
  aún no hay casi ningún dato oficial.
- Variante a evaluar también: día 15 del mes t+1, con el empleo y el IPC de t ya publicados. Se informa aparte.

## 10. Versionado

- Esta ficha es la **v1.0, CONGELADA**. Se etiqueta en git (`label-v1.0`). La serie está en
  `data/archive/labels/regime_us_v1.0.parquet` y su `meta.json` guarda los parámetros, el hash del contenido y el
  SHA-256 del código que la genera (`src/labels/regime_us.py`).
- **Cualquier cambio posterior** (de definición, parámetros o series) crea una **v1.1 o v2.0**, obliga a repetir
  **todas** las validaciones (§8 y estudio de revisión) y queda anotado en el registro de pruebas. Las nuevas
  publicaciones de datos solo actualizan los meses provisionales; no cambian la versión.

## 11. Parámetros finales v1.0 (congelados el 2026-10-14)

| parámetro | valor v1.0 | alternativa descartada |
|---|---|---|
| Umbral de inflación κ | 2,5 % PCE subyacente | 2,0 % (objetivo exacto) / 3,0 % |
| Escala s<sub>G</sub> | **0,40 z, fija** (ruido de revisión ALFRED de INDPRO + PAYEMS, 1955-2024; MAD × 1,4826 de primera publicación − última vintage) | 0,33 (cuatro indicadores, solo 2013-2024) |
| Escala s<sub>I</sub> | **0,31 pp, fija** (ruido de revisión ALFRED de PCEPILFE, 2000-2024) | 0,5 pp |
| Ventana de ritmo | 6 meses centrada (t−3…t+3), anualizado, sobre media de 3 meses centrada | 12 meses (más estable, más lenta) |
| Ventana de inflación | 6 meses centrada (t−3…t+3), anualizada | — |
| Pesos | 0 en 1950-1954, 1 en el resto | — |
| Ventana de tendencia | mediana centrada de 10 años | 7 años / filtro HP |
| Umbral de frontera | máx. prob. < 0,55 | < 0,6 |
| Meses provisionales | **54** (estudio de revisión, §7) | 24 / 36 |
| Embargo del backtest | **6 meses** | — |
| Fecha de decisión | último día hábil de t | día 15 de t+1 |

## 12. Registro de cambios

### v1.0 (2026-10-14, CONGELADA, aprobada por el usuario)

1. **Escalas fijas:** s<sub>G</sub> = 0,40 (INDPRO + PAYEMS, 1955-2024) en lugar de 0,33. La estimación de cuatro
   indicadores solo cubre 2013-2024, un periodo de revisiones pequeñas, y no representa la muestra. s<sub>I</sub> = 0,31.
   Como los ejes son independientes, la etiqueta dura solo depende del signo de G y de I − κ y no cambia en ningún mes
   frente a la v0.2. Cambian las probabilidades (Δp medio 0,019, máx. 0,045) y los meses frontera (72 → 84).
2. **`provisional_months` = 54** (antes 24), fijado por el estudio de revisión del borde derecho con una regla declarada
   de antemano (§7). Con 24 meses, la etiqueta dura de los meses "maduros" se revisaba aún en ~10 % de los casos. 30
   meses (2021-11 → 2024-04) pasan a provisionales.
3. **Metadatos de uso:** `embargo_months = 6` y la regla "provisional o weight = 0 no puntúan ni entrenan", en el
   `meta.json` y en la §7; hash del contenido y SHA-256 del código en el `meta.json`.
4. Las comprobaciones de la §8 se repiten con la muestra nueva: pasan todas (`docs/models/label_v1.0_checks.md`).
5. **Nota:** a partir de aquí, cualquier cambio = v1.1 / v2.0 con revalidación completa.

### v0.2 (2026-10-14, aprobada por el usuario)

Corrigen la definición para que la etiqueta describa el mes t. No son ajustes para pasar las comprobaciones: los umbrales
de la §8 no cambian.

1. **Ventanas centradas en t (§3, §4).** En la v0.1, G(t) comparaba la media de 3 m en t con la de t−6, es decir, medía
   el crecimiento de t−7 a t (centro en ~t−4), e I(t) la inflación de t−6 a t (centro en ~t−3). Las comprobaciones de la
   v0.1 lo mostraron: G correlacionaba 0,62 con CFNAI-MA3 contemporáneo, pero 0,81 con CFNAI-MA3 retrasado 2 meses y
   0,95 con el CFNAI agregado en la misma ventana. La etiqueta del mes t llegaba ~4 meses tarde y además los dos ejes
   estaban desalineados un mes entre sí. Como la etiqueta es ex post, puede usar datos posteriores a t: G pasa a t−3…t+3
   sobre la media de 3 m centrada, e I a t−3…t+3. Efecto: G v0.2(t) = G v0.1(t+4) e I v0.2(t) = I v0.1(t+3)
   (correlación 1,00); cambian de cuadrante 244 de 856 meses (28,5 %), casi todos en los giros. La etiqueta termina ~4
   meses antes y las escalas ALFRED se reestiman en las unidades nuevas (la primera publicación de G(t) es la primera
   vintage con t+4).
2. **Cuadrante G↓ I↓ renombrado (§5):** de "Desaceleración / recesión" (`slowdown`) a "Crecimiento bajo / desinflación"
   (`low_growth_disinfl`). La recesión es una capa aparte (`usrec`) y mezclar los dos nombres inducía a leer el
   cuadrante como recesión.
3. **Pesos (§7):** `weight = 0` en 1950-1954 (IPC general con la guerra de Corea, tendencia truncada); esos meses no
   puntúan.
4. **Comprobaciones (§8):** se añade el CFNAI agregado en la ventana de G, el informe sin meses de frontera y la
   comparación entre versiones.
5. **Escala s<sub>G</sub>:** usa también las vintages ALFRED de W875RX1 (desde 2010) y CMRMTSPL (desde 2013), descargadas
   a `data/archive/labels/raw/alfred/`; s<sub>G</sub> pasa de 0,40 (INDPRO + PAYEMS) a 0,33 (cuatro indicadores,
   2012-12 → 2024-04).

### v0.1 (2026-10-14)

Primera implementación (commit 35a0375): ventanas hacia atrás, s<sub>G</sub> = 0,40, s<sub>I</sub> = 0,30.

