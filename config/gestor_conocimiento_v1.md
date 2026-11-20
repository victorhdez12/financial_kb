---
documento: Documento de conocimiento de los gestores agentes (C1, M1) y del supervisor — macro, instrumentos y modelos del proyecto
version: v1 (2026-11-19) — docs/factors/M1_cartera_macro_spec.md v1.1 §7 y C1_claude_gestor_spec.md v1.1 §7. Va detrás del
  mandato en el system prompt; su sha256 se guarda en cada línea del registro. Cambiarlo = v2 declarada (fichero nuevo).
fuentes: los documentos del repo citados en cada punto (rutas relativas al repo). Ninguna cifra es nueva: todas salen de ahí.
---

# Conocimiento del gestor

Úsalo así: la parte A es oficio de gestor macro (lo que un buen gestor sabe); la parte B dice **qué mide cada modelo
del proyecto, cuánto se ha medido que acierta y dónde falla**. Regla de oro del proyecto: **lo no validado fuera de
muestra es contexto, no señal**; un modelo «descriptivo» no se convierte en señal por citarlo.

## A. Oficio macro

### A1. Ciclo de negocio
- Fases: expansión temprana (crecimiento acelerando, inflación baja, curva empinada, crédito abriéndose), expansión
  tardía (capacidad ocupada, salarios e inflación subiendo, banco central endureciendo), desaceleración (curva plana o
  invertida, beneficios estancados) y recesión (paro subiendo deprisa, beneficios cayendo, el banco central baja tipos).
- La bolsa descuenta: suele tocar fondo **antes** del final de la recesión y caer **antes** de que empiece. Lo que mueve
  precios es el **cambio** frente a lo esperado, no el nivel del dato.
- El paro es retrasado en el nivel pero útil en el cambio: la regla de Sahm (media 3 m del paro − mínimo de 12 m ≥
  0,5 pp) marca recesiones ya empezadas, no las anticipa.
- Recesiones de EE. UU. son raras (≈ 1 cada 6-8 años): cualquier «probabilidad de recesión» tiene pocos episodios
  detrás; desconfía de la precisión.

### A2. Ciclo de deuda y crédito
- Ciclo corto (5-8 años): el crédito privado acelera con tipos bajos, el banco central endurece, los diferenciales se
  abren, los impagos suben, el crédito se contrae. Ciclo largo (décadas): deuda/PIB creciente hasta que los tipos ya no
  pueden bajar; entonces desapalancamiento (bueno si hay reflación monetaria, malo si es deflacionario).
- Diferenciales de crédito (Baa − Tesoro, HY OAS): suben ANTES y DURANTE las caídas de bolsa; niveles muy bajos
  (complacencia) no predicen el momento del giro. Un salto rápido (Δ3 m) importa más que el nivel.
- Auge de crédito/PIB (Δ5 años alto) precede a crisis bancarias con años de margen (Schularick-Taylor): es un riesgo de
  fondo, no un aviso de timing.

### A3. Liquidez y banco central
- Liquidez neta (balance de la Fed − TGA − repos inversos), M2 frente al PIB nominal, tipo real a 10 años (DFII10) y
  condiciones financieras (NFCI). Liquidez abundante ayuda a activos de riesgo con retraso de meses; el tipo real alto
  pesa sobre oro, crecimiento caro y vivienda.
- «No luches contra la Fed» es tendencia, no regla: los recortes de tipos en una recesión ya empezada no salvan la bolsa.

### A4. Curva de tipos
- Curva 10 a − 3 m invertida: históricamente precede recesiones de EE. UU. con 6-24 meses de retraso y algún falso
  positivo. El momento peligroso suele ser el **re-empinamiento** tras la inversión (el corto cae porque el banco central
  ya recorta).
- Bonos largos (TLT, duración ≈ 16-17): protegen en recesiones desinflacionarias; **no** protegen cuando la inflación
  sube (2022: bolsa y bonos cayendo juntos).

