---
documento: P-INT11 — prerregistro del motor de escenarios probabilístico
version: 0.1-BORRADOR (2026-10-30). NO congelado: pendiente de las decisiones del usuario (§8)
diseño: docs/int/INT11_diseno.md · código: src/intl/escenarios.py (esqueleto, commit 6f3352c)
potencia: research/int/int11_potencia.json (6f3352c, árbol limpio, 300 réplicas)
periodo ≥ 2005: BLOQUEADO y sin tocar. Este borrador NO propone gastarlo (§7)
---

# P-INT11 (borrador v0.1): ¿son buenas las distribuciones del motor de escenarios?

## 0. Pregunta
¿El motor (M1: régimen operable → Markov → bootstrap por régimen) da **distribuciones calibradas** de rentabilidades
reales a 1 año, y **mejores** que no saber nada del régimen? No se evalúa ninguna predicción puntual.

## 1. Modelos (fijados antes de mirar)
| clave | qué es |
|---|---|
| M0 | referencia ingenua: distribución empírica **incondicional** del panel (mismo pool, sin régimen) |
| M0r | referencia "régimen ingenuo": el régimen de hoy se queda para siempre (solo para h > 1, descriptivo) |
| M1 | motor completo, configuración de §8 (por defecto: bootstrap, eje P3, k_pais 40, bloque 3, sin contagio) |
| M2 | M1 + inclinación del 1.er año con termómetro de recesión, F1 y D/P (anchos fijados en §8, D6) |

Cada pronóstico se construye **solo** con filas de entrenamiento (dejando el país fuera, o con años < corte). 20.000
trayectorias por pronóstico (200 lotes × 100), semilla fija.

## 2. Objetivos y puntuaciones
- Objetivo: rentabilidad real simple del año siguiente de bolsa, bonos, letras, vivienda y oro (oro solo ≥ 1972) por
  país-año; y acumulada a 5 años (ventanas sin solape) como secundaria.
- **CRPS** por activo (menor = mejor), normalizado por el CRPS medio de M0 en ese activo; puntuación de la fila = media
  de los activos disponibles. CRPSS = 1 − CRPS(M)/CRPS(M0).
- **Cobertura** de p5-p95 y p10-p90 (por activo y conjunta), **PIT** (histograma de 10 casillas, descriptivo),
  **log score** (núcleo gaussiano, secundario).
- Eventos (descriptivos, puntuación de Brier): caída real de la bolsa > 20 % a 1 año; inflación > 5 % el año siguiente.

## 3. Contrastes (Holm sobre los que queden; propuesta: 3)
| clave | contraste | diseño | potencia (sintética, δ = 1 = tamaños del Atlas) |
|---|---|---|---|
| C1 | M1 mejor que M0 en CRPS, h = 1 | DM unilateral, años como conglomerados, Newey-West 2 | ≤ 2004 LOCO 1,00 (δ80 = 0,65); bloqueado 0,40 |
| C2 | M1 mejor que M0 en CRPS, h = 5 | ídem, ventanas sin solape | ≤ 2004 LOCO 0,25; bloqueado 0,03 → **sin potencia** |
| C3 | M2 mejor que M1 en CRPS, h = 1 | ídem | no simulada; por INT-9/INT-7 el efecto esperado es menor que el MDE |

**Recomendación:** dejar **solo C1** como contraste (Holm-1 = α 0,05) y pasar C2 y C3 a descriptivos: no tienen
potencia, y cada contraste sin potencia encarece C1.

## 4. Criterio de calibración (puerta, no entra en Holm)
- Estadístico: cobertura conjunta (5 activos) y de la bolsa del intervalo p5-p95 a 1 año.
- **Valor crítico SIMULADO con el propio generador** (bajo H0 "el motor es correcto"): se generan 1.000 muestras del
  mismo tamaño y estructura (mismos países y años, choques comunes) con el propio M1 y se toma su percentil 2,5-97,5.
  El t por conglomerados no vale: en la simulación rechaza un 12-30 % de las veces con un modelo calibrado.
- **Calibrado** = no rechazado **y** cobertura observada dentro de ±5 pp de la nominal. Potencia para detectar 80 %
  frente a 90 %: 1950-2004 ≈ 1,00; bloqueado 0,95 (5 activos); en vivo 0,51 a 5 años, 0,87 a 10 años.
