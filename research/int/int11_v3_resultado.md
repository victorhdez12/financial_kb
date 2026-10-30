---
documento: Resultado P-INT11 v3 v1.0, fase D (corrida única de DESARROLLO del motor v3)
prerregistro: docs/int/INT11_prerregistro_v3.md (v1.0, 00d2019)
procedencia: {'commit': 'da6011115c8a5a23dafae4b6323ebd1e20987c80', 'arbol_limpio': True, 'hora_utc': '2026-10-30T18:21:51+00:00'}
datos: JST ≤ 2004, 14 países, sin guerras ni hiperinflación. NADA ≥ 2005. NO confirmatorio (v3 se diseñó tras ver v1 y v2 en estos datos)
---

# INT-11 v3: resultado de la corrida de desarrollo

## En una frase
Puerta D (dejando cada país fuera): **PASA**. Los abanicos del 90 % de v3 contuvieron lo
que pasó el **89.8 %** de las veces (v2 en los mismos pliegues: 89.5 %); en los regímenes
raros, el **89.8 %** (v2 88.3 %); cerca del umbral del 3 %, el
**94.0 %** (v2 92.3 %, 164 filas).
v3 sustituye a v2 en la confirmación futura (fase C, D7).

## 1. Puerta D (LOCO)
| criterio | valor | umbral | ¿cumple? |
|---|---|---|---|
| S5 (5 activos) | 0,8976 | ≥ 0.8965 (p2,5 del nulo P1) y ≤ 0,93 | True |
| cada activo | bolsa 0,923, bonos 0,908, letras 0,882, vivienda 0,896, oro 0,896 | 0,90 ± 0,03 | True |
| regímenes raros | 0,8976 | ≥ 0.8852 (p10 del nulo) | True |

Banda nula (P1, 20 × 100) de S5 LOCO [0.8965, 0.9143] (media 0.9059); raros
[0.864, 0.9467]; temporal S5 [0.8805, 0.9292].

## 2. Por activo (cobertura del p5-p95)
| activo | LOCO v3 | LOCO v2 | temporal v3 | temporal v2 | banda nula LOCO por activo |
|---|---|---|---|---|---|
| bolsa | 0,923 | 0,901 | 0,822 | 0,814 | [0.8959, 0.9181] |
| bonos | 0,908 | 0,898 | 0,919 | 0,901 | [0.8936, 0.9192] |
| letras | 0,882 | 0,895 | 0,982 | 0,977 | [0.8935, 0.9184] |
| vivienda | 0,896 | 0,908 | 0,939 | 0,933 | [0.9016, 0.9219] |
| oro | 0,896 | 0,885 | — | — | [0.8939, 0.9243] |

Temporal (< 1950 → 1950-2004, descriptivo): S5 v3 0,915 (v2 0,906), bolsa v3 0,822 (v2 0,814).
Anchura media del p5-p95 de la bolsa (LOCO): v3 0,797 frente a v2 0,723.

## 3. Cobertura por régimen de partida (LOCO, v3)
| régimen conocido | filas | bolsa | bonos | letras | vivienda | oro |
|---|---|---|---|---|---|---|
| expansion | 833 | 0,933 | 0,920 | 0,883 | 0,896 | 0,929 |
| sobrecalentamiento | 616 | 0,914 | 0,894 | 0,881 | 0,894 | 0,876 |
| estanflacion | 34 | 0,900 | 0,893 | 0,885 | 0,895 | 1,000 |
| crecimiento_bajo | 65 | 0,897 | 0,897 | 0,885 | 0,918 | 1,000 |

## 4. Cobertura por país (LOCO; el país se predice sin sus propios datos)
| país | filas | 5 activos v3 | 5 activos v2 | bolsa v3 | banda nula del país (5 activos) |
|---|---|---|---|---|---|
| BEL | 112 | 0,884 | 0,873 | 0,920 | [0.8333, 0.9139] |
| DEU | 106 | 0,912 | 0,902 | 0,868 | [0.8607, 0.9297] |
| DNK | 112 | 0,926 | 0,933 | 0,973 | [0.9045, 0.9581] |
| ESP | 112 | 0,863 | 0,879 | 0,946 | [0.8611, 0.9345] |
| FIN | 111 | 0,821 | 0,812 | 0,833 | [0.7994, 0.8817] |
| FRA | 109 | 0,905 | 0,913 | 0,936 | [0.8852, 0.9468] |
| GBR | 112 | 0,924 | 0,926 | 0,964 | [0.9034, 0.9581] |
| ITA | 110 | 0,911 | 0,908 | 0,909 | [0.8847, 0.9433] |
| JPN | 109 | 0,863 | 0,852 | 0,894 | [0.8162, 0.9035] |
| NLD | 112 | 0,931 | 0,924 | 0,968 | [0.9199, 0.9604] |
| NOR | 112 | 0,921 | 0,914 | 0,955 | [0.9209, 0.9652] |
| PRT | 107 | 0,844 | 0,845 | 0,841 | [0.7839, 0.8824] |
| SWE | 112 | 0,932 | 0,931 | 0,955 | [0.9294, 0.9708] |
| USA | 112 | 0,926 | 0,916 | 0,955 | [0.9082, 0.9627] |

