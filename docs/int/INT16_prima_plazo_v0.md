---
documento: INT-16 — distinguir el tipo de movimiento de tipos: ¿la prima por plazo (ACM) anticipa la rentabilidad en
  exceso del bono a 10 años de EE. UU. a 12 meses mejor que la pendiente de la curva? (diseño + potencia + borrador)
version: 0.1 (BORRADOR, 2026-11-05; NO congelado; NO se ha corrido ningún contraste ni ninguna regresión predictiva)
estado: borrador con decisiones pendientes (§10). Veredicto de potencia: SIN POTENCIA en desarrollo, en el bloqueado y
  en vivo a horizonte útil (§6). Recomendación: NO construir el contraste confirmatorio (§11).
potencia: scripts/int16_potencia.py → research/int/int16_potencia.json (procedencia: commit y hora en el JSON)
depende_de: docs/int/E1_prerregistro_v1.md (formato, potencia antes de construir), src/factors/data.py (corte ≤ 2004;
  familia nyfed_acm añadida y declarada NO PIT), docs/int/INT12_prerregistro_v1.md (letra y tipo largo de EE. UU.)
---

# INT-16: prima por plazo frente a pendiente (borrador v0.1)

## 0. Qué se pregunta (y lo que NO)
- **Pregunta principal (a priori):** con información disponible en el fin de cada mes t, ¿un modelo de previsión con la
  **prima por plazo a 10 años** (ACM) anticipa la **rentabilidad en exceso a 12 meses del bono cupón cero a 10 años**
  de EE. UU. mejor que un modelo con la **pendiente de la curva** (10a − 1a; listón tipo Campbell-Shiller / Fama-Bliss)?
- **Objetivo:** rx12(t) = 10·y10(t) − 9·y9(t + 12) − y1(t) (rendimientos cupón cero, composición continua, GSW).
- **H1 (unilateral):** ECM fuera de muestra del modelo "prima" < ECM del modelo "pendiente" (ΔR²_OS > 0).
  **H0:** igual precisión.
- **Variante anidada (decisión 2):** ¿la prima **añade** a la pendiente (pendiente + prima frente a pendiente)?
- **Opcional (decisión 6):** ¿las subidas del tipo a 10 años **por prima** y **por expectativas** (rny) tienen efectos
  distintos en la bolsa a 3-12 meses?
- **No es:** una regla de cartera (no hay aún regla de duración); ni una prueba de la "hipótesis de expectativas" en
  general (literatura extensa); ni un estudio de los 5 factores de ACM.

## 1. Contaminación y el problema PIT (declarado)
1. **ACM NO es PIT (lo más grave).** La serie publicada por la NY Fed se **reestima con toda la muestra** (hoy, 1961-2026).
   Dos consecuencias:
   - (a) **Mirar adelante dentro del desarrollo:** en ACM la prima es, por construcción, la suma de rentabilidades en
     exceso **esperadas** según una regresión de las rentabilidades en exceso sobre 5 componentes principales de la curva
     estimada con toda la muestra. Usar la prima publicada para "predecir" rx12 es en parte **ajuste dentro de muestra**:
     la prima ya contiene la regresión que se quiere contrastar, con los datos futuros dentro.
   - (b) **Fuga débil del bloqueado:** los valores ≤ 2004 de la prima publicada dependen de datos ≥ 2005 (los
     coeficientes se estiman con ellos). Leerlos no gasta el bloqueado, pero no son "información de 2004".
   ⇒ **La prima publicada no puede ser el predictor de la prueba principal.** Solo como sensibilidad (con ventaja
   mecánica declarada) o, como aquí, para calibrar la **dinámica** de la potencia (persistencia, correlaciones).
2. **Muestra de descubrimiento de la literatura:** Cochrane-Piazzesi (2005) usan 1964-2003 y Fama-Bliss (1987) 1964-1985:
   **el desarrollo ≤ 2004 es exactamente donde se descubrió** la predictibilidad de los bonos. Saber que "dentro de
   muestra la pendiente/forwards predicen" ya es conocimiento contaminado. Bauer-Hamilton (2018) y Thornton-Valente (2012)
   (de memoria) documentan que fuera de muestra la ventaja es mucho menor o desaparece.
3. **Tendencia secular:** 1981-2004 es un mercado alcista de bonos (el 10a pasa de ≈ 15 % a ≈ 4 %); la prima ACM baja
   con el nivel de tipos (corr. prima-nivel 10a ≈ 0,74 en 1971-2004). Una prima alta "al principio" seguida de
   rentabilidades altas "durante" es exactamente el patrón que la persistencia + Stambaugh fabrican sin efecto (§6.1).
