---
tipo: estado_proyecto
actualizado: 2026-10-26
fase_real: Fase 3 (modelos); fase de datos cerrada el 14-oct
---

# Estado del proyecto

## Estado honesto (26-oct-2026)
1. **El nowcast no mejora a la persistencia:** en EE. UU. (Fase 3) ningún modelo bate a M0, y el fechado mensual de recesiones no pasó su puerta.
2. **El forecast de recesiones a un año sí funciona, moderado** (INT-4): la entrada es sólida (AUC ≈ 0,73, curva + difusión + bolsa) y la salida es más justa (≈ +0,19 de AUC, sobre todo por la bolsa).
3. **La inflación no se anticipa** (T3/T4 no establecidos).
4. **Lo útil ahora:** el atlas ([[Proyecto/Atlas regímenes]], `docs/int/ATLAS_regimenes.md`: qué activos y cuándo) y el termómetro de recesión como herramienta informativa.


> [!info] Para retomar en una sesión nueva
> Lee esta nota, después [[Proyecto/Agentes]] (roles e instrucciones completas) y [[Proyecto/Bitácora]] (qué se hizo y cuándo).
> Código: `~/Proyectos/financial_kb` (movido del Escritorio el 13-oct) · Datos: `~/financial_archive` (enlace `data/archive`) · Plan original: `docs/PLAN.md`.

## 🎯 Objetivo de la Fase 3 (acordado el 14-oct)

**Tener un nowcast del régimen de EE. UU. validado:** que el sistema diga cada mes en qué cuadrante estamos y con qué probabilidad, usando solo la información disponible en esa fecha, y que esté demostrado en un backtest honesto que lo hace mejor que las alternativas sencillas.

**Entregables, por orden:** (1) ✅ etiqueta **v1.1** congelada y validada ✅ (15-oct, tag `label-v1.1`; [[Proyecto/Etiqueta de régimen]]) · (2) ✅ base point-in-time **v0.3 congelada** (16-oct, tag `pit-v0.3`, validador ✅) · (3) ▶ arnés walk-forward (embargo 6 m, periodo 2016-2026 bloqueado, registro de pruebas) · (4) baselines: persistencia, reglas, logística, Markov · (5) GBM solo si los bate · (6) calibración. En paralelo: investigación de relaciones adelantadas (las validadas entran como variables).

**Criterios de cierre:**
- [ ] Bate a la persistencia en log-loss fuera de muestra, también en el periodo bloqueado, con intervalos que no incluyen el cero.
- [ ] Probabilidades calibradas.
- [ ] Sin fugas: test point-in-time, placebo y señal plantada superados.
- [ ] Las relaciones que usa tienen mecanismo, son estables por épocas/países y sobreviven a la corrección por comparaciones múltiples.
- [ ] **Veredicto ✅ del Validador independiente.**
- [ ] Ficha del modelo + informe de resultados del Reportero.
- [ ] Sustituye al clasificador de reglas en el reporte semanal.

**Fuera de esta fase:** factores y cartera (siguiente fase), zona euro, forecast a 6 m, informe para empresas.

**Agentes de la fase:** Constructor · Investigador de relaciones · **Validador independiente** · **Reportero** (ver [[Proyecto/Agentes]]). Informe: [[Reports/Fase 3/Informe de resultados]].

## ▶ Retomar aquí (26-oct, RECONDUCCIÓN: líneas A y B)

> [!important] Reconducción del proyecto (decisión del usuario, 26-oct). Detalle en `docs/PLAN.md` § "Reconducción".

**Diagnóstico:**
- El proyecto empezó para usar el régimen macro (nowcast de crecimiento e inflación) para mover la cartera.
- La Fase 3 concluyó "M0 sigue": el pool no mejora a la persistencia de forma demostrable.
- En la fase de factores, con unas 6 recesiones entre 1963 y 2004, no hay potencia para demostrar diferencias de rentabilidad por régimen, y el clasificador coincide poco con la etiqueta en crecimiento (68,9 %, kappa 0,394).
- Las reglas de régimen no superaron al ajuste por volatilidad, así que la cartera operativa (B0/B1) hoy NO usa el nowcast.

**Alcance:** todo lo hecho es **nowcast** (régimen del mes t, etiqueta conocida con ~5 meses de retraso; confirmado en el arnés: objetivo = etiqueta de t, M0 = etiqueta de t − 5). El **forecast** (3, 6, 12 meses) **no se ha hecho**; entra solo como forecast de **riesgo** en la línea B. No hay forecast del cuadrante.

**Línea A — cartera operativa:** B0 = estática **70/15/15** y B1 = su ajuste por volatilidad, paper trading desde el cierre de octubre. 70/15/15 decidido **después** de ver el −42 % de la 80/10/10 (declarado). Pendiente antes de la primera decisión: σ\* en la medida en vivo (calculado: 17,02 % con 1963-2004; sin congelar), declaración S&P 500 / French Developed, nota de potencia de 36 meses, launchd con aviso, y pasar código/spec/tests/ensayo a 70/15/15. El nowcast no interviene.

