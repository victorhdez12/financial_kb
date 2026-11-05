# Informe mensual del paper trading B0 / B1 / B1′ — formato fijado (v1.0, 5-nov-2026, antes del primer dato)
Cumple `docs/factors/paper_trading.md` §5 y `docs/factors/B1prima_spec.md` §4. Código: `src/paper/informe.py`; sale en el
reporte semanal como sección **5f** (no escribe en el repositorio: los proxies de French no se redistribuyen).

## 1. Valoración (las tres carteras)
- Proxies de `paper_trading.md` §4 en EUR: RV = French Developed (mercado + letra, USD) × variación del EUR/USD del BCE de
  fin de mes; RF = Bund cupón cero 5 años (y_{t−1}/12 − 5·Δy); oro = Banco Mundial (media mensual, USD) en EUR, órdenes
  con 1 mes de retraso.
- Reglas, costes (10 pb por lado RV/RF, 20 pb oro), TER y bandas de rebalanceo: las del backtest de desarrollo
  (`src.factors.backtest.simular`), con los pesos de cada decisión registrada (rigen desde el mes siguiente).
- Cada cartera empieza el mes siguiente a su primer cierre registrado (B0/B1: 2026-10-31; B1′: el primero con ACTIVO).
- Métricas: rentabilidad acumulada, volatilidad realizada anualizada (dt mensual × √12), caída máxima, rotación (suma de
  ½·Σ|Δw|), costes acumulados, últimos pesos. **Alarma** (aviso, no cambia reglas): caída < −30 % desde máximo.

## 2. Calidad de la previsión de volatilidad (B1 frente a B1′)
- Para cada cierre t: varianza realizada del mes t + 1 = Σ r² diarios del S&P 500 en EUR (misma medida que B1′).
- Previsión de B1 = σ̂²/12 (12 meses de rendimientos mensuales); de B1′ = `f_varianza_mes` registrada.
- QLIKE = RV/f − ln(RV/f) − 1 por mes y su media en los meses con las dos previsiones. **Descriptivo**; solo meses
  completos.
- Declarado: σ̂ de B1 mide la vol. de rendimientos MENSUALES y la RV es de rendimientos DIARIOS; la comparación favorece
  por construcción a la previsión que mira la misma medida (B1′). Es lo que la regla usa, no un contraste.

## 3. Lo que NO hace
- No contrasta ventajas de cartera (sin potencia en años: `paper_trading.md` §5).
- No cambia ninguna regla; cualquier cambio cierra el paper trading y abre uno nuevo, declarado.
