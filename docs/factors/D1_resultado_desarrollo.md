---
documento: D1 «tendencia y volatilidad diaria multiactivo» — resultado del desarrollo (≤ 2004)
estado: NO CORRIDO (2026-11-19). Bloqueado antes de calcular ninguna rentabilidad de D1: (1) el prerregistro congelado
  (7d04137) no estaba en origin/main (regla de sellado) y (2) no hay precio DIARIO del oro ≤ 2004 en el archivo, y la
  spec lo necesita para fijar el periodo (§3) y el listón L1 (§4). Decide el usuario.
spec: docs/factors/D1_tendencia_diaria_spec.md v1.0 (CONGELADA, commit 7d04137); sin cambios de diseño
---

# D1: resultado del desarrollo

## 0. Resumen
**No hay resultado.** Se hizo todo lo que no calcula rentabilidades de D1 (series, inventario, motor con tests
sintéticos, script de la corrida única con fallo cerrado, vivo y espejo) y se paró antes del backtest por dos motivos:

1. **Sellado.** `git fetch origin && git merge-base --is-ancestor 7d04137 origin/main` → falso (comprobado dos veces el
   19-nov). **Falta que el usuario haga push** de `main`. `scripts/d1_desarrollo.py` repite esta comprobación y se niega.
2. **Oro diario.** El archivo solo tiene oro mensual (Banco Mundial, datahub) y anual (MeasuringWorth). §1 dice que un
   activo sin diario ≤ 2005 se excluye, pero §3 define el periodo como «del primer día con datos de al menos bolsa
   EE. UU., bonos **y oro**» y §4 define L1 = 70/15/15 **con oro**: sin oro no hay periodo ni L1 sin cambiar el diseño.
   Lectura conservadora: parar y preguntar, no improvisar un listón.

Fuentes públicas probadas para el oro diario (solo descarga de precios; ninguna rentabilidad calculada):
| fuente | resultado |
|---|---|
| FRED / ALFRED (GOLDAMGBD228NLBM, GOLDPMGBD228NLBM) | retiradas de FRED en 2022; ALFRED: «series does not exist» |
| LBMA (prices.lbma.org.uk/json) | detrás de Cloudflare (página de comprobación) |
| Stooq (xauusd) | verificación JavaScript (no se intenta saltar) |
| Bundesbank BBEX3 | solo fixing de Frankfurt en **DEM**, 1968-06-18 → 1998-12-31 (sin USD ni tras 1998) |

## 1. Opciones para el usuario (ninguna aplicada)
- **A (recomendada, no cambia el diseño):** que el usuario descargue a mano, con su navegador, el histórico diario del
  fixing LBMA en USD (p. ej. la descarga CSV/XLSX de la web de LBMA) a `~/financial_archive/raw/gold/`. Se añade un
  lector en `src/factors/data.py` (familia nueva, corte ≤ 2004), se fija el periodo en `research/factors/d1_series.json`
  con commit y se corre una sola vez. Periodo esperado: desde el primer día con bolsa, bonos y oro + 252 días.
- **B:** oro de Frankfurt (Bundesbank, DEM × DEM/USD diario, ambas en la misma fuente) 1968-1998: el periodo terminaría
  en 1998-12 en vez de 2004-12 (§3) y el fixing de Frankfurt no es el de Londres. Es un cambio de periodo: lo decide el
  usuario y se anota.
- **C:** desarrollo sin oro: L1 deja de ser el de §4 → cambio de listón = **v2 (N = 2 al registro)**.

## 2. Lo que sí está fijado (commit 46d617a, antes de cualquier rentabilidad)
`research/factors/d1_series.json` (solo fechas, recuentos y huecos):
| activo | vivo | desarrollo | cobertura ≤ 2004 |
|---|---|---|---|
| bolsa EE. UU. | SPY | Ken French diario, Mkt-RF + RF (`ffx_us_*_d`) | 1926-07-01 → 2004-12-31, sin huecos |
| bolsa fuera de EE. UU. | VEA | Ken French «Developed ex US» diario en USD (`ffx_devxus_*_d`), compuesto al calendario de EE. UU. | 1990-07-02 → 2004-12-31 |
| bonos largos | TLT | r = y₍t−1₎/252 − 17·Δy; DGS20, y DGS10 en el hueco del 20 a (1987-01 → 1993-09); arrastre ≤ 5 días | 1962-01-03 → 2004-12-31, sin huecos |
| oro | GLD | **sin serie diaria** → bloqueante | — |
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

## 4. Código listo (sin correr con datos reales)
- `src/factors/d1.py` (motor puro) y `tests/test_d1_motor.py` (sintéticos, incluido un extremo a extremo).
- `src/factors/data.py`: `d1_dev`, `d1_bonos_dev`, familia `DGS(10|20)`; `tests/test_d1_datos.py`.
- `scripts/d1_series.py` (inventario) y `scripts/d1_desarrollo.py` (corrida única: sellado → periodo «listo» → nunca
  dos veces; L1, L2, 1 000 placebos, mitades, caída, rotación, costes y criterios §5 a)-d)).
- Vivo: `src/paper/d1.py`, `scripts/paper_decision_d1.py`, `config/alpaca_etfs_d1.json` (SPY, VEA, TLT, GLD, DBC),
  cartera `D1` en `src/broker/espejo.py` (pesos que suman ≤ 100 %, banda de 3 pp frente a la cuenta real),
  `scripts/launchd/com.financialkb.d1.plist` (lun-vie 22:30 Madrid) **sin instalar**; `tests/test_d1_vivo.py`.
  Registrar exige `research/paper/D1_ACTIVO` (no existe). `src/broker/alpaca.py` no se ha tocado: el vivo pide las
  barras **ajustadas** (`adjustment=all`) con el método interno del cliente.
