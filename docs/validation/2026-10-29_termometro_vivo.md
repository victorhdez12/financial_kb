---
documento: validación de la parte EN VIVO del termómetro de recesión informativo
fecha: 2026-10-29
autor: Validador independiente (rama val-vivo, worktree financial_kb_int3b); no ha escrito este código
objeto: src/report/termometro_vivo.py, scripts/termometro_vivo.py, tests/test_termometro_vivo.py,
  research/int/termometro_vivo_ultimo.json (código en `aa72ed2`)
contexto: docs/int/TERMOMETRO_diseno_v1.md (§1-4, §8, §9), src/intl/termometro.py, scripts/termometro_puerta_v2.py,
  research/int/termometro_puerta_v2_corr.json (`final`), docs/validation/2026-10-29_termometro.md
método: lectura del código; reproducción con el warehouse real (fechas ≤ 2004, código de desarrollo sin redondeo frente
  al módulo en vivo con el JSON); pruebas sintéticas de "as of" estricto y de series que faltan o se cortan; bootstrap
  de la puerta de T2 con la S4 corregida (para el texto del aviso). Scripts del Validador fuera del repo (scratchpad):
  no se ha tocado el módulo.
---

# Validación del termómetro en vivo

## Veredicto global

(se completa al final)

## 1. Nada de JST, nada reajustado con datos ≥ 2005, parámetros solo del JSON congelado — ✅ (con un matiz ⚠️)

- **Lectura de datos.** El único acceso al warehouse es `_serie` (l. 104-113): rechaza todo `jst_*` y todo lo que no esté
  en `D.FAMILIAS` antes de consultar (`FactorCutoffError`). `cargar` solo pide `oecd_{irlt,ir3m,share}_*`,
  `oecd_cpi_*_idx`, `oecd_gdpq_*` y `bis_creditgap_*_ratio`. No se llama a `load_dev`, `P.anual`, `P.mensual` ni a nada
  que lea JST; `P._mensual_completa`, `Lg.asof` y las funciones de `T` no tocan la base. ✅
- **Parámetros.** `parametros()` lee solo `final` de `termometro_puerta_v2_corr.json` (modelo T2, `cal` T2, `rectas`,
  percentiles p50/p80/p95 de T2) y el veredicto. Falla explícitamente si falta algo, si T2 no consta aprobado o si T1 no
  consta como NO aprobado. En el módulo no hay ninguna llamada a `logit_fit`, `congelar`, `rectas`, `calibrar` ni
  `polyfit`. ✅
- **Redondeo del JSON.** Medido con el código de la puerta sin redondear (≤ 2004): coeficientes de T2 a ≤ 4e-5;
  (α, β) = (0,03097; 0,94830) frente a (0,031; 0,9483); pendientes de las rectas a ≤ 0,03 % salvo **C2: 0,93 %** de error
  relativo (lo que ya declara el docstring). Efecto máximo en la probabilidad de T2 mes a mes, 1960-2004: **5,3e-4**. ✅
- ⚠️ **Referencias ≤ 2004 que no están congeladas.** El percentil histórico de cada indicador y el "centro" de las
  contribuciones (media de [B1, S1-S5] en los meses en recesión 1960-2004) se recalculan en cada ejecución con
  `obs_latest`. No usan datos ≥ 2005 (la rejilla ≤ 2004 solo ve datos disponibles antes de 2005-01; comprobado que el
  bloque mensual con corte 2004-12 es idéntico al de desarrollo), pero **no están congelados**: si una recarga del
  warehouse revisa la historia OCDE/BIS, cambian sin aviso. No es un reajuste del modelo (no cambian ni la probabilidad
  ni la banda), pero rompe la promesa "todo lo ≤ 2004 queda fijo". Propuesta (diff 5): congelarlos una vez en un JSON
  con procedencia, o fijar en un test su huella (centro medido hoy: B1 0,1531; S1 0,3638; S2 −0,0049; S3 0,1470;
  S4 0,2905; S5 0,1234).

## 2. "As of" en vivo igual que en desarrollo, sin mirar el futuro — ✅ (con dos avisos ⚠️)

- **Mismas reglas.** Mensuales: `P._mensual_completa` + `Lg.asof` (fin de mes + 1 día tipos y bolsa, + 45 días IPC,
  más viejo que 120 días = ausente) — las mismas funciones que `panel.mensual`. Trimestrales: `T.asof_q` (BIS + 183 días,
  PIB + 75, máximo 200 días) y `T.estado_mensual` (fechado conocido 75 días tras el trimestre). La única diferencia con
  desarrollo es que `_serie` corta en la fecha de cálculo en lugar de 2004-12. El test con corte 2004-12 lo confirma
  (bloque mensual y PIB idénticos a `load_dev`/`load_dev_curado`). ✅
- **Prueba estricta del Validador (sintética):** con fecha 2026-03-31 se multiplican por 3 los datos con fecha ≤ corte
  que todavía no se conocen ese día (tipos y bolsa de marzo, IPC de febrero y marzo, PIB 2026T1 × 0,5, BIS 2025T4 × 3) →
  **resultado idéntico byte a byte**. Y al revés, cambiar el tipo a 10 años de febrero (ya conocido) sí cambia C1
  (3,17 → 3,59). ✅
- **Hoy (2026-10-29 → fecha de cálculo 2026-09-30):** tipos y bolsa de agosto, IPC de julio, BIS 2026T1
  (31-mar + 183 = 30-sep, justo), PIB 2026T2 (30-jun + 75 = 13-sep). Comprobado en el warehouse. ✅
- ⚠️ **Hasta un mes de retraso evitable.** La fecha de cálculo es el último fin de mes ≤ la fecha pedida: el 29-oct se
  ignoran los tipos y la bolsa de septiembre y el IPC de agosto, ya publicados. No es mirar el futuro (es lo prudente y
  coincide con la rejilla de desarrollo), pero el reporte semanal irá hasta 4 semanas por detrás. El título del Markdown
  dice la fecha de cálculo; conviene decirlo en palabras ("datos conocidos al 30-sep-2026").
- ⚠️ **Arrastre de datos viejos dentro de las medias de 12 meses** (heredado de desarrollo, no nuevo): un tipo que deja de
  publicarse se repite hasta 120 días en la curva "as of", y C1 (media de 12 meses con ≥ 9) puede salir calculada con
  3-4 meses repetidos. Con la GBR real: el tipo a 3 meses acaba en 2026-02; en julio-agosto la C1 de GBR aún salía,
  con marzo-mayo iguales a febrero; en septiembre ya sale vacía. Es la regla de desarrollo; solo falta decirlo (§6).
