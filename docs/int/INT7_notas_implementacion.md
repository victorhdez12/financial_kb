---
documento: INT-7, notas de implementación (lecturas de las ambigüedades del prerregistro congelado)
prerregistro: docs/int/INT7_prerregistro_v1.md v1.0 (711dcd9, congelado 2026-10-29T18:34:16Z)
código (00640a3): src/intl/int7.py (método), scripts/int7_corrida.py (corrida con puerta), tests/test_intl_int7.py
estado: fijado ANTES de la corrida, sin haber cruzado ningún indicador de valoración con ninguna rentabilidad
---

# INT-7: cómo se ha leído el texto congelado

Regla: donde el texto admite más de una lectura, se toma la más literal. Ninguna de estas decisiones se ha tomado
mirando resultados: antes de commitear el script solo se ha ejecutado con datos sintéticos (`--sintetico`).

## Datos
1. **Familia de Shiller** (decisión 4): la expresión literal del §9,
   `shiller_(cape|real_price|real_earnings|real_dividend|real_stock_tr_ret_m)`, con el mismo corte y la misma
   comprobación que el resto (`load_dev`). `shiller_tr_cape` (citada en §10.4 como disponible) **no** entra: no la usa
   ninguna pregunta y el §9 no la nombra. Commit aparte (eecbe50).
2. **Hiperinflación** (§3, "regla de INT-3b; mira solo el IPC"): inflación simple IPC_t/IPC_{t−1} − 1 > 50 %, como
   `activos3b.inflacion_jst` de INT-3b. (El script de potencia usaba |Δlog IPC| > 0,5; la regla de INT-3b es la
   citada.) Se aplica a los años de la fila: t y t + 1 en V1-V2; t … t + 5 en V3 (los años del resultado); t − 1 … t + 1 en
   la sensibilidad estricta; t … t + 2 en la de t + 2. IPC ausente = no es hiperinflación.
3. **Celdas del indicador para su AR(1)** ("limpias"): log D/P con D/P > 0 y sin hiperinflación en ese año. Los pares
   del AR(1) son años consecutivos con las dos celdas limpias.
4. **Recuentos**: el §1 cita 1.656 filas (V1) y 1.577 (V3) del script de potencia, que aplicaba la hiperinflación un año
   más allá (t + 2). Con la regla literal las filas pueden diferir en unas pocas; se publican las reales.

## Confirmatorias V1 y V2
5. **z**: (x − media)/dt con media y dt del log D/P en las filas de V1. b en log-rentabilidad por 1 dt (× 100 = pp).
6. **V2**: la regresora es el log D/P total estandarizado con efectos de país y de año. Como los efectos fijos absorben
   cualquier a_i + λ_t, se usa directamente el D/P relativo (z sin efectos de país ni de año, proyección exacta sobre
   las celdas limpias), en unidades de la dt total: mismo b y misma t que con el total. "Por 1 dt del relativo" = b × dt
   del relativo en las filas.
7. **Driscoll-Kraay**: agrupado por el año t de la fila (el del indicador), Bartlett, retardos ⌊4(T/100)^(2/9)⌋,
   corrección T/(T − 1); efectos fijos por Frisch-Waugh (idéntico a `int3.driscoll_kraay`; hay test).
8. **Amihud-Hurvich en panel**: AR(1) por país del indicador (V2: del relativo) con φ_c = φ̂ + (1 + 3φ̂)/T (Kendall,
   el mismo término que §2.2), con tope 0,999; v̂c_{i,t+1} = x_{t+1} − c_i − φ_c·x_t; regresión aumentada
   y_{t+1} = FE + b·z_t + γ·v̂c_{t+1}. Las filas sin v̂c_{t+1} (x_{t+1} ausente o no limpio) salen de la regresión
   aumentada (se publica cuántas quedan).
9. **Bootstrap nulo (§3.2)**:
   - ê_{i,s}: y del año de resultado s menos la media del país en las filas (V2: residuo con efectos de país y de año);
     v̂_{i,s}: innovación del AR(1) corregido. Un par (ê, v̂) es válido si existen los dos.
   - Años remuestreados por bloques de 5 años consecutivos (bloques móviles, no circulares) de entre los años con algún
     par válido; se toma el vector de todos los países del año sorteado.
   - **Celda sin par válido** en el año sorteado (país que no existe ese año): se sustituye por el par (ê, v̂) de un año
     válido del mismo país, al azar. Conserva δ dentro del país; solo en esas celdas pierde la correlación entre países.
     El texto no lo resuelve.
   - x* se reconstruye desde el primer valor limpio real de cada país con el AR(1) corregido y se le aplican los mismos
     huecos (celdas limpias). y*_s = ȳ_i + ê*_s.
   - Estadístico: la t de Driscoll-Kraay de la MCO, igual que en los datos. B = 4.999, semilla 20261029.
   - p = 2·mín(P(t* ≥ t), P(t* ≤ t)), con cada P = (1 + #)/(1 + B) y p ≤ 1. Suelo 2/5.000 = 0,0004 (el texto dice
     "1/5.000": es la P de una cola; sigue lejos de 0,0125).
   - Test sintético (φ = 0,9, δ = −0,9, 4 países × 70 años, 160 paneles, B = 199): rechazos al 5 % del bootstrap
     **5,0 %**; del t de Student ingenuo, 20,6 %.
