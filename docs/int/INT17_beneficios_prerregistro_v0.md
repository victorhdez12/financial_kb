---
documento: P-DEV-INT17 — ¿los beneficios empresariales agregados (NIPA) anticipan la recesión de EE. UU. a 12 meses, con contenido incremental sobre E1? Diseño + potencia + borrador de prerregistro
version: 0.1 (borrador, 2026-11-18). Diseño (§0-§6, §8-§10) escrito y commiteado ANTES de escribir y correr la potencia; §7 se rellena con la salida del script
estado: BORRADOR. Solo diseño y potencia con señal plantada. Ningún rasgo de beneficios se ha cruzado con la etiqueta NBER (ni con ninguna otra); ningún dato ≥ 2005 leído.
potencia: scripts/int17_potencia.py → research/int/int17_potencia.json (§7)
nace_de: docs/int/INFORME_10k_2026-11-18.md §4, prioridad 2; plan aprobado 18-nov (Estado «▶ Retomar (18-nov)», línea B)
depende_de: docs/int/E1_prerregistro_v1.md (listón E1, coeficientes congelados research/int/e1_modelos.json sha256 227ffa8c…),
  docs/int/INT15_credito_prerregistro_v0.md (formato, potencia con efecto a la mitad, placebo circular), docs/int/INT8_diseno_v0.md
  (O4 NBER: 7 entradas 1960-2004, MDE ΔAUC ≈ 0,31), docs/int/EVAL_registros_vivo.md (cómo se evalúa E1 en vivo)
---

# P-DEV-INT17: ¿los beneficios agregados avisan de la recesión? (borrador v0.1)

## 0. Qué se pregunta (y lo que NO)
- **Pregunta (O1, contraste único):** con datos mensuales "as of" de EE. UU. ≤ 2004, ¿añadir el **crecimiento interanual
  de los beneficios empresariales reales** (NIPA, después de impuestos con IVA y CCAdj) al índice de E1 (curva + Δ12 del
  tipo corto + IP interanual + confianza empresarial) reduce la **log-loss fuera de muestra** (walk-forward con embargo)
  de la probabilidad de que EE. UU. **entre en recesión NBER en los 12 meses siguientes**?
- **H1 (unilateral):** D = LL(L) − LL(A) > 0 (nats por fila; L = E1, A = E1 + beneficios). **H0:** D ≤ 0.
- **Secundaria (S1, con Holm-2):** la misma pregunta con la **caída del margen** (log de beneficios/PIB nominal frente a
  su máximo de los últimos 8 trimestres).
- **No es** una señal para la cartera ni para el reporte (B0/B1/B1′ no usan el nowcast; el reporte no da probabilidades
  de recesión). **No es** una confirmación: es una corrida de desarrollo ≤ 2004; un "establecido" sería un candidato
  (como INT-13 → E1), cuya confirmación solo podría ser en vivo (el bloqueado ≥ 2005 NO se toca, opción A del 15-nov).
- **Listón = E1 tal cual** (índice lineal del modelo A congelado), recalibrado a la etiqueta NBER en el walk-forward.

## 1. Mecanismo económico (por qué podría funcionar)
- **Margen al final del ciclo:** en la fase tardía de una expansión, los costes laborales unitarios suben más que los
  precios (mercado de trabajo tenso) y los tipos suben; el margen se comprime antes de que caiga la producción.
- **Beneficios → inversión y empleo:** la inversión empresarial y la contratación dependen de los beneficios corrientes
  y esperados (financiación interna, señal de demanda). Una caída de beneficios precede a recortes de inversión y
  plantilla, que son los que convierten una desaceleración en recesión.
- **Por qué podría NO añadir a E1:** E1 ya tiene la curva (que recoge el endurecimiento monetario, causa común de la
  compresión de márgenes) y la IP y la confianza (que recogen la demanda). Lo que quede de los beneficios después de
  eso es la parte "de distribución" (salarios frente a beneficios), y su efecto incremental puede ser pequeño.
- **Contra el mecanismo, el dato:** los beneficios NIPA salen tarde (≈ 2-3 meses después del trimestre; §3) y se
  revisan mucho (IVA, CCAdj, revisiones de referencia). Lo que se gana en anticipación se pierde en parte por el retraso.