### A5. Inflación
- Mira la subyacente (sin energía ni alimentos) y su aceleración a 3-6 meses, salarios, expectativas (breakevens) y
  materias primas. La inflación alta es lo peor para bonos y letras en términos reales y malo para la bolsa en
  estanflación; ayudan materias primas, oro (sobre todo con tipos reales cayendo) y, a largo, la vivienda.
- La inflación **no se anticipa** bien con modelos (en el proyecto: T3/T4 no establecidos).

### A6. Indicadores adelantados (EE. UU.)
- Pedidos nuevos del ISM manufacturero, peticiones iniciales de paro (tendencia de 4 semanas), permisos de construcción,
  confianza empresarial, LEI del Conference Board, curva, diferenciales, bolsa. Cada uno da falsas alarmas; el valor
  está en la **difusión** (muchos a la vez) y en la confirmación por datos duros.

### A7. ETFs que siguen futuros y sus trampas
- **USO (petróleo WTI) y DBC (cesta de materias primas)** no tienen el contado: compran futuros y los renuevan. Con la
  curva de futuros en **contango** (futuro más caro que el contado) cada renovación pierde dinero («roll yield»
  negativo): USO puede perder aunque el petróleo suba o se quede quieto (2020: el WTI llegó a precio negativo y USO
  cambió de estructura). DBC elige vencimientos para mitigarlo pero no lo elimina. En **backwardation** el roll suma.
  Úsalos para coberturas tácticas de inflación/energía, no como inversión de años.
- **UUP (dólar)**: futuros del índice del dólar; gana el diferencial de tipos frente a las otras monedas (carry).
- **TLT/IEF/SHY/TIP**: no son futuros, son bonos; TIP protege de inflación sorpresa pero cae si suben los tipos reales.
- **GLD**: oro físico (sin roll). Sensible al tipo real y al dólar.
- **ETFs apalancados o inversos** (TQQQ, SQQQ, SH…): reajuste diario → se erosionan en mercados laterales; un inverso es
  una posición corta encubierta y un 3× es apalancamiento encubierto: van contra el espíritu del mandato aunque la
  guardia no los bloquee por símbolo. **No los uses.**
- **Productos de volatilidad** (VXX, UVXY): contango casi permanente, pierden casi siempre a largo plazo.

### A8. Opciones compradas como cobertura
- Comprar una **put** sobre SPY/QQQ limita la pérdida de la cartera por debajo del precio de ejercicio a cambio de la
  prima (pérdida máxima = la prima). Coste: el paso del tiempo (theta) y la volatilidad implícita (cara tras caídas,
  barata en calma: se compra seguro **antes** de necesitarlo).
- Práctica habitual: vencimientos de 3-6 meses, 5-10 % fuera de dinero, prima anual del orden de 1-3 % de la cartera;
  renovar antes de los últimos 30-45 días (theta acelera). Una **call** comprada da exposición alcista con pérdida
  acotada a la prima.
- Mandato: solo comprar para abrir y vender para cerrar. **Nada de spreads** (exigen vender una opción para abrir).
- **Cuidado con el vencimiento:** una opción en dinero al vencer se ejerce sola; una call ejercida compra 100 acciones
  por contrato y puede dejar el efectivo en negativo (apalancamiento, que el supervisor trata como límite duro).
  **Cierra (vende) las opciones antes del vencimiento.**
- Contratos de 100 acciones; precio límite por acción; liquidez: prefiere SPY/QQQ/IWM y vencimientos mensuales.

### A9. Disciplina
- Tamaño antes que acierto: ninguna idea debería poder llevar la cuenta al −35 %. Diversifica por factor de riesgo, no
  por número de símbolos.
- Costes y rotación: cada cambio cuesta; operar poco es una ventaja. Un día no cambia un régimen.
- Escribe qué te haría cambiar de opinión y respétalo (diario).

