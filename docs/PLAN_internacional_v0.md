---
documento: Plan de la fase internacional del modelo macro (línea B ampliada)
version: 0.1 APROBADA por el usuario (2026-10-26, "dale, vamos a ello"; decisiones 1-4 de §6 con las opciones recomendadas)
estado: APROBADO. En curso: INT-0. Nada corrido. Sustituye al enfoque "solo EE. UU." de la línea B.
depende_de: docs/PLAN.md § "Reconducción del proyecto (2026-10-26)"
---

# Modelo macro internacional — plan v0.1 (borrador)

## Estado honesto
1. **El nowcast no mejora a la persistencia:** en EE. UU. (Fase 3) ningún modelo bate a M0, y el fechado mensual de recesiones no pasó su puerta.
2. **El forecast de recesiones a un año sí funciona, moderado** (INT-4): la entrada es sólida (AUC ≈ 0,73, curva + difusión + bolsa) y la salida es más justa (≈ +0,19 de AUC, sobre todo por la bolsa).
3. **La inflación no se anticipa** (T3/T4 no establecidos).
4. **Lo útil ahora:** el atlas (`docs/int/ATLAS_regimenes.md`: qué activos y cuándo) y el termómetro de recesión como herramienta informativa.

## 0. Objetivo (palabras del usuario, 26-oct)
1. Con los datos macro, **saber en qué régimen estamos** y **qué activos son más ventajosos en él**.
2. Más adelante, **forecast**: qué macro viene y qué hacer.
3. Encontrar **indicadores que se adelanten** al mercado.

**Por qué internacional:** con EE. UU. solo hay 6 recesiones entre 1963 y 2004 → no hay potencia para nada de lo
anterior (ver `docs/lineaB/diseno_v0.md`). Con 18 países y 150 años hay **cientos de episodios**. Es la palanca que usa
la literatura profesional (Jordà-Schularick-Taylor; Ilmanen; Neville et al., "The Best Strategies for Inflationary Times").

## 1. Qué datos hay (auditoría del 26-oct)

| bloque | fuente | cobertura | frecuencia | point-in-time | licencia |
|---|---|---|---|---|---|
| **Macro + rentabilidades largas** | JST Macrohistory R6 | **18 países, 1870-2020**: PIB, IPC, paro, salarios, crédito, hipotecas, deuda, cuenta corriente, crisis; rentabilidad total de **bolsa, bonos, letras y vivienda** (16 países) | **anual** | **no** (datos revisados) | **CC BY-NC-SA** (no comercial) |
| Bolsa por país | OCDE (índice de precios) | 21 países, desde ~1959 | mensual | no | CC BY 4.0 |
| Bolsa por país (rentabilidad) | AQR (mercado por país) | ~25 países, desde 1986 | mensual | no | sin redistribución |
| Tipos | OCDE (largo, 3 m, interbancario), BIS (oficial, 49 países) | ~20 países desde 1953-1982 | mensual | no | CC BY / BIS |
| Ciclo | OCDE CLI, confianza empresarial y del consumidor | 17 CLI desde 1955-1975; 50 BCI | mensual | no | CC BY 4.0 |
| Paro, IPC | OCDE paro (15 países), FMI IFS IPC/divisa (22) | desde 1955-1991 | mensual | no | CC BY / FMI |
| Crédito | BIS crédito total y brecha de crédito | 40+ países desde 1960-1995 | trimestral | no | BIS |
| Factores | French internacional (8 regiones), AQR | desde 1990 / 1986 | mensual, diario | no | investigación, sin redistribuir |
| EE. UU. en tiempo real | ALFRED, base PIT v0.4, etiqueta v1.1 | 1950-hoy | mensual | **sí** | — |

**Huecos a cubrir (por prioridad):**
1. **Producción industrial y empleo mensuales por país** (OCDE MEI): sin ellos no hay régimen mensual fuera de EE. UU.
2. **Datos en tiempo real internacionales:** base de revisiones de la OCDE (MEI Original Release Data and Revisions,
   vintages desde 1999, gratuita). Sin ella, todo lo internacional es con datos revisados (declarado).
3. **Rentabilidad total mensual de bonos por país** (se puede construir a partir de los tipos largos, como el Bund).
4. **Fechado de recesiones por país** (algoritmo Bry-Boschan sobre PIB/IP; ECRI tiene licencia restrictiva).
5. Materias primas y oro largos (ya: Banco Mundial 1960+, MeasuringWorth anual).

## 2. Arquitectura (cuatro piezas, cada una con su puerta)

### Pieza 1 — Régimen por país (nowcast, describe "dónde estamos")
- Mismos ejes que la etiqueta de EE. UU.: **crecimiento** frente a tendencia y **inflación** (nivel y dirección) → 4
  cuadrantes, más una capa de **recesión** y otra de **crisis financiera** (JST).
- Dos frecuencias: **anual** 1870-2020 (JST, para medir) y **mensual** 1960-hoy (OCDE, para operar).
- Etiqueta ex post por país con la metodología de la v1.1 (probabilística, con frontera), validada contra las recesiones
  conocidas de cada país.

### Pieza 2 — Mapa régimen → activos ("qué activos son más ventajosos")
- **Modelo jerárquico bayesiano** (agregación parcial entre países): rentabilidad real, volatilidad y caída de cada clase
  (bolsa, bonos, letras, vivienda, oro, materias primas) en cada régimen; cada país toma prestada fuerza de los demás y
  los efectos que no se repiten entre países se encogen hacia cero.
