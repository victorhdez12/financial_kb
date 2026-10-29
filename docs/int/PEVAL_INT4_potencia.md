---
documento: P-EVAL-INT4 — cálculo de potencia de la confirmación fuera de muestra (una sola vez) de T1 y T2 de INT-4 en el bloqueado JST 2005-2020
version: 0.1 (2026-10-29)
estado: §1 (qué se lee) escrito y commiteado ANTES de escribir y correr el script. Resultados en §3 tras la corrida.
depende_de: docs/int/INT4_prerregistro_v0.md (v1.0), research/int/int4_resultado.json, research/int/int4_sensibilidad_liston*.json, docs/int/INT5_diseno_v0.md §3.1
---

# P-EVAL-INT4: potencia (solo recuentos de eventos del bloqueado)

## 0. Qué se pregunta
INT-5 §3.1 propone gastar **una vez** el periodo bloqueado de JST (años objetivo 2005-2020) para confirmar fuera de
muestra los modelos T1 (entrada en recesión a 1 año) y T2 (salida) de INT-4, congelados con datos ≤ 2004. Antes de
decidir si se gasta, este documento calcula **cuánta potencia** tendría esa confirmación, contando solo eventos.

## 1. Qué se lee del bloqueado (fijado antes de leer nada)
Para contar las recesiones de 2005-2020 hace falta el **objetivo** (el PIB real per cápita), no los indicadores.
Se lee exactamente esto y nada más:

- **Series:** `jst_{iso}_rgdpmad` (PIB real per cápita, JST R6) de los 14 países del núcleo (BEL, DEU, DNK, ESP, FIN,
  FRA, GBR, ITA, JPN, NLD, NOR, PRT, SWE, USA) y de los 4 de prueba (AUS, CAN, CHE, IRL), **todos los años**
  (1870-2020). Lo ≤ 2004 ya se conocía; lo nuevo es 2005-2020.
- **Para qué:** únicamente para fechar picos y valles con la misma regla de `src/intl/regimes.recesiones_anuales`
  (convención JST) sobre la serie completa, y de ahí: entradas (pico + 1) y salidas (valle + 1) con año en 2005-2020,
  filas en riesgo de T1 (orígenes t = 2004 … 2019 fuera de recesión) y de T2 (orígenes t = 2004 … 2019 en recesión).
- **Qué sale del script:** solo años de pico, valle, entrada y salida y recuentos por país y año. **Ningún valor ni
  tasa de crecimiento del PIB** se escribe ni se imprime. El tipo de recesión (financiera/normal) **no** se calcula
  (necesitaría `crisisjst` ≥ 2005).
- **Lectura aislada:** una función del script, con consulta SQL a `obs_latest` restringida a esas 18 series
  (`load_dev` corta en 2004 por diseño; no se toca `src/intl/`). Ninguna otra serie se lee con fechas ≥ 2005.
- **Qué NO se lee nunca:** ningún indicador ≥ 2005 (ltrate, stir, tloans, gdp, cpi, eq_tr…), ni siquiera su
  disponibilidad (no se cuentan casos completos), ni `crisisjst`, ni ninguna predicción. Supuesto declarado: en
  2005-2020 los indicadores de T1/T2 están completos en el núcleo (JST R6 cubre esas variables hasta 2020); el número
  real de filas completas solo se conocerá al evaluar.
- **Comprobación de coherencia (solo ≤ 2004):** el fechado con la serie completa se compara con
  `recesiones_anuales_dev.parquet` en los eventos ≤ 2004 (puede cambiar como mucho el último valle, truncado en 2004).

## 2. Método de potencia (sin datos de indicadores)
- **Estructura real de eventos** del bloqueado (qué filas son y = 1 y en qué año) y **puntuaciones simuladas**:
  binormal, s | y ~ N(μ·y, 1) para el modelo y el listón, AUC = Φ(μ/√2), correlación del ruido modelo-listón r = 0,5,
  y un componente común por año (ICC ρ = 0 / 0,3 / 0,6) para imitar que los indicadores globales (C4, C6, S3, S4) mueven
  a todos los países a la vez.
- **Efectos de desarrollo:** T1 listón 0,55 → modelo 0,73 (ΔAUC +0,18; estratificado ≈ +0,20); T2 listón 0,58 →
  0,77 (estratificado +0,19). También la mitad del efecto (encogimiento fuera de muestra) y H0 (Δ = 0).
- **Inferencia como en INT-4:** bootstrap por bloques de año (se remuestrean años con todos sus países) sobre las
  predicciones; IC 95 % de ΔAUC; Holm sobre 2 (T1, T2).
- **Criterios alternativos:** (a) ΔAUC > 0 con IC por bloques; (b) AUC del modelo > 0,5 con IC; (c) signo de ΔAUC;
  (d) Δlog-loss < 0; (e) calibración (pendiente en [0,5; 1,5]) con el intercepto congelado de desarrollo.
- **Fórmula de referencia:** MDE de Hanley-McNeil como en `scripts/int4_potencia.py` (positivos efectivos centrales
  con efecto de diseño por año, y prudentes = años distintos con evento).
- **Sensibilidad:** sin 2020 (choque exógeno de la pandemia: se quitan las filas con año objetivo 2020).

## 3. Resultados
(pendiente de la corrida)
