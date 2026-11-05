---
documento: INT-11 — fuente de la bolsa en vivo (D9) para evaluar el registro mensual
version: 1.0 (2026-11-05) — APROBADA por el usuario (A1-A7, con las recomendaciones de §7); registro de la serie v3.1 activado
parte_de: docs/int/INT11_registro_vivo.md §3 · docs/int/INT11_prerregistro_v2.md (D9) · docs/int/INT11_prerregistro_v3.md §8
código: src/report/bolsa_vivo.py (lectura, funciones puras) · tests/test_bolsa_vivo.py ·
        scripts/int11_fuente_bolsa.py (mediciones → research/int/int11_fuente_bolsa.json) ·
        scripts/int11_v2_hoy.py --ensayo (ensayo del registro, no escribe nada) · src/report/registro_vivo.py (comprobaciones_ensayo)
---

# Fuente de la bolsa en vivo para el registro de INT-11

## 0. Resumen
- **Principal:** AQR "MKT" por país (rentabilidad total mensual en USD, en exceso de la letra de EE. UU.) + la letra
  de AQR → rentabilidad total en USD → **moneda local** con el tipo de cambio de **fin de mes** de FRED H.10. Cubre los
  14 países y llega con ≈ 2-3 meses de retraso. Frente a JST `eq_tr` (1986-2004, anual) tiene una correlación mediana de
  **0,987**, un sesgo de **−0,6 pp** y una dt de la diferencia de **4,2 pp** (12 países; JPN y DNK aparte, ver §4.3).
- **Respaldo (rápido, oficial):** índice de cotizaciones OCDE (precio, media mensual) × (1 + dividendo implícito). El
  dividendo implícito es la media de TR/precio de los 10 años naturales anteriores a la ventana. Sin dividendo, el
  sesgo es −3,4 pp; con él, ≈ 0. Cubre los 14 países y llega con ≈ 1-2 meses de retraso.
- **Contraste (anual):** Ken French, *International Research Returns*, por país, en moneda local, con y sin dividendos
  (12 de 14 países: faltan PRT y USA; USA = French `Mkt-RF + RF`). Frente a AQR coincide casi exactamente (12 meses
  móviles: correlación 0,997, sesgo −0,2 pp, dt 1,5 pp).
- **Deflactor:** IPC OCDE, media de los 12 meses de la ventana / media de los 12 anteriores. Es el mismo criterio que
  JST (inflación de la media anual) y que K2.
- **Hallazgo que hay que decidir:** el `eq_tr` de JST para **JPN** está calculado con **medias anuales** de precios
  (correlación 0,999 con el cambio de la media anual y 0,70 con diciembre-diciembre). En **DNK** pasa lo mismo hasta
  ≈ 1994. El motor se entrenó con una bolsa japonesa suavizada (dt 1986-2004 JST 20,7 % frente a 24,2 % de diciembre a
  diciembre), y ninguna fuente viva mide eso (§4.3, decisión A4).

## 1. Qué exige el registro (leído del código y de los documentos)
| aspecto | exigencia | dónde |
|---|---|---|
| países | los 14 del núcleo: BEL DEU DNK ESP FIN FRA GBR ITA JPN NLD NOR PRT SWE USA | `scripts/int11_corrida.NUCLEO` |
| frecuencia | emisión mensual (día 20); ventana = 12 meses desde el mes siguiente (`E.ventana_objetivo`); hace falta un **nivel mensual de fin de mes** (o rentabilidades mensuales) | registro_vivo.md §2-3 |
| precio o total | **rentabilidad total** (con dividendos), como JST `eq_tr` | registro_vivo.md §3, prerregistro v2 D9 |
| divisa | **moneda local** (las de antes del euro, encadenadas con el euro) | prerregistro v3 §1 |
| real / nominal | **real**: (1 + nominal)/(1 + inflación) − 1, como `jst_*_eq_tr_real`, deflactada con el IPC OCDE | registro_vivo.md §3; `src/ingest/jst_macrohistory.py` |
| uso | dentro o fuera del p5-p95 guardado y PIT con los percentiles 1-99, por ventana y país | registro_vivo.md §3 |