**▶ Retomar (29-oct, 4):** termómetro en el reporte semanal (5b). Hecho hoy: atlas visual (nota [[Proyecto/Atlas visual]]), potencia de P-EVAL-INT4 (bloqueado SIN gastar; potencia ≈ 0,4-0,5 → recomendado no gastarlo, prerregistrar criterio de refutación). En marcha (agentes): sustituto BoE tipo 3 m GBR (rama `gbr-3m`, worktree `financial_kb_int3`) e inventario + borrador INT-6 oro/M2/países/crédito (rama `inventario-int6`, worktree `financial_kb_int3b`). Pendiente del usuario: decisión sobre el bloqueado y preguntas de INT-6. Domingo 1-nov: revisar primer reporte con termómetro; ≈ 3-nov: aprobar ensayo del paper trading.

**Anterior (26-oct, noche):** INT-0, INT-1, INT-2 e INT-3 hechos (INT-3: establecidos bolsa −8,7 pp en estanflación, bonos −10,1 pp con inflación alta, bolsa −5,5 pp en recesión, vivienda +6,2 pp frente a bolsa con inflación alta). Diseño de INT-4 hecho. Pendiente: "ok" del usuario al plan ampliado (INT-3b materias primas/oro/crédito, INT-3c por qué, INT-3d giros, INT-4 entradas y salidas) y validación de INT-3 en la nube. Detalle: Bitácora del 26-oct.

**Fase internacional (borrador 26-oct):** `docs/PLAN_internacional_v0.md`: régimen por país + mapa régimen → activos (jerárquico, 18 países JST 1870-2020 + OCDE mensual) + forecast de riesgo en panel; bloqueado ≥ 2005 para todos los países. Pendiente de aprobación.

**Línea B — el nowcast como herramienta:** informativo (el reporte lo dice). Investigación con una pregunta: ¿la macro adelanta el riesgo lo bastante para mejorar el momento de los recortes de B1? Diseño: `docs/lineaB/diseno_v0.md` (potencia: con ≤ 2004 no se demuestra nada realista salvo efectos grandes en subidas de volatilidad; recesiones a ≥ 3 meses sin potencia → paper trading, años).

### Retomar (26-oct, fase de factores: desarrollo hecho → opción 3) — histórico

P-DEV-FACT v0.1 corrida una vez (`20261026-102647_pdevfact_v01`): ninguna regla de régimen (V1-V3) mejora a la cartera con ajuste por volatilidad (B1); B1 recorta volatilidad (14,4 → 12,7 %) y caída (−42 → −33 %) frente a la estática. Por defecto: **IPS 80/10/10 + B1 + paper trading**. Pendiente del usuario: confirmarlo y decidir sobre la caída de −42 % de la estática (fuera de la tolerancia). Detalle: [[Proyecto/Fase factores — plan]] §12.

### Retomar (26-oct, fase de factores: plan en borrador) — histórico

**Plan:** [[Proyecto/Fase factores — plan]] (aprobado con ajustes). Hecho: corte técnico (`src/factors/data.py`), paso 0 (vintages del clasificador y contaminación de diseño) y potencia: solo efectos enormes en rentabilidad → objetivo = reducir caídas/volatilidad. **Pendiente del usuario:** elegir la cartera de referencia (A/B/C). Sin backtests de cartera todavía.

### Retomar (26-oct, Fase 3 cerrada para el pool: "M0 sigue") — histórico

**Decisión del usuario (26-oct):** P-EVAL-BASE v4.3 **no registrada**; periodo bloqueado **intacto**. Puerta de gasto: pool − M0 = +0,040 nats, IC 95 % [−0,008; +0,086]; potencia ≤ 0,53; pool_excluir +0,013 (depende de un componente). P1–P4 no evaluables (ventanas NBER ≠ giros de G de la etiqueta), sin arreglar. Detalle en la Bitácora del 26-oct y en `research/trial_log.md`.

**Regla:** no se sigue afinando este pool con datos ≤ 2004. Un enfoque nuevo (información nueva, o modelo centrado en las entradas en recesión) empieza con un **cálculo de potencia antes de construir nada** (mejora necesaria claramente > +0,05 nats).

**Siguiente:** decidir el enfoque nuevo (o pasar a la fase de factores/cartera con el clasificador de reglas + M0).

### Retomar (26-oct, cadena de desarrollo completa) — histórico

**Hecho:** cadena de desarrollo ≤ 2004 completa (M2, M3, placebo del pool ✅ sin fuga, pool_dev y sensibilidades), todo en `main` (`5cec04f`). Resultados **sin leer**.

**Siguiente:** revisión de `claude/puerta-gasto` (Validador, nube) → fusionar → correr la puerta de gasto → **PARAR: decide el usuario** (registrar P-EVAL-BASE v4.3 y gastar el bloqueado, o no). Si la puerta sale mal, no iterar en desarrollo.

### Retomar (25-oct, control ampliado M2 v1.3) — histórico

