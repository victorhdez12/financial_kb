---
documento: Resultado P-INT11 v2 v1.0, fase D (corrida única de DESARROLLO del motor v2)
prerregistro: docs/int/INT11_prerregistro_v2.md (v1.0)
procedencia: {'commit': '61a3a978073b5ac073dd6c74c6dc2c9129ed446d', 'arbol_limpio': True, 'hora_utc': '2026-10-30T12:50:41+00:00'}
datos: JST ≤ 2004, 14 países, sin guerras ni hiperinflación. NADA ≥ 2005. NO confirmatorio (v2 se diseñó tras ver v1 en estos datos)
---

# INT-11 v2: resultado de la corrida de desarrollo

## En una frase
Puerta D (dejando cada país fuera): **PASA**. Los abanicos del 90 % de v2 contuvieron lo
que pasó el **89.6 %** de las veces (v1: 88.6 %); en los regímenes raros, el
**88.9 %** (bolsa: 87.5 %; v1 solo publicó la bolsa: 84.1 %). Apto para la confirmación futura (fase C).

## 1. Puerta D (LOCO)
| criterio | valor | umbral | ¿cumple? |
|---|---|---|---|
| S5 (5 activos) | 0,8962 | 0,90 ± 0,015 | True |
| cada activo | bolsa 0,901, bonos 0,901, letras 0,897, vivienda 0,907, oro 0,887 | 0,90 ± 0,03 | True |
| regímenes raros | 0,8886 | ≥ 0.8571 (p2,5 del nulo) | True |

Informativo: banda nula (heterogénea) de S5 LOCO [0.8976, 0.9078] (media 0.9026),
Sb [0.8966, 0.9134]; temporal S5 [0.8739, 0.9239], Sb [0.8493, 0.9417].
Real temporal: S5 0,905, Sb 0,816.

## 2. Por activo
| activo | cobertura 90 % LOCO v2 | v1 | temporal v2 | cobertura 80 % LOCO | CRPSS % LOCO | CRPSS % temporal | cobertura 90 % h = 5 (desc.) |
|---|---|---|---|---|---|---|---|
| bolsa | 0,901 | 0,895 | 0,816 | 0,807 | 0,98 | 0,98 | 0,927 |
| bonos | 0,901 | 0,892 | 0,900 | 0,805 | 2,29 | 1,38 | 0,881 |
| letras | 0,897 | 0,888 | 0,977 | 0,799 | 3,21 | 4,43 | 0,830 |
| vivienda | 0,907 | 0,894 | 0,929 | 0,812 | -0,03 | -2,40 | 0,877 |
| oro | 0,887 | 0,877 | — | 0,788 | 3,03 | — | 0,943 |

## 3. Cobertura 90 % por régimen de partida (LOCO)
| régimen conocido | filas | bolsa | bonos | letras | vivienda | oro |
|---|---|---|---|---|---|---|
| expansion | 833 | 0,902 | 0,900 | 0,901 | 0,911 | 0,899 |
| sobrecalentamiento | 616 | 0,904 | 0,902 | 0,894 | 0,901 | 0,880 |
| estanflacion | 34 | 0,900 | 0,893 | 0,885 | 0,895 | 1,000 |
| crecimiento_bajo | 65 | 0,862 | 0,897 | 0,869 | 0,918 | 1,000 |

## 4. Cobertura 90 % por país (LOCO; el país se predice sin sus propios datos)
| país | filas | 5 activos | bolsa |
|---|---|---|---|
| BEL | 112 | 0,869 | 0,893 |
| DEU | 106 | 0,902 | 0,840 |
| DNK | 112 | 0,937 | 0,973 |
| ESP | 112 | 0,883 | 0,946 |
| FIN | 111 | 0,814 | 0,823 |
| FRA | 109 | 0,910 | 0,927 |
| GBR | 112 | 0,924 | 0,946 |
| ITA | 110 | 0,910 | 0,873 |
| JPN | 109 | 0,860 | 0,875 |
| NLD | 112 | 0,924 | 0,925 |
| NOR | 112 | 0,916 | 0,911 |
| PRT | 107 | 0,845 | 0,832 |
| SWE | 112 | 0,931 | 0,920 |
| USA | 112 | 0,918 | 0,929 |