## 2. Inventario: lo que ya está en el warehouse (`obs_latest`, 2026-11-05)
| serie | países del núcleo | contenido | fin de mes / media | último dato (retraso) | licencia | ¿vale como fuente? |
|---|---|---|---|---|---|---|
| `aqr_mkt_<p>_m` (+ `aqr_rf_risk_free_rate_m`) | 14/14 (1986-; PRT 1986-08; USA 1926) | TR en USD, exceso sobre la letra de EE. UU., ponderado por capitalización | fin de mes | 2026-08 (≈ 66 días) | AQR: uso interno, **no redistribuir** | **principal** |
| `oecd_share_<p>` | 14/14 (BEL y ESP desde 1985, NOR 1986, PRT 1988) | índice de **precio**, base 2015; FRA, NOR y PRT se comportan como TR en algunos tramos | **media mensual** | 2026-09 (≈ 36 días) | CC BY 4.0 | **respaldo** (con dividendo) |
| `jkp_<p>_mkt_m` | 7/14 ingeridos (DEU ESP FRA GBR ITA NLD USA); la fuente tiene todos | TR en USD, exceso, `vw_cap` (pesos topados) | fin de mes | 2025-12 (≈ 10 meses; anual) | CC BY-NC 4.0 | no: los pesos topados se alejan de la referencia (§4) |
| `ff_mkt_rf_m`, `ff_rf_m` (French EE. UU.) | USA | TR (CRSP), USD | fin de mes | 2026-09 | French: investigación, citar | respaldo de USA |
| `shiller_nominal_stock_tr_ret_m` | USA | TR del S&P con precios medios mensuales | media | 2026-10 | Shiller: investigación, citar | contraste de USA (es casi JST: correlación 1,000) |
| `damodaran_sp500_tr` | USA | TR anual por años naturales | fin de año | 2025 (anual, enero) | educativo, citar | solo años naturales |
| `SP500` (FRED) | USA | precio, desde 2016 (FRED solo da 10 años por la licencia de S&P) | diario | 2026-11-03 | S&P vía FRED | no (precio, historia corta) |
| `boe_uk_share_prices_m` | GBR | precio | media | **2017-02 (cortada)** | BoE | no |
| `DEX*` FRED (H.10) | divisas: GBP JPY EUR (y CHF CNY) en el warehouse; **DKK NOK SEK no** | tipo de cambio diario | — | 2026-10-30 | dominio público (Fed) | divisa de la principal (DKK/NOK/SEK se bajan de FRED; ver §6) |
| `bis_xru_*_m` | parciales | tipo de cambio **medio** mensual | media | — | BIS | no (hace falta el de fin de mes) |

## 3. Opciones externas gratuitas
| fuente | países | TR / local | retraso | términos | estabilidad / riesgo de corte |
|---|---|---|---|---|---|
| **Ken French, International Countries** (`F-F_International_Countries[_Wout_Div].zip`) | 12/14 (sin PRT; USA en la biblioteca principal) | TR **y** precio, en local y en USD, mensual desde 1975 | **anual** (datos a 2025-12) | investigación, citar | biblioteca estable desde hace décadas; poco riesgo, pero se actualiza una vez al año |
| JKP (jkpfactors.com), todos los países | 14/14 | TR en USD, `vw_cap` | anual | CC BY-NC 4.0 | nuevo (2023); se aleja de la referencia por los pesos topados |
| FRED H.10 `DEXDNUS DEXNOUS DEXSDUS DEXJPUS DEXUSUK DEXUSEU` | divisas de los 14 | tipo de cambio diario (cierre del mediodía en NY) | ≈ 1 semana | dominio público | muy estable; respaldo: tipos de referencia del BCE (API SDMX, libre) |
| Bundesbank (CDAX/DAX *performance*) | DEU | TR local | días | libre con cita | un solo país |
| Nasdaq Nordic GI / OSEBX / Euronext GR | Nórdicos, BEL, NLD, FRA, PRT | TR local | días | web sin API ni licencia clara de reutilización | se rompe al cambiar la web: no recomendado |
| MSCI países (GR/NR local) | todos | TR local (es el estándar) | días | **comercial**: la web no permite la descarga sistemática | no es libre |
| Yahoo / Stooq / ETF iShares | variados | mixto | días | términos restrictivos o inestables | no recomendado |
| FMI IFS share prices | varios | precio, media | meses | libre | el FMI rehízo IFS en 2024-25 y hay series dadas de baja: riesgo alto |

