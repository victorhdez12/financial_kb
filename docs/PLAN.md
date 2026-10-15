# Plan del sistema — síntesis de los 5 informes de agentes (2026-10-07)

Fuente: revisión en paralelo por 5 agentes (Scout de datos, Estratega macro, Analista cuantitativo,
Analista de empresas, Asesor/Arquitecto). Este documento es la referencia para las siguientes fases.

## Principios

1. **Python calcula, el LLM interpreta.** Ninguna cifra la genera un LLM; la narrativa copia números del JSON de señal y un validador lo comprueba.
2. **Point-in-time siempre.** Backtests solo con datos disponibles en cada fecha (vintages ALFRED, retrasos de publicación, z-scores expansivos).
3. **Apoyo a la decisión, no ejecución.** Paper trading 6-12 meses antes de dinero real; sin herramientas de broker.
4. **Procedencia.** Cada claim/cita enlaza a su fuente (chunk_id, serie). Las contradicciones coexisten.
5. **Contar episodios, no meses.** ~12 recesiones en EE. UU. desde 1948: muestra pequeña → shrinkage, baja confianza explícita.

## Arquitectura objetivo

```
Ingesta (FRED/ALFRED, BLS, SEC, Shiller, JST, Ken French, precios ETF UCITS, RSS)
  → DuckDB + Parquet (fuente de verdad numérica)
  → features/regímenes (regime_daily)
  → motor probabilístico (HMM + análogos + Bayes) → escenarios → EV/CVaR/tamaño
  → Neo4j local (Docker): eventos, análogos, lecciones, chunks de texto
  → agentes LLM (Claude) + Jev (decisiones tipadas, como un modelo más del ensemble)
  → obsidian/Reports/ (Markdown) + señal JSON + obsidian/Decisions/ (diario)
```

## Marco de regímenes (Estratega macro)

- **Crecimiento (G):** media de z-scores (ventana 10 años) de INDPRO yoy, PAYEMS yoy, GDPC1 q/q anualizado, UNRATE invertido. Regla de Sahm > 0,5 pp fuerza G↓. G↑ si compuesto > 0 y Δ6m > 0.
- **Inflación (I):** CPILFESL y PCEPILFE 6m anualizado vs 2 %, + T5YIE, PPIACO yoy. I↑ si core 6m > 2,5 % y acelera; I↓ si < 2 % o desacelera > 0,5 pp.
- **Cuadrantes:** Reflación (G↑I↑), Goldilocks (G↑I↓), Estanflación (G↓I↑), Deflación/recesión (G↓I↓).
- **Ciclo de deuda corto:** expansión temprana (curva > 1 y empinándose, BAA10Y ↓), expansión tardía (TCU > 80, inflación ↑), endurecimiento (FEDFUNDS +100 pb/12m, real FF > 1), techo (T10Y3M < 0 ≥ 3m), desapalancamiento (BAA10Y > 3 o NFCI > 0), reflación (recortes > 150 pb o WALCL > +10 % yoy).
- **Ciclo largo:** GFDEGDQ188S > 100 % y subiendo, FYFSGDA188S < −5 % fuera de recesión, intereses/ingresos federales, deuda privada/PIB (BIS).
- **Liquidez:** M2 yoy − PIB yoy; WALCL − WTREGEN − RRPONTSYD; DFII10; NFCI.
- **USREC no sirve como variable en tiempo real** (se publica 6-18 meses tarde).

## Huecos de datos (por prioridad)

1. ALFRED vintages: GDPC1, PAYEMS, CPIAUCSL, INDPRO, UNRATE.
2. Series FRED que faltan: DFII10, A091RC1Q027SBEA, W006RC1Q027SBEA, TCMDO, WTREGEN, RRPONTSYD, THREEFYTP10, CFNAI, NROU, GS10, TB3MS, TWEXB, PCOPPNEW, TDSP, TOTLL, BUSLOANS.
3. Rentabilidades largas: Shiller (1871+), Ken French, Damodaran, World Gold Council (oro: FRED retiró GOLDAMGBD228NLBM), World Bank Pink Sheet.
4. Internacional: JST Macrohistory, BIS, OCDE CLI, BCE/Eurostat.
5. Spreads largos: BAML HY/IG en FRED solo 3 años → usar Moody's BAA/AAA.
6. Universo de empresas: composición histórica S&P 500 + empresas quebradas (Enron, Lehman, WorldCom...) contra el sesgo de supervivencia.