10. **IC del efecto corregido** ("bootstrap con b̂ impuesta"): mismos pasos con ê = residuo de y − b̂_AH·z (con sus
    efectos fijos), y* = α̂_i + b̂_AH·x*_{s−1} + ê*; en cada réplica se reestima Amihud-Hurvich (AR(1) incluido); IC =
    percentiles 2,5 y 97,5 de b̂_AH*.
11. **Holm-2** sobre los dos p del bootstrap (umbrales 0,025 y 0,05).
12. **Criterio 3 (placebo)**: z desplazado en círculo k = 6 … T − 6 años dentro del rango de años de las filas, misma k
    en todos los países (como `int3.desplazar`); t de DK (MCO) con los retardos por defecto de cada submuestra; se
    compara |t| con el p95 de las |t| placebo.
13. **Criterio 4 (dos mitades)**: por el año t del indicador (t ≤ 1949 / t ≥ 1950); se exige signo + en el efecto que
    se lee (Amihud-Hurvich, con el v̂c del AR(1) de toda la muestra); la MCO de cada mitad se publica al lado.
14. **Criterio 5 (países)**: pendiente MCO de cada país (≥ 10 filas) de y sobre z (V2: sobre su z relativo), sin
    encoger; y DerSimonian-Laird (`int3.encoger`) sobre las pendientes de y sin la media de cada año, con varianza MCO
    clásica. Umbral ≥ 2/3 en los dos (regla de INT-3b).
15. **Sensibilidades** (MCO con DK y su p de Student; Amihud-Hurvich donde el tiempo de la innovación coincide con el
    del resultado): sin guerras (t o t + 1 en 1914-1918 o 1939-1945); estricta x_{t−1} → y_{t+1} y t + 2 (sin
    Amihud-Hurvich); D/P en niveles; exceso sobre letras (log(1 + eq_tr_real) − log(1 + bill_rate_real)); winsorizado
    1-99 del log D/P en las filas; sin la regla de hiperinflación; núcleo + AUS + CHE, y la pendiente MCO de AUS y CHE
    por separado; Hodrick 1B (= DK con 0 retardos a 1 año).

## Informativas y descriptivas
16. **V3**: y = Σ log(1 + eq_tr_real) de t + 1 a t + 5; efecto fijo de país; DK con 5 retardos; p del bootstrap nulo con
    **las mismas réplicas** que V1 (mismo generador; estadístico t DK(5)); Hodrick 1B: y_{t+1} sobre Σ_{j<5} z_{t−j},
    DK 0 retardos. "Unidades de 1 año": b_5·(1 − φ̄)/(1 − φ̄⁵), φ̄ = AR(1) MCO medio por país (como la potencia); se
    publica también b_5/5.
17. **V4**: x = log(precio real de diciembre de t / media de los 120 beneficios reales de julio de t − 10 a junio de t).
    y = Σ log(1 + r_m) de los 12 meses del año (r_m de `shiller_real_stock_tr_ret_m`, fechada en el mes en que termina).
    Newey-West (1 año: retardos por defecto; 10 años: 10), corrección T/(T − 2); Hodrick 1B; bootstrap nulo de una serie
    (bloques de 5 años). Sensibilidad: `shiller_cape` de diciembre. Puente: log D/P de JST de EE. UU. "con lo mismo" =
    misma rentabilidad (Shiller) y mismos contrastes. Signo esperado: − para el CAPE, + para el D/P.
18. **§4.3**: crecimiento real del dividendo en s = Δlog D/P_s + log(1 + eq_capgain_s) − log(IPC_s/IPC_{s−1})
    (D = D/P · P; P a partir de la ganancia de capital nominal de JST). Supone que `eq_dp` usa el precio de fin de año
    (pendiente de verificar por el Validador, §3).
19. **§4.4 fuera de muestra**: ventana creciente; para cada año de resultado s de 1950 a 2004 se estima con las filas de
    V1 cuyo resultado es ≤ s − 1 y se predice y_s con z_{s−1}; modelo MCO con efecto fijo de país; referencia: media
    histórica del país en el mismo tramo; país con < 10 filas en el tramo: sin predicción ese año. V2: y y z menos la
    media de las filas de su año (corte transversal, conocido en su momento). Clark-West: f agrupado por año, t con DK,
    p unilateral.
20. **V5**: y = FE + b0·z + b1·z·S + g·S, S = estanflación de INT-1 en el año t del indicador (≤ 1999, no truncada);
    DK. La frase obligatoria se publica literal, aunque el número de filas reales difiera de 237.
21. **V6**: Shiller mensual 1881-01 … 2004-12. x = log `shiller_cape` y log(real_dividend/real_price) del mes t; y =
    Σ log(1 + r) de t + 1 … t + h (h = 3, 6). Newey-West con h retardos; bootstrap nulo con el mismo método y bloques de
    **60 meses** (5 años, literal); por año = b × 12/h. Sin Amihud-Hurvich (no lo pide).

## Ejecución
22. Antes de la corrida, el script solo se ha ejecutado con `--sintetico` (datos inventados, 19 réplicas, sin escribir).
    La corrida es `python -m scripts.int7_corrida` con el árbol limpio; escribe research/int/int7_resultado.{json,md}
    y una línea en research/trial_log.md. La lectura en español del .md se añade a mano después, sin tocar los números.
