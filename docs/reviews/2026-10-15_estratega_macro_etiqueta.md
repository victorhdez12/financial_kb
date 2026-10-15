---
documento: revisión económica y de inversión de la etiqueta de régimen
hito: etiqueta de régimen EE. UU. v1.1 (`data/archive/labels/regime_us_v1.1.parquet`, hash `8425b403…`)
fecha: 2026-10-15
revisor: Estratega macro (buy-side, asignación por régimen)
veredicto: ⚠️ SIRVE CON CAMBIOS (como objetivo del nowcast sí; como "régimen de inversión", no por sí sola)
---

# Revisión económica de la etiqueta de régimen v1.1

## Veredicto: ⚠️ sirve con cambios

**Como objetivo del nowcast, la v1.1 sirve y no hay que tocarla.** Está bien definida, es reproducible, se fijó antes de
modelar y su eje de crecimiento es económicamente sólido. Ninguno de mis hallazgos es un error de cálculo, y cambiarla
ahora, después de haber visto rendimientos de activos, sería minería de datos.

**Como "régimen de inversión", la etiqueta no basta por sí sola.** El eje de inflación mide un **nivel** frente a un
umbral fijo. Por eso funciona sobre todo como un **marcador de época** (1970-1990 frente a 1990-2020) y no como el
estado que mueve los precios de los activos, que depende de la **dirección** de la inflación y de si esta sorprende a lo
descontado. Los datos de 1955-2004 lo muestran así:
- El cuadrante "Estanflación" cambia de signo para la renta variable entre 1955-79 (−2,1 % real anual) y 1980-2004
  (+10,5 %). Lo mismo le pasa a "Crecimiento bajo/desinflación" (+11,9 % → −1,0 %).
- Solo "Expansión" tiene un significado estable para la bolsa.
- Una partición alternativa con la **dirección** de la inflación separa mejor los activos (§3).

**Lo que pido** no es una v1.2. Pido **capas y objetivos secundarios preregistrados** para la Etapa 2 (activos): la
dirección de la inflación, una capa de shock energético o de inflación general, y el cruce con la recesión. Pido también
**renombrar "Late cycle / sobrecalentamiento"** en todos los informes, porque induce a error de posicionamiento.

---

## 1. ¿La definición tiene sentido para invertir?

### Eje de crecimiento: bueno, con dos matices
- Usar el conjunto coincidente del NBER, en ritmo frente a la tendencia de 10 años, es la elección correcta para un
  cuadrante a la Bridgewater: lo que mueve a los activos es crecer **más o menos de lo normal**, no crecer o no.
- **Matiz 1. G es un momentum, no un nivel de holgura.** G > 0 al salir de una recesión, con un paro del 8 %, significa
  "recuperación", no "sobrecalentamiento". Por eso el nombre "Late cycle" es incorrecto en la mitad de los casos (A2).
- **Matiz 2. La tendencia de 10 años no distingue entre oferta y demanda.** Hoy el empleo crece ~35 mil/mes (media de
  2025-26), frente a 190 mil en 2015-19. Gran parte de esa caída es oferta de trabajo (inmigración), no demanda débil: el
  paro está estable en el 4,1-4,4 % y la regla de Sahm en tiempo real ronda 0. G lo lee como "crecimiento bajo" (M1).
  Además, INDPRO pesa un 25 % en G, cuando la manufactura es ~10 % del PIB. En 2023-24 la producción industrial estuvo
  plana con el PIB al 3 %, y eso empuja G hacia abajo en una economía de servicios.

### Eje de inflación: aquí está el problema
- **El umbral fijo del 2,5 % antes de 1996-2012 (sin objetivo explícito)** es una convención aceptable para *describir*
  la inflación, pero para invertir tiene un coste:
  - I cruza κ solo **27 veces** en 802 meses puntuables, frente a 58 cruces de G.
  - Los años 70 y 80 son casi enteros de "inflación alta" (expansión 0-1 %), y 2010-2019 entero de "baja".
  - El eje separa épocas. Dentro de una época apenas informa, y el modelo de nowcast tenderá a aprender "en qué década
    estamos".
