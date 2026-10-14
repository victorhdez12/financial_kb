---
documento: programa de investigación de relaciones adelantadas y reglas
version: 0.1
fecha: 2026-10-14
---

# Programa de investigación: indicadores adelantados y reglas "al estilo Dalio"

Objetivo: sacar de los datos **relaciones causa-efecto que se anticipen** al régimen (y a sus cambios), convertirlas en
reglas comprobadas y combinarlas en un sistema. Complementa al modelo de nowcast (`docs/PLAN.md`, Fase 3): las reglas
validadas entran como variables del modelo, como "reglas de oro" para el informe y como alertas.

## 1. Principios (lo que separa esto de buscar correlaciones)

1. **Mecanismo antes que dato.** Dalio parte de cómo funciona la máquina (crédito, deuda, dinero, productividad) y
   después lo comprueba. Toda regla empieza con un mecanismo económico escrito y un signo esperado. Sin mecanismo, no se
   prueba.
2. **Preregistro.** Cada hipótesis se apunta en `research/hypotheses.yaml` **antes** de mirar el resultado: mecanismo,
   indicador, signo, horizonte y objetivo. Se registran también las que fallan.
3. **"Atemporal y universal".** Una regla solo es de oro si funciona en EE. UU. **y** en otros países y épocas: JST,
   18 países desde 1870; BIS; OECD; zona euro. Si solo funciona en EE. UU. 1985-2007, es un accidente.
4. **Solo información point-in-time.** Todas las pruebas usan la base point-in-time (vintages ALFRED y retardos de
   publicación). Una regla que necesita el dato revisado no sirve para anticiparse.
5. **Contar episodios, no meses.** Desde 1950 hay unas 11 recesiones y unas pocas decenas de cambios de cuadrante. Se
   exigen ≥ 6 episodios para evaluar una regla.
6. **El periodo bloqueado (2005-01 → abierto, decidido el 2026-10-14) no se toca** hasta la evaluación final, igual que en el modelo. La investigación usa solo datos ≤ 2004-12. Las variables que nacen después (derivados) se preregistran por teoría y se evalúan solo fuera de muestra.

## 2. Catálogo inicial de hipótesis (por bloque de "la máquina")

| bloque | hipótesis (mecanismo → indicador → efecto) | horizonte | datos |
|---|---|---|---|
| **Crédito** | El impulso de crédito (Δ del crecimiento del crédito en % del PIB) mueve la demanda → G | 6-12 m | Z.1, H.8, BIS |
| | Endurecimiento de la oferta de crédito → caída de inversión → G↓ | 6-12 m | SLOOS |
| | Excess bond premium al alza = menos capacidad de riesgo → recesión | 6-12 m | `fed_ebp` |
| | Diferenciales high yield/BAA ampliándose → G↓ | 3-9 m | FRED |
| **Política monetaria** | Curva 10a-3m invertida → recesión | 6-18 m | FRED, ALFRED |
| | Tipo real por encima del neutral → G↓ con retardo | 6-18 m | FEDFUNDS, expectativas, r* (HLW) |
| | Liquidez neta (balance Fed − TGA − RRP) y M2 real → activos de riesgo y G | 3-6 m | liquidez |
| **Actividad adelantada** | Permisos de construcción, viviendas iniciadas → G | 6-12 m | FRED |
| | Peticiones iniciales de paro, regla de Sahm, empleo temporal → G↓ | 0-6 m | FRED |
| | Encuestas regionales de la Fed (nuevos pedidos, sustituto del ISM) → G | 1-6 m | `fred_us` |
| | Expectativas del consumidor (Michigan, Conference Board) → consumo | 3-6 m | FRED |
| **Inflación** | Petróleo y materias primas → inflación general | 1-3 m | WB, EIA, futuros |
| | Presión de costes (PPI, precios de importación) → inflación subyacente | 3-9 m | FRED |
| | Brecha de paro (paro − NAIRU) y salarios (ECI, Atlanta wage tracker) → subyacente | 6-18 m | FRED, CBO |
| | Expectativas de inflación (breakevens, Michigan, Cleveland) → subyacente | 6-12 m | FRED |
| | Dólar fuerte → importaciones baratas → inflación↓ | 6-12 m | Fed, BIS |
| **Mercados como predictores** | Bolsa y ratio cíclicos/defensivos anticipan G | 3-6 m | French, Shiller |
| | Cobre/oro y pendiente de las curvas de futuros (backwardation = demanda) → G | 3-6 m | futuros |
| | Estructura temporal del VIX invertida → estrés inminente | 0-3 m | CBOE |
| | Extremos de posicionamiento (CFTC) → giros | 1-3 m | `cftc_cot` |
| **Ciclo largo de deuda** | Boom de crédito/PIB (brecha de crédito) → crisis financiera (Schularick-Taylor) | 1-5 años | JST, BIS |
| | Ratio de servicio de la deuda alto → desapalancamiento | 1-3 años | BIS |
| **Global** | Impulso de crédito de China, CLI de la OCDE → G global y materias primas | 6-12 m | BIS, OCDE |

