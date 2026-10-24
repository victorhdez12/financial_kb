---
documento: revisión del Validador independiente (estilo SR 11-7) de las specs a priori del pool y del borrador P-EVAL-BASE v4
fecha: 2026-10-24
objeto: commit 1a5f1f9 (m2_structural_spec.md, m3_tvtp_spec.md, pool_spec.md, p_eval_base_v4_draft.md, H-M2-001/H-M3-001/H-POOL-001, src/models/regime_components.py, tests/test_regime_components.py) y commit 34554c6 (power_holdout.md, src/models/power.py)
contexto: Bitácora 24-oct, harness.md v2.3, revisión anterior docs/validation/2026-10-23_pit_v0.4_m1v2.md (M4-1/M4-2/M4-3)
contacto_con_datos: NINGUNO. No he cargado la etiqueta (ni ≤ 2004), ni la base PIT, ni los scores de desarrollo. Solo he leído registros de accesos y de corridas, la actividad de GitHub, el código, research/trials/power_holdout.json y datos SINTÉTICOS. No he corrido modelos ni registrado nada.
script: tests/validation/specs_pool_v4_validation.py (sintético; ≈ 10 s)
---

# Specs a priori del pool {M0, M2, M3} y P-EVAL-BASE v4: revisión del Validador

## Veredictos

| objeto | veredicto | hallazgos |
|---|---|---|
| Prioridad a priori (push frente a lecturas de la etiqueta y corridas) | ✅ | B-1 |
| M2 estructural (`m2_structural_spec.md`, H-M2-001) | ⚠️ | M-2, M-4, B-2, B-3 |
| M3 TVTP (`m3_tvtp_spec.md`, H-M3-001) | ⚠️ | M-1, M-4, B-4, B-5 |
| Pool (`pool_spec.md`, H-POOL-001) | ✅ | B-6 |
| P-EVAL-BASE v4 (borrador) | ⚠️ | M-1, M-3, B-7, B-8 |
| Hipótesis en `research/hypotheses.yaml` | ⚠️ | M-1 (H-POOL-001 no recoge el criterio de signos) |
| Esqueleto y tests (`regime_components.py`, 6 tests) | ✅ | — |
| Potencia (`power.py`, `power_holdout.md`) | ⚠️ | M-3, B-9 |

No hay hallazgos ALTOS. Los MEDIOS (M-1 a M-4) se pueden arreglar en los documentos, sin tocar datos. **M-1 y M-4 hay
que cerrarlos antes de la primera corrida de desarrollo** (si no, dejan de ser a priori). M-2 y M-3 se pueden cerrar
antes de registrar.

Decisiones del usuario que he comprobado:

| decisión | ¿la recogen las specs? |
|---|---|
| pool {M0, M2, M3} + BLP, Holm k = 1 | sí |
| criterio 1 con IC 95 % y ≥ 0,05 nats | sí |
| eje I = M0 | sí |
| `baa_gap10y` fuera | sí |
| base PIT v0.4 congelada | sí |
| niveles vía `levels_at`, sin base v0.5 | sí |
| `incluye: []` | sí |
| bloqueado 2005-01 reservado | sí |
| **criterio de signos: alternativa "γ > 0 en ≥ 50 % de los cortes"** | **no** (M-1): la v4 lo sigue retirando y deja la alternativa como condicional |

## 1. Prioridad a priori ✅

**Evidencia**
- **Commit y push.** `1a5f1f9` se commiteó a las 09:53:13Z. Según la API de actividad de GitHub, el push llegó a
  `main` a las **09:53:14Z** (el Constructor dice 09:53:15Z; la diferencia de 1 s no importa).
- **Las specs no han cambiado desde el push.** `d5a1337` y `4ef7d54` solo tocan Obsidian, y el árbol de trabajo está
  limpio.
- **No hay corridas de M2, M3 ni del pool.**
  - `research/trials/harness_runs.jsonl` termina el 23-oct a las 11:21 (hora local).
  - El 24-oct, `research/trials/full/harness_runs_unrecorded.jsonl` solo contiene tests de pytest y las 3
    reproducciones de M1 v1 con `record=False` (09:11-09:20Z, documentadas en la Bitácora).
  - Entre los modelos que aparecen no hay ningún `m2_*`, `m3_*` ni `pool_*`.
  - Los esqueletos lanzan `NotImplementedError` y no están en `harness.model_registry()` (lo comprueba un test).
