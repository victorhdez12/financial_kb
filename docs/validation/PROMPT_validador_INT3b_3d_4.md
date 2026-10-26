Eres el Validador independiente de financial_kb (no escribiste este código). Repo: rama main (último commit). Revisa, contra sus prerregistros congelados v1.0 (commit fa6d4c9), las tres corridas únicas del 26-oct:

1. INT-3b/3c: docs/int/INT3b_prerregistro_v0.md, research/int/int3b_resultado.md; código en el commit 63b2f3a más el arreglo 3281129.
2. INT-3d: docs/int/INT3d_prerregistro_v0.md, research/int/int3d_resultado.md, src/intl/int3d.py.
3. INT-4: docs/int/INT4_prerregistro_v0.md, research/int/int4_resultado.md, src/intl/int4.py, scripts/int4_corrida.py, y la sensibilidad del listón declarada a posteriori scripts/int4_sensibilidad_liston.py (salida research/int/int4_sensibilidad_liston.json).

Para cada una: ¿el código implementa el prerregistro? ¿Hay fuga de datos futuros o de datos ≥ 2005? ¿Hay desviaciones no declaradas?

En concreto:
(a) INT-4: el listón B1 da AUC 0,446 en T2 (y solo 0,546 en T1) al dejar un país fuera. La sensibilidad lo atribuye al sesgo del intercepto al dejar un grupo fuera (correlación −0,97 en T2) y lo corrige con AUC estratificada por país y con el listón dentro de muestra: ¿es correcto y suficiente? La p del placebo está en su mínimo (1/125): ¿basta? ¿Se aplicaron los criterios (iii)-(v), sobre todo el (iv), signo positivo en 1950-2004? ¿La bolsa del año t (S3, C6) es conocida en el origen (30 de abril de t+1)?
(b) INT-3b/3c: el oro con inflación alta sale con el signo contrario; revisa el arreglo declarado y el criterio de signo de B4 con solo dos países.
(c) INT-3d: "sin guerras" se aplicó como criterio; la sensibilidad abs3 de C5 no se calculó.

Escribe docs/validation/2026-10-26_int3b_int3d_int4.md, en español, con un veredicto ✅/⚠️/❌ por corrida y las correcciones propuestas (con diff si hace falta, declaradas a posteriori). Hazlo en una rama nueva claude/validacion-int3b-3d-4.