## 4. Mediciones (`scripts/int11_fuente_bolsa.py` → `research/int/int11_fuente_bolsa.json`)
Rentabilidades **nominales en moneda local** por años naturales (enero-diciembre). Cada celda da correlación /
sesgo (fuente − referencia, pp) / dt de la diferencia (pp). Hasta 2004 se compara con JST, leído con `load_dev` y
convertido de USD a local con `jst_*_xrusd`, que es de fin de año (comprobado contra FRED). Desde 2005 solo se comparan
fuentes vivas entre sí: no se lee JST ≥ 2005 ni ningún resultado del motor.

| país | AQR→local vs JST 1986-2004 | French TR local vs JST 1975-2004 | OCDE precio + dp constante vs JST 1986-2004 | AQR vs French, 12 m móviles 2005-2025 | AQR vs OCDE + div. implícito, 2015-2025 | div. implícito OCDE 2005-14 |
|---|---|---|---|---|---|---|
| BEL | 0.986 / -0.0 / 4.2 | 0.987 / +2.5 / 3.7 | 0.989 / -0.8 / 3.5 | 0.994 / +1.1 / 2.5 | 0.942 / -2.9 / 5.0 | 4.9 % |
| DEU | 0.978 / -1.1 / 5.2 | 0.989 / +1.0 / 4.2 | 0.982 / -1.5 / 4.8 | 0.992 / -0.1 / 2.3 | 0.954 / +0.6 / 4.1 | 2.2 % |
| DNK | 0.669 / +1.3 / 19.4 | 0.724 / -1.1 / 16.2 | 0.732 / +0.2 / 16.5 | 0.993 / +0.5 / 2.6 | 0.962 / -0.2 / 5.1 | 3.0 % |
| ESP | 0.954 / -1.9 / 9.7 | 0.933 / +0.8 / 10.9 | 0.946 / -1.8 / 10.4 | 0.996 / +0.4 / 1.8 | 0.973 / +0.5 / 4.3 | 3.8 % |
| FIN | 0.999 / -1.1 / 2.7 | 0.989 / +0.7 / 7.9 | 0.989 / +0.2 / 7.7 | 0.999 / -0.3 / 1.0 | 0.968 / -0.3 / 3.5 | 4.3 % |
| FRA | 0.989 / -0.8 / 4.0 | 0.977 / +2.4 / 5.8 | 0.978 / +0.5 / 5.7 | 0.999 / -0.0 / 0.8 | 0.986 / -0.7 / 2.4 | 4.0 % |
| GBR | 0.995 / -0.7 / 1.7 | 0.998 / -0.2 / 2.2 | 0.978 / -0.3 / 3.3 | 0.996 / -0.2 / 1.3 | 0.932 / +0.2 / 4.3 | 3.6 % |
| ITA | 0.989 / -1.9 / 4.3 | 0.981 / +1.1 / 6.9 | 0.976 / -1.7 / 6.5 | 0.998 / -0.2 / 1.4 | 0.984 / -0.6 / 3.2 | 3.8 % |
| JPN | 0.617 / +1.3 / 21.4 | 0.622 / +1.6 / 18.0 | 0.703 / +0.6 / 17.7 | 0.999 / -0.3 / 1.1 | 0.982 / +0.5 / 2.7 | 1.9 % |
| NLD | 0.998 / -0.6 / 1.6 | 0.993 / +0.2 / 2.6 | 0.989 / +0.2 / 3.4 | 0.992 / -0.9 / 2.5 | 0.923 / +0.1 / 6.5 | 4.5 % |
| NOR | 0.977 / +1.8 / 7.1 | 0.844 / +1.3 / 21.8 | 0.982 / +1.7 / 5.9 | 0.997 / +0.4 / 1.6 | 0.906 / -0.1 / 3.4 | -0.0 % |
| PRT | 0.988 / +0.3 / 4.3 | — | 0.997 / +0.4 / 2.2 | — | 0.969 / +1.0 / 3.0 | -0.5 % |
| SWE | 0.986 / -0.0 / 5.5 | 0.991 / +0.6 / 3.9 | 0.989 / -0.2 / 4.7 | 0.998 / -0.2 / 1.3 | 0.980 / -0.7 / 3.7 | 3.4 % |
| USA | 0.980 / +0.0 / 4.1 | — | 0.965 / -0.4 / 4.4 | AQR vs French EE. UU.: 0.997 / -0.6 / 1.3 | 0.907 / +2.2 / 7.4 | 3.7 % |