## Motor de decisión (Analista cuantitativo)

- Régimen: `statsmodels` MarkovRegression o `hmmlearn` GaussianHMM, usando **probabilidades filtradas**, nunca suavizadas. Previsión π_{t+h} = π_t·P^h.
- Análogos: Mahalanobis sobre z-scores + DTW sobre trayectorias de 12-24m; excluir ±24 meses; 1 representante por episodio; N_eff = (Σw)²/Σw², baja confianza si < 10.
- Combinación: prior HMM + análogos con Dirichlet: p_k = (α·π_k + Σ w_s·1[k]) / (α + Σw).
- Rentabilidades por escenario con shrinkage (James-Stein / Ledoit-Wolf).
- EV(d) = Σ p_k·Δw·(μ_k − r_f) − costes; varianza total; CVaR95 por Monte Carlo.
- Tamaño: Kelly fraccionado κ ∈ [0,1; 0,25] + risk parity + ajuste por confianza. Actuar solo si EV/σ_EV > 0,5 y EV > costes.
- Validación: walk-forward con vintages, Brier Skill Score > 0, Deflated Sharpe, costes 5-10 pb.
- Módulo: `src/decision/{features,regime,analogs,bayes,scenario_returns,ev_risk,sizing,backtest,calibration}.py`.

## Jev (TypeSafe, System One)

Modelo que devuelve decisiones tipadas con probabilidades calibradas (acceso anticipado, sept. 2026). Uso propuesto: recibir el estado macro diario (JSON desde DuckDB) y responder preguntas cerradas (régimen, P(recesión 12m), sobre/infraponderar). Se trata como **un miembro más del ensemble**, validado con el mismo walk-forward y Brier que el HMM y los análogos antes de darle peso.

## Empresas y 10-K (Analista de empresas)

- Hay 6 empresas (AAPL, MSFT, KO, GE, XOM, JPM); el texto útil (`10k_clean.txt`) son ~85 MB; nunca embeber `submission.txt`.
- XBRL CompanyFacts solo desde 2009; `fy` es el ejercicio del filing, filtrar por duración ~365 días y `period_end`; guardar primera versión publicada (`filed`).
- Trocear por secciones (1, 1A, 3, 7, 7A, 8, 9A); en el índice "Item 1A" aparece antes que el cuerpo.
- Embeddings: sustituir all-MiniLM (256 tokens; trunca la mitad de cada chunk) por bge-base-en-v1.5 o nomic-embed-text-v1.5, chunks de 300-400 tokens con cabecera ("KO 10-K FY2010 · Item 1A") + reranker.
- Neo4j: Docker `neo4j:5-community` en lugar de Aura Free.

### Lecciones de inversores → reglas comprobables (alertas, no señales)

| Principio | Regla |
|---|---|
| Buffett, foso | ROIC > 12 % en ≥ 8 de 10 años; desviación margen bruto < 3 pp |
| Graham | P/E (beneficio medio 10 años) < 15-20; P/E×P/B < 22,5; current ratio > 2 (no bancos) |
| Buffett, deuda | Deuda LP / FCF < 4 |
| Munger, incentivos | CAGR acciones diluidas ≤ 0; SBC/CFO < 10 % |
| Lynch | PEG < 1; alerta si inventario crece más que ventas |
| Calidad contable | Accruals > 10 % activos; debilidad material en Item 9A |
| Marks, péndulo | Percentil de BAA10Y y de valoración |

Las citas se guardan con `char_start/char_end` verificados en el texto original.

## Política de inversión (borrador, ajustar en `config/ips.yaml`)

- Horizonte ≥ 10 años; colchón de emergencia fuera del sistema.
- Núcleo 80-90 % All Weather en **fondos indexados** (traspaso sin tributar, art. 94 LIRPF); satélite táctico ≤ 10-20 % en ETFs UCITS.
- Volatilidad objetivo 8-10 %; drawdown máximo 20-25 %; posición táctica ≤ 5 %; sin apalancamiento ni derivados el primer año.
- Rebalanceo trimestral o bandas ±5 pp; máximo un cambio táctico al mes.
- Calcular el coste fiscal antes de proponer cualquier venta (regla de 2 meses, modelo 720, W-8BEN).

