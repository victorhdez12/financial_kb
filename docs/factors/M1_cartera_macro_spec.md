---
documento: M1 «Claude gestor macro» — Claude gestiona una cartera basándose en los modelos macro del proyecto (Alpaca PAPER)
version: 1.0 APROBADA (2026-11-19) — mandato m1-v1; cambiarlo = nueva versión declarada. Sustituye al borrador 0.1
  (regla mecánica), que queda como **sombra teórica** (§4).
estado: diseño; se construye sobre la infraestructura de C1 (paquete, guardia, registro) tras su validación.
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