**Hecho:** control sintético ampliado de M2 v1.3 (protocolo `da18753`, 40 semillas 1001–1040): **principal cumple** (media 0,810, IC 95 % [0,794; 0,826] dentro de [0,75; 0,85]); secundario 70 % (justo en el umbral). Resultado en `docs/validation/2026-10-25_m2_v13_control_ampliado_resultado.md`. El control de 4 semillas (3/7/11/21) queda declarado no superado.

**Siguiente:** veredicto formal del Validador → corrida `m2_long` (6a, desarrollo ≤ 2004), autorizada por el usuario el 25-oct. Luego `s_pit_001` → M3 → pool. Periodo bloqueado sin tocar.

### Retomar (24-oct, noche) — histórico

**Estado 24-oct, noche (histórico):**

**Hecho:** spec **M2 v1.3** empujada a priori (`d8eb113`, 15:55:57Z): σ̂² = V<sub>conj</sub> (error conjunto medido sin
etiqueta) + V<sub>rev</sub>; implementada (`90f408f`). **Control de 4 semillas NO superado:** cobertura del 80 % 0,834 /
0,818 / 0,855 / 0,872 (3/7/11/21; dos fuera de [0,75; 0,85]); parada sin iterar. Elecciones de implementación (Q1) en
`docs/models/implementation_choices_v2.4.md`.

**Siguiente:** **Validador** revisa la v1.3 + Q1 → **usuario** decide sobre el control (aceptar la v1.3 o nuevo cambio a
priori) → `m2_long` → `s_pit_001` → S-PIT-001 resuelta y empujada → resto de M2 → M3 → pool → Validador + Estratega.
Nada con la etiqueta sin barajar hasta entonces.

### Retomar (24-oct, noche) — histórico

**Hecho (Constructor, 24-oct):** specs **v1.2** (N-1…N-7) empujadas a priori (`68e66dd`, **12:15:25Z**); **arnés v2.4** y
**M2, M3 y pool implementados** con tests sintéticos (`0bd606b`) + tabla v(edad) sin etiqueta (`8e34264`), empujados a
las 12:54:43Z, antes de la primera lectura de la etiqueta. Sonda: **W_G = 1978-10**, ventana del pool **1985-01 →
2004-12**. **Placebos sin fuga ni aviso** (M2 −0,37, M3 −0,016, pool −0,022). Configs `m2_long` y `s_pit_001`
escritas, **no ejecutadas**. P-EVAL-BASE sin registrar.

**⚠️ Para el usuario antes de `m2_long`:** (Q0, bloqueante) el control de **señal plantada de M2 falla**: cobertura del
80 % = 0,88 (0,85-0,92 en otras semillas; spec 0,75-0,85) porque los errores del filtro y de la tendencia están
correlacionados (−0,31) y §4 los suma como independientes; decidir si se acepta o se cambia la spec a priori. (Q1)
revisar las elecciones provisionales de implementación (lista en la Bitácora del 24-oct y en `IMPLEMENTATION_CHOICES`).

**Siguiente:** revisión del usuario → `m2_long` (6a) → `s_pit_001` (6b) → **S-PIT-001 resuelta, commiteada y
empujada** (6c, `pool_dev spit001`) → resto de M2 → M3 → pool → Validador + Estratega.

### Retomar (24-oct, tarde) — histórico

**Hecho (Constructor, 24-oct):** specs **v1.1** empujadas a priori (`d1bde77`, **10:46:29Z**), antes de implementar y de
cualquier contacto con la etiqueta para M2/M3/pool: **M2** con las peticiones de paro como flujo (f<sub>m</sub> −
f<sub>m−12</sub>, estado 47), V<sub>rev</sub> declarado no PIT + sensibilidad PIT `m2_struct_g_revpit`, regla operativa de
S-PIT-001 (se resuelve y se empuja **antes** de M3 y del pool); **M3** con el criterio de signos (cada γ > 0,01 en ≥ 50 %
de los cortes 2005-01 → 2021-10, clave nueva); **pool** con estudio de eventos por episodio y las predicciones a priori
del Estratega (P1-P11); **P-EVAL-BASE v4.1** (borrador, **no registrado**) con criterio 8, `test_start` declarado, tamaño
como cota inferior, bloques de 24. 239 tests en verde (suite después del push).

**Siguiente:** (1) **re-auditoría del Validador** (texto v1.1/v4.1) → (2) **usuario** → (3) **extensiones del arnés
v2.4** (niveles PIT, historia de variables, modelo apilado, `fraccion_umbral`, `sd_mensual`, ACF, 3 m × 80/20, estudio de
eventos) → (4) **implementación** M2/M3/pool con tests sintéticos → tabla v(edad) sin etiqueta → sonda de elegibilidad
→ (5) **placebos** → (6) **una corrida de desarrollo ≤ 2004** (M2 → S-PIT-001 → M3 → pool). Ojo: protección de rama solo
mientras el repo sea público.

### Retomar (24-oct, mediodía) — histórico

