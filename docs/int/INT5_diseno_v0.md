---
documento: INT-5 — termómetro de recesión (T1 entrada / T2 salida) en sombra en el paper trading, y cómo intentar mejorarlo sin minería
version: 0.1-borrador (2026-10-26)
estado: BORRADOR para el usuario. Nada construido. Ningún dato ≥ 2005 de JST mirado.
depende_de: INT-4 (P-DEV-INT4 v1.0; T1 y T2 establecidos; Validador ⚠️ sin cambio de clasificación), docs/factors/paper_trading.md (B0, B1)
---

# INT-5 (diseño v0.1)

## 0. Qué es
- **B2 = B1 + termómetro.** B1 (70/15/15 con ajuste por volatilidad, RV en [55 %, 70 %]) sigue siendo la cartera
  operativa. B2 se calcula cada mes **en sombra**, se registra igual que B0 y B1 y **no mueve dinero**. Solo sustituye a
  B1 con una decisión registrada del usuario.
- **Honestidad:** 36 meses de paper trading no tienen potencia para distinguir B2 de B1 (como B1 frente a B0). La sombra
  comprueba que el termómetro **funciona en vivo** (datos llegan, la probabilidad se mueve cuando debe, rotación y costes),
  no su ventaja. La evidencia de ventaja viene de §3.

## 1. El termómetro en vivo
- **Modelo congelado:** los coeficientes del logit de INT-4 ajustados en el núcleo 1871-2004 sin guerras (T1: B1 + C1,
  C2, C4, C5, C6; T2: B1 + S1-S5). No se reajusta con datos posteriores (eso gastaría el bloqueado).
- **Problema de frecuencia:** el modelo es anual (datos JST del año t, origen en abril de t + 1); JST acaba en 2020 y no
  hay datos en vivo. Traducción fijada a priori, mensual, con datos que sí llegan en vivo:
  | indicador | anual (JST) | en vivo (mensual, últimos 12 meses) |
  |---|---|---|
  | C1/S1 curva | ltrate − stir, media del año | media 12 m de (10 años − 3 meses), OCDE / FRED |
  | C4 difusión | % de los otros 13 con curva invertida | ídem con la media 12 m de cada país (OCDE) |
  | C5/S2 Δ tipo real corto | Δ1 (stir − inflación) | Δ12 de (3 meses − IPC interanual) |
  | C6/S3 bolsa real | rentabilidad real total del año | rentabilidad real total de 12 m (MSCI/S&P + IPC) |
  | C2/S5 Δ5 crédito/PIB | JST | BIS "total credit to private non-financial sector", % PIB, Δ 20 trimestres |
  | B1 (años desde valle; duración) | fechado JST | fechado anual con el PIB real per cápita anual (OCDE/FMI) |
- **Agregado para la cartera:** la cartera es global → probabilidad = media ponderada por PIB de la de los países del
  núcleo con datos (y EE. UU. aparte, informativo).
- **Comprobación de la traducción (sin resultados de rentabilidad):** con datos ≤ 2004, la correlación entre la
  probabilidad anual JST y la mensual traducida, tomada en abril, debe ser ≥ 0,8 en los países con ambas; si no, se declara
  y se usa la anual (actualizada una vez al año).

## 2. La regla de B2 (fijada sin backtest de cartera)
- **Recorte:** si p_T1 (agregada) > **u₁** → la RV de B2 = RV de B1 − **10 pp** (suelo 45 %). Al revés, si estamos en
  recesión y p_T2 > **u₂** → B2 vuelve al peso de B1 (no por encima).
- **Umbrales por propiedades de la señal, no por rentabilidad:** u₁ = percentil 80 de p_T1 en desarrollo (≈ 1 de cada 5
  años en alerta); u₂ = percentil 50 de p_T2 en años de recesión. Se fijan con un script commiteado antes de calcularlos.
- Rotación máxima declarada; costes como en B1.

## 3. Cómo intentar mejorar (sin minería; cada paso con potencia antes)
Regla del proyecto: no afinar más con datos ≤ 2004. Añadir indicadores al modelo de INT-4 **no tiene potencia** (un
indicador suelto aporta ≈ +0,02-0,05 de AUC y lo detectable es ≈ 0,10-0,12). Tres vías honestas:
1. **P-EVAL-INT4: confirmación fuera de muestra en el bloqueado de JST (2005-2020), una sola vez.** Es la mejora más
   valiosa: dice si el termómetro funcionó en 2008, 2011-2012 y 2020 sin haberlo visto. **Cuesta el periodo bloqueado de
   JST** (el de EE. UU. de Fase 3 es otro y sigue intacto). Las recesiones de 2005-2020 se concentran en pocos años (2008-09,
   2012, 2020) → potencia baja: primero un cálculo de potencia solo con recuentos; si la mejora detectable es > 0,20,
   el usuario decide si vale la pena gastarlo.
2. **Calibración y combinación, no indicadores nuevos:** promediar T1 dejando un país fuera y temporal (dos ajustes ya
   prerregistrados) y recalibrar con beta (como el pool de Fase 3). Solo se cambia si mejora el log-loss en desarrollo
   dentro de un prerregistro nuevo con potencia previa; si no, se queda el modelo congelado.
3. **Información nueva de verdad**, prerregistrada y con potencia antes: diferenciales de crédito (Baa − Tesoro en EE. UU.
   desde 1928 y R. U. desde 1854, ya catalogados en INT-3b) para T1 y T2; difusión de la bolsa (% de países con
   caída > 20 %) para T2. Solo en EE. UU./R. U. → potencia menor; probable resultado "no establecido".

## 4. Decisiones del usuario
1. Montar la sombra de B2 con el modelo congelado y la traducción mensual de §1 (recomendado) o con el modelo anual
   (una actualización al año, más simple pero lento).
2. Regla de §2: recorte de 10 pp con u₁ = percentil 80 y vuelta con u₂ = percentil 50 (recomendado) o solo el recorte.
3. Mejora: (1) calcular ya la potencia de P-EVAL-INT4 sin mirar nada (recomendado; gastarlo se decide después),
   (2) y/o (3).
4. Orden: primero la sombra (para que empiece a registrar desde el cierre de noviembre), luego la mejora.
