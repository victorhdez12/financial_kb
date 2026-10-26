---
documento: INT-0 — datos del panel internacional (estado y tareas)
version: 0.1 (2026-10-26)
plan: docs/PLAN_internacional_v0.md (aprobado 26-oct)
---

# INT-0: datos del panel internacional

**Panel:** los 18 países de JST (AUS, BEL, CAN, CHE, DEU, DNK, ESP, FIN, FRA, GBR, IRL, ITA, JPN, NLD, NOR, PRT, SWE, USA).
Matriz de cobertura completa: `research/int/cobertura.md` (`scripts/int0_cobertura.py`, solo cuenta observaciones).

## Hecho (26-oct)
- **OCDE ampliada** (`src/ingest/oecd.py`): los 6 países JST que faltaban (BEL, DNK, FIN, IRL, NOR, PRT) en paro, tipos,
  bolsa e IPC; **producción industrial** (`oecd_ip_*`, PRVM, industria sin construcción, desestacionalizada) y **ventas
  minoristas** en volumen (`oecd_retail_*`). 339 → 427 series. Mismo número de consultas (límite de la API ≈ 20/hora).
- **Cobertura mensual resultante** (año de inicio, mayoría de países): producción industrial 1955-1965 (16/18), IPC 1955
  (18/18), IPC subyacente 1955-1979 (18/18), tipos largos 1955-1993 (18/18), tipos a 3 m 1956-2002 (18/18), bolsa (precio)
  1950-1988 (18/18), paro 1955-1991 (17/18), CLI (9/18).
- **Anual (JST):** macro de los 18 desde 1870 (IRL desde ~1920); rentabilidad total de bolsa, bonos, letras y vivienda de
  16 (faltan CAN e IRL).

## Huecos conocidos (declarados)
- **AUS:** sin producción industrial mensual (solo trimestral) e IPC mensual solo desde 2024 (antes trimestral).
- **CHE:** producción industrial mensual solo desde 2010 (trimestral antes).
- **CLI:** la OCDE ya no publica CLI de 9 países pequeños.
- **CAN, IRL:** sin rentabilidades de activos en JST.
- **Paro mensual** de DEU solo desde 1991 (unificación) y de CHE no hay.
- **Tiempo real:** la base de revisiones de la OCDE (`DF_STES_REVISIONS`) tiene vintages mensuales **solo desde 2008-03**
  (224 ediciones: producción, IPC, paro, ventas, CLI, PIB/tendencia). Todo el desarrollo internacional (≤ 2004) será con
  **datos revisados**; las fechas se tratan con retrasos de publicación conservadores. Los vintages sirven para la
  evaluación final (≥ 2005) y para operar en vivo. Declarado.
- **Licencias:** JST CC BY-NC-SA (no comercial); OCDE CC BY 4.0; AQR y French sin redistribución.

## Hecho (26-oct, tarde): tareas 1-3
- **Retrasos de publicación** (`src/intl/lags.py`): un número conservador por medida, igual para todos los países (IP,
  ventas y paro 60 días; IPC 30; CLI 45; encuestas 10; mercado 1; JST anual 120). Muestreo "as of" con las reglas de
  `src/regime/asof.py`.
- **Bonos y letras mensuales** (`src/intl/returns.py`): bono a la par a 10 años (duración + convexidad) desde el tipo largo;
  letras desde el tipo a 3 m. Los tipos OCDE son medias mensuales (suavizado declarado).
- **Panel armonizado** (`src/intl/panel.py`, corte técnico `src/intl/data.py` = mismo DEV_END 2004-12 y fallo cerrado):
  anual 2.380 país-año (JST) y mensual 11.880 país-mes (1950-2004), en `$FIN_DATA_ROOT/intl/` (fuera de git);
  `scripts/int0_panel.py`, resumen `research/int/panel.json`. Tests `tests/test_intl_panel.py` (5 ✅).
- **Coherencia con JST (anual 1960-2004):** bonos con correlación 0,90-0,99 en 15 países y diferencia media ≤ 1,4 pp,
  salvo **ESP** (0,83; +2,6 pp); bolsa (precio OCDE + dividendo JST) 0,95-0,999 salvo **FRA** (+3,2 pp), **DNK** (0,65) y
  **JPN** (0,70). Para el Validador.
- **Países con huecos** (AUS, CHE, CAN, IRL…): se reservan como **países de prueba** fuera de muestra (decisión del
  usuario, 26-oct): se verá cómo se comporta el modelo en ellos con lo que tengan.

## Validador (27-oct): ⚠️ usable tras corregir → corregido
Informe `docs/validation/2026-10-27_int0_datos.md` (rama `claude/int0-validacion`, `41fd273`; la sesión no escribió el
código). Corte técnico ✅, fórmula del bono ✅. Diff del Validador aplicado y verificado en local:
- **A1 (ALTO, confirmado):** las diferencias contaban observaciones, no meses (IPC trimestral de IRL hasta ~1975, meses
  sueltos en FIN/PRT) → rejilla mensual completa antes de transformar; `load_dev` y la ingesta OCDE fallan con fechas
  repetidas (comprobado: con los datos de hoy no hay ninguna, la ingesta diaria no se rompe); control de años en el anual.
- **A2 (ALTO, probable):** el paro mensual de 9 países (BEL, DNK, FRA, GBR, IRL, ITA, NLD, PRT, SWE) empieza en 1983,
  interpolado de encuestas → **excluido antes de 1998-01** (decisión del Constructor, prudente).
- **M1:** retrasos subidos para los calendarios históricos: IP/ventas/paro 75 días, IPC 45, CLI 60.
- **CLI y `crisisjst`:** filtros de dos lados / clasificación ex post → **no se usan como variables "as of"**.
- **Casos JST, confirmados en local** (`scripts/int0_diagnostico.py`, `research/int/diagnostico.json`): ESP bono
  +5,1 pp ≤ 1991 frente a +0,4 pp ≥ 1992 → bono mensual de ESP desde 1992 (corr. 0,99); FRA: el índice OCDE ya es de
  rentabilidad total (−0,5 pp sin sumar dividendo) → corregido; DNK y JPN: rupturas del índice (residuos concentrados en
  1985/1988/1993 y 1972-73) → sin bolsa mensual OCDE, se usa AQR desde 1986.
- **Saltos (29 series):** casi todos hechos reales (mayo del 68 en FRA, huelga general de SWE 1980, cierre patronal de
  NOR 1986, semana de tres días de GBR 1974, IVA de GBR 1979, impuesto al consumo de JPN 1997); sin errores de unidades.
  Declarados; la IP de BEL antes de 1962 es ruidosa.
- Tests del panel: 9 ✅ (2 nuevos del Validador).

## Pendiente en INT-0
1. (hecho) · 2. (hecho) · 3. (hecho; la conversión a EUR se hace al usarlo)
4. **Descarga de la base de revisiones** de la OCDE (para ≥ 2005 y en vivo; no se usa en desarrollo).
5. (hecho: Validador ⚠️ → corregido; ver arriba)
