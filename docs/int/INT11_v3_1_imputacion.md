---
documento: INT-11 v3.1 — imputación condicionada de los activos sin dato (cambio de INGENIERÍA declarado)
fecha: 2026-11-05
estado: hecho (decisiones V2, V3 y V4 de docs/int/INT11_v4_correlaciones_v0.md §6, aprobadas por el usuario)
codigo: src/intl/escenarios.py (Config.v3_1, Generador._ajustar_pmm / _donante); tests/test_intl_int11_v3_1.py
medicion: scripts/int11_v3_1_imputacion.py (commit 63d70ea, árbol limpio) → research/int/int11_v3_1_imputacion.json
datos: solo ≤ 2004 (load_dev). Nada ≥ 2005 leído en el desarrollo.
---

# INT-11 v3.1: imputación condicionada

## 1. Qué cambia
- **Antes (v3):** el motor sortea filas país-año completas dentro de la celda de régimen (s_{t−1}, s_t). Si a la fila
  sorteada le falta un activo (oro antes de 1972: 70 % de las filas; vivienda: 17 %; bolsa, bonos y letras: 1-4 %),
  el hueco se rellena con un donante **al azar** de la misma celda, independiente del resto de la fila.
- **Ahora (v3.1):** el donante se elige **emparejado** (predictive mean matching, PMM), dentro de la misma celda:
  1. predictores Z = todas las demás variables observadas en la fila (activos en log 1 + r; inflación y crecimiento);
  2. donantes = filas de la celda con el activo y con todo Z observado (los mismos donantes de v3); si son menos de 20,
     filas del mismo s_{t−1}; si tampoco, todas;
  3. regresión ridge (Z estandarizada en los donantes, λ = 1) del activo sobre Z;
  4. el hueco toma el valor de un donante al azar entre los **5** cuya predicción está más cerca de la de la fila.
  El valor imputado sigue siendo un dato histórico real (con la reescala por país y el suavizado de v3, que no cambian).
- Parámetros (k = 5, λ = 1, n mín = 20) fijados **a priori** (valores de manual del PMM), sin mirar ningún resultado.
- **Todo lo demás es v3**: celdas, bloques, semivida 50 años (decisión V4: no se toca), c = 5,25, curtosis por país,
  pertenencia suave, κ. `Config.v3()` sigue reproduciendo v3 **bit a bit** (`imputacion="independiente"`, por
  defecto; test con valores calculados antes del cambio; además la fase D de v3 recalculada con el código nuevo sale
  idéntica a la oficial, `v3_identica_a_la_oficial: true`, y la tabla D_motor_v3 de v4 se reproduce exacta).

## 2. Por qué
INT-11 v4-correlaciones (docs/int/INT11_v4_correlaciones_v0.md §1.1-§1.2) encontró que la imputación independiente
diluye la dependencia del oro y de la vivienda con el resto: bonos-oro con inflación alta −0,26 en las filas con los
dos datos frente a −0,12/−0,20 en los escenarios de v3. Por qué PMM y no otra opción: (a) es el método estándar más
simple que condiciona en las variables observadas; (b) conserva la lógica del motor (el valor sale de una fila real,
así que la reescala por país y las colas no se tocan), a diferencia de una imputación gaussiana, que inventaría valores
y necesitaría un residuo aparte; (c) reducir a pool ≥ 1972 los escenarios con oro tiraría el 70 % de las filas y
cambiaría la predictiva de todos los activos.

## 3. Efecto medido
### 3.1 Caso sintético (tests)
Panel sintético con ρ(bonos, oro) = −0,61 en las filas completas y el 78 % del oro sin dato: escenarios v3 ≈ −0,26;
v3.1 ≈ −0,51/−0,54 (−0,59 sin el suavizado ni la reescala, que atenúan aparte); dt del oro igual (± 10 %).

### 3.2 Correlación de los escenarios (≤ 2004, 1 año, mismos países y semillas que D_motor_v3)
| país | partida | bolsa-bonos v3 → v3.1 | bonos-oro v3 → v3.1 | bolsa-oro v3 → v3.1 | bolsa-vivienda v3 → v3.1 |
|---|---|---|---|---|---|
| USA | expansión | 0,11 → 0,11 | −0,02 → 0,02 | −0,08 → −0,12 | 0,09 → 0,07 |
| USA | sobrecalentamiento | 0,45 → 0,44 | **−0,18 → −0,27** | −0,10 → −0,15 | 0,12 → 0,13 |
| DEU | expansión | 0,15 → 0,13 | −0,08 → −0,07 | −0,12 → −0,15 | 0,05 → 0,06 |
| DEU | sobrecalentamiento | 0,42 → 0,42 | **−0,18 → −0,30** | −0,04 → −0,14 | 0,06 → 0,07 |
| GBR | expansión | 0,22 → 0,19 | −0,04 → −0,03 | −0,07 → −0,05 | −0,04 → 0,00 |
| GBR | sobrecalentamiento | 0,50 → 0,53 | **−0,20 → −0,30** | −0,13 → −0,20 | 0,01 → 0,02 |
| ESP | expansión | 0,22 → 0,24 | −0,09 → −0,07 | −0,05 → −0,08 | 0,08 → 0,11 |
| ESP | sobrecalentamiento | 0,48 → 0,45 | **−0,12 → −0,25** | −0,04 → −0,06 | 0,13 → 0,12 |
| filas crudas s_{t−1} | expansión / sobrecal. | 0,22 / 0,46 | 0,02 / −0,26 | −0,06 / −0,05 | 0,11 / 0,12 |

