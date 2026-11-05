# Deriva de revisión OCDE ≤ 2004: umbrales y respaldo de la instantánea (propuesta v1, 5-nov-2026)

**Estado: PROPUESTA, pendiente de aprobación del usuario** (las dos decisiones que quedaron abiertas en la opción 1 del
4-nov; `docs/int/INT8b_nowcast.md` §6). Código: `src/report/revisiones.py` (umbrales), `src/intl/data.py` (respaldo),
`scripts/instantanea_respaldo.py`; tests: `tests/test_deriva_revisiones.py`, `tests/test_instantanea_respaldo.py`.

Nada de esto toca las referencias congeladas (INT-8b, termómetro) ni la instantánea: la deriva solo **mide** y el
respaldo solo **copia** con el mismo sha256.

## 1. Deriva medida (instantánea del 26-oct frente a `obs_latest` del 5-nov, solo ≤ 2004)

Comparación en la transformación que usa el proyecto (`src/intl/panel.py`, `src/intl/termometro.py`): interanual en
log ×100 para los índices que solo se usan así; nivel para tipos, paro, CLI y confianza (estos dos se usan en nivel).
El **nivel** de la IP y de las ventas no se compara: en la instantánea se ancló al de hoy al reconstruirla (manifiesto,
`no_visible_en_cache`), así que su diferencia de nivel es un artefacto.

| Familia | Series | Revisadas | Métrica | \|Δ\| máx (serie) | Distribución de los meses revisados |
|---|---|---|---|---|---|
| IP | 16 | 7 | pp interanual | **0,76** (GBR, 1990-10) | GBR 655/672 meses, mediana 0,09, p90 0,25; BEL 0,20 (21 meses, 2000-2004); ESP 0,11, SWE 0,12, FIN 0,10 (≤ 15 meses: un dígito del índice); ITA 0,09 (583 meses, mediana ≈ 0); FRA 0,01 |
| Ventas | 17 | 2 | pp interanual | 0,20 (GBR, 1988-05) | GBR 24 meses 1988-2003, mediana 0,18; DNK 406 meses de 1e-4 (ruido de decimales) |
| Paro | 17 | 2 | pp nivel | 0,10 (IRL, ITA) | 3 meses en total, exactamente un dígito (0,1) |
| Tipos (10 a, 3 m, oficial) | 52 | 1 | pp nivel | 0,02 (BEL 10 a) | 162 meses, mediana 0,003, p90 0,005 (redondeo a 2-3 decimales) |
| IPC y subyacente | 34 | 0 | pp interanual | 0 | — |
| Bolsa OCDE | 18 | 0 | pp interanual | 0 | — |
| CLI | 9 | 0 | puntos | 0 | — |
| Confianza (BCI) | 18 | 0 | puntos | 0 | — |
| PIB trimestral | 18 | 0 | pp interanual (trim.) | 0 | — (warehouse y capa curada idénticos a la instantánea) |
| Crédito/PIB (BIS), AQR, JST, USREC | 53 | 0 | nivel | 0 | — |

Ninguna serie pierde ni gana fechas ≤ 2004; ningún cambio de base. Efecto: **0 de 127** percentiles del nowcast y
**0 de 90** del termómetro cambiarían si se recalcularan las referencias con los datos de hoy.

Escala de referencia (σ ≤ 2004 de la transformación en el país con menos variación; mediana entre paréntesis):
IP 3,9 (5,4) pp; ventas 1,9 (3,4); IPC 1,7 (3,8); bolsa 14,5 (21); PIB 1,8 (2,5) pp interanual; CLI y confianza
≈ 1,3-2,0 puntos de nivel; Δ12 de tipos 1,2 (1,2-2,2) pp; Δ12 de paro 0,9 pp; crédito/PIB Δ4 trimestres 4,8 pp.

