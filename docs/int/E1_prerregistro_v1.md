---
documento: P-E1 — logit de ACTIVIDAD frente a logit de CURVA para la entrada en recesión a 12 meses (OCDE mensual): prerregistro
version: 1.0 (congelado 2026-11-05, decisiones §10 aprobadas por el usuario: todas las recomendadas)
estado: CONGELADO v1.0. Modo = REGISTRO PROSPECTIVO EN VIVO (decisión 1: el bloqueado ≥ 2005 NO se gasta en E1 ni
  se lee para contar eventos). Ningún indicador cruzado con ningún objetivo ≥ 2005. Ver §11 (lo que cambia respecto al
  borrador por las decisiones).
nace_de: INT-13 (EXPLORATORIO; research/int/int13_resultado.md, corrida 3bfd43a): el paquete de actividad (P3) es el
  que más aporta a E1-12 sobre el logit de curva (ΔAUC V1 +0,167 [+0,100; +0,226]; V2 0,82 frente a 0,66) pero NO pasa
  Holm-32 (p Holm 0,053). Su "Lectura" propone la pregunta confirmatoria "logit con actividad frente a logit con curva".
potencia: scripts/e1_potencia.py (commits 894a101 y 88b4b46, árbol limpio) → research/int/e1_potencia.json
depende_de: docs/int/INT13_plan_exploratorio.md, docs/int/INT4_prerregistro_v0.md (formato, criterios), docs/int/INT8_diseno_v0.md
  (potencia mensual: 11-22 episodios), docs/int/INT10_ml_potencia_v0.md (la potencia viene de eventos e información, no de
  capacidad), docs/int/PEVAL_INT4_potencia.md (cómo se gasta el bloqueado: refutación, no confirmación)
---

# P-E1: ¿la actividad anticipa la recesión a 12 meses mejor que la curva? (borrador v0.1)

## 0. Qué se pregunta (y lo que NO)
- **Pregunta:** con datos mensuales "as of" de la OCDE y un **logit congelado con datos ≤ 2004**, ¿añadir **actividad**
  (producción industrial interanual y confianza empresarial) al logit de **curva** (pendiente 10a − corto y Δ12 del tipo
  corto) ordena mejor los país-meses en los que un país **entra en recesión en los 12 meses siguientes**, en datos que el
  proyecto **no ha visto**?
- **H1 (unilateral):** ΔAUC = AUC(A) − AUC(L) > 0 y Δlog-loss < 0, con A = curva + actividad y L = curva (listón).
- **H0:** ΔAUC ≤ 0.
- **Contraste único declarado:** uno solo (ΔAUC de A frente a L, muestra principal, §5). Sin Holm porque no hay familia;
  todo lo demás es secundario o descriptivo y no puede convertir un "no" en un "sí".
- **No es** XGBoost ni ML: es un logit de 4 variables sin hiperparámetros (INT-10: la ganancia, si existe, es de la
  **información**, no del modelo; INT-13 no comparó el boosting con un lineal con la misma información).
- **No es** un nowcast mensual a 3-6 meses (INT-8: sin potencia) ni una probabilidad para el reporte: aunque saliera
  bien, la calibración en vivo no es comprobable en décadas (INT-8 §2).

## 1. Contaminación (declarada) y cómo se mitiga
**Por qué E1 está contaminada:**
1. **Nace de un análisis exploratorio** (INT-13) que miró 4 objetivos × 6 paquetes × 2 validaciones (64 evaluaciones) en
   los mismos datos ≤ 2004. El paquete de actividad es el **ganador** de esa búsqueda en E1 → maldición del ganador: el
   efecto real esperable es menor que +0,167 (se usa la mitad, ≈ +0,08, como caso realista).
2. **Los datos ≤ 2004 están gastados** para E1: INT-4 (T1 anual), INT-4-ML, INT-8 (potencia y recuentos), INT-8b (regla
   tipo Sahm, difusión de IP), INT-12 e INT-13 los usaron. Ningún resultado nuevo con ≤ 2004 cuenta como confirmación.
3. **Elección de variables con información de INT-13:** la confianza empresarial dominó las importancias (|SHAP|) de P3
   en E1-12. La justificación declarada aquí es otra (cobertura: IP y confianza son las dos series de actividad con más
   historia; el paro solo existe sin interpolar desde 1998 en 9 países, §2), pero la elección **no es ciega**.
