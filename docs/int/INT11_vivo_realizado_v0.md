---
documento: INT-11 v3.1 — prerregistro del REALIZADO en vivo de bonos, letras, vivienda y oro, y del semáforo y el contraste formal del registro
version: 0.1 (2026-11-05) — BORRADOR para el usuario, con recomendaciones (§7). Escrito ANTES de cualquier ventana cerrada (la primera cierra ≈ 2028-03; hoy el registro no tiene ni una emisión).
parte_de: docs/int/INT11_registro_vivo.md §3 · docs/int/INT11_fuente_bolsa_vivo.md (bolsa, aprobada) · docs/int/EVAL_registros_vivo.md §3-§4 (I-1, I-5)
código: src/report/activos_vivo.py (lectura y semáforo, funciones puras) · tests/test_activos_vivo.py (12, sintéticos) ·
        scripts/int11_vivo_realizado.py (mediciones → research/int/int11_vivo_realizado.json y bandas congeladas → research/int/int11_vivo_semaforo.json) ·
        scripts/eval_int11_vivo.py (conectado; interruptor MEDIDAS_NUEVAS_APROBADAS = False) · tests/test_eval_registros_vivo.py (+4)
---

# Realizado en vivo de bonos, letras, vivienda y oro; semáforo y contraste formal

## 0. Resumen
- **Regla de esta medición:** igual que la de la bolsa. Hasta 2004 se comparan **fuentes** con JST (`load_dev`). Desde
  2005 solo se comparan fuentes vivas entre sí. No se ha leído JST ≥ 2005 ni ningún resultado del motor; el registro
  sigue vacío. Cada celda da *correlación / sesgo (fuente − JST, pp) / dt de la diferencia (pp)*, con rentabilidades
  nominales en moneda local por años naturales.
- **Bonos:** OCDE `oecd_irlt_<p>` (rendimiento a 10 años, media mensual) → bono a la par a 10 años con
  `returns.bono_tr_mensual`, encadenado en los 12 meses de la ventana. Frente a JST `bond_tr` (14 países, mediana de
  21 años): **0,956 / +0,6 / 2,9**. Es poco frente a la dispersión del activo (10 pp): con ese error, la cobertura
  esperada del p5-p95 es 88,6 % en lugar de 90 %.
- **Letras:** OCDE `oecd_ir3m_<p>`, **media de los 12 meses** de la ventana. Es la definición de JST: `bill_rate` es
  el tipo corto medio del año. Resultado: **0,997 / +0,2 / 0,3**. Encadenar `y_{m−1}/12` es peor (sesgo +0,7). GBR se
  empalma con el OIS a 3 meses del BoE (como el termómetro). El tipo a un día queda de respaldo.
- **Vivienda:** **JST `hpnom` es una media anual**. La plusvalía media/media coincide con JST mucho mejor que la de
  T4/T4 (0,971 frente a 0,916 en 1986-2004). Medida propuesta: precio BIS `bis_spp_<iso2>_n` (media de los 4
  trimestres de la ventana / media de los 4 anteriores) **+ alquiler como JST** (rent_rtn = rent_yd · (1 + plusvalía)).
  El rent_yd se encadena desde el de JST de 2004 con el índice de alquileres y el de precios de la OCDE. Con un ancla a
  20 años, frente a JST `housing_tr`: **0,968 / −0,1 / 1,45**. Solo con el precio, el sesgo es −4,6 pp: la cobertura
  bajaría a 84,9 %, así que **no vale**. El índice de alquileres de la OCDE **no está en el warehouse** (V3).
- **Oro:** Banco Mundial `gold_wb_usd_m` (media mensual): último mes de la ventana / mes previo × divisa de fin de mes
  de FRED H.10. En una ventana enero-diciembre es **exactamente la construcción del motor**, solo que con la divisa de
  FRED en lugar de la de JST. En los 6 países no euro (33 años): **1,000 / 0,0 / 0,5-0,8**; en el euro solo hay
  2000-2004.
- **Deflactor:** el de la bolsa (IPC OCDE, media de los 12 meses de la ventana / media de los 12 anteriores). Frente a
  JST: 0,998 / 0,0 / 0,3.
