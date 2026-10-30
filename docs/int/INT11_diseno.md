---
documento: INT-11 — motor de escenarios probabilístico (diseño + potencia)
version: 0.1 (2026-10-30)
estado: DISEÑO + ESQUELETO. Ningún modelo evaluado con datos reales; ningún indicador cruzado con resultados futuros.
codigo: src/intl/escenarios.py (generador e interfaz), src/intl/int11.py (proceso sintético de potencia),
        scripts/int11_potencia.py, tests/test_intl_int11.py (sintéticos), tests/sint_int11.py
potencia: research/int/int11_potencia.json (commit 6f3352c, árbol limpio)
prerregistro: borrador docs/int/INT11_prerregistro_v0.md
depende_de: Atlas §8 (régimen operable), INT-4 (termómetro), INT-6 (X1 contagio), INT-7 (valoración), INT-9 f1 (F1/F2)
---

# INT-11: un generador de escenarios que habla en probabilidades

## 0. En una frase
Dado **dónde estamos hoy** (régimen de inflación × crecimiento observable a tiempo), el motor genera miles de
**trayectorias posibles** de 1 a 5 años para bolsa, bonos, letras, vivienda y oro (rentabilidades **reales**),
remuestreando lo que pasó en 14 países y 130 años cuando se estaba en una situación parecida, y añadiendo la duda sobre
los propios parámetros. De ahí salen **abanicos** ("la bolsa real a 1 año está entre X e Y con un 90 %"),
**probabilidades** ("caída > 20 % a 1 año: p [IC de parámetros]") y la tabla **"qué activo gana en qué régimen"** con su incertidumbre.
No hay predicción puntual en ninguna parte.

**Idea clave para aprender:** un pronóstico de distribución se juzga por dos cosas: **calibración** (si digo 90 %,
¿acierta el 90 % de las veces?) y **finura** (¿son mis abanicos más estrechos / mejor centrados que los de alguien que
no sabe nada del régimen?). El CRPS mide las dos a la vez; la cobertura mide la primera.

## 1. Arquitectura

```
 estado hoy (país c, fin del año t)                     incertidumbre de parámetros (por LOTE de trayectorias)
 ├ régimen operable s_t  (inflación obs. > 3 % × brecha P3 < 0)    ├ matriz de transición ~ posterior Dirichlet
 ├ [opcional] régimen mundo w_t (mayoría de países)                └ pesos de bootstrap bayesiano por AÑO histórico
 └ [opcional M2] termómetro, F1/F2, D/P → "inclinación" del 1.er año
        │
        ▼  año h = 1 … H
 transición   s_{t+h−1} → s_{t+h}        Markov del país, encogido hacia el panel (κ por Bayes empírico)
        │                                (con contagio: primero el mundo w, luego el país dado w)
        ▼
 rentabilidades del año t+h   ← fila país-año histórica de la celda (s_prev, s) = (s_{t+h−1}, s_{t+h})
        │                       · bloque estacionario: si la fila siguiente del mismo país casa con el régimen
        │                         simulado, se sigue con ella (prob. 1 − 1/L, L = 3) → conserva rachas y autocorrelación
        │                       · credibilidad: fila del país propio con prob. n_c/(n_c + 40); si no, del panel
        │                       · huecos (oro < 1972, vivienda) → donante de la misma celda
        │                       · alternativa paramétrica: t multivariante (ν = 5) por celda, encogida al pool
        ▼
 trayectorias (P × H × activos) + inflación + crecimiento + régimen  →  abanicos, probabilidades, tabla de regímenes
```

### 1.1 Estado: por qué el régimen OPERABLE y no la etiqueta ex post
La etiqueta de INT-1 usa ventanas centradas (mira 5 años al futuro): no sirve para decidir hoy. El motor usa la versión
del Atlas §8, la única que se puede conocer a tiempo: **inflación observada del año > 3 %** y **brecha P3 < 0**
(log PIB pc − media de los 10 años anteriores). Es también la definición con la que se obtuvo el único resultado
operable que pasa Holm (bolsa en estanflación observada ≈ −12 pp).

