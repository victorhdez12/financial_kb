---
documento: INT-8b — nowcast mensual DESCRIPTIVO de recesión (alternativa del §5 de docs/int/INT8_diseno_v0.md)
version: 1.0 (2026-10-30)
estado: CONSTRUIDO. Informativo; no confirmatorio; no es una señal de cartera.
regla: docs/int/INT8b_regla_v1.md (congelada en 88ae9be, antes de escribir código y sin ver resultados)
codigo: src/intl/int8b.py (funciones puras), src/report/nowcast_vivo.py (en vivo), scripts/int8b_corrida.py (referencias ≤ 2004 y gráfico), tests/test_intl_int8b.py
salidas: research/int/int8b_referencias.json (commit e53b7fb, árbol limpio), research/int/graficas/int8b_ilustracion.png
---

# INT-8b: ¿está empezando ya una recesión, o empezará en 0-3 meses? (nowcast descriptivo)

> **Informativo, no es una señal de cartera.** El resultado es una **banda** (bajo / medio / alto / muy alto) y un
> percentil frente a la historia 1960-2004 de cada país. **Nunca** es una probabilidad de recesión a 3 meses.

## 1. Qué es
Un "termómetro de coincidencia": junta seis indicadores **ya conocidos** (no se buscó ninguno nuevo) y dice si su
combinación está, frente a la propia historia del país, en una zona parecida a la de las recesiones pasadas.

| clave | indicador | por qué está |
|---|---|---|
| K1 | curva 10a−3m (media 12 m) | adelantado clásico (INT-4, Estrella-Mishkin) |
| K2 | difusión de curvas invertidas | INT-4 (C4) |
| K3 | bolsa real 12 m | INT-4 (C6) |
| K4 | Δ5 años crédito/PIB (BIS) | INT-4 (C2) |
| K5 | difusión de la producción industrial (% de los otros países del núcleo con IP interanual < 0) | coincidente: "¿ya está pasando?" |
| K6 | regla tipo Sahm con el paro (media 3 m − mínimo de 12 m previos) | coincidente |

**Cómo se combina (congelado):** cada indicador se convierte en su percentil frente a los meses 1960-2004 del propio país
(orientado: alto = más parecido a una recesión); el índice del país es la **media con pesos iguales** (≥ 4 de 6); su
percentil frente a la historia del índice da la banda (< 50 bajo, 50-80 medio, 80-95 alto, ≥ 95 muy alto). El agregado es
la media del núcleo (≥ 10 de 14 países). Ningún peso ni umbral se estimó con el objetivo.

El **fechado trimestral en vivo** (la suma de 4 trimestres del PIB cae dos trimestres seguidos) se enseña al lado como
"confirmado por el PIB, con retraso", pero **no entra en el índice**: es justo lo que el índice intenta ver antes.

Dónde se ve: sección **5c** del reporte semanal (`src/report/weekly.py`), justo después del termómetro (5b). Si falla, el
reporte sale igual y lo dice. El JSON de la señal guarda el resultado de cada semana (eso será el registro en vivo).

## 2. Qué NO demuestra
- **Nada sobre su capacidad de anticipar.** No se calculó ningún acierto (ni AUC, ni tasas) con datos ≤ 2004, a propósito:
  el estudio de potencia de INT-8 (§2-3) mostró que con 11-22 episodios no se puede demostrar un efecto realista a 3-6
  meses. Medirlo aquí solo invitaría a afinar.
- **No es una probabilidad.** "Percentil 90" significa "el 90 % de los meses 1960-2004 de este país tuvieron un índice
  más bajo", no "90 % de probabilidad de recesión".
- **Pesos iguales no significa "los mejores pesos"**: significa "sin elegir pesos". Es deliberado.
- Las bandas comparan con la historia del propio país; un país con historia corta (p. ej., paro desde 1998) tiene
  referencias más pobres. Si un indicador tiene < 60 meses de historia ≤ 2004, no cuenta (p. ej., la curva de JPN o CHE).

## 3. Contaminación (declarada)
- Los seis indicadores se eligieron **sabiendo** que funcionaron en 1974-75, 1980-82, 1990-93 y 2001-03 (INT-4, el
  termómetro y la literatura). Cualquier parecido entre el índice y las recesiones 1960-2004 es **réplica**, no prueba.
- El gráfico `research/int/graficas/int8b_ilustracion.png` (agregado del núcleo con los meses en que ≥ 1/3 del núcleo está
  en recesión según el fechado; EE. UU. con las recesiones NBER, usadas solo como contraste externo) es **solo una
  ilustración contaminada** para ver qué mide el índice. No se sacó de él ninguna cifra ni se cambió nada después de verlo.
  El agregado empieza en 1982-12 porque antes no hay ≥ 10 países con índice (la curva de muchos países es corta).