## Equipo de agentes permanente

| Agente | Salida | Cuándo |
|---|---|---|
| Scout | `News/fecha.md`: datos nuevos, sorpresas, fallos de ingesta | Diario |
| Estratega macro | Régimen, ciclo, 3 escenarios con probabilidad | Diario breve / semanal completo |
| Analista cuantitativo | Probabilidades, EV, alertas de ruptura (sin LLM salvo resumen) | Diario |
| Analista de empresas | Fichas en `Assets/` | Semanal / bajo demanda |
| Abogado del diablo | Contraargumentos, colas, veto si se incumple el IPS | Antes del comité |
| Comité | Reporte final + señal JSON + entrada del diario | Semanal/mensual |

## Fase 3 — arquitectura de modelos (propuesta del usuario, revisada el 2026-10-14)

Sustituye y concreta el "Motor de decisión" de arriba: HMM, análogos y Bayes pasan a ser modelos del ensemble, no la base.

### Capa 1 — Base point-in-time (primer entregable)
- **Etiqueta de régimen definida antes de modelar** (`docs/models/label_spec.md`): cuadrante G×I **ex post** con datos definitivos (crecimiento e inflación realizados en los k meses siguientes; contraste con fechas NBER). Nunca la salida del clasificador de reglas (sería circular).
- Decidir y documentar: **nowcast** (régimen actual) frente a **forecast** (régimen a h = 3, 6, 12 meses); número de clases; frecuencia (mensual al principio).
- **Matriz de variables as-of** (`src/models/features.py`): en cada fecha t, solo lo publicado en t (vintages ALFRED, retardos de publicación, `pit_role = 'observed'`, z-scores con ventana expansiva). Excluir `forecast`/`lookahead` y marcar las series que se revisan (AQR, JKP, Z.1, SOFR).
- Test automático de fuga: ninguna variable puede tener fecha de publicación posterior a t.

### Capa 2 — Modelos
- **Baselines obligatorios** (el listón que hay que batir): persistencia point-in-time (la última etiqueta que se conoce en t, la de t − 5, recalculada con los datos publicados en t; ficha §12), clasificador de reglas actual, logística/probit con 5-10 variables (curva, EBP, Sahm, inflación subyacente), Markov switching.
- **Aspirante:** LightGBM/XGBoost/CatBoost con árboles poco profundos, regularización fuerte y restricciones de monotonía donde haya sentido económico. Solo entra si bate a los baselines fuera de muestra.
- Ensemble: combinar modelos **distintos** (GBM + logística + Markov), no tres GBM.
- **Dos etapas:** (1) probabilidad de régimen + confianza calibrada; (2) preferencia relativa de factores/activos condicionada al régimen, con shrinkage hacia la media (pocos meses por régimen).
- Un único modelo de régimen al principio; los indicadores por bloque (crédito, empleo, inflación, liquidez) entran como variables.

### Validación (nivel profesional)
- Walk-forward con **purging + embargo** (etiquetas solapadas); ajuste de hiperparámetros con validación anidada.
- **Periodo final bloqueado: 2005-01 → abierto** (decidido el 2026-10-14): no se mira hasta el final; una sola evaluación.
- Métricas de probabilidad: **log-loss / Brier Skill Score frente a la persistencia**, curvas de calibración (calibración isotónica/Platt dentro del walk-forward). El acierto (58-65 % esperable) se informa, pero no decide.
- **Registro de pruebas** (todas, también las fallidas) y **Deflated Sharpe** para corregir por número de intentos.
- Etapa 2 validada **de extremo a extremo**: ¿la cartera resultante bate a la cartera estática del IPS después de costes (5-10 pb), impuestos y en EUR? Con instrumentos invertibles (fondos indexados / ETFs UCITS), no solo con factores teóricos.
- Estabilidad: resultados por década y por episodio (contar episodios, no meses).