## 2. Contaminación (declarada) y mitigación
1. **La idea es conocida**: "los beneficios tocan techo antes de la recesión" es folclore de mercado y un hecho
   estilizado de los ciclos de EE. UU. que se recuerda de memoria (beneficios NIPA cayendo desde 1997-98 antes de 2001;
   desde 2006 antes de 2008, esto último en el bloqueado). Sesgo de publicación y de memoria a favor. No conozco con
   seguridad una cifra publicada del ΔAUC o de la ganancia de log-loss de los beneficios **sobre** un modelo de curva +
   actividad; por eso no se cita ninguna y el efecto plantado se fija con la convención del proyecto (§7).
2. **Los datos ≤ 2004 están gastados en general** (INT-4, INT-8, INT-8b, INT-12, INT-13, E1, M1…), pero los beneficios
   NIPA **no se han cruzado nunca** con ningún objetivo en el proyecto (grep de `CPATAX`, `A053RC1Q027SBEA`, `CP` en
   `src/`, `scripts/`, `docs/`: solo aparecen en la ingesta `src/ingest/fred_us.py`). Los beneficios de Shiller (S&P,
   `shiller_real_earnings`) entraron en INT-7, pero como valoración (CAPE) y frente a rentabilidades, no a recesiones.
3. **El listón E1 está ajustado con datos ≤ 2004 que incluyen EE. UU.** (dentro de muestra para el listón, con la
   etiqueta OCDE y no la NBER). Favorece al listón: hace el contraste más exigente para los beneficios. Declarado.
4. **La etiqueta NBER se fecha con información ex post** y la recesión de 2001 se recuerda como "la de los beneficios".

**Mitigación (todo fijado antes de cruzar nada):** (M1) una variable principal, una secundaria con Holm-2, un objetivo,
un horizonte, una transformación; sin búsqueda de ventanas ni retrasos; (M2) potencia con el efecto a la mitad (§7) y
veredicto escrito antes; (M3) solo métricas fuera de muestra con walk-forward y embargo de 12 meses; (M4) placebos (§9);
(M5) D por episodio y por mitades (1962-79 / 1980-2003) para que no decida un solo episodio; (M6) procedencia y puerta.

## 3. Datos (todo "as of" en el último día del mes M; NADA ≥ 2005)
| uso | serie (FRED/ALFRED) | desde | "as of" en el fin de M |
|---|---|---|---|
| beneficios (principal y S1) | `CPATAX` — Corporate Profits After Tax with IVA and CCAdj, trimestral, mm$ SAAR | 1947T1 | **ALFRED** (vintage vigente en el fin de M) para orígenes ≥ 1981-01 (primera añada 1980-12-23); antes, última añada con el trimestre usable al **fin del 4.º mes tras el fin del trimestre** (regla abajo) |
| deflactor (principal) | `GDPDEF` | 1947T1 | última añada, mismo calendario que el trimestre de beneficios (sale antes: avance del PIB) |
| PIB nominal (S1) | `GDP` | 1947T1 | ALFRED desde 1991-12 si se quiere; **última añada** (se publica antes que los beneficios) |
| listón E1 | `oecd_irlt_usa`, `bis_cbpol_us`, `oecd_ip_usa`, `oecd_bci_usa` (las de `src/intl/e1.rasgos`) | 1955-08 (las 4) | retrasos de `src/intl/lags.py` sobre la última añada (como E1) |
| objetivo | `USREC` (NBER, mensual) | 1854 | ex post (objetivo, nunca rasgo; familia ya permitida "solo como contraste externo... nunca como variable") |

- **Variable principal (`prof_yoy`):** `log(CPATAX_q / GDPDEF_q) − log(CPATAX_{q−4} / GDPDEF_{q−4})`, con q = último
  trimestre publicado en el fin de M y los dos trimestres de la **misma añada**. Signo esperado: **−** (menos beneficios
  → más riesgo). **Por qué esta y no la caída del margen (decidido antes de ver nada):** (a) es la que fija la
  recomendación del informe 10-K; (b) no tiene ningún parámetro libre (la caída desde el máximo exige elegir la ventana,
  4 u 8 trimestres, y elegir después sería minería); (c) es la misma transformación que la IP en E1 (interanual), sin
  deriva secular (el margen sobre PIB tiene tendencia y niveles distintos por década, la lección de INT-12 C2 con el
  nivel del crédito); (d) real y no nominal porque la inflación de los 70 inflaría el crecimiento nominal.