**Limitación:** solo hay **un** episodio de revisión observado (el 2-nov); `raw/oecd` se sobrescribía y el warehouse no
guarda añadas de la OCDE. La distribución es la de los meses dentro de ese episodio, no la de muchos episodios. Desde el
4-nov la ingesta archiva cada descarga fechada (`raw/<fuente>/archivo/`), así que con unos meses de datos se podrán
recalibrar los umbrales con varias revisiones.

## 2. Umbrales propuestos (a aprobar)

Regla simple, por serie, sobre el |Δ| máximo en la métrica de su familia (estrictamente mayor):
- **ok**: no supera «aviso» (retoques de la última cifra publicada).
- **aviso**: supera «aviso» → se informa en el test (warning) pero **no falla**. Es una revisión normal (reestimación
  de la desestacionalización, rebase con decimales).
- **fallo**: supera «fallo» → **el test falla** y se decide a mano (nueva instantánea y nueva congelación declarada,
  o no). Es el orden de un cambio de base, de definición o de fuente.

Criterio: «aviso» justo por encima del redondeo con el que publica la fuente; «fallo» ≈ 0,2-0,3 σ (mínima por familia)
de la transformación usada, que es lo que empieza a mover percentiles y signos (K5: IP cerca de 0).

| Familia | Métrica | Aviso > | Fallo > | Medido 2-nov | Por qué |
|---|---|---|---|---|---|
| Tipos (irlt, ir3m, ircall, cbpol) | pp nivel | 0,05 | 0,25 | 0,02 → ok | 2-3 decimales; 25 pb ≈ 0,2 σ de Δ12; un cambio de bono de referencia mueve decenas de pb |
| Paro | pp nivel | 0,10 | 0,25 | 0,10 → ok | Se publica con 1 decimal: un dígito no avisa; 0,3 (3 dígitos) ≈ 0,3 σ de Δ12 |
| IPC, subyacente | pp interanual | 0,05 | 0,30 | 0 → ok | El IPC casi nunca se revisa; 0,3 ≈ 0,17 σ; un rebase puro no mueve la interanual (aviso aparte) |
| IP | pp interanual | 0,25 | 1,0 | **0,76 (GBR) → aviso** | Un dígito del índice ≈ 0,1-0,2; 1 pp ≈ 0,26 σ y puede cambiar el signo cerca de 0 (K5) |
| Ventas | pp interanual | 0,25 | 0,50 | 0,20 → ok | σ mínima 1,9: 0,5 ≈ 0,26 σ |
| Bolsa OCDE (share) | pp interanual | 0,50 | 3,0 | 0 → ok | σ 14,5-21; 3 pp ≈ 0,2 σ |
| CLI | puntos nivel | 0,05 | 0,30 | 0 → ok | Se usa en nivel (y Δ6): un rebase SÍ importa → cuenta como diferencia de nivel |
| Confianza (BCI/CCI) | puntos nivel | 0,05 | 0,30 | 0 → ok | Ídem CLI |
| PIB trimestral | pp interanual (trim.) | 0,10 | 0,50 | 0 → ok | Revisiones benchmark de cuentas nacionales: 0,1-0,5 normales; σ mínima 1,8 |
| Crédito/PIB (BIS) | pp PIB nivel | 0,50 | 2,0 | 0 → ok | Se usa en Δ20 trimestres (decenas de pp); cambia con las revisiones del PIB |
| AQR mercado | pp rent. mensual | 0,05 | 0,50 | 0 → ok | Rentabilidades CRSP/MSCI: retoques pequeños; 0,5 pp en un mes ya es otra fuente |
| JST eq_dp | ratio | 0,0005 | 0,005 | 0 → ok | Versión fija R6: no debería cambiar |
| USREC | 0/1 | 0 | 0 | 0 → ok | Cualquier cambio de fechado NBER → fallo |

