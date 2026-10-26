---
documento: Paper trading de la opción 3 (fase de factores y cartera)
version: 0.1-borrador (2026-10-26)
estado: BORRADOR. Nada registrado. Primera decisión prevista: cierre de 2026-10 (se registra a principios de noviembre).
origen: P-DEV-FACT v0.1, corrida 20261026-102647_pdevfact_v01: ninguna regla de régimen mejora a B1 → opción 3.
---

# Paper trading (opción 3)

## 1. Qué se sigue
- **B0:** cartera de referencia estática **80 % RV / 10 % RF / 10 % oro** (IPS: opción C + 10 % de oro), con su
  rebalanceo (diciembre o bandas ± 5 pp).
- **B1:** B0 con ajuste por volatilidad: RV = 80 % × min(1, σ\*/σ̂<sub>t</sub>), acotada en [65 %, 80 %]; cambio solo si
  mueve ≥ 2,5 pp; lo que sale va a RF; el oro fijo al 10 %.
- Las reglas de régimen V1-V3 **no** se siguen (fallaron en desarrollo).
- **Pendiente del usuario:** la estática cayó −42 % en desarrollo (2001-03, en EUR), por encima de la tolerancia
  (−35/−40 %). Mientras no decida, se siguen las dos y la cartera de referencia no cambia. Cualquier cambio posterior a
  este resultado se declara como decisión a posteriori.

## 2. Señal en vivo (src/paper/live.py)
- **σ̂<sub>t</sub>:** volatilidad de 12 rendimientos mensuales de la RV en EUR al cierre de mes: S&P 500 (`SP500`, FRED,
  precio) / EUR-USD del BCE (`ecb_eurusd_d`). Sustitución declarada frente al desarrollo (EE. UU. con dividendos y
  divisa media del BIS): para la volatilidad, los dividendos no importan y el cierre de mes es mejor que la media.
- **σ\* = 15,48 % congelada:** mediana expansiva de σ̂ 1963-07 → 2004-12 (datos de desarrollo, en EUR). En desarrollo era
  la mediana expansiva hasta t; congelarla evita leer la historia 2005-2025. Declarado. (En USD sería 14,12 %.)
- Falla cerrado si el último dato diario está a más de 5 días del cierre o faltan meses.

## 3. Registro (inmutable)
- `scripts/paper_decision.py --registrar`: una decisión por cierre de mes en `research/paper/decisiones.jsonl` (pesos
  objetivo de B0 y B1, σ̂, entradas), con el árbol limpio, commit y push: la hora del commit en el remoto (rama `main`
  protegida contra reescritura) fecha la decisión. Una segunda decisión para el mismo mes se rechaza.
- Calendario: el primer día hábil con los datos del último día hábil del mes (normalmente el 2.º-3.er día del mes).
  Automatizable con launchd (pendiente de aprobación del usuario).

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
- **Sin juicio antes de 36 meses** (con la potencia de la fase, antes no se distingue nada). Cualquier cambio de reglas
  durante el seguimiento cierra este paper trading y abre uno nuevo, declarado.
- P-EVAL-FACT (≥ 2005), si llega, es secundaria y se prerregistra antes de mirar nada.