USA ≤ 2004 frente a JST: Shiller 1,000 / +0,2 / 0,7 (JST USA es, en la práctica, Shiller); French 0,981 / +0,1 / 4,1;
Damodaran 0,988 / +0,1 / 3,1. JKP (7 países) frente a JST: mediana 0,957 / −1,0 / 7,1 (peor que AQR).

### 4.1 Continuidad con JST (≤ 2004)
- AQR→local es la fuente viva más cercana a JST (sin JPN ni DNK: mediana 0,987 / −0,6 / 4,2). ESP difiere por un año
  (1987: JST +48 %, AQR +10 %, OCDE +8 %): es cosa de JST, no de AQR.
- **Precio sin dividendos** (OCDE): sesgo de −3,4 pp de mediana, que es casi todo dividendo. Con un dividendo constante
  por país, el sesgo es ≈ 0 y la dispersión igual.
- Error de medida típico de 4 pp frente a una dispersión anual de 20-30 pp: con ruido independiente, la cobertura del
  p5-p95 baja menos de 0,5 pp (√(20² + 4²) ≈ 20,4). Un sesgo de −3,5 pp sin corregir (usar el precio a secas) la baja
  ≈ 0,5-1 pp y desplaza el PIT, así que **hay que añadir los dividendos**.

### 4.2 Continuidad entre fuentes vivas (≥ 2005)
- AQR frente a French (las dos con dividendos, en local): mensual 0,994 / 0,0 / 0,5 pp; 12 meses móviles 0,997 /
  −0,2 / 1,5 pp. Son dos construcciones distintas y coinciden: la conversión con el tipo de cambio de FRED de fin de
  mes funciona.
- AQR frente a JKP: 12 meses móviles 0,974 / −0,4 / 4,6 pp. JKP queda descartado como respaldo.
- AQR frente a OCDE solo precio: sesgo de +3,6 pp (el dividendo). Con el dividendo implícito de 2005-14 aplicado a
  2015-25: sesgo mediano ≈ 0, pero va de −2,9 (BEL) a +2,2 (USA), con una dt de 4 pp. El "dividendo" implícito absorbe
  también diferencias de composición (USA 5,6 % en 2015-24: el índice OCDE de EE. UU. no es el S&P 500).
- **El carácter TR/precio del índice OCDE no es fijo:** el código anterior (`src/intl/panel.py`) daba FRA como TR, pero
  desde 2005 se comporta como precio (+3,8 pp frente a AQR). NOR y PRT se comportan como TR (sesgo ≈ 0; NOR −5,5 pp
  frente al precio de French). El dividendo implícito lo recoge automáticamente; no hay excepciones por país.

### 4.3 Hallazgo: JST JPN (y DNK hasta ≈ 1994) usa medias anuales
Correlación de JST `eq_tr` con el cambio del precio OCDE, de diciembre a diciembre frente a media anual: **JPN**
1960-85 0,68 frente a 0,96; 1986-94 0,77 frente a 0,999; 1995-2004 0,58 frente a 0,999. **DNK** 1986-94 0,49 frente
a 0,94; 1995-2004 0,99 frente a 0,63. En el resto de países gana diciembre a diciembre (0,95-0,99). Consecuencias:
(i) el motor aprendió para JPN una bolsa más suave y con autocorrelación; (ii) una fuente de fin de mes medirá en JPN más
dispersión de la que el motor espera, lo que puede dar "fuera del abanico" que no es culpa del motor; (iii) medir JPN
con medias (media de los 12 meses de la ventana / media de los 12 anteriores) reproduciría JST, pero la mitad del
realizado se conocería en la emisión. Recomendación: medida principal de fin de mes en los 14 países (lo que gana un
inversor) más una **sensibilidad sin JPN** declarada de antemano en K1, y la medida "con medias" de JPN como
descriptiva. **Lo decide el usuario (A4).**