4. **Objetivo retrasado:** el fechado trimestral entra 2-3 trimestres **después** del pico (INT-8). Parte de lo que la
   actividad "anticipa a 12 meses" es ver una recesión que ya ha empezado y que el PIB todavía no ha fechado. Es una
   amenaza a la interpretación ("anticipa" frente a "ve antes que el fechado"), no a la validez del contraste.
5. **El bloqueado tampoco es ciego del todo:** se sabe de memoria que en 2008 la confianza y la IP se hundieron en otoño,
   antes del fechado por PIB (2009T1), y que la curva europea apenas se invirtió en 2006-07; y que 2020 fue un choque sin
   aviso. Esto favorece a la actividad frente a la curva **en el bloqueado**, y lo sabíamos antes de diseñar.

**Mitigación (todo fijado antes de leer nada ≥ 2005):**
- **(M1) Separación estricta:** ≤ 2004 solo para **ajustar** (coeficientes congelados con sha256); la evaluación es
  únicamente fuera de muestra, en datos no vistos (bloqueado o vivo). Ninguna métrica ≤ 2004 entra en el veredicto.
- **(M2) Especificación mínima y cerrada:** 2 variables de actividad, lineales, sin transformaciones nuevas, sin
  interacciones, sin búsqueda; las mismas definiciones de `src/intl/int13.construir` (código ya congelado en 3bfd43a).
- **(M3) Potencia con la mitad del efecto** (maldición del ganador) y veredicto honesto si no llega (§6).
- **(M4) Comprobación de "anticipación pura"** (secundaria, decisión 6): repetir el contraste quitando las filas con la
  entrada en los 6 meses siguientes (y = 1 solo si la entrada cae en (M + 6, M + 12]). Si la ventaja desaparece ahí, se
  publica como "la actividad ve antes que el fechado; no anticipa" aunque el principal salga.
- **(M5) Contrapeso de lo que sabemos del bloqueado:** 2020 se excluye **a priori** de la muestra principal (choque
  exógeno; sensibilidad sin veredicto) y se publica el ΔAUC por episodio (Gran Recesión, crisis del euro, 2022-24) para
  que un solo episodio no decida en silencio.
- **(M6) Placebos** (§8) y **procedencia** con puerta (§9).

## 2. Datos y fuentes (todo "as of" en el fin de cada mes M; PIT por retrasos de publicación)
| uso | serie | fuente (familia permitida en `src/intl/data.py`) | retraso "as of" (`src/intl/lags.py`) |
|---|---|---|---|
| listón | `curva` = tipo 10a − corto | `oecd_irlt_*` (OCDE, mensual); corto = tipo oficial BIS `bis_cbpol_*` (16 países), letra 3 m OCDE `oecd_ir3m_*` en FIN e IRL (fuente única por país, como INT-13) | 1 día (en el fin de M se conoce M − 1) |
| listón | `d12_corto` = corto(M) − corto(M − 12) | ídem | ídem |
| actividad | `ip_yoy` = log IP 12 m | `oecd_ip_*` (OCDE) | 75 días |
| actividad | `confianza_emp` (nivel) | `oecd_bci_*` (OCDE, confianza empresarial) | 10 días |
| alternativa (decisión 3) | `paro_d12` | `oecd_unemp_*` (paro interpolado de 9 países antes de 1998 excluido, como `panel.mensual`) | 75 días |
| objetivo | PIB trimestral real | `oecd_gdpq_*` (OCDE QNA, capa curada) → `termometro.fechado_trimestral` | ex post (objetivo, nunca rasgo) |

- **Países: 16** (BEL, CAN, DEU, DNK, ESP, FIN, FRA, GBR, IRL, ITA, JPN, NLD, NOR, PRT, SWE, USA). **AUS y CHE fuera**:
  no hay `oecd_ip_aus` ni `oecd_retail_aus`, y CHE no tiene paro (comprobado en el catálogo de series, sin leer valores).
- **PIT, con límites declarados:** "as of" = retrasos conservadores de publicación sobre la **última añada** del
  warehouse, no añadas reales. La confianza casi no se revisa; la IP sí (revisión no modelada; sesgo a favor de la
  actividad, de tamaño desconocido). El objetivo usa el PIB revisado a propósito: es lo que se quiere anticipar.
- **Muestra de ajuste (≤ 2004):** filas de E1-12 de INT-13 con las 4 columnas completas: **3.306 filas, 240 eventos,
  140 meses con evento, 16 países, ≈ 11 episodios** (1960-01 … 2003-12). Listón y candidato se ajustan con **las
  mismas filas**. (La muestra de la base de INT-13 tenía 5.232 / 380; con paro serían 1.356 / 90 y 11 países.)