## 5. Descriptivos
- **Inflación > 5 % (Brier, LOCO):** BSS v3 26,9 % (v2 25,1 %); Brier cerca
  del umbral v3 0,1493 (v2 0,1768); p media cerca 0,262
  frente a frecuencia 0,165. Temporal: BSS v3 25,0 % (v2 24,3 %).
- **Bolsa ≤ −20 % (Brier, LOCO):** BSS v3 2,2 % (v2 2,0 %),
  frecuencia 0,091.
- **κ** (motor con todas las filas): 1e+06 (en el borde: True).
- **Factor de dispersión de la bolsa por país** (v3; entre paréntesis v2): BEL 0.85 (0.91), DEU 1.19 (1.08), DNK 0.80 (0.90), ESP 0.96 (0.95), FIN 1.10 (0.98), FRA 0.83 (0.91), GBR 0.86 (0.91), ITA 0.95 (0.95), JPN 1.20 (1.01), NLD 0.80 (0.90), NOR 0.84 (0.91), PRT 1.24 (1.03), SWE 0.73 (0.87), USA 0.85 (0.91).
- **Curtosis (exceso) estandarizada por país, panel:** [4.05, 2.66, 5.63, 2.68, 0.15] (v2 agrupada: [16.75, 4.7, 22.61, 3.94, 1.5]).
- **n efectivo de Kish (bolsa) de las celdas raras:** {'crecimiento_bajo→expansion': 20.9, 'crecimiento_bajo→crecimiento_bajo': 20.2}.

## 6. Lectura
- **Calibración (desarrollo):** 89.8 % (v2 en los mismos pliegues 89.5 %); raros 89.8 %; país peor cubierto FIN (82.1 %); países por debajo de su banda nula: ninguno. La puerta D pasa.
- **Temporal (≤ 1949 → 1950-2004, descriptivo):** S5 91.5 %, bolsa 82.2 % (v1 80,5 %, v2 81,6 %). La semivida no puede corregir este diseño (pondera 1900-1949); es el riesgo principal de la confirmación.
- **Qué significa:** NO es una confirmación: v3 se diseñó mirando v1 y v2 en estos mismos datos. Solo dice si los arreglos hacen lo que se esperaba. La confirmación (K1, K2) está en el prerregistro §6 y se hará una vez, dentro de la confirmación final del proyecto; el periodo ≥ 2005 sigue sin gastar.

## 7. Nota del Constructor (a posteriori; no cambia el veredicto)
- **Pasa por poco.** S5 = 0,8976 frente al p2,5 nulo 0,8965 (0,1 pp de margen) y por debajo de la media nula (0,906):
  el motor real sigue algo más estrecho que su propio nulo. Con la tolerancia de v2 (±1,5 pp) habría pasado holgado;
  con la regla de la banda pasa justo. La banda nula usa 20 × 100 sorteos (la real 200 × 100), declarado.
- **Letras 88,2 %** queda dentro de ±3 pp (criterio 2) pero por debajo de su banda nula por activo [89,4; 91,8] (descriptivo).
- **Lo que mejoró respecto a v2 en los mismos pliegues:** raros 88,3 → 89,8 %; cerca del umbral 92,3 → 94,0 %; Brier
  de inflación > 5 % cerca del umbral −16 % (0,177 → 0,149), BSS global 25,1 → 26,9 %. La curtosis por país se ve
  (bolsa 16,8 → 4,1) y los volátiles se ensanchan (JPN 1,01 → 1,20; PRT 1,03 → 1,24; DEU 1,08 → 1,19), pero FIN (82 %),
  PRT (84 %), JPN y ESP (86 %) siguen por debajo del 90 % (dentro de sus bandas nulas por país).
- **Coste:** la anchura media del p5-p95 de la bolsa sube un 10 % (0,723 → 0,797) y la bolsa sobrecubre (92,3 %).
- **Temporal bolsa 82,2 %** (v2 81,6 %): la no estacionariedad sigue sin resolverse en el diseño de desarrollo, como se
  anticipó (diseño §2.4). Es el riesgo principal de K1.
