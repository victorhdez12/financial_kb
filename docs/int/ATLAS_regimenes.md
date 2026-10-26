---
documento: Atlas régimen → activos (qué activos se comportan bien en cada régimen, por qué, cuándo, y si merece la pena actuar)
version: 1.0 (2026-10-26)
estado: SOLO RECOPILA resultados ya calculados y validados. Ningún contraste nuevo; no cambia ningún resultado ni prerregistro.
fuentes: research/int/int3_resultado.{md,json} + int3_sensibilidad_robusta.json (INT-3); int3b_resultado.{md,json} (INT-3b/3c);
         int3d_resultado.{md,json} + int3d_sensibilidad_abs3.json (INT-3d); int4_resultado.md + int4_sensibilidad_liston*.json (INT-4);
         validaciones docs/validation/2026-10-26_int3.md y 2026-10-26_int3b_int3d_int4.md
muestra: 14 países JST (núcleo), 1870/1877-1999/2004, rentabilidades REALES anuales; nada ≥ 2005 (bloqueado)
---

# Atlas régimen → activos

## 0. Cómo leerlo
- **Efecto** = diferencia de rentabilidad real anual (pp/año) de ese activo en ese régimen **frente al resto de años**,
  en el mismo país (efectos de país y de año común quitados según cada prerregistro).
- **IC robusto:** el de Driscoll-Kraay (sensibilidad robusta de INT-3, declarada a posteriori) donde existe; si no, el de
  la corrida única.
- **"Con el régimen conocido (t − 1)":** el mismo efecto si solo se sabe el régimen del año anterior (lo que se puede saber
  a tiempo). Es la columna que dice si **merece la pena actuar**.
- **Clasificación (fijada por escrito antes de clasificar):**
  - **Establecido:** cumple todos los criterios de su prerregistro en la corrida única.
  - **Probable:** el signo es el esperado, pasa la sensibilidad robusta (Driscoll-Kraay con Holm o IC robusto sin el 0, y
    por encima de los placebos), pero no todos los criterios oficiales.
  - **No establecido:** ni lo uno ni lo otro.
  - **Descriptivo:** no se contrastó (tabla por cuadrante, sin inferencia).
- Regímenes: expansión (crecimiento alto, inflación baja), sobrecalentamiento (alto, alta), estanflación (bajo, alta),
  crecimiento bajo (bajo, baja); "inflación alta" = sobrecalentamiento + estanflación. Etiqueta ex post (ventanas
  centradas): describe dónde se estuvo, **no** se conoce en el momento.

## 1. La tabla

| activo | régimen | efecto (pp/año) | IC 95 % robusto | con el régimen conocido (t − 1) | clasificación | motivo (una frase) |
|---|---|---|---|---|---|---|
| **Bolsa** | estanflación (Q1) | **−8,7** | [−15,0; −2,4] | −0,8 [−5,4; +3,9] | **establecido** | grande y en 14/14 países, pero desaparece si solo se conoce el régimen del año anterior |
| Bolsa | recesión (Q5) | −5,5 | [−10,2; −0,8] | −1,2 [−4,9; +2,5] | **establecido (frágil)** | sin guerras p = 0,095 y en 1950-2004 solo −1,9: el más débil de los establecidos |
| Bolsa | recesión financiera frente a normal (Q5b) | +1,4 | [−5,9; +8,7] | — | no establecido | contra lo esperado; el Validador lo atribuye en parte a la definición de la ventana |
| **Bonos** | inflación alta (Q2) | **−10,1** | [−13,9; −6,3] | **−3,4 [−5,6; −1,2]** | **establecido** | el más sólido; sobrevive con el régimen conocido |
| **Bonos** | crecimiento bajo / desinflación (Q3) | **+7,9** | [+5,9; +9,9] | **+5,0 [+3,2; +6,7]** | **probable** (muy sólido) | falla solo el placebo oficial (autocorrelación); pasa Driscoll-Kraay y supera los 113 placebos |
| Bonos − letras | recesión (INT-3d C3) | +1,2 | [+0,1; +2,2] | — | probable | signo esperado en 12/14 países; falla solo Holm-2 (p = 0,029) |
| **Letras** | inflación alta (Q4) | **−7,7** | [−10,9; −4,6] | **−3,4 [−5,0; −1,8]** | **probable** (muy sólido) | igual que Q3: falla solo el placebo oficial |
| **Vivienda − bolsa** | inflación alta (Q6) | **+6,2** | [+2,0; +10,4] | +3,6 [+0,1; +7,1] | **establecido** | sólido en el agregado, pero solo 10/14 países sin el choque común del año |
| Oro (moneda local) | inflación alta (B3) | −6,0 | [−9,5; −2,6] | −6,4 [−9,2; −3,7] | no establecido (signo contrario) | mecánico: precio fijo en dólares hasta 1971; en dólares 1972-1999 −0,4 [−23; +22] |
| Oro (moneda local) | por cuadrante | expansión +3,0; sobrecal. −3,9; estanfl. −4,2; crec. bajo +0,9 | — | — | descriptivo | mismo problema del precio fijo |
| Materias primas (AQR, mundial) | inflación alta (B1) | +0,7 | [−13,6; +15,0] | −0,0 | no establecido | cambia de signo según la época: +11,6 en 1878-1949, −10,9 en 1950-1999 |
| Materias primas | recesión mundial (B2) | −17,4 | [−37,1; +2,2] | −0,6 | no establecido (indicio) | pocos años de recesión mundial; con futuros desde 1927, −22,5 (p = 0,057) |
| Materias primas | por cuadrante (media) | expansión +10,4; sobrecal. +8,4; crec. bajo +6,5; estanfl. +1,8 | — | — | descriptivo | 11 años de estanflación mundial: no se puede decir nada |
| Petróleo (real) | inflación alta | +21 | [−10; +52] | — | descriptivo | enorme varianza; 1973-1979 domina |
| Crédito − bono del Estado (EE. UU., R. U.) | recesión (B4) | −0,7 | [−1,9; +0,5] | +0,9 | no establecido | dos países; efecto pequeño |
| Crédito corporativo (real) | por cuadrante | crec. bajo +7,3; expansión +3,9; estanfl. +0,1; sobrecal. −5,5 | — | — | descriptivo | se comporta como un bono |

