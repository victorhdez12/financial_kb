---
documento: Especificación de B1′ (B1 con previsión diaria de volatilidad), para paper trading EN PARALELO
version: 1.0 (2026-10-30) — congelada junto con docs/int/INT12_prerregistro_v1.md, ANTES de la corrida de INT-12
estado: SOLO DOCUMENTO. No se implementa ni se registra nada hasta que (a) C1 de P-DEV-INT12 quede "establecido" y
        (b) el usuario apruebe el paso a código. B1 y su paper trading (docs/factors/paper_trading.md) NO se tocan.
---

# B1′: la misma regla que B1, con una σ̂ que mira datos diarios

## 1. Por qué
B1 recorta la renta variable con σ̂ = volatilidad de los 12 últimos rendimientos mensuales. INT-12 fase 1 mostró (en
simulación) que esa σ̂ es una mala previsión de la volatilidad del mes siguiente y que un HAR con datos diarios la
mejora ≈ 50 % en QLIKE. P-DEV-INT12 C1 lo comprueba con datos reales ≤ 2004. **Una mejor previsión no garantiza una
mejor cartera**: por eso B1′ va en paralelo, no en sustitución.

## 2. Condición de apertura (fijada antes de la corrida)
- Se abre **solo si C1 queda "establecido"** en `research/int/int12_resultado.json`. Si no, B1′ no existe.
- Lo que digan C2 y C3 **no cambia** B1′ (σ̂′ es el HAR sin X): se evita elegir la versión después de ver resultados.

## 3. Regla (idéntica a B1 salvo σ̂ y σ\*)
- Referencia 70 % RV / 15 % RF / 15 % oro. RV = 70 % × min(1, σ\*′ / σ̂′_t), acotada en [55 %, 70 %]; cambio solo si
  mueve ≥ 2,5 pp; lo que sale va a RF; oro fijo al 15 %. Mismos instrumentos, costes y calendario que B1.
- **σ̂′_t = √(12 · f_t)**, con f_t la previsión HAR a 1 mes de la varianza de la RV **en EUR**:
  - rendimientos diarios en EUR: r = (1 + r_USD) · (EURUSD_{t−1} / EURUSD_t) − 1 (S&P 500 precio de FRED `SP500` y
    BCE `ecb_eurusd_d` en vivo; en desarrollo, mercado de EE. UU. diario de AQR con DEM/USD del Bundesbank ≤ 1998 y el BCE
    desde 1999);
  - log-HAR con medias de r² de 5, 21 y 63 días (como P-DEV-INT12), **coeficientes estimados una sola vez** con todos los
    meses 1963-07 … 2004-11 en esa medida y **congelados** (no se re-estiman en vivo);
  - el número de días hábiles del mes siguiente se toma del calendario de la NYSE.
- **σ\*′** = mediana de σ̂′ en 1963-07 … 2004-12 en la misma medida (regla "misma medida que en vivo", como σ\* de B1),
  con los coeficientes congelados (dentro de muestra, declarado). Se calcula una vez, se publica y se congela.
- Falla cerrado como B1: dato diario de más de 5 días o meses que faltan → no se decide y se avisa.

## 4. Registro y seguimiento
- Fichero propio `research/paper/decisiones_b1prima.jsonl` (inmutable), mismas reglas de fin de mes que B1
  (`tests/test_paper_decision.py` como modelo), arranca el primer cierre de mes después de la aprobación; sin historia
  "retroactiva".
- Informe mensual junto al de B0/B1: σ̂ y σ̂′, pesos, rotación, costes, volatilidad realizada y caída de B1′.
- **Sin potencia para ventaja de cartera** (como B1 frente a B0 en 36 meses). Lo que sí se puede evaluar en vivo:
  la calidad de la previsión (QLIKE de σ̂′ frente a σ̂ mes a mes), la rotación y los costes.
- Cualquier cambio de esta regla cierra B1′ y abre otra versión declarada. P-EVAL (≥ 2005) no se usa.
