---
documento: Prerregistro INTERNO de desarrollo de la fase de factores y cartera (P-DEV-FACT)
version: 0.1-borrador (2026-10-26)
estado: BORRADOR para revisión del usuario. NO se ha corrido nada. Ninguna rentabilidad de cartera calculada.
alcance: desarrollo ≤ 2004 (corte técnico src/factors/data.py). No abre el periodo bloqueado ni la caja fuerte.
---

# P-DEV-FACT v0.1 (borrador)

## 0. Qué es y qué no es
- Fija **antes de mirar ninguna rentabilidad** las estrategias, métricas, listones, costes y criterios del backtest de
  desarrollo. Todo lo que se corra queda en el registro de pruebas (`research/trial_log.md`), también lo fallido.
- La prueba principal es el **paper trading** (decisión del usuario, 26-oct); P-EVAL-FACT (≥ 2005), si llega, es
  secundaria y tendrá su propio prerregistro antes de mirar nada.
- Si ninguna variante cumple §6, el resultado por defecto es la **opción 3**: cartera de referencia + su versión con
  ajuste por volatilidad + paper trading.

## 1. Cartera de referencia (IPS, decisión del usuario 26-oct: opción C + 10 % de oro)

| parámetro | valor |
|---|---|
| pesos estratégicos | **80 % renta variable / 10 % renta fija / 10 % oro** |
| horizonte | 15+ años |
| caída máxima tolerable | −35 a −40 % |
| renta variable | global, **sin cubrir** (EUR) |
| renta fija | deuda pública en EUR, duración ≈ 5 años, sin riesgo de divisa |
| oro | precio en USD convertido a EUR, **sin cubrir** |
| rebalanceo | al cierre de diciembre **o** cuando un peso se separe ± 5 pp del estratégico (revisión mensual), lo que llegue antes |
| desviación táctica máxima | renta variable entre **65 % y 80 %** (solo a la baja, − 15 pp); lo que sale va a renta fija; el oro no se mueve (sin reglas tácticas: no hay potencia) |
| frecuencia táctica | como mucho un cambio al mes (PLAN) |
| costes de transacción | 10 pb por lado en renta variable y renta fija; 20 pb por lado en oro (ETC) |
| costes corrientes | TER 0,20 % RV, 0,15 % RF, 0,15 % oro, descontados mensualmente (iguales en todas las estrategias) |
| fiscalidad | vehículos traspasables: sin coste fiscal en los cambios (supuesto declarado) |

## 2. Datos (todo vía `src/factors/data.py`, corte 2004-12, fallo cerrado)
- **Renta variable:** mercado de EE. UU. con rentabilidad total (`ff_mkt_rf_m` + `ff_rf_m`) en USD → EUR. **Declarado:**
  antes de 1990 no hay "global" invertible; EE. UU. hace de aproximación (es el ~50-70 % del índice global).
- **Renta fija:** Bund cupón cero 5 años (Svensson, Bundesbank, `bundesbank_bund_zero_5y_m`, 1972-09 →).
  Rentabilidad mensual ≈ y<sub>t−1</sub>/12 − 5·(y<sub>t</sub> − y<sub>t−1</sub>) (duración de un cupón cero = plazo).
- **Oro:** `gold_eur_dev` (Banco Mundial, media mensual, × EUR/USD del BIS).
- **Efectivo (Sharpe):** `oecd_ir3m_deu`.
- **EUR/USD antes de 1999:** euro sintético del BIS (`bis_xru_xm_eur_m`, 1974 →).
- **Por verificar antes de correr (no bloquea el texto):** si las series del BIS y de la Bundesbank son cierre o media
  del mes. Si son media, se declara igual que el oro y se añade la sensibilidad en USD (§7).

## 3. Periodo
- **Puntuación principal: 1975-01 → 2004-12** (360 meses; compra privada de oro en EE. UU. desde 1975). Recesiones
  (episodios): **1980, 1981-82, 1990-91, 2001** (4).
- Las estimaciones causales (volatilidad de B1) usan historia desde 1963-07, sin puntuarla.
- **Sensibilidad informativa:** 1963-07 → 2004-12 sin oro (80/20), con 6 recesiones.

## 4. Estrategias (5 en total; N = 5 para el Deflated Sharpe)

**Cronología común:** la señal se fija con la información del cierre del mes t; los pesos nuevos de renta variable y
renta fija rigen el rendimiento de t + 1. **El oro se opera con un mes más de retraso** (rige desde t + 2), para no comprar
a una media que incluye días posteriores a la decisión (decisión del usuario).

| id | qué es | papel |
|---|---|---|
| **B0** | cartera de referencia estática 80/10/10 con su rebalanceo | listón 1 |
| **B1** | B0 con ajuste por volatilidad, sin régimen: RV = 80 % × min(1, σ\*/σ̂<sub>t</sub>), acotada en [65 %, 80 %]; σ̂<sub>t</sub> = volatilidad realizada de la RV en EUR en los 12 meses hasta t; σ\* = mediana expansiva de σ̂ desde 1963-07 hasta t; un cambio solo si mueve ≥ 2,5 pp; lo que sale va a RF | **listón 2 (el que hay que batir)** |
| **V1** | DEFENSIVO si G del clasificador < 0 (k = 1) → RV 65 % / RF 25 % / oro 10 % | candidata |
| **V2** | ídem con θ = −0,25, k = 1 | candidata |
| **V3** | ídem con θ = 0, k = 3 (ancla a priori) | candidata |