**Expansión** no se contrastó para ningún activo (no había mecanismo claro que distinguiera); solo aparece en las tablas
descriptivas.

## 2. Por qué (mecanismo; INT-3c, reparto descriptivo salvo C4)

| efecto | total (pp) | de dónde sale |
|---|---|---|
| Bolsa en estanflación | −6,5 | **dividendo real −8,3** (la inflación se come el dividendo; C2 p = 0,001); valoración **+1,6** (n. s.; la bolsa NO se abarata más); rentabilidad por dividendo +0,2 |
| Bonos con inflación alta | −8,7 | **cupón real −7,0** (la inflación se come el cupón); capital −1,7 (C3, p = 0,034, no pasa Holm) |
| Bonos en crecimiento bajo | +7,2 | cupón real +4,7; **capital +2,5 (C4 ESTABLECIDO, 14/14)**: bajan los tipos y sube el precio del bono |
| Letras con inflación alta | −6,6 | el tipo nominal sube +1,4, pero la inflación resta −8,0: el tipo corto va por detrás |
| Vivienda − bolsa con inflación alta | +5,9 | **precio +6,5** (el precio de la vivienda sigue a la inflación; C6 p = 0,003); alquiler −0,6 |
| Materias primas con inflación alta | +0,7 | spot +1,9; carry (rendimiento del futuro) +6,5; menos el tipo real de la letra −7,7 |
| Crédito − bono en recesión (EE. UU. desde 1954) | −0,8 | todo por el precio (el diferencial se abre); carry 0 |

## 3. Cuándo (INT-3d, giros; 267 recesiones, confirmación con el retraso real ≈ 16 meses)

| pregunta | resultado | clasificación |
|---|---|---|
| ¿Cuánto rebote se pierde por **esperar a confirmar la salida** de la recesión (bolsa − letras, 16 meses)? | **+2,8 pp** anómalos [+0,1; +5,4] (bruto +7,6, de ellos +4,8 los da cualquier fecha); 13/14 países; 1950-2004 +9,6 | probable (falla solo Holm-2) |
| ¿Cuánto cuesta **esperar a confirmar la entrada** (bolsa)? | **−3,2 pp** [−5,6; −0,9]; en las financieras **−8,4** | descriptivo |
| ¿Cuánto cuesta en bonos esperar a confirmar la **inflación alta**? | **−2,3 pp** [−3,6; −0,9]; con la etiqueta abs3 −2,3 (p = 0,016) | descriptivo (C5; etiqueta ex post) |
| ¿**Cuándo toca fondo** cada activo respecto al valle? | bolsa ≈ 1,3 años antes; bonos ≈ 1,4; vivienda ≈ 2,5 — pero **igual que con fechas al azar** (placebo) | no distinguible |
| ¿Recesiones financieras peores? | bolsa −3,1 y vivienda −5,0 pp, IC ± 9-10 | sin potencia |
| EE. UU. mensual (6 recesiones) | la bolsa suele tocar fondo 3-5 meses antes del valle NBER (salvo 1980 y 2001); el coste de esperar al anuncio del NBER va de −15 a +17 pp | anecdótico |

## 4. ¿Se ve venir? (INT-4, termómetro; dejando un país fuera, 1871-2004)