4. **Lo que se ha usado de los datos aquí:** solo propiedades de los **predictores** (VAR(1), correlaciones) y la
   correlación contemporánea entre sus innovaciones y el shock de rentabilidad mensual aproximado (−(119/12)·Δy10). Como
   rx12 es función de la curva, cualquier estadístico de la curva "toca" el objetivo; lo que **no** se ha estimado es
   ningún β ni ningún R² predictivo (x_t frente a rx12_{t+12}). Declarado.

**Mitigación propuesta del problema PIT (decisión 1):**
- **(M1, recomendada si se construye) ACM en tiempo real ("ACM-TR"):** reestimar el modelo de Adrian-Crump-Moench (2013;
  tres regresiones MCO: componentes principales + VAR(1); regresión de rentabilidades en exceso mensuales sobre
  constante, innovaciones y factores; sección cruzada para λ0, λ1; recursiones de precios) en **cada origen t** con
  **ventana creciente** que acaba en t. La prima "as of t" es la del último mes de esa estimación.
  - **Datos:** los rendimientos cupón cero GSW del warehouse (`gsw_sveny01…10`, diarios, PIT por construcción: cada día
    se ajusta solo con precios de ese día) existen 1-7 años desde 1961-06 y 8-10 años desde **1971-08**; **no hay
    vencimientos < 1 año**. ACM usa 3, 6, …, 120 meses. Hay dos vías:
    - **(M1a, recomendada):** ingerir los **parámetros Svensson de GSW** (BETA0-3, TAU1-2), que están en el fichero
      bruto `feds200628.csv` ya descargado (comprobado solo su cabecera) pero no en el warehouse. Con ellos se calculan
      los rendimientos a 3…120 meses desde 1961-06 (lo mismo que hace ACM). Coste: un cambio de ingesta + familia nueva.
      Aviso: antes de 1971 los vencimientos largos son extrapolación del ajuste de GSW.
    - **(M1b):** vencimientos anuales 1-10 desde 1971-08, interpolando el de n − 1/12 y con tipo corto = letra a 3 meses
      (`TB3MS`, media mensual, base descuento: aproximación declarada). Primera estimación con 10 años → ACM-TR desde
      **1981-08** (muestra principal fuera de muestra 1981-08 … 2003-12, 269 orígenes).
  - **Comprobación previa (sin el objetivo):** correlación ACM-TR(2004-12) con la publicada ≤ 2004 y dispersión entre
    añadas; esto calibra el "ruido de añada" de la potencia (supuesto κ = 0,25 en §6).
- **(M2) Prima publicada como sensibilidad** declarada "con ventaja mecánica"; nunca decide.
- **(M3) Listón simétrico:** la pendiente se calcula con los mismos GSW, en el mismo mes, y ambos modelos usan la misma
  previsión MCO de ventana creciente (en el origen t, solo pares con s ≤ t − 12: sin solapamiento con el futuro).

## 2. Datos (todo ≤ 2004 en desarrollo; `src/factors/data.load_dev`)
| uso | serie | fuente | PIT |
|---|---|---|---|
| objetivo | rx12 del cupón cero 10a: `gsw_sveny10`, `gsw_sveny09`, `gsw_sveny01` (último dato del mes) | GSW (Fed Board) | sí (curva diaria) |
| listón | pendiente = y10 − y1 (GSW) | ídem | sí |
| candidato | prima 10a ACM-TR (M1) | reestimación propia sobre GSW | sí, si se construye |
| sensibilidad | `nyfed_acm_tp10_m` (publicada) | NY Fed (fichero ACMTermPremium.xls) | **NO** |
| bolsa (opcional) | `nyfed_acm_tp10_m`, `nyfed_acm_rny10_m`; bolsa: `ff_mkt_rf_m` (+ `ff_rf_m`) | NY Fed; Ken French | prima/rny: NO |
- Comprobado: las mensuales de ACM son **fin de mes** (fechadas el día 1; |ACM y10 − GSW y10| medio ≈ 1 pb).
- **Familia añadida** a `src/factors/data.FAMILIAS`: `nyfed_acm_(y|tp|rny)\d\d_m`, con el comentario "no PIT".
- **Muestras:** principal 1971-08 … 2003-12 (389 orígenes con objetivo; fuera de muestra 1981-08 … 2003-12 = 269);
  alternativa con objetivo ajustado ACM desde 1961-06 (511; fuera de muestra 1971-06 … 2003-12 = 391; objetivo de
  modelo, no observado; solo con M1a).

