---
documento: Termómetro de recesión INFORMATIVO (probabilidad mensual de entrar y de salir de recesión por país) — diseño corregido
version: 1.1 APROBADO (2026-10-26; las 4 decisiones + ajustes a/b del usuario fijados aquí antes de escribir código)
estado: APROBADO. Nada construido. Sustituye a la parte "cartera" de docs/int/INT5_diseno_v0.md (INT-5 aparcado).
depende_de: INT-4 (P-DEV-INT4 v1.0; T1 y T2 establecidos; Validador ⚠️), sensibilidad del listón (int4_sensibilidad_liston*.json)
---

# Termómetro de recesión informativo (diseño v1.0)

**Es una herramienta informativa, no una señal de cartera.** No cambia B0/B1 ni el paper trading. En el reporte semanal irá
siempre con la frase: *"Informativo, no es una señal de cartera."*

## 1. Modelo
- **Congelado:** coeficientes de los logit de INT-4 ajustados en el núcleo (14 países) 1871-2004 sin guerras:
  T1 = B1 (primer año tras valle; log años desde el valle) + C1 curva, C2 Δ5 crédito/PIB, C4 difusión de curvas invertidas,
  C5 Δ tipo real corto, C6 bolsa real; T2 = B1 (log duración) + S1-S5. No se reajusta nunca con datos ≥ 2005.
- Horizonte: el modelo es anual (datos del año t, origen 30 de abril de t + 1, objetivo en t + 1). En vivo se lee como
  **"probabilidad de entrar (o salir) en los próximos ≈ 12 meses"**, declarado como aproximación.

## 2. Traducción mensual (fijada aquí, antes de calcular nada)
Cada mes m, con los datos publicados hasta m (retrasos de `src/intl/lags.py`):

| indicador | anual (JST, en el ajuste) | mensual en vivo | fuente en el warehouse | retraso |
|---|---|---|---|---|
| C1 / S1 curva | ltrate − stir, media anual | media de 12 meses de (10 años − 3 meses) | `oecd_irlt_*`, `oecd_ir3m_*` | 1 mes |
| C4 difusión | % de los otros 13 con C1 < 0 | ídem con la C1 mensual de cada país (≥ 5 con dato) | ídem | 1 mes |
| C5 / S2 Δ tipo real corto | Δ1 (stir − inflación) | (media 12 m de ir3m − IPC interanual) menos lo mismo 12 meses antes | `oecd_ir3m_*`, `oecd_cpi_*_idx` | IPC 45 días |
| C6 / S3 bolsa real | rentabilidad real total del año | rentabilidad real de **precio** a 12 meses (índice OCDE) | `oecd_share_*`, IPC | 1 mes |
| C2 / S5 Δ5 crédito/PIB | JST préstamos bancarios / PIB | Δ 20 trimestres del crédito total / PIB del **BIS** | `bis_creditgap_*_ratio` | **6 meses** tras el fin del trimestre (el BIS publica el trimestre q ≈ 5-6 meses después; declarado) |
| B1 (valle, duración) | fechado anual JST | fechado **en vivo** (§3) | PIB trimestral | 75 días |

- **Escala (fijada ≤ 2004):** las series mensuales no miden lo mismo que las anuales (precio frente a rentabilidad total,
  crédito total del BIS frente a préstamos bancarios de JST, medias móviles). Para cada indicador y país se ajusta una
  recta **x_anual ≈ a + b · x_mensual(abril de t + 1)** con los años ≤ 2004 que tienen ambas (desde ≈ 1960); la recta se
  congela y se aplica en vivo. Solo usa los indicadores, nunca el objetivo.
- **Puerta de la traducción (antes de mostrar nada):** con datos ≤ 2004, la correlación entre la probabilidad anual de
  INT-4 y la mensual traducida (tomada en abril de t + 1) debe ser **≥ 0,8** en el agregado de los países con ambas, y la
  pendiente de una recta entre las dos debe estar en **[0,8; 1,25]**. Se publica por país.
  - Si un país no pasa: no se muestra su probabilidad, solo sus indicadores.
  - Si el agregado no pasa: no hay termómetro; el reporte muestra solo los indicadores (curva, difusión, bolsa, crédito).

