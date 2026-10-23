---
documento: resultados de desarrollo (≤ 2004) de M1 v2 (H-M1-002) — UNA sola pasada, publicada tal cual
fecha: 2026-10-23
especificacion: docs/models/m1_v2_spec.md (commit 4d2b1ac, empujado antes de cualquier corrida con la etiqueta; placebo e5a5fd3)
codigo_corridas: commit e5a5fd3 (árbol limpio en src/config/tests, --official); base PIT v0.4 CANDIDATA; arnés v2.2
corridas: 20261023-111824_m1v2_principal_512ecfcc (principal), 20261023-112028_m1v2_long_d6d807d6 (larga, eje G),
  20261023-112119_m1v2_sens_cb4a66b7 (sensibilidades de s)
derivados: research/trials/m1_v2/{placebo_m1_v2.json, compare_*.json, coef_*.json}
datos: solo ≤ 2004-12. Nada ≥ 2005 de la etiqueta leído ni puntuado
---

# M1 v2 frente a M0 y frente a M1 v1: desarrollo ≤ 2004

**Resumen.** **M1 v2 no bate a M0 en desarrollo.** Es la única pasada, sin iteración; se publica tal cual.
- **Principal** (1989-10 → 2004-12, vintage): M1 v2 − M0 = **−0,017 nats [−0,131; +0,078]**. Casi igual que M1 v1
  (−0,019): v2 − v1 = **+0,001 [−0,053; +0,056]**.
- Lo que cambia frente a M1 v1 es **dónde** pierde: mucho menos en los **giros** (−0,035 frente a −0,160; v2 − v1
  **+0,125 [−0,043; +0,298]**) y algo más en los **estables** (−0,012 frente a +0,023). El eje I estructural ya no
  empeora a M0 como el subyacente libre (−0,004 frente a −0,032), pero el eje G empeora (−0,012 frente a +0,013).
- **Falsas alarmas de G: 0,75 al año** (M0 0,19; M1 v1 0,56) → incumple el listón ≤ 0,5. Confirma los giros antes que
  M0 (2,8 frente a 4,4 meses; pareado −1,6) y detecta los 5.
- **Eje G aislado, ventana larga** (1978-07 → 2004-12): `m1v2_g` − M0 = **+0,035 [−0,035; +0,099]**, giros **+0,003**,
  estables +0,046, falsas alarmas 0,56/año, retraso 2,1 frente a 4,4 (pareado −2,3). Frente al eje G de M1 v1:
  +0,002 [−0,046; +0,047] (giros +0,027).
- **Signos:** `baa_gap10y` sale **positivo** (preregistrado −) en el **100 %** de los cortes; `sahm_d3m` ≈ 0 con signo
  positivo en la principal (preregistrado −; 21 % de cortes con el signo esperado). El resto, con el signo preregistrado
  en el 100 % de los cortes.
- **Placebo limpio** (antes de la etiqueta real) y ninguna mejora cerca de la alarma de fuga (0,25 nats).
- **Criterio de referencia** (el aceptado para P-EVAL-BASE: total ≥ 0,05 con IC > 0, giros ≥ 0, falsas alarmas ≤
  0,5/año): **no lo cumpliría** en la principal (ninguno de los tres) ni con el eje G aislado (solo giros ≥ 0). Esto no
  decide nada (H-M1-002 está contaminada por este periodo), pero es la información de desarrollo que hay.

## 1. Placebo (antes de la etiqueta real; `placebo_m1_v2.json`, commit e5a5fd3)

Δ = ll(M0) − ll(M1 v2), etiqueta ≤ 2004 barajada en bloques de 24, 20 semillas, L2 de M1 v2, base v0.4.