### Capa 3 — Reglas de oro
- Candidatas desde SHAP, comportamiento histórico de factores por régimen y sentido económico. **SHAP explica el modelo, no la economía:** una regla es hipótesis hasta que tiene sentido económico **y** aguanta en el periodo bloqueado.
- Se guardan versionadas (`config/rules.yaml` + Neo4j) con su evidencia y fecha de validación.

### Capa 4 — Cartera y riesgo (nueva)
- Traduce probabilidades + preferencias a pesos dentro del IPS: límites por posición, control de rotación (máx. un cambio táctico al mes), volatilidad objetivo, cobertura de divisa USD/EUR, coste fiscal antes de vender.
- Benchmark fijo: la cartera estratégica del IPS.

### Capa 5 — LLM (Claude)
- Recibe solo salidas estructuradas (JSON de señal) + reglas validadas + plantilla fija. Python calcula, el LLM redacta; un validador comprueba que cada cifra del texto está en el JSON.
- No busca señales libres en la web ni en redes para alterar la decisión.
- Knowledge Graph como memoria estructurada: reglas, definiciones de régimen, historial de decisiones, perfiles de empresa.

### Capa 6 — Salidas
- **A) Informe de inversión/régimen:** régimen actual + confianza calibrada; renta variable (estilos a favorecer/infraponderar); renta fija/duración; riesgos y puntos de vigilancia; implicaciones para la cartera; vista opcional Fed/BCE; limitaciones del sistema.
- **B) Informe para empresas** (después de validar A): mismo régimen cruzado con el perfil de la empresa (inventario, capex, deuda, liquidez, segmentos). Requiere datos propios de cada empresa.
- Aviso: recomendaciones de inversión a terceros = asesoramiento regulado (CNMV, MiFID II). Uso propio sin problema.

### Operación
- Monitorización: deriva de variables y del modelo, calidad de datos (auditor existente), alertas si la calibración se degrada.
- Registro de modelos y experimentos (MLflow o equivalente), ficha por modelo (`docs/models/<modelo>.md`): datos, etiqueta, métricas, limitaciones.
- Paper trading ≥ 6 meses antes de dinero real.

### Regla de admisión de variables al modelo principal (2026-10-14)
Una variable solo entra en el modelo de producción si cumple las cuatro condiciones:
1. **Fuente viva:** se puede actualizar hoy. Si no, por ejemplo `eia_futures`, cortada en 2024-04, solo sirve para investigación hasta que se empalme con otra fuente.
2. **Historia mínima:** cubre ≥ 3 recesiones NBER **o** ≥ 6 cambios de régimen de la etiqueta. Si no, por ejemplo `atl_mpt`, desde 2023, se usa solo en la capa "descontado por el mercado" y en el informe.
3. **Point-in-time:** tiene un retardo de publicación documentado en el calendario y no es `forecast`/`lookahead`, salvo que se use de forma explícita como expectativa con su fecha de publicación.
4. **Sin cambio de régimen de disponibilidad:** el patrón de huecos no puede delatar la época. Las variables que empiezan tarde entran en modelos por época o se imputan con un indicador de disponibilidad; nunca se deja que "dato presente / ausente" haga de señal.

El backtest usa un **embargo de 6 meses**, porque la etiqueta usa datos hasta t+4. Los meses provisionales y con peso 0 no entrenan ni puntúan.

### Periodo bloqueado y reglas del arnés (decisión del usuario, 2026-10-14, tras la validación de la etiqueta)
- **Periodo bloqueado: 2005-01 → abierto.** La investigación empírica de relaciones y el diseño del modelo base usan **solo datos con fecha ≤ 2004-12**. El periodo bloqueado se evalúa **una sola vez**, con todo preregistrado; sus ampliaciones (a medida que maduran los meses provisionales) también se preregistran.
- **Etiqueta de entrenamiento sin fuga de tendencia (obligatorio):** en cada corte T del walk-forward, la etiqueta de entrenamiento se **recalcula solo con los datos disponibles hasta T**. Prohibido usar la etiqueta final precalculada para entrenar. La puntuación sí se hace contra la etiqueta oficial congelada.
- **Columnas prohibidas:** el arnés llama a `assert_no_forbidden()` (lista negra de `src/labels/`) antes de entrenar.
- **Baseline honesto que hay que batir: persistencia point-in-time**, es decir, la última etiqueta que realmente se conoce en t (**63,6 % de acierto, log-loss blanda 1,235**; ficha v1.1 §12 y `label_v1.1_checks.md` §6b). La persistencia "mes anterior" (89 %) y la etiqueta final desplazada 5 meses (68 %) tienen fuga y no valen como referencia. El baseline y las variables se construyen con el mismo `vintage_mode`. La métrica principal sigue siendo la log-loss.
- **Variables que nacen dentro del periodo bloqueado** (`cboe_vx` 2004, `mpls_mpd` 2006): no se seleccionan ni se ajustan explorando datos de 2005-2026. Se definen **a priori por teoría económica y se preregistran** (`research/hypotheses.yaml`, H-DER-001 y H-DER-002). Se evalúan como **módulo adicional** dentro de la evaluación única del walk-forward point-in-time, cuando cumplan la historia mínima de la regla de admisión.