- **Semáforo:** cobertura p5-p95 **acumulada** de las emisiones de **diciembre**, frente a bandas simuladas bajo H0
  (abanico calibrado). Las bandas tienen en cuenta el **choque común del año**, medido ≤ 2004. Verde dentro del 80 %
  central, ámbar dentro del 95 % y rojo fuera.
  - **La binomial ingenua (14 × años filas independientes) no sirve:** el efecto de diseño es 2,4 en la bolsa, 3,2 en
    los bonos, 1,1 en la vivienda, 10 en el oro y 6 en S5 (media de los 5 activos). Con ella, el "rojo" saldría en un
    16-43 % de los años con un motor calibrado.
  - Las bandas quedan congeladas en `research/int/int11_vivo_semaforo.json` (sha256 en el evaluador).
- **Potencia** (contraste bilateral al 5 %, potencia 0,8 frente a una cobertura real del 80 %):
  - **S5: 10 años** de diciembre (0,84). La bolsa sola: 19. Las letras: 19. La vivienda: 8. Los bonos y el oro: más
    de 20.
  - Frente a una cobertura real del 85 %, nada llega a 0,8 en 20 años (S5 a 20 años: 0,61).
  - Con la binomial ingenua harían falta 8 años para un activo y 2 para S5, pero esa cifra es falsa.
- **Contraste formal (único):** con los **10 primeros años de diciembre** (ventanas 2027-2036, evaluable ≈ 2038), S5
  fuera de [83,6 %; 94,4 %] → "DESCALIBRADO EN VIVO". **Si sale rojo, no se reestima nada sobre el vivo** (§5.5).

## 1. Qué aprendió el motor (leído del código)
| activo | variable del motor | construcción | código |
|---|---|---|---|
| bonos | JST `bond_tr_real` | rentabilidad total anual del bono del Estado (≈ 10 años) en local, real con el IPC JST | `scripts/int11_corrida.COL` |
| letras | JST `bill_rate_real` | `bill_rate` = **tipo corto medio del año** (`= stir/100` en 1950-2004 en DEU DNK FRA GBR ITA siempre y en BEL ESP FIN JPN NLD PRT a ratos; NOR, SWE y USA, otra serie de letras) | ídem |
| vivienda | JST `housing_tr_real` | `housing_capgain` (cambio de `hpnom`, **media anual**, §3.3) + `housing_rent_rtn` (= `rent_yd` · (1 + plusvalía), comprobado: ESP 2004 0,0174 × 1,1831 = 0,0206) | ídem |
| oro | `activos3b.oro_panel` | oro en USD (≤ 1959 MeasuringWorth; ≥ 1960 **media de diciembre del Banco Mundial**) × `xrusd` JST (fin de año), real con el IPC JST; solo ≥ 1972 | `src/intl/activos3b.py` |

Todas son rentabilidades reales **simples** anuales: (1 + nominal)/(1 + inflación) − 1. El registro emite cuantiles de
la ventana de 12 meses que empieza el mes siguiente a la emisión. La de diciembre es un año natural, igual que en JST.

## 2. Inventario y disponibilidad (warehouse, 2026-11-05)
| serie | países | contenido | último dato | ¿uso? |
|---|---|---|---|---|
| `oecd_irlt_<p>` | 14/14 (ESP 1980, NOR 1985, SWE 1986, DNK 1987, FIN 1988, JPN 1989, ITA 1991, PRT 1993) | rendimiento a 10 años, **media** mensual | 2026-09 (DEU, NOR 2026-10) | **bonos, principal** |
| `IRLTLT01*` FRED, `bde_es_gov_long_yield_m`, `DGS10`, `GS10` | parciales | lo mismo que la OCDE (FRED es la OCDE; BdE frente a la OCDE: 1,000 / 0,0 / 0,1); DGS10 es diario | 2026-09 / 11 | contraste |
| `oecd_ir3m_<p>` | 14/14 (JPN desde 2002); **GBR cortada en 2026-02** | tipo a 3 meses, media mensual | 2026-09 (JPN 2026-08) | **letras, principal** |
| `boe_ois3m_m` | GBR | OIS SONIA a 3 meses, media mensual | 2026-09 | empalme de GBR (docs/int/GBR_3m_sustituto.md) |
| `oecd_ircall_<p>` | 14/14 (**SWE cortada en 2020-10**, DNK en 2025-12) | tipo a un día, media mensual | 2026-10 | letras, respaldo |
| `bis_spp_<iso2>_n` | 14/14 (PRT desde 1988) | precio residencial nominal, **trimestral** | T2 2026 (BEL T1, **JPN T4 2025**) | **vivienda, precio** |
| OCDE *Analytical house prices*, `HPI` y `RPI` | 14/14 (RPI de **USA hasta T4 2024**, de ITA hasta T4 2025) | precio y **alquiler**, trimestral, CC BY 4.0 | T2-T3 2026 | **alquiler (RPI)**; HPI de respaldo. **No ingerido** (caché de la medición: `$FIN_DATA_ROOT/raw/int11_oecd_vivienda/`) |
| `CSUSHPINSA`, `bde_es_house_price_m2_q` | USA, ESP | precio | 2026-08 / T2 2026 | contraste |
| `gold_wb_usd_m` (= `gold_datahub_usd_m` = `gold_usd_monthly`, idénticas) | — | oro en USD, media mensual (Banco Mundial, Pink Sheet) | 2026-09 | **oro, principal** |
| FX FRED H.10 (`DEX*`) | divisas de los 14 (las de DKK, NOK y SEK, en la caché de la bolsa) | diario | 2026-10-30 | la misma de la bolsa |