| caso | media Δ | Δ_G | Δ_I | semillas > 0 | t | ¿fuga (> 0,02)? | ¿aviso? |
|---|---|---|---|---|---|---|---|
| **M1 v2** (1990-01 → 2004) | −0,876 | −0,012 | −0,865 | 0/20 | −11,8 | no | no |
| **`m1v2_g`** (1979-01 → 2004) | −0,025 | −0,025 | −0,000 | 3/20 | −4,4 | no | no |
| potencia (`m1v2_g`): ruido | −0,005 | | | 1/20 | −6,5 | no | no |
| control t−5 (sin fuga) | −0,027 | | | 1/20 | −9,5 | no | no |
| t+1, σ = 1 | +0,043 | | | 20/20 | 12,7 | **sí** | **sí** |
| t+1, σ = 2 | +0,007 | | | 15/20 | 3,6 | no | **sí** |
| t, σ = 2 | +0,009 | | | 17/20 | 4,4 | no | **sí** |
| calendario t−4 | +0,015 | | | 16/20 | 4,2 | no | **sí** |

- El −0,865 del eje I es el esperado (especificación §5): con la etiqueta barajada, el offset estructural fijo
  (informativo con la etiqueta real) solo puede perjudicar. El eje G (−0,012) se comporta como en M1 v1.
- La regla complementaria (signo/t) detecta las fugas débiles y la de calendario de un mes; ni ruido ni control t−5
  dan aviso. Igual que con M1 v1.

## 2. Corrida principal: 1989-10 → 2004-12 (183 meses)

| modo | modelo | acierto | log-loss 4 c. | G | I |
|---|---|---|---|---|---|
| vintage | M0 | 67,2 % | **0,948** | 0,586 | 0,362 |
| vintage | M1 v1 (`m1_logit_axis`) | 65,6 % | 0,966 | **0,572** | 0,394 |
| vintage | **M1 v2** (`m1v2_logit_axis`) | **69,4 %** | 0,965 | 0,598 | 0,367 |
| vintage | persistencia cruda | 62,8 % | 1,250 | 0,740 | 0,500 |
| latest_truncated | M0 | | 0,930 | 0,563 | 0,367 |
| latest_truncated | M1 v1 | | 0,943 | 0,566 | 0,376 |
| latest_truncated | M1 v2 | | 0,927 | 0,573 | 0,353 |

M0, la persistencia y M1 v1 reproducen las cifras de la principal de M1 v1 (`m1_results_dev.md` §2): la matriz v0.4
contiene las columnas de la v0.3 bit a bit.

**Diferencias** (positivo = mejor que el comparador; IC 95 % por bloques de 12 meses):

| | M1 v2 − M0, vintage | M1 v2 − M0, latest_tr. | M1 v1 − M0, vintage | **M1 v2 − M1 v1**, vintage |
|---|---|---|---|---|
| total | **−0,017** [−0,131; +0,078] | +0,003 [−0,107; +0,095] | −0,019 [−0,128; +0,076] | **+0,001** [−0,053; +0,056] |
| eje G | −0,012 [−0,108; +0,067] | −0,010 | +0,013 | −0,026 [−0,085; +0,028] |
| eje I | −0,004 [−0,057; +0,039] | +0,013 | −0,032 | +0,027 [−0,021; +0,084] |
| **giro** | **−0,035** [−0,348; +0,206] | −0,057 | −0,160 | **+0,125** [−0,043; +0,298] |
| **estable** | −0,012 [−0,119; +0,079] | +0,021 | +0,023 | −0,035 [−0,092; +0,019] |
| 1989-10→1996 / 1997→2004 | −0,079 / +0,039 (signo distinto) | −0,046 / +0,047 | −0,120 / +0,074 | |
| frontera / no frontera | −0,266 / +0,007 | | −0,282 / +0,007 | |
| episodios ganados: NBER ± 6 / rachas / giros G | 2 de 2 / 5 de 8 / 4 de 5 | | 2 de 2 / 4 de 8 / 3 de 5 | |
| Holm frente a M0 (p ajustada) | 1,0 | 1,0 | 1,0 | |

**Detección de giros de G** (definición v2.1; 5 giros en la ventana):

| vintage | M0 | M1 v1 | M1 v2 |
|---|---|---|---|
| detectados / censurados | 5 / 0 | 5 / 0 | 5 / 0 |
| retraso medio hasta confirmar | 4,4 m | 2,4 m | **2,8 m** |
| retraso pareado frente a M0 | — | −2,0 | **−1,6** |
| **falsas alarmas al año** | **0,19** | 0,56 | **0,75** |