- **Muestra de evaluación:** ver §3 y la decisión 1. Para el bloqueado haría falta un cargador nuevo y aislado
  (`load_bloqueado`, fuera de `src/intl/data.load_dev`), que solo se activa con la autorización registrada (§9).

## 3. Objetivo (idéntico a E1-12 de INT-13)
- Fechado trimestral del termómetro sobre el PIB OCDE: entra en el trimestre de la **2.ª caída seguida de la suma de 4
  trimestres**; mes de entrada = último mes de ese trimestre. **y(M) = 1 si hay una entrada en (M, M + 12].**
- **En riesgo:** filas cuyo trimestre (el que contiene M) no está en recesión según el fechado (ex post).
- **Bloqueado (si se usa):** orígenes 2005-01 … 2023-12 (el objetivo acaba ≤ 2024-12). Los orígenes 2004-01 … 2004-12
  no entran en ningún lado (su objetivo cae en 2005): embargo natural de 12 meses entre el último objetivo de ajuste y la
  primera predicción evaluada.
- **Principal sin 2020:** fuera los orígenes 2019-01 … 2021-06 (su ventana toca la pandemia). **Con 2020:** sensibilidad.

## 4. Modelos (fijados aquí; nada se elige después)
- **L (listón = "la curva"):** logit(`curva`, `d12_corto`), la base de INT-13. Signos esperados: curva −, d12_corto +.
- **A (candidato = "curva + actividad"):** logit(`curva`, `d12_corto`, `ip_yoy`, `confianza_emp`). Signos esperados:
  ip_yoy −, confianza_emp −. **Anidado** (decisión 4): la pregunta es si la actividad **añade** a la curva.
- Ajuste: `src/intl/int4.logit_fit` (sin penalizar), rasgos estandarizados con media/dt de la muestra de ajuste ≤ 2004,
  agrupado (sin efectos fijos de país), **una vez** con todas las filas de ajuste. Coeficientes, medias y dt se guardan en
  JSON con sha256 **antes** de leer nada ≥ 2005. Si un signo de la actividad sale al revés en el ajuste ≤ 2004, se
  publica y se para (no se cambia la especificación).
- **Congelado, sin reajustar** en la evaluación (recomendado, decisión 5): ni intercepto nuevo, ni recalibración, ni
  ventana creciente. Alternativa: walk-forward anual con ventana creciente y embargo de 12 meses (más realista, pero
  cada reajuste "mira" una parte del bloqueado y los coeficientes dejan de ser los registrados).
- Casos completos: una fila cuenta si tiene las 4 columnas (las mismas filas para A y L).

## 5. Métrica y contraste único
- **Principal:** ΔAUC = AUC(A) − AUC(L) sobre las predicciones apiladas (país × mes) de la muestra principal.
  AUC y no log-loss como principal porque con el intercepto congelado la tasa base del bloqueado (otra que la de
  desarrollo) mueve la log-loss de los dos modelos por igual y añade ruido de nivel; la log-loss entra como condición.
- **p-valor del contraste único:** placebo de desplazamiento circular (§8, P1), unilateral; α = 0,05. El error típico
  agrupado por bloques de 24 meses y el bootstrap por bloques se publican, pero con 2-4 bloques con evento no son fiables
  como inferencia (por eso el p sale del placebo).
- **Secundarios (sin veredicto):** Δlog-loss y ΔBrier; pendiente e intercepto de calibración de A; ΔAUC por episodio;
  ΔAUC con 2020; "anticipación pura" (M4); AUC de A y de L frente a 0,5; A con paro (si la decisión 3 lo incluye) solo
  en los países con paro.

## 6. Potencia (antes que nada)
**Método** (`scripts/e1_potencia.py`, commit 88b4b46, árbol limpio, 2026-11-04T13:54Z, 538 s →
`research/int/e1_potencia.json`): estructura de eventos (real ≤ 2004; **supuesta** para 2005-2024, sin leer ninguna
serie ≥ 2005) y puntuaciones **simuladas** binormales; ruido AR(1) φ = 0,95, componente común entre países ρ, ruido
modelo-listón correlacionado r, y **heterogeneidad del efecto entre episodios** τ (desplazamiento común a todos los
positivos de un episodio; τ = 0,4 ≈ dt 0,11 de ΔAUC por episodio). Listón AUC 0,661 (INT-13). Probabilidades congeladas
calibradas a la tasa de desarrollo (para Δlog-loss). 600 réplicas por punto (error Monte Carlo ≈ ±0,02). Contraste
unilateral 5 % con el **valor crítico empírico** de la nula simulada (equivale al p del placebo de §8): el z nominal con
error típico agrupado por bloques de 24 meses tiene **tamaño real 16-33 %** en el bloqueado (pocos bloques con evento):
no sirve como inferencia.

