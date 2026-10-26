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

## Pendiente en INT-0
1. **Retrasos de publicación por país y serie** (tabla conservadora, como `PUB_LAG` de EE. UU.).
2. **Rentabilidad total mensual de bonos por país** a partir del tipo largo (método de duración, declarado) y de letras a
   partir del tipo a 3 m; comprobación contra JST en anual.
3. **Constructor del panel armonizado** (anual y mensual; misma moneda: local y EUR; real y nominal), con corte técnico
   en 2004-12 igual que `src/factors/data.py`, para todos los países.
4. **Descarga de la base de revisiones** de la OCDE (para ≥ 2005 y en vivo; no se usa en desarrollo).
5. **Validador independiente** sobre los datos (coherencia JST frente a OCDE en los años comunes, saltos, unidades).