## 3. Modelos (a fijar; nada se elige después)
- **Media histórica** (referencia de R²_OS).
- **L (listón):** rx12 = a + b·pendiente(t). MCO, ventana creciente, previsión en t con pares s ≤ t − 12.
- **P (candidato):** rx12 = a + b·prima10(t) (nivel; decisión 3: nivel frente a cambio a 12 meses).
- **LP (anidado):** rx12 = a + b·pendiente + c·prima10.
- Referencia descriptiva (decisión 4): factor Cochrane-Piazzesi con forwards GSW 1-5 años y pesos de ventana creciente
  (contaminado: descubierto en esta muestra).

## 4. Métrica y contraste
- **Principal (no anidado):** ΔR²_OS = (ECM_L − ECM_P) / ECM_media sobre los orígenes fuera de muestra.
- **p-valor:** no fiable por la vía nominal: Diebold-Mariano con Newey-West(12) tiene **tamaño real 10-14 %** al 5 %
  nominal (§6). Se propone un **bootstrap paramétrico de la nula** (VAR de los predictores + residuos remuestreados por
  bloques, con igual precisión poblacional), el mismo mecanismo de la potencia.
- **Anidado:** Clark-West (MSE-ajustado) de LP frente a L, con el mismo bootstrap (tamaño real del nominal 11-13 % con la prima en nivel).
- **Secundarios:** R²_OS de L y de P frente a la media; ΔR²_OS por décadas; con la prima publicada; con Δ12 prima.

## 5. Opcional: bolsa tras subidas "por prima" frente a "por expectativas"
- r_bolsa(t → t + h) = a + b_tp·ΔTP3(t) + b_rny·ΔRNY3(t) + e, h ∈ {3, 6, 12}; H1: b_tp ≠ b_rny (bilateral).
- Mismo problema PIT (más leve: los **cambios** de la descomposición se revisan menos que el nivel; a comprobar con M1).

## 6. Potencia (antes de construir nada)
**Método** (`scripts/int16_potencia.py`): DGP mensual con x = (pendiente, prima) VAR(1) estimado en 1971-08 … 2004-12
(autovalores |0,97|), residuos **reales remuestreados por bloques de 12** junto al shock de rentabilidad mensual del bono
(conserva Stambaugh: corr. innovación prima-shock ≈ −0,50, pendiente-shock ≈ +0,17, y la heterocedasticidad de
1979-82). rx12 = c·(w_s·s̃ + w_p·p̃) + Σ12 shocks futuros (solapamiento de 12 meses). El **tamaño del efecto es un
parámetro**: R² poblacional conjunto a 12 meses ∈ {0,05; 0,10; 0,20; 0,30} (literatura dentro de muestra: Fama-Bliss
≈ 0,10-0,15; Cochrane-Piazzesi ≈ 0,30-0,35, que es la cota alta y contaminada), repartido entre pendiente y prima por un
ángulo θ (45° = misma precisión = nula del no anidado; 90° = solo la prima predice; 0° = la prima no añade = nula del
anidado). Correlación poblacional pendiente-prima 0,35. Previsión MCO de ventana creciente como en §3. Valor crítico
**empírico** de la nula simulada. 1.500 réplicas por celda (en vivo, 500; error Monte Carlo de una potencia ≈ ±0,01-0,02).

Ejecución: commit 17ede3c, árbol limpio, 2026-11-05T08:14:50Z, 765 s → `research/int/int16_potencia.json`.

### 6.1 Persistencia y sesgo de Stambaugh (sin ningún efecto, c = 0; 389 orígenes de 1971-08 … 2003-12)
| predictor | R² dentro de muestra a 12 m (media / p95) | tamaño real del t de Newey-West(12) al 5 % bilateral |
|---|---|---|
| pendiente | 0,026 / 0,098 | 0,16 |
| prima (nivel) | 0,031 / 0,111 | **0,19** |
| prima (Δ12) | 0,019 / 0,077 | 0,12 |
Sin ninguna predictibilidad, un R² de 0,10 dentro de muestra sale en ≈ 5 % de las muestras y el t de NW rechaza 3-4
veces más de lo nominal. La prima en nivel es la peor (más persistente y con innovación muy correlacionada con el shock
de rentabilidad, −0,50). Cualquier R² dentro de muestra "de la literatura" en esta muestra hay que leerlo con esto.