## 5. Descriptivos
- **Finura (C1, sin decisión; contaminado):** CRPSS medio 1,90 % (v1 1,79 %);
  DM d = 0,0172, t = 2,44, p = 0,0082; temporal d = 0,0107.
- **Eventos (Brier, LOCO):** inflación > 5 % BSS 25,1 % (frecuencia
  0,267); caída de la bolsa ≥ 20 % BSS 2,0 %
  (frecuencia 0,091).
- **κ** (motor con todas las filas): 1e+06 (en el borde: True).
- **Factores de dispersión por país** (bolsa, motor con todas las filas): {'BEL': 0.91, 'DEU': 1.077, 'DNK': 0.896, 'ESP': 0.947, 'FIN': 0.985, 'FRA': 0.907, 'GBR': 0.914, 'ITA': 0.947, 'JPN': 1.015, 'NLD': 0.9, 'NOR': 0.909, 'PRT': 1.032, 'SWE': 0.872, 'USA': 0.914}.

## 6. Lectura
- **Calibración (desarrollo):** 89.6 % frente al 90 % nominal (v1 88.6 %); activo más desviado oro (88.7 %); regímenes raros 88.9 %; país peor cubierto FIN (81.4 %). La puerta D pasa.
- **Temporal (≤ 1949 → 1950-2004, descriptivo):** S5 90.5 %, bolsa 81.6 % (v1: bolsa 80,5 %). Es el diseño que más se parece a la confirmación futura.
- **Qué significa:** NO es una confirmación: v2 se diseñó mirando v1 en estos mismos datos. Solo dice si los arreglos hacen lo que se esperaba. La confirmación (K1 calibración, K2 inflación) está escrita en el prerregistro §6 y se hará una vez, dentro de la confirmación final del proyecto.

## 7. Lectura del Constructor (A POSTERIORI; no cambia ninguna clasificación)
- **Lo que mejoró:** la cobertura global pasa de 88,6 % a 89,6 % y todos los activos quedan entre 88,7 % y 90,7 %. Donde
  más se nota es en los casos difíciles: estanflación 90 % en la bolsa (v1 86,7 %); oro y letras, los más estrechos de
  v1, suben 1 pp. Era lo esperado por la potencia (sintético 90,3 %); el real queda ≈ 0,7 pp por debajo y **dentro de
  la tolerancia**, pero por debajo de la banda nula heterogénea [89,8; 90,8], que es informativa: v2 sigue siendo
  ligeramente estrecho en este panel.
- **Lo que no mejoró:** (1) **crecimiento bajo** (65 filas) sigue en 86 % en bolsa y 87 % en letras; (2) **países
  volátiles**: FIN 81 %, PRT 85 %, JPN 86 % — la escala por país, encogida con Bayes, los trata casi como el panel
  (factor posterior de la bolsa 0,87-1,08: con colas gruesas el error de medida del factor es grande y el encogimiento
  fuerte); un país nuevo y volátil seguirá teniendo abanicos algo estrechos; (3) **temporal, bolsa 81,6 %** (v1 80,5 %),
  fuera de su banda nula [84,9; 94,2]: la no estacionariedad no la arregla v2 y es **el riesgo principal de la
  confirmación K1** (que es un diseño "entrena antes, prueba después").
- **κ = 10^6, en el borde de la rejilla nueva:** las transiciones de régimen de los 14 países no se distinguen del panel.
  La lectura correcta es "un único Markov para todos", no un fallo.
- **Finura e inflación:** CRPSS 1,9 % (v1 1,8 %) y Brier de inflación > 5 % +25 %: los arreglos no cuestan precisión.
  Caída ≥ 20 %: +2 % (sin potencia para afirmar nada).
- **Siguiente:** fase C solo en la confirmación final única (K1 calibración 2005-2020, K2 inflación OCDE 2005-2025);
  mientras, registro mensual en vivo (docs/int/INT11_registro_vivo.md).