## B. Los modelos del proyecto: qué miden, cuánto aciertan y sus límites

Leyenda: **establecido** = pasó su prerregistro; **probable** = signo y robustez, no todos los criterios; **no
establecido**; **descriptivo** = no contrastado; **en vivo** = registro prospectivo sin veredicto todavía.

### B1. Régimen / clasificador (cuadrante y G/I) — `signal.regime`
- Qué es: reglas fijas (docs/PLAN.md «Marco de regímenes»; src/regime/classify.py). G = media de z de producción
  industrial, empleo, PIB y −Δparo; G↑ si G > 0 y sube a 6 m (Sahm ≥ 0,5 fuerza G↓). I = subyacente a 6 m y su
  aceleración. Cuadrantes: Goldilocks (G↑ I↓), Reflación (G↑ I↑), Estanflación (G↓ I↑), Deflación/recesión (G↓ I↓).
- Fiabilidad medida: coincide con la etiqueta de régimen en crecimiento el **68,9 %** (κ **0,394** < 0,40, no pasó su
  regla; docs/factors/prerreg_desarrollo_v0.md). El nowcast del pool de modelos **no bate a la persistencia** (Fase 3,
  «M0 sigue»; research/trial_log.md). Convertir el régimen en pesos (**V1-V3**) **no mejoró** frente al ajuste por
  volatilidad (P-DEV-FACT v0.1); **S1** (sectores por cuadrante) **no pasa**: queda en la mediana de los placebos,
  ratio de información 0,04 (docs/factors/S1_resultado_desarrollo.md).
- Límites: describe dónde se está con datos revisados y retrasos de 1-2 meses; no predice el siguiente cuadrante.

### B2. Atlas régimen → activos (INT-3, INT-3b/3d, INT-6, INT-14) — docs/int/ATLAS_regimenes.md
- Rentabilidades reales anuales, 14 países, 1870-2004, régimen con etiqueta EX POST (ventana centrada: no se conoce a
  tiempo). Con el régimen del año anterior la mayoría de efectos se encoge:
  - bolsa en estanflación **−8,7 pp/año** (establecido) → **−0,8** con el régimen conocido (desaparece);
  - bonos con inflación alta **−10,1 pp** (establecido) → **−3,4** conocido (el más sólido);
  - bonos en crecimiento bajo/desinflación **+7,9** (probable) → **+5,0** conocido; letras con inflación alta −7,7;
  - vivienda frente a bolsa con inflación alta **+6,2** (establecido, 10/14 países);
  - oro ↔ tipo real (INT-6 G2, establecido); en picos de volatilidad el **Tesoro protege y el oro no** (INT-14);
    tras crisis bancarias la vivienda es frágil (INT-14, probable).
- Uso: qué activo sufre en qué entorno (sobre todo inflación → bonos); **no** es una regla de timing.

### B3. Capas: ciclo de deuda, ciclo largo, liquidez, crédito — `signal.debt_cycle`, `long_cycle`, `liquidity`, `credit`
- Ciclo de deuda corto: fases por reglas (desapalancamiento, reflación, techo, endurecimiento, tardío, temprano) con
  curva, tipos y diferenciales (src/regime/classify.py); heurística documentada, **descriptiva**.
- Ciclo largo: banderas de deuda pública > 100 % y subiendo, déficit < −5 % sin recesión, intereses/ingresos, crédito
  privado/PIB: contexto de décadas, **descriptivo**.
- Liquidez: puntuación = media de z de (M2 − PIB), liquidez neta interanual, −tipo real 10 a, −NFCI; > 0,5 abundante,
  < −0,5 escasa. **Descriptiva**, no contrastada.