**Retrasos de lectura** (meses después del fin de la ventana; cada activo se lee **una vez**, a su retraso):
bonos, letras y oro, **3** (como la bolsa); vivienda, **12** (el BIS de JPN llega ≈ 10 meses tarde y el de BEL ≈ 7).

## 3. Mediciones (`scripts/int11_vivo_realizado.py` → `research/int/int11_vivo_realizado.json`)
### 3.1 Bonos
Medida: bono a la par a 10 años, cupón y_{m−1}, r(m) ≈ y_{m−1}/12 − D·Δy + ½·C·Δy², con los rendimientos medios de la
OCDE, encadenado en los 12 meses. Frente a JST `bond_tr`, ≤ 2004:

| país | años | irlt encadenado | país | años | irlt encadenado |
|---|---|---|---|---|---|
| BEL | 49 | 0,952 / +0,4 / 2,9 | JPN | 15 | 0,939 / −0,2 / 2,4 |
| DEU | 48 | 0,904 / +0,9 / 3,3 | NLD | 45 | 0,947 / +0,8 / 2,9 |
| DNK | 17 | 0,966 / +0,4 / 2,8 | NOR | 19 | 0,984 / +0,7 / 1,9 |
| ESP | 24 | **0,828 / +2,6 / 7,8** | PRT | 11 | 0,985 / +0,5 / 2,1 |
| FIN | 15 | 0,982 / +0,9 / 2,6 | SWE | 18 | 0,991 / −0,2 / 1,6 |
| FRA | 44 | 0,901 / +1,1 / 4,6 | USA | 51 | 0,960 / +0,3 / 3,0 |
| GBR | 44 | 0,943 / +0,2 / 4,8 | ITA | 13 | 0,989 / +1,4 / 3,0 |

- **Mediana: 0,956 / +0,6 / 2,9.** El sesgo positivo, de +0,6 pp, es coherente con un bono a la par de duración algo
  menor que la cartera de JST. Se declara y no se corrige.
- Aplicar la fórmula a la **media anual** del rendimiento es mucho peor (0,64 / −0,1 / 8,2): hay que encadenar por
  meses.
- USA: con el DGS10 de **fin de mes**, 0,970 / +0,3 / 2,7 (efecto Working pequeño); Damodaran frente a JST,
  0,952 / −0,2 / 2,9.
- Desde 2005, el irlt de USA frente al DGS10 de fin de mes da 0,983 / 0,0 / 1,7 (anual) y 0,981 / +0,1 / 1,5 (12 meses
  móviles). ESP OCDE frente a BdE: 1,000 / 0,0 / 0,1.
- **ESP** se aparta antes de 1990: el JST de ESP no es un bono a 10 años de mercado. Igual que con DNK y JPN en la
  bolsa, se declara y no se excluye.

### 3.2 Letras
| medida (frente a JST `bill_rate`) | países | mediana |
|---|---|---|
| **ir3m, media de los 12 meses** | 13 (JPN: ir3m desde 2002) | **0,997 / +0,2 / 0,3** |
| ir3m encadenada (`letra_tr_mensual`) | 13 | 0,993 / +0,7 / 0,5 |
| tipo a un día, media | 14 | 0,990 / 0,0 / 0,2 |
| USA TB3MS, media | 1 | 0,981 / −0,7 / 0,7 |
| GBR, letras del BoE, media (hasta 2017) | 1 | 1,000 / 0,0 / 0,1 |

