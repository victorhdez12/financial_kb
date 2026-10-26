---
documento: P-DEV-INT3 — prerregistro interno del mapa régimen → activos (panel internacional anual)
version: 0.1-borrador (2026-10-27)
estado: BORRADOR para el usuario. Nada corrido. Ninguna rentabilidad mirada por régimen.
depende_de: INT-1 (etiquetas anuales, G = nivel frente a tendencia) e INT-2 v0.2 (potencia)
---

# P-DEV-INT3 v0.1 (borrador): ¿qué activos van mejor en cada régimen?

## 0. Qué es y qué no es
- Es la **descripción histórica** (ex post) de cómo rinden los activos en cada régimen, en 14 países y 135 años. Responde a
  la primera pregunta del usuario: "en qué régimen estamos y qué activos son más ventajosos ahí".
- **No es todavía una regla de inversión.** La versión "operable" (régimen conocido con retraso → rentabilidad siguiente)
  se mide como pregunta secundaria (§4) y, si sale, pasará a INT-5 (B2 en sombra frente a B1).
- Pocas preguntas (≤ 6), elegidas por mecanismo antes de mirar, porque INT-2 dice que solo se distinguen efectos grandes
  (bolsa ≈ 7 pp con un contraste, ≈ 8-10 pp con varios).

## 1. Datos y muestra
- JST R6, rentabilidades **reales** anuales: `eq_tr_real`, `bond_tr_real`, `bill_rate_real`, `housing_tr_real`.
- Regímenes: etiqueta anual de INT-1 (principal: inflación relativa + 2 %), `regimen_anual_dev.parquet`; recesiones JST.
- **Núcleo:** 14 países (BEL, DEU, DNK, ESP, FIN, FRA, GBR, ITA, JPN, NLD, NOR, PRT, SWE, USA). **1870-2004**, sin años
  truncados. Corte técnico ≤ 2004 (`src/intl/data.py`).
- **Países de prueba:** AUS y CHE (CAN e IRL no tienen rentabilidades en JST: no sirven aquí). No entran en ninguna
  estimación ni elección; se miran al final.
- Rentabilidad del año t frente al régimen del año t (contemporáneo, ex post).

## 2. Preguntas, mecanismo y expectativa a priori (escritas antes de mirar)

| id | pregunta (contraste: estado frente al resto) | mecanismo | signo esperado |
|---|---|---|---|
| **Q1** | bolsa real en **estanflación** | caen beneficios reales y suben tipos reales esperados; prima de riesgo al alza | − (grande) |
| **Q2** | bonos reales con **inflación alta** (sobrecalentamiento + estanflación) | la inflación no esperada erosiona el cupón nominal y sube los tipos | − |
| **Q3** | bonos reales en **crecimiento bajo / desinflación** | bajan tipos e inflación: plusvalía en el bono | + |
| **Q4** | letras reales con **inflación alta** | los tipos cortos van por detrás de la inflación → tipo real negativo | − |
| **Q5** | bolsa real en **recesión** (años de pico a valle); y recesión **financiera** frente a normal | caída de beneficios; las financieras son más hondas (Jordà-Schularick-Taylor) | − ; financiera más negativa |
| **Q6** | **vivienda frente a bolsa** (diferencia de rentabilidad real) con **inflación alta** | activo real con rentas que se ajustan a la inflación | + (relativo) |

## 3. Método
- **Principal:** diferencia de medias de la rentabilidad real (estado − resto), con **errores agrupados por año** (CR2) y
  efectos fijos de país; contraste bilateral al 5 % con **Holm sobre las 6 preguntas** (Q5 cuenta su parte principal).
- **Heterogeneidad entre países:** modelo **jerárquico** (efecto del estado por país, con agregación parcial hacia el
  común y efecto aleatorio de año para los choques globales). PyMC si está instalado; si no, modelo mixto de
  `statsmodels` + encogimiento empírico de Bayes. Da el efecto encogido de cada país.
- **Placebo:** los mismos contrastes con los regímenes desplazados ≥ 6 años (como INT-2): tasa de falsos positivos.

## 4. Criterio de "efecto establecido" (todas)
1. Signo igual al esperado.
2. IC 95 % agrupado por año sin el 0, tras Holm.
3. Mismo signo en **≥ 2/3 de los países** del núcleo (efectos encogidos).
4. Mismo signo en **1950-2004** (sin exigir significación: ahí la potencia es menor).
5. Placebo: la tasa de falsos positivos de los desplazados ≤ 10 %.

Pregunta secundaria (operable, informativa): las mismas Q1-Q6 con el régimen del año **t − 1** (conocido) frente a la
rentabilidad del año **t**.

## 5. Sensibilidades (se publican siempre; no deciden)
Sin años de guerra (1914-1918, 1939-1945); sin años en "frontera"; inflación absoluta 3 %; 1950-2004; rentabilidades
nominales; países de prueba AUS y CHE (signos).

## 6. Expectativa honesta (antes de correr)
- Q1, Q2 y Q4 son los efectos más documentados y grandes: probables.
- Q3 y Q5 dependen de cómo caigan los episodios; Q6 es la más incierta.
- Con un MDE de ≈ 7-9 pp en bolsa, un efecto verdadero de 5 pp puede no salir. "No establecido" no es "no existe".

## 7. Orden y gobierno
1. El usuario aprueba este texto → commit y push con hora (procedencia) **antes** de calcular nada.
2. Una sola corrida (script con puerta: árbol limpio, commit y hora en la salida). Todo al registro de pruebas.
3. Validador independiente del resultado.
4. El periodo bloqueado de JST (2005-2020) queda para una evaluación única aparte (P-EVAL-INT3), con su propio
   prerregistro, si el usuario lo decide.
