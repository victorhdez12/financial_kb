---
documento: Especificación de B2 «compra en caídas», cartera EN PARALELO a B0/B1/B1′ para el paper trading
version: 0.1-borrador (2026-11-18)
estado: BORRADOR para el usuario. NO congelado, NO registrado, NO enganchado a scripts/paper_mensual.sh ni al espejo de
        Alpaca. B0, B1 y B1′ (docs/factors/paper_trading.md, B1prima_spec.md) NO se tocan. Periodo ≥ 2005 sin mirar.
origen: pregunta del usuario ante la caída del 18-nov: «¿no debería ser mejor comprar?». Plan aprobado 18-nov (Estado
        «▶ Retomar (18-nov)»): «borrador B2 compra en caídas, prerregistro antes del primer dato».
script: scripts/b2_borrador.py (reproducible, solo ≤ 2004; NO es validación). Tests: tests/test_b2_borrador.py.
---

# B2: comprar cuando la bolsa ha caído (borrador)

## 0. Qué es y qué no es
- **B2 = B0 (70/15/15) que sube la renta variable al 80 % cuando la bolsa en EUR ha caído ≥ X desde su máximo de 12
  meses**, y vuelve al 70 % cuando se recupera. Es la apuesta **contraria** a B1: B1 recorta en los meses de volatilidad
  alta, que suelen ser los de caídas; B2 compra en ellos.
- Se seguiría **en paralelo**, en papel (y en una cuenta paper propia de Alpaca), **sin mover dinero** y sin sustituir a
  nada. Su papel es poner en vivo, con una regla fijada de antemano, la pregunta del usuario.
- **Lo que no puede hacer:** decir en pocos años si comprar en caídas es mejor. Con los números de desarrollo harían
  falta **décadas** (§7). Lo que sí mide pronto: que la regla se ejecuta cuando debe, cuánta rotación y coste tiene, y
  cuánto riesgo extra se asume en cada caída.
- **Nombre:** «B2» ya se usó en `docs/int/INT5_diseno_v0.md` (B1 + termómetro de recesión; INT-5 aparcado el 26-oct).
  Decisión del usuario (§10, D1): mantener «B2» aquí y renombrar el de INT-5, o llamar a esta «B2c».

## 1. Hipótesis y mecanismo
**H (direccional, a largo plazo):** la rentabilidad media de B2 es mayor que la de B1 (y que la de B0), a cambio de
más volatilidad y caídas más profundas. No se espera que B2 reduzca el riesgo: lo aumenta a propósito.

**Mecanismos posibles (por qué podría pagar):**
1. **Prima por aportar liquidez / soportar riesgo cuando otros no pueden.** Tras una caída, muchos inversores venden por
   obligación (márgenes, mandatos, miedo); quien compra cobra una prima. En modelos de prima de riesgo variable (p. ej.
   hábitos de consumo, Campbell y Cochrane, 1999), la rentabilidad esperada sube después de las caídas, pero **porque el
   riesgo también sube**: no es dinero gratis.
2. **Reversión a la media a horizonte largo** de los índices: si parte de la caída es transitoria, comprar barato paga
   a 2-5 años.

**Por qué podría NO pagar (o perder):**
3. **Momentum de serie temporal a corto plazo** (1-12 meses): los índices que han caído tienden a seguir cayendo algo en
   los meses siguientes; B2 compra justo en la fase en que el momentum juega en contra.
4. **Las caídas largas existen:** 1929-32, 1973-74, 2000-03, 2008-09 (este último en el periodo bloqueado; no se mira).

**Lo que dice la evidencia que conozco con seguridad (resumen honesto, sin citas que no pueda respaldar):**
- **Reversión a largo plazo:** Fama y French (1988, JPE) y Poterba y Summers (1988, JFE) encontraron autocorrelación
  negativa de los rendimientos del mercado de EE. UU. a 3-5 años. Es **estadísticamente frágil**: depende mucho de
  1926-1940 y se debilita en la posguerra (p. ej., Kim, Nelson y Startz, 1991). Con datos solapados y pocos periodos
  independientes, la incertidumbre es enorme.