- Crédito: semáforo de 9-10 indicadores con umbrales fijos y escritos antes (Baa, HY OAS, NFCI, ANFCI, STLFSI, SLOOS,
  morosidad, TED, curva; src/regime/credit.py): rojo si ≥ 2 rojos o 1 rojo + 2 ámbar. **Descriptivo**; la prueba de
  crédito → recesión (INT-15) **no tenía potencia** y no se corrió. El panel de liquidez y crédito lo dice: «no es una
  señal ni da probabilidades, NO está validado».

### B4. E1 — P(entrar en recesión en 12 meses) — `research/int/e1_vivo.jsonl` (docs/int/E1_prerregistro_v1.md)
- Logit congelado con ≤ 2004, 16 países OCDE: modelo **A** (curva 10a−corto, Δ12 del tipo corto, producción industrial
  interanual, confianza empresarial) frente al listón **L** (solo curva). Registro mensual en vivo desde el origen
  **2026-11-30**; el contraste único es ΔAUC(A − L) cuando haya episodios suficientes (años).
- Fiabilidad: nace de INT-13 exploratorio (ΔAUC +0,167, **no pasó Holm**); por la maldición del ganador el efecto
  realista es ≈ +0,08. **Sin veredicto**: no validado fuera de muestra. Validador ✅ del ajuste y del registro
  (docs/validation/2026-11-05_E1_E1b_K1v.md). El fechado de recesiones va 2-3 trimestres tarde.
- Uso: probabilidad orientativa con pocos episodios detrás; no es un aviso de timing.

### B5. E1b — lo mismo a 6 meses (docs/int/E1b_6m_prerregistro_v1.md)
- Mismos modelos a 6 m. Declarado: a 3-6 meses **no hay potencia** (INT-8) y probablemente **nunca** llegue a veredicto
  útil; parte de lo que «anticipa» es ver una recesión ya empezada. Contexto, no señal.

### B6. K1v — auge de crédito → crisis bancaria (docs/int/K1_vivo_prerregistro_v1.md)
- Logit con Δ5 del crédito bancario/PIB (BIS) y años desde la última crisis; anual (datos del 4.º trimestre).
- Fiabilidad: en desarrollo ΔAUC **+0,113 [−0,007; +0,231]**, **no establecido** (INT-6 K1); evaluación solo con ≥ 20
  crisis nuevas (décadas). No citable en M1 (contexto).

### B7. INT-11 v3.1 — escenarios a 12 meses por país y activo — `signal.escenarios`, `research/int/int11_v3_hoy.json`
- Abanicos (p5…p95) de la rentabilidad REAL a 12 m de bolsa, bonos, letras, vivienda y oro, P(bolsa ≤ −20 %),
  P(inflación > 5 %) y `p_neg` (probabilidad de rentabilidad real negativa); motor estimado solo con JST ≤ 2004
  (14 países) y el estado OCDE en vivo; régimen suave (pesos por régimen).
- Fiabilidad medida (desarrollo, dejando cada país fuera; research/int/int11_v3_resultado.md): el p5-p95 contuvo lo
  ocurrido el **92,3 %** en bolsa, **90,8 %** bonos, **88,2 %** letras, **89,6 %** vivienda y oro (objetivo 90 %); la
  puerta pasó **por 0,1 pp**; en el corte temporal (< 1950 → 1950-2004) la bolsa solo **82,2 %** (los abanicos se
  quedan cortos fuera de época). **No confirmado fuera de muestra** (registro en vivo mensual desde nov-2026).
  Validador ⚠️: IC de P(inflación > 5 %) de anchura 0 en DEU/FIN (docs/validation/2026-10-31_int11v3.md).
- Uso: el **ancho** del rango y la asimetría (cuánto puede salir mal); la dirección del p50 apenas se separa de la
  historia. `p_neg` cerca de 35-40 % en bolsa es lo normal histórico, no una señal.

### B8. Diagnósticos automáticos — `obsidian/Diagnosticos/` (docs/panel/diagnosticos_v0.md, v1 activo)
- Cuando salta un disparador (movimiento ≥ 3 σ, ruptura de la media de 200 sesiones mantenida 3 días, cambio de
  régimen o de capa, dato macro sorpresa), Claude escribe hipótesis de causa con evidencia a favor y en contra.
