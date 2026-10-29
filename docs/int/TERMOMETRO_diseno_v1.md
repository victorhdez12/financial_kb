---
documento: Termómetro de recesión INFORMATIVO (probabilidad mensual de entrar y de salir de recesión por país) — diseño corregido
version: 1.2 APROBADO (2026-10-29; v1.1 + opciones a, b, d, e del usuario por el bloqueo de datos, §8, fijadas antes de escribir código)
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

## 8. Bloqueo de datos y opciones aprobadas (v1.2, 2026-10-29, antes de escribir código)
Bloqueo (agente, 26-oct): el tipo a 3 meses de la OCDE empieza ≈ 1980-1990 en casi todos los países → con ≥ 15 años por
mitad solo DEU y USA tendrían recta; C4 (difusión) no llega a 15 años; S4 no tenía traducción mensual; faltaba fijar las
filas y el B1 de la puerta. El usuario eligió **a + b + d + e**:

a) **C4 sin recta.** Mensual = % de los otros países del núcleo con curva mensual (C1 mensual sin traducir) < 0, con ≥ 5
   países con dato. Es una proporción, como la anual: se usa tal cual.
b) **Rectas agrupadas.** Si un país-indicador no tiene ≥ 15 años con ambos datos en cada mitad (pares e impares ≤ 2004), se
   le aplica la recta **agrupada** (ajustada con los años pares de todos los países del núcleo con ambos datos). Se publica
   qué recta usa cada país-indicador.
d) **S4 con el PIB trimestral.** Mensual = % de los otros países del núcleo con la suma de 4 trimestres del PIB real por
   debajo de la de 4 trimestres antes (dato conocido 75 días tras el trimestre), con ≥ 5 países con dato. Sin recta (como
   C4). JST usa PIB per cápita; aquí PIB total (declarado).
e) **Puerta de T1 en las filas de T1 y de T2 en las de T2**, las mismas filas (país, año t) del ajuste de INT-4, con el
   **B1 del fechado anual JST** en las dos probabilidades (la puerta mide solo la traducción de los indicadores). Solo
   años impares, y solo filas con todos los indicadores anuales y mensuales.

Concreciones (fijadas aquí, antes de calcular nada):
- Fecha mensual de cada fila: fin de abril de t + 1 (el origen de INT-4).
- C1 mensual = media de los 12 últimos meses de la curva "as of" (10 años − 3 meses, `src/intl/panel.py`), con ≥ 9 de 12.
- C5 mensual = r(m) − r(m − 12), con r = media de 12 meses del tipo a 3 meses / 100 − IPC interanual (log).
- C6 mensual = variación de 12 meses (log) del índice de bolsa OCDE − IPC interanual (log). DNK y JPN sin bolsa mensual
  (índices OCDE rotos, como en `panel.py`) → sin T1 ni T2 (solo indicadores).
- C2 mensual = Δ 20 trimestres del crédito/PIB del BIS (%), conocido 183 días después del fin del trimestre.
- S1 = C1, S2 = C5, S3 = C6 (mensuales); S5 = C2 mensual traducida en abril del año del pico + 1.
- Recta: MCO de x anual (JST, año t) sobre x mensual (abril de t + 1), todos los años ≤ 2004 con ambos datos (no solo las
  filas del modelo), sin guerras (todo es ≥ 1950).
- Modelo congelado: logit de INT-4 (B1 + C1, C2, C4, C5, C6 para T1; B1 + S1-S5 para T2) ajustado UNA vez con todas las
  filas completas del núcleo 1871-2004 sin guerras, h = 1.
- Puerta: correlación de Pearson entre p anual y p mensual ≥ 0,8 y pendiente de la MCO de p anual sobre p mensual en
  [0,8; 1,25], por giro (T1 y T2 por separado). Agregado: impares de todo el núcleo. Por país: si tiene ≥ 8 filas impares
  debe pasar su propia puerta; con < 8, depende solo del agregado (marcado "sin puerta propia").
- Informativo: partición temporal (rectas con ≤ 1984, puerta 1985-2004).
- Percentiles de referencia (§4): probabilidades mensuales traducidas de todos los meses 1960-2004 del núcleo con datos
  completos, B1 del fechado en vivo (§3): T1 en meses fuera de recesión, T2 dentro.
- La parte en vivo (datos ≥ 2005, reporte semanal) se construye solo si pasa la puerta agregada y tras el Validador.

## 9. Segundo y último intento (v1.3, 2026-10-29, fijado ANTES de correrlo; el usuario lo delegó: "confío en tu criterio")
Resultado del 1.er intento (`188cc30`): T1 r 0,81 pero pendiente 0,66; T2 r 0,79 con solo 18 filas impares. **Contaminación
declarada:** este intento se diseña sabiendo que el fallo de T1 es de escala (pendiente < 1, orden bien) y que T2 tiene
pocas filas. Para compensar, la puerta NO se relaja (mismos umbrales: r ≥ 0,8 y pendiente en [0,8; 1,25]) y **no habrá un
3.er intento**: si falla, el termómetro queda definitivamente en "solo indicadores".

Cambios (los únicos):
1. **Recalibración de la escala.** Con las filas de la mitad de ajuste: MCO de logit(p anual) sobre logit(p mensual
   traducida) → (α, β); la probabilidad mostrada es σ(α + β · logit(p mensual)). Solo usa las dos probabilidades (no el
   objetivo).
2. **Validación cruzada en dos mitades.** Pliegue 1: rectas y recalibración con los pares, puerta con los impares; pliegue
   2: al revés. La puerta se mide con las filas de los dos pliegues juntas (cada fila predicha por el pliegue que no la
   usó). Regla propia/agrupada de las rectas: la misma (≥ 15 años en cada mitad).
3. Por país: puerta propia si tiene ≥ 8 filas en total (los dos pliegues); si no, depende del agregado.
- En vivo (si pasa): rectas y recalibración ajustadas con TODOS los años ≤ 2004; percentiles de referencia recalculados con
  esas probabilidades recalibradas.
- T1 y T2 se juzgan por separado: si solo pasa uno, solo se muestra ese.
