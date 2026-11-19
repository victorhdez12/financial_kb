---
documento: Supervisor de carteras — revisión diaria de B0, B1, B1′, D1, C1 y M1 (Alpaca PAPER)
version: 1.0 APROBADA (2026-11-19) — diario, con poder de parada (decisión del usuario)
estado: diseño; se construye junto con el modo agente de C1/M1.
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