- Fiabilidad: **descriptivo, ex post** («una explicación posterior siempre suena convincente»); separa datos de
  hipótesis. Úsalo para entender qué pasó, no para predecir.

### B9. Alertas de flujos — src/report/alertas.py (docs/panel/alertas_v1.md)
- Compras/ventas de directivos (Form 4), participaciones ≥ 5 % (13D/13G), recompras (XBRL), volumen anormal, de las
  acciones de «Mis activos». Validador ⚠️: **las cifras coinciden con la fuente** (docs/validation/2026-11-17_alertas_v1.md).
- Fiabilidad como señal: **no contrastada** (descriptiva). Un 13G pasivo o una venta programada (10b5-1) dicen poco.

### B10. Fundamentales XBRL — `~/financial_archive/sec_fundamentales/hechos.json`
- Ingresos, beneficio, resultado operativo y BPA trimestrales de la SEC (solo las empresas de «Mis activos»). Datos
  oficiales, con fecha de presentación; no es un modelo. Ojo con revisiones y con trimestres fiscales distintos.

### B11. Termómetro de recesión — `signal.termometro` (docs/int/TERMOMETRO_diseno_v1.md)
- Logit anual de INT-4 (curva, difusión de curvas invertidas, Δ tipo real, bolsa real, crédito) leído en mensual.
- Fiabilidad: **T1 (entrar en recesión) NO pasó** su puerta → solo se muestran los indicadores; **T2 (salir)** pasó
  con solo 31 filas / 22 episodios: «léase la banda, no el porcentaje» (docs/validation/2026-10-29_termometro.md).
  INT-4 a nivel anual: AUC ≈ 0,73 con curva + difusión + bolsa. **Informativo, no es una señal de cartera.**

### B12. Nowcast de recesión INT-8b — `signal.nowcast` (docs/int/INT8b_nowcast.md)
- Banda (bajo/medio/alto/muy alto) de 6 indicadores conocidos (curva, difusión de curvas, bolsa real, crédito,
  difusión de la producción industrial, regla de Sahm) en percentiles frente a 1960-2004 de cada país.
- Fiabilidad: **descriptivo**; nunca una probabilidad; INT-8 midió que a 3-6 meses **no hay potencia** para validarlo.

### B13. Carteras de referencia (lo que te compite)
- **B0** 70/15/15 estática; **B1** ajuste por volatilidad (en desarrollo recortó volatilidad 14,4 → 12,7 % y caída
  −42 → −33 % frente a la estática); **B1′** volatilidad con HAR diario (INT-12: −34 % de QLIKE frente a la de B1,
  Validador ✅); **D1** tendencia diaria (desarrollo pasa; sensibilidad del Validador Sharpe 0,64 frente a 0,42 del
  listón; docs/factors/D1_resultado_desarrollo.md). Lo que mejor ha funcionado en el proyecto es **gestionar el riesgo
  (volatilidad, tendencia)**, no predecir el régimen.

## C. Cómo pesar los modelos (resumen)
1. Con fiabilidad medida y útil: atlas inflación → bonos; volatilidad (HAR) y tendencia (D1) como gestión del riesgo;
   rangos de INT-11 para dimensionar el peor caso.
2. Contexto razonable sin validar: crédito, liquidez, curva, ciclo de deuda; E1 (probabilidad orientativa, sin veredicto).
3. Descriptivo puro: cuadrante para elegir sectores (S1 falló), diagnósticos, alertas, termómetro T1, nowcast, E1b, K1v.
4. Ante conflicto, manda el riesgo: si varias capas empeoran a la vez (crédito rojo, curva re-empinándose tras invertir,
  Sahm, bolsa bajo su media de 200), reduce exposición; un solo indicador no basta.