En latest_truncated: M1 v2 retraso 2,6 m (M0 3,2), falsas alarmas 0,47/año (M0 0,47). M1 v2 frente a M1 v1 (vintage):
retraso pareado +0,4 m, falsas alarmas +0,19/año.

## 3. Ventana larga: eje G de M1 v2 aislado, 1978-07 → 2004-12 (318 meses)

`m1v2_g` = eje G de M1 v2 + eje I de M0 (idéntico a M0 en I). `m1_logit_axis_hl` = eje G de M1 v1 + IPC general.

| modo | modelo | acierto | log-loss 4 c. | G | I |
|---|---|---|---|---|---|
| vintage | M0 | 69,2 % | 0,829 | 0,594 | 0,235 |
| vintage | M1 v1 (G) + IPC general | 70,8 % | 0,795 | 0,563 | 0,232 |
| vintage | **`m1v2_g`** | **75,5 %** | **0,793** | **0,558** | 0,235 |

| | `m1v2_g` − M0, vintage | latest_tr. | M1 v1 (hl) − M0, vintage | **`m1v2_g` − M1 v1 (hl)**, vintage |
|---|---|---|---|---|
| total | **+0,035** [−0,035; +0,099] | +0,028 [−0,035; +0,083] | +0,033 [−0,031; +0,095] | +0,002 [−0,046; +0,047] |
| eje G | +0,035 | +0,028 | +0,031 | +0,005 [−0,040; +0,047] |
| **giro** | **+0,003** | +0,012 | −0,025 | +0,027 [−0,062; +0,115] |
| estable | +0,046 | +0,034 | +0,053 | −0,007 |
| 1978-07→1989 / 1990→2004 | +0,099 / −0,013 (signo distinto) | +0,077 / −0,010 | +0,057 / +0,015 | |
| frontera / no frontera | −0,097 / +0,045 | | −0,046 / +0,039 | |
| episodios: NBER ± 6 / rachas / giros G | 3 de 4 / 11 de 15 / 6 de 10 | | 3 de 4 / 10 de 15 / 7 de 10 | |
| Holm frente a M0 | 0,62 | 0,74 | 0,62 | |

| detección (vintage, 10 giros) | M0 | M1 v1 (hl) | `m1v2_g` |
|---|---|---|---|
| detectados / censurados | 9 / 1 | 9 / 1 | 9 / 1 |
| retraso medio | 4,4 m | 2,8 m | **2,1 m** |
| retraso pareado frente a M0 | — | −1,7 | **−2,3** |
| falsas alarmas al año | **0,22** | 0,62 | 0,56 |

**Lectura:** el eje G de M1 v2 confirma los giros antes que M0 y que M1 v1 y deja de perder en los meses de giro
(+0,003 frente a −0,025), pero su mejora total es la misma que la de M1 v1 (+0,035 frente a +0,033), se concentra en
1978-89 y en 1990-2004 es ligeramente negativa (−0,013). Las falsas alarmas siguen por encima de 0,5 al año.

## 4. Sensibilidades preregistradas de la escala del eje I (vintage, principal; no eligen)

| s (pp) | M1 v2 − M0 total | G | I | giro / estable |
|---|---|---|---|---|
| 0,5 | −0,063 [−0,196; +0,051] | −0,012 | −0,049 | −0,134 / −0,041 |
| **0,75 (a priori)** | **−0,017** | −0,012 | −0,004 | −0,035 / −0,012 |
| 1,0 | −0,007 [−0,116; +0,084] | −0,012 | +0,006 | −0,020 / −0,003 |

Una escala más ancha (offset más suave) acerca el eje I a M0; ninguna lo mejora de forma apreciable. No se cambia s.

## 5. Coeficientes (estandarizados; `coef_m1v2_*.json`)