- **Lecturas de la etiqueta del 24-oct** (`research/trials/full/label_access.jsonl`, 325 entradas, todas antes de
  las 09:51:07Z):
  - tres pasadas de la suite: 08:47-08:52Z, 08:57-09:02Z y 09:47-09:51Z;
  - `power.py` a las 09:05:52Z (también en el registro principal);
  - las reproducciones de M1 v1 de 09:10-09:20Z.
  - Todas son de `development` y llegan como mucho a 2004-12. Las denegadas (`granted: false`) son tests de la
    barrera (`test_vault_development_never_decodes_holdout`, `test_M1_pitlabeler_blocks_holdout`,
    `test_N4_levels_at_blocks_holdout`).
  - No hay ninguna lectura después del push.

**¿Contamina algo la suite de 09:47-09:52Z?** No.
- Los tests antiguos del arnés solo producen M0, baselines, placebos y ensayos en seco con la etiqueta ≤ 2004, cuyo
  contenido ya se conocía desde el 16-oct.
- No pueden informar sobre M2, M3 ni el pool, que no existían.
- Ningún parámetro de las specs se puede rastrear hasta esa salida.

Lo que sí ha influido en el diseño es lo ya declarado en el §0 de cada spec: los resultados de M1 v1/v2 en desarrollo
y el cálculo de potencia, que usó la etiqueta ≤ 2004 para marcar los giros (B-1).

## 2. Hallazgos

### M-1 (MEDIA, bloquea el registro) · La v4 no recoge la decisión del usuario sobre el criterio de signos, y la regla no es operativa

- **Evidencia (documentos):**
  - El cambio A1-3 de `p_eval_base_v4_draft.md` dice "**sin** criterio de signos" y deja la alternativa como
    condicional en A9-4 ("si no lo aprueba…").
  - A3 no tiene el criterio, y `criterio_de_referencia` de H-POOL-001 tampoco.
  - El usuario ya decidió (Bitácora, 24-oct): la alternativa "γ > 0 en ≥ 50 % de los cortes" **no se retira**.
- **Evidencia (arnés):** con `expected_signs` (A8), el arnés calcula `criterio_signos_cumple` = signo de la media
  igual al esperado **y** estable en los saltos de vintage (`harness.coefficient_signs`).
  - Con γ ≥ 0 impuesto, eso se cumple siempre que algún corte tenga γ > 0. Es justo el criterio que no puede fallar
    (el motivo de A1-3).
  - Si se registra la configuración tal como está escrita, el criterio de signos quedaría **vacío sin que nadie lo
    note**.
- **Evidencia (`frac_signo_esperado`):** usa `np.sign(x) == 1`, así que γ = 0 exacto no cuenta y γ = 1e-12 sí.
  - L-BFGS-B con cotas suele devolver 0 exacto, pero un residuo de 1e-10 contaría como positivo (script, prueba 3:
    0,6 frente a 0,2 con tolerancia).
- **Dónde está la ambigüedad:**
  - "En la ventana": ¿cuál?
  - "Para cada γ": ¿los 4 por separado?
  - La frase "el criterio 6 de la v3 vuelve" choca con la numeración de la v4 (allí el 6 es "subperiodos").
  - Tampoco queda claro si vuelve también la cláusula de estabilidad en los saltos de vintage de la v3.

**Para aprobar.** Antes de la corrida de desarrollo del pool:
1. Añadir un **criterio 8** a A3: "para cada j = 1…4, la fracción de cortes de `m3_tvtp_g` (vintage, cortes cuyo mes
   está en 2005-01 → 2021-10) con γ<sub>j</sub> > **1e-6** es ≥ 0,50". Fijar la tolerancia y decir explícitamente que
   **no** hay cláusula de estabilidad por vintage.
2. Darle una clave de informe nueva. Por ejemplo, `report["signos_coeficientes"]["vintage/m3_tvtp_g"].frac_min_cumple`
   (extensión del arnés v2.4, con test).
3. Quitar A1-3 y A9-4 y sustituirlos por "decisión del usuario 24-oct".
4. Actualizar `criterio_de_referencia` de H-POOL-001 y el §5 de M3, que hoy solo lo informa.
5. Anotar en el trial log que el criterio se aplica a un componente: el pool puede fallar por M3 aunque mejore.

### M-2 (MEDIA) · V<sub>rev</sub>(edad) mide la revisión frente a la última vintage (posterior a 2004): no es PIT