### 4.4 Disponibilidad (2026-11-05)
AQR hasta 2026-08 (≈ 2 meses tras el fin de mes; AQR reconstruye toda la historia en cada actualización, así que
**revisa**). OCDE (precio e IPC) hasta 2026-09. French países hasta 2025-12 (anual). FRED H.10 hasta 2026-10-30. El IPC
OCDE de **USA no tiene 2025-10** (cierre del Gobierno de EE. UU.): la lectura rellena huecos sueltos de 1 mes por
interpolación log-lineal y los declara (`ipc_interpolados`).

## 5. Recomendación
1. **Principal:** `aqr_mkt_<p>_m` + `aqr_rf_risk_free_rate_m` → TR en USD; × X(m)/X(m−1), con X = unidades locales por
   USD al último día hábil del mes (FRED H.10; EUR para los 8 países del euro). Se cumple
   1 + r_local = (1 + exceso + rf)·X(m)/X(m−1). La ventana se evalúa con sus 12 meses.
2. **Respaldo** (solo si a la principal le falta algún mes de la ventana, o deja de publicarse): OCDE
   P̄(último mes)/P̄(mes anterior a la ventana) × (1 + d). d es la media de (1 + TR AQR)/(1 + precio OCDE) − 1 de los
   10 años naturales **anteriores** a la ventana; queda fijado antes de mirarla. Nunca se mezclan fuentes dentro de una
   ventana, y la usada se registra.
3. **Contraste anual:** French países (TR local), cuando se publique el año, como control de la principal. Si en una
   ventana la diferencia con AQR es > 5 pp, se anota y no se cambia el valor.
4. **De precio a total:** solo hace falta en el respaldo (punto 2). French da además el dividendo directamente
   (TR/precio sin dividendos): 2015-25 entre 2,3 % (JPN) y 5,1 % (NOR). Puede sustituir a d si AQR desaparece.
5. **Real:** IPC OCDE con el método "media" (como JST y K2); el método "punta" se guarda como descriptivo.
6. **Al evaluar** (script futuro `scripts/int11_v2_vivo_eval.py`): guardar el valor leído, la fuente, la fecha de
   lectura y el sha256 de las series usadas, igual que la huella de las emisiones. AQR revisa la historia: lo que vale
   es lo leído en la primera evaluación.
7. **Licencia:** AQR no permite redistribuir. En el repositorio solo se guarda el realizado derivado (un número por
   país y ventana), nunca las series. Si el repositorio es público, hay que confirmarlo (A6).

## 6. Implementación (hecha, NO activada)
- `src/report/bolsa_vivo.py`, funciones puras: `tr_local_desde_usd`, `fin_de_mes`, `rent_ventana_tr`,
  `rent_ventana_precio`, `inflacion_ventana` ("media" / "punta"), `ipc_con_huecos`, `real`, `rend_div_implicito`,
  `realizado_pais` (elige principal o respaldo), `french_pais_local` (lector de los .Dat de French), `anual`,
  `comparar`. Lectura: `leer_obs` (rechaza JST), `fx_fred`, `leer_realizado(con, fx, desde, hasta)`, `plan_evaluacion`.
  Tests: `tests/test_bolsa_vivo.py` (15, sintéticos, sin red).
