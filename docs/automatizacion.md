# Actualización automática

Desde el 2026-10-13 el proyecto se actualiza solo en el Mac con **launchd** (no en la nube: los datos viven en `~/financial_archive`).
El proyecto está en `~/Proyectos/financial_kb` (fuera del Escritorio: macOS bloquea a las tareas programadas leer carpetas protegidas).

| Tarea | Cuándo | Qué hace (`scripts/actualizar.sh`) |
|---|---|---|
| `com.financialkb.diario` | lun-sáb 7:30 | `make daily`: fuentes diarias (`INGEST_DAILY` del Makefile: yahoo_precios, fred_extended, fed_yieldcurve, us_liquidity, nyfed_repo, ecb, bundesbank, cboe, cboe_vx, atl_mpt, umich, alfred_vintages, eurostat) + warehouse + régimen |
| `com.financialkb.semanal` | domingo 7:00 | `make semanal`: todas las fuentes (`INGEST`) + warehouse + régimen + auditoría + reporte semanal en `obsidian/Reports/` |

- Si el Mac está apagado o dormido a esa hora, launchd la lanza al despertar.
- Resultado de cada ejecución: una línea en `obsidian/Proyecto/Actualizaciones.md` (estado, duración, fuentes con fallo, críticas de la auditoría, régimen) y el log en `~/financial_archive/logs/` (se borran a los 60 días).
- Raw de la OCDE (`oecd`, `oecd_qna`, en la semanal): además de sobrescribir `raw/<fuente>/*.csv`, cada descarga nueva se archiva comprimida y fechada en `raw/<fuente>/archivo/` (índice `indice.jsonl` con sha256; las idénticas no se duplican). Retención: todo lo de los últimos 730 días y, antes, la primera copia de cada mes (`src/ingest/_archivo_raw.py`; motivo: la OCDE revisa en origen, `docs/int/INT8b_nowcast.md` §6).
- Si alguna fuente falla o la auditoría tiene críticas: notificación de macOS. Las fuentes que fallan no paran el resto (se queda el último dato bueno).
- No commitea datos (no van a git). Excepciones: la verificación diaria commitea y sube `research/verif/*.jsonl`
  (registro append-only), y desde el 17-nov-2026 la semanal commitea **sin push** solo sus informes
  (`obsidian/Reports/*_semanal.md`, `*_signal.json`, `docs/data/audit_*_series.csv`; `scripts/commit_informes.sh`) para
  que los registros en vivo que exigen árbol limpio no aborten (`docs/int/ENSAYO_cierre_nov2026.md`). Los sube el
  siguiente registro que haga push.
- Un lock de más de 4 h se considera huérfano (Mac apagado a la fuerza) y se quita.
- Registros en vivo: `com.financialkb.paper` (10:00 + al encender; `scripts/paper_mensual.sh`: E1/E1b, K1v, B1′, B1
  desde el día 3; espera a la diaria y no corre con una actualización en marcha ni fuera de `main`) y
  `com.financialkb.int11vivo` (10:30 + al encender; INT-11 desde el día 20). Plists en `scripts/launchd/`.

## Mac apagado a la hora de la cita (14-oct)
launchd recupera una cita perdida si el Mac estaba en **reposo**, pero **no si estaba apagado** (el 14-oct arrancó a las 8:06 y la diaria de las 7:30 no se ejecutó).
Por eso hay una tercera tarea, `com.financialkb.arranque` (`RunAtLoad` + cada hora), que llama a `scripts/actualizar.sh pendiente`:
- marcas `~/financial_archive/logs/.hecho_diario` y `.hecho_semanal` (fecha de la última ejecución correcta; la semanal también marca la diaria);
- si la semanal tiene más de 7 días, o es domingo después de las 7:00 y no está hecha → semanal;
- si es lunes-sábado después de las 7:30 y la diaria de hoy no está hecha → diaria; si no, no hace nada.
En `Actualizaciones.md` estas salen como "(recuperada al encender)". Un lock evita que coincida con las tareas normales.

### Ciclos C1/M1/A1 perdidos (26-nov)
El 25-nov C1 y A1 no corrieron (Mac apagado o dormido) y M1 falló al despertar sin DNS. Ahora:
- cada `scripts/{c1,m1,a1}_gestor.sh` espera hasta 10 min a tener red (`paper-api.alpaca.markets`), corre con
  `caffeinate -i` (sin reposo a mitad del ciclo) y tiene su cerrojo `~/financial_archive/logs/.gestor_<g>.lock`
  (huérfano a los 90 min), para que launchd y la recuperación nunca lancen dos ciclos a la vez;
- `actualizar.sh pendiente` (al encender y cada hora) llama después a `scripts/recupera_gestores.sh`: lun-vie,
  entre la hora del gestor (15:45 / 16:00 / 16:15) y las 22:30, si existe `<P>_ACTIVO` y no hay línea de hoy en
  `decisiones_<g>.jsonl`, lanza el gestor. Es seguro repetirlo: `--auto` no hace nada si ya hay decisión de hoy o el
  mercado está cerrado. Si el mercado sale cerrado (festivo, cierre anticipado), apunta `.mercado_cerrado` y no
  reintenta ese día. Log en `<fecha>_recupera.log`; en `Actualizaciones.md` sale «C1 (recuperado)».
- Un fallo (p. ej. de red) se reintenta solo en el siguiente tick horario del arranque.

## Comandos
```
scripts/actualizar.sh diario      # a mano, igual que la tarea
scripts/actualizar.sh semanal
launchctl print gui/$(id -u)/com.financialkb.diario | grep -E "state|last exit"
launchctl kickstart gui/$(id -u)/com.financialkb.diario       # lanzarla ya
# instalar / desinstalar
cp scripts/launchd/com.financialkb.*.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.financialkb.diario.plist   # ídem .semanal y .arranque
launchctl bootout   gui/$(id -u) ~/Library/LaunchAgents/com.financialkb.diario.plist
```

## Fuente nueva
Añadirla a `INGEST` (y a `INGEST_DAILY` si es diaria) en el `Makefile`. Si una fuente cambia de formato (le pasó al FMI), saldrá en `Actualizaciones.md` como "fuentes con fallo": arreglar su script en `src/ingest/`.

## Espera de red (24-oct-2026)
`scripts/actualizar.sh` espera hasta 10 min a que responda `https://api.stlouisfed.org/` antes de lanzar `make`. Motivo: la semanal del 22-oct, recuperada al encender el Mac, arrancó sin DNS y fallaron fred_us, fred_extended, fed_yieldcurve, us_treasury y shiller_housing (el resto, ya con red, fue bien).