**Consecuencia medida (solo X, `research/int/int11_potencia.json`):** con P3 la brecha es negativa solo en el 5,6 % de
los país-años (el PIB crece, así que estar por debajo de la media de los 10 años anteriores exige una caída fuerte).
Frecuencias: expansión 55 %, sobrecalentamiento 39 %, **estanflación 1,7 %**, **crecimiento bajo 3,9 %**. Es decir, con
P3 el eje "crecimiento" funciona como un detector de **contracciones serias**, y el régimen es sobre todo
"inflación alta o no". La alternativa "crecimiento del año < media de los 10 anteriores" (`eje="tendencia"`) reparte
33/20/21/26 % pero es mucho menos persistente (0,46 frente a 0,74). **Decisión del usuario D1** (§8).

### 1.2 Transiciones: Markov por país con encogimiento jerárquico
- Recuentos de transiciones s_{t−1} → s_t por país. La fila del país c se modela como
  `P_c(·|i) ~ Dirichlet(κ · P_panel(·|i))`. Posterior: `recuentos_c + κ · P_panel`.
- **κ por Bayes empírico** (máxima verosimilitud Dirichlet-multinomial en una rejilla): si los países se parecen, κ sale
  grande y todos se acercan al panel; si difieren, κ sale pequeño y cada uno conserva lo suyo. Lo decide el dato de X,
  no el analista.
- **Contagio (X1)**, opcional (`contagio=True`): se simula primero un régimen **mundo** (mayoría de países con
  inflación > 3 % / con brecha < 0; Markov propio) y la transición del país se condiciona al mundo del año siguiente:
  `P_c(·|i, w) ~ Dirichlet(κ_w · P_panel(·|i, w))`, con `P_panel(·|i, w)` encogido a su vez hacia `P_panel(·|i)`. Es la
  vía para que un "mundo en inflación" arrastre al país (lo que X1 estableció para las recesiones).
- **Incertidumbre:** cada lote de trayectorias usa una matriz sorteada del posterior. Con pocas transiciones (los
  estados raros) el sorteo varía mucho → abanicos más anchos donde sabemos menos.

### 1.3 Rentabilidades: bootstrap por bloques emparejado por régimen
- **Por qué remuestrear filas reales y no un modelo:** las colas de la bolsa son muy gruesas (curtosis en exceso ≈ 17
  de los residuos frente al año) y la relación entre activos cambia por régimen. Una fila país-año real trae **a la
  vez** bolsa, bonos, letras, vivienda, oro, inflación y crecimiento: conserva la dependencia conjunta sin modelizarla.
- **Celda (s_prev, s):** se condiciona al régimen conocido al empezar el año (lo que sabíamos) **y** al régimen
  simulado al acabarlo (coherencia: si la trayectoria dice "inflación alta", la inflación sorteada pasa del 3 %).
  Si una celda tiene < 25 filas (las de estanflación), respaldo jerárquico: (s_prev, mismo lado de la inflación) →
  (s_prev, ·) → (·, s) → todo. Se conserva primero lo que se sabía a tiempo.
- **Bloques estacionarios (Politis-Romano):** con probabilidad 1 − 1/3 el año siguiente se toma de la **misma
  historia** (país, año + 1) si su régimen casa con el simulado. Así un sorteo de "1973 en el R. U." puede seguir con
  "1974 en el R. U.": las rachas malas y la reversión se conservan.
- **Encogimiento entre países (credibilidad de Bühlmann):** para el país c, con probabilidad n_c/(n_c + k) se usa una
  fila suya y si no una del panel (k = 40 por defecto). Un país dejado fuera recibe el panel puro.
- **Incertidumbre de parámetros:** pesos de **bootstrap bayesiano por año histórico** (Dirichlet(1) por año, el mismo
  peso para todos los países de ese año): respeta que los países de un mismo año no son independientes.
- **Alternativa paramétrica (`modo="t"`):** por celda, media y covarianza ponderadas (log-rentabilidades), covarianza
  encogida hacia la del pool (n0 = 30), t multivariante ν = 5. Sin bloques. Útil como sensibilidad y para colas
  más allá de lo observado.