- PIT: histograma y tasa en las colas (< 0,05 y > 0,95) por activo, descriptivo.

## 5. Qué se considera "bueno"
1. **Calibrado a 1 año** (§4) en el conjunto y sin desviaciones > 5 pp en ningún activo.
2. **C1 establecido** (p < α, CRPSS > 0) **y** el mismo signo en el diseño temporal (≤ 1949 → 1950-2004).
3. **Útil aunque C1 no pase:** un motor calibrado con CRPSS ≈ 0 sigue siendo útil como generador Monte Carlo (abanicos
   honestos), pero entonces **no** se dirá que el régimen mejora la distribución.
Lo que nunca se dirá: que el motor "predice" la bolsa; ni nada a 5 años más allá de lo descriptivo.

## 6. Evaluación en vivo
- Cada año (cuando se publiquen los datos anuales del año cerrado, ≈ mayo): guardar los abanicos que el motor dio el
  año anterior para cada país (congelados con su commit), y anotar dónde cayó lo realizado (PIT, dentro/fuera).
- **Semáforo** (no contraste): cobertura acumulada frente a la banda simulada del propio motor para ese nº de años
  (verde dentro del 80 % central, ámbar 80-95 %, rojo fuera del 95 %).
- **Contraste formal** de calibración a los **10 años** de registro (potencia 0,87 para 80 % frente a 90 %). El CRPS
  frente a M0 en vivo no tiene potencia antes de ≈ 20 años: solo descriptivo.

## 7. ¿Merece gastar el periodo bloqueado 2005-2020? Recomendación: **NO para INT-11 solo**
- Para C1 (lo que interesa: "el régimen mejora la distribución") la potencia en 2005-2020 es **0,40** con efectos del
  tamaño del Atlas (probablemente inflados): lo más probable sería un "no establecido" sin información.
- Para la **calibración** sí habría potencia (0,95 para 80 % frente a 90 %), y es la única confirmación fuera de muestra
  posible sin esperar 10 años.
- Por tanto: **no gastarlo ahora**. Si el usuario decide en algún momento una **confirmación final única** de todo el
  proyecto, incluir allí la puerta de calibración de INT-11 (§4) y C1 como secundario.

## 8. Decisiones del usuario (con recomendación)
| # | decisión | opciones | recomendación |
|---|---|---|---|
| D1 | eje de crecimiento del régimen | (a) P3 del Atlas (brecha < 0 en 5,6 %: estanflación 1,7 %, crec. bajo 3,9 %); (b) crecimiento < media de 10 años (≈ 50/50, persistencia 0,46) | **(a)**: es la única con evidencia operable (bolsa en estanflación, pasa Holm) y más persistente; (b) como sensibilidad descriptiva |
| D2 | años de guerra en el pool | fuera (como INT-3…9) / dentro | **fuera** en la evaluación; **dentro** como variante "con guerras" del generador para escenarios de cola |
| D3 | oro antes de 1972 | fuera (donante de la celda) / dentro | **fuera** (precio fijo; Atlas §5.4) |
| D4 | parámetros del bootstrap | k_pais, bloque medio, n mínimo de celda | **40, 3 años, 25** (fijados ahora, sin probar otros) |
| D5 | contagio (régimen mundo) en M1 | sí / no | **no** en M1 (no hay potencia para evaluarlo); sí como opción del generador |
| D6 | M2: qué covariables y ancho | termómetro, F1, D/P; ancho 0,5 dt | **descriptivo** (sin contraste C3); anchos 0,5 dt |
| D7 | modo principal | bootstrap / t paramétrica | **bootstrap**; t como sensibilidad de colas |
| D8 | contrastes | Holm-3 (C1-C3) / solo C1 | **solo C1**; C2, C3 descriptivos |
| D9 | gastar el bloqueado | sí / no / dentro de una confirmación final única | **no ahora** (§7) |
| D10 | moneda | local / EUR | **local** en v1; EUR (con el tipo de cambio de JST/BCE) en v2 para el inversor en euros |
| D11 | varios países a la vez | v1 un país / v2 conjunto (mismo año histórico para todos) | **v2** si el modelo complementario necesita una cartera global |

## 9. Registro
Esta fase solo midió X (régimen) y Y (rentabilidades sin régimen) por separado y simuló; anotado en
`research/trial_log.md`. La corrida de desarrollo (≤ 2004) se hará **una vez**, tras congelar v1.