**Calibración con una cifra ya publicada:** el error típico de ΔAUC de INT-13 (P3 frente a base, E1-12, V1) es ≈ 0,032.
En la estructura de desarrollo la simulación lo reproduce con τ = 0, ρ = 0, r = 0,5 (0,034); con τ = 0,4 sale 0,040
(+23 %), con τ = 0,6-0,8, 0,053-0,064. **Solo τ ≈ 0 es compatible con INT-13**, pero ese error típico sale de dejar un
país fuera con las mismas fechas en el entreno (INT-13 dice que V1 "aprende el calendario"), así que probablemente
subestima la incertidumbre real: **τ = 0 es el caso optimista y τ = 0,4 el prudente.**

**Estructuras supuestas del bloqueado** (16 países, orígenes 2005-01 … 2023-12; de memoria, historia pública):
Gran Recesión (entradas 2008T4-2009T1, 16 países), crisis del euro (PRT, ITA, ESP, NLD, FIN, BEL; 2011T4-2013T1),
2023 (DEU, SWE, FIN), 2020 (15 países, sin IRL).

| muestra (supuesta) | filas | eventos | episodios | MDE ΔAUC 80 % τ = 0 / **0,4** | potencia si Δ = +0,167 (dev) τ 0 / 0,4 | potencia si Δ = +0,08 (mitad) τ 0 / 0,4 | P(ΔAUC > 0) con +0,08 | ídem bajo H0 |
|---|---|---|---|---|---|---|---|---|
| **central sin 2020 (principal)** | 2.820 | 250 | 3 | **0,15 / 0,21** | 0,89 / 0,62 | **0,41 / 0,22** | 0,95 / 0,84 | 0,50 |
| pesimista sin 2020 (euro con 4 países, sin 2023) | 2.859 | 200 | 2 | 0,17 / 0,28 | 0,81 / 0,47 | 0,36 / 0,20 | 0,94 / 0,82 | 0,50 |
| solo la Gran Recesión | 2.928 | 160 | 1 | 0,15 / > 0,30 | 0,88 / 0,33 | 0,37 / 0,13 | 0,91 / 0,79 | 0,50 |
| central con 2020 (sensibilidad) | 3.165 | 400 | 4 | 0,11 / 0,18 | 0,99 / 0,75 | 0,62 / 0,29 | 0,98 / 0,88 | 0,47 |
| central sin 2020, listón AUC 0,60 | 2.820 | 250 | 3 | 0,16 (τ 0) | — | 0,29 | — | — |

(τ = 0,6 / 0,8: MDE 0,28 / > 0,30 en la central.) **Referencia ≤ 2004** (estructura de ajuste, 11 episodios): MDE 0,13
(τ 0): coherente con que INT-13 viera +0,167 y quedara en el borde de Holm.

**En vivo** (estructuras sintéticas, 16 países, 60 % de países por episodio, ≈ 3,6 episodios por década):

| episodios nuevos | años aprox. | MDE τ = 0 / 0,4 | potencia con +0,08: τ 0 / 0,4 |
|---|---|---|---|
| 3 | 9 | 0,15 / 0,27 | 0,40 / 0,20 |
| 5 | 14 | 0,14 / 0,20 | 0,50 / 0,23 |
| 8 | 23 | 0,10 / 0,16 | 0,70 / 0,37 |
| 12 | 34 | 0,08 / 0,13 | 0,83 / 0,45 |
| 16 | 45 | 0,07 / 0,10 | 0,93 / 0,71 |

**Lectura honesta:**
- **MDE del contraste único en el bloqueado (principal, sin 2020): ΔAUC ≈ 0,15 (optimista) – 0,21 (prudente).** El
  efecto realista (la mitad del de INT-13 por maldición del ganador, +0,08) está **muy por debajo**: potencia
  **0,22-0,41**. Solo un efecto tan grande como el de INT-13 (+0,167) tendría potencia razonable (0,62-0,89), y eso
  es justo lo que no se puede suponer de un ganador exploratorio.
- La razón es la de INT-8 y P-EVAL-INT4: el bloqueado tiene **≈ 2-3 episodios** sin 2020 (uno, la Gran Recesión,
  pesa más de la mitad). Muchas filas, poca información.
