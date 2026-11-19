---
documento: M1 «Claude gestor macro» — Claude gestiona una cartera basándose en los modelos macro del proyecto (Alpaca PAPER)
version: 1.1 APROBADA (2026-11-19) — mandato m1-v1 + modo agente (§7); cambiarlo = nueva versión declarada. Sustituye al borrador 0.1
  (regla mecánica), que queda como **sombra teórica** (§4).
estado: CONSTRUIDO (2026-11-19, rama del Constructor; pendiente del Validador), NO activado: faltan claves `_M1`,
  `research/paper/M1_ACTIVO` y cargar el plist. Piezas en §8.
---

# M1: Claude como gestor, obligado a basarse en los modelos macro

## 0. Qué es y qué no es
- Decisión del usuario (19-nov): «tú eres el manager, pero quiero que lo bases en los modelos para ver si se pueden
  usar». Claude decide **cuánta bolsa y qué contenido** (ETFs, sectores, acciones, ETFs tipo futuros), cada día, pero
  cada decisión debe **apoyarse en las salidas de los modelos** y citarlas.
- Compite con: **C1** (Claude libre, sin obligación de usar los modelos), **D1** (regla de precio, sin macro), y
  B0/B1/B1′. La comparación M1 vs C1 dice si **anclarse a los modelos** ayuda a un gestor; M1 vs su sombra (§4) dice
  si el **criterio** añade algo a una aplicación mecánica de los modelos.
- **Solo hacia delante**; previo escéptico declarado (V1-V3 y S1 no ganaron con historia ≤ 2004).

## 1. Ciclo diario (misma infraestructura que C1)
- 20:45 Madrid (mercado abierto). Paquete del día sin IA + `claude -p` con el **mandato m1-v1** → JSON de órdenes →
  **guardia de C1** (sin apalancamiento, sin cortos, opciones solo compradas, ≤ 20 órdenes, `M1_PARADA`) → cuenta PAPER
  del perfil `M1` → registro `research/paper/decisiones_m1.jsonl` (commit y push el mismo día; exige `M1_ACTIVO`).
- Puede no operar ningún día.

## 2. Mandato m1-v1 (texto fijo en `config/m1_mandato_v1.md`)
1. Objetivo: máxima rentabilidad ajustada por riesgo a largo plazo; caída máxima tolerable −35 %.
2. **Obligación de base:** cada orden (y la decisión de no operar) debe citar qué salidas de los modelos la justifican,
   de esta lista: cuadrante y G/I, crédito, liquidez, ciclo de deuda, P(recesión) de E1, escenarios de INT-11 por
   activo, diagnósticos de la semana, alertas de flujos, fundamentales XBRL de las acciones. Sin cita → la guardia la
   rechaza.
3. Debe declarar cada día, en una línea por modelo, si **le hace caso o no y por qué** (esto es lo que mide qué
   modelos usa un gestor y cuáles descarta).
4. Universo: lo que Alpaca permita negociar (acciones, ETFs incluidos los que siguen futuros —DBC, USO, UUP, TLT…—,
   opciones compradas). Sin cortos ni apalancamiento.
5. Recibe cada día, como referencia, la **cartera sombra** (§4); puede desviarse de ella explicando por qué.

## 3. Paquete del día (además del de C1)
Salidas completas de los modelos con su fecha de publicación (régimen y capas, E1, INT-11, K1v si hay emisión,
diagnósticos, alertas), fundamentales XBRL de las acciones en cartera y de las candidatas que pida, y la cartera
sombra con sus pesos.

## 4. Sombra teórica (la regla mecánica del borrador 0.1)
La regla del borrador 0.1 (bolsa 60 % ± ajustes por crédito, E1, liquidez, INT-11 y G; sectores del cuadrante;
8 acciones; resto por inflación) se calcula cada día **sin cuenta** (valoración teórica con cierres y costes de 5 pb)
y se registra en `research/paper/decisiones_m1_sombra.jsonl`. Sirve de listón y de referencia para Claude.

## 5. Evaluación
- Tabla «Competición»: M1, C1, D1, B0, B1, B1′ y la sombra.
- **Uso de modelos:** por cada modelo, % de días en que M1 le hizo caso, y rentabilidad de las decisiones apoyadas en
  él (descriptivo; muchos años para concluir).
- Cambio de modelo de Claude: se anota (otro gestor desde ese día).

