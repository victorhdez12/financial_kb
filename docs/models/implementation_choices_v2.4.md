---
documento: elecciones de implementación del arnés v2.4 y de M2 (v1.3), M3 (v1.2) y el pool (v1.2) que las specs no fijan (Q1)
fecha: 2026-10-24
para: Validador (revisión antes de `m2_long`) y usuario
codigo: src/models/models_struct.py, struct_factor.py, models_tvtp.py, models_pool.py, harness.py, metrics.py (constantes `IMPLEMENTATION_CHOICES`)
estado: APROBADAS por el usuario tal cual (2026-10-25, antes de 6b `s_pit_001`; `m2_long` ya había corrido con ellas). PROVISIONALES. Ninguna se ha elegido mirando la etiqueta real: hasta hoy la etiqueta solo se ha leído en la sonda de elegibilidad (recuentos) y en placebos barajados ≤ 2004. Si el usuario cambia alguna, se cambia antes de `m2_long`.
---

# Elecciones de implementación (Q1)

Cada fila: qué deja abierto la spec, qué hace el código y por qué. Ninguna afecta a la etiqueta ni a qué datos se ven
(todo sigue siendo ≤ la fecha de decisión).

## M2 (`m2_structural_spec.md` v1.3)

| # | punto abierto | elección | justificación |
|---|---|---|---|
| M2-1 | detalles del arranque (§3: "primer componente principal… regresión… MCO") | PCA del panel balanceado **centrado** (media de columna), sobre la matriz de covarianza de las x ya estandarizadas; componente escalada a varianza 1 (ddof 0) y signo con λ_PAYEMS > 0; cargas = pendiente MCO **con constante** de cada x sobre la componente (peticiones: sobre su diferencia a 12 meses); φ y ρ por MCO **sin constante**; residuo = x − (constante + pendiente·regresor); si el φ del arranque no es estacionario, ×0,95 hasta que lo sea (se anota) | lectura estándar del ACP; las x ya están en unidades comparables; la constante absorbe que τʳ es una mediana y no una media. Solo afecta al punto de partida (óptimo local) |
| M2-2 | panel balanceado < 60 meses también con las 4 coincidentes (§3 no dice qué hacer) | se usa el de las 4 coincidentes igualmente (46-51 meses en 1978-79, por el τʳ de CMRMTSPL desde 1974-08); las series fuera arrancan con λ = 0,1 × signo esperado | lectura literal ("si < 60, el de las 4 coincidentes", sin condición sobre su longitud) |
| M2-3 | optimizador (§3 fija L-BFGS-B, maxiter, gtol) | inicialización estacionaria del filtro (verosimilitud exacta); gradiente por defecto de statsmodels (paso complejo); `pgtol` = 1e-6, `factr` por defecto | "máxima verosimilitud exacta"; los demás valores son los por defecto de la implementación única fijada (statsmodels 0.15.0) |
| M2-4 | sin convergencia: "se conservan los parámetros vigentes" | se conserva la **versión** anterior completa: parámetros + d_i + medias/desviaciones de peticiones y Filadelfia (los parámetros están en esas unidades); V_tend y V_conj se miden igualmente con esa versión | usar parámetros viejos con una estandarización nueva sería incoherente |
| M2-5 | "para los meses futuros se fija τʳ en su último valor" | τʳ futuro = τʳ del mes siguiente a la última observación (mediana de los 120 últimos meses observados, ≥ 90) | es el último τʳ calculable solo con datos observados |
| M2-6 | serie sin τʳ o sin d_i (CMRMTSPL antes de 1974-08) | no se extiende: su ritmo en t queda NaN y G se compone con las demás (mínimo 2, como la etiqueta) | sin τʳ no hay previsión definida; la regla de mínimo de la etiqueta decide |
| M2-7 | V_filtro (v1.3: diagnóstico) | covarianza de d_i·(λ_i f + u_i), sin el ε de regularización (1e-4) | ε es regularización numérica, no parte de la tasa |
| M2-8 | Ĝ de un mes anterior a 1968-06 (M3, Platt) | NaN | antes de la ventana de datos del factor no hay nowcast |
| M2-9 | tabla v(edad): qué fechas y meses | fechas de decisión de la matriz PIT ≤ 2004-12 en que la serie entra desde una vintage; todos los meses observados de esa vintage ≤ 2004-12 (el tramo ≥ 13 incluye todos los meses antiguos) | lectura literal de §4; los tramos usados en la práctica son los de edad 1-3 |
| M2-10 | V_conj (v1.3) en pseudo-tiempo-real | `from_vintage` = falso en los niveles pseudo (la revisión va aparte, en V_rev); meses s con Ĝ^ps no finito se excluyen; ℓ_i del corte T para todos los s (escrito en la spec) | evita contar dos veces la revisión |
| M2-11 | `m2_struct_g_platt`: con qué P se ajusta la capa en los meses de entrenamiento | P en tiempo real de cada mes de entrenamiento (fecha de decisión de s, parámetros vigentes en el corte), como la emisión de M3; meses sin P (antes de 1968-06) fuera; `B.fit_binary_logit` como M0 | única P disponible que respeta el "todo ≤ corte" sin reajustar el pasado |
| M2-12 | `m2_struct_g_coinc`: variables de la ventana del eje | las mismas que la principal (`claims_4w_yoy`, `philly_neworders`) para la ventana y la elegibilidad; el factor no las usa | así la sensibilidad cambia solo el factor (misma muestra) |