- Excepciones: NOR (+2,7 / 1,8) y SWE (+1,8 / 1,5). El `bill_rate` de JST de esos países no es el tipo a 3 meses de la
  OCDE.
- JPN sale perfecto con el tipo a un día (1,000 / 0,0 / 0,0, 19 años).
- Desde 2005: ir3m frente al tipo a un día, 0,99 / +0,2 / 0,2 en todos los países. GBR, ir3m frente al OIS (2016-2026):
  0,9996 / +0,1 / 0,06.

### 3.3 Vivienda
**Hallazgo:** la plusvalía de JST es un cambio de **medias anuales**, no de fin de año.

| plusvalía frente a JST `housing_capgain` | 1986-2004 (14 países, 19 años) | toda la historia (34 años) |
|---|---|---|
| **BIS, media/media** | **0,971 / −0,1 / 1,3** | 0,981 / 0,0 / 1,8 |
| BIS, T4/T4 | 0,916 / 0,0 / 3,0 | 0,903 / 0,0 / 4,3 |
| OCDE HPI, media/media | 0,958 / 0,0 / 1,7 | 0,968 / −0,2 / 1,9 |
| OCDE HPI, T4/T4 | 0,882 / 0,0 / 3,5 | 0,884 / 0,0 / 4,2 |

Al revés que en la bolsa, esto ocurre en **los 14 países** a la vez, no en uno (como JPN). El motor aprendió una
vivienda con precios medios. Medirla en T4/T4 añadiría dispersión que no es culpa del motor: el error de medida pasa de
1,45 a 3,2 pp y la cobertura esperada, de 89,6 % a 87,9 %. **Recomendación (V1):** la plusvalía principal es
media/media (la media de los 4 trimestres de la ventana frente a la de los 4 anteriores); T4/T4 queda como
descriptivo. Coste declarado: en la emisión de diciembre ya se conoce casi todo el año anterior, la base de la media.
Esa es la definición que aprendió el motor.

**Alquiler.** JST: rent_rtn = rent_yd · (1 + plusvalía). En vivo, rent_yd(ventana) = rent_yd_JST(2004) ·
[R̄(ventana)/R̄(2004)] / [P̄(ventana)/P̄(2004)], con R el índice de alquileres (RPI) y P el de precios (BIS). Para probarlo
con un horizonte como el del vivo (≈ 20 años), se ancla en **1984** (PRT en 1989) y se compara 1985-2004 con JST
`housing_tr`:

| total (precio BIS media/media +) | mediana 14 países | cobertura esperada del p5-p95 (§3.6) |
|---|---|---|
| **alquiler encadenado con el RPI de la OCDE** | **0,968 / −0,1 / 1,45** | **89,6 %** |
| rent_yd fijo en el ancla (sin RPI) | 0,959 / 0,0 / 1,8 (pero BEL +1,9, ESP +2,1, NLD +1,3) | 89,3 % |
| solo precio | 0,959 / **−4,6** / 1,8 | **84,9 %** |
| alquiler encadenado, plusvalía T4/T4 | 0,909 / 0,0 / 3,2 | 87,9 % |

- El rent_yd encadenado reproduce el de JST: 0,967 / −0,1 / 0,2 pp (rent_yd de 2004: BEL 4,43 % frente a 4,46 %; ESP
  1,65 % frente a 1,74 %).
- Fijarlo en el ancla se desvía mucho por país (BEL: 7,9 % fijo frente a 4,5 % real). La mediana sale bien de
  casualidad.
- Fallan NOR (3,8 % frente a 5,1 %) y SWE (7,5 % frente a 5,0 %).
- **PRT** no casa con JST en ninguna versión (0,47 / −4,3 / 6,5 en el precio; BIS y OCDE coinciden entre sí). Se
  declara y se recomienda una **sensibilidad sin PRT** en la vivienda, descriptiva (V6).
- Desde 2005: BIS frente a OCDE HPI, T4/T4, en 0,93-1,00 (USA 0,947 / −0,5 / 2,7; Case-Shiller 0,972 / −0,2 / 1,8).