- **Huecos:** el oro solo tiene sentido desde 1972 (precio fijo antes; Atlas §5.4): antes, el valor del oro se toma de
  un donante de la misma celda. Declarado: rompe parte de la dependencia oro-resto en esos sorteos.

### 1.4 Modulación M2 (termómetro, F1/F2, valoración): solo el primer año
Las covariables continuas (probabilidad de recesión del termómetro, F1, F2, D/P) no se simulan hacia delante. Se usan
como **inclinación** del primer año: las filas históricas cuyo valor de t − 1 se parece al de hoy pesan más (núcleo
gaussiano, ancho fijado de antemano) y la primera transición se reescala por la razón "núcleo medio en la celda /
núcleo medio en la fila". Del año 2 en adelante el modelo vuelve a M1. Justificación: INT-9 e INT-7 muestran que estos
efectos, si existen, son pequeños (MDE 4-5 pp por dt en bolsa); añadir dimensiones al condicionamiento dispersa celdas
que ya son pequeñas.

## 2. Interfaz para otro modelo (Monte Carlo)

```python
from src.intl import escenarios as E
filas = E.preparar_filas(df, activos=E.ACTIVOS, covariables=("termometro", "F1"), excluir=E.GUERRAS)   # ≤ 2004
gen = E.Generador(E.Config(modo="bootstrap", contagio=False, k_pais=40, bloque_medio=3)).ajustar(filas)
esc = gen.simular("ESP", estado="sobrecalentamiento", horizonte=5, n_lotes=200, por_lote=100, semilla=1,
                  inclinacion={"termometro": (0.62, 0.5)})          # opcional (M2)
esc.abanico()                       # p5 … p95 por activo y horizonte (acumulada, anualizada o anual)
esc.prob_caida("bolsa", -0.20, h=1) # {"p": …, "ic90": (…, …)}
esc.prob_inflacion(0.05, h=2)       # inflación > 5 % en algún año de los 2 próximos
esc.prob_regimen(h=1)
gen.tabla_regimenes("ESP")          # qué activo gana en qué régimen, con IC
esc.a_tabla(); esc.guardar("ruta")  # parquet largo + json de metadatos
```

**Formato de salida (`Escenarios`):** `rent` (P, H, A) rentabilidad **real simple** anual en fracción, moneda local;
`inflacion`, `crecimiento` (P, H) en Δlog; `regimen` (P, H) régimen del país al final de cada año (0 expansión,
1 sobrecalentamiento, 2 estanflación, 3 crecimiento bajo); `mundo` (P, H) o None; `lote` (P,) índice del sorteo de
parámetros (las trayectorias del mismo lote comparten parámetros); `meta` (versión, país, estado inicial, semilla,
configuración completa, κ, años del pool). En tabla larga: `trayectoria, lote, h, regimen, [regimen_mundo], inflacion,
crecimiento, bolsa, bonos, letras, vivienda, oro`. **Contrato para el modelo consumidor:** (1) cada trayectoria es un
escenario equiprobable; (2) para separar riesgo de "mala suerte" del de "no conocer los parámetros", agrupar por
`lote`; (3) nada de esto es un pronóstico puntual: usar cuantiles y probabilidades.

**IC de las probabilidades:** la probabilidad es la media de todas las trayectorias (predictiva posterior). El IC 90 %
mide **solo la parte de parámetros**: varianza entre lotes menos el ruido Monte Carlo binomial (método de momentos).
Si sale degenerado (anchura 0) es que el ruido de simulación domina: subir `por_lote`.

## 3. Qué activo gana en qué régimen (cómo se presentará)
`tabla_regimenes(pais)` simula un año desde cada régimen conocido y da, por activo: media, p10/p50/p90, P(ser el
mejor de los 5), P(< 0), con IC de parámetros. Es la versión probabilística del Atlas: en lugar de "efecto −12 pp
[IC]" dirá "en estanflación observada, la bolsa real del año siguiente suele estar entre X e Y (p10-p90); es el peor
activo con prob. Z". **No se ha calculado con datos reales** (sería mirar resultados por régimen); se calculará una sola
vez tras congelar el prerregistro, y su lectura heredará la contaminación del Atlas (§5).

