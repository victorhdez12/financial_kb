# Actualización automática

Desde el 2026-10-13 el proyecto se actualiza solo en el Mac con **launchd** (no en la nube: los datos viven en `~/financial_archive`).
El proyecto está en `~/Proyectos/financial_kb` (fuera del Escritorio: macOS bloquea a las tareas programadas leer carpetas protegidas).

| Tarea | Cuándo | Qué hace (`scripts/actualizar.sh`) |
|---|---|---|
| `com.financialkb.diario` | lun-sáb 7:30 | `make daily`: fuentes diarias (`INGEST_DAILY` del Makefile: fred_extended, fed_yieldcurve, us_liquidity, nyfed_repo, ecb) + warehouse + régimen |
| `com.financialkb.semanal` | domingo 7:00 | `make semanal`: todas las fuentes (`INGEST`) + warehouse + régimen + auditoría + reporte semanal en `obsidian/Reports/` |

- Si el Mac está apagado o dormido a esa hora, launchd la lanza al despertar.
- Resultado de cada ejecución: una línea en `obsidian/Proyecto/Actualizaciones.md` (estado, duración, fuentes con fallo, críticas de la auditoría, régimen) y el log en `~/financial_archive/logs/` (se borran a los 60 días).
- Si alguna fuente falla o la auditoría tiene críticas: notificación de macOS. Las fuentes que fallan no paran el resto (se queda el último dato bueno).
- No hace commits (los datos no van a git).

## Comandos
```
scripts/actualizar.sh diario      # a mano, igual que la tarea
scripts/actualizar.sh semanal
launchctl print gui/$(id -u)/com.financialkb.diario | grep -E "state|last exit"
launchctl kickstart gui/$(id -u)/com.financialkb.diario       # lanzarla ya
# instalar / desinstalar
cp scripts/launchd/com.financialkb.*.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.financialkb.diario.plist
launchctl bootout   gui/$(id -u) ~/Library/LaunchAgents/com.financialkb.diario.plist
```

## Fuente nueva
Añadirla a `INGEST` (y a `INGEST_DAILY` si es diaria) en el `Makefile`. Si una fuente cambia de formato (le pasó al FMI), saldrá en `Actualizaciones.md` como "fuentes con fallo": arreglar su script en `src/ingest/`.
