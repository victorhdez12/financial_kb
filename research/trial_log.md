# Registro de pruebas

Toda mirada a datos de resultados (rendimientos de activos, habilidad de un modelo o regla) se anota aquí, **aunque no
se use**, para poder corregir por comparaciones múltiples (Deflated Sharpe, Benjamini-Hochberg) y saber qué está
contaminado. Ver `docs/PLAN.md` (Fase 3) y `docs/models/research_program.md`. El periodo bloqueado (2005-01 →) no se
mira salvo en la evaluación única preregistrada.

| fecha | quién | qué se miró | muestra | particiones/variantes probadas | consecuencia |
|---|---|---|---|---|---|
| 2026-10-15 | Estratega macro (revisión de la etiqueta v1.1) | Rendimientos reales anualizados y volatilidad de bolsa, bonos a 10 años, oro, materias primas, 60/40 y dólar por cuadrante de la etiqueta dura, por recesión NBER y por época (1955-79 / 1980-2004) | 1955-01 → 2004-12 | 2: cuadrantes de la v1.1 y **una** alternativa definida por teoría (crecimiento × dirección de la inflación) | La v1.1 no se cambia (cambiarla tras ver rendimientos sería minería). Cualquier capa o etiqueta v2.0 que use la "dirección de la inflación" cuenta esta prueba en su corrección por comparaciones múltiples. Informe: `docs/reviews/2026-10-15_estratega_macro_etiqueta.md` |