V1-V3 se eligieron **solo con propiedades de la señal** (regla commiteada antes de calcular, `scripts/factors_variantes.py`;
`research/factors/variantes_senal.json`):

| | θ | k | cambios/año | % defensivo | κ con la etiqueta (G↓) |
|---|---|---|---|---|---|
| V1 | 0 | 1 | 0,87 | 42 % | 0,415 |
| V2 | −0,25 | 1 | 0,43 | 32 % | 0,371 |
| V3 | 0 | 3 | 0,43 | 44 % | 0,335 |

El clasificador **no se toca**: la histéresis (k) está en la regla de cartera.

## 5. Métricas (todas netas de costes)
1. **Volatilidad anualizada** (principal).
2. **Caída máxima por episodio:** en cada recesión, la peor caída desde máximo dentro de [pico NBER − 6 m, valle NBER + 12 m].
3. Caída máxima total 1975-2004 y CVaR al 5 % mensual.
4. Rotación anual (suma de |Δw| / 2) y costes anuales.
5. Rentabilidad anualizada y Sharpe frente al efectivo en EUR (informativos; el objetivo no es ganar más).
6. **Oro (efecto Working):** todas las métricas se publican **con y sin corrección** de la serie del oro. Corrección:
   desuavizado r\*<sub>t</sub> = (r<sub>t</sub> − ρ r<sub>t−1</sub>)/(1 − ρ) con **ρ = 0,161** (AR(1) del oro en EUR,
   1975-2004, medido el 26-oct; en USD 0,205; teórico de Working 0,25). Volatilidad del oro: 16,1 % sin corregir,
   ≈ 18,5-19,7 % corregida.

## 6. Criterio: una variante "mejora a B1" solo si cumple TODO
- **(a) Volatilidad:** σ(V) < σ(B1), con el IC 95 % por bootstrap de bloques de 12 meses de σ(V) − σ(B1) por debajo de 0.
- **(b) Caídas:** caída por episodio mejor que B1 en **≥ 3 de los 4** episodios, y caída máxima total no peor.
- **(c) Placebo:** la reducción de volatilidad frente a B1 supera el percentil 95 de **500 placebos** en los que la serie de
  estados DEFENSIVO/NORMAL de la variante se baraja en bloques de 24 meses (misma proporción de tiempo defensivo).
- **(d) Deflated Sharpe:** DSR(V) ≥ DSR(B1) con N = 5 pruebas (B0, B1, V1-V3) y la varianza de Sharpe entre ellas.
- **(e) Multiplicidad:** Holm sobre las 3 variantes en (a) y (c).
- (a)-(e) en la versión **sin** corrección del oro **y** en la corregida; si discrepan, manda la corregida.
- Si ninguna cumple → **opción 3**. Si cumple más de una, se queda la de menor rotación.

## 7. Sensibilidades (se publican siempre; no deciden)
1963-2004 sin oro; todo en USD (sin divisa); costes × 2; bloques de 24 meses en el bootstrap; B1 con ventana de 6 y 24 meses.

## 8. Expectativa honesta (antes de correr)
- Mover 15 pp de renta variable a renta fija reduce la volatilidad de la cartera **como mucho ≈ 19 %** mientras se está en
  DEFENSIVO (≈ 15/80, si RF y oro apenas aportan); con un 32-44 % del tiempo en DEFENSIVO, el efecto medio es bastante
  menor. Y B1 ya recorta en los periodos de volatilidad alta, que suelen coincidir con las recesiones.
- Con 4 episodios, el criterio (b) se decide con muy poca muestra.
- **Lo más probable es que ninguna variante pase y quede la opción 3.** Eso es un resultado válido, no un fracaso.

## 9. Contaminación y sesgos declarados
- Inflación del clasificador con datos revisados hasta mediados de los 90; diseño del clasificador con conocimiento
  posterior a 2004 (Sahm, 2 %, NFCI).
- **G del clasificador no pasó la regla del paso 1** (concordancia 68,9 %, κ 0,394 < 0,40); se sigue **por decisión del
  usuario** (26-oct).
- Oro: decisión de incluirlo influida por 2005-2011 y 2019-2025; medias mensuales (corregidas en §5).
- Factores: historia posterior a 2005 conocida (momentum 2009, value 2010s). Aquí no se usan factores de estilo, solo el
  mercado, la renta fija y el oro.
- Renta variable global aproximada por EE. UU.

## 10. Registro y orden
1. El usuario aprueba este texto → se commitea y se sube (con hora) **antes** de calcular ninguna rentabilidad.
2. Verificación de cierre/media de BIS y Bundesbank (sin rentabilidades).
3. Una sola corrida de B0, B1, V1-V3 + sensibilidades + placebos. Todo al registro.
4. Lectura por el usuario. Sin iterar: si no pasa, opción 3.