## M3 (`m3_tvtp_spec.md` v1.2)

| # | punto abierto | elección | justificación |
|---|---|---|---|
| M3-1 | estandarización de z ("media y desviación del entrenamiento") | sin ponderar, ddof 0, filas de entrenamiento del corte; un z que falte en un mes del filtro (fuera del entrenamiento) = 0 | la spec no pide ponderar; el 0 es la media, como la imputación del arnés |
| M3-2 | α de arranque ("logit de la frecuencia") | frecuencia ponderada de salida, recortada a [1e-3, 1 − 1e-3] | coherente con la logística ponderada; el recorte evita ±∞ |
| M3-3 | gradiente | analítico en las logísticas y la calibración | forma cerrada exacta |
| M3-4 | mes del filtro sin emisión finita | solo predicción, sin actualización | el filtro estándar con un dato que falta |
| M3-5 | `_fac` "estandarizado" | media y desviación de los meses de entrenamiento | indiferente: la emisión gaussiana con μ_k, ω estimadas es invariante |
| M3-6 | estados sin ningún mes con emisión finita | error explícito (no NaN silencioso) | con ≥ 8 cambios de G no ocurre |

## Pool (`pool_spec.md` v1.2)

| # | punto abierto | elección | justificación |
|---|---|---|---|
| P-1 | gradiente del MAP | numérico de scipy (diferencias finitas por defecto) | la derivada de la beta regularizada respecto de a y b no tiene forma cerrada sencilla |
| P-2 | recorte dentro del objetivo | P se recorta a [1e-6, 1 − 1e-6] | el de la predicción |
| P-3 | variantes `_eq`, `_lin`, `_kull`, `_unif` antes de N_min | conservan el arranque (= M0 si |S| < 60) | la spec solo cambia lo que nombra |
| P-4 | `_kull` "sobre el pool lineal MAP" | dos pasos: pesos como `_lin`, después la beta de Kull MAP (c, ln a, ln b ~ N(0; 0,5²)), L-BFGS-B 500 / 1e-8, arranque c = 0, a = b = 1 | lectura literal; la BLP principal es la conjunta |
| P-5 | eje I del pool | ajuste propio idéntico a M0 (mismos datos y parámetros) | da bit a bit el eje I de M0 |

## Arnés v2.4 (`harness.md` §11)

| # | punto abierto | elección | justificación |
|---|---|---|---|
| H-1 | "estables" del estudio de eventos (pool §5b) | el corte `estable` del arnés (etiqueta dura oficial t = t − 5) | ya es la definición de estable de los criterios 3-4 |
| H-2 | 3 m × 80/20: tasa de declaraciones falsas | por año de meses de la ventana puntuada | la spec dice "por año" sin más |
| H-3 | barrera de los niveles PIT en la predicción con refit > 1 | ≤ la fecha de decisión de la última fila del bloque (cada fila usa la suya) | como las filas de la matriz del bloque; con refit 1 es la del corte |
| H-4 | `sd_mensual` | ddof = 1 | como `power.py` (`power_holdout.md` §4) |
| H-5 | registro de accesos de los niveles PIT | una línea por modelo y corrida en el registro completo (llamadas, fecha máxima), no por llamada | los niveles no son la etiqueta; evita miles de líneas |
| H-6 | caché compartida M2-M3 | motor por (identidad de los datos, modo, factor), versiones por (corte, versión previa), nowcasts por (versión, mes) | "una sola implementación, misma caché" (M3 §4); los placebos usan una clave distinta de las corridas reales |