## 4. Potencia (simulación; ningún resultado real cruzado con el estado)
`scripts/int11_potencia.py` (commit 6f3352c, árbol limpio, 2026-10-30T08:09Z, 300 réplicas por punto) →
`research/int/int11_potencia.json`.

### 4.1 Qué se midió del dato real (por separado) y cómo se generan los paneles falsos
| | medido (≤ 2004, 14 países, sin guerras ni hiperinflación) |
|---|---|
| X: inflación > 3 % | frecuencia 41 %, persistencia 0,77, concordancia entre países 0,42 |
| X: brecha P3 < 0 | frecuencia 5,6 %, persistencia 0,95, concordancia 0,15 |
| X: regímenes | exp. 55 %, sobrecal. 39 %, estanfl. 1,7 %, crec. bajo 3,9 %; diagonal media de la matriz de transición 0,74 |
| Y: bolsa (log real) | media 5,1 %; dt común (entre años) 11,8 pp; propia 17,1 pp; curtosis en exceso 17 (ν = 4,5) |
| Y: bonos / letras / vivienda | dt común 6,6 / 3,3 / 2,2 pp; propia 7,5 / 4,6 / 8,7 pp |
| Y: oro (≥ 1972) | dt común 20,0 pp, propia 6,3 pp (es casi un único precio mundial) |

Generador sintético: dos latentes AR(1) por país (inflación, brecha) con componente común, calibrados para reproducir
frecuencia, persistencia y concordancia; rentabilidades = media + efecto del régimen **conocido** s_{t−1} + choque común
del año + choque propio, t multivariante con la correlación entre activos medida; mismos huecos que el panel real.
Efecto plantado = **δ × tamaños del Atlas §8** (bolsa: −3 sobrecal., −12 estanfl.; bonos −6 y letras −5 con inflación
alta; vivienda −3 en estanfl. [supuesto]; oro 0). δ = 1 es probablemente **optimista** (maldición del ganador).
Modelos: M0 = distribución empírica incondicional del panel; M1 = distribución empírica por régimen conocido.
Contraste: Diebold-Mariano del CRPS normalizado por activo (media de 5), años como conglomerados, α = 0,05/3 unilateral.

### 4.2 CRPS: ¿se puede demostrar que el régimen mejora las distribuciones?
| diseño | potencia δ = 0,5 | δ = 1 | δ = 1,5 | δ con 80 % | CRPSS medio en ese δ | solo bolsa (δ = 1,5) |
|---|---|---|---|---|---|---|
| C1 dejando un país fuera, h = 1 (≤ 2004) | 0,54 | 1,00 | 1,00 | **0,65** | **1,3 %** | 0,19 |
| C1 temporal ≤ 1949 → 1950-2004, h = 1 | 0,21 | 0,79 | 0,98 | 1,04 | 3,4 % | 0,11 |
| C2 dejando un país fuera, h = 5 | 0,02 | 0,25 | 0,59 | — | — | 0 |
| C2 temporal, h = 5 | 0,01 | 0,13 | 0,24 | — | — | 0,02 |
| bloqueado 2005-2020 (18 países), h = 1 | 0,10 | 0,40 | 0,72 | — | — | 0,09 |
| bloqueado 2005-2020, h = 5 | 0,01 | 0,03 | 0,04 | — | — | 0,03 |

Lectura en llano:
1. **La mejora que se puede esperar es pequeña en CRPS** (1-3 %, aunque los efectos sean del tamaño del Atlas): el
   régimen mueve el centro unos pocos pp y la dispersión de un año es de 20 pp. Es normal en finanzas; no es un fallo.
2. **La potencia viene de bonos y letras** (CRPSS 4 % y 9 % con δ = 1); **la bolsa sola no se puede demostrar nunca**
   (CRPSS < 1 %, potencia ≤ 0,19 incluso con δ = 1,5). Lo que digamos de la bolsa por régimen será descriptivo.
3. **A 5 años no hay potencia** en ningún diseño (pocas ventanas independientes: ≈ 25 por país en 130 años).
4. **El periodo bloqueado tiene poca potencia para el CRPS** (0,40 con δ = 1).
5. Con ≤ 2004 sí hay potencia, pero esa muestra está **contaminada** por el Atlas (§5): sirve para desarrollar.