### 6.2 Contraste principal no anidado (prima frente a pendiente), muestra principal ACM-TR 1981-08 … 2003-12 (269)
Potencia con el **efecto máximo posible** de cada fila (θ = 90°: solo la prima predice; ΔR²_pob = (1 − 0,35²)·R²):
| R² conjunto a 12 m | ΔR²_pob máx | potencia (crítico empírico) | P(ΔR²_OS > 0) | ídem bajo H0 | tamaño real DM nominal 5 % |
|---|---|---|---|---|---|
| 0,05 | 0,044 | 0,09 | 0,66 | ≈ 0,53 | 0,10 |
| 0,10 | 0,088 | 0,14 | 0,75 | 0,53 | 0,12 |
| 0,20 | 0,176 | 0,27 | 0,89 | — | 0,14 |
| 0,30 | 0,264 | **0,40** | 0,96 | — | 0,14 |
**MDE (80 %) en ΔR²_pob: por encima de la rejilla en todas las filas** (> 0,26 incluso con R² = 0,30 y la pendiente sin
poder predictivo propio). Otras muestras, con θ = 90° y R² = 0,30:
| muestra | fuera de muestra | potencia no anidado | MDE |
|---|---|---|---|
| ACM-TR con ruido de añada κ = 0,25 | 269 | 0,41 (R² = 0,10: 0,13) | > rejilla |
| ACM publicada 1961-, OOS 1971-06 … 2003-12 (sensibilidad, no PIT) | 391 | 0,60 | > rejilla |
| prima en Δ12 (ACM-TR) | 269 | 0,53 | > rejilla |
| bloqueado 2005-2023 (hipotético, no leído) | 228 | 0,44 | > rejilla |
| en vivo 10 / 20 / 30 / 40 años | 120 / 240 / 360 / 480 | 0,29 / 0,46 / 0,62 / 0,79 | > rejilla en todos |

### 6.3 Variante anidada (¿la prima añade a la pendiente? Clark-West, crítico empírico)
MDE (80 %) en R² parcial poblacional a 12 m (R²_conjunto − R²_pendiente sola):
| muestra | R² 0,10 | R² 0,20 | R² 0,30 | tamaño real CW nominal |
|---|---|---|---|---|
| ACM-TR, prima nivel (principal) | > 0,088 (pot. máx 0,35) | > 0,176 (0,63) | **0,22** | 0,11-0,13 |
| ACM-TR, prima Δ12 | > 0,098 (0,53) | 0,17 | 0,14 | 0,06-0,07 |
| ACM-TR nivel con ruido κ = 0,25 | > 0,088 (0,28) | > 0,176 (0,46) | > 0,264 (0,73) | ≈ 0,10 |
| publicada 1961- (391) | > 0,088 (0,49) | > 0,176 (0,79) | 0,15 | ≈ 0,10 |
| bloqueado (228) | > 0,088 (0,32) | > 0,176 (0,63) | 0,26 | ≈ 0,12 |
| en vivo 30 / 40 años | > 0,088 / > 0,088 | 0,17 / 0,10 | 0,19 / 0,09 | ≈ 0,1 |
Un efecto **realista** de la prima sobre la pendiente sería un R² parcial de 0,02-0,05 (la prima y la pendiente comparten
información; en ACM la prima es una combinación lineal de los mismos componentes de la curva): la potencia ahí es
**0,13-0,20** en el desarrollo (θ = 45°, R² 0,05-0,10) y no pasa de ≈ 0,3 ni en 40 años en vivo.

### 6.4 Opcional: bolsa (1961-06 … 2004-12, 510 meses; dt ΔTP3 = 0,39 pp, ΔRNY3 = 0,52 pp, corr. −0,22)
MDE (80 %, bilateral) de b_tp − b_rny, en pp de rentabilidad de la bolsa por 1 pp de cambio de tipo a 3 meses:
**h = 3: 3,9 pp; h = 6: 6,0 pp; h = 12: 8,5 pp** (por 1 dt de ΔTP3: 1,5 / 2,3 / 3,3 pp). Supuesto: dt mensual de la
bolsa 4,4 % iid (15 % anual; literatura, no se ha leído la bolsa). Es decir: detectaría que una subida de 40 pb por
prima y una de 40 pb por expectativas difieren en ≥ 3,3 pp de rentabilidad a 12 meses. Es potencia **moderada** (un
efecto así no es descabellado), pero con 3 horizontes y la prima no PIT. Exploratorio, no confirmatorio.