### 3.4 Oro
| comparación | resultado |
|---|---|
| construcción del registro (WB dic. × FX FRED fin de dic.) frente a la del motor (WB dic. × JST `xrusd`), DNK GBR JPN NOR SWE, 1972-2004 | **1,000 / 0,0 / 0,5-0,8** (33 años; USA, idéntica por construcción) |
| ídem, los 8 del euro (FRED EUR solo desde 1999) | 0,978 / +0,2 / 0,6 (5 años) |
| cambio anual de la divisa FRED de fin de diciembre frente a `xrusd` JST | 0,998-1,000 / 0,0 / 0,5-0,8 |
| oro en USD, WB dic./dic. frente a Damodaran, 1961-2004 | 0,983 / −0,2 / 5,2 (Damodaran usa otra fecha) |
| WB frente a `gold_datahub_usd_m`, ≥ 2005 | idénticas (diferencia máxima 0 %): **no son dos fuentes** |

El oro en USD es la misma serie que usó el motor. Solo cambia la divisa, la misma de fin de mes que la bolsa ya
aprobada. No hay un respaldo independiente en el warehouse (V5).

### 3.5 Deflactor
El de la bolsa (A3, aprobado): IPC OCDE, media/media, frente a la inflación JST, 0,998 / 0,0 / 0,3 (mediana de 49
años).

### 3.6 Error de medida → cobertura
Si el realizado lleva un error independiente de dt d y sesgo b frente a la definición del motor, la cobertura de un
p5-p95 calibrado de dt σ es Φ((1,645σ − b)/√(σ² + d²)) − Φ((−1,645σ − b)/√(σ² + d²)). σ es la dt total (común +
propia, ≤ 2004, `int11_potencia.json`).

| activo | σ (pp) | d / b (pp) | cobertura esperada |
|---|---|---|---|
| bolsa (doc. de la bolsa) | 20,8 | 4,2 / −0,6 | 89,3 % |
| bonos | 10,0 | 2,9 / +0,6 | 88,6 % |
| letras | 5,6 | 0,3 / +0,2 | 89,9 % |
| vivienda | 8,9 | 1,45 / −0,1 | 89,6 % |
| oro | 20,9 | 0,6 / +0,2 | 90,0 % |

La pérdida (≤ 1,4 pp) es menor que la anchura de cualquier banda del semáforo (§5). Es una cota superior: parte de la
diferencia con JST es error de JST, no de la fuente viva.

## 4. Medidas propuestas (V1-V5)
| activo | principal | respaldo (solo si a la principal le falta algún dato de la ventana; nunca se mezclan) | contraste / descriptivo | retraso |
|---|---|---|---|---|
| bonos | `oecd_irlt_<p>` → `bono_tr_mensual` encadenado (hace falta también el mes previo) | `IRLTLT01<p>M156N` FRED (es la OCDE) | USA: DGS10 de fin de mes; ESP: BdE | 3 m |
| letras | `oecd_ir3m_<p>`, media de los 12 meses; GBR + `boe_ois3m_m` desde 2026-03 (empalme del termómetro: sin ajuste si \|dif. 24 m\| < 0,05 pp) | `oecd_ircall_<p>`, media (SWE: el tipo a un día está cortado) | encadenada `y_{m−1}/12` | 3 m |
| vivienda | `bis_spp_<iso2>_n` media/media + alquiler JST con rent_yd encadenado con el RPI de la OCDE desde el de JST de 2004 | precio OCDE HPI; sin RPI, rent_yd **fijo** en 2004, declarado (`metodo = alquiler_fijo`) | T4/T4; sin PRT | 12 m |
| oro | `gold_wb_usd_m` último mes / mes previo × FX FRED H.10 de fin de mes | ninguno independiente en el warehouse (V5) | — | 3 m |

Reglas comunes, las mismas que la bolsa:
- se pasa a real con el IPC OCDE media/media;
- cada activo se lee **una vez**, a su retraso, en `research/int/int11_v3_1_realizado/AAAA-MM_<activo>.json`, que no
  se reescribe;
- se guardan el valor, el método usado (`metodo`, `modo`), la fecha de lectura y el sha256 de las series;
- solo el realizado derivado, nunca las series;
- un país sin dato a la hora de la lectura queda fuera de esa ventana (se cuenta, no se rellena después).