| coeficiente | signo preregistrado | principal, vintage (192 cortes): media [mín; máx] | % cortes con el signo | larga `m1v2_g` (318 cortes) |
|---|---|---|---|---|
| G: logit persistencia | + | +0,08 [+0,01; +0,13] | 100 % | +0,07, 100 % |
| G: `growth_rt` | + | +0,48 [+0,40; +0,60] | 100 % | +0,43, 100 % |
| G: `claims_4w_yoy` | − | −0,38 [−0,46; −0,30] | 100 % | −0,34, 100 % |
| G: `curve_min12` | + | +0,59 [+0,43; +0,74] | 100 % | +0,62, 100 % |
| G: **`baa_gap10y`** | **−** | **+0,29 [+0,10; +0,38]** | **0 %** | +0,23, **0 %** |
| G: `baa_d6m` | − | −0,32 [−0,37; −0,24] | 100 % | −0,28, 100 % |
| G: `eq_ret_6m` | + | +0,21 [+0,13; +0,35] | 100 % | +0,24, 100 % |
| G: **`sahm_d3m`** | **−** | **+0,06 [−0,06; +0,17]** | **21 %** | +0,01, 52 % |
| I: logit persistencia | + | +0,40 [+0,05; +0,58] | 100 % | (M0) |
| I: `core_cpi_6m_ann` | + (fijo) | +2,27 por pp (1,7/0,75; no estimado) | — | — |

- **Estabilidad en los saltos de vintage:** `growth_rt` en 1981-05 mantiene el signo (+0,36 → +0,44); no hay otros
  saltos con ≥ 12 cortes a cada lado dentro de las corridas.
- **`baa_gap10y` al revés:** condicionado a `baa_d6m` (el empeoramiento) y a `curve_min12`, el nivel del diferencial
  frente a su mediana entra con signo positivo. Lectura posible (no comprobada, y **no se corrige**: sería iterar): tras
  las recesiones el diferencial sigue alto frente a su mediana mientras G ya se recupera, el mismo patrón de rebote que
  tenía la Sahm en nivel en M1 v1.
- **`sahm_d3m` sin señal:** coeficiente ≈ 0 una vez dentro `claims_4w_yoy` y `growth_rt`.
- Con el criterio 6 del borrador P-EVAL-BASE v3 (signos), M1 v2 **fallaría** por `baa_gap10y` (y `sahm_d3m`).
- Correlación de residuos G-I: 0,135 (vintage, principal), por debajo del umbral de 0,2.

## 6. Diagnóstico

1. **Fuga:** sin indicios. Placebo limpio; mejoras pequeñas (≤ 0,035); M0, persistencia y M1 v1 reproducen las cifras
   de la principal de M1 v1 con la matriz v0.4.
2. **Los tres cambios hacen lo que su mecanismo decía, pero no bastan:**
   - **eje I estructural:** deja de empeorar a M0 (−0,004 frente a −0,032) y está identificado sin cruces; no lo mejora;
   - **variables de riesgo de giro:** reducen la pérdida en los giros (principal −0,035 frente a −0,160; eje G aislado
     +0,003 frente a −0,025) y adelantan la confirmación (−1,6 / −2,3 meses frente a M0), pero **a costa de falsas
     alarmas** (0,75 y 0,56 al año) y de los meses estables;
   - **sin Sahm en nivel:** su sustituto `sahm_d3m` no aporta.
3. **M1 v2 ≈ M1 v1 en total** (+0,001 [−0,053; +0,056]): la mejora en giros se compensa con la pérdida en estables.
4. **Inestabilidad temporal:** la mejora del eje G se concentra antes de 1990 y en 1990-2004 es ≈ 0 o negativa, en las
   dos versiones.
5. **No se itera.** Cualquier versión siguiente (p. ej. sin `baa_gap10y`) sería una v3 construida mirando esta tabla:
   no se hace. El siguiente aspirante con mecanismo distinto es el Markov con transiciones variables (Estratega §5).

## 7. Decisiones para el usuario (no tomadas aquí)

1. **¿Llevar M1 v1 + M1 v2 a la evaluación única (P-EVAL-BASE v3, Holm k = 2)?** En desarrollo ninguna cumple el
   criterio (total, giros y falsas alarmas; además los signos de Sahm en v1 y `baa_gap10y` en v2). Gastar el bloqueado
   ahora daría casi con certeza un "no" informativo y caro. Alternativa: esperar al Markov con transiciones variables
   (y, si llega, el GBM) y evaluarlos juntos.
2. **Congelar la base PIT v0.4** tras el ✅ del Validador (la necesitan M1 v2 y el Markov).
3. Revisión del Validador (v0.4, A3-1, M1 v2) y del Estratega (M1 v2).