### 4.3 Cobertura: ¿se puede detectar que los abanicos están mal calibrados?
Intervalo nominal p5-p95 (90 %). Modelo con anchura escalada para que su cobertura real sea 0,90, 0,85 u 0,80.

**Hallazgo de método importante:** el contraste t con años como conglomerados **rechaza un 12-30 % de las veces cuando
el modelo está bien calibrado** (debería ser 5 %): con colas gruesas y choques comunes, los fallos llegan en racimos
(un 2008 hace fallar a todos los países a la vez). Solución: **valor crítico simulado con el propio generador** (bajo
H0 el generador dice cómo de variable es la cobertura en una muestra así). Con él el tamaño vuelve al 5 %:

| diseño (h = 1) | detectar 80 % frente a 90 %: bolsa / 5 activos | detectar 85 %: bolsa / 5 activos | cobertura de una muestra calibrada (p5-p95 entre réplicas, 5 activos) |
|---|---|---|---|
| 1950-2004 (14 países) | 0,98 / 1,00 | 0,57 / 0,69 | 0,87-0,92 |
| bloqueado 2005-2020 (18 países) | 0,74 / **0,95** | 0,21 / 0,27 | 0,85-0,93 |
| en vivo 5 años (18 países) | 0,21 / 0,51 | 0,06 / 0,15 | 0,82-0,95 |
| en vivo 10 años | 0,54 / 0,87 | 0,15 / 0,26 | 0,85-0,94 |
| en vivo 20 años | 0,92 / 0,99 | 0,37 / 0,47 | 0,86-0,92 |

A h = 5 solo el diseño 1950-2004 con los 5 activos llega a 0,60 (80 % frente a 90 %); el bloqueado y el vivo, < 0,35.
**Lectura:** la calibración a 1 año **sí se puede comprobar** (una infracobertura seria, 80 % en lugar de 90 %, se ve en
el bloqueado con un 95 % de probabilidad y en vivo en ≈ 10 años); una infracobertura leve (85 %) no. La calibración a 5
años no se puede comprobar con los datos que existen.

### 4.4 Simplificaciones declaradas
Latentes de inflación y brecha independientes entre sí; el mismo choque t para todos los activos; estacionariedad
(2005-2020 y el vivo se generan con el mismo proceso que 1876-2004); M1 en la potencia es la distribución empírica por
régimen (no el motor completo con bloques e incertidumbre de parámetros, que debería calibrar algo mejor); k de la
cobertura calibrado en un diseño (18 países, 40 años) y aplicado a todos (de ahí 0,86-0,90 de media en el escalón
"0,90" según el diseño). El efecto de M2 (inclinación) no se simuló: INT-9 ya da su MDE en bolsa (≈ 4,5 pp por dt).

## 5. Contaminación y lo que NO se puede afirmar
- El Atlas §8 ya cruzó el régimen operable con las rentabilidades de 1876-1999 (14 países). Cualquier evaluación de
  M1 con datos ≤ 2004 **no es confirmatoria**: sabemos de antemano que bonos/letras/bolsa caen con inflación alta.
  Con ≤ 2004 solo se puede comprobar la **calibración** (¿los abanicos tienen la anchura correcta?) y la mecánica.
- La confirmación de "el régimen mejora la distribución" solo puede venir de datos no vistos: el periodo bloqueado
  2005-2020 o la evaluación en vivo.
- Moneda local, sin costes ni impuestos, datos anuales revisados (no "as of" para el PIB histórico), 14 países ricos.
- El motor es **de un país**: las trayectorias de dos países no salen coherentes entre sí (v2: sorteo conjunto del
  mismo año histórico para todos los países, que conserva la correlación entre países).
- Estacionariedad: supone que la relación régimen → activos de 1876-2004 sigue valiendo.

## 6. Próximos pasos
1. Decisiones del usuario (prerregistro §8).
2. Congelar el prerregistro v1 (con los números de §4).
3. Corrida única de desarrollo (calibración ≤ 2004, LOCO y temporal) → tabla de regímenes y abanicos de hoy.
4. Conectar al reporte semanal como sección informativa (como INT-8b) y empezar el registro en vivo.
