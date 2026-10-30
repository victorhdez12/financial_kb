---
documento: P-DEV-INT14 v1.0 — prerregistro de la corrida de DESARROLLO del estudio de eventos A (petróleo, crisis bancaria, dólar, pico de volatilidad → bolsa, bonos, letras, vivienda, oro, materias primas)
version: 1.0 (2026-10-30) — CONGELADO en este commit, antes de escribir el código de la corrida
parte_de: docs/int/INT14_eventos_v0.md (definiciones v0, recuentos, potencia: research/int/int14_potencia.json, commit a7bb547) + borrador docs/int/INT14_prerregistro_v0.md + decisiones del usuario (30-oct, delegadas): D1-D7 aceptadas tal como se recomendaron
datos: SOLO ≤ 2004-12-31. El periodo ≥ 2005 está BLOQUEADO y no se toca
---

# P-DEV-INT14 v1.0: ¿qué les pasa a los activos tras cuatro tipos de evento? (corrida única de desarrollo)

## 0. Naturaleza de esta corrida (leer primero)
- **Una sola corrida**, datos ≤ 2004. El script (`scripts/int14_corrida.py`) se niega a correr con el árbol sucio o si
  la salida `research/int/int14_resultado.json` ya existe. Nada se cambia tras ver resultados.
- **Descriptivo-confirmatorio:** 4 contrastes principales (H1-H4) con Holm; todo lo demás es descriptivo (efecto, IC 90 %
  y p de placebo sin ajustar, con el n al lado). Ningún efecto se ha mirado antes de este documento.
- **Potencia (fase 1):** MDE 80 % a α 5 %: H1 6,9 pp (optimista; ≈ 10-12 realista), H2 8,4, H3 13,0 (20 con vol. post-pico
  × 1,5), H4 10,6 pp. "No establecido" no prueba ausencia de efecto.
- **Decisiones D1-D7 (aceptadas):** umbrales v0; los 4 contrastes; dólar solo descriptivo; NO al uso B; integración en dos
  fases (inclinación del motor INT-11 sin modificarlo, tras esta corrida; estados de evento = INT-11 v3).