- **Evidencia:** §4 de M2: "error = r en la vintage de la fecha − r en la **última vintage** (la que usa la
  etiqueta)", con fechas y meses ≤ 2004-12. La tabla se congela una vez, antes del desarrollo, y se usa en todos los
  cortes (desde 1978) y en el bloqueado.
  - La referencia incluye revisiones publicadas entre 2005 y 2026 (*benchmarks*, cambios de base) de meses ≤ 2004.
  - En un corte de 1985, por tanto, σ̂ usa información de revisiones que no se conocían en 1985.
  - Esto contradice el "todo ≤ corte" del §3 y el "revisión estimada solo con vintages ≤ 2004" del encargo.
  - No lee nada de meses ≥ 2005 y es un solo hiperparámetro de escala. Es de la misma naturaleza que el s<sub>G</sub>
    = 0,40 de la etiqueta (primera publicación − última vintage, 1955-2024), y es coherente con el objetivo puntuado
    (la etiqueta oficial con la última vintage).
  - Pero **no está declarado** como no PIT.
- **Mismo hueco en otro sitio:** para W875RX1/CMRMTSPL, ρ̄·Var(r<sub>i</sub>) no fija en qué muestra se calcula
  Var(r<sub>i</sub>).

**Para aprobar**, elegir una de dos y escribirla en el §4 antes de calcular la tabla:
- **(a) declarar** V<sub>rev</sub> como hiperparámetro fijo no PIT, como s<sub>G</sub>, con el motivo. La sensibilidad
  `_norev` ya existe; o
- **(b) hacerlo PIT:** referencia = vintage de 2004-12 (o la vintage del corte T, reestimada cada enero).

En los dos casos, fijar la muestra de Var(r<sub>i</sub>). Mi recomendación es (a), por coherencia con el objetivo y con
s<sub>G</sub>.

### M-3 (MEDIA) · El tamaño "5-9 %" es una cota inferior; falta la sensibilidad de bloques de 24 en la configuración

**El método de `power.py` es correcto en lo esencial.**
- **El nulo:** centrar por separado giros y estables conserva la dependencia, las colas y la relación con los giros.
  Es sensato.
- **El contraste coincide con el del arnés:** `harness_test` reproduce `metrics.boot_mean` (salvo redondeo de 1e-17;
  script, prueba 1).
- **Las cifras del documento cuadran con `power_holdout.json`:**
  - MDE 0,128 / 0,147 / 0,097 / 0,125 / 0,120;
  - tamaño con δ = 0 de 0,051-0,092;
  - con ruido ×0,5, 0-0,01.

**Pero tiene un límite que no se comunica.** La serie ficticia se genera con bloques **alineados** de 12 meses de la
serie de desarrollo. Así, la dependencia de d más allá de 12 meses no existe por construcción, y el contraste interno
(también con bloques de 12) solo puede fallar por esa parte. Simulación sintética (script, prueba 2; 800
evaluaciones de 202 meses, t<sub>4</sub>, AR(1)):

| φ | tamaño real "lo > 0" (serie AR) | tamaño con el generador de `power.py` |
|---|---|---|
| 0 | 4,0 % | 3,9 % |
| 0,6 | 5,4 % | 5,6 % |
| 0,85 | 9,3 % | 6,3 % |
| 0,95 | 19,8 % | 7,6 % |

**Cómo leerlo:**
- Con la dependencia que se ve en desarrollo (SE·√202/desv. ≈ 2,3, equivalente a un AR(1) con φ ≈ 0,7), el 5-9 % es
  razonable. Si d<sub>t</sub> tiene memoria larga (regímenes de años), el tamaño real es mayor: el 5-9 % es una **cota
  inferior**.
- Además, `p_h0 < 0,05` por sí solo pasa con efecto 0 el **10-15 %** de las veces (`p_solo_contraste_holm_k1` en el
  JSON). Los p de las familias **informativas** (secundarias, TVTP frente a CTP) son liberales del orden de ×2-3.
- Con k = 1, el criterio 7 (Holm, p < 0,05) es **redundante** con el criterio 1 (límite inferior del IC 95 % > 0 ≈
  p < 0,025). Es coherente, pero no añade protección.

**¿Implica una corrección del tamaño en el contraste?** No hace falta cambiar los criterios. El umbral de 0,05 nats y
la conjunción de los criterios 1-8 bajan la tasa real de falso pase por debajo del 5 %. Con el ruido reducido del
pool, el tamaño es del 0-1 % (manda el umbral). La decisión del usuario (IC 95 %) queda **reforzada**.

**Para aprobar:**
1. En `power_holdout.md` §2 y en A7 de la v4, escribir "≥ 5-9 % si la dependencia de d no pasa de ≈ 12 meses" y añadir
   la nota de que los p informativos son liberales.
2. En la corrida de desarrollo del pool, informar la autocorrelación de d<sub>t</sub> en los retardos 1-24, junto a
   `sd_mensual`.