- Datos ≤ 2004 revisados (no de primera publicación); en vivo, `obs_latest` sin vintages (igual que el termómetro).
- Ejecución: una sola corrida de referencias (`e53b7fb`); se repitió una vez solo para que el título del gráfico no saliera
  cortado (las referencias salen idénticas; registrado en research/trial_log.md).

## 4. Detalles prácticos (en vivo)
- Datos: OCDE (tipos, IPC, bolsa, IP, paro, PIB) y BIS (crédito) del warehouse, con los retrasos "as of" de
  `src/intl/lags.py` y la carga de `src/report/termometro_vivo.py` (incluido el empalme declarado del tipo a 3 m de GBR).
- Las distribuciones de referencia están **congeladas** (solo datos ≤ 2004) y un test comprueba que la carga en vivo
  cortada en 2004-12, sobre la instantánea ≤ 2004 con la que se congelaron, las reproduce exactamente (§6).
- Huecos: la regla tipo Sahm exige 15 meses seguidos de paro; si falta un mes (EE. UU. no tiene 2025-10 por el cierre del
  Gobierno federal), K6 sale «—» hasta que el hueco salga de la ventana (≈ 2027-01) y el índice usa los otros cinco.
- Observación (no es un resultado): en 2026 el crédito/PIB lleva años bajando en casi todos los países, así que K4 está en
  percentil ≈ 0 frente a 1960-2004 y tira el índice hacia "bajo". Es una consecuencia conocida de usar la historia de
  antes de 2005 como referencia; no se corrige (la regla está congelada).

## 5. Cómo se evaluará en vivo (y cuánto tardará)
Regla de evaluación fijada **ahora**, antes de ningún dato en vivo, solo descriptiva:
1. **Episodio en vivo:** cada entrada en recesión de un país del núcleo según el fechado trimestral (trimestre q), a partir
   de 2026-11. Entradas de varios países a ≤ 6 meses se agrupan en un episodio.
2. **Aviso a tiempo:** la banda del país fue "alto" o "muy alto" en algún fin de mes entre el inicio del trimestre q − 1 y
   el fin del trimestre q (la ventana "empezando ya o en 0-3 meses"), **tal como salió en el reporte de esa semana**
   (JSON de la señal; nunca recalculado después).
3. **Falsas alarmas:** tramos de ≥ 3 meses seguidos en "alto/muy alto" sin entrada del país en los 6 meses siguientes.
4. Se informa por episodio (avisados / no avisados) y las falsas alarmas por país-década. No hay puerta ni umbral de éxito:
   es seguimiento, no prueba.

**Cuánto tiempo hará falta:** con ≈ 3,6 episodios agrupados por década (INT-8 §2), hacen falta **≈ 28 años para 10
episodios** y ≈ 56 para 20. Con 10 episodios, una tasa de aviso observada del 70 % tendría un IC 95 % ≈ [35 %; 93 %]:
apenas distinguible del azar. **Antes de ≈ 2050 no habrá base para decir si anticipa.** Hasta entonces, se lee como lo
que es: un resumen ordenado de indicadores conocidos.

## 6. Revisiones de datos (4-nov-2026; decisión del usuario, opción 1)
**Qué pasó.** En la ingesta semanal del 2-nov la OCDE revisó **en origen** series ≤ 2004: tipo a 10 años de BEL (162
meses, ≤ 0,02 pp), producción industrial de GBR, ITA, BEL, ESP, FIN, FRA y SWE (interanual hasta 0,76 pp en GBR), paro de
IRL e ITA (3 meses, 0,1 pp) y ventas de DNK y GBR. El código no cambió, pero los tests que recalculaban las referencias con
el warehouse de cada día (este y el del termómetro) dejaron de reproducirlas. `raw/oecd` se sobrescribía: no quedaba
ninguna descarga anterior; sí la caché del panel mensual de desarrollo del 26-oct (`$FIN_DATA_ROOT/intl/
panel_mensual_dev.parquet`, sha256 `e8ac5a6c…9615`).

**Decisiones.**
1. **Las referencias congeladas siguen siendo la verdad.** No se recalculan ni se tocan (`research/int/
   int8b_referencias.json`, `research/int/termometro_referencias.json`).
