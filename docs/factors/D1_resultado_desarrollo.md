---
documento: D1 «tendencia y volatilidad diaria multiactivo» — resultado del desarrollo (≤ 2004)
estado: CORRIDA ÚNICA HECHA (2026-11-19T11:13:40Z, git e02684c). PASA los cuatro criterios §5 a)-d) → candidata a
  Alpaca PAPER, con un aviso de sincronía (§0.2) que el Validador debe juzgar antes de activar `D1_ACTIVO`.
spec: docs/factors/D1_tendencia_diaria_spec.md v1.0 (CONGELADA, commit 7d04137); sin cambios de diseño
---

# D1: resultado del desarrollo

## 0. Resumen
Sellado comprobado antes de calcular (`git merge-base --is-ancestor 7d04137 origin/main` verdadero). Periodo y activos
fijados por disponibilidad y commiteados antes (e02684c, `research/factors/d1_series.json`): **1969-05-13 → 2004-12-31,
8 999 días**; activos bolsa EE. UU., fuera de EE. UU. (entra en 1991-06), bonos largos y oro; materias primas
excluidas. Resultado completo en `research/factors/d1_desarrollo.json` (1 000 placebos, bloques de 63 días, semilla
20261119).

| | rent./año | vol | Sharpe | caída máx. | rotación/año |
|---|---|---|---|---|---|
| **D1** (neto, costes 0,46 %/año) | 9,52 % | 4,28 % | **0,77** | **−6,7 %** | 867 % |
| L1 70/15/15 anual (sin costes) | 10,55 % | 11,68 % | 0,41 | −30,5 % | 7 % |
| L2 vol. sin tendencia (neto) | 7,37 % | 6,21 % | 0,23 | −22,9 % | 88 % |

- Placebos: D1 mejor que el **100 %** (p conservador 0,001; mediana placebo 0,06, p90 0,19).
- Mitades (Sharpe D1 / L1 / L2): 1969-05 → 1987-03 **0,91** / 0,38 / 0,11; 1987-03 → 2004-12 **0,63** / 0,44 / 0,37.
- Pesos medios: bolsa EE. UU. 17,6 %, fuera 4,7 %, bonos 13,2 %, oro 11,2 %; **efectivo medio 53 %**.
- Criterios: a) ✅ b) ✅ c) ✅ d) ✅ → **PASA**. Rinde menos al año que L1 (9,5 % frente a 10,6 %) con un tercio de la
  volatilidad: la ventaja es de Sharpe y caída, no de rentabilidad.

### 0.1 Lo que no se ha hecho
Ninguna variante, sensibilidad ni re-corrida. Cualquier cambio de la regla = v2 (N = 2 al registro).

### 0.2 Avisos para el Validador (no cambian el veredicto registrado; pueden pesar en la decisión de activar)
1. **Sincronía.** La decisión se toma al cierre de Nueva York (16:00), pero el oro se valora con el fixing de las 15:00
   de Londres (≈ 10:00 NY) y la bolsa fuera de EE. UU. con cierres de Europa/Asia. La rentabilidad que gana la posición
   (fixing d → d + 1) empieza horas ANTES de la decisión: si hay continuación a muy corto plazo, el backtest la cobra
   sin poder hacerlo. En vivo (GLD, VEA en Nueva York) no existe ese desfase.
2. **Precios rancios** del índice de mercado diario de los años 70-80 (autocorrelación positiva de primer orden) pueden
   inflar las señales de 21 días y el Sharpe de la primera mitad (0,91 frente a 0,63).
3. Rotación ≈ 8,7 veces al año con la banda de 3 pp: los costes de 5 pb/lado (0,46 %/año) son supuestos; el vivo medirá
   los reales.
4. El oro 1968-1975 es el del mercado libre de Londres en el régimen de dos niveles (los particulares de EE. UU. no
   podían tenerlo hasta 1975).

### 0.3 Historia del bloqueo (resuelto)
Al principio se paró antes de calcular: 7d04137 no estaba en origin/main y no había oro diario ≤ 2004 en el archivo
(FRED/ALFRED, LBMA, Stooq y Bundesbank probados sin éxito). El usuario aprobó la **opción A** sin cambio de diseño: el
fixing LBMA de la tarde en USD (serie FRED GOLDPMGBD228NLBM, copia de archive.org, sha256 cf04e466…, procedencia en
`~/financial_archive/raw/gold/LEEME_oro_diario.md`). Festivos de Londres («.»): el precio se arrastra como mucho 5 días
(rentabilidad 0 ese día; el cambio entra el siguiente día con fixing); más de 5 días sin fixing → fallo cerrado (no
ocurre en el periodo).