## 5. Semáforo y contraste formal (I-5)
### 5.1 Qué se mide
- **Principal:** emisiones de **diciembre**, ventanas enero-diciembre sin solape (I-2). La medida es la cobertura
  p5-p95 **acumulada** desde la primera, por activo, y **S5** = media de las coberturas de los 5 activos (14 países).
- Todas las emisiones, la bolsa sin JPN y la vivienda sin PRT van como descriptivo.

### 5.2 Bandas (H0 = abanico calibrado), congeladas
- **Simulación:** 20.000 réplicas con semilla 20261105. En cada año, un choque **común** a los 14 países más uno
  propio de cada país, t multivariante entre activos (ν = 5,2). Las dt común y propia y la correlación entre activos
  son las medidas ≤ 2004 en `int11_potencia.json`.
- El abanico, calibrado para la marginal, no anticipa el choque común. Esa es la hipótesis de la simulación.
  Proporción común de la varianza: bolsa 0,32, bonos 0,43, letras 0,34, vivienda 0,06, **oro 0,91** (el oro en local
  es casi el mismo número en los 14 países).
- **H80 y H85:** el realizado se escala (× 1,34 o × 1,17) hasta que el p5-p95 cubre el 80 % o el 85 %.

Extracto de `research/int/int11_vivo_semaforo.json`. Banda en %: p2,5 / p10 – p90 / p97,5. "Ingenua" es la binomial de
14·años·activos filas independientes; entre paréntesis, cuántas veces daría rojo con un motor calibrado.

| | años | banda (p2,5 / p10 – p90 / p97,5) | efecto de diseño | ingenua (tamaño real) | potencia frente a 80 % | frente a 85 % |
|---|---|---|---|---|---|---|
| **S5** | 1 | 65,7 / 78,6 – 97,1 / 98,6 | 6,0 | 82,9–95,7 (0,35) | 0,12 | 0,06 |
| S5 | 3 | 77,1 / 83,3 – 95,2 / 96,7 | 6,0 | 85,7–93,8 (0,38) | 0,29 | 0,11 |
| S5 | 5 | 80,6 / 84,9 – 94,3 / 95,7 | 6,1 | 86,9–93,1 (0,40) | 0,49 | 0,16 |
| **S5** | **10** | **83,6 / 86,3 – 93,3 / 94,4** | 6,1 | 87,7–92,1 (0,43) | **0,84** | 0,31 |
| S5 | 20 | 85,8 / 87,4 – 92,4 / 93,4 | 6,0 | 88,4–91,6 (0,42) | 0,995 | 0,61 |
| bolsa | 10 | 80,7 / 84,3 – 94,3 / 95,7 | 2,4 | 85,0–95,0 (0,16) | 0,50 | 0,17 |
| bonos | 10 | 79,3 / 83,6 – 95,0 / 96,4 | 3,3 | 85,0–95,0 (0,22) | 0,40 | 0,14 |
| letras | 10 | 80,7 / 84,3 – 94,3 / 96,4 | 2,5 | 85,0–95,0 (0,17) | 0,48 | 0,17 |
| vivienda | 10 | 84,3 / 86,4 – 93,6 / 95,0 | 1,1 | 85,0–95,0 (0,04) | 0,88 | 0,38 |
| oro | 10 | 70,7 / 79,3 – 99,3 / 100 | 10,1 | 85,0–95,0 (0,55) | 0,18 | 0,08 |

**Años para potencia 0,8 frente a 80 %:**
- S5: 10.
- Sin la bolsa: 11.
- Vivienda: 8.
- Bolsa: 19.
- Letras: 19.
- Bonos: más de 20 (0,71 a 20 años).
- Oro: más de 20 (0,35 a 20 años).

Frente a 85 %, ninguno llega en 20 años. Con la binomial ingenua harían falta 8 años para un activo y 2 para S5, pero
esa cifra es falsa: tiene un tamaño de 0,16-0,43 en lugar de 0,05.

**Semáforo (cada año, sin contraste):**
- verde si la cobertura acumulada está en [p10, p90] de su banda;
- ámbar si está en [p2,5, p97,5] pero fuera de la anterior;
- rojo si está fuera.

Colores por activo y para S5. Ojo: en los años 1-2 las bandas de un activo son casi inútiles (granularidad de 14
filas; con el oro, de una).