- **Lo que mueven los activos es la aceleración o desaceleración de la inflación frente a lo descontado** (el núcleo del
  marco de Dalio que señalé en la revisión de la Fase 1). Un 4 % que baja desde el 6 % (1983-85, 1991-92) es un régimen
  excelente para bonos y bolsa. La etiqueta lo llama "sobrecalentamiento" o "estanflación".
- **Subyacente frente a general.** La subyacente es correcta para el **eje**: es persistente, es la que mira la Fed y
  revisa poco. Pero el petróleo importa a los activos (materias primas, energía, breakevens, curva) y a la renta real del
  consumidor. Según el PCE general y el subyacente (ventana de 6 m centrada), el lado del umbral difiere en el **11,1 %
  de los meses de 1959-2004**, y lo hace justo en episodios con significado de inversión:

| tramo | I subyacente | I general | lectura económica |
|---|---|---|---|
| 1985-12 → 1986-09 | 3,2 | 1,5 | contrachoque petrolero: desinflación general y boom de bonos |
| 1991-01 → 1991-05 | 3,3 | 2,2 | resaca de la guerra del Golfo: el petróleo ya baja |
| 1999-09 → 2000-04 | 1,8 | 2,7 | petróleo al alza y Fed subiendo: era late cycle de verdad |
| 2003-09 → 2004-04 | 2,0-2,2 | 2,7-2,8 | reflación por materias primas |

  Recomendación: mantener la subyacente en el eje y añadir una **capa de shock de oferta energética** (como la de
  recesión), no mezclarla en el eje.

---

## 2. Recorrido histórico: tramos discutibles

Tramos de la etiqueta dura sacados del parquet v1.1 (G e I son medias del tramo).