## 2. Series (commits 46d617a y e02684c, antes de cualquier rentabilidad)
`research/factors/d1_series.json` (solo fechas, recuentos y huecos):
| activo | vivo | desarrollo | cobertura ≤ 2004 |
|---|---|---|---|
| bolsa EE. UU. | SPY | Ken French diario, Mkt-RF + RF (`ffx_us_*_d`) | 1926-07-01 → 2004-12-31, sin huecos |
| bolsa fuera de EE. UU. | VEA | Ken French «Developed ex US» diario en USD (`ffx_devxus_*_d`), compuesto al calendario de EE. UU. | 1990-07-02 → 2004-12-31 |
| bonos largos | TLT | r = y₍t−1₎/252 − 17·Δy; DGS20, y DGS10 en el hueco del 20 a (1987-01 → 1993-09); arrastre ≤ 5 días | 1962-01-03 → 2004-12-31, sin huecos |
| oro | GLD | fixing LBMA 15:00 en USD (FRED GOLDPMGBD228NLBM, archive.org), festivos arrastrados ≤ 5 días | 1968-04-01 → 2004-12-31 |
| materias primas | DBC | **excluido**: sin índice diario ≤ 2004 (el futuro de crudo de la EIA es una sola materia y sin rollo) | — |
| efectivo | cuenta | RF diario de Ken French | 1926-07-01 → 2004-12-31 |

## 3. Lecturas de la spec (anotadas antes de correr; el Validador debe revisarlas)
1. **N_activos** (§2.2) = activos con historia completa (252 rentabilidades y σ de 63 días) ese día; un activo sin
   historia (p. ej. fuera de EE. UU. antes de 1991) pesa 0 y no cuenta.
2. Rentabilidad compuesta exactamente 0 en una ventana → señal 0 («1 si es positiva»).
3. σ = desviación típica (ddof = 1) de 63 rentabilidades diarias × √252.
4. Orden de los pasos: tope del 40 % por activo y después, si la suma pasa del 100 %, escala de todo.
5. Banda (§2.4) frente al peso **derivado** con los precios. Si mantener los activos que no cruzan la banda dejara la
   suma por encima del 100 %, se va al objetivo en todos (nunca hay apalancamiento).
6. Costes por lado sobre |Δw| de cada activo, cargados en la rentabilidad del día siguiente, como S1.
   Rotación = ½·Σ|Δw| contando el efectivo; se informa anualizada (media diaria × 252).
7. **L1 sin costes** (lectura más exigente para D1). **L2** = la misma regla con s = 1 siempre: tope, banda y costes
   incluidos (solo así aísla la tendencia).
8. Placebo: la matriz de señales s de los días de decisión, todas las columnas a la vez, barajada por bloques de 63 días
   (1 000, semilla 20261119); σ, rentabilidades, banda y costes reales. Un activo fuera del universo ese día sigue fuera;
   si al barajar le cae un hueco de calentamiento, s = 0. p conservador = (1 + #placebos ≥ D1)/(N + 1); c) exige p ≤ 0,10.
9. Sharpe = media/desviación de la rentabilidad diaria neta menos RF × √252. Mitades = mitad de los días puntuados.
10. Bonos: devengo y₍t−1₎/252 por día hábil de la bolsa; el 20 a manda donde existe.
11. Fuera de EE. UU.: cierres asíncronos (Asia/Europa cierran antes que Nueva York); se compone sin perder días.

## 4. Código
- `src/factors/d1.py` (motor puro) y `tests/test_d1_motor.py` (sintéticos, incluido un extremo a extremo).
- `src/factors/data.py`: `d1_dev`, `d1_bonos_dev`, familia `DGS(10|20)`; `tests/test_d1_datos.py`.
- `scripts/d1_series.py` (inventario) y `scripts/d1_desarrollo.py` (corrida única: sellado → periodo «listo» → nunca
  dos veces; L1, L2, 1 000 placebos, mitades, caída, rotación, costes y criterios §5 a)-d)).
- Vivo: `src/paper/d1.py`, `scripts/paper_decision_d1.py`, `config/alpaca_etfs_d1.json` (SPY, VEA, TLT, GLD, DBC),
  cartera `D1` en `src/broker/espejo.py` (pesos que suman ≤ 100 %, banda de 3 pp frente a la cuenta real),
  `scripts/launchd/com.financialkb.d1.plist` (lun-vie 22:30 Madrid) **sin instalar**; `tests/test_d1_vivo.py`.
  Registrar exige `research/paper/D1_ACTIVO` (no existe). `src/broker/alpaca.py` no se ha tocado: el vivo pide las
  barras **ajustadas** (`adjustment=all`) con el método interno del cliente.
