---
documento: INT-8 — probabilidad mensual de ENTRAR en recesión a h = 3 y 6 meses (OCDE, 18 países): potencia y borrador de diseño
version: 0.1-borrador (2026-10-29)
estado: BORRADOR para el usuario. Solo potencia: ningún indicador cruzado con ningún resultado. Nada construido.
potencia: scripts/int8_potencia.py (commit aed6ae2, árbol limpio, 2026-10-29T18:44Z) → research/int/int8_potencia.json
---

# INT-8: ¿probabilidad de entrar en recesión a 3-6 meses? (borrador v0.1)

## 0. Qué se pregunta
El usuario: *"anticipar a un año vista es mucho; ¿por qué no a algunos meses vista y dar la probabilidad de entrar en
recesión?"*. Pregunta concreta: con datos mensuales "as of" de la OCDE (18 países, desarrollo ≤ 2004), ¿un modelo sencillo
ordena mejor que un listón sencillo (B1: meses desde la última salida / tasa base) los meses en que un país **entra en
recesión en los próximos 3 o 6 meses**? Y, si sí, ¿se puede mostrar esa probabilidad en vivo con una calibración creíble?

**Idea clave (antes de los números):** acortar el horizonte **no añade recesiones**. Hay las mismas entradas (≈ 16-22
episodios independientes en 1960-2004) a 3, 6 o 12 meses; solo cambia cuántos meses "positivos" rodean a cada una. La
potencia depende de los episodios, no de los meses. Y a 3 meses el modelo se acerca a un **nowcast** (lo que ya está
pasando), que es justo donde los datos coincidentes ganan y la anticipación vale poco.

## 1. El problema central: ¿qué es "entrar en recesión" cada mes?

| objetivo | qué es | países, años | entradas 1960-2004 núcleo (18) | episodios agrupados* | años distintos | estado |
|---|---|---|---|---|---|---|
| **O1 PIB-a** | fechado trimestral del termómetro: la suma de 4 trimestres cae 2 trimestres seguidos (`termometro.fechado_trimestral`) | 18, 1960-2004 (GBR 1955, USA 1947) | **50** (62) | **16** (17) | 19 | contrastado con JST: 40/45 entradas ± 1 año. **Retrasado**: entra 2-3 trimestres después del pico |
| **O2 PIB-t** | "recesión técnica": 2 caídas trimestrales seguidas del PIB (entra en la 1.ª) | ídem | **80** (109) | **22** (23) | 31 | definición popular, más cercana al pico; **no validada**; PIB trimestral de los años 60 interpolado en varios países (riesgo de eventos falsos) |
| O3 BB-IP | Bry-Boschan sobre IP + paro (INT-1 v2) | 16, desde 1956-76 | 120 (134) | 28 | 36 | **falló su puerta 2 veces** (EE. UU. 4-6/8 NBER): no es un objetivo válido |
| O4 NBER | USREC | solo EE. UU. | 7 | 7 | 7 | válido, pero sin potencia (§2) |
| CLI / ECRI / OCDE | puntos de giro | — | — | — | — | **no están en el warehouse** (solo los índices CLI de 22 zonas, que son de dos lados y revisados: no son tiempo real ni un fechado de recesión; el ciclo OCDE es de crecimiento, no clásico) |

\* Episodio = entradas de cualquier país a ≤ 6 meses de la anterior (1974-75 reúne 11 entradas; 1980-83, 13; 1990-93, 11).

**Con la curva disponible** (el tipo a 3 meses empieza en 1980-90 en casi todos los países): O1 28 entradas / **11
episodios**; O2 38 / **15**. JPN (curva desde 2002), ITA (1991), PRT (1993) y CHE (1999) casi no aportan entradas con curva.

Lectura: los eventos se agrupan mucho por fecha (ICC por mes 0,08-0,20; efecto diseño de Kish 2-3,5). En efectivo hay
**≈ 11-22 episodios**, frente a 72-84 años distintos de la versión anual con JST (INT-4).

## 2. Potencia (solo recuentos y propiedades de cada serie por separado)
Método: estructura **real** de eventos (país × mes en riesgo) y puntuaciones **simuladas** (binormales); el ruido tiene la
persistencia y la correlación entre países **medidas en los indicadores, cada uno por separado** (AR(1) mediana 0,95:
curva 0,95, bolsa 0,95, paro 0,96, IP 0,73; correlación media entre países 0,50); modelo y listón correlacionados 0,5.
ΔAUC con varianza por **bloques de tiempo de 24 meses** (todos los países juntos) y valor crítico ajustado con la nula
simulada (tamaño nominal 3-7 %; el bootstrap por bloques "de verdad" sale algo optimista: 10 % bajo H0 y 0,94 frente a
0,93 de potencia con Δ 0,20). Holm sobre 2 contrastes (h = 3 y 6).

**MDE de ΔAUC (80 %, Holm-2), núcleo 14 países, listón A0 = 0,55-0,60:**

| objetivo | muestra | h = 3 | h = 6 | optimista (φ 0,5, ρ 0) | Hanley-McNeil con episodios |
|---|---|---|---|---|---|
| O1 PIB-a | todo 1960-2004 (indicadores sin curva: IP, bolsa, paro) | **0,21** | **0,18-0,20** | 0,09-0,10 | 0,22 |
| O1 PIB-a | con curva | **0,22-0,24** | **0,22-0,24** | 0,12-0,14 | 0,26 |
| O2 PIB-t | todo | **0,16-0,17** | **0,14-0,17** | 0,08-0,09 | 0,19 |
| O2 PIB-t | con curva | **0,19-0,22** | **0,20** | 0,10-0,13 | 0,23 |
| O4 NBER (EE. UU.) | 1960-2004 | 0,31 (HM) | 0,32 (HM) | — | — |