El catálogo crece con hipótesis nuevas. Cada una se registra antes de probarla.

## 3. Lo que aportan los futuros y derivados

Los precios de futuros y opciones dicen **qué está ya descontado**: trayectoria de tipos, inflación esperada, curvas de
materias primas y volatilidad esperada. Tienen dos usos:
- **Variables:** pendiente de curvas (contango/backwardation), estructura del VIX y probabilidades implícitas.
- **Sorpresa frente a lo descontado.** La ventaja no está en saber que viene una desaceleración, sino en verla **antes
  de que el mercado la descuente**. La señal útil es *nuestro nowcast − lo descontado* (p. ej. recortes esperados por los
  futuros frente a nuestra probabilidad de recesión).

## 4. Métodos

Para cada hipótesis, con la base point-in-time:
1. **Estudio de eventos:** trayectoria mediana del indicador en ±24 meses alrededor de cada cambio de régimen y de cada
   recesión, con banda entre episodios. ¿Se mueve antes y en el sentido esperado en la mayoría?
2. **Señal de alerta temprana** (Kaminsky-Reinhart): umbral → tasa de acierto, falsas alarmas, **ratio ruido/señal**,
   adelanto medio y dispersión.
3. **Contenido incremental:** ¿mejora la log-loss del nowcast/forecast frente al baseline (persistencia + régimen
   actual)? Se mide fuera de muestra, en walk-forward. Es la prueba que cuenta: un indicador muy correlacionado con lo
   que ya sabemos no aporta.
4. **Proyecciones locales** (Jordà) para la respuesta de G e I a horizontes de 1-24 meses, con bandas.
5. **Estabilidad:** mismo signo por década, antes y después de 1985, y en otros países (JST, OCDE, zona euro).

**Control de la minería de datos:**
- registro de todas las pruebas;
- corrección por comparaciones múltiples (Benjamini-Hochberg sobre el conjunto de hipótesis);
- para las reglas de trading: Reality Check de White / SPA de Hansen y Deflated Sharpe;
- umbrales fijados en la muestra de entrenamiento y evaluados fuera.

## 5. Ciclo de vida de una regla

`hipótesis` → `candidata` (pasa estudio de eventos + estabilidad en EE. UU.) → `validada` (aporta fuera de muestra, es
universal, sobrevive a la corrección múltiple, y al final, al periodo bloqueado) → `en producción` → `retirada` (si deja
de funcionar; se registra el porqué).

Cada regla se guarda en `config/rules.yaml` con:
- mecanismo, condición exacta y adelanto;
- evidencia (EE. UU. dentro y fuera de muestra, países, ruido/señal, episodios);
- estado, fecha de validación y última revisión.

## 6. Del conjunto de reglas a un sistema

- Como Dalio, se prefieren **muchas señales razonadas y poco correlacionadas, combinadas de forma simple** (pesos
  iguales o con contracción) antes que una optimización fina. El sistema de reglas compite con el GBM en el mismo
  backtest: lo que gane, o la combinación, va a producción.
- Las reglas validadas también alimentan:
  - el informe, como "reglas de oro" que Claude puede citar;
  - un panel de alertas (qué reglas están activas hoy y cuánto adelanto suelen dar).

## 7. Orden

1. Etiqueta v1.0 congelada + base point-in-time + calendario de publicación (en curso).
2. Ingesta de futuros y derivados (en curso) y del resto de datos del catálogo que falten.
3. `research/hypotheses.yaml` con el catálogo de §2 preregistrado.
4. Arnés de investigación: estudios de eventos, alertas tempranas, contenido incremental, estabilidad (`src/research/`).
5. Primera tanda: crédito y política monetaria (las relaciones más sólidas de la literatura) → informe → revisión del
   usuario.
6. Resto de bloques; prueba de universalidad con JST, OCDE y zona euro; sistema de reglas frente al GBM.
