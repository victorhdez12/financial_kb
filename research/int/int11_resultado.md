---
documento: Resultado P-DEV-INT11 v1.0 (corrida única de desarrollo del motor de escenarios)
prerregistro: docs/int/INT11_prerregistro_v1.md (congelado en a9f6279)
procedencia: {'commit': '9cf53dfe55f333b6d2b7e9ed048fd5b414f598bd', 'arbol_limpio': True, 'hora_utc': '2026-10-30T08:34:40+00:00'}
datos: JST ≤ 2004, 14 países, sin guerras ni hiperinflación. NADA ≥ 2005. NO confirmatorio para C1 (Atlas §8 ya miró)
---

# INT-11: resultado de la corrida de desarrollo

## En una frase
Puerta de calibración (LOCO): **NO PASA**. C1 (el régimen mejora la distribución a 1 año
frente a no saberlo): **no establecido (motor no calibrado)** (CRPSS medio 1,79 %, p = 0,0106).

## 1. Calibración (¿el abanico p5-p95 contiene lo que pasó el 90 % de las veces?)
| | LOCO | banda simulada (2,5-97,5) | temporal 1950-2004 | banda simulada |
|---|---|---|---|---|
| S5 (5 activos) | 0,886 | [0.8927, 0.9003] | 0,906 | [0.856, 0.9174] |
| Sb (bolsa) | 0,895 | [0.8906, 0.902] | 0,805 | [0.8337, 0.9377] |

Criterios (LOCO): S5 en banda False; Sb en banda True; |S5 − 0,90| ≤ 5 pp True;
cada activo a ≤ 5 pp {'bolsa': True, 'bonos': True, 'letras': True, 'vivienda': True, 'oro': True}.

## 2. Por activo
| activo | cobertura 90 % LOCO | temporal | cobertura 80 % LOCO | cobertura 90 % de M0 (LOCO) | CRPSS % LOCO | CRPSS % temporal | CRPSS % h = 5 (desc.) | cobertura 90 % h = 5 (desc.) |
|---|---|---|---|---|---|---|---|---|
| bolsa | 0,895 | 0,805 | 0,797 | 0,900 | 0,95 | 0,43 | -0,27 | 0,927 |
| bonos | 0,892 | 0,906 | 0,792 | 0,898 | 2,14 | 1,58 | -0,83 | 0,870 |
| letras | 0,888 | 0,977 | 0,783 | 0,897 | 3,05 | 4,88 | -0,51 | 0,819 |
| vivienda | 0,894 | 0,942 | 0,790 | 0,898 | -0,08 | -1,06 | 0,30 | 0,864 |
| oro | 0,877 | — | 0,773 | 0,896 | 2,90 | — | -1,68 | 0,943 |

## 3. Contraste C1 (único, α = 0,05 unilateral)
LOCO: media de d = 0,0158 (mejora media del CRPS normalizado), t = 2,34, 112 años,
p = 0,0106. Temporal: media de d = 0,0143 (mismo signo: True).
Clasificación: **no establecido (motor no calibrado)**.

## 4. Descriptivo
**Por régimen de partida (LOCO):**

| régimen conocido | filas | cobertura 90 % bolsa | CRPSS % bolsa | CRPSS % bonos | CRPSS % letras |
|---|---|---|---|---|---|
| expansion | 833 | 0,898 | 0,9 | 1,4 | 2,4 |
| sobrecalentamiento | 616 | 0,900 | 1,1 | 1,7 | 3,2 |
| estanflacion | 34 | 0,867 | 0,1 | 16,8 | 5,7 |
| crecimiento_bajo | 65 | 0,828 | 0,1 | 3,1 | 4,3 |

**Eventos (Brier, LOCO):** caída de la bolsa ≥ 20 % (frecuencia 0,091): BSS
2,0 %; inflación > 5 % (frecuencia 0,267): BSS
25,0 %. (BSS > 0: el motor mejora a la frecuencia histórica.)

**PIT (10 casillas, LOCO):** {'bolsa': [152, 153, 146, 155, 146, 141, 152, 143, 152, 150], 'bonos': [156, 155, 147, 151, 151, 148, 152, 144, 159, 160], 'letras': [166, 152, 148, 151, 146, 158, 143, 154, 147, 166], 'vivienda': [136, 128, 130, 133, 126, 122, 122, 126, 124, 133], 'oro': [51, 51, 42, 46, 44, 37, 47, 37, 53, 54]}

## 5. Lectura
- **Calibración:** el abanico p5-p95 del motor contuvo lo realizado el 88.6 % de las veces (5 activos, dejando el país fuera; nominal 90 %); la bolsa, el 89.5 %. El activo más desviado es oro (87.7 %). La puerta NO pasa: los abanicos no tienen la anchura correcta en algún criterio (ver §1).
- **Finura:** frente a no saber el régimen, el CRPS mejora un 1.79 % de media (bolsa 0.95 %, bonos 2.14 %, letras 3.05 %). Era lo esperado por la potencia: mejoras pequeñas, sobre todo en bonos y letras.
- **C1: no establecido (motor no calibrado).** Recordatorio: no es confirmatorio (el Atlas ya cruzó régimen y rentabilidad con estos datos).
- **Temporal (entrenar ≤ 1949, evaluar 1950-2004):** cobertura 90.6 %, CRPSS 1.46 %.

## 6. Lectura del Constructor (A POSTERIORI; no cambia ninguna clasificación)
- **Lo que significa "no pasa":** los abanicos del 90 % aciertan el **88,6 %** dejando cada país fuera. Está dentro de la
  tolerancia de ±5 pp y la bolsa (89,5 %) está en su banda, pero la banda simulada del conjunto es muy estrecha
  ([89,3; 90,0]) porque el proceso sintético es **homogéneo** entre países (mismas volatilidades). El panel real no lo
  es: un país con más volatilidad que la media del panel falla más cuando se evalúa con el pool de los otros. Es decir,
  el motor es **algo estrecho** (≈ 1,4 pp) y la puerta, tal como se congeló, lo detecta. Los más estrechos: oro (87,7 %),
  letras (88,8 %).
- **Temporal (≤ 1949 → 1950-2004):** la bolsa cubre solo el **80,5 %** (fuera de su banda [83,4; 93,8]): con la
  historia anterior a 1950 el motor infravalora la dispersión de la bolsa en 1950-2004. Las letras cubren de más
  (97,7 %): sus rentabilidades reales fueron más tranquilas después de 1950. Aviso de **no estacionariedad**.
- **C1:** la mejora es la esperada por la potencia (CRPSS 1,8 %; p = 0,011, mismo signo en el temporal), pero por la
  regla congelada se clasifica "no establecido (motor no calibrado)". Y aunque hubiera pasado, no sería confirmatorio.
- **Eventos:** el motor mejora mucho la probabilidad de **inflación > 5 %** el año siguiente (BSS +25 %: la inflación es
  persistente) y casi nada la de **caída de la bolsa ≥ 20 %** (BSS +2 %).
- **h = 5 (descriptivo):** sin mejora (CRPSS ≈ 0 o negativo) y cobertura irregular (82-94 %): no usar el motor para
  afirmar nada a 5 años más allá de "abanico amplio".
- **Qué cambiaría en una v2 (prerregistro nuevo):** escala de dispersión por país (encoger la volatilidad del país hacia
  la del panel en lugar de usar el pool tal cual), y un proceso nulo con heterogeneidad entre países.