### 5.3 Contraste formal (único)
- **Cuándo:** en la primera revisión con **10 años de diciembre** con los 5 activos medidos. Son las ventanas
  2027-2036, ≈ abril de 2038.
- **Qué se contrasta:** S5 de esos 10 primeros años.
  - Fuera de **[83,6 %; 94,4 %]** → **"DESCALIBRADO EN VIVO"**, diciendo el lado (abanico estrecho o ancho).
  - Dentro → **"NO SE RECHAZA LA CALIBRACIÓN"**.
- **Potencia:** 0,84 frente a una cobertura real del 80 %; 0,31 frente al 85 %. Tamaño de 0,05 si el motor está
  calibrado y la estructura de choques comunes de ≤ 2004 se mantiene.
- **Veredicto:** se escribe **una vez** en `research/int/eval_int11_vivo_veredicto_10a.json` y no se rehace.
- Lo que se publica al lado, como descriptivo y sin decidir nada:
  - por activo, con su banda de 10 años, sin corrección por multiplicidad;
  - todas las emisiones, con IC por años;
  - la bolsa sin JPN y la vivienda sin PRT;
  - K2 (Brier y BSS con IC por años, como en EVAL §3).
- **Relación con el bloqueado:** el contraste del bloqueado (la confirmación única) es otra evidencia, con otras
  reglas. Si llega antes, no cambia este contraste.

### 5.4 PIT y CRPS (descriptivos, como I-4)
Por activo y para S5:
- histograma del PIT por deciles, KS, fracción por debajo del p5 y por encima del p95 (¿el abanico falla por un lado?);
- CRPS por cuantiles.

No deciden nada; sirven para diagnosticar un ámbar o un rojo.

### 5.5 Qué se hace si sale rojo (y si el contraste da "descalibrado")
1. **Nunca** se reestima, recalibra ni ensancha el motor con datos del vivo. Ni un factor de anchura aprendido del
   registro ni un cambio de umbral. El motor sigue estimado con ≤ 2004.
2. **Rojo en el semáforo anual** (antes de 10 años): el informe de INT-11 pone el aviso "abanico fuera de su banda en
   vivo (<activo>, <lado>)" junto a las cifras del activo. El registro sigue igual y no se para.
3. **Diagnóstico, declarado y sin cambiar el veredicto:**
   - el PIT (¿de un lado?);
   - por país (¿JPN o PRT?);
   - si el rojo desaparece con el **respaldo** de la medida;
   - si lo explica el error de medida (§3.6).
4. **"DESCALIBRADO EN VIVO" en el contraste:** las cifras de INT-11 se presentan como "no calibradas en vivo", con la
   cobertura medida, en todas las salidas.
   - Cualquier arreglo es un **motor nuevo con prerregistro nuevo** (v4 o posterior), estimado solo con ≤ 2004 (y,
     si ya se ha gastado, con lo que permita el bloqueado). Abre una **serie nueva** del registro.
   - La serie v3.1 sigue emitiendo sin cambios hasta que el usuario la retire, para no romper la evidencia acumulada.
5. **"NO SE RECHAZA":** no se anuncia "calibrado". Se dice "compatible con el 90 % en 10 años; esta prueba no distingue
   el 85 %" (potencia 0,31).

## 6. Implementación (hecha, NO activada)
- **`src/report/activos_vivo.py`**, funciones puras (sin warehouse, red ni escritura):
  - lectura de la ventana: `rent_bono_ventana`, `rent_letra_ventana` ("media" / "encadenada"), `empalmar_3m` (el del
    termómetro), `rent_vivienda_ventana` ("media" / "q4"; "indice_alquiler" / "alquiler_fijo" / "solo_precio"),
    `rent_oro_ventana`, `realizado_activos_pais`;
  - semáforo: `banda_binomial`, `semaforo`, `simular_dentro`, `umbral_marginal`, `escala_para`.
- **Lectura** (`activos_vivo.py`): `leer_realizado_activos`, `series_leidas` y `yd_ancla_jst`. Este último es el
  **único** dato JST: rent_yd de 2004, con `load_dev`.