**Hecho (Constructor, 24-oct):** specs **a priori** empujadas antes de cualquier contacto con la etiqueta (`1a5f1f9`,
09:53:15Z): **M2 estructural** (`docs/models/m2_structural_spec.md`: factor coincidente con *ragged edge*, Ĝ con el
código de la etiqueta, σ̂² = filtro + revisión por edad + tendencia, sin parámetros ajustados con la etiqueta), **M3
TVTP eje G** (`docs/models/m3_tvtp_spec.md`: estados = etiqueta, emisión Ĝ en tiempo real, γ ≥ 0, ancla PIT, referencia
γ = 0, 3 m × 80/20 secundaria), **pool** (`docs/models/pool_spec.md`: {M0, M2, M3} + BLP por MAP, N<sub>min</sub> 60) y
borrador **P-EVAL-BASE v4** (`docs/models/p_eval_base_v4_draft.md`: pool − M0, k = 1, IC 95 %, ≥ 0,05; corrige M4-1/2/3;
**no registrado**). Esqueleto no registrado + 6 tests sintéticos; 235 tests en verde.

**Siguiente:** (1) **Validador + Estratega** revisan las tres specs y la v4 (en paralelo) → (2) **usuario**: aprobar la
retirada del criterio de signos (A1-3), niveles vía `levels_at` (sin v0.5), `incluye: []` → (3) arnés v2.4 +
implementación con tests sintéticos → tabla v(edad) sin etiqueta → sonda de elegibilidad (solo recuentos) → placebos
→ **una corrida de desarrollo ≤ 2004** (M2, M3, pool) → Validador + Estratega → decidir si registrar la v4 (puerta de
potencia: < 0,05 nats en desarrollo ⇒ potencia < 30 %). Ojo: protección de rama solo mientras el repo sea público.

### Retomar (24-oct, mañana) — histórico

**Decidido (usuario, 24-oct):** contraste principal de la evaluación única = **pool de log-scores {M0, estructural de G,
Markov TVTP eje G} + recalibración beta, Holm k = 1**; estructural y TVTP pasan a ser componentes del pool; M1 v1/v2,
informativas fuera de Holm.

**Hecho hoy (Constructor):** arnés **v2.3 con eje G continuo** (`d5b1e00`; sin modelos continuos no cambia nada) ·
**potencia del bloqueado** (`34554c6`, `docs/models/power_holdout.md`): **MDE (80 %) ≈ 0,12-0,15 nats** con el ruido de
M1 y ≈ 0,07 si el pool lo reduce a la mitad; umbral observado para pasar ≈ 0,10 nats; **k = 1 ≈ k = 2** con el criterio 1
actual (el IC 95 % > 0 ya exige p < 0,025) · **hash de M1 v1 explicado** (`7656192`, anexo A de `m1_results_dev.md`): lo
cambió el informe del harness v2.1 (`2fd94e0`, detección de giros v2.1); predicciones idénticas bit a bit, conclusión
intacta. 229 tests.

**Decisión pendiente del usuario (antes de la corrida de desarrollo del pool):** ¿criterio 1 con IC 95 % (como está) o
IC 90 % (aprovecha k = 1; MDE −0,01…−0,03 nats)? Es un cambio de criterio: se preregistra en P-EVAL-BASE v4.

**Siguiente:** (1) specs **a priori** de los componentes del pool: estructural vía **factor coincidente con ragged edge**
(4 series de la etiqueta + peticiones de paro + Filadelfia; Kalman; Ĝ con los pesos de la etiqueta) y **Markov TVTP con
emisión desde ese factor**; y la del pool (pesos, N<sub>min</sub>, recalibración beta fijada, BLP como sensibilidad) —
Investigador §5 · (2) **preregistro P-EVAL-BASE v4 con k = 1** (sin registrar hasta el ✅) · (3) una corrida de
desarrollo ≤ 2004 · (4) Validador + Estratega. Ojo: protección de rama solo mientras el repo sea público.

### Retomar (23-oct, tarde) — histórico

**Hecho hoy (Constructor):** base PIT **v0.4 candidata** (`657b6eb`; 4 derivadas de riesgo de giro; v0.3 intacta y
congelada; v0.4 en `CANDIDATE`, no en `FROZEN`) · **A3-1** comprobación de la protección de rama por código (`f1ccc8f`;
comprobada en GitHub: ok) · **spec M1 v2** a priori (`4d2b1ac`, H-M1-002 contaminada) · placebo limpio (`e5a5fd3`) ·
**una pasada de desarrollo: M1 v2 no bate a M0** (−0,017 nats; giros −0,035; falsas alarmas 0,75/año; `baa_gap10y` con
signo contrario) — `docs/models/m1_v2_results_dev.md` · borrador **P-EVAL-BASE v3** (M1 v1 + v2 frente a M0, Holm k = 2;
NO registrado). 215 tests.

**Siguiente:** Validador (base v0.4 + A3-1 + M1 v2) y Estratega (M1 v2) en paralelo → usuario decide: (a) congelar la
v0.4; (b) ¿evaluación única con M1 v1 + v2 (casi seguro "no") o esperar al Markov con transiciones variables (Filardo)
y evaluarlos juntos? No registrar P-EVAL-BASE sin esa decisión. Ojo: protección de rama solo mientras el repo sea
público (sin Pro).

