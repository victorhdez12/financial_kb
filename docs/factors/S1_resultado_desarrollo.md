---
documento: S1 «rotación de sectores por régimen macro»: resultado de la corrida ÚNICA de desarrollo (≤ 2004)
version: 1.0 (2026-11-19)
estado: corrida hecha una sola vez, sin re-corridas. **NO PASA** el criterio §5 (falla a, b y c; pasa d).
spec: docs/factors/S1_rotacion_sectorial_spec.md v1.0 CONGELADA (commit 7a0b1a3); ningún parámetro de diseño cambiado
codigo: src/factors/data.py (industrias12_dev, mercado_dev), src/factors/s1.py, scripts/s1_senal.py, scripts/s1_desarrollo.py
datos: research/factors/s1_senal.{csv,json} (señal, fijada antes: commit 199e639), research/factors/s1_desarrollo.json (resultado: commit 3f42b83)
---

# S1: resultado del desarrollo (1950-02 → 2004-12)

## 0. En una frase
La inclinación por sectores según el cuadrante **no añade nada que no dé cualquier secuencia de cuadrantes con la misma
frecuencia**: S1 queda en la mediana de los placebos (mejor que el 50 %), con un ratio de información de 0,04 y la
primera mitad en negativo. **No entra en Alpaca como candidata.** El usuario decide si se lleva como **observación**
(«falló en desarrollo») o se cierra la línea. No se ajusta la regla: cualquier S1 v2 es una prueba nueva (N = 2).

## 1. Cronología (lo que se fijó antes de mirar)
| paso | commit | qué |
|---|---|---|
| spec congelada | 7a0b1a3 | regla, sectores, 50/50, costes, listón, placebos, criterios |
| datos + script de señal | d8e665d | 12 industrias con corte ≤ 2004 (warehouse y zip, cuadran al céntimo); sin rentabilidades |
| **señal y periodo fijados** | **199e639** | cuadrante PIT 1950-01 → 2004-12 (sha256 `53877fce…`), puntuación 1950-02 → 2004-12, placebos 1 000 × bloques de 12, semilla 20261119 |
| motor + tests sintéticos | 501a238 | src/factors/s1.py, tests/test_s1_motor.py; sin correr con datos reales |
| **corrida única** | **3f42b83** | research/factors/s1_desarrollo.json, tal cual salió |

## 2. Señal (propiedades; se miraron antes de calcular rentabilidades)
- **Código:** el mismo que corre en vivo (`make regime` → `src.regime.run`): `src.regime.features.build_panel` +
  `src.regime.run.classify_all` (`src/regime/classify.py`), con la rejilla cortada en 2004-12-31. Coincide **mes a mes**
  con la tabla viva `regime_monthly` (0 meses distintos en 1950-01 → 2004-12).
- **Modo PIT:** 608 meses `mixed` (parte de las entradas de G/I con vintage ALFRED, el resto última vintage con retraso
  de publicación), 52 `alfred` (desde 2000-08). Ningún mes sin cuadrante.
- **Periodo:** el primer cuadrante del código en vivo es 1950-01 (la tabla viva empieza en `START` = 1950-01-31); rige
  la rentabilidad de 1950-02. Las industrias existen desde 1926-07, no limitan. Final 2004-12 (corte).

| cuadrante (meses que gobiernan 1950-02 … 2004-12) | % del tiempo | duración media |
|---|---|---|
| Goldilocks | 18,1 % | 4,3 meses |
| Reflación | 13,4 % | 4,0 |
| Estanflación | 32,5 % | 5,6 |
| Deflación/recesión | 36,1 % | 5,7 |

129 cambios de cuadrante (2,35 al año; 130 operaciones de S1 contando la inclinación inicial). Cuadrantes por año:
`research/factors/s1_senal.json` y `s1_desarrollo.json` (`por_año`).