| tramo | etiqueta | G / I | valoración |
|---|---|---|---|
| 1955-01 → 1956-02 | Expansión | 1,81 / 0,41 | ✅ (IPC general; I muy baja por la deflación posterior a Corea) |
| 1957-01 → 1958-05 | Estanf. / Bajo, alternando | | ⚠️ Recesión de 1957-58: el empalme decide entre estanflación y desinflación (1957-10 es Bajo; 1957-11/12, Estanf.). Es ruido de medida, no economía |
| 1962-03 → 1963-10 | Bajo / desinf. (20 m) | −0,39 / 1,41 | ⚠️ Pausa sin recesión. Aceptable como "crecimiento bajo"; recuerda que el cuadrante **no** es recesión |
| 1966-01 → 1968-12 | Late ↔ Estanf. (6 cambios) | | ⚠️ El credit crunch de 1966 y la miniparada de 1967 son razonables, pero alternan meses frontera (1968-05→12: pmax 0,58) |
| 1969-01 → 1970-12 | Estanf. (24 m) | −1,33 / 4,81 | ✅ |
| 1971-08 → 1972-09 | Late (14 m) | 1,32 / 3,00 | ⚠️ Los **controles de precios de Nixon** (desde 1971-08) reprimen la I medida. El régimen "verdadero" era más inflacionario de lo que dice la serie |
| 1973-09 → 1975-06 | Estanf. (22 m) | −2,92 / 8,39 | ✅ |
| **1975-07 → 1976-05** | **Late / sobrecal.** (11 m) | 0,79 / 6,00; ΔI6 = −0,58 | ❌ Es la **recuperación temprana** con paro > 8 % e inflación bajando. Llamarla sobrecalentamiento invierte el posicionamiento (late cycle: infraponderar bolsa; early cycle: sobreponderar) |
| 1976-08 → 1979-01 | Late (30 m) | 1,10 / 6,63 | ✅ Boom inflacionario clásico: RV real ≈ 0, bonos −3 %, materias primas +8 % |
| 1979-02 → 1980-07 | Estanf. (18 m) | | ✅ |
| 1981-01 → 1982-12 | Estanf. (24 m) | −1,90 / 6,71 | ⚠️ 1981 es correcto. **1982-06 → 1982-12** (G = −2,1, I = 5,9) es el giro desinflacionario de Volcker: los bonos ganan un **+33 % real anualizado en 1982** y la bolsa empieza su mercado alcista en 1982-08. En cuanto a activos, es lo contrario de una estanflación |
| **1983-01 → 1985-01** | **Late / sobrecal.** (25 m) | 1,30 / 4,20; ΔI6 = −0,45 | ❌ Recuperación con fuerte desinflación (paro del 10,8 % al 7,3 %). No hay nada de "late cycle" |
| 1986-05 → 1988-12 | Late (32 m) | 0,46 / 3,85 | ⚠️ 1987-88 sí, por la Fed subiendo y el crash. Pero 1986 lleva la inflación general en el 1,5 % (contrachoque petrolero) |
| **1989-01 → 1992-02** | **Estanf.** (38 m) | −1,02 / 3,67 | ⚠️ 1989-90 es defendible: desaceleración con subyacente del 4 % y petróleo del Golfo. Pero **1991-04 → 1992-02** es la salida de la recesión con desinflación: bolsa +14,9 %, bonos +8,5 % reales |
| 1992-03 → 1993-07 | 8 cambios en 17 meses | pmax 0,39-0,69 | ⚠️ Recuperación "sin empleo" con I ≈ κ. Aquí no hay régimen: solo vale la probabilística |
| 1995-01 → 1996-01 | Bajo / desinf. (13 m) | | ✅ El aterrizaje suave de 1995 |
| 1996-02 → 2000-03 | Expansión (50 m) | | ✅. Pero 1999-09 → 2000-04, con la inflación general al 2,7 % y la Fed subiendo, era late cycle (A3) |
| 2000-04 → 2003-05 | Bajo (con 2001-12 en Estanf.) | | ✅. **2001-12** es Estanf. en un solo mes por un salto de ΔI de +2,3 pp en la subyacente: artefacto de medida |
| 2003-06 → 2007-10 | Exp ↔ Late ↔ Bajo | pmax 0,50-0,77 | ✅ en conjunto; I ronda κ (periodo bloqueado; no lo analizo) |
| 2007-11 → 2009-11 | Bajo (25 m) | | ✅ |
| 2010-2019 | Exp ↔ Bajo | | ✅. Ciclo de "minirrecesiones" (2012, 2015-16, 2019) bien capturado |
| 2018-10 → 2020-05 | Bajo (20 m) | | ⚠️ Con la ventana centrada, 2020-01/02 son "crecimiento bajo" antes del choque (ya señalado por el Validador). En inversión, la bolsa marcó máximos en 2020-02 |
| 2020-06 → 2021-12 | Exp → Late | | ✅ |
| 2022-01 → 2022-06 | Estanf. (provisional) | −0,31 / 5,33 | ✅ El PIB cayó en el primer semestre de 2022, con inflación del 5 % |
| 2022-07 → 2023-07 | Late (provisional) | 0,24 / 4,21 | ✅ |
| **2024-07 → 2024-11** | **Estanf.** (provisional) | −0,06 / 2,72; pmax 0,40, **5/5 frontera** | ❌ en la lectura dura. El PIB del 2024-T3 creció al 3,15 % anualizado. Es "crecimiento en tendencia con inflación algo alta". G < 0 sale de la industria plana y de la tendencia truncada (M1) |

**Patrón:** los errores económicos se concentran en **las salidas de recesión con inflación alta pero bajando** (1975-76,
1982-85, 1991-92) y en **la inflación general frente a la subyacente** (1986, 1999-2000). No son meses frontera: la
etiqueta está muy segura (pmax 0,90 en 1983-85), así que la probabilística no los rescata.

---

## 3. ¿Discriminan los cuadrantes los rendimientos? (1955-2004, ex post, NO operable)

**Advertencias.**
- La etiqueta usa datos hasta t+4 y la tendencia hasta t+60. Esto es una **descripción a posteriori**, no una estrategia.
- Solo 1955-01 → 2004-12, `weight = 1`. **No he mirado nada de 2005 en adelante.**
- Hay unos 20 tramos por cuadrante. Los errores estándar iid (≈ σ/√años: ±3-5 pp en RV) subestiman la incertidumbre
  real.
- Hice una sola partición alternativa, elegida por teoría (Bridgewater), no por búsqueda.