| giro | mejora de AUC sobre el listón | IC 95 % (estratificado por país) | placebo (z) | clasificación |
|---|---|---|---|---|
| **Entrada en recesión** a 1 año | +0,20 (AUC ≈ 0,73) | [+0,12; +0,27] | 5,4 | **establecido, sólido**: curva, curvas invertidas en otros países, bolsa |
| **Salida de recesión** a 1 año | +0,19 (AUC ≈ 0,77) | [+0,08; +0,28] | 2,8 | **establecido, justo**: casi todo lo aporta la bolsa (el mercado se adelanta) |
| Repunte de la inflación | ≈ 0 | [−0,04; +0,05] | 1,9 | no establecido |
| Vuelta de la inflación | +0,08 | [+0,01; +0,15] | 2,1 | no establecido (falla el placebo) |

## 5. Avisos de fragilidad
1. **Q5 (bolsa en recesión)** es el establecido más débil: depende de las guerras y casi desaparece en 1950-2004.
2. **Q3 y Q4 fallan solo por el placebo**, no por falta de efecto: los regímenes son persistentes y los bonos y letras
   autocorrelados, y el placebo desplazado da demasiados falsos positivos. Con Driscoll-Kraay son los más sólidos.
3. **El "14/14 países" de INT-3 es casi mecánico** (el modelo de efectos aleatorios sin efecto de año encoge hacia la
   media). Sin encoger: 10-14/14 según la pregunta.
4. **Oro negativo** con inflación alta: artefacto del patrón oro y de Bretton Woods (precio fijo hasta 1971). No sabemos si
   protege; con 1972-1999 el IC va de −23 a +22.
5. **Materias primas:** el signo depende de la época; con 1 dato mundial por año la potencia es baja (lo detectable es
   ≈ 14-20 pp).
6. **Etiqueta ex post:** todo el §1 usa el régimen con ventanas centradas (mira años futuros). Lo que se puede usar a
   tiempo es la columna t − 1.
7. **Muestra:** 14 países ricos, 1870-1999/2004, datos revisados, sin costes ni impuestos. Nada de 2005-2020 (bloqueado).
8. **T2 (salida) estaba inflado** en la corrida oficial (+0,30) por un sesgo del listón; la cifra honesta es ≈ +0,19.

## 6. Lecciones (en llano)
1. **La inflación es el enemigo de los bonos y de las letras**, y eso sí se puede aprovechar: aun sabiendo solo el
   régimen del año anterior, con inflación alta los bonos y las letras rinden ≈ 3,4 pp/año menos.
2. **Cuando la economía se enfría y la inflación baja, los bonos ganan** (≈ +8 pp; +5 con el régimen conocido): es el
   resultado más fiable del atlas, y su motivo está demostrado (bajan los tipos).
3. **La bolsa sufre mucho en estanflación y algo en recesión, pero eso no se puede aprovechar** con lo que se sabe a tiempo:
   cuando te enteras del régimen, la caída ya ha pasado (−8,7 pp se queda en −0,8).
4. **La caída de la bolsa en estanflación viene de que la inflación se come los dividendos, no de que la bolsa se abarate.**
5. **La vivienda aguanta mejor que la bolsa con inflación alta** (≈ +6 pp), porque su precio sigue a la inflación.
6. **El oro y las materias primas no han demostrado proteger contra la inflación** en esta historia; no sabemos si lo hacen.
7. **Las recesiones se ven venir moderadamente bien** (curva y lo que pasa en otros países), y **la salida la anuncia sobre
   todo la bolsa**: esperar a la confirmación oficial cuesta ≈ 3 pp de rebote.
8. **La inflación no se ve venir** con dinero, salarios, brecha ni tipo real.

## 7. Lo que NO sabemos

| pregunta | por qué no lo sabemos |
|---|---|
| ¿El oro protege contra la inflación? | precio fijo hasta 1971; después, muy pocos años y una varianza enorme |
| ¿Las materias primas protegen contra la inflación? | el signo cambia de época; 1 observación mundial por año, poca potencia |
| ¿Qué activo gana en **expansión** y en **sobrecalentamiento**? | no se contrastó (solo medias descriptivas) |
| ¿Las recesiones financieras son peores para los activos? | sin potencia (IC ± 9-10 pp); Q5b sale al revés de lo esperado |
| ¿Cuándo toca fondo exactamente cada activo? | no se distingue de fechas al azar con datos anuales |
| ¿El crédito corporativo sufre en recesión frente al bono del Estado? | solo EE. UU. y R. U.; efecto pequeño |
| ¿Se anticipan los giros de inflación? | T3/T4 no establecidos |
| ¿Sigue valiendo todo esto en 2005-2020? | periodo bloqueado, sin mirar |
| ¿Merece la pena actuar **después de costes**? | no se han medido costes ni impuestos; el paper trading (B0/B1) lo irá viendo |