## 1. Corrección declarada ANTES de congelar: lista de Hamilton (2011)
El borrador v0 y el diseño citaban la tabla 1 de Hamilton (2011, "Historical Oil Shocks", NBER WP 16790) por **años**
y avisaban de que los meses estaban "por verificar". Se ha comprobado contra el original (tabla 1, "Summary of
significant postwar events", columna *Price increase*). Diferencias con lo escrito en el diseño (§2) y correcciones:

| episodio (tabla 1) | inicio de la subida (original) | lo que decía el diseño v0 | corrección |
|---|---|---|---|
| 1947-48 | Nov 47 (Nov 47-Jan 48, 37 %) | 1947-48 | — (mes fijado: 1947-11) |
| 1952-53 | **Jun 53** (10 %); escasez May 52 | 1952-53 | el evento de PRECIO es 1953-06 |
| Suez | **Jan 57** (Jan 57-Feb 57, 9 %); escasez Nov-Dec 56 (Europa) | 1956-57 | 1957-01 |
| 1969 / 1970 | **Feb 69** (7 %) y **Nov 70** (8 %), agrupados por Hamilton | 1969, 1970 (dos) | **un episodio**, 1969-02 (Hamilton los agrupa) |
| 1973-74 | **Apr 73** (Apr-Sep 73, 16 %) y Nov 73-Feb 74 (51 %), agrupados | 1973-74 | un episodio, 1973-04 |
| Revolución iraní | **May 79** (May 79-Jan 80, 57 %) | "1978-79" | **1979-05** (no 1978) |
| Irán-Irak | **Nov 80** (Nov 80-Feb 81, 45 %) | 1980-81 | 1980-11 |
| Guerra del Golfo I | Aug 90 (Aug-Oct 90, 93 %) | 1990 | 1990-08 |
| 1999-2000 | **Dec 99** (Dec 99-Nov 00, 38 %) | 1999-2000 | 1999-12 |
| Venezuela / Golfo II | **Nov 02** (Nov 02-Mar 03, 28 %) | 2002-03 | 2002-11 |
| 2007-08 | Feb 07 | — | fuera (≥ 2005) |

**Lista de sensibilidad congelada (10 episodios ≤ 2004):** 1947-11, 1953-06, 1957-01, 1969-02, 1973-04, 1979-05,
1980-11, 1990-08, 1999-12, 2002-11. Retraso 1 mes, como E1. Es **descriptiva**. Nota: la definición principal E1 (cadena
mundial) no capta 1947-57 porque hay hueco 1941-46 y el empalme de 1960; por eso Hamilton es la sensibilidad útil
para 1947-1970.

## 2. Eventos (`src/intl/eventos.py`, constantes v0, sin cambios)
- **E1 petróleo:** Σ12 m del NOPI36 ≥ 0,20, cadena mundial (pozo EE. UU. 1890-1941, PPI crudo 1947-59, Banco Mundial
  1960-2004), separación 24 m, retraso 1 m. Sensibilidades: umbral 0,10 y 0,30, cadena doméstica, Hamilton (§1).
- **E2 crisis bancaria:** JST `crisisJST` (año de inicio), separación 5 años por país; años de guerra (1914-18, 1939-45)
  fuera del panel; episodio global = años encadenados a ≤ 1 año. Sensibilidad: solo 1946-2004.
- **E3 dólar:** Δlog 12 m de `TWEXMMTH` ≥ 0,10, 1973-2004, separación 24 m, retraso 1 m. Sensibilidad: umbral 0,05.
  **Todo E3 es descriptivo.**
- **E4 pico de volatilidad:** RV mensual CRSP ≥ P90 expansivo (≥ 60 meses), separación 12 m, retraso 0. Sensibilidades:
  P95, separación 6, modo racha, réplica VIX 1990-2004.
- **Año del evento** (para el panel anual): año natural del mes del evento (E1, E3, E4) o el de JST (E2).
- Un evento entra en un horizonte solo si **todo** el horizonte cae ≤ 2004-12.

## 3. Rentabilidades
**Capa mensual (EE. UU./mundo; nominal, en USD).** Acumulada = Σ log(1 + r) de t + retraso + 1 a t + retraso + h,
h ∈ {1, 3, 6, 12, 24}:
bolsa (CRSP total: `aqr_mkt_usa_d` + `ffx_us_rf_d`, 1926-07), letras (`ffx_us_rf_d`), bonos (10 a. a la par desde
`shiller_gs10`, aproximado), oro (`gold_usd_monthly`, desde 1968-04), materias AQR CFP total (`aqr_cfp_commodities_market_m`
+ letras, 1926-07), materias AQR CLR **exceso** (`aqr_clr_ew_xret_m`, 1877), petróleo (precio, cadena de E1), Banco
Mundial energía, metales base y metales preciosos (1960; cambio de la media mensual).

**Capa anual, panel JST (17 países, REAL, como INT-11):** (1 + tr)/(1 + Δ IPC) − 1 para bolsa (`eq_tr`), bonos
(`bond_tr`), letras (`bill_rate`), vivienda (`housing_tr`). Acumulada log t+1..t+H, H ∈ {1, 2, 3}; el año t del evento
se informa aparte (descriptivo, "H0").

**Capa anual mundial (REAL en USD, IPC de EE. UU. de JST):** oro (diciembre a diciembre, desde 1969) y materias CLR
exceso (compuesto anual, 1878). Eventos: E2 = años de inicio de los episodios globales; E1/E3/E4 = años del evento.
Descriptivo.

**Estadístico (todas las capas):** efecto = media de las acumuladas tras los eventos − media de los orígenes sin evento
en (t − h, t] (en el panel, del mismo país). Se informa también la **media absoluta** tras el evento (log y en %), la
proporción de eventos con acumulada > 0 y n.

## 4. Contrastes principales (familia de 4, Holm, α = 5 %, bilaterales)
| id | evento → activo | capa / muestra | horizonte |
|---|---|---|---|
| **H1** | E2 crisis → vivienda real | panel JST, sin guerras | t+1..t+3 |
| **H2** | E2 crisis → bolsa real | panel JST, sin guerras | t+1 |
| **H3** | E4 pico de volatilidad → bolsa EE. UU. | mensual 1931-2004 | 12 m |
| **H4** | E1 petróleo → bolsa real | panel JST, años globales de E1 sin guerras | t+1 |

**Valor p (placebo de fechas, 2.000 juegos, semilla 20261030):**
- H3: n fechas falsas entre los orígenes válidos, separadas ≥ 12 meses entre sí y a > h meses de los eventos verdaderos
  (`eventos.placebo`).
- H1, H2: para cada crisis verdadera (país, año), un año falso del **mismo país** entre sus años válidos (acumulada
  definida, no guerra, a > H años de cualquier crisis verdadera del país), con separación ≥ 5 años entre los falsos del
  mismo país.
- H4: tantos años falsos globales como años de evento, entre los años válidos (no guerra, a > H de los años verdaderos),
  separados ≥ 2 años; se aplican a todos los países.
- p = (1 + #{|placebo| ≥ |efecto|}) / (1 + #placebos válidos). Holm sobre H1-H4.

**IC 90 %** por bootstrap (2.000) de bloques: H3, bloques de calendario de 60 meses (`eventos.ic_bloques`); H1-H2,
conglomerado = episodio global de crisis; H4, conglomerado = año del evento (`eventos.ic_panel`).

**"Establecido"** si p_Holm < 0,05 **y** el IC 90 % no contiene 0. Si no, "no establecido" (con el MDE al lado).

## 5. Descriptivo (sin p ajustada)
Todas las demás combinaciones evento × activo × horizonte de §3 y las sensibilidades de §2 y §1: efecto, IC 90 %
(1.000 bootstrap) y p de placebo (300 juegos). Si un evento tiene < 5 casos en un horizonte: "n insuficiente" (se
informa la media, sin IC ni p).

## 6. Tabla "qué activo protege en cada evento" (descriptiva)
Para cada evento principal (E1, E2, E3, E4) y horizontes 12 m (mensual) y t+1..t+3 (anual): activos ordenados por media
absoluta tras el evento, con su efecto frente a lo normal e IC. Etiqueta **"protege"**: media absoluta tras el evento
> 0 **y** mayor que la de la bolsa en el mismo horizonte y capa. Etiqueta **"sufre"**: efecto con IC 90 % entero < 0.
No son contrastes: con n de 3-16 son orientativas.

## 7. Reglas fijas
- Nada se cambia tras ver resultados; variantes nuevas → prerregistro nuevo. Semilla 20261030.
- Los solapes (petróleo ~ volatilidad en 5 de 6 shocks 1971-2000) se declaran; no se separan efectos.
- Salida: `research/int/int14_resultado.{json,md}` (español) y una fila en `research/trial_log.md`.
- Después: tabla para el motor INT-11 (inclinación, fase 1 de la integración) — sin modificar `escenarios.py`.
  Confirmación solo en ≥ 2005 con puerta de gasto y prerregistro de confirmación.