**Datos** (warehouse, `obs_latest`):
- RV: `ff_mkt_rf_m` + `ff_rf_m`.
- Bono a 10 años: `shiller_nominal_bond_tr_ret_m`.
- Letras: `ff_rf_m`.
- Materias primas: `aqr_cfp_commodities_market_m` (exceso) + letras.
- Oro: `gold_usd_monthly`, precio.
- Energía y utilities: `ff_ind10_*_vw_m`.
- HML y SMB: largo-corto, sin deflactar.
- Dólar: Δlog de `TWEXMMTH`, desde 1973.

Todo en real con `CPIAUCSL`. Media mensual × 12, en % (volatilidad anualizada entre paréntesis).

### 3.1 Etiqueta dura v1.1

| activo (real) | Expansión (149 m) | Late / sobrecal. (167) | Estanflación (186) | Bajo / desinf. (98) | Todos |
|---|---|---|---|---|---|
| RV EE. UU. | **+15,4** (12) | +6,3 (15) | +4,1 (17) | +4,8 (17) | +7,6 (15) |
| Bono 10a | −0,0 (5) | +1,3 (6) | +3,0 (9) | **+8,3** (5) | +2,6 (7) |
| Letras | +1,5 | +1,0 | +1,2 | +1,2 | +1,2 |
| Materias primas (colat.) | +2,2 (9) | **+10,4** (13) | +3,7 (17) | +9,4 (9) | +6,2 (13) |
| Oro | −3,1 (8) | +1,7 (16) | **+7,0** (23) | +2,8 (7) | +2,3 (16) |
| Energía (RV) | +14,3 (15) | +9,2 (18) | +4,5 (20) | +9,1 (16) | +9,0 (18) |
| Utilities | +8,2 (11) | +4,1 (12) | +5,4 (15) | **+11,8** (16) | +6,8 (14) |
| Value HML (L/S) | +1,4 (8) | +5,5 (9) | +4,4 (9) | **+11,3** (11) | +5,1 (9) |
| 60/40 | **+9,3** (7) | +4,3 (9) | +3,6 (11) | +6,2 (10) | +5,6 (10) |
| Dólar majors (1973+) | +1,0 | −2,5 | +0,3 | −3,4 | −0,9 |

Sin meses frontera, las cifras casi no cambian (RV en Expansión +16,3; bono en Bajo +8,3).

**Lectura.** A primera vista la etiqueta discrimina con el signo esperado:
- la bolsa, en Expansión;
- la duración, en Crecimiento bajo/desinflación;
- el oro, en Estanflación;
- las materias primas, en Late.

Pero hay dos problemas:

**(a) Inestabilidad entre épocas** (RV, bono, materias primas y oro, reales):

| cuadrante | 1955-79: RV / bono / MP / oro | 1980-2004: RV / bono / MP / oro |
|---|---|---|
| Expansión | +16,4 / +0,1 / −0,1 / −1,0 | +14,7 / −0,1 / +4,2 / −4,9 |
| Late | +1,0 / −0,9 / +13,0 / +9,5 | +12,9 / +4,0 / +7,2 / −8,2 |
| **Estanflación** | **−2,1 / −4,0** / +10,3 / +14,4 | **+10,5 / +10,2** / −3,1 / −0,7 |
| **Bajo / desinf.** | **+11,9** / +3,5 / +10,3 / −1,7 | **−1,0** / +12,2 / +8,6 / +6,3 |

Hay dos patrones:
- En **1980-2004**, "Estanflación" es un **buen** régimen para bonos y bolsa. Son los meses de desinflación de 1981-82,
  1985-86 y 1989-92 con la subyacente aún por encima del 2,5 %.
- "Late" pasa de malo (+1 %) a bueno (+12,9 %) para la bolsa, por 1983-85.

Lo único estable es: **Expansión → bolsa** y **Bajo/desinflación → duración**. El oro y las materias primas en
Estanflación solo funcionan en la época de 1970-79.

**(b) La recesión explica buena parte.**

| | RV real | bono real | materias primas |
|---|---|---|---|
| Meses de recesión NBER | +1,2 | +9,9 | +2,8 |
| Resto de meses | +8,7 | +1,5 | +6,7 |

Esa diferencia es de la misma magnitud que la que hay entre cuadrantes. Estanflación y Bajo/desinflación mezclan
recesiones (1974, 1980-82, 1990-91, 2001) con pausas sin recesión (1962-63, 1985, 1992-93, 1995).

