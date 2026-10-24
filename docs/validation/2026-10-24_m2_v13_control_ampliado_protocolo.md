---
documento: protocolo PRERREGISTRADO del control sintético ampliado de M2 v1.3 (cobertura del intervalo del 80 % de G)
fecha: 2026-10-24
autor: Validador independiente
objeto: m2_structural_spec.md v1.3 (d8eb113), implementación 90f408f, control de 4 semillas d892b93 (0,834 / 0,818 / 0,855 / 0,872; NO superado, queda declarado y no se borra)
estado: escrito, commiteado y empujado ANTES de correr ninguna semilla nueva. Nada de lo de abajo se cambia después de ver un resultado de las semillas 1001-1040
contacto_con_datos: NINGUNO. Solo datos sintéticos (tests/m2_synth.py). No se carga la etiqueta (ni ≤ 2004), ni la base PIT, ni niveles reales. Nada se registra en harness_runs ni en el trial log
script: tests/validation/m2_v13_control_ampliado.py (salida en research/validation/m2_v13_control_ampliado/)
---

# Control ampliado de M2 v1.3: protocolo prerregistrado

## 0. Qué había visto antes de escribir esto

- Los resultados agregados del control de la v1.2 (0,855-0,922) y de la v1.3 (0,834 / 0,818 / 0,855 / 0,872, cobertura
  del 50 %: 0,52-0,58) con las semillas 3, 7, 11 y 21. No he visto ningún resultado mes a mes.
- El código: `src/models/pool_controls.py::m2_planted`, `src/models/models_struct.py` (`v_conj`, `ghat`, `FactorEngine`)
  y `tests/m2_synth.py`. Al leerlo he formulado dos hipótesis (H-a y H-b, §4). **No las he comprobado con ningún dato
  antes de este push.**
- Ninguna semilla de 1001 a 1040 se ha generado ni ejecutado.

## 1. Qué se reproduce (sin tocar nada)

- **Generador:** `tests.m2_synth.Synth(seed)` sin cambiar el código. **Código de M2:** `src.models.models_struct.StructuralG(rev="none")`
  del commit `90f408f` (sin cambios hasta HEAD `2f9322f`).
- **Bucle:** el mismo de `m2_planted` en `src/models/pool_controls.py`: cortes mensuales T = 1980-01 … 2004-08 (296);
  en cada T `fit_axis_continuous("G", …, s.info(T, data_key=…))` y `predict_axis_continuous`; z = (G − μ)/σ̂ con
  G = `s.true_G()`; acierto del 80 % = |z| < Φ⁻¹(0,9). Mi script copia ese bucle (sin la parte de recuperación de λ, que
  no interviene en la cobertura) y además guarda la serie mes a mes (μ, σ̂, G, z, versión, V<sub>conj</sub>, n<sub>conj</sub>,
  convergencia). Un proceso por semilla, `MS.clear_engines()` al empezar, BLAS a 1 hilo.
- **R0, comprobación de la réplica:** las semillas 3, 7, 11 y 21 deben reproducir las coberturas de
  `research/trials/m2/controles_m2_v13.json` con diferencia < 1e-9. Si no, paro y no corro nada más hasta entenderlo.

## 2. Brazos

| brazo | qué | semillas | papel |
|---|---|---|---|
| **A (principal)** | réplica literal del control de la spec v1.3 §6: `Synth(seed)` (fin por defecto 2004-12) | **1001, 1002, …, 1040** (40, por regla: las primeras 40 a partir de 1001; distintas de 3/7/11/21) | **criterio de aceptación** |
| B (diagnóstico) | igual que A, pero `Synth(seed, end="2009-12")` (mismo código, solo cambia el argumento `end`): el G verdadero de todos los cortes ≤ 2004-08 tiene la ventana de tendencia de ±60 meses completa, como pide el texto de §6 ("G verdadero = el de la etiqueta con los niveles sintéticos **completos**") y como tiene la etiqueta oficial real. El modelo solo ve datos ≤ T, así que alargar la serie no le da información | 1001-1040 (trayectorias distintas de A, porque el RNG reparte las extracciones de otra forma) | diagnóstico de H-a |
| D3 (diagnóstico) | en las semillas 1001-1010 del brazo A, para cada versión T (cada enero), los errores e<sub>s</sub> de V<sub>conj</sub> mes a mes (réplica de `models_struct.v_conj` llamando a `MS.ghat`; su media debe coincidir con `v.v_conj` con diferencia < 1e-9) | 1001-1010 | diagnóstico de H-b |

**Regla de tiempo (fijada ahora):** si el tiempo medio por semilla de R0 supera 12 minutos, los brazos A y B se reducen
a las semillas 1001-1024 y D3 a 1001-1005, y lo anoto en este fichero **antes** de lanzar ninguna semilla nueva. No hay
ninguna otra reducción posible después.

## 3. Criterio de aceptación (brazo A; fijado)