## 3. Resultado (neto de costes; USD; mensual, anualizado)
| | S1 | L0 (mercado) |
|---|---|---|
| rentabilidad anual (compuesta) | **12,17 %** | 11,89 % |
| volatilidad | 13,90 % | 14,74 % |
| Sharpe (frente a `ff_rf`) | 0,55 | 0,51 |
| caída máxima | −46,9 % | −46,5 % |
| rotación anual (½·Σ\|Δw\|) | 81 % | 0 |
| coste anual | 0,16 % | 0 |

| activa S1 − L0 | valor |
|---|---|
| aritmética anualizada (neta / bruta) | **+0,13 %** / +0,29 % |
| geométrica (diferencia de rentabilidades compuestas) | +0,28 % |
| error de seguimiento | 2,97 % |
| **ratio de información** | **0,04** |
| placebos (1 000, bloques de 12 m): mediana / p90 / p95 de la activa | +0,13 % / +0,53 % / +0,61 % |
| **S1 mejor que** | **50,1 % de los placebos** (p conservador 0,50) |

| mitad | meses | activa aritmética | activa geométrica | IR |
|---|---|---|---|---|
| 1950-02 → 1977-07 | 330 | **−0,13 %** | −0,06 % | −0,05 |
| 1977-08 → 2004-12 | 329 | +0,39 % | +0,63 % | 0,11 |

Por década (rentabilidad acumulada S1 / L0): 1950s 426 % / 429 %; 1960s 122 % / 121 %; 1970s 79 % / 80 %;
1980s 412 % / 376 %; 1990s 429 % / 423 %; 2000-04 −2,8 % / −8,7 %.

## 4. Criterios §5 (todos necesarios)
| criterio | listón | S1 | |
|---|---|---|---|
| a) activa neta > 0 **y** IR ≥ 0,20 | > 0 y ≥ 0,20 | +0,13 % (geo +0,28 %), **IR 0,04** | ❌ |
| b) mejor que el 90 % de los placebos (p ≤ 0,10) | p ≤ 0,10 | mejor que el 50,1 %, p 0,50 | ❌ |
| c) activa ≥ 0 en cada mitad | ≥ 0 y ≥ 0 | **−0,13 %** / +0,39 % | ❌ |
| d) caída máxima no peor que L0 en más de 5 pp | ≥ −51,5 % | −46,9 % (0,3 pp peor) | ✅ |

**Veredicto: NO PASA.** Ninguna de las lecturas resueltas en §5 cambia el veredicto: a) falla por el IR con cualquier
definición de la activa; b) falla con cualquier forma de calcular el percentil; c) la primera mitad es negativa en
aritmética y en geométrica.

Lectura (informativa, no decide nada): la pequeña ventaja y la menor volatilidad vienen de la **estructura estática**
de la regla (≈ 69 % del tiempo en Estanflación o Deflación/recesión → sobrepeso fijo en NoDur, Hlth y Utils), no del
momento: los placebos, con la misma frecuencia de cuadrantes, ganan lo mismo (mediana +0,13 %). Activa por cuadrante
vigente: Goldilocks −0,86 %/año, Reflación +1,35 %, Estanflación +0,18 %, Deflación/recesión +0,13 %. **No** se usa
para retocar la regla (eso sería S1 v2, N = 2, contaminada por esta tabla).

## 5. Ambigüedades resueltas (lectura conservadora; decididas en el código antes de la corrida, commit 501a238; la cifra de cambios de los placebos se conoció con la corrida)
1. **«Base PIT v0.4» frente a «el mismo código que corre en vivo».** La matriz v0.4 (`src/features/pit.py`) no contiene
   las entradas del clasificador con sus transformaciones (`indpro_yoy`, `payems_yoy`, `unrate_d12`, `sahm`,
   `core_6m`…: la v0.4 usa otras, p. ej. 3 m anualizadas), así que alimentar `classify.py` con ella exigiría inventar
   transformaciones (señal improvisada, prohibida por §1). Se usa la capa PIT **del propio código en vivo**
   (`src/regime/asof.py`: vintages ALFRED del warehouse donde existen; si no, última vintage con retraso de
   publicación), que es la que cumple «mismo código» y sigue el mismo principio de la spec. **A revisar por el Validador.**