### Retomar (23-oct, mañana) — histórico


**Decidido (23-oct):** M1 v2 + base PIT v0.4 (propuesta del Estratega §4-§5). Repo GitHub **público** con protección de `main` (sin force-push/borrado, admins incluidos) → A3-1 cubierta en GitHub. **En marcha:** Constructor (v0.4 → M1 v2 spec a priori → una corrida de desarrollo ≤ 2004; + comprobación por código de la protección de rama). Después: Validador + Estratega en paralelo → usuario → registrar P-EVAL-BASE (v1 + v2 vs M0, Holm k=2) → evaluación única. Si la sesión se corta: `git log --oneline -15`, ver qué commiteó el Constructor y relanzar con el encargo de la Bitácora del 23-oct. Ojo: si el repo vuelve a privado sin Pro se pierde la protección → evaluación única mientras sea público.

**Cierre 23-oct:** M1 v2 no bate a M0 (−0,017; FA 0,75/año). Validador: v0.4 ✅ (congelable), A3-1 ✅, M1 v2 ✅ proceso, P-EVAL-BASE v3 ⚠️ (no registrable). Estratega: ❌ no gastar el bloqueado en M1 v1+v2; siguiente: Markov TVTP solo eje G y/o nowcast estructural de G (`docs/reviews/2026-10-23_estratega_macro_m1v2.md`). **Pendiente del usuario:** congelar v0.4; reservar bloqueado; aspirante (Markov / estructural / ambos, Holm k≤2); cálculo de potencia antes de P-EVAL-BASE v4.

## Retomar (16-oct) — histórico

**Base PIT v0.3 CONGELADA** (tag `pit-v0.3`; veredicto ✅ `docs/validation/2026-10-16_pit_base_v0.3.md`; `tcu_gap` principal desde 1984-01 por decisión del usuario). Informe v0.3 hecho (`fbc5166`). **Arnés walk-forward v1 hecho** (`b01e7ee`, 115 tests, listón reproducido exacto) → en revisión: Validador (`docs/validation/2026-10-16_harness_v1.md`) + Estratega (`docs/reviews/2026-10-16_estratega_macro_harness.md`). Si no existen al retomar, relanzarlos (encargos en la Bitácora del 16-oct). Revisiones hechas (ambas ⚠️; A-1: la evaluación única no estaba garantizada por código; listón → persistencia calibrada M0). Arnés v2 hecho (`2159d53`): re-auditoría ⚠️ (**aprobado para desarrollo y para M1**; evaluación única bloqueada por A2-1, M2-1, M2-2). M0 (persistencia calibrada) es el listón: vintage ≤ 2004 0,811. **En marcha (16-oct, tarde):** Constructor arnés v2.1 (correcciones + ancla GitHub) y Constructor entregable (4) M1 (logística por eje + reglas). **Pendiente del usuario:** `gh auth login` y crear repo privado; aprobar P-EVAL-BASE (borrador). Después: Validador + Estratega sobre ambos.


**Estado al cierre del 16-oct (noche):** arnés v2.1 ✅ (condiciones operativas: protección de rama en GitHub antes de registrar P-EVAL-BASE). **M1 v1 no bate a M0** (✅ del Validador al proceso; Estratega ❌ para gastar el bloqueado). Validador y Estratega coinciden: **no gastar el periodo bloqueado en M1 v1**; preparar M1 v2 (hipótesis nueva, declarada contaminada; sin Sahm lineal; eje I estructural con subyacente; variables de riesgo de giro → base PIT v0.4); en la evaluación única v1 + v2 frente a M0 con Holm. **Usuario (16-oct):** acepta el criterio nuevo (giros ≥ 0, FA ≤ 0,5/año, total ≥ 0,05) y **para aquí**. Al retomar: preguntarle M1 v2 + base PIT v0.4 (recomendado) o Markov (Filardo). También pendiente: GitHub (`gh auth login`, repo privado + protección de rama). Detalle en la Bitácora del 16-oct.

**Si la sesión se corta (16-oct, tarde) — pasos:**
1. `git log --oneline -15` y `git status`: ver si los dos Constructores (arnés v2.1 y M1) commitearon. Encargos completos en la Bitácora del 16-oct.
2. Si falta alguno: relanzarlo con su encargo (revisando el trabajo sin commitear). Arnés v2.1 → resumen con cifras de detección de M0; M1 → `docs/models/m1_spec.md` debe estar commiteado ANTES de cualquier resultado.
3. Al terminar ambos: Validador (re-auditoría v2.1 + auditoría M1) y Estratega (M1) en paralelo → paquete al usuario.
4. GitHub: el usuario hará `gh auth login`; luego crear repo privado `financial_kb` (`gh repo create financial_kb --private --source . --remote origin --push`). Antes, comprobar que no se sube nada de datos ni `.env`.
5. Usuario aprueba P-EVAL-BASE (borrador `docs/models/p_eval_base_draft.md`) → registrar → evaluación única (solo con ✅ del Validador y ancla en GitHub).

