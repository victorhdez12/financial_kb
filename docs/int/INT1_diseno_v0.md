---
documento: INT-1 — régimen por país y fechado de recesiones (diseño)
version: 0.1-borrador (2026-10-26)
estado: BORRADOR para el usuario. Nada corrido. No se ejecuta hasta que INT-0 tenga el veredicto del Validador.
plan: docs/PLAN_internacional_v0.md (pieza 1)
---

# INT-1: régimen por país (diseño v0.1)

## 1. Qué produce
Para cada país y periodo, una **etiqueta de régimen ex post** (describe "dónde estábamos", con datos revisados, como la
etiqueta v1.1 de EE. UU.) en dos frecuencias, más dos capas:
- **Anual 1870-2004** (JST, 18 países): para medir el mapa régimen → activos con muchos episodios (INT-3).
- **Mensual 1955-2004** (OCDE, los países con datos): para operar y para el forecast de riesgo (INT-4).
- **Capa de recesión** (fechas de pico y valle por país) y **capa de crisis financiera** (JST `crisisjst`).

La etiqueta ex post **no es una señal**: es el objetivo que luego se intentará estimar o anticipar con información de cada
momento (as of). El corte técnico (≤ 2004) se mantiene.

## 2. Ejes y cuadrantes (misma lógica que la v1.1 de EE. UU.)
- **Crecimiento (G):** por encima o por debajo de su tendencia.
  - Anual: crecimiento del PIB real per cápita frente a su media móvil **centrada** de 11 años (t − 5 … t + 5) del propio
    país. Centrada a propósito: es ex post.
  - Mensual: producción industrial (y paro invertido cuando exista), z-score frente a la tendencia centrada de 10 años, como
    la v1.1 (ventana t − 3 … t + 3 para el nivel).
- **Inflación (I):** alta o baja.
  - **Principal (propuesta):** **relativa**: inflación por encima de su media móvil centrada de 11 años **y** por encima
    del 2 %. Motivo: con 150 años y patrones oro, un umbral fijo (p. ej. 3 %) marcaría como "baja" casi todo el siglo XIX
    y como "alta" casi todos los años 70-80 en todos los países, y mezclaría régimen con época.
  - **Sensibilidad (siempre publicada):** umbral absoluto del 3 % anual.
- **Cuadrantes:** expansión (G↑ I↓), sobrecalentamiento (G↑ I↑), estanflación (G↓ I↑), crecimiento bajo / desinflación
  (G↓ I↓). Probabilística como la v1.1 (P = Φ(distancia / s), s medida con la dispersión de cada serie) y "frontera" si la
  probabilidad máxima < 0,55.

## 3. Fechado de recesiones
- **Anual (JST):** pico = año con PIB real per cápita máximo local antes de una caída (la convención de Jordà-Schularick-
  Taylor); recesión = de pico a valle. Se distinguen **recesiones normales** y **financieras** (con crisis en ± 2 años del
  pico, `crisisjst`), como en su trabajo.
- **Mensual (OCDE):** algoritmo **Bry-Boschan** sobre la producción industrial (fase mínima 6 meses, ciclo mínimo 15 meses,
  amplitud mínima declarada). Parámetros fijados aquí, antes de correrlo.
- **Validación externa (solo como contraste, no como entrada):** NBER (EE. UU.), CEPR (zona euro desde 1970), y las fechas
  publicadas por los institutos nacionales donde existan. Medida: % de recesiones conocidas detectadas y desfase en meses.

## 4. Países
- **Núcleo** (datos completos anual y mensual): BEL, DEU, DNK, ESP, FIN, FRA, GBR, ITA, JPN, NLD, NOR, PRT, SWE, USA.
- **Países de prueba** (decisión del usuario: se usan después para ver cómo se comporta el modelo fuera de muestra):
  **AUS** (sin producción industrial mensual), **CHE** (mensual solo desde 2010), **CAN** e **IRL** (sin rentabilidades en
  JST). No entran en ningún ajuste ni en la elección de parámetros.
- Los 4 casos raros de INT-0 (ESP bonos; FRA, DNK, JPN bolsa) esperan al Validador.

## 5. Qué se publica y puerta
- Por país: % del tiempo en cada cuadrante, duración media de los estados, nº de recesiones (normales y financieras),
  concordancia con las fechas externas.
- **Recuento de episodios** (alimenta INT-2, el cálculo de potencia): país-episodios por cuadrante y recesiones, con la
  agrupación por año (recesiones globales: 1873, 1890s, 1907, 1920-21, 1929-33, 1974-75, 1980-82, 1991-93, 2001).
- **Puerta:** Validador ✅ (sin haber escrito el código) y concordancia con recesiones conocidas ≥ 80 % en los países con
  fechado externo; si no, se corrige el método **antes** de mirar ningún activo.

## 6. Lo que NO hace INT-1
No mira rentabilidades de activos por régimen (eso es INT-3, con su prerregistro); no usa nada ≥ 2005; no estima
modelos de nowcast ni forecast.

## 7. Decisiones del usuario
1. Inflación: **relativa + 2 %** como principal y 3 % absoluto como sensibilidad (recomendado), o al revés.
2. Parámetros de Bry-Boschan: fase mínima 6 meses, ciclo mínimo 15 meses (estándar de la literatura).
3. Núcleo y países de prueba como en §4.