### 3.2 Contraste: G × **dirección** de la inflación (ΔI = I<sub>t</sub> − I<sub>t−6</sub>)

| activo (real) | G+ e I sube (164) | **G+ e I baja** (152) | **G− e I sube** (125) | G− e I baja (159) |
|---|---|---|---|---|
| RV EE. UU. | +6,4 | **+15,1** | **−1,5** | +8,9 |
| Bono 10a | **−2,1** | +3,6 | +3,3 | **+6,0** |
| Materias primas | +7,3 | +5,8 | **+12,7** | +0,2 |
| Oro | −1,0 | −0,1 | **+16,9** | −3,4 |
| Energía (RV) | +5,6 | **+18,0** | +8,7 | +4,1 |
| Utilities | −0,1 | +12,8 | +1,2 | +12,6 |
| 60/40 | +3,0 | **+10,5** | **+0,4** | +7,7 |

La estanflación "de dirección" (G− con inflación acelerando) es el único cuadrante en el que la bolsa y el 60/40 no
ganan nada. Es donde el oro y las materias primas brillan. Una cartera All Weather necesita **ese** estado, no el de
nivel. Es coherente con la teoría (los activos descuentan el nivel y reaccionan al cambio) y con lo que ya pedí en la
Fase 1 (eje de sorpresa).

**Cuidado:**
- ΔI centrada también es ex post.
- La dirección de la inflación es más ruidosa y menos persistente, así que será más difícil de nowcastear que el nivel.

Esto se lleva como **hipótesis preregistrada para la Etapa 2**, no como cambio de la etiqueta.

---

## 4. El régimen actual: ¿estanflación en zona frontera?

La etiqueta termina en 2026-04 y está provisional:
- 2025-09 → 2026-04: Estanf., con G entre −0,03 y −0,31, I entre 2,9 y 3,9 y pmax entre 0,53 y 0,78.

Datos del warehouse (descriptivos, no los uso para buscar relaciones):

| | 2025 | último dato 2026 |
|---|---|---|
| PCE subyacente a/a | 2,6-2,9 % | 3,0-3,2 % |
| PCE general a/a | 2,3-2,8 % | 3,4-3,8 % (desde 2026-03) |
| IPC general a/a | 2,3-3,0 % | 4,0 % (2026-09) |
| WTI | 58-76 $ | 91-102 $ (marzo a mayo de 2026); 97 $ en 2026-09 |
| Empleo (media 3 m) | 108 mil → −45 mil | 28-142 mil; ~51 mil a fin de periodo |
| Paro | 4,0-4,5 % | 4,1-4,2 % |
| Sahm en tiempo real | 0,1-0,4 | ~0 |
| PIB real (t/t anualizado) | 0,1 / 4,0 / 3,9 / 0,2 | 2,5 (T1), 2,2 (T2) |
| Fed funds / 10a | 4,33 → 3,64 | 3,63-3,75 / 4,99 (2026-09) |
| BAA − 10a | 1,5-2,0 | 1,45 (mínimos) |

**Mi lectura:**
- **Que la inflación está por encima del objetivo y no baja es sólido**, y desde marzo de 2026 lo empeora un shock
  energético (WTI +60 %). La etiqueta, al usar la subyacente y acabar en abril, **todavía no recoge ese shock**. Si
  pasara a la subyacente, la lectura de "estanflación" se reforzaría.
- **El "crecimiento bajo" es débil y, en parte, de oferta.** El PIB crece en torno al 2-2,5 %, el paro está estable y
  los diferenciales de crédito están en mínimos. G < 0 se explica sobre todo por dos cosas:
  - el empleo, comparado con una tendencia de 10 años inflada por la inmigración de 2015-19 y 2022-24;
  - una producción industrial floja.
  No es una caída de la demanda.
- La etiqueta lo marca bien en la blanda: G está entre −0,03 y −0,31, **dentro de una s<sub>G</sub> (0,40) del cero**. La
  P(G alto) ronda el 40-50 %, salvo en 2025-11.