- **Secundaria (`margen_caida8`, S1):** `m_q − max(m_{q−7..q})` con `m_q = log(CPATAX_q / GDP_q)` (≤ 0). Signo esperado
  **−** (caída mayor → más riesgo; el coeficiente sobre un valor ≤ 0 sale negativo). 8 trimestres fijados aquí.
- **Regla del retraso antes de 1981 (fijada antes de mirar el retraso real):** el trimestre q se usa desde el fin del
  4.º mes tras su fin (T1 → fin de julio; T4 → fin de abril). Es conservadora a propósito: en la ALFRED 1981-2004 el
  primer dato sale a los ≈ 48-93 días (T4 el más lento, ≈ 3 meses; máximo de la muestra 111 días, un T3 retrasado) y
  antes de 1981 no hay añadas. La descripción del retraso real está en el JSON (`datos.retraso_alfred`), sin cruzar nada.
- **Revisiones:** antes de 1981 se usa la última añada (no hay otra). Las revisiones de los beneficios son grandes
  (IVA/CCAdj, revisiones de referencia); el JSON describe cuánto se revisa el interanual (primera publicación frente a la
  última añada, 1981-2004) para calibrar el ruido de la simulación. Sesgo a favor de los beneficios antes de 1981,
  declarado; la sensibilidad "solo última añada en toda la muestra" se publicaría sin veredicto.

## 4. Objetivo
- **Entrada NBER:** primer mes con `USREC` = 1 tras un mes con 0 (el mes siguiente al pico). **y(M) = 1** si hay una
  entrada en (M, M + 12]. **En riesgo:** `USREC(M)` = 0 (ex post, como el "en riesgo" de E1).
- **Muestra:** orígenes desde 1955-08 (las 4 variables de E1 para EE. UU.) hasta 2003-12 (el objetivo acaba ≤ 2004-12).
- **Recuento (solo la etiqueta, nada cruzado):** en el JSON (`eventos`). Entradas NBER 1955-2004: 1957-09, 1960-05,
  1970-01, 1973-12, 1980-02, 1981-08, 1990-08, 2001-04 (8); en la evaluación (desde el primer enero con ≥ 2 entradas en
  las filas de ajuste con embargo): 6.

## 5. Modelos (fijados aquí)
- **Índice E1 (`s_E1`):** predictor lineal del modelo A congelado de E1 (`research/int/e1_modelos.json`, coeficientes,
  medias y dt tal cual, sha256 comprobado), calculado para EE. UU. con `src/intl/e1.rasgos`.
- **P0 (persistencia/climatología):** la tasa de positivos de las filas de ajuste disponibles en cada enero. (Para una
  entrada en recesión no hay persistencia de la etiqueta: en las filas en riesgo el estado es siempre "sin recesión";
  la tasa base es el listón ingenuo.)
- **L (listón):** logit(y ~ `s_E1`). **A (candidato):** logit(y ~ `s_E1` + `prof_yoy`). **A2 (S1):** logit(y ~ `s_E1` +
  `margen_caida8`). Anidados; `src/intl/int4.logit_fit` sin penalizar, rasgos estandarizados con las filas de ajuste.
- **Walk-forward:** re-estimación cada enero con ventana creciente desde 1955-08 y **embargo de 12 meses** (solo filas
  cuyo objetivo ya se cerró: M + 12 ≤ origen); predicción de los 12 orígenes de ese año. Primer año de evaluación = el
  primer enero con ≥ 2 entradas NBER en las filas de ajuste (1962). Mismas filas y calendario para P0, L, A y A2.

## 6. Métricas y contraste
- **Principal:** D = media(ℓ_L − ℓ_A) sobre las predicciones apiladas de la evaluación (ℓ = −log verosimilitud, nats
  por fila). **p:** placebo de desplazamiento circular de `prof_yoy` (§9 P1), unilateral; α = 0,05, Holm-2 con S1.