## Retomar (15-oct, tarde) — histórico

**Dónde estamos:** Fase 3, entregable (2) **base point-in-time**, a punto de cerrarse.
- ✅ (1) Etiqueta **v1.1 congelada** (tag `label-v1.1`, validador ✅). Listón: persistencia PIT.
- ⏳ (2) Base PIT: v0.1 → v0.2 (re-auditoría ⚠️ "muy cerca de ✅", `docs/validation/2026-10-15_pit_base_v0.2.md`) → **v0.3 candidata hecha** (commit `64186fe`, 92/92 tests; **re-auditoría final del Validador en marcha**) con las correcciones: herencia automática de `principal_desde` (infl_energy_pressure), `vix` condicional < 2003-09, control "etiqueta t−4" en el placebo + tabla de potencia honesta, v0.3 **fuera de `FROZEN` hasta el ✅**, hash del meta de la etiqueta en los baselines, preregistros completos.
- Documentos clave: `docs/models/pit_base.md` (registro de cambios por versión), `docs/models/pit_calendar.md`, `research/pit_whitelist.yaml`, `research/hypotheses.yaml`, `research/trial_log.md`.

**Pasos para seguir (en orden):**
1. ✅ v0.3 terminada y commiteada.
2. (16-oct) Validador relanzado → `docs/validation/2026-10-16_pit_base_v0.3.md`. Si no existe al retomar, relanzarlo con el encargo de la Bitácora.
3. **Re-auditoría final del Validador** sobre la v0.3 → `docs/validation/<fecha>_pit_base_v0.3.md`. Si da ✅: meter la v0.3 en `FROZEN` (`src/features/pit.py`), tag `pit-v0.3`, instantánea de solo lectura, Bitácora y este Estado.
4. Reportero: añadir la base PIT al informe ([[Reports/Fase 3/Informe de resultados]]).
5. Siguiente entregable **(3) arnés walk-forward**: modo principal `vintage` (ALFRED) y `latest_truncated` como sensibilidad, puntuando en los dos sobre los mismos meses; etiqueta de entrenamiento recalculada con datos ≤ T en cada corte; embargo 6 m; periodo bloqueado 2005-01→ intocable; variables solo desde la lista blanca + `assert_no_forbidden`; estabilidad de cada variable a ambos lados del salto revisado → primera publicación; registro de pruebas. Baselines a batir (≤ 2004, 579 meses): vintage 61,1 % / log-loss 1,300; latest_truncated 63,0 % / 1,182.
6. Circuito en cada hito (preferencia del usuario): Constructor → **Validador** + **Estratega macro** en paralelo → paquete de correcciones al usuario → Constructor → **re-auditoría**.

**16-oct:** re-auditoría v0.3 ⚠️ con 2 condiciones (H-1 `tcu_gap` desde 1984-01, **decidido por el usuario**; H-2 guarda de `write_snapshot`) → Constructor corrigiendo → comprobación rápida del Validador → FROZEN + tag.

**Pendiente de decisión del usuario (no urgente):** v0.3 de la lista blanca con `permit_yoy` sobre media de 3 m y "sorpresa de inflación" (propuestas del Estratega no aprobadas aún); empalme VIX con VXO; inicio real del IPC subyacente del BLS (hueco).

### Retomar (14-oct, histórico)

**Fases del plan (`docs/PLAN.md`) y estado:**
| Fase | Contenido | Estado |
|---|---|---|
| 0 | Limpieza, git, datos unificados | ✅ hecha (7-oct) |
| 1 · MVP | DuckDB, clasificador de régimen, reporte semanal | ✅ hecha (7-oct); la revisión dijo que el reporte aún no sirve para decidir |
| Fase de datos (añadida por el usuario el 12-oct) | Recopilar, limpiar, auditar | ✅ cerrada el 14-oct: 15.397 series, 12,25 M filas, fusionada en `main` |
| 2 | Neo4j, textos (Dalio, Berkshire, 10-K), agentes Scout/Estratega/Abogado del diablo | 🟡 empezada y aparcada (Neo4j en Docker, ingestas de ciclos/textos); agentes de análisis parados hasta cerrar datos |
| 3 | Modelos (ver `docs/PLAN.md`, "Fase 3 — arquitectura de modelos") | ▶ **siguiente**: etiqueta + base point-in-time + test de fugas |
| 4 | Cron diario, analista de empresas, calculadora fiscal, dashboard | 🟡 actualización automática montada el 13-oct; resto pendiente |
| +6 meses | Paper trading antes de dinero real | ⏳ |

**Hecho el 14-oct:** auditoría completa con las fuentes nuevas (`docs/data/audit_2026-10-14.md`, 0 críticas), arreglos de INE (EPA por sexo), CFTC (ECU) y `PIT_RULES`, reporte [[Reports/2026-10-14_semanal]] y commit en `fase-datos`. Tarea launchd de arranque (`com.financialkb.arranque`) instalada: recupera la actualización perdida al encender el Mac.