- Con 2020 sube algo (0,11-0,18), pero 2020 es el episodio en que "la actividad gana" por construcción (el choque llega
  sin curva invertida y la confianza se hunde a la vez que el PIB): sería ganar con el episodio que menos dice.
- **El signo sí es informativo para refutar:** con un efecto real de +0,08, P(ΔAUC ≤ 0) ≈ 5-16 %; sin efecto, 50 %. Un
  ΔAUC negativo multiplica por ≈ 3-10 la verosimilitud de "no aporta". Un ΔAUC positivo apenas confirma (≈ × 1,7-1,9).
- **En vivo** hacen falta **≈ 30-45 años** (12-16 episodios) para detectar +0,08.
- **Veredicto: sin potencia para confirmar. No recomiendo correr E1 como confirmación en el bloqueado.**

## 7. Criterios de éxito y de refutación (muestra principal, sin 2020)
Como el bloqueado no tiene potencia para confirmar (§6), el criterio se plantea como **prueba de refutación** (formato
de P-EVAL-INT4), con la potencia escrita delante:
- **Refutado** ("la actividad no añade a la curva fuera de muestra"): ΔAUC ≤ 0 **o** Δlog-loss ≥ 0 (punto). Probabilidad
  de refutar por error (ΔAUC ≤ 0 o Δlog-loss ≥ 0) si el efecto real es +0,08: ≈ 7-23 % (τ 0-0,4, central y pesimista); si es +0,167: ≈ 0-6 %; sin efecto: ≈ 50 %.
- **Confirmado** (todos): (i) ΔAUC > 0 con p del placebo P1 < 0,05 (unilateral); (ii) Δlog-loss < 0; (iii) pendiente de
  calibración de A en [0,5; 1,5]; (iv) ΔAUC > 0 en la Gran Recesión **y** en la crisis del euro por separado (que no lo
  decida un solo episodio). Potencia de (i) con +0,08: 0,22-0,41; el paquete completo, menos.
- **Ni refutado ni confirmado** en el resto (lo más probable): "no contradicho; sin potencia para confirmar". No se
  vuelve a correr con otra especificación.
- Secundarios (M4 anticipación pura, P2 países permutados, con 2020) se publican junto al veredicto y lo **matizan**
  (p. ej., "confirmado pero solo como nowcast del fechado") sin cambiarlo.

