# INT-7: valoración → rentabilidad. Resultado de la corrida única

**Procedencia:** commit `65a7cb9` (árbol limpio), 2026-10-29T18:47:12Z, una sola corrida. Prerregistro
`docs/int/INT7_prerregistro_v1.md` v1.0 (711dcd9); lecturas de lo ambiguo en `docs/int/INT7_notas_implementacion.md`
(65a7cb9, fijadas antes de correr). Datos JST ≤ 2004 (14 países del núcleo) y Shiller ≤ 2004 (EE. UU.); nada ≥ 2005.
Bootstrap: 4.999 réplicas, semilla 20261029. Unidades: pp de rentabilidad real (log) al año por 1 dt del indicador.

## En una frase
Ni V1 ni V2 quedan **establecidas**: las dos tienen el signo esperado, superan el placebo, mantienen el signo en las
dos mitades y en 12 de 14 países, pero **no pasan el p principal** (bootstrap nulo que conserva δ), que es el criterio
que decide. "No establecido" no es "no existe".

## Confirmatorias (Holm-2 sobre el p del bootstrap nulo; umbrales 0,025 y 0,05)

| | V1: D/P alto → más bolsa real en t + 1 (panel, efecto total) | V2: país más barato que los demás → más bolsa real relativa |
|---|---|---|
| Filas | 1.648 país-años, 14 países, indicador 1870-2003 | ídem, con efectos de país y de año |
| Efecto MCO | +2,72 pp por dt (t DK 2,31) | +3,81 pp por dt (t DK 4,12) |
| **Efecto leído (Amihud-Hurvich)** | **+1,99 pp por dt** | **+3,11 pp por dt** (+2,40 por dt del D/P relativo; dt relativa = 0,77 de la total) |
| IC 95 % (bootstrap con b̂ impuesta) | [+1,20; +3,20] | [+2,66; +4,59] |
| **p del bootstrap nulo** | **0,508** | **0,131** |
| Holm-2 | no | no |
| 3. \|t\| > p95 del placebo | sí (2,31 > 1,60) | sí (4,12 > 2,09) |
| 4. signo + en 1871-1949 / 1950-2004 (AH) | sí (+1,09 / +3,74) | sí (+1,86 / +4,87) |
| 5. países con signo + (sin encoger / DL) | 12/14 / 12/14 | 12/14 / 12/14 |
| **Veredicto** | **NO ESTABLECIDO** (falla solo el criterio 2) | **NO ESTABLECIDO** (falla solo el criterio 2) |

Sensibilidades (MCO, t DK; no deciden): V1 entre +2,4 y +3,1 pp (t 2,2-2,5) en sin guerras, estricta x_{t−1}, D/P en
niveles, exceso sobre letras, winsorizado y con AUS y CHE; sin la regla de hiperinflación sube a +5,9 (t 5,5). V2 entre
+3,6 y +4,2 pp (t 3,1-5,0); sin hiperinflación +6,4. AUS: +9,2 (V1) / +1,5 (V2) pp; CHE: −0,3 / −1,7 pp. Nota: la
sensibilidad "estricta x_{t−1} → y_{t+1}" y la de "t + 2" son **la misma regresión** (los mismos pares x_s → y_{s+2}
con otro nombre de fila) y dan lo mismo.

### Lo que hay que saber para leer el p (observación para el Validador; no cambia nada)
La distribución nula del bootstrap sale **muy desplazada**: t* medio 1,61 en V1 (p2,5-p97,5: −0,48 a 3,68) y 2,44 en V2
(0,37 a 4,68), mucho más de lo que predecía el sesgo de Stambaugh de la potencia (§2.2). La causa es del diseño
congelado, no de los datos: ê = y − ȳ_i **conserva la parte predecible de y** (si existe), y al remuestrear años en
bloques de 5 se mantienen juntos ê_s y las innovaciones v̂_{s−1} … v̂_{s−4} con las que se reconstruye x*_{s−1}; así el
"nulo" reintroduce parte del efecto real. En sintético (14 países × 130 años, φ = 0,8, δ = −0,8) con b = 0 el bootstrap
tiene el tamaño correcto (test: 5,0 % de rechazos frente a 20,6 % del t ingenuo), pero con un efecto real la t nula media
pasa de 0,8 (bloques de 1 año) a 4,9 (bloques de 5). Consecuencia: el contraste es válido pero tiene **mucha menos
potencia que la simulada en §2** (que calibró con un nulo sin esta fuga). No se corrige ni se repite: la corrida es
única. Si se quiere, es materia para una decisión del usuario y un prerregistro nuevo.

## Informativas y descriptivas (sin Holm y sin veredicto)
- **V3 (5 años, solapada):** +11,5 pp acumulados por dt (≈ +3,4 en unidades de 1 año; +2,3 simple), t DK(5) 2,12, p del
  bootstrap nulo 0,589, Hodrick 1B t 1,98. Va con V1, con IC más anchos (lo esperado).
- **V4 (CAPE de EE. UU., réplica de Campbell-Shiller):** 1 año −3,84 pp por dt (AH −2,72), t NW −2,17, R² 4,5 %,
  p bootstrap 0,448. 10 años: −30,1 pp acumulados por dt, t NW −4,88 (11 observaciones no solapadas), Hodrick 1B t
  −2,25, p bootstrap 0,089. Con `shiller_cape` de diciembre, casi idéntico. Puente con el D/P de JST de EE. UU.: +2,5 pp
  (AH +1,8) a 1 año, p bootstrap 0,381.
