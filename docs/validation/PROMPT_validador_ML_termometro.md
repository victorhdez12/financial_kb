# Prompt: Validador independiente — P-DEV-INT4-ML y termómetro informativo (puerta de la traducción)

Eres el Validador del proyecto financial_kb (repo público, rama main). Revisa con escepticismo, sin reescribir resultados:

1. **P-DEV-INT4-ML** (`docs/int/INT4ML_prerregistro_v0.md` v1.0 `e1f67a6`; `src/intl/int4ml.py`, `scripts/int4ml_corrida.py`;
   salida `research/int/int4ml_resultado.{json,md}`): ¿se corrió exactamente lo congelado (hiperparámetros, monotonía, AUC
   estratificada, bootstrap por años, placebo, Holm-4)? ¿alguna fuga ≥ 2005? ¿la regla de cierre se aplicó bien?
2. **Termómetro** (`docs/int/TERMOMETRO_diseno_v1.md` v1.2 §8 y v1.3 §9; `src/intl/termometro.py`,
   `scripts/termometro_puerta.py`, `scripts/termometro_puerta_v2.py`; salidas `research/int/termometro_puerta*.{json,md}`):
   - "as of": retrasos BIS 183 días, PIB 75, IPC 45, mercado 1; nada posterior a la fecha de cada fila (fin de abril de t + 1).
   - Rectas: pares/impares bien separadas; regla propia/agrupada; S5 leído en abril del pico + 1.
   - Fechado trimestral (regla de dos trimestres), `estado_mensual` y `b1_vivo` (comparar con `int4.liston`).
   - Recalibración: solo usa p anual y p mensual (nunca el objetivo); validación cruzada sin fugas entre pliegues.
   - Orden de commits: diseño (`e9ec71d`, `a94ac09`) antes de código y de cada ejecución; procedencia con árbol limpio.
   - ¿T2 con 31 filas es suficiente para mostrar su probabilidad? ¿la lista de países de T2 incluye DNK/JPN sin bolsa?
   Sensibilidades útiles (declaradas a posteriori, no cambian el veredicto): bootstrap por años del r y la pendiente de la
   puerta de T2; puerta de T1 sin las filas de un país cada vez.
Informe en `docs/validation/2026-10-29_ml_termometro.md` con ✅ / ⚠️ / ❌ por punto y diffs propuestos.