- **Predecibilidad por valoración** (rentabilidad por dividendo, CAPE; Campbell y Shiller, 1988): la rentabilidad a largo
  plazo es algo mayor cuando los precios están bajos respecto a los fundamentales, pero **fuera de muestra** casi
  ninguna variable bate a la media histórica de forma fiable (Goyal y Welch, 2008, RFS). Una caída del 15 % abarata, pero
  es una señal de valoración tosca.
- **Momentum de serie temporal** (Moskowitz, Ooi y Pedersen, 2012, JFE): en futuros, incluidos índices de bolsa, el
  rendimiento de los últimos 12 meses predice con signo positivo el del mes siguiente, con reversión parcial después. Es
  justo lo contrario de B2 a corto plazo.
- **Reversión a corto plazo como prima de liquidez** (Nagel, 2012, RFS, «Evaporating liquidity»): la rentabilidad de
  aportar liquidez es mayor cuando el VIX está alto. Pero es **en acciones individuales y a días/semanas**, no en el
  índice a un mes: solo apoya el mecanismo 1 de forma indirecta.
- **Gestión por volatilidad** (Moreira y Muir, 2017, JF), base de B1, y su crítica fuera de muestra (Cederburg,
  O'Doherty, Wang y Yan, 2020, JFE): la ventaja de recortar con volatilidad alta es discutida. Es decir, **ni B1 ni B2
  tienen a priori una ventaja establecida**; por eso tiene sentido seguirlas las dos.
- **El rebalanceo ya es contrario:** B0 vuelve al 70 % cuando la RV se separa ± 5 pp, es decir, ya compra algo tras las
  caídas. B2 añade una inclinación de + 10 pp encima. Lo que B2 mide es **esa inclinación**, no «comprar en caídas» en
  general.
- Mi lectura: la evidencia **no permite esperar** que B2 gane a B0 de forma clara; frente a B1 la diferencia de
  rentabilidad, si existe, será de décimas de punto al año, enterrada en ruido (§7).

## 2. Activos, frecuencia y cronología (iguales que B1)
- Tres tramos: RV global desarrollada, RF deuda pública euro duración ≈ 5, oro físico; mismos instrumentos tipo, proxies
  de valoración, costes (10 pb por lado RV/RF, 20 pb oro), TER y bandas de rebalanceo (± 5 pp, diciembre) que
  `docs/factors/paper_trading.md` §4 y el informe 5f.
- **Mensual:** la señal se fija al cierre del mes t y los pesos rigen desde t + 1. Como el oro no cambia (15 % fijo), el
  retraso de un mes de sus órdenes no interviene salvo en el rebalanceo.
- Justificación: misma frecuencia y activos que B1 para que la comparación aísle **la regla**, no el universo ni el
  calendario. Una regla diaria (comprar el día de la caída) tendría más rotación, sería otra pregunta y no encaja con el
  registro mensual inmutable.

## 3. Regla (única, fijada a priori)
1. **Nivel de la bolsa en EUR** P_t a cierre de mes (en vivo: S&P 500 de FRED `SP500` / EUR-USD del BCE, el último día
   hábil del mes; **la misma medida que σ̂ de B1**).
2. **Caída desde el máximo de 12 meses:** DD_t = P_t / max(P_{t−11}, …, P_t) − 1 (12 cierres de mes, incluido t).
3. **Estado:**
   - NORMAL → **COMPRA** si DD_t ≤ −X;
   - COMPRA → NORMAL si DD_t ≥ −X/2 (histéresis fija de la mitad, para no entrar y salir cada mes en torno al umbral);
   - si no, se mantiene el estado del mes anterior.
4. **Pesos:** NORMAL = **70/15/15** (= B0); COMPRA = **80/5/15** (los + 10 pp de RV salen de la RF; oro fijo).
5. **Falla cerrado** como B1: dato diario de más de 5 días respecto al cierre, o menos de 12 cierres de mes → no se
   decide y se avisa.
6. Estado inicial: NORMAL (si el primer cierre ya cumple DD ≤ −X, entra en COMPRA ese mismo cierre).

**Calibración de X (regla fijada antes de mirar rentabilidades):** X = −(percentil 20 de DD_t en 1963-07 … 2004-12),
con la medida de desarrollo equivalente a la de vivo (mercado de EE. UU. de French, cierre de mes, en EUR con el fixing
DEM/USD de Frankfurt ≤ 1998 y el BCE ≥ 1999: la de σ\* de B1, `scripts/paper_sigma_star.py`), redondeado a 0,1 pp. La
distribución incluye los meses en máximo (DD = 0). Es una propiedad de la señal, no de la cartera; el periodo bloqueado
no se usa.

**Resultado (`scripts/b2_borrador.py`):** **X = 14,7 %**; salida en **−7,35 %**.

Propiedades de la señal 1963-07 … 2004-12 (sin rentabilidades):

| variante | umbral | % meses en COMPRA | entradas | cambios/año | duración media en COMPRA |
|---|---|---|---|---|---|
| **propuesta (P20, salida −X/2)** | **14,7 %** | **30,5 %** | **15** | **0,72** | **10,1 meses** |
| P10 (referencia) | 20,5 % | 15,3 % | 7 | 0,34 | 10,9 |
| P30 (referencia) | 10,6 % | 35,3 % | 16 | 0,77 | 11,0 |
| P20 sin histéresis (sale en −X) | 14,7 % | 20,3 % | 22 | 1,06 | 4,6 |

Con la histéresis, B2 pasa ≈ 30 % del tiempo en COMPRA (no el 20 % que sugiere el percentil). P10 y P30 se muestran
**solo como sensibilidad de la señal**; sus rentabilidades no se han calculado para no elegir por resultados.

**Alternativas consideradas y descartadas a priori:**
- *Caída del último mes* (p. ej., comprar si la RV cae ≥ 5 % en el mes): más ruido, más rotación, y mide sustos de un mes,
  no «la bolsa ha caído». Descartada.
- *Desde máximos históricos:* en EUR la bolsa pasa años lejos de su máximo (desde 2000 hasta el final del desarrollo, 2004); B2 sería casi una
  80/5/15 permanente. Descartada.
- *Escala continua* (más RV cuanto más cae): más parámetros, más difícil de juzgar. Descartada.

## 4. Límites y costes
- RV entre **70 % y 80 %**; RF entre 5 % y 15 %; oro 15 %. Un cambio como mucho al mes (de hecho, ≈ 0,7 al año).
- **Conflicto con el IPS (decisión del usuario, D2):** el IPS solo permite desviaciones tácticas **a la baja** (RV en
  [55 %, 70 %]), y la 70/15/15 se eligió **después** de ver que la 80/10/10 caía −42 % en desarrollo, por encima de la
  tolerancia del usuario (−35/−40 %). B2 sube al 80 % **justo en las caídas**: en desarrollo su caída máxima es −42,6 %
  (§6). En papel no mueve dinero, pero hay que aceptarlo explícitamente. Alternativas dentro del IPS: (b) + 5 pp
  (75/10/15), con menos efecto y aún menos potencia; (c) «B1 que no recorta en caídas» (si DD ≤ −X, RV = 70 % aunque B1
  dijera menos), que mide si recortar en caídas perjudica, pero ya no es «comprar».
- Costes: los del backtest (10 pb RV/RF, 20 pb oro por lado; TER 0,20/0,15/0,15 %). En desarrollo: rotación 0,14/año y
  ≈ 3,6 pb/año de costes (B1: 0,19 y 4,5 pb). En Alpaca, el coste real se mide aparte (§9).

## 5. Señal en vivo y diferencias de medida (declaradas)
- **Precio frente a rentabilidad total:** en vivo, el S&P 500 de FRED es **precio**; en desarrollo, French incluye
  dividendos. Con dividendos, las caídas desde máximos son algo menores. Sensibilidad: restando un dividendo constante
  aproximado del 3 %/año, el P20 sería **16,4 %** en lugar de 14,7 %. Consecuencia: en vivo, B2 entrará en COMPRA **algo
  más a menudo** que en desarrollo. Se acepta (el mismo tipo de diferencia que en B1: S&P de precio frente a French).
  Decisión del usuario (D3): umbral 14,7 % (regla literal) o 16,4 % (ajustado a la medida de precio).
- **Señal ≠ cartera:** la señal es EE. UU. (S&P 500); la cartera es RV global (French Developed, MSCI World). Igual que B1.
- **Cierres de mes, no máximos diarios:** una caída dentro del mes que se recupera antes del cierre no cuenta. A
  propósito: la decisión es mensual.
- **No se ha calculado el estado actual de B2** (con la caída de noviembre) para que la aprobación de X no dependa de él.

## 6. Comportamiento en desarrollo, 1975-01 … 2004-12 (NO ES VALIDACIÓN)
Mismo periodo que calibra la señal; regla de B1 tal como corre en vivo (σ\* = 17,02 % congelado, también dentro de
muestra); RV valorada con la misma medida que la señal (French EE. UU. en EUR a cierre de mes); RF Bund 5 años; oro del
Banco Mundial (media mensual, sin corregir el efecto Working). La 70/15/15 no se había backtestado antes: estas cifras
son descriptivas y **no deciden nada**.

| | rent. anual | vol. anual | caída máx. | CVaR 5 % mensual | Sharpe | rotación/año | costes pb/año | RV media |
|---|---|---|---|---|---|---|---|---|
| B0 70/15/15 | 10,46 % | 13,99 % | −37,7 % | −8,5 % | 0,389 | 0,06 | 1,8 | 70,5 % |
| B1 (vivo) | 9,93 % | 12,68 % | −29,1 % | −7,6 % | 0,377 | 0,19 | 4,5 | 63,5 % |
| **B2** | **10,44 %** | **14,61 %** | **−42,6 %** | **−9,1 %** | **0,377** | 0,14 | 3,6 | 73,5 % |

Caídas por episodio (recesión ± ventana de `src/factors/backtest.py`):

| | 1980 | 1981-82 | 1990-91 | 2001 |
|---|---|---|---|---|
| B0 | −6,1 % | −10,5 % | −18,7 % | −35,2 % |
| B1 | −7,0 % | −10,2 % | −17,2 % | −27,6 % |
| B2 | −6,1 % | −12,0 % | −21,7 % | −39,7 % |

Tramos (rentabilidad acumulada): 2000-04 → 2003-03 (caída que sigue) B0 −34,3 %, B1 −25,3 %, **B2 −39,4 %**;
1987-09 → 1988-12 (rebote rápido) B0 −9,8 %, B1 −10,1 %, **B2 −8,4 %**; 2003-04 → 2004-12 (recuperación) B0 16,2 %,
B1 13,5 %, B2 17,3 %.

Lectura (descriptiva): **en desarrollo, la inclinación de B2 no añadió rentabilidad frente a B0** (10,44 % frente a
10,46 %) y sí volatilidad y caída (−42,6 % frente a −37,7 %). Frente a B1, B2 rinde ≈ 0,5 pp/año más con ≈ 2 pp más de
volatilidad: es casi todo **más renta variable**, no una prima de la regla. Las 12 entradas en COMPRA tuvieron una RV
media de +18,9 % en los 12 meses siguientes (error típico 5,6 pp) frente a +13,9 % incondicional: + 5 pp, menos de un
error típico, con 12 casos y dentro de muestra. Las peores entradas: 1990-01 (−5,6 %) y 2000-12 (−6,2 %, en plena caída
2000-03).

**Prueba de estrés 1927-1962 (USD, RV + letras, sin oro; mismo X):** 70/30 frente a 80/20 en COMPRA. 1929-09 → 1932-06:
−70,2 % frente a **−74,5 %**; 1932-07 → 1937-02: +221 % frente a +258 %; rentabilidad anual 1927-62: 7,10 % frente a
7,02 %. Comprar en una caída que sigue cuesta caro en el momento y no garantiza compensarlo.

## 7. Cómo se compara con B1/B1′ y cuánto hay que esperar
**Métricas (las del informe 5f, sin cambiar su formato):** rentabilidad acumulada, volatilidad realizada anualizada,
caída máxima, rotación, costes acumulados, últimos pesos; alarma a −30 %. **Añadidos propios de B2** (descriptivos):
estado (NORMAL/COMPRA) y DD_t de cada cierre; nº de entradas; para cada entrada, rentabilidad de la RV y de B2 − B0 a
3, 6 y 12 meses; diferencia acumulada B2 − B1 y B2 − B0.

**Contraste (cuando haya horizonte):** diferencia media mensual B2 − B1 (y B2 − B0), unilateral, H: > 0, error típico
con bloques de 12 meses. Secundario: caída máxima y volatilidad (B2 debería ser peor; si no lo es, algo falla en la
implementación).

**Potencia (`scripts/b2_borrador.py`, desarrollo 1975-2004, 80 % de potencia, unilateral al 5 %):**

| comparación | dif. media anual (dev) | error de seguimiento anual | años necesarios con la dif. de dev | si la dif. real fuera 0,5 pp | si fuera 1 pp |
|---|---|---|---|---|---|
| B2 − B1 | + 0,73 pp | 2,87 % | **≈ 95 años** | ≈ 204 | ≈ 51 |
| B2 − B0 | + 0,07 pp | 1,22 % | **≈ 1 900 años** | ≈ 37 | ≈ 9 |

Bootstrap de bloques de 12 meses con la diferencia de desarrollo (B2 − B1): probabilidad de un resultado significativo
a 3 / 5 / 10 / 20 / 30 años = 20 / 23 / 27 / 34 / 40 %. Con diferencia real nula, ≈ 6-7 % de falsos positivos.

**Conclusión honesta:** el paper trading **no podrá** distinguir B2 de B1 ni de B0 en rentabilidad en ningún horizonte
razonable (y la diferencia de desarrollo frente a B1 es sobre todo más RV, y frente a B0 prácticamente cero). Propuesta
de **horizonte mínimo antes de juzgar nada: 10 años y al menos 3 entradas en COMPRA**, y aun así solo como descriptivo.
Antes de eso, el informe muestra números sin veredicto. Lo que sí se evalúa pronto: que el estado cambia cuando la
regla dice, que la ejecución sigue a la decisión, la rotación y los costes reales.

**B2 frente a B1′:** misma base que B1; la comparación con B1′ es igual de impotente. Se informa, no se contrasta.

## 8. Riesgos
- **Comprar en una caída que sigue** (2008-09, 2000-03, 1929-32): B2 entra con −15 % y la bolsa puede caer otro 30-40 %.
  En desarrollo, 2000-03: −39,4 % frente a −34,3 % de B0. Con la ventana de 12 meses, si la caída dura más de un año el
  máximo de referencia «baja» con ella: B2 puede salir a mitad de la caída (DD vuelve a > −7,35 % sin recuperación real)
  y volver a entrar más abajo. Es la regla; se declara y no se corrige.
- **Caída máxima por encima de la tolerancia del usuario** (−42,6 % en desarrollo): alarma del informe a −30 % igual
  que B0/B1; la alarma avisa, no cambia la regla.
- **Sesgo de narrativa:** la pregunta surge tras una caída concreta (18-nov). Por eso la regla y X se fijan antes del
  primer dato, y el estado actual no se ha calculado.
- **Calibración en el mismo periodo que se muestra** (≤ 2004): §6 está dentro de muestra.
- **Medida:** precio frente a total (§5), EE. UU. frente a global, divisa del BCE a cierre.
- **Multiplicidad:** cada cartera nueva en paralelo aumenta la probabilidad de que alguna «parezca» buena por azar. B2 es
  una sola regla; no se añadirán variantes después de ver datos (cualquier cambio cierra B2 y abre otra versión).

## 9. Registro y espejo en Alpaca (cuando se apruebe; nada de esto existe aún)
- **Congelación:** spec v1.0 + `research/paper/b2_congelado.json` (X, salida, pesos, medida, sha256, procedencia del
  commit con árbol limpio). Primer registro: el primer cierre de mes **después** de la congelación; sin historia
  retroactiva.
- **Registro inmutable** `research/paper/decisiones_b2.jsonl`, con las reglas de mes de `scripts/paper_decision.py`
  (`validar`, `cierre_objetivo`: último fin de mes pasado, sin saltos ni repeticiones) y la misma puerta
  `research/paper/ACTIVO`; estado previo = el del último registro (NORMAL si vacío). Enganche a `paper_mensual.sh` en un
  bloque independiente, como B1′, en un commit aparte que revisa el usuario.
- **Informe 5f:** añadir B2 como cuarta cartera con sus métricas (§7); prerregistrar los añadidos antes del primer dato.
- **Alpaca (otra cuenta paper):** abrir una cuenta paper nueva (*Open New Paper Account*), claves con sufijo `_B2` en
  `~/financial_archive/config/alpaca.env` (`ALPACA_API_KEY_ID_B2`, `ALPACA_API_SECRET_KEY_B2`). Cambio de código
  necesario: `CARTERAS["B2"] = (research/paper/decisiones_b2.jsonl, "b2")` en `src/broker/espejo.py` + tests. Mismo
  mapeo `config/alpaca_etfs.json` (URTH/IEI/GLD; en COMPRA, IEI al 5 %), colchón 0,5 %, mismas reglas de órdenes
  (limit ± 0,5 % si el mercado está cerrado), «una cuenta = una cartera». Declarado: la decisión es de cierre de mes y se
  ejecuta días después (≈ día 3); en una caída rápida, el «deslizamiento frente al cierre» puede ser grande, y es
  precisamente lo que queremos medir.

## 10. Decisiones del usuario
- **D1. Nombre:** «B2» (renombrando el B2 aparcado de INT-5) o «B2c».
- **D2. Tamaño y límites:** (a) 70 → 80 % (propuesta; fuera del rango táctico del IPS, caída de −42,6 % en desarrollo),
  (b) 70 → 75 %, o (c) «B1 que no recorta en caídas» (dentro del IPS).
- **D3. Umbral:** 14,7 % (regla literal, medida total) o 16,4 % (ajuste aproximado a la medida de precio en vivo).
- **D4. Horizonte mínimo** antes de cualquier lectura: 10 años y ≥ 3 entradas (propuesta), sabiendo que ni así habrá
  potencia (§7).
- **D5. Espejo de Alpaca:** abrir la cuarta cuenta paper para B2, o solo el registro teórico.
- **D6. Aprobación** del texto → se congela (v1.0) y se implementa el registro; hasta entonces nada corre.

## 11. Ambigüedades resueltas en el borrador (lo más literal o lo más simple)
1. «Máximo de 12 m» = máximo de los 12 últimos cierres de mes, incluido el actual (no máximos diarios).
2. El percentil 20 se toma sobre **todos** los meses (incluidos los de DD = 0) de 1963-07 … 2004-12, en la medida de
   σ\* de B1; redondeo a 0,1 pp.
3. La salida a −X/2 es una constante fijada a priori (no calibrada); sin ella B2 cambiaría 1,06 veces al año en lugar de
   0,72.
4. Los + 10 pp salen de la RF (como B1, que mueve RV ↔ RF); el oro no se toca.
5. En §6, B1 usa σ\* = 17,02 % congelado (la regla en vivo), no la mediana expansiva de P-DEV-FACT.
