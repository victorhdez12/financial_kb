---
documento: C1 «Claude gestor» — cartera discrecional diaria gestionada por un agente, en Alpaca PAPER
version: 1.0 APROBADA (2026-11-19) — mandato v1; cambiarlo = nueva versión declarada
estado: CONSTRUIDO (2026-11-19, rama del Constructor; pendiente del Validador), NO activado: faltan claves `_C1`,
  `research/paper/C1_ACTIVO` y cargar el plist. Piezas en §6.
---

# C1: Claude como gestor diario (experimento hacia delante)

## 0. Qué es y qué no es
- Decisión del usuario (19-nov): un agente que gestiona una cartera **cada día**, con libertad «dentro de la cuenta»:
  cualquier activo que Alpaca permita (acciones, ETFs, opciones, cripto), **sin cortos y sin apalancamiento**.
- **No se puede probar con historia:** el modelo ya conoce lo que pasó (sesgo de anticipación). Solo cuenta lo que haga
  **desde el primer día en vivo**, con cada decisión registrada y commiteada con fecha antes de conocer el resultado.
- Compite en la misma tabla que B0, B1, B1′ y D1. Mismo aviso: años, no meses, para separar habilidad de suerte.

## 1. Cómo decide (un ciclo al día)
1. **20:30 Madrid** (14:30 Nueva York, mercado abierto), launchd lanza `scripts/c1_gestor.sh`.
2. Python arma el **paquete del día** (sin IA): posiciones y efectivo de la cuenta C1, precios, régimen y capas,
   alertas, diagnósticos de la semana, panel resumido, y el **diario de C1** (sus decisiones y razones anteriores).
3. `claude -p` con un **mandato fijo versionado** (§2) lee el paquete y devuelve **solo un JSON** de órdenes con su razón
   y una nota corta para el diario. **No tiene claves, ni Bash, ni acceso a la red de Alpaca.**
4. Python **valida** el JSON con la guardia (§3); lo que no cumple se rechaza y se anota. Lo válido se envía a la cuenta
   PAPER de C1 y se apuntan las ejecuciones.
5. Se registra todo en `research/paper/decisiones_c1.jsonl` (paquete resumido + hash del paquete completo, modelo y
   versión del mandato, órdenes propuestas, rechazadas y enviadas) y se **commitea y sube el mismo día**.

## 2. Mandato (texto fijo, en el repo; cambiarlo = nueva versión declarada)
- Objetivo: **máxima rentabilidad ajustada por riesgo** (Sharpe) a largo plazo, con una caída máxima tolerable del
  **−35 %** (la misma tolerancia que el usuario declaró para su cartera).
- Puede no operar ningún día. Debe explicar cada orden en 1-3 frases y decir qué le haría cambiar de opinión.
- Universo: lo que Alpaca permita negociar en la cuenta paper.

## 3. Guardia en código (no depende del modelo; tests)
- Solo `paper-api` (igual que el resto: el endpoint real se rechaza siempre).
- **Sin apalancamiento:** las compras no superan el efectivo disponible (se ignora el poder de compra 2× de Alpaca).
- **Sin cortos:** no se vende más de lo que hay en cartera.
- **Opciones:** solo comprar para abrir y vender para cerrar (calls y puts compradas); nada de vender opciones al
  descubierto. Prima total en opciones ≤ efectivo disponible (sin margen).
- Máximo **20 órdenes al día**; símbolos que Alpaca marque como no negociables, fuera.
- Si el JSON no es válido o Claude falla o tarda más de 10 min: ese día **no opera** y se anota.
- Botón de parada: `research/paper/C1_PARADA` (si existe, no opera).

## 4. Evaluación
- Tabla «Competición» en el panel: rentabilidad, volatilidad, Sharpe, caída máxima, rotación, costes y nº de
  operaciones de B0, B1, B1′, D1 y C1 desde el inicio común.
- Cuando cambie el modelo de Claude, se anota en el registro (es otro gestor a partir de ese día).
- Coste: un `claude -p` al día (≈ 2-10 min); se mide y aparece en la tabla.

## 5. Requisitos del usuario
- Segundo usuario de Alpaca (otro correo) con cuentas paper para **D1** y **C1**; claves en `alpaca.env` con
  sufijos `_D1` y `_C1` (el código distingue el usuario por las claves, no hace falta nada más).

## 6. Construcción (2026-11-19)
| pieza | dónde |
|---|---|
| paquete del día (sin IA, con hash) | `src/paper/c1_paquete.py` |
| mandato `c1-v1` y formato JSON de salida | `config/c1_mandato_v1.md` (su sha256 va en cada línea del registro) |
| explicador | `scripts/c1_gestor.sh explicar DIR`: `claude -p --restricted --tools "" --strict-mcp-config --output-format json`, mandato como system prompt, paquete por stdin, entorno mínimo sin `ALPACA_*`, carpeta fuera del repo; plazo 10 min desde `src/paper/c1.py` |
| guardia (§3) | `src/broker/c1_guardia.py` (tests `tests/test_c1_guardia.py`) |
| ciclo, ejecución y registro | `src/paper/c1.py` → `research/paper/decisiones_c1.jsonl` (una línea por día; exige `C1_ACTIVO`, árbol limpio, claves `_C1`, mercado abierto; commit y push) |
| automatización (no instalada) | `scripts/c1_gestor.sh` + `scripts/launchd/com.financialkb.c1.plist` (20:30, lun-vie) |
| Competición | `src/report/panel_competicion.py`, en «Mi cartera» |
- Ensayo (sin registrar): `.venv/bin/python -m src.paper.c1 [--simulada]` guarda paquete, prompt, salida y línea en
  `~/financial_archive/c1/ensayos/`. Sin claves de C1: cuenta ficticia de 100 000 $ y solo acciones/ETFs de «Mis
  activos» validables (precio = cierre del warehouse).
- Declarado: la salida se admite también envuelta en un único bloque ```json; las compras de mercado se estiman al
  precio de referencia + 1 %; las ventas del día no liberan efectivo; >20 órdenes = ese día no opera.
