---
documento: P-DEV-INT9 — factores comunes → giros y bolsa (prerregistro interno, fase 2)
version: 0.1 BORRADOR (2026-10-30). NO congelado
estado: borrador. Antes de escribirlo NO se ha cruzado ningún factor con ningún objetivo. Solo estructura de X (docs/int/INT9_fase1.md) y potencia con objetivos sintéticos
depende_de: INT9_fase1.md (research/int/int9_fase1.json, commit 55075f6); INT-4 (listón B1, dejar un país fuera, AUC estratificada, placebo por desplazamientos); INT-6 X1 (S4 establecido); INT-7 (bolsa real, Driscoll-Kraay)
---

# P-DEV-INT9 (borrador v0.1): ¿los factores comunes anticipan recesiones o bolsa?

## 0. Qué es y qué no es
- **Pregunta.** Los dos factores globales que salen de los indicadores (F1 nominal mundial, F2 condiciones financieras
  mundiales; INT9_fase1 §3) ¿añaden información para anticipar la **entrada en recesión** del año siguiente? La bolsa
  real del año siguiente queda como informativa (potencia insuficiente, §2).
- **Muestra:** JST ≤ 2004, 14 países del núcleo, 1871-2004, sin guerras ni hiperinflación (como INT-4 / INT-6). Países
  de prueba (AUS, CAN, CHE, IRL) con modelo congelado. **No gasta el periodo bloqueado.**
- **No es** un modelo de inversión. Gobierno de siempre: decisiones del usuario (§7) → congelar con hora → script con
  puerta (árbol limpio) → **una sola corrida**.

## 1. Factores (fijados antes de mirar ningún objetivo)
- Indicadores, transformaciones, winsorización y exclusiones: exactamente los de `scripts/int9_fase1.py` (8 indicadores).
- **Estimación PIT de las cargas (recomendado: ajuste cruzado por mitades).** Las cargas de 1871-1949 puntúan los años
  1950-2004 y viceversa (EM-PCA, R = 2, alineadas por congruencia con el signo de INT9_fase1). Así ningún año se puntúa
  con cargas que lo hayan visto. Factor del año t con datos JST de t (conocidos a 30-abr de t + 1, como INT-4).
- Cobertura mínima: un año entra si tiene ≥ 60 % de sus celdas (quita 1870).
- Signo: el de INT9_fase1 (F1 + con inflación; F2 + con bolsa).

## 2. Contrastes (≤ 3) y potencia (INT9_fase1 §6)

| id | pregunta | base | estadístico | MDE 80 % (α/3) | destino |
|---|---|---|---|---|---|
| **N1** | F1 en t → entrada en recesión en t + 1 | B1 + S4 | ΔAUC estratificada, dejar un país fuera | OR ≈ 1,7/dt; ΔAUC ≈ +0,05 | confirmatoria |
| **N2** | F2 en t → entrada en recesión en t + 1 (signo −: condiciones buenas, menos recesiones) | B1 + S4 | ídem | ídem (≈) | confirmatoria |
| N3 | F1 y F2 en t → bolsa real en t + 1 (panel, efectos de país, DK) | — | t DK | ≈ 4,5 pp/dt (INT-7 halló 2-3) | **informativa** |

- Por qué **sobre B1 + S4**: X1 (% de otros países con PIB cayendo) ya está establecido y es en parte un factor común
  (corr F1-S4 −0,37). La pregunta útil es si F1/F2 añaden algo **más allá** de lo que ya sabemos. Sobre B1 solo se
  publica como informativo.
- Familia confirmatoria: **Holm-2** sobre el p del placebo (como INT-6).

## 3. Placebo
Las series F1/F2 (años × 1, comunes a todos los países) se desplazan k años en círculo dentro de 1871-2004, k = 6 …
L − 6 (como INT-4); se rehacen filas completas, los dos modelos y el dejar un país fuera. p_z unilateral de la ΔAUC
(INT-6) y p por rangos (sin Holm). Con un factor solo de año, el desplazamiento conserva su autocorrelación.

## 4. Criterios de "establecido" (todos)
1. ΔAUC estratificada > 0 con IC por bloques de año que excluye 0 tras Holm-2.
2. p_z del placebo pasa Holm-2.
3. Δlog-loss < 0.
4. ΔAUC > 0 en las dos mitades (1871-1949 y 1950-2004) **y** en la temporal 1950-2004.
5. Pendiente de calibración entre 0,5 y 1,5.
N2 además: coeficiente de F2 negativo.

## 5. Informativas y descriptivas (sin Holm)
- N1/N2 sobre B1 solo; con cargas de toda la muestra; con 1 solo factor (F1 + F2 juntos); países de prueba.
- N3 (bolsa) con t DK y bootstrap de INT-7 si la decisión 3 lo pide.
- Variante "solo macro" (sin bolsa ni vivienda en X).

## 6. Expectativa honesta
La potencia solo cubre efectos grandes: ΔAUC incremental ≈ +0,05 sobre S4 es mucho pedir a un factor que comparte
parte de su información con S4 y con la curva y la bolsa de INT-4. **Lo más probable es "no establecido"**, y eso no
será "no existe". El valor de INT-9 está también en la fase 1: saber que el mundo, en estos datos, es esencialmente
**dos factores** y que los regionales no aportan.

## 7. Decisiones del usuario (antes de congelar)

| # | decisión | opciones | recomendación |
|---|---|---|---|
| 1 | Base de N1/N2 | B1 (comparable con X1) · **B1 + S4** (valor añadido) | **B1 + S4**; B1 solo como informativa |
| 2 | Cargas PIT | toda la muestra (más potencia, mira X futuro) · **ajuste cruzado por mitades** · ventana creciente desde 1900 (pierde 1871-1899) | **ajuste cruzado**; toda la muestra como sensibilidad |
| 3 | Bolsa (N3) | confirmatoria (Holm-3) · **informativa** | **informativa** (MDE el doble de lo plausible) |
| 4 | Número de factores | **2** · 3 (F3 inestable) | **2** |
| 5 | X con rentabilidades del año (bolsa, vivienda) | **sí** (F2 las necesita) · solo macro | **sí**; solo macro como sensibilidad |
| 6 | Factor propio por país (P1) | contraste aparte · **fuera** | **fuera**: corr −0,68 con F1, no es otra idea |
| 7 | Regionales | **no** · sí | **no**: no superan a grupos al azar (INT9_fase1 §5) |
| 8 | Siguiente paso si N1/N2 no pasan | cerrar INT-9 · knockoffs/PCMCI con división interna (nota de literatura) | cerrar y anotar knockoffs para la base v0.5 |