Reglas de estructura (independientes de la magnitud):
- Fechas ≤ 2004 que **desaparecen** hoy → **fallo** (rotura: serie recortada o discontinuada).
- Fechas ≤ 2004 **nuevas** (alargada hacia atrás) → aviso.
- **Cambio de base puro** en una serie usada solo en interanual (log(hoy/instantánea) constante, rango ≤ 0,01 % y
  media ≠ 0) → aviso (inocuo para la interanual). En CLI/confianza/tipos el rebase aparece como diferencia de nivel y
  sigue la tabla.

Efecto en percentiles publicados hoy (nowcast INT-8b y termómetro): **aviso** si alguno cambia ≥ 1 punto; **fallo** si
alguno cambia ≥ 3 puntos o pasa de nulo a no nulo. *Cambio respecto al 4-nov:* antes cualquier punto fallaba. Un punto
lo puede mover cualquier revisión pequeña con el valor de hoy cerca de una frontera; 3 puntos ya es un desplazamiento
de la distribución de referencia.

Con estos umbrales hoy: estado **AVISO** (solo IP GBR), 0 fallos → el test pasa. Con los anteriores (4-nov) también
pasaba; los nuevos separan además «revisión notable» (aviso) de «retoque» (ok).

**El usuario debe aprobar:** (a) la tabla de umbrales por familia; (b) las reglas de estructura; (c) relajar el de
percentiles de «≥ 1 falla» a «≥ 1 avisa, ≥ 3 falla» (alternativa: mantener ≥ 1 falla); (d) recalibrar dentro de 6
meses con el archivo de descargas fechadas.

## 3. Respaldo de la instantánea (implementado)

La instantánea **no se puede regenerar**: se reconstruyó invirtiendo la caché del 26-oct frente al warehouse del 4-nov
(`scripts/instantanea_dev_2004.py`), y ese warehouse ya no existe. Por eso, dos copias con el mismo sha256:

| Copia | Dónde | Tamaño | Papel |
|---|---|---|---|
| Archivo | `$FIN_DATA_ROOT/intl/snapshots/dev_le2004_20261026.parquet` (solo lectura) | 742 KB | La que se lee normalmente |
| Respaldo | `research/int/snapshots/dev_le2004_20261026.parquet.xz` (en git → también en origin) | 437 KB | Copia fuera de `~/financial_archive`, versionada |

El manifiesto (`research/int/instantanea_dev_2004.json`) añade `respaldo`: ruta (relativa al repo), `sha256_xz`,
`bytes_xz`, formato y fecha. `sha256` del parquet sigue igual (`e95f7fb6…65d0`).

**Verificación al cargar** (`src/intl/data.leer_instantanea` / `connect_instantanea`):
1. Si el archivo existe y su sha256 = manifiesto → se usa.
2. Si falta o no coincide → se lee el respaldo: sha256 del .xz = `respaldo.sha256_xz` **y** sha256 del parquet
   descomprimido = `sha256` del manifiesto; se emite `InstantaneaDesdeRespaldo` (warning) con la orden de restaurar.
3. Si ninguno vale → `InstantaneaNoDisponible` (los tests de reproducción se saltan, como antes).
Comprobado: con `$FIN_DATA_ROOT` vacío, las reproducciones exactas de INT-8b y del termómetro pasan desde el respaldo.

**Restauración:** `.venv/bin/python scripts/instantanea_respaldo.py restaurar` reescribe el archivo desde el respaldo
(atómico, 0o444) solo si falta o está corrupto; nunca toca una copia válida; la corrupta se aparta como
`<nombre>.corrupta-<fecha>`, no se borra. `verificar` informa del estado de las dos copias (sale con 1 si alguna
falla); `respaldar` crea el respaldo una vez desde un archivo válido (ya hecho).

**`load_dev` no se rompe:** la ruta por defecto (warehouse) no lee la instantánea; un test lo comprueba con el manifiesto
apuntando a un archivo inexistente.

Pendiente opcional (no implementado): ejecutar `instantanea_respaldo.py verificar` en el trabajo semanal de launchd.