**Conclusión:** "**estanflación suave, de oferta, en frontera**" me parece una lectura sensata. Es la misma conclusión
que saqué en la Fase 1 con otra metodología (shock de oferta con presión fiscal y de term premium; el 10a en el 5 % y la
curva empinándose por arriba lo confirman). Pero en el informe debe decirse "**inflación persistente con crecimiento en
torno a tendencia, sesgo estanflacionario**", con las probabilidades, y no "Estanflación" a secas. La palabra evoca 1974
o 1980 (recesión con inflación del 8-9 %), y hoy no hay recesión. Para activos, el riesgo relevante es la **duración**
(la inflación general sube y el term premium también), no un desplome de beneficios.

---

## 5. Hallazgos priorizados

| # | gravedad | hallazgo | evidencia |
|---|---|---|---|
| A1 | ALTA | El eje I en **nivel** con κ fijo marca épocas, no regímenes de activos. El significado de Estanflación y de Bajo/desinf. para la bolsa cambia de signo entre 1955-79 y 1980-2004 | §3.1(a); 27 cruces de I frente a 58 de G |
| A2 | ALTA | "**Late cycle / sobrecalentamiento**" está mal nombrado: G es ritmo frente a tendencia, así que las recuperaciones tempranas con inflación alta caen ahí (1975-07→76-05, 1983-01→85-01), con pmax ≈ 0,9 | §2 |
| A3 | ALTA (para la Etapa 2) | La recesión (capa) explica tanta varianza de activos como el cuadrante. Estanf. y Bajo mezclan recesiones con pausas | §3.1(b) |
| M1 | MEDIA | El borde actual de G está sesgado por un shock de oferta de trabajo y por el peso de INDPRO. La "estanflación" de 2024-07→11 es dudosa (PIB del 3 %) | §2, §4 |
| M2 | MEDIA | La subyacente ignora los shocks energéticos que mueven activos (1986, 1999-2000, 2026). Correcto para el eje, pero falta la capa | §1; desacuerdo del 11 % |
| M3 | MEDIA | Las salidas de recesión desinflacionarias (1982-H2, 1991-04→92-02) salen como "Estanf." con alta confianza: justo los mejores momentos para comprar duración y bolsa | §2 |
| B1 | BAJA | Artefactos de un mes: 2001-12 Estanf. (salto de la subyacente); 1957 depende del empalme; 1971-72 con controles de precios | §2 |
| B2 | BAJA | Alternancia en 1992-93 y 1966-68: en esas zonas solo vale la probabilística; la dura no debe usarse para asignar | §2 |

---

## 6. Propuestas concretas

### Sobre la etiqueta (sin cambiar la v1.1)
1. **No modificar la v1.1.** Es un objetivo de nowcast legítimo, y cambiarla ahora, después de ver rendimientos, sería
   snooping. Todo lo que sigue va como capas y objetivos secundarios **preregistrados en `research/hypotheses.yaml`
   antes de evaluarlos**.
2. **Renombrar en informes y en el alias del `meta.json`**:
   - `late_cycle` → "**Crecimiento con inflación alta**" (o "boom inflacionario"), con la nota "puede ser recuperación
     temprana o sobrecalentamiento; distinguir con el nivel de holgura (paro − NAIRU)".
   - "Estanflación" → mantener el nombre, con la etiqueta adicional "con/sin recesión".
3. **Capas nuevas** (como `usrec`, ex post y prohibidas como variables):
   - **`infl_dir`**: signo de I<sub>t</sub> − I<sub>t−6</sub> con banda probabilística (misma s<sub>I</sub>·√2).
   - **`energy_shock`**: PCE general − subyacente (6 m centrada) > +1 pp o WTI a/a > 40 %.
   - **`slack`**: paro − NAIRU (CBO) > 0, para separar "recuperación" de "sobrecalentamiento" dentro de G+ I+.
4. **Candidata a v2.0** (no ahora; solo si la Etapa 2 lo justifica con datos ≤ 2004): un eje I **frente a lo esperado**,
   es decir, la inflación realizada menos las expectativas. Fuentes: Livingston desde 1946, SPF desde 1981, Michigan
   desde 1978. Es lo más fiel a "frente a lo descontado" y elimina el problema del umbral fijo antes de 1996.

