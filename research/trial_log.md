# Registro de pruebas

Toda mirada a datos de resultados (rendimientos de activos, habilidad de un modelo o regla) se anota aquí, **aunque no
se use**, para poder corregir por comparaciones múltiples (Deflated Sharpe, Benjamini-Hochberg) y saber qué está
contaminado. Ver `docs/PLAN.md` (Fase 3) y `docs/models/research_program.md`. El periodo bloqueado (2005-01 →) no se
mira salvo en la evaluación única preregistrada.

| fecha | quién | qué se miró | muestra | particiones/variantes probadas | consecuencia |
|---|---|---|---|---|---|
| 2026-10-15 | Estratega macro (revisión de la etiqueta v1.1) | Rendimientos reales anualizados y volatilidad de bolsa, bonos a 10 años, oro, materias primas, 60/40 y dólar por cuadrante de la etiqueta dura, por recesión NBER y por época (1955-79 / 1980-2004) | 1955-01 → 2004-12 | 2: cuadrantes de la v1.1 y **una** alternativa definida por teoría (crecimiento × dirección de la inflación) | La v1.1 no se cambia (cambiarla tras ver rendimientos sería minería). Cualquier capa o etiqueta v2.0 que use la "dirección de la inflación" cuenta esta prueba en su corrección por comparaciones múltiples. Informe: `docs/reviews/2026-10-15_estratega_macro_etiqueta.md` |
| 2026-10-15 | Constructor (base point-in-time, entregable 2) | Habilidad del **baseline de persistencia point-in-time** (etiqueta frente a etiqueta, sin variables) en los modos `vintage` y `latest_truncated` | 1955-06 → 2004-12 (entrenamiento) | 2 modos | latest_truncated 62,9 % / log-loss 1,228 (reproduce la ficha §12); vintage 61,1 % / 1,300 (n = 579). Ninguna variable implicada. `docs/models/pit_base.md` §6 |
| 2026-10-15 | Constructor (tests de fugas) | **Placebo**: logística multinomial con 8 variables fijadas a priori (curva, empleo, producción, Sahm, IPC subyacente, PPI, Baa, Δ fed funds) + persistencia, frente a solo persistencia, con la etiqueta **barajada en bloques de 24 meses** (10 permutaciones). No se ajustó con la etiqueta real | 1962-01 → 2004-12, walk-forward 1975-2004 | 10 permutaciones, una especificación | Mejora −0,37 a −0,67 nats: sin habilidad (test de la tubería). No informa sobre la relación real variable-etiqueta, que no se ha mirado. `tests/test_pit_leaks.py::test_c_placebo_block_shuffled_label` |
| 2026-10-15 | Constructor (tests de fugas) | **Señal plantada** en un warehouse sintético (régimen de Markov inventado) | sintética 1950-2004 | 1 señal + 1 ruido | Señal +0,23 nats, ruido < 0,02. Sin datos reales. `test_d_planted_signal_recovered_and_noise_not` |