### Capas ex post y decisiones tras la revisión económica de la etiqueta (usuario, 2026-10-15)
- La etiqueta v1.1 **no se toca**: es el objetivo del nowcast. Revisión: `docs/reviews/2026-10-15_estratega_macro_etiqueta.md`.
- **Nombre visible** del cuadrante `late_cycle`: "Crecimiento con inflación alta" (solo en informes y gráficos; el identificador no cambia).
- **Capas ex post preregistradas** (`research/hypotheses.yaml`, L-CAP-001/002/003): dirección de la inflación, shock energético y holgura laboral. Son columnas aparte, prohibidas como variables; sirven a la Etapa 2 (cuadrante × recesión × dirección, mismo signo en 1955-79 y 1980-2004) y a los informes.
- **Pospuesto a su fase:** etiqueta v2.0 con inflación frente a expectativas (Livingston, SPF, Michigan), solo si la Etapa 2 lo justifica con datos ≤ 2004; capa EUR; fiscalidad española (rotar con fondos traspasables, no ETF) en la fase de cartera.
- Toda mirada a rendimientos se anota en `research/trial_log.md`.

### Investigación de relaciones adelantadas
Programa propio en `docs/models/research_program.md`: hipótesis con mecanismo y preregistradas, prueba de universalidad (JST, OCDE, zona euro), métodos de alerta temprana y contenido incremental fuera de muestra, control de comparaciones múltiples. Las reglas validadas alimentan el modelo, las reglas de oro y un panel de alertas; el sistema de reglas compite con el GBM. Futuros y derivados: variables y "sorpresa frente a lo descontado".

### Orden de trabajo
1. Especificación de la etiqueta + matriz point-in-time + test de fugas.
2. Pendientes de la revisión de la Fase 1 como variables: histéresis de G, inflación compuesta (petróleo, PPI), bear/bull steepening, liquidez neta diaria y global, capa EUR.
3. Arnés de backtest walk-forward (purging, embargo, periodo bloqueado, registro de pruebas).
4. Baselines → aspirante GBM → ensemble → calibración.
5. Etapa 2 (factores por régimen) + capa de cartera, validadas de extremo a extremo.
6. Reglas de oro validadas → informe A con Claude → paper trading.

## Roadmap

- **Fase 0 (hecha 2026-10-07):** limpieza, git, bugs de descarga, datos unificados en `data/archive`.
- **Fase 1 — MVP (2 semanas):** FRED + BLS a DuckDB; clasificador de 4 cuadrantes + curva + spreads; script con Claude que escribe `obsidian/Reports/<semana>.md`; plantilla de diario de decisiones.
- **Fase de datos (añadida 2026-10-12, cerrada 2026-10-14):** 15.397 series, 12,25 M filas, auditadas; actualización automática con launchd.
- **Fase 2 (sem. 3-5):** Neo4j local; ingesta por secciones (Dalio, Berkshire, 10-K); agentes Scout, Estratega, Abogado del diablo.
- **Fase 3 (siguiente, desde 2026-10-14):** ver "Fase 3 — arquitectura de modelos": base point-in-time, baselines y GBM, validación walk-forward, reglas de oro, capa de cartera, informe con Claude; paper trading.
- **Fase 4 (sem. 10-13):** cron diario; analista de empresas con universo histórico; calculadora fiscal; dashboard.
- **+6 meses de paper trading:** decidir si se pasa a dinero real en el satélite.