- **Principal:** c̄ = media de las 40 coberturas del 80 %; IC 95 % entre semillas = c̄ ± t<sub>0,975; 39</sub>·sd/√40
  (sd con ddof 1). **Se acepta si el IC entero queda dentro de [0,75; 0,85]**.
- **Secundario (fijado de antemano, informa, no decide solo):** fracción de semillas con cobertura en [0,75; 0,85]
  **≥ 0,70**. Si el principal se cumple y el secundario no, el veredicto es "aceptado con reserva (dispersión entre
  semillas)".
- Se informan también, sin criterio: cobertura del 50 % y del 95 %, media de z² (calibración de la varianza; ideal 1)
  con su IC entre semillas, y el exceso de curtosis de z.
- El control de 4 semillas de la spec (3/7/11/21, "las cuatro dentro") **queda NO superado y declarado**; este control
  no lo sustituye ni lo borra: es otro control, más preciso, preregistrado aparte.

**Expectativa a priori (para que conste):** con c̄ ≈ 0,845 en las 4 semillas viejas y sd ≈ 0,023, la semiamplitud del IC
con 40 semillas será ≈ 0,007, así que el criterio principal es exigente: si la cobertura media verdadera es ≈ 0,845, lo
más probable es que **falle** por arriba. Lo acepto así; no cambio el criterio.

## 4. Hipótesis de diagnóstico (formuladas solo leyendo el código, antes de ver datos)

- **H-a (artefacto del control):** `Synth` termina en 2004-12, así que para los cortes T ≥ 2000-01 el "G verdadero"
  tiene la tendencia truncada (T + 60 > 2004-12), mucho más cerca del Ĝ (truncado en T + 4) que la G con ventana
  completa contra la que se mide V<sub>conj</sub>. En 2004-08 los dos truncan en el mismo mes y el error de tendencia
  desaparece. Predicción: en A, cobertura(T ≥ 2000-01) > cobertura(T ≤ 1999-12); B < A.
- **H-b (sesgo de V<sub>conj</sub>):** la muestra de V<sub>conj</sub> empieza en s = 1968-06; hasta ≈ 1974-07 CMRMTSPL no
  tiene τʳ (≥ 90 de 120 meses; empieza en 1967-01 en el sintético, como en los datos reales) y, por M2-6, el Ĝ
  pseudo-tiempo-real se compone con 3 coincidentes mientras que G(niveles de T) usa 4; además σ<sub>i</sub> de CMRMTSPL
  sale de una muestra corta. En T = 1980-01 casi toda la muestra de V<sub>conj</sub> (1968-06 → 1974-08) es de ese tipo.
  Predicción: en D3, ECM de e<sub>s</sub> con s < 1974-08 > ECM con s ≥ 1974-08; en A, sobrecobertura mayor en los
  cortes de 1980-1989 que en 1990-1999.
- **H-c (forma, no escala):** si los errores tienen colas gruesas o son heterocedásticos, una σ̂ con el ECM correcto
  sobrecubre el 80 % (con E[z²] ≈ 1). Se distingue con la media de z² y las coberturas del 50/95 %.

## 5. Qué se concluye en cada caso (fijado)

| resultado | veredicto que daré |
|---|---|
| A cumple el principal | `m2_long` puede correr con M2 v1.3 tal cual, declarando el control de 4 semillas no superado y por qué su regla era demasiado estricta |
| A no cumple; B cumple el principal; en A la cobertura de T ≤ 1999-12 tiene el IC dentro del rango | el desvío es un **artefacto del control** (H-a), no de M2: `m2_long` con M2 v1.3 tal cual; corrección a priori **del control** (§6: generador hasta ≥ 2009-12), a aprobar por el usuario |
| B tampoco cumple (por arriba) | σ̂ de M2 sobrestima de verdad: diagnóstico con D3 (H-b) y H-c; propongo **un** cambio a priori dirigido a la causa que los datos señalen (p. ej., si H-b: medir V<sub>conj</sub> solo en los s cuyo Ĝ<sup>ps</sup> se compone con el mismo conjunto de coincidentes que en T); si es H-c con E[z²] ≈ 1, la varianza está bien y el criterio de cobertura del 80 % no es el adecuado para la log-score: lo diré así y el usuario decide |
| A o B por debajo de 0,75 | infracobertura: lo informo con la misma lógica; ningún cambio sin diagnóstico |

## 6. Error de Monte Carlo (tarea 3; con las semillas viejas de R0 y con las nuevas)

Para cada semilla: SE de la cobertura por **bootstrap de bloques móviles** sobre la serie de aciertos (bloques de 12, 24
y 48 meses; 2.000 réplicas; semilla del bootstrap 12345) y n<sub>efectivo</sub> = c(1 − c)/SE². Se compara con la sd
entre semillas (estimación directa del error de Monte Carlo de una semilla) y se calcula, con esa sd, la probabilidad
de que 4 semillas caigan todas en [0,75; 0,85] si la cobertura media verdadera fuera 0,80 y si fuera la observada.