- **§4.3 la otra mitad de la identidad:** un D/P alto anticipa **menos crecimiento real del dividendo**: −6,3 pp por dt
  (t DK −3,40; AH −5,7). Buena parte del D/P se va por el lado del dividendo (la hipótesis rival, §3).
- **§4.4 fuera de muestra (1950-2004, ventana creciente, 751 predicciones):** V1 R² +1,7 %, Clark-West t 1,59
  (p unilateral 0,059); V2 R² +4,9 %, Clark-West t 3,33 (p 0,001). Solo informativo (decisión 6).
- **V5 (× estanflación):** pendiente en estanflación +1,06 pp, resto +2,45, diferencia −1,39 pp [−4,98; +2,20] (231 filas
  en estanflación, 85 años; MDE ≈ 5,7-6,2 pp). Con 237 país-años en estanflación esto no puede distinguir una modulación
  de 1-3 pp de cero.
- **V6 (EE. UU. mensual, 1881-2004):** CAPE → 3 meses: −0,83 pp por dt (−3,3 al año), R² 1,0 %, t NW −2,14, p bootstrap
  0,178; → 6 meses: −1,79 (−3,6 al año), R² 2,1 %, p 0,180. D/P → 3 meses: +0,60 (+2,4 al año), R² 0,5 %, p 0,518; →
  6 meses: +1,27 (+2,5 al año), R² 1,1 %, p 0,474. **A horizontes cortos la valoración explica muy poco de la
  rentabilidad; su información se acumula con el horizonte.**

## Desviaciones y avisos declarados
- Filas: 1.648 (V1-V2) y 1.559 (V3) frente a 1.656 y 1.577 del §1: la regla de hiperinflación literal de INT-3b
  (inflación simple > 50 % en los años de la fila) en lugar de la del script de potencia. V5: 231 filas frente a 237.
- Pendiente del Validador (§3): comprobar que `eq_dp` de JST usa el precio de fin de año (afecta a la lectura "as of" y
  a §4.3).
- Contaminación muy alta (§6): V1, V3 y V4 replican resultados publicados con estos mismos datos.

---

## Anexo: tablas automáticas del script (sin editar)

Procedencia: commit `65a7cb9`, árbol limpio True, 2026-10-29T18:47:12+00:00. Prerregistro docs/int/INT7_prerregistro_v1.md v1.0 (711dcd9). Réplicas del bootstrap: 4999. Unidades: pp de rentabilidad real (log) por 1 dt del indicador.

## Confirmatorias (Holm-2 sobre el p del bootstrap nulo)

| id | MCO | Amihud-Hurvich (efecto leído) | IC 95 % (bootstrap) | t DK | p bootstrap nulo | Holm-2 | > p95 placebo | ≤1949 / ≥1950 (AH) | países sin encoger / DL | ESTABLECIDO |
|---|---|---|---|---|---|---|---|---|---|---|
| V1 | +2.72 | +1.99 | [+1.20; +3.20] | 2.31 | 0.5084 | no | sí | +1.09 / +3.74 | 0.86 / 0.86 | **no** |
| V2 | +3.81 | +3.11 | [+2.66; +4.59] | 4.12 | 0.1308 | no | sí | +1.86 / +4.87 | 0.86 / 0.86 | **no** |

## Informativas y descriptivas (sin Holm, sin veredicto)

- V3 (5 años): b acumulado +11.45, t DK(5) 2.12, p bootstrap nulo 0.5888, Hodrick 1B t 1.98.
- V4 cape_asof (principal): 1 año b -3.84 (AH -2.72), t NW -2.17, p bootstrap 0.4484, R² 0.045; 10 años b -30.09, t NW -4.88, p bootstrap 0.0892, Hodrick 1B t -2.25.
- V4 cape_shiller (sensibilidad): 1 año b -3.80 (AH -2.69), t NW -2.16, p bootstrap 0.4276, R² 0.044; 10 años b -30.09, t NW -4.83, p bootstrap 0.0896, Hodrick 1B t -2.27.
- V4 dp_jst_usa (puente con V1): 1 año b +2.53 (AH +1.76), t NW 1.63, p bootstrap 0.3812, R² 0.020; 10 años b +26.39, t NW 2.24, p bootstrap 0.3888, Hodrick 1B t 1.40.
- Fuera de muestra V1 (1950-2004): R² +1.66 %, Clark-West t 1.59 (p unilateral 0.059).
- Fuera de muestra V2 (1950-2004): R² +4.92 %, Clark-West t 3.33 (p unilateral 0.001).
- §4.3 D/P → crecimiento real del dividendo: MCO -6.33, t DK -3.40; AH -5.74.
- V5: pendiente en estanflación +1.06, resto +2.45, diferencia -1.39 [-4.98; +2.20]; 231 filas en estanflación. Con 237 país-años en estanflación esto no puede distinguir una modulación de 1-3 pp de cero.
- V6 log_cape h3_meses: b -0.83 (por año -3.32), R² 0.0096, t NW -2.14, p bootstrap 0.1784.
- V6 log_cape h6_meses: b -1.79 (por año -3.57), R² 0.0211, t NW -2.51, p bootstrap 0.1800.
- V6 log_dp h3_meses: b +0.60 (por año +2.39), R² 0.0050, t NW 1.44, p bootstrap 0.5176.
- V6 log_dp h6_meses: b +1.27 (por año +2.54), R² 0.0105, t NW 1.68, p bootstrap 0.4744.
- V6: A horizontes cortos la valoración explica muy poco de la rentabilidad; su información se acumula con el horizonte.
