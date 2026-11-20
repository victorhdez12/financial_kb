---
documento: Supervisor de carteras — revisión diaria de B0, B1, B1′, D1 (solo papel), C1, M1 y A1 (Alpaca PAPER)
version: 1.1 (2026-11-20) — mandato supervisor-v2: A1, reasignación de cuentas y vigía macro sobre C1/M1/A1 (§5).
  1.0 APROBADA (2026-11-19) — diario, con poder de parada (decisión del usuario)
estado: CONSTRUIDO (2026-11-19, rama del Constructor; pendiente del Validador), NO instalado: falta cargar el plist
  (`scripts/launchd/com.financialkb.supervisor.plist`, 8:00 diario). Piezas en §4.
---

# Supervisor de carteras

## 0. Qué es
Un agente distinto de los gestores, que **nunca opera**. Cada mañana (8:00 Madrid, tras la diaria) revisa todas las
carteras y escribe `obsidian/Carteras/Supervisor/AAAA-MM-DD.md` (fuera de git). Coste: suscripción del usuario.

## 1. Qué revisa
1. **Cumplimiento:** B0/B1/B1′/D1 — que las órdenes coinciden con la decisión registrada y su regla; C1/M1 — que
   respetan el mandato (M1: cada orden cita modelos que existen y dicen lo que la orden afirma).
2. **Riesgo:** caída desde máximo, concentración por activo/sector, efectivo, exposición a opciones y cripto.
3. **Coherencia** (C1/M1): lo que el diario dice frente a lo que la cuenta hizo; datos citados que no existen.
4. **Ejecución:** órdenes sin ejecutar, deslizamiento anómalo, órdenes abiertas viejas.
5. **Salud:** registros que faltan, tareas de launchd que no corrieron, cupo de la suscripción agotado.

## 2. Poder de parada (límites duros, en código; el agente no decide si se superan)
Python calcula los límites y, si se supera alguno, crea el fichero de parada de esa cartera
(`research/paper/<CARTERA>_PARADA`, fuera de git) y avisa al usuario (notificación de macOS + línea en
`Actualizaciones.md`):
- caída desde máximo ≤ −35 %;
- orden ejecutada fuera de mandato (apalancamiento, corto, opción vendida para abrir) que la guardia no debió dejar
  pasar;
- más de 3 días seguidos con error en el ciclo de la cartera.
El agente supervisor **explica** la parada en su informe; quitarla es decisión del usuario (borrar el fichero).
B0/B1/B1′/D1 no tienen parada propia hoy: el supervisor solo avisa (cambiarlo exige aprobación).

## 3. Seguridad
Solo lectura (Read/Grep/Glob) del repo, el panel, los registros y `~/financial_archive/` salvo `config/`; escritura
solo en su informe. Sin Bash, sin red de Alpaca: los datos de las cuentas los prepara Python en un paquete.

## 4. Construcción (2026-11-19)
| pieza | dónde |
|---|---|
| paquete, límites duros, paradas y avisos | `src/paper/supervisor.py`: cuentas con el cliente de `src/broker/alpaca.py` (perfiles B0/B1/B1P/D1/C1/M1), registros de `research/paper/`, espejo, diarios de `obsidian/Carteras/`, logs, salud; límites (§2) en código; parada = el mismo fichero que miran los ciclos (`C1_PARADA`, `M1_PARADA`); aviso = notificación + línea en `Actualizaciones.md` |
| mandato | `config/supervisor_mandato_v1.md` (+ documento de conocimiento) |
| agente | `src/paper/agente.py`, rol `supervisor` (lee además `research/paper/`, `logs`, `alpaca`, `c1`, `m1`); salida JSON → Python escribe `obsidian/Carteras/Supervisor/AAAA-MM-DD.md` |
| automatización (no instalada) | `scripts/supervisor.sh` + `scripts/launchd/com.financialkb.supervisor.plist` (8:00, todos los días) |
Declarado: «orden ejecutada fuera de mandato» se mide por su efecto en la cuenta (posición corta, opción vendida, efectivo
negativo); «> 3 días seguidos con error» = últimas líneas seguidas del registro con Claude fallido o salida inválida.
**Vigía macro** (petición del usuario, 19-nov; misma ejecución y paquete): para B1 y D1 (carteras de regla fija con
cuenta) el agente escribe qué dicen hoy los modelos macro (régimen, crédito, liquidez, E1, INT-11, diagnósticos: `modelos`
del paquete, los mismos que recibe M1) para lo que tiene cada una, riesgos que la regla no ve y qué haría un gestor
macro. **No opera ni cambia nada de esas carteras.** Si marca `aviso_usuario`, notificación + línea en
`Actualizaciones.md`. Cada día y cartera, una línea en `~/financial_archive/supervisor/vigia_avisos.jsonl` (fuera de
git) para medir después si los avisos acertaban (evaluación por definir antes de mirar resultados).
Ensayo (`python -m src.paper.supervisor --simulada`): cuentas ficticias, no crea paradas ni avisa (dice qué haría).

## 5. Cambios v1.1 (2026-11-20, decisión del usuario: las 3 cuentas las gestiona el agente)
- Carteras: B0, B1, B1′ y D1 son **solo papel** (registros teóricos, sin cuenta ni órdenes; en el paquete salen como
  `sin_cuenta: solo papel`); C1 (…4JGR, antes B1), M1 (…ZFJX) y A1 (…X9F9, antes B0 y D1) tienen cuenta y parada.
  Si aparece una orden nueva del espejo en alguna cuenta, es grave (el espejo ya no debe operar).
- **Vigía macro** sobre las tres cuentas gestionadas (C1, M1, A1) en vez de B1/D1: qué dicen hoy los modelos macro
  para lo que tiene cada una, riesgos que su gestor no ve y qué haría un gestor macro; sigue sin operar ni proponer
  órdenes; avisos en `vigia_avisos.jsonl` (fuera de git).
- Límites duros de A1, además de los generales (en código, con parada `A1_PARADA`): opciones o cripto en la cuenta
  (fuera de mandato), y un valor > 15 % del valor de la cuenta (10 % del mandato + 5 pp de deriva por precio; no
  cuentan el colchón SGOV/BIL/SHV/SHY/IEI ni los ETFs heredados URTH/GLD).
- Mandato `config/supervisor_mandato_v2.md` (`supervisor-v2`); el v1 queda en el repo como histórico.
