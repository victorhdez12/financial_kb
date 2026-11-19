---
documento: S1 «rotación de sectores por régimen macro» — prerregistro de desarrollo (≤ 2004) y espejo Alpaca PAPER
version: 0.1 BORRADOR (2026-11-19) — pendiente de aprobación del usuario; NO congelado
estado: diseño ANTES de calcular ninguna rentabilidad de S1. Ni el autor ni ningún agente ha mirado rentabilidades por
  régimen de las industrias de Ken French para escribir esto.
alcance: desarrollo ≤ 2004 (corte de `src/factors/data.py`, fallo cerrado). No abre el periodo bloqueado (≥ 2005).
  No toca B0/B1/B1′ ni sus registros.
---

# S1: rotación de sectores según el régimen macro

## 0. Qué es y qué no es
- Decisión del usuario (19-nov): tercera cuenta Alpaca PAPER con una cartera de **acciones basada en la macro**;
  **primero historia (≤ 2004), luego vivo**. Las otras dos cuentas: B1 y B1′.
- Es una cartera **100 % renta variable de EE. UU.** que inclina los pesos por sectores según el cuadrante del
  clasificador de régimen **en vivo** (`src/regime/classify.py`, el mismo que sale cada día en `Actualizaciones.md`).
  No compite con B1 (otra clase de activo): su listón es la propia bolsa sin inclinación (§4).
- Antecedente honesto: las reglas de régimen V1-V3 (bolsa ↔ bonos) **no** mejoraron a B1 (P-DEV-FACT, 26-oct). Que la
  macro no sirva para cronometrar la bolsa entera no implica que no sirva para elegir sectores, pero el previo es escéptico.
- La asignación régimen → sectores (§3) viene de la literatura del ciclo (reloj de inversión de Merrill Lynch 2004,
  rotación sectorial clásica de Stovall), **no de nuestros datos**. Declarado: esa literatura usó datos que se solapan
  con nuestro periodo de desarrollo, así que el desarrollo no es una muestra independiente de la idea; por eso el
  listón incluye placebos (§5).

## 1. Datos (vía `src/factors/data.py`, corte 2004-12, fallo cerrado)
- **Sectores:** Ken French, 12 industrias, ponderadas por capitalización, rentabilidad total mensual en USD
  (`~/financial_archive/raw/ken_french/12_Industry_Portfolios_CSV.zip`). Moneda: **USD** (la cuenta Alpaca es en USD).
- **Mercado:** `ff_mkt_rf_m + ff_rf_m`. **Efectivo:** `ff_rf_m`.
- **Señal:** cuadrante del clasificador **point-in-time** (base PIT v0.4, vintages ALFRED donde existan; si no,
  `latest_truncated` con los retrasos de publicación de la base), con la información disponible al cierre de t. Si el
  Constructor no puede reconstruir el cuadrante PIT con el **mismo código** que corre en vivo, se para y avisa (no se
  improvisa otra señal).

## 2. Periodo
- **Puntuación principal:** desde el primer mes con cuadrante PIT disponible (lo fija el Constructor **solo por
  disponibilidad de datos**, antes de calcular rentabilidades, y lo anota en el registro) hasta **2004-12**.
- **Mitades:** se informa también cada mitad del periodo por separado (consistencia, §5c).

## 3. Regla (única; N = 1 candidata)
Cronología: el cuadrante se fija con la información del **cierre de t**; los pesos rigen la rentabilidad de **t + 1**.

| cuadrante (clasificador en vivo) | sectores favorecidos (industrias French) |
|---|---|
| **Goldilocks** (G↑ I↓) | BusEq, Durbl, Shops, Money |
| **Reflación** (G↑ I↑) | Enrgy, Chems, Manuf, Money |
| **Estanflación** (G↓ I↑) | Enrgy, Utils, NoDur, Hlth |
| **Deflación/recesión** (G↓ I↓) | NoDur, Hlth, Utils, Telcm |

- **Pesos:** 50 % **núcleo** = el mercado (las 12 industrias con su peso por capitalización del mes anterior;
  aproximación: `ff_mkt`) + 50 % **inclinación** = repartido a partes iguales entre los 4 sectores favorecidos.
  Sin cortos, sin apalancamiento, siempre invertida al 100 %.
- **Cambio:** solo cuando cambia el cuadrante (como mucho una vez al mes). Sin cuadrante (dato ausente) → se mantienen
  los pesos anteriores. «Other» nunca se favorece (no tiene ETF limpio, §6).
- **Costes:** 10 pb por lado sobre la rotación (½·Σ|Δw|); TER no se descuenta (iguales en S1 y listón salvo ±0,1 %).

## 4. Listón
- **L0 = mercado** (`ff_mkt + ff_rf`), la cartera que S1 tendría sin inclinar.
- **Placebo:** 1 000 secuencias de cuadrantes **barajadas por bloques** (bloques de 12 meses, misma frecuencia de
  cuadrantes y de cambios) aplicadas a la misma regla de pesos.

## 5. Criterio para pasar a Alpaca como candidata (todos)
a) Rentabilidad activa neta de costes frente a L0 **> 0** y ratio de información **≥ 0,20**.
b) S1 **mejor que el 90 %** de los placebos en rentabilidad activa (p ≤ 0,10).
c) Rentabilidad activa ≥ 0 en **cada mitad** del periodo.
d) Caída máxima de S1 **no peor que L0 en más de 5 pp**.

Si falla: **no** entra en Alpaca como candidata. El usuario puede decidir llevarla igualmente como **observación**
(declarada «falló en desarrollo»), o cerrar la línea. No se ajusta la regla y se vuelve a correr: cualquier S1 v2 es
una prueba nueva que se anota (N = 2) en `research/trial_log.md`.

## 6. Vivo: espejo Alpaca PAPER (tercera cuenta, perfil `S1`)
| industria French | ETF | diferencia declarada |
|---|---|---|
| BusEq | XLK | XLK es más estrecho (sin parte de servicios de empresa) |
| Durbl | XLY | XLY mezcla duraderos con comercio (AMZN, TSLA) |
| Shops | XRT | XRT es equiponderado |
| Money | XLF | — |
| Enrgy | XLE | — |
| Chems | XLB | XLB incluye minería y envases |
| Manuf | XLI | — |
| Utils | XLU | — |
| NoDur | XLP | — |
| Hlth | XLV | — |
| Telcm | XLC | XLC incluye medios e internet (GOOGL, META) |
| núcleo (mercado) | VTI | — |

- Decisión al cierre de cada mes con el cuadrante de la diaria de ese día; registro propio inmutable
  `research/paper/decisiones_s1.jsonl`, mismas reglas de árbol limpio y commit que B1.
- El espejo (`src/broker/espejo.py`) necesita admitir esta cartera (pesos por ETF en vez de tramos RV/RF/oro): cambio
  pequeño, con tests, sin tocar el comportamiento de B0/B1/B1′.
- **Límite de lo que dirá el vivo:** con 12 cambios de pesos como mucho al año y cuadrantes que duran meses, años de
  paper no tienen potencia para confirmar la ventaja; el vivo valida implementación, ejecución y coste real.

## 7. Registro
Una sola corrida de desarrollo (S1, L0, placebos, mitades, caída, rotación, tabla de cuadrantes por año) al registro
`research/trial_log.md` y a `docs/factors/S1_resultado_desarrollo.md`, también si falla.