**14-oct (tarde):** etiqueta de régimen v0.2 lista ([[Proyecto/Etiqueta de régimen]]: 13/13 comprobaciones; falta decidir 4 propuestas y congelar v1.0). Programa de investigación de relaciones adelantadas en `docs/models/research_program.md`. Futuros y derivados integrados (5 fuentes, 213 series; decisión pendiente: ¿pagar Databento/Norgate?). Base de datos: 15.610 series, 12,53 M filas.

**Siguiente paso (Fase 3, orden de `docs/PLAN.md`):**
1. Especificación de la etiqueta de régimen (ex post, nowcast vs forecast, horizonte) + matriz de variables point-in-time + test de fugas.
2. Pendientes de la revisión de la Fase 1 como variables (histéresis de G, inflación compuesta, bear/bull steepening, liquidez neta diaria y global, capa EUR).
3. Arnés walk-forward → baselines (persistencia, reglas, logística, Markov) → GBM → calibración → etapa 2 + cartera → reglas de oro → informe con Claude → paper trading.
- Más adelante: reactivar la Fase 2 (grafo y agentes de análisis). Volver a ejecutar `imf_weo` con el WEO de octubre de 2026.

## Fase de datos (decisión del 2026-10-12; cerrada el 14-oct)

Aunque `docs/PLAN.md` ya habla de la Fase 2 (Neo4j, agentes de decisión), **seguimos en la fase de datos**: recopilar, limpiar, almacenar y auditar.
- **Agentes activos:** recopiladores (EE. UU., Europa/BCE/España e internacional) y un auditor de datos.
- **Aparcados hasta tener datos completos y fiables:** abogado del diablo, comité, estratega y cuantitativo.

## Hecho

- **Fase 0** (2026-10-07): limpieza, git y datos unificados en `data/archive`.
- **Fase 1** (2026-10-07, commit `9c3f887`): base de datos DuckDB, clasificador de régimen desde 1950 (4 cuadrantes, ciclo de deuda, crédito y liquidez), validación en `docs/phase1_validation.md` y primer reporte en [[Reports/2026-10-07_semanal]].
- **Fase 2a** (sin commitear): Neo4j local en Docker (`src/graph/`, `make graph-up/graph-load`) e ingestas de ciclos (BIS, NY Fed, RTDSM).
- **Revisiones de la Fase 1:** `docs/reviews/2026-10-07_estratega_macro.md` y `docs/reviews/2026-10-07_pm_abogado_diablo.md`. Veredicto: **el reporte aún no sirve para decidir.**
- **13-oct:** 7 arreglos MEDIA cerrados (incluido un fallo real en Maddison regional), 6 fuentes nuevas (release 388, Z.1, repo SOFR/BGCR/TGCR, liquidez EE. UU., balances de bancos centrales, IFS del FMI) e `ine` ampliado (EPA desde 1976, IPC desde 1961). Base de datos: **14.026 series**, 6,46 M de filas. Auditoría `docs/data/audit_2026-10-13.md`: 0 críticas, 32 altas explicadas. Reporte [[Reports/2026-10-13_semanal]].
- **Auditoría de datos** (2026-10-12): `docs/data/audit_2026-10-12.md` y su CSV. Reejecutar con `.venv/bin/python -m src.audit.run`.

## Inventario de datos (`~/financial_archive/curated`, 2026-10-12 por la mañana)

| fuente | series | estado |
|---|---|---|
| fred | 362 | ámbar (auditoría) |
| alfred | 14 | ámbar; ampliándose |
| bis | 688 | ámbar |
| jst_macrohistory | 998 | verde (solo uso no comercial) |
| maddison | 517 | ámbar (catálogo duplicado) |
| spf | 488 | verde |
| ken_french, damodaran, gpr, sipri, boe_millennium_uk | 88, 19, 99, 77, 45 | verde |
| shiller, nyfed, rtdsm, nber_macrohistory, wb_pinksheet | 21, 42, 16, 39, 87 | ámbar |
| gold, imf_cofer | 10, 58 | rojo |
| **EE. UU. (terminado):** fred_us, fed_yieldcurve, us_treasury, nyfed_hhdc, us_hist_labor, shiller_housing, + alfred 14, nber_macrohistory 1.627 | 1.691, 73, 25, 103, 2, 9 (~3.500 en total) | hecho y auditado (tarde). Doc: `docs/data/us_macro_credit.md` |
| **nuevas hoy (internacional, terminado):** bis_ext, oecd, imf_weo, imf_gdd, imf_hpdd, wb_wdi, measuringworth | 366, 309, 955, 155, 31, 375, 16 (2.207 en total) | hecho y auditado (tarde). Doc: `docs/data/international_macro.md` |
| **Europa (terminado):** ecb, eurostat, bde, ine, bundesbank | 116, 98, 53, 13, 19 (299 en total) | hecho y auditado (tarde). Doc: `docs/data/europe_macro_financial.md` |

## Actualización automática (desde el 13-oct)
launchd en el Mac: **diario** lun-sáb 7:30 (`make daily`: fuentes diarias + warehouse + régimen) y **semanal** domingo 7:00 (`make semanal`: todo + auditoría + reporte). Resultado de cada ejecución en [[Proyecto/Actualizaciones]]; notificación de macOS si falla algo. Detalle: `docs/automatizacion.md`.