2. **Instantánea fechada e inmutable** de las series ≤ 2004 de la congelación: `$FIN_DATA_ROOT/intl/snapshots/
   dev_le2004_20261026.parquet` (fuera del repo, solo lectura; 252 series con datos, 95 755 filas: OCDE mensual y PIB
   trimestral, BIS, AQR, JST eq_dp, USREC). Manifiesto en el repo: `research/int/instantanea_dev_2004.json` (ruta, sha256,
   fecha, procedencia, series restauradas, lo que la caché no ve). La construye `scripts/instantanea_dev_2004.py`: parte
   del warehouse de hoy ≤ 2004, detecta las series revisadas comparando `panel.mensual` con la caché y, solo en esas,
   restaura el valor previo invirtiendo la caché (niveles con retraso; índices por su interanual; último mes del tipo a
   10 años desde `r_bono`). No escribe nada si `panel.mensual` con la instantánea no es idéntico a la caché en todas las
   columnas (|Δ| ≤ 1e-12) o si no reproduce las referencias congeladas de INT-8b **y** del termómetro con la tolerancia
   de los tests (1e-12 en distribuciones; 1e-9 en índice y agregado). Resultado: diferencia máxima 0 en ambas.
   Límites declarados: lo que la caché no ve (paro interpolado de antes de 1998 de los 9 países excluidos, los últimos
   meses de 2004 de las series con retraso, el **nivel** de la IP y de las ventas —solo se usa su interanual—, PIB y BIS,
   que no están en la caché pero quedan verificados por la reproducción exacta) se queda con el valor del 4-nov.
3. **Dos tests, por separado:**
   - *Reproducción* (`tests/test_intl_int8b.py::test_referencias_congeladas_reproducidas_desde_instantanea`,
     `::test_ruta_de_desarrollo_lee_la_instantanea` y `tests/test_termometro_vivo.py::
     test_referencias_congeladas_igual_a_recalculadas`): recalcula desde la instantánea (sha256 comprobado) y compara con
     las congeladas. Debe pasar siempre; si falta el parquet, se salta.
   - *Deriva de revisión* (`tests/test_deriva_revisiones.py`, `src/report/revisiones.py`): compara el warehouse de hoy
     ≤ 2004 con la instantánea y **avisa** con las magnitudes por serie; solo **falla** si la diferencia es grande:
     |Δ| > 0,10 pp en tipos o paro (la OCDE publica 2-3 decimales: los retoques de redondeo no llegan; más ya es un
     cambio de fuente o de definición), > 1 pp en la interanual de un índice o en crédito/PIB (1 pp ya puede cambiar el
     signo de la IP cerca de 0, K5), o **cualquier** percentil entero publicado hoy (nowcast: agregado, índice e
     indicadores; termómetro: percentil ≤ 2004 de cada indicador) que cambiaría si se recalcularan las referencias con
     los datos de hoy. Medido el 4-nov: 12 series revisadas, ninguna grande; 0 de 127 (nowcast) y 0 de 90 (termómetro)
     percentiles cambiarían. Si un día falla, se decide a mano (nueva instantánea y nueva congelación declarada, o no).
     **5-nov (propuesta pendiente de aprobación):** umbrales por familia con dos niveles, aviso y fallo, en la
     transformación que usa cada indicador, reglas de rotura y respaldo de la instantánea en el repo (xz, mismo sha256,
     lectura con caída al respaldo y `scripts/instantanea_respaldo.py restaurar`): `docs/int/OCDE_deriva_umbrales.md`.
4. **Ruta de desarrollo.** `src/intl/data.connect(fuente="instantanea")` (o `FIN_DEV_FUENTE=instantanea`) abre la
   instantánea con la misma interfaz que el warehouse; `load_dev` falla si se pide una serie que no cubre y
   `load_dev_curado` lee de ella el PIB trimestral. `scripts/int8b_corrida.cargar_dev(fuente=...)` y
   `scripts/termometro_puerta.cargar(fuente=...)` (el anual JST, versión fija R6, sigue del warehouse) la aceptan.
5. **Archivo del raw.** La ingesta de la OCDE (`src/ingest/oecd.py`, `src/ingest/oecd_qna.py`) guarda además cada
   descarga nueva comprimida y fechada en `raw/<fuente>/archivo/<nombre>_<AAAA-MM-DD>.csv.gz`, con índice
   `archivo/indice.jsonl` (sha256; las idénticas no se duplican). Retención (`src/ingest/_archivo_raw.py`): todas las
   copias de los últimos 730 días y, de las anteriores, la primera de cada mes (≈ 2,5 MB por juego semanal; ≈ 130 MB al
   año). La próxima revisión en origen se podrá reconstruir desde ahí sin invertir cachés.