- **Ensayo del registro:** `.venv/bin/python -m scripts.int11_v2_hoy --ensayo`. Hace las mismas comprobaciones que
  `--registro` (fecha ± 3 días, árbol limpio fuera del registro, mes libre), pero las **anota** en lugar de abortar.
  Hace la emisión v2 completa y la huella, e imprime lo que se escribiría (ruta, sha256, ventana, países). Añade el plan
  de evaluación de la bolsa y una prueba de lectura con la última ventana de 12 meses de la principal, sin compararla
  con ningún abanico. **No escribe nada** (comprobado con `git status`). Ensayo del 2026-11-05: 14/14 países emitidos;
  ventana 2026-12 → 2027-11, evaluable con la principal desde ≈ 2028-02-29; lectura de prueba 2025-09 → 2026-08 con la
  principal en los 14 países (USA con el IPC de 2025-10 interpolado). Con el árbol sucio, la emisión real abortaría,
  como debe.
- Los tipos de cambio DKK, NOK y SEK no están en el warehouse. Las mediciones los bajan de FRED a una caché local
  (`$FIN_DATA_ROOT/raw/int11_fx_fred/`), y French países a `$FIN_DATA_ROOT/raw/int11_french_paises/`. Para el uso
  mensual conviene añadirlos al ingest de FRED (`DEXDNUS DEXNOUS DEXSDUS`; el resto ya está) y crear un ingest de French
  países (A5).

## 7. Lo que el usuario debe aprobar
| # | decisión | recomendación |
|---|---|---|
| A1 | fuente principal de la bolsa en vivo (D9) | **AQR MKT + letra AQR + divisa FRED H.10 de fin de mes** (14/14, TR, la más continua con JST) |
| A2 | respaldo y paso de precio a total | **OCDE precio × (1 + dividendo implícito de los 10 años previos)**; contraste anual con French países |
| A3 | deflactor | **IPC OCDE, media de 12 meses / media de los 12 anteriores** (como JST y K2); "punta" descriptivo; huecos de 1 mes interpolados y declarados |
| A4 | JPN (JST con medias anuales) | **medida de fin de mes en los 14 + sensibilidad K1 sin JPN declarada de antemano**; la medida "con medias" de JPN solo descriptiva |
| A5 | ingest | añadir `DEXDNUS DEXNOUS DEXSDUS` al ingest de FRED e ingerir French International Countries (anual) |
| A6 | licencia AQR | guardar en el repositorio solo el realizado derivado; confirmar si el repositorio es público |
| A7 | activar el registro (D8) | con A1-A6 aprobadas, se puede instalar la plantilla de launchd (registro_vivo.md §2), con permiso |

## 8. Límites
- La comparación con JST solo cubre 1986-2004 (19 años por país) y años naturales; las ventanas del registro van de mes
  a mes (la continuidad de 12 meses móviles solo se ha visto entre fuentes vivas).
- AQR (empresa privada) puede dejar de publicar o cambiar la construcción: para eso están el respaldo OCDE (oficial, CC
  BY, pero ya ha cambiado de TR a precio en FRA y ha cortado otras series, como el tipo a 3 meses de GBR) y French
  (anual).
- La divisa de FRED (mediodía en NY) no es exactamente la que usa AQR. El efecto medido frente a French es pequeño
  (dt mensual 0,5 pp).

## 9. Aprobación y activación (5-nov-2026)
- A1-A4 como se recomiendan. A4: JPN medido a fin de mes como los demás; **sensibilidad sin JPN declarada de antemano**
  en la evaluación del registro (la medida "con medias anuales" solo descriptiva).
- A5: `DEXDNUS DEXNOUS DEXSDUS` en `src/ingest/fred_extended.py` (entran con la actualización diaria);
  French International Countries en `src/ingest/ken_french_paises.py` (`ffc_<iso3>_<tr|precio>_m`, en el ingest semanal).
- A6: el repositorio es **público** → en git solo el realizado derivado (rentabilidad real de la ventana por país), nunca
  series de AQR ni de French.
- A7: registro mensual de la **serie v3.1** (`scripts/int11_v3_hoy.py --registro` → `research/int/int11_v3_1_vivo/`)
  con `scripts/int11_vivo_mensual.sh` y launchd `com.financialkb.int11vivo` (diario 10:30; emite a partir del día 20,
  una vez por mes). La serie v2 (`int11_vivo/`) queda sin registrar.