## 6. Requisitos
Tercera cuenta paper del 2.º usuario de Alpaca, claves `_M1`.

## 7. Modo agente (decisión del usuario 19-nov, v1.1)
- M1 no recibe solo el paquete: es un **agente gestor especializado** (`claude -p` con herramientas **solo de lectura**:
  Read/Grep/Glob) que lee lo mismo que el usuario —panel (`~/financial_archive/panel/index.html`), índice y notas de
  Obsidian (`obsidian/`), informes y diagnósticos— y explora los datos (`~/financial_archive/` salvo `config/`).
  **Denegado:** `~/financial_archive/config/**`, `research/paper/**` (salvo leer su propio registro), Bash, red de
  Alpaca. Escritura solo en su diario.
- **Especialización:** documento de conocimiento versionado `config/gestor_conocimiento_v1.md` (ciclo, crédito,
  liquidez, curva, indicadores, ETFs que siguen futuros, qué mide cada modelo del proyecto y sus límites).
- **Diario** en Obsidian `obsidian/Carteras/M1/AAAA-MM-DD.md` (fuera de git, como los diagnósticos): qué vio, qué
  decidió y por qué, modelo por modelo. Las órdenes siguen pasando por la guardia de C1; el registro inmutable sigue en
  `research/paper/decisiones_m1.jsonl`.
- Coste: lo paga la **suscripción del usuario** (decisión 19-nov). Límite por ejecución: 15 min; si se agota el cupo
  de la suscripción, ese día no opera y se anota.

## 8. Construcción (2026-11-19)
| pieza | dónde |
|---|---|
| ciclo (el de C1 con la cartera M1) y registro | `src/paper/m1.py` → `research/paper/decisiones_m1.jsonl` (una línea por día, con `uso_modelos`; exige `M1_ACTIVO`, árbol limpio, claves `_M1`, mercado abierto; commit y push) |
| paquete (§3) | `src/paper/m1_paquete.py`: paquete de C1 + `modelos` (salida y fecha de publicación de cada uno) + `modelos_disponibles` + `sombra` + cierres del universo de la sombra |
| mandato `m1-v1` (§2) | `config/m1_mandato_v1.md` + `config/gestor_conocimiento_v1.md` (system prompt; sha256 de los dos en el registro) |
| guardia (§1-§2) | `src/broker/m1_guardia.py` = guardia de C1 + citas: orden sin cita válida (modelo de la lista y con salida hoy, con `dice`) → rechazada; no operar sin `citas_no_operar` válidas, `declaracion_modelos` sin los 9 modelos una vez, o «si» a un modelo sin salida → salida inválida (no opera). Botón `research/paper/M1_PARADA` |
| sombra (§4) | `src/paper/m1_sombra.py` (regla del borrador 0.1; acciones `config/m1_acciones_v1.json`; sectores del mapa de S1) → `research/paper/decisiones_m1_sombra.jsonl`, en el mismo commit que M1 |
| agente (§7) | `src/paper/agente.py` (rol M1; ver C1 §8); diario `obsidian/Carteras/M1/AAAA-MM-DD.md`; no puede leer el de C1 |
| automatización (no instalada) | `scripts/m1_gestor.sh` + `scripts/launchd/com.financialkb.m1.plist` (20:45, lun-vie; espera a que acabe C1) |
| evaluación (§5) | `src/report/panel_competicion.py`: filas M1 y «M1 · sombra teórica» y tabla «uso de modelos» |
Declarado (lo que la spec no fijaba):
- Sombra: entradas del último signal semanal (`regime.quadrant/G_state/I_state`, `credit.light`, `liquidity.state`,
  INT-11 `paises.USA.abanicos.bolsa.p_neg`) y E1 = `p_A` de EE. UU. del último origen; sin dato → esa entrada no
  ajusta. La liquidez «holgada» del borrador es la «abundante» del clasificador. Ejecución teórica al cierre del día de
  la decisión, valorada con sesiones completas (al día siguiente); cierres Alpaca ajustados → archivo → Yahoo.
- Acciones de la sombra: las 2 mayores por capitalización de cada sector según el conocimiento del Constructor
  (lista declarada, no medida; revisión en enero).
- E1 llega a M1 aunque su prerregistro dice que no se muestra en el reporte: lo pide esta spec (aprobada); a decidir
  por el Validador/usuario si eso contamina E1 (no cambia sus predicciones congeladas).
