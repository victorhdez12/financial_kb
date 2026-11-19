---
documento: D1 «tendencia y volatilidad diaria multiactivo» — prerregistro de desarrollo (≤ 2004) y vivo en Alpaca PAPER
version: 1.0 CONGELADA (2026-11-19) — aprobada por el usuario; sin cambios de diseño a partir de aquí
estado: diseño ANTES de calcular ninguna rentabilidad de D1. Nadie ha mirado rentabilidades de reglas de tendencia en
  nuestros datos para escribir esto.
alcance: desarrollo ≤ 2004 (fallo cerrado). No abre el periodo bloqueado (≥ 2005). No toca B0/B1/B1′ ni sus registros.
---

# D1: cartera diaria por tendencia y volatilidad

## 0. Qué es y qué no es
- Decisión del usuario (19-nov): carteras **activas diarias** que compitan con B0/B1/B1′ (que siguen mensuales y sin
  cambios). D1 es la sistemática; C1 (`docs/factors/C1_claude_gestor_spec.md`) es la discrecional.
- Regla de **seguimiento de tendencia por activo** (time-series momentum) con **objetivo de volatilidad**, solo largos.
  La idea viene de la literatura (Moskowitz-Ooi-Pedersen 2012; Hurst-Ooi-Pedersen «A century of evidence on
  trend-following», 2017), **no de nuestros datos**. Declarado: esa literatura usa datos que se solapan con nuestro
  desarrollo → el listón incluye placebos (§5).
- Antecedente: el ajuste por volatilidad (B1) sí funcionó en desarrollo; las reglas de régimen macro (V1-V3, S1) no.

## 1. Universo (5 activos + efectivo) y datos
| activo | vivo (ETF) | desarrollo ≤ 2004 (diario) |
|---|---|---|
| bolsa EE. UU. | SPY | mercado Ken French diario (`ff_mkt + ff_rf`) |
| bolsa fuera de EE. UU. | VEA | el mejor índice diario disponible en el archivo; si no hay, se quita del desarrollo (declarado) |
| bonos Tesoro largo | TLT | rentabilidad aproximada desde el 10 a / 20 a diario de FRED (duración ≈ 17, declarada) |
| oro | GLD | precio diario del oro disponible en el archivo |
| materias primas | DBC | índice diario disponible (GSCI u otro); si no hay, se quita del desarrollo (declarado) |
| efectivo | (no se invierte: queda en la cuenta) | `ff_rf` diario |
El Constructor fija las series y el **periodo de puntuación solo por disponibilidad de datos**, y lo anota con
commit ANTES de calcular ninguna rentabilidad de D1. Si falta el diario de un activo antes de 2005, ese activo se
excluye del desarrollo y se declara; la regla no cambia.

## 2. Regla (única; N = 1)
Cronología: señal con el **cierre del día d**; pesos nuevos rigen la rentabilidad desde el cierre de d hasta d + 1
(en vivo: órdenes en la apertura o en la sesión de d + 1; se declara la diferencia).
1. **Tendencia por activo:** s = media de 3 señales, sign(rentabilidad de los últimos 21, 63 y 252 días hábiles),
   cada una 0 si es negativa y 1 si es positiva → s ∈ {0, ⅓, ⅔, 1}. (Solo largos: tendencia negativa = 0.)
2. **Tamaño por volatilidad:** peso bruto del activo i = s_i × (10 % / N_activos) / σ_i, con σ_i = volatilidad anualizada
   de 63 días hábiles.
3. **Tope:** cada activo ≤ 40 %; suma ≤ 100 % (sin apalancamiento; si pasa de 100 %, se escala todo). Lo que sobra,
   efectivo.
4. **Banda de no operar:** solo se opera un activo si su peso objetivo se separa ≥ **3 pp** del actual (limita la
   rotación diaria).
5. **Costes:** 5 pb por lado en ETFs (bolsa, bonos, oro), 10 pb en materias primas, sobre la rotación.

## 3. Periodo
- Principal: del primer día con datos de al menos bolsa EE. UU., bonos y oro (+ 252 días de calentamiento) a
  2004-12-31. Mitades por separado.

## 4. Listones
- **L1 = B0 diaria equivalente** (70/15/15 bolsa EE. UU./bonos/oro, rebalanceo anual): lo que hace el inversor pasivo.
- **L2 = misma volatilidad sin tendencia**: los mismos pesos por volatilidad del paso 2 con s = 1 siempre (aísla el
  valor de la tendencia frente al del ajuste por volatilidad).
- **Placebo:** 1 000 secuencias de señales barajadas por bloques de 63 días.

## 5. Criterio para pasar a Alpaca como candidata (todos)
a) Sharpe neto de D1 ≥ Sharpe de L1 **y** ≥ Sharpe de L2.
b) Caída máxima de D1 ≤ caída máxima de L1.
c) D1 mejor que el **90 %** de los placebos en Sharpe (p ≤ 0,10).
d) Sharpe de D1 ≥ L2 en **cada mitad**.
Si falla: no entra como candidata; el usuario decide observación o cierre. Sin re-corridas con la regla ajustada
(cualquier v2 = N = 2 al registro).

## 6. Vivo (Alpaca PAPER, cuenta del 2.º usuario, perfil `D1`)
- Cada día hábil tras el cierre de EE. UU. (≈ 22:30 Madrid) calcula la señal con cierres IEX/consolidados del día;
  envía órdenes **limit ± 0,5 %** para la sesión siguiente, o de mercado si se corre con el mercado abierto. Registro
  propio inmutable `research/paper/decisiones_d1.jsonl` (commit diario; misma regla de árbol limpio).
- Mismo espejo y mismas protecciones que B0/B1/B1′: solo `paper-api`, nunca dinero real, sin margen (el código no usa
  el poder de compra 2× de Alpaca), sin cortos.
- Límite: años de paper no confirman la ventaja; mide implementación, costes y rotación reales.