2. **Inicio del periodo:** el primer cuadrante que publica el código en vivo (recorte `START` de `src/regime/run.py`,
   1950-01), no el primero que el clasificador podría calcular antes de 1950 con la rejilla desde 1947.
3. **Entre cambios de cuadrante no se rebalancea** (§3 «cambio solo cuando cambia el cuadrante»): los pesos derivan con
   los precios; en cada cambio se vuelve a 50 % mercado + 4 × 12,5 % exactos.
4. **Costes:** «10 pb por lado» = 10 pb sobre lo comprado y 10 pb sobre lo vendido: coste = 10 pb × Σ|Δw| =
   20 pb × rotación (como `src/factors/backtest.py` de P-DEV-FACT). Se cargan en el primer mes con los pesos nuevos, y
   la inclinación inicial desde L0 (100 % mercado) también paga.
5. **Rentabilidad activa:** se exige > 0 (≥ 0 en las mitades) **a la vez** en aritmética anualizada (la del IR) y en
   geométrica; el IR = activa aritmética / error de seguimiento.
6. **Placebos:** se baraja la secuencia de cuadrantes de las fechas de decisión del periodo (1950-01 … 2004-11, 659
   meses) en 55 bloques consecutivos (54 de 12 y el último de 11), permutando su orden; la frecuencia de cada cuadrante
   se conserva exacta; los cambios, no del todo (en las fronteras de bloque aparecen cambios nuevos: 154,5 operaciones
   de media frente a 130 de S1, ≈ +0,03 pp/año de coste más en los placebos, lo que **favorece a S1**; falla igual).
   p = (1 + #placebos ≥ S1)/(N + 1).
7. **Mitades:** los ⌈659/2⌉ = 330 primeros meses y los 329 restantes, de la misma corrida continua (no se reinicia).
8. **Núcleo:** `ff_mkt` (aproximación que da la spec); L0 sin costes ni TER.

## 6. Límites
- **Potencia:** con un error de seguimiento del 3 % y 55 años, una activa de +0,13 %/año tiene t ≈ 0,3; un efecto 5 veces
  mayor daría t ≈ 1,6. El resultado es «sin evidencia», no «evidencia en contra».
- **PIT imperfecto:** hasta 2000 los meses son `mixed` (parte de las entradas con datos revisados); el IPC subyacente
  antes de 1957 usa el general. El diseño del clasificador conoce datos posteriores a 2004 (Sahm, 2 %).
- **Literatura solapada** (Merrill Lynch 2004, Stovall): la asignación régimen → sectores se escribió con datos que
  incluyen nuestro periodo; aun así no supera a los placebos.
- Industrias de Ken French con la vintage CRSP 202609 (revisadas); los ETF del vivo (§6 de la spec) no son las
  industrias French (XLC, XRT, XLK declarados).
- Esta tabla (activa por cuadrante y por década) **contamina** el periodo ≤ 2004 para cualquier S1 v2.

## 7. Qué debe revisar el Validador
1. La resolución de la ambigüedad 1 (capa PIT del código en vivo en vez de la matriz v0.4): ¿cumple §1?
2. Reproducción: `.venv/bin/python -m scripts.s1_senal` (debe dar el mismo sha256 `53877fce…` y 0 meses distintos de
   `regime_monthly`) y `scripts.s1_desarrollo --recorrida "reproducción del Validador"` en una copia (debe dar las
   mismas cifras; los placebos son deterministas con la semilla).
3. Cronología del motor (`tests/test_s1_motor.py`): cuadrante de t → pesos de t + 1, deriva, costes, «sin cuadrante →
   mantener», ningún dato ≥ 2005 (`tests/test_s1_datos.py`).
4. Que el placebo con más cambios que S1 (ambigüedad 6) no cambia el veredicto.