- **Tests:** `tests/test_activos_vivo.py`, 12, sintéticos, incluido un warehouse inventado en memoria.
- **Evaluador `scripts/eval_int11_vivo.py`:**
  - `cerrada(o, hoy, activo)` aplica el retraso de cada activo;
  - `leer_realizado_activo` guarda `AAAA-MM_<activo>.json` una sola vez;
  - `semaforo_diciembre`, `contraste` y `bandas()` comprueban el sha256 de las bandas;
  - hay un veredicto único a 10 años.
  - **Interruptor `MEDIDAS_NUEVAS_APROBADAS = False`:** mientras no se apruebe, los activos nuevos **no se leen ni se
    congelan** (se anotan "sin leer"), y el semáforo sale solo para la bolsa, sin S5.
  - Hoy, en modo real: "INT-11 v3.1: sin ventanas cerradas a 2026-11-05 (0 emisiones registradas)". No abre el
    warehouse ni escribe nada.
  - El modo `--sintetico` da los mismos números que EVAL §3 (la bolsa y K2 usan el mismo generador; los activos nuevos,
    otro).
  - Tests: 4 nuevos en `tests/test_eval_registros_vivo.py`. Con los 5 activos calibrados, el contraste da "NO SE
    RECHAZA"; con 1,7 σ da rojo y "DESCALIBRADO (abanico estrecho)"; con menos de 10 años, "sin contraste". Hay también
    un test de integridad de las bandas.
- **Mediciones:** `.venv/bin/python -m scripts.int11_vivo_realizado [--refrescar] [--nsim N]` (≈ 10 s). Descarga el
  CSV de OECD Analytical house prices a la caché, si no está. Las bandas salen idénticas al repetir la corrida
  (sha256 `1f3703ac…7309ec`).

## 7. Lo que el usuario debe aprobar
| # | decisión | recomendación |
|---|---|---|
| V1 | vivienda: plusvalía **media/media** (como JST) o T4/T4 (lo que gana un inversor) | **media/media**: 0,971 frente a 0,916; pasa en los 14 países, no en uno. T4/T4 como descriptivo |
| V2 | bonos y letras | **bonos:** irlt encadenado. **Letras:** ir3m media de 12 meses, GBR con el OIS y el tipo a un día de respaldo |
| V3 | **ingerir OECD Analytical house prices** (`oecd_rpi_<p>_q`, `oecd_hpi_<p>_q`, trimestral, CC BY), que da el alquiler | **sí**, antes de 2029-01 (la primera vivienda se lee 12 meses después de cerrar la ventana). Mientras no esté, el evaluador usaría el rent_yd fijo (respaldo, declarado) |
| V4 | RPI de **USA** parado en T4 2024 en la OCDE | vigilar; si no se reanuda antes de 2028, sustituirlo por el IPC de alquileres de EE. UU. (FRED `CUSR0000SEHA`) con el mismo encadenado (enmienda) |
| V5 | oro sin respaldo independiente | aceptarlo; si el Banco Mundial deja de publicar, usar el LBMA PM mensual (requiere ingest) |
| V6 | sensibilidades declaradas de antemano | bolsa sin JPN (ya aprobada); **vivienda sin PRT**; las dos, descriptivas |
| V7 | semáforo y contraste (§5) | **S5** como contraste principal único a 10 años de diciembre, con las bandas congeladas; por activo, descriptivo; la regla de §5.5 |
| V8 | activar | con V1-V7 aprobadas: `MEDIDAS_NUEVAS_APROBADAS = True` en un commit propio, antes de 2028-03 |

## 8. Límites
- La continuidad con JST solo se mide en ≤ 2004, con años naturales, a veces con pocos años (bonos: PRT 11, ITA 13;
  oro del euro: 5). Las ventanas del registro que no van de enero a diciembre (descriptivas) usan para la vivienda una
  aproximación al trimestre.
- La potencia supone la estructura de choques comunes de ≤ 2004 y un abanico calibrado para la marginal. Si el motor
  anticipa parte del choque común, el efecto de diseño baja y las bandas son conservadoras (demasiado anchas). Si los
  choques futuros están más concentrados (el oro, siempre), son optimistas.
- El alquiler en vivo depende de una sola fuente, el RPI de la OCDE, que ya se ha parado en USA. El ancla de 2004 lleva
  el error del rent_yd de JST.
- El efecto de diseño de S5 (6) hace que 14 países × 5 activos valgan como ≈ 11-12 observaciones independientes al
  año. Ninguna regla de evaluación cambia eso: solo lo arregla el tiempo.