- **Intervalo:** bootstrap por bloques móviles de 24 meses sobre las filas de evaluación (2.000 réplicas), IC 90 %
  unilateral publicado; con ≈ 6 entradas no es fiable como inferencia (la potencia mide su tamaño real, §7), por eso el p
  sale del placebo.
- **Secundarios (sin veredicto):** ΔBrier (A − L); D y ΔBrier frente a P0 de L y de A; ΔAUC de índice (como INT-15);
  D por episodio y por mitades; signo de β̂(`prof_yoy`) en los ajustes anuales; calibración de A.

## 7. Potencia (antes que nada)
*Pendiente: se rellena con la salida de `scripts/int17_potencia.py` (commit con árbol limpio). Método fijado antes:*
estructura de eventos **real** (filas en riesgo y entradas NBER 1955-08 … 2003-12) y rasgos **simulados**: `x1` = índice
E1 (a·y + u, AUC poblacional del listón 0,80 central, rejilla 0,70-0,90; la curva sola para el NBER a 6-12 meses da
≈ 0,80-0,90 dentro de muestra según INT-8 §2), `x2` = beneficios (b_e·y + λ·x1 + w: λ da la colinealidad con E1 sin
añadir información, b_e = b + τ·N(0,1) por entrada = heterogeneidad entre episodios), u AR(1) mensual φ 0,95 (como E1),
w trimestral AR(1) con la persistencia **medida en la propia serie** (sin la etiqueta) y mantenida 3 meses, más el ruido
de revisión medido. Walk-forward idéntico a §5. Contraste con el valor crítico de la nula simulada (b = 0, ≈ placebo P1)
y, aparte, el bootstrap por bloques (tamaño real y potencia). Efecto plantado en ΔAUC poblacional del oráculo:
**realista +0,04** (la mitad del optimista, maldición del ganador, como INT-15), **optimista +0,08**; se da también en
nats. **Umbral del proyecto: potencia ≥ 0,80** (MDE al 80 % en todos los documentos de potencia). Si con el efecto
realista no llega, **se cierra sin correr** (como INT-8, INT-15, INT-16).

## 8. Criterios (O1, fijados antes)
- **Establecido (todos):** (i) p del placebo P1 < α de Holm-2; (ii) D > 0 y ΔBrier < 0; (iii) β̂(`prof_yoy`) < 0 en
  ≥ 2/3 de los ajustes anuales; (iv) D > 0 en 1962-79 y en 1980-2003 por separado; (v) A mejora a P0 en log-loss.
- **Refutado** ("los beneficios no añaden a E1"): D ≤ 0.
- **Ni lo uno ni lo otro:** "no contradicho; sin potencia para establecerlo". No se repite con otra especificación.
- **Consecuencia decidida de antemano:** aunque saliera establecido, no entra en la cartera ni en el reporte como
  probabilidad; abriría un registro en vivo junto a E1 (nunca el bloqueado).
- **Cierre:** si la potencia con el efecto realista es < 0,80 (§7), se recomienda **no correr** el contraste real.

## 9. Placebos y controles
- **P1 desplazamiento circular (da el p):** `prof_yoy` desplazado k meses en círculo (k ∈ [24, T − 24]), walk-forward
  completo; p = (1 + #{D_k ≥ D_obs}) / (1 + nº de k).
- **P2 beneficios retrasados 24 meses:** no debería ayudar (descriptivo).
- **P3 signo:** si β̂ > 0 en la mayoría de los años, se publica y no se cambia nada.
- **P4 señal plantada (sintético, hecho en la potencia):** la tubería recupera una señal conocida y, sin señal, no la
  inventa (tests `tests/test_intl_int17_potencia.py`).
- **P5 corte PIT:** nada ≥ 2005 (`load_dev`); el trimestre usado en el origen M respeta la añada o la regla del §3.

## 10. Procedencia y puerta
`scripts/int17_corrida.py` (NO escrito; solo si el usuario decide correr): `procedencia(exigir_limpio=True)`, sha256 de
este documento congelado (v1.0) y de `e1_modelos.json`, se niega si la salida existe, solo ≤ 2004; una corrida;
entrada en `research/trial_log.md`; Validador independiente.

## 11. Decisiones pendientes del usuario
*Se completan con la potencia (§7).*