## 3. "En recesión" en vivo (definido a priori)
- Con el **PIB real trimestral** de la OCDE (fuente nueva: `oecd_gdpq_*`, Quarterly National Accounts, volumen; se añade a
  `INGEST` y a la auditoría de datos antes de construir nada). JST usa PIB **per cápita anual**; aquí se usa PIB total
  (población trimestral no fiable en vivo; declarado).
- **Suma móvil de 4 trimestres (S).** Equivale al dato anual de JST, pero se actualiza cada trimestre.
  - **Entra** en recesión el trimestre en que S cae frente a la S del trimestre anterior **por segunda vez seguida**
    (evita entrar por una revisión pequeña).
  - **Sale** el trimestre en que S vuelve a crecer frente al trimestre anterior **dos veces seguidas**.
- Fechas "as of": el trimestre q se conoce 75 días después de su cierre; se usa la primera publicación disponible en el
  warehouse (vintages donde existan; si no, la última, declarado).
- B1 en vivo: "años desde la última salida" y "duración de la recesión en curso" con este fechado.
- **Comprobación (≤ 2004, sin mirar rentabilidades):** concordancia de este fechado con el anual de JST (años de pico y valle
  a ± 1 año) en los países con PIB trimestral; se publica, no es puerta (el modelo usa su B1 propio).

## 4. Qué se muestra
- **Por país** (14 del núcleo; los 4 de prueba aparte) y **EE. UU. en su propia línea**:
  - fuera de recesión: **riesgo de entrar** en los próximos ≈ 12 meses;
  - en recesión: **probabilidad de salir** en los próximos ≈ 12 meses.
- **Como riesgo relativo, no como porcentaje exacto:** el percentil de la probabilidad frente a la distribución mensual
  traducida ≤ 2004 (todos los países del núcleo juntos), en bandas fijadas aquí: **bajo** (< p50), **medio** (p50-p80),
  **alto** (p80-p95), **muy alto** (≥ p95). La probabilidad se enseña entre paréntesis, con el aviso de que su nivel no
  está calibrado en vivo.
- Qué indicador empuja más (contribución al logit), para entender el porqué.
- Aviso fijo: *"Informativo, no es una señal de cartera. Modelo histórico 1871-2004; en desarrollo acierta el orden de los
  años de más riesgo con AUC ≈ 0,73 (entrada) y ≈ 0,77 (salida); la inflación no se anticipa."*

## 5. Gobierno
- Este diseño, aprobado por el usuario y commiteado antes de escribir el código. Puerta de la traducción con procedencia
  (commit, árbol limpio). Nada de JST ≥ 2005. Validador del código antes de ponerlo en el reporte semanal.
- Nunca se evalúa su acierto en vivo como prueba (no hay potencia); se registra cada mes para verlo con el tiempo.

## 6. Decisiones del usuario
1. PIB trimestral de la OCDE como fuente nueva para "en recesión" (recomendado) o solo el fechado anual (llega con más de un
   año de retraso).
2. Regla de dos trimestres seguidos para entrar y salir (recomendado) o uno solo.
3. Bandas p50 / p80 / p95 (recomendado).
4. Puerta: correlación ≥ 0,8 y pendiente en [0,8; 1,25] (recomendado).

## 7. Ajustes del usuario (fijados antes de calcular nada)
a) **Puerta fuera de muestra.** Elegido: **rectas de escala ajustadas con los años PARES ≤ 2004 y puerta medida con los
   IMPARES** (equilibra épocas; con ≤ 1984 / 1985-2004 casi ningún país tendría 15 años en cada lado). Como los años
   contiguos están autocorrelacionados, se publica además, solo informativa, la partición temporal (ajuste ≤ 1984, puerta
   1985-2004).
b) **Mínimo de 15 años** con los dos datos (anual JST y mensual traducido) **en cada mitad** (pares para la recta, impares
   para la puerta) para que un país tenga recta y puerta propias; si no, solo se muestran sus indicadores. Se publican los
   años usados por país e indicador.
- La puerta agregada (§2) se mide con los impares de los países que tienen recta propia.
- Decisiones aprobadas (26-oct): PIB trimestral OCDE como fuente nueva; dos trimestres seguidos para entrar y salir;
  bandas p50 / p80 / p95; puerta correlación ≥ 0,8 y pendiente en [0,8; 1,25].
