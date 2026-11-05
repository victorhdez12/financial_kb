---
documento: P-E1b — logit de CURVA frente a CURVA + ACTIVIDAD para la entrada en recesión a 6 MESES (registro en vivo)
version: 1.0 (congelado 2026-11-05, antes de escribir el ajuste; petición del usuario de un horizonte más corto que 12 m)
estado: CONGELADO. Copia de P-E1 v1.0 (docs/int/E1_prerregistro_v1.md, con su enmienda 1) salvo lo indicado aquí.
  Bloqueado ≥ 2005 NO se gasta ni se lee.
---

# P-E1b (6 meses): lo que cambia respecto a P-E1 v1.0
1. **Objetivo:** y(M) = 1 si hay una entrada en recesión (mismo fechado trimestral) en (M, M + 6] = E1-6 de INT-13
   (`src/intl/int13.objetivo_e1`, h = 6). Mismas filas en riesgo, mismos 16 países, mismas 4 variables, mismos modelos
   L (curva, Δ12 corto) y A (+ `ip_yoy`, `confianza_emp`), ajuste único agrupado ≤ 2004 (objetivo ≤ 2004-12),
   estandarizado, congelado con sha256 en `research/int/e1_6_modelos.json`. Si un signo de la actividad sale al revés,
   se publica y se para.
2. **Contaminación adicional declarada:** INT-8 calculó que a 3-6 meses NO hay potencia (pocos meses positivos) y
   INT-13 ya miró E1-6 con el paquete de actividad (exploratorio). Lo más probable es que este registro no llegue
   nunca a un veredicto en un horizonte útil; se hace porque es barato y el usuario lo pidió. El fechado va 2-3
   trimestres tarde: a 6 meses, buena parte de lo que "anticipa" la actividad es ver una recesión ya empezada.
3. **"Anticipación pura" (M4):** quitar las filas con entrada en (M, M + 3]; secundario obligatorio.
4. **Evaluación:** como P-E1 §5/§7/§8 con la muestra en vivo (orígenes ≥ 2026-11-30, enmienda 1 aplicada), cuando haya
   ≥ 12 episodios nuevos; antes, solo descriptivo. Contraste único: ΔAUC de A frente a L (placebo P1). Sin Holm con
   E1-12: son preguntas distintas y ninguna dará veredicto pronto; si algún día se evalúan a la vez, Holm-2.
5. **Registro:** la misma línea mensual de `research/int/e1_vivo.jsonl` lleva p_L6 y p_A6. No se muestra en el reporte.