### Para la Etapa 2 (activos por régimen)
5. Condicionar las preferencias a **cuadrante × recesión × dirección de la inflación**, con contracción fuerte hacia la
   media (12 celdas con ~50 meses de media son pocas). Preregistrar que el contraste principal es "la estanflación de
   dirección (G− e I sube) frente al resto", que es el que más separa la bolsa y el 60/40 del oro y las materias primas.
6. Validar siempre **por época** (1955-79 frente a 1980-2004) y exigir el mismo signo en ambas. Hoy solo lo cumplen
   "Expansión → bolsa" y "Bajo → duración".
7. **Nunca asignar con la etiqueta dura**: usar las probabilidades y no actuar con pmax < 0,6.

### Variables candidatas con mecanismo (para el nowcast)
- **I, nivel y dirección:**
  - PPI de bienes intermedios y precios de importación → subyacente (3-9 m);
  - petróleo a/a → inflación general (1-3 m) y, con retardo, servicios de transporte;
  - salarios (ECI, Atlanta) y brecha de paro → servicios subyacentes (6-18 m);
  - alquileres de mercado (Zillow/CoreLogic, dentro de su historia) → vivienda en el PCE con 9-12 m;
  - breakevens a 5 años y Michigan a 1 año → expectativas.
- **G:**
  - peticiones iniciales de paro y continuadas (0-3 m);
  - nuevos pedidos de las encuestas regionales de la Fed;
  - permisos de construcción;
  - excess bond premium y SLOOS (6-12 m);
  - curva 10a-3m (6-18 m);
  - tipo real frente a r\*.
- **Específica del borde actual:** una corrección de la tendencia del empleo por oferta de trabajo, con la población
  activa o el umbral de empleo de equilibrio (Fed de SF / Brookings), para que el modelo no confunda menos inmigración
  con recesión.

### Capa EUR para el inversor español
8. La etiqueta de EE. UU. no es el régimen de la cartera de un residente en España. Hacen falta:
   - **la etiqueta de la zona euro con ficha propia** (producción industrial, empleo y ventas de la zona euro;
     HICP subyacente frente a un κ ≈ 2,3 %), ya prevista;
   - **el EUR/USD como canal**: en 1973-2004 el dólar **cae** en Bajo/desinflación (−3,4 %/año) y en Late (−2,5 %).
     Para un inversor en euros, la bolsa de EE. UU. sin cubrir **no** tuvo el colchón de "dólar refugio" en las
     desaceleraciones de esa época (el patrón refugio es posterior y no lo he mirado: está en el periodo bloqueado);
   - las decisiones de cobertura de divisa deben evaluarse en EUR y por régimen.
9. **Fiscalidad española:**
   - implementar las rotaciones tácticas con **fondos indexados traspasables** (el traspaso entre fondos no tributa,
     art. 94 LIRPF) y no con ETF, cuya venta sí tributa;
   - con ETF, cada cambio de régimen realiza plusvalías al 19-28 %, y con ~1,2 cambios/año de la etiqueta dura (86
     tramos en 66 años) el coste fiscal se come la ventaja táctica;
   - la Capa 4 debe incluir el coste fiscal en la función objetivo.

### Qué evitar
- Ajustar κ, la ventana o la definición mirando rendimientos de activos (esta revisión ya ha mirado 1955-2004: que conste
  en el registro de pruebas).
- Leer "Estanflación" como 1974: hoy no hay recesión.
- Entrenar un modelo que en el fondo aprenda "década" con variables de nivel (tipos, inflación) sin estandarizar por
  ventana móvil.
- Sacar conclusiones del oro y las materias primas en Estanflación: es un resultado de los años 70 (n efectivo ≈ 2-3
  episodios).
- Usar el periodo 2005+ para elegir capas o variables. Todo lo anterior se ha calculado con datos ≤ 2004-12.

---

## Anexo: método del §3
Script temporal, no versionado, en el scratchpad de la sesión. Se reproduce con las series citadas:
- rendimiento real mensual = nominal − ΔCPIAUCSL;
- etiqueta `label_hard` del mes t frente al rendimiento del mes t;
- muestra 1955-01 → 2004-12 con `weight = 1` (600 meses; el dólar, 383 meses desde 1973);
- partición alternativa: signo de G y signo de I<sub>t</sub> − I<sub>t−6</sub> del propio parquet.

No he modificado código ni datos.