3. A6 de la v4 promete bloques de 24 como sensibilidad, pero la configuración de A8 no la incluye: añadirla (las
   claves `mejora_logloss` con `BOOT24`) para que se publique siempre.
4. Opcional y barato: repetir `power.py` con bloques exteriores de 24/36 como robustez (sin cambiar nada más).

### M-4 (MEDIA) · S-PIT-001: criterio ambiguo y bifurcación que arrastra a M3 y al pool

- **Evidencia:** M2 §2 aplica S-PIT-001 "tal como está preregistrada", y si se dispara, Filadelfia antes de 1990-07
  pasa a NaN en el factor.
  - El criterio de `hypotheses.yaml` es "si la diferencia de log-loss ≤ 2004 supera el intervalo bootstrap de la
    principal". No dice de qué modelo, de qué contraste ni de qué intervalo (¿el IC de M2 − M0? ¿la semiamplitud?
    ¿el valor absoluto?).
  - El factor es **compartido**: si se dispara, cambian M2, la emisión de M3 y el pool.
  - En el orden de M2 §6, `s_pit_001` va **después** de `m2_long`. El pool §7 y M3 no dicen que haya que esperar al
    resultado.
  - Se podría acabar con corridas de desarrollo de M3/pool hechas con un M2 que no es el que va al bloqueado, o
    eligiendo después qué corrida vale.

**Para aprobar.** Antes de la corrida:
1. Escribir la regla operativa. Por ejemplo: "se dispara si |media de ll(M2, prudente) − ll(M2, principal)| > la
   semiamplitud del IC 95 % de `mejora_logloss` de M2 frente a M0 en `m2_long`, vintage".
2. Fijar el orden: `s_pit_001` se resuelve **antes** de las corridas de M3 y del pool.
3. Si se dispara, la versión con NaN es la única que se corre para M2, M3 y el pool.

### Bajas

- **B-1 · La nota de proceso está incompleta** (§9/§8 de las specs).
  - Cita solo la suite de 09:47-09:52Z. Faltan: las pasadas de 08:47Z y 08:57Z, la lectura de `power.py` (09:05Z;
    sus d<sub>t</sub> de M1 y sus MDE sí informan el diseño: `sd_mensual`, puerta de gasto) y las reproducciones de
    M1 v1 (09:10-09:20Z).
  - "Antes de cualquier contacto con la etiqueta" debería decir "antes de cualquier contacto **para M2/M3/pool**".
  - Ninguna contamina.
- **B-2 · Grados de libertad sin fijar en M2.**
  - Se permiten dos implementaciones de la máxima verosimilitud ("statsmodels o propia"): con óptimos locales pueden
    dar parámetros distintos. Fijar una.
  - No está definido el "panel balanceado más largo" del arranque.
  - Falta una regla si L-BFGS-B no converge (propuesta: conservar los parámetros anteriores y anotarlo).
  - El arranque desde el óptimo anterior hace que los parámetros dependan del primer corte. Comprobar que el ensayo
    en seco (`dry_run_window` 1993-01) corre los componentes desde W<sub>G</sub> o da los mismos parámetros.
- **B-3 · Placebo de M2.** M2 no lee la etiqueta, así que su placebo solo prueba el arnés. La prueba de fuga que
  importa para M2 es la de truncamiento (§6), que ya está. Sin cambios; solo para la lectura.
- **B-4 · Coherencia entre M3 y M2.**
  - Para s = m, la emisión de M3 es exactamente el Ĝ de M2 (mismos datos y parámetros).
  - Para s < m (meses filtrados y de entrenamiento), usa los parámetros vigentes en el corte m, no los del corte s. Es
    PIT y está bien, pero no coincide con la predicción fuera de muestra de M2 en s. Decirlo así en M3 §2.
- **B-5 · Calibración de M3 dentro de muestra.**
  - La capa Platt de M3 se ajusta con p<sub>filtro</sub> de los meses de entrenamiento, con parámetros estimados en
    esos mismos meses. Es un poco optimista (M0 hace lo mismo con 2 parámetros, M3 con 9). Declararlo.
  - Fijar `maxiter`/`gtol` de las logísticas y de la calibración.
- **B-6 · "Exactamente" en d<sub>t</sub>.**
  - La igualdad de las diferencias de log-loss de 4 cuadrantes y del eje G se cumple con el eje I común (error 6e-15
    con objetivos blandos no producto; prueba 4).
  - Se **rompe** cuando actúa `metrics.CLIP` = 1e-4 por cuadrante. Con P<sub>pool</sub> = 1e-5 la diferencia llega a
    1,28 nats en un mes.
  - El recorte del pool (1e-6) es más fino que el de M0 (1e-3) y que el del arnés. Declarar que es "exacta salvo
    recorte"; opcionalmente, recortar el pool a 1e-4.