**Ganancia esperable (literatura, orden de magnitud, de memoria y en su mayoría dentro de muestra):** curva para el NBER a
6-12 meses AUC ≈ 0,80-0,90 (Estrella-Mishkin 1998; Liu-Moench 2016); a 3 meses la curva pierde y ganan bolsa, diferenciales
y datos coincidentes (Berge-Jordà 2011: AUC ≈ 0,8-0,9 con indicadores adelantados); para otros países, fuera de muestra,
AUC ≈ 0,70-0,80 con curva, CLI y difusión. Frente a un listón de 0,55-0,60, eso es **ΔAUC ≈ +0,10-0,20 fuera de muestra**
(+0,20-0,30 dentro). INT-4 anual dio +0,18 en desarrollo. Es decir: **la MDE (0,17-0,24) está en el borde superior de lo
plausible**; solo se detectaría un efecto tan grande como el mejor resultado publicado, y la muestra con curva (la que
interesa) es la peor.

**Calibración ("la probabilidad en vivo"):** con los episodios efectivos de O1 a 6 meses (≈ 19 con todo, ≈ 11 con curva),
un modelo **bien calibrado** daría una pendiente de calibración con IC 95 % ≈ [0,5; 1,6] (19) o [0,4; 1,9] (11), y el
cociente eventos observados / predichos ≈ [0,6; 1,5] o [0,45; 1,65]. Hacen falta ≈ 40 episodios para un IC ≈ [0,65; 1,4].
**En vivo** llegan ≈ 3,6 episodios por década: **≈ 28 años para 10 episodios** y 56 para 20. Un porcentaje mensual
"exacto" no se podrá comprobar en décadas.

## 3. Veredicto
- **O1 (el fechado validado): no viable** como prueba. MDE 0,18-0,24 frente a una ganancia esperable de 0,10-0,20, y además
  el objetivo va 2-3 trimestres por detrás del pico: a 3-6 meses el "acierto" sería sobre todo ver una recesión que ya ha
  empezado (nowcast), no anticiparla.
- **O2 (recesión técnica): justo.** MDE 0,14-0,17 sin curva, 0,19-0,22 con curva; mismo orden que la ganancia esperable,
  pero es un objetivo **no validado** (y el PIB trimestral de los 60 es en parte interpolado). Habría que validarlo primero
  (solo objetivo frente a JST, NBER, CEPR; sin indicadores) y, aun así, potencia ≈ 50 % para un efecto realista.
- **Calibración en vivo: no viable** (IC de la pendiente ≈ [0,4-0,5; 1,6-1,9]; décadas para comprobarla).
- **Comparación con el anual:** el horizonte de un año no se eligió por gusto: con JST hay ≈ 72-84 años distintos con
  entrada; con la OCDE mensual, 11-22 episodios. Acortar el horizonte cambia la resolución, no la información.

**Resumen honesto: a 3-6 meses no hay potencia para demostrar nada que no sea un efecto muy grande, y el objetivo mensual
sigue sin estar validado. No recomiendo construir INT-8 como prueba.**

## 4. Contaminación (declarada)
- Hemos visto el termómetro (T1 anual de INT-4: AUC 0,73 frente a 0,55; T1 mensual traducido: r 0,788 con el anual; el
  fechado trimestral: 40/45) y sabemos que la curva, la difusión y la bolsa funcionan a un año. Cualquier INT-8 con esos
  indicadores sería **réplica**, no descubrimiento.
- La literatura (curva, CLI, diferenciales; Sahm, EBP y NFCI después de 2005) es conocida; un modelo mensual se elegiría
  sabiendo qué funcionó en 1974-75, 1980-82, 1990-93 y 2001-03, que son casi todos los episodios disponibles.
- Este estudio no cruzó ningún indicador con ningún objetivo (solo recuentos, AR(1) y correlaciones de cada serie).

## 5. Alternativa más útil (recomendada)
1. **Mantener lo que ya hay y está validado:** en el reporte, la probabilidad **anual** de INT-4 donde pasó su puerta (T2,
   salida) y, para entrar, los **indicadores mensuales** (curva, difusión de curvas invertidas, bolsa real 12 m, crédito) con
   su percentil histórico, como "semáforo" descriptivo, con la frase "Informativo, no es una señal de cartera".
2. **Añadir sin modelo, como descriptivo**, dos indicadores coincidentes que responden a "¿está empezando ya?": difusión de
   la producción industrial (% de países con IP interanual < 0) y el fechado trimestral en vivo (ya calculado). No se
   ponen como probabilidad.
3. Si se muestra algún número de T1 anual, siempre con su IC (AUC 0,73, IC por bloques) y como "riesgo relativo"
   (percentil), nunca como porcentaje a 3 meses.

## 6. Decisiones del usuario
1. **No construir INT-8 como prueba** y quedarse con la alternativa del §5 (**recomendado**), o
2. INT-8 **solo exploratorio** con O2 a h = 6, previa validación del objetivo (paso 0: O2 frente a JST/NBER/CEPR, puerta
   ≥ 80 % ± 2 trimestres, sin indicadores), con la MDE (≈ 0,17-0,20) escrita delante y sin ninguna probabilidad en el
   reporte aunque salga bien (la calibración no es comprobable), o
3. aparcar la pregunta hasta tener datos nuevos (cada década añade ≈ 3-4 episodios).
