---
documento: cálculo de potencia de la evaluación única (P-EVAL-BASE v4)
version: 1.2 (2026-10-25: §6 nuevo con la potencia del pool real y del criterio de P-EVAL-BASE v4.3; §1-§5 sin cambio, quedan como historia con el ruido de M1). 1.1: solo texto; tamaño como cota inferior, Validador M-3; decisión del IC ya tomada, B-9
fecha: 2026-10-24
codigo: src/models/power.py (§1-§5); tests/validation/potencia_holdout_{comun,reducida,estructural}.py (§6)
resultados: research/trials/power_holdout.json (§1-§5; una pasada, 1.000 evaluaciones ficticias por punto); research/validation/potencia_holdout/*.json (§6; 2.000 réplicas por celda)
datos: solo desarrollo ≤ 2004 (diferencias de log-loss de corridas ya registradas) + la LONGITUD pública del bloqueado (202 meses)
depende_de: harness.md v2.3 (§6, bootstrap del arnés), p_eval_base_draft.md v3 §A3 (criterios), decisión del usuario 24-oct (pool, Holm k = 1)
---

# Potencia de la evaluación única

**Pregunta.** Con 202 meses (2005-01 → 2021-10) y el contraste del arnés, ¿qué mejora media frente a M0 hace falta
para que el contraste principal pase con un 80 % de probabilidad? El contraste principal será el **pool de
log-scores {M0, estructural de G, Markov TVTP eje G} + recalibración beta, con Holm k = 1** (decisión del usuario,
24-oct). Holm k = 2 (dos aspirantes) se mantiene solo como referencia.

**Respuesta corta.** El MDE (efecto mínimo detectable con 80 % de potencia) es de **≈ 0,12-0,15 nats** si el pool tiene
el ruido mensual de M1 v1/v2 y de **≈ 0,07 nats** si el pool reduce ese ruido a la mitad (supuesto, no medido). Pasar de
k = 2 a k = 1 **no cambia casi nada** con el criterio 1 tal y como está escrito: lo que limita es el "límite inferior del
IC 95 % > 0", que ya equivale a p unilateral < 0,025.

## 1. Método

No se ajusta ningún modelo ni se lee nada ≥ 2005. Fuentes: las diferencias mensuales d<sub>t</sub> = ll(M0) − ll(modelo)
en vintage de las corridas de desarrollo registradas el 23-oct (`20261023-111824_m1v2_principal_512ecfcc`,
1989-10 → 2004-12, 183 meses; `20261023-112028_m1v2_long_d6d807d6`, 1978-07 → 2004-12, 318 meses), y la marca de giro
(`month_cuts` sobre la etiqueta oficial ≤ 2004, una lectura de desarrollo registrada en
`research/trials/label_access.jsonl`, 24-oct 11:05).

| fuente | serie d | meses | media dev (giros / estables) | desv. mensual |
|---|---|---|---|---|
| M1v1_total | log-loss 4 cuadrantes, M1 v1 | 183 | −0,019 (−0,160 / +0,023) | 0,303 |
| M1v2_total | log-loss 4 cuadrantes, M1 v2 | 183 | −0,017 (−0,035 / −0,012) | 0,363 |
| M1v1_ejeG | log-loss del eje G, M1 v1 | 183 | +0,013 (−0,019 / +0,023) | 0,227 |
| M1v2_ejeG | log-loss del eje G, M1 v2 | 183 | −0,012 (−0,032 / −0,007) | 0,259 |
| M1v2g_largo | eje G de M1 v2 con el I de M0 | 318 | +0,035 (+0,003 / +0,046) | 0,296 |

Simulación (por fuente):

1. **Nulo:** d<sub>0</sub> = d centrada por separado en giros y en estables (efecto 0 en los dos; se conservan la
   dependencia, las colas y la relación con los giros).
2. **Evaluación ficticia** de 202 meses: bootstrap circular por bloques de 12 de los pares (d<sub>0</sub>, giro). La
   proporción de giros varía de una simulación a otra como en el desarrollo (≈ 23-26 %, ≈ 46-51 meses de giro).
3. **Efecto:** + δ en todos los meses (escenario *uniforme*) o + δ solo en los de giro (*solo giros*).
4. **Contraste del arnés** sobre cada serie ficticia, exactamente `metrics.boot_mean` (bloques de 12, 5.000 réplicas,
   semilla 20261015, IC percentil 95 %, `p_h0` unilateral).
5. **Pasa (k = 1)** si criterio 1 (media ≥ 0,05 nats y límite inferior del IC 95 % > 0) **y** p < 0,05. **Pasa
  (k = 2, referencia)** si además p < 0,025 (peor caso de Holm: el otro aspirante no pasa).

Potencia = fracción de las 1.000 evaluaciones ficticias que pasan. MDE = efecto medio esperado (sobre los 202 meses)
con potencia 0,80, interpolado en la rejilla (δ de 0 a 0,40 cada 0,02; solo giros, de 0 a 1,6 cada 0,1).

Escenarios de ruido: ×1 (el de la fuente), ×1,5 (colas más gruesas: por ejemplo, la crisis de 2008 y la de 2020) y
×0,5 (**supuesto para el pool**: si el pool pone un peso w fuera de M0, d<sub>pool</sub> ≈ w·d y su desviación ≈ w veces
la de la fuente; con w ≈ 0,5, ruido ×0,5). El pool aún no existe: el ×0,5 es un supuesto, no una medida.

## 2. Supuestos y límites

- La dependencia y las colas del bloqueado son como las de 1978/1989-2004. 2005-2021 tiene dos recesiones grandes
  (2008-09, 2020): el escenario ×1,5 cubre parte de ese riesgo, no todo.
- Los criterios 2-8 de A3 de la v4 (eje G, giros ≥ 0, estables ≥ −0,05, falsas alarmas, subperiodos, Holm, signos de
  M3) no se simulan salvo giros y estables (columna "criterios 1-3", numeración de la v3 en la que se calculó: allí el
  2 era "giros ≥ 0", que es el **3** de la v4); la potencia conjunta real es **menor** que la del contraste.
- La forma del efecto (uniforme o solo en giros) es un supuesto; la realidad estará entre medias.
- **Tamaño empírico:** con δ = 0 el contraste "pasa" en el **≥ 5-9 %** de las evaluaciones con ruido ×1 (nominal: 2,5 %
  por el criterio 1) **si la dependencia de d no pasa de ≈ 12 meses**. El bootstrap por bloques de 12 infraestima algo
  la varianza de la media en 202 meses con esta dependencia; el umbral de 0,05 nats lo contiene en parte. Con ruido
  ×0,5 el tamaño es del 0-1 % (manda el umbral de 0,05).
- **El 5-9 % es una cota inferior** (v1.1; Validador M-3, `docs/validation/2026-10-24_specs_pool_v4.md`). Las
  evaluaciones ficticias se generan con bloques **alineados** de 12 meses de la serie de desarrollo, así que la
  dependencia de d más allá de 12 meses no existe por construcción y el contraste interno (también con bloques de 12)
  solo puede fallar por la parte de ≤ 12 meses. En una simulación sintética del Validador (800 evaluaciones de 202
  meses, t<sub>4</sub>, AR(1)), el tamaño real de "lo > 0" es 4,0 / 5,4 / 9,3 / **19,8 %** con φ = 0 / 0,6 / 0,85 /
  **0,95**, frente a 3,9 / 5,6 / 6,3 / 7,6 % con el generador de este documento. Con la dependencia vista en desarrollo
  (equivalente a φ ≈ 0,7) el 5-9 % es razonable; si d tiene memoria de años, el tamaño real es mayor. Por eso la
  corrida de desarrollo del pool informa la ACF de d en los retardos 1-24 y la sensibilidad de bloques de 24
  (`mejora_logloss_b24`). No se cambia el contraste: la conjunción de criterios y el umbral de 0,05 nats bajan la
  tasa real de falso pase.
- **p de las familias informativas** (secundarias, TVTP frente a CTP): `p_h0 < 0,05` por sí solo pasa con efecto 0 el
  10-15 % de las veces (`p_solo_contraste_holm_k1` del JSON): son liberales, del orden de ×2-3.

## 3. Resultados

### 3.1 MDE (efecto total esperado con 80 % de potencia, nats)

| fuente | uniforme k = 1 | uniforme k = 2 | colas ×1,5 k = 1 | ruido ×0,5 k = 1 | solo giros k = 1 | k = 1 con criterios 1-3 |
|---|---|---|---|---|---|---|
| M1v1_total | **0,128** | 0,128 | 0,190 | 0,072 | 0,130 | 0,130 |
| M1v2_total | **0,147** | 0,147 | 0,220 | 0,075 | 0,137 | 0,155 |
| M1v1_ejeG | **0,097** | 0,097 | 0,146 | 0,068 | 0,111 | 0,098 |
| M1v2_ejeG | **0,125** | 0,125 | 0,187 | 0,070 | 0,119 | 0,126 |
| M1v2g_largo | **0,120** | 0,121 | 0,181 | 0,070 | 0,118 | 0,129 |

Aproximación normal (varianza de largo plazo por bloques, reescalada a 202 meses): error típico de la media 0,037-0,051
nats; MDE 0,09-0,13 (α = 0,05) y 0,10-0,14 (α = 0,025); umbral **observado** del criterio 1 ≈ 0,07-0,10 nats
(= máx(0,05; 1,96·SE)). Coincide con la simulación.

### 3.2 Potencia en función del efecto verdadero (uniforme, k = 1; k = 2 idéntica a ±0,01)

| efecto verdadero | 0 | 0,04 | 0,06 | 0,08 | 0,10 | 0,12 | 0,14 | 0,16 | 0,20 |
|---|---|---|---|---|---|---|---|---|---|
| M1v1_total, ruido ×1 | 0,07 | 0,24 | 0,36 | 0,50 | 0,63 | 0,76 | 0,86 | 0,92 | 0,99 |
| M1v2_total, ruido ×1 | 0,09 | 0,23 | 0,33 | 0,45 | 0,55 | 0,67 | 0,77 | 0,85 | 0,94 |
| M1v2g_largo, ruido ×1 | 0,08 | 0,28 | 0,42 | 0,56 | 0,69 | 0,80 | 0,89 | 0,94 | 0,99 |
| M1v1_total, ruido ×0,5 | 0,01 | 0,35 | 0,67 | 0,89 | 0,98 | 1,00 | 1,00 | 1,00 | 1,00 |
| M1v2_total, ruido ×0,5 | 0,01 | 0,36 | 0,64 | 0,85 | 0,94 | 0,98 | 0,99 | 1,00 | 1,00 |

Solo giros (M1v1_total): δ = 0,4 nats por mes de giro (≈ 0,09 de efecto total) → potencia 0,59; δ = 0,6 (≈ 0,14) → 0,84.

### 3.3 k = 1 frente a k = 2

- Con el criterio 1 **tal como está escrito**, la diferencia es ≤ 0,002 de potencia: el "límite inferior del IC 95 % > 0"
  ya exige p ≈ < 0,025, así que el p < 0,05 de Holm k = 1 no añade nada y el de k = 2 (p < 0,025) casi tampoco.
- La ganancia real de k = 1 sería **cambiar el IC del criterio 1 al 90 %** (límite inferior > 0 ⇔ p < 0,05): el MDE
  bajaría ≈ 0,01-0,03 nats (p. ej. M1v1_total 0,128 → 0,108; M1v2_total 0,147 → 0,120). Es un **cambio de criterio**:
  solo si lo decide el usuario y se preregistra en P-EVAL-BASE v4 como tal (columna `p_k1_ic90` del JSON).
- La ventaja de k = 1 que sí se mantiene: un único contraste, sin elegir a posteriori entre aspirantes.

### 3.4 Criterio de giros ≥ 0 por azar (criterio 2 de la v3 = criterio 3 de la v4)

Con una mejora de 0,10 nats solo en los meses estables (0 en giros), ese criterio se cumple por azar en el 52-54 % de
las evaluaciones: con ≈ 46 meses de giro, ese criterio es casi una moneda al aire si el modelo no mejora en los giros.

## 4. Implicación para el pool

- **Mejora necesaria:** para un 80 % de potencia, el pool tiene que mejorar a M0 en **≈ 0,12-0,15 nats de media** sobre
  202 meses si su diferencia mensual con M0 es tan ruidosa como la de M1, o en **≈ 0,07 nats** si el pool reduce ese
  ruido a la mitad. En el bloqueado, el umbral **observado** para pasar el criterio 1 es ≈ 0,10 nats (≈ 0,05-0,07 con
  ruido ×0,5).
- **Dónde estamos:** el mejor resultado de desarrollo (eje G de M1 v2 en la ventana larga) es +0,035 nats → potencia
  ≈ 0,15-0,20 si ese fuera el efecto real. M1 v1/v2 (≈ −0,02) tienen potencia ≈ tamaño.
- **Qué ayuda al pool:** reducir el ruido de d (la mezcla con M0 y la recalibración lo hacen por construcción) es tan
  importante como subir la media. La spec del pool debería informar a priori la desviación mensual de d en desarrollo
  como métrica, no solo la media.
- **Regla práctica para la corrida de desarrollo del pool** (lectura, no criterio nuevo): si en desarrollo la mejora es
  < 0,05 nats o el IC incluye claramente 0, gastar el bloqueado tiene una potencia baja (< 30 %).
- **Decidido (usuario, 24-oct):** el criterio 1 se mantiene con **IC 95 %** (no 90 %), escrito en P-EVAL-BASE v4
  (A1-9). El análisis de M-3 del Validador refuerza esa decisión.

## 5. Reproducción

```
.venv/bin/python -m src.models.power research/trials/power_holdout.json      # ≈ 15 min, una pasada (24-oct)
```

Semillas fijas (simulación 7; bootstrap 20261015). No se ha iterado sobre los resultados: rejillas, escenarios y
criterios estaban en el código antes de ejecutarlo; el único cambio previo a la ejecución fue adaptar el contraste
principal a k = 1 (decisión del usuario) y añadir el escenario de ruido ×0,5.

## 6. Potencia con el pool real y el criterio de P-EVAL-BASE v4.3 (25-oct; solo sintético)

**Por qué.** §1-§5 usan el ruido de las d de M1 (desviación mensual 0,30-0,36). El pool no existía: el «ruido ×0,5» era
un supuesto. Este estudio simula el pool tal como está especificado y aplica los criterios de A3 que se pueden calcular
con d.

**Método.** Dos capas, sin datos reales ni la etiqueta:
- **Estructural** (`tests/validation/potencia_holdout_estructural.py`): G latente (régimen de Markov + AR(1)), objetivo
  t = Φ(G/0,4); M0 = persistencia calibrada con t(s−5); M2 = Ĝ = q·G + (1−q)·G(s−5) + error AR(1) con σ̂ calibrada; M3 =
  mezcla más ruidosa; **pool exactamente como `pool_spec.md` §3** (BLP, Dirichlet moda (½, ¼, ¼) κ 20, ln a, ln b ~
  N(0; 0,5²), embargo 6, N_min 60), reestimado cada 12 meses (simplificación declarada). 312 meses de historia + 202 de
  bloqueado. q fija la calidad de M2 y, con ella, la mejora verdadera Δ del pool.
- **Forma reducida** (`potencia_holdout_reducida.py`): d con AR(1) e innovaciones t₄, desviación ×2 y efecto común por
  episodio en los giros de G, calendario con k recesiones, para la sensibilidad.
- Bootstrap = réplica exacta y vectorizada de `metrics.boot_mean` (bloques 12, 5.000 réplicas, semilla 20261015;
  diferencia ≤ 4e-17). 2.000 réplicas por celda, semillas fijas.

**Resultado (v4.3: criterios 1-4, 6 y 7; el 5 no se simula; el 8 no decide).** `estructural_v43.json`:

| Δ verdadera (nats) | 0 | 0,03 | 0,05 | 0,07 | 0,10 |
|---|---|---|---|---|---|
| v4.3 | **0,024** | 0,41 | 0,66 | 0,80 | 0,89 |
| v4.2 (suelo de 0,05) | 0,005 | 0,12 | 0,40 | 0,65 | 0,81 |
| HAC EWC (sensibilidad de A6) | 0,042 | 0,44 | 0,68 | 0,80 | 0,88 |
| unilateral 5 %, bootstrap b12 (no adoptado, D3) | 0,059 | 0,59 | 0,82 | 0,90 | 0,96 |

(Δ realizadas −0,0001 / 0,029 / 0,050 / 0,073 / 0,097; error de Monte Carlo ≤ 0,011.) **MDE al 80 % ≈ 0,074 nats.** El
pool deja la desviación de d en ≈ 0,55 veces la de M2; contrastar M2 solo tendría ≈ 1/3 de la potencia.

**Sensibilidad** (forma reducida, `reducida.json`, potencia con Δ = 0,07 con el criterio v4.3): base 0,87; φ = 0,6
0,68; φ = 0,85 0,48; σ = 0,29 0,69; σ = 0,365 0,54; 2 recesiones 0,87; n = 250 0,93; adverso 0,47. Error tipo I: 2,4 %
(estructural), 3,9 % (base), 5,2 % (φ 0,6), 8,4 % (φ 0,85).

**Límites.** El criterio 5 (falsas alarmas) no se simula (la potencia real es algo menor). El generador es el mejor caso
por construcción: componentes bien especificados y σ̂ de M2 calibrada. Con memoria larga de d el bootstrap es liberal.

**Reproducción** (`PYTHONPATH=.`):
```
python tests/validation/potencia_holdout_reducida.py research/validation/potencia_holdout/reducida.json        # ~3 min
NPROC=3 python tests/validation/potencia_holdout_estructural.py research/validation/potencia_holdout/estructural.json
QS=0.0,0.33,0.465,0.615,0.8 NPROC=4 python tests/validation/potencia_holdout_estructural.py \
    research/validation/potencia_holdout/estructural_v43.json                                               # ~9 min
```