### 6.5 Lectura honesta
- **Pregunta principal (no anidada): sin potencia en ninguna muestra disponible.** Incluso en el caso más favorable
  imaginable (la prima es el único predictor y explica el 30 % de la varianza a 12 meses, el máximo de Cochrane-Piazzesi
  dentro de muestra), la potencia es 0,40 en el desarrollo con ACM-TR, 0,44 en el bloqueado y 0,79 tras 40 años en
  vivo. Con efectos realistas (R² 0,05-0,10) la potencia es 0,09-0,14: igual que tirar una moneda trucada por el tamaño.
- La razón: 12 meses de solapamiento → 22 años ≈ 22 observaciones independientes; predictores con autocorrelación 0,97;
  heterocedasticidad de 1979-82; y dos modelos con ruido de estimación que se compara entre sí.
- El **signo** apenas informa: P(ΔR²_OS > 0) es 0,53 sin efecto y 0,66-0,75 con efectos realistas.
- **Anidado:** solo efectos enormes (R² parcial ≥ 0,14-0,22) se detectan; los realistas (0,02-0,05) no.
- Los contrastes nominales (DM, CW con Newey-West) tienen tamaño real 10-15 %: no usarlos sin bootstrap.
- **Veredicto: sin potencia. No construir el contraste principal.**

## 7. Criterios (si, contra la recomendación, se construyera)
- **Confirmado:** ΔR²_OS > 0 con p del bootstrap de la nula < 0,05 (unilateral), R²_OS(P) > 0, y ΔR²_OS > 0 en
  1981-1992 y 1993-2003 por separado.
- **Refutado:** ΔR²_OS ≤ 0 (punto). Con la potencia de §6 esto **apenas informa** (P(ΔR²_OS > 0) ≈ 0,53 bajo la nula y
  0,66-0,75 con efectos realistas).
- **Ni uno ni otro:** lo más probable; "no contradicho, sin potencia". No se vuelve a correr con otra especificación.

## 8. Placebos y controles (si se construye)
- P1 señal plantada con el DGP de §6 (la tubería recupera ΔR²_OS con θ = 90°, R² = 0,3).
- P2 ACM-TR frente a publicada ≤ 2004 (descriptivo; calibra κ).
- P3 prima retrasada 24 meses: no debería ayudar.
- P4 corte PIT: test de que ACM-TR en t no lee nada > t ni ≥ 2005.

## 9. Procedencia
- `scripts/int16_potencia.py` con puerta (árbol limpio; commit y hora UTC en el JSON; semilla fija 20261105).
- Ningún contraste corrido. Ninguna regresión x_t → rx12 sobre datos reales estimada.

## 10. Decisiones pendientes del usuario (con mi recomendación)
1. **¿Construir ACM-TR (M1)?** **Recomendado: NO** mientras la potencia sea la de §6; si algún día se construye, vía
   **M1a** (ingerir parámetros GSW), con la comprobación P2 antes de tocar el objetivo.
2. **No anidado frente a anidado:** **recomendado anidado (Clark-West)** si se construye: algo más de potencia y es la
   pregunta útil ("¿la prima añade a la pendiente?"); el no anidado de la pregunta original como secundario.
3. **Prima en nivel frente a cambio a 12 meses:** **recomendado nivel** (es lo que la prima significa: rentabilidad en
   exceso esperada); el cambio como secundario (su potencia anidada es algo mejor, pero no hay razón a priori).
4. **Listón:** **recomendado pendiente 10a − 1a** (sin pesos estimados); Cochrane-Piazzesi solo descriptivo.
5. **¿Gastar el bloqueado (2005-2023)?** **Recomendado: NO** (MDE por encima de la rejilla, §6).
6. **Bolsa (opcional):** es la única pregunta con potencia moderada (MDE ≈ 3,3 pp a 12 m por 1 dt de ΔTP3).
   **Recomendado: solo exploratorio** con la prima publicada (declarada no PIT), un único horizonte fijado antes
   (h = 12) y sin veredicto; si saliera algo grande, entonces ACM-TR y prerregistro.
7. **Registro en vivo** (como E1): **recomendado no** para la pregunta principal (40 años no bastan); posible como
   registro descriptivo barato si se construye ACM-TR para otra cosa.

## 11. Recomendación
NO construir INT-16 como contraste confirmatorio. Dejar el documento como registro de que la pregunta se planteó, se
midió su potencia y no tiene respuesta posible con 22-33 años de datos mensuales solapados (ni con 40 años en vivo). Si interesa la prima por
plazo como herramienta, usarla **descriptivamente** (qué parte de una subida de tipos es prima y qué parte
expectativas) en el reporte, declarada no PIT, sin afirmar que anticipa nada.