- **Priors económicos explícitos** escritos ANTES de mirar (p. ej., los bonos protegen en recesiones desinflacionistas;
  en estanflación sufren bolsa y bonos; el oro y las materias primas protegen en shocks de inflación). Los datos los
  confirman o los corrigen.
- Resultados con **intervalos**, en términos de riesgo y rentabilidad, contados por **país-episodio**, no por año.

### Pieza 3 — Forecast de riesgo ("qué macro viene", 3-12 meses)
- Pregunta: probabilidad de **recesión, caída fuerte de bolsa o subida de volatilidad** en 3, 6 y 12 meses.
- **Panel de países**, pocos indicadores fijados de antemano con mecanismo conocido: curva de tipos, crecimiento del
  crédito / brecha de crédito (Schularick-Taylor), CLI, momentum de bolsa, vivienda, tipo real.
- **"Indicadores que no se ven":** búsqueda disciplinada, no minería: candidatos con mecanismo, prerregistrados, y una
  cuota fija de exploración cuyos hallazgos solo cuentan si sobreviven en países y épocas que no se usaron para
  encontrarlos.

### Pieza 4 — De la señal a la cartera
- La señal solo entra en la cartera como **B2 en sombra** frente a **B1** (paper trading), tras prerregistro aprobado
  por el usuario. B2 nunca sustituye a B1 sin decisión registrada.

### Más adelante — nowcast de alta frecuencia
Estimar el dato macro (empleo, PIB, inflación) antes de que se publique con series diarias y semanales: la ventaja
realista de "adelantarse", de semanas. Fase aparte.

## 3. Estándar profesional (lo que se mantiene y lo que se añade)
- **Validación en dos ejes:** fuera de muestra en el tiempo (**periodo bloqueado ≥ 2005-01 para todos los países**;
  JST llega a 2020 → 2005-2020 queda para la evaluación única) **y entre países** (dejar un país fuera cada vez).
- Inferencia con **errores agrupados por año** (las recesiones globales no son independientes: 1974, 1980-82, 1991, 2001,
  2008-09).
- **Cálculo de potencia antes de construir** cada pieza, con episodios efectivos.
- **Prerregistro** de cada pieza; registro de todas las pruebas; Deflated Sharpe / corrección por comparaciones múltiples.
- **Listones ingenuos** siempre: media incondicional, persistencia, B1.
- **Validador independiente** (agente) en cada hito, sin haber escrito el código que revisa.
- **Ficha de cada modelo** (datos, supuestos, límites, contaminación declarada).
- **Contaminación declarada:** sabemos lo que pasó en 2008, en la crisis del euro y en 2020-22; la literatura de crédito y
  crisis es de 2012 en adelante.

## 4. Fases y puertas (orden propuesto)

| fase | qué | puerta para seguir |
|---|---|---|
| **INT-0** | Auditoría y armonización del panel (JST + OCDE + BIS + FMI); cubrir huecos 1-4 | Validador ✅ de datos; cobertura por país y década publicada |
| **INT-1** | Régimen por país (anual y mensual) + fechado de recesiones | concordancia con recesiones conocidas; Validador ✅ |
| **INT-2** | Cálculo de potencia del panel (episodios efectivos con agrupación) | si no hay potencia para la pieza 2 o 3, se dice y se replantea |
| **INT-3** | Mapa régimen → activos (jerárquico bayesiano) | prerregistro aprobado → desarrollo ≤ 2004 → usuario decide si gasta 2005-2020 |
| **INT-4** | Forecast de riesgo (panel) | ídem |
| **INT-5** | B2 en sombra frente a B1 | prerregistro aprobado; nunca sustituye a B1 sin decisión |

La línea A (B0/B1 en paper trading) sigue en paralelo, sin cambios.

## 5. Expectativas honestas
- **Pieza 2 (régimen → activos):** con cientos de país-episodios **sí debería haber potencia** para los efectos grandes y
  conocidos (estanflación frente a recesión desinflacionista, papel de los bonos y del oro). Los efectos finos no.
- **Pieza 3 (forecast):** la literatura da AUC de ≈ 0,7-0,8 para recesión a 12 meses con curva y crédito. Útil para
  gestionar riesgo; **no** es una máquina de batir al mercado.
- **"Adelantarse al mercado":** la ventaja realista está en la disciplina (reducir riesgo antes) y en el nowcast de alta
  frecuencia, no en indicadores secretos. Cualquier indicador "nuevo" tiene que sobrevivir fuera de muestra en países que
  no se usaron para encontrarlo.
- **Limitaciones:** JST es anual y revisado; la parte mensual internacional empieza en los 60-80 y no tiene tiempo real
  antes de 1999; JST es no comercial.

## 6. Decisiones pendientes del usuario
1. Aprobar el enfoque (piezas 1-4, fases INT-0 a INT-5).
2. Periodo bloqueado internacional: **≥ 2005-01 para todos los países** (recomendado, coherente con EE. UU.).
3. Uso no comercial asumido (JST, AQR, French); si algún día se comercializa, habrá que sustituir fuentes.
4. Empezar por INT-0 (datos), con el Validador al final.
