---
documento: Paper trading de la opción 3 (línea A, cartera operativa)
version: 0.2 (2026-10-26) — APROBADA por el usuario con correcciones (hechas en esta versión)
estado: activo en cuanto el usuario apruebe el ensayo del cierre de 2026-10 (crea research/paper/ACTIVO). Nada registrado.
origen: P-DEV-FACT v0.1, corrida 20261026-102647_pdevfact_v01: ninguna regla de régimen mejora a B1 → opción 3.
---

# Paper trading (línea A)

## 1. Qué se sigue
- **B0:** cartera de referencia estática **70 % RV / 15 % RF / 15 % oro**, con su rebalanceo (diciembre o bandas ± 5 pp).
- **B1:** B0 con ajuste por volatilidad: RV = 70 % × min(1, σ\*/σ̂<sub>t</sub>), acotada en **[55 %, 70 %]** (− 15 pp);
  cambio solo si mueve ≥ 2,5 pp; lo que sale va a RF; el oro fijo al 15 %.
- **Decisión declarada a posteriori:** la referencia pasó de 80/10/10 a 70/15/15 (oro del 10 al 15 %) **después** de ver
  que la 80/10/10 caía −42 % en desarrollo (2001-03, en EUR), por encima de la tolerancia del usuario (−35/−40 %). Es una
  decisión de tolerancia al riesgo, no de rentabilidad. La 70/15/15 no se ha backtestado.
- Las reglas de régimen V1-V3 **no** se siguen. El nowcast no interviene en la cartera.

## 2. Señal en vivo (src/paper/live.py)
- **σ̂<sub>t</sub>:** volatilidad de 12 rendimientos mensuales de la RV en EUR: **S&P 500** (`SP500`, FRED, precio) / EUR-USD
  del BCE, **ambos a cierre de mes**.
- **σ\* = 17,02 % congelada, en la misma medida** (precio y divisa a cierre de mes): mediana de σ̂ 1963-07 → 2004-12 con
  el mercado de EE. UU. de French (cierre de mes) en EUR con el fixing DEM/USD de Frankfurt (Bundesbank, ≤ 1998) y el BCE
  (≥ 1999) (`scripts/paper_sigma_star.py`, `research/paper/sigma_star.json`). Elegida por la regla "misma medida que en
  vivo", no por resultados. Valor anterior: 15,48 % (divisa media del BIS). Alternativa declarada y no usada: solo tipos
  flotantes (1973-2004), 18,72 %. Frecuencia de recorte de B1 en desarrollo (propiedad de la señal): con 17,02 %, 57 % de los
  meses desde 1963 y 71 % desde 1975; con 15,48 %, 62 % y 71 %.
- Falla cerrado si el último dato diario está a más de 5 días del cierre o faltan meses.

### Por qué la señal usa el S&P 500 y la valoración French Developed
- **Señal = S&P 500:** es la única serie de renta variable diaria y sin retraso en el warehouse; la decisión se toma a
  los pocos días del cierre. French publica con ≈ 2 meses de retraso, así que no sirve para decidir a tiempo. La señal
  solo necesita la **volatilidad**, y la del S&P 500 es casi la del mercado mundial desarrollado (EE. UU. pesa ≈ 70 %).
- **Valoración = French Developed:** la cartera invierte en RV **global** desarrollada; para medir lo que habría ganado
  o perdido hay que usar ese universo, con dividendos. Se valora con retraso, cuando se publica.
- Consecuencia declarada: señal y cartera no son el mismo índice; si EE. UU. y el resto divergen mucho en volatilidad, la
  señal puede recortar de más o de menos.

## 3. Registro (inmutable) y automatización
- `scripts/paper_decision.py --auto --registrar`: una decisión por cierre de mes en `research/paper/decisiones.jsonl`
  (pesos objetivo de B0 y B1, σ̂, entradas), con el árbol limpio, commit y push (la hora del commit en el remoto, rama
  `main` protegida, fecha la decisión).
- **Reglas (con tests, `tests/test_paper_decision.py`):** solo se registra el **último fin de mes pasado**; nunca un mes
  futuro, atrasado o que no sea fin de mes; nunca dos veces el mismo mes; sin saltos (el siguiente cierre tiene que ser el
  inmediatamente posterior al último registrado). Si un mes se pierde, la cadena se para y avisa: decide el usuario.
- **launchd** `com.financialkb.paper` (`scripts/paper_mensual.sh`): cada día a las 10:00 y al encender el Mac; desde el
  día 3 intenta registrar; espera a la red y a que termine la actualización diaria. Si falla (árbol sucio, datos con más
  de 5 días, push fallido…): notificación de macOS + línea en `obsidian/Proyecto/Actualizaciones.md`, y reintento al día
  siguiente. Mientras no exista `research/paper/ACTIVO`, solo ensaya y avisa ("pendiente de aprobación").

## 4. Instrumentos (para valorar; sin compra real)
| tramo | instrumento tipo | proxy de valoración |
|---|---|---|
| RV | ETF/fondo UCITS MSCI World, acumulación, sin cubrir | Ken French Developed (`ffx_dev_mkt_rf_m` + `ffx_dev_rf_m`) en EUR con el BCE a cierre de mes (≈ 2 meses de retraso) |
| RF | ETF/fondo de deuda pública euro, duración ≈ 5 | Bund cupón cero 5 años a cierre de mes (Bundesbank) |
| oro | ETC de oro físico | precio de cierre de mes si se valida una fuente (candidata: fixing de Londres en la Bundesbank); si no, media mensual del Banco Mundial con un mes de retraso en las órdenes, como en desarrollo |
| costes | 10 pb por lado RV/RF, 20 pb oro; TER 0,20/0,15/0,15 % | — |

## 5. Seguimiento y evaluación
- Informe mensual (tras cada valoración): rentabilidad, volatilidad realizada, caída desde máximo y rotación de B0 y B1.
- **Alarma (no cambia reglas):** si B0 o B1 caen más de −30 % desde máximo, aviso al usuario.
- **36 meses no tienen potencia para distinguir B1 de B0.** En desarrollo, 30 años dieron una diferencia de volatilidad
  de 1,7 pp; en 36 meses el error de esa diferencia es varias veces mayor y puede que no haya ni un episodio de estrés. El
  paper trading **valida la implementación y el comportamiento en vivo** (que la señal se calcula a tiempo, que los
  recortes ocurren cuando deben, costes y rotación reales), **no la ventaja** de B1 sobre B0.
- Cualquier cambio de reglas durante el seguimiento cierra este paper trading y abre uno nuevo, declarado.
- P-EVAL-FACT (≥ 2005), si llega, es secundaria y se prerregistra antes de mirar nada.