- **B-7 · Cambio no declarado en A1 de la v4:** `test_start` pasa de 1978-07 (v3) a 1956-10. A4 lo justifica, pero
  debe estar en la tabla de cambios (M4-2).
- **B-8 · Estado de M4-1/M4-2/M4-3.**
  - **M4-1:** se puede ejecutar por diseño (configuración fijada en A8 y ensayo en seco como condición A9-5), pero no
    está demostrado. Queda abierto hasta A9-5, y es lo correcto.
  - **M4-2:** **corregido** ("eje G > 0" recuperado como criterio 2; promoción "< 0" de la v2; cada cambio declarado),
    salvo B-7.
  - **M4-3:** **corregido**, salvo la alternativa de signos condicional (M-1).
- **B-9 · `power_holdout.md` está desfasado.**
  - Sigue "decisión del usuario pendiente: IC 95/90" (§4), cuando ya está decidido.
  - Numera los criterios como la v3: su "criterio 2 (giros ≥ 0)" es el 3 de la v4.

## 3. Lo que he comprobado y está bien

- **PIT (por diseño):**
  - **M2:** usa el *ragged edge* real vía `levels_at` (misma barrera ≥ 2005). τʳ es una mediana de los 120 meses
    anteriores. Las estandarizaciones y los parámetros salen del tramo del corte y se reestiman cada enero. V<sub>tend</sub>
    se calcula con niveles ≤ T y sin etiqueta (s ≤ T − 65 deja la tendencia completa).
  - **M3:** estados = etiqueta recalculada ≤ T con embargo 6. El ancla es el `label_month` de la persistencia PIT. El
    filtro solo usa z y Ĝ<sup>rt</sup> ≤ m.
  - **Pool:** usa solo predicciones fuera de muestra de cada corte s, con s ≤ m0 − 6. El objetivo se recalcula ≤ m0
    con pesos de madurez, y el placebo baraja toda la pila.
- **Signos de las transiciones:** son coherentes con el mecanismo (−γ1·curva, +γ2·Δcrédito para la salida de G alto;
  −γ3·Δcrédito, +γ4·bolsa para la salida de G bajo) y con `TVTPSpec`.
- **Composición de M2:**
  - La linealización c = (1/n)(2/3)w/σ coincide con `R.pace` (test del Constructor, tolerancia 1 %).
  - P = Φ(Ĝ/√(σ̂² + s<sub>G</sub>²)) es exactamente E[Φ(G/s<sub>G</sub>)] si G ~ N(Ĝ, σ̂²), es decir, el objetivo
    blando esperado.
- **Grados de libertad:** pool, M3 y M2 fijan ventanas por regla, previas, κ, N<sub>min</sub>, templado, optimizador
  del pool, semillas del bootstrap y del placebo, y umbrales de fuga y aviso. Las sensibilidades están marcadas como no
  principales y "no eligen". La única dependencia de resultados es la "puerta de gasto", que es explícitamente una
  lectura y no un criterio (decide el usuario).
- **Contraste único:** familia `principal_k1` con un miembro. No hay desempate ni preguntas abiertas, salvo M-1.

## 4. Para aprobar

1. **Antes de la primera corrida de desarrollo:** M-1 (criterio 8 de signos con tolerancia, ventana y clave) y M-4
   (regla de S-PIT-001 y su orden). Si no, dejan de ser a priori.
2. **Antes de registrar P-EVAL-BASE:** M-2 (declarar o hacer PIT V<sub>rev</sub>), M-3 (comunicar el tamaño como cota
   inferior y añadir los bloques de 24 a A8) y las bajas B-1, B-2, B-5, B-6, B-7 y B-9.
3. Nueva revisión del Validador del texto v4 corregido y de la implementación (arnés v2.4, tests sintéticos, tabla
   v(edad), sonda de elegibilidad, placebos) antes de la corrida.

**Para el usuario:**
- (a) Confirmar la forma operativa del criterio de signos (M-1: tolerancia 1e-6, ventana del bloqueado, cada γ por
  separado, sin cláusula de vintage).
- (b) V<sub>rev</sub>: declararlo como no PIT (recomendado) o hacerlo PIT (M-2).
- (c) Nada que cambiar en el IC 95 %: el análisis del tamaño refuerza la decisión.