## Segunda tanda del 13-oct (huecos de prioridad alta)
- Factores: `ken_french_intl` (internacional y diario), `aqr` (QMJ con España, BAB, VME, TSMOM, Century; **sin redistribuir**), `jkp` (13 temas, 12 zonas; **no comercial**).
- Mercado y sentimiento: `cftc_cot` (posicionamiento, 21 contratos), `cboe` (VIX3M, VVIX, SKEW, put/call…), `fed_ebp` (excess bond premium), +51 en `fred_us` (Brent diario, encuestas regionales de la Fed, dólar AFE/EME).
- Europa y España: Bund diario 1-30 años, forwards y estrés soberano diario del BCE, empleo euro, vivienda España (IPV, compraventas, hipotecas), producción industrial, `ifo`, `zew`; IPC de la OCDE desbloqueado.
- Series diarias de FRED que estaban congeladas: arregladas.
- Base de datos: **15.397 series, 12,2 M de filas.**
- Huecos que quedan: PMI (de pago), bonos soberanos diarios por país salvo Alemania, Euribor diario, MOVE, flujos ICI e Inverco, índices MSCI/STOXX con dividendos.

## Liquidez (petición del 13-oct)
Datos para medir cuánta liquidez meten la Fed, el Tesoro y los grandes bancos centrales (doc `docs/data/liquidity_2026-10-13.md`):
- EE. UU.: balance de la Fed (WALCL + detalle H.4.1), reservas, TGA **diaria** desde 2005, RRP, SRF, emisión neta de letras/cupones, subastas desde 1979, recompras, M2 mensual y semanal, repo SOFR/BGCR/TGCR.
- Global: Eurosistema, BoJ, SNB, BoE (balance solo 2006-14; M4 desde 1982), PBoC (hasta 2025-06), M2 de China.
- El clasificador ya usa liquidez neta = WALCL − TGA − RRP (semanal). Propuesto para la fase de modelo: versión diaria, agregado global en USD e impulso a 13/26 semanas.
- Hoy: liquidez **neutral** por poco (score −0,47; ayer escasa, −0,51), liquidez neta 5,86 billones $ (+4,5 % a/a).

## Problemas abiertos (reauditoría del 2026-10-12 por la tarde)
> 13-oct: los MEDIA de esta lista están **cerrados** salvo rtdsm (modelo) y la revisión una a una de `fred_us`/`imf_weo`.

Los problemas en rojo de la mañana (fallo del IPC, base de datos desfasada, TED, oro en los análogos, look-ahead sin marcar y COFER) están **corregidos**: ver `docs/data/audit_2026-10-12_tarde.md`. Ya no hay ninguna fuente en rojo.

Quedan problemas de prioridad MEDIA que no bloquean:
- **`BOGZ1FL073164003Q`:** unidades mal en el catálogo y salto ×10 en 1952.
- **`nber_m12014`:** 1915 dividido por 10.
- **`shiller_gs10`:** el dato de 2019-07 está desplazado.
- **Arroz:** valores a 0 en 2008; hay que limpiarlo en `wb_pinksheet.py`.
- **M1SL:** ruptura de definición en 2020-05.
- **Eventos:** tipo `inflation_crisis` fuera del contrato y `cow_extra_321` con fechas al revés.
- **Catálogo de maddison:** filas duplicadas.
- **rtdsm:** sin conectar al clasificador.
- **Fuentes nuevas:** quedan muchas MEDIA por revisar (`fred_us`, `imf_weo`).

Huecos de fuentes (de pago o sin API):
- PMI, Lebergott/Weir, Homer & Sylla, Global Financial Data y Euribor diario.
- Banque de France (exige clave).
- EPA 1976-2001 (solo en INEbase).
- IFS del FMI sin curar.
- Release 388 de FRED (1914-41) y Z.1 completo (zip de la Fed).

## Próximos pasos
0. (13-oct) Fusionar `fase-datos` en `main` cuando el usuario lo apruebe. Huecos que siguen: MTS anterior a 1980, BoE tras 2014, total de activos de la Fed 1969-2002, IPC subyacente de España antes de 2002, PMI, Euribor diario.

1. Corregir los problemas MEDIA de la lista anterior (los scripts de ingesta afectados, sin tocar los datos a mano).
2. Cubrir los huecos accesibles: release 388 de FRED, Z.1 completo, IFS del FMI, EPA anterior a 2002 (PC-Axis del INE) y repo BGCR/TGCR.
3. Volver a ejecutar `imf_weo` cuando salga el WEO de octubre de 2026, guardando antes la versión de abril.
4. Pendientes de la revisión de la Fase 1, que seguirán cuando el usuario dé por cerrada la fase de datos: histéresis de G, I compuesta (que incluya petróleo y PPI), bear frente a bull steepening y capa EUR.
5. Ciclo de mantenimiento: `make data` (ingest → warehouse → regime → audit).