## 8. Placebos y controles
- **P1 desplazamiento circular (da el p del contraste):** se desplazan `ip_yoy` y `confianza_emp` k meses en círculo
  dentro de la muestra de evaluación (misma k para todos los países, k ∈ [24, T − 24]), se recalcula ΔAUC con los
  coeficientes congelados; p = (1 + #{ΔAUC_k ≥ ΔAUC_obs}) / (1 + nº de k). Conserva la persistencia y la sincronía entre
  países; rompe la alineación temporal con el objetivo.
- **P2 países permutados:** a cada país se le asigna la actividad de otro país del mismo mes (rotación fija del orden
  alfabético). Si A sigue ganando igual, la ventaja es del **calendario global** y no de la actividad del país (la
  objeción de INT-13 a P6). Descriptivo.
- **P3 actividad retrasada 24 meses:** la actividad de M − 24 no debería ayudar; si ayuda, hay algo mal (fuga o efecto
  de nivel). Descriptivo.
- **P4 señal plantada (sintético, antes de la corrida):** la tubería entera con datos inventados y una señal conocida
  debe recuperarla; con la señal quitada, ΔAUC ≈ 0.
- **P5 corte PIT:** test de que el ajuste no lee nada ≥ 2005 y de que la evaluación no lee nada antes de la
  autorización; test de que con `hasta = 2004` la tubería reproduce las filas de INT-13 (3.306 / 240).

## 9. Procedencia y puerta
- `scripts/e1_corrida.py` (no escrito): `src/intl/procedencia.procedencia(exigir_limpio=True)` (commit, árbol limpio,
  hora UTC en la salida); comprueba el sha256 de este documento congelado y del JSON de coeficientes; se niega si la
  salida ya existe; **no lee nada ≥ 2005 sin un fichero de autorización** con la decisión registrada del usuario.
- Una sola corrida; entrada en `research/trial_log.md` con el número de pruebas (1 principal + secundarios declarados);
  Validador independiente del diseño y del resultado.

## 10. Decisiones pendientes del usuario (con mi recomendación)
1. **¿Gastar el bloqueado en E1?** **Recomendado: NO ahora.** MDE 0,15-0,21 frente a un efecto realista de +0,08
   (potencia 0,22-0,41). El bloqueado es una corrida única que conviene reservar para lo ya establecido (P-EVAL-INT4
   T1/T2, X1, motor v3). Si se gasta, solo como **refutación** (§7) y cuando una decisión dependa de ello.
2. **Muestra confirmatoria:** **recomendado: registro prospectivo en vivo** (modelos L y A congelados con ≤ 2004,
   predicción mensual con procedencia en `research/`, sin mostrarla como probabilidad en el reporte), con la evaluación
   fijada desde ya para cuando haya ≥ 12 episodios nuevos (≈ 30+ años) y revisiones intermedias solo descriptivas. Es
   barato y no gasta nada, pero no dará respuesta en un horizonte útil: declararlo así.
3. **Variables de actividad:** **recomendado `ip_yoy` + `confianza_emp`** (3.306 filas / 240 eventos de ajuste, 16
   países). Alternativas: + `paro_d12` (1.356 / 90, 11 países: ajuste pobre) o solo confianza (18 países, pero es la
   elección más contaminada por los SHAP de INT-13).
4. **Anidado frente a no anidado:** **recomendado anidado** (curva + actividad frente a curva), que es lo que midió
   INT-13 (corrección sobre la base). "Actividad sola frente a curva sola" como descriptivo.
5. **Congelado frente a walk-forward en la evaluación:** **recomendado congelado** (coeficientes con sha256, sin
   reajuste); el walk-forward anual con embargo de 12 meses queda como sensibilidad.
6. **"Anticipación pura" (M4, quitar los 6 meses previos a la entrada):** **recomendado incluirlo como secundario
   obligatorio de publicar**, porque el fechado va 2-3 trimestres tarde y es la amenaza principal de interpretación.
7. **2020 fuera a priori:** **recomendado sí** (principal sin 2020; con 2020 como sensibilidad sin veredicto).
8. **¿Contar los eventos reales del bloqueado** leyendo solo el PIB (como P-EVAL-INT4) para sustituir las estructuras
   supuestas? **Recomendado solo si se elige la opción 1 = sí**; si no, no tocar el bloqueado ni para eso.
9. **Métrica principal ΔAUC** (log-loss como condición) frente a Δlog-loss principal (como INT-13): **recomendado ΔAUC**
   por el intercepto congelado (§5).
10. Si se aprueban 1-9, este borrador pasa a v1.0 con hora **antes** de escribir `scripts/e1_corrida.py`.

## 11. Decisiones registradas (v1.0, 2026-11-05) y lo que implican
Aprobadas por el usuario ("ok E1") las recomendaciones 1-9 de §10:
1. **Bloqueado NO se gasta en E1** (ni para contar eventos, decisión 8). `load_bloqueado` no se escribe.
2. **Confirmación = registro prospectivo en vivo:** L y A congelados con ≤ 2004 (coeficientes + media/dt con sha256 en
   `research/int/e1_modelos.json`); cada mes, una predicción por país con procedencia en `research/int/e1_vivo.jsonl`
   (solo meses de origen ≥ 2026-11, posteriores a esta congelación). **No se muestra como probabilidad en el reporte.**
   Evaluación (§5, §7 con la muestra en vivo en lugar del bloqueado) fijada para cuando haya **≥ 12 episodios nuevos**
   (≈ 30+ años); antes, solo revisiones descriptivas sin veredicto. Declarado: no dará respuesta en un horizonte útil.
3. Actividad = `ip_yoy` + `confianza_emp` (paro fuera). 4. Anidado. 5. Congelado sin reajuste (walk-forward = sensibilidad).
6. M4 "anticipación pura" secundario obligatorio. 7. 2020 fuera a priori (aplica igual a pandemias/choques futuros solo
   si se declaran ANTES de ver la predicción; ninguno declarado). 9. Principal ΔAUC; log-loss como condición.

**Pasos ejecutables (orden fijo):** (a) `scripts/e1_corrida.py --sintetico` = P4 (señal plantada recuperada; sin señal
ΔAUC ≈ 0); (b) `scripts/e1_corrida.py` = ajuste único ≤ 2004 con puerta (árbol limpio, sha256 de este documento,
comprueba 3.306 filas / 240 eventos de INT-13 = P5, signos de §4: si la actividad sale al revés, se publica y se para);
(c) `scripts/e1_vivo.py` mensual (pendiente; usa datos en vivo como `src/report/termometro_vivo`).