- **Bonos-oro con inflación alta** pasa de −0,12/−0,20 a −0,25/−0,30: vuelve al nivel de las filas con los dos datos
  (−0,26). Con inflación baja sigue ≈ 0 (como las filas: 0,02).
- **Bolsa-bonos** no cambia (± 0,03: bolsa y bonos casi nunca faltan). Bolsa-vivienda tampoco (± 0,04: la vivienda
  falta en el 17 % y su dependencia con la bolsa es débil). Bolsa-oro se vuelve algo más negativa con inflación alta (−0,02 a −0,09).
- Emparejamiento en los datos reales: oro 87,5 % de los huecos con donante de la celda y 12,5 % del mismo s_{t−1};
  vivienda 69 % / 6 % / 25 % (todas); **ningún hueco** cae al donante independiente.

### 3.3 Cobertura de desarrollo (INFORMATIVO; no es una puerta nueva)
La fase D de v3 (LOCO + temporal ≤ 2004, mismas semillas y pliegues) recalculada con v3.1. **No es una puerta**: ≤ 2004
ya se usó para desarrollar; la banda nula es la oficial de v3, no recalculada; la puerta D de v3 sigue siendo la que
cuenta (pasó, 30-oct).

| | v3 (oficial = recalculada) | v3.1 (informativo) |
|---|---|---|
| S5 LOCO | 0,8976 | 0,8993 |
| bolsa / bonos / letras / vivienda / oro | 0,923 / 0,908 / 0,882 / 0,896 / 0,896 | 0,925 / 0,911 / 0,884 / 0,895 / 0,903 |
| regímenes raros | 0,898 | 0,895 |
| cerca del umbral | 0,940 | 0,943 |
| S5 temporal (< 1950 → 1950-2004) | 0,9153 | 0,9154 |
| BSS inflación > 5 % / caída bolsa ≤ −20 % | 0,269 / 0,022 | 0,269 / 0,020 |
| "puerta" con la banda de v3 (referencia) | pasa | pasaría |

Las marginales casi no se mueven (≤ 0,7 pp por activo): el cambio es de dependencia, no de anchura.

## 4. Cambios en la salida "hoy" y en el 5d del reporte semanal
- `scripts/int11_v3_hoy.py` emite con **v3.1** por defecto (`--v3` reproduce la imputación de v3, solo para comparar);
  research/int/int11_v3_hoy.{json,md} regenerados el 5-nov-2026. El acierto que etiqueta cada abanico sigue siendo el
  **medido en la fase D de v3**; al lado, la cifra informativa de v3.1.
- Abanicos de hoy frente a v3 en la misma fecha: bolsa p5/p50/p95 ≤ 2 pp; P(bolsa ≤ −20 %) ± 0,5 pp; P(inflación > 5 %)
  igual. Oro: con inflación baja el p5 baja hasta ≈ 4 pp (FIN, FRA, SWE, ITA: −16 % → −20 %), porque el oro que se
  imputa a las filas anteriores a 1972 sigue ahora la relación con el resto de la fila en lugar de ser una copia al
  azar.
- **Nuevo (decisión V3):** tabla "Dependencia entre activos por régimen (≤ 2004, no confirmado)" con bolsa-bonos y
  bonos-oro de los escenarios de cada país (hoy, partiendo de expansión y de sobrecalentamiento) y la descriptiva ≤ 2004
  por inflación previa (research/int/int11_v4_potencia.json: bolsa-bonos 0,23 / 0,45; bonos-oro 1972-2004 0,03 /
  −0,27). Bonos-oro partiendo de sobrecalentamiento, mediana de los 14 países: −0,18 con v3 → −0,29 con v3.1.
- `src/report/weekly.py` (5d): título "INT-11 v3.1", la tabla de dependencia entra en el reporte y en el
  `_signal.json` (`dependencia_hoy`, `dependencia_por_regimen`, `dependencia_descriptiva_2004`).

## 5. Registro en vivo: serie nueva
El motor cambia → **serie nueva** (prerregistro v3 §8; registro v0.2 §1): `serie_registro = "int11_v3_1"`, carpeta
propia `research/int/int11_v3_1_vivo/` (`SERIE_VIVO`, `VIVO_V3_1` en el script "hoy"). `registro_vivo.registrar` marca
la carpeta con su serie en la primera emisión y rechaza una emisión de otra serie, o una serie con nombre en una
carpeta con emisiones sin marca (la serie v2). El registro **sigue sin activarse** (falta fijar la fuente de bolsa, D9).
Ninguna emisión de v3 se mezcla con las de v3.1.

## 6. Límites (declarados)
- Si faltan dos activos en la misma fila (oro y vivienda), cada uno se empareja por separado con las variables
  observadas: la dependencia oro-vivienda de esas filas no se conserva.
- El PMM conserva la dependencia **lineal en la media**; con k = 5 y el suavizado de v3 queda una atenuación pequeña
  (sintético: −0,51/−0,54 frente a −0,61).
- Las filas sin oro (anteriores a 1972) tienen otra época; el emparejamiento traslada a ellas la relación medida en
  1972-2004 (más inflación) dentro de la celda. Es el supuesto del motor (misma celda, misma dependencia), no algo nuevo.
- Lo medido en §3 es en ≤ 2004 ya usado: descriptivo, no confirmatorio.
