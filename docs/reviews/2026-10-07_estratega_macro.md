# Revisión Fase 1 — Estratega macro (2026-10-07)

Resumen: el marco mide niveles, no dato vs lo descontado (esencia de Dalio). Hay un bug de datos que distorsiona la inflación de 2026 y el tipo real.

## 1. G↓ en el 63 % de expansiones
`classify.py:46` exige G>0 **y** ΔG6m>0 → G↓ por defecto (32,6 % G<0; 28,9 % G>0 pero frenando).

| regla | recesión | 6m antes | expansión | cambios/año |
|---|---|---|---|---|
| actual | 96,5 | 80,3 | 63,2 | 1,61 |
| G<0 o Sahm | 93,8 | 51,5 | 34,5 | 0,97 |
| G 3m<0 o Sahm | 92,0 | 47,0 | 34,2 | 0,64 |
| **G 3m con histéresis ±0,15 o Sahm** | **90,3** | **54,5** | **30,4** | **0,43** |
| CFNAI-MA3<−0,35 (1967+) | 80,0 | 16,7 | 18,2 | – |

Propuesta: G 3m, tres estados (↓ si < −0,15 o Sahm; ↑ si > +0,15; "≈ frontera" mantiene estado); ΔG6m como eje de impulso aparte.

## 2. Lectura de hoy
- **BUG**: falta CPI oct-2025 (cierre del Gobierno); `db.py:31` descarta nulos y `features.py:27-32` hace shift por posición → yoy de nov-25 a sep-26 mide 13 meses. Core yoy 2,76 % (real 2,45 %); tipo real FF 0,99 (debería 1,30, `features.py:180`); 6m nov-25→mar-26 mide 7 meses.
- Frontera ALFRED vs revisado = 0,07 z → ruido.
- I solo mira core (`classify.py:63`): ignora WTI 97 $ (+52 % a/a), PPI +9,85 %, CPI general 6m ≈4,1 %, T5YIE p76, GPR 330.
- Curva: 10y 5,31, 2y 4,88, FF 3,75 → mercado descuenta subidas; term premium 0,50→1,08; DFII10 2,95.
- Lectura del revisor: **estanflación por shock de oferta con presión fiscal y de term premium**, no deflación.

## 3. Ciclo de deuda / histórico
- 1972-82: 68 % "desapalancamiento" por NFCI>0 (`classify.py:106`) → falso.
- Sep-21–may-22 "reflación" por WALCL>10 % (`:107`) con real −6 → debería ser endurecimiento.
- Hoy "expansión temprana" por curva >1 empinándose (`:111`), pero es bear steepening.
- Ciclo largo: 2007 "temprano/medio"; `pct_rank` expansivo (`:149`) marca intereses/ingresos >p90 en 1960-90 (artefacto). Falta "tipos en el suelo".

## 4. Top 10 (impacto/esfuerzo)
1. Shifts por fecha (`asfreq('MS')`) y rehacer real/6m — alto/bajo.
2. G 3 estados con histéresis ±0,15 — alto/bajo.
3. I compuesta (core + general/petróleo + breakevens) con banda; no I↓ con core > 2,5 — alto/bajo.
4. Eje de sorpresa: SPF, Cleveland Fed, 2y−FF implícito — alto/medio.
5. Bear vs bull steepening (DGS2, THREEFYTP10); reflación exige FF bajando; ANFCI o z móvil en vez de NFCI>0 — alto/bajo.
6. Ciclo largo: TCMDO/PIB, TDSP, FF<0,5, r−g, umbrales absolutos; validar con JST 1929/1945/2008 — alto/medio.
7. Capa de shock de oferta: petróleo a/a > 40 % o GPR alto — medio/bajo.
8. Liquidez: tipo real vs r* en niveles — medio/bajo.
9. Nóminas vs breakeven, paro vs NROU — medio/bajo.
10. P(G↓) probabilística (logit/HMM) con Brier vs USREC y discrepancia por vintage — alto/alto.
